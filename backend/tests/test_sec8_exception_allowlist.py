"""SEC-8 — Exception-Klassennamen-Leak und Methoden-Enumeration (Pentest R3-A).

Befund der autorisierten Pentest-Runde 3 (`bericht-deepseek-runde3.md`, R3-A,
NIEDRIG): Jede Fehlerantwort trug `exception`/`exc_type` mit dem INTERNEN
Python-Klassennamen — `ValidationError`, `DoesNotExistError`, `NotFound`,
`MethodNotAllowed`, `InternalError`, … Zusammen mit dem Status-Code ergab das
eine Landkarte: 404 = Methode gibt es nicht, 417 = gibt es mit falschen
Argumenten, 401 = gibt es mit Auth-Pflicht.

Was diese Karte NICHT tut: das Feld abschalten. Die SPA wertet es aus
(`shared/sitzung-pruefen.js` → `CSRFTokenError`/`SessionExpired`,
`MitgliedDetail.vue`/`useApi.js` → `PermissionError`). Der Weg ist deshalb
eine **Allowlist** dreier Namen, alles andere geht als `Error` hinaus:

  (S1) Genau diese drei Werte kommen unveraendert beim Client an — der
       Vertrag ist geprueft, nicht angenommen (erster Abschnitt).
  (S2) Jeder andere Klassenname wird zu `Error`; der echte Name steht im Log.
  (S3) Die Unterscheidbarkeit ueber den Status ist dort eingeengt, wo es die
       Auth-Semantik nicht bricht: unbekannter Name und falsche Argumente
       sehen gleich aus (404 vs. 404, 417 vs. 417), ein falscher Argumenttyp
       wird nicht mehr zum 500. 401 fuer „Anmeldung noetig" bleibt.
"""

from __future__ import annotations

import logging

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.router import (
    EXC_TYPEN_ALLOWLIST,
    GENERISCHER_EXC_TYP,
)

REGISTRIERUNG = "diakronos.diakonos.api.registrierung"

#: Alles, was ein interner Klassenname ist und NICHT nach aussen darf.
INTERNE_NAMEN = (
    "ValidationError",
    "DoesNotExistError",
    "NotFound",
    "MethodNotAllowed",
    "InternalError",
    "AuthenticationError",
    "RateLimitError",
    "DuplicateEntryError",
    "FrappeError",
    "FrappeCompatError",
)


def _exc_werte(body: dict) -> set[str]:
    return {str(body.get("exc_type", "")), str(body.get("exception", ""))}


# ── (S1) Der Frontend-Vertrag bleibt: drei Namen, unveraendert ─────────────


def test_allowlist_ist_genau_der_frontend_vertrag():
    """Die Allowlist ist der Vertrag — sie darf weder wachsen noch schrumpfen.

    Ermittelt per grep ueber `frontend/src` (Kartenpflicht S1):
    `shared/sitzung-pruefen.js:34` (CSRFTokenError), die 401-Wege
    (SessionExpired) und die Rechte-Behandlung (PermissionError).
    """
    assert EXC_TYPEN_ALLOWLIST == {"CSRFTokenError", "SessionExpired", "PermissionError"}
    assert GENERISCHER_EXC_TYP == "Error"


def test_csrf_token_error_kommt_unveraendert_an(client):
    """CSRF-Ablauf: 417 + `CSRFTokenError` — ohne diesen Wert baut die SPA die
    Sitzung nicht neu auf und zeigt dem Menschen einen Fachfehler."""
    r = client.post(
        "/api/method/frappe.client.insert",
        json={"doctype": "Mitglied"},
        headers={"X-Frappe-CSRF-Token": "falsch"},
    )

    assert r.status_code == 417, r.text
    assert r.json()["exc_type"] == "CSRFTokenError"
    assert r.json()["exception"] == "CSRFTokenError"


def test_session_expired_kommt_unveraendert_an(guest_client):
    """401 fuer „nicht angemeldet": die SPA unterscheidet das von 403."""
    r = guest_client.get("/api/method/ping")
    assert r.status_code == 401, r.text
    assert r.json()["exc_type"] == "SessionExpired"


def test_permission_error_kommt_unveraendert_an(client):
    """403 bleibt `PermissionError` — daran haengt die Rechte-Anzeige."""
    from diakronos_app.models.core import User

    r = client.get("/api/resource/User")
    # Ohne Admin: 403 PermissionError; mit Admin: 200. Beides ist in Ordnung,
    # geprueft wird nur der Fehlerfall.
    if r.status_code == 403:
        assert r.json()["exc_type"] == "PermissionError"
    else:  # pragma: no cover — Testclient ist Admin, dann ueber den DocType
        r2 = client.get("/api/resource/GibtEsNicht")
        assert User is not None
        assert r2.status_code == 404


