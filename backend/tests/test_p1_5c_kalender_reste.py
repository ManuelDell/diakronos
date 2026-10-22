"""P1-5c — Kalender/CalDAV-Restpunkte (Basis: main).

Deckt die Restbefunde aus drei unabhaengigen Reviews verhaltensbasiert ab:

  (5) Serienanzahl (`calendar_get._attach_serien_anzahl`) zaehlt nur Termine,
      die der Nutzer auch sehen darf — dieselben Kalender- und Statusfilter wie
      die Terminliste (Review P1-3, K1).
  (6) `series._series_datum` lehnt ungueltige Datumsformate mit 417 ab statt
      still nach zehn Zeichen abzuschneiden (Review P1-3, K2).
  (7) Kalenderwechsel verlangt das Moderationsrecht an Quell- UND Zielkalender
      (Review P1-2, W-1) — wie die Freigabe eines Vorschlags.
  (8) `moderation.trenne_aenderung`: ein `None` bei Kind-Tabellen heisst
      „unveraendert" und leert die Tabelle nicht (Review P1-2, N2).

Die CalDAV-Punkte (1)-(3) liegen in `test_p1_6_caldav_xml.py`; der
Ganztaegig-Fall (4) im Node-Test `frontend/tests/p1-3-kalender-fenster.test.mjs`.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import Element, Kalender, KalenderModerator

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren laufen beim Import

MODERATOR = "moderator@example.org"
SCHREIBER = "schreiber@example.org"
KAL_QUELLE = "KAL-QUELLE"
KAL_ZIEL = "KAL-ZIEL"
KAL_FREMD = "KAL-FREMD"   # fuer SCHREIBER gar nicht lesbar


@pytest.fixture()
def welt(patched_db):
    """Drei Kalender: SCHREIBER schreibt auf QUELLE und ZIEL, moderiert nur ZIEL.

    MODERATOR moderiert QUELLE und ZIEL. KAL_FREMD ist fuer SCHREIBER weder
    les- noch schreibbar (fuer den Serien-Anzahl-Test).
    """
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Schreiber", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL_QUELLE, calendar_name="Quelle", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_ZIEL, calendar_name="Ziel", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_FREMD, calendar_name="Fremd", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        # SCHREIBER darf auf QUELLE und ZIEL schreiben …
        UserRole(name="UR-1", parent=KAL_QUELLE, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-2", parent=KAL_ZIEL, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        # … MODERATOR darf ueberall schreiben (fuer die Gegenproben).
        UserRole(name="UR-3", parent=KAL_QUELLE, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-4", parent=KAL_ZIEL, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        # MODERATOR darf die QUELLE auch lesen (fuer die Serienanzahl).
        UserRole(name="UR-5", parent=KAL_QUELLE, parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        # SCHREIBER moderiert NUR das ZIEL; MODERATOR beide.
        KalenderModerator(name="KM-1", parent=KAL_ZIEL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=SCHREIBER,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-2", parent=KAL_QUELLE, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-3", parent=KAL_ZIEL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_user():
    yield
    set_user("Administrator")


def _als(user):
    set_user(user)


def _termin(sess, name, calendar=KAL_QUELLE, status="Festgelegt", series_id="", **felder):
    el = Element(
        name=name, element_name=felder.pop("element_name", "Chorprobe"),
        element_calendar=calendar,
        element_start=felder.pop("element_start", datetime(2026, 3, 1, 10)),
        element_end=felder.pop("element_end", datetime(2026, 3, 1, 12)),
        all_day=0, status=status, series_id=series_id, docstatus=0, idx=0,
        **felder,
    )
    sess.add(el)
    sess.commit()
    return el


# ═══════════════════════════════════════════════════════════════════════════
# (7) Kalenderwechsel verlangt Moderationsrecht an Quelle UND Ziel
# ═══════════════════════════════════════════════════════════════════════════

def test_wechsel_quelle_moderator_ohne_zielmoderation_wartet(welt):
    """ROT vorher: Wer die QUELLE moderiert, verschob sofort in ein Ziel, das er
    NICHT moderiert — die Freigabe eines Vorschlags verlangt aber Zielrecht.
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _termin(sess, "EL-P15C-W1", calendar=KAL_QUELLE)
    _als(MODERATOR)  # moderiert die QUELLE und (hier absichtlich) nicht das ZIEL
    sess.query(KalenderModerator).filter(
        KalenderModerator.name == "KM-3"
    ).delete()
    sess.commit()

    res = event_crud.save_event(
        "EL-P15C-W1", "Chorprobe", "2026-03-02 10:00:00", "2026-03-02 12:00:00",
        KAL_ZIEL,
    )
    assert res.get("aenderung_wartet") is True, "Wechsel wirkte ohne Zielmoderation"
    assert sess.get(Element, "EL-P15C-W1").element_calendar == KAL_QUELLE


