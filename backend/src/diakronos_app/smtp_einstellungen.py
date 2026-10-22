"""MAIL-1: SMTP-Einstellungen lesen, pruefen, verschluesselt speichern.

DIE REGELN DIESES MODULS
------------------------
1. **Das Passwort geht nie zurueck.** ``als_dict`` liefert nur
   ``passwort_gesetzt: ja/nein`` — es gibt keinen Pfad, der den Klartext in
   eine Antwort, ein Log oder ein Audit-Protokoll bringt.
2. **Verschluesselt wie die Google-Zugangsdaten** (``google_secrets.py``):
   Fernet mit einem Schluessel aus ``SECRET_KEY``, eigener Ableitungs-Kontext
   ``b"diakronos/smtp/v1\\0"``. Getrennte Kontexte heisst: ein Geheimtext des
   einen Moduls ist im anderen wertlos.
3. **Leeres Passwortfeld = unveraendert lassen.** Die Oberflaeche schickt nie
   ein Passwort zurueck, also kann sie auch keines mitschicken; wer das Feld
   leer laesst, will das hinterlegte behalten. Ausdrueckliches Entfernen geht
   ueber ``passwort_entfernen=True``.
4. **Pruefen hier UND im Endpunkt** — dieselbe Funktion. Eine Schranke nur in
   der Oberflaeche liesse den Versand mit einem unmoeglichen Wert laufen.
5. **„keine Sicherheit" ist erlaubt, aber nicht mit Anmeldung.** Klartext
   plus Zugangsdaten ist ein Passwort im Netz; das verweigert ``pruefen``
   (S1: „keine" nur mit deutlicher Warnung — die Warnung steht in der
   Oberflaeche, die Schranke hier).
6. **Das Passwort gehoert zu Server UND Benutzer** (MAIL-1b, N1). Wechselt
   eines von beiden, wird das hinterlegte Passwort NICHT weiterverwendet: es
   wuerde sonst an einen fremden Server gehen. Ein leeres Feld verwirft es
   dann, der Administrator muss es neu eintippen.
7. **Keine Steuerzeichen in Kopffeldern** (MAIL-1b, N2). CR/LF im
   Absendernamen brachte ``EmailMessage`` zum Werfen — ausserhalb des
   ``try`` in ``sende()`` eine 500, und die Loeschbestaetigung war blockiert.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.models.smtp import (
    SICHERHEIT_KEINE,
    SICHERHEIT_SSL,
    SICHERHEIT_STARTTLS,
    SICHERHEITSWERTE,
    SMTP_EINSTELLUNGEN_NAME,
    STANDARD_TIMEOUT,
    SmtpEinstellungen,
)

logger = logging.getLogger("diakronos_app.smtp_einstellungen")

__all__ = [
    "EinstellungFehler", "verschluessle", "entschluessle", "pruefen", "als_dict",
    "holen", "speichern", "ZUGANGSDATEN", "PASSWORT_PRAEFIX",
    "hat_steuerzeichen", "gleicher_stand", "passwort_verworfen_meldung",
]

#: Praefix der Geheimtexte — dieselbe Form wie ``google_secrets.PREFIX``.
PASSWORT_PRAEFIX = "fernet:v1:"

#: Kontext der Schluesselableitung. NIE aendern: bestehende Geheimtexte waeren
#: sonst nicht mehr lesbar (der Administrator muesste das Passwort neu setzen).
ABLEITUNGS_KONTEXT = b"diakronos/smtp/v1\0"

#: Plane Adressform. Absichtlich grosszuegig (das endgueltige Urteil faellt der
#: Mailserver), aber nicht so grosszuegig, dass ein Tippfehler ohne @ durchgeht.
_ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
#: Hostname: keine Leerzeichen, kein Schema, kein Pfad — „mail.example.org".
_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?$")
#: Steuerzeichen (C0 und DEL). Sie haben in keinem Kopffeld etwas zu suchen:
#: ein CR/LF im Absendernamen liess `EmailMessage` werfen (MAIL-1b, N2).
_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f]")


def hat_steuerzeichen(wert: object) -> bool:
    """Enthaelt der Wert ein Steuerzeichen (CR, LF, NUL, …)?"""
    return bool(_STEUERZEICHEN.search(str(wert or "")))


def gleicher_stand(alt: dict | None, neu: dict) -> bool:
    """Sind Server und Benutzer unveraendert (MAIL-1b, N1)?

    Nur dann darf ein hinterlegtes Passwort weiterverwendet werden. Der
    Vergleich ist absichtlich streng (getrimmt, aber nicht umgeschrieben):
    eine andere Schreibweise desselben Servers kostet ein neu eingetipptes
    Passwort — ein Passwort an den falschen Server kostet weit mehr.
    """
    alt = alt or {}
    return (str(alt.get("host") or "").strip() == str(neu.get("host") or "").strip()
            and str(alt.get("benutzername") or "").strip()
            == str(neu.get("benutzername") or "").strip())


def passwort_verworfen_meldung() -> str:
    """Der eine Satz fuer „Passwort passt nicht mehr zum Ziel" (N1)."""
    return ("Bei geändertem Server oder Benutzer bitte das Passwort neu "
            "eingeben.")


