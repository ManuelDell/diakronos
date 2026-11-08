"""BS-1b — Oeffentliche Lese-API fuer Website-Bausteine + iCal-Feed.

Was die Karte verspricht (und dieser Test festhaelt)
====================================================

Grundsatz G1 (Freigabe-Prinzip): Nichts ist oeffentlich, solange es in
Diakronos nicht freigegeben ist (Default AUS), und hinaus geht nur eine
Feld-Positivliste — nie eine ganze Zeile. Dieser Test prueft beides in jeder
Richtung: Freigabe an/aus, Statusfilter, Kategorie-Einschraenkung, Grenzen
und EXPLIZIT NEGATIV, dass keine Antwort Personendaten traegt
(``mitarbeiter``, ``ablehnungs_grund``, ``autor``, E-Mail-Adressen).

Abgedeckt:

  (L1) ``website.oeffentlich.kalender``   -> ``[{slug, titel, farbe}]``
  (L2) ``website.oeffentlich.termine``    -> Termine im Zeitfenster
  (L3) ``website.oeffentlich.naechster_termin`` -> ein Termin oder ``null``
  (L4) ``website.oeffentlich.gruppen``/``.gruppe`` -> Gruppen (+ Termine)
  (L5) ``website.oeffentlich.beitraege``  -> Beitraege, HTML nach Allowlist
  (L6) ``/website/bild/{art}/{slug}``     -> nur Bilder freigegebener Objekte
  (L7) ``/website/ical/{slug}.ics``       -> VCALENDAR (Parser), UID stabil
  (L8) CORS nur fuer ``PRIMO_PUBLIC_URL``, ``Cache-Control``, Bremse (429)
  Pfade mit UND ohne ``DIAKRONOS_BASE_PATH``; Methoden ausser GET -> 405.

Netz (Kartenregel 11): ausschliesslich ``--network none``, DB = ``patched_db``
(In-Memory-SQLite), Redis = ``fake_redis``. Kein Test greift auf
``settings.database_url`` zu und keiner spricht Primo an.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen  # noqa: F401 — Fixture-Naht
from diakronos_app.models.diakonos import Beitrag, Gruppe, Registrierungslink
from diakronos_app.models.kronos import (
    Element,
    Eventkategorie,
    Kalender,
    Ressource,
)

MODUL = "diakronos_app.website.oeffentlich_api"
PFAD = "website.oeffentlich"

#: Aus der Ortszeit (nicht UTC) — das Produktionsfenster rechnet ebenso.
#: BS-2c2, Befund 1 (ursprueglicher Fehler): der alte Test baute seine Daten mit
#: ``date.today()`` (UTC) „+400 Tage" und verlangte „draussen" — der Termin
#: stand aber AUF der einschliessenden 400-Tage-Grenze. Der Tageswechsel
#: UTC/Ortszeit machte das mal rot, mal gruen.
try:
    HEUTE = datetime.now(tz=ZoneInfo("Europe/Berlin")).date()
except Exception:  # noqa: BLE001 — ohne tzdata gilt UTC
    HEUTE = datetime.utcnow().date()
MORGEN = HEUTE + timedelta(days=1)
UEBERMORGEN = HEUTE + timedelta(days=2)
SPAETER = HEUTE + timedelta(days=30)
WEIT_WEG = HEUTE + timedelta(days=400)
#: Ein Datum JENSEITS der Fenstergrenze (401 Tage) — nicht auf der Kante.
WEIT_WEG_DAHINTER = HEUTE + timedelta(days=401)

#: Diese Schluessel duerfen in KEINER Antwort auftauchen (G1).
VERBOTEN = frozenset(
    {
        "mitarbeiter",
        "ablehnungs_grund",
        "moderiert_von",
        "ablaufplan",
        "dienstplan",
        "owner",
        "autor",
        "autor_email",
        "email",
        "teilnehmer",
        "event_participants",
        "leiter",
        "verantwortliche",
        "name_intern",
        "modified_by",
        "created_by",
        "docstatus",
        "website_freigabe",
        "sichtbarkeit",
    }
)


#: Einstellungen, die einzelne Tests veraendern — nach JEDEM Test zurueck.
_SETTINGS = (
    "primo_public_url",
    "website_oeffentlich_max_ip",
    "website_oeffentlich_max_gesamt",
    "website_oeffentlich_fenster_sekunden",
)


def _setze_setting(name: str, wert) -> None:
    """Setzt eine Einstellung fuer die Dauer des Tests.

    ``settings`` ist eine pydantic-Instanz: ``monkeypatch.setattr`` scheitert
    dort an der Validierung, und Felder mit ``validation_alias`` greifen nicht
    auf den Feldnamen. ``object.__setattr__`` schreibt direkt — deshalb stellt
    das autouse-Fixture unten jeden Wert wieder her (dasselbe Muster wie
    ``test_web10_kontakt.py``). Ohne das Zuruecksetzen verfaelscht ein Test
    die folgenden: ``primo_public_url`` oder ``diakronos_base_path`` blieben
    sonst stehen.
    """
    from diakronos_app.settings import settings as echte

    object.__setattr__(echte, name, wert)


@pytest.fixture(autouse=True)
def _settings_zuruecksetzen():
    """Stellt alle veraenderten Einstellungen wieder her (auch ``diakronos_base_path``)."""
    from diakronos_app.settings import settings as echte

    alt = {name: getattr(echte, name) for name in _SETTINGS + ("diakronos_base_path",)}
    yield
    for name, wert in alt.items():
        object.__setattr__(echte, name, wert)


# ── Bestand ────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Bestand: zwei Kalender (einer freigegeben), Gruppen, Beitraege, Termine."""
    sess = patched_db()
    sess.add(
        Kalender(
            name="kal-gemeinde",
            calendar_name="Gemeinde",
            calendar_color="#1f6feb",
            website_freigabe=True,
            website_slug="gemeinde",
            website_nur_oeffentliche_kategorien=False,
        )
    )
    sess.add(
        Kalender(
            name="kal-intern",
            calendar_name="Intern",
            calendar_color="#ff0000",
            website_freigabe=False,
            website_slug="intern",
        )
    )
    # Freigegeben, aber nur mit OEFFENTLICHEN Kategorien.
    sess.add(
        Kalender(
            name="kal-jugend",
            calendar_name="Jugend",
            calendar_color="rot; background:url(x)",
            website_freigabe=True,
            website_slug="jugend",
            website_nur_oeffentliche_kategorien=True,
        )
    )
    sess.add(Eventkategorie(name="kat-gd", event_category_name="Gottesdienst", oeffentlich=True))
    sess.add(Eventkategorie(name="kat-sitzung", event_category_name="Sitzung", oeffentlich=False))
    sess.add(Ressource(name="res-saal", ressource_name="Gemeindesaal"))
    sess.add(
        Gruppe(
            name="gr-jugendkreis",
            gruppenname="Jugendkreis",
            gruppentyp=None,
            website_freigabe=True,
            website_slug="jugendkreis",
            sichtbarkeit="Öffentlich",
            beschreibung="<p>Wir treffen <b>uns</b>.</p>",
            treffzeit="Freitag 19:00",
            treffpunkt="Jugendraum",
            bild=None,
        )
    )
    sess.add(
        Gruppe(
            name="gr-intern",
            gruppenname="Ältestenkreis",
            website_freigabe=False,
            website_slug="aeltestenkreis",
            sichtbarkeit="Öffentlich",
        )
    )
    sess.add(
        Gruppe(
            name="gr-versteckt",
            gruppenname="Versteckter Kreis",
            website_freigabe=True,
            website_slug="versteckt",
            sichtbarkeit="Versteckt",
        )
    )
    sess.add(
        Beitrag(
            name="b-1",
            titel="Sommerfest",
            kategorie="allgemein",
            datum=MORGEN,
            veroeffentlicht=True,
            auf_website=True,
            autor="Erika Muster",
            autor_email="erika@example.org",
            auszug="<p>Ein <b>Fest</b> für alle.</p>",
            inhalt=(
                "<p>Kommt <strong>alle</strong>.</p><script>alert(1)</script>"
                '<a href="javascript:alert(1)">böse</a>'
                '<a href="https://example.org">gut</a>'
            ),
            bild=None,
        )
    )
    sess.add(
        Beitrag(
            name="b-2",
            titel="Entwurf",
            datum=MORGEN,
            veroeffentlicht=False,
            auf_website=True,
            autor="Erika Muster",
        )
    )
    sess.add(
        Beitrag(
            name="b-3",
            titel="Nicht auf Website",
            datum=MORGEN,
            veroeffentlicht=True,
            auf_website=False,
        )
    )
    sess.add(Registrierungslink(
        name="link-gast",
        typ="Gast-Anmeldung",
        aktiv=True,
        slug="abc123token",
        element=None,
    ))
    sess.commit()
    yield sess
    sess.close()


