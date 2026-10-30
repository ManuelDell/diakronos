#!/usr/bin/env python3
"""Import der Echtdaten aus der Frappe-MariaDB (Site `development`) in die
PostgreSQL-DB der Neuentwicklung.

Quelle ist ein *read-only* gezogener `mysqldump` der Frappe-Datenbank
(`--no-create-info --complete-insert --skip-extended-insert`,
utf8mb4). Dieser Dump wird hier geparst; es wird niemals etwas auf den
Frappe-Host geschrieben. Der Import selbst ist idempotent:

    - Die Zieltabellen der 70 DocTypes mit eigener Tabelle werden vor dem
      Befuellen geleert (`TRUNCATE`). Ein zweiter Lauf ergibt damit
      exakt dieselben Zeilen — keine Duplikate.
    - `name` (String-Primaerschluessel) bleibt 1:1 erhalten.
    - Die drei Singles (`Diakronos Einstellungen`, `Kronos Einstellungen`,
      `Google Kalender Einstellungen`) haben keine eigene MariaDB-Tabelle;
      ihre Werte liegen in `tabSingles` als Key-Value-Zeilen und werden hier
      in die jeweilige Zieltabelle uebertragen.

Typkonvertierung (NICHT die von `frappe_compat.query` — die gilt nur fuer
Abfragen): MariaDB 0/1 -> PostgreSQL boolean, Datums-/Zeitstrings -> echte
`date`/`time`/`timestamp`, NULL bleibt NULL, Leerstring bleibt Leerstring.

Aufruf:
    python tools/import_aus_frappe.py --dump /tmp/p7/frappe_full.sql \
        --database-url 'postgresql+psycopg://diakronos:***@127.0.0.1:5433/diakronos'
    python tools/import_aus_frappe.py --dry-run ...   # nur Parsen + Report

Geschrieben wird AUSSCHLIESSLICH in die Ziel-PostgreSQL-DB.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text

from diakronos_app import import_metadaten

# --------------------------------------------------------------------------
# Parser fuer den MariaDB-INSERT-Strom
# --------------------------------------------------------------------------
# Der Dump wurde mit --skip-extended-insert erzeugt: genau EINE Zeile pro
# INSERT-Statement. `--complete-insert` sorgt fuer eine explizite Spaltenliste.
# Damit ist das Parsen ein Zustandsautomat ueber literale Werte; MariaDB
# nutzt Backslash-Escapes (\' \" \\ \n) — NICHT die SQL-Standard-Doubling-
# Konvention. `NULL` (unquoted) wird zu Python None.

_INSERT_RE = re.compile(r"^INSERT INTO `(?P<table>[^`]+)` \((?P<cols>.*?)\) VALUES \((?P<vals>.*)\);$")

# MariaDB-Escape-Mapping fuer String-Literale.
_ESCAPES = {
    "0": "\0",
    "b": "\b",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "Z": "\x1a",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "%": "\\%",
    "_": "\\_",
}


def _split_values(raw: str) -> list[str | None]:
    """Zerlegt den VALUES-Teil eines INSERT in seine literalen Werte.

    Liefert je Wert den *rohen* String (bei String-Literalen bereits
    unescaped) bzw. None fuer SQL-NULL.
    """
    out: list[str | None] = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if c == " " or c == ",":
            i += 1
            continue
        if c == "'":
            i += 1
            buf: list[str] = []
            while i < n:
                ch = raw[i]
                if ch == "\\":
                    if i + 1 < n:
                        buf.append(_ESCAPES.get(raw[i + 1], raw[i + 1]))
                        i += 2
                        continue
                    buf.append("\\")
                    i += 1
                    continue
                if ch == "'":
                    # '' ist ein escaped Quote im Standardmodus.
                    if i + 1 < n and raw[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(ch)
                i += 1
            out.append("".join(buf))
            continue
        if raw.startswith("NULL", i):
            out.append(None)
            i += 4
            continue
        # Zahl oder Funktionsausdruck ohne Quotes bis zum naechsten Komma.
        j = i
        depth = 0
        while j < n:
            if raw[j] == "(":
                depth += 1
            elif raw[j] == ")":
                depth -= 1
            elif raw[j] == "," and depth == 0:
                break
            j += 1
        out.append(raw[i:j].strip())
        i = j
    return out


@dataclass
class TableData:
    """Alle Zeilen einer MariaDB-Tabelle aus dem Dump."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[str | None]] = field(default_factory=list)

    def count(self) -> int:
        return len(self.rows)


