"""P1-2 — Kalender: Datenverlust und Loeschen.

Massgebliche Befunde der Nachtpruefung:

  UXK-R4  Termin bearbeiten (nur Titel aendern) loeschte ALLE eingetragenen
          Mitarbeiter/Dienste des Termins — Datenverlust. Ursache: `save_event`
          ersetzte die Kind-Tabellen immer; der Edit-Dialog sendet sie nicht.
  UXK-R3  „Gesamte Serie loeschen" / „Alle nachfolgenden loeschen" ohne
          Rueckfrage; danach lud der Kalender nicht neu.

Dazu die Nachtrags-Befunde des vorausgehenden Reviews, die zu diesem
Datenverlust-Paket gehoeren:

  N2  `save_event` ohne `zusaetzliche_ressourcen`/`mitarbeiter` loeschte diese
      sofort (auch bei Drag&Drop) — gleiche Ursache wie UXK-R4.
  N1  Moderationsrecht beim Kalenderwechsel wurde am ZIELkalender geprueft.
  N3  `vorschlag_anwenden` verglich den Zielkalender mit der TERMIN-ID.
  N4  Migration: verwaiste Vorschlaege vor FK-Anlage bereinigen.
  N5  Serien-Batch meldete einen verworfenen Status nicht.
  K1  Konfliktpruefung bei der Freigabe fehlte.

Jeder Test war vor dem Patch rot (bzw. der bestehende K2-Test dokumentierte das
alte Verhalten und dreht hier auf Gruen).
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

import diakronos_app.api  # noqa: E402,F401  (registriert die @whitelist-Pfade)

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    ElementAenderung,
    ElementMitarbeiter,
    ElementRessource,
    Kalender,
    KalenderModerator,
    Ressource,
)

MODERATOR = "moderator-p12@example.org"
SCHREIBER = "schreiber-p12@example.org"
KAL_QUELLE = "KAL-P12-QUELLE"
KAL_ZIEL = "KAL-P12-ZIEL"


@pytest.fixture()
def welt(patched_db):
    """Zwei Kalender: SCHREIBER schreibt ueberall, moderiert nur das ZIEL."""
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Schreiber", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-P12-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-P12-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL_QUELLE, calendar_name="Quelle", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_ZIEL, calendar_name="Ziel", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        # SCHREIBER darf auf BEIDEN schreiben …
        UserRole(name="UR-P12-1", parent=KAL_QUELLE, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-P12-2", parent=KAL_ZIEL, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        # … moderiert aber NUR das ZIEL.
        KalenderModerator(name="KM-P12-1", parent=KAL_ZIEL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=SCHREIBER,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-P12-2", parent=KAL_QUELLE, parenttype="Kalender",
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


def _festgelegt(sess, name, calendar=KAL_QUELLE, **felder):
    el = Element(
        name=name, element_name=felder.pop("element_name", "Chorprobe"),
        element_calendar=calendar,
        element_start=felder.pop("element_start", datetime(2026, 3, 1, 10)),
        element_end=felder.pop("element_end", datetime(2026, 3, 1, 12)),
        all_day=0, status="Festgelegt", series_id="", docstatus=0, idx=0,
        **felder,
    )
    sess.add(el)
    sess.commit()
    return el


# ═══════════════════════════════════════════════════════════════════════════
# UXK-R4 / N2 — Kind-Tabellen nur aendern, wenn das Feld gesendet wurde
# ═══════════════════════════════════════════════════════════════════════════

def test_save_event_ohne_mitarbeiter_erhaelt_mitarbeiter(welt):
    """ROT vorher (K2): save_event ohne `mitarbeiter` loeschte die Zuordnung.

    Der Edit-Dialog und Drag&Drop senden das Feld nicht — die eingetragenen
    Dienste eines Termins verschwanden damit bei jeder Titel-Aenderung.
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P12-R4")
    _als(MODERATOR)
    event_crud.save_event(
        "EL-P12-R4", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_QUELLE, mitarbeiter=[{"mitglied": SCHREIBER, "dienstrolle": "Klavier"}],
    )
    assert sess.query(ElementMitarbeiter).count() == 1

    # Nur der Titel aendert sich; beide Kind-Felder fehlen in der Anfrage.
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P12-R4", "Chorprobe (neu)", "2026-03-01 10:00:00",
        "2026-03-01 12:00:00", KAL_QUELLE,
    )
    assert sess.get(Element, "EL-P12-R4").element_name == "Chorprobe (neu)"
    assert sess.query(ElementMitarbeiter).count() == 1, "Mitarbeiter verloren"


