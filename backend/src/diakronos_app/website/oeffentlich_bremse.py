"""BS-1b — Bremse der oeffentlichen Website-Ausgabe.

Bauform wie ``anmeldung/kontaktbremse.py`` (dasselbe Muster, eigener
Namensraum, eigene Schwellen): ein Zaehler im Redis, gleitendes Fenster,
gesalzener Adressschluessel ohne Klartext, FAIL CLOSED — ist Redis nicht
erreichbar, wird gebremst (der Aufrufer antwortet 429/503), nicht
durchgelassen.

Warum eine EIGENE Bremse und nicht die Kontaktbremse
----------------------------------------------------
Die Kontaktbremse schuetzt ein Postfach (5/Stunde je Adresse, 50/Stunde
gesamt). Die Lese-API wird aber von der WEBSITE aufgerufen — ein Besucher
laedt Termine, Gruppen und Beitraege auf einer Seite, und ein Baustein darf
mehrfach fragen. Eine 5/Stunde-Grenze waere dort ein Ausfall. Kartenvorgabe
L8: „grosszuegig, z. B. 120/min je Adresse“.

Schwellen (Einstellungen, Defaults in Klammern)
-----------------------------------------------
``WEBSITE_OEFFENTLICH_MAX_IP``      Anfragen je Adresse und Fenster (120)
``WEBSITE_OEFFENTLICH_MAX_GESAMT``  Anfragen gesamt je Fenster (0 = aus)
``WEBSITE_OEFFENTLICH_FENSTER_SEKUNDEN``  Fensterlaenge (60)

Die Gesamtgrenze steht auf 0 (= ausdruecklich aus): eine Gemeinde-Website
mit vielen Besuchern hinter einem Proxy haette EINE Adresse, und eine
Gesamtgrenze traefe dann alle. Der Adresszaehler ist hier der richtige
Hebel; wer die Gesamtgrenze will, setzt sie ausdruecklich.
"""

from __future__ import annotations

import hashlib

from diakronos_app.ip_adressen import parse_ip
from diakronos_app.settings import settings

__all__ = [
    "SCHLUESSEL_PRAEFIX",
    "fehlermeldung",
    "pruefe",
    "zaehler_stand",
    "zuruecksetzen",
]

#: Eigener Namensraum: weder Kontakt-, Login- noch Registrierungszaehler.
SCHLUESSEL_PRAEFIX = "diakronos:website-lesen:"
#: Gesamtzaehler (eine Kennung, keine Personendaten).
GESAMT_KEY = f"{SCHLUESSEL_PRAEFIX}gesamt"


def _client():
    """Redis-Client (patchbar fuer Tests, wie ``kontaktbremse._client``)."""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _hash(rohdaten: str) -> str:
    """Gesalzener Schluessel-Anteil einer Adresse — kein Klartext im Keyspace."""
    salz = str(getattr(settings, "secret_key", "") or "")
    return hashlib.sha256(f"{salz}|{rohdaten}".encode()).hexdigest()[:32]


def _max_ip() -> int:
    return max(0, int(getattr(settings, "website_oeffentlich_max_ip", 120)))


def _max_gesamt() -> int:
    return max(0, int(getattr(settings, "website_oeffentlich_max_gesamt", 0)))


def _fenster() -> int:
    return max(
        1, int(getattr(settings, "website_oeffentlich_fenster_sekunden", 60))
    )


def _inkrement(client, key: str, grenze: int) -> bool:
    """Ein Fenster-Zaehler: True, wenn der Aufruf noch erlaubt ist.

    ``INCR`` + ``EXPIRE … NX`` in einer Transaktion: ein bestehender Ablauf
    bleibt unveraendert, Dauerlast verlaengert das Fenster also nicht.
    """
    if grenze <= 0:
        return True
    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, _fenster(), nx=True)
    anzahl, _ = pipe.execute()
    return int(anzahl) <= grenze


def pruefe(ip: str | None, client=None) -> tuple[bool, str]:
    """Prueft die Bremse fuer EINEN Leseaufruf: ``(erlaubt, grund)``.

    ``grund`` ist ``"ip"`` oder ``"gesamt"`` und dient der internen
    Diagnose/Logzeile, NICHT der Anzeige — nach aussen geht
    :func:`fehlermeldung`. Beide Zaehler werden mitgezaehlt, auch wenn einer
    schon abgelehnt hat.
    """
    client = client or _client()
    erlaubt = True
    grund = ""

    if not _inkrement(client, GESAMT_KEY, _max_gesamt()):
        erlaubt, grund = False, "gesamt"

    if _max_ip() > 0:
        adresse = parse_ip(ip)
        key = f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(adresse))}"
        if not _inkrement(client, key, _max_ip()) and erlaubt:
            erlaubt, grund = False, "ip"

    return erlaubt, grund


def zaehler_stand(ip: str | None, client=None) -> dict[str, int]:
    """Liest beide Zaehler OHNE sie zu veraendern (Tests/Diagnose)."""
    client = client or _client()
    adresse = parse_ip(ip)
    stand = {
        "ip": int(
            client.get(f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(adresse))}") or 0
        ),
        "gesamt": int(client.get(GESAMT_KEY) or 0),
    }
    return stand


def zuruecksetzen(client=None) -> None:
    """Loescht beide Zaehler — fuer Tests; im Betrieb laeuft das Fenster ab."""
    client = client or _client()
    client.delete(GESAMT_KEY)


def fehlermeldung() -> str:
    """Verstaendlicher Satz fuer eine gebremste Anfrage (keine Interna)."""
    return (
        "Es sind gerade zu viele Anfragen eingegangen. Bitte versuche es in "
        "einer Minute erneut."
    )
