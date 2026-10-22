"""ORM-Modelle des Dev-Modus (DM1).

Der Dev-Modus ersetzt die Testsuite: statt Szenarien/Katalog/Punkten gibt es
Befunde — je Befund mit Text, Bild(ern), Element-Kontext und (falls vorhanden)
Audio. Die Tabellen werden NICHT per Alembic-autogenerate erzeugt, sondern in
der Migration ``dm1_devmodus`` ausdruecklich angelegt. Die Modelle hier sind
die Laufzeit-Sicht (SQLAlchemy) auf genau diese Tabellen — Namen und Spalten
muessen deckungsgleich sein.

Datenhaltung
------------
* ``dm_sitzung``   — eine laufende Dev-Sitzung je Benutzer (Herzschlag). Nur
  solange eine solche Sitzung laeuft, sammelt das ``ueberwachung``-Mittelstueck
  serverseitige Fehler. Ohne laufende Sitzung kostet der Dev-Modus nichts.
* ``dm_ereignis``  — Fehler/Logs/fehlgeschlagene Anfragen je Benutzer (das
  Fehlerumfeld, das einem Befund automatisch beigelegt wird).
* ``dm_befund``    — der Befund selbst: Text, Art, Wichtigkeit, Status, URL,
  Element-Kontext (JSON), Fehlerumfeld (JSON), Bild-/Audiopfade.

``dm_befund.element`` und ``dm_befund.fehlerumfeld`` sind JSON-Objekte bzw.
-listen. Eine eigene Kindtabelle waere hier reine Zeremonie: gelesen wird immer
das ganze Objekt, und SQLite (Tests) kennt kein JSONB — ``sa.JSON`` ist auf
beiden Datenbanken derselbe Typ in der Anwendung.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class DevSitzung(Base):
    """Eine laufende Dev-Sitzung: ein Nutzer mit eingeschaltetem Dev-Modus."""

    __tablename__ = "dm_sitzung"

    benutzer: Mapped[str] = mapped_column(String(140), primary_key=True)
    aktiv: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    begonnen: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    herzschlag: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class DevEreignis(Base):
    """Ein gemeldetes Ereignis (Fehler, Log, fehlgeschlagene Anfrage) je Nutzer."""

    __tablename__ = "dm_ereignis"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    benutzer: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    art: Mapped[str] = mapped_column(String(30), nullable=False)
    zeitpunkt: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    methode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    pfad: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dauer_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meldung: Mapped[str | None] = mapped_column(Text, nullable=True)
    meldungen: Mapped[list | None] = mapped_column(JSON, nullable=True)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    erzeugt: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class DevBefund(Base):
    """Ein Befund des Dev-Modus — Text, Kontext, Bilder und Fehlerumfeld."""

    __tablename__ = "dm_befund"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    benutzer: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    art: Mapped[str] = mapped_column(String(30), default="fehler", nullable=False, index=True)
    wichtigkeit: Mapped[str] = mapped_column(String(20), default="mittel", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="offen", nullable=False, index=True)
    titel: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Ort
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    route: Mapped[str | None] = mapped_column(String(300), nullable=True)
    seitentitel: Mapped[str | None] = mapped_column(String(300), nullable=True)
    seite: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    # Umgebung
    viewport: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bildschirm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geraet: Mapped[str | None] = mapped_column(String(300), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(300), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sprache: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Element-Kontext und Fehlerumfeld sind JSON (siehe Modul-Docstring).
    element: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fehlerumfeld: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Bildpfade RELATIV zu FILES_DIR (z.B. devmodus/2026-10-15/ab12.png).
    bilder: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Audiopfad RELATIV zu FILES_DIR (Sprachaufnahme, optional).
    audio: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    zeitpunkt: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


__all__ = ["DevSitzung", "DevEreignis", "DevBefund"]
