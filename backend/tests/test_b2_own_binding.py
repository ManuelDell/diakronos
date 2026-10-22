"""B2: eigene Daten folgen der expliziten Nutzerbindung, nicht fremder Email."""
import pytest

from tests.test_b2_adressbuch_sichtbarkeit import _set_user, _zeile, _sichtbarkeit_setzen, sess
from tests.test_permissions import hierarchie


@pytest.mark.parametrize("route", ["liste", "detail", "adressbuch"])
def test_eigene_listenzeile_per_user_link(client, hierarchie, sess, route):
    from diakronos_app.models.diakonos import Mitglied
    own = sess.get(Mitglied, "M-gruppe-a1")
    own.user = "mitglied-a@example.org"
    own.email = "zz-b-neue-email@example.invalid"
    own.telefonnummer = "zz-b-telefon"
    _sichtbarkeit_setzen(sess, own.name, email=False, telefonnummer=False)
    _set_user("mitglied-a@example.org")
    # Permission-Overlap bleibt im Original mangels Email-Match sonst leer;
    # der eigene User-Link muss dennoch seine Listen-Zeile sehen.
    if route == "liste":
        data = _zeile(client, own.name)
    elif route == "detail":
        r = client.get("/api/method/mitglieder.get_mitglied_detail", params={"mitglied_id": own.name})
        assert r.status_code == 200
        data = r.json()["message"]["data"]
    else:
        r = client.get("/api/method/mitglieder.get_adressbuch")
        data = next(z for z in r.json()["message"]["data"] if z["name"] == own.name)
    assert data["telefonnummer"] == "zz-b-telefon"


def test_doppelte_email_ist_nicht_herstellbar(hierarchie, sess):
    """Ein zweites Mitglied mit derselben Adresse gibt es nicht mehr.

    SEC-b (Fachentscheidung Manuel 2026-10-19): Jede Person hat eine eigene
    E-Mail-Adresse. Der frueher hier gepruefte Zustand „mehrdeutige Adresse“
    (Familienpostfach) ist auf Datenebene nicht mehr herstellbar — der
    partielle Unique-Index `uq_mitglied_email_normalisiert` verweigert ihn.
    Damit kann eine fremde Adresse auch nicht mehr zur „eigenen“ werden.
    """
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import ist_eigenes_mitglied
    other = sess.get(Mitglied, "M-verantw-a")
    other.email = "mitglied-a@example.org"
    with pytest.raises(IntegrityError):
        sess.commit()
    sess.rollback()
    _set_user("mitglied-a@example.org")
    assert not ist_eigenes_mitglied(other.name)


def test_private_resource_delete_verweigert(client, hierarchie):
    _set_user("mitglied-a@example.org")
    assert client.delete("/api/resource/Mitglied/M-gruppe-b1").status_code == 403


@pytest.mark.parametrize("admin", [False, True])
def test_sichtbarkeitsblob_nur_im_eigenen_detail_nicht_in_liste(client, hierarchie, sess, admin):
    from diakronos_app.models.core import HasRole
    if admin:
        sess.add(HasRole(name="zz-b-shape-role", parent="mitglied-a@example.org",
                        parenttype="User", parentfield="roles", role="System Manager"))
        sess.commit()
    _sichtbarkeit_setzen(sess, "M-gruppe-a1", email=False)
    _set_user("mitglied-a@example.org")
    assert "adressbuch_sichtbarkeit" not in _zeile(client, "M-gruppe-a1")
    r = client.get("/api/method/mitglieder.get_mitglied_detail",
                   params={"mitglied_id": "M-gruppe-a1"})
    assert "adressbuch_sichtbarkeit" in r.json()["message"]["data"]
