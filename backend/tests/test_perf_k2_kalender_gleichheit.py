"""PERF-K2 — Ergebnisgleichheit: derselbe Kalender vor und nach dem Umbau.

Der Test haelt die ANTWORT fest, nicht die Zahl der Abfragen. Er laeuft mit
dem echten Endpunkt (`get_calendar_events`) gegen die echte Datenbank und
vergleicht fuer mehrere Nutzer

  * die volle Terminliste (Reihenfolge, alle Felder inkl. `extendedProps`), und
  * die Kalenderliste (`get_accessible_calendars`: Rechtefelder je Kalender)

ZWISCHEN zwei Betriebsarten desselben Codes: einmal mit eingeschaltetem
Vorabladen (`rechte.vorladen.kalender_rechte_vorladen`, wie im Betrieb unter
`merkungsrahmen`) und einmal ohne (jedes Vorabladen abgeschaltet, jede
Rechtefrage rechnet frisch). Das Vorabladen ist die einzige neue Stelle, die
Antworten beeinflussen koennte — deshalb genau dieser Vergleich.

Zusaetzlich steht hier die OBERGRENZE der Abfragen (PERF-K2), mit derselben
Welt wie `test_perf_k1_kalender_abfragen.py`.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren/Registrierung
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
from diakronos_app.models.kronos import Element, Kalender
from diakronos_app.models.rechte import (
    RechteFreigabe,
    RechteGruppenrolle,
    RechteModul,
    RechteObjekt,
)

# Obergrenze fuer EINE Monatsansicht (FullCalendar-Fenster, 6 Wochen) mit
# 10 Kalendern und 312 Terminen. Ist-Werte (Vorbau-Image,
# `tests/perf_k2_rollen.py`), PERF-K2 R1 nach dem Review:
#
#         Moderator edit/view 79/79   Mitglied edit/view 99/99
#         Admin edit/view 29/29        Gast 84/84 (kein Termin sichtbar)
#
# (R0: 440/388 Moderator, 533/531 Mitglied, 414/364 Admin, 82 Gast.)
# Schlechteste Szene 99 Abfragen. Darauf 30 % Luft -> 129; der Test nimmt
# 140, damit auch eine etwas schwerere Testwelt nicht sofort reisst.
# Zum Vergleich: PERF-K1 hatte als Grenze 40 000 bei ~440 Abfragen je Aufruf,
# der Befund davor 110 803.
HOECHSTENS_ABFRAGEN = 140

# ── Testwelt: Rollen, Kalender und die Rechte-Sonderfaelle (SOLL 2) ─────────
NUTZER = (
    "perf00@example.org",      # HV der Gruppe GR-P (Moderator)
    "perf05@example.org",      # Mitglied
    "perf06@example.org",      # GL der Untergruppe UG-P
    "perf07@example.org",      # Einzelfreigabe (nur lesen)
    "perf08@example.org",      # deaktiviert (User.enabled = False), mit Freigabe
    "perf09@example.org",      # Login MIT User-Zeile, aber OHNE Mitglied-Zeile
    "perf40@example.org",      # Systemrolle kalender_moderation
    "gast@example.org",        # angemeldet, kein Mitglied
)
WAISE, KALENDER, ALTE_KALENDER = "KAL-WAISE", [], []
SERIEN_KALENDER = [f"KAL-P{i}" for i in range(10)]   # tragen die Termine


@pytest.fixture()
def rechtewelt(patched_db):
    """10 Kalender, 50 Nutzer, 312 Termine (240 frei + 6 Serien x 12).

    Wie in `test_perf_k1_kalender_abfragen.py`: die Fixture COMMITTET, weil der
    Endpunkt ueber eigene Sitzungen liest (`lesesitzung`, `get_value`).

    PERF-K2 R1 (SOLL 2): die Welt ist um die Rechte-Sonderfaelle erweitert,
    damit der Gleichheitstest ALLE Wege sieht — Untergruppe mit GL, geloeschte
    Gruppe, Modul aus, Gemeinde-Kalender ohne Gruppe (oeffentlich/nicht),
    Einzelfreigabe an eine Person, Kalenderadministrator als Systemrolle,
    deaktivierter Nutzer mit Freigabe, Login MIT User-Zeile aber OHNE
    Mitglied-Zeile, nicht existierender Kalender und ein verwaister
    Rechte-Eintrag ohne Kalender-Zeile (entsteht in `delete_kalender`, wenn
    die Kalender-Zeile weg ist, `entferne_objekt` aber scheitert).
    """
    sess = patched_db()

    nutzer = [User(name=f"perf{i:02d}@example.org", email=f"perf{i:02d}@example.org",
                   full_name=f"Person {i:02d}", enabled=True,
                   user_type="System User") for i in range(50)]
    sess.add_all(nutzer)
    sess.commit()
    sess.add_all([
        HasRole(name=f"HR-P{i}", parent=n.name, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1) for i, n in enumerate(nutzer)
    ])
    sess.add(Gruppe(name="GR-P", gruppenname="Gemeinde", docstatus=0, idx=0))
    sess.flush()
    mitglieder = [
        Mitglied(name=f"MIT-P{i:02d}", vorname="Person", nachname=f"{i:02d}",
                 email=n.email, user=n.name, status="Aktiv", ausgeschlossen=0,
                 docstatus=0, idx=i)
        for i, n in enumerate(nutzer)
    ]
    sess.add_all(mitglieder)
    sess.flush()
    gruppenmitgliedschaften = [
        Gruppenmitgliedschaft(name=f"GM-P{i:02d}", parent="GR-P", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=m.name, status="Aktiv",
                              docstatus=0, idx=i)
        for i, m in enumerate(mitglieder) if i != 9   # perf09 OHNE Mitglied
    ]
    sess.add_all(gruppenmitgliedschaften)
    sess.flush()
    sess.add(RechteGruppenrolle(gruppe="GR-P", untergruppe=None,
                                benutzer=nutzer[0].name, rolle="HV"))
    sess.add(RechteModul(gruppe="GR-P", modul="kalender"))
    sess.flush()

    kalender = [
        Kalender(name=f"KAL-P{i}", calendar_name=f"Kalender {i}",
                 calendar_color=f"#3366{i:02d}", selbstverwaltet=(i % 3 == 0),
                 docstatus=0, idx=i)
        for i in range(10)
    ]
    sess.add_all(kalender)
    sess.flush()
    sess.add_all([
        RechteObjekt(typ="kalender", objekt=k.name, gruppe="GR-P",
                     gemeinde_status="aktiv", gruppe_status="aktiv")
        for k in kalender
    ])
    sess.flush()
    sess.add_all([
        RechteFreigabe(typ="kalender", objekt=k.name, gruppe="GR-P",
                       lesen=True, schreiben=True, moderieren=(i < 4))
        for i, k in enumerate(kalender)
    ])
    sess.flush()

    elemente = []
    start = datetime(2026, 11, 1, 9, 0)
    for i in range(240):
        s = start + timedelta(days=i % 29, hours=(i % 8))
        elemente.append(Element(
            name=f"EL-P{i:03d}", element_name=f"Termin {i}",
            element_calendar=f"KAL-P{i % 10}", element_start=s,
            element_end=s + timedelta(hours=1), all_day=(i % 7 == 0),
            status=("Festgelegt" if i % 5 else "Vorschlag"),
            owner=nutzer[i % 50].name, repeat_this_event=0, docstatus=0, idx=i))
    for k in range(6):
        for j in range(12):
            s = datetime(2026, 10, 5, 18, 0) + timedelta(days=7 * j)
            elemente.append(Element(
                name=f"EL-PS{k}-{j:02d}", element_name=f"Serie {k} Folge {j}",
                element_calendar=f"KAL-P{k}", element_start=s,
                element_end=s + timedelta(hours=2), all_day=False,
                status="Festgelegt", series_id=f"SER-P{k}",
                owner=nutzer[k].name, repeat_this_event=0, docstatus=0,
                idx=1000 + k * 20 + j))
    sess.add_all(elemente)

    # Zusatz-Ressourcen und Mitarbeiter an je einem Termin — die Nachlade-Wege
    # (`_attach_zusaetzliche_ressourcen`, `_attach_mitarbeiter`) muessen
    # mitverglichen werden, sonst deckte der Gleichheitstest sie nicht ab.
    from diakronos_app.models.kronos import ElementMitarbeiter, ElementRessource, Ressource

    sess.add(Ressource(name="RES-P0", ressource_name="Raum P0", docstatus=0, idx=0))
    sess.flush()
    sess.add(ElementRessource(name="ER-P0", parent="EL-P000", parenttype="Element",
                              parentfield="zusaetzliche_ressourcen", ressource="RES-P0",
                              freitext_ressource="", status="Bestaetigt", notiz="Test",
                              docstatus=0, idx=0))
    sess.add(ElementMitarbeiter(name="EM-P0", parent="EL-P000", parenttype="Element",
                                parentfield="mitarbeiter", mitglied=mitglieder[3].name,
                                dienstrolle="Technik", bestaetigt=1, notiz="",
                                docstatus=0, idx=0))
    sess.flush()

    # ── SOLL 2: Rechte-Sonderfaelle ────────────────────────────────────────
    from diakronos_app.models.core import HasRole as _HasRole
    from diakronos_app.models.diakonos import Untergruppe, Untergruppenmitgliedschaft

    # GL der Untergruppe UG-P (und Mitglied der Gruppe GR-P)
    sess.add(Untergruppe(name="UG-P", gruppe="GR-P", untergruppenname="Untergruppe P",
                         docstatus=0, idx=0))
    sess.flush()
    sess.add(Untergruppenmitgliedschaft(name="UM-P6", parent="UG-P",
                                        parenttype="Untergruppe", parentfield="mitglieder",
                                        mitglied="MIT-P06", status="Aktiv",
                                        docstatus=0, idx=0))
    sess.add(RechteGruppenrolle(gruppe="GR-P", untergruppe="UG-P",
                                benutzer="perf06@example.org", rolle="GL"))
    # Geloeschte Gruppe: sie verleiht KEIN Recht mehr.
    sess.add(Gruppe(name="GR-TOT", gruppenname="Geloescht", docstatus=0, idx=1,
                    geloescht_am=datetime(2026, 1, 1, 0, 0)))
    sess.add(Gruppenmitgliedschaft(name="GM-TOT", parent="GR-TOT", parenttype="Gruppe",
                                   parentfield="mitglieder", mitglied="MIT-P05",
                                   status="Aktiv", docstatus=0, idx=0))
    # Systemrolle Kalender-Moderation (Kalenderadministrator ohne Admin-Konto)
    sess.add(_HasRole(name="HR-P40-moderation", parent="perf40@example.org", parenttype="User",
                      parentfield="roles", role="Kalenderadministrator", docstatus=0, idx=2))
    # deaktivierter Nutzer mit Freigabe
    sess.flush()

    sess.add_all([
        # Untergruppen-Kalender (Gruppe + Untergruppe, Modul an)
        Kalender(name="KAL-UG", calendar_name="UG-Kalender", calendar_color="#1000aa",
                 docstatus=0, idx=20),
        # Kalender einer GELOESCHTEN Gruppe
        Kalender(name="KAL-TOT", calendar_name="Toter Kalender", calendar_color="#aa0000",
                 docstatus=0, idx=21),
        # Gemeinde-Kalender OHNE Gruppe, gemeindeweit oeffentlich
        Kalender(name="KAL-GEM", calendar_name="Gemeinde oeffentlich",
                 calendar_color="#00aa00", docstatus=0, idx=22),
        # Gemeinde-Kalender OHNE Gruppe, NICHT oeffentlich
        Kalender(name="KAL-GEM-AUS", calendar_name="Gemeinde intern",
                 calendar_color="#00aaaa", docstatus=0, idx=23),
        # Kalender in einer Gruppe, deren Modul AUS ist
        Kalender(name="KAL-OHNE-MODUL", calendar_name="Ohne Modul",
                 calendar_color="#aaaa00", docstatus=0, idx=24),
    ])
    sess.add(Gruppe(name="GR-OHNE", gruppenname="Ohne Modul", docstatus=0, idx=2))
    sess.flush()
    sess.add_all([
        RechteObjekt(typ="kalender", objekt="KAL-UG", gruppe="GR-P",
                     untergruppe="UG-P", gemeinde_status="aus", gruppe_status="aus"),
        RechteObjekt(typ="kalender", objekt="KAL-TOT", gruppe="GR-TOT",
                     gemeinde_status="aus", gruppe_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="KAL-GEM", gruppe=None,
                     gemeinde_status="aktiv", gruppe_status=None),
        RechteObjekt(typ="kalender", objekt="KAL-GEM-AUS", gruppe=None,
                     gemeinde_status="aus", gruppe_status=None),
        RechteObjekt(typ="kalender", objekt="KAL-OHNE-MODUL", gruppe="GR-OHNE",
                     gemeinde_status="aus", gruppe_status="aktiv"),
        RechteFreigabe(typ="kalender", objekt="KAL-UG", gruppe="GR-P",
                       lesen=True, schreiben=True, moderieren=False),
        RechteFreigabe(typ="kalender", objekt="KAL-TOT", gruppe="GR-TOT",
                       lesen=True, schreiben=True, moderieren=True),
        # Einzelfreigabe an EINE Person (perf07) und an den deaktivierten (perf08)
        RechteFreigabe(typ="kalender", objekt="KAL-GEM-AUS", benutzer="perf07@example.org",
                       lesen=True, schreiben=False, moderieren=False),
        RechteFreigabe(typ="kalender", objekt="KAL-GEM-AUS", benutzer="perf08@example.org",
                       lesen=True, schreiben=True, moderieren=False),
        RechteFreigabe(typ="kalender", objekt="KAL-OHNE-MODUL", gruppe="GR-P",
                       lesen=True, schreiben=True, moderieren=False),
        # VERWAISTER Rechte-Eintrag: Objekt ohne Kalender-Zeile
        RechteObjekt(typ="kalender", objekt=WAISE, gruppe="GR-P",
                     gemeinde_status="aktiv", gruppe_status="aktiv"),
        RechteFreigabe(typ="kalender", objekt=WAISE, gruppe="GR-P",
                       lesen=True, schreiben=True, moderieren=True),
    ])
    # Modul "kalender" fuer GR-P an, GR-TOT aus (geloescht), GR-OHNE aus (nie gesetzt)
    # -> GR-OHNE hat bewusst KEINEN RechteModul-Eintrag.
    sess.flush()
    _deaktiviert = sess.query(User).filter(User.name == "perf08@example.org").one()
    _deaktiviert.enabled = False
    # Login MIT User-Zeile, aber OHNE Mitglied-Zeile: perf09 ist schon als
    # Nutzer/User-Zeile angelegt (Index 9) — nur sein Mitglied fehlt oben.
    _ohne = sess.query(User).filter(User.name == "perf09@example.org").one()
    assert _ohne.enabled is True
    sess.commit()

    KALENDER[:] = SERIEN_KALENDER + ["KAL-UG", "KAL-TOT", "KAL-GEM",
                                    "KAL-GEM-AUS", "KAL-OHNE-MODUL", WAISE]
    return sess


def _welt_vergleich(rechtewelt, nutzer: str, view_mode: str):
    """(Kalenderliste, Terminliste) eines Nutzers — mit / ohne Vorabladen."""
    import diakronos_app.rechte.vorladen as V
    from diakronos_app.api.kronos import permissions as P
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(nutzer)
    filter_json = json.dumps([f"KAL-P{i}" for i in range(10)])

    def _lauf():
        with merkungsrahmen():
            with als_aktuelle_sitzung(rechtewelt):
                kalender = P.get_accessible_calendars()
                termine = get_calendar_events("2026-10-26", "2026-12-06",
                                              filter_json, view_mode)
        return kalender, termine

    # OHNE Vorabladen: die eine neue Stelle abschalten, alles andere gleich
    # lassen. Der Merkungsrahmen bleibt — so unterscheidet der Vergleich
    # genau die eine Aenderung, nicht den ganzen Merker.
    gesichert = V.kalender_rechte_vorladen
    V.kalender_rechte_vorladen = lambda *a, **k: None
    try:
        ohne = _lauf()
    finally:
        V.kalender_rechte_vorladen = gesichert
    mit = _lauf()
    return ohne, mit


@pytest.mark.parametrize("nutzer", NUTZER)
@pytest.mark.parametrize("view_mode", ["edit", "view"])
def test_perf_k2_vorabladen_aendert_keine_antwort(rechtewelt, nutzer, view_mode):
    """Dieselbe Antwort mit und ohne Vorabladen — Feld fuer Feld.

    Alle Rollen der Testwelt: HV (Moderator), Mitglied, GL der Untergruppe,
    Einzelfreigabe, deaktiviert, Login ohne Mitglied, Kalenderadministrator,
    Gast ohne Mitglied.
    """
    ohne, mit = _welt_vergleich(rechtewelt, nutzer, view_mode)
    assert mit == ohne


def test_perf_k2_gast_und_admin_gleich(rechtewelt):
    """Auch die Raender (Gast ohne Mitglied, Administrator) bleiben gleich."""
    for nutzer in ("gast@example.org", "Administrator", "perf09@example.org"):
        ohne, mit = _welt_vergleich(rechtewelt, nutzer, "edit")
        assert mit == ohne


def _alte_auswertung(calendar_name) -> dict:
    """Die PERF-K2 ABGELOESTE Rechnung: Eintrag aus der ganzen Liste ziehen.

    Wortgleich das, was `moderation.ist_moderator` / `schreibt_direkt` vor dem
    Umbau taten — nur in Python nachgebaut, damit der alte Stand im Test
    nachweisbar bleibt:
        any(c["name"] == name and c.get(feld) for c in get_accessible_calendars())
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    for c in get_accessible_calendars():
        if c["name"] == calendar_name:
            return c
    return {}


