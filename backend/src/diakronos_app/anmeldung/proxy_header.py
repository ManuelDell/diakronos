"""Forward-Auth-Kopfzeilen (SEC1, TEIL B) — OPTIONAL, AUS per Default.

Ein Authentik-Forward-Auth-Proxy kann den bereits angemeldeten Benutzer in
Kopfzeilen mitgeben (``X-authentik-username`` u. a.). Diese Kopfzeilen sind
**nur** dann vertrauenswuerdig, wenn BEIDE Bedingungen erfuellt sind:

  1. die direkte Peer-Adresse des Requests liegt in ``AUTH_PROXY_TRUSTED_IPS``,
  2. das gemeinsame Geheimnis (``AUTH_PROXY_SHARED_SECRET``) stimmt in konstanter
     Zeit mit dem Kopfzeilenwert ueberein.

Fehlt eine der beiden Bedingungen, werden die Kopfzeilen **vollstaendig
verworfen** — kein halbes Vertrauen (z. B. „Benutzername ja, Gruppen nein“).
Sonst koennte jeder Client, der den Backend-Port erreicht, per Kopfzeile eine
beliebige Identitaet behaupten.

Die Peer-Adresse ist ``request.client.host`` — der Wert, den der Client NICHT
bestimmen kann. ``X-Forwarded-For`` wird hier NICHT herangezogen: er ist selbst
nur eine Behauptung.
"""

from __future__ import annotations

import hmac
import logging

from diakronos_app.anmeldung.konfiguration import (
    ProxyHeaderKonfiguration,
    proxy_header_aktiv,
    proxy_header_konfiguration,
)
from diakronos_app.anmeldung.zuordnung import ExternesKonto

logger = logging.getLogger("diakronos_app.anmeldung.proxy")

__all__ = [
    "IP_UNBEKANNT",
    "ip_vertraut",
    "konto_aus_kopfzeilen",
]

# Kennung fuer die Quellkennzeichnung der Zuordnung. Der Issuer ist ein fester,
# nicht anbieterspezifischer Wert, damit die Zuordnung nicht an einer
# externen URL haengt: Forward-Auth liefert keine stabile ``iss``.
PROXY_ISSUER = "proxy:forward-auth"

IP_UNBEKANNT = "__unbekannt__"


def ip_vertraut(peer_ip: str, konfig: ProxyHeaderKonfiguration) -> bool:
    """True, wenn ``peer_ip`` in einem der vertrauenswuerdigen Netze liegt.

    Eine unbekannte oder leere Adresse ist NIE vertrauenswuerdig.
    """
    import ipaddress

    if not peer_ip or peer_ip == IP_UNBEKANNT:
        return False
    try:
        adresse = ipaddress.ip_address(peer_ip)
    except ValueError:
        return False
    return any(adresse in netz for netz in konfig.trusted_netze)


def konto_aus_kopfzeilen(
    kopfzeilen,
    *,
    peer_ip: str,
) -> ExternesKonto | None:
    """Baut aus den Proxy-Kopfzeilen ein Konto — nur bei voller Vertrauenslage.

    ``kopfzeilen`` ist ein case-insensitiver Mapping-artiger Zugriff (Starlette
    ``Headers``). Liefert ``None``, wenn Forward-Auth aus ist, die Peer-Adresse
    nicht vertraut ist oder das Geheimnis fehlt/falsch ist. In diesen Faellen
    werden die Kopfzeilen NICHT ausgewertet — auch nicht teilweise.
    """
    if not proxy_header_aktiv():
        return None
    try:
        konfig = proxy_header_konfiguration()
    except Exception:  # noqa: BLE001 — Fehlkonfiguration -> Kopfzeilen verwerfen
        logger.warning("Forward-Auth fehlkonfiguriert — Kopfzeilen verworfen.")
        return None

    if not ip_vertraut(peer_ip, konfig):
        return None

    geliefert = _header(kopfzeilen, konfig.header_secret)
    if not geliefert or not hmac.compare_digest(
        str(geliefert), str(konfig.shared_secret)
    ):
        return None

    username = (_header(kopfzeilen, konfig.header_username) or "").strip()
    email = (_header(kopfzeilen, konfig.header_email) or "").strip()
    uid = (_header(kopfzeilen, konfig.header_uid) or "").strip()
    gruppen = _gruppen(_header(kopfzeilen, konfig.header_groups) or "")

    # Der ``sub`` MUSS stabil sein. Bevorzugt wird die UID; fehlt sie, dient der
    # Benutzername als Ersatz (immer noch stabiler als die E-Mail).
    sub = uid or username
    if not sub:
        return None

    # Forward-Auth liefert keine Verifikation der E-Mail. Wir behandeln sie als
    # NICHT verifiziert — das ist die sichere Annahme (keine Konto-Uebernahme
    # ueber die E-Mail).
    return ExternesKonto(
        issuer=PROXY_ISSUER,
        sub=sub,
        email=email,
        email_verified=False,
        name=username or email,
        gruppen=gruppen,
        quelle="proxy_header",
    )


def _header(kopfzeilen, name: str) -> str | None:
    """Liest eine Kopfzeile case-insensitiv; fehlt sie, ``None``."""
    if not name:
        return None
    try:
        return kopfzeilen.get(name)
    except Exception:  # noqa: BLE001
        return None


def _gruppen(roh: str) -> tuple[str, ...]:
    """Kopfzeilenwert der Gruppen -> Tupel.

    Authentik trennt mehrfach belegte Kopfzeilen mit Komma; zusaetzlich werden
    Leerzeichen/Zeilenumbrueche als Trenner akzeptiert.
    """
    if not roh:
        return ()
    teile = []
    for stueck in roh.replace("\n", ",").split(","):
        wert = stueck.strip()
        if wert:
            teile.append(wert)
    return tuple(teile)
