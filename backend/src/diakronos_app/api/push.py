"""CHAT-10a — Web-Push ohne Inhalt (VAPID): Abonnements, Versand, Endpunkte.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` 3.2 („Push aufs Handy“) und
Entscheidung **F10: Web-Push OHNE Inhalt**. Diese Datei ist die EINE Stelle für
drei Dinge:

  1. **Abonnements** — ``anmelden``/``abmelden`` je Gerät (Tabelle
     ``push_abonnement``, Migration ``chat10a_push``).
  2. **Versand** — ``versand_auftrag`` (was der Hook aufruft), ``sende_auftrag``
     (der rq-Job) und ``_senden_an`` (der einzige Netzaufruf).
  3. **Schlüssel** — ``schluessel`` (der Browser holt hier den öffentlichen
     VAPID-Schlüssel).

KEINE SCHLÜSSEL IM REPO, KEINE ERZEUGUNG ZUR LAUFRUNKT
======================================================
Die drei VAPID-Werte kommen aus der Umgebung (``DIAKRONOS_VAPID_PUBLIC``,
``DIAKRONOS_VAPID_PRIVATE``, ``DIAKRONOS_VAPID_KONTAKT``, gelesen über
``settings`` wie jede andere Einstellung). Fehlt EINER, ist Push **AUS**:

  * ``push.schluessel`` → ``{"aktiv": False}`` (kein ``public_key``),
  * ``push.anmelden``/``push.abmelden`` → ``{"aktiv": False}`` ohne Schreiben,
  * der Versand-Hook stellt gar keinen Auftrag ein.

Das ist kein Fehler, sondern der gültige Zustand einer Installation ohne Push.
Ein Paar erzeugt der Operator mit ``tools/vapid_schluessel.py`` und trägt es in
die ``.env`` ein.

WAS EIN PUSH ENTHÄLT — UND WAS NIE
==================================
Nutzlast ist GENAU ``{"titel", "text", "ziel"}``:

  ``titel``  wie die Glocke (``Notification Log.subject``),
  ``text``   wie die Glocke (``Notification Log.email_content``),
  ``ziel``   Adresse im SPA (``#/nachrichten/<gespräch>``).

NIE Nachrichteninhalt, NIE Absendername (die Glocke nennt ihn auch nicht —
``api.chat._glocken_titel`` ist im 1:1 neutral), NIE Kennungen anderer
Personen. Der Push ist damit auf dem Sperrbildschirm unschädlich: er sagt
„es gibt etwas Neues im Chor“ und nicht, was.

Ein Push in der Nähe einer Glocke heißt: **dieselben** Bedingungen wie die
Glocke — stumm geschaltete Gespräche bekommen keinen Push (die Glocke auch
nicht), eine Erwähnung klingelt auch bei stumm (die Glocke auch). Umgesetzt ist
das NICHT hier, sondern an der Glocke selbst (``api.chat``: nur wo
``glocke_setzen`` wirklich geschrieben hat, entsteht ein Auftrag).

ASYNCHRON ÜBER DEN VORHANDENEN rq-WORKER
========================================
``versand_auftrag`` reiht ``sende_auftrag`` über
``frappe_compat.queue.enqueue`` ein (dasselbe Muster wie der Google-Import:
Callable, ``queue="default"``, ``timeout``). Kein Versand im Request, kein
Netzaufruf in der Fach-Transaktion. Ist Redis nicht erreichbar, ist der Push
verloren — er ist Beiwerk, die Glocke steht.

**Erst NACH dem Commit** (Review R1/7): der Chat-Hook sammelt die Aufträge in
der Fach-Sitzung und reiht sie erst über das ``after_commit``-Ereignis dieser
Sitzung ein — bei einem Rollback geht deshalb kein Push für eine Glocke
hinaus, die es nicht gibt. Das Muster liegt in ``api.chat._push_nach_glocke``
(das Projekt hat kein ``after_commit``; ``frappe_compat.queue`` ignoriert die
Frappe-Option ausdrücklich, weil es dort keinen offenen Transaktionskontext
gibt — hier gibt es einen).

EIN NETZAUFRUF, EINE FUNKTION
=============================
``_senden_an(abo, nutzlast)`` ist der einzige Ort, der ins Netz geht. Sie
importiert ``pywebpush`` ERST IN DER FUNKTION: die Tests ersetzen sie, und die
App läuft auch, wenn das Paket (noch) nicht installiert ist. Fehlt das Paket
ganz, wird gar kein Auftrag eingereiht (``importlib.util.find_spec`` vorab,
eine Warnung im Protokoll) — und wenn doch einer läuft, zählt er NICHT als
Fehlversuch des Geräts.

Antworten des Push-Dienstes:

  * **2xx** → ``zuletzt_ok_am = jetzt``, ``fehlversuche = 0``
  * **404/410** → das Gerät ist weg (Abonnement im Browser gelöscht) →
    Zeile LÖSCHEN
  * **Netzfehler/4xx/5xx/Zeitlimit/Redirect** → ``fehlversuche + 1``, ab
    ``MAX_FEHLVERSUCHE`` Zeile löschen
  * **eigener Konfigurationsfehler** (Paket fehlt, Schlüssel/Signatur kaputt)
    → ``fehlversuche`` bleibt, nichts wird gelöscht (Review R1/3)

KEINE REDIRECTS (Review R1/1)
=============================
``_senden_an`` übergibt eine eigene ``requests.Session`` mit
``max_redirects = 0``. Ohne sie folgte ``pywebpush`` (bzw. ``requests.post``)
einem 302 auf einen beliebigen Host — die Allowlist prüfte dann das erste
Ziel, angeschrieben würde ein anderes. Eine 3xx-Antwort ist ein Fehlversuch.

ALLOWLIST DER PUSH-DIENSTE (Review R1/2, Operator-Entscheidung)
==============================================================
``PUSH_DIENSTE`` nennt die vier Dienste, an die gesendet werden darf
(FCM, Mozilla, WNS, APNs) — exakter Host oder Suffix mit führendem Punkt.
Nur https, nur Port 443 (oder kein Port), keine IP-Literale. Geprüft wird

  * beim ANMELDEN (``pruefe_endpoint``) — plus eine DNS-Auflösung als zweite
    Grenze, die öffentliche Adressen verlangt,
  * beim ABMELDEN (nur Syntax/Allowlist, KEINE DNS-Auflösung — R1/6),
  * beim VERSAND je Abonnement (``_abo_endpunkt_erlaubt``): eine Zeile
    außerhalb der Liste wird gelöscht und nie angeschrieben.

Eine Allowlist statt einer Blocklist, weil der Endpunkt ein ZIEL ist: eine
Blocklist deckt nur die Ziele ab, an die man gedacht hat.

SEC-11
======
``schluessel`` ist GET (liest nur), ``anmelden``/``abmelden`` sind POST-only
(schreiben). Rechte: nur angemeldete Konten mit Kontozeile — kein Gast, und
jede Person sieht/ändert AUSSCHLIESSLICH eigene Abonnements.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.exceptions import throw
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.push import (
    ENDPOINT_MAX,
    MAX_ABOS_JE_KONTO,
    MAX_FEHLVERSUCHE,
    SCHLUESSEL_MAX,
    PushAbonnement,
)

# Original-Frappe-Pfad der SPA (Registry-Schlüssel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakronos.api.push"

logger = logging.getLogger("diakronos_app.api.push")

__all__ = [
    "ENDPOINT_MAX",
    "FRAPPE_MODULE",
    "MAX_ABOS_JE_KONTO",
    "MAX_FEHLVERSUCHE",
    "NUTZLAST_FELDER",
    "PUSH_DIENSTE",
    "SCHLUESSEL_MAX",
    "VAPID_AUS",
    "VAPID_FEHLER",
    "VAPID_KONFIG",
    "VAPID_OK",
    "VAPID_WEG",
    "abmelden",
    "aktiv",
    "anmelden",
    "pruefe_endpoint",
    "sende_auftrag",
    "schluessel",
    "versand_auftrag",
]

#: Ergebnis von ``_senden_an``. Vier Fälle — drei entscheidet der Dienst, den
#: vierten die eigene Konfiguration (s. ``_senden_an``).
VAPID_OK = "ok"
VAPID_WEG = "weg"          # 404/410 — Abonnement löschen
VAPID_FEHLER = "fehler"    # Netz-/HTTP-Fehler — Fehlversuch zählen
#: Fehler UNSERER Seite (pywebpush fehlt, Schlüssel kaputt, Signatur scheitert).
#: Das Gerät kann nichts dafür: ``fehlversuche`` bleibt, nichts wird gelöscht
#: (Review R1/3). Ein Abo würde sonst nach fünf fehlenden Schlüsseln
#: verschwinden, obwohl es gesund ist.
VAPID_KONFIG = "konfig"
#: Push ist AUS (VAPID-Werte fehlen) — gleiche Behandlung wie ``VAPID_KONFIG``.
VAPID_AUS = "aus"

#: Die erlaubten Push-Dienste (Review R1/2, Operator-Entscheidung: ALLOWLIST).
#:
#: Ein Eintrag ist entweder ein EXAKTER Host, ein SUFFIX mit führendem Punkt
#: („dieser Host und jede Unterdomäne“) oder eine Kennzeichnung für eine
#: Unterdomäne einer Domäne aus ``_PUSH_DIENST_SUFFIXE``.
#:
#: Warum eine Allowlist und keine Blocklist: der Endpunkt ist eine ZIELADRESSE,
#: zu der die App einen POST schickt. Eine Blocklist („keine privaten
#: Adressen“) verhindert nur die Ziele, an die man gerade gedacht hat; ein
#: fremder Host im öffentlichen Netz bleibt erlaubt und bekommt von der App
#: einen signierten Request. Die Liste ist der kleinere, prüfbare Weg: es gibt
#: genau vier Dienste, die Web-Push anbieten, und alle sind hier.
PUSH_DIENSTE: tuple[str, ...] = (
    "fcm.googleapis.com",
    ".push.services.mozilla.com",
    ".notify.windows.com",
    ".push.apple.com",
)

#: Exakte Hosts, deren Unterdomänen ebenfalls erlaubt sind. Getrennt von
#: ``PUSH_DIENSTE``, weil ein Suffix-Eintrag ``.fcm.googleapis.com`` auch
#: ``evil.fcm.googleapis.com`` erlauben würde — für FCM ist der Host exakt.
_PUSH_DIENST_EXAKT_MIT_UD: tuple[str, ...] = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
)

#: Ein Suffix aus ``PUSH_DIENSTE``, das Unterdomänen erlaubt (Mozilla verteilt
#: je Kanal eigene Hosts, z. B. ``updates.push.services.mozilla.com``).
_PUSH_DIENST_SUFFIXE: tuple[str, ...] = (
    ".push.services.mozilla.com",
    ".notify.windows.com",
    ".push.apple.com",
)

#: Die erlaubten Ports. Web-Push läuft ausschließlich auf 443; kein Port in der
#: Adresse heißt 443. ``8443`` wäre ein anderer Dienst auf demselben Host und
#: ist NICHT erlaubt.
ERLAUBTE_PORTS = frozenset({None, 443})

#: Die Felder der Nutzlast. Mehr geht NICHT hinaus (Konzept F10).
NUTZLAST_FELDER = ("titel", "text", "ziel")

#: Höchstlänge der Nutzlast-Felder. Die Glocke schreibt kurze Betreffzeilen;
#: 500 Zeichen sind großzügig und verhindern, dass ein Fehler in der Glocke
#: einen Riesen-Payload an einen fremden Dienst schickt.
NUTZLAST_MAX = 500

#: Präfix des Ziels im SPA (Adresse im Gespräch). ``#/nachrichten/<gespräch>``.
ZIEL_PRAEFIX = "#/nachrichten/"


# ── Schlüssel (Umgebung) ────────────────────────────────────────────────────


def _vapid() -> tuple[str, str, str] | None:
    """``(public, private, kontakt)`` aus der Umgebung — oder ``None`` = AUS.

    Gelesen über ``settings`` (dieselbe Stelle wie jede andere Einstellung).
    Fehlt einer der drei Werte, ist Push AUS — es gibt KEINEN Teilbetrieb: ein
    öffentlicher Schlüssel ohne privaten könnte abonnieren lassen, aber nichts
    senden (der Browser zeigte ein Abonnement, das nie klingelt).
    """
    from diakronos_app.settings import settings

    oeffentlich = str(getattr(settings, "vapid_public", "") or "").strip()
    privat = str(getattr(settings, "vapid_private", "") or "").strip()
    kontakt = str(getattr(settings, "vapid_kontakt", "") or "").strip()
    if not (oeffentlich and privat and kontakt):
        return None
    # Review CHAT-10a-2, Befunde 2/3: eine Fehlkonfiguration UNSERER Seite
    # schaltet Push ab, statt beim Senden als Gerätefehler zu zählen (das
    # löschte nach fünf Glocken alle Abonnements). ``sub`` muss mailto:/https:
    # sein (py_vapid wirft sonst VapidException); der private Schlüssel muss
    # das Rohformat aus tools/vapid_schluessel.py sein (32 Byte Base64url).
    if not _KONTAKT_MUSTER.fullmatch(kontakt):
        logger.warning("push: DIAKRONOS_VAPID_KONTAKT muss mit mailto: oder https:// beginnen — Push aus")
        return None
    if not _privat_rohformat(privat):
        logger.warning("push: DIAKRONOS_VAPID_PRIVATE ist kein 32-Byte-Schlüssel (Base64url) — Push aus")
        return None
    return oeffentlich, privat, kontakt


_KONTAKT_MUSTER = re.compile(r"(mailto:\S+|https://\S+)")


def _privat_rohformat(privat: str) -> bool:
    """32 Byte Base64url und ein gültiger P-256-Skalar."""
    import base64
    import binascii

    try:
        roh = base64.urlsafe_b64decode(privat + "=" * (-len(privat) % 4))
    except (binascii.Error, ValueError):
        return False
    if len(roh) != 32:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric import ec

        ec.derive_private_key(int.from_bytes(roh, "big"), ec.SECP256R1())
    except ImportError:  # pragma: no cover — cryptography ist Pflicht
        return True
    except (ValueError, TypeError):
        return False
    return True


def aktiv() -> bool:
    """Ist Push eingeschaltet (alle drei VAPID-Werte gesetzt)?"""
    return _vapid() is not None


# ── Rechte ──────────────────────────────────────────────────────────────────


def _benutzer() -> str:
    """Das angemeldete Konto — oder 403 (auch für Gast).

    ``allow_guest=False`` an den Endpunkten schließt den Gast schon auf der
    Routen-Ebene aus. Diese Prüfung ist die zweite, unabhängige Grenze: sie
    greift auch, wenn ein Endpunkt einmal ohne Dekoration aufgerufen wird
    (Scheduler, Test, künftiger Aufrufer). Ein Gast ist der Name ``"Guest"``.
    """
    konto = str(session.user or "").strip()
    if not konto or konto == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return konto


# ── Endpunkt-Prüfung (Allowlist + SSRF) ─────────────────────────────────────


def _ist_oeffentliche_adresse(adresse: str) -> bool:
    """Liegt die Adresse NICHT in einem internen/reservierten Bereich?

    ZWEITE Grenze, nur beim ANMELDEN. Geprüft wird über ``ipaddress`` (nicht
    über Namensmuster): ``is_global`` ist genau die Frage „im öffentlichen
    Internet erreichbar?“. Zusätzlich ausgeschlossen werden Multicast und das
    Netz 0.0.0.0/8 — ``is_global`` ließe beides durch.
    """
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    if ip.is_private or ip.is_reserved:
        return False
    return bool(ip.is_global)


def _host_erlaubt(host: str) -> bool:
    """Steht der Host auf der Allowlist der Push-Dienste?

    Drei Formen, exakt geprüft (KEIN ``endswith`` über den ganzen Namen —
    sonst ginge ``http``-Präfixe oder Suffix-Fallen durch):

      * exakter Host aus ``_PUSH_DIENST_EXAKT_MIT_UD`` (z. B. FCM),
      * Suffix mit führendem Punkt: ``host.endswith(suffix)`` UND der Host ist
        LÄNGER als das Suffix (``.push.apple.com`` selbst ist kein Geräte-Host),
      * exakter Host aus ``PUSH_DIENSTE`` ohne führenden Punkt.

    Damit fallen ``evilfcm.googleapis.com.attacker.tld`` (exakter Vergleich
    schlägt fehl, kein Suffix passt), ``fcm.googleapis.com.evil.tld`` (Suffix
    passt nicht) und ``xnotify.windows.com`` (Suffix beginnt mit einem Punkt).
    """
    name = str(host or "").strip().lower().rstrip(".")
    if not name:
        return False
    # Ein IP-Literal ist nie ein Push-Dienst — auch keine öffentliche Adresse.
    try:
        ipaddress.ip_address(name)
    except ValueError:
        pass
    else:
        return False
    if name in _PUSH_DIENST_EXAKT_MIT_UD:
        return True
    for suffix in _PUSH_DIENST_SUFFIXE:
        if len(name) > len(suffix) and name.endswith(suffix):
            return True
    # Ein Suffix-Eintrag ohne führenden Punkt wäre ein exakter Host.
    return any(not eintrag.startswith(".") and name == eintrag
               for eintrag in PUSH_DIENSTE)


def _host_ist_oeffentlich(host: str) -> bool:
    """Löst den Hostnamen auf und verlangt für JEDE Adresse „öffentlich“.

    ZWEITE Grenze, nur beim ANMELDEN (Review R1/2, R1/6): die Allowlist
    entscheidet, WER als Push-Dienst gilt; diese Auflösung prüft zusätzlich,
    dass der Name heute nicht in ein internes Netz zeigt (ein vergifteter oder
    übernommener Name). Beim ABMELDEN wird sie NICHT gefahren: dort gibt es
    keinen Netzaufruf, nur ein DELETE auf die eigene Zeile — eine Auflösung
    wäre eine überflüssige Abhängigkeit von DNS.

    **Fail closed**: lässt sich der Name nicht auflösen, ist er für das
    ANMELDEN nicht brauchbar. Sind mehrere Adressen hinterlegt (A/AAAA), muss
    JEDE öffentlich sein: sonst genügte ein Name, der zusätzlich auf 127.0.0.1
    zeigt.

    Kein ``socket.setdefaulttimeout``: der wirkt PROZESSWEIT und nicht auf
    ``getaddrinfo`` (Review R1/2). Der Aufruf hängt stattdessen am
    Systemauflöser — die Allowlist ist die Grenze, die trägt, diese Prüfung
    ist die Zugabe.
    """
    if not host:
        return False
    try:
        treffer = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError):
        return False
    adressen = {str(t[4][0]) for t in treffer if t and t[4]}
    if not adressen:
        return False
    return all(_ist_oeffentliche_adresse(a) for a in adressen)


@dataclass(frozen=True)
class _Endpunkt:
    """Ein geprüfter Push-Endpunkt: die Adresse und der Host."""

    url: str
    host: str
    port: int | None


def _zerlege_endpoint(endpoint: Any) -> _Endpunkt:
    """Syntax + Länge + Schema + Port + Allowlist — OHNE Namensauflösung.

    Diese Prüfung ist für ``anmelden`` UND ``abmelden`` dieselbe. Sie enthält
    alles, was ohne Netz entscheidbar ist: der Host muss ein bekannter
    Push-Dienst sein, deshalb ist ein internes Ziel schon hier ausgeschlossen.

    **ZWEI PARSER, EIN HOST** (Review CHAT-10a-2/1, SSRF): geprüft wird der
    Host, den ``urllib.parse.urlsplit`` liefert — ANGEfaheren wird aber der der
    ``requests``/``urllib3``. Die beiden lesen eine Authority unterschiedlich:
    ``urllib3`` schneidet sie am ``\\`` ab (der in URL-Pfaden als ``/`` gilt),
    ``urlsplit`` nicht. ``https://127.0.0.1\\.push.apple.com/x`` und
    ``https://evil.tld\\x.notify.windows.com/x`` bestanden damit die Allowlist,
    obwohl der POST an ``127.0.0.1`` bzw. ``evil.tld`` gegangen wäre. Deshalb:

      1. ``\\``, ``%``, Leerraum und Steuerzeichen in der Authority ablehnen —
         keines davon gehört in einen Host, und jedes ist ein Weg, zwei Parser
         verschieden lesen zu lassen (``%5c`` wird von ``urllib3`` NICHT
         dekodiert: der rohe Text bleibt im Host stehen),
      2. der Host muss streng ``[a-z0-9-]+(\\.[a-z0-9-]+)*\\.?`` erfüllen,
      3. **Gegenprobe**: ``urllib3.util.parse_url(roh).host`` (klein, ohne
         Schlußpunkt) muss dem geprüften Host entsprechen. Weicht der zweite
         Parser ab, wird abgewiesen — die Allowlist gilt für das Ziel, das
         ``requests`` tatsächlich anfährt, nicht für das, was wir glauben.
    """
    roh = str(endpoint or "").strip()
    if not roh:
        throw("endpoint fehlt.")
    if len(roh) > ENDPOINT_MAX:
        throw(f"Der Push-Endpunkt ist zu lang (höchstens {ENDPOINT_MAX} Zeichen).")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in roh):
        throw("Der Push-Endpunkt enthält Steuerzeichen.")
    try:
        # ``#`` ist ein Fragment-Anfang: in einem Endpunkt hat er nichts zu
        # suchen (der POST ginge an den Pfad VOR dem ``#``), und ``urlsplit``/
        # ``urllib3`` behandeln ihn unterschiedlich genug, dass er als Trenner
        # für eine Parser-Differenz taugt.
        formen: dict[str, Any] = _endpunkt_formen(roh)
    except ValueError:
        throw("Der Push-Endpunkt ist keine gültige Adresse.")
        raise  # unerreichbar; macht ``formen`` für die Prüfer gebunden
    if formen["netloc"] == "" or formen["netloc"] is None:
        throw("Der Push-Endpunkt ist keine gültige Adresse.")
    if formen["schema"] != "https":
        throw("Der Push-Endpunkt muss https sein.")
    if formen["fragment"]:
        throw("Der Push-Endpunkt darf kein Fragment enthalten.")
    if formen["benutzer"] or formen["passwort"]:
        throw("Der Push-Endpunkt darf keine Zugangsdaten enthalten.")
    netzteil = str(formen["netloc"])
    if any(c in netzteil for c in "\\%") or any(c.isspace() for c in netzteil):
        # ``\`` trennt für ``urllib3`` die Authority ab; ``%`` (etwa ``%5c``)
        # wird dort NICHT dekodiert und bliebe als Text im Host stehen. Beides
        # sind Wege, den geprüften und den angefahrenen Host auseinanderlaufen
        # zu lassen (Karte CHAT-10a-2/1).
        throw("Der Push-Endpunkt enthält unzulässige Zeichen im Host.")
    host = str(formen["host"] or "").strip()
    if not host:
        throw("Der Push-Endpunkt hat keinen Host.")
    if not _hostform_streng(host):
        throw("Der Push-Endpunkt hat keinen gültigen Hostnamen.")
    if not _zweiter_parser_stimmt(roh, host):
        throw("Der Push-Endpunkt ist nicht eindeutig lesbar.")
    port = formen["port"]
    if port not in ERLAUBTE_PORTS:
        throw("Der Push-Endpunkt muss auf Port 443 laufen.")
    if not _host_erlaubt(host):
        # KEINE Details: die Antwort soll nicht verraten, welche Dienste die
        # App kennt (das wäre selbst eine Auskunft über die Anbindung).
        throw("Der Push-Endpunkt gehört zu keinem bekannten Push-Dienst.")
    return _Endpunkt(url=roh, host=host.lower().rstrip("."), port=port)


def _endpunkt_formen(roh: str) -> dict[str, Any]:
    """Die Teile, die ``urlsplit`` liest — als einfaches Dict (``port`` geprüft)."""
    teile = urlsplit(roh)
    return {
        "schema": (teile.scheme or "").lower(),
        "netloc": teile.netloc,
        "fragment": teile.fragment,
        "benutzer": teile.username,
        "passwort": teile.password,
        "host": teile.hostname,
        "port": teile.port,  # wirft ValueError bei kaputtem Port
    }


#: Ein Hostname, wie ihn ein Push-Dienst liefert. Streng und klein: Buchstaben,
#: Ziffern, Bindestriche, Punkte — kein Unterstrich, kein Leerzeichen, kein
#: Unicode (ein IDN kommt bei den vier Diensten nicht vor).
_HOSTFORM = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.?")


def _hostform_streng(host: str) -> bool:
    """Erfüllt ``host`` die strenge Namensform (klein, Ziffern, ``-``, ``.``)?"""
    return bool(_HOSTFORM.fullmatch(str(host or "").lower()))


def _zweiter_parser_stimmt(roh: str, host: str) -> bool:
    """Liest ``urllib3`` (der Parser von ``requests``) DENSELBEN Host?

    ``urllib3`` ist die Bibliothek, die den Request tatsächlich schickt — ihre
    Auffassung von der Authority ist die maßgebliche. Weicht sie von der
    geprüften ab (oder wirft sie), wird abgewiesen. Ist ``urllib3`` nicht
    importierbar, bleibt es bei der strengen Namensform oben (kein Absturz,
    keine stille Zustimmung: die Formprüfung allein lässt keinen ``\\`` durch).
    """
    try:
        from urllib3.util import parse_url
    except ImportError:  # pragma: no cover — requests bringt urllib3 mit
        return True
    try:
        zweiter = parse_url(roh).host or ""
    except Exception:  # noqa: BLE001 — was er nicht lesen kann, fahren wir nicht an
        return False
    return str(zweiter).lower().rstrip(".") == str(host or "").lower().rstrip(".")


def pruefe_endpoint(endpoint: Any, *, aufloesen: bool = True) -> str:
    """Prüft einen Push-Endpunkt und gibt ihn getrimmt zurück (oder wirft).

    Regeln (Karte CHAT-10a + Review R1):

      * nur **https**,
      * Länge ≤ ``ENDPOINT_MAX`` (nicht abschneiden: ein abgeschnittener
        Endpunkt ist ein anderes Gerät),
      * kein Benutzer/Passwort in der Adresse,
      * Port 443 oder kein Port,
      * **Allowlist** (``_host_erlaubt``): nur die vier Push-Dienste
        (Review R1/2). Das schließt interne Adressen mit ein, ohne eine
        Blocklist zu führen, die nur die bekannten Fälle abdeckt,
      * ``aufloesen=True`` (Default, für ``anmelden``): zusätzlich muss der
        Name heute auf öffentliche Adressen zeigen (``_host_ist_oeffentlich``).
        ``aufloesen=False`` für ``abmelden``: dort wird nichts versendet,
        eine DNS-Auflösung wäre nur eine zusätzliche Fehlerquelle
        (Review R1/6).
    """
    geprueft = _zerlege_endpoint(endpoint)
    if aufloesen and not _host_ist_oeffentlich(geprueft.host):
        throw("Der Push-Endpunkt zeigt auf eine nicht öffentliche Adresse.")
    return geprueft.url


def _pruefe_schluessel(wert: Any, feld: str) -> str:
    """``p256dh``/``auth``: Base64url, Länge begrenzt, keine Leerzeichen.

    Beides sind Base64url-Werte (RFC 8291) — geprüft wird das Zeichenvorrat
    (A–Z a–z 0–9 - _ = ), nicht die Kryptographie. Der Verschlüsselungs-Fehler
    eines falschen Punktes meldet sich beim ersten Push; hier geht es darum,
    dass kein Fremdtext in der Spalte landet.
    """
    text = str(wert or "").strip()
    if not text:
        throw(f"{feld} fehlt.")
    if len(text) > SCHLUESSEL_MAX:
        throw(f"{feld} ist zu lang (höchstens {SCHLUESSEL_MAX} Zeichen).")
    erlaubt = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")
    if any(c not in erlaubt for c in text):
        throw(f"{feld} ist kein Base64url-Wert.")
    return text


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(methods=["GET"], allow_guest=False)
def schluessel() -> dict[str, Any]:
    """Der öffentliche VAPID-Schlüssel für den Browser (``applicationServerKey``).

    **ABNAHMESCHNITTSTELLE** für die Frontend-Karte.

    Rückgabe::

        {"aktiv": true,  "public_key": "<Base64url>"}
        {"aktiv": false}                      # Push ist aus

    Ohne Schlüssel KEIN Fehler: die Oberfläche fragt hier einmal und blendet
    die Push-Einstellung aus, wenn ``aktiv`` falsch ist. Der öffentliche
    Schlüssel ist öffentlich — er steht im Abonnement des Browsers und im JWT
    jedes Versands. Der PRIVATE Schlüssel verlässt diese Datei nie.
    """
    _benutzer()
    werte = _vapid()
    if werte is None:
        return {"aktiv": False}
    return {"aktiv": True, "public_key": werte[0]}


@whitelist(methods=["POST"], allow_guest=False)
def anmelden(endpoint=None, p256dh=None, auth=None) -> dict[str, Any]:
    """Ein Gerät für Push anmelden (idempotent je ``endpoint``).

    Legt die Zeile an oder aktualisiert sie. Derselbe ``endpoint`` ist
    DIESELBE Zeile: meldet sich auf demselben Browser eine andere Person an,
    wird die Zeile auf sie UMGEHÄNGT („ein Gerät gehört dem, der gerade
    angemeldet ist“) — es entsteht keine zweite Zeile und kein Push an die
    vorige Person.

    Rückgabe ``{"aktiv": True, "angemeldet": True}``; ist Push aus, antwortet
    der Endpunkt ``{"aktiv": False}`` ohne zu schreiben (kein Fehler — die
    Oberfläche zeigt dann bloß keine Push-Einstellung).

    **Höchstens ``MAX_ABOS_JE_KONTO`` Geräte je Konto** (Review R1/4): beim
    Anlegen eines NEUEN Geräts wird das ÄLTESTE (``angelegt_am``) verdrängt.
    Ohne Grenze könnte ein Konto die Tabelle und jeden Versandlauf beliebig
    aufblähen; zehn sind mehr, als jemand Browser hat.
    """
    konto = _benutzer()
    if not aktiv():
        return {"aktiv": False}
    ziel = pruefe_endpoint(endpoint)
    schluessel_p256dh = _pruefe_schluessel(p256dh, "p256dh")
    schluessel_auth = _pruefe_schluessel(auth, "auth")

    from diakronos_app import db as dbmod
    from diakronos_app.zeit import jetzt_wanduhr

    jetzt = jetzt_wanduhr()
    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(PushAbonnement, ziel)
        if zeile is None:
            zeile = PushAbonnement(
                endpoint=ziel, benutzer=konto, p256dh=schluessel_p256dh,
                auth=schluessel_auth, angelegt_am=jetzt, zuletzt_ok_am=None,
                fehlversuche=0,
            )
            try:
                with s.begin_nested():
                    _sperre_konto(s, konto)
                    s.add(zeile)
                    s.flush()          # die neue Zeile steht — sie zählt mit
                    _verdraenge_aelteres(s, konto)
            except IntegrityError:
                # Zwei gleichzeitige Anmeldungen desselben Geräts: die andere
                # hat gewonnen — ab hier ist es ein UPDATE.
                zeile = s.get(PushAbonnement, ziel)
                if zeile is None:  # pragma: no cover — Zeile war eben noch da
                    raise
                _aktualisiere(s, zeile, konto, schluessel_p256dh, schluessel_auth)
        else:
            _aktualisiere(s, zeile, konto, schluessel_p256dh, schluessel_auth)
        s.flush()
    return {"aktiv": True, "angemeldet": True}


def _sperre_konto(s, konto: str) -> None:
    """Serialisiert die Geräte-Grenze EINES Kontos — auf PostgreSQL.

    Ohne Sperre können zwei gleichzeitige Anmeldungen desselben Kontos beide
    „es sind noch neun“ sehen und beide ein Gerät verdrängen: das eine Konto
    landet bei acht Geräten, oder zwei Verdrängungen treffen dasselbe älteste
    und ein anderes bleibt über der Grenze stehen (Karte CHAT-10a-2/4).

    ``pg_advisory_xact_lock`` hängt an der Transaktion (``hashtext(konto)`` als
    Kennung) und fällt am Ende von selbst weg. SQLite (Tests, Einzelplatz) kennt
    die Funktion nicht und braucht sie nicht: dort schreibt ohnehin nur eine
    Verbindung.
    """
    bind = s.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": str(konto)})


def _verdraenge_aelteres(s, konto: str, *, behalten: str | None = None) -> None:
    """Hält ein Konto bei höchstens ``MAX_ABOS_JE_KONTO`` Geräten.

    Wird beim Anlegen einer neuen Zeile UND beim Umhängen einer fremden Zeile
    gerufen (CHAT-10a-2/4: ein Gerätewechsel bringt dem neuen Konto ein Gerät
    mehr — ohne Verdrängen stünde es über der Grenze). Sortiert nach
    ``angelegt_am`` aufsteigend — das älteste Gerät fällt zuerst; bei gleichem
    Zeitstempel entscheidet der ``endpoint``, damit die Wahl nicht von der
    Datenbank abhängt.

    Der Aufrufer flusht VORHER: die Zeile, um die es geht, steht dann schon in
    der Abfrage — sonst verdrängte ein frisch angemeldetes Gerät sich selbst,
    wenn das Konto über der Grenze stünde (Altbestand aus der Zeit vor R1/4).
    """
    vorhanden = list(s.scalars(
        select(PushAbonnement)
        .where(PushAbonnement.benutzer == konto)
        .order_by(PushAbonnement.angelegt_am, PushAbonnement.endpoint)
    ).all())
    if behalten is not None:
        # Das GERADE angemeldete Gerät fällt nie selbst heraus — auch nicht,
        # wenn es umgehängt wurde und sein ``angelegt_am`` älter ist als die
        # Geräte des neuen Kontos (Review CHAT-10a-2, Befund 1).
        vorhanden = [z for z in vorhanden if z.endpoint != behalten]
        vorhanden.append(None)  # zählt mit, steht als jüngstes am Ende
    # ``vorhanden`` enthält bei einer NEUEN Zeile schon alle bestehenden; das
    # neue Gerät ist das jüngste und bleibt. Bei einer UMGEHÄNGTEN Zeile ist
    # sie selbst dabei und zählt mit — beide Fälle ergeben dieselbe Rechnung.
    ueberzaehlig = len(vorhanden) - MAX_ABOS_JE_KONTO
    for alt in vorhanden[:max(0, ueberzaehlig)]:
        if alt is None:
            continue
        logger.info("push: ältestes Gerät %s von %s verdrängt",
                    _kurz(alt.endpoint), konto)
        s.delete(alt)


def _aktualisiere(s, zeile: PushAbonnement, konto: str, p256dh: str, auth: str) -> None:
    """Die vorhandene Zeile auf den AKTUELLEN Stand bringen (Gerätewechsel).

    ``angelegt_am`` bleibt stehen (es sagt, seit wann das Gerät abonniert ist);
    ``zuletzt_ok_am`` bleibt ebenfalls (die Buchführung des Versands beginnt
    nicht neu). ``fehlversuche`` wird auf 0 gesetzt: eine neue Anmeldung ist
    ein neuer Versuch — sonst löschte die Zeile nach dem fünften Fehlschlag
    trotz frischer Anmeldung.

    **Umhängen verdrängt** (Karte CHAT-10a-2/4): gehört die Zeile bisher einer
    ANDEREN Person, bekommt das neue Konto ein Gerät mehr. Wäre es damit über
    ``MAX_ABOS_JE_KONTO``, fällt sein ältestes weg — sonst wäre die Grenze über
    einen Gerätewechsel umgehbar. Die Sperre (``_sperre_konto``) liegt davor.
    """
    umgehaengt = str(zeile.benutzer or "") != str(konto)
    zeile.benutzer = konto
    zeile.p256dh = p256dh
    zeile.auth = auth
    zeile.fehlversuche = 0
    if umgehaengt:
        _sperre_konto(s, konto)
        s.flush()  # die Zeile gehört jetzt zum neuen Konto — sonst zählt sie nicht mit
        _verdraenge_aelteres(s, konto, behalten=zeile.endpoint)


@whitelist(methods=["POST"], allow_guest=False)
def abmelden(endpoint=None) -> dict[str, Any]:
    """Ein Gerät abmelden — **nur das eigene** Abonnement.

    Ein fremder ``endpoint`` wird NICHT gelöscht: die Antwort ist trotzdem
    ``{"aktiv": True, "abgemeldet": True}``. Absicht — die Antwort verrät
    nicht, ob es das Gerät gibt (sonst wäre der Endpunkt eine Sonde für
    fremde Geräte).

    Geprüft wird nur, was OHNE Netz entscheidbar ist (Syntax, Länge, https,
    Port, Allowlist) — ``aufloesen=False`` (Review R1/6). Ein Abmelden ist ein
    DELETE auf die eigene Zeile; es gibt keinen Grund, dafür einen Namen
    aufzulösen, und ein DNS-Ausfall dürfte das Abmelden nicht blockieren.
    """
    konto = _benutzer()
    if not aktiv():
        return {"aktiv": False}
    ziel = pruefe_endpoint(endpoint, aufloesen=False)

    from diakronos_app import db as dbmod

    with dbmod.SessionLocal.begin() as s:
        s.execute(
            delete(PushAbonnement)
            .where(PushAbonnement.endpoint == ziel,
                   PushAbonnement.benutzer == konto)
        )
    return {"aktiv": True, "abgemeldet": True}


# ── Versand ─────────────────────────────────────────────────────────────────


def _ziel_fuer(gespraech: str) -> str:
    """Adresse im SPA: ``#/nachrichten/<gespräch>``.

    Der Gesprächsname IST die Kennung, die die SPA in der Route führt
    (``api.chat``: ``document_name`` der Glocke = Gespräch). Keine Kennung
    einer anderen PERSON — ein 1:1-Gespräch wird über seinen eigenen Namen
    adressiert, nicht über das Gegenüber.
    """
    return f"{ZIEL_PRAEFIX}{gespraech}"


def _pruefe_nutzlast(nutzlast: Any) -> dict[str, str] | None:
    """Nur ``titel``/``text``/``ziel``, jede Zeichenkette gekappt. Sonst ``None``.

    Gekappt (nicht abgewiesen): die Glocke schreibt die Werte, sie sind keine
    Eingabe einer Person. Fehlt etwas Wesentliches, ist der Auftrag kaputt —
    dann gibt es KEINEN Push (lieber keiner als ein leerer).
    """
    if not isinstance(nutzlast, dict):
        return None
    if set(nutzlast) != set(NUTZLAST_FELDER):
        # GENAU die drei Felder. Ein zusätzliches Feld wäre ein Weg, Inhalt
        # hinauszutragen (etwa den Nachrichtentext) — dann lieber kein Push.
        return None
    sauber: dict[str, str] = {}
    for feld in NUTZLAST_FELDER:
        wert = nutzlast.get(feld)
        if not isinstance(wert, str):
            return None
        wert = wert.strip()
        if not wert:
            return None
        sauber[feld] = wert[:NUTZLAST_MAX]
    return sauber


def _pywebpush_da() -> bool:
    """Ist ``pywebpush`` installiert? (Nur die Existenz, kein Import.)

    ``importlib.util.find_spec`` kostet nichts und lädt das Paket nicht: die
    Prüfung darf im Request-Pfad laufen. Sie ist die VORBedingung dafür, einen
    Auftrag überhaupt einzureihen (Review R1/3): ohne das Paket könnte der Job
    nichts senden, und ein Auftrag je Glocke wäre nur Rauschen im Worker.
    """
    import importlib.util

    try:
        return importlib.util.find_spec("pywebpush") is not None
    except (ImportError, ValueError):  # pragma: no cover — kaputter sys.path
        return False


#: Einmal-Warnung: fehlt ``pywebpush``, steht im Protokoll EINE Zeile statt
#: einer je Glocke.
_ohne_pywebpush_gemeldet = False


def versand_auftrag(konto: str, nutzlast: Any) -> bool:
    """Einen Push-Versand einreihen — **die EINE Stelle**, die Chat-Code ruft.

    Reiht ``sende_auftrag`` über den vorhandenen rq-Worker ein (dasselbe Muster
    wie der Google-Import: ``enqueue(callable, queue="default", timeout=…)``).
    Gibt ``True`` zurück, wenn der Auftrag angenommen wurde.

    Kein Auftrag (und ``False``) bei:
      * Push ist aus (keine VAPID-Werte) — es gäbe nichts zu senden,
      * ``pywebpush`` ist nicht installiert (Review R1/3) — der Job könnte
        nichts tun; es wird EINMAL gewarnt, nicht je Glocke,
      * unbrauchbarer Nutzlast,
      * keinem angemeldeten Konto,
      * Redis nicht erreichbar (``EnqueueError``) — der Push ist Beiwerk, die
        Glocke steht schon; ein Fehler darf den Fachvorgang nicht kippen.

    Was NICHT hier entschieden wird: OB geglockt werden soll. Das entscheidet
    die Glocke selbst (stumm, Rechte, Absender) — der Hook läuft nur, wenn
    ``glocke_setzen`` wirklich geschrieben hat.
    """
    global _ohne_pywebpush_gemeldet
    if not konto or not aktiv():
        return False
    if not _pywebpush_da():
        if not _ohne_pywebpush_gemeldet:
            _ohne_pywebpush_gemeldet = True
            logger.warning("push: pywebpush fehlt — kein Versand (VAPID gesetzt, "
                           "Paket nicht installiert); Abonnements bleiben bestehen")
        return False
    sauber = _pruefe_nutzlast(nutzlast)
    if sauber is None:
        return False
    try:
        from diakronos_app.frappe_compat.queue import enqueue

        enqueue(sende_auftrag, konto=konto, nutzlast=sauber,
                queue="default", timeout=60)
        return True
    except Exception as ex:  # noqa: BLE001 — Push ist Beiwerk
        logger.warning("push: Versandauftrag für %s nicht eingereiht: %s", konto, ex)
        return False


def sende_auftrag(konto: str, nutzlast: Any) -> int:
    """rq-Job: an ALLE Geräte des Kontos senden. Rückgabe: Erfolge.

    Läuft im Worker, NICHT im Request (eigene Sitzung über
    ``SessionLocal``). Je Abonnement:

      * ``_senden_an`` meldet ``VAPID_OK``  → ``zuletzt_ok_am``, Zähler zurück,
      * ``VAPID_WEG`` (404/410)             → Zeile löschen,
      * ``VAPID_FEHLER``                    → ``fehlversuche + 1``, ab
        ``MAX_FEHLVERSUCHE`` Zeile löschen,
      * ``VAPID_KONFIG``/``VAPID_AUS``      → NICHTS zählen, NICHTS löschen
        (Review R1/3): das Gerät ist nicht schuld, wenn das Paket fehlt oder
        der Schlüssel kaputt ist.

    **Allowlist ein ZWEITES Mal** (Review R1/2): die Zeile mag aus einer Zeit
    vor dieser Prüfung stammen (Bestand, Import, künftiger Schreiber). Ein Abo
    außerhalb der Liste wird gelöscht und NICHT angeschrieben — der POST geht
    nur an Adressen, die hier als Push-Dienst festgeschrieben sind.

    Ist Push inzwischen AUS (jemand hat die VAPID-Werte entfernt), wird nichts
    gesendet und nichts gelöscht — kein Netzaufruf ohne Schlüssel.
    """
    if not aktiv():
        return 0
    sauber = _pruefe_nutzlast(nutzlast)
    if sauber is None or not konto:
        return 0
    if not _pywebpush_da():
        logger.warning("push: pywebpush fehlt — Auftrag ohne Versand beendet")
        return 0

    from diakronos_app import db as dbmod
    from diakronos_app.zeit import jetzt_wanduhr

    erfolge = 0
    with dbmod.SessionLocal() as s:
        abos = list(s.scalars(
            select(PushAbonnement).where(PushAbonnement.benutzer == konto)
        ).all())
        for abo in abos:
            if not _abo_endpunkt_erlaubt(abo):
                logger.warning("push: Abo %s nicht in der Dienstliste — entfernt",
                               _kurz(abo.endpoint))
                s.delete(abo)
                s.flush()
                continue
            ergebnis = _senden_an(abo, sauber)
            if ergebnis == VAPID_OK:
                abo.zuletzt_ok_am = jetzt_wanduhr()
                abo.fehlversuche = 0
                erfolge += 1
            elif ergebnis == VAPID_WEG:
                # Gerät weg: das Abonnement ist nicht mehr wahr.
                s.delete(abo)
            elif ergebnis in (VAPID_KONFIG, VAPID_AUS):
                # Eigener Fehler: kein Fehlversuch, kein Löschen (R1/3).
                logger.warning("push: %s -> eigener Konfigurationsfehler (%s)",
                               _kurz(abo.endpoint), ergebnis)
            else:
                abo.fehlversuche = int(abo.fehlversuche or 0) + 1
                if abo.fehlversuche >= MAX_FEHLVERSUCHE:
                    logger.info("push: %s nach %s Fehlversuchen entfernt",
                                _kurz(abo.endpoint), abo.fehlversuche)
                    s.delete(abo)
            s.flush()
        s.commit()
    return erfolge


def _abo_endpunkt_erlaubt(abo: PushAbonnement) -> bool:
    """Prüft die Zeile im Versand noch einmal gegen die Allowlist.

    Nur Syntax/Allowlist (``aufloesen=False``) — KEINE DNS-Auflösung im
    Worker: die Adresse wird ohnehin von ``requests`` aufgelöst, und ein
    zweiter Auflöser davor wäre nur eine weitere Fehlerquelle. Was zählt: der
    Host ist einer der vier Dienste, https, Port 443, Länge stimmt.
    """
    try:
        pruefe_endpoint(abo.endpoint, aufloesen=False)
    except Exception:  # noqa: BLE001 — jede Abweichung = nicht senden
        return False
    return True


def _kurz(endpoint: str) -> str:
    """Ein Endpunkt für Protokollzeilen — gekürzt, nie vollständig.

    Der endpoint ist ein Zugangs-Token des Geräts (wer ihn hat, kann es
    anpingen). Deshalb steht er NIE ganz im Protokoll.
    """
    text = str(endpoint or "")
    return f"{text[:32]}…" if len(text) > 32 else text


def _geraetefehler(abo: PushAbonnement) -> str | None:
    """Ist das GERÄT unbrauchbar? Dann den Grund, sonst ``None``.

    ``p256dh`` ist ein unkomprimierter Punkt auf P-256 (65 Byte, erstes Byte
    ``0x04``), ``auth`` ein 16-Byte-Geheimnis (RFC 8291) — beides Base64url.
    Geprüft wird NUR das, was ohne Netz entscheidbar ist; die Kryptographie
    selbst macht ``pywebpush``.

    Rückgabe ist ein KURZER Grund fürs Protokoll (nie ein Wert, nie das
    Token): ``p256dh:base64``, ``p256dh:punkt``, ``auth:base64``,
    ``auth:laenge``.
    """
    import base64
    import binascii

    for feld, roh in (("p256dh", abo.p256dh), ("auth", abo.auth)):
        text = str(roh or "").strip()
        if not text:  # pragma: no cover — Spalte ist NOT NULL
            return None
        try:
            bytes_ = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        except (binascii.Error, ValueError):
            return f"{feld}:base64"
        if feld == "auth":
            if len(bytes_) != 16:
                return "auth:laenge"
            continue
        if len(bytes_) != 65 or bytes_[0] != 0x04:
            return "p256dh:punkt"
        # Der Punkt muss AUF der Kurve liegen — ein zufälliges 65-Byte-Feld
        # tut das fast nie, und ``pywebpush`` scheiterte daran erst später.
        try:
            from cryptography.hazmat.primitives.asymmetric import ec

            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes_)
        except ImportError:  # pragma: no cover — cryptography ist Pflicht
            continue
        except ValueError:
            return "p256dh:punkt"
    return None


def _eigener_schluessel_fehler(ex: BaseException, privat: str) -> bool:
    """Ist ``ex`` ein Fehler UNSERES VAPID-Schlüssels (und nicht des Geräts)?

    Beleg ist der SCHLÜSSEL, nicht der Fehlertext (der nennt das Token):
    ``pywebpush`` signiert das JWT mit ``vapid_private_key``; ist der Wert
    kein gültiger P-256-Skalar (Base64url, 32 Byte, 1 ≤ d < n), ist es unsere
    Konfiguration und nicht das Gerät. Der Fehler selbst muss dabei ein
    ``ValueError``/``TypeError``/``ArithmeticError`` sein — alles andere (auch
    ``AttributeError``, ``KeyError``, ein Transportfehler) bleibt ein Fehler
    des Versuchs (fail closed, Karte CHAT-10a-2/5).
    """
    if not isinstance(ex, (ValueError, TypeError, ArithmeticError)):
        return False
    import base64
    import binascii

    try:
        text = str(privat or "")
        roh = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        return True  # nicht dekodierbar = unsere Konfiguration
    if len(roh) != 32:
        return True
    try:
        from cryptography.hazmat.primitives.asymmetric import ec

        ec.derive_private_key(int.from_bytes(roh, "big"), ec.SECP256R1())
    except ImportError:  # pragma: no cover — cryptography ist Pflicht
        return False
    except (ValueError, TypeError):
        return True
    # Der Schlüssel trägt: derselbe Fehlertyp kam also NICHT von ihm. Damit ist
    # er ein Fehler des Versuchs (das Gerät/das Paket) — nicht unserer.
    return False


def _senden_an(abo: PushAbonnement, nutzlast: dict[str, str]) -> str:
    """**Der einzige Netzaufruf.** Ergebnis wie in ``sende_auftrag`` beschrieben.

    Tests ersetzen DIESE Funktion (``monkeypatch.setattr(P, "_senden_an", …)``)
    — es gibt keinen zweiten Weg ins Netz.

    ``pywebpush`` wird ERST HIER importiert: die App läuft auch ohne das Paket
    (nur der Versand scheitert), und die Tests brauchen es nicht.

    **KEINE Redirects** (Review R1/1, HOCH): ``pywebpush`` benutzt intern
    ``requests.post``, das 301/302/303/307/308 folgt — und ein Redirect könnte
    das Ziel auf einen beliebigen Host verschieben, nachdem die Allowlist
    geprüft wurde. Deshalb eine eigene Sitzung mit ``max_redirects=0``; jede
    3xx-Antwort ist ein Fehlversuch (``VAPID_FEHLER``), kein zweiter Versuch
    an einem anderen Ziel.

    **Eigene Fehler zählen nicht** (Review R1/3): fehlt ``pywebpush``, ist der
    Schlüssel kaputt oder scheitert die Signatur, kommt ``VAPID_KONFIG``
    zurück — ``fehlversuche`` bleibt, nichts wird gelöscht. Nur Netz- und
    HTTP-Fehler des Dienstes zählen.

    Das Zeitlimit kommt aus ``settings.push_timeout_sekunden``: ein hängender
    Push-Dienst darf den Worker-Job nicht festhalten.

    Protokoll OHNE Token (Review R1/5): nur ``_kurz(endpoint)`` und der
    Ausnahmetyp — die Endpunkt-URL ist ein Zugangs-Token des Geräts und steht
    nirgends vollständig.
    """
    werte = _vapid()
    if werte is None:
        return VAPID_AUS
    oeffentlich, privat, kontakt = werte
    from diakronos_app.settings import settings

    timeout = float(getattr(settings, "push_timeout_sekunden", 10.0) or 10.0)

    # Das GERÄT zuerst prüfen (CHAT-10a-2/5): ein kaputter ``p256dh`` oder ein
    # unbrauchbares ``auth`` ist ein Fehler des ABONNEMENTS — das Gerät muss
    # wie jeder andere Fehlschlag zählen und nach ``MAX_FEHLVERSUCHE``
    # verschwinden. Bisher kam das als undurchsichtiger Fehler aus dem
    # Verschlüsselungsschritt und galt als UNSER Konfigurationsfehler; die
    # Zeile blieb damit für immer stehen und der Worker scheiterte an ihr
    # weiter. Geprüft wird, was ``pywebpush`` ohnehin dekodiert (Base64url) und
    # der Punkt auf der Kurve P-256 — jeder Dekodier-/Punktfehler zählt.
    try:
        import requests
        from pywebpush import WebPushException, webpush
    except Exception as ex:  # noqa: BLE001 — Paket fehlt/falsch installiert
        logger.error("push: pywebpush nicht verfügbar (%s) — Versand ausgesetzt",
                     type(ex).__name__)
        return VAPID_KONFIG

    fehler = _geraetefehler(abo)
    if fehler is not None:
        logger.warning("push: %s -> Gerät unbrauchbar (%s)",
                       _kurz(abo.endpoint), fehler)
        return VAPID_FEHLER

    # Redirects AUS: die Allowlist gilt für das Ziel des Requests, nicht für
    # das Ziel, auf das ein fremder Dienst weiterleiten möchte.
    sitzung = requests.Session()
    sitzung.max_redirects = 0

    try:
        antwort = webpush(
            subscription_info={
                "endpoint": abo.endpoint,
                "keys": {"p256dh": abo.p256dh, "auth": abo.auth},
            },
            data=json.dumps(nutzlast),
            vapid_private_key=privat,
            vapid_claims={"sub": kontakt},
            timeout=timeout,
            requests_session=sitzung,
        )
    except WebPushException as ex:
        ziel = getattr(ex, "response", None)
        status = getattr(ziel, "status_code", None)
        if status in (404, 410):
            return VAPID_WEG
        logger.warning("push: %s -> HTTP %s", _kurz(abo.endpoint), status)
        return VAPID_FEHLER
    except Exception as ex:  # noqa: BLE001
        # Netzfehler (Verbindung, Zeitlimit) zählen — Schlüssel-/Signaturfehler
        # UNSERER Seite nicht. Getrennt wird über die Fehlerart, nicht über den
        # Text: ``requests``-Fehler sind Transport, ein Fehler beim eigenen
        # VAPID-Schlüssel/Signieren ist unsere Konfiguration.
        import requests

        if isinstance(ex, requests.RequestException):
            logger.warning("push: %s -> %s", _kurz(abo.endpoint), type(ex).__name__)
            return VAPID_FEHLER
        # Eigener Schlüssel kaputt? Dann ist es UNSERE Konfiguration (R1/3);
        # alles andere an dieser Stelle ist unerwartet und zählt als Fehler
        # des Versuchs (fail closed: die Zeile verschwindet notfalls, statt
        # den Versandlauf dauerhaft zu blockieren).
        if type(ex).__name__ == "VapidException" or _eigener_schluessel_fehler(ex, privat):
            # **Ohne ``str(ex)``**: die Fehlermeldung nennt das Token des
            # Geräts (R1/5).
            logger.warning("push: %s -> eigener Schlüsselfehler %s",
                           _kurz(abo.endpoint), type(ex).__name__)
            return VAPID_KONFIG
        logger.warning("push: %s -> Fehler %s", _kurz(abo.endpoint),
                       type(ex).__name__)
        return VAPID_FEHLER
    finally:
        sitzung.close()

    # ``webpush`` wirft bei 4xx/5xx; kommt eine Antwort ohne Fehler zurück,
    # entscheidet der Status (defensiv: auch ein 2xx-Objekt wird geprüft).
    status = getattr(antwort, "status_code", 201)
    if status in (404, 410):
        return VAPID_WEG
    if isinstance(status, int) and 200 <= status < 300:
        return VAPID_OK
    logger.warning("push: %s -> HTTP %s", _kurz(abo.endpoint), status)
    return VAPID_FEHLER
