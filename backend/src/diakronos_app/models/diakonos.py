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
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from diakronos_app.models.base import Base

if TYPE_CHECKING:
    from diakronos_app.models.core import DocType
    from diakronos_app.models.kronos import Element
    from diakronos_app.models.kronos import ElementRessource
    from diakronos_app.models.kronos import Eventkategorie
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.psalmos import Liedfassung
    from diakronos_app.models.psalmos import Liedgruppe
    from diakronos_app.models.kronos import Ressource
    from diakronos_app.models.core import Role
    from diakronos_app.models.core import User


class Anmeldeformular(Base):
    __tablename__ = "anmeldeformular"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bezeichnung: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    mit_gaesten: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mit_kinder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    felder: Mapped[list["AnmeldeformularFeld"]] = relationship(
        primaryjoin="Anmeldeformular.name == foreign(AnmeldeformularFeld.parent) and AnmeldeformularFeld.parentfield == 'felder'",
        foreign_keys="[AnmeldeformularFeld.parent]",
        order_by="AnmeldeformularFeld.idx",
        viewonly=True,
    )
    dokumente: Mapped[list["AnmeldeformularDokument"]] = relationship(
        primaryjoin="Anmeldeformular.name == foreign(AnmeldeformularDokument.parent) and AnmeldeformularDokument.parentfield == 'dokumente'",
        foreign_keys="[AnmeldeformularDokument.parent]",
        order_by="AnmeldeformularDokument.idx",
        viewonly=True,
    )
    dsgvo_text_override: Mapped[Any | None] = mapped_column(Text, nullable=True)
    bestaetigung_text: Mapped[Any | None] = mapped_column(Text, nullable=True)

