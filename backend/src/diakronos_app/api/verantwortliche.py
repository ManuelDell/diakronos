"""P1-8 — Verantwortliche pflegbar machen (OP-CHOR-3 / OP-ADMIN-4).

DER BEFUND
----------
Die Rechte des Plan-Rahmens haengen an den *Verantwortlicher*-Kindtabellen
(`gruppe_verantwortlicher`, `untergruppe_verantwortlicher`,
`dienstbereich_verantwortlicher`, Feld `user` = Konto). Geschrieben hat sie
NIRGENDS ein Endpunkt — die vorhandenen Zeilen stammen aus dem Altimport. Eine
Chorleiterin konnte damit in der Oberflaeche nirgends zur Planerin gemacht
werden (OP-CHOR-3); die Rolle „Leiter" in der Mitgliedschaft ist nur ein
Etikett und gibt keine Rechte (OP-ADMIN-4).

Dieses Modul ist der EINE Schreibweg fuer Verantwortlichkeiten. Die
Rechtepruefung liegt bei der Anwendung, nicht in der Oberflaeche: wer einen
Dienstbereich verantwortet, darf dessen Gruppen und Untergruppen pflegen —
das ist dieselbe Staffelung wie in `api/gruppen.py::_darf_gruppe_verwalten`
und in `planrahmen/rechte.py::Rechte.bereich`.

Warum eine eigene Datei und nicht `gruppen.py`: Verantwortlichkeit ist eine
eigene Sache (Rechtequelle) und wird von Gruppen, Untergruppen UND
Dienstbereichen benutzt. Die drei Alt-Tabellen haben dieselbe Form; hier gibt
es dafuer genau eine Umsetzung statt dreier Kopien.
"""

from __future__ import annotations

from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    FrappeCompatError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.permissions import (
    _is_verantwortlicher_in,
    check_permission,
    get_roles,
    mitglied_ausgeschlossen as _mitglied_ausgeschlossen,
)
from diakronos_app.frappe_compat.permissions import GUEST
from diakronos_app.frappe_compat.query import get_all, get_value
from diakronos_app.frappe_compat.session import session

# Doctype -> Kindtabelle + Feld, in dem die Verantwortlichen stehen. Dieselbe
# Zuordnung wie in `api/gruppen.py::_VERANTWORTLICHER` — die Ziel-Doctypes der
# Oberflaeche sind Gruppe, Untergruppe und Dienstbereich.
_TABELLE = {
    "Gruppe": "Gruppe Verantwortlicher",
    "Untergruppe": "Untergruppe Verantwortlicher",
    "Dienstbereich": "Dienstbereich Verantwortlicher",
}

ADMIN_ROLES = ("System Manager", "Mitgliederadministrator")

# Nur diese Rollen sind in der Oberflaeche als „Zugang" vergebbar. Feste
# Diakronos-Liste (OP-ADMIN-2) — nicht die 71 geerbten ERPNext-Rollen.
ZUGANGS_ROLLEN = (
    "Mitglied",
    "Mitgliederadministrator",
    "Kalenderadministrator",
    "Ressourcenmoderator",
    "Tester",
)


def _require_admin() -> str:
    """Nur Administratoren. Der erste Administrator hat kein Mitglied."""
    user = str(session.user or "").strip()
    if not user or user == "Guest":
        throw("Anmeldung verweigert.", FrappePermissionError)
    if not any(r in get_roles(user) for r in ADMIN_ROLES):
        throw("Nur Administratoren dürfen das.", FrappePermissionError)
    return user


def _is_admin() -> bool:
    return any(r in get_roles() for r in ADMIN_ROLES)


def _dienstbereich_von(doctype: str, name: str) -> str | None:
    """Der Dienstbereich oberhalb einer Gruppe/Untergruppe (sonst None)."""
    if doctype == "Dienstbereich":
        return name
    if doctype == "Gruppe":
        wert = get_value("Gruppe", name, "dienstbereich")
        return str(wert) if wert else None
    # Untergruppe -> Gruppe -> Dienstbereich
    obergruppe = get_value("Untergruppe", name, "gruppe")
    if not obergruppe:
        return None
    wert = get_value("Gruppe", str(obergruppe), "dienstbereich")
    return str(wert) if wert else None