def test_wechsel_mit_moderation_an_beiden_kalendern_wirkt_sofort(welt):
    """Gegenprobe: MODERATOR moderiert QUELLE und ZIEL -> sofort."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _termin(sess, "EL-P15C-W2", calendar=KAL_QUELLE)
    _als(MODERATOR)
    res = event_crud.save_event(
        "EL-P15C-W2", "Chorprobe", "2026-03-02 10:00:00", "2026-03-02 12:00:00",
        KAL_ZIEL,
    )
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-P15C-W2").element_calendar == KAL_ZIEL


def test_update_event_verlangt_ebenfalls_zielmoderation(welt):
    """Der zweite Weg (`update_event`) folgt derselben Regel."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _termin(sess, "EL-P15C-W3", calendar=KAL_QUELLE)
    _als(MODERATOR)
    sess.query(KalenderModerator).filter(
        KalenderModerator.name == "KM-3"
    ).delete()
    sess.commit()

    res = event_crud.update_event("EL-P15C-W3", element_calendar=KAL_ZIEL)
    assert res.get("aenderung_wartet") is True
    assert sess.get(Element, "EL-P15C-W3").element_calendar == KAL_QUELLE


def test_helfer_kalenderwechsel_wirkt_sofort(welt):
    """Die zentrale Regel direkt: kein Wechsel -> Quellrecht entscheidet."""
    from diakronos_app.api.kronos import moderation

    _als(MODERATOR)
    # Kein Wechsel: das Quellrecht genuegt.
    assert moderation.kalenderwechsel_wirkt_sofort(KAL_QUELLE, None, True) is True
    assert moderation.kalenderwechsel_wirkt_sofort(KAL_QUELLE, KAL_QUELLE, True) is True
    # Ohne Quellrecht nie.
    assert moderation.kalenderwechsel_wirkt_sofort(KAL_QUELLE, KAL_ZIEL, False) is False


# ═══════════════════════════════════════════════════════════════════════════
# (6) _series_datum lehnt ungueltige Formate ab (417)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ungueltig", [
    "2026-11-08xyz",   # Muell nach dem zehnten Zeichen — wurde still abgeschnitten
    "20261108",        # Basisformat (Python >= 3.11) — kein ISO-Tag mit Bindestrichen
    "08.11.2026",      # deutsches Datum
    "2026-13-01",      # Monat 13
    "2026-02-30",      # Tag ausserhalb des Monats
    "morgen",
])
def test_series_datum_lehnt_ungueltiges_ab(welt, ungueltig):
    """ROT vorher: `text[:10]` + `date.fromisoformat` akzeptierten
    `2026-11-08xyz` (still gekuerzt) und `20261108` (Basisformat). Beides lief
    bis in die SQL-Abfrage.
    """
    from diakronos_app.api.kronos import series

    sess = welt
    _termin(sess, "EL-P15C-D1", series_id="SER-D1")
    _als(MODERATOR)
    with pytest.raises(ValidationError):
        series.delete_future_series_events("SER-D1", ungueltig)


def test_series_datum_akzeptiert_tag_und_zeitstempel(welt):
    """Gegenprobe: der reine ISO-Tag und ein Zeitstempel bleiben erlaubt."""
    from diakronos_app.api.kronos import series

    sess = welt
    _termin(sess, "EL-P15C-D2", series_id="SER-D2",
            element_start=datetime(2026, 11, 10, 19))
    _als(MODERATOR)
    res = series.delete_future_series_events("SER-D2", "2026-11-08")
    assert res["success"] is True

    _termin(sess, "EL-P15C-D3", series_id="SER-D3",
            element_start=datetime(2026, 11, 10, 19))
    res2 = series.delete_future_series_events("SER-D3", "2026-11-08 10:00:00")
    assert res2["success"] is True


# ═══════════════════════════════════════════════════════════════════════════
# (8) trenne_aenderung: None bei Kind-Tabellen = unveraendert
# ═══════════════════════════════════════════════════════════════════════════

def test_trenne_aenderung_none_kind_tabelle_bleibt_unveraendert(welt):
    """ROT vorher: ein `None` fiel in den SOFORT-Zweig und leerte die
    Kind-Tabelle (`wende_kind_tabellen_an` schreibt None = leer).
    """
    from diakronos_app.api.kronos import moderation
    from diakronos_app.frappe_compat.query import get_doc

    sess = welt
    _termin(sess, "EL-P15C-K1", calendar=KAL_ZIEL)
    _als(MODERATOR)
    doc = get_doc("Element", "EL-P15C-K1")
    aufteilung = moderation.trenne_aenderung(
        doc, {"element_name": "Neu"}, ist_mod=True,
        kind_tabellen={"mitarbeiter": None, "zusaetzliche_ressourcen": None},
    )
    assert aufteilung.sofort_kind == {}, "None wurde als Leerung durchgereicht"
    assert aufteilung.vorschlag_kind == {}


