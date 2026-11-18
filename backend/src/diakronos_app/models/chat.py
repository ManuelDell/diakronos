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

Bewusst NICHT hier (spätere Karten): Umfragen (S2, CHAT-5), Push-Abonnements
(CHAT-10), Anhänge (CHAT-9) und der Löschjob mit den Aufbewahrungsfristen
(CHAT-8).

DSGVO (Konzept 4.3): ``chat_nachricht.autor_benutzer`` ist eine Konto-Spalte
(``user_null`` — sie verschwindet mit dem Konto), ``chat_nachricht.autor`` ist
die MITGLIED-Kennung, die die Anonymisierung auf die neutrale Kennung
UMHÄNGT, damit der Verlauf lesbar bleibt. ``chat_reaktion.benutzer`` und
``chat_teilnehmer.benutzer`` sind Konto-Spalten (Zeile fällt).
``chat_gespraech.angelegt_von`` ist ein Konto-Verweis (``user_null``). Die
Freitexte stehen im Inventar unter ``protokoll``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Gesprächsarten. S1 kennt nur die beiden Gruppen-Räume; ``direkt``/``runde``
#: gehören zu S3 (CHAT-7) und werden hier nicht angelegt.
ART_GRUPPE = "gruppe"
ART_UNTERGRUPPE = "untergruppe"
ARTEN = (ART_GRUPPE, ART_UNTERGRUPPE)

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



class ChatGespraech(Base):
    """Ein Gespräch je Gruppe/Untergruppe (lazy angelegt)."""

    __tablename__ = "chat_gespraech"
    __table_args__ = (
        # EIN Gespräch je Einheit — ZWEI partielle Indizes statt EINES
        # UniqueConstraint: in PostgreSQL und SQLite gilt NULL nie als gleich,
        # ein Constraint über ``(art, gruppe, untergruppe)`` ließe also
        # beliebig viele Zeilen mit ``untergruppe IS NULL`` zu (also beliebig
        # viele Gruppen-Gespräche derselben Gruppe). Die Teilbedingung macht
        # die Regel für beide Fälle wahr (Review CHAT-2, Punkt 2).
        Index("uq_chat_gespraech_einheit", "art", "gruppe", unique=True,
              sqlite_where=text("untergruppe IS NULL"),
              postgresql_where=text("untergruppe IS NULL")),
        Index("uq_chat_gespraech_einheit_ug", "art", "gruppe", "untergruppe",
              unique=True,
              sqlite_where=text("untergruppe IS NOT NULL"),
              postgresql_where=text("untergruppe IS NOT NULL")),
        Index("ix_chat_gespraech_gruppe", "gruppe"),
        Index("ix_chat_gespraech_untergruppe", "untergruppe"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: ``gruppe`` / ``untergruppe`` (S1); ``direkt``/``runde`` = S3.
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Hauptgruppe — bei einer Untergruppe ist das ihre Gruppe.
    gruppe: Mapped[str] = mapped_column(String(140), nullable=False)
    untergruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Anzeigetitel. Leer heißt: die Oberfläche nimmt den Gruppennamen.
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
    #: Boolean mit ``server_default=text("false")`` (PostgreSQL) — dasselbe
    #: Muster wie ``rechte_modul``/``rechte_objekt`` (``rechte.py``).
    stumm: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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


class ChatNachricht(Base):
    """Eine Nachricht im Verlauf. Soft-Delete lässt die Lücke stehen."""

    __tablename__ = "chat_nachricht"
    __table_args__ = (
        # „Neueste zuerst“ (rückwärts gelesen) UND „seit X“ (vorwärts) laufen
        # über denselben Index (Konzept 3.3).
        Index("ix_chat_nachricht_gespraech_erstellt", "gespraech", "erstellt_am"),
        # Antworten einer Nachricht (Anzeige „N Antworten“).
        Index("ix_chat_nachricht_antwort_auf", "antwort_auf"),
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
              sqlite_where=text("stand = 'offen'"),
              postgresql_where=text("stand = 'offen'")),
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
        server_default=text("'offen'"),
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


__all__: list[Any] = [
    "ARTEN",
    "ART_GRUPPE",
    "ART_UNTERGRUPPE",
    "BEARBEITEN_MINUTEN",
    "ChatGespraech",
    "ChatMeldung",
    "ChatNachricht",
    "ChatReaktion",
    "ChatTeilnehmer",
    "MELDEGRUENDE",
    "MELDUNG_ENTSCHEIDUNGEN",
    "MELDUNG_ERLEDIGT",
    "MELDUNG_FREITEXT_MAX",
    "MELDUNG_OFFEN",
    "MELDUNG_STAENDE",
    "MELDUNG_VERWORFEN",
    "NACHRICHT_MAX",
    "REAKTIONEN",
]
