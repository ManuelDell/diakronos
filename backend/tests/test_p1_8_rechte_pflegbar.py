"""P1-8 — Ausgeschlossene Mitglieder haben keine Mitgliederrechte mehr.

DER BEFUND (Nachtrag R-P1-9b, Operator 16.10.)
----------------------------------------------
`schliesse_mitglied_aus` (`api/mitglieder.py`) setzt am MITGLIED
`ausgeschlossen=1` und den Status auf „Passiver Gast“. Das Login-Konto
(`user.enabled`) bleibt unberuehrt — und **nirgends** im Code wurde
`ausgeschlossen` bei einer Rechtepruefung ausgewertet. Eine ausgeschlossene
Person konnte sich also weiter anmelden und behielt Rollen und Sichtbarkeit.

Was hier festgenagelt wird:

  1. **Rollen** (`frappe_compat/permissions.py::get_roles`): ein
     ausgeschlossenes Mitglied bekommt `()`. Weil `is_admin`,
     `check_permission` und `has_role` alle ueber `get_roles` laufen, wirkt
     die Regel damit in JEDER Rollenpruefung an einer Stelle.
  2. **Login/Sitzung** (`frappe_compat/benutzer_status.py`): `ist_aktiv`
     und `konto_ist_aktiv` melden `False` — der Weg ueber das
     Sitzungs-Cookie UND der Weg ueber das Login-Formular sehen dieselbe
     Regel.
  3. **Plan-Rahmen** (`planrahmen/rechte.py::Rechte.angemeldet`): auch die
     eigene Rechtsschicht des Plan-Rahmens verweigert.
  4. **Gegenrichtung**: ein aehnliches, NICHT ausgeschlossenes Mitglied
     behaelt alles; der Administrator ohne Mitglied-Datensatz ist nie
     betroffen.

Jeder Test hier waere **ohne** den Fix rot.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import diakronos_app.api.profile  # noqa: F401  (registriert die whitelists)
from diakronos_app import frappe_compat
from diakronos_app.frappe_compat import benutzer_status, permissions, sitzungen
from diakronos_app.frappe_compat.passwoerter import neuer_hash
from diakronos_app.main import app
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

# Der Fixture-Baum der Permissions-Matrix (Dienstbereich DB-A, Gruppe G-A1,
# Untergruppe UG-A1, `bereichsverantw@`, `gruppenverantw@`) — dieselbe Welt,
# nur einmal definiert.
from tests.test_permissions import hierarchie  # noqa: F401  (Fixture)

PROFIL = "diakronos.diakonos.api.profile"
PROFIL_PFAD = f"/api/method/{PROFIL}"

RAUS = "raus@example.org"
DRIN = "drin@example.org"


@pytest.fixture()
def welt(patched_db):
    """Zwei Mitglieder mit Konto und der Rolle „Mitgliederadministrator“.

    Beide sind zunaechst NICHT ausgeschlossen — so laesst sich in einem Test
    die eine Seite umschalten und die andere als Kontrolle stehen lassen.
    """
    sess = patched_db()
    sess.add_all([
        User(name=RAUS, email=RAUS, full_name="Raus Rentner", enabled=True,
             password_hash=neuer_hash("Geheim-1")),
        User(name=DRIN, email=DRIN, full_name="Drin Dauerhaft", enabled=True,
             password_hash=neuer_hash("Geheim-2")),
        Mitglied(name="M-raus", vorname="Raus", nachname="Rentner",
                 email=RAUS, status="Mitglied", user=RAUS,
                 ausgeschlossen=False, docstatus=0, idx=0),
        Mitglied(name="M-drin", vorname="Drin", nachname="Dauerhaft",
                 email=DRIN, status="Mitglied", user=DRIN,
                 ausgeschlossen=False, docstatus=0, idx=0),
        HasRole(name="HR-raus", parent=RAUS, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator",
                docstatus=0, idx=1),
        HasRole(name="HR-drin", parent=DRIN, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator",
                docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


def _ausschliessen(sess, mitglied: str) -> None:
    from diakronos_app.models.diakonos import Mitglied as M

    sess.expire_all()
    sess.get(M, mitglied).ausgeschlossen = True
    sess.commit()
    # Der Status-Cache ist die dokumentierte Frist; fuer die Messung der
    # Regel selbst wird er geleert (wie in test_b1_sitzungswiderruf).
    try:
        for schluessel in benutzer_status._client().scan_iter(
            match=f"{benutzer_status.STATUS_PRAEFIX}*"
        ):
            benutzer_status._client().delete(schluessel)
    except Exception:  # noqa: BLE001 — Cache ist Optimierung
        pass


# ── 1. Rollen ───────────────────────────────────────────────────────────────


def test_ausgeschlossenes_mitglied_hat_keine_rollen(welt) -> None:
    assert permissions.get_roles(RAUS) == ("Mitgliederadministrator",), "Ausgangslage"
    _ausschliessen(welt, "M-raus")
    assert permissions.get_roles(RAUS) == ()


def test_ausgeschlossenes_mitglied_ist_kein_admin(welt) -> None:
    assert permissions.is_admin(RAUS) is True, "Ausgangslage"
    _ausschliessen(welt, "M-raus")
    assert permissions.is_admin(RAUS) is False


def test_nicht_ausgeschlossenes_mitglied_behaelt_rollen(welt) -> None:
    """Gegenrichtung: ein anderer Benutzer bleibt unberuehrt."""
    _ausschliessen(welt, "M-raus")
    assert permissions.get_roles(DRIN) == ("Mitgliederadministrator",)
    assert permissions.is_admin(DRIN) is True


def test_benutzer_ohne_mitglied_ist_nie_ausgeschlossen(patched_db) -> None:
    """Der erste Administrator hat kein Mitglied — die Regel greift nicht."""
    sess = patched_db()
    sess.add(User(name="chef@example.org", email="chef@example.org",
                  full_name="Chefin", enabled=True))
    sess.add(HasRole(name="HR-chef", parent="chef@example.org", parenttype="User",
                     parentfield="roles", role="System Manager", docstatus=0, idx=1))
    sess.commit()
    assert permissions.get_roles("chef@example.org") == ("System Manager",)
    assert permissions.mitglied_ausgeschlossen("chef@example.org") is False


# ── 2. Login / Sitzung ──────────────────────────────────────────────────────


def test_ist_aktiv_meldet_ausgeschlossenes_mitglied_als_inaktiv(welt, fake_redis) -> None:
    assert benutzer_status.ist_aktiv(RAUS) is True, "Ausgangslage"
    _ausschliessen(welt, "M-raus")
    assert benutzer_status.ist_aktiv(RAUS) is False


def test_konto_ist_aktiv_meldet_ausgeschlossenes_mitglied_als_inaktiv(welt) -> None:
    doc = welt.get(User, RAUS)
    assert benutzer_status.konto_ist_aktiv(doc) is True, "Ausgangslage"
    _ausschliessen(welt, "M-raus")
    welt.expire_all()
    assert benutzer_status.konto_ist_aktiv(welt.get(User, RAUS)) is False


def test_ausgeschlossener_benutzer_verliert_seine_sitzung(welt, fake_redis) -> None:
    """Der Weg ueber das Sitzungs-Cookie (SessionMiddleware)."""
    sid, csrf = sitzungen.anlegen(RAUS)
    c = TestClient(app)
    c.cookies.set("sid", sid)
    c.headers["X-Frappe-CSRF-Token"] = csrf
    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 200, "Ausgangslage"

    _ausschliessen(welt, "M-raus")

    antwort = c.post(f"{PROFIL_PFAD}.get_my_profile")
    assert antwort.status_code == 401
    assert antwort.json()["exc_type"] == "SessionExpired"
    c.close()


# ── 3. Plan-Rahmen ──────────────────────────────────────────────────────────


def test_planrahmen_rechte_verweigert_ausgeschlossenem(welt, fake_redis) -> None:
    """Auch die eigene Rechtsschicht des Plan-Rahmens verweigert."""
    from diakronos_app.frappe_compat.exceptions import PermissionError as PErr
    from diakronos_app.planrahmen.rechte import Rechte

    sess = welt
    Rechte(sess, RAUS).angemeldet()  # Ausgangslage: kein Fehler

    _ausschliessen(sess, "M-raus")

    with pytest.raises(PErr):
        Rechte(sess, RAUS).angemeldet()


# ── 4. Verantwortliche pflegbar (OP-CHOR-3 / OP-ADMIN-4) ────────────────────
#
# Der Fixture-Baum der Permissions-Matrix (tests/test_permissions.py) hat
# genau die Objekte, die es braucht: Dienstbereich DB-A, Gruppe G-A1 (in DB-A)
# und Untergruppe UG-A1 (in G-A1). `bereichsverantw@` verantwortet DB-A,
# `gruppenverantw@` die Gruppe G-A1 — beide OHNE eigenes Mitglied.
#
# Ziel: ein Konto zur Planerin machen (Gruppenverantwortung eintragen), die
# Rechte des Plan-Rahmens greifen danach serverseitig — nicht nur in der
# Anzeige.


def _neues_mitglied_mit_konto(sess, name: str, email: str) -> None:
    sess.add_all([
        User(name=email, email=email, full_name=name, enabled=True),
        Mitglied(name=name, vorname=name.split()[0], nachname=name.split()[-1],
                 email=email, status="Mitglied", user=email, docstatus=0, idx=0),
    ])
    sess.commit()


def _planerin_rolle(sess, user: str, gruppe: str) -> bool:
    """Greift die Gruppenverantwortung serverseitig (planrahmen/rechte.py)?"""
    from diakronos_app.planrahmen.rechte import Rechte

    return Rechte(sess, user).gruppen_verantwortlich({gruppe})


def test_verantwortliche_lesen_liefert_anzeigenamen(hierarchie) -> None:
    from diakronos_app.api.verantwortliche import get_verantwortliche

    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    daten = get_verantwortliche("Gruppe", "G-A1")
    assert daten["darf_pflegen"] is True
    assert [v["user"] for v in daten["verantwortliche"]] == ["gruppenverantw@example.org"]


def test_verantwortliche_setzen_macht_zur_planerin(hierarchie) -> None:
    """Der Kern von OP-CHOR-3: Konto eintragen -> die Person ist Planerin."""
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.session import set_user

    _neues_mitglied_mit_konto(hierarchie, "Ruth Chorleiter", "ruth@example.org")
    set_user("admin@example.org")

    assert _planerin_rolle(hierarchie, "ruth@example.org", "G-A1") is False, "Ausgangslage"

    set_verantwortliche("Gruppe", "G-A1",
                        ["gruppenverantw@example.org", "ruth@example.org"])

    hierarchie.expire_all()
    assert _planerin_rolle(hierarchie, "ruth@example.org", "G-A1") is True


def test_verantwortliche_entziehen_wirkt(hierarchie) -> None:
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    assert _planerin_rolle(hierarchie, "gruppenverantw@example.org", "G-A1") is True
    set_verantwortliche("Gruppe", "G-A1", [])
    hierarchie.expire_all()
    assert _planerin_rolle(hierarchie, "gruppenverantw@example.org", "G-A1") is False


def test_verantwortliche_bereich_ueber_gruppe(hierarchie) -> None:
    """Wer den Dienstbereich verantwortet, darf dessen Gruppen pflegen."""
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.session import set_user

    set_user("bereichsverantw@example.org")
    daten = set_verantwortliche("Gruppe", "G-A1", ["bereichsverantw@example.org"])
    assert daten["success"] is True


def test_verantwortliche_fremde_gruppe_verweigert(hierarchie) -> None:
    """Ein Gruppenverantwortlicher darf KEINE fremde Gruppe pflegen."""
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.exceptions import PermissionError as PErr
    from diakronos_app.frappe_compat.session import set_user

    set_user("gruppenverantw@example.org")
    with pytest.raises(PErr):
        set_verantwortliche("Gruppe", "G-B1", ["gruppenverantw@example.org"])


def test_verantwortliche_ohne_konto_verweigert(hierarchie) -> None:
    """„Nur Personen mit Konto" ist serverseitig durchgesetzt (OP-CHOR-3)."""
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    with pytest.raises(ValidationError, match="Benutzerkonto"):
        set_verantwortliche("Gruppe", "G-A1", ["gibt-es-nicht@example.org"])