def parse_dump(path: Path, wanted_tables: set[str]) -> dict[str, TableData]:
    """Liest den Dump und liefert {tabellenname: TableData} fuer die gewuenschten."""
    tables: dict[str, TableData] = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("INSERT INTO `"):
                continue
            m = _INSERT_RE.match(line.rstrip("\n"))
            if not m:
                continue
            table = m.group("table")
            if table not in wanted_tables:
                continue
            cols = [c.strip().strip("`") for c in m.group("cols").split(",")]
            vals = _split_values(m.group("vals"))
            td = tables.get(table)
            if td is None:
                td = TableData(columns=cols)
                tables[table] = td
            td.rows.append(vals)
    return tables


# --------------------------------------------------------------------------
# Schema-Abbildung: DocType -> Zieltabelle, inkl. Spalten und Typen
# --------------------------------------------------------------------------
@dataclass
class Column:
    name: str
    kind: str  # "bool" | "date" | "time" | "datetime" | "int" | "float" | "text"


@dataclass
class DocTypeTarget:
    doctype: str
    table: str  # PostgreSQL-Tabellenname
    istable: bool
    issingle: bool
    columns: list[Column]  # Reihenfolge = Zielschema-Reihenfolge (ohne name/docstatus/idx-Sonderfall)


# Frappe-Standardspalten, die in jedem DocType vorkommen.
_STD_COLS = ["creation", "modified", "modified_by", "owner", "docstatus", "idx"]


def load_targets() -> tuple[list[DocTypeTarget], dict[str, list[str]]]:
    """Baut die Zielbeschreibung aus `doctypes.json` + `_mapping.json`.

    Rueckgabe: (targets, quelle_spalten_je_doctype)
    """
    doctypes = import_metadaten.doctypes()
    mapping = import_metadaten.mapping()
    targets: list[DocTypeTarget] = []
    for dt in doctypes:
        name = dt["name"]
        info = mapping.get(name)
        if info is None:
            continue
        cols: list[Column] = []
        for f in dt["fields"]:
            cols.append(Column(f["fieldname"], _fieldtype_to_kind(f.get("fieldtype"))))
        targets.append(
            DocTypeTarget(
                doctype=name,
                table=info["table"],
                istable=bool(info["istable"]),
                issingle=bool(dt.get("issingle")),
                columns=cols,
            )
        )
    return targets, {dt["name"]: [f["fieldname"] for f in dt["fields"]] for dt in doctypes}


def _fieldtype_to_kind(ft: str | None) -> str:
    ft = (ft or "").strip()
    if ft == "Link":
        return "link"
    if ft == "Check":
        return "bool"
    if ft == "Date":
        return "date"
    if ft == "Time":
        return "time"
    if ft in ("Datetime", "Datetime"):
        return "datetime"
    if ft in ("Int", "Long Int", "Integer"):
        return "int"
    if ft in ("Float", "Currency", "Percent"):
        return "float"
    return "text"


# --------------------------------------------------------------------------
# Frappe-CORE-Tabellen (P7b)
# --------------------------------------------------------------------------
# Der erste Import (P7) hat ausschliesslich die 70 App-DocTypes geladen. Die
# Frappe-Core-Tabellen `tabUser` (13 Zeilen) und `tabHas Role` (230 Zeilen)
# blieben aussen vor — mit der Folge, dass niemand Rollen hatte,
# `permissions.get_roles()` leer lieferte und die App fail-closed unbenutzbar
# war. Diese Liste schliesst die Luecke.
#
# Die Zielmodelle sind die schmalen Stubs aus `models/core.py`
# (`tools/gen_models.py:CORE_STUBS`). Sie bilden bewusst nur einen Ausschnitt
# der MariaDB-Spalten ab. Deshalb gilt hier dasselbe Prinzip wie fuer die
# DocTypes: **nur die Spalten importieren, die es im Ziel gibt** — und von
# denen nichts verlieren. `import_table` schneidet die Dump-Spalten ohnehin
# gegen `information_schema.columns` der Zieltabelle; die Spec hier dient der
# Vollstaendigkeitsdokumentation und der Zeilenzahl-Pruefung.
#
# Link-Ziel je Tabelle (Frappe-DocType-Name), damit `tab`-Praefix und
# Reihenfolge stimmen.

