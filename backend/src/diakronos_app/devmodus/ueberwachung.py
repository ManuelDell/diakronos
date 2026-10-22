"""Backend-Ueberwachung des Dev-Modus (DM1).

Die Middleware ordnet jede fehlerhafte Anfrage der laufenden Dev-Sitzung des
angemeldeten Benutzers zu. Verbindlich ist die laufende Sitzung, die der
Server zu diesem Benutzer kennt (``dm_sitzung``) — nicht ein Wert vom Client.
Ohne laufende Dev-Sitzung bricht die Middleware nach einem Nachschlag ab:
normale Nutzer haben dadurch keinen Mehraufwand.

Erfasst werden:

* Antworten mit Status 4xx/5xx (Methode, Pfad, Status, Dauer, Request-ID,
  Meldung inkl. strukturierter Planrahmen-Meldungen ``pfad/code/meldung``),
* unbehandelte Exceptions inklusive Traceback,
* Log-Eintraege ab WARNING aus dem Request-Kontext,
* langsame Anfragen (> 1 s).

Alle Texte laufen durch ``redaktion``, bevor sie gespeichert werden.
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from diakronos_app import db
from diakronos_app.frappe_compat.session import session as frappe_session
from diakronos_app.devmodus import dienste, einstellungen
from diakronos_app.devmodus.einstellungen import LANGSAM_MS
from diakronos_app.devmodus.redaktion import redigiere

logger = logging.getLogger("diakronos_app.devmodus")

#: Eigene Pfade werden nie erfasst — die SPA fragt im Sekundentakt nach dem
#: Fehlerumfeld; das waere Rauschen und wuerde die Liste unlesbar machen.
AUSGENOMMEN = ("/api/method/diakronos.devmodus.api.", "/healthz")


class DevmodusMiddleware(BaseHTTPMiddleware):
    """Ordnet Fehler und Auffaelligkeiten der laufenden Dev-Sitzung zu."""

    async def dispatch(self, request: Request, call_next):
        if not einstellungen.aktiv():
            return await call_next(request)

        pfad = request.url.path
        if pfad.startswith(AUSGENOMMEN):
            return await call_next(request)

        benutzer = self._benutzer()
        if not benutzer or benutzer == "Guest":
            return await call_next(request)
        if not self._sitzung_laeuft(benutzer):
            # Kein Mehraufwand ohne laufende Dev-Sitzung.
            return await call_next(request)

        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        fehler: BaseException | None = None
        antwort = None
        protokoll = _ProtokollAufzeichner()
        root = logging.getLogger()
        root.addHandler(protokoll)
        try:
            antwort = await call_next(request)
        except BaseException as exc:  # noqa: BLE001 — wird weitergeworfen
            fehler = exc
            raise
        finally:
            root.removeHandler(protokoll)
            dauer_ms = int((time.perf_counter() - start) * 1000)
            try:
                self._schreiben(benutzer, request, antwort, fehler,
                                dauer_ms, request_id, protokoll.eintraege)
            except Exception:  # noqa: BLE001 — Ueberwachung darf nie den Aufruf kippen
                logger.warning("Dev-Modus-Ueberwachung konnte nicht speichern",
                               exc_info=True)
        if antwort is not None:
            antwort.headers["X-Request-Id"] = request_id
        return antwort

    @staticmethod
    def _benutzer() -> str:
        try:
            return frappe_session.user or "Guest"
        except Exception:  # noqa: BLE001
            return "Guest"

    @staticmethod
    def _sitzung_laeuft(benutzer: str) -> bool:
        try:
            with db.SessionLocal() as s:
                return dienste.sitzung_aktiv(s, benutzer) is not None
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _schreiben(benutzer: str, request: Request, antwort,
                   fehler: BaseException | None, dauer_ms: int, request_id: str,
                   logs: list[logging.LogRecord]) -> None:
        status = getattr(antwort, "status_code", None) if antwort is not None else None
        with db.SessionLocal.begin() as s:
            if fehler is not None:
                dienste.ereignis_speichern(
                    s, benutzer=benutzer, art="exception",
                    methode=request.method, pfad=request.url.path,
                    status=500, dauer_ms=dauer_ms, request_id=request_id,
                    meldung=str(fehler),
                    traceback_text="".join(traceback.format_exception(
                        type(fehler), fehler, fehler.__traceback__)),
                )
            elif status is not None and status >= 500:
                dienste.ereignis_speichern(
                    s, benutzer=benutzer, art="http_5xx",
                    methode=request.method, pfad=request.url.path, status=status,
                    dauer_ms=dauer_ms, request_id=request_id,
                    meldung=f"HTTP {status}",
                )
            elif status is not None and status >= 400:
                dienste.ereignis_speichern(
                    s, benutzer=benutzer, art="http_4xx",
                    methode=request.method, pfad=request.url.path, status=status,
                    dauer_ms=dauer_ms, request_id=request_id,
                    meldung=f"HTTP {status}",
                )
            if dauer_ms >= LANGSAM_MS:
                dienste.ereignis_speichern(
                    s, benutzer=benutzer, art="langsam",
                    methode=request.method, pfad=request.url.path, status=status,
                    dauer_ms=dauer_ms, request_id=request_id,
                    meldung=f"{dauer_ms} ms",
                )
            for eintrag in logs:
                dienste.ereignis_speichern(
                    s, benutzer=benutzer, art="log",
                    methode=request.method, pfad=request.url.path,
                    request_id=request_id,
                    meldung=f"{eintrag.levelname}: {eintrag.getMessage()}",
                )


class _ProtokollAufzeichner(logging.Handler):
    """Sammelt Log-Eintraege ab WARNING waehrend EINES Requests."""

    def __init__(self, grenze: int = 20) -> None:
        super().__init__(level=logging.WARNING)
        self.eintraege: list[logging.LogRecord] = []
        self.grenze = grenze

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        if len(self.eintraege) < self.grenze:
            self.eintraege.append(record)


def installiere(app) -> bool:
    """Haengt die Middleware ein, wenn der Dev-Modus aktiv ist."""
    if not einstellungen.aktiv():
        return False
    app.add_middleware(DevmodusMiddleware)
    return True


__all__ = ["DevmodusMiddleware", "installiere", "AUSGENOMMEN"]
