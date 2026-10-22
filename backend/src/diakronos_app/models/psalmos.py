"""GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.

Quelle: DocType-Schema des Frappe-Originals (P1a). Aenderungen am Generator, dann neu laufen.

AUSNAHME PF2 (2026-10-13): Die Spalten `Lied.titel`, `LiedAnlass.anlass`,
`LiedGruppenzuordnung.gruppe`, `LiedKategorie.kategorie`, `Liedfassung.lied`
und `LiedgruppeLied.lied` tragen von Hand `index=True` (Migration
`pf2_lied_indizes`). Das ist bewusst hier und nicht im Generator: der
Generator kennt keine Indizes, und ein Neulauf wuerde ohnehin die spaeter
handgepflegten Spalten (st2/ln1: buch/seite/quelle) verlieren. Wer diese
Modelle neu erzeugt, muss die sechs `index=True` danach wieder setzen.
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
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.diakonos import SichererAnhang


class Lied(Base):
    __tablename__ = "lied"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True, index=True)
    alternativtitel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gesangbuch_nummer: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ccli_nummer: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gruppen: Mapped[list["LiedGruppenzuordnung"]] = relationship(
        primaryjoin="Lied.name == foreign(LiedGruppenzuordnung.parent) and LiedGruppenzuordnung.parentfield == 'gruppen'",
        foreign_keys="[LiedGruppenzuordnung.parent]",
        order_by="LiedGruppenzuordnung.idx",
        viewonly=True,
    )
    kategorien: Mapped[list["LiedKategorie"]] = relationship(
        primaryjoin="Lied.name == foreign(LiedKategorie.parent) and LiedKategorie.parentfield == 'kategorien'",
        foreign_keys="[LiedKategorie.parent]",
        order_by="LiedKategorie.idx",
        viewonly=True,
    )
    anlaesse: Mapped[list["LiedAnlass"]] = relationship(
        primaryjoin="Lied.name == foreign(LiedAnlass.parent) and LiedAnlass.parentfield == 'anlaesse'",
        foreign_keys="[LiedAnlass.parent]",
        order_by="LiedAnlass.idx",
        viewonly=True,
    )
    strophen: Mapped[list["Liedstrophe"]] = relationship(
        primaryjoin="Lied.name == foreign(Liedstrophe.parent) and Liedstrophe.parentfield == 'strophen'",
        foreign_keys="[Liedstrophe.parent]",
        order_by="Liedstrophe.idx",
        viewonly=True,
    )
    rechte_status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    # ST2-Nachtrag (2026-10-09): Buch/Heft und Heftseite eines Liedes sind
    # eingebaute Attribute der Formatvorlagen (``{lied.buch}``,
    # ``{lied.seite}``). Sie werden NICHT vom Generator aus dem Inventar
    # erzeugt (die Alt-DB kennt sie nicht), sondern von der Migration
    # ``st2_lied_material`` ergaenzt und hier bewusst mitgefuehrt.
    buch: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    seite: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    # LN1 (2026-10-09): klare QUELLE eines Liedes. Eine Wahrheit:
    #   'buch'  = Liederbuch/Heft mit Nummer und/oder Seite
    #   'kopie' = Kopie/Einzelblatt (lose, ohne Nummer)
    #   'ohne'  = ohne Angabe (noch nichts gepflegt)
    # Damit laesst sich ueberall "Nr." vermeiden, wo es keine Nummer gibt.
    quelle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    streaming_erlaubt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rechtehinweis: Mapped[Any | None] = mapped_column(Text, nullable=True)
    zuletzt_gesungen: Mapped[Any | None] = mapped_column(Date, nullable=True)
    anzahl_gesungen: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class LiedAnlass(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "lied_anlass"

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
    anlass: Mapped[str | None] = mapped_column(String(140), ForeignKey("liedanlass.name"), nullable=True, index=True)

class LiedGruppenzuordnung(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "lied_gruppenzuordnung"

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
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True, index=True)

class LiedKategorie(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "lied_kategorie"

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
    kategorie: Mapped[str | None] = mapped_column(String(140), ForeignKey("liedkategorie.name"), nullable=True, index=True)

class LiedMaterial(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "lied_material"

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
    art: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    stimme: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    anhang: Mapped[str | None] = mapped_column(String(140), ForeignKey("sicherer_anhang.name"), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class Liedanlass(Base):
    __tablename__ = "liedanlass"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anlassname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class Liedfassung(Base):
    __tablename__ = "liedfassung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lied: Mapped[str | None] = mapped_column(String(140), ForeignKey("lied.name"), nullable=True, index=True)
    fassungsname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    ist_standard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    besetzung: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    stimmen: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    tonart: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    taktart: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    tempo_bpm: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    dauer_minuten: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    schwierigkeit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    arrangeur: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    material: Mapped[list["LiedMaterial"]] = relationship(
        primaryjoin="Liedfassung.name == foreign(LiedMaterial.parent) and LiedMaterial.parentfield == 'material'",
        foreign_keys="[LiedMaterial.parent]",
        order_by="LiedMaterial.idx",
        viewonly=True,
    )
    externe_links: Mapped[Any | None] = mapped_column(Text, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Liedgruppe(Base):
    __tablename__ = "liedgruppe"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gruppenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    dauer_minuten: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    komponist: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    textautor: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    verlag: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    lizenzhinweis: Mapped[Any | None] = mapped_column(Text, nullable=True)
    lieder: Mapped[list["LiedgruppeLied"]] = relationship(
        primaryjoin="Liedgruppe.name == foreign(LiedgruppeLied.parent) and LiedgruppeLied.parentfield == 'lieder'",
        foreign_keys="[LiedgruppeLied.parent]",
        order_by="LiedgruppeLied.idx",
        viewonly=True,
    )
    rollen: Mapped[list["LiedgruppeRolle"]] = relationship(
        primaryjoin="Liedgruppe.name == foreign(LiedgruppeRolle.parent) and LiedgruppeRolle.parentfield == 'rollen'",
        foreign_keys="[LiedgruppeRolle.parent]",
        order_by="LiedgruppeRolle.idx",
        viewonly=True,
    )
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)

class LiedgruppeLied(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "liedgruppe_lied"

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
    reihenfolge: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    lied: Mapped[str | None] = mapped_column(String(140), ForeignKey("lied.name"), nullable=True, index=True)
    fassung: Mapped[str | None] = mapped_column(String(140), ForeignKey("liedfassung.name"), nullable=True)
    nummer: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    szene: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class LiedgruppeRolle(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "liedgruppe_rolle"

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
    rollenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    rollentyp: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    stimmlage: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    umfang: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    min_alter: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    max_alter: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    anzahl_besetzungen: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Liedkategorie(Base):
    __tablename__ = "liedkategorie"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kategoriename: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class Liedstrophe(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "liedstrophe"

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
    nummer: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    text: Mapped[Any | None] = mapped_column(Text, nullable=True)
    sprache: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    nur_chor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
