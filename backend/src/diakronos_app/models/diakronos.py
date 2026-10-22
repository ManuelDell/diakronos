"""GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.

Quelle: DocType-Schema des Frappe-Originals (P1a). Aenderungen am Generator, dann neu laufen.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from diakronos_app.models.base import Base

if TYPE_CHECKING:
    from diakronos_app.models.core import Role
    from diakronos_app.models.core import User


class DiakronosEinstellungen(Base):
    """Frappe Single (DocType ohne Tabelle mit mehreren Zeilen)."""
    __tablename__ = "diakronos_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    organisationsname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakronos_anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakronos_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakronos_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diakronos_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosEinstellungen.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'diakronos_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )
    kronos_anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kronos_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kronos_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kronos_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosEinstellungen.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'kronos_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )
    kronos_kalender_bezeichnung: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kronos_kalender_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakonos_anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakonos_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    diakonos_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diakonos_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosEinstellungen.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'diakonos_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )
    psalmos_anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    psalmos_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    psalmos_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    psalmos_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosEinstellungen.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'psalmos_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )
    seelsorge_anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    seelsorge_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    seelsorge_sichtbar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seelsorge_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosEinstellungen.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'seelsorge_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )
    demodaten_erstellen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    demodaten_aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dev_modus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class DiakronosModulEinstellung(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "diakronos_modul_einstellung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    parent: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parenttype: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parentfield: Mapped[str | None] = mapped_column(String(140), nullable=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    module_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    anzeige_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    standard_icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    im_app_bereich_anzeigen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sichtbar_fuer_rollen: Mapped[list["DiakronosModulRolle"]] = relationship(
        primaryjoin="DiakronosModulEinstellung.name == foreign(DiakronosModulRolle.parent) and DiakronosModulRolle.parentfield == 'sichtbar_fuer_rollen'",
        foreign_keys="[DiakronosModulRolle.parent]",
        order_by="DiakronosModulRolle.idx",
        viewonly=True,
    )

class DiakronosModulRolle(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "diakronos_modul_rolle"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    parent: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parenttype: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parentfield: Mapped[str | None] = mapped_column(String(140), nullable=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role: Mapped[str | None] = mapped_column(String(140), ForeignKey("role.name"), nullable=True)

class Nutzereinzelrechte(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "nutzereinzelrechte"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    parent: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parenttype: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    parentfield: Mapped[str | None] = mapped_column(String(140), nullable=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nutzer: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