def _termin(sess, name: str, *, kalender: str = "kal-gemeinde", start=None,
            ende=None, status: str = "Festgelegt", kategorie: str | None = None,
            gruppe: str | None = None, all_day: bool = False,
            anmeldung_aktiv: bool = False, link: str | None = None) -> Element:
    """Legt einen Termin an (mit allen Feldern, die G1 verbietet)."""
    beginn = start or datetime.combine(MORGEN, datetime.min.time()).replace(hour=10)
    element = Element(
        name=name,
        element_name=f"Termin {name}",
        element_calendar=kalender,
        element_start=beginn,
        element_end=ende or (beginn + timedelta(hours=1)),
        all_day=all_day,
        status=status,
        element_category=kategorie,
        gruppe=gruppe,
        description="<p>Beschreibung mit <b>HTML</b></p>",
        ressource="res-saal",
        element_color="#00aa00",
        anmeldung_aktiv=anmeldung_aktiv,
        registrierungslink=link,
        ablehnungs_grund="NICHT OEFFENTLICH",
        moderiert_von="verwaltung@example.org",
        owner="verwaltung@example.org",
    )
    sess.add(element)
    sess.commit()
    return element


# ── Helfer ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def gast(patched_db, fake_redis):
    """Client OHNE Sitzung (Gast) — die oeffentliche Ausgabe ist allow_guest."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def _get(c, name: str, **params):
    return c.get(f"/api/method/{PFAD}.{name}", params=params)


def _schluessel(daten) -> set[str]:
    """Alle Schluesselnamen einer Antwort (rekursiv)."""
    gefunden: set[str] = set()
    if isinstance(daten, dict):
        for k, v in daten.items():
            gefunden.add(str(k))
            gefunden |= _schluessel(v)
    elif isinstance(daten, list):
        for eintrag in daten:
            gefunden |= _schluessel(eintrag)
    return gefunden


def _ohne_verbotene(daten) -> set[str]:
    """Schnittmenge der Antwort-Schluessel mit der Verbotsliste."""
    return _schluessel(daten) & VERBOTEN


# ═══════════════════════════════════════════════════════════════════════════
# (L1) Kalender
# ═══════════════════════════════════════════════════════════════════════════


def test_l1_nur_freigegebene_kalender(gast, welt):
    antwort = _get(gast, "kalender")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    slugs = {k["slug"] for k in daten}
    assert slugs == {"gemeinde", "jugend"}, "nicht freigegebener Kalender ist oeffentlich"
    for k in daten:
        assert set(k) == {"slug", "titel", "farbe"}
    gemeinde = next(k for k in daten if k["slug"] == "gemeinde")
    assert gemeinde["titel"] == "Gemeinde"
    assert gemeinde["farbe"] == "#1f6feb"
    # Ein unbrauchbarer Farbwert wird NICHT durchgereicht (CSS-Injektion).
    jugend = next(k for k in daten if k["slug"] == "jugend")
    assert jugend["farbe"] == ""


def test_l1_ohne_freigabe_ist_leer(gast, patched_db):
    """Default AUS: ohne Freigabe gibt es nichts zu lesen."""
    sess = patched_db()
    sess.add(Kalender(name="kal-x", calendar_name="X", website_freigabe=False))
    sess.commit()
    daten = _get(gast, "kalender").json()["message"]
    assert daten == []


def test_l1_kalender_ohne_slug_ist_nicht_oeffentlich(gast, welt):
    """Freigabe ohne Slug ist nicht adressierbar — und damit nicht oeffentlich."""
    welt.add(Kalender(name="kal-ohne", calendar_name="Ohne Slug", website_freigabe=True))
    welt.commit()
    slugs = {k["slug"] for k in _get(gast, "kalender").json()["message"]}
    assert "kal-ohne" not in slugs
    assert "" not in slugs


# ═══════════════════════════════════════════════════════════════════════════
# (L2) Termine — Status- und Freigabefilter
# ═══════════════════════════════════════════════════════════════════════════


def test_l2_nur_festgelegte_termine_freigegebener_kalender(gast, welt):
    _termin(welt, "t-ok")
    _termin(welt, "t-vorschlag", status="Vorschlag")
    _termin(welt, "t-konflikt", status="Konflikt")
    _termin(welt, "t-abgelehnt", status="Abgelehnt")
    _termin(welt, "t-bestaetigt", status="Bestätigt")
    _termin(welt, "t-intern", kalender="kal-intern")

    daten = _get(gast, "termine", von=HEUTE.isoformat(), bis=(HEUTE + timedelta(days=7)).isoformat()).json()["message"]
    titel = {t["titel"] for t in daten}
    assert "Termin t-ok" in titel
    # Alle anderen Stati sind NICHT oeffentlich (Entwurf, Konflikt, abgelehnt).
    for verboten in ("Termin t-vorschlag", "Termin t-konflikt",
                     "Termin t-abgelehnt", "Termin t-bestaetigt",
                     "Termin t-intern"):
        assert verboten not in titel, f"{verboten} ist oeffentlich geworden"


def test_l2_feld_positivliste_und_verbotene_felder(gast, welt):
    element = _termin(welt, "t-internkennung", anmeldung_aktiv=True, link="link-gast")
    # Der ANZEIGENAME ist frei waehlbar (die Gemeinde tippt ihn) — er darf
    # deshalb nicht wie die interne Kennung heissen, sonst pruefte der Test
    # nur den Titel. Die Kennung selbst ist das Verbotene.
    element.element_name = "Gottesdienst am Sonntag"
    welt.commit()
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    assert daten, "erwartet mindestens einen Termin"
    eintrag = daten[0]
    assert set(eintrag) == {
        "id", "titel", "beginn", "ende", "ganztaegig", "beschreibung",
        "ort", "kategorie", "gruppe", "farbe", "anmeldung_url",
    }
    # G1 EXPLIZIT NEGATIV: keine Personendaten, keine Ablehnungsgruende,
    # keine internen Kennungen — weder als Schluessel noch als Wert.
    assert _ohne_verbotene(daten) == set()
    roh = str(daten)
    assert "verwaltung@example.org" not in roh
    assert "NICHT OEFFENTLICH" not in roh
    assert "t-internkennung" not in roh, "interne Terminkennung steht in der Antwort"
    # Beschreibung ist Klartext (HTML entfernt).
    assert "<" not in eintrag["beschreibung"]
    assert "Beschreibung mit HTML" in eintrag["beschreibung"]
    # Ort ist der Ressourcen-ANZEIGENAME, nicht die Kennung.
    assert eintrag["ort"] == "Gemeindesaal"


def test_l2_beginn_ist_iso_mit_zone(gast, welt):
    _termin(welt, "t-ok")
    eintrag = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    beginn = eintrag["beginn"]
    assert "T" in beginn
    assert beginn.endswith(("+01:00", "+02:00")), beginn


def test_l2_kategorie_einschraenkung_des_kalenders(gast, welt):
    """``website_nur_oeffentliche_kategorien``: nur oeffentliche Kategorien."""
    _termin(welt, "t-jugend-oeff", kalender="kal-jugend", kategorie="kat-gd")
    _termin(welt, "t-jugend-intern", kalender="kal-jugend", kategorie="kat-sitzung")
    _termin(welt, "t-jugend-ohne", kalender="kal-jugend")
    daten = _get(gast, "termine", kalender="jugend", von=HEUTE.isoformat()).json()["message"]
    titel = {t["titel"] for t in daten}
    assert titel == {"Termin t-jugend-oeff"}
    # Der freigegebene Kalender OHNE Einschraenkung gibt weiterhin alles aus.
    daten = _get(gast, "termine", kalender="gemeinde", von=HEUTE.isoformat()).json()["message"]
    assert titel.isdisjoint({t["titel"] for t in daten})


def test_l2_kategorie_parameter_nur_oeffentliche_kategorien(gast, welt):
    _termin(welt, "t-gd", kategorie="kat-gd")
    _termin(welt, "t-sitzung", kategorie="kat-sitzung")
    daten = _get(
        gast, "termine", von=HEUTE.isoformat(), kategorie="Gottesdienst"
    ).json()["message"]
    assert {t["titel"] for t in daten} == {"Termin t-gd"}
    # Eine NICHT oeffentliche Kategorie ergibt eine leere Liste — der Filter
    # darf keine internen Terminarten zugaenglich machen.
    daten = _get(
        gast, "termine", von=HEUTE.isoformat(), kategorie="Sitzung"
    ).json()["message"]
    assert daten == []


def test_l2_nicht_freigegebener_kalender_ist_still_verworfen(gast, welt):
    """Ein angegebener, nicht freigegebener Slug verraet nichts (leere Liste)."""
    _termin(welt, "t-intern", kalender="kal-intern")
    daten = _get(gast, "termine", kalender="intern", von=HEUTE.isoformat()).json()["message"]
    assert daten == []


def test_l2_unbekannter_slug_ebenfalls_leer(gast, welt):
    daten = _get(gast, "termine", kalender="gibtsnicht", von=HEUTE.isoformat()).json()["message"]
    assert daten == []


def test_l2_zeitfenster_default_und_grenzen(gast, welt, monkeypatch):
    """Fenstergrenzen: Standard 90 Tage, hoechstens 400 — und einschliesslich.

    BS-2c2, Befund 1 — warum dieser Test zeitweise auf ``main`` rot war:
    der ALTE Test legte seinen fernen Termin auf ``HEUTE + 400`` und verlangte
    „draussen" — das Fenster schliesst Tag 400 aber EIN (``von .. von + 400``,
    einschliesslich). Der Termin stand also AUF der Grenze, nicht dahinter.
    Zuverlaessig rot wurde das durch den Tageswechsel zwischen Testmodul und
    Produktionsmodul: ``HEUTE`` kam aus der Ortszeit (``Europe/Berlin``), ein
    zur UTC-Mitternacht erzeugtes ``date.today() + 400`` liegt je nach
    Uhrzeit/Zeitzone einen Tag daneben — dann rutschte die Kante mal nach
    innen, mal nach aussen. Die Ursache lag allein im Test, nicht im
    Produktionscode (``fristen()`` kuerzt korrekt einschliesslich auf
    ``von + TAGE_MAX_BIS``). Deshalb: Uhr des Moduls festnageln, und die
    Grenze an ``TAGE_MAX_BIS`` haengen statt eine Zahl zu wiederholen.
    Beleg (messbar in diesem Test): Fenster = 400 Tage, Tag 400 im Fenster
    (``t-grenze``), Tag 401 nicht (``t-fern``).
    """
    from diakronos_app.website import oeffentlich_daten as mod

    monkeypatch.setattr(mod, "_heute", lambda: HEUTE)
    grenze = HEUTE + timedelta(days=mod.TAGE_MAX_BIS)
    _termin(welt, "t-heute", start=datetime.combine(HEUTE, datetime.min.time()).replace(hour=9))
    _termin(welt, "t-fern",
            start=datetime.combine(WEIT_WEG_DAHINTER, datetime.min.time()).replace(hour=9))
    # Default: heute .. +90 Tage -> beide fernen Termine fehlen.
    titel = {t["titel"] for t in _get(gast, "termine").json()["message"]}
    assert "Termin t-heute" in titel
    assert "Termin t-fern" not in titel
    # Explizit weites Fenster: die Grenze von 400 Tagen greift (Tag 401 fehlt).
    daten = _get(gast, "termine", von=HEUTE.isoformat(),
                 bis=(HEUTE + timedelta(days=900)).isoformat()).json()["message"]
    assert "Termin t-fern" not in daten, "Fenstergrenze 400 Tage nicht wirksam"
    # Die Grenze selbst ist einschliesslich: Tag 400 kommt mit, Tag 401 nicht.
    # (Weites ``bis`` noetig — OHNE ``bis`` gilt das Standardfenster von 90
    # Tagen; genau daran war die erste Fassung dieses Tests gescheitert.)
    _termin(welt, "t-grenze", start=datetime.combine(grenze, datetime.min.time()).replace(hour=9))
    titel = {
        t["titel"]
        for t in _get(gast, "termine", von=HEUTE.isoformat(),
                      bis=(HEUTE + timedelta(days=900)).isoformat(),
                      limit=500).json()["message"]
    }
    assert "Termin t-grenze" in titel
    assert "Termin t-fern" not in titel
    # Und im Standardfenster ist auch der Grenztermin draussen.
    titel = {t["titel"] for t in _get(gast, "termine").json()["message"]}
    assert "Termin t-grenze" not in titel


def test_l2_limit_grenzen(gast, welt):
    for i in range(5):
        _termin(
            welt,
            f"t-{i}",
            start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=8 + i),
        )
    assert len(_get(gast, "termine", von=HEUTE.isoformat(), limit=2).json()["message"]) == 2
    # Ein unsinniger Wert faellt auf die Vorgabe zurueck (kein 500).
    assert len(_get(gast, "termine", von=HEUTE.isoformat(), limit="viel").json()["message"]) == 5


def test_l2_gruppenfilter_mehrere_kalender_mit_komma(gast, welt):
    _termin(welt, "t-gemeinde")
    _termin(welt, "t-jugend", kalender="kal-jugend", kategorie="kat-gd")
    daten = _get(
        gast, "termine", kalender="gemeinde,jugend", von=HEUTE.isoformat()
    ).json()["message"]
    titel = {t["titel"] for t in daten}
    assert titel == {"Termin t-gemeinde", "Termin t-jugend"}


def test_l2_gruppenzuordnung_nur_wenn_gruppe_freigegeben(gast, welt):
    _termin(welt, "t-mit-gruppe", gruppe="gr-jugendkreis")
    _termin(welt, "t-ohne", )
    daten = {
        t["titel"]: t for t in _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    }
    assert daten["Termin t-mit-gruppe"]["gruppe"] == {
        "slug": "jugendkreis",
        "name": "Jugendkreis",
    }
    assert daten["Termin t-ohne"]["gruppe"] is None


def test_l2_anmeldung_url_nur_bei_aktivem_link(gast, welt):
    _termin(welt, "t-anmeldung", anmeldung_aktiv=True, link="link-gast")
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    assert daten["anmeldung_url"], "aktiver Link, aber keine Adresse"
    assert "abc123token" in daten["anmeldung_url"]
    assert "/gast" in daten["anmeldung_url"]


def test_l2_anmeldung_url_leer_wenn_link_inaktiv(gast, welt):
    link = welt.get(Registrierungslink, "link-gast")
    link.aktiv = False
    welt.commit()
    _termin(welt, "t-anmeldung", anmeldung_aktiv=True, link="link-gast")
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    assert daten["anmeldung_url"] == ""

    # Ohne anmeldung_aktiv gar keine Adresse, auch bei aktivem Link.
    link.aktiv = True
    welt.commit()
    _termin(welt, "t-keine-anmeldung", anmeldung_aktiv=False, link="link-gast")
    alle = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    ohne = next(t for t in alle if t["titel"] == "Termin t-keine-anmeldung")
    assert ohne["anmeldung_url"] == ""


def test_l2_nur_anmeldung_filtert_vor_dem_limit(gast, welt, monkeypatch):
    """BS-2c2 (4): ``nur_anmeldung`` filtert SERVERSEITIG.

    Vorher holte der Baustein ``anmeldung`` das ganze Fenster (limit 500) und
    behielt im Browser die Zeilen mit ``anmeldung_url``. Bei vielen Terminen
    ohne Anmeldung fiel die Anzeige dadurch kuerzer aus als verlangt. Hier
    steht die Anmeldung ERST hinter einer Reihe von Terminen ohne Anmeldung:
    mit ``limit=1`` muss trotzdem genau der Anmeldetermin kommen.
    """
    from diakronos_app.website import oeffentlich_daten as mod

    monkeypatch.setattr(mod, "_heute", lambda: HEUTE)
    for i in range(3):
        _termin(welt, f"t-ohne-{i}",
                start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=8 + i))
    _termin(welt, "t-mit", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=20),
            anmeldung_aktiv=True, link="link-gast")

    daten = _get(gast, "termine", von=HEUTE.isoformat(),
                 nur_anmeldung=1, limit=1).json()["message"]
    assert [t["titel"] for t in daten] == ["Termin t-mit"]
    assert "abc123token" in daten[0]["anmeldung_url"]

    # Schalter-Varianten: 0/false/leer = wie ohne Parameter.
    alle = _get(gast, "termine", von=HEUTE.isoformat(), nur_anmeldung=0).json()["message"]
    assert len(alle) == 4
    alle = _get(gast, "termine", von=HEUTE.isoformat(), nur_anmeldung="nein").json()["message"]
    assert len(alle) == 4


def test_l2_nur_anmeldung_ohne_tauglichen_link_zaehlt_nicht(gast, welt, monkeypatch):
    """Ein Termin mit „Anmeldung aktiv", aber ohne Adresse, gehoert NICHT dazu.

    Zwei Faelle: Link inaktiv (Zeitfenster/Typ) und gar kein Link gepflegt.
    Beide haben ``anmeldung_url == ""`` — ein Knopf „Anmelden" ins Leere waere
    genau der Fehler, den der Filter verhindert.
    """
    from diakronos_app.models.diakonos import Registrierungslink
    from diakronos_app.website import oeffentlich_daten as mod

    monkeypatch.setattr(mod, "_heute", lambda: HEUTE)
    _termin(welt, "t-ok", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=9),
            anmeldung_aktiv=True, link="link-gast")
    _termin(welt, "t-ohne-link", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=10),
            anmeldung_aktiv=True)
    link = welt.get(Registrierungslink, "link-gast")
    link.aktiv = False
    welt.commit()
    _termin(welt, "t-inaktiv", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=11),
            anmeldung_aktiv=True, link="link-gast")
    link.aktiv = True
    welt.commit()

    daten = _get(gast, "termine", von=HEUTE.isoformat(), nur_anmeldung="true").json()["message"]
    assert {t["titel"] for t in daten} == {"Termin t-ok", "Termin t-inaktiv"}
    assert all(t["anmeldung_url"] for t in daten)


def test_l2_nur_anmeldung_und_gruppe(gast, welt):
    """Die Filter lassen sich verbinden: ``nur_anmeldung`` + ``gruppe``."""
    _termin(welt, "t-gruppe-mit", gruppe="gr-jugendkreis",
            anmeldung_aktiv=True, link="link-gast")
    _termin(welt, "t-gruppe-ohne", gruppe="gr-jugendkreis")
    _termin(welt, "t-anders-mit", anmeldung_aktiv=True, link="link-gast")
    daten = _get(gast, "termine", von=HEUTE.isoformat(),
                 nur_anmeldung=1, gruppe="jugendkreis").json()["message"]
    assert [t["titel"] for t in daten] == ["Termin t-gruppe-mit"]


def test_l2_serienwerden_einzeln_ausgegeben(gast, welt):
    """Serien sind Einzelzeilen mit gemeinsamem ``series_id`` — keine RRULE."""
    for i in range(3):
        element = _termin(
            welt,
            f"t-serie-{i}",
            start=datetime.combine(MORGEN + timedelta(days=7 * i), datetime.min.time()).replace(hour=10),
        )
        element.series_id = "serie-1"
        element.repeat_this_event = True
        welt.commit()
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    assert len([t for t in daten if t["titel"].startswith("Termin t-serie")]) == 3


# ═══════════════════════════════════════════════════════════════════════════
# (L3) naechster Termin
# ═══════════════════════════════════════════════════════════════════════════


def test_l3_naechster_termin_ist_der_frueheste(gast, welt):
    _termin(welt, "t-spaet", start=datetime.combine(SPAETER, datetime.min.time()).replace(hour=10))
    _termin(welt, "t-frueh", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=9))
    daten = _get(gast, "naechster_termin").json()["message"]
    assert daten["titel"] == "Termin t-frueh"


def test_l3_ohne_termine_null(gast, welt):
    assert _get(gast, "naechster_termin").json()["message"] is None


def test_l3_vergangene_termine_zaehlen_nicht(gast, welt):
    _termin(
        welt,
        "t-gestern",
        start=datetime.combine(HEUTE - timedelta(days=1), datetime.min.time()).replace(hour=10),
    )
    assert _get(gast, "naechster_termin").json()["message"] is None


def test_l3_kategorie_und_kalender_filter(gast, welt):
    _termin(welt, "t-gemeinde", start=datetime.combine(MORGEN, datetime.min.time()).replace(hour=9))
    _termin(welt, "t-jugend", kalender="kal-jugend", kategorie="kat-gd",
            start=datetime.combine(UEBERMORGEN, datetime.min.time()).replace(hour=9))
    daten = _get(gast, "naechster_termin", kalender="jugend").json()["message"]
    assert daten["titel"] == "Termin t-jugend"
    daten = _get(gast, "naechster_termin", kategorie="Gottesdienst").json()["message"]
    assert daten["titel"] == "Termin t-jugend"


# ═══════════════════════════════════════════════════════════════════════════
# (L4) Gruppen
# ═══════════════════════════════════════════════════════════════════════════


def test_l4_nur_freigegebene_und_nicht_versteckte_gruppen(gast, welt):
    daten = _get(gast, "gruppen").json()["message"]
    slugs = {g["slug"] for g in daten}
    assert slugs == {"jugendkreis"}, (
        "nicht freigegebene oder versteckte Gruppe ist oeffentlich"
    )
    assert set(daten[0]) == {
        "slug", "name", "typ", "beschreibung", "treffzeit", "treffpunkt", "bild_url",
    }
    assert "<" not in daten[0]["beschreibung"]
    assert _ohne_verbotene(daten) == set()


def test_l4_gruppe_detail_mit_naechsten_terminen(gast, welt):
    _termin(welt, "t-gruppe", gruppe="gr-jugendkreis")
    daten = _get(gast, "gruppe", slug="jugendkreis").json()["message"]
    assert daten["name"] == "Jugendkreis"
    assert set(daten["naechste_termine"][0]) == {
        "id", "titel", "beginn", "ende", "ganztaegig", "beschreibung",
        "ort", "kategorie", "gruppe", "farbe", "anmeldung_url",
    }
    assert daten["naechste_termine"][0]["titel"] == "Termin t-gruppe"
    assert _ohne_verbotene(daten) == set()


def test_l4_gruppe_detail_404_wenn_nicht_freigegeben(gast, welt):
    antwort = _get(gast, "gruppe", slug="aeltestenkreis")
    assert antwort.status_code == 404, antwort.text
    # SEC-8: der Klassenname bleibt generisch; unterschieden wird am Status.
    assert antwort.json()["exc_type"] == "Error"
    assert antwort.json()["message"] == "Nicht gefunden."
    assert _get(gast, "gruppe", slug="versteckt").status_code == 404
    assert _get(gast, "gruppe", slug="").status_code == 404


def test_l4_gruppentyp_filter(gast, welt):
    from diakronos_app.frappe_compat.registry_gen import model_for

    Gruppentyp = model_for("Gruppentyp")
    welt.add(Gruppentyp(name="typ-chor", typname="Chor"))
    welt.add(
        Gruppe(
            name="gr-chor",
            gruppenname="Chor",
            gruppentyp="typ-chor",
            website_freigabe=True,
            website_slug="chor",
            sichtbarkeit="Öffentlich",
        )
    )
    welt.commit()
    assert {g["slug"] for g in _get(gast, "gruppen").json()["message"]} == {
        "jugendkreis", "chor",
    }
    gefiltert = _get(gast, "gruppen", typ="Chor").json()["message"]
    assert [g["slug"] for g in gefiltert] == ["chor"]


# ═══════════════════════════════════════════════════════════════════════════
# (L5) Beitraege
# ═══════════════════════════════════════════════════════════════════════════


def test_l5_nur_veroeffentlicht_und_auf_website(gast, welt):
    daten = _get(gast, "beitraege").json()["message"]
    assert {b["titel"] for b in daten} == {"Sommerfest"}
    assert _ohne_verbotene(daten) == set()
    roh = str(daten)
    assert "Erika Muster" not in roh, "Autorname ist oeffentlich geworden"
    assert "erika@example.org" not in roh, "Autor-Adresse ist oeffentlich geworden"
    assert "b-1" not in roh, "interne Beitragskennung steht in der Antwort"


def test_l5_inhalt_nach_allowlist(gast, welt):
    inhalt = _get(gast, "beitraege").json()["message"][0]["inhalt"]
    assert "<script" not in inhalt
    assert "alert(1)" not in inhalt
    assert "javascript:" not in inhalt
    assert "<strong>alle</strong>" in inhalt
    assert '<a href="https://example.org">gut</a>' in inhalt
    # Der Link ohne erlaubtes Schema bleibt als Text stehen.
    assert ">böse</a>" in inhalt


def test_l5_limit_und_kategorie(gast, welt):
    for i in range(4):
        welt.add(Beitrag(
            name=f"b-x{i}", titel=f"Neu {i}", kategorie="jugend",
            datum=MORGEN + timedelta(days=i),
            veroeffentlicht=True, auf_website=True,
        ))
    welt.commit()
    daten = _get(gast, "beitraege", limit=2).json()["message"]
    assert len(daten) == 2
    # neueste zuerst
    assert daten[0]["titel"] == "Neu 3"
    gefiltert = _get(gast, "beitraege", kategorie="jugend").json()["message"]
    assert {b["kategorie"] for b in gefiltert} == {"jugend"}
    assert len(gefiltert) == 4


def test_l5_auszug_ist_klartext(gast, welt):
    auszug = _get(gast, "beitraege").json()["message"][0]["auszug"]
    assert "<" not in auszug
    assert "Ein Fest für alle." in auszug


# ═══════════════════════════════════════════════════════════════════════════
# (L7) iCal-Feed
# ═══════════════════════════════════════════════════════════════════════════


def test_l7_ics_valide_und_uid_stabil(gast, welt):
    from icalendar import Calendar

    _termin(welt, "t-ics-1")
    _termin(welt, "t-ics-2", start=datetime.combine(UEBERMORGEN, datetime.min.time()).replace(hour=9))
    antwort = gast.get("/website/ical/gemeinde.ics")
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["content-type"].startswith("text/calendar")
    cal = Calendar.from_ical(antwort.content)
    namen = [str(t.get("summary")) for t in cal.walk("VEVENT")]
    assert namen == ["Termin t-ics-1", "Termin t-ics-2"]
    uids = [str(t.get("uid")) for t in cal.walk("VEVENT")]
    assert len(set(uids)) == 2
    assert all(u.endswith("@diakronos") for u in uids)
    # UID stabil ueber zwei Aufrufe (und NICHT die interne Kennung).
    zweite = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    assert [str(t.get("uid")) for t in zweite.walk("VEVENT")] == uids
    assert "t-ics-1" not in " ".join(uids)


def test_l7_ics_gleiche_filter_wie_l2(gast, welt):
    from icalendar import Calendar

    _termin(welt, "t-ok")
    _termin(welt, "t-vorschlag", status="Vorschlag")
    cal = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    namen = [str(t.get("summary")) for t in cal.walk("VEVENT")]
    assert namen == ["Termin t-ok"]


def test_l7_ics_enthaelt_keine_personendaten(gast, welt):
    _termin(welt, "t-ok")
    text = gast.get("/website/ical/gemeinde.ics").text
    assert "verwaltung@example.org" not in text
    assert "NICHT OEFFENTLICH" not in text
    assert "Mitarbeiter" not in text


def test_l7_nicht_freigegeben_ist_404(gast, welt):
    antwort = gast.get("/website/ical/intern.ics")
    assert antwort.status_code == 404
    assert antwort.json()["exc_type"] == "Error"


def test_l7_escaping_und_ganztaegig(gast, welt):
    from icalendar import Calendar

    element = _termin(
        welt, "t-sonder",
        start=datetime.combine(MORGEN, datetime.min.time()), all_day=True,
    )
    element.element_name = "Fest, Feier; mit \\ Sonderzeichen"
    element.description = "Zeile 1\nZeile 2"
    welt.commit()
    cal = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    event = list(cal.walk("VEVENT"))[0]
    assert str(event.get("summary")) == "Fest, Feier; mit \\ Sonderzeichen"
    assert "Zeile 1" in str(event.get("description"))
    assert event.decoded("dtstart") == MORGEN


# ═══════════════════════════════════════════════════════════════════════════
# (L6) Bild-Route
# ═══════════════════════════════════════════════════════════════════════════


def _bild_anlegen(monkeypatch, tmp_path, name: str = "foto.png") -> str:
    """Legt eine echte PNG-Datei an und zeigt ``files_dir`` darauf."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    # Kleinstes gueltiges PNG (1x1).
    daten = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (tmp_path / name).write_bytes(daten)
    return f"/files/{name}"


