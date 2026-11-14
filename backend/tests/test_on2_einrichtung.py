"""ON-2 — Einrichtungs-Daten (Logo, Kontakt) + Status-API.

Was diese Karte liefert und was hier geprueft wird:

* ``gemeinde.gemeinde_logo_hochladen`` / ``gemeinde.gemeinde_logo_entfernen``
  (nur Admin-Rollen) und die OEFFENTLICHE Auslieferung
  ``GET /gemeinde/logo`` (mit und ohne Praefix).
* Die neuen Kontaktfelder an ``gemeinde_speichern`` / ``gemeinde_get_einstellungen``
  (``kurzname``, ``strasse``, ``plz``, ``ort``, ``telefon``, ``website``) samt
  Anzeige der Zeitzone (nur lesen, Konfigurationswert).
* ``einrichtung.status`` — 7 Punkte, aus ECHTEN Daten berechnet.
* ``einrichtung.schritt_setzen``, ``einrichtung.abschliessen``,
  ``einrichtung.erinnern_spaeter``.
* ``einrichtung.kalender_vorschlag_anlegen`` (nutzt ``create_kalender``).

Rollen: Admin-Rollen sehen alles, jede andere angemeldete Person bekommt 403.
Datenbank: ausschliesslich ``patched_db`` (SQLite) — kein Betrieb.
"""
from __future__ import annotations

import io
import struct
import zlib

import datetime as _dtmod

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user

GEMEINDE = "gemeinde."
EINRICHTUNG = "einrichtung."
ADMIN = "mitgliederadmin@example.org"
NUR_MITGLIED = "berta@example.org"


# ── Hilfsmittel ─────────────────────────────────────────────────────────────


