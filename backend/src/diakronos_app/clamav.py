"""DATEIEN-6 — Virenpruefung ueber ClamAV (clamd INSTREAM), fail-closed.

Der Haken ``ablage.pruefe_inhalt`` (F7, Manuel 23.11.) ruft GENAU EINE
Funktion dieses Moduls: ``pruefe(roh, name)``. Alles andere hier ist Zubehoer
(Ziel lesen, Protokoll sprechen, Meldungen).

Vertrag (Karte DATEIEN-6, Abschnitt 2):

* ``CLAMAV_HOST`` **leer** → No-Op. Entwicklung/Tests laufen ohne Dienst; beim
  ersten Upload steht EINE Protokollzeile „Virenpruefung aus“.
* ``CLAMAV_HOST`` gesetzt, Dienst **nicht erreichbar** / Zeitueberschreitung /
  Protokollfehler / unerwartete Antwort → **fail-closed**: ``ValidationError``
  „Die Datei konnte gerade nicht geprueft werden. Bitte spaeter erneut
  versuchen.“ + ``logger.error``. Ein Upload ohne Pruefung geht NICHT durch —
  sonst waere die Pruefung mit einem Port-Schliessen abschaltbar.
* Fund (``FOUND``) → ``ValidationError`` „Die Datei wurde abgewiesen, weil sie
  Schadsoftware enthalten koennte.“ + ``logger.warning`` mit dem
  SIGNATURNAMEN (nur im Protokoll, nie in der Meldung an den Benutzer).

Protokoll: clamd-INSTREAM ueber TCP, von Hand mit ``socket`` — KEINE neue
Abhaengigkeit (die Karte verlangt es ausdruecklich). Ablauf:

    zINSTREAM\\0                      (Befehl)
    <4 Byte Laenge, Netzwerkordnung> <Daten>   ... je Block
    <4 Byte 0>                       (Ende)

clamd antwortet EINE Zeile: ``stream: OK``, ``stream: <Signatur> FOUND`` oder
``... ERROR``.

Grenzen: ``CLAMAV_PORT`` (3310), Zeitlimit ``CLAMAV_ZEITLIMIT_SEKUNDEN`` (15)
und ``StreamMaxLength`` (hier 64 MiB, siehe ``CLAMD_CONF_StreamMaxLength`` in ``compose/stack.yml``).
Eine Datei, die clamd ohnehin nicht pruefen will, wird GAR NICHT erst
geschickt — sie gilt wie ein Protokollfehler (fail-closed), denn „zu gross fuer
clamd“ heisst nicht „sauber“. Die eigene Upload-Grenze der App liegt bei
hoechstens 50 MB (``ANHANG_MAX_MB_GRENZE``); ``StreamMaxLength`` ist der
Rueckfall, falls sie je angehoben wird.
"""

from __future__ import annotations

import logging
import socket
import struct
from dataclasses import dataclass

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.settings import get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "BLOCKGROESSE",
    "MELDUNG_FEHLER",
    "MELDUNG_FUND",
    "STANDARD_PORT",
    "STANDARD_ZEITLIMIT_SEKUNDEN",
    "STREAM_MAX_LENGTH",
    "Ziel",
    "deute_antwort",
    "pruefe",
    "ziel",
]

#: Ein Block je INSTREAM-Rahmen. 64 KiB ist die uebliche Groesse; klein genug,
#: um nicht viel Speicher zu doppeln, gross genug fuer wenige Rahmen je Datei.
BLOCKGROESSE = 64 * 1024

#: clamd hoert auf 3310, wenn nichts anderes gesagt wird.
STANDARD_PORT = 3310

#: Zeitlimit fuer Verbindung UND Antwort zusammen (Sekunden). Bewusst knapp:
#: der Aufruf blockiert synchron einen Uvicorn-Arbeiter, und clamd antwortet
#: im Normalfall in Millisekunden.
STANDARD_ZEITLIMIT_SEKUNDEN = 15.0

