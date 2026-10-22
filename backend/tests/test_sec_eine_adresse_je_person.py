"""Regressionstests: eine E-Mail-Adresse gehoert zu genau EINER Person.

Fachentscheidung (Manuel, 2026-10-19, verbindlich): JEDE PERSON BRAUCHT EINE
EIGENE E-MAIL-ADRESSE. Eine Adresse gehoert hoechstens zu EINEM Mitglied
(Vergleich getrimmt + kleingeschrieben, NFKC); Familienpostfaecher gibt es
nicht mehr.

Quelle der Faelle: die Proben des unabhaengigen Reviews
des Reviews (F1–F4, G1/G2, N01–N21, L1–L5, P4/V1/V2).
Die Erwartungen sind auf die Fachentscheidung umgestellt:
  * F1/F3/F4 (Familienpostfach, Ausschluss sperrt den Partner) sind hinfaellig
    — es gibt keine Familienpostfaecher mehr. An ihre Stelle treten die
    Faelle `test_familienpostfach_*` mit fail-closed-Erwartung fuer den
    ALTbestand.
  * N11 (Altlast-Dublette) ist damit ebenfalls fail-closed: das
    ausgeschlossene Konto bleibt gesperrt.
"""
from __future__ import annotations

import asyncio
import types

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"


def _konto(sess, email, rolle=None, *, mitglied=True, link=True, ausgeschlossen=False,
           m_email=None, kontomail=None):
    sess.add(User(name=email, email=kontomail if kontomail is not None else email,
                  full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                          email=m_email if m_email is not None else email,
                          status="Mitglied", user=email if link else None,
                          ausgeschlossen=1 if ausgeschlossen else 0, docstatus=0, idx=0))
    sess.commit()


def _aktiv(user):
    from diakronos_app.frappe_compat import benutzer_status
    benutzer_status.vergiss(user)
    return benutzer_status.ist_aktiv(user)


def _versuch(fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        return ("abgelehnt", type(e).__name__, str(e)[:120])
    if isinstance(r, dict) and r.get("_error"):
        return ("abgelehnt", r)
    status = getattr(r, "status_code", None)
    if status is not None and status >= 400:
        return ("abgelehnt", status, bytes(r.body)[:120])
    return ("erlaubt", str(r)[:80])


def _basis(patched_db, *, link=False, m_email=None, kontomail=None, wer="ma@x.org"):
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "alt@x.org", SM, link=link, ausgeschlossen=True, m_email=m_email,
           kontomail=kontomail)
    assert _aktiv("alt@x.org") is False, "Vorbedingung"
    set_user(wer)
    return sess


def _melde(tag, r):
    print(f"\n{tag}: {r} | alt aktiv: {_aktiv('alt@x.org')}")


# ── Alte Proben V1/V2 mit sicherer Erwartung ────────────────────────────────
def test_v1_insert_dup_email(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                                     "email": "alt@x.org"}))
    _melde("V1", r)
    assert _aktiv("alt@x.org") is False


