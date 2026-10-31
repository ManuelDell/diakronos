"""BS-1a2 — Nachbesserung Website-Freigaben (Befunde des Opus-Reviews).

Was diese Datei festhaelt (je Befund ein Test, der ohne die Nachbesserung rot war)
===============================================================================

  (F1) ``inventar/schema_overlay.json`` existiert wieder. Die BS-1a-Spalten
       stehen NICHT darin (das Overlay haelt nur LIVE-Spalten aus Frappe), der
       Waechter kennt sie als ``EIGENE_SPALTEN``. Vorher fehlte die Datei
       komplett: ``test_schema_drift.test_overlay_spalten_sind_im_modell``
       uebersprang sich still und ``tools/gen_models.py`` fiel auf ``{}``
       zurueck — der Waechter war damit abgeschaltet.
  (F2) Die FUENF schreibenden Verwaltungs-Endpunkte sind nur per POST
       erreichbar. GET (Link, ``<img src>``, Proxy-Vorabruf) endet mit 405 und
       schreibt NICHTS; ``freigaben_lesen`` bleibt GET. SEC-11
       (``whitelist(methods=…)``) ist im Router NICHT vorhanden — deshalb
       prueft jeder Endpunkt die Methode selbst, VOR Rollen-Gate und DB-Zugriff.
  (F3) Ein ABGELEITETER Slug kollidiert nicht mehr: ist ``jugend-freizeit``
       vergeben, bekommt der zweite Eintrag ``jugend-freizeit-2``, der dritte
       ``-3`` — ohne 417. Ein AUSDRUECKLICH eingegebener Slug bleibt ein
       Konflikt (417): dort hat ein Mensch entschieden, da wird nichts
       umbenannt.
  (F4) Wettlauf auf den Unique-Index: der ``IntegrityError`` beim Schreiben
       wird zu 417 „bereits vergeben“ (statt 500) — und die Zeile bleibt
       unveraendert.
  (F5) ``postfach_speichern`` validiert ``sortierung`` VOR beiden Zweigen
       (Anlegen und Aendern); ein unbrauchbarer Wert legt kein Postfach an.
  (F6) SQLite-Rundlauf der Migration: ``upgrade head`` -> ``downgrade -1`` ->
       ``upgrade head`` gegen einen ALT-Stand, der die BS-1a-Spalten schon
       traegt (Zwischenstand eines abgebrochenen Laufs) — der partielle
       Unique-Index ist danach da, die Postfach-Tabelle auch, Spalten genau
       einmal.
  (F7) ``_email_pruefen`` lehnt DEL (0x7f) ab — wie die uebrigen
       Steuerzeichen.

Netz (Kartenregel 11): ausschliesslich ``--network none``, DB = ``patched_db``
(In-Memory-SQLite) bzw. eine Datei-SQLite im Testlauf. Kein Test greift auf
``settings.database_url`` zu und keiner spricht Primo oder eine echte
PostgreSQL an.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
import diakronos_app.api.website as website_api
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Beitrag, Gruppe
from diakronos_app.models.kronos import Eventkategorie, Kalender
from diakronos_app.website import freigaben as regeln

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
MODUL = "diakronos_app.api.website"
PFAD_LESEN = f"{MODUL}.freigaben_lesen"
PFAD_SETZEN = f"{MODUL}.freigabe_setzen"
PFAD_BEITRAG = f"{MODUL}.beitrag_auf_website"
PFAD_POSTFACH_SPEICHERN = f"{MODUL}.postfach_speichern"
PFAD_POSTFACH_LOESCHEN = f"{MODUL}.postfach_loeschen"
PFAD_KATEGORIE = f"{MODUL}.kategorie_oeffentlich"

#: Die schreibenden Endpunkte mit einem Aufruf, der — wenn er durchkaeme —
#: etwas aendern WUERDE. Genau diese Aufrufe muessen per GET wirkungslos sein.
SCHREIBENDE = [
    (PFAD_SETZEN, {"art": "kalender", "name": "kal-gemeinde", "freigabe": True}),
    (PFAD_BEITRAG, {"name": "b-1", "wert": True}),
    (
        PFAD_POSTFACH_SPEICHERN,
        {"slug": "allgemein", "bezeichnung": "Allgemein", "email": "kontakt@example.org"},
    ),
    (PFAD_POSTFACH_LOESCHEN, {"slug": "allgemein"}),
    (PFAD_KATEGORIE, {"name": "kat-gottesdienst", "wert": True}),
]

ADMIN_MAIL = "verwaltung@example.org"


# ── Aufbau (wie BS-1a) ────────────────────────────────────────────────────


def _benutzer_anlegen(sess, email: str, rollen=()) -> str:
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
        for idx, rolle in enumerate(rollen, start=1):
            sess.add(
                HasRole(
                    name=f"{email}-{rolle}",
                    parent=email,
                    parenttype="User",
                    parentfield="roles",
                    role=rolle,
                    docstatus=0,
                    idx=idx,
                )
            )
        sess.commit()
    return email


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    _benutzer_anlegen(sess, ADMIN_MAIL, ("Administrator",))
    sess.add(
        Kalender(
            name="kal-gemeinde",
            calendar_name="Gemeinde",
            website_freigabe=False,
            website_nur_oeffentliche_kategorien=False,
        )
    )
    sess.add(
        Kalender(
            name="kal-jugend",
            calendar_name="Jugend & Freizeit",
            website_freigabe=False,
        )
    )
    sess.add(Gruppe(name="gr-jugendkreis", gruppenname="Jugendkreis", website_freigabe=False))
    sess.add(Gruppe(name="gr-kirchenchor", gruppenname="Kirchenchor", website_freigabe=False))
    sess.add(Beitrag(name="b-1", titel="Sommerfest", veroeffentlicht=True, auf_website=False))
    sess.add(
        Eventkategorie(
            name="kat-gottesdienst", event_category_name="Gottesdienst", oeffentlich=False
        )
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt, patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    erzeugt: list[TestClient] = []

    def _bauen(benutzer: str) -> TestClient:
        set_user(benutzer)
        sid, csrf = sitzungen.anlegen(benutzer)
        c = TestClient(app)
        c.__enter__()
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        erzeugt.append(c)
        return c

    yield _bauen
    for c in erzeugt:
        c.__exit__(None, None, None)


def _post(client, pfad: str, daten: dict):
    return client.post(f"/api/method/{pfad}", json=daten)


# ── (F1) Overlay existiert und traegt die BS-1a-Spalten NICHT ─────────────


def test_f1_overlay_existiert_und_ist_gueltiges_json():
    """Ohne diese Datei ueberspringt sich der Drift-Waechter still."""
    overlay = REPO / "inventar" / "schema_overlay.json"
    assert overlay.is_file(), (
        "inventar/schema_overlay.json fehlt — tools/gen_models.py faellt auf {} "
        "zurueck und test_schema_drift.test_overlay_spalten_sind_im_modell "
        "ueberspringt sich selbst"
    )
    daten = json.loads(overlay.read_text(encoding="utf-8"))
    assert daten.get("docTypes"), "Overlay ohne docTypes ist wertlos"
    # Die Frappe-geerbten Eintraege sind weiterhin da (Stichprobe).
    assert "DSGVO Einwilligung" in daten["docTypes"]
    assert "Gruppe" in daten["docTypes"]


def test_f1_bs1a_spalten_stehen_nicht_im_overlay():
    """BS-1a-Spalten sind EIGENE (Migration), keine LIVE-Frappe-Spalten."""
    overlay = REPO / "inventar" / "schema_overlay.json"
    doc_types = json.loads(overlay.read_text(encoding="utf-8")).get("docTypes") or {}
    for doctype, feld in [
        ("Kalender", "website_freigabe"),
        ("Kalender", "website_slug"),
        ("Kalender", "website_nur_oeffentliche_kategorien"),
        ("Gruppe", "website_freigabe"),
        ("Gruppe", "website_slug"),
        ("Beitrag", "auf_website"),
    ]:
        felder = {f.get("fieldname") for f in doc_types.get(doctype) or []}
        assert feld not in felder, (
            f"{doctype}.{feld} gehoert nicht ins Overlay (kein LIVE-Frappe-Feld); "
            "der Waechter kennt es als EIGENE_SPALTEN"
        )


def test_f1_waechter_kennt_die_bs1a_spalten_als_eigene():
    quelle = (BACKEND / "tests" / "test_schema_drift.py").read_text(encoding="utf-8")
    for eintrag in (
        "Gruppe.website_freigabe",
        "Gruppe.website_slug",
        "Kalender.website_freigabe",
        "Kalender.website_slug",
        "Kalender.website_nur_oeffentliche_kategorien",
        "Beitrag.auf_website",
    ):
        assert eintrag in quelle, f"EIGENE_SPALTEN nennt {eintrag} nicht"


# ── (F2) schreibende Endpunkte nur per POST ───────────────────────────────


@pytest.mark.parametrize("pfad,daten", SCHREIBENDE)
def test_f2_get_schreibt_nicht_und_ist_405(als_benutzer, welt, pfad, daten):
    """Der klassische CSRF-per-Link: GET mit Argumenten im Query-String."""
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.get(f"/api/method/{pfad}", params=daten)
    assert antwort.status_code == 405, antwort.text
    # SEC-8: exc_type läuft über die Allowlist (MethodNotAllowed -> "Error").
    assert antwort.json()["exc_type"] in ("MethodNotAllowed", "Error")
    assert antwort.headers.get("allow") == "POST"

    welt.expire_all()
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False
    assert welt.get(Kalender, "kal-jugend").website_freigabe is False
    assert welt.get(Beitrag, "b-1").auf_website is False
    assert welt.get(Eventkategorie, "kat-gottesdienst").oeffentlich is False


@pytest.mark.parametrize("pfad,daten", SCHREIBENDE)
def test_f2_get_ohne_rolle_verraet_nichts(als_benutzer, welt, pfad, daten):
    """Die Methodenpruefung steht VOR dem Rollen-Gate: 405, nicht 403."""
    _benutzer_anlegen(welt, "mitglied@example.org", ("Mitglied",))
    c = als_benutzer("mitglied@example.org")
    antwort = c.get(f"/api/method/{pfad}", params=daten)
    assert antwort.status_code == 405, antwort.text
    # Und auch per POST bleibt es beim Rollen-Nein (fail closed).
    assert _post(c, pfad, daten).status_code == 403


def test_f2_post_geht_weiter_durch(als_benutzer, welt):
    """Die Nachbesserung darf den regulaeren Weg nicht sperren."""
    c = als_benutzer(ADMIN_MAIL)
    assert _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-gemeinde", "freigabe": True}).status_code == 200
    assert c.get(f"/api/method/{PFAD_LESEN}").status_code == 200


def test_f2_lesen_bleibt_get(als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    assert c.get(f"/api/method/{PFAD_LESEN}").status_code == 200


# ── (F3) abgeleiteter Slug weicht aus ─────────────────────────────────────


def _slug(antwort) -> str:
    return antwort.json()["message"]["slug"]


def test_f3_zwei_gleichnamige_kalender_bekommen_2_und_3(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    # Drei Kalender mit demselben Anzeigenamen (der Bestand hat nur zwei).
    welt.add(Kalender(name="kal-jugend-2", calendar_name="Jugend & Freizeit"))
    welt.add(Kalender(name="kal-jugend-3", calendar_name="Jugend & Freizeit"))
    welt.commit()

    erste = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-jugend", "freigabe": True})
    assert erste.status_code == 200, erste.text
    assert _slug(erste) == "jugend-freizeit"

    zweite = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-jugend-2", "freigabe": True})
    assert zweite.status_code == 200, zweite.text
    assert _slug(zweite) == "jugend-freizeit-2"

    dritte = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-jugend-3", "freigabe": True})
    assert dritte.status_code == 200, dritte.text
    assert _slug(dritte) == "jugend-freizeit-3"

    welt.expire_all()
    assert welt.get(Kalender, "kal-jugend-2").website_slug == "jugend-freizeit-2"
    assert welt.get(Kalender, "kal-jugend-3").website_slug == "jugend-freizeit-3"


def test_f3_fallback_bereich_weicht_ebenfalls_aus(als_benutzer, welt):
    """„---“ ergibt den Rueckfall ``bereich`` — auch der muss eindeutig sein."""
    c = als_benutzer(ADMIN_MAIL)
    welt.add(Kalender(name="kal-strich-1", calendar_name="---"))
    welt.add(Kalender(name="kal-strich-2", calendar_name="***"))
    welt.commit()

    erste = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-strich-1", "freigabe": True})
    assert _slug(erste) == "bereich"
    zweite = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-strich-2", "freigabe": True})
    assert zweite.status_code == 200, zweite.text
    assert _slug(zweite) == "bereich-2"


def test_f3_ausdruecklicher_slug_bleibt_ein_konflikt(als_benutzer, welt):
    """Ein MENSCH hat den Slug getippt: nicht stillschweigend umbenennen."""
    c = als_benutzer(ADMIN_MAIL)
    assert _post(
        c, PFAD_SETZEN,
        {"art": "kalender", "name": "kal-gemeinde", "freigabe": True, "slug": "gemeinde"},
    ).status_code == 200
    antwort = _post(
        c, PFAD_SETZEN,
        {"art": "kalender", "name": "kal-jugend", "freigabe": True, "slug": "gemeinde"},
    )
    assert antwort.status_code == 417, antwort.text
    assert "vergeben" in antwort.json()["message"]
    welt.expire_all()
    assert welt.get(Kalender, "kal-jugend").website_slug is None


def test_f3_ausweichen_bleibt_innerhalb_der_laenge(als_benutzer, welt):
    """SLUG_MAX gilt fuer den GANZEN Slug — der Zusatz muss hineinpassen."""
    lang = "a" * regeln.SLUG_MAX
    c = als_benutzer(ADMIN_MAIL)
    welt.add(Kalender(name="kal-lang-1", calendar_name=lang))
    welt.add(Kalender(name="kal-lang-2", calendar_name=lang))
    welt.commit()
    erste = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-lang-1", "freigabe": True})
    assert _slug(erste) == lang
    zweite = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-lang-2", "freigabe": True})
    assert zweite.status_code == 200, zweite.text
    assert len(_slug(zweite)) <= regeln.SLUG_MAX
    assert _slug(zweite).endswith("-2")


# ── (F4) Wettlauf auf den Unique-Index ────────────────────────────────────


def test_f4_integrity_error_wird_zu_417(als_benutzer, welt, monkeypatch):
    """Zwei gleichzeitige Aufrufe: der zweite kommt an der Vorpruefung vorbei."""
    import diakronos_app.frappe_compat.api_helpers as helpers

    c = als_benutzer(ADMIN_MAIL)

    def _kracht(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(helpers, "_update_doc", _kracht)
    antwort = _post(
        c, PFAD_SETZEN,
        {"art": "kalender", "name": "kal-gemeinde", "freigabe": True, "slug": "gemeinde"},
    )
    assert antwort.status_code == 417, antwort.text
    assert "vergeben" in antwort.json()["message"]
    assert antwort.json()["exc_type"] == "Error"
    welt.expire_all()
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False


def test_f4_anderer_fehler_bleibt_ein_fehler(als_benutzer, welt, monkeypatch):
    """Nicht jeder Fehler ist ein Slug-Konflikt — nur der Unique-Index."""
    import diakronos_app.frappe_compat.api_helpers as helpers

    c = als_benutzer(ADMIN_MAIL)

    def _kracht(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(helpers, "_update_doc", _kracht)
    with pytest.raises(RuntimeError):
        _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-gemeinde", "freigabe": True})


# ── (F5) sortierung vor beiden Zweigen ────────────────────────────────────

BASIS = {"slug": "allgemein", "bezeichnung": "Allgemein", "email": "kontakt@example.org"}


@pytest.mark.parametrize("sortierung", ["drei", "1,5", [1], {"a": 1}])
def test_f5_neues_postfach_mit_kaputter_sortierung_legt_nichts_an(als_benutzer, welt, sortierung):
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(c, PFAD_POSTFACH_SPEICHERN, {**BASIS, "sortierung": sortierung})
    assert antwort.status_code == 417, antwort.text
    assert "Sortierung" in antwort.json()["message"], antwort.text
    welt.expire_all()
    assert welt.get(WebsiteKontaktPostfach, "allgemein") is None


def test_f5_bestehendes_postfach_mit_kaputter_sortierung_bleibt_unveraendert(als_benutzer, welt):
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    c = als_benutzer(ADMIN_MAIL)
    assert _post(c, PFAD_POSTFACH_SPEICHERN, {**BASIS, "sortierung": 10}).status_code == 200
    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {**BASIS, "bezeichnung": "Neu", "sortierung": "drei"},
    )
    assert antwort.status_code == 417, antwort.text
    welt.expire_all()
    zeile = welt.get(WebsiteKontaktPostfach, "allgemein")
    assert zeile.bezeichnung == "Allgemein"
    assert zeile.sortierung == 10


def test_f5_gueltige_sortierung_als_text_geht(als_benutzer, welt):
    """Formularwerte kommen als String — „20“ ist eine Zahl."""
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(c, PFAD_POSTFACH_SPEICHERN, {**BASIS, "sortierung": "20"})
    assert antwort.status_code == 200, antwort.text
    welt.expire_all()
    assert welt.get(WebsiteKontaktPostfach, "allgemein").sortierung == 20


# ── (F6) SQLite-Rundlauf der Migration ────────────────────────────────────


def _cfg(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _spalten(eng, tabelle: str) -> list[str]:
    from sqlalchemy import inspect

    return [str(s["name"]).lower() for s in inspect(eng).get_columns(tabelle)]


def _indizes(eng, tabelle: str) -> set[str]:
    from sqlalchemy import inspect

    return {str(ix.get("name")) for ix in inspect(eng).get_indexes(tabelle)}


def _tabelle_da(eng, name: str) -> bool:
    from sqlalchemy import inspect

    return str(name).lower() in {t.lower() for t in inspect(eng).get_table_names()}


def _stempel(cfg, url: str) -> None:
    """Setzt den Alembic-Stand auf ``web1b_primo_konto`` (Vorgaengerstand).

    Die vollstaendige Kette ist auf SQLite nicht fahrbar: ``p1bmodelle`` legt
    Fremdschluessel per ``ALTER TABLE`` an, was der SQLite-Dialekt nicht kann
    (``No support for ALTER of constraints in SQLite dialect``). Deshalb wird
    die BS-1a-Welt direkt angelegt und der Stand gestempelt — genau der
    Zustand, den die Vorgaenger-Migration im Betrieb hinterlaesst. Gestempelt
    wird ueber :class:`MigrationContext` (kein ``command.stamp``): der laedt
    die ``env.py`` und damit die ganze Kette.
    """
    from alembic.migration import MigrationContext

    from sqlalchemy import create_engine

    eng = create_engine(url, future=True)
    try:
        with eng.begin() as conn:
            ctx = MigrationContext.configure(conn)
            ctx.stamp(_SCRIPT(), "web1b_primo_konto")
    finally:
        eng.dispose()


def _SCRIPT():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def _vorwelt(eng) -> None:
    """Die drei Tabellen der BS-1a-Freigaben, wie sie vorher aussehen."""
    from sqlalchemy import text

    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kalender ("
                "name VARCHAR(140) PRIMARY KEY, calendar_name VARCHAR(140))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE gruppe ("
                "name VARCHAR(140) PRIMARY KEY, gruppenname VARCHAR(140))"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE beitrag ("
                "name VARCHAR(140) PRIMARY KEY, titel VARCHAR(140))"
            )
        )


def _alembic_stand(eng) -> str | None:
    from sqlalchemy import text

    with eng.begin() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _bewegung(cfg, url: str, ziel: str) -> None:
    """Ein echter ``upgrade``/``downgrade``-Lauf (ueber die ``env.py``).

    ``env.py`` liest die URL ueber ``settings.database_url`` (nicht aus der
    ``Config``) — deshalb wird die Einstellung fuer die Dauer des Laufs
    gesetzt und danach zurueckgegeben.
    """
    from alembic import command

    from diakronos_app.settings import settings

    alt = settings.database_url
    settings.database_url = url
    try:
        if ziel == "head":
            command.upgrade(cfg, "head")
        else:
            command.downgrade(cfg, ziel)
    finally:
        settings.database_url = alt


def test_f6_sqlite_rundlauf_upgrade_downgrade_upgrade(monkeypatch, tmp_path):
    """upgrade head -> downgrade -1 -> upgrade head, partieller Index inklusive."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    from diakronos_app.settings import settings

    url = f"sqlite+pysqlite:///{tmp_path / 'bs1a2-rundlauf.sqlite'}"
    monkeypatch.setattr(settings, "database_url", url, raising=False)
    cfg = _cfg(url)
    eng = create_engine(url, future=True, poolclass=NullPool)
    try:
        _vorwelt(eng)
        _stempel(cfg, url)
        assert _alembic_stand(eng) == "web1b_primo_konto"

        _bewegung(cfg, url, "head")
        assert _alembic_stand(eng) == "bs1a_website_freigaben"
        assert "website_slug" in _spalten(eng, "kalender")
        assert "uq_kalender_website_slug" in _indizes(eng, "kalender")
        assert "uq_gruppe_website_slug" in _indizes(eng, "gruppe")
        assert _tabelle_da(eng, "website_kontakt_postfach")

        # Partieller Index wirklich partiell: zwei NULL-Slugs sind erlaubt,
        # derselbe Slug zweimal nicht.
        with eng.begin() as conn:
            conn.execute(text("INSERT INTO kalender (name) VALUES ('k1'), ('k2')"))
            conn.execute(
                text("UPDATE kalender SET website_slug = 'gemeinde' WHERE name = 'k1'")
            )
        with pytest.raises(IntegrityError):
            with eng.begin() as conn:
                conn.execute(
                    text("UPDATE kalender SET website_slug = 'gemeinde' WHERE name = 'k2'")
                )

        _bewegung(cfg, url, "-1")
        assert _alembic_stand(eng) == "web1b_primo_konto"
        assert "website_slug" not in _spalten(eng, "kalender")
        assert "website_freigabe" not in _spalten(eng, "kalender")
        assert "auf_website" not in _spalten(eng, "beitrag")
        assert "uq_kalender_website_slug" not in _indizes(eng, "kalender")
        assert not _tabelle_da(eng, "website_kontakt_postfach")

        _bewegung(cfg, url, "head")
        assert _alembic_stand(eng) == "bs1a_website_freigaben"
        assert _spalten(eng, "kalender").count("website_slug") == 1
        assert _spalten(eng, "gruppe").count("website_slug") == 1
        assert "uq_kalender_website_slug" in _indizes(eng, "kalender")
        assert "uq_gruppe_website_slug" in _indizes(eng, "gruppe")
        assert _tabelle_da(eng, "website_kontakt_postfach")
    finally:
        eng.dispose()


