"""N10 / W1 (R-P1-8e): Aussperrschutz auf den GENERISCHEN Wegen fuer User/Has Role.

DER BEFUND (W1)
---------------------------------------
Der Aussperrschutz galt nur auf der Mitglied-Ebene. Ueber die generischen Wege
liess sich der einzige System Manager trotzdem selbst aussperren
(reproduziert im Nachreview):

  * ``DELETE /api/resource/Has Role/<eigene SM-Rolle>`` -> 202, Rollen danach ()
  * ``PUT  /api/resource/User/<sm>`` mit ``{enabled: 0}`` -> Konto inaktiv
  * ``DELETE /api/resource/User/<sm>`` -> Konto weg

Nur System Manager kommen an diese Wege (Mitgliederadministrator bekommt 403),
also kein Eskalationspfad — aber die Zusage „der letzte aktive System Manager
verliert nie seine Rolle/das Konto“ galt nur ueber die Zugang-Endpunkte.

Jede Probe ist mit der SICHEREN Erwartung uebernommen: der generische Weg
verweigert (403 / ``PermissionError``) ODER das Konto bleibt aktiv mit seinen
Rollen. Ohne die Schranke ``_pruefe_konto_schreibzugriff`` in
``frappe_compat/api_helpers.py`` waeren die Proben rot.
"""

from __future__ import annotations

import asyncio

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied


def _konto(sess, email: str, rolle: str | None = None, *, enabled: bool = True) -> None:
    """Konto anlegen (ohne Mitglied) — wie im W1-Probenlauf."""
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(
            name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
            parentfield="roles", role=rolle, docstatus=0, idx=1,
        ))
    sess.commit()


def _aktiv(user: str) -> bool:
    from diakronos_app.frappe_compat import benutzer_status

    benutzer_status.vergiss(user)
    return benutzer_status.ist_aktiv(user)


def _rollen(user: str) -> tuple[str, ...]:
    from diakronos_app.frappe_compat.permissions import get_roles

    return get_roles(user)


def _sm_rolle_zeile(sess, user: str) -> str:
    """Name der Has-Role-Zeile mit der Rolle System Manager fuer `user`."""
    zeile = (
        sess.query(HasRole)
        .filter(HasRole.parent == user, HasRole.role == "System Manager")
        .one()
    )
    return str(zeile.name)


# ── W1a: `Has Role` loeschen (generischer Weg) ──────────────────────────────


def test_has_role_loeschen_einziger_sm_verweigert(patched_db, fake_redis) -> None:
    """Der letzte aktive SM darf seine SM-Rolle nicht per DELETE verlieren."""
    from diakronos_app.frappe_compat.router import resource_delete

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_rolle_zeile(sess, "sm@x.org")
    assert _aktiv("sm@x.org")

    antwort = asyncio.run(resource_delete("Has Role", zeile))
    assert antwort.status_code == 403

    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")
    assert _aktiv("sm@x.org")


def test_has_role_loeschen_zweiter_sm_erlaubt(patched_db, fake_redis) -> None:
    """Mit einem zweiten aktiven SM darf die eigene Rolle weg."""
    from diakronos_app.frappe_compat.router import resource_delete

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_rolle_zeile(sess, "sm@x.org")

    antwort = asyncio.run(resource_delete("Has Role", zeile))
    assert antwort.status_code == 202

    sess.expire_all()
    assert "System Manager" not in _rollen("sm@x.org")
    assert "System Manager" in _rollen("sm2@x.org")


def test_has_role_fremde_rolle_loeschen_erlaubt(patched_db, fake_redis) -> None:
    """Eine NICHT-System-Manager-Rolle darf auch die des letzten SM weg."""
    from diakronos_app.frappe_compat.router import resource_delete

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    sess.add(HasRole(
        name="HR-sm-Kalender", parent="sm@x.org", parenttype="User",
        parentfield="roles", role="Kalenderadministrator", docstatus=0, idx=2,
    ))
    sess.commit()
    set_user("sm@x.org")

    antwort = asyncio.run(resource_delete("Has Role", "HR-sm-Kalender"))
    assert antwort.status_code == 202
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


# ── W1b: `User` sperren loeschen (generischer Weg) ──────────────────────────


