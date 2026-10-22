"""P1-1 — Kalender: Termine anlegen/bearbeiten zuverlaessig.

Reproduktionstests zu den Befunden des Nachtberichts (Abschnitt 7, Paket P1-1)
und zur Operator-Regel vom 16.10. Jeder Test war vor diesem Patch rot und ist
danach gruen.

Befunde
  UXK-R1   Klick auf Tag/Zeitfeld erzeugte ein ungueltiges Datum
           (`2026-10-21T00:00:00T19:00`). Die Backend-Seite dieses Befunds ist
           `parse_iso_datetime_raw`: das doppelte `T` muss weiterhin abgelehnt
           werden (der Fehler lag im Client, hier wird die Grenze gesichert).
  UXK-R7   Monatsserie driftete auf den 28.; ohne Serienende still 100 Termine.
  UXK-009  Titel ueber 140 Zeichen: roher SQL-Text statt Klartextmeldung.
  UXK-R6   „Als Konflikt markieren“ setzte den Status nie.
  UXK-R5   Bearbeiten setzte den Status still auf „Festgelegt“ (Backend).
  Operator-Regel 16.10.: Aenderungen von Nicht-Moderatoren an Datum, Uhrzeit,
           Ort/Ressource oder Kalender eines FESTGELEGTEN Termins warten als
           Vorschlag auf die Freigabe; Kleinigkeiten sind sofort gueltig.
  series.py update_series_batch_fast: Status nur fuer Moderatoren.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

import diakronos_app.api  # noqa: E402,F401  (registriert die @whitelist-Pfade)

from diakronos_app.frappe_compat.api_helpers import ValidationError
from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.kronos import (
    Element,
    ElementAenderung,
    Kalender,
    KalenderModerator,
)

MODERATOR = "moderator-p11@example.org"
SCHREIBER = "schreiber-p11@example.org"
KAL = "KAL-P11-MOD"
KAL_SCHREIB = "KAL-P11-SCHREIB"
# Kalender, auf dem SCHREIBER schreiben UND MODERATOR moderieren darf — fuer
# die Operator-Regel (der Schreibende ist kein Moderator, ein anderer schon).
KAL_BEIDE = "KAL-P11-BEIDE"


@pytest.fixture()
def welt(patched_db):
    """Ein moderierter Kalender (MODERATOR), einer nur schreibbar (SCHREIBER)."""
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Schreiber", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-P11-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-P11-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL, calendar_name="Gottesdienst", calendar_color="#111111",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_SCHREIB, calendar_name="Praxis", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_BEIDE, calendar_name="Miteinander", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        UserRole(name="UR-P11-1", parent=KAL, parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-P11-2", parent=KAL_SCHREIB, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        # SCHREIBER darf auf KAL_BEIDE schreiben (kein Moderationsrecht).
        UserRole(name="UR-P11-3", parent=KAL_BEIDE, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        KalenderModerator(name="KM-P11-1", parent=KAL, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATOR,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-P11-2", parent=KAL_BEIDE, parenttype="Kalender",
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


def _festgelegt(sess, name="EL-P11-FEST", calendar=KAL_SCHREIB, **felder):
    el = Element(
        name=name, element_name=felder.pop("element_name", "Chorprobe"),
        element_calendar=calendar,
        element_start=datetime(2026, 3, 1, 10), element_end=datetime(2026, 3, 1, 12),
        all_day=0, status="Festgelegt", series_id="", docstatus=0, idx=0,
        **felder,
    )
    sess.add(el)
    sess.commit()
    return el


# ═══════════════════════════════════════════════════════════════════════════
# UXK-R1 — doppeltes T bleibt ein Fehler (Client schickt jetzt reines Datum)
# ═══════════════════════════════════════════════════════════════════════════

def test_datum_mit_doppeltem_t_wird_abgelehnt(welt):
    """Der alte Fehlerwert darf nie als gueltiges Datum durchgehen."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    with pytest.raises(ValidationError):
        event_crud.create_event(
            "Kaputt", "2026-10-21T00:00:00T19:00", "2026-10-21T20:00:00", KAL_SCHREIB,
        )


