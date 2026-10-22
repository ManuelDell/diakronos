"""P1-1b — Nacharbeit zum Review: die Moderationsregel auf
ALLEN Schreibwegen, Freigabe nur fuer geaenderte Felder, Aufraeumen beim
Loeschen.

Die Tests in `test_p1_1_kalender_termine.py` deckt den Hauptpfad `save_event`
ab. Hier stehen die im Review benannten Luecken:

  B1  update_event umging die Regel vollstaendig (Zeit/Ort/Kalender/Ganztag
      sofort, Status sogar zurueckstufbar).
  B2  update_series_batch_fast schrieb Datum/Uhrzeit aller (auch festgelegter)
      Termine einer Serie sofort und erlaubte Nicht-Moderatoren die
      Serien-Rueckstufung.
  W1  Zusaetzliche Ressourcen wurden im Vorschlagszweig sofort geschrieben.
  W2  Die Freigabe schrieb den ganzen Feldstand zurueck und verwarf damit
      zwischenzeitliche Sofortaenderungen.
  W3  Loeschen eines Termins/Serie raeumte offene Vorschlaege nicht ab;
      Modell und Migration waren sich beim Fremdschluessel uneinig.
  W4  Ersetzen des aelteren Vorschlags laeuft in EINER Transaktion.

Jeder Test war vor dem Patch rot.
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
    Kalender,
    KalenderModerator,
    Ressource,
)

MODERATOR = "moderator-p11b@example.org"
SCHREIBER = "schreiber-p11b@example.org"
KAL_BEIDE = "KAL-P11B-BEIDE"
KAL_SCHREIB = "KAL-P11B-SCHREIB"


@pytest.fixture()
def welt(patched_db):
    """Ein Kalender, auf dem SCHREIBER schreiben und MODERATOR moderieren darf."""
    sess = patched_db()
    sess.add_all([
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        User(name=SCHREIBER, email=SCHREIBER, full_name="Schreiber", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-P11B-M", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-P11B-S", parent=SCHREIBER, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL_BEIDE, calendar_name="Miteinander", calendar_color="#333333",
                 selbstverwaltet=0, docstatus=0, idx=0),
        # Kalender, auf dem der SCHREIBER schreiben, aber NICHT moderieren darf.
        Kalender(name=KAL_SCHREIB, calendar_name="Praxis", calendar_color="#222222",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        UserRole(name="UR-P11B-1", parent=KAL_BEIDE, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="UR-P11B-2", parent=KAL_SCHREIB, parenttype="Kalender",
                 parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        KalenderModerator(name="KM-P11B-1", parent=KAL_BEIDE, parenttype="Kalender",
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


def _festgelegt(sess, name, calendar=KAL_SCHREIB, **felder):
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
# B1 — update_event unterliegt derselben Regel
# ═══════════════════════════════════════════════════════════════════════════

def test_update_event_zeit_wird_vorschlag(welt):
    """ROT vorher: update_event schrieb die neue Zeit sofort an den Termin."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-B1-ZEIT")
    _als(SCHREIBER)
    res = event_crud.update_event(
        "EL-P11B-B1-ZEIT", element_start="2026-03-02 18:00:00",
        element_end="2026-03-02 20:00:00",
    )
    assert res.get("aenderung_wartet") is True
    el = sess.get(Element, "EL-P11B-B1-ZEIT")
    assert el.element_start == datetime(2026, 3, 1, 10)  # alte Fassung sichtbar
    vorschlaege = sess.query(ElementAenderung).all()
    assert len(vorschlaege) == 1
    assert json.loads(vorschlaege[0].vorschlag)["element_start"] == "2026-03-02 18:00:00"


def test_update_event_status_rueckstufung_verboten(welt):
    """ROT vorher: status="Vorschlag" stufte einen festgelegten Termin zurueck."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-B1-STATUS")
    _als(SCHREIBER)
    event_crud.update_event("EL-P11B-B1-STATUS", status="Vorschlag")
    assert sess.get(Element, "EL-P11B-B1-STATUS").status == "Festgelegt"


def test_update_event_status_festgelegt_verboten(welt):
    """Regressschutz: ein Nicht-Moderator kann nicht freigeben."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    sess.add(Element(
        name="EL-P11B-B1-FREI", element_name="Vorschlag",
        element_calendar=KAL_SCHREIB,
        element_start=datetime(2026, 4, 1, 10), element_end=datetime(2026, 4, 1, 11),
        all_day=0, status="Vorschlag", series_id="", docstatus=0, idx=0,
    ))
    sess.commit()
    _als(SCHREIBER)
    event_crud.update_event("EL-P11B-B1-FREI", status="Festgelegt")
    assert sess.get(Element, "EL-P11B-B1-FREI").status == "Vorschlag"


