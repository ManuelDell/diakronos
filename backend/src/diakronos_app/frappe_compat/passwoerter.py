"""Passwort-Verifikation — Frappe-Hashes UND Argon2 unter einer Schnittstelle.

Hintergrund (Karte A1a): Frappe legt Login-Passwoerter als `pbkdf2-sha256`-
Hashes in `__Auth` ab (`doctype='User'`, `fieldname='password'`,
`encrypted=0`). Diese Hashes werden 1:1 uebernommen und muessen hier
verifiziert werden koennen. Fuer NEU gesetzte Passwoerter wird Argon2
verwendet (`argon2-cffi`, bereits im Image) — der staerkere Algorithmus.

Es gibt bewusst keine `passlib`-Abhaengigkeit: der Frappe-Verifier unten ist
20 Zeilen stdlib. Er ist gegen echtes `passlib` gegengeprueft (Umlaute,
200 Zeichen, Leerstring). `pwdlib` war nur eine Mitnahme von
`fastapi-users` (dort auf `==0.2.1` gepinnt) und faellt mit dessen Entfernung
weg. `argon2-cffi` ist eine direkte Abhaengigkeit und wird direkt genutzt.

Diese Datei ist reine Datenschicht — sie aendert NICHT, wer eingeloggt ist.
Die Umschaltung macht Karte A1b.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

__all__ = [
    "pruefe",
    "pruefe_frappe_hash",
    "neuer_hash",
    "muss_neu_gehasht_werden",
]

FRAPPE_PRAEFIX = "$pbkdf2-sha256$"
ARGON2_PRAEFIX = "$argon2"


def _ab64(s: str) -> bytes:
    """Dekodiert passlib-"adapted base64".

    WICHTIG: das Alphabet ist NICHT vollstaendig permutiert. Nur `+` ist
    durch `.` ersetzt, das Padding entfaellt. Eine "vollstaendige"
    Uebersetzungstabelle wirkt plausibel und lehnt das RICHTIGE Passwort ab —
    dieser Fehler wurde beim Bauen dieser Karte gemacht und gemessen gefunden.
    """
    return base64.b64decode(s.replace(".", "+") + "=" * (-len(s) % 4))


def pruefe_frappe_hash(passwort: str, hash_str: str) -> bool:
    """Verifiziert ein Passwort gegen einen Frappe-`pbkdf2-sha256`-Hash.

    Erwartetes Format: `$pbkdf2-sha256$<runden>$<salt>$<digest>`.
    """
    try:
        _, schema, runden, salt, digest = hash_str.split("$")
    except (ValueError, AttributeError):
        return False
    if schema != "pbkdf2-sha256":
        return False
    try:
        erwartet = _ab64(digest)
        berechnet = hashlib.pbkdf2_hmac(
            "sha256",
            passwort.encode("utf-8"),
            _ab64(salt),
            int(runden),
            dklen=len(erwartet),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(berechnet, erwartet)


def _argon2_hasher():
    """Argon2-Hasher direkt aus `argon2-cffi`.

    Gemessen: `pwdlib` stand nie als eigene Abhaengigkeit im Projekt, es kam
    ausschliesslich ueber `fastapi-users` herein (`pwdlib[argon2,bcrypt]==0.2.1`)
    und ist mit dessen Entfernung weg. `argon2-cffi` ist direkte Abhaengigkeit
    und ohnehin der Hasher unter `pwdlib` — also direkt nutzen, ohne
    Zwischenschicht. Der Default (`argon2id`, m=65536, t=3, p=4) ist zeitgemaess.
    """
    from argon2 import PasswordHasher

    return PasswordHasher()


def neuer_hash(passwort: str) -> str:
    """Erzeugt einen neuen Argon2-Hash fuer ein Klartextpasswort.

    Wird nur fuer NEU gesetzte Passwoerter benutzt; die importierten
    Frappe-Hashes bleiben unangetastet, bis der Benutzer sich das naechste
    Mal erfolgreich anmeldet (A1b hebt dann per `muss_neu_gehasht_werden`).
    """
    return _argon2_hasher().hash(passwort)


def _pruefe_argon2(passwort: str, hash_str: str) -> bool:
    from argon2.exceptions import InvalidHashError, VerificationError

    try:
        return _argon2_hasher().verify(hash_str, passwort)
    except (VerificationError, InvalidHashError):
        # VerificationError umfasst VerifyMismatchError, VerificationError,
        # InvalidHashError in aelteren Versionen — hier explizit beide.
        return False


def pruefe(passwort: str, hash_str: str) -> bool:
    """Die eine oeffentliche Funktion: erkennt BEIDE Formate am Praefix.

    - `$pbkdf2-sha256$...` -> Frappe-Hash (stdlib-Verifier)
    - `$argon2...`         -> Argon2 (argon2-cffi)
    Alles andere (leer, None-artig, unbekanntes Schema) -> False.
    """
    if not hash_str:
        return False
    if hash_str.startswith(FRAPPE_PRAEFIX):
        return pruefe_frappe_hash(passwort, hash_str)
    if hash_str.startswith(ARGON2_PRAEFIX):
        return _pruefe_argon2(passwort, hash_str)
    return False


def muss_neu_gehasht_werden(hash_str: str) -> bool:
    """True, wenn der Hash beim naechsten Login auf Argon2 gehoben werden soll.

    Nur die importierten Frappe-`pbkdf2-sha256`-Hashes sind Kandidaten;
    Argon2-Hashes sind bereits aktuell, Unbekanntes wird nicht blind ersetzt.
    """
    return bool(hash_str) and hash_str.startswith(FRAPPE_PRAEFIX)
