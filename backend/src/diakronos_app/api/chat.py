"""CHAT-2 (S1): Gespräche, Verlauf, Senden, Bearbeiten, Löschen, Reaktion, Lesestand.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` (Abschnitt 1/S1, 2, 3.3, 3.4, 4.3,
4.5, 9, 10; Entscheidungen Manuel 17.11.2026) und Karte CHAT-2.

WAS HIER STEHT (nur Backend, nur Gruppen-/Untergruppen-Gespräche)
----------------------------------------------------------------
* **Ein Gespräch je Gruppe/Untergruppe**, LAZY beim ersten Zugriff angelegt
  (``gespraech``) — kein Massen-Insert über alle Gruppen.
* **Lesen** seitenweise: rückwärts („vor X“ = ältere) und vorwärts
  („seit X“ = neuere, zugleich der Polling-Abruf aus 3.1). Beide laufen über
  den Index ``(gespraech, erstellt_am)``.
* **Senden**: nur Text, ≤ 4 000 Zeichen, Zeilenumbrüche bleiben (kein
  Trimmen des Textes, nur der Rand wird geprüft). Antwort auf GENAU EINE
  Nachricht desselben Gesprächs.
* **Bearbeiten**: eigene Nachricht, 15 Minuten (``BEARBEITEN_MINUTEN``),
  Kennzeichen ``bearbeitet_am``. Danach ``ValidationError``.
* **Löschen**: Soft-Delete — die Zeile bleibt, die Lücke bleibt sichtbar.
  Eigene jederzeit; fremde nur mit Moderationsrecht (der Rechte-Kern
  entscheidet, s. unten).
* **Reaktion**: festes Set (``REAKTIONEN``), EINE je Person und Nachricht.
  Der Endpunkt setzt (``reaktion`` gesetzt) oder entfernt (leer) sie.
* **Lesestand**: je Person ein Zeitstempel + Kennung. Sichtbar ist NUR die
  Summe „gelesen von N“ an EIGENEN Nachrichten (F2, 4.5) — nie eine Liste
  „wer hat was gelesen“; an fremden Nachrichten steht ``None``.

RECHTE: NICHTS SELBST GEBAUT
----------------------------
Jeder Endpunkt fragt ``rechte.darf(...)`` — LESEN/ANLEGEN für jedes Mitglied
der Einheit, SCHREIBEN mit ``besitzer=<Konto des Autors>`` für die eigene
Nachricht, MODERIEREN für die Leitung (HV/MV, in der Untergruppe auch GL). Das
Modul ``chat`` muss in der Gruppe an sein (``modul_aktiv``, im Kern enthalten).
Die Besitzfrage vergleicht KONTEN: ``chat_nachricht.autor_benutzer`` trägt das
Konto, ``chat_nachricht.autor`` die Anzeige (Mitglied-Kennung).
Ablehnung → 403 OHNE Inhalt (``throw("", PermissionError)``): der Grund
(Rollenstring) bleibt im Server, nicht in der Antwort.

SITZUNG
-------
Gelesen und geschrieben wird in der Sitzung des Aufrufs
(``dbmod.SessionLocal.begin()`` + ``als_aktuelle_sitzung``). Der Rechte-Kern liest
dadurch denselben Stand (er benutzt ``db.lesesitzung``); der Merker des Kerns
leert sich bei jedem Flush (``db.py``), ein Rechtewechsel wirkt also sofort.

CHAT-6 — MELDEN UND MODERATION (Konzept 2.5, 3.3, 4.5, 9/F7)
-----------------------------------------------------------
* ``meldung_senden``   jede Person, die die Nachricht LESEN darf; die eigene
                       (und eine bereits gelöschte) Nachricht ist nicht meldbar
                       (400). Grund aus dem festen Set (``MELDEGRUENDE``),
                       Freitext ≤ 500 Zeichen. Eine OFFENE Meldung je
                       (Nachricht, Melder) — geprüft UND in der Datenbank
                       (partieller Unique-Index).
* ``meldungen_liste``  nur wer moderieren darf: ERST die Gespräche bestimmen,
                       die diese Person moderieren darf (je Gespräch
                       ``rechte.darf(…, MODERIEREN, "chat_gespraech", …)`` über
                       ``_erlaube``), DANN filtern, DANN ``limit``. Je Meldung
                       steht die gemeldete Nachricht und die fünf davor
                       (Konzept 2.5: „der gemeldete Ausschnitt wird sichtbar“).
                       ``offen`` zählt per SQL über genau diese Gespräche —
                       unabhängig von ``stand`` und ``limit``.
* ``meldung_entscheiden`` ``entfernen`` = Soft-Delete der Nachricht mit
                       ``entfernt_grund`` und ``geloescht_von`` (alle weiteren
                       offenen Meldungen derselben Nachricht werden erledigt),
                       ``verwerfen`` = Meldung ohne Folge. Beim Entfernen
                       Pflicht-Grund (2.5). Zwei gleichzeitige Entscheidungen:
                       bedingtes UPDATE, der Verlierer bekommt 409. Die
                       verfassende Person bekommt die Glocke über den
                       BESTEHENDEN Weg (``benachrichtigungen``) — ohne den
                       Namen der meldenden Person.

Die MELDER-IDENTITÄT geht nie nach außen, außer an die Moderation selbst:
weder ``meldung_senden`` noch der Verlauf noch die Glocke nennen sie. Die
Moderationsliste nennt sie, weil ohne sie „wer meldet hier im Dutzend“ nicht
beurteilbar wäre (Konzept 2.5, „wiederholte Meldungen“).

CHAT-R2b: PERSONENSUCHE (``personen_suchen``)
--------------------------------------------
„Personen“ verschwindet als Menüpunkt; alle Personen findet man unter
„Nachrichten“ (Konzept 10.1 Punkt 2–4). Die Suche ist die EINE Fundstelle und
ist rein lesend: `q` ist der Name (Vor-/Nachname, Teilstring, ab 2 Zeichen),
das Ergebnis ist auf 20 Treffer begrenzt (max 50), sortiert nach Nachname,
Vorname.

ZWEI STUFEN, zwei getrennte Aufgaben:
1. **Vorfilter (SQL)** — aktive Mitglieder, deren Name den Begriff enthält.
   Das ist eine Vorfilterung, KEINE Entscheidung: `m.nachname`/`m.vorname`
   und der Name als Phrase („Anna Beispiel“). Der Vorfilter ist bewusst
   grosszügig (er darf zu viel liefern, nie zu wenig), die Grenze auf
   ``SUCHE_MAX`` Zeilen gilt erst nach der Rechteprüfung.
2. **Entscheidung** — JEDER Treffer läuft durch ``rechte.darf_person_finden``
   (und ``darf_direktnachricht`` für ``darf_schreiben``). Im API-Code steht
   KEINE eigene Status- oder Rollenlogik; wer auffindbar ist, entscheidet
   allein der Rechte-Kern.

FAIL CLOSED, ohne Unterscheidung: Gast, Fehler, nicht angemeldetes Konto →
leere Liste. „Gibt es nicht“ und „darfst du nicht“ sind in der Antwort NICHT
unterscheidbar (dieselbe Regel wie beim Registrierungslink, Konzept 2.4).

FELDER: ``mitglied``, ``anzeigename``, ``bild``, ``hat_konto``,
``darf_schreiben`` und die Kontaktfelder, die
``frappe_compat.mitglied_sichtbarkeit.maskiere_datensatz`` freigibt. Ein
NICHT freigegebenes Feld fehlt GANZ (Schlüssel nicht vorhanden, nicht
``null``) — die Suche liefert absichtlich WENIGER Felder als das Profil, und
zwar über DENSELBEN Maskierer wie Adressbuch/Liste (kein zweiter
Auslieferungsweg).

WAS HIER BEWUSST FEHLT (spätere Karten): Meldungen (CHAT-6),
Direktnachrichten (CHAT-7), Löschfristen (CHAT-8), Push (CHAT-10),
Anhänge/Chatverlaufssuche (CHAT-9). Kein WebSocket: Zustellung ist der
„seit X“-Abruf (3.1, Empfehlung A).

CHAT-4a — GEBÜNDELTE GLOCKE (Konzept 1/S1, 3.1, 4.5)
---------------------------------------------------
Eine In-App-Meldung (Glocke) **gebündelt**: „Chor: 3 neue Nachrichten“ nach
5 Minuten Ruhe, nicht je Nachricht.

* ``chat_glocken_buendeln`` ist der Scheduler-Job (Minuten-Takt, s.
  ``scheduler.MINUTEN_JOBS``). Er glockt nur Gespräche, deren NEUESTE
  Nachricht mindestens ``GLOCKE_RUHE_MINUTEN`` (5) alt ist.
* Die ZAHL ist „ungelesen seit dem letzten Lesestand“ —
  ``_ungelesen_zaehlen`` (Beitritt, eigene und gelöschte Nachrichten
  ausgenommen), NICHT „neu seit der letzten Glocke“. Der Merker
  ``chat_glocke`` entscheidet nur, OB seit der letzten Glocke etwas Neues kam
  (``merker_am``) und ab wo das nächste Bündel zählt (``stand``/``stand_am`` =
  Lesestand beim Glocken).
* Je (Gespräch, Person) EINE Glocke: eine noch ungelesene Glocke desselben
  Gesprächs wird über ``benachrichtigungen.glocke_setzen`` AKTUALISIERT statt
  verdoppelt.
* Keine Glocke für die verfassende Person, für stumm geschaltete (der Zähler
  bleibt, F3), für wer seitdem gelesen hat, für wen ``rechte.darf`` das Lesen
  verweigert (Modul ``chat`` aus ⇒ kein Lesen ⇒ keine Glocke) und für
  gelöschte Gespräche.
* Der Text enthält NUR Gesprächstitel und Anzahl — kein Nachrichtentext, kein
  Absendername (Datenschutz, wie ``_glocke_neue_meldung``).
* ``lesestand_setzen`` markiert die Glocke(n) dieses Gesprächs als gelesen —
  aber nur, wenn danach nichts ungelesen bleibt (sonst bleibt sie stehen und
  wird beim nächsten Lauf fortgeschrieben).
* Aufwand: der Job wählt in SQL nur die PAARE (Gespräch, Person) aus, bei
  denen seit dem Merker etwas Neues offen ist; er lädt keine Nachrichten und
  keine Verläufe. Ein zweiter Lauf ohne neue Nachricht endet nach einer
  festen Zahl von Abfragen, unabhängig von der Zahl der Gespräche.
* Zwei gleichzeitige Läufe: eine Sitzungssperre je Lauf (PostgreSQL
  ``pg_try_advisory_xact_lock``) — der zweite Lauf tut nichts, statt dieselbe
  Glocke doppelt zu schreiben.
CHAT-5 (S2): UMFRAGEN (``umfrage_anlegen``, ``umfrage_abstimmen``,
``umfrage_schliessen``, ``umfrage_ergebnis``)
------------------------------------------------------
Die Umfrage hängt an einer Nachricht (``chat_nachricht.umfrage``) und ist
damit im Verlauf, im Lesestand und beim Löschen eine Nachricht wie jede
andere — kein zweiter Verlauf, keine zweite Sortierung.

**Anonym (F5, Standard)**: es existiert KEINE Zeile mit Personenbezug zur
gewählten Option. Geschrieben werden der Zähler
(``chat_umfrage_option.stimmen``) und eine Marke „hat abgestimmt“
(``chat_umfrage_abgabe``) — ohne Optionsspalte. Deshalb ist die Abgabe
ENDGÜLTIG (Entscheidung Operator): eine Änderung wäre nur über eine neue,
personenbezogene Zeile möglich. Unter 5 Abgegebenen steht der Hinweis in der
Antwort (``hinweis``), weil das Ergebnis dann erratbar ist.

**Offen**: eine Stimme je Person und Option (``chat_stimme``), bis zur Frist
änderbar; das Ergebnis zeigt die Namen.

**Nach Frist oder Schließung**: keine Stimme mehr (``ValidationError`` → 400),
das Ergebnis bleibt. Die Schließung zur Frist macht der BESTEHENDE Scheduler
(``scheduler.job_umfragen_schliessen``), vorzeitig der Ersteller oder wer im
Gespräch MODERIEREN darf — beides über den Rechte-Kern, nichts Eigenes.

**Verlauf**: ``verlauf`` liefert die Umfragedaten AN der Nachricht mit
(``umfrage``-Schlüssel). Die Zähler und der eigene Stand kommen in EINER
Abfrage je Seite mit (``_umfragen_laden``), nicht je Nachricht.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timedelta
from typing import Any, NoReturn

from sqlalchemy import case, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("diakronos_app.api.chat")

#: Original-Frappe-Pfad ist leer: dieses Modul ist NEU (kein Altcode-Port).
FRAPPE_MODULE = "diakronos.diakronos.api.chat"

from diakronos_app import rechte
#: Die Sitzungs-Factory wird ueber das MODUL `db` benutzt (`db.SessionLocal()`),
#: NICHT als gebundener Name: `from diakronos_app.db import SessionLocal` friert
#: die Factory beim Import ein, und die Test-Fixture `patched_db` (die auf die
#: Test-Engine umbiegt) erreicht sie dann nicht mehr — der Test liefe gegen die
#: Betriebs-Datenbank. `api.mitglieder` macht es genauso (`_db.SessionLocal`).
from diakronos_app import db as dbmod
from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    KonfliktError,
    PermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.chat import (
    ART_GRUPPE,
    ART_UNTERGRUPPE,
    BEARBEITEN_MINUTEN,
    GLOCKE_RUHE_MINUTEN,
    FRAGE_MAX,
    HINWEIS_AB,
    MELDEGRUENDE,
    MELDUNG_ENTSCHEIDUNGEN,
    MELDUNG_ERLEDIGT,
    MELDUNG_FREITEXT_MAX,
    MELDUNG_OFFEN,
    MELDUNG_STAENDE,
    MELDUNG_VERWORFEN,
    NACHRICHT_MAX,
    OPTIONEN_MAX,
    OPTIONEN_MIN,
    OPTION_MAX,
    REAKTIONEN,
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
)
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

#: Seitengröße des Verlaufs. 50 Nachrichten sind ~ eine Bildschirmseite am
#: Handy und am Desktop (Konzept 3.4: ~300 Nachrichten am Tag in einer
#: Gemeinde — 50 ist ein Sechstel davon).
SEITE = 50
#: Obergrenze für einen Aufruf (die Oberfläche fragt nie mehr an; ein Skript
#: soll die Datenbank nicht in einem Rutsch leeren können).
SEITE_MAX = 200
#: Höchstlänge eines Titels (Spalte ``chat_gespraech.titel``).
TITEL_MAX = 140
#: Wie viele Nachrichten VOR der gemeldeten die Moderation sieht (Konzept 2.5:
#: „genau die eine Nachricht plus die fünf davor“).
MELDUNG_KONTEXT = 5
#: Obergrenze einer Meldungsliste (ein Aufruf soll die Datenbank nicht in einem
#: Rutsch leeren können; die offene Liste einer Gemeinde bleibt weit darunter).
MELDUNGEN_MAX = 200
#: CHAT-4a: Kennung im ``Notification Log.document_type`` der gebündelten
#: Chat-Glocke. ``document_name`` ist die Kennung des GESPRÄCHS — darüber
#: findet ``lesestand_setzen`` die Glocke wieder (und die Oberfläche verlinkt).
CHAT_GLOCKE_DOCTYPE = "chat_gespraech"
#: CHAT-4a: Kennung der Sitzungssperre, die ZWEI Jobläufe auseinanderhält
#: (``pg_try_advisory_xact_lock``; Review R1/e). Feste Zahl, keine Zufallswerte:
#: alle Prozesse derselben Datenbank müssen dieselbe Kennung nehmen.
GLOCKE_SPERRE = 4714_0001


# ── Grundlagen ──────────────────────────────────────────────────────────────


def _h(ktion: str = "") -> NoReturn:
    """Ablehnung OHNE Inhalt: der Grund bleibt im Server (Karte: 403 ohne Inhalt).

    ``rechte.darf`` liefert den Grund als Rollen-/Regelnamen
    (``chat_leitung_hv``, ``modul_aus`` …). Der darf NICHT in die Antwort —
    er verrät Mitgliedschaften und Modulstand. Deshalb ein leerer Text und der
    Fehlerklasse, die der Router als 403 übersetzt.
    """
    raise PermissionError(ktion)


def _jetzt() -> datetime:
    """Jetzt als Wandzeit der Gemeinde, OHNE Zeitzone.

    Dieselbe Quelle wie überall in der App (``zeit.jetzt_wanduhr``): die
    Spalten sind ``DateTime`` ohne Zeitzone, und ein ``tzinfo``-Wert würde auf
    PostgreSQL als Wandzeit abgelegt, aber in Python anders verglichen.
    """
    from diakronos_app.zeit import jetzt_wanduhr

    return jetzt_wanduhr()


def _kennung(präfix: str) -> str:
    """Technische Kennung (Frappe-Namensreihe), z. B. ``chat-n-<uuid>``.

    Die Zeichen sind auf ``[a-z0-9-]`` begrenzt: keine Klammern, keine
    Leerzeichen — die Kennung reist als Parameter in der Adresse mit.
    """
    from uuid import uuid4

    return f"{präfix}-{uuid4().hex}"


def _benutzer() -> str:
    """Der angemeldete Benutzer (``frappe.session.user``)."""
    return str(session.user or "")


def _meine_kennung() -> str:
    """Mitglied-Kennung der angemeldeten Person — die Spalte ``autor`` traegt SIE.

    Dieselbe Aufloesung wie im Rechte-Kern (``mitglied.user``, sonst eindeutige
    E-Mail). Fehlt sie (Administrator, HV ueber eine RechteGruppenrolle), bleibt
    der ANZEIGE-Autor leer: der BESITZ steht in ``autor_benutzer`` (Konto) und
    traegt dann allein die Rechtefrage.
    """
    return str(rechte.eigenes_mitglied(_benutzer()) or "")


def _nicht_von(benutzer: str):
    """SQL-Bedingung „nicht von DIESER Person“ — verglichen wird das KONTO.

    ``autor_benutzer`` traegt den Besitz. NULL ist dabei NICHT „fremd“, sondern
    „Konto unbekannt/entfernt“ (z. B. nach einer Anonymisierung) — die Zeile
    bleibt lesbar, und „fremd“ ist keine Aussage mehr, die man treffen kann.
    ``or_(…, is_(None))`` macht das in EINER Bedingung: eine Zeile ohne Konto
    bleibt im Ungelesen-Zaehler, eine eigene faellt heraus.
    """
    return or_(ChatNachricht.autor_benutzer.is_(None),
               ChatNachricht.autor_benutzer != benutzer)


def _personen(s, kennungen) -> dict[str, str]:
    """Anzeigename je MITGLIED-Kennung („Vorname Nachname“, sonst die Kennung)."""
    namen = {str(k) for k in kennungen if k}
    if not namen:
        return {}
    zeilen = s.execute(
        _anzeigename_select().where(Mitglied.name.in_(namen))
    ).all()
    ergebnis: dict[str, str] = {}
    for kennung, anzeige in zeilen:
        text = str(anzeige or "").strip()
        ergebnis[str(kennung)] = text or str(kennung)
    for kennung in namen - set(ergebnis):
        ergebnis[kennung] = kennung
    return ergebnis


def _konto_namen(s, konten) -> dict[str, str]:
    """Anzeigename je KONTO (``user.full_name``, sonst die Adresse).

    NUR fuer Nachrichten ohne Mitgliedsdatensatz (Administrator, HV ueber eine
    RechteGruppenrolle): dort gibt es keine Mitglied-Kennung fuer ``autor``,
    und die Anzeige kommt aus dem Konto. Mehr als der Name wird nicht gelesen.
    """
    namen = {str(k) for k in konten if k}
    if not namen:
        return {}
    zeilen = s.execute(
        select(User.name, User.full_name).where(User.name.in_(namen))
    ).all()
    ergebnis: dict[str, str] = {}
    for konto, anzeige in zeilen:
        text = str(anzeige or "").strip()
        ergebnis[str(konto)] = text or str(konto)
    return ergebnis


def _anzeigename_select():
    """``(mitglied.name, „Vorname Nachname“)`` — dieselbe Anzeige wie überall.

    Kein eigener Personenbestand: der Name kommt aus ``mitglied`` (vorname +
    nachname). Konten OHNE Mitgliedsdatensatz haben keine Kennung zum Anzeigen —
    fuer die gibt es ``_konto_namen``.
    """
    return select(Mitglied.name, (func.trim(Mitglied.vorname + " " + Mitglied.nachname)))


# ── Gespräch (lazy) ─────────────────────────────────────────────────────────


def _gespraech_holen(s, gruppe: str, untergruppe: str | None = None) -> ChatGespraech:
    """Das Gespräch der Einheit; legt es beim ERSTEN Zugriff an (lazy).

    Der Schlüssel ist ``(art, gruppe, untergruppe)`` — in der Datenbank sichern
    ihn zwei PARTIELLE Unique-Indizes (Review Punkt 2: ein Constraint über die
    drei Spalten greift bei ``untergruppe IS NULL`` nicht). Zwei gleichzeitige
    Anfragen können deshalb beide anlegen wollen; der Index lässt nur eine
    durch, der zweite Aufruf faengt den ``IntegrityError`` im SAVEPOINT ab und
    liest die vorhandene Zeile. Ohne das Abfangen bliebe die Sitzung nach dem
    Fehler unbrauchbar (PostgreSQL bricht die Transaktion ab) und jeder weitere
    Aufruf liefe in einen 500er.
    """
    art = ART_UNTERGRUPPE if untergruppe else ART_GRUPPE
    vorhanden = _gespraech_suchen(s, art, gruppe, untergruppe)
    if vorhanden is not None:
        return vorhanden
    neu = ChatGespraech(
        name=_kennung("chat-gespraech"),
        art=art,
        gruppe=gruppe,
        untergruppe=untergruppe,
        angelegt_von=_benutzer() or None,
        angelegt_am=_jetzt(),
    )
    try:
        with s.begin_nested():
            s.add(neu)
            s.flush()
    except IntegrityError:
        # Ein paralleler Aufruf war schneller: der Savepoint ist zurueckgerollt,
        # die aeussere Transaktion lebt weiter — jetzt die vorhandene Zeile.
        vorhanden = _gespraech_suchen(s, art, gruppe, untergruppe)
        if vorhanden is None:
            raise
        return vorhanden
    return neu


def _gespraech_suchen(s, art: str, gruppe: str, untergruppe: str | None) -> ChatGespraech | None:
    """Die EINE Zeile der Einheit — ``scalar_one_or_none`` statt ``one``.

    Bleibt trotzdem eine zweite Zeile stehen (Altbestand aus der Zeit vor den
    partiellen Indizes), wird die aelteste genommen statt eines 500ers: der
    Verlauf ist dann nicht verloren, und der Betrieb kann die Doppelung
    aufraeumen.
    """
    return s.execute(
        select(ChatGespraech).where(
            ChatGespraech.art == art,
            ChatGespraech.gruppe == gruppe,
            ChatGespraech.untergruppe == untergruppe,
        ).order_by(ChatGespraech.name)
    ).scalars().first()


def _teilnahme(s, gespraech: str, benutzer: str) -> ChatTeilnehmer:
    """Teilnahme-Zeile der Person; wird beim ersten Zugriff angelegt.

    Die Teilnahme ist die eine Wahrheit über „wer ist im Gespräch“ (3.3) und
    trägt den Lesestand. Sie entsteht für JEDEN, der den Verlauf öffnet — ohne
    sie gäbe es keinen Lesestand und keinen Ungelesen-Zähler.
    """
    zeile = s.get(ChatTeilnehmer, (gespraech, benutzer))
    if zeile is not None:
        return zeile
    zeile = ChatTeilnehmer(
        gespraech=gespraech, benutzer=benutzer, stumm=False, hinzugefuegt_am=_jetzt()
    )
    s.add(zeile)
    s.flush()
    return zeile


# ── Nachricht als Antwortform ───────────────────────────────────────────────


def _reaktionen(s, nachrichten: list[str], benutzer: str) -> dict[str, list[dict[str, Any]]]:
    """Reaktionen je Nachricht: ``[{"reaktion": "👍", "anzahl": 3, "von_mir": True}]``.

    Der Zähler je Zeichen, nicht die Namen (F2/4.5: kein Verhaltensprofil).
    ``von_mir`` sagt der Oberfläche, welches Zeichen die eigene Person gesetzt
    hat — daraus ergibt sich „erneut klicken = entfernen“.
    """
    if not nachrichten:
        return {}
    zeilen = s.execute(
        select(ChatReaktion.nachricht, ChatReaktion.reaktion, ChatReaktion.benutzer)
        .where(ChatReaktion.nachricht.in_(nachrichten))
    ).all()
    gesammelt: dict[str, dict[str, dict[str, Any]]] = {}
    for nachricht, reaktion_text, konto in zeilen:
        eimer = gesammelt.setdefault(str(nachricht), {})
        eintrag = eimer.setdefault(str(reaktion_text), {"reaktion": str(reaktion_text),
                                                         "anzahl": 0, "von_mir": False})
        eintrag["anzahl"] += 1
        if str(konto) == benutzer:
            eintrag["von_mir"] = True
    # Feste Reihenfolge (das Set aus REAKTIONEN), damit die Oberfläche nicht
    # bei jedem Abruf anders sortiert.
    reihenfolge = {zeichen: i for i, zeichen in enumerate(REAKTIONEN)}
    ergebnis: dict[str, list[dict[str, Any]]] = {}
    for nachricht, eimer in gesammelt.items():
        ergebnis[nachricht] = sorted(
            eimer.values(),
            key=lambda e: (reihenfolge.get(str(e["reaktion"]), len(reihenfolge)),
                           -int(e["anzahl"])),
        )
    return ergebnis


def _gelesen_von(s, nachrichten, gespraech: str | None, benutzer: str) -> dict[str, int | None]:
    """„Gelesen von N“ — die SUMME, nie eine Namensliste (F2), NUR an eigenen.

    Konzept 1/S1 und 4.5: die Summe steht an der EIGENEN Nachricht („wer liest
    mit?“). An einer fremden Nachricht ist sie ``None`` — sonst waere sie ein
    Verhaltensprofil der anderen fuer jeden, der mitliest (Review Punkt 3).

    Gezählt wird eine Leserschaft, wenn ihr Lesestand (Zeitstempel + Kennung)
    HINTER dieser Nachricht liegt oder sie an einer SPAETEREN Nachricht gelesen
    hat (kumulativ). Gezaehlt werden:
      * nur AKTUELLE Angehoerige der Einheit — Teilnahmezeilen ehemaliger
        Mitglieder bleiben stehen (der Kern raeumt sie nicht ab) und wuerden die
        Zahl sonst dauerhaft aufblaehen;
      * ohne den Autor selbst — „gelesen“ heisst „von anderen gelesen“.
    """
    offen = [n for n in nachrichten if n is not None]
    if not offen or not gespraech or not benutzer:
        return {}
    staende = s.execute(
        select(ChatTeilnehmer.benutzer,
               ChatTeilnehmer.letzter_lesestand,
               ChatTeilnehmer.letzter_lesestand_nachricht)
        .where(ChatTeilnehmer.gespraech == gespraech,
               ChatTeilnehmer.letzter_lesestand.is_not(None))
    ).all()
    ergebnis: dict[str, int | None] = {}
    for n in offen:
        eigene = str(n.autor_benutzer or "") == benutzer
        if not eigene:
            ergebnis[str(n.name)] = None
            continue
        zaehler = 0
        for stand_benutzer, stand_am, stand_nachricht in staende:
            konto = str(stand_benutzer or "")
            if not konto or konto == benutzer:
                continue  # der Autor zaehlt sich nicht selbst
            if stand_am is None or not _darf_lesen(s, konto, n.gespraech):
                continue  # ehemaliges Mitglied (oder Konto weg) zaehlt nicht
            if stand_am > n.erstellt_am:
                zaehler += 1
            elif stand_am == n.erstellt_am and str(stand_nachricht or "") >= str(n.name):
                zaehler += 1
        ergebnis[str(n.name)] = zaehler
    return ergebnis


def _darf_lesen(s, benutzer: str, gespraech: str) -> bool:
    """Darf ``benutzer`` dieses Gespraech JETZT lesen? — ueber den Rechte-Kern.

    Die Frage entscheidet ``rechte.darf`` (Mitgliedschaft + Modul), nicht eine
    eigene Rollenlogik. Sie wird nur fuer die Zaehlung gebraucht: eine
    Teilnahmezeile allein sagt nichts ueber den heutigen Stand.
    """
    g = s.get(ChatGespraech, gespraech)
    if g is None or g.geloescht_am is not None:
        return False
    return bool(rechte.darf(benutzer, rechte.LESEN, "chat_gespraech", g.name,
                            gruppe=g.gruppe, untergruppe=g.untergruppe))


def _zeile(s, n: ChatNachricht, *,
           lesestand: dict[str, int | None] | None = None,
           reaktionen: dict[str, list[dict[str, Any]]] | None = None,
           antwort_auf: str | None = None,
           namen: dict[str, str] | None = None,
           konto_namen: dict[str, str] | None = None,
           umfragen: dict[str, dict[str, Any]] | None = None,
           ich: str = "") -> dict[str, Any]:
    """Eine Nachricht als flache Antwortzeile.

    ``text`` ist bei einer gelöschten Nachricht ``None`` — der Platz bleibt
    („Nachricht gelöscht“), der Inhalt geht nicht nach außen. ``bearbeitet``
    ist das Kennzeichen aus S1. ``gelesen_von`` ist ``None`` an fremden
    Nachrichten (Review Punkt 3).

    CHAT-5: ``umfrage`` steht NUR an einer Umfrage-Nachricht (sonst fehlt der
    Schlüssel ganz — dieselbe Form wie bei den Suchtreffern). Bei einer
    gelöschten Nachricht ist er ``None``: das Ergebnis einer gelöschten
    Umfrage hat im Verlauf nichts mehr zu suchen.
    CHAT-6: ``geloescht_grund`` steht NUR an einer durch die Moderation
    entfernten Nachricht (``chat_nachricht.entfernt_grund``) — die Oberfläche
    zeigt „Von der Moderation entfernt“ mit dem Grund. Eine selbst gelöschte
    Nachricht hat keinen Grund und damit hier ``None``. Der MELDER steht
    bewusst in keiner Antwortzeile.
    """
    geloescht = n.geloescht_am is not None
    zeile = {
        "name": n.name,
        "gespraech": n.gespraech,
        # Anzeige (Mitglied-Kennung -> Name), sonst der Name des Kontos — ein
        # Konto OHNE Mitgliedsdatensatz (Administrator, HV ueber eine
        # RechteGruppenrolle) hat keinen ``autor``. In der Antwort steht
        # BEIDES: `autor` fuer die Anzeige, `autor_mitglied` fuer den Vergleich
        # „ist das meine Nachricht“ (Konten sind nicht stabil, die
        # Mitglied-Kennung ist es).
        "autor": ((namen or {}).get(str(n.autor or ""), n.autor)
                  or (konto_namen or {}).get(str(n.autor_benutzer or ""))),
        "autor_mitglied": n.autor,
        "eigene": bool(n.autor_benutzer) and str(n.autor_benutzer) == str(ich or ""),
        "text": None if geloescht else n.text,
        "geloescht": geloescht,
        "geloescht_grund": n.entfernt_grund if geloescht else None,
        "bearbeitet": n.bearbeitet_am is not None,
        "bearbeitet_am": _isoopt(n.bearbeitet_am),
        "erstellt_am": _isoopt(n.erstellt_am),
        "antwort_auf": n.antwort_auf,
        "antwort_auf_text": antwort_auf,
        "reaktionen": (reaktionen or {}).get(n.name, []),
        "gelesen_von": (lesestand or {}).get(n.name),
    }
    if n.umfrage:
        zeile["umfrage"] = None if geloescht else (umfragen or {}).get(str(n.umfrage))
    return zeile


def _isoopt(wert: datetime | None) -> str | None:
    return wert.isoformat() if wert else None


def _zitat(s, n: ChatNachricht) -> str | None:
    """Eine Zeile des zitierten Textes („die Antwort zitiert eine Zeile“).

    Gelöscht → ``None`` (kein Inhalt nach außen). Sonst die erste nicht-leere
    Zeile, auf 140 Zeichen gekürzt — die Oberfläche zeigt sie klein über der
    Antwort.
    """
    if n.geloescht_am is not None:
        return None
    for zeile in str(n.text or "").splitlines():
        if zeile.strip():
            return zeile.strip()[:140]
    return None


def _zitate(s, nachrichten: list[ChatNachricht]) -> dict[str, str | None]:
    ids = {n.antwort_auf for n in nachrichten if n.antwort_auf}
    if not ids:
        return {}
    ziele = s.execute(select(ChatNachricht).where(ChatNachricht.name.in_(ids))).scalars().all()
    return {str(n.name): _zitat(s, n) for n in ziele}


def _seite_antwort(s, gespraech: str, zeilen: list[ChatNachricht], *,
                   richtung: str, benutzer: str) -> dict[str, Any]:
    """Die Antwortform des Verlaufs — für beide Leserichtungen EINE Form."""
    kennungen = [n.name for n in zeilen]
    zitate = _zitate(s, zeilen)
    reakt = _reaktionen(s, kennungen, benutzer)
    stand = _gelesen_von(s, zeilen, gespraech, benutzer)
    namen = _personen(s, {n.autor for n in zeilen if n.autor})
    konten = _konto_namen(s, {n.autor_benutzer for n in zeilen if n.autor_benutzer})
    # CHAT-5: EIN Abruf für alle Umfragen dieser Seite (kein N+1).
    umfragen = _umfragen_laden(s, [n.umfrage for n in zeilen if n.umfrage], benutzer)
    posten = [_zeile(s, n, lesestand=stand, reaktionen=reakt, antwort_auf=zitate.get(n.name),
                     namen=namen, konto_namen=konten, umfragen=umfragen, ich=benutzer)
              for n in zeilen]
    return {
        "gespraech": gespraech,
        "richtung": richtung,
        "nachrichten": posten,
        # Für den nächsten Abruf: die älteste und die neueste Kennung dieser
        # Seite (die Oberfläche fragt damit weiter bzw. pollt).
        "vor": posten[0]["name"] if posten else None,
        "seit": posten[-1]["name"] if posten else None,
    }


# ── Endpunkte: Gespräche ────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)  # legt Gespraech + Teilnahme an (SEC-11)
def gespraech_anlegen(gruppe=None, untergruppe=None):
    """Das Gespräch einer Gruppe/Untergruppe holen (legt es lazy an).

    Recht: LESEN in der Einheit (jedes Mitglied; Untergruppe = eigener Raum,
    F4). Antwort: ``{name, art, gruppe, untergruppe, titel}`` — die Kennung
    braucht die Oberfläche für Verlauf/Senden.

    ``gruppe`` darf auch WEGGELASSEN werden, wenn ``untergruppe`` angegeben ist:
    die Hauptgruppe wird dann aus ``untergruppe.gruppe`` gelesen.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g, u = _einheit(s, gruppe, untergruppe)
        _erlaube(benutzer, rechte.LESEN, gruppe=g, untergruppe=u)
        zeile = _gespraech_holen(s, g, u)
        _teilnahme(s, zeile.name, benutzer)
        return {
            "name": zeile.name,
            "art": zeile.art,
            "gruppe": zeile.gruppe,
            "untergruppe": zeile.untergruppe,
            "titel": zeile.titel,
        }