#: Feldname -> Bezeichnung fuer Meldungen (deutsch, wie in der Oberflaeche).
_FELDNAMEN = {
    "host": "Der Name des Mailservers",
    "benutzername": "Der Benutzername",
    "absender": "Die Absenderadresse",
    "absender_name": "Der Absendername",
}


class EinstellungFehler(ValueError):
    """Ungueltige Einstellung — der Text ist die Meldung fuer die Oberflaeche."""


# ── Verschluesselung (S1) ──────────────────────────────────────────────────

def _cipher():
    """Fernet mit eigenem Kontext, abgeleitet aus ``SECRET_KEY``."""
    from diakronos_app.settings import settings

    if not settings.secret_key or settings.secret_key == "insecure-dev-key":
        raise ValidationError(
            "Für den Mailversand braucht das Passwort einen sicheren SECRET_KEY."
        )
    from cryptography.fernet import Fernet

    key = hashlib.sha256(ABLEITUNGS_KONTEXT + settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def verschluessle(klartext: str) -> str:
    """Klartext -> Geheimtext mit Praefix. Der Klartext wird nie geloggt."""
    # json.dumps ist hier nicht noetig: der Wert kommt aus einem Eingabefeld
    # und geht als UTF-8 in Fernet.
    return PASSWORT_PRAEFIX + _cipher().encrypt(str(klartext).encode("utf-8")).decode("ascii")


def entschluessle(geheimtext: str | None) -> str:
    """Geheimtext -> Klartext; leer/None -> ``""`` (kein Passwort hinterlegt).

    Klartext in der Spalte (etwa von Hand eingetragen) wird NICHT akzeptiert —
    er gilt als „nicht lesbar" und fuehrt zu einer klaren Meldung, statt still
    ein Passwort zu benutzen, das jeder in der Tabelle sieht.
    """
    if not geheimtext:
        return ""
    from cryptography.fernet import InvalidToken

    try:
        if not str(geheimtext).startswith(PASSWORT_PRAEFIX):
            raise InvalidToken
        return _cipher().decrypt(
            str(geheimtext)[len(PASSWORT_PRAEFIX):].encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise ValidationError(
            "Das gespeicherte Mailpasswort lässt sich nicht entschlüsseln "
            "(SECRET_KEY geändert?). Bitte das Passwort neu eintragen."
        ) from None


# ── Pruefung ───────────────────────────────────────────────────────────────

def pruefen(*, host: object, port: object, sicherheit: object, benutzername: object,
            absender: object, absender_name: object, timeout: object,
            passwort_gesetzt: bool, passwort_entfernen: bool = False) -> dict:
    """Alle Felder pruefen und normalisieren. Rueckgabe ohne Passwort.

    ``passwort_entfernen`` (MAIL-1b, N4): Wer das gespeicherte Passwort gerade
    entfernt, will bewusst KEINE Anmeldung mehr. Ohne diesen Schalter verlangt
    die Pruefung unten das Passwort, und der ausdrueckliche Loeschwunsch waere
    in der Oberflaeche nicht ausfuehrbar — genau das fiel in der Abnahme auf.
    Ist danach noch ein Benutzername gesetzt, bleibt die Regel „STARTTLS/SSL
    mit Anmeldung braucht ein Passwort“ unangetastet (Meldung wie bisher); nur
    bei leerem Benutzernamen (Server ohne Anmeldung) ist der Zustand stimmig.
    """
    for feld in ("host", "benutzername", "absender", "absender_name"):
        if hat_steuerzeichen(locals()[feld]):
            raise EinstellungFehler(
                f"{_FELDNAMEN[feld]} enthält ein unerlaubtes Steuerzeichen "
                "(Zeilenumbruch o. Ä.). Bitte ohne Umbrüche eingeben."
            )
    geprueft = {
        "host": str(host or "").strip(),
        "port": 0,
        "sicherheit": str(sicherheit or "").strip().lower(),
        "benutzername": str(benutzername or "").strip(),
        "absender": str(absender or "").strip(),
        "absender_name": str(absender_name or "").strip(),
        "timeout": STANDARD_TIMEOUT,
    }
    if not geprueft["host"]:
        raise EinstellungFehler("Bitte den Namen des Mailservers angeben.")
    if not _HOST.match(geprueft["host"]):
        raise EinstellungFehler(
            "Der Mailserver ist ein Name wie mail.example.org — ohne http:// und "
            "ohne Schrägstrich."
        )
    try:
        geprueft["port"] = int(str(port).strip())
    except (TypeError, ValueError):
        raise EinstellungFehler("Bitte den Port als Zahl angeben (meist 587).") from None
    if not 1 <= geprueft["port"] <= 65535:
        raise EinstellungFehler("Der Port muss zwischen 1 und 65535 liegen.")
    if geprueft["sicherheit"] not in SICHERHEITSWERTE:
        raise EinstellungFehler(
            "Bitte die Verschlüsselung wählen: STARTTLS, SSL/TLS oder keine."
        )
    if not geprueft["absender"]:
        raise EinstellungFehler("Bitte die Absenderadresse angeben.")
    if not _ADRESSE.match(geprueft["absender"]):
        raise EinstellungFehler("Die Absenderadresse ist keine gültige E-Mail-Adresse.")
    if geprueft["sicherheit"] == SICHERHEIT_KEINE and geprueft["benutzername"]:
        raise EinstellungFehler(
            "Ohne Verschlüsselung geht der Mailversand nur ohne Anmeldung. "
            "Bitte STARTTLS oder SSL/TLS wählen."
        )
    if geprueft["sicherheit"] == SICHERHEIT_KEINE and passwort_gesetzt:
        raise EinstellungFehler(
            "Ohne Verschlüsselung geht der Mailversand nur ohne Anmeldung. "
            "Bitte das Passwort entfernen oder STARTTLS bzw. SSL/TLS wählen."
        )
    if geprueft["sicherheit"] in (SICHERHEIT_STARTTLS, SICHERHEIT_SSL) \
            and geprueft["benutzername"] and not passwort_gesetzt \
            and not passwort_entfernen:
        raise EinstellungFehler(
            "Für die Anmeldung fehlt das Passwort. Bitte das Passwort eintragen."
        )
    if geprueft["sicherheit"] in (SICHERHEIT_STARTTLS, SICHERHEIT_SSL) \
            and geprueft["benutzername"] and passwort_entfernen:
        # N4: Entfernen heisst „keine Anmeldung mehr“. Mit Benutzername ist das
        # ein Widerspruch — die Meldung sagt, was zu tun ist.
        raise EinstellungFehler(
            "Das Passwort lässt sich nur entfernen, wenn kein Benutzername "
            "eingetragen ist. Bitte den Benutzernamen leeren — ein Server ohne "
            "Anmeldung braucht keinen."
        )
    try:
        geprueft["timeout"] = float(str(timeout).strip() or STANDARD_TIMEOUT)
    except (TypeError, ValueError):
        raise EinstellungFehler("Bitte das Zeitlimit in Sekunden angeben.") from None
    if not 3 <= geprueft["timeout"] <= 120:
        raise EinstellungFehler("Das Zeitlimit muss zwischen 3 und 120 Sekunden liegen.")
    return geprueft


# ── Lesen und Schreiben ────────────────────────────────────────────────────

def holen(session: Session) -> SmtpEinstellungen | None:
    """Die Einstellungszeile oder ``None`` = nicht eingerichtet."""
    return session.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)


def als_dict(zeile: SmtpEinstellungen | None) -> dict:
    """Darstellung fuer die Oberflaeche — OHNE Passwort, nur „gesetzt"."""
    if zeile is None:
        return {
            "eingerichtet": False,
            "host": "",
            "port": 587,
            "sicherheit": SICHERHEIT_STARTTLS,
            "benutzername": "",
            "passwort_gesetzt": False,
            "absender": "",
            "absender_name": "",
            "timeout": STANDARD_TIMEOUT,
            "geaendert": "",
        }
    return {
        "eingerichtet": True,
        "host": zeile.host or "",
        "port": int(zeile.port or 0),
        "sicherheit": zeile.sicherheit or SICHERHEIT_STARTTLS,
        "benutzername": zeile.benutzername or "",
        "passwort_gesetzt": bool(zeile.passwort_verschluesselt),
        "absender": zeile.absender or "",
        "absender_name": zeile.absender_name or "",
        "timeout": float(zeile.timeout or STANDARD_TIMEOUT),
        "geaendert": zeile.modified.isoformat() if zeile.modified else "",
    }


def speichern(session: Session, *, benutzer: str, host: object, port: object,
              sicherheit: object, benutzername: object = "", passwort: object = "",
              passwort_entfernen: bool = False, absender: object,
              absender_name: object = "", timeout: object = STANDARD_TIMEOUT,
              jetzt: datetime | None = None) -> SmtpEinstellungen:
    """Pruefen und in EINER Transaktion schreiben.

    ``passwort`` leer = das hinterlegte Passwort bleibt (Regel 3) — aber NUR,
    wenn ``host`` und ``benutzername`` unveraendert sind (Regel 6). Wechselt
    eines davon, wird das alte Passwort verworfen: es gehoert zu einem anderen
    Ziel und darf dort nicht hin (MAIL-1b, N1).
    ``passwort_entfernen=True`` loescht es ausdruecklich (Server ohne Anmeldung).
    """
    zeile = holen(session)
    neues_passwort = str(passwort or "")
    vorher = als_dict(zeile)
    vorher_gesetzt = bool(zeile is not None and zeile.passwort_verschluesselt)
    ziel_gewechselt = vorher_gesetzt and not gleicher_stand(
        vorher, {"host": host, "benutzername": benutzername})
    verworfen = ziel_gewechselt and not neues_passwort and not passwort_entfernen
    danach_gesetzt = (False if (passwort_entfernen or verworfen)
                      else (bool(neues_passwort) or vorher_gesetzt))

    geprueft = pruefen(
        host=host, port=port, sicherheit=sicherheit, benutzername=benutzername,
        absender=absender, absender_name=absender_name, timeout=timeout,
        passwort_gesetzt=danach_gesetzt,
        # N4: nur wenn wirklich geloescht wird UND kein neues Passwort kommt.
        passwort_entfernen=bool(passwort_entfernen and not neues_passwort),
    )

    zeit = jetzt or datetime.now()
    if zeile is None:
        zeile = SmtpEinstellungen(name=SMTP_EINSTELLUNGEN_NAME, created=zeit,
                                  created_by=benutzer)
        session.add(zeile)
    zeile.host = geprueft["host"]
    zeile.port = geprueft["port"]
    zeile.sicherheit = geprueft["sicherheit"]
    zeile.benutzername = geprueft["benutzername"] or None
    zeile.absender = geprueft["absender"]
    zeile.absender_name = geprueft["absender_name"] or None
    zeile.timeout = int(geprueft["timeout"])
    if neues_passwort:
        zeile.passwort_verschluesselt = verschluessle(neues_passwort)
    elif passwort_entfernen or verworfen:
        # N1: ein Passwort zu einem anderen Server/Benutzer wird verworfen,
        # statt es still weiterzureichen.
        zeile.passwort_verschluesselt = None
    zeile.eingerichtet = True
    zeile.modified = zeit
    zeile.modified_by = benutzer
    session.commit()
    # Nie das Passwort, nie den Benutzernamen im Log: nur die Aenderung als
    # solche (S2: Aenderungen sind nachvollziehbar).
    logger.info("Mailversand-Einstellungen geaendert von %s (Passwort %s)",
                benutzer, "neu gesetzt" if neues_passwort
                else ("entfernt" if passwort_entfernen else
                      ("verworfen (Ziel geändert)" if verworfen else
                       ("unverändert" if vorher_gesetzt else "nicht gesetzt"))))
    return zeile


#: Spalten, die NIE in eine Antwort gehoeren (Waechter fuer Tests/Review).
ZUGANGSDATEN = ("passwort_verschluesselt",)
