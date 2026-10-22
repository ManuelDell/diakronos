"""N12b: Rolle/Konto-Platz ist unveraenderlich (W1, P5) + Leser filtern parenttype.

DIE BEFUNDE (Befunde)
----------------------------------
* W1 (wichtig, durch N12 neu): ``get_roles``/``_rollen_von``/
  ``_aktive_system_manager`` filtern seit N12 nach ``parenttype``. Damit ist
  ``parenttype`` selbst zum Hebel geworden: ``_ist_letzter_system_manager``
  prueft nur ``parent`` und ``role``, also konnte der EINZIGE System Manager
  seine Zeile per ``PUT /api/resource/Has Role/<zeile>`` auf ``parenttype:
  "Page"`` setzen und war ausgesperrt (auf main war dieser Weg dicht).

* P5 (klein): ``PUT /api/resource/User/<sm>`` mit ``{"name": "..."}`` benennt
  den Primaerschluessel um — derselbe stille Weg aus der Verwaltung heraus.
  Nur der SM selbst kommt daran, aber genauso still.

* R-N10 Punkt 7 (klein, Altlast): ``zugang._aktive_administratoren`` und
  ``planrahmen/rechte.admin()`` waren die letzten Leser OHNE
  ``parenttype``-Filter. Wirksam nur, wenn ein Konto exakt so heisst wie eine
  Seite/ein Bericht (z.B. ``backups``).

DIE REGEL
---------
``parent``, ``parenttype``, ``parentfield`` einer bestehenden ``Has Role``-
Zeile und ``name`` eines Kontos sind unveraenderlich. Ein Rollenwechsel geht
ueber ``role``, ein Kontowechsel ueber eine neue Zeile. Unveraendert
gesendete Werte bleiben erlaubt (das ganze Dokument speichern).

Die Proben stammen aus dem Review-Probensatz
(``test_zz_n12_proben.py``) und sind mit der SICHEREN Erwartung uebernommen.
"""

from __future__ import annotations

import asyncio

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User


def _konto(
    sess,
    email: str,
    rolle: str | None = None,
    *,
    enabled: bool = True,
    parenttype: str = "User",
    zeile: str | None = None,
) -> None:
    """Konto anlegen, optional mit einer Rollenzeile (wie im Probenlauf)."""
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(
            name=zeile or f"HR-{email}-{rolle}", parent=email,
            parenttype=parenttype, parentfield="roles", role=rolle,
            docstatus=0, idx=1,
        ))
    sess.commit()


def _rollen(user: str) -> tuple[str, ...]:
    from diakronos_app.frappe_compat.permissions import get_roles

    return get_roles(user)


def _sm() -> set[str]:
    from diakronos_app.api.zugang import _aktive_system_manager

    return _aktive_system_manager()


def _sm_zeile(sess, user: str) -> str:
    return str(
        sess.query(HasRole)
        .filter(HasRole.parent == user, HasRole.role == "System Manager")
        .one()
        .name
    )


# ── W1: `parenttype` einer bestehenden Zeile ist unveraenderlich ────────────

@pytest.mark.parametrize("pt", ["Page", "Report", "ToDo"])
def test_parenttype_umbiegen_verweigert(client, patched_db, fake_redis, pt) -> None:
    """Der letzte SM darf seine Zeile nicht auf einen Fremdtyp umbiegen.

    Regression N12b (W1): vor der Behebung liess dieser PUT durch
    (200), die SM-Rolle verschwand aus ``get_roles`` und das Konto stand ohne
    Rollen da.
    """
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(f"/api/resource/Has Role/{zeile}", json={"parenttype": pt})
    assert antwort.status_code == 403, antwort.text

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")
    assert "sm@x.org" in _sm()


def test_parenttype_unveraendert_erneut_gesendet_erlaubt(client, patched_db, fake_redis) -> None:
    """Unveraendert mitgesendete Werte bleiben erlaubt (ganzes Dokument speichern)."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(
        f"/api/resource/Has Role/{zeile}",
        json={"parenttype": "User", "parentfield": "roles", "parent": "sm@x.org"},
    )
    assert antwort.status_code == 200, antwort.text
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


# ── W-a: `parent` einer bestehenden Zeile ist unveraenderlich ───────────────

def test_parent_verschieben_verweigert(client, patched_db, fake_redis) -> None:
    """Der letzte SM darf seine Zeile nicht auf ein anderes Konto schieben (W-a)."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "b@x.org")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(f"/api/resource/Has Role/{zeile}", json={"parent": "b@x.org"})
    assert antwort.status_code == 403, antwort.text

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


