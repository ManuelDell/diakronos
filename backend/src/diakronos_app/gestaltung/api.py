"""UX1j — Endpunkte der „Gestaltung“-Einstellungen (nur System Manager).

Drei Endpunkte, mehr gibt es nicht:

  ``gestaltung.lesen``          — Standardwerte + Abweichungen (lesend)
  ``gestaltung.speichern``      — ``{token: wert}`` schreiben (POST)
  ``gestaltung.zuruecksetzen``  — ein Token oder alles (POST)

Rollen
------
NUR ``System Manager`` — dieselbe Prüfung wie ``api/zugang.py`` und
``api/sicherung.py``. Die Maße gelten für die GANZE Oberfläche; wer sie
verstellt, verstellt sie für alle. Ein Mitgliederadministrator hat dort nichts
zu suchen, und die Oberfläche blendet den Bereich zusätzlich aus (das ist nur
Komfort — entschieden wird hier).

Die SPA ruft die Frappe-Form ``diakronos.diakonos.api.gestaltung.<name>``;
der Kurzpfad ``gestaltung.<name>`` wird zusätzlich registriert, weil die Karte
ihn so nennt.

Audit
-----
Jede Änderung schreibt einen Eintrag ins vorhandene Audit-Log
(``api.audit.log``, ``action_typ = "Berechtigungsänderung"`` — der einzige
Typ, der „eine Einstellung für alle" beschreibt, und in ``VALID_ACTIONS``
vorhanden ist). ``target_doctype = "Gestaltung"``, ``target_name`` ist der
Token-Name bzw. ``alle``; der Klartext (alt → neu) steht in der Begründung.
Kein neuer ``action_typ``: das wäre ein Schema-Thema und keine Kartenaufgabe.
"""

from __future__ import annotations

import logging

from diakronos_app.api import audit
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.registry import whitelist, register_with_frappe_module
from diakronos_app.frappe_compat.session import session

from . import speicher
from . import tokens as T

logger = logging.getLogger("diakronos_app.gestaltung.api")

FRAPPE_MODULE = "diakronos.diakonos.api.gestaltung"

#: Ziel-Name im Audit-Log für „alles zurückgesetzt“.
ZIEL_ALLE = "alle"

#: Der Audit-Typ. ``Berechtigungsänderung`` ist der nächste vorhandene Typ:
#: die Änderung wirkt auf ALLE Nutzer und ist damit eine Freigabe-Entscheidung,
#: keine persönliche Profiländerung.
AUDIT_TYP = "Berechtigungsänderung"

__all__ = [
    "FRAPPE_MODULE",
    "gestaltung_lesen",
    "gestaltung_speichern",
    "gestaltung_zuruecksetzen",
]


def _angemeldeter_system_manager() -> str:
    """Nur System Manager — gleiche Prüfung wie ``api/sicherung.py``."""
    user = str(session.user or "").strip()
    if not user or user == "Guest":
        throw("Anmeldung verweigert.", FrappePermissionError)
    from diakronos_app.frappe_compat.permissions import get_roles

    if "System Manager" not in get_roles():
        throw(
            "Nur System Manager dürfen die Gestaltung einstellen.",
            FrappePermissionError,
        )
    return user


def _felder(abweichungen: dict[str, int]) -> list[dict]:
    """Ein Eintrag je einstellbarem Maß — die einzige Quelle für die Oberfläche.

    Die Oberfläche braucht KEINE eigene Token-Liste: Name, Standard, Grenzen,
    Einheit, Gruppe und der geltende Wert kommen von hier. So kann sie nicht
    etwas anbieten, das der Server ablehnt.
    """
    return [
        {
            "token": t.name,
            "standard": t.standard,
            "wert": int(abweichungen.get(t.name, t.standard)),
            "einheit": t.einheit,
            "min": t.minimum,
            "max": t.maximum,
            "schritt": t.schritt,
            "gruppe": t.gruppe,
            "abweichend": t.name in abweichungen,
        }
        for t in T.TOKENS
    ]


