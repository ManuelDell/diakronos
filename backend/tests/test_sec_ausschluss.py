"""SEC-Ausschluss — Rechte-Luecke aus dem Opus-Review (W1/W2).

Die Proben stammen aus dem Review zu N11 und sind hier mit der SICHEREN
Erwartung uebernommen. Sie waren gegen main ROT:

  * W1 (P4, V1, V2) — `_pruefe_mitglied_schreibzugriff` prueft nur neu
    GESPERRTE Konten. Ein ausgeschlossenes Konto mit Verwaltungsrolle wurde
    ueber drei Wege wieder aktiv, ohne dass ein System Manager am Werk war:

      V1  `frappe_core.insert` eines Mitglieds mit derselben E-Mail machte die
          Adresse mehrdeutig, `wirksame_konten` loeste sie nicht mehr auf —
          der Ausschluss fiel weg, das SM-Konto war wieder aktiv.
      V2  `_update_doc("Mitglied", ..., {"ausgeschlossen": 0})` hob den
          Ausschluss direkt auf.
      P4  der Import (Dublette, bestaetigt) ist derselbe Weg wie V1.

  * W2 (P8) — die Dublettenpruefung des Imports verglich die E-Mail EXAKT.
    Im Bestand „Gross@X.org“, im Import „gross@x.org“ — die Zeile galt als
    neu, entstand als zweite Person, die Adresse wurde mehrdeutig und ein
    Ausschluss ueber die E-Mail wirkte nicht mehr.

Beide Befunde haengen zusammen: eine mehrdeutige Adresse setzt den Ausschluss
aus. Deshalb prueft jede Probe BEIDES — die Verweigerung (bzw. das
Dubletten-Ergebnis) UND dass das Verwaltungskonto danach noch gesperrt ist.
Ohne die Aenderungen in `frappe_compat/api_helpers.py` und
`api/mitglieder.py` waere diese Datei rot.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"


def _konto(
    sess,
    email: str,
    rolle: str | None = None,
    *,
    mitglied: bool = True,
    link: bool = True,
    ausgeschlossen: bool = False,
) -> None:
    """Konto anlegen; `link=False` verbindet das Mitglied NUR ueber die E-Mail.

    `mitglied=False` legt NUR das Konto an (der Fall „erster Administrator“).
    """
    sess.add(User(name=email, email=email, full_name=email, enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                          email=email, status="Mitglied",
                          user=email if link else None,
                          ausgeschlossen=1 if ausgeschlossen else 0,
                          docstatus=0, idx=0))
    sess.commit()


def _aktiv(user: str) -> bool:
    """Frische Messung des Kontozustands (Cache vergessen)."""
    from diakronos_app.frappe_compat import benutzer_status

    benutzer_status.vergiss(user)
    return benutzer_status.ist_aktiv(user)


def _rollen(user: str) -> set[str]:
    """Die Rollen EINES KONTOS (nicht des Aufrufers) — wie `zugang._rollen_von`."""
    from diakronos_app.api.zugang import _rollen_von

    return _rollen_von(user)


def _zustand(patched_db) -> None:
    """Ein Mitgliederadministrator, ein aktiver SM, ein ausgeschlossener SM.

    Der ausgeschlossene `alt@x.org` haengt NUR ueber die E-Mail an seinem
    Mitglied (kein `user`-Link) — genau die Lage aus der Probe P4.
    """
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "alt@x.org", SM, link=False, ausgeschlossen=True)
    assert _aktiv("alt@x.org") is False, "Vorbedingung: alt@x.org ist gesperrt"
    set_user("ma@x.org")


def _import(csv_text: str, **kw):
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen

    return import_mitglieder_uebernehmen(csv_text, **kw)


# ── W1: Entsperren ist dem System Manager vorbehalten ──────────────────────


def test_w1_v1_insert_gleiche_email_macht_verwaltungskonto_nicht_wieder_aktiv(
    patched_db, fake_redis
):
    """V1: Mitglied mit der E-Mail eines gesperrten SM anlegen (insert)."""
    _zustand(patched_db)
    from diakronos_app.api.frappe_core import insert

    with pytest.raises(FrappePermissionError):
        insert(doc={"doctype": "Mitglied", "vorname": "Zweit", "nachname": "Eintrag",
                    "email": "alt@x.org"})

    assert _aktiv("alt@x.org") is False, "gesperrtes Verwaltungskonto wurde wieder aktiv"
    assert SM in _rollen("alt@x.org")


def test_w1_v2_ausschluss_aufheben_nur_system_manager(patched_db, fake_redis):
    """V2: `ausgeschlossen=0` am Mitglied eines gesperrten SM."""
    _zustand(patched_db)
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-alt@x.org", {"ausgeschlossen": 0})

    assert _aktiv("alt@x.org") is False, "Ausschluss wurde aufgehoben"
    assert SM in _rollen("alt@x.org")


def test_w1_p4_import_dublette_holt_gesperrtes_verwaltungskonto_nicht_zurueck(
    patched_db, fake_redis
):
    """P4: Import mit der E-Mail eines gesperrten SM (Dublette, bestaetigt).

    Erwartung: der Import wird abgelehnt — durch die Rechte-Schranke
    (`PermissionError`) ODER mit Klartext (`ValidationError`, K4). Entscheidend
    ist die Wirkung: das Verwaltungskonto bleibt gesperrt.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _zustand(patched_db)
    text = "Vorname;Nachname;E-Mail\nZweit;Eintrag;alt@x.org\n"

    with pytest.raises((FrappePermissionError, ValidationError)) as fehler:
        _import(text, dubletten_ueberspringen=0, bestaetigt=1)
    assert "System Manager" in str(fehler.value), "Grund fehlt in der Meldung (K4)"

    assert _aktiv("alt@x.org") is False, "Import hat das Verwaltungskonto freigegeben"
    assert SM in _rollen("alt@x.org")


