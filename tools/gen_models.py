#!/usr/bin/env python3
"""Generator: DocType-Inventar -> SQLAlchemy-2.0-Modelle.

Quelle: `inventar/doctypes.json` (aus P1a). NUR diese Datei ist Schema-Quelle;
die rohen JSONs unter `referenz/` werden bewusst NICHT gelesen.

Ausgabe nach `backend/src/diakronos_app/models/`:
  - eine Moduldatei pro DocType-Sammlung (models/<module>.py)
  - models/base.py  (DeclarativeBase `Base`)
  - models/core.py  (Frappe-Core-Stubs: User, Role, DocType, ...)
  - models/__init__.py  (exportiert alle Modelle, `__all__` = alle Klassen)
  - models/_mapping.json (DocType-Name <-> Tabelle <-> Klasse)
  - models/UNMAPPED.md   (Felder, die nicht abbildbar waren)

Die erzeugten Dateien werden mitcommittet, aber NICHT von Hand nachgebessert.
Wenn etwas falsch ist: diesen Generator fixen und neu laufen lassen.

Aufruf:
    python tools/gen_models.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

# --------------------------------------------------------------------------
# Pfade
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTAR = REPO_ROOT / "inventar" / "doctypes.json"
OVERLAY = REPO_ROOT / "inventar" / "schema_overlay.json"
MODELS_DIR = REPO_ROOT / "backend" / "src" / "diakronos_app" / "models"

# --------------------------------------------------------------------------
# Schema-Drift-Overlay (P1d)
# --------------------------------------------------------------------------
# Spalten, die LIVE in der Frappe-DB existieren, aber in den DocType-JSONs
# fehlen. `inventar/live_schema_ist.tsv` ist die Wahrheit des Abgleichs.
# Die Typen und ihre Belege stehen in `inventar/SCHEMA_DRIFT.md`.
#
# Die Overlay-Felder werden ANS ENDE der JSON-Feldliste gehaengt, damit
# bestehende Spaltenpositionen stabil bleiben und das Diff klein ist.
def load_overlay(path: Path = OVERLAY) -> dict[str, list[dict]]:
    """Liest `inventar/schema_overlay.json` -> {DocType: [feld, ...]}."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for dt_name, fields in (raw.get("docTypes") or {}).items():
        clean: list[dict] = []
        for f in fields:
            if not f.get("fieldname") or not f.get("fieldtype"):
                raise SystemExit(
                    f"schema_overlay.json: {dt_name!r} hat ein Feld ohne "
                    f"fieldname/fieldtype: {f!r}")
            clean.append(f)
        out[dt_name] = clean
    return out


# --------------------------------------------------------------------------
# Typ-Mapping — VERBINDLICH (siehe Kanban-Karte P1b). Nicht raten.
# --------------------------------------------------------------------------
LAYOUT_TYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "Button",
    "HTML",
}

# fieldtype -> Baustein fuer mapped_column(...)
SIMPLE_TYPES = {
    "Data": "String(140)",
    "Select": "String(140)",
    "Phone": "String(140)",
    "Color": "String(140)",
    "Attach": "String(140)",
    "Attach Image": "String(140)",
    "Small Text": "Text",
    "Text": "Text",
    "Long Text": "Text",
    "Text Editor": "Text",
    "Code": "Text",
    "JSON": "JSON",
    "Int": "Integer",
    "Date": "Date",
    "Time": "Time",
    "Dynamic Link": "String(140)",
}

# Frappe-Core-Stubs (gehoeren NICHT zu den 73) — bleiben in core.py.
# Wert = tatsaechlicher Klassenname im generierten core.py.
CORE_STUBS = {
    "User": "User",
    "Role": "Role",
    "DocType": "DocType",
    "User Role": "UserRole",
    "Has Role": "HasRole",
    "Event Participants": "EventParticipants",
    "Dynamic Link": "DynamicLinkModel",
    # P2c: Frappe-Core-DocType fuer `/api/method/upload_file`. Kein Link-Ziel
    # der 73, aber die SPA legt hierueber Dateien ab.
    "File": "FileModel",
    # P4g: Frappe-Core-DocTypes fuer `diakonos.api.audit` (Benachrichtigungen).
    # Beide existieren LIVE (inventar/live_schema_ist.tsv), sind aber
    # nicht Teil der 73 App-DocTypes -> ohne Stub wirft `get_all`/`db.count`
    # DoesNotExistError. Quelle ist die Live-Schema-Spaltenliste, nicht ein JSON.
    "Notification Log": "NotificationLog",
    "User Notification Preference": "UserNotificationPreference",
}
CORE_STUB_NAMES = set(CORE_STUBS)

