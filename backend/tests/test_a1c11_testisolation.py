"""A1c11: echte Redis-Stores bleiben auch zwischen Testprozessen getrennt."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import redis
import pytest

from test_a1c6_cli_entsperren import echt_stores

#: ZEIT-1 (Review): eigenes `pytest-timeout`-Budget fuer diese Datei. Die
#: Unterprozess-Tests hier warten bis 60 s (`_unterprozess`) bzw. auf eine
#: SQLite-`create_all` im Fixture-Aufbau; das globale Budget (60 s) brach sie
#: ab, bevor die sprechende Meldung kam. Globaler Wert unveraendert.
pytestmark = pytest.mark.timeout(180)



def test_cli_store_ist_nicht_die_redis_instanz_des_betriebs(
        echt_stores, privater_redis_url):
    """Der Teststore ist NIEMALS der Store des Betriebs.

    TEST-ISO1 (Befund im vollen Lauf 09.11.): hier stand
    ``redis.Redis.from_url(settings.redis_url)``. `privates_redis()` setzt
    `settings.redis_url` fuer die Dauer des Kontexts auf den privaten
    Server (Absicht: `erstelle_app()` bekommt die URL EINMAL beim Aufbau
    gereicht), und `conftest.pytest_configure` setzt `REDIS_URL` fuer den
    ganzen Lauf auf denselben privaten Store. Innerhalb des Tests verglich
    die alte Fassung den privaten Store also MIT SICH SELBST — in der
    Vollsuite rot, einzeln (ohne `echt_stores`) gruen.

    Verglichen wird deshalb gegen die BETRIEBS-URL, gemerkt VOR
    `pytest_configure` (`redis_testdb.BETRIEBS_REDIS_URL`). Fehlt sie (Lauf ohne gesetzte
    Umgebungsvariable), greift der Produktions-Default aus `Settings` —
    damit ist der Vergleich immer gegen den Betrieb und nie gegen den
    gerade laufenden Teststore.
    """
    from diakronos_app.settings import Settings

    import redis_testdb

    # Gemerkt in `conftest.pytest_configure` BEVOR die Umgebung auf den
    # privaten Teststore umgebogen wird. Ein Modul-Global hier (Import in der
    # Collection) kaeme zu spaet: pytest_configure laeuft VOR der Collection,
    # `REDIS_URL` zeigt dann schon auf einen privaten Store.
    betriebs_url = (redis_testdb.BETRIEBS_REDIS_URL
                    or Settings.model_fields["redis_url"].default)
    assert betriebs_url != privater_redis_url, (
        "Die Betriebs-URL ist der Teststore — die Umgebung war schon vor "
        f"pytest_configure verbogen ({betriebs_url!r}); der Vergleich unten "
        "waere wertlos")
    # Der Teststore laeuft ueber einen privaten Unix-Socket, der Betrieb
    # nicht aus dem Test heraus erreichbar: der Vergleich ist der run_id.
    assert privater_redis_url.startswith("unix://"), (
        f"Der Teststore laeuft nicht ueber einen privaten Unix-Socket: "
        f"{privater_redis_url!r}")
    if not _erreichbar(betriebs_url):
        # Betriebs-Redis ist aus dem Test-Container nicht erreichbar
        # (eigene Netzinsel): dann ist "verschiedene Server" bereits an der
        # Adresse belegt — der Teststore ist ein unix-Socket, der Betrieb
        # nicht. Kein stilles Ueberspringen: das wird GEMELDET.
        print(f"[A1c11] Betriebs-Store {betriebs_url!r} nicht erreichbar — "
              "Isolation an der Adresse belegt (unix-Socket vs. TCP)")
        return
    betrieb = redis.Redis.from_url(betriebs_url, socket_timeout=2,
                                   socket_connect_timeout=2)
    try:
        assert echt_stores.info("server")["run_id"] != betrieb.info("server")["run_id"], (
            "Der CLI-Teststore ist der Store des Betriebs — die Isolation "
            "zwischen CLI-Unterprozess und Betrieb ist aufgehoben")
    finally:
        betrieb.close()


def _erreichbar(url: str) -> bool:
    """Antwortet der Store? (Nur fuer die Meldung — keine Zusicherung.)"""
    client = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    try:
        return bool(client.ping())
    except Exception:  # noqa: BLE001 — Unerreichbarkeit ist hier ein Befund
        return False
    finally:
        client.close()


def _unterprozess(url, code):
    env = {**os.environ, "REDIS_URL": url}
    # ZEIT-1: 10 s war zu knapp unter Last (Load 15–18): der Prozessstart
    # (Interpreter + `import redis`) brauchte allein mehrere Sekunden, und der
    # Timeout-Fehler von `subprocess.run` sagte nichts ueber die Isolation
    # aus. Die Frist ist bewusst grosszuegig, der Inhalt (ein `flushdb` in
    # einem FREMDEN Store darf den eigenen nicht leeren) bleibt unveraendert.
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True,
            text=True, timeout=60,
        )
    except subprocess.TimeoutExpired as frist:
        raise AssertionError(
            f"Unterprozess nach {frist.timeout} s nicht beendet — "
            f"Start unter Last haengen geblieben; Code: {code!r}") from None
    assert result.returncode == 0, result.stderr


def test_zwei_prozesse_koennen_einander_nicht_leeren():
    from redis_testdb import privates_redis

    with privates_redis() as erste_url, privates_redis() as zweite_url:
        erste = redis.Redis.from_url(erste_url)
        zweite = redis.Redis.from_url(zweite_url)
        try:
            assert erste.info("server")["run_id"] != zweite.info("server")["run_id"]
            erste.set("sitzungen:testnutzer", "bleibt")
            zweite.set("sitzungen:testnutzer", "fremd")
            # Ein echter zweiter Prozess fuehrt das frueher kollidierende flushdb aus.
            _unterprozess(zweite_url, "import os, redis; redis.Redis.from_url(os.environ['REDIS_URL']).flushdb()")
            assert erste.get("sitzungen:testnutzer") == b"bleibt"
            assert zweite.dbsize() == 0
        finally:
            erste.close()
            zweite.close()


def test_gleicher_store_kollidiert_als_gegenprobe():
    from redis_testdb import privates_redis

    with privates_redis() as url:
        client = redis.Redis.from_url(url)
        try:
            client.set("sitzungen:testnutzer", "bleibt")
            _unterprozess(url, "import os, redis; redis.Redis.from_url(os.environ['REDIS_URL']).flushdb()")
            assert client.get("sitzungen:testnutzer") is None
        finally:
            client.close()


def test_abbruch_hinterlaesst_keinen_store_fuer_den_naechsten_lauf():
    import pytest
    from redis_testdb import privates_redis

    with pytest.raises(RuntimeError, match="Abbruch"):
        with privates_redis() as url:
            client = redis.Redis.from_url(url)
            client.set("sitzungen:testnutzer", "Rest")
            run_id = client.info("server")["run_id"]
            client.close()
            raise RuntimeError("Abbruch")
    with privates_redis() as neue_url:
        client = redis.Redis.from_url(neue_url)
        try:
            assert client.info("server")["run_id"] != run_id
            assert client.dbsize() == 0
        finally:
            client.close()


def test_fehlendes_binary_faellt_nicht_auf_betriebsredis_zurueck(monkeypatch):
    import pytest
    import redis_testdb

    monkeypatch.setattr(redis_testdb.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="nicht als Ersatz"):
        with redis_testdb.privates_redis():
            pytest.fail("Ohne redis-server darf kein Teststore entstehen")


def test_server_und_socket_werden_beim_verlassen_entfernt():
    from pathlib import Path
    from urllib.parse import urlsplit
    import pytest
    from redis_testdb import privates_redis

    with privates_redis() as url:
        socket = Path(urlsplit(url).path)
        client = redis.Redis.from_url(url, socket_timeout=1)
        assert socket.exists()
        assert client.ping()
    try:
        assert not socket.parent.exists()
        with pytest.raises(redis.ConnectionError):
            client.ping()
    finally:
        client.close()


def test_parallele_starts_bekommen_eigene_sockets():
    from threading import Barrier
    from redis_testdb import privates_redis

    barriere = Barrier(2)

    def starten():
        with privates_redis() as url:
            # ZEIT-1: 10 s Rendezvous reichten unter Last nicht (der zweite
            # Thread kam spaeter zur Barriere, beide warteten aufeinander und
            # `privates_redis()` brach beim Verlassen ab). 30 s aendern nur
            # die Wartezeit, nicht die Aussage (zwei eigene Sockets).
            barriere.wait(timeout=30)
            return url

    with ThreadPoolExecutor(max_workers=2) as pool:
        urls = list(pool.map(lambda _: starten(), range(2)))
    assert urls[0] != urls[1]