def _darf_verantwortliche_pflegen(doctype: str, name: str) -> bool:
    """Wer darf die Verantwortlichen von `name` setzen?

    Fail closed, in dieser Reihenfolge:
      * Administrator (Rollen-Kurzschluss).
      * Wer das Objekt selbst schreiben darf (`check_permission`).
      * Wer es bereits VERANTWORTET (eine bestehende Zeile in genau der
        Tabelle) — damit kann sich ein Verantwortlicher nicht selbst
        aussperren, indem er sich entfernt, aber weitere Verantwortliche
        aufnehmen.
      * Wer den Dienstbereich oberhalb verantwortet.

    Die Pruefung ist die einzige Wahrheit; die Oberflaeche blendet hoechstens
    aus, was hier ohnehin verweigert wird.
    """
    if _is_admin():
        return True
    if check_permission(doctype, name, "write").get("allowed"):
        return True
    if _is_verantwortlicher_in(_TABELLE[doctype], name):
        return True
    bereich = _dienstbereich_von(doctype, name)
    return bool(bereich and _is_verantwortlicher_in("Dienstbereich Verantwortlicher", bereich))


def _zeilen(doctype: str, name: str) -> list[dict[str, Any]]:
    """Verantwortlichen-Zeilen mit Anzeigenamen (nur Personen mit Konto).

    R-P1-8/W4: Der Kontoname ist oft die E-Mail. Nur wer die Verantwortlichen
    auch PFLEGEN darf (Admin bzw. bestehender/uebergeordneter Verantwortlicher),
    bekommt `user`/`mitglied`/`email`; alle anderen — jedes Mitglied, das die
    Gruppe sehen darf — erhalten ausschliesslich den Anzeigenamen. Vorher
    leakte die Liste Kontonamen (= E-Mail) an jeden mit Leserecht.
    """
    tabelle = _TABELLE[doctype]
    # AUSTRITT-b (B1): Anzeigenamen ueber die eine Regel (`personen_anzeige`).
    # AUSTRITT-d (NM1): EINE Sicht fuer die ganze Liste — vorher entstand sie
    # (samt `get_roles`) je Name.
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    sicht = PersonenSicht.aus()
    rows = get_all(
        tabelle,
        filters={"parent": name, "parentfield": "verantwortliche"},
        fields=["name", "user"],
        order_by="idx asc",
    ) or []
    voll = _darf_verantwortliche_pflegen(doctype, name)
    # Die Mitgliedszeilen aller Konten EINMAL lesen (vorher je Zeile eine Abfrage).
    konten = sorted({str(r.get("user") or "") for r in rows if r.get("user")})
    mitglieder = (get_all(
        "Mitglied",
        filters={"user": ["in", konten]},
        fields=["name", "vorname", "nachname", "user", "ausgeschlossen", "status",
                "austritt_datum"],
    ) or []) if konten else []
    je_konto: dict[str, dict[str, Any]] = {}
    for m in mitglieder:
        je_konto.setdefault(str(m.get("user") or ""), m)
    ergebnis: list[dict[str, Any]] = []
    for row in rows:
        user = str(row.get("user") or "")
        if not user:
            continue
        m = je_konto.get(user) or {}
        # AUSTRITT-b (B1): Anzeigename ueber die eine Regel — der Klarname
        # einer ausgetretenen Person geht hier sonst an jeden Leser.
        aus_mitglied = anzeigename(m, sicht=sicht) if m else ""
        anzeige = aus_mitglied or str(get_value("User", user, "full_name") or user)
        zeile: dict[str, Any] = {
            "name": row.get("name"),
            "anzeige": anzeige,
        }
        if voll:
            zeile["user"] = user
            zeile["mitglied"] = m.get("name")
            zeile["email"] = str(get_value("User", user, "email") or "") or None
        ergebnis.append(zeile)
    return ergebnis


