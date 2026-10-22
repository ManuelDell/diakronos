"""A1c3, Punkt 3: Die Test-Naht `set_user()` darf im Betrieb nichts gelten.

Die Lage: `frappe_compat/session.py::set_user()` markiert die Identitaet als
"explizit gesetzt", und `SessionMiddleware` **ueberschreibt sie dann nicht** —
der Aufrufer gewinnt also gegen das `sid`-Cookie. Fuer Tests genau richtig, im
Produktivpfad waere es eine vollstaendige Umgehung der Anmeldung: ein
einziger Aufruf irgendwo im Servercode, und jeder Request laeuft als der
gerufene Benutzer.

Gemessen (Wegwerf-Container, src gemountet): **kein** Produktionscode ruft
`set_user()`. (`api/dashboard.py:240/286` heissen `set_user_config` /
`reset_user_config` und sind etwas anderes — nicht verwechseln.) Die Naht ist
also heute harmlos, aber sie ist eine geladene Waffe, deren Abzug nur an der
Disziplin haengt.

Gewaehlt ist Variante (a) "Abschalten" aus der Karte, nicht (b) "Entfernen":
17 Testmodule stellen ihre Identitaet per `set_user()`. (b) wuerde bedeuten,
diese 17 Module auf echte Sitzungen umzuschreiben — das ist ein Umbau der
gesamten Testsuite und gehoert in eine eigene Karte, nicht als Nebenwirkung
einer Review-Notiz.

Die Form des Hakens ist bewusst **keine ENV-Variable** (die Karte laesst beides
zu): eine ENV-Variable kann versehentlich im Compose- oder
Produktions-ENV stehen, und genau das soll sie nicht. Stattdessen schaltet
eine pytest-Autouse-Fixture in `conftest.py` den Haken prozesslokal ein — im
Betrieb ist er damit strukturell nicht erreichbar, unabhaengig von jeder
Konfiguration. `test_keine_env_und_kein_compose_schalten_die_naht` nagelt das
fest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "diakronos_app"


def _repo_root() -> Path | None:
    """Projektwurzel — oder `None`, wenn der Test im Image laeuft.

    Im Repo liegt `tests/` unter `backend/`, die Wurzel also zwei Ebenen
    hoeher. Im Image liegt der Test in `/app/tests` (das Dockerfile kopiert
    `backend/tests` nach `/app/tests` und verliert die `backend/`-Ebene), und
    es gibt gar keine `docker-compose.yml` im Dateisystem. Deshalb wird nicht
    geraten, sondern die Datei gesucht — mit `None` als ehrlicher Antwort.
    """
    for kandidat in Path(__file__).resolve().parents:
        if (kandidat / "docker-compose.yml").is_file():
            return kandidat
    return None


@pytest.fixture()
def naht_aus():
    """Schaltet die Test-Naht fuer die Dauer des Tests ab.

    Notwendig, weil die Autouse-Fixture aus `conftest.py` sie in JEDEM Test
    einschaltet — genau so, wie es die Suite heute braucht. Ohne diesen
    Fixture laege man innerhalb der Tests immer im "Produktiv"-Zustand und
    koennte die Zusage der Karte gar nicht messen.
    """
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    with session_mod.testnaht_aus():
        yield


# ── Die Zusage ─────────────────────────────────────────────────────────────


def test_set_user_ohne_haken_wirkt_nicht(naht_aus) -> None:
    """Kern der Karte: ohne Haken keine Wirkung.

    Geprueft wird **nicht nur** die Ausnahme, sondern der Zustand danach:
    `session.user` bleibt `Guest` und `user_uebersteuert()` bleibt `False`.
    Ein Aufrufer, der die Ausnahme faengt, darf also nicht auf eine
    halbgesetzte Identitaet zurueckfallen.
    """
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    assert session_mod.naht_aktiv() is False, "Vorbedingung: Haken ist aus"

    with pytest.raises(RuntimeError) as excinfo:
        session_mod.set_user("Administrator")

    # Die Meldung muss den Grund und den Weg zur Loesung nennen.
    text = str(excinfo.value).lower()
    assert "test" in text, f"RuntimeError nennt das Wort Test nicht: {excinfo.value}"
    assert "naht" in text or "haken" in text, (
        f"RuntimeError nennt die Naht nicht: {excinfo.value}"
    )

    # Und vor allem: nichts hat sich geaendert.
    assert session_mod.session.user == session_mod.GUEST
    assert session_mod.user_uebersteuert() is False


def test_middleware_ueberschreibt_im_betrieb_trotzdem(naht_aus, monkeypatch) -> None:
    """Der naechste Schritt: die Middleware laesst nichts unangetastet.

    `set_user()` ist im Betrieb wirkungslos, also stellt sich die Frage
    zu Recht: was, wenn jemand `session.user = …` direkt setzt (ohne die
    Naht zu benutzen)? Dann ist `_overridden` **nicht** gesetzt — und genau
    daran erkennt die Middleware, dass sie ueberschreiben darf. Der Test
    haelt fest, dass der Schutzweg auch umgangen werden kann, ohne dass
    `_overridden` True wird.
    """
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    session_mod.session.user = "Administrator"

    assert session_mod.session.user == "Administrator"
    assert session_mod.user_uebersteuert() is False, (
        "Direktes Setzen von session.user darf die Identitaet NICHT als "
        "uebersteuert markieren — sonst waere es ein zweites Weg zur Umgehung"
    )


def test_naht_aktiviert_verhaelt_sich_wie_bisher(naht_aus) -> None:
    """Gegenrichtung: mit Haken arbeitet `set_user()` unveraendert.

    Das ist die Zusage an die 17 Testmodule, die sich darauf verlassen.
    """
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    with session_mod.testnaht():
        assert session_mod.naht_aktiv() is True
        session_mod.set_user("Administrator")
        assert session_mod.session.user == "Administrator"
        assert session_mod.user_uebersteuert() is True

    # `reset_user()` beendet auch die Uebersteuerung.
    assert session_mod.user_uebersteuert() is False
    assert session_mod.session.user == session_mod.GUEST


# ── Der Schalter darf nicht versehentlich im Betrieb stehen ─────────────────


def test_keine_env_und_kein_compose_schalten_die_naht() -> None:
    """Die Naht haengt an einem Haken, den es im Betrieb nicht gibt.

    Drei Pruefungen statt einer, weil jede fuer sich eine andere
    Ausrede offenlaesst:
      1. `session.py` liest die ENV **nicht** (kein `os.environ`, kein
         `getenv`, kein Settings-Feld) — der Schalter ist nicht von aussen
         erreichbar;
      2. `docker-compose.yml` traegt keinen solchen Schalter;
      3. `.env.example` beschreibt keinen solchen Schalter (sonst traegt ihn
         der naechste, der die Datei abhakt).
    """
    import importlib

    session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

    quelle = (SRC / "frappe_compat" / "session.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)

    # 1. Kein ENV-Zugriff in session.py.
    verboten = {"environ", "getenv"}
    zugriffe: list[str] = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Attribute) and knoten.attr in verboten:
            zugriffe.append(knoten.attr)
    assert not zugriffe, (
        "session.py greift auf die Umgebung zu — der Naht-Schalter darf nicht "
        f"konfigurierbar sein: {zugriffe}"
    )

    # 2./3. Kein Schaltername in Compose oder Beispiel-ENV.
    #     Gesucht wird nach dem, was jemand eintragen wuerde: die Funktionen
    #     `testnaht`/`naht_aktiv` bzw. eine ENV mit TEST im Namen.
    wurzel = _repo_root()
    if wurzel is None:
        # Im Image gibt es diese Dateien nicht — die Zusage kann dort weder
        # geprueft noch verletzt werden. Kein stiller Skip: die Pruefung oben
        # (kein ENV-Zugriff im Code) ist die tragende, die laeuft ueberall.
        pytest.skip(
            "Kein docker-compose.yml/.env.example im Dateisystem (Image-Lauf). "
            "Die tragende Pruefung 'session.py liest keine ENV' laeuft trotzdem."
        )
    for datei in (wurzel / "docker-compose.yml", wurzel / ".env.example"):
        inhalt = datei.read_text(encoding="utf-8")
        zeilen = [
            zeile
            for zeile in inhalt.splitlines()
            if "naht" in zeile.lower() or "SET_USER" in zeile
        ]
        assert not zeilen, f"{datei.name} schaltet die Test-Naht: {zeilen}"

    # Und der Schalter existiert ueberhaupt als eigene Funktion — sonst waere
    # der Test oben (und der Fixture in conftest.py) Luft.
    assert hasattr(session_mod, "testnaht"), "testnaht() fehlt"
    assert hasattr(session_mod, "testnaht_aus"), "testnaht_aus() fehlt"
    assert hasattr(session_mod, "naht_aktiv"), "naht_aktiv() fehlt"


# ── Gegenprobe auf Ebene des Codes ─────────────────────────────────────────
#
# Ein `set_user()`, das still nichts tut, waere ebenfalls "gruen" fuer
# `test_set_user_ohne_haken_wirkt_nicht` — aber dann waere jeder Test, der die
# Naht benutzt, stillschweigend sinnlos. Deshalb wird der Aufbau des Codes
# selbst geprueft.


def test_set_user_prueft_den_haken_vor_der_wirkung() -> None:
    """Die Haken-Pruefung steht VOR jeder Wirkung in `set_user()`.

    Per AST, weil ein Reihenfolgefehler hier sonst nur durch Zufall auffaellt:
    `session.user = user` **vor** der Pruefung wuerde die Identitaet setzen und
    dann zurueckgeben — `pytest.raises` waere gruen, `user_uebersteuert()` aber
    auch, und die Middleware wuerde weiterhin die Identitaet schonen.

    Geprueft wird die Reihenfolge der drei Effekte im Rumpf:
      1. `naht_aktiv()` — die Abfrage,
      2. das `raise` bei ausgeschaltetem Haken,
      3. `session.user = user` / `_overridden.set(True)` — die eigentliche
         Wirkung.
    """
    quelle = (SRC / "frappe_compat" / "session.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)

    funktion = next(
        n
        for n in ast.walk(baum)
        if isinstance(n, ast.FunctionDef) and n.name == "set_user"
    )

    def _name(knoten) -> str:
        """Name des aufgerufenen Ziels — `f()` wie auch `a.f()`."""
        func = getattr(knoten, "func", None)
        if isinstance(func, ast.Name):
            return func.id
        return getattr(func, "attr", "")

    abfrage = [k.lineno for k in ast.walk(funktion)
               if isinstance(k, ast.Call) and _name(k) == "naht_aktiv"]
    assert abfrage, "set_user() fragt den Haken nicht ab"

    wirf = [k.lineno for k in ast.walk(funktion) if isinstance(k, ast.Raise)]
    assert wirf, "set_user() wirft ohne Haken nichts"

    wirkung = [k.lineno for k in ast.walk(funktion)
               if isinstance(k, ast.Assign)
               or (isinstance(k, ast.Call) and _name(k) == "set")]
    assert wirkung, "set_user() hat gar keine Wirkung mehr"

    # Reihenfolge: erst die Abfrage, dann das Werfen, dann die Wirkung.
    assert min(abfrage) < min(wirf), (
        f"Haken-Abfrage bei Zeile {min(abfrage)}, raise aber schon bei {min(wirf)}"
    )
    assert min(wirf) < min(wirkung), (
        f"raise bei Zeile {min(wirf)}, die Identitaet aber schon bei {min(wirkung)}"
    )
