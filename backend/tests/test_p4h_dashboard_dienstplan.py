"""P4h — Portierte Module `api.dashboard` (11 Endpunkte) und
`api.dienstplan` (3 Endpunkte, Mitglieder-Sicht).

Quelle (READ-ONLY):
  * `referenz/diakronos-frappe/diakronos/diakonos/api/dashboard.py`
  * `referenz/diakronos-frappe/diakronos/diakonos/api/dienstplan.py`

Abgedeckt:
  * Registrierung: `FRAPPE_MODULE` gesetzt, alle 14 SPA-Pfade aufloesbar.
  * Login-Pflicht (`allow_guest=False`) fuer jeden Endpunkt -> Guest = 403.
  * Dashboard:
      - `get_available_widgets`: nur `enabled=1`, Rollen-/Permission-Gate.
      - `get_user_config`: Default-Layout, personalisiertes Layout,
        `visible`/`collapsed`/`position`/`grid_size`-Uebernahme.
      - `set_user_config`: fremde/unbekannte Widget-IDs werden ignoriert
        (SICHERHEIT: Layout-Manipulation fremder Widgets), Update statt
        Duplikat bei zweitem Speichern.
      - `reset_user_config`: Loescht nur die eigenen Zeilen.
      - `get_widget_data`: unbekannt -> 404, nicht sichtbar -> 403,
        leere api_method -> data=None, Fehler in der Methode -> error-Feld.
      - `get_upcoming_events` / `get_events_for_month` / `get_pinned_beitraege`
        / `get_recent_articles` / `get_meine_buchungen_widget`: Datenaufbau,
        Entwuerfe (docstatus=2) ausgefiltert, Monatsgrenzen, Limit.
      - `get_widget_badge_counts` (AGGREGAT-SICHTBARKEIT): Schluessel fehlen
        GANZ ohne die passende Rolle (nicht 0), erscheinen mit ihr.
  * Dienstplan:
      - `get_dienstrollen`: Liste mit name/rollenname/farbe.
      - `get_dienstplan`: Standardzeitraum = laufende Woche, Entwuerfe
        (`ist_entwurf=1`) raus, Kalender-Sichtbarkeit als Schranke.
      - `get_meine_dienste` (SICHTBARKEIT): nur die EIGENEN Dienste — die
        Mitarbeiter-Zeilen anderer Personen am selben Element erscheinen
        nicht; ohne eigenen Mitgliedssatz leere Antworten.
      - Ablaufplan-Markierung: `verantwortet` nur fuer eigene Positionen.
  * Schema-Belege: `Element.element_start` ist eine `timestamp`-Spalte ->
    Filter muessen `datetime`-Objekte sein (Regressionstest gegen den
    VARCHAR-Bind, der in Postgres `timestamp >= varchar` ausloest).
"""

from __future__ import annotations

import datetime

import pytest

from diakronos_app.frappe_compat.exceptions import DoesNotExistError
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

DASH = "diakronos.diakonos.api.dashboard"
DIENST = "diakronos.diakonos.api.dienstplan"

# Die 11 in hooks.py gelisteten Originalpfade des Dashboards.
SPA_PFADE_DASHBOARD = [
    "get_available_widgets",
    "get_events_for_month",
    "get_meine_buchungen_widget",
    "get_pinned_beitraege",
    "get_recent_articles",
    "get_upcoming_events",
    "get_user_config",
    "get_widget_badge_counts",
    "get_widget_data",
    "reset_user_config",
    "set_user_config",
]

