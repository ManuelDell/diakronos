"""BS-1b — Inhaltsregeln der oeffentlichen Website-Ausgabe (ohne HTTP).

Warum ein eigenes Modul
=======================
Die oeffentliche Lese-API (``api/website_oeffentlich.py``) und der iCal-Feed
geben Texte Dritter heraus: Beschreibungen, Auszuege, Beitragsinhalte. Genau
dort entstehen die Fehler, die keine Testsuite von selbst findet, wenn die
Regel im Endpunkt steht: eine vergessene Stelle gibt rohes HTML heraus, ein
Tag-Filter ist zu weit, ein Umschlag fehlt.

Deshalb stehen hier DIE Regeln, pruefbar ohne HTTP:

  * :func:`klartext`      — HTML entfernen, Entities aufloesen, Raeume ordnen.
  * :func:`html_erlaubt`  — Allowlist-Bereiniger fuer Beitragsinhalte
    (``p, br, strong, em, ul, ol, li, a[href http/https/mailto], h2, h3,
    blockquote``); alles andere wird ENTFERNT, nicht maskiert.
  * :func:`zeitpunkt`     — Datum/Zeit einer Zeile in Europe/Berlin (ISO 8601
    mit Versatz), ``None``-fest.
  * :func:`termin_ics`    — ein VEVENT (RFC 5545) mit stabilem UID.
  * :func:`kalender_ics`  — VCALENDAR-Dokument aus mehreren Zeilen.
  * :func:`bild_url`      — Adresse der oeffentlichen Bild-Route (praefixbewusst).

Grundsatz G1 (Freigabe-Prinzip)
-------------------------------
Dieses Modul erzeugt KEINE Oeffentlichkeit: es bereinigt Werte, die der
Aufrufer bereits als freigegeben geprueft hat. Die Feld-Positivliste steht in
``website/oeffentlich_auswahl.py`` — dort wird entschieden, WAS hinausgeht,
hier nur, WIE es aussieht.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser

__all__ = [
    "ERLAUBTE_TAGS",
    "ERLAUBTE_ATTRIBUTE",
    "frist",
    "html_erlaubt",
    "kalender_ics",
    "klartext",
    "termin_ics",
    "zeitpunkt",
]

#: Zeitzone der Gemeinde fuer die oeffentliche Ausgabe. Dieselbe Vorgabe wie
#: ``settings.calendar_timezone``; hier fest, weil das Modul ohne Einstellungen
#: benutzbar bleiben soll (Tests, Werkzeuge).
ZEITZONE = "Europe/Berlin"

try:  # Python 3.9+: zoneinfo ist in der Standardbibliothek.
    from zoneinfo import ZoneInfo

    _ZONE = ZoneInfo(ZEITZONE)
except Exception:  # pragma: no cover — ohne tzdata bleibt es bei UTC
    _ZONE = None


# ── Klartext ───────────────────────────────────────────────────────────────


class _TextSammler(HTMLParser):
    """Sammelt sichtbaren Text; Block-Elemente werden zu Zeilenumbruechen.

    ``convert_charrefs=True`` loest ``&amp;``/``&#39;`` schon beim Parsen auf —
    ein zweites ``unescape`` wuerde ``&amp;lt;`` zu ``<`` machen.
    """

    #: Elemente, die im Fliesstext einen Umbruch erzeugen.
    _BLOCK = frozenset(
        {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
         "blockquote", "ul", "ol", "table", "section", "article"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._teile: list[str] = []
        self._ueberspringen = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 — HTMLParser-API
        if tag in ("script", "style"):
            self._ueberspringen += 1
        elif tag in self._BLOCK:
            self._teile.append("\n")

    def handle_endtag(self, tag):  # noqa: ANN001 — HTMLParser-API
        if tag in ("script", "style") and self._ueberspringen:
            self._ueberspringen -= 1
        elif tag in self._BLOCK:
            self._teile.append("\n")

    def handle_data(self, data):  # noqa: ANN001 — HTMLParser-API
        if not self._ueberspringen:
            self._teile.append(data)

    def text(self) -> str:
        return "".join(self._teile)


def klartext(wert) -> str:
    """HTML entfernen und den sichtbaren Text zurueckgeben.

    ``<p>Wir <b>feiern</b> &amp; singen</p>`` -> ``Wir feiern & singen``.
    Mehr als eine Leerzeile wird zu einer, Zeilenenden werden vereinheitlicht.
    ``None``/``""`` ergeben ``""`` (nie ``"None"``).

    Skript- und Stilinhalte verschwinden mit dem Tag — ein ``<script>``-Rumpf
    ist kein Text der Gemeinde und darf in keiner Ausgabe auftauchen.
    """
    if wert is None:
        return ""
    roh = str(wert)
    if not roh.strip():
        return ""
    if "<" not in roh and "&" not in roh:
        return _raeume(roh)
    sammler = _TextSammler()
    try:
        sammler.feed(roh)
        sammler.close()
        text = sammler.text()
    except Exception:  # noqa: BLE001 — kaputtes HTML: lieber grob als 500
        text = unescape(re.sub(r"<[^>]*>", " ", roh))
    return _raeume(text)


def _raeume(text: str) -> str:
    """Zeilenenden vereinheitlichen, Leerraum je Zeile ordnen, Leerzeilen kappen."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    zeilen = [re.sub(r"[ \t\u00a0]+", " ", z).strip() for z in text.split("\n")]
    ergebnis: list[str] = []
    for zeile in zeilen:
        if not zeile and (not ergebnis or not ergebnis[-1]):
            continue
        ergebnis.append(zeile)
    return "\n".join(ergebnis).strip()


