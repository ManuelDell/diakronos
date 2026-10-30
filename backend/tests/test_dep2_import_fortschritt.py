"""DEP-2: Fortschritt des Google-Imports abfragbar (Abfrage statt Socket.IO).

Hintergrund: `frontend/package.json` fuehrte `socket.io-client` allein fuer den
Fortschrittsbalken in `KalenderImport.vue`. Ein zweiter Verbindungsweg
(Socket.IO) ist im Hausnetz fehleranfaellig und bindet ein Paket mit eigener
Abhaengigkeitskette. Der Stand liegt jetzt zusaetzlich in Redis und wird ueber
den RPC `get_import_progress` gelesen; `publish_realtime` bleibt unveraendert
bedient (der Kanal `gcal_import_progress` ist Vertrag, realtime.py).

Geprueft wird:
1. ein gemeldeter Stand kommt unveraendert zurueck,
2. ohne Stand kommt `{"state": None}` (kein Fehler),
3. ein kaputter Redis-Wert fuehrt nicht zu einem 500er,
4. ein Redis-Ausfall kippt weder Abfrage noch Import,
5. Gaeste duerfen nicht abfragen,
6. der Worker legt JEDE Meldung auch ab (Fortschritt und Abschluss).

Redis ist der Test-Stub — nie das Redis des Betriebs (Regel 11).
"""
import json

import pytest
from redis.exceptions import RedisError

from diakronos_app.api.kronos import google_import as g
from test_google_oauth import PATH, authorize, configured, google


class _FortschrittsStub:
    """Minimaler Redis-Ersatz: nur die Kommandos, die der Endpunkt nutzt."""

    def __init__(self):
        self.store = {}
        self.fehler = False

    def set(self, key, value, ex=None):
        if self.fehler:
            raise RedisError("nicht erreichbar")
        self.store[key] = value

    def get(self, key):
        if self.fehler:
            raise RedisError("nicht erreichbar")
        return self.store.get(key)

    def delete(self, key):
        if self.fehler:
            raise RedisError("nicht erreichbar")
        self.store.pop(key, None)


@pytest.fixture()
def fortschritt(monkeypatch):
    stub = _FortschrittsStub()
    monkeypatch.setattr(g, "_progress_client", lambda: stub)
    return stub


def test_stand_wird_abgelegt_und_zurueckgegeben(configured, fortschritt):
    g._merke_fortschritt("Administrator", {"status": "importing", "imported": 7})
    antwort = configured.get(PATH + "get_import_progress")
    assert antwort.status_code == 200
    assert antwort.json()["message"] == {"state": {"status": "importing", "imported": 7}}


def test_ohne_stand_ist_die_antwort_leer_und_kein_fehler(configured, fortschritt):
    antwort = configured.get(PATH + "get_import_progress")
    assert antwort.status_code == 200
    assert antwort.json()["message"] == {"state": None}


def test_kaputter_wert_wird_verworfen(configured, fortschritt):
    fortschritt.store[g._SCHLUESSEL.format(benutzer="Administrator")] = "kein json"
    antwort = configured.get(PATH + "get_import_progress")
    assert antwort.status_code == 200
    assert antwort.json()["message"] == {"state": None}


def test_redis_ausfall_kippt_weder_abfrage_noch_import(configured, fortschritt):
    fortschritt.fehler = True
    # Ablegen darf nie werfen (der Import laeuft weiter).
    g._merke_fortschritt("Administrator", {"status": "done"})
    antwort = configured.get(PATH + "get_import_progress")
    assert antwort.status_code == 200
    assert antwort.json()["message"] == {"state": None}


def test_gaeste_duerfen_nicht_abfragen(guest_client, fortschritt):
    assert guest_client.get(PATH + "get_import_progress").status_code in (401, 403, 417)