def test_w1_system_manager_darf_freigeben(patched_db, fake_redis):
    """Gegenprobe: mit der Rolle System Manager bleibt derselbe Weg offen."""
    _zustand(patched_db)
    set_user("sm@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    _update_doc("Mitglied", "M-alt@x.org", {"ausgeschlossen": 0})

    assert _aktiv("alt@x.org") is True


def test_w1_eigene_zeile_ohne_verwaltungsrolle_bleibt_frei(patched_db, fake_redis):
    """Falsch-Positiv-Schutz: normale Mitglieder pflegt der Admin weiterhin."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "normal@x.org", ausgeschlossen=True, link=False)
    set_user("ma@x.org")
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    _update_doc("Mitglied", "M-normal@x.org", {"ausgeschlossen": 0})

    assert _aktiv("normal@x.org") is True


# ── W2: E-Mail-Vergleich getrimmt + case-insensitiv ────────────────────────


def test_w2_import_dublette_erkennt_gross_klein(patched_db, fake_redis):
    """P8: Bestand „Gross@X.org“, Import „gross@x.org“ ist eine Dublette.

    SEC-c (K-c, Befund): eine vergebene ADRESSE meldet die Vorschau
    als FEHLERZEILE — die Oberflaeche sagt „der Server lehnt Zeilen ab“, und
    beim Uebernehmen ist die Zeile abgelehnt statt „uebersprungen“.
    """
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-CASE", vorname="Gross", nachname="Klein",
                      email="Gross@X.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import import_mitglieder_vorschau

    vorschau = import_mitglieder_vorschau("Vorname;Nachname;E-Mail\nAnders;Name;gross@x.org\n")
    assert vorschau["zeilen"][0]["status"] == "fehler"
    assert "Gross Klein" in " ".join(vorschau["zeilen"][0]["fehler"])

    # Auch mit Leerraum in der Zelle.
    vorschau = import_mitglieder_vorschau("Vorname;Nachname;E-Mail\nAnders;Name; Gross@X.org \n")
    assert vorschau["zeilen"][0]["status"] == "fehler"


def test_w2_import_dublette_erkennt_konto_ohne_mitglied(patched_db, fake_redis):
    """W2 weiter gedacht: die Adresse eines KONTOS ohne Mitglied.

    Ein Konto OHNE Rolle ist kein Rechte-Risiko: die Zeile wird angelegt, aber
    mit Hinweis als Dublette markiert (K4 — kein stiller Zustand). Die Pruefung
    steht hier als Regressionstest fuer diesen Rand.
    """
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "kontakt@x.org", None, mitglied=False)
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import _import_zeile

    geprueft = _import_zeile(
        {"Vorname": "Neu", "Nachname": "Person", "E-Mail": "kontakt@x.org"},
        {"vorname": "Vorname", "nachname": "Nachname", "email": "E-Mail"},
    )
    assert not geprueft["fehler"]
    assert geprueft["dublette"]["grund"] == "konto"
    assert geprueft["dublette"]["vorhanden"] == "kontakt@x.org"


def test_w1_import_mit_konto_adresse_eines_verwaltungskontos(patched_db, fake_redis):
    """W1: Adresse eines Verwaltungskontos ohne Mitglied — kein Anlegen per Import.

    Frueher galt die Zeile als „neu“ und wurde angelegt; die Schranke verweigerte
    erst danach (P3, K4). Jetzt steht der Grund in der Zeile selbst.
    """
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM, mitglied=False)
    _konto(sess, "sm2@x.org", SM)
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import import_mitglieder_vorschau

    vorschau = import_mitglieder_vorschau("Vorname;Nachname;E-Mail\nNeu;Person;sm@x.org\n")
    zeile = vorschau["zeilen"][0]
    assert zeile["status"] == "fehler"
    assert any("System Manager" in f for f in zeile["fehler"])


def test_w2_create_mitglied_lehnt_andere_schreibweise_ab(patched_db, fake_redis):
    """create_mitglied: dieselbe Adresse in anderer Schreibweise ist vergeben."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-CASE", vorname="Gross", nachname="Klein",
                      email="Gross@X.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import create_mitglied
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        create_mitglied("Anders", "Name", email="gross@x.org")


def test_w2_update_mitglied_lehnt_andere_schreibweise_ab(patched_db, fake_redis):
    """update_mitglied: die Adresse eines ANDEREN Mitglieds in anderer Schreibweise."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-A", vorname="Anna", nachname="A", email="anna@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.add(Mitglied(name="M-B", vorname="Bruno", nachname="B", email="bruno@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import update_mitglied
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        update_mitglied("M-B", data={"email": "ANNA@X.org"})


def test_w2_eigene_schreibweise_bleibt_erlaubt(patched_db, fake_redis):
    """Falsch-Positiv-Schutz: die unveraenderte eigene Adresse bleibt durch."""
    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    sess.add(Mitglied(name="M-A", vorname="Anna", nachname="A", email="anna@x.org",
                      status="Mitglied", docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    from diakronos_app.api.mitglieder import update_mitglied

    # Vollformular der SPA: alle Felder inkl. unveraenderter E-Mail.
    update_mitglied("M-A", data={"vorname": "Anna", "nachname": "A",
                                 "email": "anna@x.org"})
