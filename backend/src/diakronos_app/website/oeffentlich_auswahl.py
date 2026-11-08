"""BS-1b — Feld-Positivliste der oeffentlichen Website-Ausgabe.

Grundsatz G1 (Freigabe-Prinzip)
===============================
Nichts ist oeffentlich, solange es in Diakronos nicht ausdruecklich
freigegeben ist, und oeffentlich geht NUR heraus, was hier in einer
Positivliste steht. Es wird NIE eine ganze Zeile serialisiert
(das blosse Durchreichen der Zeile): ein neues Datenbankfeld waere
sonst beim naechsten Deploy stillschweigend oeffentlich, ohne dass jemand
darueber entschieden haette. Genau dafuer gibt es dieses Modul: die Auswahl
ist eine Liste von Namen, und ein Test haelt fest, dass keine Antwort einen
Schluessel ausserhalb dieser Listen traegt.

Was NIE oeffentlich ist (Kartenvorgabe, verbindlich)
----------------------------------------------------
Mitglieder-/Personendaten, Teilnehmer, ``mitarbeiter``, ``ablehnungs_grund``,
``ablaufplan``, ``dienstplan``, interne Kennungen von Personen,
E-Mail-Adressen, Autor-/Leiternamen.

Die Kennung eines Termins
-------------------------
``element.name`` ist eine interne Kennung (``gottesdienst-2026-11-01``) und
traegt in aller Regel schon den oeffentlichen Titel — sie ist aber KEIN
Geheimnis und war im Frappe-Original der UID des Kalenderfeeds. Fuer die
Website-Ausgabe wird sie nicht roh ausgeliefert, sondern als
:func:`oeffentliche_kennung` umgerechnet: ein gesalzener, gekuerzter
HMAC-Wert. Der Wert ist stabil (gleicher Termin -> gleiche Kennung), nicht
erratbar und rueckrechnungsfrei. Der iCal-Feed (L7) benutzt dieselbe
Umrechnung, damit ein Kalender-Client einen Termin ueber Aufrufe hinweg
wiedererkennt.
"""

from __future__ import annotations

import hashlib
import re
import secrets

from diakronos_app.settings import settings
from diakronos_app.website import oeffentlich_inhalt as inhalt

__all__ = [
    "FELDER_ANSPRECHPARTNER",
    "FELDER_BEITRAG",
    "FELDER_GRUPPE",
    "FELDER_KALENDER",
    "FELDER_TERMIN",
    "ansprechpartner_oeffentlich",
    "oeffentliche_kennung",
    "beitrag_oeffentlich",
    "gruppe_oeffentlich",
    "kalender_oeffentlich",
    "termin_oeffentlich",
]

# ── Feldlisten (die Allowlists selbst) ─────────────────────────────────────

#: Felder einer Kalender-Ausgabe (L1).
FELDER_KALENDER = ("slug", "titel", "farbe")

#: Felder einer Termin-Ausgabe (L2). ``gruppe``/``anmeldung_url`` sind
#: optional und nur gesetzt, wenn die jeweilige Bedingung erfuellt ist.
FELDER_TERMIN = (
    "id",
    "titel",
    "beginn",
    "ende",
    "ganztaegig",
    "beschreibung",
    "ort",
    "kategorie",
    "gruppe",
    "farbe",
    "anmeldung_url",
)

#: Felder einer Gruppen-Ausgabe (L4). ``naechste_termine`` nur im Detail.
FELDER_GRUPPE = (
    "slug",
    "name",
    "typ",
    "beschreibung",
    "treffzeit",
    "treffpunkt",
    "bild_url",
)

#: Felder einer Beitrags-Ausgabe (L5).
FELDER_BEITRAG = (
    "id",
    "titel",
    "datum",
    "kategorie",
    "auszug",
    "inhalt",
    "bild_url",
)

#: Felder eines Ansprechpartners (BS-3a, P3). Die Liste ist ABSICHTLICH kurz —
#: was hier nicht steht, geht nie hinaus: keine E-Mail, kein Telefon, keine
#: Adresse, kein Geburtsdatum, keine interne Personenkennung, kein
#: ``website_einwilligung`` (Einwilligungsdaten sind nichts für die
#: Öffentlichkeit, Kartenvorgabe BS-3a).
FELDER_ANSPRECHPARTNER = (
    "bereich",
    "funktion",
    "name",
    "foto_url",
    "postfach",
)


