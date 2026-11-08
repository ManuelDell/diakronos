"""BS-3a: Ansprechpartner-Bereiche der Website (Verwaltungsauswahl).

Warum es diese Tabelle gibt
---------------------------
Die Karte trennt zwei Entscheidungen streng:

  * **Wer erscheint** entscheidet die PERSON (Einwilligung, ``website/einwilligung.py``).
  * **Welche Funktion/Position erscheint** entscheidet die Verwaltung — HIER.

Diese Tabelle haelt genau die Verwaltungsentscheidung: eine Zeile je
Funktion/Position, die auf der Website als Ansprechpartner-Bereich auftauchen
soll, mit einem optionalen Kontakt-Postfach (Slug aus BS-1a, ``website_kontakt_postfach``)
statt einer persoenlichen E-Mail-Adresse.

Eine Zeile enthaelt NIEMALS eine Einwilligung, eine E-Mail-Adresse oder einen
Namen: ``funktion`` ist eine Kennung aus dem Organigramm (``dienstbereich.name``
oder ``gruppe.name``), ``postfach`` ein Slug. Wer die Funktion ausfuellt, steht
in der Mitgliederverwaltung — und ob diese Person erscheinen darf, entscheidet
allein ihre eigene Einwilligung.

Handmodell wie ``models/website_kontakt.py`` (kein Frappe-DocType): die Tabelle
haelt eine technische Zuordnung, keine Fachdaten, und wird von der Migration
``bs3a_website_einwilligung`` ausdruecklich angelegt.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class WebsiteAnsprechpartner(Base):
    """Eine ausgewaehlte Funktion/Position fuer die oeffentliche Ausgabe."""

    __tablename__ = "website_ansprechpartner"
    __table_args__ = (
        # UNIQUE als eigener INDEX (nicht `unique=True` an der Spalte): sonst
        # meldet `alembic check` einen Unterschied (Index vs.
        # UniqueConstraint), obwohl beide dasselbe bewirken — dieselbe
        # Begruendung wie in `models/website.py`.
        Index(
            "uq_website_ansprechpartner_art_funktion",
            "art",
            "funktion",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: ``dienstbereich`` oder ``gruppe`` (die zwei Knotenarten des Organigramms).
    art: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Kennung des Datensatzes (``dienstbereich.name`` bzw. ``gruppe.name``).
    funktion: Mapped[str] = mapped_column(String(140), nullable=False)
    #: Anzeigename des Bereichs; leer = Anzeigename des Datensatzes.
    bezeichnung: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Kontakt-Postfach (Slug aus ``website_kontakt_postfach``); NULL = keines.
    #: Eine E-Mail-Adresse steht hier NIE — nur der Slug.
    postfach: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Reihenfolge der Ausgabe (klein zuerst), dann ``funktion``.
    sortierung: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