# Spalten, die NIEMALS importiert werden — Geheimnisse.
# `tabUser` fuehrt Passwort-/Token-Spalten (`password`, `api_secret`,
# `reset_password_key`, `new_password`, `api_key`, `last_known_versions`).
# Das Zielmodell hat dafuer keine Felder, und es gibt noch keine echte Auth.
# Importiert werden Identitaet und Rollen, keine Geheimnisse. Sollte spaeter
# ein Passwortfeld ins Zielmodell wandern, bleibt es LEER.
_SECRET_COLUMNS = frozenset({
    "password",
    "new_password",
    "api_key",
    "api_secret",
    "reset_password_key",
    "last_reset_password_key_generated_on",
    "last_password_reset_date",
})

# (DocType-Name, Zieltabelle, ist_child_table, Modellklasse)
# Reihenfolge = Importreihenfolge (Eltern vor Kindern).
CORE_TABLES: list[tuple[str, str, bool, str]] = [
    ("DocType", "doctype", False, "DocType"),
    ("Role", "role", False, "Role"),
    ("User", "user", False, "User"),
    ("Has Role", "has_role", True, "HasRole"),
    ("User Role", "user_role", True, "UserRole"),
    ("Dynamic Link", "dynamic_link", True, "DynamicLinkModel"),
    ("Event Participants", "event_participants", True, "EventParticipants"),
    ("File", "file", False, "FileModel"),
]

# Alle Core-Tabellennamen (PG) — fuer Truncate + Pruefung.
CORE_TABLE_NAMES: tuple[str, ...] = tuple(t[1] for t in CORE_TABLES)

# --------------------------------------------------------------------------
# Frappe `__Auth` — Passworthashes uebernehmen (A1a)
# --------------------------------------------------------------------------
# Frappe legt Login-Passwoerter NICHT in `tabUser`, sondern in der
# Schluessel-Wert-Tabelle `__Auth` ab:
#     (doctype, name, fieldname, password, encrypted)
# Fuer Login-Passwoerter gilt `doctype='User' AND fieldname='password'`.
#
# `encrypted=0` -> der Wert ist ein KLARTEXT-Hash (passlib
#                  `$pbkdf2-sha256$29000$...`); der Site-`encryption_key`
#                  wird NICHT gebraucht.
# `encrypted=1` -> Fernet-verschluesselter Wert (z. B. `api_secret`). Das sind KEINE Login-Passwoerter; ohne den
#                  encryption_key nicht lesbar und hier ausdruecklich
#                  IGNORIERT.
#
# Die Zeilen werden nach `user.password_hash` geschrieben. Das ist die
# bewusste Ausnahme von `_SECRET_COLUMNS`: NICHT der Klartext, sondern der
# Hash ist das Ziel — er ist ohne das Passwort nicht verwertbar.
AUTH_TABLE = "__Auth"


def auth_passwort_hashes(auth: TableData) -> dict[str, str]:
    """{username: hash} aus den `__Auth`-Zeilen fuer User-Passwoerter.

    Nur `doctype='User'`, `fieldname='password'`, `encrypted='0'` und ein
    nicht-leerer Hash. Alles andere (encrypted=1, andere fieldnames) faellt
    heraus.
    """
    out: dict[str, str] = {}
    for row in auth.rows:
        rec = dict(zip(auth.columns, row))
        if (rec.get("doctype") or "").strip() != "User":
            continue
        if (rec.get("fieldname") or "").strip() != "password":
            continue
        if str(rec.get("encrypted")) not in ("0", "False", "false"):
            continue
        name = rec.get("name")
        pw = rec.get("password")
        if name and pw:
            out[name] = pw
    return out