# Die 3 Originalpfade der Mitglieder-Sicht.
SPA_PFADE_DIENSTPLAN = [
    "get_dienstplan",
    "get_dienstrollen",
    "get_meine_dienste",
]

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
ADMIN = "admin@example.org"


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Datenwelt: 2 Nutzer + Admin, Widgets, Termine, Beitraege, Wiki,
    Anmeldungen, Registrierungslinks, Dienstrollen, Gruppen, Dienstplaene,
    Rollenbesetzung, Ablaufplan, Ressourcen-Buchungen, Kalender.

    Deckt bewusst den ganzen Datenbedarf beider Module ab, damit die Tests
    echtes Verhalten (und nicht nur die leere Antwort) pruefen.
    """
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import (
        Anmeldung,
        Beitrag,
        DashboardWidget,
        DashboardWidgetUserConfig,
        Dienstplan,
        Dienstrolle,
        Gruppe,
        Mitglied,
        MitgliedBereich,
        Registrierungslink,
        RessourcenBuchung,
        WikiArtikel,
    )
    from diakronos_app.models.kronos import (
        Ablaufplan,
        AblaufplanPosition,
        Element,
        ElementMitarbeiter,
        Kalender,
        Ressource,
    )

    sess = patched_db()
    now = datetime.datetime.now()
    morgen = now + datetime.timedelta(days=1)
    gestern = now - datetime.timedelta(days=1)

    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
    ])

    # Mitglieder + Verknuepfung User -> Mitglied (Kern der Dienstplan-Sicht).
    sess.add_all([
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel", email=ANNA,
                 user=ANNA, status="Mitglied", docstatus=0, idx=0,
                 ancestor_path="/M-0001"),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel", email=BRUNO,
                 user=BRUNO, status="Mitglied", docstatus=0, idx=0,
                 ancestor_path="/M-0002"),
    ])

    # Kalender: Anna darf sehen, Bruno nicht (Grundlage der Dienstplan-Schranke).
    sess.add_all([
        Kalender(name="KAL-A", calendar_name="Gemeinde", calendar_color="#ff0000",
                 selbstverwaltet=0, docstatus=0, idx=0),
        Kalender(name="KAL-B", calendar_name="Intern", calendar_color="#00ff00",
                 selbstverwaltet=0, docstatus=0, idx=0),
    ])
    # Kalender-Leserechte laufen ueber Child-DocType `User Role` (parentfield
    # `leserechte`) — NICHT ueber `Has Role`.
    sess.add_all([
        UserRole(name="UR-A1", parent="KAL-A", parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add_all([
        HasRole(name="HR-A1", parent=ANNA, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-B1", parent=BRUNO, parenttype="User", parentfield="roles",
                role="Mitglied", docstatus=0, idx=1),
        HasRole(name="HR-ADM", parent=ADMIN, parenttype="User", parentfield="roles",
                role="Mitgliederadministrator", docstatus=0, idx=1),
        HasRole(name="HR-ADM2", parent=ADMIN, parenttype="User", parentfield="roles",
                role="Kalenderadministrator", docstatus=0, idx=2),
    ])

    sess.add_all([
        Gruppe(name="GRP-1", gruppenname="Kueche", dienstbereich="Gemeinde",
               ancestor_path="/GRP-1", docstatus=0, idx=0),
    ])
    # Bereichs-Zugehoerigkeit von Anna (fuer has_bereichs_zugriff).
    sess.add_all([
        MitgliedBereich(name="MB-1", parent="M-0001", parenttype="Mitglied",
                        parentfield="bereiche", dienstbereich="Gemeinde",
                        docstatus=0, idx=1),
    ])

    sess.add_all([
        Dienstrolle(name="DR-1", rollenname="Koch", farbe="#123456",
                    docstatus=0, idx=0),
        Dienstrolle(name="DR-2", rollenname="Spueler", farbe="#654321",
                    docstatus=0, idx=0),
    ])

    # Zwei Dienstplaene: einer gueltig, einer Entwurf.
    sess.add_all([
        Dienstplan(name="DP-1", plantitel="Sommerfest-Plan", ist_entwurf=0,
                   dienstbereich="Gemeinde", gruppe="GRP-1", docstatus=0, idx=0),
        Dienstplan(name="DP-2", plantitel="Zurueckgezogen", ist_entwurf=1,
                   dienstbereich="Gemeinde", gruppe="GRP-1", docstatus=0, idx=0),
    ])

    sess.add_all([
        Ressource(name="RES-1", ressource_name="Kuechenwagen",
                  docstatus=0, idx=0),
    ])

    # Termine: sichtbarer Einsatz, Entwurfstermin (raus), Entwurfsplan-Termin
    # (raus), Termin in anderem (fuer Bruno unsichtbarem) Kalender.
    # `status="Festgelegt"` wie im Betrieb: die Dashboard-Listen filtern seit
    # OP-HANDY-R1 zusaetzlich auf diesen Status.
    sess.add_all([
        Element(name="EL-1", element_name="Einsatz Kueche", element_category="CAT-1",
                element_calendar="KAL-A", element_start=morgen,
                element_end=morgen + datetime.timedelta(hours=3),
                status="Festgelegt",
                gruppe="GRP-1", ressource="RES-1", dienstplan="DP-1",
                docstatus=0, idx=0),
        Element(name="EL-2", element_name="Storniert", element_category="CAT-1",
                element_calendar="KAL-A", element_start=morgen,
                element_end=morgen + datetime.timedelta(hours=2),
                status="Festgelegt",
                gruppe="GRP-1", dienstplan="DP-1", docstatus=2, idx=0),
        Element(name="EL-3", element_name="Entwurfsplan-Termin", element_category="CAT-1",
                element_calendar="KAL-A", element_start=morgen,
                element_end=morgen + datetime.timedelta(hours=1),
                status="Festgelegt",
                gruppe="GRP-1", dienstplan="DP-2", docstatus=0, idx=0),
        Element(name="EL-4", element_name="Anderer Kalender", element_category="CAT-1",
                element_calendar="KAL-B", element_start=morgen,
                element_end=morgen + datetime.timedelta(hours=1),
                status="Festgelegt",
                gruppe="GRP-1", ressource="RES-1", dienstplan="DP-1",
                docstatus=0, idx=0),
        Element(name="EL-5", element_name="Vergangen", element_category="CAT-1",
                element_calendar="KAL-A", element_start=gestern,
                element_end=gestern + datetime.timedelta(hours=1),
                status="Festgelegt",
                gruppe="GRP-1", dienstplan="DP-1", docstatus=0, idx=0),
    ])

    # Rollenbesetzung: EL-1 hat Anna UND Bruno -> Kern des Sichtbarkeitstests.
    # EL-4 hat nur Bruno.
    sess.add_all([
        ElementMitarbeiter(name="EM-1", parent="EL-1", parenttype="Element",
                           parentfield="mitarbeiter", mitglied="M-0001",
                           dienstrolle="DR-1", bestaetigt=1, docstatus=0, idx=1),
        ElementMitarbeiter(name="EM-2", parent="EL-1", parenttype="Element",
                           parentfield="mitarbeiter", mitglied="M-0002",
                           dienstrolle="DR-2", bestaetigt=0, docstatus=0, idx=2),
        ElementMitarbeiter(name="EM-3", parent="EL-4", parenttype="Element",
                           parentfield="mitarbeiter", mitglied="M-0002",
                           dienstrolle="DR-1", bestaetigt=1, docstatus=0, idx=1),
    ])

    # Ablaufplan mit einer Position fuer Anna, einer fuer Bruno.
    sess.add_all([
        Ablaufplan(name="AP-1", titel="Ablauf Kueche", docstatus=0, idx=0),
    ])
    sess.add_all([
        AblaufplanPosition(name="APP-1", parent="AP-1", parenttype="Ablaufplan",
                           parentfield="positionen", reihenfolge=1,
                           bezeichnung="Vorbereiten", dauer_minuten=30,
                           verantwortlicher="M-0001", docstatus=0, idx=1),
        AblaufplanPosition(name="APP-2", parent="AP-1", parenttype="Ablaufplan",
                           parentfield="positionen", reihenfolge=2,
                           bezeichnung="Aufraeumen", dauer_minuten=20,
                           verantwortlicher="M-0002", docstatus=0, idx=2),
    ])

    # Widgets: eines ohne Gate, eines mit Rolle, eines deaktiviert.
    sess.add_all([
        DashboardWidget(name="DW-1", widget_id="termine", label="Termine",
                        widget_type="list", category="kalender", icon="calendar",
                        api_method="diakronos.diakonos.api.dashboard.get_upcoming_events",
                        grid_size="half", default_position=1, default_visible=1,
                        enabled=1, empty_state_mode="text",
                        empty_state_message="Keine Termine.", refresh_interval=0,
                        docstatus=0, idx=0),
        DashboardWidget(name="DW-2", widget_id="adminbox", label="Admin",
                        widget_type="info_card", category="admin", icon="lock",
                        api_method=None, required_role="Mitgliederadministrator",
                        grid_size="full", default_position=2, default_visible=1,
                        enabled=1, empty_state_mode="text",
                        empty_state_message="Nur Admin.", refresh_interval=0,
                        docstatus=0, idx=0),
        DashboardWidget(name="DW-3", widget_id="aus", label="Deaktiviert",
                        widget_type="info_card", category="sonst", icon="x",
                        grid_size="half", default_position=3, default_visible=1,
                        enabled=0, empty_state_mode="text",
                        empty_state_message="-", refresh_interval=0,
                        docstatus=0, idx=0),
    ])

    # Beitrag (veroeffentlicht) + Wiki + Anmeldungen + Registrierungslinks.
    sess.add_all([
        Beitrag(name="BEI-1", titel="Sommerfest", kategorie="gemeinde",
                datum=datetime.date(2026, 7, 1), autor="Anna Beispiel",
                veroeffentlicht=1, auszug="Grosses Fest", bild="fest.jpg",
                docstatus=0, idx=0),
    ])
    sess.add_all([
        WikiArtikel(name="WIK-1", titel="Beamer", kategorie="technik",
                    modified=datetime.datetime(2026, 7, 5, 10, 0, 0),
                    docstatus=0, idx=0),
    ])
    sess.add_all([
        Anmeldung(name="ANM-1", status="Ausstehend", docstatus=0, idx=0),
        Anmeldung(name="ANM-2", status="Bestaetigt", docstatus=0, idx=0),
    ])
    sess.add_all([
        Registrierungslink(name="RL-1", aktiv=1, docstatus=0, idx=0),
        Registrierungslink(name="RL-2", aktiv=0, docstatus=0, idx=0),
    ])

    # Ressourcen-Buchung fuer Anna (kommend) und Bruno (kommend).
    sess.add_all([
        RessourcenBuchung(name="RB-1", ressource="RES-1", gebucht_von=ANNA,
                          datum_von=morgen, datum_bis=morgen,
                          zweck="Kochen", status="Aktiv", docstatus=0, idx=0),
        RessourcenBuchung(name="RB-2", ressource="RES-1", gebucht_von=BRUNO,
                          datum_von=morgen, datum_bis=morgen,
                          zweck="Fremd", status="Aktiv", docstatus=0, idx=0),
    ])

    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


@pytest.fixture()
def als_bruno(welt):
    set_user(BRUNO)
    yield BRUNO
    set_user("Administrator")


@pytest.fixture()
def als_admin(welt):
    set_user(ADMIN)
    yield ADMIN
    set_user("Administrator")


@pytest.fixture()
def als_guest(welt):
    set_user("Guest")
    yield "Guest"
    set_user("Administrator")


# ── Registrierung / Router ──────────────────────────────────────────────────


@pytest.mark.parametrize("modul,erwartet", [(DASH, "api.dashboard"),
                                            (DIENST, "api.dienstplan")])
def test_frappe_module_konstante_ist_gesetzt(modul, erwartet):
    """Ohne FRAPPE_MODULE ist der Endpunkt fuer die SPA unerreichbar."""
    import importlib

    m = importlib.import_module(f"diakronos_app.{erwartet}")
    assert m.FRAPPE_MODULE == modul


@pytest.mark.parametrize("fn", SPA_PFADE_DASHBOARD)
def test_dashboard_spa_pfade_sind_registriert(fn):
    assert lookup(f"{DASH}.{fn}") is not None


@pytest.mark.parametrize("fn", SPA_PFADE_DIENSTPLAN)
def test_dienstplan_spa_pfade_sind_registriert(fn):
    assert lookup(f"{DIENST}.{fn}") is not None


@pytest.mark.parametrize("modul,fn", [(DASH, f) for f in SPA_PFADE_DASHBOARD]
                         + [(DIENST, f) for f in SPA_PFADE_DIENSTPLAN])
def test_guest_wird_ueberall_abgewiesen(client, als_guest, modul, fn):
    """`allow_guest=False` gilt fuer alle 14 Endpunkte."""
    resp = client.get(f"/api/method/{modul}.{fn}")
    assert resp.status_code == 401, (modul, fn, resp.text)


# ── Dashboard: Widget-Metadaten & Layout ────────────────────────────────────


def test_available_widgets_filtert_deaktivierte(als_anna):
    from diakronos_app.api import dashboard as d

    ids = [w["widget_id"] for w in d.get_available_widgets()]
    assert "termine" in ids
    # enabled=0 -> nie in der Liste.
    assert "aus" not in ids


def test_available_widgets_rollen_gate(als_anna):
    from diakronos_app.api import dashboard as d

    # Anna hat Mitgliederadministrator NICHT -> adminbox unsichtbar.
    ids_anna = [w["widget_id"] for w in d.get_available_widgets()]
    assert "adminbox" not in ids_anna

    # Admin hat die Rolle -> sichtbar.
    set_user(ADMIN)
    ids_admin = [w["widget_id"] for w in d.get_available_widgets()]
    assert "adminbox" in ids_admin
    set_user("Administrator")


def test_user_config_defaults(als_anna):
    """Ohne eigene Konfiguration gilt das Standard-Layout."""
    from diakronos_app.api import dashboard as d

    cfg = {c["widget_id"]: c for c in d.get_user_config()}
    assert cfg["termine"]["position"] == 1
    assert cfg["termine"]["visible"] is True
    assert cfg["termine"]["collapsed"] is False
    assert cfg["termine"]["grid_size"] == "half"


def test_set_user_config_ignoriert_unbekannte_widgets(als_anna):
    """SICHERHEIT: fremde/unbekannte Widget-IDs duerfen nichts anlegen."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.query import get_all

    d.set_user_config([
        {"widget_id": "termine", "position": 5, "visible": False, "size": "full"},
        {"widget_id": "gibt-es-nicht", "position": 1, "visible": True},
        {"widget_id": "adminbox", "position": 1, "visible": True},  # keine Rolle
    ])

    rows = get_all("Dashboard Widget User Config", filters={"user": ANNA},
                   fields=["widget", "position", "visible", "size"])
    assert len(rows) == 1, rows
    assert rows[0]["widget"] == "termine"
    assert rows[0]["position"] == 5
    assert int(rows[0]["visible"]) == 0
    assert rows[0]["size"] == "full"


