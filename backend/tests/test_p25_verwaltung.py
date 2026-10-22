"""P2-5 — Regressionstests fuer das Reparaturpaket (Einrichtung/Verwaltung).

Jeder Test nennt den Nachtbefund, den er absichert. Die Identitaet kommt aus
der `set_user`-Naht, die ROLLEN sind echte `Has Role`-Zeilen (wie im Betrieb)
— nicht gepatcht. Nur so prueft der Test denselben Weg, den die Anwendung
geht (`get_roles` liest die Tabelle).

Die Befunde:

    OP-ADMIN-10  Kalender anlegen/aendern/loeschen, Rechte, Moderatoren
    OP-ADMIN-11  Ressourcen anlegen/aendern/loeschen, Wartung
    OP-ADMIN-19  parenttype der Anmeldeformular-Kindzeilen
    UXD-R18      Zaehler offener Anmeldungen (nie vorkommender Status)
    OP-ADMIN-12  keine Impersonation im Backend (Gegenprobe zum Knopf)
"""

from __future__ import annotations

from datetime import datetime

import pytest

# Identitaet des Aufrufers setzen — dieselbe Naht wie in den Nachbartests
# (`session.set_user`). Bewusst als Import und nicht als Fixture: mehrere
# Tests stellen die Identitaet MITTEN im Ablauf um.
from diakronos_app.frappe_compat.session import set_user


# ── Gemeinsame Fixtures ─────────────────────────────────────────────────────


def _nutzer(sess, name, rollen=()):
	"""Einen Benutzer mit echten `Has Role`-Zeilen anlegen.

	Der Code liest Rollen aus der Tabelle (`get_roles`), nicht aus einem
	gepatchten Wert — die Zeilen sind deshalb die einzige ehrliche Quelle.
	"""
	from diakronos_app.models.core import HasRole, User

	if sess.get(User, name) is None:
		sess.add(User(name=name, email=name, full_name=name, enabled=True,
		              password_hash="x"))
	for i, rolle in enumerate(rollen, start=1):
		sess.add(HasRole(name=f"{name}-{i}", parent=name, parenttype="User",
		                 parentfield="roles", role=rolle, docstatus=0, idx=i))
	sess.flush()


@pytest.fixture()
def db(patched_db):
	"""Kurzform: eine Sitzung auf der Wegwerf-Datenbank."""
	sess = patched_db()
	yield sess
	sess.close()


@pytest.fixture()
def kalender_admin(db):
	"""Ein Kalenderadministrator (OP-ADMIN-10)."""
	_nutzer(db, "kalenderadmin@test.local", ["Administrator", "Kalenderadministrator"])
	db.commit()
	set_user("kalenderadmin@test.local")
	return "kalenderadmin@test.local"


@pytest.fixture()
def ressourcen_moderator(db):
	"""Ein Ressourcenmoderator (OP-ADMIN-11)."""
	_nutzer(db, "ressourcen@test.local", ["Ressourcenmoderator"])
	db.commit()
	set_user("ressourcen@test.local")
	return "ressourcen@test.local"


@pytest.fixture()
def mitglieder_admin(db):
	"""Ein Mitgliederadministrator (OP-ADMIN-19, admin_hub)."""
	_nutzer(db, "verwaltung@test.local", ["Mitgliederadministrator"])
	db.commit()
	set_user("verwaltung@test.local")
	return "verwaltung@test.local"


# ── OP-ADMIN-10: Kalenderverwaltung ─────────────────────────────────────────


def test_op_admin_10_kalender_anlegen_mit_rechten(db, kalender_admin):
	"""Ein Kalender entsteht mit Farbe, Rechten und Moderatoren.

	Vorher gab es diesen Weg nicht (nur iCal-Import); dieser Test haelt fest,
	dass die Rechte als KIND-ZEILEN landen — genau die Form, die
	`get_accessible_calendars` spaeter auswertet.
	"""
	from diakronos_app.api.kronos import kalender_verwaltung

	ergebnis = kalender_verwaltung.create_kalender(
		titel="Jugend",
		farbe="#ff8800",
		leserechte=["All"],
		schreibrechte=["Mitglied"],
		moderatoren=[],
	)
	assert ergebnis["success"] is True
	assert ergebnis["name"] == "Jugend"

	from diakronos_app.models.core import UserRole
	from diakronos_app.models.kronos import Kalender

	db.expire_all()
	doc = db.get(Kalender, "Jugend")
	assert doc is not None
	assert doc.calendar_name == "Jugend"
	assert doc.calendar_color == "#ff8800"

	zeilen = db.query(UserRole).filter(UserRole.parent == "Jugend").all()
	lesen = {(z.role, z.parentfield) for z in zeilen}
	assert ("All", "leserechte") in lesen
	assert ("Mitglied", "schreibrechte") in lesen