def import_auth_passwoerter(
    conn, auth: TableData, *, dry_run: bool, report: dict
) -> int:
    """Schreibt die `__Auth`-Passworthashes nach `user.password_hash`.

    Idempotent: jeder betroffene User wird auf einen definierten Wert gesetzt
    (vorhandener Hash oder NULL). User ohne Hash in der Quelle werden NICHT
    angefasst, wenn sie in der Zieltabelle fehlen — ein `UPDATE` auf einen
    nicht vorhandenen User ist schlicht wirkungslos.
    """
    hashes = auth_passwort_hashes(auth)
    report["auth_passwoerter_gefunden"] = len(hashes)
    if dry_run:
        # Nur die ANZAHL berichten, nie die Hashes selbst.
        report["auth_passwoerter_geschrieben"] = len(hashes)
        return len(hashes)
    # Alle User zunächst auf NULL setzen (idempotenter Ausgangspunkt), dann
    # die vorhandenen Hashes setzen. Kein Hash verlaesst je die DB in ein Log.
    conn.execute(text('UPDATE "user" SET password_hash = NULL'))
    n = 0
    for name, h in hashes.items():
        res = conn.execute(
            text('UPDATE "user" SET password_hash = :h WHERE name = :n'),
            {"h": h, "n": name},
        )
        n += res.rowcount or 0
    report["auth_passwoerter_geschrieben"] = n
    return n


def load_live_schema() -> dict[str, list[str]]:
    """`inventar/live_schema_ist.tsv` -> {"tabUser": ["name", ...], ...}.

    Die TSV ist die dokumentierte Wahrheit der ECHTEN Frappe-DB (P1d). Sie ist
    die Referenz fuer die Spaltenauswahl der Core-Tabellen: das DocType-JSON
    ist hier nicht die Wahrheit (die Core-DocTypes liegen in keinem der 73
    JSONs).
    """
    out: dict[str, list[str]] = {}
    for line in import_metadaten.live_schema().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        table, cols = parts[0].strip(), parts[1]
        out[table] = [c.strip() for c in cols.split(",") if c.strip()]
    return out


def core_targets(
    live_schema: dict[str, list[str]] | None = None,
) -> list[DocTypeTarget]:
    """Baut `DocTypeTarget`s fuer die Frappe-Core-Tabellen.

    Die *Quellspalten* kommen aus `live_schema_ist.tsv` (die echte MariaDB),
    die *Zielspalten* sind durch die schmalen Stubs in `models/core.py`
    begrenzt. `import_table` schneidet ohnehin gegen das Zielinformationsschema;
    hier werden die Geheimnisspalten zusaetzlich hart ausgefiltert.
    """
    live = live_schema if live_schema is not None else load_live_schema()
    targets: list[DocTypeTarget] = []
    for doctype, table, istable, _cls in CORE_TABLES:
        src_cols = live.get("tab" + doctype, [])
        cols: list[Column] = []
        for c in src_cols:
            if c in _SECRET_COLUMNS:
                continue
            cols.append(Column(c, _core_column_kind(c)))
        targets.append(
            DocTypeTarget(
                doctype=doctype,
                table=table,
                istable=istable,
                issingle=False,
                columns=cols,
            )
        )
    return targets


def _core_column_kind(col: str) -> str:
    """Typart einer Core-Spalte — nur fuer die Konvertierung.

    Das Zielinformationsschema entscheidet endgueltig; hier werden die
    Zeit-/Zahlspalten der Core-Tabellen getroffen, damit `convert_value`
    dieselben Python-Typen erzeugt wie der Zielspaltentyp.
    """
    if col in ("creation", "modified"):
        return "datetime"
    if col in ("docstatus", "idx"):
        return "int"
    if col in ("enabled", "is_private", "attending", "disabled", "desk_access",
               "is_custom", "two_factor_auth", "send_welcome_email",
               "unsubscribed", "mute_sounds", "thread_notify", "send_me_a_copy",
               "allowed_in_mentions", "follow_created_documents",
               "follow_commented_documents", "follow_liked_documents",
               "follow_assigned_documents", "follow_shared_documents",
               "notifications", "list_sidebar", "bulk_actions",
               "view_switcher", "form_sidebar", "form_navigation_buttons",
               "timeline", "dashboard", "show_absolute_datetime_in_timeline",
               "logout_all_sessions", "document_follow_notify",
               "bypass_restrict_ip_check_if_2fa_enabled",
               "is_home_folder", "is_attachments_folder", "is_folder"):
        return "bool"
    if col in ("file_size",):
        return "int"
    return "text"


