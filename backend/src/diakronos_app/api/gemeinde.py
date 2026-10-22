"""N9: Gemeinde- und Datenschutz-Einstellungen (Admin-Endpunkte).

Ein Ort fuer das, was die Gemeinde und die Technik betrifft (Neuordnung N9,
Befund OP-ADMIN-14). Der Bereich ist **nur fuer Mitgliederadministratoren**;
die Oberflaeche blendet nur aus, was der Server ohnehin verweigert.

Aufgeteilt in drei Abschnitte:

* ``gemeinde_get_einstellungen`` / ``gemeinde_speichern`` — Gemeindename
  (Spalte ``organisationsname`` der portierten Frappe-Single
  ``diakronos_einstellungen``), Kontakt-E-Mail, oeffentliche Adresse,
  Willkommenstext und Standardwerte fuer neue Registrierungslinks.
* ``gemeinde_setze_modul`` — die Modul-Sichtbarkeit von Diakronos/Kronos/
  Diakonos/Psalmos/Seelsorge (die ``*_sichtbar``-Spalten derselben Single).
* ``datenschutz_get_texte`` / ``datenschutz_speichern`` — die pflegbaren
  Einwilligungs-, Datenschutz- und Aufbewahrungstexte samt Versionszaehler.

Alles wird serverseitig geprueft (Pflichtfelder, Laengen, erlaubte Werte) und
in EINER Transaktion geschrieben — kein stiller Teilstand.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.gemeinde"

import logging
from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.models.gemeinde import (
    DATENSCHUTZ_TEXT_NAME,
    DATENSCHUTZ_VEROEFFENTLICHT_NAME,
    GEMEINDE_EINSTELLUNGEN_NAME,
    STANDARD_LAUFZEIT_TAGE,
    STANDARD_MAX_ANMELDUNGEN,
    DatenschutzText,
    DatenschutzTextVeroeffentlicht,
    GemeindeEinstellungen,
)

logger = logging.getLogger("diakronos_app.api.gemeinde")

__all__ = [
    "gemeinde_get_einstellungen",
    "gemeinde_speichern",
    "gemeinde_setze_linkvorgaben",
    "gemeinde_setze_modul",
    "datenschutz_get_texte",
    "datenschutz_speichern",
    "oeffentliche_texte",
    "wirksame_texte",
    "wirksame_einwilligung",
    "wirksame_fassung",
]

# Name der portierten Frappe-Single (Gemeindename + Modul-Spalten).
_DIAKRONOS_EINSTELLUNGEN = "Diakronos Einstellungen"


def _angemeldeter_admin() -> str:
    """Stellt sicher, dass der Aufrufer Administrator ist; gibt seinen Namen zurueck.

    Wie ``anmeldung.einstellungen_api._require_admin``: die Rechtepruefung liegt
    serverseitig — der Client darf den Benutzer NICHT selbst mitgeben.
    ``is_admin`` behandelt (wie das Original) den Benutzer ``Administrator``
    gesondert, deshalb wird es hier benutzt und nicht die reine Rollenpruefung.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import session

    user = session.user
    if not user or user == "Guest":
        raise PermissionError("Anmeldung verweigert.")
    if not permissions.is_admin(user):
        raise PermissionError("Nur Administratoren duerfen die Gemeinde einstellen.")
    return user

# Module, deren Sichtbarkeit pflegbar ist: (Spaltenpraefix, Anzeigename).
MODULE = (
    ("diakronos", "Diakronos"),
    ("kronos", "Kronos"),
    ("diakonos", "Diakonos"),
    ("psalmos", "Psalmos"),
    ("seelsorge", "Seelsorge"),
)

# Obergrenzen, damit ein Tippfehler keine unbrauchbare Konfiguration erzeugt.
_MAX_LAUFZEIT_TAGE = 365
_MAX_ANMELDUNGEN = 100000
_MAX_EMAIL = 255
_MAX_ADRESSE = 255
_MAX_WILLKOMMEN = 4000
_MAX_TEXT = 20000

