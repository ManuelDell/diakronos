"""Ratenbegrenzung der OEFFENTLICHEN Registrierung (Befund 1, P0-4b).

Die drei anonymen Endpunkte (`validate_token`, `submit_registrierung`,
`submit_gast`) und die oeffentliche Seite hatten KEINE Bremse: jeder Aufruf
loeste Datenbankabfragen aus, jedes Absenden legte eine Anmeldeanfrage an, und
damit liess sich die Admin-Warteschlange mit einem Skript fluten. Der Login hat
seit A1c1 eine Bremse (`frappe_compat.loginversuche`) — die Registrierung nicht.

Warum eine EIGENE Datenschicht und nicht die Loginbremse mitbenutzt wird:

  * Die Loginbremse sperrt ein **Konto** (E-Mail) und/oder eine Adresse und
    verhaengt eine wachsende Sperre (Backoff). Hier gibt es kein Konto — der
    Absender ist anonym, und der zu schuetzende Gegenstand ist der **Link**
    (ein einzelner Registrierungslink darf nicht durch Massenanmeldungen
    leerlaufen) sowie die **Adresse** (ein Skript darf die Warteschlange
    nicht fluten). Zwei Zaehler, dieselbe Bauform wie dort, aber getrennte
    Schwellen und Schluessel.
  * Eine Sperre waere hier zu grob: eine Gemeinde hat EINEN Anschluss
    (NAT/Proxy), hinter dem mehrere ehrliche Anmeldungen aus demselben
    Foyer kommen koennen. Ein **Fenster** ("hoechstens N je Stunde") bremst
    das Skript und laesst den Normalfall durch — genau die Abwaegung aus
    `werkzeuglimit_entsperren` (A1c6).

AUFBAU (Redis). Ein fester Zaehler je Fenster und Kennungsart:

    diakronos:reg-versuche:ip:<sha256>    -> "3"   (Absendeversuche je Adresse)
    diakronos:reg-versuche:link:<sha256>  -> "2"   (Absendeversuche je Link)
    diakronos:reg-valid:ip:<sha256>       -> "7"   (Tokenpruefungen je Adresse)

Die Schluessel tragen **keinen Klartext** — die Kennung (Adresse oder Link-Token)
laeuft durch denselben gesalzenen Hash wie die Loginbremse. Wer den Keyspace
liest, sieht keine Adressen und keine gueltigen Tokens.

FENSTER. `INCR` und `EXPIRE NX` laufen atomar in einer Redis-Transaktion.
Ein bestehender Ablauf bleibt unverändert; alte Schlüssel ohne TTL erhalten
wieder einen Ablauf. Dauerlast verlängert das feste Fenster nicht.

FAIL CLOSED. Bei Redis-Ausfall wird keine Anmeldung angenommen. Statt einer
internen Fehlermeldung erscheint ein verständlicher Hinweis zum späteren
Wiederholen. Die Schwellen kommen aus `settings` und koennen ausdruecklich
abgeschaltet werden (`*_max = 0` = unbegrenzt) — der Default ist die Grenze,
nicht das Nichts. Wer eine bestehende Installation hochfaehrt, bekommt die
Bremse also automatisch.

Eigene Adressen (Loopback, privat) werden — wie in der Loginbremse — NICHT
gezaehlt: hinter einem Reverse-Proxy waere die Adresse die des Proxies, und
eine Grenze darauf traefe jede Anmeldung der Gemeinde. Der Link-Zaehler wirkt
dort weiterhin. Die Regel sitzt an EINER Stelle (`_zaehle_ip`).
"""

from __future__ import annotations

import hashlib

from diakronos_app.frappe_compat.loginversuche import _ist_eigene_adresse
from diakronos_app.ip_adressen import parse_ip
from diakronos_app.settings import settings

__all__ = [
    "SCHLUESSEL_PRAEFIX",
    "pruefe",
    "zaehle_validierung",
    "zaehler_stand",
]

# Eigener Namensraum, damit die Registrierungsbremse weder mit den
# Loginzaehlern noch mit den Sperren oder den Werkzeug-Budgets kollidiert.
SCHLUESSEL_PRAEFIX = "diakronos:reg-versuche:"

# Praefix der Token-Pruefungen (GET der oeffentlichen Seite / validate_token).
# Getrennt vom Absende-Zaehler: ein Aufruf der Seite darf die Absende-Grenze
# nicht verbrauchen und umgekehrt.
VALIDIERUNG_PRAEFIX = "diakronos:reg-valid:"


def _client():
    """Redis-Client (patchbar fuer Tests, wie `loginversuche._client`)."""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _hash(rohdaten: str) -> str:
    """Schluessel-Anteil aus `rohdaten` — ohne Klartext im Redis-Key.

    Derselbe gesalzene SHA-256 wie in der Loginbremse (`settings.secret_key`).
    Eine Adresse ist kein Geheimnis, ein gueltiger Registrierungstoken aber
    schon — er darf nicht im Keyspace stehen.
    """
    salz = str(getattr(settings, "secret_key", "") or "")
    return hashlib.sha256(f"{salz}|{rohdaten}".encode()).hexdigest()[:32]


def _max_ip() -> int:
    return max(0, int(getattr(settings, "registrierung_max_ip", 10)))


def _max_link() -> int:
    return max(0, int(getattr(settings, "registrierung_max_link", 20)))


def _max_valid() -> int:
    return max(0, int(getattr(settings, "registrierung_max_validierung", 60)))