def test_save_event_leere_liste_leert_mitarbeiter(welt):
    """Gegenprobe: eine AUSDRUECKLICH leere Liste leert die Tabelle weiterhin."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P12-R4-LEER")
    _als(MODERATOR)
    event_crud.save_event(
        "EL-P12-R4-LEER", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_QUELLE, mitarbeiter=[{"mitglied": SCHREIBER, "dienstrolle": "Klavier"}],
    )
    assert sess.query(ElementMitarbeiter).count() == 1
    event_crud.save_event(
        "EL-P12-R4-LEER", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_QUELLE, mitarbeiter=[],
    )
    assert sess.query(ElementMitarbeiter).count() == 0


def test_save_event_ohne_zusatzressourcen_erhaelt_sie(welt):
    """N2: auch die zusaetzlichen Ressourcen blieben nur bei gesendetem Feld."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Ressource(name="RES-P12-1", ressource_name="Beamer",
                       docstatus=0, idx=0))
    sess.commit()
    _festgelegt(sess, "EL-P12-R4-RES")
    _als(MODERATOR)
    event_crud.save_event(
        "EL-P12-R4-RES", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_QUELLE, zusaetzliche_ressourcen=[{"ressource": "RES-P12-1"}],
    )
    assert sess.query(ElementRessource).count() == 1
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P12-R4-RES", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_QUELLE,
    )
    assert sess.query(ElementRessource).count() == 1, "Zusatzressource verloren"


def test_update_event_ohne_mitarbeiter_erhaelt_mitarbeiter(welt):
    """UXK-R4 praezise: „nur Titel aendern" darf keine Dienste loeschen."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P12-R4-UPD")
    _als(MODERATOR)
    event_crud.update_event(
        "EL-P12-R4-UPD", mitarbeiter=[{"mitglied": SCHREIBER, "dienstrolle": "Klavier"}],
    )
    assert sess.query(ElementMitarbeiter).count() == 1
    _als(SCHREIBER)
    event_crud.update_event("EL-P12-R4-UPD", element_name="Anderer Titel")
    assert sess.query(ElementMitarbeiter).count() == 1, "Mitarbeiter verloren"


# ═══════════════════════════════════════════════════════════════════════════
# N1 — Moderationsrecht gilt am KALENDER DES TERMINS (Quelle)
# ═══════════════════════════════════════════════════════════════════════════

def test_kalenderwechsel_umgeht_quellmoderation_nicht(welt):
    """ROT vorher: SCHREIBER (Moderator nur im ZIEL) verschob einen im QUELLE
    festgelegten Termin sofort, weil `save_event` am Zielkalender pruefte.
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P12-N1", calendar=KAL_QUELLE)
    _als(SCHREIBER)
    res = event_crud.save_event(
        "EL-P12-N1", "Chorprobe", "2026-03-02 10:00:00", "2026-03-02 12:00:00",
        KAL_ZIEL,
    )
    assert res.get("aenderung_wartet") is True, "Wechsel wirkte sofort"
    el = sess.get(Element, "EL-P12-N1")
    assert el.element_calendar == KAL_QUELLE  # alte Fassung sichtbar
    assert el.element_start == datetime(2026, 3, 1, 10)