def test_op_admin_10_doppelter_name_wird_abgelehnt(db, kalender_admin):
	"""Zwei Kalender mit demselben Anzeigenamen waeren nicht unterscheidbar."""
	from diakronos_app.api.kronos import kalender_verwaltung

	kalender_verwaltung.create_kalender(titel="Gemeinde")

	with pytest.raises(Exception):
		kalender_verwaltung.create_kalender(titel="Gemeinde")


def test_op_admin_10_rechte_sind_aenderbar(db, kalender_admin):
	"""Moderatoren und Schreibrechte lassen sich nachtragen (Kern des Befunds)."""
	from diakronos_app.api.kronos import kalender_verwaltung

	kalender_verwaltung.create_kalender(titel="Chor")
	kalender_verwaltung.update_kalender(
		"Chor",
		titel="Chor & Band",
		schreibrechte=["Mitglied"],
		moderatoren=[],
	)

	verwaltung = kalender_verwaltung.get_kalender_verwaltung()
	eintrag = next(k for k in verwaltung["kalender"] if k["name"] == "Chor")
	assert eintrag["titel"] == "Chor & Band"
	assert eintrag["schreibrechte"] == ["Mitglied"]


def test_op_admin_10_loeschen_ohne_termine_und_mit_rueckfrage(db, kalender_admin):
	"""Loeschen verlangt die Bestaetigung und geht nur ohne Termine."""
	from diakronos_app.api.kronos import kalender_verwaltung

	kalender_verwaltung.create_kalender(titel="Leer")

	# Ohne Bestaetigung: abgelehnt.
	with pytest.raises(Exception):
		kalender_verwaltung.delete_kalender("Leer")

	# Mit Bestaetigung: weg.
	assert kalender_verwaltung.delete_kalender("Leer", bestaetigt=1)["success"] is True

	verwaltung = kalender_verwaltung.get_kalender_verwaltung()
	assert all(k["name"] != "Leer" for k in verwaltung["kalender"])


def test_op_admin_10_loeschen_verweigert_bei_termine(db, kalender_admin):
	"""Ein Kalender mit Terminen bleibt stehen (keine verwaisten Termine)."""
	from diakronos_app.api.kronos import kalender_verwaltung
	from diakronos_app.models.kronos import Element

	kalender_verwaltung.create_kalender(titel="Voll")

	db.add(Element(
		name="EL-VOLL-1",
		element_name="Gottesdienst",
		element_calendar="Voll",
		element_start=datetime(2026, 11, 1, 10, 0),
		element_end=datetime(2026, 11, 1, 11, 0),
		status="Festgelegt",
		docstatus=0,
	))
	db.commit()

	with pytest.raises(Exception) as fehler:
		kalender_verwaltung.delete_kalender("Voll", bestaetigt=1)
	assert "Termine" in str(fehler.value)


def test_n12b_registrierungslink_ist_kein_kalenderverweis(db, kalender_admin):
	"""N12b (R-N12, klein): ein Registrierungslink zaehlt nicht als Verweis.

	Der Link zeigt auf einen TERMIN (`Registrierungslink.element`), nicht auf
	einen Kalender — ein eigener Verweiszweig waere toter Code. Festgehalten
	wird beides: (a) ein Link allein blockiert das Loeschen NICHT, (b) sobald
	sein Termin in dem Kalender liegt, blockiert der TERMIN (wie bisher).
	"""
	from diakronos_app.api.kronos import kalender_verwaltung
	from diakronos_app.models.diakonos import Registrierungslink
	from diakronos_app.models.kronos import Element

	kalender_verwaltung.create_kalender(titel="Mit-Link")

	# (a) Ein Link ohne Termin in diesem Kalender ist kein Verweis.
	db.add(Registrierungslink(
		name="RL-N12B", bezeichnung="Link", typ="Mitglied-Registrierung",
		aktiv=True, docstatus=0, idx=0, anmeldungen_count=0,
	))
	db.commit()
	assert kalender_verwaltung.delete_kalender("Mit-Link", bestaetigt=1)["success"] is True

	# (b) Derselbe Link an einem Termin: jetzt zaehlt der TERMIN.
	kalender_verwaltung.create_kalender(titel="Mit-Link-2")
	db.add(Element(
		name="EL-LINK-1", element_name="Gottesdienst", element_calendar="Mit-Link-2",
		element_start=datetime(2026, 12, 1, 10, 0),
		element_end=datetime(2026, 12, 1, 11, 0),
		status="Festgelegt", docstatus=0,
	))
	db.add(Registrierungslink(
		name="RL-N12B-2", bezeichnung="Link", typ="Mitglied-Registrierung",
		aktiv=True, docstatus=0, idx=0, anmeldungen_count=0, element="EL-LINK-1",
	))
	db.commit()
	with pytest.raises(Exception) as fehler:
		kalender_verwaltung.delete_kalender("Mit-Link-2", bestaetigt=1)
	assert "Termine" in str(fehler.value)


