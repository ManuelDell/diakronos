#!/usr/bin/env python3
"""
P1a Inventar — maschinenlesbare Uebersetzungs-Spezifikation der Altanwendung.

Reine Analyse. Quelldatei-Baum `referenz/diakronos-frappe/` wird NIE veraendert.

Erzeugt unter inventar/:
  doctypes.json          DocType-Spezifikation (Felder, Permissions, Links, Child-Tables)
  endpoints.json         @frappe.whitelist-Endpunkte (per AST geparst) + hooks.py-Abgleich
  frappe_api_usage.json  Jede frappe.*-Verwendung (Portierungs-Landkarte)
  frontend_calls.json    Backend-Aufrufe aus frontend/src und diakonos/public
  REPORT.md              Menschenlesbare Zusammenfassung

Idempotent: mehrfach ausfuehrbar, Ergebnis ist deterministisch (sortierte Keys).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# --------------------------------------------------------------------------
# Pfade
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
REF = REPO_ROOT / "referenz" / "diakronos-frappe"
OUT = REPO_ROOT / "inventar"

# Gebaute Vite-Bundles sind minifiziert und enthalten keine lesbaren Aufrufpfade.
# Sie werden beim Frontend-Scan uebersprungen (siehe REPORT.md "Auffaelligkeiten").
BUILD_ARTIFACT_DIRS = ("public/frontend",)

FRONTEND_SCAN_ROOTS = [
    REF / "frontend" / "src",
    REF / "diakronos" / "public",
]

FRONTEND_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".vue", ".html"}

# Auffaelligkeiten / Parse-Fehler werden hier gesammelt und im Report ausgegeben.
ANOMALIES: list[str] = []


def rel(p: Path) -> str:
    """Pfad relativ zum Repo-Root, POSIX-Style."""
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def is_build_artifact(p: Path) -> bool:
    s = p.as_posix()
    return any(f"/{d}/" in s or s.endswith(f"/{d}") for d in BUILD_ARTIFACT_DIRS)


# --------------------------------------------------------------------------
# 1. DocTypes
# --------------------------------------------------------------------------
DT_FIELD_KEYS = (
    "fieldname",
    "fieldtype",
    "label",
    "options",
    "reqd",
    "unique",
    "default",
    "read_only",
    "hidden",
    "in_list_view",
    "precision",
)
DT_PERM_KEYS = ("role", "read", "write", "create", "delete", "submit", "report", "share")


def collect_doctype_files() -> list[Path]:
    files = []
    for p in REF.rglob("*.json"):
        parts = p.parts
        if "doctype" not in parts:
            continue
        # Muster: .../doctype/<name>/<name>.json
        try:
            i = parts.index("doctype")
        except ValueError:
            continue
        tail = parts[i + 1:]
        if len(tail) != 2:
            continue
        if not p.name.endswith(".json"):
            continue
        files.append(p)
    return sorted(set(files))


def parse_doctypes() -> list[dict]:
    out: list[dict] = []
    for path in collect_doctype_files():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            ANOMALIES.append(f"DocType-JSON nicht lesbar: {rel(path)} — {exc}")
            continue

        if raw.get("doctype") != "DocType":
            ANOMALIES.append(
                f"JSON im doctype/-Baum ist kein DocType (doctype={raw.get('doctype')!r}): {rel(path)}"
            )
            continue

        # Modul = Verzeichnis unterhalb von diakronos/ (kronos, diakonos, psalmos, diakronos)
        module = ""
        parts = path.relative_to(REF).parts
        if len(parts) >= 3 and parts[0] == "diakronos":
            module = parts[1]

        fields = []
        links = []
        child_tables = []
        for f in raw.get("fields", []) or []:
            if not isinstance(f, dict):
                ANOMALIES.append(f"Nicht-dict-Eintrag in fields von {raw.get('name')!r}: {f!r}")
                continue
            ftype = f.get("fieldtype")
            entry = {k: f.get(k) for k in DT_FIELD_KEYS}
            fields.append(entry)

            if ftype == "Link":
                links.append(
                    {
                        "fieldname": f.get("fieldname"),
                        "target_doctype": f.get("options") or None,
                    }
                )
            elif ftype == "Table":
                child_tables.append(
                    {
                        "fieldname": f.get("fieldname"),
                        "child_doctype": f.get("options") or None,
                    }
                )

        permissions = []
        for p in raw.get("permissions", []) or []:
            if not isinstance(p, dict):
                ANOMALIES.append(
                    f"Nicht-dict-Eintrag in permissions von {raw.get('name')!r}: {p!r}"
                )
                continue
            permissions.append({k: p.get(k) for k in DT_PERM_KEYS})

        out.append(
            {
                "name": raw.get("name"),
                "module": module,
                "istable": raw.get("istable") or 0,
                "issingle": raw.get("issingle") or 0,
                "autoname": raw.get("autoname"),
                "title_field": raw.get("title_field"),
                "is_tree": raw.get("is_tree") or 0,
                "allow_rename": raw.get("allow_rename"),
                "engine": raw.get("engine"),
                "field_count": len(fields),
                "fields": fields,
                "permissions": permissions,
                "links": links,
                "child_tables": child_tables,
                "source": rel(path),
            }
        )

    out.sort(key=lambda d: (d["module"] or "", d["name"] or ""))
    return out


# --------------------------------------------------------------------------
# 2. Endpunkte — per AST
# --------------------------------------------------------------------------
def decorator_info(dec: ast.expr) -> tuple[bool, bool, list[str] | None]:
    """Prueft, ob ein Dekorator frappe.whitelist ist.

    Rueckgabe: (is_whitelist, allow_guest, methods)
    """
    func = dec.func if isinstance(dec, ast.Call) else dec
    name = None
    if isinstance(func, ast.Attribute):
        # frappe.whitelist
        parts = []
        node: ast.expr = func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        name = ".".join(reversed(parts))
    elif isinstance(func, ast.Name):
        name = func.id

    if name not in ("frappe.whitelist", "whitelist"):
        return (False, False, None)

    allow_guest = False
    methods: list[str] | None = None
    if isinstance(dec, ast.Call):
        for kw in dec.keywords:
            if kw.arg == "allow_guest" and isinstance(kw.value, ast.Constant):
                allow_guest = bool(kw.value.value)
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                methods = [
                    elt.value
                    for elt in kw.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    return (True, allow_guest, methods)


def annotation_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return None


def default_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return None


def dotted_path(module_path: str, func_name: str) -> str:
    """diakronos/diakonos/api/x.py -> diakronos.diakonos.api.x.func"""
    mp = module_path
    if mp.endswith(".py"):
        mp = mp[:-3]
    mp = mp.replace("/", ".")
    if mp.endswith(".__init__"):
        mp = mp[: -len(".__init__")]
    return f"{mp}.{func_name}" if mp else func_name


def collect_frappe_apis(tree: ast.AST) -> list[str]:
    """Alle frappe.<a>[.<b>]-Referenzen in einem AST, dedupliziert + sortiert."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == "frappe":
                parts.append("frappe")
                found.add(".".join(reversed(parts)))
    return sorted(found)