# --------------------------------------------------------------------------
# Typkonvertierung MariaDB -> PostgreSQL-Python-Typ
# --------------------------------------------------------------------------
def convert_value(value: str | None, kind: str):
    if value is None:
        return None
    if kind == "link":
        return value or None
    if kind == "bool":
        # MariaDB 0/1 -> bool. Auch "0"/"1"/"True"/"False" tolerieren.
        s = str(value).strip()
        if s == "":
            return None
        return s not in ("0", "False", "false")
    if kind == "date":
        s = str(value).strip()
        if not s:
            return None
        return s[:10]
    if kind == "time":
        s = str(value).strip()
        if not s:
            return None
        return s
    if kind == "datetime":
        s = str(value).strip()
        if not s:
            return None
        return s
    if kind == "int":
        s = str(value).strip()
        if s == "":
            return None
        try:
            return int(float(s))
        except ValueError:
            return None
    if kind == "float":
        s = str(value).strip()
        if s == "":
            return None
        try:
            return float(s)
        except ValueError:
            return None
    # text: Leerstring bleibt Leerstring, NULL bleibt NULL.
    return value


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------
def build_target_column_kinds(targets: list[DocTypeTarget]) -> dict[str, dict[str, str]]:
    """{table: {column: kind}} fuer alle Zielspalten (inkl. Standardspalten)."""
    kinds: dict[str, dict[str, str]] = {}
    for t in targets:
        cols = {c.name: c.kind for c in t.columns}
        for sc in _STD_COLS:
            cols.setdefault(sc, "datetime" if sc in ("creation", "modified") else "text")
        cols.setdefault("name", "text")
        cols.setdefault("docstatus", "int")
        cols.setdefault("idx", "int")
        cols.setdefault("parent", "text")
        cols.setdefault("parenttype", "text")
        cols.setdefault("parentfield", "text")
        kinds[t.table] = cols
    return kinds


def existing_pg_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t ORDER BY ordinal_position"
        ),
        {"t": table},
    ).fetchall()
    return [r[0] for r in rows]


def import_table(
    conn,
    target: DocTypeTarget,
    td: TableData,
    *,
    dry_run: bool,
    report: dict,
    counts_by_table: dict[str, int] | None = None,
    self_ref_tables: set[str] | None = None,
) -> int:
    """Importiert eine Tabelle. Leert sie vorher (TRUNCATE) -> idempotent.

    `counts_by_table` sammelt die *bereits* importierten Zeilenzahlen der
    Zieltabellen; damit werden verwaiste Link-Werte erkannt, die schon in der
    Quelle zeigen ins Leere (Frappe kennt keine echten FKs).
    """
    pg_cols = existing_pg_columns(conn, target.table)
    if not pg_cols:
        report["fehlende_zieltabellen"].append(target.table)
        return 0
    # Spalten des Dumps, die es im Ziel gibt.
    src_cols = [c for c in td.columns if c in pg_cols]
    kinds = build_target_column_kinds([target])[target.table]
    payload = []
    for row in td.rows:
        rec = {}
        for c, v in zip(td.columns, row):
            if c not in pg_cols:
                continue
            rec[c] = convert_value(v, kinds.get(c, "text"))
        payload.append(rec)
    if dry_run:
        return len(payload)
    # Tabellen werden VOR dem Lauf einmalig gesammelt geleert (main()).
    # Hier kein TRUNCATE CASCADE: das wuerde bereits geladene Kindzeilen
    # wieder loeschen.
    if not payload:
        return 0
    cols = [c for c in src_cols]
    stmt = sa.text(
        f'INSERT INTO "{target.table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '
        f'VALUES ({", ".join(":" + c for c in cols)})'
    )
    conn.execute(stmt, payload)
    return len(payload)


def _truncate_targets(conn, tables: list[str]) -> None:
    """Leert alle Zieltabelle in EINEM Statement (idempotenter Ausgangspunkt).

    `TRUNCATE ... CASCADE` einmalig fuer alle Tabellen: die Reihenfolge
    innerhalb des Statements ist fuer PG irrelevant, weil FK-Checks zu diesem
    Zeitpunkt (replica-Rolle) aus sind.
    """
    present = [t for t in tables if existing_pg_columns(conn, t)]
    if not present:
        return
    joined = ", ".join('"' + t + '"' for t in present)
    conn.execute(text(f"TRUNCATE TABLE {joined} CASCADE"))


