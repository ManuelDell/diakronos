"""BS-1a: Postfaecher des Website-Kontaktformulars (``website_kontakt_postfach``).

Handmodell wie ``models/sicherung.py`` und ``models/website.py`` (PrimoKonto):
die Tabelle haelt eine technische Verwaltungs-Liste, keine Fachdaten eines
DocType, und wird in der Migration ``bs1a_website_freigaben`` ausdruecklich
angelegt. Sie ist bewusst NICHT im DocType-Inventar — es gibt in Diakronos
keinen DocType, dem sie gehoerte.

Spalten
-------
``slug``          Primaerschluessel, URL-sicher ([a-z0-9-]); der Wert
                  ``standard`` ist reserviert (Abwaertskompatibilitaet).
``bezeichnung``   Anzeigename im Formular (z. B. „Allgemeine Anfragen“).
``email``         Empfaengeradresse des Postfachs.
``aktiv``         Nur aktive Postfaecher werden im Formular angeboten.
``sortierung``    Reihenfolge im Formular (aufsteigend).

Fallback (WEB-10)
-----------------
Ist KEINE Zeile vorhanden, gilt ``WEBSITE_KONTAKT_EMPFAENGER`` als Postfach
``standard`` — der Endpunkt ``website.kontakt_senden`` verhaelt sich dann
unveraendert wie vor BS-1a. Diese Regel steht in ``website/freigaben.py``
(``postfaecher_oeffentlich``), nicht hier.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class WebsiteKontaktPostfach(Base):
    """Eine Zeile je Empfaenger-Postfach des Kontaktformulars (BS-1a)."""

    __tablename__ = "website_kontakt_postfach"

    slug: Mapped[str] = mapped_column(String(140), primary_key=True)
    bezeichnung: Mapped[str] = mapped_column(String(140), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sortierung: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
