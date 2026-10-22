"""In-Memory-Redis-Stub fuer Sitzungs-Tests — Karte A1b1.

Die Vorarbeit hat gemeldet: `conftest.py` patcht
`query`/`db`/`doc`/`router`, aber **Redis nicht** — damit waeren Sitzungs-Tests
nicht isoliert. Genau das loest dieses Modul.

Bewusst KEIN `fakeredis` als neue Abhaengigkeit (selfhoster-Image): die
Sitzungs-Schicht benutzt nur eine Handvoll Kommandos, die hier exakt und
nachvollziehbar nachgebaut sind. Das ist ehrlicher als ein Paket fuer
Funktionen, die der Test nicht ausuebt.

Unterstuetzt: GET, SET(ex), EXISTS, DELETE, EXPIRE, SADD, SREM, SMEMBERS,
PIPELINE. Alles andere wirft laut — ein Test, der etwas anderes braucht, soll
das melden und nicht still falsch laufen.
"""

from __future__ import annotations

import time
from typing import Any


def _trifft(text: str, muster: str) -> bool:
    """Trifft `text` auf ein Redis-`SCAN`-Muster?

    Redis matcht Glob, nicht Regex, und im Store wird genau ein Muster
    benutzt: `<praefix>*`. `fnmatch` bildet `*`, `?` und `[…]` so ab, wie
    Redis es tut — `fnmatch` ist case-insistent auf Windows-artigen
    Plattformen, deshalb wird ueber `fnmatchcase` verglichen, damit der
    Test auf jedem Rechner dasselbe sagt wie der Store.
    """
    from fnmatch import fnmatchcase

    return fnmatchcase(text, muster)


class StubPipeline:
    """Sammelt Kommandos und fuehrt sie beim Verlassen des Kontexts aus.

    `redis.pipeline()` gibt hier ein Objekt zurueck, das die Kommandos
    puffert und bei `execute()` in einem Rutsch ausfuehrt — genau wie der
    echte Client mit `transaction=True`.
    """

    def __init__(self, store: "StubRedis") -> None:
        self._store = store
        self._ops: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        method = getattr(self._store, name)

        def _collect(*args, **kwargs):
            self._ops.append((method.__name__, args, kwargs))
            return self

        return _collect

    def execute(self) -> list[Any]:
        results = [getattr(self._store, name)(*args, **kwargs) for name, args, kwargs in self._ops]
        self._ops.clear()
        return results


