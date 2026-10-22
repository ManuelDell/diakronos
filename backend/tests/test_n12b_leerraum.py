"""Regression R-N12b: Leerraum darf Has-Role-/User-Schluesselfelder nicht unbemerkt aendern (Aussperrschutz)."""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User


def _konto(sess, email, rolle=None):
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()


def _rollen(u):
    from diakronos_app.frappe_compat.permissions import get_roles
    return get_roles(u)


def _sm():
    from diakronos_app.api.zugang import _aktive_system_manager
    return _aktive_system_manager()


@pytest.mark.parametrize("neu", ["sm2@x.org ", " sm2@x.org", "sm2@x.org\t"])
def test_has_role_parent_mit_leerraum_bleibt_unveraendert(client, patched_db, fake_redis, neu):
    sess = patched_db(); _konto(sess, "sm@x.org", "System Manager"); _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")
    r = client.put("/api/resource/Has Role/HR-sm2@x.org-System Manager", json={"parent": neu})
    sess.expire_all()
    p = sess.get(HasRole, "HR-sm2@x.org-System Manager").parent
    assert p == "sm2@x.org", (r.status_code, repr(p), _rollen("sm2@x.org"))


@pytest.mark.parametrize("neu", ["sm2@x.org ", " sm2@x.org"])
def test_user_name_mit_leerraum_nicht_umbenennbar(client, patched_db, fake_redis, neu):
    sess = patched_db(); _konto(sess, "sm@x.org", "System Manager"); _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")
    r = client.put("/api/resource/User/sm2@x.org", json={"name": neu})
    sess.expire_all()
    assert sess.get(User, "sm2@x.org") is not None, (r.status_code, r.text[:200])


def test_letzter_sm_nicht_per_leerraum_umbenennbar(client, patched_db, fake_redis):
    sess = patched_db(); _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    r = client.put("/api/resource/User/sm@x.org", json={"name": "sm@x.org "})
    sess.expire_all()
    assert "sm@x.org" in _sm(), (r.status_code, r.text[:200], _sm())