# Tabellennamen der Core-Stubs (muessen zu core.py passen).
CORE_STUB_TABLES = {
    "User": "user",
    "Role": "role",
    "DocType": "doctype",
    "User Role": "user_role",
    "Has Role": "has_role",
    "Event Participants": "event_participants",
    "Dynamic Link": "dynamic_link",
    "File": "file",
    "Notification Log": "notification_log",
    "User Notification Preference": "user_notification_preference",
}


def table_for(doctype_name: str, known_doctypes: set[str]) -> str:
    """Tabellenname fuer ein Link-/Tabellen-Ziel (73er oder Core-Stub)."""
    if doctype_name in CORE_STUB_TABLES:
        return CORE_STUB_TABLES[doctype_name]
    return to_snake(doctype_name)


def target_class(doctype_name: str, known_doctypes: set[str]) -> str:
    """Klassenname fuer ein Link-/Tabellen-Ziel (73er oder Core-Stub)."""
    if doctype_name in CORE_STUBS:
        return CORE_STUBS[doctype_name]
    return to_pascal(doctype_name)

# Child-Type-Feldtypen
CHILD_TABLE_TYPES = {"Table", "Table MultiSelect"}


# --------------------------------------------------------------------------
# Namenskonvention
# --------------------------------------------------------------------------
_UML = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "ae", "Ö": "oe", "Ü": "ue"}


def deumlaut(text: str) -> str:
    for k, v in _UML.items():
        text = text.replace(k, v)
    # Rest per NFD zerlegen und Akzente entfernen.
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def to_snake(name: str) -> str:
    """DocType-Name -> Tabellenname (snake_case, ohne `tab`-Praefix)."""
    s = deumlaut(name)
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    if s and s[0].isdigit():
        s = "t_" + s
    return s


def to_pascal(name: str) -> str:
    """DocType-Name -> Klassenname (PascalCase ohne Leerzeichen)."""
    s = deumlaut(name)
    parts = re.split(r"[^0-9A-Za-z]+", s)
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    if out and out[0].isdigit():
        out = "T" + out
    return out


def module_ident(dt: dict) -> str:
    """Moduldatei-Name fuer einen DocType (aus `module`, sonst `sonstige`)."""
    m = dt.get("module") or "sonstige"
    return to_snake(m)


# --------------------------------------------------------------------------
# Feld-Abbildung
# --------------------------------------------------------------------------
class Issue:
    """Ein nicht (sauber) abbildbares Feld."""

    def __init__(self, doctype, fieldname, kind, detail):
        self.doctype = doctype
        self.fieldname = fieldname
        self.kind = kind
        self.detail = detail


def column_name(fieldname: str) -> str:
    """Feldname -> Spaltenname (py-Identifier). Ungueltige Zeichen -> `_`.

    ACHTUNG: Buchstaben mit Umlaut/ß BLEIBEN erhalten. Sie sind gueltige
    Python-Identifier (`"straße".isidentifier()` ist True) und — wichtiger —
    die LIVE-DB fuehrt die Spalte genau so (`straße`, nicht `strasse` oder
    `stra_e`). Ein frueherer Stand hat `ß` zu `_` verstuemmelt und so eine
    Spalte `stra_e` erzeugt, die es in der DB nicht gibt (siehe
    inventar/SCHEMA_DRIFT.md, Drift-Waechter tests/test_schema_drift.py).
    """
    s = fieldname.strip()
    # Nur echte Trennzeichen ersetzen — Unicode-Buchstaben behalten.
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "unnamed"
    if s[0].isdigit():
        s = "f_" + s
    return s


