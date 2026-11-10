"""TEST-ISO1: Ein Alembic-Lauf darf die Logger der Suite nicht stumm schalten.

Befund 08.11.: In der Auswahl

    tests/test_bs1a2_website_freigaben_nachbesserung.py
    tests/test_bs1a_website_freigaben.py
    tests/test_bs2a2_bausteine.py tests/test_bs2a_bausteine.py
    tests/test_drift1_alembic_check.py tests/test_dsgvo1d_alembic_kette.py
    tests/test_health.py tests/test_login3_*.py tests/test_sec11_methoden.py
    tests/test_spa_serving.py tests/test_web10_kontakt.py
    tests/test_web1_primo_anbindung.py tests/test_web1b_primo_zuordnung.py
    tests/test_web1b_zuordnung_dsgvo.py

waren `test_web10_kontakt.py::test_log_enthaelt_keine_inhalte`,
`::test_log_nennt_bei_fehler_nur_den_typ`,
`test_web1_primo_anbindung.py::test_keine_secrets_im_log` und
`test_web1b_primo_zuordnung.py::test_keine_secrets_im_log` rot — einzeln und
paarweise gruen. Ursache: `alembic/env.py` rief `fileConfig()` ohne
`disable_existing_loggers=False`; der Standard `True` setzt ALLE bereits
vorhandenen Logger auf `disabled = True`, also auch die der importierten App
und den Handler, den `caplog` beim Betreten des Tests anhaengt. Ein
Alembic-Lauf innerhalb des Laufs (hier ueber `command.upgrade`, getrieben von
den BS-1a-Tests) machte damit jeden LOG-Test danach blind.

Der Fix steht an der Naht, an der der Schaden entsteht (env.py), deshalb
prueft dieser Test genau das: ein echter `command.upgrade` gegen eine
Wegwerf-SQLite-Datei, danach muss ein `caplog`-Test weiterhin Datensaetze
sehen.

Die Variante „`disable_existing_loggers = false` in die alembic.ini
schreiben" wurde geprueft und verworfen: Alembic gibt nur die Schluessel aus
der ini weiter, die es selbst kennt (`alembic.config.Config`: Attribute wie
`config_file_name`, `script_location`, `sqlalchemy.url`) — der Schalter
gehoert nicht dazu und erreicht `fileConfig` nie.
"""

from __future__ import annotations

import atexit
import logging
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

#: `logging.root.manager.disable` beim Import DIESES Moduls (Collection-Phase,
#: also vor jedem Test). Verglichen wird im Log-Test und im `atexit`-Haken
#: unten — so faellt jeder Verursacher im selben Lauf auf.
_ZUSTAND_BEIM_START = logging.root.manager.disable


def _wache_am_laufende():
    """Meldet am Laufende, wenn `logging.disable` stehen geblieben ist.

    Bewusst NUR eine Warnung auf stdout: der Haken aendert den Exitstatus
    NICHT (ein `raise` in `atexit` wird von CPython nur als Fehlertext
    gedruckt, nicht als Rueckgabewert durchgereicht). Ob der Lauf gruen ist,
    entscheiden allein die Tests; `test_alembic_lauf_schaltet_keine_logger_stumm`
    prueft denselben Zustand mit einer echten Zusicherung.
    """
    jetzt = logging.root.manager.disable
    if jetzt != _ZUSTAND_BEIM_START:
        print(
            "\n[TEST-ISO1] WARNUNG: `logging.disable` wurde im Lauf von "
            f"{_ZUSTAND_BEIM_START} auf {jetzt} gesetzt und nicht "
            "zurueckgenommen — alle Log-Tests danach sind blind. Verursacher "
            "in der Ausgabe suchen (-p z1ord / -x bis zum ersten Wechsel).",
            flush=True,
        )


atexit.register(_wache_am_laufende)


def _stumme_logger() -> list[str]:
    """Alle Logger, die global abgeschaltet sind — mit Namen fuer die Meldung."""
    return sorted(
        name
        for name, logger in logging.root.manager.loggerDict.items()
        if getattr(logger, "disabled", False)
    )


