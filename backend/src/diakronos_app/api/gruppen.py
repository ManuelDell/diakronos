"""Portierung von `diakronos.diakonos.api.gruppen` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/gruppen.py`

Uebersetzen heisst hier: **dieselbe Signatur, dieselbe Antwortstruktur,
dieselbe Logik.** Die Umstaendlichkeit des Originals ist die Fachlogik.

Portierte Endpunkte (dotted paths identisch zum Original):

    get_gruppen_hierarchie        get_gruppe_detail
    get_untergruppe_detail        add_mitglied_to_gruppe
    remove_mitglied_from_gruppe   update_mitglied_rolle
    get_gruppen_for_orgchart      get_user_create_permissions
    create_dienstbereich          create_gruppe
    create_untergruppe            update_gruppe
    update_untergruppe            update_dienstbereich
    get_gruppen_page_data
    get_aufgaben                  create_aufgabe
    toggle_aufgabe                get_ankuendigungen
    create_ankuendigung

NICHT portiert: — (update_dienstbereich wurde in P1-7 ergaenzt, der Altcode
hatte die Funktion nicht; Begruendung bei der Funktion selbst).

Frappe-Aufrufe des Originals -> Compat-Schicht (nur das, was `frappe_compat`
tatsaechlich anbietet):

    frappe.session.user           -> session.user
    frappe.get_roles(user)        -> permissions.get_roles()
    frappe.db.sql(...)            -> query.get_all(...) + Python-Aggregation
    frappe.db.get_value(...)      -> query.get_value(...)
    frappe.db.count(...)          -> db.count(...)
    frappe.db.exists(...)         -> db.exists(...)
    frappe.get_doc(...)           -> query.get_doc(...) -> Document
    frappe.get_all(...)           -> query.get_all(...)
    frappe.throw(...)             -> exceptions.throw(...)
    doc.append("mitglieder", ..)  -> _child_insert(...)  (Document kennt kein append)
    frappe.get_doc({...}).insert()-> _create(...)        (Document kennt kein dict-insert)
    frappe.utils.today()          -> date.today().isoformat()

Die 14 `frappe.db.sql`-Aufrufe des Originals sind **alle** auf
`get_all`/`db.count` umgestellt:
die Originale sind DISTINCT-parent- und COUNT-GROUP-BY-Abfragen, die der
Filter-Compiler bzw. eine Python-Aggregation abbilden. Kein rohes SQL.

Berechtigungen kommen ausschliesslich aus `frappe_compat.permissions`
(EINE Wahrheit, P3) — hier wird nichts nachgebaut.
"""

from __future__ import annotations

# Original-Frappe-Modulpfad. Die SPA ruft ausschliesslich diese Form auf;
# die Registry registriert daraus `diakronos.diakonos.api.gruppen.<funktion>`.
FRAPPE_MODULE = "diakronos.diakonos.api.gruppen"

import uuid
from datetime import date, datetime, timezone
from typing import Any

from diakronos_app import frappe_compat as frappe
from diakronos_app.frappe_compat import db as _db
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    FrappeCompatError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.mitglied_sichtbarkeit import (
    ist_eigenes_mitglied,
    maskiere_datensatz,
)
from diakronos_app.frappe_compat.permissions import (
    _extract_segments,
    _get_current_user_mitglied,
    _is_verantwortlicher_in,
    _paths_overlap,
    check_permission,
    get_roles,
    ist_verantwortlich_fuer,
    mitglied_permissions,
)
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.registry_gen import column_names, is_known, model_for
from diakronos_app.frappe_compat.session import session
# UXD-R28/DES-04: die eine Farbreinigungsstelle — dieselbe nutzt das
# Organigramm (`api/orgchart_api.py`). Keine zweite Kopie der Pruefregel.
from diakronos_app.api.farbe import _normalisiere_farbe  # noqa: F401  (Re-Export fuer Tests)

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]

# Doctypes, die eine Kind-Tabelle "mitglieder" bzw. "verantwortliche" tragen.
_MITGLIEDSCHAFT = {
    "Gruppe": "Gruppenmitgliedschaft",
    "Untergruppe": "Untergruppenmitgliedschaft",
}
_VERANTWORTLICHER = {
    "Gruppe": "Gruppe Verantwortlicher",
    "Untergruppe": "Untergruppe Verantwortlicher",
    "Dienstbereich": "Dienstbereich Verantwortlicher",
}


# ── Interne Helfer (ersetzt frappe-Komfort, den die Compat-Schicht nicht hat) ──


def _is_admin() -> bool:
    """Admin-Kurzschluss aus den Rollen (Original: `any(r in ADMIN_ROLES)`)."""
    return any(r in get_roles() for r in ADMIN_ROLES)


def _today() -> str:
    """`frappe.utils.today()` -> ISO-Datum."""
    return date.today().isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_name() -> str:
    """Ersatz fuer Frappe-Autonamen (Altcode: `autoname = field:gruppenname`).

    Der Altcode bekam den Namen aus dem Feld; im Standalone-Backend ist der PK
    ein String. Ein kurzer, eindeutiger Name erhaelt die Semantik (stabil,
    nicht erratbar) ohne vom Anzeigenamen abzuhaengigen.
    """
    return str(uuid.uuid4())[:10]