def classify(fieldtype: str, options):
    """Liefert (kategorie, baustein).

    kategorie in {skip, simple, password, check, datetime, link,
                  dynamic_link, child_table, unknown}
    """
    if fieldtype in LAYOUT_TYPES:
        return "skip", None
    if fieldtype in SIMPLE_TYPES:
        return "simple", SIMPLE_TYPES[fieldtype]
    if fieldtype == "Check":
        return "check", "Boolean"
    if fieldtype == "Datetime":
        return "datetime", "DateTime"
    if fieldtype == "Password":
        return "password", "String(255)"
    if fieldtype == "Link":
        return "link", "String(140)"
    if fieldtype in CHILD_TABLE_TYPES:
        return "child_table", None
    return "unknown", None


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_field(
    dt: dict,
    field: dict,
    known_doctypes: set[str],
    warnings: list[Issue],
) -> tuple[str | None, list[str], str | None]:
    """Rendert fuer ein Feld die Modell-Zeilen.

    Rueckgabe: (spalten_zeile | None, relationship_zeilen, import_hinweis)
    `import_hinweis` ist die Klasse, die importiert werden muss (FK/rel) oder None.
    """
    fieldname = field.get("fieldname") or ""
    fieldtype = field.get("fieldtype") or ""
    options = field.get("options")

    col = column_name(fieldname)
    if not fieldname:
        warnings.append(Issue(dt["name"], "<leer>", "skip",
                              "Feld ohne fieldname uebersprungen"))
        return None, [], None

    category, baustein = classify(fieldtype, options)

    if category == "skip":
        return None, [], None

    if category == "child_table":
        target = (options or "").strip()
        if target not in known_doctypes and target not in CORE_STUBS:
            warnings.append(Issue(
                dt["name"], fieldname, "table-target-missing",
                f"Child-Tabelle {target!r} weder in den 73 noch in core.py"))
            return None, [], None
        rel_name = to_snake(fieldname)
        rel_cls = target_class(target, known_doctypes)
        parent_cls = to_pascal(dt["name"])
        # Frappe-Join: Kind.parent == Eltern.name AND Kind.parentfield == <fieldname>.
        # parentfield trennt mehrere Child-Tabellen desselben Eltern-DocTypes.
        # `viewonly=True`: Frappe schreibt die Kind-Zeilen ueber parent/
        # parenttype/parentfield, nicht ueber eine ORM-Kaskade — der Import
        # laeuft 1:1 ueber diese drei Spalten.
        join_expr = (
            f'{parent_cls}.name == foreign({rel_cls}.parent)'
            f' and {rel_cls}.parentfield == \'{fieldname}\''
        )
        fk_expr = f'[{rel_cls}.parent]'
        lines = [
            f'    {rel_name}: Mapped[list["{rel_cls}"]] = relationship(',
            f'        primaryjoin="{join_expr}",',
            f'        foreign_keys="{fk_expr}",',
            f'        order_by="{rel_cls}.idx",',
            f'        viewonly=True,',
            f'    )',
        ]
        return None, lines, rel_cls

    if category == "link":
        target = (options or "").strip()
        if target in known_doctypes or target in CORE_STUBS:
            target_cls = target_class(target, known_doctypes)
            target_table = table_for(target, known_doctypes)
            line = (
                f"    {col}: Mapped[str | None] = mapped_column("
                f"String(140), ForeignKey(\"{target_table}.name\"), "
                f"nullable=True)"
            )
            return line, [], target_cls
        warnings.append(Issue(
            dt["name"], fieldname, "link-target-missing",
            f"Link-Ziel {target!r} weder in den 73 noch in core.py — "
            f"Spalte ohne FK"))
        line = f"    {col}: Mapped[str | None] = mapped_column(String(140), nullable=True)"
        return line, [], None

    if category == "dynamic_link":
        line = f"    {col}: Mapped[str | None] = mapped_column(String(140), nullable=True)"
        return line, [], None

    if category == "check":
        line = (
            f"    {col}: Mapped[bool] = mapped_column("
            f"Boolean, default=False, nullable=False)"
        )
        return line, [], None

    if category == "datetime":
        line = (
            f"    {col}: Mapped[datetime | None] = mapped_column("
            f"DateTime(timezone=False), nullable=True)"
        )
        return line, [], None

    if category == "password":
        if dt["name"] == "Google Kalender Einstellungen":
            return (f"    # G1a: Fernet ciphertext, API-only (google_secrets.py)\n"
                    f"    {col}: Mapped[str | None] = mapped_column(Text, nullable=True)"), [], None
        line = (
            f"    # TODO verschluesselt speichern\n"
            f"    {col}: Mapped[str | None] = mapped_column(String(255), nullable=True)"
        )
        return line, [], None

    if category == "simple":
        line = f"    {col}: Mapped[Any | None] = mapped_column({baustein}, nullable=True)"
        return line, [], None

    # unbekannt
    warnings.append(Issue(
        dt["name"], fieldname, "fieldtype-unknown",
        f"Feldtyp {fieldtype!r} nicht im Mapping — Spalte NICHT erzeugt"))
    return None, [], None


