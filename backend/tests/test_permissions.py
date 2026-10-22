"""P3 — Testmatrix der Hierarchie-Permissions.

180 Faelle = 9 Benutzertypen x 5 DocTypes x 4 Aktionen, als parametrisierte
Tabelle (nicht als 180 Funktionen). Erwartungswerte stammen aus der
Rollen-/DocType-Matrix der Karte P3 — jede Zeile nennt eine Fundstelle im
Altcode.

Zusaetzlich in diesem Modul (siehe unten):
  * die Kartensperre "mindestens diese Faelle MUESSEN verweigern"
  * die Hilfsfunktionen aus `_permissions.py` (Verantwortlichkeit, Entwurf)
  * `_paths_overlap`-Randfaelle
  * die Patch-Hebel fuer den Negativtest (`PATCH_HEBEL`)
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import permissions as P
from diakronos_app.frappe_compat.exceptions import DoesNotExistError, PermissionError

# ── Fixture-Baum ────────────────────────────────────────────────────────────
#
#   DB-A  "/|/DB-A/"                 DB-B  "/|/DB-B/"
#    G-A1   "/G-A1/|/DB-A/"          G-B1   "/G-B1/|/DB-B/"
#     UG-A1 "/UG-A1/G-A1/|/DB-A/"    UG-B1  "/UG-B1/G-B1/|/DB-B/"
#
# Mitglieder:
#   M-gruppe-a1      in G-A1
#   M-untergruppe-a1 in UG-A1
#   M-verantw-a      Verantwortlicher DB-A + G-A1, selbst in G-A1/UG-A1
#   M-eigen-b        eigenes Mitglied von mitglied-b (DB-B)
#   M-gruppe-b1      fremdes Mitglied in DB-A — Ziel der Verweigerungs-Faelle
#
# Benutzer:
#   admin@example.org      System Manager
#   mitarbadmin@example.org Mitgliederadministrator
#   bereichsverantw@...    in Dienstbereich Verantwortlicher (DB-A  ) — OHNE Mitglied
#   gruppenverantw@...     in Gruppe Verantwortlicher       (G-A1  ) — OHNE Mitglied
#   mitglied-a@example.org Mitglied in G-A1
#   mitglied-b@example.org Mitglied in G-B1 (eigener Datensatz: M-eigen-b)
#   ohne-mitglied@...      User ohne Mitglied-Datensatz
#   (Administrator / Guest: keine DB-Zeilen)

ANFORDERUNGSSTELLER = [
    "Administrator",
    "admin@example.org",
    "mitarbadmin@example.org",
    "bereichsverantw@example.org",
    "gruppenverantw@example.org",
    "mitglied-a@example.org",
    "mitglied-b@example.org",
    "ohne-mitglied@example.org",
    "Guest",
]

#: (Beschreibung, User, DocType, docname, Aktion) -> (erwartet, erwarteter reason)
#: DocTypes mit ancestor_path; Ziel jeweils in DB-A.
PATH_ZIELE = {
    "Gruppe": "G-A1",
    "Untergruppe": "UG-A1",
    "Dienstbereich": "DB-A",
}

# Ziel fuer die Mitglied-Faelle.
MITGLIED_ZIEL = "M-gruppe-b1"     # fremdes Mitglied (DB-B)
MITGLIED_ZIEL_EIGEN = "M-gruppe-a1"
UNBEKANNTER_DOCTYPE = "Unbekannt"


def _faelle():
    """Baut die 180 Faelle (9 x 5 x 4) als parametrisierte Tabelle."""
    matrix = []

    for user in ANFORDERUNGSSTELLER:
        for aktion in ("read", "write", "create", "delete"):
            # 1) DocType Mitglied -> fremdes Mitglied
            matrix.append((user, "Mitglied", MITGLIED_ZIEL, aktion))
            # 2)..4) Gruppe / Untergruppe / Dienstbereich (Ziel in DB-A)
            for doctype, docname in PATH_ZIELE.items():
                matrix.append((user, doctype, docname, aktion))
            # 5) unbekannter DocType
            matrix.append((user, UNBEKANNTER_DOCTYPE, "irgendwas", aktion))

    return matrix


FAELLE = _faelle()


# ── Erwartungswerte aus der Spezifikation (§3) ──────────────────────────────
#
# Struktur: {user: {doctype: (allowed_read, reason_read, allowed_write, reason_write)}}
# write/create/delete verhalten sich im Altcode jeweils gleich (session.py:164
# bildet write/create/delete auf denselben Map-Schluessel ab).
ERWARTUNG = {
    "Administrator": {
        # Rolle "Administrator" ist NICHT in ADMIN_ROLES (nur die Funktion
        # is_admin() kennt die Sonderbehandlung). Spec §2.1 / §3.1 M1.
        "Mitglied": (False, "no_access", False, "no_access"),
        "Gruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Untergruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Dienstbereich": (False, "no_mitglied", False, "no_mitglied"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "admin@example.org": {          # System Manager
        "Mitglied": (True, "admin_role", True, "admin_role"),
        "Gruppe": (True, "admin_role", True, "admin_role"),
        "Untergruppe": (True, "admin_role", True, "admin_role"),
        "Dienstbereich": (True, "admin_role", True, "admin_role"),
        # Admin-Kurzschluss steht VOR der DocType-Weiche (session.py:157-159)
        "Unbekannt": (True, "admin_role", True, "admin_role"),
    },
    "mitarbadmin@example.org": {    # Mitgliederadministrator
        "Mitglied": (True, "admin_role", True, "admin_role"),
        "Gruppe": (True, "admin_role", True, "admin_role"),
        "Untergruppe": (True, "admin_role", True, "admin_role"),
        "Dienstbereich": (True, "admin_role", True, "admin_role"),
        "Unbekannt": (True, "admin_role", True, "admin_role"),
    },
    "bereichsverantw@example.org": {   # OHNE Mitglied-Datensatz
        "Mitglied": (False, "no_access", False, "no_access"),
        "Gruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Untergruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Dienstbereich": (False, "no_mitglied", False, "no_mitglied"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "gruppenverantw@example.org": {    # OHNE Mitglied-Datensatz
        "Mitglied": (False, "no_access", False, "no_access"),
        "Gruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Untergruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Dienstbereich": (False, "no_mitglied", False, "no_mitglied"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "mitglied-a@example.org": {     # Mitglied in G-A1, Ziel M-gruppe-b1 (fremd)
        "Mitglied": (False, "no_overlap", False, "no_overlap"),
        "Gruppe": (True, "ancestor_path", False, "no_overlap"),
        "Untergruppe": (True, "ancestor_path", False, "no_overlap"),
        "Dienstbereich": (True, "ancestor_path", False, "no_overlap"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "mitglied-b@example.org": {     # Mitglied in G-B1, Ziel in DB-A -> fremd
        "Mitglied": (False, "no_overlap", False, "no_overlap"),
        "Gruppe": (False, "no_overlap", False, "no_overlap"),
        "Untergruppe": (False, "no_overlap", False, "no_overlap"),
        "Dienstbereich": (False, "no_overlap", False, "no_overlap"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "ohne-mitglied@example.org": {  # kein Mitglied-Datensatz, kein E-Mail-Match
        "Mitglied": (False, "no_access", False, "no_access"),
        "Gruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Untergruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Dienstbereich": (False, "no_mitglied", False, "no_mitglied"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
    "Guest": {
        # Guest hat keine Rollen und ist mitgliedslos -> alles verweigert.
        "Mitglied": (False, "no_access", False, "no_access"),
        "Gruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Untergruppe": (False, "no_mitglied", False, "no_mitglied"),
        "Dienstbereich": (False, "no_mitglied", False, "no_mitglied"),
        "Unbekannt": (False, "unsupported_doctype", False, "unsupported_doctype"),
    },
}


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def hierarchie(patched_db):
    """Legt die komplette Hierarchie + Benutzer in der Test-DB an."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        DienstbereichVerantwortlicher,
        Gruppe,
        GruppeVerantwortlicher,
        Mitglied,
        Untergruppe,
    )

    sess = patched_db()

    # ── Dienstbereiche ──
    # ACHTUNG: `Dienstbereich.verantwortliche` ist `viewonly=True` (models/
    # diakonos.py:406-411) — Kind-Zeilen muessen EXPLIZIT eingefuegt werden,
    # sonst bleiben sie still ungespeichert und jede Verantwortlichkeits-
    # Pruefung schlaegt fehl.
    verw_bereich = DienstbereichVerantwortlicher(
        name="DVB-1", parent="DB-A", parenttype="Dienstbereich",
        parentfield="verantwortliche", user="bereichsverantw@example.org",
        docstatus=0, idx=1,
    )
    sess.add_all([
        Dienstbereich(name="DB-A", ancestor_path="/|/DB-A/", docstatus=0, idx=0),
        Dienstbereich(name="DB-B", ancestor_path="/|/DB-B/", docstatus=0, idx=0),
        # DB-C ist die isolierte Fremd-Welt: kein User hat hier eine Gruppe.
        Dienstbereich(name="DB-C", ancestor_path="/|/DB-C/", docstatus=0, idx=0),
        verw_bereich,
    ])
    sess.flush()

    # ── Gruppen + Untergruppen ──
    verw_gruppe = GruppeVerantwortlicher(
        name="GRV-1", parent="G-A1", parenttype="Gruppe",
        parentfield="verantwortliche", user="gruppenverantw@example.org",
        docstatus=0, idx=1,
    )
    sess.add_all([
        Gruppe(name="G-A1", dienstbereich="DB-A", ancestor_path="/G-A1/|/DB-A/",
               docstatus=0, idx=0),
        Gruppe(name="G-B1", dienstbereich="DB-B", ancestor_path="/G-B1/|/DB-B/",
               docstatus=0, idx=0),
        Untergruppe(name="UG-A1", gruppe="G-A1", ancestor_path="/UG-A1/G-A1/|/DB-A/",
                    docstatus=0, idx=0),
        Untergruppe(name="UG-B1", gruppe="G-B1", ancestor_path="/UG-B1/G-B1/|/DB-B/",
                    docstatus=0, idx=0),
        verw_gruppe,
    ])
    sess.flush()

    # ── Benutzer + Rollen ──
    sess.add_all([
        User(name="admin@example.org", email="admin@example.org",
             full_name="Admin", enabled=True),
        User(name="mitarbadmin@example.org", email="mitarbadmin@example.org",
             full_name="Mitarbadmin", enabled=True),
        User(name="bereichsverantw@example.org", email="bereichsverantw@example.org",
             full_name="Bereichsverantw", enabled=True),
        User(name="gruppenverantw@example.org", email="gruppenverantw@example.org",
             full_name="Gruppenverantw", enabled=True),
        User(name="mitglied-a@example.org", email="mitglied-a@example.org",
             full_name="Mitglied A", enabled=True),
        User(name="mitglied-b@example.org", email="mitglied-b@example.org",
             full_name="Mitglied B", enabled=True),
        User(name="ohne-mitglied@example.org", email="ohne-mitglied@example.org",
             full_name="Ohne Mitglied", enabled=True),
    ])
    sess.add_all([
        HasRole(name="HR-1", parent="admin@example.org",
                parenttype="User", parentfield="roles", role="System Manager",
                docstatus=0, idx=1),
        HasRole(name="HR-2", parent="mitarbadmin@example.org",
                parenttype="User", parentfield="roles",
                role="Mitgliederadministrator", docstatus=0, idx=1),
        # Mitglieder haben bewusst KEINE Rolle -> die Rechte kommen allein
        # aus ancestor_path (so ist der Altcode gedacht).
    ])

    # ── Mitglieder ──
    sess.add_all([
        Mitglied(name="M-gruppe-a1", vorname="Greta", nachname="A",
                 email="mitglied-a@example.org", status="Mitglied",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        Mitglied(name="M-untergruppe-a1", vorname="Ulrike", nachname="A",
                 email="untergruppe-a@example.org", status="Mitglied",
                 ancestor_path="/UG-A1/G-A1/|/DB-A/", docstatus=0, idx=0),
        Mitglied(name="M-verantw-a", vorname="Vera", nachname="A",
                 email="verantw-a@example.org", status="Mitglied",
                 ancestor_path="/G-A1/UG-A1/|/DB-A/", docstatus=0, idx=0),
        # Eigenes Mitglied von mitglied-b (DB-B).
        Mitglied(name="M-eigen-b", vorname="Berta", nachname="B",
                 email="mitglied-b@example.org", status="Mitglied",
                 ancestor_path="/G-B1/|/DB-B/", docstatus=0, idx=0),
        # Fremdes Mitglied in DB-C (isolierte Fremd-Welt) — Ziel der
        # Verweigerungs-Faelle.
        Mitglied(name="M-gruppe-b1", vorname="Bruno", nachname="Fremd",
                 email="fremd-b@example.org", status="Mitglied",
                 ancestor_path="/G-C1/|/DB-C/", docstatus=0, idx=0),
    ])
    sess.commit()

    yield sess

    sess.close()


@pytest.fixture(autouse=True)
def _reset_session_user():
    """Setzt den Session-Benutzer nach jedem Test zurueck."""
    from diakronos_app.frappe_compat.session import set_user

    yield
    set_user("Administrator")


# ── 180-Faelle-Matrix ───────────────────────────────────────────────────────


def _erwartung(user: str, doctype: str, aktion: str):
    read_allowed, read_reason, write_allowed, write_reason = ERWARTUNG[user][doctype]
    if aktion == "read":
        return read_allowed, read_reason
    return write_allowed, write_reason


@pytest.mark.parametrize(
    "user,doctype,docname,aktion",
    FAELLE,
    ids=[f"{u}|{d}|{a}" for u, d, _, a in FAELLE],
)
def test_matrix(hierarchie, user, doctype, docname, aktion):
    """Ein Tabelleneintrag der 180er-Matrix gegen die Spec."""
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)
    result = P.check_permission(doctype, docname, aktion)

    exp_allowed, exp_reason = _erwartung(user, doctype, aktion)
    assert result["allowed"] is exp_allowed, (
        f"{user} | {doctype} | {aktion}: allowed={result['allowed']}, "
        f"erwartet {exp_allowed} (Spec §3)"
    )
    assert result["reason"] == exp_reason, (
        f"{user} | {doctype} | {aktion}: reason={result['reason']!r}, "
        f"erwartet {exp_reason!r} (Spec §3)"
    )