def test_v2_set_ausgeschlossen_0(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-alt@x.org", {"ausgeschlossen": 0}))
    _melde("V2", r)
    assert _aktiv("alt@x.org") is False


# ── Neue Umgehungsversuche (MA) ─────────────────────────────────────────────
def test_n01_put_resource_ausgeschlossen_0(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat import router
    r = _versuch(lambda: router._apply_resource_write("Mitglied", "M-alt@x.org", {"ausgeschlossen": 0}))
    _melde("N01", r)
    assert _aktiv("alt@x.org") is False


def test_n02_put_resource_email_aendern(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat import router
    r = _versuch(lambda: router._apply_resource_write("Mitglied", "M-alt@x.org", {"email": "weg@x.org"}))
    _melde("N02", r)
    assert _aktiv("alt@x.org") is False


def test_n03_update_mitglied_email(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.mitglieder import update_mitglied
    r = _versuch(lambda: update_mitglied("M-alt@x.org", {"email": "weg@x.org"}))
    _melde("N03", r)
    assert _aktiv("alt@x.org") is False


def test_n04_delete_resource(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat import router
    r = _versuch(lambda: asyncio.run(router.resource_delete("Mitglied", "M-alt@x.org")))
    _melde("N04", r)
    assert _aktiv("alt@x.org") is False


def test_n05_delete_doc_helper(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _delete_doc
    r = _versuch(lambda: _delete_doc("Mitglied", "M-alt@x.org"))
    _melde("N05", r)
    assert _aktiv("alt@x.org") is False


def test_n06_user_link_null_bei_abweichender_mail(patched_db, fake_redis):
    # Mitglied haengt NUR ueber user-Link (eigene Mitglied-Mail weicht ab)
    _basis(patched_db, link=True, m_email="privat@x.org")
    from diakronos_app.frappe_compat import router
    r = _versuch(lambda: router._apply_resource_write("Mitglied", "M-alt@x.org", {"user": None}))
    _melde("N06", r)
    assert _aktiv("alt@x.org") is False


def test_n07_user_link_leerstring(patched_db, fake_redis):
    _basis(patched_db, link=True, m_email="privat@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-alt@x.org", {"user": ""}))
    _melde("N07", r)
    assert _aktiv("alt@x.org") is False


@pytest.mark.parametrize("variante", [" ALT@X.ORG ", "Alt@x.Org", "\talt@x.org\n"])
def test_n08_insert_schreibvarianten(patched_db, fake_redis, variante):
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                                     "email": variante}))
    _melde(f"N08 {variante!r}", r)
    assert _aktiv("alt@x.org") is False


@pytest.mark.parametrize("variante", ["alt@x.org​", "ａｌｔ@x.org", "alt@x.org."])
def test_n09_unicode_varianten(patched_db, fake_redis, variante):
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                                     "email": variante}))
    _melde(f"N09 {variante!r}", r)
    assert _aktiv("alt@x.org") is False


