"""BS-1a — Website-Freigaben: Datenmodell, Migration, Verwaltungs-API.

Was die Karte verspricht (und dieser Test festhaelt)
====================================================

  (A3) Rollen: nur ``System Manager``, ``Administrator`` und
       ``Website-Moderator`` duerfen lesen und schreiben — alle anderen Rollen
       bekommen **403** (`PermissionError`), ein Gast **401/403**; ohne
       CSRF-Token **417**. Fail closed: ein abgewiesener Aufruf schreibt
       nichts. Eingabefehler sind **417** mit einer deutschen, generischen
       Meldung (Frappes Convention, die die SPA erwartet — kein zweiter
       Statuscode, SEC-7); der Klassenname bleibt nach SEC-8 ``Error``,
       unbekannte Kennungen sind **404**.
  (A2) Endpunkte: ``freigaben_lesen`` (GET), ``freigabe_setzen``,
       ``beitrag_auf_website``, ``postfach_speichern``, ``postfach_loeschen``,
       ``kategorie_oeffentlich`` (POST) — Antwortformen wie im
       Abschlusskommentar der Karte beschrieben.
  (A1) Migration ``bs1a_website_freigaben``: Defaulte AUS, Slug-Eindeutigkeit
       (auch pruefbar auf der Test-DB), ein einziger Head, ``downgrade``
       entfernt alles wieder. Der volle ``upgrade``/``downgrade``/``check``
       gegen PostgreSQL steht im Abnahmeprotokoll der Karte (Wegwerf-DB);
       hier laeuft die Kette am Skript selbst (Reihenfolge, Kopf, Befehle).
  Slug-Regeln: nur ``[a-z0-9-]``, reservierte Werte abgelehnt.
  Postfach-Rueckfall (WEB-10): ohne Zeile gilt ``WEBSITE_KONTAKT_EMPFAENGER``
  als Postfach ``standard``; sind Zeilen vorhanden, aber keine aktiv, ist die
  oeffentliche Liste LEER (kein stiller Rueckfall).

Netz (Kartenregel 11): ausschliesslich ``--network none``, DB = ``patched_db``
(In-Memory-SQLite). Kein Test greift auf ``settings.database_url`` zu und
keiner spricht Primo an.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Beitrag, Gruppe
from diakronos_app.models.kronos import Eventkategorie, Kalender
from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach
from diakronos_app.settings import settings
from diakronos_app.website import freigaben as regeln

MODUL = "diakronos_app.api.website"
PFAD_LESEN = f"{MODUL}.freigaben_lesen"
PFAD_SETZEN = f"{MODUL}.freigabe_setzen"
PFAD_BEITRAG = f"{MODUL}.beitrag_auf_website"
PFAD_POSTFACH_SPEICHERN = f"{MODUL}.postfach_speichern"
PFAD_POSTFACH_LOESCHEN = f"{MODUL}.postfach_loeschen"
PFAD_KATEGORIE = f"{MODUL}.kategorie_oeffentlich"

ADMIN_MAIL = "verwaltung@example.org"
SYSTEMMANAGER_MAIL = "system@example.org"
MODERATOR_MAIL = "moderator@example.org"
MITGLIED_MAIL = "mitglied@example.org"
KALENDER_ADMIN_MAIL = "kalenderadmin@example.org"

POSTFACH_ADRESSE = "kontakt@example.org"


# ── Benutzer/Rollen ────────────────────────────────────────────────────────


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
    """Bestand: zwei Kalender, zwei Gruppen, ein Beitrag, eine Kategorie."""
    sess = patched_db()
    _benutzer_anlegen(sess, ADMIN_MAIL, ("Administrator",))
    _benutzer_anlegen(sess, SYSTEMMANAGER_MAIL, ("System Manager",))
    _benutzer_anlegen(sess, MODERATOR_MAIL, ("Website-Moderator",))
    _benutzer_anlegen(sess, MITGLIED_MAIL, ("Mitglied",))
    _benutzer_anlegen(sess, KALENDER_ADMIN_MAIL, ("Kalenderadministrator",))

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
    sess.add(
        Beitrag(name="b-1", titel="Sommerfest", veroeffentlicht=True, auf_website=False)
    )
    sess.add(
        Beitrag(name="b-2", titel="Entwurf", veroeffentlicht=False, auf_website=False)
    )
    sess.add(Eventkategorie(name="kat-gottesdienst", event_category_name="Gottesdienst", oeffentlich=False))
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt, patched_db, fake_redis):
    """Factory: HTTP-Client mit echter Sitzung (und CSRF-Token) je Benutzer."""
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


@pytest.fixture()
def gast():
    """Client ohne Sitzung (Gast)."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def _post(client, pfad: str, daten: dict):
    """POST wie die SPA: JSON-Koerper + CSRF-Header."""
    return client.post(f"/api/method/{pfad}", json=daten)


