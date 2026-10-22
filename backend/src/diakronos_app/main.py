"""FastAPI-Anwendung — Skelett mit echtem /healthz.

/healthz fuehrt ECHTE Verbindungstests gegen Postgres und Redis aus.
Es wird kein Zustand gecacht; jeder Aufruf prueft die Abhaengigkeiten frisch.

Kein Radicale-Check (P8): Radicale wurde bewusst verworfen (CalDAV ist im
Backend portiert, P6b) — Begruendung: ein zweiter Terminspeicher waere eine
zweite Quelle der Wahrheit gewesen (s. `caldav/__init__.py`).
"""

import logging

from fastapi import FastAPI
from redis import Redis
from sqlalchemy import text

from diakronos_app import __version__
from diakronos_app.settings import settings
from diakronos_app.spa import mount_spa

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("diakronos_app")

app = FastAPI(title="Diakronos API", version=__version__)

# Request-Kontext (Client-IP / Kopfzeilen) fuer `frappe.request`-Ersatz.
# MUSS vor den Endpunkten registriert werden, damit portierte Funktionen
# waehrend des Aufrufs darauf zugreifen koennen.
from diakronos_app.request_context import RequestContextMiddleware  # noqa: E402

# A1b2 — die Umschaltung. Reihenfolge ist FACHLICH relevant:
#   `add_middleware` schiebt jede neue Schicht VOR die bisherigen, d.h. die
#   ZULETZT hinzugefuegte laeuft als erste. Deshalb steht hier die
#   Session-Middleware ZULETZT: sie setzt `session.user`, BEVOR die
#   CSRF-Pruefung und der Request-Kontext laufen.
#   Ablauf pro Request: Session -> CSRF -> RequestContext -> Endpunkt.
from diakronos_app.frappe_compat.auth_middleware import (  # noqa: E402
    CsrfMiddleware,
    SessionMiddleware,
)

# SEC1: Forward-Auth-Middleware. Sie MUSS VOR der Session-Middleware laufen,
# damit sie den Benutzer aus vertrauenswuerdigen Kopfzeilen setzen kann, bevor
# die Sitzung aus dem Cookie aufgeloest wird. `add_middleware` schiebt jede
# neue Schicht VOR die bisherigen — also wird ForwardAuth ZULETZT hinzugefuegt.
# Ablauf pro Request:
#   ForwardAuth -> Session -> CSRF -> RequestContext -> Endpunkt.
from diakronos_app.anmeldung.middleware import ForwardAuthMiddleware  # noqa: E402

app.add_middleware(RequestContextMiddleware)

# DM1: Dev-Modus-Ueberwachung. Sie MUSS NACH der Session-Aufloesung laufen,
# damit `session.user` gesetzt ist — sonst sieht sie nur "Guest" und sammelt
# nichts. `add_middleware` schiebt jede neue Schicht VOR die bisherigen, d.h.
# die ZULETZT hinzugefuegte laeuft als erste. Deshalb wird die Dev-Modus-
# Schicht HIER (vor Csrf/Session) hinzugefuegt: die Session-Schicht kommt
# spaeter dazu und laeuft damit VOR ihr.
# Ablauf pro Request: Session -> DevModus -> CSRF -> RequestContext -> Endpunkt.
from diakronos_app.devmodus import einstellungen as _devmodus_einstellungen  # noqa: E402

if _devmodus_einstellungen.aktiv():
    from diakronos_app.devmodus import ueberwachung as _devmodus_ueberwachung  # noqa: E402

    _devmodus_ueberwachung.installiere(app)
    logger.info("Dev-Modus ist eingeschaltet (DEVMODE_ENABLED).")

app.add_middleware(CsrfMiddleware)
app.add_middleware(SessionMiddleware)
app.add_middleware(ForwardAuthMiddleware)

# PF1: gzip fuer alle Antworten ueber 1 KB. Die Plan-/Stammdaten-Antworten sind
# grosse JSON-Koerper (Plan oeffnen ~200 KB); unkomprimiert kostet das im
# lokalen Netz spuerbar Uebertragungszeit. GZipMiddleware kommt aus Starlette
# (bereits Abhaengigkeit von FastAPI) — keine neue Abhaengigkeit.
# Reihenfolge: add_middleware schiebt jede neue Schicht VOR die bisherigen;
# gzip als aeusserste Schicht komprimiert damit auch die SPA-Assets und JSON.
from starlette.middleware.gzip import GZipMiddleware  # noqa: E402

app.add_middleware(GZipMiddleware, minimum_size=1024)

