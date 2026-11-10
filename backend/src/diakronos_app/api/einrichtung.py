"""ON-2 — Einrichtungs-Status fuer Assistent und „Einrichten“-Hinweise.

Der Endpunkt ``einrichtung.status`` ist die EINE Quelle fuer
* den Assistenten (Fortschritt links, Entwurf Frames 04–09),
* die Einrichtungs-Karte auf der Uebersicht (Frame 10) und
* die Hinweise in den Einstellungen (Frame 11).

Grundsatz (Kartenvorgabe D2)
----------------------------
**„erledigt“ wird aus ECHTEN Daten berechnet, nicht aus Klicks.** Fuer jeden
Punkt wird bei JEDEM Aufruf die zugrunde liegende Tabelle gelesen. Es gibt
deshalb keinen gespeicherten Haken, der veralten koennte: was als erledigt
erscheint, ist es auch — und umgekehrt verschwindet der Haken, wenn die Daten
wieder weg sind.

Der Assistent speichert nur Prozess-Zustand (``uebersprungen``,
``assistent_abgeschlossen``, ``erinnern_spaeter``) in ``einrichtung_stand``.

Die sieben Punkte (Entwurf Frame 09/10)
---------------------------------------
============================  ====================================================
``gemeindename``              ``organisationsname`` gesetzt
``logo``                      Logo-Datei hinterlegt UND vorhanden
``kontakt``                   Kontakt-E-Mail ODER Anschrift (Strasse+PLZ+Ort)
``mailversand``               ``smtp_einstellungen.eingerichtet`` (und ladbar)
``module``                    mindestens ein Modul sichtbar (bewusste Bestaetigung)
``mitglieder``                Mitglieder > 0 — OHNE den Systemadministrator selbst
``kalender``                  mindestens ein Kalender angelegt
============================  ====================================================

Rollen: angemeldet; Admin-Rollen sehen alles, jede andere Person bekommt 403
(die Karte schreibt das ausdruecklich so — die Punkte nennen interne Zahlen).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import ValidationError

logger = logging.getLogger("diakronos_app.api.einrichtung")

__all__ = [
    "status",
    "schritt_setzen",
    "abschliessen",
    "erinnern_spaeter",
    "kalender_vorschlag_anlegen",
    "PUNKTE",
    "SCHRITTE",
]

#: Anzeigereihenfolge der Punkte (Frame 09/10). Titel und Ziel sind WOERTLICH
#: aus dem Entwurf: ``titel`` = Zeilenbeschriftung der Checkliste, ``hinweis`` =
#: die Zeile darunter bzw. der Text auf der Uebersichts-Karte.
PUNKTE = (
    # Schluessel, Titel, Ziel (Frontend-Route), Titel wenn erledigt
    ("gemeindename", "Gemeinde", "#/einstellungen/gemeinde",
     "Gemeindename gesetzt"),
    ("logo", "Logo", "#/einstellungen/gemeinde",
     "Logo hinterlegt"),
    ("kontakt", "Kontakt", "#/einstellungen/gemeinde",
     "Kontakt hinterlegt"),
    ("mailversand", "Mailversand", "#/einstellungen/mailversand",
     "Mailversand eingerichtet"),
    ("module", "Module", "#/einstellungen",
     "Module festgelegt"),
    ("mitglieder", "Mitglieder", "#/mitglieder/liste",
     "Mitglieder vorhanden"),
    ("kalender", "Kalender", "#/kalender/verwalten",
     "Kalender angelegt"),
)

#: Schritte des Assistenten (Frame 04–08). ``fertig`` ist kein eigener Schritt.
SCHRITTE = (
    ("gemeinde", "Gemeinde"),
    ("kontakt", "Kontakt"),
    ("mailversand", "Mailversand"),
    ("module", "Module"),
    ("mitglieder_kalender", "Mitglieder & Kalender"),
)

MAX_ERINNERUNG_TAGE = 365
MIN_ERINNERUNG_TAGE = 1

#: F8: hoechstens so viele Kalender legt ein Vorschlags-Aufruf an. Die Liste
#: kommt vom Client — ohne Deckel waere ein Aufruf ein Massen-Insert.
MAX_KALENDER_VORSCHLAEGE = 10


def _angemeldeter_admin() -> str:
    """Wie ``api.gemeinde._angemeldeter_admin``: angemeldet UND Admin-Rolle.

    Bewusst dieselbe Pruefung (``permissions.is_admin``, inkl. der
    ``Administrator``-Sonderbehandlung des Originals) — zwei verschiedene
    Admin-Begriffe in derselben App waeren eine Fehlerquelle.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import session

    user = session.user
    if not user or user == "Guest":
        raise PermissionError("Anmeldung verweigert.")
    if not permissions.is_admin(user):
        raise PermissionError("Nur Administratoren duerfen die Einrichtung sehen.")
    return user


