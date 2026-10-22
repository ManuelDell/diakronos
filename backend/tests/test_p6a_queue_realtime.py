"""P6a Teil 2+3 — Queue (`enqueue`/RQ) und Realtime (`publish_realtime`/Socket.IO).

Originale (READ-ONLY):
`referenz/diakronos-frappe/diakronos/kronos/api/google_import.py:288` (enqueue)
`referenz/diakronos-frappe/diakronos/kronos/api/google_import.py:302,506,517,545`
(`publish_realtime`, Ereignis `gcal_import_progress`)
`referenz/.../doctype/mitglied/mitglied.py:196` (enqueue Callable)
`referenz/.../api/audit_policy/decorator.py:236` (enqueue Callable)

Die Queue-Tests laufen gegen ECHTES Redis und einen ECHTEN RQ-Worker (kein
Mock). Nur so ist die Kartenanforderung "enqueue fuehrt NICHT synchron aus"
tatsaechlich belegt: der Aufruf kehrt zurueck, *bevor* der Worker die Arbeit
erledigt. Redis ist im Test-Container unter `REDIS_URL` erreichbar.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from redis import Redis
from rq import Queue, SimpleWorker

# ── Test-Jobs (muessen importierbar sein, RQ laedt sie per dotted path) ──────

MARKER: dict[str, float] = {}

# Der Importpfad, unter dem pytest dieses Modul laedt (kein Package-Prefix).
THIS_MODULE = __name__


def job_mark(key: str) -> str:
	"""Testjob: traegt einen Zeitstempel in MARKER ein."""
	MARKER[key] = time.time()
	return key


def job_boom(msg: str = "kaputt") -> None:
	"""Testjob, der immer scheitert (fuer die failed-Queue)."""
	raise RuntimeError(msg)


def _redis_available() -> bool:
	try:
		return bool(Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0")).ping())
	except Exception:  # noqa: BLE001
		return False


requires_redis = pytest.mark.skipif(
	not _redis_available(),
	reason="Redis nicht erreichbar (Queue-Tests brauchen den echten Broker)",
)


@pytest.fixture()
def redis_conn():
	return Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


@pytest.fixture()
def test_queue(redis_conn):
	"""Frische, leere Queue mit eindeutigem Namen (keine Kollision mit 'default')."""
	name = f"p6a-test-{uuid.uuid4().hex[:8]}"
	q = Queue(name=name, connection=redis_conn)
	yield q
	q.empty()
	try:
		q.delete(delete_jobs=True)
	except Exception:  # noqa: BLE001
		pass


# ── Queue: enqueue ist asynchron ─────────────────────────────────────────────

@requires_redis
def test_enqueue_kehrt_zurueck_bevor_die_arbeit_fertig_ist(test_queue):
	"""Kartenanforderung: `enqueue` darf NICHT synchron ausfuehren.

	Beweis: direkt nach `enqueue` ist der Job nicht gelaufen; erst der Worker
	erledigt ihn. Ein synchroner Pfad wuerde MARKER sofort fuellen.
	"""
	from diakronos_app.frappe_compat.queue import enqueue

	key = f"k-{uuid.uuid4().hex[:8]}"
	MARKER.pop(key, None)

	job = enqueue(f"{THIS_MODULE}.job_mark", queue=test_queue.name, key=key)

	# Direkt nach dem Einreihen: Arbeit ist NICHT gelaufen.
	assert key not in MARKER
	assert job.id

	# Erst ein Worker erledigt sie.
	worker = SimpleWorker([test_queue], connection=test_queue.connection)
	worker.work(burst=True, logging_level="WARNING")

	assert key in MARKER


# ── Queue: Fehler landen in der failed-Queue ─────────────────────────────────

@requires_redis
def test_fehlgeschlagener_job_landet_in_failed_queue(test_queue, redis_conn):
	"""Ein Fehler darf den Aufrufer nicht still gruen aussehen lassen."""
	from rq.job import Job
	from rq.registry import FailedJobRegistry

	from diakronos_app.frappe_compat.queue import enqueue

	job = enqueue(f"{THIS_MODULE}.job_boom", queue=test_queue.name, msg="kaputt")

	worker = SimpleWorker([test_queue], connection=redis_conn)
	worker.work(burst=True, logging_level="WARNING")

	refresh = Job.fetch(job.id, connection=redis_conn)
	assert refresh.is_failed
	registry = FailedJobRegistry(queue=test_queue)
	assert job.id in registry.get_job_ids()


# ── Queue: Signatur/Aufloesung ───────────────────────────────────────────────

def test_enqueue_loest_dotted_path_und_callable_auf():
	"""Beide Original-Formen: String-Pfad UND Callable."""
	from diakronos_app.frappe_compat.queue import _job_target, resolve_job

	# String bleibt unveraendert (Original: Frappe-Pfad).
	assert _job_target("diakronos.kronos.api.google_import._do_import") == (
		"diakronos.kronos.api.google_import._do_import"
	)
	# Callable -> <modul>.<qualname>.
	assert _job_target(job_mark) == f"{THIS_MODULE}.job_mark"

	# Aufloesung ueber die Registry und per Import.
	from diakronos_app.frappe_compat.registry import registered

	assert resolve_job(f"{THIS_MODULE}.job_mark") is job_mark
	if "anonymize_expired_audit_logs" in registered():
		assert resolve_job("anonymize_expired_audit_logs") is not None


def test_enqueue_wirft_bei_unbekanntem_pfad():
	"""Fail fast: Tippfehler knallt beim Einreihen, nicht erst im Worker."""
	from diakronos_app.frappe_compat.queue import EnqueueError, resolve_job

	with pytest.raises(EnqueueError):
		resolve_job("gibt.es.nicht.gibt_es_nicht")


# ── Realtime: Signatur + Ereignisname ────────────────────────────────────────

def test_realtime_ereignisname_ist_exakt_wie_im_original():
	"""Der Kanalname muss `gcal_import_progress` sein — sonst hoert die SPA nicht."""
	from diakronos_app.frappe_compat.realtime import EVENT_GCAL_IMPORT_PROGRESS

	assert EVENT_GCAL_IMPORT_PROGRESS == "gcal_import_progress"
	# Und die 4 Original-Fundstellen nutzen genau diesen Namen.
	import subprocess

	ref = "referenz/diakronos-frappe/diakronos/kronos/api/google_import.py"
	if os.path.exists(ref):
		with open(ref) as fh:
			text = fh.read()
		namen = {
			line.split('"')[1]
			for line in text.splitlines()
			if "publish_realtime(" in line
		}
		assert namen == {"gcal_import_progress"}


def test_publish_realtime_ist_synchron_und_wirft_nicht_ohne_loop():
	"""Frappe-Signatur: synchron, kein Return — und best effort ohne Empfaenger."""
	from diakronos_app.frappe_compat.realtime import publish_realtime

	# Ohne laufende Event-Loop und ohne zuhoerenden Client darf nichts fliegen.
	assert publish_realtime("gcal_import_progress", {"status": "importing"},
	                        user="a@b.de") is None
	assert publish_realtime("gcal_import_progress", {"status": "done"}) is None


# ── Realtime: echter Client, echtes Ereignis, echter Empfang ─────────────────

@requires_redis
@pytest.mark.parametrize("lifecycle", [1, 2])
def test_realtime_client_empfaengt_ereignis(client, lifecycle):
	"""Ein Client verbindet, ein Ereignis wird ausgeloest, Empfang ist belegt.

	Wir fahren den Socket.IO-ASGI-Server mit einem echten `socketio.Client`
	(synchroner Client, nutzt `requests` — `aiohttp` ist im Image NICHT
	installiert, deshalb bewusst nicht der AsyncClient) gegen einen lokalen
	Uvicorn-Thread. Das prueft die ganze Kette
	(publish_realtime -> sio.emit -> Client-Empfang), nicht nur ein Dictionary.
	"""
	socketio = pytest.importorskip("socketio")
	import uvicorn

	from diakronos_app.frappe_compat.realtime import create_socket_server
	_, socket_app = create_socket_server()

	received: list = []
	got = threading.Event()
	connected = threading.Event()
	port = 8791

	session_cookie = client.cookies.get("sid")
	client = socketio.Client()

	@client.on("gcal_import_progress")
	def _on(data):  # noqa: ANN001
		received.append(data)
		got.set()

	config = uvicorn.Config(socket_app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=2)
	server = uvicorn.Server(config)
	server_thread = threading.Thread(target=server.run, daemon=True)
	server_thread.start()
	try:
		for _ in range(200):
			if server.started:
				break
			time.sleep(0.05)
		assert server.started, "Uvicorn-Thread nicht gestartet"

		client.connect(f"http://127.0.0.1:{port}", socketio_path="socket.io",
		               headers={"Cookie": "sid=" + session_cookie})
		connected.set()
		# Dem Client Zeit geben, seinen persoenlichen Raum zu betreten.
		time.sleep(0.4)

		from diakronos_app.frappe_compat.realtime import publish_realtime

		publish_realtime("gcal_import_progress",
		                 {"status": "importing", "imported": 1},
		                 user="Administrator")

		assert got.wait(timeout=10), "kein Realtime-Ereignis empfangen"
	finally:
		try:
			client.disconnect()
		except Exception:  # noqa: BLE001
			pass
		server.should_exit = True
		server_thread.join(timeout=5)

	assert received, "kein Realtime-Ereignis empfangen"
	assert received[0]["status"] == "importing"
