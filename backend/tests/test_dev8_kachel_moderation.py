"""DEV-8 — Startseiten-Kachel „Zu moderierende Termine“ zaehlt das Falsche.

BEFUND DMB-7bee65f6c32b (Dev-Modus, 2026-10-16): Die Kachel zeigt 2, die
Moderationsseite ist leer. Ursache im Code:

    dashboard.get_widget_badge_counts()          -> pending-registrations
    dashboard._count_ueberlappende_ressourcen_events()   (dashboard.py:737-740)

Der Zaehler masz Ressourcen-DOPPELBELEGUNGEN (jeder Status, auch vergangene);
die Moderationsseite zeigt dagegen Termin-VORSCHLAEGE der moderierten
Kalender. Zwei verschiedene Mengen, zwei verschiedene Zahlen — der Titel der
Kachel log.

Diese Datei ist der rote->gruene Nachweis. Geprueft wird an drei Stellen:

1. **Kachel-Zaehler vs. Kachel-Liste** — `get_widget_badge_counts()` muss
   genau die Laenge von `get_moderation_vorschlaege()` melden (dieselbe
   Abfrage, gleiche Rechte). Die Konfliktdaten (zwei ueberlappende Termine)
   sind im Fixture EXTRA enthalten: sie duerfen die Zahl NICHT mehr aufblaehen.
2. **Kachel vs. Seiten-Badge** — `kanban_api.get_moderation_count()` (Badge
   der Moderationsseite) und `len(get_kanban_board_data()["vorschlaege"])`
   sind die Sollzahl.
3. **Sichtbarkeit** — wer einen Kalender nicht moderiert, sieht dessen
   Vorschlaege in keiner der drei Zahlen (gleiche Schranke wie das Brett).

Ressourcen-Konflikte werden nicht stillschweigend entfernt: Test 4 belegt,
dass sie weiter in der Spalte „Konflikte“ des Bretts und ueber
`ressource_api.get_conflict_events` auffindbar sind.
"""

from __future__ import annotations

import datetime

import pytest

import diakronos_app.api  # noqa: F401 — alle @whitelist-Dekoratoren registrieren

from diakronos_app.frappe_compat.api_helpers import _create
from diakronos_app.frappe_compat.session import set_user

MODERATORIN = "moderatorin@example.org"
NUR_MOD = "nurmoderatorin@example.org"
FREMD = "fremd@example.org"
KAL_MOD = "KAL-DEV8-MOD"
KAL_FREMD = "KAL-DEV8-FREMD"


