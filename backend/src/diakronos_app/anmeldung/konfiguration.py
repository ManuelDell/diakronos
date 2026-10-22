"""Anmelde-Anbieter (SEC1) — Konfiguration und Startpruefung.

Dieses Paket setzt die Entscheidungen der Karte SEC1 um:

  * **OIDC** als Standardweg (Authorization Code Flow + PKCE + state + nonce),
    Anbieter extern (Authentik), keine Container im Stack.
  * **Forward-Auth-Kopfzeilen** als OPTIONALER zweiter Weg (AUS per Default).
  * **EIN Login**: bei aktivem OIDC leitet `/login` automatisch weiter.
  * Umgang mit **unbekannten Nutzern** konfigurierbar (in der Oberflaeche,
    gespeichert in der DB, Default sicher = abweisen).

Alle Einstellungen kommen aus `.env`/ENV (`settings.py`). Dieses Modul BUENDELT
die wirksame Sicht auf die Konfiguration und prueft beim Start, ob eine
aktivierte Funktion vollstaendig konfiguriert ist — eine halb eingeschaltete
Anmeldung ist gefaehrlicher als eine ausgeschaltete.

Keine Secrets in Logs: Fehlermeldungen nennen nur den NAMEN der fehlenden
Einstellung, nie ihren Wert.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.anmeldung")

__all__ = [
    "OidcKonfiguration",
    "ProxyHeaderKonfiguration",
    "oidc_aktiv",
    "proxy_header_aktiv",
    "oidc_konfiguration",
    "proxy_header_konfiguration",
    "pruefe_konfiguration",
    "KonfigurationsFehler",
]


class KonfigurationsFehler(RuntimeError):
    """Eine aktivierte Anmeldefunktion ist unvollstaendig konfiguriert."""


@dataclass(frozen=True)
class OidcKonfiguration:
    """Wirksame OIDC-Konfiguration (nach Secret-Aufloesung)."""

    issuer: str
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]
    redirect_url: str
    logout: bool
    anbietername: str
    metadata_ttl: int
    leeway: int
    local_login: str

    @property
    def discovery_url(self) -> str:
        """URL der Discovery-Metadaten (`.well-known/openid-configuration`)."""
        return self.issuer.rstrip("/") + "/.well-known/openid-configuration"


@dataclass(frozen=True)
class ProxyHeaderKonfiguration:
    """Wirksame Konfiguration der Forward-Auth-Kopfzeilen."""

    trusted_netze: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    shared_secret: str
    header_secret: str
    header_username: str
    header_email: str
    header_uid: str
    header_groups: str


def oidc_aktiv() -> bool:
    """True, wenn OIDC in der Konfiguration eingeschaltet ist."""
    return bool(settings.auth_oidc_enabled)


def proxy_header_aktiv() -> bool:
    """True, wenn Forward-Auth-Kopfzeilen eingeschaltet sind."""
    return bool(settings.auth_proxy_header_enabled)


def oidc_konfiguration() -> OidcKonfiguration:
    """Baut die wirksame OIDC-Konfiguration aus den Settings.

    Wirft NICHT bei fehlenden Werten — die Startpruefung
    (`pruefe_konfiguration`) entscheidet, ob das ein harter Fehler ist.
    """
    return OidcKonfiguration(
        issuer=(settings.auth_oidc_issuer or "").strip(),
        client_id=(settings.auth_oidc_client_id or "").strip(),
        client_secret=settings.oidc_client_secret_effektiv,
        scopes=tuple(settings.oidc_scopes_liste),
        redirect_url=settings.oidc_redirect_ziel,
        logout=bool(settings.auth_oidc_logout),
        anbietername=(settings.auth_oidc_anbietername or "Authentik").strip(),
        metadata_ttl=int(settings.auth_oidc_metadata_ttl),
        leeway=int(settings.auth_oidc_leeway),
        local_login=str(settings.auth_local_login or "nur-admin").strip().lower(),
    )


def _parse_netze(roh: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parst eine kommaseparierte CIDR-Liste. Ungueltige Eintraege -> Fehler.

    Ein ungueltiger Eintrag wird NICHT stillschweigend uebergangen: sonst
    glaubte der Betreiber, eine Adresse sei vertrauenswuerdig, waehrend sie in
    Wahrheit nie geprueft wird.
    """
    netze = []
    for teil in (roh or "").split(","):
        wert = teil.strip()
        if not wert:
            continue
        try:
            netze.append(ipaddress.ip_network(wert, strict=False))
        except ValueError as exc:
            raise KonfigurationsFehler(
                f"AUTH_PROXY_TRUSTED_IPS enthaelt keine gueltige Adresse: {wert!r}"
            ) from exc
    return tuple(netze)


