"""Portierung von `diakonos/api/bugreport.py` (P4j) — Dev-Bugmelder, 4 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/bugreport.py`

Die SPA ruft ausschliesslich den ORIGINAL-Pfad
`diakronos.diakonos.api.bugreport.melden` auf. Kontrollpfad zeichenweise aus
Aufrufliste des Frappe-Frontends entnommen (nicht aus diesem Code abgeleitet):

    "diakronos.diakonos.api.bugreport.melden"

Achtung auf das „r": `diakronos`, NICHT `diakonos`. Dafuer traegt dieses Modul
die Konstante `FRAPPE_MODULE`.

Schema-Realitaet (geprueft, NICHT angenommen):
`Spaltenabzug der Betriebs-DB`, Zeile `tabBug Report`. Alle im Original
benutzten Felder existieren dort:

    name, creation, modified, modified_by, owner, docstatus, idx,
    naming_series, titel, status, gemeldet_am, benutzer, mitglied,
    oberflaeche, beschreibung, route, url, viewport, user_agent, build,
    screenshot, konsole_log, netzwerk_log, notiz,
    element_selektor, element_text, element_html, element_komponente

`tabBug Report` hat KEINE Kindtabellen — das Modul braucht keine
`_child_*`-Helfer.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user                -> session.user
    frappe.db.get_single_value(...)    -> get_value(..., as_dict=True)
    frappe.get_roles()                 -> permissions.get_roles()
    frappe.db.get_value(...)           -> query.get_value(...)
    frappe.get_all(...)                -> query.get_all(...)   (Zeilendicts)
    frappe.get_doc("Bug Report", n)    -> query.get_doc(...)   -> Document
    frappe.get_doc({...}).insert()     -> _create(...)
    doc.save(ignore_permissions=True)  -> _update_doc(...)
    frappe.db.commit()                 -> no-op (die Ports committen je Session)
    frappe.throw(msg, exc)             -> exceptions.throw(...)
    frappe.log_error(...)              -> _log_error(...) (stderr)
    frappe.utils.file_manager.save_file -> upload_file(...) (P2c, EINE Ablage)
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.bugreport"

import base64
import json
import sys
from typing import Any

from diakronos_app.api.frappe_core import upload_file
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    FrappeCompatError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.session import session
from diakronos_app.frappe_compat.api_helpers import _create, _update_doc

MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024   # 4 MB
MAX_LOG_ENTRIES = 50
MAX_LOGS_CHARS = 256 * 1024              # 256 KB, beide Logs zusammen

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]

# Kontextfelder, die gemeldet werden und 1:1 aus dem Payload übernommen werden
_KONTEXT_FELDER = [
    "oberflaeche", "route", "url", "viewport", "user_agent", "build",
    "element_selektor", "element_text", "element_html", "element_komponente",
]

# Serverseitige Haerte-Kuerzung der Element-Referenz (nie dem Frontend trauen).
# Selektor 500 / Text 300 / HTML 2000 Zeichen (wie im Frontend beim Erfassen).
_ELEMENT_CAPS = {
    "element_selektor": 500,
    "element_text": 300,
    "element_html": 2000,
    "element_komponente": 200,   # Komponentenname ist kurz — defensive Kappe
}
_KLIP_TAIL = "\u2026"

DOCTYPES_SETTINGS = "Diakronos Einstellungen"

# DocType dieses Moduls (einzige Erzeugungs-Quelle: `melden`).
_BUGREPORT = "Bug Report"


def _kappe(feldwert, cap):
    """Deckel einen String serverseitig hart auf cap Zeichen (+ Marker)."""
    if cap is not None and len(feldwert) > cap:
        if cap > 1:
            return feldwert[:cap - 1] + _KLIP_TAIL
        return _KLIP_TAIL
    return feldwert


def _log_error(message: str, title: str | None = None) -> None:
    """`frappe.log_error` -> stderr (kein Error-Log-DocType im Backend).

    Der Altcode loggt einen gescheiterten Screenshot und macht weiter; die
    Funktion darf den Ablauf nie veraendern.
    """
    label = f"[{title}] " if title else ""
    print(f"bugreport error: {label}{message}", file=sys.stderr)


# ---------------------------------------------------------------------- #
# Schranke                                                               #
# ---------------------------------------------------------------------- #

def _dev_modus():
    """Liest den Entwicklungs-Schalter (Single DocType).

    Original: `frappe.db.get_single_value("Diakronos Einstellungen", "dev_modus")`.
    Die Compat-Schicht fuehrt keine `get_single_value` — ein Single DocType ist
    eine normale Zeile mit `name == <DocType>`; `get_value(..., as_dict=True)`
    liefert dieselbe Information (siehe `api/kronos/permissions.py` und
    `api/kronos/impersonation.py` fuer dasselbe Muster).
    """
    try:
        row = get_value(
            DOCTYPES_SETTINGS, DOCTYPES_SETTINGS, ["dev_modus"], as_dict=True
        )
        return int((row or {}).get("dev_modus") or 0)
    except Exception:  # noqa: BLE001 — Feld/DocType fehlt -> konservativ aus
        # Feld noch nicht migriert / DocType fehlt → konservativ aus.
        return 0


def _require_dev_modus():
    if not _dev_modus():
        throw(
            "Der Bugmelder ist auf dieser Site deaktiviert.",
            FrappePermissionError,
        )


def _require_admin():
    """Original: `_require_admin()` — Guest abweisen, Administrator durchlassen.

    Die Rollenliste ist exakt die des Originals (`frappe.get_roles()`); die
    Compat-Umsetzung ist `permissions.get_roles()` (`tabHas Role`).
    """
    user = session.user
    if user == "Guest":
        throw("Zugriff verweigert.", FrappePermissionError)
    if user == "Administrator":
        return
    roles = set(get_roles())
    if not (ADMIN_ROLES[0] in roles or ADMIN_ROLES[1] in roles):
        throw(
            "Nur für Mitgliederadministratoren.", FrappePermissionError
        )


def _current_user_mitglied_name():
    """Auflösen des angemeldeten Users auf einen Mitglied-Namen (falls vorhanden)."""
    user = session.user
    if user in ("Guest", "Administrator"):
        return None
    name = get_value("Mitglied", {"user": user}, "name")
    if not name:
        email = get_value("User", user, "email") or user
        name = get_value("Mitglied", {"email": email}, "name")
    return name


# ---------------------------------------------------------------------- #
# Payload-Normalisierung                                                 #
# ---------------------------------------------------------------------- #

def _as_dict(payload):
    """payload aus JSON-String oder dict in ein dict normalisieren."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return {}
        try:
            loaded = json.loads(payload)
            return loaded if isinstance(loaded, dict) else {}
        except (ValueError, TypeError):
            throw("Ungültiger Payload (kein JSON-Objekt).")
    throw("Ungültiger Payload-Typ.")


