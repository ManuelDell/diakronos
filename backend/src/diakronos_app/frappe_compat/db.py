"""`db` — minimales `frappe.db` (SQL-Passthrough + get_value/count/exists).

Der einzige im Altcode benutzte Teil ist `frappe.db.sql(<sql>, <params>, as_dict=True)`
mit `%(name)s`-Platzhaltern, plus `count`/`exists`/`get_value`. Wir reichen SQL
bewusst 1:1 an die Session weiter (Frappe tut dasselbe); die Migration der
Abfragen auf SQLAlchemy ist Sache der jeweiligen Portierkarte.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from .session import session as _session  # noqa: F401  (frappe.db.session gibt es, hier nicht gebraucht)

# Frappe-Platzhalter `%(name)s` -> SQLAlchemy/SQLite `:name`.
# `%` in LIKE-Mustern (`f"%{suche}%"`) wuerde SQLAlchemy sonst als
# Bind-Parameter-Einleitung interpretieren ("syntax error at or near %").
_PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def _adapt_placeholders(query: str, params: Any):
	"""Uebersetzt Frappe-`%(name)s` in `:name` und escapt `%` fuer SQLAlchemy."""
	names = _PLACEHOLDER.findall(query)
	if not names:
		return query, params
	adapted = _PLACEHOLDER.sub(r":\1", query)
	# `%%` (bereits escapt) bleibt, einzelne `%` werden zu `%%`.
	adapted = adapted.replace("%%", "\x00").replace("%", "%%").replace("\x00", "%%")
	if isinstance(params, dict):
		params = {k: v for k, v in params.items() if k in names}
	return adapted, params


class Database:
	"""Duenne Huelle um die aktuelle SQLAlchemy-Session-Factory."""

	def sql(self, query: str, params: Any = None, as_dict: bool = False):
		from diakronos_app.db import SessionLocal

		query, params = _adapt_placeholders(query, params)
		sess = SessionLocal()
		try:
			result = sess.execute(text(query), params or {})
			rows = result.mappings().all() if as_dict else result.all()
			# Frappe liefert bei nicht-SELECT (INSERT/UPDATE/DELETE) oft eine Liste.
			try:
				return [dict(r) for r in rows] if as_dict else [tuple(r) for r in rows]
			except Exception:  # pragma: no cover — defensiver Pfad
				return rows
		finally:
			sess.close()

	def get_value(self, *args, **kwargs):
		from .query import get_value

		return get_value(*args, **kwargs)

	def set_value(self, doctype: str, filters, fieldname, value, update_modified: bool = True) -> None:
		"""Frappe-`db.set_value` im Bulk-Modus (filters = dict).

		Ersetzt `mark_notifications_read` im Original (api/audit.py:103), das
		alle offenen Zeilen eines Users in EINEM UPDATE umsetzt. Wirkt auf alle
		Treffer von `filters`; ohne Treffer passiert nichts (wie Frappe).
		"""
		from sqlalchemy import update

		from diakronos_app.db import SessionLocal

		from .query import _compile_filters, _require_doctype

		model = _require_doctype(doctype)
		col = getattr(model, fieldname, None)
		if col is None:
			raise KeyError(f"{doctype}: unbekanntes Feld {fieldname!r}")

		sess = SessionLocal()
		try:
			stmt = update(model).values({fieldname: value})
			if update_modified and hasattr(model, "modified"):
				stmt = stmt.values(modified=__import__("datetime").datetime.now())
			for clause in _compile_filters(doctype, model, filters):
				stmt = stmt.where(clause)
			sess.execute(stmt)
			sess.commit()
		finally:
			sess.close()

	def count(self, doctype: str, filters=None, **kwargs) -> int:
		from sqlalchemy import func, select

		from diakronos_app.db import lesesitzung

		from .query import _compile_filters, _require_doctype

		model = _require_doctype(doctype)
		# Lesehilfe: im Request-Rahmen die vorhandene Sitzung mitbenutzen statt
		# eine zweite zu oeffnen (siehe diakronos_app/db.py).
		with lesesitzung() as sess:
			query = select(func.count()).select_from(model)
			for clause in _compile_filters(doctype, model, filters):
				query = query.where(clause)
			return int(sess.execute(query).scalar() or 0)

	def exists(self, doctype: str, filters=None, **kwargs) -> bool:
		return self.count(doctype, filters) > 0

	# Frappe hat viele weitere Methoden; sie werden nach Bedarf ergaenzt.
	# Bewusst NICHT implementiert, damit Aufrufe laut scheitern statt still falsch.


db = Database()
