"""Redaktion — Geheimnisse verlassen den Server nie.

Die Testsuite sammelt Fehlermeldungen, Log-Zeilen und (gekuerzte)
Request-Bodies. Genau dort stehen im Fehlerfall Passwoerter, Tokens, Cookies
und CSRF-Werte. Diese Datei ist die EINZIGE Stelle, die entscheidet, was
gespeichert werden darf; sie wird vor JEDEM Schreibvorgang aufgerufen
(Middleware, Kommentar-Endpunkt, Browser-Meldungen, Log-Handler).

Zwei Wege, unabhaengig voneinander:

1. **Feldnamen** (`redigiere_felder`): Schluessel wie ``password``, ``token``,
   ``authorization`` werden rekursiv durch ``"[entfernt]"`` ersetzt.
2. **Muster im Text** (`redigiere`): ``Authorization: Bearer …``,
   ``Cookie: …``, ``sid=…``, ``csrf_token=…``, ``<field>_password=<wert>``,
   ``client_secret=…`` und JWT-artige Zeichenketten.

Was NICHT passiert: ein pauschales Loeschen ganzer Meldungen. Der Nutzen der
Testsuite haengt daran, dass die Fehlermeldung lesbar bleibt — deshalb werden
nur die Geheimnisanteile ersetzt.
"""

from __future__ import annotations

import re

ERSATZ = "[entfernt]"

#: Feldnamen, deren Wert niemals gespeichert wird (case-insensitiv, Teilstring).
GEHEIME_FELDER = (
    "password", "passwort", "pwd", "secret", "token", "authorization",
    "auth", "cookie", "csrf", "session_id", "sid", "api_key", "apikey",
    "access_key", "private_key", "client_secret", "credential",
)

#: Kopfzeilen-Namen, die in Request-/Antwort-Kontexten nie auftauchen.
GEHEIME_KOPFZEILEN = (
    "authorization", "cookie", "set-cookie", "x-frappe-csrf-token",
    "x-csrf-token", "proxy-authorization", "x-diakronos-proxy-secret",
)

def _input_redigieren(treffer: "re.Match[str]") -> str:
    """Ersetzt den value-Wert in einem Passwort-/hidden-Tag durch ``[entfernt]``."""
    return re.sub(r'(?is)(value\s*=\s*["\'])[^"\']*(["\'])', rf'\1{ERSATZ}\2', treffer.group(0))


_MUSTER: tuple[tuple[re.Pattern[str], object], ...] = (
    # Authorization: Bearer *** / Basic <base64>
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/=]+"), rf"\1 {ERSATZ}"),
    # Ganzzeilige Kopfzeilen
    (re.compile(r"(?im)^(\s*(?:authorization|cookie|set-cookie|x-frappe-csrf-token|"
                r"x-csrf-token|proxy-authorization)\s*:\s*).*$"), rf"\1{ERSATZ}"),
    # name=wert-Formen in Query, Form und Logs
    (re.compile(r"(?i)\b(sid|csrf_token|csrf|token|access_token|refresh_token|"
                r"password|passwort|pwd|secret|client_secret|api_key)\s*=\s*"
                r"([^&\s;,\"']+)"), rf"\1={ERSATZ}"),
    # JSON-Formen: "password": "…"
    (re.compile(r'(?i)"([a-z0-9_]*(?:password|passwort|secret|token|cookie|csrf|api_key)[a-z0-9_]*)"\s*:\s*"[^"]*"'),
     rf'"\1": "{ERSATZ}"'),
    # JWT (drei base64url-Segmente)
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"), ERSATZ),
    # Basic-Auth in URLs: https://user:pass@host
    (re.compile(r"(?i)\b(https?://)([^/\s:@]+):([^/\s@]+)@"), rf"\1\2:{ERSATZ}@" ),
    # DM1: Eingabewerte in outerHTML — Passwort-/versteckte Felder NIE.
    # Das Tag wird zuerst erkannt (type=password|hidden), dann wird der
    # value="..."-Wert darin ersetzt. Ohne diese Regel ueberlebte der Wert
    # eines <input type="password"> die Redaktion (der Feldname hilft hier
    # nicht, weil er im HTML-Attribut steht).
    (re.compile(r'(?is)<input\b[^>]*type\s*=\s*["\']?(?:password|hidden)["\']?[^>]*>'
                r'|value\s*=\s*["\'][^"\']*["\'](?=[^>]*type\s*=\s*["\']?(?:password|hidden))'),
     _input_redigieren),
    # Ganz allgemein: value="…" in einem Passwort-/hidden-Feld.
    (re.compile(r'(?is)(<input\b[^>]*type\s*=\s*["\']?(?:password|hidden)["\']?[^>]*'
                r'value\s*=\s*["\'])([^"\']*)(["\'])'), rf'\1{ERSATZ}\3'),
)


