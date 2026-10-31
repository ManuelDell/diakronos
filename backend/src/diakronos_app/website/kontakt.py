"""WEB-10 — Kontaktformular der Website: sendet NUR eine E-Mail.

Der Vertrag (WEB-9b baut das Formular dagegen)
=============================================

    POST {Praefix}/api/method/website.kontakt_senden        (allow_guest)

    JSON: {"name": str, "email": str, "nachricht": str,
           "einwilligung": true, "website": str}

    Erfolg:            200 {"message": {"ok": true}}
    Feldpruefung:      400 {"message": "...", "felder": {"<feld>": "..."}, ...}
    fremde Herkunft:   403
    andere Methode:    403
    zu viele Anfragen: 429
    nicht eingerichtet/ Versandfehler/ Bremse aus: 503

KEINE SPEICHERUNG. Die Anfrage wird nicht in die Datenbank geschrieben und
nicht ins Protokoll aufgenommen — sie geht ausschliesslich als E-Mail an
`WEBSITE_KONTAKT_EMPFAENGER`. Das ist der Zweck der Karte und der Grund,
warum hier kein Modell, keine Migration und keine Tabelle existiert.

Warum der Endpunkt so gebaut ist
--------------------------------
* **Oeffentlich (`allow_guest=True`)** und damit ohne Sitzung. Die
  CSRF-Middleware prueft nur, WENN eine Sitzung mitkommt (`auth_middleware`);
  die Herkunftspruefung unten ist der Ersatz dafuer und gilt immer.
* **Herkunft (K3).** `Origin` — und, wenn der Browser keinen schickt (aeltere
  Browser, manche Formular-Posts), `Referer` — muss zum Host der Anfrage
  passen. Beide fehlen: **403**. Das ist fail closed und die einzige
  Bedingung, unter der wir eine fremde Seite von einer echten Besucherin
  unterscheiden koennen.
* **Honeypot (K1).** `website` ist fuer Menschen unsichtbar; ein Bot fuellt
  es. Ist es gefuellt: **200 `{"ok": true}` und keine Mail** — ein Bot soll
  nicht erfahren, dass er erkannt wurde. Der Honeypot greift VOR der
  Feldpruefung, damit ein Bot kein Feld-Feedback bekommt; gezaehlt wird die
  Anfrage trotzdem gegen die Bremse, sonst waere diese gratis umgehbar.
* **Validierung (K2).** Je Feld eine generische deutsche Meldung, keine
  Stacktraces, keine Python-Signaturen (SEC-7/8). Laengen werden auf
  Zeichen gezaehlt (nicht Bytes) und VOR jeder Weiterverarbeitung geprueft.
* **Kopfzeilen-Injektion.** Betreff ist eine Konstante; der Name steht nur im
  Text und wird von Zeilenumbruechen befreit; die Adresse geht als Reply-To
  erst raus, nachdem sie durch `email.headerregistry` gepasst hat (dieselbe
  Pruefung, die `EmailMessage` selbst ansetzt) — ein `\\r\\n` ueberlebt keine
  der beiden Stufen.
* **Nichts ins Log.** Ins Protokoll gehen nur „Kontaktmail versendet" bzw.
  der FEHLERTYP. Name, Adresse, Nachricht und Zeitpunkt stehen in keiner
  Logzeile — dieselbe Zusage wie im Mailversand-Modul.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    RateLimitError,
    ValidationError,
    throw,
)

#: WEB-10: Der Kontakt-Endpunkt traegt den Namen „website.kontakt_senden" —
#: die Karte legt den Pfad fest, und die Website (Primo) baut das Formular
#: dagegen. Das Modul liegt in `diakronos_app.website` (dort gehoert es
#: fachlich hin); der Frappe-Originalpfad ist `diakronos.diakronos.api.website`
#: — dieselbe Konvention wie `api/website.py`, nur mit dem neuen Namen.
FRAPPE_MODULE = "diakronos.diakronos.api.website"

#: Register-Kurzpfad des Endpunkts. `@whitelist` leitet den Namen aus Modul und
#: Funktion ab (`kontakt.kontakt_senden`); die Karte verlangt
#: `website.kontakt_senden`. Der Alias entsteht über DIESELBE Funktion und
#: traegt damit dieselben Optionen (`allow_guest=True`).
_KURZPFAD = "website.kontakt_senden"

logger = logging.getLogger("diakronos_app.website.kontakt")

#: Fester Betreff — KEINE Eingabe, KEIN Praefix aus dem Formular (K4).
BETREFF = "Kontaktformular Website"

# Grenzen der Felder (K2).
NAME_MIN, NAME_MAX = 1, 100
EMAIL_MAX = 254
NACHRICHT_MIN, NACHRICHT_MAX = 10, 5000

#: Groesste zulaessige Anfrage (Bytes). 5000 Zeichen Nachricht plus drei
#: kleine Felder passen bequem hinein; alles darueber ist kein Formular,
#: sondern ein Rumpf-Angriff und wird abgelehnt, bevor `json.loads` laeuft.
MAX_KOERPER = 64 * 1024

#: Zeitlimit fuers Nachladen des Rumpfes (Sekunden) — wie im Methoden-Router
#: (`_read_args`): ein haengender Client darf den Worker nicht blockieren.
KOERPER_ZEITLIMIT = 10.0

#: Zeichen, die in einem Kopfzeilenfeld nicht vorkommen duerfen. Sie werden
#: aus dem Text ENTFERNT (nicht ersetzt): ein Angreifer soll nicht per
#: Zeilenumbruch einen `Bcc:`-Kopf erzeugen koennen.
_STEUERZEICHEN = re.compile(r"[\r\n\x00\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]+")

# Absichtlich eng und ohne Sonderfaelle: eine Adresse wie im RFC-Header
# (`local@domain.tld`), keine Anzeigenamen, keine Kommentare, keine
# Adresslisten. Was hier nicht passt, ist fuer einen Reply-To nicht brauchbar.
_EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}")

#: Nur Leerraum (Leerzeichen, Tab, Umbruch …). Ein Honeypot-Wert, der
#: ausschliesslich daraus besteht, ist NICHT leer — siehe `honeypot_gefuellt`.
_NUR_LEERRAUM = re.compile(r"\s*\Z")

#: Zeitformat im Mailtext (deutsche Schreibweise, Ortszeit der Gemeinde).
_ZEIT = "%d.%m.%Y um %H:%M Uhr"


# ── Herkunft ───────────────────────────────────────────────────────────────


def _host(wert: str) -> str:
    """`https://example.org:8443/pfad` -> `example.org` (klein, ohne Port)."""
    from urllib.parse import urlsplit

    roh = str(wert or "").strip()
    if not roh:
        return ""
    teile = urlsplit(roh if "://" in roh else f"//{roh}")
    return (teile.hostname or "").lower().strip(".")


def herkunft_ist_eigen(request) -> bool:
    """True, wenn `Origin`/`Referer` zum Host DIESER Anfrage passen (K3).

    Geprueft wird zuerst `Origin` (der Kopf, den ein Formular-`fetch` immer
    setzt), danach `Referer`. Steht dort eine FREMDE Adresse, ist die Antwort
    `False` — auch dann, wenn der jeweils andere Kopf passt: eine Anfrage von
    einer fremden Seite soll nicht durch den zweiten Kopf durchrutschen.
    Fehlen beide, ist das Ergebnis ebenfalls `False` (fail closed).

    `X-Forwarded-Host` wird NICHT gelesen: der Kopf ist frei setzbar, und
    `settings.behind_proxy` ist eine Zusage ueber die ABSENDER-Adresse. Der
    Vergleich mit dem Host dieser Anfrage genuegt, weil der Eingang (nginx)
    den Kopf `Host` unveraendert durchreicht.
    """
    host = _host(request.headers.get("host", ""))
    if not host:
        return False
    for kopf in ("origin", "referer"):
        wert = request.headers.get(kopf, "").strip()
        if not wert:
            continue
        if kopf == "origin" and wert.lower() == "null":
            # `Origin: null` (Sandbox-iframe, file://) ist keine eigene Seite.
            return False
        if _host(wert) != host:
            return False
    return bool(request.headers.get("origin") or request.headers.get("referer"))


# ── Feldpruefung ───────────────────────────────────────────────────────────


def _text(wert: Any) -> str:
    """Eingabe als Text; `None` wird zur leeren Zeichenkette."""
    if wert is None:
        return ""
    if isinstance(wert, str):
        return wert
    if isinstance(wert, bool):
        # `true`/`false` sind KEIN Name und KEINE Nachricht.
        return ""
    return str(wert)


def _saubere_kopfzeile(wert: str) -> str:
    """Zeilenumbrueche und Steuerzeichen aus einem Kopfzeilen-Anteil entfernen."""
    return _STEUERZEICHEN.sub(" ", wert).strip()


def email_gueltig(adresse: str) -> bool:
    """Formpruefung einer Absenderadresse (K2/K3).

    Drei Stufen, damit eine Kopfzeilen-Injektion nicht nur „unwahrscheinlich"
    ist: Laenge, Zeichenform und der Parser des Mailpakets selbst. `EmailMessage`
    wuerde einen `\\r\\n` in einer Adresse als `ValueError` abweisen — hier wird
    das VOR dem Versand entschieden, damit der Besucher eine Feldmeldung sieht
    statt einer 503.
    """
    roh = str(adresse or "").strip()
    if not roh or len(roh) > EMAIL_MAX:
        return False
    if _STEUERZEICHEN.search(roh) or any(z.isspace() for z in roh):
        return False
    if _EMAIL.fullmatch(roh) is None:
        return False
    from email.headerregistry import Address

    try:
        Address(addr_spec=roh)
    except Exception:  # noqa: BLE001 — jede Parser-Ablehnung ist ein „nein"
        return False
    return True


def _als_ja(wert: Any) -> bool:
    """Nur ein echtes `true` zaehlt (K2: `einwilligung === true`)."""
    return wert is True


def pruefe_felder(daten: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Prueft die Eingabe und liefert `(bereinigt, fehler)`.

    `fehler` ist je Feld eine generische Meldung (K2); ist es nicht leer, wird
    NICHTS verschickt. `bereinigt` traegt die fuer die Mail verwendeten Werte
    (getrimmt, ohne Steuerzeichen in Name/Adresse).
    """
    name = _text(daten.get("name")).strip()
    email = _text(daten.get("email")).strip()
    nachricht = _text(daten.get("nachricht"))

    fehler: dict[str, str] = {}
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        fehler["name"] = f"Bitte gib einen Namen mit {NAME_MIN} bis {NAME_MAX} Zeichen an."
    elif _STEUERZEICHEN.search(name):
        # Ein Name mit Zeilenumbruch ist kein Name — und darf nie in eine
        # Kopfzeile geraten.
        fehler["name"] = "Bitte gib einen Namen ohne Zeilenumbrüche an."

    if not email:
        fehler["email"] = "Bitte gib eine E-Mail-Adresse an."
    elif len(email) > EMAIL_MAX:
        fehler["email"] = f"Die E-Mail-Adresse darf höchstens {EMAIL_MAX} Zeichen haben."
    elif not email_gueltig(email):
        fehler["email"] = "Das sieht nicht wie eine gültige E-Mail-Adresse aus."

    # Umbrueche in der Nachricht sind erlaubt (Fliesstext) — gezaehlt wird der
    # Text ohne Steuerzeichen, damit 5000 Umbrueche keine 5000-Zeichen-Nachricht
    # vortaeuschen. Fuer die Mail bleiben sie erhalten.
    zeichen = len(_STEUERZEICHEN.sub("", nachricht))
    if zeichen < NACHRICHT_MIN:
        fehler["nachricht"] = (
            f"Bitte schreibe mindestens {NACHRICHT_MIN} Zeichen."
        )
    elif zeichen > NACHRICHT_MAX:
        fehler["nachricht"] = (
            f"Die Nachricht darf höchstens {NACHRICHT_MAX} Zeichen haben."
        )

    if not _als_ja(daten.get("einwilligung")):
        fehler["einwilligung"] = (
            "Ohne Einwilligung in die Verarbeitung darf die Nachricht nicht "
            "gesendet werden."
        )

    bereinigt = {
        "name": _saubere_kopfzeile(name),
        "email": _saubere_kopfzeile(email),
        "nachricht": nachricht,
    }
    return bereinigt, fehler