def _stand_zeile(sess):
    """Liest die Zeile ``einrichtung_stand``; legt sie bei Bedarf an.

    Fuer die SCHREIBENDEN Endpunkte: ohne Zeile gibt es nichts zu setzen, also
    wird eine angelegt und sofort geflusht (die ID steht dann fuer die
    Zuweisungen bereit).

    ``status`` benutzt absichtlich NICHT diese Funktion, sondern
    ``_stand_lesen``: ein Leseendpunkt darf keine Zeile anlegen. Der
    Werkzeug-Test ``test_sec11_methoden`` (SEC-11b/F2) prueft genau das am
    Funktionsrumpf — ein ``flush()`` in ``status`` waere ein Schreibzugriff
    hinter einem GET.
    """
    from diakronos_app.models.einrichtung import EINRICHTUNG_STAND_NAME, EinrichtungStand

    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    if zeile is None:
        zeile = EinrichtungStand(
            name=EINRICHTUNG_STAND_NAME,
            assistent_abgeschlossen=False,
            created=datetime.datetime.now(),
        )
        sess.add(zeile)
        sess.flush()
    return zeile


class _OhneZeile:
    """Ersatz fuer eine fehlende ``einrichtung_stand``-Zeile — NUR zum Lesen.

    Liefert fuer jedes Feld den Auslieferungszustand (Schritt ``""``, also
    `offen`; ``assistent_abgeschlossen`` False; keine Erinnerung). Damit kann
    ``status`` ohne Schreibzugriff antworten und ohne ``None``-Pruefungen an
    jeder Stelle.
    """

    assistent_abgeschlossen = False
    erinnerung_ab = None

    def __getattr__(self, name: str):  # noqa: ANN401 — Feldnamen sind dynamisch
        return None


def _stand_lesen(sess):
    """Liest die Zeile ``einrichtung_stand`` — OHNE sie anzulegen.

    Fuer ``status``: ein Leseendpunkt schreibt nichts. Fehlt die Zeile, gilt
    der Auslieferungszustand (``_OhneZeile``) — genau das, was das Anlegen
    mit Defaults auch ergaebe, nur ohne INSERT.
    """
    from diakronos_app.models.einrichtung import EINRICHTUNG_STAND_NAME, EinrichtungStand

    zeile = sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME)
    return _OhneZeile() if zeile is None else zeile


# ── Die sieben Punkte: je eine echte Abfrage ────────────────────────────────


def _gemeindename_gesetzt(sess) -> bool:
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    zeile = sess.get(DiakronosEinstellungen, "Diakronos Einstellungen")
    return bool(str(getattr(zeile, "organisationsname", "") or "").strip())


def _logo_hinterlegt(sess) -> bool:
    from diakronos_app.gemeinde_logo import logo_pfad
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is None:
        return False
    # Datei UND Eintrag: eine von Hand geloeschte Datei ist kein Logo.
    return logo_pfad(getattr(zeile, "logo_datei", None)) is not None


def _kontakt_hinterlegt(sess) -> bool:
    """E-Mail ODER vollstaendige Anschrift (Kartenvorgabe D2)."""
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is None:
        return False
    if str(zeile.kontakt_email or "").strip():
        return True
    return all(
        str(getattr(zeile, feld, "") or "").strip()
        for feld in ("strasse", "plz", "ort")
    )


def _mailversand_eingerichtet(sess) -> bool:
    """``smtp_einstellungen.eingerichtet`` — UND ladbar.

    ``eingerichtet`` ist der Haken, den ``api.mailversand.speichern`` setzt; die
    Ladepruefung daneben faengt den Fall ab, dass der Schluessel zum
    Entschluesseln des Passworts fehlt (dann kann wirklich nichts rausgehen).
    """
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    zeile = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
    if zeile is None or not bool(zeile.eingerichtet):
        return False
    try:
        from diakronos_app import mailversand

        return bool(mailversand.ist_konfiguriert())
    except Exception as exc:  # noqa: BLE001 — „nicht eingerichtet“ ist sicher
        logger.warning("Mailversand nicht pruefbar: %s", type(exc).__name__)
        return False


