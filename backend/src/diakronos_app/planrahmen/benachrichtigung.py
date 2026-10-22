"""Benachrichtigungen des Plan-Rahmens (OP-HANDY-6, Konzept B10).

Bis hierher erzeugte NUR ``api/admin_hub`` und das Ablehnen im Kalender einen
Eintrag in ``Notification Log``. Plan-Veroeffentlichung, Terminaenderung und
Buchungsentscheidung liefen still: die betroffenen Mitglieder erfuhren nichts.

Diese Datei ist die EINE Stelle, an der der Plan-Rahmen Benachrichtigungen
schreibt — aus demselben Grund wie ``Notification Log`` (Frappe-Core): sie
ist die Quelle, die ``api.audit.get_my_notifications`` ausliefert und die
``useNotifications`` in der Oberflaeche anzeigt.

Regeln:
* Empfaenger ist immer der USER, nicht das Mitglied (``for_user``). Ein
  Mitglied ohne Benutzerkonto kann nicht benachrichtigt werden — das ist
  ausdruecklich kein Fehler.
* Schreiben ist BEIWERK: ein Fehler beim Benachrichtigen darf den ausloesenden
  Fachvorgang niemals scheitern lassen (Vorbild: ``kanban_api._benachrichtige_owner``).
* Kein Commit, kein Rollback — die Benachrichtigung gehoert in die Transaktion
  des Aufrufers (``dienste``-Schreiber committen selbst).
"""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session

from diakronos_app.benachrichtigungen import schreibe_meldung, user_zu_mitglied
from diakronos_app.models.diakonos import Mitglied

# Nur diese Typen werden geschrieben (Frappe-Core kennt diese Werte).
TYP_ALERT = "Alert"
TYP_MENTION = "Mention"


def benachrichtige(
    session: Session,
    empfaenger_user: Iterable[str | None],
    *,
    subject: str,
    inhalt: str,
    document_type: str | None = None,
    document_name: str | None = None,
    typ: str = TYP_ALERT,
) -> int:
    """Schreibt je Empfaenger eine ``Notification Log``-Zeile. Gibt die Zahl zurueck.

    Doppelte/leere Empfaenger werden zusammengefasst; sich selbst nicht
    doppelt benachrichtigen bleibt dem Aufrufer ueberlassen.
    """
    geschrieben = 0
    for user in dict.fromkeys(u for u in empfaenger_user if u):
        if schreibe_meldung(for_user=user, subject=subject, inhalt=inhalt,
                            document_type=document_type or "", document_name=document_name or "",
                            typ=typ):
            geschrieben += 1
    return geschrieben


def empfaenger_aus_eintraegen(session: Session, wert: Any) -> set[str]:
    """Mitglied-Kennungen aus einem Eintragswert (Person oder Personenliste)."""
    roh = wert if isinstance(wert, list) else [wert]
    treffer: set[str] = set()
    for kennung in roh:
        if isinstance(kennung, str) and session.get(Mitglied, kennung) is not None:
            treffer.add(kennung)
    return treffer


def meldung_plan_veroeffentlicht(plan_titel: str, anzahl: int, erstveroeffentlichung: bool) -> tuple[str, str]:
    """Betreff und Text der Plan-Benachrichtigung (verstaendlich, ohne Fachbegriffe)."""
    if erstveroeffentlichung:
        betreff = f"Neuer Plan: {plan_titel}"
        inhalt = (f"Der Plan \u201e{plan_titel}\u201c wurde ver\u00f6ffentlicht. "
                  f"Du kannst deine Dienste unter \u201eMeine Dienste\u201c einsehen.")
    else:
        betreff = f"Plan ge\u00e4ndert: {plan_titel}"
        inhalt = (f"Der Plan \u201e{plan_titel}\u201c wurde ge\u00e4ndert "
                  f"({anzahl} \u00c4nderung(en)). Bitte pr\u00fcfe deine Dienste unter "
                  f"\u201eMeine Dienste\u201c.")
    return betreff, inhalt


__all__ = [
    "TYP_ALERT",
    "TYP_MENTION",
    "benachrichtige",
    "empfaenger_aus_eintraegen",
    "meldung_plan_veroeffentlicht",
    "user_zu_mitglied",
]
