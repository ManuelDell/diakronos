"""Review-Proben N12 (Aussperrschutz / parenttype). SICHERE Erwartung je Probe.

Uebernommen aus dem vorausgehenden Review als Regressionstests fuer
N12b. P1, P2, P3, P4, P5, P6, P7, P10, P11, P12 sind die Proben, die N12b
schliesst; P8/P9 pruefen die letzten Leser ohne ``parenttype``-Filter.
"""
from __future__ import annotations
import asyncio
import pytest
from diakronos_app.frappe_compat.exceptions import PermissionError as FPE
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User


def _konto(sess, email, rolle=None, *, enabled=True, parenttype="User", zeile=None):
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=zeile or f"HR-{email}-{rolle}", parent=email, parenttype=parenttype,
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()


def _rollen(u):
    from diakronos_app.frappe_compat.permissions import get_roles
    return get_roles(u)


def _sm():
    from diakronos_app.api.zugang import _aktive_system_manager
    return _aktive_system_manager()


# P1: parenttype der einzigen SM-Zeile auf einen Fremdtyp setzen
@pytest.mark.parametrize("pt", ["Page", "Report", "ToDo"])
def test_p1_parenttype_umbiegen(client, patched_db, fake_redis, pt):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    r = client.put("/api/resource/Has Role/HR-sm@x.org-System Manager", json={"parenttype": pt})
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org"), (r.status_code, r.text)
    assert "sm@x.org" in _sm()