def _png(breite: int = 4, hoehe: int = 4) -> bytes:
    """Ein echtes, minimales PNG (ohne Pillow — nur Standardbibliothek)."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (
            struct.pack("!I", len(daten))
            + typ
            + daten
            + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF)
        )

    ihdr = struct.pack("!IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)
    roh = b"".join(b"\x00" + b"\xff\x00\x00" * breite for _ in range(hoehe))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(roh))
        + chunk(b"IEND", b"")
    )


def _sitzung(patched_db):
    """Eine Arbeits-Sitzung auf der Test-Datenbank (``patched_db`` ist eine Factory)."""
    return patched_db()


# ── ZEIT-TESTS: „heute“ ist der Tag der Gemeinde, nicht die UTC des Containers ─


class _FesteUhr(_dtmod.datetime):
    """Ersatz fuer ``datetime.datetime`` in ``diakronos_app.zeit``.

    Gefroren wird nur ``now()`` (wie ``freezegun``). Die Klasse ERBT dabei von
    ``datetime.datetime``: ein Fremdobjekt an dieser Stelle bricht die
    uebrigen Schichten (SQLAlchemy fragt ``isinstance`` gegen
    ``datetime.datetime`` ab).
    """

    # Die Felder der Attrappe kommen aus ``datetime.__new__`` (es reicht die
    # Argumente auch an ``__init__`` weiter) — deshalb steht der gefrorene
    # Zeitpunkt NICHT in einer Instanzvariable, sondern in der Klasse.
    def __init__(self, *args, **kwargs):
        # Auf Instanzen wird nichts gefroren (``now()`` ist der Klassenweg).
        raise TypeError("_FesteUhr ist nur als Klassen-Ersatz gedacht")

    @classmethod
    def now(cls, tz=None):
        return cls.fest if tz is None else cls.fest.astimezone(tz)


def _friere_zeit(monkeypatch, iso_utc: str) -> None:
    """Friert die Gemeinde-Uhr auf den Zeitpunkt ``iso_utc`` ein.

    Die Ersatzklasse erbt von ``datetime.datetime``: die uebrigen Schichten
    (SQLAlchemy, ``dateutil``) fragen ``datetime.datetime`` direkt ab — ein
    Fremdobjekt an dieser Stelle bricht sie mit „isinstance() arg 2 must be a
    type“. Das Frieren gilt nur in ``diakronos_app.zeit``.
    """
    from datetime import datetime, timezone

    from diakronos_app import zeit

    fest = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    monkeypatch.setattr(zeit._dt, "datetime", type("FesteUhr", (_FesteUhr,), {"fest": fest}))


def _nutzer(sess, name: str, rollen: tuple[str, ...] = ()) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=True))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


@pytest.fixture()
def admin_umgebung(client, patched_db):
    """Echter Admin (``System Manager`` — R-11a: die Mitgliederverwaltung ist
    kein Admin mehr) + ein Nur-Mitglied."""
    sess = _sitzung(patched_db)
    # Kalenderadministrator: der Kalender-Vorschlag laeuft ueber
    # ``create_kalender``, dessen Rechtepruefung diese Rolle verlangt.
    _nutzer(sess, ADMIN, ("System Manager", "Kalenderadministrator"))
    _nutzer(sess, NUR_MITGLIED)
    sess.commit()

    set_user(ADMIN)
    try:
        yield client
    finally:
        set_user("Administrator")


@pytest.fixture()
def mitglied_client(client, patched_db):
    """Angemeldet, aber ohne Admin-Rolle."""
    sess = _sitzung(patched_db)
    _nutzer(sess, NUR_MITGLIED)
    sess.commit()
    sess.close()

    set_user(NUR_MITGLIED)
    try:
        yield client
    finally:
        set_user("Administrator")


def _post(client, pfad: str, **daten):
    return client.post(f"/api/method/{pfad}", json=daten)


def _status(client) -> dict:
    r = _post(client, EINRICHTUNG + "status")
    assert r.status_code == 200, r.text
    return r.json()["message"]


def _punkte(client) -> dict:
    return {p["schluessel"]: p for p in _status(client)["punkte"]}


def _logo_pfad(url: str) -> str:
    """Der Pfadteil einer Logo-Adresse — ``?v=…`` (F8) bleibt aussen vor."""
    from urllib.parse import urlparse

    return urlparse(url).path


def gemeinde_einstellungen(client) -> dict:
    r = client.post(f"/api/method/{GEMEINDE}gemeinde_get_einstellungen")
    assert r.status_code == 200, r.text
    return r.json()["message"]


# ── D1: Kontaktfelder ───────────────────────────────────────────────────────


def test_kontaktfelder_speichern_und_wiederlesen(admin_umgebung):
    r = _post(
        admin_umgebung,
        GEMEINDE + "gemeinde_speichern",
        gemeindename="Versöhnungskirche Heilbronn",
        kurzname="Versöhnungskirche",
        strasse="Kirchplatz 1",
        plz="74072",
        ort="Heilbronn",
        telefon="+49 7131 123456",
        website="https://gemeinde.example.org",
        kontakt_email="buero@example.org",
    )
    assert r.status_code == 200, r.text

    d = admin_umgebung.post(f"/api/method/{GEMEINDE}gemeinde_get_einstellungen").json()["message"]
    assert d["gemeindename"] == "Versöhnungskirche Heilbronn"
    assert d["kurzname"] == "Versöhnungskirche"
    assert d["strasse"] == "Kirchplatz 1"
    assert d["plz"] == "74072"
    assert d["ort"] == "Heilbronn"
    assert d["telefon"] == "+49 7131 123456"
    assert d["website"] == "https://gemeinde.example.org"


@pytest.mark.parametrize("daten,grund", [
    ({"kurzname": "X" * 41}, "Kurzname"),
    # 11 Ziffern: zu lang, bevor die Ziffernregel greift.
    ({"plz": "12345678901"}, "zu lang"),
    ({"plz": "abcde"}, "Postleitzahl"),
    ({"website": "gemeinde.example.org"}, "Website"),
    ({"website": "javascript:alert(1)"}, "Website"),
    ({"strasse": "X" * 121}, "zu lang"),
    ({"telefon": "1" * 41}, "zu lang"),
    ({"ort": "X" * 121}, "zu lang"),
])
def test_kontaktfelder_pruefen_eingaben(admin_umgebung, daten, grund):
    r = _post(admin_umgebung, GEMEINDE + "gemeinde_speichern",
              gemeindename="X", **daten)
    assert r.status_code == 417, r.text
    assert grund in r.text


def test_zeitzone_wird_nur_angezeigt(admin_umgebung):
    d = admin_umgebung.post(f"/api/method/{GEMEINDE}gemeinde_get_einstellungen").json()["message"]
    from diakronos_app.settings import settings

    assert d["zeitzone"] == settings.calendar_timezone
    # Nur Anzeige: kein Schreibweg. Ein mitgeschickter Wert wird ignoriert.
    r = _post(admin_umgebung, GEMEINDE + "gemeinde_speichern",
              gemeindename="X", zeitzone="America/New_York")
    assert r.status_code == 200, r.text
    d = admin_umgebung.post(f"/api/method/{GEMEINDE}gemeinde_get_einstellungen").json()["message"]
    assert d["zeitzone"] == settings.calendar_timezone


# ── D1: Logo ────────────────────────────────────────────────────────────────


def test_logo_hochladen_ausliefern_entfernen(admin_umgebung):
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["message"]
    assert d["logo_vorhanden"] is True
    assert _logo_pfad(d["logo_url"]).endswith("/gemeinde/logo")

    # Auslieferung OEFFENTLICH (ohne Anmeldung lesbar).
    from diakronos_app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as oeffentlich:
        bild = oeffentlich.get("/gemeinde/logo")
    assert bild.status_code == 200, bild.text
    assert bild.headers["content-type"] == "image/png"
    # Kein Skript, kein Markup — auch wenn ein Browser den Typ ignoriert.
    assert "sandbox" in bild.headers["content-security-policy"]
    assert bild.headers["x-content-type-options"] == "nosniff"
    assert bild.content.startswith(b"\x89PNG")

    # Entfernen: danach 404 (Frontend zeigt das Monogramm).
    r = _post(admin_umgebung, GEMEINDE + "gemeinde_logo_entfernen")
    assert r.status_code == 200, r.text
    assert r.json()["message"]["logo_vorhanden"] is False
    with TestClient(app) as oeffentlich:
        assert oeffentlich.get("/gemeinde/logo").status_code == 404


def test_logo_route_ohne_logo_ist_404(guest_client):
    r = guest_client.get("/gemeinde/logo")
    assert r.status_code == 404
    assert "Kein Logo" in r.text


def test_logo_route_mit_praefix(admin_umgebung):
    """WEB-5a: unter DIAKRONOS_BASE_PATH liegt die Route darunter — nicht davor."""
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings

    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert r.status_code == 200, r.text

    alt = base_path.aktiver_praefix()
    try:
        app = erstelle_app(settings.model_copy(update={"diakronos_base_path": "/diakronos"}))
        with TestClient(app) as c:
            assert c.get("/gemeinde/logo").status_code == 404
            r = c.get("/diakronos/gemeinde/logo")
            assert r.status_code == 200, r.text
            assert r.headers["content-type"] == "image/png"
    finally:
        base_path.setze_praefix(alt)


@pytest.mark.parametrize("name,inhalt,typ,grund", [
    # ON-2b: SVG ist ZUGELASSEN (Nachtrag Orchestrator 2026-11-01). Abgesichert
    # wird ueber die Auslieferung (CSP sandbox, nosniff, nur per <img>), nicht
    # durch Bereinigung. Siehe test_logo_svg_* weiter unten.
    ("logo.txt", b"kein bild", "text/plain", "nicht erlaubt"),
    # Abgeschnittene PNG: Magic-Bytes stimmen, der Inhalt ist kein Bild.
    ("logo.png", b"\x89PNG\r\n\x1a\n" + b"x" * 10, "image/png", "zu klein"),
    # SVG, das kein XML ist bzw. dessen Wurzel nicht <svg> heisst.
    ("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><rect>",
     "image/svg+xml", "kein zulaessiges XML"),
    ("logo.svg", b'<?xml version="1.0"?><html><body/></html>',
     "image/svg+xml", "<svg>-Wurzel-Tag"),
    # Nicht-SVG mit .svg-Endung: der Inhalt entscheidet, nicht der Name.
    ("logo.svg", _png(), "image/svg+xml", "passt nicht"),
])
def test_logo_lehnt_fremdtypen_ab(admin_umgebung, name, inhalt, typ, grund):
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": (name, io.BytesIO(inhalt), typ)},
    )
    assert r.status_code == 417, r.text
    assert grund in r.text
    # Und es bleibt nichts haengen.
    assert admin_umgebung.get("/gemeinde/logo").status_code == 404


_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<rect width="10" height="10" fill="#c00"/></svg>'
)


def test_logo_svg_wird_angenommen(admin_umgebung):
    """Nachtrag Orchestrator: SVG zulaessig — Auslieferung entschaerft es."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.svg", io.BytesIO(_SVG), "image/svg+xml")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["message"]
    assert d["logo_vorhanden"] is True
    assert _logo_pfad(d["logo_url"]).endswith("/gemeinde/logo")

    with TestClient(app) as oeffentlich:
        bild = oeffentlich.get("/gemeinde/logo")
    assert bild.status_code == 200, bild.text
    assert bild.headers["content-type"].startswith("image/svg+xml")
    assert bild.content == _SVG
    # Ein SVG ist ein BILD, kein Dokument: sandbox-CSP und nosniff gelten
    # fuer ALLE Typen — auch fuer SVG.
    csp = bild.headers["content-security-policy"]
    assert "sandbox" in csp
    assert "default-src 'none'" in csp
    assert "style-src 'unsafe-inline'" in csp
    assert bild.headers["x-content-type-options"] == "nosniff"
    assert "inline" in bild.headers["content-disposition"]

    # Das Status-/Einstellungsbild meldet das SVG wie jedes andere Logo.
    assert _punkte(admin_umgebung)["logo"]["erledigt"] is True
    assert gemeinde_einstellungen(admin_umgebung)["logo_vorhanden"] is True