@pytest.fixture()
def welt(patched_db):
    """Zwei Kalender, zwei offene Vorschlaege, zwei Ressourcen-Doppelbelegungen.

    Der Aufbau bildet die Befund-Lage nach („Kachel 2, Liste leer“):

      * KAL-DEV8-MOD wird von MODERATORIN moderiert.
      * In ihm liegen ZWEI Termine mit Status „Vorschlag“ — der eine in der
        ZUKUNFT, der andere in der VERGANGENHEIT (das Brett zeigt beide;
        frueher blendete die Kachel Vergangenes per Zeitfilter aus).
      * Zusaetzlich zwei ueberlappende „Festgelegt“-Termine auf derselben
        Ressource — die alte Zaehlquelle. Sie ergeben zwei
        Ressourcen-Ueberschneidungen und damit frueher die Zahl 2.
      * In KAL-DEV8-FREMD (nicht moderiert) liegt ein weiterer Vorschlag —
        er darf in keiner Zahl auftauchen.
    """
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.kronos import Kalender, KalenderModerator

    sess = patched_db()
    jetzt = datetime.datetime.now()
    sess.add_all([
        User(name=MODERATORIN, email=MODERATORIN, full_name="Moderatorin M", enabled=1),
        User(name=NUR_MOD, email=NUR_MOD, full_name="Nur-Moderatorin N", enabled=1),
        User(name=FREMD, email=FREMD, full_name="Fremd F", enabled=1),
    ])
    # Die Rollen, die die Widget-Zeile „pending-registrations“ verlangt
    # (`required_role = "Kalenderadministrator"`).
    #
    # WICHTIG (nachgemessen): In `dashboard.get_widget_badge_counts` liefert
    # `permissions.get_roles` fuer diese Konten die Rolle NICHT, weil die
    # Rollenzeilen ohne `parenttype="User"`/`parentfield="roles"` nicht als
    # Rollen gelesen werden — die Rollenzeilen unten setzen beides deshalb
    # ausdruecklich. Ebenso oeffnet `Kalenderadministrator` in
    # `get_accessible_calendars` ALLE Kalender; die Sichtbarkeitspruefung
    # (`test_vorschlag_fremder_kalender_zaehlt_nicht`) laeuft darum mit dem
    # Konto NUR_MOD, das nur EINEN Kalender moderiert.
    sess.add_all([
        HasRole(name="HR-DEV8-KA", parent=MODERATORIN, parenttype="User",
                parentfield="roles", role="Kalenderadministrator", docstatus=0, idx=2),
        HasRole(name="HR-DEV8-SM", parent=MODERATORIN, parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=3),
        # Nur-Kalender-Moderatorin (ohne Kalenderadministrator): sieht nur KAL_MOD.
        HasRole(name="HR-DEV8-M2", parent=NUR_MOD, parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        Kalender(name=KAL_MOD, calendar_name="Jugend", calendar_color="#123456",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name=KAL_FREMD, calendar_name="Fremd", calendar_color="#654321",
                 selbstverwaltet=0, docstatus=0, idx=0),
        KalenderModerator(name="KM-DEV8-1", parent=KAL_MOD, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=MODERATORIN,
                          docstatus=0, idx=1),
        KalenderModerator(name="KM-DEV8-2", parent=KAL_MOD, parenttype="Kalender",
                          parentfield="kalendermoderatoren", user=NUR_MOD,
                          docstatus=0, idx=2),
    ])
    sess.commit()

    # Offene Vorschlaege im moderierten Kalender: einer kuenftig, einer vorbei.
    _create("Element", {
        "name": "EL-DEV8-V1", "element_name": "Jugendabend",
        "element_calendar": KAL_MOD, "status": "Vorschlag",
        "element_start": jetzt + datetime.timedelta(days=3),
        "element_end": jetzt + datetime.timedelta(days=3, hours=2),
        "docstatus": 0, "idx": 0,
    })
    _create("Element", {
        "name": "EL-DEV8-V2", "element_name": "Nachholtermin (vergangen)",
        "element_calendar": KAL_MOD, "status": "Vorschlag",
        "element_start": jetzt - datetime.timedelta(days=5),
        "element_end": jetzt - datetime.timedelta(days=5, hours=-2),
        "docstatus": 0, "idx": 1,
    })

    # Die ALTE Zaehlquelle: zwei Ueberschneidungen auf derselben Ressource,
    # beide FESTGELEGT — also keine offenen Vorschlaege.
    start = jetzt + datetime.timedelta(days=10)
    _create("Element", {
        "name": "EL-DEV8-K1", "element_name": "Chorprobe",
        "element_calendar": KAL_MOD, "status": "Festgelegt",
        "ressource": "Gemeindesaal",
        "element_start": start, "element_end": start + datetime.timedelta(hours=3),
        "docstatus": 0, "idx": 2,
    })
    _create("Element", {
        "name": "EL-DEV8-K2", "element_name": "Posaunenchor",
        "element_calendar": KAL_MOD, "status": "Festgelegt",
        "ressource": "Gemeindesaal",
        "element_start": start + datetime.timedelta(minutes=30),
        "element_end": start + datetime.timedelta(hours=2),
        "docstatus": 0, "idx": 3,
    })

    # Vorschlag in einem NICHT moderierten Kalender.
    _create("Element", {
        "name": "EL-DEV8-F1", "element_name": "Fremder Vorschlag",
        "element_calendar": KAL_FREMD, "status": "Vorschlag",
        "element_start": jetzt + datetime.timedelta(days=1),
        "element_end": jetzt + datetime.timedelta(days=1, hours=1),
        "docstatus": 0, "idx": 4,
    })

    # Die Widget-Zeile selbst (1:1 wie die System-Zeile in `dashboard_widget`).
    _create("Dashboard Widget", {
        "widget_id": "pending-registrations",
        "label": "Zu moderierende Termine",
        "category": "action",
        "widget_type": "action_card",
        "grid_size": "medium",
        "default_position": 12,
        "default_visible": 1,
        "refresh_interval": 30,
        "required_role": "Kalenderadministrator",
        "api_method": "diakronos.diakonos.api.dashboard.get_moderation_vorschlaege",
        "empty_state_mode": "show_message",
        "empty_state_message": "Keine offenen Termine zur Moderation.",
        "enabled": 1,
        "is_system": 1,
    })

    yield sess
    sess.close()


@pytest.fixture()
def als_moderatorin(welt):
    set_user(MODERATORIN)
    yield MODERATORIN
    set_user("Administrator")


# ── 1. Kachel: Zaehler = Laenge der Kachel-Liste ────────────────────────────


def test_kachel_zaehler_ist_anzahl_der_vorschlaege(als_moderatorin):
    """DER BEFUND als Test: die Zahl stammt aus derselben Menge wie die Liste.

    Konto: MODERATORIN mit ``Kalenderadministrator`` — wer diese Rolle hat,
    moderiert ALLE Kalender (so ist das Recht definiert), also zaehlen hier
    alle drei offenen Vorschlaege. Vorher zaehlte die Kachel die
    Festgelegt-Ueberschneidungen (2) statt der Vorschlaege (3) — genau die
    gemeldete Abweichung „Zahl da, Liste leer“.

    Die Sichtbarkeits-Schranke prueft `test_vorschlag_fremder_kalender_zaehlt_nicht`
    mit einem Konto ohne globale Rolle.
    """
    from diakronos_app.api import dashboard as d

    counts = d.get_widget_badge_counts()
    liste = d.get_moderation_vorschlaege()
    widget = d.get_widget_data("pending-registrations")

    assert counts["pending-registrations"] == 3, (
        "Kachel-Zaehler zaehlt nicht die Vorschlaege: %r" % counts
    )
    assert counts["pending-registrations"] == len(liste)
    assert {e["id"] for e in liste} == {"EL-DEV8-V1", "EL-DEV8-V2", "EL-DEV8-F1"}
    # Und die Kachel liefert in `data` genau dieselbe Laenge.
    assert len(widget["data"]) == counts["pending-registrations"]


def test_kachel_zaehlt_keine_ressourcen_ueberschneidungen(als_moderatorin):
    """Die alten Konfliktzaehlungen duerfen die Zahl nicht mehr beeinflussen.

    Gegenprobe zur alten Quelle: sie liefert 2 (die beiden Festgelegt-
    Ueberschneidungen). Der Kachel-Zaehler ist 3 aus ANDEREN Zeilen (den
    Vorschlaegen). Zum Beweis wird ein Vorschlag freigegeben: die Konfliktzahl
    bleibt 2, die Kachel faellt auf 2.
    """
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    assert d._count_ueberlappende_ressourcen_events() == 2
    assert d.get_widget_badge_counts()["pending-registrations"] == 3

    _update_doc("Element", "EL-DEV8-V1", {"status": "Festgelegt"})

    assert d._count_ueberlappende_ressourcen_events() == 2  # unveraendert
    assert d.get_widget_badge_counts()["pending-registrations"] == 2


# ── 2. Kachel = Moderationsseite (Badge und Brett) ──────────────────────────


def test_kachel_zahl_gleich_badge_der_moderationsseite(als_moderatorin):
    from diakronos_app.api import dashboard as d
    from diakronos_app.api.kronos import kanban_api

    kachel = d.get_widget_badge_counts()["pending-registrations"]
    badge = kanban_api.get_moderation_count()["count"]
    board = kanban_api.get_kanban_board_data()

    assert kachel == badge == len(board["vorschlaege"]) == 3


# ── 3. Gleiche Rechte wie das Brett ─────────────────────────────────────────


def test_fremder_sieht_keine_zahl_und_keine_liste(als_moderatorin):
    """Wer keinen Kalender moderiert, bekommt weder Schluessel noch Liste."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.api.kronos import kanban_api

    set_user(FREMD)
    try:
        # Schluessel fehlt GANZ (Aggregat-Sichtbarkeit), nicht 0.
        assert "pending-registrations" not in d.get_widget_badge_counts()
        assert d.get_moderation_vorschlaege() == []
        assert kanban_api.get_moderation_count() == {"count": 0}
    finally:
        set_user(MODERATORIN)


def test_vorschlag_fremder_kalender_zaehlt_nicht(welt):
    """EL-DEV8-F1 liegt in einem fremden Kalender — nirgends gezaehlt.

    Konto: NUR_MOD moderiert ausschliesslich KAL-DEV8-MOD per
    `Kalender Moderator` (KEINE globale Rolle Kalenderadministrator — die
    wuerde alle Kalender oeffnen). Geprueft wird dieselbe Schranke wie im
    Brett: Liste, Kachel-Liste und Seiten-Badge einig.
    """
    from diakronos_app.api import dashboard as d
    from diakronos_app.api.kronos import kanban_api

    set_user(NUR_MOD)
    try:
        ids = {e["id"] for e in d.get_moderation_vorschlaege()}
        assert ids == {"EL-DEV8-V1", "EL-DEV8-V2"}
        assert "EL-DEV8-F1" not in ids
        assert kanban_api.get_moderation_count() == {"count": 2}
        board = kanban_api.get_kanban_board_data()
        assert len(board["vorschlaege"]) == 2
    finally:
        set_user("Administrator")


# ── 4. Konflikte bleiben sichtbar (nichts stillschweigend entfernt) ─────────


def test_ressourcenkonflikte_bleiben_im_brett_und_im_endpunkt(als_moderatorin):
    from diakronos_app.api.kronos import kanban_api, ressource_api

    board = kanban_api.get_kanban_board_data()
    # Konflikte haben ihre eigene Spalte (Status „Konflikt“) und sind hier
    # nicht der Fall — geprueft wird, dass die Konflikt-ABFRAGE die beiden
    # Ueberschneidungen weiterhin findet.
    assert board["konflikte"] == []
    konflikte = ressource_api.get_conflict_events()
    assert {e["name"] for e in konflikte} == {"EL-DEV8-K1", "EL-DEV8-K2"}
