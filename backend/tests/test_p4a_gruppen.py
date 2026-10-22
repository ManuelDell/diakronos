"""P4a — Portierte Gruppen-/Orgchart-Endpunkte (`api.gruppen`, `api.orgchart_api`).

Prueft die 19 portierten Endpunkte gegen dieselbe Hierarchie-Fixture wie
`test_permissions.py` (P3): dieselbe Datenlage, dieselbe Rollenquelle —
so ist die Permissions-Schicht aus P3 die *eine* Wahrheit, nicht eine
zweite Implementierung.

Abgedeckt:
  * Login-Pflicht jedes Endpunkts (`allow_guest=False` im Router).
  * `get_gruppen_hierarchie`: Baum, Mitgliederzahl, Archiviert-Filter,
    Sichtbarkeitsfilter fuer Nicht-Admins.
  * `get_gruppe_detail` / `get_untergruppe_detail`: Detailfelder + die
    Verweigerung fuer Fremde (Pflichtfall aus der Karte).
  * Mitgliedschafts-Schreibpfade (`add`/`remove`/`update_mitglied_rolle`)
    inklusive doppelt-Add und der 0-Zeilen-Loeschung.
  * Aufgaben/Ankuendigungen: Anlegen + Toggle.
  * `get_gruppen_for_orgchart`: Knoten/Elternkanten.
  * `orgchart_api.get_orgchart_data`: Root/Join/Leiter/Mitgliederzahlen.
  * `get_user_create_permissions`: Admin vs. Verantwortlicher.
"""

from __future__ import annotations

from datetime import date

import pytest

from diakronos_app.frappe_compat import permissions as P
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import (
    Dienstbereich,
    DienstbereichVerantwortlicher,
    Gruppe,
    GruppeVerantwortlicher,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)

# ── Fixture: dieselbe Hierarchie wie die P3-Matrix ──────────────────────────
#
#   DB-A  "/|/DB-A/"                 DB-B  "/|/DB-B/"        DB-C  "/|/DB-C/"
#    G-A1   "/G-A1/|/DB-A/"          G-B1   "/G-B1/|/DB-B/"
#     UG-A1 "/UG-A1/G-A1/|/DB-A/"    UG-B1  "/UG-B1/G-B1/|/DB-B/"
#
# User:
#   admin@example.org       System Manager
#   mitarbadmin@example.org Mitgliederadministrator
#   bereichsverantw@...     Verantwortlicher DB-A (ohne Mitglied)
#   gruppenverantw@...      Verantwortlicher G-A1 (ohne Mitglied)
#   mitglied-a@example.org  Mitglied in G-A1 (M-gruppe-a1)
#   mitglied-b@example.org  Mitglied in G-B1 (M-eigen-b, eigene Welt)
#   ohne-mitglied@...       User ohne Mitglied-Datensatz
#   Guest                   ohne alles


