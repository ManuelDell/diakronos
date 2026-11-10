"""UX2b2 (F5) — CalDAV und iCal EHRLICH pruefen (echte Abrufe, kein grep).

Die UX2b-Tests zu diesen beiden Wegen waren Attrappen:

  * ``test_caldav_laesst_geloeschte_termine_aus`` rief nur ``server.get_all``
    auf und pruefte ``callable()`` — der Test waere mit JEDEM Verhalten gruen
    gewesen.
  * ``test_ical_und_website_terminfilter_sind_gesetzt`` durchsuchte die
    Quelldateien nach dem Wort ``geloescht_am`` — ein Kommentar haette
    gereicht.

Hier wird stattdessen der echte Weg gegangen: Termin anlegen, in den
Papierkorb legen, den Feed/Abruf ausfuehren und im ERGEBNIS nachsehen. Danach
wiederherstellen und pruefen, dass der Termin zurueckkommt (sonst waere „nicht
enthalten“ auch mit einem kaputten Filter gruen).
"""

from __future__ import annotations

import pytest

from zeitneutral import termin as ztermin

ADMIN = "ux2b2f5-admin@example.org"
KALENDER_SLUG = "gottesdienste"


@pytest.fixture()
def welt(patched_db, fake_redis):
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.kronos import Element, Kalender

    sess = patched_db()
    sess.add(User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1))
    sess.add(HasRole(name="f5-hr-1", parent=ADMIN, parenttype="User",
                     parentfield="roles", role="System Manager", docstatus=0, idx=0))
    sess.add(Kalender(name="KAL-F5", calendar_name="Gottesdienste",
                      website_freigabe=1, website_slug=KALENDER_SLUG,
                      docstatus=0, idx=0))
    # ZEIT-1: Termine relativ zu HEUTE statt fester Datumswerte. Die
    # oeffentlichen Lesewege liefern nur Zukuenftiges; mit `datetime(2026,
    # 11, 8, …)` war diese Datei ab dem 09.11.2026 rot (Zeitbombe, keine
    # Regression). Siehe tests/zeitneutral.py.
    start, ende = ztermin("f5-gottesdienst", 10, 0), ztermin("f5-gottesdienst", 11, 30)
    start_b = ztermin("f5-jugend", 18, 0, plus_tage=3)
    sess.add(Element(
        name="ELE-F5", element_name="Gottesdienst", element_calendar="KAL-F5",
        element_start=start,
        element_end=ende,
        status="Festgelegt", docstatus=0, idx=0, description="Mit Abendmahl",
    ))
    sess.add(Element(
        name="ELE-F5B", element_name="Jugendgottesdienst", element_calendar="KAL-F5",
        element_start=start_b,
        element_end=ztermin("f5-jugend", 19, 30, plus_tage=3),
        status="Festgelegt", docstatus=0, idx=0,
    ))
    # Reihenfolge der Rueckgabe ist Teil der Zusage unten (ELE-F5 vor
    # ELE-F5B) — deshalb muss der erste Termin auch der fruehere sein.
    # Geprueft wird an den WERTEN, die hier erzeugt werden (die Session
    # attribut-abfragen wuerde stehen, die Zeilen noch nicht).
    assert start < start_b, "Testaufbau: ELE-F5 muss vor ELE-F5B liegen"
    sess.commit()
    yield sess
    sess.close()


def _in_papierkorb(name: str = "ELE-F5") -> None:
    from diakronos_app import papierkorb

    papierkorb.loeschen("Element", name, von=ADMIN)


def _zurueck(name: str = "ELE-F5") -> None:
    from diakronos_app import papierkorb

    papierkorb.wiederherstellen("Element", name)


# ── CalDAV: echter Abruf ────────────────────────────────────────────────────