#: Erwartete Ausnahmen des Laufs auf der leeren In-Memory-SQLite. NUR diese
#: sind hier zulaessig; alles andere ist ein echter Fehler und darf nicht in
#: ein `except Exception: pass` verschwinden (Review TEST-ISO1).
def _erwartete_fehlerklassen() -> tuple[type[BaseException], ...]:
    """Fehlerklassen, mit denen die Kette auf leerer SQLite abbrechen DARF.

    ``alembic.command.upgrade`` verpackt Unerwartetes in ``CommandError``;
    SQLite kann kein ``ALTER TABLE ... ADD CONSTRAINT`` und bricht mit einem
    ``DatabaseError`` (``OperationalError``) ab. Genau das ist der im
    Docstring beschriebene Abbruch — mehr wird hier nicht verziehen.
    """
    from alembic.util.exc import CommandError
    from sqlalchemy.exc import DatabaseError, OperationalError

    return (CommandError, DatabaseError, OperationalError, NotImplementedError)


def _echte_ursache(fehler: BaseException) -> BaseException:
    """Der von Alembic verpackte Grund (``__cause__``), sonst der Fehler selbst."""
    return fehler.__cause__ if fehler.__cause__ is not None else fehler


#: Auf leerer SQLite ist GENAU DIESER Abbruch erwartet: Alembic/SQLite kann
#: ``ALTER ... ADD CONSTRAINT`` nicht (``NotImplementedError`` der SQLAlchemy-
#: SQLite-Dialekte, von Alembic als ``CommandError`` verpackt). Ein
#: Sammel-``DatabaseError`` waere zu weit: er wuerde auch eine kaputte
#: Migration verziehen.
_SQLITE_GRENZE = "No support for ALTER of constraints in SQLite dialect"


def _ist_erwarteter_abbruch(fehler: BaseException) -> bool:
    """Ist das der dokumentierte SQLite-Abbruch der Kette?

    Beobachtet im Image (2026-11-09): der ``NotImplementedError`` des
    SQLite-Dialekts kommt UNVERPACKT aus ``command.upgrade`` (Alembic reicht
    ihn durch, kein ``CommandError``). Deshalb wird er direkt zugelassen —
    aber NUR mit genau diesem Text; ein NotImplementedError aus einer
    Migration selbst faellt weiterhin durch.
    """
    from alembic.util.exc import CommandError

    if isinstance(fehler, CommandError):
        kandidaten = (fehler, _echte_ursache(fehler))
    else:
        kandidaten = (fehler,)
    return any(_SQLITE_GRENZE in str(kandidat) for kandidat in kandidaten)


@pytest.fixture()
def frischer_logger(monkeypatch):
    """Ein eigener Logger fuer den Test, vor dem Alembic-Lauf angelegt.

    Genau das ist der Fall im Befund: der App-Logger existiert schon, wenn die
    Migration laeuft. `caplog` haengt seinen Handler an WURZEL und Logger —
    der Logger muss also vorher da sein, damit `disable_existing_loggers=True`
    ihn trifft.
    """
    name = "diakronos_app.test_iso1_sonde"
    logger = logging.getLogger(name)
    logger.disabled = False
    yield logger


