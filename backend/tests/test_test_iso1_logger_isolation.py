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

import logging
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _stumme_logger() -> list[str]:
    """Alle Logger, die global abgeschaltet sind — mit Namen fuer die Meldung."""
    return sorted(
        name
        for name, logger in logging.root.manager.loggerDict.items()
        if getattr(logger, "disabled", False)
    )


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
        try:
            command.upgrade(cfg, "head")
        except Exception:
            pass
    finally:
        settings.database_url = alt

    assert frischer_logger.disabled is False, (
        "Der Alembic-Lauf hat den Logger der App stumm geschaltet — "
        "genau der TEST-ISO1-Befund."
    )
    assert logging.root.manager.disable < logging.CRITICAL
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
