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

CHAT-7a — DIREKTNACHRICHTEN 1:1 (``direkt_oeffnen``)
--------------------------------------------------
Ein Direktgespräch ist KEINE neue Tabellenfamilie: eine Zeile in
``chat_gespraech`` mit ``art = "direkt"``, ``gruppe = NULL`` und zwei Zeilen in
``chat_teilnehmer``. Verlauf, Senden, Bearbeiten, Löschen, Reaktion, Lesestand,
Stumm, Umfragen und Meldungen funktionieren deshalb OHNE Sonderfall — sie
laufen über dieselben Endpunkte.

RECHTE: EINE WEICHE, KEINE ZWEITE REGEL
``_erlaube(benutzer, aktion, g=<Zeile>, besitzer=…, sitzung=<Sitzung>)``
entscheidet je ``art``:

* Gruppe/Untergruppe → ``rechte.darf`` (unverändert seit CHAT-2),
* ``direkt`` → ``rechte.darf_direktgespraech(benutzer, aktion,
  teilnehmer=<Konten>, besitzer=…)`` — der Raum sind die Teilnehmenden.

ALLE Endpunkte gehen durch diese Weiche, auch der Meldeweg
(``meldungen_liste``, ``meldung_entscheiden``, ``_darf_moderieren``,
``_darf_lesen``, ``_gespraech_kennungen_mit``) — es gibt in diesem Modul
KEINEN direkten ``rechte.ist_meldestelle``/``darf_direktgespraech``-Aufruf
mehr. Die Teilnahme prüft der KERN; die Weiche liest nur die Konten (in der
Sitzung des Aufrufers, wenn er eine hat).

Anlegen eines Gesprächs fragt ``rechte.darf_direktnachricht`` (der Kern);
Status-, Rollen- und Kontofragen stehen NIRGENDS in diesem Modul.

Moderation im 1:1 gibt es AUSSCHLIESSLICH über ``meldung_entscheiden``; eine
fremde Nachricht löschen oder eine fremde Umfrage schließen ist dort
``SCHREIBEN`` mit ``besitzer`` → 403, auch für einen teilnehmenden Admin.

EIN Gespräch je Personenpaar (Konzept 10.1 Punkt 4) sichern die Datenbank
(``paar_schluessel`` + ``uq_chat_gespraech_paar``) und ``_direkt_holen``
(``IntegrityError`` im Savepoint abgefangen, wie beim Lazy-Anlegen): zwei
gleichzeitige Aufrufe — auch in vertauschter Reihenfolge — ergeben EINE Zeile.

Lesen: NUR die Teilnehmenden. Der Administrator ist KEIN stiller Mitleser
(F7): er bekommt ausschließlich die GEMELDETE Nachricht samt Kontext, über den
bestehenden Meldeweg (``meldung_senden`` → Glocke an die Meldestelle,
``meldungen_liste``/``meldung_entscheiden`` über die Weiche mit
``MODERIEREN``).

Die Glocke eines 1:1 trägt den NEUTRALEN Betreff „Direktnachricht: …“: der
Gesprächstitel eines 1:1 ist der Name des Gegenübers, und ein Absendername
gehört nicht in die Glocke (CHAT-4a).

CHAT-7b — RUNDEN (3–8) UND BLOCKIEREN (Konzept S3, Zeilen ~100–122)
-------------------------------------------------------------------
**Runde** = ``art = 'runde'``, ``gruppe = NULL``, ``titel`` = Name der Runde,
3–8 Zeilen in ``chat_teilnehmer``. Verlauf, Senden, Bearbeiten, Löschen,
Reaktion, Lesestand, Stumm, Umfragen und Meldungen laufen über DIESELBEN
Endpunkte — die Weiche (``_erlaube``) fragt je ``art`` und reicht für
``direkt`` UND ``runde`` die Teilnehmenden an den Kern
(``darf_direktgespraech``). Anlegen fragt ``darf_runde_anlegen``, Erweitern
``darf_runde_erweitern`` — nichts Eigenes.

**Vorschlag → Zustimmung** (``runde_vorschlagen``/``runde_zustimmen``/
``runde_ablehnen``): hinzugefügt wird erst, wenn ALLE bisherigen
Teilnehmenden außer der vorschlagenden Person zugestimmt haben; JEDE
Ablehnung beendet den Vorschlag. Der Verlauf zeigt EINE Systemnachricht
„X möchte Y hinzufügen“ ohne weitere Daten; gezählt werden Zahlen, keine
Namen (``chat_runde_vorschlag.zustimmungen``).

**Verlassen** (``runde_verlassen``): ``chat_teilnehmer.verlassen_am`` wird
gesetzt, die Zeile bleibt. Wer gegangen ist, liest nicht mehr, sendet nicht
mehr und schlägt niemanden mehr vor — und die anderen sehen ihn weiter als
benannte Person, NICHT als „Gelöschte Person“ (das ist die Löschung, Art. 17).

**Blockieren** (``kontakt_sperren``/``kontakt_entsperren``/
``meine_sperren``): die Sperre wirkt schon im Kern
(``darf_direktnachricht`` → NEIN „gesperrt“, beide Richtungen) — dieser
Endpunkt schreibt nur die Zeile. Nach außen ist „gesperrt“ NICHT von „nicht
erreichbar“ zu unterscheiden: gleicher Text, gleicher Status (403 ohne
Inhalt), in jedem Endpunkt dieses Moduls. ``personen_suchen`` liefert nur
``darf_schreiben: false``, sonst nichts Auffälliges.

WAS HIER BEWUSST FEHLT (spätere Karten): Push (CHAT-10), Anhänge und
Chatverlaufssuche (CHAT-9b/c). Kein WebSocket: Zustellung ist der „seit X“-Abruf
(3.1, Empfehlung A).

CHAT-9a — ERWÄHNUNGEN (@Name, Konzept S4)
-----------------------------------------
Der Client schickt die Erwähnten AUSDRÜCKLICH mit:
``senden(gespraech, text, antwort_auf=None, erwaehnt=[…])``. Der Server parst
KEIN „@…“ aus dem Text. ``erwaehnt`` sind MITGLIED-Kennungen (wie sie die
Gesprächs-/Personen-APIs liefern). Die Obergrenze (20) wird VOR der Prüfung
gezogen (Client-Reihenfolge). Je Kennung prüft ``_erwaehnungen_pruefen``:
Beteiligte/r des Gesprächs, die/der die Nachricht lesen darf (dieselbe Weiche
wie beim Lesen — ``_darf_lesen``/``rechte.darf``, bei Runden zusätzlich
``verlassen_am``/``sichtbar_ab``) und nicht die sendende Person selbst.
UNGÜLTIGE Kennungen werden STILL verworfen — kein Fehler, keine Auskunft
darüber, ob es die Person gibt.

Eine Kontaktsperre (CHAT-7b) ist KEIN Verwerf-Grund, sondern eine
Glocken-Frage: die Erwähnung wird gespeichert (die Antwort an die sendende
Person ist mit und ohne Sperre gleich — sonst wäre die Sperre erkennbar), die
Glocke unterbleibt (``_erwaehnungen_gesperrt``).

Gespeichert wird je Paar EINE Zeile in ``chat_erwaehnung`` (neu, Migration
``chat9a_erwaehnung``). Je gespeicherter Erwähnung entsteht eine EIGENE Glocke
(``document_type = 'chat_erwaehnung'``, ``document_name`` = Nachricht) — NICHT
gebündelt mit dem Gesprächs-Zähler und auch bei stumm geschaltetem Gespräch
(bewusste Entscheidung, wie gängige Messenger). Der Text folgt den
Datenschutz-Regeln der Chat-Glocken: kein Nachrichteninhalt, kein
Absendername. Beim Lesen bis über die Nachricht hinaus markiert
``lesestand_setzen`` sie in EINEM ``UPDATE`` als gelesen. Löschen/Entfernen
räumt die Zeilen ab und stellt die Glocke auf gelesen (kein Weg auf eine
Lücke); die Frist (CHAT-8) löscht die Zeilen mit dem Gespräch und räumt die
verwaisten Glocken ab. Bearbeiten lässt Erwähnungen und Glocken unverändert.
Die Nachrichten-Antworten tragen ``erwaehnt: [{mitglied, anzeigename}]`` —
gefiltert über ``rechte.darf_person_finden`` (Kapitel 2.4): wer für die
lesende Person nicht auffindbar ist, fehlt in der Liste (der Text enthält das
„@Name“ ohnehin).

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
  aber nur, wenn danach nichts ungelesen bleibt. Bleibt ein Rest offen, wird
  die Glocke SOFORT mit der neuen Zahl fortgeschrieben (CHAT-4b, Restpunkt b:
  ``merker_am`` hätte weitere Läufe blockiert, die Zahl wäre stehen geblieben).
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