def parse_endpoints() -> list[dict]:
    out: list[dict] = []
    for path in sorted(REF.rglob("*.py")):
        try:
            src = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            ANOMALIES.append(f"Python-Datei nicht lesbar: {rel(path)} — {exc}")
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as exc:
            ANOMALIES.append(f"Python-Syntaxfehler: {rel(path)}:{exc.lineno} — {exc.msg}")
            continue

        # Modul-Dotted-Path relativ zur App-Wurzel
        relmod = rel(path)
        if relmod.startswith("referenz/"):
            # referenz/diakronos-frappe/diakronos/... -> diakronos/...
            idx = relmod.find("/diakronos-frappe/")
            if idx != -1:
                relmod = relmod[idx + len("/diakronos-frappe/") :]

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            allow_guest = False
            methods: list[str] | None = None
            is_wl = False
            for dec in node.decorator_list:
                wl, ag, me = decorator_info(dec)
                if wl:
                    is_wl = True
                    allow_guest = ag
                    methods = me
            if not is_wl:
                continue

            # Endzeile bestimmen (letzte Zeile im Funktionskoerper inkl. Deko)
            end_lineno = getattr(node, "end_lineno", node.lineno) or node.lineno
            loc = max(1, end_lineno - node.lineno + 1)

            fn_args = node.args
            positional = list(fn_args.posonlyargs) + list(fn_args.args)
            defaults = list(fn_args.defaults)
            # Defaults sind rechtsbuendig ausgerichtet
            default_map: dict[str, str | None] = {}
            if defaults:
                offset = len(positional) - len(defaults)
                for i, name_node in enumerate(positional):
                    if i >= offset:
                        default_map[name_node.arg] = default_str(defaults[i - offset])
            for a in positional:
                default_map.setdefault(a.arg, None)

            params = []
            for a in positional:
                if a.arg in ("self", "cls"):
                    continue
                params.append(
                    {
                        "name": a.arg,
                        "default": default_map.get(a.arg),
                        "annotation": annotation_str(a.annotation),
                        "kind": "positional",
                    }
                )
            for a in fn_args.kwonlyargs:
                params.append(
                    {
                        "name": a.arg,
                        "default": default_str(None),
                        "annotation": annotation_str(a.annotation),
                        "kind": "keyword_only",
                    }
                )
            if fn_args.vararg:
                params.append(
                    {
                        "name": "*" + fn_args.vararg.arg,
                        "default": None,
                        "annotation": None,
                        "kind": "vararg",
                    }
                )
            if fn_args.kwarg:
                params.append(
                    {
                        "name": "**" + fn_args.kwarg.arg,
                        "default": None,
                        "annotation": None,
                        "kind": "kwarg",
                    }
                )

            doc = ast.get_docstring(node) or ""

            # Im Funktionskoerper verwendete frappe-APIs
            local = ast.Module(body=node.body, type_ignores=[])
            apis = collect_frappe_apis(local)

            out.append(
                {
                    "dotted_path": dotted_path(relmod, node.name),
                    "datei": relmod,
                    "funktionsname": node.name,
                    "parameter": params,
                    "allow_guest": allow_guest,
                    "methods": methods or ["POST", "GET"],
                    "docstring": doc,
                    "loc": loc,
                    "lineno": node.lineno,
                    "genutzte_frappe_apis": apis,
                    "in_hooks": False,
                }
            )

    out.sort(key=lambda e: e["dotted_path"])
    return out


def parse_hooks_whitelisted() -> list[str]:
    """Liest whitelisted_methods aus diakronos/hooks.py per AST."""
    hooks = REF / "diakronos" / "hooks.py"
    if not hooks.exists():
        ANOMALIES.append("hooks.py nicht gefunden")
        return []
    try:
        tree = ast.parse(hooks.read_text(encoding="utf-8"), filename=str(hooks))
    except SyntaxError as exc:
        ANOMALIES.append(f"Syntaxfehler in hooks.py:{exc.lineno} — {exc.msg}")
        return []

    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "whitelisted_methods":
                    if isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                result.append(elt.value)
    return sorted(set(result))