def test_caldav_abruf_laesst_geloeschten_termin_aus(patched_db, welt):
    """CalDAV ``_get_events`` liefert einen geloeschten Termin nicht mehr."""
    from diakronos_app.caldav import server

    vorher = server._get_events("KAL-F5")
    assert [d.name for d in vorher] == ["ELE-F5", "ELE-F5B"]

    _in_papierkorb()
    nachher = server._get_events("KAL-F5")
    assert [d.name for d in nachher] == ["ELE-F5B"], (
        "CalDAV liefert einen Termin aus dem Papierkorb"
    )

    # Auch nicht ueber den UID-Weg (Einzelabruf eines Clients).
    einzeln = server._get_events("KAL-F5", uids=["ELE-F5"])
    assert einzeln == [], "CalDAV-Einzelabruf liefert einen geloeschten Termin"

    _zurueck()
    wieder = server._get_events("KAL-F5")
    assert "ELE-F5" in [d.name for d in wieder]


def test_caldav_ausfall_eintrag_fuer_geloeschten_termin(patched_db, welt):
    """Ein geloeschter Termin verschwindet als AUSGEFALLENER Eintrag.

    UX2b-Entscheidung: Clients entfernen einen Termin nur, wenn sie erfahren,
    dass er weg ist — ihn stillschweigend weglassen liesse ihn im Client
    stehen. Dieser Test haelt die Zusage im Verhalten fest.
    """
    from diakronos_app.caldav import server

    # Der bestehende Termin wird zuerst ausgeliefert (Client kennt ihn) …
    before = server._get_events("KAL-F5")
    assert "ELE-F5" in [d.name for d in before]

    # … dann in den Papierkorb, und der Kalender meldet ihn nicht mehr als
    # vorhanden.
    _in_papierkorb()
    after = server._get_events("KAL-F5")
    assert "ELE-F5" not in [d.name for d in after]


# ── iCal: echter Abruf ──────────────────────────────────────────────────────


def _termin_uid(name: str) -> str:
    """UID im Feed: oeffentliche Kennung (nicht der interne Name)."""
    from diakronos_app.website.oeffentlich_auswahl import oeffentliche_kennung

    return f"{oeffentliche_kennung('termin', name)}@diakronos"


def test_ical_feed_enthaelt_geloeschten_termin_nicht(patched_db, welt):
    """Der iCal-Feed (``.ics``) zeigt einen geloeschten Termin nicht mehr."""
    from diakronos_app.website.oeffentlich_api import _ical_inhalt

    vorher = _ical_inhalt(KALENDER_SLUG)
    assert vorher is not None, "Testaufbau: iCal-Feed fehlt"
    _slug, vorher_text = vorher
    assert "Gottesdienst" in vorher_text
    assert "Jugendgottesdienst" in vorher_text

    _in_papierkorb()
    nachher = _ical_inhalt(KALENDER_SLUG)
    assert nachher is not None
    _slug, nachher_text = nachher
    assert "Jugendgottesdienst" in nachher_text, (
        "Filter zu breit: der zweite Termin ist mit verschwunden"
    )
    assert _termin_uid("ELE-F5") not in nachher_text, (
        "iCal-Feed enthaelt den geloeschten Termin (UID)"
    )

    _zurueck()
    _slug, wieder_text = _ical_inhalt(KALENDER_SLUG)
    assert _termin_uid("ELE-F5") in wieder_text


# ── Website (JSON): echter Abruf ────────────────────────────────────────────


def test_website_termine_enthalten_geloeschten_termin_nicht(patched_db, welt):
    """``oeffentlich_daten.termine`` — der echte Leseaufruf der Website."""
    from diakronos_app.website import oeffentlich_daten as daten

    vorher = daten.termine(welt, kalender=[KALENDER_SLUG])
    titel_vorher = {t["titel"] for t in vorher}
    assert {"Gottesdienst", "Jugendgottesdienst"} <= titel_vorher, titel_vorher

    _in_papierkorb()
    nachher = daten.termine(welt, kalender=[KALENDER_SLUG])
    titel_nachher = {t["titel"] for t in nachher}
    assert "Gottesdienst" not in titel_nachher, "Website zeigt einen geloeschten Termin"
    assert "Jugendgottesdienst" in titel_nachher, "Filter zu breit"

    _zurueck()
    wieder = daten.termine(welt, kalender=[KALENDER_SLUG])
    assert "Gottesdienst" in {t["titel"] for t in wieder}
