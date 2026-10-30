"""WEB-5a: der Socket.IO-Baum unter einem Pfad-Praefix (`DIAKRONOS_BASE_PATH`).

WARUM DIESE SCHICHT
-------------------
`python-engineio` (4.15.1, von `python-socketio` 5.17.1 benutzt) vergleicht in
`engineio/async_drivers/asgi.py` den **rohen** `scope["path"]` mit seinem
Pfad:

    self._ensure_trailing_slash(scope['path']).startswith(self.engineio_path)

Hinter einem Starlette-`Mount` bleibt `scope["path"]` der VOLLE Pfad
(`/diakronos/socket.io/…`); `root_path` beachtet Engine.IO nicht, und den
`child_scope` des Mounts liest es dort nicht. Ergebnis: mit Praefix kann der
Handshake nie passen — `GET /diakronos/socket.io/?EIO=4&transport=polling`
endet in **404**, waehrend dieselbe Anfrage ohne Praefix 200 liefert (im
Abnahme-Stack gemessen, 2026-10-30).

WARUM EINE MITTELSCHICHT UND KEINE HUELLE UM `socket_app`
--------------------------------------------------------
Eine generische ASGI-Huelle direkt vor `socketio.ASGIApp` verliert dessen
internen Kurzweg (`isinstance(self, ASGIApp)`) und liefert ebenfalls 404 (im
Test gemessen). Deshalb bleibt der ECHTE `socketio.ASGIApp` gemountet — nur
der Pfad wird vorher beschnitten, und zwar ausschliesslich im Socket-Teilbaum
(`PraefixSocketMiddleware`).

Ohne Praefix ist die Schicht wirkungslos: der Pfad bleibt, wie er ist.

Nicht angefasst wird `socketio_path`: der JS-Client haengt ihn an seine
Basis-URL (`io({path: basePath + '/socket.io'})`, WEB-5b), die Request-Pfade
bleiben also dieselben wie heute.
"""

from __future__ import annotations

import re

from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = ["PraefixSocketMiddleware"]

_SOCKET = "/socket.io"


class PraefixSocketMiddleware:
    """Schneidet `{praefix}/socket.io` ab, bevor Engine.IO den Pfad prueft.

    Ans Ende der Middleware-Kette gehaengt (also aeusserste Schicht) sieht sie
    den VOLLEN Pfad und reicht `/socket.io/…` weiter — genau die Form, die
    Engine.IO an der Wurzel erwartet.
    """

    def __init__(self, app: ASGIApp, praefix: str = "") -> None:
        self.app = app
        wert = str(praefix or "").strip("/")
        self.praefix = f"/{wert}" if wert else ""
        self._muster = (
            re.compile(r"^" + re.escape(self.praefix) + r"(?=" + re.escape(_SOCKET) + r")(.*)$")
            if self.praefix
            else None
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._muster is not None and scope.get("type") in {"http", "websocket"}:
            pfad = scope.get("path") or ""
            treffer = self._muster.match(pfad)
            if treffer is not None:
                scope = dict(scope)
                scope["path"] = treffer.group(1) or "/"
                # `root_path` bleibt unangetastet: Engine.IO liest ihn nicht,
                # und der Server baut daraus absolute Adressen.
        await self.app(scope, receive, send)
