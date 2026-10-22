"""P4g — Audit-Modul `api.audit` (4 Endpunkte).

Quelle (READ-ONLY):
  `referenz/diakronos-frappe/diakronos/diakonos/api/audit.py`

DSGVO ist der Kern dieser Datei: kein Nutzer darf fremde Audit-/Notification-
Eintraege sehen. Diese Tests belegen das aus beiden Richtungen (eigene sichtbar,
fremde nicht) — siehe Aufrufliste des Frappe-Frontends fuer die Aufruferpfade.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

AUDIT = "diakronos.diakonos.api.audit"

# Die 4 Originalpfade (hooks.py listet genau diese).
PATHS = [
    "diakronos.diakonos.api.audit.get_my_audit_log",
    "diakronos.diakonos.api.audit.get_unread_notifications",
    "diakronos.diakonos.api.audit.mark_notifications_read",
    "diakronos.diakonos.api.audit.get_my_notifications",
]

ALICE = "alice@example.invalid"
BOB = "bob@example.invalid"

# Session-Tests (P4g, session.py): eigene Konstanten, damit die Audit-Namen
# unangetastet bleiben.
E_ALICE = "alice@example.invalid"
E_BOB = "bob@example.invalid"
E_CAROL = "carol@example.invalid"
E_ADMIN = "admin@example.invalid"

GRUPPE_ALICE = "|/Gruppe-A/|"          # alice + carol
GRUPPE_BOB = "|/Gruppe-B/|"            # bob alleine


@pytest.fixture()
def welt(patched_db):
    """Drei User, Audit-/Notification-Zeilen fuer alice und bob.

    Enthaelt zusaetzlich die Session-Test-Welt (Mitglieder, Rollen,
    Diakronos-Einstellungen mit Modul-Kindern), weil audit/session/auswahl
    sich denselben Fixture-Namen teilen.
    """
    from diakronos_app.models.core import HasRole, NotificationLog, User
    from diakronos_app.models.diakonos import AuditLog

    sess = patched_db()
    sess.add_all([
        User(name=ALICE, email=ALICE, full_name="Alice", enabled=1),
        User(name=BOB, email=BOB, full_name="Bob", enabled=1),
        User(name=E_CAROL, email=E_CAROL, full_name="Carol", enabled=1),
        User(name=E_ADMIN, email=E_ADMIN, full_name="Admin", enabled=1),
    ])
    sess.add_all([
        # alice: actor -> sichtbar; bob: fremd -> unsichtbar.
        AuditLog(name="A-1", zeitstempel=datetime(2026, 1, 1, 10, 0), action_typ="Sonstiges",
                 actor=ALICE, target_doctype="Mitglied", target_name="M-1",
                 notification_gesendet=0),
        AuditLog(name="A-2", zeitstempel=datetime(2026, 1, 2, 10, 0), action_typ="Sonstiges",
                 actor=BOB, target_doctype="Mitglied", target_name="M-2",
                 notification_gesendet=0),
        # bob ist target_user -> fuer alice unsichtbar, fuer bob sichtbar.
        AuditLog(name="A-3", zeitstempel=datetime(2026, 1, 3, 10, 0), action_typ="Sonstiges",
                 actor=BOB, target_user=BOB, target_doctype="Mitglied", target_name="M-3",
                 notification_gesendet=0),
        # alice ist target_user, actor ist bob -> fuer alice sichtbar (DSGVO Art. 15).
        AuditLog(name="A-4", zeitstempel=datetime(2026, 1, 4, 10, 0), action_typ="Sonstiges",
                 actor=BOB, target_user=ALICE, target_doctype="Mitglied", target_name="M-4",
                 notification_gesendet=0),
    ])
    sess.add_all([
        NotificationLog(name="N-1", for_user=ALICE, subject="Fuer Alice", read=0,
                        type="Alert", email_content="a", creation=datetime(2026, 1, 1)),
        NotificationLog(name="N-2", for_user=ALICE, subject="Gelesen", read=1,
                        type="Alert", email_content="b", creation=datetime(2026, 1, 2)),
        NotificationLog(name="N-3", for_user=BOB, subject="Fuer Bob", read=0,
                        type="Alert", email_content="c", creation=datetime(2026, 1, 3)),
    ])

    # ── Session-Welt ────────────────────────────────────────────────────
    from diakronos_app.models.diakonos import Mitglied

    sess.add_all([
        Mitglied(name="M-ALICE", email=E_ALICE, vorname="Alice", nachname="A",
                 status="Aktiv", ancestor_path=GRUPPE_ALICE),
        Mitglied(name="M-BOB", email=E_BOB, vorname="Bob", nachname="B",
                 status="Aktiv", ancestor_path=GRUPPE_BOB),
        Mitglied(name="M-CAROL", email=E_CAROL, vorname="Carol", nachname="C",
                 status="Aktiv", ancestor_path=GRUPPE_ALICE),
    ])

    # Admin hat beide Rollen; bob ist explizit NICHT Kalenderadministrator.
    sess.add_all([
        HasRole(name="r1", parent=E_ADMIN, parenttype="User",
                parentfield="roles", role="System Manager"),
        HasRole(name="r2", parent=E_ADMIN, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator"),
    ])

    # Diakronos Einstellungen (Single): Diakronos+Kronos sichtbar, Psalmos aus.
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    sess.add(DiakronosEinstellungen(
        name="Diakronos Einstellungen",
        diakronos_sichtbar=True, diakronos_anzeige_name="Diakronos",
        diakronos_icon="/assets/diakronos/images/diakronos-logo.svg",
        kronos_sichtbar=True, kronos_anzeige_name="Kronos",
        kronos_icon="/assets/diakronos/images/kronos-logo.svg",
        diakonos_sichtbar=True, diakonos_anzeige_name="Diakonos",
        psalmos_sichtbar=False, seelsorge_sichtbar=False,
    ))
    sess.commit()
    yield sess
    sess.close()


# ── Registrierung ───────────────────────────────────────────────────────────

def test_frappe_module_gesetzt():
    import diakronos_app.api.audit as mod

    assert mod.FRAPPE_MODULE == AUDIT


@pytest.mark.parametrize("path", PATHS)
def test_originalpfad_aufloesbar(path):
    assert callable(lookup(path)), f"{path} nicht registriert"


@pytest.mark.parametrize("path", PATHS)
def test_login_pflicht(path, client):
    set_user("Guest")
    resp = client.post(f"/api/method/{path}", json={})
    assert resp.status_code == 401, f"{path} liess Guest durch: {resp.status_code}"


# ── Sichtbarkeit (DSGVO) ────────────────────────────────────────────────────

def test_audit_sieht_eigene_aber_keine_fremden(client, welt):
    set_user(ALICE)
    resp = client.post("/api/method/diakronos.diakonos.api.audit.get_my_audit_log", json={})
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    names = {r["name"] for r in msg["data"]}
    # A-1 (actor) + A-4 (target_user) sichtbar, A-2/A-3 (fremd) NICHT.
    assert names == {"A-1", "A-4"}, f"alice sah {names}"
    assert msg["total"] == 2


def test_audit_bob_sieht_seine_eintraege(client, welt):
    set_user(BOB)
    resp = client.post("/api/method/diakronos.diakonos.api.audit.get_my_audit_log", json={})
    names = {r["name"] for r in resp.json()["message"]["data"]}
    # A-2/A-3: bob ist actor (bzw. actor+target). A-4 hat actor=bob, taucht also
    # ueber die actor-Seite der OR-Bedingung auf — das ist die dokumentierte
    # Semantik (target_user ODER actor), nicht ein Leck.
    assert names == {"A-2", "A-3", "A-4"}
    assert "A-1" not in names, "bob sah fremden Eintrag A-1 (actor=alice)"


def test_notifications_sieht_fremde_nicht(client, welt):
    set_user(ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.audit.get_my_notifications", json={}
    )
    names = {r["name"] for r in resp.json()["message"]["data"]}
    assert names == {"N-1", "N-2"}, f"alice sah fremde: {names}"


def test_unread_count_nur_eigene(client, welt):
    set_user(ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.audit.get_unread_notifications", json={}
    )
    # alice hat N-1 ungelesen; N-3 (bob) darf nicht zaehlen.
    assert resp.json()["message"]["unread_count"] == 1


def test_mark_read_setzt_nur_eigene(client, welt):
    set_user(ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.audit.mark_notifications_read", json={"names": ["N-1", "N-3"]}
    )
    assert resp.status_code == 200, resp.text
    welt.expire_all()
    from diakronos_app.models.core import NotificationLog

    own = welt.get(NotificationLog, "N-1").read
    foreign = welt.get(NotificationLog, "N-3").read
    assert own in (1, True), "eigene Notification nicht als gelesen markiert"
    assert foreign in (0, False), "mark_notifications_read hat fremde veraendert"


def test_ungueltiger_action_typ_wirft(client, welt):
    set_user(ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.audit.get_my_audit_log",
        json={"action_typ": "Quatsch"},
    )
    assert resp.status_code == 417, resp.text


# ═══════════════════════════════════════════════════════════════════════════
# auswahl.py — Suchdropdowns (4 Endpunkte)
# ═══════════════════════════════════════════════════════════════════════════

AUSWAHL = "diakronos.diakonos.api.auswahl"

AUSWAHL_PATHS = [
    "diakronos.diakonos.api.auswahl.get_inhalt_optionen",
    "diakronos.diakonos.api.auswahl.get_sammlungen",
    "diakronos.diakonos.api.auswahl.get_kalender_optionen",
    "diakronos.diakonos.api.auswahl.get_ressourcen_optionen",
]


def test_auswahl_frappe_module_gesetzt():
    import diakronos_app.api.auswahl as mod

    assert mod.FRAPPE_MODULE == AUSWAHL


@pytest.mark.parametrize("path", AUSWAHL_PATHS)
def test_auswahl_originalpfad_aufloesbar(path):
    assert callable(lookup(path)), f"{path} nicht registriert"


@pytest.mark.parametrize("path", AUSWAHL_PATHS)
def test_auswahl_login_pflicht(path, client):
    set_user("Guest")
    resp = client.post(f"/api/method/{path}", json={})
    assert resp.status_code == 401, f"{path} liess Guest durch: {resp.status_code}"


@pytest.fixture()
def stammdaten(patched_db):
    """Mitglied (Vollzugriff) + Gast (kein Planungszugriff) + Stammdaten."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Dienstrolle, Gruppe, Mitglied
    from diakronos_app.models.kronos import Eventkategorie
    from diakronos_app.models.psalmos import Lied, Liedgruppe, LiedgruppeLied

    sess = patched_db()
    sess.add_all([
        User(name="planer@example.invalid", email="planer@example.invalid",
             full_name="Planer", enabled=1),
        User(name="gast@example.invalid", email="gast@example.invalid",
             full_name="Gast", enabled=1),
    ])
    sess.add_all([
        Mitglied(name="M-100", vorname="Pia", nachname="Planer",
                 email="planer@example.invalid", status="Mitglied",
                 docstatus=0, idx=0),
        Mitglied(name="M-101", vorname="Gina", nachname="Gast",
                 email="gast@example.invalid", status="Gast",
                 docstatus=0, idx=0),
    ])
    sess.add_all([
        Lied(name="HASH-A", titel="Alpha", docstatus=0, idx=0),
        Lied(name="HASH-B", titel="Beta", docstatus=0, idx=0),
        Dienstrolle(name="R-1", rollenname="Moderator", docstatus=0, idx=0),
        Gruppe(name="G-1", gruppenname="Team A", docstatus=0, idx=0),
        Eventkategorie(name="EK-1", event_category_name="Gottesdienst",
                       docstatus=0, idx=0),
        Liedgruppe(name="LG-1", gruppenname="Lobpreis", typ="Sammlung",
                   status="Aktiv", docstatus=0, idx=0),
        Liedgruppe(name="LG-2", gruppenname="Alt", typ="Sammlung",
                   status="Inaktiv", docstatus=0, idx=0),
    ])
    sess.add_all([
        LiedgruppeLied(name="LGL-1", parent="LG-1", parenttype="Liedgruppe",
                       parentfield="lieder", lied="HASH-A", fassung="1",
                       nummer="1", reihenfolge=1, docstatus=0, idx=1),
        LiedgruppeLied(name="LGL-2", parent="LG-1", parenttype="Liedgruppe",
                       parentfield="lieder", lied="HASH-B", fassung="2",
                       nummer="2", reihenfolge=2, docstatus=0, idx=2),
    ])
    sess.commit()
    yield sess
    sess.close()