def test_matrix_hat_180_faelle():
    """Die Matrix ist vollstaendig: 9 Benutzertypen x 5 DocTypes x 4 Aktionen."""
    assert len(ANFORDERUNGSSTELLER) == 9
    assert len(PATH_ZIELE) + 2 == 5  # Mitglied + 3 Pfad-DocTypes + Unbekannt
    assert len(FAELLE) == 180, f"Matrix hat {len(FAELLE)} Faelle statt 180"


# ── Kartensperre: diese Faelle MUESSEN verweigern ───────────────────────────
#
# Wird als eigene parametrisierte Liste gefuehrt, damit der Negativtest
# (siehe unten) zeigt, dass genau diese Zeilen rot werden.

MUSS_VERWEIGERN = [
    # (Beschreibung, User, DocType, docname, Aktion, erwarteter reason)
    ("Mitglied liest Mitglied aus FREMDEM Dienstbereich",
     "mitglied-b@example.org", "Mitglied", MITGLIED_ZIEL, "read", "no_overlap"),
    ("Mitglied(FREMDE Gruppe) liest Gruppe in DB-A",
     "mitglied-b@example.org", "Gruppe", "G-A1", "read", "no_overlap"),
    ("Mitglied schreibt Gruppe (die EIGENE!)",
     "mitglied-a@example.org", "Gruppe", "G-A1", "write", "no_overlap"),
    ("Mitglied schreibt Untergruppe (die eigene)",
     "mitglied-a@example.org", "Untergruppe", "UG-A1", "write", "no_overlap"),
    ("Mitglied schreibt Dienstbereich (den eigenen)",
     "mitglied-a@example.org", "Dienstbereich", "DB-A", "write", "no_overlap"),
    ("Mitglied loescht Gruppe (die eigene)",
     "mitglied-a@example.org", "Gruppe", "G-A1", "delete", "no_overlap"),
    ("Benutzer ohne Mitglied-Datensatz liest Gruppe",
     "ohne-mitglied@example.org", "Gruppe", "G-A1", "read", "no_mitglied"),
    ("Benutzer ohne Mitglied-Datensatz liest Untergruppe",
     "ohne-mitglied@example.org", "Untergruppe", "UG-A1", "read", "no_mitglied"),
    ("Benutzer ohne Mitglied-Datensatz liest Dienstbereich",
     "ohne-mitglied@example.org", "Dienstbereich", "DB-A", "read", "no_mitglied"),
    ("Guest liest Mitglied",
     "Guest", "Mitglied", MITGLIED_ZIEL, "read", "no_access"),
    ("Guest liest Gruppe",
     "Guest", "Gruppe", "G-A1", "read", "no_mitglied"),
    ("Guest liest Untergruppe",
     "Guest", "Untergruppe", "UG-A1", "read", "no_mitglied"),
    ("Guest liest Dienstbereich",
     "Guest", "Dienstbereich", "DB-A", "read", "no_mitglied"),
    ("Guest schreibt Gruppe",
     "Guest", "Gruppe", "G-A1", "write", "no_mitglied"),
    ("unbekannter DocType (Nicht-Admin)",
     "mitglied-a@example.org", UNBEKANNTER_DOCTYPE, "x", "read", "unsupported_doctype"),
    ("unbekannter DocType (Guest)",
     "Guest", UNBEKANNTER_DOCTYPE, "x", "read", "unsupported_doctype"),
]