def honeypot_gefuellt(daten: dict[str, Any]) -> bool:
    """True, wenn das unsichtbare Feld `website` Inhalt hat (K1).

    Auch reine Leerzeichen zaehlen als gefuellt: ein Mensch sieht das Feld
    nicht und tippt nichts hinein; ein Bot fuellt es — und ein Skript, das
    „nur zur Sicherheit" ein Leerzeichen setzt, ist kein Mensch.
    """
    wert = daten.get("website")
    if wert is None:
        return False
    # NUR der leere Text ist „leer". Ein Leerzeichen, eine Zahl, eine Liste,
    # `true` — alles zaehlt als gefuellt (siehe oben): ein Mensch tippt dort
    # nichts, und ein Skript, das „zur Sicherheit" etwas setzt, ist kein Mensch.
    if isinstance(wert, str):
        return wert != ""
    return True


# ── Mail ───────────────────────────────────────────────────────────────────


def mailtext(bereinigt: dict[str, str], *, jetzt: datetime | None = None) -> str:
    """Der Text der Kontaktmail (K4): Name, Adresse, Nachricht, Zeitpunkt."""
    from zoneinfo import ZoneInfo

    from diakronos_app.settings import settings

    try:
        zone = ZoneInfo(str(settings.calendar_timezone or "Europe/Berlin"))
    except Exception:  # noqa: BLE001 — ohne Zone bleibt UTC
        zone = None
    zeitpunkt = (jetzt or datetime.now(tz=zone)).strftime(_ZEIT)
    return (
        "Neue Anfrage über das Kontaktformular der Website.\n\n"
        f"Name:      {bereinigt['name']}\n"
        f"E-Mail:    {bereinigt['email']}\n"
        f"Zeitpunkt: {zeitpunkt}\n\n"
        "Nachricht:\n"
        f"{bereinigt['nachricht'].strip()}\n\n"
        "— Diese Nachricht wurde automatisch vom Kontaktformular der Website "
        "gesendet. Antworten gehen direkt an die oben genannte Adresse.\n"
    )