def render_doctype(
    dt: dict,
    known_doctypes: set[str],
    warnings: list[Issue],
    overlay_fields: list[dict] | None = None,
) -> dict:
    """Rendert eine komplette Modellklasse.

    `overlay_fields` sind Zusatzspalten aus `inventar/schema_overlay.json`
    (Schema-Drift-Korrektur, P1d). Sie werden ANS ENDE gehaengt.
    """
    cls = to_pascal(dt["name"])
    table = to_snake(dt["name"])
    istable = int(dt.get("istable") or 0) == 1

    sealed = False  # belegte Spaltennamen (PK, Standard, parent-Trio)
    used_cols: set[str] = set()
    fk_imports: set[str] = set()
    rel_targets: list[tuple[str, str]] = []  # (rel-name, zielklasse)
    body: list[str] = []

    # --- Primaerschluessel + Standardspalten ---
    body.append('    name: Mapped[str] = mapped_column(String(140), primary_key=True)')
    used_cols.add("name")

    if istable:
        body.append(
            '    parent: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)')
        body.append(
            '    parenttype: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)')
        body.append(
            '    parentfield: Mapped[str | None] = mapped_column(String(140), nullable=True)')
        used_cols.update({"parent", "parenttype", "parentfield"})

    for extra in ("creation", "modified"):
        body.append(
            f'    {extra}: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)')
        used_cols.add(extra)
    for extra in ("modified_by", "owner"):
        body.append(
            f'    {extra}: Mapped[str | None] = mapped_column(String(140), nullable=True)')
        used_cols.add(extra)
    body.append(
        '    docstatus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)')
    body.append('    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)')
    used_cols.update({"docstatus", "idx"})

    # --- Kinder: back_populates-Ziel aus child_tables des Eltern-DocTypes ---
    # Wir loesen die Gegenrichtung spaeter auf; hier nur sammeln.

    # --- Felder ---
    for field in dt.get("fields", []):
        fname = field.get("fieldname") or ""
        col = column_name(fname)
        if fname and col in used_cols:
            warnings.append(Issue(
                dt["name"], fname, "column-collision",
                f"Spaltenname {col!r} kollidiert mit Standard-/PK-Spalte — "
                f"Feld uebersprungen"))
            continue
        line, rel_lines, import_cls = render_field(dt, field, known_doctypes, warnings)
        if line:
            body.append(line)
            used_cols.add(col)
        if import_cls:
            fk_imports.add(import_cls)
        for rl in rel_lines:
            body.append(rl)

    # --- Overlay-Felder (Schema-Drift, P1d) ---
    for field in overlay_fields or []:
        fname = field.get("fieldname") or ""
        col = column_name(fname)
        if col in used_cols:
            warnings.append(Issue(
                dt["name"], fname, "overlay-collision",
                f"Overlay-Spalte {col!r} existiert bereits im DocType-JSON — "
                f"Overlay-Eintrag entfernen (Schema ist dann nicht mehr driftend)"))
            continue
        line, rel_lines, import_cls = render_field(
            dt, field, known_doctypes, warnings)
        if line:
            body.append(f"    # overlay(P1d): in der Live-DB vorhanden, im DocType-JSON nicht")
            body.append(line)
            used_cols.add(col)
        if import_cls:
            fk_imports.add(import_cls)
        for rl in rel_lines:
            body.append(rl)

    return {
        "name": dt["name"],
        "class": cls,
        "table": table,
        "istable": istable,
        "module": module_ident(dt),
        "istree": int(dt.get("is_tree") or 0) == 1,
        "issingle": int(dt.get("issingle") or 0) == 1,
        "fk_imports": sorted(fk_imports),
        "body": body,
    }