@pytest.mark.parametrize("nutzer", (*NUTZER, "perf10@example.org", "Administrator"))
def test_perf_k2_einzelabfrage_gleich_listenauswertung(rechtewelt, nutzer):
    """`moderation.ist_moderator` / `schreibt_direkt` gegen die alte Rechnung.

    Beide fragen jetzt NUR ihren einen Kalender (`_kalender_eintrag`) statt
    die ganze Liste je Frage neu aufzubauen. Entscheidend ist, dass jedes
    Feld dasselbe sagt wie der Eintrag aus `get_accessible_calendars` — und
    dass ein NICHT sichtbarer Kalender weiterhin `False` liefert.
    """
    from diakronos_app.api.kronos.moderation import ist_moderator, schreibt_direkt
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(nutzer)
    with merkungsrahmen(), als_aktuelle_sitzung(rechtewelt):
        for name in KALENDER:
            alt = _alte_auswertung(name)
            assert ist_moderator(name) == bool(alt.get("is_moderator")), (nutzer, name)
            assert schreibt_direkt(name) == bool(alt.get("direkt")), (nutzer, name)
            assert schreibt_direkt(name, aenderung=True) == bool(alt.get("aendert_direkt")), (nutzer, name)
        # Ein Kalender, den es nicht gibt, und ein leerer Name: nie moderierbar
        # — auch nicht fuer den Administrator. Die alte Rechnung las die
        # Kalenderliste, und dort steht nur, was es gibt.
        assert ist_moderator("KAL-GIBTSNICHT") is False, nutzer
        assert schreibt_direkt("KAL-GIBTSNICHT") is False, nutzer
        assert schreibt_direkt("KAL-GIBTSNICHT", aenderung=True) is False, nutzer
        assert _alte_auswertung("KAL-GIBTSNICHT") == {}
        assert ist_moderator("") is False
        assert ist_moderator(None) is False
        assert schreibt_direkt(None) is False


