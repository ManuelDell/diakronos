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


def _doku_adressen(einstellungen=None) -> tuple[str | None, str | None, str | None]:
    """SEC-4: Adressen von Swagger, ReDoc und OpenAPI — ohne Schalter `None`.

    Pentest-Befund 8: `/docs`, `/redoc` und `/openapi.json` waren ohne
    Anmeldung erreichbar und legten alle Pfade der App offen. `None` schaltet
    die jeweilige Route in FastAPI ab; sie antwortet dann 404. Eingeschaltet
    wird nur ueber `SEC_DOKU_OEFFENTLICH=1` (settings.py, Default aus).

    Eigene Funktion, damit die Regel genau EINE Quelle hat (Karte ist
    getestet) und `main` beim Import nichts weiter entscheiden muss.
    """
    s = einstellungen if einstellungen is not None else settings
    if getattr(s, "sec_doku_oeffentlich", False):
        return "/docs", "/redoc", "/openapi.json"
    return None, None, None


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

from diakronos_app.devmodus import einstellungen as _devmodus_einstellungen  # noqa: E402

from starlette.middleware.gzip import GZipMiddleware  # noqa: E402

from diakronos_app.sec_header import SicherheitsHeaderMiddleware  # noqa: E402

# WEB-5a: Pfad-Beschnitt fuer den Socket-Baum unter einem Praefix.
from diakronos_app.frappe_compat.socket_praefix import (  # noqa: E402
    PraefixSocketMiddleware,
)

# Frappe-kompatible Endpunkte (/api/method/*, /api/resource/*).
# Bewusst unter dem Praefix /api gemountet, damit spaetere SPA-Statik-Auslieferung
# (/, /assets/*, SPA-Fallback) nicht kollidiert. Vertrag: backend/API_VERTRAG.md
from diakronos_app.frappe_compat import router as _compat_router  # noqa: E402

# Authenticated file delivery must precede the SPA catch-all.
from diakronos_app.files import router as _files_router  # noqa: E402

# REG-1a: Bilder eines Anmeldeformulars — OEFFENTLICH, aber nur ueber den
# Registrierungstoken (`/public/registrierung/<token>/bild/<rolle>`). Muss
# ebenfalls VOR dem SPA-Catch-all stehen, sonst liefert die SPA ein HTML.
from diakronos_app.formularbilder_api import router as _formularbilder_router  # noqa: E402

# OAuth callback keeps its original public path, but requires an admin session.
from diakronos_app.google_callback import router as _google_callback_router  # noqa: E402

from diakronos_app.anmeldung.passwortseite import router as _passwort_router  # noqa: E402

# Socket.IO fuer `publish_realtime` (P6a). Der Pfad `/socket.io` ist der
# Default des JS-Clients (`io()`), die SPA verbindet sich ohne Optionen.
from diakronos_app.frappe_compat.realtime import socket_app  # noqa: E402

# DM1: Dev-Modus (ersetzt die Testsuite). Die Endpunkte werden ueber den
# Import registriert; die Middleware wurde bereits oben eingehaengt (siehe
# Kommentar dort — Reihenfolge ist fachlich relevant). Ist `DEVMODE_ENABLED`
# nicht gesetzt, passiert hier nichts: keine Endpunkte, kein Monitoring.
from diakronos_app.devmodus import api as _devmodus_api  # noqa: E402

# CalDAV (P6b) — portierter, NUR LESENDER DAV-Baum unter /dav/ und
# /.well-known/caldav. Eigener HTTP-Baum, NICHT ueber /api/method erreichbar:
# ein Kalender-Client schickt OPTIONS/PROPFIND/REPORT.
from diakronos_app.caldav import register_dav_routes  # noqa: E402

# SEC1: /login, /auth/oidc/*, /logout. MUSS vor `mount_spa(app)` stehen — der
# SPA-Catch-all wuerde /login sonst schlucken.
from diakronos_app.anmeldung.routen import registriere_routen  # noqa: E402


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


def _not_found():
    """WEB-5a: 404 der App, wenn die Adresse mit Praefix nicht ihr gehoert."""
    from starlette.responses import JSONResponse

    return JSONResponse({"detail": "Not Found"}, status_code=404)


