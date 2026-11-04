"""UX1j — Tabelle `gestaltung_abweichung`: vom Standard abweichende Maße.

Warum eine eigene Tabelle und keine Einstellungszeile
-----------------------------------------------------
Die Gestaltungs-Abweichungen sind eine MENGE gleichrangiger Werte (ein Eintrag
je Token) mit eigener Herkunft (wer, wann). Als Spalten in einer
Einstellungstabelle müsste jede neue einstellbare Größe eine Migration
bekommen — hier ist es eine Zeile. Und „zurücksetzen“ heißt: eine Zeile
löschen. Genau das bildet die Tabelle ab.

Spalten
-------
* ``token``        — CSS-Variablenname, ``--sp-1`` … (Primärschlüssel, weil ein
                     Token höchstens EINE Abweichung hat). Die Positivliste
                     steht in ``gestaltung/tokens.py``; die Datenbank ist NICHT
                     die Grenze (sie kann Altzeilen enthalten — die Ausgabe
                     filtert über die Liste).
* ``wert``         — ganze Zahl in px. Der CSS-Text (``"16px"``) wird erst beim
                     Ausgeben gebaut; so kann in der Spalte kein CSS landen.
* ``geaendert_von``— Benutzername der letzten Änderung (Nachweis).
* ``geaendert_am`` — Zeitstempel der letzten Änderung.

Kein Frappe-DocType: die Tabelle hält keine Fachdaten, sondern Betriebs-
Einstellungen, und wird in der Migration ``ux1j_gestaltung`` angelegt.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class GestaltungAbweichung(Base):
    """Eine Zeile je vom Standard abweichendem Maß (UX1j)."""

    __tablename__ = "gestaltung_abweichung"

    token: Mapped[str] = mapped_column(String(40), primary_key=True)
    wert: Mapped[int] = mapped_column(Integer, nullable=False)
    geaendert_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