class StubRedis:
    """Minimaler Redis-Ersatz mit TTL-Semantik."""

    def __init__(self) -> None:
        # key -> (value, ablaufzeitpunkt oder None)
        self._values: dict[str, tuple[Any, float | None]] = {}
        self._sets: dict[str, set[str]] = {}
        self._ttl: dict[str, float | None] = {}

    # ── interne Helfer ──────────────────────────────────────────────────
    def _abgelaufen(self, key: str) -> bool:
        deadline = self._ttl.get(key)
        if deadline is not None and deadline <= time.monotonic():
            self._values.pop(key, None)
            self._sets.pop(key, None)
            self._ttl.pop(key, None)
            return True
        return False

    def _roh(self, key: str) -> Any:
        self._abgelaufen(key)
        if key in self._values:
            return self._values[key][0]
        return None

    # ── Kommandos ───────────────────────────────────────────────────────
    def get(self, key: str) -> Any:
        return self._roh(key)

    def getdel(self, key: str) -> Any:
        """Wert holen UND loeschen — Redis-`GETDEL`, atomar.

        Der Produktivcode `anmeldung/transaktionen.py` entnimmt den
        OIDC-`state` damit in einem Schritt. Der Stub braucht die Form, damit
        der Atomaritaets-Test denselben Weg geht wie der Betrieb (sonst
        testete er den Rueckfall statt des echten Kommandos).
        """
        wert = self._roh(key)
        if wert is None:
            return None
        self._values.pop(key, None)
        self._sets.pop(key, None)
        self._ttl.pop(key, None)
        return wert

    def set(self, key: str, value: Any, ex: int | None = None,
            nx: bool = False, px: int | None = None) -> bool:
        """``SET``; mit ``nx`` nur, wenn der Schluessel fehlt (BACKUP-1).

        ``nx``/``px`` sind echte Redis-Optionen: ``SET key value NX PX <ms>``
        ist das atomare "Sperre setzen" und wird von der Sicherungssperre
        (BACKUP-1) gebraucht. Ohne sie muesste der Test einen anderen Weg
        gehen als der Betrieb — genau das soll er nicht.
        """
        if nx and self.exists(key):
            return False
        ttl = px / 1000 if px is not None else ex
        self._values[key] = (value, time.monotonic() + ttl if ttl else None)
        self._ttl[key] = time.monotonic() + ttl if ttl else None
        return True

    def exists(self, key: str) -> int:
        if self._abgelaufen(key):
            return 0
        return 1 if (key in self._values or key in self._sets) else 0

    def delete(self, *keys: str) -> int:
        entfernt = 0
        for key in keys:
            if self._abgelaufen(key):
                continue
            if key in self._values or key in self._sets:
                self._values.pop(key, None)
                self._sets.pop(key, None)
                self._ttl.pop(key, None)
                entfernt += 1
        return entfernt

    def expire(self, key: str, sekunden: int, nx: bool = False) -> bool:
        if not self.exists(key):
            return False
        if nx and self._ttl.get(key) is not None:
            return False
        self._ttl[key] = time.monotonic() + sekunden
        return True

    def incr(self, key: str, menge: int = 1) -> int:
        """Zaehler hochzaehlen; legt den Schluessel bei 0 an.

        Redis-Semantik: `INCR` erzeugt den Key, wenn er fehlt, und behandelt
        einen nicht-numerischen Wert als 0. Beides bildet der Stub so nach,
        damit die Loginversuche-Zaehler (A1c1) getestet werden koennen, ohne
        einen zweiten Redis zu brauchen.
        """
        roh = self._roh(key)
        try:
            wert = int(roh)
        except (TypeError, ValueError):
            wert = 0
        wert += menge
        self._values[key] = (wert, self._ttl.get(key))
        self._ttl.setdefault(key, None)
        return wert

    def ttl(self, key: str) -> int:
        """Restlaufzeit in Sekunden: -2 fehlt, -1 ohne TTL, sonst >= 0."""
        if self._abgelaufen(key):
            return -2
        if key not in self._values and key not in self._sets:
            return -2
        deadline = self._ttl.get(key)
        if deadline is None:
            return -1
        return int(max(0.0, deadline - time.monotonic()))

    def sadd(self, key: str, *werte: str) -> int:
        self._abgelaufen(key)
        menge = self._sets.setdefault(key, set())
        vorher = len(menge)
        menge.update(str(w) for w in werte)
        return len(menge) - vorher

    def srem(self, key: str, *werte: str) -> int:
        self._abgelaufen(key)
        menge = self._sets.get(key)
        if not menge:
            return 0
        entfernt = 0
        for wert in werte:
            if wert in menge:
                menge.discard(wert)
                entfernt += 1
        return entfernt

    def smembers(self, key: str) -> set[str]:
        self._abgelaufen(key)
        return set(self._sets.get(key, set()))

    def scan_iter(self, match: str | None = None, count: int | None = None):
        """Namespaced SCAN — wie der echte Client, als Generator.

        Gebraucht von `zaehle_gesperrte_ips()` und `zaehle_adressen_im_weg()`
        (A1c6/A1c8): beide fragen den Store ab, **statt** einen Schluessel
        vorauszusagen. Das ist der Unterschied zwischen "ich habe
        nachgesehen" und "ich weiss es" — und genau darum geht es in diesen
        Funktionen.

        Nur `SCAN`-Hirschhorn wird unterstuetzt (`*`, `?`, `[...]`), weil das
        alles ist, was der Store braucht. Alles andere wirft laut: ein Test,
        der etwas anderes braucht, soll das melden und nicht still falsch
        laufen. Genau das ist der Grundsatz dieses Stubs.

        Der Schluessel wird **dekodiert**, bevor verglichen wird: der echte
        Client liefert je nach `decode_responses` `str` oder `bytes`. Ein
        Stub, der immer `str` liefert, wuerde die `bytes`-Haelfte des
        Vergleichs (`.decode()` im Produktivcode) stillschweigend ungetestet
        lassen — dieser Fehler ist im Keyspace schon einmal passiert
        (`zaehle_gesperrte_ips` zaehlte die Backoff-Stufe mit).
        """
        for key in list(self._values) + list(self._sets):
            self._abgelaufen(key)
            text = key.decode() if isinstance(key, bytes) else str(key)
            if match is None or _trifft(text, match):
                yield text

    def pipeline(self, transaction: bool = True) -> StubPipeline:
        return StubPipeline(self)

    def flushall(self) -> bool:
        self._values.clear()
        self._sets.clear()
        self._ttl.clear()
        return True

    def ping(self) -> bool:
        return True