class KontaktNichtEingerichtet(RuntimeError):
    """`WEBSITE_KONTAKT_EMPFAENGER` fehlt — es wurde NICHTS versucht (K4, 503)."""


def _absenderzeile(bereinigt: dict[str, str]) -> str:
    """`Erika Beispiel <erika@example.org>` — beide Teile sind geprueft.

    Der Name ist bereits von Steuerzeichen befreit (`pruefe_felder`), die
    Adresse hat den Mail-Parser passiert. Zusaetzlich entfernt
    `formataddr`/`Address` jede verbliebene Spitze Klammer korrekt — ein
    `>` im Namen kann die Adresse nicht „aufbrechen".
    """
    from email.utils import formataddr

    return formataddr((bereinigt["name"], bereinigt["email"]))


def sende_kontaktmail(bereinigt: dict[str, str]) -> None:
    """Verschickt die Kontaktmail (K4).

    An = `WEBSITE_KONTAKT_EMPFAENGER` (Einstellung/ENV), Betreff = `BETREFF`,
    Reply-To = Absenderadresse. Wirft `KontaktNichtEingerichtet`, wenn kein
    Empfaenger eingerichtet ist, und `mailversand.MailVersandFehler`, wenn der
    Versand scheitert.

    Zwei Wege, EIN Nachrichtenaufbau (`Mail.als_nachricht`):

      * **Betrieb**: `mailversand.sende(...)` — Verbindung, TLS, Anmeldung,
        Zeitlimit und Fehlerbehandlung liegen dort (eine Wahrheit).
      * **Testnaht** (`mailversand.VERBINDUNG` gesetzt): derselbe Aufbau gegen
        die Attrappe, zusaetzlich mit sichtbarem `Reply-To`. Die Naht kennt
        keine Reply-To-Uebergabe, und eine Zusage, die im Test nicht messbar
        ist, ist keine.
    """
    from diakronos_app import mailversand
    from diakronos_app.settings import settings

    empfaenger = str(settings.website_kontakt_empfaenger or "").strip()
    if not empfaenger:
        raise KontaktNichtEingerichtet()

    mail = mailversand.Mail(
        an=empfaenger,
        betreff=BETREFF,
        text=mailtext(bereinigt),
        antwort_an=_absenderzeile(bereinigt),
    )

    verbindung = getattr(mailversand, "VERBINDUNG", None)
    if verbindung is None:
        # Betrieb: `sende` kapselt Verbindung, Anmeldung, TLS und Fehler.
        mailversand.sende(mail)
        return

    # Testnaht: derselbe Aufbau, sichtbar gegen die Attrappe.
    einstellungen = mailversand.einstellungen_lesen()
    if einstellungen is None:
        raise KontaktNichtEingerichtet()
    nachricht = mail.als_nachricht(einstellungen.absender, einstellungen.absender_name)
    try:
        if einstellungen.sicherheit == "starttls":
            verbindung.ehlo()
            if not verbindung.has_extn("starttls"):
                raise mailversand.MailVersandFehler(
                    "Der Mailserver unterstützt kein STARTTLS — Versand abgebrochen."
                )
            verbindung.starttls()
        if einstellungen.benutzername:
            verbindung.login(einstellungen.benutzername, einstellungen.passwort)
        verbindung.send_message(nachricht)
    except mailversand.MailVersandFehler:
        raise
    except Exception as ex:  # noqa: BLE001 — jede Ursache wird zur fachlichen Meldung
        raise mailversand.MailVersandFehler(
            "Der Versand der E-Mail ist fehlgeschlagen.",
            art=mailversand._art(ex),  # noqa: SLF001 — bewusst dieselbe Einordnung
        ) from None