PLANER = "planer@example.invalid"
GAST = "gast@example.invalid"


def test_inhalt_optionen_liefert_kandidaten(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "Dienstrolle"},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()["message"]
    assert out == [{"name": "R-1", "label": "Moderator"}]


def test_inhalt_optionen_lied_name_ist_hash_label_titel(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "Lied"},
    )
    out = resp.json()["message"]
    assert {o["name"] for o in out} == {"HASH-A", "HASH-B"}
    assert {o["label"] for o in out} == {"Alpha", "Beta"}


def test_inhalt_optionen_suche_filtert(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "Lied", "suche": "alp"},
    )
    out = resp.json()["message"]
    assert [o["name"] for o in out] == ["HASH-A"]


def test_inhalt_optionen_mit_sammlung(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "Lied", "sammlung": "LG-1"},
    )
    out = resp.json()["message"]
    assert [o["name"] for o in out] == ["HASH-A", "HASH-B"]
    assert out[0]["fassung"] == "1" and out[0]["nummer"] == "1"


def test_inhalt_optionen_whitelist_blockt_fremden_doctype(client, stammdaten):
    """Kernabsicherung: unbekannter DocType darf NICHT durchgereicht werden."""
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "User"},
    )
    assert resp.status_code == 417, resp.text


def test_inhalt_optionen_limit_ist_gedeckelt(client, stammdaten):
    from diakronos_app.api.auswahl import MAX_LIMIT, _cap_limit

    assert _cap_limit(99999) == MAX_LIMIT
    assert _cap_limit(None) == 50
    assert _cap_limit("quatsch") == 50