def test_update_event_kleinigkeit_sofort(welt):
    """Gegenprobe: die Beschreibung bleibt eine sofort gueltige Kleinigkeit."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-B1-KLEIN")
    _als(SCHREIBER)
    res = event_crud.update_event("EL-P11B-B1-KLEIN", description="Neue Notiz")
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-P11B-B1-KLEIN").description == "Neue Notiz"
    assert sess.query(ElementAenderung).count() == 0


def test_update_event_moderator_aendert_sofort(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-B1-MOD", calendar=KAL_BEIDE)
    _als(MODERATOR)
    res = event_crud.update_event(
        "EL-P11B-B1-MOD", element_start="2026-03-02 18:00:00",
        element_end="2026-03-02 20:00:00",
    )
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-P11B-B1-MOD").element_start == datetime(2026, 3, 2, 18)


# ═══════════════════════════════════════════════════════════════════════════
# B2 — update_series_batch_fast: Zeit als Vorschlag, Status gar nicht
# ═══════════════════════════════════════════════════════════════════════════

def _serie(sess, series_id, calendar, status="Festgelegt", start=None):
    sess.add(Element(
        name=f"EL-{series_id}", element_name="Serie", element_calendar=calendar,
        element_start=start or datetime(2026, 5, 1, 10),
        element_end=datetime(2026, 5, 1, 11),
        all_day=0, status=status, series_id=series_id, docstatus=0, idx=0,
    ))
    sess.commit()


def test_series_batch_zeit_wird_vorschlag(welt):
    """ROT vorher: die Zeit ALLER Serientermine wurde sofort geschrieben."""
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11B-ZEIT", KAL_SCHREIB)
    _als(SCHREIBER)
    res = series.update_series_batch_fast(
        "SER-P11B-ZEIT", {"element_start": "2026-05-01 18:00:00"},
    )
    assert res.get("aenderung_wartet") is True
    assert res.get("wartende_termine") == 1
    assert sess.get(Element, "EL-SER-P11B-ZEIT").element_start == datetime(2026, 5, 1, 10)
    assert sess.query(ElementAenderung).count() == 1


def test_series_batch_rueckstufung_verboten(welt):
    """ROT vorher: status="Vorschlag" stufte die ganze Serie zurueck."""
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11B-RUECK", KAL_SCHREIB, status="Festgelegt")
    _als(SCHREIBER)
    series.update_series_batch_fast("SER-P11B-RUECK", {"status": "Vorschlag"})
    assert sess.get(Element, "EL-SER-P11B-RUECK").status == "Festgelegt"


def test_series_batch_moderator_aendert_zeit_sofort(welt):
    from diakronos_app.api.kronos import series

    sess = welt
    _serie(sess, "SER-P11B-MOD", KAL_BEIDE)
    _als(MODERATOR)
    res = series.update_series_batch_fast(
        "SER-P11B-MOD", {"element_start": "2026-05-01 18:00:00"},
    )
    assert not res.get("aenderung_wartet")
    assert sess.get(Element, "EL-SER-P11B-MOD").element_start == datetime(2026, 5, 1, 18)


# ═══════════════════════════════════════════════════════════════════════════
# W1 — zusaetzliche Ressourcen gehoeren in den Vorschlag
# ═══════════════════════════════════════════════════════════════════════════

def test_zusaetzliche_ressource_wartet_als_vorschlag(welt):
    """ROT vorher: `_apply_additional_resources` lief im Vorschlagszweig sofort."""
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import ElementRessource

    sess = welt
    sess.add(Ressource(name="RES-P11B", ressource_name="Mikrofon", typ="Technik",
                       docstatus=0, idx=0))
    sess.commit()
    _festgelegt(sess, "EL-P11B-W1", element_name="Chorprobe")
    _als(SCHREIBER)
    res = event_crud.save_event(
        "EL-P11B-W1", "Chorprobe", "2026-03-02 18:00:00", "2026-03-02 20:00:00",
        KAL_SCHREIB,
        zusaetzliche_ressourcen=[{"ressource": "RES-P11B", "status": "Angefragt"}],
    )
    assert res.get("aenderung_wartet") is True
    # Keine Kind-Zeile am Termin — die Ressource ist Teil des Vorschlags.
    assert sess.query(ElementRessource).count() == 0
    vorschlag = json.loads(sess.query(ElementAenderung).one().vorschlag)
    assert vorschlag["zusaetzliche_ressourcen"][0]["ressource"] == "RES-P11B"


def test_freigabe_setzt_zusaetzliche_ressource(welt):
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import ElementRessource

    sess = welt
    sess.add(Ressource(name="RES-P11B-2", ressource_name="Beamer", typ="Technik",
                       docstatus=0, idx=0))
    sess.commit()
    _festgelegt(sess, "EL-P11B-W1F", calendar=KAL_BEIDE, element_name="Chorprobe")
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11B-W1F", "Chorprobe", "2026-03-02 18:00:00", "2026-03-02 20:00:00",
        KAL_BEIDE,
        zusaetzliche_ressourcen=[{"ressource": "RES-P11B-2", "status": "Angefragt"}],
    )
    vorschlag = sess.query(ElementAenderung).one()
    _als(MODERATOR)
    event_crud.aenderung_freigeben(vorschlag.name)
    assert sess.query(ElementRessource).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# W2 — Freigabe uebernimmt NUR die geaenderten Felder
# ═══════════════════════════════════════════════════════════════════════════

def test_freigabe_ueberschreibt_zwischenzeitliche_beschreibung_nicht(welt):
    """ROT vorher: die Freigabe schrieb den alten Titel/Text zurueck."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-W2", calendar=KAL_BEIDE, element_name="Chorprobe")
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11B-W2", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00",
        KAL_BEIDE, description="alt",
    )
    # Zwischenzeitliche Sofortaenderung (sofort gueltig).
    event_crud.save_event(
        "EL-P11B-W2", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00",
        KAL_BEIDE, description="zwischenzeitlich",
    )
    vorschlag = sess.query(ElementAenderung).one()
    vorschlag_json = json.loads(vorschlag.vorschlag)
    # Der Vorschlag traegt nur die moderationspflichtigen Felder.
    assert "description" not in vorschlag_json
    assert set(vorschlag_json) == {"element_start", "element_end"}

    _als(MODERATOR)
    event_crud.aenderung_freigeben(vorschlag.name)
    el = sess.get(Element, "EL-P11B-W2")
    assert el.element_start == datetime(2026, 3, 5, 18)
    assert el.description == "zwischenzeitlich"  # nicht ueberschrieben