#: ``StreamMaxLength`` unserer clamd-Konfiguration (``CLAMD_CONF_StreamMaxLength`` in ``compose/stack.yml``,
#: 64 MiB): groessere Daten nimmt der Dienst gar nicht an. Wird hier GEPRUEFT,
#: damit klar ist, warum ein Upload abgewiesen wurde. Die hoechste
#: Upload-Grenze der App ist 50 MB (``ANHANG_MAX_MB_GRENZE``).
STREAM_MAX_LENGTH = 64 * 1024 * 1024

#: Menschen-Meldungen — EINE Wahrheit je Fall (die Aufrufer uebersetzen nichts).
MELDUNG_FUND = "Die Datei wurde abgewiesen, weil sie Schadsoftware enthalten könnte."
MELDUNG_FEHLER = "Die Datei konnte gerade nicht geprüft werden. Bitte später erneut versuchen."


@dataclass(frozen=True)
class Ziel:
    """Wohin gesprochen wird (aus ``settings``, nicht aus der Umgebung direkt)."""

    host: str
    port: int
    zeitlimit: float


def ziel() -> Ziel | None:
    """Das Pruefziel aus den Einstellungen — ``None`` heisst: Pruefung AUS.

    Gelesen wird ueber ``settings.get_settings()`` (dieselbe Fassung, die der
    Rest der App benutzt), nicht ueber ``os.environ``: so kommen auch die
    ``.env``-Werte an, und ein Test kann die Umgebung mit ``neu_laden()``
    umstellen. Ein unbrauchbarer Port/ein unbrauchbares Zeitlimit wird auf den
    Standard gezogen statt den Upload scheitern zu lassen — die PRUEFUNG
    bleibt dabei scharf (fail-closed).
    """
    s = get_settings()
    host = str(getattr(s, "clamav_host", "") or "").strip()
    if not host:
        return None
    try:
        port = int(getattr(s, "clamav_port", STANDARD_PORT))
    except (TypeError, ValueError):
        port = STANDARD_PORT
    if not 1 <= port <= 65535:
        port = STANDARD_PORT
    try:
        zeitlimit = float(getattr(s, "clamav_zeitlimit_sekunden",
                                  STANDARD_ZEITLIMIT_SEKUNDEN))
    except (TypeError, ValueError):
        zeitlimit = STANDARD_ZEITLIMIT_SEKUNDEN
    if zeitlimit <= 0:
        zeitlimit = STANDARD_ZEITLIMIT_SEKUNDEN
    return Ziel(host=host, port=port, zeitlimit=zeitlimit)


def deute_antwort(zeile: bytes | str) -> tuple[str, str]:
    """Eine Antwortzeile von clamd lesen — ``(``ok``|``fund``|``fehler``, name)``.

    ``stream: OK`` → ``("ok", "")``;
    ``stream: Eicar-Test-Signature FOUND`` → ``("fund", "Eicar-Test-Signature")``;
    alles andere (``... ERROR``, leer, Muell) → ``("fehler", <Zeile>)``.
    Streng, weil die Zeile die EINZIGE Auskunft ist: ein Praefix-Vergleich
    „nicht FOUND also sauber“ waere offen fuer jede fremde Antwort.
    """
    text = zeile.decode("utf-8", "replace") if isinstance(zeile, bytes) else str(zeile)
    text = text.strip().rstrip("\x00")
    if text.endswith("OK") and (text == "OK" or text.endswith(": OK")):
        return "ok", ""
    if text.endswith("FOUND"):
        rumpf = text[: -len("FOUND")].rstrip()
        if ":" in rumpf:
            rumpf = rumpf.split(":", 1)[1]
        return "fund", rumpf.strip()
    return "fehler", text


