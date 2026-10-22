"""`get_all`, `get_doc`, `get_value` — Abfrage-Compiler auf SQLAlchemy.

Unterstuetzte Filter-Formen (abgeleitet aus Nutzungsabzug der Frappe-API und
dem Altcode, NICHT erfunden):

    {"feld": "wert"}                  Gleichheit
    [["feld", "=", "wert"], ...]      Liste von Tripeln
    {"feld": ["like", "%x%"]}         LIKE
    {"feld": ["in", [...]]}           IN
    {"feld": ["not in", [...]]}       NOT IN
    {"feld": [">", v]} / "<" / ">=" / "<=" / "!="
    {"feld": ["between", [a, b]]}
    {"feld": ["is", "set"]}           IS NOT NULL
    {"feld": ["is", "not set"]}       IS NULL

Child-Tabellen werden IMMER nach `idx` sortiert (Frappe-Konvention).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import and_, asc, desc, func, not_, or_, select
from sqlalchemy.orm import Session

from diakronos_app.db import SessionLocal

from .exceptions import DoesNotExistError
from .registry_gen import column_names, is_child_table, is_known, model_for

# J (BF1): „Suche beachtet Gross-/Kleinschreibung nicht" — und Umlaute sollen
# gleichwertig sein („mueller" findet „Müller"). SQLAlchemy's `col.like` ist in
# PostgreSQL case-SENSITIV, und SQLites `LOWER` laesst Nicht-ASCII (Umlaute)
# unveraendert. Deshalb wird VOR `LOWER` jede Umlaut-/ß-Schreibweise ersetzt.
# Der Ausdruck enthaelt KEINE Nutzereingabe (nur feste Zeichen) — der
# Suchbegriff bleibt ein gebundener Parameter.
_FALTUNG = (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
            ("ä", "ae"), ("ö", "oe"), ("ü", "ue"))


def _gefaltet(col):
    """`LOWER(REPLACE(...))` als SQLAlchemy-Ausdruck — umlaut-/case-tolerant."""
    ausdruck = col
    for von, nach in _FALTUNG:
        ausdruck = func.replace(ausdruck, von, nach)
    return func.lower(ausdruck)


def _like_tolerant(col, muster):
    """`like` ohne Ruecksicht auf Gross-/Kleinschreibung und Umlautform.

    Muster und Spalte werden gleich gefaltet; nur so findet „Mueller" „MÜLLER"
    auf beiden Datenbanken identisch (siehe `_gefaltet`).
    """
    return _gefaltet(col).like(_normalisiere_like(muster))


def _normalisiere_like(muster):
    text = str(muster or "")
    for von, nach in _FALTUNG:
        text = text.replace(von, nach)
    return text.lower()


def _like_wildcards_escapen(muster):
    """K-2: `%` und `_` im Nutzertext als Zeichen behandeln, nicht als Platzhalter.

    Ohne Maskierung fände die Lied-Dublettenprüfung auf einen Titel wie „100 %"
    mit `%` beliebige Zeilen — die Regel wäre zu weit. Der Backslash wird
    zuerst maskiert, damit er selbst kein Escape-Zeichen wird.
    """
    return str(muster or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _like_exakt(col, wert):
    """`like` ohne Platzhalter: gleicher Text (Gross/Klein, Umlautform egal).

    Anders als `like` sind `%` und `_` hier KEINE Platzhalter — der Wert wird
    maskiert und mit `ESCAPE '\\\\'` verglichen. Fuer Gleichheits-Kandidaten
    (z. B. Lied-Dubletten) statt fuer Freitextsuche.
    """
    muster = _normalisiere_like(_like_wildcards_escapen(wert))
    return _gefaltet(col).like(muster, escape="\\")


_COMPARATORS = {
	"=": lambda col, val: col == val,
	"!=": lambda col, val: col != val,
	">": lambda col, val: col > val,
	"<": lambda col, val: col < val,
	">=": lambda col, val: col >= val,
	"<=": lambda col, val: col <= val,
	"like": _like_tolerant,
	"like_exakt": _like_exakt,
	"not like": lambda col, val: ~_like_tolerant(col, val),
	"in": lambda col, val: col.in_(list(val)),
	"not in": lambda col, val: col.notin_(list(val)),
	"between": lambda col, val: col.between(val[0], val[1]),
}


def _require_doctype(doctype: str):
	if not is_known(doctype):
		# Frappe antwortet auf einen unbekannten DocType mit
		# `DoesNotExistError` (404), nicht mit einem nackten KeyError (500).
		raise DoesNotExistError(f"DocType {doctype!r} nicht gefunden")
	return model_for(doctype)


def _field(cols: set[str], doctype: str, name: str):
	"""Spalte aufloesen; `name as alias` -> (spalte, alias)."""
	if " as " in name.lower():
		base, alias = name.lower().split(" as ", 1)
		base = base.strip()
		alias = alias.strip()
	else:
		base, alias = name, None
	base = base.strip()
	if base not in cols:
		raise KeyError(f"{doctype}: unbekanntes Feld {base!r}")
	return base, alias


def _spaltenwert(col, wert: Any) -> Any:
	"""Einen Filterwert an den echten Spaltentyp anpassen.

	PostgreSQL ist streng, wo SQLite tolerant ist. Der Altcode schreibt in
	Filtern die Frappe-ueblichen `0`/`1` fuer Check-Felder; in PostgreSQL sind
	das echte `boolean`-Spalten, und `WHERE gelesen = 1` scheitert mit
	`operator does not exist: boolean = integer`. Dasselbe gilt fuer
	Datums-/Zeitspalten, die als ISO-String ankommen
	(`timestamp without time zone <= character varying`).

	Die Koerzierung sitzt bewusst HIER, im gemeinsamen Engpass aller
	Filterformen (dict, Tripel-Liste, `or_filters`), und nicht in einem
	Hilfsmodul, das jedes API-Modul einzeln aufrufen muesste. Genau dieser
	Fehler ist am 2026-09-25 aufgetreten: der Fix lag in
	`frappe_compat/api_helpers._coerce_filters`, `api/audit.py` ging aber ueber
	`or_filters` daran vorbei und lieferte 500. Eine Sicherung, die man
	vergessen kann, wird vergessen.
	"""
	from sqlalchemy import Boolean, Date, DateTime, Time

	try:
		typ = col.type
	except AttributeError:  # pragma: no cover — defensiver Pfad
		return wert
	if wert is None:
		return wert
	if isinstance(typ, Boolean) and not isinstance(wert, bool):
		if wert in (0, "0", "false", "False"):
			return False
		if wert in (1, "1", "true", "True"):
			return True
		return wert
	if isinstance(typ, (Date, DateTime, Time)) and isinstance(wert, str):
		from datetime import date, datetime, time

		text = wert.strip()
		if not text:
			return wert
		try:
			if isinstance(typ, DateTime):
				return datetime.fromisoformat(text)
			if isinstance(typ, Date):
				return date.fromisoformat(text[:10])
			return time.fromisoformat(text)
		except ValueError:
			return wert
	return wert


def _koerziere(col, op: str, wert: Any) -> Any:
	"""Wie `_spaltenwert`, aber fuer Operatoren mit Listenwerten."""
	if op in ("in", "not in") and isinstance(wert, (list, tuple, set)):
		return [_spaltenwert(col, v) for v in wert]
	if op == "between" and isinstance(wert, (list, tuple)) and len(wert) == 2:
		return [_spaltenwert(col, wert[0]), _spaltenwert(col, wert[1])]
	if op == "like":
		return wert
	return _spaltenwert(col, wert)


def _condition(doctype: str, model: type, feld: str, op: Any):
	cols = column_names(doctype)
	col = getattr(model, feld) if feld in cols else None
	if col is None:
		raise KeyError(f"{doctype}: unbekanntes Filterfeld {feld!r}")
	return _COMPARATORS[op[0]](col, _koerziere(col, op[0], op[1]))


def _compile_filters(doctype: str, model: type, filters) -> list:
	"""Uebersetzt eine Frappe-Filter-Struktur in SQLAlchemy-Bedingungen."""
	if not filters:
		return []

	clauses: list = []

	# Form 1: Liste von Tripeln [["feld", "op", "wert"], ...]
	if isinstance(filters, (list, tuple)):
		for item in filters:
			if not isinstance(item, (list, tuple)) or len(item) != 3:
				raise ValueError(f"Ungueltiger Filter-Eintrag: {item!r}")
			feld, op, val = item
			clauses.append(_condition(doctype, model, feld, (op, val)))
		return clauses

	# Form 2: dict {"feld": wert} oder {"feld": [op, wert]}
	if isinstance(filters, dict):
		for feld, spec in filters.items():
			# Link-Feld auf ein Kind/verknuepftes DocType: "feld.value" -> Feldfeld
			feld = feld.replace(".", "_") if feld not in column_names(doctype) else feld
			if isinstance(spec, (list, tuple)) and len(spec) == 2 and isinstance(spec[0], str):
				op, val = spec[0].lower(), spec[1]
				if op == "is":
					col = getattr(model, feld)
					clauses.append(col.isnot(None) if val == "set" else col.is_(None))
					continue
				clauses.append(_condition(doctype, model, feld, (op, val)))
			else:
				col = getattr(model, feld) if feld in column_names(doctype) else None
				if col is None:
					raise KeyError(f"{doctype}: unbekanntes Filterfeld {feld!r}")
				clauses.append(col == _spaltenwert(col, spec))
		return clauses

	raise ValueError(f"Nicht unterstuetzte Filterform: {type(filters).__name__}")


def _apply_or_filters(doctype: str, model: type, query, or_filters):
	if not or_filters:
		return query
	parts = []
	# or_filters hat dieselbe Struktur wie filters, aber jede Bedingung wird ODER-verknuepft.
	if isinstance(or_filters, dict):
		items = list(or_filters.items())
		for feld, spec in items:
			if isinstance(spec, (list, tuple)) and len(spec) == 2 and isinstance(spec[0], str):
				parts.append(_condition(doctype, model, feld, (spec[0].lower(), spec[1])))
			else:
				parts.append(getattr(model, feld) == spec)
	elif isinstance(or_filters, (list, tuple)):
		for item in or_filters:
			if isinstance(item, (list, tuple)) and len(item) == 3:
				op, val = item[1].lower(), item[2]
				# BLD-R6: „is“ auch im ODER-Zweig verstehen (`["element_end",
				# "is", "not set"]` -> IS NULL). Nur der UND-Zweig kannte das
				# bisher; im ODER landete es in `_COMPARATORS` und brach mit
				# KeyError ab.
				if op == "is":
					col = getattr(model, item[0], None)
					if col is None:
						raise KeyError(f"{doctype}: unbekanntes Filterfeld {item[0]!r}")
					parts.append(col.isnot(None) if val == "set" else col.is_(None))
					continue
				parts.append(_condition(doctype, model, item[0], (op, val)))
			elif isinstance(item, (list, tuple)) and len(item) == 2:
				parts.append(_condition(doctype, model, item[0], (item[1].lower(), item[2] if len(item) > 2 else None)))
			else:
				raise ValueError(f"Ungueltiger or_filter: {item!r}")
	else:
		raise ValueError("Nicht unterstuetzte or_filters-Form")
	if parts:
		query = query.where(or_(*parts))
	return query


def _serialize(value: Any) -> Any:
	if isinstance(value, (datetime, date)):
		return str(value)
	if isinstance(value, Decimal):
		return float(value)
	return value


def _row_to_dict(row, field_map: list[tuple[str, str]]) -> dict:
	out: dict[str, Any] = {}
	for attr, alias in field_map:
		out[alias] = _serialize(getattr(row, attr))
	return out


# ── oeffentliche API ────────────────────────────────────────────────────────


def get_all(
	doctype: str,
	filters=None,
	or_filters=None,
	fields: Iterable[str] | str | None = None,
	order_by: str | None = None,
	limit_start: int = 0,
	limit_page_length: int | None = None,
	as_list: bool = False,
	pluck: str | None = None,
	session: Session | None = None,
) -> list[dict[str, Any]] | list[list[Any]] | list[Any]:
	"""Frappe-`get_all` ueber die SQLAlchemy-Modelle."""
	model = _require_doctype(doctype)
	# Lesehilfe: im Request-Rahmen die vorhandene Sitzung mitbenutzen statt
	# eine zweite zu oeffnen (siehe diakronos_app/db.py).
	if session is None:
		from diakronos_app.db import sitzung_fuer_lesen

		sess, own_session = sitzung_fuer_lesen()
	else:
		sess, own_session = session, False
	try:
		# Feldauswahl
		pluck_field = pluck
		if pluck_field is not None:
			fields = [pluck_field]
		if not fields or fields == "*":
			field_map = [(c.name, c.name) for c in model.__table__.columns]
		elif isinstance(fields, str):
			field_map = [(_field(column_names(doctype), doctype, f)[0], _field(column_names(doctype), doctype, f)[1] or f)
			             for f in (x.strip() for x in fields.split(",")) if f]
		else:
			field_map = []
			for f in fields:
				base, alias = _field(column_names(doctype), doctype, f)
				field_map.append((base, alias or f))

		cols = [getattr(model, attr) for attr, _ in field_map]
		query = select(*cols)
		for clause in _compile_filters(doctype, model, filters):
			query = query.where(clause)
		query = _apply_or_filters(doctype, model, query, or_filters)

		# Sortierung: explizit, sonst Child-Tabellen immer nach idx.
		if order_by:
			for token in str(order_by).split(","):
				token = token.strip()
				if not token:
					continue
				descending = token.lower().endswith(" desc")
				name = token.rsplit(" ", 1)[0].strip().strip("`")
				col = getattr(model, name, None)
				if col is None:
					raise KeyError(f"{doctype}: unbekanntes Sortierfeld {name!r}")
				query = query.order_by(desc(col) if descending else asc(col))
		elif is_child_table(doctype):
			query = query.order_by(asc(model.idx))

		if limit_start:
			query = query.offset(int(limit_start))
		if limit_page_length is not None:
			query = query.limit(int(limit_page_length))

		rows = sess.execute(query).all()

		if pluck_field is not None:
			return [_serialize(r[0]) for r in rows]
		if as_list:
			return [[_serialize(v) for v in r] for r in rows]
		return [_row_to_dict(r, field_map) for r in rows]
	finally:
		if own_session:
			sess.close()


def get_doc(doctype: str, name: str, session: Session | None = None):
	"""Ein Dokument per `name` laden. Wirft `DoesNotExistError`, wenn nicht da.

	Rueckgabe ist ein `Document`-Wrapper (Frappe-Feeling: `doc.feld`, `doc.get()`,
	`doc.as_dict()`), kein nacktes SQLAlchemy-Modell. So verhaelt sich der
	portierte Altcode unveraendert.
	"""
	from .doc import Document

	model = _require_doctype(doctype)
	# Lesehilfe: im Request-Rahmen die vorhandene Sitzung mitbenutzen statt
	# eine zweite zu oeffnen (siehe diakronos_app/db.py). Das Dokument haelt die
	# Sitzung fuer Lazy-Attribute am Leben; eine geliehene Sitzung darf es NICHT
	# schliessen (sie gehoert dem Aufruf).
	if session is None:
		from diakronos_app.db import sitzung_fuer_lesen

		sess, own_session = sitzung_fuer_lesen()
	else:
		sess, own_session = session, False
	try:
		obj = sess.get(model, name)
		if obj is None:
			raise DoesNotExistError(f"{doctype} {name!r} existiert nicht")
		return Document(obj, session=sess, besitzt_sitzung=own_session)
	finally:
		if own_session:
			# Session offen halten, solange das Dokument lebt (Lazy-Attribute);
			# geschlossen wird sie mit dem Objekt (siehe Document.__del__).
			pass


def get_value(
	doctype: str,
	filters,
	fieldname: str | Iterable[str],
	as_dict: bool = False,
	order_by: str | None = None,
):
	"""Frappe-`db.get_value`: erster Treffer, ein Feld oder mehrere.

	`fieldname` ist ein String (Skalar zurueck) oder eine Liste (Liste/Dict
	zurueck). `filters` kann ein Name sein oder eine Filter-Struktur.
	"""
	model = _require_doctype(doctype)
	cols = column_names(doctype)

	# filters als "Name" (String) -> PK-Gleichheit
	if isinstance(filters, str):
		filters = {"name": filters}

	wanted = [fieldname] if isinstance(fieldname, str) else list(fieldname)

	field_map = []
	for f in wanted:
		base, alias = _field(cols, doctype, f)
		field_map.append((base, alias or f))

	# Lesehilfe: im Request-Rahmen die vorhandene Sitzung mitbenutzen.
	from diakronos_app.db import sitzung_fuer_lesen

	sess, _eigene = sitzung_fuer_lesen()
	try:
		query = select(*[getattr(model, attr) for attr, _ in field_map])
		for clause in _compile_filters(doctype, model, filters):
			query = query.where(clause)
		if order_by:
			token = str(order_by).strip()
			descending = token.lower().endswith(" desc")
			fname = token.rsplit(" ", 1)[0].strip().strip("`")
			query = query.order_by(desc(getattr(model, fname)) if descending else asc(getattr(model, fname)))
		elif is_child_table(doctype):
			query = query.order_by(asc(model.idx))
		row = sess.execute(query).first()
		if row is None:
			return None
		if isinstance(fieldname, str):
			return _serialize(row[0])
		if as_dict:
			return {alias: _serialize(getattr(row, attr)) for attr, alias in field_map}
		return [_serialize(v) for v in row]
	finally:
		if _eigene:
			sess.close()