def proxy_header_konfiguration() -> ProxyHeaderKonfiguration:
    """Baut die wirksame Forward-Auth-Konfiguration aus den Settings."""
    return ProxyHeaderKonfiguration(
        trusted_netze=_parse_netze(settings.auth_proxy_trusted_ips),
        shared_secret=settings.proxy_shared_secret_effektiv,
        header_secret=(settings.auth_proxy_header_secret or "").strip(),
        header_username=(settings.auth_proxy_header_username or "").strip(),
        header_email=(settings.auth_proxy_header_email or "").strip(),
        header_uid=(settings.auth_proxy_header_uid or "").strip(),
        header_groups=(settings.auth_proxy_header_groups or "").strip(),
    )


def pruefe_konfiguration() -> list[str]:
    """Prueft die Anmeldekonfiguration und liefert Warnungen.

    Wirft `KonfigurationsFehler`, wenn eine AKTIVIERTE Funktion nicht benutzbar
    ist (fail fast: lieber gar nicht starten als still falsch arbeiten). Gibt
    eine Liste harmloser Warnungen zurueck (z. B. OIDC ist aus).
    """
    warnungen: list[str] = []

    if oidc_aktiv():
        cfg = oidc_konfiguration()
        fehlend = [
            name
            for name, wert in (
                ("AUTH_OIDC_ISSUER", cfg.issuer),
                ("AUTH_OIDC_CLIENT_ID", cfg.client_id),
                ("AUTH_OIDC_CLIENT_SECRET", cfg.client_secret),
                ("AUTH_OIDC_REDIRECT_URL (oder APP_BASE_URL)", cfg.redirect_url),
            )
            if not wert
        ]
        if fehlend:
            raise KonfigurationsFehler(
                "AUTH_OIDC_ENABLED=1, aber es fehlen: " + ", ".join(fehlend)
            )
        if not cfg.issuer.startswith("https://") and not cfg.issuer.startswith(
            "http://localhost"
        ):
            # Der Authorization Code Flow ueber eine unverschluesselte
            # Verbindung ist ein offenes Fenster; nur localhost ist geduldet.
            warnungen.append(
                "AUTH_OIDC_ISSUER ist nicht https — im Betrieb unsicher."
            )
    else:
        warnungen.append("OIDC ist aus (AUTH_OIDC_ENABLED=0).")

    if proxy_header_aktiv():
        try:
            cfg_p = proxy_header_konfiguration()
        except KonfigurationsFehler:
            raise
        fehlend = []
        if not cfg_p.trusted_netze:
            fehlend.append("AUTH_PROXY_TRUSTED_IPS")
        if not cfg_p.shared_secret:
            fehlend.append("AUTH_PROXY_SHARED_SECRET")
        if not cfg_p.header_secret:
            fehlend.append("AUTH_PROXY_HEADER_SECRET")
        if fehlend:
            raise KonfigurationsFehler(
                "AUTH_PROXY_HEADER_ENABLED=1, aber es fehlen: " + ", ".join(fehlend)
            )
    else:
        warnungen.append("Forward-Auth-Kopfzeilen sind aus.")

    return warnungen