# --------------------------------------------------------------------------
# Core-Stubs
# --------------------------------------------------------------------------
CORE_SOURCE = '''"""Frappe-Core-Stubs — Fremd-Referenzen ausserhalb der 73 DocTypes.

Diese Modelle sind bewusst schlank: sie existieren, damit die ForeignKeys der
generierten Modelle aufloesen und der spatere 1:1-Import funktioniert. Sie sind
NICHT Teil der 73 DocTypes aus `inventar/doctypes.json`.

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
    # tabUser-Spalte (inventar/live_schema_ist.tsv), fehlte aber im Stub.
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
'''

BASE_SOURCE = '''"""Gemeinsame DeclarativeBase fuer alle ORM-Modelle.

GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Basisklasse aller Diakronos-Modelle (Frappe-String-PK bleibt erhalten)."""
'''


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------
HEADER = '''"""GENERIERT von tools/gen_models.py — nicht von Hand bearbeiten.

Quelle: inventar/doctypes.json (P1a). Aenderungen am Generator, dann neu laufen.
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
'''


def write_models(rendered: list[dict], core_classes: list[str]) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    (MODELS_DIR / "base.py").write_text(BASE_SOURCE, encoding="utf-8")
    (MODELS_DIR / "core.py").write_text(CORE_SOURCE, encoding="utf-8")

    # Modul -> Klassen
    by_module: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rendered:
        by_module.setdefault(r["module"], []).append(r)

    all_classes: list[str] = []
    mapping: dict = {}

    for module, entries in sorted(by_module.items()):
        parts = [HEADER]
        own = {x["class"] for x in entries}

        # Ziel-Klassen von FKs und relationships sammeln. Alle Ziele kommen in
        # einen TYPE_CHECKING-Block: die Annotationen sind dank
        # `from __future__ import annotations` Strings, und SQLAlchemy loest
        # `relationship("Klassenname")` sowie ForeignKey("tabelle.name") ueber
        # die Registry auf — es braucht KEINE Laufzeit-Importe. Das vermeidet
        # Zirkular-Importe zwischen den Modulen.
        wanted: set[str] = set()
        for e in entries:
            wanted.update(e["fk_imports"])
            for ln in e["body"]:
                m = re.search(r'Mapped\[list\["(\w+)"\]\]', ln)
                if m:
                    wanted.add(m.group(1))

        cross = sorted(wanted - own)
        if cross:
            parts.append("if TYPE_CHECKING:")
            for c in cross:
                origin = CLASS_ORIGIN.get(c)
                if origin is None:
                    parts.append(f"    from diakronos_app.models import {c}  # noqa: F401")
                elif origin == "core":
                    parts.append(f"    from diakronos_app.models.core import {c}")
                else:
                    parts.append(f"    from diakronos_app.models.{origin} import {c}")
            parts.append("")

        for e in entries:
            # Beziehungen brauchen den Import des Kindes, auch wenn gleiches Modul
            parts.append("")
            parts.append(f"class {e['class']}(Base):")
            if e["issingle"]:
                parts.append(
                    '    """Frappe Single (DocType ohne Tabelle mit mehreren Zeilen)."""')
            if e["istable"]:
                parts.append(
                    '    """Frappe Child-Tabelle (istable=1) — Sortierung immer ueber `idx`."""')
            parts.append(f'    __tablename__ = "{e["table"]}"')
            parts.append("")
            parts.extend(e["body"])
            all_classes.append(e["class"])
            mapping[e["name"]] = {
                "table": e["table"],
                "class": e["class"],
                "istable": e["istable"],
            }

        text = "\n".join(parts).rstrip() + "\n"
        (MODELS_DIR / f"{module}.py").write_text(text, encoding="utf-8")

    # __init__.py
    init_lines = [
        '"""Modelle — generiert von tools/gen_models.py."""',
        "from __future__ import annotations",
        "",
        "from diakronos_app.models.base import Base",
        "from diakronos_app.models.core import (",
    ]
    for c in sorted(core_classes):
        init_lines.append(f"    {c},")
    init_lines.append(")")
    init_lines.append("")
    for module in sorted(by_module):
        for e in by_module[module]:
            init_lines.append(f"from diakronos_app.models.{module} import {e['class']}")
    init_lines.append("")
    init_lines.append("__all__ = [")
    for c in sorted(set(all_classes) | set(core_classes)):
        init_lines.append(f'    "{c}",')
    init_lines.append("]")
    init_lines.append("")
    (MODELS_DIR / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")

    # Core-Stubs in das Mapping aufnehmen: sie sind echte Frappe-Tabellen,
    # auf die portierter Code per `get_value("User", ...)` / `get_all("Has Role")`
    # zugreift, und sie muessen ueber `/api/resource/<name>` und `is_known()`
    # erreichbar sein. Ohne Eintrag wirft die Registry DoesNotExistError.
    #
    # `istable` muss stimmen: User Role, Has Role, Event Participants und
    # Dynamic Link sind Frappe-CHILD-Tabellen (sie tragen parent/parenttype/
    # parentfield, siehe inventar/live_schema_ist.tsv). Sie pauschal als
    # istable=False zu fuehren waere falsch — Child-Zeilen werden nach `idx`
    # sortiert und ueber `parent` aufgeloest.
    _CORE_CHILD_TABLES = {"User Role", "Has Role", "Event Participants", "Dynamic Link"}
    for stub_name, stub_class in CORE_STUBS.items():
        mapping[stub_name] = {
            "table": CORE_STUB_TABLES[stub_name],
            "class": stub_class,
            "istable": stub_name in _CORE_CHILD_TABLES,
        }

    (MODELS_DIR / "_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
CLASS_ORIGIN: dict[str, str] = {}  # Klasse -> Modul|core (fuer Import-Aufloesung)


def main() -> int:
    data = json.loads(INVENTAR.read_text(encoding="utf-8"))
    known = {dt["name"] for dt in data}
    overlay = load_overlay()

    # Overlay-Eintraege fuer unbekannte DocTypes sind ein Fehler, kein No-Op:
    # sonst verschwindet eine Drift-Korrektur still.
    unknown_overlay = sorted(set(overlay) - known)
    if unknown_overlay:
        raise SystemExit(
            f"schema_overlay.json nennt unbekannte DocTypes: {unknown_overlay}")

    # Klassen -> Herkunft ermitteln
    for dt in data:
        CLASS_ORIGIN[to_pascal(dt["name"])] = module_ident(dt)
    for cls in CORE_STUBS.values():
        CLASS_ORIGIN[cls] = "core"

    warnings: list[Issue] = []
    rendered = [
        render_doctype(dt, known, warnings, overlay.get(dt["name"]))
        for dt in data
    ]

    core_classes = list(CORE_STUBS.values())

    write_models(rendered, core_classes)

    # UNMAPPED.md
    unmapped = [w for w in warnings]
    lines = [
        "# UNMAPPED — Felder ohne saubere Abbildung",
        "",
        "GENERIERT von `tools/gen_models.py`. Bitte melden, nicht wegputzen.",
        "",
        f"Anzahl Beanstandungen: **{len(unmapped)}**",
        "",
        "| DocType | Feld | Art | Detail |",
        "|---|---|---|---|",
    ]
    for w in unmapped:
        lines.append(f"| {w.doctype} | {w.fieldname} | {w.kind} | {w.detail} |")
    if not unmapped:
        lines.append("| — | — | — | keine — |")
    lines.append("")
    (MODELS_DIR / "UNMAPPED.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Quelle:            {INVENTAR.relative_to(REPO_ROOT)}")
    print(f"DocTypes gelesen:  {len(data)}")
    print(f"Modelle erzeugt:   {len(rendered)}")
    print(f"Module geschrieben:{len({r['module'] for r in rendered})}")
    print(f"Core-Stubs:        {len(core_classes)}")
    print(f"Beanstandungen:    {len(unmapped)}")
    for w in unmapped:
        print(f"  ! {w.doctype}.{w.fieldname}: {w.kind} — {w.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