def test_alembic_lauf_schaltet_keine_logger_stumm(frischer_logger, monkeypatch):
    """`command.upgrade` darf fremde Logger nicht abschalten (Kern des Befunds).

    Geprueft wird der Zustand nach dem Lauf, nicht ueber `caplog`: `caplog`
    haengt seinen Handler erst beim Betreten des Tests an, und `fileConfig`
    legt fuer die Wurzel einen EIGENEN Handler an — die Wurzel traegt danach
    zwei. Fuer die Log-Tests der Suite zaehlt genau das: ihr Logger ist noch
    aktiv und reicht weiter, also bekommen sie ihre Datensaetze.
    """
    from alembic import command
    from alembic.config import Config

    from diakronos_app.settings import settings

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    alt = settings.database_url
    settings.database_url = "sqlite+pysqlite:///:memory:"
    try:
        # Auf einer leeren SQLite scheitert die Kette an einer
        # ALTER-Constraint-Operation — das ist hier egal: `fileConfig` laeuft
        # VOR den Migrationen, der Logger-Zustand ist danach schon gesetzt.
        # Verziehen werden NUR die erwarteten Klassen (Review TEST-ISO1: das
        # fruehere `except Exception: pass` haette auch einen kaputten
        # Import oder einen Tippfehler in der Kette verschluckt und den Test
        # dann gruen gemeldet). Alles andere bricht den Test ab.
        try:
            command.upgrade(cfg, "head")
        except _erwartete_fehlerklassen() as fehler:
            if not _ist_erwarteter_abbruch(fehler):
                raise
            # ... und nur der ist verziehen; jeder andere Fehler (kaputte
            # Migration, Importfehler) schlaegt hier durch.
    finally:
        settings.database_url = alt

    assert frischer_logger.disabled is False, (
        "Der Alembic-Lauf hat den Logger der App stumm geschaltet — "
        "genau der TEST-ISO1-Befund."
    )
    # TEST-ISO1 (Befund in der VOLLEN Suite): hier stand nur diese Zusicherung
    # — und sie kippte intermittierend (`disable == CRITICAL`). Ursache: ein
    # Test setzt irgendwo `logging.disable(CRITICAL)` prozessweit; ohne
    # Zuruecksetzen bleibt die GANZE Suite danach blind (der Fehler tritt
    # dann nicht hier auf, sondern in jedem spaeteren Log-Test und trifft
    # je nach Reihenfolge andere Dateien).
    #
    # Darum wird der Zustand JETZT eingefroren und in einem `atexit`-Haken
    # geprueft: kippt er zwischen diesem Test und dem Ende des Laufs, meldet
    # der Haken den Verursacher auf stdout (NUR eine Warnung — der Exitstatus
    # bleibt davon unberuehrt). Das ist die Wache, die die Ursache sichtbar
    # macht, statt sie zu verziehen.
    assert logging.root.manager.disable == _ZUSTAND_BEIM_START, (
        "Zwischen Testbeginn und diesem Punkt hat jemand "
        f"`logging.disable()` benutzt: disable={logging.root.manager.disable} "
        f"(beim Start {_ZUSTAND_BEIM_START}) — genau der TEST-ISO1-Befund."
    )
    # Die ALTE Zusicherung bleibt zusaetzlich stehen (Review ZEIT-1): auch
    # wenn der Startwert bereits ungleich 0 war, darf nach dem Alembic-Lauf
    # nichts ueber CRITICAL hinaus abgeschaltet sein.
    assert 0 <= logging.root.manager.disable < logging.CRITICAL, (
        "Logger sind auf oder ueber CRITICAL stumm geschaltet: "
        f"disable={logging.root.manager.disable} "
        f"(Schwelle {logging.CRITICAL} = nichts kommt mehr durch)"
    )
    # Der Logger muss weiterhin bis zur Wurzel durchreichen — `caplog`
    # haengt seinen Handler dort an.
    assert frischer_logger.propagate is True
    assert not _stumme_logger(), (
        "Der Alembic-Lauf hat fremde Logger abgeschaltet: "
        f"{_stumme_logger()[:5]}"
    )

    # Gegenprobe: ein Datensatz nimmt wirklich den Weg bis zur Wurzel.
    gesammelt: list[str] = []

    class Sammler(logging.Handler):
        def emit(self, record):
            gesammelt.append(record.getMessage())

    sammler = Sammler()
    sammler.setLevel(logging.NOTSET)
    wurzel = logging.getLogger()
    alt_level = wurzel.level
    wurzel.addHandler(sammler)
    try:
        wurzel.setLevel(logging.WARNING)
        frischer_logger.setLevel(logging.WARNING)
        frischer_logger.warning("TEST-ISO1 Gegenprobe")
    finally:
        wurzel.removeHandler(sammler)
        wurzel.setLevel(alt_level)

    assert "TEST-ISO1 Gegenprobe" in gesammelt, (
        "kein Datensatz angekommen — der Log-Pfad ist nach dem Alembic-Lauf blind"
    )


def test_env_py_setzt_disable_existing_loggers_aus():
    """Der Schalter steht am `fileConfig`-Aufruf in `alembic/env.py`."""
    quelle = (BACKEND / "alembic" / "env.py").read_text(encoding="utf-8")
    aufruf = [z for z in quelle.splitlines() if z.strip().startswith("fileConfig(")]
    assert aufruf, "env.py ruft fileConfig nicht mehr auf"
    assert "disable_existing_loggers=False" in aufruf[0].replace(" ", ""), (
        f"fileConfig ohne den Schalter: {aufruf[0]!r}"
    )


def test_alembic_ini_verspricht_nichts_was_nicht_wirkt():
    """Die ini traegt KEINEN `disable_existing_loggers`-Eintrag, der nur taeuscht.

    Alembic reicht den Schluessel nicht durch; ein Eintrag dort haette keinen
    Effekt und wuerde den Fix beim naechsten Umbau wieder verdecken.
    """
    ini = (BACKEND / "alembic.ini").read_text(encoding="utf-8")
    aktiv = [
        z for z in ini.splitlines()
        if z.strip().startswith("disable_existing_loggers")
    ]
    assert not aktiv, (
        "disable_existing_loggers in der alembic.ini wirkt nicht "
        f"(Alembic reicht ihn nicht an fileConfig durch): {aktiv}"
    )