def test_n10_zweischritt_anlegen_dann_mail(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    from diakronos_app.frappe_compat import router
    r1 = _versuch(lambda: insert(doc={"doctype": "Mitglied", "name": "M-zwei", "vorname": "Z",
                                      "nachname": "Z", "email": "frei@x.org"}))
    r2 = _versuch(lambda: router._apply_resource_write("Mitglied", "M-zwei", {"email": "ALT@x.org"}))
    _melde("N10", (r1, r2))
    assert _aktiv("alt@x.org") is False


def test_n11_altbestand_dublette_laesst_ausschluss_bestehen(patched_db, fake_redis):
    """N11 (neu): eine Altbestand-Dublette hebt den Ausschluss NICHT auf.

    Mit der Fachentscheidung gibt es keine Familienpostfaecher mehr; neue
    Dopplungen lehnt bereits die Datenbank ab. Fuer einen ALTbestand, der die
    Dopplung noch enthaelt, gilt fail closed: das ausgeschlossene Konto bleibt
    gesperrt, auch wenn ein zweiter Datensatz derselben Adresse existiert.

    Der zweite Datensatz wird hier per `bulk_save_objects` eingefuegt — die
    Datenbank verweigert ihn (Unique-Index); der Zustand wird nur nachgestellt,
    um die Aufloesung zu pruefen.
    """
    sess = _basis(patched_db)
    from sqlalchemy import text as _sql

    sess.execute(_sql("DROP INDEX IF EXISTS uq_mitglied_email_normalisiert"))
    sess.add(Mitglied(name="M-dup", vorname="D", nachname="D", email="alt@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    vor = _aktiv("alt@x.org")
    _melde(f"N11 (aktiv bei Altbestand-Dublette: {vor})", ())
    assert vor is False, "Doppelte Adresse: ausgeschlossenes SM-Konto ist AKTIV"


def test_n12_set_mitglied_status(patched_db, fake_redis):
    sess = _basis(patched_db)
    from diakronos_app.api.mitglieder import set_mitglied_status
    r = _versuch(lambda: set_mitglied_status("M-alt@x.org", "Mitglied"))
    sess.expire_all()
    m = sess.get(Mitglied, "M-alt@x.org")
    _melde(f"N12 (danach status={m.status}, ausgeschlossen={m.ausgeschlossen})", r)
    assert _aktiv("alt@x.org") is False


def test_n13_anonymisieren(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.datenschutz import anonymisieren
    req = types.SimpleNamespace(method="POST")
    r = _versuch(lambda: anonymisieren("M-alt@x.org", bestaetigt=True, bestaetigung="ANONYMISIEREN",
                                       request=req))
    _melde("N13", r)
    assert _aktiv("alt@x.org") is False


def test_n14_import_case_dublette_bestaetigt(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    r = _versuch(lambda: import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nZweit;Eintrag; ALT@X.ORG \n", dubletten_ueberspringen=0, bestaetigt=1))
    _melde("N14", r)
    assert _aktiv("alt@x.org") is False


def test_n15_import_zwei_zeilen_selbe_mail(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    r = _versuch(lambda: import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nA;Eins;alt@x.org\nB;Zwei;Alt@x.org\n",
        dubletten_ueberspringen=0, bestaetigt=1))
    _melde("N15", r)
    assert _aktiv("alt@x.org") is False


def test_n16_anmeldung_genehmigen_dublette(patched_db, fake_redis):
    sess = _basis(patched_db)
    from diakronos_app.models.diakonos import Anmeldung
    sess.add(Anmeldung(name="ANM-1", anmeldungstyp="Mitglied-Registrierung", status="Offen",
                       vorname="Boese", nachname="Kopie", email="Alt@X.org", docstatus=0, idx=0))
    sess.commit()
    from diakronos_app.api.admin_hub import genehmige_anmeldung
    r = _versuch(lambda: genehmige_anmeldung("ANM-1", dublette_bestaetigt=1))
    _melde("N16", r)
    assert _aktiv("alt@x.org") is False


def test_n17_create_mitglied_variante(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.api.mitglieder import create_mitglied
    r = _versuch(lambda: create_mitglied("Z", "Z", email=" ALT@x.org"))
    _melde("N17", r)
    assert _aktiv("alt@x.org") is False


def test_n18_frappe_client_save_set_value(patched_db, fake_redis):
    _basis(patched_db)
    from diakronos_app.frappe_compat import router
    import diakronos_app.api.frappe_core as fc
    namen = [n for n in dir(fc) if n in ("save", "set_value", "client_save", "client_set_value")]
    from diakronos_app.frappe_compat.query import get_doc
    doc = get_doc("Mitglied", "M-alt@x.org")
    r1 = _versuch(lambda: doc.db_set("ausgeschlossen", 0))
    _melde(f"N18 db_set (frappe_core hat {namen})", r1)
    assert _aktiv("alt@x.org") is False


def test_n19_nur_user_link_kein_email(patched_db, fake_redis):
    _basis(patched_db, link=True, m_email="")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-alt@x.org", {"ausgeschlossen": "0"}))
    _melde("N19", r)
    assert _aktiv("alt@x.org") is False


def test_n20_kontomail_abweichend(patched_db, fake_redis):
    # Konto-Name alt@x.org, Konto-E-Mail " ALT@X.ORG " (Altbestand), Mitglied nur ueber Mail
    _basis(patched_db, kontomail=" ALT@X.ORG ")
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                                     "email": "alt@x.org"}))
    _melde("N20", r)
    assert _aktiv("alt@x.org") is False


def test_n21_ma_als_user_link_auf_dublette(patched_db, fake_redis):
    # Zweites Mitglied mit user=alt@x.org (direkter Link, nicht ausgeschlossen)
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                                     "user": "alt@x.org"}))
    _melde("N21", r)
    assert _aktiv("alt@x.org") is False


# ── Familienpostfach / Ueber-Sperre (Regression?) ───────────────────────────
def test_f1_eigene_adressen_je_person_trennen_die_konten(patched_db, fake_redis):
    """F1 (neu): jede Person hat eine eigene Adresse — Ausschluss trifft nur sie.

    Die frueheren Proben F1/F3/F4 prueften die Familienpostfach-Grenze
    („Ausschluss der Frau sperrt den Partner nicht"). Diese Grenze ist mit der
    Fachentscheidung hinfaellig: es gibt keine Familienpostfaecher mehr.
    Geprueft wird jetzt, was an ihre Stelle tritt — eigene Adressen trennen
    die Konten sauber, und der Ausschluss bleibt auf die Person begrenzt.
    """
    sess = patched_db()
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "frau@x.org", None, m_email="frau@x.org", ausgeschlossen=True)
    _konto(sess, "mann@x.org", None, m_email="mann@x.org", ausgeschlossen=False)
    assert _aktiv("frau@x.org") is False
    assert _aktiv("mann@x.org") is True, "Fremde Person mitgesperrt"


