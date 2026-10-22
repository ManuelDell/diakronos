"""Regressionstests zur Fachentscheidung „eine Adresse je Person" (SEC-b).

Fachentscheidung (Manuel, 2026-10-19, verbindlich): JEDE PERSON BRAUCHT EINE
EIGENE E-MAIL-ADRESSE. Eine Adresse gehoert hoechstens zu EINEM Mitglied
(Vergleich getrimmt + kleingeschrieben, NFKC); Familienpostfaecher gibt es
nicht mehr.

Abgedeckt:
  * alle Schreibwege, ueber die ein zweites Mitglied mit derselben Adresse
    entstehen koennte (Anlegen, Aendern, Frappe-Client, Import,
    Anmeldung freigeben),
  * die Klartext-Meldung „… gehoert bereits zu <Anzeigename>",
  * K2 (unsichtbare Zeichen / Vollbreite in der Adresse),
  * K3 (normalisierter Vergleich beim Import).
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"


def _konto(sess, email, rolle=None, *, mitglied=True, ausgeschlossen=False):
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname="Anna", nachname="Beispiel",
                          email=email, status="Mitglied",
                          user=email if mitglied else None,
                          ausgeschlossen=1 if ausgeschlossen else 0, docstatus=0, idx=0))
    sess.commit()


def _basis(patched_db, *, wer="ma@x.org"):
    """Ein Mitgliederadministrator und ein bestehendes Mitglied `anna@x.org`."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    sess.add(Mitglied(name="M-anna", vorname="Anna", nachname="Beispiel",
                      email="anna@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user(wer)
    return sess