def _module_bestaetigt(sess) -> bool:
    """Entscheidung des Betreibers ueber die Module (F2, Orchestrator 2026-11-01).

    **Erledigt ist der Punkt, wenn der Assistent den Modul-Schritt abgeschlossen
    hat** — ``einrichtung_stand.schritt_module == "erledigt"`` — **oder** wenn
    der Assistent insgesamt abgeschlossen ist (``assistent_abgeschlossen``).

    Bewusst NICHT „mindestens ein Modul sichtbar“: die Karte „Module“ erlaubt
    auch die bewusste Entscheidung, ALLE Module abzuschalten (eine Gemeinde
    ohne Diakronos-Bereich ist ein gueltiger Betrieb). „Sichtbar“ ist damit
    kein Mass fuer „erledigt“ — der Vorgang ist es.

    ``uebersprungen`` zaehlt NICHT: uebersprungen heisst genau, dass die
    Entscheidung offen bleibt (wie bei allen anderen Punkten).
    """
    zeile = _stand_lesen(sess)
    if bool(getattr(zeile, "assistent_abgeschlossen", False)):
        return True
    return str(getattr(zeile, "schritt_module", "") or "").strip() == "erledigt"


def _systemadministrator_namen(sess) -> set[str]:
    """Namen, die den Systemadministrator SELBST bezeichnen.

    Zwei Quellen, damit ``Mitglieder > 0`` nicht durch den Erst-Admin kippt:

      1. das Konto ``Administrator`` (``spa.py``/``is_admin`` behandeln es
         gesondert — es ist die Wurzel jedes Bestands),
      2. Mitglieder, deren verknuepftes Konto (``Mitglied.user``) Inhaber einer
         Admin-Rolle ist (``System Manager``/``Mitgliederadministrator`` usw.).
         Das ist der Erst-Administrator aus ``erstinstallation.py``, der als
         Mitglied gefuehrt wird — verknuepft ueber ``Mitglied.user`` oder,
         wenn der Link fehlt, ueber dieselbe E-Mail.
    """
    from diakronos_app.frappe_compat.permissions import ADMIN_ROLES
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    namen = {"Administrator"}
    # Rollen in Python auswerten, nicht per ``IN``/``JOIN``: die Testdatenbank
    # (SQLite im Image) liefert fuer zusammengesetzte Vergleiche reproduzierbar
    # keine Zeile, obwohl die Zeilen existieren. Die Zahl der Rollenzeilen ist
    # klein — dieselbe Regel gilt dann auf jeder Datenbank.
    konten = {
        str(z.parent) for z in sess.query(HasRole).all()
        if z.parent and str(z.role or "") in ADMIN_ROLES
    }
    if not konten:
        return namen
    for mitglied_name, konto in sess.query(Mitglied.name, Mitglied.user).all():
        if mitglied_name and str(konto or "") in konten:
            namen.add(str(mitglied_name))
    emails = {
        str(u.email).strip().lower()
        for u in sess.query(User).all()
        if u.email and str(u.name) in konten
    }
    if emails:
        # Adressvergleich ebenfalls in Python (dieselbe Plattform-Eigenheit wie
        # oben bei ``IN``); die Zahl der Konten ist klein.
        for name, email in sess.query(Mitglied.name, Mitglied.email).all():
            if str(email or "").strip().lower() in emails and name:
                namen.add(str(name))
    return namen


def _mitglieder_vorhanden(sess) -> bool:
    """Mitglieder > 0 — OHNE den Systemadministrator selbst (Karte D2).

    Ausgetretene zaehlen nicht: die Gemeinde hat dann keine Mitglieder mehr.

    Gelesen werden NUR die beiden gebrauchten Spalten und in Python
    ausgewertet (kein ``IN``/``NOT IN`` im SQL): die Testdatenbank des Images
    (SQLite in-memory) verhaelt sich bei zusammengesetzten Vergleichen
    unzuverlaessig, und die Zahl der Mitglieder ist fuer diese Pruefung klein
    genug. So gilt auf jeder Datenbank dieselbe, nachvollziehbare Regel.
    """
    from sqlalchemy import text

    ohne = _systemadministrator_namen(sess)
    # Rohe Abfrage: keine ORM-Identitaetsmap, keine veralteten Objekte.
    zeilen = sess.execute(text("SELECT name, status FROM mitglied")).fetchall()
    for name, status in zeilen:
        if str(name) in ohne:
            continue
        if str(status or "").strip().lower() == "ausgetreten":
            continue
        return True
    return False