def _konto_pruefen(user: str) -> str:
    """Der Verantwortliche muss ein AKTIVES KONTO haben (nicht nur ein Mitglied).

    Die Rechtepruefungen vergleichen gegen `session.user`; ein Mitglied ohne
    Login kann ein Recht gar nicht ausueben (OP-CHOR-3: „nur Personen mit
    Konto"). Fail closed statt einer Zeile, die nie wirkt.

    R-P1-8/W5: Guest, gesperrte (`enabled=False`) und ausgeschlossene Konten
    werden abgelehnt. Vorher liessen sich „Guest" und deaktivierte Konten als
    Verantwortliche eintragen — sie koennen das Recht nie ausueben und sind
    damit eine Attrappe; ein ausgeschlossenes Konto darf aus demselben Grund
    wie ueberall sonst keine Rechte bekommen.
    """
    wert = str(user or "").strip()
    if not wert:
        throw("Bitte eine Person wählen.", ValidationError)
    if wert == GUEST:
        throw("Der Benutzer „Guest“ kann keine Rechte erhalten.", ValidationError)
    if get_value("User", wert, "name") is None:
        throw("Diese Person hat kein Benutzerkonto und kann keine Rechte erhalten.",
              ValidationError)
    if not bool(get_value("User", wert, "enabled")):
        throw("Dieses Benutzerkonto ist gesperrt und kann keine Rechte erhalten.",
              ValidationError)
    if _mitglied_ausgeschlossen(wert):
        throw("Dieses Mitglied ist ausgeschlossen und kann keine Rechte erhalten.",
              ValidationError)
    return wert


def _naechster_idx(tabelle: str, parent: str) -> int:
    rows = get_all(
        tabelle,
        filters={"parent": parent, "parentfield": "verantwortliche"},
        fields=["idx"],
        order_by="idx desc",
        limit_page_length=1,
    ) or []
    try:
        return int(rows[0].get("idx") or 0) + 1
    except (TypeError, ValueError):
        return 1


@whitelist(allow_guest=False)
def get_verantwortliche(doctype: str, name: str) -> dict[str, Any]:
    """Verantwortliche eines Dienstbereichs/einer Gruppe/Untergruppe (Lesen).

    Lesen darf, wer das Objekt sehen darf; Schreiben regelt
    `set_verantwortliche`. Die Liste liefert fuer die Oberflaeche außerdem
    `darf_pflegen` — die Anzeige folgt damit dem Server, nicht umgekehrt.
    """
    doctype = str(doctype or "").strip()
    name = str(name or "").strip()
    if doctype not in _TABELLE:
        throw("Unbekannte Art: " + doctype, ValidationError)
    if not name or get_value(doctype, name, "name") is None:
        throw(f"{doctype} nicht gefunden.", DoesNotExistError)
    if not check_permission(doctype, name, "read").get("allowed") \
            and not _darf_verantwortliche_pflegen(doctype, name):
        throw("Keine Berechtigung für diese Angaben.", FrappePermissionError)
    return {
        "success": True,
        "verantwortliche": _zeilen(doctype, name),
        "darf_pflegen": _darf_verantwortliche_pflegen(doctype, name),
    }