def _coerce(doctype: str, data: dict[str, Any]) -> dict[str, Any]:
    """Werte an die Spaltentypen anpassen (HTTP liefert Strings).

    Frappe parst Datums-/Zeitangaben aus dem Request; hier macht das die
    Portierung selbst, damit der Altcode-Aufrufer (SPA) weiter ISO-Strings
    schicken darf. Nur `Date`/`DateTime`-Spalten werden angefasst.
    """
    from sqlalchemy import Date, DateTime

    model = model_for(doctype)
    cols = {c.name: c for c in model.__table__.columns}
    out = dict(data)
    for key, value in list(out.items()):
        if value is None or not isinstance(value, str):
            continue
        col = cols.get(key)
        if col is None:
            continue
        # SQLAlchemy-Typ kann ein Instance- oder Klassenobjekt sein.
        typ = col.type
        is_date = isinstance(typ, Date) and not isinstance(typ, DateTime)
        is_dt = isinstance(typ, DateTime)
        if is_date:
            try:
                out[key] = date.fromisoformat(value[:10])
            except ValueError:
                pass
        elif is_dt:
            try:
                out[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
    return out


def _create(doctype: str, values: dict[str, Any]) -> str:
    """`frappe.get_doc({...}).insert()` + `frappe.db.commit()`.

    Die Compat-Schicht kennt kein dict-insert; hier wird direkt eine
    SQLAlchemy-Session benutzt (Muster: `api/frappe_core.py:121-135`).
    Felder, die das Modell nicht kennt, werden verworfen (Frappe ignoriert
    unbekannte Felder ebenfalls, statt zu scheitern).
    """
    if not is_known(doctype):
        raise ValidationError(f"DocType {doctype!r} nicht gefunden")

    from diakronos_app.db import SessionLocal

    model = model_for(doctype)
    cols = column_names(doctype)
    data = {k: v for k, v in values.items() if k in cols}
    data = _coerce(doctype, data)
    if not data.get("name"):
        data["name"] = _new_name()
    # Frappe setzt die Metafelder selbst.
    data.setdefault("docstatus", 0)
    data.setdefault("idx", 0)
    data.setdefault("owner", session.user)
    data.setdefault("modified_by", session.user)
    data.setdefault("creation", _now())
    data.setdefault("modified", _now())

    sess = SessionLocal()
    try:
        obj = model(**data)
        sess.add(obj)
        sess.commit()
        return data["name"]
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001 — als fachlicher Fehler zurueckgeben
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


def _child_insert(
    child_doctype: str,
    parent: str,
    parentfield: str,
    values: dict[str, Any],
    parenttype: str | None = None,
) -> str:
    """`doc.append(parentfield, {...})` einer Kind-Tabelle + Speichern.

    `Document` hat bewusst kein `append` (siehe `frappe_compat/doc.py`); der
    Altcode haengt aber Zeilen an Gruppen/Untergruppen. Kind-Zeilen werden
    deshalb direkt geschrieben — mit derselben Dreiteilung
    parent/parenttype/parentfield wie in Frappe.
    """
    if not is_known(child_doctype):
        raise ValidationError(f"DocType {child_doctype!r} nicht gefunden")

    from sqlalchemy import func, select

    from diakronos_app.db import SessionLocal

    model = model_for(child_doctype)
    cols = column_names(child_doctype)

    sess = SessionLocal()
    try:
        # idx = naechste Position innerhalb des Elternfeldes (Frappe-Konvention).
        max_idx = sess.execute(
            select(func.max(model.idx)).where(
                model.parent == parent, model.parentfield == parentfield
            )
        ).scalar()
        data = dict(values)
        data["name"] = data.get("name") or _new_name()
        data["parent"] = parent
        # parenttype ist der DocType der ELTERNZEILE (Frappe-Konvention).
        data["parenttype"] = parenttype or _parenttype_for(child_doctype)
        data["parentfield"] = parentfield
        data["idx"] = (int(max_idx) + 1) if max_idx is not None else 1
        data.setdefault("docstatus", 0)
        data.setdefault("owner", session.user)
        data.setdefault("modified_by", session.user)
        data.setdefault("creation", _now())
        data.setdefault("modified", _now())
        data = {k: v for k, v in data.items() if k in cols}
        data = _coerce(child_doctype, data)
        obj = model(**data)
        sess.add(obj)
        sess.commit()
        return data["name"]
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


def _child_delete(child_doctype: str, parent: str, parentfield: str, filters: dict[str, Any]) -> int:
    """Kind-Zeilen entfernen (Original: `doc.get(table).remove(row)` + save)."""
    from diakronos_app.db import SessionLocal

    model = model_for(child_doctype)
    sess = SessionLocal()
    try:
        conditions = [model.parent == parent, model.parentfield == parentfield]
        for feld, wert in filters.items():
            conditions.append(getattr(model, feld) == wert)
        result = sess.execute(model.__table__.delete().where(*conditions))
        sess.commit()
        return int(result.rowcount or 0)
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


def _child_rows(child_doctype: str, parent: str, parentfield: str) -> list[dict[str, Any]]:
    """Kind-Zeilen eines Elternfeldes, nach `idx` sortiert.

    Die Mitglieds- und Verantwortlichen-Kindtabellen haben unterschiedliche
    Spalten (`mitglied` vs. `user`); es werden nur vorhandene Felder angefragt.
    """
    cols = column_names(child_doctype)
    wanted = [
        f for f in ("name", "mitglied", "user", "rolle", "status", "beitrittsdatum")
        if f in cols
    ]
    return list(
        get_all(
            child_doctype,
            filters={"parent": parent, "parentfield": parentfield},
            fields=wanted,
            order_by="idx asc",
        )
        or []
    )


def _update_doc(doctype: str, name: str, values: dict[str, Any]) -> None:
    """`doc.feld = ...; doc.save()` — nur gesetzte Felder schreiben."""
    from diakronos_app.db import SessionLocal

    model = model_for(doctype)
    cols = column_names(doctype)
    data = {k: v for k, v in values.items() if k in cols and v is not None}
    if not data:
        return
    data = _coerce(doctype, data)
    data["modified"] = _now()
    if "modified_by" in cols:
        data["modified_by"] = session.user

    sess = SessionLocal()
    try:
        obj = sess.get(model, name)
        if obj is None:
            raise DoesNotExistError(f"{doctype} {name!r} existiert nicht")
        for feld, wert in data.items():
            setattr(obj, feld, wert)
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


def _count(child_doctype: str, parent: str) -> int:
    """`frappe.db.count(child, {"parent": parent, "status": "Aktiv"})`."""
    return int(_db.count(child_doctype, {"parent": parent, "status": "Aktiv"}) or 0)


def _require(condition: bool, message: str) -> None:
    """`frappe.throw(msg, frappe.PermissionError)`."""
    if not condition:
        throw(message, FrappePermissionError)


# `_normalisiere_farbe` (UXD-R28) liegt in `api/farbe.py` — sie wird auch vom
# Organigramm (`orgchart_api.py`) gebraucht. Import oben, keine Kopie hier.


def _parenttype_for(child_doctype: str) -> str:
    """Eltern-DocType zu einer Kind-Tabelle (Frappe-Konvention parenttype).

    `child_table_of` der Registry ist nicht oeffentlich; die Zuordnung ist
    klein und explizit — genau die Tabellen, die dieser Modul-Port anfasst.
    """
    return {
        "Gruppenmitgliedschaft": "Gruppe",
        "Gruppe Verantwortlicher": "Gruppe",
        "Untergruppenmitgliedschaft": "Untergruppe",
        "Untergruppe Verantwortlicher": "Untergruppe",
        "Dienstbereich Verantwortlicher": "Dienstbereich",
    }.get(child_doctype, child_doctype)


# ── Hierarchie ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_gruppen_hierarchie():
    """
    Gibt alle Gruppen und Untergruppen als Baum zurück.
    Respektiert Permissions via ancestor_path.
    """
    is_admin = _is_admin()

    gruppen = get_all(
        "Gruppe",
        fields=[
            "name", "gruppenname", "dienstbereich", "gruppentyp", "status",
            "sichtbarkeit", "beschreibung", "ancestor_path",
        ],
        filters={"status": ["!=", "Archiviert"]},
        order_by="gruppenname asc",
    )

    untergruppen = get_all(
        "Untergruppe",
        fields=[
            "name", "untergruppenname", "gruppe", "status", "sichtbarkeit",
            "beschreibung", "ancestor_path",
        ],
        filters={"status": ["!=", "Archiviert"]},
        order_by="untergruppenname asc",
    )

    # Permission-Filter für normale User
    if not is_admin:
        current_mitglied = _get_current_user_mitglied()
        user_path = current_mitglied.get("ancestor_path", "|") if current_mitglied else "|"
        gruppen = [g for g in gruppen if _has_group_access(g, user_path)]
        untergruppen = [u for u in untergruppen if _has_group_access(u, user_path)]

    # Zwei Abfragen statt einer pro (Unter-)Gruppe, nur sichtbare Eltern.
    from collections import Counter

    gruppe_counts = {}
    for typ, eltern in (("Gruppenmitgliedschaft", gruppen),
                        ("Untergruppenmitgliedschaft", untergruppen)):
        ids = [g["name"] for g in eltern]
        if ids:
            counts = Counter(r["parent"] for r in get_all(
                typ, fields=["parent"], filters={"parent": ["in", ids], "status": "Aktiv"}))
            gruppe_counts.update(counts)

    # Baum aufbauen
    result = []
    for g in gruppen:
        ug_list = [u for u in untergruppen if u["gruppe"] == g["name"]]
        result.append({
            "name": g["name"],
            "gruppenname": g["gruppenname"],
            "dienstbereich": g["dienstbereich"],
            "gruppentyp": g["gruppentyp"],
            "status": g["status"],
            "sichtbarkeit": g["sichtbarkeit"],
            "beschreibung": g["beschreibung"],
            "mitglieder_count": gruppe_counts.get(g["name"], 0),
            "untergruppen": [
                {
                    "name": u["name"],
                    "untergruppenname": u["untergruppenname"],
                    "status": u["status"],
                    "sichtbarkeit": u["sichtbarkeit"],
                    "beschreibung": u["beschreibung"],
                    "mitglieder_count": gruppe_counts.get(u["name"], 0),
                }
                for u in ug_list
            ],
        })

    return {"success": True, "gruppen": result}


def _hat_dienstbereich_verantwortung(dienstbereich: str | None) -> bool:
    """`frappe.db.exists("Dienstbereich Verantwortlicher", {"parent": .., "user": ..})`."""
    if not dienstbereich:
        return False
    return bool(_db.exists(
        "Dienstbereich Verantwortlicher",
        {"parent": dienstbereich, "user": session.user},
    ))


def _hat_gruppen_verantwortung(gruppe: str | None) -> bool:
    """`frappe.db.exists("Gruppe Verantwortlicher", {"parent": .., "user": ..})`."""
    if not gruppe:
        return False
    return bool(_db.exists(
        "Gruppe Verantwortlicher", {"parent": gruppe, "user": session.user}
    ))


def _mitglied_id_des_users() -> str | None:
    """Mitglied des aktuellen Users — via `user`-Feld, sonst via E-Mail.

    Quelle (Original, gruppen.py:94-97, 172-175, 209-212, 256-259):
        get_value(Mitglied, {"user": session.user}, "name")
        or get_value(Mitglied, {"email": <User.email>}, "name")
    """
    user = session.user
    by_user = get_value("Mitglied", {"user": user}, "name")
    if by_user:
        return by_user
    email = get_value("User", user, "email") or user
    return get_value("Mitglied", {"email": email}, "name") or None


def _hat_gruppen_lesezugriff(doctype: str, docname: str, child_doctype: str) -> bool:
    """Dasselbe Lese-Gate fuer Details und Inhalte (B4)."""
    if check_permission(doctype, docname, "read").get("allowed"):
        return True
    current_mitglied = _mitglied_id_des_users()
    return bool(current_mitglied and _db.exists(
        child_doctype, {"parent": docname, "mitglied": current_mitglied}
    ))


def _require_gruppen_lesezugriff(doctype: str, docname: str, kind: str, child_doctype: str) -> None:
    """Zugriffsgate der Detail-Endpunkte (Original gruppen.py:91-105 / 206-220).

    Erst `check_permission`; verweigert sie, ist der User NUR dann noch
    zugelassen, wenn er direktes Mitglied ist. Alles andere -> PermissionError.
    """
    _require(_hat_gruppen_lesezugriff(doctype, docname, child_doctype), f"Kein Zugriff auf diese {kind}.")


def _mitglieder_der_gruppe(doctype: str, docname: str) -> list[dict[str, Any]]:
    """Kind-Zeilen `mitglieder` eines Gruppe/Untergruppe-Dokuments aufloesen.

    B2: `email` ist ein Adressbuch-Feld, also der einen `adressbuch_sichtbarkeit`
    unterliegt. Dieser Weg las es ungeprueft — dieselbe Luecke wie in Liste und
    Detail. Die Maskierung laeuft ueber die zentrale Funktion
    (`frappe_compat.mitglied_sichtbarkeit.maskiere_datensatz`), damit es nicht
    eine zweite, davon abweichende Regel gibt. Nur `email` wird hier
    ausgeliefert; `adressbuch_sichtbarkeit` selbst wird entfernt.

    Das Frappe-Original hat hier ebenfalls keinen Sichtbarkeitsfilter
    (`referenz/.../api/gruppen.py`) — dieselbe dokumentierte Abweichung wie in
    `mitglieder.py`, gleiche Begruendung (siehe Modul-Docstring dort).
    """
    child = _MITGLIEDSCHAFT[doctype]
    # AUSTRITT-b (B1): Der Anzeigename kommt aus `personen_anzeige.anzeigename`
    # — eine Regel fuer alle Auslieferungswege. Ohne sie stand hier der
    # Klarname einer ausgetretenen Person fuer jeden Gruppenleser.
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    sicht = PersonenSicht.aus()
    out: list[dict[str, Any]] = []
    for row in _child_rows(child, docname, "mitglieder"):
        if not row.get("mitglied"):
            continue
        m = get_value(
            "Mitglied", row["mitglied"],
            ["name", "vorname", "nachname", "email", "foto",
             "adressbuch_sichtbarkeit", "ausgeschlossen", "status",
             "austritt_datum"],
            as_dict=True,
        )
        if not m:
            continue
        # `vollstaendig` nur fuer Admin bzw. das eigene Mitglied; alles andere
        # geht durch die gemeinsame Feld-fuer-Feld-Regel.
        ziel = row["mitglied"]
        sichtbar = (
            bool(mitglied_permissions(ziel).get("can_view_sensitive"))
            or ist_eigenes_mitglied(ziel)
        )
        m = maskiere_datensatz(dict(m), mitglied_id=ziel, vollstaendig=sichtbar) or {}
        out.append({
            "mitglied": ziel,
            "name": anzeigename(m, sicht=sicht) or m.get("name"),
            "email": m.get("email"),
            "foto": m.get("foto"),
            "rolle": row.get("rolle"),
            "status": row.get("status"),
            "beitrittsdatum": row.get("beitrittsdatum"),
        })
    return out


@whitelist(allow_guest=False)
def get_gruppe_detail(gruppe_id):
    """
    Gibt Details einer Gruppe inkl. Mitglieder und Verantwortliche zurück.

    UXD-R7: Ist die ID keine Gruppe, aber eine Untergruppe, wird deren Detail
    geliefert (statt eines 404, auf den die SPA sonst mit einer zweiten
    Abfrage reagiert). Eine ID pro Adresse, eine Antwort — kein Probe-404 mehr.
    """
    # Erst Gruppe, dann Untergruppe — die ID ist in der Adresse nicht typisiert.
    if get_value("Gruppe", gruppe_id, "name") is None \
            and get_value("Untergruppe", gruppe_id, "name") is not None:
        return get_untergruppe_detail(gruppe_id)

    _require_gruppen_lesezugriff("Gruppe", gruppe_id, "Gruppe", "Gruppenmitgliedschaft")

    # AUSTRITT-b (B1): die Sicht EINMAL für alle Namensauflösungen dieses
    # Endpunkts (Mitglieder oben holen sie sich selbst, sie ist dieselbe).
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    sicht = PersonenSicht.aus()

    gruppe = get_doc("Gruppe", gruppe_id)
    if not gruppe:
        throw("Gruppe nicht gefunden.", DoesNotExistError)

    untergruppen = get_all(
        "Untergruppe",
        fields=["name", "untergruppenname", "status", "treffpunkt", "treffzeit"],
        filters={"gruppe": gruppe_id},
        order_by="untergruppenname asc",
    )
    untergruppen = [
        u for u in untergruppen
        if _hat_gruppen_lesezugriff("Untergruppe", u["name"], "Untergruppenmitgliedschaft")
    ]

    mitglieder = _mitglieder_der_gruppe("Gruppe", gruppe_id)

    # Verantwortliche aufloesen
    verantwortliche = []
    for row in _child_rows("Gruppe Verantwortlicher", gruppe_id, "verantwortliche"):
        if not row.get("user"):
            continue
        v = get_value(
            "Mitglied", {"user": row["user"]},
            ["name", "vorname", "nachname", "email", "foto",
             "adressbuch_sichtbarkeit", "ausgeschlossen", "status",
             "austritt_datum"],
            as_dict=True,
        )
        # `get_value(..., as_dict=True)` ist untypisiert und liefert laut
        # Signatur auch eine Liste. Der Bestand liefert an dieser Stelle ein
        # Dict (`if v:`), deshalb wird es hier ausdruecklich so behandelt und
        # nicht stillschweigend weiterverwendet.
        if isinstance(v, list):
            v = v[0] if v else None
        if v:
            # B2: derselbe Weg, dieselbe Regel wie in der Mitgliederliste
            # oben — `email` ist ein Adressbuch-Feld. Der Verantwortliche wird
            # ueber `user` gefunden, sein `name` ist deshalb der Schluessel.
            v_name = str(v.get("name") or "")
            v = maskiere_datensatz(
                dict(v),
                mitglied_id=v_name,
                vollstaendig=(
                    bool(mitglied_permissions(v_name).get("can_view_sensitive"))
                    or ist_eigenes_mitglied(v_name)
                ),
            ) or {}
            verantwortliche.append({
                # Der Accountname ist oft selbst die verborgene Email.
                "verantwortlicher": row["user"] if v.get("email") is not None else None,
                "name": anzeigename(v, sicht=sicht),
                "email": v.get("email"),
                "foto": v.get("foto"),
            })

    aufgaben = _get_gruppen_inhalte(
        "Gruppen Aufgabe",
        filters={"gruppe": gruppe_id},
        fields=["name", "titel", "erledigt", "faellig"],
        order_by="erledigt asc, creation asc",
    )
    ankuendigungen = _get_gruppen_inhalte(
        "Gruppen Ankuendigung",
        filters={"gruppe": gruppe_id},
        fields=["name", "titel", "text", "pinned", "creation"],
        order_by="pinned desc, creation desc",
    )
    # Original prueft `frappe.db.has_column("Wiki Artikel", "gruppe")`; das
    # Standalone-Schema hat kein solches Feld -> Zweig entfaellt.
    # Antwortfeld bleibt, damit die SPA stabil ist.
    wiki_artikel: list[dict[str, Any]] = []

    # Prüfe ob aktueller User Mitglied ist (für Frontend-Logik)
    current_mitglied_id = _mitglied_id_des_users()
    is_member = bool(_db.exists(
        "Gruppenmitgliedschaft", {"parent": gruppe_id, "mitglied": current_mitglied_id}
    )) if current_mitglied_id else False

    return {
        "success": True,
        "is_member": is_member,
        "gruppe": {
            "name": gruppe.name,
            "gruppenname": gruppe.gruppenname,
            "dienstbereich": gruppe.dienstbereich,
            # UXD-R25: Anzeigename statt roher ID im Untertitel der Detailseite.
            "dienstbereich_name": (
                get_value("Dienstbereich", gruppe.dienstbereich, "ministry") or gruppe.dienstbereich
            ) if gruppe.dienstbereich else "",
            "gruppentyp": gruppe.gruppentyp,
            "status": gruppe.status,
            "sichtbarkeit": gruppe.sichtbarkeit,
            "beschreibung": gruppe.beschreibung,
            "treffpunkt": gruppe.treffpunkt,
            "treffzeit": gruppe.treffzeit,
            "bild": gruppe.bild,
        },
        "untergruppen": untergruppen,
        "mitglieder": mitglieder,
        "verantwortliche": verantwortliche,
        "aufgaben": aufgaben,
        "ankuendigungen": ankuendigungen,
        "wiki_artikel": wiki_artikel,
    }


@whitelist(allow_guest=False)
def get_untergruppe_detail(untergruppe_id):
    """Gibt Details einer Untergruppe inkl. Mitglieder zurück."""
    _require_gruppen_lesezugriff(
        "Untergruppe", untergruppe_id, "Untergruppe", "Untergruppenmitgliedschaft"
    )

    ug = get_doc("Untergruppe", untergruppe_id)
    if not ug:
        throw("Untergruppe nicht gefunden.", DoesNotExistError)

    mitglieder = _mitglieder_der_gruppe("Untergruppe", untergruppe_id)

    aufgaben_ug = _get_gruppen_inhalte(
        "Gruppen Aufgabe",
        filters={"untergruppe": untergruppe_id},
        fields=["name", "titel", "erledigt", "faellig"],
        order_by="erledigt asc, creation asc",
    )
    ankuendigungen_ug = _get_gruppen_inhalte(
        "Gruppen Ankuendigung",
        filters={"untergruppe": untergruppe_id},
        fields=["name", "titel", "text", "pinned", "creation"],
        order_by="pinned desc, creation desc",
    )

    # Prüfe ob aktueller User Mitglied ist (für Frontend-Logik)
    current_mitglied_id = _mitglied_id_des_users()
    is_member = bool(_db.exists(
        "Untergruppenmitgliedschaft",
        {"parent": untergruppe_id, "mitglied": current_mitglied_id},
    )) if current_mitglied_id else False

    return {
        "success": True,
        "is_member": is_member,
        "untergruppe": {
            "name": ug.name,
            "untergruppenname": ug.untergruppenname,
            "gruppe": ug.gruppe,
            # UXD-R25: Obergruppe als Anzeigename, nicht als rohe ID.
            "gruppe_name": (
                get_value("Gruppe", ug.gruppe, "gruppenname") or ug.gruppe
            ) if ug.gruppe else "",
            "status": ug.status,
            "sichtbarkeit": ug.sichtbarkeit,
            "beschreibung": ug.beschreibung,
            "treffpunkt": ug.treffpunkt,
            "treffzeit": ug.treffzeit,
            "bild": ug.bild,
        },
        "mitglieder": mitglieder,
        "aufgaben": aufgaben_ug,
        "ankuendigungen": ankuendigungen_ug,
    }


# ── Mitgliedschaft schreiben ────────────────────────────────────────────────


def _dienstbereich_der_gruppe(doctype: str, gruppe_id: str) -> str | None:
    """Dienstbereich der Gruppe bzw. der zugehoerigen Obergruppe (W1).

    `Untergruppe` hat keine eigene Spalte `dienstbereich` (models/diakonos.py);
    ein `get_value("Untergruppe", id, "dienstbereich")` lief deshalb in einen
    `KeyError` und der Rechtepfad endete als HTTP 500 statt als 403. Der
    Dienstbereich einer Untergruppe ist der ihrer Obergruppe.
    """
    if doctype == "Untergruppe":
        obergruppe = get_value("Untergruppe", gruppe_id, "gruppe")
        return str(get_value("Gruppe", obergruppe, "dienstbereich") or "") or None if obergruppe else None
    return str(get_value("Gruppe", gruppe_id, "dienstbereich") or "") or None


def _darf_gruppe_verwalten(doctype: str, gruppe_id: str) -> bool:
    """BF1-E: Darf der Aufruf diese Gruppe verwalten?

    Admin (Rollen-Kurzschluss von `check_permission`), Verantwortlicher der
    Gruppe/Untergruppe oder Verantwortlicher des Dienstbereichs oberhalb. Genau
    die Personen, die in der SPA `canManage` sehen — die Pruefung kommt aber
    vom Server, nicht aus der Anzeige.
    """
    if check_permission(doctype, gruppe_id, "write").get("allowed"):
        return True
    if _is_verantwortlicher_in(f"Untergruppe Verantwortlicher" if doctype == "Untergruppe"
                               else "Gruppe Verantwortlicher", gruppe_id):
        return True
    # Ein Dienstbereich oberhalb kann die Gruppe verantworten.
    dienstbereich = _dienstbereich_der_gruppe(doctype, gruppe_id)
    return bool(
        dienstbereich and _is_verantwortlicher_in("Dienstbereich Verantwortlicher", dienstbereich)
    )


@whitelist(allow_guest=False)
def get_gruppe_mitglieder_auswahl(gruppe_id, suche="", limit=0, is_untergruppe=False):
    """BF1-E: Auswahlliste aller Mitglieder fuer "Mitglieder hinzufuegen".

    Liefert ALLE Mitglieder (nicht nur die der Gruppe — sonst ist ein neues
    Mitglied nicht auswaehlbar), dazu `in_gruppe` als Hinweis fuer die SPA.

    B-1 (Datenschutz, Regel B2): Geliefert werden NUR `mitglied`, `name` und
    `in_gruppe`. E-Mail und Status sind KEINE Felder dieser Auswahl: die
    E-Mail ist ein Adressbuch-Feld (`adressbuch_sichtbarkeit`) und darf einem
    Gruppenverantwortlichen nicht ungemaskt gezeigt werden — die
    Verwalterrolle ist keine Freigabe (siehe `frappe_compat/mitglied_sichtbarkeit.py`
    Kopf). Genauso ist die E-Mail kein Suchfeld (sonst waere die Suche ein
    Seitenkanal genau auf die E-Mail, die `get_mitglieder_liste` abschneidet).
    Gesucht wird ausschliesslich in Vor-/Nachname, umlaut- und
    gross-klein-unabhaengig (BF1-J).

    B-2: Der Aufruf schneidet NICHT bei 50 ab. Der Standard ist unbegrenzt
    (`limit=0`); die SPA tippt den Suchbegriff an den Server und laesst dort
    filtern. Ein gesetztes `limit` wird auf einen sinnvollen Bereich begrenzt.

    Deckt B-1, B-2, K6 ab.
    """
    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    # K6: Rechte-pruefung VOR der Existenz-pruefung. Umgekehrt unterschied die
    # Antwort „nicht gefunden“ von „verboten“ und verriet einem Unberechtigten
    # damit, welche Gruppen es gibt. `_darf_gruppe_verwalten` verweigert bei
    # unbekannter Gruppe (check_permission findet nichts -> nicht erlaubt),
    # also ist „verboten“ die Antwort auf beide Faelle (fail closed).
    if not _darf_gruppe_verwalten(doctype, gruppe_id):
        throw("Keine Berechtigung fuer diese Gruppe.", FrappePermissionError)
    if get_value(doctype, gruppe_id, "name") is None:
        throw(f"{doctype} nicht gefunden.", DoesNotExistError)

    try:
        grenze = int(limit or 0)
    except (TypeError, ValueError):
        grenze = 0
    # `limit=0` (Vorgabe) -> keine Abschneidung. Ein negatives oder
    # unsinniges Limit faellt auf die Vorgabe zurueck, nie auf einen Fehler.
    if grenze < 0:
        grenze = 0
    if grenze > 2000:
        grenze = 2000

    # Bereits enthaltene Mitglieder (zur Kennzeichnung in der SPA).
    in_gruppe = {
        str(row.get("mitglied"))
        for row in _child_rows(_MITGLIEDSCHAFT[doctype], gruppe_id, "mitglieder")
        if row.get("mitglied")
    }

    # Alle waehlbaren Mitglieder. Kein E-Mail-, kein Statusfeld (B-1) und
    # keine Ausgetretenen/Verstorbenen — die Liste bietet nur Menschen an,
    # die tatsaechlich aufgenommen werden koennen.
    from diakronos_app.api.gruppen_auswahl import waehlbare_mitglieder

    alle = waehlbare_mitglieder(suche=suche, limit=grenze)

    ergebnis: list[dict[str, Any]] = [
        {
            "mitglied": m["mitglied"],
            "name": m["name"],
            "in_gruppe": m["mitglied"] in in_gruppe,
        }
        for m in alle
    ]
    return ergebnis


@whitelist(allow_guest=False)
def add_mitglied_to_gruppe(gruppe_id, mitglied_id, rolle="", is_untergruppe=False):
    """Fügt Mitglied zu Gruppe/Untergruppe hinzu.

    W2: Dieselbe Rechtepruefung wie `remove_mitglied_from_gruppe` und
    `update_mitglied_rolle` — wer aufnehmen darf, darf auch wieder entfernen
    und die Rolle aendern. Sonst kann ein Gruppenverantwortlicher einen
    Fehlgriff nicht zuruecknehmen, obwohl die SPA ihm genau diese drei
    Bedienelemente zeigt (Hinzufuegen, Rolle, Entfernen).
    """
    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    _require(_darf_gruppe_verwalten(doctype, gruppe_id), "Keine Berechtigung zum Bearbeiten.")

    # BLD-R4: Ohne Existenzpruefung entstand bei einer falschen/veralteten
    # Gruppen-ID eine verwaiste Gruppenmitgliedschaft (HTTP 200). Genau die
    # Kindtabelle hat keinen Fremdschluessel. Fail closed statt stiller Muell.
    if get_value(doctype, gruppe_id, "name") is None:
        throw(f"{doctype} nicht gefunden.", DoesNotExistError)

    child = _MITGLIEDSCHAFT[doctype]
    # Prüfen, ob Mitglied bereits vorhanden
    if _db.exists(child, {"parent": gruppe_id, "mitglied": mitglied_id}):
        return {"success": False, "message": "Mitglied ist bereits in der Gruppe."}

    _child_insert(child, gruppe_id, "mitglieder", {
        "mitglied": mitglied_id,
        "rolle": rolle,
        "status": "Aktiv",
        "beitrittsdatum": _today(),
    })

    return {"success": True, "message": "Mitglied hinzugefügt."}


@whitelist(allow_guest=False)
def remove_mitglied_from_gruppe(gruppe_id, mitglied_id, is_untergruppe=False):
    """Entfernt Mitglied aus Gruppe/Untergruppe (W2: gleiche Rechte wie add)."""
    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    _require(_darf_gruppe_verwalten(doctype, gruppe_id), "Keine Berechtigung zum Bearbeiten.")

    child = _MITGLIEDSCHAFT[doctype]
    entfernt = _child_delete(
        child, gruppe_id, "mitglieder", {"mitglied": mitglied_id}
    )
    if not entfernt:
        return {"success": False, "message": "Mitglied nicht in der Gruppe gefunden."}

    return {"success": True, "message": "Mitglied entfernt."}


@whitelist(allow_guest=False)
def update_mitglied_rolle(gruppe_id, mitglied_id, rolle, is_untergruppe=False):
    """Ändert Rolle eines Mitglieds in einer Gruppe (W2: gleiche Rechte wie add)."""
    doctype = "Untergruppe" if is_untergruppe else "Gruppe"
    _require(_darf_gruppe_verwalten(doctype, gruppe_id), "Keine Berechtigung zum Bearbeiten.")

    from diakronos_app.db import SessionLocal

    child = _MITGLIEDSCHAFT[doctype]
    model = model_for(child)

    sess = SessionLocal()
    try:
        rows = sess.query(model).filter(
            model.parent == gruppe_id,
            model.parentfield == "mitglieder",
            model.mitglied == mitglied_id,
        ).all()
        if not rows:
            return {"success": False, "message": "Mitglied nicht gefunden."}
        for row in rows:
            row.rolle = rolle
            row.modified = _now()
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()

    return {"success": True, "message": "Rolle aktualisiert."}


# ── Helpers ─────────────────────────────────────────────────────────────────


def _has_group_access(group_doc, user_path):
    """Prüft, ob User Zugriff auf eine Gruppe/Untergruppe hat."""
    if not user_path or user_path == "|":
        return False
    group_path = group_doc.get("ancestor_path", "|")
    if not group_path or group_path == "|":
        # Leerer Zielpfad begruendet keinen Zugriff (fail closed).
        return False
    return _paths_overlap(user_path, group_path)


# ── Orgchart ────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_gruppen_for_orgchart():
    """Gibt Dienstbereiche, Gruppen und Untergruppen als flaches Array für d3-org-chart zurück."""
    gruppen_result = get_gruppen_hierarchie()
    gruppen_list = gruppen_result.get("gruppen", [])

    dienstbereiche = get_all(
        "Dienstbereich",
        fields=["name", "ministry", "farbe", "icon", "beschreibung"],
        order_by="sortierung asc, ministry asc",
    )

    untergruppen = get_all(
        "Untergruppe",
        fields=["name", "untergruppenname", "gruppe", "status", "beschreibung"],
        filters={"status": ["!=", "Archiviert"]},
        order_by="untergruppenname asc",
    )

    if not _is_admin():
        dienstbereiche = [
            d for d in dienstbereiche
            if check_permission("Dienstbereich", d["name"], "read").get("allowed")
        ]
        allowed_untergruppen = {u["name"] for g in gruppen_list for u in g["untergruppen"]}
        untergruppen = [u for u in untergruppen if u["name"] in allowed_untergruppen]

    ug_counts = {
        u["name"]: _count("Untergruppenmitgliedschaft", u["name"]) for u in untergruppen
    }

    nodes = [{"id": "virtual-root", "parentId": None, "name": "", "type": "root"}]

    db_names = {d["name"] for d in dienstbereiche}
    for d in dienstbereiche:
        nodes.append({
            "id": f"db_{d['name']}",
            "parentId": "virtual-root",
            "name": d["ministry"],
            "type": "dienstbereich",
            "raw_name": d["name"],
            # UXD-R28/DES-04: auch Bestandsdaten durch die Pruefung — ein
            # Alt-Wert wie "zzz-keine-farbe" kommt so nie in einen
            # style-String der Oberflaeche.
            "farbe": _normalisiere_farbe(d.get("farbe")),
            "icon": d.get("icon") or "",
            "beschreibung": d.get("beschreibung") or "",
        })

    gruppe_extra = {
        g["name"]: g
        for g in get_all("Gruppe", fields=["name", "treffpunkt", "treffzeit"])
    }

    gruppe_names = set()
    for g in gruppen_list:
        if not g.get("dienstbereich") or g["dienstbereich"] not in db_names:
            continue
        gruppe_names.add(g["name"])
        extra = gruppe_extra.get(g["name"], {})
        nodes.append({
            "id": f"g_{g['name']}",
            "parentId": f"db_{g['dienstbereich']}",
            "name": g["gruppenname"],
            "type": "gruppe",
            "raw_name": g["name"],
            "mitglieder_count": g.get("mitglieder_count", 0),
            "beschreibung": g.get("beschreibung") or "",
            "treffpunkt": extra.get("treffpunkt") or "",
            "treffzeit": extra.get("treffzeit") or "",
        })

    ug_extra = {
        u["name"]: u
        for u in get_all("Untergruppe", fields=["name", "treffpunkt", "treffzeit"])
    }

    for u in untergruppen:
        if not u.get("gruppe") or u["gruppe"] not in gruppe_names:
            continue
        extra = ug_extra.get(u["name"], {})
        nodes.append({
            "id": f"ug_{u['name']}",
            "parentId": f"g_{u['gruppe']}",
            "name": u["untergruppenname"],
            "type": "untergruppe",
            "raw_name": u["name"],
            "mitglieder_count": ug_counts.get(u["name"], 0),
            "beschreibung": u.get("beschreibung") or "",
            "treffpunkt": extra.get("treffpunkt") or "",
            "treffzeit": extra.get("treffzeit") or "",
        })

    return {"success": True, "nodes": nodes}


# ── Erstellen-Rechte ────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_user_create_permissions():
    """Gibt zurück, welche Strukturen der aktuelle User erstellen darf."""
    roles = get_roles()
    is_admin = any(r in roles for r in ADMIN_ROLES)

    result = {
        "can_create_dienstbereich": False,
        "can_create_gruppe": False,
        "can_create_untergruppe": False,
        "allowed_dienstbereiche": [],
        "allowed_gruppen": [],
    }

    if is_admin or "Gemeindeverantwortlicher" in roles:
        result["can_create_dienstbereich"] = True

    # Original: SELECT DISTINCT parent ... WHERE user = <user>
    db_verantwortlich = {
        r["parent"]
        for r in get_all(
            "Dienstbereich Verantwortlicher",
            filters={"user": session.user},
            fields=["parent"],
        )
    }
    if db_verantwortlich or is_admin:
        result["can_create_gruppe"] = True
        result["allowed_dienstbereiche"] = sorted(db_verantwortlich)

    g_verantwortlich = {
        r["parent"]
        for r in get_all(
            "Gruppe Verantwortlicher",
            filters={"user": session.user},
            fields=["parent"],
        )
    }
    if g_verantwortlich or is_admin:
        result["can_create_untergruppe"] = True
        result["allowed_gruppen"] = sorted(g_verantwortlich)

    result["can_create_any"] = any([
        result["can_create_dienstbereich"],
        result["can_create_gruppe"],
        result["can_create_untergruppe"],
    ])

    # OP-ADMIN-5/UXD-R4: welche Objekte darf der Aufruf umbenennen? Die SPA
    # blendet danach die Stifte ein; die eigentliche Pruefung bleibt im Server
    # (update_gruppe/update_untergruppe/update_dienstbereich). Ausgeliefert
    # werden ROHE Namen (ohne Orgchart-Praefix db_/g_/ug_), damit die SPA sie
    # direkt als Parameter weitergeben kann.
    result["can_edit_ids"] = _editierbare_ids(is_admin)
    return result


def _editierbare_ids(is_admin: bool) -> list[str]:
    """Namen aller Dienstbereiche/Gruppen/Untergruppen, die der User aendern darf.

    Admin: alle. Sonst: die Dienstbereiche, die er verantwortet (samt deren
    Gruppen und Untergruppen) und die Gruppen/Untergruppen, die er direkt
    verantwortet. Genau die Personen, die `_darf_gruppe_verwalten` bzw. die
    Update-Pfade durchlassen — die Liste ist nur die Anzeige, nicht die Freigabe.
    """
    if is_admin:
        ids: list[str] = []
        ids += [d["name"] for d in get_all("Dienstbereich", fields=["name"])]
        ids += [g["name"] for g in get_all("Gruppe", fields=["name"])]
        ids += [u["name"] for u in get_all("Untergruppe", fields=["name"])]
        return sorted(set(ids))

    db_verantwortlich = {
        r["parent"]
        for r in get_all(
            "Dienstbereich Verantwortlicher",
            filters={"user": session.user},
            fields=["parent"],
        )
    }
    g_verantwortlich = {
        r["parent"]
        for r in get_all(
            "Gruppe Verantwortlicher",
            filters={"user": session.user},
            fields=["parent"],
        )
    }
    ug_verantwortlich = {
        r["parent"]
        for r in get_all(
            "Untergruppe Verantwortlicher",
            filters={"user": session.user},
            fields=["parent"],
        )
    }
    # Gruppen/Untergruppen unterhalb eines verantworteten Dienstbereichs sind
    # ebenfalls aenderbar (dieselbe Regel wie `_darf_gruppe_verwalten`).
    gruppen_unter_db = {
        g["name"]
        for g in get_all("Gruppe", fields=["name", "dienstbereich"])
        if g.get("dienstbereich") in db_verantwortlich
    }
    untergruppen_unter_db = {
        u["name"]
        for u in get_all("Untergruppe", fields=["name", "gruppe"])
        if u.get("gruppe") in (g_verantwortlich | gruppen_unter_db)
    }
    return sorted(
        db_verantwortlich | g_verantwortlich | ug_verantwortlich
        | gruppen_unter_db | untergruppen_unter_db
    )


# ── Anlegen ─────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def create_dienstbereich(name, beschreibung=None, farbe=None):
    """Erstellt einen neuen Dienstbereich. Nur für Gemeindeverantwortliche."""
    roles = get_roles()
    _require(
        any(r in roles for r in ["System Manager", "Mitgliederadministrator", "Gemeindeverantwortlicher"]),
        "Nur Gemeindeverantwortliche können Dienstbereiche erstellen.",
    )
    new_name = _create("Dienstbereich", {
        "ministry": name,
        "beschreibung": beschreibung or "",
        # UXD-R28: nur ein gueltiger Hex-Wert wird gespeichert; Klartext oder
        # CSS-Fragmente landen nie in der Datenbank.
        "farbe": _normalisiere_farbe(farbe),
    })
    return {"success": True, "name": new_name}


@whitelist(allow_guest=False)
def create_gruppe(name, dienstbereich, gruppentyp=None, beschreibung=None, treffpunkt=None, treffzeit=None):
    """Erstellt eine neue Gruppe. Nur für Dienstbereichsverantwortliche."""
    is_admin = _is_admin()
    if not is_admin:
        _require(
            _hat_dienstbereich_verantwortung(dienstbereich),
            "Du bist kein Verantwortlicher dieses Dienstbereichs.",
        )
    new_name = _create("Gruppe", {
        "gruppenname": name,
        "dienstbereich": dienstbereich,
        "gruppentyp": gruppentyp or None,
        "beschreibung": beschreibung or "",
        "treffpunkt": treffpunkt or "",
        "treffzeit": treffzeit or "",
        "status": "Aktiv",
    })
    return {"success": True, "name": new_name}


@whitelist(allow_guest=False)
def create_untergruppe(name, gruppe, beschreibung=None, treffpunkt=None, treffzeit=None):
    """Erstellt eine neue Untergruppe. Nur für Gruppenverantwortliche."""
    is_admin = _is_admin()
    if not is_admin:
        mitglied = _get_current_user_mitglied()
        _require(
            bool(mitglied) and _hat_gruppen_verantwortung(gruppe),
            "Du bist kein Verantwortlicher dieser Gruppe.",
        )
    new_name = _create("Untergruppe", {
        "untergruppenname": name,
        "gruppe": gruppe,
        "beschreibung": beschreibung or "",
        "treffpunkt": treffpunkt or "",
        "treffzeit": treffzeit or "",
        "status": "Aktiv",
    })
    return {"success": True, "name": new_name}


@whitelist(allow_guest=False)
def update_gruppe(name, gruppenname=None, beschreibung=None, treffpunkt=None, treffzeit=None):
    """Aktualisiert eine Gruppe. Verantwortliche oder uebergeordnete Admins."""
    is_admin = _is_admin()
    if not is_admin:
        gruppe = get_doc("Gruppe", name)
        is_db_verantwortlich = _hat_dienstbereich_verantwortung(gruppe.dienstbereich)
        is_g_verantwortlich = _hat_gruppen_verantwortung(name)
        _require(
            is_db_verantwortlich or is_g_verantwortlich,
            "Keine Berechtigung zum Bearbeiten dieser Gruppe.",
        )
    _update_doc("Gruppe", name, {
        "gruppenname": gruppenname,
        "beschreibung": beschreibung,
        "treffpunkt": treffpunkt,
        "treffzeit": treffzeit,
    })
    return {"success": True}


@whitelist(allow_guest=False)
def update_untergruppe(name, untergruppenname=None, beschreibung=None, treffpunkt=None, treffzeit=None):
    """Aktualisiert eine Untergruppe."""
    is_admin = _is_admin()
    if not is_admin:
        ug = get_doc("Untergruppe", name)
        is_g_verantwortlich = _hat_gruppen_verantwortung(ug.gruppe)
        is_ug_verantwortlich = bool(_db.exists(
            "Untergruppe Verantwortlicher", {"parent": name, "user": session.user}
        ))
        _require(
            is_g_verantwortlich or is_ug_verantwortlich,
            "Keine Berechtigung zum Bearbeiten dieser Untergruppe.",
        )
    _update_doc("Untergruppe", name, {
        "untergruppenname": untergruppenname,
        "beschreibung": beschreibung,
        "treffpunkt": treffpunkt,
        "treffzeit": treffzeit,
    })
    return {"success": True}


@whitelist(allow_guest=False)
def update_dienstbereich(name, ministry=None, beschreibung=None, farbe=None):
    """Aktualisiert einen Dienstbereich. Nur für Gemeindeverantwortliche.

    UXD-R4/OP-ADMIN-5: Im Altcode gab es diese Funktion nicht (die SPA rief
    `diakronos.diakonos.api.gruppen.update_dienstbereich` und bekam 404). Hier
    portiert, damit Dienstbereiche in der Oberfläche umbenannt und gefärbt
    werden können. Rechte wie `create_dienstbereich`; zusätzlich darf der
    verantwortete Dienstbereich geändert werden.
    """
    roles = get_roles()
    _require(
        any(r in roles for r in ["System Manager", "Mitgliederadministrator", "Gemeindeverantwortlicher"])
        or _hat_dienstbereich_verantwortung(name),
        "Keine Berechtigung zum Bearbeiten dieses Dienstbereichs.",
    )
    if get_value("Dienstbereich", name, "name") is None:
        throw("Dienstbereich nicht gefunden.", DoesNotExistError)
    werte: dict[str, Any] = {"ministry": ministry, "beschreibung": beschreibung}
    # Nur setzen, wenn eine Farbe mitkam: `_normalisiere_farbe` liefert sonst
    # den Standardwert und wuerde eine bereits gesetzte Farbe ueberschreiben.
    if farbe is not None:
        werte["farbe"] = _normalisiere_farbe(farbe)
    _update_doc("Dienstbereich", name, werte)
    return {"success": True}


@whitelist(allow_guest=False)
def get_gruppe_termine(gruppe_id, tage=60):
    """UXD-R10: Die nächsten Termine einer Gruppe (oder Untergruppe).

    Der Endpunkt der SPA rief vorher `kalender.get_events(gruppe, limit,
    future_only)` auf — dessen Signatur verlangt `start_date`/`end_date`, die
    Abfrage scheiterte bei jedem Laden mit HTTP 417. Hier der passende Aufruf:
    Termine von heute bis +`tage` Tage, gefiltert auf `Element.gruppe`.

    Rechte: derselbe Lesezugriff wie `get_gruppe_detail` — wer die Gruppe nicht
    sehen darf, bekommt auch ihre Termine nicht. Die Kalender-Sichtbarkeit
    (`get_accessible_calendars`) wird zusätzlich angewandt, damit keine Termine
    gesperrter Kalender durchsickern. Status wie in der regulären Terminabfrage
    (P0-3): moderierte Kalender liefern alle Status, sonst nur `Festgelegt`
    oder der eigene Vorschlag.
    """
    from datetime import timedelta

    # Gruppe oder Untergruppe? Beide tragen in `Element.gruppe` ihren Namen.
    is_ug = get_value("Untergruppe", gruppe_id, "name") is not None
    if is_ug:
        _require_gruppen_lesezugriff(
            "Untergruppe", gruppe_id, "Untergruppe", "Untergruppenmitgliedschaft"
        )
    else:
        _require_gruppen_lesezugriff("Gruppe", gruppe_id, "Gruppe", "Gruppenmitgliedschaft")

    try:
        tage_int = max(1, min(int(tage or 60), 366))
    except (TypeError, ValueError):
        tage_int = 60

    start = date.today()
    ende = start + timedelta(days=tage_int)
    fenster_start = f"{start.isoformat()} 00:00:00"
    fenster_ende = f"{ende.isoformat()} 23:59:59"

    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    kalender_info = get_accessible_calendars()
    kalender = [c["name"] for c in kalender_info if isinstance(c, dict) and "name" in c]
    if not kalender:
        return {"success": True, "termine": []}

    mod_kalender = [
        c["name"] for c in kalender_info
        if isinstance(c, dict) and c.get("is_moderator")
    ]

    def _hole(cal_names, *, alle_status: bool):
        if not cal_names:
            return []
        # P0-3/B2: Zeitfenster wie in calendar_get — ein Termin gehoert dazu,
        # wenn er das Fenster beruehrt (Ende >= Fensteranfang); die Obermenge
        # holt `element_start <= Fensterende`.
        filters: dict[str, Any] = {
            "gruppe": gruppe_id,
            "element_start": ["<=", fenster_ende],
            "element_calendar": ["in", cal_names],
        }
        or_filters = [
            ["element_end", ">=", fenster_start],
            ["element_start", ">=", fenster_start],
        ]
        rows = get_all(
            "Element",
            filters=filters,
            or_filters=or_filters,
            fields=[
                "name", "element_name", "element_start", "element_end",
                "status", "description", "element_calendar", "owner",
            ],
            order_by="element_start asc",
            limit_page_length=50,
        ) or []
        # P0-3/B2: Statusfilter hier in Python statt in SQL, damit ein eigener
        # Vorschlag nicht schon von der Abfrage verworfen wird. Moderierte
        # Kalender liefern alle Status AUSSER `Abgelehnt` (W-A); sonst nur
        # `Festgelegt` oder der eigene (nicht abgelehnte) Vorschlag.
        if alle_status:
            return [r for r in rows if (r.get("status") or "") != "Abgelehnt"]
        return [
            r for r in rows
            if (r.get("status") or "") != "Abgelehnt"
            and (r.get("status") == "Festgelegt" or r.get("owner") == session.user)
        ]

    # P0-3/B2: Nicht-Moderatoren sehen im fremden Kalender nur `Festgelegt`;
    # im eigenen/moderierten Kalender auch die eigenen Vorschlaege.
    rows: list[dict] = []
    rows.extend(_hole(mod_kalender, alle_status=True))
    regulaer = [n for n in kalender if n not in set(mod_kalender)]
    rows.extend(_hole(regulaer, alle_status=False))

    gesehen: set[str] = set()
    termine = []
    for r in rows:
        name = r.get("name")
        if name in gesehen:
            continue
        gesehen.add(name)
        termine.append(
            {
                "name": name,
                "titel": r.get("element_name") or name,
                "start": r.get("element_start"),
                "ende": r.get("element_end"),
                "status": r.get("status"),
            }
        )
    return {"success": True, "termine": termine}


# ── Gruppenseite ────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_gruppen_page_data():
    roles = get_roles()
    is_admin = any(r in roles for r in ADMIN_ROLES)
    mitglied_name = get_value("Mitglied", {"user": session.user}, "name")
    verantwortlich = get_all(
        "Gruppe Verantwortlicher",
        filters={"user": session.user},
        fields=["parent"],
    )
    verantwortlich_names = {r["parent"] for r in verantwortlich}
    member_names = set()
    if mitglied_name:
        rows = get_all(
            "Gruppenmitgliedschaft",
            filters={"mitglied": mitglied_name, "status": "Aktiv"},
            fields=["parent"],
        )
        member_names = {r["parent"] for r in rows}
    my_groups = verantwortlich_names | member_names

    def g_dict(g, ist_verantwortlich=False, ist_meins=False):
        db_name, db_farbe = "", "#667eea"
        if g.get("dienstbereich"):
            d = get_value(
                "Dienstbereich", g["dienstbereich"], ["ministry", "farbe"], as_dict=True
            ) or {}
            db_name = d.get("ministry") or ""
            # DES-04: kein Rohwert aus der API in einen style-String —
            # auch Bestandsdaten laufen durch die Pruefung.
            db_farbe = _normalisiere_farbe(d.get("farbe"))
        typ_name = ""
        if g.get("gruppentyp"):
            typ_name = get_value("Gruppentyp", g["gruppentyp"], "typname") or ""
        count = _count("Gruppenmitgliedschaft", g["name"])
        return {
            "name": g["name"], "gruppenname": g["gruppenname"],
            "dienstbereich_name": db_name, "dienstbereich_farbe": db_farbe,
            "gruppentyp_name": typ_name, "bild": g.get("bild") or "",
            "mitglieder_count": count,
            "ist_verantwortlich": ist_verantwortlich, "ist_meins": ist_meins,
        }

    meine_gruppen = []
    filters: dict[str, Any] = {"status": "Aktiv"}
    # OP-ADMIN-6: „Meine Gruppen" sind die Gruppen, in denen der Aufruf
    # tatsächlich Mitglied oder Verantwortlicher ist. Vorher füllte der
    # Admin-Zweig hier ALLE Gruppen ein — „Meine Gruppen 13" = „Alle 13".
    if my_groups:
        filters["name"] = ["in", list(my_groups)]
    else:
        filters["name"] = ["in", []]
    for g in get_all(
        "Gruppe", filters=filters,
        fields=["name", "gruppenname", "dienstbereich", "gruppentyp", "bild"],
    ):
        meine_gruppen.append(g_dict(
            g,
            ist_verantwortlich=g["name"] in verantwortlich_names,
            ist_meins=True,
        ))

    typen = []
    for typ in get_all("Gruppentyp", fields=["name", "typname", "bild", "farbe"]):
        gruppen = []
        for g in get_all(
            "Gruppe",
            filters={"gruppentyp": typ["name"], "status": "Aktiv"},
            fields=["name", "gruppenname", "dienstbereich", "bild", "sichtbarkeit"],
        ):
            if g["sichtbarkeit"] == "Versteckt":
                continue
            if g["sichtbarkeit"] == "Intern" and g["name"] not in my_groups and not is_admin:
                continue
            gruppen.append(g_dict(g, ist_meins=g["name"] in my_groups))
        typen.append({
            "name": typ["name"], "typname": typ["typname"],
            "bild": typ.get("bild") or "", "farbe": _normalisiere_farbe(typ.get("farbe")),
            "gruppen": gruppen, "gruppen_count": len(gruppen),
        })

    # Alle Gruppen (nur für Admins) — Gruppen wo Admin KEIN Mitglied/Verantwortlicher ist
    andere_gruppen_by_db = []
    if is_admin:
        # Dienstbereiche für Sortierung laden
        db_info_map = {}
        for db_doc in get_all(
            "Dienstbereich", fields=["name", "ministry", "farbe"],
            order_by="sortierung asc, ministry asc",
        ):
            db_info_map[db_doc["name"]] = db_doc

        alle_gruppen_raw = get_all(
            "Gruppe",
            filters={"status": "Aktiv"},
            fields=["name", "gruppenname", "dienstbereich", "gruppentyp", "bild"],
            order_by="gruppenname asc",
        )
        # Nur Gruppen wo Admin kein Mitglied/Verantwortlicher ist
        andere_raw = [g for g in alle_gruppen_raw if g["name"] not in my_groups]

        # Nach Dienstbereich gruppieren
        by_db: dict[str, dict[str, Any]] = {}
        for g in andere_raw:
            db_key = g.get("dienstbereich") or "__kein_db__"
            if db_key not in by_db:
                db_meta = db_info_map.get(db_key, {})
                by_db[db_key] = {
                    "dienstbereich": db_key,
                    "dienstbereich_name": db_meta.get("ministry") or db_key,
                    "dienstbereich_farbe": _normalisiere_farbe(db_meta.get("farbe")),
                    "gruppen": [],
                }
            by_db[db_key]["gruppen"].append(g_dict(g, ist_meins=False))

        # Sortiert nach Dienstbereich-Name ausgeben
        andere_gruppen_by_db = sorted(by_db.values(), key=lambda x: x["dienstbereich_name"])

    # B5/OP-ADMIN-6: Auswahllisten nur fuer Nutzer mit Anlege-Rechten. Vorher
    # bekam jeder Nutzer alle Dienstbereich-/Gruppennamen zu sehen — auch nicht
    # sichtbare (privat). Wer gar nichts anlegen darf, braucht die Liste nicht;
    # wer anlegen darf, bekommt die vollstaendige Auswahl (der Server prueft die
    # konkrete Auswahl ohnehin beim Anlegen nach).
    create_perms = get_user_create_permissions()
    dienstbereich_auswahl: list[dict[str, Any]] = []
    gruppen_auswahl: list[dict[str, Any]] = []
    if create_perms.get("can_create_any"):
        dienstbereich_auswahl = [
            {"name": d["name"], "ministry": d.get("ministry") or d["name"]}
            for d in get_all("Dienstbereich", fields=["name", "ministry"],
                             order_by="sortierung asc, ministry asc")
        ]
        gruppen_auswahl = [
            {"name": g["name"], "gruppenname": g.get("gruppenname") or g["name"]}
            for g in get_all("Gruppe", fields=["name", "gruppenname"],
                             filters={"status": "Aktiv"}, order_by="gruppenname asc")
        ]

    return {
        "meine_gruppen": meine_gruppen, "gruppentypen": typen,
        "andere_gruppen": andere_gruppen_by_db, "is_admin": is_admin,
        # OP-ADMIN-6: was darf hier angelegt werden und in welcher Auswahl.
        "create_permissions": create_perms,
        "dienstbereich_auswahl": dienstbereich_auswahl,
        "gruppen_auswahl": gruppen_auswahl,
    }


# ── Aufgaben ────────────────────────────────────────────────────────────────


def _require_inhalte_zugriff(gruppe_id=None, untergruppe_id=None, *, write=False):
    """Elternrechte statt ungeschuetzter Aufgaben-/Ankuendigungs-IDs (B4).

    Lesen wie die Detail-API; Schreiben wie update_gruppe/update_untergruppe,
    ausschliesslich ueber die vorhandenen Permission-/Verantwortungshelfer.
    Beide Links muessen zusammenpassen, damit keine fremde Gruppe ueber eine
    erlaubte Untergruppe beschrieben werden kann. Verwaiste Ziele: fail closed.
    """
    message = "Keine Berechtigung zum Zugriff auf Gruppeninhalte."
    if untergruppe_id:
        ug = get_value("Untergruppe", untergruppe_id, ["name", "gruppe"], as_dict=True)
        _require(bool(ug) and bool(ug.get("gruppe")), message)
        _require(not gruppe_id or gruppe_id == ug["gruppe"], message)
        parent_gruppe = ug["gruppe"]
        doctype, name, child = "Untergruppe", untergruppe_id, "Untergruppenmitgliedschaft"
    else:
        _require(bool(gruppe_id), message)
        parent_gruppe = gruppe_id
        doctype, name, child = "Gruppe", gruppe_id, "Gruppenmitgliedschaft"
    gruppe = get_value("Gruppe", parent_gruppe, ["name", "dienstbereich"], as_dict=True)
    _require(bool(gruppe), message)
    if write:
        allowed = check_permission(doctype, name, "write").get("allowed")
        allowed = allowed or ist_verantwortlich_fuer(gruppe.get("dienstbereich"), parent_gruppe)
        if untergruppe_id:
            allowed = allowed or _is_verantwortlicher_in("Untergruppe Verantwortlicher", untergruppe_id)
        _require(bool(allowed), message)
    else:
        _require_gruppen_lesezugriff(doctype, name, doctype, child)


def _get_gruppen_inhalte(doctype, *, filters, fields, order_by):
    """Auch historische Doppel-/Fremdlinks vor der Auslieferung pruefen.

    Die Zusatzfelder bleiben intern; SPA-Felder und Sortierung bleiben gleich.
    """
    rows = get_all(doctype, filters=filters, fields=[*fields, "gruppe", "untergruppe"], order_by=order_by)
    result = []
    for row in rows:
        try:
            _require_inhalte_zugriff(row.get("gruppe"), row.get("untergruppe"))
        except FrappePermissionError:
            continue
        result.append({field: row.get(field) for field in fields})
    return result


@whitelist(allow_guest=False)
def get_aufgaben(gruppe_id=None, untergruppe_id=None):
    filters = {}
    if untergruppe_id:
        filters["untergruppe"] = untergruppe_id
    elif gruppe_id:
        filters["gruppe"] = gruppe_id
    else:
        throw("gruppe_id oder untergruppe_id erforderlich")
    _require_inhalte_zugriff(gruppe_id, untergruppe_id)
    items = _get_gruppen_inhalte(
        "Gruppen Aufgabe",
        filters=filters,
        fields=["name", "titel", "erledigt", "faellig", "erstellt_von"],
        order_by="erledigt asc, creation asc",
    )
    return {"success": True, "data": items}


@whitelist(allow_guest=False)
def create_aufgabe(titel, gruppe_id=None, untergruppe_id=None, faellig=None):
    _require_inhalte_zugriff(gruppe_id, untergruppe_id, write=True)
    mid = _mitglied_id_des_users()
    new_name = _create("Gruppen Aufgabe", {
        "titel": titel,
        "gruppe": gruppe_id or None,
        "untergruppe": untergruppe_id or None,
        "faellig": faellig or None,
        "erstellt_von": mid,
        "erledigt": False,
    })
    return {"success": True, "name": new_name}


@whitelist(allow_guest=False)
def toggle_aufgabe(aufgabe_id):
    # Unbekannte und fremde IDs liefern dieselbe 403, auch im Fehlerbody.
    doc = get_value("Gruppen Aufgabe", aufgabe_id,
                    ["gruppe", "untergruppe", "erledigt"], as_dict=True)
    _require(bool(doc), "Keine Berechtigung zum Zugriff auf Gruppeninhalte.")
    _require_inhalte_zugriff(doc.get("gruppe"), doc.get("untergruppe"), write=True)
    neuer_wert = 0 if doc.get("erledigt") else 1
    _update_doc("Gruppen Aufgabe", aufgabe_id, {"erledigt": bool(neuer_wert)})
    return {"success": True, "erledigt": neuer_wert}


# ── Ankündigungen ───────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_ankuendigungen(gruppe_id=None, untergruppe_id=None):
    filters = {}
    if untergruppe_id:
        filters["untergruppe"] = untergruppe_id
    elif gruppe_id:
        filters["gruppe"] = gruppe_id
    else:
        throw("gruppe_id oder untergruppe_id erforderlich")
    _require_inhalte_zugriff(gruppe_id, untergruppe_id)
    items = _get_gruppen_inhalte(
        "Gruppen Ankuendigung",
        filters=filters,
        fields=["name", "titel", "text", "erstellt_von", "pinned", "creation"],
        order_by="pinned desc, creation desc",
    )
    return {"success": True, "data": items}


@whitelist(allow_guest=False)
def create_ankuendigung(titel, text="", gruppe_id=None, untergruppe_id=None):
    _require_inhalte_zugriff(gruppe_id, untergruppe_id, write=True)
    mid = _mitglied_id_des_users()
    new_name = _create("Gruppen Ankuendigung", {
        "titel": titel,
        "text": text,
        "gruppe": gruppe_id or None,
        "untergruppe": untergruppe_id or None,
        "erstellt_von": mid,
    })
    return {"success": True, "name": new_name}


# ── Registrierung (dotted paths wie im Altcode) ─────────────────────────────

_ENDPUNKTE = (
    get_gruppen_hierarchie,
    get_gruppe_detail,
    get_untergruppe_detail,
    add_mitglied_to_gruppe,
    remove_mitglied_from_gruppe,
    update_mitglied_rolle,
    get_gruppen_for_orgchart,
    get_user_create_permissions,
    create_dienstbereich,
    create_gruppe,
    create_untergruppe,
    update_gruppe,
    update_untergruppe,
    get_gruppen_page_data,
    get_aufgaben,
    create_aufgabe,
    toggle_aufgabe,
    get_ankuendigungen,
    create_ankuendigung,
)

for _fn in _ENDPUNKTE:
    frappe.whitelist(allow_guest=False)(_fn)

del _fn

__all__ = [f.__name__ for f in _ENDPUNKTE]
