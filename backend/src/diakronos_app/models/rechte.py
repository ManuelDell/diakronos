"""R-1: Tabellen des EINEN Rechtesystems (Plan ``diakronos-rechte``).

Leitregel (Manuel 2026-11-11): Es gibt genau ein Rechtesystem, nicht eines je
Modul. Diese fuenf Tabellen sind die einzige Quelle fuer Gruppenrollen,
Gruppen-Module, Objekt-Zuordnungen, Einzelfreigaben und Gast-Links. Entschieden
wird ausschliesslich in ``diakronos_app.rechte.kern``.

Ueberblick
----------
``rechte_gruppenrolle``
    Wer ist Hauptverantwortlicher (HV) bzw. Mitverantwortlicher (MV) einer
    Gruppe, wer Gruppenleiter (GL) einer Untergruppe. Genau EIN HV je Gruppe
    (partieller Unique-Index). Die einfache
    Mitgliedschaft steht weiter in ``gruppenmitgliedschaft`` (Bestand).

``rechte_modul``
    Welche Diakronos-Bausteine eine Gruppe hat (kalender, beitraege, wiki,
    aufgaben, lieder, dienstplaene). Ohne Zeile ist das Modul in der Gruppe aus.

``rechte_objekt``
    Zu welcher Gruppe ein Objekt eines Moduls gehoert (``gruppe`` leer =
    Gemeinde-Objekt, z. B. ein gemeinsamer Kalender: verwaltet vom
    Administrator bzw. der passenden Fachverwaltung) (z. B. Kalender
    ``gottesdienste`` -> Gruppe ``Chor``) und wie es freigegeben ist:
    ``standard_gruppe_lesen`` (alle Gruppenmitglieder lesen) und
    ``gemeinde_status`` (Freigabe an alle Mitglieder der Gemeinde: aus /
    beantragt / aktiv). ``eltern_typ``/``eltern_objekt`` verbinden z. B. einen
    Dienstplan mit seinem Kalender.

``rechte_freigabe``
    Freigabe eines Objekts an EINE Person oder EINE Gruppe
    (Lesen/Schreiben/Moderieren).

``rechte_gastlink``
    Zugang fuer Gaeste ohne Konto: Token (nur Hash), Passwort (nur Hash),
    Ablaufzeitpunkt (Standard 3 Tage, einstellbar).

Handmodell (kein Frappe-DocType); angelegt von der Migration ``r1_rechte_kern``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Gueltige Werte fuer ``rechte_gruppenrolle.rolle``.
ROLLE_HV = "HV"   # Hauptverantwortlicher der Gruppe (genau einer)
ROLLE_MV = "MV"   # Mitverantwortliche der Gruppe
ROLLE_GL = "GL"   # Gruppenleiter einer Untergruppe

#: Gueltige Werte fuer ``rechte_objekt.gemeinde_status``.
GEMEINDE_AUS = "aus"
GEMEINDE_BEANTRAGT = "beantragt"
GEMEINDE_AKTIV = "aktiv"


class RechteGruppenrolle(Base):
    """HV/MV einer Gruppe bzw. GL einer Untergruppe.

    Zwei Ebenen, mehr gibt es nicht (Manuel 11.11.): Gruppe -> Untergruppe.
    ``untergruppe`` leer = Rolle in der Hauptgruppe (HV/MV); gesetzt = Rolle in
    dieser Untergruppe (GL). ``gruppe`` ist immer die Hauptgruppe.
    """

    __tablename__ = "rechte_gruppenrolle"
    __table_args__ = (
        Index(
            "uq_rechte_gruppenrolle_gruppe_benutzer", "gruppe", "benutzer", unique=True,
            postgresql_where=text("untergruppe IS NULL"), sqlite_where=text("untergruppe IS NULL"),
        ),
        Index(
            "uq_rechte_gruppenrolle_untergruppe_benutzer", "untergruppe", "benutzer", unique=True,
            postgresql_where=text("untergruppe IS NOT NULL"), sqlite_where=text("untergruppe IS NOT NULL"),
        ),
        # Genau EIN Hauptverantwortlicher je Gruppe.
        Index(
            "uq_rechte_gruppenrolle_ein_hv",
            "gruppe",
            unique=True,
            postgresql_where=text("rolle = 'HV'"),
            sqlite_where=text("rolle = 'HV'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gruppe: Mapped[str] = mapped_column(String(140), nullable=False)
    untergruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Login-Name (``user.name``), nicht die Mitglied-Kennung.
    benutzer: Mapped[str] = mapped_column(String(140), nullable=False)
    #: ``HV`` / ``MV`` (Hauptgruppe) oder ``GL`` (Untergruppe).
    rolle: Mapped[str] = mapped_column(String(2), nullable=False)
    erteilt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    erteilt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class RechteModul(Base):
    """Ein aktives Modul einer Gruppe."""

    __tablename__ = "rechte_modul"
    __table_args__ = (
        Index("uq_rechte_modul_gruppe_modul", "gruppe", "modul", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gruppe: Mapped[str] = mapped_column(String(140), nullable=False)
    modul: Mapped[str] = mapped_column(String(40), nullable=False)


class RechteObjekt(Base):
    """Zuordnung eines Modul-Objekts zu seiner Gruppe + Gemeinde-Freigabe."""

    __tablename__ = "rechte_objekt"
    __table_args__ = (
        Index("uq_rechte_objekt_typ_objekt", "typ", "objekt", unique=True),
        Index("ix_rechte_objekt_gruppe", "gruppe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: z. B. ``kalender``, ``beitrag``, ``wiki``, ``aufgabe``, ``dienstplan``.
    typ: Mapped[str] = mapped_column(String(40), nullable=False)
    objekt: Mapped[str] = mapped_column(String(140), nullable=False)
    gruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Besitzende Untergruppe (dann ist ``gruppe`` ihre Hauptgruppe).
    untergruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Alle Mitglieder der besitzenden (Unter-)Gruppe lesen ohne Einzelfreigabe.
    standard_gruppe_lesen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    #: Freigabe an alle Mitglieder der Gemeinde: ``aus`` / ``beantragt`` / ``aktiv``.
    gemeinde_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GEMEINDE_AUS, server_default=text("'aus'")
    )
    #: Nur fuer Untergruppen-Objekte: Freigabe an die ganze Hauptgruppe
    #: (``aus`` / ``beantragt`` / ``aktiv``) — moderiert von HV/MV.
    gruppe_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=GEMEINDE_AUS, server_default=text("'aus'")
    )
    eltern_typ: Mapped[str | None] = mapped_column(String(40), nullable=True)
    eltern_objekt: Mapped[str | None] = mapped_column(String(140), nullable=True)


class RechteFreigabe(Base):
    """Freigabe eines Objekts an EINE Person ODER an EINE Gruppe.

    Genau eines von ``benutzer``/``gruppe`` ist gesetzt. Bei einer
    Gruppen-Freigabe gilt ``lesen`` fuer alle Gruppenmitglieder, ``schreiben``
    und ``moderieren`` fuer HV und MV der Gruppe (Rollenwechsel brauchen so keine
    neuen Einzelfreigaben).
    """

    __tablename__ = "rechte_freigabe"
    __table_args__ = (
        Index(
            "uq_rechte_freigabe_typ_objekt_benutzer", "typ", "objekt", "benutzer", unique=True,
            postgresql_where=text("benutzer IS NOT NULL"), sqlite_where=text("benutzer IS NOT NULL"),
        ),
        Index(
            "uq_rechte_freigabe_typ_objekt_gruppe", "typ", "objekt", "gruppe", unique=True,
            postgresql_where=text("gruppe IS NOT NULL"), sqlite_where=text("gruppe IS NOT NULL"),
        ),
        Index("ix_rechte_freigabe_benutzer", "benutzer"),
        Index("ix_rechte_freigabe_gruppe", "gruppe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    typ: Mapped[str] = mapped_column(String(40), nullable=False)
    objekt: Mapped[str] = mapped_column(String(140), nullable=False)
    benutzer: Mapped[str | None] = mapped_column(String(140), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), nullable=True)
    lesen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    schreiben: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    moderieren: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    erteilt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    erteilt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class RechteGastlink(Base):
    """Gast-Zugang zu genau einem Objekt — immer mit Ablaufzeit."""

    __tablename__ = "rechte_gastlink"
    __table_args__ = (
        Index("uq_rechte_gastlink_token", "token_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    typ: Mapped[str] = mapped_column(String(40), nullable=False)
    objekt: Mapped[str] = mapped_column(String(140), nullable=False)
    #: sha256 des Tokens; das Token selbst wird nie gespeichert.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    passwort_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    ablauf: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    erstellt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    erstellt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    widerrufen_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


__all__ = [
    "GEMEINDE_AKTIV",
    "GEMEINDE_AUS",
    "GEMEINDE_BEANTRAGT",
    "ROLLE_GL",
    "ROLLE_HV",
    "ROLLE_MV",
    "RechteFreigabe",
    "RechteGastlink",
    "RechteGruppenrolle",
    "RechteModul",
    "RechteObjekt",
]