@pytest.mark.parametrize("inhalt", [
    # Externe Entitaet (XXE): DTD ist der Weg dorthin — defusedxml verweigert.
    b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
    b'<svg xmlns="http://www.w3.org/2000/svg">&xxe;</svg>',
    # Auch eine harmlose DTD wird nicht verarbeitet (keine Dokumenttypen).
    b'<?xml version="1.0"?><!DOCTYPE svg SYSTEM "http://example.org/x.dtd">'
    b'<svg xmlns="http://www.w3.org/2000/svg"/>',
])
def test_logo_svg_mit_doctype_wird_abgelehnt(admin_umgebung, inhalt):
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.svg", io.BytesIO(inhalt), "image/svg+xml")},
    )
    assert r.status_code == 417, r.text
    assert "Dokumenttyp" in r.text
    assert admin_umgebung.get("/gemeinde/logo").status_code == 404


def test_logo_abmessungen_werden_gedeckelt(admin_umgebung):
    """F5: > 4096 px Kante wird abgelehnt — aus den Kopfdaten, ohne Dekodieren."""
    from diakronos_app import gemeinde_logo

    assert gemeinde_logo.abmessungen(_png(7, 5), "image/png") == (7, 5)

    for breite, hoehe in ((4097, 4), (4, 4097)):
        r = admin_umgebung.post(
            f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
            files={"file": ("logo.png", io.BytesIO(_png(breite, hoehe)), "image/png")},
        )
        assert r.status_code == 417, r.text
        assert "zu gross" in r.text
        assert "4096" in r.text

    # Genau an der Grenze ist erlaubt.
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png(4096, 4)), "image/png")},
    )
    assert r.status_code == 200, r.text


