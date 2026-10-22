"""OIDC-Transaktionsspeicher (Redis).

Zwischen der Weiterleitung zum Anbieter und der Rueckkehr muss der Server
``state``, ``nonce`` und ``code_verifier`` kennen — und zwar serverseitig, nicht
im Cookie (sonst koennte ein Angreifer sie setzen). Gespeichert wird unter dem
``state`` als Schluessel, mit kurzer TTL.

Der Speicher ist reine Datenschicht (wie `frappe_compat/sitzungen.py`) und wird
von den Tests ueber `_client` auf einen In-Memory-Stub gepatcht.
"""

from __future__ import annotations

import json
import secrets

from diakronos_app.settings import settings

__all__ = ["SCHLUESSEL_PRAEFIX", "ablegen", "entnehmen", "neuer_state"]

SCHLUESSEL_PRAEFIX = "diakronos:oidc-tx:"

# Kurze Lebensdauer: der Nutzer muss sich in dieser Zeit beim Anbieter
# anmelden. Grosszuegig genug fuer einen Consent-Bildschirm, kurz genug, dass
# ein abgebrochener Versuch nicht liegen bleibt.
_TTL_SEKUNDEN = 600


def neuer_state() -> str:
    """Ein frischer, nicht erratbarer `state` (CSRF-Schutz des Flows)."""
    return secrets.token_urlsafe(32)


def _client():
    """Redis-Client des Transaktionsspeichers (patchbar fuer Tests)."""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _key(state: str) -> str:
    return f"{SCHLUESSEL_PRAEFIX}{state}"


def _getdel(client, key: str) -> str | None:
    """Wert holen UND den Schluessel loeschen — atomar, mit Rueckfall.

    Der regulaere Weg ist ``GETDEL`` (Redis >= 6.2): in einem Kommando, also
    ohne Fenster fuer einen zweiten Leser. Fehlt die Kommandoform (aeltere
    Server, Test-Stubs ohne ``getdel``), wird auf ein ``PIPELINE`` mit
    ``GET`` + ``DELETE`` zurueckgefallen. Die Pipeline ist bei Redis
    standardmaessig eine MULTI/EXEC-Transaktion — ``GET`` und ``DELETE``
    laufen darin ebenfalls zusammen, nur ohne das Zwischenergebnis nach
    aussen. Ist auch das nicht verfuegbar, bleibt das ehrliche, nicht-atomare
    ``DELETE`` (dokumentierte Rest-Grenze) statt eines stillen Fehlers.
    """
    getdel = getattr(client, "getdel", None)
    if callable(getdel):
        wert = getdel(key)
        return wert if isinstance(wert, str) else None
    pipe = client.pipeline()
    pipe.get(key)
    pipe.delete(key)
    ergebnis = pipe.execute()
    wert = ergebnis[0] if ergebnis else None
    return wert if isinstance(wert, str) else None


def ablegen(
    state: str,
    nonce: str,
    code_verifier: str,
    ziel: str | None = None,
) -> None:
    """Legt Nonce und PKCE-Verifier unter dem `state` ab (TTL begrenzt).

    ``ziel`` (OP-CHOR-4/P0-4b): das relative Weiterleitungsziel nach der
    Rueckkehr. Es MUSS serverseitig liegen und nicht im Cookie/Query — sonst
    koennte ein Angreifer es setzen (Open Redirect) und es ginge beim
    Anbieter-Roundtrip ohnehin verloren. Schon geprueft (`_relatives_ziel`),
    trotzdem nur pfadrelative Werte, weil der Wert spaeter in einen
    `Location`-Header geht.
    """
    daten = json.dumps(
        {"nonce": nonce, "code_verifier": code_verifier, "ziel": ziel or ""}
    )
    _client().set(_key(state), daten, ex=_TTL_SEKUNDEN)


def entnehmen(state: str) -> dict | None:
    """Liest UND loescht die Transaktion zu `state` — in EINEM Schritt.

    Einmalverwendung: derselbe Code/`state` kann kein zweites Mal eingeloest
    werden. Entscheidend ist, dass Lesen und Loeschen **atomar** passieren:
    mit getrenntem ``GET`` und ``DELETE`` koennten zwei nebenlaeufige
    Rueckkehr-Requests einer Anmeldung denselben `state` beide als vorhanden
    lesen und damit denselben Autorisierungscode zweimal einloesen
    (Race Condition, Authorization-Code-Replay). ``GETDEL`` uebergibt das an
    Redis: nur der erste Aufruf erhaelt den Wert, jeder weitere ``None``.
    """
    if not state:
        return None
    client = _client()
    key = _key(state)
    raw = _getdel(client, key)
    if raw is None:
        return None
    try:
        daten = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return daten if isinstance(daten, dict) else None
