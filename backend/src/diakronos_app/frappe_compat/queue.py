"""`frappe.enqueue` — Hintergrundjobs ueber RQ (P6a Teil 2).

Original-Pendants (READ-ONLY):
`referenz/diakronos-frappe/diakronos/kronos/api/google_import.py:288`
`referenz/diakronos-frappe/diakronos/diakonos/doctype/mitglied/mitglied.py:196`
`referenz/diakronos-frappe/diakronos/diakonos/api/audit_policy/decorator.py:236`

Frappe-Aufrufe, die hier abgebildet werden (alle drei Fundstellen):

    frappe.enqueue("diakronos.kronos.api.google_import._do_import",
                   mappings=..., user=..., queue="long", timeout=600,
                   enqueue_after_commit=False)          # dotted path als String
    frappe.enqueue(send_notification, queue="short",
                   audit_log_name=..., target_user=...)  # Callable direkt

WICHTIG — Abweichung vom Original, bewusst und begruendet:
Frappe loest den Job im Worker ueber `frappe.utils.get_attr(dotted_path)` auf.
Im Standalone gibt es `frappe` nicht; der Worker laeuft als eigener Prozess
(`rq worker ... default` im `worker`-Container) und importiert die Funktion
ueber DENSELBEN dotted path. Damit beide Formen des Originals tragen, werden
Callables beim Einreihen auf ihren Importpfad abgebildet
(`<modul>.<qualname>`) — RQ importiert diese Zeichenkette im Worker.

Kein synchroner Fallback: `enqueue` gibt IMMER zurueck, bevor die Arbeit
laeuft (Kartenanforderung). Ist Redis nicht erreichbar, wird eine
`EnqueueError` geworfen — der Aufrufer soll NICHT glauben, der Job laufe.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from redis import Redis
from rq import Queue

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.queue")

# Frappe-Queues: `short`/`default`/`long`. Der `worker`-Container konsumiert
# (noch) nur `default`; unbekannte Queues landen trotzdem in Redis und werden
# von einem `rq worker <name>` abgearbeitet, sobald einer laeuft. Die Namen
# bleiben deshalb 1:1 wie im Original.
DEFAULT_QUEUE = "default"
# Frappe-Default fuer `timeout`: 300 s ("long"). Uebernommen.
DEFAULT_TIMEOUT = 300


class EnqueueError(RuntimeError):
	"""Der Job konnte nicht eingereiht werden (z. B. Redis nicht erreichbar)."""


def _redis() -> Redis:
	return Redis.from_url(settings.redis_url)


def _job_target(func: str | Callable) -> str:
	"""Ziel des Jobs als dotted path — die Form, die RQ im Worker importiert.

	* String: unveraendert uebernehmen (Original nutzt hier den Frappe-Pfad,
	  z. B. `diakronos.kronos.api.google_import._do_import`).
	* Callable: `<modul>.<qualname>` — genau das, was `pickle`-freie RQ-Ausfuehrung
	  braucht. Frappe-Reexports (`from .permissions import x`) tragen denselben
	  Importpfad wie ihr Modul, deshalb ist `__module__` hier korrekt.
	"""
	if isinstance(func, str):
		path = func.strip()
		if not path:
			raise EnqueueError("enqueue: leere Job-Angabe")
		return path
	if callable(func):
		module = getattr(func, "__module__", None)
		name = getattr(func, "__qualname__", None) or getattr(func, "__name__", None)
		if not module or not name:
			raise EnqueueError(f"enqueue: kein Importpfad fuer {func!r}")
		return f"{module}.{name}"
	raise EnqueueError(f"enqueue: weder dotted path noch Callable: {func!r}")


def resolve_job(path: str) -> Callable:
	"""Dotted path -> Funktion. Erst ueber die Registry, dann per Import.

	Die Registry (`frappe_compat.registry`) kennt die portierten API-Pfade.
	Faellt der Pfad nicht in die Registry (z. B. ein Original-Frappe-Pfad fuer
	ein Modul, das noch nicht portiert ist), wird `importlib` benutzt — das ist
	dieselbe Aufloesung, die RQ selbst im Worker fahren wuerde.
	"""
	from diakronos_app.frappe_compat.registry import lookup

	fn = lookup(path)
	if fn is not None:
		return fn

	module_name, _, attr = path.rpartition(".")
	if not module_name:
		raise EnqueueError(f"enqueue: '{path}' ist kein dotted path")
	try:
		module = importlib.import_module(module_name)
	except ImportError as exc:  # noqa: PERF203
		raise EnqueueError(f"enqueue: Modul '{module_name}' nicht importierbar") from exc
	try:
		return getattr(module, attr)
	except AttributeError as exc:
		raise EnqueueError(f"enqueue: '{attr}' fehlt in '{module_name}'") from exc


def enqueue(
	func: str | Callable,
	queue: str = DEFAULT_QUEUE,
	timeout: int | None = None,
	**kwargs: Any,
) -> Any:
	"""`frappe.enqueue` — Job einreihen, ohne auf das Ergebnis zu warten.

	Signatur und Optionsnamen entsprechen dem Original
	(`queue`, `timeout`, `enqueue_after_commit`). `enqueue_after_commit` wird
	akzeptiert und ignoriert: die Compat-Schicht committet jeden Satz sofort
	(SQLAlchemy-Sessions), es gibt hier keinen offenen Transaktionskontext wie
	in Frappe. Das ist dokumentiert, nicht still weggelassen.

	Rueckgabe ist das RQ-`Job`-Objekt. Der Aufrufer kann `job.id` nutzen, um
	spaeter den Status zu pruefen.
	"""
	# Frappe akzeptiert sowohl `queue` als auch das Synonym `queue_name`.
	# Hier bleibt es beim Original-Namen; unbekannte Frappe-Optionen werden
	# nicht verschluckt, sondern als Job-Kwargs weitergereicht (wie Frappe).
	if "enqueue_after_commit" in kwargs:
		kwargs.pop("enqueue_after_commit")

	target = _job_target(func)
	# Aufloesung VOR dem Einreihen: ein Tippfehler im Pfad soll hier knallen
	# (fail fast), nicht erst im Worker, wo niemand mehr hinsieht.
	resolve_job(target)

	try:
		q = Queue(name=queue, connection=_redis())
		# RQ 2.x nennt die Option `job_timeout`; `timeout` waere hier ein
		# FUNKTIONS-Argument und wuerde im Worker als unerwartetes Kwarg
		# ankommen (`TypeError: ... unexpected keyword argument 'timeout'`).
		# Der Frappe-Name der Compat-Funktion bleibt `timeout` (Original).
		job = q.enqueue(target, job_timeout=timeout or DEFAULT_TIMEOUT, **kwargs)
	except EnqueueError:
		raise
	except Exception as exc:  # noqa: BLE001 — Redis/Netz -> klarer Fehler
		raise EnqueueError(f"enqueue an Queue '{queue}' fehlgeschlagen: {exc}") from exc

	logger.info("enqueue %s -> Queue '%s' (job %s)", target, queue, job.id)
	return job


__all__ = ["DEFAULT_QUEUE", "DEFAULT_TIMEOUT", "EnqueueError", "enqueue", "resolve_job"]
