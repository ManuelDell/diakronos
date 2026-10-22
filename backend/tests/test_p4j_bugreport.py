"""P4j — Portiertes Modul `api.bugreport` (4 Endpunkte, Dev-Bugmelder).

Quelle (READ-ONLY):
  referenz/diakronos-frappe/diakronos/diakonos/api/bugreport.py

Kontrollpfad zeichenweise aus Aufrufliste des Frappe-Frontends (die SPA ruft NUR
`diakronos.diakonos.api.bugreport.melden`; Achtung auf das „r" in `diakronos`).
Die uebrigen 3 Endpunkte (`liste`, `detail`, `set_status`) sind Desk/Orchestrator
und werden trotzdem mitportiert (Regel 12: ein Modul wird nicht aufgeteilt).

Abgedeckt:
  * Registrierung: `FRAPPE_MODULE == "diakronos.diakonos.api.bugreport"`, alle 4
    Originalpfade aufloesbar, `melden` ueber den Router per HTTP erreichbar.
  * Login-Pflicht (`allow_guest=False`): Guest -> 403 fuer alle 4.
  * `melden`: Schranke `dev_modus` (aus -> 403, an -> 201/insert), Spoofing-Schutz
    (benutzer/mitglied NIE aus dem Payload), Kontextfelder + Element-Kappen,
    Log-Deckelung (50 Eintraege, 256 KB-Budget), Titel/Beschreibung-Trimmung.
  * Screenshot: gueltige PNG-Data-URL -> `File`-Doc + `file_url` am Bericht;
    zu gross -> WARNUNG in der Beschreibung, Bericht bleibt bestehen;
    ungueltig -> WARNUNG; Datei-Ablage ist die aus P2c (`upload_file`).
  * `liste`: nur Admins (Nicht-Admin -> 403, Guest -> 403), Statusfilter,
    limit-Klemmung (1..200), Feldsatz ohne die grossen Felder.
  * `detail`: nur Admins, alle Felder, unbekannter Name -> DoesNotExist.
  * `set_status`: nur Admins, Status-Allowlist, unbekannter Status -> 417.
  * Sichtbarkeit: ein Nicht-Admin sieht fremde Berichte NICHT (die Sichtbarkeit
    liegt in `_require_admin`; `liste`/`detail` geben Nicht-Admins gar nichts).
"""

from __future__ import annotations

import base64
import json

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

BUGREPORT = "diakronos.diakonos.api.bugreport"

# Alle 4 Originalpfade (FRAPPE_MODULE + Funktionsname).
PATHS = [
    f"{BUGREPORT}.melden",
    f"{BUGREPORT}.liste",
    f"{BUGREPORT}.detail",
    f"{BUGREPORT}.set_status",
]

ANNA = "anna@example.org"       # eingeloggt, KEIN Admin
BRUNO = "bruno@example.org"     # eingeloggt, Mitglied verknuepft
ADMIN = "admin@example.org"     # Mitgliederadministrator
ROOT = "Administrator"          # Frappe-Admin-Sonderfall


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def files_dir(tmp_path, monkeypatch):
    """`settings.files_dir` auf ein tmp-Verzeichnis zeigen (wie in P2c).

    Ohne das schreibt `upload_file` in die echte Ablage (`/data`).
    """
    from diakronos_app import settings as settings_mod

    target = tmp_path / "files"
    monkeypatch.setattr(settings_mod.settings, "files_dir", str(target))
    return target


