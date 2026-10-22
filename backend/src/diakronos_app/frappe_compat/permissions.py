"""Permissions der Compat-Schicht — **fail closed**.

Portierung von `diakronos.diakonos.api.session` (check_permission,
get_mitglied_permissions, _paths_overlap) und `api/_permissions.py`
(is_admin, ist_verantwortlich_fuer, has_bereichs_zugriff, darf_entwurf_sehen).

Die Spezifikation mit Fundstelle fuer jede Zeile steht in den Docstrings
unten und in der Testmatrix (`backend/tests/test_permissions.py`). Wer eine
Regel aendert, aendert beide mit.

WARUM DIESE DATEI SO STRENG IST
-------------------------------
Diakronos verwaltet Mitgliederdaten einer Kirchengemeinde. Eine zu grosszuegige
Permission-Regel ist kein Bug, sondern ein Datenschutzvorfall (Art. 5/32 DSGVO).
Eine zu strenge Regel faellt beim Testen sofort auf; eine zu lockere faellt
niemandem auf.

Drei Regeln, die NICHT verhandelbar sind (Karte P3):
  * kein "wenn keine Rollen ermittelbar, dann Admin annehmen"
    -> `get_roles()` ist eine echte DB-Abfrage und liefert bei Unbekanntem `()`.
  * kein stilles `True` bei unbekanntem DocType
    -> `reason="unsupported_doctype"`, erlaubt nur der Admin-Kurzschluss.
  * die `permission_type == "read"`-Einschraenkung fuer
    Gruppe/Untergruppe/Dienstbereich bleibt drin. Ohne sie koennte jedes
    einfache Mitglied seine eigene Gruppe schreiben.

Bekannte Abweichung vom Altcode (bewusst, dokumentiert, fail closed):
  `has_bereichs_zugriff("")` -> `False`. Der Altcode ruft dort
  `frappe.has_permission("Dienstbereich", "read")` auf, das in der
  Compat-Schicht nicht existiert. Begruendung: fail closed.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from .exceptions import DoesNotExistError, PermissionError, throw
from .query import get_all, get_value
from .session import session

# Rollen, die im Altcode Vollzugriff auf Mitgliederdaten haben.
# Quelle: referenz/diakronos-frappe/diakronos/diakonos/api/_permissions.py:21
#         referenz/diakronos-frappe/diakronos/diakonos/api/session.py:7
ADMIN_ROLES = ("System Manager", "Mitgliederadministrator")

# Der Altcode kennt KEINE separate Admin-Mode-Rolle; siehe
# api/session.py:155 ("kein separater Admin-Mode mehr noetig").
GUEST = "Guest"

# DocTypes mit ancestor_path-basierter Sichtbarkeit
# Quelle: api/session.py:167
_PATH_DOCTYPES = ("Gruppe", "Untergruppe", "Dienstbereich")


def mitglied_ausgeschlossen(user: str | None = None) -> bool:
    """True, wenn das Mitglied dieses Benutzers ausgeschlossen ist (P1-8).

    „Ausschliessen“ (`api/mitglieder.py::schliesse_mitglied_aus`) setzt am
    MITGLIED `ausgeschlossen=1`; das Login-Konto bleibt unberuehrt. Ohne
    diese Abfrage behielte eine ausgeschlossene Person ihre Rollen und
    Sichtbarkeit. Deshalb ist der Ausschluss hier eine der *Wurzeln* der
    Rechteprüfung: `get_roles()` liefert fuer ein ausgeschlossenes Mitglied
    `()` — und damit greift dieselbe Verweigerung in JEDER Rollenprüfung.

    Ein Benutzer ohne verknuepftes Mitglied (z. B. der erste Administrator)
    ist nicht ausgeschlossen; Fehler beim Nachsehen führen zu `False` (die
    Hauptregel `enabled` bleibt fail closed, siehe `benutzer_status`).
    """
    name = str(user if user is not None else session.user or "").strip()
    if not name or name == GUEST:
        return False
    try:
        from diakronos_app.frappe_compat.benutzer_status import (
            _mitglied_ausgeschlossen as _impl,
        )

        return _impl(name)
    except Exception:  # noqa: BLE001 — Zusatzschranke, siehe Docstring
        return False


# ── Rollen ──────────────────────────────────────────────────────────────────


def ist_user_zeile(parenttype: str | None) -> bool:
    """Ist eine `Has Role`-Kindzeile dem DocType `User` zuzuordnen?

    R-N10 Punkt 7: Die `Has Role`-Tabelle ist mit Frappe gewachsen und enthaelt
    auch Zeilen fuer ANDERE Eltern-DocTypes (z. B. Seiten/Berichte wie `ToDo`,
    `backups`), deren `parent` zufaellig wie ein Benutzername aussehen kann.

    Der `parenttype` fehlt aber bei Altdaten haeufig (NULL oder leer); solche
    Zeilen sind in dieser Installation historisch Benutzer-Rollen — die
    datenschutz-Auskunft behandelt sie genauso (siehe
    `api/datenschutz.py`: "Zeilen ohne parenttype"). Deshalb gilt: NUR ein
    ausdruecklich FREMDER parenttype wird ausgeschlossen, NULL/leer zaehlt als
    `User`. Ein reines `parenttype == "User"` haette alle Altdaten-Zeilen
    verworfen und damit jedes Konto seine Rollen gekostet (Befund im Testlauf
    N12: 403 fuer den Administrator).
    """
    wert = (parenttype or "").strip()
    return wert in ("", "User")


def get_roles(user: str | None = None) -> tuple[str, ...]:
    """Rollen eines Benutzers — **echte Quelle** aus der `Has Role`-Tabelle.

    Ersetzt `frappe.get_roles(user)` (api/session.py:49, 98, 152).

    Quelle: `inventar/live_schema_ist.tsv` (`tabHas Role`, Kind von `User`).
    Der Altcode liest dieselbe Tabelle in
    `kronos/api/permissions.py:_user_has_role`:
    `frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])`.

    Fail closed, in dieser Reihenfolge:
      * `Guest` hat per Definition keine Rollen. Das Original behandelt Guest
        in `admin_hub._require_admin()` (api/admin_hub.py:6) als Sonderfall
        *vor* der Rollenpruefung; hier wird er an der Wurzel ausgefiltert,
        damit kein Aufrufpfad ihn vergessen kann.
      * Ein unbekannter/NULL-Benutzer hat keine Rollen. Es gibt KEINE
        Sonderbehandlung fuer einen Default-Benutzernamen — sonst waere jeder
        anonyme Aufruf ein Admin.
      * P1-8 (Nachtrag R-P1-9b): Ein AUSGESCHLOSSENES Mitglied hat keine
        Rollen. Der Ausschluss ist der stärkere Wille der Gemeinde; die
        Rollenprüfung an genau dieser Stelle abzuschneiden stellt sicher,
        dass „ausgeschlossen“ in JEDER Rechteprüfung wirkt (is_admin,
        check_permission, has_role) — nicht nur in der Sitzungsprüfung.
    """
    name = user if user is not None else session.user
    if not name or name == GUEST:
        return ()
    if mitglied_ausgeschlossen(name):
        return ()

    # R-N10 Punkt 7: nur Kindzeilen des DocType `User`. Die Auswahl holt alle
    # Zeilen des Kontos und schliesst ausdruecklich fremde `parenttype`-Werte
    # aus; altdaten-`parenttype` (NULL/leer) zaehlt als `User` (siehe
    # `ist_user_zeile`). Der Filter laeuft in Python, weil `get_all` keinen
    # OR-Ausdruck auf einen einzelnen Doctype-Filter abbildet.
    zeilen = get_all(
        "Has Role",
        filters={"parent": name},
        fields=["role", "parenttype"],
    )
    return tuple(sorted({
        str(z["role"]) for z in zeilen
        if z.get("role") and ist_user_zeile(z.get("parenttype"))
    }))


def has_role(role: str) -> bool:
    """Rollen-Praedikat fuer den portierten Code (Frappe `"x" in frappe.get_roles()`)."""
    return role in get_roles(session.user)


def is_guest(user: str | None = None) -> bool:
    """True, wenn der aktuelle Benutzer nicht angemeldet ist.

    Entspricht `frappe.session.user == "Guest"` im Altcode
    (`admin_hub.py:_require_admin`).
    """
    return (user or session.user) == GUEST


def is_admin(user: str | None = None) -> bool:
    """True wenn der Benutzer Vollzugriff hat.

    Quelle: `_permissions.is_admin()` (api/_permissions.py:24-29).
    Enthaelt die `"Administrator"`-Sonderbehandlung des Originals **1:1**.

    ACHTUNG — nicht verwechseln: `check_permission()` und
    `mitglied_permissions()` benutzen im Original **nur** die Rollenpruefung
    (api/session.py:153, 99) und NICHT diese Funktion.
    """
    name = user if user is not None else session.user
    if name == "Administrator":
        return True
    return any(r in get_roles(name) for r in ADMIN_ROLES)


def _has_admin_role(user: str | None = None) -> bool:
    """Nur die Rollenpruefung — das, was `check_permission` im Original nutzt.

    Quelle: api/session.py:152-153 (`any(r in roles for r in ADMIN_ROLES)`).
    """
    roles = get_roles(user)
    return any(r in roles for r in ADMIN_ROLES)


def require_admin() -> None:
    """Wirft `PermissionError`, wenn der aktuelle Benutzer kein Admin ist.

    Entspricht `_require_admin()` aus `admin_hub.py`. Guest wird — wie im
    Original — gesondert und mit derselben Meldung behandelt.
    """
    user = session.user
    if user == GUEST:
        throw("Zugriff verweigert.", PermissionError)
    if not _has_admin_role(user):
        throw("Nur für Mitgliederadministratoren.", PermissionError)


# ── Pfad-Ueberlappung ───────────────────────────────────────────────────────


def _extract_segments(path: str | None) -> tuple[set[str], set[str]]:
    """Zerlegt einen ancestor_path in (Gruppen, Bereiche).

    Format: `/Gruppe1/Gruppe2/|/BereichA/`
    Quelle: `_paths_overlap._extract_segments` (api/session.py:235-240).
    """
    if not path:
        return set(), set()
    parts = path.split("|")
    gruppen = {g for g in parts[0].split("/") if g}
    bereiche = {b for b in parts[1].split("/") if b} if len(parts) > 1 else set()
    return gruppen, bereiche


def _paths_overlap(user_path: str | None, target_path: str | None) -> bool:
    """Prueft, ob zwei ancestor_paths ueberlappen.

    Quelle: api/session.py:227-246 — **exakt uebernommen**.

    Gruppen und Bereiche sind getrennte Mengen: eine Gruppe ueberlappt nie mit
    einem Bereich. Leerer Pfad -> False (fail closed).
    """
    if not user_path or not target_path:
        return False

    user_gruppen, user_bereiche = _extract_segments(user_path)
    target_gruppen, target_bereiche = _extract_segments(target_path)

    return bool(user_gruppen & target_gruppen or user_bereiche & target_bereiche)


# ── Mitglied-Datensatz des aktuellen Users ──────────────────────────────────


def _get_current_user_mitglied() -> dict[str, Any] | None:
    """Holt den Mitglied-Datensatz des aktuellen Users.

    Quelle: api/session.py:184-192. Die E-Mail kommt aus `User.email`, sonst
    ist sie der Benutzername selbst.

    SEC-d (X4): verglichen wird NORMALISIERT (`email_belegung.normalisiere`:
    NFKC, ohne Leerraum, klein) — nicht mehr mit `filters={"email": email}`
    in SQL. Grund: seit SEC-c speichert jeder Schreibweg die Adresse
    normalisiert (`Max@X.org` -> `max@x.org`). Ein Konto mit gemischter
    Schreibweise (OIDC, Altimport) verlor damit beim ERSTEN Speichern seines
    eigenen Formulars die Zuordnung zu seiner Person — und mit ihr Profil und
    Selbstrechte.
    """
    from diakronos_app.email_belegung import normalisiere

    user = session.user
    email = get_value("User", user, "email") or user
    gesucht = normalisiere(email)
    if not gesucht:
        return None
    # Bewusst Vollscan: eine Vorauswahl per SQL faltet Leer-/Sonderzeichen
    # anders als `normalisiere` und wuerde Treffer (und Dubletten) verlieren.
    rows = get_all(
        "Mitglied",
        fields=["name", "ancestor_path", "email", "status"],
        limit_page_length=None,
    )
    treffer = [r for r in rows if normalisiere(r.get("email")) == gesucht]
    if len(treffer) > 1:
        logging.getLogger(__name__).warning("Mehrdeutige Mitglied-Zuordnung; Zugriff verweigert")
        return None
    return dict(treffer[0]) if treffer else None


# ── Permission-Map eines Mitglieds ──────────────────────────────────────────

_DENIED_MITGLIED = {
    "can_view": False,
    "can_edit": False,
    "can_delete": False,
    "can_view_sensitive": False,
}


def mitglied_permissions(mitglied_id: str, target: dict[str, Any] | None = None) -> dict[str, Any]:
    """Permission-Map fuer ein Mitglied.

    Quelle: `get_mitglied_permissions()` (api/session.py:82-141).
    Struktur und `reason`-Werte sind identisch, damit die SPA unveraendert
    daran aufhaengen kann (`can_view_sensitive` steuert den DSGVO-Block).

    `can_delete` ist **auch fuer Admins False** (session.py:107) — Loeschen
    laeuft nie ueber diese Map. `can_view_sensitive` ist **Admin-only**.
    """
    user = session.user

    if target is None:
        target = get_value(
            "Mitglied",
            mitglied_id,
            ["name", "ancestor_path", "email", "status"],
            as_dict=True,
        )

    if not target:
        throw("Mitglied nicht gefunden.", DoesNotExistError)

    # Admin-Kurzschluss. Quelle: session.py:98-110.
    if _has_admin_role(user):
        return {
            "can_view": True,
            "can_edit": True,
            "can_delete": False,
            "can_view_sensitive": True,
            "reason": "admin_role",
        }

    current_mitglied = _get_current_user_mitglied()

    # Kein Email-Fallback nach einem fehlgeschlagenen Lookup: insbesondere
    # eine mehrdeutige Zuordnung darf nicht wieder Selbstrechte bekommen.
    if not current_mitglied:
        return {**_DENIED_MITGLIED, "reason": "no_access"}

    # User hat ancestor_path: Gruppen-/Bereichs-basierte Pruefung.
    # Quelle: session.py:124-141.
    user_path = current_mitglied.get("ancestor_path") or "|"
    target_path = target.get("ancestor_path") or "|"

    can_view = _paths_overlap(user_path, target_path)

    # Fallback: eigenes Profil immer erlaubt (auch wenn Pfade leer sind).
    # Quelle: session.py:131-133.
    if not can_view and target.get("email") == current_mitglied.get("email"):
        can_view = True

    return {
        "can_view": can_view,
        "can_edit": can_view and target.get("name") == current_mitglied.get("name"),
        "can_delete": False,
        "can_view_sensitive": False,
        "reason": "ancestor_path" if can_view else "no_overlap",
    }


def require_mitglied_view(mitglied_id: str) -> dict[str, Any]:
    """`mitglied_permissions` + Durchsetzung. Wirft bei fehlender Sichtbarkeit."""
    perms = mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        throw("Kein Zugriff", PermissionError)
    return perms


def require_mitglied_edit(mitglied_id: str) -> dict[str, Any]:
    """Wie `require_mitglied_view`, aber fuer schreibende Zugriffe."""
    perms = mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        throw("Kein Zugriff", PermissionError)
    return perms


# ── generische Permission-Abfrage ───────────────────────────────────────────


def check_permission(
    doctype: str,
    docname: str,
    permission_type: str = "read",
) -> dict[str, Any]:
    """Generische Permission-Check API.

    Quelle: `check_permission()` (api/session.py:144-179).

    doctype: 'Mitglied' | 'Gruppe' | 'Untergruppe' | 'Dienstbereich'
    permission_type: 'read' | 'write' | 'create' | 'delete'

    Reihenfolge wie im Original: Admin-Kurzschluss -> DocType-Weiche.
    Der Admin-Kurzschluss steht **vor** der DocType-Weiche; deshalb darf auch
    ein unbekannter DocType von einem Admin gelesen werden (session.py:157-159).
    """
    user = session.user

    # Admin-Kurzschluss (nur Rollen, ohne "Administrator"-Sonderfall).
    # Quelle: session.py:152-159.
    if _has_admin_role(user):
        return {"allowed": True, "reason": "admin_role"}

    if doctype == "Mitglied":
        perms = mitglied_permissions(docname)
        key = "can_edit" if permission_type in ("write", "create", "delete") else "can_view"
        return {"allowed": bool(perms.get(key, False)), "reason": perms.get("reason")}

    if doctype in _PATH_DOCTYPES:
        current_mitglied = _get_current_user_mitglied()
        if not current_mitglied:
            return {"allowed": False, "reason": "no_mitglied"}

        user_path = current_mitglied.get("ancestor_path") or "|"
        target = get_value(doctype, docname, "ancestor_path")
        target_path = target or "|"

        # Die `permission_type == "read"`-Einschraenkung IST die Fachlogik:
        # ohne sie koennte ein Mitglied seine eigene Gruppe schreiben.
        # Quelle: session.py:176.
        allowed = _paths_overlap(user_path, target_path) and permission_type == "read"
        return {"allowed": allowed, "reason": "ancestor_path" if allowed else "no_overlap"}

    return {"allowed": False, "reason": "unsupported_doctype"}


# ── Verantwortlichkeit ──────────────────────────────────────────────────────


def _is_verantwortlicher_in(child_doctype: str, parent: str | None) -> bool:
    """Eine Zeile in einer *Verantwortlicher-Child-Tabelle fuer diesen User?"""
    if not parent:
        return False
    return bool(
        get_all(
            child_doctype,
            filters={"user": session.user, "parent": parent},
            fields=["name"],
            limit_page_length=1,
        )
    )


def ist_verantwortlich_fuer(dienstbereich: str | None, gruppe: str | None) -> bool:
    """Verantwortlichkeit anhand von Bereich und Gruppe pruefen.

    Quelle: `_permissions.ist_verantwortlich_fuer()` (api/_permissions.py:32-56).

    Verantwortlichkeit haengt an `Dienstbereich Verantwortlicher` bzw.
    `Gruppe Verantwortlicher` (Feld `user`) — NICHT am ancestor_path, der
    Mitgliedschaft abbildet. Wer einen Bereich verantwortet, ist dort oft
    selbst in keiner Gruppe und haette sonst gar keine Sicht.

    Leere Argumente (None/"") werden uebersprungen, NICHT als Fehler gewertet.
    """
    if _is_verantwortlicher_in("Dienstbereich Verantwortlicher", dienstbereich):
        return True
    if _is_verantwortlicher_in("Gruppe Verantwortlicher", gruppe):
        return True
    return False


def has_bereichs_zugriff(dienstbereich: str | None, gruppe: str | None = None) -> bool:
    """Lese-Zugriff auf einen Dienstbereich — Mitgliedschaft ODER Leitung.

    Quelle: `_permissions.has_bereichs_zugriff()` (api/_permissions.py:59-74).

    Ein User darf den Bereich sehen, wenn er (a) Admin ist, (b) eine Gruppe
    im Bereich verantwortet (Verantwortliche sind oft in keiner eigenen
    Gruppe) oder (c) per ancestor_path Mitglied einer Gruppe des Bereichs ist.

    ABWEICHUNG (fail closed): ohne
    `dienstbereich`-Argument greift im Original ein generischer
    `frappe.has_permission("Dienstbereich", "read")`-Fallback. Diese Funktion
    existiert in der Compat-Schicht nicht und ist im Altcode nicht weiter
    belegt -> hier `False`.
    """
    if is_admin():
        return True
    if not dienstbereich:
        # UNGEKLAERT -> verweigert (Spec §2.4). Nicht "vereinfachen".
        return False
    if ist_verantwortlich_fuer(dienstbereich, gruppe):
        return True
    perm = check_permission("Dienstbereich", dienstbereich, "read")
    return bool(perm.get("allowed"))


def darf_entwurf_sehen(
    owner: str | None,
    dienstbereich: str | None,
    gruppe: str | None,
) -> bool:
    """Schranke fuer Entwuerfe (ist_entwurf=1) — EINE Wahrheit fuer alle APIs.

    Quelle: `_permissions.darf_entwurf_sehen()` (api/_permissions.py:77-106).

    Ein Plan im Entwurf ist sichtbar NUR fuer:
      - den Ersteller (`owner`, der Frappe-User-Login des Plans), und
      - Verantwortliche des Dienstbereichs bzw. der Gruppe (`gruppe`), und
      - `"Administrator"` selbst.

    Hinweis: das Original deklariert `admin = is_admin()` (P:95), wertet die
    Variable aber nie aus — toter Code. Wirksam sind genau die drei obigen
    Bedingungen. Das wird hier nicht "repariert": eine Auswertung von
    `is_admin()` waere eine Erweiterung der Sicht und damit genau die zu
    lockere Regel, vor der diese Karte warnt.
    """
    current = session.user

    # Ersteller (owner ist der User-Login, nicht eine Mitglied-Referenz)
    if owner and owner == current:
        return True

    # Administrator wird bereits von is_admin() erfasst; owner == "Administrator"
    # ebenso — hier rein zur Eindeutigkeit der Logik.
    if current == "Administrator":
        return True

    # Verantwortliche des Dienstbereichs bzw. der Gruppe
    if ist_verantwortlich_fuer(dienstbereich, gruppe):
        return True

    return False


__all__ = [
    "ADMIN_ROLES",
    "GUEST",
    "check_permission",
    "darf_entwurf_sehen",
    "get_roles",
    "has_role",
    "has_bereichs_zugriff",
    "is_admin",
    "is_guest",
    "ist_verantwortlich_fuer",
    "mitglied_permissions",
    "require_admin",
    "require_mitglied_edit",
    "require_mitglied_view",
]