def pruefe(roh: bytes, name: str | None = None) -> None:
    """Die Bytes durch clamd schicken — ``None`` = sauber, sonst ``ValidationError``.

    ``name`` wird NUR fuer das Protokoll benutzt (Fund: welcher Dateiname);
    der Signaturname steht NIE in der Meldung an den Benutzer, und der Name
    des Uploads auch nicht (er ist Eingabe des Absenders).

    Jeder Weg ausser „clamd sagt OK“ endet in einer ``ValidationError``: das
    ist die Signatur-Zusage an ``ablage.pruefe_inhalt`` (Karte DATEIEN-2).
    """
    z = ziel()
    if z is None:
        _melde_aus()
        return None
    daten = bytes(roh or b"")
    if len(daten) > STREAM_MAX_LENGTH:
        # Nicht pruefbar (clamd nimmt es nicht an) — also nicht durchlassen.
        logger.error(
            "Virenpruefung: Datei groesser als StreamMaxLength (%d Byte) — "
            "clamd kann sie nicht pruefen, Upload abgewiesen", len(daten),
        )
        raise ValidationError(MELDUNG_FEHLER)
    try:
        antwort = _instream(z, daten)
    except (OSError, socket.timeout, ValueError) as fehler:
        # Fail-closed: nicht erreichbar, zu langsam, Verbindung mitten im
        # Schreiben zu, unlesbare Antwort. Kein Pfad, kein Inhalt im Log.
        logger.error(
            "Virenpruefung nicht moeglich (%s:%s): %s — Upload abgewiesen",
            z.host, z.port, type(fehler).__name__,
        )
        raise ValidationError(MELDUNG_FEHLER) from None
    art, wert = deute_antwort(antwort)
    if art == "ok":
        return None
    if art == "fund":
        # Der Signaturname gehoert ins Protokoll — fuer die Nachvollziehbarkeit
        # im Betrieb —, NICHT in die Antwort an den Browser.
        logger.warning("Virenpruefung: Schadsoftware gefunden (%s) in %r",
                       wert or "unbenannt", name)
        raise ValidationError(MELDUNG_FUND)
    logger.error("Virenpruefung: unerwartete Antwort von clamd: %r — Upload abgewiesen",
                 wert[:200])
    raise ValidationError(MELDUNG_FEHLER)


_aus_gemeldet = False


def _melde_aus() -> None:
    """Einmal je Prozess „Virenpruefung aus“ protokollieren (nicht je Upload)."""
    global _aus_gemeldet
    if not _aus_gemeldet:
        _aus_gemeldet = True
        logger.warning("Virenpruefung aus (CLAMAV_HOST nicht gesetzt)")


def _instream(z: Ziel, daten: bytes) -> bytes:
    """INSTREAM sprechen und EINE Antwortzeile zurueckgeben.

    Lebt genau so lange wie das Zeitlimit: ``socket.create_connection`` mit
    ``timeout`` deckt Verbindung UND alle folgenden Schreib-/Lesevorgaenge ab
    (der Timeout gilt je Operation auf dem Socket). Der Socket wird in jedem
    Fall geschlossen (``with``) — eine haengende clamd-Verbindung darf keinen
    Arbeitsfaden behalten.

    Die Antwort endet je nach clamd-Fassung mit ``\\n`` ODER mit ``\\0``
    (z-Modus, ``zINSTREAM``): beide Zeichen beenden die Schleife. Sonst
    wuerde auf einen haengenden Dienst gewartet, obwohl die Zeile schon da ist.
    """
    with socket.create_connection((z.host, z.port), timeout=z.zeitlimit) as s:
        s.settimeout(z.zeitlimit)
        s.sendall(b"zINSTREAM\x00")
        for anfang in range(0, len(daten), BLOCKGROESSE):
            block = daten[anfang:anfang + BLOCKGROESSE]
            s.sendall(struct.pack("!I", len(block)))
            s.sendall(block)
        s.sendall(struct.pack("!I", 0))  # Ende des Stroms
        stuecke: list[bytes] = []
        while True:
            stueck = s.recv(4096)
            if not stueck:
                break
            stuecke.append(stueck)
            if b"\n" in stueck or b"\x00" in stueck:
                break
    return b"".join(stuecke)