def test_op_admin_10_nur_kalenderadministrator(db):
	"""Ohne die Rolle verweigert der Server — fail closed."""
	from diakronos_app.api.kronos import kalender_verwaltung

	_nutzer(db, "mitglied@test.local", ["Mitglied"])
	db.commit()
	set_user("mitglied@test.local")

	with pytest.raises(Exception):
		kalender_verwaltung.get_kalender_verwaltung()
	with pytest.raises(Exception):
		kalender_verwaltung.create_kalender(titel="Heimlich")


# ── OP-ADMIN-11: Ressourcenverwaltung ───────────────────────────────────────


def test_op_admin_11_ressource_anlegen_aendern_loeschen(db, ressourcen_moderator):
	"""Ein Raum entsteht, laesst sich umbenennen, in Wartung setzen und loeschen."""
	from diakronos_app.api import ressourcen

	assert ressourcen.create_ressource(name="Gemeindesaal", typ="Raum",
	                                   kapazitaet=80)["success"]

	# Aendern: Name, Wartung.
	ressourcen.update_ressource("Gemeindesaal", name="Gemeindesaal groß", wartung=1)

	liste = ressourcen.get_ressourcen_verwaltung()["ressourcen"]
	eintrag = next(r for r in liste if r["id"] == "Gemeindesaal")
	assert eintrag["name"] == "Gemeindesaal groß"
	assert eintrag["wartung"] == 1

	# Loeschen ohne Bestaetigung: abgelehnt.
	with pytest.raises(Exception):
		ressourcen.delete_ressource("Gemeindesaal")

	assert ressourcen.delete_ressource("Gemeindesaal", bestaetigt=1)["success"] is True
	assert all(r["id"] != "Gemeindesaal"
	           for r in ressourcen.get_ressourcen_verwaltung()["ressourcen"])


def test_op_admin_11_art_wird_geprueft(db, ressourcen_moderator):
	"""Nur die drei bekannten Arten sind zulaessig."""
	from diakronos_app.api import ressourcen

	with pytest.raises(Exception):
		ressourcen.create_ressource(name="Ufo", typ="Raumfahrzeug")


def test_op_admin_11_kapazitaet_muss_zahl_sein(db, ressourcen_moderator):
	from diakronos_app.api import ressourcen

	with pytest.raises(Exception):
		ressourcen.create_ressource(name="Saal", typ="Raum", kapazitaet="viele")


def test_op_admin_11_loeschen_verweigert_bei_buchung(db, ressourcen_moderator):
	"""Eine Ressource mit Buchung bleibt stehen."""
	from diakronos_app.api import ressourcen
	from diakronos_app.models.diakonos import RessourcenBuchung

	ressourcen.create_ressource(name="Bus", typ="Fahrzeug")

	db.add(RessourcenBuchung(
		name="BUCH-1",
		ressource="Bus",
		zweck="Freizeit",
		datum_von=datetime(2026, 11, 1, 8, 0),
		datum_bis=datetime(2026, 11, 1, 18, 0),
		status="Bestätigt",
	))
	db.commit()

	with pytest.raises(Exception) as fehler:
		ressourcen.delete_ressource("Bus", bestaetigt=1)
	assert "Buchungen" in str(fehler.value)


# ── OP-ADMIN-19: parenttype der Anmeldeformular-Kindzeilen ──────────────────