# ── HTML-Allowlist (Beitragsinhalt) ────────────────────────────────────────

#: Erlaubte Elemente des Beitragsinhalts (Kartenvorgabe L5).
ERLAUBTE_TAGS = frozenset(
    {"p", "br", "strong", "em", "ul", "ol", "li", "a", "h2", "h3", "blockquote"}
)

#: Erlaubte Attribute je Element. ``a`` traegt nur ``href``; alles andere
#: (``style``, ``class``, ``onclick``, ``target``) wird entfernt.
ERLAUBTE_ATTRIBUTE = {"a": frozenset({"href"})}

#: Erlaubte Schemata eines Links. Relative Adressen sind NICHT erlaubt: der
#: Beitrag koennte sonst auf app-interne Pfade zeigen, die auf der Website
#: ins Leere oder in die Verwaltung fuehren.
ERLAUBTE_SCHEMATA = ("http://", "https://", "mailto:")

#: Elemente, die MIT Inhalt verschwinden (ihr Text ist kein Fliesstext).
_VERWERFEN_MIT_INHALT = frozenset({"script", "style", "template", "noscript"})

#: Elemente ohne schliessendes Tag.
_LEER = frozenset({"br", "img", "hr", "input", "meta", "link", "source", "wbr"})


class _Bereiniger(HTMLParser):
    """Baut erlaubtes HTML neu auf — aus einer Allowlist, nicht per Filterliste.

    Alles, was nicht in :data:`ERLAUBTE_TAGS` steht, wird ENTFERNT (Tag weg),
    sein Text bleibt aber erhalten (``<div>Text</div>`` -> ``Text``). Attribute
    werden je Element aus :data:`ERLAUBTE_ATTRIBUTE` uebernommen; ein Link mit
    fremdem Schema (``javascript:``, ``data:``) verliert sein ``href`` und
    bleibt als Text stehen.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._aus: list[str] = []
        self._springen = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001 — HTMLParser-API
        tag = tag.lower()
        if tag in _VERWERFEN_MIT_INHALT:
            self._springen += 1
            return
        if self._springen:
            return
        if tag not in ERLAUBTE_TAGS:
            return
        self._aus.append(self._tag(tag, attrs, schliessen=False))

    def handle_startendtag(self, tag, attrs):  # noqa: ANN001 — HTMLParser-API
        tag = tag.lower()
        if self._springen or tag not in ERLAUBTE_TAGS:
            return
        self._aus.append(self._tag(tag, attrs, schliessen=True))

    def handle_endtag(self, tag):  # noqa: ANN001 — HTMLParser-API
        tag = tag.lower()
        if tag in _VERWERFEN_MIT_INHALT:
            if self._springen:
                self._springen -= 1
            return
        if self._springen or tag not in ERLAUBTE_TAGS or tag in _LEER:
            return
        self._aus.append(f"</{tag}>")

    def handle_data(self, data):  # noqa: ANN001 — HTMLParser-API
        if not self._springen:
            self._aus.append(_maskiere(data))

    def html(self) -> str:
        return "".join(self._aus).strip()

    def _tag(self, tag: str, attrs, *, schliessen: bool) -> str:  # noqa: ANN001
        erlaubt = ERLAUBTE_ATTRIBUTE.get(tag, frozenset())
        stuecke = [tag]
        for name, wert in attrs:
            name = (name or "").lower()
            if name not in erlaubt:
                continue
            if name == "href":
                ziel = _link_ziel(wert)
                if ziel is None:
                    continue
                stuecke.append(f'href="{_maskiere(ziel)}"')
                continue
            stuecke.append(f'{name}="{_maskiere(wert or "")}"')
        return f"<{' '.join(stuecke)} />" if schliessen else f"<{' '.join(stuecke)}>"


def _link_ziel(wert) -> str | None:
    """Link-Ziel, wenn es ein erlaubtes Schema traegt — sonst ``None``.

    Leerraum und Steuerzeichen werden zuerst entfernt, weil ``java\\tscript:``
    sonst an einer Praefixpruefung vorbeikaeme.
    """
    ziel = re.sub(r"[\s\x00-\x1f\x7f]+", "", str(wert or "")).strip()
    if not ziel:
        return None
    klein = ziel.lower()
    if not klein.startswith(ERLAUBTE_SCHEMATA):
        return None
    return ziel


def _maskiere(text) -> str:
    """Text fuer die Ausgabe maskieren (nur die vier Pflichtzeichen)."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def html_erlaubt(wert) -> str:
    """Bereinigtes HTML nach der Allowlist der Karte (L5).

    Unbekannte Elemente, Skripte, Stile und alle nicht erlaubten Attribute
    verschwinden; der Text bleibt. Ein kaputter Rumpf ergibt keinen Fehler,
    sondern eine grobe Bereinigung (``strip_tags``): die Website soll auch bei
    einem alten Beitrag mit unvollstaendigem HTML Inhalte zeigen.
    """
    if wert is None:
        return ""
    roh = str(wert)
    if not roh.strip():
        return ""
    reiniger = _Bereiniger()
    try:
        reiniger.feed(roh)
        reiniger.close()
        return reiniger.html()
    except Exception:  # noqa: BLE001 — kaputtes HTML nie als 500
        return _maskiere(klartext(roh))


