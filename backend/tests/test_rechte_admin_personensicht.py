"""PersonenSicht fragt das EINE Rechtesystem (rechte.kern), keine eigene Rollenliste.

Vorher: ``PersonenSicht.aus`` nutzte ``permissions._has_admin_role`` — das
Login ``Administrator`` ohne ``Has Role``-Zeile galt dort NICHT als Admin,
in ``rechte.kern.ist_admin`` aber schon. Jetzt entscheidet
``hat_systemrolle(…, "mitgliederverwaltung")``.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User


def _konto(sess, name: str, rolle: str | None = None) -> None:
    sess.add(User(name=name, email=f"{name}@x.org" if "@" not in name else name,
                  full_name=name, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{name}-{rolle}", parent=name, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()


@pytest.mark.parametrize(("konto", "rolle", "erwartet"), [
    ("Administrator", None, True),          # Login ohne Rollenzeile
    ("sm@x.org", "System Manager", True),
    ("ma@x.org", "Mitgliederadministrator", True),
    ("leser@x.org", None, False),
    ("kal@x.org", "Kalenderadministrator", False),
])
def test_personensicht_folgt_dem_rechtekern(patched_db, konto, rolle, erwartet) -> None:
    from diakronos_app.rechte.kern import hat_systemrolle

    sess = patched_db()
    _konto(sess, konto, rolle)
    set_user(konto)
    sicht = PersonenSicht.aus({"name": "M-eigen"})
    assert sicht.vollstaendig is erwartet
    # Dieselbe Antwort wie der Rechtekern — keine zweite Admin-Definition.
    assert sicht.vollstaendig is hat_systemrolle(konto, "mitgliederverwaltung")
    if not erwartet:
        assert sicht.darf_vollstaendig("M-eigen")
        assert not sicht.darf_vollstaendig("M-fremd")
    sess.close()


def test_personensicht_gast_ist_nie_vollstaendig(patched_db) -> None:
    patched_db()
    set_user("Guest")
    assert PersonenSicht.aus().vollstaendig is False