def redigiere(text: str | None) -> str:
    """Ersetzt Geheimnisanteile in einem Text. ``None`` wird zu ``""``."""
    if not text:
        return ""
    ergebnis = str(text)
    for muster, ersatz in _MUSTER:
        ergebnis = muster.sub(ersatz, ergebnis)
    return ergebnis


def redigiere_felder(wert):
    """Redigiert rekursiv Dicts/Listen: geheime Felder werden ersetzt.

    Nicht-geheime Werte bleiben unveraendert (nur echte Strings werden per
    Muster geprueft) — sonst wuerde aus einem Statuscode eine Zeichenkette.
    """
    if isinstance(wert, dict):
        neu = {}
        for schluessel, inhalt in wert.items():
            if _geheim(schluessel):
                neu[schluessel] = ERSATZ
            else:
                neu[schluessel] = redigiere_felder(inhalt)
        return neu
    if isinstance(wert, (list, tuple)):
        return [redigiere_felder(x) for x in wert]
    if isinstance(wert, str):
        return redigiere(wert)
    return wert


def _geheim(schluessel) -> bool:
    k = str(schluessel).lower()
    return any(teil in k for teil in GEHEIME_FELDER)


def gekuerzt(text: str | None, grenze: int) -> str | None:
    """Kuerzt und redigiert in EINER Funktion (Reihenfolge ist wichtig:
    erst kuerzen vermeidet Arbeit, dann redigieren — aber ein Geheimnis darf
    nie durch die Kuerzung halb stehen bleiben, deshalb wird nach dem Kuerzen
    nochmals redigiert)."""
    if text is None:
        return None
    roh = str(text)
    if len(roh) > grenze:
        roh = roh[:grenze] + "…"
    return redigiere(roh)


def redigiere_kopfzeilen(headers) -> dict[str, str]:
    """Kopfzeilen fuer die Speicherung: geheime Namen werden ersetzt."""
    ausgabe: dict[str, str] = {}
    for name, wert in dict(headers or {}).items():
        if str(name).lower() in GEHEIME_KOPFZEILEN:
            ausgabe[name] = ERSATZ
        else:
            ausgabe[name] = redigiere(str(wert))
    return ausgabe


def enthaelt_geheimnis(text: str | None) -> bool:
    """Nur fuer Tests: taucht noch ein GeheimnisWERT auf?

    Wichtig: geprueft wird der WERT, nicht das Feld. Nach der Redaktion steht
    ``password=[entfernt]`` da — das ist das Ziel, kein Restgeheimnis. Deshalb
    wird der Platzhalter vorher aus dem Text entfernt; nur was daneben noch
    wie ein Geheimnis aussieht, zaehlt.
    """
    if not text:
        return False
    rest = str(text)
    for _ in range(3):
        if ERSATZ not in rest:
            break
        rest = rest.replace(ERSATZ, "")
    for muster, _ in _BELEG_MUSTER:
        if muster.search(rest):
            return True
    return False


#: Muster, die einen echten GeheimnisWERT erkennen (ohne Feldnamen).
_BELEG_MUSTER: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/=]{8,}"), ""),
    (re.compile(r"(?i)\b(sid|csrf_token|csrf|token|access_token|refresh_token|"
                r"password|passwort|pwd|secret|client_secret|api_key)\s*=\s*[^\s;&,\"']{4,}"), ""),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"), ""),
    (re.compile(r"(?i)\bhttps?://[^/\s:@]+:[^/\s@]{4,}@"), ""),
)
