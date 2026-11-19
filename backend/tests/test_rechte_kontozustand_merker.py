"""Rechte-Kern: der Kontozustand (Mitglied + User) wird je Aufruf EINMAL gelesen.

Operator 19.11.2026. ``_kontozustand`` steht hinter jeder Rechtefrage
(``get_roles`` -> ``mitglied_ausgeschlossen``). Der Merker darf keine
Entscheidung veraendern: ein im selben Aufruf gesetzter Ausschluss muss sofort
wirken — geflusht, ungeflusht oder in einer anderen Sitzung committet.
"""

from __future__ import annotations

import pytest

from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

ANNA = "anna@x.org"


@pytest.fixture()
def welt(patched_db):
	s = patched_db()
	s.add(User(name=ANNA, email=ANNA, enabled=1))
	s.add(Mitglied(name="M-Anna", vorname="Anna", nachname="A", email=ANNA, user=ANNA))
	s.commit()
	yield patched_db
	s.close()


def _zaehler(monkeypatch):
	from diakronos_app.frappe_compat import benutzer_status as B

	echt = B._kontozustand_lesen
	z = {"n": 0}

	def zaehlend():
		z["n"] += 1
		return echt()

	monkeypatch.setattr(B, "_kontozustand_lesen", zaehlend)
	return z


def test_ohne_rahmen_wird_jedes_mal_gelesen(welt, monkeypatch):
	from diakronos_app.frappe_compat import benutzer_status as B

	z = _zaehler(monkeypatch)
	B._kontozustand()
	B._kontozustand()
	assert z["n"] == 2


def test_im_rahmen_einmal_gelesen(welt, monkeypatch):
	from diakronos_app.frappe_compat import benutzer_status as B
	from diakronos_app.rechte.kern import merkungsrahmen

	z = _zaehler(monkeypatch)
	with merkungsrahmen():
		for _ in range(5):
			assert not B._mitglied_ausgeschlossen(ANNA)
	assert z["n"] == 1


def test_kopien_schuetzen_den_merker(welt):
	from diakronos_app.frappe_compat import benutzer_status as B
	from diakronos_app.rechte.kern import merkungsrahmen

	with merkungsrahmen():
		mitglieder, konten = B._kontozustand()
		mitglieder[0]["ausgeschlossen"] = 1
		konten.clear()
		m2, k2 = B._kontozustand()
	assert not any(m.get("ausgeschlossen") for m in m2)
	assert any(k["name"] == ANNA for k in k2)


def test_ausschluss_in_anderer_sitzung_wirkt_sofort(welt):
	from diakronos_app.frappe_compat import benutzer_status as B
	from diakronos_app.rechte.kern import merkungsrahmen

	with merkungsrahmen():
		assert not B._mitglied_ausgeschlossen(ANNA)
		s = welt()
		s.query(Mitglied).filter_by(name="M-Anna").update({"ausgeschlossen": 1})
		s.commit()
		s.close()
		assert B._mitglied_ausgeschlossen(ANNA)


def test_bei_ungeflushten_aenderungen_wird_nicht_gemerkt(welt, monkeypatch):
	"""Traegt die Aufrufsitzung ungeflushte Aenderungen, liest jede Frage neu.

	(``SessionLocal`` hat ``autoflush=False``: Ungeflushtes sieht keine Abfrage
	— das ist das Verhalten OHNE Merker und bleibt es. Der Merker darf hier nur
	nichts anderes liefern als der ungemerkte Weg.)
	"""
	from diakronos_app import db as dbmod
	from diakronos_app.frappe_compat import benutzer_status as B
	from diakronos_app.rechte.kern import merkungsrahmen

	z = _zaehler(monkeypatch)
	with merkungsrahmen():
		s = welt()
		with dbmod.als_aktuelle_sitzung(s):
			B._kontozustand()
			s.get(Mitglied, "M-Anna").vorname = "Anne"      # ungeflusht
			assert s.dirty
			B._kontozustand()
			B._kontozustand()
		s.rollback()
		s.close()
	assert z["n"] == 3


def test_geflushter_ausschluss_wirkt_sofort(welt):
	from diakronos_app import db as dbmod
	from diakronos_app.frappe_compat import benutzer_status as B
	from diakronos_app.rechte.kern import merkungsrahmen

	with merkungsrahmen():
		s = welt()
		with dbmod.als_aktuelle_sitzung(s):
			assert not B._mitglied_ausgeschlossen(ANNA)
			s.get(Mitglied, "M-Anna").ausgeschlossen = 1
			s.flush()
			assert not s.dirty
			assert B._mitglied_ausgeschlossen(ANNA)
		s.rollback()
		s.close()