# ── (A3) Rollenmatrix ──────────────────────────────────────────────────────


@pytest.mark.parametrize("benutzer", [ADMIN_MAIL, SYSTEMMANAGER_MAIL, MODERATOR_MAIL])
def test_berechtigte_rollen_duerfen_lesen(als_benutzer, benutzer):
    c = als_benutzer(benutzer)
    antwort = c.get(f"/api/method/{PFAD_LESEN}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert {k["name"] for k in daten["kalender"]} == {"kal-gemeinde", "kal-jugend"}
    assert {g["name"] for g in daten["gruppen"]} == {"gr-jugendkreis", "gr-kirchenchor"}
    assert daten["beitraege_anzahl"] == 0
    assert daten["postfaecher"] == []


@pytest.mark.parametrize("benutzer", [MITGLIED_MAIL, KALENDER_ADMIN_MAIL])
def test_andere_rollen_bekommen_403(als_benutzer, benutzer, welt):
    """Es reicht NICHT, irgendeine Verwaltungsrolle zu haben (Kalenderadmin)."""
    c = als_benutzer(benutzer)
    assert c.get(f"/api/method/{PFAD_LESEN}").status_code == 403
    antwort = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-gemeinde", "freigabe": True})
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"
    # Fail closed: nichts geschrieben.
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False


def test_gast_bekommt_401_oder_403(gast):
    """Gast: die Sitzungs-Middleware antwortet 401, das Rollen-Gate 403 — beides
    ist ein sauberes Nein (Karte A3: „Gast -> 401/403")."""
    assert gast.get(f"/api/method/{PFAD_LESEN}").status_code in (401, 403)


def test_post_ohne_csrf_wird_abgewiesen(welt, fake_redis):
    """Ohne CSRF-Token (Sitzung vorhanden) -> 417 und KEINE Aenderung."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user(ADMIN_MAIL)
    sid, _csrf = sitzungen.anlegen(ADMIN_MAIL)
    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        antwort = c.post(
            f"/api/method/{PFAD_SETZEN}",
            json={"art": "kalender", "name": "kal-gemeinde", "freigabe": True},
        )
    assert antwort.status_code == 417, antwort.text
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False


# ── (A1) Defaulte AUS ──────────────────────────────────────────────────────


def test_defaults_sind_aus(als_benutzer, welt):
    daten = als_benutzer(ADMIN_MAIL).get(f"/api/method/{PFAD_LESEN}").json()["message"]
    assert all(k["freigabe"] is False for k in daten["kalender"])
    assert all(g["freigabe"] is False for g in daten["gruppen"])
    assert daten["beitraege_anzahl"] == 0
    assert all(k["oeffentlich"] is False for k in daten["kategorien"])


def test_neue_zeilen_ohne_angabe_sind_nicht_freigegeben(patched_db):
    """Ein frisch angelegter Kalender ist NICHT oeffentlich (Default AUS)."""
    sess = patched_db()
    sess.add(Kalender(name="kal-neu", calendar_name="Neu"))
    sess.add(Gruppe(name="gr-neu", gruppenname="Neu"))
    sess.add(Beitrag(name="b-neu", titel="Neu"))
    sess.commit()
    assert sess.get(Kalender, "kal-neu").website_freigabe is False
    assert sess.get(Kalender, "kal-neu").website_nur_oeffentliche_kategorien is False
    assert sess.get(Kalender, "kal-neu").website_slug is None
    assert sess.get(Gruppe, "gr-neu").website_freigabe is False
    assert sess.get(Beitrag, "b-neu").auf_website is False


# ── (A2) freigabe_setzen ───────────────────────────────────────────────────


def test_freigabe_setzen_leitet_slug_ab(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-jugend", "freigabe": True})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["freigabe"] is True
    assert daten["slug"] == "jugend-freizeit"
    assert daten["nur_oeffentliche_kategorien"] is False

    welt.expire_all()
    zeile = welt.get(Kalender, "kal-jugend")
    assert zeile.website_freigabe is True
    assert zeile.website_slug == "jugend-freizeit"


def test_freigabe_setzen_nimmt_eigenen_slug_und_kategorie_regel(als_benutzer, welt):
    c = als_benutzer(MODERATOR_MAIL)
    antwort = _post(
        c,
        PFAD_SETZEN,
        {
            "art": "kalender",
            "name": "kal-gemeinde",
            "freigabe": True,
            "slug": "gottesdienste",
            "nur_oeffentliche_kategorien": True,
        },
    )
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["slug"] == "gottesdienste"
    assert daten["nur_oeffentliche_kategorien"] is True


def test_bestehender_slug_bleibt_beim_umbenennen(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    _post(c, PFAD_SETZEN, {"art": "gruppe", "name": "gr-kirchenchor", "freigabe": True})
    welt.expire_all()
    welt.get(Gruppe, "gr-kirchenchor").gruppenname = "Chor (neu)"
    welt.commit()
    antwort = _post(c, PFAD_SETZEN, {"art": "gruppe", "name": "gr-kirchenchor", "freigabe": True})
    assert antwort.json()["message"]["slug"] == "kirchenchor"


@pytest.mark.parametrize(
    "slug",
    ["Diakronos", "primo", "admin", "api", "login", "standard", "mit leer", "mit_unterstrich", "ÄÖÜ"],
)
def test_reservierte_und_ungueltige_slugs_werden_abgelehnt(als_benutzer, welt, slug):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c,
        PFAD_SETZEN,
        {"art": "kalender", "name": "kal-gemeinde", "freigabe": True, "slug": slug},
    )
    assert antwort.status_code == 417, antwort.text
    # SEC-8: der Klassenname bleibt generisch — der Vertrag ist Status +
    # deutsche Meldung (kein Python-Name, keine Signatur in der Antwort).
    assert antwort.json()["exc_type"] == "Error"
    assert "Kürzel" in antwort.json()["message"]
    welt.expire_all()
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False


def test_slug_muss_eindeutig_sein(als_benutzer, welt):
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
    assert welt.get(Kalender, "kal-jugend").website_freigabe is False


def test_slug_eindeutigkeit_gilt_ueber_arten_hinweg_nicht(als_benutzer, welt):
    """Gleicher Slug in Kalender UND Gruppe ist erlaubt (verschiedene Tabellen)."""
    c = als_benutzer(ADMIN_MAIL)
    assert _post(
        c, PFAD_SETZEN,
        {"art": "kalender", "name": "kal-gemeinde", "freigabe": True, "slug": "gemeinde"},
    ).status_code == 200
    antwort = _post(
        c, PFAD_SETZEN,
        {"art": "gruppe", "name": "gr-jugendkreis", "freigabe": True, "slug": "gemeinde"},
    )
    assert antwort.status_code == 200, antwort.text


def test_derselbe_slug_an_derselben_zeile_ist_kein_konflikt(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    for _ in range(2):
        antwort = _post(
            c, PFAD_SETZEN,
            {"art": "gruppe", "name": "gr-kirchenchor", "freigabe": True, "slug": "chor"},
        )
        assert antwort.status_code == 200, antwort.text


def test_unbekannte_art_und_unbekannter_name(als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    assert _post(c, PFAD_SETZEN, {"art": "beitrag", "name": "x", "freigabe": True}).status_code == 417
    antwort = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "gibt-es-nicht", "freigabe": True})
    assert antwort.status_code == 404, antwort.text
    assert antwort.json()["exc_type"] == "Error"


def test_falscher_wahrheitswert_wird_abgelehnt(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(c, PFAD_SETZEN, {"art": "kalender", "name": "kal-gemeinde", "freigabe": "vielleicht"})
    assert antwort.status_code == 417, antwort.text
    welt.expire_all()
    assert welt.get(Kalender, "kal-gemeinde").website_freigabe is False


def test_kategorie_regel_nur_fuer_kalender(als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c, PFAD_SETZEN,
        {"art": "gruppe", "name": "gr-kirchenchor", "freigabe": True,
         "nur_oeffentliche_kategorien": True},
    )
    assert antwort.status_code == 417, antwort.text


# ── (A2) beitrag_auf_website ───────────────────────────────────────────────


def test_beitrag_auf_website_und_anzahl(als_benutzer, welt):
    c = als_benutzer(MODERATOR_MAIL)
    antwort = _post(c, PFAD_BEITRAG, {"name": "b-1", "wert": True})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten == {
        "name": "b-1",
        "titel": "Sommerfest",
        "auf_website": True,
        "veroeffentlicht": True,
    }
    lesen = c.get(f"/api/method/{PFAD_LESEN}").json()["message"]
    assert lesen["beitraege_anzahl"] == 1
    assert lesen["beitraege"] == [{"name": "b-1", "titel": "Sommerfest", "veroeffentlicht": True}]

    # Zuruecknehmen
    assert _post(c, PFAD_BEITRAG, {"name": "b-1", "wert": False}).json()["message"]["auf_website"] is False
    assert c.get(f"/api/method/{PFAD_LESEN}").json()["message"]["beitraege_anzahl"] == 0


def test_beitrag_nicht_veroeffentlicht_ist_vorbereitung(als_benutzer, welt):
    """auf_website ohne veroeffentlicht ist erlaubt, aber (spaeter) wirkungslos."""
    c = als_benutzer(ADMIN_MAIL)
    daten = _post(c, PFAD_BEITRAG, {"name": "b-2", "wert": 1}).json()["message"]
    assert daten["auf_website"] is True
    assert daten["veroeffentlicht"] is False


def test_beitrag_unbekannt_ist_404(als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    assert _post(c, PFAD_BEITRAG, {"name": "gibt-es-nicht", "wert": True}).status_code == 404


# ── (A2) Postfaecher + Rueckfall (WEB-10) ──────────────────────────────────


def test_postfach_anlegen_aendern_loeschen(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {"slug": "allgemein", "bezeichnung": "Allgemeine Anfragen", "email": POSTFACH_ADRESSE},
    )
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["postfach"] == {
        "slug": "allgemein",
        "bezeichnung": "Allgemeine Anfragen",
        "email": POSTFACH_ADRESSE,
        "aktiv": True,
    }

    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {"slug": "allgemein", "bezeichnung": "Kontakt", "email": "neu@example.org", "aktiv": False},
    )
    assert antwort.json()["message"]["postfach"]["bezeichnung"] == "Kontakt"
    assert antwort.json()["message"]["postfach"]["aktiv"] is False

    lesen = c.get(f"/api/method/{PFAD_LESEN}").json()["message"]
    assert [p["slug"] for p in lesen["postfaecher"]] == ["allgemein"]

    antwort = _post(c, PFAD_POSTFACH_LOESCHEN, {"slug": "allgemein"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["postfaecher"] == []
    assert _post(c, PFAD_POSTFACH_LOESCHEN, {"slug": "allgemein"}).status_code == 404


@pytest.mark.parametrize("slug", ["standard", "Diakronos", "mit_leer", "mit leer"])
def test_postfach_slug_regeln(als_benutzer, slug):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {"slug": slug, "bezeichnung": "X", "email": POSTFACH_ADRESSE},
    )
    assert antwort.status_code == 417, antwort.text


@pytest.mark.parametrize("email", ["", "keine-adresse", "a@b", "zwei@@example.org", "a b@example.org"])
def test_postfach_email_wird_geprueft(als_benutzer, email):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {"slug": "allgemein", "bezeichnung": "X", "email": email},
    )
    assert antwort.status_code == 417, antwort.text


def test_postfach_ohne_bezeichnung_wird_abgelehnt(als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    antwort = _post(
        c, PFAD_POSTFACH_SPEICHERN,
        {"slug": "allgemein", "bezeichnung": "  ", "email": POSTFACH_ADRESSE},
    )
    assert antwort.status_code == 417, antwort.text


def test_rueckfall_auf_website_kontakt_empfaenger(monkeypatch, welt, patched_db):
    """Ohne Zeile gilt WEBSITE_KONTAKT_EMPFAENGER als Postfach „standard“."""
    monkeypatch.setattr(settings, "website_kontakt_empfaenger", POSTFACH_ADRESSE, raising=False)
    sess = patched_db()
    liste = regeln.postfaecher_oeffentlich(sess, settings.website_kontakt_empfaenger)
    assert [(p.slug, p.email) for p in liste] == [("standard", POSTFACH_ADRESSE)]


def test_ohne_zeile_und_ohne_einstellung_ist_nichts_eingerichtet(monkeypatch, patched_db):
    monkeypatch.setattr(settings, "website_kontakt_empfaenger", "", raising=False)
    assert regeln.postfaecher_oeffentlich(patched_db(), "") == []


def test_zeilen_ohne_aktives_postfach_ergeben_leere_liste(monkeypatch, patched_db):
    """Bewusst abgeschaltet != „noch nie eingerichtet“: kein stiller Rueckfall."""
    monkeypatch.setattr(settings, "website_kontakt_empfaenger", POSTFACH_ADRESSE, raising=False)
    sess = patched_db()
    sess.add(
        WebsiteKontaktPostfach(
            slug="allgemein", bezeichnung="Allgemein", email=POSTFACH_ADRESSE,
            aktiv=False, sortierung=0,
        )
    )
    sess.commit()
    assert regeln.postfaecher_oeffentlich(sess, POSTFACH_ADRESSE) == []


def test_freigaben_lesen_meldet_den_rueckfall(monkeypatch, als_benutzer):
    monkeypatch.setattr(settings, "website_kontakt_empfaenger", POSTFACH_ADRESSE, raising=False)
    daten = als_benutzer(ADMIN_MAIL).get(f"/api/method/{PFAD_LESEN}").json()["message"]
    assert daten["postfaecher"] == []
    assert daten["postfach_fallback"] == {"aktiv": True, "bezeichnung": "Allgemein"}


def test_postfach_liste_sortiert(als_benutzer, welt):
    c = als_benutzer(ADMIN_MAIL)
    for slug, sortierung in (("zwei", 20), ("eins", 10), ("drei", 30)):
        _post(
            c, PFAD_POSTFACH_SPEICHERN,
            {"slug": slug, "bezeichnung": slug.title(), "email": POSTFACH_ADRESSE,
             "sortierung": sortierung},
        )
    daten = c.get(f"/api/method/{PFAD_LESEN}").json()["message"]
    assert [p["slug"] for p in daten["postfaecher"]] == ["eins", "zwei", "drei"]
    assert daten["postfach_fallback"]["aktiv"] is False


# ── (A2) kategorie_oeffentlich ─────────────────────────────────────────────


def test_kategorie_oeffentlich_setzen(als_benutzer, welt):
    c = als_benutzer(MODERATOR_MAIL)
    antwort = _post(c, PFAD_KATEGORIE, {"name": "kat-gottesdienst", "wert": True})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {
        "name": "kat-gottesdienst",
        "titel": "Gottesdienst",
        "oeffentlich": True,
    }
    welt.expire_all()
    assert welt.get(Eventkategorie, "kat-gottesdienst").oeffentlich is True
    assert _post(c, PFAD_KATEGORIE, {"name": "gibt-es-nicht", "wert": True}).status_code == 404


def test_normales_mitglied_darf_kategorie_nicht_setzen(als_benutzer, welt):
    c = als_benutzer(MITGLIED_MAIL)
    assert _post(c, PFAD_KATEGORIE, {"name": "kat-gottesdienst", "wert": True}).status_code == 403
    welt.expire_all()
    assert welt.get(Eventkategorie, "kat-gottesdienst").oeffentlich is False


# ── (A1) Migration: Kette, Kopf, Inhalt ────────────────────────────────────


def _script() -> ScriptDirectory:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_ist_teil_der_einen_kette():
    """Genau EIN Kopf — und bs1a haengt auf dem Weg dorthin.

    Bis ON-1 war `bs1a_website_freigaben` selbst der Kopf. Jede neue Migration
    haengt sich hinten an (seit ON-2b/ON-1: `on2_einrichtung` -> `on1_einrichtung`);
    der Waechter prueft deshalb, was er wirklich zusichern will: eine einzige
    Kette ohne Gabelung, in der bs1a vorkommt. KEIN Literal auf den Nachfolger —
    das braeche beim naechsten Anhaengen.
    """
    script = _script()
    heads = script.get_heads()
    assert len(heads) == 1, heads
    # Genau EINE Migration haengt unmittelbar an bs1a (keine Gabelung dort).
    nachfolger = [r for r in script.walk_revisions() if r.down_revision == "bs1a_website_freigaben"]
    assert len(nachfolger) == 1, [r.revision for r in nachfolger]
    assert script.get_revision(nachfolger[0].revision) is not None


def test_migration_haengt_an_web1b():
    revision = _script().get_revision("bs1a_website_freigaben")
    assert revision.down_revision == "web1b_primo_konto"


def test_migration_nennt_alle_felder_und_die_tabelle():
    revision = _script().get_revision("bs1a_website_freigaben")
    quelle = Path(revision.path).read_text(encoding="utf-8")
    for feld in (
        "website_freigabe",
        "website_slug",
        "website_nur_oeffentliche_kategorien",
        "auf_website",
        "website_kontakt_postfach",
    ):
        assert feld in quelle, feld
    assert "def upgrade" in quelle and "def downgrade" in quelle
    # Defaulte AUS: die Spalten kommen mit server_default false.
    assert quelle.count('sa.text("false")') >= 4
    # Slugs sind eindeutig (partielle Unique-Indizes).
    assert "unique=True" in quelle
    assert "uq_kalender_website_slug" in quelle and "uq_gruppe_website_slug" in quelle


def test_migration_ist_idempotent_gebaut():
    """Jeder Schritt prueft den Bestand — zweiter Lauf aendert nichts."""
    revision = _script().get_revision("bs1a_website_freigaben")
    quelle = Path(revision.path).read_text(encoding="utf-8")
    assert "if not _hat_spalte(bind, tabelle, spalte)" in quelle
    assert "if not _hat_index(bind, tabelle, index)" in quelle
    assert "if not _hat_tabelle(bind, TABELLE_POSTFACH)" in quelle


# ── Slug-Regeln (reine Funktionen) ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text,erwartet",
    [
        ("Gemeinde", "gemeinde"),
        ("Jugend & Freizeit", "jugend-freizeit"),
        ("Musik & Chor", "musik-chor"),
        ("Größe", "groesse"),
        ("Café", "cafe"),
        ("admin", "bereich"),
        ("---", "bereich"),
        ("", "bereich"),
    ],
)
def test_slug_aus_text(text, erwartet):
    assert regeln.slug_aus_text(text) == erwartet


@pytest.mark.parametrize("wert", ["diakronos", "primo", "admin", "api", "login", "standard", "_"])
def test_reservierte_slugs(wert):
    with pytest.raises(regeln.SlugUngueltig):
        regeln.slug_pruefen(wert)


def test_slug_pruefen_normalisiert_nur_rand():
    assert regeln.slug_pruefen("  gemeinde  ") == "gemeinde"
    with pytest.raises(regeln.SlugUngueltig):
        regeln.slug_pruefen("Gemeinde")


def test_darf_website_nutzt_dieselbe_rollenliste_wie_web1b():
    from diakronos_app.website import primo

    for rollen in (["System Manager"], ["Administrator"], ["Website-Moderator"]):
        assert regeln.darf_website(rollen) is True
    assert regeln.darf_website(["Mitglied"]) is False
    assert regeln.darf_website([]) is False
    assert set(primo.WEBSITE_ROLLEN) == {"System Manager", "Administrator", "Website-Moderator"}