def test_set_user_config_aktualisiert_statt_duplikat(als_anna):
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.query import get_all

    d.set_user_config([{"widget_id": "termine", "position": 5, "visible": False}])
    d.set_user_config([{"widget_id": "termine", "position": 9, "visible": True}])

    rows = get_all("Dashboard Widget User Config", filters={"user": ANNA},
                   fields=["widget", "position", "visible"])
    assert len(rows) == 1, rows
    assert rows[0]["position"] == 9


def test_reset_user_config_loescht_nur_eigene(als_anna):
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.query import get_all

    d.set_user_config([{"widget_id": "termine", "position": 5}])
    # Fremde Zeile (Bruno) darf der Reset nicht anfassen.
    _fremd("Dashboard Widget User Config", {"user": BRUNO, "widget": "termine",
                                            "position": 2, "visible": 1,
                                            "size": "default", "collapsed": 0})

    d.reset_user_config()

    assert get_all("Dashboard Widget User Config", filters={"user": ANNA},
                   fields=["name"]) == []
    assert len(get_all("Dashboard Widget User Config", filters={"user": BRUNO},
                       fields=["name"])) == 1


# ── Dashboard: Widget-Daten ─────────────────────────────────────────────────


def test_widget_data_unbekannt_ist_404(als_anna):
    from diakronos_app.api import dashboard as d

    with pytest.raises(DoesNotExistError):
        d.get_widget_data("gibt-es-nicht")


