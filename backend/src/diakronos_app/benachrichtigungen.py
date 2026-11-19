"""Gemeinsame Schreibstelle fuer In-App-Benachrichtigungen.

Keine eigene Transaktion: im Request wird dessen Sitzung verwendet.
Benachrichtigungen sind Beiwerk und duerfen den Fachvorgang nicht abbrechen.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.api_helpers import _create, log_error
from diakronos_app.models.core import NotificationLog, User
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


def _jetzt() -> datetime:
    """Jetzt als Wandzeit der Gemeinde, ohne Zeitzone (wie in ``api.chat``)."""
    from diakronos_app.zeit import jetzt_wanduhr

    return jetzt_wanduhr()


def _laufende_sitzung(dbmod) -> Session:
    """Die offene Sitzung des Aufrufs (oder eine neue, falls keine läuft).

    Glocken sind Beiwerk, aber der Merker ``chat_glocke.stand`` muss in
    DERSELBEN Transaktion stehen wie die Glocke. Läuft bereits ein Vorgang
    (``als_aktuelle_sitzung``), wird dessen Sitzung benutzt; andernfalls eine
    eigene, die der Aufrufer nicht committen muss (``_create`` committet).
    """
    vorhanden = getattr(dbmod, "aktuelle_sitzung", None)
    if vorhanden is not None:
        try:
            sess = vorhanden.get()
        except Exception:  # noqa: BLE001 — hier ist jede Sitzung besser als keine
            sess = None
        if sess is not None:
            return sess
    return dbmod.SessionLocal()


def _glocke_zeile(session: Session, *, for_user: str, document_type: str,
                  document_name: str) -> NotificationLog | None:
    """Die jüngste UNGELESENE Glocke zu (Konto, Dokumentart, Dokument).

    Genau diese Zeile wird beim Bündeln AKTUALISIERT statt eine zweite
    anzulegen — sonst stünde für dasselbe Gespräch eine Glocke je Meldung.
    """
    return session.scalars(
        select(NotificationLog)
        .where(NotificationLog.for_user == for_user,
               NotificationLog.document_type == document_type,
               NotificationLog.document_name == document_name,
               NotificationLog.read.is_(False))
        .order_by(NotificationLog.creation.desc(), NotificationLog.name.desc())
        .limit(1)
    ).first()


def glocke_setzen(*, for_user: str, subject: str, inhalt: str,
                  document_type: str, document_name: str,
                  typ: str = "Alert") -> str:
    """Bündel-Glocke schreiben: vorhandene UNGELESENE aktualisieren, sonst neu.

    Liefert die Kennung der ``Notification Log``-Zeile (oder ``""``, wenn das
    Schreiben scheitert — Benachrichtigungen sind Beiwerk). Der Aufrufer merkt
    sich in ``chat_glocke``, bis wohin geglockt wurde; hier wird KEIN
    Nachrichtentext und KEIN Absender abgelegt (Konzept 4.5).

    Eine AKTUALISIERTE Glocke bekommt ``modified`` = jetzt (Existenz des
    Feldes genügt: ``creation`` sagt, wann es die Glocke zuerst gab,
    ``modified``, wann sie zuletzt etwas Neues zu sagen hatte — sonst stünde
    die fortgeschriebene Glocke in der Liste an ihrem alten Platz).

    Keine eigene Transaktion: es gilt die Sitzung des Aufrufs, damit Merker
    und Glocke gemeinsam committen oder gemeinsam scheitern (ein Fehler wird
    VORHER in einem Savepoint zurückgenommen: eine kaputte Benachrichtigung
    darf die Fach-Transaktion des Aufrufers nicht unbrauchbar machen).

    ACHTUNG: ``SessionLocal()`` ist bewusst NICHT der Weg — der Aufrufer hat
    seine Sitzung bereits offen, und eine zweite Sitzung sähe den Merker des
    laufenden Vorgangs nicht. Geschrieben wird über ``_create`` (es committet
    selbst; eine Benachrichtigung ist Beiwerk und darf den Fachvorgang nicht
    mitreißen) bzw. über ein UPDATE in genau dieser Sitzung.
    """
    from diakronos_app import db as dbmod

    if not for_user or not document_name:
        return ""
    session: Session = _laufende_sitzung(dbmod)
    try:
        zeile = _glocke_zeile(session, for_user=for_user,
                              document_type=document_type,
                              document_name=document_name)
        if zeile is None:
            return _create("Notification Log", {
                "subject": subject, "for_user": for_user, "type": typ,
                "email_content": inhalt, "document_type": document_type,
                "document_name": document_name, "read": 0,
            }) or ""
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"glocke {document_name}")
        return ""
    # Ab hier steht die Zeile: das UPDATE läuft im SAVEPOINT, damit ein Fehler
    # nur DIESE Glocke zurücknimmt (der Aufrufer kann weiterarbeiten und meldet
    # über den leeren Rückgabewert, dass es nicht geklappt hat).
    try:
        with session.begin_nested():
            zeile.subject = subject
            zeile.email_content = inhalt
            zeile.read = False
            zeile.modified = _jetzt()
        return str(zeile.name)
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"glocke {document_name}")
        return ""


def glocke_gelesen(*, for_user: str, document_type: str, document_name: str) -> int:
    """Alle ungelesenen Glocken zu (Konto, Dokument) als gelesen markieren.

    Rückgabe: Zahl der geänderten Zeilen. Fehler werden gemeldet, nicht
    weitergeworfen (Beiwerk, wie oben).
    """
    from diakronos_app import db as dbmod

    if not for_user or not document_name:
        return 0
    try:
        session: Session = _laufende_sitzung(dbmod)
        zeilen = session.scalars(
            select(NotificationLog)
            .where(NotificationLog.for_user == for_user,
                   NotificationLog.document_type == document_type,
                   NotificationLog.document_name == document_name,
                   NotificationLog.read.is_(False))
        ).all()
        for zeile in zeilen:
            zeile.read = True
        session.flush()
        return len(zeilen)
    except Exception as ex:  # noqa: BLE001
        log_error(str(ex), f"glocke gelesen {document_name}")
        return 0
