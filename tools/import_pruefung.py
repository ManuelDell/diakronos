#!/usr/bin/env python3
"""Integritaetspruefung des Frappe->PostgreSQL-Imports — VOLLSTAENDIG,
keine Stichproben. Vergleicht Quelle (mysqldump) und Ziel (PostgreSQL)
zeilenweise ueber alle 49(+)-Tabellen und 1.429(+)-Zeilen.

Fuenf Pruefungen:
  1. Zeilenzahl je Tabelle alt gegen neu.
  2. `ancestor_path`-Ketten (Gruppe, Untergruppe, Dienstbereich, Mitglied).
  3. Link-Felder auf Verwaisung — getrennt nach "schon in der Quelle"
     und "durch den Import entstanden".
  4. Child-Table-Zuordnung: parent/parenttype/parentfield/idx zeilenweise.
  5. Feldwerte: Hash ueber alle Spalten je Zeile nach Typkonvertierung
     (inkl. `straße`, DSGVO-Felder).

Aufruf:
    python tools/import_pruefung.py --dump /tmp/p7/frappe_full.sql \
        --database-url 'postgresql+psycopg://diakronos:***@db:5432/diakronos' \
        --report inventar/IMPORT_PRUEFUNG.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_aus_frappe import (  # noqa: E402
    CORE_TABLE_NAMES,
    SINGLE_TARGETS,
    build_target_column_kinds,
    convert_value,
    core_targets,
    existing_pg_columns,
    load_targets,
    parse_dump,
)

from diakronos_app import import_metadaten


@dataclass
class CheckResult:
    name: str
    passed: bool
    numbers: dict
    details: list[str]


def load_link_fields() -> list[tuple[str, str, str]]:
    """[(doctype, fieldname, options_doctype)] fuer alle Link-Felder."""
    dts = import_metadaten.doctypes()
    out = []
    for dt in dts:
        for f in dt["fields"]:
            if f.get("fieldtype") == "Link" and f.get("options"):
                out.append((dt["name"], f["fieldname"], f["options"]))
    return out


# --------------------------------------------------------------------------
def fetch_pg_rows(conn, table: str, columns: list[str]) -> dict[str, dict]:
    if not existing_pg_columns(conn, table):
        return {}
    cols = ", ".join('"' + c + '"' for c in columns if c in existing_pg_columns(conn, table))
    rows = conn.execute(text(f'SELECT {cols} FROM "{table}"')).mappings().all()
    return {r["name"]: dict(r) for r in rows}


def check_zeilenzahlen(
    tables: dict, targets: list, conn, report_lines: list[str]
) -> tuple[CheckResult, dict[str, tuple[int, int]]]:
    """Zeilenzahl je Tabelle alt/neu.

    P7b: Die Core-Tabellen (User, Has Role, Role, DocType, User Role,
    Dynamic Link, Event Participants, File) sind seit dem Import-Umbau Teil
    des Zielbestands. Ohne sie hier mitzuzaehlen verschwaende die Pruefung
    genau die Tabellen, die neu dazugekommen sind — die Zeilenzahl-Tabelle
    im Report war insoweit unvollstaendig.
    """
    details: list[str] = []
    per_table: dict[str, tuple[int, int]] = {}
    mismatches: list[str] = []
    for t in targets:
        if t.issingle:
            continue
        td = tables.get("tab" + t.doctype)
        src = td.count() if td else 0
        if existing_pg_columns(conn, t.table):
            dst = conn.execute(text(f'SELECT count(*) FROM "{t.table}"')).scalar()
        else:
            dst = 0
        per_table[t.doctype] = (src, dst)
        if src != dst:
            mismatches.append(f"{t.doctype}: alt={src} neu={dst} (Differenz {dst - src})")
    src_total = sum(v[0] for v in per_table.values())
    dst_total = sum(v[1] for v in per_table.values())
    n_src_tables = sum(1 for v in per_table.values() if v[0] > 0)
    n_dst_tables = sum(1 for v in per_table.values() if v[1] > 0)
    passed = not mismatches
    numbers = {
        "tabellen_geprueft": len(per_table),
        "tabellen_mit_daten_quelle": n_src_tables,
        "tabellen_mit_daten_ziel": n_dst_tables,
        "zeilen_quelle": src_total,
        "zeilen_ziel": dst_total,
        "abweichungen": len(mismatches),
    }
    for m in mismatches:
        details.append("ABWEICHUNG " + m)
    return CheckResult("1. Zeilenzahl je Tabelle", passed, numbers, details), per_table


def check_ancestor_path(tables: dict, targets: list, conn) -> CheckResult:
    """Prueft, dass kein Datensatz NULL/leer hat, wo die Quelle einen Wert hatte."""
    doctypes = ["Gruppe", "Untergruppe", "Dienstbereich", "Mitglied"]
    details: list[str] = []
    numbers: dict = {}
    passed = True
    for dt in doctypes:
        t = next((x for x in targets if x.doctype == dt), None)
        if t is None:
            continue
        td = tables.get("tab" + dt)
        if td is None or "ancestor_path" not in td.columns:
            numbers[dt] = {"quelle_mit_wert": 0, "ziel_leer": 0}
            continue
        ci = td.columns.index("ancestor_path")
        src_rows = {r[td.columns.index("name")]: r[ci] for r in td.rows}
        src_with_value = [k for k, v in src_rows.items() if v not in (None, "")]
        pg_rows = fetch_pg_rows(conn, t.table, ["name", "ancestor_path"])
        ziel_leer = [
            k for k in src_with_value
            if k in pg_rows and pg_rows[k].get("ancestor_path") in (None, "")
        ]
        # Formatpruefung: /Name/|/BereichsName/ (oder /|/ bei Wurzel)
        fmt_bad = []
        for k, v in src_rows.items():
            if v in (None, ""):
                continue
            if k in pg_rows:
                zv = pg_rows[k].get("ancestor_path")
                if zv not in (None, "") and not (zv.startswith("/") and "|" in zv and zv.endswith("/")):
                    fmt_bad.append(f"{k}: {zv!r}")
        numbers[dt] = {
            "quelle_mit_wert": len(src_with_value),
            "ziel_leer": len(ziel_leer),
            "format_verletzt": len(fmt_bad),
        }
        if ziel_leer:
            passed = False
            details.append(f"{dt}: {len(ziel_leer)} Ziel-Datensaetze ohne ancestor_path: {ziel_leer[:10]}")
        if fmt_bad:
            passed = False
            details.append(f"{dt}: {len(fmt_bad)} Formatverletzungen: {fmt_bad[:10]}")
    return CheckResult("2. ancestor_path-Ketten", passed, numbers, details)


def check_links(tables: dict, targets: list, conn, core: list | None = None) -> CheckResult:
    """Link-Felder auf Verwaisung, getrennt nach Quelle/Ziel.

    KORREKTUR (P7b): Die frueher hier verwendete Regel lautete im Kern
    "`val` steht nicht in `src_pk[target_dt]` -> also war die Referenz schon
    in der QUELLE verwaist". Das ist ein Fehlschluss, sobald `src_pk` leer
    ist, weil die Zieltabelle vom Import **gar nicht geladen** wurde: eine
    leere Menge ist kein Nachweis. Genau so verschwand der Befund "Audit
    Log.actor = 'Administrator' -> User existiert in der Quelle nicht",
    obwohl die Quelle 13 User (darunter `Administrator`) hat.

    Eine Referenz gilt nur dann als "in der QUELLE verwaist", wenn das in der
    QUELLE **nachgewiesen** ist:

      * Die Quelltabelle wurde geladen UND ist leer -> nachgewiesen verwaist.
      * Die Quelltabelle ist im Zielmodell/-mapping bekannt und wurde geladen,
        der Wert fehlt -> nachgewiesen verwaist.
      * Die Quelltabelle ist weder im Import-Umfang noch im Dump auffindbar
        -> NICHT nachgewiesen -> eigenes Zaehlwerk `unpruefbar`, KEIN
        stilles "quelle_verwaist", und `passed=False`.
    """
    link_fields = load_link_fields()
    all_targets = list(targets) + list(core or [])
    by_doctype = {t.doctype: t for t in all_targets}
    # Alle Ziel-PKs je Tabelle cachen.
    pk_cache: dict[str, set] = {}

    def pks(dt: str) -> set:
        if dt in pk_cache:
            return pk_cache[dt]
        t = by_doctype.get(dt)
        if t is None or not existing_pg_columns(conn, t.table):
            pk_cache[dt] = set()
            return pk_cache[dt]
        rows = conn.execute(text(f'SELECT name FROM "{t.table}"')).scalars().all()
        pk_cache[dt] = set(rows)
        return pk_cache[dt]

    # Ziel-(Quell-)PKs je DocType aus dem DUMP (Quelle).
    # `None` = die Quelltabelle war NICHT Teil des Imports/Dumps -> unpruefbar.
    # `set()` = geladen, aber leer -> echte Leere (nachweisbar).
    src_pk: dict[str, set | None] = {}
    for t in all_targets:
        td = tables.get("tab" + t.doctype)
        if td is None:
            src_pk[t.doctype] = None
            continue
        ni = td.columns.index("name") if "name" in td.columns else 0
        src_pk[t.doctype] = {r[ni] for r in td.rows}

    details: list[str] = []
    numbers = {
        "link_felder_geprueft": 0,
        "quelle_verwaist": 0,
        "import_verwaist": 0,
        "unpruefbar": 0,
    }
    passed = True
    for dt, field, target_dt in link_fields:
        t = by_doctype.get(dt)
        if t is None:
            continue
        td = tables.get("tab" + dt)
        if td is None or field not in td.columns:
            continue
        numbers["link_felder_geprueft"] += 1
        fi = td.columns.index(field)
        ni = td.columns.index("name")
        src_target = src_pk.get(target_dt, None)
        # Nachweis der Verwaisung in der Quelle ist nur moeglich, wenn die
        # Quelltabelle ueberhaupt geladen wurde.
        quell_entscheidbar = src_target is not None
        for r in td.rows:
            val = r[fi]
            if val in (None, ""):
                continue
            rowname = r[ni]
            # Quelle: zeigt der Wert auf einen existierenden Quell-Datensatz?
            in_src = quell_entscheidbar and val in src_target
            # Ziel: zeigt der Wert auf einen existierenden Ziel-Datensatz?
            in_dst = val in pks(target_dt)
            if not quell_entscheidbar:
                # Weder die Quelle noch das Ziel koennen die Referenz aufloesen
                # -> das ist ein PRUEF-LOCH, kein Freibrief. Nicht als
                # "quelle_verwaist" verbuchen.
                if not in_dst:
                    numbers["unpruefbar"] += 1
                    passed = False
                    details.append(
                        f"UNPRUEFBAR: {dt}.{field} = {val!r} (Zeile {rowname}) "
                        f"-> Quelltabelle fuer {target_dt!r} wurde nicht "
                        f"importiert; Verwaisung in der Quelle NICHT nachgewiesen"
                    )
                continue
            if not in_src and in_dst:
                # In der Quelle verwaist, im Ziel (warum auch immer) vorhanden.
                continue
            if not in_src:
                numbers["quelle_verwaist"] += 1
                if len(details) < 40:
                    details.append(
                        f"QUELLE verwaist (nachgewiesen): {dt}.{field} = {val!r} "
                        f"(Zeile {rowname}) -> {target_dt} existiert in der "
                        f"geladenen Quelltabelle nicht (Quelle: "
                        f"{len(src_target)} Datensaetze)"
                    )
            elif not in_dst:
                numbers["import_verwaist"] += 1
                passed = False
                details.append(
                    f"IMPORT verwaist: {dt}.{field} = {val!r} (Zeile {rowname}) "
                    f"-> {target_dt} fehlt im Ziel, obwohl in der Quelle vorhanden"
                )
    return CheckResult("3. Link-Felder auf Verwaisung", passed, numbers, details)


def check_child_tables(tables: dict, targets: list, conn) -> CheckResult:
    """parent/parenttype/parentfield + idx zeilenweise fuer alle Child-Tables."""
    child_targets = [t for t in targets if t.istable]
    details: list[str] = []
    numbers = {"child_tables": len(child_targets), "zeilen_geprueft": 0, "abweichungen": 0}
    passed = True
    for t in child_targets:
        td = tables.get("tab" + t.doctype)
        if td is None:
            continue
        # Zielzeilen ueber name -> dict.
        pg_rows = fetch_pg_rows(conn, t.table, td.columns)
        for r in td.rows:
            rec = dict(zip(td.columns, r))
            rowname = rec.get("name")
            numbers["zeilen_geprueft"] += 1
            if rowname not in pg_rows:
                details.append(f"{t.doctype}: Zeile {rowname} fehlt im Ziel")
                numbers["abweichungen"] += 1
                passed = False
                continue
            zr = pg_rows[rowname]
            for col in ("parent", "parenttype", "parentfield", "idx"):
                if col not in td.columns:
                    continue
                sv = rec.get(col)
                zv = zr.get(col)
                # idx ist int in PG, im Dump String.
                if col == "idx":
                    sv_n = int(sv) if sv not in (None, "") else None
                    zv_n = int(zv) if zv is not None else None
                    if sv_n != zv_n:
                        details.append(f"{t.doctype}:{rowname}: idx alt={sv} neu={zv}")
                        numbers["abweichungen"] += 1
                        passed = False
                else:
                    if sv != zv:
                        details.append(f"{t.doctype}:{rowname}: {col} alt={sv!r} neu={zv!r}")
                        numbers["abweichungen"] += 1
                        passed = False
    return CheckResult("4. Child-Table-Zuordnung", passed, numbers, details)


def _row_hash(rec: dict, kinds: dict) -> str:
    """Stabiler Hash ueber alle Spaltenwerte nach Typkonvertierung."""
    items = []
    for k in sorted(rec.keys()):
        v = rec[k]
        if v is None:
            items.append(f"{k}=\x00NULL")
        elif isinstance(v, bool):
            items.append(f"{k}=b{int(v)}")
        else:
            items.append(f"{k}={v}")
    return hashlib.sha256("\x1f".join(items).encode("utf-8")).hexdigest()


def check_feldwerte(tables: dict, targets: list, conn) -> CheckResult:
    """Zeilenweiser Wertvergleich ueber ALLE Spalten (nach Typkonvertierung)."""
    details: list[str] = []
    counts: dict[str, int] = {"zeilen_geprueft": 0, "abweichungen": 0, "tabellen": 0}
    dropped_by_table: dict[str, list[str]] = {}
    numbers: dict[str, object] = dict(counts)
    passed = True
    for t in targets:
        if t.issingle:
            continue
        td = tables.get("tab" + t.doctype)
        if td is None or td.count() == 0:
            continue
        kinds = build_target_column_kinds([t])[t.table]
        pg_rows = fetch_pg_rows(conn, t.table, td.columns)
        if not pg_rows:
            details.append(f"{t.doctype}: keine Zielzeilen (Tabelle {t.table})")
            passed = False
            continue
        counts["tabellen"] += 1
        # Nur Spalten vergleichen, die im ZIEL existieren. Frappe-interne
        # Felder ohne Modell-Entsprechung (z.B. `_seen` fuer Notification-
        # Tracking) werden beim Import bewusst verworfen -> kein Datenverlust.
        tgt_cols = set(existing_pg_columns(conn, t.table))
        dropped = sorted(c for c in td.columns if c not in tgt_cols)
        if dropped:
            dropped_by_table[t.doctype] = dropped
        for r in td.rows:
            rec = dict(zip(td.columns, r))
            rowname = rec.get("name")
            counts["zeilen_geprueft"] += 1
            if rowname not in pg_rows:
                details.append(f"{t.doctype}: Zeile {rowname} fehlt im Ziel")
                counts["abweichungen"] += 1
                passed = False
                continue
            # Quelle konvertieren (wie der Import) und vergleichen.
            src_conv = {k: convert_value(v, kinds.get(k, "text")) for k, v in rec.items()}
            zr = pg_rows[rowname]
            diffs = []
            for k in sorted(src_conv.keys()):
                if k not in tgt_cols:
                    continue
                kind = kinds.get(k, "text")
                sv_cmp = _norm_typed(src_conv[k], kind)
                zv_cmp = _norm_typed(zr.get(k), kind)
                if sv_cmp != zv_cmp:
                    diffs.append(f"{k}: alt={src_conv[k]!r} neu={zr.get(k)!r}")
            if diffs:
                counts["abweichungen"] += 1
                passed = False
                if len(details) < 60:
                    details.append(f"{t.doctype}:{rowname}: " + "; ".join(diffs[:5]))
    numbers["tabellen"] = counts["tabellen"]
    numbers["zeilen_geprueft"] = counts["zeilen_geprueft"]
    numbers["abweichungen"] = counts["abweichungen"]
    if dropped_by_table:
        numbers["bewusst_verworfene_spalten"] = dropped_by_table
    return CheckResult("5. Feldwerte (zeilenweiser Hash/Vergleich)", passed, numbers, details)


def _norm(v):
    """Normalisierung fuer den Vergleich.

    Die Quelle liefert rohe MariaDB-Strings ('0', '2026-04-20 11:50:04.000000'),
    das Ziel typisierte Python-Werte (False, datetime). Beide werden auf EINE
    kanonische Form gebracht: bool -> 0/1, Zeitwerte -> 'YYYY-MM-DD HH:MM:SS'
    (ohne Bruchteile), Zahlen ohne Trailing-Nullen. So faellt ECHTER
    Datenverlust auf (abgeschnittene Texte, verlorene Umlaute, NULL vs. ''),
    ohne dass reine Typdarstellung als Abweichung zaehlt.
    """
    import datetime as _dt

    if v is None:
        return None
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, _dt.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, _dt.time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, (int, float)):
        f = float(v)
        if f == int(f):
            return str(int(f))
        return repr(f)
    s = str(v)
    # MariaDB-Strings angleichen: '0'/'1' -> bool-Kanonik nur, wenn der
    # Quellwert aus einem Check-Feld stammt (macht der Aufrufer via kind).
    return s


def _norm_typed(v, kind: str):
    """Normalisierung MIT Feldtyp-Wissen (Check-Felder -> bool-Kanonik)."""
    if v is None:
        return None
    if kind == "bool":
        if isinstance(v, bool):
            return "1" if v else "0"
        s = str(v).strip()
        if s == "":
            return None
        return "0" if s in ("0", "False", "false") else "1"
    if kind == "datetime":
        # '2026-04-20 11:50:04.000000' -> '2026-04-20 11:50:04'
        s = str(v).strip()
        if not s:
            return None
        import datetime as _dt
        if isinstance(v, _dt.datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return s.split(".")[0]
    if kind == "date":
        return str(v).split(" ")[0]
    if kind == "time":
        s = str(v).strip()
        if not s:
            return None
        import datetime as _dt
        if isinstance(v, _dt.time):
            return v.strftime("%H:%M:%S")
        return s.split(".")[0]
    return _norm(v)


# --------------------------------------------------------------------------
def render_report(results: list[CheckResult], per_table: dict, extra: dict) -> str:
    L: list[str] = []
    L.append("# Import-Pruefung: Frappe-MariaDB -> PostgreSQL")
    L.append("")
    L.append("Automatisch generiert von `tools/import_pruefung.py`. "
             "Vollstaendige, zeilenweise Gegenprobe (KEINE Stichproben).")
    L.append("")
    overall = all(r.passed for r in results)
    L.append(f"## Gesamtergebnis: {'BESTANDEN' if overall else 'NICHT BESTANDEN'}")
    L.append("")
    L.append("| # | Pruefung | Ergebnis |")
    L.append("|---|---|---|")
    for r in results:
        L.append(f"| {r.name.split('.')[0]} | {r.name.split('. ', 1)[1]} | "
                 f"{'BESTANDEN' if r.passed else 'NICHT BESTANDEN'} |")
    L.append("")
    for r in results:
        L.append(f"## {r.name}: {'BESTANDEN' if r.passed else 'NICHT BESTANDEN'}")
        L.append("")
        L.append("```")
        L.append(json.dumps(r.numbers, indent=2, ensure_ascii=False))
        L.append("```")
        L.append("")
        if r.details:
            L.append("Details:")
            L.append("")
            for d in r.details:
                L.append(f"- {d}")
            L.append("")
        else:
            L.append("Keine Abweichungen.")
            L.append("")
    # Zeilenzahltabelle alt/neu
    L.append("## Zeilenzahl alt gegen neu (vollstaendig)")
    L.append("")
    L.append("| DocType | Zeilen alt | Zeilen neu | Delta |")
    L.append("|---|---:|---:|---:|")
    for dt in sorted(per_table):
        a, b = per_table[dt]
        L.append(f"| {dt} | {a} | {b} | {b - a:+d} |")
    L.append("")
    L.append(f"Summe alt: {sum(v[0] for v in per_table.values())}, "
             f"Summe neu: {sum(v[1] for v in per_table.values())}")
    L.append("")
    if extra:
        L.append("## Zusatz")
        L.append("")
        L.append("```")
        L.append(json.dumps(extra, indent=2, ensure_ascii=False))
        L.append("```")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--database-url", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    targets, _ = load_targets()
    core = core_targets()
    checked = targets + core
    wanted = {"tab" + t.doctype for t in checked} | {"tabSingles"}
    tables = parse_dump(Path(args.dump), wanted)

    engine = sa.create_engine(args.database_url, future=True)
    with engine.connect() as conn:
        r1, per_table = check_zeilenzahlen(tables, checked, conn, [])
        r2 = check_ancestor_path(tables, targets, conn)
        r3 = check_links(tables, targets, conn, core)
        r4 = check_child_tables(tables, targets, conn)
        r5 = check_feldwerte(tables, checked, conn)
    results = [r1, r2, r3, r4, r5]

    extra = {
        "core_tabellen": sorted(c.doctype for c in core),
        "hinweis": (
            "Core-Tabellen (Frappe-Rahmen) sind seit P7b Teil des Import-Scopes "
            "und werden in Pruefung 1 und 5 mitgezaehlt."
        ),
    }
    md = render_report(results, per_table, extra)
    if args.report:
        Path(args.report).write_text(md, encoding="utf-8")
    print(md)
    if args.json:
        Path(args.json).write_text(
            json.dumps([{"name": r.name, "passed": r.passed, "numbers": r.numbers,
                         "details": r.details} for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