def test_sammlungen_nur_aktive_mit_anzahl(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_sammlungen", json={}
    )
    out = resp.json()["message"]
    assert [g["name"] for g in out] == ["LG-1"], f"inaktive Sammlung gelistet: {out}"
    assert out[0]["anzahl_lieder"] == 2
    assert out[0]["gruppenname"] == "Lobpreis"


def test_sammlungen_fremder_doctype_leer(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_sammlungen",
        json={"doctype": "Gruppe"},
    )
    assert resp.json()["message"] == []


def test_gast_darf_planungsstammdaten_nicht(client, stammdaten):
    set_user(GAST)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_inhalt_optionen",
        json={"doctype": "Lied"},
    )
    assert resp.status_code == 403, resp.text


def test_kalender_optionen_shape(client, stammdaten):
    set_user(PLANER)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.auswahl.get_kalender_optionen", json={}
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert set(msg) == {"calendars", "categories"}
    assert [c["name"] for c in msg["categories"]] == ["EK-1"]


def test_referenz_label_faellt_zurueck(client, stammdaten):
    from diakronos_app.api.auswahl import referenz_label

    set_user(PLANER)
    assert referenz_label("Lied", "HASH-A") == "Alpha"
    assert referenz_label("Dienstrolle", "R-1") == "Moderator"
    assert referenz_label("Unbekannt", "X") == "X"
    assert referenz_label(None, "X") == "X"


