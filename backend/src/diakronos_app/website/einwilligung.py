"""BS-3a — Einwilligung fuer die oeffentliche Ansprechpartner-Ausgabe.

Warum dieses Modul
==================
Die Karte macht den Datenschutz zum Kern: eine Person erscheint NUR dann als
Ansprechpartner auf der Website, wenn SIE SELBST dem zugestimmt hat — nicht,
weil ein Administrator es einstellt. Deshalb liegen die Regeln hier, ohne HTTP
und ohne Endpunkt, damit Verwaltungs-API, oeffentliche Ausgabe und Profil
dieselben Regeln benutzen statt sie nachzubauen (dasselbe Muster wie
``website/freigaben.py`` aus BS-1a).

Die vier Felder am ``Mitglied``
-------------------------------
* ``website_einwilligung``     BOOLEAN NOT NULL DEFAULT false
* ``website_einwilligung_am``  TIMESTAMP (NULL = nie zugestimmt)
* ``website_einwilligung_foto``   BOOLEAN NOT NULL DEFAULT false
* ``website_anzeigename``      VARCHAR(140) (NULL/leer = Vor- und Nachname)

Sie werden von der Migration ``bs3a_website_einwilligung`` angelegt.

Regeln (Kartenvorgabe P1)
=========================
* Default AUS (G1): ohne Zustimmung ist die Person nie oeffentlich — auch
  nicht als Platzhalter und auch nicht mit ihrem Namen.
* Der Widerruf wirkt SOFORT, weil die oeffentliche Ausgabe die Schalter bei
  JEDER Anfrage liest. Es gibt keinen Zwischenspeicher und keine Kopie.
* Das Foto braucht eine EIGENE Zustimmung (``website_einwilligung_foto``);
  eine Zustimmung zum Namen ist keine zum Bild.
* ``website_anzeigename`` ist freiwillig: NUR wenn die Person ihn setzt, wird
  er statt des Namens ausgegeben (z. B. nur der Vorname).
* Nur die PERSON selbst schreibt diese Felder (``website.meine_einwilligung_setzen``).
  Die Verwaltungs-Endpunkte kennen sie nicht — ein Administrator kann sie
  damit auch nicht ueber einen Umweg setzen (Test: 403/417, Allowlist).

Was NICHT hier steht
--------------------
Die Feld-Positivliste der oeffentlichen Antwort gehoert zur Ausgabe
(``website/oeffentlich_auswahl.py``) — dort steht sie neben den anderen
Listen und wird dort negativ geprueft.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

from diakronos_app.api.gruppen_auswahl import AUSGESCHIEDEN

__all__ = [
    "ANZEIGENAME_MAX",
    "FELDER_EINWILLIGUNG",
    "NIE_OEFFENTLICH_STATUS",
    "SCHREIBEN_ERLAUBT",
    "ZUSTIMMUNG_UNTERSCHRIFT",
    "anzeigename_pruefen",
    "foto_erlaubt",
    "ist_oeffentlich",
    "oeffentlicher_name",
    "pruefe_generischen_schreibweg",
    "status_ist_ausgeschieden",
    "zeitstempel",
    "zustimmungs_fenster",
]

#: Status, in denen eine Person nie oeffentlich ist (Review BS-3a, Punkt 7):
#: eine ausgeschlossene, geloeschte oder ausgetretene Person erscheint nicht
#: als Ansprechpartner — auch dann nicht, wenn das Einwilligungsfeld (aus
#: welchem Grund auch immer) noch auf „ja“ steht. Die Einwilligung sagt „ich
#: will genannt werden“, nicht „ich bin noch Teil der Gemeinde“; die
#: Ausgabe vertritt die Gemeinde.
#:
#: NACHTRAG 2 (HOCH 1): Die Liste ist NICHT mehr selbst geschrieben, sondern
#: die eine bestehende Wahrheit aus :data:`api.gruppen_auswahl.AUSGESCHIEDEN`
#: („ausgetreten“, „verstorben“, „verstorben/ausgetreten“, „geloescht“).
#: Grund: ``api/austritt.py`` setzt ``status = "Ausgetreten"`` — mit einem
#: exakten Vergleich auf Kleinschreibung war ``ist_oeffentlich`` fuer jede so
#: gesetzte Person True. Verglichen wird jetzt per ``casefold`` (siehe
#: :func:`status_ist_ausgeschieden`), damit „Ausgetreten“, „AUSGETRETEN“ und
#: „ausgetreten“ dieselbe Antwort geben.
NIE_OEFFENTLICH_STATUS = (
    frozenset(AUSGESCHIEDEN)
    | {
        "ausgeschlossen",
        # Umlaut-Schreibweisen (Nachtrag 2, HOCH 1): der Bestand schreibt
        # ASCII („geloescht“), aber ``mitglied.status`` ist ein Freitextfeld
        # der Verwaltung. ``casefold`` faltet „Gelöscht“ NICHT auf
        # „geloescht“ — eine so markierte Person bliebe oeffentlich. Die
        # zweite Schreibweise mitzufuehren kostet nichts (fail closed).
        "gelöscht",
    }
)

#: Hoechstlaenge des Anzeigenamens (Spalte ist VARCHAR(140)).
ANZEIGENAME_MAX = 140

#: Felder, die die Person ueber ``meine_einwilligung_lesen`` sieht.
#: Der Zeitstempel ist Teil der Auskunft (DSGVO Art. 15: seit wann gilt die
#: Einwilligung) — er ist NICHT personenbezogen im Sinne eines Namens und
#: geht nur an die Person selbst, nie in eine oeffentliche Antwort.
FELDER_EINWILLIGUNG = (
    "website_einwilligung",
    "website_einwilligung_am",
    "website_einwilligung_foto",
    "website_anzeigename",
)


def _wahr(wert) -> bool:
    """Ein gespeicherter Schalter gilt nur bei echtem Ja als Ja (fail closed)."""
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return wert == 1
    return str(wert or "").strip().lower() in {"1", "true", "t", "yes", "on"}


def status_ist_ausgeschieden(zeile) -> bool:
    """True, wenn ``status`` oder ``ausgeschlossen`` die Ausgabe sperrt.

    Zwei unabhaengige Riegel, jeder genuegt (Nachtrag 2, HOCH 1):

    * ``status`` per ``casefold`` gegen :data:`NIE_OEFFENTLICH_STATUS` —
      ``api/austritt.py`` schreibt „Ausgetreten“ mit grossem A, die
      Mitgliederverwaltung kann jede Schreibweise speichern; ein exakter
      Vergleich liess die Person oeffentlich.
    * ``ausgeschlossen`` als Flag — der Austritt setzt BEIDES
      (``status`` + ``ausgeschlossen``), der reine Ausschluss nur das Flag.
      Wer das Feld von Hand auf „aktiv“ zuruecksetzt, ist trotzdem out.

    Fail closed: ein unbekannter oder leerer Status ist KEIN Ausschluss (er
    sperrt die Ausgabe nicht), aber ``ausgeschlossen`` zu lesen schlaegt nie
    fehl — :func:`_wahr` behandelt ``None`` als Nein.
    """
    status = str(getattr(zeile, "status", "") or "").strip().casefold()
    if status and status in NIE_OEFFENTLICH_STATUS:
        return True
    return _wahr(getattr(zeile, "ausgeschlossen", False))


def ist_oeffentlich(zeile) -> bool:
    """True, wenn die Person auf der Website erscheinen DARF.

    Drei Bedingungen, alle Pflicht (Kartenvorgabe P1/P2):

      1. ``website_einwilligung`` ist gesetzt (die Person hat zugestimmt),
      2. für den Namen gibt es etwas auszugeben: Vor-/Nachname oder ein
         Anzeigename, UND
      3. die Person ist nicht ausgeschlossen/geloescht/ausgetreten/verstorben
         (:func:`status_ist_ausgeschieden`).

    Ein leerer Name ist kein Grund, eine Zeile mit leerem Feld zu zeigen:
    ohne Namen gibt es keinen Ansprechpartner. Es wird hier KEIN Platzhalter
    erfunden (Kartenvorgabe: „auch nicht als Platzhalter mit Namen").
    """
    if not _wahr(getattr(zeile, "website_einwilligung", False)):
        return False
    if status_ist_ausgeschieden(zeile):
        return False
    return bool(oeffentlicher_name(zeile))


def oeffentlicher_name(zeile) -> str:
    """Der Name, der oeffentlich erscheinen darf — oder ``""``.

    Reihenfolge: ``website_anzeigename`` (die Person hat sich so entschieden)
    vor ``vorname nachname``. Der Anzeigename wird NICHT auf den vollen Namen
    ergaenzt: wer „Anna" eintraegt, will „Anna" lesen.
    """
    anzeige = str(getattr(zeile, "website_anzeigename", "") or "").strip()
    if anzeige:
        return " ".join(anzeige.split())
    vor = str(getattr(zeile, "vorname", "") or "").strip()
    nach = str(getattr(zeile, "nachname", "") or "").strip()
    return " ".join(t for t in (vor, nach) if t)


def foto_erlaubt(zeile) -> bool:
    """True, wenn das Bild der Person oeffentlich gezeigt werden darf.

    Beide Bedingungen: die Einwilligung ueberhaupt UND die eigene
    Foto-Zustimmung. Ein gesetztes ``foto``-Feld des Mitglieds allein genuegt
    NICHT — das ist ein Verwaltungsfeld und keine Zustimmung (ON-8: die
    frueheren ``foto_einwilligung``/``foto_datum`` Felder bleiben unberuehrt,
    sie gehoeren der Mitgliederverwaltung und nicht der Website).
    """
    if not _wahr(getattr(zeile, "website_einwilligung", False)):
        return False
    return _wahr(getattr(zeile, "website_einwilligung_foto", False))


def anzeigename_pruefen(wert) -> str | None:
    """Prueft den Anzeigenamen und gibt ihn normalisiert zurueck.

    ``None``/``""`` -> ``None`` (kein Anzeigename; es gilt der volle Name).
    Sonst: getrimmt, innere Mehrfach-Leerzeichen zusammengefasst, hoechstens
    :data:`ANZEIGENAME_MAX` Zeichen. Steuerzeichen sind ein Fehler — sie
    wuerden in HTML-Ausgaben und Alt-Texten landen.

    Wirft :class:`ValueError` mit deutscher Meldung (Uebersetzung am Rand,
    wie ``freigaben.SlugUngueltig``).
    """
    text = str(wert or "").strip()
    if not text:
        return None
    if any(ord(zeichen) < 32 or ord(zeichen) == 127 for zeichen in text):
        raise ValueError("Der Anzeigename enthält unzulässige Zeichen.")
    if "\n" in text or "\r" in text:
        raise ValueError("Der Anzeigename darf keine Zeilenumbrüche enthalten.")
    text = " ".join(text.split())
    if len(text) > ANZEIGENAME_MAX:
        raise ValueError(
            f"Der Anzeigename darf höchstens {ANZEIGENAME_MAX} Zeichen lang sein."
        )
    return text


def zeitstempel(wert) -> str | None:
    """``website_einwilligung_am`` als ISO-Zeichenkette (oder ``None``).

    Nur fuer die Antwort an die Person selbst. Sekundengenau und ohne Zone
    (die Spalte ist ``DateTime(timezone=False)`` wie der ganze Bestand); ein
    fehlender Wert bleibt ``None`` statt einer erfundenen Zeit.
    """
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.replace(microsecond=0).isoformat(sep=" ")
    return str(wert)


# ── Die zentrale Schranke gegen fremde Einwilligungen ──────────────────────
#
# DER BEFUND (Datenschutz-Review BS-3a, KRITISCH 1)
# -------------------------------------------------
# Die Einwilligung war nur in den EIGENEN Endpunkten geschuetzt. Der
# generische Schreibweg nahm sie trotzdem an:
#
#   PUT  /api/resource/Mitglied/<x>  {"website_einwilligung": 1, …}   -> 200
#   POST /api/resource/Mitglied      {"website_einwilligung": 1, …}   -> 200
#   frappe.client.insert             {"website_einwilligung": 1, …}   -> 200
#   doc.save()/doc.db_set()/frappe.db.set_value (derselbe Weg ohne HTTP)
#
# Danach war die Person oeffentlich. Eine Einwilligung, die ein Administrator
# setzen kann, ist keine Einwilligung (Art. 4 Nr. 11, Art. 7 DSGVO) — ein
# Verstoss gegen die Kartenvorgabe P1 und der schwerste Befund der Karte.
#
# DESHALB HIER, wie bei ``_pruefe_mitglied_schreibzugriff``: EINE Schranke in
# der Schicht, die JEDER Schreibweg passiert.
#
# WIE DER RECHTMAESSIGE WEG DURCHKOMMT
# ------------------------------------
# ``website.api.website.meine_einwilligung_setzen`` oeffnet ein Zeitfenster
# (:func:`SCHREIBEN_ERLAUBT`) und schreibt seine Felder ausschliesslich in
# diesem Fenster. Das Fenster ist ein ``ContextVar``: pro Aufruf, nicht pro
# Prozess — HTTP-Anfragen laufen in eigenen Kontexten, und ein ``with`` haelt
# es auf den eigenen Aufruf beschraenkt (auch mit mehreren Threads).
#
# Das Zeitfenster gibt NUR die vier Felder aus :data:`FELDER_EINWILLIGUNG`
# frei. Wer es missbraeuchte, um ``status`` oder ``email`` zu schreiben, kommt
# nicht weiter: eine andere Spalte zu setzen ist ein Fehler (``ValueError``),
# kein stiller Erfolg.
#
# WAS DIE SCHRANKE NICHT SIEHT
# ---------------------------
# Rohes SQL (``UPDATE mitglied SET …``) und der Import eines Datenbank-Dumps.
# Beides laeuft an jeder Anwendungsschranke vorbei; dagegen hilft nur der
# Datenbankbenutzer, nicht dieser Code. Fuer die Anwendung ist die Regel
# damit vollstaendig — der Test
# ``test_kein_generischer_weg_setzt_die_einwilligung`` prueft ALLE in
# ``NICHT_SCHREIBBAR`` genannten Wege.

#: Felder, die ausschliesslich die Person selbst schreibt. Ein Schreibversuch
#: ueber einen generischen Weg ist ein Rechtefehler (403), kein stiller
#: Verlust. ``website_einwilligung_am`` ist enthalten, weil ein gesetzter
#: Zeitstempel ohne Zustimmung ein Nachweis fuer etwas waere, das nicht gilt.
SCHREIBEN_ERLAUBT: ContextVar[frozenset[str]] = ContextVar(
    "website_einwilligung_schreibfenster", default=frozenset()
)

#: Zeitfenster fuer :data:`SCHREIBEN_ERLAUBT` — nur der eigene Endpunkt.
ZUSTIMMUNG_UNTERSCHRIFT = "nur die Person selbst (website.meine_einwilligung_setzen)"

_MELDUNG = (
    "Die Einwilligung zur Veröffentlichung kann nur die Person selbst "
    "erteilen oder widerrufen. Die Verwaltung kann sie nicht setzen."
)


def pruefe_generischen_schreibweg(werte, name: str | None = None) -> None:
    """403, wenn ein generischer Schreibweg ein Einwilligungsfeld schreibt.

    ``werte`` sind die zu schreibenden Felder (nach Spaltenfilter), ``name``
    die Mitglied-Kennung (``None`` beim Anlegen). Wird ausschliesslich aus
    ``_pruefe_mitglied_schreibzugriff`` aufgerufen — dort laufen Anlegen und
    Aendern aller Wege durch (`/api/resource`, ``frappe.client``,
    ``_create``, ``_update_doc``, ``Document.save``/``db_set``/``set_value``).

    Ein Feld, das auf denselben Wert geschrieben wird, ist ``= name``
    bei ``PUT /api/resource`` — das ist keine Einwilligung, aber trotzdem ein
    Schreibversuch auf einem gesperrten Feld; er wird ebenfalls abgelehnt
    (fail closed, wie die Parametergrenze der Verwaltungs-Endpunkte).
    """
    from diakronos_app.frappe_compat.exceptions import PermissionError

    felder = {str(k) for k in (werte or {})}
    versuch = felder.intersection(FELDER_EINWILLIGUNG)
    if not versuch:
        return
    erlaubt = SCHREIBEN_ERLAUBT.get()
    if versuch <= erlaubt:
        return
    raise PermissionError(_MELDUNG)


@contextmanager
def zustimmungs_fenster(felder):
    """Oeffnet :data:`SCHREIBEN_ERLAUBT` fuer :data:`FELDER_EINWILLIGUNG`.

    Nur fuer den eigenen Endpunkt der Person. Andere Felder zu oeffnen ist ein
    Programmierfehler und wird sofort gemeldet — sonst koennte ein spaeterer
    Aufrufer die Schranke ueber das Fenster aushebeln.
    """
    fremd = {str(f) for f in felder}.difference(FELDER_EINWILLIGUNG)
    if fremd:
        raise ValueError(
            f"Das Einwilligungs-Fenster darf nur Einwilligungsfelder öffnen, nicht {sorted(fremd)}."
        )
    token = SCHREIBEN_ERLAUBT.set(frozenset(str(f) for f in felder))
    try:
        yield
    finally:
        SCHREIBEN_ERLAUBT.reset(token)
