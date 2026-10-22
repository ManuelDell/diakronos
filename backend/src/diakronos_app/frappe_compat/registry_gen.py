"""DocType-Name -> SQLAlchemy-Modell.

Nutzt das generierte Mapping `models/_mapping.json` als einzige Wahrheit:
`{"Mitglied": {"class": "Mitglied", "table": "mitglied", "istable": false}}`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from diakronos_app.models import __all__ as _MODEL_EXPORTS

_MAPPING_PATH = Path(__file__).resolve().parent.parent / "models" / "_mapping.json"


@lru_cache(maxsize=1)
def _mapping() -> dict[str, dict[str, Any]]:
	if not _MAPPING_PATH.is_file():  # pragma: no cover — Build-Fehler, kein Laufzeitpfad
		raise RuntimeError(f"Mapping fehlt: {_MAPPING_PATH}")
	return json.loads(_MAPPING_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _classes() -> dict[str, type]:
	import diakronos_app.models as models

	return {name: getattr(models, name) for name in _MODEL_EXPORTS}


def all_doctypes() -> list[str]:
	return sorted(_mapping())


def is_known(doctype: str) -> bool:
	return doctype in _mapping()


def is_child_table(doctype: str) -> bool:
	entry = _mapping().get(doctype)
	return bool(entry and entry.get("istable"))


def table_name(doctype: str) -> str:
	entry = _mapping().get(doctype)
	if entry is None:
		raise KeyError(doctype)
	return entry["table"]


def model_for(doctype: str) -> type:
	"""Modellklasse fuer einen DocType-Namen. `KeyError` bei unbekanntem DocType."""
	entry = _mapping().get(doctype)
	if entry is None:
		raise KeyError(doctype)
	cls = _classes().get(entry["class"])
	if cls is None:  # pragma: no cover — Mapping/Modell-Export auseinandergelaufen
		raise KeyError(f"Modellklasse {entry['class']!r} fuer {doctype!r} nicht exportiert")
	return cls


def column_names(doctype: str) -> set[str]:
	return {c.name for c in model_for(doctype).__table__.columns}


@lru_cache(maxsize=1)
def _doctype_zu_klasse() -> dict[str, str]:
	"""Modellklassen-Name -> DocType-Name (Umkehrung des Mappings)."""
	return {
		str(eintrag["class"]): name
		for name, eintrag in _mapping().items()
	}


def doctype_fuer_klasse(klassenname: str) -> str | None:
	"""DocType-Name zu einem Modellklassen-Namen, sonst `None`.

	N12b: `Document.doctype` liefert bisher den KLASSEN-Namen (`HasRole`), weil
	`frappe_compat/doc.py` auf `type(obj).__name__` zurueckfaellt. Fuer
	Pruefungen gegen die Verwaltungs-DocTypes (`Has Role`, nicht `HasRole`) und
	fuer den `parenttype`-Vergleich braucht es den echten DocType-Namen.
	"""
	return _doctype_zu_klasse().get(klassenname)


@lru_cache(maxsize=1)
def _kindtabelle_zu_eltern() -> dict[str, str]:
	"""Kind-DocType -> Eltern-DocType, abgeleitet aus den SQLAlchemy-Modellen.

	Die Kind-Tabellen tragen im Modell einen Fremdschluessel auf `parent` des
	Eltern-DocTypes (z. B. `AnmeldeformularFeld.parent` ist KEIN `ForeignKey`,
	aber `ElementRessource.parent` verweist auf `element`) — eine generische
	Ableitung waere deshalb unzuverlaessig. Verlaesslich ist etwas anderes:
	Frappe bildet den `parenttype` als DocType-Namen des Elternteils, und die
	Kind-Tabellen tragen in der Regel dessen Namen als Praefix
	(„Anmeldeformular Feld“ -> „Anmeldeformular“). Diese Ableitung ist ein
	FALLBACK fuer `_parenttype_for` — die gepflegte Zuordnung dort hat Vorrang.
	"""
	ergebnis: dict[str, str] = {}
	alle = _mapping()
	for name, eintrag in alle.items():
		if not eintrag.get("istable"):
			continue
		teile = name.split(" ")
		for schnitt in range(len(teile) - 1, 0, -1):
			kandidat = " ".join(teile[:schnitt])
			if kandidat in alle and not alle[kandidat].get("istable"):
				ergebnis[name] = kandidat
				break
	return ergebnis


def child_doctype_parent(child_doctype: str) -> str | None:
	"""Eltern-DocType einer Kind-Tabelle, sonst `None`."""
	return _kindtabelle_zu_eltern().get(child_doctype)
