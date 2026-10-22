"""A1c11: echte Redis-Stores bleiben auch zwischen Testprozessen getrennt."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import redis

from test_a1c6_cli_entsperren import echt_stores


def test_cli_store_ist_nicht_die_redis_instanz_des_betriebs(echt_stores):
    from diakronos_app.settings import settings

    betrieb = redis.Redis.from_url(settings.redis_url)
    try:
        assert echt_stores.info("server")["run_id"] != betrieb.info("server")["run_id"]
    finally:
        betrieb.close()


def _unterprozess(url, code):
    env = {**os.environ, "REDIS_URL": url}
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True,
        text=True, timeout=10,
    )
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
            barriere.wait(timeout=10)
            return url

    with ThreadPoolExecutor(max_workers=2) as pool:
        urls = list(pool.map(lambda _: starten(), range(2)))
    assert urls[0] != urls[1]