def test_logo_zu_gross_wird_abgelehnt(admin_umgebung, monkeypatch):
    from diakronos_app import gemeinde_logo

    monkeypatch.setattr(gemeinde_logo, "LOGO_MAX_BYTES", 64)
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png(30, 30)), "image/png")},
    )
    assert r.status_code == 417, r.text
    assert "zu gross" in r.text


def test_logo_mit_falschem_client_typ_wird_abgelehnt(admin_umgebung):
    """Eine als text/plain deklarierte PNG-Datei wird nicht durchgelassen.

    Der Typ wird an den Magic-Bytes erkannt; ein abweichender Client-Typ ist
    kein „harmloser“ Fall, sondern ein Zeichen fuer einen falschen Upload.
    """
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.txt", io.BytesIO(_png()), "text/plain")},
    )
    assert r.status_code == 417, r.text
    assert "passt nicht" in r.text


# ── Rollen ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pfad,daten", [
    (GEMEINDE + "gemeinde_logo_entfernen", {}),
    (EINRICHTUNG + "status", {}),
    (EINRICHTUNG + "schritt_setzen", {"schluessel": "gemeinde", "zustand": "erledigt"}),
    (EINRICHTUNG + "abschliessen", {}),
    (EINRICHTUNG + "erinnern_spaeter", {"tage": 7}),
    (EINRICHTUNG + "kalender_vorschlag_anlegen", {"namen": ["Gottesdienste"]}),
])
def test_nicht_admin_bekommt_403(mitglied_client, pfad, daten):
    r = _post(mitglied_client, pfad, **daten)
    assert r.status_code == 403, r.text


def test_nicht_admin_darf_kein_logo_hochladen(mitglied_client):
    r = mitglied_client.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert r.status_code == 403, r.text


def test_gast_bekommt_401(guest_client):
    r = guest_client.post(f"/api/method/{EINRICHTUNG}status", json={})
    assert r.status_code == 401, r.text


# ── D2: Status-API ──────────────────────────────────────────────────────────


def test_status_leere_datenbank_alle_punkte_offen(admin_umgebung):
    d = _status(admin_umgebung)
    schluessel = [p["schluessel"] for p in d["punkte"]]
    assert schluessel == [
        "gemeindename", "logo", "kontakt", "mailversand",
        "module", "mitglieder", "kalender",
    ]
    assert d["gesamt_anzahl"] == 7
    assert d["offen_anzahl"] == 7
    assert d["assistent_abgeschlossen"] is False
    assert [s["schluessel"] for s in d["schritte"]] == [
        "gemeinde", "kontakt", "mailversand", "module", "mitglieder_kalender",
    ]
    assert {s["zustand"] for s in d["schritte"]} == {"offen"}
    assert all(p["erledigt"] is False for p in d["punkte"])
    for p in d["punkte"]:
        assert p["titel"] and p["hinweis"]
        assert p["ziel"].startswith("#/")