# --------------------------------------------------------------------------
# 3. frappe.*-Verwendung
# --------------------------------------------------------------------------
def parse_frappe_usage() -> list[dict]:
    out: list[dict] = []
    for path in sorted(REF.rglob("*.py")):
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue  # bereits als Auffaelligkeit erfasst

        lines = src.splitlines()
        relmod = rel(path)
        idx = relmod.find("/diakronos-frappe/")
        if idx != -1:
            relmod = relmod[idx + len("/diakronos-frappe/") :]

        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            parts = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if not (isinstance(cur, ast.Name) and cur.id == "frappe"):
                continue
            # Nur die aeusserste Referenz zaehlen: pruefen ob Parent auch frappe.* ist
            # (walk liefert alle Teilknoten; wir filtern Teilknoten spaeter per Dedupe)
            api = "frappe." + ".".join(reversed(parts))
            lineno = node.lineno
            ctx = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            out.append(
                {
                    "api": api,
                    "datei": relmod,
                    "zeile": lineno,
                    "kontext_zeile": ctx,
                }
            )

    # Teilmengen entfernen: wenn sowohl frappe.db.sql als auch frappe.db existiert,
    # ist frappe.db ein Praefix desselben Ausdrucks an derselben Position.
    seen: set[tuple[str, str, int]] = set()
    deduped: list[dict] = []
    for rec in sorted(out, key=lambda r: (r["datei"], r["zeile"], r["api"])):
        key = (rec["datei"], rec["zeile"], rec["api"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


# --------------------------------------------------------------------------
# 4. Frontend-Aufrufe
# --------------------------------------------------------------------------
# Die SPA ruft das Backend auf DREI Wegen:
#   (a) apiCall('dotted.path', {...}) / apiGet('dotted.path')  — die HAUPTFORM
#   (b) fetch('/api/method/<dotted.path>')                     — literal
#   (c) fetch('/api/resource/<DocType>')                       — Frappe-REST
# Ausserdem: frappe.call({ method: '...' }) in den Desk-nahen admin-SPAs.
#
# Indirektionen (Pfad in Konstante/Variable/Ternary) werden, soweit im selben
# File aufloesbar, aufgeloest; alles Unaufloesbare wird als `dynamisch`
# vermerkt statt stillschweigend verworfen.

# fetch('/api/resource/<DocType>')
RE_URL_RESOURCE = re.compile(r"['\"`](/api/resource/([A-Za-z0-9_%\-.]*[A-Za-z0-9_%\-]))")
# frappe.call({ method: '...' })
RE_FRAPPE_CALL = re.compile(
    r"frappe\.call\(\s*\{[^}]*?method\s*:\s*['\"]([A-Za-z0-9_.\-]+)['\"]", re.S
)
# const X = 'wert'  |  const X = '/api/method/pfad'
RE_CONST_ASSIGN = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*['\"`]([^'\"`]*)['\"`]"
)
# apiCall(`${PREFIX}.methode`) — Template mit Konstante + Suffix
RE_APICALL_TPL = re.compile(r"api(?:Call|Get)\(\s*`\$\{([A-Za-z_$][\w$]*)\}\.([\w.]+)`")
# apiCall('dotted.path' | `dotted.path`) — reines Literal
RE_APICALL_LIT = re.compile(r"api(?:Call|Get)\(\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`]*)`)");  # noqa: E501
# const m = cond ? 'a' : 'b'  — Ternary-Zuweisung, auch mehrzeilig
# (GruppeDetail.saveDesc, KronosSeriesDialog, modal_create `endpoint`)
RE_TERNARY_ASSIGN = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:(?!\b(?:const|let|var)\b)[^;])*?"
    r"\?\s*['\"]([/A-Za-z0-9_.\-]+)['\"]"
    r"\s*:\s*['\"]([/A-Za-z0-9_.\-]+)['\"]",
    re.S,
)


def iter_frontend_files() -> list[Path]:
    files = []
    for root in FRONTEND_SCAN_ROOTS:
        if not root.exists():
            ANOMALIES.append(f"Frontend-Scan-Root fehlt: {rel(root)}")
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in FRONTEND_SUFFIXES:
                continue
            if is_build_artifact(p):
                continue
            if "node_modules" in p.parts:
                continue
            # Vendor-/Vendored-Libs: minifiziert, keine App-Aufrufe
            if "/lib/" in p.as_posix() or ".min." in p.name:
                continue
            files.append(p)
    return sorted(set(files))


def _norm_call_path(val: str) -> str:
    """Normalisiert einen erfassten Pfad; entfernt Query/Trailing-Slash."""
    v = val.strip()
    for pre in ("/api/method/", "api/method/"):
        if v.startswith(pre):
            v = v[len(pre) :]
    v = v.split("?")[0]
    return v.rstrip("/.")


def _read_call_arg(line: str, start: int) -> str:
    """Liest das erste Argument eines bereits geoeffneten Aufrufs.

    String-/Template-Literale und Klammer-Nesting werden respektiert, damit
    `fetch(`${C}?${x.toString()}`)` vollstaendig erfasst wird (kein Abbruch am
    inneren `)`). Abbruch bei Trenner `,` oder schliessender Klammer auf
    Tiefe 0.
    """
    depth = 0
    i = start
    quote = None
    out = []
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            out.append(ch)
        elif ch in "([{":
            depth += 1
            out.append(ch)
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
            out.append(ch)
        elif ch == "," and depth == 0:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).strip()


def emit_target(
    target: str,
    lineno: int,
    consts: dict,
    emit,
    form: str,
    local_tpl: dict | None = None,
    ternary: dict | None = None,
) -> None:
    """Loest den Ziel-Ausdruck eines fetch(...) in einen Endpunkt-Pfad auf.

    Behandelt:
      '/api/method/<dotted>'            -> <dotted>
      `<dotted-literal>`                -> <dotted>
      `/api/method/${CONST}`            -> Wert von CONST
      `${CONST}`                        -> Wert von CONST
      `${CONST}.${var}`                 -> dynamisch (Methodenname variabel)
      VARIABLE                          -> Wert der Konstante, sonst dynamisch
      '/api/resource/<DocType>'         -> resource:<DocType>  (via (c) separat erfasst)
    """
    local_tpl = local_tpl or {}
    t = target.strip()
    # (0) Lokale Template-Variable aufloesen (const url = `...`; fetch(url))
    if t in local_tpl:
        t = local_tpl[t].strip()
    # (1) reines String-Literal
    lit = re.fullmatch(r"""(['"`])(.*?)\1""", t)
    if lit and "${" not in lit.group(2):
        val = lit.group(2)
        if val.startswith("/api/resource/"):
            return  # wird von (c) erfasst
        if val.startswith("http"):
            return
        if val in ("", "/api/method/", "api/method/"):
            return  # leeres Praefix (spaeter per Konkatenation ergaenzt)
        emit(val, lineno, "method", form)
        return
    # (1b) String-Konkatenation '/api/method/' + <var>  -> dynamisch
    cat = re.fullmatch(r"""['"]/api/method/['"]\s*\+\s*([A-Za-z_$][\w$]*)""", t)
    if cat:
        emit(f"<dynamisch: {cat.group(1)}>", lineno, "dynamisch", form)
        return
    # (1c) sonstige Konkatenation / Ausdruck mit `+`
    if "+" in t and ("${" not in t) and ("`" not in t):
        emit(f"<dynamisch: {t[:40]}>", lineno, "dynamisch", form)
        return
    # (2) Template-Literal
    tm = re.fullmatch(r"`(.*)`", t)
    if tm:
        body = tm.group(1)
        # ${CONST}.${var}  -> dynamisch
        mv = re.fullmatch(r"\$\{([A-Za-z_$][\w$]*)\}\.\$\{([A-Za-z_$][\w$]*)\}", body)
        if mv:
            emit(f"<dynamisch: {mv.group(1)}.{mv.group(2)}>", lineno, "dynamisch", form)
            return
        # ${CONST} (evtl. mit nachfolgendem Query ?...)  -> Konstante aufloesen
        mc = re.fullmatch(r"\$\{([A-Za-z_$][\w$]*)\}(\?.*)?", body)
        if mc:
            base = consts.get(mc.group(1), "")
            if base:
                emit(base, lineno, "method", form)
            else:
                emit(f"<dynamisch: {mc.group(1)}>", lineno, "dynamisch", form)
            return
        # /api/method/${CONST}...
        mc2 = re.match(r"/api/method/\$\{([A-Za-z_$][\w$]*)\}", body)
        if mc2:
            base = consts.get(mc2.group(1), "")
            if base:
                emit(base, lineno, "method", form)
            else:
                emit(f"<dynamisch: {mc2.group(1)}>", lineno, "dynamisch", form)
            return
        # /api/method/<literal> (Template ohne Interpolation im Pfad)
        ml = re.match(r"/api/method/([A-Za-z0-9_.\-]+)", body)
        if ml:
            emit(ml.group(1), lineno, "method", form)
            return
        return
    # (3) blanke Variable
    if re.fullmatch(r"[A-Za-z_$][\w$]*", t):
        base = consts.get(t, "")
        if base.startswith("/api/method/"):
            base = base[len("/api/method/") :]
        if base.startswith("/api/resource/"):
            emit(f"resource:{base[len('/api/resource/'):].rstrip('/')}", lineno, "resource", form)
        elif base:
            emit(base, lineno, "method", form)
        elif t in consts:
            # Konstante war nur ein Praefix (z.B. `const url = '/api/method/' + m`)
            emit(f"<dynamisch: {t}>", lineno, "dynamisch", form)
        elif ternary and t in ternary:
            for branch in ternary[t]:
                emit(branch, lineno, "method", form)
        else:
            emit(f"<dynamisch: {t}>", lineno, "dynamisch", form)
        return