def test_offene_aenderungen_nennen_geaenderte_felder(welt):
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-W2B", calendar=KAL_BEIDE,
                element_start=datetime(2026, 3, 1, 10),
                element_end=datetime(2026, 3, 1, 12))
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11B-W2B", "Chorprobe", "2026-03-05 18:00:00", "2026-03-01 12:00:00",
        KAL_BEIDE,
    )
    _als(MODERATOR)
    offen = event_crud.get_offene_aenderungen()
    assert len(offen) == 1
    assert "element_start" in offen[0]["geaenderte_felder"]
    # Das Ende blieb gleich -> nicht als Aenderung gemeldet.
    assert "element_end" not in offen[0]["geaenderte_felder"]


# ═══════════════════════════════════════════════════════════════════════════
# W3 — Aufraeumen beim Loeschen
# ═══════════════════════════════════════════════════════════════════════════

def test_delete_event_raeumt_vorschlag(welt):
    """ROT vorher: der offene Vorschlag blieb als Waise zurueck."""
    from diakronos_app.api.kronos import event_crud

    sess = welt
    _festgelegt(sess, "EL-P11B-W3")
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11B-W3", "Chorprobe", "2026-03-05 18:00:00", "2026-03-05 20:00:00",
        KAL_SCHREIB,
    )
    assert sess.query(ElementAenderung).count() == 1
    event_crud.delete_event("EL-P11B-W3")
    assert sess.get(Element, "EL-P11B-W3") is None
    assert sess.query(ElementAenderung).count() == 0


def test_series_delete_raeumt_vorschlaege(welt):
    from diakronos_app.api.kronos import event_crud, series

    sess = welt
    _serie(sess, "SER-P11B-W3", KAL_SCHREIB)
    _als(SCHREIBER)
    series.update_series_batch_fast(
        "SER-P11B-W3", {"element_start": "2026-05-01 18:00:00"},
    )
    assert sess.query(ElementAenderung).count() == 1
    series.delete_series_batch_fast("SER-P11B-W3")
    assert sess.get(Element, "EL-SER-P11B-W3") is None
    assert sess.query(ElementAenderung).count() == 0