def test_status_punkte_aus_echten_daten(admin_umgebung, patched_db):
    from diakronos_app.models.diakonos import Mitglied

    _post(admin_umgebung, GEMEINDE + "gemeinde_speichern",
          gemeindename="Versöhnungskirche",
          kurzname="VK",
          strasse="Kirchplatz 1", plz="74072", ort="Heilbronn",
          kontakt_email="buero@example.org")
    _post(admin_umgebung, GEMEINDE + "gemeinde_setze_modul",
          schluessel="kronos", sichtbar=True)

    sess = _sitzung(patched_db)
    sess.add(Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                      email="anna@example.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    from diakronos_app.api.kronos.kalender_verwaltung import create_kalender
    set_user(ADMIN)
    try:
        create_kalender("Gottesdienste")
    finally:
        set_user(ADMIN)

    p = _punkte(admin_umgebung)
    assert p["gemeindename"]["erledigt"] is True
    assert p["kontakt"]["erledigt"] is True
    # F2: „Module“ haengt NICHT an ``*_sichtbar`` — nur am Assistenten-Schritt.
    assert p["module"]["erledigt"] is False
    assert p["mitglieder"]["erledigt"] is True
    assert p["kalender"]["erledigt"] is True
    assert p["logo"]["erledigt"] is False
    assert p["mailversand"]["erledigt"] is False

    d = _status(admin_umgebung)
    assert d["offen_anzahl"] == 3
    assert d["gesamt_anzahl"] == 7


# ── F2: „Module“ = Entscheidung im Assistenten, nicht „etwas sichtbar“ ──────


def test_module_punkt_folgt_dem_schritt_nicht_der_sichtbarkeit(admin_umgebung):
    """F2 (Orchestrator): ``schritt_module == "erledigt"`` ODER abgeschlossen.

    Eine Gemeinde, die bewusst ALLE Module abschaltet, hat den Punkt trotzdem
    erledigt — der Vorgang zaehlt, nicht die Zahl der sichtbaren Module.
    """
    assert _punkte(admin_umgebung)["module"]["erledigt"] is False

    # Alle Module AUS lassen: der Punkt bleibt offen, solange nichts entschieden ist.
    for prefix in ("diakronos", "kronos", "diakonos", "psalmos", "seelsorge"):
        _post(admin_umgebung, GEMEINDE + "gemeinde_setze_modul",
              schluessel=prefix, sichtbar=False)
    assert _punkte(admin_umgebung)["module"]["erledigt"] is False

    # Schritt „Module“ erledigt -> Punkt erledigt, auch ohne sichtbares Modul.
    r = _post(admin_umgebung, EINRICHTUNG + "schritt_setzen",
              schluessel="module", zustand="erledigt")
    assert r.status_code == 200, r.text
    p = _punkte(admin_umgebung)["module"]
    assert p["erledigt"] is True
    assert p["titel"] == "Module festgelegt"
    assert p["hinweis"] == "Module sind festgelegt."


def test_module_punkt_uebersprungen_zaehlt_nicht(admin_umgebung):
    """``uebersprungen`` heisst „Entscheidung offen“ — Punkt bleibt offen."""
    _post(admin_umgebung, EINRICHTUNG + "schritt_setzen",
          schluessel="module", zustand="uebersprungen")
    assert _punkte(admin_umgebung)["module"]["erledigt"] is False


def test_module_punkt_erledigt_wenn_assistent_abgeschlossen(admin_umgebung):
    """Zweiter Weg (F2): der abgeschlossene Assistent schliesst den Punkt mit ein."""
    _post(admin_umgebung, EINRICHTUNG + "abschliessen")
    assert _punkte(admin_umgebung)["module"]["erledigt"] is True


def test_kontakt_punkt_akzeptiert_email_oder_anschrift(admin_umgebung):
    # Nur Anschrift (ohne E-Mail) genuegt.
    _post(admin_umgebung, GEMEINDE + "gemeinde_speichern",
          gemeindename="X", strasse="Kirchplatz 1", plz="74072", ort="Heilbronn")
    assert _punkte(admin_umgebung)["kontakt"]["erledigt"] is True


def test_mitgliederpunkt_offen_wenn_nur_der_erst_admin_existiert(client, patched_db):
    """Frische Installation (``erstinstallation.py``) -> Punkt „Mitglieder“ offen.

    Der Erst-Administrator wird als MITGLIED gefuehrt und ist zugleich Inhaber
    einer Admin-Rolle an seinem Konto. Genau dieser eine Datensatz darf den
    Punkt NICHT erledigen (Kartenvorgabe D2).
    """
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(User(name="admin@example.org", email="admin@example.org",
                  full_name="Admin", enabled=True))
    sess.add(HasRole(name="admin@example.org-System Manager",
                     parent="admin@example.org", parenttype="User",
                     parentfield="roles", idx=1, role="System Manager"))
    sess.add(Mitglied(name="M-0001", vorname="Administrator", nachname="System",
                      email="admin@example.org", user="admin@example.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    sess.close()

    assert _punkte(client)["mitglieder"]["erledigt"] is False


def test_mitgliederpunkt_erledigt_bei_einer_echten_person(client, patched_db):
    """Gegenprobe: eine Person ohne Admin-Konto erledigt den Punkt."""
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(Mitglied(name="M-0002", vorname="Anna", nachname="Beispiel",
                      email="anna@example.org", status="Mitglied",
                      docstatus=0, idx=0))
    sess.commit()
    sess.close()

    assert _punkte(client)["mitglieder"]["erledigt"] is True


def test_mitgliederpunkt_zaehlt_nur_nicht_ausgetretene(admin_umgebung, patched_db):
    from diakronos_app.models.diakonos import Mitglied

    sess = _sitzung(patched_db)
    sess.add(Mitglied(name="M-0009", vorname="Clara", nachname="Clausen",
                      email="clara@example.org", status="Ausgetreten",
                      docstatus=0, idx=0))
    sess.commit()
    assert _punkte(admin_umgebung)["mitglieder"]["erledigt"] is False


def test_logo_punkt_wird_aus_datei_berechnet(admin_umgebung):
    admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert _punkte(admin_umgebung)["logo"]["erledigt"] is True
    _post(admin_umgebung, GEMEINDE + "gemeinde_logo_entfernen")
    assert _punkte(admin_umgebung)["logo"]["erledigt"] is False


def test_mailversand_punkt_folgt_smtp_eingerichtet(admin_umgebung):
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    assert _punkte(admin_umgebung)["mailversand"]["erledigt"] is False

    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        s.add(SmtpEinstellungen(
            name=SMTP_EINSTELLUNGEN_NAME,
            host="mail.example.org",
            port=587,
            sicherheit="starttls",
            benutzername="u",
            absender="noreply@example.org",
            absender_name="Gemeinde",
            timeout=30,
            eingerichtet=True,
        ))
        s.commit()

    assert _punkte(admin_umgebung)["mailversand"]["erledigt"] is True


# ── D3: Assistent ───────────────────────────────────────────────────────────


def test_schritt_setzen_und_abschliessen(admin_umgebung):
    r = _post(admin_umgebung, EINRICHTUNG + "schritt_setzen",
              schluessel="mailversand", zustand="uebersprungen")
    assert r.status_code == 200, r.text
    d = _status(admin_umgebung)
    schritt = {s["schluessel"]: s for s in d["schritte"]}["mailversand"]
    assert schritt["zustand"] == "uebersprungen"
    # Der Punkt selbst bleibt OFFEN — uebersprungen ist kein Datenstand.
    assert {p["schluessel"]: p for p in d["punkte"]}["mailversand"]["erledigt"] is False

    r = _post(admin_umgebung, EINRICHTUNG + "abschliessen")
    assert r.status_code == 200, r.text
    assert _status(admin_umgebung)["assistent_abgeschlossen"] is True


def test_schritt_setzen_prueft_schluessel_und_zustand(admin_umgebung):
    r = _post(admin_umgebung, EINRICHTUNG + "schritt_setzen",
              schluessel="gibtsnicht", zustand="erledigt")
    assert r.status_code == 417, r.text
    r = _post(admin_umgebung, EINRICHTUNG + "schritt_setzen",
              schluessel="gemeinde", zustand="halbfertig")
    assert r.status_code == 417, r.text


def test_erinnern_spaeter_blendet_die_karte_aus(admin_umgebung, monkeypatch):
    """ZEIT-TESTS: „heute + 7“ rechnet im Gemeinde-Tag, nicht im UTC-Tag.

    Geprueft um 23:30 UTC — in Berlin (MEZ) ist das schon der Folgetag. Wer
    hier ``date.today()`` des Containers nimmt, erwartet den Vortag und wird
    genau zwischen 0 und 1 Uhr Ortszeit rot.
    """
    import datetime

    from diakronos_app.zeit import heute_gemeinde

    _friere_zeit(monkeypatch, "2026-11-11T23:30:00")

    r = _post(admin_umgebung, EINRICHTUNG + "erinnern_spaeter", tage=7)
    assert r.status_code == 200, r.text

    d = _status(admin_umgebung)
    erinnerung = d["erinnerung_ab"]
    assert erinnerung
    tag = datetime.date.fromisoformat(str(erinnerung)[:10])
    assert tag == heute_gemeinde() + datetime.timedelta(days=7)
    # Der Kalendertag der Gemeinde ist hier der 12.11. (nicht der UTC-Tag 11.11.).
    assert tag == datetime.date(2026, 11, 19)

    r = _post(admin_umgebung, EINRICHTUNG + "erinnern_spaeter", tage=0)
    assert r.status_code == 417, r.text


def test_erinnern_ist_zeitgeber_nicht_einstellung(admin_umgebung, monkeypatch):
    """Nach Ablauf der Frist erscheint die Karte wieder (Datum in der Vergangenheit)."""
    import datetime

    from diakronos_app.models.einrichtung import EinrichtungStand, EINRICHTUNG_STAND_NAME

    _friere_zeit(monkeypatch, "2026-11-11T23:30:00")
    from diakronos_app.zeit import heute_gemeinde

    set_user(ADMIN)
    try:
        from diakronos_app.db import SessionLocal

        with SessionLocal() as s:
            zeile = s.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
            if zeile is None:
                zeile = EinrichtungStand(name=EINRICHTUNG_STAND_NAME)
                s.add(zeile)
            zeile.erinnerung_ab = heute_gemeinde() - datetime.timedelta(days=1)
            s.commit()
    finally:
        set_user(ADMIN)

    assert _status(admin_umgebung)["erinnerung_ab"] is None


# ── D4: Kalender-Vorschlag ──────────────────────────────────────────────────


def test_kalender_vorschlag_legt_an_und_ueberspringt_duplikate(admin_umgebung):
    from diakronos_app.api.kronos.kalender_verwaltung import create_kalender

    create_kalender("Gottesdienste")

    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=["Gottesdienste", "Gemeindekalender"])
    assert r.status_code == 200, r.text
    d = r.json()["message"]
    assert d["angelegt"] == ["Gemeindekalender"]
    assert d["uebersprungen"] == ["Gottesdienste"]

    from diakronos_app.frappe_compat.query import get_all
    from diakronos_app.frappe_compat.session import set_user as _su

    _su(ADMIN)
    try:
        namen = {z["name"] for z in get_all("Kalender", fields=["name"])}
    finally:
        _su(ADMIN)
    assert {"Gottesdienste", "Gemeindekalender"} <= namen

    # Zweiter Lauf: nichts doppelt.
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=["Gottesdienste", "Gemeindekalender"])
    assert r.json()["message"]["angelegt"] == []
    assert set(r.json()["message"]["uebersprungen"]) == {"Gottesdienste", "Gemeindekalender"}


def test_kalender_vorschlag_prueft_eingaben(admin_umgebung):
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen", namen=[])
    assert r.status_code == 417, r.text
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=["X" * 141])
    assert r.status_code == 417, r.text


