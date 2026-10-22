"""MAIL-1: die SMTP-Einstellungen (Single-Zeile in der DB).

Manuel hat entschieden (2026-10-20): **kein festgeschriebenes Postfach** — bei
der Einrichtung im Betrieb bestimmt die Gemeinde, welches Postfach der
Mailversand benutzt. Bis MAIL-1 kam die Konfiguration aus der ``.env``
(``SMTP_*``, DSGVO-1); ein zweiter Weg neben der Oberflaeche waere eine zweite
Wahrheit. Deshalb steht der geltende Wert ab jetzt **nur** hier in der
Datenbank, und ``mailversand.py`` liest ausschliesslich diese Zeile (S4).

Handmodell wie ``models/sicherung.py`` und ``models/gemeinde.py`` — kein
Frappe-DocType. Regeln, die dieses Modell traegt:

* **Das Passwort steht verschluesselt in der Spalte** (Fernet, abgeleitet aus
  ``SECRET_KEY`` mit eigenem Kontext, ``smtp_einstellungen.verschluessle``).
  Klartext wird beim Lesen nie angenommen: ``entschluessle`` prueft das
  Praefix und verweigert alles andere.
* **Die Zeile ist optional.** Existiert keine Zeile, ist der Versand nicht
  eingerichtet (``mailversand.ist_konfiguriert()`` = False). Die Migration legt
  bewusst KEINE Zeile an — „nicht eingerichtet" ist ein gueltiger Zustand.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Fester Name der Single-Zeile (wie ``SICHERUNGSEINSTELLUNGEN_NAME``).
SMTP_EINSTELLUNGEN_NAME = "SMTP Einstellungen"

#: Verschluesselungsarten (S1). Werte stehen so in der DB und in der Antwort.
SICHERHEIT_STARTTLS = "starttls"
SICHERHEIT_SSL = "ssl"
SICHERHEIT_KEINE = "keine"
SICHERHEITSWERTE = (SICHERHEIT_STARTTLS, SICHERHEIT_SSL, SICHERHEIT_KEINE)

#: Standardport je Art — nur ein Vorschlag der Oberflaeche, der Port bleibt
#: frei einstellbar (manche Haeuser bieten 587 nicht an).
STANDARDPORT = {SICHERHEIT_STARTTLS: 587, SICHERHEIT_SSL: 465, SICHERHEIT_KEINE: 25}

#: Zeitbudget je Verbindung in Sekunden (S3: eine Zeitueberschreitung muss als
#: solche erkannt und gemeldet werden, nicht als „Server nicht erreichbar").
STANDARD_TIMEOUT = 15.0


class SmtpEinstellungen(Base):
    """Single-Zeile: Server, Sicherheit, Zugang, Absender des Mailversands."""

    __tablename__ = "smtp_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    # Server und Port: beide Pflicht, sobald die Zeile existiert.
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    # Einer aus SICHERHEITSWERTE. ``keine`` ist nur mit deutlicher Warnung
    # erlaubt und wird bei Anmeldung nicht zugelassen (s. pruefen.py).
    sicherheit: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SICHERHEIT_STARTTLS
    )
    benutzername: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Fernet-Geheimtext (Praefix ``fernet:v1:``), NIE Klartext. Leer = kein
    # Passwort hinterlegt (Server ohne Anmeldung).
    passwort_verschluesselt: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    absender: Mapped[str] = mapped_column(String(255), nullable=False)
    absender_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    timeout: Mapped[float] = mapped_column(
        Integer, nullable=False, default=int(STANDARD_TIMEOUT)
    )
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    #: Wird beim Speichern gesetzt, damit die Oberflaeche „zuletzt geaendert"
    #: zeigen kann, ohne einen zweiten Zeitstempel zu fuehren.
    eingerichtet: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
