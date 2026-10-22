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
    from diakronos_app.models.diakonos import Dienstplan
    from diakronos_app.models.diakonos import Dienstrolle
    from diakronos_app.models.core import DocType
    from diakronos_app.models.core import DynamicLinkModel
    from diakronos_app.models.core import EventParticipants
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.diakonos import Registrierungslink
    from diakronos_app.models.core import User
    from diakronos_app.models.core import UserRole


class Ablaufplan(Base):
    __tablename__ = "ablaufplan"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element: Mapped[str | None] = mapped_column(String(140), ForeignKey("element.name"), nullable=True)
    datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    positionen: Mapped[list["AblaufplanPosition"]] = relationship(
        primaryjoin="Ablaufplan.name == foreign(AblaufplanPosition.parent) and AblaufplanPosition.parentfield == 'positionen'",
        foreign_keys="[AblaufplanPosition.parent]",
        order_by="AblaufplanPosition.idx",
        viewonly=True,
    )
    notizen: Mapped[Any | None] = mapped_column(Text, nullable=True)

class AblaufplanPosition(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "ablaufplan_position"

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
    bezeichnung: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    dauer_minuten: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    verantwortlicher: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)
    referenz_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    referenz_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    funktion: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    detail: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class Element(Base):
    __tablename__ = "element"

    # `name` ist der Primaerschluessel und technisch NICHT nullbar. Die
    # Annotation traegt trotzdem `| None`, weil der Frappe-Weg fuer DocTypes
    # mit Benennungsregel (hier `ELE-…`) die Kennung NICHT mitschickt:
    # `_create("Element", {...})` laesst `name` weg und die Schicht vergibt
    # sie. Mit `Mapped[str]` bricht `Document(...)`/`model(**data)` mit
    # „name darf nicht NULL sein“ ab, bevor die Regel ueberhaupt greifen kann
    # (gefunden beim Demo-Seed PUB-2). Die Datenbank setzt die Regel durch.
    name: Mapped[str | None] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repeat_this_event: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ressource: Mapped[str | None] = mapped_column(String(140), ForeignKey("ressource.name"), nullable=True)
    zusaetzliche_ressourcen: Mapped[list["ElementRessource"]] = relationship(
        primaryjoin="Element.name == foreign(ElementRessource.parent) and ElementRessource.parentfield == 'zusaetzliche_ressourcen'",
        foreign_keys="[ElementRessource.parent]",
        order_by="ElementRessource.idx",
        viewonly=True,
    )
    ignore_conflict: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    repeat_till: Mapped[Any | None] = mapped_column(Date, nullable=True)
    monday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Any | None] = mapped_column(Text, nullable=True)
    event_participants: Mapped[list["EventParticipants"]] = relationship(
        primaryjoin="Element.name == foreign(EventParticipants.parent) and EventParticipants.parentfield == 'event_participants'",
        foreign_keys="[EventParticipants.parent]",
        order_by="EventParticipants.idx",
        viewonly=True,
    )
    mitarbeiter: Mapped[list["ElementMitarbeiter"]] = relationship(
        primaryjoin="Element.name == foreign(ElementMitarbeiter.parent) and ElementMitarbeiter.parentfield == 'mitarbeiter'",
        foreign_keys="[ElementMitarbeiter.parent]",
        order_by="ElementMitarbeiter.idx",
        viewonly=True,
    )
    ablaufplan: Mapped[str | None] = mapped_column(String(140), ForeignKey("ablaufplan.name"), nullable=True)
    anmeldung_aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registrierungslink: Mapped[str | None] = mapped_column(String(140), ForeignKey("registrierungslink.name"), nullable=True)
    reference_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    reference_docname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    links: Mapped[list["DynamicLinkModel"]] = relationship(
        primaryjoin="Element.name == foreign(DynamicLinkModel.parent) and DynamicLinkModel.parentfield == 'links'",
        foreign_keys="[DynamicLinkModel.parent]",
        order_by="DynamicLinkModel.idx",
        viewonly=True,
    )
    series_id: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    google_event_id: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_category: Mapped[str | None] = mapped_column(String(140), ForeignKey("eventkategorie.name"), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    dienstplan: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstplan.name"), nullable=True)
    element_color: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    element_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    repeat_on: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_calendar: Mapped[str | None] = mapped_column(String(140), ForeignKey("kalender.name"), nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    auto_repeat: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # P1-5b (W-1): Ablehnungsgrund und Ablehnender am Termin — sichtbar nur fuer
    # Antragsteller und Moderatoren, NICHT in der Beschreibung. Migration
    # p15b_ablehnungsgrund; Vorbild ressourcen_buchung.ablehnungs_grund.
    ablehnungs_grund: Mapped[Any | None] = mapped_column(Text, nullable=True)
    moderiert_von: Mapped[str | None] = mapped_column(String(140), nullable=True)

class ElementMitarbeiter(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "element_mitarbeiter"

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
    mitglied: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    dienstrolle: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstrolle.name"), nullable=True)
    bestaetigt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class ElementRessource(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "element_ressource"

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
    ressource: Mapped[str | None] = mapped_column(String(140), ForeignKey("ressource.name"), nullable=True)
    freitext_ressource: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Eventkategorie(Base):
    __tablename__ = "eventkategorie"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    event_category_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    event_category_detail: Mapped[Any | None] = mapped_column(Text, nullable=True)
    terminart: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    betrifft: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    hat_ablaufplan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hat_text: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oeffentlich: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class GoogleKalenderEinstellungen(Base):
    """Frappe Single (DocType ohne Tabelle mit mehreren Zeilen)."""
    __tablename__ = "google_kalender_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    client_id: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    # G1a: Fernet ciphertext, API-only (google_secrets.py)
    client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_uri: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_data: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Kalender(Base):
    __tablename__ = "kalender"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    calendar_color: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    calender_details: Mapped[Any | None] = mapped_column(Text, nullable=True)
    kalendermoderatoren: Mapped[list["KalenderModerator"]] = relationship(
        primaryjoin="Kalender.name == foreign(KalenderModerator.parent) and KalenderModerator.parentfield == 'kalendermoderatoren'",
        foreign_keys="[KalenderModerator.parent]",
        order_by="KalenderModerator.idx",
        viewonly=True,
    )
    calendar_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    selbstverwaltet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    leserechte: Mapped[list["UserRole"]] = relationship(
        primaryjoin="Kalender.name == foreign(UserRole.parent) and UserRole.parentfield == 'leserechte'",
        foreign_keys="[UserRole.parent]",
        order_by="UserRole.idx",
        viewonly=True,
    )
    schreibrechte: Mapped[list["UserRole"]] = relationship(
        primaryjoin="Kalender.name == foreign(UserRole.parent) and UserRole.parentfield == 'schreibrechte'",
        foreign_keys="[UserRole.parent]",
        order_by="UserRole.idx",
        viewonly=True,
    )

class KalenderModerator(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "kalender_moderator"

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
    user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)

class KronosEinstellungen(Base):
    """Frappe Single (DocType ohne Tabelle mit mehreren Zeilen)."""
    __tablename__ = "kronos_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ressource_pflichtfeld: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    standard_ressource: Mapped[str | None] = mapped_column(String(140), ForeignKey("ressource.name"), nullable=True)

class KronosKanbanZustand(Base):
    __tablename__ = "kronos_kanban_zustand"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    staging_events: Mapped[Any | None] = mapped_column(Text, nullable=True)
    event_snapshots: Mapped[Any | None] = mapped_column(Text, nullable=True)


class ElementAenderung(Base):
    """Offener Aenderungsvorschlag zu einem bereits festgelegten Termin.

    Operator-Entscheidung 16.10. (P1-1, verbindlich): Ein Nicht-Moderator mit
    Schreibrecht darf einen festgelegten Termin nur in Kleinigkeiten
    (Beschreibung, Notiz) sofort aendern. Aenderungen an Datum, Uhrzeit, Ort/
    Ressource oder Kalender bleiben am Termin unwirksam und warten hier als
    Vorschlag auf die Freigabe durch einen Moderator (alt/neu im Vergleich).

    Die Zeile traegt den ganzen vorgeschlagenen Feldstand als JSON; beim
    Freigeben wird er auf das `element` angewandt, beim Ablehnen verworfen.
    Je Termin ist hoechstens EIN offener Vorschlag sinnvoll (der neuere
    ersetzt den aelteren).
    """

    __tablename__ = "element_aenderung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    element: Mapped[str | None] = mapped_column(
        String(140),
        ForeignKey("element.name", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    element_calendar: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("kalender.name"), nullable=True
    )
    antragsteller: Mapped[str | None] = mapped_column(String(140), nullable=True)
    vorschlag: Mapped[Any | None] = mapped_column(Text, nullable=True)


class Ressource(Base):
    __tablename__ = "ressource"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ressource_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kapazitaet: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    wartung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bild: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    tags: Mapped[Any | None] = mapped_column(Text, nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