#: Voreinstellungen der Datenschutz-Texte, wenn noch nichts gepflegt wurde.
#: Sie sind bewusst schlicht und ersetzen keine Rechtsberatung — die Gemeinde
#: passt sie an ihre Verhaeltnisse an.
STANDARD_EINWILLIGUNG = (
    "Ich willige ein, dass meine Angaben zur Mitgliedschaft und zur "
    "Organisation der Gemeindearbeit gespeichert und verarbeitet werden. "
    "Diese Einwilligung kann ich jederzeit widerrufen."
)
STANDARD_DATENSCHUTZERKLAERUNG = (
    "Die Gemeinde verarbeitet die von dir angegebenen Daten ausschliesslich "
    "zur Organisation der Gemeindearbeit (Mitgliederverwaltung, Dienste, "
    "Kalender). Es findet keine Weitergabe an Dritte zu Werbezwecken statt."
)
STANDARD_AUFBEWAHRUNG = (
    "Daten werden nur so lange gespeichert, wie es fuer die Gemeindearbeit "
    "erforderlich ist. Nach einem Loeschwunsch werden die persoenlichen "
    "Angaben anonymisiert; Nachweise der Einwilligung bleiben erhalten."
)


def wirksame_texte() -> dict[str, str]:
    """Die Texte, die neuen Anmeldungen tatsaechlich gezeigt werden (H-1/M-2).

    N9b: Es gilt ausschliesslich die **veroeffentlichte** Fassung
    (``datenschutz_text_veroeffentlicht``). Der bearbeitbare Entwurf
    (``datenschutz_text``) veraendert die oeffentliche Seite NICHT — sonst
    belegte die Anmeldung einen Wortlaut, den die Person nie gesehen hat
    (Art. 7 DSGVO). Gibt es noch keine veroeffentlichte Fassung, gelten die
    Standardtexte.

    Rueckgabe enthaelt immer alle drei Texte als reiner Text (nie HTML).

    Nie eine Exception: eine fehlende/lesbare Einstellung darf die
    oeffentliche Seite nicht wegkaufen — dann gelten die Standardtexte.
    """
    ergebnis = {
        "einwilligung": STANDARD_EINWILLIGUNG,
        "datenschutzerklaerung": STANDARD_DATENSCHUTZERKLAERUNG,
        "aufbewahrung": STANDARD_AUFBEWAHRUNG,
    }
    try:
        from diakronos_app.db import SessionLocal

        with SessionLocal() as sess:
            zeile = sess.get(
                DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME
            )
            if zeile is None:
                return ergebnis
            for feld in ("einwilligung", "datenschutzerklaerung", "aufbewahrung"):
                wert = (getattr(zeile, feld, None) or "").strip()
                if wert:
                    ergebnis[feld] = wert
    except Exception:  # noqa: BLE001 — oeffentliche Seite darf nicht scheitern
        return ergebnis
    return ergebnis


def wirksame_einwilligung() -> str:
    """Nur der wirksame Einwilligungstext (Kurzform fuer den Beleg-Snapshot)."""
    return wirksame_texte()["einwilligung"]


