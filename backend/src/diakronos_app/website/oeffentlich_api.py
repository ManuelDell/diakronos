"""BS-1b — Oeffentliche LESE-API fuer die Website-Bausteine (Diakronos x Primo).

Sechs Endpunkte, alle ``allow_guest=True`` und alle NUR GET:

    website.oeffentlich.kalender                          (L1)
    website.oeffentlich.termine                           (L2)
    website.oeffentlich.naechster_termin                  (L3)
    website.oeffentlich.gruppen                           (L4)
    website.oeffentlich.gruppe                            (L4)
    website.oeffentlich.beitraege                         (L5)

Dazu drei HTTP-Routen AUSSERHALB des Methoden-Routers (sie brauchen eigene
Inhaltstypen bzw. eine CORS-Antwort ohne Sitzung):

    GET {Praefix}/website/ical/{kalender-slug}.ics        (L7)
    GET {Praefix}/website/bild/{art}/{slug}               (L6)
    GET {Praefix}/website/oeffentlich/{funktion}          (L1–L5, CORS-Variante)

Warum die Lese-Endpunkte ZWEI Adressen haben
============================================
Der Methoden-Router (``/api/method/<pfad>``) ist der Weg, den die SPA und
Pruefwerkzeuge kennen — dort liegen auch die Verwaltungsendpunkte aus BS-1a.
Er setzt aber KEINE CORS-Kopfzeilen (die Middleware ist auf ``Sec-Fetch-Site``
ausgerichtet und nicht auf fremde, aber erlaubte Herkuenfte). Eine Website auf
eigener Herkunft (``PRIMO_PUBLIC_URL``) braucht genau diese Koepfe. Deshalb
gibt es dieselben Funktionen zusaetzlich unter ``/website/oeffentlich/<name>``
— gleicher Code, gleiche Filter, plus CORS. Beide Wege sind im Vertrag
dokumentiert; BS-2* darf beide benutzen.

Freigabe (G1)
=============
Nichts ist oeffentlich, solange es in Diakronos nicht freigegeben ist:
Default AUS, nur eine Feld-Positivliste geht hinaus
(``website/oeffentlich_auswahl.py``), keine Personendaten, keine Adressen,
keine internen Kennungen. Ein einzelner, nicht freigegebener Slug wird still
verworfen (die Antwort verraet nicht, dass es ihn gibt); eine nicht
freigegebene Einzelressource (Gruppe per Slug, iCal, Bild) antwortet 404.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from diakronos_app.frappe_compat import whitelist

FRAPPE_MODULE = "diakronos.diakronos.api.website"

logger = logging.getLogger("diakronos_app.website.oeffentlich")

#: Kurzpfad-Praefix der Lese-API (Register + HTTP-Routen).
KURZPFAD = "website.oeffentlich"


def _bremse(request):
    """Zaehlt den Aufruf und liefert ``None`` oder die 429-Antwort.

    FAIL CLOSED: ist Redis nicht erreichbar, wird NICHT gelesen (503 bzw.
    429 nach aussen — beides ohne Interna). Dieselbe Entscheidung wie im
    Kontaktformular (WEB-10): lieber eine Anfrage weniger als ein
    ungebremster Weg.
    """
    from diakronos_app import request_context
    from diakronos_app.website import oeffentlich_bremse as bremse
    from diakronos_app.website import oeffentlich_http as http

    try:
        erlaubt, grund = bremse.pruefe(request_context.zaehler_client_ip())
    except Exception as ex:  # noqa: BLE001 — Bremse faellt aus: fail closed
        logger.warning(
            "Website-Lese-API: Bremse nicht erreichbar (%s).", type(ex).__name__
        )
        return http.fehler(
            "Die Website ist gerade nicht verfügbar. Bitte später erneut.",
            "RateLimitError",
            503,
            request,
        )
    if not erlaubt:
        logger.info("Website-Lese-API gebremst (Grund=%s).", grund or "unbekannt")
        return http.fehler(
            bremse.fehlermeldung(), "RateLimitError", 429, request
        )
    return None


def _liefert(request, antwort_teil: str = ""):
    """Gemeinsamer Eingang: Methode -> Bremse -> Antwort.

    Rueckgabe: ``None``, wenn der Aufruf weiterlaufen darf — sonst die fertige
    Antwort (405/429/503). Die Reihenfolge ist bewusst: erst die Methode
    (kostet nichts), dann die Bremse (kostet einen Redis-Aufruf), zuletzt die
    Datenbank.
    """
    from diakronos_app.website import oeffentlich_http as http

    if request is not None and str(getattr(request, "method", "GET")).upper() == "OPTIONS":
        return http.optionen_antwort(request)
    abweisung = http.methoden_abweisung(request)
    if abweisung is not None:
        return abweisung
    return _bremse(request)


def _lesen(fn, *args, **kwargs):
    """Fuehrt eine Datenfunktion in einer Lesesitzung aus."""
    from diakronos_app.db import lesesitzung

    with lesesitzung() as sess:
        return fn(sess, *args, **kwargs)


def _liste(wert) -> list[str]:
    """Parameter als Liste: ``"a,b"``, ``["a","b"]`` oder ``"a"``."""
    if wert is None:
        return []
    if isinstance(wert, (list, tuple, set)):
        teile = [str(t) for t in wert]
    else:
        teile = str(wert).split(",")
    return [t.strip() for t in teile if str(t).strip()]


def _wahr(wert) -> bool:
    """Parameter als Schalter: ``1/true/ja/on`` (auch ``"0"`` = falsch)."""
    if isinstance(wert, bool):
        return wert
    if wert is None:
        return False
    return str(wert).strip().lower() in {"1", "true", "ja", "on", "yes"}


def _zahl(wert, vorgabe: int) -> int:
    """Parameter als Zahl; unbrauchbare Angaben fallen auf die Vorgabe zurueck."""
    try:
        return int(str(wert).strip())
    except (TypeError, ValueError):
        return vorgabe


# ═══════════════════════════════════════════════════════════════════════════
# L1 — Kalender
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def kalender(request=None):
    """Freigegebene Kalender der Website: ``[{"slug", "titel", "farbe"}]``.

    Leer, solange kein Kalender in Diakronos freigegeben ist (Default AUS).
    Keine Kennungen, keine Moderator-/Leserechtslisten — nur was ein Baustein
    zum Beschriften und Faerben braucht.
    """
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    return _lesen(daten.kalender)


# ═══════════════════════════════════════════════════════════════════════════
# L2 — Termine
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def termine(request=None, kalender=None, von=None, bis=None, kategorie=None,
            gruppe=None, limit=None, nur_anmeldung=None):
    """Freigegebene Termine im Zeitfenster (Liste, nach Beginn sortiert).

    Parameter:
      ``kalender``  Slug, mehrere mit Komma (``"gottesdienste,jugend"``) oder
                    wiederholt; ohne Angabe ALLE freigegebenen Kalender.
      ``von``/``bis``  ``JJJJ-MM-TT``; Vorgabe heute .. +90 Tage, hoechstens
                    400 Tage Fenster (laengere Angaben werden gekuerzt).
      ``kategorie`` Name oder Kennung einer Eventkategorie — nur oeffentliche
                    Kategorien wirken (sonst leere Liste).
      ``gruppe``    Slug einer freigegebenen Gruppe.
      ``limit``     Vorgabe 50, hoechstens 500.
      ``nur_anmeldung``  ``1``/``true``/``ja``/``on`` = nur Termine, fuer die
                    die Website eine ANMELDUNG anbietet (``anmeldung_url``
                    gesetzt). Ein Baustein „Termine mit offener Anmeldung"
                    fragt damit, statt ein grosses Fenster zu holen und im
                    Browser zu filtern (BS-2c2). ``limit`` gilt fuer das
                    Ergebnis, nicht fuer die Vorauswahl.

    Antwort: Liste von Terminen nach der Feld-Positivliste
    (``website/oeffentlich_auswahl.FELDER_TERMIN``).
    """
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    ergebnis = _lesen(
        daten.termine,
        kalender=_liste(kalender),
        von=von,
        bis=bis,
        kategorie=(str(kategorie).strip() if kategorie else None),
        gruppe=(str(gruppe).strip() if gruppe else None),
        nur_anmeldung=_wahr(nur_anmeldung),
        limit=_zahl(limit, daten.LIMIT_STANDARD),
    )
    if _wahr(nur_anmeldung):
        # Ein Termin mit „Anmeldung aktiv", aber ohne tauglichen Link, hat
        # keine Adresse anzubieten — der gehoert NICHT in diese Liste.
        ergebnis = [t for t in ergebnis if t.get("anmeldung_url")]
    return ergebnis


# ═══════════════════════════════════════════════════════════════════════════
# L3 — naechster Termin
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def naechster_termin(request=None, kategorie=None, kalender=None, gruppe=None):
    """Der naechste freigegebene Termin ab heute — oder ``null``.

    ``kategorie``/``kalender``/``gruppe`` optional (Filter wie L2). Die
    Antwortform ist GENAU die eines Listeneintrags aus L2: ein Baustein kann
    damit die Darstellung ohne Sonderfall teilen.
    """
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    treffer = _lesen(
        daten.naechste_termine,
        kategorie=(str(kategorie).strip() if kategorie else None),
        kalender=(str(kalender).strip() if kalender else None),
        gruppe=(str(gruppe).strip() if gruppe else None),
        limit=1,
    )
    return treffer[0] if treffer else None


# ═══════════════════════════════════════════════════════════════════════════
# L4 — Gruppen
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def gruppen(request=None, typ=None):
    """Freigegebene Gruppen: ``[{slug, name, typ, beschreibung, treffzeit,
    treffpunkt, bild_url}]`` (nach Name sortiert).

    ``typ`` filtert auf den Gruppentyp (Name der Typzeile). KEINE
    Verantwortlichen, Leiter oder Mitglieder (G1).
    """
    from diakronos_app.website import oeffentlich_auswahl as auswahl
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    zeilen = _lesen(daten.gruppen, typ=(str(typ).strip() if typ else None))
    ergebnis = [
        auswahl.gruppe_oeffentlich(
            z, bild_url=(inhalt_bild_url("gruppe", z["website_slug"]) if z["bild"] else "")
        )
        for z in zeilen
    ]
    return ergebnis


@whitelist(methods=["GET"], allow_guest=True)
def gruppe(request=None, slug=None):
    """Eine freigegebene Gruppe samt ``naechste_termine`` (max. 10) — sonst 404.

    Die naechsten Termine stammen ausschliesslich aus FREIGEGEBENEN Kalendern
    und tragen dieselbe Feld-Positivliste wie L2.
    """
    from diakronos_app.website import oeffentlich_auswahl as auswahl
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    treffer = _lesen(daten.gruppe_detail, str(slug or "").strip())
    if treffer is None:
        return http.fehler("Nicht gefunden.", "DoesNotExistError", 404, request)
    ausgabe = auswahl.gruppe_oeffentlich(
        treffer,
        bild_url=(
            inhalt_bild_url("gruppe", treffer["website_slug"]) if treffer["bild"] else ""
        ),
    )
    ausgabe["naechste_termine"] = treffer["naechste_termine"]
    return ausgabe


def inhalt_bild_url(art: str, slug: str) -> str:
    """Bild-Adresse (praefixbewusst) — duenne Huelle um ``oeffentlich_inhalt``."""
    from diakronos_app.website.oeffentlich_inhalt import bild_url

    return bild_url(art, slug)


# ═══════════════════════════════════════════════════════════════════════════
# L5 — Beitraege
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def beitraege(request=None, limit=None, kategorie=None):
    """Veroeffentlichte Beitraege, die auf der Website stehen (neueste zuerst).

    ``limit`` Vorgabe 10, hoechstens 50; ``kategorie`` filtert auf den
    Kategorienamen des Beitrags. ``inhalt`` ist bereinigtes HTML (Allowlist
    ``p, br, strong, em, ul, ol, li, a[href http/https/mailto], h2, h3,
    blockquote``), ``auszug`` Klartext. KEIN Autor, KEINE Adresse.
    """
    from diakronos_app.website import oeffentlich_auswahl as auswahl
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    zeilen = _lesen(
        daten.beitraege_oeffentlich,
        limit=_zahl(limit, daten.BEITRAEGE_LIMIT_STANDARD),
        kategorie=(str(kategorie).strip() if kategorie else None),
    )
    ergebnis = []
    for zeile in zeilen:
        bild = ""
        # Die Bild-Route adressiert Beitraege ueber ihre OEFFENTLICHE Kennung.
        if zeile.get("bild"):
            bild = inhalt_bild_url(
                "beitrag", auswahl.oeffentliche_kennung("beitrag", zeile["name"])
            )
        ergebnis.append(auswahl.beitrag_oeffentlich(zeile, bild_url=bild))
    return ergebnis


# ═══════════════════════════════════════════════════════════════════════════
# L7 — iCal-Feed
# ═══════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════
# BS-3a — Ansprechpartner (mit Einwilligung)
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(methods=["GET"], allow_guest=True)
def ansprechpartner(request=None, bereich=None):
    """Ansprechpartner mit Einwilligung: ``[{bereich, funktion, name,
    foto_url, postfach}]`` (BS-3a, P3).

    Zwei Bedingungen, beide Pflicht:

      1. Die Verwaltung hat die Funktion ausgewaehlt
         (``website.ansprechpartner_bereiche_setzen``),
      2. die Person hat selbst zugestimmt (``website_einwilligung``).

    Ohne Zustimmung erscheint NIEMAND — auch nicht als Platzhalter und auch
    nicht mit Namen. Der Widerruf wirkt sofort (bei jeder Anfrage neu gelesen).

    ``bereich`` filtert optional auf den Anzeigenamen. Es gehen NUR die Felder
    aus ``oeffentlich_auswahl.FELDER_ANSPRECHPARTNER`` hinaus: keine E-Mail,
    kein Telefon, keine Adresse, kein Geburtsdatum, keine interne Kennung der
    Person und keine Einwilligungsdaten. ``foto_url`` ist nur gesetzt, wenn die
    Person auch dem Bild zugestimmt hat; ``postfach`` ist ein Slug (BS-1a),
    keine Adresse, und ``null``, wenn der Bereich kein Postfach hat.
    """
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung
    return _lesen(daten.ansprechpartner,
                  bereich=(str(bereich).strip() if bereich else None))


def _ical_inhalt(kalender_slug: str) -> tuple[str, str] | None:
    """``(dateiname_slug, ics_text)`` eines freigegebenen Kalenders — sonst ``None``."""
    from diakronos_app.website import oeffentlich_daten as daten
    from diakronos_app.website import oeffentlich_inhalt as inhalt
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    bestand = _lesen(daten.ical_termine, str(kalender_slug or "").strip())
    if bestand is None:
        return None
    info = bestand["kalender"]
    eintraege = []
    for zeile in bestand["termine"]:
        eintraege.append(
            {
                # Derselbe UID wie die Kennung in der JSON-Ausgabe: der
                # Kalender-Client erkennt einen Termin wieder, auch wenn
                # Titel oder Zeit verschoben wurden.
                "uid": f"{auswahl.oeffentliche_kennung('termin', zeile['name'])}"
                       "@diakronos",
                "titel": inhalt.klartext(zeile.get("element_name")),
                "beginn": zeile.get("element_start"),
                "ende": zeile.get("element_end"),
                "ganztaegig": bool(zeile.get("all_day")),
                "beschreibung": inhalt.klartext(zeile.get("description")),
                "ort": inhalt.klartext(zeile.get("ressource_name")),
                "stand": zeile.get("modified"),
            }
        )
    return (
        str(info["slug"]),
        inhalt.kalender_ics(eintraege, name=str(info["titel"] or "")),
    )


def ical_route(request):
    """``GET {Praefix}/website/ical/{kalender-slug}.ics`` (L7).

    Nicht freigegebener/unbekannter Kalender -> 404 (die Antwort verraet
    nicht, ob es ihn gibt). Inhaltstyp ``text/calendar; charset=utf-8``,
    ``Content-Disposition: inline`` (ein Kalender-Abo soll im Browser
    ankommen, nicht als Download in einem Ordner landen), Cache 5 Minuten.

    ``Vary: Origin`` steht trotzdem drauf (BS-1b2/F6): Kalender-Clients
    senden zwar keinen ``Origin``, ein Browser-Aufruf der Adresse kann aber
    einen CORS-Kopf bekommen — ohne ``Vary`` wuerde ein Zwischenspeicher diese
    Antwort auch einem Aufrufer ohne Berechtigung ausliefern.
    """
    from starlette.responses import Response

    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung

    pfad = str(getattr(getattr(request, "url", None), "path", "") or "")
    slug = pfad.rsplit("/", 1)[-1]
    if slug.lower().endswith(".ics"):
        slug = slug[: -len(".ics")]
    try:
        from urllib.parse import unquote

        slug = unquote(slug)
    except Exception:  # noqa: BLE001 — kaputtes Prozentzeichen: 404
        slug = ""

    bestand = _ical_inhalt(slug)
    if bestand is None:
        return http.fehler("Nicht gefunden.", "DoesNotExistError", 404, request)
    _, text = bestand
    antwort = Response(
        content=text.encode("utf-8"),
        status_code=200,
        media_type="text/calendar; charset=utf-8",
    )
    antwort.headers["Content-Disposition"] = f'inline; filename="{slug}.ics"'
    antwort.headers["Cache-Control"] = f"public, max-age={http.CACHE_SEKUNDEN}"
    # BS-1b2 (F6): derselbe Zwischenspeicher-Schutz wie bei den JSON-Antworten
    # — sonst bekaeme ein Aufrufer ohne CORS-Berechtigung eine Antwort MIT
    # CORS-Kopf aus dem Cache (der eine darfs, der andere nicht).
    antwort.headers[http.ORIGIN_HEADER] = "Origin"
    return http.cors_kopf(antwort, request)


# ═══════════════════════════════════════════════════════════════════════════
# L6 — oeffentliche Bilder
# ═══════════════════════════════════════════════════════════════════════════

#: Erlaubte Bild-Inhaltstypen (Endung -> Typ). NUR Rasterformate: SVG kann
#: Skript enthalten und wird deshalb nicht ausgeliefert.
_BILD_TYPEN = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
#: Groesste ausgelieferte Bilddatei (Bytes). Ein Bild der Website ist ein
#: Anzeigewert; alles darueber ist kein Foto, sondern ein Versehen.
_BILD_MAX = 12 * 1024 * 1024


def _bild_datei(wert) -> tuple[str, bytes] | None:
    """``(content_type, bytes)`` eines Bildwerts aus ``bild``/``img`` — sonst ``None``.

    Der Datenbankwert ist eine Datei-URL (``/files/x.png``,
    ``/private/files/x.png``) oder ein Dateiname. Gelesen wird ueber
    ``files.stored_path`` — dieselbe Pruefung wie die Anmeldungs-Bilder
    (kein Pfad, kein ``..``, kein Symlink, kein Ausbruch aus dem Ordner).
    """
    from pathlib import Path

    from diakronos_app.files import stored_path

    roh = str(wert or "").strip()
    if not roh:
        return None
    dateiname = roh.rsplit("/", 1)[-1]
    pfad = stored_path(dateiname)
    if pfad is None:
        return None
    typ = _BILD_TYPEN.get(Path(dateiname).suffix.lower())
    if typ is None:
        return None
    try:
        if pfad.stat().st_size > _BILD_MAX:
            return None
        daten = pfad.read_bytes()
    except OSError:
        return None
    # Inhalt gegen die Endung pruefen: eine umbenannte HTML-Datei ist kein Bild.
    from diakronos_app.files import binary_content_type

    erkannt = binary_content_type(daten[:4096])
    if erkannt is None or not erkannt.startswith("image/"):
        return None
    return typ, daten


def _oeffentliches_bild(art: str, slug: str) -> tuple[str, bytes] | None:
    """Bild eines FREIGEGEBENEN Objekts (L6) — sonst ``None`` (-> 404).

    ``art`` ist ``gruppe`` oder ``beitrag``; der Slug ist bei Gruppen der
    ``website_slug``, bei Beitraegen die oeffentliche Kennung. Geprueft wird
    dieselbe Freigabe wie in L4/L5 — ein Bild ist nur oeffentlich, weil sein
    Objekt es ist.

    BS-1b2 (F3): Die Gruppe laeuft ueber ``daten.freigegebene_gruppe`` —
    dieselbe Funktion wie die Liste. Vorher prueft diese Route nur
    ``website_freigabe`` und lieferte damit auch das Bild einer VERSTECKTEN
    Gruppe aus (``sichtbarkeit == "Versteckt"``).
    """
    from diakronos_app.models.diakonos import Beitrag
    from diakronos_app.db import lesesitzung
    from diakronos_app.website import oeffentlich_auswahl as auswahl
    from diakronos_app.website import oeffentlich_daten as daten

    kennung = str(slug or "").strip()
    if not kennung:
        return None
    with lesesitzung() as sess:
        if art == "gruppe":
            treffer_gruppe = daten.freigegebene_gruppe(sess, kennung)
            if treffer_gruppe is None:
                return None
            wert = treffer_gruppe.get("bild")
        elif art == "person":
            # BS-3a: das Bild einer Person nur bei EIGENER Einwilligung UND
            # eigener Foto-Zustimmung. Kennung ist die gesalzene
            # oeffentliche Kennung, nicht ``mitglied.name`` — aus der Adresse
            # laesst sich kein Personenname ableiten. Der Widerruf wirkt
            # sofort: die Bedingungen werden je Aufruf neu geprueft.
            #
            # NACHTRAG 2 (MITTEL 2) — zwei Luecken geschlossen:
            #   * bisher genuegte die Foto-Zustimmung; ein ausgetretener Mensch
            #     behielt damit seinen Bildpfad. Jetzt entscheidet DIESELBE
            #     Regel wie in der L4/L5-Ausgabe: `einwilligung.ist_oeffentlich`
            #     (Einwilligung + Name + nicht ausgeschieden),
            #   * ausserdem muss die Person AKTUELL als Ansprechpartner
            #     ausgewaehlt sein (`daten.oeffentliche_ansprechpartner_personen`)
            #     — sonst waere jedes freigegebene Mitgliederfoto ueber eine
            #     geratene Kennung abrufbar. Dieselbe Funktion fuehrt den
            #     Hash-Index: der Abgleich laeuft gegen die Handvoll
            #     ausgewaehlter Personen, nicht gegen alle Mitglieder.
            from diakronos_app.website import einwilligung as einwilligung_regel

            if not daten.person_ist_oeffentlicher_ansprechpartner(sess, kennung):
                return None
            treffer_person = daten.mitglied_zu_oeffentlicher_kennung(sess, kennung)
            if treffer_person is None:
                return None
            if not einwilligung_regel.ist_oeffentlich(treffer_person):
                return None
            if not einwilligung_regel.foto_erlaubt(treffer_person):
                return None
            wert = treffer_person.foto
        elif art == "beitrag":
            gesucht = kennung
            treffer = None
            for zeile in sess.query(Beitrag).filter(
                Beitrag.veroeffentlicht.is_(True),
                Beitrag.auf_website.is_(True),
                # UX2b: kein Bild eines Beitrags im Papierkorb.
                Beitrag.geloescht_am.is_(None),
            ):
                if auswahl.oeffentliche_kennung("beitrag", zeile.name) == gesucht:
                    treffer = zeile
                    break
            if treffer is None:
                return None
            wert = treffer.bild
        else:
            return None
    return _bild_datei(wert)


def bild_route(request):
    """``GET {Praefix}/website/bild/{art}/{slug}`` (L6).

    Nicht freigegeben, unbekannt, kein Bild oder kein Bildformat -> 404
    (im Zweifel 404: eine 403 waere ein Hinweis, dass es das Objekt gibt).
    Ausgeliefert wird mit dem ERKANNTEN Inhaltstyp, ``nosniff`` und kurzem
    oeffentlichem Cache.
    """
    from starlette.responses import Response

    from diakronos_app.website import oeffentlich_http as http

    abweisung = _liefert(request)
    if abweisung is not None:
        return abweisung

    pfad = str(getattr(getattr(request, "url", None), "path", "") or "")
    teile = [t for t in pfad.split("/") if t]
    # .../website/bild/<art>/<slug>
    art = teile[-2] if len(teile) >= 2 else ""
    slug = teile[-1] if teile else ""
    from urllib.parse import unquote

    art, slug = unquote(art), unquote(slug)

    treffer = _oeffentliches_bild(art, slug)
    if treffer is None:
        return http.fehler("Nicht gefunden.", "DoesNotExistError", 404, request)
    typ, daten = treffer
    person = art == "person"
    if person:
        # Review BS-3a: Punkt 6 — kein EXIF/GPS im ausgelieferten Foto
        # (Original in `/files` bleibt unberuehrt); Punkt 5 — kein
        # Zwischenspeicher, damit der Widerruf SOFORT wirkt.
        from diakronos_app.gemeinde_logo import ohne_metadaten

        daten = ohne_metadaten(daten, typ)
    antwort = Response(content=daten, status_code=200, media_type=typ)
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    antwort.headers["Content-Disposition"] = 'inline'
    antwort.headers["Cache-Control"] = (
        "no-store, private, max-age=0" if person
        else f"public, max-age={http.CACHE_SEKUNDEN}"
    )
    antwort.headers[http.ORIGIN_HEADER] = "Origin"
    return http.cors_kopf(antwort, request)


# ═══════════════════════════════════════════════════════════════════════════
# HTTP-Routen (/website/…) — NUR GET, oeffentlich, mit CORS
# ═══════════════════════════════════════════════════════════════════════════

#: Funktionsname -> Pfad-Parameter, die aus dem Query-String kommen.
_PARAMETER = {
    "kalender": (),
    "termine": ("kalender", "von", "bis", "kategorie", "gruppe", "limit"),
    "naechster_termin": ("kategorie", "kalender", "gruppe"),
    "gruppen": ("typ",),
    "gruppe": ("slug",),
    "beitraege": ("limit", "kategorie"),
    # BS-2a2 (Abnahmebefund): der Kontakt-Baustein holt die Postfach-Liste ueber
    # `{Basis}/website/oeffentlich/postfaecher` (dieselbe CORS-Fassung wie die
    # Lese-Endpunkte). Bis hier fehlte der Name in dieser Route — der Baustein
    # bekam 404 und zeigte die Auswahl nie an, obwohl `/api/method/…` sie
    # lieferte. Ohne Parameter.
    "postfaecher": (),
    # BS-3a: Ansprechpartner (nur mit Einwilligung).
    "ansprechpartner": ("bereich",),
}

_FUNKTIONEN = {}


def _funktionen() -> dict:
    """Name -> Funktion (erst hier, weil die Funktionen oben stehen muessen)."""
    if not _FUNKTIONEN:
        from diakronos_app.website.kontakt import postfaecher_oeffentlich

        _FUNKTIONEN.update(
            {
                "kalender": kalender,
                "termine": termine,
                "naechster_termin": naechster_termin,
                "gruppen": gruppen,
                "gruppe": gruppe,
                "beitraege": beitraege,
                "postfaecher": postfaecher_oeffentlich,
                "ansprechpartner": ansprechpartner,
            }
        )
    return _FUNKTIONEN


def _routen_antwort(request):
    """``/website/oeffentlich/<funktion>?…`` — dieselbe Logik, mit CORS."""
    from diakronos_app.website import oeffentlich_http as http

    pfad = str(getattr(getattr(request, "url", None), "path", "") or "")
    name = [t for t in pfad.split("/") if t][-1] if pfad.strip("/") else ""
    fn = _funktionen().get(name)
    if fn is None:
        return http.fehler("Nicht gefunden.", "DoesNotExistError", 404, request)
    werte = {
        param: request.query_params.get(param)
        for param in _PARAMETER.get(name, ())
        if request.query_params.get(param) is not None
    }
    # `kalender` darf mehrfach im Query-String stehen.
    if name in ("termine",):
        mehrfach = request.query_params.getlist("kalender")
        if mehrfach:
            werte["kalender"] = mehrfach
    ergebnis = fn(request=request, **werte)
    # Der Router-Weg verpackt in `{"message": …}`; hier kommt die Antwort
    # direkt aus der Route — dieselbe Huelle, wie sie ein Frappe-Client kennt
    # (die Besucher-Website liest `antwort.message`, BS-2* genauso).
    if _ist_antwort(ergebnis):
        return ergebnis
    return http.json_antwort(ergebnis, request)


def _ist_antwort(wert) -> bool:
    """True, wenn die Funktion bereits eine HTTP-Antwort geliefert hat."""
    from starlette.responses import Response

    return isinstance(wert, Response)


@dataclass(frozen=True)
class Routen:
    """Die drei HTTP-Pfade der oeffentlichen Ausgabe (praefixfrei)."""

    ical: str = "/website/ical/{kalender_slug}"
    bild: str = "/website/bild/{art}/{slug}"
    lesen: str = "/website/oeffentlich/{funktion}"


def registriere_routen(app) -> None:
    """Traegt die drei HTTP-Routen in die Anwendung ein (idempotent).

    MUSS vor dem SPA-Catch-all laufen (``main.erstelle_app``): sonst liefert
    die SPA auf ``/website/…`` HTML. Die Methoden stehen ausdruecklich auf
    GET/HEAD/OPTIONS; jede andere Methode beantwortet Starlette mit 405, die
    inhaltliche Pruefung steht zusaetzlich in den Funktionen (dieselbe
    Antwortform wie ueberall sonst).
    """
    from starlette.routing import Route

    ziele = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    routen = Routen()
    if routen.ical not in ziele:
        app.add_route(routen.ical, ical_route, methods=["GET", "HEAD", "OPTIONS"])
    if routen.bild not in ziele:
        app.add_route(routen.bild, bild_route, methods=["GET", "HEAD", "OPTIONS"])
    if routen.lesen not in ziele:
        app.add_route(
            routen.lesen, _routen_antwort, methods=["GET", "HEAD", "OPTIONS"]
        )


def _registriere_kurzpfade() -> None:
    """Traegt ``website.oeffentlich.<name>`` in das Register ein (wie BS-1a).

    ``@whitelist`` leitet den Kurzpfad aus Modul und Funktion ab
    (``oeffentlich.termine``); die Karte verlangt
    ``website.oeffentlich.termine``. DIESELBE Funktion, damit die Optionen
    (``allow_guest``, ``methods``) mitgehen.

    BS-1b2 (F7): NUR noch der ausdrueckliche Praefix ``website.oeffentlich.*``
    (plus die Frappe-Originalbahn aus ``FRAPPE_MODULE``). Das Register kannte
    die Endpunkte vorher auch unter NACKTEN Namen (``kalender``, ``termine``,
    ``gruppe``, ``gruppen``, ``beitraege``, ``naechster_termin``) — die
    kollidieren mit den gleichnamigen Verwaltungsfunktionen aus
    ``api/kronos/*`` und ``api/gruppen.py``, je nach Importreihenfolge gewann
    die oeffentliche Fassung. Diese Namen werden nach dem Import wieder
    entfernt; die Registrierung selbst (``@whitelist``) bleibt unberuehrt,
    weil sie die Optionen an der Funktion festhaelt.
    """
    from diakronos_app.frappe_compat.registry import (
        nackte_namen_entfernen,
        register_with_frappe_module,
    )

    for name in _PARAMETER:
        register_with_frappe_module(KURZPFAD, name, _funktionen()[name])
    nackte_namen_entfernen(_funktionen())


# Beim Import ausfuehren (das Modul wird von `diakronos_app.api` gezogen, also
# vor dem ersten Methodenaufruf) — wie `website/kontakt.py`.
_registriere_kurzpfade()


__all__ = [
    "KURZPFAD",
    "Routen",
    "beitraege",
    "bild_route",
    "gruppe",
    "gruppen",
    "ical_route",
    "kalender",
    "naechster_termin",
    "registriere_routen",
    "termine",
]