def test_modell_hat_kaskaden_fremdschluessel():
    """Modell und Migration muessen denselben FK tragen (Befund W3)."""
    from sqlalchemy import inspect as sa_inspect

    from diakronos_app.models.kronos import ElementAenderung as EA

    fks = list(sa_inspect(EA.__table__).foreign_keys)
    element_fks = [fk for fk in fks if getattr(fk.column, "name", None) == "name"
                   and fk.column.table.name == "element"]
    assert element_fks, "Fremdschluessel auf element fehlt"
    assert element_fks[0].ondelete == "CASCADE"


# ═══════════════════════════════════════════════════════════════════════════
# W4 — Ersetzen des aelteren Vorschlags in EINER Transaktion
# ═══════════════════════════════════════════════════════════════════════════

def test_zweiter_vorschlag_ersetzt_in_einer_transaktion(client, welt, monkeypatch):
    """Der Ersatzvorgang laeuft in EINER Transaktion.

    Befund W4: Loeschen-dann-Anlegen ueber zwei getrennte Schreibungen liesse
    den alten Vorschlag verschwinden, wenn das Anlegen scheitert. Hier wird
    das Anlegen erzwungen fehlschlagen (Primaerschluessel-Kollision mit einer
    bereits vorhandenen Zeile): danach ist der ALTE Vorschlag unveraendert da.
    """
    from diakronos_app.api.kronos import event_crud, moderation

    sess = welt
    _festgelegt(sess, "EL-P11B-W4")
    _als(SCHREIBER)
    antwort = client.post(
        "/api/method/diakronos.kronos.api.event_crud.save_event",
        json={
            "name": "EL-P11B-W4", "element_name": "Chorprobe",
            "element_start": "2026-03-05 18:00:00",
            "element_end": "2026-03-05 20:00:00",
            "element_calendar": KAL_SCHREIB,
        },
    )
    assert antwort.status_code < 400, antwort.text
    alt = sess.query(ElementAenderung).one()
    alt_name = alt.name
    alt_json = alt.vorschlag
    sess.add(ElementAenderung(
        name="ELEMAEND-kollision", element="EL-P11B-W4",
        element_calendar=KAL_SCHREIB, antragsteller="x", vorschlag="{}",
        docstatus=0, idx=0,
    ))
    sess.commit()
    sess.close()

    monkeypatch.setattr(moderation, "_generate_hash", lambda n=12: "kollision")

    with pytest.raises(Exception):
        moderation.speichere_aenderungsvorschlag(
            "EL-P11B-W4", KAL_SCHREIB, SCHREIBER,
            {"element_start": "2026-03-06 18:00:00"},
        )

    sess = welt
    sess.expire_all()
    # Der alte Vorschlag ist unveraendert vorhanden (Rollback, kein Verlust).
    alt_zeile = sess.get(ElementAenderung, alt_name)
    assert alt_zeile is not None
    assert alt_zeile.vorschlag == alt_json


# ═══════════════════════════════════════════════════════════════════════════
# K2 — save_event aendert Kind-Tabellen nur, wenn das Feld gesendet wurde
#      (P1-2/UXK-R4: das alte Verhalten war Datenverlust und ist behoben)
# ═══════════════════════════════════════════════════════════════════════════

def test_save_event_ohne_mitarbeiter_erhaelt_mitarbeiter(welt):
    """P1-2/UXK-R4: ein fehlendes `mitarbeiter`-Feld laesst die Dienste stehen.

    Vorher ersetzte `save_event` die Kind-Tabelle immer; ein Termin verlor beim
    reinen Bearbeiten (und bei Drag&Drop, das das Feld nicht mitschickt) alle
    Mitarbeiter. Eine AUSDRUECKLICH leere Liste leert sie weiterhin.
    """
    from diakronos_app.api.kronos import event_crud
    from diakronos_app.models.kronos import ElementMitarbeiter

    sess = welt
    _festgelegt(sess, "EL-P11B-K2")
    _als(SCHREIBER)
    event_crud.save_event(
        "EL-P11B-K2", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_SCHREIB, mitarbeiter=[{"mitglied": SCHREIBER, "dienstrolle": ""}],
    )
    assert sess.query(ElementMitarbeiter).count() == 1
    # Ohne das Feld bleibt die Zuordnung bestehen …
    event_crud.save_event(
        "EL-P11B-K2", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_SCHREIB,
    )
    assert sess.query(ElementMitarbeiter).count() == 1
    # … eine ausdruecklich leere Liste leert sie.
    event_crud.save_event(
        "EL-P11B-K2", "Chorprobe", "2026-03-01 10:00:00", "2026-03-01 12:00:00",
        KAL_SCHREIB, mitarbeiter=[],
    )
    assert sess.query(ElementMitarbeiter).count() == 0