def test_parent_und_rolle_gleichzeitig_verweigert(client, patched_db, fake_redis) -> None:
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "b@x.org")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(
        f"/api/resource/Has Role/{zeile}",
        json={"parent": "b@x.org", "role": "Mitglied"},
    )
    assert antwort.status_code == 403, antwort.text


@pytest.mark.parametrize("neu", ["sm@x.org ", "SM@X.ORG"])
def test_parent_variante_verweigert(client, patched_db, fake_redis, neu) -> None:
    """Auch eine Schreib-Variante desselben Kontos ist eine Aenderung."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(f"/api/resource/Has Role/{zeile}", json={"parent": neu})
    assert antwort.status_code == 403, antwort.text

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


def test_parentfield_verschieben_verweigert(client, patched_db, fake_redis) -> None:
    """`parentfield` bestimmt, wo die Kindzeile im Dokument steht."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(f"/api/resource/Has Role/{zeile}", json={"parentfield": "anderes"})
    assert antwort.status_code == 403, antwort.text


def test_rollenwechsel_ueber_role_erlaubt(client, patched_db, fake_redis) -> None:
    """Der vorgesehene Weg bleibt offen: Rolle wechseln, bei zwei SM."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.put(f"/api/resource/Has Role/{zeile}", json={"role": "Mitglied"})
    assert antwort.status_code == 200, antwort.text
    sess.expire_all()
    assert "System Manager" not in _rollen("sm@x.org")
    assert "Mitglied" in _rollen("sm@x.org")


# ── P5: `name` eines Kontos ist unveraenderlich ─────────────────────────────

def test_user_name_umbenennen_verweigert(client, patched_db, fake_redis) -> None:
    """Der Primaerschluessel eines Kontos laesst sich nicht umbenennen (P5).

    Regression N12b: vor der Behebung gab dieser PUT 200 zurueck und
    der letzte System Manager war weg.
    """
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    antwort = client.put("/api/resource/User/sm@x.org", json={"name": "weg@x.org"})
    assert antwort.status_code == 403, antwort.text

    sess.expire_all()
    assert "sm@x.org" in _sm()


def test_user_name_gleich_gesendet_erlaubt(client, patched_db, fake_redis) -> None:
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    antwort = client.put("/api/resource/User/sm@x.org", json={"name": "sm@x.org"})
    assert antwort.status_code == 200, antwort.text


def test_user_name_umbenennen_ueber_doc_save_verweigert(patched_db, fake_redis) -> None:
    """Derselbe Schutz auf dem `doc.save()`-Weg (frappe.client).

    `Document.name` ist eine NUR-LESEN-Eigenschaft: ein Umbenennen scheitert
    schon am Schreiben (strenger als ein 403). Zusaetzlich laeuft der
    `doc.save()`-Weg durch dieselbe Bestandsschranke — hier ueber ein
    Has-Role-Objekt belegt, dessen `parenttype` ein echtes Feld ist.
    """
    from diakronos_app.frappe_compat.query import get_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    doc = get_doc("User", "sm@x.org")
    with pytest.raises(FrappePermissionError):
        setattr(doc, "name", "weg@x.org")  # noqa: B010 — genau dieser Weg wird geprueft
        doc.save()

    sess.expire_all()
    assert "sm@x.org" in _sm()


def test_has_role_parenttype_ueber_doc_save_verweigert(patched_db, fake_redis) -> None:
    """Und ebenso fuer `Has Role` (frappe.client / doc.save)."""
    from diakronos_app.frappe_compat.query import get_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    doc = get_doc("Has Role", zeile)
    doc.parenttype = "Page"
    with pytest.raises(FrappePermissionError):
        doc.save()

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


# ── Fremdzeilen zaehlen nicht mehr als zweiter SM/Administrator ─────────────

def test_fremdzeile_kein_zweiter_sm(client, patched_db, fake_redis) -> None:
    """Eine Seite `backups` mit SM-Rolle macht die Schranke nicht auf."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "backups", "System Manager", parenttype="Page", zeile="HR-page-backups")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = client.delete(f"/api/resource/Has Role/{zeile}")
    assert antwort.status_code == 403, antwort.text


