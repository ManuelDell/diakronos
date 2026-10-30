"""REG-1c (4) — Groessenlimit der Formularbilder: Server und Anzeige, EIN Wert.

Befund (Opus-Review REG-1b): Die Oberflaeche lud eine zu grosse Datei erst
hoch und erfuhr die Grenze dann als Serverfehler. Verlangt ist eine Pruefung
VOR dem Upload mit klarer Meldung „max. X MB“ — und der Wert muss aus
DERSELBEN Quelle kommen wie die Grenze, die der Server zieht.

Der Test haelt deshalb beide Enden fest:

  * ``api.frappe_core.bild_upload_max_bytes`` ist das Limit, gegen das
    ``upload_file`` prueft (Bildtypen -> ``settings.max_upload_bytes``),
  * das Boot-Objekt der SPA nennt genau diesen Wert
    (``bild_upload_max_bytes``), damit die Oberflaeche nicht raten muss.

Alle Tests laufen ohne Netz (``patched_db``/SQLite) — Regel 11 der Karte.
"""

from __future__ import annotations

import io

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def test_bildlimit_ist_das_allgemeine_upload_limit(monkeypatch):
    """Bildtypen haengen am allgemeinen Limit, nicht am Audio-Limit."""
    from diakronos_app.api import frappe_core
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 4096)
    monkeypatch.setattr(settings, "max_upload_bytes_audio", 999999)

    assert frappe_core.bild_upload_max_bytes() == 4096
    for typ in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        assert frappe_core.upload_limit(typ) == 4096
    # Gegenprobe: ein Audio-Typ nutzt weiter sein eigenes Limit.
    assert frappe_core.upload_limit("audio/mpeg") == 999999


def test_boot_objekt_nennt_dasselbe_limit(monkeypatch):
    """Die Anzeige bekommt GENAU die Grenze, die der Server zieht."""
    from diakronos_app.frappe_compat import session
    from diakronos_app.settings import settings
    from diakronos_app.spa import boot_fuer_request

    monkeypatch.setattr(settings, "max_upload_bytes", 7 * 1024 * 1024)
    from diakronos_app.api.frappe_core import bild_upload_max_bytes

    session.user = "Guest"
    boot = boot_fuer_request()
    assert boot["bild_upload_max_bytes"] == bild_upload_max_bytes() == 7 * 1024 * 1024
    # Ganze Megabyte: die Oberflaeche zeigt „7 MB“ ohne Nachkommastelle.
    assert boot["bild_upload_max_bytes"] % (1024 * 1024) == 0


def test_server_lehnt_zu_grosse_datei_mit_dem_limit_ab(admin_client, monkeypatch):
    """Die Grenze des Boot-Objekts ist die Grenze, an der der Upload scheitert.

    Beweist die gemeinsame Quelle von der anderen Seite: knapp unter dem Limit
    geht durch, ein Byte mehr nicht.
    """
    from diakronos_app.api.frappe_core import bild_upload_max_bytes
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "max_upload_bytes", len(PNG))

    def hoch(inhalt: bytes):
        return admin_client.post(
            "/api/method/upload_file",
            files={"file": ("grenze.png", io.BytesIO(inhalt), "image/png")},
            data={"doctype": "Anmeldeformular", "docname": "AF-REG1C"},
        )

    assert len(PNG) == bild_upload_max_bytes()
    assert hoch(PNG).status_code == 200
    zu_gross = hoch(PNG + b"\x00")
    assert zu_gross.status_code == 417, zu_gross.text
    assert "zu gross" in (zu_gross.json().get("message") or "").lower()


@pytest.fixture()
def admin_client(client, patched_db):
    """Angemeldeter Mitgliederadministrator (wie in den REG-Tests)."""
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import HasRole, User

    admin = "reg1c-limit@example.org"
    sess = patched_db()
    if sess.get(User, admin) is None:
        sess.add(User(name=admin, email=admin, full_name="Admin", enabled=True))
    if not sess.query(HasRole).filter_by(parent=admin, role="Mitgliederadministrator").first():
        sess.add(
            HasRole(
                name=f"{admin}-MA",
                parent=admin,
                parenttype="User",
                parentfield="roles",
                idx=1,
                role="Mitgliederadministrator",
            )
        )
    sess.commit()
    sess.close()

    set_user(admin)
    try:
        yield client
    finally:
        set_user("Administrator")
