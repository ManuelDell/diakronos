"""P1-8 — Reste aus R-P1-4b: Ressourcen-Moderation bei Vorschlag und Zeitwechsel.

Die drei Klein-Befunde des vorausgehenden Reviews (dem Paket P1-8
zugeordnet):

  * K-a  Beim Ablegen eines Terminvorschlags wurde die Ressourcenliste ROH
         gespeichert. Ein Nicht-Moderator konnte „Bestätigt" per API
         einschleusen; bei der Freigabe entschied der Status des Freigebenden
         statt der Rolle des Antragstellers.
  * K-b  Eine bestätigte Termin-Ressource blieb bestätigt, wenn ein
         Nicht-Moderator den Zeitpunkt eines noch nicht festgelegten Termins
         änderte — die Bestätigung deckte den neuen Zeitpunkt nicht mehr.
  * K-c  Ablehnen einer Termin-Ressource löschte die Zeile still: kein Grund,
         keine Benachrichtigung an den Antragsteller.

Jeder Test wäre ohne die zugehörige Änderung rot.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import NotificationLog
from diakronos_app.models.kronos import Element, ElementRessource

from tests.test_p1_4b_ressourcen import (  # noqa: F401  (Fixtures)
    ANNA,
    BRUNO,
    MODERATOR,
    _termin,
    als_moderator,
    welt,
)

RES_MODUL = "diakronos.diakonos.api.ressourcen"


def _ressourcen_zeilen(sess, element: str) -> list[ElementRessource]:
    sess.expire_all()
    return (
        sess.query(ElementRessource)
        .filter(ElementRessource.parent == element)
        .all()
    )


# ── K-a: Ressourcenliste im Vorschlag wird normalisiert ─────────────────────


def test_k_a_vorschlag_schleust_kein_bestaetigt_ein(client, welt, monkeypatch) -> None:
    """Ein Nicht-Moderator kann „Bestätigt" nicht in den Vorschlag schreiben."""
    from diakronos_app.api.kronos import event_crud

    # Kein Ressourcenmoderator.
    monkeypatch.setattr(
        "diakronos_app.api.ressourcen._is_ressourcenmoderator", lambda: False
    )
    _termin(welt, "EL-KA", "Probe", 5, owner=BRUNO, kalender="Gemeinde")
    ziel = welt.get(Element, "EL-KA")
    # Noch nicht festgelegt -> moderationsbeduerftig fuer einen Nicht-Moderator.
    ziel.status = "Vorschlag"
    welt.commit()

    event_crud._speichere_aenderungsvorschlag(
        "EL-KA",
        "Gemeinde",
        ANNA,
        {"element_start": "2026-11-01 10:00:00"},
        {"zusaetzliche_ressourcen": [
            {"ressource": "RES-BEAMER", "freitext_ressource": "",
             "status": "Bestätigt", "notiz": ""},
        ]},
    )

    from diakronos_app.frappe_compat.query import get_all

    zeilen = get_all("Element Aenderung", filters={"element": "EL-KA"},
                     fields=["vorschlag"]) or []
    assert zeilen, "Vorschlag wurde abgelegt"
    import json

    nutzlast = json.loads(zeilen[0]["vorschlag"])
    ressourcen = nutzlast["zusaetzliche_ressourcen"]
    assert ressourcen[0]["status"] == "Angefragt", ressourcen