@whitelist(allow_guest=False)
def meine_gespraeche():
    """Alle Gruppen-/Untergruppen-Chats, die der Benutzer LESEN darf.

    Entscheidung Operator im Review (Punkt 5): die Liste zeigt AUCH noch nie
    geöffnete Gespräche (ungelesen = 0, ``geoeffnet: false``) und legt dafür
    KEINE Zeilen an — weder Gespräch noch Teilnahme. Grundlage sind die
    MITGLIEDSCHAFTEN des Benutzers (eine Abfrage für Gruppen, eine für
    Untergruppen), nicht alle Gespräche des Systems: die Rechtefrage stellt
    danach ``rechte.darf`` je Kandidat.

    Ungelesen: Nachrichten ANDERER (``autor_benutzer``) nach dem eigenen
    Lesestand, gelöschte zählen nicht. Ohne Lesestand zählt alles, was seit
    dem Beitritt geschrieben wurde (ohne Beitrittsdatum: alles) — die Anzeige
    darf kappen, der Zähler bleibt die Wahrheit.

    ``teilnehmer`` zählt nur AKTUELLE Angehörige der Einheit (nicht jede
    stehengebliebene Teilnahmezeile eines ehemaligen Mitglieds).

    Antwort: ``{gespraeche: [{name, art, gruppe, untergruppe, titel,
    teilnehmer, stumm, geoeffnet, ungelesen, letzte_nachricht, letzte_am}]}``.
    """
    benutzer = _benutzer()
    ergebnis: list[dict[str, Any]] = []
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.ist_gemeindemitglied(benutzer):
            _h()
        for g in _lesbare_gespraeche(s, benutzer):
            ergebnis.append(_gespraech_kopf(s, g, benutzer))
    ergebnis.sort(key=lambda e: (str(e["letzte_am"] or ""), str(e["titel"])), reverse=True)
    return {"gespraeche": ergebnis}


# ── Endpunkte: Personensuche (CHAT-R2b) ─────────────────────────────────────