def test_gueltiges_iso_datum_wird_uebernommen(welt):
    """Gegenprobe: das vom Client erzeugte Format ist gueltig."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_event(
        "Gueltig", "2026-10-21T09:00", "2026-10-21T10:00", KAL_SCHREIB,
    )
    assert res["id"]


# ═══════════════════════════════════════════════════════════════════════════
# UXK-R7 — Monatsserie driftet nicht mehr auf den 28.
# ═══════════════════════════════════════════════════════════════════════════

def test_monatsserie_bleibt_am_monatsletzten(welt):
    """ROT vorher: 31.01., 28.02., 28.03., 28.04., ... (schrittweise Addition).

    Erwartet: 31.01., 28.02., 31.03., 30.04., 31.05., 30.06. — jeder Termin
    wird aus dem Startdatum berechnet.
    """
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_series(
        "Monatsende", "2027-01-31 10:00:00", "2027-01-31 11:00:00", KAL_SCHREIB,
        repeat_type="monthly", series_end="2027-06-30",
    )
    sesso = welt
    tage = [
        sesso.get(Element, eid).element_start.strftime("%Y-%m-%d")
        for eid in res["created_ids"]
    ]
    assert tage == [
        "2027-01-31", "2027-02-28", "2027-03-31",
        "2027-04-30", "2027-05-31", "2027-06-30",
    ], f"Drift: {tage}"


def test_serie_ohne_ende_bleibt_bei_hundert_terminen(welt):
    """Grenze bleibt bestehen (kein unbegrenztes Anlegen)."""
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_series(
        "Taeglich", "2027-03-01 10:00:00", "2027-03-01 11:00:00", KAL_SCHREIB,
        repeat_type="daily",
    )
    assert res["created_count"] == 100


# ═══════════════════════════════════════════════════════════════════════════
# UXK-009 — Titel ueber 140 Zeichen: Klartext statt roher SQL-Text
# ═══════════════════════════════════════════════════════════════════════════

def test_titel_zu_lang_klartextmeldung(welt):
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    zu_lang = "T" * 200
    with pytest.raises(ValidationError) as exc:
        event_crud.create_event(
            zu_lang, "2026-10-21T09:00", "2026-10-21T10:00", KAL_SCHREIB,
        )
    text = str(exc.value)
    assert "zu lang" in text
    assert "200" in text
    # Kein roher Datenbanktext (Spaltenliste/INSERT).
    assert "INSERT" not in text and "element_name" not in text


def test_titel_genau_140_erlaubt(welt):
    from diakronos_app.api.kronos import event_crud

    _als(SCHREIBER)
    res = event_crud.create_event(
        "T" * 140, "2026-10-21T09:00", "2026-10-21T10:00", KAL_SCHREIB,
    )
    assert res["id"]


def test_save_event_titel_zu_lang(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-LANG")
    _als(SCHREIBER)
    with pytest.raises(ValidationError):
        event_crud.save_event(
            "EL-P11-LANG", "T" * 200, "2026-03-01 10:00:00",
            "2026-03-01 12:00:00", KAL_SCHREIB,
        )


# ═══════════════════════════════════════════════════════════════════════════
# UXK-R5 — Bearbeiten ist keine Freigabe (Backend-Nachweis)
# ═══════════════════════════════════════════════════════════════════════════

def test_save_event_nicht_moderator_haelt_status(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-R5")
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11-R5", "Neuer Titel", "2026-03-01 10:00:00",
        "2026-03-01 12:00:00", KAL_SCHREIB,
    )
    # Status bleibt "Festgelegt" (Bearbeiten ist keine Freigabe) — zugleich
    # greift die Operator-Regel: die Datumsaenderung wartet als Vorschlag.
    assert sess.get(Element, "EL-P11-R5").status == "Festgelegt"


def test_save_event_nicht_moderator_darf_nicht_freigeben(welt):
    """Ein ausdrueckliches 'Festgelegt' darf nicht durchgehen (Regressschutz)."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(
        name="EL-P11-V", element_name="Vorschlag", element_calendar=KAL_SCHREIB,
        element_start=datetime(2026, 4, 1, 10), element_end=datetime(2026, 4, 1, 11),
        all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0,
    ))
    sess.commit()
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11-V", "Vorschlag", "2026-04-01 10:00:00", "2026-04-01 11:00:00",
        KAL_SCHREIB, status="Festgelegt",
    )
    assert sess.get(Element, "EL-P11-V").status == "Vorschlag"


# ═══════════════════════════════════════════════════════════════════════════
# Operator-Regel 16.10. — Aenderungen an festgelegten Terminen
# ═══════════════════════════════════════════════════════════════════════════