def test_k_a_moderator_darf_bestaetigt_behalten(client, welt, monkeypatch) -> None:
    """Gegenrichtung: ein Ressourcenmoderator schreibt weiterhin „Bestätigt"."""
    from diakronos_app.api.kronos import event_crud

    monkeypatch.setattr(
        "diakronos_app.api.ressourcen._is_ressourcenmoderator", lambda: True
    )
    _termin(welt, "EL-KA2", "Probe", 5, owner=BRUNO, kalender="Gemeinde")
    welt.get(Element, "EL-KA2").status = "Vorschlag"
    welt.commit()

    event_crud._speichere_aenderungsvorschlag(
        "EL-KA2", "Gemeinde", MODERATOR,
        {"element_start": "2026-11-01 10:00:00"},
        {"zusaetzliche_ressourcen": [
            {"ressource": "RES-BEAMER", "freitext_ressource": "",
             "status": "Bestätigt", "notiz": ""},
        ]},
    )

    from diakronos_app.frappe_compat.query import get_all

    import json

    zeilen = get_all("Element Aenderung", filters={"element": "EL-KA2"},
                     fields=["vorschlag"]) or []
    nutzlast = json.loads(zeilen[0]["vorschlag"])
    assert nutzlast["zusaetzliche_ressourcen"][0]["status"] == "Bestätigt"


# ── K-b: Zeitwechsel stufen Bestätigtes erneut auf „Angefragt" ──────────────


def test_k_b_zeitwechsel_stuft_bestaetigte_ressource_zurueck(client, welt, monkeypatch) -> None:
    from diakronos_app.api.kronos import moderation

    monkeypatch.setattr(
        "diakronos_app.api.ressourcen._is_ressourcenmoderator", lambda: False
    )
    _termin(welt, "EL-KB", "Probe", 5, owner=BRUNO, kalender="Gemeinde")
    el = welt.get(Element, "EL-KB")
    el.status = "Vorschlag"  # noch nicht festgelegt
    welt.add(ElementRessource(
        name="ER-KB", parent="EL-KB", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Bestätigt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    set_user(ANNA)
    try:
        from diakronos_app.frappe_compat.query import get_doc

        moderation.wende_termin_aenderung_an(
            get_doc("Element", "EL-KB"),
            {"element_start": "2026-12-01 09:00:00"},
            False,
        )
    finally:
        set_user("Administrator")

    zeilen = _ressourcen_zeilen(welt, "EL-KB")
    assert len(zeilen) == 1
    assert zeilen[0].status == "Angefragt", zeilen[0].status


def test_k_b_nur_titel_bleibt_bestaetigt(client, welt, monkeypatch) -> None:
    """Gegenrichtung: eine reine Titeländerung tastet die Bestätigung nicht an."""
    from diakronos_app.api.kronos import moderation

    monkeypatch.setattr(
        "diakronos_app.api.ressourcen._is_ressourcenmoderator", lambda: False
    )
    _termin(welt, "EL-KB2", "Probe", 5, owner=BRUNO, kalender="Gemeinde")
    welt.get(Element, "EL-KB2").status = "Vorschlag"
    welt.add(ElementRessource(
        name="ER-KB2", parent="EL-KB2", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Bestätigt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    set_user(ANNA)
    try:
        from diakronos_app.frappe_compat.query import get_doc

        moderation.wende_termin_aenderung_an(
            get_doc("Element", "EL-KB2"), {"element_name": "Neuer Titel"}, False,
        )
    finally:
        set_user("Administrator")

    zeilen = _ressourcen_zeilen(welt, "EL-KB2")
    assert zeilen[0].status == "Bestätigt"


# ── K-c: Ablehnen speichert Grund und benachrichtigt ────────────────────────


def test_k_c_ablehnen_benachrichtigt_antragsteller(client, als_moderator, welt) -> None:
    _termin(welt, "EL-KC", "Jugendabend", 12, owner=BRUNO)
    welt.add(ElementRessource(
        name="ER-KC", parent="EL-KC", parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-BEAMER",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    welt.commit()

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-KC", "entscheidung": "ablehnen",
                          "grund": "Beamer ist belegt."})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["status"] == "Abgelehnt"

    # Die Zeile ist weg (wie bisher) ...
    assert welt.get(ElementRessource, "ER-KC") is None
    # ... aber der Antragsteller wurde informiert (neu).
    welt.expire_all()
    logs = welt.query(NotificationLog).filter(NotificationLog.for_user == BRUNO).all()
    assert logs, "Antragsteller wurde nicht benachrichtigt"
    assert any("Beamer" in (l.email_content or "") for l in logs), \
        [l.email_content for l in logs]