@whitelist(allow_guest=False)
def set_verantwortliche(doctype: str, name: str, user: list[str] | None = None) -> dict[str, Any]:
    """Verantwortliche eines Objekts vollstaendig setzen (Liste von Konten).

    „Vollstaendig" heisst: die uebergebene Liste ERSETZT den Bestand — die
    Oberflaeche pflegt eine Auswahl und muss keinen Diff bilden (dasselbe
    Muster wie `anmeldung_setze_rollen_zuordnung`). Die Liste darf leer sein
    (alle Verantwortlichkeiten entziehen).

    Rechte: `_darf_verantwortliche_pflegen`. Jede Person muss ein Konto
    haben. Doppelte Eintraege werden entfernt, die Reihenfolge bleibt.
    """
    doctype = str(doctype or "").strip()
    name = str(name or "").strip()
    if doctype not in _TABELLE:
        throw("Unbekannte Art: " + doctype, ValidationError)
    if not name or get_value(doctype, name, "name") is None:
        throw(f"{doctype} nicht gefunden.", DoesNotExistError)
    if not _darf_verantwortliche_pflegen(doctype, name):
        throw("Keine Berechtigung, Verantwortliche zu ändern.", FrappePermissionError)

    if user is None:
        user = []
    if isinstance(user, str):
        import json

        try:
            user = json.loads(user)
        except (TypeError, ValueError):
            user = [user]
    if not isinstance(user, list):
        throw("user muss eine Liste sein.", ValidationError)

    konten: list[str] = []
    for eintrag in user:
        # Ein Eintrag darf ein Konto (String) oder eine Zeile mit `user` sein.
        wert = eintrag.get("user") if isinstance(eintrag, dict) else eintrag
        konto = _konto_pruefen(wert)
        if konto not in konten:
            konten.append(konto)

    # R-P1-8/W5: Wer NUR als bestehender Verantwortlicher pflegen darf (kein
    # Admin, kein Schreibrecht), darf sich nicht selbst entfernen — sonst
    # verliert er mit dem Speichern sein eigenes Pflegerecht. Ein Admin bzw.
    # Objektschreiber darf die Liste frei setzen.
    aufrufer = str(session.user or "")
    if not _is_admin() and not check_permission(doctype, name, "write").get("allowed"):
        if _is_verantwortlicher_in(_TABELLE[doctype], name) and aufrufer not in konten:
            throw(
                "Sie können sich nicht selbst als Verantwortliche(n) entfernen. "
                "Bitte eine andere Person mit der Pflege beauftragen.",
                ValidationError,
            )

    tabelle = _TABELLE[doctype]
    _ersetze_zeilen(tabelle, name, konten)
    return {"success": True, "verantwortliche": _zeilen(doctype, name)}


def _ersetze_zeilen(tabelle: str, parent: str, konten: list[str]) -> None:
    """Kind-Zeilen der Verantwortlichen ersetzen — in EINER Transaktion.

    Loeschen und Anlegen duerfen nicht getrennt committen: faellt das Anlegen
    aus, waere der alte Stand weg (dasselbe Muster wie in
    `moderation.speichere_aenderungsvorschlag`, Befund W4).
    """
    import uuid

    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.registry_gen import model_for

    model = model_for(tabelle)
    sess = SessionLocal()
    try:
        sess.execute(
            model.__table__.delete().where(
                model.parent == parent, model.parentfield == "verantwortliche"
            )
        )
        from datetime import datetime

        for idx, konto in enumerate(konten, start=1):
            sess.add(model(
                name=f"GRV-{uuid.uuid4().hex[:10]}",
                parent=parent,
                parenttype=tabelle.replace(" Verantwortlicher", ""),
                parentfield="verantwortliche",
                user=konto,
                idx=idx,
                docstatus=0,
                owner=str(session.user or ""),
                modified_by=str(session.user or ""),
                creation=datetime.now(),
                modified=datetime.now(),
            ))
        sess.commit()
    except FrappeCompatError:
        sess.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        sess.rollback()
        raise ValidationError(str(exc)) from exc
    finally:
        sess.close()


