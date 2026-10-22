"""Erstinstallation (Karte A1b3) — der erste Administrator.

Die Karte verlangt: aus `ADMIN_EMAIL`/`ADMIN_PASSWORD` entsteht bei einer
FRISCHEN Installation genau ein anmeldbarer Administrator mit echten Inhalten
statt des `Administrator`-Platzhalters.

Gemessen wird gegen die echte Auth-Kette (nicht gegen eine Attrappe):
  * der angelegte Benutzer hat einen Argon2-Hash und laesst sich per
    `/api/method/login` anmelden;
  * `session.get_current_user_context` liefert DANACH den echten User
    (`is_admin=True`, Rollen) — nicht den Dummy;
  * ein zweiter Lauf aendert NICHTS (Idempotenz, kein zweites Konto);
  * fehlende Werte / halb gesetzte Werte legen nichts an.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def admin_werte(monkeypatch):
    """Setzt ADMIN_EMAIL/ADMIN_PASSWORD in den Settings fuer den Test."""
    from diakronos_app import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "admin_email", "chef@example.org")
    monkeypatch.setattr(settings_mod.settings, "admin_password", "erst-geheim-123")
    return settings_mod.settings


def test_frische_installation_legt_admin_an(patched_db, admin_werte):
    from diakronos_app.erstinstallation import bootstrap_erstinstallation
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.frappe_compat.passwoerter import pruefe

    angelegt = bootstrap_erstinstallation()
    assert angelegt == "chef@example.org"

    sess = patched_db()
    try:
        doc = sess.get(User, "chef@example.org")
        assert doc is not None
        assert doc.enabled is True
        # Echter Argon2-Hash, KEIN Klartext.
        assert doc.password_hash.startswith("$argon2")
        assert doc.password_hash != "erst-geheim-123"
        assert pruefe("erst-geheim-123", doc.password_hash)
        assert not pruefe("falsch", doc.password_hash)

        rollen = {
            r.role
            for r in sess.query(HasRole).filter(HasRole.parent == "chef@example.org")
        }
        assert "System Manager" in rollen
        assert "Mitgliederadministrator" in rollen
    finally:
        sess.close()


def test_angemeldeter_admin_sieht_echte_inhalte(patched_db, admin_werte, fake_redis):
    """Abnahme: nach Login liefert der User-Context den ECHTEN Benutzer.

    Das ist die Kernzusage der Karte — der Erst-Admin sieht nach dem Login
    Inhalte, nicht den `Administrator`-Platzhalter. Der Test meldet sich ueber
    den echten HTTP-Login an und fragt den Context ab.
    """
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    bootstrap_erstinstallation()

    from fastapi.testclient import TestClient
    from diakronos_app.main import app

    with TestClient(app) as c:
        r = c.post("/api/method/login",
                   json={"usr": "chef@example.org", "pwd": "erst-geheim-123"})
        assert r.status_code == 200, r.text

        # Lesende Methoden laufen ohne CSRF, aber die SPA holt den Context per
        # POST -> dafuer braucht es das Token aus der Login-Antwort. Frappe legt
        # es neben `message` ab (`{"message": "Logged In", "csrf_token": ...}`).
        login_daten = r.json()
        token = login_daten.get("csrf_token")
        assert token, login_daten
        c.headers["X-Frappe-CSRF-Token"] = token

        ctx = c.post("/api/method/diakronos.diakonos.api.session.get_current_user_context",
                     json={})
        assert ctx.status_code == 200, ctx.text
        data = ctx.json().get("message", ctx.json())
        if isinstance(data, str):
            import json
            data = json.loads(data)

    assert data["user"] == "chef@example.org"
    assert data["user_email"] == "chef@example.org"
    assert data["is_admin"] is True
    assert data["user"] != "Administrator"


def test_zweiter_lauf_aendert_nichts(patched_db, admin_werte):
    from diakronos_app.erstinstallation import bootstrap_erstinstallation
    from diakronos_app.models.core import User

    assert bootstrap_erstinstallation() == "chef@example.org"
    # Zweiter Lauf: Tabelle ist gefuellt -> kein zweites Konto, kein Fehler.
    assert bootstrap_erstinstallation() is None

    sess = patched_db()
    try:
        assert sess.query(User).count() == 1
    finally:
        sess.close()


def test_bestehende_benutzer_werden_nicht_ueberschrieben(patched_db, admin_werte):
    """Ein bereits vorhandener Benutzer schuetzt vor dem Bootstrap."""
    from diakronos_app.erstinstallation import bootstrap_erstinstallation
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        sess.add(User(name="alt@example.org", email="alt@example.org",
                      full_name="Alt", enabled=True, password_hash="$argon2$x"))
        sess.commit()
    finally:
        sess.close()

    assert bootstrap_erstinstallation() is None

    sess = patched_db()
    try:
        assert sess.query(User).count() == 1
        assert sess.get(User, "alt@example.org").password_hash == "$argon2$x"
        assert sess.get(User, "chef@example.org") is None
    finally:
        sess.close()


@pytest.mark.parametrize("email,passwort", [
    ("", ""),                       # nichts gesetzt -> Normalfall bestehender Inst.
    ("chef@example.org", ""),       # nur E-Mail
    ("", "erst-geheim-123"),        # nur Passwort
])
def test_unvollstaendige_werte_legen_nichts_an(
    patched_db, monkeypatch, email, passwort
):
    from diakronos_app import settings as settings_mod
    from diakronos_app.erstinstallation import bootstrap_erstinstallation
    from diakronos_app.models.core import User

    monkeypatch.setattr(settings_mod.settings, "admin_email", email)
    monkeypatch.setattr(settings_mod.settings, "admin_password", passwort)

    assert bootstrap_erstinstallation() is None

    sess = patched_db()
    try:
        assert sess.query(User).count() == 0
    finally:
        sess.close()