# P2: parent verschieben (Befund W-a) HTTP
def test_p2_parent_verschieben(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager"); _konto(sess, "b@x.org")
    set_user("sm@x.org")
    r = client.put("/api/resource/Has Role/HR-sm@x.org-System Manager", json={"parent": "b@x.org"})
    assert r.status_code == 403, r.text
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


# P3: parent + role gleichzeitig
def test_p3_parent_und_rolle(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager"); _konto(sess, "b@x.org")
    set_user("sm@x.org")
    r = client.put("/api/resource/Has Role/HR-sm@x.org-System Manager",
                   json={"parent": "b@x.org", "role": "Mitglied"})
    assert r.status_code == 403, r.text


# P4: parent auf Variante desselben Kontos (Leerraum / Grossschreibung)
@pytest.mark.parametrize("neu", ["sm@x.org ", "SM@X.ORG"])
def test_p4_parent_variante(client, patched_db, fake_redis, neu):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    client.put("/api/resource/Has Role/HR-sm@x.org-System Manager", json={"parent": neu})
    sess.expire_all()
    assert "System Manager" in _rollen("sm@x.org")


# P5: User-Kennung (Primaerschluessel) umbenennen
def test_p5_user_name_umbenennen(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")
    r = client.put("/api/resource/User/sm@x.org", json={"name": "weg@x.org"})
    sess.expire_all()
    assert "sm@x.org" in _sm(), (r.status_code, r.text)


# P6: zweiter "SM" nur ueber Fremdzeile -> Loeschen der echten SM-Zeile verweigert
def test_p6_fremdzeile_kein_zweiter_sm(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "backups", "System Manager", parenttype="Page", zeile="HR-page-backups")
    set_user("sm@x.org")
    r = client.delete("/api/resource/Has Role/HR-sm@x.org-System Manager")
    assert r.status_code == 403, r.text


# P7: Konto namens einer Frappe-Seite erbt keine Rechte
def test_p7_konto_mit_seitenname_erbt_nichts(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    sess.add(HasRole(name="HR-page-backups", parent="backups", parenttype="Page",
                     parentfield="roles", role="System Manager", docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "backups", "Mitglied")
    assert "System Manager" not in _rollen("backups")
    assert "backups" not in _sm()


# P8: Planrahmen-Admin fuer Konto mit Seitennamen
def test_p8_planrahmen_admin_seitenname(patched_db, fake_redis):
    sess = patched_db()
    sess.add(HasRole(name="HR-page-backups", parent="backups", parenttype="Page",
                     parentfield="roles", role="System Manager", docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "backups", "Mitglied")
    from diakronos_app.planrahmen import rechte
    import inspect
    src = inspect.getsource(rechte)
    # nur Info: ob admin() parenttype filtert
    assert "parenttype" in src.split("def admin")[1].split("def ")[0], "planrahmen.rechte.admin ohne parenttype-Filter"


# P9: _aktive_administratoren zaehlt Fremdzeilen eines gleichnamigen Kontos
def test_p9_aktive_administratoren(patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    sess.add(HasRole(name="HR-page-ah", parent="anmeldungen-hub", parenttype="Page",
                     parentfield="roles", role="Mitgliederadministrator", docstatus=0, idx=1))
    sess.commit()
    _konto(sess, "anmeldungen-hub", "Mitglied")
    from diakronos_app.api.zugang import _aktive_administratoren
    assert _aktive_administratoren() == {"ma@x.org"}


# P10: Has-Role-Zeile mit Fremd-parenttype fuer ein echtes Konto per POST anlegen gibt keine Rolle
def test_p10_post_fremdzeile(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "b@x.org", "Mitglied")
    set_user("sm@x.org")
    client.post("/api/resource/Has Role", json={"name": "HR-x", "parent": "b@x.org",
                "parenttype": "Page", "parentfield": "roles", "role": "System Manager"})
    sess.expire_all()
    assert "System Manager" not in _rollen("b@x.org")


# P11: Moderator-Auswahl liefert keine E-Mails, verlangt Rolle
def test_p11_moderator_auswahl(client, patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "ka@x.org", "Kalenderadministrator")
    _konto(sess, "m@x.org", "Mitglied")
    from diakronos_app.api.zugang import get_moderator_auswahl
    set_user("ka@x.org")
    res = get_moderator_auswahl()
    for k in res["konten"]:
        assert set(k) <= {"user", "name", "aktiv"}
    set_user("m@x.org")
    with pytest.raises(Exception):
        get_moderator_auswahl()


# P12: Moderator-Auswahl fuer Ressourcenmoderator / ausgeschlossene / deaktivierte Konten
def test_p12_moderator_auswahl_listet_inaktive(client, patched_db, fake_redis):
    """N12b: deaktivierte Konten stehen NICHT mehr in der Auswahl.

    Der Review meldete (klein): die Auswahl listete auch deaktivierte Konten
    und damit deren Anzeigenamen (bzw. die Adresse als Rueckfall). Fuer die
    Auswahl eines Moderators sind sie ohne Nutzen.
    """
    sess = patched_db()
    _konto(sess, "ka@x.org", "Kalenderadministrator")
    _konto(sess, "aus@x.org", "Mitglied", enabled=False)
    from diakronos_app.api.zugang import get_moderator_auswahl
    set_user("ka@x.org")
    res = get_moderator_auswahl()
    namen = [k["user"] for k in res["konten"]]
    assert "ka@x.org" in namen
    assert "aus@x.org" not in namen


def test_p12b_ausgeschlossenes_mitglied_behaelt_konto_aktiv(client, patched_db, fake_redis):
    """Ein ausgeschlossenes Mitglied ist kein gueltiger Moderator.

    `ausgeschlossen` ist KEIN `enabled`-Flag — das Konto bleibt technisch
    aktiv, `get_roles` liefert aber keine Rollen mehr. Als Moderator waere es
    damit wirkungslos; die Auswahl bietet weiterhin alle AKTIVEN Konten an
    (sie filtert nur `enabled`), was hier festgehalten wird.
    """
    sess = patched_db()
    _konto(sess, "ka@x.org", "Kalenderadministrator")
    _konto(sess, "raus@x.org", "Mitglied")
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(name="M-RAUS", vorname="Raus", nachname="X",
                      email="raus@x.org", user="raus@x.org",
                      ausgeschlossen=True, docstatus=0, idx=0))
    sess.commit()

    from diakronos_app.frappe_compat.permissions import get_roles
    from diakronos_app.api.zugang import get_moderator_auswahl

    assert get_roles("raus@x.org") == ()
    set_user("ka@x.org")
    res = get_moderator_auswahl()
    assert "ka@x.org" in [k["user"] for k in res["konten"]]