CHAT-4b — UMFRAGE-GLOCKEN (Konzept S2: „eine Glocke beim Start (‚Neue Umfrage
im Chor'), eine Erinnerung 24 h vor Frist an die, die noch nicht abgestimmt
haben“)
-------------------------------------------------------------------------------
* **Start** (``_glocke_neue_umfrage``, aus ``umfrage_anlegen`` nach dem
  Commit): „Neue Umfrage im <Titel>“ an alle, die das Gespräch lesen dürfen —
  außer der/dem Anlegenden und den stumm geschalteten. Ohne Frage, ohne
  Optionen, ohne Namen. Empfänger über ``chat_teilnehmer`` (EINE SQL-Abfrage,
  ``stumm`` kommt mit), dann ``rechte.darf`` je Kandidat: wer das Gespräch nie
  geöffnet hat, bekommt nichts (dieselbe Regel wie CHAT-4a). Der/die
  Anlegende reicht die UMFRAGE durch (Review R1/2) — nicht „die neueste des
  Gesprächs“.
* **Erinnerung** (``chat_umfrage_erinnerungen``, Minuten-Job hinter
  ``chat_glocken_buendeln``, KEIN HTTP-Endpunkt — Review R1/1): schließt
  zuerst fällige Umfragen, dann „Umfrage im <Titel> endet morgen“ an alle
  Berechtigten, die NOCH NICHT abgestimmt haben (offen: keine
  ``chat_stimme``-Zeile; anonym: keine ``chat_umfrage_abgabe``-Marke). Merker
  ``chat_umfrage.erinnert_am`` ⇒ genau einmal; er wird nur gesetzt, wenn
  wirklich geschrieben wurde oder es niemanden zu erinnern gab. Geschlossene,
  gelöschte und fristlose Umfragen nie; wurde die Umfrage weniger als 24 h vor
  ihrer Frist angelegt, genügt die Start-Glocke. Die Erinnerung verrät nur der
  Person selbst „du hast noch nicht abgestimmt“ — keine Liste an Dritte.
* Beide Glocken laufen je (Umfrage, Konto) auf EINER ``Notification Log``-Zeile
  (``document_type = chat_umfrage``, ``document_name`` = Umfrage) und werden
  fortgeschrieben statt verdoppelt. Ihre Zeitstempel sind UTC wie bei
  ``_create`` (Review R1/3), und CHAT-8 räumt sie mit dem Gespräch ab
  (``chat_aufbewahrung.GLOCKE_DOKUMENTTYPEN``, Review R1/5).
"""

from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime, timedelta
from typing import Any, NoReturn

from sqlalchemy import (Integer, and_, case, cast, delete, func, or_, select,
                        text, update)
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
    ART_DIREKT,
    ART_GRUPPE,
    ART_RUNDE,
    ART_UNTERGRUPPE,
    BEARBEITEN_MINUTEN,
    ERWAEHNUNGEN_MAX,
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
    RUNDE_TITEL_MAX,
    VORSCHLAG_ABGELEHNT,
    VORSCHLAG_ANGENOMMEN,
    VORSCHLAG_BEENDET,
    VORSCHLAG_OFFEN,
    ChatGespraech,
    ChatGlocke,
    ChatErwaehnung,
    ChatMeldung,
    ChatNachricht,
    ChatReaktion,
    ChatRundeVorschlag,
    ChatStimme,
    ChatTeilnehmer,
    ChatUmfrage,
    ChatUmfrageAbgabe,
    ChatUmfrageOption,
)
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.rechte import RechteKontaktsperre

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
#: CHAT-9c-2: Trefferzahl der Erwähnungs-Suche (``gespraech_mitglieder``).
#: Größere Wünsche werden gekappt: die Einzelprüfung über die Rechte-Regel läuft
#: je Kandidat, und mehr als ein Bildschirm voll Namen braucht die Oberfläche nie.
MITGLIEDER_LIMIT = 20
#: Kleinste sinnvolle Trefferzahl (Review R1/6): mit ``limit=1`` ließe sich über
#: ``mehr`` und immer längere ``q`` Zeichen für Zeichen durch die Gemeinde
#: fragen — eine Suche, die niemand tippt, und ein Seitenkanal über die
#: Trefferzahl. Die Oberfläche zeigt ohnehin eine Liste.
MITGLIEDER_LIMIT_MIN = 5
#: Höchstlänge des Suchbegriffs ``q`` (getippter Namensanfang nach dem „@“).
MITGLIEDER_Q_MAX = 40
#: Höchstzahl geprüfter Kandidaten je Aufruf, als Vielfaches von ``limit``:
#: findet die Suche in den ersten ``3*limit`` niemanden mehr (ausgetreten,
#: nicht lesend …), sagt sie „mehr“ statt die ganze Gruppe durchzuprüfen.
MITGLIEDER_PRUEF_FAKTOR = 3
#: CHAT-4a: Kennung im ``Notification Log.document_type`` der gebündelten
#: Chat-Glocke. ``document_name`` ist die Kennung des GESPRÄCHS — darüber
#: findet ``lesestand_setzen`` die Glocke wieder (und die Oberfläche verlinkt).
CHAT_GLOCKE_DOCTYPE = "chat_gespraech"
#: CHAT-4a: Kennung der Sitzungssperre, die ZWEI Jobläufe auseinanderhält
#: (``pg_try_advisory_xact_lock``; Review R1/e). Feste Zahl, keine Zufallswerte:
#: alle Prozesse derselben Datenbank müssen dieselbe Kennung nehmen.
GLOCKE_SPERRE = 4714_0001
#: CHAT-4b: Kennung im ``Notification Log.document_type`` der UMFRAGE-Glocken
#: (Start „Neue Umfrage im …“ und Erinnerung „… endet morgen“). ``document_name``
#: ist die Kennung der UMFRAGE — getrennt von ``CHAT_GLOCKE_DOCTYPE``
#: (``chat_gespraech``), damit die gebündelte Chat-Glocke und die
#: Umfrage-Glocken desselben Gesprächs nicht auf derselben Zeile landen.
CHAT_UMFRAGE_GLOCKE_DOCTYPE = "chat_umfrage"


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


def _nicht_eigener_vorschlag(benutzer: str):
    """SQL-Bedingung „diese Nachricht ist nicht MEIN eigener Vorschlag“.

    CHAT-7b-2 (SOLL 5): eine Vorschlags-Systemzeile (``chat_nachricht.vorschlag``
    gesetzt) zählt beim VORSCHLAGENDEN nicht als ungelesen und löst keine
    Glocke aus — er hat den Vorschlag selbst gemacht. Für die übrigen bleibt
    sie stehen: sie sollen zustimmen oder ablehnen.

    Erwartet einen ``outerjoin`` auf ``ChatRundeVorschlag`` (die Spalte
    ``vorgeschlagen_von``) — Zeilen ohne Vorschlag haben dort NULL und bleiben
    damit im Ergebnis (nur der eigene Vorschlag fällt heraus). EINE Definition
    für ``_ungelesen_zaehlen`` und ``_offen_bedingung``.
    """
    return or_(ChatNachricht.vorschlag.is_(None),
               ChatRundeVorschlag.vorgeschlagen_von.is_(None),
               ChatRundeVorschlag.vorgeschlagen_von != benutzer)


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

    Für Direktgespräche (CHAT-7a) gilt dasselbe Muster über
    ``paar_schluessel`` — s. ``_direkt_holen``.
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


def _gespraech_suchen(s, art: str, gruppe: str | None, untergruppe: str | None) -> ChatGespraech | None:
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
        # Wer eine Runde verlassen hat, wird durch das Lesen NICHT wieder
        # Teilnehmer (CHAT-7b): Wieder eintreten geht nur ueber einen neuen
        # Vorschlag mit Zustimmung der Runde. Die Zeile bleibt unveraendert.
        return zeile
    zeile = ChatTeilnehmer(
        gespraech=gespraech, benutzer=benutzer, stumm=False, hinzugefuegt_am=_jetzt()
    )
    s.add(zeile)
    s.flush()
    return zeile


# ── Direktgespräch 1:1 (CHAT-7a) ────────────────────────────────────────────


#: Trenner des Kontenpaars. NICHT ``"\0"``: PostgreSQL-Textfelder dürfen kein
#: NUL-Byte enthalten (``psycopg.DataError: text fields cannot contain NUL``) —
#: der PG-Lauf von ``chat7a_direkt`` hat das sofort gezeigt. ``"\x1f"``
#: (Unit Separator) ist in keinem Konto-Namen (Adressen) enthalten und in
#: ``varchar`` unbedenklich.
PAAR_TRENNER = "\x1f"

#: Das Konto der Meldestelle (F7). Kandidat der Glocken-Abfrage; ob es die
#: Meldestelle IST, entscheidet ``_weiche_ja(... MODERIEREN)``.
MELDESTELLE_KONTO = "Administrator"

#: Neutraler Betreff der Glocke für ein 1:1 (CHAT-7a): KEIN Name — im
#: Direktgespräch wäre der Gesprächstitel der Absender (Regel CHAT-4a).
DIREKT_GLOCKE_TITEL = "Direktnachricht"

#: CHAT-9a: Kennung im ``Notification Log.document_type`` der
#: ERWÄHNUNGS-Glocke. EIGENE Art neben ``CHAT_GLOCKE_DOCTYPE``
#: (``chat_gespraech``) und ``CHAT_UMFRAGE_GLOCKE_DOCTYPE`` (``chat_umfrage``),
#: damit die Erwähnung NICHT mit dem gebündelten Gesprächs-Zähler auf derselben
#: Zeile landet (Konzept S4: „eine eigene Glocke, nicht gebündelt“).
#: ``document_name`` ist die Kennung der NACHRICHT: darüber markiert
#: ``lesestand_setzen`` sie beim Lesen als gelesen, und die Oberfläche verlinkt
#: genau die Stelle.
CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE = "chat_erwaehnung"


def _push_nach_glocke(s, konto: str, *, titel: str, inhalt: str,
                      gespraech: str) -> bool:
    """CHAT-10a: den Web-Push zu einer GERADE geschriebenen Chat-Glocke einreihen.

    **Die EINE Stelle**, an der Chat-Code einen Push anstößt. Sie wird von den
    drei Glocken wegen gerufen, die Chat-Nachrichten ankündigen — der
    gebündelten Gesprächs-Glocke (``_glocke_setzen``), der
    Umfrage-Glocke (``_umfrage_glocke_setzen``) und der Erwähnungs-Glocke
    (``_erwaehnung_glocke_setzen``) — und NUR, wenn ``glocke_setzen`` wirklich
    geschrieben hat. Damit gilt für den Push genau die Glocken-Regel und keine
    eigene: stumm → keine Glocke → kein Push; Erwähnung klingelt auch bei
    stumm → Push wie die Glocke.

    Nutzlast ist ``{titel, text, ziel}`` — ``titel``/``text`` sind WÖRTLICH
    die Glocke, ``ziel`` ist die Adresse im SPA. Kein Nachrichtentext, kein
    Absendername (Konzept F10).

    **Erst NACH dem Commit** (Review R1/7): der Auftrag wird NICHT sofort
    eingereiht, sondern am Ende der Transaktion von ``s`` — über das
    SQLAlchemy-Ereignis ``after_commit``. Bei einem Rollback läuft er nie, dann
    gibt es auch keine Glocke. ``verzögert`` merkt sich die Nutzlast (eine
    kleine Kopie, kein ORM-Objekt), damit der Listener sie nach dem
    Sitzungsende noch einreihen kann (``session.expunge_all()`` passiert vor
    ``after_commit``).

    Der Aufruf ist Beiwerk: ein Fehler wird protokolliert, nicht geworfen —
    die Glocke steht bereits.
    """
    from diakronos_app.api import push as push_api

    if not konto or not push_api.aktiv():
        return False  # Push ist aus: kein Auftrag, kein Fehler
    nutzlast = {"titel": titel, "text": inhalt, "ziel": f"#/nachrichten/{gespraech}"}
    try:
        if not _push_verzoegert(s, str(konto), nutzlast):
            # Keine Sitzung (oder kein Ereignis möglich): sofort einreihen.
            # Das ist der Fall, wenn ein Aufrufer ohne ``session=s`` glockt.
            return bool(push_api.versand_auftrag(str(konto), nutzlast))
        return True
    except Exception:  # noqa: BLE001 — Push ist Beiwerk, die Glocke steht
        logger.exception("chat: Push-Auftrag %s fehlgeschlagen", konto)
        return False


#: Schlüssel in ``session.info``: Aufträge je offener Transaktion
#: (``{SessionTransaction: [(konto, nutzlast), …]}``).
_AUFTRAG_INFO_SCHLUESSEL = "chat_push_auftraege"
#: Schlüssel in ``session.info``: die Listener hängen schon an dieser Sitzung.
_LISTENER_INFO_SCHLUESSEL = "chat_push_listener"
#: Schlüssel in ``session.info``: Transaktionen, deren Commit gemeldet wurde.
_COMMIT_INFO_SCHLUESSEL = "chat_push_committet"


def _push_transaktion_committet(session) -> None:
    """``after_commit``: die GERADE committende Transaktion vormerken.

    SQLAlchemy meldet ``after_commit`` auch für einen Savepoint — dann ist er
    noch die innerste Transaktion. Sonst ist es die äußerste. Was mit den
    Aufträgen geschieht, entscheidet erst ``after_transaction_end``.
    """
    tx = session.get_nested_transaction() or session.get_transaction()
    if tx is not None:
        session.info.setdefault(_COMMIT_INFO_SCHLUESSEL, set()).add(tx)


def _push_transaktion_ende(session, tx) -> None:
    """``after_transaction_end``: Aufträge von ``tx`` abgeben, einreihen oder verwerfen.

    - Savepoint gut ausgegangen → seine Aufträge gehen an die umgebende
      Transaktion (sie werden erst mit deren Commit wirksam).
    - Äußerste Transaktion committet → alle ihre Aufträge einreihen.
    - Sonst (Rollback, ``close()`` ohne Commit) → NUR die Aufträge von ``tx``
      verwerfen; die einer umgebenden Transaktion bleiben stehen.
    """
    committet = session.info.get(_COMMIT_INFO_SCHLUESSEL, set())
    gut = tx in committet
    committet.discard(tx)
    auftraege = session.info.get(_AUFTRAG_INFO_SCHLUESSEL, {})
    offen = auftraege.pop(tx, [])
    eltern = tx.parent
    if gut and offen and eltern is not None:
        auftraege.setdefault(eltern, []).extend(offen)
        offen = []
    if eltern is None:
        # Äußerste Transaktion zu Ende: ``session.info`` überlebt ``close()``,
        # also hier aufräumen — nichts darf in die nächste Transaktion wandern.
        session.info.pop(_AUFTRAG_INFO_SCHLUESSEL, None)
        session.info.pop(_COMMIT_INFO_SCHLUESSEL, None)
    if not (gut and offen):
        return
    from diakronos_app.api import push as push_api

    for konto_i, nutzlast_i in offen:
        try:
            push_api.versand_auftrag(konto_i, nutzlast_i)
        except Exception:  # noqa: BLE001 — ein Auftrag, nicht der Rest
            logger.exception("chat: Push-Auftrag %s fehlgeschlagen", konto_i)


def _push_verzoegert(s, konto: str, nutzlast: dict[str, str]) -> bool:
    """Merkt ``(konto, nutzlast)`` an der innersten offenen Transaktion von ``s``.

    Gibt ``False`` zurück, wenn ``s`` keine Sitzung ist oder keine Transaktion
    offen hat — der Aufrufer reiht dann sofort ein.

    Der Merker lebt in ``s.info`` (nicht in einem Modul-Dict über
    ``id(session)``: Adressen werden wiederverwendet). Je Transaktion eine
    eigene Liste, damit ein zurückgenommener Savepoint nur SEINE Aufträge
    mitnimmt und ein gut ausgegangener sie nach außen abgibt. Eingereiht wird
    erst, wenn die äußerste Transaktion committet ist.
    """
    from sqlalchemy import event as sa_event

    if s is None or not hasattr(s, "dispatch") or not hasattr(s, "info"):
        return False
    tx = s.get_nested_transaction() or s.get_transaction()
    if tx is None:
        return False
    s.info.setdefault(_AUFTRAG_INFO_SCHLUESSEL, {}).setdefault(tx, []).append(
        (konto, dict(nutzlast)))
    if not s.info.get(_LISTENER_INFO_SCHLUESSEL):
        # Je Sitzung EINMAL; die Listener bleiben hängen (Abmelden im eigenen
        # Rückruf bricht SQLAlchemys Iteration) und sind ohne Merker leer.
        sa_event.listen(s, "after_commit", _push_transaktion_committet)
        sa_event.listen(s, "after_transaction_end", _push_transaktion_ende)
        s.info[_LISTENER_INFO_SCHLUESSEL] = True
    return True


def _paar_schluessel(konto_a: str, konto_b: str) -> str:
    """Das sortierte Kontenpaar — der Schlüssel „EIN Gespräch je Personenpaar“.

    Sortiert, damit die REIHENFOLGE des Anlegens gleichgültig ist („A schreibt
    B“ und „B schreibt A“ treffen dieselbe Zeile, Konzept 10.1 Punkt 4).
    Getrennt mit ``PAAR_TRENNER``: kein Konto-Name enthält dieses Zeichen, also
    können ``("ab", "c")`` und ``("a", "bc")`` nicht denselben Schlüssel
    ergeben.
    """
    a, b = sorted((str(konto_a or ""), str(konto_b or "")))
    return f"{a}{PAAR_TRENNER}{b}"


def _gespraech_mit_paar(s, konto_a: str, konto_b: str) -> ChatGespraech | None:
    """Das 1:1-Gespräch zweier Konten — oder ``None``.

    Gesucht wird über ``paar_schluessel``; bleibt (Altbestand/Handeingriff)
    mehr als eine Zeile stehen, gilt ``art = 'direkt'`` und die älteste — der
    Verlauf ist dann nicht verloren und der Betrieb sieht die Doppelung.
    """
    return s.execute(
        select(ChatGespraech)
        .where(ChatGespraech.art == ART_DIREKT,
               ChatGespraech.paar_schluessel == _paar_schluessel(konto_a, konto_b))
        .order_by(ChatGespraech.name)
    ).scalars().first()


def _direkt_holen(s, konto_a: str, konto_b: str) -> ChatGespraech:
    """Das 1:1-Gespräch zweier Konten; legt es beim ersten Zugriff an.

    Dasselbe Muster wie ``_gespraech_holen``: der Unique-Index
    ``uq_chat_gespraech_paar`` lässt nur EINE Zeile je Personenpaar zu, zwei
    gleichzeitige Aufrufe fangen den ``IntegrityError`` im SAVEPOINT ab und
    lesen die Zeile des Gewinners. Ohne das Abfangen bliebe die Sitzung auf
    PostgreSQL nach dem Fehler unbrauchbar (500er für alle Folgeschritte).
    """
    vorhanden = _gespraech_mit_paar(s, konto_a, konto_b)
    if vorhanden is not None:
        return vorhanden
    neu = ChatGespraech(
        name=_kennung("chat-gespraech"),
        art=ART_DIREKT,
        # KEINE Gruppe: der Raum sind die Teilnehmenden (Konzept 3.3).
        gruppe=None,
        untergruppe=None,
        paar_schluessel=_paar_schluessel(konto_a, konto_b),
        angelegt_von=_benutzer() or None,
        angelegt_am=_jetzt(),
    )
    try:
        with s.begin_nested():
            s.add(neu)
            s.flush()
            # BEIDE Teilnahmezeilen in DEMSELBEN Savepoint: ein Gespräch ohne
            # vollständige Teilnahme wäre ein Raum, den der Rechte-Kern nicht
            # kennt (und den niemand mehr öffnen könnte).
            for konto in sorted({str(konto_a), str(konto_b)}):
                s.add(ChatTeilnehmer(gespraech=neu.name, benutzer=konto,
                                     stumm=False, hinzugefuegt_am=_jetzt()))
            s.flush()
    except IntegrityError:
        vorhanden = _gespraech_mit_paar(s, konto_a, konto_b)
        if vorhanden is None:
            raise
        return vorhanden
    return neu


def _direkt_konten(s, gespraech: str) -> list[str]:
    """Alle Konten des 1:1-Gesprächs (``chat_teilnehmer``) — sortiert."""
    return sorted(_teilnahme_konten(s, gespraech))


def _direkt_gegenueber(s, g: ChatGespraech, benutzer: str) -> str | None:
    """Das KONTO der anderen Person in einem 1:1-Gespräch (oder ``None``).

    Grundlage sind die Teilnahmezeilen, nicht ``paar_schluessel``: fällt eine
    Zeile (Konto gelöscht), bleibt die andere stehen und ist dann allein.
    """
    andere = [k for k in _direkt_konten(s, g.name) if k != benutzer]
    return andere[0] if len(andere) == 1 else None


def _konto_ausgeschlossen(konto: str | None) -> bool:
    """Ist dieses Konto ausgeschlossen? — dieselbe Schranke wie im Rechte-Kern.

    Nur für die ANZEIGE (Bild des Gegenübers in einem 1:1, Review CHAT-7a,
    Punkt 4): ``mitglied_ausgeschlossen`` ist die *Wurzel* der Rechteprüfung
    (``get_roles`` liefert dafür ``()``) und wird hier direkt gefragt, statt das
    Konto durch ``_erlaube`` zu schicken — es geht nicht um ein Recht dieser
    Person, sondern um eine Auskunft ÜBER sie. Fehler ⇒ ``False`` (dieselbe
    fail-open-Grenze wie die Funktion selbst, sie ist eine Zusatzschranke; die
    Hauptregel ``enabled`` bleibt fail closed).
    """
    if not konto:
        return False
    try:
        from diakronos_app.frappe_compat.permissions import mitglied_ausgeschlossen

        return bool(mitglied_ausgeschlossen(str(konto)))
    except Exception:  # noqa: BLE001 — Anzeige, siehe Docstring
        return False


def _person_je_konto(s, konto: str | None) -> str | None:
    """Mitglied-Kennung eines Kontos — REIN LESEND über ``mitglied.user``.

    Nur zum ANZEIGEN (Titel/Bild), nie für eine Rechtefrage. Deshalb steht hier
    KEINE Aktiv-/Statusprüfung und NICHT ``rechte.eigenes_mitglied`` (das ist
    die Rechte-Sicht und liefert für eine ausgeschlossene oder ausgetretene
    Person ``None``). Genau daran ging die Maskierung vorher verloren: ohne
    Mitglied fiel der Titel auf Konto bzw. E-Mail zurück — und das ist der
    volle Name, den niemand sehen soll.

    Mehrdeutig (zwei Mitglieder am selben Login) → ``None`` (dann bleibt der
    Titel leer statt falsch).
    """
    kennung = str(konto or "").strip()
    if not kennung:
        return None
    treffer = [str(n) for n in s.execute(
        select(Mitglied.name).where(Mitglied.user == kennung)
    ).scalars().all() if n]
    return treffer[0] if len(treffer) == 1 else None


def _direkt_titel(s, g: ChatGespraech, benutzer: str,
                  *, ausgeschlossene: set[str] | None = None,
                  ) -> tuple[str, str | None, str]:
    """Titel, Mitglied-Kennung und Bild des Gegenübers in einem 1:1-Gespräch.

    Der Titel ist IMMER der gekürzte Anzeigename aus der bestehenden Quelle
    (``personen_anzeige.kuerze_name`` — dieselbe Regel wie Suche/Adressbuch,
    also „Bert B.“ auch für ein aktives Mitglied und „Gelöschte Person“ nach
    Art. 17). Auf Konto oder E-Mail wird NIE zurückgefallen: eine Adresse ist
    der volle Name. Fehlt der Mitgliedsdatensatz (Altbestand), bleibt der
    Titel LEER — die Oberfläche zeigt dann „Unbekannt“.

    Nach einer Anonymisierung ist die Teilnahmezeile des gelöschten Kontos weg
    (``chat_teilnehmer.benutzer`` ist eine Konto-Spalte) — es stehen dann
    weniger als zwei Teilnahmen im Gespräch. Dann steht dort „Gelöschte
    Person": der neutrale Text, NICHT die Kennung, NICHT die Adresse, NICHT
    der Rest des Namens. Ein leeres Feld wäre für die Oberfläche nicht von
    „noch kein Gegenüber“ zu unterscheiden.

    Ist das Gegenüber AUSGESCHLOSSEN, wird KEIN Bild ausgeliefert (Review
    CHAT-7a, Punkt 4, Entscheidung Operator): in der Personensuche erscheint
    diese Person auch nicht, ein Bild in der Gesprächsliste wäre der einzige
    Weg zu ihr. Der Titel bleibt der gekürzte Name — die Kennung fürs Profil
    ebenfalls (sie ist keine Auskunft über die Person; ohne sie könnte die
    Oberfläche das Gegenüber nicht zuordnen).

    ``ausgeschlossene`` (CHAT-N2): die Menge der gesperrten Konten, EINMAL je
    Anfrage von ``meine_gespraeche`` gelesen (``_ausgeschlossene_konten``;
    deckt auch Konten ab, die erst über die E-Mail zum Mitglied gehören —
    ``wirksame_konten``). Ohne sie bleibt der heutige Weg als Rückfall: die
    Marke in der Mitgliedszeile, sonst die Schranke des Kerns (je Gespräch ein
    Volllauf) — nur für Aufrufwege außerhalb der Liste.
    """
    from diakronos_app.frappe_compat.personen_anzeige import (
        GELOESCHT_ANZEIGE,
        ist_geloescht,
        kuerze_name,
    )

    konten = _direkt_konten(s, g.name)
    gegner = _direkt_gegenueber(s, g, benutzer)
    # Ein 1:1 hat immer ZWEI Teilnahmezeilen. Steht nur noch eine (oder keine),
    # ist die andere Person gegangen — anonymisiert oder gelöscht.
    ohne_teilnahme = len(konten) < 2
    if ausgeschlossene is None:
        # Rückfall ohne übergebene Menge: dieselbe Auskunft, aber je Gespräch
        # ein Volllauf über Mitglied/User.
        ausgeschlossen = _konto_ausgeschlossen(gegner)
    else:
        ausgeschlossen = bool(gegner) and gegner in ausgeschlossene
    mitglied = _person_je_konto(s, gegner)
    if mitglied:
        zeile = s.execute(
            select(Mitglied.name, Mitglied.vorname, Mitglied.nachname,
                   Mitglied.foto, Mitglied.status, Mitglied.ausgeschlossen)
            .where(Mitglied.name == mitglied)
        ).first()
        if zeile is not None:
            roh = {"name": mitglied, "vorname": zeile[1], "nachname": zeile[2],
                   "foto": zeile[3], "status": zeile[4]}
            # EINE Namensregel für ALLE (``kuerze_name``): „Vorname N.“ auch
            # für ein AKTIVES Mitglied — der Chat ist kein Verwaltungsweg.
            # Gelöscht → „Gelöschte Person“ (das sagt ``kuerze_name`` über die
            # Kennung), Bild dann keines (``ist_geloescht``). Der Titel fällt
            # NIE auf Kennung, Konto oder Adresse zurück (Review CHAT-7a,
            # Punkt 4); „Ehemaliges Mitglied“ ist der Text ohne jeden Namen.
            name = str(kuerze_name(zeile[1], zeile[2], mitglied) or "").strip()
            # Der Ausschluss steht in DIESER Zeile UND in der übergebenen
            # Menge: die Marke kennt nur das verknüpfte Mitglied, die Menge
            # auch ein Konto, das über die E-Mail dazugehört (``wirksame_konten``).
            ausgeschlossen = ausgeschlossen or bool(zeile[5])
            bild = "" if ausgeschlossen else _suche_bild(
                roh.get("foto"), ist_geloescht(roh))
            return name, mitglied, bild
    if gegner is None and ohne_teilnahme:
        # Kein Gegenüber-Konto mehr (Anonymisierung hat die Teilnahmezeile
        # mitgenommen): der neutrale Text, NICHT die Kennung und NICHT die
        # Adresse. Bewusst ohne Bild.
        return GELOESCHT_ANZEIGE, None, ""
    return "", None, ""


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
    """Darf ``benutzer`` dieses Gespraech JETZT lesen? — ueber die EINE Weiche.

    ``_weiche_ja`` fragt je ``art`` den Kern (Gruppe ``rechte.darf``,
    Direktgespraech ``rechte.darf_direktgespraech``) — keine eigene
    Rollenlogik und kein zweiter Rechtepfad. Gebraucht wird das fuer die
    Zaehlung: eine Teilnahmezeile allein sagt nichts ueber den heutigen Stand.
    """
    g = s.get(ChatGespraech, gespraech)
    if g is None or g.geloescht_am is not None:
        return False
    return _weiche_ja(benutzer, rechte.LESEN, g=g, sitzung=s)


def _zeile(s, n: ChatNachricht, *,
           lesestand: dict[str, int | None] | None = None,
           reaktionen: dict[str, list[dict[str, Any]]] | None = None,
           antwort_auf: str | None = None,
           namen: dict[str, str] | None = None,
           konto_namen: dict[str, str] | None = None,
           umfragen: dict[str, dict[str, Any]] | None = None,
           erwaehnungen: dict[str, list[dict[str, str]]] | None = None,
           ich: str = "",
           system: dict[str, Any] | None = None) -> dict[str, Any]:
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

    CHAT-7b (Review R1, SOLL 8): eine SYSTEMZEILE (``n.vorschlag``) wird mit
    ``system={text, stand, vorschlag, eigene}`` übergeben — der sichtbare Satz
    „X möchte Y hinzufügen“ entsteht beim Lesen aus der Vorschlagszeile und
    steht NICHT in der Nachricht. Solche Zeilen haben keinen Besitz (``autor``
    None) und keinen Text im Datensatz.

    CHAT-7b-3: ``system.vorschlag`` ist die Kennung, die ``runde_zustimmen``/
    ``runde_ablehnen`` erwarten, ``system.eigene`` sagt der LESENDEN Person, ob
    SIE den Vorschlag gemacht hat (``vorgeschlagen_von`` == sie selbst) — das
    Feld hängt also am Lesenden und kommt deshalb aus ``system``, nicht aus dem
    Datensatz. Das ``eigene`` der Zeile selbst bleibt davon unberührt (eine
    Systemzeile hat keinen Autor).
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
        "text": (None if geloescht
                 else ((system or {}).get("text") if n.vorschlag else n.text)),
        "geloescht": geloescht,
        "geloescht_grund": n.entfernt_grund if geloescht else None,
        "bearbeitet": n.bearbeitet_am is not None,
        "bearbeitet_am": _isoopt(n.bearbeitet_am),
        "erstellt_am": _isoopt(n.erstellt_am),
        "antwort_auf": n.antwort_auf,
        "antwort_auf_text": antwort_auf,
        "reaktionen": (reaktionen or {}).get(n.name, []),
        "gelesen_von": (lesestand or {}).get(n.name),
        # CHAT-9a: die erwähnten Beteiligten — an einer GELÖSCHTEN Nachricht
        # niemand (an einer Lücke gibt es nichts zu erwähnen), sonst die
        # Liste aus ``_erwaehnungen_laden`` (Mitglied-Kennung + Anzeigename).
        "erwaehnt": [] if geloescht else list((erwaehnungen or {}).get(n.name, [])),
    }
    if n.vorschlag:
        # Eigene Art statt eines „normalen“ Beitrags: nicht bearbeitbar,
        # nicht löschbar, nicht meldbar — die Oberfläche zeichnet sie als
        # Systemhinweis („X möchte Y hinzufügen“).
        # CHAT-7b-3: `vorschlag` ist die Kennung für runde_zustimmen/
        # runde_ablehnen; `eigene` ist die Sicht der LESENDEN Person.
        zeile["system"] = {"art": "runde_vorschlag",
                           "stand": (system or {}).get("stand"),
                           "vorschlag": str(n.vorschlag),
                           "eigene": bool((system or {}).get("eigene"))}
    if n.umfrage:
        zeile["umfrage"] = None if geloescht else (umfragen or {}).get(str(n.umfrage))
    return zeile


def _isoopt(wert: datetime | None) -> str | None:
    return wert.isoformat() if wert else None


def _zitat(s, n: ChatNachricht, *, vor_eintritt: bool = False) -> str | None:
    """Eine Zeile des zitierten Textes („die Antwort zitiert eine Zeile“).

    Gelöscht → ``None`` (kein Inhalt nach außen). Sonst die erste nicht-leere
    Zeile, auf 140 Zeichen gekürzt — die Oberfläche zeigt sie klein über der
    Antwort.

    ``vor_eintritt`` (CHAT-7b-2, SOLL 2): die zitierte Nachricht liegt für den
    Lesenden VOR seinem Eintritt in die Runde — dann ist der Text ebenfalls
    ``None``. Die Hülle (``antwort_auf``/``antwort_auf_text = None``) bleibt
    stehen, der Inhalt nicht.
    """
    if n.geloescht_am is not None or vor_eintritt:
        return None
    for zeile in str(n.text or "").splitlines():
        if zeile.strip():
            return zeile.strip()[:140]
    return None


def _zitate(s, nachrichten: list[ChatNachricht], *,
            gespraech: ChatGespraech | None = None,
            gespraech_name: str | None = None,
            benutzer: str | None = None) -> dict[str, str | None]:
    """Zitattexte einer VERLAUFSSEITE — EINE Abfrage, Sichtbarkeit je Ziel.

    CHAT-7b-2 (SOLL 2): in einer RUNDE kann die zitierte Nachricht ÄLTER sein
    als die Sichtbarkeitsgrenze des Lesenden. Dann liefert ``_zitat`` ``None``
    — die Antwort zeigt die Zitat-Hülle „nicht sichtbar“ statt des Textes.
    Ohne Gespräch/``benutzer`` gibt es keine Grenze.

    ``gespraech_name`` ist der Weg für Aufrufer, die nur die KENNUNG haben
    (``_seite_antwort``): ohne ihn liefe ``_sichtbar_ab`` über eine
    Zeichenkette und fände keine Grenze — das Zitat von vor dem Eintritt
    würde also stehen bleiben.
    """
    ids = {n.antwort_auf for n in nachrichten if n.antwort_auf}
    if not ids:
        return {}
    ziele = s.execute(select(ChatNachricht).where(ChatNachricht.name.in_(ids))).scalars().all()
    if benutzer:
        if gespraech is None and gespraech_name:
            gespraech = _gespraech_lesen(s, gespraech_name)
        grenze = _sichtbar_ab(s, gespraech, benutzer) if gespraech is not None else None
    else:
        grenze = None
    return {str(n.name): _zitat(s, n, vor_eintritt=bool(
        grenze is not None and n.erstellt_am is not None
        and n.erstellt_am < grenze)) for n in ziele}


def _vorschlags_texte(s, kennungen, benutzer: str = "") -> dict[str, dict[str, Any]]:
    """``{vorschlag: {text, stand, eigene}}`` für eine VERLAUFSSEITE — EINE Abfrage.

    Review R1 (SOLL 8): der Satz „X möchte Y hinzufügen“ steht nicht in der
    Nachricht, sondern wird hier aus der Vorschlagszeile gebildet. Namen kommen
    aus EINER Abfrage (``_personen``), nicht je Zeile.

    CHAT-7b-3: ``eigene`` ist die Sicht der LESENDEN Person (``benutzer``) —
    True genau dann, wenn SIE den Vorschlag gemacht hat. Ohne ``benutzer``
    (kein Lesender bekannt) bleibt es False.
    """
    namen_kennungen = {str(k) for k in kennungen if k}
    if not namen_kennungen:
        return {}
    vorschlaege = s.execute(
        select(ChatRundeVorschlag).where(ChatRundeVorschlag.name.in_(namen_kennungen))
    ).scalars().all()
    if not vorschlaege:
        return {}
    konten = {str(v.vorgeschlagen_von) for v in vorschlaege if v.vorgeschlagen_von}
    eigene = set()
    for konto in konten:
        mitglied = _person_je_konto(s, konto)
        if mitglied:
            eigene.add(mitglied)
    personen = _personen(s, eigene | {str(v.mitglied) for v in vorschlaege if v.mitglied})
    konto_namen = _konto_namen(s, konten)
    ergebnis: dict[str, dict[str, Any]] = {}
    for v in vorschlaege:
        konto = str(v.vorgeschlagen_von or "")
        wer = None
        mitglied_des_kontos = _person_je_konto(s, konto) if konto else None
        if mitglied_des_kontos:
            wer = personen.get(mitglied_des_kontos)
        if not wer and konto:
            wer = konto_namen.get(konto)
        wer = str(wer or "").split(" ")[0] or "Jemand"
        wen = personen.get(v.mitglied) or "die Person"
        ergebnis[str(v.name)] = {"text": _vorschlag_satz(wer, wen, v.stand),
                                 "stand": v.stand,
                                 # CHAT-7b-3: hängt am LESENDEN, nicht an der Zeile.
                                 "eigene": bool(benutzer) and konto == str(benutzer)}
    return ergebnis


def _vorschlag_satz(wer: str, wen: str, stand: str | None) -> str:
    """Der sichtbare Satz einer Vorschlags-Systemzeile — EINE Stelle.

    Die Form hängt am STAND (CHAT-7b-2, SOLL 4): ein mit dem Austritt
    hinfällig gewordener Vorschlag ist „beendet“ — das ist etwas anderes als
    „abgelehnt“ (dort hat jemand gegen etwas gestimmt). Der Satz nennt KEINE
    Namen Dritter und keinen Grund, nur wer wen wollte und dass der Vorschlag
    sich erledigt hat.
    """
    if stand == VORSCHLAG_BEENDET:
        return (f"{wer} wollte {wen} hinzufügen. Der Vorschlag ist beendet, "
                "weil sich die Runde geändert hat.")
    return f"{wer} möchte {wen} hinzufügen."


def _seite_antwort(s, gespraech: str, zeilen: list[ChatNachricht], *,
                   richtung: str, benutzer: str,
                   g: ChatGespraech | None = None) -> dict[str, Any]:
    """Die Antwortform des Verlaufs — für beide Leserichtungen EINE Form."""
    kennungen = [n.name for n in zeilen]
    if g is None:
        g = _gespraech_lesen(s, gespraech)
    # CHAT-7b-2 (SOLL 2): die Zitate werden gegen die Sichtbarkeitsgrenze des
    # LESENDEN geprüft — ein Zitat von vor seinem Eintritt bleibt leer.
    zitate = _zitate(s, zeilen, gespraech=g, gespraech_name=gespraech,
                     benutzer=benutzer)
    reakt = _reaktionen(s, kennungen, benutzer)
    stand = _gelesen_von(s, zeilen, gespraech, benutzer)
    namen = _personen(s, {n.autor for n in zeilen if n.autor})
    konten = _konto_namen(s, {n.autor_benutzer for n in zeilen if n.autor_benutzer})
    # CHAT-5: EIN Abruf für alle Umfragen dieser Seite (kein N+1) —
    # `darf_schliessen` deshalb auch für die ganze Seite, nicht je Zeile.
    umfragen = _umfragen_laden(s, [n.umfrage for n in zeilen if n.umfrage], benutzer,
                               _gespraech_lesen(s, gespraech))
    # CHAT-7b (SOLL 8): die Vorschlags-Systemzeilen dieser Seite in EINER
    # Abfrage — ihr Satz entsteht beim Lesen, nicht aus dem Nachrichtentext.
    # CHAT-7b-3: `eigene` dieser Zeilen hängt an der LESENDEN Person.
    systeme = _vorschlags_texte(s, [n.vorschlag for n in zeilen if n.vorschlag],
                                 benutzer=benutzer)
    # CHAT-9a: die Erwähnungen dieser Seite in EINER Abfrage (kein N+1).
    erwaehnungen = _erwaehnungen_laden(s, kennungen, benutzer)
    # CHAT-7b-2: der Zitattext gehört zur ZITIERTEN Nachricht
    # (``n.antwort_auf``), nicht zur zitierenden — ``_zitate`` ist nach der
    # Kennung des ZIELS geschlüsselt. Mit ``n.name`` blieb der Text immer leer
    # (die Sichtbarkeitsprüfung hätte dann nichts zu schützen gehabt).
    posten = [_zeile(s, n, lesestand=stand, reaktionen=reakt,
                     antwort_auf=zitate.get(n.antwort_auf),
                     namen=namen, konto_namen=konten, umfragen=umfragen,
                     erwaehnungen=erwaehnungen, ich=benutzer,
                     system=systeme.get(str(n.vorschlag)))
              for n in zeilen]
    return {
        "gespraech": gespraech,
        "richtung": richtung,
        "nachrichten": posten,
        # CHAT-7b-3: schaut die lesende Person auf eine Runde, in die sie erst
        # NACH dem Anlegen eingetreten ist? Die Oberfläche blendet dann
        # „frühere Nachrichten nicht sichtbar“ ein. Bewusst ein bool — weder
        # eine Zahl noch eine Auskunft über ältere Nachrichten. Dieselbe
        # Grenze wie der Verlaufsfilter (``_sichtbar_ab``).
        "ab_eintritt": _ab_eintritt(s, g, benutzer),
        # Für den nächsten Abruf: die älteste und die neueste Kennung dieser
        # Seite (die Oberfläche fragt damit weiter bzw. pollt).
        "vor": posten[0]["name"] if posten else None,
        "seit": posten[-1]["name"] if posten else None,
    }


def _ab_eintritt(s, g: ChatGespraech | None, benutzer: str | None) -> bool:
    """Ist die lesende Person erst NACH dem Anlegen dieser Runde eingetreten?

    CHAT-7b-3: nur für Runden, und nur wenn ``chat_teilnehmer.sichtbar_ab``
    NACH ``chat_gespraech.angelegt_am`` liegt. Gründungsmitglieder (Eintritt =
    Anlegen) und Nicht-Runden → ``False``. Fehlt eine der beiden Zeiten, gibt es
    nichts zu vergleichen → ``False`` (keine Aussage erfinden).
    """
    if g is None or g.art != ART_RUNDE or g.angelegt_am is None:
        return False
    eintritt = _sichtbar_ab(s, g, benutzer)
    if eintritt is None:
        return False
    return eintritt > g.angelegt_am


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

    CHAT-7a — DIREKTGESPRÄCHE: sie stehen in DERSELBEN Liste („ein Ort für
    Nachrichten“, Konzept 10.1), tragen aber ``art: "direkt"``, den
    Anzeigenamen des GEGENÜBERS als ``titel``, dessen Bild und kein
    ``gruppe``/``untergruppe``. Grundlage sind hier die TEILNAHMEZEILEN der
    Person (``chat_teilnehmer``, die eine Wahrheit über „wer ist im
    Gespräch“), je Kandidat entscheidet danach die Weiche
    (``_erlaube`` → ``rechte.darf_direktgespraech``). Fremde Direktgespräche
    tauchen nicht auf, weil sie keine Teilnahmezeile der Person haben.

    Antwort: ``{gespraeche: [{name, art, gruppe, untergruppe, titel,
    teilnehmer, stumm, geoeffnet, ungelesen, letzte_nachricht, letzte_am,
    mitglied, bild}]}``.

    CHAT-N2 — Ausschluss EINMAL je Anfrage: der Zustand (ganz ``Mitglied`` +
    ganz ``User``) wird hier EINMAL gelesen und als Menge an die Köpfe
    gereicht. Vorher lief ``mitglied_ausgeschlossen`` je 1:1-Gespräch als
    Volllauf (N+1). Die Menge kommt aus ``_ausgeschlossene_konten`` und ist
    damit dieselbe Schranke wie im Kern — auch für ein Konto, das erst über
    die E-Mail zu einem ausgeschlossenen Mitglied gehört (``wirksame_konten``).
    """
    benutzer = _benutzer()
    # EINMAL je Anfrage (CHAT-N2): derselbe Zustand, dieselbe Schranke wie im
    # Kern (``_mitglied_ausgeschlossen`` ruft genau diese beiden Funktionen).
    from diakronos_app.frappe_compat.benutzer_status import (
        _ausgeschlossene_konten,
        _kontozustand,
    )

    ergebnis: list[dict[str, Any]] = []
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.ist_gemeindemitglied(benutzer):
            _h()
        aus = _ausgeschlossene_konten(*_kontozustand())
        for g in _lesbare_gespraeche(s, benutzer):
            ergebnis.append(_gespraech_kopf(
                s, g, benutzer, ausgeschlossene=aus))
        for g in _direkt_gespraeche(s, benutzer):
            ergebnis.append(_gespraech_kopf(
                s, g, benutzer, ausgeschlossene=aus))
        for g in _runde_gespraeche(s, benutzer):
            ergebnis.append(_gespraech_kopf(
                s, g, benutzer, ausgeschlossene=aus))
    ergebnis.sort(key=lambda e: (str(e["letzte_am"] or ""), str(e["titel"])), reverse=True)
    return {"gespraeche": ergebnis}


# ── Endpunkt: Direktgespräch öffnen (CHAT-7a) ───────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)  # legt Gespraech + 2 Teilnahmen an (SEC-11)
def direkt_oeffnen(mitglied=None):
    """Das 1:1-Gespräch mit ``mitglied`` holen — oder anlegen (Konzept S3).

    EINE Zeile je Personenpaar, gleich in welcher Reihenfolge gefragt wird
    (10.1 Punkt 4: „Nachricht schreiben legt das 1:1-Gespräch an ODER setzt das
    vorhandene fort — nie ein zweites Gespräch je Personenpaar“). Die
    Eindeutigkeit steht in der Datenbank (``chat_gespraech.paar_schluessel`` +
    ``uq_chat_gespraech_paar``); zwei gleichzeitige Aufrufe erzeugen deshalb
    genau EIN Gespräch (``_direkt_holen`` fängt den ``IntegrityError``).

    Rechte — AUSSCHLIESSLICH über den Kern, nichts Eigenes hier:
    ``rechte.darf_direktnachricht(benutzer, ziel_mitglied)``. Damit fallen
    Gäste (kein Gemeinde-Mitglied), Ausgetretene/Ausgeschlossene, Personen ohne
    aktives Konto und die eigene Person heraus — jeweils 403 ohne Inhalt
    („gibt es nicht“ und „darfst du nicht“ bleiben ununterscheidbar).

    ``mitglied`` ist die MITGLIED-Kennung (``mitglied.name``); das Konto der
    Gegenperson kommt allein aus ``mitglied.user`` via ``_konto_je_mitglied``.
    Einen Rückfall über die E-Mail gibt es NICHT mehr:
    er war ein zweiter Weg zum selben Gespräch und konnte bei abweichender
    Adresse ein anderes Konto treffen. Lässt sich kein Konto auflösen → 403
    (kein Rateweg).

    Antwort: derselbe Kopf wie in ``meine_gespraeche`` (``art: "direkt"``,
    ``titel`` = Anzeigename des Gegenübers, ``mitglied``, ``bild``,
    ``ungelesen``, ``stumm``).
    """
    ziel = str(mitglied or "").strip()
    if not ziel:
        throw("mitglied fehlt.")
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        # DIE Entscheidung: der Kern. Keine Status-/Rollenabfrage in diesem Modul.
        if not rechte.darf_direktnachricht(benutzer, ziel):
            _h()
        gegenkonto = _konto_je_mitglied(s, ziel)
        if not gegenkonto:
            # Ohne Konto gibt es kein Gegenüber — dieselbe 403 wie „darfst du
            # nicht“ (der Kern hat das Konto gerade zugesagt; hier ist es die
            # Wache gegen einen zweiten Weg an ihm vorbei).
            _h()
        zeile = _direkt_holen(s, benutzer, gegenkonto)
        g = s.get(ChatGespraech, zeile.name)
        if g is None:
            raise DoesNotExistError("Gespräch nicht gefunden.")
        # Die Teilnahme der aufrufenden Person (die andere legt `_direkt_holen`
        # mit an); ein vorhandenes Gespräch hat sie schon.
        _teilnahme(s, g.name, benutzer)
        s.flush()
        return _gespraech_kopf(s, g, benutzer)


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
            # CHAT-7a: bestehende 1:1-Gespräche der Treffer in EINER Abfrage
            # (`gespraech` im Treffer). Rein lesend; angelegt wird nichts.
            vorhandene = _gespraech_kennungen_mit(
                s, benutzer,
                [dict(z._mapping if hasattr(z, "_mapping") else z).get("user")
                 for z in kandidaten])
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
            # CHAT-7b (Review R1, SOLL 6): eine Sperre darf die Suche NICHT
            # verraten. Ein gesperrtes Paar ist für die Suche dasselbe wie
            # „hat kein Konto“: `hat_konto` UND `darf_schreiben` beide false.
            # Erkannt wird die Sperre am GRUND des Kerns — ``gesperrt`` — und
            # NUR daran: „selbst“, „kein_konto“, „nicht_auffindbar“ haben mit
            # einer Sperre nichts zu tun (die eigene Person bleibt z. B.
            # auffindbar MIT Konto, nur nicht beschreibbar).
            schreibbar = darf_direktnachricht(benutzer, kennung)
            gesperrt = (not schreibbar
                        and getattr(schreibbar, "grund", "") == "gesperrt")
            treffer.append(_suche_treffer(
                kennung=kennung,
                roh=m,
                maskiert=maskiert,
                darf_schreiben=bool(schreibbar),
                hat_konto=False if gesperrt else None,
                # CHAT-7a: gibt es DIESES 1:1-Gespräch schon? Dann kann die
                # Oberfläche direkt öffnen statt „neu anlegen“.
                gespraech=vorhandene.get(str(m.get("user") or "")),
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


def _gespraech_kennungen_mit(s, benutzer: str, gegenkonten) -> dict[str, str]:
    """BESTEHENDE 1:1-Gespräche ``benutzer`` ↔ Gegenperson — EINE Abfrage.

    Für die Personensuche (CHAT-7a): der Treffer trägt ``gespraech``, damit die
    Oberfläche direkt öffnen kann; fehlt der Schlüssel, gibt es noch keines.
    Rein LESEND — angelegt wird erst in ``direkt_oeffnen``.

    Gesucht wird über ``paar_schluessel`` (sortiertes Kontenpaar), also für
    ALLE Gegenkonten einer Suchseite in EINER Abfrage — nicht mit einer
    eigenen Sitzung je Treffer. Welche Gespräche diese Person lesen darf,
    entscheidet danach die Weiche (``_weiche_ja`` → Kern); gezeigt wird nur,
    was sie ohnehin sehen könnte.
    """
    paare = {_paar_schluessel(benutzer, k): str(k)
             for k in (str(x or "").strip() for x in gegenkonten or ())
             if k and str(k) != str(benutzer)}
    if not paare or not benutzer:
        return {}
    zeilen = s.execute(
        select(ChatGespraech.name, ChatGespraech.paar_schluessel)
        .where(ChatGespraech.art == ART_DIREKT,
               ChatGespraech.geloescht_am.is_(None),
               ChatGespraech.paar_schluessel.in_(sorted(paare)))
        .order_by(ChatGespraech.name)
    ).all()
    ergebnis: dict[str, str] = {}
    for kennung, paar in zeilen:
        gegen = paare.get(str(paar))
        if not gegen or gegen in ergebnis:   # Doppelung: die aelteste gilt
            continue
        if _weiche_ja(benutzer, rechte.LESEN,
                      g=ChatGespraech(name=str(kennung), art=ART_DIREKT,
                                      gruppe=None, untergruppe=None),
                      sitzung=s):
            ergebnis[gegen] = str(kennung)
    return ergebnis


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


def _suche_begriff(q, *, min_zeichen: int = SUCHE_MIN_ZEICHEN) -> str:
    """Suchbegriff normalisieren (Kleinschreibung, Umlaute aufgelöst, getrimmt).

    Dieselbe Faltung wie die Mitgliederliste (``api.mitglieder``): „weiss“
    findet „Weiß“, „MUELLER“ findet „Müller“. Zu kurze Eingaben → ``""``.

    ``min_zeichen`` ist die einzige Stelle, an der sich die Aufrufer
    unterscheiden dürfen (CHAT-9c-2, Review R1/1): die Personensuche braucht
    zwei Zeichen (ein einzelnes fände fast die ganze Gemeinde), die
    Erwähnungssuche nach dem „@“ nicht — dort ist das erste getippte Zeichen
    der Normalfall. Die FALTUNG bleibt für beide dieselbe.
    """
    text = unicodedata.normalize("NFC", str(q or "")).strip().lower()
    for von, nach in (("ß", "ss"), ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(von, nach)
    text = " ".join(text.split())
    return text if len(text) >= min_zeichen else ""


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
                   maskiert: dict[str, Any], darf_schreiben: bool,
                   gespraech: str | None = None,
                   hat_konto: bool | None = None) -> dict[str, Any]:
    """Ein Treffer in der Form, die „Nachrichten“ zeichnet.

    ``anzeigename`` läuft durch ``personen_anzeige.kuerze`` (EINE Regel für
    gekürzte Namen) — bei einer gelöschten Person steht dort „Gelöschte
    Person“, nie die Kennung. ``hat_konto`` (aktives Konto) und
    ``darf_schreiben`` kommen beide aus dem Rechte-Kern — eine Person mit
    deaktiviertem Konto ist auffindbar, gilt aber als „hat kein Konto“.

    Kontaktfelder kommen aus ``maskiert`` (dem Ergebnis von
    ``maskiere_datensatz``) und nur, wenn die Person sie freigegeben hat. Was
    nicht freigegeben ist, steht NICHT im Treffer — auch nicht als ``None``.

    ``gespraech`` (CHAT-7a) ist die Kennung des BESTEHENDEN 1:1-Gesprächs mit
    dieser Person — oder ``None``. Die Oberfläche öffnet damit direkt; ein
    Gespräch legt erst ``direkt_oeffnen`` an (die Suche bleibt rein lesend).

    ``hat_konto`` (CHAT-7b, SOLL 6): ``None`` = die Antwort des Kerns. Für ein
    GESPERRTES Paar reicht der Aufrufer ``False`` durch — dieselbe Auskunft wie
    „hat kein Konto“, damit die Suche die Sperre nicht verrät.
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
        # Bei einem gesperrten Paar gibt der Aufrufer ``False`` mit (SOLL 6).
        "hat_konto": rechte.person_hat_konto(kennung) if hat_konto is None else bool(hat_konto),
        "darf_schreiben": bool(darf_schreiben),
        # CHAT-7a: Kennung des BESTEHENDEN 1:1-Gesprächs (``None`` = noch
        # keines); die Suche selbst legt keines an.
        "gespraech": gespraech,
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
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
        # Review R1 (SOLL 7): in einer RUNDE sieht man den Verlauf erst ab dem
        # eigenen Eintritt (``chat_teilnehmer.sichtbar_ab``); wer wieder
        # eintritt, ab dem neuen Eintritt. Beim 1:1/in der Gruppe ist das Feld
        # leer (NULL) und es gibt keine Einschränkung.
        sichtbar_ab = _sichtbar_ab(s, g, benutzer)
        # Rein lesend (SEC-11): die Teilnahme entsteht beim Oeffnen
        # (`gespraech_anlegen`), Senden oder Lesestand-Setzen.
        if vor:
            anker = _nachricht(s, str(vor), g.name)
            bedingung = [
                ChatNachricht.gespraech == g.name,
                or_(ChatNachricht.erstellt_am < anker.erstellt_am,
                    (ChatNachricht.erstellt_am == anker.erstellt_am)
                    & (ChatNachricht.name < anker.name)),
            ]
            if sichtbar_ab is not None:
                bedingung.append(ChatNachricht.erstellt_am >= sichtbar_ab)
            zeilen = s.execute(
                select(ChatNachricht).where(*bedingung)
                .order_by(ChatNachricht.erstellt_am.desc(),
                          ChatNachricht.name.desc()).limit(grenze)
            ).scalars().all()
            zeilen.reverse()  # alt -> neu anzeigen
            return _seite_antwort(s, g.name, zeilen, richtung="vor", benutzer=benutzer)
        if seit:
            anker = _nachricht(s, str(seit), g.name)
            bedingung = [
                ChatNachricht.gespraech == g.name,
                or_(ChatNachricht.erstellt_am > anker.erstellt_am,
                    (ChatNachricht.erstellt_am == anker.erstellt_am)
                    & (ChatNachricht.name > anker.name)),
            ]
            if sichtbar_ab is not None:
                bedingung.append(ChatNachricht.erstellt_am >= sichtbar_ab)
            zeilen = s.execute(
                select(ChatNachricht).where(*bedingung)
                .order_by(ChatNachricht.erstellt_am, ChatNachricht.name).limit(grenze)
            ).scalars().all()
            return _seite_antwort(s, g.name, zeilen, richtung="seit", benutzer=benutzer)
        bedingung = [ChatNachricht.gespraech == g.name]
        if sichtbar_ab is not None:
            bedingung.append(ChatNachricht.erstellt_am >= sichtbar_ab)
        zeilen = s.execute(
            select(ChatNachricht).where(*bedingung)
            .order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
            .limit(grenze)
        ).scalars().all()
        zeilen.reverse()
        return _seite_antwort(s, g.name, zeilen, richtung="neueste", benutzer=benutzer)


# ── CHAT-9a: Erwähnungen (@Name) ────────────────────────────────────────────


def _erwaehnten_liste(erwaehnt) -> list[str]:
    """Die KENNUNGEN aus ``erwaehnt`` — ausdrückliche Liste, kein Text-Parsen.

    Der Client schickt sie mit (Kartenentscheidung 1); hier wird NICHTS aus
    dem Nachrichtentext gelesen. Akzeptiert wird eine Liste (auch als
    JSON-Zeichenkette, wie sie aus einem Formular kommt) und eine einzelne
    Zeichenkette (dann ist es EINE Kennung). Alles andere ist leer: ein
    ungültiger Behälter wird STILL wie „keine Erwähnung“ behandelt — kein
    Fehler, keine Auskunft (Kartenentscheidung 2).

    Normalisiert wird nur die Form: getrimmt, leere Einträge raus, Duplikate
    zusammengefasst (Reihenfolge bleibt die des Clients — daraus ergibt sich
    die Auswahl, WELCHE 20 bei der Kappung stehen bleiben).
    """
    roh = erwaehnt
    if isinstance(roh, (bytes, bytearray)):
        try:
            roh = roh.decode("utf-8")
        except UnicodeDecodeError:
            return []
    if isinstance(roh, str):
        text_roh = roh.strip()
        if not text_roh:
            return []
        if text_roh[:1] in ("[", "{"):
            try:
                roh = json.loads(text_roh)
            except (ValueError, TypeError):
                return []
        else:
            roh = [text_roh]
    if isinstance(roh, (set, tuple)):
        roh = list(roh)
    if not isinstance(roh, list):
        return []
    gesehen: list[str] = []
    for eintrag in roh:
        if isinstance(eintrag, dict):
            # Toleranz für die Form ``{"mitglied": …}`` — der Wert ist die
            # Kennung, mehr liest dieser Weg nicht.
            eintrag = eintrag.get("mitglied")
        if not isinstance(eintrag, str):
            continue
        kennung = eintrag.strip()
        if kennung and kennung not in gesehen:
            gesehen.append(kennung)
    return gesehen


def _erwaehnungen_pruefen(s, g: ChatGespraech, benutzer: str,
                          kennungen, erstellt_am: datetime | None = None) -> list[str]:
    """Welche der genannten Kennungen GESPEICHERT werden — je Prüfung still verworfen.

    Kartenentscheidung 2, EINE Regel je Kennung (kein Fehler nach außen, keine
    Auskunft darüber, ob es die Person gibt):

    1. **Beteiligte/r des Gesprächs, die/er die Nachricht lesen darf** — über
       die vorhandenen Hilfen: bei 1:1/Runde entscheidet ``_darf_lesen`` als
       DIESE Person (dieselbe Weiche wie beim Lesen: Teilnahme + Kern), bei
       Gruppe/Untergruppe gilt die Einheit des Gesprächs (wer sie lesen darf,
       liest auch die Nachricht) plus ``chat_teilnehmer`` als Beleg, dass die
       Person im Gespräch ist. Wer die Runde VERLASSEN hat
       (``verlassen_am``) oder dessen ``sichtbar_ab`` nach der Nachricht
       liegt, ist raus.
    2. **Nicht die sendende Person selbst.**

    **Die Kontaktsperre ist hier bewusst KEIN Verwerf-Grund** (Entscheidung
    Operator R1/3): eine Sperre darf nie erkennbar sein. Wer gesperrt ist, den
    trifft sonst die stille Verwerfung — und der Absender merkte am fehlenden
    Eintrag in ``erwaehnt``, dass die Sperre besteht. Die Erwähnung wird also
    gespeichert wie jede andere; nur die GLOCKE unterbleibt
    (``_erwaehnungen_speichern`` → ``_erwaehnungen_gesperrt``).

    Rückgabe in der Reihenfolge des Clients. ``benutzer`` ist leer nur bei
    einem Aufruf ohne Anmeldung — dann gibt es keine Erwähnungen.
    """
    if not benutzer or not g.name:
        return []
    # R1/4: die Obergrenze wird VOR jeder Prüfung gezogen — sonst kostete eine
    # Liste mit 5 000 Kennungen 5 000 Kern-Abfragen, nur um danach 20 zu
    # behalten. Ausgewählt wird in der Reihenfolge des Clients.
    kandidaten = _erwaehnten_liste(kennungen)[:ERWAEHNUNGEN_MAX]
    if not kandidaten:
        return []
    # Die eigene Kennung: „erwähne dich nicht selbst“ ist keine Auskunft.
    eigene = _eigene_kennung(s, benutzer)
    konten = _konto_je_mitglieder(s, kandidaten)
    erlaubt: list[str] = []
    for mitglied in kandidaten:
        if mitglied == eigene:
            continue  # sich selbst erwähnt niemand
        if not _erwaehnung_erreichbar(s, g, mitglied, konten.get(mitglied),
                                      erstellt_am=erstellt_am):
            continue
        erlaubt.append(mitglied)
    return erlaubt


def _erwaehnungen_gesperrt(s, g: ChatGespraech, benutzer: str,
                           mitglieder) -> set[str]:
    """Die der GESPEICHERTEN Erwähnungen, die eine Kontaktsperre treffen.

    Dieselbe Prüfung wie in CHAT-7b (``RechteKontaktsperre``, BEIDE
    Richtungen in EINER Abfrage) — hier nur nicht als Verwerf-, sondern als
    Glocken-Frage (Entscheidung Operator R1/3): gespeichert wird die
    Erwähnung, geklingelt nicht. So ist die Antwort an die sendende Person mit
    und ohne Sperre gleich; nur die erwähnte Person merkt nichts.

    Die Sperre hängt an KONTEN (``user.name``). Meine Seite ist mein Konto
    plus das Konto meiner Mitgliedszeile, die andere Seite sind die Konten der
    Erwähnten — EINE Abfrage für alle Paare.
    """
    from diakronos_app.models.rechte import RechteKontaktsperre

    eigene = _eigene_kennung(s, benutzer)
    meine_seite = {str(benutzer)}
    if eigene:
        meine_seite |= {str(k) for k in _konto_je_mitglieder(s, [eigene]).values() if k}
    konten = _konto_je_mitglieder(s, mitglieder)
    fremde_seite = {str(k) for k in konten.values() if k}
    if not fremde_seite:
        return set()
    gesperrt: set[str] = set()
    for a, b in s.execute(
        select(RechteKontaktsperre.benutzer, RechteKontaktsperre.gesperrt)
        .where(RechteKontaktsperre.benutzer.in_(meine_seite | fremde_seite),
               RechteKontaktsperre.gesperrt.in_(meine_seite | fremde_seite))
    ).all():
        a, b = str(a), str(b)
        if a in meine_seite and b in fremde_seite:
            gesperrt.add(b)
        elif b in meine_seite and a in fremde_seite:
            gesperrt.add(a)
    if not gesperrt:
        return set()
    return {m for m in mitglieder if str(konten.get(m) or "") in gesperrt}



def _erwaehnung_erreichbar(s, g: ChatGespraech, mitglied: str,
                           konto: str | None,
                           erstellt_am: datetime | None = None) -> bool:
    """Ist ``mitglied`` Beteiligte/r dieses Gesprächs — und darf es lesen?

    Dieselben Hilfen wie beim Lesen, nichts nachgebaut:

    * Teilnahmezeile in ``chat_teilnehmer`` ist für JEDE Art der Beleg „ist
      im Gespräch“; ``verlassen_am`` gesetzt heißt raus (CHAT-7b).
    * ``sichtbar_ab`` (nur bei Runden gesetzt): wer erst NACH der Nachricht
      eingetreten ist, sieht sie nicht — eine Erwähnung wäre eine Auskunft
      über einen Inhalt, den es für ihn nicht gibt (``_vor_eintritt``, ohne
      die eigene Person als Maßstab: hier wird die GRENZE der anderen
      gelesen, nicht meine).
    * Bei 1:1/Runde entscheidet ``_darf_lesen`` (Teilnahme + Kern) — fail
      closed ohne Konto.
    * Bei Gruppe/Untergruppe gilt die Einheit des Gesprächs: dieselbe Frage,
      die ``verlauf`` stellt (``rechte.darf(... LESEN ...)``), nur für die
      erwähnte Person.

    CHAT-9c: die REGEL steht jetzt in ``_erwaehnung_grenze`` — die neue
    Mitgliederliste (``gespraech_mitglieder``) braucht dieselbe Grenze für
    VIELE Personen und darf keine zweite Regel bauen. Diese Funktion liest die
    Teilnahmezeile für EINE Person und reicht sie durch.
    """
    if not mitglied:
        return False
    zeile = s.execute(
        select(ChatTeilnehmer.verlassen_am, ChatTeilnehmer.sichtbar_ab)
        .where(ChatTeilnehmer.gespraech == g.name,
               ChatTeilnehmer.benutzer == konto if konto is not None
               else ChatTeilnehmer.benutzer.is_(None))
    ).first()
    return _erwaehnung_grenze(s, g, mitglied=mitglied, konto=konto,
                              zeile=zeile, erstellt_am=erstellt_am)


def _erwaehnung_grenze(s, g: ChatGespraech, *, mitglied: str,
                       konto: str | None,
                       zeile: tuple[datetime | None, datetime | None] | None,
                       erstellt_am: datetime | None = None) -> bool:
    """DIE Grenze „wen kann man in diesem Gespräch erwähnen“ — eine Regel.

    Herausgezogen aus ``_erwaehnung_erreichbar`` (CHAT-9c), damit Prüfung beim
    Senden und Mitgliederliste NICHT auseinanderlaufen. Unterschied ist allein
    die HERTKUNFT der Teilnahmezeile: ``_erwaehnung_erreichbar`` liest sie für
    EINE Person, die Liste holt sie für alle Kandidaten in EINER Abfrage
    (``zeile = (verlassen_am, sichtbar_ab)``, ``None`` = keine Zeile) — kein
    N+1 über die Gruppenmitglieder.

    Gleichbleibend: ``verlassen_am`` gesetzt heißt raus; ``sichtbar_ab`` (nur
    Runden) schneidet Nachrichten vor dem Eintritt ab; bei 1:1/Runde entscheidet
    ``_darf_lesen`` (Teilnahme + Kern, fail closed ohne Konto); bei
    Gruppe/Untergruppe die Einheit (``rechte.darf(... LESEN ...)``).
    """
    if not mitglied:
        return False
    if g.art in (ART_DIREKT, ART_RUNDE):
        # 1:1/Runde: der Raum sind die TEILNEHMENDEN — eine Teilnahmezeile ist
        # Pflicht, ``verlassen_am`` heißt raus, ``sichtbar_ab`` begrenzt.
        if zeile is None:
            return False
        if zeile[0] is not None:
            return False  # verlassen: keine Teilnahme mehr
        sichtbar_ab = zeile[1]
        if (sichtbar_ab is not None and erstellt_am is not None
                and erstellt_am < sichtbar_ab):
            return False  # Nachricht liegt VOR dem Eintritt dieser Person
        return bool(konto) and _darf_lesen(s, str(konto), g.name)
    # Gruppe/Untergruppe: der Raum ist die EINHEIT — wer sie lesen darf, liest
    # auch die Nachricht. Eine Teilnahmezeile entsteht dort erst beim Öffnen
    # und ist darum KEINE Voraussetzung (sie würde die halbe Gruppe
    # ausschließen, nur weil sie den Chat noch nie geöffnet hat).
    if not konto:
        return False
    return _weiche_ja(str(konto), rechte.LESEN, gruppe=g.gruppe,
                      untergruppe=g.untergruppe, gespraech=g.name, sitzung=s)


def _erwaehnung_glocke_setzen(s, *, konto: str, nachricht: str,
                              g: ChatGespraech) -> str:
    """EINE eigene Glocke je Erwähnung — Text im Stil der Chat-Glocken.

    Über ``benachrichtigungen.glocke_setzen`` (dieselbe Stelle wie die
    gebündelte Glocke), aber mit EIGENEM ``document_type``
    (``CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE``) und ``document_name`` = Kennung der
    NACHRICHT: sie landet damit nie auf der Zeile des Gesprächs-Zählers und
    wird beim Lesen der Nachricht wiedergefunden.

    Inhalt nach den Datenschutz-Regeln von CHAT-4a: **kein Nachrichtentext,
    kein Absendername** (``_glocken_titel`` ist aus demselben Grund neutral).

    Kein ``stumm``-Filter: die Karte entscheidet ausdrücklich, dass die
    Erwähnung auch bei stumm geschaltetem Gespräch klingelt (wie gängige
    Messenger) — wer jemanden ausdrücklich anspricht, will ihn erreichen.
    """
    from diakronos_app.benachrichtigungen import glocke_setzen

    titel = _glocken_titel(g)
    betreff = f"{titel}: Du wurdest erwähnt"
    hinweis = ("Du wurdest in einem Gespräch erwähnt. Öffne den Chat, "
               "um die Nachricht zu lesen.")
    name = glocke_setzen(
        for_user=konto,
        subject=betreff,
        inhalt=hinweis,
        document_type=CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE,
        document_name=nachricht,
        session=s,
    )
    if name:
        # CHAT-10a: Push zur geschriebenen Erwähnungs-Glocke — auch bei stumm
        # geschaltetem Gespräch (dieselbe Regel wie die Glocke, Konzept S4).
        _push_nach_glocke(s, konto, titel=betreff, inhalt=hinweis,
                          gespraech=g.name)
    return name


def _erwaehnungen_speichern(s, n: ChatNachricht, g: ChatGespraech,
                            benutzer: str, kennungen) -> list[str]:
    """Prüfen, speichern, glocken — die EINE Stelle für eine neue Nachricht.

    Rückgabe sind die GESPEICHERTEN Mitglied-Kennungen (in der Reihenfolge des
    Clients); der Aufrufer reicht sie in ``_zeile`` weiter. Glocken sind
    Beiwerk: scheitert eine, bleibt die Erwähnung trotzdem stehen
    (``glocke_setzen`` meldet den Fehler und liefert ``""``).

    Eine GESPEICHERTE Erwähnung bekommt NICHT immer eine Glocke: besteht eine
    Kontaktsperre zwischen der sendenden und der erwähnten Person (egal welche
    Richtung), unterbleibt die Glocke — die Sperre darf nie erkennbar sein
    (Entscheidung Operator R1/3, ``_erwaehnungen_gesperrt``).
    """
    erlaubt = _erwaehnungen_pruefen(s, g, benutzer, kennungen,
                                    erstellt_am=n.erstellt_am)
    if not erlaubt:
        return []
    jetzt = _jetzt()
    konten = _konto_je_mitglieder(s, erlaubt)
    for mitglied in erlaubt:
        s.add(ChatErwaehnung(nachricht=n.name, mitglied=mitglied,
                             angelegt_am=jetzt))
    s.flush()
    gesperrt = _erwaehnungen_gesperrt(s, g, benutzer, erlaubt)
    for mitglied in erlaubt:
        if mitglied in gesperrt:
            continue  # gespeichert, aber keine Glocke (Sperre bleibt unsichtbar)
        konto = konten.get(mitglied)
        if not konto:
            continue
        try:
            with s.begin_nested():
                _erwaehnung_glocke_setzen(s, konto=str(konto),
                                          nachricht=n.name, g=g)
        except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
            logger.warning("Erwähnungs-Glocke %s: %s", n.name, ex)
    return erlaubt


def _erwaehnungen_laden(s, kennungen, benutzer: str) -> dict[str, list[dict[str, str]]]:
    """``{nachricht: [{mitglied, anzeigename}]}`` für eine VERLAUFSSEITE.

    EINE Abfrage für alle Nachrichten der Seite (kein N+1). Der Anzeigename
    kommt aus ``_personen`` — der bestehenden Namensquelle inklusive
    Maskierung („Gelöschte Person“), kein zweiter Namensweg.

    **Sichtbarkeit (R1/2):** geliefert wird nur, wer für die LESENDE Person
    auffindbar ist — ``rechte.darf_person_finden`` (die Kern-Frage „Darf A B
    sehen?“ aus Kapitel 2.4), je eindeutiger Kennung der Seite EINMAL
    entschieden und für alle ihre Nachrichten wiederverwendet. Wer
    ausgetreten/ausgeschlossen/gelöscht ist, fehlt damit in der
    strukturierten Liste. Betroffen ist NUR diese Liste: der Nachrichtentext
    enthält das „@Name“ ohnehin.

    Gelöschte Nachrichten tragen KEINE Erwähnung (``_zeile`` liefert dort
    ``[]``): an einer Lücke gibt es niemanden zu erwähnen.
    """
    from diakronos_app.rechte import darf_person_finden

    ids = [str(k) for k in kennungen if k]
    if not ids:
        return {}
    zeilen = s.execute(
        select(ChatErwaehnung.nachricht, ChatErwaehnung.mitglied)
        .where(ChatErwaehnung.nachricht.in_(ids))
        .order_by(ChatErwaehnung.nachricht, ChatErwaehnung.angelegt_am,
                  ChatErwaehnung.mitglied)
    ).all()
    if not zeilen:
        return {}
    # EINE Entscheidung je eindeutiger Kennung der Seite (nicht je Zeile).
    sichtbar: dict[str, bool] = {}
    for _n, mitglied in zeilen:
        if mitglied and str(mitglied) not in sichtbar:
            sichtbar[str(mitglied)] = bool(darf_person_finden(benutzer, str(mitglied)))
    namen = _personen(s, {str(m) for _n, m in zeilen if m})
    ergebnis: dict[str, list[dict[str, str]]] = {}
    for nachricht, mitglied in zeilen:
        if not mitglied or not sichtbar.get(str(mitglied)):
            continue
        ergebnis.setdefault(str(nachricht), []).append(
            {"mitglied": str(mitglied), "anzeigename": namen.get(str(mitglied), str(mitglied))})
    return ergebnis


def _erwaehnung_glocken_als_gelesen(s, gespraech: str, benutzer: str,
                                    nachricht: str | None) -> int:
    """Erwähnungs-Glocken bis ``nachricht`` als gelesen markieren.

    Analog zum Lesestand: gelesen ist, was BIS ZU DIESER Nachricht
    (einschließlich) erwähnt hat — nicht mehr. Verglichen wird über die
    POSITION im Verlauf (Zeitstempel + Kennung), nicht über die Reihenfolge
    der Erwähnungen: eine Nachricht ohne Erwähnung darf die Grenze nicht
    verschieben. ``nachricht=None`` fasst nichts an (der Aufrufer kennt die
    sichtbare Grenze).

    R1/5: EIN ``UPDATE`` über ``document_name IN (Unterabfrage der
    Erwähnungen ≤ Grenze)`` — kein N+1 über die einzelnen Glocken. Fehler
    bleiben Beiwerk.

    Die Zeile im ``Notification Log`` bleibt als Nachweis stehen (wie jede
    andere Benachrichtigung), nur ``read`` wird gesetzt.
    """
    from diakronos_app.models.core import NotificationLog

    if not benutzer or not nachricht:
        return 0
    # ``chat_erwaehnung.mitglied`` ist eine MITGLIED-Kennung — das Konto der
    # Person wird über ``_eigene_kennung`` aufgelöst (kein zweiter Weg).
    mitglied = _eigene_kennung(s, benutzer)
    if not mitglied:
        return 0
    anker = s.execute(
        select(ChatNachricht.erstellt_am, ChatNachricht.name)
        .where(ChatNachricht.name == nachricht, ChatNachricht.gespraech == gespraech)
    ).first()
    if anker is None:
        return 0  # nicht im Gespräch: keine Grenze, keine Aussage
    grenze_am, grenze_name = anker
    # Die Grenze (Zeitstempel + Kennung) und die Ziel-Kennungen in EINER
    # Anweisung: UNTERABFRAGE statt Namensliste nach Python.
    bis_hier = or_(ChatNachricht.erstellt_am < grenze_am,
                   and_(ChatNachricht.erstellt_am == grenze_am,
                        ChatNachricht.name <= grenze_name))
    grenzen = (
        select(ChatErwaehnung.nachricht)
        .join(ChatNachricht, ChatNachricht.name == ChatErwaehnung.nachricht)
        .where(ChatErwaehnung.mitglied == mitglied,
               ChatNachricht.gespraech == gespraech,
               bis_hier)
        .scalar_subquery()
    )
    try:
        # Savepoint: scheitert das UPDATE auf PostgreSQL, bliebe sonst die
        # ganze Transaktion abgebrochen und der Lesestand ginge mit verloren.
        with s.begin_nested():
            return int(s.execute(
                update(NotificationLog)
                .where(NotificationLog.for_user == benutzer,
                       NotificationLog.document_type == CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE,
                       NotificationLog.document_name.in_(grenzen),
                       NotificationLog.read.is_(False))
                .values(read=True)
                .execution_options(synchronize_session=False)
            ).rowcount or 0)
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        logger.warning("Erwähnungs-Glocken als gelesen %s: %s", gespraech, ex)
        return 0


def _nachricht_erwaehnungen_raeumen(s, nachricht: str) -> int:
    """Erwähnungen einer Nachricht entfernen (gelöschte/entfernte Nachricht).

    Dasselbe Muster wie bei den Umfrage-Glocken: die Zeilen fallen weg, und
    eine offene Erwähnungs-Glocke wird GELESEN gestellt statt zu bleiben —
    sonst führte sie zu einer Lücke im Verlauf.
    """
    from diakronos_app.benachrichtigungen import glocke_gelesen

    personen = [str(m) for m in s.execute(
        select(ChatErwaehnung.mitglied).where(ChatErwaehnung.nachricht == nachricht)
    ).scalars().all() if m]
    if not personen:
        return 0
    s.execute(delete(ChatErwaehnung).where(ChatErwaehnung.nachricht == nachricht))
    # Die Glocke hängt am KONTO (`for_user`) — ``chat_erwaehnung.mitglied``
    # ist die Mitglied-Kennung. Dieselbe Auflösung wie beim Senden
    # (``_konto_je_mitglieder``), kein zweiter Weg.
    konten = _konto_je_mitglieder(s, personen)
    for mitglied in personen:
        konto = konten.get(mitglied)
        if not konto:
            continue
        glocke_gelesen(for_user=str(konto),
                       document_type=CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE,
                       document_name=nachricht)
    return len(personen)


# ── CHAT-9c: zwei Lese-Endpunkte für die Erwähnungs-Oberfläche ──────────────


@whitelist(methods=["GET"], allow_guest=False)  # rein lesend (SEC-11)
def nachricht_kontext(nachricht):
    """Wohin gehört diese Nachricht? ``{gespraech, art, titel}``.

    Die Oberfläche braucht das für eine Erwähnungs-Glocke: sie kennt nur die
    Kennung der Nachricht (``document_name``) und muss das Gespräch öffnen.
    ``titel`` ist derselbe Titel wie in ``meine_gespraeche`` für die LESENDE
    Person (``_gespraech_kopf`` — bei 1:1 der Anzeigename des Gegenübers, bei
    Runden der Rundenname, sonst Gruppe/Untergruppe).

    Nur wenn die lesende Person GENAU DIESE Nachricht sehen darf: Gespräch
    lesen (``_erlaube`` LESEN) und — in einer Runde — ``sichtbar_ab``/
    aktive Teilnahme (``_vor_eintritt``, dieselbe Grenze wie Verlauf, Zitat
    und Lesestand). Eine gelöschte/entfernte Nachricht (``geloescht_am``) gilt
    wie „gibt es nicht“ — an einer Lücke gibt es nichts zu öffnen.

    Alle Fehlfälle antworten GLEICH (``DoesNotExistError`` ohne Unterschied):
    unbekannte Nachricht, fremdes Gespräch, fehlendes Leserecht, Nachricht vor
    dem eigenen Eintritt, gelöschte Nachricht. Keine Auskunft darüber, ob es
    die Nachricht gibt — damit ist auch ein Erwähnungs-Anker kein Rateweg.
    """
    benutzer = _benutzer()
    nachricht = str(nachricht or "").strip()
    if not nachricht:
        raise DoesNotExistError("Nachricht nicht gefunden.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = s.get(ChatNachricht, nachricht)
        if n is None or n.geloescht_am is not None:
            raise DoesNotExistError("Nachricht nicht gefunden.")
        g = s.get(ChatGespraech, n.gespraech)
        if g is None or g.geloescht_am is not None:
            raise DoesNotExistError("Nachricht nicht gefunden.")
        # Leserecht: dieselbe Weiche wie überall. Der Wurf wird zu DERSELBEN
        # neutralen Antwort — kein 403, das „hier gibt es etwas“ verriete.
        if not _weiche_ja(benutzer, rechte.LESEN, g=g, sitzung=s):
            raise DoesNotExistError("Nachricht nicht gefunden.")
        if _vor_eintritt(s, g, benutzer, n.erstellt_am):
            raise DoesNotExistError("Nachricht nicht gefunden.")
        # Derselbe Kopf wie in `meine_gespraeche` (Titel, Ausschluss-Zustand
        # EINMAL je Anfrage — CHAT-N2), damit der Titel nicht abweicht.
        from diakronos_app.frappe_compat.benutzer_status import (
            _ausgeschlossene_konten,
            _kontozustand,
        )

        kopf = _gespraech_kopf(
            s, g, benutzer,
            ausgeschlossene=_ausgeschlossene_konten(*_kontozustand()))
        return {"gespraech": str(g.name), "art": str(g.art or ""),
                "titel": kopf["titel"]}


@whitelist(methods=["GET"], allow_guest=False)  # rein lesend (SEC-11)
def gespraech_mitglieder(gespraech, q="", limit=MITGLIEDER_LIMIT):
    """Wen kann ich in diesem Gespräch erwähnen — Suche nach Namensanfang.

    ``{art, mitglieder, mehr}``; ``mitglieder`` = ``[{mitglied, anzeigename}]``
    nach Anzeigename sortiert (``_personen`` — dieselbe Namensquelle wie
    ``erwaehnt[].anzeigename`` und ``autor``; KEINE Kontaktdaten).

    CHAT-9c-2 — SUCH-VERTRAG (ersetzt die Vollliste): ``q`` ist der getippte
    Namensanfang nach dem „@“ (0–40 Zeichen, getrimmt, sonst wird es
    abgeschnitten; auch EIN Zeichen filtert schon). Die Kandidaten der Einheit
    (Gruppe/Untergruppe = Mitgliedschaften, 1:1/Runde = aktive Teilnahmezeilen)
    werden IN SQL nach Name vorgefiltert — Vorname, Nachname oder „Vorname
    Nachname“ BEGINNT mit ``q``, groß/klein- und umlautgefaltet wie
    ``personen_suchen``. ``q=""`` heißt: alle Kandidaten. Danach wird der Reihe
    nach über DIESELBE Erwähnungs-Regel geprüft (``_erwaehnung_grenze`` +
    ``darf_person_finden``, ohne mich, Kontaktsperren NICHT gefiltert), bis
    ``limit`` Treffer zusammen sind ODER ``3*limit`` Kandidaten geprüft wurden.

    ``mehr`` heißt „es GIBT weitere Kandidaten“ — nicht „es gibt weitere
    erwähnbare“ (Review R1/2): der 3*limit-Abbruch kann vor Personen stehen,
    die die Grenze ablehnen würde. Ich selbst zähle nicht als weiterer
    Kandidat.

    ``limit`` 5–20 (größer wird gekappt, kleiner auf 5 gehoben, unlesbar =
    Vorgabe; kein Fehler).

    Warum die Grenze bleibt und trotzdem reicht: eine Mengenregel über alle
    Gruppenmitglieder wäre eine ZWEITE Rechteregel (Entscheidung Operator) —
    die Suche schneidet die Kandidatenliste so weit vor, dass die
    Einzelprüfung nur für wenige Personen läuft (vorher: 300 Mitglieder =
    ~7500 SQL-Anweisungen, ~10 s).

    Für ALLE Gesprächsarten: bei Gruppe/Untergruppe alle, die die Einheit
    lesen dürfen; bei Runde/1:1 nur die AKTIVEN Teilnehmenden. Die lesende
    Person selbst fehlt immer (sich selbst erwähnt niemand) — verglichen wird
    die MITGLIED-Kennung UND das KONTO (das Konto deckt den Fall ab, dass
    ``_eigene_kennung`` nichts auflöst, z. B. Administrator). Ebenso fehlt,
    wer für sie nicht auffindbar ist (``rechte.darf_person_finden``, wie
    ``_erwaehnungen_laden``).

    Eine KONTAKTSPERRE filtert hier NICHTS: eine Sperre darf nicht erkennbar
    sein — die Glocke unterdrückt CHAT-9a bereits (``_erwaehnungen_gesperrt``).

    Recht: LESEN im Gespräch (``_erlaube``); sonst die neutrale Ablehnung wie
    bei den übrigen Chat-Endpunkten (403 ohne Inhalt).

    Leistung: ``ist_gemeindemitglied`` EINMAL vor der Schleife (bei „nein“
    leere Liste), eine Abfrage für die Kandidaten (Mitgliedschaft der Einheit
    MIT ihrem Konto, kein Hin und Zurück über Kennungen), Namens-Vorfilter in
    derselben Abfrage; die Prüfungen laufen innerhalb eines
    ``merkungsrahmen`` (PERF-K1).
    """
    from diakronos_app.models.diakonos import (
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )
    from diakronos_app.rechte import darf_person_finden, merkungsrahmen

    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    grenze = _mitglieder_grenze(limit)
    begriff = _mitglieder_begriff(q)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
        art = str(g.art or "")
        antwort: dict[str, Any] = {"art": art, "mitglieder": [], "mehr": False}
        # EINMAL vor der Schleife: ohne Gemeindemitgliedschaft findet niemand
        # jemanden (darf_person_finden sagt je Person dasselbe).
        if not rechte.ist_gemeindemitglied(benutzer):
            return antwort
        with merkungsrahmen():
            eigene = _eigene_kennung(s, benutzer)
            ich = str(benutzer)
            if art in (ART_DIREKT, ART_RUNDE):
                # Der Raum sind die TEILNEHMENDEN: Teilnahmezeile je Konto —
                # EINE Abfrage, und der Namens-Vorfilter hängt daneben.
                # Wer gegangen ist, hat keine Teilnahme mehr und fällt damit
                # schon hier heraus (dieselbe Notwendigkeit wie in der Grenze,
                # Review R1/3) — keine Zeile durch die Prüfstrecke schleppen.
                zeile_je_konto: dict[str, tuple] = {
                    str(konto): (verlassen, sichtbar)
                    for konto, verlassen, sichtbar in s.execute(
                        select(ChatTeilnehmer.benutzer, ChatTeilnehmer.verlassen_am,
                               ChatTeilnehmer.sichtbar_ab)
                        .where(ChatTeilnehmer.gespraech == g.name,
                               ChatTeilnehmer.verlassen_am.is_(None))
                    ).all() if konto
                }
                kandidaten = _mitglieder_kandidaten(s, begriff, konten=list(zeile_je_konto))
            else:
                # Über die Mitgliedschaft der EINHEIT (nicht über die erst beim
                # Öffnen entstehenden Teilnahmezeilen): sonst fehlte die halbe
                # Gruppe, die den Chat noch nie geöffnet hat. Die Kandidaten
                # kommen MIT ihrem Konto — keine Kennung-Hin-und-Zurück-Runde.
                if g.untergruppe:
                    einheit = select(
                        Untergruppenmitgliedschaft.mitglied.label("mitglied"),
                        Mitglied.user.label("user"),
                        Mitglied.vorname.label("vorname"),
                        Mitglied.nachname.label("nachname"),
                    ).join(Mitglied, Mitglied.name == Untergruppenmitgliedschaft.mitglied
                           ).where(Untergruppenmitgliedschaft.parent == g.untergruppe)
                else:
                    einheit = select(
                        Gruppenmitgliedschaft.mitglied.label("mitglied"),
                        Mitglied.user.label("user"),
                        Mitglied.vorname.label("vorname"),
                        Mitglied.nachname.label("nachname"),
                    ).join(Mitglied, Mitglied.name == Gruppenmitgliedschaft.mitglied
                           ).where(Gruppenmitgliedschaft.parent == g.gruppe)
                zeile_je_konto = {}
                kandidaten = _mitglieder_kandidaten(s, begriff, basis=einheit)
            geprueft = 0
            for zeile in kandidaten:
                mitglied = str(zeile.mitglied or "")
                konto = str(zeile.user) if zeile.user else None
                # Der Selbst-Ausschluss steht VOR der Abbruchprüfung (Review
                # R1/2): ich bin ein Kandidat wie jeder andere, aber nie ein
                # geprüfter — sonst zählte ich als „weiterer Kandidat“ und
                # ``mehr`` wäre true, obwohl niemand dahinter liegt.
                if not mitglied or mitglied == eigene or konto == ich:
                    continue  # sich selbst erwähnt niemand
                if len(antwort["mitglieder"]) >= grenze \
                        or geprueft >= grenze * MITGLIEDER_PRUEF_FAKTOR:
                    antwort["mehr"] = True
                    break
                geprueft += 1
                if not _erwaehnung_grenze(s, g, mitglied=mitglied, konto=konto,
                                          zeile=zeile_je_konto.get(konto or "")):
                    continue
                if not darf_person_finden(benutzer, mitglied):
                    continue  # nicht auffindbar (ausgetreten/gelöscht/…)
                antwort["mitglieder"].append({
                    "mitglied": mitglied,
                    "anzeigename": _anzeigename_aus_zeile(zeile, mitglied)})
        return antwort


def _mitglieder_grenze(limit) -> int:
    """Tatsächliche Trefferzahl der Erwähnungs-Suche: 5–``MITGLIEDER_LIMIT``.

    Unlesbare/negative Angaben fallen auf die Vorgabe zurück (kein Fehler) —
    die Suche soll an einem kaputten ``limit`` nicht scheitern. Nach UNTEN
    gilt ``MITGLIEDER_LIMIT_MIN`` (Review R1/6): mit ``limit=1`` ließe sich
    über ``mehr`` sonst Zeichen für Zeichen durch die Gemeinde fragen — eine
    Suche, die niemand tippt, und ein Seitenkanal über die Trefferzahl.
    """
    if limit is None or limit == "":
        return MITGLIEDER_LIMIT
    try:
        wert = int(str(limit).strip())
    except (TypeError, ValueError):
        return MITGLIEDER_LIMIT
    return max(MITGLIEDER_LIMIT_MIN, min(MITGLIEDER_LIMIT, wert))


def _mitglieder_begriff(q) -> str:
    """Suchbegriff der Erwähnungs-Suche: 0–``MITGLIEDER_Q_MAX`` Zeichen.

    Getrimmt und auf die Höchstlänge gekappt (``q`` kommt aus der Adresse).
    Die Faltung macht ``_suche_faltung`` im SQL-Ausdruck. ABWEICHEND von
    ``personen_suchen`` gilt hier KEINE Mindestlänge (Review R1/1): nach dem
    „@“ tippt man Buchstabe für Buchstabe, das erste Zeichen ist der
    Normalfall — es darf nicht heißen „alle Kandidaten“.
    """
    text = str(q or "").strip()
    return text[:MITGLIEDER_Q_MAX]


def _mitglieder_begriff_gefaltet(begriff: str) -> str:
    """``begriff`` in der Faltung der Spalten, ohne Mindestlänge (R1/1)."""
    return _suche_begriff(begriff, min_zeichen=1)


def _mitglieder_kandidaten(s, begriff: str, *, basis=None, konten=None) -> list:
    """Kandidaten der Erwähnungs-Suche — Vorfilter nach Name, sortiert.

    Zwei Bauarten, EINE Frage: ``basis`` ist die Mitgliedschafts-Abfrage der
    Einheit (Gruppe/Untergruppe, Spalten ``mitglied/user/vorname/nachname``),
    ``konten`` die Konten der Teilnahmezeilen (1:1/Runde, Namensdaten kommen
    aus ``mitglied``). Der Vorfilter entscheidet NICHTS: er schneidet nur
    Namen nach dem Anfang ab (``q=""`` = alle). Beides sind BEKANNTE Mengen aus
    dieser Datei, keine Nutzereingabe.

    Der Vorfilter lässt nur Zeilen durch, die ``_erwaehnung_grenze``
    überhaupt bejahen KANN (Review R1/3) — dieselbe Notwendigkeit, keine neue
    Regel: ohne Konto gibt es keinen Raum (beide Zweige der Grenze brauchen
    ``konto``), bei 1:1/Runde ebenso keine Teilnahme ohne Zeile für das Konto.
    Das ist wichtig für den 3*limit-Abbruch: ohne diese Bedingung füllten
    Personen ohne Konto die Prüfstrecke und verdrängten die Erwähnbaren.
    """
    if basis is None:
        if not konten:
            return []
        basis = select(
            Mitglied.name.label("mitglied"),
            Mitglied.user.label("user"),
            Mitglied.vorname.label("vorname"),
            Mitglied.nachname.label("nachname"),
        ).where(Mitglied.user.in_(list(konten)))
    basis = basis.where(Mitglied.user.is_not(None))
    if begriff:
        # EIN Muster, EINE Bedingung: Vorname, Nachname oder „Vor Nach“ beginnt
        # mit dem Begriff — dieselbe Faltung wie ``personen_suchen``.
        basis = basis.where(_mitglieder_namensfilter(begriff))
    # Nach Anzeigename (Groß-/Kleinschreibung egal), dann Kennung: stabil, damit
    # „3*limit Kandidaten“ reproduzierbar dieselben sind. ``COALESCE`` je
    # Namensteil (Review R1/4): ``vorname + " " + nachname`` ergäbe in
    # PostgreSQL bei fehlendem Teil NULL, in SQLite stillschweigend etwas
    # anderes — die Reihenfolge muss in beiden Datenbanken dieselbe sein.
    return s.execute(
        basis.order_by(_mitglieder_sortierung(), Mitglied.name)
    ).all()


def _mitglieder_sortierung():
    """Sortier-Ausdruck „Anzeigename“, DB-unabhängig (Review R1/4).

    Dieselbe Vergleichsform wie ``_anzeigename_select`` (``trim(a + ' ' + b)``),
    aber ``COALESCE`` je Namensteil: fehlt ein Teil, ergäbe ``a + ' ' + b`` in
    PostgreSQL NULL (die Zeile rutschte ans Ende) — in SQLite stillschweigend
    etwas anderes. ``COALESCE`` macht daraus in beiden Datenbanken dieselbe
    Zeichenkette.

    Als ``text()`` ausgeschrieben (feste Bezeichner aus dieser Datei, keine
    Nutzereingabe): ``text("''")`` als Argument von ``func.coalesce`` wird von
    SQLAlchemy als BINDEPARAMETER ausgegeben und in ORDER BY zu ``0`` — die
    Reihenfolge fiel damit auf die Kennung zurück (im Test belegt).
    """
    return text(
        "trim(coalesce(lower(trim(mitglied.vorname)), '') || ' ' || "
        "coalesce(lower(trim(mitglied.nachname)), ''))")


def _mitglieder_namensfilter(begriff: str):
    """SQL-Bedingung: der NAME beginnt mit ``begriff`` (gefaltet, maskiert).

    Gesucht wird in ``vorname``, ``nachname`` und der Phrase „Vorname Nachname“
    — alle drei als ANFANG (``begriff%``). Die Faltung ist ``_suche_faltung``
    (klein + Umlaute aufgelöst), damit „ber“ auch „Bert“ und „mueller“ auch
    „Müller“ trifft; der BEGRIFF wird dafür mit ``_mitglieder_begriff_gefaltet``
    gefaltet — eine zweite Faltungsregel gibt es nicht. Platzhalter im Begriff
    werden maskiert (ein getipptes ``%``/``_`` darf nichts aufreißen).
    """
    maskiert = _mitglieder_begriff_gefaltet(begriff)
    for zeichen in ("\\", "%", "_"):
        maskiert = maskiert.replace(zeichen, "\\" + zeichen)
    muster = f"{maskiert}%"
    like = " LIKE :muster ESCAPE '\\'"
    vorname = _suche_faltung("mitglied.vorname")
    nachname = _suche_faltung("mitglied.nachname")
    phrase = _suche_faltung(
        "COALESCE(mitglied.vorname, '') || ' ' || COALESCE(mitglied.nachname, '')")
    return text(
        f"({vorname}{like} OR {nachname}{like} OR {phrase}{like})"
    ).bindparams(muster=muster)


def _anzeigename_aus_zeile(zeile, mitglied: str) -> str:
    """Anzeigename aus einer Kandidatenzeile (``vorname``/``nachname``).

    Dieselbe Anzeige wie ``_anzeigename_select`` / ``_personen`` („Vorname
    Nachname“, getrimmt); ohne Namen bleibt die Kennung — eine zweite
    Namensregel gibt es nicht.
    """
    vor = str(getattr(zeile, "vorname", None) or "").strip()
    nach = str(getattr(zeile, "nachname", None) or "").strip()
    return f"{vor} {nach}".strip() or str(mitglied)



# ── Endpunkte: Senden / Bearbeiten / Löschen ────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def senden(gespraech, text, antwort_auf=None, erwaehnt=None):
    """Nachricht senden (nur Text, ≤ 4 000 Zeichen, Absätze bleiben).

    Recht: ANLEGEN in der Einheit — jedes Mitglied darf senden (Konzept 2.2),
    Gäste nie (der Kern gibt Gästen kein Modul).

    Der Text wird NICHT getrimmt: Zeilenumbrüche und Einrückungen sind Inhalt.
    Geprüft wird nur, dass am Rand etwas steht und die Länge passt — gezählt
    werden ZEICHEN, nicht Bytes.

    ``antwort_auf`` muss eine Nachricht DESSELBEN Gesprächs sein (sonst könnte
    man fremde Gespräche zitieren) und für die sendende Person SICHTBAR: eine
    Nachricht von vor dem eigenen Eintritt (``_vor_eintritt``) ist auch hier
    404 — sonst gäbe die Sende-Antwort den Zitattext eines Inhalts heraus, den
    der Verlauf nicht zeigt.

    ``erwaehnt`` (CHAT-9a, Konzept S4): die ausdrückliche Liste der zu
    erwähnenden Beteiligten — MITGLIED-Kennungen, wie sie die Gesprächs-/
    Personen-APIs liefern (Liste oder JSON-Zeichenkette; ``{"mitglied": …}``
    wird ebenso gelesen). Der Server parst KEIN „@…“ aus dem Text. Je Kennung
    gilt (``_erwaehnungen_pruefen``): Beteiligte/r des Gesprächs, die/der die
    Nachricht lesen darf, nicht die sendende Person selbst. UNGÜLTIGE
    Kennungen werden STILL verworfen — kein Fehler, keine Auskunft darüber, ob
    es die Person gibt; Duplikate werden zusammengefasst, höchstens 20 zählen.
    Je gespeicherter Erwähnung entsteht eine EIGENE Glocke (nicht gebündelt,
    keine Mail, auch bei stumm geschaltetem Gespräch) — AUSSER es besteht eine
    Kontaktsperre: dann wird die Erwähnung gespeichert, aber nicht geklingelt
    (eine Sperre darf nie erkennbar sein).
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    inhalt = _pruefe_text(text)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.ANLEGEN, g=g, sitzung=s)
        ziel = None
        if antwort_auf not in (None, ""):
            ziel = _nachricht(s, str(antwort_auf), g.name)
            # CHAT-7b-2 R1 (MUSS 1): dieselbe Grenze wie Zitat/Reaktion/
            # Lesestand — „nicht sichtbar“ ist „gibt es nicht“.
            if _vor_eintritt(s, g, benutzer, ziel.erstellt_am):
                raise DoesNotExistError("Nachricht nicht gefunden.")
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
        # CHAT-9a: prüfen, speichern, glocken — EINE Stelle. Die Antwort
        # zeigt dieselbe Liste wie der Verlauf (nur die gültigen).
        _erwaehnungen_speichern(s, zeile, g, benutzer, erwaehnt)
        return _zeile(s, zeile, antwort_auf=_zitat(s, ziel) if ziel else None,
                      namen=_personen(s, {zeile.autor}),
                      konto_namen=_konto_namen(s, {zeile.autor_benutzer}),
                      erwaehnungen=_erwaehnungen_laden(s, [zeile.name], benutzer),
                      ich=benutzer)


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
        if n.vorschlag:
            # Systemhinweis (SOLL 8): kein Beitrag einer Person — nicht
            # bearbeitbar. Geändert würde ohnehin nur die Vorschlagszeile.
            throw("Ein Systemhinweis lässt sich nicht bearbeiten.")
        g = _gespraech_lesen(s, n.gespraech)
        # Die Besitzfrage entscheidet der Rechte-KERN — durchgereicht wird das
        # KONTO der Nachricht. Bearbeiten ist keine Moderationshandlung: eine
        # fremde Nachricht entfernt man, man schreibt sie nicht um (der Kern
        # liesse es der Leitung durchgehen, deshalb zusaetzlich die Pruefung
        # „ist es meine“).
        if not _ist_meine(n, benutzer):
            _h()
        _erlaube(benutzer, rechte.SCHREIBEN, g=g,
                 besitzer=n.autor_benutzer, sitzung=s)
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

    im 1:1 gilt EINE Regel ohne Sonderzweig je ``art`` (Review CHAT-7a,
    Punkt 3): ``_erlaube(SCHREIBEN, besitzer=autor)`` — der Kern antwortet für
    eine fremde Nachricht ``fremde_nachricht`` (403), auch für einen
    TEILNEHMENDEN Administrator. Moderation im 1:1 gibt es nur über
    ``meldung_entscheiden``; die Meldestelle ist dort nicht Teilnehmerin.

    Der Text bleibt in der Datenbank (Widerspruchsfälle, CHAT-6/8), wird aber
    nicht mehr ausgeliefert: ``text=None``, ``geloescht=True``. Zweites Löschen
    ist kein Fehler (idempotent) — der Zeitpunkt des ersten bleibt stehen.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        if n.vorschlag:
            # Systemhinweis (SOLL 8): es gibt keine Person, die ihn geschrieben
            # hätte — und keinen Text, der verschwinden könnte.
            throw("Ein Systemhinweis lässt sich nicht löschen.")
        if _ist_meine(n, benutzer):
            # Eigene Nachricht loeschen = SCHREIBEN. Eine FREMDDE im 1:1 ist
            # damit NEIN (der Kern: ``fremde_nachricht``), auch fuer einen
            # teilnehmenden Admin — MODERIEREN gibt es im Direktgespraech nur
            # auf dem Meldeweg (``meldung_entscheiden``).
            _erlaube(benutzer, rechte.SCHREIBEN, g=g,
                     besitzer=n.autor_benutzer, sitzung=s)
        elif g.art in (ART_DIREKT, ART_RUNDE):
            # Dieselbe Frage, keine Sonderregel: der Kern sagt „fremde
            # Nachricht“ (teilnehmender Admin ebenso wie ein Dritter).
            # ``besitzer`` ist IMMER eine Zeichenkette: der Kern liest
            # ``besitzer is None`` als „eigene“ — nach der Anonymisierung ist
            # ``autor_benutzer`` aber NULL, und ohne diese Umwandlung duerfte
            # die verbliebene Person die Nachricht der geloeschten loeschen
            # (Review CHAT-N1, MUSS 2). ``""`` ist nie ein Konto.
            # CHAT-7b (Review R1): in einer RUNDE gilt dieselbe Regel — eine
            # fremde Nachricht ist dort SCHREIBEN mit fremdem Besitzer (NEIN),
            # Moderation gibt es nur auf dem Meldeweg.
            _erlaube(benutzer, rechte.SCHREIBEN, g=g,
                     besitzer=str(n.autor_benutzer or ""), sitzung=s)
        else:
            _erlaube(benutzer, rechte.MODERIEREN, g=g, sitzung=s)
        if n.geloescht_am is None:
            n.geloescht_am = _jetzt()
            n.geloescht_von = benutzer
            # CHAT-9a: mit der Nachricht verschwinden ihre Erwähnungen, und
            # eine offene Erwähnungs-Glocke wird als gelesen gestellt — sie
            # führte sonst auf eine Lücke im Verlauf. Dasselbe Muster wie bei
            # einer entfernten Nachricht (die Glockenzeile bleibt als
            # Nachweis stehen, nur ``read`` wird gesetzt).
            _nachricht_erwaehnungen_raeumen(s, n.name)
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
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
        # CHAT-7b-2 (SOLL 2): eine Nachricht von VOR dem eigenen Eintritt in
        # die Runde ist für diese Person nicht da — 404, wie eine unbekannte
        # Kennung (die Reaktion darf den Inhalt nicht bestätigen).
        if _vor_eintritt(s, g, benutzer, n.erstellt_am):
            raise DoesNotExistError("Nachricht nicht gefunden.")
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
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
        teilnahme = _teilnahme(s, g.name, benutzer)
        if nachricht not in (None, ""):
            ziel = _nachricht(s, str(nachricht), g.name)
            # CHAT-7b-2 (SOLL 2): der Anker muss für DIESE Person sichtbar
            # sein. Ein Lesestand auf einer Nachricht von vor dem eigenen
            # Eintritt wäre eine Aussage über einen Inhalt, den es für sie
            # nicht gibt → 404 über dieselbe Grenze (``_vor_eintritt``).
            if _vor_eintritt(s, g, benutzer, ziel.erstellt_am):
                raise DoesNotExistError("Nachricht nicht gefunden.")
        else:
            # Ohne Anker: bis zur neuesten Nachricht, die für diese Person
            # sichtbar ist (dieselbe Grenze wie im Verlauf) — vor dem Eintritt
            # gibt es keinen Lesestand zu setzen, dann bleibt `ziel` None.
            bedingung = [ChatNachricht.gespraech == g.name]
            sichtbar_ab = _sichtbar_ab(s, g, benutzer)
            if sichtbar_ab is not None:
                bedingung.append(ChatNachricht.erstellt_am >= sichtbar_ab)
            ziel = s.execute(
                select(ChatNachricht).where(*bedingung)
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
        # lässt die Glocke stehen (Reviews R1/d) — CHAT-4b schreibt sie dann
        # sofort mit der neuen Zahl fort (Restpunkt b: ``merker_am`` hätte den
        # nächsten Joblauf sonst blockiert, die Glocke zeigte ewig „3 neue“).
        ungelesen = _ungelesen_zaehlen(s, g.name, benutzer, teilnahme)
        _glocke_als_gelesen(s, g.name, benutzer, alles_gelesen=(ungelesen == 0),
                            ungelesen=ungelesen)
        # CHAT-9a: die ERWÄHNUNGS-Glocken bis hierhin als gelesen — analog zum
        # Lesestand, über die Position im Verlauf (Zeitstempel + Kennung).
        # Nichts anderes als „diese Nachricht und alles davor“.
        _erwaehnung_glocken_als_gelesen(s, g.name, benutzer, ziel.name if ziel else None)
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
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
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

    CHAT-4b — Start-Glocke: nach dem Commit bekommt JEDE Person, die das
    Gespräch lesen darf, eine Glocke „Neue Umfrage im <Titel>“ — außer der/dem
    Anlegenden und den stumm geschalteten. Siehe ``_glocke_neue_umfrage``.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    inhalt = _pruefe_frage(frage)
    auswahl = _pruefe_optionen(optionen)
    frist_am = _frist_lesen(frist)
    gespraech_titel = ""
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.ANLEGEN, g=g, sitzung=s)
        gespraech_titel = _glocken_titel(g)
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
        daten = _umfrage_daten(s, umfrage, benutzer, g)
        # Die Kennung INNERHALB der Sitzung merken: nach dem `begin()`-Block
        # wird die Instanz detached, und ein Attributzugriff darauf löst
        # ``DetachedInstanceError`` aus (im Zwischenstand passiert).
        nachricht_name = zeile.name
        gespraech_name = g.name
        umfrage_name = umfrage.name
    # Nach dem Commit — wie ``meldung_senden``: der Empfängerkreis wird in
    # einer EIGENEN Sitzung bestimmt (er sieht dann genau die Umfrage, die
    # gerade festgeschrieben wurde). Die UMFRAGE wird über ihre Kennung neu
    # geladen (Review R1/2): so hängt die Start-Glocke sicher an DIESER
    # Umfrage und nicht an „der neuesten des Gesprächs“.
    # Die Umfrage IST gespeichert: ein Fehler beim Benachrichtigen darf den
    # Aufruf nie mit 500 enden lassen (sonst legt der Client sie erneut an).
    try:
        with dbmod.SessionLocal.begin() as s2, als_aktuelle_sitzung(s2):
            umfrage_frisch = s2.get(ChatUmfrage, umfrage_name)
            gespraech_frisch = s2.get(ChatGespraech, gespraech_name)
            if umfrage_frisch is not None and gespraech_frisch is not None:
                _glocke_neue_umfrage(s2, umfrage_frisch, gespraech_frisch,
                                     gespraech_titel, benutzer)
    except Exception:
        logger.exception("umfrage_anlegen: Start-Glocke zu %s nicht geschrieben",
                         umfrage_name)
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
        u, g = _umfrage_lesen(s, umfrage, benutzer)
        _erlaube(benutzer, rechte.ANLEGEN, g=g, sitzung=s)
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
        return _umfrage_daten(s, u, benutzer, g)


@whitelist(methods=["POST"], allow_guest=False)
def umfrage_schliessen(umfrage):
    """Umfrage vorzeitig schließen — ERSTELLER oder wer MODERIEREN darf.

    Recht: ZWEI Wege, beide über den Rechte-Kern:
      * der Ersteller (die Nachricht gehört ihm → SCHREIBEN mit eigenem
        Besitzer),
      * sonst MODERIEREN im Gespräch (HV/MV, in der Untergruppe auch GL).

    Im 1:1 gibt es KEINEN Sonderzweig je ``art`` (Review CHAT-7a, Punkt 3):
    dort gilt ``_erlaube(SCHREIBEN, besitzer=autor)``, und der Kern antwortet
    für eine fremde Umfrage ``fremde_nachricht`` (403) — auch für einen
    teilnehmenden Administrator. Moderation im 1:1 gibt es nur über
    ``meldung_entscheiden``.

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
        u, g = _umfrage_lesen(s, umfrage, benutzer)
        autor = _umfrage_autor(s, u.name)
        # Dieselben Zweige wie `darf_schliessen` in der Antwort (CHAT-5-UI) —
        # EINE Stelle: `_schliessen_erlaube`, hier mit Wurf statt Wahrheitswert.
        _schliessen_erlaube(s, g, autor, benutzer)
        if u.geschlossen_am is None:
            u.geschlossen_am = _jetzt()
            u.geschlossen_von = benutzer or None
            s.flush()
        return _umfrage_daten(s, u, benutzer, g)


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
        u, g = _umfrage_lesen(s, umfrage, benutzer)
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
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


def _umfragen_laden(s, kennungen, benutzer: str,
                    gespraech: ChatGespraech | None = None) -> dict[str, dict[str, Any]]:
    """Die Umfragedaten zu einer SEITE Nachrichten — in fester Zahl Abfragen.

    Vier Abfragen für die ganze Seite (Umfragen, Optionen, eigene Stimmen,
    eigene Abgaben) — keine je Nachricht. Das ist die Zusage aus der Karte
    „ohne N+1“.

    ``darf_schliessen`` (CHAT-5-UI) kommt für die GANZE Seite aus
    ``_darf_schliessen_je_umfrage``: EINE Moderationsfrage, keine je Zeile. Ist
    ``gespraech`` nicht übergeben, bleibt es ``False`` (der Aufrufer bestimmt
    den Kontext; die Endpunkte Anlegen/Abstimmen liefern es eigens).

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
        # Namen und Mitglied-Kennungen für die GANZE Seite holen (je EINE
        # Abfrage), nicht je Umfrage: sonst hinge die Zahl der Abfragen an
        # der Zahl der Umfragen auf der Seite (Review CHAT-5-UI R2, SOLL 1).
        konten = {str(k) for _, _, k in stimmen if k}
        mitglied_je_konto = _mitglieder_je_konto(s, konten)
        anzeige = _personen(s, set(mitglied_je_konto.values()))
        konto_anzeige = _konto_namen(s, konten)
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

    darf_schliessen = _darf_schliessen_je_umfrage(s, gespraech, list(umfragen), benutzer)

    return {
        kennung: _umfrage_form(u, optionen.get(kennung, []), benutzer,
                               eigene_stimmen.get(kennung, []),
                               kennung in eigene_abgabe,
                               namen_je_option, abgegeben.get(kennung, 0),
                               darf_schliessen=darf_schliessen.get(kennung, False))
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
                  abgegeben: int = 0, *, darf_schliessen: bool = False) -> dict[str, Any]:
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
        # CHAT-5-UI: darf DIESE Sitzung diese Umfrage schließen? Aus dem
        # Rechte-Kern (dieselben Zweige wie `umfrage_schliessen`); die
        # Oberfläche blendet den Knopf nur daran aus.
        "darf_schliessen": bool(darf_schliessen),
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


def _schliessen_erlaube(s, g: ChatGespraech, autor: str | None, benutzer: str) -> None:
    """DIE Zweige von ``umfrage_schliessen`` — auch Quelle für ``darf_schliessen``.

    EINE Stelle: der Endpunkt wirft hier, ``_darf_umfrage_schliessen`` fragt
    dieselbe Funktion als Wahrheitswert. Drei Fälle, alle über den Rechte-Kern
    (keine eigene Rollenlogik):

      * eigene Umfrage (die Hülle-Nachricht gehört ``benutzer``) → SCHREIBEN
        mit ``besitzer=autor``,
      * fremde Umfrage im DIREKTGESPRÄCH → dieselbe Frage, GLEICHE Umwandlung
        ``str(autor or "")`` wie beim Löschen (Review CHAT-N1, MUSS 2): nach
        einer Anonymisierung hat die Hülle kein Konto mehr (``None``) — der
        Kern läse das als „eigene“ und die verbliebene Person dürfte die
        fremde Umfrage schließen,
      * sonst → MODERIEREN im Gespräch.

    Kein Sonderzweig je ``art`` außer dem 1:1 (Review CHAT-7a, Punkt 3): dort
    gibt es keine Moderation über das Gespräch, nur über
    ``meldung_entscheiden``. CHAT-7b (Review R1): dasselbe gilt in einer RUNDE
    (``g.art in (ART_DIREKT, ART_RUNDE)``) — ``besitzer`` als Zeichenkette,
    damit eine anonymisierte Hülle nicht als „eigene“ durchgeht.
    """
    if autor and str(autor) == str(benutzer or ""):
        _erlaube(benutzer, rechte.SCHREIBEN, g=g, besitzer=autor, sitzung=s)
    elif g.art in (ART_DIREKT, ART_RUNDE):
        _erlaube(benutzer, rechte.SCHREIBEN, g=g, besitzer=str(autor or ""), sitzung=s)
    else:
        _erlaube(benutzer, rechte.MODERIEREN, g=g, sitzung=s)


def _darf_umfrage_schliessen(s, g: ChatGespraech, autor: str | None,
                             benutzer: str) -> bool:
    """Darf ``benutzer`` DIESE Umfrage schließen? — ``_schliessen_erlaube`` als
    Wahrheitswert (``_weiche_ja``).

    Die eigene Umfrage ist über ``benutzer``/``autor`` erkennbar; die Frage
    geht trotzdem durch die Zweige, damit Anzeige und Endpunkt nicht
    auseinanderlaufen können.
    """
    try:
        _schliessen_erlaube(s, g, autor, benutzer)
    except PermissionError:
        return False
    return True


def _darf_schliessen_je_umfrage(s, g: ChatGespraech | None, umfragen, benutzer: str
                                ) -> dict[str, bool]:
    """``{umfrage: darf_schliessen}`` für eine SEITE — ohne N+1.

    DREI Fälle, je Seite EINE Rechtefrage (statt einer je Zeile):

      * eigene Umfragen → ``_schliessen_erlaube`` mit dem eigenen Konto (der
        Ersteller-Zweig: SCHREIBEN auf der eigenen Nachricht — für JEDE Person
        an ihrer eigenen Umfrage dasselbe Ergebnis, darum einmal),
      * fremde Umfragen im 1:1 → derselbe Zweig mit ``besitzer=str(autor or "")``;
        das Ergebnis hängt an der Person, nicht an der Umfrage → einmal,
      * fremde Umfragen sonst → EINE Moderationsfrage für die ganze Seite.

    Die Zweige sind DIESELBEN wie in ``umfrage_schliessen``
    (``_schliessen_erlaube``) — Anzeige und Endpunkt können nicht
    auseinanderlaufen.

    ``g=None`` (kein Gespräch zur Hand) → alles ``False``: ohne Gespräch keine
    Moderationsfrage, und der Ersteller-Zweig braucht es nicht.
    """
    kennungen = [str(k) for k in umfragen if k]
    if not kennungen:
        return {}
    if g is None:
        return {kennung: False for kennung in kennungen}
    autoren: dict[str, str | None] = {}
    for name, autor in s.execute(
        select(ChatNachricht.umfrage, ChatNachricht.autor_benutzer)
        .where(ChatNachricht.umfrage.in_(kennungen))
    ).all():
        autoren[str(name)] = autor

    eigene = [k for k in kennungen if _ist_eigene_umfrage(autoren.get(k), benutzer)]
    fremde = [k for k in kennungen if k not in eigene]
    # 1:1 UND Runde (CHAT-7b): dort gibt es keine Moderation über das Gespräch,
    # nur den Meldeweg — für fremde Umfragen gilt deshalb dieselbe
    # Besitzer-Frage wie bei Nachrichten (Besitzer als Zeichenkette).
    direkt = str(g.art or "") in (ART_DIREKT, ART_RUNDE)

    # Je Fall EINE Frage — nicht je Umfrage.
    eigene_darf = (bool(eigene)
                   and _darf_umfrage_schliessen(s, g, benutzer, benutzer))
    fremd_direkt_darf = False
    # Im 1:1: dieselbe Frage, Besitzer ist das (ggf. anonymisierte) Konto des
    # Erstellers — ``str(autor or "")`` wie beim Löschen (CHAT-N1, MUSS 2).
    if fremde and direkt:
        erster_autor = next((autoren.get(k) for k in fremde), None)
        fremd_direkt_darf = _darf_umfrage_schliessen(
            s, g, str(erster_autor or ""), benutzer)
    # Gruppe: EINE Moderationsfrage für alle fremden Umfragen der Seite.
    moderation = (bool(fremde) and not direkt
                  and _weiche_ja(benutzer, rechte.MODERIEREN, g=g, sitzung=s))

    ergebnis: dict[str, bool] = {}
    for kennung in kennungen:
        if kennung in eigene:
            ergebnis[kennung] = eigene_darf
        elif direkt:
            ergebnis[kennung] = fremd_direkt_darf
        else:
            ergebnis[kennung] = moderation
    return ergebnis


def _ist_eigene_umfrage(autor: str | None, benutzer: str) -> bool:
    """Gehört die Umfrage dieser Person? — verglichen wird das KONTO."""
    return bool(autor) and str(autor) == str(benutzer or "")


def _umfrage_daten(s, u: ChatUmfrage, benutzer: str,
                   g: ChatGespraech | None = None) -> dict[str, Any]:
    """Die Umfragedaten EINER Umfrage (Anlegen, Abstimmen, Ergebnis, Schließen).

    ``daten["darf_schliessen"]`` (CHAT-5-UI) sagt, ob DIESE Sitzung schließen
    darf — EINE Frage an dieselbe Hilfsfunktion, die ``umfrage_schliessen``
    benutzt. Ohne ``g`` wird das Gespräch gelesen (die Antwort soll den Knopf
    zeigen können).
    """
    if g is None:
        g = _gespraech_lesen(s, u.gespraech)
    autor = _umfrage_autor(s, u.name)
    darf_schliessen = _darf_umfrage_schliessen(s, g, autor, benutzer)
    daten = _umfragen_laden(s, [u.name], benutzer).get(str(u.name))
    if daten is not None:
        daten["darf_schliessen"] = bool(darf_schliessen)
        return daten
    # Keine Optionen (darf nicht vorkommen) — trotzdem eine ganze Antwortform.
    return _umfrage_form(u, [], benutzer, [], False, {}, 0,
                         darf_schliessen=darf_schliessen)


def _umfrage_lesen(s, umfrage: str,
                   benutzer: str | None) -> tuple[ChatUmfrage, ChatGespraech]:
    """Umfrage + ihr Gespräch per Kennung; unbekannt → 404 (nichts raten).

    Eine Umfrage lebt NUR als Nachricht im Verlauf: ist die Hülle-Nachricht
    gelöscht (selbst gelöscht oder von der Moderation entfernt), ist die
    Umfrage für ALLE Wege weg — Abstimmen, Ergebnis, Schließen. Sonst nähme
    eine entfernte Umfrage weiter Stimmen an und lieferte bei einer offenen
    Umfrage sogar Namen. Wie bei einer unbekannten Kennung: 404, nicht 403 —
    die Kennung allein soll nichts über ihren Inhalt verraten.

    CHAT-7b-2 (MUSS 1b): dasselbe gilt, wenn die Hülle für die fragende
    Person VOR ihrem Eintritt in die Runde liegt (``_vor_eintritt``). Die
    Umfrage ist ein Inhalt im Verlauf; was im Verlauf nicht sichtbar ist, ist
    über diesen Weg auch nicht abstimmbar, lesbar oder schließbar. ``benutzer``
    ist deshalb Pflicht (kein Vorgabewert): „niemand“ (``None``) prüft fail
    closed gegen jede gesetzte Grenze, ein stiller Vorgabewert ``None`` wäre
    aber fail OPEN für jeden vergessenen Aufrufer.
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
    if _vor_eintritt(s, gespraech, benutzer, huelle.erstellt_am):
        raise DoesNotExistError("Umfrage nicht gefunden.")
    return zeile, gespraech


def _umfrage_nachricht(s, umfrage: str) -> ChatNachricht | None:
    """Die Nachricht, an der die Umfrage hängt (für Besitz und Anzeige)."""
    return s.execute(
        select(ChatNachricht).where(ChatNachricht.umfrage == umfrage)
    ).scalars().first()


def _umfrage_autor(s, umfrage: str) -> str | None:
    """Das KONTO, das die Umfrage gestartet hat (Besitz = die Hülle-Nachricht).

    Nimmt die KENNUNG der Umfrage (nicht die Instanz): aufgerufen aus
    ``umfrage_schliessen`` und ``_umfrage_daten``, wo nur ``u`` bzw. der Name
    zur Hand ist.
    """
    n = _umfrage_nachricht(s, umfrage)
    return n.autor_benutzer if n is not None else None


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
        _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
        # CHAT-7b-2 (SOLL 2): eine Nachricht von VOR dem eigenen Eintritt ist
        # für diese Person nicht sichtbar → 404 (dieselbe Antwort wie für eine
        # unbekannte Kennung; die Meldung darf den Inhalt nicht bestätigen).
        if _vor_eintritt(s, g, benutzer, n.erstellt_am):
            raise DoesNotExistError("Nachricht nicht gefunden.")
        if _ist_meine(n, benutzer):
            throw("Die eigene Nachricht lässt sich nicht melden.")
        if n.geloescht_am is not None:
            throw("Eine gelöschte Nachricht lässt sich nicht melden.")
        if n.vorschlag:
            # CHAT-7b (Review R1, SOLL 8): ein Systemhinweis („X möchte Y
            # hinzufügen“) ist kein Beitrag einer Person — es gibt niemanden,
            # über den zu entscheiden wäre. Wer den Vorgang nicht will, lehnt
            # den Vorschlag ab (``runde_ablehnen``).
            throw("Ein Systemhinweis lässt sich nicht melden.")
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
        empfaenger = [k for k in _moderation_konten(g, sitzung=s)
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
        # CHAT-7a: Meldungen aus DIREKTGESPRÄCHEN gehören der Meldestelle
        # (F7: Administrator). ``chat_moderatoren`` fragt Gruppenrollen und
        # liefert für ein 1:1 nichts — ohne diesen Zweig bekäme der
        # Administrator die Meldung als Glocke, aber nie in die Liste.
        # Gefragt wird die WEICHE, nicht ``rechte.ist_meldestelle``: MODERIEREN
        # ist im 1:1 die Meldestelle, in der Gruppe die Leitung — der Kern
        # beantwortet das je ``art``, hier steht keine zweite Rechtefrage.
        # ``meldeweg=True``: DAS hier ist einer der Meldewege (MUSS 1).
        # CHAT-7b: Runden zählen ebenfalls als Meldeweg (Entscheidung des
        # Operators), aber NICHT in der Leitungs-Schleife unten — dort würde
        # ``chat_moderatoren`` auf `gruppe = NULL` gefragt (MUSS 10).
        meldestelle = _weiche_ja(benutzer, rechte.MODERIEREN, direkt=True,
                                 meldeweg=True)

        # 2) Je Kandidat EINE Rechtefrage über den Rechte-Kern (`_erlaube`),
        #    nichts Eigenes. Gefragt wird nur nach den Gesprächen, in denen
        #    Meldungen liegen.
        eigene: dict[str, ChatGespraech] = {}
        for kennung in kandidaten:
            try:
                g = _gespraech_lesen(s, kennung)
            except DoesNotExistError:
                continue          # Gespräch zwischenzeitlich weg — kein Kandidat
            # Kein Sonderzweig je ``art``: die Weiche fragt den Kern, und der
            # kennt beide Arten (1:1 → Meldestelle, Gruppe → Leitung).
            if _darf_moderieren(benutzer, g, sitzung=s, meldeweg=True):
                eigene[g.name] = g
        if not eigene:
            # 3) Keiner der Kandidaten ist moderierbar. Jetzt erst entscheidet
            #    sich „[] vs 403“: gibt es überhaupt ein moderierbares
            #    Gespräch? Mit frühem Abbruch beim ersten „ja“ — der Normalfall
            #    (Leitung hat ein Gespräch) kostet keinen zweiten Durchlauf.
            # Direktgespraeche nicht durchlaufen (O(Paare)): fuer sie steht
            # unten der Meldestellen-Zweig. RUNDEN ebenso (CHAT-7b, MUSS 10):
            # sie haben keine Gruppe, ``chat_moderatoren`` liefe ins Leere —
            # ihre Meldungen gehören der Meldestelle (Zweig unten).
            rest = s.execute(
                select(ChatGespraech)
                .where(ChatGespraech.geloescht_am.is_(None),
                       or_(ChatGespraech.art.is_(None),
                           ChatGespraech.art.notin_((ART_DIREKT, ART_RUNDE))))
                .order_by(ChatGespraech.name)
            ).scalars()
            vorhanden_ja = False
            for g in rest:
                if nur_gespraech and g.name != nur_gespraech:
                    continue
                if _darf_moderieren(benutzer, g, sitzung=s, meldeweg=True):
                    vorhanden_ja = True
                    break
            # CHAT-7a: die Meldestelle darf DIREKTGESPRÄCHE moderieren, ohne
            # dass eines davon schon existiert. Ohne diesen Zweig bekäme der
            # Administrator ohne Gruppenrolle 403 („gar kein moderierbares
            # Gespräch“) — obwohl die Glocke ihm die Meldung angekündigt hat.
            # CHAT-7b: für RUNDEN gilt dasselbe (MUSS 2/10).
            if not vorhanden_ja and meldestelle:
                direkt_da = s.execute(
                    select(ChatGespraech.name)
                    .join(ChatNachricht, ChatNachricht.gespraech == ChatGespraech.name)
                    .join(ChatMeldung, ChatMeldung.nachricht == ChatNachricht.name)
                    .where(ChatGespraech.art.in_((ART_DIREKT, ART_RUNDE)),
                           ChatGespraech.geloescht_am.is_(None))
                    .limit(1)
                ).scalar_one_or_none() is not None
                if (nur_gespraech is not None
                        and _wechselart_lesen(nur_gespraech, sitzung=s)
                        not in (ART_DIREKT, ART_RUNDE)):
                    # Auf EIN Gruppen-Gespräch eingegrenzt, und dort darf
                    # diese Person nicht moderieren → ehrliche 403.
                    _h()
                if direkt_da or not nur_gespraech:
                    return {"meldungen": [], "offen": 0}
                _h()
            if not vorhanden_ja:
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
        # Die EINE Weiche — auch hier. Im Direktgespräch ist MODERIEREN laut
        # Kern die MELDESTELLE (F7, ``ist_meldestelle``), in der Gruppe die
        # Leitung; ein eigener ``ist_meldestelle``-Aufruf wäre ein zweiter
        # Rechtepfad. Das ist die EINZIGE Stelle, an der im 1:1 moderiert wird.
        # ``meldeweg=True`` (Review CHAT-7b R1, MUSS 1): ohne das Flag antwortet
        # der Kern im 1:1/in der Runde ``nur_meldeweg`` — und die Meldestelle
        # könnte keine Meldung mehr entscheiden.
        _erlaube(benutzer, rechte.MODERIEREN, g=g, sitzung=s, meldeweg=True)
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
                # CHAT-9a: eine von der Moderation ENTFERNTE Nachricht trägt
                # keine Erwähnung mehr — und die offene Erwähnungs-Glocke wird
                # als gelesen gestellt (dasselbe Muster wie beim Löschen).
                _nachricht_erwaehnungen_raeumen(s, n.name)
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


def _darf_moderieren(benutzer: str, g: ChatGespraech, *, sitzung=None,
                     meldeweg: bool = False) -> bool:
    """Darf ``benutzer`` in DIESEM Gespräch moderieren? — über ``_erlaube``.

    EINE Rechtefrage für Liste und Entscheiden (Review Punkt 7): keine eigene
    Rollenlogik, kein zweiter Aufrufpfad. ``_weiche_ja`` macht aus dem Wurf ein
    ``False``, weil die Liste über VIELE Gespräche fragt und das erste „nein“
    nicht das Ende ist.

    CHAT-7a: Die Weiche entscheidet je ``art`` — im Direktgespräch ist
    MODERIEREN die MELDESTELLE (F7: Administrator), nicht die Gruppenleitung.
    CHAT-7b (Review R1, MUSS 1/2): Das gilt im 1:1 UND in der Runde NUR auf dem
    Meldeweg.

    CHAT-7b-2 (SOLL 7): Vorgabe ist deshalb ``meldeweg=False`` — die sichere
    Seite. Wer den MELDEWEG fragt (``meldungen_liste``,
    ``meldung_entscheiden``, ``_moderation_konten``), setzt ``meldeweg=True``
    ausdrücklich; ein neuer Aufrufer ohne Flag bekommt im 1:1/in der Runde
    ``nur_meldeweg`` (NEIN) statt still Moderation. Löschen und
    Umfrage-Schließen fragen ``_erlaube`` ohnehin direkt.
    """
    return _weiche_ja(benutzer, rechte.MODERIEREN, g=g, sitzung=sitzung,
                      meldeweg=meldeweg)


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
        # Im 1:1 NEUTRAL („Direktnachricht“) — der Gesprächstitel waere hier
        # der Name des Gegenuebers, und der gehoert nicht in die Meldungszeile.
        "gespraech_titel": _glocken_titel(g),
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


def _moderation_konten(g: ChatGespraech, *, sitzung=None) -> list[str]:
    """Wer bekommt die MELDUNGS-Glocke dieses Gesprächs (Konzept 2.5)?

    * Gruppen-Chat: ``rechte.chat_moderatoren(gruppe, untergruppe)`` —
      unverändert seit CHAT-6 (HV/MV, in der Untergruppe auch GL; der
      Administrator steht bewusst NICHT darin).
    * Direktgespräch (CHAT-7a): die MELDESTELLE (F7). Genau diese Person
      bekommt die Glocke und sieht die Meldung in der Liste — und NUR sie; die
      Gemeindeleitung sieht in einem 1:1 nichts (Konzept S3: „niemand sonst
      kann mitlesen“). Die Frage je Kandidat stellt ``_weiche_ja(... MODERIEREN)``
      (= der Kern) — hier steht keine eigene Rollenlogik.
    * Runde (CHAT-7b, Review R1 MUSS 2): dieselbe Regel wie im 1:1 — nur die
      Meldestelle. Ohne diesen Zweig liefe eine Runde in
      ``rechte.chat_moderatoren('' , None)`` und die Meldung erreichte NIEMANDEN.

    ``sitzung`` ist die Sitzung des AUFRUFERS und wird durchgereicht (Review
    CHAT-7a, Punkt 2): MODERIEREN wertet die Teilnehmenden im Kern NICHT aus
    (``darf_direktgespraech`` antwortet für MODERIEREN allein über
    ``ist_meldestelle``), also wird das Gespräch als Zeile übergeben statt als
    transientes ``ChatGespraech(...)`` — und es entsteht keine eigene Sitzung
    je Kandidat. ``meldeweg=True`` ist gesetzt: DAS hier IST der Meldeweg.
    """
    if g.art in (ART_DIREKT, ART_RUNDE):
        return sorted(k for k in _meldestellen_konten() if _weiche_ja(
            k, rechte.MODERIEREN, g=g, sitzung=sitzung, meldeweg=True))
    return list(rechte.chat_moderatoren(g.gruppe, g.untergruppe))


def _meldestellen_konten() -> list[str]:
    """KANDIDATEN für die Meldestelle (F7) — per SQL, danach der Kern-Recheck.

    Nicht jedes aktive Konto durch den Rechte-Kern schicken: ``ist_admin`` gilt
    für ``Administrator``, den eingetragenen root und Konten mit der Rolle
    ``System Manager``. Genau diese holt EINE Abfrage; ob sie es wirklich sind,
    entscheidet danach ``_weiche_ja(... MODERIEREN)`` — die Liste ist Vorfilter,
    KEINE Entscheidung (dieselbe Trennung wie bei der Personensuche).

    ROLLENNAMEN sind KEINE Konten (Review CHAT-7a, Punkt 1): ``"System
    Manager"`` und ``ROOT_ROLLE`` stehen als ``role`` in ``HasRole``, nicht als
    ``parent`` — als Konto-Kandidat wären sie eine Zeile, die der Kern
    anschließend gar nicht kennt (er fragt ``User``). Kandidaten sind deshalb
    nur ``parent``-Werte der Rollenzeilen, der eingetragene root und das Konto
    ``Administrator``.

    ``Administrator`` steht auch OHNE eigene ``User``-Zeile in der Liste
    (dieselbe Entscheidung des Operators, Review CHAT-7a Punkt 1): der Kern
    gilt für dieses eine Konto wahr — er nennt es ausdrücklich, ohne
    Rollenzeile (``ist_admin``) und ohne User-Zeile
    (``_ist_angemeldetes_mitglied``). Die Aktiv-Prüfung der Rollen-Kandidaten
    gilt deshalb nur für Konten, die OHNE ihn gefunden wurden — und ein
    AUSGESCHLOSSENES Konto fällt auch dann heraus (``mitglied_ausgeschlossen``;
    der Kern gäbe ihm keine Rolle). Für alle anderen bleibt die Regel „nur
    Konten, die es gibt und die aktiv sind“.

    CHAT-N2 — EINMAL je Anfrage: der Ausschluss-Zustand wird hier genau EINMAL
    gelesen (``_ausgeschlossene_konten(*_kontozustand())``) und die
    Kandidatenliste damit gefiltert. Vorher lief je Kandidat ein Volllauf über
    Mitglied/User. Dieselbe Schranke wie im Kern, also auch für ein Konto, das
    erst über die E-Mail zu einem ausgeschlossenen Mitglied gehört
    (``wirksame_konten``).

    ``parenttype`` wird bewusst NICHT auf ``User`` verengt: Altdaten-Zeilen
    ohne parenttype gelten im Kern als Benutzer-Rollen (``ist_user_zeile``),
    eine zu enge Abfrage würde die Kandidatenliste leeren. Bleibt sie LEER,
    bleibt es bei „niemand“ — fail closed, wie der Kern.
    """
    from diakronos_app.frappe_compat.benutzer_status import (
        _ausgeschlossene_konten,
        _kontozustand,
    )
    from diakronos_app.frappe_compat.permissions import ROOT_ROLLE
    from diakronos_app.models.core import HasRole, User

    konten: set[str] = set()
    # Die Sitzung des Aufrufers, wenn es eine gibt (``dbmod.lesesitzung``):
    # diese Funktion kann in einer Schreibtransaktion laufen, und eine zweite
    # Sitzung auf derselben Verbindung risse sie mit (Review CHAT-N1, SOLL).
    with dbmod.lesesitzung() as s:
        konten |= {str(k) for k in s.execute(
            select(HasRole.parent).where(
                HasRole.role.in_((*rechte.ADMIN_ROLLEN, ROOT_ROLLE)))
        ).scalars().all() if k}
        try:
            from diakronos_app import root_benutzer

            eingetragen = root_benutzer.root_name()
        except Exception:  # noqa: BLE001 — kein root bei Lesefehler (fail closed)
            eingetragen = None
        if eingetragen:
            konten.add(str(eingetragen))
        # Nur KONTEN, die es gibt und die aktiv sind (der Kern prüft dasselbe).
        aktiv = {str(k) for k in s.execute(
            select(User.name).where(User.name.in_(sorted(konten)),
                                    User.enabled.is_(True))
        ).scalars().all() if k}
    # ``Administrator`` ist der Systembenutzer und braucht keine eigene Zeile —
    # der Kern bestätigt ihn auch ohne (``ist_admin`` fragt genau diesen Namen).
    # Ob er Meldestelle IST, sagt danach ohnehin ``_weiche_ja(... MODERIEREN)``.
    if MELDESTELLE_KONTO:
        aktiv.add(MELDESTELLE_KONTO)
    # Ein ausgeschlossenes Konto bekommt im Kern keine Rolle — es fällt hier
    # schon heraus. Der Zustand wird dafür EINMAL gelesen (CHAT-N2), nicht je
    # Kandidat: dieselbe Schranke (``mitglied_ausgeschlossen``) für alle.
    aus = _ausgeschlossene_konten(*_kontozustand())
    return sorted(k for k in aktiv if k not in aus)


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

    ``titel`` ist der NEUTRALE Betreff aus ``_glocken_titel`` — im
    Direktgespräch also „Direktnachricht“, nie der Name des Gegenübers.
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
    """Titel der Glocke: im 1:1 NEUTRAL, sonst Gesprächstitel, sonst Einheit.

    Ein Direktgespräch hat weder ``titel`` noch ``untergruppe``/``gruppe``
    (beide NULL) — ohne eigenen Zweig hieße die Glocke „None: 1 neue
    Nachricht“. Und der Gesprächstitel eines 1:1 IST der Name des Gegenübers:
    der darf in der Glocke nicht stehen (CHAT-4a: „kein Absendername“).
    Deshalb ein fester Betreff ohne jede Personenangabe. Fehlen bei einem
    Gruppengespräch Titel und Einheit, gilt derselbe neutrale Rückfall —
    nie „None“ oder ein leerer Text in der Glocke (CHAT-4b R1).
    """
    if g.art == ART_DIREKT:
        return DIREKT_GLOCKE_TITEL
    titel = str(g.titel or "").strip()
    if g.art == ART_RUNDE:
        # CHAT-7b: „Runde <Titel>“ — ohne Absendernamen (derselbe Grund wie im
        # 1:1). Fehlt der Name einer Altzeile, bleibt es beim neutralen
        # Rückfall; ein leerer Rundenname entsteht über den Endpunkt nie.
        return f"Runde {titel}" if titel else "Runde"
    if titel:
        return titel
    return str(g.untergruppe or g.gruppe or "").strip() or DIREKT_GLOCKE_TITEL


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
                   jetzt: datetime,
                   nur_fortschreiben: bool = False,
                   nur_zahl: bool = False) -> bool:
    """Die EINE Glocke je (Gespräch, Konto) schreiben — ersetzen statt doppeln.

    Liegt im ``Notification Log`` schon eine UNGELESENE Chat-Glocke desselben
    Gesprächs, wird sie AKTUALISIERT (Betreff, Inhalt). Sonst entsteht eine
    neue Zeile — AUSSER mit ``nur_fortschreiben``: dann wird keine angelegt
    (Review R1/4, Fall „die Person hat die Glocke weggeklickt“) und die
    Rückgabe ist ``False``.

    ``nur_zahl`` (Review CHAT-7a, Punkt 6): nur die ZAHL fortschreiben, NICHT
    ``modified``. Beim teilweisen Lesen soll die Glocke in der Liste an ihrem
    Platz bleiben — sie nach oben zu schieben ist allein Sache neuer
    Nachrichten. Die Uhr ``jetzt`` wird deshalb nur im Merker vermerkt.

    Der Merker wird NUR fortgeschrieben, wenn die Glocke wirklich stand (der
    Rückgabewert von ``glocke_setzen`` ist leer, wenn das Schreiben scheiterte)
    — sonst ginge die Nachricht still verloren, weil der nächste Lauf sie als
    „schon geglockt“ ansähe. ``merker_am`` = die neueste Nachricht, die jetzt
    schon da ist; damit ist dieselbe Nachricht beim nächsten Lauf nicht wieder
    „neu“, auch wenn sie (noch) nicht gelesen wurde.
    """
    from diakronos_app.benachrichtigungen import glocke_setzen

    titel = _glocken_titel(gespraech)
    betreff = _glocken_text(titel, anzahl)
    hinweis = _glocken_hinweis(anzahl)
    # ``document_name`` ist das GESPRÄCH: darüber findet ``lesestand_setzen``
    # die Glocke wieder, und darüber verlinkt die Oberfläche.
    name = glocke_setzen(
        for_user=konto,
        subject=betreff,
        inhalt=hinweis,
        document_type=CHAT_GLOCKE_DOCTYPE,
        document_name=gespraech.name,
        # CHAT-4b: die Glocke entsteht in der Sitzung des Joblaufs/Endpunkts —
        # dieselbe Sitzung, in der Merker und Fach-Transaktion stehen.
        session=s,
        nur_fortschreiben=nur_fortschreiben,
        nur_zahl=nur_zahl,
    )
    if not name:
        return False  # Benachrichtigung ist Beiwerk — aber dann auch kein Merker
    # CHAT-10a: Push NUR, wenn die Glocke wirklich (neu) geschrieben wurde.
    # ``nur_zahl`` (teilweises Lesen führt die Zahl nach) ist KEIN Anlass: die
    # Person hat gerade gelesen, sie soll nicht geweckt werden; und
    # ``nur_fortschreiben`` legt nie eine neue Zeile an (dann ist ``name``
    # leer und der Aufruf kommt hier gar nicht an).
    if not nur_zahl:
        _push_nach_glocke(s, konto, titel=betreff, inhalt=hinweis,
                          gespraech=gespraech.name)
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
                        alles_gelesen: bool = True,
                        ungelesen: int | None = None) -> int:
    """Die Glocken dieses Gesprächs für diese Person als gelesen markieren.

    Zwei Dinge: die ``Notification Log``-Zeile(n) auf ``read`` stellen (das ist
    die Glocke in der Oberfläche) und den Merker ``gelesen_am`` setzen. Fehler
    sind Beiwerk — ``lesestand_setzen`` darf daran nicht scheitern.

    ``alles_gelesen=False`` (der Lesestand wurde nur bis zu einer ÄLTEREN
    Nachricht gesetzt, danach ist noch etwas ungelesen): dann bleibt die
    Glocke UNGELESEN stehen, denn es gibt weiter etwas zu sehen.

    CHAT-4b, Restpunkt b aus dem CHAT-4a-Review: sie stehen zu lassen genügte
    NICHT — ``merker_am`` blockiert weitere Läufe (``_glocke_faellig``), die
    Glocke zeigte also weiter die alte Zahl („3 neue“, obwohl 2 ungelesen).
    Deshalb wird sie hier SOFORT mit der neuen Zahl fortgeschrieben
    (``_glocke_setzen``, ``nur_fortschreiben=True``). Die Bedingungen sind
    Bewusst dieselben wie beim Job (Review R1/4):

      * es muss eine BESTEHENDE UNGELESENE Glocke fortgeschrieben werden —
        keine vorhanden (die Person hat sie weggeklickt) ⇒ NICHTS, es entsteht
        keine neue Glocke,
      * stumm geschaltet ⇒ NICHTS (F3: keine Glocke; der Zähler bleibt),
      * innerhalb der Ruhezeit ⇒ NICHTS (der Job glockt dann auch nicht; die
        Zahl folgt beim nächsten Lauf),
      * gelöschtes Gespräch oder noch nie geglockt ⇒ NICHTS.

    ``ungelesen`` muss der Aufrufer hereinreichen (er kennt die Zahl);
    ``None`` ⇒ es wird nichts fortgeschrieben.
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
        # Die Zahl der Bündel-Glocke folgt dem Lesestand: bleibt etwas offen,
        # wird die BESTEHENDE Zeile JETZT fortgeschrieben (statt erst beim
        # nächsten Lauf, der wegen ``merker_am`` nie käme).
        _buendel_glocke_nachziehen(s, gespraech, benutzer, merker, ungelesen)
        return 0
    anzahl = glocke_gelesen(for_user=benutzer, document_type=CHAT_GLOCKE_DOCTYPE,
                            document_name=gespraech)
    if merker is not None:
        merker.gelesen_am = _jetzt()
        s.flush()
    return anzahl


def _buendel_glocke_nachziehen(s, gespraech: str, benutzer: str,
                               merker: ChatGlocke | None,
                               ungelesen: int | None) -> None:
    """Die BESTEHENDE Bündel-Glocke auf die neue Zahl fortschreiben.

    Kein Anlegen, kein Wiederbeleben, kein Umgehen von ``stumm`` und Ruhezeit
    (Review R1/4). Fehler sind Beiwerk wie überall bei Glocken — der Lesestand
    ist längst geschrieben, das hier ist nur die Anzeige.

    ``modified`` wird NICHT hochgesetzt (Review CHAT-7a, Punkt 6): Lesen ist
    kein Anlass nach oben. Die Glocke soll in der Liste bleiben, wo sie steht —
    nur eine NEUE Nachricht schiebt sie nach oben (das macht
    ``chat_glocken_buendeln`` mit ``glocke_setzen``). Fortgeschrieben wird
    allein die ZAHL im Betreff/Inhalt, und zwar über ``nur_zahl=True``.
    """
    if not ungelesen or ungelesen <= 0:
        return
    if merker is None or merker.geglockt_am is None:
        return  # es wurde nie geglockt — nichts fortzuschreiben
    g = s.get(ChatGespraech, gespraech)
    if g is None or g.geloescht_am is not None:
        return
    teilnahme = s.get(ChatTeilnehmer, (gespraech, benutzer))
    if teilnahme is not None and teilnahme.stumm:
        return  # F3: keine Glocke mehr (der Zähler bleibt)
    jetzt = _jetzt()
    if not _glocke_ruhe_vorbei(s, gespraech, jetzt):
        return  # in der Ruhezeit glockt auch der Job nicht
    try:
        with s.begin_nested():
            _glocke_setzen(s, konto=benutzer, gespraech=g, teilnahme=teilnahme,
                           anzahl=int(ungelesen), jetzt=jetzt,
                           nur_fortschreiben=True, nur_zahl=True)
    except Exception:  # noqa: BLE001 — Anzeige, nicht der Lesestand
        logger.exception("chat: Bündel-Glocke %s/%s nicht fortgeschrieben",
                         gespraech, benutzer)


def _offen_bedingung(konto: str | None = None):
    """SQL-Bedingung „diese Nachricht ist für die Person ungelesen und zählt“.

    EINE Definition für Kandidaten-Abfrage und Nachprüfung (``_glocke_faellig``),
    damit die beiden nicht auseinanderlaufen: fremde Nachricht
    (``_nicht_von``), nicht gelöscht, nicht vor dem Beitritt, hinter dem
    Lesestand (Zeitstempel + Kennung — zwei Nachrichten können denselben
    Zeitstempel tragen, Sekundengenauigkeit auf PostgreSQL).

    ``konto=None``: die Person ist die des JOINS (``ChatTeilnehmer.benutzer``).

    CHAT-7b-2 (SOLL 5): der EIGENE Vorschlag zählt auch hier nicht als offen —
    dieselbe Bedingung wie ``_ungelesen_zaehlen`` (``_nicht_eigener_vorschlag``).
    BEIDE Aufrufer verbinden ``ChatRundeVorschlag`` per ``outerjoin`` auf
    ``chat_nachricht.vorschlag``; ohne diesen Join wäre die Bedingung ein
    Querverweis auf eine Tabelle, die nicht in der Abfrage steht.
    """
    person = ChatTeilnehmer.benutzer if konto is None else konto
    return [
        ChatNachricht.geloescht_am.is_(None),
        _nicht_von(person),
        _nicht_eigener_vorschlag(person),
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
        # SOLL 5: der Join trägt die Bedingung „nicht MEIN eigener Vorschlag“
        # (``_offen_bedingung`` → ``_nicht_eigener_vorschlag``).
        .outerjoin(ChatRundeVorschlag,
                   ChatRundeVorschlag.name == ChatNachricht.vorschlag)
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


def _glocke_ruhe_vorbei(s, gespraech: str, jetzt: datetime,
                        ruhe: int | None = None) -> bool:
    """Ist die Ruhezeit des Gesprächs abgelaufen? — dieselbe Regel wie im Job.

    Der Job glockt erst, wenn die neueste Nachricht mindestens ``ruhe``
    Minuten alt ist (``GLOCKE_RUHE_MINUTEN``, ``_glocken_kandidaten``). Das
    Nachziehen der Zahl beim Lesen (``_buendel_glocke_nachziehen``) darf diese
    Ruhe nicht umgehen (Review R1/4) — hier steht dieselbe Grenze als EINE
    Abfrage. Ein Gespräch ohne lebende Nachricht gilt als ruhig.
    """
    minuten = GLOCKE_RUHE_MINUTEN if ruhe is None else int(ruhe)
    neueste = s.execute(
        select(func.max(ChatNachricht.erstellt_am))
        .where(ChatNachricht.gespraech == gespraech,
               ChatNachricht.geloescht_am.is_(None))
    ).scalar_one_or_none()
    if neueste is None:
        return True
    return neueste <= jetzt - timedelta(minutes=minuten)


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
        # SOLL 5: derselbe Join wie in `_glocken_kandidaten` — er trägt die
        # Bedingung „nicht mein eigener Vorschlag“.
        .outerjoin(ChatRundeVorschlag,
                   ChatRundeVorschlag.name == ChatNachricht.vorschlag)
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


# ── CHAT-4b: Glocke beim Start und Erinnerung vor der Frist ─────────────────

#: CHAT-4b: Vorlauf der Erinnerung (Konzept S2: „eine Erinnerung 24 h vor
#: Frist“). Gefragt wird „noch offen UND Frist in höchstens 24 h“ — der Job
#: läuft minütlich, die Erinnerung geht dadurch zwischen 24 h und 23 h 59 min
#: vor der Frist heraus, genau einmal (``chat_umfrage.erinnert_am``).
ERINNERUNG_VORLAUF_STUNDEN = 24


def _glocken_empfaenger(s, gespraech: str) -> list[str]:
    """Konten, die dieses Gespräch lesen dürfen — EINE Abfrage, dann der Kern.

    Empfängerkreis der Umfrage-Glocken (CHAT-4b): die Teilnehmenden des
    Gesprächs (``chat_teilnehmer``), geprüft über ``_darf_lesen``
    (``rechte.darf``, nichts Eigenes). Wer NIE im Gespräch war, hat keine
    ``chat_teilnehmer``-Zeile und bekommt deshalb NICHTS — dieselbe Regel wie
    bei der gebündelten Glocke (CHAT-4a). Eine Umfrage ist für die Person eine
    Nachricht im Verlauf; ohne Verlauf gibt es nichts zu erinnern.

    ``rechte.darf`` läuft je Kandidat (der Kern kennt keinen Massenaufruf);
    die Kandidatenliste ist EINE SQL-Abfrage, keine N+1-Kette über Gespräche.
    Wer den Stumm-Schalter mitbraucht, nimmt ``_glocken_empfaenger_stumm``.
    """
    return [konto for konto in _teilnahme_konten(s, gespraech)
            if _darf_lesen(s, konto, gespraech)]


def _glocken_empfaenger_stumm(s, gespraech: str) -> list[tuple[str, bool]]:
    """Wie ``_glocken_empfaenger``, aber je Kandidat mit ``(konto, stumm)``.

    ``stumm`` kommt aus DERSELBEN SQL-Abfrage (Review R1, SOLL): kein
    ``s.get(ChatTeilnehmer)`` je Kandidat. Der Rechte-Kern entscheidet wie
    immer über ``rechte.darf``.
    """
    return [(konto, stumm) for konto, stumm in _teilnahme_und_stumm(s, gespraech)
            if _darf_lesen(s, konto, gespraech)]


def _umfrage_glocke_setzen(s, *, umfrage: ChatUmfrage, gespraech: ChatGespraech,
                           konto: str, subject: str, inhalt: str) -> bool:
    """EINE Umfrage-Glocke je (Umfrage, Konto) — fortschreiben statt doppeln.

    ``document_type`` ist ``chat_umfrage`` (die Glocke gehört zur UMFRAGE, nicht
    zum Gespräch: die gebündelte Chat-Glocke und die Erinnerung dürfen sich
    nicht gegenseitig überschreiben), ``document_name`` die Kennung der
    Umfrage. Liegt schon eine ungelesene Glocke dieser Umfrage, wird sie
    fortgeschrieben (``benachrichtigungen.glocke_setzen``) — dadurch steht je
    Person und Umfrage genau EINE Zeile.

    Fehler sind Beiwerk (Rückgabe ``False``), die Fach-Transaktion läuft weiter.
    """
    from diakronos_app.benachrichtigungen import glocke_setzen

    if not konto:
        return False
    try:
        with s.begin_nested():
            name = glocke_setzen(
                for_user=konto,
                subject=subject,
                inhalt=inhalt,
                document_type=CHAT_UMFRAGE_GLOCKE_DOCTYPE,
                document_name=umfrage.name,
                # DIE Sitzung des Aufrufs: die Glocke muss mit der
                # Fach-Transaktion sichtbar werden und mit ihr committen.
                session=s,
            )
        if name:
            # CHAT-10a: Push zur geschriebenen Umfrage-Glocke — dieselben
            # Empfänger wie die Glocke (stumm ist hier schon ausgesiebt).
            _push_nach_glocke(s, konto, titel=subject, inhalt=inhalt,
                              gespraech=gespraech.name)
        return bool(name)
    except Exception:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        logger.exception("chat: Umfrage-Glocke %s/%s fehlgeschlagen",
                         umfrage.name, konto)
        return False


def _umfrage_betreff_start(gespraech: ChatGespraech, titel: str) -> str:
    """Betreff der Start-Glocke. Im 1:1 ein eigener Satz ohne Namen.

    „Neue Umfrage im Direktnachricht“ wäre falsch; und der Titel eines 1:1
    wäre der Name des Gegenübers — der steht nie in einer Glocke.

    Runde (CHAT-7b, Review R1 SOLL 9): „Neue Umfrage in der Runde <Titel>“ —
    grammatisch korrekt (der Rundenname ist ein Eigenname) und ohne
    Absendernamen. ``titel`` kommt hier als ``_glocken_titel`` an, das für eine
    Runde bereits „Runde <Name>“ lautet — deshalb wird für Runden der NAME
    bevorzugt (sonst stünde „Runde Runde …“; Fehlt der Name, bleibt der
    neutrale Rückfall).
    """
    if gespraech.art == ART_DIREKT:
        return "Neue Umfrage in einer Direktnachricht"
    if gespraech.art == ART_RUNDE:
        name = str(getattr(gespraech, "titel", "") or "").strip() or _runde_name(titel)
        return (f"Neue Umfrage in der Runde {name}" if name
                else "Neue Umfrage in einer Runde")
    return f"Neue Umfrage im {titel}"


def _runde_name(titel: str) -> str:
    """Der blosse Rundenname aus einem ``_glocken_titel``-Text (``Runde X``)."""
    text = str(titel or "").strip()
    return text[len("Runde "):].strip() if text.startswith("Runde ") else text


def _umfrage_betreff_ende(gespraech: ChatGespraech, titel: str) -> str:
    """Betreff der Erinnerung „… endet morgen“; im 1:1 ohne Namen (s. o.)."""
    if gespraech.art == ART_DIREKT:
        return "Umfrage in einer Direktnachricht endet morgen"
    if gespraech.art == ART_RUNDE:
        name = str(getattr(gespraech, "titel", "") or "").strip() or _runde_name(titel)
        return (f"Umfrage in der Runde {name} endet morgen" if name
                else "Umfrage in einer Runde endet morgen")
    return f"Umfrage im {titel} endet morgen"


def _glocke_neue_umfrage(s, umfrage: ChatUmfrage, gespraech: ChatGespraech,
                         titel: str, angelegt_von: str) -> int:
    """Start-Glocke (CHAT-4b): „Neue Umfrage im <Titel>“ an alle Lesenden.

    Konzept S2: „eine Glocke beim Start (‚Neue Umfrage im Chor')“. Empfänger
    sind die Konten aus ``_glocken_empfaenger`` — also wer das Gespräch lesen
    darf UND schon eine Teilnahmezeile hat —, AUSSER:

      * der/dem Anlegenden (es weiß es selbst),
      * stumm geschalteten Personen (F3: keine Glocke mehr — dieselbe Regel wie
        bei der gebündelten Glocke; der Ungelesen-Zähler bleibt),
      * wer nicht mehr lesen darf (``rechte.darf`` im Kern).

    Die UMFRAGE kommt als Instanz herein (Review R1/2): der Aufrufer kennt sie,
    die frühere Variante suchte „die neueste Umfrage des Gesprächs“ und traf
    bei zwei offenen Umfragen die falsche.

    Der Text enthält NUR den Gesprächstitel: keine Frage, keine Optionen, kein
    Name der anlegenden Person (Konzept 4.5 — dieselbe Zusage wie bei der
    gebündelten Glocke und bei ``_glocke_neue_meldung``).

    Läuft NACH dem Commit des Anlegens, in einer eigenen Sitzung — eine kaputte
    Benachrichtigung darf die angelegte Umfrage nicht zurücknehmen.

    Rückgabe: Zahl der geschriebenen Glocken.
    """
    if umfrage is None or gespraech is None:
        return 0
    if gespraech.geloescht_am is not None:
        return 0
    geschrieben = 0
    for konto, stumm in _glocken_empfaenger_stumm(s, gespraech.name):
        if konto == angelegt_von or stumm:
            continue
        # CHAT-7b-2 (MUSS 1b): wer NACH der Umfrage in die Runde eingetreten
        # ist, sieht sie im Verlauf nicht — er bekommt auch keine Glocke
        # („Neue Umfrage“ wäre eine Nachricht zu einem Inhalt, den es für ihn
        # nicht gibt). Dieselbe Grenze wie im Verlauf, KEINE eigene Regel.
        if _vor_eintritt(s, gespraech, konto, umfrage.erstellt_am):
            continue
        if _umfrage_glocke_setzen(
            s, umfrage=umfrage, gespraech=gespraech, konto=konto,
            subject=_umfrage_betreff_start(gespraech, titel),
            inhalt=("Im Gespräch wurde eine Umfrage gestartet. "
                    "Öffne den Chat, um abzustimmen."),
        ):
            geschrieben += 1
    return geschrieben


def _offene_umfragen_mit_frist(s, zeit: datetime, vorlauf_stunden: int) -> list[str]:
    """Umfragen, deren Frist in höchstens ``vorlauf_stunden`` abläuft — in SQL.

    Kriterien (alle in der Datenbank, damit der Minutentakt nicht die halbe
    Chat-Tabelle lädt):

      * ``erinnert_am IS NULL`` — noch nicht erinnert (Idempotenz),
      * ``geschlossen_am IS NULL`` — nicht geschlossen,
      * ``frist_am IS NOT NULL`` und ``frist_am <= zeit + vorlauf`` — die Frist
        naht (auch eine bereits VERSTRICHENE Frist fällt hier hinein: solange
        der Schließ-Job sie noch nicht geschlossen hat, ist eine Erinnerung
        besser als keine),
      * **kurze Frist**: ``frist_am - erstellt_am > vorlauf`` — eine Umfrage,
        die schon mit einer Frist INNERHALB des Vorlaufs angelegt wurde, wird
        hier ausgeschlossen (Review CHAT-7a, Punkt 5). Sie wäre sonst in jedem
        Minutentakt Kandidat, bis die Frist vorbei ist: erinnert werden kann
        sie ohnehin nur einmal, und der Lauf holt sie dann jede Minute neu.
        Die Grenze ist STRIKT (Review CHAT-N1, MUSS 1): genau ``vorlauf``
        Abstand zählt als kurz und ist KEIN Kandidat — dieselbe Grenze wie in
        der Python-Nachprüfung, mit derselben Größe.
      * die Hülle-Nachricht ist nicht gelöscht (``chat_nachricht.geloescht_am``)
        — eine entfernte Umfrage wird nie erinnert,
      * das Gespräch lebt.
    """
    grenze = zeit + timedelta(hours=int(vorlauf_stunden))
    # Kurze Frist ausschliessen — je Dialekt, aber mit DERSELBEN Groesse wie die
    # Python-Nachpruefung (``vorlauf_stunden``, strikt). ``julianday`` waere ein
    # SQL-Funktionsname, den PostgreSQL nicht kennt (Review CHAT-N1, MUSS 1):
    # der Job waere dort an ``UndefinedFunction`` gescheitert und haette NIE
    # erinnert. Zwei Wege, EINE Grenze:
    #   * SQLite: Sekunden seit der Epoche als Ganzzahl, Differenz > h*3600;
    #   * PostgreSQL: Zeitstempel + ``interval`` (der Vergleich bleibt ein
    #     Zeitstempel-Vergleich).
    stunden = int(vorlauf_stunden)
    if s.get_bind().dialect.name == "sqlite":
        nicht_kurz = (
            cast(func.strftime("%s", ChatUmfrage.frist_am), Integer)
            - cast(func.strftime("%s", ChatUmfrage.erstellt_am), Integer)
        ) > stunden * 3600
    else:
        nicht_kurz = (ChatUmfrage.frist_am
                      > ChatUmfrage.erstellt_am + timedelta(hours=stunden))
    return [str(k) for k in s.execute(
        select(ChatUmfrage.name)
        .join(ChatNachricht, ChatNachricht.umfrage == ChatUmfrage.name)
        .join(ChatGespraech, ChatGespraech.name == ChatUmfrage.gespraech)
        .where(
            ChatUmfrage.erinnert_am.is_(None),
            ChatUmfrage.geschlossen_am.is_(None),
            ChatUmfrage.frist_am.is_not(None),
            ChatUmfrage.frist_am <= grenze,
            # Kurze Frist: ``frist_am - erstellt_am > vorlauf``, strikt.
            nicht_kurz,
            ChatNachricht.geloescht_am.is_(None),
            ChatGespraech.geloescht_am.is_(None),
        )
        .order_by(ChatUmfrage.frist_am, ChatUmfrage.name)
    ).scalars().all() if k]


def _umfrage_offen_je_konto(s, umfrage: ChatUmfrage) -> dict[str, bool]:
    """``{konto: hat_schon_abgestimmt}`` für EIN Gespräch — EINE Abfrage.

    Die beiden Zählwege der Umfrage (CHAT-5) getrennt ausgewertet:
    OFFEN gibt es ``chat_stimme``-Zeilen je Person, ANONYM ``chat_umfrage_abgabe``
    ohne jeden Optionsbezug. Beides ist eine Mengen-Abfrage über das GESPRÄCH,
    nicht je Person.

    Die Antwort bleibt im Server: die Erinnerung verrät nach außen nur „du hast
    noch nicht abgestimmt“ an die Person selbst — niemals eine Liste an Dritte.
    """
    if umfrage.anonym:
        konten = set(s.execute(
            select(ChatUmfrageAbgabe.benutzer)
            .where(ChatUmfrageAbgabe.umfrage == umfrage.name)
        ).scalars().all())
    else:
        konten = set(s.execute(
            select(ChatStimme.benutzer)
            .where(ChatStimme.umfrage == umfrage.name)
        ).scalars().all())
    return {str(k): True for k in konten if k}


def _glocke_umfrage_erinnerung(s, *, umfrage: ChatUmfrage, gespraech: ChatGespraech,
                               titel: str,
                               vorlauf_stunden: int | None = None
                               ) -> tuple[int, int, bool]:
    """Erinnerung 24 h vor der Frist an alle, die NOCH NICHT abgestimmt haben.

    Der Job ``chat_umfrage_erinnerungen`` ruft DAS (nach dem Schließen fälliger
    Umfragen). Empfängerkreis wie bei der Start-Glocke
    (``_glocken_empfaenger_stumm``: Teilnahmezeile + ``rechte.darf`` LESEN +
    Stumm-Schalter aus derselben Abfrage), AUSSER allen, die schon abgestimmt
    haben (offen: ``chat_stimme``, anonym: ``chat_umfrage_abgabe``).

    Die UMFRAGE kommt als Instanz herein (Review R1/2): der Job kennt die
    Kandidaten-Kennung. Die frühere Variante suchte „die neueste Umfrage des
    Gesprächs“ — bei zwei offenen Umfragen hätte die Erinnerung zu A die
    Abgestimmten von B gefiltert und an B gehängt.

    Die Erinnerung an die Person selbst ist die EINZIGE Information, die
    entsteht: „du hast noch nicht abgestimmt“. Eine Liste, WER nicht abgestimmt
    hat, gibt es in keiner Antwort und in keiner Glocke an Dritte (Anonymität,
    Konzept S2). Die Glocke ist je (Umfrage, Konto) eine und wird
    fortgeschrieben — die Start-Glocke derselben Person steht auf derselben
    Zeile.

    Rückgabe: ``(geschriebene Glocken, Zahl der Empfänger, zutreffend)``.
    ``zutreffend=False`` heißt „für diese Umfrage gibt es keine Erinnerung“
    (kurze Frist, Review R1 SOLL) — der Merker wird dann NICHT gesetzt, sonst
    stünde „erinnert“ an einer Umfrage, die nie hätte erinnert werden dürfen.
    Sonst setzt der Aufrufer ``erinnert_am`` nur, wenn geschrieben wurde ODER
    es keine Empfänger gab (Review R1, SOLL): bei einem Schreibfehler holt der
    nächste Lauf es nach, statt die Erinnerung still zu verlieren.
    """
    if umfrage is None or gespraech is None:
        return 0, 0, False
    if gespraech.geloescht_am is not None:
        return 0, 0, False
    # Kurze Fristen (Review R1, SOLL): wurde die Umfrage mit einer Frist
    # INNERHALB des Vorlaufs angelegt, ist die Start-Glocke die ganze
    # Erinnerung. Dieselbe Größe und dieselbe Grenze wie in der SQL-Auswahl
    # (``_offene_umfragen_mit_frist``, Review CHAT-N1 MUSS 1): strikt ``<=``
    # ist kurz — genau ``vorlauf`` Abstand zählt NICHT als Erinnerung.
    # Ohne ``erstellt_am`` wird konservativ NICHT erinnert.
    stunden = (ERINNERUNG_VORLAUF_STUNDEN if vorlauf_stunden is None
               else int(vorlauf_stunden))
    if umfrage.frist_am is not None and umfrage.erstellt_am is not None:
        if umfrage.frist_am - umfrage.erstellt_am <= timedelta(hours=stunden):
            return 0, 0, False
    abgestimmt = _umfrage_offen_je_konto(s, umfrage)
    geschrieben = 0
    empfaenger = 0
    for konto, stumm in _glocken_empfaenger_stumm(s, gespraech.name):
        if stumm or abgestimmt.get(konto):
            continue
        # CHAT-7b-2 (MUSS 1b): wer erst NACH der Umfrage eingetreten ist, sieht
        # sie nicht im Verlauf — er wird auch nicht erinnert („stimme noch ab“
        # wäre eine Aufforderung zu einem Inhalt, den es für ihn nicht gibt).
        if _vor_eintritt(s, gespraech, konto, umfrage.erstellt_am):
            continue
        empfaenger += 1
        if _umfrage_glocke_setzen(
            s, umfrage=umfrage, gespraech=gespraech, konto=konto,
            subject=_umfrage_betreff_ende(gespraech, titel),
            inhalt=("Die Frist der Umfrage läuft ab. "
                    "Öffne den Chat, um noch abzustimmen."),
        ):
            geschrieben += 1
    return geschrieben, empfaenger, True


def chat_umfrage_erinnerungen(jetzt: datetime | None = None,
                              vorlauf: int | None = None) -> int:
    """Scheduler-Job (CHAT-4b): EINE Erinnerung 24 h vor der Frist.

    KEIN HTTP-Endpunkt (Review R1/1): bewusst ohne ``@whitelist`` — wie
    ``chat_glocken_buendeln``. Der Rumpf nimmt ``jetzt``/``vorlauf`` an und
    SCHLIESST fällige Umfragen mit; über HTTP wäre das für jeden Angemeldeten
    ein Hebel (``jetzt=2099-01-01`` schlösse alle befristeten Umfragen,
    ``vorlauf=99999`` verschöbe alle Erinnerungen). Aufrufer ist allein
    ``scheduler.job_chat_umfrage_erinnerungen``.

    Konzept S2: „eine Erinnerung 24 h vor Frist an die, die noch nicht
    abgestimmt haben“. Läuft im Glocken-Minutentakt hinter
    ``chat_glocken_buendeln`` (DIESELBE Sitzungssperre ``GLOCKE_SPERRE``: beide
    Jobs schreiben Glocken in dieselben Zeilen. Der zweite Lauf bekommt die
    Sperre deshalb nicht und überspringt diesen Takt — ``_lauf_sperren`` liefert
    dann ``False``, es wird nichts gedoppelt; der Minutentakt holt ihn nach).

    Das minütliche ``schliesse_faellige`` in Schritt 1 ist eine bewusste
    Entscheidung des Operators (Review R1, SOLL): die Umfrage schließt damit
    pünktlich zur Frist statt bis zu einen Tag später, und es bleibt EINE
    Anweisung über einen Index (``ix_chat_umfrage_frist``) — kein Lesen, keine
    Namensliste.

    Ablauf je Lauf:

      1. **Erst schließen, dann erinnern** (``schliesse_faellige``): eine
         Umfrage, deren Frist vorbei ist, wird nicht mehr erinnert. Der
         Schließ-Job läuft zwar täglich, aber ein Tageslauf kann ausfallen —
         der Merker ``erinnert_am`` macht die Erinnerung trotzdem einmalig.
      2. **Kandidaten in SQL** (``_offene_umfragen_mit_frist``): offen, mit
         Frist in höchstens ``vorlauf`` Stunden, noch nicht erinnert, Hülle und
         Gespräch nicht gelöscht.
      3. Je Umfrage die Glocken an die Nicht-Abgestimmten
         (``_glocke_umfrage_erinnerung``) und DANACH ``erinnert_am`` setzen —
         im selben Vorgang. Der Merker wird nur gesetzt, wenn das Schreiben
         durchlief ODER es gar keine Empfänger gab; scheitert eine Glocke,
         bleibt er leer und der nächste Minutentakt versucht es erneut
         (Review R1, SOLL).

    Idempotent: der zweite Lauf findet keine Umfrage mit ``erinnert_am IS
    NULL`` mehr — vorausgesetzt, der erste hat den Merker gesetzt.

    ``jetzt`` und ``vorlauf`` sind injizierbar (Tests, kein ``sleep``).

    Rückgabe: Zahl der geschriebenen/aktualisierten Glocken.
    """
    from diakronos_app import db as _db

    zeit = jetzt or _jetzt()
    stunden = ERINNERUNG_VORLAUF_STUNDEN if vorlauf is None else int(vorlauf)
    # Ein verspäteter Tageslauf soll die Grundlage nicht verfälschen: erst
    # schließen (eigene Transaktion mit eigener Sitzung), dann erinnern.
    schliesse_faellige(zeit)
    geschrieben = 0
    with _db.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        from diakronos_app.rechte import merkungsrahmen

        if not _lauf_sperren(s):
            logger.info("chat_umfrage_erinnerungen: anderer Lauf aktiv, übersprungen")
            return 0
        with merkungsrahmen():
            for kennung in _offene_umfragen_mit_frist(s, zeit, stunden):
                try:
                    with s.begin_nested():
                        u = s.get(ChatUmfrage, kennung)
                        if u is None or u.erinnert_am is not None \
                                or u.geschlossen_am is not None:
                            continue
                        g = s.get(ChatGespraech, u.gespraech)
                        if g is None or g.geloescht_am is not None:
                            continue
                        anzahl, empfaenger, zutreffend = _glocke_umfrage_erinnerung(
                            s, umfrage=u, gespraech=g, titel=_glocken_titel(g),
                            vorlauf_stunden=stunden)
                        # Merker nur bei Erfolg: „nicht zutreffend“ (kurze Frist)
                        # bleibt ohne Merker, „keine Empfänger“ ist fertig, und
                        # eine geschriebene Glocke heißt „erinnert“. Gab es
                        # Empfänger, aber keine Glocke, ist das Schreiben
                        # gescheitert — der nächste Minutentakt holt es nach.
                        if zutreffend and (anzahl or not empfaenger):
                            u.erinnert_am = zeit
                        s.flush()
                        geschrieben += anzahl
                except Exception:  # noqa: BLE001 — eine Umfrage, nicht der Lauf
                    logger.exception("chat_umfrage_erinnerungen: %s fehlgeschlagen",
                                     kennung)
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


def _erklaere(benutzer: str, aktion: str, *, gruppe: str | None,
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


def _erlaube(benutzer: str, aktion: str, *, g: ChatGespraech | None = None,
             gruppe: str | None = None, untergruppe: str | None = None,
             besitzer: str | None = None, gespraech: str | None = None,
             teilnehmer=None, sitzung=None,
             direkt: bool = False, meldeweg: bool = False) -> None:
    """DIE eine Rechteweiche je Gesprächsart (CHAT-7a).

    Jeder Endpunkt fragt HIER — nicht selbst — und bekommt je ``art`` die
    passende Frage des Kerns; eine eigene Rechtelogik gibt es in diesem Modul
    nicht (Kartenauflage). Auch der Meldeweg (Liste, Entscheiden,
    ``_darf_moderieren``) und die Zählhilfen gehen durch diese eine Funktion.

    * ``art = 'direkt'`` → ``rechte.darf_direktgespraech(benutzer, aktion,
      teilnehmer=<Konten des Gesprächs>, besitzer=…)``. Der Raum sind die
      Teilnehmenden, nicht eine Gruppe.
    * sonst → ``_erklaere`` → ``rechte.darf(..., gruppe/untergruppe)``
      (unverändert seit CHAT-2).

    ``g`` ist die Zeile, wenn der Aufrufer sie schon hat; ``gespraech`` die
    Kennung, ``gruppe``/``untergruppe`` die Einheit. Der ART-Vergleich gilt nur
    für ECHTE Gespräche (``g.name`` gesetzt): das Platzhalter-Objekt aus
    ``_lesbare_gespraeche`` für eine noch nicht angelegte Einheit hat
    ``name = None`` — dort gibt es kein Direktgespräch zu erkennen, und
    ``rechte.darf`` entscheidet wie seit CHAT-2.

    ``direkt=True`` fragt die 1:1-Regel OHNE Gespräch — für die eine Frage
    „ist diese Person Meldestelle?“ (``meldungen_liste``), die vor jedem
    Kandidaten beantwortet sein muss. Ohne ``g`` und ohne Teilnehmende ist die
    Antwort für LESEN/ANLEGEN/SCHREIBEN ``nein`` (fail closed); für MODERIEREN
    entscheidet sie der Kern.

    ``teilnehmer`` sind die KONTEN des Gesprächs. Fehlt die Angabe, werden sie
    in ``sitzung`` (der Sitzung des Aufrufers) gelesen — so kann kein Aufrufer
    eine zu kleine Liste mitgeben und sich damit Zugang verschaffen. Eine
    EIGENE Sitzung öffnet die Weiche nur, wenn der Aufrufer gar keine hat:
    je Rechtefrage zwei frische Sitzungen (und womöglich noch nicht
    committete Zeilen darin) wären eine stille Fehlerquelle.

    AUSNAHME MODERIEREN im 1:1 (Review CHAT-7a, Punkt 2): der Kern wertet die
    Teilnehmenden für MODERIEREN gar nicht aus (``darf_direktgespraech``
    antwortet allein über ``ist_meldestelle``). Sie werden deshalb hier auch
    nicht gelesen — weder die ART noch die Konten. Dieselbe Sitzung des
    Aufrufers, kein zweiter Weg zur Wahrheit.

    Die Teilnahme prüft der KERN (``benutzer not in konten → kein_teilnehmer``)
    — hier steht bewusst KEINE Vorprüfung davor.

    ``meldeweg`` (Review CHAT-7b R1, MUSS 1): MODERIEREN gibt es im 1:1 und in
    der Runde NUR noch auf dem Meldeweg — ``meldungen_liste``,
    ``meldung_entscheiden`` und die Glocke an die Meldestelle setzen es.
    Jeder andere Aufrufer (Löschen, Umfrage schließen, Verlauf …) lässt es weg
    und bekommt vom Kern ``nur_meldeweg`` (NEIN) — auch als teilnehmender
    Administrator. Ein zweiter Rechtepfad entsteht dadurch nicht: das Flag
    reicht nur die INFORMATION weiter, WO die Frage gestellt wird.
    """
    art = ART_DIREKT if direkt else ""  # Runden kommen aus `_wechselart_lesen`
    if g is not None:
        if g.name:
            art = str(g.art or "")
        gespraech = gespraech or g.name
        gruppe = gruppe if gruppe is not None else g.gruppe
        untergruppe = untergruppe if untergruppe is not None else g.untergruppe
    if not (direkt and aktion == rechte.MODERIEREN):
        if g is None and gespraech and sitzung is not None:
            art = _wechselart_lesen(gespraech, sitzung=sitzung)
        elif g is None and gespraech:
            art = _wechselart_lesen(gespraech)

    # 1:1 UND Runde: der Raum sind die Teilnehmenden (CHAT-7a/7b). Dieselbe
    # Frage des Kerns — kein zweiter Pfad für Runden.
    if art in (ART_DIREKT, ART_RUNDE):
        if teilnehmer is None and aktion != rechte.MODERIEREN:
            if sitzung is not None and gespraech:
                teilnehmer = _teilnehmer_konten(sitzung, gespraech)
            elif gespraech:
                teilnehmer = _teilnehmer_konten_aus_db(gespraech, sitzung=sitzung)
        entscheidung = rechte.darf_direktgespraech(
            benutzer, aktion, teilnehmer=teilnehmer, besitzer=besitzer,
            meldeweg=meldeweg)
        if not entscheidung:
            _h()
        return
    _erklaere(benutzer, aktion, gruppe=gruppe, untergruppe=untergruppe,
              besitzer=besitzer, gespraech=gespraech)


def _weiche_ja(benutzer: str, aktion: str, **kwargs) -> bool:
    """``_erlaube`` als WAHRHEITSWERT — für Fragen über VIELE Gespräche.

    Dieselbe Weiche, nur ohne Wurf: die Liste fragt über alle Kandidaten, und
    das erste „nein“ ist dort nicht das Ende. Kein zweiter Rechtepfad.
    ``kwargs`` reicht alles durch (``meldeweg`` für die Meldewege).
    """
    try:
        _erlaube(benutzer, aktion, **kwargs)
    except PermissionError:
        return False
    return True


def _wechselart_lesen(gespraech: str, *, sitzung=None) -> str:
    """Die ``art`` eines Gesprächs — in der Sitzung des Aufrufers.

    ``sitzung`` MUSS die Sitzung des Aufrufers sein (Review CHAT-7a, Punkt 2):
    eine eigene Sitzung je Kandidat war der Fehler. Wird eine Sitzung
    übergeben, wird SIE benutzt (Review CHAT-N1, SOLL) — sonst sähe diese
    Abfrage in einer zweiten Transaktion nicht die geflushten, noch nicht
    festgeschriebenen Zeilen des Aufrufers. Ohne Sitzung wird die laufende des
    Aufrufs genommen (``db.lesesitzung``); sie zu schließen ist dann Sache des
    Aufrufs. Unbekannte Kennung → ``""`` (der Aufrufer hat sie meist schon
    geprüft; dann entscheidet die Gruppenfrage wie bisher).
    """
    if not gespraech:
        return ""

    def _art(s) -> str:
        return str(s.execute(
            select(ChatGespraech.art).where(ChatGespraech.name == gespraech)
        ).scalar_one_or_none() or "")

    if sitzung is not None:
        return _art(sitzung)
    with dbmod.lesesitzung() as s:
        return _art(s)


def _teilnehmer_konten(s, gespraech: str) -> list[str]:
    """KONTEN, die JETZT als Teilnehmende zaehlen — je Gespraechsart.

    1:1 und Runde: wer in einer RUNDE ``verlassen_am`` traegt, ist raus
    (CHAT-7b) — die Zeile bleibt fuer die Anzeige stehen, die Rechtefrage
    bekommt sie aber nicht mehr. Beim 1:1 gibt es keinen Austritt; die Spalte
    ist dort immer leer, die Filterung also wirkungslos aber harmlos.
    """
    return sorted(
        str(konto) for konto in s.execute(
            select(ChatTeilnehmer.benutzer).where(
                ChatTeilnehmer.gespraech == gespraech,
                ChatTeilnehmer.verlassen_am.is_(None),
            )
        ).scalars().all() if konto
    )


def _teilnehmer_konten_aus_db(gespraech: str, *, sitzung=None) -> list[str]:
    """Wie ``_teilnehmer_konten``, nur ohne Sitzung des Aufrufers."""
    if not gespraech:
        return []
    if sitzung is not None:
        return _teilnehmer_konten(sitzung, gespraech)
    with dbmod.lesesitzung() as s:
        return _teilnehmer_konten(s, gespraech)


def _teilnahme_konten_aus_db(gespraech: str, *, sitzung=None) -> list[str]:
    """Die Konten des Gesprächs — KURZ und in der Sitzung des AUFRUFERS.

    ``_teilnahme_konten`` liest in EINER Sitzung; hier wird die Frage vor dem
    Rechteaufruf gestellt (der Kern öffnet seine eigene Sitzung), deshalb wird
    eine übergebene Sitzung benutzt oder — wenn es keine gibt — die laufende
    des Aufrufs (Review CHAT-7a, Punkt 2: keine eigene Sitzung je Kandidat).
    Reihenfolge egal: der Kern sortiert selbst.
    """
    if not gespraech:
        return []
    if sitzung is not None:
        return _teilnahme_konten(sitzung, gespraech)
    with dbmod.lesesitzung() as s:
        return _teilnahme_konten(s, gespraech)


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


def _sichtbar_ab(s, g: ChatGespraech, benutzer: str | None) -> datetime | None:
    """Ab wann ``benutzer`` den Verlauf dieses Gesprächs sehen darf (SOLL 7).

    Nur für RUNDEN: ``chat_teilnehmer.sichtbar_ab`` ist der Eintritt (bzw. der
    WIEDEREINTRITT) — wer neu dazukommt, liest nicht rückwirkend mit. ``None``
    = keine Einschränkung (Gruppe, 1:1, Bestandszeile ohne Datum).
    """
    if not g.name or g.art != ART_RUNDE:
        return None
    return s.execute(
        select(ChatTeilnehmer.sichtbar_ab).where(
            ChatTeilnehmer.gespraech == g.name,
            ChatTeilnehmer.benutzer == benutzer,
        )
    ).scalar_one_or_none()


def _vor_eintritt(s, g: ChatGespraech, benutzer: str | None,
                  erstellt_am: datetime | None) -> bool:
    """Liegt ``erstellt_am`` VOR dem Eintritt von ``benutzer`` in diese Runde?

    CHAT-7b-2 (MUSS 1): die Sichtbarkeitsgrenze (``_sichtbar_ab``) gilt nicht
    nur für den Verlauf, sondern für JEDEN Weg zu einem Inhalt von davor —
    Zitat, Reaktion, Meldung, Lesestand-Anker, Umfrage. Wer neu (oder wieder)
    eintritt, liest nicht rückwirkend mit; „nicht sichtbar“ ist dabei
    dasselbe wie „gibt es nicht“ (404, nichts über den Inhalt verraten).

    ``False`` heißt: keine Einschränkung (Gruppe, 1:1, Bestandszeile ohne
    Datum, fehlendes ``erstellt_am``) — dieselbe Regel wie ``_sichtbar_ab``.
    EINE Wahrheit für alle Aufrufer, kein zweiter Vergleich je Endpunkt.
    """
    if erstellt_am is None:
        return False
    grenze = _sichtbar_ab(s, g, benutzer)
    return grenze is not None and erstellt_am < grenze


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
                 _nicht_von(benutzer),
                 # SOLL 5 (CHAT-7b-2): der EIGENE Vorschlag ist für den
                 # Vorschlagenden keine ungelesene Nachricht (er kennt ihn).
                 _nicht_eigener_vorschlag(benutzer)]
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
                         .outerjoin(ChatRundeVorschlag,
                                    ChatRundeVorschlag.name == ChatNachricht.vorschlag)
                         .where(*bedingung)).scalar_one())


def _teilnahme_konten(s, gespraech: str) -> list[str]:
    """Konten mit Teilnahmezeile in diesem Gespraech (nur Kennungen)."""
    return [str(k) for k in s.execute(
        select(ChatTeilnehmer.benutzer).where(ChatTeilnehmer.gespraech == gespraech)
    ).scalars().all() if k]


def _konto_je_mitglied(s, mitglied: str) -> str | None:
    """Das KONTO einer Mitglied-Kennung — EINE Auflösung: ``mitglied.user``.

    Dieselbe stabile Verknüpfung, die auch ``darf_direktnachricht`` über
    ``_mitglied_von`` benutzt (Priorität der Kopplung). Der frühere
    E-Mail-Rückfall ist RAUS: er war ein zweiter Weg zum selben Gespräch und
    konnte bei abweichender Adresse ein anderes Konto treffen. Ohne
    ``mitglied.user`` gibt es kein Konto → ``None`` (fail closed).
    """
    if not mitglied:
        return None
    konto = s.execute(select(Mitglied.user).where(Mitglied.name == mitglied)).scalar_one_or_none()
    return str(konto) if konto else None


def _direkt_gespraeche(s, benutzer: str) -> list[ChatGespraech]:
    """Die 1:1-Gespräche, an denen ``benutzer`` beteiligt ist — und lesen darf.

    Grundlage sind SEINE Teilnahmezeilen (``chat_teilnehmer``) auf Gesprächen
    mit ``art = 'direkt'``: fremde Direktgespräche können damit gar nicht erst
    in die Liste geraten. Je Kandidat entscheidet die Weiche
    (``_darf_lesen`` → ``rechte.darf_direktgespraech``) — keine eigene
    Rollenlogik.
    """
    if not benutzer:
        return []
    kandidaten = s.execute(
        select(ChatGespraech)
        .join(ChatTeilnehmer, ChatTeilnehmer.gespraech == ChatGespraech.name)
        .where(ChatGespraech.art == ART_DIREKT,
               ChatGespraech.geloescht_am.is_(None),
               ChatTeilnehmer.benutzer == benutzer)
        .order_by(ChatGespraech.name)
    ).scalars().all()
    return [g for g in kandidaten if _darf_lesen(s, benutzer, g.name)]


def _runde_gespraeche(s, benutzer: str) -> list[ChatGespraech]:
    """Die RUNDEN, an denen ``benutzer`` als AKTIVE Person beteiligt ist.

    Wie ``_direkt_gespraeche``: Grundlage sind SEINE Teilnahmezeilen, hier
    aber nur die ohne ``verlassen_am`` (wer gegangen ist, sieht die Runde nicht
    mehr in seiner Liste). Je Kandidat entscheidet die Weiche
    (``_darf_lesen`` → ``rechte.darf_direktgespraech``) — keine Rollenlogik hier.
    """
    if not benutzer:
        return []
    kandidaten = s.execute(
        select(ChatGespraech)
        .join(ChatTeilnehmer, ChatTeilnehmer.gespraech == ChatGespraech.name)
        .where(ChatGespraech.art == ART_RUNDE,
               ChatGespraech.geloescht_am.is_(None),
               ChatTeilnehmer.benutzer == benutzer,
               ChatTeilnehmer.verlassen_am.is_(None))
        .order_by(ChatGespraech.name)
    ).scalars().all()
    return [g for g in kandidaten if _darf_lesen(s, benutzer, g.name)]


def _teilnahme_und_stumm(s, gespraech: str) -> list[tuple[str, bool]]:
    """``(konto, stumm)``-Paare der Teilnahmezeilen — EINE Abfrage (CHAT-4b R1).

    Der Stumm-Schalter steht in derselben Zeile wie das Konto; ihn hier
    mitzuholen erspart ein ``s.get(ChatTeilnehmer)`` je Kandidat.
    """
    return [(str(konto), bool(stumm)) for konto, stumm in s.execute(
        select(ChatTeilnehmer.benutzer, ChatTeilnehmer.stumm)
        .where(ChatTeilnehmer.gespraech == gespraech)
    ).all() if konto]


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


def _gespraech_kopf(s, g: ChatGespraech, benutzer: str,
                    *, ausgeschlossene: set[str] | None = None) -> dict[str, Any]:
    """Ein Eintrag der Gespraechsliste — auch fuer ein noch nie geoeffnetes.

    Ein DIREKTGESPRAECH (CHAT-7a) traegt statt des Gruppennamens den
    Anzeigenamen des GEGENUEBERS (``_direkt_titel`` — bestehende Namensquelle
    inkl. Maskierung) und dessen Bild; ``gruppe``/``untergruppe`` bleiben
    leer, ``mitglied`` nennt die Mitglied-Kennung fuers Profil.

    ``ausgeschlossene`` reicht ``meine_gespraeche`` durch (CHAT-N2): EIN
    Ausschluss-Zustand je Anfrage statt eines Volllaufs je Direktgespraech.
    """
    teilnahme = s.get(ChatTeilnehmer, (g.name, benutzer)) if g.name else None
    if g.name:
        ungelesen = _ungelesen_zaehlen(s, g.name, benutzer, teilnahme)
        # CHAT-7b-2 (MUSS 1a): in einer RUNDE gilt für die Vorschau dieselbe
        # Grenze wie im Verlauf — wer neu (oder wieder) eintritt, sieht die
        # Nachrichten von VOR seinem Eintritt nicht. Ohne diesen Filter stand
        # der Text der letzten Nachricht hier ungefiltert in der Liste.
        bedingung = [ChatNachricht.gespraech == g.name]
        sichtbar_ab = _sichtbar_ab(s, g, benutzer)
        if sichtbar_ab is not None:
            bedingung.append(ChatNachricht.erstellt_am >= sichtbar_ab)
        # SOLL 5 (CHAT-7b-2): die eigene Vorschlags-Systemzeile („X möchte Y
        # hinzufügen“) ist für den VORSCHLAGENDEN kein „letzter Beitrag“ — für
        # die übrigen bleibt sie stehen (sie sollen zustimmen). Dieselbe
        # Bedingung wie im Ungelesen-Zähler (``_nicht_eigener_vorschlag``).
        # Eine Vorschlags-Systemzeile trägt ihren Satz NICHT in der Datenbank
        # (er entsteht beim Lesen) — als Vorschau wäre sie leer (``_zitat`` →
        # None) und verdrängte den letzten echten Beitrag. Deshalb: keine
        # Vorschlagszeilen in der Vorschau (sie stehen im Verlauf).
        letzte = s.execute(select(ChatNachricht)
                           .outerjoin(ChatRundeVorschlag,
                                      ChatRundeVorschlag.name == ChatNachricht.vorschlag)
                           .where(*bedingung,
                                  ChatNachricht.vorschlag.is_(None),
                                  _nicht_eigener_vorschlag(benutzer))
                           .order_by(ChatNachricht.erstellt_am.desc(),
                                     ChatNachricht.name.desc())
                           .limit(1)).scalar_one_or_none()
    else:
        ungelesen, letzte = 0, None
    if g.art == ART_DIREKT and g.name:
        titel, gegenueber, bild = _direkt_titel(
            s, g, benutzer, ausgeschlossene=ausgeschlossene)
    else:
        # Runden (CHAT-7b) tragen ihren Namen in `titel`; `gruppe`/`untergruppe`
        # sind NULL. Ein leerer Titel bleibt leer (die Oberfläche zeigt
        # „Runde“) — nie „None“.
        titel = str(g.titel or "").strip() or (g.untergruppe or g.gruppe or "")
        gegenueber, bild = None, ""
    # CHAT-5-UI: „darf ich hier senden?“ in DERSELBEN Antwort wie die Liste —
    # die Oberfläche blendet „Umfrage starten“ daran aus (dieselbe Aktion wie
    # „Nachricht senden“, `umfrage_anlegen` prüft `rechte.ANLEGEN`). Reine
    # Anzeige über den Rechte-Kern; kein zweiter Rechtepfad.
    darf_senden = _weiche_ja(benutzer, rechte.ANLEGEN, g=g, sitzung=s)
    kopf = {
        "name": g.name,
        "art": g.art,
        "gruppe": g.gruppe,
        "untergruppe": g.untergruppe,
        "titel": titel,
        # 1:1: das Gegenueber fuer Bild/Profil-Link; bei Gruppen leer.
        "mitglied": gegenueber,
        "bild": bild,
        "teilnehmer": _teilnehmer_aktuelle(s, g),
        "stumm": bool(teilnahme.stumm) if teilnahme is not None else False,
        # `geoeffnet: false` heisst: es gibt noch keine Gespraechszeile. Die
        # Oberflaeche holt sie beim Tipp auf den Eintrag ueber `gespraech(...)`.
        "geoeffnet": bool(g.name),
        "ungelesen": ungelesen,
        "letzte_nachricht": _zitat(s, letzte) if letzte else None,
        "letzte_am": _isoopt(letzte.erstellt_am) if letzte else None,
        # CHAT-5-UI: darf die Sitzung hier schreiben (Nachricht senden /
        # Umfrage starten)? Reine Anzeige — der Endpunkt prüft erneut.
        "darf_senden": darf_senden,
    }
    if g.art == ART_RUNDE and g.name:
        # CHAT-7b-3: die Oberfläche braucht die NAMEN der Beteiligten, um
        # Vorschläge und Mitgliederliste zu zeichnen. Nur Runden tragen das
        # Feld; bei 1:1/Gruppen FEHLT es (nicht `None`) — dieselbe Form wie
        # die Antwort von `runde_anlegen` (`_runde_kopf` → `_runde_mitglieder`).
        kopf["mitglieder"] = _runde_mitglieder(s, g.name)
    return kopf


def _teilnehmer_aktuelle(s, g: ChatGespraech) -> int:
    """Wie viele AKTUELLE Angehoerige hat die Einheit? (nicht: Teilnahmezeilen)

    Review Punkt 3: eine stehengebliebene Teilnahmezeile eines ausgetretenen
    Mitglieds ist kein Teilnehmer mehr. Gezaehlt wird daher ueber den
    Rechte-Kern (``darf`` LESEN je Konto) — und nur unter den Konten, die eine
    Teilnahmezeile haben. Neu hinzugekommene Mitglieder ohne Teilnahmezeile
    zaehlen NICHT mit: die Zahl beschreibt das Gespraech, nicht die Einheit.

    Beim 1:1-Gespraech (CHAT-7a) ist es dieselbe Regel ueber die EINE Weiche
    (``darf_direktgespraech`` LESEN je Konto): 1 solange beide dabei sind,
    nach einem Austritt nur noch die verbliebene Person — nach einer
    Anonymisierung 0 (die Teilnahmezeile ging mit dem Konto).

    CHAT-7b (Review R1, SOLL 11): in einer RUNDE sind die aktiven
    Teilnehmenden schon bekannt (``_runde_teilnahme`` filtert
    ``verlassen_am``) — die zusätzliche Rechtefrage je Konto wäre ein N+1
    ohne neue Wahrheit. Sie fällt weg: die Zahl ist die der aktiven Zeilen.
    """
    if not g.name:
        return 0
    if g.art == ART_RUNDE:
        return len(_runde_teilnahme(s, g.name))
    return sum(1 for konto in _teilnahme_konten(s, g.name)
               if _darf_lesen(s, konto, g.name))


# ── Endpunkte: Aufbewahrungsfristen (CHAT-8, Entscheidung F8) ───────────────


@whitelist(allow_guest=False)
def fristen_lesen():
    """Die Aufbewahrungsfristen des Chats in Monaten (Konzept 4.2, F8).

    Lesbar fuer jedes angemeldete Konto: die Werte gelten fuer ALLE und stehen
    so im Datenschutzhinweis („Verlauf bleibt 12 Monate“). Nur das SCHREIBEN
    ist Administrationsrecht — eine Frist, die niemand kennt, waere keine
    Zusage.

    Antwort: ``{chat_frist_gruppe_monate, chat_frist_direkt_monate,
    standard: {...}, minimum, maximum}``; die Standardwerte kommen mit, damit
    die Oberflaeche „Standard 24“ anzeigen kann, ohne sie zu kennen.
    """
    from diakronos_app import chat_aufbewahrung as aufbewahrung

    with dbmod.SessionLocal.begin() as s:
        werte = aufbewahrung.holen_einstellungen(s)
    return {
        **werte,
        "standard": dict(aufbewahrung.FRIST_STANDARD),
        "minimum": aufbewahrung.FRIST_MIN_MONATE,
        "maximum": aufbewahrung.FRIST_MAX_MONATE,
        # Die FESTEN Fristen aus 4.2 — nicht einstellbar, nur zur Anzeige.
        "nachricht_monate": aufbewahrung.FRIST_NACHRICHT_MONATE,
        "umfrage_stimmen_monate": aufbewahrung.FRIST_UMFRAGE_MONATE,
        "meldung_monate": aufbewahrung.MELDUNG_FRIST_MONATE,
    }


@whitelist(methods=["POST"], allow_guest=False)  # schreibt die Gemeinde-Single (SEC-11)
def fristen_speichern(chat_frist_gruppe_monate=None,
                      chat_frist_direkt_monate=None):
    """Aufbewahrungsfristen setzen — NUR mit Administrationsrecht (F8).

    Die Rechtefrage beantwortet der zentrale Rechte-Kern
    (``rechte.ist_admin``) — KEINE eigene Rollenlogik: HV/MV/GL duerfen den
    Chat moderieren, die Aufbewahrung der Gemeinde aber nicht verkuerzen
    (das waere eine Loeschung von Verlaeufen, die ihre Mitglieder behalten
    wollen). Geprueft wird VOR dem Schreiben und VOR jeder Wertpruefung —
    ein Nicht-Admin erfaehrt nicht, welche Werte zulaessig sind.

    Beide Werte sind Pflicht (die Karte: „Grenzen sinnvoll“), 1…120 Monate.
    Antwort: die gespeicherten Werte (wie ``fristen_lesen``).
    """
    from diakronos_app import chat_aufbewahrung as aufbewahrung

    benutzer = _benutzer()
    if not rechte.ist_admin(benutzer):
        _h()
    try:
        with dbmod.SessionLocal.begin() as s:
            aufbewahrung.setze_einstellungen(
                s, gruppe_monate=chat_frist_gruppe_monate,
                direkt_monate=chat_frist_direkt_monate,
                benutzer=benutzer, jetzt=_jetzt(),
            )
            werte = aufbewahrung.holen_einstellungen(s)
    except aufbewahrung.FristFehler as fehler:
        raise ValidationError(str(fehler)) from None
    return {**werte, "gespeichert": True}



# ── Runden (CHAT-7b) ────────────────────────────────────────────────────────


def _runde_teilnahme(s, gespraech: str) -> list[str]:
    """Konten, die in dieser Runde (noch) teilnehmen — ohne Ausgetretene.

    ``chat_teilnehmer.verlassen_am`` ist die Wahrheit über „ist noch dabei“:
    die Zeile bleibt für die Anzeige stehen, zählt aber nicht. Der Rechte-Kern
    bekommt deshalb NUR die aktiven Konten (``darf_direktgespraech`` prüft
    ``benutzer in teilnehmer``); wer die Runde verlassen hat, ist damit kein
    Teilnehmer mehr — ohne dass jemand die Zeile löscht (das wäre die
    Darstellung „Gelöschte Person“).
    """
    return sorted(
        str(konto) for konto in s.execute(
            select(ChatTeilnehmer.benutzer).where(
                ChatTeilnehmer.gespraech == gespraech,
                ChatTeilnehmer.verlassen_am.is_(None),
            )
        ).scalars().all() if konto
    )


def _runde_mitglieder(s, gespraech: str) -> list[dict[str, str]]:
    """Die AKTIVEN Teilnehmenden der Runde als ``[{mitglied, anzeigename}]``.

    CHAT-7b-3 (Vertrag 3): EINE Form und EINE Reihenfolge für alle Aufrufer —
    ``runde_anlegen``/``_runde_kopf`` und ``meine_gespraeche`` liefern dieselbe
    Liste (kein zweites Feld, keine zweite Schreibweise). Sortiert wird über
    den EINTRITT (``hinzugefuegt_am``) und dann über den Anzeigenamen, nicht
    über die Kontokennung: die Liste ist für Menschen gedacht.

    Der Name kommt aus ``_personen`` — derselben Quelle wie „Darf A B sehen?“
    und die Antwort von ``runde_anlegen``. Ausgetretene (``verlassen_am``
    gesetzt) fallen heraus; eine Sperre (CHAT-7b) entscheidet hier NICHTS —
    wer aktiv in der Runde ist, steht mit Namen drin. Mehr als ``mitglied``
    und ``anzeigename`` gibt es je Eintrag nicht.
    """
    zeilen = s.execute(
        select(Mitglied.name, Mitglied.user, ChatTeilnehmer.hinzugefuegt_am)
        .join(ChatTeilnehmer, ChatTeilnehmer.benutzer == Mitglied.user)
        .where(ChatTeilnehmer.gespraech == gespraech,
               ChatTeilnehmer.verlassen_am.is_(None))
    ).all()
    kennungen = [str(name) for name, _konto, _am in zeilen if name]
    if not kennungen:
        return []
    namen = _personen(s, kennungen)
    eintritt = {str(name): (am or datetime.min) for name, _konto, am in zeilen if name}
    reihenfolge = sorted(kennungen,
                         key=lambda k: (eintritt.get(k, datetime.min), namen.get(k, k)))
    return [{"mitglied": k, "anzeigename": namen.get(k, k)} for k in reihenfolge]


def _konto_je_mitglieder(s, mitglieder) -> dict[str, str]:
    """``{mitglied: konto}`` — EINE Abfrage, nur fest verknüpfte Konten.

    Derselbe Weg wie ``_konto_je_mitglied`` (``mitglied.user``, KEIN
    E-Mail-Rückfall): eine zweite Auflösung wäre ein zweiter Weg zum Gespräch.
    """
    kennungen = sorted({str(m) for m in (mitglieder or ()) if m})
    if not kennungen:
        return {}
    return {str(mitglied): str(konto) for mitglied, konto in s.execute(
        select(Mitglied.name, Mitglied.user).where(Mitglied.name.in_(kennungen))
    ).all() if mitglied and konto}


def _eigene_kennung(s, benutzer: str) -> str | None:
    """Mitglied-Kennung des KONTOS (``mitglied.user``) — oder ``None``.

    Fest verknüpft (kein E-Mail-Rückfall, wie ``_konto_je_mitglied`` in der
    Gegenrichtung): der Kern rechnet mit derselben Auflösung.
    """
    kennung = str(benutzer or "").strip()
    if not kennung:
        return None
    treffer = [str(n) for n in s.execute(
        select(Mitglied.name).where(Mitglied.user == kennung)
    ).scalars().all() if n]
    return treffer[0] if len(treffer) == 1 else None


def _runde_pruefen(s, benutzer: str, gespraech) -> ChatGespraech:
    """Die Runde zur Kennung — mit Leserecht über die EINE Weiche (403/404)."""
    kennung = str(gespraech or "").strip()
    if not kennung:
        throw("gespraech fehlt.")
    g = _gespraech_lesen(s, kennung)
    if g.art != ART_RUNDE:
        # Nur Runden: „Vorschlag“ und „verlassen“ haben für Gruppen- und
        # 1:1-Gespräche keine Bedeutung (dort endet die Teilnahme nie).
        throw("Das ist keine Runde.")
    _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
    return g


def _runde_kopf(s, g: ChatGespraech, benutzer: str) -> dict[str, Any]:
    """Kopf einer Runde: Titel, Zahl der Beteiligten, Ungelesen.

    ``teilnehmer`` zählt AKTIVE Beteiligte (ohne Ausgetretene). ``mitglieder``
    kommt mit, weil die Oberfläche für Namensliste und Vorschläge BEIDES
    braucht — Kennung und Anzeigename, als ``[{mitglied, anzeigename}]``
    (CHAT-7b-3, dieselbe Form wie in ``meine_gespraeche``). Es sind
    ausschliesslich die der Runde, nichts über Dritte.
    """
    teilnahme = s.get(ChatTeilnehmer, (g.name, benutzer))
    return {
        "name": g.name,
        "art": g.art,
        "titel": str(g.titel or "").strip(),
        "teilnehmer": len(_runde_teilnahme(s, g.name)),
        "mitglieder": _runde_mitglieder(s, g.name),
        "stumm": bool(teilnahme.stumm) if teilnahme is not None else False,
        "ungelesen": _ungelesen(s, g.name, benutzer),
        "erstellt_am": _isoopt(g.angelegt_am),
    }


def _runde_titel_pruefen(titel) -> str:
    """Name der Runde: nicht leer am Rand, ≤ ``RUNDE_TITEL_MAX`` Zeichen."""
    inhalt = str(titel or "").strip()
    if not inhalt:
        throw("Bitte einen Namen für die Runde eingeben.")
    if len(inhalt) > RUNDE_TITEL_MAX:
        throw(f"Der Name der Runde darf höchstens {RUNDE_TITEL_MAX} Zeichen "
              f"lang sein (eingegeben: {len(inhalt)}).")
    return inhalt


def _vorschlag_holen(s, vorschlag, benutzer: str) -> tuple[ChatRundeVorschlag, ChatGespraech]:
    """Ein Vorschlag + seine Runde — nur für AKTIVE Teilnehmende der Runde.

    Unbekannte Kennung → 404, Vorschlag einer FREMDEN Runde → 403 ohne Inhalt:
    wer nicht in der Runde ist, erfährt auch nicht, dass es ihn gibt.
    """
    kennung = str(vorschlag or "").strip()
    if not kennung:
        throw("vorschlag fehlt.")
    zeile = s.get(ChatRundeVorschlag, kennung)
    if zeile is None:
        raise DoesNotExistError("Vorschlag nicht gefunden.")
    g = _gespraech_lesen(s, zeile.gespraech)
    if g.art != ART_RUNDE:
        throw("Das ist keine Runde.")
    _erlaube(benutzer, rechte.LESEN, g=g, sitzung=s)
    return zeile, g


def _vorschlag_beschreiben(s, v: ChatRundeVorschlag) -> dict[str, Any]:
    """Antwortzeile eines Vorschlags — mit Zahlen, ohne Namen der Zustimmenden."""
    zustimmungen, benoetigt, _angenommen = _vorschlag_fortschritt(s, v)
    return {
        "name": v.name,
        "gespraech": v.gespraech,
        "mitglied": v.mitglied,
        "anzeigename": _personen(s, {v.mitglied}).get(v.mitglied),
        "stand": v.stand,
        "zustimmungen": zustimmungen,
        "benoetigt": benoetigt,
        "angelegt_am": _isoopt(v.angelegt_am),
        "entschieden_am": _isoopt(v.entschieden_am),
    }


def _vorschlag_fortschritt(s, v: ChatRundeVorschlag) -> tuple[int, int, bool]:
    """``(zustimmungen der Aktiven, benoetigt, angenommen)`` — aus AKTIVEN.

    Review R1 (MUSS 5a): Zustimmungen zählen nur, solange die zustimmende
    Person noch AKTIV dabei ist. Wer die Runde verlassen hat, zählt weder als
    Zustimmende noch als Nötig-Zustimmende — sonst bliebe ein Vorschlag offen,
    den niemand mehr annehmen kann (oder würde ohne die Betroffene „allein“
    durchgehen).
    """
    aktiv = set(_runde_teilnahme(s, v.gespraech))
    wer = str(v.vorgeschlagen_von or "")
    zustimmend = {k for k in v.zustimmungen if k in aktiv and k != wer}
    noetig = len(aktiv - {wer}) if wer else len(aktiv)
    return len(zustimmend), noetig, bool(noetig and len(zustimmend) >= noetig)


def _vorschlag_agebaut(s, v: ChatRundeVorschlag) -> None:
    """Einen offenen Vorschlag als ABGELEHNT beenden (bedingtes UPDATE).

    Nimmt den Zustimmenden die Sichtbarkeit nicht weg — der Verlauf zeigt die
    Systemzeile weiter, der Stand ist „abgelehnt“.
    """
    s.execute(
        update(ChatRundeVorschlag)
        .where(ChatRundeVorschlag.name == v.name,
               ChatRundeVorschlag.stand == VORSCHLAG_OFFEN)
        .values(stand=VORSCHLAG_ABGELEHNT, entschieden_am=_jetzt())
    )
    s.flush()


def _vorschlag_nameschild(s, v: ChatRundeVorschlag) -> tuple[str, str]:
    """``(wer schlägt vor, wen)`` — Vorname bzw. gekürzter Anzeigename.

    Wird NUR beim Anlegen der Systemzeile ausgewertet (Review R1, SOLL 8): der
    Text steht danach nicht als Personen-Kopie im Verlauf, sondern wird aus
    DIESER Zeile gebildet (``_vorschlag_verlaufszeile``).
    """
    konto = str(v.vorgeschlagen_von or "")
    eigener = _person_je_konto(s, konto) if konto else None
    wer = _personen(s, {eigener}).get(eigener) if eigener else None
    if not wer and konto:
        wer = _konto_namen(s, {konto}).get(konto)
    wer = str(wer or "").split(" ")[0] or "Jemand"
    wen = _personen(s, {v.mitglied}).get(v.mitglied) or "die Person"
    return wer, wen


def _vorschlagsnachricht(s, g: ChatGespraech, v: ChatRundeVorschlag) -> ChatNachricht:
    """Die Systemzeile „X möchte Y hinzufügen“ im Verlauf — als VERWEIS.

    Review R1 (SOLL 8): KEINE normale Nachricht der vorschlagenden Person.
    Die Zeile trägt ``autor=None``, ``autor_benutzer=None`` und KEINEN Text —
    nur ``vorschlag=<Kennung>``. Damit ist sie

      * nicht bearbeitbar/löschbar/meldbar (die Endpunkte verlangen eine
        eigene Nachricht bzw. eine Meldung; ein Systembeitrag hat weder Besitz
        noch meldbaren Text),
      * ohne Namen-Kopie im Verlauf: die Anzeige („X möchte Y hinzufügen“)
        entsteht beim LESEN aus der Vorschlagszeile,
      * bei einer Anonymisierung/Diskretion: die Zeile fällt mit dem Vorschlag
        (``_gespraech_entfernen``/DSGVO) — es bleibt kein Fremdtext stehen.
    """
    zeile = ChatNachricht(
        name=_kennung("chat-n"),
        gespraech=g.name,
        autor_benutzer=None,
        autor=None,
        text="",
        vorschlag=v.name,
        erstellt_am=_jetzt(),
    )
    s.add(zeile)
    s.flush()
    return zeile


def _vorschlag_verlaufszeile(s, v: ChatRundeVorschlag,
                             benutzer: str = "") -> dict[str, Any]:
    """Der sichtbare Satz einer Vorschlags-Systemzeile — beim LESEN gebildet.

    Der Text nennt Vornamen und Zielperson, sonst NICHTS (keine Kennungen,
    keinen Grund, keine Zwischenstände) — dieselbe Zusage wie vorher, nur ohne
    gespeicherte Namen-Kopie. Der Stand („abgelehnt“, „angenommen“) kommt aus
    der Vorschlagszeile; ist sie weg, bleibt der Satz stehen.

    CHAT-7b-3: ``eigene`` ist die Sicht der LESENDEN Person (``benutzer``) —
    dieselbe Bedeutung wie in ``_vorschlags_texte``, damit die Antwort von
    ``runde_vorschlagen`` und der Verlauf dasselbe sagen.
    """
    wer, wen = _vorschlag_nameschild(s, v)
    return {"text": _vorschlag_satz(wer, wen, v.stand), "stand": v.stand,
            "eigene": bool(benutzer) and str(v.vorgeschlagen_von or "") == str(benutzer)}


def _vorschlag_mitglied_konto(s, v: ChatRundeVorschlag) -> str | None:
    """Konto der vorgeschlagenen Person (``mitglied.user``) — oder ``None``."""
    return _konto_je_mitglieder(s, [v.mitglied]).get(v.mitglied)


def _runde_aufnehmen(s, g: ChatGespraech, v: ChatRundeVorschlag) -> bool:
    """Die vorgeschlagene Person wird Teilnehmende (nach Zustimmung ALLER).

    Eine vorhandene Zeile (früher ausgetreten) wird wiederbelebt:
    ``verlassen_am = None`` — die Person steht danach wieder als Beteiligte da,
    ohne eine zweite Zeile (Primärschlüssel ``(gespraech, benutzer)``).
    ``sichtbar_ab`` wird auf JETZT gesetzt: wer neu (oder wieder) dazukommt,
    liest nicht rückwirkend mit (Review R1, SOLL 7).

    Rückgabe ``False``, wenn es kein Konto mehr gibt — dann ist der Vorschlag
    NICHT aufgenommen und der Aufrufer beendet ihn als abgelehnt (MUSS 5c).
    """
    konto = _vorschlag_mitglied_konto(s, v)
    if not konto:
        return False
    jetzt = _jetzt()
    zeile = s.get(ChatTeilnehmer, (g.name, konto))
    if zeile is None:
        s.add(ChatTeilnehmer(gespraech=g.name, benutzer=konto, stumm=False,
                             hinzugefuegt_am=jetzt, sichtbar_ab=jetzt))
    else:
        zeile.verlassen_am = None
        zeile.hinzugefuegt_am = jetzt
        zeile.sichtbar_ab = jetzt
        zeile.letzter_lesestand = None
        zeile.letzter_lesestand_nachricht = None
    s.flush()
    return True


def _vorschlaege_beenden(s, gespraech: str, *, ausser: str | None = None,
                         nur_von: str | None = None) -> int:
    """Alle OFFENEN Vorschläge einer Runde als BEENDET schließen.

    Ohne weitere Angabe: ALLE (Austritt einer Person — jeder offene Vorschlag
    der Runde wird neu verhandelt, weil sich der Kreis geändert hat).
    ``nur_von``: nur die Vorschläge dieses Kontos.

    CHAT-7b-2 (SOLL 4): der Stand ist ``VORSCHLAG_BEENDET``, NICHT
    ``abgelehnt`` — der Kreis hat sich geändert, niemand hat dagegen gestimmt.
    Der Verlauf zeigt die Zeile weiter (die Sichtbarkeit der Zustimmenden
    bleibt), nur mit dem Stand „beendet“.
    """
    bedingung = [ChatRundeVorschlag.gespraech == gespraech,
                 ChatRundeVorschlag.stand == VORSCHLAG_OFFEN]
    if ausser:
        bedingung.append(ChatRundeVorschlag.name != ausser)
    if nur_von is not None:
        bedingung.append(ChatRundeVorschlag.vorgeschlagen_von == nur_von)
    return int(s.execute(
        update(ChatRundeVorschlag).where(*bedingung)
        .values(stand=VORSCHLAG_BEENDET, entschieden_am=_jetzt())
    ).rowcount or 0)


# ── Endpunkte: Runde anlegen (CHAT-7b) ──────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)  # legt Gespraech + Teilnahmen an (SEC-11)
def runde_anlegen(titel=None, mitglieder=None):
    """Eine benannte Runde mit 3–8 Beteiligten anlegen (Konzept S3).

    ``mitglieder`` sind die MITGLIED-Kennungen der ANDEREN (2–7); die
    anlegende Person zählt als erste Beteiligte mit. Rechte — ausschliesslich
    über den Kern: ``rechte.darf_runde_anlegen(benutzer, ziele=[…])``. Damit
    braucht es für ALLE anderen ein ``darf_direktnachricht`` (auffindbar,
    aktives Konto, NICHT gesperrt): „anlegen darf, wer alle erreichen darf“.

    Eine Sperre verhindert die Runde in BEIDE Richtungen, ohne dass die andere
    Seite davon erfährt: die Ablehnung ist 403 OHNE Inhalt — derselbe Text,
    derselbe Status wie bei „nicht erreichbar“.

    Runden sind NICHT paarweise eindeutig (mehrere Runden derselben Personen
    sind erlaubt); es gibt deshalb keinen Schlüssel und keinen
    ``IntegrityError``-Weg wie beim 1:1.

    Antwort: der Kopf der Runde (``name, art, titel, teilnehmer, mitglieder,
    stumm, ungelesen, erstellt_am``) — ``mitglieder`` als
    ``[{mitglied, anzeigename}]`` der AKTIVEN Beteiligten (CHAT-7b-3).
    """
    name = _runde_titel_pruefen(titel)
    if mitglieder in (None, ""):
        ziele: list[str] = []
    elif isinstance(mitglieder, str):
        ziele = [mitglieder.strip()] if mitglieder.strip() else []
    else:
        ziele = [str(m).strip() for m in mitglieder if str(m or "").strip()]
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.darf_runde_anlegen(benutzer, ziele=ziele):
            _h()
        eigene = _eigene_kennung(s, benutzer)
        if not eigene:
            # Ohne Mitgliedsdatensatz gibt es keine „anlegende Person“ in der
            # Runde; der Kern verlangt für die eigenen Rechte ohnehin ein
            # eigenes Mitglied (``darf_direktnachricht`` → ``selbst_nicht_aktiv``).
            _h()
        konten = _konto_je_mitglieder(s, ziele)
        # Review R1 (Kleinkram): verglichen werden MITGLIED-Kennungen mit
        # MITGLIED-Kennungen — nicht die Konto-Werte gegen die eigene Kennung.
        # Fehlt für eine genannte Person das Konto, ODER steht die eigene
        # Person unter den Zielen: dieselbe 403 ohne Inhalt (kein Rateweg).
        if len(konten) != len(set(ziele)) or eigene in set(ziele):
            _h()
        jetzt = _jetzt()
        g = ChatGespraech(
            name=_kennung("chat-rund"),
            art=ART_RUNDE,
            gruppe=None,
            untergruppe=None,
            paar_schluessel=None,
            titel=name,
            angelegt_von=benutzer or None,
            angelegt_am=jetzt,
        )
        s.add(g)
        s.flush()
        # Teilnahme am KONTO (nicht an der Mitglied-Kennung): `eigene` ist die
        # Mitglied-Kennung der anlegenden Person, `benutzer` ihr Konto.
        for konto in sorted({benutzer, *konten.values()}):
            s.add(ChatTeilnehmer(gespraech=g.name, benutzer=konto, stumm=False,
                                 hinzugefuegt_am=jetzt, sichtbar_ab=jetzt))
        s.flush()
        return _runde_kopf(s, g, benutzer)


# ── Endpunkte: Vorschlag, Zustimmung, Ablehnung (CHAT-7b) ───────────────────


@whitelist(methods=["POST"], allow_guest=False)  # schreibt Vorschlag + Systemzeile (SEC-11)
def runde_vorschlagen(gespraech=None, mitglied=None):
    """Vorschlagen, eine Person in die Runde zu holen („X möchte Y hinzufügen“).

    Recht — ausschliesslich der Kern: ``rechte.darf_runde_erweitern(benutzer,
    teilnehmer=<aktive Konten>, ziel=<mitglied>)``. Damit schlagen nur
    Teilnehmende vor, nur unter 8 Beteiligte, nur eine Person, die sie selbst
    erreichen dürfen und die nicht schon dabei ist. Der Kern bringt niemanden
    mit einer Person zusammen, die ihn (oder die er) gesperrt hat — auch nicht
    durch Dritte; nach aussen „nicht erreichbar“ (403 ohne Inhalt).

    Der Vorschlag wird NICHT sofort wirksam (Konzept S3: „nur mit Zustimmung
    der Runde“). Im Verlauf erscheint EINE Systemzeile (``chat_nachricht.
    vorschlag``) ohne weitere Daten und ohne Namen-Kopie — der Satz entsteht
    beim Lesen aus der Vorschlagszeile (Review R1, SOLL 8).

    Ein zweiter OFFENER Vorschlag derselben Person in derselben Runde ist
    abgewiesen (400) und in der Datenbank durch einen partiellen Unique-Index
    verhindert.

    Antwort: ``{vorschlag: {…}, nachricht: {…}}``.
    """
    ziel = str(mitglied or "").strip()
    if not ziel:
        throw("mitglied fehlt.")
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _runde_pruefen(s, benutzer, gespraech)
        teilnehmer = _runde_teilnahme(s, g.name)
        if not rechte.darf_runde_erweitern(benutzer, teilnehmer=teilnehmer, ziel=ziel):
            # Gleiche Auskunft wie „nicht erreichbar“ — der Grund „gesperrt“
            # bleibt im Kern und geht hier nie nach außen.
            _h()
        offen = s.execute(
            select(ChatRundeVorschlag.name).where(
                ChatRundeVorschlag.gespraech == g.name,
                ChatRundeVorschlag.mitglied == ziel,
                ChatRundeVorschlag.stand == VORSCHLAG_OFFEN,
            )
        ).scalar_one_or_none()
        if offen is not None:
            throw("Für diese Person liegt schon ein offener Vorschlag vor.")
        zeile = ChatRundeVorschlag(
            name=_kennung("chat-vorschlag"),
            gespraech=g.name,
            vorgeschlagen_von=benutzer or None,
            mitglied=ziel,
            stand=VORSCHLAG_OFFEN,
            zustimmende="",
            angelegt_am=_jetzt(),
        )
        try:
            with s.begin_nested():
                s.add(zeile)
                s.flush()
        except IntegrityError:
            throw("Für diese Person liegt schon ein offener Vorschlag vor.")
        nachricht = _vorschlagsnachricht(s, g, zeile)
        return {
            "vorschlag": _vorschlag_beschreiben(s, zeile),
            "nachricht": _zeile(s, nachricht,
                                namen={}, konto_namen={}, ich=benutzer,
                                system=_vorschlag_verlaufszeile(s, zeile,
                                                                benutzer=benutzer)),
        }


@whitelist(methods=["POST"], allow_guest=False)  # tritt Teilnahme hinzu (SEC-11)
def runde_zustimmen(vorschlag=None):
    """Einem Vorschlag zustimmen (Konzept S3: „alle bisherigen ausser X“).

    Gezählt werden NUR Zustimmungen AKTIVER Teilnehmender (Review R1, MUSS 5a):
    wer die Runde verlassen hat, stimmt nicht mehr mit und zählt auch nicht
    mehr als Nötig-Zustimmende. Nötig sind so viele, wie es aktive
    Teilnehmende ohne die vorschlagende Person gibt. Erreicht die Zahl diese
    Grenze, wird die Person Teilnehmende und der Vorschlag steht auf
    ``angenommen``.

    GEGEN RENNEN (MUSS 5c): zuerst wird die GESPRÄCHSZEILE gesperrt
    (``with_for_update``), dann die Vorschlagszeile gelesen (``refresh``),
    erst DANACH gezählt und mit einem bedingten ``UPDATE`` (``WHERE stand =
    'offen'``) geschrieben. Zwei gleichzeitige Zustimmungen können die Grenze
    damit nicht überschreiten und nicht doppelt zählen; die Erhöhung des
    Teilnehmerstands passiert ebenfalls hinter der Sperre.

    Bei Annahme wird die Erweiterung ERNEUT über den Kern gefragt (MUSS 5c):
    ``rechte.darf_runde_erweitern(vorgeschlagen_von, teilnehmer=<aktive>,
    ziel=<mitglied>)``. Hat sich in der Zwischenzeit etwas geändert (Ziel ohne
    Konto, inzwischen gesperrt, Vorschlagender gegangen), endet der Vorschlag
    als „abgelehnt“ — nie still „angenommen“ ohne Aufnahme. Die Größe ≤ 8 prüft
    derselbe Kern erneut (MUSS 5b). EINE Ablehnung beendet ihn ohnehin.

    Der Vorschlagende stimmt nicht mit (er hat ihn ja gemacht). Jede Person
    zählt GENAU EINMAL; eine wiederholte Zustimmung ist idempotent.

    Antwort: ``{vorschlag: {…}, teilnehmer: <neue Zahl>, angenommen: <bool>}``.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        # (1) Die Runde ist der Serialisierungspunkt: jede Zustimmung zu
        #     IRGENDEINEM Vorschlag dieser Runde läuft hier nacheinander.
        zeile, g = _vorschlag_holen(s, vorschlag, benutzer)
        s.execute(select(ChatGespraech.name)
                  .where(ChatGespraech.name == g.name).with_for_update())
        # (2) Zeile unter der Sperre neu lesen — ein paralleler Lauf kann den
        #     Stand bis hierher geändert haben.
        s.refresh(zeile)
        if zeile.stand != VORSCHLAG_OFFEN:
            throw("Der Vorschlag ist bereits entschieden.")
        if str(zeile.vorgeschlagen_von or "") == benutzer:
            throw("Über den eigenen Vorschlag stimmt die Runde ab.")
        if benutzer in zeile.zustimmungen:
            # Dieselbe Person zaehlt EINMAL: mehrfaches Zustimmen erhoeht die
            # Zahl nicht (sonst koennte eine Person die Grenze „alle bisherigen
            # Teilnehmenden“ allein erreichen).
            return {
                "vorschlag": _vorschlag_beschreiben(s, zeile),
                "teilnehmer": len(_runde_teilnahme(s, g.name)),
                "angenommen": False,
            }
        jetzt = _jetzt()
        bisher = [k for k in zeile.zustimmungen if k]
        gesetzt = s.execute(
            update(ChatRundeVorschlag)
            .where(ChatRundeVorschlag.name == zeile.name,
                   ChatRundeVorschlag.stand == VORSCHLAG_OFFEN)
            .values(zustimmende=", ".join(sorted({*bisher, benutzer})),
                    entschieden_von=benutzer or None,
                    entschieden_am=jetzt)
        ).rowcount or 0
        if not gesetzt:
            throw("Der Vorschlag ist bereits entschieden.")
        s.refresh(zeile)
        zustimmungen, noetig, angenommen = _vorschlag_fortschritt(s, zeile)
        if angenommen:
            # (3) ERNEUT über den Kern fragen (MUSS 5b/5c): Größe ≤ 8, Ziel
            #     erreichbar, Vorschlagender noch Teilnehmender.
            teilnehmer_jetzt = _runde_teilnahme(s, g.name)
            erlaubt = rechte.darf_runde_erweitern(
                zeile.vorgeschlagen_von, teilnehmer=teilnehmer_jetzt,
                ziel=zeile.mitglied)
            aufgenommen = bool(erlaubt) and _runde_aufnehmen(s, g, zeile)
            if not aufgenommen:
                # Nie still „angenommen“ ohne Aufnahme: der Vorschlag endet.
                _vorschlag_agebaut(s, zeile)
                s.refresh(zeile)
                return {
                    "vorschlag": _vorschlag_beschreiben(s, zeile),
                    "teilnehmer": len(_runde_teilnahme(s, g.name)),
                    "angenommen": False,
                }
            beendet = s.execute(
                update(ChatRundeVorschlag)
                .where(ChatRundeVorschlag.name == zeile.name,
                       ChatRundeVorschlag.stand == VORSCHLAG_OFFEN)
                .values(stand=VORSCHLAG_ANGENOMMEN)
            ).rowcount or 0
            if not beendet:
                throw("Der Vorschlag ist bereits entschieden.")
            s.refresh(zeile)
        s.flush()
        return {
            "vorschlag": _vorschlag_beschreiben(s, zeile),
            "teilnehmer": len(_runde_teilnahme(s, g.name)),
            "angenommen": angenommen,
        }


@whitelist(methods=["POST"], allow_guest=False)  # beendet den Vorschlag (SEC-11)
def runde_ablehnen(vorschlag=None):
    """Einen Vorschlag ablehnen — JEDE Gegenstimme beendet ihn (Konzept S3).

    Nur Teilnehmende (Weiche), nicht der Vorschlagende selbst: über den
    eigenen Vorschlag stimmt die Runde ab, nicht der Vorschlagende.

    Antwort: ``{vorschlag: {…}, angenommen: false}``.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        zeile, g = _vorschlag_holen(s, vorschlag, benutzer)
        s.execute(select(ChatGespraech.name)
                  .where(ChatGespraech.name == g.name).with_for_update())
        s.refresh(zeile)
        if zeile.stand != VORSCHLAG_OFFEN:
            throw("Der Vorschlag ist bereits entschieden.")
        if str(zeile.vorgeschlagen_von or "") == benutzer:
            throw("Über den eigenen Vorschlag stimmt die Runde ab.")
        gesetzt = s.execute(
            update(ChatRundeVorschlag)
            .where(ChatRundeVorschlag.name == zeile.name,
                   ChatRundeVorschlag.stand == VORSCHLAG_OFFEN)
            .values(stand=VORSCHLAG_ABGELEHNT, entschieden_von=benutzer or None,
                    entschieden_am=_jetzt())
        ).rowcount or 0
        if not gesetzt:
            throw("Der Vorschlag ist bereits entschieden.")
        s.refresh(zeile)
        return {"vorschlag": _vorschlag_beschreiben(s, zeile), "angenommen": False}


@whitelist(methods=["POST"], allow_guest=False)  # beendet die Teilnahme (SEC-11)
def runde_verlassen(gespraech=None):
    """Eine Runde verlassen — die Teilnahme endet, die Person bleibt benannt.

    ``chat_teilnehmer.verlassen_am`` wird gesetzt; die Zeile BLEIBT. Das ist
    der Unterschied zur Löschung (Art. 17): dort fällt die Zeile und die
    anderen sehen „Gelöschte Person“. Hier sieht jeder weiter den Namen —
    „ist gegangen“ ist keine Löschung.

    Danach: LESEN nein (der Kern bekommt das Konto nicht mehr in
    ``teilnehmer``), Senden nein, Vorschlag nein. Wieder eintreten geht nur
    über einen neuen Vorschlag mit Zustimmung der Runde.

    Review R1 (MUSS 5e/5f): ALLE offenen Vorschläge der Runde enden mit dem
    Austritt — die eigenen (die Person könnte sie nicht mehr vertreten) wie
    die, die ANDERE für sie gemacht haben (sie kann nicht mehr aufgenommen
    werden, ohne dass jemand zustimmt, der sie gar nicht mehr in der Runde
    will): der Kreis hat sich geändert, es wird neu verhandelt. Sie enden
    ``beendet`` (CHAT-7b-2, SOLL 4) — das ist NICHT dasselbe wie „abgelehnt“:
    niemand hat gegen etwas gestimmt, der Vorschlag ist mit dem Austritt
    hinfällig geworden.

    GEGEN RENNEN (CHAT-7b-2, SOLL 3): wie ``runde_zustimmen``/``runde_ablehnen``
    wird ZUERST die GESPRÄCHSZEILE gesperrt (``with_for_update``) — sonst
    könnten eine Zustimmung (die die Grenze prüft und die Person aufnimmt) und
    dieser Austritt aneinander vorbeilaufen.

    Antwort: ``{gespraech, teilnehmer, verlassen: true}``.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _runde_pruefen(s, benutzer, gespraech)
        # (1) Die Runde ist der Serialisierungspunkt — dieselbe Sperre wie in
        #     `runde_zustimmen`/`runde_ablehnen` (SOLL 3).
        s.execute(select(ChatGespraech.name)
                  .where(ChatGespraech.name == g.name).with_for_update())
        zeile = s.get(ChatTeilnehmer, (g.name, benutzer))
        if zeile is None or zeile.verlassen_am is not None:
            throw("Du bist nicht (mehr) Teil dieser Runde.")
        zeile.verlassen_am = _jetzt()
        s.flush()
        # ALLE offenen Vorschläge der Runde enden (eigene und fremde) — der
        # Kreis hat sich geändert. Stand `beendet`, kein „abgelehnt“.
        _vorschlaege_beenden(s, g.name)
        return {"gespraech": g.name,
                "teilnehmer": len(_runde_teilnahme(s, g.name)),
                "verlassen": True}


# ── Endpunkte: Kontaktsperre (CHAT-7b) ──────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)  # schreibt die Sperre (SEC-11)
def kontakt_sperren(mitglied=None):
    """„Nicht mehr anschreiben lassen“ — sofort, ohne Begründung (Konzept S3).

    Recht — ausschliesslich der Kern: ``rechte.darf_kontakt_sperren(benutzer,
    ziel_mitglied)``. Gesperrt wird immer das KONTO der Person; ohne Konto gibt
    es nichts zu sperren (403 ohne Inhalt).

    Die Sperre wirkt im Kern in BEIDE Richtungen: weder die sperrende noch die
    gesperrte Person kann ein NEUES 1:1 beginnen (``darf_direktnachricht`` →
    NEIN „gesperrt“), und im BESTEHENDEN 1:1 kann niemand mehr senden
    (``darf_direktgespraech`` → ANLEGEN prüft ``darf_direktnachricht``).

    Nach aussen ist „gesperrt“ NICHT zu erkennen: die Antwort der gesperrten
    Seite ist exakt die von „nicht erreichbar“ — derselbe Text, derselbe
    Status, in jedem Endpunkt dieses Moduls. Der Grund bleibt im Kern.

    Idempotent (Unique ``(benutzer, gesperrt)``): zweimal sperren ändert nichts.

    Antwort: ``{mitglied, gesperrt: true}`` — nur die eigene Seite sieht sie.
    """
    ziel = str(mitglied or "").strip()
    if not ziel:
        throw("mitglied fehlt.")
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.darf_kontakt_sperren(benutzer, ziel):
            _h()
        konto = _konto_je_mitglieder(s, [ziel]).get(ziel)
        if not konto:
            _h()
        vorhanden = s.execute(
            select(RechteKontaktsperre.id).where(
                RechteKontaktsperre.benutzer == benutzer,
                RechteKontaktsperre.gesperrt == konto,
            )
        ).scalar_one_or_none()
        if vorhanden is None:
            try:
                with s.begin_nested():
                    s.add(RechteKontaktsperre(benutzer=benutzer, gesperrt=konto,
                                              angelegt_am=_jetzt()))
                    s.flush()
            except IntegrityError:
                # Zwei gleichzeitige Aufrufe: die Sperre steht schon.
                pass
        return {"mitglied": ziel, "gesperrt": True}


@whitelist(methods=["POST"], allow_guest=False)  # loescht die Sperre (SEC-11)
def kontakt_entsperren(mitglied=None):
    """Eine Kontaktsperre aufheben — nur die EIGENE Richtung.

    Recht — ausschliesslich der Kern: ``rechte.darf_kontakt_sperren``
    (dieselbe Frage, eine Sperre zu setzen und zu löschen). Gelöscht wird NUR
    die Zeile ``(benutzer, gesperrt)``: hat die andere Seite ebenfalls
    gesperrt, bleibt deren Sperre stehen und wirkt weiter — das ist ihre
    Entscheidung, nicht die eigene.

    Idempotent: ohne Sperre gibt es nichts zu löschen, die Antwort ist dieselbe.

    Antwort: ``{mitglied, gesperrt: false}``.
    """
    ziel = str(mitglied or "").strip()
    if not ziel:
        throw("mitglied fehlt.")
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.darf_kontakt_sperren(benutzer, ziel):
            _h()
        konto = _konto_je_mitglieder(s, [ziel]).get(ziel)
        if not konto:
            _h()
        s.execute(delete(RechteKontaktsperre).where(
            RechteKontaktsperre.benutzer == benutzer,
            RechteKontaktsperre.gesperrt == konto,
        ))
        return {"mitglied": ziel, "gesperrt": False}


@whitelist(methods=["GET"], allow_guest=False)  # SEC-11: rein lesend, NUR GET
def meine_sperren():
    """Die EIGENEN Kontaktsperren — nur die eigene Seite, rein lesend (GET).

    ``methods=["GET"]`` ist ausdrücklich gesetzt, obwohl GET der Lesevorgabe
    entspricht: der SEC-11-Wächter liest den Namen „…_sperren“ als SCHREIBEND
    und verlangt für schreibende Namen ``POST``. Die ausdrückliche Menge sagt
    ihm, dass dieser Endpunkt NUR liest (er ändert nichts) — und sperrt PUT/
    DELETE/PATCH zusätzlich aus.

    Antwort: ``{sperren: [{mitglied, anzeigename, bild, angelegt_am}]}``.

    KEIN Konto-Feld (Review R1, MUSS 3): ``benutzer`` IST die E-Mail-Adresse
    (Login) — die gehört nicht in eine Antwort, die das Beschreiben der Person
    nur zeigen soll. Auch der Anzeigename kommt aus ``mitglied`` (gekürzt über
    ``personen_anzeige``), nicht aus dem Konto.

    Wer WEN gesperrt hat, erfährt niemand sonst: die Liste ist auf
    ``benutzer = <eigene Kennung>`` eingegrenzt, und keine andere Antwort
    dieses Moduls nennt eine Sperre.

    Kein N+1 (Review R1, SOLL 11): Konten, Mitglied-Kennungen und Namen kommen
    aus je EINER Abfrage — nicht aus einem ``_person_je_konto`` je Sperre.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        zeilen = s.execute(
            select(RechteKontaktsperre.gesperrt, RechteKontaktsperre.angelegt_am)
            .where(RechteKontaktsperre.benutzer == benutzer)
            .order_by(RechteKontaktsperre.angelegt_am)
        ).all()
        konten = [str(konto) for konto, _am in zeilen if konto]
        # EINE Abfrage: Konto -> Mitglied-Kennung (dieselbe feste Kopplung
        # ``mitglied.user`` wie ``_konto_je_mitglied`` in der Gegenrichtung).
        mitglied_je_konto: dict[str, str] = {}
        if konten:
            for mitglied, konto in s.execute(
                select(Mitglied.name, Mitglied.user).where(Mitglied.user.in_(konten))
            ).all():
                if mitglied and konto and str(konto) not in mitglied_je_konto:
                    mitglied_je_konto[str(konto)] = str(mitglied)
        kennungen = set(mitglied_je_konto.values())
        namen = _personen(s, kennungen)
        bilder = _bilder(s, kennungen)
        sperren = []
        for konto, am in zeilen:
            mitglied = mitglied_je_konto.get(str(konto))
            if not mitglied:
                # Konto ohne Mitgliedsdatensatz (z. B. Administrator): es gibt
                # nichts zu benennen — Kennung und Name fehlen, das Konto selbst
                # bleibt draußen (MUSS 3).
                continue
            sperren.append({
                "mitglied": mitglied,
                "anzeigename": namen.get(mitglied),
                "bild": bilder.get(mitglied) or "",
                "angelegt_am": _isoopt(am),
            })
    return {"sperren": sperren}


def _bilder(s, kennungen) -> dict[str, str]:
    """Bildadresse je MITGLIED-Kennung — EINE Abfrage, wie überall präfigiert.

    Ohne Bild (kein Foto, gelöschte Person) bleibt der Eintrag leer; die
    Oberfläche zeigt dann ihren Platzhalter. Dieselbe Regel wie
    ``_suche_bild`` (kein toter Verweis auf eine entfernte Datei).
    """
    namen = {str(k) for k in kennungen if k}
    if not namen:
        return {}
    from diakronos_app.api.profile import foto_mit_praefix

    ergebnis: dict[str, str] = {}
    for kennung, foto, status in s.execute(
        select(Mitglied.name, Mitglied.foto, Mitglied.status).where(Mitglied.name.in_(namen))
    ).all():
        if not foto or str(status or "").strip().casefold() == "geloescht":
            continue
        ergebnis[str(kennung)] = foto_mit_praefix(str(foto))
    return ergebnis


__all__ = [
    "CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE",
    "CHAT_GLOCKE_DOCTYPE",
    "CHAT_UMFRAGE_GLOCKE_DOCTYPE",
    "ERINNERUNG_VORLAUF_STUNDEN",
    "FRAPPE_MODULE",
    "GLOCKE_SPERRE",
    "MELDUNGEN_MAX",
    "MELDUNG_KONTEXT",
    "SEITE",
    "SEITE_MAX",
    "TITEL_MAX",
    "aendern",
    "fristen_lesen",
    "fristen_speichern",
    "chat_glocken_buendeln",
    "chat_umfrage_erinnerungen",
    "direkt_oeffnen",
    "gespraech_anlegen",
    "glocken_merker",
    "kontakt_entsperren",
    "kontakt_sperren",
    "lesestand_setzen",
    "loeschen",
    "meine_sperren",
    "meldung_entscheiden",
    "meldung_senden",
    "meldungen_liste",
    "meine_gespraeche",
    "reaktion_setzen",
    "runde_ablehnen",
    "runde_anlegen",
    "runde_verlassen",
    "runde_vorschlagen",
    "runde_zustimmen",
    "senden",
    "stumm_setzen",
    "verlauf",
]