def _fenster() -> int:
    return max(1, int(getattr(settings, "registrierung_fenster_sekunden", 3600)))


def _zaehle_ip(client, ip: str | None) -> bool:
    """Ist die Adresse zaehlbar (keine eigene Infrastruktur, gueltig)?

    Die eine Stelle, an der die Proxy-/Infrastruktur-Regel sitzt — kein
    Aufrufer kann sie umgehen. Ist keine Adresse bekannt oder ist sie privat,
    traegt der Link-Zaehler die Bremse allein.
    """
    adresse = parse_ip(ip)
    if adresse is None:
        return False
    return not _ist_eigene_adresse(str(adresse))


def _zaehle(client, key: str, grenze: int) -> bool:
    """Ein Fenster-Zaehler: True, wenn der Versuch noch erlaubt ist.

    `INCR` und `EXPIRE NX` laufen in einer Redis-Transaktion. NX setzt den
    Ablauf nur, wenn noch keiner besteht (Redis >= 7, wie im Compose-Stack).
    Das repariert auch alte Schlüssel ohne TTL, ohne feste Fenster zu verlängern.
    Ist `grenze <= 0`, ist die Pruefung ausdruecklich aus.
    """
    if grenze <= 0:
        return True
    from redis.exceptions import RedisError
    from diakronos_app.frappe_compat.exceptions import ValidationError

    try:
        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, _fenster(), nx=True)
        anzahl, _ = pipe.execute()
    except RedisError:
        # Fail closed: nie ungeprüft schreiben, aber keine internen Adressen
        # oder Verbindungstexte an öffentliche Besucher weiterreichen.
        raise ValidationError(
            "Anmeldungen können gerade nicht verarbeitet werden. "
            "Bitte versuche es später erneut."
        ) from None
    return int(anzahl) <= grenze


def pruefe(ip: str | None, token: str | None = None, client=None) -> tuple[bool, str]:
    """Prueft die Bremse fuer ein ABSENDEN. **ABNAHMESCHNITTSTELLE.**

    Rueckgabe `(erlaubt, grund)` — `grund` ist `"ip"` oder `"link"` und dient
    der internen Diagnose/Logzeile, NICHT der Anzeige (nach aussen wird daraus
    ein einheitlicher, verstaendlicher Satz — siehe `fehlermeldung`).

    Zählt Adresse und/oder einen bereits geprüften Link. Bei öffentlichen
    Absendewegen prüft api/registrierung.py zuerst nur die Adresse, validiert
    dann den Token und zählt erst danach den Link. Ungeprüfte fremde Tokens
    dürfen hier nicht als Link übergeben werden.
    """
    client = client or _client()
    erlaubt = True
    grund = ""

    if _zaehle_ip(client, ip):
        ok_ip = _zaehle(client, f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(parse_ip(ip)))}", _max_ip())
        if not ok_ip:
            erlaubt, grund = False, "ip"

    if token and token.strip():
        ok_link = _zaehle(
            client, f"{SCHLUESSEL_PRAEFIX}link:{_hash(token.strip())}", _max_link()
        )
        # Die Adressgrenze hat Vorrang in der Meldung; fachlich ist es egal,
        # welche zuerst greift — gezaehlt wird trotzdem beides.
        if not ok_link and erlaubt:
            erlaubt, grund = False, "link"

    return erlaubt, grund


def zaehle_validierung(ip: str | None, client=None) -> bool:
    """Bremse fuer die TOKENPRUEFUNG (Seitenaufruf / `validate_token`).

    Eigener Zaehler mit eigener, hoeherer Grenze: ein Besucher laedt die Seite
    mehrfach (Reload, Weiterleitung), ein Skript dagegen soll die DB nicht mit
    Tokenabfragen fluten. Rueckgabe True = erlaubt.
    """
    client = client or _client()
    if not _zaehle_ip(client, ip):
        return True
    return _zaehle(
        client, f"{VALIDIERUNG_PRAEFIX}ip:{_hash(str(parse_ip(ip)))}", _max_valid()
    )


def zaehler_stand(ip: str | None, token: str | None = None, client=None) -> dict[str, int]:
    """Liest die Zaehler OHNE sie zu veraendern. Fuer Tests/Diagnose."""
    client = client or _client()
    stand = {"ip": 0, "link": 0, "validierung": 0}
    adresse = parse_ip(ip)
    if _zaehle_ip(client, ip) and adresse is not None:
        stand["ip"] = int(client.get(f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(adresse))}") or 0)
        stand["validierung"] = int(
            client.get(f"{VALIDIERUNG_PRAEFIX}ip:{_hash(str(adresse))}") or 0
        )
    if token and token.strip():
        stand["link"] = int(
            client.get(f"{SCHLUESSEL_PRAEFIX}link:{_hash(token.strip())}") or 0
        )
    return stand


def fehlermeldung() -> str:
    """Verstaendlicher Satz fuer einen gebremsten Versuch (kein Fachjargon).

    Bewusst dieselbe Meldung fuer Adress- und Link-Grenze: welcher Zaehler
    gegriffen hat, ist eine interne Diagnose und geht einen anonymen Absender
    nichts an (er koennte daraus ableiten, wann er es erneut versuchen darf).
    """
    return (
        "Es sind gerade zu viele Anmeldungen eingegangen. Bitte versuche es "
        "in ein paar Minuten erneut."
    )
