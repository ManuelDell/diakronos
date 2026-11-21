"""CHAT-2 (S1): Gruppen- und Untergruppenchat — Handmodell, kein Frappe-DocType.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 3.3 (Entwurf) und die
Entscheidungen Manuel 17.11.2026 in Abschnitt 9 (F1–F11). Diese Datei legt
NUR die vier Tabellen der Stufe S1 an:

``chat_gespraech``
    EIN Gespräch je Gruppe bzw. je Untergruppe (F4: getrennte Räume). Der
    Datensatz entsteht LAZY beim ersten Zugriff (``chat.dienst``) — kein
    Massen-Insert über alle Gruppen. ``art`` unterscheidet heute nur
    ``gruppe``/``untergruppe``; Direktnachrichten und Runden (S3) kommen mit
    CHAT-7, die Spalte ist dafür schon da.

``chat_teilnehmer``
    Wer im Gespräch ist, mit ``stumm`` (F3: jede Person für sich) und
    ``letzter_lesestand`` (eine Spalte, KEINE eigene Lesestand-Tabelle — sonst
    gäbe es zwei Wahrheiten über „wer ist im Gespräch“, Konzept 3.3).
    Primärschlüssel ``(gespraech, benutzer)``.

``chat_nachricht``
    Text bis 4 000 Zeichen (Absätze bleiben), ``antwort_auf`` (genau eine
    Nachricht), Soft-Delete (``geloescht_am``/``geloescht_von``), „bearbeitet“
    über ``bearbeitet_am``. Index ``(gespraech, erstellt_am)`` — rückwärts
    gelesen ist das der „neueste zuerst“-Zugriff und zugleich der
    „seit X“-Abruf. ZWEI Verfasserspalten (Entscheidung Operator im Review):
    ``autor_benutzer`` (Konto, ``user.name``) trägt den BESITZ und entscheidet
    über die Rechte, ``autor`` (``mitglied.name``) trägt die ANZEIGE und wird
    bei einer Löschung (Art. 17) auf die neutrale Kennung umgehängt.

``chat_reaktion``
    Festes Set (``REAKTIONEN``), EINE je Person und Nachricht —
    Primärschlüssel ``(nachricht, benutzer)``.

CHAT-5 (S2) — UMFRAGEN — drei weitere Tabellen (Konzept Abschnitt 1/S2 und
Abschnitt 9, F5: jedes Mitglied darf starten, Standard ANONYM, je Umfrage
wählbar):

``chat_umfrage``
    EINE Umfrage je ``chat_nachricht``: die Umfrage erscheint als Nachricht im
    Verlauf, und der Verweis steht RÜCKWÄRTS von der Nachricht
    (``chat_nachricht.umfrage``) — so bleiben Reihenfolge, Lesestand,
    Soft-Delete und Zitate unverändert die Regeln der Nachricht. Frage,
    2–15 Optionen, ``mehrfach``, ``anonym`` (Standard ``true``), Frist
    (``frist_am``) ODER offen bis zur Schließung, ``geschlossen_am``.
    CHAT-4b ergänzt ``erinnert_am``: der Merker der EINEN Erinnerung 24 h vor
    der Frist (``chat_umfrage_erinnerungen``) — ein Zeitpunkt je Umfrage,
    keine Zeile je Person.

``chat_umfrage_option``
    Die Auswahl der Umfrage, PK ``(umfrage, nummer)`` — ``nummer`` ist
    zugleich die Reihenfolge der Anzeige. Keine freie Kennung: die Optionen
    werden immer im Block geschrieben und nie einzeln verwiesen.

``chat_stimme``
    Eine Stimme, PK ``(umfrage, option, benutzer)``. Diese Zeile gibt es NUR
    bei einer OFFENEN Umfrage. Bei einer ANONYMEN Umfrage steht statt ihrer
    eine ``chat_umfrage_abgabe`` — eine Zeile ohne jeden Bezug zur gewählten
    Option (Konzept S2: „technisch: keine Zeile mit Personenbezug wird
    geschrieben“).

``chat_umfrage_abgabe``
    „hat abgestimmt“-Marke, PK ``(umfrage, benutzer)`` und sonst NICHTS.
    Sie ist die Sperre gegen die zweite Abgabe (anonyme Stimmen sind nach
    Abgabe endgültig — Entscheidung Operator) und der Zähler „N haben
    abgestimmt“. Aus ihr lässt sich keine Option ableiten, auch nicht durch
    den Administrator: die Information steht in keiner Spalte.

CHAT-6 ergänzt die fünfte Tabelle:

``chat_meldung``
    Eine Meldung zu EINER Nachricht: ``grund`` aus einem FESTEN Set
    (``MELDEGRUENDE``, Konzept 2.5), ``freitext`` bis 500 Zeichen, ``stand``
    offen/erledigt/verworfen, wer sie wann bearbeitet hat. EINE offene Meldung
    je (Nachricht, Melder) — als partieller Unique-Index, weil nach einer
    Entscheidung (erledigt/verworfen) eine neue Meldung derselben Person
    wieder möglich sein muss. ``melder`` ist ein Konto-Verweis
    (``user_null``): bei einer Löschung (Art. 17) verschwindet die Herkunft
    der Meldung, die Moderationsentscheidung bleibt nachvollziehbar.

CHAT-4a ergänzt die sechste Tabelle:

``chat_glocke``
    Der Merker der GEBÜNDELTEN Glocke (Konzept 1/S1 „eine In-App-Meldung
    (Glocke) gebündelt: ‚Chor: 3 neue Nachrichten' nach 5 Minuten Ruhe"):
    je (Gespräch, Konto) EINE Zeile mit dem Anker ``stand``/``stand_am``/
    ``stand_nachricht`` (der Lesestand beim Glocken), ``merker_am`` (die
    neueste schon geglockte Nachricht), ``geglockt_am`` und ``gelesen_am``.
    Ohne ihn würde jeder Joblauf (alle 1–2 Minuten) dieselbe Nachricht erneut
    glocken. Die ZAHL der Glocke kommt aus dem Lesestand
    (``_ungelesen_zaehlen``), nicht aus dem Merker. Die Zeile ist
    AUSDRÜCKLICH KEIN Lesestand — der steht in
    ``chat_teilnehmer.letzter_lesestand``; „gelesen“ (markiert die Glocke als
    gelesen) und „geglockt“ (verhindert eine zweite Glocke) sind zwei Fragen.

Bewusst NICHT hier (spätere Karten): Push-Abonnements (CHAT-10), Anhänge
(CHAT-9) und der Löschjob mit den Aufbewahrungsfristen (CHAT-8).

CHAT-7a (S3/1:1) — DIREKTNACHRICHTEN
------------------------------------
Kein eigenes Tabellenpaar: ein Direktgespräch ist eine Zeile in
``chat_gespraech`` mit ``art = 'direkt'``, ``gruppe = NULL`` und zwei Zeilen in
``chat_teilnehmer``. Damit gelten Verlauf, Lesestand, Reaktionen, Umfragen,
Meldungen und Soft-Delete OHNE Sonderfall — und der Rechte-Kern fragt je Konto
(``darf_direktgespraech(..., teilnehmer=…)``) statt je Gruppe.

Genau EIN Gespräch je Personenpaar (Konzept 10.1 Punkt 4) sichern ZWEI Dinge:
``chat_gespraech.paar_schluessel`` (sortiertes Kontenpaar, getrennt mit einem
Steuerzeichen ``\x1f`` — PostgreSQL-Textfelder verbieten das NUL-Byte)
und der partielle Unique-Index ``uq_chat_gespraech_paar``. Die Reihenfolge des
Anlegens ist damit gleichgültig; zwei gleichzeitige Aufrufe erzeugen eine Zeile
und einen ``IntegrityError``, den der Endpunkt wie beim Lazy-Anlegen auffängt.

DSGVO (Konzept 4.3): ``chat_nachricht.autor_benutzer`` ist eine Konto-Spalte
(``user_null`` — sie verschwindet mit dem Konto), ``chat_nachricht.autor`` ist
die MITGLIED-Kennung, die die Anonymisierung auf die neutrale Kennung
UMHÄNGT, damit der Verlauf lesbar bleibt. ``chat_reaktion.benutzer`` und
``chat_teilnehmer.benutzer`` sind Konto-Spalten (Zeile fällt).
``chat_gespraech.angelegt_von`` ist ein Konto-Verweis (``user_null``). Die
Freitexte stehen im Inventar unter ``protokoll``.

Umfragen (CHAT-5): ``chat_umfrage.frage`` ist Freitext (``protokoll``),
``chat_stimme.benutzer`` und ``chat_umfrage_abgabe.benutzer`` sind
Konto-Spalten. Bei einer OFFENEN Umfrage bleibt der ZÄHLER stehen, wenn die
Person geht — die Stimme fällt (namentliche Stimmen sind Verhaltensdaten, die
mit der Person verschwinden). Bei einer anonymen Umfrage ist die
``chat_umfrage_abgabe``-Zeile ersatzlos weg; der Zähler je Option steht in
``chat_umfrage_option.stimmen`` und trägt keinen Personenbezug.

CHAT-7b (S3: Runden 3–8 und Blockieren)
---------------------------------------
**Runden** sind KEINE neue Gesprächsfamilie: ``art = 'runde'``, ``gruppe =
NULL``, ``paar_schluessel = NULL``, ``titel`` = Name der Runde, 3–8 Zeilen in
``chat_teilnehmer``. Verlauf, Lesestand, Reaktionen, Umfragen, Meldungen und
Soft-Delete gelten damit OHNE Sonderfall, und der Rechte-Kern fragt je Konto
(``darf_direktgespraech``, Teilnehmende aus ``chat_teilnehmer``) — genau wie
im 1:1. Anders als das 1:1 ist eine Runde NICHT paarweise eindeutig: dieselben
Personen dürfen mehrere Runden haben (``uq_chat_gespraech_paar`` greift nur bei
``art = 'direkt'``).

**Verlassen** (``chat_teilnehmer.verlassen_am``): die Zeile bleibt stehen, die
Person ist aber keine Teilnehmerin mehr. Das ist ABSICHTLICH etwas anderes als
eine Löschung (Art. 17), bei der die Zeile fällt und die anderen „Gelöschte
Person“ sehen: wer eine Runde verlässt, bleibt für die anderen eine benannte
Person — er ist nur nicht mehr dabei.

**Vorschläge** (``chat_runde_vorschlag``): „X möchte Y hinzufügen“ ist ein
Vorgang der Runde, keine Nachricht an Y. Hinzugefügt wird erst, wenn ALLE
bisherigen Teilnehmenden außer X zugestimmt haben; eine Ablehnung beendet den
Vorschlag. Der Verlauf zeigt dazu EINE Systemnachricht ohne weitere Daten.
Der zwischenzeitliche Zustand (wer hat schon zugestimmt) steht in der Zeile
selbst (``stand``) — es gibt keine Abstimmungstabelle je Person: die
Zustimmungen werden gezählt, nicht gespeichert (Konzept S3: „schlicht
halten“); eine Zustimmung ist wiederholbar und idempotent.

**Blockieren** (``rechte_kontaktsperre``, Modell in ``rechte.py``): wirkt
ausschließlich im Rechte-Kern (``darf_direktnachricht`` → NEIN „gesperrt“, in
beide Richtungen) — die Sperre ist eine Zeile des Rechtesystems, keine
Chat-Tabelle, damit kein zweiter Weg an ihr vorbeiführt. Nach außen ist der
Grund „gesperrt“ nicht von „nicht erreichbar“ zu unterscheiden.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
#: ``text`` als SQL-Ausdruck — NICHT als `from sqlalchemy import text` führen:
#: in ``ChatUmfrageOption`` heißt eine SPALTE ``text`` und verdeckt den Namen im
#: Klassenrumpf, dann scheitert ``server_default=sql_text("0")`` mit
#: „'MappedColumn' object is not callable“ (im CHAT-5-Lauf passiert).
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Gesprächsarten. S1 kennt die beiden Gruppen-Räume; ``direkt`` gehört zu S3
#: (CHAT-7a, 1:1), ``runde`` zu CHAT-7b und wird hier nicht angelegt.
ART_GRUPPE = "gruppe"
ART_UNTERGRUPPE = "untergruppe"
#: 1:1-Gespräch (CHAT-7a): ``gruppe`` ist NULL, der Raum sind die
#: Teilnehmenden. Genau EINES je Personenpaar — die Datenbank sichert das über
#: ``chat_gespraech.paar_schluessel`` (sortiertes Kontenpaar, Unique-Index).
ART_DIREKT = "direkt"
#: Benannte Runde mit 3–8 Beteiligten (CHAT-7b, Konzept S3). Wie das 1:1 ohne
#: Gruppe (``gruppe`` NULL) — der Raum sind die Teilnehmenden; ``titel`` ist der
#: Name der Runde und der EINZIGE Ort, an dem er steht. Kein
#: ``paar_schluessel``: eine Runde ist kein Personenpaar, und mehrere Runden
#: derselben Personen sind ausdrücklich erlaubt (der Unique-Index
#: ``uq_chat_gespraech_paar`` greift nur bei ``art = 'direkt'``).
ART_RUNDE = "runde"
ARTEN = (ART_GRUPPE, ART_UNTERGRUPPE, ART_DIREKT, ART_RUNDE)

#: Grenzen einer Runde (Konzept S3: „3–8 benannte Beteiligte“) — INKLUSIVE der
#: anlegenden Person. ``RUNDE_MAX`` ist zugleich die Grenze für das Hinzufügen
#: (``rechte.darf_runde_erweitern``). Die Zahlen stehen hier, weil Modell,
#: Endpunkt und Rechte-Kern dieselbe Grenze nennen müssen.
RUNDE_MIN = 3
RUNDE_MAX = 8

#: Höchstlänge des Rundennamens (dieselbe Spalte wie ``chat_gespraech.titel``).
RUNDE_TITEL_MAX = 140

#: Zustände eines Vorschlags „X möchte Y hinzufügen“ (Tabelle
#: ``chat_runde_vorschlag``). ``offen`` ist der einzige Zustand, in dem
#: zugestimmt werden kann; ``angenommen`` (Person ist Teilnehmende) und
#: ``abgelehnt`` (eine Gegenstimme beendet den Vorschlag) sind abschließend.
#: ``beendet`` (CHAT-7b-2, SOLL 4) heißt: der Vorschlag ist HINFÄLLIG geworden,
#: ohne dass jemand dagegen gestimmt hat — der Kreis der Runde hat sich
#: geändert (Austritt), der Vorgang wird neu verhandelt.
VORSCHLAG_OFFEN = "offen"
VORSCHLAG_ANGENOMMEN = "angenommen"
VORSCHLAG_ABGELEHNT = "abgelehnt"
VORSCHLAG_BEENDET = "beendet"
VORSCHLAG_STAENDE: tuple[str, ...] = (
    VORSCHLAG_OFFEN, VORSCHLAG_ANGENOMMEN, VORSCHLAG_ABGELEHNT, VORSCHLAG_BEENDET,
)

#: Höchstlänge einer Nachricht (Konzept Abschnitt 1/S1: „Text bis 4 000
#: Zeichen“). Gezählt werden ZEICHEN (``len(text)``), nicht Bytes — ein Emoji
#: ist ein Zeichen, auch wenn es in UTF-8 vier Bytes belegt.
NACHRICHT_MAX = 4000

#: Bearbeiten einer eigenen Nachricht nur innerhalb dieses Fensters
#: (Konzept Abschnitt 1/S1: „15 Minuten“). Löschen ist jederzeit möglich —
#: für die eigene Nachricht wie für die Moderation.
BEARBEITEN_MINUTEN = 15

#: Das feste Reaktionsset (Konzept Abschnitt 1/S1). Es ist eine geschlossene
#: Liste, keine freie Eingabe: die Oberfläche zeigt genau diese sechs, und der
#: Endpunkt weist alles andere ab (``ValidationError``).
REAKTIONEN: tuple[str, ...] = ("👍", "❤", "🙏", "✅", "😀", "😢")

#: Umfrage (CHAT-5, Konzept S2): Grenzen aus der Tabelle in Abschnitt 1 —
#: „Frage, 2–15 Optionen“. Die Frage ist so lang wie eine Nachricht erlaubt
#: sein soll, aber deutlich kürzer: sie ist eine Überschrift, kein Aufsatz.
FRAGE_MAX = 300
#: Höchstlänge einer Option („Probe am Samstag um 18 Uhr“).
OPTION_MAX = 140
#: Grenzen der Optionszahl. Unter 2 wäre es keine Abstimmung, über 15 kann
#: niemand am Handy sinnvoll entscheiden.
OPTIONEN_MIN = 2
OPTIONEN_MAX = 15
#: Unterhalb dieser Zahl Abgegebener steht der Hinweis an der Umfrage
#: („Ergebnis bei wenigen Teilnehmenden erratbar“, Karte CHAT-5).
HINWEIS_AB = 5
#: CHAT-9a (Konzept S4, Zeile „Erwähnung“): höchstens so viele Erwähnungen je
#: Nachricht. Was darüber kommt, wird STILL verworfen (der Endpunkt meldet
#: keinen Fehler — er verrät damit auch nicht, wie viele es waren).
ERWAEHNUNGEN_MAX = 20
#: Die fünf Meldegründe (Konzept 2.5: „Beleidigung, Spam, persönliche Daten,
#: falsche Person, Sonstiges“). Gespeichert wird der stabile Schlüssel, nicht
#: die Anzeige — die Oberfläche übersetzt. Ein geschlossenes Set wie
#: ``REAKTIONEN``: der Endpunkt weist alles andere ab.
MELDEGRUENDE: tuple[str, ...] = (
    "beleidigung",
    "spam",
    "persoenliche_daten",
    "falsche_person",
    "sonstiges",
)

#: Höchstlänge des Freitexts einer Meldung (Konzept 2.5: „Freitext bis 500
#: Zeichen“). Gezählt werden ZEICHEN, nicht Bytes.
MELDUNG_FREITEXT_MAX = 500

#: Stand einer Meldung. ``offen`` ist der einzige Stand, in dem die Moderation
#: noch etwas tun muss; ``erledigt`` (Nachricht entfernt) und ``verworfen``
#: (Meldung trägt nicht) sind abschließend.
MELDUNG_OFFEN = "offen"
MELDUNG_ERLEDIGT = "erledigt"
MELDUNG_VERWORFEN = "verworfen"
MELDUNG_STAENDE: tuple[str, ...] = (MELDUNG_OFFEN, MELDUNG_ERLEDIGT, MELDUNG_VERWORFEN)

#: Die zwei Entscheidungen des Endpunkts ``meldung_entscheiden``
#: (Karte CHAT-6): Nachricht entfernen oder Meldung verwerfen.
MELDUNG_ENTSCHEIDUNGEN: tuple[str, ...] = ("entfernen", "verwerfen")

#: CHAT-4a: Ruhezeit vor der gebündelten Glocke (Konzept 1/S1: „nach 5 Minuten
#: Ruhe, nicht je Nachricht“). Erst wenn im Gespräch 5 Minuten lang nichts
#: Neues geschrieben wurde, geht EINE Glocke je Person heraus.
GLOCKE_RUHE_MINUTEN = 5

# ── CHAT-12a: ANHÄNGE (Konzept S4, F11) ─────────────────────────────────────
#: Höchstgröße EINES Anhangs in Bytes (Konzept S4: „10 MB je Datei“). Die
#: Grenze steht hier, weil Endpunkt, Speicher-Schreibvorgang und Meldung
#: dieselbe Zahl nennen müssen.
ANHANG_MAX_BYTES = 10 * 1024 * 1024
#: Höchstzahl Anhänge je Nachricht (Konzept S4: „3 Anhänge je Nachricht“).
ANHAENGE_MAX = 3
#: Höchstzahl Anhänge je KONTO und KALENDERTAG (Konzept-Kostenrechnung,
#: Abschnitt 3.4). Überschritten → 429 wie bei den übrigen Grenzen.
ANHAENGE_PRO_TAG = 20
#: Höchstlänge des ANGEZEIGTEN Dateinamens (Karte: „dateiname (bereinigt, max
#: 120)“). Er ist reine Anzeige — der Speicher-Schlüssel ist eine eigene,
#: technische Kennung.
ANHANG_NAME_MAX = 120
#: Wie lange ein „offener“ Anhang (hochgeladen, aber keiner Nachricht
#: zugeordnet) liegen bleiben darf (Karte: „älter als 24 h räumt ein Job weg“).
ANHANG_OFFEN_STUNDEN = 24
#: Review R1/3: Höchstlänge der Kurzfassung des letzten Entsorgungs-Fehlers.
ENTSORGUNG_FEHLER_MAX = 200
#: Review R1/4: Aufbewahrung der Hochlade-Marken in TAGEN. Zwei Tage, nicht
#: einer: die Tagesgrenze rechnet ab lokaler Mitternacht, ein Lauf am Folgetag
#: darf die Marken des Vortags noch nicht weggenommen haben.
HOCHLADUNG_AUFBEWAHRUNG_TAGE = 2
#: Die ERLAUBTEN Typen (Konzept S4: „Bilder jpg/png/webp/heic, PDF, kleine
#: Audio-Dateien (mp3/m4a/ogg/opus)“). Geprüft wird der aus den MAGIC BYTES
#: erkannte Typ (``files.binary_content_type``), nie der Client-Typ.
#:
#: ``audio/mp4`` deckt ``.m4a`` (MP4-Container, ``ftyp``) — dieselbe Magie
#: erkennt auch ``.mp4``-VIDEO. Video ist nicht Teil des Konzepts, und der
#: Container allein unterscheidet es nicht: deshalb gilt für ``audio/mp4``
#: zusätzlich, dass der Client den Typ als Audio deklariert haben muss
#: (``_anhang_typ``) — ein Video-Upload deklariert ``video/mp4``.
ANHANG_TYPEN: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    # HEIC/HEIF: die Magie ist ein ISO-BMFF-``ftyp`` mit ``heic``/``heix``/
    # ``heim``/``heis``/``hevc``/``mif1`` — ``binary_content_type`` kennt sie
    # NICHT (es meldet für jeden ``ftyp`` ``audio/mp4``), deshalb steht die
    # Erkennung in ``api.chat._anhang_typ``.
    "image/heic": ".heic",
    "application/pdf": ".pdf",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
}
#: Die Bildtypen — nur sie werden INLINE ausgeliefert (Konzept S4:
#: „Vorschau nur für Bilder“); alles andere geht als ``attachment``.
ANHANG_BILDER: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/heic"}
)


class ChatGespraech(Base):
    """Ein Gespräch je Gruppe/Untergruppe (lazy angelegt) oder je Personenpaar."""

    __tablename__ = "chat_gespraech"
    __table_args__ = (
        # EIN Gespräch je Einheit — ZWEI partielle Indizes statt EINES
        # UniqueConstraint: in PostgreSQL und SQLite gilt NULL nie als gleich,
        # ein Constraint über ``(art, gruppe, untergruppe)`` ließe also
        # beliebig viele Zeilen mit ``untergruppe IS NULL`` zu (also beliebig
        # viele Gruppen-Gespräche derselben Gruppe). Die Teilbedingung macht
        # die Regel für beide Fälle wahr (Review CHAT-2, Punkt 2).
        # ``paar_schluessel IS NULL`` hält die Direktgespräche draußen: deren
        # ``gruppe`` ist NULL, und die Rechte des Kerns fragen je Konto
        # (``chat_teilnehmer``), nicht je Gruppe.
        Index("uq_chat_gespraech_einheit", "art", "gruppe", unique=True,
              sqlite_where=sql_text("untergruppe IS NULL AND paar_schluessel IS NULL"),
              postgresql_where=sql_text("untergruppe IS NULL AND paar_schluessel IS NULL")),
        Index("uq_chat_gespraech_einheit_ug", "art", "gruppe", "untergruppe",
              unique=True,
              sqlite_where=sql_text("untergruppe IS NOT NULL"),
              postgresql_where=sql_text("untergruppe IS NOT NULL")),
        # CHAT-7a: EIN 1:1-Gespräch je Personenpaar. Der Schlüssel ist das
        # SORTIERTE Kontenpaar (``a\x1fb`` mit ``a < b``), damit die
        # Reihenfolge des Anlegens keine zweite Zeile erzeugen kann; der
        # partielle Unique-Index lässt ihn nur bei ``art = 'direkt'`` greifen
        # (Gruppen-Gespräche tragen NULL und kollidieren nicht).
        Index("uq_chat_gespraech_paar", "paar_schluessel", unique=True,
              sqlite_where=sql_text("art = 'direkt'"),
              postgresql_where=sql_text("art = 'direkt'")),
        Index("ix_chat_gespraech_gruppe", "gruppe"),
        Index("ix_chat_gespraech_untergruppe", "untergruppe"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: ``gruppe`` / ``untergruppe`` / ``direkt`` (S1 + S3/CHAT-7a).
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Hauptgruppe — bei einer Untergruppe ist das ihre Gruppe.
    #: Bei einem Direktgespräch ``NULL``: der Raum sind die Teilnehmenden.
    gruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    untergruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Nur bei ``art = 'direkt'``: das sortierte Kontenpaar der beiden
    #: Teilnehmenden (``kleineres`` + ``\x1f`` + ``groesseres``, s.
    #: ``api.chat.PAAR_TRENNER``). Trägt den Unique-Index
    #: ``uq_chat_gespraech_paar`` — die Eindeutigkeit steht damit in der
    #: Datenbank, nicht nur im Lazy-Anlegen (zwei gleichzeitige Aufrufe).
    paar_schluessel: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: Anzeigetitel. Leer heißt: die Oberfläche nimmt den Gruppennamen.
    #: Bei einer RUNDE (CHAT-7b) ist das der Name der Runde — der einzige Ort,
    #: an dem er steht (Konzept S3: „benannte Beteiligte“).
    titel: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Konto, das das Gespräch angelegt hat (das erste schreibende Mitglied).
    angelegt_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    angelegt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: Gesetzt, wenn das Gespräch stillgelegt ist (z. B. Untergruppe aufgelöst).
    #: Ab dann liest niemand mehr (dieselbe Regel wie ``_gruppe_lebt``).
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class ChatTeilnehmer(Base):
    """Teilnahme einer Person an einem Gespräch — mit Stumm und Lesestand."""

    __tablename__ = "chat_teilnehmer"
    __table_args__ = (
        # Der Lesezugriff „nimm mich“ läuft über den Benutzer.
        Index("ix_chat_teilnehmer_benutzer", "benutzer"),
    )

    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), primary_key=True
    )
    #: Login-Name (``user.name``) — dieselbe Kennung wie überall im Rechtesystem.
    benutzer: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name"), primary_key=True
    )
    #: F3: jede Person schaltet für SICH stumm. Keine Glocke, der Zähler bleibt.
    #: Boolean mit ``server_default=sql_text("false")`` (PostgreSQL) — dasselbe
    #: Muster wie ``rechte_modul``/``rechte_objekt`` (``rechte.py``).
    stumm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    hinzugefuegt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: Zeitstempel der ZULETZT gelesenen Nachricht (``chat_nachricht.erstellt_am``
    #: plus Kennung). Alles danach ist ungelesen. Es gibt KEINE Liste „wer hat
    #: was gelesen“ — sichtbar ist nur die Summe (F2, Konzept 4.5).
    letzter_lesestand: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Kennung der zuletzt gelesenen Nachricht — nötig, weil zwei Nachrichten
    #: denselben Zeitstempel tragen können (Sekundengenauigkeit auf PostgreSQL).
    letzter_lesestand_nachricht: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: CHAT-7b: Wann die Person die RUNDE verlassen hat (``runde_verlassen``).
    #: Die Zeile wird NICHT gelöscht — es gibt zwei völlig verschiedene Dinge:
    #: „ist gegangen“ (diese Spalte gesetzt, die Person bleibt für die anderen
    #: eine benannte Person) und „Konto gelöscht“ (die Zeile fällt, die anderen
    #: sehen „Gelöschte Person“). Ein gelöschtes Konto und ein Austritt sähen
    #: sonst gleich aus. Gesetzt = keine Teilnahme mehr (der Kern bekommt das
    #: Konto nicht mehr in ``teilnehmer``), Lesestand und ``stumm`` bleiben als
    #: Geschichte stehen.
    verlassen_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: CHAT-7b (Review R1, SOLL 7): ab wann diese Person den VERLAUF sieht.
    #: Beim ersten Beitritt die Zeit des Beitritts, nach einem Austritt die des
    #: WIEDEREINTRITTS — wer neu dazukommt, liest nicht rückwirkend mit, was
    #: vorher geschrieben wurde. Beim 1:1 bleibt das Feld leer (dort sieht man
    #: von Anfang an alles).
    sichtbar_ab: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )


class ChatNachricht(Base):
    """Eine Nachricht im Verlauf. Soft-Delete lässt die Lücke stehen."""

    __tablename__ = "chat_nachricht"
    __table_args__ = (
        # „Neueste zuerst“ (rückwärts gelesen) UND „seit X“ (vorwärts) laufen
        # über denselben Index (Konzept 3.3).
        Index("ix_chat_nachricht_gespraech_erstellt", "gespraech", "erstellt_am"),
        # Antworten einer Nachricht (Anzeige „N Antworten“).
        Index("ix_chat_nachricht_antwort_auf", "antwort_auf"),
        # CHAT-5: die Umfrage einer Nachricht (0 oder 1). Der UNIQUE-Index
        # macht daraus „höchstens EINE“; das Umfrage-Modell verweist
        # RÜCKWÄRTS auf die Nachricht — so bleiben Reihenfolge, Lesestand und
        # Soft-Delete die Regeln der Nachricht und brauchen keinen zweiten Weg.
        Index("uq_chat_nachricht_umfrage", "umfrage", unique=True),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), nullable=False
    )
    #: Der BESITZ: das Konto (``user.name``), das die Nachricht geschrieben hat.
    #: Er entscheidet über die Rechte — ``rechte.darf(..., besitzer=…)``
    #: vergleicht Konto gegen Konto — und schließt die eigenen Nachrichten aus
    #: dem Ungelesen-Zähler aus. NULLABLE, weil Konten ohne Mitgliedsdatensatz
    #: (Administrator, HV über eine RechteGruppenrolle) senden dürfen und sich
    #: dann nur über diese Spalte ausweisen. DSGVO: ``user_null`` — der Besitz
    #: verschwindet mit dem Konto, der Verlauf bleibt.
    autor_benutzer: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    #: Die ANZEIGE — ein VERWEIS auf die Person, keine Kontokennung: die Spalte
    #: zeigt auf ``mitglied.name`` (dieselbe Form wie ``beitrag.autor``) und
    #: darf NULL sein (Konto ohne Mitgliedsdatensatz). Grund für diese zweite
    #: Spalte ist Konzept 4.3: nach einer Löschung (Art. 17) hängt die
    #: Anonymisierung die MITGLIED-Kennung auf die neutrale Kennung um — der
    #: Verlauf behält seinen Autor, obwohl die anderen ein Recht auf ihren
    #: Gesprächsstoff haben. Der Anzeigename kommt aus ``personen_anzeige``
    #: („Gelöschte Person“ nach der Löschung).
    autor: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("mitglied.name"), nullable=True
    )
    #: Der Text. Bleibt bei einem Soft-Delete in der Datenbank (nur für die
    #: Meldestelle lesbar — CHAT-6); die Oberfläche zeigt „Nachricht gelöscht“.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Bezug auf genau EINE Nachricht (flacher Verlauf, WhatsApp-Modell).
    antwort_auf: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("chat_nachricht.name"), nullable=True
    )
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    bearbeitet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: Soft-Delete: wer (Konto) und wann. Der Verlauf behält die Zeile.
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    geloescht_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    #: Grund einer Moderations-Entfernung (Pflicht bei fremder Nachricht,
    #: CHAT-6). Eigene Löschung braucht keinen.
    entfernt_grund: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: CHAT-5: die Umfrage, die an DIESER Nachricht hängt (0 oder 1, im
    #: UNIQUE-Index `uq_chat_nachricht_umfrage`). Der Verweis läuft von der
    #: Nachricht zur Umfrage und nicht umgekehrt, damit der Verlauf EINE
    #: Sortierung behält: eine Umfrage ist eine Nachricht wie jede andere —
    #: Lesestand, Zitat, Soft-Delete und Reaktionen greifen ohne Sonderfall.
    umfrage: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("chat_umfrage.name"), nullable=True
    )
    #: CHAT-7b (Review R1, SOLL 8): eine SYSTEMZEILE des Verlaufs. Steht hier die
    #: Kennung eines ``chat_runde_vorschlag``, ist die Nachricht der sichtbare
    #: Satz „X möchte Y hinzufügen“ — gebildet beim LESEN aus der Vorschlagszeile.
    #: Deshalb: kein ``autor_benutzer`` (nicht bearbeitbar/löschbar/meldbar),
    #: ``text`` leer und keine Namen-Kopie, die eine Anonymisierung stehen ließe.
    #: NULL = normale Nachricht.
    vorschlag: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("chat_runde_vorschlag.name"), nullable=True
    )


class ChatReaktion(Base):
    """EINE Reaktion je Person und Nachricht (Primärschlüssel)."""

    __tablename__ = "chat_reaktion"

    nachricht: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_nachricht.name"), primary_key=True
    )
    benutzer: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name"), primary_key=True
    )
    #: Eines der sechs Zeichen aus ``REAKTIONEN`` (geprüft im Endpunkt; ein
    #: CHECK wäre je Dialekt eine eigene Baustelle — der Endpunkt ist der
    #: einzige Schreibweg).
    reaktion: Mapped[str] = mapped_column(String(8), nullable=False)
    erstellt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class ChatUmfrage(Base):
    """Eine Umfrage zu EINER Nachricht im Gespräch (S2, F5).

    Die Umfrage hat keine eigene Position im Verlauf: sie hängt an einer
    Nachricht (``chat_nachricht.umfrage``), und diese Nachricht trägt den Text
    (die Frage). Damit gilt für Reihenfolge, Lesestand, Zitat und Löschen
    KEINE zweite Regel.

    ``anonym`` ist der STANDARD (F5). Die beiden Zählwege sind getrennt:
    anonym → ``chat_umfrage_abgabe`` (nur „hat abgestimmt“, ohne Option) und
    der Zähler ``chat_umfrage_option.stimmen``; offen → ``chat_stimme`` je
    Person und Option (namentlich, bis zur Frist änderbar).
    """

    __tablename__ = "chat_umfrage"
    __table_args__ = (
        # „Welche Umfrage hängt an dieser Nachricht?“ — der Verweis läuft
        # rückwärts, gesucht wird er trotzdem; der UNIQUE-Index liegt auf der
        # Nachricht (``uq_chat_nachricht_umfrage``).
        Index("ix_chat_umfrage_gespraech", "gespraech"),
        # Der Scheduler sucht „fällige, noch offene“ Umfragen (CHAT-5).
        Index("ix_chat_umfrage_frist", "frist_am"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: Das Gespräch — redundant zur Nachricht, damit Frist und Schließung ohne
    #: Join über den Verlauf laufen und ein Verweis nie in ein fremdes
    #: Gespräch zeigen kann (beides wird beim Anlegen geprüft).
    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), nullable=False
    )
    #: Die Frage (Freitext, ``FRAGE_MAX`` Zeichen).
    frage: Mapped[str] = mapped_column(Text, nullable=False)
    #: Mehrfachauswahl erlaubt? Bei ``false`` gilt genau EINE Option je Person.
    mehrfach: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    #: ANONYM (Standard ``true``, F5). Bei ``true`` wird NIE eine Zeile mit
    #: Personenbezug zur Option geschrieben.
    anonym: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sql_text("true")
    )
    #: Frist als Wandzeit der Gemeinde (ohne Zeitzone, wie alle Fachzeiten).
    #: ``NULL`` = offen bis zur Schließung durch Ersteller/Moderation.
    frist_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    #: Gesetzt bei Schließung (Frist erreicht ODER vorzeitig). Ab hier keine
    #: Stimme mehr; das Ergebnis bleibt stehen.
    geschlossen_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: WER geschlossen hat. ``NULL`` = automatisch zur Frist (Scheduler) —
    #: eine Schließung durch einen Menschen ist damit unterscheidbar.
    geschlossen_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    #: CHAT-4b: Wann die EINE Erinnerung „endet morgen“ verschickt wurde.
    #: Der Merker ist die ganze Umfrage (nicht die Person — die Empfängerliste
    #: ist der Rechte-Kern, eine Zeile je Konto wäre doppelt geführt). ``NULL``
    #: = noch nicht erinnert; der Job ``chat_umfrage_erinnerungen`` setzt ihn
    #: im selben Vorgang wie die Glocken und läuft dadurch genau einmal.
    #: Kein Personenbezug: ein Zeitpunkt, keine Kennung.
    erinnert_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class ChatUmfrageOption(Base):
    """Eine Antwortmöglichkeit — PK ``(umfrage, nummer)``.

    ``nummer`` ist Reihenfolge UND Kennung: die Optionen werden immer im Block
    geschrieben, es gibt keinen Weg, eine einzelne Option zu referenzieren.

    ``stimmen`` ist der ZÄHLER. Bei einer anonymen Umfrage ist er der EINZIGE
    Träger des Ergebnisses (es gibt keine Stimmenzeile je Person); bei einer
    offenen Umfrage ist er die Summe der ``chat_stimme``-Zeilen und wird im
    selben Vorgang fortgeschrieben — damit die Anzeige ohne Zählabfrage
    auskommt und die Zusage „Zähler bleibt“ nach einer Löschung hält.
    """

    __tablename__ = "chat_umfrage_option"

    umfrage: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_umfrage.name"), primary_key=True
    )
    #: 1 … ``OPTIONEN_MAX`` — zugleich die Anzeigereihenfolge.
    nummer: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(String(OPTION_MAX), nullable=False)
    stimmen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sql_text("0")
    )


class ChatStimme(Base):
    """Eine Stimme — NUR bei einer OFFENEN Umfrage (PK ``(umfrage, option, benutzer)``).

    Die Zeile ist der Personenbezug: sie sagt, WER WAS gewählt hat. Deshalb
    entsteht sie ausschliesslich bei ``chat_umfrage.anonym = false``; bei einer
    anonymen Umfrage gibt es sie nicht (auch nicht mit ``NULL``-Option — eine
    Zeile, deren Option fehlt, wäre wieder eine Marke, und für die gibt es
    ``chat_umfrage_abgabe``).

    ``benutzer`` ist ein Konto-Verweis und fällt bei einer Löschung (Art. 17);
    der Zähler in ``chat_umfrage_option.stimmen`` bleibt.
    """

    __tablename__ = "chat_stimme"
    __table_args__ = (
        # Zweiter Index auf den Benutzer: „meine Stimmen in dieser Umfrage“
        # und die Abfrage der Anonymisierung nach Konto.
        Index("ix_chat_stimme_benutzer", "benutzer"),
        # Die Option MUSS zu DIESER Umfrage gehören — als zusammengesetzter
        # Fremdschlüssel, nicht als Zusage im Endpunkt: ``chat_umfrage_option``
        # hat den PK ``(umfrage, nummer)``, eine Stimme mit fremder Nummer
        # würde sonst den Zähler einer nicht existierenden Option treffen.
        # Die Migration legt ihn genauso an (`alembic check` ist still).
        ForeignKeyConstraint(
            ["umfrage", "option"],
            ["chat_umfrage_option.umfrage", "chat_umfrage_option.nummer"],
            name="fk_chat_stimme_option_chat_umfrage_option",
        ),
    )

    umfrage: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_umfrage.name"), primary_key=True
    )
    #: Die gewählte Option (``chat_umfrage_option.nummer``).
    option: Mapped[int] = mapped_column(Integer, primary_key=True)
    benutzer: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name"), primary_key=True
    )
    erstellt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class ChatUmfrageAbgabe(Base):
    """„Hat abgestimmt“-Marke OHNE Option (PK ``(umfrage, benutzer)``).

    Nur bei ANONYMEN Umfragen. Die Tabelle hat BEWUSST keine Spalte für die
    gewählte Option (Karte CHAT-5: „KEINE Zeile mit Personenbezug zur
    gewählten Option“) — damit ist auch für den Administrator nicht
    rekonstruierbar, wer wie gestimmt hat.

    Sie trägt zwei Zusagen: (1) die zweite Abgabe ist gesperrt (anonyme
    Stimmen sind endgültig), (2) „N haben abgestimmt“. Der Primärschlüssel IST
    die Sperre — eine zweite Abgabe scheitert in der Datenbank, nicht erst im
    Code.
    """

    __tablename__ = "chat_umfrage_abgabe"
    __table_args__ = (
        Index("ix_chat_umfrage_abgabe_benutzer", "benutzer"),
    )

    umfrage: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_umfrage.name"), primary_key=True
    )
    benutzer: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name"), primary_key=True
    )
    erstellt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class ChatMeldung(Base):
    """Eine Meldung zu EINER Nachricht (Konzept 2.5, Karte CHAT-6).

    ``melder`` ist ein KONTO-Verweis (``user.name``) — dieselbe Kennung, gegen
    die der Rechte-Kern rechnet, und die Spalte, die die Anonymisierung nullt.
    Die gemeldete Person erfährt nicht, WER gemeldet hat: weder die Antwort
    der Meldung noch der Verlauf nennt den Melder.
    """

    __tablename__ = "chat_meldung"
    __table_args__ = (
        # EINE OFFENE Meldung je (Nachricht, Melder) — partiell, weil nach
        # einer Entscheidung (erledigt/verworfen) dieselbe Person dieselbe
        # Nachricht erneut melden dürfen muss. Ein voller Unique-Constraint
        # würde das für immer verbieten (CHAT-2-Muster, Review Punkt 2).
        Index("uq_chat_meldung_offen", "nachricht", "melder", unique=True,
              sqlite_where=sql_text("stand = 'offen'"),
              postgresql_where=sql_text("stand = 'offen'")),
        # Die Moderationsliste fragt nach dem Stand („alle offenen“).
        Index("ix_chat_meldung_stand", "stand", "erstellt_am"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    nachricht: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_nachricht.name"), nullable=False
    )
    #: Konto der meldenden Person (``user.name``). DSGVO: ``user_null`` — die
    #: Herkunft der Meldung verschwindet mit dem Konto; der Vorgang bleibt.
    melder: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    #: Einer der fünf Schlüssel aus ``MELDEGRUENDE`` (im Endpunkt geprüft; ein
    #: CHECK wäre je Dialekt eine eigene Baustelle — der Endpunkt ist der
    #: einzige Schreibweg, wie bei ``chat_reaktion.reaktion``).
    grund: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Freitext bis 500 Zeichen (optional) — der Grund „Sonstiges“ braucht ihn.
    freitext: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ``offen`` / ``erledigt`` / ``verworfen`` (``MELDUNG_STAENDE``).
    stand: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MELDUNG_OFFEN,
        server_default=sql_text("'offen'"),
    )
    #: Wer die Meldung entschieden hat (Konto) und wann.
    bearbeitet_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    bearbeitet_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Grund der Entscheidung (Pflicht beim Entfernen, Konzept 2.5; optional
    #: beim Verwerfen). Er steht ZUSÄTZLICH an der Nachricht
    #: (``chat_nachricht.entfernt_grund``), weil der Verlauf ihn zeigt.
    entscheidung_grund: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class ChatGlocke(Base):
    """Gebündelte Chat-Glocke: was je (Gespräch, Konto) schon geglockt wurde.

    Konzept 1/S1 („eine In-App-Meldung (Glocke) gebündelt: ‚Chor: 3 neue
    Nachrichten' nach 5 Minuten Ruhe, nicht je Nachricht“) und 3.1.

    Der Job ``api.chat.chat_glocken_buendeln`` liest je Lauf die Paare
    (Gespräch, Person), die ihre Ruhezeit hinter sich haben, und schreibt je
    Person EINE Zeile in ``Notification Log``. Damit ein zweiter Lauf
    (1–2 Minuten später) dieselbe Nachricht NICHT erneut glockt, steht hier der
    Stand; er ist ein ANKER, kein Zähler:

    * ``stand``     — der Lesestand DIESER Person zum Zeitpunkt der letzten
                      Glocke (Kopie von ``chat_teilnehmer.letzter_lesestand``)
                      bzw. der Beitritt, wenn noch nie gelesen wurde. Was
                      davor liegt, war beim Glocken schon gelesen — es zählt
                      nie in die nächste Zahl.
    * ``stand_am``  — derselbe Anker als Zeitstempel (``stand`` kann nach
                      einer Löschung der Nachricht NULL werden, s. CHAT-8).
    * ``stand_nachricht`` — Kennung zum Zeitstempel (zwei Nachrichten können
                      denselben Zeitstempel tragen).
    * ``merker_am`` — die neueste Nachricht, die beim letzten Glocken schon da
                      war. Der Job nimmt nur Paare auf, bei denen es DANACH
                      noch etwas gibt — ohne diesen Wert würde ein zweiter Lauf
                      dieselbe Nachricht erneut als „neu“ sehen (die Glocke
                      wäre dann nie fertig).

    Die ZAHL in der Glocke kommt NICHT von hier, sondern aus
    ``_ungelesen_zaehlen`` (Lesestand): „N = ungelesene seit letztem
    Lesestand“. Der Stand entscheidet nur, OB seit der letzten Glocke etwas
    Neues kam — und ab wo das nächste Bündel zählt.

    Kein Lesestand: „geglockt“ und „gelesen“ sind zwei Fragen. Der Lesestand
    bleibt ``chat_teilnehmer.letzter_lesestand``; ``lesestand_setzen`` markiert
    zusätzlich die Glocke dieses Gesprächs als gelesen (``gelesen_am``).

    DSGVO (Konzept 4.3): ``benutzer`` ist eine KONTO-Spalte
    (``user_null``/``zeile_loeschen``) — der Merker verschwindet mit dem
    Konto. Er enthält KEINEN Text und KEINEN Absender, nur Kennungen.
    """

    __tablename__ = "chat_glocke"
    __table_args__ = (
        # Der Job fragt je Gespräch nach dem Stand („was ist neu seit …“).
        Index("ix_chat_glocke_gespraech", "gespraech"),
        # Review R1 (MUSS 2): der Job steigt über den MERKER in die Paare ein
        # („gibt es überhaupt einen Anker?“), nicht über die Nachrichten.
        Index("ix_chat_glocke_benutzer", "benutzer"),
    )

    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), primary_key=True
    )
    #: Konto (``user.name``) — dieselbe Kennung wie im Rechtesystem.
    benutzer: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name"), primary_key=True
    )
    #: Kennung der Nachricht, bis zu der geglockt wurde (``chat_nachricht.name``).
    #: ``ON DELETE SET NULL`` (Review R1/f): löscht CHAT-8 Nachrichten, wird
    #: der Verweis genullt — ``stand_am`` bleibt als Anker erhalten.
    stand: Mapped[str | None] = mapped_column(
        String(140),
        ForeignKey("chat_nachricht.name", ondelete="SET NULL"),
        nullable=True,
    )
    #: Derselbe Anker als Zeitstempel (siehe Klassen-Doku). NULL = Anker
    #: unbekannt (dann zählt ab dem Beitritt bzw. allem).
    stand_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Kennung zum Anker-Zeitstempel (``chat_nachricht.name``, KEIN FK: die
    #: Nachricht darf verschwinden, ohne dass der Merker verschwindet).
    stand_nachricht: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Die neueste Nachricht, die beim letzten Glocken schon da war.
    merker_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Wann zuletzt geglockt wurde (Wandzeit der Gemeinde, ohne Zeitzone).
    geglockt_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    #: Wann die Glocke dieses Gesprächs als GELESEN markiert wurde
    #: (``lesestand_setzen``). Gesetzt = die Glocke im
    #: ``Notification Log`` wurde auf ``read`` gestellt.
    gelesen_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )


class ChatRundeVorschlag(Base):
    """Vorschlag „X möchte Y in die Runde holen“ (CHAT-7b, Konzept S3).

    Hinzugefügt wird NUR mit Zustimmung der Runde: ALLE bisherigen
    Teilnehmenden außer der vorschlagenden Person müssen zustimmen, EINE
    Ablehnung beendet den Vorschlag (der Endpunkt ``runde_zustimmen`` /
    ``runde_ablehnen`` rechnet das, nicht diese Tabelle).

    Die Zeile ist bewusst schlicht:

    * ``gespraech`` + ``mitglied`` (die VORGESCHLAGENE Person, eine
      Mitglied-Kennung) + ``vorgeschlagen_von`` (Konto) + ``angelegt_am``.
    * ``stand`` — ``offen`` / ``angenommen`` / ``abgelehnt`` / ``beendet``
      (``VORSCHLAG_STAENDE``; ``beendet`` = mit dem Austritt hinfällig
      geworden, ohne Gegenstimme — CHAT-7b-2, SOLL 4). ``offen`` ist der
      einzige Zustand, in dem
      abgestimmt werden kann; der Zustandswechsel ist ein bedingtes
      ``UPDATE`` (``WHERE stand = 'offen'``), damit zwei gleichzeitige
      Gegenstimmen nicht beide „gewinnen“.
    * ``entschieden_am``/``entschieden_von`` (Konto) — wer den Vorschlag
      beendet hat (bei Annahme: die letzte zustimmende Person). Nur für den
      Nachweis; der VERLAUF nennt niemanden (die Systemnachricht sagt nur
      „X möchte Y hinzufügen“, ohne weitere Daten).

    Der partielle Unique-Index ``uq_chat_runde_vorschlag_offen`` lässt je
    (Runde, Person) höchstens EINEN offenen Vorschlag zu — nach einer
    Entscheidung darf dieselbe Person erneut vorgeschlagen werden.

    DSGVO (Review R1, MUSS 4): ``vorgeschlagen_von``/``entschieden_von`` sind
    Konto-Spalten (``user_null`` — die Zeile bleibt, das Konto verschwindet),
    ``zustimmende`` ist eine Konten-Liste (``WERT_SPALTEN`` Art ``liste``) und
    ``mitglied`` eine Mitglied-Kennung ohne FK, die das Inventar auf die
    neutrale Kennung umhängt. Die Zeile fällt NICHT mit dem Konto: die
    Systemzeile im Verlauf (``chat_nachricht.vorschlag``) zeigen die anderen
    weiter.
    """

    __tablename__ = "chat_runde_vorschlag"
    __table_args__ = (
        # EIN OFFENER Vorschlag je (Runde, vorgeschlagene Person) — partiell,
        # weil nach einer Entscheidung ein neuer Vorschlag möglich sein muss
        # (dasselbe Muster wie ``uq_chat_meldung_offen``).
        Index("uq_chat_runde_vorschlag_offen", "gespraech", "mitglied",
              unique=True,
              sqlite_where=sql_text("stand = 'offen'"),
              postgresql_where=sql_text("stand = 'offen'")),
        # Die Abfrage des Endpunkts: „offene Vorschläge dieser Runde“.
        Index("ix_chat_runde_vorschlag_gespraech", "gespraech", "stand"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), nullable=False
    )
    #: Konto, das den Vorschlag gemacht hat (``user.name``). DSGVO:
    #: ``user_null`` — der Vorschlag fällt bei einer Löschung aber ganz (er
    #: hätte ohne Vorschlagende keine Bedeutung mehr).
    vorgeschlagen_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    #: Die VORGESCHLAGENE Person (``mitglied.name``). Kein FK — dieselbe Form
    #: wie ``chat_nachricht.autor``; die Anonymisierung entfernt die Zeile.
    mitglied: Mapped[str] = mapped_column(String(140), nullable=False)
    #: ``offen`` / ``angenommen`` / ``abgelehnt``.
    stand: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VORSCHLAG_OFFEN,
        server_default=sql_text("'offen'"),
    )
    #: Die Konten, die zugestimmt haben — sortiert, mit ``", "`` getrennt
    #: (dieselbe Form wie ``sicherungslauf.benachrichtigt``; die Anonymisierung
    #: entfernt den Eintrag der Person mit ``_konto_listen_bereinigen``).
    #: EINE Spalte, KEINE Zeile je Stimme: der Vorgang bleibt ein Datensatz,
    #: und ohne diese Liste könnte dieselbe Person mehrfach zustimmen und die
    #: Grenze „alle bisherigen Teilnehmenden“ allein erreichen — genau das
    #: verhindert sie. Der VERLAUF und jede Antwort nennen daraus niemanden.
    #: DSGVO: ``user_null`` — die Liste fällt mit dem Konto (``_konto_listen_-
    #: bereinigen`` entfernt den Eintrag exakt).
    zustimmende: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=sql_text("''")
    )
    entschieden_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name"), nullable=True
    )
    entschieden_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    @property
    def zustimmungen(self) -> list[str]:
        """Die KONTEN der Zustimmenden (aus ``zustimmende``) — nie eine Zahl.

        Eine ZAHL allein wäre falsch zählbar (dieselbe Person mehrfach); die
        Liste ist die Wahrheit, die Anzahl ihre Länge.
        """
        return [k.strip() for k in str(self.zustimmende or "").split(",")
                if k.strip()]


class ChatErwaehnung(Base):
    """Eine ERWÄHNUNG („@Name“, CHAT-9a, Konzept S4) an einer Nachricht.

    Der Client schickt die Erwähnten AUSDRÜCKLICH mit — der Server parst KEIN
    „@…“ aus dem Text. Je gültiger Erwähnung steht hier EINE Zeile; die
    Gültigkeit prüft ``api.chat._erwaehnungen_pruefen`` (Beteiligte des
    Gesprächs, nicht die sendende Person selbst; gezählt werden nur die
    ersten 20 Kennungen, gekappt VOR der Prüfung). Eine Kontaktsperre
    verwirft NICHT — sie unterdrückt nur die Glocke (sonst verriete die
    Antwort an die sendende Person die Sperre).

    ``mitglied`` ist eine MITGLIED-Kennung ohne FK — dieselbe Form wie
    ``chat_runde_vorschlag.mitglied`` (die Anonymisierung löscht die Zeile mit
    der Person, sie hängt sie nicht um). ``nachricht`` hängt dagegen am Leben
    der Nachricht (``ON DELETE CASCADE``): eine endgültig gelöschte Nachricht
    (CHAT-8) nimmt ihre Erwähnungen mit. Das SOFT-Delete räumt sie vorher über
    ``api.chat.loeschen``/``_nachricht_erwaehnungen_raeumen`` ab.

    DSGVO (Konzept 4.3): die Zeile fällt mit der Person
    (``ZEILEN_LOESCHEN``/``chat_erwaehnung``) — eine Erwähnung ist ein
    Verhaltensdatum AM KONTO („wer wurde von wem wie oft genannt“), der
    Nachrichtentext bleibt davon unberührt.
    """

    __tablename__ = "chat_erwaehnung"
    __table_args__ = (
        # „Wer ist an dieser Seite erwähnt?“ — EIN Abruf je Verlaufsseite.
        Index("ix_chat_erwaehnung_nachricht", "nachricht"),
        # „Welche Glocken gehören dieser Person?“ (Lesen/Aufräumen).
        Index("ix_chat_erwaehnung_mitglied", "mitglied"),
    )

    nachricht: Mapped[str] = mapped_column(
        String(140),
        ForeignKey("chat_nachricht.name", ondelete="CASCADE"),
        primary_key=True,
    )
    #: Die erwähnte Person (``mitglied.name``) — EINE je Nachricht und Person
    #: (zusammengesetzter Primärschlüssel; Duplikate verwirft der Endpunkt).
    mitglied: Mapped[str] = mapped_column(String(140), primary_key=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class ChatAnhang(Base):
    """Ein ANHANG an einer Chat-Nachricht (CHAT-12a, Konzept S4 + F11).

    Die DATEI selbst liegt NUR in der Ablage (``diakronos_app.speicher``) unter
    ``schluessel`` — hier stehen nur die Angaben, die zum Ausliefern und
    Anzeigen nötig sind (Anzeigename, geprüfter Typ, Größe). Es gibt keinen
    zweiten Speicherweg (kein ``files.py``-Eintrag, keine ``File``-Zeile): die
    Karte verbietet ihn ausdrücklich.

    ``nachricht`` ist ZUERST leer: ``anhang_hochladen`` legt die Zeile „offen“
    an und gibt ihre Kennung zurück; ``senden`` hängt sie an die neue Nachricht
    (``anhaenge=[…]``). Ein offener Anhang, der 24 h keiner Nachricht zugeordnet
    wurde, räumt der Minuten-Job ``chat_anhaenge_aufraeumen`` weg — Zeile UND
    Datei.

    ``gespraech`` steht zusätzlich zur Nachricht hier, weil der Upload das
    Gespräch braucht, lange bevor es eine Nachricht gibt: die Rechtefrage beim
    Hochladen ist „darf ich in DIESES Gespräch senden“ (dieselbe Weiche wie
    ``senden``), und die Tagesgrenze zählt je Person über alle Gespräche.

    DSGVO (Konzept 4.3): ``angelegt_von`` ist ein Konto-Verweis (``user_null``
    — er verschwindet mit dem Konto); ``dateiname`` ist Freitext (er kann einen
    Namen tragen) und läuft über ``protokoll``. Die DATEI selbst fällt mit der
    Person: ``dsgvo_anonymisierung`` sammelt den Schlüssel und löscht das
    Speicherobjekt nach dem Commit.
    """

    __tablename__ = "chat_anhang"
    __table_args__ = (
        # „Welche Anhänge hängen an diesen Nachrichten?“ — EIN Abruf je
        # Verlaufsseite (kein N+1).
        Index("ix_chat_anhang_nachricht", "nachricht"),
        # Tagesgrenze je Person und das Aufräumen offener Anhänge.
        Index("ix_chat_anhang_angelegt_von_am", "angelegt_von", "angelegt_am"),
        Index("ix_chat_anhang_gespraech", "gespraech"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: Die Nachricht, an der der Anhang hängt — NULL, solange er „offen“ ist.
    #: ``ON DELETE CASCADE``: eine endgültig gelöschte Nachricht (CHAT-8) nimmt
    #: ihre Anhang-Zeilen mit; die DATEI räumt der Löschweg vorher weg.
    nachricht: Mapped[str | None] = mapped_column(
        String(140),
        ForeignKey("chat_nachricht.name", ondelete="CASCADE"),
        nullable=True,
    )
    gespraech: Mapped[str] = mapped_column(
        String(140), ForeignKey("chat_gespraech.name"), nullable=False
    )
    #: Der SCHLÜSSEL in der Ablage (``speicher/schluessel.py``-Form) — die
    #: EINZIGE Stelle, an der die Datei zu finden ist.
    schluessel: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Anzeigename (bereinigt, höchstens ``ANHANG_NAME_MAX`` Zeichen). Reine
    #: Anzeige — er wird NIE als Speicherpfad benutzt.
    dateiname: Mapped[str] = mapped_column(String(ANHANG_NAME_MAX), nullable=False)
    #: Der GEPRÜFTE Typ (aus den Magic Bytes, nie der Client-Typ).
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    groesse: Mapped[int] = mapped_column(Integer, nullable=False)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: Das Konto, das hochgeladen hat (``user_null``: fällt mit dem Konto).
    #: ``ON DELETE SET NULL`` MUSS zum Migrationsstand passen (Review R1/2:
    #: Modell ohne ``ondelete`` war Drift). Die DSGVO erfasst die Zeilen
    #: trotzdem VOR dem Löschen der ``user``-Zeile — auf PostgreSQL wäre
    #: ``angelegt_von`` sonst schon NULL und die Zeile samt ``dateiname``
    #: bliebe stehen.
    angelegt_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="SET NULL"), nullable=True
    )


class ChatAnhangEntsorgung(Base):
    """ENTSORGUNGSLISTE der Anhang-Dateien (Review R1/3).

    Jede Zeile ist ein AUFTRAG „lösche diesen Speicher-Schlüssel“. Der Auftrag
    entsteht in DERSELBEN Transaktion, in der die ``chat_anhang``-Zeile fällt —
    damit ist die Datei nie unerreichbar: entweder es gibt noch die
    Anhang-Zeile mit dem Schlüssel, oder es gibt den Auftrag.

    Ohne diese Liste waren Dateien nach einem gescheiterten Ablage-Löschen
    (Netzfehler, Nextcloud kurz weg) verwaist und niemand versuchte es erneut.
    Abgearbeitet wird sie von ``api.chat.chat_anhang_entsorgung_abarbeiten``
    (Minuten-Job, wie der Aufräumjob der offenen Anhänge):

    * Erfolg (Datei weg oder „war schon weg“) → Zeile fällt,
    * Fehler → ``versuche`` + 1, ``letzter_fehler`` (kurz, ohne Geheimnisse),
      nächster Lauf versucht es erneut.

    **Keine Kopfblockade (CHAT-12a-2, Review):** Der Job nimmt nicht mehr die
    ältesten Aufträge, sondern die, die JETZT dran sind (``naechster_versuch_am
    <= jetzt``), der früheste zuerst. Vorher konnten 100 dauerhaft scheiternde
    Schlüssel (403, kaputter Pfad) die Liste von vorn blockieren — neuere
    Aufträge wurden nie bearbeitet. ``naechster_versuch_am`` wird beim
    Fehlschlag hochgesetzt (``api.chat.ENTSORGUNG_BACKOFF_MINUTEN``: 1, 5, 30
    Minuten, danach 6 Stunden). Ein Auftrag wird NIE still gelöscht — es geht
    um DSGVO-Dateien; ab ``ENTSORGUNG_WARNUNG_AB`` Versuchen steht einmal ein
    ``logger.error`` im Protokoll, versucht wird weiter (alle 6 Stunden).

    DSGVO-Inventar: die Tabelle trägt KEINE Personendaten — der Schlüssel ist
    eine technische Kennung (``chat-a…``), kein Name, kein Konto, kein Bezug
    auf eine Person. Sie steht deshalb weder in ``ZEILEN_LOESCHEN`` noch in
    ``SPALTEN`` und wird vom Anonymisierer nicht angefasst (``test_dsgvo1_
    inventar`` prüft die Begründung).
    """

    __tablename__ = "chat_anhang_entsorgung"
    __table_args__ = (
        # Die Auswahl des Jobs: „was ist jetzt dran?“, frühestes zuerst.
        Index("ix_chat_anhang_entsorgung_am", "vorgemerkt_am"),
        Index("ix_chat_anhang_entsorgung_naechster", "naechster_versuch_am"),
    )

    #: Der Speicher-Schlüssel selbst ist der Primärschlüssel: derselbe Auftrag
    #: entsteht nie zweimal (INSERT OR IGNORE bzw. bedingtes Einfügen).
    schluessel: Mapped[str] = mapped_column(String(255), primary_key=True)
    vorgemerkt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    versuche: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Wann dieser Auftrag das nächste Mal versucht werden darf
    #: (``api.chat.ENTSORGUNG_BACKOFF_MINUTEN``). Gleich ``vorgemerkt_am`` beim
    #: Anlegen — ein frischer Auftrag ist sofort dran.
    naechster_versuch_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    #: Kurzfassung des letzten Fehlers (höchstens ``ENTSORGUNG_FEHLER_MAX``
    #: Zeichen) — für die Diagnose, nie mit Zugangsdaten.
    letzter_fehler: Mapped[str | None] = mapped_column(
        String(ENTSORGUNG_FEHLER_MAX), nullable=True
    )


class ChatAnhangHochladung(Base):
    """Eine Hochlade-MARKE (Review R1/4) — Grundlage des Tageskontingents.

    Vorher zählte ``_anhang_kontingent`` die vorhandenen ``chat_anhang``-Zeilen
    des Tages. Wer hochlädt, sendet und die Nachricht wieder löscht, hatte
    damit ein unbegrenztes Kontingent. Die Marke hier wird beim Löschen einer
    Nachricht deshalb NICHT mitgelöscht; sie fällt erst mit dem Konto (DSGVO)
    oder nach ``HOCHLADUNG_AUFBEWAHRUNG_TAGE`` Tagen (Aufräumjob).

    **Gezählt wird je Hochlade-VERSUCH, nicht je erfolgreichem Upload
    (CHAT-12a-2):** die Marke entsteht in ``_anhang_kontingent``, BEVOR Typ und
    Größe geprüft sind. Das ist Absicht — sonst wäre die Grenze mit
    Fehlversuchen umgehbar (20 × 500 MB abgelehnt und das Kontingent bliebe
    unberührt).

    ``konto`` ist der Kontoname (Adresse) — für die Tageszählung und die
    DSGVO-Zuordnung. Die Zeile trägt kein Bild und keinen Dateinamen; sie sagt
    nur „diese Person hat an diesem Tag N-mal hochgeladen (versucht)“.
    """

    __tablename__ = "chat_anhang_hochladung"
    __table_args__ = (
        # „Wie viele Uploads hat dieses Konto seit Mitternacht?“ — ein Zugriff.
        Index("ix_chat_anhang_hochladung_konto_am", "konto", "angelegt_am"),
        Index("ix_chat_anhang_hochladung_am", "angelegt_am"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    konto: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="CASCADE"), nullable=False
    )
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)



__all__: list[Any] = [
    "ANHAENGE_MAX",
    "ANHAENGE_PRO_TAG",
    "ANHANG_BILDER",
    "ANHANG_MAX_BYTES",
    "ANHANG_NAME_MAX",
    "ANHANG_OFFEN_STUNDEN",
    "ANHANG_TYPEN",
    "ARTEN",
    "ART_DIREKT",
    "ART_GRUPPE",
    "ART_RUNDE",
    "ART_UNTERGRUPPE",
    "BEARBEITEN_MINUTEN",
    "ChatAnhang",
    "ChatAnhangEntsorgung",
    "ChatAnhangHochladung",
    "ChatErwaehnung",
    "ENTSORGUNG_FEHLER_MAX",
    "HOCHLADUNG_AUFBEWAHRUNG_TAGE",
    "ERWAEHNUNGEN_MAX",
    "ChatGespraech",
    "ChatGlocke",
    "ChatMeldung",
    "ChatNachricht",
    "ChatReaktion",
    "ChatRundeVorschlag",
    "ChatStimme",
    "ChatTeilnehmer",
    "GLOCKE_RUHE_MINUTEN",
    "ChatUmfrage",
    "ChatUmfrageAbgabe",
    "ChatUmfrageOption",
    "FRAGE_MAX",
    "HINWEIS_AB",
    "MELDEGRUENDE",
    "MELDUNG_ENTSCHEIDUNGEN",
    "MELDUNG_ERLEDIGT",
    "MELDUNG_FREITEXT_MAX",
    "MELDUNG_OFFEN",
    "MELDUNG_STAENDE",
    "MELDUNG_VERWORFEN",
    "NACHRICHT_MAX",
    "OPTIONEN_MAX",
    "OPTIONEN_MIN",
    "OPTION_MAX",
    "REAKTIONEN",
    "RUNDE_MAX",
    "RUNDE_MIN",
    "RUNDE_TITEL_MAX",
    "VORSCHLAG_ABGELEHNT",
    "VORSCHLAG_ANGENOMMEN",
    "VORSCHLAG_BEENDET",
    "VORSCHLAG_OFFEN",
    "VORSCHLAG_STAENDE",
]
