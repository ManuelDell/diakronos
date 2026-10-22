"""Portierung von `diakonos/api/ressourcen.py` (P4c2).

Quelle (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/ressourcen.py`

Neun Endpunkte der Ressourcen-Buchung, 1:1 nach Logik und Antwortstruktur.
Der SPA-Pfad ist `diakronos.diakonos.api.ressourcen.<fn>` (siehe `hooks.py`
des Originals). ACHTUNG: die SPA ruft `decide_buchung` ueber den Tippfehler-Pfad
`diakronos.diakronos.api.ressourcen.decide_buchung` (Ressourcen.vue:482/:502) auf
und kann diesen Endpunkt deshalb derzeit nicht erreichen. Es wird bewusst KEIN
Alias unter dem falschen Pfad angelegt.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user              -> session.user
    frappe.get_roles()               -> permissions.get_roles()
    frappe.get_all(...)              -> query.get_all(...)   (Zeilen sind dicts)
    frappe.db.exists(...)            -> db.exists(...)
    frappe.db.get_value(...)         -> query.get_value(...)
    frappe.get_doc({...}).insert()   -> _create(...)
    frappe.get_doc(dt, name)         -> query.get_doc(...) -> Document
    doc.save(ignore_permissions=..)  -> _update_doc(...)
    frappe.db.commit()               -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)           -> exceptions.throw(...)
    frappe.utils.now_datetime()      -> _now()
    frappe.utils.get_datetime(...)   -> compat_get_datetime(...)
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.ressourcen"

from datetime import date, datetime
from typing import Any

from diakronos_app.frappe_compat.api_helpers import _create, _delete_doc, _now, _update_doc
from diakronos_app.frappe_compat import db
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.session import session

# ─── Helfer ──────────────────────────────────────────────────────────────────


def compat_get_datetime(value: Any) -> datetime:
    """`frappe.utils.get_datetime` fuer die im Modul benutzten Eingaben.

    Der Altcode ruft `get_datetime` sowohl auf DB-Werte (datetime) als auch auf
    Request-Strings (`"2026-05-01 10:00:00"` / ISO mit `T`) auf. `None` und
    Leerstrings waeren in Frappe `None` — hier ebenfalls, damit die nachfolgenden
    `strftime`-Aufrufe identisch scheitern.
    """
    if value is None or value == "":
        return None  # type: ignore[return-value]
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unbekanntes Datumsformat: {value!r}")


def _get_user():
    user = session.user
    if user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return user


def _is_ressourcenmoderator():
    """Moderationsrechte: Ressourcenmoderator, Mitgliederadministrator oder System Manager."""
    roles = permissions.get_roles()
    return any(r in roles for r in ("Ressourcenmoderator", "Mitgliederadministrator", "System Manager"))


def _typ_key(typ):
    return {"Raum": "room", "Fahrzeug": "vehicle", "Gegenstand": "item"}.get(typ, "item")


# OP-HANDY-23: Deutsche Tages- und Monatsnamen. `strftime('%a/%b')` liefert die
# Namen der Server-Sprache (englisch) — „Sat, 28. Nov 2026“ in einer deutschen
# Oberflaeche. Die Namen stehen deshalb als Tabelle hier.
_WOCHENTAGE_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
_MONATE_DE = [
    "Jan.", "Feb.", "März", "Apr.", "Mai", "Juni",
    "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez.",
]


def _datum_de(wert) -> str:
    """`Sa, 28. Nov. 2026` — deutsch, ohne Server-Sprache (OP-HANDY-23)."""
    return (
        f"{_WOCHENTAGE_DE[wert.weekday()]}, "
        f"{wert.day}. {_MONATE_DE[wert.month - 1]} {wert.year}"
    )


def _zeitraum(von, bis) -> str:
    """`f"{dv.strftime('%d.%m.%Y %H:%M')} - {db_.strftime('%H:%M')}"`."""
    return f"{von.strftime('%d.%m.%Y %H:%M')} - {bis.strftime('%H:%M')}"


def _lesbarer_titel(element_name, element_calendar) -> str:
    """OP-HANDY-12: Termintitel nur zeigen, wenn der Kalender lesbar ist.

    Sonst „Belegt“ — die Belegung bleibt erkennbar (Konflikt erkannt), der
    Titel eines fremden Kalenders wird nicht verraten. Dieselbe Regel wie in
    `kronos.ressource_api`.
    """
    from diakronos_app.api.kronos.permissions import hat_leserecht

    if hat_leserecht(element_calendar):
        return element_name or "Belegt"
    return "Belegt"


def _darf_ressourcen_buchen() -> bool:
    """P1-4b (K1): darf der Aufrufer Buchungen sehen (inkl. Bucher-Name)?

    Der Konfliktdialog nennt bei Ressourcenbuchungen den Namen des Buchers.
    Das ist keine Kalenderangabe, sondern eine Ressourcen-Sicht — sie gehoert
    nur an Ressourcen-Moderatoren/Admins. Alle anderen sehen „Belegt“.
    """
    from diakronos_app.api.kronos.permissions import _is_kalenderadministrator

    user = session.user
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    if _is_ressourcenmoderator():
        return True
    try:
        return bool(_is_kalenderadministrator(user))
    except Exception:  # noqa: BLE001 — Zusatzpruefung, kein Kern
        return False


def _check_konflikte(ressource_id, datum_von, datum_bis, exclude_id=""):
    """Interner Konflikt-Check: Harte Blocker + weiche Hinweise.

    Returns dict:
        hart: list of hard-blocking conflicts (Bestätigte Buchungen + Kalender-Elemente)
        hinweise: list of soft warnings (Angefragt-Anfragen Dritter)
        kalender_konflikte: list of calendar element conflicts
    """
    hart = []
    hinweise = []
    kalender_konflikte = []

    # ── 1. Bestätigte Buchungen (HART) ──────────────────────────────────────
    filters = {
        "ressource": ressource_id,
        "status": "Bestätigt",
        "datum_von": ["<", datum_bis],
        "datum_bis": [">", datum_von],
    }
    if exclude_id:
        filters["name"] = ["!=", exclude_id]

    for b in get_all(
        "Ressourcen Buchung",
        filters=filters,
        fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name"],
    ):
        dv = compat_get_datetime(b["datum_von"])
        db_ = compat_get_datetime(b["datum_bis"])
        hart.append({
            "typ": "buchung",
            "name": b["name"],
            "titel": b["zweck"],
            "zeitraum": _zeitraum(dv, db_),
            "nutzer": b["gebucht_von_name"] or "",
        })

    # ── 2. Kalender-Elemente mit Ressourcenbezug (HART) ─────────────────────
    element_filter = {
        "element_start": ["<", datum_bis],
        "element_end": [">", datum_von],
        "ignore_conflict": 0,
    }

    # 2a. Direkte Ressource auf Element
    direct = get_all(
        "Element",
        filters={**element_filter, "ressource": ressource_id},
        fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
    )
    for el in direct:
        es = compat_get_datetime(el["element_start"])
        ee = compat_get_datetime(el["element_end"])
        kalender_konflikte.append({
            "element": el["name"],
            # OP-HANDY-12: Titel fremder, nicht lesbarer Kalender nicht
            # verraten. Die Belegung bleibt erkennbar („Belegt“); sichtbare
            # Kalender nennen weiterhin ihren Terminnamen.
            "name": _lesbarer_titel(el.get("element_name"), el.get("element_calendar")),
            "zeitraum": _zeitraum(es, ee),
            # ISO-Zeitstempel fuer die Verfuegbarkeitsleiste (OP-HANDY-12).
            "von": es.strftime("%Y-%m-%d %H:%M:%S"),
            "bis": ee.strftime("%Y-%m-%d %H:%M:%S"),
            "quelle": "direkt",
        })

    # 2b. Zusätzliche Ressourcen (Child-Tabelle "Element Ressource", Status Bestätigt)
    child_rows = get_all(
        "Element Ressource",
        filters={"ressource": ressource_id, "status": "Bestätigt"},
        fields=["parent"],
    )
    if child_rows:
        parent_ids = list({r["parent"] for r in child_rows})
        parents = get_all(
            "Element",
            filters={
                **element_filter,
                "name": ["in", parent_ids],
            },
            fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
        )
        for el in parents:
            es = compat_get_datetime(el["element_start"])
            ee = compat_get_datetime(el["element_end"])
            kalender_konflikte.append({
                "element": el["name"],
                "name": _lesbarer_titel(el.get("element_name"), el.get("element_calendar")),
                "zeitraum": _zeitraum(es, ee),
                "von": es.strftime("%Y-%m-%d %H:%M:%S"),
                "bis": ee.strftime("%Y-%m-%d %H:%M:%S"),
                "quelle": "zusatzressource",
            })

    hart.extend({"typ": "kalender", **k} for k in kalender_konflikte)

    # ── 3. Angefragt-Anfragen Dritter (WEICH) ──────────────────────────────
    pending_filters = {
        "ressource": ressource_id,
        "status": "Angefragt",
        "datum_von": ["<", datum_bis],
        "datum_bis": [">", datum_von],
    }
    if exclude_id:
        pending_filters["name"] = ["!=", exclude_id]

    for p in get_all(
        "Ressourcen Buchung",
        filters=pending_filters,
        fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name"],
    ):
        dv = compat_get_datetime(p["datum_von"])
        db_ = compat_get_datetime(p["datum_bis"])
        hinweise.append({
            "name": p["name"],
            "titel": p["zweck"],
            "zeitraum": _zeitraum(dv, db_),
            "nutzer": p["gebucht_von_name"] or "",
        })

    # ── 4. Termin-Ressourcen mit Status „Angefragt“ (WEICH, OP-EVENT-10) ────
    # Ein Vorschlag am Termin sperrt nicht hart, muss aber sichtbar sein —
    # sonst bestaetigt ein Moderator eine Buchung, die einen offenen Vorschlag
    # ueberfaehrt.
    for h in _angefragte_termin_ressourcen(ressource_id, datum_von, datum_bis, exclude_id):
        hinweise.append(h)

    return {"hart": hart, "hinweise": hinweise, "kalender_konflikte": kalender_konflikte}


def _angefragte_termin_ressourcen(ressource_id, datum_von, datum_bis, exclude_id=""):
    """Termin-Ressourcen (Kind-Tabelle) mit Status „Angefragt“ im Zeitraum.

    Nur Termine aus lesbaren Kalendern; der Titel kommt ueber `_lesbarer_titel`.
    """
    zeilen = [
        z for z in (get_all(
            "Element Ressource",
            filters={"ressource": ressource_id, "status": "Angefragt"},
            fields=["name", "parent"],
        ) or [])
        if isinstance(z, dict)
    ]
    if not zeilen:
        return []
    parent_ids = sorted({str(z.get("parent")) for z in zeilen if z.get("parent")})
    if not parent_ids:
        return []
    termine = [
        el for el in (get_all(
            "Element",
            filters={
                "name": ["in", parent_ids],
                "element_start": ["<", datum_bis],
                "element_end": [">", datum_von],
            },
            fields=["name", "element_name", "element_start", "element_end", "element_calendar"],
        ) or [])
        if isinstance(el, dict) and (not exclude_id or el.get("name") != exclude_id)
    ]
    hinweise = []
    for el in termine:
        es = compat_get_datetime(el["element_start"])
        ee = compat_get_datetime(el["element_end"])
        hinweise.append({
            "name": el["name"],
            "titel": _lesbarer_titel(el.get("element_name"), el.get("element_calendar")),
            "zeitraum": _zeitraum(es, ee),
            "nutzer": "",
        })
    return hinweise


def _konflikt_details(konflikte) -> str:
    """Konflikte als lesbare Aufzaehlung (OP-HANDY-12).

    Vorher stand hier `f"{k['typ']}: …"` — der rohe Typ-Schluessel
    („kalender:“ / „buchung:“) landete Wort fuer Wort in der Meldung. Jetzt
    heisst jede Zeile dasselbe wie in der Oberflaeche: „Belegung durch
    ‚Titel' (Zeitraum)“. `_lesbarer_titel` hat fremde Titel bereits zu
    „Belegt“ gemacht.
    """
    teile = []
    for k in konflikte:
        titel = k.get("titel") or k.get("name") or "Belegt"
        zeitraum = k.get("zeitraum") or ""
        teile.append(f"Belegung durch „{titel}“ ({zeitraum})" if zeitraum
                     else f"Belegung durch „{titel}“")
    return "; ".join(teile)


# ─── CRUD ────────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_ressourcen_liste(typ="", search=""):
    """Gibt alle Ressourcen zurück, mit berechnetem Echtzeit-Status."""
    _get_user()

    filters = {}
    if typ:
        typ_de = {"room": "Raum", "vehicle": "Fahrzeug", "item": "Gegenstand"}.get(typ, typ)
        filters["typ"] = typ_de

    ressourcen = get_all(
        "Ressource",
        filters=filters,
        fields=["name", "ressource_name", "typ", "kapazitaet", "beschreibung", "bild", "tags", "wartung"],
        order_by="ressource_name asc",
    )

    now = str(_now())

    result = []
    for r in ressourcen:
        if search:
            q = search.lower()
            haystack = (r["ressource_name"] or "").lower() + " " + (r["beschreibung"] or "").lower() + " " + (r["tags"] or "").lower()
            if q not in haystack:
                continue

        if r["wartung"]:
            status = "maintenance"
        else:
            aktiv = db.exists(
                "Ressourcen Buchung",
                {"ressource": r["name"], "status": "Bestätigt", "datum_von": ["<=", now], "datum_bis": [">=", now]},
            )
            status = "booked" if aktiv else "available"

        tags_list = [t.strip() for t in (r["tags"] or "").split(",") if t.strip()]
        result.append({
            "id":          r["name"],
            "name":        r["ressource_name"],
            "type":        _typ_key(r["typ"]),
            "description": r["beschreibung"] or "",
            "capacity":    r["kapazitaet"] or None,
            "status":      status,
            "tags":        tags_list,
            "image":       r["bild"] or None,
        })

    return result


@whitelist(allow_guest=False)
def get_ressource_buchungen(ressource_id, date_from="", date_to=""):
    """Gibt Buchungen für eine Ressource zurück (alle sichtbaren Status)."""
    _get_user()

    filters = {"ressource": ressource_id}
    # Nur nicht-stornierte anzeigen
    filters["status"] = ["!=", "Storniert"]
    if date_from:
        filters["datum_bis"] = [">=", date_from]
    if date_to:
        filters["datum_von"] = ["<=", date_to]

    buchungen = get_all(
        "Ressourcen Buchung",
        filters=filters,
        fields=["name", "zweck", "datum_von", "datum_bis", "gebucht_von_name",
                "status", "ablehnungs_grund", "moderiert_von"],
        order_by="datum_von asc",
        limit_page_length=50,
    )

    result = []
    for b in buchungen:
        dv = compat_get_datetime(b["datum_von"])
        db_ = compat_get_datetime(b["datum_bis"])
        result.append({
            "id":               b["name"],
            "title":            b["zweck"],
            "date":             dv.strftime("%Y-%m-%d"),
            # OP-HANDY-12: ISO-Zeitstempel fuer die Verfuegbarkeitsleiste. Die
            # Leiste las `_datum_von`/`_datum_bis`, die dieser Endpunkt nie
            # geliefert hat — deshalb war sie immer „alles frei“.
            "datum_von":        dv.strftime("%Y-%m-%d %H:%M:%S"),
            "datum_bis":        db_.strftime("%Y-%m-%d %H:%M:%S"),
            "day":              dv.strftime("%d"),
            "month":            _MONATE_DE[dv.month - 1],
            "time":             f"{dv.strftime('%H:%M')} – {db_.strftime('%H:%M')}",
            "user":             b["gebucht_von_name"] or "",
            "status":           b["status"],
            "ablehnungs_grund": b["ablehnungs_grund"] or "",
            "moderiert_von":    b["moderiert_von"] or "",
        })
    return result


@whitelist(allow_guest=False)
def get_meine_buchungen():
    """Gibt Buchungen des aktuellen Nutzers zurück (alle eigenen, außer stornierte)."""
    user = _get_user()

    buchungen = get_all(
        "Ressourcen Buchung",
        filters={"gebucht_von": user, "status": ["!=", "Storniert"]},
        fields=["name", "ressource", "zweck", "datum_von", "datum_bis",
                "status", "ablehnungs_grund", "moderiert_von"],
        order_by="datum_von asc",
        limit_page_length=50,
    )

    result = []
    for b in buchungen:
        ressource_name = get_value("Ressource", b["ressource"], "ressource_name") or b["ressource"]
        ressource_typ = get_value("Ressource", b["ressource"], "typ") or ""
        dv = compat_get_datetime(b["datum_von"])
        db_ = compat_get_datetime(b["datum_bis"])

        entry = {
            "id":           b["name"],
            "resourceId":   b["ressource"],
            "resourceName": ressource_name,
            "resourceType": _typ_key(ressource_typ),
            "date":         _datum_de(dv),
            "time":         f"{dv.strftime('%H:%M')} – {db_.strftime('%H:%M')}",
            "purpose":      b["zweck"],
            "status":       b["status"],
            "ablehnungs_grund": b["ablehnungs_grund"] or "",
            "moderiert_von":    b["moderiert_von"] or "",
        }
        # Konflikt-Hinweise für Angefragte mitliefern
        if b["status"] == "Angefragt":
            konflikte = _check_konflikte(b["ressource"], str(b["datum_von"]), str(b["datum_bis"]), exclude_id=b["name"])
            if konflikte["hinweise"]:
                entry["konflikt_hinweis"] = konflikte["hinweise"]
        result.append(entry)

    return result


@whitelist(allow_guest=False)
def check_verfuegbarkeit(ressource_id, datum_von, datum_bis, exclude_id=""):
    """Prüft ob die Ressource im Zeitraum verfügbar ist.

    Returns: {verfuegbar: bool, konflikt_hinweis: [...], kalender_konflikte: [...]}
    """
    _get_user()

    if not ressource_id or not datum_von or not datum_bis:
        throw("ressource_id, datum_von und datum_bis sind erforderlich.")

    if not db.exists("Ressource", {"name": ressource_id}):
        throw(f"Ressource '{ressource_id}' nicht gefunden.")

    konflikte = _check_konflikte(ressource_id, datum_von, datum_bis, exclude_id)

    return {
        "verfuegbar": len(konflikte["hart"]) == 0,
        "konflikt_hinweis": konflikte["hinweise"],
        "kalender_konflikte": konflikte["kalender_konflikte"],
        "harte_konflikte": konflikte["hart"],
    }


@whitelist(allow_guest=False)
def create_buchung(ressource_id, datum_von, datum_bis, zweck, notizen=""):
    """Erstellt eine Buchungs-Anfrage (Status IMMER 'Angefragt').

    Hart blockiert nur bei bestätigten Buchungen oder Kalender-Terminen.
    Angefragt-Anfragen Dritter erzeugen konflikt_hinweis, blocken aber nicht.
    """
    user = _get_user()

    if not ressource_id or not datum_von or not datum_bis or not zweck.strip():
        throw("ressource_id, datum_von, datum_bis und zweck sind erforderlich.")

    if not db.exists("Ressource", {"name": ressource_id}):
        throw(f"Ressource '{ressource_id}' nicht gefunden.")

    if compat_get_datetime(datum_bis) <= compat_get_datetime(datum_von):
        throw("Das Ende der Buchung muss nach dem Beginn liegen. Bitte prüfe Datum und Uhrzeit.", ValidationError)

    # Konflikt-Check
    konflikte = _check_konflikte(ressource_id, datum_von, datum_bis)

    if konflikte["hart"]:
        throw(
            f"Ressource im Zeitraum nicht verfügbar: {_konflikt_details(konflikte['hart'])}",
            ValidationError,
        )

    user_doc = get_value("User", user, ["full_name"], as_dict=True) or {}

    buchung_id = _create("Ressourcen Buchung", {
        "ressource":        ressource_id,
        "zweck":            zweck.strip(),
        "datum_von":        datum_von,
        "datum_bis":        datum_bis,
        "notizen":          notizen.strip() if notizen else "",
        "gebucht_von":      user,
        "gebucht_von_name": user_doc.get("full_name") or user,
        "status":           "Angefragt",
    })

    result = {"success": True, "buchung_id": buchung_id, "status": "Angefragt"}
    if konflikte["hinweise"]:
        result["konflikt_hinweis"] = konflikte["hinweise"]

    return result


@whitelist(allow_guest=False)
def decide_buchung(buchung_id, entscheidung, grund=""):
    """Moderator entscheidet über eine Anfrage: bestätigen oder ablehnen.

    Nur Rolle Ressourcenmoderator. Vor Bestätigung: erneuter HARTER Konfliktcheck.
    """
    user = _get_user()

    if not _is_ressourcenmoderator():
        throw("Nur Ressourcenmoderatoren können Anfragen entscheiden.", FrappePermissionError)

    if entscheidung not in ("bestaetigen", "ablehnen"):
        throw("entscheidung muss 'bestaetigen' oder 'ablehnen' sein.", ValidationError)

    doc = get_doc("Ressourcen Buchung", buchung_id)

    if doc.status != "Angefragt":
        throw(f"Nur Anfragen mit Status 'Angefragt' können entschieden werden (aktuell: {doc.status}).", ValidationError)

    # Self-Approval verhindern
    if doc.gebucht_von == user:
        throw("Eigene Anfragen können nicht selbst moderiert werden.", FrappePermissionError)

    if entscheidung == "bestaetigen":
        # Erneuter HARTER Konfliktcheck vor Bestätigung
        konflikte = _check_konflikte(doc.ressource, str(doc.datum_von), str(doc.datum_bis), exclude_id=doc.name)
        if konflikte["hart"]:
            throw(
                f"Bestätigung nicht möglich — Konflikt: {_konflikt_details(konflikte['hart'])}",
                ValidationError,
            )
        neuer_status = "Bestätigt"
        updates = {"status": neuer_status, "moderiert_von": user}
    else:
        neuer_status = "Abgelehnt"
        updates = {
            "status": neuer_status,
            "ablehnungs_grund": grund.strip() if grund else "",
            "moderiert_von": user,
        }

    _update_doc("Ressourcen Buchung", buchung_id, updates)

    # OP-HANDY-6: Die entschiedene Person erfaehrt das Ergebnis. `gebucht_von`
    # ist der Benutzername des Antragstellers (Self-Approval ist oben verboten,
    # der Empfaenger ist also nie der Moderator selbst).
    _benachrichtige_buchung(
        doc, entscheidung, grund, user,
        document_type="Ressourcen Buchung", document_name=buchung_id,
    )

    return {"success": True, "status": neuer_status}


def _benachrichtige_buchung(doc, entscheidung: str, grund: str, moderator: str, *,
                            document_type: str, document_name: str) -> None:
    """In-App-Nachricht an den Antragsteller einer Buchung (Beiwerk)."""
    empfaenger = str(doc.gebucht_von or "")
    if not empfaenger or empfaenger == moderator:
        return
    zweck = str(doc.zweck or doc.ressource or "Buchung")
    if entscheidung == "bestaetigen":
        subject = f"Buchung bestätigt: {zweck}"
        inhalt = (f"Deine Anfrage „{zweck}“ wurde bestätigt. "
                  f"Der Raum/die Ressource ist für dich reserviert.")
    else:
        subject = f"Buchung abgelehnt: {zweck}"
        inhalt = f"Deine Anfrage „{zweck}“ wurde abgelehnt."
        if grund:
            inhalt += f"\nGrund: {grund}"
    from diakronos_app.benachrichtigungen import schreibe_meldung

    schreibe_meldung(for_user=empfaenger, subject=subject, inhalt=inhalt,
                     document_type=document_type, document_name=document_name)


@whitelist(allow_guest=False)
def decide_termin_ressource(zeile_id, entscheidung, grund=""):
    """P1-4b (B1): Moderator entscheidet eine TERMIN-Ressource (quelle="termin").

    `get_anfragen` spiegelt gespiegelte Termin-Ressourcen (`Element Ressource`,
    Status „Angefragt“) in dieselbe Liste. Ihre `id` ist der Name der
    Kind-Zeile — `decide_buchung` laedt dagegen `Ressourcen Buchung` und scheiterte
    daran. Dieser Endpunkt entscheidet sie am richtigen Ort.

    Rechte wie bei Buchungen: nur Ressourcenmoderator (bzw.
    Mitgliederadministrator/System Manager). Kein Selbst-Entscheiden (wer den
    Termin angelegt hat, darf ihn nicht selbst bestaetigen). Vor dem
    Bestaetigen: harter Konfliktcheck ueber die Ressource im Terminzeitraum.

    `ablehnen` LOESCHT die Zeile — eine Termin-Ressource hat keinen
    Ablehnungs-Status; eine abgelehnte Zuordnung darf nicht am Termin stehen
    bleiben. `grund` wird dabei nur fuer die Meldung benutzt.
    """
    user = _get_user()

    if not _is_ressourcenmoderator():
        throw("Nur Ressourcenmoderatoren können Anfragen entscheiden.", FrappePermissionError)

    if entscheidung not in ("bestaetigen", "ablehnen"):
        throw("entscheidung muss 'bestaetigen' oder 'ablehnen' sein.", ValidationError)

    doc = get_doc("Element Ressource", zeile_id)

    if doc.status != "Angefragt":
        throw(
            f"Nur Anfragen mit Status 'Angefragt' können entschieden werden "
            f"(aktuell: {doc.status}).",
            ValidationError,
        )

    parent = str(doc.parent or "")
    if not parent:
        throw("Die Zeile gehört zu keinem Termin.", ValidationError)

    termin = get_doc("Element", parent)

    # Kein Selbst-Entscheiden: wer den Termin angelegt hat, ist befangen.
    if str(termin.get("owner") or "") == user:
        throw("Eigene Termine können nicht selbst moderiert werden.", FrappePermissionError)

    ressource = str(doc.ressource or "")

    if entscheidung == "bestaetigen":
        from diakronos_app.frappe_compat.exceptions import DoesNotExistError

        # Hart blockieren nur belegte, bestaetigte Zuordnungen. Eine Anfrage
        # ohne Katalog-Ressource (reiner Freitext) belegt nichts — nichts zu pruefen.
        if ressource:
            if not db.exists("Ressource", {"name": ressource}):
                throw(f"Ressource '{ressource}' nicht gefunden.", DoesNotExistError)
            konflikte = _check_konflikte(
                ressource,
                str(termin.get("element_start")),
                str(termin.get("element_end")),
                exclude_id=parent,
            )
            if konflikte["hart"]:
                throw(
                    f"Bestätigung nicht möglich — Konflikt: {_konflikt_details(konflikte['hart'])}",
                    ValidationError,
                )
        _update_doc("Element Ressource", zeile_id, {"status": "Bestätigt"})
        # OP-HANDY-6: Der Termin-Eigentuemer erfaehrt die Entscheidung.
        # B-1: `doc` ist eine Element-Ressource-Zeile — sie fuehrt KEIN
        # `ressource_name` (AttributError). Der Anzeigename kommt aus dem
        # Katalog; Freitextzeilen haben keine Kennung, dann bleibt der Text leer.
        _benachrichtige_termin_ressource(
            termin, parent, ressource, "bestaetigen", "", user)
        return {"success": True, "status": "Bestätigt"}

    # Ablehnen: die Zuordnung verschwindet vom Termin — aber nicht spurlos
    # (K-c, P1-8): der Antragsteller wird benachrichtigt, genau wie bei einer
    # Ressourcen-Buchung (`decide_buchung`). Vorher verschwand die Zeile still;
    # wer die Ressource angefragt hatte, erfuhr nie, warum sie nicht kam.
    #
    # R-P1-8/K2: Das fruehere `_update_doc("Element Ressource", ..., {"notiz":
    # grund})` unmittelbar vor dem Loeschen war wirkungslos — die Zeile wird
    # gleich darauf geloescht. Der Grund liegt jetzt ausschliesslich in der
    # Benachrichtigung an den Antragsteller.
    grund_text = str(grund or "").strip()
    antragsteller = str(termin.get("owner") or "")
    ressource_name = str(
        get_value("Ressource", ressource, "ressource_name") or ressource
    ) if ressource else "die Ressource"
    titel = str(termin.get("title") or termin.get("element_name") or "")
    _delete_doc("Element Ressource", zeile_id)
    # OP-HANDY-6: auch eine Ablehnung erreicht den Termin-Eigentuemer.
    _benachrichtige_termin_ressource(
        termin, parent, ressource, "ablehnen", grund_text, user)
    return {"success": True, "status": "Abgelehnt"}


def _ressource_anzeigename(ressource: str) -> str:
    """Anzeigename einer Katalog-Ressource; leer, wenn keine Kennung vorliegt."""
    if not ressource:
        return ""
    return str(get_value("Ressource", ressource, "ressource_name") or ressource)


def _benachrichtige_termin_ressource(termin, element_name: str, ressource: str,
                                     entscheidung: str, grund: str, moderator: str) -> None:
    """In-App-Nachricht an den Eigentuemer eines Termins (Beiwerk).

    B-1: Der Aufruf steht AUSSERHALB des Konflikt-`try` des Aufrufers — ein
    Fehler hier darf die bereits gespeicherte Entscheidung nicht mit einem
    HTTP-Fehler quittieren. Deshalb ist die ganze Funktion abgesichert.
    """
    from diakronos_app.frappe_compat.api_helpers import log_error

    try:
        _schreibe_termin_ressource_meldung(
            termin, element_name, _ressource_anzeigename(ressource), entscheidung, grund, moderator)
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"benachrichtige_termin_ressource {element_name}")


def _schreibe_termin_ressource_meldung(termin, element_name: str, ressource: str,
                                       entscheidung: str, grund: str, moderator: str) -> None:
    empfaenger = str(termin.get("owner") or "")
    if not empfaenger or empfaenger == moderator:
        return
    titel = str(termin.get("element_name") or "Termin")
    name = ressource or "Ressource"
    if entscheidung == "bestaetigen":
        subject = f"Ressource bestätigt: {titel}"
        inhalt = (f"Die Ressource „{name}“ für deinen Termin „{titel}“ wurde bestätigt.")
    else:
        subject = f"Ressource abgelehnt: {titel}"
        inhalt = f"Die Ressource „{name}“ für deinen Termin „{titel}“ wurde abgelehnt."
        if grund:
            inhalt += f"\nGrund: {grund}"
    from diakronos_app.benachrichtigungen import schreibe_meldung

    schreibe_meldung(for_user=empfaenger, subject=subject, inhalt=inhalt,
                     document_type="Element", document_name=element_name)


@whitelist(allow_guest=False)
def get_anfragen():
    """Gibt alle offenen Anfragen zurück (nur Ressourcenmoderator).

    Aufsteigend nach creation, je Anfrage konflikt_hinweis berechnet.
    """
    user = _get_user()

    if not _is_ressourcenmoderator():
        throw("Nur Ressourcenmoderatoren können Anfragen einsehen.", FrappePermissionError)

    anfragen = get_all(
        "Ressourcen Buchung",
        filters={"status": "Angefragt"},
        fields=["name", "ressource", "datum_von", "datum_bis", "zweck", "notizen",
                "gebucht_von", "gebucht_von_name", "creation"],
        order_by="creation asc",
    )

    result = []
    for a in anfragen:
        ressource_name = get_value("Ressource", a["ressource"], "ressource_name") or a["ressource"]
        konflikte = _check_konflikte(a["ressource"], str(a["datum_von"]), str(a["datum_bis"]), exclude_id=a["name"])
        dv = compat_get_datetime(a["datum_von"])
        db_ = compat_get_datetime(a["datum_bis"])

        result.append({
            "id":               a["name"],
            "name":             a["name"],
            "ressource":        a["ressource"],
            "ressource_name":   ressource_name,
            "datum_von":        str(a["datum_von"]),
            "datum_bis":        str(a["datum_bis"]),
            "datum_von_fmt":    dv.strftime("%d.%m.%Y %H:%M"),
            "datum_bis_fmt":    db_.strftime("%H:%M"),
            "zweck":            a["zweck"],
            "notizen":          a["notizen"] or "",
            "gebucht_von":      a["gebucht_von"],
            "gebucht_von_name": a["gebucht_von_name"] or "",
            "creation":         str(a["creation"]),
            "konflikt_hinweis": konflikte["hinweise"] + konflikte["kalender_konflikte"],
        })

    return {"anfragen": result + _event_ressourcen_anfragen()}


def _event_ressourcen_anfragen() -> list[dict[str, Any]]:
    """OP-EVENT-10: Termin-Ressourcen mit Status „Angefragt“ als Anfragen.

    Ein Termin kann eine Ressource als „Angefragt“ fuehren (Kind-Tabelle
    `Element Ressource`). Bisher tauchten solche Zeilen NIRGENDS zur
    Moderation auf: der Termin blockierte nichts, war aber auch fuer keinen
    Ressourcenmoderator sichtbar. Hier werden sie in dieselbe Liste
    gespiegelt — mit `quelle="termin"`, damit die Oberflaeche die Entscheidung
    an den richtigen Endpunkt schickt (`decide_termin_ressource`, P1-4b/B1).

    Nur Termine aus Kalendern, die der Aufrufer lesen darf — sonst waere dies
    ein zweiter Weg, an fremde Titel zu kommen.

    P1-4b: `creation` (der Kind-Zeile) und der Konflikthinweis werden
    mitgeliefert — vorher standen dort „"“ und ein leeres Array, waehrend die
    Buchungs-Anfragen beides fuehren.
    """
    from diakronos_app.api.kronos.permissions import hat_leserecht

    zeilen = [
        z for z in (get_all(
            "Element Ressource", filters={"status": "Angefragt"},
            fields=["name", "parent", "ressource", "freitext_ressource", "notiz",
                    "creation"],
        ) or [])
        if isinstance(z, dict)
    ]
    if not zeilen:
        return []

    # Eltern-Termine in EINER Abfrage holen.
    parent_ids = sorted({str(z.get("parent")) for z in zeilen if z.get("parent")})
    termine = {}
    if parent_ids:
        for el in (get_all(
            "Element",
            filters={"name": ["in", parent_ids]},
            fields=["name", "element_name", "element_start", "element_end",
                    "element_calendar", "owner"],
        ) or []):
            if isinstance(el, dict):
                termine[el["name"]] = el

    ergebnis: list[dict[str, Any]] = []
    for z in zeilen:
        el = termine.get(z.get("parent"))
        if not el or not hat_leserecht(el.get("element_calendar")):
            continue
        ressource_id = z.get("ressource") or z.get("freitext_ressource") or ""
        ressource_name = ressource_id
        if z.get("ressource"):
            ressource_name = get_value("Ressource", z["ressource"], "ressource_name") or z["ressource"]
        dv = compat_get_datetime(el.get("element_start"))
        db_ = compat_get_datetime(el.get("element_end"))
        # P1-4b: Konflikte derselben Anzeige wie bei Buchungen mitliefern,
        # damit die Moderatorin vor dem Bestaetigen sieht, was kollidiert.
        hinweise: list[dict[str, Any]] = []
        if z.get("ressource") and el.get("element_start") and el.get("element_end"):
            k = _check_konflikte(
                z["ressource"],
                str(el.get("element_start")),
                str(el.get("element_end")),
                exclude_id=str(el.get("name") or ""),
            )
            hinweise = k["hinweise"] + k["kalender_konflikte"]
        ergebnis.append({
            "id":               z["name"],
            "name":             z["name"],
            "quelle":           "termin",
            "ressource":        ressource_id,
            "ressource_name":   ressource_name,
            "datum_von":        str(el.get("element_start") or ""),
            "datum_bis":        str(el.get("element_end") or ""),
            "datum_von_fmt":    dv.strftime("%d.%m.%Y %H:%M") if dv else "",
            "datum_bis_fmt":    db_.strftime("%H:%M") if db_ else "",
            "zweck":            el.get("element_name") or "",
            "notizen":          z.get("notiz") or "",
            "gebucht_von":      el.get("owner") or "",
            "gebucht_von_name": el.get("owner") or "",
            "creation":         str(z.get("creation") or ""),
            "konflikt_hinweis": hinweise,
        })
    return ergebnis


@whitelist(allow_guest=False)
def update_buchung(buchung_id, zweck, notizen="", datum_von=None, datum_bis=None):
    """Aktualisiert eine eigene Anfrage (nur wenn Status=Angefragt).

    `zweck`/`notizen` wie im Original; seit OP-EVENT-14 zusaetzlich
    `datum_von`/`datum_bis`. Ohne die beiden Felder verhaelt sich der Aufruf
    exakt wie vorher (nur Zweck/Notizen) — der Bestandsaufruf bleibt gueltig.
    Ein verschobener Zeitraum wird wie beim Anlegen hart geprueft: eine
    Verschiebung darf keine bestaetigte Buchung ueberfahren.

    P1-4b (K3): Unparsbare Zeitangaben werden WIE DIE UEBRIGEN Endpunkte mit
    einer fachlichen Meldung (HTTP 417) abgewiesen. Vorher lief
    `compat_get_datetime` mit einem rohen `ValueError` durch — das war ein 500.
    """
    user = _get_user()

    doc = get_doc("Ressourcen Buchung", buchung_id)

    if doc.gebucht_von != user:
        throw("Nur der Ersteller kann die Anfrage bearbeiten.", FrappePermissionError)

    if doc.status != "Angefragt":
        throw("Nur Anfragen mit Status 'Angefragt' können bearbeitet werden.", ValidationError)

    updates: dict[str, Any] = {
        "zweck": zweck.strip(),
        "notizen": notizen.strip() if notizen else "",
    }

    # OP-EVENT-14: Zeitraum verschieben. Beide Grenzen gehoeren zusammen —
    # nur eine zu setzen hinterliesse einen halb verschobenen Zeitraum.
    if (datum_von in (None, "")) != (datum_bis in (None, "")):
        throw("datum_von und datum_bis muessen gemeinsam angegeben werden.", ValidationError)

    if datum_von not in (None, ""):
        # K3: erst die Zeitangaben normalisieren/pruefen (417 statt 500) —
        # dieselbe Schranke wie in `create_buchung`.
        neu_von = _als_zeitpunkt(datum_von)
        neu_bis = _als_zeitpunkt(datum_bis)
        if neu_bis <= neu_von:
            throw("Das Ende der Buchung muss nach dem Beginn liegen. Bitte prüfe Datum und Uhrzeit.", ValidationError)
        konflikte = _check_konflikte(
            doc.ressource, datum_von, datum_bis, exclude_id=doc.name
        )
        if konflikte["hart"]:
            throw(
                f"Verschiebung nicht möglich — Konflikt: {_konflikt_details(konflikte['hart'])}",
                ValidationError,
            )
        updates["datum_von"] = neu_von
        updates["datum_bis"] = neu_bis

    _update_doc("Ressourcen Buchung", buchung_id, updates)

    return {"success": True}


def _als_zeitpunkt(wert) -> datetime:
    """Zeitangabe in ein `datetime` wandeln — ungueltige Eingabe wird fachlich.

    K3: `compat_get_datetime` wirft bei unparsbaren Werten ein rohes
    `ValueError`; das ergab einen 500er. Hier wird daraus ein `ValidationError`
    (417) mit derselben Meldung wie in den uebrigen Endpunkten.
    """
    try:
        ergebnis = compat_get_datetime(wert)
    except ValueError:
        ergebnis = None
    if ergebnis is None:
        throw(f"Ungültiges Datum: {wert}", ValidationError)
        raise AssertionError("unerreichbar")  # pragma: no cover
    return ergebnis


@whitelist(allow_guest=False)
def delete_buchung(buchung_id):
    """Storniert eine eigene Buchung (soft: Status → Storniert).

    Erlaubt für Status Angefragt oder Bestätigt. Abgelehnt/Storniert → keine Operation.
    """
    user = _get_user()

    doc = get_doc("Ressourcen Buchung", buchung_id)

    if doc.gebucht_von != user:
        throw("Nur der Ersteller kann die Buchung stornieren.", FrappePermissionError)

    if doc.status in ("Abgelehnt", "Storniert"):
        throw(f"Buchung mit Status '{doc.status}' kann nicht storniert werden.", ValidationError)

    _update_doc("Ressourcen Buchung", buchung_id, {"status": "Storniert"})

    return {"success": True}


# ─── Verwaltung: Raeume, Fahrzeuge, Gegenstaende (OP-ADMIN-11) ──────────────
#
# Der Altcode kennt nur das LESEN der Ressourcen (`get_ressources` in
# `kronos.ressource_api`); angelegt wurden die 7 Bestandsraeume beim Import.
# In der Oberflaeche gab es damit keinen Weg, einen Raum zu ergaenzen, einen
# Tippfehler zu berichtigen oder einen ausgemusterten Gegenstand zu entfernen
# (Nachtbefund OP-ADMIN-11). Die folgenden Endpunkte schliessen genau diese
# Luecke — sie schreiben NICHTS anderes als die Zeile `ressource` und ihre
# Belegungen bleiben unangetastet.


#: Arten einer Ressource — dieselbe Quelle wie `kronos.ressource_api`
#: (`_typ_options`), nur hier direkt, um keine zweite Liste zu pflegen.
RESSOURCE_ARTEN = ("Raum", "Fahrzeug", "Gegenstand")


def _require_ressourcen_verwalter() -> str:
    """Ressourcenverwaltung: Ressourcenmoderator oder Administrator. Fail closed.

    Dieselbe Schranke wie beim Bestaetigen einer Buchung
    (`_is_ressourcenmoderator`, plus `Administrator` — den kennt
    `_is_ressourcenmoderator` nicht, weil er in Frappe alle Rechte implizit
    traegt).
    """
    user = _get_user()
    if user != "Administrator" and not _is_ressourcenmoderator():
        throw(
            "Nur Ressourcenmoderatoren dürfen Räume und Gegenstände verwalten.",
            FrappePermissionError,
        )
    return user


def _pruefe_ressource_name(wert, typ) -> str:
    """Anzeigename einer Ressource: Pflicht, getrimmt, hoechstens 140 Zeichen.

    Prueft ausserdem die Art, wenn eine mitkommt — fuer den Aufrufer, der nur
    die Art aendern will, ist das der einzige Pruefpunkt.
    """
    text = str(wert or "").strip()
    if not text:
        raise ValidationError("Bitte einen Namen angeben.")
    if len(text) > 140:
        raise ValidationError("Der Name darf höchstens 140 Zeichen lang sein.")
    if typ and typ not in ("Raum", "Fahrzeug", "Gegenstand"):
        raise ValidationError("Bitte als Art „Raum“, „Fahrzeug“ oder „Gegenstand“ angeben.")
    return text


def _pruefe_kapazitaet(wert) -> int | None:
    """Kapazitaet: leer oder eine ganze Zahl >= 0 (Personen/Zahl der Plaetze)."""
    if wert is None or str(wert).strip() == "":
        return None
    try:
        zahl = int(str(wert).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("Die Kapazität muss eine ganze Zahl sein.") from exc
    if zahl < 0:
        raise ValidationError("Die Kapazität darf nicht negativ sein.")
    return zahl


@whitelist(allow_guest=False)
def get_ressourcen_verwaltung():
    """Alle Ressourcen mit allen Feldern fuer die Verwaltungsseite.

    Anders als `get_ressourcen_liste` (Kalender-/Buchungssicht mit
    Echtzeit-Status) liefert das hier die PFLEGE-Sicht: Art, Kapazitaet,
    Beschreibung, Tags, Wartung — genau die Felder, die der Verwaltungsdialog
    bearbeitet.
    """
    _require_ressourcen_verwalter()

    rows = get_all(
        "Ressource",
        fields=["name", "ressource_name", "typ", "kapazitaet", "beschreibung", "tags", "wartung"],
    ) or []
    rows = sorted(rows, key=lambda r: (r.get("typ") or "", r.get("ressource_name") or r.get("name") or ""))

    return {
        "ressourcen": [
            {
                "id": r["name"],
                "name": r.get("ressource_name") or r["name"],
                "typ": r.get("typ") or "Gegenstand",
                "kapazitaet": r.get("kapazitaet"),
                "beschreibung": r.get("beschreibung") or "",
                "tags": r.get("tags") or "",
                "wartung": 1 if r.get("wartung") else 0,
            }
            for r in rows
        ],
        "arten": list(RESSOURCE_ARTEN),
    }


@whitelist(allow_guest=False)
def create_ressource(name, typ="Raum", kapazitaet=None, beschreibung="", tags="", wartung=0):
    """Neue Ressource anlegen (Raum, Fahrzeug oder Gegenstand).

    Der `name` ist der Docname (Termine und Buchungen zeigen darauf); der
    Anzeigename steht in `ressource_name`. Beide werden auf denselben Wert
    gesetzt — ein abweichender Docname waere nur eine zweite Wahrheit.
    Doppelte Namen werden abgelehnt.
    """
    _require_ressourcen_verwalter()

    anzeige = _pruefe_ressource_name(name, typ)
    doppelt = get_all(
        "Ressource", filters={"ressource_name": anzeige}, fields=["name"], limit_page_length=1
    ) or []
    if db.exists("Ressource", {"name": anzeige}) or doppelt:
        raise ValidationError(f"Eine Ressource mit dem Namen „{anzeige}“ gibt es schon.")

    _create(
        "Ressource",
        {
            "name": anzeige,
            "ressource_name": anzeige,
            "typ": typ,
            "kapazitaet": _pruefe_kapazitaet(kapazitaet),
            "beschreibung": str(beschreibung or "").strip(),
            "tags": str(tags or "").strip(),
            "wartung": 1 if wartung else 0,
        },
    )
    return {"success": True, "id": anzeige}


@whitelist(allow_guest=False)
def update_ressource(ressource_id, name=None, typ=None, kapazitaet=None,
                     beschreibung=None, tags=None, wartung=None):
    """Ressource aendern. Nicht mitgeschickte Felder bleiben unveraendert.

    `wartung` sperrt die Ressource fuer neue Buchungen (Feld `ressource.wartung`,
    das `get_ressourcen_liste` bereits als Status „maintenance“ auswertet) und
    ist damit der Weg, „Ausfall/Wartung“ ueberhaupt eintragen zu koennen.
    """
    _require_ressourcen_verwalter()

    doc = get_doc("Ressource", str(ressource_id or "").strip())
    if doc is None:
        raise ValidationError("Ressource nicht gefunden.")

    werte: dict[str, Any] = {}
    if name is not None:
        anzeige = _pruefe_ressource_name(name, typ or doc.get("typ"))
        if anzeige != (doc.get("ressource_name") or doc.name):
            doppelt = get_all(
                "Ressource", filters={"ressource_name": anzeige}, fields=["name"], limit_page_length=5
            ) or []
            if any(z.get("name") != doc.name for z in doppelt):
                raise ValidationError(f"Eine Ressource mit dem Namen „{anzeige}“ gibt es schon.")
        werte["ressource_name"] = anzeige
    if typ is not None:
        _pruefe_ressource_name("Platzhalter", typ)  # prueft nur die Art
        werte["typ"] = typ
    if kapazitaet is not None:
        werte["kapazitaet"] = _pruefe_kapazitaet(kapazitaet)
    if beschreibung is not None:
        werte["beschreibung"] = str(beschreibung or "").strip()
    if tags is not None:
        werte["tags"] = str(tags or "").strip()
    if wartung is not None:
        werte["wartung"] = 1 if wartung else 0

    if werte:
        _update_doc("Ressource", doc.name, werte)
    return {"success": True, "id": doc.name}


@whitelist(allow_guest=False)
def delete_ressource(ressource_id, bestaetigt=0):
    """Ressource entfernen — nur ohne Buchungen und Terminbezug.

    Eine Ressource, auf die noch Buchungen oder Termine zeigen, wird NICHT
    geloescht: die Buchungen zeigten danach ins Leere (in „Meine Buchungen“
    waere der Raum nicht mehr aufloesbar), und am Termin bliebe eine
    unaufloesbare Ressourcenzeile stehen.

    R-P2-5 (klein 2): Auch STORNIERTE Buchungen und Termin-Kindzeilen
    (`ElementRessource`) blockieren das Loeschen — sonst antwortet die
    Fremdschluessel-Pruefung mit 417 und rohem SQL-Text.
    """
    _require_ressourcen_verwalter()

    doc = get_doc("Ressource", str(ressource_id or "").strip())
    if doc is None:
        raise ValidationError("Ressource nicht gefunden.")

    # ALLE Buchungen, auch stornierte (Grund wie bei delete_kalender).
    buchungen = get_all(
        "Ressourcen Buchung",
        filters={"ressource": doc.name},
        fields=["name"],
    ) or []
    if buchungen:
        raise ValidationError(
            f"Zu dieser Ressource gibt es noch {len(buchungen)} Buchungen (auch "
            "stornierte zählen). Bitte zuerst die Buchungen endgültig löschen."
        )

    termine = get_all("Element", filters={"ressource": doc.name}, fields=["name"]) or []
    if termine:
        raise ValidationError(
            f"Diese Ressource ist noch an {len(termine)} Terminen eingetragen. "
            "Bitte zuerst dort entfernen."
        )

    # Termin-Kindzeilen (Element Ressource) zeigen ebenfalls auf die Ressource.
    try:
        kindzeilen = get_all(
            "Element Ressource", filters={"ressource": doc.name}, fields=["name"]
        ) or []
    except Exception:  # noqa: BLE001 — fehlende Tabelle ist kein Verweis
        kindzeilen = []
    if kindzeilen:
        raise ValidationError(
            f"Diese Ressource ist noch in {len(kindzeilen)} Termin-Einträgen "
            "vermerkt. Bitte zuerst dort entfernen."
        )

    if not int(bestaetigt or 0):
        raise ValidationError("Zum Löschen bitte bestätigen.")

    _delete_doc("Ressource", doc.name)
    return {"success": True, "id": doc.name}