@pytest.mark.parametrize(
    "beschreibung,user,doctype,docname,aktion,reason",
    MUSS_VERWEIGERN,
    ids=[f"{i:02d}-{b}" for i, (b, *_) in enumerate(MUSS_VERWEIGERN)],
)
def test_muss_verweigern(hierarchie, beschreibung, user, doctype, docname, aktion, reason):
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)
    result = P.check_permission(doctype, docname, aktion)
    assert result["allowed"] is False, f"ERLAUBT, muss verweigern: {beschreibung}"
    assert result["reason"] == reason, f"{beschreibung}: reason={result['reason']!r}"


# ── Rollenaufloesung ────────────────────────────────────────────────────────


def test_get_roles_liest_aus_has_role(hierarchie):
    assert P.get_roles("admin@example.org") == ("System Manager",)
    assert P.get_roles("mitarbadmin@example.org") == ("Mitgliederadministrator",)


def test_get_roles_ohne_zeilen_ist_leer(hierarchie):
    """Keine Rollen ermittelbar -> KEIN Admin-Annehmen (Kartensperre)."""
    assert P.get_roles("mitglied-a@example.org") == ()
    assert P.get_roles("ohne-mitglied@example.org") == ()
    assert P.get_roles("nie-gesehen@example.org") == ()
    assert P.get_roles("") == ()
    assert P.get_roles(None) == ()