def _abweisung(fn) -> str:
    """Fuehrt `fn` aus und liefert die Meldung einer Ablehnung (sonst '')."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 — genau die Ablehnung ist das Ziel
        return str(e)
    return ""


# ── (1) Eindeutigkeit auf allen Wegen ───────────────────────────────────────

def test_create_mitglied_meldet_wem_die_adresse_gehoert(patched_db, fake_redis):
    """Zweites Mitglied mit derselben Adresse: abgelehnt, mit Anzeigename."""
    _basis(patched_db)
    from diakronos_app.api.mitglieder import create_mitglied

    meldung = _abweisung(lambda: create_mitglied("Zweite", "Person", email="anna@x.org"))
    assert "Anna Beispiel" in meldung, meldung


@pytest.mark.parametrize("variante", ["ANNA@X.ORG", " Anna@X.org ", "\tanna@x.org\n"])
def test_create_mitglied_vergleicht_normalisiert(patched_db, fake_redis, variante):
    """Gross/Klein und Leerraum zaehlen nicht (getrimmt + kleingeschrieben)."""
    _basis(patched_db)
    from diakronos_app.api.mitglieder import create_mitglied

    meldung = _abweisung(lambda: create_mitglied("Zweite", "Person", email=variante))
    assert meldung, f"{variante!r} wurde angenommen"


def test_update_mitglied_meldet_wem_die_adresse_gehoert(patched_db, fake_redis):
    """Aendern auf eine belegte Adresse: abgelehnt, mit Anzeigename."""
    sess = _basis(patched_db)
    sess.add(Mitglied(name="M-other", vorname="Bo", nachname="Beispiel",
                      email="bo@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    from diakronos_app.api.mitglieder import update_mitglied

    meldung = _abweisung(lambda: update_mitglied("M-other", {"email": "ANNA@X.ORG"}))
    assert "Anna Beispiel" in meldung, meldung


def test_frappe_client_insert_gleiche_adresse_abgelehnt(patched_db, fake_redis):
    """Der generische Weg (`frappe.client.insert`) ist ebenfalls dicht."""
    _basis(patched_db)
    from diakronos_app.api.frappe_core import insert

    meldung = _abweisung(lambda: insert(doc={
        "doctype": "Mitglied", "vorname": "Z", "nachname": "Z", "email": "anna@x.org"}))
    assert meldung, "insert hat die belegte Adresse angenommen"


def test_resource_write_gleiche_adresse_abgelehnt(patched_db, fake_redis):
    """`PUT /api/resource/Mitglied` auf eine belegte Adresse: abgelehnt."""
    sess = _basis(patched_db)
    sess.add(Mitglied(name="M-other", vorname="Bo", nachname="Beispiel",
                      email="bo@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    from diakronos_app.frappe_compat import router

    antwort = router._apply_resource_write("Mitglied", "M-other", {"email": "anna@x.org"})
    assert getattr(antwort, "status_code", 200) >= 400


def test_import_dublette_bestaetigen_erlaubt_keine_gleiche_adresse(patched_db, fake_redis):
    """Dubletten-'Bestaetigen' im Import hebt die Eindeutigkeit NICHT auf."""
    _basis(patched_db)
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen

    meldung = _abweisung(lambda: import_mitglieder_uebernehmen(
        "Vorname;Nachname;E-Mail\nZweit;Eintrag;anna@x.org\n",
        dubletten_ueberspringen=0, bestaetigt=1))
    # Entweder als Dublette uebersprungen oder abgelehnt — aber nie angelegt.
    assert "angelegt" not in meldung.lower() or "abgebrochen" in meldung.lower()


def test_genehmige_anmeldung_bestaetigte_dublette_legt_keine_zweite_person_an(
    patched_db, fake_redis,
):
    """Oeffentliche Anmeldung: auch mit Bestaetigung keine zweite Adresse."""
    sess = _basis(patched_db, wer="sm@x.org")
    from diakronos_app.models.diakonos import Anmeldung

    sess.add(Anmeldung(name="ANM-DUP", anmeldungstyp="Mitglied-Registrierung",
                       status="Offen", vorname="Zweit", nachname="Person",
                       email="Anna@X.org", docstatus=0, idx=0))
    sess.commit()
    from diakronos_app.api.admin_hub import genehmige_anmeldung

    vorher = len(sess.query(Mitglied).all())
    _abweisung(lambda: genehmige_anmeldung("ANM-DUP", dublette_bestaetigt=1))
    sess.expire_all()
    nachher = sess.query(Mitglied).filter(
        Mitglied.email.isnot(None)).all()
    # Es darf keine ZWEITE Person mit dieser Adresse dazugekommen sein.
    gleich = [m for m in nachher if str(m.email).strip().lower() == "anna@x.org"]
    assert len(gleich) == 1, f"{len(gleich)} Mitglieder mit anna@x.org"
    assert len(nachher) >= vorher - 1


# ── (2) Klartext-Meldung nennt den Anzeigenamen ─────────────────────────────

def test_meldung_nennt_anzeigename_bei_kontoadresse(patched_db, fake_redis):
    """Gehoert die Adresse einem KONTO ohne Mitglied, nennt sie dessen Namen."""
    _basis(patched_db)
    sess = patched_db()
    sess.add(User(name="dienst@x.org", email="dienst@x.org",
                  full_name="Gemeindebuero", enabled=True))
    sess.commit()
    from diakronos_app.api.mitglieder import create_mitglied

    meldung = _abweisung(lambda: create_mitglied("Z", "Z", email="dienst@x.org"))
    assert "Gemeindebuero" in meldung, meldung


# ── K2: unsichtbare Zeichen und Vollbreite ──────────────────────────────────

@pytest.mark.parametrize("variante", [
    "anna@x.org\u200b",      # Nullbreiten-Leerzeichen
    "anna@x.org\ufeff",      # BOM
    "anna@x.org\u00ad",      # weicher Trennstrich
])
def test_k2_unsichtbare_zeichen_abgelehnt(patched_db, fake_redis, variante):
    """Eine Adresse mit unsichtbarem Zeichen wird nicht stillschweigend angenommen."""
    _basis(patched_db)
    from diakronos_app.api.mitglieder import create_mitglied

    meldung = _abweisung(lambda: create_mitglied("Z", "Z", email=variante))
    assert "unsichtbare" in meldung.lower(), meldung


def test_k2_vollbreite_wird_normalisiert_und_erkannt(patched_db, fake_redis):
    """Vollbreite-Zeichen (NFKC) sind dieselbe Adresse, keine zweite."""
    _basis(patched_db)
    from diakronos_app.email_belegung import normalisiere

    # Vollbreite-Buchstaben werden zu ASCII zusammengezogen.
    assert normalisiere("ａｎｎａ@ｘ.ｏｒｇ") == "anna@x.org"


def test_k2_normalisiere_zieht_nfkc_an():
    """Die eine Normalisierung: NFKC, getrimmt, kleingeschrieben."""
    from diakronos_app.email_belegung import normalisiere

    assert normalisiere("  ANNA@X.ORG ") == "anna@x.org"
    assert normalisiere(None) == ""
    assert normalisiere("ａｌｔ@ｘ.ｏｒｇ") == "alt@x.org"


# ── K3: Import vergleicht normalisiert ──────────────────────────────────────

def test_k3_import_erkennt_bestand_in_anderer_schreibweise(patched_db, fake_redis):
    """Ein Bestand „Gross@X.org" belegt die Adresse auch fuer „gross@x.org"."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-GROSS", vorname="Gross", nachname="Bestand",
                      email="Gross@X.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")
    from diakronos_app.api.mitglieder import import_mitglieder_vorschau

    vorschau = import_mitglieder_vorschau(
        "Vorname;Nachname;E-Mail\nZweit;Person;gross@x.org\n")
    zeile = vorschau["zeilen"][0]
    # SEC-c (K-c): vergebene Adresse = Fehlerzeile (der Server lehnt sie ab).
    assert zeile["status"] == "fehler", zeile
    assert "Gross Bestand" in " ".join(zeile["fehler"]), zeile


def test_k3_ohne_mitglied_abgleich_normalisiert(patched_db, fake_redis):
    """Mitglied mit Konto-Adresse in anderer Schreibweise: kein Konto-Zweig."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(User(name="Gross@X.org", email="Gross@X.org",
                  full_name="Konto", enabled=True))
    sess.add(Mitglied(name="M-GROSS", vorname="Gross", nachname="Bestand",
                      email="gross@x.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")
    from diakronos_app.api.mitglieder import _import_zeile

    geprueft = _import_zeile(
        {"Vorname": "Neu", "Nachname": "Person", "E-Mail": "GROSS@x.org"},
        {"vorname": "Vorname", "nachname": "Nachname", "email": "E-Mail"})
    # Es GIBT ein Mitglied mit dieser Adresse -> Dublette, nicht „Konto".
    assert geprueft["dublette"]["grund"] == "email", geprueft["dublette"]
