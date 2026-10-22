"""LOGIN-1: kurzlebiger Flash-Cookie fuer die Anmeldemaske.

Problem: Ein fehlgeschlagener **Formular**-Login wurde im Browser als roher
JSON-Block angezeigt (401 auf `/api/method/login`). Die Maske muss wieder
erscheinen, und sie soll die zuletzt eingegebene E-Mail vorausfuellen, ohne
sie in die URL zu schreiben (URLs landen im Verlauf, in Logs und im
`Referer`).

Dafuer gibt es genau EINEN Cookie, `dk_login_flash`, mit einem signierten,
kurzlebigen Wert:

    <abgelaufen>:<email_b64>:<hmac>

  * `abgelaufen` — Unix-Zeit in Sekunden. Nicht manipulierbar, weil im MAC.
  * `email_b64`  — die E-Mail als url-sicheres Base64 (nur ASCII im Cookie).
  * `hmac`       — HMAC-SHA256 ueber ``<abgelaufen>:<email_b64>`` mit
                   `settings.secret_key`, hex.

Warum signiert und nicht einfach signaturlos: der Cookie ist `Path=/login`,
also ausschliesslich fuer die Anmeldeseite — aber ein Angreifer mit Zugriff
auf den Browser (oder eine fremde Subdomain, die Cookies setzen kann) darf
darueber **keinen** Text auf die Anmeldeseite schieben. Die E-Mail wird beim
Anzeigen uebrigens zusaetzlich HTML-escaped; der MAC verhindert schon, dass
ueberhaupt fremder Inhalt durchkommt.

Der Cookie wird IMMER gesetzt, auch wenn keine E-Mail vorliegt — sonst waere
"Meldung ohne E-Mail" (leeres Feld) von "Meldung mit E-Mail" (vorbefuellt) zu
unterscheiden, und die Fehlschlagarten waeren nicht mehr gleich. Er ist
`HttpOnly`, `SameSite=Lax`, `Path=/login` und laeuft nach
`FLASH_TTL_SEKUNDEN` ab; die Maske loescht ihn beim Anzeigen (Einmal-Gebrauch,
sonst stuende die Meldung nach einem Neuladen weiter da).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time

from starlette.responses import Response

__all__ = [
    "COOKIE_NAME",
    "FLASH_TTL_SEKUNDEN",
    "setze_flash",
    "lese_flash",
    "loesche_flash",
    "MELDUNG_FALSCH",
    "MELDUNG_LEER",
]

COOKIE_NAME = "dk_login_flash"

#: 60 Sekunden reichen fuer den Sprung 401 -> Maske. Kurz, weil der Cookie
#: die E-Mail eines Menschen enthaelt (wenngleich nur fuer seine eigene
#: Anmeldung gedacht und an den Browser gebunden).
FLASH_TTL_SEKUNDEN = 60

#: Ein Fehlschlag — identisch fuer unbekannt, falsches Passwort, deaktiviert
#: und gesperrt (siehe `api/auth.py::UNGUELTIGE_ANMELDEDATEN`).
MELDUNG_FALSCH = "E-Mail-Adresse oder Passwort ist falsch."

#: Beide Felder leer: kein "falsches Passwort", sondern ein Hinweis, was fehlt.
#: Diese Meldung wird NIE fuer einen benannten Fehlversuch benutzt und ist
#: damit keine Auskunft ueber Konten.
MELDUNG_LEER = "Bitte gib deine E-Mail-Adresse und dein Passwort ein."

#: Pfad des Cookies — er soll NUR bei der Anmeldeseite mitgehen.
FLASH_PATH = "/login"


def _signatur(abgelaufen: str, email_b64: str) -> str:
    """HMAC-SHA256 ueber Nutzlast + Ablauf, Schluessel aus `secret_key`."""
    from diakronos_app.settings import settings

    schluessel = str(getattr(settings, "secret_key", "") or "").encode("utf-8")
    return hmac.new(
        schluessel, f"{abgelaufen}:{email_b64}".encode("ascii"), hashlib.sha256
    ).hexdigest()


def _email_b64(email: str) -> str:
    """E-Mail URL-sicher kodieren (Cookies tragen nur ASCII)."""
    return base64.urlsafe_b64encode(email.encode("utf-8")).decode("ascii").rstrip("=")


def _email_aus_b64(text: str) -> str | None:
    """Umkehrung von `_email_b64`; `None` bei unbrauchbarem Inhalt."""
    try:
        roh = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        return roh.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _secure_flag() -> bool:
    """Derselbe Schalter wie beim `sid`-Cookie (`api/auth.py::_secure_flag`)."""
    from diakronos_app.api.auth import _secure_flag as _sid_secure

    return _sid_secure()


def setze_flash(response: Response, email: str, *, leer: bool = False) -> None:
    """Setzt den Flash-Cookie. `email` darf leer sein (dann nur die Meldung).

    Der dritte Teil der Nutzlast (Art der Meldung) ist bewusst NICHT dabei:
    es gibt genau zwei Faelle, und `leer` wird aus der leeren E-Mail
    abgeleitet. Damit kann ein manipulierter Cookie keine andere Meldung
    erzeugen als die zwei vorgesehenen.
    """
    abgelaufen = str(int(time.time()) + FLASH_TTL_SEKUNDEN)
    email_b64 = _email_b64(email or "")
    wert = f"{abgelaufen}:{email_b64}:{_signatur(abgelaufen, email_b64)}"
    response.set_cookie(
        key=COOKIE_NAME,
        value=wert,
        httponly=True,
        samesite="lax",
        path=FLASH_PATH,
        secure=_secure_flag(),
        max_age=FLASH_TTL_SEKUNDEN,
    )


def loesche_flash(response: Response) -> None:
    """Loescht den Flash — die Maske ruft das bei jedem Anzeigen auf."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        path=FLASH_PATH,
        secure=_secure_flag(),
    )


def lese_flash(cookies) -> tuple[str, bool] | None:
    """Liest und prueft den Flash.

    Rueckgabe ``(email, leer)`` oder ``None``, wenn kein/kein gueltiger
    Cookie da ist (abgelaufen, Signatur falsch, Unsinn). `None` heisst fuer
    die Maske: normaler Aufruf ohne Meldung.
    """
    roh = ""
    if cookies is not None:
        try:
            roh = str(cookies.get(COOKIE_NAME) or "")
        except Exception:  # noqa: BLE001 — kein Cookie-Jar -> kein Flash
            roh = ""
    if not roh:
        return None
    teile = roh.split(":")
    if len(teile) != 3:
        return None
    abgelaufen, email_b64, signatur = teile
    if not abgelaufen.isdigit():
        return None
    if not hmac.compare_digest(_signatur(abgelaufen, email_b64), signatur):
        return None
    if int(abgelaufen) < int(time.time()):
        return None
    email = _email_aus_b64(email_b64)
    if email is None:
        return None
    # Steuerzeichen koennen NaN umgehen, aber nicht in ein HTML-Feld gehoeren.
    email = "".join(c for c in email if c >= " " and c != "\x7f")
    return email, not email
