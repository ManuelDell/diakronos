"""Rechte des Dev-Modus — serverseitig, fail closed.

Zugriff hat, wer **Administrator** ist oder die Rolle **Tester** traegt
(``has_role``). Ohne angemeldeten Benutzer, bei deaktiviertem Konto oder bei
ausgeschaltetem Dev-Modus gibt es keinen Zugriff — die Pruefung wirft dann
eine ``PermissionError`` der Compat-Schicht.

Die Rechte werden NICHT im Frontend entschieden: die SPA blendet nur aus, was
der Server ohnehin verweigert.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.exceptions import PermissionError
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.core import HasRole, User

ROLLE_TESTER = "Tester"
ADMIN_ROLLEN = ("Administrator", "System Manager")


def ist_admin(sitzung: Session, benutzer: str | None = None) -> bool:
    """Administrator/System Manager (dieselbe Definition wie im Plan-Rahmen).

    R-P1-8/W3: ueber `permissions.get_roles`, damit Ausschluss und Sperre
    greifen — eine eigene `Has Role`-Abfrage umging beide Schranken.
    """
    wer = benutzer or session.user
    if wer == "Administrator":
        return True
    if not wer or wer == "Guest":
        return False
    from diakronos_app.frappe_compat.permissions import get_roles

    return bool(set(get_roles(wer)) & set(ADMIN_ROLLEN))


def ist_tester(sitzung: Session, benutzer: str | None = None) -> bool:
    """Traegt der Benutzer die Rolle ``Tester``? — ueber `get_roles` (W3)."""
    wer = benutzer or session.user
    if not wer or wer == "Guest":
        return False
    from diakronos_app.frappe_compat.permissions import get_roles

    return ROLLE_TESTER in set(get_roles(wer))


def zugriff(sitzung: Session, benutzer: str | None = None) -> bool:
    """Darf dieser Benutzer den Dev-Modus benutzen?"""
    wer = benutzer or session.user
    if not wer or wer == "Guest":
        return False
    if wer != "Administrator":
        konto = sitzung.get(User, wer)
        if konto is None or not konto.enabled:
            return False
    return ist_admin(sitzung, wer) or ist_tester(sitzung, wer)


def pruefen(sitzung: Session, benutzer: str | None = None) -> str:
    """Prueft den Zugriff und liefert den Benutzernamen zurueck.

    Wirft ``PermissionError``, wenn kein Zugriff besteht. Fehlermeldungen sind
    absichtlich nicht unterscheidbar ("Zugriff verweigert.") — ein Nicht-Tester
    erfaehrt nicht, ob es die Rolle oder das Konto ist.
    """
    wer = benutzer or session.user
    if not zugriff(sitzung, wer):
        raise PermissionError("Zugriff verweigert.")
    return wer