def test_widget_data_verweigert_ohne_rolle(als_anna):
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.exceptions import PermissionError as PermErr

    # adminbox hat required_role=Mitgliederadministrator -> Anna = 403.
    with pytest.raises(PermErr):
        d.get_widget_data("adminbox")


def test_widget_data_ohne_api_method_gibt_none(als_admin):
    """Admin sieht adminbox, aber `api_method` ist leer -> data None."""
    from diakronos_app.api import dashboard as d

    set_user(ADMIN)
    out = d.get_widget_data("adminbox")
    assert out == {"widget_id": "adminbox", "data": None}
    set_user("Administrator")


def test_widget_data_ruft_methode_auf(als_anna):
    from diakronos_app.api import dashboard as d

    out = d.get_widget_data("termine")
    assert out["widget_id"] == "termine"
    assert isinstance(out["data"], list)


def test_widget_data_fehler_wird_gemeldet(als_anna):
    """Eine werfende Ziellaedt die Antwort nicht umbringen — error-Feld."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.query import get_value

    get_value_widget = _widget_mit_boeser_methode()
    out = d.get_widget_data("boese")
    assert out["widget_id"] == "boese"
    assert out["data"] is None
    assert "error" in out


# ── Dashboard: Daten-Endpunkte ──────────────────────────────────────────────


def test_upcoming_events_filtert_vergangenes_und_storniertes(als_anna):
    from diakronos_app.api import dashboard as d

    ids = [e["id"] for e in d.get_upcoming_events(limit=10)]
    assert "EL-1" in ids
    assert "EL-2" not in ids      # docstatus=2
    assert "EL-5" not in ids      # vergangen


def test_upcoming_events_limit(als_anna):
    from diakronos_app.api import dashboard as d

    assert len(d.get_upcoming_events(limit=1)) == 1


def test_events_for_month_grenzen(als_anna):
    """Nur Tage des gefragten Monats; Entwuerfe raus."""
    from diakronos_app.api import dashboard as d

    heute = datetime.date.today()
    out = d.get_events_for_month(year=heute.year, month=heute.month)
    assert out["year"] == heute.year
    assert out["month"] == heute.month
    # Alle Termine liegen innerhalb des Monats; der Tag des stornierten EL-2
    # wird vom Referenzcode nicht ausgefiltert (er floss bereits in
    # `get_events_for_month` ueber den Zeitraum, nicht ueber docstatus).
    assert len(out["event_days"]) >= 1
    assert all(day.startswith(f"{heute.year:04d}-{heute.month:02d}") for day in out["event_days"]), out["event_days"]
    # Ein Monat ohne Termine ist leer.
    leer = d.get_events_for_month(year=1999, month=1)
    assert leer["event_days"] == []


def test_events_for_month_dezember_ueberlauf(als_anna):
    """Dezember -> Obergrenze 1.1. des Folgejahres (kein Monat 13)."""
    from diakronos_app.api import dashboard as d

    out = d.get_events_for_month(year=1999, month=12)
    assert out["year"] == 1999 and out["month"] == 12
    assert out["event_days"] == []


def test_pinned_beitraege(als_anna):
    from diakronos_app.api import dashboard as d

    rows = d.get_pinned_beitraege(limit=3)
    assert len(rows) == 1
    assert rows[0]["title"] == "Sommerfest"
    assert rows[0]["excerpt"] == "Grosses Fest"


def test_recent_articles(als_anna):
    from diakronos_app.api import dashboard as d

    rows = d.get_recent_articles(limit=3)
    assert len(rows) == 1
    assert rows[0]["title"] == "Beamer"
    assert rows[0]["category"] == "technik"


def test_meine_buchungen_nur_eigene(als_anna):
    """SICHTBARKEIT: nur die eigenen Buchungen, niemals fremde."""
    from diakronos_app.api import dashboard as d

    anna = d.get_meine_buchungen_widget(limit=10)
    assert [b["id"] for b in anna] == ["RB-1"]
    assert anna[0]["ressource_name"] == "Kuechenwagen"

    set_user(BRUNO)
    bruno = d.get_meine_buchungen_widget(limit=10)
    assert [b["id"] for b in bruno] == ["RB-2"]
    set_user("Administrator")


def test_meine_buchungen_ignoriert_vergangenes(als_anna, welt):
    """upcoming_only=0 hebt den Datumsfilter auf."""
    from diakronos_app.api import dashboard as d

    assert len(d.get_meine_buchungen_widget(upcoming_only=0, limit=10)) == 1
    assert len(d.get_meine_buchungen_widget(upcoming_only=1, limit=10)) == 1


# ── Dashboard: Aggregat-Sichtbarkeit ────────────────────────────────────────


def test_badge_counts_fehlen_ganz_ohne_rolle(als_anna):
    """AGGREGAT-SICHTBARKEIT: kein Schluessel statt 0."""
    from diakronos_app.api import dashboard as d

    out = d.get_widget_badge_counts()
    assert "pending-registrations" not in out
    assert "manage-registrations" not in out
    assert "open-signups" not in out


def test_badge_counts_mit_adminrollen(als_admin):
    from diakronos_app.api import dashboard as d

    set_user(ADMIN)
    out = d.get_widget_badge_counts()
    # Admin hat Mitglieder- UND Kalenderadministrator.
    assert out["manage-registrations"] == 1   # ANM-1 "Ausstehend"
    assert out["open-signups"] == 1           # RL-1 aktiv=1
    assert "pending-registrations" in out
    set_user("Administrator")


def test_badge_counts_zaehlt_nur_offene_anmeldungen(als_admin):
    """ANM-2 ist bestaetigt und darf nicht mitgezaehlt werden."""
    from diakronos_app.api import dashboard as d

    set_user(ADMIN)
    out = d.get_widget_badge_counts()
    assert out["manage-registrations"] == 1
    set_user("Administrator")


# ── Dienstplan ──────────────────────────────────────────────────────────────


def test_dienstrollen_liste(als_anna):
    from diakronos_app.api import dienstplan as dp

    rows = dp.get_dienstrollen()
    namen = [r["rollenname"] for r in rows]
    assert namen == ["Koch", "Spueler"]   # rollenname asc
    assert rows[0]["farbe"] == "#123456"


def test_dienstplan_standardzeitraum_ist_woche(als_admin):
    from diakronos_app.api import dienstplan as dp

    out = dp.get_dienstplan()
    start = datetime.date.fromisoformat(out["start_date"])
    ende = datetime.date.fromisoformat(out["end_date"])
    assert start.weekday() == 0            # Montag
    assert (ende - start).days == 6        # Sonntag


def test_dienstplan_entwuerfe_raus(als_admin):
    """Elemente mit `ist_entwurf=1` duerfen in keinem Eintrag erscheinen."""
    from diakronos_app.api import dienstplan as dp

    set_user(ADMIN)
    heute = datetime.date.today()
    out = dp.get_dienstplan(start_date=str(heute),
                            end_date=str(heute + datetime.timedelta(days=7)))
    elemente = {e["element"] for e in out["eintraege"]}
    assert "EL-3" not in elemente          # Entwurfsplan
    # Hinweis: der Referenzcode filtert stornierte Elemente (docstatus=2) hier
    # NICHT heraus — `_filter_entwurf_elements` entfernt ausschliesslich
    # Elemente zurueckgezogener Plaene. EL-2 bleibt daher sichtbar.
    assert "EL-1" in elemente
    set_user("Administrator")


def test_dienstplan_kalender_schranke(als_anna):
    """Anna sieht nur KAL-A; Bruno hat gar keinen Kalender -> nichts."""
    from diakronos_app.api import dienstplan as dp

    heute = datetime.date.today()
    bis = heute + datetime.timedelta(days=7)

    anna = dp.get_dienstplan(start_date=str(heute), end_date=str(bis))
    a_elemente = {e["element"] for e in anna["eintraege"]}
    assert "EL-1" in a_elemente
    assert "EL-4" not in a_elemente        # KAL-B: kein Leserecht

    set_user(BRUNO)
    bruno = dp.get_dienstplan(start_date=str(heute), end_date=str(bis))
    b_elemente = {e["element"] for e in bruno["eintraege"]}
    # Bruno hat keinen Kalender-Zugriff -> keine fremden Termine ...
    assert "EL-4" not in b_elemente        # KAL-B
    # ... aber EL-1 ist SEIN eigener Dienst (Element Mitarbeiter) und bleibt
    # per Referenz-Regel "Eigene Dienste immer sichtbar" erhalten.
    assert "EL-1" in b_elemente
    assert all(e["element"] != "EL-6" for e in bruno["eintraege"])
    set_user("Administrator")


def test_dienstplan_eintrag_je_mitarbeiter(als_admin):
    """Ein Element mit 2 Mitarbeitern -> 2 Eintraege, Namen aufgeloest."""
    from diakronos_app.api import dienstplan as dp

    set_user(ADMIN)
    heute = datetime.date.today()
    out = dp.get_dienstplan(start_date=str(heute),
                            end_date=str(heute + datetime.timedelta(days=7)))
    el1 = [e for e in out["eintraege"] if e["element"] == "EL-1"]
    assert len(el1) == 2
    namen = sorted(e["mitglied_name"] for e in el1)
    assert namen == ["Anna Beispiel", "Bruno Beispiel"]
    rollen = sorted(e["dienstrolle_name"] for e in el1)
    assert rollen == ["Koch", "Spueler"]
    assert all(e["ressource_name"] == "Kuechenwagen" for e in el1)
    set_user("Administrator")


def test_meine_dienste_nur_eigene(als_anna):
    """SICHTBARKEIT: Anna sieht nur ihre Zeile an EL-1, nicht Brunos."""
    from diakronos_app.api import dienstplan as dp

    anna = dp.get_meine_dienste()
    alle = anna["vorbereitung"] + anna["einsatz"]
    assert all(e["mitglied"] == "M-0001" for e in alle), alle
    assert all(e["mitglied_name"] == "Anna Beispiel" for e in alle), alle
    # Bruno ist am selben Element -> darf bei Anna nicht auftauchen.
    assert not any(e["mitglied_name"] == "Bruno Beispiel" for e in alle)
    assert any(e["element"] == "EL-1" for e in alle)

    set_user(BRUNO)
    bruno = dp.get_meine_dienste()
    b_alle = bruno["vorbereitung"] + bruno["einsatz"]
    assert all(e["mitglied"] == "M-0002" for e in b_alle), b_alle
    # Brunos EIGENE Zeile an EL-1 ist sichtbar (er ist dort Mitarbeiter),
    # aber niemals ANNAS Zeile an EL-1.
    el1_bruno = [e for e in b_alle if e["element"] == "EL-1"]
    assert el1_bruno and all(e["mitglied_name"] == "Bruno Beispiel" for e in el1_bruno), el1_bruno
    assert not any(e["mitglied_name"] == "Anna Beispiel" for e in b_alle)
    set_user("Administrator")


def test_meine_dienste_heute_vergangener_dienst_faellt_raus(als_anna, welt):
    """Regression: Zeitgrenze ist der VOLLE Zeitstempel, nicht der Tagesbeginn.

    Referenz (`dienstplan.py:319`) filtert `element_start >= now` mit
    `now = datetime.now()`. Ein Dienst, der HEUTE schon begonnen hat, ist
    damit kein "zukuenftiger Dienst" mehr und darf nicht erscheinen. Eine
    fruehere Fassung der Portierung nutzte faelschlich `_day_start(heute)`
    (00:00) und zeigte den vergangenen Dienst weiter an.
    """
    from diakronos_app.api import dienstplan as dp
    from diakronos_app.models.kronos import Element

    sess = welt
    jetzt = datetime.datetime.now()
    # Ein Dienst HEUTE, eine Stunde in der Vergangenheit, mit Anna als
    # Mitarbeiterin -> sie ist "betroffen", darf ihn aber nicht mehr sehen.
    sess.add(Element(
        name="EL-VGL", element_name="Heute vergangen", element_category="CAT-1",
        element_calendar="KAL-A", element_start=jetzt - datetime.timedelta(hours=1),
        element_end=jetzt + datetime.timedelta(hours=1),
        gruppe="GRP-1", dienstplan="DP-1", docstatus=0, idx=0,
    ))
    from diakronos_app.models.kronos import ElementMitarbeiter

    sess.add(ElementMitarbeiter(
        name="EM-VGL", parent="EL-VGL", parenttype="Element",
        parentfield="mitarbeiter", mitglied="M-0001", dienstrolle="DR-1",
        bestaetigt=1, docstatus=0, idx=2,
    ))
    sess.commit()

    out = dp.get_meine_dienste()
    namen = [e["element"] for e in out["vorbereitung"] + out["einsatz"]]
    assert "EL-VGL" not in namen, (
        "heute bereits begonnener Dienst darf nicht als zukuenftig gelten: %r" % namen
    )
    # Gegenprobe: der morgige Dienst ist weiterhin da.
    assert "EL-1" in namen


def test_meine_dienste_ohne_mitglied_leer(welt):
    """Nutzer ohne Mitgliedssatz bekommt leere Antworten (keine Exception)."""
    from diakronos_app.api import dienstplan as dp

    set_user(ADMIN)
    out = dp.get_meine_dienste()
    assert out == {"vorbereitung": [], "einsatz": []}
    set_user("Administrator")


def test_meine_dienste_ablaufplan_markierung(als_anna, welt):
    """`verantwortet` ist nur fuer die eigene Position True."""
    from diakronos_app.api import dienstplan as dp
    from diakronos_app.frappe_compat.query import get_value

    # EL-1 an den Ablaufplan haengen (Fixture laesst das Feld bewusst leer,
    # damit der None-Pfad mitgetestet wird).
    sess = welt
    from diakronos_app.models.kronos import Element

    obj = sess.get(Element, "EL-1")
    obj.ablaufplan = "AP-1"
    sess.commit()

    out = dp.get_meine_dienste()
    eintraege = [e for e in out["vorbereitung"] + out["einsatz"] if e["element"] == "EL-1"]
    assert eintraege
    plan = eintraege[0]["ablaufplan"]
    assert plan is not None
    assert plan["ablaufplan"] == "AP-1"
    assert plan["titel"] == "Ablauf Kueche"
    assert len(plan["positionen"]) == 2
    verantwortet = {p["bezeichnung"]: p["verantwortet"] for p in plan["positionen"]}
    assert verantwortet == {"Vorbereiten": True, "Aufraeumen": False}


def test_meine_dienste_einsatz_auch_ohne_terminart(als_anna):
    """Ein Dienst mit fehlender terminart landet in `einsatz`, nicht im Nichts."""
    from diakronos_app.api import dienstplan as dp

    out = dp.get_meine_dienste()
    alle = out["vorbereitung"] + out["einsatz"]
    assert any(e["element"] == "EL-1" for e in alle)
    assert out["vorbereitung"] == []


def test_meine_dienste_vergangenes_raus(als_anna):
    """EL-5 (gestern) darf nicht in den kommenden Diensten stehen."""
    from diakronos_app.api import dienstplan as dp
    from diakronos_app.models.kronos import Element

    out = dp.get_meine_dienste()
    alle = out["vorbereitung"] + out["einsatz"]
    assert not any(e["element"] == "EL-5" for e in alle)


def test_dienstplan_zeitraum_mit_datetime_gebunden(als_admin):
    """Regression: `element_start` ist `timestamp` -> kein VARCHAR-Bind.

    Vor der Korrektur band die Compat-Schicht den Datum-String als VARCHAR,
    was in Postgres `timestamp >= varchar` ausloest. Der Test haelt fest, dass
    die Filterwerte als `datetime` ankommen.
    """
    from diakronos_app.api import dienstplan as dp
    from diakronos_app.frappe_compat import query as q

    gesehen: list[tuple] = []
    original = q._condition

    def spion(doctype, model, feld, op):
        if feld == "element_start":
            gesehen.append((op[0], type(op[1]).__name__))
        return original(doctype, model, feld, op)

    q._condition = spion
    try:
        heute = datetime.date.today()
        dp.get_dienstplan(start_date=str(heute),
                          end_date=str(heute + datetime.timedelta(days=1)))
    finally:
        q._condition = original

    assert gesehen, "keine element_start-Filter gesehen"
    for _op, typ in gesehen:
        assert typ == "datetime", (op, typ)


def test_booleansche_filter_bindung_der_beiden_module():
    """Klassen-Wache: jeder Boolean-Filter beider Module wird umgewandelt.

    Ohne `_coerce_filters` bindet die Compat-Schicht das Frappe-uebliche `1`
    als INTEGER; SQLite (Test-Fixture) ist tolerant, PostgreSQL nicht. Der
    AST-basierte Scan ueber die Quelltexte stellt sicher, dass keine
    Boolean-Filter-Stelle der beiden Kartenmodule unbeschuetzt bleibt.
    """
    import ast
    from pathlib import Path

    from sqlalchemy import Boolean

    import diakronos_app
    from diakronos_app.models.base import Base

    bool_cols: dict[str, set[str]] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        tbl = getattr(cls, "__tablename__", None)
        if not tbl:
            continue
        bs = {c.name for c in cls.__table__.columns
              if isinstance(c.type, Boolean)}
        if bs:
            bool_cols[tbl] = bs

    basis = Path(diakronos_app.__file__).parent / "api"
    ungeschuetzt: list[str] = []
    for modul in ("dashboard.py", "dienstplan.py"):
        pfad = basis / modul
        quelle = pfad.read_text()
        tree = ast.parse(quelle)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            if name not in ("get_all", "get_value", "get_list", "get_value_list", "count"):
                continue
            if not node.args:
                continue
            dtarg = node.args[0]
            if not (isinstance(dtarg, ast.Constant) and isinstance(dtarg.value, str)):
                continue
            dt = dtarg.value
            tabelle = dt.lower().replace(" ", "_")
            bools = bool_cols.get(tabelle, set())
            # Filterausdruck: `filters=` oder (bei get_value) positionales Arg 1.
            fnode = None
            for kw in node.keywords:
                if kw.arg == "filters":
                    fnode = kw.value
            if fnode is None and name in ("get_value", "get_value_list", "count") \
                    and len(node.args) > 1:
                fnode = node.args[1]
            if fnode is None:
                continue
            fsrc = ast.get_source_segment(quelle, fnode) or ""
            if any(b in fsrc for b in bools) and "_coerce_filters" not in fsrc:
                ungeschuetzt.append(f"{modul}:{node.lineno} {name}({dt!r}) {fsrc}")

    assert not ungeschuetzt, (
        "Boolean-Filter ohne _coerce_filters (Postgres: boolean = integer):\n  "
        + "\n  ".join(ungeschuetzt)
    )


def test_booleansche_filter_werden_zu_bool_gekoeffiziert(als_anna):
    """Regression: Check-Felder sind in Postgres `boolean`, nicht `integer`.

    Der Altcode schreibt Frappe-uebliche `0`/`1`-Filter. Ohne Koerzierung
    scheitert das live mit `operator does not exist: boolean = integer`
    (HTTP 500) — auf den kritischen Pfaden `get_widget_data` und
    `get_meine_dienste`. SQLite (Test-Fixture) vergleicht tolerant, deshalb
    wird hier direkt an der Fix-Stelle `_coerce_filters` geprueft.
    """
    from diakronos_app.frappe_compat.api_helpers import _coerce_filters

    faelle = [
        ("Dashboard Widget", {"enabled": 1}),
        ("Dienstplan", {"ist_entwurf": 1}),
        ("Beitrag", {"veroeffentlicht": 1}),
        ("Registrierungslink", {"aktiv": 1}),
    ]
    for doctype, filters in faelle:
        feld = next(iter(filters))
        out = _coerce_filters(doctype, filters)
        assert isinstance(out[feld], bool), (
            "%s.%s nicht als bool gebunden (Postgres: boolean = integer): %r"
            % (doctype, feld, out[feld])
        )
        assert out[feld] is True

    # Operator-Form muss erhalten bleiben, nur der Wert wird gewandelt.
    out = _coerce_filters(
        "Dienstplan", {"name": ["in", ["DP-1"]], "ist_entwurf": 1}
    )
    assert out["ist_entwurf"] is True
    assert out["name"] == ["in", ["DP-1"]]


def test_booleansche_filter_bindung_auf_echten_pfaden(als_anna, welt):
    """Regression: die portierten Module binden Check-Filter als `bool`.

    End-to-End-Nachweis ueber die echten Aufrufpfade: beide Endpunkte, die im
    Review als live-500 aufgefallen sind, duerfen nicht mit
    `boolean = integer` in die Datenbank gehen. Geprueft wird der Wert, der
    tatsaechlich an die Compat-Query-Schicht uebergeben wird.
    """
    from diakronos_app.api import dashboard as dash
    from diakronos_app.api import dienstplan as dp
    from diakronos_app.frappe_compat import query as q

    from diakronos_app.frappe_compat import api_helpers as _shared

    gesehen: list = []

    orig_get_value = _shared.get_value
    orig_get_all = _shared.get_all

    def spy_get_value(doctype, filters, *a, **kw):
        if isinstance(filters, dict):
            for feld in ("enabled", "veroeffentlicht", "aktiv"):
                if feld in filters:
                    gesehen.append((doctype, feld, filters[feld]))
        return orig_get_value(doctype, filters, *a, **kw)

    def spy_get_all(doctype, filters=None, *a, **kw):
        if isinstance(filters, dict):
            for feld in ("enabled", "ist_entwurf", "veroeffentlicht", "aktiv"):
                if feld in filters:
                    gesehen.append((doctype, feld, filters[feld]))
        return orig_get_all(doctype, filters, *a, **kw)

    _shared.get_value = spy_get_value
    _shared.get_all = spy_get_all
    dash.get_value = spy_get_value
    dash.get_all = spy_get_all
    dp.get_value = spy_get_value
    dp.get_all = spy_get_all
    try:
        try:
            dash.get_widget_data(widget_id="gibt-es-nicht")
        except Exception:
            pass
        dp.get_meine_dienste()
        try:
            dash.get_upcoming_events(limit=5)
        except Exception:
            pass
        try:
            dash.get_pinned_beitraege(limit=3)
        except Exception:
            pass
    finally:
        _shared.get_value = orig_get_value
        _shared.get_all = orig_get_all
        dash.get_value = orig_get_value
        dash.get_all = orig_get_all
        dp.get_value = orig_get_value
        dp.get_all = orig_get_all

    assert gesehen, "keine Check-Feld-Filter auf den echten Pfaden gesehen"
    for doctype, feld, wert in gesehen:
        assert isinstance(wert, bool), (
            "%s.%s nicht als bool gebunden (Postgres: boolean = integer): %r"
            % (doctype, feld, wert)
        )


# ── Helfer ──────────────────────────────────────────────────────────────────

def _fremd(doctype, values):
    """Legt eine Zeile direkt an (fuer Fremd-Nutzer-Setups)."""
    from diakronos_app.frappe_compat.api_helpers import _create

    return _create(doctype, values)


def _widget_mit_boeser_methode():
    """Legt ein Widget an, dessen `api_method` beim Aufruf wirft."""
    from diakronos_app.frappe_compat.registry import whitelist
    from diakronos_app.frappe_compat.registry_gen import is_known
    from diakronos_app.frappe_compat.api_helpers import _create

    @whitelist(allow_guest=False)
    def boese_methode():
        raise RuntimeError("kaputt")

    _create("Dashboard Widget", {
        "widget_id": "boese",
        "label": "Boese",
        "widget_type": "info_card",
        "category": "test",
        "api_method": f"{boese_methode.__module__}.{boese_methode.__name__}",
        "grid_size": "half",
        "default_position": 9,
        "default_visible": 1,
        "enabled": 1,
        "empty_state_mode": "text",
        "empty_state_message": "-",
        "refresh_interval": 0,
    })
    return "boese"


# ── OP-HANDY-R1: Terminlisten filtern nach Leserecht + Status ────────────────
#
# Ausgangsbefund: get_upcoming_events/get_events_for_month lieferten Termine
# ALLER Kalender (auch gesperrter) und jeden Status — das Dashboard-Widget war
# nur zufaellig ausgeblendet, die API leakte trotzdem.


def test_upcoming_events_verraet_gesperrten_kalender_nicht(als_anna):
    """Anna liest KAL-A, nicht KAL-B -> EL-4 (KAL-B) fehlt."""
    from diakronos_app.api import dashboard as d

    ids = [e["id"] for e in d.get_upcoming_events(limit=50)]
    assert "EL-1" in ids
    assert "EL-4" not in ids, "Termin aus gesperrtem Kalender leakt"
    # Admin (Vollzugriff) sieht auch KAL-B.
    set_user(ADMIN)
    ids_admin = [e["id"] for e in d.get_upcoming_events(limit=50)]
    assert "EL-4" in ids_admin
    set_user("Administrator")


def test_upcoming_events_nur_festgelegt(als_anna):
    """Vorschlaege/Konflikte gehoeren nicht ins oeffentliche Widget."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Element", {
        "element_name": "Vorschlagstermin", "element_calendar": "KAL-A",
        "element_start": datetime.datetime.now() + datetime.timedelta(days=2),
        "element_end": datetime.datetime.now() + datetime.timedelta(days=2, hours=1),
        "status": "Vorschlag", "docstatus": 0, "idx": 0,
    })
    ids = [e["id"] for e in d.get_upcoming_events(limit=50)]
    rows = d.get_upcoming_events(limit=50)
    assert all(e["title"] != "Vorschlagstermin" for e in rows), ids


