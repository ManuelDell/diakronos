"""Gemeinsame Schreibstelle fuer In-App-Benachrichtigungen.

Keine eigene Transaktion: im Request wird dessen Sitzung verwendet.
Benachrichtigungen sind Beiwerk und duerfen den Fachvorgang nicht abbrechen.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.api_helpers import _create, log_error
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied


def user_zu_mitglied(session: Session, mitglied: str | None) -> str | None:
    """Aktives Konto zum Mitglied; E-Mail nur bei eindeutiger Zuordnung."""
    if not mitglied:
        return None
    person = session.get(Mitglied, mitglied)
    if person is None:
        return None
    name = person.user
    if not name and person.email:
        treffer = session.scalars(select(User.name).where(User.email == person.email)).all()
        name = treffer[0] if len(treffer) == 1 else None
    konto = session.get(User, name) if name else None
    return konto.name if konto is not None and konto.enabled else None


def schreibe_meldung(*, for_user: str, subject: str, inhalt: str,
                     document_type: str = "", document_name: str = "",
                     typ: str = "Alert") -> bool:
    """Schreibt eine Nachricht; Fehler werden gemeldet, nicht weitergeworfen."""
    if not for_user:
        return False
    try:
        _create("Notification Log", {
            "subject": subject, "for_user": for_user, "type": typ,
            "email_content": inhalt, "document_type": document_type or "",
            "document_name": document_name or "", "read": 0,
        })
        return True
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"benachrichtigung {document_name}")
        return False