def test_f2_konto_der_ausgeschlossenen_adresse_ist_gesperrt(patched_db, fake_redis):
    """F2 (neu): fail closed — die Adresse eines Ausgeschlossenen sperrt das Konto.

    Ein Konto, das nur ueber die E-Mail mit einer ausgeschlossenen Person
    verbunden ist, ist gesperrt. Mit eigenen Adressen je Person ist dieser
    Fall eindeutig (keine Mitnahme fremder Konten mehr).
    """
    sess = patched_db()
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "frau@x.org", None, m_email="frau@x.org", ausgeschlossen=True)
    # Konto "frau" traegt dieselbe Adresse wie die ausgeschlossene Person.
    _konto(sess, "fam", None, mitglied=False, kontomail="frau@x.org")
    assert _aktiv("fam") is False


def test_f3_ausschluss_der_frau_laesst_den_sm_partner_frei(patched_db, fake_redis):
    """F3 (neu): eigene Adressen — der Ausschluss einer Person trifft den SM nicht."""
    sess = patched_db()
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "sm2@x.org", SM, m_email="sm2privat@x.org")
    _konto(sess, "frau@x.org", None, m_email="frau@x.org")
    set_user("sm@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-frau@x.org", {"ausgeschlossen": 1}))
    assert r[0] == "erlaubt", r
    assert _aktiv("sm2@x.org") is True, "Ausschluss einer fremden Person sperrt den SM"