# ── Oeffentliche Kennung ───────────────────────────────────────────────────

#: Der Vorgabewert aus ``settings.secret_key`` — kein echtes Geheimnis und
#: deshalb KEIN gueltiges Salz (BS-1b2/F7, siehe ``oeffentliche_kennung``).
SECRET_KEY_PLATZHALTER = "insecure-dev-key"

#: Zufaelliges Salz dieses Prozesses (erst beim ersten Bedarf gezogen).
_PROZESSSALZ = ""


def oeffentliche_kennung(namespace: str, wert) -> str:
    """Stabile, nicht erratbare Kennung fuer die oeffentliche Ausgabe.

    ``oeffentliche_kennung("termin", "gottesdienst-2026-11-01")`` -> 32
    Hexzeichen. Gesalzen mit ``settings.secret_key`` (derselbe Umgang wie die
    Bremsenzaehler): wer die Kennung sieht, kann den internen Namen nicht
    ableiten; wer den internen Namen kennt, kann die Kennung nachrechnen —
    das ist gewollt (der Feed muss ueber Aufrufe hinweg stabil bleiben).

    Bewusst eine Einwegfunktion: ein Rueckweg auf ``element.name`` existiert
    nicht. Kein Rueckfall auf den nackten internen Namen und KEIN fester
    Ersatzwert: ohne ``secret_key`` waere das Salz in jedem Betrieb gleich und
    die Kennung damit trivial nachrechenbar. Fehlt er, wird deshalb ein
    ZUFAELLIGER Prozesswert benutzt (BS-1b2/F7) — die Kennung bleibt fuer
    diesen Prozess stabil (Feed-Aufrufe innerhalb einer Laufzeit passen
    zusammen), wechselt aber mit dem Neustart. Das ist die sichere Richtung:
    ein wechselnder UID ist kosmetisch, ein nachrechenbarer ist ein Leck.
    """
    salz = str(getattr(settings, "secret_key", "") or "").strip()
    if not salz or salz == SECRET_KEY_PLATZHALTER:
        salz = _prozesssalz()
    roh = f"{salz}|{namespace}|{wert}".encode()
    return hashlib.sha256(roh).hexdigest()[:32]


def _prozesssalz() -> str:
    """Zufaelliges Salz EINES Prozesses (einmal gezogen, dann fest)."""
    global _PROZESSSALZ
    if not _PROZESSSALZ:
        _PROZESSSALZ = secrets.token_hex(32)
    return _PROZESSSALZ


# ── Serialisierung je Art ──────────────────────────────────────────────────


def kalender_oeffentlich(slug: str, titel: str, farbe: str = "") -> dict:
    """Eine Kalender-Zeile (nur ``slug``, ``titel``, ``farbe``)."""
    return {
        "slug": str(slug or ""),
        "titel": inhalt.klartext(titel) or str(slug or ""),
        "farbe": _farbe(farbe),
    }


def _farbe(wert) -> str:
    """Farbwert nur durchreichen, wenn er ein Hex-Wert ist.

    Eine Farbe aus der Datenbank ist ein Anzeigewert; ein Freitext dort
    (``"rot"``, ``"red; background:url(…)"``) gehoert nicht in eine
    CSS-Variable der Website. Unbrauchbares wird leer — die Bausteine setzen
    dann ihre eigene Vorgabe.

    Geprueft wird auf ``#`` + 3, 4, 6 oder 8 Hexziffern (ON-0a/ON-0c: die
    Regel steht im Muster, nicht als Beispiel-Literal — der CSS-Waechter
    zaehlt jedes Farb-Literal in serverseitigem HTML).
    """
    text = str(wert or "").strip()
    if re.fullmatch(r"#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})", text):
        return text
    return ""