def _text_kennung(text: str) -> str:
    """Kurze, stabile Kennung eines Textes (erste 16 Zeichen eines SHA-256).

    N-1: Der Einwilligungsbeleg soll erkennen lassen, WELCHE Fassung angezeigt
    wurde. Die Fassungsnummer allein genuegt nicht — nach einem Downgrade kann
    dieselbe Nummer einen anderen Wortlaut tragen. Der Hash bindet den Beleg an
    den tatsaechlichen Text.
    """
    import hashlib

    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def wirksame_fassung() -> dict[str, Any]:
    """Die geltende Einwilligungsfassung mit Nummer, Text und Kennung (N-1).

    Massgeblich ist die VEROEFFENTLICHTE Fassung (`datenschutz_text_veroeffentlicht`);
    ohne veroeffentlichte Zeile gelten die Standardtexte mit Fassung 1. Dieselbe
    Quelle speist die oeffentliche Seite UND den Beleg — so kann der angezeigte
    Wortlaut nicht vom belegten abweichen (Art. 7 DSGVO).

    Nie eine Exception (wie ``wirksame_texte``): im Zweifel der Standardtext.
    """
    text = wirksame_einwilligung() or STANDARD_EINWILLIGUNG
    version = 1
    try:
        from diakronos_app.db import SessionLocal

        with SessionLocal() as sess:
            zeile = sess.get(
                DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME
            )
            if zeile is not None and zeile.version is not None:
                version = int(zeile.version)
    except Exception:  # noqa: BLE001 — oeffentliche Seite darf nicht scheitern
        version = 1
    return {"version": version, "text": text, "kennung": _text_kennung(text)}


def _text(wert: Any, feld: str, max_laenge: int, pflicht: bool = False) -> str | None:
    """Bereinigt einen Freitext; prueft Pflicht und Laenge."""
    if wert is None:
        if pflicht:
            raise ValidationError(f"{feld} ist ein Pflichtfeld.")
        return None
    wert = str(wert).strip()
    if not wert:
        if pflicht:
            raise ValidationError(f"{feld} ist ein Pflichtfeld.")
        return None
    if len(wert) > max_laenge:
        raise ValidationError(f"{feld} ist zu lang (hoechstens {max_laenge} Zeichen).")
    return wert


def _ist_email(wert: str) -> bool:
    """Sehr einfache Adresspruefung — kein vollstaendiger RFC-Test gewollt."""
    if wert.count("@") != 1:
        return False
    vor, nach = wert.split("@")
    return bool(vor) and "." in nach and not nach.startswith(".") and not nach.endswith(".")


def _zahl(wert: Any, feld: str, minimum: int, maximum: int) -> int:
    """Wandelt in eine ganze Zahl und prueft den Bereich."""
    try:
        zahl = int(wert)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{feld} muss eine ganze Zahl sein.") from exc
    if zahl < minimum or zahl > maximum:
        raise ValidationError(f"{feld} muss zwischen {minimum} und {maximum} liegen.")
    return zahl