def test_verantwortliche_untergruppe_und_dienstbereich(hierarchie) -> None:
    """Alle drei Ebenen sind pflegbar — nicht nur die Gruppe."""
    from diakronos_app.api.verantwortliche import set_verantwortliche
    from diakronos_app.frappe_compat.query import get_all
    from diakronos_app.frappe_compat.session import set_user

    _neues_mitglied_mit_konto(hierarchie, "Lea Leiterin", "lea@example.org")
    set_user("admin@example.org")

    set_verantwortliche("Untergruppe", "UG-A1", ["lea@example.org"])
    set_verantwortliche("Dienstbereich", "DB-B", ["lea@example.org"])

    hierarchie.expire_all()
    assert get_all("Untergruppe Verantwortlicher",
                   filters={"parent": "UG-A1", "user": "lea@example.org"})
    assert get_all("Dienstbereich Verantwortlicher",
                   filters={"parent": "DB-B", "user": "lea@example.org"})


def test_verantwortliche_auswahl_nur_personen_mit_konto(hierarchie) -> None:
    """Die Auswahl bietet nur Personen MIT Konto an (OP-CHOR-3).

    Ein Mitglied ohne Login kann ein Recht nicht ausueben; es darf deshalb
    nicht in der Auswahl stehen — sonst verspraeche die Oberflaeche eine
    Verantwortung, die nie wirkt.
    """
    from diakronos_app.api.verantwortliche import get_verantwortliche_auswahl
    from diakronos_app.frappe_compat.session import set_user

    sess = hierarchie
    # Ein Mitglied OHNE Konto.
    sess.add(Mitglied(name="M-ohne-konto", vorname="Ohne", nachname="Konto",
                      email="ohne@example.org", status="Mitglied",
                      user=None, docstatus=0, idx=0))
    sess.commit()
    # Ein Mitglied MIT Konto.
    _neues_mitglied_mit_konto(sess, "Mit Konto", "mit@example.org")

    set_user("admin@example.org")
    daten = get_verantwortliche_auswahl("Gruppe", "G-A1", "")
    konten = {a["user"] for a in daten["auswahl"]}
    assert "mit@example.org" in konten
    assert "ohne@example.org" not in konten
    # Die Auswahl baut auf MITGLIEDERN mit Konto auf; `gruppenverantw@` hat im
    # Fixture keinen Mitglied-Datensatz und ist daher nicht waehlbar (dieselbe
    # Regel, die `get_verantwortliche` beim Setzen durchsetzt).
    assert "gruppenverantw@example.org" not in konten
    # Suche filtert serverseitig.
    gefiltert = get_verantwortliche_auswahl("Gruppe", "G-A1", "Mit")
    assert {a["user"] for a in gefiltert["auswahl"]} == {"mit@example.org"}