# Frappe-kompatible Endpunkte (/api/method/*, /api/resource/*).
# Bewusst unter dem Praefix /api gemountet, damit spaetere SPA-Statik-Auslieferung
# (/, /assets/*, SPA-Fallback) nicht kollidiert. Vertrag: backend/API_VERTRAG.md
from diakronos_app.frappe_compat import router as _compat_router  # noqa: E402

_compat_router.mount(app)

# Authenticated file delivery must precede the SPA catch-all.
from diakronos_app.files import router as _files_router  # noqa: E402

app.include_router(_files_router)

# OAuth callback keeps its original public path, but requires an admin session.
from diakronos_app.google_callback import router as _google_callback_router  # noqa: E402

app.include_router(_google_callback_router)

from diakronos_app.anmeldung.passwortseite import router as _passwort_router  # noqa: E402

app.include_router(_passwort_router)

# Socket.IO fuer `publish_realtime` (P6a). Der Pfad `/socket.io` ist der
# Default des JS-Clients (`io()`), die SPA verbindet sich ohne Optionen.
from diakronos_app.frappe_compat.realtime import socket_app  # noqa: E402

app.mount("/socket.io", socket_app)

# DM1: Dev-Modus (ersetzt die Testsuite). Die Endpunkte werden ueber den
# Import registriert; die Middleware wurde bereits oben eingehaengt (siehe
# Kommentar dort — Reihenfolge ist fachlich relevant). Ist `DEVMODE_ENABLED`
# nicht gesetzt, passiert hier nichts: keine Endpunkte, kein Monitoring.
from diakronos_app.devmodus import api as _devmodus_api  # noqa: E402

_devmodus_api.registriere(app)

# CalDAV (P6b) — portierter, NUR LESENDER DAV-Baum unter /dav/ und
# /.well-known/caldav. Eigener HTTP-Baum, NICHT ueber /api/method erreichbar:
# ein Kalender-Client schickt OPTIONS/PROPFIND/REPORT.
from diakronos_app.caldav import register_dav_routes  # noqa: E402

register_dav_routes(app)

# SEC1: /login, /auth/oidc/*, /logout. MUSS vor `mount_spa(app)` stehen — der
# SPA-Catch-all wuerde /login sonst schlucken.
from diakronos_app.anmeldung.routen import registriere_routen  # noqa: E402

registriere_routen(app)

# SEC1: Startpruefung der Anmeldekonfiguration laeuft NICHT beim Import (Tests
# importieren `main` mit eigenen Flags), sondern ueber den Container-Entrypoint
# (`python -m diakronos_app.anmeldung.startup`) — genau wie die Erstinstallation.

# BEIDES MUSS VOR `mount_spa(app)` STEHEN — der SPA-Catch-all wuerde sonst
# /socket.io und /dav/ verdecken. Reihenfolge in dieser Datei:
#   API-Router -> /healthz -> socket.io -> CalDAV -> Anmelde-Routen -> mount_spa.

# Die Erstinstallation (A1b3) laeuft NICHT hier beim Import, sondern im
# Container-Entrypoint per `python -m diakronos_app.erstinstallation` NACH
# `alembic upgrade head`. Grund: beim Import von `main` in Tests darf kein
# Bootstrap gegen die echte DB laufen, und die `user`-Tabelle existiert erst
# nach den Migrationen.


def _check_db() -> bool:
    """Echter Verbindungstest gegen PostgreSQL (SELECT 1)."""
    try:
        from diakronos_app.db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — Healthcheck darf nie werfen
        logger.warning("healthz: db check failed: %s", exc)
        return False


def _check_redis() -> bool:
    """Echter Verbindungstest gegen Redis (PING)."""
    try:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.healthcheck_timeout,
            socket_timeout=settings.healthcheck_timeout,
        )
        return bool(client.ping())
    except Exception as exc:  # noqa: BLE001
        logger.warning("healthz: redis check failed: %s", exc)
        return False


@app.get("/healthz")
def healthz() -> dict:
    db_ok = _check_db()
    redis_ok = _check_redis()
    all_ok = db_ok and redis_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }


@app.get("/", include_in_schema=False)
def wurzel():
    """Die Startadresse fuehrt in die SPA (relativ: gilt hinter jedem Proxy/jeder Domain)."""
    from starlette.responses import RedirectResponse

    return RedirectResponse("/diakonos", status_code=302)


# ──────────────────────────────────────────────────────────────────────────
# SPA-Auslieferung — MUSS ZULETZT registriert werden.
# Der Catch-all unter /diakonos wuerde sonst spaeter definierte Routen
# (/healthz, /api/*) verdecken. mount_spa() schliesst diese Praefixe
# zusaetzlich explizit aus.
# ──────────────────────────────────────────────────────────────────────────
mount_spa(app)