@pytest.fixture()
def hierarchie(patched_db):
    sess = patched_db()

    verw_bereich = DienstbereichVerantwortlicher(
        name="DVB-1", parent="DB-A", parenttype="Dienstbereich",
        parentfield="verantwortliche", user="bereichsverantw@example.org",
        docstatus=0, idx=1,
    )
    verw_gruppe = GruppeVerantwortlicher(
        name="GRV-1", parent="G-A1", parenttype="Gruppe",
        parentfield="verantwortliche", user="gruppenverantw@example.org",
        docstatus=0, idx=1,
    )
    sess.add_all([
        Dienstbereich(name="DB-A", ministry="Gottesdienst", ancestor_path="/|/DB-A/",
                      docstatus=0, idx=0),
        Dienstbereich(name="DB-B", ministry="Jugend", ancestor_path="/|/DB-B/",
                      docstatus=0, idx=0),
        Dienstbereich(name="DB-C", ministry="Musik", ancestor_path="/|/DB-C/",
                      docstatus=0, idx=0),
        verw_bereich,
    ])
    sess.flush()
    sess.add_all([
        Gruppe(name="G-A1", gruppenname="Kleingruppe Nord", dienstbereich="DB-A",
               status="Aktiv", sichtbarkeit="Öffentlich", ancestor_path="/G-A1/|/DB-A/",
               docstatus=0, idx=0),
        Gruppe(name="G-B1", gruppenname="Kleingruppe Süd", dienstbereich="DB-B",
               status="Aktiv", sichtbarkeit="Öffentlich", ancestor_path="/G-B1/|/DB-B/",
               docstatus=0, idx=0),
        # Archiviert: darf in keiner Liste auftauchen.
        Gruppe(name="G-ARCH", gruppenname="Alte Gruppe", dienstbereich="DB-A",
               status="Archiviert", sichtbarkeit="Öffentlich",
               ancestor_path="/G-ARCH/|/DB-A/", docstatus=0, idx=0),
        # Versteckt: nur fuer Admins sichtbar.
        Gruppe(name="G-HIDE", gruppenname="Geheime Gruppe", dienstbereich="DB-A",
               status="Aktiv", sichtbarkeit="Versteckt",
               ancestor_path="/G-HIDE/|/DB-A/", docstatus=0, idx=0),
        Untergruppe(name="UG-A1", untergruppenname="Nord-Team", gruppe="G-A1",
                    status="Aktiv", sichtbarkeit="Öffentlich",
                    ancestor_path="/UG-A1/G-A1/|/DB-A/", docstatus=0, idx=0),
        Untergruppe(name="UG-B1", untergruppenname="Süd-Team", gruppe="G-B1",
                    status="Aktiv", sichtbarkeit="Öffentlich",
                    ancestor_path="/UG-B1/G-B1/|/DB-B/", docstatus=0, idx=0),
        verw_gruppe,
    ])
    sess.flush()

    from diakronos_app.models.core import HasRole, User
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
        HasRole(name="HR-1", parent="admin@example.org", parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=1),
        HasRole(name="HR-2", parent="mitarbadmin@example.org", parenttype="User",
                parentfield="roles", role="Mitgliederadministrator",
                docstatus=0, idx=1),
    ])
    sess.add_all([
        Mitglied(name="M-gruppe-a1", vorname="Greta", nachname="A",
                 email="mitglied-a@example.org", status="Mitglied",
                 user="mitglied-a@example.org",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        Mitglied(name="M-eigen-b", vorname="Berta", nachname="B",
                 email="mitglied-b@example.org", status="Mitglied",
                 user="mitglied-b@example.org",
                 ancestor_path="/G-B1/|/DB-B/", docstatus=0, idx=0),
        Mitglied(name="M-fremd-c", vorname="Bruno", nachname="Fremd",
                 email="fremd-c@example.org", status="Mitglied",
                 ancestor_path="/|/DB-C/", docstatus=0, idx=0),
        Mitglied(name="M-neu-d", vorname="Nina", nachname="Neu",
                 email="neu-d@example.org", status="Mitglied",
                 user="neu-d@example.org",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        # Der Gruppenverantwortliche braucht laut Referenz einen Mitglieds-
        # Datensatz (create_untergruppe prueft `mitglied` UND Verantwortung).
        Mitglied(name="M-grv", vorname="Gustav", nachname="Verantw",
                 email="gruppenverantw@example.org", status="Mitglied",
                 user="gruppenverantw@example.org",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
    ])
    # Mitgliedschaft: mitglied-a in G-A1 (Aktiv), ein Zweiter in G-A1 damit
    # die Zaehlung >1 prueft, und eine Inaktive, die nicht zaehlen darf.
    sess.add_all([
        Gruppenmitgliedschaft(name="GM-1", parent="G-A1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-gruppe-a1",
                              rolle="Leiter", status="Aktiv",
                              beitrittsdatum=date(2024, 1, 1),
                              docstatus=0, idx=1),
        Gruppenmitgliedschaft(name="GM-2", parent="G-A1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-fremd-c",
                              rolle="Mitglied", status="Aktiv",
                              beitrittsdatum=date(2024, 2, 1),
                              docstatus=0, idx=2),
        Gruppenmitgliedschaft(name="GM-3", parent="G-A1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-eigen-b",
                              rolle="Mitglied", status="Inaktiv",
                              docstatus=0, idx=3),
        Untergruppenmitgliedschaft(name="UGM-1", parent="UG-A1",
                                   parenttype="Untergruppe", parentfield="mitglieder",
                                   mitglied="M-gruppe-a1", rolle="Mitglied",
                                   status="Aktiv", docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_session_user():
    yield
    set_user("Administrator")


# ── Login-Pflicht ───────────────────────────────────────────────────────────

GRUPPEN_ENDPUNKTE = [
    "get_gruppen_hierarchie",
    "get_gruppe_detail",
    "get_untergruppe_detail",
    "add_mitglied_to_gruppe",
    "remove_mitglied_from_gruppe",
    "update_mitglied_rolle",
    "get_gruppen_for_orgchart",
    "get_user_create_permissions",
    "create_dienstbereich",
    "create_gruppe",
    "create_untergruppe",
    "update_gruppe",
    "update_untergruppe",
    "get_gruppen_page_data",
    "get_aufgaben",
    "create_aufgabe",
    "toggle_aufgabe",
    "get_ankuendigungen",
    "create_ankuendigung",
]


def _options(fn):
    from diakronos_app.frappe_compat.registry import options_for

    return options_for(fn)


@pytest.mark.parametrize("name", GRUPPEN_ENDPUNKTE)
def test_gruppen_endpunkte_sind_nicht_guest(name):
    """`@frappe.whitelist(allow_guest=False)` muss am Modul haengen (Kartensperre)."""
    from diakronos_app.api import gruppen

    fn = getattr(gruppen, name)
    assert _options(fn).get("allow_guest") is False, f"{name} ist guest-erlaubt"


def test_orgchart_data_ist_nicht_guest():
    from diakronos_app.api import orgchart_api

    assert _options(orgchart_api.get_orgchart_data).get("allow_guest") is False


# ── Hierarchie ──────────────────────────────────────────────────────────────


def test_hierarchie_admin_sieht_aktive_ohne_archivierte(hierarchie):
    from diakronos_app.api.gruppen import get_gruppen_hierarchie

    set_user("admin@example.org")
    res = get_gruppen_hierarchie()

    assert res["success"] is True
    namen = {g["gruppenname"] for g in res["gruppen"]}
    assert "Kleingruppe Nord" in namen
    assert "Kleingruppe Süd" in namen
    assert "Geheime Gruppe" in namen          # Admin sieht Verstecktes
    assert "Alte Gruppe" not in namen          # Archiviert ist immer raus

    nord = next(g for g in res["gruppen"] if g["gruppenname"] == "Kleingruppe Nord")
    # GM-1 + GM-2 sind Aktiv, GM-3 ist Inaktiv -> 2, nicht 3.
    assert nord["mitglieder_count"] == 2
    assert [u["untergruppenname"] for u in nord["untergruppen"]] == ["Nord-Team"]


def test_hierarchie_nicht_admin_sieht_nur_eigene_welt(hierarchie):
    from diakronos_app.api.gruppen import get_gruppen_hierarchie

    set_user("mitglied-a@example.org")
    res = get_gruppen_hierarchie()

    namen = {g["gruppenname"] for g in res["gruppen"]}
    assert "Kleingruppe Nord" in namen     # ancestor_path ueberlappt G-A1
    assert "Kleingruppe Süd" not in namen  # DB-B, fremde Welt
    # Referenz filtert NICHT nach `sichtbarkeit` — Zugang haengt allein an der
    # ancestor_path-Ueberlappung (siehe referenz/.../api/gruppen.py:36-40).
    assert "Geheime Gruppe" in namen       # Pfad ueberlappt ebenfalls


def test_hierarchie_ohne_mitglied_sieht_nichts_ausser_admin(hierarchie):
    """User ohne Mitglied/ancestor_path: nur was der Admin-Zweig ohnehin zeigt."""
    from diakronos_app.api.gruppen import get_gruppen_hierarchie

    set_user("ohne-mitglied@example.org")
    res = get_gruppen_hierarchie()
    assert res["gruppen"] == []


# ── Detail + Verweigerung ───────────────────────────────────────────────────


def test_gruppe_detail_admin_liefert_mitglieder_und_zaehler(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_detail

    set_user("admin@example.org")
    res = get_gruppe_detail("G-A1")

    assert res["success"] is True
    assert res["gruppe"]["gruppenname"] == "Kleingruppe Nord"
    mitglied_ids = {m["mitglied"] for m in res["mitglieder"]}
    assert "M-gruppe-a1" in mitglied_ids
    assert "M-fremd-c" in mitglied_ids
    # Referenz listet ALLE Kindzeilen inkl. Inaktiver (kein Status-Filter,
    # siehe referenz/.../api/gruppen.py:117-124); `status` steht je Zeile mit drin.
    inaktiv = {m["mitglied"]: m["status"] for m in res["mitglieder"]}
    assert inaktiv["M-eigen-b"] == "Inaktiv"


def test_gruppe_detail_miglied_sieht_eigene_gruppe(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_detail

    set_user("mitglied-a@example.org")
    res = get_gruppe_detail("G-A1")
    assert res["success"] is True


def test_gruppe_detail_fremde_welt_wird_verweigert(hierarchie):
    """Pflicht-Verweigerung: DB-B/G-B1 fuer Mitglied der DB-A."""
    from diakronos_app.api.gruppen import get_gruppe_detail
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        get_gruppe_detail("G-B1")


def test_gruppe_detail_ohne_mitglied_wird_verweigert(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_detail
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("ohne-mitglied@example.org")
    with pytest.raises(PermissionError):
        get_gruppe_detail("G-A1")


def test_untergruppe_detail_verweigert_fremde_welt(hierarchie):
    from diakronos_app.api.gruppen import get_untergruppe_detail
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        get_untergruppe_detail("UG-B1")


def test_untergruppe_detail_erlaubt_eigene(hierarchie):
    from diakronos_app.api.gruppen import get_untergruppe_detail

    set_user("mitglied-a@example.org")
    res = get_untergruppe_detail("UG-A1")
    assert res["success"] is True
    assert res["untergruppe"]["untergruppenname"] == "Nord-Team"
    assert {m["mitglied"] for m in res["mitglieder"]} == {"M-gruppe-a1"}


def test_gruppe_detail_unbekannt_ist_doesnotexist(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_detail
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    set_user("admin@example.org")
    with pytest.raises(DoesNotExistError):
        get_gruppe_detail("G-GIBTS-NICHT")


# ── Mitgliedschaft schreiben ────────────────────────────────────────────────


def test_add_mitglied_legt_kindzeile_an(hierarchie):
    from diakronos_app.api.gruppen import add_mitglied_to_gruppe, get_gruppe_detail

    set_user("admin@example.org")
    res = add_mitglied_to_gruppe("G-A1", "M-neu-d", rolle="Mitglied")
    assert res["success"] is True

    detail = get_gruppe_detail("G-A1")
    assert "M-neu-d" in {m["mitglied"] for m in detail["mitglieder"]}


def test_add_mitglied_doppelt_ist_false(hierarchie):
    from diakronos_app.api.gruppen import add_mitglied_to_gruppe

    set_user("admin@example.org")
    res = add_mitglied_to_gruppe("G-A1", "M-gruppe-a1")
    assert res["success"] is False
    assert "bereits" in res["message"]


def test_add_mitglied_ohne_berechtigung_ist_verweigert(hierarchie):
    from diakronos_app.api.gruppen import add_mitglied_to_gruppe
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        add_mitglied_to_gruppe("G-B1", "M-eigen-b")


def test_remove_mitglied_loescht_kindzeile(hierarchie):
    from diakronos_app.api.gruppen import remove_mitglied_from_gruppe

    set_user("admin@example.org")
    res = remove_mitglied_from_gruppe("G-A1", "M-fremd-c")
    assert res["success"] is True

    from diakronos_app.frappe_compat.query import get_all
    rest = get_all("Gruppenmitgliedschaft",
                   filters={"parent": "G-A1", "mitglied": "M-fremd-c"})
    assert rest == []


def test_remove_nicht_vorhandenes_mitglied_ist_false(hierarchie):
    from diakronos_app.api.gruppen import remove_mitglied_from_gruppe

    set_user("admin@example.org")
    res = remove_mitglied_from_gruppe("G-A1", "M-gibts-nicht")
    assert res["success"] is False


def test_update_mitglied_rolle_schreibt(hierarchie):
    from diakronos_app.api.gruppen import update_mitglied_rolle
    from diakronos_app.frappe_compat.query import get_value

    set_user("admin@example.org")
    res = update_mitglied_rolle("G-A1", "M-gruppe-a1", "Stellvertreter")
    assert res["success"] is True
    assert get_value(
        "Gruppenmitgliedschaft",
        {"parent": "G-A1", "mitglied": "M-gruppe-a1"},
        "rolle",
    ) == "Stellvertreter"


def test_update_mitglied_rolle_unbekannt_ist_false(hierarchie):
    from diakronos_app.api.gruppen import update_mitglied_rolle

    set_user("admin@example.org")
    res = update_mitglied_rolle("G-A1", "M-gibts-nicht", "Leiter")
    assert res["success"] is False


def test_add_mitglied_untergruppe_flag(hierarchie):
    """`is_untergruppe=True` schreibt in die Untergruppen-Kindtabelle."""
    from diakronos_app.api.gruppen import add_mitglied_to_gruppe
    from diakronos_app.frappe_compat.query import get_all

    set_user("admin@example.org")
    res = add_mitglied_to_gruppe("UG-A1", "M-eigen-b", is_untergruppe=True)
    assert res["success"] is True
    assert get_all("Untergruppenmitgliedschaft",
                   filters={"parent": "UG-A1", "mitglied": "M-eigen-b"})


# ── Anlegen ─────────────────────────────────────────────────────────────────


def test_create_dienstbereich_nur_mit_rolle(hierarchie):
    from diakronos_app.api.gruppen import create_dienstbereich
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        create_dienstbereich("Neuer DB")

    set_user("admin@example.org")
    res = create_dienstbereich("Neuer DB", beschreibung="x")
    assert res["success"] is True
    assert res["name"]


# ── UXD-R28 / DES-04: Dienstbereich-Farbe wird geprueft ─────────────────────


def test_create_dienstbereich_ergaenzt_fehrendes_rautenzeichen(hierarchie):
    """Der Hinweis in der Oberflaeche nennt `3b82f6` ohne `#` — das muss gehen."""
    from diakronos_app.api.gruppen import create_dienstbereich
    from diakronos_app.frappe_compat.query import get_value

    set_user("admin@example.org")
    res = create_dienstbereich("Farb-DB", farbe="3b82f6")
    assert get_value("Dienstbereich", res["name"], "farbe") == "#3b82f6"


def test_create_dienstbereich_verwirft_ungueltige_farbe(hierarchie):
    """Klartext/Fremdwert darf nie in der Datenbank landen (sonst roh im style)."""
    from diakronos_app.api.gruppen import create_dienstbereich
    from diakronos_app.frappe_compat.query import get_value

    set_user("admin@example.org")
    res = create_dienstbereich("Schmutz-DB", farbe="zzz-keine-farbe")
    assert get_value("Dienstbereich", res["name"], "farbe") == "#667eea"

    res2 = create_dienstbereich("CSS-DB", farbe="red;background-image:url(x)")
    assert get_value("Dienstbereich", res2["name"], "farbe") == "#667eea"


def test_orgchart_knoten_farbe_ist_bereinigt(hierarchie):
    """Bestandsdaten mit unguelter Farbe kommen bereinigt aus der API (DES-04)."""
    from diakronos_app.api.gruppen import get_gruppen_for_orgchart
    from diakronos_app.frappe_compat.query import get_doc

    set_user("admin@example.org")
    db = get_doc("Dienstbereich", "DB-A")
    db.farbe = "zzz-keine-farbe"
    db.save()

    res = get_gruppen_for_orgchart()
    nodes = {n["id"]: n for n in res["nodes"]}
    assert nodes["db_DB-A"]["farbe"] == "#667eea"


def test_create_gruppe_verantwortlicher_darf(hierarchie):
    from diakronos_app.api.gruppen import create_gruppe

    set_user("bereichsverantw@example.org")
    res = create_gruppe("Neue Gruppe", "DB-A")
    assert res["success"] is True

    from diakronos_app.frappe_compat.query import get_value
    assert get_value("Gruppe", res["name"], "dienstbereich") == "DB-A"


def test_create_gruppe_fremder_dienstbereich_verweigert(hierarchie):
    from diakronos_app.api.gruppen import create_gruppe
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("bereichsverantw@example.org")
    with pytest.raises(PermissionError):
        create_gruppe("Fremd", "DB-B")


def test_create_untergruppe_braucht_gruppenverantwortung(hierarchie):
    from diakronos_app.api.gruppen import create_untergruppe
    from diakronos_app.frappe_compat.exceptions import PermissionError

    # bereichsverantw ist nicht Gruppenverantwortlicher von G-A1.
    set_user("bereichsverantw@example.org")
    with pytest.raises(PermissionError):
        create_untergruppe("Sub", "G-A1")

    set_user("gruppenverantw@example.org")
    res = create_untergruppe("Sub", "G-A1")
    assert res["success"] is True


def test_update_gruppe_verantwortlicher_schreibt(hierarchie):
    from diakronos_app.api.gruppen import update_gruppe
    from diakronos_app.frappe_compat.query import get_value

    set_user("gruppenverantw@example.org")
    res = update_gruppe("G-A1", gruppenname="Nord umbenannt")
    assert res["success"] is True
    assert get_value("Gruppe", "G-A1", "gruppenname") == "Nord umbenannt"


def test_update_gruppe_fremd_verweigert(hierarchie):
    from diakronos_app.api.gruppen import update_gruppe
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("gruppenverantw@example.org")
    with pytest.raises(PermissionError):
        update_gruppe("G-B1", gruppenname="Hack")


def test_update_untergruppe_schreibt(hierarchie):
    from diakronos_app.api.gruppen import update_untergruppe
    from diakronos_app.frappe_compat.query import get_value

    set_user("gruppenverantw@example.org")
    res = update_untergruppe("UG-A1", untergruppenname="Nord-Team neu")
    assert res["success"] is True
    assert get_value("Untergruppe", "UG-A1", "untergruppenname") == "Nord-Team neu"


# ── Seiten-/Erstellrechte ───────────────────────────────────────────────────


def test_get_user_create_permissions_admin(hierarchie):
    from diakronos_app.api.gruppen import get_user_create_permissions

    set_user("admin@example.org")
    res = get_user_create_permissions()
    assert res["can_create_dienstbereich"] is True
    assert res["can_create_gruppe"] is True
    assert res["can_create_untergruppe"] is True
    assert res["can_create_any"] is True


def test_get_user_create_permissions_verantwortliche(hierarchie):
    from diakronos_app.api.gruppen import get_user_create_permissions

    set_user("bereichsverantw@example.org")
    res = get_user_create_permissions()
    assert res["can_create_dienstbereich"] is False
    assert res["can_create_gruppe"] is True
    assert res["allowed_dienstbereiche"] == ["DB-A"]

    set_user("gruppenverantw@example.org")
    res = get_user_create_permissions()
    assert res["can_create_untergruppe"] is True
    assert res["allowed_gruppen"] == ["G-A1"]


def test_get_user_create_permissions_ohne_rollen(hierarchie):
    from diakronos_app.api.gruppen import get_user_create_permissions

    set_user("mitglied-a@example.org")
    res = get_user_create_permissions()
    assert res["can_create_any"] is False


def test_gruppen_page_data_admin_und_mitglied(hierarchie):
    from diakronos_app.api.gruppen import get_gruppen_page_data

    set_user("admin@example.org")
    res = get_gruppen_page_data()
    assert res["is_admin"] is True
    assert "meine_gruppen" in res and "gruppentypen" in res

    set_user("mitglied-a@example.org")
    res = get_gruppen_page_data()
    assert res["is_admin"] is False
    assert "Kleingruppe Nord" in {g["gruppenname"] for g in res["meine_gruppen"]}


# ── Aufgaben ────────────────────────────────────────────────────────────────


def test_aufgaben_anlegen_und_toggle(hierarchie):
    from diakronos_app.api.gruppen import create_aufgabe, get_aufgaben, toggle_aufgabe

    set_user("admin@example.org")
    res = create_aufgabe("Kaffee kaufen", gruppe_id="G-A1", faellig="2026-01-01")
    assert res["success"] is True
    name = res["name"]

    liste = get_aufgaben(gruppe_id="G-A1")
    assert {a["name"] for a in liste["data"]} == {name}

    t1 = toggle_aufgabe(name)
    assert t1["erledigt"] == 1
    t2 = toggle_aufgabe(name)
    assert t2["erledigt"] == 0


def test_aufgaben_ohne_id_ist_fehler(hierarchie):
    from diakronos_app.api.gruppen import get_aufgaben
    from diakronos_app.frappe_compat.exceptions import ValidationError

    set_user("admin@example.org")
    with pytest.raises(ValidationError):
        get_aufgaben()


# ── Ankuendigungen ──────────────────────────────────────────────────────────


def test_ankuendigung_anlegen_und_lesen(hierarchie):
    from diakronos_app.api.gruppen import create_ankuendigung, get_ankuendigungen

    set_user("admin@example.org")
    res = create_ankuendigung("Wichtig", text="Bitte lesen", gruppe_id="G-A1")
    assert res["success"] is True

    liste = get_ankuendigungen(gruppe_id="G-A1")
    assert [a["titel"] for a in liste["data"]] == ["Wichtig"]
    assert liste["data"][0]["text"] == "Bitte lesen"


def test_ankuendigung_untergruppe(hierarchie):
    from diakronos_app.api.gruppen import create_ankuendigung, get_ankuendigungen

    set_user("admin@example.org")
    res = create_ankuendigung("UG-Info", untergruppe_id="UG-A1")
    assert res["success"] is True
    liste = get_ankuendigungen(untergruppe_id="UG-A1")
    assert {a["name"] for a in liste["data"]} == {res["name"]}


# ── Orgchart (gruppen) ──────────────────────────────────────────────────────


def test_gruppen_for_orgchart_knoten_und_kanten(hierarchie):
    from diakronos_app.api.gruppen import get_gruppen_for_orgchart

    set_user("admin@example.org")
    res = get_gruppen_for_orgchart()
    nodes = {n["id"]: n for n in res["nodes"]}

    assert nodes["virtual-root"]["parentId"] is None
    assert nodes["db_DB-A"]["parentId"] == "virtual-root"
    assert nodes["g_G-A1"]["parentId"] == "db_DB-A"
    assert nodes["ug_UG-A1"]["parentId"] == "g_G-A1"
    # Archivierte Gruppe erzeugt keinen Knoten.
    assert "g_G-ARCH" not in nodes
    # Mitgliederzahl der Gruppe ist an der Knoten-Form.
    assert nodes["g_G-A1"]["mitglieder_count"] == 2


# ── Orgchart (orgchart_api) ─────────────────────────────────────────────────


def test_orgchart_data_root_und_kinder(hierarchie):
    from diakronos_app.api.orgchart_api import get_orgchart_data

    set_user("admin@example.org")
    nodes = get_orgchart_data()
    by_id = {n["id"]: n for n in nodes}

    assert by_id["__root__"]["node_type"] == "org"
    assert by_id["__root__"]["name"] == "Meine Gemeinde"  # kein Single -> Default

    assert by_id["DB-A"]["node_type"] == "dienstbereich"
    assert by_id["DB-A"]["parentId"] == "__root__"
    assert by_id["G-A1"]["parentId"] == "DB-A"
    assert by_id["G-A1"]["node_type"] == "gruppe"
    assert by_id["G-A1"]["leiter"] == "Gruppenverantw"     # aus User.full_name
    assert by_id["G-A1"]["member_count"] == 2              # nur Aktive
    assert by_id["UG-A1"]["parentId"] == "G-A1"
    assert by_id["UG-A1"]["member_count"] == 1

    mitglied_knoten = [n for n in nodes if n["node_type"] == "mitglied"]
    assert {n["id"] for n in mitglied_knoten} == {
        "m__M-gruppe-a1__G-A1",
        "m__M-fremd-c__G-A1",
        "m__M-gruppe-a1__UG-A1",
    }


def test_orgchart_data_archivierte_gruppe_fehlt(hierarchie):
    from diakronos_app.api.orgchart_api import get_orgchart_data

    set_user("admin@example.org")
    ids = {n["id"] for n in get_orgchart_data()}
    assert "G-ARCH" not in ids

# ── HTTP-Routing: beide Module sind ueber /api/method erreichbar ────────────
# Die Reinheits-Tests oben rufen die Funktionen direkt. Hier wird geprueft,
# dass die dotted paths *tatsaechlich* im Router registriert sind — genau der
# Fehler, den ein fehlendes `@whitelist` oder ein fehlender Import in
# `api/__init__.py` erzeugen wuerde.

ROUTING_PFADE = [
    "gruppen.get_gruppen_hierarchie",
    "gruppen.get_gruppe_detail",
    "gruppen.get_untergruppe_detail",
    "gruppen.add_mitglied_to_gruppe",
    "gruppen.remove_mitglied_from_gruppe",
    "gruppen.update_mitglied_rolle",
    "gruppen.get_gruppen_for_orgchart",
    "gruppen.get_user_create_permissions",
    "gruppen.create_dienstbereich",
    "gruppen.create_gruppe",
    "gruppen.create_untergruppe",
    "gruppen.update_gruppe",
    "gruppen.update_untergruppe",
    "gruppen.get_gruppen_page_data",
    "gruppen.get_aufgaben",
    "gruppen.create_aufgabe",
    "gruppen.toggle_aufgabe",
    "gruppen.get_ankuendigungen",
    "gruppen.create_ankuendigung",
    "orgchart_api.get_orgchart_data",
]


@pytest.mark.parametrize("pfad", ROUTING_PFADE)
def test_endpunkt_ist_im_router_registriert(client, pfad):
    """Unbekannte Methode -> 404, registrierte Methode -> 200/4xx (nie 404)."""
    r = client.post(f"/api/method/{pfad}", json={})
    assert r.status_code != 404, f"{pfad} ist nicht registriert: {r.text}"


def test_routing_unbekannter_pfad_ist_404(client):
    r = client.post("/api/method/gruppen.gibt_es_nicht", json={})
    assert r.status_code == 404


# ── P0-5b: die eine Farbreinigungsstelle (api/farbe.py) ─────────────────────
# P0-5 hatte die Reinigung nur im Schreibpfad und in get_gruppen_for_orgchart.
# Der "andere"-Zweig von get_gruppen_page_data und der zweite Organigramm-
# Endpunkt (orgchart_api) gingen daran vorbei — ein Alt-/Fremdwert kam so roh
# als CSS-Wert in die Oberflaeche. Beide nutzen jetzt api/farbe.py.


def test_farbe_normalisieren_grenzfaelle():
    """Die gemeinsame Stelle: Hex ja, alles andere nein — auch geschleust."""
    from diakronos_app.api.farbe import _normalisiere_farbe

    assert _normalisiere_farbe("#3b82f6") == "#3b82f6"
    assert _normalisiere_farbe("#abc") == "#abc"
    assert _normalisiere_farbe("3b82f6") == "#3b82f6"        # fehlendes '#'
    assert _normalisiere_farbe("  #FFF  ") == "#FFF"          # getrimmt
    assert _normalisiere_farbe("#11223344") == "#11223344"     # RRGGBBAA
    assert _normalisiere_farbe(None) == "#667eea"
    assert _normalisiere_farbe("") == "#667eea"
    # Angriffsformen: Fallback auf den Standard, nie roh durchreichen.
    for boese in (
        "zzz-keine-farbe",
        "red;background-image:url(x)",
        "expression(alert(1))",
        "javascript:alert(1)",
        '"><script>alert(1)</script>',
        "url(javascript:alert(1))",
        "#12345",           # unzulaessige Laenge
        "#gggggg",          # kein Hex
    ):
        assert _normalisiere_farbe(boese) == "#667eea", boese


def test_gruppen_page_data_andere_bereiche_farbe_bereinigt(hierarchie):
    """Der "andere_gruppen"-Zweig (Admin) gibt die Farbe bereinigt aus."""
    from diakronos_app.api.gruppen import get_gruppen_page_data
    from diakronos_app.frappe_compat.query import get_doc

    set_user("admin@example.org")
    db = get_doc("Dienstbereich", "DB-A")
    db.farbe = "red;background-image:url(x)"
    db.save()

    res = get_gruppen_page_data()
    # Nur Bereiche MIT Gruppen erscheinen; DB-A traegt Schrott -> Standard.
    farben = {e["dienstbereich"]: e["dienstbereich_farbe"] for e in res["andere_gruppen"]}
    assert farben["DB-A"] == "#667eea"

    # Zum Gegenbeweis: eine gueltige Farbe kommt unveraendert heraus.
    db2 = get_doc("Dienstbereich", "DB-B")
    db2.farbe = "3b82f6"
    db2.save()
    res2 = get_gruppen_page_data()
    farben2 = {e["dienstbereich"]: e["dienstbereich_farbe"] for e in res2["andere_gruppen"]}
    assert farben2["DB-B"] == "#3b82f6"


def test_orgchart_api_farbe_bereinigt(hierarchie):
    """orgchart_api.get_orgchart_data (zweiter Renderer) gibt keine Rohlwerte."""
    from diakronos_app.api.orgchart_api import get_orgchart_data
    from diakronos_app.frappe_compat.query import get_doc

    set_user("admin@example.org")
    db = get_doc("Dienstbereich", "DB-A")
    db.farbe = '"><script>window.__xss=1</script>'
    db.save()

    by_id = {n["id"]: n for n in get_orgchart_data()}
    assert by_id["DB-A"]["farbe"] == "#667eea"

    # Gueltige Farbe bleibt erhalten.
    db2 = get_doc("Dienstbereich", "DB-B")
    db2.farbe = "3b82f6"
    db2.save()
    by_id2 = {n["id"]: n for n in get_orgchart_data()}
    assert by_id2["DB-B"]["farbe"] == "#3b82f6"