@whitelist(allow_guest=False)
def get_verantwortliche_auswahl(doctype: str, name: str, suche: str = "") -> dict[str, Any]:
    """Auswahlliste der Personen MIT Konto fuer „Verantwortliche" (P1-8).

    Anders als `get_gruppe_mitglieder_auswahl` (alle Mitglieder) liefert diese
    Liste nur Personen, die ein Login-Konto haben — nur die koennen ein Recht
    ausueben (OP-CHOR-3). Je Treffer: `user` (Konto), `name` (Anzeigename),
    `ist_verantwortlich` (bereits eingetragen).

    Rechte wie `get_verantwortliche`: wer die Angaben sehen darf, darf die
    Auswahl sehen. Die Suche filtert serverseitig (umlaut-/gross-klein-unabhaengig).
    """
    doctype = str(doctype or "").strip()
    name = str(name or "").strip()
    if doctype not in _TABELLE:
        throw("Unbekannte Art: " + doctype, ValidationError)
    if not name or get_value(doctype, name, "name") is None:
        throw(f"{doctype} nicht gefunden.", DoesNotExistError)
    # R-P1-8/W4: Die Auswahl enthaelt ALLE Mitglieder mit Konto samt Kontoname
    # (= E-Mail). Sie ist nur fuer die Pflegeberechtigten bestimmt; jedes andere
    # Mitglied, das die Gruppe sehen darf, saehe sonst die Kontenliste der
    # Gemeinde. Leserecht allein genuegt hier NICHT.
    if not _darf_verantwortliche_pflegen(doctype, name):
        throw("Keine Berechtigung für die Personenauswahl.", FrappePermissionError)

    bereits = {v["user"] for v in _zeilen(doctype, name) if v.get("user")}
    begriff = str(suche or "").strip().lower()
    # Personen mit Konto: die Verknuepfung laeuft ueber `Mitglied.user`.
    mitglieder = get_all(
        "Mitglied",
        filters={"user": ["is", "set"]},
        fields=["name", "vorname", "nachname", "user", "ausgeschlossen",
                "status", "austritt_datum"],
    ) or []
    ergebnis: list[dict[str, Any]] = []
    # AUSTRITT-b (B1): Anzeigename ueber die eine Regel (siehe `_zeilen`).
    # AUSTRITT-d (NM1): die Sicht EINMAL bilden, nicht je Zeile.
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename

    sicht = PersonenSicht.aus()
    for m in mitglieder:
        user = str(m.get("user") or "")
        if not user:
            continue
        # R-P1-8/W5: nur aktive, nicht ausgeschlossene Konten sind waehlbar —
        # sie allein koennen ein Recht ausueben.
        if not bool(get_value("User", user, "enabled")):
            continue
        if _mitglied_ausgeschlossen(user):
            continue
        anzeige = anzeigename(m, sicht=sicht).strip() or user
        if begriff and begriff not in anzeige.lower() and begriff not in user.lower():
            continue
        ergebnis.append({
            "user": user,
            "mitglied": m.get("name"),
            "name": anzeige,
            "ist_verantwortlich": user in bereits,
        })
    ergebnis.sort(key=lambda r: r["name"].lower())
    return {"success": True, "auswahl": ergebnis}


@whitelist(allow_guest=False)
def get_zugangs_rollen() -> dict[str, Any]:
    """Die in der Oberflaeche waehlbaren Zugangs-Rollen (OP-ADMIN-2).

    Feste Diakronos-Liste — nicht die 71 geerbten ERPNext-Rollen. Fuehrt die
    Installation eigene Rollen (`role`-Tabelle), kommen NUR die bekannten
    Diakronos-Rollen zurueck; eine Gemeinde soll kein „Fleet Manager"
    vergeben.
    """
    _require_admin()
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import Role

    sess = SessionLocal()
    try:
        bekannte = {
            str(r.name).strip() for r in sess.query(Role).all()
            if getattr(r, "name", None)
        }
    finally:
        sess.close()
    verfuegbar = [r for r in ZUGANGS_ROLLEN if r in bekannte]
    # Rollen immer anbieten, auch wenn die `role`-Tabelle sie (noch) nicht
    # fuehrt — sonst waere in einer frischen Installation nichts waehlbar.
    alle = list(dict.fromkeys(verfuegbar + list(ZUGANGS_ROLLEN)))
    return {"rollen": alle}
