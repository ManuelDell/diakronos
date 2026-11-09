"""Privates, nicht persistierendes Redis fuer echte CLI-Unterprozesse (A1c11).

Kein Fallback auf REDIS_URL: der Store des laufenden Stacks ist niemals ein
Teststore. Jeder Kontext startet einen eigenen Server an einem privaten
Unix-Socket, ohne TCP-Port, RDB-Datei oder AOF. Ein harter Prozessabbruch kann
einen Server bis zum Containerende hinterlassen, aber keinen Zustand fuer den
naechsten Lauf: jeder Start bekommt ein neues temporaeres Verzeichnis.

Warum der Store auch in `settings.redis_url` steht: `erstelle_app()` reicht die
URL EINMAL an die Middleware weiter; jeder andere Zugriff liest sie frisch.
Ohne den Eintrag baut ein Test eine App gegen den Betriebs-Namen
(`redis:6379`), und jede Anfrage mit Bremse (Kontaktformular) antwortet 503 —
je nachdem, ob ein frueherer Test schon eine App gebaut hat (TEST-ISO1). Der
Betriebs-Wert kommt beim Verlassen zurueck.
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
            # TEST-ISO1 (08.11.): `settings.redis_url` MUSS auf diesen Store
            # zeigen. Die Frueh-Fassung liess den Betriebswert stehen
            # (Default `redis://redis:6379/0`); prozessweit war das
            # folgenlos, weil jeder Redis-Zugriff die Einstellung frisch
            # liest. Fuer `erstelle_app()` ist es das nicht: die Middleware
            # bekommt die URL EINMAL beim Aufbau gereicht und behaelt sie.
            # Nach einem solchen Aufbau lief jede Anfrage, die die Bremse
            # benutzt (Kontaktformular), gegen einen Namen, den es in der
            # Testumgebung nicht gibt — 503, abhaengig davon, ob ein
            # frueherer Test schon eine App gebaut hatte.
            #
            # `settings` ist pydantic: `object.__setattr__` schreibt ohne
            # Validierung, der alte Wert kommt beim Verlassen zurueck.
            #
            # A1c11 bleibt unberuehrt: der Betriebs-Store ist der Wert VOR
            # diesem Kontext (in der Suite der des Betriebs), und genau den
            # vergleicht `test_cli_store_ist_nicht_die_redis_instanz_des_betriebs`
            # mit dem privaten Server — beide bleiben verschieden.
            from diakronos_app.settings import settings

            vorher = settings.redis_url
            object.__setattr__(settings, "redis_url", url)
            try:
                yield url
            finally:
                object.__setattr__(settings, "redis_url", vorher)
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