def erstelle_app(einstellungen=None):
    """Baut die Anwendung: FastAPI, mit Praefix eine Starlette-Huelle darum.

    Warum als Funktion und nicht beim Import (SEC-4): die abgeschaltete
    API-Doku haengt an einer Einstellung und wird beim Anlegen von
    `FastAPI(...)` festgelegt. Als Import-Nebenwirkung liesse sich das nicht
    mehr pruefen (die Tests importieren `main` einmal je Prozess) und ein
    Umschalten ohne Neustart waere ausgeschlossen. `settings` ist modulweit
    gecacht; wer eine andere Umgebung pruefen will, leert diesen Cache und
    baut neu (`tests/test_sec4_header_doku.py`).
    """
    s = einstellungen if einstellungen is not None else settings

    # WEB-5a: der Prozess-Praefix steht ab hier fest. Alle Adressen, die
    # Laufzeitcode baut (`base_path.pfad` / `base_path.datei_url`), richten
    # sich danach. Leer = kein Praefix = unveraendertes Verhalten.
    from diakronos_app import base_path as _base_path

    praefix = _base_path.setze_praefix(getattr(s, "diakronos_base_path", ""))

    docs_url, redoc_url, openapi_url = _doku_adressen(s)
    app = FastAPI(
        title="Diakronos API",
        version=__version__,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )


    app.add_middleware(RequestContextMiddleware)

    # Dev-Modus-Ueberwachung: sie MUSS NACH der Session-Aufloesung laufen,
    # damit `session.user` gesetzt ist — sonst sieht sie nur "Guest" und sammelt
    # nichts. `add_middleware` schiebt jede neue Schicht VOR die bisherigen,
    # d.h. die ZULETZT hinzugefuegte laeuft als erste. Deshalb wird die
    # Dev-Modus-Schicht HIER (vor Csrf/Session) hinzugefuegt: die
    # Session-Schicht kommt spaeter dazu und laeuft damit VOR ihr.
    # Ablauf pro Request: Session -> DevModus -> CSRF -> RequestContext -> Endpunkt.
    if _devmodus_einstellungen.aktiv(s):
        from diakronos_app.devmodus import ueberwachung as _devmodus_ueberwachung

        _devmodus_ueberwachung.installiere(app)
        logger.info("Dev-Modus ist eingeschaltet (DEVMODE_ENABLED).")

    app.add_middleware(CsrfMiddleware)
    app.add_middleware(SessionMiddleware)
    app.add_middleware(ForwardAuthMiddleware)

    # PF1: gzip fuer alle Antworten ueber 1 KB. Die Plan-/Stammdaten-Antworten
    # sind grosse JSON-Koerper (Plan oeffnen ~200 KB); unkomprimiert kostet das
    # im lokalen Netz spuerbar Uebertragungszeit. GZipMiddleware kommt aus
    # Starlette (bereits Abhaengigkeit von FastAPI) — keine neue Abhaengigkeit.
    # Reihenfolge: add_middleware schiebt jede neue Schicht VOR die bisherigen;
    # gzip als aeusserste Schicht komprimiert damit auch die SPA-Assets und JSON.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # WEB-5a: Engine.IO vergleicht den ROHEN Pfad (es liest `root_path` nicht).
    # Unter dem Praefix muss der Pfad vorher beschnitten werden, sonst
    # antwortet der Handshake 404 — Begruendung und Messung in
    # `frappe_compat/socket_praefix.py`. Ohne Praefix wirkungslos.
    # Steht VOR der Kopfzeilen-Schicht, damit die Kopfzeilen die aeusserste
    # Schicht bleiben (sec4-Waechter); inhaltlich beruehren sie sich nicht:
    # diese Schicht aendert nur den Pfad.
    app.add_middleware(PraefixSocketMiddleware, praefix=praefix)

    # SEC-4: Sicherheits-Kopfzeilen (HSTS, CSP, X-Frame-Options,
    # X-Content-Type-Options, Referrer-Policy) auf JEDER Antwort.
    # Diese Schicht wird ZULETZT hinzugefuegt und laeuft damit als aeusserste —
    # so bekommen auch Antworten die Kopfzeilen, die eine innere Schicht selbst
    # abschliesst (CSRF 417, Anmeldung 401, Fehlerseiten des Servers).
    # Sie UEBERSCHREIBT keine vorhandene Kopfzeile: engere Policies einzelner
    # Endpunkte (z.B. `default-src 'none'; sandbox` bei Formularbildern) bleiben.
    # Ablauf pro Request danach:
    #   Kopfzeilen -> gzip -> ForwardAuth -> Session -> DevModus -> CSRF
    #   -> RequestContext -> Endpunkt.
    app.add_middleware(SicherheitsHeaderMiddleware)

    _compat_router.mount(app)

    app.include_router(_files_router)
    app.include_router(_formularbilder_router)
    # ON-2: das Gemeinde-Logo ist OEFFENTLICH (Anmeldeseite, Website) und muss
    # deshalb ebenfalls VOR dem SPA-Catch-all stehen.
    from diakronos_app.gemeinde_logo import registriere as _registriere_logo

    _registriere_logo(app)
    app.include_router(_google_callback_router)
    app.include_router(_passwort_router)

    app.mount("/socket.io", socket_app)

    _devmodus_api.registriere(app)

    register_dav_routes(app)

    # SEC1: /login, /auth/oidc/*, /logout. MUSS vor `mount_spa(app)` stehen.
    registriere_routen(app)

    # BS-1b: oeffentliche Website-Ausgabe als eigene Routen (iCal-Feed,
    # Bild-Route, CORS-Variante der Lese-API). Ebenfalls VOR dem SPA-Catch-all
    # — sonst liefert die SPA auf `/website/…` HTML. Unter dem Betriebs-
    # Praefix (`DIAKRONOS_BASE_PATH`) liegen sie automatisch mit, weil der
    # ganze Bau unter dem Mount haengt.
    from diakronos_app.website.oeffentlich_api import registriere_routen as _website_oeffentlich_routen

    _website_oeffentlich_routen(app)

    # ON-1: Seiten der Ersteinrichtung (`/einrichtung/<token>`) — ebenfalls
    # NACH `anmeldung.routen` und VOR `mount_spa(app)`. Sie bringen ihren
    # eigenen CSRF-Schutz mit (Herkunft + Masken-Token, SEC-4).
    from diakronos_app.anmeldung.einrichtung_routen import (
        registriere_routen as _registriere_einrichtung,
    )

    _registriere_einrichtung(app)

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
        """Die Startadresse fuehrt in die SPA (relativ: gilt hinter jedem Proxy/jeder Domain).

        WEB-5a: MIT Praefix gehoert `/` der Website — die App antwortet 404
        und leitet nichts um (die Wurzel ist nicht ihre). Der Alias
        `{Praefix}` -> `{Praefix}/diakonos` sitzt in `base_path.praefigiere`.
        """
        from starlette.responses import RedirectResponse

        if _base_path.aktiver_praefix():
            return _not_found()
        return RedirectResponse("/diakonos", status_code=302)

    # ──────────────────────────────────────────────────────────────────────
    # SPA-Auslieferung — MUSS ZULETZT registriert werden.
    # Der Catch-all unter /diakonos wuerde sonst spaeter definierte Routen
    # (/healthz, /api/*) verdecken. mount_spa() schliesst diese Praefixe
    # zusaetzlich explizit aus.
    # ──────────────────────────────────────────────────────────────────────
    mount_spa(app)

    # ──────────────────────────────────────────────────────────────────────
    # WEB-5a: der ganze Betrieb unter `DIAKRONOS_BASE_PATH`.
    # MUSS ZULETZT kommen: erst wenn alle Routen stehen, wird die komplette
    # Anwendung (inkl. socket.io und /healthz) unter den Praefix gehaengt.
    # Ohne Praefix kommt die Anwendung unveraendert zurueck.
    # ──────────────────────────────────────────────────────────────────────
    return _base_path.praefigiere(app, praefix)


# Die Anwendung des Prozesses. `uvicorn diakronos_app.main:app` und der
# TestClient greifen genau hierauf zu.
app = erstelle_app()

