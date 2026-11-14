"""Permissions der Compat-Schicht — **fail closed**.

Portierung von `diakronos.diakonos.api.session` (check_permission,
get_mitglied_permissions) und `api/_permissions.py`
(is_admin, ist_verantwortlich_fuer, has_bereichs_zugriff, darf_entwurf_sehen).

R-11 (Plan diakronos-rechte, Manuel 11.11.): Diese Funktionen sind nur noch
ADAPTER auf den EINEN Rechte-Kern (``diakronos_app.rechte``). Der
``ancestor_path`` ist keine Rechtequelle mehr, ``is_admin`` ist der
Administrator des Kerns, die Mitgliederverwaltung steht in
``ist_mitgliederverwaltung`` bzw. ``ADMIN_ROLES`` (Personenbereich).

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

# Rollen mit Vollzugriff auf MITGLIEDERDATEN (Personenbereich: Admin und
# Fachverwaltung Mitglieder). Kein allgemeiner Admin-Begriff — siehe is_admin.
# Quelle: referenz/diakronos-frappe/diakronos/diakonos/api/_permissions.py:21
#         referenz/diakronos-frappe/diakronos/diakonos/api/session.py:7
ADMIN_ROLES = ("System Manager", "Mitgliederadministrator")

# Der Altcode kennt KEINE separate Admin-Mode-Rolle; siehe
# api/session.py:155 ("kein separater Admin-Mode mehr noetig").
GUEST = "Guest"



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


# ── ON-6: root ──────────────────────────────────────────────────────────────

#: Der Rollenname der root-Kennzeichnung (``root_benutzer.ROOT_ROLLE``). Er
#: steht in ``get_roles(root)`` und ist damit die Marke, an der ``has_role`` und
#: ``is_admin`` einen root erkennen — aber NUR, solange ``get_roles`` ihm
#: Rollen liefert. Ein ausgeschlossener root bekommt ``()`` (ON-6b, Befund 2)
#: und besteht damit keine Pruefung mehr.
ROOT_ROLLE = "root"


def _ist_root(user: str | None) -> bool:
    """Ist dieses Konto der eingetragene root? (ON-6, fail closed)

    Die Fachlogik steht in ``diakronos_app.root_benutzer``; hier nur der
    duenne Ruf, damit ``get_roles`` die EINE Wahrheit benutzt und nicht eine
    zweite Abfrage auf dieselbe Tabelle fuehrt. Ein Fehler beim Lesen der
    Einstellungen bedeutet: KEIN root (die Hauptregel bleibt fail closed).
    """
    try:
        from diakronos_app import root_benutzer

        return root_benutzer.ist_root(user)
    except Exception:  # noqa: BLE001 — fail closed, siehe Docstring
        return False


def _root_rollen(user: str) -> tuple[str, ...]:
    """Alle Rollen fuer root — die EIGENEN bleiben darin enthalten.

    ``has_role`` und alle Aufrufer lesen die Rollen hierueber. Damit gilt:
    root besteht jede Rollenpruefung, auch fuer eine Rolle, die es noch gar
    nicht gibt (``has_role("Kuenftige Rolle")`` -> True). Die Liste selbst
    dient der Anzeige und der Protokollierung.
    """
    rollen: set[str] = set()
    try:
        from diakronos_app import root_benutzer

        rollen.update(root_benutzer._alle_rollen())
    except Exception:  # noqa: BLE001
        pass
    rollen.add(ROOT_ROLLE)
    return tuple(sorted(rollen))


def ist_root(user: str | None = None) -> bool:
    """Oeffentliche Fassung von :func:`_ist_root` (ON-6).

    Fuer Aufrufer, die „ist das der root?“ fragen — z. B. der Schutz in
    ``api/zugang.py`` und der Boot in ``spa.py``. Nennt kein ``user``, gilt
    der angemeldete.
    """
    return _ist_root(user if user is not None else session.user)


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

    # ON-6: der ERSTE Administrator ist `root` und besteht JEDE
    # Rollen-/Rechtepruefung (Manuel 2026-11-05: „er ist root/sudo fuer
    # Diakronos“). Der Kurzschluss sitzt hier — an der EINEN Stelle, aus der
    # jede andere Pruefung ihre Rollen holt — und nicht an den 100+
    # Aufrufstellen. Darum steht er NACH den Fail-closed-Schranken: wer
    # ausgeschlossen oder Guest ist, ist auch als root kein root.
    if _ist_root(name):
        return _root_rollen(name)

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
    """Rollen-Praedikat fuer den portierten Code (Frappe `"x" in frappe.get_roles()`).

    ON-6: fuer den root ist JEDE Rolle wahr — auch eine, die es noch nicht
    gibt. ``get_roles`` liefert ihm dafuer die bekannten Rollen; diese Zeile
    schliesst die Luecke fuer alles, was NICHT in der Liste steht („alle
    Rollen inkl. kuenftiger“, Kartentext Punkt 2).
    """
    wert = str(role or "")
    if not wert:
        return False
    # ON-6b: ENTSCHIEDEN wird ueber `get_roles` — die EINE Stelle, die einen
    # ausgeschlossenen root bereits aussortiert (`mitglied_ausgeschlossen`).
    # Ein direkter `_ist_root`-Kurzschluss hier haette einem ausgeschlossenen
    # root weiter JEDE Rolle gegeben (Befund 2 des Sicherheits-Reviews).
    rollen = get_roles(session.user)
    if wert in rollen:
        return True
    # Fuer einen root stehen in `rollen` alle BEKANNTEN Rollen; diese Zeile
    # deckt die noch unbekannte (kuenftige) ab. Sie gilt nur, solange
    # `get_roles` ueberhaupt Rollen liefert — ein ausgeschlossener root hat ().
    return ROOT_ROLLE in rollen


def is_guest(user: str | None = None) -> bool:
    """True, wenn der aktuelle Benutzer nicht angemeldet ist.

    Entspricht `frappe.session.user == "Guest"` im Altcode
    (`admin_hub.py:_require_admin`).
    """
    return (user or session.user) == GUEST


def is_admin(user: str | None = None) -> bool:
    """Vollzugriff — der Administrator des EINEN Rechtesystems (R-11a).

    Manuel 11.11.: „Der Admin ist ja der einzige der alles darf“; die
    Fachverwaltungen sind eine eigene Ebene. Deshalb fragt diese Funktion den
    Rechte-Kern (``Administrator``, root, ``System Manager``) und zaehlt den
    ``Mitgliederadministrator`` NICHT mehr mit. Wo die Mitgliederverwaltung
    fachlich zustaendig ist (Personen, Konten, Registrierung, Datenschutz),
    steht :func:`ist_mitgliederverwaltung`.
    """
    from diakronos_app.rechte import ist_admin

    return ist_admin(user if user is not None else session.user)


def ist_mitgliederverwaltung(user: str | None = None) -> bool:
    """Fachverwaltung Personen: Admin oder Systemrolle Mitgliederverwaltung (R-11a)."""
    from diakronos_app.rechte import hat_systemrolle

    return hat_systemrolle(user if user is not None else session.user, "mitgliederverwaltung")


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

    # Eigenes Profil: lesen und bearbeiten. Quelle: session.py:131-133.
    if target.get("name") == current_mitglied.get("name") or (
        target.get("email") and target.get("email") == current_mitglied.get("email")
    ):
        return {
            "can_view": True,
            "can_edit": target.get("name") == current_mitglied.get("name"),
            "can_delete": False,
            "can_view_sensitive": False,
            "reason": "eigenes",
        }

    # R-11b (Manuel 11.11.): Vor- und Nachnamen ALLER Mitglieder sieht jedes
    # Gemeindemitglied; alles Weitere nur nach Freigabe der Person — die
    # Maskierung (`mitglied_sichtbarkeit.maskiere_datensatz`) liegt bei den
    # Auslieferungswegen. Die fruehere ancestor_path-Ueberlappung entfaellt.
    from diakronos_app import rechte

    can_view = rechte.ist_gemeindemitglied(user)
    return {
        "can_view": can_view,
        "can_edit": False,
        "can_delete": False,
        "can_view_sensitive": False,
        "reason": "gemeinde" if can_view else "no_access",
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

    if doctype == "Mitglied":
        # Personenbereich: Admin und Fachverwaltung Mitglieder sehen alles.
        if _has_admin_role(user):
            return {"allowed": True, "reason": "admin_role"}
        perms = mitglied_permissions(docname)
        key = "can_edit" if permission_type in ("write", "create", "delete") else "can_view"
        return {"allowed": bool(perms.get(key, False)), "reason": perms.get("reason")}

    # R-11b: Gruppen und Untergruppen fragen den EINEN Rechte-Kern (lesen =
    # Mitglied/Leitung/Admin; aendern = HV/MV bzw. GL/Admin). Dienstbereiche
    # entfallen (Manuel 11.11.) — sie pflegt und liest nur der Administrator.
    from diakronos_app import rechte

    if rechte.ist_admin(user):
        return {"allowed": True, "reason": "admin"}
    if doctype in ("Gruppe", "Untergruppe"):
        aktion = rechte.LESEN if permission_type == "read" else rechte.VERWALTEN
        entscheidung = rechte.darf(user, aktion, doctype.lower(), docname or None)
        return {"allowed": bool(entscheidung), "reason": entscheidung.grund}
    if doctype == "Dienstbereich":
        return {"allowed": False, "reason": "nur_admin"}
    return {"allowed": False, "reason": "unsupported_doctype"}


# ── Verantwortlichkeit ──────────────────────────────────────────────────────


def ist_verantwortlich_fuer(dienstbereich: str | None, gruppe: str | None) -> bool:
    """Leitung (HV/MV) der Gruppe — ueber den EINEN Rechte-Kern (R-11c).

    Dienstbereiche haben keine eigenen Verantwortlichen mehr (Manuel 11.11.:
    „Dienstbereich braucht man dann nicht“); ``dienstbereich`` bleibt nur
    fuer die Signatur. Leere Argumente -> ``False``.
    """
    if not gruppe:
        return False
    from diakronos_app import rechte

    return rechte.gruppenrolle(session.user, gruppe) in ("HV", "MV")


def has_bereichs_zugriff(dienstbereich: str | None, gruppe: str | None = None) -> bool:
    """Lesezugriff auf Inhalte einer Gruppe des Bereichs (R-11c).

    Admin immer; sonst nur ueber die Gruppe (Mitglied, GL, HV/MV) — ein
    Bereich allein verleiht kein Recht mehr (fail closed).
    """
    if is_admin():
        return True
    if not gruppe:
        return False
    from diakronos_app import rechte

    return rechte.gruppenrolle(session.user, gruppe) is not None


def darf_entwurf_sehen(
    owner: str | None,
    dienstbereich: str | None,
    gruppe: str | None,
) -> bool:
    """Schranke fuer Entwuerfe (ist_entwurf=1): Ersteller, Admin und die
    Leitung (HV/MV) der Gruppe — ueber den EINEN Rechte-Kern (R-11c)."""
    current = session.user
    if owner and owner == current:
        return True
    if is_admin(current):
        return True
    return ist_verantwortlich_fuer(dienstbereich, gruppe)


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
    "ist_mitgliederverwaltung",
    "ist_root",
    "ist_verantwortlich_fuer",
    "mitglied_permissions",
    "require_admin",
    "require_mitglied_edit",
    "require_mitglied_view",
]