def test_kalender_vorschlag_hoechstens_zehn_namen(admin_umgebung):
    """F8: die Namensliste kommt vom Client — ein Aufruf legt hoechstens 10 an."""
    from diakronos_app.api.einrichtung import MAX_KALENDER_VORSCHLAEGE

    assert MAX_KALENDER_VORSCHLAEGE == 10
    zuviele = [f"Kalender {i}" for i in range(MAX_KALENDER_VORSCHLAEGE + 1)]
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=zuviele)
    assert r.status_code == 417, r.text
    assert "zu viele" in r.text
    # Nichts angelegt — die Pruefung greift VOR dem ersten Insert.
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.db import SessionLocal

    with SessionLocal() as s:
        assert s.query(Kalender.name).first() is None

    # Doppelte Namen zaehlen EINMAL: 10 doppelte Eintraege sind 5 Kalender.
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=[f"Kalender {i}" for i in range(5)] * 2)
    assert r.status_code == 200, r.text
    assert len(r.json()["message"]["angelegt"]) == 5


# ── F6: ``logo_vorhanden`` folgt der DATEI, nicht dem Eintrag ───────────────


def test_logo_vorhanden_folgt_der_datei(admin_umgebung):
    """F6: dasselbe wie im Status-Punkt — eine geloeschte Datei ist kein Logo."""
    from diakronos_app.gemeinde_logo import logo_pfad
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )
    from diakronos_app.db import SessionLocal

    assert gemeinde_einstellungen(admin_umgebung)["logo_vorhanden"] is False

    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert r.status_code == 200, r.text
    d = gemeinde_einstellungen(admin_umgebung)
    assert d["logo_vorhanden"] is True
    assert _logo_pfad(d["logo_url"]).endswith("/gemeinde/logo")

    # Datei von Hand entfernen (Eintrag bleibt!) -> kein Logo mehr.
    with SessionLocal() as s:
        zeile = s.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        name = zeile.logo_datei
    pfad, _typ = logo_pfad(name)
    pfad.unlink()

    d = gemeinde_einstellungen(admin_umgebung)
    assert d["logo_vorhanden"] is False
    assert d["logo_url"] == ""
    assert _punkte(admin_umgebung)["logo"]["erledigt"] is False


