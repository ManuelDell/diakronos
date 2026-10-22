"""Privates, nicht persistierendes Redis fuer echte CLI-Unterprozesse (A1c11).

Kein Fallback auf REDIS_URL: der Store des laufenden Stacks ist niemals ein
Teststore. Jeder Kontext startet einen eigenen Server an einem privaten
Unix-Socket, ohne TCP-Port, RDB-Datei oder AOF. Ein harter Prozessabbruch kann
einen Server bis zum Containerende hinterlassen, aber keinen Zustand fuer den
naechsten Lauf: jeder Start bekommt ein neues temporaeres Verzeichnis.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import redis


@contextmanager
def privates_redis():
    executable = shutil.which("redis-server")
    if executable is None:
        raise RuntimeError(
            "CLI-Tests brauchen redis-server; Test-Image neu bauen. "
            "Das Redis des Betriebs wird nicht als Ersatz benutzt."
        )
    # Kurzer Pfad: Unix-Sockets haben unter Linux ein Laengenlimit von 108 Bytes.
    with tempfile.TemporaryDirectory(prefix="dk-redis-") as directory:
        socket = Path(directory) / "redis.sock"
        url = f"unix://{socket}?db=0"
        process = subprocess.Popen(
            [executable, "--port", "0", "--unixsocket", str(socket),
             "--unixsocketperm", "700", "--save", "", "--appendonly", "no",
             "--dir", directory],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )
        client = redis.Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
        try:
            deadline = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Test-Redis beendet (Exitcode {process.returncode})")
                try:
                    if client.ping():
                        break
                except redis.ConnectionError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Test-Redis wird nicht bereit (10 Sekunden)")
                time.sleep(0.02)
            yield url
        finally:
            # Auch bei fehlgeschlagenem Setup/Test beenden; nie SHUTDOWN gegen
            # eine URL aus der Umgebung senden, nur unseren eigenen Prozess.
            client.close()
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