def _kalender_vorhanden(sess) -> bool:
    from diakronos_app.models.kronos import Kalender

    return sess.query(Kalender.name).first() is not None


#: Zuordnung Punkt -> Prueffunktion. EINE Stelle, damit die Reihenfolge in
#: ``PUNKTE`` und die Berechnung nicht auseinanderlaufen.
_PRUEFUNGEN = {
    "gemeindename": _gemeindename_gesetzt,
    "logo": _logo_hinterlegt,
    "kontakt": _kontakt_hinterlegt,
    "mailversand": _mailversand_eingerichtet,
    "module": _module_bestaetigt,
    "mitglieder": _mitglieder_vorhanden,
    "kalender": _kalender_vorhanden,
}


def _hinweis(schluessel: str, erledigt: bool) -> str:
    """Der Satz unter dem Punkt.

    Woertlich aus dem Entwurf, wo er dort steht (Frame 09: die drei offenen
    Zeilen; Frame 10: dieselben drei). Fuer die erledigten Punkte nennt der
    Satz den Datenstand — der Entwurf zeigt sie nur in Kurzform
    („Ev. Gemeinde Musterstadt · Kontakt hinterlegt“).
    """
    if erledigt:
        return {
            "gemeindename": "Gemeindename ist gesetzt.",
            "logo": "Logo hinterlegt.",
            "kontakt": "Kontakt hinterlegt.",
            "mailversand": "Mailversand ist eingerichtet.",
            "module": "Module sind festgelegt.",
            "mitglieder": "Mitglieder sind vorhanden.",
            "kalender": "Mindestens ein Kalender ist angelegt.",
        }[schluessel]
    return {
        # Frame 10: „Logo der Gemeinde fehlt“
        "logo": "Logo der Gemeinde fehlt",
        # Frame 09: „Nicht eingerichtet – keine Einladungen möglich“
        "mailversand": "Nicht eingerichtet – keine Einladungen möglich",
        # Frame 09/10: „Noch keine Mitglieder angelegt“
        "mitglieder": "Noch keine Mitglieder angelegt",
        "gemeindename": "Noch kein Gemeindename gesetzt",
        "kontakt": "Weder Kontakt-E-Mail noch Anschrift hinterlegt",
        "module": "Module noch nicht festgelegt",
        "kalender": "Noch kein Kalender angelegt",
    }[schluessel]


def _erinnerung_wirksam(zeile) -> datetime.date | None:
    """Das gespeicherte Erinnerungsdatum — aber nur, solange es in der Zukunft liegt.

    Ein vergangenes Datum ist keine Erinnerung mehr: die Karte erscheint dann
    wieder. So laeuft „Spaeter erinnern“ von selbst ab und braucht keinen Job.
    """
    wert = getattr(zeile, "erinnerung_ab", None)
    if not wert:
        return None
    if isinstance(wert, datetime.datetime):
        wert = wert.date()
    # ZEIT-3: „in der Zukunft“ ist der Kalendertag der Gemeinde, nicht die UTC
    # des Containers — sonst laeuft „Spaeter erinnern“ 1-2 Stunden zu lang.
    return wert if wert > _heute_gemeinde() else None


