"""P6a Teil 2+3 — Queue (`enqueue`/RQ) und Realtime (`publish_realtime`/Socket.IO).

ZEIT-1 (Review): Das Modul traegt ein eigenes `pytest-timeout`-Budget. Der
globale Wert in `pyproject.toml` (60 s) darf NICHT erhoeht werden — er ist
die Haenger-Bremse der ganzen Suite. Die Fristen, die die Tests hier
brauchen, liegen aber darueber: der RQ-Worker-Lauf, der Uvicorn-Start und der
Engine.IO-Handshake haben je eigene Wartegrenzen (30–45 s). Ohne diesen
Modulwert greift KEINE davon: pytest bricht bei 60 s ab, bevor die
Wartelogik ihre sprechende Meldung abgeben kann. 120 s = grosszuegigste
Frist hier (45 s) + Reserve fuer Start und Teardown.

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

#: Modulbudget fuer pytest-timeout (s. Modul-Docstring). Gilt fuer ALLE Tests
#: der Datei und deckt die laengste eigene Wartegrenze (45 s) mit Reserve ab;
#: der globale 60-s-Wert bleibt unangetastet.
pytestmark = pytest.mark.timeout(120)

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
	return Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"),
	                      socket_timeout=10, socket_connect_timeout=10)


def _verschwundene_jobs(queue) -> str:
	"""Warum ein Job aus der Queue verschwand, als Text fuer die Meldung.

	Im vollen Lauf (ZEIT-1) kam `assert key in MARKER` mit leerem MARKER und
	`NoSuchJobError` — der Job war WEG, ohne gelaufen zu sein. RQ nimmt einen
	Job aus der Queue, sobald ein Worker ihn reisst; stirbt der Worker
	danach, liegt der Job in der Registry `StartedJobRegistry` (RQ 2.x) bzw.
	in `FailedJobRegistry`. Beides wird hier gelesen, statt zu raten.
	"""
	from rq.registry import FailedJobRegistry, StartedJobRegistry

	teile = []
	for name, registry in (
		("gestartet", StartedJobRegistry(queue=queue)),
		("fehlgeschlagen", FailedJobRegistry(queue=queue)),
	):
		ids = registry.get_job_ids()
		if ids:
			teile.append(f"{name}: {ids}")
	return "; ".join(teile) or "in keiner Registry (Job nie angekommen?!)"


def _mit_frist(was, frist: float, beschreibung: str):
	"""Fuehrt `was()` aus und bricht mit sprechender Meldung ab, wenn sie haengt.

	ZEIT-1 (Last-Flake): `SimpleWorker.work(burst=True)` kehrt erst zurueck,
	wenn er fertig ist — bricht der Worker unter Last in einen Haenger,
	haengt der Test bis zum pytest-Timeout und meldet "Failed: Timeout",
	nicht die Ursache.

	Der Lauf bleibt im HAUPT-Faden: RQ setzt im Worker einen SIGALRM-Handler
	(Job-Zeitgrenze), und `signal` funktioniert nur im Haupt-Faden — ein
	eigener Faden brach hier mit "signal only works in main thread" ab.
	Statt des Fadens begrenzt ein Wachhund die Wartezeit: `SIGALRM` (Unix)
	loest `TimeoutError` aus, das wir in die sprechende Meldung uebersetzen.
	"""
	import signal

	class _Frist(Exception):
		pass

	alt = signal.getsignal(signal.SIGALRM)

	def _abgelaufen(_sig, _frm):
		raise _Frist(f"{beschreibung} nach {frist} s nicht zurueckgekehrt — "
		             "Worker/Redis unter Last haengen geblieben (kein Fehler "
		             "der Aussage des Tests, ein haengender Lauf)")

	# Ein laufender Wecker (pytest-timeout mit `timeout_method=signal`, so in
	# der Integrationskette) wird gemerkt und mit der Restzeit wieder
	# gestellt — sonst waere der Test nach `_mit_frist` ungebremst.
	rest_vorher = signal.getitimer(signal.ITIMER_REAL)[0]
	start = time.monotonic()
	signal.signal(signal.SIGALRM, _abgelaufen)
	signal.setitimer(signal.ITIMER_REAL, frist)
	try:
		try:
			return was()
		except _Frist as frist_fehler:
			raise AssertionError(str(frist_fehler)) from None
		finally:
			signal.setitimer(signal.ITIMER_REAL, 0)
	finally:
		signal.signal(signal.SIGALRM, alt)
		if rest_vorher > 0:
			signal.setitimer(signal.ITIMER_REAL,
			                 max(rest_vorher - (time.monotonic() - start), 0.01))


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

	# Erst ein Worker erledigt sie. Der Test misst, DASS der Job ausgefuehrt
	# wird — dass `enqueue` selbst nicht synchron ausfuehrt, steht im
	# `assert key not in MARKER` oben.
	worker = SimpleWorker([test_queue], connection=test_queue.connection)
	_mit_frist(lambda: worker.work(burst=True, logging_level="WARNING"),
	           45, "Worker-Lauf (enqueue)")

	assert key in MARKER, (
		"Der Testjob ist nicht gelaufen, obwohl der Worker-Lauf zurueckkam "
		f"(Queue {test_queue.name!r}, Job {job.id}): {_verschwundene_jobs(test_queue)}")


# ── Queue: Fehler landen in der failed-Queue ─────────────────────────────────

@requires_redis
def test_fehlgeschlagener_job_landet_in_failed_queue(test_queue, redis_conn):
	"""Ein Fehler darf den Aufrufer nicht still gruen aussehen lassen."""
	from rq.exceptions import NoSuchJobError
	from rq.job import Job
	from rq.registry import FailedJobRegistry

	from diakronos_app.frappe_compat.queue import enqueue

	job = enqueue(f"{THIS_MODULE}.job_boom", queue=test_queue.name, msg="kaputt")

	worker = SimpleWorker([test_queue], connection=redis_conn)
	_mit_frist(lambda: worker.work(burst=True, logging_level="WARNING"),
	           45, "Worker-Lauf (failed-Queue)")

	try:
		refresh = Job.fetch(job.id, connection=redis_conn)
	except NoSuchJobError:
		raise AssertionError(
			"Der Job ist nach dem Worker-Lauf nicht mehr vorhanden "
			f"(Queue {test_queue.name!r}, Job {job.id}): "
			f"{_verschwundene_jobs(test_queue)}") from None
	assert refresh.is_failed, f"Job nicht als fehlgeschlagen markiert: {refresh.get_status()}"
	registry = FailedJobRegistry(queue=test_queue)
	assert job.id in registry.get_job_ids(), (
		f"Job nicht in der Failed-Registry: {_verschwundene_jobs(test_queue)}")


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


def _freier_port() -> int:
	"""Ein freier TCP-Port statt der festen 8791.

	Ein fester Port ist eine zweite Zeitbombe: laufen zwei Testlaeufe
	gleichzeitig (oder haelt ein abgebrochener Uvicorn-Thread den Port),
	scheitert der BIND — nichts davon hat mit dem Pruefziel zu tun.
	"""
	import socket

	with socket.socket() as sock:
		sock.bind(("127.0.0.1", 0))
		return sock.getsockname()[1]


def _startbereit(server, frist: float = 30) -> None:
	"""Wartet mit Frist auf `server.started` (statt 200 x 50 ms).

	Die Schleife deckte 10 s ab; unter Last startet der Uvicorn-Thread
	langsamer. Gemessen wird weiterhin `server.started` — keine Vermutung.
	"""
	import time as _time

	ende = _time.monotonic() + frist
	while _time.monotonic() < ende:
		if server.started:
			return
		_time.sleep(0.02)
	assert server.started, f"Uvicorn-Thread nach {frist} s nicht gestartet"


def _warten_bis_empfangsbereit(client, grenze: float = 20) -> None:
	"""Misst, dass der Client Nachrichten empfaengt (Raum steht), statt zu schlafen.

	Gleiche Begruendung wie in `test_google_realtime._warten_bis_empfangsbereit`:
	`connect()` ist zurueck, sobald der Engine.IO-Handshake steht — der
	`connect`-Handler des Servers (der `enter_room` aufruft) kann noch
	ausstehen. Eine Sonde ueber den ECHTEN Redis-Weg (`publish_realtime`,
	hier ohne laufende Event-Loop -> synchroner Zweig) wiederholt, bis sie im
	Client ankommt. Eigener Ereignisname, damit die Pruefung
	`received[0]["status"] == "importing"` unverfaelscht bleibt.
	"""
	import time as _time

	from diakronos_app.frappe_compat.realtime import publish_realtime

	empfangen = threading.Event()

	def _sonde(_daten):
		empfangen.set()

	client.on("zeit1_sonde", _sonde)
	try:
		ende = _time.monotonic() + grenze
		while _time.monotonic() < ende:
			publish_realtime("zeit1_sonde", {"bereit": True}, user="Administrator")
			if empfangen.wait(1.5):
				return
			_time.sleep(0.1)
		raise AssertionError(
			f"Socket-Client nach {grenze} s nicht empfangsbereit — die Sonde kam "
			"nie an; Realtime-Zustellung pruefen, nicht den Test aufweichen")
	finally:
		try:
			client.handlers["/"].pop("zeit1_sonde", None)
		except Exception:  # noqa: BLE001 — Aufraeumen darf nie werfen
			pass


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
	port = _freier_port()

	session_cookie = client.cookies.get("sid")
	client = socketio.Client(reconnection=False)

	@client.on("gcal_import_progress")
	def _on(data):  # noqa: ANN001
		received.append(data)
		got.set()

	config = uvicorn.Config(socket_app, host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=2)
	server = uvicorn.Server(config)
	server_thread = threading.Thread(target=server.run, daemon=True)
	server_thread.start()
	try:
		_startbereit(server, frist=30)
		# ZEIT-1: `wait()` in socketio.Client ist 1 s — unter Last reisst der
		# Engine.IO-Handshake (Verbindung ueber localhost, Redis-Manager)
		# diese Grenze. Eine eigene Frist schwaescht die Aussage nicht: der
		# Client muss weiterhin verbinden, nur eben ohne willkuerliche Sekunde.
		client.connect(f"http://127.0.0.1:{port}", socketio_path="socket.io",
		               headers={"Cookie": "sid=" + session_cookie}, wait_timeout=30)
		# ZEIT-1: statt `sleep(0.4)` ("dem Client Zeit geben") wird die
		# Empfangsbereitschaft GEMESSEN — dieselbe Technik wie in
		# test_google_realtime._warten_bis_empfangsbereit: eine Sonde ueber
		# den echten Redis-Weg, wiederholt bis sie im Client ankommt. Erst
		# dann sitzt der Client im Raum `user:Administrator`. Unter Last
		# fiel die feste Wartezeit zu kurz aus; ein `sleep` haette die
		# Aussage des Tests ohnehin nur auf eine Vermutung gestuetzt.
		_warten_bis_empfangsbereit(client)

		from diakronos_app.frappe_compat.realtime import publish_realtime

		publish_realtime("gcal_import_progress",
		                 {"status": "importing", "imported": 1},
		                 user="Administrator")

		assert got.wait(timeout=30), "kein Realtime-Ereignis empfangen"
	finally:
		try:
			client.disconnect()
		except Exception:  # noqa: BLE001
			pass
		server.should_exit = True
		server_thread.join(timeout=5)

	assert received, "kein Realtime-Ereignis empfangen"
	assert received[0]["status"] == "importing"
