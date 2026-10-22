"""OIDC — Entdeckung, JWKS, Token-Pruefung und der Authorization-Code-Flow.

Bewaehrte Bibliothek statt Eigenbau (Kartenvorgabe): **Authlib** liefert die
JWS-/JWK-Pruefung (`authlib.jose`) und den OAuth2-Client
(`authlib.integrations.httpx_client`). Diese Datei stellt den Flow zusammen:

  1. ``autorisierungs_url`` — baut die Weiterleitung zum Anbieter mit
     ``state``, ``nonce`` und PKCE (``code_challenge`` = S256).
  2. ``hole_token`` — tauscht den Code (mit ``code_verifier``) gegen Token.
  3. ``pruefe_id_token`` — verifiziert das ID-Token: Signatur gegen JWKS,
     ``iss``, ``aud`` (bzw. ``azp``), ``exp`` mit kleiner Toleranz und den
     ``nonce``.

Alle Geheimnisse (Client-Secret, ``code_verifier``, Token) werden NIE geloggt.
Fehler werden als `OidcFehler` gemeldet — ohne Kennung des Anbieters und ohne
Inhalt eines Tokens.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from diakronos_app.anmeldung.konfiguration import OidcKonfiguration

logger = logging.getLogger("diakronos_app.anmeldung.oidc")

__all__ = [
    "OidcFehler",
    "OidcMetadaten",
    "autorisierungs_url",
    "hole_token",
    "pruefe_id_token",
    "hole_metadaten",
    "leere_metadaten_cache",
]


class OidcFehler(RuntimeError):
    """Fehler im OIDC-Ablauf. Die Meldung enthaelt keine Geheimnisse."""


@dataclass(frozen=True)
class OidcMetadaten:
    """Relevante Felder der Discovery-Metadaten."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str | None
    id_token_signing_alg_values_supported: tuple[str, ...]


# ── Metadaten-Cache (prozesslokal) ─────────────────────────────────────────
_METADATEN: dict[str, tuple[float, OidcMetadaten]] = {}


def leere_metadaten_cache() -> None:
    """Leert den Metadaten-Cache (Tests, Konfigurationswechsel)."""
    _METADATEN.clear()


def hole_metadaten(cfg: OidcKonfiguration, *, erzwinge: bool = False) -> OidcMetadaten:
    """Holt die Discovery-Metadaten, mit Cache (TTL aus der Konfiguration).

    Der Cache haengt am Issuer: ein Konfigurationswechsel (anderer Anbieter)
    zieht automatisch neue Metadaten.
    """
    jetzt = time.monotonic()
    zwischengespeichert = _METADATEN.get(cfg.issuer)
    if (
        not erzwinge
        and zwischengespeichert is not None
        and jetzt - zwischengespeichert[0] < cfg.metadata_ttl
    ):
        return zwischengespeichert[1]

    url = cfg.discovery_url
    try:
        antwort = httpx.get(url, timeout=10.0, follow_redirects=True)
        antwort.raise_for_status()
        daten = antwort.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcFehler(f"Discovery fehlgeschlagen ({url}).") from exc

    if not isinstance(daten, dict):
        raise OidcFehler("Discovery lieferte kein Objekt.")
    benoetigt = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
    fehlend = [k for k in benoetigt if not daten.get(k)]
    if fehlend:
        raise OidcFehler("Discovery unvollstaendig: " + ", ".join(fehlend))

    # Der ``issuer`` aus den Metadaten MUSS dem konfigurierten entsprechen —
    # sonst koennte eine manipulierte Discovery auf einen fremden Issuer zeigen.
    if str(daten["issuer"]).rstrip("/") != cfg.issuer.rstrip("/"):
        raise OidcFehler("Discovery-Issuer weicht von AUTH_OIDC_ISSUER ab.")

    meta = OidcMetadaten(
        issuer=str(daten["issuer"]),
        authorization_endpoint=str(daten["authorization_endpoint"]),
        token_endpoint=str(daten["token_endpoint"]),
        jwks_uri=str(daten["jwks_uri"]),
        end_session_endpoint=(str(daten["end_session_endpoint"])
                              if daten.get("end_session_endpoint") else None),
        id_token_signing_alg_values_supported=tuple(
            daten.get("id_token_signing_alg_values_supported") or ()
        ),
    )
    _METADATEN[cfg.issuer] = (jetzt, meta)
    return meta


def _b64url(roh: bytes) -> str:
    """Base64url ohne Padding (PKCE)."""
    return base64.urlsafe_b64encode(roh).rstrip(b"=").decode("ascii")


def _pkce_verifier() -> str:
    """Neuer PKCE-`code_verifier` (43-128 Zeichen, CSPRNG)."""
    return _b64url(secrets.token_bytes(48))