def test_kleinigkeit_sofort_gueltig(welt):
    """Beschreibung ist eine Kleinigkeit -> sofort uebernommen, kein Vorschlag."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-KLEIN")
    _als(SCHREIBER)
    res = event_crud.save_event(
        "EL-P11-KLEIN", "Chorprobe", "2026-03-01 10:00:00",
        "2026-03-01 12:00:00", KAL_SCHREIB, description="Neue Notiz",
    )
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-P11-KLEIN").description == "Neue Notiz"
    assert sess.query(ElementAenderung).count() == 0


def test_datum_aenderung_wartet_als_vorschlag(welt):
    """ROT vorher: die Zeit wurde sofort uebernommen.

    Jetzt: Termin bleibt in der alten Fassung, ein Vorschlag liegt bereit.
    """
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-ZEIT")
    _als(SCHREIBER)
    res = event_crud.save_event(
        "EL-P11-ZEIT", "Chorprobe", "2026-03-02 18:00:00",
        "2026-03-02 20:00:00", KAL_SCHREIB,
    )
    assert res.get("aenderung_wartet") is True
    el = sess.get(Element, "EL-P11-ZEIT")
    # Alte Fassung bleibt sichtbar.
    assert el.element_start == datetime(2026, 3, 1, 10)
    # Vorschlag liegt vor.
    vorschlaege = sess.query(ElementAenderung).all()
    assert len(vorschlaege) == 1
    vorschlag = json.loads(vorschlaege[0].vorschlag)
    assert vorschlag["element_start"] == "2026-03-02 18:00:00"
    assert vorschlaege[0].antragsteller == SCHREIBER


def test_ort_aenderung_wartet_als_vorschlag(welt):
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import Ressource

    sess = welt
    sess.add(Ressource(name="RES-P11", ressource_name="Saal", typ="Raum",
                       docstatus=0, idx=0))
    sess.commit()
    _festgelegt(sess, "EL-P11-ORT")
    _als(SCHREIBER)
    res = event_crud.save_event(
        "EL-P11-ORT", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_SCHREIB, ressource="RES-P11",
    )
    assert res.get("aenderung_wartet") is True
    assert sess.query(ElementAenderung).count() == 1


def test_zweiter_vorschlag_ersetzt_den_ersten(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-ERSETZ")
    _als(SCHREIBER)
    event_crud.save_event("EL-P11-ERSETZ", "A", "2026-03-02 18:00:00",
                          "2026-03-02 20:00:00", KAL_SCHREIB)
    event_crud.save_event("EL-P11-ERSETZ", "B", "2026-03-03 18:00:00",
                          "2026-03-03 20:00:00", KAL_SCHREIB)
    assert sess.query(ElementAenderung).count() == 1


def test_moderator_aendert_sofort(welt):
    """Gegenprobe: ein Moderator wartet nicht auf seine eigene Freigabe."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-MOD", calendar=KAL)
    _als(MODERATOR)
    res = event_crud.save_event(
        "EL-P11-MOD", "Chorprobe", "2026-03-02 18:00:00", "2026-03-02 20:00:00", KAL,
    )
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-P11-MOD").element_start == datetime(2026, 3, 2, 18)


def test_freigabe_uebernimmt_und_loescht_vorschlag(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-FREI", calendar=KAL_BEIDE)  # Moderator darf hier moderieren
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11-FREI", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00", KAL_BEIDE,
    )
    vorschlag = sess.query(ElementAenderung).one()

    _als(MODERATOR)
    offen = event_crud.get_offene_aenderungen()
    assert len(offen) == 1
    assert offen[0]["alt"]["element_start"] == "2026-03-01 10:00:00"
    assert offen[0]["neu"]["element_start"] == "2026-03-05 18:00:00"

    event_crud.aenderung_freigeben(vorschlag.name)
    assert sess.get(Element, "EL-P11-FREI").element_start == datetime(2026, 3, 5, 18)
    assert sess.query(ElementAenderung).count() == 0


def test_ablehnung_verwirft_vorschlag_und_laesst_termin(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-ABLEHN", calendar=KAL_BEIDE)
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11-ABLEHN", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00", KAL_BEIDE,
    )
    vorschlag = sess.query(ElementAenderung).one()

    _als(MODERATOR)
    event_crud.aenderung_ablehnen(vorschlag.name)
    assert sess.get(Element, "EL-P11-ABLEHN").element_start == datetime(2026, 3, 1, 10)
    assert sess.query(ElementAenderung).count() == 0


def test_nicht_moderator_darf_vorschlag_nicht_freigeben(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11-RECHT", calendar=KAL_BEIDE)
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11-RECHT", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00", KAL_BEIDE,
    )
    vorschlag = sess.query(ElementAenderung).one()
    with pytest.raises(PermErr):
        event_crud.aenderung_freigeben(vorschlag.name)


# ═══════════════════════════════════════════════════════════════════════════
# update_series_batch_fast — Status nur fuer Moderatoren
# ═══════════════════════════════════════════════════════════════════════════

def _serie(sess, series_id, calendar, status="Vorschlag"):
    sess.add(Element(
        name=f"EL-{series_id}", element_name="Serie", element_calendar=calendar,
        element_start=datetime(2026, 5, 1, 10), element_end=datetime(2026, 5, 1, 11),
        all_day=0, status=status, series_id=series_id, docstatus=0, idx=0,
    ))
    sess.commit()


def test_series_batch_status_nur_moderator(welt):
    """ROT vorher: jeder Schreibberechtigte konnte eine ganze Serie freigeben."""
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11-S", KAL_SCHREIB)
    _als(SCHREIBER)
    series.update_series_batch_fast("SER-P11-S", {"status": "Festgelegt"})
    assert sess.get(Element, "EL-SER-P11-S").status == "Vorschlag"


def test_series_batch_moderator_darf_freigeben(welt):
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11-M", KAL)
    _als(MODERATOR)
    series.update_series_batch_fast("SER-P11-M", {"status": "Festgelegt"})
    assert sess.get(Element, "EL-SER-P11-M").status == "Festgelegt"


def test_series_batch_titel_bleibt_erlaubt(welt):
    """Der Titel-Update (einziger echter Aufrufer) funktioniert weiter."""
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11-T", KAL_SCHREIB)
    _als(SCHREIBER)
    series.update_series_batch_fast("SER-P11-T", {"element_name": "Neuer Titel"})
    assert sess.get(Element, "EL-SER-P11-T").element_name == "Neuer Titel"