def test_f4_ma_schliesst_normale_person_neben_sm_aus(patched_db, fake_redis):
    """F4 (neu): normale Pflege bleibt erlaubt — eigene Adressen je Person."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "sm2@x.org", SM, m_email="sm2privat@x.org")
    _konto(sess, "frau@x.org", None, m_email="frau@x.org")
    set_user("ma@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-frau@x.org", {"ausgeschlossen": 1}))
    print("\nF4:", r)
    assert r[0] == "erlaubt", r


# ── Legitime Wege ───────────────────────────────────────────────────────────
def test_l1_sm_hebt_ausschluss_auf(patched_db, fake_redis):
    _basis(patched_db, wer="sm@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    r = _versuch(lambda: _update_doc("Mitglied", "M-alt@x.org", {"ausgeschlossen": 0}))
    _melde("L1", r)
    assert r[0] == "erlaubt" and _aktiv("alt@x.org") is True


def test_l2_sm_set_status(patched_db, fake_redis):
    _basis(patched_db, wer="sm@x.org")
    from diakronos_app.api.mitglieder import set_mitglied_status
    r = _versuch(lambda: set_mitglied_status("M-alt@x.org", "Mitglied"))
    _melde("L2", r)
    assert r[0] == "erlaubt" and _aktiv("alt@x.org") is True


def test_l3_sm_loescht(patched_db, fake_redis):
    _basis(patched_db, wer="sm@x.org")
    from diakronos_app.frappe_compat.api_helpers import _delete_doc
    r = _versuch(lambda: _delete_doc("Mitglied", "M-alt@x.org"))
    _melde("L3", r)
    assert r[0] == "erlaubt"


def test_l4_ma_normale_pflege(patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "normal@x.org", None, ausgeschlossen=True)
    _konto(sess, "n2@x.org", None)
    set_user("ma@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.api.mitglieder import update_mitglied, create_mitglied, set_mitglied_status
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    rs = {
        "aufheben": _versuch(lambda: _update_doc("Mitglied", "M-normal@x.org", {"ausgeschlossen": 0})),
        "status": _versuch(lambda: set_mitglied_status("M-n2@x.org", "Gast")),
        "mail": _versuch(lambda: update_mitglied("M-n2@x.org", {"email": "N2neu@x.org"})),
        "anlegen": _versuch(lambda: create_mitglied("Neu", "Person", email="neu@x.org")),
        "import": _versuch(lambda: import_mitglieder_uebernehmen("Vorname;Nachname;E-Mail\nI;Mp;imp@x.org\n")),
        "ausschluss": _versuch(lambda: _update_doc("Mitglied", "M-n2@x.org", {"ausgeschlossen": 1})),
    }
    print("\nL4:", rs)
    assert all(v[0] == "erlaubt" for v in rs.values()), rs
    assert _aktiv("normal@x.org") is True


def test_l5_sm_import_dublette_legt_keine_zweite_person_an(patched_db, fake_redis):
    """L5 (neu): auch der System Manager legt keine zweite Person mit der Adresse an.

    Vorher (W-a/N11-L5) holte ein SM-Import einer „bestaetigten Dublette" ein
    ausgeschlossenes Verwaltungskonto ohne Hinweis zurueck. Mit der
    Fachentscheidung ist der Fall gegenstandslos: eine Adresse gehoert zu
    genau EINER Person, auch fuer den System Manager. Der Import darf die
    zweite Zeile nicht anlegen.
    """
    sess = _basis(patched_db, wer="sm@x.org")
    before = sess.query(Mitglied).filter(Mitglied.email == "alt@x.org").count()
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    r = _versuch(lambda: import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nZweit;Eintrag;alt@x.org\n", dubletten_ueberspringen=0, bestaetigt=1))
    _melde("L5 (SM, Dublette bestaetigt)", r)
    sess.expire_all()
    after = sess.query(Mitglied).filter(Mitglied.email == "alt@x.org").count()
    assert after == before, "Import hat eine ZWEITE Person mit derselben Adresse angelegt"
    assert _aktiv("alt@x.org") is False, "Ausschluss wurde durch den Import aufgehoben"


def test_g1_ma_import_konto_mit_rolle_mitglied(patched_db, fake_redis):
    # Konto ohne Mitglied, nur Rolle "Mitglied" (z. B. wartendes/selbst angelegtes Konto)
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "warte@x.org", "Mitglied", mitglied=False)
    set_user("ma@x.org")
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    r = _versuch(lambda: import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nAnna;Neu;anna@x.org\nWarte;Konto;warte@x.org\n",
        dubletten_ueberspringen=0, bestaetigt=1))
    print("\nG1:", r)
    assert r[0] == "erlaubt", "Import scheitert ganz an Konto mit Rolle 'Mitglied'"


def test_g2_ma_insert_konto_mit_rolle_mitglied(patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "warte@x.org", "Mitglied", mitglied=False)
    set_user("ma@x.org")
    from diakronos_app.api.frappe_core import insert
    r = _versuch(lambda: insert(doc={"doctype": "Mitglied", "vorname": "W", "nachname": "K",
                                     "email": "warte@x.org"}))
    print("\nG2:", r)
    assert r[0] == "erlaubt"