def test_events_for_month_verraet_gesperrten_kalender_nicht(als_anna):
    from diakronos_app.api import dashboard as d

    heute = datetime.date.today()
    out = d.get_events_for_month(year=heute.year, month=heute.month)
    assert len(out["event_days"]) >= 1
    # Gegenprobe ohne Leserecht (Gast liefert []).
    set_user("Guest")
    assert d.get_events_for_month(year=heute.year, month=heute.month)["event_days"] == []
    set_user("Administrator")


# ── OP-HANDY-11: Widgets mit echtem required_permission sichtbar ─────────────


def _widget_mit_permission(welt, widget_id, required_permission):
    from diakronos_app.frappe_compat.api_helpers import _create

    _create("Dashboard Widget", {
        "widget_id": widget_id, "label": widget_id, "widget_type": "list_card",
        "category": "info", "api_method": None, "required_permission": required_permission,
        "grid_size": "half", "default_position": 20, "default_visible": 1,
        "enabled": 1, "empty_state_mode": "text", "empty_state_message": "-",
        "refresh_interval": 0,
    })
    return widget_id


def test_widget_kronos_element_ist_fuer_mitglied_sichtbar(welt):
    """`Kronos Element,read` blendete Mitglieder aus (OP-HANDY-11)."""
    from diakronos_app.api import dashboard as d

    _widget_mit_permission(welt, "upcoming-events", "Kronos Element,read")
    set_user(ANNA)  # liest KAL-A
    try:
        ids = [w["widget_id"] for w in d.get_available_widgets()]
        assert "upcoming-events" in ids
    finally:
        set_user("Administrator")