def _stand(abweichungen: dict[str, int]) -> dict:
    from . import route

    return {
        "felder": _felder(abweichungen),
        "standard": T.standardwerte(),
        "abweichungen": dict(sorted(abweichungen.items())),
        # EINE Quelle für die aufsteigende Kette (UX1j2): nur diese Maße
        # müssen `--sp-1 < … < --sp-8` bleiben. `--pad` u. ä. stehen NICHT
        # darin — die Oberfläche (UX1k) soll die Kette nicht selbst raten.
        "skala_ordnung": list(T.SKALA_TOKEN),
        "css_hash": route.css_hash(),
    }


@whitelist(allow_guest=False)
def gestaltung_lesen():
    """Standardwerte aus der Positivliste + die gespeicherten Abweichungen."""
    _angemeldeter_system_manager()
    return _stand(speicher.abweichungen())


@whitelist(methods=["POST"], allow_guest=False)
def gestaltung_speichern(werte=None):
    """``{token: wert}`` prüfen und schreiben.

    Wirft 417 (``ValidationError``) bei unbekanntem Token, ungültigem Wert
    oder gebrochener Abstands-Skala. Dann wird NICHTS geschrieben.
    """
    user = _angemeldeter_system_manager()
    if not isinstance(werte, dict):
        throw("Es wurde kein Wert zum Speichern übergeben.", ValidationError)

    vorher = speicher.abweichungen()
    try:
        nachher = speicher.speichern(werte, benutzer=user)
    except ValueError as exc:
        # `throw` wirft (417) — die Zuweisung danach wird nie erreicht; die
        # Zuweisung an `nachher` bleibt so aber für Leser/Nachweis eindeutig.
        throw(str(exc), ValidationError)
        raise  # noqa: B904 — unerreichbar, nur für Typprüfer

    geaendert = {
        name: (vorher.get(name, T.standard_zu(name)), wert)
        for name, wert in nachher.items()
        if vorher.get(name, T.standard_zu(name)) != wert
    }
    for name, (alt, neu) in sorted(geaendert.items()):
        audit.log(
            AUDIT_TYP,
            "Gestaltung",
            name,
            f"{name}: {alt} px → {neu} px",
        )
    return _stand(nachher)


@whitelist(methods=["POST"], allow_guest=False)
def gestaltung_zuruecksetzen(token=None):
    """Einen Wert (``token``) oder ALLE (ohne Angabe) auf den Standard setzen."""
    user = _angemeldeter_system_manager()
    name = None if token in (None, "") else str(token).strip()

    vorher = speicher.abweichungen()
    try:
        nachher = speicher.zuruecksetzen(name, benutzer=user)
    except ValueError as exc:
        throw(str(exc), ValidationError)
        raise  # noqa: B904 — unerreichbar, nur für Typprüfer

    ziel = name or ZIEL_ALLE
    if name is None:
        begruendung = (
            f"alle Abweichungen zurückgesetzt ({len(vorher)} Wert(e))"
            if vorher
            else "alle Abweichungen zurückgesetzt (es gab keine)"
        )
    else:
        alt = vorher.get(name, T.standard_zu(name))
        begruendung = f"{name}: {alt} px → Standard {T.standard_zu(name)} px"
    audit.log(AUDIT_TYP, "Gestaltung", ziel, begruendung)
    return _stand(nachher)


# Kurzpfade, die die Karte so nennt (`gestaltung.lesen|speichern|zuruecksetzen`)
# zusätzlich zur Frappe-Bahn und zur abgeleiteten Form
# (`gestaltung.gestaltung_lesen`). DIESELBEN Funktionen — die Optionen
# (`allow_guest`, `methods`) hängen an der Funktion und gehen mit.
for _kurz, _fn in (
    ("lesen", gestaltung_lesen),
    ("speichern", gestaltung_speichern),
    ("zuruecksetzen", gestaltung_zuruecksetzen),
):
    register_with_frappe_module("gestaltung", _kurz, _fn)
