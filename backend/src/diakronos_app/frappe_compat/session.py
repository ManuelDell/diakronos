"""`frappe.session` — aktueller Benutzer.

Seit A1b2 (Umschaltung) ist der Default `Guest`: ein Aufruf ohne gueltige
Sitzung ist NICHT angemeldet. Die `SessionMiddleware` in
`frappe_compat/auth_middleware.py` setzt den Benutzer pro Request aus dem
`sid`-Cookie; ohne Sitzung bleibt es bei `Guest`. Portierter Code
(`frappe.session.user`) laeuft unveraendert weiter, sieht aber die Wahrheit.

Vor A1b2 stand hier `Administrator` — damit war jeder anonyme Aufruf
Administrator. Genau dieses Loch schliesst die Karte.

Test-Naht (`set_user`)
----------------------
Die portierte Test-Suite (16 Module) stellt die Identitaet per
`session.set_user(...)` — teils mitten im Test, teils als Modul-Import. Das
ist eine bewusste, prozess-lokale Uebersteuerung und keine echte Sitzung.

`set_user()` markiert die Identitaet deshalb als **explizit gesetzt**; die
`SessionMiddleware` laesst eine solche Identitaet unangetastet, statt sie aus
dem Cookie zu ueberschreiben. Ohne Aufruf von `set_user()` bleibt es bei der
Cookiewahrheit (`Guest` ohne Sitzung). `reset_user()` hebelt die Naht wieder
aus.

Diese Uebersteuerung ist im **Produktivpfad eine vollstaendige Umgehung der
Anmeldung**: ein einziger Aufruf irgendwo im Servercode, und jeder Request
laeuft als der gerufene Benutzer. Bisher hing das allein an der Disziplin
("Produktionscode ruft `set_user()` nie auf" — ein Kommentar). Seit A1c3
haengt es an einem **Haken**:

  * `set_user()` wirkt nur, wenn `naht_aktiv()` `True` sagt.
  * `naht_aktiv()` ist genau dann wahr, wenn `testnaht()` den Haken gesetzt
    hat — und das tut ausschliesslich die Autouse-Fixture in
    `tests/conftest.py`.
  * Ohne Haken wirft `set_user()` `RuntimeError` und aendert **nichts**: kein
    halbgesetzter `session.user`, kein gesetztes `_overridden`.

Warum ausdruecklich KEINE ENV-Variable: die Karte laesst beides zu, aber eine
ENV kann versehentlich im Compose- oder Produktions-ENV stehen — genau das
soll sie nicht. Der Haken lebt in einer pytest-Fixture und ist damit im
Betrieb strukturell nicht erreichbar, unabhaengig von jeder Konfiguration.
`test_keine_env_und_kein_compose_schalten_die_naht` nagelt das fest.

Variante (b) der Karte — `set_user()` ersatzlos entfernen und die 17
Testmodule auf echte Sitzungen umstellen — waere der strengere Weg, ist aber
ein Umbau der gesamten Testsuite und gehoert in eine eigene Karte.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

# Nicht angemeldet. Entspricht `frappe.session.user == "Guest"` bei Frappe.
GUEST = "Guest"

DEFAULT_USER = GUEST

_current_user: ContextVar[str] = ContextVar("frappe_session_user", default=DEFAULT_USER)

# True, wenn `set_user()` die Identitaet explizit gesetzt hat (Test-Naht).
# Die Middleware respektiert das und ueberschreibt nicht mit dem Cookie.
# Setzt NUR der Haken (`testnaht`) — nie ein ENV, nie ein Request.
_overridden: ContextVar[bool] = ContextVar("frappe_session_user_override", default=False)

# Der Haken selbst (A1c3). Standardmaessig aus: im Betrieb ist die Naht damit
# nicht erreichbar. Gesetzt wird er nur von `testnaht()` — praktisch von der
# Autouse-Fixture in `tests/conftest.py`.
_naht: ContextVar[bool] = ContextVar("frappe_session_testnaht", default=False)


class _Session:
	"""Minimales `frappe.session`-Interface."""

	@property
	def user(self) -> str:
		return _current_user.get()

	@user.setter
	def user(self, value: str) -> None:
		_current_user.set(value or DEFAULT_USER)

	def get(self, key: str, default=None):
		if key == "user":
			return self.user
		return default


session = _Session()


# ── Der Haken ──────────────────────────────────────────────────────────────


def naht_aktiv() -> bool:
	"""True, wenn die Test-Naht in diesem Kontext eingeschaltet ist.

	Das ist die **einzige** Bedingung, unter der `set_user()` etwas tun darf.
	Aufrufer: `set_user()` selbst. `naht_aktiv()` liest weder ENV noch
	Settings — die Antwort steht ausschliesslich in diesem ContextVar.
	"""
	return _naht.get()


@contextmanager
def testnaht():
	"""Schaltet die Test-Naht **an** (Tests / Testwerkzeuge).

	Verwendung im Test:

	    with testnaht():
	        set_user("Administrator")

	Innerhalb des Blocks verhaelt sich `set_user()` wie bisher. Wird der Block
	verlassen, ist der Haken aus **und** die Identitaet auf `Guest`
	zurueckgesetzt — sonst wuerde eine Naht in den naechsten Test lecken.
	"""
	token = _naht.set(True)
	try:
		yield
	finally:
		_current_user.set(DEFAULT_USER)
		_overridden.set(False)
		_naht.reset(token)


@contextmanager
def testnaht_aus():
	"""Schaltet die Test-Naht **aus** — prueft den Produktivpfad.

	Damit laesst sich die Zusage der Karte messen, obwohl die Autouse-Fixture
	aus `conftest.py` die Naht in jedem Test einschaltet. Ohne diese
	Umkehrung waere der Produktivzustand in der Suite nicht erreichbar.
	"""
	token = _naht.set(False)
	_benutzer = _current_user.set(DEFAULT_USER)
	_uebersteuert = _overridden.set(False)
	try:
		yield
	finally:
		_naht.reset(token)
		_current_user.reset(_benutzer)
		_overridden.reset(_uebersteuert)


# ── Die Naht ───────────────────────────────────────────────────────────────


def set_user(user: str) -> None:
	"""Setzt den aktuellen Benutzer explizit — **nur mit Test-Haken**.

	Markiert die Identitaet als uebersteuert, damit die `SessionMiddleware`
	sie nicht aus dem `sid`-Cookie ueberschreibt. Produktionscode setzt den
	Benutzer ueber die Middleware (Cookie), nicht ueber diese Funktion.

	A1c3: ohne eingeschalteten Haken (`naht_aktiv()`, siehe `testnaht()`) wird
	**nichts** gesetzt und `RuntimeError` geworfen. Grund: diese Funktion
	gewinnt gegen das Sitzungs-Cookie, waere also im Produktivpfad eine
	vollstaendige Umgehung der Anmeldung. Die Ausnahme wird **vor** jeder
	Wirkung geprueft, damit ein Aufrufer, der sie faengt, nicht auf einer
	thalbgesetzten Identitaet zuruecklaeuft.

	Die Identitaet bleibt `Guest`, wenn dies ohne Haken passiert — der
	Produktivzustand fuer einen Aufruf ohne Sitzung.
	"""
	if not naht_aktiv():
		raise RuntimeError(
			"set_user() ist eine Test-Naht und im Betrieb abgeschaltet. "
			"Die Identitaet kommt aus dem sid-Cookie (SessionMiddleware). "
			"Fuer Tests: with diakronos_app.frappe_compat.session.testnaht(): "
			"set_user(...) — die Autouse-Fixture in tests/conftest.py "
			"schaltet den Haken bereits."
		)
	session.user = user
	_overridden.set(True)


def reset_user() -> None:
	"""Hebt die explizite Uebersteuerung auf (Test-Naht zuruecksetzen).

	Danach gilt wieder die Cookiewahrheit. Fuer Tests gedacht, die zwischen
	zwei Faellen die Identitaet sauber zuruecksetzen wollen.
	"""
	_overridden.set(False)
	_current_user.set(DEFAULT_USER)


def user_uebersteuert() -> bool:
	"""True, wenn `set_user()` die Identitaet explizit gesetzt hat."""
	return _overridden.get()