# ═══════════════════════════════════════════════════════════════════
# session.py — get_current_user_context / get_mitglied_permissions / check_permission
# ═══════════════════════════════════════════════════════════════════

def _seed_user(session, email, full_name="Test User", user_id=None, roles=()):
    from diakronos_app.models.core import HasRole, User

    uid = user_id or email
    if not session.get(User, uid):
        session.add(User(name=uid, email=email, full_name=full_name, enabled=1))
        session.flush()
    for r in roles:
        session.add(HasRole(name=f"{uid}-{r}", parent=uid, parenttype="User",
                            parentfield="roles", role=r))
    session.commit()
    return uid


def _seed_mitglied(session, name, email, ancestor_path="|", vorname="A", nachname="B"):
    from diakronos_app.models.diakonos import Mitglied

    if not session.get(Mitglied, name):
        session.add(Mitglied(name=name, email=email, vorname=vorname,
                             nachname=nachname, status="Aktiv",
                             ancestor_path=ancestor_path))
        session.commit()
    return name


def test_session_context_liefert_beide_email_schluessel(client, welt):
    """BOOT_VERTRAG fordert `user_email`; das Original liefert `email`.

    Der Port liefert BEIDE — sonst bricht entweder SPA oder Original-Semantik.
    """
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["user"] == E_ALICE
    assert msg["user_email"] == E_ALICE, "Vertragsfeld user_email fehlt"
    assert msg["email"] == E_ALICE, "Originalfeld email fehlt"


def test_session_context_admin_flag(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ADMIN)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    msg = resp.json()["message"]
    assert msg["is_admin"] is True
    assert msg["permissions"]["can_view_dsgvo"] is True
    assert msg["permissions"]["can_export_data"] is True


def test_session_context_nicht_admin(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    msg = resp.json()["message"]
    assert msg["is_admin"] is False
    assert msg["permissions"]["can_view_dsgvo"] is False
    # Bob hat ein Mitglied -> normale Rechte.
    assert msg["permissions"]["can_view_dienstplan"] is True
    assert msg["mitglied"]["name"] == "M-BOB"


def test_session_context_ohne_mitglied(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user("gast@example.org")
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    msg = resp.json()["message"]
    assert msg["mitglied"] is None
    assert msg["permissions"]["can_view_mitglieder"] is False
    assert msg["permissions"]["can_view_gruppen"] is False


def test_session_context_guest_abgelehnt(client, welt):
    """Kein Gast-Zugriff: der Boot darf nie ohne Login leaken."""
    from diakronos_app.frappe_compat.session import set_user

    set_user("Guest")
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    assert resp.status_code in (401, 403), resp.text


def test_session_context_liefert_csrf_token_schluessel(client, welt):
    """Vertrag verlangt den Schluessel `csrf_token` (Wert darf leer sein —
    kein erfundenes Token, siehe Modul-Docstring)."""
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ALICE)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_current_user_context", json={}
    )
    assert "csrf_token" in resp.json()["message"]