def test_konto_mit_seitenname_erbt_keine_rolle(patched_db, fake_redis) -> None:
    """Ein Konto, das wie eine Seite heisst, erbt deren Zeile nicht."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    sess.add(HasRole(
        name="HR-page-backups", parent="backups", parenttype="Page",
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.commit()
    _konto(sess, "backups", "Mitglied")

    assert "System Manager" not in _rollen("backups")
    assert "backups" not in _sm()


def test_aktive_administratoren_ohne_fremdzeilen(patched_db, fake_redis) -> None:
    """`_aktive_administratoren` zaehlt nur Benutzerzeilen (R-N10 Punkt 7)."""
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    sess.add(HasRole(
        name="HR-page-ah", parent="anmeldungen-hub", parenttype="Page",
        parentfield="roles", role="Mitgliederadministrator", docstatus=0, idx=1,
    ))
    sess.commit()
    _konto(sess, "anmeldungen-hub", "Mitglied")

    from diakronos_app.api.zugang import _aktive_administratoren

    assert _aktive_administratoren() == {"ma@x.org"}


def test_planrahmen_admin_ohne_fremdzeilen(patched_db, fake_redis) -> None:
    """Ein Konto mit einem Seitennamen ist kein Plan-Administrator."""
    sess = patched_db()
    sess.add(HasRole(
        name="HR-page-backups", parent="backups", parenttype="Page",
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.commit()
    _konto(sess, "backups", "Mitglied")

    from diakronos_app.planrahmen.rechte import Rechte

    assert Rechte(sess, "backups").admin() is False


def test_planrahmen_admin_mit_user_zeile(patched_db, fake_redis) -> None:
    """Gegenprobe: eine echte Benutzerzeile macht weiter Plan-Administrator."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")

    from diakronos_app.planrahmen.rechte import Rechte

    assert Rechte(sess, "sm@x.org").admin() is True
    # Altdaten ohne parenttype zaehlen weiter als Benutzerzeile.
    sess.add(User(name="alt@x.org", email="alt@x.org", enabled=True))
    sess.add(HasRole(
        name="HR-alt", parent="alt@x.org", parenttype="",
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.commit()
    assert Rechte(sess, "alt@x.org").admin() is True


def test_post_fremdzeile_gibt_keine_rolle(client, patched_db, fake_redis) -> None:
    """POST einer `Has Role`-Zeile mit Fremd-`parenttype` bringt keine Rolle."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "b@x.org", "Mitglied")
    set_user("sm@x.org")

    client.post("/api/resource/Has Role", json={
        "name": "HR-x", "parent": "b@x.org", "parenttype": "Page",
        "parentfield": "roles", "role": "System Manager",
    })
    sess.expire_all()
    assert "System Manager" not in _rollen("b@x.org")


# ── Der generische Weg ohne HTTP (api_helpers direkt) ───────────────────────

def test_update_doc_parenttype_verweigert(patched_db, fake_redis) -> None:
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Has Role", zeile, {"parenttype": "Page"})

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


def test_resource_write_ohne_http_verweigert(patched_db, fake_redis) -> None:
    """`_apply_resource_write` ist derselbe Weg ohne HTTP-Transport."""
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = _apply_resource_write("Has Role", zeile, {"parenttype": "Page"})
    assert antwort.status_code == 403

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


def test_loeschen_bleibt_verweigert(patched_db, fake_redis) -> None:
    """Regressionsschutz: der Aussperrschutz selbst bleibt scharf."""
    from diakronos_app.frappe_compat.api_helpers import _delete_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    with pytest.raises(FrappePermissionError):
        _delete_doc("Has Role", zeile)
    with pytest.raises(FrappePermissionError):
        _delete_doc("User", "sm@x.org")

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")
    assert "sm@x.org" in _sm()


def test_has_role_loeschen_zweiter_sm_erlaubt(patched_db, fake_redis) -> None:
    """Gegenprobe: mit zwei SM bleibt das Loeschen der eigenen Zeile offen."""
    from diakronos_app.frappe_compat.router import resource_delete

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_zeile(sess, "sm@x.org")

    antwort = asyncio.run(resource_delete("Has Role", zeile))
    assert antwort.status_code == 202

    sess.expire_all()
    assert "System Manager" not in _rollen("sm@x.org")
    assert "System Manager" in _rollen("sm2@x.org")
