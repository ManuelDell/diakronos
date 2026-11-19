"""CHAT-8 — Aufbewahrung des Chats: Einstellungen und der taegliche Loeschlauf.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 4.2 (Tabelle Fristen), 4.3
und die Entscheidung **F8** (Abschnitt 9): *„Aufbewahrungsfristen pro Gemeinde
einstellbar (Einstellung des Administrators), Standard 24 Monate Gruppe / 12
Monate Direkt; Loeschung automatisch.“*

WAS HIER STEHT
--------------
1. **Die Einstellungen** — ``chat_frist_gruppe_monate`` (Standard 24) und
   ``chat_frist_direkt_monate`` (Standard 12), gelesen und geschrieben als
   Spalten der BESTEHENDEN Gemeinde-Single ``gemeinde_einstellungen``
   (``models/gemeinde.py``, Muster von ``link_laufzeit_tage``). Angelegt werden
   sie von ``alembic/versions/chat8_fristen.py`` — ein Modellattribut ohne die
   Spalte in der Datenbank bricht jeden Zugriff auf die Einstellungen mit
   ``UndefinedColumn`` (Review R1, MUSS). Eine Absicherung ueber ``hasattr``
   waere wirkungslos (das Modellattribut existiert immer) und deshalb NICHT
   enthalten.

2. **Der Loeschlauf** ``aufraeumen()`` — EINE Funktion, die der Scheduler-Job
   ``scheduler.job_chat_aufbewahrung`` taeglich ruft. Vier Fristen:

   a) **Gespraeche** ganz loeschen, deren LETZTE Nachricht aelter ist als die
      Frist der Gespraechsart (Gruppe 24 / Direkt 12 Monate). Ein Gespraech
      OHNE Nachrichten zaehlt ab ``angelegt_am``. Reihenfolge der Loeschungen
      ist Pflicht, nicht Geschmack: die Fremdschluessel sind NICHT als
      ``ON DELETE CASCADE`` angelegt (die Suite laeuft auf SQLite, das sie
      ohnehin nicht erzwingt — und ein Kaskadieren wuerde Zeilen loeschen,
      ohne dass jemand sie auswaehlt). Deshalb Kinder zuerst, Wurzel zuletzt:

          chat_meldung  ->  chat_glocke
          ->  chat_stimme / chat_umfrage_abgabe -> chat_umfrage_option
          ->  chat_umfrage  ->  (chat_nachricht.umfrage = NULL)
          ->  chat_nachricht (erst antwort_auf = NULL, dann Zeilen)
          ->  chat_reaktion  ->  chat_teilnehmer  ->  chat_gespraech

      ``chat_meldung`` steht UEBER den Nachrichten, weil ihre FK auf
      ``chat_nachricht`` zeigt — andersherum scheitert PostgreSQL sofort.

      **Offene Meldung = Aussetzung** (Entscheidung Operator im Review R1):
      ein Gespraech mit einer noch OFFENEN Meldung wird uebersprungen. Solange
      ein Fall nicht entschieden ist, braucht die Meldestelle den Ausschnitt;
      nach der Entscheidung greift die Frist beim naechsten Lauf. Das ist die
      einzige Ausnahme — entschiedene Meldungen halten nichts fest.

   b) **Geloeschte/entfernte Nachrichten**: Text nach 6 Monaten endgueltig
      leeren (``text = ''``). Bis dahin ist der Text nur fuer die Meldestelle
      lesbar — dieses Verhalten aendert der Lauf NICHT (er leert nur, was
      ohnehin niemandem mehr angezeigt wird). Gemessen wird ab
      ``geloescht_am``.

   c) **Offene Umfragen**: Stimmenzeilen (``chat_stimme``) 6 Monate nach
      SCHLIESSUNG loeschen — die Zaehler ``chat_umfrage_option.stimmen``
      bleiben (Konzept 4.2: „anonym: nur der Zaehler bleibt“). Eine noch
      offene Umfrage verliert keine Stimme; gemessen wird ab
      ``geschlossen_am``.

   d) **Meldungen** (``chat_meldung``): 12 Monate nach ABSCHLUSS loeschen,
      also ab ``bearbeitet_am`` der entschiedenen Meldung. Eine entschiedene
      Altzeile OHNE Zeitpunkt wird NICHT geloescht: ohne Datum gibt es keine
      Frist (Entscheidung R1, beibehalten). Offene Meldungen bleiben.

3. **Keine toten Links in der Glocke.** Chat-Benachrichtigungen
   (``document_type`` ``chat_gespraech`` / ``chat_nachricht`` /
   ``chat_meldung``) auf ein geloeschtes Ziel werden GELOESCHT (Entscheidung
   Operator R1 — nicht entkoppelt): eine Glocke, deren Ziel weg ist, hat
   keinen Zweck mehr. Fremde Benachrichtigungen bleiben unberuehrt; die
   Bedingung ist je ``document_type`` formuliert (``NOT EXISTS``), es wird
   KEINE Namensliste nach Python geladen.

WAS DER LAUF AUSDRUECKLICH NICHT TUT
------------------------------------
* Er fasst KEINE Nicht-Chat-Tabelle an ausser ``Notification Log`` (und dort
  nur Chat-Ziele).
* Er loescht kein Gespraech, das noch Nachrichten INNERHALB der Frist hat
  oder eine OFFENE Meldung traegt.
* ``chat_umfrage_abgabe`` bleibt beim Stimmen-Lauf (c) stehen: sie traegt
  KEINE Option, ist also kein Stimmgeheimnis, und „N haben abgestimmt“ bleibt
  lesbar. Beim Loeschen eines Gespraechs (a) faellt sie mit.

GROESSENORDNUNG (keine Riesen-IN-Listen)
----------------------------------------
Alle Loeschungen laufen ueber UNTERABFRAGEN (``in_(select(...))``), nicht ueber
in Python geladene Kennungslisten: psycopg hat eine harte Grenze von 65 535
Parametern je Anweisung, und ein Gespraech mit vielen Nachrichten wuerde sie
reissen. Jede Frist ist EINE Anweisung, deren Groesse nicht von der
Zeilenzahl abhaengt.

IDEMPOTENZ
----------
Jeder Schritt ist eine Loeschung nach einem Cutoff: ein zweiter Lauf findet
nichts mehr (``rowcount`` = 0). Der Test ``test_chat8_fristen`` prueft das.

ZEIT
----
Gerechnet wird in der WANDZEIT der Gemeinde (``zeit.jetzt_wanduhr``), weil
alle Chat-Zeitstempel so gespeichert sind (``api.chat._jetzt``). ``jetzt`` ist
injizierbar — Tests schlafen nicht.

NACHZIEHEN NACH CHAT-4a / CHAT-7
--------------------------------
``chat_glocke`` (CHAT-4a) und die Umfrage-Tabellen (CHAT-5) sind Teil der
Kette und werden DIREKT importiert — kein ``try/except ImportError`` mehr
(Review R1/SOLL 5): beide Tabellen sind in ``main``, ein Ausweichpfad waere
nur noch toter Code mit eigener Fehlerquelle. CHAT-7 Direktgespraeche
(``art = 'direkt'``) bekommen ``chat_frist_direkt_monate`` ueber ``frist_art``.
Ein neues Gespraechsart ohne Eintrag in ``FRIST_ARTEN`` faellt auf die
GRUPPEN-Frist zurueck (nie auf „nie loeschen“ — die Frist ist die Zusage).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update

from diakronos_app import db as dbmod
from diakronos_app.models.chat import (
    ART_GRUPPE,
    ART_UNTERGRUPPE,
    ChatGespraech,
    ChatGlocke,
    ChatMeldung,
    ChatNachricht,
    ChatReaktion,
    ChatStimme,
    ChatTeilnehmer,
    ChatUmfrage,
    ChatUmfrageAbgabe,
    ChatUmfrageOption,
    MELDUNG_OFFEN,
)

logger = logging.getLogger("diakronos_app.chat_aufbewahrung")

__all__ = [
    "ERGEBNIS_KEYS",
    "FRIST_ARTEN",
    "FRIST_MAX_MONATE",
    "FRIST_MIN_MONATE",
    "FRIST_NACHRICHT_MONATE",
    "FRIST_STANDARD",
    "FRIST_UMFRAGE_MONATE",
    "MELDUNG_FRIST_MONATE",
    "aufraeumen",
    "frist_art",
    "holen_einstellungen",
    "hole_frist",
    "monate_zurueck",
    "setze_einstellungen",
]

# ── Die Fristen (Konzept 4.2, Entscheidung F8) ──────────────────────────────

#: Standardwerte in MONATEN. F8: 24 Monate Gruppen-, 12 Monate Direktgespraech.
FRIST_STANDARD: dict[str, int] = {
    "gruppe": 24,
    "direkt": 12,
}

#: Schluessel der Einstellung je Gespraechsart (Spaltennamen der
#: Gemeinde-Single). Eine Art OHNE Eintrag bekommt die Gruppen-Frist —
#: „unbegrenzt“ ist bewusst kein Zustand (Konzept 4.2: „sonst waechst der Chat
#: unbegrenzt und die Frist ist Papier“).
FRIST_ARTEN: dict[str, str] = {
    ART_GRUPPE: "chat_frist_gruppe_monate",
    ART_UNTERGRUPPE: "chat_frist_gruppe_monate",
    "direkt": "chat_frist_direkt_monate",
    # Runden (S3) sind wie Direktnachrichten private Kommunikation — dieselbe
    # kuerzere Frist, dieselbe Begruendung (hoeheres Schutzbeduerfnis).
    "runde": "chat_frist_direkt_monate",
}

#: Grenzen einer einstellbaren Frist: 1 Monat … 10 Jahre. Unten 1, weil 0
#: „sofort loeschen“ bedeuten wuerde (ein Tippfehler, der den Chat leert);
#: oben 120 als Bremse gegen Zahlendreher (2400 statt 24).
FRIST_MIN_MONATE = 1
FRIST_MAX_MONATE = 120

#: Feste Fristen aus Konzept 4.2 — NICHT einstellbar (sie sind die
#: Datenschutz-Zusage gegenueber der Meldestelle bzw. den Abgegebenen).
FRIST_NACHRICHT_MONATE = 6   # Text geloeschter/entfernter Nachrichten
FRIST_UMFRAGE_MONATE = 6     # Stimmenzeilen (offen) nach Schliessung
MELDUNG_FRIST_MONATE = 12    # Meldungen nach Abschluss

#: Die Chat-Ziele, auf die eine Glocke zeigen kann (``Notification Log``).
#: CHAT-4b: ``chat_umfrage`` gehört dazu — die Umfrage-Glocken
#: („Neue Umfrage im …“, „… endet morgen“) hängen an der UMFRAGE. Ohne diesen
#: Eintrag blieben sie stehen, nachdem das Gespräch gelöscht wurde, und
#: führten in keinen Verlauf mehr (Review R1/5).
GLOCKE_DOKUMENTTYPEN = ("chat_gespraech", "chat_nachricht", "chat_meldung",
                        "chat_umfrage")


class FristFehler(ValueError):
    """Ungueltige Frist — der Text ist die Meldung fuer die Oberflaeche."""


# ── Rechnung ────────────────────────────────────────────────────────────────


def monate_zurueck(zeit: datetime, monate: int) -> datetime:
    """``zeit`` minus ``monate`` Kalendermonate — ohne Tages-Ueberlauf.

    Der 31. Mai minus 3 Monate ist der 28. Februar, NICHT der 3. Maerz (ein
    ``timedelta(days=90)`` waere eine andere Frist und je nach Monatslaenge
    mal zu streng, mal zu lasch). Der Tag wird auf den letzten des Zielmonats
    gekappt; die Uhrzeit bleibt.
    """
    gesamt = (zeit.year * 12 + (zeit.month - 1)) - int(monate)
    jahr, monat0 = divmod(gesamt, 12)
    monat = monat0 + 1
    tage = [31, 29 if _schaltjahr(jahr) else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31][monat - 1]
    return zeit.replace(year=jahr, month=monat, day=min(zeit.day, tage))


def _schaltjahr(jahr: int) -> bool:
    return jahr % 4 == 0 and (jahr % 100 != 0 or jahr % 400 == 0)


def jetzt_wanduhr() -> datetime:
    """Jetzt als Wandzeit der Gemeinde (dieselbe Naht wie ``api.chat._jetzt``)."""
    from diakronos_app.zeit import jetzt_wanduhr as naht

    return naht()


# ── Einstellungen (bestehende Gemeinde-Single, Migration chat8_fristen) ─────


def _pruefe_monate(wert: Any, feld: str) -> int:
    """Ganze Zahl zwischen ``FRIST_MIN_MONATE`` und ``FRIST_MAX_MONATE``."""
    try:
        zahl = int(str(wert).strip())
    except (TypeError, ValueError):
        raise FristFehler(f"{feld} muss eine ganze Zahl in Monaten sein.") from None
    if zahl < FRIST_MIN_MONATE or zahl > FRIST_MAX_MONATE:
        raise FristFehler(
            f"{feld} muss zwischen {FRIST_MIN_MONATE} und {FRIST_MAX_MONATE} "
            f"Monaten liegen."
        )
    return zahl


def _gemeinde_zeile(session):
    """Die Gemeinde-Single lesen — ueber den BESTEHENDEN Weg (``api.gemeinde``).

    Kein zweites Anlegen: ``api.gemeinde._gemeinde_zeile`` legt die Zeile mit
    ihren Voreinstellungen an, falls es sie noch nicht gibt. Ein eigener
    Leg-Weg waere eine zweite Wahrheit ueber dieselbe Zeile.
    """
    from diakronos_app.api.gemeinde import _gemeinde_zeile as bestehend

    return bestehend(session)


def _standard_fuer(spalte: str) -> int:
    """Der Standardwert zu einer Einstellungsspalte."""
    return FRIST_STANDARD["direkt" if spalte.endswith("direkt_monate") else "gruppe"]


def frist_art(art: str | None) -> str:
    """Die Einstellungsspalte einer Gespraechsart (unbekannt -> Gruppe)."""
    return FRIST_ARTEN.get(str(art), "chat_frist_gruppe_monate")


def hole_frist(session, art: str) -> int:
    """Die wirksame Frist einer Gespraechsart in Monaten (Standard, wenn leer)."""
    spalte = frist_art(art)
    standard = _standard_fuer(spalte)
    wert = getattr(_gemeinde_zeile(session), spalte)
    if wert is None:
        return standard
    try:
        return _pruefe_monate(wert, spalte)
    except FristFehler:
        # Ein unmoeglicher Wert in der Datenbank darf den Job nicht toeten und
        # nicht „unbegrenzt“ bedeuten: es gilt der Standard.
        logger.warning("Chat-Frist %s=%r unbrauchbar — Standard %s gilt.",
                       spalte, wert, standard)
        return standard


def holen_einstellungen(session) -> dict[str, int]:
    """Beide Fristen als ``{"chat_frist_gruppe_monate": …, "chat_frist_direkt_monate": …}``.

    Lesbar OHNE Schreibrecht (die Werte gelten fuer alle); geschrieben wird nur
    ueber den Endpunkt (und der verlangt Administrator-Recht).
    """
    zeile = _gemeinde_zeile(session)
    ergebnis: dict[str, int] = {}
    for schluessel in ("chat_frist_gruppe_monate", "chat_frist_direkt_monate"):
        wert = getattr(zeile, schluessel)
        if wert is None:
            ergebnis[schluessel] = _standard_fuer(schluessel)
            continue
        try:
            ergebnis[schluessel] = _pruefe_monate(wert, schluessel)
        except FristFehler:
            ergebnis[schluessel] = _standard_fuer(schluessel)
    return ergebnis


def setze_einstellungen(session, *, gruppe_monate: Any, direkt_monate: Any,
                        benutzer: str | None = None,
                        jetzt: datetime | None = None) -> dict[str, int]:
    """Beide Fristen pruefen und in EINER Transaktion schreiben.

    Die RECHTE-Pruefung steht NICHT hier, sondern im Endpunkt
    (``api.chat.fristen_speichern``) — ueber den zentralen Rechte-Kern. Diese
    Funktion prueft nur die WERTE (dieselbe Schranke liest auch der Job, sonst
    liefe er mit einem unmoeglichen Wert).
    """
    geprueft = {
        "chat_frist_gruppe_monate": _pruefe_monate(gruppe_monate,
                                                   "Frist Gruppengespraeche"),
        "chat_frist_direkt_monate": _pruefe_monate(direkt_monate,
                                                   "Frist Direktgespraeche"),
    }
    zeile = _gemeinde_zeile(session)
    for schluessel, wert in geprueft.items():
        setattr(zeile, schluessel, wert)
    zeile.modified = jetzt or jetzt_wanduhr()
    zeile.modified_by = benutzer
    zeile.created_by = zeile.created_by or benutzer
    session.flush()
    return geprueft


# ── Der Loeschlauf ──────────────────────────────────────────────────────────

#: Ergebnis-Schluessel des Laufs (auch die Antwort des Scheduler-Jobs).
ERGEBNIS_KEYS = (
    "gespraeche",        # ganz entfernte Gespraeche
    "gespraeche_offen",  # uebersprungen: offene Meldung (Aussetzung)
    "nachrichten",       # endgueltig geleerte Nachrichtentexte
    "stimmen",           # entfernte Stimmenzeilen geschlossener Umfragen
    "meldungen",         # entfernte abgeschlossene Meldungen
    "glocken",           # geloeschte Chat-Benachrichtigungen
)


def _gespraech_entfernen(session, name: str) -> tuple[int, int]:
    """EIN Gespraech vollstaendig loeschen — Kinder zuerst, Wurzel zuletzt.

    Die Reihenfolge kommt aus den Fremdschluesseln (Modulkopf): jede Zeile
    zeigt auf die naechste, keine zeigt zurueck. ``chat_nachricht.antwort_auf``
    ist ein Selbst-Verweis und wird deshalb VOR dem Loeschen der Zeilen genullt
    (sonst haelt die letzte Antwort auf die erste fest).

    Alle Kinder werden ueber UNTERABFRAGEN bestimmt (``gespraech`` bzw.
    ``in_(select(chat_nachricht.name) …)``) — keine in Python geladene
    Kennungsliste, sonst reisst ein grosses Gespraech die psycopg-Grenze von
    65 535 Parametern. Rueckgabe: ``(Nachrichten, Meldungen)`` fuer das Log.
    """
    # Die Nachrichten DIESES Gespraechs als Unterabfrage — sie wird mehrfach
    # gebraucht und bleibt eine Anweisung, kein Python-Set.
    nachrichten = select(ChatNachricht.name).where(ChatNachricht.gespraech == name)

    # 1. Meldungen — sie zeigen auf Nachrichten, also VOR diesen weg.
    #    ``chat_meldung`` haengt sonst an der FK und PostgreSQL verweigert die
    #    Nachrichten-Loeschung.
    meldungen = session.execute(
        delete(ChatMeldung).where(ChatMeldung.nachricht.in_(nachrichten))
    ).rowcount or 0

    # 2. Glocken-Merker des Gespraechs (CHAT-4a). Der Merker haelt das
    #    Gespraech als Primaerschluessel — ohne diese Zeile scheitert die
    #    Gespraechs-Loeschung an der FK.
    session.execute(delete(ChatGlocke).where(ChatGlocke.gespraech == name))

    # 3. Umfragen samt Optionen, Stimmen, Abgaben. ``chat_nachricht.umfrage``
    #    zeigt auf die Umfrage — die Spalte wird daher VOR der Umfrage genullt.
    umfragen = select(ChatUmfrage.name).where(ChatUmfrage.gespraech == name)
    session.execute(delete(ChatStimme).where(ChatStimme.umfrage.in_(umfragen)))
    session.execute(delete(ChatUmfrageAbgabe).where(ChatUmfrageAbgabe.umfrage.in_(umfragen)))
    session.execute(delete(ChatUmfrageOption)
                    .where(ChatUmfrageOption.umfrage.in_(umfragen)))
    session.execute(update(ChatNachricht)
                    .where(ChatNachricht.gespraech == name)
                    .values(umfrage=None))
    session.execute(delete(ChatUmfrage).where(ChatUmfrage.name.in_(umfragen)))

    # 4. Nachrichten: erst den Selbst-Verweis loesen, dann Reaktionen, dann die
    #    Zeilen.
    session.execute(update(ChatNachricht)
                    .where(ChatNachricht.gespraech == name)
                    .values(antwort_auf=None))
    session.execute(delete(ChatReaktion)
                    .where(ChatReaktion.nachricht.in_(nachrichten)))
    anzahl_nachrichten = session.execute(
        delete(ChatNachricht).where(ChatNachricht.gespraech == name)
    ).rowcount or 0

    # 5. Teilnahme (Lesestand) und zuletzt das Gespraech selbst.
    session.execute(delete(ChatTeilnehmer).where(ChatTeilnehmer.gespraech == name))
    session.execute(delete(ChatGespraech).where(ChatGespraech.name == name))
    return int(anzahl_nachrichten), int(meldungen)


def _gespraeche_mit_offener_meldung():
    """Unterabfrage: Gespraeche mit MINDESTENS einer offenen Meldung.

    Aussetzung der Frist (Entscheidung Operator R1/4): solange eine Meldung
    offen ist, braucht die Meldestelle den Ausschnitt — das Gespraech bleibt
    stehen, auch wenn es alt ist. Nach der Entscheidung greift die Frist beim
    naechsten Lauf.
    """
    return (
        select(ChatNachricht.gespraech)
        .select_from(ChatMeldung)
        .join(ChatNachricht, ChatNachricht.name == ChatMeldung.nachricht)
        .where(ChatMeldung.stand == MELDUNG_OFFEN)
    )


def _glocken_verwaist_loeschen(session) -> int:
    """Chat-Benachrichtigungen auf Ziele, die es nicht (mehr) gibt — loeschen.

    Entscheidung Operator R1/3: GELOESCHT, nicht entkoppelt. Eine Glocke, deren
    Ziel weg ist, hat keinen Zweck mehr (sie fuehrt in keinen Verlauf) — eine
    leere Huelle waere nur eine Zeile, die niemand aufraeumt.

    Je ``document_type`` EIN ``DELETE … WHERE NOT EXISTS``: es wird KEINE
    Namensliste nach Python geladen (Review R1/SOLL 2), die Anweisung ist
    unabhaengig von der Zahl der Glocken und Ziele. ``document_type``/
    ``document_name`` sind auf ``Notification Log`` gewoehnliche Spalten —
    fremde Benachrichtigungen (anderer Typ) bleiben unberuehrt.
    """
    from diakronos_app.models.core import NotificationLog

    gesamt = 0
    je_typ = (
        ("chat_gespraech", ChatGespraech),
        ("chat_nachricht", ChatNachricht),
        ("chat_meldung", ChatMeldung),
        # CHAT-4b: die Umfrage-Glocken (Start + Erinnerung). Eine Umfrage
        # verschwindet mit ihrem Gespräch (``_gespraech_leeren``) — die Glocke
        # zu ihr muss dann mitgehen, sonst zeigt sie in nichts (Review R1/5).
        ("chat_umfrage", ChatUmfrage),
    )
    for doc_type, modell in je_typ:
        # ``NOT EXISTS (SELECT 1 FROM <ziel> WHERE <ziel>.name = document_name)``
        ziel = modell.__table__
        vorhanden = (
            select(1)
            .select_from(ziel)
            .where(ziel.c.name == NotificationLog.document_name)
            .exists()
        )
        ergebnis = session.execute(
            delete(NotificationLog)
            .where(NotificationLog.document_type == doc_type)
            .where(~vorhanden)
        )
        gesamt += int(ergebnis.rowcount or 0)
    return gesamt


def aufraeumen(jetzt: datetime | None = None) -> dict[str, int]:
    """Der taegliche Aufraeumlauf — EINE Transaktion, idempotent.

    Die Fristen gelten JE GESPRAECHSART (``frist_art``) und werden in der
    Wandzeit der Gemeinde gemessen. ``jetzt`` ist injizierbar (Tests schlafen
    nicht). Rueckgabe: Zahlen je Schritt (``ERGEBNIS_KEYS``).
    """
    zeit = jetzt or jetzt_wanduhr()
    ergebnis = {schluessel: 0 for schluessel in ERGEBNIS_KEYS}

    with dbmod.SessionLocal.begin() as session:
        # Fristen EINMAL lesen (pro Art), damit ein Wechsel waehrend des Laufs
        # nicht zwei verschiedene Wahrheiten im selben Durchgang erzeugt.
        fristen: dict[str, int] = {}
        for art in set(FRIST_ARTEN) | {ART_GRUPPE}:
            fristen[art] = hole_frist(session, art)

        # ── a) Gespraeche, deren letzte Nachricht (oder Anlage) zu alt ist ──
        # Eine Abfrage statt N: Gespraech + Kennung der letzten Nachricht
        # (LEFT JOIN, damit ein Gespraech OHNE Nachrichten nicht verschwindet —
        # es alterniert dann ab ``angelegt_am``). Gespraeche mit einer OFFENEN
        # Meldung sind ausgenommen (Aussetzung, s. ``_gespraeche_mit_offener
        # _meldung``).
        kandidaten = session.execute(
            select(
                ChatGespraech.name,
                ChatGespraech.art,
                ChatGespraech.angelegt_am,
                func.max(ChatNachricht.erstellt_am).label("letzte"),
            )
            .select_from(ChatGespraech)
            .outerjoin(ChatNachricht, ChatNachricht.gespraech == ChatGespraech.name)
            .where(~ChatGespraech.name.in_(_gespraeche_mit_offener_meldung()))
            .group_by(ChatGespraech.name, ChatGespraech.art, ChatGespraech.angelegt_am)
        ).all()
        for name, art, angelegt_am, letzte in kandidaten:
            monate = fristen.get(str(art), fristen[ART_GRUPPE])
            cutoff = monate_zurueck(zeit, monate)
            bezug = letzte or angelegt_am
            if bezug is None:
                # Keine Nachricht und keine Anlage-Zeit: nicht raten — stehen
                # lassen ist harmloser als loeschen (der naechste Lauf sieht die
                # Zeile erneut).
                continue
            if bezug <= cutoff:
                _gespraech_entfernen(session, name)
                ergebnis["gespraeche"] += 1

        # Wie viele Gespraeche wegen einer offenen Meldung stehen blieben —
        # nur zur Anzeige im Job-Log (Index-Zugriff, eine Anweisung).
        ergebnis["gespraeche_offen"] = int(session.execute(
            select(func.count()).select_from(
                _gespraeche_mit_offener_meldung().subquery()
            )
        ).scalar_one() or 0)

        # ── b) Text geloeschter/entfernter Nachrichten nach 6 Monaten leeren ──
        nachricht_cutoff = monate_zurueck(zeit, FRIST_NACHRICHT_MONATE)
        geleert = session.execute(
            update(ChatNachricht)
            .where(ChatNachricht.geloescht_am.is_not(None),
                   ChatNachricht.geloescht_am <= nachricht_cutoff,
                   ChatNachricht.text != "")
            .values(text="")
        )
        ergebnis["nachrichten"] = int(geleert.rowcount or 0)

        # ── c) Stimmenzeilen geschlossener Umfragen 6 Monate nach Schliessung ──
        umfrage_cutoff = monate_zurueck(zeit, FRIST_UMFRAGE_MONATE)
        faellige_umfragen = select(ChatUmfrage.name).where(
            ChatUmfrage.geschlossen_am.is_not(None),
            ChatUmfrage.geschlossen_am <= umfrage_cutoff,
        )
        stimmen = session.execute(
            delete(ChatStimme).where(ChatStimme.umfrage.in_(faellige_umfragen))
        )
        ergebnis["stimmen"] = int(stimmen.rowcount or 0)
        # Die Zaehler ``chat_umfrage_option.stimmen`` bleiben ausdruecklich
        # stehen (Konzept 4.2) — kein UPDATE an ihnen. ``chat_umfrage_abgabe``
        # traegt keine Option und bleibt ebenfalls (Kartenentscheidung).

        # ── d) Meldungen 12 Monate nach Abschluss ───────────────────────────
        # Abgeschlossen = entschieden (Stand nicht ``offen``) UND mit
        # Bearbeitungszeitpunkt. Eine entschiedene Altzeile OHNE Zeitpunkt wird
        # nicht geloescht: ohne Datum gibt es keine Frist.
        meldung_cutoff = monate_zurueck(zeit, MELDUNG_FRIST_MONATE)
        geloescht = session.execute(
            delete(ChatMeldung).where(
                ChatMeldung.stand != MELDUNG_OFFEN,
                ChatMeldung.bearbeitet_am.is_not(None),
                ChatMeldung.bearbeitet_am <= meldung_cutoff,
            )
        )
        ergebnis["meldungen"] = int(geloescht.rowcount or 0)

        # ── e) Chat-Benachrichtigungen ohne Ziel (kein toter Link) ──────────
        # Nach den Loeschungen oben — und als zweiter Netz fuer Glocken aus
        # einem frueheren Lauf oder einer Integration.
        ergebnis["glocken"] = _glocken_verwaist_loeschen(session)

    logger.info("Chat-Aufbewahrung fertig: %s", ergebnis)
    return ergebnis