def test_trenne_aenderung_leere_liste_leert_weiterhin(welt):
    """Gegenprobe: eine AUSDRUECKLICH gesendete leere Liste ist eine Leerung."""
    from diakronos_app.api.kronos import moderation
    from diakronos_app.frappe_compat.query import get_doc

    sess = welt
    _termin(sess, "EL-P15C-K2", calendar=KAL_ZIEL)
    _als(MODERATOR)
    doc = get_doc("Element", "EL-P15C-K2")
    aufteilung = moderation.trenne_aenderung(
        doc, {"element_name": "Neu"}, ist_mod=True,
        kind_tabellen={"mitarbeiter": [], "zusaetzliche_ressourcen": []},
    )
    assert aufteilung.sofort_kind == {"mitarbeiter": [], "zusaetzliche_ressourcen": []}


def test_update_event_ohne_mitarbeiterfeld_erhaelt_zuordnungen(welt):
    """Ende-zu-Ende: `update_event` ohne `mitarbeiter` laesst die Zeilen stehen."""
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import ElementMitarbeiter

    sess = welt
    _termin(sess, "EL-P15C-K3", calendar=KAL_ZIEL)
    _als(MODERATOR)
    event_crud.update_event(
        "EL-P15C-K3",
        mitarbeiter=[{"mitglied": SCHREIBER, "dienstrolle": "Klavier"}],
    )
    assert sess.query(ElementMitarbeiter).count() == 1
    event_crud.update_event("EL-P15C-K3", element_name="Anderer Titel")
    assert sess.query(ElementMitarbeiter).count() == 1, "Mitarbeiter verloren"


# ═══════════════════════════════════════════════════════════════════════════
# (5) Serienanzahl nur aus lesbaren Kalendern und ohne Vorschlaege
#
# Der Endpunkt wird ueber den compat-Router aufgerufen (echter HTTP-Weg), damit
# die Rechte- und Statusfilter der Terminliste wirklich greifen.
# ═══════════════════════════════════════════════════════════════════════════

KAL_PFAD = "/api/method/diakronos.kronos.api.calendar_get.get_calendar_events"


def _events(client, **body):
    r = client.post(KAL_PFAD, json=body)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def test_serienanzahl_zaehlt_nur_sichtbare_termine(client, welt):
    """ROT vorher: die Zaehlung lief ohne Kalender-/Statusfilter — sie nannte
    auch Termine fremder Kalender und Vorschlaege und verriet so die Groesse
    fremder Serien.
    """
    sess = welt
    # Serie mit drei Terminen: zwei sichtbar (QUELLE, Festgelegt),
    # einer in einem NICHT lesbaren Kalender, einer als Vorschlag.
    _termin(sess, "EL-P15C-S1", calendar=KAL_QUELLE, series_id="SER-S1",
            element_start=datetime(2026, 3, 2, 10), element_end=datetime(2026, 3, 2, 12))
    _termin(sess, "EL-P15C-S2", calendar=KAL_QUELLE, series_id="SER-S1",
            element_start=datetime(2026, 3, 3, 10), element_end=datetime(2026, 3, 3, 12))
    _termin(sess, "EL-P15C-S3", calendar=KAL_FREMD, series_id="SER-S1",
            element_start=datetime(2026, 3, 4, 10), element_end=datetime(2026, 3, 4, 12))
    _termin(sess, "EL-P15C-S4", calendar=KAL_QUELLE, series_id="SER-S1",
            status="Vorschlag",
            element_start=datetime(2026, 3, 5, 10), element_end=datetime(2026, 3, 5, 12))

    _als(MODERATOR)
    events = _events(
        client,
        start_date="2026-03-01", end_date="2026-03-31",
        calendar_filter=json.dumps([KAL_QUELLE]),
        view_mode="view",
    )
    meiner = [e for e in events if e["extendedProps"].get("series_id") == "SER-S1"]
    assert meiner, "Serientermine fehlen in der Antwort"
    # Lesemodus: nur Festgelegt UND nur der lesbare Kalender -> 2.
    assert {e["extendedProps"]["series_count"] for e in meiner} == {2}


def test_serienanzahl_im_bearbeitungsmodus_ohne_fremdkalender(client, welt):
    """Bearbeitungsmodus eines Moderators: Vorschlaege im EIGENEN Kalender
    zaehlen mit, der unlesbare Fremdkalender bleibt aussen vor."""
    sess = welt
    _termin(sess, "EL-P15C-T1", calendar=KAL_QUELLE, series_id="SER-T1",
            element_start=datetime(2026, 3, 2, 10), element_end=datetime(2026, 3, 2, 12))
    _termin(sess, "EL-P15C-T2", calendar=KAL_QUELLE, series_id="SER-T1",
            status="Vorschlag",
            element_start=datetime(2026, 3, 3, 10), element_end=datetime(2026, 3, 3, 12))
    _termin(sess, "EL-P15C-T3", calendar=KAL_FREMD, series_id="SER-T1",
            element_start=datetime(2026, 3, 4, 10), element_end=datetime(2026, 3, 4, 12))

    _als(MODERATOR)
    events = _events(
        client,
        start_date="2026-03-01", end_date="2026-03-31",
        calendar_filter=json.dumps([KAL_QUELLE]),
        view_mode="edit",
    )
    meiner = [e for e in events if e["extendedProps"].get("series_id") == "SER-T1"]
    assert meiner
    assert {e["extendedProps"]["series_count"] for e in meiner} == {2}