@pytest.mark.parametrize("weg", ["resource_update", "delete_doc", "update_doc"])
def test_user_letzter_sm_verweigert(client, patched_db, fake_redis, weg) -> None:
    """Sperren/Loeschen des letzten SM-Kontos wird auf jedem Weg verweigert."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("sm@x.org")
    assert _aktiv("sm@x.org")

    if weg == "resource_update":
        antwort = client.put("/api/resource/User/sm@x.org", json={"enabled": 0})
        assert antwort.status_code == 403, antwort.text
        sess.expire_all()
        assert _aktiv("sm@x.org")
    elif weg == "delete_doc":
        from diakronos_app.frappe_compat.api_helpers import _delete_doc

        with pytest.raises(FrappePermissionError):
            _delete_doc("User", "sm@x.org")
        sess.expire_all()
        assert sess.get(User, "sm@x.org") is not None
        assert _aktiv("sm@x.org")
    else:
        from diakronos_app.frappe_compat.api_helpers import _update_doc

        with pytest.raises(FrappePermissionError):
            _update_doc("User", "sm@x.org", {"enabled": 0})
        sess.expire_all()
        assert _aktiv("sm@x.org")


def test_user_letzter_sm_mit_zweitem_erlaubt(patched_db, fake_redis) -> None:
    """Mit einem zweiten aktiven SM darf sich der erste sperren."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")

    _update_doc("User", "sm@x.org", {"enabled": 0})
    sess.expire_all()
    assert not _aktiv("sm@x.org")
    assert _aktiv("sm2@x.org")