def test_op_admin_19_parenttype_ist_der_eltern_doctype(db, mitglieder_admin):
	"""`_parenttype_for` nennt das ELTERNTEIL, nicht die Kind-Tabelle.

	Vorher stand in `parenttype` der Name der Kind-Tabelle — die Zeile war
	damit fuer jede Kind-Tabellen-Abfrage unsichtbar (genau der Grund, warum
	„Felder“ immer leer blieb). Dieser Test haelt die Zuordnung fest.
	"""
	from diakronos_app.frappe_compat.api_helpers import _parenttype_for

	assert _parenttype_for("Anmeldeformular Feld") == "Anmeldeformular"
	assert _parenttype_for("Anmeldeformular Dokument") == "Anmeldeformular"
	# Die Altzuordnungen bleiben unveraendert.
	assert _parenttype_for("Element Ressource") == "Element"
	assert _parenttype_for("User Role") == "Kalender"


def test_op_admin_19_formular_felder_werden_gezaehlt_und_gelesen(db, mitglieder_admin):
	"""Anlegen -> Felder setzen -> Liste zaehlt -> Felder kommen zurueck.

	Das ist der Durchlauf, der vorher nicht moeglich war: die Zaehlung las
	Kind-Zeilen, die wegen des falschen `parenttype` unsichtbar waren.
	"""
	import json

	from diakronos_app.api import admin_hub

	angelegt = admin_hub.create_anmeldeformular(
		bezeichnung="Freizeit", mit_gaesten=1, mit_kinder=0
	)
	fid = angelegt["id"]

	admin_hub.update_anmeldeformular_felder(
		fid,
		json.dumps([
			{"label": "T-Shirt-Größe", "feldtyp": "Text", "pflichtfeld": 1},
			{"label": "Allergien", "feldtyp": "Text", "pflichtfeld": 0},
		]),
	)

	liste = admin_hub.get_anmeldeformulare()["formulare"]
	eintrag = next(f for f in liste if f["name"] == fid)
	assert eintrag["felder_anzahl"] == 2, "Die Spalte „Felder“ darf nicht mehr leer sein"

	details = admin_hub.get_anmeldeformular_felder(fid)
	assert [f["label"] for f in details["felder"]] == ["T-Shirt-Größe", "Allergien"]

	# Aendern: Bezeichnung und Felder in einem Aufruf.
	admin_hub.update_anmeldeformular(
		fid, bezeichnung="Freizeit 2027",
		felder_json=json.dumps([{"label": "Nur eins", "feldtyp": "Text"}]),
	)
	details = admin_hub.get_anmeldeformular_felder(fid)
	assert details["bezeichnung"] == "Freizeit 2027"
	assert len(details["felder"]) == 1


def test_op_admin_19_formular_loeschen_mit_rueckfrage(db, mitglieder_admin):
	from diakronos_app.api import admin_hub

	fid = admin_hub.create_anmeldeformular(bezeichnung="Wegwerf")["id"]

	with pytest.raises(Exception):
		admin_hub.delete_anmeldeformular(fid)

	assert admin_hub.delete_anmeldeformular(fid, bestaetigt=1)["success"] is True
	assert all(f["name"] != fid for f in admin_hub.get_anmeldeformulare()["formulare"])


# ── UXD-R18: Zaehler offener Anmeldungen ────────────────────────────────────


def test_uxd_r18_zaehler_kennt_anmeldeanfrage(db):
	"""Der Zaehler zaehlt „Anmeldeanfrage“, nicht nur „Ausstehend“.

	Der alte Wert „Ausstehend“ kommt fuer Anmeldungen nie vor — der Zaehler
	war deshalb dauerhaft 0, obwohl Anfragen offen lagen.
	"""
	from diakronos_app.api import dashboard
	from diakronos_app.models.diakonos import Anmeldung

	db.add_all([
		Anmeldung(name="A-1", status="Anmeldeanfrage"),
		Anmeldung(name="A-2", status="Anmeldeanfrage"),
		Anmeldung(name="A-3", status="Bestätigt"),
	])
	db.commit()

	_nutzer(db, "verwaltung@test.local", ["Mitgliederadministrator"])
	db.commit()
	set_user("verwaltung@test.local")

	zaehler = dashboard.get_navigation_zaehler()
	assert zaehler["anfragen"] == 2

	badges = dashboard.get_widget_badge_counts()
	assert badges["manage-registrations"] == 2, "Widget und Seitenleiste muessen dasselbe zaehlen"