def test_guest_hat_nie_rollen(hierarchie):
    """Guest wird an der Wurzel abgeschnitten — auch wenn Zeilen existieren."""
    assert P.get_roles("Guest") == ()
    assert P.is_guest("Guest") is True
    assert P.is_guest("admin@example.org") is False


def test_is_admin_kennt_administrator_sonderfall(hierarchie):
    """Spec §2.1: `is_admin()` hat die "Administrator"-Sonderbehandlung."""
    assert P.is_admin("Administrator") is True
    assert P.is_admin("admin@example.org") is True
    assert P.is_admin("mitarbadmin@example.org") is True
    assert P.is_admin("mitglied-a@example.org") is False
    assert P.is_admin("Guest") is False
    assert P.is_admin("ohne-mitglied@example.org") is False


def test_check_permission_kennt_administrator_sonderfall_NICHT(hierarchie):
    """Spec §2.1 (Abweichung): check_permission prueft nur Rollen.

    Genau der Fall, der im Altcode zwischen `_permissions.is_admin()` und
    `session.check_permission()` auseinanderlaeuft.
    """
    from diakronos_app.frappe_compat.session import set_user

    set_user("Administrator")
    assert P.check_permission("Gruppe", "G-A1", "read") == {
        "allowed": False, "reason": "no_mitglied",
    }


