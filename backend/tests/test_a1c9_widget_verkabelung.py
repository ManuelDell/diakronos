"""A1c9 — Die Karte »Zu moderierende Termine« zeigt dauerhaft einen Fehler.

BEFUND (live gemessen, nicht aus einem Kartentext):

    POST diakronos.diakonos.api.dashboard.get_widget_data
         {"widget_id": "pending-registrations"}
      -> HTTP 200 {"data": null, "error": "'NoneType' object is not callable"}

URSACHE: die Tabelle `dashboard_widget` zeigt mit `api_method` auf
`diakronos.kronos.api.ressource_api.get_conflict_events` — eine Funktion, die
im Port **nicht existiert** (Karte P4c1 war bewusst schmal). `dashboard.py`
nahm den Rueckgabewert von `lookup()` ohne Pruefung an und rief `None` auf.

Diese Datei deckt beide Haelften der Karte ab:

  1. **Verkabelung** — `get_conflict_events` ist portiert und unter dem
     Pfad erreichbar, den die Widget-Tabelle nennt. Geprueft wird AUCH die
     Konsistenz der Tabelle selbst: jeder `api_method`, der dort steht, muss
     aufloesbar sein (sonst ist jede spaetere Fixture-Aenderung wieder eine
     stille Fehlerkarte).
  2. **Fehlerunterscheidung** — ein nicht auffindbarer `api_method` ist ein
     *Konfigurationsfehler*: Log-Eintrag, KEINE Benutzeroberflaechen-Fehlerkarte.
     Ein Fehler *innerhalb* der Funktion antwortet weiterhin wie bisher mit
     `data: null, error: <text>`. Der eine Fall darf den anderen nicht
     ausloesen — beide Richtungen sind hier belegt.

GEWAEHLTER WEG (c): Funktion portiert, **ohne** den Moderations-Workflow
(`confirm_element` bleibt unportiert — `confirm_element` waere eine
Schreibfunktion und waere hier falsch).
"""

from __future__ import annotations

import datetime

import pytest

# Importiert das API-Paket (alle `@whitelist`-Dekoratoren laufen). Im Betrieb
# passiert das in `frappe_compat/router.py::mount`; im Test ist es sonst von
# der Reihenfolge anderer Dateien abhaengig — genau die Sorte Kopplung, die
# einen Test spaeter nur scheinbar gruen laesst.
import diakronos_app.api  # noqa: F401

from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

RESSOURCE_API_PFAD = "diakronos.kronos.api.ressource_api.get_conflict_events"
# BF1c/W6: Die Kachel »Zu moderierende Termine« zeigt die offenen Vorschlaege
# der moderierten Kalender — nicht die Ressourcenkonflikte. Der Zeiger der
# System-Zeile ist deshalb `dashboard.get_moderation_vorschlaege`.
MODERATION_API_PFAD = "diakronos.diakonos.api.dashboard.get_moderation_vorschlaege"

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
ADMIN = "admin@example.org"


# ── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Nutzer + Rollen + zwei kollidierende Termine auf derselben Ressource.

    Die Kollision bildet die echte Datenlage ab (gemessen live: 2 Konflikte
    auf `Jugendraum`, 2026-04-17) — sie ist kein Kunstfall, sonst prueft der
    Test nur sich selbst.
    """
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.kronos import Kalender

    sess = patched_db()

    start = datetime.datetime(2026, 4, 17, 21, 0, 0)
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
    ])
    sess.add_all([
        HasRole(name="HR-A", parent=ANNA, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-B", parent=BRUNO, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1),
        # Genau die Rollen, die die WIDGET-ZEILE verlangt
        # (`dashboard_widget.required_role = "Kalenderadministrator"`), live
        # gemessen an `Administrator`: Kalenderadministrator + System Manager.
        HasRole(name="HR-ADM", parent=ADMIN, parenttype="User", parentfield="roles",
                role="Kalenderadministrator", docstatus=0, idx=1),
        HasRole(name="HR-ADM2", parent=ADMIN, parenttype="User", parentfield="roles",
                role="System Manager", docstatus=0, idx=2),
    ])
    sess.add_all([
        Kalender(name="KAL-JUG", calendar_name="Jugend", calendar_color="#123456",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name="KAL-GEM", calendar_name="Gemeinschaftsteam",
                 calendar_color="#654321", selbstverwaltet=0, docstatus=0, idx=0),
    ])

    # Zwei Termine, dieselbe Ressource, ueberlappend -> genau ein Konflikt.
    _create("Element", {
        "name": "EL-1", "element_name": "Jugendstunde", "ressource": "Jugendraum",
        "element_calendar": "KAL-JUG",
        "element_start": start,
        "element_end": start + datetime.timedelta(hours=2, minutes=59),
        "docstatus": 0, "idx": 0,
    })
    _create("Element", {
        "name": "EL-2", "element_name": "Gemeinschaftsteam: Annika", "ressource": "Jugendraum",
        "element_calendar": "KAL-GEM",
        "element_start": start + datetime.timedelta(minutes=30),
        "element_end": start + datetime.timedelta(hours=2, minutes=59),
        "docstatus": 0, "idx": 1,
    })
    # Nicht kollidierend: andere Ressource, gleiche Zeit.
    _create("Element", {
        "name": "EL-3", "element_name": "Chorprobe", "ressource": "Gemeindesaal",
        "element_calendar": "KAL-GEM",
        "element_start": start,
        "element_end": start + datetime.timedelta(hours=1),
        "docstatus": 0, "idx": 2,
    })
    # W6: ein offener VORSCHLAG in einem moderierten Kalender — genau das,
    # was die Kachel »Zu moderierende Termine« zeigen soll. KAL-JUG ist fuer
    # den Admin moderiert (Kalenderadministrator-Rolle).
    _create("Element", {
        "name": "EL-VORSCHLAG", "element_name": "Neuer Vorschlag",
        "element_calendar": "KAL-JUG", "status": "Vorschlag",
        "element_start": datetime.datetime.now() + datetime.timedelta(days=3),
        "element_end": datetime.datetime.now() + datetime.timedelta(days=3, hours=1),
        "docstatus": 0, "idx": 3,
    })

    # Die Widget-Zeile selbst, 1:1 aus `dashboard_widget` (live gemessen).
    # Ohne sie pruefen die `get_widget_data`-Tests eine erfundene Zeile.
    _create("Dashboard Widget", {
        "widget_id": "pending-registrations",
        "label": "Zu moderierende Termine",
        "category": "action",
        "widget_type": "action_card",
        "grid_size": "medium",
        "default_position": 2,
        "default_visible": 1,
        "refresh_interval": 30,
        "required_role": "Kalenderadministrator",
        "api_method": MODERATION_API_PFAD,
        "empty_state_mode": "show_message",
        "empty_state_message": "Keine offenen Termine zur Moderation.",
        "enabled": 1,
        "is_system": 1,
    })

    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield
    set_user("Administrator")


# ── 1. Die Funktion existiert unter dem Pfad, den die Tabelle nennt ───────


def test_conflict_events_unter_widget_pfad_erreichbar():
    """Der Pfad aus `dashboard_widget.api_method` muss aufloesbar sein.

    Ohne diesen Test koennte die Karte erneut stillbrechen: die Tabelle zeigt
    auf einen Pfad, den es nicht gibt, und der Fehler faellt nur auf der
    Benutzeroberflaeche auf.

    BF1c/W6: Der Zeiger der System-Zeile zeigt jetzt auf die
    Moderationsvorschlaege; der alte Konflikt-Endpunkt bleibt als Funktion
    erhalten und muss ebenfalls aufloesbar bleiben (er wird weiter von
    `get_conflict_events`-Aufrufern benutzt).
    """
    assert lookup(MODERATION_API_PFAD) is not None, (
        "api_method aus dashboard_widget ist nicht auffindbar: %s" % MODERATION_API_PFAD
    )
    assert lookup(RESSOURCE_API_PFAD) is not None, (
        "get_conflict_events ist nicht mehr auffindbar: %s" % RESSOURCE_API_PFAD
    )


def test_jeder_widget_zeiger_ist_auffindbar():
    """KEINE Widget-Zeile darf auf eine nicht vorhandene Funktion zeigen.

    Das ist der Test, der diese Fehlerklasse fuer die Zukunft schliesst —
    nicht nur fuer `pending-registrations`, sondern fuer jede Zeile.
    """
    from diakronos_app.frappe_compat.query import get_all

    zeilen = get_all(
        "Dashboard Widget",
        fields=["widget_id", "api_method"],
    ) or []
    tot = [
        r["widget_id"]
        for r in zeilen
        if r.get("api_method") and lookup(r["api_method"]) is None
    ]
    assert tot == [], "Widget-Zeiger ohne Funktion: %s" % tot


# ── 2. Inhalt von get_conflict_events ─────────────────────────────────────


def test_conflict_events_liefert_die_kollidierenden_terminpaare(als_admin):
    """Nur Termine, die sich auf DERSELBEN Ressource ueberlappen.

    Spiegelt das Original-SQL: Self-JOIN `Element` auf `Element`, Sortierung
    `ressource, element_start`.
    """
    from diakronos_app.api.kronos import ressource_api

    events = ressource_api.get_conflict_events()

    assert {e["name"] for e in events} == {"EL-1", "EL-2"}
    assert all(e["ressource"] == "Jugendraum" for e in events)
    # Die vom Original zugesagten Felder — das Frontend liest genau diese.
    for e in events:
        assert {"name", "element_name", "element_start", "element_end",
                "ressource", "element_calendar"} <= set(e)


def test_conflict_events_sortiert_nach_ressource_dann_start(als_admin):
    from diakronos_app.api.kronos import ressource_api

    events = ressource_api.get_conflict_events()
    schluessel = [(e["ressource"], str(e["element_start"])) for e in events]
    assert schluessel == sorted(schluessel)


def test_conflict_events_ignoriert_paare_verschiedener_ressourcen(als_admin):
    """EL-3 laeuft zeitgleich, aber auf anderer Ressource -> kein Konflikt."""
    from diakronos_app.api.kronos import ressource_api

    events = ressource_api.get_conflict_events()
    assert "EL-3" not in {e["name"] for e in events}


def test_conflict_events_ohne_konflikt_ist_leer(als_admin):
    """Ein Termin, der mit niemandem kollidiert, erzeugt keinen Konflikt.

    Geprueft wird die ZUSATZzeile: EL-4 darf den bestehenden Konflikt
    (EL-1/EL-2) nicht veraendern und selbst keiner sein.
    """
    from diakronos_app.api.kronos import ressource_api
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Element", {
        "name": "EL-4", "element_name": "Allein", "ressource": "Frei",
        "element_calendar": "KAL-JUG",
        "element_start": datetime.datetime(2030, 1, 1, 10, 0, 0),
        "element_end": datetime.datetime(2030, 1, 1, 12, 0, 0),
        "docstatus": 0, "idx": 3,
    })

    namen = {e["name"] for e in ressource_api.get_conflict_events()}
    assert namen == {"EL-1", "EL-2"}, "EL-4 ist allein und darf kein Konflikt sein"


def test_conflict_events_ignoriert_entwuerfe(als_admin):
    """`docstatus != 2` gilt auf BEIDEN Seiten des Joins."""
    from diakronos_app.api.kronos import ressource_api
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Element", {
        "name": "EL-5", "element_name": "Entwurf", "ressource": "Jugendraum",
        "element_calendar": "KAL-JUG",
        "element_start": datetime.datetime(2026, 4, 17, 21, 0, 0),
        "element_end": datetime.datetime(2026, 4, 17, 23, 0, 0),
        "docstatus": 2, "idx": 4,
    })

    assert "EL-5" not in {e["name"] for e in ressource_api.get_conflict_events()}


def test_conflict_events_ignoriert_zeilen_ohne_ressource(als_admin):
    """`WHERE a.ressource IS NOT NULL AND a.ressource != ''` — zwei Termine
    ohne Ort duerfen sich nicht gegenseitig als Konflikt melden (sonst waere
    jeder ''-Wert ein Konflikt mit jedem anderen)."""
    from diakronos_app.api.kronos import ressource_api
    from diakronos_app.frappe_compat.api_helpers import _create

    for nr in (6, 7):
        _create("Element", {
            "name": f"EL-{nr}", "element_name": f"Ohne Ort {nr}", "ressource": "",
            "element_calendar": "KAL-JUG",
            "element_start": datetime.datetime(2026, 5, 1, 10, 0, 0),
            "element_end": datetime.datetime(2026, 5, 1, 12, 0, 0),
            "docstatus": 0, "idx": nr,
        })

    # Der Zwei-Zeilen-Fall: die Zeilen ueberlappen sich, teilen aber keine
    # Ressource — sie sind KEIN Konflikt.
    namen = {e["name"] for e in ressource_api.get_conflict_events()}
    assert "EL-6" not in namen
    assert "EL-7" not in namen
    assert namen == {"EL-1", "EL-2"}


# ── 3. Rechte: Kalenderadministrator ja, Mitglied nein ────────────────────


def test_conflict_events_fuer_kalenderadministrator(als_admin):
    from diakronos_app.api.kronos import ressource_api

    assert ressource_api.get_conflict_events() != []


def test_conflict_events_fuer_plisses_mitglied_verweigert(welt):
    """GEGENRICHUNG: ein angemeldetes Mitglied ohne Kalenderrecht darf die
    Konfliktliste NICHT sehen. Der Fehlerfall aus A1c9 darf nicht zur neuen
    Anmeldemoeglichkeit geworden sein."""
    from diakronos_app.api.kronos import ressource_api

    set_user(ANNA)
    with pytest.raises(FrappePermissionError):
        ressource_api.get_conflict_events()


def test_conflict_events_fuer_guest_verweigert(welt):
    from diakronos_app.api.kronos import ressource_api

    set_user("Guest")
    with pytest.raises(FrappePermissionError):
        ressource_api.get_conflict_events()


def test_conflict_events_fuer_kalendermoderator_erlaubt(welt):
    """Ein Moderator EINER Kalender darf die Konflikte sehen.

    Das entspricht dem Original `confirm_element` (ressource_api.py:249-265),
    das `Administrator` ODER `_is_kalenderadministrator` ODER
    `_is_moderator_of` gelten laesst. In der Compat-Schicht gibt es kein
    DocType-Recht, mit dem sich das Original-`has_permission("Element")`
    abbilden liesse — ohne diese Regel waere die Karte fuer einen
    Kalendermoderator leer, obwohl er die Konflikte seiner Kalender
    aufloesen kann.
    """
    from diakronos_app.api.kronos import ressource_api
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Kalender Moderator", {
        "name": "KM-1",
        "parent": "KAL-JUG",
        "parenttype": "Kalender",
        "parentfield": "kalendermoderatoren",
        "user": BRUNO,
        "docstatus": 0,
        "idx": 1,
    })

    set_user(BRUNO)
    events = ressource_api.get_conflict_events()
    assert {e["name"] for e in events} == {"EL-1", "EL-2"}


# ── 4. get_widget_data: die Karte liefert jetzt Daten statt eines Fehlers ──


def test_widget_data_pending_registrations_liefert_daten(als_admin):
    """DER BEFUND, als Test: HTTP 200, `data` gefuellt, KEIN `error`.

    BF1c/W6: Die Kachel zeigt jetzt die offenen VORSCHLAEGE der moderierten
    Kalender (nach Start sortiert, Vergangenes ausgeblendet) — nicht die
    Ressourcenkonflikte. Genau das verspricht Titel und Sprungziel.
    """
    from diakronos_app.api import dashboard as d

    out = d.get_widget_data("pending-registrations")

    assert "error" not in out, out
    assert out["data"], "Karte liefert keine Vorschlaege, obwohl einer offen ist"
    ids = {e["id"] for e in out["data"]}
    assert ids == {"EL-VORSCHLAG"}, f"Kachel zeigt nicht den Vorschlag: {ids}"
    eintrag = out["data"][0]
    # Keine internen Adressdaten; Titel/Zeit/Kalender sind da.
    assert eintrag["element_name"] == "Neuer Vorschlag"
    assert eintrag["calendar_title"] == "Jugend"


def test_widget_data_pending_registrations_bleibt_403_ohne_rolle(welt):
    """Gegenrichtung am echten Endpunkt: ohne `Kalenderadministrator`
    403 »Zugriff verweigert« — die Karte ist kein offener Lesekanal."""
    from diakronos_app.api import dashboard as d

    set_user(BRUNO)
    with pytest.raises(FrappePermissionError) as err:
        d.get_widget_data("pending-registrations")
    assert "Zugriff verweigert" in str(err.value)


# ── 5. Konfigurationsfehler ist KEIN Oberflaechenfehler ───────────────────


def test_unbekannte_api_method_loggt_statt_fehlerkarte(als_admin, capsys):
    """Der Pfad existiert nicht -> Log-Eintrag, `data: None`, KEIN `error`.

    Genau das war der Witz von A1c9: ein Datenfehler der Konfiguration landete
    als roter Text auf einer Karte, die der Benutzer nicht reparieren kann,
    und in keinem Log, das jemand ansieht.
    """
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Dashboard Widget", {
        "widget_id": "kaputt_verdrahtet",
        "label": "Kaputt verdrahtet",
        "widget_type": "info_card",
        "category": "test",
        "api_method": "diakronos.gibt.es.nicht.gibtsnicht",
        "grid_size": "half",
        "default_position": 20,
        "default_visible": 1,
        "enabled": 1,
        "empty_state_mode": "show_message",
        "empty_state_message": "-",
        "refresh_interval": 0,
    })

    out = d.get_widget_data("kaputt_verdrahtet")

    assert "error" not in out, "Konfigurationsfehler darf keine Fehlerkarte sein"
    assert out["data"] is None
    # Und er ist sichtbar — im Log, nicht in der Oberflaeche.
    log = capsys.readouterr()
    assert "gibtsnicht" in (log.err + log.out)


def test_fehler_in_der_funktion_bleibt_im_error_feld(als_admin):
    """GEGENRICHTUNG zu Test 5a: wirft die *Funktion* selbst, bleibt das
    bisherige Verhalten erhalten (`error`-Feld). Der Konfigurationsfehler hat
    den Datenfehler nicht ersetzt."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.frappe_compat.registry import whitelist

    @whitelist(allow_guest=False)
    def _werfende_methode():
        raise RuntimeError("kaputt")

    _create("Dashboard Widget", {
        "widget_id": "werfende_methode",
        "label": "Werfende Methode",
        "widget_type": "info_card",
        "category": "test",
        "api_method": f"{_werfende_methode.__module__}.{_werfende_methode.__name__}",
        "grid_size": "half",
        "default_position": 21,
        "default_visible": 1,
        "enabled": 1,
        "empty_state_mode": "show_message",
        "empty_state_message": "-",
        "refresh_interval": 0,
    })

    out = d.get_widget_data("werfende_methode")

    assert "error" in out, "Fehler INNERHALB der Funktion muss weiterhin melden"
    assert "kaputt" in out["error"]
    assert out["data"] is None


def test_unbekannte_api_method_ist_kein_403_und_kein_404(als_admin):
    """Nur zur Abgrenzung: der Konfigurationsfehler darf nicht wie ein
    Rechte-/Nicht-gefunden-Fehler aussehen, sonst sucht niemand die Ursache."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Dashboard Widget", {
        "widget_id": "zeiger_ins_leere",
        "label": "Zeiger ins Leere",
        "widget_type": "info_card",
        "category": "test",
        "api_method": "diakronos.kronos.api.ressource_api.gibtsnicht",
        "grid_size": "half",
        "default_position": 22,
        "default_visible": 1,
        "enabled": 1,
        "empty_state_mode": "show_message",
        "empty_state_message": "-",
        "refresh_interval": 0,
    })

    out = d.get_widget_data("zeiger_ins_leere")  # darf nicht werfen
    assert out["widget_id"] == "zeiger_ins_leere"
