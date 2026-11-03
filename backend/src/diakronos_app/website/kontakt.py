"""WEB-10 — Kontaktformular der Website: sendet NUR eine E-Mail.

Der Vertrag (WEB-9b baut das Formular dagegen)
=============================================

    POST {Praefix}/api/method/website.kontakt_senden        (allow_guest)

    JSON: {"name": str, "email": str, "nachricht": str,
           "einwilligung": true, "website": str,
           "postfach": str,           # optional, BS-1c/K1
           "betreff_zusatz": str}     # optional, BS-1c/K3

    Erfolg:            200 {"message": {"ok": true}}
    Feldpruefung:      400 {"message": "...", "felder": {"<feld>": "..."}, ...}
    fremde Herkunft:   403
    andere Methode:    403
    zu viele Anfragen: 429
    nicht eingerichtet/ Versandfehler/ Bremse aus: 503
    OPTIONS (Preflight): 204 mit CORS-Kopfzeilen fuer die Primo-Herkunft

    GET {Praefix}/api/method/website.oeffentlich.postfaecher  (allow_guest)

    Erfolg: 200 {"message": {"postfaecher": [{"slug": str, "bezeichnung": str}]}}
    (nur aktive Postfaecher, NIE die E-Mail-Adresse — BS-1c/K2)
    zu viele Anfragen: 429; Bremse aus: 503 (eigener Eimer der Bremse, F5)

BS-1c2 — Nachbesserung nach dem Opus-Review
============================================

  F1  Die Postfach-Liste steht in der EXAKTEN Ausnahmemenge der
      Sec-Fetch-Site-Schranke (`auth_middleware._OEFFENTLICHE_WEBSITE_NAMEN`,
      samt Aliassen). Sonst waere sie von der Primo-Herkunft (cross-site)
      unerreichbar.
  F2  Herkunft EXAKT: Schema + Host + Port, normalisiert (klein,
      Standardport weg, Pfad/Query weg) — EINE Funktion
      `_normalisiere_herkunft`, ein Aufruf fuer `PRIMO_PUBLIC_URL`.
  F3  Der Preflight (`router._preflight`) bekommt den Request NUR noch bei
      ausdruecklicher Anmeldung `@whitelist(preflight="self")`, nicht mehr
      nach Funktionsgestalt (`async def` + `request`).
  F4  `Vary: Origin` steht auf JEDER Antwort dieses Moduls — Liste,
      Formular (jeder Status) und Preflight.
  F5  Die Postfach-Liste hat einen EIGENEN Eimer der Kontaktbremse
      (`kontaktbremse.pruefe_liste`).
  F6  Der Betreff-Zusatz lehnt die VOLLE Steuerzeichenmenge ab
      (`[\\x00-\\x1f\\x7f\\x85\\u2028\\u2029]`), nicht nur Zeilenumbrueche.
  F7  Postfaecher angelegt, aber keines aktiv -> `kontakt_senden` bleibt 503
      (bewusst abgeschaltet, kein stiller Rueckfall); die Liste ist dann leer.

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

#: Fester Betreff — KEINE Eingabe (BS-1c/K3 haengt hoechstens den geprueften
#: Zusatz `betreff_zusatz` an, getrennt durch `BETREFF_TRENNER`).
BETREFF = "Kontaktformular Website"

#: Trenner zwischen festem Betreff und `betreff_zusatz` (BS-1c/K3).
BETREFF_TRENNER = " - "

#: Hoechstlaenge des Zusatzes im Betreff (BS-1c/K3).
BETREFF_ZUSATZ_MAX = 100

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

#: BS-1c2 (F6): die VOLLE Steuerzeichenmenge nach RFC 5322 fuer ein
#: Kopfzeilenfeld — ``[\\x00-\\x1f\\x7f\\x85\\u2028\\u2029]``. `_STEUERZEICHEN`
#: enthielt nur die Zeilenumbrueche und einige Trenner; `\\t`, `\\x08`, `\\x1f`
#: und `\\x7f` kamen dort NICHT vor und landeten im Betreff. Fuer den
#: Betreff-Zusatz gilt deshalb diese strengere Menge (Ablehnung, nicht
#: Bereinigung).
_KOPFZEILEN_STEUERZEICHEN = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]")

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

#: Standardports: werden in einer Herkunft NICHT genannt (`https://x:443` →
#: `https://x`). BS-1c2/F2.
_STANDARDPORTS = {"http": 80, "https": 443}


def _host(wert: str) -> str:
    """`https://example.org:8443/pfad` -> `example.org` (klein, ohne Port)."""
    from urllib.parse import urlsplit

    roh = str(wert or "").strip()
    if not roh:
        return ""
    teile = urlsplit(roh if "://" in roh else f"//{roh}")
    return (teile.hostname or "").lower().strip(".")


def _normalisiere_herkunft(wert: str) -> str:
    """Eine Herkunft auf ``schema://host[:port]`` bringen — oder ``""`` (F2).

    BS-1c2/F2: `PRIMO_PUBLIC_URL` und die `Origin`-Kopfzeile wurden bis BS-1c
    nur ueber den HOST verglichen. Damit galt `http://x` als dieselbe Herkunft
    wie `https://x`, und `https://x:8443` wie `https://x` — beides ist falsch:
    eine Herkunft ist laut Standard das Tripel (Schema, Host, Port).

    Regeln (einmal, an EINER Stelle):

      * Schema und Host **klein** (`HTTPS://Example.ORG` == `https://example.org`);
      * nur `http`/`https` — alles andere (auch `file:`, `null`) ergibt ``""``;
      * der **Standardport** faellt weg (`https://x:443` -> `https://x`);
      * **Pfad, Query und Fragment** fallen weg (`https://x/diakronos` ->
        `https://x`);
      * Steuerzeichen/Leerraum: ``""`` (nichts davon gehoert in eine Kopfzeile).
    """
    from urllib.parse import urlsplit

    roh = str(wert or "").strip()
    if not roh or _STEUERZEICHEN.search(roh) or any(z.isspace() for z in roh):
        return ""
    if "://" not in roh:
        return ""
    teile = urlsplit(roh)
    schema = (teile.scheme or "").lower()
    if schema not in _STANDARDPORTS:
        return ""
    host = (teile.hostname or "").lower().strip(".")
    if not host:
        return ""
    try:
        port = teile.port
    except ValueError:  # z. B. `https://x:abc` — kein Port, keine Herkunft
        return ""
    if port is None or port == _STANDARDPORTS[schema]:
        return f"{schema}://{host}"
    return f"{schema}://{host}:{port}"


def _primo_herkunft() -> str:
    """Die Primo-Herkunft aus den Einstellungen, normalisiert — oder ``""``.

    EINE Stelle fuer Herkunftsvergleich und `cors_herkunft` (F2): bis BS-1c
    wurde `PRIMO_PUBLIC_URL` zweimal unabhaengig gelesen, und beide Stellen
    konnten auseinanderlaufen.
    """
    try:
        from diakronos_app.settings import settings

        return _normalisiere_herkunft(settings.primo_public_url_effektiv)
    except Exception:  # noqa: BLE001 — ohne Einstellung gibt es keine Primo-Herkunft
        return ""


def _eigenes_schema(request) -> str:
    """Das Schema, unter dem der CLIENT die Anfrage gestellt hat.

    BS-1bc (Proxy-Fix): Bisher kam das Schema aus `request.url.scheme`. Hinter
    einem TLS-Vorbau (Eingang/nginx, NPM) fuehrt der Proxy die Verbindung zum
    Backend ueber HTTP; `request.url.scheme` waere dann `http`, waehrend der
    Browser `https` meldet. Ein `Origin: https://…` passte damit nicht mehr auf
    die eigene Herkunft — das EIGENE Formular wurde mit 403 abgewiesen, sobald
    `BEHIND_PROXY` gesetzt war und uvicorn die Kopfzeilen nicht selbst
    auswertet (`--forwarded-allow-ips` ist NICHT gesetzt).

    Deshalb: bei `settings.behind_proxy` gilt `X-Forwarded-Proto` (erster
    Wert, nur `http`/`https`) — dieselbe Regel wie `api/auth.py`
    `_eigene_herkunft`. Ohne die Einstellung bleibt es beim Schema der
    Anfrage: der Kopf ist frei setzbar, und ohne Zusage ueber den Proxy darf
    ihn niemand faelschen. `X-Forwarded-Host` wird NIE gelesen (siehe
    `herkunft_ist_eigen`).
    """
    from diakronos_app.settings import settings

    eigenes = str(getattr(getattr(request, "url", None), "scheme", "") or "").lower()
    if not bool(getattr(settings, "behind_proxy", False)):
        return eigenes
    kopf = getattr(request, "headers", {}) or {}
    weitergeleitet = str(kopf.get("x-forwarded-proto") or "").strip().lower()
    erster = weitergeleitet.split(",")[0].strip()
    if erster in _STANDARDPORTS:
        return erster
    return eigenes


def _herkunfts_erlaubt(request) -> set[str]:
    """Alle Herkünfte, die als eigene gelten: eigener Host + `PRIMO_PUBLIC_URL`.

    BS-1c/K4: Primo kann auf einer eigenen Herkunft laufen (G3). Dann ist die
    Herkunft der Primo-Seite keine „fremde" Seite — sie ist die Website dieser
    Gemeinde. Der eigene Host der Anfrage wird zum Vergleich ebenfalls
    normalisiert (Schema der Anfrage + `Host`-Kopf), damit `http`/`https` und
    Standardport nicht zu Fehlentscheidungen fuehren.

    BS-1c2/F2: verglichen wird die HERKUNFT (Schema + Host + Port), nicht mehr
    der nackte Host — ein falsches Schema oder ein falscher Port ist eine
    fremde Herkunft.

    BS-1bc (Proxy-Fix): Das Schema kommt bei `BEHIND_PROXY` aus
    `X-Forwarded-Proto` (`_eigenes_schema`).
    """
    erlaubt: set[str] = set()
    schema = _eigenes_schema(request)
    host = str((getattr(request, "headers", {}) or {}).get("host", "") or "")
    if host:
        erlaubt.add(_normalisiere_herkunft(f"{schema or 'http'}://{host}"))
    primo = _primo_herkunft()
    if primo:
        erlaubt.add(primo)
    return erlaubt - {""}


def herkunft_ist_eigen(request) -> bool:
    """True, wenn `Origin`/`Referer` zu einer erlaubten Herkunft passen (K3/F2).

    Geprueft wird zuerst `Origin` (der Kopf, den ein Formular-`fetch` immer
    setzt), danach `Referer`. Steht dort eine FREMDE Herkunft, ist die Antwort
    `False` — auch dann, wenn der jeweils andere Kopf passt: eine Anfrage von
    einer fremden Seite soll nicht durch den zweiten Kopf durchrutschen.
    Fehlen beide, ist das Ergebnis ebenfalls `False` (fail closed).

    BS-1c2/F2: Der Vergleich ist EXAKT (`_normalisiere_herkunft` auf beiden
    Seiten) — Schema, Host und Port muessen passen. Bis BS-1c genuegte der
    Host; damit war `http://…` fuer `https://…` eine eigene Herkunft und
    `:8443` gleich `:443`.

    `X-Forwarded-Host` wird NICHT gelesen: der Kopf ist frei setzbar, und
    `settings.behind_proxy` ist eine Zusage ueber die ABSENDER-Adresse. Fuer
    den eigenen Host genuegt der `Host`-Kopf dieser Anfrage, weil der Eingang
    (nginx) ihn unveraendert durchreicht; laeuft Diakronos hinter einem
    TLS-Vorbau, gehoert die oeffentliche Adresse in `PRIMO_PUBLIC_URL`.
    """
    erlaubte_herkuenfte = _herkunfts_erlaubt(request)
    if not erlaubte_herkuenfte:
        return False
    gesehen = False
    for kopf in ("origin", "referer"):
        wert = str((getattr(request, "headers", {}) or {}).get(kopf, "") or "").strip()
        if not wert:
            continue
        if kopf == "origin" and wert.lower() == "null":
            # `Origin: null` (Sandbox-iframe, file://) ist keine eigene Seite.
            return False
        gesehen = True
        if _normalisiere_herkunft(wert) not in erlaubte_herkuenfte:
            return False
    return gesehen


def cors_herkunft(request) -> str:
    """Die Antwort-Herkunft fuer `Access-Control-Allow-Origin` — oder `""`.

    BS-1c/K4: Nur wenn die Anfrage von der Herkunft aus `PRIMO_PUBLIC_URL`
    kommt (also NICHT vom eigenen Host), ist ein CORS-Kopf noetig. Zurueck
    kommt dann genau diese Herkunft als ``schema://host[:port]`` — nie ``*``,
    nie eine Liste, nie mit Credentials, immer in normalisierter Form (F2:
    Standardport weg, Pfad weg, klein). Eine fremde Herkunft bekommt ``""``
    (der Endpunkt antwortet ihr mit 403, ohne CORS-Kopf).
    """
    primo = _primo_herkunft()
    if not primo:
        return ""
    kopf = getattr(request, "headers", {}) or {}
    origin = _normalisiere_herkunft(kopf.get("origin", ""))
    if not origin or origin != primo:
        return ""
    # Kommt die Anfrage schon auf der Primo-Herkunft an, ist sie die eigene
    # Herkunft — dann braucht sie kein CORS (gleiches Schema/Host/Port).
    schema = str(getattr(getattr(request, "url", None), "scheme", "") or "").lower()
    eigene_herkunft = _normalisiere_herkunft(f"{schema or 'http'}://{kopf.get('host', '')}")
    return "" if eigene_herkunft == primo else origin


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


def pruefe_betreff_zusatz(daten: dict[str, Any]) -> tuple[str, str]:
    """Prueft `betreff_zusatz` (BS-1c/K3) und liefert `(zusatz, fehler)`.

    Der Zusatz haengt an einem FESTEN Betreff — er ist der einzige
    Besuchertext, der in eine Kopfzeile gelangt. Deshalb dieselbe Regel wie
    beim Namen, nur strenger: hoechstens `BETREFF_ZUSATZ_MAX` Zeichen und
    JEDES Steuerzeichen aus `_KOPFZEILEN_STEUERZEICHEN` (also auch `\\r`,
    `\\n`, `\\t`, `\\x00`, `\\x7f`, `\\x85`, U+2028) fuehrt zur Ablehnung statt
    zur Bereinigung (BS-1c2/F6). Ein Formular, das einen Zeilenumbruch
    schickt, ist kein Tippfehler; es soll nicht stillschweigend „geheilt"
    werden. Fehlt das Feld oder ist es leer, gibt es keinen Zusatz.
    """
    if "betreff_zusatz" not in daten or daten.get("betreff_zusatz") is None:
        return "", ""
    wert = _text(daten.get("betreff_zusatz"))
    # Nur Raender aus LEERZEICHEN entfernen: `strip()` wuerde `"\r\n"` zu einem
    # leeren Zusatz machen und die Ablehnung umgehen (der Tester prueft genau
    # diesen Fall). Steuerzeichen bleiben stehen und werden unten abgelehnt.
    zusatz = wert.strip(" ")
    if not zusatz:
        return "", ""
    if len(zusatz) > BETREFF_ZUSATZ_MAX:
        return "", (
            f"Der Zusatz im Betreff darf höchstens {BETREFF_ZUSATZ_MAX} "
            "Zeichen haben."
        )
    if _KOPFZEILEN_STEUERZEICHEN.search(zusatz):
        return "", (
            "Der Zusatz im Betreff darf keine Zeilenumbrüche oder "
            "Steuerzeichen enthalten."
        )
    return zusatz, ""


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

    zusatz, zusatz_fehler = pruefe_betreff_zusatz(daten)
    if zusatz_fehler:
        fehler["betreff_zusatz"] = zusatz_fehler

    bereinigt = {
        "name": _saubere_kopfzeile(name),
        "email": _saubere_kopfzeile(email),
        "nachricht": nachricht,
        "postfach": _postfach_slug(daten),
        "betreff_zusatz": zusatz,
    }
    return bereinigt, fehler


def _postfach_slug(daten: dict[str, Any]) -> str:
    """Der gewuenschte Postfach-Slug aus der Eingabe ("" = keine Auswahl).

    Hier wird NUR der Text gelesen und getrimmt; ob es das Postfach gibt,
    entscheidet `postfach_waehlen` — und zwar erst, wenn die Felder in
    Ordnung sind (sonst verriete die Reihenfolge der Meldungen, welche Slugs
    existieren).
    """
    if "postfach" not in daten or daten.get("postfach") is None:
        return ""
    return _text(daten.get("postfach")).strip()


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


class PostfachUnbekannt(ValueError):
    """Der verlangte Postfach-Slug existiert nicht oder ist inaktiv (BS-1c/K1).

    Die Meldung ist bewusst generisch: sie nennt weder den Slug noch die
    vorhandenen Postfaecher — sonst liesse sich die Tabelle abfragen.
    """


def postfach_waehlen(slug: str) -> Any:
    """Loest den gewuenschten Slug in EIN Postfach auf (BS-1c/K1).

    Regel (Vertrag der Karte):

      * Slug angegeben -> genau dieses Postfach, **nur wenn aktiv**; sonst
        :class:`PostfachUnbekannt` (der Endpunkt antwortet 400).
      * Kein Slug -> das Postfach ``standard``, sonst das **erste aktive**
        nach ``sortierung`` (dann ``slug``), sonst — ohne jede Zeile — der
        Rueckfall ``WEBSITE_KONTAKT_EMPFAENGER``.

    Quelle ist ``website.freigaben.postfaecher_oeffentlich`` (dieselbe Wahrheit
    wie die oeffentliche Liste K2). Gibt ein :class:`website.freigaben.Postfach`
    zurueck. Liegt keine Zeile UND ist die Einstellung leer, wirft die
    Funktion :class:`KontaktNichtEingerichtet` (503 wie in WEB-10).
    """
    from diakronos_app.settings import settings
    from diakronos_app.website import freigaben as regeln

    sess, eigene = _postfach_sitzung()
    try:
        liste = regeln.postfaecher_oeffentlich(
            sess, settings.website_kontakt_empfaenger
        )
    finally:
        if eigene:
            sess.close()

    gewuenscht = str(slug or "").strip()
    if gewuenscht:
        for postfach in liste:
            if postfach.slug == gewuenscht:
                return postfach
        raise PostfachUnbekannt()

    for postfach in liste:
        if postfach.slug == regeln.POSTFACH_STANDARD:
            return postfach
    if liste:
        return liste[0]
    # Keine Zeile, kein Rueckfall: dieselbe 503 wie in WEB-10.
    raise KontaktNichtEingerichtet()


def _postfach_sitzung():
    """DB-Sitzung fuer die Postfach-Aufloesung — `(session, eigene)`.

    Der Endpunkt laeuft OHNE Anmeldung; es gibt also keinen Aufruf-Kontext,
    aus dem eine Sitzung kaeme. `db.sitzung_fuer_lesen` liefert die Sitzung des
    Aufrufs, wenn es eine gibt (Verwaltung, Tests), sonst eine eigene, die
    hier geschlossen wird. Nur LESE-Zugriff — der Endpunkt speichert nichts.
    """
    from diakronos_app import db as dbmod

    # Ueber das MODUL lesen, nicht ueber einen frueheren Import: `patched_db`
    # ersetzt `SessionLocal` (Tests/Naht) — eine eingefrorene Bindung wuerde
    # daran vorbeigehen und die echte `database_url` anfassen (Kartenregel 11).
    return dbmod.sitzung_fuer_lesen()


def betreff_mit_zusatz(zusatz: str) -> str:
    """`Kontaktformular Website` bzw. `… - <zugesatz>` (BS-1c/K3)."""
    text = str(zusatz or "").strip()
    if not text:
        return BETREFF
    return f"{BETREFF}{BETREFF_TRENNER}{text}"


def _absenderzeile(bereinigt: dict[str, str]) -> str:
    """`Erika Beispiel <erika@example.org>` — beide Teile sind geprueft.

    Der Name ist bereits von Steuerzeichen befreit (`pruefe_felder`), die
    Adresse hat den Mail-Parser passiert. Zusaetzlich entfernt
    `formataddr`/`Address` jede verbliebene Spitze Klammer korrekt — ein
    `>` im Namen kann die Adresse nicht „aufbrechen".
    """
    from email.utils import formataddr

    return formataddr((bereinigt["name"], bereinigt["email"]))


def sende_kontaktmail(bereinigt: dict[str, str], postfach=None) -> None:
    """Verschickt die Kontaktmail (K4, BS-1c/K1+K3).

    An = das aufgeloeste Postfach (BS-1c/K1) bzw. — ohne Postfach-Zeile —
    `WEBSITE_KONTAKT_EMPFAENGER`, Betreff = `BETREFF` plus geprueftem
    `betreff_zusatz`, Reply-To = Absenderadresse. Wirft
    `KontaktNichtEingerichtet`, wenn kein Empfaenger eingerichtet ist, und
    `mailversand.MailVersandFehler`, wenn der Versand scheitert.

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

    empfaenger = str(getattr(postfach, "email", "") or "").strip()
    if not empfaenger:
        empfaenger = str(settings.website_kontakt_empfaenger or "").strip()
    if not empfaenger:
        raise KontaktNichtEingerichtet()

    mail = mailversand.Mail(
        an=empfaenger,
        betreff=betreff_mit_zusatz(bereinigt.get("betreff_zusatz", "")),
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
    # BS-1c2 (F4): IMMER `Vary: Origin`. Die Antwort haengt an der Herkunft
    # (CORS-Kopf oder nicht) — ohne diesen Hinweis darf ein Zwischenspeicher
    # die Antwort der EINEN Herkunft an eine ANDERE ausliefern.
    antwort.headers["Vary"] = "Origin"
    for name, wert in headers.items():
        antwort.headers[name] = wert
    return antwort


def _cors_kopfzeilen(fremde_herkunft: str) -> dict[str, str]:
    """CORS-Antwortkopfzeilen fuer genau EINE fremde Herkunft (BS-1c/K4).

    Ohne Herkunft: nur `Vary: Origin` (die eigene Domain braucht kein CORS,
    aber die Antwort ist trotzdem herkunftsabhaengig — F4).
    Nie ``*``, nie eine Liste, nie ``Access-Control-Allow-Credentials`` — das
    Formular schickt keine Cookies, und der Endpunkt braucht keine Sitzung.
    """
    if not fremde_herkunft:
        return {"Vary": "Origin"}
    return {
        "Access-Control-Allow-Origin": fremde_herkunft,
        "Vary": "Origin",
    }


def _antwort_mit_cors(status: int, koerper: dict[str, Any], request, **headers):
    herkunft = cors_herkunft(request) if request is not None else ""
    kopf = {**_cors_kopfzeilen(herkunft), **headers}
    return _antwort(status, koerper, **kopf)


def _preflight(request):
    """Antwort auf OPTIONS (CORS-Preflight) fuer den Kontaktpfad (BS-1c/K4).

    204 ohne Inhalt. Erlaubt wird ``POST`` — mehr nimmt der Endpunkt nicht an.
    Eine fremde Herkunft bekommt 403 OHNE CORS-Kopfzeilen (der Browser bricht
    den echten Aufruf dann ab) — dieselbe Entscheidung wie beim POST.
    """
    from starlette.responses import Response

    if request is None or not herkunft_ist_eigen(request):
        logger.warning("Kontaktformular: Preflight aus fremder Herkunft abgewiesen.")
        return _antwort(403, {"message": "Die Anfrage kam nicht von der Website dieser Gemeinde."})

    herkunft = cors_herkunft(request)
    antwort = Response(status_code=204)
    antwort.headers["Cache-Control"] = "no-store"
    # BS-1c2 (F4): `Vary: Origin` IMMER — auch ohne CORS-Freigabe.
    antwort.headers["Vary"] = "Origin"
    if herkunft:
        antwort.headers["Access-Control-Allow-Origin"] = herkunft
        antwort.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        antwort.headers["Access-Control-Allow-Headers"] = "Content-Type"
        antwort.headers["Access-Control-Max-Age"] = "600"
    return antwort


@whitelist(methods=["POST"], preflight="self", allow_guest=True)
async def kontakt_senden(request=None):
    """Nimmt eine Kontaktanfrage an und sendet SIE als E-Mail (K1–K4).

    Rueckgabe (Vertrag fuer WEB-9b, erweitert um BS-1c):

        200 {"message": {"ok": true}}
        400 {"message": "Bitte prüfe die markierten Felder.",
             "felder": {"<feld>": "<Satz>"}, "exception": ..., "exc_type": ...}
        403 {"message": "…", "exception": "PermissionError", "exc_type": "PermissionError"}
        429 {"message": "…", "exception": "Error", "exc_type": "Error"}
        503 {"message": "…", "exception": "Error", "exc_type": "Error"}

    Zusatzfelder aus BS-1c (alle optional):
      ``postfach``        Slug aus ``website.oeffentlich.postfaecher`` (K1).
                          Unbekannt/inaktiv -> 400 im Feld ``postfach``.
      ``betreff_zusatz``  hoechstens 100 Zeichen ohne Zeilenumbruch (K3);
                          haengt an den festen Betreff.

    Alles andere als POST ist 403 (`PermissionError`, Frappe-Konvention) — der
    Router laesst GET/PUT/PATCH fuer alle Endpunkte offen, die Entschuldigung
    dafuer steht hier und nicht dort. OPTIONS beantwortet den CORS-Preflight
    (BS-1c/K4), BEVOR Methode/Herkunft des Formulars geprueft werden.

    Reihenfolge (jede Stufe kann abbrechen, KEINE Stufe speichert):

      1. Methode (403) — vor allem anderen, auch vor der Herkunft.
      2. Herkunft (403) — eigene Domain oder Primo-Herkunft, sonst nichts.
      3. Bremse (429/503) — VOR dem Honeypot gezaehlt, sonst waere sie gratis.
      4. JSON lesen (400).
      5. Honeypot (200, KEINE Mail).
      6. Feldpruefung (400 mit `felder`).
      7. Postfach aufloesen (400 im Feld `postfach` / 503 nicht eingerichtet).
      8. Mailversand (503) — Betreff fest + Zusatz, Reply-To geprueft.
    """
    from diakronos_app import request_context
    from diakronos_app.anmeldung import kontaktbremse
    from diakronos_app.frappe_compat.router import _fehler_koerper

    methode = str(getattr(request, "method", "") or "").upper()
    if methode == "OPTIONS":
        return _preflight(request)
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
        return _antwort_mit_cors(503, _fehler_koerper(
            "Das Kontaktformular ist gerade nicht verfügbar. Bitte später erneut.",
            "RateLimitError", 503), request)

    if not erlaubt:
        logger.warning("Kontaktformular gebremst (Grund=%s).", grund or "unbekannt")
        return _antwort_mit_cors(429, _fehler_koerper(
            kontaktbremse.fehlermeldung(), "RateLimitError", 429), request)

    daten = await _lese_json(request)
    if daten is None:
        return _antwort_mit_cors(400, _fehler_koerper(
            "Die Anfrage konnte nicht gelesen werden.", "ValidationError", 400), request)

    if honeypot_gefuellt(daten):
        # Bot: hoeflich „ok", aber KEINE Mail und kein Hinweis auf die Erkennung.
        logger.info("Kontaktformular: Honeypot gefüllt — keine Mail.")
        return _antwort_mit_cors(200, {"message": {"ok": True}}, request)

    bereinigt, fehler = pruefe_felder(daten)
    if fehler:
        koerper = _fehler_koerper(
            "Bitte prüfe die markierten Felder.", "ValidationError", 400)
        koerper["felder"] = fehler
        return _antwort_mit_cors(400, koerper, request)

    try:
        postfach = _postfach_zuordnen(bereinigt.get("postfach", ""))
    except PostfachUnbekannt:
        logger.warning("Kontaktformular: unbekanntes oder inaktives Postfach abgewiesen.")
        koerper = _fehler_koerper(
            "Bitte prüfe die markierten Felder.", "ValidationError", 400)
        koerper["felder"] = {
            "postfach": "Dieses Postfach gibt es nicht. Bitte wähle eines aus der Liste."
        }
        return _antwort_mit_cors(400, koerper, request)
    except KontaktNichtEingerichtet:
        logger.warning("Kontaktformular: WEBSITE_KONTAKT_EMPFAENGER fehlt.")
        return _antwort_mit_cors(503, _fehler_koerper(
            "Das Kontaktformular ist nicht eingerichtet.", "Error", 503), request)
    except Exception as ex:  # noqa: BLE001 — Datenbankfehler: 503, ohne Interna
        logger.warning("Kontaktformular: Postfach nicht lesbar (%s).", type(ex).__name__)
        return _antwort_mit_cors(503, _fehler_koerper(
            "Das Kontaktformular ist gerade nicht verfügbar. Bitte später erneut.",
            "Error", 503), request)

    try:
        sende_kontaktmail(bereinigt, postfach)
    except KontaktNichtEingerichtet:
        logger.warning("Kontaktformular: WEBSITE_KONTAKT_EMPFAENGER fehlt.")
        return _antwort_mit_cors(503, _fehler_koerper(
            "Das Kontaktformular ist nicht eingerichtet.", "Error", 503), request)
    except Exception as ex:  # noqa: BLE001 — Versandfehler: 503, ohne Interna
        # NUR der Fehlertyp geht ins Protokoll — nie Name, Adresse, Nachricht.
        logger.warning("Kontaktmail nicht versendet (%s).", type(ex).__name__)
        return _antwort_mit_cors(503, _fehler_koerper(
            "Die Nachricht konnte gerade nicht versendet werden. "
            "Bitte später erneut versuchen oder die Gemeinde direkt anschreiben.",
            "Error", 503), request)

    logger.info("Kontaktmail versendet.")
    return _antwort_mit_cors(200, {"message": {"ok": True}}, request)


def _postfach_zuordnen(slug: str):
    """`postfach_waehlen` fuer den Endpunkt (eigener Name fuer Tests/Patches)."""
    return postfach_waehlen(slug)


@whitelist(methods=["GET"], allow_guest=True)
def postfaecher_oeffentlich(request=None):
    """Die Postfaecher, die das Formular anbieten darf (BS-1c/K2).

    Rueckgabe: ``{"message": {"postfaecher": [{"slug", "bezeichnung"}, …]}}``
    — nur AKTIVE Postfaecher, nur diese zwei Felder. **Keine E-Mail-Adresse**
    (G1), keine interne Kennung, keine Zaehlung. Ist nichts eingerichtet (keine
    Zeile und kein Rueckfall), ist die Liste LEER — der Endpunkt antwortet
    trotzdem 200: „nichts zur Auswahl" ist keine Stoerung, sondern der Zustand
    vor der Einrichtung (das Formular zeigt dann keine Auswahl an).

    BS-1c2 (F7): Sind Postfaecher ANGELEGT, aber KEINES ist aktiv, ist die
    Liste ebenfalls leer — das Formular darf dann nicht still auf ein anderes
    Postfach ausweichen. ``kontakt_senden`` antwortet in diesem Zustand
    bewusst **503** („nicht eingerichtet", Betreiberentscheidung: abgeschaltet
    ist abgeschaltet und kein stiller Rueckfall).

    BS-1c2 (F5): Die Liste geht durch einen EIGENEN Eimer der Kontaktbremse
    (`kontaktbremse.pruefe_liste`). Ein oeffentlicher GET, der die Datenbank
    liest, darf nicht ungebremst sein; gemeinsam mit dem Formular geteilt
    haette ein Abruf der Liste aber das Kontaktkontingent der Besucherin
    verbraucht. Ist die Bremse nicht erreichbar: 503 (fail closed, wie beim
    Formular).

    Reihenfolge nach ``sortierung``, dann ``slug`` — dieselbe Ordnung, nach
    der ``kontakt_senden`` ohne Slug das erste aktive Postfach waehlt.
    """
    from diakronos_app.settings import settings
    from diakronos_app.website import freigaben as regeln

    gebremst = _liste_gebremst(request)
    if gebremst is not None:
        return gebremst

    sess, eigene = _postfach_sitzung()
    try:
        liste = regeln.postfaecher_oeffentlich(
            sess, settings.website_kontakt_empfaenger
        )
    finally:
        if eigene:
            sess.close()

    daten = [
        {"slug": str(p.slug), "bezeichnung": str(p.bezeichnung)}
        for p in liste
        if bool(p.aktiv)
    ]
    antwort = _antwort_mit_cors(200, {"message": {"postfaecher": daten}}, request)
    # Kurz zwischenspeicherbar (G4): die Liste aendert sich nur, wenn die
    # Verwaltung ein Postfach pflegt.
    antwort.headers["Cache-Control"] = "public, max-age=300"
    return antwort


def _liste_gebremst(request):
    """Bremse fuer die Postfach-Liste (F5) — `None` = durchgelassen.

    Eigener Eimer (`kontaktbremse.pruefe_liste`), damit ein Abruf der Liste
    das Kontaktkontingent nicht verbraucht. Antworten tragen wie alle
    Kontakt-Antworten `Vary: Origin` und den CORS-Kopf der Primo-Herkunft
    (F4) — sonst bricht der Browser den eigentlichen `fetch` ab.
    """
    from diakronos_app import request_context
    from diakronos_app.anmeldung import kontaktbremse
    from diakronos_app.frappe_compat.router import _fehler_koerper

    try:
        erlaubt, grund = kontaktbremse.pruefe_liste(request_context.zaehler_client_ip())
    except Exception as ex:  # noqa: BLE001 — Bremse faellt aus: fail closed
        logger.warning("Postfach-Liste: Bremse nicht erreichbar (%s).", type(ex).__name__)
        return _antwort_mit_cors(503, _fehler_koerper(
            "Die Liste ist gerade nicht verfügbar. Bitte später erneut.",
            "RateLimitError", 503), request)

    if not erlaubt:
        logger.warning("Postfach-Liste gebremst (Grund=%s).", grund or "unbekannt")
        return _antwort_mit_cors(429, _fehler_koerper(
            kontaktbremse.fehlermeldung(), "RateLimitError", 429), request)
    return None


def _registriere_kurzpfad() -> None:
    """Traegt `website.kontakt_senden` in das Register ein (Karte, K1).

    `@whitelist` vergibt den Namen aus Modul und Funktion
    (`kontakt.kontakt_senden`). Der Pfad der Karte ist `website.kontakt_senden`
    — er wird hier auf DIESELBE Funktion gelegt; damit gelten auch dieselben
    Optionen (`allow_guest=True`, `router._guest_denied` liest sie ueber
    `options_for(fn)` und nicht ueber den Namen).

    BS-1c/K2: derselbe Weg fuer `website.oeffentlich.postfaecher` — der Name
    der Karte, auf `postfaecher_oeffentlich` gelegt (Optionen: Gast, nur GET).

    Idempotent: ein zweiter Import ueberschreibt nur denselben Eintrag.
    """
    from diakronos_app.frappe_compat.registry import register_with_frappe_module

    register_with_frappe_module("website", "kontakt_senden", kontakt_senden)
    register_with_frappe_module(
        "website.oeffentlich", "postfaecher", postfaecher_oeffentlich
    )


# Beim Import ausfuehren (das Modul wird von `diakronos_app.api` gezogen, also
# vor dem ersten Methodenaufruf). Bewusst hier und nicht im Dekorator: der
# Registerweg ist die dokumentierte Schnittstelle fuer Zusatzpfade.
_registriere_kurzpfad()


__all__ = [
    "BETREFF",
    "BETREFF_TRENNER",
    "BETREFF_ZUSATZ_MAX",
    "KontaktNichtEingerichtet",
    "PostfachUnbekannt",
    "betreff_mit_zusatz",
    "cors_herkunft",
    "email_gueltig",
    "herkunft_ist_eigen",
    "honeypot_gefuellt",
    "kontakt_senden",
    "mailtext",
    "postfaecher_oeffentlich",
    "postfach_waehlen",
    "pruefe_betreff_zusatz",
    "pruefe_felder",
    "sende_kontaktmail",
]

# Unbenutzt importiert waere `throw`/`ValidationError`/`RateLimitError` ein
# Rest aus dem ersten Entwurf — die Endpunkt-Antworten entstehen bewusst als
# JSONResponse (eigener Koerper mit `felder`), nicht ueber die Compat-Exception.
del throw, ValidationError, RateLimitError, FrappePermissionError
