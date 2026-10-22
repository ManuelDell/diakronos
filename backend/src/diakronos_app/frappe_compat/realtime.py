"""`frappe.publish_realtime` + Socket.IO-Server (P6a Teil 3).

Original-Fundstellen (READ-ONLY, alle 4 liegen in google_import):

    referenz/diakronos-frappe/diakronos/kronos/api/google_import.py:302
        frappe.publish_realtime("gcal_import_progress", data, user=user)
    ...:506  {"status": "error", "error": ...}
    ...:517  {"status": "warning", "warning": ...}
    ...:545  {"status": "importing", "calendar_name", "imported", "skipped"}

Der Ereignisname ist damit **exakt** `gcal_import_progress` — das ist der
Kanalname, den die SPA abonniert. Wird er geaendert, hoert das Frontend auf
dem falschen Kanal und der Fortschrittsbalken bleibt stehen.

ZUORDNUNG user/room (Frappe-Verhalten, hier 1:1):
Frappe adressiert `publish_realtime(event, message, user=..., room=...)` an
einen persoenlichen Raum (`user:<email>`). Der Client join't beim Verbinden
seinen eigenen Raum. Wir bilden das mit einem privaten Room pro User nach:
* `user` gesetzt  -> nur dieser Client-Raum erhaelt das Ereignis.
* `room` gesetzt  -> expliziter Raum (hat Vorrang, wie im Original).
* keins von beiden -> Broadcast an alle verbundenen Clients.

Der Server wird als ASGI-App (`socket_app`) gemountet; FastAPI nimmt ihn ueber
`app.mount("/socket.io", socket_app)` an. Der Pfad `/socket.io` ist der
Default-Pfad des JS-Clients (`io()` ohne Optionen) — deshalb bleibt er so.
"""

from __future__ import annotations

import logging
from typing import Any

import socketio
from starlette.datastructures import Headers

from diakronos_app.settings import settings
from diakronos_app.frappe_compat import sitzungen, benutzer_status
from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers

logger = logging.getLogger("diakronos_app.realtime")

# Frappe nennt den persoenlichen Raum `user:<email>`. Beibehalten, damit die
# Namen zwischen Server und einem Frappe-vertrauten Client deckungsgleich sind.
USER_ROOM_PREFIX = "user:"

# Das ist der EINZIGE im Original genutzte Ereignisname (4 Fundstellen).
EVENT_GCAL_IMPORT_PROGRESS = "gcal_import_progress"

def create_socket_server():
	"""One server/Redis listener per ASGI lifecycle (never share closed loops)."""
	server = socketio.AsyncServer(
		async_mode="asgi",
		client_manager=socketio.AsyncRedisManager(settings.redis_url, channel="diakronos-realtime"),
		cors_allowed_origins=None,
		logger=False,
		engineio_logger=False,
	)

	async def on_connect(sid, environ, auth=None):
		return await _connect(server, sid, environ, auth)

	server.on("connect", handler=on_connect)
	server.on("disconnect", handler=disconnect)
	return server, socketio.ASGIApp(server, socketio_path="socket.io")


def _user_room(user: str) -> str:
	return f"{USER_ROOM_PREFIX}{user}"


async def connect(sid, environ, auth=None):
	return await _connect(sio, sid, environ, auth)


async def _connect(server, sid, environ, auth=None):
	"""Join only the authenticated session user's room; ignore client auth.user."""
	cookie = environ.get("HTTP_COOKIE", "")
	sid_cookie = sid_aus_headers(Headers({"cookie": cookie}))
	data = sitzungen.lesen(sid_cookie) if sid_cookie else None
	user = data.get("user") if data else None
	if not user or user == "Guest" or not benutzer_status.ist_aktiv(user):
		return False
	await server.enter_room(sid, _user_room(str(user)))
	return True


async def disconnect(sid):
	logger.info("socket.io disconnect %s", sid)


async def _publish(event: str, message: Any, user: str | None, room: str | None) -> None:
	"""Kern von `publish_realtime` — adressiert wie das Original."""
	target_room = room or (_user_room(user) if user else None)
	if target_room:
		await sio.emit(event, message, room=target_room)
	else:
		await sio.emit(event, message)


def publish_realtime(
	event: str,
	message: Any = None,
	user: str | None = None,
	room: str | None = None,
	**kwargs: Any,
) -> None:
	"""`frappe.publish_realtime(event, message, user=..., room=...)`.

	**Wichtig — bewusste Abweichung:** Frappe ruft im Hintergrundjob auf und
	kehrt sofort zurueck (der Job laeuft in einem eigenen Prozess/Worker).
	`publish_realtime` im Original ist also *nicht* async und wirft nicht, wenn
	niemand zuhoert. Wir behalten diese Signatur (synchron, kein Return).

	`async`-Server braucht ein `await`; innerhalb einer Event-Loop erfolgt
	der Emit ueber den AsyncRedisManager. Synchrone RQ-Prozesse publizieren
	ueber einen write-only RedisManager auf denselben Kanal. So erhaelt
	der ASGI-Server Fortschritt auch aus separaten Worker-Prozessen.

	Zusaetzliche Frappe-Optionen (`after_commit`) werden akzeptiert und
	ignoriert — dokumentiert, nicht stillschweigend verschluckt.
	"""
	kwargs.pop("after_commit", None)

	try:
		import asyncio

		loop = asyncio.get_running_loop()
	except RuntimeError:
		# Kein laufender Loop (synchroner Kontext, z. B. RQ-Worker).
		loop = None

	if loop is not None:
		loop.create_task(_publish(event, message, user, room))
	else:
		_emit_from_sync(event, message, user, room)


def _emit_from_sync(event: str, message: Any, user: str | None, room: str | None) -> None:
	"""Publish via Redis from a sync worker, not a process-local AsyncServer."""
	try:
		manager = socketio.RedisManager(settings.redis_url, channel="diakronos-realtime", write_only=True)
		manager.emit(event, message, room=room or (_user_room(user) if user else None))
	except Exception:  # Realtime is best effort; never log connection credentials.
		logger.warning("Realtime delivery unavailable")


# Production uses one ASGI lifecycle per process; tests create their own servers.
sio, socket_app = create_socket_server()


__all__ = [
	"create_socket_server",
	"EVENT_GCAL_IMPORT_PROGRESS",
	"publish_realtime",
	"sio",
	"socket_app",
]