def test_quellmoderator_wechselt_sofort(welt):
    """Gegenprobe: MODERATOR moderiert die QUELLE -> ohne Zielmoderation wartet
    der Wechsel nun (P1-5c, Punkt 7: Kalenderwechsel ist eine Freigabehandlung
    und verlangt das Moderationsrecht am Ziel). Die frueher hier erwartete
    Sofortwirkung war genau die Uneinheitlichkeit zur Freigabe.

    Mit Zielmoderation wirkt der Wechsel sofort — das zeigt der zweite Teil.
    """
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import KalenderModerator

    sess = welt
    _festgelegt(sess, "EL-P12-N1-MOD", calendar=KAL_QUELLE)
    _als(MODERATOR)
    res = event_crud.save_event(
        "EL-P12-N1-MOD", "Chorprobe", "2026-03-02 10:00:00", "2026-03-02 12:00:00",
        KAL_ZIEL,
    )
    assert res.get("aenderung_wartet") is True, "Wechsel ohne Zielmoderation wirkte sofort"
    assert sess.get(Element, "EL-P12-N1-MOD").element_calendar == KAL_QUELLE

    # Zielmoderation nachtragen -> derselbe Aufruf wirkt sofort.
    sess.add(KalenderModerator(name="KM-P12-M-ZIEL", parent=KAL_ZIEL,
                               parenttype="Kalender",
                               parentfield="kalendermoderatoren",
                               user=MODERATOR, docstatus=0, idx=1))
    sess.commit()
    res2 = event_crud.save_event(
        "EL-P12-N1-MOD", "Chorprobe", "2026-03-02 10:00:00", "2026-03-02 12:00:00",
        KAL_ZIEL,
    )
    assert not res2.get("aenderung_wartet")
    assert sess.get(Element, "EL-P12-N1-MOD").element_calendar == KAL_ZIEL


# ═══════════════════════════════════════════════════════════════════════════
# N3 — vorschlag_anwenden vergleicht mit dem bisherigen Kalender
# ═══════════════════════════════════════════════════════════════════════════

def test_freigabe_ohne_kalenderwechsel_verlangt_kein_recht_am_ziel(welt):
    """ROT vorher: `neuer_kalender != element_name` war immer wahr; die
    Moderationspruefung lief gegen einen Wunsch-Kalender, den es nicht gibt.
    Hier steht ein Kalenderwechsel NICHT im Vorschlag — die Pruefung darf
    nicht gegen den Zufallswert laufen.
    """
    from diakronos_app.api.kronos import event_crud, moderation

    sess = welt
    _festgelegt(sess, "EL-P12-N3", calendar=KAL_QUELLE)
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P12-N3", "Chorprobe", "2026-03-05 10:00:00", "2026-03-05 12:00:00",
        KAL_QUELLE,
    )
    vorschlag = sess.query(ElementAenderung).one()
    neu = json.loads(vorschlag.vorschlag)
    neu.pop("element_calendar", None)  # kein Kalenderwechsel im Vorschlag
    vorschlag.vorschlag = json.dumps(neu)
    sess.commit()

    _als(MODERATOR)
    # Frueher lief hier die Pruefung gegen die TERMIN-ID (kein Kalender) und
    # schlug mit „Keine Moderationsrechte fuer Kalender EL-P12-N3" fehl.
    moderation.vorschlag_anwenden(vorschlag.name, "EL-P12-N3", neu)
    assert sess.get(Element, "EL-P12-N3").element_start == datetime(2026, 3, 5, 10)


# ═══════════════════════════════════════════════════════════════════════════
# N5 — Serien-Batch nennt den verworfenen Status
# ═══════════════════════════════════════════════════════════════════════════