def _heute_gemeinde() -> datetime.date:
    """ZEIT-3: HEUTE in der Zeitzone der Gemeinde (nicht die UTC des Containers)."""
    from diakronos_app.zeit import heute_gemeinde

    return heute_gemeinde()


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist()
def status() -> dict[str, Any]:
    """Zustand der Einrichtung: Schritte, Punkte, Zaehler, Erinnerung."""
    from diakronos_app.db import SessionLocal

    _angemeldeter_admin()
    sess = SessionLocal()
    try:
        zeile = _stand_lesen(sess)
        punkte = []
        for schluessel, titel, ziel, titel_erledigt in PUNKTE:
            erledigt = bool(_PRUEFUNGEN[schluessel](sess))
            punkte.append({
                "schluessel": schluessel,
                "erledigt": erledigt,
                "titel": titel_erledigt if erledigt else titel,
                "hinweis": _hinweis(schluessel, erledigt),
                "ziel": ziel,
            })
        schritte = []
        for schluessel, anzeige in SCHRITTE:
            zustand = str(getattr(zeile, f"schritt_{schluessel}", "") or "offen")
            if zustand not in ("offen", "erledigt", "uebersprungen"):
                zustand = "offen"
            schritte.append({
                "schluessel": schluessel,
                "anzeige": anzeige,
                "zustand": zustand,
            })
        erledigt_anzahl = sum(1 for p in punkte if p["erledigt"])
        erinnerung = _erinnerung_wirksam(zeile)
        return {
            "assistent_abgeschlossen": bool(zeile.assistent_abgeschlossen),
            "schritte": schritte,
            "punkte": punkte,
            "offen_anzahl": len(punkte) - erledigt_anzahl,
            "erledigt_anzahl": erledigt_anzahl,
            "gesamt_anzahl": len(punkte),
            "erinnerung_ab": erinnerung.isoformat() if erinnerung else None,
        }
    finally:
        # ``status`` schreibt nichts — ein beim Lesen angelegter Default soll
        # nicht kleben (wie in ``gemeinde_get_einstellungen``).
        sess.rollback()
        sess.close()


