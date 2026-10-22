"""Forward-Auth-Middleware (SEC1, TEIL B).

Laeuft VOR der `SessionMiddleware`. Hat der Browser die Authentik-Sitzung
(Forward-Auth), schickt der Proxy bei JEDEM Request die Kopfzeilen mit. Ist
Forward-Auth aktiv und vertrauenswuerdig, aber der Request bringt noch keine
gueltige Diakronos-Sitzung, wird still eine angelegt ("silent login"): Konto
zuordnen, Sitzung anlegen, Cookie setzen. Der Nutzer merkt so nur EINEN Login.

Die Kopfzeilen werden ausschliesslich ueber `proxy_header.konto_aus_kopfzeilen`
ausgewertet — also nur bei voller Vertrauenslage (Peer-Adresse in TRUSTED_IPS
UND korrektes Geheimnis). Sonst passiert NICHTS: es wird weder ein Benutzer
gesetzt noch ein Cookie ausgegeben.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from diakronos_app.anmeldung import proxy_header
from diakronos_app.anmeldung.konfiguration import proxy_header_aktiv
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers
from diakronos_app.frappe_compat.session import user_uebersteuert

logger = logging.getLogger("diakronos_app.anmeldung.middleware")

__all__ = ["ForwardAuthMiddleware"]

# Pfade, bei denen Forward-Auth NICHT greifen darf: CalDAV (eigene Auth),
# Healthcheck, OIDC-Routen selbst und der Google-Callback (eigener Admin-Gate).
AUSGENOMMEN = (
    "/healthz",
    "/dav/",
    "/.well-known/caldav",
    "/google-calendar-callback",
    "/auth/oidc/",
)


def _ausgenommen(pfad: str) -> bool:
    """True, wenn der Pfad NICHT ueber Forward-Auth laufen darf."""
    return any(pfad == p or pfad.startswith(p) for p in AUSGENOMMEN)


class ForwardAuthMiddleware(BaseHTTPMiddleware):
    """Setzt den Benutzer aus Forward-Auth-Kopfzeilen (nur wenn vertrauenswuerdig)."""

    async def dispatch(self, request: Request, call_next):
        if user_uebersteuert() or not proxy_header_aktiv():
            return await call_next(request)
        if _ausgenommen(request.url.path):
            return await call_next(request)

        # Schon eine gueltige Sitzung? Dann nichts tun (die Sitzung gewinnt).
        vorhandene_sid = sid_aus_headers(request.headers)
        if vorhandene_sid and sitzungen.lesen(vorhandene_sid):
            return await call_next(request)

        peer = request.client.host if request.client else ""
        konto = proxy_header.konto_aus_kopfzeilen(request.headers, peer_ip=peer)
        if konto is None:
            # Kein/kein vertrauenswuerdiges Forward-Auth -> Request unveraendert.
            return await call_next(request)

        ergebnis, sid = _ordne_und_sitzung(konto)
        if ergebnis is None:
            return await call_next(request)

        response = await call_next(request)
        if sid:
            from diakronos_app.anmeldung.routen import _sitzungscookie

            _sitzungscookie(response, sid)
        return response


def _ordne_und_sitzung(konto):
    """Ordnet das Konto zu und legt bei Erfolg eine Sitzung an.

    Rueckgabe ``(ergebnis, sid)``. Bei Ablehnung ist ``sid`` ``None`` und der
    Request laeuft als Gast weiter (die SPA zeigt dann die Anmeldung).
    """
    from diakronos_app.anmeldung.zuordnung import (
        loese_konto_auf,
        merke_ablehnung_separat,
    )
    from diakronos_app.db import SessionLocal

    sess = SessionLocal()
    try:
        ergebnis = loese_konto_auf(sess, konto)
        if not ergebnis.erlaubt:
            sess.rollback()
            # R-N8 (Punkt 2): abgelehnte E-Mail-Zuordnung fuer die Verwaltung
            # vermerken (eigene Transaktion, weil hier zurueckgerollt wird).
            merke_ablehnung_separat(konto, ergebnis)
            return None, None
        sess.commit()
    except Exception as exc:  # noqa: BLE001 — nie roh durchschlagen
        sess.rollback()
        logger.warning("Forward-Auth-Zuordnung fehlgeschlagen: %s", exc.__class__.__name__)
        return None, None
    finally:
        sess.close()

    sid, _csrf = sitzungen.anlegen(str(ergebnis.user), sso=True)
    return ergebnis, sid