def _deckel_logs(konsole, netzwerk):
    """(konsole, netzwerk) → gedeckelte Strings.

    Je Log bleiben höchstens MAX_LOG_ENTRIES Einträge; zusammen dürfen beide
    nicht mehr als MAX_LOGS_CHARS Zeichen belegen. Über den gemeinsamen
    Rahmen zuerst den netzwerk-, dann den konsole-Anteil kürzen.
    """
    konsole_list, netzwerk_list = [], []
    for src, target in ((konsole, konsole_list), (netzwerk, netzwerk_list)):
        if src is None:
            continue
        if isinstance(src, str):
            src_s = src.strip()
            if src_s:
                try:
                    data = json.loads(src_s)
                except (ValueError, TypeError):
                    data = None
            else:
                data = None
        else:
            data = src
        if isinstance(data, list):
            for item in data:
                if item is not None:
                    if not isinstance(item, str):
                        item = json.dumps(item, ensure_ascii=False)
                    target.append(item)
        # nur letzte MAX_LOG_ENTRIES
        target[:] = target[-MAX_LOG_ENTRIES:]

    def _stringify(items):
        return json.dumps(items, ensure_ascii=False) if items else ""

    k = _stringify(konsole_list)
    n = _stringify(netzwerk_list)

    budget = MAX_LOGS_CHARS
    # gemeinsames Budget durchtrimmen: zuerst netzwerk, dann konsole
    if len(k) + len(n) > budget:
        n = _trim_front_json(n, budget // 2)
    if len(k) + len(n) > budget:
        k = _trim_front_json(k, budget - len(n))
    return k, n


def _trim_front_json(log_json, max_chars):
    """JSON-Liste von hinten kürzen, sodass String ≤ max_chars bleibt.

    Da wir ohnehin schon nur die letzten Einträge halten, wird hier der
    serialisierte String hart abgeschnitten (falls selbst die 50 Einträge
    zu groß sind) und durch einen Marker ergänzt.
    """
    if not log_json or len(log_json) <= max_chars:
        return log_json
    marker = ", ...(geschnitten)]"
    head_len = max_chars - len(marker)
    if head_len <= 0:
        return marker
    return log_json[:head_len] + marker


# ---------------------------------------------------------------------- #
# Screenshot                                                             #
# ---------------------------------------------------------------------- #

class _ScreenshotTooBig(Exception):
    pass


class _ScreenshotInvalid(Exception):
    pass


def _decode_screenshot(data_url, max_bytes):
    """Prüft + dekodiert eine Screenshot-Data-URL. Wirft bei zu groß / ungültig."""
    if not data_url or not isinstance(data_url, str):
        raise _ScreenshotInvalid("kein Screenshot")
    marker = ";base64,"
    idx = data_url.find(marker)
    if idx < 0:
        raise _ScreenshotInvalid("keine base64-Data-URL")
    b64 = data_url[idx + len(marker):]

    missing = len(b64) % 4
    if missing:
        b64 += "=" * (4 - missing)
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:  # noqa: BLE001 — jeder Decode-Fehler ist "ungueltig"
        raise _ScreenshotInvalid("base64-Decode fehlgeschlagen") from None

    if len(raw) > max_bytes:
        raise _ScreenshotTooBig(len(raw))
    return raw


def _speichere_screenshot(raw_bytes, mime, bug_name):
    """Privater File-Doc am Bug Report → file_url.

    Original: `frappe.utils.file_manager.save_file(fname=..., content=...,
    dt="Bug Report", dn=bug_name, df="screenshot", is_private=1, decode=False)`.
    Das Standalone-Backend hat EINE Ablage aus P2c (`api.frappe_core.upload_file`,
    Groessenlimit, Content-Type-Allowlist, Path-Traversal-Abwehr). Es wird KEINE
    zweite Ablage gebaut — nur der Aufruf umgeschrieben.

    Unterschied zum Original: `upload_file` prueft den Content-Type gegen eine
    Allowlist. Ein Screenshot ist immer `image/png` oder `image/jpeg` (die
    `mime` kommt aus der Data-URL, `_mime_of`) — beide sind erlaubt. Der
    Dateiname enthaelt die Zielendung, damit `mimetypes` denselben Typ errät,
    falls der Content-Type nicht explizit mitgegeben wird.
    """
    ext = "png"
    if mime == "image/jpeg":
        ext = "jpg"
    # The generic document-write ACL intentionally does not support Bug Report.
    # Only this server-side flow may attach the freshly created reporter's file;
    # do not weaken upload_file's client-controlled attachment permission check.
    if session.user == "Guest" or get_value(_BUGREPORT, bug_name, "benutzer") != session.user:
        throw("Nur eigene Bugmeldungen sind erlaubt.", FrappePermissionError)
    result = upload_file(
        file=bytes(raw_bytes),
        filename=f"screenshot-{bug_name}.{ext}",
        is_private=1,
    )
    _update_doc("File", result["name"], {
        "attached_to_doctype": _BUGREPORT,
        "attached_to_name": bug_name,
        "attached_to_field": "screenshot",
    })
    return result.get("file_url")


def _mime_of(data_url):
    if data_url and data_url.startswith("data:"):
        return data_url[5:data_url.find(";")].strip().lower()
    return ""


# ---------------------------------------------------------------------- #
# Whitelist                                                              #
# ---------------------------------------------------------------------- #

@whitelist(allow_guest=False)
def melden(payload=None, screenshot=None):
    """Legt einen Bug Report an (einzige Erzeugungs-Quelle)."""
    _require_dev_modus()  # Schranke zuerst — auf Produktion faktisch inexistent.

    data = _as_dict(payload)
    user = session.user

    # Benutzer/Mitglied NIE aus dem Payload übernehmen (Spoofing-Schutz).
    benutzer = user
    mitglied = _current_user_mitglied_name()

    params = {"benutzer": benutzer, "mitglied": mitglied, "status": "Neu"}
    for f in _KONTEXT_FELDER:
        v = data.get(f)
        if v and isinstance(v, str):
            params[f] = _kappe(v, _ELEMENT_CAPS.get(f))

    beschreibung = ""
    if isinstance(data.get("beschreibung"), str):
        beschreibung = data["beschreibung"].strip()

    titel = ""
    if isinstance(data.get("titel"), str):
        titel = data["titel"].strip()

    konsole, netzwerk = _deckel_logs(data.get("konsole_log"), data.get("netzwerk_log"))
    params["konsole_log"] = konsole
    params["netzwerk_log"] = netzwerk
    params["beschreibung"] = beschreibung
    params["titel"] = titel

    name = _create(_BUGREPORT, params)

    screenshot_saved = False
    mime = _mime_of(screenshot)
    if screenshot:
        try:
            raw = _decode_screenshot(screenshot, MAX_SCREENSHOT_BYTES)
        except _ScreenshotTooBig as exc:
            # Verlorener Screenshot schlägt den Bericht nicht nieder.
            mb = round(exc.args[0] / (1024 * 1024), 1)
            beschreibung = (beschreibung + "\n\n[WARNUNG: Screenshot "
                            f"> {MAX_SCREENSHOT_BYTES // (1024*1024)} MB ({mb} MB) "
                            "verworfen.]").strip()
        except _ScreenshotInvalid:
            beschreibung = (beschreibung +
                            "\n\n[WARNUNG: Screenshot-Datei war ungültig "
                            "und wurde verworfen.]").strip()
        else:
            try:
                _update_doc(_BUGREPORT, name, {
                    "screenshot": _speichere_screenshot(raw, mime, name),
                    "beschreibung": beschreibung if beschreibung else None,
                })
                screenshot_saved = True
            except Exception:  # noqa: BLE001 — Screenshot darf den Bericht nicht kippen
                _log_error("Screenshot-Speicherung scheiterte.", "bugreport.melden.screenshot")
                beschreibung = (beschreibung +
                                "\n\n[WARNUNG: Screenshot-Speicherung "
                                "scheiterte.]").strip()

    # Beschreibung nachtragen (Original: `doc.save(ignore_permissions=True)`).
    _update_doc(_BUGREPORT, name, {"beschreibung": beschreibung})

    # `titel` (falls ohne Titel gemeldet) ist durch den DocType-Controller
    # auf der ersten Beschreibungszeile gesetzt.
    return {"name": name, "screenshot": screenshot_saved}


@whitelist(allow_guest=False)
def liste(status=None, limit=50):
    """Kompakte Liste für die Desk-Ansicht und das Auswerteskript. Nur Admins.

    Ohne die großen Felder (konsole_log, netzwerk_log, screenshot) — die liefert
    ``detail``.
    """
    _require_admin()
    try:
        limit = int(limit or 50)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    filters = {}
    if status:
        filters["status"] = status

    rows = get_all(
        _BUGREPORT,
        filters=filters,
        fields=[
            "name", "titel", "status", "gemeldet_am", "benutzer",
            "mitglied", "oberflaeche", "route",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )
    return rows


@whitelist(allow_guest=False)
def detail(name):
    """Vollständiger Bericht (inkl. konsole_log, netzwerk_log, screenshot)."""
    _require_admin()
    if not name:
        throw("Name fehlt.")
    doc = get_doc(_BUGREPORT, name)
    return {
        "name": doc.name,
        "titel": doc.titel,
        "status": doc.status,
        "gemeldet_am": str(doc.gemeldet_am) if doc.gemeldet_am else None,
        "benutzer": doc.benutzer,
        "mitglied": doc.mitglied,
        "oberflaeche": doc.oberflaeche,
        "route": doc.route,
        "url": doc.url,
        "viewport": doc.viewport,
        "user_agent": doc.user_agent,
        "build": doc.build,
        "beschreibung": doc.beschreibung,
        "konsole_log": doc.konsole_log,
        "netzwerk_log": doc.netzwerk_log,
        "screenshot": doc.screenshot,
        "notiz": doc.notiz,
        "created": str(doc.creation) if doc.creation else None,
    }


@whitelist(allow_guest=False)
def set_status(name, status=None):
    """Status eines Berichts setzen (Desk/Orchestrator). Nur Admins."""
    _require_admin()
    allowed = ["Neu", "In Arbeit", "Behoben", "Verworfen"]
    if status not in allowed:
        throw("Ungültiger Status: %s" % (status or ""))
    _update_doc(_BUGREPORT, name, {"status": status})
    return {"name": name, "status": status}
