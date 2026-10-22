"""`Document` — duenne Huelle um eine SQLAlchemy-Instanz mit Frappe-Feeling.

Deckt genau das ab, was der Altcode auf Dokumenten tut:
`doc.name`, `doc.feld`, `doc.get("feld")`, `doc.set("feld", wert)`,
`doc.get_doc(doctype, name)`, `doc.insert()`, `doc.save()`,
`doc.db_set(feld, wert)`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect

from .exceptions import DoesNotExistError


class Document:
	"""Wrapper mit Frappe-artigem Zugriff. Das Modell bleibt die Wahrheit."""

	def __init__(self, obj: Any, session=None, besitzt_sitzung: bool | None = None):
		self._obj = obj
		self._session = session
		# Nur Sessions schliessen, die wir selbst geoeffnet haben.
		# `besitzt_sitzung` ist die explizite Aussage des Aufrufers (get_doc);
		# ohne Angabe gilt die alte Regel: eine uebergebene Sitzung gehoert uns.
		self._owns_session = (session is not None) if besitzt_sitzung is None else besitzt_sitzung

	# ── Aufraeumen ─────────────────────────────────────────────────────────
	def close(self) -> None:
		"""Session schliessen, falls dieses Dokument sie besitzt."""
		if self._owns_session and self._session is not None:
			try:
				self._session.close()
			finally:
				self._session = None

	def __enter__(self) -> "Document":
		return self

	def __exit__(self, *exc) -> None:
		self.close()

	def __del__(self):  # pragma: no cover — GC-Pfad
		try:
			self.close()
		except Exception:
			pass

	# ── Feldzugriff ────────────────────────────────────────────────────────
	def __getattr__(self, item: str) -> Any:
		# Nur fuer Felder durchreichen, die am Modell existieren.
		try:
			return getattr(self._obj, item)
		except AttributeError as exc:  # pragma: no cover
			raise AttributeError(item) from exc

	def __setattr__(self, key: str, value: Any) -> None:
		if key.startswith("_"):
			object.__setattr__(self, key, value)
			return
		setattr(self._obj, key, value)

	def get(self, key: str, default: Any = None) -> Any:
		return getattr(self._obj, key, default)

	def set(self, key: str, value: Any) -> None:
		"""`doc.set("feld", wert)` — Frappes Schreibweg neben `doc.feld = ...`.

		Der Altcode nutzt beides (`profile.py:67` setzt die Umlaut-Spalte
		`straße` ueber `set`, weil `doc.straße` unlesbar waere). Die
		SQLAlchemy-Instanz kennt `__setattr__`, deshalb ist beides derselbe
		Weg — hier als benannte Methode, damit der Altcode unveraendert
		laeuft.
		"""
		setattr(self._obj, key, value)

	def __getitem__(self, key: str) -> Any:
		return getattr(self._obj, key)

	def __setitem__(self, key: str, value: Any) -> None:
		setattr(self._obj, key, value)

	@property
	def name(self) -> str:
		return getattr(self._obj, "name")

	@property
	def doctype(self) -> str:
		"""Der DocType-Name des Dokuments (`Has Role`, nicht `HasRole`).

		N12b: Vorher fiel die Eigenschaft auf den KLASSEN-Namen zurueck. Der
		generische Frappe-Name traegt ein Leerzeichen (`Has Role`), deshalb
		trafen Vergleiche wie `doctype in ("User", "Has Role")` nie zu — und
		die Schranken der Verwaltungs-DocTypes liefen ueber den
		`doc.save()`-Weg ins Leere.
		"""
		from .registry_gen import doctype_fuer_klasse

		namen = getattr(self._obj, "doctype", None)
		if namen:
			return str(namen)
		return doctype_fuer_klasse(type(self._obj).__name__) or type(self._obj).__name__

	def as_dict(self) -> dict:
		return {c.name: getattr(self._obj, c.name) for c in self._obj.__table__.columns}

	# ── Persistenz ─────────────────────────────────────────────────────────
	def _coerce_typen(self) -> None:
		"""Wandelt die GESETZTEN Felder an die echten Spaltentypen an.

		Der Altcode setzt Felder genauso wie hier (`doc.geburtstag =
		"1988-02-29"`, `doc.datenschutz_einwilligung = 1`) und verlaesst sich
		dabei auf Frappe, das die Werte an den DocType-Typ bindet. SQLAl tut
		das nicht: eine `Date`-Spalte bekommt einen ISO-**String** und SQLite
		bricht mit `TypeError: SQLite Date type only accepts Python date
		objects as input` ab — dieselbe Fehlerklasse wie in P4c1 (dort fuer
		timestamp), nur ueber den anderen Schreibweg.

		`_create`/`_update_doc` in `api_helpers` koerzieren bereits; dieser
		Schritt fehlte nur dem `Document`-Weg (`doc.feld = ...; doc.save()`,
		`doc.set(...)`). Dieselbe `_coerce`-Logik, damit beide Wege dasselbe
		Ergebnis liefern — und nur tatsaechlich AENDERTE Felder werden
		angesehen, ein unberuehrtes `Date`-Feld bleibt ein `date`.
		"""
		from .api_helpers import _coerce
		from .registry_gen import is_known, model_for

		obj = self._obj
		typname = type(obj).__name__
		if not is_known(typname):
			return
		geaendert = {
			attr.key
			for attr in inspect(obj).attrs
			if attr.history.has_changes()
		}
		if not geaendert:
			return
		# `mitglied_name` o. ae. sind Foreign-Key-Zuordnungen, keine Spalten
		# des DocTypes — die `_coerce` sonst auf einer falschen Spalte sucht.
		cols = {c.name for c in model_for(typname).__table__.columns}
		payload = {
			feld: getattr(obj, feld)
			for feld in geaendert
			if feld in cols
		}
		if not payload:
			return
		for feld, wert in _coerce(typname, payload).items():
			if getattr(obj, feld) is not wert:
				object.__setattr__(obj, feld, wert)

	def _pruefe_mitglied(self) -> None:
		from .api_helpers import (
			_normalisiere_mitglied_email,
			_pruefe_konto_schreibzugriff,
			_pruefe_mitglied_schreibzugriff,
		)

		if self.doctype not in ("Mitglied", "User", "Has Role"):
			return

		zustand = inspect(self._obj)
		payload = {
			c.name: getattr(self._obj, c.name)
			for c in self._obj.__table__.columns
			if zustand.attrs[c.name].history.has_changes()
		}
		# N12b: die BESTEHENDE Kennung kommt aus der Identitaetsmap, nicht aus
		# dem Attribut — wurde `name` selbst verbogen, liefert `self.name`
		# schon den NEUEN Wert und die Bestandspruefung fände die Zeile nicht
		# mehr (der stille Weg, den P5 schliesst).
		name = str(zustand.identity[0]) if zustand.identity else None
		if self.doctype == "Mitglied":
			# SEC-c: die E-Mail wird auch hier normalisiert und geprueft — der
			# `Document`-Weg (`doc.feld = ...; doc.save()`, `doc.db_set`) ist
			# derselbe generische Schreibweg wie `/api/resource`.
			if "email" in payload:
				payload = _normalisiere_mitglied_email(payload, name)
				for feld, wert in payload.items():
					if getattr(self._obj, feld) is not wert:
						object.__setattr__(self._obj, feld, wert)
				payload = {k: v for k, v in payload.items() if k in ("email",)}
			_pruefe_mitglied_schreibzugriff(payload, name)
			return
		# N12b (W1/P5): `doc.parent = ...; doc.save()` ist derselbe generische
		# Weg wie `/api/resource` — der Platz einer bestehenden Zeile darf sich
		# auch hier nicht aendern (sonst wandert eine Rolle still, bzw. der
		# letzte System Manager sperrt sich aus).
		from .api_helpers import _pruefe_bestand_unveraenderlich

		if name:
			_pruefe_bestand_unveraenderlich(self.doctype, name, payload)
			_pruefe_konto_schreibzugriff(self.doctype, name, payload)

	def insert(self, *args, **kwargs) -> "Document":
		# ID-1d: Die Kennung einer Person vergibt IMMER der Server. Der
		# `Document`-Weg (`frappe.get_doc({...}).insert()`) ist derselbe
		# generische Schreibweg wie `/api/resource` und `frappe.client.insert`
		# — ein vom Client gesetzter `name` („Max Muster“) wird hier ebenso
		# verworfen. Ein BESTEHENDES Dokument (`get_doc`) behaelt seine
		# Kennung; sie steht dann schon in der Identitaetsmap.
		from .api_helpers import _ist_personen_kennung, _new_name

		zustand = inspect(self._obj)
		if _ist_personen_kennung(self.doctype) and zustand.identity is None:
			object.__setattr__(self._obj, "name", _new_name())
		self._coerce_typen()
		self._pruefe_mitglied()
		from diakronos_app.db import SessionLocal

		sess = self._session or SessionLocal()
		sess.add(self._obj)
		self._abschluss(sess)
		sess.refresh(self._obj)
		self._session = sess
		return self

	def _abschluss(self, sess) -> None:
		"""Schreibung festmachen — Fehler als fachliche Meldung, nie als SQL.

		SEC-c (W1): `str(exc)` ging hier roh an den Client (auf PG inklusive
		`DETAIL: Key (…)=(anna@x.org) already exists`). `_db_fehler` uebersetzt
		auch die Index-Dublette in Klartext.
		"""
		from .exceptions import FrappeCompatError
		from .api_helpers import _db_fehler

		try:
			sess.commit()
		except FrappeCompatError:
			sess.rollback()
			raise
		except Exception as exc:  # noqa: BLE001 — fachlicher Fehler zurueckgeben
			sess.rollback()
			raise _db_fehler(exc, self.doctype) from exc

	def save(self, *args, **kwargs) -> "Document":
		self._coerce_typen()
		return self.insert()

	def db_set(self, fieldname: str, value: Any, *args, **kwargs) -> None:
		self.set(fieldname, value)
		self._coerce_typen()
		self._pruefe_mitglied()
		from diakronos_app.db import SessionLocal

		sess = self._session or SessionLocal()
		if self._obj not in sess:
			sess.add(self._obj)
		self._abschluss(sess)

	def get_doc(self, doctype: str, name: str) -> "Document":
		from .query import get_doc

		return get_doc(doctype, name)

	def __repr__(self) -> str:  # pragma: no cover
		return f"<Document {self.doctype} {self.name!r}>"


def new_doc(doctype: str, **kwargs) -> Document:
	"""Leeres Dokument anlegen (nicht persistiert)."""
	from .registry_gen import model_for

	model = model_for(doctype)
	obj = model(**kwargs)
	return Document(obj)


__all__ = ["Document", "new_doc", "DoesNotExistError"]
