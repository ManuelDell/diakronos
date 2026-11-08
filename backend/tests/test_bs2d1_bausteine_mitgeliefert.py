"""BS-2d1 — Backend: mitgelieferte Bausteine und ihre Freigaben.

Was die Karte verspricht (und dieser Test festhält)
===================================================

1. ``website.bausteine_status`` liefert in ``mitgeliefert`` ALLE mitgelieferten
   Bausteine mit ``kennung``, ``name``, ``beschreibung`` und ``freigaben`` —
   auch dann, wenn in Primo noch nichts davon liegt (das ist der Normalfall
   vor dem ersten Einspielen, und genau deshalb war der Bereich „Bausteine"
   bisher leer).
2. Die Freigaben stehen in ``deploy/primo/bausteine/<kennung>/block.json``
   (Quelle) und kommen über ``bausteine_lesen`` mit. Sie sind aus der
   TATSÄCHLICH genutzten BS-1b-API abgeleitet — dieser Test prüft die
   Zuordnung gegen die Endpunkte im ``component.svelte``, nicht gegen eine
   zweite Liste neben der Quelle.
3. Ein unbrauchbarer Quellenstand ist KEIN 500: ``mitgeliefert`` ist leer und
   ``hinweis`` sagt warum.
4. Die Rechte sind unverändert: der Status-Endpunkt läuft weiter durch
   ``_require_website_rolle`` (System Manager / Administrator /
   Website-Moderator; alles andere 403, Gast 401/403).

Netz (Kartenregel 11): keine Netzverbindung; die DB ist die In-Memory-SQLite
aus ``conftest.py``, Primo wird nie angesprochen (der Export scheitert
kontrolliert, damit der Zustand „nicht erreichbar" gilt).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.website import bausteine as bibliothek

#: Wurzel des Image-Testlaufs (``/app``): ``<Datei>`` → ``tests`` → ``/app``.
#: Im Repo ist das dieselbe Ebene wie ``backend/`` (``backend/tests/x.py`` →
#: ``backend`` → Repo). ``deploy/`` steht in ``.dockerignore``: die Tests, die
#: ``block.json`` bzw. ``component.svelte`` aus dem Repo lesen, prüfen die
#: AUSLIEFERUNG und werden im Image übersprungen; die Laufzeitkopie im Paket
#: prüft ``test_bausteine_lesen_liefert_die_freigaben_mit`` immer.
# Repo-Wurzel: tests/ liegt in backend/ — die Quellen liegen eine Ebene höher
# (Review 08.11.: parents[1] zeigte auf backend/ und übersprang die Tests still).
REPO = next((p for p in Path(__file__).resolve().parents[1:3]
             if (p / "deploy" / "primo" / "bausteine").is_dir()),
            Path(__file__).resolve().parents[1])
QUELLE_REPO = REPO / "deploy" / "primo" / "bausteine"

nur_im_repo = pytest.mark.skipif(
    not QUELLE_REPO.is_dir(),
    reason="deploy/primo/bausteine liegt nicht im Build-Kontext (Image)",
)

MODUL = "diakronos_app.api.website"
PFAD_STATUS = f"{MODUL}.bausteine_status"

#: Die neun mitgelieferten Bausteine (BS-2c-Stand) — Reihenfolge = ``index``.
BAUSTEINE = (
    "kontakt",
    "termine-liste",
    "kalender",
    "naechster-gottesdienst",
    "kalender-abo",
    "gruppen",
    "gruppe-steckbrief",
    "neuigkeiten",
    "anmeldung",
    "ansprechpartner",
)

#: Die Zuordnung, die die Karte verlangt: welche Freigabe-Gruppen ein Baustein
#: liest. Sie ist aus dem ``component.svelte`` abgeleitet (siehe
#: ``test_freigaben_passen_zur_benutzten_api``) und steht in ``block.json``.
ERWARTETE_FREIGABEN = {
    "kontakt": ["kontaktpostfaecher"],
    "termine-liste": ["termine"],
    "kalender": ["termine"],
    "naechster-gottesdienst": ["termine"],
    "kalender-abo": ["kalender"],
    "gruppen": ["gruppen"],
    "gruppe-steckbrief": ["gruppen", "termine"],
    "neuigkeiten": ["beitraege"],
    "anmeldung": ["termine"],
    # BS-3a: eigene Auswahl + Einwilligung, keine Freigabegruppe.
    "ansprechpartner": [],
}

#: Endpunkt im Baustein -> Freigabe-Gruppen, die er öffentlich macht.
ENDPUNKT_ZU_FREIGABE = {
    "/website/oeffentlich/termine": {"termine"},
    "/website/oeffentlich/naechster_termin": {"termine"},
    "/website/oeffentlich/kalender": {"kalender"},
    "/website/oeffentlich/gruppen": {"gruppen"},
    # Der Detailendpunkt liefert die Gruppe SAMT ``naechste_termine``
    # (``oeffentlich_daten.gruppe_detail``) — also Gruppen- UND Termindaten.
    "/website/oeffentlich/gruppe": {"gruppen", "termine"},
    "/website/oeffentlich/beitraege": {"beitraege"},
    "/website/oeffentlich/postfaecher": {"kontaktpostfaecher"},
    "/website/oeffentlich/ansprechpartner": set(),
}


# ── Benutzer/Rollen ────────────────────────────────────────────────────────

ADMIN_MAIL = "verwaltung@example.org"
SYSTEMMANAGER_MAIL = "system@example.org"
MODERATOR_MAIL = "moderator@example.org"
MITGLIED_MAIL = "mitglied@example.org"
KALENDER_ADMIN_MAIL = "kalenderadmin@example.org"


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
def welt(patched_db, fake_redis):
    """Bestand: fünf Benutzer mit den Rollen der Website-Verwaltung."""
    sess = patched_db()
    _benutzer_anlegen(sess, ADMIN_MAIL, ("Administrator",))
    _benutzer_anlegen(sess, SYSTEMMANAGER_MAIL, ("System Manager",))
    _benutzer_anlegen(sess, MODERATOR_MAIL, ("Website-Moderator",))
    _benutzer_anlegen(sess, MITGLIED_MAIL, ("Mitglied",))
    _benutzer_anlegen(sess, KALENDER_ADMIN_MAIL, ("Kalenderadministrator",))
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt):
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


@pytest.fixture()
def primo_nicht_erreichbar(monkeypatch):
    """Primo antwortet nicht — der Stand ist „erreichbar: false", ohne 500.

    Der Zustand ist für diese Karte der interessante: die ``mitgeliefert``
    Liste MUSS trotzdem vollständig sein (sonst wäre der Bereich vor dem
    ersten Einspielen leer — genau der Befund aus BS-2d).
    """
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "primo_url", "http://primo.test:8080", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", "su@example.org", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password", "x", raising=False)

    class Kaputt:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            raise AssertionError("Der Test darf Primo nicht ansprechen.")

        def post(self, *a, **k):
            raise AssertionError("Der Test darf Primo nicht ansprechen.")

    monkeypatch.setattr(bibliothek, "_client", Kaputt)


# ── 1. Freigaben in den Quellen ────────────────────────────────────────────


@nur_im_repo
def test_alle_neun_bausteine_nennen_freigaben():
    """``block.json`` JEDES Bausteins trägt ``freigaben`` (auch leer = bewusst)."""
    for kennung in BAUSTEINE:
        datei = QUELLE_REPO / kennung / "block.json"
        daten = json.loads(datei.read_text(encoding="utf-8"))
        assert "freigaben" in daten, f"{kennung}: freigaben fehlt in block.json"
        assert isinstance(daten["freigaben"], list), kennung
        assert daten["freigaben"] == ERWARTETE_FREIGABEN[kennung], kennung


def test_bausteine_lesen_liefert_die_freigaben_mit():
    """``bausteine_lesen`` liefert Kennung, Name, Beschreibung UND Freigaben."""
    liste = bibliothek.bausteine_lesen()
    assert [b.kennung for b in liste] == list(BAUSTEINE)
    for baustein in liste:
        assert baustein.freigaben == tuple(ERWARTETE_FREIGABEN[baustein.kennung])
        als_dict = baustein.als_dict()
        assert als_dict["kennung"] == baustein.kennung
        assert als_dict["name"].startswith("Diakronos:")
        assert als_dict["beschreibung"].strip()
        assert als_dict["freigaben"] == list(ERWARTETE_FREIGABEN[baustein.kennung])


@nur_im_repo
def test_freigaben_passen_zur_benutzten_api():
    """Die Zuordnung ist aus dem Baustein abgeleitet, nicht daneben erfunden.

    Gelesen wird jeder ``/website/oeffentlich/<name>``-Aufruf im
    ``component.svelte``; seine Freigabe-Gruppe MUSS in ``block.json`` stehen,
    und ``block.json`` darf keine Freigabe nennen, die der Code nicht nutzt.

    Ausnahme ``gruppe``: der Detailendpunkt liefert die Gruppe **samt
    ``naechste_termine``** (``oeffentlich_daten.gruppe_detail``) — er ist also
    auch eine Termin-Ausgabe. Ein Steckbrief, der diese Liste anzeigt, braucht
    deshalb ``termine`` UND ``gruppen`` (steht in ``ENDPUNKT_ZU_FREIGABE``).
    """
    for kennung in BAUSTEINE:
        quelle = (QUELLE_REPO / kennung / "component.svelte").read_text(encoding="utf-8")
        genutzt: set[str] = set()
        for pfad in re.findall(r"/website/oeffentlich/[a-z0-9_]+", quelle):
            genutzt |= ENDPUNKT_ZU_FREIGABE[pfad]
        # Das Kontaktformular schreibt über den Methoden-Router — eigener Pfad.
        if "/api/method/website.kontakt_senden" in quelle:
            genutzt.add("kontaktpostfaecher")
        genannt = set(ERWARTETE_FREIGABEN[kennung])
        assert genutzt <= genannt, (
            f"{kennung}: Baustein nutzt {sorted(genutzt - genannt)}, "
            "block.json nennt sie nicht"
        )
        assert genannt <= genutzt, (
            f"{kennung}: block.json nennt {sorted(genannt - genutzt)}, "
            "der Baustein nutzt diese Freigabe nicht"
        )


def test_freigaben_sind_eine_positivliste():
    """Unbekannte Namen, Doppelungen und ein fehlender Schlüssel brechen."""
    gueltig = {"freigaben": ["termine"]}
    assert bibliothek.freigaben_lesen(gueltig, "probe") == ("termine",)
    assert bibliothek.freigaben_lesen({"freigaben": []}, "probe") == ()

    for kaputt in (
        {},                                   # Schlüssel fehlt
        {"freigaben": "termine"},             # keine Liste
        {"freigaben": ["termine", "termine"]},  # doppelt
        {"freigaben": ["termien"]},           # Tippfehler -> nicht still
        {"freigaben": ["mitglieder"]},        # nie öffentlich (G1)
    ):
        with pytest.raises(bibliothek.BausteinQuelleFehler):
            bibliothek.freigaben_lesen(kaputt, "probe")


@nur_im_repo
def test_version_ist_elf():
    """BS-2d1 erhöht die Auslieferung: main stand auf 9."""
    assert bibliothek.mitgelieferte_version() == 11
    assert (QUELLE_REPO / "VERSION").read_text(encoding="utf-8").strip() == "11"


# ── 2. Der Status-Endpunkt liefert „mitgeliefert“ ──────────────────────────


def test_mitgeliefert_ist_vor_dem_einspielen_vollstaendig(primo_nicht_erreichbar):
    """Der Kern des Befunds: die Liste hängt NICHT an Primo."""
    stand = bibliothek.bibliothek_stand()
    assert stand.erreichbar is False
    daten = stand.als_dict()
    assert [e["kennung"] for e in daten["mitgeliefert"]] == list(BAUSTEINE)
    for eintrag in daten["mitgeliefert"]:
        assert eintrag["name"].startswith("Diakronos:")
        assert eintrag["beschreibung"].strip()
        assert eintrag["freigaben"] == ERWARTETE_FREIGABEN[eintrag["kennung"]]
    # Was in Primo liegt, ist eine andere Liste und hier leer.
    assert daten["bausteine"] == []
    assert daten["installiert_version"] == 0


def test_status_endpunkt_hat_das_feld_mitgeliefert(als_benutzer, primo_nicht_erreichbar):
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert len(daten["mitgeliefert"]) == 10
    kennungen = [e["kennung"] for e in daten["mitgeliefert"]]
    assert kennungen == list(BAUSTEINE)
    assert daten["mitgeliefert_version"] == 11
    # Je Eintrag genau die Felder der Karte — keine Personendaten, keine
    # internen Kennungen (G1).
    assert set(daten["mitgeliefert"][0]) == {
        "kennung",
        "name",
        "beschreibung",
        "freigaben",
        "sha256",
        "felder",
    }


# ── 3. Fehlerfall: unbrauchbare Quellen sind kein 500 ──────────────────────


def test_unbrauchbare_quellen_ergeben_leere_liste_und_hinweis(monkeypatch):
    def platzt():
        raise bibliothek.BausteinQuelleFehler("Quellen kaputt")

    monkeypatch.setattr(bibliothek, "bausteine_lesen", platzt)
    daten = bibliothek.Stand(mitgeliefert=0, hinweis="").als_dict()
    assert daten["mitgeliefert"] == []
    # ``als_dict`` selbst erfindet keinen Hinweis — der kommt aus dem Stand.
    assert daten["hinweis"] == ""


def test_unbrauchbare_quellen_setzen_den_hinweis(monkeypatch):
    """``bibliothek_stand`` meldet den Quellenfehler im Klartext, ohne 500."""
    def platzt():
        raise bibliothek.BausteinQuelleFehler("Quellen kaputt")

    monkeypatch.setattr(bibliothek, "bausteine_lesen", platzt)
    stand = bibliothek.bibliothek_stand()
    assert stand.als_dict()["mitgeliefert"] == []
    assert stand.hinweis == "Die mitgelieferten Bausteine sind unvollständig."


def test_status_endpunkt_bleibt_bei_quellenfehler_200(
    als_benutzer, primo_nicht_erreichbar, monkeypatch
):
    def platzt():
        raise bibliothek.BausteinQuelleFehler("Quellen kaputt")

    monkeypatch.setattr(bibliothek, "bausteine_lesen", platzt)
    c = als_benutzer(SYSTEMMANAGER_MAIL)
    antwort = c.get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["mitgeliefert"] == []
    assert daten["hinweis"] == "Die mitgelieferten Bausteine sind unvollständig."


# ── 4. Rechte unverändert (``_require_website_rolle``) ─────────────────────


@pytest.mark.parametrize("benutzer", [ADMIN_MAIL, SYSTEMMANAGER_MAIL, MODERATOR_MAIL])
def test_berechtigte_rollen_duerfen_den_stand_lesen(
    als_benutzer, benutzer, primo_nicht_erreichbar
):
    antwort = als_benutzer(benutzer).get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text


@pytest.mark.parametrize("benutzer", [MITGLIED_MAIL, KALENDER_ADMIN_MAIL])
def test_andere_rollen_bekommen_403(als_benutzer, benutzer, primo_nicht_erreichbar):
    antwort = als_benutzer(benutzer).get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"


def test_gast_bekommt_401_oder_403(gast, primo_nicht_erreichbar):
    assert gast.get(f"/api/method/{PFAD_STATUS}").status_code in (401, 403)


def test_status_bleibt_lesend():
    """Der Status-Endpunkt schreibt nichts — keine Methodenauswahl, kein Gast."""
    from diakronos_app.frappe_compat.registry import options_for

    optionen = options_for(diakronos_app.api.website.bausteine_status) or {}
    assert optionen.get("allow_guest") is False
    assert optionen.get("methods") in (None, ["GET"], "GET")

