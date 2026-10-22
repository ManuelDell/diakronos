"""Request-Kontext — `frappe.request`-Ersatz fuer Portierungen.

Der Altcode liest an wenigen Stellen den HTTP-Request direkt
(`frappe.request.environ` / `.headers`), z. B. in
`diakonos.api.registrierung._get_client_ip` (X-Forwarded-For, REMOTE_ADDR)
und in `dsgvo_log.log_einwilligung` (REMOTE_ADDR, User-Agent).

FastAPI-Endpunkte sind `async`, die portierten Fachfunktionen sind synchron und
werden direkt aufgerufen; ein Parameter durch alle Signaturen waere eine
API-Aenderung. Deshalb legt diese Middleware die Request-Daten in
`ContextVar`s ab — gleiches Muster wie `frappe_compat.session`
(`_current_user`). Ausserhalb eines Requests (Tests, Cron) sind die Werte leer.
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from diakronos_app.ip_adressen import parse_ip

_client_ip: ContextVar[str] = ContextVar("frappe_request_client_ip", default="")
_headers: ContextVar[dict[str, str]] = ContextVar("frappe_request_headers", default={})


def set_request(request: Request) -> None:
	"""Request-Daten im aktuellen Kontext hinterlegen."""
	_client_ip.set(request.client.host if request.client else "")
	# Kopfzeilen klein normalisieren, damit `get_header` case-insensitiv ist.
	_headers.set({k.lower(): v for k, v in request.headers.items()})


def clear_request() -> None:
	_client_ip.set("")
	_headers.set({})


def get_client_ip() -> str:
	"""`REMOTE_ADDR` des laufenden Requests ("" ausserhalb eines Requests)."""
	return _client_ip.get()


def zaehler_client_ip() -> str:
    """Die IP, die fuer den Brute-Force-IP-Zaehler gilt (A1c1/A1c2).

    **Fail closed: `X-Forwarded-For` wird nur gelesen, wenn ein
    Reverse-Proxy vorausgesetzt ist** (`settings.behind_proxy`).

    Warum das ein Schalter und keine Ermessensfrage ist: `X-Forwarded-For`
    ist ein Header, den **jeder Client selbst setzen darf**. Ohne einen
    vorausgesetzten, vertrauenswuerdigen Proxy, der die Kette ueberschreibt,
    wuerde der IP-Zaehler auf einen vom Angreifer gewaehlten Wert laufen —
    jeder neue Header waere ein neues Leben, und die halbe Sperre waere mit
    einem Wort aufzuheben. Genau das ist der Gegengipfel, den die Karte
    A1c2 verlangt.

    Hinter einem Proxy ist es umgekehrt: dort ist `request.client.host` immer
    die Adresse des Proxies, also fuer **alle** Benutzer identisch — der
    IP-Zaehler waere dann wertlos, weil er nach der Schwelle JEDEN sperrt.
    Deshalb wird in dem Fall die erste Adresse aus `X-Forwarded-For`
    genommen (von links, dem Client naechsten).

    Der Default ist bewusst "kein Proxy": lieber zu paranoid (die Sperre
    greift fuer alle Benutzer hinter dem Proxy) als zu lax (keine IP-Sperre
    ueberhaupt). Wer seinen Stack hinter einen Proxy stellt, setzt einmalig
    `BEHIND_PROXY=1` — siehe `settings.py`.

    A1c12: Ist der erste XFF-Wert ungueltig, bleibt der echte Peer die
    Kennung, nicht der Muell und nicht ein spaeterer Wert aus der Kette.
    Ist der Peer privat, bleibt gemaess Proxy-Regel nur die Kontosperre.
    Der Proxy MUSS fremdes XFF ueberschreiben; der Backend-Port darf bei
    aktivem Schalter nicht direkt fuer fremde Clients erreichbar sein.
    """
    direkt = (_client_ip.get() or "").strip()
    if not _proxy_vorausgesetzt():
        return direkt
    roh = (get_header("X-Forwarded-For") or "").strip()
    if not roh:
        return direkt
    # Links beginnt die Kette mit dem Client, der die Anfrage stellte;
    # rechts stehen die nachgeforderten Proxies. Nur der erste Wert ist der
    # des Absenders — der Rest sind zwischenzeitliche Stationen.
    adresse = parse_ip(roh.split(",")[0].strip())
    # Muell darf weder neue Zaehler noch einen IP-Limit-Bypass erzeugen:
    # der echte Peer bleibt die Kennung, falls XFF keine Adresse enthaelt.
    return str(adresse) if adresse is not None else direkt


def _proxy_vorausgesetzt() -> bool:
    """Ist ein Reverse-Proxy als vorausgesetzt markiert? (`BEHIND_PROXY`)"""
    from diakronos_app.settings import settings

    return bool(getattr(settings, "behind_proxy", False))


def get_header(name: str, default: str = "") -> str:
	"""Kopfzeile des laufenden Requests, case-insensitiv."""
	return _headers.get().get(name.lower(), default)


def get_user_agent(limit: int = 200) -> str:
	"""`User-Agent` des laufenden Requests, auf `limit` Zeichen gekuerzt.

	Entspricht `frappe.request.headers.get("User-Agent")` plus der Kuerzung,
	die `dsgvo_log.log_einwilligung` im Original anwendet.
	"""
	return get_header("User-Agent")[:limit]


class RequestContextMiddleware(BaseHTTPMiddleware):
	"""Setzt den Request-Kontext fuer jeden Aufruf."""

	async def dispatch(self, request: Request, call_next):
		set_request(request)
		try:
			return await call_next(request)
		finally:
			clear_request()