# ── F7: Logo-Adresse mit Cache-Busting ──────────────────────────────────────


def test_logo_url_hat_kurzhash(admin_umgebung):
    """F8: ``logo_url`` traegt ``?v=<kurzhash>`` — neues Logo, neue Adresse."""
    from urllib.parse import parse_qs, urlparse

    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png()), "image/png")},
    )
    assert r.status_code == 200, r.text
    erste = r.json()["message"]["logo_url"]
    ziel = urlparse(erste)
    assert ziel.path.endswith("/gemeinde/logo")
    v1 = parse_qs(ziel.query)["v"][0]
    assert len(v1) == 8 and all(c in "0123456789abcdef" for c in v1)

    # Ein zweites Logo (andere UUID) -> andere Adresse.
    r = admin_umgebung.post(
        f"/api/method/{GEMEINDE}gemeinde_logo_hochladen",
        files={"file": ("logo.png", io.BytesIO(_png(8, 8)), "image/png")},
    )
    zweite = r.json()["message"]["logo_url"]
    v2 = parse_qs(urlparse(zweite).query)["v"][0]
    assert v2 != v1

    # Ohne Logo keine Version.
    _post(admin_umgebung, GEMEINDE + "gemeinde_logo_entfernen")
    assert gemeinde_einstellungen(admin_umgebung)["logo_url"] == ""


