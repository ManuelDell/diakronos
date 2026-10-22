"""Serverseitiger Sitzungs-Store (Redis) — Karte A1b1.

Warum Redis und kein signiertes Cookie: eine Sitzung muss WIDERRUFBAR sein.
Logout auf einem gemeinsam genutzten Gemeinde-Rechner muss die Sitzung
wirklich toeten, und "alle Sitzungen beenden" muss moeglich sein. Ein
signiertes Cookie kann das nicht. Redis liegt ohnehin im Stack und teilt sich
ueber mehrere Worker-Prozesse.

Schluesselraum: `<prefix><sid>` -> JSON `{"user": ..., "csrf_token": ...}`.
`sid` und `csrf_token` sind je 56 Hex-Zeichen (`secrets.token_hex(28)`) —
dieselbe Laenge wie `frappe.generate_hash()`.

Diese Datei ist reine Datenschicht: sie aendert NICHT, wer eingeloggt ist.
Die Umschaltung macht Karte A1b2.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from diakronos_app.settings import settings

__all__ = [
    "SCHLUESSEL_PRAEFIX",
    "anlegen",
    "lesen",
    "verlaengern",
    "loeschen",
    "loesche_alle_von",
    "benutzer_index_key",
    "neuer_token",
]

# Eigener Praefix, damit der Store nicht mit anderen Redis-Nutzern kollidiert
# (RQ-Queue, Scheduler, Cache).
SCHLUESSEL_PRAEFIX = "diakronos:sitzung:"

# Pro Benutzer eine Menge offener `sid` — Grundlage fuer `loesche_alle_von`.
_BENUTZER_PRAEFIX = "diakronos:sitzungen:"

# 28 Byte -> 56 Hex, wie `frappe.generate_hash()`.
_TOKEN_BYTES = 28


def neuer_token() -> str:
    """56 Hex-Zeichen aus dem CSPRNG (`secrets`)."""
    return secrets.token_hex(_TOKEN_BYTES)


def benutzer_index_key(user: str) -> str:
    """Redis-Key der `sid`-Menge eines Benutzers."""
    return f"{_BENUTZER_PRAEFIX}{user}"


def _neuer_client():
    """Baut einen neuen Redis-Client aus `settings.redis_url`.

    Bewusst NICHT der Healthcheck-Client aus `main.py`: der setzt ein
    Zeitbudget fuer Verbindungstests, hier soll normal gearbeitet werden.

    Tests patchen `_client` (nicht diese Funktion) auf einen In-Memory-Stub —
    siehe `tests/conftest.py`.
    """
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _client():
    """Liefert den Redis-Client der Sitzungs-Schicht (patchbar fuer Tests)."""
    return _neuer_client()


def _ttl() -> int:
    return int(settings.session_ttl_seconds)


def _key(sid: str) -> str:
    return f"{SCHLUESSEL_PRAEFIX}{sid}"


def anlegen(user: str, *, sso: bool = False) -> tuple[str, str]:
    """Legt eine Sitzung an. Rueckgabe `(sid, csrf_token)`.

    Der CSRF-Token liegt im Server-Zustand (Synchronizer-Token-Muster), nicht
    in einem Cookie — die SPA sendet nur den Header `X-Frappe-CSRF-Token`.
    """
    sid = neuer_token()
    csrf_token = neuer_token()
    daten: dict[str, Any] = {"user": user, "csrf_token": csrf_token}
    # Nur die geprüften OIDC-/Forward-Auth-Wege setzen diese Herkunft.
    # Ein lokales Startpasswort darf keine vollwertige Sitzung erzeugen;
    # ein bestätigter Anbieter-Login benötigt dagegen kein lokales Passwort.
    if sso:
        daten["sso"] = True
    payload = json.dumps(daten)
    client = _client()
    pipe = client.pipeline()
    pipe.set(_key(sid), payload, ex=_ttl())
    index = benutzer_index_key(user)
    pipe.sadd(index, sid)
    pipe.expire(index, _ttl())
    pipe.execute()
    return sid, csrf_token


def lesen(sid: str) -> dict[str, Any] | None:
    """Liest eine Sitzung. `None`, wenn unbekannt oder abgelaufen."""
    if not sid:
        return None
    raw = _client().get(_key(sid))
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        # Beschaedigter Eintrag ist wie kein Eintrag.
        return None
    return data if isinstance(data, dict) else None


def verlaengern(sid: str) -> bool:
    """Setzt die TTL einer bestehenden Sitzung neu. False, wenn sie weg ist."""
    if not sid:
        return False
    client = _client()
    if not client.exists(_key(sid)):
        return False
    client.expire(_key(sid), _ttl())
    data = lesen(sid)
    if data and data.get("user"):
        client.expire(benutzer_index_key(str(data["user"])), _ttl())
    return True


def loeschen(sid: str) -> bool:
    """Loescht GENAU eine Sitzung (Logout). True, wenn es sie gab."""
    if not sid:
        return False
    client = _client()
    data = lesen(sid)
    removed = bool(client.delete(_key(sid)))
    if data and data.get("user"):
        client.srem(benutzer_index_key(str(data["user"])), sid)
    return removed


def loesche_alle_von(user: str) -> int:
    """Loescht alle Sitzungen eines Benutzers. Rueckgabe: Anzahl geloeschter Sitzungen.

    Raeumt auch verwaiste `sid` aus dem Benutzer-Index, die im Store schon
    abgelaufen sind — der Index ist eine Beschleunigung, keine Wahrheit.
    """
    client = _client()
    index = benutzer_index_key(user)
    sids = client.smembers(index) or set()
    vergangen = [s for s in sids if not client.exists(_key(str(s)))]
    zu_loeschen = [s for s in sids if s not in vergangen]
    deleted = 0
    for sid in zu_loeschen:
        deleted += int(bool(client.delete(_key(str(sid)))))
    client.delete(index)
    return deleted
