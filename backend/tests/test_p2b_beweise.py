"""P2b-Beweise: die drei in P2a unbelegten Compat-Primitive.

Kartentext Punkt 3:
  - db.sql: parametrisierte Abfrage + Injection als PARAMETERWERT
  - or_filters: ODER-verknuepfte Bedingungen
  - idx-Sortierung: Child-Tabelle in verdrehter Einfuegereihenfolge

Alle Tests laufen auf In-Memory-SQLite (siehe conftest).
"""

from __future__ import annotations

import pytest

# ── db.sql ───────────────────────────────────────────────────────────────────


def test_db_sql_parametrisierte_abfrage(patched_db, seed_mitglieder):
	"""Eine parametrisierte Abfrage liefert korrekt gefilterte Zeilen."""
	from diakronos_app.frappe_compat import db

	rows = db.sql(
		"SELECT name, vorname FROM mitglied WHERE status = %(status)s ORDER BY name",
		{"status": "Mitglied"},
		as_dict=True,
	)
	assert [r["name"] for r in rows] == ["M-0001", "M-0002"]
	assert rows[0]["vorname"] == "Anna"


def test_db_sql_like_muster_mit_prozent(patched_db, seed_mitglieder):
	"""`%` im LIKE-Muster darf nicht als Platzhalter fehlinterpretiert werden.

	Regression: unescapte `%` in Text fuehrten unter psycopg zu einem
	SyntaxError, weil `text()` sie als Bindeparameter liest.
	"""
	from diakronos_app.frappe_compat import db

	rows = db.sql(
		"SELECT name FROM mitglied WHERE nachname LIKE %(muster)s ORDER BY name",
		{"muster": "Beisp%"},
		as_dict=True,
	)
	assert [r["name"] for r in rows] == ["M-0001"]


def test_db_sql_injection_als_paramwert_bleibt_literal(patched_db, seed_mitglieder):
	"""Injection-Versuch als PARAMETERWERT wird als Literal behandelt.

	Beweist beides: Tabelle existiert danach noch, und der Wert wird nicht
	als SQL ausgefuehrt (er trifft kein Mitglied).
	"""
	from diakronos_app.frappe_compat import db

	boese = "x'; DROP TABLE mitglied; --"

	rows = db.sql(
		"SELECT name FROM mitglied WHERE vorname = %(wert)s",
		{"wert": boese},
		as_dict=True,
	)
	assert rows == []

	# Tabelle lebt und ist unveraendert
	alle = db.sql("SELECT name FROM mitglied ORDER BY name", as_dict=True)
	assert [r["name"] for r in alle] == ["M-0001", "M-0002", "M-0003"]


# ── or_filters ───────────────────────────────────────────────────────────────


def test_get_all_or_filters(patched_db, seed_mitglieder):
	"""Zwei ODER-verknuepfte Bedingungen: Vereinigung, nicht Schnittmenge."""
	from diakronos_app.frappe_compat import get_all

	rows = get_all(
		"Mitglied",
		or_filters=[["vorname", "=", "Anna"], ["vorname", "=", "Clara"]],
		fields=["name"],
		order_by="name asc",
	)
	assert [r["name"] for r in rows] == ["M-0001", "M-0003"]


def test_get_all_or_filters_unterscheidet_sich_von_and(patched_db, seed_mitglieder):
	"""Gegenprobe: dieselben zwei Bedingungen als AND liefern nichts."""
	from diakronos_app.frappe_compat import get_all

	rows = get_all(
		"Mitglied",
		filters=[["vorname", "=", "Anna"], ["vorname", "=", "Clara"]],
		fields=["name"],
	)
	assert rows == []


def test_get_all_or_filters_mit_treffer_auf_eine_bedingung(patched_db, seed_mitglieder):
	"""Eine Bedingung trifft, eine nicht -> nur die Treffermenge kommt zurueck."""
	from diakronos_app.frappe_compat import get_all

	rows = get_all(
		"Mitglied",
		or_filters=[["vorname", "=", "Bruno"], ["vorname", "=", "GibtEsNicht"]],
		fields=["name"],
	)
	assert [r["name"] for r in rows] == ["M-0002"]


# ── idx-Sortierung der Child-Tabelle ─────────────────────────────────────────


@pytest.fixture()
def verdrehte_bereiche(patched_db):
	"""Child-Zeilen absichtlich in verdrehter idx-Reihenfolge einfuegen."""
	from diakronos_app.models.diakonos import MitgliedBereich

	sess = patched_db()
	# Einfuegereihenfolge: idx 2, dann 0, dann 1 — Ergebnis muss nach idx kommen.
	rows = [
		MitgliedBereich(name="B-IDX2", parent="M-0001", idx=2),
		MitgliedBereich(name="B-IDX0", parent="M-0001", idx=0),
		MitgliedBereich(name="B-IDX1", parent="M-0001", idx=1),
	]
	sess.add_all(rows)
	sess.commit()
	yield sess
	sess.close()


def test_child_tabelle_wird_nach_idx_sortiert(patched_db, seed_mitglieder, verdrehte_bereiche):
	"""Ohne explizites order_by kommt die Child-Tabelle nach `idx` zurueck."""
	from diakronos_app.frappe_compat import get_all

	rows = get_all("Mitglied Bereich", filters={"parent": "M-0001"}, fields=["name", "idx"])
	assert [r["name"] for r in rows] == ["B-IDX0", "B-IDX1", "B-IDX2"]
	assert [r["idx"] for r in rows] == [0, 1, 2]
