"""BS-1a — Website-Freigaben: Rollen, Slugs und Postfaecher (eine Wahrheit).

Warum dieses Modul
==================
Die Verwaltungs-API (``api/website.py``) und die spaeteren oeffentlichen
Bausteine (BS-1b/1c/1d) brauchen DIESELBEN Regeln:

  * wer freigeben darf (Rollen),
  * was ein gueltiger Slug ist und welche Werte reserviert sind,
  * wie ein Slug aus einem Anzeigenamen entsteht,
  * welche Postfaecher das Kontaktformular oeffentlich anbieten darf und was
    gilt, wenn keine Zeile existiert (Abwaertskompatibilitaet WEB-10).

Liegen diese Regeln im Endpunkt, muesste jede oeffentliche Ausgabe sie neu
erfinden — genau die Art von Doppelung, die schon einmal auseinandergelaufen
ist. Deshalb hier, importierbar und ohne HTTP.

Freigabe-Prinzip (G1)
=====================
Nichts ist oeffentlich, solange es nicht ausdruecklich freigegeben ist. Dieses
Modul erzeugt KEINE Oeffentlichkeit: es liest und schreibt nur die Schalter.
Die Feld-Positivliste fuer die spaetere oeffentliche Ausgabe steht bewusst
NICHT hier — sie gehoert zur jeweiligen Ausgabe (BS-1b/1c/1d) und wird dort
geprueft.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Rollen mit Zugriff auf die Website-Verwaltung. EINE Quelle ist
#: ``website.primo.WEBSITE_ROLLEN`` (WEB-1b); hier nur der sprechende Name —
#: eine zweite Liste wuerde bei der naechsten Rollenaenderung abweichen.
from diakronos_app.website.primo import WEBSITE_ROLLEN

#: Slugs, die die Technik selbst belegt. ``standard`` ist der Slug des
#: Rueckfall-Postfachs (WEB-10) und deshalb ebenfalls reserviert.
RESERVIERTE_SLUGS: frozenset[str] = frozenset(
    {
        "diakronos",
        "primo",
        "admin",
        "api",
        "login",
        "standard",
    }
)

#: Erlaubte Zeichen eines Slugs: klein, Ziffern, Bindestrich. ``_`` ist
#: bewusst NICHT erlaubt (Kartenvorgabe: reserviert/abzulehnen).
_SLUG_ERLAUBT = re.compile(r"^[a-z0-9-]+$")

#: Hoechstlaenge eines Slugs / Anzeigenamens (Spalte ist VARCHAR(140)).
SLUG_MAX = 140
BEZEICHNUNG_MAX = 140
EMAIL_MAX = 320

#: Slug des Rueckfall-Postfachs ohne Zeilen in ``website_kontakt_postfach``.
POSTFACH_STANDARD = "standard"
#: Bezeichnung des Rueckfall-Postfachs (WEB-10-Verhalten: eine Adresse,
#: keine Auswahl im Formular).
POSTFACH_STANDARD_BEZEICHNUNG = "Allgemein"

#: Arten, die ``freigabe_setzen`` kennt.
ARTEN = ("kalender", "gruppe")


class SlugUngueltig(ValueError):
    """Der Slug verletzt Form oder Reservierungsliste (Meldung ist deutsch)."""


def darf_website(rollen: list[str] | tuple[str, ...]) -> bool:
    """True, wenn die Rollenliste die Website-Verwaltung sehen darf."""
    vorhanden = {str(r or "").strip() for r in rollen}
    return any(rolle in vorhanden for rolle in WEBSITE_ROLLEN)


def slug_pruefen(wert: object) -> str:
    """Prueft einen vom Benutzer gelieferten Slug und gibt ihn normalisiert zurueck.

    Regeln: nur ``[a-z0-9-]``, hoechstens :data:`SLUG_MAX` Zeichen, nicht
    reserviert. Grossbuchstaben werden NICHT still umgewandelt — ein
    eingetippter Slug soll so gespeichert werden, wie er dasteht, oder
    abgelehnt werden. Wirft :class:`SlugUngueltig` mit einer Meldung, die der
    Verwaltung direkt angezeigt werden kann (keine Python-Signatur, SEC-7/8).
    """
    text = str(wert or "").strip()
    if not text:
        raise SlugUngueltig("Bitte einen Kürzel angeben (z. B. „gemeinde“).")
    if len(text) > SLUG_MAX:
        raise SlugUngueltig(
            f"Der Kürzel darf höchstens {SLUG_MAX} Zeichen lang sein."
        )
    if text.lower() in RESERVIERTE_SLUGS:
        raise SlugUngueltig("Dieser Kürzel ist reserviert. Bitte einen anderen wählen.")
    if not _SLUG_ERLAUBT.match(text):
        raise SlugUngueltig(
            "Der Kürzel darf nur Kleinbuchstaben, Ziffern und Bindestriche "
            "enthalten."
        )
    if text.startswith("-") or text.endswith("-"):
        raise SlugUngueltig("Der Kürzel darf nicht mit einem Bindestrich beginnen oder enden.")
    return text


def slug_aus_text(text: object, *, fallback: str = "bereich") -> str:
    """Leitet einen URL-sicheren Slug aus einem Anzeigenamen ab.

    Umlaute werden aufgeloest (ä -> ae …), Grossbuchstaben klein, alles
    andere zu ``-`` zusammengefasst. Bleibt nichts uebrig (z. B. nur
    Sonderzeichen), kommt ``fallback`` zurueck. Das Ergebnis ist nach
    :func:`slug_pruefen` gueltig; ist dann noch ein reservierter Wert
    getroffen, wird ``fallback`` verwendet — die Verwaltung sieht ihn im
    Formular und kann ihn aendern.
    """
    roh = str(text or "").strip()
    ersetzt = (
        roh.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "ae")
        .replace("Ö", "oe")
        .replace("Ü", "ue")
        .replace("ß", "ss")
    )
    # Restliche Akzente (é -> e) ueber NFKD zerlegen und Marken entfernen.
    zerlegt = unicodedata.normalize("NFKD", ersetzt)
    ascii_text = "".join(z for z in zerlegt if not unicodedata.combining(z))
    klein = ascii_text.lower()
    klein = re.sub(r"[^a-z0-9]+", "-", klein).strip("-")
    if len(klein) > SLUG_MAX:
        klein = klein[:SLUG_MAX].rstrip("-")
    if not klein or klein in RESERVIERTE_SLUGS:
        klein = fallback
    return klein


#: Erster Zusatz fuer einen abgeleiteten Slug, der schon vergeben ist (BS-1a2/F3).
SLUG_ZUSATZ_AB = 2


def slug_verfuegbar(basis: str, belegt) -> str:
    """Erster freier Slug ab ``basis``: ``basis``, ``basis-2``, ``basis-3`` …

    Fuer ABGELEITETE Slugs (BS-1a2/F3): zwei Kalender duerfen denselben
    Anzeigenamen tragen („Gottesdienst“), der Slug muss trotzdem eindeutig
    sein. ``belegt`` ist ein Aufruf ``belegt(slug) -> bool``; er wird erst
    gefragt, wenn ``basis`` nicht mehr in :data:`SLUG_MAX` passt bzw. fuer
    jeden Zusatz. Der Zusatz gehoert in den Slug (Laengengrenze!), ein
    abgeschnittenes ``basis`` wird deshalb vorher gekuerzt.

    Ein AUSDRUECKLICH eingegebener Slug laeuft hier NICHT durch — dort bleibt
    ein Konflikt ein Fehler: was ein Mensch getippt hat, wird nicht
    stillschweigend umbenannt.
    """
    start = str(basis or "").strip()
    if not start:
        raise SlugUngueltig("Bitte einen Kürzel angeben (z. B. „gemeinde“).")
    if not belegt(start):
        return start
    for nummer in range(SLUG_ZUSATZ_AB, SLUG_ZUSATZ_AB + 1000):
        zusatz = f"-{nummer}"
        stamm = start[: SLUG_MAX - len(zusatz)].rstrip("-")
        if not stamm:
            raise SlugUngueltig(
                f"Zu viele Einträge mit demselben Namen ({start})."
            )
        kandidat = f"{stamm}{zusatz}"
        if not belegt(kandidat):
            return kandidat
    raise SlugUngueltig(f"Zu viele Einträge mit demselben Namen ({start}).")


@dataclass(frozen=True)
class Postfach:
    """Ein Postfach, wie es die Verwaltung und das Formular sehen."""

    slug: str
    bezeichnung: str
    email: str
    aktiv: bool

    def als_dict(self) -> dict:
        return {
            "slug": self.slug,
            "bezeichnung": self.bezeichnung,
            "email": self.email,
            "aktiv": bool(self.aktiv),
        }


def postfaecher_lesen(session) -> list[Postfach]:
    """Alle Postfaecher, sortiert nach ``sortierung``, dann ``slug``."""
    from sqlalchemy import select

    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    zeilen = session.execute(
        select(WebsiteKontaktPostfach).order_by(
            WebsiteKontaktPostfach.sortierung, WebsiteKontaktPostfach.slug
        )
    ).scalars().all()
    return [
        Postfach(
            slug=z.slug,
            bezeichnung=z.bezeichnung,
            email=z.email,
            aktiv=bool(z.aktiv),
        )
        for z in zeilen
    ]


def postfaecher_oeffentlich(session, empfaenger_standard: str) -> list[Postfach]:
    """Postfaecher fuer das OEFFENTLICHE Formular (nur aktive).

    Ist keine Zeile vorhanden, gilt ``WEBSITE_KONTAKT_EMPFAENGER``
    (``empfaenger_standard``) als Postfach ``standard`` — das Formular
    verhaelt sich dann unveraendert wie vor BS-1a (WEB-10). Ist die
    Einstellung leer UND gibt es keine Zeile, ist die Liste LEER: das
    Formular ist dann nicht eingerichtet (der Aufrufer antwortet 503, wie
    bisher).

    Die E-Mail-Adresse steht NUR in dieser verwaltungsnahen Struktur; die
    oeffentliche Ausgabe (BS-1d) darf daraus hoechstens Slug und Bezeichnung
    veroeffentlichen (G1: keine Adressen).
    """
    vorhanden = postfaecher_lesen(session)
    aktive = [p for p in vorhanden if p.aktiv]
    if aktive:
        return aktive
    if vorhanden:
        # Es gibt Postfaecher, aber keines ist aktiv: die Gemeinde hat die
        # Auswahl bewusst abgeschaltet. Kein stiller Rueckfall auf WEB-10.
        return []
    adresse = str(empfaenger_standard or "").strip()
    if not adresse:
        return []
    return [
        Postfach(
            slug=POSTFACH_STANDARD,
            bezeichnung=POSTFACH_STANDARD_BEZEICHNUNG,
            email=adresse,
            aktiv=True,
        )
    ]


__all__ = [
    "ARTEN",
    "BEZEICHNUNG_MAX",
    "EMAIL_MAX",
    "POSTFACH_STANDARD",
    "POSTFACH_STANDARD_BEZEICHNUNG",
    "Postfach",
    "RESERVIERTE_SLUGS",
    "SLUG_MAX",
    "SlugUngueltig",
    "darf_website",
    "postfaecher_lesen",
    "postfaecher_oeffentlich",
    "slug_aus_text",
    "slug_pruefen",
    "slug_verfuegbar",
]