@pytest.fixture()
def welt(patched_db, files_dir):
    """Benutzer, Rollen, Mitglieder, Einstellungen (dev_modus AN), Berichte."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import BugReport, Mitglied
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    sess = patched_db()

    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=1),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=1),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=1),
    ])
    # Nur ADMIN hat die Admin-Rolle.
    sess.add_all([
        HasRole(name="r1", parent=ADMIN, parenttype="User",
                parentfield="roles", role="Mitgliederadministrator"),
    ])
    # Bruno ist Mitglied (user-Verknuepfung) -> melden setzt `mitglied`.
    sess.add_all([
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                 email=ANNA, user=ANNA, status="Mitglied", docstatus=0, idx=0),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel",
                 email=BRUNO, user=BRUNO, status="Mitglied", docstatus=0, idx=0),
    ])
    # Bugmelder AN (dev_modus=True).
    sess.add(DiakronosEinstellungen(name="Diakronos Einstellungen", dev_modus=True))
    # Bestandsberichte: einer von ANNA, einer von BRUNO.
    sess.add_all([
        BugReport(name="BR-1", titel="Anna kaputt", status="Neu",
                  benutzer=ANNA, mitglied="M-0001", oberflaeche="kronos",
                  route="/kronos/kalender", beschreibung="Detail A",
                  konsole_log='["a"]', netzwerk_log='["n"]',
                  screenshot="/files/br1.png", docstatus=0, idx=0),
        BugReport(name="BR-2", titel="Bruno kaputt", status="Behoben",
                  benutzer=BRUNO, mitglied="M-0002", oberflaeche="diakonos",
                  route="/diakonos", beschreibung="Detail B",
                  konsole_log="", netzwerk_log="", screenshot=None,
                  docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


def _png_data_url(raw: bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 32) -> str:
    return "data:image/png;base64," + base64.b64encode(raw).decode()


# ── Registrierung ───────────────────────────────────────────────────────────


def test_frappe_module_gesetzt():
    import diakronos_app.api.bugreport as mod

    assert mod.FRAPPE_MODULE == BUGREPORT


def test_frappe_module_pfad_zeichenweise():
    """Der Fehler einer frueheren Karte war ein einzelnes fehlendes „r"."""
    import diakronos_app.api.bugreport as mod

    assert "diakronos.diakonos.api.bugreport" == mod.FRAPPE_MODULE
    assert "diakonos.diakronos" not in mod.FRAPPE_MODULE


@pytest.mark.parametrize("path", PATHS)
def test_originalpfad_aufloesbar(path):
    assert callable(lookup(path)), f"{path} nicht registriert"


def test_melden_per_http_erreichbar(client, welt):
    """Der Router (nicht nur das Registry-Dict) muss den Originalpfad kennen."""
    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={})
    # 417/500 waeren Fachfehler, 404 waere ein Routing-Fehler.
    assert resp.status_code != 404, resp.text


# ── Login-Pflicht ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", PATHS)
def test_login_pflicht(path, client):
    set_user("Guest")
    resp = client.post(f"/api/method/{path}", json={})
    assert resp.status_code == 401, f"{path} liess Guest durch: {resp.status_code}"


# ── Schranke dev_modus ──────────────────────────────────────────────────────


def test_melden_ohne_dev_modus_ist_gesperrt(client, welt):
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    welt.get(DiakronosEinstellungen, "Diakronos Einstellungen").dev_modus = False
    welt.commit()
    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={})
    assert resp.status_code == 403, resp.text
    assert "deaktiviert" in resp.json()["message"].lower()


def test_melden_mit_dev_modus_legt_bericht_an(client, welt):
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({
            "titel": "  Absturz im Kalender  ",
            "beschreibung": "  Klick auf Speichern  ",
            "oberflaeche": "kronos",
            "route": "/kronos/kalender",
        }),
    })
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["screenshot"] is False
    name = msg["name"]
    assert name

    row = welt.get(BugReport, name)
    assert row.titel == "Absturz im Kalender"
    assert row.beschreibung == "Klick auf Speichern"
    assert row.status == "Neu"
    assert row.oberflaeche == "kronos"
    assert row.route == "/kronos/kalender"
    # Mitglied wurde aus der user-Verknuepfung aufgeloest.
    assert row.mitglied == "M-0002"


def test_melden_benutzer_nicht_aus_payload(client, welt):
    """Spoofing-Schutz: `benutzer`/`mitglied` kommen NIE aus dem Payload."""
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({"benutzer": ADMIN, "mitglied": "M-0001",
                               "titel": "Spoof"}),
    })
    assert resp.status_code == 200, resp.text
    row = welt.get(BugReport, resp.json()["message"]["name"])
    assert row.benutzer == BRUNO
    assert row.mitglied == "M-0002"


def test_melden_kappt_elementfelder(client, welt):
    from diakronos_app.api.bugreport import _ELEMENT_CAPS
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({
            "element_selektor": "s" * 900,
            "element_text": "t" * 900,
            "element_html": "h" * 5000,
            "element_komponente": "k" * 900,
        }),
    })
    assert resp.status_code == 200, resp.text
    row = welt.get(BugReport, resp.json()["message"]["name"])
    for feld, cap in _ELEMENT_CAPS.items():
        wert = getattr(row, feld)
        assert len(wert) == cap, f"{feld}: {len(wert)} != {cap}"
        assert wert.endswith("\u2026")


