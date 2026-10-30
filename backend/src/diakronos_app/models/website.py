"""WEB-1b: Zuordnung Diakronos-Benutzer <-> Primo-Konto.

Warum es diese Tabelle gibt
---------------------------
WEB-1 hat den Primo-Nutzer ueber die **E-Mail** gesucht. Das ist eine
Konto-Uebernahme per Adressgleichheit: wer in Primo ein Konto mit derselben
Adresse hat (oder anlegen laesst), bekommt beim naechsten Login Diakronos'
Rollen-Denkweise uebergestuelpt — und umgekehrt landet ein Diakronos-Benutzer
in einem fremden Primo-Konto.

Deshalb gilt ab WEB-1b: **eine Zuordnung ist die einzige Quelle der Wahrheit**
fuer die Frage, welches Primo-Konto zu einem Diakronos-Benutzer gehoert.
Ohne Zuordnung wird nur dann ein Konto angelegt, wenn in Primo KEIN Konto mit
der Adresse existiert; existiert eines, ist der Weg zu (409) und ein Admin
muss verknuepfen.

Die Tabelle ist **kein** Frappe-DocType (Handmodell wie
``models/sicherung.py``): sie haelt nur eine technische Verknuepfung, keine
Fachdaten, und wird in der Migration ``web1b_primo_konto`` ausdruecklich
angelegt.

Spalten
-------
* ``user``       — Diakronos-Benutzername (``User.name``), Primaerschluessel:
                   ein Benutzer hat hoechstens EIN Primo-Konto.
* ``primo_id``   — PocketBase-``users.id``; UNIQUE: ein Primo-Konto gehoert
                   hoechstens EINEM Diakronos-Benutzer.
* ``email``      — die Adresse, unter der das Konto in Primo angelegt wurde
                   (Nachweis fuer die Verwaltung, keine Identitaet).
* ``angelegt_am`` — Zeitstempel der Zuordnung.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class PrimoKonto(Base):
    """Eine Zeile je verknuepftem Primo-Konto (WEB-1b)."""

    __tablename__ = "website_primo_konto"
    __table_args__ = (
        # UNIQUE als eigener INDEX, nicht als `unique=True` an der Spalte:
        # sonst erzeugt der Vergleich mit `alembic check` einen Unterschied
        # (Index vs. UniqueConstraint), obwohl beide dasselbe bewirken. Der
        # Name ist der aus der Migration.
        Index("uq_website_primo_konto_primo_id", "primo_id", unique=True),
    )

    user: Mapped[str] = mapped_column(String(140), primary_key=True)
    primo_id: Mapped[str] = mapped_column(String(140), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    angelegt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
