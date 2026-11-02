"""ON-2 — Stand der Einrichtung (Assistent + Merker).

Warum eine EIGENE Single-Zeilen-Tabelle und keine Spalten in
``gemeinde_einstellungen``:

* Der Assistent speichert **Prozess**-Zustand („Schritt uebersprungen“,
  „Assistent abgeschlossen“, „erst am … wieder erinnern“), nicht Fachdaten der
  Gemeinde. Ein ``DELETE``/Neuaufsetzen der Gemeinde-Angaben soll den
  Assistentenstand nicht mitreissen und umgekehrt.
* Die Punkte selbst (Gemeindename, Logo, Kontakt, Mailversand, Module,
  Mitglieder, Kalender) werden bei JEDEM Aufruf aus den echten Daten
  berechnet — hier steht KEIN „erledigt“-Haken, der veralten koennte. Damit
  gilt: was in der Oberflaeche als erledigt erscheint, ist es auch.

Ein Vorbild ist ``passwortzugang.py`` / ``datenschutz.py`` (dieselbe Bauform:
eine Zeile, ``name`` als Primaerschluessel, ``created``/``modified``).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Fester Name der Single-Zeile (wie ``GEMEINDE_EINSTELLUNGEN_NAME``).
EINRICHTUNG_STAND_NAME = "Einrichtung Stand"

#: Die Schritte des Assistenten in Anzeigereihenfolge (Entwurf 04–09).
#: ``fertig`` ist kein Schritt mit eigenem Zustand — er zeigt nur die
#: Checkliste (Frame 09).
SCHRITT_SCHLUESSEL = (
    "gemeinde",
    "kontakt",
    "mailversand",
    "module",
    "mitglieder_kalender",
)

#: Erlaubte Zustaende eines Schritts. ``uebersprungen`` ist NUR hier gespeichert;
#: die Punkte in ``einrichtung.status`` bleiben davon unberuehrt (sie werden
#: aus echten Daten berechnet).
SCHRITT_ZUSTAENDE = ("offen", "erledigt", "uebersprungen")


class EinrichtungStand(Base):
    """Single-Zeile: Assistentenstand und Erinnerung."""

    __tablename__ = "einrichtung_stand"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    assistent_abgeschlossen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Ein Zustand je Schritt als Spalte (``schritt_gemeinde`` …). Bewusst
    #: Spalten und keine Kindtabelle: die Zahl der Schritte ist fest (Entwurf),
    #: und ein ``status``-Aufruf soll die Zeile ohne Join lesen koennen.
    schritt_gemeinde: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_kontakt: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_mailversand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_module: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_mitglieder_kalender: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    #: „Spaeter erinnern“: bis zu diesem Tag bleibt die Karte auf der Uebersicht
    #: ausgeblendet. Ein Datum, kein Schalter — es laeuft von selbst ab.
    erinnerung_ab: Mapped[date | None] = mapped_column(Date, nullable=True)
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
