"""DEV-B5 — Ressourcen: eigene Anfragen freigeben (mit Recht) + „Eigene Anfragen“.

Befund DMB-fd818e23a4b6 (Dev-Modus, 08.11.); ENTSCHEIDUNG Manuel (09.11.):
„Wenn man die Rechte hat, soll man es freigeben können.“

Vorher sperrte der Server die Selbst-Freigabe absichtlich
(`decide_buchung`/`decide_termin_ressource`: „Eigene Anfragen können nicht
selbst moderiert werden.“), die Oberfläche zeigte die Knöpfe trotzdem — der
Klick endete im Fehler.

Abgedeckt:
  * Selbstfreigabe MIT Recht ist erlaubt und im Audit-Protokoll als
    „Selbstfreigabe“ gekennzeichnet (Buchung und Termin-Ressource).
  * OHNE Recht weiterhin 403 (die Rechtsschranke bleibt unangetastet).
  * Die Konfliktprüfung beim Bestätigen gilt unverändert auch für die eigene
    Anfrage.
  * `get_meine_buchungen`: `darf_entscheiden` nur mit Recht und nur bei
    offenen Anfragen; eigene Termin-Ressourcen erscheinen mit `quelle="termin"`.
  * Zurücknehmen (`delete_buchung`) nur eigene Anfragen, nur „Angefragt“.

Frontend: `frontend/tests/devb5-eigene-anfragen.test.mjs`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.query import get_all
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import RessourcenBuchung
from diakronos_app.models.kronos import Element, ElementRessource, Kalender, Ressource

RES_MODUL = "diakronos.diakonos.api.ressourcen"

ANNA = "anna@example.org"
BRUNO = "bruno@example.org"
MODERATOR = "moderator@example.org"


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=True),
        User(name=MODERATOR, email=MODERATOR, full_name="Moderator", enabled=True),
        Ressource(name="RES-SAAL", ressource_name="Gemeindesaal", typ="Raum",
                  kapazitaet=80, beschreibung="Saal", tags="saal",
                  bild="", wartung=0, docstatus=0, idx=0),
        Kalender(name="Gemeinde", calendar_name="Gemeinde",
                 selbstverwaltet=0, docstatus=0, idx=0),
        HasRole(name="HR-MOD", parent=MODERATOR, parenttype="User",
                parentfield="roles", role="Ressourcenmoderator", docstatus=0, idx=1),
        UserRole(name="UR-GEM-1", parent="Gemeinde", parenttype="Kalender",
                 parentfield="leserechte", role="All", docstatus=0, idx=1),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_moderator(welt):
    set_user(MODERATOR)
    yield MODERATOR
    set_user("Administrator")


def _offene_buchung(gebucht_von: str, name: str = "BUC-EIGEN",
                    tage: int = 40) -> str:
    """Offene Anfrage einer Person anlegen (docstatus 0, Status Angefragt)."""
    from diakronos_app.api import ressourcen as R

    start = (datetime.now() + timedelta(days=tage)).replace(microsecond=0)
    return R._create("Ressourcen Buchung", {
        "name": name,
        "ressource": "RES-SAAL", "zweck": "Eigene Anfrage", "status": "Angefragt",
        "datum_von": start, "datum_bis": start + timedelta(hours=2),
        "gebucht_von": gebucht_von, "gebucht_von_name": "Wer auch immer",
    })


def _offene_termin_anfrage(sess, owner: str, *, zeile: str = "ER-EIGEN",
                           termin: str = "EL-EIGEN") -> None:
    start = (datetime.now() + timedelta(days=45)).replace(microsecond=0)
    sess.add(Element(
        name=termin, element_name="Eigener Termin", element_start=start,
        element_end=start + timedelta(hours=2), element_calendar="Gemeinde",
        ressource="", status="Festgelegt", ignore_conflict=0, docstatus=0,
        idx=0, owner=owner,
    ))
    sess.add(ElementRessource(
        name=zeile, parent=termin, parenttype="Element",
        parentfield="zusaetzliche_ressourcen", ressource="RES-SAAL",
        freitext_ressource="", status="Angefragt", notiz="", docstatus=0, idx=1,
    ))
    sess.commit()


def _audit_eintraege() -> list[dict]:
    return [e for e in (get_all(
        "Audit Log", fields=["actor", "target_doctype", "target_name", "begruendung"],
    ) or []) if isinstance(e, dict)]


# ── Selbstfreigabe Buchung ──────────────────────────────────────────────────


def test_selbstfreigabe_bestaetigen_mit_recht(client, als_moderator):
    """Wer das Freigaberecht hat, darf die EIGENE Anfrage bestätigen."""
    buchung_id = _offene_buchung(MODERATOR)

    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": buchung_id, "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == {"success": True, "status": "Bestätigt"}

    from diakronos_app.frappe_compat.query import get_doc

    doc = get_doc("Ressourcen Buchung", buchung_id)
    assert doc.status == "Bestätigt"
    assert doc.moderiert_von == MODERATOR


def test_selbstfreigabe_steht_als_selbstfreigabe_im_protokoll(client, als_moderator):
    """Die Selbstfreigabe ist nachvollziehbar gekennzeichnet (Audit)."""
    buchung_id = _offene_buchung(MODERATOR, name="BUC-AUDIT")

    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": buchung_id, "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text

    treffer = [e for e in _audit_eintraege() if e.get("target_name") == buchung_id]
    assert treffer, "kein Protokolleintrag zur Selbstfreigabe"
    assert any("Selbstfreigabe" in (e.get("begruendung") or "") for e in treffer)
    assert treffer[0]["actor"] == MODERATOR
    assert treffer[0]["target_doctype"] == "Ressourcen Buchung"


def test_selbstfreigabe_ohne_recht_bleibt_verweigert(client, welt):
    """Ein normaler Nutzer bekommt weiter 403 — die Rechtsschranke bleibt."""
    set_user(ANNA)
    try:
        buchung_id = _offene_buchung(ANNA, name="BUC-ANNA")
        r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                        json={"buchung_id": buchung_id, "entscheidung": "bestaetigen"})
        assert r.status_code == 403, r.text
        assert "Ressourcenmoderatoren" in r.json()["message"]
    finally:
        set_user("Administrator")


def test_selbstfreigabe_prueft_konflikte_wie_fremde_anfragen(client, als_moderator):
    """Wird der Zeitraum hart belegt, scheitert auch die eigene Freigabe (417)."""
    buchung_id = _offene_buchung(MODERATOR, name="BUC-KONFLIKT")
    from diakronos_app.api import ressourcen as R
    from diakronos_app.frappe_compat.query import get_doc

    eigen = get_doc("Ressourcen Buchung", buchung_id)
    R._create("Ressourcen Buchung", {
        "ressource": "RES-SAAL", "zweck": "Fremd bestätigt",
        "status": "Bestätigt",
        "datum_von": eigen.datum_von, "datum_bis": eigen.datum_bis,
        "gebucht_von": BRUNO, "gebucht_von_name": "Bruno Beispiel",
    })

    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": buchung_id, "entscheidung": "bestaetigen"})
    assert r.status_code == 417, r.text
    assert "Konflikt" in r.json()["message"]
    assert get_doc("Ressourcen Buchung", buchung_id).status == "Angefragt"


def test_fremde_anfrage_wird_nicht_als_selbstfreigabe_protokolliert(client, als_moderator):
    """Zur Gegenprobe: fremde Anfrage -> Protokoll ohne „Selbstfreigabe“."""
    buchung_id = _offene_buchung(BRUNO, name="BUC-FREMD", tage=50)

    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": buchung_id, "entscheidung": "ablehnen",
                          "grund": "belegt"})
    assert r.status_code == 200, r.text

    treffer = [e for e in _audit_eintraege()
               if e.get("target_name") == buchung_id and e.get("begruendung")]
    assert treffer
    assert all("Selbstfreigabe" not in (e.get("begruendung") or "") for e in treffer)
    assert any("Freigabe" in (e.get("begruendung") or "") for e in treffer)


# ── Selbstfreigabe Termin-Ressource ─────────────────────────────────────────


def test_selbstfreigabe_termin_ressource_mit_recht(client, als_moderator, welt):
    """Der Eigentümer des Termins darf mit Recht dessen Ressource bestätigen."""
    _offene_termin_anfrage(welt, MODERATOR)

    r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                    json={"zeile_id": "ER-EIGEN", "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text
    zeile = welt.get(ElementRessource, "ER-EIGEN")
    welt.refresh(zeile)
    assert zeile.status == "Bestätigt"

    treffer = [e for e in _audit_eintraege()
               if e.get("target_name") == "ER-EIGEN" and e.get("begruendung")]
    assert any("Selbstfreigabe" in (e.get("begruendung") or "") for e in treffer)


def test_selbstfreigabe_termin_ressource_ohne_recht_403(client, welt):
    """Ohne Recht bleibt die Entscheidung an der eigenen Termin-Zeile 403."""
    _offene_termin_anfrage(welt, ANNA, zeile="ER-ANNA", termin="EL-ANNA")
    set_user(ANNA)
    try:
        r = client.post(f"/api/method/{RES_MODUL}.decide_termin_ressource",
                        json={"zeile_id": "ER-ANNA", "entscheidung": "bestaetigen"})
        assert r.status_code == 403, r.text
    finally:
        set_user("Administrator")


# ── get_meine_buchungen: Recht + eigene Termin-Anfragen ────────────────────


def test_meine_buchungen_darf_entscheiden_mit_recht(client, als_moderator):
    _offene_buchung(MODERATOR, name="BUC-MEIN")
    r = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen")
    assert r.status_code == 200, r.text
    eintrag = next(x for x in r.json()["message"] if x["id"] == "BUC-MEIN")
    assert eintrag["darf_entscheiden"] is True
    assert eintrag["status"] == "Angefragt"
    assert eintrag["quelle"] == "buchung"
    assert "notizen" in eintrag


@pytest.fixture()
def als_anna_probe_welt(welt):
    set_user(ANNA)
    _offene_buchung(ANNA, name="BUC-ANNA")
    yield welt
    set_user("Administrator")


def test_meine_buchungen_ohne_recht_kein_darf_entscheiden(client, als_anna_probe_welt):
    r = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen")
    assert r.status_code == 200, r.text
    eintrag = next(x for x in r.json()["message"] if x["id"] == "BUC-ANNA")
    assert eintrag["darf_entscheiden"] is False


def test_meine_buchungen_entschiedene_anfrage_ohne_darf_entscheiden(client, als_moderator):
    """Entschiedene eigene Anfragen bleiben in der Liste, aber ohne Knöpfe."""
    buchung_id = _offene_buchung(MODERATOR, name="BUC-ENTSCH")
    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": buchung_id, "entscheidung": "ablehnen",
                          "grund": "zu kurzfristig"})
    assert r.status_code == 200, r.text

    r = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen")
    eintrag = next(x for x in r.json()["message"] if x["id"] == buchung_id)
    assert eintrag["status"] == "Abgelehnt"
    assert eintrag["ablehnungs_grund"] == "zu kurzfristig"
    assert eintrag["darf_entscheiden"] is False


def test_meine_buchungen_enthaelt_eigene_termin_anfragen(client, als_moderator, welt):
    _offene_termin_anfrage(welt, MODERATOR, zeile="ER-MEIN", termin="EL-MEIN")
    r = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen")
    assert r.status_code == 200, r.text
    eintrag = next(x for x in r.json()["message"] if x["id"] == "ER-MEIN")
    assert eintrag["quelle"] == "termin"
    assert eintrag["status"] == "Angefragt"
    assert eintrag["resourceName"] == "Gemeindesaal"
    assert eintrag["purpose"] == "Eigener Termin"
    assert eintrag["darf_entscheiden"] is True


def test_meine_buchungen_zeigt_keine_fremden_termin_anfragen(client, als_moderator, welt):
    _offene_termin_anfrage(welt, BRUNO, zeile="ER-FREMD", termin="EL-FREMD")
    r = client.get(f"/api/method/{RES_MODUL}.get_meine_buchungen")
    ids = {x["id"] for x in r.json()["message"]}
    assert "ER-FREMD" not in ids


# ── Zurücknehmen nur eigene, nur offene ─────────────────────────────────────


def test_zuruecknehmen_nur_eigene_anfrage(client, als_moderator):
    fremd = _offene_buchung(BRUNO, name="BUC-FREMD2", tage=60)
    r = client.post(f"/api/method/{RES_MODUL}.delete_buchung",
                    json={"buchung_id": fremd})
    assert r.status_code == 403, r.text
    assert "Ersteller" in r.json()["message"]


def test_zuruecknehmen_eigene_offene_anfrage(client, als_moderator):
    eigen = _offene_buchung(MODERATOR, name="BUC-ZURUECK", tage=62)
    r = client.post(f"/api/method/{RES_MODUL}.delete_buchung",
                    json={"buchung_id": eigen})
    assert r.status_code == 200, r.text

    from diakronos_app.frappe_compat.query import get_doc

    assert get_doc("Ressourcen Buchung", eigen).status == "Storniert"


def test_zuruecknehmen_nach_entscheidung_nicht_mehr_moeglich(client, als_moderator):
    eigen = _offene_buchung(MODERATOR, name="BUC-DANN", tage=64)
    r = client.post(f"/api/method/{RES_MODUL}.decide_buchung",
                    json={"buchung_id": eigen, "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text

    r = client.post(f"/api/method/{RES_MODUL}.delete_buchung",
                    json={"buchung_id": eigen})
    assert r.status_code == 200, r.text  # Bestätigt darf storniert werden

    r = client.post(f"/api/method/{RES_MODUL}.delete_buchung",
                    json={"buchung_id": eigen})
    assert r.status_code == 417, r.text
    assert "Storniert" in r.json()["message"]