def test_serien_batch_meldet_verworfenen_status(welt):
    """ROT vorher: der Status wurde still verworfen, der Nutzer glaubte an Erfolg."""
    from diakronos_app.api.kronos import series

    sess = welt
    for i in range(2):
        sess.add(Element(
            name=f"EL-P12-N5-{i}", element_name="Serie", element_calendar=KAL_QUELLE,
            element_start=datetime(2026, 3, 1, 10 + i), element_end=datetime(2026, 3, 1, 11 + i),
            all_day=0, status="Festgelegt", series_id="SER-P12", docstatus=0, idx=0,
        ))
    sess.commit()
    _als(SCHREIBER)
    res = series.update_series_batch_fast("SER-P12", {"status": "Festgelegt"})
    assert res.get("verworfen") == ["status"]
    assert "Status" in res.get("meldung", "")
    assert sess.get(Element, "EL-P12-N5-0").status == "Festgelegt"


def test_serien_batch_moderator_status_ohne_meldung(welt):
    """Gegenprobe: fuer einen Moderator ist der Status keine Verwerfung."""
    from diakronos_app.api.kronos import series

    sess = welt
    sess.add(Element(
        name="EL-P12-N5-M", element_name="Serie", element_calendar=KAL_ZIEL,
        element_start=datetime(2026, 3, 1, 10), element_end=datetime(2026, 3, 1, 11),
        all_day=0, status="Vorschlag", series_id="SER-P12-M", docstatus=0, idx=0,
    ))
    sess.commit()
    _als(SCHREIBER)  # moderiert KAL_ZIEL
    res = series.update_series_batch_fast("SER-P12-M", {"status": "Festgelegt"})
    assert "verworfen" not in res
    assert sess.get(Element, "EL-P12-N5-M").status == "Festgelegt"


# ═══════════════════════════════════════════════════════════════════════════
# K1 — Belegungskonflikt bei der Freigabe
# ═══════════════════════════════════════════════════════════════════════════

def test_freigabe_meldet_belegungskonflikt(welt):
    """ROT vorher: die Freigabe pruefte keine Belegung (Doppelbelegung)."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Ressource(name="RES-P12-K1", ressource_name="Jugendraum",
                       docstatus=0, idx=0))
    # Belegender Termin (bleibt stehen).
    sess.add(Element(
        name="EL-P12-K1-BLOCK", element_name="Andere Gruppe",
        element_calendar=KAL_ZIEL, ressource="RES-P12-K1",
        element_start=datetime(2026, 3, 10, 18), element_end=datetime(2026, 3, 10, 20),
        all_day=0, status="Festgelegt", series_id="", docstatus=0, idx=0,
    ))
    # Der Vorschlag schiebt einen zweiten Termin in dieselbe Zeit/denselben Raum.
    # Der Termin liegt in der QUELLE, die der SCHREIBER nicht moderiert -> die
    # Aenderung wartet als Vorschlag (sonst gaebe es nichts freizugeben).
    _festgelegt(sess, "EL-P12-K1", calendar=KAL_QUELLE)
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P12-K1", "Chorprobe", "2026-03-10 19:00:00", "2026-03-10 21:00:00",
        KAL_QUELLE, ressource="RES-P12-K1",
    )
    vorschlag = sess.query(ElementAenderung).one()
    _als(MODERATOR)
    res = event_crud.aenderung_freigeben(vorschlag.name)
    assert res.get("belegung_konflikt"), "Doppelbelegung nicht gemeldet"


def test_freigabe_ohne_konflikt_meldet_nichts(welt):
    """Gegenprobe: freie Belegung -> keine Konfliktmeldung."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P12-K1-FREI", calendar=KAL_QUELLE)
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P12-K1-FREI", "Chorprobe", "2026-03-11 10:00:00", "2026-03-11 12:00:00",
        KAL_QUELLE,
    )
    vorschlag = sess.query(ElementAenderung).one()
    _als(MODERATOR)
    res = event_crud.aenderung_freigeben(vorschlag.name)
    assert not res.get("belegung_konflikt")