def test_uxd_r18_zaehler_fehlt_ohne_rolle(db):
	"""Ohne Rolle kommt die Zahl GAR NICHT (nicht als 0 getarnt)."""
	from diakronos_app.api import dashboard

	_nutzer(db, "mitglied@test.local", ["Mitglied"])
	db.commit()
	set_user("mitglied@test.local")
	assert dashboard.get_navigation_zaehler() == {}


# ── OP-ADMIN-12: kein Knopf ohne Funktion (Frontend-Vertrag) ────────────────


def test_op_admin_12_kein_impersonations_endpunkt(db):
	"""Die Gegenprobe zum entfernten Knopf: es GIBT keine Impersonation.

	Der Frontend-Test (Node) prueft, dass der Knopf weg ist. Hier steht die
	Begruendung als messbare Aussage: das Backend kennt keine effektive
	Benutzerumschaltung — `_get_effective_user` liefert immer den Aufrufer.
	"""
	import importlib

	from diakronos_app.api.kronos.permissions import _get_effective_user
	from diakronos_app.frappe_compat import session as session_mod

	# Kein Modul `impersonation` in der Anwendung.
	with pytest.raises(ModuleNotFoundError):
		importlib.import_module("diakronos_app.api.impersonation")

	# `_get_effective_user` gibt es, aber es gibt keinen Umschalter: der
	# Wert ist immer der Sitzungsbenutzer.
	_nutzer(db, "kalenderadmin@test.local", ["Kalenderadministrator"])
	db.commit()
	set_user("kalenderadmin@test.local")
	assert _get_effective_user() == "kalenderadmin@test.local"
	_ = session_mod


# ── R-P2-5 (klein 1-5): Nacharbeit Loeschen/Rechte/Auswahl ─────────────────


def test_delete_kalender_meldet_auch_stornierte_termine(db, kalender_admin):
	"""Klein 1: stornierte Termine blockieren das Loeschen — mit Klartext.

	Vorher zaehlte `delete_kalender` nur Termine mit docstatus != 2; ein
	stornierter Termin liess das Loeschen erst an der Fremdschluessel-Pruefung
	mit 417 scheitern (technischer Text statt freundlicher Meldung).
	"""
	from diakronos_app.api.kronos import kalender_verwaltung
	from diakronos_app.models.kronos import Element

	kalender_verwaltung.create_kalender(titel="MitStorno")
	db.add(Element(
		name="EL-STORNO", element_calendar="MitStorno", element_name="Alt",
		docstatus=2, idx=0,
	))
	db.commit()

	with pytest.raises(Exception) as fehler:
		kalender_verwaltung.delete_kalender("MitStorno", bestaetigt=1)
	assert "stornierte" in str(fehler.value).lower()
	# Der Kalender steht noch.
	from diakronos_app.models.kronos import Kalender

	db.expire_all()
	assert db.get(Kalender, "MitStorno") is not None


def test_delete_kalender_meldet_verweis_auf_gruppe(db, kalender_admin):
	"""Klein 1: ein Verweis (Gruppe.kalender) wird freundlich gemeldet."""
	from diakronos_app.api.kronos import kalender_verwaltung
	from diakronos_app.models.diakonos import Gruppe
	from diakronos_app.models.kronos import Kalender

	kalender_verwaltung.create_kalender(titel="Chorkalender")
	db.add(Gruppe(name="G-CHOR", gruppenname="Chor", kalender="Chorkalender",
	              docstatus=0, idx=0))
	db.commit()

	with pytest.raises(Exception) as fehler:
		kalender_verwaltung.delete_kalender("Chorkalender", bestaetigt=1)
	assert "verwendet" in str(fehler.value).lower()
	db.expire_all()
	assert db.get(Kalender, "Chorkalender") is not None


def test_delete_ressource_meldet_auch_stornierte_buchung(db, ressourcen_moderator):
	"""Klein 2: auch eine stornierte Buchung blockiert das Loeschen."""
	from diakronos_app.api import ressourcen
	from diakronos_app.models.diakonos import RessourcenBuchung

	ressourcen.create_ressource(name="Saal2", typ="Raum")
	db.add(RessourcenBuchung(
		name="BUCH-STORNO", ressource="Saal2", zweck="Alt",
		datum_von=datetime(2026, 11, 1, 8, 0),
		datum_bis=datetime(2026, 11, 1, 18, 0), status="Storniert",
	))
	db.commit()

	with pytest.raises(Exception) as fehler:
		ressourcen.delete_ressource("Saal2", bestaetigt=1)
	assert "stornierte" in str(fehler.value).lower()