def test_melden_deckelt_logs_auf_50_eintraege(client, welt):
    from diakronos_app.models.diakonos import BugReport

    eintraege = [f"log-{i}" for i in range(80)]
    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({"konsole_log": eintraege,
                               "netzwerk_log": eintraege}),
    })
    assert resp.status_code == 200, resp.text
    row = welt.get(BugReport, resp.json()["message"]["name"])
    konsole = json.loads(row.konsole_log)
    netzwerk = json.loads(row.netzwerk_log)
    assert len(konsole) == 50 and len(netzwerk) == 50
    # Nur die LETZTEN 50 bleiben erhalten.
    assert konsole == eintraege[-50:]
    assert netzwerk == eintraege[-50:]


def test_melden_ungueltiger_payload(client, welt):
    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden",
                       json={"payload": "kein json {"})
    assert resp.status_code == 417, resp.text
    assert "payload" in resp.json()["message"].lower()


# ── Screenshot ──────────────────────────────────────────────────────────────


def test_melden_speichert_gueltigen_screenshot(client, welt):
    from diakronos_app.models.core import FileModel
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({"titel": "mit Bild"}),
        "screenshot": _png_data_url(),
    })
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["screenshot"] is True

    row = welt.get(BugReport, msg["name"])
    assert row.screenshot and row.screenshot.startswith("/files/")
    # Die Ablage ist die aus P2c: ein `File`-Doc am Bericht, privat.
    file_rows = welt.query(FileModel).filter(
        FileModel.attached_to_doctype == "Bug Report",
        FileModel.attached_to_name == msg["name"],
    ).all()
    assert len(file_rows) == 1
    f = file_rows[0]
    assert f.is_private is True
    assert f.attached_to_field == "screenshot"
    assert f.file_name.endswith(".png")
    assert f.file_size > 0
    assert f.owner == BRUNO
    assert client.get(f.file_url).status_code == 200
    set_user(ANNA)
    assert client.get(f.file_url).status_code == 403


def test_screenshot_cannot_attach_to_foreign_report(welt):
    from diakronos_app.api.bugreport import _speichere_screenshot
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.models.core import FileModel

    set_user(BRUNO)
    before = welt.query(FileModel).count()
    with pytest.raises(PermissionError):
        _speichere_screenshot(b'\x89PNG\r\n\x1a\n' + b'\x00' * 24, 'image/png', 'BR-1')
    assert welt.query(FileModel).count() == before


def test_melden_zu_grosser_screenshot_kippt_bericht_nicht(client, welt):
    from diakronos_app.models.diakonos import BugReport

    gross = b"\x89PNG" + b"x" * (4 * 1024 * 1024 + 100)
    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({"beschreibung": "Text bleibt"}),
        "screenshot": _png_data_url(gross),
    })
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["screenshot"] is False
    row = welt.get(BugReport, msg["name"])
    assert row.screenshot is None
    assert "Text bleibt" in row.beschreibung
    assert "WARNUNG" in row.beschreibung and "verworfen" in row.beschreibung


def test_melden_ungueltiger_screenshot_kippt_bericht_nicht(client, welt):
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)
    resp = client.post(f"/api/method/{BUGREPORT}.melden", json={
        "payload": json.dumps({"beschreibung": "Text bleibt"}),
        "screenshot": "data:image/png;base64,!!!!kein-base64!!!!",
    })
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["screenshot"] is False
    row = welt.get(BugReport, msg["name"])
    assert row.screenshot is None
    assert "ungültig" in row.beschreibung or "ungueltig" in row.beschreibung


# ── liste ───────────────────────────────────────────────────────────────────


def test_liste_nur_admin(client, welt):
    set_user(ANNA)
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={})
    assert resp.status_code == 403, resp.text


def test_liste_admin_sieht_alle(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={})
    assert resp.status_code == 200, resp.text
    names = {r["name"] for r in resp.json()["message"]}
    assert names == {"BR-1", "BR-2"}


def test_liste_administrator_sonderfall(client, welt):
    """Der Original-`_require_admin` laesst `Administrator` ohne Rolle durch."""
    set_user(ROOT)
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={})
    assert resp.status_code == 200, resp.text