def _gemeinde_zeile(sess) -> GemeindeEinstellungen:
    """Liest die Single-Zeile; legt sie mit Voreinstellungen an, falls noetig."""
    from datetime import datetime

    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is None:
        zeile = GemeindeEinstellungen(
            name=GEMEINDE_EINSTELLUNGEN_NAME,
            link_laufzeit_tage=STANDARD_LAUFZEIT_TAGE,
            link_max_anmeldungen=STANDARD_MAX_ANMELDUNGEN,
            created=datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


def _text_zeile(sess) -> DatenschutzText:
    """Liest die Text-Single-Zeile; legt sie mit den Standardtexten an."""
    from datetime import datetime

    zeile = sess.get(DatenschutzText, DATENSCHUTZ_TEXT_NAME)
    if zeile is None:
        zeile = DatenschutzText(
            name=DATENSCHUTZ_TEXT_NAME,
            einwilligung=STANDARD_EINWILLIGUNG,
            datenschutzerklaerung=STANDARD_DATENSCHUTZERKLAERUNG,
            aufbewahrung=STANDARD_AUFBEWAHRUNG,
            version=1,
            veroeffentlicht=False,
            created=datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


def _veroeffentlicht_zeile(sess) -> DatenschutzTextVeroeffentlicht:
    """Liest die veroeffentlichte Fassung; legt sie mit den Standardtexten an.

    N9b (M-2): Die Zeile wird nur beim Speichern MIT Haken aus dem Entwurf
    gefuellt (siehe ``datenschutz_speichern``). Ein unveroeffentlichter Entwurf
    laesst sie unberuehrt — die oeffentliche Seite und der Beleg bleiben damit
    auf dem zuletzt veroeffentlichten Wortlaut.
    """
    from datetime import datetime

    zeile = sess.get(DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME)
    if zeile is None:
        zeile = DatenschutzTextVeroeffentlicht(
            name=DATENSCHUTZ_VEROEFFENTLICHT_NAME,
            einwilligung=STANDARD_EINWILLIGUNG,
            datenschutzerklaerung=STANDARD_DATENSCHUTZERKLAERUNG,
            aufbewahrung=STANDARD_AUFBEWAHRUNG,
            version=1,
            created=datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


def _diakronos_einstellungen(sess):
    """Die portierte Frappe-Single als ORM-Objekt (anlegen, falls noetig)."""
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    zeile = sess.get(DiakronosEinstellungen, _DIAKRONOS_EINSTELLUNGEN)
    if zeile is None:
        from datetime import datetime

        zeile = DiakronosEinstellungen(
            name=_DIAKRONOS_EINSTELLUNGEN,
            docstatus=0,
            idx=0,
            diakronos_sichtbar=False,
            kronos_sichtbar=False,
            diakonos_sichtbar=False,
            psalmos_sichtbar=False,
            seelsorge_sichtbar=False,
            demodaten_erstellen=False,
            demodaten_aktiv=False,
            dev_modus=False,
            creation=datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


@whitelist()
def gemeinde_get_einstellungen() -> dict[str, Any]:
    """Liefert Gemeindename, Kontakt, oeffentliche Adresse, Module und Link-Vorgaben."""
    from diakronos_app.db import SessionLocal

    _angemeldeter_admin()
    sess = SessionLocal()
    try:
        g = _gemeinde_zeile(sess)
        d = _diakronos_einstellungen(sess)
        return {
            "gemeindename": d.organisationsname or "",
            "kontakt_email": g.kontakt_email or "",
            "oeffentliche_adresse": g.oeffentliche_adresse or "",
            "willkommenstext": g.willkommenstext or "",
            "link_laufzeit_tage": int(g.link_laufzeit_tage or STANDARD_LAUFZEIT_TAGE),
            "link_max_anmeldungen": int(g.link_max_anmeldungen or 0),
            # Die Anzeigenamen der Module zeigt die Oberflaeche nur zur Info —
            # sie sind Teil der Alt-Konfiguration und werden hier nicht geaendert.
            "module": [
                {
                    "schluessel": prefix,
                    "anzeige": label,
                    "sichtbar": bool(getattr(d, f"{prefix}_sichtbar", False)),
                }
                for prefix, label in MODULE
            ],
        }
    finally:
        sess.rollback()  # ein beim Lesen angelegter Default soll nicht kleben
        sess.close()


@whitelist()
def gemeinde_speichern(gemeindename: str = "", kontakt_email: str = "",
                       oeffentliche_adresse: str = "", willkommenstext: str = "",
                       link_laufzeit_tage: Any = None,
                       link_max_anmeldungen: Any = None,
                       request=None) -> dict[str, Any]:
    """Speichert die Gemeinde-Angaben und Link-Vorgaben in einer Transaktion.

    ``link_laufzeit_tage``/``link_max_anmeldungen`` sind **optional**: fehlt der
    Wert, bleibt die gespeicherte Vorgabe erhalten. So kann die Karte „Gemeinde“
    speichern, ohne die auf der Karte „Registrierung“ gepflegten Werte
    versehentlich auf den Standard zurückzusetzen.
    """
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    if request is not None and request.method != "POST":
        raise ValidationError("Speichern ist nur per POST erlaubt.")

    name = _text(gemeindename, "Gemeindename", 140, pflicht=True)
    email = _text(kontakt_email, "Kontakt-E-Mail", _MAX_EMAIL)
    if email is not None and not _ist_email(email):
        raise ValidationError("Kontakt-E-Mail ist keine gueltige Adresse.")
    adresse = _text(oeffentliche_adresse, "Oeffentliche Adresse", _MAX_ADRESSE)
    if adresse is not None and not (adresse.startswith("http://") or adresse.startswith("https://")):
        raise ValidationError("Oeffentliche Adresse muss mit http:// oder https:// beginnen.")
    if adresse is not None:
        adresse = adresse.rstrip("/")
    willkommen = _text(willkommenstext, "Willkommenstext", _MAX_WILLKOMMEN)
    laufzeit = (None if link_laufzeit_tage is None
                else _zahl(link_laufzeit_tage, "Laufzeit der Links", 0, _MAX_LAUFZEIT_TAGE))
    maximum = (None if link_max_anmeldungen is None
               else _zahl(link_max_anmeldungen, "Hoechstzahl Anmeldungen", 0, _MAX_ANMELDUNGEN))

    with SessionLocal() as sess:
        g = _gemeinde_zeile(sess)
        d = _diakronos_einstellungen(sess)
        d.organisationsname = name
        d.modified_by = besitzer
        d.modified = datetime.now()
        g.kontakt_email = email
        g.oeffentliche_adresse = adresse
        g.willkommenstext = willkommen
        if laufzeit is not None:
            g.link_laufzeit_tage = laufzeit
        if maximum is not None:
            g.link_max_anmeldungen = maximum
        g.modified = datetime.now()
        g.modified_by = besitzer
        g.created_by = g.created_by or besitzer
        sess.commit()
    logger.info("Gemeinde-Einstellungen gespeichert.")
    return {"gespeichert": True}


@whitelist()
def gemeinde_setze_linkvorgaben(link_laufzeit_tage: int, link_max_anmeldungen: int,
                                request=None) -> dict[str, Any]:
    """Setzt nur die Vorgaben fuer neue Registrierungslinks (Admin).

    Eigener Endpunkt, damit die Karte „Registrierung“ speichern kann, ohne die
    Gemeinde-Angaben der Karte „Gemeinde“ zu beruehren (und umgekehrt).
    """
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    if request is not None and request.method != "POST":
        raise ValidationError("Speichern ist nur per POST erlaubt.")
    laufzeit = _zahl(link_laufzeit_tage, "Laufzeit der Links", 0, _MAX_LAUFZEIT_TAGE)
    maximum = _zahl(link_max_anmeldungen, "Hoechstzahl Anmeldungen", 0, _MAX_ANMELDUNGEN)
    with SessionLocal() as sess:
        g = _gemeinde_zeile(sess)
        g.link_laufzeit_tage = laufzeit
        g.link_max_anmeldungen = maximum
        g.modified = datetime.now()
        g.modified_by = besitzer
        g.created_by = g.created_by or besitzer
        sess.commit()
    return {"link_laufzeit_tage": laufzeit, "link_max_anmeldungen": maximum}


@whitelist()
def gemeinde_setze_modul(schluessel: str, sichtbar: bool,
                         request=None) -> dict[str, Any]:
    """Schaltet die Sichtbarkeit eines Moduls (Diakronos/Kronos/...)."""
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    prefixe = {prefix for prefix, _ in MODULE}
    if schluessel not in prefixe:
        raise ValidationError("Unbekanntes Modul.")
    if isinstance(sichtbar, str):
        sichtbar = sichtbar.strip().lower() in ("true", "1", "yes", "ja")
    if not isinstance(sichtbar, bool):
        raise ValidationError("Die Sichtbarkeit muss ein Ja/Nein-Wert sein.")

    with SessionLocal() as sess:
        d = _diakronos_einstellungen(sess)
        setattr(d, f"{schluessel}_sichtbar", sichtbar)
        d.modified_by = besitzer
        d.modified = datetime.now()
        sess.commit()
    return {"schluessel": schluessel, "sichtbar": sichtbar}


@whitelist()
def datenschutz_get_texte() -> dict[str, Any]:
    """Liefert die pflegbaren Datenschutz-/Einwilligungstexte."""
    from diakronos_app.db import SessionLocal

    _angemeldeter_admin()
    sess = SessionLocal()
    try:
        t = _text_zeile(sess)
        v = _veroeffentlicht_zeile(sess)
        # ``version``/``veroeffentlicht`` beschreiben den ENTWURF (das, was der
        # Administrator gerade bearbeitet). Zusaetzlich die Fassung der zuletzt
        # veroeffentlichten Fassung, damit die Oberflaeche sagen kann, ob ein
        # unveroeffentlichter Entwurf vorliegt (M-2).
        entwurf_veroeffentlicht = bool(t.veroeffentlicht)
        veroeffentlichte_version = int(v.version or 1)
        return {
            "einwilligung": t.einwilligung or "",
            "datenschutzerklaerung": t.datenschutzerklaerung or "",
            "aufbewahrung": t.aufbewahrung or "",
            "version": int(t.version or 1),
            "veroeffentlicht": entwurf_veroeffentlicht,
            "veroeffentlichte_version": veroeffentlichte_version,
            "wirksam": wirksame_texte(),
        }
    finally:
        sess.rollback()
        sess.close()


@whitelist()
def datenschutz_speichern(einwilligung: str = "", datenschutzerklaerung: str = "",
                          aufbewahrung: str = "", veroeffentlicht: bool = False,
                          request=None) -> dict[str, Any]:
    """Speichert die Texte. Der Versionszaehler steigt bei echter Aenderung."""
    from datetime import datetime

    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    if request is not None and request.method != "POST":
        raise ValidationError("Speichern ist nur per POST erlaubt.")

    einw = _text(einwilligung, "Einwilligungstext", _MAX_TEXT, pflicht=True)
    erklaerung = _text(datenschutzerklaerung, "Datenschutzerklaerung", _MAX_TEXT, pflicht=True)
    aufbew = _text(aufbewahrung, "Aufbewahrungshinweis", _MAX_TEXT, pflicht=True)
    if isinstance(veroeffentlicht, str):
        veroeffentlicht = veroeffentlicht.strip().lower() in ("true", "1", "yes", "ja")
    if not isinstance(veroeffentlicht, bool):
        raise ValidationError("Veroeffentlicht muss ein Ja/Nein-Wert sein.")

    with SessionLocal() as sess:
        t = _text_zeile(sess)
        geaendert = (
            (t.einwilligung or "") != einw
            or (t.datenschutzerklaerung or "") != erklaerung
            or (t.aufbewahrung or "") != aufbew
        )
        t.einwilligung = einw
        t.datenschutzerklaerung = erklaerung
        t.aufbewahrung = aufbew
        t.veroeffentlicht = veroeffentlicht
        if geaendert:
            t.version = int(t.version or 1) + 1
        t.modified = datetime.now()
        t.modified_by = besitzer
        t.created_by = t.created_by or besitzer

        # N9b (M-2): Nur das Speichern MIT Haken macht den Entwurf zur geltenden
        # Fassung — dann wird er in die veroeffentlichte Zeile kopiert. Ohne
        # Haken bleibt die zuletzt veroeffentlichte Fassung unveraendert; der
        # Entwurf kann also beliebig oft bearbeitet werden, ohne dass die
        # oeffentliche Seite oder der Einwilligungs-Beleg wandert.
        if veroeffentlicht:
            v = _veroeffentlicht_zeile(sess)
            v.einwilligung = einw
            v.datenschutzerklaerung = erklaerung
            v.aufbewahrung = aufbew
            v.version = int(v.version or 1) + 1
            v.modified = datetime.now()
            v.modified_by = besitzer
            v.created_by = v.created_by or besitzer

        sess.commit()
        version = int(t.version or 1)
    logger.info("Datenschutz-Texte gespeichert (Entwurf Fassung %s, veroeffentlicht=%s).",
                version, veroeffentlicht)
    return {"gespeichert": True, "version": version, "veroeffentlicht": veroeffentlicht}
