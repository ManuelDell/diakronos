"""Hotfix R-P1-8: `frappe.client.insert` darf keine Rollen/Konten an Nicht-System-Manager geben."""
import pytest

from diakronos_app.frappe_compat.exceptions import PermissionError as PE
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User


def _u(sess, email, rolle):
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    sess.add(HasRole(name="HR-" + email + rolle, parent=email, parenttype="User",
                     parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()


@pytest.mark.parametrize("doc", [
    {"doctype": "Has Role", "parent": "ma@x.org", "parenttype": "User",
     "parentfield": "roles", "role": "System Manager"},
    {"doctype": "User", "name": "neu@x.org", "email": "neu@x.org", "enabled": 1},
])
def test_mitgliederadmin_kann_ueber_insert_keine_konten_oder_rollen_anlegen(patched_db, doc):
    from diakronos_app.api.frappe_core import insert
    from diakronos_app.frappe_compat.permissions import get_roles

    s = patched_db()
    _u(s, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")
    with pytest.raises(PE):
        insert(doc=dict(doc))
    assert "System Manager" not in get_roles("ma@x.org")


def test_system_manager_darf_weiter_rollen_anlegen(patched_db):
    from diakronos_app.api.frappe_core import insert

    s = patched_db()
    _u(s, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    r = insert(doc={"doctype": "Has Role", "parent": "sm@x.org", "parenttype": "User",
                    "parentfield": "roles", "role": "Mitgliederadministrator"})
    assert r["role"] == "Mitgliederadministrator"