def _pkce_challenge(verifier: str) -> str:
    """`code_challenge` nach S256."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass(frozen=True)
class Autorisiert:
    """Ergebnis von `autorisierungs_url`: URL + die zu merkenden Werte."""

    url: str
    state: str
    nonce: str
    code_verifier: str


def autorisierungs_url(cfg: OidcKonfiguration, meta: OidcMetadaten) -> Autorisiert:
    """Baut die Autorisierungs-URL mit `state`, `nonce` und PKCE."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = _pkce_verifier()
    parameter = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_url,
        "scope": " ".join(cfg.scopes),
        "state": state,
        "nonce": nonce,
        "code_challenge": _pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    trenner = "&" if "?" in meta.authorization_endpoint else "?"
    return Autorisiert(
        url=meta.authorization_endpoint + trenner + urlencode(parameter),
        state=state,
        nonce=nonce,
        code_verifier=verifier,
    )


def hole_token(
    cfg: OidcKonfiguration,
    meta: OidcMetadaten,
    *,
    code: str,
    code_verifier: str,
) -> dict:
    """Tauscht den Autorisierungscode gegen Token (Client-Secret + PKCE)."""
    daten = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": cfg.redirect_url,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "code_verifier": code_verifier,
    }
    try:
        antwort = httpx.post(meta.token_endpoint, data=daten, timeout=10.0)
    except httpx.HTTPError as exc:
        raise OidcFehler("Token-Abruf nicht moeglich.") from exc
    if antwort.status_code != 200:
        raise OidcFehler(f"Token-Abruf abgelehnt (HTTP {antwort.status_code}).")
    try:
        ergebnis = antwort.json()
    except ValueError as exc:
        raise OidcFehler("Token-Antwort war kein JSON.") from exc
    if not isinstance(ergebnis, dict):
        raise OidcFehler("Token-Antwort war kein Objekt.")
    return ergebnis


def _hole_jwks(meta: OidcMetadaten) -> dict:
    """Holt das JWKS des Anbieters (kein Cache ueber Prozessgrenzen)."""
    try:
        antwort = httpx.get(meta.jwks_uri, timeout=10.0)
        antwort.raise_for_status()
        daten = antwort.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OidcFehler("JWKS nicht abrufbar.") from exc
    if not isinstance(daten, dict) or "keys" not in daten:
        raise OidcFehler("JWKS besitzt keine Schluessel.")
    return daten


def pruefe_id_token(
    cfg: OidcKonfiguration,
    meta: OidcMetadaten,
    id_token: str,
    *,
    nonce: str,
) -> dict:
    """Verifiziert das ID-Token und liefert die Ansprueche (Claims).

    Geprueft werden: Signatur gegen das JWKS, ``iss``, ``aud`` (bei mehreren
    Publikumswerten ``azp``), ``exp``/``nbf`` mit kleiner Toleranz und der
    ``nonce``. Algorithmus wird auf die vom Anbieter angekuendigten Verfahren
    beschraenkt (kein ``none``).
    """
    from authlib.jose import JsonWebToken
    from authlib.jose.errors import JoseError

    if not id_token:
        raise OidcFehler("Kein ID-Token in der Antwort.")

    jwks = _hole_jwks(meta)
    erlaubte_alg = list(meta.id_token_signing_alg_values_supported) or [
        "RS256", "ES256",
    ]
    # `none` ist NIEMALS zulaessig, selbst wenn ein Anbieter es ankuendigt.
    erlaubte_alg = [a for a in erlaubte_alg if a.lower() != "none"]

    jwt = JsonWebToken(erlaubte_alg)
    try:
        claims = jwt.decode(id_token, jwks, claims_options={
            "iss": {"essential": True, "value": meta.issuer},
            "aud": {"essential": True, "value": cfg.client_id},
            "exp": {"essential": True},
            "nonce": {"essential": True, "value": nonce},
        })
        # Kleine Toleranz (Uhrenabweichung), nicht mehr.
        claims.validate(leeway=int(cfg.leeway))
    except JoseError as exc:
        raise OidcFehler("ID-Token ungueltig.") from exc
    except Exception as exc:  # noqa: BLE001 — jede unerwartete Form ist eine Ablehnung
        raise OidcFehler("ID-Token nicht pruefbar.") from exc

    daten = dict(claims)
    # `azp` (authorized party) explizit pruefen, wenn das Publikum eine Liste ist:
    # ohne diese Pruefung koennte ein Token fuer einen anderen Client mit
    # demselben Publikumskreis durchgehen.
    aud = daten.get("aud")
    if isinstance(aud, (list, tuple)) and len(aud) > 1:
        if daten.get("azp") != cfg.client_id:
            raise OidcFehler("ID-Token: azp passt nicht zum Client.")
    return daten