def test_update_kalender_prueft_rollen_vor_dem_schreiben(db, kalender_admin):
	"""Klein 3: eine ungueltige Rolle laesst den Kalender unveraendert."""
	from diakronos_app.api.kronos import kalender_verwaltung
	from diakronos_app.models.kronos import Kalender

	kalender_verwaltung.create_kalender(titel="Unveraendert", farbe="#112233")

	with pytest.raises(Exception):
		kalender_verwaltung.update_kalender(
			"Unveraendert", titel="NeuerName", leserechte=["GibtEsNicht"],
		)

	db.expire_all()
	doc = db.get(Kalender, "Unveraendert")
	assert doc is not None, "Der Titel darf NICHT geschrieben worden sein"
	assert (doc.calendar_name or doc.name) == "Unveraendert"


def test_ressourcen_endpunkt_ohne_moderatorrolle(db):
	"""Klein 5: Ressourcen-Endpunkte ohne Moderatorrolle werden verweigert.

	Die Schranke laesst ausschliesslich `Ressourcenmoderator`,
	`Mitgliederadministrator` und `System Manager` durch
	(`_is_ressourcenmoderator`). Dieser Test prueft die Gegenprobe mit einem
	Konto OHNE jede dieser Rollen — ein Mitgliederadministrator ist bewusst
	zugelassen und taugt daher nicht als Gegenprobe.
	"""
	from diakronos_app.api import ressourcen

	_nutzer(db, "nur-mitglied@test.local", ["Mitglied"])
	db.commit()
	set_user("nur-mitglied@test.local")  # KEINE Ressourcen-Moderatorrolle
	with pytest.raises(Exception):
		ressourcen.create_ressource(name="Heimlich", typ="Raum")


def test_get_konten_liste_ohne_admin(db, ressourcen_moderator):
	"""Klein 5: `get_konten_liste` verlangt Mitgliederadministrator."""
	from diakronos_app.api import zugang

	set_user("ressourcen@test.local")
	with pytest.raises(Exception):
		zugang.get_konten_liste()


def test_moderator_auswahl_fuer_kalenderadministrator(db, kalender_admin):
	"""Klein 4: ein Kalenderadministrator darf die schmale Auswahl lesen.

	`get_konten_liste` verlangt Mitgliederadministrator; der neue,
	schmale Endpunkt liefert nur Kennung + Anzeigename.
	"""
	from diakronos_app.api import zugang

	set_user("kalenderadmin@test.local")
	daten = zugang.get_moderator_auswahl()
	assert daten["success"] is True
	assert daten["konten"], "Auswahl ist leer"
	# Keine E-Mail, keine Rollen — nur das, was die Auswahl braucht.
	assert set(daten["konten"][0].keys()) == {"user", "name", "aktiv"}


def test_moderator_auswahl_ohne_verwaltungsrolle(db):
	"""Klein 4: ein normales Mitglied bekommt die Auswahl nicht."""
	from diakronos_app.api import zugang

	_nutzer(db, "nurmitglied@test.local", ["Mitglied"])
	db.commit()
	set_user("nurmitglied@test.local")
	with pytest.raises(Exception):
		zugang.get_moderator_auswahl()


def test_delete_anmeldeformular_mit_links_verweigert(db, mitglieder_admin):
	"""Klein 5: ein Formular mit Registrierungslinks wird verweigert."""
	from diakronos_app.api import admin_hub
	from diakronos_app.models.diakonos import (
		Anmeldeformular,
		Registrierungslink,
	)

	db.add(Anmeldeformular(name="AF-X", bezeichnung="X", mit_kinder=False,
	                       mit_gaesten=False, docstatus=0, idx=0))
	db.add(Registrierungslink(
		name="RL-X", bezeichnung="L", typ="Mitglied-Registrierung", aktiv=True,
		slug="slug-x", anmeldeformular="AF-X", max_anmeldungen=0,
		anmeldungen_count=0, docstatus=0, idx=0,
	))
	db.commit()
	set_user("verwaltung@test.local")

	with pytest.raises(Exception) as fehler:
		admin_hub.delete_anmeldeformular("AF-X", bestaetigt=1)
	assert "Registrierungslinks" in str(fehler.value)
	db.expire_all()
	assert db.get(Anmeldeformular, "AF-X") is not None