# ── F4: SEC-11 — schreibende Endpunkte nur POST ─────────────────────────────


@pytest.mark.parametrize("pfad,daten", [
    (EINRICHTUNG + "schritt_setzen", {"schluessel": "gemeinde", "zustand": "erledigt"}),
    (EINRICHTUNG + "abschliessen", {}),
    (EINRICHTUNG + "erinnern_spaeter", {"tage": 7}),
    (EINRICHTUNG + "kalender_vorschlag_anlegen", {"namen": ["X"]}),
    (GEMEINDE + "gemeinde_logo_entfernen", {}),
])
def test_schreibende_endpunkte_nur_post(admin_umgebung, pfad, daten):
    """SEC-11 (F4): GET auf einen schreibenden Endpunkt darf nichts aendern."""
    r = admin_umgebung.get(f"/api/method/{pfad}", params=daten)
    assert r.status_code in (404, 405, 417), r.text
    # Und der Zustand ist unveraendert geblieben.
    d = _status(admin_umgebung)
    assert d["assistent_abgeschlossen"] is False
    assert d["erinnerung_ab"] is None
    assert {s["zustand"] for s in d["schritte"]} == {"offen"}



# ── ON-5 (E2-3): Kalender-Vorschlag darf Rechte nicht still verschlucken ────


def test_on5_kalender_vorschlag_durch_den_router_legt_beide_an(admin_umgebung):
    """Der Weg des Assistenten: ECHTER Router, Admin mit Kalenderrolle.

    Nachgestellt wird der Aufruf, den `useEinrichtungsAssistent.weiter()` macht:
    `POST /api/method/diakronos.diakonos.api.einrichtung.kalender_vorschlag_anlegen`
    mit ``namen=["Gottesdienste","Gemeindekalender"]`` (CSRF ueber den
    Test-Client, Rechte ueber die Rolle). Ergebnis: BEIDE Kalender stehen in
    der Tabelle — nicht nur „uebersprungen“ in der Antwort.
    """
    r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
              namen=["Gottesdienste", "Gemeindekalender"])
    assert r.status_code == 200, r.text
    d = r.json()["message"]
    assert d["angelegt"] == ["Gottesdienste", "Gemeindekalender"], d
    assert d["uebersprungen"] == [], d

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Kalender

    with SessionLocal() as s:
        namen = {n for (n,) in s.query(Kalender.name)}
    assert {"Gottesdienste", "Gemeindekalender"} <= namen, namen


def test_on5_kalender_vorschlag_ohne_kalenderrolle_meldet_sich(admin_umgebung, patched_db):
    """Der Befund selbst: Verwaltungsrolle ja, Kalenderrolle NEIN.

    Vorher antwortete der Endpunkt 200 mit ``uebersprungen: [beide]`` und legte
    NICHTS an — die Oberflaeche konnte das nicht bemerken. Jetzt kommt ein
    Rechtefehler, und es bleibt nichts Halbes zurueck. R-11a: die
    Mitgliederverwaltung ist kein Admin — sie kommt gar nicht in die
    Einrichtung (403 schon an der Tuer).
    """
    admin = "on5-admin@example.org"
    sess = _sitzung(patched_db)
    # Nur die Einrichtungs-Rolle, ausdruecklich KEIN Kalenderadministrator.
    _nutzer(sess, admin, ("Mitgliederadministrator",))
    sess.commit()
    sess.close()

    from diakronos_app.frappe_compat.session import set_user

    set_user(admin)
    try:
        r = _post(admin_umgebung, EINRICHTUNG + "kalender_vorschlag_anlegen",
                  namen=["Gottesdienste", "Gemeindekalender"])
    finally:
        set_user(ADMIN)

    assert r.status_code == 403, r.text

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Kalender

    with SessionLocal() as s:
        assert s.query(Kalender.name).first() is None, "es wurde trotzdem etwas angelegt"
