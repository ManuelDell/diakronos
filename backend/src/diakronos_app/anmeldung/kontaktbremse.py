"""WEB-10 — Datenschicht der Ratenbegrenzung des OEFFENTLICHEN Kontaktformulars.

Warum eine eigene Datenschicht und nicht die Registrierungsbremse
----------------------------------------------------------------
Die Registrierungsbremse (`anmeldung/registrierungsbremse.py`) schuetzt das
ANMELDEN: ihre Fenster und Schwellen sind auf Links und Tokenpruefungen
zugeschnitten. Das Kontaktformular hat einen anderen Gegenstand — es sendet
eine E-Mail an die Gemeinde, und zwar ohne Sitzung und ohne Link. Zwei
Zaehler, dieselbe Bauform wie dort, aber ein eigener Namensraum und eigene
Schwellen (Karte WEB-10, K3: je Adresse 5/Stunde, global 50/Stunde).

Schluesselraum (Redis) — ohne Klartext:

    diakronos:kontakt-versuche:ip:<sha256>     -> "3"   (Anfragen je Adresse)
    diakronos:kontakt-versuche:gesamt          -> "17"  (Anfragen gesamt)

Die Adresskennung laeuft durch denselben gesalzenen Hash wie die Loginbremse
(`settings.secret_key`): wer den Keyspace liest, sieht keine Adressen.

WARUM ES DEN GESAMTZAEHLER GEBEN MUSS
-------------------------------------
Der Adresszaehler allein ist hinter einem Reverse-Proxy wirkungslos: dort
sieht die App fuer ALLE Besucher dieselbe (private) Adresse. Waere er der
einzige Zaehler, waere die Bremse mit einem Besucher im Foyer oder einem
einzigen Bot aufgebraucht — oder, bei Befreiung privater Adressen (wie in der
Loginbremse), voellig aus. Das Gesamtfenster ist die Grenze, die unabhaengig
davon greift: 50 Mails pro Stunde an die Gemeinde sind im Normalfall weit
ueber jedem echten Aufkommen (eine Gemeinde bekommt einzelne Anfragen), fuer
einen Flutangriff aber die entscheidende Schwelle.

Die Adressgrenze (5/Stunde) schuetzt zusaetzlich davor, dass EIN Absender das
Gemeindepostfach fuellt. Ausgenommen ist genau Loopback (`127.0.0.1`/`::1`) —
dort steht der Proxy, eine Adresssperre traefe alle (Begruendung in
`_ist_ausgenommen`). Private LAN-Adressen werden MITGEZAEHLT: ein Bot im Netz
soll die Adressgrenze treffen, statt sie durch "ist privat" zu umgehen.
Die Gesamtgrenze gilt immer.

FENSTER. `INCR` und `EXPIRE NX` laufen in einer Redis-Transaktion: ein
bestehender Ablauf bleibt unveraendert, Dauerlast verlaengert das Fenster
also nicht. `0` als Schwelle heisst ausdruecklich "unbegrenzt" — der Default
ist die Grenze, nicht das Nichts.

FAIL CLOSED. Ist Redis nicht erreichbar, wird NICHT gesendet (der Aufrufer
antwortet 503 ueber `RateLimitError`): lieber eine Mail weniger als ein
ungebremstes Postfach. Die Meldung nennt keine Interna.
"""

from __future__ import annotations

import hashlib

from diakronos_app.ip_adressen import parse_ip
from diakronos_app.settings import settings

__all__ = [
    "SCHLUESSEL_PRAEFIX",
    "GESAMT_KEY",
    "pruefe",
    "zaehler_stand",
    "zuruecksetzen",
    "fehlermeldung",
]

# Eigener Namensraum: weder Login-, CalDAV- noch Registrierungszaehler.
SCHLUESSEL_PRAEFIX = "diakronos:kontakt-versuche:"

# Der Gesamtzaehler (eine Kennung, kein Hash — er traegt keine Personendaten).
GESAMT_KEY = f"{SCHLUESSEL_PRAEFIX}gesamt"


def _client():
    """Redis-Client (patchbar fuer Tests, wie `loginversuche._client`)."""
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _hash(rohdaten: str) -> str:
    """Gesalzener Schluessel-Anteil einer Adresse — kein Klartext im Keyspace."""
    salz = str(getattr(settings, "secret_key", "") or "")
    return hashlib.sha256(f"{salz}|{rohdaten}".encode()).hexdigest()[:32]


def _max_ip() -> int:
    return max(0, int(getattr(settings, "website_kontakt_max_ip", 5)))


def _max_gesamt() -> int:
    return max(0, int(getattr(settings, "website_kontakt_max_gesamt", 50)))