def test_perf_k2_hat_leserecht_gleich_listenauswertung(rechtewelt):
    """`permissions.hat_leserecht` gegen die alte `any(... in get_accessible_calendars)`.

    Die Funktion fragt jetzt den Kern direkt. Sie wird aus Listen aufgerufen
    (Buchungsanfragen je Termin) — dort war das Neuaufbauen der ganzen Liste
    der Wiederholer. Dieselbe Antwort fuer jeden Kalender und jeden Nutzer —
    auch fuer einen Namen, den es nicht gibt: der Kern antwortet dem Admin
    zwar JA, die ALT Liste enthielt den Kalender aber gar nicht, und diese
    Vorbedingung gilt weiter (auch fuer einen verwaisten Rechte-Eintrag ohne
    Kalender-Zeile, `KAL-WAISE`).
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars, hat_leserecht
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    for nutzer in (NUTZER + ("Administrator",)):
        set_user(nutzer)
        with merkungsrahmen(), als_aktuelle_sitzung(rechtewelt):
            sichtbar = {c["name"] for c in get_accessible_calendars()}
            for name in (*SERIEN_KALENDER, f"KAL-{WAISE}", "KAL-GIBTSNICHT"):
                assert hat_leserecht(name) == (name in sichtbar), (nutzer, name)
            assert hat_leserecht("KAL-GIBTSNICHT") is False, nutzer
            assert hat_leserecht(None) is False
            assert hat_leserecht("") is False


def test_perf_k2_unbekannt_und_verwaist_bleiben_gesperrt(rechtewelt):
    """R1/MUSS 1 als eigener Waechter: nicht existierende Kalender sind gesperrt.

    Der Rechte-Kern antwortet dem Administrator JA, BEVOR er das Objekt prueft
    (`_darf_roh`), und ein verwaister Rechte-Eintrag (Objekt ohne
    Kalender-Zeile, entsteht in `delete_kalender`) traegt volle Freigaben. Die
    alte Liste (`get_accessible_calendars`) enthielt beides NIE — deshalb
    muessen Existenzpruefung und Einzelfragen hier ueberall NEIN sagen, auch
    fuer Admin, HV und GL. Ohne diese Zusage waere der Gleichheitstest blind:
    bei falscher Existenzantwort sind BEIDE Laeufe gleich falsch.
    """
    from diakronos_app.api.kronos.moderation import ist_moderator, schreibt_direkt
    from diakronos_app.api.kronos.permissions import get_accessible_calendars, hat_leserecht
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    for nutzer in (*NUTZER, "Administrator"):
        for name in ("KAL-GIBTSNICHT", f"KAL-{WAISE}"):
            set_user(nutzer)
            with merkungsrahmen(), als_aktuelle_sitzung(rechtewelt):
                sichtbar = {c["name"] for c in get_accessible_calendars()}
                assert name not in sichtbar, (nutzer, name)
                assert hat_leserecht(name) is False, (nutzer, name)
                assert ist_moderator(name) is False, (nutzer, name)
                assert schreibt_direkt(name) is False, (nutzer, name)
                assert schreibt_direkt(name, aenderung=True) is False, (nutzer, name)


def test_perf_k2_vorrat_gleich_einzelfrage(rechtewelt):
    """SOLL 2: der VORRAT selbst stimmt mit der frischen Einzelfrage ueberein.

    Je Rolle x Kalender: was `kalender_rechte_vorladen` in den Merker legt,
    muss Feld fuer Feld das sein, was `darf` / `pruefstufen` /
    `moderationsstufen` ohne Merker rechnen. Der Gleichheitstest oben
    vergleicht die ENDPUNKTE (Liste + Termine) und wuerde einen falschen
    Vorrat nur dann sehen, wenn er sich dort auswirkt — hier steht der
    Vergleich direkt an der neuen Stelle.

    PERF-K2b: Geprueft wird ZWEIMAL — mit der Liste davor und ohne. „Liste
    zuerst“ fiel R1 nicht auf (dort war der Vorrat selbst richtig, falsch war
    der Nachtrag AUS der Liste); „Einzelfrage zuerst“ ist der Weg, der den
    Merker vergiftete. Beide Reihenfolgen muessen die frische Antwort liefern.
    """
    from diakronos_app import rechte as R
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    aktionen = (R.LESEN, R.SCHREIBEN, R.VORSCHLAGEN, R.MODERIEREN, R.VERWALTEN)

    def _ist(nutzer, name):
        return (
            tuple(bool(R.darf(nutzer, a, "kalender", name)) for a in aktionen),
            tuple(R.pruefstufen(nutzer, "kalender", name)),
            tuple(R.moderationsstufen(nutzer, "kalender", name)),
        )

    for nutzer in (*NUTZER, "Administrator"):
        set_user(nutzer)
        with als_aktuelle_sitzung(rechtewelt):
            # frisch, OHNE Merkungsrahmen
            frisch = {name: _ist(nutzer, name) for name in KALENDER}
        for reihenfolge in ("vorladen", "liste_dann_vorladen"):
            with merkungsrahmen():
                if reihenfolge == "liste_dann_vorladen":
                    with als_aktuelle_sitzung(rechtewelt):
                        get_accessible_calendars()
                kalender_rechte_vorladen(nutzer, KALENDER)
                with als_aktuelle_sitzung(rechtewelt):
                    for name in KALENDER:
                        ist = _ist(nutzer, name)
                        assert ist == frisch[name], (reihenfolge, nutzer, name, ist, frisch[name])


def _abfragen(rechtewelt, nutzer: str, view_mode: str, engine) -> tuple[int, int]:
    from diakronos_app.api.kronos.calendar_get import get_calendar_events
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    zaehler = {"n": 0}

    def _zaehle_sql(conn, cursor, statement, parameters, context, executemany):
        zaehler["n"] += 1

    set_user(nutzer)
    event.listen(engine, "before_cursor_execute", _zaehle_sql)
    try:
        with merkungsrahmen():
            with als_aktuelle_sitzung(rechtewelt):
                termine = get_calendar_events(
                    "2026-10-26", "2026-12-06",
                    json.dumps([f"KAL-P{i}" for i in range(10)]), view_mode)
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle_sql)
    return len(termine), zaehler["n"]


def test_perf_k2_monatsansicht_unter_der_abfragegrenze(rechtewelt, engine):
    """PERF-K2: eine Monatsansicht kostet feste, kleine Zahl von Abfragen.

    VORHER (PERF-K1, gleicher Aufbau): 440 Abfragen im Bearbeitungsmodus —
    davon 276 Einzelabfragen des Kalender-Anzeigenamens (eine je Termin).
    Der Test ist vor der Behebung rot (440 > 160) und danach gruen.
    """
    termine, abfragen = _abfragen(rechtewelt, "perf00@example.org", "edit", engine)
    assert termine >= 200, termine
    assert abfragen < HOECHSTENS_ABFRAGEN, (
        f"{abfragen} SQL-Abfragen fuer eine Monatsansicht "
        f"(Obergrenze {HOECHSTENS_ABFRAGEN}; PERF-K1: 440, Befund davor: 110 803)")


def test_perf_k2_lesemodus_unter_der_abfragegrenze(rechtewelt, engine):
    termine, abfragen = _abfragen(rechtewelt, "perf00@example.org", "view", engine)
    assert termine >= 100, termine
    assert abfragen < HOECHSTENS_ABFRAGEN, (
        f"{abfragen} SQL-Abfragen im Lesemodus "
        f"(Obergrenze {HOECHSTENS_ABFRAGEN}; PERF-K1: 388)")


def test_perf_k2_zahl_haengt_nicht_an_der_terminzahl(rechtewelt, engine):
    """GLEICHHEIT, nicht nur eine Schranke: doppelt so viele Termine, gleiche Zahl.

    Ohne diese Zusage waere die Obergrenze nur eine Zahl, die man mit der
    naechsten Datenmenge wieder anheben muesste.
    """
    from diakronos_app.models.kronos import Element

    _, klein = _abfragen(rechtewelt, "perf00@example.org", "edit", engine)
    neu = []
    for i in range(240):
        s = datetime(2026, 11, 2, 9, 0) + timedelta(days=i % 27, hours=(i % 8))
        neu.append(Element(
            name=f"EL-Q{i:03d}", element_name=f"Zusatz {i}",
            element_calendar=f"KAL-P{i % 10}", element_start=s,
            element_end=s + timedelta(hours=1), all_day=False,
            status="Festgelegt", owner="perf10@example.org",
            repeat_this_event=0, docstatus=0, idx=5000 + i))
    rechtewelt.add_all(neu)
    rechtewelt.commit()
    termine, gross = _abfragen(rechtewelt, "perf00@example.org", "edit", engine)
    assert termine >= 400, termine
    assert gross == klein, f"{gross} statt {klein} Abfragen bei doppelter Terminzahl"