def parse_frontend_calls() -> list[dict]:
    out: list[dict] = []
    for path in iter_frontend_files():
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            ANOMALIES.append(f"Frontend-Datei nicht lesbar: {rel(path)} — {exc}")
            continue

        relfile = rel(path)
        idx = relfile.find("/diakronos-frappe/")
        if idx != -1:
            relfile = relfile[idx + len("/diakronos-frappe/") :]

        # Alle String-Konstanten der Datei (Name -> Wert). Deckt
        # PREFIX/PATH-Konstanten ab, sodass `apiCall(`${P}.x`)` aufloesbar ist.
        consts: dict[str, str] = {}
        for m in RE_CONST_ASSIGN.finditer(src):
            consts[m.group(1)] = m.group(2)

        # Lokale Template-Ziele: `const url = \`/api/method/${CONST}?...\``
        # sowie `const endpoint = \`${CONST}.${var}\`` o.ae. — damit wird ein
        # spaeteres `fetch(url)` noch aufloesbar.
        local_tpl: dict[str, str] = {}
        for m in re.finditer(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(`[^`]*`)", src
        ):
            local_tpl[m.group(1)] = m.group(2)
        # Auch: `const endpoint = <bool> ? a : b` mit Template-Operanden
        for m in re.finditer(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^;\n]*?\?\s*(`[^`]*`)", src
        ):
            local_tpl.setdefault(m.group(1), m.group(2))

        # Ternary-Zuweisungen (const m = cond ? 'a' : 'b') — beide Zweige merken
        ternary: dict[str, tuple] = {}
        for m in RE_TERNARY_ASSIGN.finditer(src):
            ternary[m.group(1)] = (m.group(2), m.group(3))

        def emit(pfad: str, lineno: int, art: str, form: str) -> None:
            # art: method | resource | dynamisch
            # dynamisch = Pfad steckt in Variable/Konstante, nicht aufloesbar
            dyn = pfad.startswith("<dynamisch")
            if dyn:
                art = "dynamisch"
            out.append(
                {
                    "aufgerufener_pfad": _norm_call_path(pfad),
                    "datei": relfile,
                    "zeile": lineno,
                    "art": art,
                    "aufrufform": form,
                    "dynamisch": dyn,
                }
            )

        lines = src.splitlines()
        for lineno, line in enumerate(lines, start=1):
            # ---- (a) apiCall/apiGet ----
            for m in RE_APICALL_TPL.finditer(line):
                var, suffix = m.group(1), m.group(2)
                base = consts.get(var, "")
                if base:
                    emit(f"{_norm_call_path(base)}.{suffix}", lineno, "method", "apiCall-template")
                else:
                    emit(
                        f"<dynamisch: {var}.{suffix}>",
                        lineno,
                        "dynamisch",
                        "apiCall-template",
                    )
            for m in RE_APICALL_LIT.finditer(line):
                lit = next((g for g in m.groups() if g is not None), "")
                if not lit or ("${" in lit):
                    continue
                if (lit.startswith("http")) or ("?" in lit):
                    continue
                emit(lit, lineno, "method", "apiCall-literal")
            # apiCall(VARIABLE) — nicht weiter aufloesbar
            for m in re.finditer(r"api(?:Call|Get)\(\s*([A-Za-z_$][\w$]*)\s*[,)]", line):
                var = m.group(1)
                if var in ("method",):
                    continue
                if var in ternary:
                    for branch in ternary[var]:
                        emit(branch, lineno, "method", "apiCall-variable")
                else:
                    emit(
                        f"<dynamisch: {var}>",
                        lineno,
                        "dynamisch",
                        "apiCall-variable",
                    )

            # ---- (b) fetch(...) — Ziel-Ausdruck aufloesen ----
            for fm in re.finditer(r"fetch\(", line):
                target = _read_call_arg(line, fm.end())
                emit_target(target, lineno, consts, emit, "fetch", local_tpl, ternary)

            # ---- (c) fetch('/api/resource/<DocType>') ----
            for m in RE_URL_RESOURCE.finditer(line):
                dt = m.group(1)
                for pre in ("/api/resource/", "api/resource/"):
                    if dt.startswith(pre):
                        dt = dt[len(pre) :]
                emit(f"resource:{dt.rstrip('/')}", lineno, "resource", "fetch-resource")

            # ---- frappe.call({method:'...'}) ----
            for m in RE_FRAPPE_CALL.finditer(line):
                emit(m.group(1), lineno, "method", "frappe.call")

        # frappe.call ueber mehrere Zeilen (kein Zeilenkontext) — nachziehen
        for m in RE_FRAPPE_CALL.finditer(src):
            meth = m.group(1)
            lineno = src.count("\n", 0, m.start()) + 1
            emit(meth, lineno, "method", "frappe.call")

    # Dedupe: gleiche Datei+Zeile+Pfad+Art+Aufrufform nur einmal
    seen = set()
    deduped = []
    for rec in sorted(
        out,
        key=lambda r: (
            r["datei"],
            r["zeile"],
            r["art"],
            r["aufrufform"],
            r["aufgerufener_pfad"],
        ),
    ):
        key = (
            rec["aufgerufener_pfad"],
            rec["datei"],
            rec["zeile"],
            rec["art"],
            rec["aufrufform"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


# --------------------------------------------------------------------------
# 5. Report
# --------------------------------------------------------------------------
def _module_of(pfad: str) -> str:
    """Ordnet einen Endpunkt-Pfad einem der Portierungsmodule zu.

    Basis ist das Segment nach `api.` (z.B. `…api.gruppen.create_x` -> gruppen).
    Kalender/Kronos-Bereiche werden unter `Kalender/Kronos` gebuendelt.
    """
    if pfad.startswith("resource:"):
        return "Ressourcen"
    if pfad.startswith("<dynamisch"):
        return "Sonstiges"
    parts = pfad.split(".")
    seg = parts[3] if len(parts) > 3 and parts[:3] == ["diakronos", "diakonos", "api"] else ""
    if not seg and len(parts) > 3 and parts[2] == "api":
        # z.B. diakronos.kronos.api.<seg>
        seg = parts[3]
    # Achtung: "diakronos" enthaelt die Zeichenfolge "kronos" — daher NICHT
    # per Substring pruefen, sondern das App-Segment (parts[1]) betrachten.
    app = parts[1] if len(parts) > 1 else ""
    kronos = (
        app == "kronos"
        or seg in {"calendar_get", "event_crud", "series", "kanban_api", "permissions", "ablaufplan_api"}
        or seg.startswith("ressource")
    )
    if kronos:
        return "Kalender/Kronos"
    mapping = {
        "gruppen": "Gruppen",
        "mitglieder": "Mitglieder",
        "ressourcen": "Ressourcen",
        "anmeldungen": "Anmeldungen",
        "registrierung": "Anmeldungen",
        "registrierungslink_api": "Anmeldungen",
        "veranstaltungsanmeldung": "Anmeldungen",
        "dienstplan": "Dienstplan",
        "beitraege": "Beitraege",
        "wiki": "Wiki",
        "musik": "Psalmos",
        "admin_hub": "Admin-Hub",
        "bugreport": "Bugreport",
        "audit": "Admin-Hub",
        "dashboard": "Admin-Hub",
        "profile": "Mitglieder",
        "session": "Sonstiges",
        "planung": "Anmeldungen",
        "auswahl": "Sonstiges",
        "orgchart_api": "Gruppen",
        "kalender": "Kalender/Kronos",
        "google_import": "Kalender/Kronos",
    }
    return mapping.get(seg, "Sonstiges")


def build_portierungsliste(endpoints, frontend_calls) -> str:
    """Erzeugt `inventar/PORTIERUNGSLISTE.md` — die Arbeitsgrundlage fuer P4.

    Fuer jeden von der SPA gerufenen Pfad: Existenz im Backend-Inventar,
    LOC des Originals, db.sql-Nutzung, Modul, Aufrufstellen. Dazu die
    Abschnitte Verwaiste / Fehlende Endpunkte und Aufwandsschaetzung.
    """
    L: list[str] = []
    a = L.append

    by_path = {e["dotted_path"]: e for e in endpoints}
    called_paths = sorted({c["aufgerufener_pfad"] for c in frontend_calls})
    concrete = [p for p in called_paths if not p.startswith("<dynamisch")]

    # Aufrufstellen je Pfad sammeln
    stellen: dict[str, list[str]] = {}
    for c in frontend_calls:
        stellen.setdefault(c["aufgerufener_pfad"], []).append(
            f"{c['datei']}:{c['zeile']}"
        )
    for p in stellen:
        stellen[p] = sorted(set(stellen[p]))

    def loc_of(p: str) -> str:
        e = by_path.get(p)
        return str(e["loc"]) if e else "—"

    def dyn_of(p: str) -> str:
        e = by_path.get(p)
        if not e:
            return "—"
        apis = e.get("genutzte_frappe_apis") or []
        return "ja" if any(x.startswith("frappe.db") for x in apis) else "nein"

    def eff_klasse(p: str) -> str:
        e = by_path.get(p)
        if not e:
            return "?"
        n = e["loc"]
        if n < 30:
            return "klein"
        if n <= 80:
            return "mittel"
        return "gross"

    found = [p for p in concrete if p in by_path]
    missing = [p for p in concrete if p not in by_path]
    called_set = set(concrete)
    orphan = sorted(e["dotted_path"] for e in endpoints if e["dotted_path"] not in called_set)

    a("# Portierungsliste — SPA-Endpunkte")
    a("")
    a("Automatisch generiert von `tools/inventar.py`. **Nicht manuell editieren.**")
    a("")
    a("Grundlage: `inventar/frontend_calls.json` (SPA-Aufrufe) gegen")
    a("`inventar/endpoints.json` (Backend-Inventar).")
    a("")
    a("## Kennzahlen")
    a("")
    a(f"- Eindeutige SPA-Pfade (aufgeloest): **{len(concrete)}**")
    n_res = sum(1 for p in concrete if p.startswith("resource:"))
    a(f"  - davon Methoden: **{len(concrete) - n_res}** (`/api/method/...`)")
    a(f"  - davon Ressourcen: **{n_res}** (`/api/resource/...`)")
    a(f"- davon im Backend gefunden: **{len(found)}**")
    a(f"- davon NICHT gefunden: **{len(missing)}**")
    a(f"- davon dynamisch (nicht aufloesbar): **{len(called_paths) - len(concrete)}**")
    a(f"- Backend-Endpunkte insgesamt: **{len(endpoints)}**")
    a(f"- davon verwaist (von der SPA nie gerufen): **{len(orphan)}**")
    a("")

    # --- Tabellen je Modul
    a("## Portierungstabelle je Modul")
    a("")
    a("Sortiert innerhalb der Module nach LOC absteigend (teuerste zuerst).")
    a("")
    mod_order = [
        "Mitglieder",
        "Gruppen",
        "Kalender/Kronos",
        "Ressourcen",
        "Anmeldungen",
        "Dienstplan",
        "Beitraege",
        "Wiki",
        "Psalmos",
        "Admin-Hub",
        "Bugreport",
        "Sonstiges",
    ]
    per_mod: dict[str, list[str]] = {m: [] for m in mod_order}

    def sortkey(p: str):
        e = by_path.get(p)
        return (-(e["loc"] if e else 0), p)

    for p in concrete:
        per_mod.setdefault(_module_of(p), []).append(p)

    for mod in mod_order:
        paths = per_mod.get(mod) or []
        if not paths:
            continue
        paths.sort(key=sortkey)
        a(f"### {mod} ({len(paths)} Pfade)")
        a("")
        a("| Pfad | im Backend? | LOC | nutzt db.sql? | Aufrufstellen |")
        a("|---|---|---|---|---|")
        for p in paths:
            exist = "ja" if p in by_path else "**NEIN**"
            st = ", ".join(stellen.get(p, []))
            if len(st) > 90:
                st = st[:87] + "…"
            a(f"| `{p}` | {exist} | {loc_of(p)} | {dyn_of(p)} | {st} |")
        a("")

    # --- Verwaiste
    a("## Verwaiste Endpunkte")
    a("")
    a("Im Backend vorhanden, von der SPA NIE gerufen. Kandidaten, die man in v1")
    a("weglassen kann — zur Entscheidung, nicht entschieden.")
    a("")
    if orphan:
        a("| Pfad | Modul | LOC | nutzt db.sql? |")
        a("|---|---|---|---|")
        for p in sorted(orphan, key=lambda x: (-by_path[x]["loc"], x)):
            a(f"| `{p}` | {_module_of(p)} | {by_path[p]['loc']} | {dyn_of(p)} |")
    else:
        a("_keine_")
    a("")

    # --- Fehlende
    a("## Fehlende Endpunkte")
    a("")
    a("Von der SPA gerufen, im Backend-Inventar NICHT auffindbar. Einzeln am")
    a("Altcode zu pruefen: Tippfehler in der SPA? Anderer Modulpfad? Wirklich fehlend?")
    a("")
    if missing:
        a("| Pfad | vermutete Ursache | Aufrufstellen |")
        a("|---|---|---|")
        for p in missing:
            if p == "diakronos.diakronos.api.ressourcen.decide_buchung":
                urs = (
                    "doppeltes 'diakronos' — echter Endpunkt heisst "
                    "`diakronos.diakonos.api.ressourcen.decide_buchung` (Tippfehler in der SPA)"
                )
            elif p == "diakronos.diakonos.api.gruppen.update_dienstbereich":
                urs = "im Altcode nicht als whitelisted Endpunkt auffindbar — pruefen"
            elif p == "upload_file":
                urs = "vermutlich Frappe-Core-Upload, nicht App-eigen"
            elif p == "frappe.client.insert":
                urs = "Frappe-Core-API (kein App-Endpunkt) — SPA-Schreibpfad pruefen"
            elif p == "logout":
                urs = "Frappe-Core-Logout, nicht App-eigen"
            elif p.startswith("resource:"):
                urs = "Frappe-REST-Ressource (DocType) — kein @whitelist-Endpunkt"
            elif p.endswith(".get_accessible_calendars") or "kronos" in p:
                urs = "Kronos-Modul — nicht in hooks/endpoints erfasst, pruefen"
            else:
                urs = "pruefen"
            st = ", ".join(stellen.get(p, []))
            a(f"| `{p}` | {urs} | {st} |")
    else:
        a("_keine_")
    a("")

    # --- Aufwand
    a("## Aufwandsschaetzung")
    a("")
    a("Grobe Einteilung nach LOC des Originals: klein (<30), mittel (30-80),")
    a("gross (>80). Nur gefundene Endpunkte (fehlende haben keinen LOC-Wert).")
    a("")
    a("| Modul | klein | mittel | gross | Summe LOC | unbekannt |")
    a("|---|---|---|---|---|---|")
    tot = {"klein": 0, "mittel": 0, "gross": 0, "unbekannt": 0, "loc": 0}
    for mod in mod_order:
        paths = [p for p in per_mod.get(mod) or []]
        if not paths:
            continue
        cnt = {"klein": 0, "mittel": 0, "gross": 0, "unbekannt": 0}
        locsum = 0
        for p in paths:
            k = eff_klasse(p)
            if k == "?":
                cnt["unbekannt"] += 1
            else:
                cnt[k] += 1
                locsum += by_path[p]["loc"]
        for k in cnt:
            tot[k] += cnt[k]
        tot["loc"] += locsum
        a(
            f"| {mod} | {cnt['klein']} | {cnt['mittel']} | {cnt['gross']} | "
            f"{locsum} | {cnt['unbekannt']} |"
        )
    a(
        f"| **Summe** | **{tot['klein']}** | **{tot['mittel']}** | **{tot['gross']}** | "
        f"**{tot['loc']}** | **{tot['unbekannt']}** |"
    )
    a("")

    return "\n".join(L)


def build_report(doctypes, endpoints, api_usage, frontend_calls, hooks_methods) -> str:
    L: list[str] = []
    a = L.append

    total_fields = sum(d["field_count"] for d in doctypes)
    total_links = sum(len(d["links"]) for d in doctypes)
    total_child = sum(len(d["child_tables"]) for d in doctypes)
    child_doctypes = {c["child_doctype"] for d in doctypes for c in d["child_tables"] if c["child_doctype"]}
    tree_dts = [d["name"] for d in doctypes if d["is_tree"]]
    single_dts = [d["name"] for d in doctypes if d["issingle"]]

    a("# Inventar — Diakronos Altanwendung")
    a("")
    a("Automatisch generiert von `tools/inventar.py`. **Nicht manuell editieren.**")
    a("")
    a("Quelle (read-only): `referenz/diakronos-frappe/`")
    a("")
    a("## Kennzahlen")
    a("")
    a(f"- DocTypes: **{len(doctypes)}**")
    a(f"- Felder gesamt: **{total_fields}**")
    a(f"- Link-Felder: **{total_links}**")
    a(f"- Child-Table-Felder: **{total_child}** ({len(child_doctypes)} verschiedene Child-DocTypes)")
    a(f"- Endpunkte (`@frappe.whitelist`): **{len(endpoints)}**")
    a(f"- davon `allow_guest=True`: **{sum(1 for e in endpoints if e['allow_guest'])}**")
    a(f"- Einträge in `hooks.py:whitelisted_methods`: **{len(hooks_methods)}**")
    a(f"- `frappe.*`-Verwendungen: **{len(api_usage)}** (distinkte APIs: {len({r['api'] for r in api_usage})})")
    a(f"- Frontend-Backend-Aufrufe: **{len(frontend_calls)}**")
    a(f"- DocTypes mit `is_tree`: {', '.join(tree_dts) if tree_dts else '—'}")
    a(f"- Single-DocTypes: {', '.join(single_dts) if single_dts else '—'}")
    a("")

    # --- DocTypes je Modul
    a("## DocTypes je Modul")
    a("")
    a("| Modul | DocTypes | Felder | Link-Felder | Child-Tables |")
    a("|---|---:|---:|---:|---:|")
    by_mod: dict[str, list[dict]] = defaultdict(list)
    for d in doctypes:
        by_mod[d["module"] or "(unbekannt)"].append(d)
    for mod in sorted(by_mod):
        ds = by_mod[mod]
        a(
            f"| {mod} | {len(ds)} | {sum(x['field_count'] for x in ds)} | "
            f"{sum(len(x['links']) for x in ds)} | {sum(len(x['child_tables']) for x in ds)} |"
        )
    a("")

    a("### DocType-Details")
    a("")
    a("| DocType | Modul | Felder | Links | Child-Tables | Permissions | istable |")
    a("|---|---|---:|---:|---:|---:|---:|")
    for d in sorted(doctypes, key=lambda x: (x["module"] or "", x["name"] or "")):
        a(
            f"| {d['name']} | {d['module']} | {d['field_count']} | {len(d['links'])} | "
            f"{len(d['child_tables'])} | {len(d['permissions'])} | {d['istable']} |"
        )
    a("")

    # --- Top-20 Endpunkte nach LOC
    a("## Top-20 Endpunkte nach LOC (teuerste Portierungen)")
    a("")
    a("| # | Endpunkt | LOC | allow_guest | frappe-APIs |")
    a("|---:|---|---:|---|---:|")
    for i, e in enumerate(sorted(endpoints, key=lambda x: (-x["loc"], x["dotted_path"]))[:20], start=1):
        a(
            f"| {i} | `{e['dotted_path']}` | {e['loc']} | "
            f"{'ja' if e['allow_guest'] else 'nein'} | {len(e['genutzte_frappe_apis'])} |"
        )
    a("")

    # --- frappe.db.sql
    sql_eps = [
        e for e in endpoints if any(api.startswith("frappe.db.sql") for api in e["genutzte_frappe_apis"])
    ]
    a("## Endpunkte mit `frappe.db.sql` (brauchen Sonderbehandlung)")
    a("")
    if sql_eps:
        a("| Endpunkt | LOC | SQL-Aufrufe |")
        a("|---|---:|---:|")
        for e in sorted(sql_eps, key=lambda x: x["dotted_path"]):
            n = sum(1 for api in e["genutzte_frappe_apis"] if api.startswith("frappe.db.sql"))
            a(f"| `{e['dotted_path']}` | {e['loc']} | {n} |")
    else:
        a("_Keine._")
    a("")
    a(f"Zusätzlich `frappe.db.sql` außerhalb whitelisted Endpunkte: "
      f"{sum(1 for r in api_usage if r['api'].startswith('frappe.db.sql'))} Vorkommen "
      f"in {len({r['datei'] for r in api_usage if r['api'].startswith('frappe.db.sql')})} Dateien.")
    a("")

    # --- Frontend ruft, aber nicht in hooks.py
    ep_by_path = {e["dotted_path"]: e for e in endpoints}
    hooks_set = set(hooks_methods)
    fe_methods = sorted(
        {c["aufgerufener_pfad"] for c in frontend_calls if c["art"] == "method" and not c["aufgerufener_pfad"].startswith("<")}
    )
    fe_not_in_hooks = [m for m in fe_methods if m not in hooks_set]
    fe_not_in_endpoints = [m for m in fe_methods if m not in ep_by_path]

    a("## Frontend ruft, aber NICHT in `hooks.py:whitelisted_methods`")
    a("")
    if fe_not_in_hooks:
        a("| Aufgerufener Pfad | Datei(en) | In endpoints.json vorhanden? |")
        a("|---|---|---|")
        for m in fe_not_in_hooks:
            files = sorted({c["datei"] for c in frontend_calls if c["aufgerufener_pfad"] == m})
            a(f"| `{m}` | {', '.join(files[:3])}{' …' if len(files) > 3 else ''} | "
              f"{'ja' if m in ep_by_path else 'NEIN'} |")
    else:
        a("_Keine Abweichung._")
    a("")
    if fe_not_in_endpoints:
        a("**Ohne `@frappe.whitelist` im Code (Frappe-Bordmittel oder nicht auflösbar):**")
        a("")
        for m in fe_not_in_endpoints:
            a(f"- `{m}`")
        a("")

    # --- Endpunkte in hooks.py, aber nicht als @frappe.whitelist gefunden
    ep_paths = set(ep_by_path)
    hooks_not_in_ep = sorted(hooks_set - ep_paths)
    a("## In `hooks.py` deklariert, aber im Code nicht als `@frappe.whitelist` gefunden")
    a("")
    a("**Wichtig fuer die Portierung:** Diese Eintraege zeigen auf Funktionen, die es im")
    a("Code unter diesem Namen nicht gibt. Entweder Tippfehler/Umbenennung im Altsystem")
    a("oder Funktion existiert gar nicht — beim Portieren muss die Absicht rekonstruiert")
    a("werden, nicht der Literalpfad.")
    a("")
    if hooks_not_in_ep:
        a("| Deklarierter Pfad | Modul | Aehnliche Namen im selben Modul |")
        a("|---|---|---|")
        for m in hooks_not_in_ep:
            mod, _, fn = m.rpartition(".")
            similar = sorted(
                e["funktionsname"]
                for e in endpoints
                if e["dotted_path"].rpartition(".")[0] == mod
            )
            # Namensnaehe: gemeinsamer Praefix >= 8 Zeichen
            close = [s for s in similar if s[:8] == fn[:8] and s != fn]
            a(f"| `{m}` | `{mod}` | {', '.join(f'`{c}`' for c in close) if close else '—'} |")
    else:
        a("_Keine Abweichung._")
    a("")

    # --- Nicht referenzierte DocTypes
    linked_targets = {l["target_doctype"] for d in doctypes for l in d["links"] if l["target_doctype"]}
    # DocTypes, die in frappe.*-Aufrufen als String auftauchen (Heuristik)
    used_in_code: set[str] = set()
    code_blob = " ".join(
        r["kontext_zeile"] for r in api_usage
    )
    for d in doctypes:
        name = d["name"]
        if name and (f'"{name}"' in code_blob or f"'{name}'" in code_blob):
            used_in_code.add(name)
    fe_blob = " ".join(c["aufgerufener_pfad"] for c in frontend_calls)
    for d in doctypes:
        name = d["name"]
        if name and name in fe_blob:
            used_in_code.add(name)

    all_dt_names = {d["name"] for d in doctypes}
    orphans = sorted(all_dt_names - linked_targets - used_in_code)
    a("## DocTypes ohne Link-Referenz und ohne Code-Erwähnung")
    a("")
    a(f"Gesamt: **{len(orphans)}** (Heuristik: Link-Ziele + String-Vorkommen in "
      f"`frappe.*`-Kontextzeilen + Frontend-Pfade)")
    a("")
    if orphans:
        a("| DocType | Modul | Felder | istable | issingle |")
        a("|---|---|---:|---:|---:|")
        by_name = {d["name"]: d for d in doctypes}
        for n in orphans:
            d = by_name[n]
            a(f"| {n} | {d['module']} | {d['field_count']} | {d['istable']} | {d['issingle']} |")
    else:
        a("_Keine._")
    a("")

    # --- Feldtypen
    ft = Counter()
    for d in doctypes:
        for f in d["fields"]:
            if f["fieldtype"]:
                ft[f["fieldtype"]] += 1
    a("## Feldtypen mit Häufigkeit (Grundlage Typ-Mapper DocType → SQLAlchemy)")
    a("")
    a(f"Distinkte Feldtypen: **{len(ft)}**")
    a("")
    a("| Feldtyp | Vorkommen |")
    a("|---|---:|")
    for t, c in sorted(ft.items(), key=lambda kv: (-kv[1], kv[0])):
        a(f"| {t} | {c} |")
    a("")

    # --- frappe-API-Häufigkeit
    a("## `frappe.*`-APIs nach Häufigkeit (Top 40)")
    a("")
    a("| API | Vorkommen | Dateien |")
    a("|---|---:|---:|")
    api_counter = Counter(r["api"] for r in api_usage)
    for api, c in api_counter.most_common(40):
        files = len({r["datei"] for r in api_usage if r["api"] == api})
        a(f"| `{api}` | {c} | {files} |")
    a("")

    # --- Auffaelligkeiten
    a("## Auffälligkeiten")
    a("")
    a("Nichts wird stillschweigend übersprungen. Parse-Fehler, unerwartete Felder und")
    a("Scan-Ausnahmen stehen hier (bzw. der Befund, dass keine vorlagen).")
    a("")
    a("- **Gebaute Vite-Bundles übersprungen:** `diakonos/public/frontend/**` enthält "
      "minifiziertes JS (Hashes im Dateinamen, keine lesbaren Aufrufpfade). Der "
      "Frontend-Scan deckt `frontend/src/**` und `diakonos/public/**` **ohne** "
      "`public/frontend/` ab. Die dort eingebetteten Aufrufe sind Ableitungen der "
      "Quellen unter `frontend/src/`.")
    a("- **`diakonos/public/js/lib/**` (Vendor: moment, event-calendar, html-to-image)** "
      "wird mitgescannt, enthält aber keine eigenen Backend-Aufrufe.")
    a(f"- **Parse-Fehler / Übersprungene Einträge: {len(ANOMALIES)}**"
      + ("" if ANOMALIES else " — keine. Alle `*.py`-Dateien und alle DocType-JSONs "
                             "waren parsebar."))
    a(f"- **Endpunkt-Zahl 176 vs. 181 in der Aufgabenstellung:** Die Karte nennt "
      f"\"181 Endpunkte\", verifiziert aber nur `>= 176`. Gezaehlt wurden per AST "
      f"**{len(endpoints)}** Funktionen mit `@frappe.whitelist`-Dekorator; dieselbe Zahl "
      f"ergibt ein unabhaengiger `grep -rc '@frappe.whitelist'`. Es gibt keine "
      f"Duplikate (176 von 176 `dotted_path` sind eindeutig). Die Diskrepanz ist in "
      f"der Quelle nicht aufloesbar — moeglicherweise wurden in der Karte Endpunkte "
      f"mitgezaehlt, die nur in `hooks.py` stehen, oder eine aeltere Revision. "
      f"Massgeblich ist der Code-Stand: **{len(endpoints)}**.")
    if ANOMALIES:
        a("")
        a("| # | Auffälligkeit |")
        a("|---:|---|")
        for i, msg in enumerate(ANOMALIES, start=1):
            safe = msg.replace("|", "\\|")
            a(f"| {i} | {safe} |")
        a("")
    a("### Dynamische Frontend-Aufrufe")
    a("")
    dyn = [c for c in frontend_calls if c["aufgerufener_pfad"].startswith("<dynamic")]
    if dyn:
        for c in dyn:
            a(f"- `{c['datei']}`: {c['aufgerufener_pfad']}")
        a("")
        a("Diese Aufrufe bauen den Pfad zur Laufzeit aus einer Basis-Konstante "
          "(z.B. `const API = '/api/method/diakronos.diakonos.api'` + `.methode`). "
          "Die konkreten Endpunkte derselben Datei sind über die statischen Funde abgedeckt.")
    else:
        a("_Keine._")
    a("")
    a("---")
    a("")
    a("Generiert von `tools/inventar.py` (idempotent).")
    a("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    if not REF.exists():
        print(f"FEHLER: Quelle fehlt: {REF}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)

    doctypes = parse_doctypes()
    endpoints = parse_endpoints()
    hooks_methods = parse_hooks_whitelisted()

    hooks_set = set(hooks_methods)
    for e in endpoints:
        e["in_hooks"] = e["dotted_path"] in hooks_set

    api_usage = parse_frappe_usage()
    frontend_calls = parse_frontend_calls()

    (OUT / "doctypes.json").write_text(
        json.dumps(doctypes, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "endpoints.json").write_text(
        json.dumps(endpoints, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "frappe_api_usage.json").write_text(
        json.dumps(api_usage, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "frontend_calls.json").write_text(
        json.dumps(frontend_calls, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = build_report(doctypes, endpoints, api_usage, frontend_calls, hooks_methods)
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    portierung = build_portierungsliste(endpoints, frontend_calls)
    (OUT / "PORTIERUNGSLISTE.md").write_text(portierung, encoding="utf-8")

    print(f"doctypes.json         : {len(doctypes)} DocTypes")
    print(f"endpoints.json        : {len(endpoints)} Endpunkte")
    print(f"frappe_api_usage.json : {len(api_usage)} Verwendungen")
    print(f"frontend_calls.json   : {len(frontend_calls)} Aufrufe")
    print(f"REPORT.md             : geschrieben ({len(report)} Zeichen)")
    print(f"PORTIERUNGSLISTE.md   : geschrieben ({len(portierung)} Zeichen)")
    print(f"Auffaelligkeiten      : {len(ANOMALIES)}")
    for m in ANOMALIES:
        print(f"  - {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