def test_mitglied_permissions_selbst(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_mitglied_permissions",
        json={"mitglied_id": "M-BOB"},
    )
    perms = resp.json()["message"]
    assert perms["can_view"] is True
    assert perms["can_edit"] is True


def test_mitglied_permissions_fremd_ohne_ueberlappung(client, welt):
    """DSGVO: Bob und Alice liegen in verschiedenen Gruppen -> kein Zugriff."""
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_mitglied_permissions",
        json={"mitglied_id": "M-ALICE"},
    )
    perms = resp.json()["message"]
    assert perms["can_view"] is False
    assert perms["can_edit"] is False


def test_mitglied_permissions_admin_sieht_alles(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ADMIN)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_mitglied_permissions",
        json={"mitglied_id": "M-ALICE"},
    )
    perms = resp.json()["message"]
    assert perms["can_view"] is True
    assert perms["reason"] == "admin_role"


def test_mitglied_permissions_gleiche_gruppe(client, welt):
    """Carol liegt in derselben Gruppe wie Alice -> Sichtzugriff, aber
    NICHT Schreibzugriff auf fremdes Profil."""
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_CAROL)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_mitglied_permissions",
        json={"mitglied_id": "M-ALICE"},
    )
    perms = resp.json()["message"]
    assert perms["can_view"] is True
    assert perms["can_edit"] is False


def test_mitglied_permissions_unbekanntes_mitglied(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ADMIN)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.get_mitglied_permissions",
        json={"mitglied_id": "GIBT-ES-NICHT"},
    )
    assert resp.status_code == 404, resp.text


def test_check_permission_admin(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ADMIN)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.check_permission",
        json={"doctype": "Mitglied", "docname": "M-ALICE", "permission_type": "write"},
    )
    assert resp.json()["message"]["allowed"] is True


def test_check_permission_normaler_user_fremd(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.check_permission",
        json={"doctype": "Mitglied", "docname": "M-ALICE", "permission_type": "read"},
    )
    assert resp.json()["message"]["allowed"] is False


def test_check_permission_unbekanntes_doctype(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.diakonos.api.session.check_permission",
        json={"doctype": "Zauberstab", "docname": "X", "permission_type": "read"},
    )
    assert resp.json()["message"]["allowed"] is False
    assert resp.json()["message"]["reason"] == "unsupported_doctype"


# ═══════════════════════════════════════════════════════════════════
# kronos/permissions.py — get_accessible_modules
# ═══════════════════════════════════════════════════════════════════

def test_get_accessible_modules_signatur_und_typen(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_ADMIN)
    resp = client.post(
        "/api/method/diakronos.kronos.api.permissions.get_accessible_modules", json={}
    )
    assert resp.status_code == 200, resp.text
    modules = resp.json()["message"]
    assert isinstance(modules, list)
    assert modules, "Admin ohne Module -> Konfiguration fehlt"
    # Schluessel 1:1 aus dem Original (permissions.py:172-178).
    #
    # A1c5: `route` ist seitdem OPTIONAL. Es zeigt in die SPA und existiert nur
    # fuer Module mit einer SPA-Seite (`MODUL_ZIEL_SPA`). `Diakronos` hat keine
    # (im Original leeres `MODULE_PAGES`) und bekommt den Schluessel deshalb gar
    # nicht — das ist die beabsichtigte Aenderung am Vertrag, kein Fehler.
    # Die vier Pflichtfelder bleiben unveraendert; `route` wird einzeln geprueft.
    for m in modules:
        assert {"module_name", "prefix", "anzeige_name", "icon"} <= set(m), m
        if "route" in m:
            assert m["route"].startswith("#/"), m
    names = {m["module_name"] for m in modules}
    assert "Diakronos" in names and "Kronos" in names
    assert "Psalmos" not in names, "psalmos_sichtbar=0 darf nicht auftauchen"


def test_get_accessible_modules_normaler_user(client, welt):
    from diakronos_app.frappe_compat.session import set_user

    set_user(E_BOB)
    resp = client.post(
        "/api/method/diakronos.kronos.api.permissions.get_accessible_modules", json={}
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json()["message"], list)