def termin_oeffentlich(
    zeile: dict,
    *,
    gruppe: dict | None = None,
    anmeldung_url: str | None = None,
) -> dict:
    """Ein Termin nach der Feld-Positivliste (L2).

    ``zeile`` ist eine Zeile des Termins (``element``) mit den Feldern
    ``name``, ``element_name``, ``element_start``, ``element_end``,
    ``all_day``, ``description``, ``element_color``, ``ressource``,
    ``element_category``, ``gruppe``. ``gruppe`` ist die bereits geprueft
    freigegebene Gruppe (``{"slug", "name"}``) oder ``None``.

    ``ort`` ist der Name der Ressource (Raum/Saal) — bewusst NICHT die
    interne Kennung, sondern der Anzeigename; fehlt er, bleibt das Feld leer.
    """
    name = str(zeile.get("name") or "")
    titel = inhalt.klartext(zeile.get("element_name")) or ""
    return {
        "id": oeffentliche_kennung("termin", name),
        "titel": titel,
        "beginn": inhalt.zeitpunkt(zeile.get("element_start")),
        "ende": inhalt.zeitpunkt(zeile.get("element_end")),
        "ganztaegig": bool(zeile.get("all_day")),
        "beschreibung": inhalt.klartext(zeile.get("description")),
        "ort": inhalt.klartext(zeile.get("ressource_name")),
        "kategorie": inhalt.klartext(zeile.get("kategorie_name")),
        # Ausdruecklich NUR die zwei erlaubten Felder — kein `dict(gruppe)`,
        # damit ein spaeter hinzugefuegtes Feld der Gruppe nicht mitkommt.
        "gruppe": (
            {"slug": str(gruppe.get("slug") or ""),
             "name": inhalt.klartext(gruppe.get("name"))}
            if gruppe
            else None
        ),
        "farbe": _farbe(zeile.get("element_color")),
        "anmeldung_url": str(anmeldung_url) if anmeldung_url else "",
    }


def gruppe_oeffentlich(zeile: dict, *, bild_url: str = "") -> dict:
    """Eine Gruppe nach der Feld-Positivliste (L4).

    Enthaelt NUR Slug, Name, Gruppentyp, Klartext-Beschreibung, Treffzeit,
    Treffpunkt und die Bild-Adresse. Verantwortliche, Leiter, Mitglieder,
    Dienstbereich und interne Kennungen bleiben draussen (G1).
    """
    slug = str(zeile.get("website_slug") or "")
    return {
        "slug": slug,
        "name": inhalt.klartext(zeile.get("gruppenname")),
        "typ": inhalt.klartext(zeile.get("typname")),
        "beschreibung": inhalt.klartext(zeile.get("beschreibung")),
        "treffzeit": inhalt.klartext(zeile.get("treffzeit")),
        "treffpunkt": inhalt.klartext(zeile.get("treffpunkt")),
        "bild_url": bild_url or "",
    }


def beitrag_oeffentlich(zeile: dict, *, bild_url: str = "") -> dict:
    """Ein Beitrag nach der Feld-Positivliste (L5).

    ``auszug`` ist Klartext, ``inhalt`` bereinigtes HTML (Allowlist). KEIN
    Autor, KEINE Autor-Adresse, kein ``owner``, kein interner Name.
    """
    return {
        "id": oeffentliche_kennung("beitrag", zeile.get("name")),
        "titel": inhalt.klartext(zeile.get("titel")),
        "datum": inhalt.frist(zeile.get("datum")),
        "kategorie": inhalt.klartext(zeile.get("kategorie")),
        "auszug": inhalt.klartext(zeile.get("auszug")),
        "inhalt": inhalt.html_erlaubt(zeile.get("inhalt")),
        "bild_url": bild_url or "",
    }


def ansprechpartner_oeffentlich(zeile: dict) -> dict:
    """Ein Ansprechpartner nach der Feld-Positivliste (BS-3a/P3).

    ``zeile`` kommt aus :func:`oeffentlich_daten.ansprechpartner` und enthält
    NUR ``bereich``, ``funktion``, ``name``, ``foto_url``, ``postfach``.
    Es wird nichts ergänzt, nichts umbenannt: der Aufrufer (Datenfunktion) hat
    die Felder schon ausgewählt, diese Funktion hält die Liste sichtbar an
    EINER Stelle (und der Test prüft sie negativ).

    ``postfach`` ist ``None``, wenn der Bereich kein Kontakt-Postfach hat —
    dann gibt es auf der Website keinen Kontakt-Knopf für diesen Eintrag.
    Eine E-Mail-Adresse kommt hier NIE an: ``postfach`` ist ein Slug.
    """
    return {
        "bereich": inhalt.klartext(zeile.get("bereich")),
        "funktion": inhalt.klartext(zeile.get("funktion")),
        "name": inhalt.klartext(zeile.get("name")),
        "foto_url": str(zeile.get("foto_url") or ""),
        "postfach": (
            str(zeile.get("postfach"))
            if zeile.get("postfach")
            else None
        ),
    }