# ── Zeit ───────────────────────────────────────────────────────────────────


def _als_datetime(wert) -> datetime | None:
    """Wert zu ``datetime`` (naiv bleibt naiv — die DB speichert Ortszeit)."""
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert
    if isinstance(wert, date):
        return datetime.combine(wert, time.min)
    text = str(wert).strip()
    if not text:
        return None
    # Feste Laengen, damit ein Zeitanteil nicht in ein Datumsmuster rutscht.
    for form, laenge in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%dT%H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        if len(text) < laenge:
            continue
        try:
            return datetime.strptime(text[:laenge], form)
        except ValueError:
            continue
    return None


def _mit_zone(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None and _ZONE is not None:
        return dt.replace(tzinfo=_ZONE)
    return dt


def zeitpunkt(wert) -> str | None:
    """ISO-8601-Zeitpunkt in der Zeitzone der Gemeinde (``None`` bleibt ``None``).

    ``datetime(2026, 11, 1, 10, 0)`` -> ``"2026-11-01T10:00:00+01:00"``.
    Ein reines Datum wird zu Mitternacht. Ein Wert mit Zeitzone wird
    umgerechnet, nicht neu beschriftet.
    """
    dt = _als_datetime(wert)
    if dt is None:
        return None
    dt = _mit_zone(dt)
    return dt.isoformat(timespec="seconds") if dt is not None else None


def frist(wert) -> str | None:
    """Reines Datum als ISO-Zeichenkette (``2026-11-01``)."""
    dt = _als_datetime(wert)
    return dt.date().isoformat() if dt is not None else None


# ── iCalendar (RFC 5545) ───────────────────────────────────────────────────


def _escape_i(text) -> str:
    """iCal-Escaping nach RFC 5545 (Backslash zuerst).

    BS-1b2 (F4): Zuerst werden ALLE Steuerzeichen entfernt, die iCal nicht
    kennt (``\\x00``-``\\x08``, ``\\x0b``, ``\\x0c``, ``\\x0e``-``\\x1f``, ``\\x7f``).
    Ein ``\\r``/``\\n`` wird zur erlaubten Escapesequenz ``\\\\n`` — nur dadurch
    entsteht spaeter keine Leerzeile im Dokument. Die Steuerzeichen davor
    sind der Grund, warum ein Feld mit ``\\r\\n`` frueher eine ungefaltete
    Leerzeile in den Feed schrieb.
    """
    roh = str(text or "")
    roh = "".join(
        zeichen
        for zeichen in roh
        if zeichen in "\r\n\t" or (ord(zeichen) >= 0x20 and ord(zeichen) != 0x7F)
    )
    return (
        roh
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
        .replace("\t", " ")
    )


def _falten(zeile: str) -> list[str]:
    """Zeile auf 75 Oktette falten (Folgezeilen beginnen mit einem Leerzeichen)."""
    roh = zeile.encode("utf-8")
    if len(roh) <= 75:
        return [zeile]
    teile: list[str] = []
    rest = roh
    while len(rest) > 75:
        schnitt = 75
        # Nicht mitten in einer UTF-8-Folge schneiden.
        while schnitt > 0 and (rest[schnitt] & 0xC0) == 0x80:
            schnitt -= 1
        teile.append(rest[:schnitt].decode("utf-8"))
        rest = rest[schnitt:]
    teile.append(rest.decode("utf-8"))
    return [teile[0]] + [" " + t for t in teile[1:]]


def _ics_zeit(wert, *, ganztaegig: bool) -> str:
    """iCal-Datums-/Zeitwert: ``VALUE=DATE`` bzw. UTC-``Z``-Form."""
    dt = _als_datetime(wert)
    if dt is None:
        return ""
    if ganztaegig:
        return dt.date().strftime("%Y%m%d")
    dt = _mit_zone(dt)
    if dt is not None and dt.tzinfo is not None:
        dt = dt.astimezone(_UTC if _UTC is not None else dt.tzinfo)
    return dt.strftime("%Y%m%dT%H%M%SZ") if dt is not None else ""


def _als_datum_plus_tag(wert):
    """``wert`` + 1 Tag als DATUM (Rueckfall, wenn ``ende`` fehlt/kaputt ist)."""
    dt = _als_datetime(wert)
    if dt is None:
        return None
    return dt + timedelta(days=1)


def _ohne_eine_tagesspanne(ende, beginn):
    """``ende + 1 Tag`` — das EXKLUSIVE iCal-Ende eines Ganztagstermins.

    BS-1bc (iCal-Ganztagsende, Entscheidung Orchestrator): Diakronos speichert
    das Ende ganztägiger Termine EINSCHLIESSLICH. Beleg: das Formular zählt
    „n Tage" inklusive letztem Tag (`frontend/src/diakonos/composables/
    datumZeit.mjs`, `zeitraumText`: ``${diff + 1} Tage``), und ein eintägiger
    Termin hat Ende == Beginn.

    iCal-``DTEND;VALUE=DATE`` ist dagegen AUSSCHLIESSLICH (der erste Tag NACH
    dem Termin, RFC 5545 §3.8.2.2). Deshalb ist hier der einzige richtige
    Wert: ``Datum(Ende) + 1 Tag``; fehlt/kaputt das Ende, ``Beginn + 1 Tag``.

    Die alte Fassung gab ``ende`` unverändert zurück, sobald die Spanne
    mindestens einen Tag betrug — ein Termin 7.–8. April endete im Feed damit
    am 8. April statt am 9. (er wurde beim Import um einen Tag zu kurz).
    ``ende`` mit Uhrzeit 00:00 des letzten Tages zählt wie das Datum selbst:
    ``2026-04-08 00:00`` -> ``20260409``.
    """
    dt = _als_datetime(ende)
    if dt is None:
        return _als_datum_plus_tag(beginn)
    return dt + timedelta(days=1)


try:  # ebenfalls Standardbibliothek; nur fuer die UTC-Umrechnung
    from datetime import timezone as _tz

    _UTC = _tz.utc
except Exception:  # pragma: no cover
    _UTC = None


def termin_ics(zeile: dict) -> list[str]:
    """Die VEVENT-Zeilen EINES Termins (ohne VCALENDAR-Umschlag).

    ``zeile`` braucht ``uid``, ``titel``, ``beginn``, ``ende``, ``ganztaegig``
    und optional ``beschreibung``, ``ort``, ``stand``. Der UID ist die aus der
    Terminkennung abgeleitete, stabile Zeichenkette — er aendert sich nicht,
    wenn der Termin umbenannt wird, und ist kein Rohwert aus der Datenbank.

    RFC 5545 (BS-1b2/F4, korrigiert in BS-1bc):
      * ``DTEND;VALUE=DATE`` ist EXKLUSIV (der erste Tag NACH dem Termin).
        Diakronos speichert das Ende ganztägiger Termine dagegen
        EINSCHLIESSLICH (Formular zählt „n Tage" inkl. letztem Tag,
        eintägig = Ende == Beginn). Deshalb gilt IMMER
        ``DTEND = Datum(Ende) + 1 Tag``; fehlt oder bricht ``ende``, gilt
        ``Beginn + 1 Tag``. Ein Sonderfall „+1 nur wenn Ende <= Beginn" gibt
        es nicht mehr — er machte mehrtägige Termine um einen Tag zu kurz.
      * ``DTSTAMP`` kommt aus ``modified`` der Zeile (der Zeitpunkt der letzten
        Aenderung) — nicht aus ``now()``, sonst aendert sich der Feed bei
        jedem Abruf grundlos.
    """
    ganztaegig = bool(zeile.get("ganztaegig"))
    beginn = _ics_zeit(zeile.get("beginn"), ganztaegig=ganztaegig)
    if ganztaegig:
        # Eingeschlossenes Ende -> exklusiver DTEND: immer +1 Tag.
        ende = _ics_zeit(
            _ohne_eine_tagesspanne(zeile.get("ende"), zeile.get("beginn")),
            ganztaegig=True,
        )
    else:
        ende = _ics_zeit(zeile.get("ende"), ganztaegig=False)
    zeilen = [
        "BEGIN:VEVENT",
        f"UID:{_escape_i(zeile.get('uid'))}",
        f"DTSTAMP:{_ics_zeit(zeile.get('stand') or datetime.now(tz=_UTC), ganztaegig=False)}",
    ]
    if beginn:
        zeilen.append(
            f"DTSTART;VALUE=DATE:{beginn}" if ganztaegig else f"DTSTART:{beginn}"
        )
    if ende:
        # Ein ganztägiges DTEND ist exklusiv — es muss NACH DTSTART liegen.
        if ganztaegig and beginn and ende <= beginn:
            ende = _ics_zeit(
                _als_datum_plus_tag(zeile.get("beginn")),
                ganztaegig=True,
            )
        zeilen.append(f"DTEND;VALUE=DATE:{ende}" if ganztaegig else f"DTEND:{ende}")
    zeilen.append(f"SUMMARY:{_escape_i(zeile.get('titel'))}")
    if zeile.get("beschreibung"):
        zeilen.append(f"DESCRIPTION:{_escape_i(zeile['beschreibung'])}")
    if zeile.get("ort"):
        zeilen.append(f"LOCATION:{_escape_i(zeile['ort'])}")
    zeilen.append("TRANSP:OPAQUE")
    zeilen.append("END:VEVENT")
    return zeilen


def kalender_ics(zeilen: list[dict], *, name: str = "", stand=None) -> str:
    """Vollstaendiges VCALENDAR-Dokument (CRLF, gefaltet, UTF-8).

    Die Reihenfolge der Termine bleibt erhalten; sortiert der Aufrufer nach
    Beginn, steht der Feed chronologisch. Ohne Termine ist das Dokument
    trotzdem gueltig (ein Kalender mit null Eintraegen ist erlaubt).
    """
    kopf = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Diakronos//Website//DE",
        "CALSCALE:GREGORIAN",
        # Der Feed ist reine Anzeige: kein Einladen, kein Bearbeiten.
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_i(name)}" if name else "",
        f"X-WR-TIMEZONE:{ZEITZONE}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    rumpf = list(kopf)
    for eintrag in zeilen:
        rumpf.extend(termin_ics(eintrag))
    rumpf.append("END:VCALENDAR")
    # RFC 5545: zwischen den Inhaltszeilen steht KEINE Leerzeile — eine leere
    # Zeile ist eine ungefaltete Inhaltszeile ohne Namen und macht das
    # Dokument ungueltig (BS-1b2/F4).
    ausgabe: list[str] = []
    for zeile in rumpf:
        if not zeile:
            continue
        ausgabe.extend(_falten(zeile))
    return "\r\n".join(ausgabe) + "\r\n"


# ── Bilder ─────────────────────────────────────────────────────────────────

#: Arten der oeffentlichen Bild-Route (Kartenvorgabe L6).
BILD_ARTEN = ("gruppe", "beitrag")


def bild_url(art: str, slug: str) -> str:
    """Adresse der Bild-Route unter dem Betriebs-Praefix.

    Ohne Freigabe/Bild antwortet die Route 404; die Adresse wird trotzdem
    gebaut, weil die Oberflaeche ein ``<img onerror>`` braucht statt eines
    Feldes, das je nach Freigabe fehlt (Vertrag BS-2).
    """
    from diakronos_app.base_path import pfad

    return pfad(f"/website/bild/{art}/{slug}")
