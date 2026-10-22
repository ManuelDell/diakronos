"""BACKUP-1: Einstellungen und Protokoll der eigenen Datensicherung.

Zwei Tabellen, beide **kein** Frappe-DocType (Handmodell wie
``models/gemeinde.py`` und ``models/datenschutz.py``):

* ``sicherungseinstellungen`` — Single-Zeile: automatisch an/aus, Uhrzeit,
  Aufbewahrung in Tagen. Die Aufbewahrung ist Pflicht und hat ein Minimum von
  1 Tag; die Pruefung liegt in ``sicherung/aufbewahrung.py`` UND im Endpunkt
  (eine Schranke allein reicht nicht: der Scheduler liest denselben Wert).
* ``sicherungslauf`` — je Lauf eine Zeile: Zeitpunkt, Groesse, Status und
  Meldung. Die Liste in der Oberflaeche kommt aus dieser Tabelle, die
  Dateien selbst liegen unter ``settings.backup_dir``.

**Keine Zugangsdaten** in beiden Tabellen: ``meldung`` traegt hoechstens die
Fehlerursache im Klartext (z. B. "pg_dump fehlgeschlagen (Exit 1)"), niemals
die Kommandozeile des Dumps — die enthaelt den Datenbank-Benutzer und damit
den Ansatzpunkt fuer das Passwort (B4).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Fester Name der Single-Zeile (wie ``GEMEINDE_EINSTELLUNGEN_NAME``).
SICHERUNGSEINSTELLUNGEN_NAME = "Sicherung Einstellungen"

#: Aufbewahrung: Standard und Untergrenze (Karte BACKUP-1 B2).
STANDARD_AUFBEWAHRUNG_TAGE = 30
MINIMUM_AUFBEWAHRUNG_TAGE = 1
#: Standard-Uhrzeit der automatischen Sicherung (Ortszeit, Europe/Berlin).
STANDARD_UHRZEIT = "03:00"

#: Statuswerte eines Laufs. ``laeuft`` existiert nur waehrend des Laufs; bricht
#: der Prozess ab, bleibt die Zeile stehen und wird beim naechsten Start als
#: ``fehlgeschlagen`` gemeldet (``sicherung/sperre.py``).
STATUS_LAEUFT = "laeuft"
STATUS_OK = "ok"
STATUS_FEHLGESCHLAGEN = "fehlgeschlagen"


class Sicherungseinstellungen(Base):
    """Single-Zeile: automatische Sicherung an/aus, Uhrzeit, Aufbewahrung."""

    __tablename__ = "sicherungseinstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    automatisch: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default="1"
    )
    # Ortszeit "HH:MM" (24 h). Der Scheduler vergleicht gegen die Uhrzeit aus
    # ``settings.calendar_timezone`` — nicht gegen UTC, damit "03:00" fuer den
    # Betreiber auch 03:00 bedeutet.
    uhrzeit: Mapped[str] = mapped_column(
        String(5), nullable=False, default=STANDARD_UHRZEIT,
        server_default=STANDARD_UHRZEIT,
    )
    aufbewahrung_tage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=STANDARD_AUFBEWAHRUNG_TAGE,
        server_default=str(STANDARD_AUFBEWAHRUNG_TAGE),
    )
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Sicherungslauf(Base):
    """Eine Zeile je Sicherungslauf (Erfolg, Fehler oder laufend)."""

    __tablename__ = "sicherungslauf"

    #: Zeitstempel-basierte Kennung ``JJJJ-MM-TT_HHMMSS`` — derselbe Name wie
    #: das Verzeichnis unter ``backup_dir``. Damit findet die Liste ihre
    #: Dateien ohne zweite Quelle, und eine Sicherung ist ueber Zeitpunkt
    #: und Groesse hinaus identifizierbar.
    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: Beginn des Laufs (Ortszeit ohne Zeitzone, wie in den Frappe-Modellen).
    begonnen_am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    #: Ende des Laufs; leer, solange er laeuft.
    beendet_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_LAEUFT,
        server_default=STATUS_LAEUFT,
    )
    #: Groesse der Sicherung in Bytes (Dump + Dateiarchiv + Pruefsummen).
    groesse_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ``automatisch`` (Scheduler) oder ``manuell`` (Knopf "Jetzt sichern").
    ausloeser: Mapped[str] = mapped_column(
        String(20), nullable=False, default="automatisch",
        server_default="automatisch",
    )
    #: Kurze Meldung fuer die Oberflaeche. NIE Zugangsdaten (Modulkopf).
    meldung: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Konten, die beim Fehlschlag benachrichtigt wurden (nur zur Nachvoll-
    #: ziehbarkeit; die Benachrichtigung selbst steht im `Notification Log`).
    benachrichtigt: Mapped[str | None] = mapped_column(Text, nullable=True)