# ── (S2) Alles andere wird generisch ──────────────────────────────────────


def test_does_not_exist_ist_generisch(client):
    """R3-A im Original: `GET /api/resource/User?fields=name,password_hash`."""
    r = client.get("/api/resource/User", params={"fields": "name,password_hash"})

    assert r.status_code == 404, r.text
    assert _exc_werte(r.json()) == {GENERISCHER_EXC_TYP}
    for name in INTERNE_NAMEN:
        assert name not in r.text, f"{name} steht noch in der Antwort: {r.text}"


def test_unbekannter_doctype_ist_generisch(client):
    r = client.get("/api/resource/GibtEsNicht")

    assert r.status_code == 404, r.text
    assert _exc_werte(r.json()) == {GENERISCHER_EXC_TYP}


def test_fachfehler_validationerror_ist_generisch(client):
    """`frappe.throw` → 417; die MELDUNG bleibt, der Klassenname nicht."""
    r = client.post("/api/method/fail_validation", json={"msg": "zu jung"})

    assert r.status_code == 417, r.text
    assert r.json()["message"] == "zu jung"
    assert _exc_werte(r.json()) == {GENERISCHER_EXC_TYP}


def test_argumentfehler_sind_generisch(client):
    r = client.post(f"/api/method/{REGISTRIERUNG}.submit_registrierung")

    assert r.status_code == 417, r.text
    assert _exc_werte(r.json()) == {GENERISCHER_EXC_TYP}


def test_unbekannte_methode_ist_generisch(client):
    r = client.get("/api/method/gibt.es.nicht")

    assert r.status_code == 404, r.text
    assert _exc_werte(r.json()) == {GENERISCHER_EXC_TYP}


def test_echter_name_steht_im_log(client, caplog):
    """S2 zweite Haelfte: der Klassename geht ins Log, nicht in die Antwort."""
    with caplog.at_level(logging.INFO, logger="diakronos_app.frappe_compat.router"):
        r = client.post("/api/method/fail_validation", json={"msg": "zu jung"})

    assert r.status_code == 417
    protokoll = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "ValidationError" in protokoll, protokoll
    assert "ValidationError" not in r.text


@pytest.mark.parametrize(
    "aufruf",
    [
        ("get", "/api/method/gibt.es.nicht", None),
        ("get", "/api/resource/GibtEsNicht", None),
        ("post", f"/api/method/{REGISTRIERUNG}.submit_registrierung", None),
        ("post", "/api/method/fail_validation", {"msg": "x"}),
    ],
)
def test_keine_internen_klassennamen_im_ganzen_body(client, aufruf):
    """Sammelwaechter: KEINE Antwort dieses Routers nennt eine interne Klasse."""
    methode, pfad, body = aufruf
    r = getattr(client, methode)(pfad, json=body) if body is not None else getattr(client, methode)(pfad)

    for name in INTERNE_NAMEN:
        assert name not in r.text, f"{pfad}: {name} in {r.text}"


# ── (S3) Methoden-Enumeration ueber den Status ────────────────────────────


def test_unbekannt_und_ungueltig_sehen_gleich_aus(client):
    """Traversal/unbekannt vs. bekannter Name ohne Argumente: kein Unterschied
    ueber die Antwortform hinaus, den ein Angreifer auswerten koennte."""
    unbekannt = client.post("/api/method/gibt.es.nicht")
    traversal = client.post("/api/method/..%2F..%2Fetc%2Fpasswd")

    assert unbekannt.status_code == traversal.status_code == 404
    assert unbekannt.json() == traversal.json()


def test_falscher_argumenttyp_wird_kein_500(client):
    """Ein falscher Typ ist ein ARGUMENTFEHLER, kein Serverfehler.

    Vorher lief z. B. `mitglied_id: 123` (int statt str) in den
    `except Exception`-Zweig und endete als 500 „Interner Fehler" — ein
    weiteres Unterscheidungsmerkmal und eine falsche Aussage ueber die Ursache.
    """
    r = client.post(
        "/api/method/diakronos.diakonos.api.mitglieder.get_mitglied_detail",
        json={"mitglied_id": 123},
    )

    assert r.status_code in (403, 417), r.text
    assert r.status_code != 500
    assert _exc_werte(r.json()) <= {GENERISCHER_EXC_TYP, "SessionExpired", "PermissionError"}