def test_require_admin(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    for user in ("admin@example.org", "mitarbadmin@example.org"):
        set_user(user)
        P.require_admin()  # darf nicht werfen

    for user in ("mitglied-a@example.org", "without@example.org"):
        set_user(user)
        with pytest.raises(PermissionError) as err:
            P.require_admin()
        assert "Nur für Mitgliederadministratoren." in str(err.value)

    set_user("Guest")
    with pytest.raises(PermissionError) as err:
        P.require_admin()
    assert "Zugriff verweigert." in str(err.value)


# ── _paths_overlap: Randfaelle ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "user_path,target_path,erwartet",
    [
        # Spec §1.2 — exakt aus session.py:227-246
        ("/G-A1/|/DB-A/", "/G-A1/|/DB-B/", True),      # Gruppe gemeinsam
        ("/G-A1/|/DB-A/", "/G-B1/|/DB-A/", True),      # Bereich gemeinsam
        ("/G-A1/|/DB-A/", "/G-B1/|/DB-B/", False),     # nichts gemeinsam
        ("/UG-A1/G-A1/|/DB-A/", "/G-A1/|/DB-B/", True),
        ("", "/G-A1/|/DB-A/", False),                  # leerer Nutzerpfad
        ("/G-A1/|/DB-A/", "", False),                  # leerer Zielpfad
        (None, None, False),
        ("|", "|", False),
        ("|", "/G-A1/|/DB-A/", False),
        # Gruppen und Bereiche sind getrennte Mengen: "G-A1" als Bereich
        # trifft nicht "G-A1" als Gruppe.
        ("/|/G-A1/", "/G-A1/|/DB-A/", False),
        # Gegenprobe: steht derselbe Name in beiden Mengen, ueberlappt er
        # ueber die Bereichs-Seite (session.py:246 ist ein Mengen-Schnitt).
        ("/DB-A/|/DB-A/", "/|/DB-A/", True),
        ("/DB-A/|/DB-B/", "/|/DB-A/", False),
    ],
)
def test_paths_overlap(user_path, target_path, erwartet):
    assert P._paths_overlap(user_path, target_path) is erwartet


# ── mitglied_permissions: die Map im Detail ─────────────────────────────────