def _fenster() -> int:
    return max(1, int(getattr(settings, "website_kontakt_fenster_sekunden", 3600)))


def _ist_ausgenommen(ip: str | None) -> bool:
    """Befreit eine Adresse vom ADRESS-Zaehler? (nur 127.0.0.1/::1)

    ACHTUNG — diese Ausnahme ist ABSICHTLICH eng und wird nicht erweitert,
    ohne den Gesamtzaehler zu betrachten: sie nimmt nur den Server selbst aus
    (Loopback), nicht das LAN.

    WARUM NUR LOOPBACK — und nicht (wie in der Loginbremse) alle eigenen
    Netze: das Postfach der Gemeinde ist ein anderes Gut als ein Konto. Ein
    Bot im LAN (private Adresse), der das Formular flutet, laesst sich an der
    Adresse nicht von einer Besucherin hinter demselben NAT unterscheiden —
    die GESAMTgrenze faengt ihn. Loopback aber heisst: die Anfrage kommt von
    DIESEM Server (Proxy/Vorgang), also nicht von der Besucherin; eine
    Adresssperre dort traefe nur den Proxy und damit alle. Deshalb ist genau
    `127.0.0.1`/`::1` ausgenommen — nicht `X-Forwarded-For`, das jemand
    behaupten kann.
    """
    adresse = parse_ip(ip)
    if adresse is None:
        return False
    return str(adresse) in ("127.0.0.1", "::1")


def _inkrement(client, key: str, grenze: int) -> bool:
    """Ein Fenster-Zaehler: True, wenn der Versuch noch erlaubt ist.

    `INCR` + `EXPIRE ... NX` in einer Transaktion. NX setzt den Ablauf nur,
    wenn noch keiner besteht (Redis >= 7, wie im Compose-Stack) — ein
    Dauerlauf verschiebt das Fenster damit nicht.
    """
    if grenze <= 0:
        return True
    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, _fenster(), nx=True)
    anzahl, _ = pipe.execute()
    return int(anzahl) <= grenze


def pruefe(ip: str | None, client=None) -> tuple[bool, str]:
    """Prueft die Bremse fuer EINE Kontaktanfrage. **ABNAHMESCHNITTSTELLE.**

    Rueckgabe `(erlaubt, grund)` — `grund` ist `"ip"` oder `"gesamt"` und
    dient der internen Diagnose/Logzeile, NICHT der Anzeige (nach aussen geht
    `fehlermeldung()`, damit ein Angreifer nicht erfaehrt, welcher Zaehler
    gegriffen hat).

    Beide Zaehler werden mitgezaehlt, auch wenn einer schon abgelehnt hat:
    sonst waere die Gesamtgrenze mit wechselnden Adressen umgehbar.
    """
    client = client or _client()
    erlaubt = True
    grund = ""

    # Gesamt zuerst und IMMER: die Grenze, die auch hinter Proxy/NAT greift.
    if not _inkrement(client, GESAMT_KEY, _max_gesamt()):
        erlaubt, grund = False, "gesamt"

    if not _ist_ausgenommen(ip):
        adresse = parse_ip(ip)
        key = f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(adresse))}"
        if not _inkrement(client, key, _max_ip()) and erlaubt:
            erlaubt, grund = False, "ip"

    return erlaubt, grund


def zaehler_stand(ip: str | None, client=None) -> dict[str, int]:
    """Liest beide Zaehler OHNE sie zu veraendern. Fuer Tests/Diagnose.

    Enthaelt bewusst keine Kennung — wer das in ein Log schreibt, hat weder
    Adressen noch Schluessel ausgegeben.
    """
    client = client or _client()
    stand = {"ip": 0, "gesamt": 0}
    adresse = parse_ip(ip)
    if adresse is not None and not _ist_ausgenommen(ip):
        stand["ip"] = int(
            client.get(f"{SCHLUESSEL_PRAEFIX}ip:{_hash(str(adresse))}") or 0
        )
    stand["gesamt"] = int(client.get(GESAMT_KEY) or 0)
    return stand


def zuruecksetzen(client=None) -> None:
    """Loescht beide Zaehler — fuer Tests und den Notfall (Neustart des Fensters).

    NICHT Teil des Anfragepfads: im Betrieb laeuft das Fenster ueber die TTL ab.
    """
    client = client or _client()
    client.delete(GESAMT_KEY)


def fehlermeldung() -> str:
    """Verstaendlicher Satz fuer eine gebremste Anfrage (kein Fachjargon).

    Bewusst dieselbe Meldung fuer beide Grenzen — welcher Zaehler gegriffen
    hat, ist eine interne Diagnose.
    """
    return (
        "Es sind gerade zu viele Anfragen eingegangen. Bitte versuche es in "
        "ein paar Minuten erneut."
    )