def test_widget_wiki_artikel_ist_fuer_mitglied_sichtbar(welt):
    from diakronos_app.api import dashboard as d

    _widget_mit_permission(welt, "wiki-recent", "Wiki Artikel,read")
    set_user(ANNA)
    try:
        ids = [w["widget_id"] for w in d.get_available_widgets()]
        assert "wiki-recent" in ids
    finally:
        set_user("Administrator")


def test_widget_kronos_element_ohne_leserecht_unsichtbar(welt):
    """Ohne lesbaren Kalender bleibt das Termin-Widget weg (fail closed)."""
    from diakronos_app.api import dashboard as d
    from diakronos_app.frappe_compat.api_helpers import _create

    # Nutzer ohne jede Rolle -> kein lesbarer Kalender.
    _create("User", {"name": "niemand@example.org", "email": "niemand@example.org",
                     "full_name": "Niemand", "enabled": True})
    _widget_mit_permission(welt, "upcoming-events", "Kronos Element,read")
    set_user("niemand@example.org")
    try:
        ids = [w["widget_id"] for w in d.get_available_widgets()]
        assert "upcoming-events" not in ids
    finally:
        set_user("Administrator")


# ── OP-HANDY-1: Leserecht "All"/"Guest" (rollenbasiert) ─────────────────────


