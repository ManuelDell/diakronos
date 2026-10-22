"""LI1b — Testisolation der Testdatenbank (Beleg für die Karten-Reparatur).

Der Teststack läuft auf In-Memory-SQLite mit ``StaticPool``: EINE Verbindung
für alle Sitzungen. Öffnete ein Lese-Helfer (``frappe_compat.db.count``, gerufen
aus ``psalmos.musik._is_musikverantwortlicher``) oder ein Schreib-Helfer
während eines laufenden Endpunkts eine ZWEITE Sitzung auf dieser Verbindung,
riss deren ``close()``/``commit()`` die noch offene Transaktion der
Aufrufer-Sitzung mit: geflushte, nicht committete Schreibungen verschwanden
still. Auf PostgreSQL (eine Verbindung je Sitzung) tritt das nicht auf.

Die Reparatur: ``diakronos_app.db.sitzung_fuer_lesen()`` liefert im
Request-Rahmen (``db.als_aktuelle_sitzung``, gesetzt von ``planrahmen._endpunkt``)
die vorhandene Sitzung, sonst eine neue. Die Helfer benutzen sie mit und
schließen keine geliehene Sitzung.

Beleg: StaticPool ohne diese Naht → Zeile weg.
"""

from __future__ import annotations

from diakronos_app.models.psalmos import Lied


def test_geliehene_sitzung_darf_nicht_geschlossen_werden(patched_db):
	"""``db.count`` im Request-Rahmen benutzt die vorhandene Sitzung —
	ihr close() würde sonst die offene Transaktion des Aufrufers mitreißen."""
	from diakronos_app import db as dbmod
	from diakronos_app.frappe_compat import db as compat_db

	aufrufer = patched_db()
	try:
		aufrufer.add(Lied(name="ISO-1", titel="Isolation", aktiv=True))
		aufrufer.flush()

		with dbmod.als_aktuelle_sitzung(aufrufer):
			# Die zweite, kurzlebige Lesesitzung — dieselbe Form wie db.count.
			anzahl = compat_db.count("Lied")
			assert anzahl == 1, "im Request-Rahmen zählt db.count die offene Zeile mit"
			# Nach der Lesehilfe ist die Aufrufer-Sitzung weiter offen und benutzbar.
			assert aufrufer.is_active, "die geliehene Sitzung darf nicht geschlossen werden"

		aufrufer.commit()
	finally:
		aufrufer.close()

	pruefer = patched_db()
	try:
		assert pruefer.get(Lied, "ISO-1") is not None, (
			"die Schreibung der Aufrufer-Sitzung darf durch die Lesehilfe "
			"nicht verworfen werden")
	finally:
		pruefer.close()


def test_ohne_rahmen_oeffnet_lesehilfe_eigene_sitzung(patched_db):
	"""Ohne Request-Rahmen bleibt ``db.count`` autark (eigene Sitzung)."""
	from diakronos_app.frappe_compat import db as compat_db

	s = patched_db()
	try:
		s.add(Lied(name="ISO-2", titel="Autark", aktiv=True))
		s.commit()
	finally:
		s.close()

	assert compat_db.count("Lied") == 1