def test_user_nicht_sm_sperren_erlaubt(patched_db, fake_redis) -> None:
    """Ein gewoehnliches Konto darf der SM jederzeit sperren."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "mitglied@x.org", "Mitglied")
    set_user("sm@x.org")

    _update_doc("User", "mitglied@x.org", {"enabled": 0})
    sess.expire_all()
    assert not _aktiv("mitglied@x.org")


# ── W1c: `frappe.client.insert` laeuft durch dieselbe Schranke ──────────────


def test_client_insert_user_bleibt_gesperrt_fuer_nicht_sm(patched_db, fake_redis) -> None:
    """Ein Nicht-SM kommt an `User`/`Has Role` ohnehin nicht (Rollenmatrix)."""
    from diakronos_app.api import frappe_core

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        frappe_core.insert({"doctype": "Has Role", "parent": "ma@x.org", "role": "System Manager"})


def test_client_insert_role_auf_letztes_sm_konto_wird_geprueft(patched_db, fake_redis) -> None:
    """Der generische Insert-Weg ruft dieselbe Schranke (kein Umgehen)."""
    from diakronos_app.frappe_compat import api_helpers

    # Direkter Nachweis: die Schranke wird fuer Has Role gerufen und lehnt das
    # Entfernen der letzten SM-Rolle ab (loeschen=True).
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    zeile = _sm_rolle_zeile(sess, "sm@x.org")

    with pytest.raises(FrappePermissionError):
        api_helpers._pruefe_konto_schreibzugriff("Has Role", zeile, {}, loeschen=True)


# ── W-a: `parent` einer SM-Zeile verschieben (R-N10) ────────────────────────
#
# DER BEFUND (W-a)
# -------------------------------
# `PUT /api/resource/Has Role/<SM-Zeile>` mit `{"parent": "<anderes Konto>"}`
# verschob die System-Manager-Rolle auf ein anderes Konto: `_has_role_ziel`
# nahm den NEUEN parent als Konto und die Pruefung „Rolle bleibt SM" liess es
# durch. Das urspruengliche Konto verlor seine SM-Rolle still — der letzte SM
# war damit aussperrbar. `parent` einer Has-Role-Zeile ist seither nicht mehr
# aenderbar (bzw. der Alt-Parent wird mitgeprueft).


def test_has_role_parent_verschieben_verweigert(client, patched_db, fake_redis) -> None:
    """W-a: Der einzige SM darf seine SM-Zeile nicht auf ein anderes Konto schieben."""
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "opfer@x.org")
    set_user("sm@x.org")
    zeile = _sm_rolle_zeile(sess, "sm@x.org")

    antwort = client.put(
        f"/api/resource/Has Role/{zeile}", json={"parent": "opfer@x.org"}
    )
    assert antwort.status_code == 403, antwort.text

    sess.expire_all()
    # Die Zeile bleibt beim alten Konto — der letzte SM behaelt seine Rolle.
    assert "System Manager" in _rollen("sm@x.org")
    assert "System Manager" not in _rollen("opfer@x.org")


def test_has_role_parent_verschieben_mit_zweitem_sm_verweigert(patched_db, fake_redis) -> None:
    """`parent` einer bestehenden Zeile ist unveraenderlich (N12b/W-a).

    N10 hatte hier das Verschieben mit einem zweiten SM noch erlaubt (kein
    Aussperrrisiko). N12b schliesst die Ursache statt nur des letzten Falls:
    eine wandernde Zeile entzieht dem Altkonto still eine Rolle, und wer sie
    verschiebt, ist nicht mehr erkennbar. Der Rollenwechsel laeuft ueber
    `role` (siehe `test_rollenwechsel_ueber_role_erlaubt`).
    """
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    _konto(sess, "opfer@x.org")
    set_user("sm@x.org")
    zeile = _sm_rolle_zeile(sess, "sm@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Has Role", zeile, {"parent": "opfer@x.org"})
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")
    assert "System Manager" in _rollen("sm2@x.org")
    assert "System Manager" not in _rollen("opfer@x.org")


# ── Punkt 7: Has-Role-Zeilen mit fremdem `parenttype` ───────────────────────
#
# Die `Has Role`-Tabelle enthaelt historisch auch Zeilen, deren Elter kein User
# ist (Frappe-Seiten/Berichte). Zaehlte der Aussperrschutz sie mit, koennte ein
# gleichnamiger `parent` einen weiteren „System Manager" vortaeuschen und den
# letzten echten aussperrbar machen. Alle Rollen-Leser filtern auf
# `parenttype='User'`.


def test_fremde_has_role_zeile_zaehlt_nicht_als_rolle(patched_db, fake_redis) -> None:
    """Eine `Has Role`-Zeile mit parenttype != 'User' gibt keinem Konto Rollen."""
    from diakronos_app.api.zugang import _rollen_von, _aktive_system_manager
    from diakronos_app.frappe_compat.permissions import get_roles

    sess = patched_db()
    _konto(sess, "mitglied@x.org", "Mitglied")
    # Fremde Zeile: gleicher `parent`-Text, aber ein anderer Elterntyp.
    sess.add(HasRole(
        name="HR-ToDo-SM", parent="mitglied@x.org", parenttype="ToDo",
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.commit()

    assert _rollen_von("mitglied@x.org") == {"Mitglied"}
    assert "System Manager" not in get_roles("mitglied@x.org")
    assert "mitglied@x.org" not in _aktive_system_manager()


def test_fremde_zeile_sperrt_letzten_sm_nicht_aus(patched_db, fake_redis) -> None:
    """Der echte letzte SM bleibt geschuetzt, obwohl eine fremde Zeile existiert.

    Ohne den parenttype-Filter zaehlte `_aktive_system_manager` das Mitglied
    faelschlich als zweiten SM mit, und der letzte echte SM waere aussperrbar.
    """
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "mitglied@x.org", "Mitglied")
    sess.add(HasRole(
        name="HR-Report-SM", parent="mitglied@x.org", parenttype="Report",
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.commit()
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("User", "sm@x.org", {"enabled": 0})
    sess.expire_all()
    assert _aktiv("sm@x.org")


def test_altzeile_ohne_parenttype_zaehlt_als_user(patched_db, fake_redis) -> None:
    """Altdaten ohne `parenttype` (NULL/leer) sind Benutzer-Rollen.

    Der Nachtrag R-N10 Punkt 7 warnt vor FREMDEN `parenttype`-Werten. Ein
    reiner `parenttype == "User"`-Filter verwirft aber zugleich die
    Altdaten-Zeilen ohne `parenttype` — und damit die Rollen JEDES Kontos
    (Regression im N12-Testlauf: der Administrator bekam 403, weil seine
    `Has Role`-Zeile keinen `parenttype` trug). Die datenschutz-Auskunft
    behandelt solche Zeilen ebenso als Benutzer-Rollen
    (`api/datenschutz.py`, „Zeilen ohne parenttype").
    """
    from diakronos_app.api.zugang import _rollen_von, _aktive_system_manager
    from diakronos_app.frappe_compat.permissions import get_roles

    sess = patched_db()
    # Konto mit Rollen-Zeile OHNE parenttype (NULL) und einer mit leerem Wert.
    sess.add(User(name="alt@x.org", email="alt@x.org", enabled=True))
    sess.add(HasRole(
        name="HR-alt-1", parent="alt@x.org", parenttype=None,
        parentfield="roles", role="System Manager", docstatus=0, idx=1,
    ))
    sess.add(HasRole(
        name="HR-alt-2", parent="alt@x.org", parenttype="",
        parentfield="roles", role="Mitgliederadministrator", docstatus=0, idx=2,
    ))
    sess.commit()

    assert _rollen_von("alt@x.org") == {"System Manager", "Mitgliederadministrator"}
    assert "System Manager" in get_roles("alt@x.org")
    assert "alt@x.org" in _aktive_system_manager()

