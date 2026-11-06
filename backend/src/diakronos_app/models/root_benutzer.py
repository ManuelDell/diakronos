"""ON-6 — Kennrolle ``root`` (Handmodell, kein Frappe-DocType).

Die ROLLE ``root`` in ``has_role`` ist die Kennzeichnung, die die Oberflaeche
anzeigt und die ``get_roles`` mitliefert. Diese Tabelle ist die AUTORITATIVE
Quelle dafuer, WER sie tragen darf: sie entsteht ausschliesslich durch
``root_benutzer.markiere`` (Ersteinrichtung bzw. Uebertragung) — ein
handgeschriebener ``has_role``-Eintrag allein macht niemanden zum root.
Umgekehrt nimmt ``root_benutzer.entferne`` beides zurueck, und der
Rechtepruefpunkt (``permissions.ist_root``) prueft ohnehin gegen
``gemeinde_einstellungen.root_benutzer`` — die Tabelle ist Protokoll und
Inventar (``dataset_status``), nie die Rechtequelle.

Angelegt von der Migration ``on6_root_benutzer``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Fester Name der Kennrolle in ``has_role``.
ROOT_ROLLE = "root"


class RootUser(Base):
    """Konten, die die Kennrolle ``root`` tragen (hoechstens eines ist wirksam)."""

    __tablename__ = "gruppen_root_user"

    #: ``user.name`` des Kontos. Der Name der Tabelle traegt das Praefix
    #: ``gruppen_``, weil ``root_user`` als Tabellenname nichts ueber den Zweck
    #: sagt und in einem Datenbank-Dump neben ``user`` wie ein Synonym klingt.
    konto: Mapped[str] = mapped_column(String(140), primary_key=True)
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


__all__ = ["ROOT_ROLLE", "RootUser"]