def test_worker_legt_jede_meldung_ab(client, patched_db, monkeypatch):
    """Der Hintergrundauftrag schreibt neben `publish_realtime` auch den Stand."""
    abgelegt = []
    monkeypatch.setattr(g, "publish_realtime", lambda *a, **kw: None)
    monkeypatch.setattr(g, "_merke_fortschritt", lambda user, data: abgelegt.append(data))
    monkeypatch.setattr(g, "_require_import_admin", lambda: None)
    # `ist_aktiv` wird im Worker lokal aus benutzer_status importiert.
    monkeypatch.setattr("diakronos_app.frappe_compat.benutzer_status.ist_aktiv", lambda user: True)

    # Leere Zuordnung: der Lauf endet sofort mit der Abschlussmeldung.
    g._do_import([], "Administrator")

    assert abgelegt, "der Worker hat keinen Stand abgelegt"
    assert abgelegt[-1]["status"] == "done"
    assert "total_imported" in abgelegt[-1]
    # Der abgelegte Stand muss JSON-faehig sein — genau so liegt er in Redis.
    json.dumps(abgelegt[-1])


# ── Operator-Review DEP-2, Punkte 2 und 3 ────────────────────────────────

def test_start_import_loescht_den_stand_des_vorigen_laufs(configured, google, patched_db,
                                                         fortschritt, monkeypatch):
    """Punkt 2: Ohne das Loeschen liest ein zweiter Import innerhalb von
    `PROGRESS_TTL` sofort das alte `done` und beendet den Balken."""
    state = authorize(configured)
    configured.post(PATH + "exchange_code", json={"code": "fake-code", "state": state})
    # Der vorige Lauf hat abgeschlossen — der Stand liegt noch in Redis.
    g._merke_fortschritt("Administrator", {"status": "done", "total_imported": 99})
    schluessel = g._SCHLUESSEL.format(benutzer="Administrator")
    assert schluessel in fortschritt.store

    monkeypatch.setattr(g, "enqueue", lambda *a, **kw: None)
    antwort = configured.post(PATH + "start_import", json={"mappings_json": json.dumps([
        {"google_id": "id", "google_name": "Fake", "create_new": True},
    ])})
    assert antwort.status_code == 200
    assert schluessel not in fortschritt.store, "der Stand des vorigen Laufs steht noch"
    # Und die Abfrage meldet danach „noch nichts", nicht das alte Ergebnis.
    assert configured.get(PATH + "get_import_progress").json()["message"] == {"state": None}


def test_loeschen_ist_fehlerfest(configured, fortschritt):
    """Ein Redis-Ausfall beim Loeschen darf den Import nicht verhindern."""
    def platze(key):
        raise RedisError("nicht erreichbar")

    fortschritt.delete = platze
    g._loesche_fortschritt("Administrator")  # darf nicht werfen


def test_worker_traegt_die_vollstaendige_warnliste(configured, patched_db, monkeypatch):
    """Punkt 3: Zwischenwarnungen gingen verloren, wenn sie zwischen zwei
    Abfragen kamen. Jeder Stand traegt jetzt die vollstaendige Liste."""
    gemeldet = []
    monkeypatch.setattr(g, "publish_realtime", lambda *a, **kw: None)
    monkeypatch.setattr(g, "_merke_fortschritt", lambda user, data: gemeldet.append(data))
    monkeypatch.setattr(g, "_require_import_admin", lambda: None)
    monkeypatch.setattr("diakronos_app.frappe_compat.benutzer_status.ist_aktiv", lambda user: True)
    # Ein Kalender, damit der Lauf meldet (Zuordnung ohne DB-Zugriff: neuer Kalender).
    monkeypatch.setattr(g, "_validate_mappings", lambda m: m)
    monkeypatch.setattr(g, "_get_valid_access_token", lambda: "fake")
    monkeypatch.setattr(g, "_ensure_kalender", lambda name, color, db: "Chor")
    monkeypatch.setattr(g, "_import_events_from_google",
                        lambda *a, **kw: (kw["pub"]({"status": "warning",
                                                     "warning": "Grosser Kalender: Import kann laenger dauern."}) or (3, 1)))

    g._do_import([{"google_id": "id", "google_name": "Chor", "create_new": True,
                   "target_kalender": "", "color": "#4285F4", "time_filter": "all"}], "Administrator")

    assert gemeldet, "der Worker hat nichts abgelegt"
    abschluss = gemeldet[-1]
    assert abschluss["status"] == "done"
    # Die Warnung des Zwischenstands steht auch im Abschluss.
    assert abschluss["warnings"] == ["Grosser Kalender: Import kann laenger dauern."]
    # Jeder Stand traegt die Liste — auch die ohne eigene Warnung.
    assert all("warnings" in stand for stand in gemeldet)