def test_mitglied_permissions_admin(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    perms = P.mitglied_permissions(MITGLIED_ZIEL)
    assert perms == {
        "can_view": True, "can_edit": True, "can_delete": False,
        "can_view_sensitive": True, "reason": "admin_role",
    }


def test_mitglied_permissions_can_delete_ist_auch_fuer_admin_false(hierarchie):
    """session.py:107 — Loeschen laeuft nie ueber diese Map."""
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    assert P.mitglied_permissions(MITGLIED_ZIEL)["can_delete"] is False
    set_user("mitglied-a@example.org")
    assert P.mitglied_permissions(MITGLIED_ZIEL_EIGEN)["can_delete"] is False


def test_mitglied_permissions_can_view_sensitive_ist_admin_only(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    for user in ("mitglied-a@example.org", "mitglied-b@example.org",
                 "ohne-mitglied@example.org", "Guest"):
        set_user(user)
        assert P.mitglied_permissions(MITGLIED_ZIEL)["can_view_sensitive"] is False


def test_mitglied_permissions_eigenes_profil_ist_editierbar(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("mitglied-a@example.org")
    perms = P.mitglied_permissions(MITGLIED_ZIEL_EIGEN)
    assert perms["can_view"] is True
    assert perms["can_edit"] is True
    assert perms["reason"] == "ancestor_path"


def test_mitglied_permissions_fremdes_mitglied_nicht_editierbar(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("mitglied-a@example.org")
    perms = P.mitglied_permissions(MITGLIED_ZIEL)
    assert perms["can_view"] is False and perms["can_edit"] is False
    assert perms["reason"] == "no_overlap"


def test_mitglied_permissions_email_fallback_ohne_mitglied(hierarchie):
    """session.py:112-122 — E-Mail-Fallback fuer User ohne Mitglied-Datensatz.

    Die Suche laeuft ueber `User.email or session.user`
    (session.py:184-192). Ist der Benutzername zufaellig gleich der
    Mitglied-E-Mail, greift die Suche immer — der "self"-Zweig ist dann
    unerreichbar. Genau das bilden wir hier ab: `session.user` ist die
    E-Mail, also findet die Suche den Datensatz und der Pfad laeuft ueber
    "ancestor_path"/Overlap. Der Zustand "kein current_mitglied" ist bei
    dieser Referenzlogik nur mit einer Benutzername != E-Mail erreichbar.
    """
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.diakonos import Mitglied

    sess = hierarchie
    sess.add(Mitglied(name="M-nur-email", vorname="Nur", nachname="Email",
                      email="ohne-mitglied@example.org", status="Mitglied",
                      ancestor_path="/G-B1/|/DB-B/", docstatus=0, idx=0))
    sess.commit()

    set_user("ohne-mitglied@example.org")
    # Benutzername == E-Mail -> Suche findet den Datensatz.
    assert P._get_current_user_mitglied()["name"] == "M-nur-email"
    perms = P.mitglied_permissions("M-nur-email")
    assert perms["can_view"] is True
    assert perms["can_edit"] is True          # eigenes Profil
    assert perms["reason"] == "ancestor_path"  # nicht "self"
    assert perms["can_view_sensitive"] is False


def test_mitglied_permissions_ziel_existiert_nicht(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    with pytest.raises(DoesNotExistError):
        P.mitglied_permissions("M-gibt-es-nicht")


def test_require_mitglied_view_und_edit(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("mitglied-a@example.org")
    # Fremdes Mitglied (DB-C): weder lesbar noch editierbar.
    with pytest.raises(PermissionError):
        P.require_mitglied_view(MITGLIED_ZIEL)
    # Eigenes Profil: lesbar UND editierbar (session.py:129-136).
    assert P.require_mitglied_view(MITGLIED_ZIEL_EIGEN)["can_view"] is True
    assert P.require_mitglied_edit(MITGLIED_ZIEL_EIGEN)["can_edit"] is True
    # Loeschen ist laut Referenz IMMER verweigert.
    assert P.require_mitglied_view(MITGLIED_ZIEL_EIGEN)["can_delete"] is False

    set_user("admin@example.org")
    assert P.require_mitglied_view(MITGLIED_ZIEL)["can_view"] is True
    assert P.require_mitglied_edit(MITGLIED_ZIEL)["can_edit"] is True


# ── Verantwortlichkeit / Bereichszugriff / Entwurf ──────────────────────────


def test_ist_verantwortlich_fuer(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("bereichsverantw@example.org")
    assert P.ist_verantwortlich_fuer("DB-A", None) is True
    assert P.ist_verantwortlich_fuer(None, "G-A1") is False   # nur Bereich
    assert P.ist_verantwortlich_fuer("DB-B", None) is False

    set_user("gruppenverantw@example.org")
    assert P.ist_verantwortlich_fuer(None, "G-A1") is True
    assert P.ist_verantwortlich_fuer("DB-A", None) is False   # nur Gruppe
    assert P.ist_verantwortlich_fuer(None, "G-B1") is False

    set_user("mitglied-a@example.org")
    assert P.ist_verantwortlich_fuer("DB-A", "G-A1") is False


def test_ist_verantwortlich_fuer_leere_argumente_werfen_nicht(hierarchie):
    """_permissions.py:43 — leere Argumente werden UEBERSPRUNGEN, kein Fehler."""
    from diakronos_app.frappe_compat.session import set_user

    for user in ("bereichsverantw@example.org", "mitglied-a@example.org", "Guest"):
        set_user(user)
        assert P.ist_verantwortlich_fuer(None, None) is False
        assert P.ist_verantwortlich_fuer("", "") is False


def test_verantwortlichkeit_haengt_nicht_am_ancestor_path(hierarchie):
    """Wer einen Bereich verantwortet, ist dort oft in keiner Gruppe."""
    from diakronos_app.frappe_compat.session import set_user

    set_user("bereichsverantw@example.org")
    # Hat keinen Mitglied-Datensatz -> kein Overlap-Pfad, aber Verantwortlicher
    assert P._get_current_user_mitglied() is None
    assert P.ist_verantwortlich_fuer("DB-A", None) is True
    assert P.has_bereichs_zugriff("DB-A") is True


def test_has_bereichs_zugriff(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("admin@example.org")
    assert P.has_bereichs_zugriff("DB-A") is True

    set_user("bereichsverantw@example.org")
    assert P.has_bereichs_zugriff("DB-A") is True

    set_user("mitglied-a@example.org")          # ueber ancestor_path
    assert P.has_bereichs_zugriff("DB-A") is True
    assert P.has_bereichs_zugriff("DB-B") is False

    set_user("mitglied-b@example.org")
    assert P.has_bereichs_zugriff("DB-A") is False
    assert P.has_bereichs_zugriff("DB-B") is True

    set_user("Guest")
    assert P.has_bereichs_zugriff("DB-A") is False


def test_has_bereichs_zugriff_ohne_bereich_ist_verweigert(hierarchie):
    """Spec §2.4 — Abweichung: der unbelegte has_permission-Fallback -> False."""
    from diakronos_app.frappe_compat.session import set_user

    set_user("mitglied-a@example.org")
    assert P.has_bereichs_zugriff(None) is False
    assert P.has_bereichs_zugriff("") is False


def test_darf_entwurf_sehen(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    # Ersteller sieht seinen Entwurf
    set_user("mitglied-a@example.org")
    assert P.darf_entwurf_sehen("mitglied-a@example.org", "DB-A", "G-A1") is True
    # ... aber nicht den eines anderen
    assert P.darf_entwurf_sehen("jemand@example.org", "DB-A", "G-A1") is False
    assert P.darf_entwurf_sehen("jemand@example.org", "DB-B", "G-B1") is False

    # Verantwortliche sehen Entwuerfe ihres Bereichs / ihrer Gruppe
    set_user("bereichsverantw@example.org")
    assert P.darf_entwurf_sehen("x@example.org", "DB-A", None) is True
    assert P.darf_entwurf_sehen("x@example.org", "DB-B", None) is False

    set_user("gruppenverantw@example.org")
    assert P.darf_entwurf_sehen("x@example.org", None, "G-A1") is True
    assert P.darf_entwurf_sehen("x@example.org", None, "G-B1") is False

    # "Administrator" sieht alles (session.py:_permissions.py:101-102)
    set_user("Administrator")
    assert P.darf_entwurf_sehen("x@example.org", None, None) is True

    # Admin-ROLLE ohne den Literal-Namen sieht nur ueber Verantwortlichkeit:
    # is_admin() wird im Original nicht ausgewertet (toter Code, Spec §2.5).
    set_user("admin@example.org")
    assert P.darf_entwurf_sehen("x@example.org", None, None) is False
    assert P.darf_entwurf_sehen("x@example.org", "DB-A", None) is False


def test_darf_entwurf_sehen_owner_leer(hierarchie):
    from diakronos_app.frappe_compat.session import set_user

    set_user("mitglied-a@example.org")
    assert P.darf_entwurf_sehen(None, "DB-B", "G-B1") is False
    assert P.darf_entwurf_sehen("", "DB-B", "G-B1") is False


# ── Negativtest-Hebel ───────────────────────────────────────────────────────
#
# Fuer den in der Karte geforderten Negativtest ("dreh eine Regel testhalber
# um, zeig dass die Matrix rot wird, nimm es zurueck") sind hier zwei Hebel
# benannt, damit der Nachweis mit EINEM Befehl reproduzierbar ist:
#
#   PERM_PATCH=read_gate  -> entfernt die permission_type=="read"-Einschraenkung
#   PERM_PATCH=no_mitglied -> erlaubt Nutzern ohne Mitglied-Datensatz read
#
# Die Patches wirken nur, wenn die Umgebungsvariable gesetzt ist; im
# Normalbetrieb (und in CI) ist sie nicht gesetzt und es aendert sich nichts.

PATCH_HEBEL = ("read_gate", "no_mitglied")


@pytest.fixture()
def patch_hebel(monkeypatch):
    """Aktiviert den per PERM_PATCH gewaehlten Hebel (nur fuer den Negativtest).

    Die Hebel drehen je EINE verbindliche Regel um:
      * ``read_gate``  — entfernt ``permission_type == "read"`` bei den drei
        Pfad-DocTypes. Dadurch darf ein Mitglied seine eigene Gruppe schreiben.
      * ``no_mitglied`` — laesst Nutzer ohne Mitglied-Datensatz bei den drei
        Pfad-DocTypes lesen, statt zu verweigern.
    """
    import os

    hebel = os.environ.get("PERM_PATCH")
    if not hebel:
        pytest.skip("PERM_PATCH nicht gesetzt — Negativtest-Hebel inaktiv")
    if hebel not in PATCH_HEBEL:
        pytest.skip(f"unbekannter Hebel {hebel!r}")

    echte_check = P.check_permission

    if hebel == "read_gate":
        def check_ohne_read_gate(doctype, docname, permission_type="read"):
            user = P.session.user
            if P._has_admin_role(user):
                return {"allowed": True, "reason": "admin_role"}
            if doctype == "Mitglied":
                perms = P.mitglied_permissions(docname)
                key = ("can_edit" if permission_type in ("write", "create", "delete")
                       else "can_view")
                return {"allowed": bool(perms.get(key, False)),
                        "reason": perms.get("reason")}
            if doctype in P._PATH_DOCTYPES:
                current = P._get_current_user_mitglied()
                if not current:
                    return {"allowed": False, "reason": "no_mitglied"}
                user_path = current.get("ancestor_path") or "|"
                _ziel = P.get_value(doctype, docname, "ancestor_path")
                target_path = _ziel if isinstance(_ziel, str) else "|"
                # MUTATION: die read-Einschraenkung fehlt absichtlich.
                allowed = P._paths_overlap(user_path, target_path)
                return {"allowed": allowed,
                        "reason": "ancestor_path" if allowed else "no_overlap"}
            return {"allowed": False, "reason": "unsupported_doctype"}

        monkeypatch.setattr(P, "check_permission", check_ohne_read_gate)
        yield hebel
    else:
        # MUTATION: kein Mitglied-Datensatz -> trotzdem lesen erlauben.
        def check_ohne_mitglied(doctype, docname, permission_type="read"):
            user = P.session.user
            if P._has_admin_role(user):
                return {"allowed": True, "reason": "admin_role"}
            if doctype == "Mitglied":
                perms = P.mitglied_permissions(docname)
                key = ("can_edit" if permission_type in ("write", "create", "delete")
                       else "can_view")
                return {"allowed": bool(perms.get(key, False)),
                        "reason": perms.get("reason")}
            if doctype in P._PATH_DOCTYPES:
                return {"allowed": True, "reason": "ancestor_path"}
            return {"allowed": False, "reason": "unsupported_doctype"}

        monkeypatch.setattr(P, "check_permission", check_ohne_mitglied)
        yield hebel

    monkeypatch.setattr(P, "check_permission", echte_check)


def test_negativtest_hebel_ist_wirksam(hierarchie, patch_hebel):
    """Beweist, dass der Hebel die verbotene Regel TATSAECHLICH umdreht.

    Ohne Hebel ist dieser Test ein Skip. Mit ``PERM_PATCH=read_gate`` muss
    ``check_permission("Gruppe", "G-A1", "write")`` fuer ein einfaches Mitglied
    auf ``True`` kippen — genau der Mutationsfall "Mitglied schreibt die
    eigene Gruppe", der laut Karte scheitern MUSS.

    Mit ``PERM_PATCH=no_mitglied`` muss der Read fuer einen Nutzer ohne
    Mitglied-Datensatz auf ``True`` kippen.
    """
    from diakronos_app.frappe_compat.session import set_user

    if patch_hebel == "read_gate":
        set_user("mitglied-a@example.org")
        result = P.check_permission("Gruppe", "G-A1", "write")
        assert result["allowed"] is True, (
            "Der Hebel haette 'Mitglied schreibt eigene Gruppe' erlauben "
            "muessen — die Mutation wirkt nicht, der Negativtest taugt nichts."
        )
    else:
        set_user("ohne-mitglied@example.org")
        result = P.check_permission("Gruppe", "G-A1", "read")
        assert result["allowed"] is True, (
            "Der Hebel haette den Read ohne Mitglied-Datensatz erlauben "
            "muessen — die Mutation wirkt nicht."
        )


# Die eigentliche Matrix unter dem Hebel: jeder dieser Faelle MUSS rot werden.
MAXIMUM_FAELLE = [
    # (User, DocType, docname, Aktion) — laut Karte zwingend zu verweigern.
    ("mitglied-a@example.org", "Gruppe", "G-A1", "write"),
    ("mitglied-a@example.org", "Untergruppe", "UG-A1", "write"),
    ("mitglied-a@example.org", "Dienstbereich", "DB-A", "write"),
    ("mitglied-a@example.org", "Gruppe", "G-A1", "delete"),
    ("mitglied-b@example.org", "Mitglied", MITGLIED_ZIEL, "read"),
    ("mitglied-b@example.org", "Gruppe", "G-A1", "read"),
    ("ohne-mitglied@example.org", "Gruppe", "G-A1", "read"),
    ("Guest", "Gruppe", "G-A1", "read"),
    ("Guest", "Mitglied", MITGLIED_ZIEL, "read"),
]


@pytest.mark.parametrize(
    "user,doctype,docname,aktion", MAXIMUM_FAELLE,
    ids=lambda v: str(v).replace("@example.org", "").replace("/", "-"),
)
def test_negativtest_muss_rot_werden(hierarchie, patch_hebel, user, doctype, docname, aktion):
    """Die verbotenen Faelle MUESSEN unter dem Hebel scheitern.

    Dies ist der Beweis, dass die Matrix diese Faelle wirklich prueft: waeren
    die Faelle nicht in der Matrix, bliebe dieser Test gruen.
    """
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)
    result = P.check_permission(doctype, docname, aktion)
    assert result["allowed"] is True, (
        f"{user} darf {aktion} auf {doctype}/{docname} NICHT erlauben, "
        f"aber der Hebel sagt: {result}"
    )