class AnmeldeformularDokument(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "anmeldeformular_dokument"

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
    label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    datei: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    bestaetigung_pflicht: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class AnmeldeformularFeld(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "anmeldeformular_feld"

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
    label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    feldtyp: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    optionen: Mapped[Any | None] = mapped_column(Text, nullable=True)
    pflichtfeld: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fuer_gaeste: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fuer_kinder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Anmeldung(Base):
    __tablename__ = "anmeldung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anmeldungstyp: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    anmeldedatum: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    verarbeitet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mitglied: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    registrierungslink: Mapped[str | None] = mapped_column(String(140), ForeignKey("registrierungslink.name"), nullable=True)
    vorname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    nachname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    email: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    telefon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    geburtstag: Mapped[Any | None] = mapped_column(Date, nullable=True)
    dsgvo_zustimmung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dsgvo_text_snapshot: Mapped[Any | None] = mapped_column(Text, nullable=True)
    ip_adresse: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    referenz_typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element: Mapped[str | None] = mapped_column(String(140), ForeignKey("element.name"), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    kommentar: Mapped[Any | None] = mapped_column(Text, nullable=True)
    kinder: Mapped[list["AnmeldungKind"]] = relationship(
        primaryjoin="Anmeldung.name == foreign(AnmeldungKind.parent) and AnmeldungKind.parentfield == 'kinder'",
        foreign_keys="[AnmeldungKind.parent]",
        order_by="AnmeldungKind.idx",
        viewonly=True,
    )
    antworten: Mapped[list["AnmeldungAntwort"]] = relationship(
        primaryjoin="Anmeldung.name == foreign(AnmeldungAntwort.parent) and AnmeldungAntwort.parentfield == 'antworten'",
        foreign_keys="[AnmeldungAntwort.parent]",
        order_by="AnmeldungAntwort.idx",
        viewonly=True,
    )
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    name_freitext: Mapped[Any | None] = mapped_column(Text, nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    email_freitext: Mapped[Any | None] = mapped_column(Text, nullable=True)

class AnmeldungAntwort(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "anmeldung_antwort"

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
    feldlabel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    antwort: Mapped[Any | None] = mapped_column(Text, nullable=True)

class AnmeldungKind(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "anmeldung_kind"

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
    vorname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    nachname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    geburtstag: Mapped[Any | None] = mapped_column(Date, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    zeitstempel: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    action_typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    target_doctype: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    target_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    notification_gesendet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_triggered: Mapped[str | None] = mapped_column(String(140), ForeignKey("audit_policy.name"), nullable=True)
    consequence: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    field_changed: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    old_value: Mapped[Any | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[Any | None] = mapped_column(Text, nullable=True)
    confirm_reason: Mapped[Any | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    begruendung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    error_message: Mapped[Any | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    user_agent: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    target_user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)

class AuditPolicy(Base):
    __tablename__ = "audit_policy"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    policy_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    doctype_target: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    field_target: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    action: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(140), ForeignKey("role.name"), nullable=True)
    target_is_other: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consequence: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    confirm_prompt: Mapped[Any | None] = mapped_column(Text, nullable=True)
    confirm_field_label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    notify_on_confirm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Beitrag(Base):
    __tablename__ = "beitrag"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kategorie: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    autor: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    autor_email: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    veroeffentlicht: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auszug: Mapped[Any | None] = mapped_column(Text, nullable=True)
    inhalt: Mapped[Any | None] = mapped_column(Text, nullable=True)
    bild: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kommentare: Mapped[list["BeitragKommentar"]] = relationship(
        primaryjoin="Beitrag.name == foreign(BeitragKommentar.parent) and BeitragKommentar.parentfield == 'kommentare'",
        foreign_keys="[BeitragKommentar.parent]",
        order_by="BeitragKommentar.idx",
        viewonly=True,
    )

class BeitragKommentar(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "beitrag_kommentar"

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
    autor: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    autor_email: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    text: Mapped[Any | None] = mapped_column(Text, nullable=True)

class BugReport(Base):
    __tablename__ = "bug_report"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    naming_series: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gemeldet_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    benutzer: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    mitglied: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    oberflaeche: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    route: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    url: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    viewport: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    user_agent: Mapped[Any | None] = mapped_column(Text, nullable=True)
    build: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_selektor: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    element_text: Mapped[Any | None] = mapped_column(Text, nullable=True)
    element_html: Mapped[Any | None] = mapped_column(Text, nullable=True)
    element_komponente: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    screenshot: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    konsole_log: Mapped[Any | None] = mapped_column(Text, nullable=True)
    netzwerk_log: Mapped[Any | None] = mapped_column(Text, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class DSGVOEinwilligung(Base):
    __tablename__ = "dsgvo_einwilligung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mitglied: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    aktion: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    zeitstempel: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    quelle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ip_adresse: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    user_agent: Mapped[Any | None] = mapped_column(Text, nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    einwilligungstext: Mapped[Any | None] = mapped_column(Text, nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    widerrufen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    widerruf_datum: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    widerruf_begruendung: Mapped[Any | None] = mapped_column(Text, nullable=True)

class DashboardWidget(Base):
    __tablename__ = "dashboard_widget"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    widget_id: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    description: Mapped[Any | None] = mapped_column(Text, nullable=True)
    widget_type: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    category: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    required_role: Mapped[str | None] = mapped_column(String(140), ForeignKey("role.name"), nullable=True)
    required_permission: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    api_method: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    api_args: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    refresh_interval: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    grid_size: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    default_position: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    default_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    empty_state_mode: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    empty_state_message: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class DashboardWidgetUserConfig(Base):
    __tablename__ = "dashboard_widget_user_config"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    widget: Mapped[str | None] = mapped_column(String(140), ForeignKey("dashboard_widget.name"), nullable=True)
    position: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    size: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    collapsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Dienstbereich(Base):
    __tablename__ = "dienstbereich"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ministry: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    sortierung: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    ancestor_path: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    verantwortliche: Mapped[list["DienstbereichVerantwortlicher"]] = relationship(
        primaryjoin="Dienstbereich.name == foreign(DienstbereichVerantwortlicher.parent) and DienstbereichVerantwortlicher.parentfield == 'verantwortliche'",
        foreign_keys="[DienstbereichVerantwortlicher.parent]",
        order_by="DienstbereichVerantwortlicher.idx",
        viewonly=True,
    )
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    ministry_leader: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    ministry_read_role: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class DienstbereichVerantwortlicher(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstbereich_verantwortlicher"

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

class Dienstplan(Base):
    __tablename__ = "dienstplan"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plantitel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    vorlage: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstplan_vorlage.name"), nullable=True)
    dienstbereich: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstbereich.name"), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    jahr: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ist_entwurf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    ende_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    leitung: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    kalender: Mapped[str | None] = mapped_column(String(140), ForeignKey("kalender.name"), nullable=True)
    quelle_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    quelle_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    plan_anzahl_positionen: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    plan_anzahl_verantwortliche: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    plan_anzahl_teilnehmer: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    min_alter: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    max_alter: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    max_teilnehmer: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    anmeldung_aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anmeldeschluss: Mapped[Any | None] = mapped_column(Date, nullable=True)
    anmeldeformular: Mapped[str | None] = mapped_column(String(140), ForeignKey("anmeldeformular.name"), nullable=True)
    registrierungslink: Mapped[str | None] = mapped_column(String(140), ForeignKey("registrierungslink.name"), nullable=True)
    termine: Mapped[list["DienstplanTermin"]] = relationship(
        primaryjoin="Dienstplan.name == foreign(DienstplanTermin.parent) and DienstplanTermin.parentfield == 'termine'",
        foreign_keys="[DienstplanTermin.parent]",
        order_by="DienstplanTermin.idx",
        viewonly=True,
    )
    positionen: Mapped[list["DienstplanPosition"]] = relationship(
        primaryjoin="Dienstplan.name == foreign(DienstplanPosition.parent) and DienstplanPosition.parentfield == 'positionen'",
        foreign_keys="[DienstplanPosition.parent]",
        order_by="DienstplanPosition.idx",
        viewonly=True,
    )
    mitwirkende: Mapped[list["DienstplanMitwirkender"]] = relationship(
        primaryjoin="Dienstplan.name == foreign(DienstplanMitwirkender.parent) and DienstplanMitwirkender.parentfield == 'mitwirkende'",
        foreign_keys="[DienstplanMitwirkender.parent]",
        order_by="DienstplanMitwirkender.idx",
        viewonly=True,
    )
    teilnehmer: Mapped[list["DienstplanTeilnehmer"]] = relationship(
        primaryjoin="Dienstplan.name == foreign(DienstplanTeilnehmer.parent) and DienstplanTeilnehmer.parentfield == 'teilnehmer'",
        foreign_keys="[DienstplanTeilnehmer.parent]",
        order_by="DienstplanTeilnehmer.idx",
        viewonly=True,
    )

class DienstplanMitwirkender(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_mitwirkender"

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
    funktion: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstrolle.name"), nullable=True)
    hauptverantwortlich: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verfuegbar_ab: Mapped[Any | None] = mapped_column(Date, nullable=True)
    verfuegbar_bis: Mapped[Any | None] = mapped_column(Date, nullable=True)

class DienstplanPosition(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_position"

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
    referenz_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    referenz_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    fassung: Mapped[str | None] = mapped_column(String(140), ForeignKey("liedfassung.name"), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    verantwortlicher: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    dienstrolle: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstrolle.name"), nullable=True)
    unterstuetzer: Mapped[list["DienstplanPositionMitglied"]] = relationship(
        primaryjoin="DienstplanPosition.name == foreign(DienstplanPositionMitglied.parent) and DienstplanPositionMitglied.parentfield == 'unterstuetzer'",
        foreign_keys="[DienstplanPositionMitglied.parent]",
        order_by="DienstplanPositionMitglied.idx",
        viewonly=True,
    )
    faellig_ab: Mapped[Any | None] = mapped_column(Date, nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    detail: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    szene: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class DienstplanPositionMitglied(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_position_mitglied"

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

class DienstplanTeilnehmer(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_teilnehmer"

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
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    untergruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("untergruppe.name"), nullable=True)
    anmeldung: Mapped[str | None] = mapped_column(String(140), ForeignKey("anmeldung.name"), nullable=True)
    kontakt_abweichend: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    kann_solo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notiz_intern: Mapped[Any | None] = mapped_column(Text, nullable=True)

class DienstplanTermin(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_termin"

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
    datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    ressource: Mapped[str | None] = mapped_column(String(140), ForeignKey("ressource.name"), nullable=True)
    zusatzressourcen: Mapped[list["ElementRessource"]] = relationship(
        primaryjoin="DienstplanTermin.name == foreign(ElementRessource.parent) and ElementRessource.parentfield == 'zusatzressourcen'",
        foreign_keys="[ElementRessource.parent]",
        order_by="ElementRessource.idx",
        viewonly=True,
    )
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)
    element: Mapped[str | None] = mapped_column(String(140), ForeignKey("element.name"), nullable=True)

class DienstplanVorlage(Base):
    __tablename__ = "dienstplan_vorlage"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vorlagenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    dienstbereich: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstbereich.name"), nullable=True)
    betriebsmodus: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    icon: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    positions_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    positions_label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    positions_plural: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    hat_fassung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vorbereitung_aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vorbereitung_rhythmus: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    vorbereitung_wochentag: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    vorbereitung_uhrzeit: Mapped[Any | None] = mapped_column(Time, nullable=True)
    vorbereitung_label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    einsatz_aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    einsatz_rhythmus: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    einsatz_wochentag: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    einsatz_uhrzeit: Mapped[Any | None] = mapped_column(Time, nullable=True)
    einsatz_label: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    zuteilung_modus: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    rotation_modus: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    rotation_einheit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    rotation_pool: Mapped[list["DienstplanVorlageGruppe"]] = relationship(
        primaryjoin="DienstplanVorlage.name == foreign(DienstplanVorlageGruppe.parent) and DienstplanVorlageGruppe.parentfield == 'rotation_pool'",
        foreign_keys="[DienstplanVorlageGruppe.parent]",
        order_by="DienstplanVorlageGruppe.idx",
        viewonly=True,
    )
    slots: Mapped[list["DienstplanVorlageSlot"]] = relationship(
        primaryjoin="DienstplanVorlage.name == foreign(DienstplanVorlageSlot.parent) and DienstplanVorlageSlot.parentfield == 'slots'",
        foreign_keys="[DienstplanVorlageSlot.parent]",
        order_by="DienstplanVorlageSlot.idx",
        viewonly=True,
    )
    hat_rollenbesetzung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hat_teilnehmerliste: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hat_material: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hat_szenen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hat_planzahlen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    standard_kalender: Mapped[str | None] = mapped_column(String(140), ForeignKey("kalender.name"), nullable=True)
    standard_dienstrolle: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstrolle.name"), nullable=True)
    kategorien: Mapped[list["DienstplanVorlageKategorie"]] = relationship(
        primaryjoin="DienstplanVorlage.name == foreign(DienstplanVorlageKategorie.parent) and DienstplanVorlageKategorie.parentfield == 'kategorien'",
        foreign_keys="[DienstplanVorlageKategorie.parent]",
        order_by="DienstplanVorlageKategorie.idx",
        viewonly=True,
    )

class DienstplanVorlageGruppe(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_vorlage_gruppe"

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
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)

class DienstplanVorlageKategorie(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_vorlage_kategorie"

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
    eventkategorie: Mapped[str | None] = mapped_column(String(140), ForeignKey("eventkategorie.name"), nullable=True)

class DienstplanVorlageSlot(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "dienstplan_vorlage_slot"

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
    inhalt_doctype: Mapped[str | None] = mapped_column(String(140), ForeignKey("doctype.name"), nullable=True)
    inhalt_sammlung: Mapped[str | None] = mapped_column(String(140), ForeignKey("liedgruppe.name"), nullable=True)
    dienstrolle: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstrolle.name"), nullable=True)

class Dienstrolle(Base):
    __tablename__ = "dienstrolle"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rollenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class Gruppe(Base):
    __tablename__ = "gruppe"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gruppenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    dienstbereich: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstbereich.name"), nullable=True)
    gruppentyp: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppentyp.name"), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    sichtbarkeit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    bild: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ancestor_path: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    treffpunkt: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    treffzeit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    verantwortliche: Mapped[list["GruppeVerantwortlicher"]] = relationship(
        primaryjoin="Gruppe.name == foreign(GruppeVerantwortlicher.parent) and GruppeVerantwortlicher.parentfield == 'verantwortliche'",
        foreign_keys="[GruppeVerantwortlicher.parent]",
        order_by="GruppeVerantwortlicher.idx",
        viewonly=True,
    )
    mitglieder: Mapped[list["Gruppenmitgliedschaft"]] = relationship(
        primaryjoin="Gruppe.name == foreign(Gruppenmitgliedschaft.parent) and Gruppenmitgliedschaft.parentfield == 'mitglieder'",
        foreign_keys="[Gruppenmitgliedschaft.parent]",
        order_by="Gruppenmitgliedschaft.idx",
        viewonly=True,
    )
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    leiter: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    obergruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht
    kalender: Mapped[str | None] = mapped_column(String(140), ForeignKey("kalender.name"), nullable=True)

class GruppeVerantwortlicher(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "gruppe_verantwortlicher"

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

class GruppenAnkuendigung(Base):
    __tablename__ = "gruppen_ankuendigung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    text: Mapped[Any | None] = mapped_column(Text, nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    untergruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("untergruppe.name"), nullable=True)
    erstellt_von: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class GruppenAufgabe(Base):
    __tablename__ = "gruppen_aufgabe"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    erledigt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    untergruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("untergruppe.name"), nullable=True)
    faellig: Mapped[Any | None] = mapped_column(Date, nullable=True)
    erstellt_von: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)

class Gruppenmitgliedschaft(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "gruppenmitgliedschaft"

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
    rolle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beitrittsdatum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Gruppenrolle(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "gruppenrolle"

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
    rolle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ist_leitungsrolle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Gruppentyp(Base):
    __tablename__ = "gruppentyp"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    typname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    bild: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    farbe: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    rollen: Mapped[list["Gruppenrolle"]] = relationship(
        primaryjoin="Gruppentyp.name == foreign(Gruppenrolle.parent) and Gruppenrolle.parentfield == 'rollen'",
        foreign_keys="[Gruppenrolle.parent]",
        order_by="Gruppenrolle.idx",
        viewonly=True,
    )

class Mitglied(Base):
    __tablename__ = "mitglied"
    # Fachentscheidung (Manuel, 2026-10-19): Jede Person hat eine EIGENE
    # E-Mail-Adresse — eine Adresse gehoert hoechstens zu EINEM Mitglied.
    # Der partielle Unique-Index vergleicht getrimmt + kleingeschrieben
    # (wie `email_belegung.normalisiere`) und laesst Mitglieder OHNE Adresse
    # weiterhin zu.
    #
    # Angelegt wird er von der Migration `sec2_email_eindeutig`. Fuer den
    # Autogenerate-Vergleich (`alembic check`) ist er in `alembic/env.py`
    # ueber `include_object` ausgenommen: ein Ausdrucksindex
    # (`lower(trim(email))` mit Teilbedingung) laesst sich nicht zuverlaessig
    # aus der Metadaten-Deklaration zurueckrendern, `check` meldete sonst
    # dauerhaft „remove_index + add_index“. Die Deklaration hier haelt die
    # Definition fuer SQLite (Tests) trotzdem bereit.
    __table_args__ = (
        Index(
            "uq_mitglied_email_normalisiert",
            text("lower(trim(email))"),
            unique=True,
            postgresql_where=text("coalesce(trim(email), '') <> ''"),
            sqlite_where=text("coalesce(trim(email), '') <> ''"),
        ),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vorname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    nachname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    email: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    benutzer_mit_mitglied_anlegen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    geburtstag: Mapped[Any | None] = mapped_column(Date, nullable=True)
    telefonnummer: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    postleitzahl: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    wohnort: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    straße: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    nummer: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    mitglied_seit: Mapped[Any | None] = mapped_column(Date, nullable=True)
    user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    auf_bemerkung_gesetzt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auf_bemerkung_gesetzt_seit: Mapped[Any | None] = mapped_column(Date, nullable=True)
    ausgeschlossen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ausgeschlossen_seit: Mapped[Any | None] = mapped_column(Date, nullable=True)
    # AUSTRITT (A1/A4): „Austritt / Deaktivieren“ ist derselbe Riegel wie
    # `ausgeschlossen`, aber mit eigener Absicht. `austritt_grund` unterscheidet
    # beide Faelle (Ausschluss hat keinen Grund hier), `austritt_datum` ist das
    # vom Administrator angegebene Datum und `vor_austritt_status` der Status,
    # in den „Reaktivieren“ zurueckfuehrt. Kein eigenes Boolean-Feld: Sitzung,
    # Login, CalDAV, Rollen und Plan-Rahmen fragen alle `ausgeschlossen` — ein
    # zweites Feld muesste an jeder dieser Stellen mitgeprueft werden.
    # `vor_austritt_konto_aktiv` (AUSTRITT-c, M1) merkt den Kontozustand je
    # wirksamem Konto VOR dem Austritt („Kontoname -> true/false“): nur so
    # bleibt eine vorher gesetzte Kontosperre beim Reaktivieren bestehen.
    austritt_grund: Mapped[Any | None] = mapped_column(Text, nullable=True)
    austritt_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    vor_austritt_status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    vor_austritt_konto_aktiv: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    foto: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ancestor_path: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    geschlecht: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    familienstand: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    elternteil: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    ehepartner: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    datenschutz_einwilligung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    datenschutz_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    foto_einwilligung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    foto_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    werbeeinwilligung: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    werbung_datum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    adressbuch_sichtbarkeit: Mapped[Any | None] = mapped_column(Text, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)
    bereiche: Mapped[list["MitgliedBereich"]] = relationship(
        primaryjoin="Mitglied.name == foreign(MitgliedBereich.parent) and MitgliedBereich.parentfield == 'bereiche'",
        foreign_keys="[MitgliedBereich.parent]",
        order_by="MitgliedBereich.idx",
        viewonly=True,
    )
    beziehungen: Mapped[list["MitgliedBeziehung"]] = relationship(
        primaryjoin="Mitglied.name == foreign(MitgliedBeziehung.parent) and MitgliedBeziehung.parentfield == 'beziehungen'",
        foreign_keys="[MitgliedBeziehung.parent]",
        order_by="MitgliedBeziehung.idx",
        viewonly=True,
    )

class MitgliedBereich(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "mitglied_bereich"

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
    dienstbereich: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstbereich.name"), nullable=True)
    rolle: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class MitgliedBeziehung(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "mitglied_beziehung"

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
    beziehung_zu: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    beziehungstyp: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ist_spiegel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Registrierungslink(Base):
    __tablename__ = "registrierungslink"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bezeichnung: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    typ: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slug: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gueltig_bis: Mapped[Any | None] = mapped_column(Date, nullable=True)
    max_anmeldungen: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    anmeldungen_count: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    anmeldeformular: Mapped[str | None] = mapped_column(String(140), ForeignKey("anmeldeformular.name"), nullable=True)
    element: Mapped[str | None] = mapped_column(String(140), ForeignKey("element.name"), nullable=True)
    link_anzeige: Mapped[Any | None] = mapped_column(String(140), nullable=True)

class RessourcenBuchung(Base):
    __tablename__ = "ressourcen_buchung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ressource: Mapped[str | None] = mapped_column(String(140), ForeignKey("ressource.name"), nullable=True)
    zweck: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    datum_von: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    datum_bis: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    gebucht_von: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gebucht_von_name: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    moderiert_von: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    ablehnungs_grund: Mapped[Any | None] = mapped_column(Text, nullable=True)
    notizen: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Rollenbesetzung(Base):
    __tablename__ = "rollenbesetzung"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dienstplan: Mapped[str | None] = mapped_column(String(140), ForeignKey("dienstplan.name"), nullable=True)
    rolle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    teilnehmer: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    besetzung_nr: Mapped[Any | None] = mapped_column(Integer, nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    zugeteilt_von: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    zugeteilt_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class SichererAnhang(Base):
    __tablename__ = "sicherer_anhang"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mitglied: Mapped[str | None] = mapped_column(String(140), ForeignKey("mitglied.name"), nullable=True)
    datei: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    dateiname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    dateityp: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    loeschfrist: Mapped[Any | None] = mapped_column(Date, nullable=True)
    sichtbarkeits_ebene: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)

class Untergruppe(Base):
    __tablename__ = "untergruppe"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    untergruppenname: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(140), ForeignKey("gruppe.name"), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    sichtbarkeit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    bild: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ancestor_path: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beschreibung: Mapped[Any | None] = mapped_column(Text, nullable=True)
    treffpunkt: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    treffzeit: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    verantwortliche: Mapped[list["UntergruppeVerantwortlicher"]] = relationship(
        primaryjoin="Untergruppe.name == foreign(UntergruppeVerantwortlicher.parent) and UntergruppeVerantwortlicher.parentfield == 'verantwortliche'",
        foreign_keys="[UntergruppeVerantwortlicher.parent]",
        order_by="UntergruppeVerantwortlicher.idx",
        viewonly=True,
    )
    mitglieder: Mapped[list["Untergruppenmitgliedschaft"]] = relationship(
        primaryjoin="Untergruppe.name == foreign(Untergruppenmitgliedschaft.parent) and Untergruppenmitgliedschaft.parentfield == 'mitglieder'",
        foreign_keys="[Untergruppenmitgliedschaft.parent]",
        order_by="Untergruppenmitgliedschaft.idx",
        viewonly=True,
    )

class UntergruppeVerantwortlicher(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "untergruppe_verantwortlicher"

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

class Untergruppenmitgliedschaft(Base):
    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""
    __tablename__ = "untergruppenmitgliedschaft"

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
    rolle: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    status: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    beitrittsdatum: Mapped[Any | None] = mapped_column(Date, nullable=True)
    notiz: Mapped[Any | None] = mapped_column(Text, nullable=True)

class WikiArtikel(Base):
    __tablename__ = "wiki_artikel"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    titel: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    kategorie: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    tags: Mapped[Any | None] = mapped_column(Text, nullable=True)
    autor: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    autor_email: Mapped[Any | None] = mapped_column(String(140), nullable=True)
    ist_neu: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auszug: Mapped[Any | None] = mapped_column(Text, nullable=True)
    inhalt: Mapped[Any | None] = mapped_column(Text, nullable=True)