@whitelist(methods=["POST"])
def schritt_setzen(schluessel: str = "", zustand: str = "", request=None) -> dict[str, Any]:
    """Speichert den Zustand EINES Assistenten-Schritts.

    ``uebersprungen`` ist ausdruecklich nur ein Schrittzustand: der zugehoerige
    Punkt in ``status().punkte`` bleibt offen, solange die Daten fehlen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.einrichtung import SCHRITT_SCHLUESSEL, SCHRITT_ZUSTAENDE

    besitzer = _angemeldeter_admin()
    wert = str(schluessel or "").strip()
    if wert not in SCHRITT_SCHLUESSEL:
        raise ValidationError("Unbekannter Einrichtungsschritt.")
    zustand_wert = str(zustand or "").strip()
    if zustand_wert not in SCHRITT_ZUSTAENDE:
        raise ValidationError("Unbekannter Zustand fuer einen Einrichtungsschritt.")

    with SessionLocal() as sess:
        zeile = _stand_zeile(sess)
        setattr(zeile, f"schritt_{wert}", zustand_wert)
        zeile.modified = datetime.datetime.now()
        zeile.modified_by = besitzer
        zeile.created_by = zeile.created_by or besitzer
        sess.commit()
    return {"schluessel": wert, "zustand": zustand_wert}


@whitelist(methods=["POST"])
def abschliessen(request=None) -> dict[str, Any]:
    """Setzt ``assistent_abgeschlossen`` — die Checkliste (Frame 09) erscheint."""
    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    with SessionLocal() as sess:
        zeile = _stand_zeile(sess)
        zeile.assistent_abgeschlossen = True
        zeile.modified = datetime.datetime.now()
        zeile.modified_by = besitzer
        zeile.created_by = zeile.created_by or besitzer
        sess.commit()
    return {"assistent_abgeschlossen": True}


@whitelist(methods=["POST"])
def erinnern_spaeter(tage: Any = 7, request=None) -> dict[str, Any]:
    """Blendet die Einrichtungs-Karte bis ``heute + tage`` aus (Frame 10).

    Ablage als DATUM in ``einrichtung_stand.erinnerung_ab`` — kein Schalter,
    der vergessen werden koennte: nach Ablauf erscheint die Karte von selbst
    wieder (``_erinnerung_wirksam``).
    """
    from diakronos_app.db import SessionLocal

    besitzer = _angemeldeter_admin()
    try:
        anzahl = int(tage)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Die Zahl der Tage muss eine ganze Zahl sein.") from exc
    if anzahl < MIN_ERINNERUNG_TAGE or anzahl > MAX_ERINNERUNG_TAGE:
        raise ValidationError(
            f"Die Zahl der Tage muss zwischen {MIN_ERINNERUNG_TAGE} und "
            f"{MAX_ERINNERUNG_TAGE} liegen."
        )
    bis = _heute_gemeinde() + datetime.timedelta(days=anzahl)
    with SessionLocal() as sess:
        zeile = _stand_zeile(sess)
        zeile.erinnerung_ab = bis
        zeile.modified = datetime.datetime.now()
        zeile.modified_by = besitzer
        zeile.created_by = zeile.created_by or besitzer
        sess.commit()
    return {"erinnerung_ab": bis.isoformat(), "tage": anzahl}


@whitelist(methods=["POST"])
def kalender_vorschlag_anlegen(namen: Any = None, request=None) -> dict[str, Any]:
    """Legt die vom Assistenten vorgeschlagenen Kalender an (Frame 08).

    Die Vorschlaege („Gottesdienste“, „Gemeindekalender“) kommen vom Frontend.
    Angelegt wird von hoechstens ``MAX_KALENDER_VORSCHLAEGE`` Namen (F8): die
    Liste kommt vom Client, und ein Aufruf soll nicht beliebig viele Kalender
    anlegen. Danach ueber ``create_kalender`` — dieselbe Fachfunktion wie in
    der Kalenderverwaltung, inklusive ihrer Rechtepruefung. Bereits vorhandene
    Namen werden UEBERSPRUNGEN (kein Fehler), damit ein zweiter Klick nicht
    scheitert.
    """
    from diakronos_app.db import SessionLocal

    _angemeldeter_admin()
    if not isinstance(namen, (list, tuple)):
        raise ValidationError("Es wurde keine Liste von Kalendernamen uebergeben.")
    gewuenscht: list[str] = []
    for wert in namen:
        name = str(wert or "").strip()
        if not name:
            continue
        if len(name) > 140:
            raise ValidationError("Ein Kalendername ist zu lang (hoechstens 140 Zeichen).")
        if name not in gewuenscht:
            gewuenscht.append(name)
    if not gewuenscht:
        raise ValidationError("Es wurde kein Kalendername uebergeben.")
    if len(gewuenscht) > MAX_KALENDER_VORSCHLAEGE:
        raise ValidationError(
            f"Es wurden zu viele Kalender uebergeben (hoechstens "
            f"{MAX_KALENDER_VORSCHLAEGE})."
        )

    from diakronos_app.api.kronos.kalender_verwaltung import create_kalender
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError, PermissionError
    from diakronos_app.models.kronos import Kalender

    angelegt: list[str] = []
    uebersprungen: list[str] = []
    # ON-5 (E2-3): Frueher wurde JEDER ``FrappeCompatError`` als „uebersprungen“
    # gemeldet — auch ein Rechtemangel. Der Onboarding-Lauf zeigte damit den
    # stillen Fall in Reinform: HTTP 200, beide Kalender „uebersprungen“, in
    # Wahrheit aber keiner angelegt („Nur Kalenderadministratoren duerfen
    # Kalender verwalten.“). Jetzt wird unterschieden:
    #   * schon vorhanden / Duplikat  -> uebersprungen (kein Fehler)
    #   * alles andere (Rechte!)      -> Fehler an den Aufrufer, nichts still
    #     verworfen und nichts halb angelegt.
    with SessionLocal() as sess:
        vorhanden = {
            str(n).strip().lower()
            for (n,) in sess.query(Kalender.name)
        }
    for name in gewuenscht:
        if name.lower() in vorhanden:
            uebersprungen.append(name)
            continue
        try:
            create_kalender(name)
        except PermissionError as exc:
            # Fail closed: an dieser Stelle hat der Assistent bereits eine
            # Admin-Rolle geprueft — wenn ``create_kalender`` trotzdem
            # verweigert, fehlt die Kalenderrolle. Das ist eine Meldung an die
            # Person, kein stiller Verlust.
            logger.warning("Kalender %r nicht angelegt: %s", name, exc)
            raise PermissionError(
                "Die Kalender konnten nicht angelegt werden. Dafuer fehlt das "
                "Recht „Kalenderadministrator“ — bitte eine Person mit dieser "
                "Rolle fragen."
            ) from exc
        except FrappeCompatError as exc:
            # Ein Duplikat, das zwischen Lesen und Schreiben entstanden ist
            # (oder ein gleichnamiger Kalender ueber ``calendar_name``), ist
            # kein Fehler des Assistenten — ueberspringen und melden.
            logger.info("Kalender %r nicht angelegt: %s", name, exc)
            uebersprungen.append(name)
            continue
        angelegt.append(name)
        vorhanden.add(name.lower())
    return {"angelegt": angelegt, "uebersprungen": uebersprungen}