# ── Endpunkt ───────────────────────────────────────────────────────────────


async def _lese_json(request) -> dict[str, Any] | None:
    """JSON-Koerper als dict — `None`, wenn kein JSON-Objekt ankommt (400).

    Der Methoden-Router liefert `request` herein und ruft Endpunkte ASYNCHRON
    auf, `body()` wird also hier gelesen (`await`). Der Router selbst liest den
    Rumpf nicht mehr vor — sonst haengt die Endpunkt-Entscheidung „nur POST"
    an einem Zeitlimit des Routers, das sie nichts angeht.

    Grenzen: nur `application/json`, hoechstens `MAX_KOERPER` Bytes und ein
    eigenes Zeitlimit (`KOERPER_ZEITLIMIT`) — ein haengender Client darf den
    Worker nicht blockieren.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return None
    try:
        body = await asyncio.wait_for(request.body(), timeout=KOERPER_ZEITLIMIT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001 — jeder Lesefehler ist ein 400
        return None
    if not body or len(body) > MAX_KOERPER:
        return None
    try:
        daten = json.loads(body)
    except (ValueError, TypeError):
        return None
    return daten if isinstance(daten, dict) else None


def _antwort(status: int, koerper: dict[str, Any], **headers):
    from starlette.responses import JSONResponse

    antwort = JSONResponse(status_code=status, content=koerper)
    antwort.headers["Cache-Control"] = "no-store"
    for name, wert in headers.items():
        antwort.headers[name] = wert
    return antwort


@whitelist(allow_guest=True)
async def kontakt_senden(request=None):
    """Nimmt eine Kontaktanfrage an und sendet SIE als E-Mail (K1–K4).

    Rueckgabe (Vertrag fuer WEB-9b):

        200 {"message": {"ok": true}}
        400 {"message": "Bitte prüfe die markierten Felder.",
             "felder": {"<feld>": "<Satz>"}, "exception": ..., "exc_type": ...}
        403 {"message": "…", "exception": "PermissionError", "exc_type": "PermissionError"}
        429 {"message": "…", "exception": "Error", "exc_type": "Error"}
        503 {"message": "…", "exception": "Error", "exc_type": "Error"}

    Alles andere als POST ist 403 (`PermissionError`, Frappe-Konvention) — der
    Router laesst GET/PUT/PATCH fuer alle Endpunkte offen, die Entschuldigung
    dafuer steht hier und nicht dort.

    Reihenfolge (jede Stufe kann abbrechen, KEINE Stufe speichert):

      1. Methode (403) — vor allem anderen, auch vor der Herkunft.
      2. Herkunft (403) — eigene Domain, sonst nichts.
      3. Bremse (429/503) — VOR dem Honeypot gezaehlt, sonst waere sie gratis.
      4. JSON lesen (400).
      5. Honeypot (200, KEINE Mail).
      6. Feldpruefung (400 mit `felder`).
      7. Empfaenger/Mailversand (503) — Betreff fest, Reply-To geprueft.
    """
    from diakronos_app import request_context
    from diakronos_app.anmeldung import kontaktbremse
    from diakronos_app.frappe_compat.router import _fehler_koerper

    methode = str(getattr(request, "method", "") or "").upper()
    if methode != "POST":
        logger.info("Kontaktformular per %s abgewiesen (nur POST).", methode or "?")
        return _antwort(403, _fehler_koerper(
            "Diese Adresse darf nur per POST aufgerufen werden.",
            "PermissionError", 403))

    if request is None or not herkunft_ist_eigen(request):
        logger.warning("Kontaktformular: fremde oder fehlende Herkunft abgewiesen.")
        return _antwort(403, _fehler_koerper(
            "Die Anfrage kam nicht von der Website dieser Gemeinde.",
            "PermissionError", 403))

    try:
        erlaubt, grund = kontaktbremse.pruefe(request_context.zaehler_client_ip())
    except Exception as ex:  # noqa: BLE001 — Bremse faellt aus: fail closed
        logger.warning("Kontaktformular: Bremse nicht erreichbar (%s).", type(ex).__name__)
        return _antwort(503, _fehler_koerper(
            "Das Kontaktformular ist gerade nicht verfügbar. Bitte später erneut.",
            "RateLimitError", 503))

    if not erlaubt:
        logger.warning("Kontaktformular gebremst (Grund=%s).", grund or "unbekannt")
        return _antwort(429, _fehler_koerper(
            kontaktbremse.fehlermeldung(), "RateLimitError", 429))

    daten = await _lese_json(request)
    if daten is None:
        return _antwort(400, _fehler_koerper(
            "Die Anfrage konnte nicht gelesen werden.", "ValidationError", 400))

    if honeypot_gefuellt(daten):
        # Bot: hoeflich „ok", aber KEINE Mail und kein Hinweis auf die Erkennung.
        logger.info("Kontaktformular: Honeypot gefüllt — keine Mail.")
        return _antwort(200, {"message": {"ok": True}})

    bereinigt, fehler = pruefe_felder(daten)
    if fehler:
        koerper = _fehler_koerper(
            "Bitte prüfe die markierten Felder.", "ValidationError", 400)
        koerper["felder"] = fehler
        return _antwort(400, koerper)

    try:
        sende_kontaktmail(bereinigt)
    except KontaktNichtEingerichtet:
        logger.warning("Kontaktformular: WEBSITE_KONTAKT_EMPFAENGER fehlt.")
        return _antwort(503, _fehler_koerper(
            "Das Kontaktformular ist nicht eingerichtet.", "Error", 503))
    except Exception as ex:  # noqa: BLE001 — Versandfehler: 503, ohne Interna
        # NUR der Fehlertyp geht ins Protokoll — nie Name, Adresse, Nachricht.
        logger.warning("Kontaktmail nicht versendet (%s).", type(ex).__name__)
        return _antwort(503, _fehler_koerper(
            "Die Nachricht konnte gerade nicht versendet werden. "
            "Bitte später erneut versuchen oder die Gemeinde direkt anschreiben.",
            "Error", 503))

    logger.info("Kontaktmail versendet.")
    return _antwort(200, {"message": {"ok": True}})


def _registriere_kurzpfad() -> None:
    """Traegt `website.kontakt_senden` in das Register ein (Karte, K1).

    `@whitelist` vergibt den Namen aus Modul und Funktion
    (`kontakt.kontakt_senden`). Der Pfad der Karte ist `website.kontakt_senden`
    — er wird hier auf DIESELBE Funktion gelegt; damit gelten auch dieselben
    Optionen (`allow_guest=True`, `router._guest_denied` liest sie ueber
    `options_for(fn)` und nicht ueber den Namen).

    Idempotent: ein zweiter Import ueberschreibt nur denselben Eintrag.
    """
    from diakronos_app.frappe_compat.registry import register_with_frappe_module

    register_with_frappe_module("website", "kontakt_senden", kontakt_senden)


# Beim Import ausfuehren (das Modul wird von `diakronos_app.api` gezogen, also
# vor dem ersten Methodenaufruf). Bewusst hier und nicht im Dekorator: der
# Registerweg ist die dokumentierte Schnittstelle fuer Zusatzpfade.
_registriere_kurzpfad()


__all__ = [
    "BETREFF",
    "KontaktNichtEingerichtet",
    "email_gueltig",
    "herkunft_ist_eigen",
    "honeypot_gefuellt",
    "kontakt_senden",
    "mailtext",
    "pruefe_felder",
    "sende_kontaktmail",
]

# Unbenutzt importiert waere `throw`/`ValidationError`/`RateLimitError` ein
# Rest aus dem ersten Entwurf — die Endpunkt-Antworten entstehen bewusst als
# JSONResponse (eigener Koerper mit `felder`), nicht ueber die Compat-Exception.
del throw, ValidationError, RateLimitError, FrappePermissionError
