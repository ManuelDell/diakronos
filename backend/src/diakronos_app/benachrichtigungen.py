"""Gemeinsame Schreibstelle fuer In-App-Benachrichtigungen.

Keine eigene Transaktion: im Request wird dessen Sitzung verwendet.
Benachrichtigungen sind Beiwerk und duerfen den Fachvorgang nicht abbrechen.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.api_helpers import _create, _now, log_error
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


def _angemeldet() -> str | None:
    """Das angemeldete Konto (für ``owner``/``modified_by`` wie bei ``_create``).

    Scheduler-Läufe haben keinen Benutzer — dann bleibt das Feld leer, genau
    wie ``_create`` es mit einem leeren ``session.user`` schriebe.
    """
    from diakronos_app.frappe_compat.session import session

    return getattr(session, "user", None) or None


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


def _neu_anlegen(session: Session, werte: dict) -> str:
    """Eine ``Notification Log``-Zeile in DIESER Sitzung anlegen.

    Gegenstück zu ``_create`` für den Fall, dass der Aufrufer bereits eine
    Sitzung hat: die Zeile wird direkt in IHR angelegt (Savepoint, damit ein
    Fehler nur diese Glocke zurücknimmt) und committet mit der Fach-Transaktion
    des Aufrufers. ``_create`` würde dieselbe Zeile über
    ``sitzung_fuer_lesen`` schreiben; das ist hier unnötig, weil die Sitzung
    schon feststeht.

    Zeitstempel wie bei ``_create`` (``api_helpers._meta_fields``): ``creation``
    und ``modified`` in **UTC** (``_now``) — die Oberfläche liest UTC, und die
    Glockenliste mischt sonst Wand- und UTC-Zeit in ihrer Sortierung
    (Review R1/3). ``owner``/``modified_by`` setzt ``_create`` ebenso auf das
    angemeldete Konto; hier wird das übergeben (leer, wenn niemand angemeldet
    ist — die Sitzung im Scheduler hat keinen Benutzer).
    """
    import uuid as _uuid

    from diakronos_app.models.core import NotificationLog

    werte = dict(werte)
    werte.setdefault("name", f"{_uuid.uuid4().hex[:8]}-{_uuid.uuid4().hex[:1]}")
    werte.setdefault("creation", _now())
    werte.setdefault("modified", werte["creation"])
    zeile = NotificationLog(**werte)
    with session.begin_nested():
        session.add(zeile)
        session.flush()
    return str(zeile.name)


def glocke_setzen(*, for_user: str, subject: str, inhalt: str,
                  document_type: str, document_name: str,
                  typ: str = "Alert", session: Session | None = None,
                  nur_fortschreiben: bool = False,
                  nur_zahl: bool = False) -> str:
    """Bündel-Glocke schreiben: vorhandene UNGELESENE aktualisieren, sonst neu.

    Liefert die Kennung der ``Notification Log``-Zeile (oder ``""``, wenn das
    Schreiben scheitert — Benachrichtigungen sind Beiwerk). Der Aufrufer merkt
    sich in ``chat_glocke``, bis wohin geglockt wurde; hier wird KEIN
    Nachrichtentext und KEIN Absender abgelegt (Konzept 4.5).

    ``session`` (CHAT-4b): die Sitzung des AUFRUFERS. Ohne sie wird über
    ``_laufende_sitzung`` die laufende Sitzung genommen (und nur, wenn keine
    läuft, eine eigene) — das ist auch das Verhalten auf main: ``_create``
    legt über ``sitzung_fuer_lesen`` in der AKTUELLEN Sitzung an. Der Parameter
    macht die Zuordnung ausdrücklich: Prüfen, Anlegen und Fortschreiben laufen
    dann alle in DERSELBEN Sitzung, und der Aufrufer committet eine Wahrheit,
    statt sich darauf zu verlassen, dass kein anderer Sitzungskontext aktiv ist.

    Eine AKTUALISIERTE Glocke bekommt ``modified`` = jetzt (Existenz des
    Feldes genügt: ``creation`` sagt, wann es die Glocke zuerst gab,
    ``modified``, wann sie zuletzt etwas Neues zu sagen hatte — sonst stünde
    die fortgeschriebene Glocke in der Liste an ihrem alten Platz). Beide
    Zeitstempel sind UTC (``api_helpers._now``) wie bei ``_create``: die
    Oberfläche liest UTC, und die Glockenliste sortiert nach
    ``coalesce(modified, creation)`` — Wandzeit mischte sich dort ein
    (Review R1/3).

    Keine eigene Transaktion: es gilt die Sitzung des Aufrufs, damit Merker
    und Glocke gemeinsam committen oder gemeinsam scheitern (ein Fehler wird
    VORHER in einem Savepoint zurückgenommen: eine kaputte Benachrichtigung
    darf die Fach-Transaktion des Aufrufers nicht unbrauchbar machen).

    ``nur_fortschreiben`` (CHAT-4b, Review R1/4): es wird NUR eine bestehende
    UNGELESENE Zeile fortgeschrieben, nie eine neue angelegt. Der Aufruf, der
    eine Zahl nachführt (``lesestand_setzen``), darf keine Glocke
    wiederbeleben, die die Person weggeklickt hat — dann bleibt es bei ``""``
    wie bei jedem Schreibfehler.

    ``nur_zahl`` (CHAT-7a, Punkt 6): die Zeile wird fortgeschrieben, aber
    ``modified`` bleibt STEHEN. Beim teilweisen Lesen ändert sich nur die
    Zahl; die Glocke soll in der Liste nicht nach oben springen — das ist
    allein Sache einer neuen Nachricht (Aufruf ohne ``nur_zahl``).
    ``modified_by`` wird dabei mitgeführt (es ist keine Sortiergröße), der
    Anlass der Zeile bleibt der alte.
    """
    from diakronos_app import db as dbmod

    if not for_user or not document_name:
        return ""
    sess: Session = session if session is not None else _laufende_sitzung(dbmod)
    # ``owner``/``modified_by`` wie ``_create``: das angemeldete Konto, sofern
    # eines angemeldet ist (Scheduler-Läufe haben keines).
    konto = _angemeldet()
    try:
        zeile = _glocke_zeile(sess, for_user=for_user,
                              document_type=document_type,
                              document_name=document_name)
        if zeile is None:
            if nur_fortschreiben:
                return ""
            return _neu_anlegen(sess, {
                "subject": subject, "for_user": for_user, "type": typ,
                "email_content": inhalt, "document_type": document_type,
                "document_name": document_name, "read": 0,
                "owner": konto, "modified_by": konto,
            }) or ""
    except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
        log_error(str(ex), f"glocke {document_name}")
        return ""
    # Ab hier steht die Zeile: das UPDATE läuft im SAVEPOINT, damit ein Fehler
    # nur DIESE Glocke zurücknimmt (der Aufrufer kann weiterarbeiten und meldet
    # über den leeren Rückgabewert, dass es nicht geklappt hat).
    try:
        with sess.begin_nested():
            zeile.subject = subject
            zeile.email_content = inhalt
            zeile.read = False
            if not nur_zahl:
                # UTC wie ``creation`` (Review R1/3): beide Zeitstempel
                # derselben Zeile müssen dieselbe Uhr tragen, sonst mischt die
                # Sortierung ``coalesce(modified, creation)`` zwei Zeitbasen.
                # ``nur_zahl`` lässt den Anlass stehen (CHAT-7a, Punkt 6).
                zeile.modified = _now()
            if konto:
                zeile.modified_by = konto
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
