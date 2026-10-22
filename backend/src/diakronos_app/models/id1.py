"""Umschlüsselung der Mitglied-Kennungen — SQLAlchemy-Modell (ID-1f).

Die Tabelle entsteht in der Migration `id1_mitglied_kennungen` (ID-1): sie hält
`alt` -> `neu` der Mitglieder, deren Kennung im Betrieb noch der Klarname war.
Sie ist ein UMZUGSPROTOKOLL, kein Nachweis: die Löschung auf Antrag entfernt die
Zeile einer gelöschten Person (`dsgvo_anonymisierung.ZEILEN_LOESCHEN`), sonst
stünde ihr Klarname hier dauerhaft.

Das Modell steht hier, damit die Löschung die Tabelle über die Metadaten findet
(`dsgvo_anonymisierung._tabelle`) und der Inventar-Test sie prüfen kann. Die
Spalten folgen der Migration (VARCHAR(140), `alt` ist der Schlüssel).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MitgliedKennung(Base):
    __tablename__ = "id1_mitglied_kennung"

    #: Frühere Kennung (im Betrieb: der Klarname). Protokoll, kein Fachdatum.
    alt: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: Kennung, unter der die Person seit ID-1 geführt wird.
    neu: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    umgeschluesselt_am: Mapped[Any | None] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
