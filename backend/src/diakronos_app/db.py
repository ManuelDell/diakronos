"""SQLAlchemy-Engine + Session-Factory.

Die Modelle liegen in `diakronos_app.models`. `Base` wird von dort
re-exportiert, damit Alembic (`target_metadata = Base.metadata`) und der
Rest der Anwendung dieselbe Metadata sehen. Der Import des Pakets
`diakronos_app.models` ist noetig, damit alle Modellklassen registriert sind,
bevor Alembic autogeneriert.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import diakronos_app.models  # noqa: F401  (registriert alle Modelle in Base.metadata)
from diakronos_app.models.base import Base
from diakronos_app.settings import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Die Sitzung, die der aktuelle Aufruf bereits geoeffnet hat (Request-Rahmen
# `_endpunkt`: `with SessionLocal.begin() as s`). Kurzlebige LESE-Helfer
# (`frappe_compat.db.count`, `query.get_all`, `get_value`) benutzen sie statt
# eine zweite Sitzung zu oeffnen.
#
# Grund: auf Datenbanken, die EINE Verbindung je Engine teilen (SQLite
# StaticPool im Test), reisst das `close()` einer zweiten Sitzung die noch
# offene Transaktion der Aufrufer-Sitzung mit — geflushte, nicht committete
# Schreibungen verschwinden still. Ausserdem spart es auf jeder Datenbank eine
# ueberzaehlige Verbindung. Schreib-Helfer bleiben unberuehrt: sie committen
# ausdruecklich und schliessen ihre eigene Sitzung.
aktuelle_sitzung: ContextVar[Session | None] = ContextVar("diakronos_aktuelle_sitzung", default=None)


def sitzung_fuer_lesen() -> tuple[Session, bool]:
    """Sitzung fuer einen LESE-Zugriff: ``(session, eigene)``.

    ``eigene=False`` heisst: die Sitzung gehoert dem Aufruf-Kontext und darf
    NICHT geschlossen werden. ``eigene=True`` heisst: der Aufrufer muss sie
    schliessen.
    """
    vorhanden = aktuelle_sitzung.get()
    if vorhanden is not None:
        return vorhanden, False
    return SessionLocal(), True


@contextmanager
def lesesitzung() -> Iterator[Session]:
    """Passende Sitzung fuer einen Lese-Helfer (schliesst nur eigene).

    Eine GELIEHENE Sitzung wird nicht zurueckgegeben und NICHT aufgeraeumt:
    `Session.close()` gibt die Verbindung zurueck und rollt sie dabei zurueck.
    Auf einer Datenbank, die eine Verbindung je Engine teilt, reisst schon das
    die offene Transaktion des Aufrufers mit — beim Import verschwand so der
    Speicherpunkt (SEC-c, „no such savepoint“). `expire_all()` waere der
    naechste Fehler: `SessionLocal` hat `autoflush=False`, ein `expire_all`
    verwirft also ungeflushte Aenderungen des Aufrufers still (SEC-d, W2).
    Wer eine geliehene Sitzung bekommt, laesst sie in Ruhe.
    """
    sess, eigene = sitzung_fuer_lesen()
    try:
        yield sess
    finally:
        if eigene:
            sess.close()


@contextmanager
def als_aktuelle_sitzung(session: Session) -> Iterator[Session]:
    """Markiert ``session`` als aktuelle Aufruf-Sitzung (Request-Rahmen)."""
    token = aktuelle_sitzung.set(session)
    try:
        yield session
    finally:
        aktuelle_sitzung.reset(token)


__all__ = ["Base", "engine", "SessionLocal", "aktuelle_sitzung", "sitzung_fuer_lesen",
           "lesesitzung", "als_aktuelle_sitzung"]
