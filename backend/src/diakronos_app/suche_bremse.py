"""Ratenbegrenzung der globalen Suche (UX3g, Befehlspalette).

Die Palette fragt bei jedem Tastendruck (die SPA entprellt, aber ein Skript
nicht). Jeder Aufruf loest sieben Abfragen ueber die halbe Datenbank aus —
ohne Grenze ist das ein bequemer Weg, den Server zu beschaeftigen und ueber
die Trefferzahl Datenbestand abzutasten.

BAUFORM: dieselbe wie `anmeldung/registrierungsbremse.py` — ein fester
Fensterzaehler in Redis (`INCR` + `EXPIRE NX` in einer Transaktion), Schluessel
OHNE Klartext (gesalzener SHA-256 des Benutzernamens). Kein Backoff, weil hier
kein Geheimnis geraten wird: begrenzt wird die MENGE, nicht ein Passwort.

    diakronos:suche:<hash>    -> "41"    (Aufrufe im Fenster)

FENSTER UND GRENZE kommen aus `settings` (`SUCHE_MAX`, `SUCHE_FENSTER_SEKUNDEN`),
damit der Betrieb sie ohne Codeaenderung setzen kann. `SUCHE_MAX = 0` schaltet
die Bremse ausdruecklich ab — der Default ist die Grenze, nicht das Nichts.

FAIL CLOSED, aber nicht spuerbar: faellt Redis aus, wird gebremst (True =
kein weiterer Aufruf). Die Palette zeigt dann „zu viele Anfragen“ statt
Treffer — ein stiller Weiterlauf waere der schlechtere Fehler, weil er die
teuerste Abfrage der App unbegrenzt offen liesse.

PRO BENUTZER, NICHT PRO ADRESSE: hinter einem Proxy teilen sich alle
Gemeindeglieder eine Adresse; eine Adressgrenze traefe alle gemeinsam. Der
angemeldete Name ist hier die richtige Kennung — und anonym kommt niemand
durch (`allow_guest=False`).
"""

from __future__ import annotations

import hashlib
import logging

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.suche.bremse")

__all__ = ["SCHLUESSEL_PRAEFIX", "bremse", "zaehler_stand"]

#: Eigener Namensraum — kollidiert weder mit Login- noch Registrierungszaehlern.
SCHLUESSEL_PRAEFIX = "diakronos:suche:"


class Bremse:
    """Ein Fensterzaehler je Benutzer (Redis). Kleine Klasse statt Modulzustand,
    damit Tests sie mit eigenem Client instanziieren koennen."""

    def __init__(self, client_factory=None):
        self._client_factory = client_factory or _client

    def _client(self):
        return self._client_factory()

    def schluessel(self, user: str) -> str:
        salz = str(getattr(settings, "secret_key", "") or "")
        kennung = hashlib.sha256(f"{salz}|{user}".encode()).hexdigest()[:32]
        return f"{SCHLUESSEL_PRAEFIX}{kennung}"

    def pruefe(self, user: str) -> bool:
        """True, wenn der Aufruf noch erlaubt ist. Zaehlt den Aufruf mit."""
        grenze = max(0, int(getattr(settings, "suche_max", 0)))
        if grenze <= 0:
            return True
        fenster = max(1, int(getattr(settings, "suche_fenster_sekunden", 60)))

        from redis.exceptions import RedisError

        try:
            client = self._client()
            pipe = client.pipeline(transaction=True)
            pipe.incr(self.schluessel(user))
            pipe.expire(self.schluessel(user), fenster, nx=True)
            anzahl, _ = pipe.execute()
        except RedisError:
            # Fail closed: eine kaputte Zaehlung darf die teuerste Abfrage der
            # App nicht oeffnen. Kein interner Text nach aussen.
            logger.warning("suche: Redis-Bremse nicht erreichbar — gebremst")
            return False
        return int(anzahl) <= grenze

    def pruefe_oder_werfen(self, user: str) -> None:
        """Bremse mit der vertraeglichen Meldung des Hauses (429)."""
        from diakronos_app.frappe_compat.exceptions import RateLimitError, throw

        if not self.pruefe(user):
            throw(
                "Es sind gerade zu viele Suchanfragen eingegangen. "
                "Bitte warte einen Moment und tippe weiter.",
                RateLimitError,
            )

    def zaehler_stand(self, user: str) -> int:
        """Liest den Zaehler OHNE ihn zu veraendern (Tests/Diagnose)."""
        from redis.exceptions import RedisError

        try:
            return int(self._client().get(self.schluessel(user)) or 0)
        except RedisError:
            return -1


def _client():
    """Redis-Client (patchbar fuer Tests, wie `loginversuche._client`)."""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


#: Die eine Instanz der App. Tests patchen `_client_factory` bzw. bauen sich
#: eine eigene `Bremse`.
bremse = Bremse()


def zaehler_stand(user: str) -> int:
    return bremse.zaehler_stand(user)