@whitelist(allow_guest=False)
def personen_suchen(q=None, limit=None):
    """Personen für „Nachrichten“ suchen — rein lesend (GET), fail closed.

    ``q`` ist der NAME (Vor- oder Nachname, Teilstring, ab 2 Zeichen; leer →
    leere Liste). ``limit`` ist die Trefferzahl: Vorgabe ``SUCHE``, höchstens
    ``SUCHE_MAX`` — ein grösserer Wunsch wird gekappt, kein Fehler (ein
    ``limit=1000`` soll die Datenbank nicht in einem Rutsch leeren können).

    Antwort: ``{treffer: [...], limit: <tatsächliche Grenze>}``. Je Treffer
    ``mitglied``, ``anzeigename``, ``bild``, ``hat_konto``, ``darf_schreiben``
    und die per ``mitglied_sichtbarkeit`` freigegebenen Kontaktfelder. Nicht
    freigegebene Felder sind GAR NICHT im Treffer (nicht ``None``).

    Rechte: nur ``rechte.darf_person_finden`` (auffindbar) und
    ``rechte.darf_direktnachricht`` (schreibbar). KEINE eigene Status- oder
    Rollenlogik hier — der Vorfilter unten ist Suche, nicht Entscheidung.
    Gast, nicht angemeldetes Konto oder ein Fehler beim Auswerten → leere
    Liste, ohne Unterschied zwischen „gibt es nicht“ und „darfst du nicht“.
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import maskiere_datensatz
    from diakronos_app.rechte import darf_direktnachricht, darf_person_finden

    grenze = _suche_grenze(limit)
    leer: dict[str, Any] = {"treffer": [], "limit": grenze}
    try:
        benutzer = _benutzer()
        begriff = _suche_begriff(q)
        if not begriff or not rechte.ist_gemeindemitglied(benutzer):
            return leer
        treffer: list[dict[str, Any]] = []
        kandidaten: list = []
        with dbmod.SessionLocal() as s:
            for seite in range(_VORFILTER_SEITEN):
                teil = _suche_kandidaten(s, begriff, seite * _VORFILTER_MAX)
                kandidaten.extend(teil)
                # Genug Rohtreffer fuer die Grenze ODER keine weiteren Zeilen.
                if len(teil) < _VORFILTER_MAX or len(kandidaten) >= grenze * 8:
                    break
        for zeile in kandidaten:
            # `Row` -> dict ueber `_mapping` (ein `dict(Row)` scheitert: ein Row
            # ist eine Folge, kein Schlüssel/Wert-Paar).
            m = dict(zeile._mapping) if hasattr(zeile, "_mapping") else dict(zeile)
            kennung = str(m.get("name") or "")
            # Die EINE Entscheidung: der Rechte-Kern, nicht dieser Code.
            if not kennung or not darf_person_finden(benutzer, kennung):
                continue
            # Derselbe Maskierer wie Liste/Adressbuch. `Weglassen` (nicht
            # `None`) macht `_nur_freigegebene_felder` daraus.
            maskiert = maskiere_datensatz(m, mitglied_id=kennung) or {}
            treffer.append(_suche_treffer(
                kennung=kennung,
                roh=m,
                maskiert=maskiert,
                darf_schreiben=bool(darf_direktnachricht(benutzer, kennung)),
            ))
            if len(treffer) >= grenze:
                break
        return {"treffer": treffer, "limit": grenze}
    except Exception as fehler:  # noqa: BLE001 — fail closed: JEDER Fehler ⇒ keine Treffer
        # Fail closed, aber nicht stumm: protokolliert wird die FEHLERKLASSE
        # (kein Suchbegriff, kein Treffer, keine Kennung). Ein kaputter
        # Endpunkt soll in den Logs auffallen, ohne Namen preiszugeben.
        logger.warning("personen_suchen: Suche fehlgeschlagen (%s) — leere Liste",
                       type(fehler).__name__)
        return leer


#: Vorgabe und Obergrenze der Trefferzahl (Konzept 10.1, Karte Punkt 3).
SUCHE = 20
SUCHE_MAX = 50
#: Kürzeste Sucheingabe — ein einzelnes Zeichen fände fast die ganze Gemeinde.
SUCHE_MIN_ZEICHEN = 2
#: So viele Vorfilter-Zeilen holt die Datenbank je Suche. Der Vorfilter ist
#: absichtlich grosszügig (er muss Treffer finden, deren Auffindbarkeit erst
#: der Rechte-Kern bejaht), aber nicht unbegrenzt: 8 × die Höchstzahl deckt
#: auch eine Gemeinde ab, in der die ersten Treffer wegfallen. Die endgültige
#: Grenze ist ``SUCHE_MAX`` NACH der Rechteprüfung.
_VORFILTER_MAX = SUCHE_MAX * 8

#: Felder, die ein Treffer ausliefern darf — ausschliesslich Kontaktfelder,
#: für die ``mitglied_sichtbarkeit`` einen Schalter kennt. Alles andere
#: (``notiz``, Einwilligungen, ``angelegt_von`` …) kommt hier gar nicht erst
#: in Frage; Verwaltungsfelder wirft zusätzlich der Maskierer weg.
_SUCHE_FELDER = ("email", "telefonnummer", "postleitzahl", "wohnort",
                 "straße", "nummer", "geburtstag")


def _suche_grenze(limit) -> int:
    """Tatsächliche Trefferzahl: Vorgabe ``SUCHE``, gekappt auf ``SUCHE_MAX``.

    Unlesbare/negative Angaben fallen auf die Vorgabe zurück (kein Fehler) —
    eine Suche soll an einem kaputten ``limit`` nicht scheitern.
    """
    if limit is None or limit == "":
        return SUCHE
    try:
        wert = int(str(limit).strip())
    except (TypeError, ValueError):
        return SUCHE
    return max(1, min(SUCHE_MAX, wert))


def _suche_begriff(q) -> str:
    """Suchbegriff normalisieren (Kleinschreibung, Umlaute aufgelöst, getrimmt).

    Dieselbe Faltung wie die Mitgliederliste (``api.mitglieder``): „weiss“
    findet „Weiß“, „MUELLER“ findet „Müller“. Zu kurze Eingaben → ``""``.
    """
    text = unicodedata.normalize("NFC", str(q or "")).strip().lower()
    for von, nach in (("ß", "ss"), ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(von, nach)
    text = " ".join(text.split())
    return text if len(text) >= SUCHE_MIN_ZEICHEN else ""


def _suche_faltung(spalte: str) -> str:
    """SQL-Ausdruck, der eine Spalte klein- UND umlautgefaltet liefert.

    Gleiche Bauart wie ``api.mitglieder._suche_ausdruck`` (dort ist sie privat,
    ein Import über Modulgrenzen wäre eine stille Kopplung): erst BEIDE
    Schreibweisen der Umlaute/ß ersetzen, dann ``LOWER`` — PostgreSQLs ``LIKE``
    ist case-sensitiv, SQLites ``LOWER`` lässt Nicht-ASCII unverändert.
    ``spalte`` ist ein fester Bezeichner aus dieser Datei, keine Nutzereingabe.
    """
    ausdruck = spalte
    for von, nach in (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
                      ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        ausdruck = f"REPLACE({ausdruck}, '{von}', '{nach}')"
    return f"LOWER({ausdruck})"


def _like_muster(begriff: str) -> str:
    """``%begriff%`` mit maskierten Platzhaltern (``\\``, ``%``, ``_``).

    Ohne Maskierung faende ``__`` oder ``%%`` die ganze Gemeinde und hebelte
    die Mindestlaenge aus. Escape-Zeichen ist ``\\`` (``ESCAPE '\\'`` in
    jeder LIKE-Klausel — SQLite kennt keinen Standard, PostgreSQL schon).
    """
    for zeichen in ("\\", "%", "_"):
        begriff = begriff.replace(zeichen, "\\" + zeichen)
    return f"%{begriff}%"


def _suche_kandidaten(s, begriff: str, versatz: int = 0) -> list:
    """Vorfilter: Mitglieder, deren Name den Begriff enthält — EINE Seite.

    Sucht in ``vorname``, ``nachname`` UND in der Phrase „Vorname Nachname“
    (damit „anna bei“ auch „Anna Beispiel“ trifft). Der Vorfilter entscheidet
    NICHTS: er schliesst nur ``geloescht-*`` aus; ob eine Person auffindbar
    ist (Status, Austritt, Ausschluss), sagt allein
    ``rechte.darf_person_finden`` je Treffer. Sortiert nach Nachname,
    Vorname (Karte Punkt 3). Der Aufrufer blaettert mit ``versatz`` weiter,
    bis genug Treffer bestaetigt sind — sonst schnitte eine Seite voller
    Ausgetretener berechtigte Treffer ab (Review 18.11.).
    """
    muster = _like_muster(begriff)
    vorname = _suche_faltung("m.vorname")
    nachname = _suche_faltung("m.nachname")
    phrase_vor = _suche_faltung(
        "COALESCE(m.vorname, '') || ' ' || COALESCE(m.nachname, '')")
    # Die umgekehrte Reihenfolge wird ebenfalls gesucht: „Brandner Bert“ ist
    # genauso ein Name wie „Bert Brandner“.
    phrase_nach = _suche_faltung(
        "COALESCE(m.nachname, '') || ' ' || COALESCE(m.vorname, '')")
    spalten = ", ".join(
        ["m.name", "m.vorname", "m.nachname", "m.foto", "m.user",
         "m.adressbuch_sichtbarkeit", "m.status"]
        + [f'm."{feld}"' if feld == "straße" else f"m.{feld}" for feld in _SUCHE_FELDER]
    )
    like = " LIKE :muster ESCAPE '\\'"
    sql = (
        "SELECT " + spalten + " FROM mitglied m WHERE ("
        + f"{vorname}{like} OR {nachname}{like}"
        + f" OR {phrase_vor}{like} OR {phrase_nach}{like}"
        + ") AND m.name NOT LIKE 'geloescht-%'"
        " ORDER BY m.nachname, m.vorname, m.name LIMIT :grenze OFFSET :versatz"
    )
    try:
        return s.execute(text(sql), {"muster": muster, "grenze": _VORFILTER_MAX,
                                     "versatz": int(versatz)}).all()
    except Exception as fehler:  # noqa: BLE001 — fail closed, aber nicht stumm
        logger.warning("personen_suchen: Vorfilter fehlgeschlagen (%s) — leere Liste",
                       type(fehler).__name__)
        return []


#: Hoechstzahl Vorfilter-Seiten je Suche (Schutz gegen Endlosblaettern).
_VORFILTER_SEITEN = 10


def _nur_freigegebene_felder(maskiert: dict[str, Any],
                             sicht: dict[str, bool]) -> dict[str, Any]:
    """Kontaktfelder, die die Person freigegeben hat — sonst Schlüssel WEG.

    Grundlage ist das Ergebnis von ``maskiere_datensatz`` (der eine
    Auslieferungsweg). Dieses setzt nicht freigegebene Felder auf ``None``;
    die Suche liefert sie stattdessen GAR NICHT (Konzept 10.4: „die Suche
    liefert weniger Felder als das Profil“). Zusätzlich muss der zugehörige
    Schalter stehen — ein Wert, der trotz fehlender Freigabe im Datensatz
    steht, wird damit nicht durchgereicht (fail closed).
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import FELD_AN_SCHALTER

    felder: dict[str, Any] = {}
    for feld in _SUCHE_FELDER:
        schalter = FELD_AN_SCHALTER.get(feld)
        if not schalter or not sicht.get(schalter):
            continue
        wert = maskiert.get(feld)
        if wert in (None, ""):
            continue
        if isinstance(wert, str):
            wert = wert.strip()
            if not wert:
                continue
        felder[feld] = wert.isoformat() if hasattr(wert, "isoformat") else wert
    return felder