def test_l6_bild_nur_freigegebener_gruppe(gast, welt, monkeypatch, tmp_path):
    adresse = _bild_anlegen(monkeypatch, tmp_path)
    gruppe = welt.get(Gruppe, "gr-jugendkreis")
    gruppe.bild = adresse
    intern = welt.get(Gruppe, "gr-intern")
    intern.bild = adresse
    welt.commit()

    antwort = gast.get("/website/bild/gruppe/jugendkreis")
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["content-type"].startswith("image/png")
    assert antwort.headers["x-content-type-options"] == "nosniff"

    # Nicht freigegebene Gruppe -> 404 (kein Hinweis, dass es sie gibt).
    assert gast.get("/website/bild/gruppe/aeltestenkreis").status_code == 404
    # Unbekannter Slug, unbekannte Art -> 404.
    assert gast.get("/website/bild/gruppe/gibtsnicht").status_code == 404
    assert gast.get("/website/bild/person/jugendkreis").status_code == 404


def test_l6_bild_ohne_bild_ist_404(gast, welt):
    assert gast.get("/website/bild/gruppe/jugendkreis").status_code == 404


def test_l6_bild_falscher_inhalt_wird_nicht_ausgeliefert(gast, welt, monkeypatch, tmp_path):
    """Ein als PNG benanntes HTML-Dokument ist kein Bild."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    (tmp_path / "boese.png").write_bytes(b"<html><script>alert(1)</script></html>")
    gruppe = welt.get(Gruppe, "gr-jugendkreis")
    gruppe.bild = "/files/boese.png"
    welt.commit()
    assert gast.get("/website/bild/gruppe/jugendkreis").status_code == 404


def test_l6_svg_wird_nicht_ausgeliefert(gast, welt, monkeypatch, tmp_path):
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    (tmp_path / "bild.svg").write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    gruppe = welt.get(Gruppe, "gr-jugendkreis")
    gruppe.bild = "/files/bild.svg"
    welt.commit()
    assert gast.get("/website/bild/gruppe/jugendkreis").status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# (L8) Methoden, CORS, Cache, Bremse
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("name", ["kalender", "termine", "naechster_termin",
                                  "gruppen", "gruppe", "beitraege"])
def test_l8_nur_get(gast, welt, name):
    """POST/PUT auf einen Leseendpunkt -> 405 und KEINE Antwortdaten."""
    antwort = gast.post(f"/api/method/{PFAD}.{name}")
    assert antwort.status_code == 405, antwort.text
    # SEC-8: nicht allowlistete Fehlertypen gehen als generisches "Error"
    # nach aussen; unterschieden wird am Status (405) — kein Datenleck.
    assert antwort.json()["exc_type"] == "Error"
    assert "GET" in antwort.headers.get("allow", "")
    assert "message" in antwort.json()


def test_l8_cache_control(gast, welt):
    """Cache 5 Minuten und `Vary: Origin` auf der CORS-Variante.

    Der Methoden-Router setzt seine Koepfe selbst (er baut den Koerper) —
    dort gilt Frappes Verhalten. Die Route `/website/oeffentlich/…` ist der
    Weg der WEBSITE und traegt beide Koepfe.
    """
    antwort = gast.get("/website/oeffentlich/kalender")
    assert antwort.status_code == 200, antwort.text
    assert "max-age=300" in antwort.headers.get("cache-control", "")
    # `Vary` traegt zusaetzlich "Accept-Encoding" (GZip-Middleware) — Origin
    # muss enthalten sein, sonst liefert ein Zwischenspeicher die CORS-Antwort
    # an einen Aufrufer ohne Berechtigung aus.
    assert "Origin" in antwort.headers.get("vary", "").split(", ")
    assert set(antwort.json()["message"][0]) == {"slug", "titel", "farbe"}


@pytest.mark.parametrize("name", ["kalender", "termine", "gruppen", "beitraege"])
def test_l8_cors_fremde_herkunft_ohne_kopf(gast, welt, monkeypatch, name):
    from diakronos_app.settings import settings

    _setze_setting("primo_public_url", "https://website.example.org")
    antwort = gast.get(
        f"/api/method/{PFAD}.{name}", headers={"Origin": "https://boese.example.net"}
    )
    assert antwort.status_code == 200
    assert "access-control-allow-origin" not in antwort.headers


def test_l8_cors_primo_herkunft_erlaubt(gast, welt, monkeypatch):
    from diakronos_app.settings import settings

    _setze_setting("primo_public_url", "https://website.example.org")
    antwort = gast.get(
        f"/website/oeffentlich/kalender", headers={"Origin": "https://website.example.org"}
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["access-control-allow-origin"] == "https://website.example.org"
    assert "access-control-allow-credentials" not in antwort.headers
    assert {k["slug"] for k in antwort.json()["message"]} == {"gemeinde", "jugend"}


def test_l8_cors_ohne_primo_public_url_kein_kopf(gast, welt, monkeypatch):
    from diakronos_app.settings import settings

    _setze_setting("primo_public_url", "")
    antwort = gast.get(
        "/website/oeffentlich/kalender", headers={"Origin": "https://website.example.org"}
    )
    assert antwort.status_code == 200
    assert "access-control-allow-origin" not in antwort.headers


def test_l8_cors_optionen_antwort(gast, welt, monkeypatch):
    from diakronos_app.settings import settings

    _setze_setting("primo_public_url", "https://website.example.org")
    antwort = gast.options(
        "/website/oeffentlich/termine", headers={"Origin": "https://website.example.org"}
    )
    assert antwort.status_code == 204
    assert antwort.headers["access-control-allow-origin"] == "https://website.example.org"
    fremd = gast.options(
        "/website/oeffentlich/termine", headers={"Origin": "https://boese.example.net"}
    )
    assert fremd.status_code == 405


def test_l8_bremse_greift(gast, welt):
    """Die Bremse greift und die Meldung nennt keine Interna.

    Der Test setzt ZUERST die Grenze hoch und leert dann den Adresszaehler:
    der Zaehler liegt im gemeinsamen Redis und enthaelt die Anfragen der
    vorherigen Tests. Wuerde er nur vorher geleert, koennte eine parallele
    Pruefung ihn wieder fuellen — die Reihenfolge Grenze -> Leeren macht den
    Test unabhaengig davon, was vorher passiert ist.
    """
    from diakronos_app.website import oeffentlich_bremse as bremse

    _setze_setting("website_oeffentlich_max_gesamt", 0)
    _setze_setting("website_oeffentlich_max_ip", 2)
    _setze_setting("website_oeffentlich_fenster_sekunden", 60)
    client = bremse._client()
    for schluessel in client.scan_iter(f"{bremse.SCHLUESSEL_PRAEFIX}*"):
        client.delete(schluessel)

    assert _get(gast, "kalender").status_code == 200
    assert _get(gast, "kalender").status_code == 200
    antwort = _get(gast, "kalender")
    assert antwort.status_code == 429, antwort.text
    # SEC-8: generischer Klassenname; unterschieden wird am Status (429).
    assert antwort.json()["exc_type"] == "Error"
    assert "zu viele Anfragen" in antwort.json()["message"]
    # Keine Interna in der Meldung.
    assert "Redis" not in antwort.text and "Traceback" not in antwort.text


def test_l8_bremse_aus_funktioniert(gast, welt, monkeypatch):
    from diakronos_app.settings import settings

    _setze_setting("website_oeffentlich_max_ip", 0)
    for _ in range(5):
        assert _get(gast, "kalender").status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Praefix (G3): alles unter DIAKRONOS_BASE_PATH
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def app_mit_praefix():
    """Anwendung mit ``DIAKRONOS_BASE_PATH=/diakronos``; Praefix danach zurueck."""
    from diakronos_app import base_path
    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings as echte

    alt_wert = echte.diakronos_base_path
    alt_praefix = base_path.aktiver_praefix()
    object.__setattr__(echte, "diakronos_base_path", "/diakronos")
    try:
        yield erstelle_app()
    finally:
        object.__setattr__(echte, "diakronos_base_path", alt_wert)
        base_path.setze_praefix(alt_praefix)


@pytest.fixture()
def gast_praefix(app_mit_praefix, patched_db, fake_redis):
    from fastapi.testclient import TestClient

    c = TestClient(app_mit_praefix)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def test_praefix_methodenpfad_und_routen(gast_praefix, welt):
    _termin(welt, "t-ok")
    antwort = gast_praefix.get("/diakronos/api/method/website.oeffentlich.kalender")
    assert antwort.status_code == 200, antwort.text
    assert {k["slug"] for k in antwort.json()["message"]} == {"gemeinde", "jugend"}

    ics = gast_praefix.get("/diakronos/website/ical/gemeinde.ics")
    assert ics.status_code == 200, ics.text
    assert "BEGIN:VCALENDAR" in ics.text

    ohne = gast_praefix.get("/api/method/website.oeffentlich.kalender")
    assert ohne.status_code == 404, "ohne Praefix darf der Pfad nicht erreichbar sein"


def test_praefix_bild_url_ist_praefixbewusst(gast_praefix, welt, monkeypatch, tmp_path):
    adresse = _bild_anlegen(monkeypatch, tmp_path)
    gruppe = welt.get(Gruppe, "gr-jugendkreis")
    gruppe.bild = adresse
    welt.commit()
    daten = gast_praefix.get("/diakronos/api/method/website.oeffentlich.gruppen").json()["message"]
    assert daten[0]["bild_url"].startswith("/diakronos/website/bild/gruppe/")
    antwort = gast_praefix.get(daten[0]["bild_url"])
    assert antwort.status_code == 200, antwort.text


def test_praefix_anmeldung_url_ist_praefixbewusst(gast_praefix, welt):
    _termin(welt, "t-anmeldung", anmeldung_aktiv=True, link="link-gast")
    daten = gast_praefix.get(
        "/diakronos/api/method/website.oeffentlich.naechster_termin"
    ).json()["message"]
    assert daten["anmeldung_url"].startswith("/diakronos/diakonos/gast"), daten["anmeldung_url"]


# ═══════════════════════════════════════════════════════════════════════════
# Registrierung (SEC-11/Inventar): allow_guest + GET, im Inventar
# ═══════════════════════════════════════════════════════════════════════════


def test_endpunkte_sind_als_lesend_registriert():
    from diakronos_app.frappe_compat import registry

    for name in ("kalender", "termine", "naechster_termin", "gruppen",
                 "gruppe", "beitraege"):
        fn = registry.lookup(f"{PFAD}.{name}")
        assert fn is not None, f"{PFAD}.{name} ist nicht registriert"
        optionen = registry.options_for(fn)
        assert optionen.get("allow_guest") is True
        assert optionen.get("methods") == ("GET",)
        # Auch der Original-Frappe-Pfad loest auf.
        assert registry.lookup(f"diakronos.diakronos.api.website.{name}") is fn
