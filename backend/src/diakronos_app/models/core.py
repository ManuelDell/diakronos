"""Frappe-Core-Stubs — Fremd-Referenzen ausserhalb der 73 DocTypes.

Diese Modelle sind bewusst schlank: sie existieren, damit die ForeignKeys der
generierten Modelle aufloesen und der spatere 1:1-Import funktioniert. Sie sind
NICHT Teil der 73 DocTypes des Frappe-Originals.

GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base


class User(Base):
    """Frappe `User` — 12 Links der 73 zeigen hierauf."""

    __tablename__ = "user"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(140), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_type: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # P4g: `session.get_current_user_context` liest `frappe.db.get_value("User",
    # user, ["full_name", "user_image", "email"])`. `user_image` ist eine echte
    # tabUser-Spalte (Spaltenabzug der Betriebs-DB), fehlte aber im Stub.
    user_image: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # A1a: uebernommener Frappe-Passworthash (`__Auth`, fieldname='password').
    # Zwei Formate koennen hier liegen: die aus Frappe importierten
    # `$pbkdf2-sha256$...`-Hashes und Argon2-Hashes fuer neu gesetzte
    # Passwoerter. Kein Klartext, keine Fernet-Verschluesselung.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class Role(Base):
    """Frappe `Role` — 3 Links der 73 zeigen hierauf."""

    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)


class DocType(Base):
    """Frappe `DocType` — 7 Links der 73 zeigen hierauf."""

    __tablename__ = "doctype"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)


class UserRole(Base):
    """Frappe Child `User Role` — Ziel der Tabelle `Kalender.leserechte`."""

    __tablename__ = "user_role"

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
    role: Mapped[str | None] = mapped_column(String(140), nullable=True)


class HasRole(Base):
    """Frappe Child `Has Role` — Rollenzuweisung eines Users.

    Quelle: `inventar/live_schema_ist.tsv` (`tabHas Role`). Traegt die
    Rollenzugehoerigkeit als Kind von `User` (`parent` = username, `role` =
    Rollenname). Das ist die Wahrheit hinter `frappe.get_roles(user)`.
    NICHT mit `UserRole` verwechseln — das ist der Link-Ziel-Stub fuer
    `Kalender.leserechte`.
    """

    __tablename__ = "has_role"

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
    role: Mapped[str | None] = mapped_column(String(140), nullable=True)


class EventParticipants(Base):
    """Frappe Child `Event Participants` — Ziel der Tabelle `Element.event_participants`."""

    __tablename__ = "event_participants"

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
    reference_doctype: Mapped[str | None] = mapped_column(String(140), nullable=True)
    reference_docname: Mapped[str | None] = mapped_column(String(140), nullable=True)


class DynamicLinkModel(Base):
    """Frappe Child `Dynamic Link` — Ziel der Tabelle `Element.links`."""

    __tablename__ = "dynamic_link"

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
    link_doctype: Mapped[str | None] = mapped_column(String(140), nullable=True)
    link_name: Mapped[str | None] = mapped_column(String(140), nullable=True)


class FileModel(Base):
    """Frappe `File` (P2c) — Ablage-Metadaten fuer `/api/method/upload_file`.

    Die Datei selbst liegt im Dateisystem (Volume, siehe `settings.files_dir`);
    hier steht nur der Verweis. `file_url` ist der Pfad, den die SPA liest.
    """

    __tablename__ = "file"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attached_to_doctype: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    attached_to_name: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    attached_to_field: Mapped[str | None] = mapped_column(String(140), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    folder: Mapped[str | None] = mapped_column(String(140), nullable=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NotificationLog(Base):
    """Frappe-Core `Notification Log` (P4g) — In-App-Benachrichtigungen.

    Quelle: Frappe-Schema. Frappe-Core-DocType (nicht in den
    73), aber LIVE vorhanden und von `diakonos.api.audit` beschrieben/gelesen.
    Sichtbarkeit ist datenschutzrelevant: gefiltert wird IMMER ueber `for_user`.
    """

    __tablename__ = "notification_log"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    for_user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    type: Mapped[str | None] = mapped_column(String(140), nullable=True)
    email_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(140), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    document_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    attached_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    from_user: Mapped[str | None] = mapped_column(String(140), nullable=True)
    link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_header: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserNotificationPreference(Base):
    """Frappe-Core `User Notification Preference` (P4g).

    Quelle: Frappe-Schema. Frappe-Core-DocType, LIVE
    vorhanden; regelt, ob ein User In-App/E-Mail-Benachrichtigungen bekommt.
    """

    __tablename__ = "user_notification_preference"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    creation: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(140), nullable=True)
    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user: Mapped[str | None] = mapped_column(String(140), ForeignKey("user.name"), nullable=True)
    email: Mapped[str | None] = mapped_column(String(140), nullable=True)
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