def _suche_treffer(*, kennung: str, roh: dict[str, Any],
                   maskiert: dict[str, Any], darf_schreiben: bool) -> dict[str, Any]:
    """Ein Treffer in der Form, die „Nachrichten“ zeichnet.

    ``anzeigename`` läuft durch ``personen_anzeige.kuerze`` (EINE Regel für
    gekürzte Namen) — bei einer gelöschten Person steht dort „Gelöschte
    Person“, nie die Kennung. ``hat_konto`` (aktives Konto) und
    ``darf_schreiben`` kommen beide aus dem Rechte-Kern — eine Person mit
    deaktiviertem Konto ist auffindbar, gilt aber als „hat kein Konto“.

    Kontaktfelder kommen aus ``maskiert`` (dem Ergebnis von
    ``maskiere_datensatz``) und nur, wenn die Person sie freigegeben hat. Was
    nicht freigegeben ist, steht NICHT im Treffer — auch nicht als ``None``.
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen
    from diakronos_app.frappe_compat.personen_anzeige import kuerze
    from diakronos_app.frappe_compat.personen_anzeige import ist_geloescht

    geloescht = ist_geloescht(dict(roh, name=kennung))
    kurz = kuerze(dict(roh, name=kennung))
    anzeige = str(kurz.get("vorname") or "").strip() or kennung
    if not geloescht:
        # `kuerze` kürzt ausgetretene Personen; sie sind in der Suche ohnehin
        # weg (Rechte-Kern). Der Normalfall trägt den vollen Namen.
        anzeige = " ".join(p for p in (str(roh.get("vorname") or "").strip(),
                                       str(roh.get("nachname") or "").strip()) if p) or kennung
    treffer: dict[str, Any] = {
        "mitglied": kennung,
        "anzeigename": anzeige,
        "bild": _suche_bild(roh.get("foto"), geloescht),
        # Konto-Frage beantwortet der Rechte-Kern (aktives Konto, Review 18.11.).
        "hat_konto": rechte.person_hat_konto(kennung),
        "darf_schreiben": bool(darf_schreiben),
    }
    treffer.update(_nur_freigegebene_felder(
        maskiert, sichtbarkeit_lesen(roh.get("adressbuch_sichtbarkeit"))))
    return treffer


def _suche_bild(foto, ist_geloescht: bool) -> str:
    """Bildadresse eines Treffers — präfigiert wie überall (``foto_mit_praefix``).

    Kein Bild einer gelöschten Person (die Datei ist entfernt, ein Rest im
    Feld wäre ein toter Verweis) — dieselbe Regel wie in der Mitgliederliste.
    """
    if ist_geloescht or not foto:
        return ""
    from diakronos_app.api.profile import foto_mit_praefix

    return foto_mit_praefix(foto)


# ── Endpunkte: Verlauf ──────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def verlauf(gespraech, vor=None, seit=None, limit=None):
    """Verlauf seitenweise: ``vor`` = ältere, ``seit`` = neuere Nachrichten.

    ``vor=<name>``   die Seite VOR dieser Nachricht (älter; beim Scrollen nach
                     oben), sortiert von alt nach neu.
    ``seit=<name>``  alle Nachrichten NACH dieser (neuer; das ist der
                     Polling-Abruf aus 3.1) — ohne Angabe die neueste Seite.

    Recht: LESEN im Gespräch. Antwort siehe ``_seite_antwort``.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    grenze = SEITE
    if limit not in (None, ""):
        try:
            grenze = max(1, min(int(limit), SEITE_MAX))
        except (TypeError, ValueError):
            throw("limit muss eine Zahl sein.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        # Rein lesend (SEC-11): die Teilnahme entsteht beim Oeffnen
        # (`gespraech_anlegen`), Senden oder Lesestand-Setzen.
        if vor:
            anker = _nachricht(s, str(vor), g.name)
            zeilen = s.execute(
                select(ChatNachricht).where(
                    ChatNachricht.gespraech == g.name,
                    or_(ChatNachricht.erstellt_am < anker.erstellt_am,
                        (ChatNachricht.erstellt_am == anker.erstellt_am)
                        & (ChatNachricht.name < anker.name)),
                ).order_by(ChatNachricht.erstellt_am.desc(),
                           ChatNachricht.name.desc()).limit(grenze)
            ).scalars().all()
            zeilen.reverse()  # alt -> neu anzeigen
            return _seite_antwort(s, g.name, zeilen, richtung="vor", benutzer=benutzer)
        if seit:
            anker = _nachricht(s, str(seit), g.name)
            zeilen = s.execute(
                select(ChatNachricht).where(
                    ChatNachricht.gespraech == g.name,
                    or_(ChatNachricht.erstellt_am > anker.erstellt_am,
                        (ChatNachricht.erstellt_am == anker.erstellt_am)
                        & (ChatNachricht.name > anker.name)),
                ).order_by(ChatNachricht.erstellt_am, ChatNachricht.name).limit(grenze)
            ).scalars().all()
            return _seite_antwort(s, g.name, zeilen, richtung="seit", benutzer=benutzer)
        zeilen = s.execute(
            select(ChatNachricht).where(ChatNachricht.gespraech == g.name)
            .order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
            .limit(grenze)
        ).scalars().all()
        zeilen.reverse()
        return _seite_antwort(s, g.name, zeilen, richtung="neueste", benutzer=benutzer)


# ── Endpunkte: Senden / Bearbeiten / Löschen ────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def senden(gespraech, text, antwort_auf=None):
    """Nachricht senden (nur Text, ≤ 4 000 Zeichen, Absätze bleiben).

    Recht: ANLEGEN in der Einheit — jedes Mitglied darf senden (Konzept 2.2),
    Gäste nie (der Kern gibt Gästen kein Modul).

    Der Text wird NICHT getrimmt: Zeilenumbrüche und Einrückungen sind Inhalt.
    Geprüft wird nur, dass am Rand etwas steht und die Länge passt — gezählt
    werden ZEICHEN, nicht Bytes.

    ``antwort_auf`` muss eine Nachricht DESSELBEN Gesprächs sein (sonst könnte
    man fremde Gespräche zitieren).
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    inhalt = _pruefe_text(text)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.ANLEGEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        ziel = None
        if antwort_auf not in (None, ""):
            ziel = _nachricht(s, str(antwort_auf), g.name)
        zeile = ChatNachricht(
            name=_kennung("chat-n"),
            gespraech=g.name,
            # Besitz = das KONTO (Rechte, Ungelesen-Zaehlung); Anzeige = die
            # Mitglied-Kennung, die bei einer Loeschung umgehaengt wird.
            autor_benutzer=benutzer or None,
            autor=_meine_kennung() or None,
            text=inhalt,
            antwort_auf=ziel.name if ziel else None,
            erstellt_am=_jetzt(),
        )
        s.add(zeile)
        _teilnahme(s, g.name, benutzer)
        s.flush()
        return _zeile(s, zeile, antwort_auf=_zitat(s, ziel) if ziel else None,
                      namen=_personen(s, {zeile.autor}),
                      konto_namen=_konto_namen(s, {zeile.autor_benutzer}), ich=benutzer)


@whitelist(methods=["POST"], allow_guest=False)
def aendern(nachricht, text):
    """Eigene Nachricht bearbeiten — nur innerhalb von 15 Minuten.

    Recht: SCHREIBEN mit ``besitzer=Autor``. Die Leitung darf eine fremde
    Nachricht NICHT bearbeiten (SCHREIBEN mit fremdem Besitzer verlangt im
    Kern Leitung — hier wird zusätzlich geprüft, dass es die EIGENE ist:
    Bearbeiten ist keine Moderationshandlung; fremde Nachrichten entfernt man,
    man schreibt sie nicht um).

    Nach ``BEARBEITEN_MINUTEN`` → ``ValidationError``. ``bearbeitet_am`` wird
    gesetzt (Kennzeichen „bearbeitet“).

    Die Hülle einer UMFRAGE (CHAT-5) ist nicht bearbeitbar (400): die Frage
    ist das Fachdatum, auf das die Stimmen antworten — ein nachträgliches
    Umschreiben machte jede abgegebene Stimme zu einer Antwort auf eine andere
    Frage. Sichtbarer Text und Umfrage-Frage bleiben damit derselbe Text
    (``verlauf``/``_zeile`` zeigen die Nachricht, das Ergebnis die Umfrage).
    """
    benutzer = _benutzer()
    inhalt = _pruefe_text(text)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        # Die Besitzfrage entscheidet der Rechte-KERN — durchgereicht wird das
        # KONTO der Nachricht. Bearbeiten ist keine Moderationshandlung: eine
        # fremde Nachricht entfernt man, man schreibt sie nicht um (der Kern
        # liesse es der Leitung durchgehen, deshalb zusaetzlich die Pruefung
        # „ist es meine“).
        if not _ist_meine(n, benutzer):
            _h()
        _erlaube(benutzer, rechte.SCHREIBEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 besitzer=n.autor_benutzer, gespraech=g.name)
        if n.geloescht_am is not None:
            throw("Eine gelöschte Nachricht kann nicht bearbeitet werden.")
        if n.umfrage:
            throw("Die Frage einer Umfrage lässt sich nicht ändern — "
                  "gestartete Abstimmungen antworten auf diesen Text.")
        jetzt = _jetzt()
        if n.erstellt_am is None or jetzt - n.erstellt_am > timedelta(minutes=BEARBEITEN_MINUTEN):
            throw("Nachrichten lassen sich nur in den ersten 15 Minuten bearbeiten.")
        n.text = inhalt
        n.bearbeitet_am = jetzt
        s.flush()
        return _zeile(s, n, namen=_personen(s, {n.autor}),
                      konto_namen=_konto_namen(s, {n.autor_benutzer}), ich=benutzer)


@whitelist(methods=["POST"], allow_guest=False)
def loeschen(nachricht):
    """Nachricht löschen (Soft-Delete — die Lücke bleibt sichtbar).

    Eigene jederzeit (SCHREIBEN mit eigenem Besitzer), fremde nur mit
    Moderationsrecht (MODERIEREN; HV/MV, in der Untergruppe auch GL). Der
    Rechte-Kern entscheidet, welcher der beiden Wege greift.

    Der Text bleibt in der Datenbank (Widerspruchsfälle, CHAT-6/8), wird aber
    nicht mehr ausgeliefert: ``text=None``, ``geloescht=True``. Zweites Löschen
    ist kein Fehler (idempotent) — der Zeitpunkt des ersten bleibt stehen.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        eigene = _ist_meine(n, benutzer)
        if eigene:
            _erlaube(benutzer, rechte.SCHREIBEN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe, besitzer=n.autor_benutzer,
                     gespraech=g.name)
        else:
            _erlaube(benutzer, rechte.MODERIEREN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe, gespraech=g.name)
        if n.geloescht_am is None:
            n.geloescht_am = _jetzt()
            n.geloescht_von = benutzer
        s.flush()
        return _zeile(s, n, namen=_personen(s, {n.autor}),
                      konto_namen=_konto_namen(s, {n.autor_benutzer}), ich=benutzer)


# ── Endpunkte: Reaktion, Lesestand, Stumm ───────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def reaktion_setzen(nachricht, reaktion=None):
    """Reaktion setzen, wechseln oder entfernen — EINE je Person und Nachricht.

    ``reaktion`` eines der sechs Zeichen → gesetzt (ein vorhandenes Zeichen
    wird ersetzt, es entsteht KEINE zweite Zeile: der Primärschlüssel ist
    ``(nachricht, benutzer)``). Leer/``None`` → entfernt.

    Recht: LESEN im Gespräch (wer mitlesen darf, darf auch reagieren) — und
    die Nachricht muss existieren, auch wenn sie gelöscht ist: die Reaktionen
    bleiben an der Lücke stehen.
    """
    benutzer = _benutzer()
    zeichen = str(reaktion or "").strip()
    if zeichen and zeichen not in REAKTIONEN:
        throw("Unbekannte Reaktion.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        vorhanden = s.get(ChatReaktion, (n.name, benutzer))
        if not zeichen:
            if vorhanden is not None:
                s.execute(delete(ChatReaktion).where(
                    ChatReaktion.nachricht == n.name, ChatReaktion.benutzer == benutzer))
        elif vorhanden is None:
            s.add(ChatReaktion(nachricht=n.name, benutzer=benutzer,
                               reaktion=zeichen, erstellt_am=_jetzt()))
        else:
            vorhanden.reaktion = zeichen
        s.flush()
        return {"nachricht": n.name,
                "reaktionen": _reaktionen(s, [n.name], benutzer).get(n.name, [])}


@whitelist(methods=["POST"], allow_guest=False)
def lesestand_setzen(gespraech, nachricht=None):
    """Lesestand setzen — „bis hierhin gelesen“.

    Ohne ``nachricht``: bis zur NEUESTEN Nachricht des Gesprächs. Mit
    ``nachricht``: bis zu dieser (sie muss im Gespräch liegen; ein
    Zurücksetzen auf eine ältere Nachricht ist erlaubt — der Stand geht
    vorwärts wie rückwärts, sonst bliebe ein versehentlicher Klick endgültig).

    Recht: LESEN. Antwort: ``{gespraech, ungelesen}`` — der neue Zähler.
    Eine NAMENSLISTE „wer hat gelesen“ gibt es bewusst nicht (F2).
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        teilnahme = _teilnahme(s, g.name, benutzer)
        if nachricht not in (None, ""):
            ziel = _nachricht(s, str(nachricht), g.name)
        else:
            ziel = s.execute(
                select(ChatNachricht).where(ChatNachricht.gespraech == g.name)
                .order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
                .limit(1)
            ).scalar_one_or_none()
        if ziel is not None:
            teilnahme.letzter_lesestand = ziel.erstellt_am
            teilnahme.letzter_lesestand_nachricht = ziel.name
        s.flush()
        # CHAT-4a: Wer das Gespräch liest, hat die gebündelte Glocke gesehen —
        # sie wird als gelesen markiert (die Glocke selbst bleibt als Nachweis
        # stehen, wie jede andere Benachrichtigung). Nur wenn danach WIRKLICH
        # nichts ungelesen bleibt: ein Lesestand auf einer ÄLTEREN Nachricht
        # lässt die Glocke stehen (Reviews R1/d) — sie zeigt weiter die
        # ungelesenen Nachrichten an und wird beim nächsten Lauf
        # fortgeschrieben.
        ungelesen = _ungelesen_zaehlen(s, g.name, benutzer, teilnahme)
        _glocke_als_gelesen(s, g.name, benutzer, alles_gelesen=(ungelesen == 0))
        return {"gespraech": g.name, "bis": ziel.name if ziel else None,
                "ungelesen": ungelesen}


@whitelist(methods=["POST"], allow_guest=False)
def stumm_setzen(gespraech, an=True):
    """Gespräch für SICH stumm schalten (F3: jede Person für sich).

    Recht: LESEN. ``an`` als Wahrheitswert (``true``/``false``, „1“/„0“).

    Wirkung auf die Glocke (CHAT-4a): ``an`` heißt „keine Glocke mehr“ —
    ``chat_glocken_buendeln`` überspringt stumm geschaltete Personen ganz.
    Der UNGELESEN-ZÄHLER bleibt davon unberührt (Konzept 1/S1: „keine Glocke
    mehr, Zähler bleibt“); hier wird deshalb NUR ``stumm`` geschrieben und
    weder der Lesestand noch eine bestehende Glocke angefasst.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    wert = _wahr(an)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        teilnahme = _teilnahme(s, g.name, benutzer)
        teilnahme.stumm = wert
        s.flush()
        return {"gespraech": g.name, "stumm": wert}


# ── Endpunkte: Umfragen (CHAT-5) ────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def umfrage_anlegen(gespraech, frage, optionen=None, mehrfach=False, anonym=True,
                    frist=None):
    """Umfrage im Gespräch starten — sie erscheint als Nachricht im Verlauf.

    Recht: ANLEGEN in der Einheit — DIESELBE Aktion wie „Nachricht senden“
    (F5: jedes Mitglied darf Umfragen starten). Der Rechte-Kern entscheidet,
    hier steht keine Rollenlogik.

    ``frage``       Freitext, ≤ ``FRAGE_MAX`` Zeichen.
    ``optionen``    2–``OPTIONEN_MAX`` Texte (Liste ODER durch ``||`` getrennt,
                    damit Formular-Aufrufe nicht an der Liste scheitern).
    ``mehrfach``    Mehrfachauswahl erlaubt?
    ``anonym``      Standard ``True`` (F5). Bei ``True`` wird NIE eine Zeile
                    mit Personenbezug zur gewählten Option geschrieben.
    ``frist``       Zeitpunkt (``JJJJ-MM-TT`` oder ``JJJJ-MM-TT HH:MM``) in der
                    Zeitzone der Gemeinde. Leer = offen bis zur Schließung.

    Die Umfrage hängt an einer NEUEN Nachricht (``text`` = Frage): damit
    gelten Reihenfolge, Lesestand, Zitat, Reaktionen und Soft-Delete ohne
    Sonderfall. Der Verweis steht an der Nachricht, eine Umfrage kann also
    nicht ohne sie existieren und nicht in ein fremdes Gespräch zeigen.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    inhalt = _pruefe_frage(frage)
    auswahl = _pruefe_optionen(optionen)
    frist_am = _frist_lesen(frist)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.ANLEGEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        jetzt = _jetzt()
        umfrage = ChatUmfrage(
            name=_kennung("chat-umfrage"),
            gespraech=g.name,
            frage=inhalt,
            mehrfach=_wahr(mehrfach) if mehrfach not in (None, "") else False,
            # Standard ANONYM (F5). ``anonym`` fehlt/leer = True.
            anonym=True if anonym in (None, "") else _wahr(anonym),
            frist_am=frist_am,
            geschlossen_am=None,
            geschlossen_von=None,
            erstellt_am=jetzt,
        )
        s.add(umfrage)
        # PostgreSQL prüft Fremdschlüssel SOFORT (SQLite im Test tat es nicht):
        # ohne diesen `flush` schrieb die Nachricht ihre `umfrage`-Kennung,
        # bevor die Umfrage-Zeile in der Datenbank stand. Im Betrieb wäre
        # JEDE Umfrage mit 500 gescheitert.
        s.flush()
        for nummer, text_ in enumerate(auswahl, start=1):
            s.add(ChatUmfrageOption(umfrage=umfrage.name, nummer=nummer,
                                    text=text_, stimmen=0))
        zeile = ChatNachricht(
            name=_kennung("chat-n"),
            gespraech=g.name,
            autor_benutzer=benutzer or None,
            autor=_meine_kennung() or None,
            text=inhalt,
            erstellt_am=jetzt,
            umfrage=umfrage.name,
        )
        s.add(zeile)
        _teilnahme(s, g.name, benutzer)
        s.flush()
        daten = _umfrage_daten(s, umfrage, benutzer)
        # Die Kennung INNERHALB der Sitzung merken: nach dem `begin()`-Block
        # wird die Instanz detached, und ein Attributzugriff darauf löst
        # ``DetachedInstanceError`` aus (im Zwischenstand passiert).
        nachricht_name = zeile.name
    return {"name": nachricht_name, "umfrage": daten}


@whitelist(methods=["POST"], allow_guest=False)
def umfrage_abstimmen(umfrage, optionen=None):
    """Stimme abgeben (oder bei OFFENER Umfrage ändern).

    Recht: ANLEGEN in der Einheit — dieselbe Aktion wie „Nachricht senden“
    (wer abstimmen darf, darf auch senden; beides entscheidet der Rechte-Kern).

    ``optionen`` ist die Liste der gewählten Nummern. Ohne Mehrfachauswahl
    genau EINE Nummer; mit Mehrfachauswahl 1 … n. Geprüft wird, dass jede
    Nummer zur Umfrage gehört.

    ANONYM: die Abgabe ist nach der ersten Stimme ENDGÜLTIG (Entscheidung
    Operator) → ``ValidationError`` (400). Der Doppelklick-Fall ist auch ohne
    diese Prüfung gesperrt: der Primärschlüssel von ``chat_umfrage_abgabe``
    lässt nur eine Zeile zu, und die Zähler werden mit einem BEDINGTEN
    ``UPDATE`` (``stimmen = stimmen + 1``) je Option fortgeschrieben — kein
    Lesen-Ändern-Schreiben, also kein verlorener Zuwachs bei Gleichzeitigkeit.

    OFFEN: Stimme je Person und Option, ersetzt bei jedem Aufruf (bis zur
    Frist änderbar); die Namen stehen im Ergebnis.

    Nach Frist oder Schließung: ``ValidationError`` (400), das Ergebnis bleibt.
    """
    benutzer = _benutzer()
    if not benutzer or benutzer == "Guest":
        _h()
    umfrage = str(umfrage or "").strip()
    if not umfrage:
        throw("umfrage fehlt.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        u, g = _umfrage_lesen(s, umfrage)
        _erlaube(benutzer, rechte.ANLEGEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        _pruefe_offen(u)
        nummern = _pruefe_stimme(s, optionen, u)
        if u.anonym:
            # Erst die SPERRE, dann die Zähler: die Marke ist der Primärschlüssel.
            # Ein zweiter Aufruf (auch gleichzeitig) scheitert hier — und zwar
            # in der Datenbank, nicht an einer Prüfung, die zwei Aufrufe
            # gleichzeitig beide bestehen würden.
            #
            # BEKANNTE GRENZE (Review CHAT-5b, SOLL d): Marke und Zähler liegen
            # in DERSELBEN Transaktion. Nach außen verbindet nichts Person und
            # Option — ein Datenbank-ADMIN kann aber über ``xmin`` (PostgreSQL)
            # sehen, welche Marke mit welchem Zählerstand entstand. Bewusst
            # dokumentiert statt umgebaut; Details im DSGVO-Inventar an
            # ``chat_umfrage_abgabe``.
            try:
                with s.begin_nested():
                    s.add(ChatUmfrageAbgabe(umfrage=u.name, benutzer=benutzer,
                                            erstellt_am=_jetzt()))
                    s.flush()
            except IntegrityError:
                throw("Für diese Umfrage haben Sie bereits abgestimmt. "
                      "Anonyme Stimmen lassen sich nicht ändern.")
            for nummer in nummern:
                _zaehle(s, u.name, nummer, +1)
        else:
            _offene_stimmen_setzen(s, u, benutzer, nummern)
        s.flush()
        return _umfrage_daten(s, u, benutzer)


@whitelist(methods=["POST"], allow_guest=False)
def umfrage_schliessen(umfrage):
    """Umfrage vorzeitig schließen — ERSTELLER oder wer MODERIEREN darf.

    Recht: ZWEI Wege, beide über den Rechte-Kern:
      * der Ersteller (die Nachricht gehört ihm → SCHREIBEN mit eigenem
        Besitzer),
      * sonst MODERIEREN im Gespräch (HV/MV, in der Untergruppe auch GL).

    Idempotent: eine bereits geschlossene Umfrage bleibt geschlossen (der
    Zeitpunkt des ersten Schließens steht). Automatisch zur Frist schließt der
    Scheduler (``job_umfragen_schliessen``) — dieselbe Zeile, ohne
    ``geschlossen_von``.
    """
    benutzer = _benutzer()
    umfrage = str(umfrage or "").strip()
    if not umfrage:
        throw("umfrage fehlt.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        u, g = _umfrage_lesen(s, umfrage)
        eigene = _umfrage_ist_meine(s, u, benutzer)
        if eigene:
            _erlaube(benutzer, rechte.SCHREIBEN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe,
                     besitzer=_umfrage_autor(s, u.name), gespraech=g.name)
        else:
            _erlaube(benutzer, rechte.MODERIEREN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe, gespraech=g.name)
        if u.geschlossen_am is None:
            u.geschlossen_am = _jetzt()
            u.geschlossen_von = benutzer or None
            s.flush()
        return _umfrage_daten(s, u, benutzer)


@whitelist(allow_guest=False)
def umfrage_ergebnis(umfrage):
    """Ergebnis einer Umfrage lesen — wer das Gespräch lesen darf.

    Rein lesend (GET). Antwort wie im Verlauf: ``_umfrage_daten``.
    """
    benutzer = _benutzer()
    umfrage = str(umfrage or "").strip()
    if not umfrage:
        throw("umfrage fehlt.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        u, g = _umfrage_lesen(s, umfrage)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        return _umfrage_daten(s, u, benutzer)


# ── Innen: Umfragen ─────────────────────────────────────────────────────────


def _pruefe_frage(frage) -> str:
    """Die Frage: nicht leer am Rand, ≤ ``FRAGE_MAX`` ZEICHEN (wie Text)."""
    if frage is None or not str(frage).strip():
        throw("Bitte eine Frage eingeben.")
    inhalt = str(frage).strip()
    if len(inhalt) > FRAGE_MAX:
        throw(f"Die Frage darf höchstens {FRAGE_MAX} Zeichen lang sein "
              f"(eingegeben: {len(inhalt)}).")
    return inhalt


def _pruefe_optionen(optionen) -> list[str]:
    """2 … ``OPTIONEN_MAX`` Optionen, jede nicht leer und ≤ ``OPTION_MAX``.

    Nimmt eine LISTE (JSON/HTTP) oder EINEN String mit ``||`` als Trenner
    (Formular). Andere Trenner werden NICHT geraten: eine Option darf Kommas
    enthalten („Samstag, 18 Uhr“).
    """
    if optionen is None or optionen == "":
        roh: list = []
    elif isinstance(optionen, str):
        roh = optionen.split("||")
    else:
        roh = list(optionen)
    texte: list[str] = []
    for eintrag in roh:
        text = str(eintrag or "").strip()
        if not text:
            continue
        if len(text) > OPTION_MAX:
            throw(f"Eine Option darf höchstens {OPTION_MAX} Zeichen lang sein.")
        texte.append(text)
    if len(texte) < OPTIONEN_MIN:
        throw(f"Eine Umfrage braucht mindestens {OPTIONEN_MIN} Optionen.")
    if len(texte) > OPTIONEN_MAX:
        throw(f"Eine Umfrage darf höchstens {OPTIONEN_MAX} Optionen haben "
              f"(eingegeben: {len(texte)}).")
    return texte


def _frist_lesen(frist) -> datetime | None:
    """Frist als Wandzeit der Gemeinde; leer → ``None`` (offen bis Schließung).

    Akzeptiert ``datetime``, ``JJJJ-MM-TT`` und ``JJJJ-MM-TT HH:MM``. Ein
    Zeitpunkt MIT Zeitzone wird auf die Wandzeit der Gemeinde umgerechnet
    (dieselbe Uhr, in der die Umfrage steht). Vergangene Fristen werden
    ABGEWIESEN: eine Umfrage, die man nicht mehr beantworten kann, ist keine.
    """
    if frist is None or str(frist).strip() == "":
        return None
    wert = frist
    if isinstance(wert, str):
        text_ = wert.strip().replace("T", " ")
        for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                wert = datetime.strptime(text_, form)
                break
            except ValueError:
                continue
        else:
            throw("Die Frist bitte als JJJJ-MM-TT oder JJJJ-MM-TT HH:MM angeben.")
    if isinstance(wert, datetime):
        if wert.tzinfo is not None:
            from diakronos_app.zeit import zeitzone

            wert = wert.astimezone(zeitzone()).replace(tzinfo=None)
        if wert <= _jetzt():
            throw("Die Frist liegt in der Vergangenheit.")
        return wert
    throw("Die Frist bitte als JJJJ-MM-TT oder JJJJ-MM-TT HH:MM angeben.")


def _pruefe_stimme(s, optionen, u: ChatUmfrage) -> list[int]:
    """Die gewählten Optionsnummern — geprüft gegen DIESE Umfrage.

    Ohne Mehrfachauswahl genau eine Nummer (sonst ``ValidationError``): eine
    stille Kürzung auf die erste wäre eine Entscheidung, die der Person nicht
    gehört.
    """
    if optionen is None or optionen == "":
        roh: list = []
    elif isinstance(optionen, str):
        roh = [t for t in optionen.replace(";", ",").split(",")]
    elif isinstance(optionen, (int, float)):
        # Eine EINZELNE Nummer (``optionen=1``) ist der häufigste Aufruf —
        # ohne diesen Zweig würde ``list(1)`` mit ``TypeError`` abstürzen
        # statt zu prüfen (im Zwischenstand passiert).
        roh = [optionen]
    else:
        roh = list(optionen)
    nummern: list[int] = []
    for eintrag in roh:
        text = str(eintrag if eintrag is not None else "").strip()
        if not text:
            continue
        try:
            nummer = int(text)
        except (TypeError, ValueError):
            throw("Bitte die Nummer der Option angeben.")
        if nummer not in nummern:
            nummern.append(nummer)
    if not nummern:
        throw("Bitte mindestens eine Option wählen.")
    if len(nummern) > 1 and not u.mehrfach:
        throw("Diese Umfrage erlaubt nur eine Antwort.")
    # Jede Nummer muss zu DIESER Umfrage gehören: der Endpunkt ist der einzige
    # Schreibweg, und eine Stimme auf eine nicht existierende Option würde in
    # `chat_stimme` hängen (FK) oder den Zähler einer fremden Option treffen.
    vorhanden = {int(n) for (n,) in s.execute(
        select(ChatUmfrageOption.nummer).where(ChatUmfrageOption.umfrage == u.name)
    ).all()}
    fremd = [n for n in nummern if n not in vorhanden]
    if fremd:
        throw("Diese Option gehört nicht zur Umfrage.")
    return nummern


def _pruefe_offen(u: ChatUmfrage) -> None:
    """Ist die Umfrage noch offen? Sonst ``ValidationError`` (400)."""
    jetzt = _jetzt()
    if u.geschlossen_am is not None:
        throw("Diese Umfrage ist geschlossen — es kann nicht mehr abgestimmt werden.")
    if u.frist_am is not None and u.frist_am <= jetzt:
        throw("Die Frist dieser Umfrage ist abgelaufen — es kann nicht mehr "
              "abgestimmt werden.")


def _zaehle(s, umfrage: str, nummer: int, delta: int) -> None:
    """Zähler einer Option fort schreiben — BEDINGT in der Datenbank.

    ``stimmen = stimmen + delta`` rechnet die Datenbank, nicht Python: zwei
    gleichzeitige Abgaben verlieren so keinen Zuwachs (kein
    Lesen-Ändern-Schreiben). Die Untergrenze 0 ist Absicht — ein negativer
    Zähler wäre kein Ergebnis, sondern ein Fehler, der stehen bliebe.

    Die Untergrenze steht als ``CASE`` da, NICHT als ``func.max(0, …)``: das
    zweiargumentige ``max`` gibt es nur in SQLite, PostgreSQL kennt es nicht
    („function max(integer, integer) does not exist“) und jede Stimmabgabe
    wäre dort mit 500 gescheitert. ``CASE`` ist auf beiden Dialekten dasselbe
    SQL; ``GREATEST`` wäre ebenfalls dialektübergreifend, aber NULL-behaftet
    (GREATEST(NULL, x) = NULL auf PostgreSQL), und ein fehlender Zähler ist
    hier kein Sonderfall, den man aussitzen sollte.
    """
    s.execute(
        update(ChatUmfrageOption)
        .where(ChatUmfrageOption.umfrage == umfrage,
               ChatUmfrageOption.nummer == nummer)
        .values(stimmen=case(
            (func.coalesce(ChatUmfrageOption.stimmen, 0) + delta < 0, 0),
            else_=func.coalesce(ChatUmfrageOption.stimmen, 0) + delta,
        ))
    )


def _offene_stimmen_setzen(s, u: ChatUmfrage, benutzer: str, nummern: list[int]) -> None:
    """Stimmen einer OFFENEN Umfrage ersetzen und die Zähler nachziehen.

    Die Zähler werden um die DIFFERENZ je Option verschoben, nicht neu
    gezählt: die Zählerspalte bleibt damit auch dann die Wahrheit, wenn eine
    Person später gelöscht wird und ihre Stimmenzeile fällt.

    Gegen das Rennen beim ÄNDERN (zwei gleichzeitige Aufrufe derselben Person):

      * die eigenen Zeilen werden mit ``FOR UPDATE`` gesperrt, und
      * heruntergezählt wird NUR, wenn das ``DELETE`` genau eine Zeile
        getroffen hat (``rowcount == 1``). Hat ein gleichzeitiger Aufruf die
        Zeile schon entfernt, hat er auch schon heruntergezählt — ein zweites
        Herunterzählen wäre ein Zähler, der nicht zu den Zeilen passt
        (Einzelauswahl ergäbe zwei Stimmen, obwohl eine Person nur eine hat).

    Das Rennen beim HINZUFÜGEN bleibt der Primärschlüssel von
    ``chat_stimme``: eine zweite Zeile (Umfrage, Option, Person) scheitert in
    der Datenbank, und der Aufruf fällt als Ganzes zurück (kein Zähler ohne
    Zeile).

    ``FOR UPDATE`` wird nur gesetzt, wo der Dialekt es kennt; SQLite sperrt
    ohnehin die ganze Schreibtransaktion und lehnt die Klausel ab.
    """
    sperren = s.get_bind().dialect.name not in ("sqlite",)
    if sperren:
        # Erst die Umfrage-Zeile sperren: serialisiert gleichzeitige Aufrufe
        # auch bei der ERSTEN Stimme (FOR UPDATE auf leere Mengen sperrt nichts).
        s.execute(select(ChatUmfrage.name).where(ChatUmfrage.name == u.name).with_for_update())
    abfrage = select(ChatStimme.option).where(ChatStimme.umfrage == u.name,
                                              ChatStimme.benutzer == benutzer)
    if sperren:
        abfrage = abfrage.with_for_update()
    alt = {int(a) for a in s.execute(abfrage).scalars().all()}
    neu = set(nummern)
    for nummer in sorted(neu - alt):
        _zaehle(s, u.name, nummer, +1)
        s.add(ChatStimme(umfrage=u.name, option=nummer, benutzer=benutzer,
                         erstellt_am=_jetzt()))
    for nummer in sorted(alt - neu):
        weg = s.execute(delete(ChatStimme).where(ChatStimme.umfrage == u.name,
                                                 ChatStimme.option == nummer,
                                                 ChatStimme.benutzer == benutzer))
        if weg.rowcount == 1:
            _zaehle(s, u.name, nummer, -1)


def _umfragen_laden(s, kennungen, benutzer: str) -> dict[str, dict[str, Any]]:
    """Die Umfragedaten zu einer SEITE Nachrichten — in fester Zahl Abfragen.

    Vier Abfragen für die ganze Seite (Umfragen, Optionen, eigene Stimmen,
    eigene Abgaben) — keine je Nachricht. Das ist die Zusage aus der Karte
    „ohne N+1“.

    Die NAMEN (offene Umfrage) kommen über ``_personen``/``_konto_namen`` aus
    den Konten der Stimmenzeilen — wer abstimmen durfte, steht damit
    namentlich im Ergebnis. Bei einer anonymen Umfrage gibt es KEINE
    Stimmenzeilen, also auch keine Namen.
    """
    ids = [str(k) for k in kennungen if k]
    if not ids:
        return {}
    umfragen = {str(u.name): u for u in s.execute(
        select(ChatUmfrage).where(ChatUmfrage.name.in_(ids))
    ).scalars().all()}
    if not umfragen:
        return {}
    optionen: dict[str, list[ChatUmfrageOption]] = {}
    for o in s.execute(
        select(ChatUmfrageOption)
        .where(ChatUmfrageOption.umfrage.in_(list(umfragen)))
        .order_by(ChatUmfrageOption.umfrage, ChatUmfrageOption.nummer)
    ).scalars().all():
        optionen.setdefault(str(o.umfrage), []).append(o)

    eigene_stimmen: dict[str, list[int]] = {}
    for kennung, nummer in s.execute(
        select(ChatStimme.umfrage, ChatStimme.option)
        .where(ChatStimme.umfrage.in_(list(umfragen)),
               ChatStimme.benutzer == benutzer)
    ).all():
        eigene_stimmen.setdefault(str(kennung), []).append(int(nummer))
    eigene_abgabe = {str(k) for k in s.execute(
        select(ChatUmfrageAbgabe.umfrage)
        .where(ChatUmfrageAbgabe.umfrage.in_(list(umfragen)),
               ChatUmfrageAbgabe.benutzer == benutzer)
    ).scalars().all()}

    # Namen je Stimme — nur für OFFENE Umfragen (anonym hat keine Zeilen).
    offene = [k for k, u in umfragen.items() if not u.anonym]
    namen_je_option: dict[tuple[str, int], list[str]] = {}
    #: Abgegebene PERSONEN je Umfrage. Anonym: die Marken, offen: die Konten.
    abgegeben: dict[str, int] = {
        kennung: 0 for kennung in umfragen
    }
    for kennung in umfragen:
        if kennung in eigene_abgabe:
            abgegeben[kennung] = max(abgegeben[kennung], 1)
    # Anonyme Umfragen: JEDE Marke ist eine abgegebene Person (eine je Person).
    anonyme = [k for k, u in umfragen.items() if u.anonym]
    if anonyme:
        for kennung, anzahl in s.execute(
            select(ChatUmfrageAbgabe.umfrage, func.count())
            .where(ChatUmfrageAbgabe.umfrage.in_(anonyme))
            .group_by(ChatUmfrageAbgabe.umfrage)
        ).all():
            abgegeben[str(kennung)] = int(anzahl or 0)
    if offene:
        stimmen = s.execute(
            select(ChatStimme.umfrage, ChatStimme.option, ChatStimme.benutzer)
            .where(ChatStimme.umfrage.in_(offene))
        ).all()
        konten = {str(k) for _, _, k in stimmen if k}
        mitglied_je_konto = _mitglieder_je_konto(s, konten)
        anzeige = _personen(s, set(mitglied_je_konto.values()))
        konto_anzeige = _konto_namen(s, konten)
        # Wer hat in DIESER Umfrage abgestimmt (= welches Konto)?
        # Als DICT-von-MENGEN ohne `.add()`: der Inventar-Wächter liest den
        # Funktionsrumpf und hielte `…add(…)` für einen Schreibvorgang — der
        # Verlauf ist rein lesend (SEC-11c), und das soll er auch nach dem
        # Rumpfbefund bleiben.
        stimmende: dict[str, set[str]] = {}
        for umfrage_id, nummer, konto in stimmen:
            konto = str(konto or "")
            kennung = str(umfrage_id)
            stimmende[kennung] = stimmende.get(kennung, set()) | {konto}
            name = (anzeige.get(mitglied_je_konto.get(konto, ""))
                    or konto_anzeige.get(konto) or konto)
            namen_je_option.setdefault((kennung, int(nummer)), []).append(name)
        for kennung, wer in stimmende.items():
            abgegeben[str(kennung)] = len(wer)

    return {
        kennung: _umfrage_form(u, optionen.get(kennung, []), benutzer,
                               eigene_stimmen.get(kennung, []),
                               kennung in eigene_abgabe,
                               namen_je_option, abgegeben.get(kennung, 0))
        for kennung, u in umfragen.items()
    }


def _mitglieder_je_konto(s, konten) -> dict[str, str]:
    """``{konto: mitglied.name}`` für die Anzeige einer Stimme (eine Abfrage)."""
    namen = {str(k) for k in konten if k}
    if not namen:
        return {}
    zeilen = s.execute(
        select(Mitglied.user, Mitglied.name).where(Mitglied.user.in_(namen))
    ).all()
    return {str(konto): str(kennung) for konto, kennung in zeilen if konto and kennung}


def _umfrage_form(u: ChatUmfrage, optionen: list[ChatUmfrageOption], benutzer: str,
                  eigene: list[int], hat_abgestimmt: bool,
                  namen_je_option: dict[tuple[str, int], list[str]],
                  abgegeben: int = 0) -> dict[str, Any]:
    """Eine Umfrage als Antwortblock (Verlauf, Ergebnis, Abstimmen).

    ``hinweis`` steht NUR, wenn weniger als ``HINWEIS_AB`` Personen abgestimmt
    haben — der Text sagt, dass das Ergebnis dann erratbar ist (Karte CHAT-5,
    Konzept S2). Er hängt an der ZAHL der Abgegebenen, nicht an ``anonym``:
    auch eine offene Umfrage mit zwei Stimmen sagt wenig.

    ``eigene_stimme`` ist bei einer anonymen Umfrage ``None`` — es gibt keine
    (und es darf keine geben); ``abgestimmt`` sagt dort ``true``/``false``.

    ``abgegeben`` ist die Zahl der PERSONEN, nicht der Stimmen: bei einer
    anonymen Umfrage sind die Zähler eindeutig (eine Marke je Person), bei
    einer offenen zählt die Menge der Konten — wer zwei Optionen gewählt hat,
    ist EINE abgebende Person. Anonym kommt sie aus ``chat_umfrage_abgabe``,
    offen aus der Menge der Konten in ``namen_je_option``; beides zählt
    ``_umfragen_laden`` für die ganze Seite, ``_zaehle_abgegeben`` für eine
    einzelne Umfrage.
    """
    gesamt = _summe(optionen)
    return {
        "name": u.name,
        "gespraech": u.gespraech,
        "frage": u.frage,
        "mehrfach": bool(u.mehrfach),
        "anonym": bool(u.anonym),
        "frist_am": _isoopt(u.frist_am),
        "geschlossen_am": _isoopt(u.geschlossen_am),
        "geschlossen_von": u.geschlossen_von,
        "offen": _ist_offen(u),
        "stimmen_gesamt": gesamt,
        "abgegeben": abgegeben,
        "hinweis": _hinweis(abgegeben),
        "abgestimmt": bool(hat_abgestimmt) or bool(eigene),
        "eigene_stimme": None if u.anonym else sorted(int(n) for n in eigene),
        "optionen": [
            {
                "nummer": int(o.nummer),
                "text": o.text,
                "stimmen": int(o.stimmen or 0),
                # Namen NUR bei offener Umfrage (anonym: leere Liste, weil es
                # keine Zeile gibt, aus der sie käme).
                "namen": [] if u.anonym else namen_je_option.get((u.name, int(o.nummer)), []),
            }
            for o in optionen
        ],
    }


def _summe(optionen: list[ChatUmfrageOption]) -> int:
    """Summe der Zähler einer Umfrage (Stimmen, nicht Personen)."""
    return sum(int(o.stimmen or 0) for o in optionen)


def _hinweis(abgegeben: int) -> str | None:
    """Hinweistext unter ``HINWEIS_AB`` Abgegebenen (Karte CHAT-5), sonst ``None``."""
    if abgegeben >= HINWEIS_AB:
        return None
    return ("Ergebnis bei wenigen Teilnehmenden erratbar — bei anonymen "
            "Umfragen lässt sich die Stimme mit Zusatzwissen zuordnen.")


def _ist_offen(u: ChatUmfrage) -> bool:
    """Nimmt die Umfrage JETZT noch Stimmen an?"""
    if u.geschlossen_am is not None:
        return False
    if u.frist_am is not None and u.frist_am <= _jetzt():
        return False
    return True


def _umfrage_daten(s, u: ChatUmfrage, benutzer: str) -> dict[str, Any]:
    """Die Umfragedaten EINER Umfrage (Anlegen, Abstimmen, Ergebnis)."""
    daten = _umfragen_laden(s, [u.name], benutzer).get(str(u.name))
    if daten is not None:
        return daten
    # Keine Optionen (darf nicht vorkommen) — trotzdem eine ganze Antwortform.
    return _umfrage_form(u, [], benutzer, [], False, {})


def _umfrage_lesen(s, umfrage: str) -> tuple[ChatUmfrage, ChatGespraech]:
    """Umfrage + ihr Gespräch per Kennung; unbekannt → 404 (nichts raten).

    Eine Umfrage lebt NUR als Nachricht im Verlauf: ist die Hülle-Nachricht
    gelöscht (selbst gelöscht oder von der Moderation entfernt), ist die
    Umfrage für ALLE Wege weg — Abstimmen, Ergebnis, Schließen. Sonst nähme
    eine entfernte Umfrage weiter Stimmen an und lieferte bei einer offenen
    Umfrage sogar Namen. Wie bei einer unbekannten Kennung: 404, nicht 403 —
    die Kennung allein soll nichts über ihren Inhalt verraten.
    """
    if not umfrage:
        throw("umfrage fehlt.")
    zeile = s.get(ChatUmfrage, umfrage)
    if zeile is None:
        raise DoesNotExistError("Umfrage nicht gefunden.")
    huelle = _umfrage_nachricht(s, zeile.name)
    if huelle is None or huelle.geloescht_am is not None:
        raise DoesNotExistError("Umfrage nicht gefunden.")
    gespraech = _gespraech_lesen(s, zeile.gespraech)
    return zeile, gespraech


def _umfrage_nachricht(s, umfrage: str) -> ChatNachricht | None:
    """Die Nachricht, an der die Umfrage hängt (für Besitz und Anzeige)."""
    return s.execute(
        select(ChatNachricht).where(ChatNachricht.umfrage == umfrage)
    ).scalars().first()


def _umfrage_autor(s, umfrage: str) -> str | None:
    """Das KONTO, das die Umfrage gestartet hat (Besitz = die Hülle-Nachricht).

    Nimmt die KENNUNG der Umfrage (nicht die Instanz): aufgerufen aus
    ``_umfrage_ist_meine`` und aus ``umfrage_schliessen``, wo nur ``u`` bzw.
    der Name zur Hand ist.
    """
    n = _umfrage_nachricht(s, umfrage)
    return n.autor_benutzer if n is not None else None


def _umfrage_ist_meine(s, u: ChatUmfrage, benutzer: str) -> bool:
    """Hat DIESE Person die Umfrage gestartet? — verglichen wird das KONTO."""
    autor = _umfrage_autor(s, u.name)
    return bool(autor) and str(autor) == str(benutzer or "")


def schliesse_faellige(jetzt: datetime | None = None) -> int:
    """Umfragen schließen, deren Frist erreicht ist — der Scheduler-Job ruft DAS.

    Kein eigener Job, kein eigener Zeitgeber: der bestehende Scheduler
    (``scheduler.job_umfragen_schliessen``) ruft diese Funktion einmal am Tag
    und schreibt ``geschlossen_am`` auf die Frist (nicht auf „jetzt“ — die
    Frist IST der Schließzeitpunkt; das macht die Anzeige unabhängig davon,
    wann der Job tatsächlich lief). ``geschlossen_von`` bleibt ``NULL``:
    automatisch heißt automatisch.

    Die Schließung ist idempotent (``WHERE geschlossen_am IS NULL``); eine
    bereits vorzeitig geschlossene Umfrage behält ihren Zeitpunkt.
    Rückgabe: Zahl der geschlossenen Umfragen.
    """
    zeit = jetzt or _jetzt()
    with dbmod.SessionLocal.begin() as s:
        ergebnis = s.execute(
            update(ChatUmfrage)
            .where(ChatUmfrage.geschlossen_am.is_(None),
                   ChatUmfrage.frist_am.is_not(None),
                   ChatUmfrage.frist_am <= zeit)
            .values(geschlossen_am=ChatUmfrage.frist_am)
        )
        return int(ergebnis.rowcount or 0)


# ── Endpunkte: Melden und Moderation (CHAT-6) ───────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def meldung_senden(nachricht, grund, freitext=None):
    """Eine Nachricht melden (Konzept 2.5, Karte CHAT-6).

    Recht: LESEN im Gespräch der Nachricht — wer mitlesen darf, darf melden.
    Eine UNBEKANNTE Nachricht ist **404** (``_nachricht``): die Kennung allein
    verrät nichts, es gibt sie schlicht nicht. Eine BESTEHENDE Nachricht in
    einem Gespräch ohne Lese-Recht ist dagegen **403 ohne Inhalt** — wer nicht
    mitliest, erfährt auch nicht, dass es die Nachricht gibt. Gäste haben kein
    Modul (der Kern gibt ihnen keines) und fallen ebenfalls auf 403 heraus.

    Die EIGENE Nachricht ist nicht meldbar (``ValidationError`` → 400): eine
    Meldung gegen sich selbst hat keinen Moderationsfall. Eine bereits
    GELÖSCHTE Nachricht ist ebenfalls nicht meldbar (400): es gibt keinen
    sichtbaren Inhalt mehr, über den zu entscheiden wäre.

    ``grund`` muss einer der fünf Schlüssel aus ``MELDEGRUENDE`` sein (der
    Anzeigetext kommt aus der Oberfläche, nicht vom Server). ``freitext`` ist
    optional und auf 500 ZEICHEN begrenzt.

    Eine OFFENE Meldung je (Nachricht, Melder): die zweite wird abgewiesen
    (400) — und in der Datenbank durch den partiellen Unique-Index zusätzlich
    verhindert (zwei gleichzeitige Aufrufe). Nach einer Entscheidung
    (erledigt/verworfen) darf dieselbe Person erneut melden.

    Antwort: ``{name, nachricht, gespraech, grund, stand, erstellt_am,
    meldung_offen}`` — OHNE den Melder (er geht nur an die Moderation) und
    ohne den Freitext (die Antwort ist keine Lesequelle für die Meldung).
    """
    benutzer = _benutzer()
    kennung = str(nachricht or "").strip()
    if not kennung:
        throw("nachricht fehlt.")
    schluessel = str(grund or "").strip()
    if schluessel not in MELDEGRUENDE:
        throw("Bitte einen der angebotenen Meldegründe wählen.")
    text = _pruefe_freitext(freitext)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, kennung, None)
        g = _gespraech_lesen(s, n.gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        if _ist_meine(n, benutzer):
            throw("Die eigene Nachricht lässt sich nicht melden.")
        if n.geloescht_am is not None:
            throw("Eine gelöschte Nachricht lässt sich nicht melden.")
        offen = s.execute(
            select(ChatMeldung.name).where(
                ChatMeldung.nachricht == n.name,
                ChatMeldung.melder == benutzer,
                ChatMeldung.stand == MELDUNG_OFFEN,
            )
        ).scalar_one_or_none()
        if offen is not None:
            throw("Diese Nachricht wurde von dir bereits gemeldet.")
        zeile = ChatMeldung(
            name=_kennung("chat-meldung"),
            nachricht=n.name,
            melder=benutzer or None,
            grund=schluessel,
            freitext=text,
            stand=MELDUNG_OFFEN,
            erstellt_am=_jetzt(),
        )
        try:
            with s.begin_nested():
                s.add(zeile)
                s.flush()
        except IntegrityError:
            # Zwei gleichzeitige Aufrufe: der partielle Index lässt nur eine
            # offene Meldung durch (dasselbe Muster wie `_gespraech_holen`).
            throw("Diese Nachricht wurde von dir bereits gemeldet.")
        empfaenger = [k for k in rechte.chat_moderatoren(g.gruppe, g.untergruppe)
                      if k != benutzer and k != str(n.autor_benutzer or "")]
        antwort = {
            "name": zeile.name,
            "nachricht": n.name,
            "gespraech": g.name,
            "grund": schluessel,
            "stand": MELDUNG_OFFEN,
            "erstellt_am": _isoopt(zeile.erstellt_am),
            # Der Zähler, den die Oberfläche braucht: „liegt die Meldung bei
            # der Moderation“. Kein Melder, kein Freitext.
            "meldung_offen": True,
        }
    # Nach dem Commit: Glocke an die Moderation der Einheit (Empfänger aus dem
    # Rechte-Kern, `chat_moderatoren`). Ohne Melder, ohne Nachrichtentext.
    _glocke_neue_meldung(empfaenger, antwort["name"])
    return antwort


@whitelist(allow_guest=False)
def meldungen_liste(stand=None, gespraech=None):
    """Die Meldungen, die DIESE Person moderieren darf — offen zuerst.

    Recht: KEIN pauschaler Rechte-Satz, sondern je Gespräch
    ``rechte.darf(benutzer, MODERIEREN, "chat_gespraech", gespraech=…)``: HV/MV
    der Gruppe, in der Untergruppe auch GL, Administrator. Die Auswahl der
    Gespräche läuft über ``_erlaube(...)`` — dieselbe Funktion, die auch
    ``meldung_entscheiden`` fragt; eine eigene Rollenlogik gibt es hier nicht.

    Reihenfolge der Schritte (Review Punkt 1): ERST die moderierbaren
    Gespräche bestimmen, DANN mit ``ChatNachricht.gespraech.in_(…)`` filtern,
    ERST DANN ``limit``. Sonst schnitte die Grenze Meldungen weg, die diese
    Person moderieren darf, bevor der Rechtefilter sie sieht.

    Gefragt wird NICHT für jedes Gespräch der Instanz, sondern nur für die
    KANDIDATEN aus den Meldungen (Review Runde 2, A3): ``SELECT DISTINCT
    n.gespraech`` über die Meldungen (nur nicht gelöschte Gespräche). Erst
    wenn keiner dieser Kandidaten moderierbar ist, wird — mit frühem Abbruch
    beim ersten „ja“ — über die übrigen Gespräche gegangen; so bleibt die
    Unterscheidung „[] statt 403“ erhalten, ohne je Meldung alle Gespräche zu
    prüfen. Gefragt wird ausschließlich ``_erlaube``, es gibt keine eigene
    Rollenlogik.

    403 nur, wenn es KEIN EINZIGES moderierbares Gespräch gibt — ein Moderator
    ohne (offene) Meldungen bekommt ``{"meldungen": [], "offen": 0}``.

    ``stand`` filtert auf ``offen``/``erledigt``/``verworfen`` (leer = offen —
    das ist die Arbeitsliste der Moderation). ``gespraech`` grenzt auf EIN
    Gespräch ein (dieselbe Rechtefrage; ohne Recht darauf → 403, nicht „leere
    Liste“).

    Je Meldung steht der GEMELDETE AUSSCHNITT (Konzept 2.5): die Nachricht im
    Zustand VOR der Entscheidung (Text, Autor, Zeit) und die fünf Nachrichten
    davor — nur so ist ein Zusammenhang beurteilbar. Der MELDER steht hier,
    weil die Moderation ihn braucht („wer meldet im Dutzend“, 2.5); er steht in
    KEINER Antwort an die gemeldete Person.

    Antwort: ``{meldungen: [...], offen: <Zähler der offenen>}``. Der Zähler
    zählt per SQL über die moderierbaren Gespräche — UNABHÄNGIG von ``stand``
    und vom ``limit`` (er sagt der Glocke, wie viel Arbeit wartet).
    """
    benutzer = _benutzer()
    gewuenscht = str(stand or "").strip()
    if gewuenscht and gewuenscht not in MELDUNG_STAENDE:
        throw("Unbekannter Stand.")
    nur_gespraech = str(gespraech or "").strip() or None
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        # 1) KANDIDATEN (Review Runde 2, A3): die Gespräche, in denen überhaupt
        #    eine Meldung liegt — ``DISTINCT``, nur nicht gelöschte Gespräche,
        #    bei ``gespraech`` genau das eine. NICHT alle Gespräche der Instanz.
        kandidaten_abfrage = (
            select(ChatNachricht.gespraech)
            .join(ChatMeldung, ChatMeldung.nachricht == ChatNachricht.name)
            .join(ChatGespraech, ChatGespraech.name == ChatNachricht.gespraech)
            .where(ChatGespraech.geloescht_am.is_(None))
            .distinct()
        )
        if nur_gespraech:
            kandidaten_abfrage = kandidaten_abfrage.where(
                ChatNachricht.gespraech == nur_gespraech)
        kandidaten = sorted(s.execute(kandidaten_abfrage).scalars().all())

        # 2) Je Kandidat EINE Rechtefrage über den Rechte-Kern (`_erlaube`),
        #    nichts Eigenes. Gefragt wird nur nach den Gesprächen, in denen
        #    Meldungen liegen.
        eigene: dict[str, ChatGespraech] = {}
        for kennung in kandidaten:
            try:
                g = _gespraech_lesen(s, kennung)
            except DoesNotExistError:
                continue          # Gespräch zwischenzeitlich weg — kein Kandidat
            if _darf_moderieren(benutzer, g):
                eigene[g.name] = g
        if not eigene:
            # 3) Keiner der Kandidaten ist moderierbar. Jetzt erst entscheidet
            #    sich „[] vs 403“: gibt es überhaupt ein moderierbares
            #    Gespräch? Mit frühem Abbruch beim ersten „ja“ — der Normalfall
            #    (Leitung hat ein Gespräch) kostet keinen zweiten Durchlauf.
            rest = s.execute(
                select(ChatGespraech)
                .where(ChatGespraech.geloescht_am.is_(None))
                .order_by(ChatGespraech.name)
            ).scalars()
            for g in rest:
                if nur_gespraech and g.name != nur_gespraech:
                    continue
                if _darf_moderieren(benutzer, g):
                    break
            else:
                # Harte Grenze: gar kein moderierbares Gespräch → 403 ohne Inhalt.
                _h()
            # Ein moderierbares Gespräch gibt es, in ihm liegt nur keine
            # (passende) Meldung → leere Liste, KEIN 403.
            return {"meldungen": [], "offen": 0}
        # 4) Meldungen NUR aus diesen Gesprächen — erst danach das Limit.
        bedingung = [
            ChatMeldung.stand == (gewuenscht or MELDUNG_OFFEN),
            ChatNachricht.gespraech.in_(sorted(eigene)),
        ]
        # (`nur_gespraech` steckt schon in `eigene`: der Kandidatenlauf oben
        #  hat auf genau dieses Gespräch eingegrenzt — keine zweite Bedingung.)
        zeilen = s.execute(
            select(ChatMeldung, ChatNachricht)
            .join(ChatNachricht, ChatNachricht.name == ChatMeldung.nachricht)
            .where(*bedingung)
            .order_by(ChatMeldung.erstellt_am.desc(), ChatMeldung.name.desc())
            .limit(MELDUNGEN_MAX)
        ).all()
        namens_cache = _melde_namen(s, [(m, n) for m, n in zeilen])
        ergebnis = [_meldung_zeile(s, m, n, eigene[str(n.gespraech)], benutzer,
                                   namens_cache) for m, n in zeilen]
        # 3) Der Zähler "offen": per SQL über die moderierbaren Gespräche,
        #    ohne den `stand`-Filter und ohne das Limit.
        offen_gesamt = int(s.execute(
            select(func.count()).select_from(ChatMeldung)
            .join(ChatNachricht, ChatNachricht.name == ChatMeldung.nachricht)
            .where(ChatMeldung.stand == MELDUNG_OFFEN,
                   ChatNachricht.gespraech.in_(sorted(eigene)))
        ).scalar_one())
    return {"meldungen": ergebnis, "offen": offen_gesamt}


@whitelist(methods=["POST"], allow_guest=False)
def meldung_entscheiden(meldung, entscheidung, grund=None):
    """Über eine Meldung entscheiden: ``entfernen`` oder ``verwerfen``.

    ``entfernen``  Soft-Delete der gemeldeten Nachricht mit ``entfernt_grund``
                   (= ``grund``, PFLICHT — Konzept 2.5: „Grund ist Pflicht“)
                   und ``geloescht_von`` = entscheidende Person. Der Verlauf
                   zeigt danach „von der Moderation entfernt“, der Text geht
                   nicht mehr nach außen (bleibt in der Datenbank, CHAT-8).
                   ALLE weiteren offenen Meldungen derselben Nachricht gelten
                   damit als erledigt — der Fall ist entschieden, sonst bliebe
                   eine Arbeitsliste stehen, die nichts mehr zu tun hat.
    ``verwerfen``  Die Meldung trägt nicht; die Nachricht bleibt stehen. Ein
                   ``grund`` ist dabei optional und wird nur an der Meldung
                   vermerkt.

    Recht: ``rechte.darf(…, MODERIEREN, "chat_gespraech", gespraech=…)`` im
    Gespräch der gemeldeten Nachricht — dieselbe Frage wie in der Liste
    (``_erlaube``), nichts Eigenes.

    Nicht entscheidbar:
      * eine bereits entschiedene Meldung — **409** (``KonfliktError``): die
        Entscheidung ist endgültig, der Zustand passt nicht mehr,
      * eine Meldung gegen die EIGENE Nachricht (**400**, niemand moderiert
        sich selbst; die Leitung, die selbst schreibt, bleibt auf die zweite
        Leitung bzw. einen HV verwiesen),
      * eine Meldung, deren Nachricht schon gelöscht ist (**400**, nichts zu
        entfernen).

    Zwei GLEICHZEITIGE Entscheidungen: je Nachricht wird zuerst die
    Nachrichtenzeile gesperrt (``SELECT … FOR UPDATE``), danach greift das
    bedingte UPDATE der Meldung (``WHERE stand = 'offen'``) — trifft es die
    Zeile nicht mehr, hat ein anderer Aufruf sie gewonnen → **409**
    (``KonfliktError``). Beide Aufrufe haben dann nicht beide den Verlauf
    umgeschrieben. Zwei Entscheidungen zu DERSELBEN Nachricht laufen dadurch
    nacheinander statt gleichzeitig (belegt in ``test_chat6_pg``).

    Benachrichtigung: die VERFASSENDE Person bekommt die Glocke über den
    bestehenden Weg (``benachrichtigungen.schreibe_meldung``) — NUR wenn die
    Nachricht durch DIESEN Aufruf entfernt wurde (vorher nicht gelöscht war)
    und ohne den Namen der meldenden Person (2.5: „die Verfasserin bekommt eine
    Glocke“; die Herkunft bleibt bei der Moderation).
    """
    benutzer = _benutzer()
    wahl = str(entscheidung or "").strip()
    if wahl not in MELDUNG_ENTSCHEIDUNGEN:
        throw("Bitte „entfernen“ oder „verwerfen“ wählen.")
    begruendung = str(grund or "").strip() or None
    if wahl == "entfernen" and not begruendung:
        throw("Zum Entfernen einer Nachricht gehört ein Grund.")
    if begruendung and len(begruendung) > MELDUNG_FREITEXT_MAX:
        throw(f"Der Grund darf höchstens {MELDUNG_FREITEXT_MAX} Zeichen lang sein.")
    kennung = str(meldung or "").strip()
    if not kennung:
        throw("meldung fehlt.")
    autor_konto: str | None = None
    nachricht_name = ""
    gespraech_name = ""
    mit_entfernt = False
    jetzt = _jetzt()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        m = s.get(ChatMeldung, kennung)
        if m is None:
            raise DoesNotExistError("Meldung nicht gefunden.")
        nachricht_kennung = m.nachricht
        # SPERR-Reihenfolge (Review Runde 2, A1): ZUERST die Nachrichtenzeile,
        # dann die Meldung. Zwei Entscheidungen zu VERSCHIEDENEN Meldungen
        # derselben Nachricht schreiben beide dieselbe Nachrichtenzeile; ohne
        # feste Reihenfolge nehmen die Transaktionen ihre Sperren in
        # wechselnder Ordnung. Mit der Nachrichtensperre zuerst sind alle
        # Entscheidungen je Nachricht serialisiert: der zweite Aufrufer wartet,
        # sieht danach den neuen Stand und bekommt 400 (Nachricht schon
        # entfernt) bzw. 409 (Meldung schon entschieden).
        # (Einen Deadlock hierfür konnte ich auf PG 17 nicht künstlich
        # erzeugen — belegt ist die Serialisierung, siehe test_chat6_pg.)
        n = s.get(ChatNachricht, nachricht_kennung, with_for_update=True)
        if n is None:
            raise DoesNotExistError("Nachricht nicht gefunden.")
        g = _gespraech_lesen(s, n.gespraech)
        _erlaube(benutzer, rechte.MODERIEREN, gruppe=g.gruppe,
                 untergruppe=g.untergruppe, gespraech=g.name)
        if m.stand != MELDUNG_OFFEN:
            throw("Diese Meldung ist bereits entschieden.", KonfliktError)
        if _ist_meine(n, benutzer):
            throw("Über eine Meldung gegen die eigene Nachricht entscheidet "
                  "eine andere Person der Leitung.")
        if n.geloescht_am is not None:
            throw("Die gemeldete Nachricht ist bereits gelöscht.")
        nachricht_name, gespraech_name = n.name, g.name
        # Bedingtes UPDATE: nur die noch OFFENE Meldung wird entschieden. Der
        # Vergleich steht in der WHERE-Klausel, damit zwei gleichzeitige
        # Aufrufe nicht beide durchkommen (rowcount entscheidet). Die neuen
        # Werte gehen NICHT über das ORM-Objekt, sondern über dieselbe
        # Anweisung — so gibt es keine zweite Wahrheit über den Stand, und ein
        # „rowcount 1“ ist der einzige Beweis, dass DIESER Aufruf gewonnen hat.
        neue_werte: dict[str, Any] = {
            "stand": MELDUNG_ERLEDIGT if wahl == "entfernen" else MELDUNG_VERWORFEN,
            "bearbeitet_von": benutzer or None,
            "bearbeitet_am": jetzt,
            "entscheidung_grund": begruendung,
        }
        getroffen = s.execute(
            update(ChatMeldung)
            .where(ChatMeldung.name == kennung, ChatMeldung.stand == MELDUNG_OFFEN)
            .values(**neue_werte)
        ).rowcount
        if getroffen != 1:
            # Ein paralleler Aufruf war schneller: NICHTS geändert, 409.
            throw("Diese Meldung wurde gerade von jemand anderem entschieden.",
                  KonfliktError)
        if wahl == "entfernen":
            mit_entfernt = n.geloescht_am is None
            if mit_entfernt:
                n.geloescht_am = jetzt
                n.geloescht_von = benutzer
            n.entfernt_grund = begruendung
            autor_konto = str(n.autor_benutzer or "") or None
            # Die übrigen offenen Meldungen derselben Nachricht sind mit der
            # Entfernung erledigt (Stapel-Entscheidung, Review Punkt 5).
            s.execute(
                update(ChatMeldung)
                .where(ChatMeldung.nachricht == n.name,
                       ChatMeldung.stand == MELDUNG_OFFEN,
                       ChatMeldung.name != kennung)
                .values(stand=MELDUNG_ERLEDIGT, bearbeitet_von=benutzer or None,
                        bearbeitet_am=jetzt,
                        entscheidung_grund="Nachricht auf andere Meldung entfernt")
            )
        # Die Meldung im Speicher auf den geschriebenen Stand bringen (das
        # UPDATE ging an der Identity-Map vorbei) — die Antwort zeigt ihn.
        for feld, wert in neue_werte.items():
            setattr(m, feld, wert)
        s.flush()
        antwort = _meldung_zeile(s, m, n, g, benutzer, _melde_namen(s, [(m, n)]))
    if mit_entfernt and autor_konto and autor_konto != benutzer:
        _glocke_entfernt(autor_konto, gespraech_name, nachricht_name, begruendung)
    return antwort


# ── Innen: lesen, prüfen, zählen ────────────────────────────────────────────


def _pruefe_freitext(freitext) -> str | None:
    """Freitext einer Meldung: optional, ≤ 500 ZEICHEN, leer = ``None``."""
    if freitext is None:
        return None
    text = str(freitext)
    if not text.strip():
        return None
    if len(text) > MELDUNG_FREITEXT_MAX:
        throw(f"Der Freitext darf höchstens {MELDUNG_FREITEXT_MAX} Zeichen lang sein "
              f"(eingegeben: {len(text)}).")
    return text


def _vorgeschichte_zeilen(s, nachrichten) -> list[ChatNachricht]:
    """Die Vorgeschichte-Zeilen für MEHRERE Nachrichten — eine Abfrage je Nachricht.

    Eine Meldungsseite zeigt je Meldung den Ausschnitt davor (2.5). Die Namen
    dieser Zeilen werden für die ganze Seite gebraucht (Review Runde 2, N1) —
    deshalb dieselbe Auswahl wie in ``_vorgeschichte``, aber GEBÜNDELT: je
    Zielnachricht eine Abfrage mit ``LIMIT MELDUNG_KONTEXT``, nicht je Zeile
    eine eigene Namensabfrage. Ein ``gespraech`` wird NICHT komplett geladen.
    """
    ziele = [n for n in nachrichten if n is not None]
    ergebnis: list[ChatNachricht] = []
    for n in ziele:
        vorher = s.execute(
            select(ChatNachricht).where(
                ChatNachricht.gespraech == n.gespraech,
                ChatNachricht.name != n.name,
                or_(ChatNachricht.erstellt_am < n.erstellt_am,
                    (ChatNachricht.erstellt_am == n.erstellt_am)
                    & (ChatNachricht.name < n.name)),
            ).order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
            .limit(MELDUNG_KONTEXT)
        ).scalars().all()
        ergebnis.extend(reversed(vorher))
    return ergebnis


def _vorgeschichte(s, n: ChatNachricht, anzahl: int = MELDUNG_KONTEXT,
                   namen: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Die ``anzahl`` Nachrichten VOR ``n`` im selben Gespräch (alt → neu).

    Konzept 2.5: „Mit der Meldung wird der gemeldete Ausschnitt sichtbar —
    genau die eine Nachricht plus die fünf davor“. Gelöschte Nachrichten
    bleiben als Platz stehen (``text=None``), damit die Lücke erkennbar ist.

    ``namen`` (optional) sind die für die GANZE Seite gesammelt geladenen
    Anzeigenamen (``_melde_namen`` — Review Runde 2, N1). Fehlen sie, lädt
    diese Funktion sie selbst: EINMAL für alle Zeilen, nicht je Zeile.
    """
    zeilen = _vorgeschichte_zeilen(s, [n])
    if anzahl != MELDUNG_KONTEXT:
        zeilen = zeilen[-anzahl:]
    if namen is None:
        namen = {
            "autor": _personen(s, {z.autor for z in zeilen if z.autor}),
            "autor_konto": _konto_namen(s, {z.autor_benutzer for z in zeilen if z.autor_benutzer}),
        }
    return [{
        "name": z.name,
        "autor": ((namen["autor"].get(str(z.autor or "")) or z.autor)
                  or namen["autor_konto"].get(str(z.autor_benutzer or ""))),
        "text": None if z.geloescht_am is not None else z.text,
        "geloescht": z.geloescht_am is not None,
        "erstellt_am": _isoopt(z.erstellt_am),
    } for z in zeilen]


def _darf_moderieren(benutzer: str, g: ChatGespraech) -> bool:
    """Darf ``benutzer`` in DIESEM Gespräch moderieren? — über ``_erlaube``.

    EINE Rechtefrage für Liste und Entscheiden (Review Punkt 7): keine eigene
    Rollenlogik, kein zweiter Aufrufpfad. ``_erlaube`` wirft bei Ablehnung; hier
    wird der Wurf zur Antwort ``False``, weil die Liste über VIELE Gespräche
    fragt und das erste „nein“ nicht das Ende ist.
    """
    try:
        _erlaube(benutzer, rechte.MODERIEREN, gruppe=g.gruppe,
                 untergruppe=g.untergruppe, gespraech=g.name)
    except PermissionError:
        return False
    return True


def _melde_namen(s, zeilen) -> dict[str, dict[str, str]]:
    """Alle Anzeigenamen EINER Meldungsseite in vier Abfragen (Review Punkt 8).

    Ohne das lud ``_meldung_zeile`` je Zeile Melder, Bearbeiter und Autor
    einzeln nach (N+1). Gesammelt wird über ALLE Zeilen, gelesen wird nur
    ``mitglied``/``user`` — dieselbe Quelle wie ``_personen``/``_konto_namen``.

    Mitgezählt werden die Autoren der VORGESCHICHTE (Review Runde 2, N1): das
    sind je Zeile bis zu ``MELDUNG_KONTEXT`` Nachrichten, deren Namen früher
    je Zeile eigens nachgeladen wurden. EINE Abfrage über alle Seiten deckt
    Hauptzeile und Vorgeschichte zusammen ab.
    """
    melder, bearbeiter, autoren, autor_konten = set(), set(), set(), set()
    for m, n in zeilen:
        if m.melder:
            melder.add(str(m.melder))
        if m.bearbeitet_von:
            bearbeiter.add(str(m.bearbeitet_von))
        if n.autor:
            autoren.add(str(n.autor))
        if n.autor_benutzer:
            autor_konten.add(str(n.autor_benutzer))
    if zeilen:
        for zeile in _vorgeschichte_zeilen(s, [n for _m, n in zeilen]):
            if zeile.autor:
                autoren.add(str(zeile.autor))
            if zeile.autor_benutzer:
                autor_konten.add(str(zeile.autor_benutzer))
    return {
        "melder": _konto_namen(s, melder),
        "bearbeiter": _konto_namen(s, bearbeiter),
        "autor": _personen(s, autoren),
        "autor_konto": _konto_namen(s, autor_konten),
    }


def _meldung_zeile(s, m: ChatMeldung, n: ChatNachricht, g: ChatGespraech,
                   ich: str, namen: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Eine Meldung als Antwortzeile FÜR DIE MODERATION.

    Enthält als einzige Form den ``melder`` (Anzeige + Konto) und den
    gemeldeten Ausschnitt. Die Nachricht steht im Zustand VOR der Entscheidung
    — nach einem Entfernen bleibt so beurteilbar, was entfernt wurde
    (``text_entfernt`` sagt, dass der Verlauf ihn nicht mehr ausliefert).

    ``text`` steht hier, solange die Nachricht nicht gelöscht ist ODER durch
    die MODERATION entfernt wurde (``entfernt_grund`` gesetzt — Entscheidung
    des Operators in Review Runde 2): nach einem ``entfernen`` soll die
    Moderation sehen, WAS sie entfernt hat. Nur bei einer SELBSTLÖSCHUNG der
    verfassenden Person bleibt der Text aus — dann gibt es nichts zu
    beurteilen, und ihr Text geht auch an die Moderation nicht mehr hinaus. Die
    Namen kommen gesammelt aus ``_melde_namen`` (kein N+1).
    """
    gemeldet_von = str(m.melder or "")
    bearbeiter = str(m.bearbeitet_von or "")
    autor = str(n.autor or "")
    autor_konto = str(n.autor_benutzer or "")
    geloescht = n.geloescht_am is not None
    # Selbstlöschung: gelöscht, aber NICHT von der Moderation entfernt.
    selbst_geloescht = geloescht and not n.entfernt_grund
    return {
        "name": m.name,
        "stand": m.stand,
        "grund": m.grund,
        "freitext": m.freitext,
        "erstellt_am": _isoopt(m.erstellt_am),
        # NUR für die Moderation: ohne die Herkunft ist „wer meldet im
        # Dutzend“ (2.5) nicht beurteilbar. Ein fehlendes Konto (anonymisiert)
        # heißt ``None`` — die Meldung bleibt als Vorgang stehen.
        "melder": namen["melder"].get(gemeldet_von, gemeldet_von) or None,
        "melder_konto": gemeldet_von or None,
        "bearbeitet_von": namen["bearbeiter"].get(bearbeiter, bearbeiter) or None,
        "bearbeitet_am": _isoopt(m.bearbeitet_am),
        "entscheidung_grund": m.entscheidung_grund,
        "gespraech": g.name,
        "gespraech_titel": str(g.titel or "").strip() or (g.untergruppe or g.gruppe),
        "gruppe": g.gruppe,
        "untergruppe": g.untergruppe,
        "nachricht": {
            "name": n.name,
            # Der Text steht hier, solange er für die Moderation beurteilbar
            # ist: eine lebende Nachricht ODER eine von der Moderation
            # entfernte (dann ist er der Beleg, WAS entfernt wurde). Nur eine
            # Selbstlöschung der verfassenden Person blendet ihn aus —
            # ``text_entfernt`` sagt, dass der VERLAUF ihn nicht mehr liefert.
            "text": None if selbst_geloescht else n.text,
            "text_entfernt": geloescht,
            "geloescht_am": _isoopt(n.geloescht_am),
            "entfernt_grund": n.entfernt_grund,
            "autor": (namen["autor"].get(autor) or autor
                      or namen["autor_konto"].get(autor_konto)),
            "erstellt_am": _isoopt(n.erstellt_am),
        },
        # Der Zusammenhang (2.5): genau die fünf davor, alt → neu. Die Namen
        # sind für die GANZE Seite schon geladen (Review Runde 2, N1).
        "vorgeschichte": _vorgeschichte(s, n, namen=namen),
    }


def _glocke_neue_meldung(konten: list[str], meldung: str) -> None:
    """Glocke an die Moderation: „neue Meldung im Chat“ (Konzept 2.5).

    Bestehender Weg (``benachrichtigungen.schreibe_meldung``). Der Text nennt
    weder die meldende Person noch den Inhalt — beides steht nur in der
    Moderationsliste, die wieder über den Rechte-Kern läuft.
    """
    from diakronos_app.benachrichtigungen import schreibe_meldung

    for konto in konten:
        schreibe_meldung(for_user=konto, subject="Neue Meldung im Chat",
                         inhalt="Eine Nachricht im Chat wurde gemeldet und wartet auf eine Entscheidung.",
                         document_type="chat_meldung", document_name=meldung)


# ── CHAT-4a: gebündelte Glocke ──────────────────────────────────────────────


def _glocken_text(titel: str, anzahl: int) -> str:
    """Betreff der gebündelten Glocke: „Chor: 3 neue Nachrichten“.

    NUR Gesprächstitel und Anzahl (Karte: „KEIN Nachrichtentext, KEIN
    Absendername“). Singular bei 1 („1 neue Nachricht“).
    """
    wort = "neue Nachricht" if anzahl == 1 else "neue Nachrichten"
    return f"{titel}: {anzahl} {wort}"


def _glocken_hinweis(anzahl: int) -> str:
    """Inhalt (``email_content``) der Glocke — ohne Text und ohne Absender.

    Die Glocke sagt nur, DASS es Neues gibt und wie viel; wer und was, steht
    ausschließlich im Gespräch, das wieder über den Rechte-Kern läuft.
    """
    wort = "neue Nachricht" if anzahl == 1 else "neue Nachrichten"
    return (f"Im Gespräch {'ist' if anzahl == 1 else 'sind'} {anzahl} {wort} "
            "eingegangen. Öffne den Chat, um sie zu lesen.")


def _glocken_titel(g: ChatGespraech) -> str:
    """Titel der Glocke: der Gesprächstitel, sonst die Einheit."""
    return str(g.titel or "").strip() or (g.untergruppe or g.gruppe)


def glocken_merker(s, gespraech: str, benutzer: str) -> ChatGlocke:
    """Die Merker-Zeile der Person für dieses Gespräch; legt sie beim ersten Mal an.

    Die Ankerfelder bleiben zunächst leer — die Zeile entsteht erst, wenn
    wirklich geglockt wird; sie ist trotzdem sofort da, damit ein zweiter Lauf
    denselben Stand liest.
    """
    zeile = s.get(ChatGlocke, (gespraech, benutzer))
    if zeile is not None:
        return zeile
    zeile = ChatGlocke(gespraech=gespraech, benutzer=benutzer)
    s.add(zeile)
    s.flush()
    return zeile


def _glocke_anker(teilnahme: ChatTeilnehmer | None) -> datetime | None:
    """Ab wann das NÄCHSTE Bündel zählt: der heutige Lesestand dieser Person.

    Ohne Lesestand ist es der Beitritt (``hinzugefuegt_am``) — was vorher
    geschrieben wurde, war für diese Person nie „neu“ (``_ungelesen_zaehlen``
    zählt genauso). Ohne beides: ``None`` = ab allem.
    """
    if teilnahme is None:
        return None
    return teilnahme.letzter_lesestand or teilnahme.hinzugefuegt_am


def _glocke_setzen(s, *, konto: str, gespraech: ChatGespraech,
                   teilnahme: ChatTeilnehmer | None, anzahl: int,
                   jetzt: datetime) -> bool:
    """Die EINE Glocke je (Gespräch, Konto) schreiben — ersetzen statt doppeln.

    Liegt im ``Notification Log`` schon eine UNGELESENE Chat-Glocke desselben
    Gesprächs, wird sie AKTUALISIERT (Betreff, Inhalt). Sonst entsteht eine
    neue Zeile.

    Der Merker wird NUR fortgeschrieben, wenn die Glocke wirklich stand (der
    Rückgabewert von ``glocke_setzen`` ist leer, wenn das Schreiben scheiterte)
    — sonst ginge die Nachricht still verloren, weil der nächste Lauf sie als
    „schon geglockt“ ansähe. ``merker_am`` = die neueste Nachricht, die jetzt
    schon da ist; damit ist dieselbe Nachricht beim nächsten Lauf nicht wieder
    „neu“, auch wenn sie (noch) nicht gelesen wurde.
    """
    from diakronos_app.benachrichtigungen import glocke_setzen

    titel = _glocken_titel(gespraech)
    # ``document_name`` ist das GESPRÄCH: darüber findet ``lesestand_setzen``
    # die Glocke wieder, und darüber verlinkt die Oberfläche.
    name = glocke_setzen(
        for_user=konto,
        subject=_glocken_text(titel, anzahl),
        inhalt=_glocken_hinweis(anzahl),
        document_type=CHAT_GLOCKE_DOCTYPE,
        document_name=gespraech.name,
    )
    if not name:
        return False  # Benachrichtigung ist Beiwerk — aber dann auch kein Merker
    neueste_am = s.execute(
        select(func.max(ChatNachricht.erstellt_am))
        .where(ChatNachricht.gespraech == gespraech.name)
    ).scalar_one_or_none()
    zeile = glocken_merker(s, gespraech.name, konto)
    zeile.stand_am = _glocke_anker(teilnahme)
    zeile.stand_nachricht = teilnahme.letzter_lesestand_nachricht if teilnahme else None
    zeile.stand = zeile.stand_nachricht if (teilnahme and teilnahme.letzter_lesestand) else None
    zeile.merker_am = neueste_am
    zeile.geglockt_am = jetzt
    zeile.gelesen_am = None
    s.flush()
    return True


def _glocke_als_gelesen(s, gespraech: str, benutzer: str,
                        alles_gelesen: bool = True) -> int:
    """Die Glocken dieses Gesprächs für diese Person als gelesen markieren.

    Zwei Dinge: die ``Notification Log``-Zeile(n) auf ``read`` stellen (das ist
    die Glocke in der Oberfläche) und den Merker ``gelesen_am`` setzen. Fehler
    sind Beiwerk — ``lesestand_setzen`` darf daran nicht scheitern.

    ``alles_gelesen=False`` (Reviews R1/d: der Lesestand wurde nur bis zu einer
    ÄLTEREN Nachricht gesetzt, danach ist noch etwas ungelesen): dann bleibt
    die Glocke UNGELESEN stehen, denn es gibt weiter etwas zu sehen — der
    nächste Joblauf schreibt sie mit der richtigen Zahl fort. Der Merker
    bekommt nur den Anker des neuen Lesestands, damit die Zählung ab dort
    stimmt.
    """
    from diakronos_app.benachrichtigungen import glocke_gelesen

    merker = s.get(ChatGlocke, (gespraech, benutzer))
    if not alles_gelesen:
        if merker is not None:
            teilnahme = s.get(ChatTeilnehmer, (gespraech, benutzer))
            merker.stand_am = _glocke_anker(teilnahme)
            merker.stand_nachricht = teilnahme.letzter_lesestand_nachricht if teilnahme else None
            merker.stand = merker.stand_nachricht
            s.flush()
        return 0
    anzahl = glocke_gelesen(for_user=benutzer, document_type=CHAT_GLOCKE_DOCTYPE,
                            document_name=gespraech)
    if merker is not None:
        merker.gelesen_am = _jetzt()
        s.flush()
    return anzahl


def _offen_bedingung(konto: str | None = None):
    """SQL-Bedingung „diese Nachricht ist für die Person ungelesen und zählt“.

    EINE Definition für Kandidaten-Abfrage und Nachprüfung (``_glocke_faellig``),
    damit die beiden nicht auseinanderlaufen: fremde Nachricht
    (``_nicht_von``), nicht gelöscht, nicht vor dem Beitritt, hinter dem
    Lesestand (Zeitstempel + Kennung — zwei Nachrichten können denselben
    Zeitstempel tragen, Sekundengenauigkeit auf PostgreSQL).

    ``konto=None``: die Person ist die des JOINS (``ChatTeilnehmer.benutzer``).
    """
    person = ChatTeilnehmer.benutzer if konto is None else konto
    return [
        ChatNachricht.geloescht_am.is_(None),
        _nicht_von(person),
        ChatTeilnehmer.stumm.is_(False),
        or_(
            ChatTeilnehmer.letzter_lesestand.is_(None),
            or_(ChatNachricht.erstellt_am > ChatTeilnehmer.letzter_lesestand,
                (ChatNachricht.erstellt_am == ChatTeilnehmer.letzter_lesestand)
                & (ChatNachricht.name
                   > func.coalesce(ChatTeilnehmer.letzter_lesestand_nachricht, ""))),
        ),
        or_(ChatTeilnehmer.hinzugefuegt_am.is_(None),
            ChatNachricht.erstellt_am >= ChatTeilnehmer.hinzugefuegt_am),
    ]


def _glocken_kandidaten(s, zeit: datetime, ruhe: int) -> list[tuple[str, str]]:
    """Paare (Gespräch, Konto), für die JETZT eine Glocke fällig sein kann.

    Die Arbeit passiert in SQL, nicht je Gespräch in Python (Review R1, MUSS 2:
    der Job lief sonst jede Minute durch JEDES Gespräch und lud den Verlauf):

    1. ``neu`` — je (Gespräch, Person) die NEUESTE fremde, nicht gelöschte
       Nachricht NACH dem Anker des Merkers (Lesestand beim letzten Glocken
       bzw. Beitritt) und nach dessen ``merker_am``. Eine Person ohne
       Merker-Zeile hat keinen Merker-Beitrag — der LEFT JOIN unten setzt
       diesen Teil der Bedingung dann auf „wahr“ (die Person hat noch nie
       eine Glocke bekommen, also ist alles seit ihrem Lesestand neu).
    2. **Ruhe**: die neueste Nachricht des GESPRÄCHS ist älter als ``ruhe``
       Minuten — nur dann wird gebündelt.
    3. **stumm** wird hier schon verworfen (der Zähler bleibt davon unberührt).
    4. **schon gelesen**: liegt der Lesestand auf oder hinter der neuesten
       Nachricht, gibt es nichts zu glocken — das erledigt SQL, nicht Python,
       und es ist der Grund, warum der zweite Lauf ohne neue Nachricht nichts
       mehr zu tun hat.

    Gelöschte Gespräche und Nachrichten zählen nicht. Ob die Person das
    Gespräch noch lesen DARF, entscheidet danach ``_darf_lesen``
    (``rechte.darf``) — hier steht KEINE Rechtelogik.
    """
    grenze = zeit - timedelta(minutes=ruhe)
    neueste = (
        select(ChatNachricht.gespraech.label("gespraech"),
               func.max(ChatNachricht.erstellt_am).label("letzte"))
        .where(ChatNachricht.geloescht_am.is_(None))
        .group_by(ChatNachricht.gespraech)
        .subquery()
    )
    # Die neueste FREMDE, lebende Nachricht je (Gespräch, Person).
    je_person = (
        select(ChatNachricht.gespraech.label("gespraech"),
               ChatTeilnehmer.benutzer.label("benutzer"),
               func.max(ChatNachricht.erstellt_am).label("neu_am"))
        .join(ChatTeilnehmer, ChatTeilnehmer.gespraech == ChatNachricht.gespraech)
        .where(*_offen_bedingung())
        .group_by(ChatNachricht.gespraech, ChatTeilnehmer.benutzer)
        .subquery()
    )
    abfrage = (
        select(je_person.c.gespraech, je_person.c.benutzer)
        .join(neueste, neueste.c.gespraech == je_person.c.gespraech)
        .outerjoin(
            ChatGlocke,
            (ChatGlocke.gespraech == je_person.c.gespraech)
            & (ChatGlocke.benutzer == je_person.c.benutzer),
        )
        .join(ChatGespraech, ChatGespraech.name == je_person.c.gespraech)
        .where(
            neueste.c.letzte <= grenze,
            ChatGespraech.geloescht_am.is_(None),
            or_(ChatGlocke.merker_am.is_(None),
                je_person.c.neu_am > ChatGlocke.merker_am),
        )
        .order_by(je_person.c.gespraech, je_person.c.benutzer)
    )
    return [(str(g), str(k)) for g, k in s.execute(abfrage).all() if g and k]


def _glocke_faellig(s, gespraech: ChatGespraech, konto: str) -> bool:
    """Ist für dies eine Paar noch etwas offen? — die EINE Frage, in SQL.

    Zweite Verteidigung gegen Doppel-Glocken und der Grund, warum ein zweiter
    Lauf ohne neue Nachricht nichts tut: ``merker_am`` steht auf der neuesten
    Nachricht, und der Lesestand der Person liegt hinter der neuesten fremden
    Nachricht.
    """
    anker = (
        select(ChatGlocke.merker_am)
        .where(ChatGlocke.gespraech == gespraech.name,
               ChatGlocke.benutzer == konto)
        .scalar_subquery()
    )
    return bool(s.execute(
        select(ChatNachricht.name)
        .join(ChatTeilnehmer, ChatTeilnehmer.gespraech == ChatNachricht.gespraech)
        .where(
            ChatNachricht.gespraech == gespraech.name,
            ChatTeilnehmer.benutzer == konto,
            *_offen_bedingung(konto),
            or_(anker.is_(None), ChatNachricht.erstellt_am > anker),
        ).limit(1)
    ).first())


def _lauf_sperren(s) -> bool:
    """Sitzungssperre für DIESEN Joblauf — ``False`` = ein anderer läuft schon.

    Zwei Scheduler-Prozesse (App + Scheduler, oder ein Neustart während eines
    Laufs) dürfen nicht dieselbe Glocke schreiben. Auf PostgreSQL nimmt der
    Lauf eine Sitzungssperre mit fester Kennung (``pg_try_advisory_xact_lock``,
    endet mit der Transaktion); SQLite (Tests, Einzelplatz) kennt sie nicht und
    braucht sie nicht — dort gibt es nur einen Schreiber.
    """
    if s.get_bind().dialect.name != "postgresql":
        return True
    return bool(s.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": GLOCKE_SPERRE}
    ).scalar())


def chat_glocken_buendeln(jetzt: datetime | None = None, ruhe: int | None = None) -> int:
    """Scheduler-Job: EINE gebündelte Glocke je Gespräch und Person.

    Läuft alle 1–2 Minuten (``scheduler.build_scheduler``) und glockt NUR
    Gespräche, deren neueste Nachricht mindestens ``ruhe`` Minuten alt ist
    (Default ``GLOCKE_RUHE_MINUTEN`` = 5). Je (Gespräch, Person) genau EINE
    Glocke: der Merker ``chat_glocke`` verhindert den zweiten Glockenschlag
    für dieselbe Nachricht, eine noch ungelesene Glocke desselben Gesprächs
    wird AKTUALISIERT statt verdoppelt.

    Die ZAHL ist der Ungelesen-Zähler der Person (``_ungelesen_zaehlen``: seit
    ihrem Lesestand, ohne eigene und gelöschte, ab dem Beitritt) — „N neue
    Nachrichten“ heißt also genau das, was die Seitenleiste auch zählt.

    Keine Glocke für:
      * die verfassende Person (eigene Nachrichten),
      * stumm geschaltete Personen (der Zähler bleibt — hier wird nichts am
        Lesestand geändert),
      * wer das Gespräch seitdem gelesen hat,
      * wer das Gespräch nicht mehr lesen darf (``rechte.darf``; bei
        ausgeschaltetem Modul gibt der Kern kein Lesen),
      * gelöschte Gespräche.

    ``jetzt`` ist injizierbar (Tests, kein ``sleep``); ``ruhe`` ebenso.

    Rückgabe: Zahl der geschriebenen/aktualisierten Glocken.
    """
    from diakronos_app import db as _db

    zeit = jetzt or _jetzt()
    minuten = GLOCKE_RUHE_MINUTEN if ruhe is None else int(ruhe)
    geschrieben = 0
    # ``begin()`` je Joblauf: der Job läuft im Scheduler-Prozess, nicht im
    # Request — die Sitzung wird hier geöffnet und wieder geschlossen.
    with _db.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        from diakronos_app.rechte import merkungsrahmen

        if not _lauf_sperren(s):
            logger.info("chat_glocken_buendeln: anderer Lauf aktiv, übersprungen")
            return 0
        with merkungsrahmen():
            for gespraech_name, konto in _glocken_kandidaten(s, zeit, minuten):
                # Ein Fehler bei EINEM Paar darf den Rest des Laufs nicht
                # kippen: eigener Savepoint, Fehler protokollieren, weiter.
                try:
                    with s.begin_nested():
                        g = s.get(ChatGespraech, gespraech_name)
                        if g is None or g.geloescht_am is not None:
                            continue
                        if not _darf_lesen(s, konto, gespraech_name):
                            continue  # Rechte-Kern: keine Glocke an ehemalige Mitglieder
                        if not _glocke_faellig(s, g, konto):
                            continue  # nichts Neues seit der letzten Glocke
                        teilnahme = s.get(ChatTeilnehmer, (gespraech_name, konto))
                        anzahl = _ungelesen_zaehlen(s, gespraech_name, konto, teilnahme)
                        if anzahl <= 0:
                            continue  # alles gelesen (oder nur eigene Nachrichten)
                        if _glocke_setzen(s, konto=konto, gespraech=g,
                                          teilnahme=teilnahme, anzahl=anzahl,
                                          jetzt=zeit):
                            geschrieben += 1
                except Exception:  # noqa: BLE001 — ein Paar, nicht der Lauf
                    logger.exception("chat_glocken_buendeln: %s/%s fehlgeschlagen",
                                     gespraech_name, konto)
    return geschrieben


def _glocke_entfernt(konto: str, gespraech: str, nachricht: str, grund: str | None) -> None:
    """Glocke an die VERFASSENDE Person: „von der Moderation entfernt“.

    Der BESTEHENDE Weg (``benachrichtigungen.schreibe_meldung``), nichts Neues
    gebaut. Ohne Gesprächstitel-Rat: der Titel ist die Kennung des Gesprächs
    nicht wert — die Oberfläche verlinkt über ``document_type``/``document_name``.
    Der Text enthält NIE den Namen der meldenden Person (Konzept 2.5/4.5).
    """
    from diakronos_app.benachrichtigungen import schreibe_meldung

    inhalt = "Eine deiner Nachrichten wurde von der Moderation entfernt."
    if grund:
        inhalt += f"\nGrund: {grund}"
    schreibe_meldung(for_user=konto, subject="Nachricht von der Moderation entfernt",
                     inhalt=inhalt, document_type="chat_nachricht",
                     document_name=nachricht)


def _einheit(s, gruppe, untergruppe) -> tuple[str, str | None]:
    """``(Hauptgruppe, Untergruppe)`` aus den Parametern — OHNE Rateweg.

    Review CHAT-2, Punkt 1: die Hauptgruppe einer Untergruppe ist IMMER
    ``untergruppe.gruppe``. Eine mitgegebene, ABWEICHENDE ``gruppe`` wird
    abgewiesen (403 ohne Inhalt): sonst umginge ``gespraech(gruppe=A,
    untergruppe=U)`` den Modulschalter von B (der Kern prueft ``modul_aktiv``
    in der Hauptgruppe) und legte ein Gespraech unter falscher Gruppe an.
    Gleiche Hauptgruppe oder keine Angabe: es gilt die aus der Untergruppe.

    Unbekannte Untergruppe → 403 ohne Inhalt (nicht 404: das verriete, dass es
    die Kennung nicht gibt).
    """
    from diakronos_app.models.diakonos import Untergruppe

    g = str(gruppe or "").strip()
    u = str(untergruppe or "").strip() or None
    if not g and not u:
        throw("gruppe fehlt.")
    if not u:
        return g, None
    haupt = s.execute(
        select(Untergruppe.gruppe).where(Untergruppe.name == u)
    ).scalar_one_or_none()
    haupt = str(haupt or "").strip()
    if not haupt:
        _h()
    if g and g != haupt:
        _h()
    return haupt, u


def _erlaube(benutzer: str, aktion: str, *, gruppe: str | None,
             untergruppe: str | None = None, besitzer: str | None = None,
             gespraech: str | None = None) -> None:
    """DIE Rechtefrage — ``rechte.darf``, nichts Eigenes (Kartenauflage).

    ``besitzer`` wird in der Form des Kerns uebergeben: eine KONTO-Kennung
    (``user.name``), verglichen gegen ``benutzer`` (``_darf_chat``:
    ``besitzer is None or besitzer == benutzer``). Deshalb traegt
    ``chat_nachricht.autor_benutzer`` den Besitz — die Mitglied-Kennung in
    ``autor`` waere nie gleich dem Konto, und der Kern saehe jede eigene
    Nachricht als fremd an.
    """
    entscheidung = rechte.darf(
        benutzer, aktion, "chat_gespraech", gespraech,
        gruppe=gruppe, untergruppe=untergruppe, besitzer=besitzer,
    )
    if not entscheidung:
        _h()


def _ist_meine(n: ChatNachricht, benutzer: str) -> bool:
    """Gehoert die Nachricht DIESER Person? — verglichen wird das KONTO."""
    return bool(n.autor_benutzer) and str(n.autor_benutzer) == str(benutzer or "")


def _gespraech_lesen(s, gespraech: str) -> ChatGespraech:
    """Gespräch per Kennung; unbekannt → 404 (nichts über seine Existenz raten)."""
    if not gespraech:
        throw("gespraech fehlt.")
    zeile = s.get(ChatGespraech, gespraech)
    if zeile is None or zeile.geloescht_am is not None:
        raise DoesNotExistError("Gespräch nicht gefunden.")
    return zeile


def _nachricht(s, nachricht: str, gespraech: str | None) -> ChatNachricht:
    """Nachricht per Kennung; ``gespraech`` grenzt sie auf EIN Gespräch ein.

    Die Eingrenzung ist die Zusage aus der Karte: „Antwort auf genau eine
    Nachricht“ — und zwar aus DEMSELBEN Verlauf. Ohne sie könnte man eine
    Nachricht aus einem fremden Gespräch zitieren oder daran reagieren.
    """
    if not nachricht:
        throw("nachricht fehlt.")
    zeile = s.get(ChatNachricht, nachricht)
    if zeile is None or (gespraech is not None and zeile.gespraech != gespraech):
        raise DoesNotExistError("Nachricht nicht gefunden.")
    return zeile


def _pruefe_text(text) -> str:
    """Text einer Nachricht: nicht leer am Rand, ≤ 4000 ZEICHEN, Absätze bleiben.

    Getrimmt wird nur, um „leer“ zu erkennen — gespeichert wird der Text
    unverändert (Einrückungen, Zeilenumbrüche und Leerzeilen sind Inhalt).
    """
    if text is None:
        throw("Bitte einen Text eingeben.")
    inhalt = str(text)
    if not inhalt.strip():
        throw("Bitte einen Text eingeben.")
    if len(inhalt) > NACHRICHT_MAX:
        throw(f"Eine Nachricht darf höchstens {NACHRICHT_MAX} Zeichen lang sein "
              f"(eingegeben: {len(inhalt)}).")
    return inhalt


def _wahr(wert) -> bool:
    """Wahrheitswert aus JSON/Formular (``true``/``1``/``ja``)."""
    if isinstance(wert, bool):
        return wert
    if wert is None or wert == "":
        return True
    text = str(wert).strip().casefold()
    if text in ("false", "0", "nein", "no", "aus"):
        return False
    if text in ("true", "1", "ja", "yes", "an"):
        return True
    throw("Bitte true oder false angeben.")


def _ungelesen(s, gespraech: str, benutzer: str) -> int:
    """Ungelesen-Zähler eines Gesprächs (gleiche Regel wie ``meine_gespraeche``)."""
    teilnahme = s.get(ChatTeilnehmer, (gespraech, benutzer))
    return _ungelesen_zaehlen(s, gespraech, benutzer, teilnahme)


def _ungelesen_zaehlen(s, gespraech: str, benutzer: str,
                       teilnahme: ChatTeilnehmer | None) -> int:
    """Fremde, nicht gelöschte Nachrichten nach dem eigenen Lesestand.

    ``_nicht_von`` vergleicht das KONTO (``autor_benutzer``) — eine Nachricht
    ohne Konto (anonymisiert) gilt als fremd. Ohne Teilnahme/ohne Lesestand
    zählt ALLES seit dem Beitritt (``hinzugefuegt_am``; ohne Datum: alles).
    """
    bedingung = [ChatNachricht.gespraech == gespraech,
                 ChatNachricht.geloescht_am.is_(None),
                 _nicht_von(benutzer)]
    if teilnahme is not None and teilnahme.letzter_lesestand is not None:
        stand = teilnahme.letzter_lesestand
        bedingung.append(or_(
            ChatNachricht.erstellt_am > stand,
            (ChatNachricht.erstellt_am == stand)
            & (ChatNachricht.name > str(teilnahme.letzter_lesestand_nachricht or "")),
        ))
    elif teilnahme is not None and teilnahme.hinzugefuegt_am is not None:
        bedingung.append(ChatNachricht.erstellt_am >= teilnahme.hinzugefuegt_am)
    return int(s.execute(select(func.count()).select_from(ChatNachricht)
                         .where(*bedingung)).scalar_one())


def _teilnahme_konten(s, gespraech: str) -> list[str]:
    """Konten mit Teilnahmezeile in diesem Gespraech (nur Kennungen)."""
    return [str(k) for k in s.execute(
        select(ChatTeilnehmer.benutzer).where(ChatTeilnehmer.gespraech == gespraech)
    ).scalars().all() if k]


def _lesbare_gespraeche(s, benutzer: str) -> list[ChatGespraech]:
    """Die Gespraeche, die ``benutzer`` LESEN darf — aus SEINEN Mitgliedschaften.

    Review Punkt 5: NICHT alle Gespraeche des Systems laden und je
    ``darf`` fragen, sondern zwei Abfragen (Gruppen, Untergruppen) auf den
    Mitgliedschaften des Benutzers aufsetzen. Je Kandidat entscheidet danach
    ``rechte.darf`` (Mitgliedschaft + Modul ``chat``) — keine eigene
    Rollenlogik. Ein Gespraech, das es (noch) nicht gibt, wird hier NICHT
    angelegt; es erscheint mit ``geoeffnet: false`` und ``name=None``.
    """
    from diakronos_app.models.diakonos import (
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )

    einheiten: list[tuple[str, str | None]] = []
    mitglied = _meine_kennung()
    if mitglied:
        einheiten += [(str(g), None) for g in s.execute(
            select(Gruppenmitgliedschaft.parent)
            .where(Gruppenmitgliedschaft.mitglied == mitglied)).scalars().all() if g]
        einheiten += [("", str(u)) for u in s.execute(
            select(Untergruppenmitgliedschaft.parent)
            .where(Untergruppenmitgliedschaft.mitglied == mitglied)).scalars().all() if u]
    # Rollen OHNE Mitgliedsdatensatz (HV/MV/GL ueber RechteGruppenrolle,
    # Administrator) — dieselbe Quelle, aus der `rechte.darf` die Rolle liest.
    from diakronos_app.models.rechte import RechteGruppenrolle
    for gruppe, untergruppe in s.execute(
        select(RechteGruppenrolle.gruppe, RechteGruppenrolle.untergruppe)
        .where(RechteGruppenrolle.benutzer == benutzer)
    ).all():
        einheiten.append((str(gruppe or ""), str(untergruppe or "") or None))

    # Review 18.11.: Hauptgruppe einer Untergruppen-Mitgliedschaft ergaenzen
    # (Untergruppenmitglieder lesen den Gruppenchat) und zu jeder Hauptgruppe
    # ihre Untergruppen (HV/MV lesen sie geerbt). Ob wirklich gelesen werden
    # darf, entscheidet unten weiter allein `rechte.darf`.
    normiert: list[tuple[str, str | None]] = []
    for gruppe, untergruppe in einheiten:
        if untergruppe:
            haupt = s.execute(select(Untergruppe.gruppe).where(
                Untergruppe.name == untergruppe)).scalar_one_or_none()
            gruppe = str(haupt or "").strip()
            normiert += [(gruppe, untergruppe), (gruppe, None)]
        else:
            normiert.append((gruppe, None))
    hauptgruppen = sorted({g for g, u in normiert if g and u is None})
    if hauptgruppen:
        normiert += [(str(g), str(u)) for u, g in s.execute(
            select(Untergruppe.name, Untergruppe.gruppe)
            .where(Untergruppe.gruppe.in_(hauptgruppen))).all() if u and g]

    gesehen: set[tuple[str, str | None]] = set()
    ergebnis: list[ChatGespraech] = []
    for gruppe, untergruppe in normiert:
        if not gruppe or (gruppe, untergruppe) in gesehen:
            continue
        gesehen.add((gruppe, untergruppe))
        if not rechte.modul_aktiv(gruppe, "chat"):
            continue  # Modul aus = kein Eintrag (und kein Rechte-Aufruf je Zeile)
        art = ART_UNTERGRUPPE if untergruppe else ART_GRUPPE
        zeile = _gespraech_suchen(s, art, gruppe, untergruppe)
        if not rechte.darf(benutzer, rechte.LESEN, "chat_gespraech",
                           zeile.name if zeile else None,
                           gruppe=gruppe, untergruppe=untergruppe):
            continue
        ergebnis.append(zeile if zeile is not None else ChatGespraech(
            name=None, art=art, gruppe=gruppe, untergruppe=untergruppe))
    return ergebnis


def _gespraech_kopf(s, g: ChatGespraech, benutzer: str) -> dict[str, Any]:
    """Ein Eintrag der Gespraechsliste — auch fuer ein noch nie geoeffnetes."""
    teilnahme = s.get(ChatTeilnehmer, (g.name, benutzer)) if g.name else None
    if g.name:
        ungelesen = _ungelesen_zaehlen(s, g.name, benutzer, teilnahme)
        letzte = s.execute(select(ChatNachricht)
                           .where(ChatNachricht.gespraech == g.name)
                           .order_by(ChatNachricht.erstellt_am.desc(),
                                     ChatNachricht.name.desc())
                           .limit(1)).scalar_one_or_none()
    else:
        ungelesen, letzte = 0, None
    titel = str(g.titel or "").strip() or (g.untergruppe or g.gruppe)
    return {
        "name": g.name,
        "art": g.art,
        "gruppe": g.gruppe,
        "untergruppe": g.untergruppe,
        "titel": titel,
        "teilnehmer": _teilnehmer_aktuelle(s, g),
        "stumm": bool(teilnahme.stumm) if teilnahme is not None else False,
        # `geoeffnet: false` heisst: es gibt noch keine Gespraechszeile. Die
        # Oberflaeche holt sie beim Tipp auf den Eintrag ueber `gespraech(...)`.
        "geoeffnet": bool(g.name),
        "ungelesen": ungelesen,
        "letzte_nachricht": _zitat(s, letzte) if letzte else None,
        "letzte_am": _isoopt(letzte.erstellt_am) if letzte else None,
    }


def _teilnehmer_aktuelle(s, g: ChatGespraech) -> int:
    """Wie viele AKTUELLE Angehoerige hat die Einheit? (nicht: Teilnahmezeilen)

    Review Punkt 3: eine stehengebliebene Teilnahmezeile eines ausgetretenen
    Mitglieds ist kein Teilnehmer mehr. Gezaehlt wird daher ueber den
    Rechte-Kern (``darf`` LESEN je Konto) — und nur unter den Konten, die eine
    Teilnahmezeile haben. Neu hinzugekommene Mitglieder ohne Teilnahmezeile
    zaehlen NICHT mit: die Zahl beschreibt das Gespraech, nicht die Einheit.
    """
    if not g.name:
        return 0
    return sum(1 for konto in _teilnahme_konten(s, g.name)
               if _darf_lesen(s, konto, g.name))


__all__ = [
    "CHAT_GLOCKE_DOCTYPE",
    "FRAPPE_MODULE",
    "GLOCKE_SPERRE",
    "MELDUNGEN_MAX",
    "MELDUNG_KONTEXT",
    "SEITE",
    "SEITE_MAX",
    "TITEL_MAX",
    "aendern",
    "chat_glocken_buendeln",
    "gespraech_anlegen",
    "glocken_merker",
    "lesestand_setzen",
    "loeschen",
    "meldung_entscheiden",
    "meldung_senden",
    "meldungen_liste",
    "meine_gespraeche",
    "reaktion_setzen",
    "senden",
    "stumm_setzen",
    "verlauf",
]
