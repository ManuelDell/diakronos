"""SEC-4 — der Token der Anmeldemaske (ohne Sitzung, ohne Redis).

Warum es dieses Modul gibt: Die Herkunftspruefung des Logins
(`api/auth._herkunft_ist_eigen`) braucht einen Nachweis, dass ein
Anmeldeformular von DIESEM Server stammt. Frueher lieferte den die
`Referer`-Kopfzeile — seit `Referrer-Policy: no-referrer` (SEC-4) fehlt sie
in jeder Anfrage dieses Stacks. Im echten Browser (Wegwerf-Stack,
2026-10-29) fuehrte das dazu, dass die RICHTIGE Anmeldung nach einer
Umleitung als „fremde Herkunft“ abgewiesen wurde.

Der Token kann NICHT an einer Server-Sitzung haengen: die Anmeldemaske wird
genau dann gebraucht, wenn noch niemand angemeldet ist, und eine eigens dafuer
angelegte Sitzung verwirft die `SessionMiddleware` sofort wieder (Sitzungen
geloeschter oder deaktivierter Konten). Deshalb ist der Token stattdessen
**signiert**: ``<zeit>:<hmac_sha256(zeit, SECRET_KEY)>``.

Eigenschaften:

* nur mit dem Server-Schluessel erzeugbar (kein Raten, kein Faelschen),
* laeuft nach :data:`FELD_GUELTIG_SEKUNDEN` ab (das Formular steht selten
  laenger offen; wer laenger braucht, laedt die Maske neu),
* zustandslos — kein Redis, keine Datenbank, kein Speicher pro Aufruf.

Er ist ein NACHTRAG zur Herkunftspruefung, kein Ersatz: `Origin`,
`Sec-Fetch-Site` und der Login-CSRF-Schutz der Sitzung bleiben, wie sie sind.
"""

from __future__ import annotations

import hashlib
import hmac
import time

#: Wie lange ein Token der Anmeldemaske gilt (Sekunden).
FELD_GUELTIG_SEKUNDEN = 60 * 60 * 12

#: Praefix im signierten Text — ein spaeterer zweiter Zweck (z.B. „Passwort
#: vergessen“) bekommt ein eigenes Praefix und kann diesen Token nicht nutzen.
_ZWECK = b"diakronos-anmeldemaske-v1"


def _schluessel() -> bytes:
    from diakronos_app.settings import settings

    schluessel = str(getattr(settings, "secret_key", "") or "")
    if not schluessel:
        # Ohne Schluessel wird NICHT mit einem Ersatzwert signiert: ein
        # allgemein bekannter Ersatzwert waere ein Token, den jeder nachbaut.
        raise RuntimeError("SECRET_KEY fehlt; Masken-Token nicht signierbar")
    return schluessel.encode("utf-8")


def _signatur(zeit: str) -> str:
    return hmac.new(_schluessel(), _ZWECK + b":" + zeit.encode("ascii"), hashlib.sha256).hexdigest()


def erzeuge_token(jetzt: int | None = None) -> str:
    """Erzeugt den Token fuer das Formular (`<zeit>:<signatur>`)."""
    zeit = str(int(time.time() if jetzt is None else jetzt))
    return f"{zeit}:{_signatur(zeit)}"


def token_ist_gueltig(token: str, jetzt: int | None = None) -> bool:
    """True, wenn der Token von uns stammt und nicht abgelaufen ist.

    Jeder unerwartete Zustand (leer, kein Doppelpunkt, keine Zahl, falsche
    Signatur, zu alt, Schluessel fehlt) ist ``False`` — fail closed.
    """
    if not token or ":" not in token:
        return False
    zeit_teil, _, signatur = token.partition(":")
    if not zeit_teil.isdigit():
        return False
    try:
        erwartet = _signatur(zeit_teil)
    except RuntimeError:
        return False
    if not hmac.compare_digest(erwartet, signatur):
        return False
    ausgestellt = int(zeit_teil)
    jetzt = int(time.time() if jetzt is None else jetzt)
    alter = jetzt - ausgestellt
    # Negatives Alter = Zeit in der Zukunft (verstellte Uhr, fremder Wert).
    return 0 <= alter <= FELD_GUELTIG_SEKUNDEN
