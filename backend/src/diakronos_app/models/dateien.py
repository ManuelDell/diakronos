"""DATEIEN-3: Gruppendateien — Handmodell (kein Frappe-DocType).

Konzept ``DATEIEN-KONZEPT.md`` Abschnitt 3 (Datenmodell-Skizze) und die
Entscheidungen Manuel 23.11.2026. Es entstehen ZWEI Tabellen; die dritte der
Skizze (``gruppe_datei_hochladung``, Tageskontingent) gibt es bewusst NICHT:
F9 sagt „kein Tageslimit — keine Hochlade-Marken-Tabelle“.

``gruppe_datei``
    EINE Zeile je Datei. Die Datei selbst liegt NUR in der Ablage
    (``diakronos_app.speicher``) unter ``schluessel``; hier stehen Anzeigename,
    geprüfter Typ und Größe. ``name`` ist eine technische Kennung
    (``gdatei-<hex>``) und reist als Parameter in der Adresse mit.

    ``untergruppe`` gesetzt = Datei der UNTERGRUPPE (F3: Untergruppen haben
    eigene Dateien), sonst Datei der Hauptgruppe. ``gruppe`` ist immer die
    Hauptgruppe.

    ``angelegt_von``/``angepinnt_von``/``geloescht_von`` tragen den LOGIN-Namen
    (``user.name``) — er entscheidet über die Rechte (``besitzer`` beim
    Löschen) und wird bei einer Löschung (Art. 17) genullt
    (``dsgvo_anonymisierung.SPALTEN``).

    ``geloescht_am``/``geloescht_von`` sind der PAPIERKORB (F5): Löschen setzt
    sie, Wiederherstellen nullt sie, endgültig entfernt die Zeile (und die
    Datei) der Job aus DATEIEN-5.

``gruppe_datei_entsorgung``
    Die Entsorgungsliste — wörtlich das Muster von ``chat_anhang_entsorgung``
    (eigene Tabelle, weil die Tabellen sonst nichts miteinander zu tun haben).
    Jede Zeile ist der AUFTRAG „lösche diesen Speicher-Schlüssel“; er entsteht
    in derselben Transaktion, in der die ``gruppe_datei``-Zeile fällt. Damit ist
    eine Datei nie unerreichbar: entweder es gibt die Zeile mit ihrem
    Schlüssel, oder es gibt den Auftrag. Abgearbeitet wird die Liste vom
    Aufräum-Job (DATEIEN-5); diese Karte legt nur Spalten und Wege an.

DSGVO: die Entsorgungsliste trägt KEINE Personendaten (der Schlüssel ist eine
technische Kennung ``datei-…``) — sie steht deshalb weder in ``SPALTEN`` noch
in ``ZEILEN_LOESCHEN`` (s. ``dsgvo_anonymisierung``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Präfix der technischen Kennung (``GDT_DATEI_PRAEFIX + uuid4().hex``).
GDT_DATEI_PRAEFIX = "gdatei-"

#: Präfix des Speicher-Schlüssels in der Ablage (``ablage.lege_ab``).
GDT_SPEICHER_PRAEFIX = "datei"

#: Höchstlänge des Anzeigenamens — dieselbe Zahl wie bei Chat-Anhängen
#: (``models.chat.ANHANG_NAME_MAX``), geprüft in ``ablage.dateiname``.
GDT_NAME_MAX = 120

#: Papierkorb: so lange bleibt eine gelöschte Datei wiederherstellbar (F5).
PAPIERKORB_TAGE = 30


class GruppeDatei(Base):
    """Eine Datei einer Gruppe bzw. Untergruppe (F3, F5, F9)."""

    __tablename__ = "gruppe_datei"
    __table_args__ = (
        # Der Listen-Abruf: „Dateien dieser (Unter-)Gruppe, ohne Papierkorb“.
        Index("ix_gruppe_datei_raum",
              "gruppe", "untergruppe", "geloescht_am"),
        # „Was ist hier angepinnt?“ — der obere Block der Liste.
        Index("ix_gruppe_datei_angepinnt", "gruppe", "angepinnt"),
    )

    #: Technische Kennung (``gdatei-<hex>``) — nie der Anzeigename, nie ein Pfad.
    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: Hauptgruppe (bei einer Untergruppen-Datei: deren Hauptgruppe).
    gruppe: Mapped[str] = mapped_column(String(140), nullable=False)
    #: NULL = Datei der Hauptgruppe; gesetzt = eigene Datei der Untergruppe.
    untergruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Der SCHLÜSSEL in der Ablage — die EINZIGE Stelle, an der die Datei liegt.
    schluessel: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Anzeigename (bereinigt, höchstens ``GDT_NAME_MAX`` Zeichen). Reine
    #: Anzeige: er wird NIE als Speicherpfad benutzt.
    dateiname: Mapped[str] = mapped_column(String(GDT_NAME_MAX), nullable=False)
    #: Der GEPRÜFTE Typ (Magie/Sperrliste, nie blind vom Client).
    mime: Mapped[str] = mapped_column(String(100), nullable=False)
    groesse: Mapped[int] = mapped_column(BigInteger, nullable=False)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: Login (``user.name``) der hochladenden Person — sein ``besitzer``
    #: entscheidet über „eigene Datei“ (F4).
    angelegt_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="SET NULL"), nullable=True
    )
    angepinnt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    angepinnt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    angepinnt_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="SET NULL"), nullable=True
    )
    #: Papierkorb (F5): gesetzt = im Papierkorb, nicht mehr in der Liste.
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    geloescht_von: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="SET NULL"), nullable=True
    )


class GruppeDateiEntsorgung(Base):
    """Entsorgungsliste der Dateien — Auftrag „lösche diesen Schlüssel“.

    Aufbau wie ``chat_anhang_entsorgung``: der Speicher-Schlüssel ist der
    Primärschlüssel (derselbe Auftrag entsteht nie zweimal), ``versuche`` und
    ``naechster_versuch_am`` tragen den Backoff. Kein Personenbezug.
    """

    __tablename__ = "gruppe_datei_entsorgung"
    __table_args__ = (
        Index("ix_gruppe_datei_entsorgung_am", "angelegt_am"),
        Index("ix_gruppe_datei_entsorgung_naechster", "naechster_versuch_am"),
    )

    schluessel: Mapped[str] = mapped_column(String(200), primary_key=True)
    versuche: Mapped[int] = mapped_column(nullable=False, default=0, server_default=text("0"))
    naechster_versuch_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    #: Zeitpunkt, bis zu dem der Auftrag belegt ist (ein Job, der ihn gerade
    #: bearbeitet, setzt/dehnt ihn — verhindert den zweiten Bearbeiter).
    belegt_bis: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


__all__ = [
    "GDT_DATEI_PRAEFIX",
    "GDT_NAME_MAX",
    "GDT_SPEICHER_PRAEFIX",
    "PAPIERKORB_TAGE",
    "GruppeDatei",
    "GruppeDateiEntsorgung",
]