def test_f6_altstand_mit_vorhandenen_spalten_ist_idempotent():
    """Abgebrochener Erstlauf: Spalten da, Index/Tabelle fehlen noch."""
    from sqlalchemy import create_engine, text

    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    try:
        # Nur die BS-1a-Spalten, wie ein abgebrochener Lauf sie hinterlaesst.
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE kalender (name VARCHAR(140) PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE gruppe (name VARCHAR(140) PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE beitrag (name VARCHAR(140) PRIMARY KEY)"))
            conn.execute(
                text("ALTER TABLE kalender ADD COLUMN website_freigabe BOOLEAN NOT NULL DEFAULT false")
            )
            conn.execute(text("ALTER TABLE kalender ADD COLUMN website_slug VARCHAR(140)"))
            conn.execute(text("ALTER TABLE gruppe ADD COLUMN website_freigabe BOOLEAN"))
            conn.execute(text("ALTER TABLE beitrag ADD COLUMN auf_website BOOLEAN NOT NULL DEFAULT false"))

        import importlib.util

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        pfad = BACKEND / "alembic" / "versions" / "bs1a_website_freigaben.py"
        spec = importlib.util.spec_from_file_location("bs1a_revision", pfad)
        assert spec is not None and spec.loader is not None
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)

        with eng.connect() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                modul.upgrade()
            conn.commit()

        assert _spalten(eng, "kalender").count("website_freigabe") == 1
        assert _spalten(eng, "kalender").count("website_slug") == 1
        assert "uq_kalender_website_slug" in _indizes(eng, "kalender")
        assert _tabelle_da(eng, "website_kontakt_postfach")
    finally:
        eng.dispose()


# ── (F7) _email_pruefen: DEL ist ein Steuerzeichen ────────────────────────


@pytest.mark.parametrize(
    "adresse",
    [
        "kon\x7ftakt@example.org",
        "\x7f@example.org",
        "kontakt@\x7fexample.org",
        "kon\ttakt@example.org",
        "kon\ntakt@example.org",
        "kon\x00takt@example.org",
    ],
)
def test_f7_steuerzeichen_werden_abgelehnt(adresse):
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError

    with pytest.raises(FrappeCompatError):
        website_api._email_pruefen(adresse)


@pytest.mark.parametrize(
    "adresse",
    ["kontakt@example.org", "a.b+c@sub.example.org", "Kontakt@Example.ORG"],
)
def test_f7_gueltige_adressen_bleiben_gueltig(adresse):
    assert website_api._email_pruefen(adresse) == adresse


def test_f7_postfach_endpunkt_lehnt_del_ab(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(c, PFAD_POSTFACH_SPEICHERN, {**BASIS, "email": "kon\x7ftakt@example.org"})
    assert antwort.status_code == 417, antwort.text