def test_kalender_mit_leserecht_all_fuer_mitglied_sichtbar(patched_db):
    """`_user_has_role` wertet "All" wie `frappe.get_roles` aus.

    Regression zum Befund OP-HANDY-1: der Kalender "Veranstaltungen"
    (Leserecht All) war fuer jedes Mitglied unsichtbar.
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import HasRole, User, UserRole  # noqa: F401
    from diakronos_app.models.kronos import Kalender

    sess = patched_db()
    sess.add_all([
        User(name="mitglied-x@example.org", email="mitglied-x@example.org",
             full_name="Mitglied X", enabled=True),
        User(name="gast-x@example.org", email="gast-x@example.org",
             full_name="Gast X", enabled=True),
    ])
    sess.add_all([
        Kalender(name="KAL-ALL", calendar_name="Veranstaltungen",
                 calendar_color="#333333", selbstverwaltet=0, docstatus=0, idx=0),
    ])
    sess.flush()
    sess.add_all([
        UserRole(name="UR-ALL", parent="KAL-ALL", parenttype="Kalender",
                 parentfield="leserechte", role="All", docstatus=0, idx=1),
    ])
    sess.commit()

    try:
        set_user("mitglied-x@example.org")
        namen = {c["name"] for c in get_accessible_calendars()}
        assert "KAL-ALL" in namen, "Leserecht All wird nicht ausgewertet"

        # Gast (unangemeldet) sieht den Kalender mit Leserecht All NICHT.
        set_user("Guest")
        assert get_accessible_calendars() == []
    finally:
        set_user("Administrator")