def fk_edges(conn) -> list[tuple[str, str]]:
    """(child_table, parent_table)-Kanten aus dem Zielschema.

    Nur Kanten zwischen Tabellen, die wir importieren (public-Schema).
    """
    rows = conn.execute(
        text(
            "SELECT conrelid::regclass::text AS child, confrelid::regclass::text AS parent "
            "FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace"
        )
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def topo_order(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Stabile topologische Sortierung: Eltern vor Kindern.

    Zyklen (z.B. element <-> registrierungslink) werden erkannt; die
    betroffenen Tabellen werden trotzdem ausgegeben (der Import laeuft mit
    deaktivierten FK-Checks, weil Frappe selbst keine FKs kennt).
    """
    ts = set(tables)
    adj: dict[str, set[str]] = {t: set() for t in tables}  # t -> abhaengige
    indeg: dict[str, int] = {t: 0 for t in tables}
    for child, parent in edges:
        if child in ts and parent in ts and child != parent:
            if child not in adj[parent]:
                adj[parent].add(child)
                indeg[child] += 1
    # Selbstbezuege ignorieren (mitglied -> mitglied).
    order: list[str] = []
    ready = sorted([t for t in tables if indeg[t] == 0])
    while ready:
        t = ready.pop(0)
        order.append(t)
        for c in sorted(adj[t]):
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(c)
        ready.sort()
    if len(order) < len(tables):
        rest = sorted(ts - set(order))
        order.extend(rest)
    return order


# Frappe-Singles: Werte aus tabSingles in die jeweilige Einstellungstabelle.
SINGLE_TARGETS = {
    "Diakronos Einstellungen": "diakronos_einstellungen",
    "Kronos Einstellungen": "kronos_einstellungen",
    "Google Kalender Einstellungen": "google_kalender_einstellungen",
}


def import_singles(conn, singles: TableData, *, dry_run: bool, report: dict) -> dict[str, int]:
    """Uebertraegt tabSingles-Zeilen in die drei Einstellungstabellen."""
    # {doctype: {field: value}}
    by_dt: dict[str, dict[str, str | None]] = {}
    for row in singles.rows:
        rec = dict(zip(singles.columns, row))
        dt = rec.get("doctype")
        by_dt.setdefault(dt, {})[rec.get("field")] = rec.get("value")

    counts: dict[str, int] = {}
    for dt, table in SINGLE_TARGETS.items():
        fields = by_dt.get(dt, {})
        if not fields:
            counts[dt] = 0
            continue
        pg_cols = existing_pg_columns(conn, table)
        rec = {}
        for f, v in fields.items():
            if f in pg_cols:
                rec[f] = v  # Werte sind alle text; PG castet auf Zieltyp
        if not rec:
            counts[dt] = 0
            continue
        if not dry_run:
            cols = list(rec.keys())
            stmt = sa.text(
                f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '
                f'VALUES ({", ".join(":" + c for c in cols)})'
            )
            conn.execute(stmt, rec)
        counts[dt] = 1
        report["singles_geschrieben"][dt] = rec
    return counts


def pruefe_import_links(conn, tables, targets, core, report):
    """Nachkontrolle vor COMMIT; neu entstandene/unpruefbare Waisen rollen zurueck.

    Quell-Altwaisen werden als Mengen ausgewiesen, nicht als personenbezogene
    Datensaetze ins Importlog geschrieben. Die separate Vollpruefung kann bei
    Bedarf weiterhin einen geschuetzten Detailbericht erzeugen.
    """
    from import_pruefung import check_links

    ergebnis = check_links(tables, targets, conn, core=core)
    report["waisenpruefung"] = ergebnis.numbers
    if not ergebnis.passed:
        raise RuntimeError("Import abgebrochen: Link-Prüfung fehlgeschlagen "
                           f"({json.dumps(ergebnis.numbers, ensure_ascii=False)}).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Import Frappe-MariaDB -> PostgreSQL")
    ap.add_argument("--dump", required=True, help="Pfad zum mysqldump (read-only gezogen)")
    ap.add_argument("--database-url", required=True, help="Ziel-PostgreSQL-URL")
    ap.add_argument("--dry-run", action="store_true", help="nur parsen + Report, nichts schreiben")
    ap.add_argument("--report-json", default=None, help="Report als JSON speichern")
    args = ap.parse_args()

    targets, _ = load_targets()
    core = core_targets()
    all_targets = targets + core
    table_names = {"tab" + t.doctype for t in all_targets}
    table_names.add("tabSingles")
    table_names.add(AUTH_TABLE)

    dump = Path(args.dump)
    tables = parse_dump(dump, table_names)
    db_by_table = {("tab" + t.doctype): t for t in all_targets}

    report: dict = {
        "dump": str(dump),
        "dry_run": args.dry_run,
        "tabellen_importiert": 0,
        "zeilen_importiert": 0,
        "zeilen_je_doctype": {},
        "fehlende_zieltabellen": [],
        "fehlende_dump_tabellen": [],
        "singles_geschrieben": {},
        "core_tabellen": [t.doctype for t in core],
        "geheimspalten_nicht_importiert": sorted(_SECRET_COLUMNS),
        "auth_passwoerter_gefunden": 0,
        "auth_passwoerter_geschrieben": 0,
    }

    engine = sa.create_engine(args.database_url, future=True)
    with engine.begin() as conn:
        # FK-Checks waehrend des Imports aus (Frappe kennt keine FKs; die
        # Ziel-DB hat welche. Zyklen element<->registrierungslink und
        # Kind-vor-Eltern-Reihenfolgen wuerden sonst scheitern). Die
        # Verletzungen werden danach in `import_pruefung.py` vollstaendig
        # aufgedeckt, nicht ignoriert.
        conn.execute(text("SET LOCAL session_replication_role = replica"))

        # Reihenfolge: Eltern vor Kindern (stabil); Zyklen hinten.
        # Zuerst die Core-Tabellen (DocType/Role/User/...): die App-Tabellen
        # referenzieren sie ueber FKs, also muessen sie vor ihren Kindern
        # stehen. Die Core-Child-Tabellen (Has Role, User Role, ...) haengen
        # nur an ihren Core-Eltern und werden in der dort festgelegten
        # Reihenfolge geladen — die Topologie der App-Tabellen bleibt davor.
        importables = [t for t in targets if not t.issingle]
        edges = fk_edges(conn)
        app_order = topo_order([t.table for t in importables], edges)
        core_order = [t.table for t in core]
        order = core_order + app_order
        by_table = {t.table: t for t in (core + importables)}

        # Einmaliges Leeren ALLER Zieltabellen vor dem Befuellen: garantiert
        # Idempotenz (zweiter Lauf -> identische Zeilen, keine Duplikate).
        if not args.dry_run:
            _truncate_targets(
                conn,
                [t.table for t in importables]
                + list(CORE_TABLE_NAMES)
                + list(SINGLE_TARGETS.values()),
            )

        for table in order:
            t = by_table[table]
            td = tables.get("tab" + t.doctype)
            if td is None:
                report["fehlende_dump_tabellen"].append(t.doctype)
                continue
            n = import_table(conn, t, td, dry_run=args.dry_run, report=report)
            report["zeilen_je_doctype"][t.doctype] = n
            report["zeilen_importiert"] += n
            report["tabellen_importiert"] += 1

        singles = tables.get("tabSingles")
        if singles is not None:
            sc = import_singles(conn, singles, dry_run=args.dry_run, report=report)
            report["singles_zeilen"] = sc

        # A1a: Passworthashes aus `__Auth` -> `user.password_hash`.
        # Setzt voraus, dass `user` bereits befuellt ist (Core-Import oben).
        auth = tables.get(AUTH_TABLE)
        if auth is not None:
            import_auth_passwoerter(conn, auth, dry_run=args.dry_run, report=report)
        else:
            report["fehlende_dump_tabellen"].append(AUTH_TABLE)

        conn.execute(text("SET LOCAL session_replication_role = DEFAULT"))
        if not args.dry_run:
            pruefe_import_links(conn, tables, targets, core, report)

    report["summe_zeilen_alle_doctypes"] = sum(report["zeilen_je_doctype"].values())
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