def test_liste_statusfilter(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.liste",
                       json={"status": "Behoben"})
    assert resp.status_code == 200, resp.text
    names = {r["name"] for r in resp.json()["message"]}
    assert names == {"BR-2"}


def test_liste_limit_geklemmt(client, welt):
    set_user(ADMIN)
    # limit=0 ist falsy -> trifft den `or 50`-Zweig des Originals (Default 50).
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={"limit": 0})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["message"]) == 2
    # limit=1 -> genau 1 Zeile (untere Klemmung wirkt).
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={"limit": 1})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["message"]) == 1
    # Unsinniges limit -> Default 50, kein Fehler.
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={"limit": "x"})
    assert resp.status_code == 200, resp.text


def test_liste_feldsatz_ohne_grosse_felder(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.liste", json={})
    zeile = resp.json()["message"][0]
    assert set(zeile) == {
        "name", "titel", "status", "gemeldet_am", "benutzer", "mitglied",
        "oberflaeche", "route",
    }


# ── detail ──────────────────────────────────────────────────────────────────


def test_detail_nur_admin(client, welt):
    set_user(ANNA)
    resp = client.post(f"/api/method/{BUGREPORT}.detail", json={"name": "BR-1"})
    assert resp.status_code == 403, resp.text


def test_detail_liefert_alle_felder(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.detail", json={"name": "BR-1"})
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["name"] == "BR-1"
    assert msg["konsole_log"] == '["a"]'
    assert msg["netzwerk_log"] == '["n"]'
    assert msg["screenshot"] == "/files/br1.png"
    assert "beschreibung" in msg and "notiz" in msg and "created" in msg


def test_detail_unbekannt(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.detail", json={"name": "NOPE"})
    # Router-Konvention: DoesNotExist -> 404 (nicht 417).
    assert resp.status_code == 404, resp.text
    assert resp.json().get("exc_type") == "DoesNotExistError"


# ── set_status ──────────────────────────────────────────────────────────────


def test_set_status_nur_admin(client, welt):
    set_user(ANNA)
    resp = client.post(f"/api/method/{BUGREPORT}.set_status",
                       json={"name": "BR-1", "status": "Behoben"})
    assert resp.status_code == 403, resp.text
    # Und der Status ist unveraendert geblieben.
    from diakronos_app.models.diakonos import BugReport

    assert welt.get(BugReport, "BR-1").status == "Neu"


def test_set_status_erlaubt(client, welt):
    from diakronos_app.models.diakonos import BugReport

    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.set_status",
                       json={"name": "BR-1", "status": "In Arbeit"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"] == {"name": "BR-1", "status": "In Arbeit"}
    assert welt.get(BugReport, "BR-1").status == "In Arbeit"


def test_set_status_unbekannter_status(client, welt):
    set_user(ADMIN)
    resp = client.post(f"/api/method/{BUGREPORT}.set_status",
                       json={"name": "BR-1", "status": "Quatsch"})
    assert resp.status_code == 417, resp.text
    assert "status" in resp.json()["message"].lower()


# ── Sichtbarkeit (DSGVO): Nicht-Admin sieht fremde Berichte NICHT ────────────


def test_nicht_admin_sieht_fremde_berichte_nicht(client, welt):
    """Bugreports tragen Screenshots/Kontext fremder Sitzungen.

    Die Sichtbarkeit wird durch `_require_admin` erzwungen: `liste` und `detail`
    liefern einem Nicht-Admin GAR NICHTS (403) — auch nicht die eigenen. Das ist
    die 1:1-Semantik des Originals (kein „nur eigene"-Filter).
    """
    set_user(ANNA)
    liste = client.post(f"/api/method/{BUGREPORT}.liste", json={})
    assert liste.status_code == 403
    detail = client.post(f"/api/method/{BUGREPORT}.detail", json={"name": "BR-2"})
    assert detail.status_code == 403


def test_set_status_nicht_admin_aendert_fremden_bericht_nicht(client, welt):
    from diakronos_app.models.diakonos import BugReport

    set_user(BRUNO)  # BR-2 ist seiner — trotzdem kein Schreibrecht ohne Admin.
    resp = client.post(f"/api/method/{BUGREPORT}.set_status",
                       json={"name": "BR-2", "status": "Verworfen"})
    assert resp.status_code == 403, resp.text
    assert welt.get(BugReport, "BR-2").status == "Behoben"
