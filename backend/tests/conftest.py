"""Test-Fixtures: frische In-Memory-SQLite-DB mit allen Modelltabellen.

Die App benutzt `SessionLocal` und `engine` aus `diakronos_app.db`; wir
patchen beide auf die Test-Engine, damit Router und Compat-Schicht dieselbe
DB sehen. Kein PG-spezifischer Typ in den Modellen -> SQLite reicht.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
	"""Auch ungepatchte Redis-Pfade der Vollsuite duerfen nicht in den Betrieb.

	Vor der Collection setzen: settings und Unterprozesse lesen REDIS_URL beim
	Import, waehrend eine autouse-Fixture dafuer bereits zu spaet kaeme.
	Die CLI-Fixture bekommt zusaetzlich ihren eigenen, pro Test geleerten Store.
	"""
	import os
	from contextlib import ExitStack
	# Die Google-Verschluesselung verweigert den Platzhalter-Schluessel; Tests ohne
	# gesetzten SECRET_KEY (netzloser Wegwerf-Lauf) brauchen einen eigenen.
	os.environ.setdefault("SECRET_KEY", "test-only-secret-key-never-use-in-production")
	from redis_testdb import privates_redis

	stack = ExitStack()
	config.add_cleanup(stack.close)
	vorher = os.environ.get("REDIS_URL")

	def wiederherstellen():
		if vorher is None:
			os.environ.pop("REDIS_URL", None)
		else:
			os.environ["REDIS_URL"] = vorher

	url = stack.enter_context(privates_redis())
	stack.callback(wiederherstellen)
	os.environ["REDIS_URL"] = url


@pytest.fixture(scope="session")
def privater_redis_url():
	"""Eigener nicht persistierender Redis-Server fuer echte CLI-Tests."""
	from redis_testdb import privates_redis

	with privates_redis() as url:
		yield url


@pytest.fixture(autouse=True)
def _testnaht():
	"""Schaltet die Test-Naht fuer **jeden** Test ein (A1c3).

	`frappe_compat/session.py::set_user()` ist im Betrieb abgeschaltet: ohne
	diesen Haken wirft sie `RuntimeError` und aendert nichts. Genau darum
	greift der Haken hier, statt ueber ENV oder Compose — eine pytest-Fixture
	ist im Betrieb strukturell nicht erreichbar.

	`testnaht_aus()` (aus derselben Datei) schaltet ihn fuer einzelne Tests
	wieder aus, damit der Produktivpfad messbar bleibt; siehe
	`tests/test_a1c3_set_user_naht.py`.

	KontextVar, deshalb pro Kontext statt pro Prozess — der Haken leckt nicht
	in den naechsten Test.

	Achtung, Import: `from diakronos_app.frappe_compat import session` liefert
	NICHT das Modul, sondern das `session`-Objekt — `frappe_compat/__init__.py`
	binde den Namen mit `from .session import ... session ...` um. Deshalb
	`importlib.import_module` bzw. der `import x.y as z`-Form, die das
	`sys.modules`-Objekt liefert statt des Paketattributs.
	"""
	import importlib

	session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

	with session_mod.testnaht():
		yield


@pytest.fixture()
def engine():
	# In-Memory-SQLite mit StaticPool: EINE geteilte Verbindung, damit
	# TestClient (eigener Thread) und App dieselbe DB sehen. Der
	# StatischPool-Effekt auf zweite Sitzungen wird in `patched_db`/`session_factory`
	# ueber `join_transaction_mode` entschaerft — siehe Kommentar dort.
	from sqlalchemy.pool import StaticPool

	eng = create_engine(
		"sqlite+pysqlite:///:memory:",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
		future=True,
	)
	import diakronos_app.models  # noqa: F401 — Modelle registrieren
	from diakronos_app.models.base import Base

	Base.metadata.create_all(eng)
	yield eng
	Base.metadata.drop_all(eng)
	eng.dispose()


@pytest.fixture()
def session_factory(engine):
	return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def altbestand_dublette(engine):
	"""Erlaubt das Anlegen eines ALTbestands mit doppelter E-Mail-Adresse.

	SEC-b (Fachentscheidung Manuel 2026-10-19): Neue Dopplungen lehnt der
	partielle Unique-Index `uq_mitglied_email_normalisiert` ab. Manche Tests
	pruefen aber bewusst das Verhalten fuer Daten, die VOR der Migration
	entstanden sind („Familienpostfach im Altbestand“) — die Lesart dort ist
	fail closed: ein Ausschluss ueber die Adresse wirkt trotzdem.

	Der Helfer nimmt den Index fuer die Dauer des Blocks heraus, damit solche
	Altbestaende herstellbar bleiben, ohne die Zusage fuer neue Daten
	aufzuweichen. Er stellt den Index am Ende wieder her.
	"""
	from diakronos_app.models.diakonos import Mitglied

	def _index_entfernen() -> None:
		# Direktes DDL ausserhalb einer Transaktion: SQLite fuehrt es sofort
		# aus (kein implizites Transaktions-Handling von SQLAlchemy).
		with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
			for idx in Mitglied.__table__.indexes:
				conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{idx.name}"')

	def _index_anlegen() -> None:
		with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
			for idx in Mitglied.__table__.indexes:
				conn.exec_driver_sql(
					f"CREATE UNIQUE INDEX IF NOT EXISTS {idx.name} ON "
					"mitglied (lower(trim(email))) "
					"WHERE coalesce(trim(email), '') <> ''"
				)

	_index_entfernen()
	try:
		yield
	finally:
		# Vor dem Wiederherstellen die Dopplungen aufloesen — der Index ist
		# gerade die Zusage, die zwei Mitglieder mit derselben Adresse
		# verbietet. Danach ist die Test-Datenbank wieder im Zielzustand.
		with engine.begin() as conn:
			conn.exec_driver_sql(
				"UPDATE mitglied SET email = NULL WHERE name IN ("
				"  SELECT name FROM mitglied m WHERE email IS NOT NULL "
				"  AND EXISTS (SELECT 1 FROM mitglied o WHERE o.name <> m.name "
				"              AND lower(trim(o.email)) = lower(trim(m.email))))"
			)
		_index_anlegen()


@pytest.fixture()
def patched_db(engine, session_factory, monkeypatch):
	"""Patcht engine + SessionLocal + alle bereits importierten Bindungen."""
	import diakronos_app.db as dbmod

	monkeypatch.setattr(dbmod, "engine", engine)
	monkeypatch.setattr(dbmod, "SessionLocal", session_factory)

	# Module, die SessionLocal per `from ... import` gebunden haben, mitpatchen.
	for modname in ("diakronos_app.frappe_compat.query", "diakronos_app.frappe_compat.db",
	                "diakronos_app.frappe_compat.doc", "diakronos_app.frappe_compat.router"):
		mod = __import__(modname, fromlist=["_"])
		if hasattr(mod, "SessionLocal"):
			monkeypatch.setattr(mod, "SessionLocal", session_factory)
	return session_factory


@pytest.fixture()
def fake_redis(monkeypatch):
	"""Patcht den Redis-Client der Sitzungs-Schicht auf einen In-Memory-Stub.

	Die Vorarbeit hat gemeldet, dass `conftest.py` Redis
	NICHT patcht und Sitzungs-Tests damit nicht isoliert waeren. Dieser
	Fixture schliesst die Luecke — jeder Test bekommt einen frischen Store.

	Auch fuer `client` noetig: sobald ein Endpunkt eine echte Sitzung liest
	oder schreibt, darf er nicht ins echte Redis greifen.

	A1c1: `loginversuche` benutzt DENSELBEN Stub, sonst wuerde ein
	Brute-Force-Test gegen das echte Redis des laufenden Stacks zaehlen und
	der naechste Test startete mit einem gesperrten Benutzer.

	B1: `benutzer_status` (der Cache "existiert und ist `enabled`") ebenfalls.
	Ohne das wuerde die `SessionMiddleware` in jedem Test in das Redis des
	laufenden Stacks fragen — und dort liegen echte Konten mit echtem
	`enabled`-Status. Ein Test, der seinen Benutzer gerade deaktiviert hat,
	laege dann eine Sekunde lang auf der falschen Antwort.
	"""
	from redis_stub import StubRedis
	from diakronos_app.frappe_compat import benutzer_status, loginversuche, sitzungen
	from diakronos_app.anmeldung import registrierungsbremse

	stub = StubRedis()
	monkeypatch.setattr(sitzungen, "_client", lambda: stub)
	monkeypatch.setattr(loginversuche, "_client", lambda: stub)
	monkeypatch.setattr(benutzer_status, "_client", lambda: stub)
	# P0-4b: die Ratenbegrenzung der oeffentlichen Registrierung nutzt denselben
	# Stub. Ohne das zaehlten die Tests gegen das echte Redis des laufenden
	# Stacks — und der naechste Test startete mit einer erreichten Grenze.
	monkeypatch.setattr(registrierungsbremse, "_client", lambda: stub)
	return stub


@pytest.fixture()
def set_user():
	"""Setzt die Identitaet des Aufrufs — Ersatz fuer den frueheren Default.

	Vor A1b2 war `session.user` immer `Administrator` (die "Kernzeile"). Seit
	der Umschaltung setzt die `SessionMiddleware` den Benutzer pro Request aus
	dem `sid`-Cookie.

	Bestandstests stellen die Identitaet aber weiter mitten im Test per
	`session.set_user(...)` um. Damit das greift und nicht vom Cookie
	ueberschrieben wird, markiert `session.set_user()` die Identitaet als
	explizit gesetzt; die Middleware respektiert das (siehe `session.py`).
	Dieser Fixture setzt den Namen und laesst die Naht danach wieder fallen,
	damit kein Fall in den naechsten leckt.
	"""
	from diakronos_app import frappe_compat

	session = frappe_compat.session

	def _set(name="Administrator", *_a, **_kw):
		frappe_compat.set_user(name)
		return name

	yield _set
	frappe_compat.reset_user()


@pytest.fixture()
def client(patched_db, fake_redis):
	"""HTTP-Client als `Administrator` (wie vor A1b2 der implizite Default).

	Die Bestandstests lebten von `session.user == "Administrator"`. Damit das
	weiter gilt, setzt der Fixture dieselbe Identitaet ueber die Test-Naht
	(`session.set_user`) — die Middleware respektiert sie.

	Fuer das Schreiben braucht die CSRF-Middleware zusaetzlich eine echte
	Sitzung mit `X-Frappe-CSRF-Token`. Die legt der Fixture an und haengt sie
	als Cookie + Header an den Client; die Identitaet kommt aber weiter aus
	der Naht (Cookie und Naht nennen beide "Administrator").

	**B1**: Die `user`-Zeile fuer `Administrator` muss wirklich existieren.
	Seit B1 prueft die `SessionMiddleware` bei jedem Aufruf, ob der Benutzer
	der Sitzung noch da und noch `enabled` ist; ohne Zeile gilt der Aufruf als
	`Guest`. Das ist die beabsichtigte Regel, nicht ein Nebeneffekt — deshalb
	legt der Fixture sie hier an, statt den Check abzuschwaechen.
	"""
	from diakronos_app.main import app
	from diakronos_app import frappe_compat
	from diakronos_app.frappe_compat import sitzungen
	from diakronos_app.models.core import User

	fremd = patched_db()
	if fremd.get(User, "Administrator") is None:
		fremd.add(User(
			name="Administrator", email="Administrator",
			full_name="Administrator", enabled=True,
		))
		fremd.commit()
	fremd.close()

	frappe_compat.set_user("Administrator")
	sid, csrf = sitzungen.anlegen("Administrator")

	with TestClient(app) as c:
		c.cookies.set("sid", sid)
		c.headers["X-Frappe-CSRF-Token"] = csrf
		yield c

	frappe_compat.reset_user()


@pytest.fixture()
def guest_client(patched_db, fake_redis):
	"""HTTP-Client OHNE Sitzung — jeder Aufruf ist `Guest`."""
	from diakronos_app.main import app

	with TestClient(app) as c:
		yield c


@pytest.fixture()
def seed_mitglieder(patched_db):
	"""Legt drei Mitglieder an und gibt die Session zum Nachpruefen zurueck."""
	from diakronos_app.models.diakonos import Mitglied

	sess = patched_db()
	rows = [
		Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
		         email="anna@example.org", status="Mitglied", docstatus=0, idx=0,
		         wohnort="Stuttgart", postleitzahl="70173",
		         ancestor_path="/M-0001"),
		Mitglied(name="M-0002", vorname="Bruno", nachname="Brandner",
		         email="bruno@example.org", status="Mitglied", docstatus=0, idx=0,
		         wohnort="Esslingen", postleitzahl="73728",
		         ancestor_path="/M-0002"),
		Mitglied(name="M-0003", vorname="Clara", nachname="Clausen",
		         email="clara@example.org", status="Ausgetreten", docstatus=0, idx=0,
		         wohnort="Ludwigsburg", postleitzahl="71634",
		         ancestor_path="/M-0003"),
	]
	sess.add_all(rows)
	sess.commit()
	yield sess
	sess.close()
