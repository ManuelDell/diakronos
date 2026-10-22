"""`/api/method/login` und `/api/method/logout` — Karte A1b1.

Die SPA ist unveraenderlich und spricht Frappe: Login geht an
`/api/method/login` mit den Feldern `usr` + `pwd`. Wir richten uns danach.

Umfang A1b1 (Fundament, KEIN Verhaltenswechsel): nach dieser Karte kann man
sich anmelden, aber wer nichts tut, ist weiterhin Administrator
(`frappe_compat/session.py` DEFAULT_USER). Das Umschalten macht A1b2.

Sicherheit:
  * Passwortpruefung ueber `frappe_compat.passwoerter.pruefe` (Frappe-pbkdf2
    UND Argon2).
  * Bei unbekanntem Benutzer wird trotzdem gegen einen Dummy-Hash geprueft,
    damit die Antwortzeit nicht verraet, ob es den Benutzer gibt.
  * Erfolgreicher Login hebt einen importierten Frappe-Hash auf Argon2
    (`muss_neu_gehasht_werden`).
  * **A1c1**: Der Login ist ueber `frappe_compat.loginversuche` gegen
    Brute-Force gesperrt. Ein gesperrter Versuch ist von einem falschen
    Passwort **nicht unterscheidbar** — gleiche Antwort, gleiche Kopfzeilen,
    gleiche Antwortzeit (Dummy-Hash).
  * KEINE Passwoerter/Hashes/sid/CSRF-Token in Logs oder Fehlermeldungen.
"""

from __future__ import annotations

FRAPPE_MODULE = "frappe.login"  # nur informativ; Login ist ein Frappe-Kernpfad

import hashlib
import logging
from typing import Any

from starlette.responses import JSONResponse, RedirectResponse, Response

from diakronos_app.frappe_compat import benutzer_status, loginversuche, sitzungen
from diakronos_app.frappe_compat.exceptions import AuthenticationError
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.auth")

__all__ = ["login", "logout", "COOKIE_NAME", "login_formular_fehler"]

# Frappe nennt das Session-Cookie `sid`.
COOKIE_NAME = "sid"

# Ziel nach der Formular-Anmeldung. `spa.py` liefert die Maske unter diesem
# Pfad aus; hier als Konstante, damit `auth.py` den Pfad nicht hart codiert.
SPA_ZIEL = "/diakonos"

# Zeichen, die in einem `Location`-Header nichts zu suchen haben (A1c3,
# Notiz 2). Zusammengestellt als Zeichenkette, damit die Pruefung ein
# `in`-Vergleich bleibt und keine Regex pro Request kompiliert wird.
#
#   * die gesamte C0-Menge 0x00-0x1F, **einschliesslich Tab (0x09)**
#   * DEL (0x7F), NEL (U+0085) und die Unicode-Zeilenenden U+2028/U+2029:
#     nicht C0, aber in Kopfzeilen genauso unsichtbar bzw. von JavaScript
#     als Zeilenumbruch gelesen.
#
# ZUM TAB, obwohl er in einem Query-String erlaubt ist: die Pruefung laeuft
# nach `unquote()`, ein vom Browser kommendes `%09` ist also zum Zeitpunkt der
# Pruefung ein roher Tab. Ihn durchzulassen hiesse, genau die Klausel wieder
# aufzubiegen, die die ganze Funktion ausmacht — "kein Steuerzeichen im
# Ziel". Der Preis ist klein und wird hier ausdruecklich bezahlt: ein
# `redirect-to` mit prozentkodiertem Tab landet auf `/diakonos` statt auf
# seinem Ziel. Kein Sprachlink der SPA enthaelt ein Tab, und ein falsches
# Ziel nach dem Login ist ein Aerger, kein Datenverlust.
#
# Bewusst ueber `chr()` statt als Escapes im Quelltext: U+2028/U+2029 waeren
# sonst unsichtbare Zeichen in der Datei, die jeder Editor als Zeilenumbruch
# anzeigt und die kein Reviewer sieht.
_KOPFZEILEN_VERBOT = (
    "".join(chr(c) for c in range(0x00, 0x20))
    + chr(0x7F)   # DEL
    + chr(0x85)   # NEL
    + chr(0x2028) + chr(0x2029)
)

# Meldung fuer JEDEN Fehlschlag — unbekannter Benutzer, falsches Passwort,
# deaktiviertes Konto und gesperrter Versuch. Eine Konstante, damit keine
# der vier Faelle auch nur versehentlich abweichen kann.
UNGUELTIGE_ANMELDEDATEN = "Ungueltige Anmeldedaten"

# LOGIN-2/S1: Grund, der im Audit-Log fuer eine abgewiesene lokale Anmeldung
# steht (pseudonymisiert, siehe `_audit_gesperrt`). Er nennt NUR die Regel,
# nie das Konto — das Passwort war ja richtig.
_GRUND_LOKAL_AUS = "lokale-anmeldung-aus"

# LOGIN-2/S2: Header, an denen ein Browser-Formular erkennbar ist. `Origin`
# schickt jeder Browser bei POST (ausser sehr alten); fehlt er, entscheidet
# `Referer`. Fehlen beide, war es kein Browser-Formular — dann bleibt der
# bisherige Weg offen (Skripte, Apps, Tests).
_ORIGIN_HEADER = "origin"
_REFERER_HEADER = "referer"

# LOGIN-3/H1(c): Vom Browser gesetzter Hinweis auf die Herkunft der Anfrage.
# Aus JavaScript NICHT setzbar (die Fetch-Metadaten sind "forbidden headers"),
# deshalb der einzige Herkunftswert, den eine fremde Seite nicht verwischen
# kann — `Origin`/`Referer` lassen sich ueber `referrerpolicy` und Umwege
# beeinflussen, dieser Header nicht. `cross-site` ist immer fremd.
_SEC_FETCH_SITE = "sec-fetch-site"

# Praefix, unter dem das SPA-Ziel liegt — fuer die Origin-Pruefung.
_SPA_PFAD = "/diakonos"

# Dummy-Hash fuer unbekannte Benutzer. Er MUSS beim Start echt erzeugt werden:
# ein von Hand geschriebener Hash wird vom Verifizierer sofort verworfen, ohne
# die teure Schluesselableitung zu durchlaufen — gemessen 0,025 ms gegen
# 86,7 ms bei einem echten Hash (Faktor 3535). Die Zeitangleichung waere damit
# wirkungslos gewesen. Hier entsteht ein echter Argon2-Hash mit denselben
# Parametern, seine Pruefung kostet genauso viel wie eine echte.
# Das Klartextpasswort ist ein Zufallswert und wird nie aufbewahrt.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    """Erzeugt den Dummy-Hash beim ersten Bedarf (nicht beim Import —
    das wuerde jeden Prozessstart um ~90 ms verzoegern)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        import secrets

        from diakronos_app.frappe_compat.passwoerter import neuer_hash

        _DUMMY_HASH = neuer_hash(secrets.token_hex(16))
    return _DUMMY_HASH


def _pruefe_dummy(passwort: str) -> None:
    """Verbraucht die gleiche Zeit wie eine echte Pruefung. Ergebnis verworfen."""
    from diakronos_app.frappe_compat.passwoerter import pruefe

    pruefe(passwort, _dummy_hash())


def _secure_flag() -> bool:
    """Entscheidet, ob das `sid`-Cookie als `Secure` gesetzt wird.

    `auto` (Default) richtet sich nach dem Protokoll des laufenden Requests:
    hinter einem TLS-Proxy meldet `X-Forwarded-Proto: https`, direkt per HTTPS
    das Request-Schema. So ist das Cookie bei einer Gemeinde hinter TLS
    geschuetzt, waehrend der interne HTTP-Stack weiter funktioniert.
    """
    modus = str(settings.session_cookie_secure).strip().lower()
    if modus in ("true", "1", "yes", "on"):
        return True
    if modus in ("false", "0", "no", "off"):
        return False
    from diakronos_app.request_context import get_header

    proto = (get_header("X-Forwarded-Proto") or get_header("X-Scheme") or "").lower()
    if proto:
        return proto.split(",")[0].strip() == "https"
    return get_header("X-Forwarded-Ssl").lower() == "on"


def _setze_cookie(response: Response, sid: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=sid,
        httponly=True,
        samesite="lax",
        path="/",
        secure=_secure_flag(),
        max_age=int(settings.session_ttl_seconds),
    )


def _loesche_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        path="/",
        secure=_secure_flag(),
    )


@whitelist(allow_guest=True)
def login(usr: str | None = None, pwd: str | None = None, request=None, **kwargs: Any):
    """Frappe-kompatibler Login. Felder: `usr` (E-Mail/Username) + `pwd`.

    Erfolg -> HTTP 200, Body `{"message": "Logged In", ...}` und Cookie `sid`.
    Fehlschlag -> HTTP 401, gleiche Fehlermeldung, gleiche Antwortzeit. Das
    gilt fuer **fuenf** Faelle gleichermassen: unbekannter Benutzer, falsches
    Passwort, deaktiviertes Konto, Benutzer ohne Hash, gesperrter Versuch.

    `allow_guest=True`: der Login ist der EINE Endpunkt, der ohne Sitzung
    erreichbar sein muss.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import (
        muss_neu_gehasht_werden,
        neuer_hash,
        pruefe,
    )
    from diakronos_app.models.core import User

    benutzer = (usr or "").strip()
    passwort = pwd if pwd is not None else ""
    client_ip = _client_ip()

    # ── LOGIN-2/S2 + LOGIN-3/H1(c): Login-CSRF ────────────────────────────
    # `/api/method/login` ist von der CSRF-Middleware ausgenommen (dort gibt es
    # noch keine Sitzung zum Vergleichen). Eine fremde Seite konnte deshalb per
    # `<form method="post" action="…/api/method/login">` den Browser des Opfers
    # in ein Konto einloggen, dessen Zugangsdaten der Angreifer kennt — das
    # Opfer arbeitet danach ahnungslos in einem fremden Konto.
    #
    # LOGIN-3/H1(c) — **die Pruefung haengt an KEINEM Content-Type mehr.**
    # Bis LOGIN-2 galt sie nur fuer `application/x-www-form-urlencoded` und
    # `multipart/form-data`. Zwei Wege kamen vorbei, ohne dass die fremde
    # Seite etwas anderes tun musste als ein Attribut zu setzen:
    #   * `<form enctype="text/plain">` — schickt `Content-Type: text/plain`;
    #   * `fetch` mit `Content-Type: text/plain` (ein "CORS-simpler Request",
    #     den der Browser NICHT vorab prueft — der Angreifer sieht die Antwort
    #     nicht, die Anmeldung passiert trotzdem).
    # Deshalb gilt jetzt: sobald ein Herkunftsmerkmal da ist (`Origin`,
    # `Referer` oder `Sec-Fetch-Site`), wird geprueft — egal wie der Body
    # kodiert ist. Fehlt alles, war es kein Browser (Skript, App, curl,
    # Abnahme-Tool); dann bleibt der Weg offen wie bisher.
    #
    # `Sec-Fetch-Site: cross-site` wird zusaetzlich und unabhaengig davon
    # abgewiesen: den Header setzt der Browser selbst, er ist aus JavaScript
    # nicht faelschbar und auch dann vorhanden, wenn `Origin` durch
    # `referrerpolicy` oder eine Weiterleitung fehlt.
    #
    # Ein `GET` erreicht diese Funktion gar nicht mehr — der Compat-Router
    # laesst auf dem Login-Pfad nur POST durch (`router.call_method`).
    #
    # Die Ablehnung ist die des falschen Passworts: gleiche Meldung, gleicher
    # Status, kein Cookie, kein Hinweis auf den Grund.
    if request is not None and not _herkunft_ist_eigen(request):
        logger.info("Anmeldung von fremder Herkunft abgewiesen.")
        raise AuthenticationError(UNGUELTIGE_ANMELDEDATEN)

    # ── A1c1: Sperre VOR der Passwortpruefung ─────────────────────────────
    # Zwei unabhaengige Zaehler (Benutzer + IP). Gesperrt heisst: exakt
    # dieselbe Antwort wie bei einem falschen Passwort. Kein 429, keine
    # Zusatzkopfzeile, kein Feld im Body — sonst wuesste ein Angreifer,
    # dass er richtig liegt, und spaeter laeuft sein Durchlauf ohne jede
    # Pruefung weiter.
    erlaubt, grund = loginversuche.pruefe_und_merke(benutzer or None, client_ip or None)

    if not erlaubt:
        # Zeitangleichung: die Sperre darf NICHT daran erkennbar sein, dass
        # sie schneller antwortet. Der Dummy-Hash kostet dasselbe wie eine
        # echte Pruefung (siehe Modulkopf) — derselbe Zweig wie bei einem
        # unbekannten Benutzer.
        _pruefe_dummy(passwort)
        _audit_gesperrt(grund, benutzer, client_ip)
        raise AuthenticationError(UNGUELTIGE_ANMELDEDATEN)

    name: str | None = None
    full_name: str | None = None
    aktiv = False
    rolle_geprueft = False

    sess = SessionLocal()
    try:
        doc = None
        if benutzer:
            doc = sess.get(User, benutzer)
            # Frappe akzeptiert auch die E-Mail als Login-Name.
            if doc is None and "@" in benutzer:
                doc = sess.query(User).filter(User.email == benutzer).one_or_none()

        if doc is None or not doc.password_hash:
            # Unbekannter Benutzer ODER Benutzer ohne hinterlegtes Passwort
            # (z. B. `Guest`): in beiden Faellen Dummy-Pruefung, damit die
            # Antwortzeit weder die Existenz noch das Fehlen eines Passworts
            # verraet. Ergebnis wird verworfen.
            _pruefe_dummy(passwort)
        elif pruefe(passwort, doc.password_hash):
            if muss_neu_gehasht_werden(doc.password_hash):
                # Hebung auf Argon2 — nur nach BESTANDENER Pruefung.
                doc.password_hash = neuer_hash(passwort)
                sess.commit()
            name = doc.name
            full_name = doc.full_name
            # B1: Die Regel "existiert das Konto und ist es `enabled`" lebt
            # an EINER Stelle (`frappe_compat/benutzer_status.py`) — CalDAV
            # und der Login pruefen dasselbe, nicht dasselbe zweimal. Die
            # Zeile ist hier ohnehin geladen, deshalb `konto_ist_aktiv` und
            # kein zweiter Query pro Versuch (das waere in der Zeitangleichung
            # aus A1c1 messbarer Laerm).
            aktiv = benutzer_status.konto_ist_aktiv(doc)
            if aktiv:
                # LOGIN-2/S1: erst nach BESTANDENER Passwortpruefung — die
                # Rollenabfrage ist ein paar Millisekunden teurer als der
                # Dummy-Hash-Pfad und darf die Zeitangleichung nicht stoeren.
                rolle_geprueft = _lokaler_login_erlaubt(doc.name)
        else:
            # Falsches Passwort: dieselbe Zeitverbrauchslogik ist hier nicht
            # noetig (der Benutzer ist bekannt), aber die Meldung ist identisch.
            pass
    finally:
        sess.close()

    if name is None or not aktiv:
        # Identische Meldung fuer "unbekannt", "falsches Passwort" und
        # "deaktiviert" — nichts davon darf unterscheidbar sein.
        raise AuthenticationError(UNGUELTIGE_ANMELDEDATEN)

    if not rolle_geprueft:
        # LOGIN-2/S1: Das Passwort WAR richtig, die Regel `AUTH_LOCAL_LOGIN`
        # erlaubt diesen Menschen hier aber nicht. Nach aussen ist das nicht
        # unterscheidbar von einem falschen Passwort — gleiche Meldung, gleiche
        # Kopfzeilen, keine Sitzung.
        #
        # LOGIN-3/N-2: Der Versuch ist bereits gezaehlt — `pruefe_und_merke`
        # steht weiter oben (VOR der Passwortpruefung) und ist fuer diesen
        # Aufruf also schon gelaufen. (Die Herkunftspruefung ganz am Anfang
        # zaehlt dagegen NICHT: sie weist vor der Bremse ab, und das ist
        # Absicht — ein fremder Origin ist Angriffsverkehr, kein Tippfehler;
        # mitgezaehlt wuerde er den IP-Zaehler fluten und den Kontoschutz
        # aushebeln.) Ins Audit-Log geht nur die Tatsache, pseudonymisiert
        # (`_audit_gesperrt`).
        _audit_gesperrt(_GRUND_LOKAL_AUS, benutzer, client_ip)
        raise AuthenticationError(UNGUELTIGE_ANMELDEDATEN)

    # A1c1: Erfolg entlastet beide Zaehler. Ohne das waere ein Benutzer,
    # der sich zweimal vertippt und dann richtig anmeldet, kurz darauf
    # ausgesperrt. Auch die Backoff-Stufe faellt: die Sperre war eine
    # Fehlserie, keine Tatsache ueber diesen Benutzer.
    loginversuche.entlaste(name, client_ip or None)

    from diakronos_app.anmeldung.passwortzugang import wechsel_noetig, link_erzeugen
    if wechsel_noetig(name):
        link = link_erzeugen(name, erstwechsel=True)
        if _ist_formular_post(request):
            return RedirectResponse(link["link"], status_code=303, headers={"Cache-Control": "no-store"})
        return JSONResponse({"message": "Passwortwechsel erforderlich", "passwortwechsel": True,
                             "redirect_to": link["link"]}, headers={"Cache-Control": "no-store"})

    sid, csrf_token = sitzungen.anlegen(name)
    response = JSONResponse(
        content={
            "message": "Logged In",
            "user": name,
            "full_name": full_name or name,
            "csrf_token": csrf_token,
        }
    )
    # Die serverseitige Login-Maske (spa.py) postet ein normales
    # HTML-Formular: `Content-Type: application/x-www-form-urlencoded`. Ein
    # Browser erwartet darauf eine HTML-Antwort, kein JSON — ohne diese
    # Unterscheidung zeigt er nach der Anmeldung den rohen JSON-Text
    # `{"message": "Logged In", …}`. Die SPA ruft denselben Endpunkt per
    # `fetch` und bekommt weiterhin JSON.
    if _ist_formular_post(request):
        # `redirect-to` (Frappe-Schreibweise mit Bindestrich) ist der einzige
        # erlaubte Zusatz; alles andere aus dem Formular wird verworfen.
        ziel = _redirect_ziel(kwargs.get("redirect-to"))
        antwort: Response = RedirectResponse(ziel, status_code=303)
    else:
        antwort = response
    _setze_cookie(antwort, sid)
    # Nur die Tatsache des Logins, NIE Name/Token.
    logger.info("Login erfolgreich (Benutzer siehe Audit-Log).")
    return antwort


def _lokaler_login_erlaubt(benutzer: str) -> bool:
    """LOGIN-2/S1 — `AUTH_LOCAL_LOGIN`, serverseitig durchgesetzt.

    Bis LOGIN-2 wurde die Einstellung NUR in der Anmeldeseite ausgewertet
    (`anmeldung/routen.py::_lokales_login_erlaubt`). Der Endpunkt
    `/api/method/login` hat sie nie gesehen: mit `nur-admin` kam jedes Konto
    lokal hinein, mit `aus` ebenfalls. Diese Funktion schliesst die Luecke an
    der Stelle, an der Passwoerter tatsaechlich geprueft werden.

    Rueckgabe `True`, wenn der lokale Weg fuer diesen Benutzer erlaubt ist.

      * ``an``        — immer erlaubt.
      * ``nur-admin`` — nur Konten mit Administratorrolle („System Manager“
        oder „Mitgliederadministrator“). Dieselbe Definition wie
        `frappe_compat/permissions.ADMIN_ROLES` und
        `anmeldung/routen.py` — bewusst nicht neu erfunden.
      * ``aus``       — nie.

    **Ohne aktivierten Anbieter gilt die Schranke nicht.** Dann ist der lokale
    Login der einzige Weg; `aus` wuerde jede Gemeinde aussperren (gleiche
    Begruendung wie in `_lokales_login_erlaubt`, Bestandsschutz). Die
    Anmeldeseite verhaelt sich genauso — sonst zeigte sie ein Formular, das
    der Server anschliessend immer abweist.

    Aufruf NUR nach bestandener Passwortpruefung: die Rollenabfrage kostet
    Zeit, und die Zeitangleichung aus A1c1 darf nicht davon abhaengen, ob ein
    Konto Admin ist.
    """
    from diakronos_app.anmeldung import konfiguration as konf

    if not konf.oidc_aktiv():
        return True
    modus = str(getattr(settings, "auth_local_login", "") or "").strip().lower()
    if modus == "aus":
        return False
    if modus != "nur-admin":
        return True
    from diakronos_app.frappe_compat.permissions import ADMIN_ROLES, get_roles

    return bool(set(ADMIN_ROLES) & set(get_roles(benutzer)))


def _herkunft_ist_eigen(request) -> bool:
    """LOGIN-2/S2 + LOGIN-3/H1(c)/N-1 — kam die Anmeldung von DIESER Seite?

    Reihenfolge und Begruendung:

      1. `Sec-Fetch-Site` — vom Browser selbst gesetzt (nicht faelschbar,
         nicht aus JavaScript zu beeinflussen). `cross-site` ist IMMER fremd,
         auch wenn `Origin`/`Referer` fehlen (Datenschutzeinstellungen,
         `referrerpolicy=no-referrer`, Weiterleitung ueber eine fremde Seite).
         `same-origin` / `same-site` / `none` (direkter Aufruf/Lesezeichen)
         gelten als eigen.
      2. `Origin` — bei POST schickt jeder Browser diesen Header, und er ist
         vom Angreifer nicht faelschbar (er wird vom Browser aus dem
         Dokument-Ursprung gesetzt, nicht aus dem Formular). Verglichen wird
         die VOLLE Herkunft: Schema, Host und Port (N-1) — `http://` ist nicht
         `https://`, und `:9999` ist nicht `:80`.
      3. Nur wenn `Origin` FEHLT: `Referer` (aeltere Browser, strenge
         Datenschutzeinstellungen). Derselbe Vergleich.
      4. Fehlen alle drei, ist es kein Browser (Skript, `requests`,
         Abnahme-Tools) — dann bleibt alles wie bisher.

    `X-Forwarded-Host` wird NICHT benutzt: den Header setzt jeder Client frei,
    und ein Angreifer, der ihn auf seinen eigenen Host faelscht, haette die
    Pruefung damit selbst ausgehebelt. Benutzt wird `Host` (bzw. `:authority`)
    und `X-Forwarded-Proto`, letzteres weil der TLS-Proxy die Verbindung zum
    Backend ueber HTTP fuehrt und der Browser trotzdem `https` meldet. Beides
    setzt der Proxy: `proxy_set_header Host $http_host` und
    `proxy_set_header X-Forwarded-Proto https` (siehe BETRIEBSANLEITUNG 11.3).
    """
    if request is None:
        return True
    kopf = getattr(request, "headers", {})
    ziel = _eigene_herkunft(kopf)
    if ziel is None:
        # Kein Host-Kopfzeilenwert (Direktaufruf im Test): nichts zu pruefen.
        return True

    fetch_site = str(kopf.get(_SEC_FETCH_SITE) or "").strip().lower()
    if fetch_site == "cross-site":
        return False

    origin = str(kopf.get(_ORIGIN_HEADER) or "").strip()
    if origin:
        return _herkunft_aus_url(origin) == ziel

    referer = str(kopf.get(_REFERER_HEADER) or "").strip()
    if referer:
        return _herkunft_aus_url(referer) == ziel

    return True


def _eigene_herkunft(kopf) -> tuple[str, str, str] | None:
    """Die eigene Herkunft als `(schema, host, port)` — oder None ohne `Host`.

    Das Schema kommt aus `X-Forwarded-Proto` (TLS-Proxy). Fehlt der Header,
    gilt `http`: die Verbindung zum Backend fuehrt ohne TLS-Proxy kein
    Schema mit sich, und ein `:scheme`-Eintrag existiert in der
    Kopfzeilen-Sicht ohnehin nicht (das ist ein HTTP/2-Pseudo-Header der
    ASGI-Ebene, nicht der `Headers`-Abbildung — LOGIN-4/N hat den toten
    Zweig entfernt). Der Port kommt aus dem `Host`-Kopf; fehlt er, gilt der
    Standardport des Schemas (80/443) — genau die Regel, nach der ein
    Browser `Origin` bildet.
    """
    host_kopf = str(kopf.get("host") or "").strip().lower()
    if not host_kopf:
        return None

    schema = "http"
    weitergeleitet = str(kopf.get("x-forwarded-proto") or "").strip().lower()
    if weitergeleitet:
        erster = weitergeleitet.split(",")[0].strip()
        if erster in ("http", "https"):
            schema = erster

    host, port = _host_und_port(host_kopf)
    if not host:
        return None
    if not port:
        port = "443" if schema == "https" else "80"
    return (schema, host, port)


def _host_und_port(wert: str) -> tuple[str, str]:
    """`testserver:8000` -> `("testserver", "8000")`, `[::1]` -> `("[::1]", "")`."""
    wert = wert.strip().lower()
    if wert.startswith("["):  # IPv6 in Klammern
        ende = wert.find("]")
        if ende == -1:
            return wert, ""
        host = wert[: ende + 1]
        rest = wert[ende + 1 :]
        port = rest[1:] if rest.startswith(":") else ""
        return host, port
    host, _, port = wert.partition(":")
    return host, port


def _herkunft_aus_url(url: str) -> tuple[str, str, str] | None:
    """`(schema, host, port)` einer absoluten URL; None bei Unsinn.

    `Origin: null` (Sandbox/`file://`) ergibt None und ist damit nie die
    eigene Herkunft — genau richtig: ein `null`-Origin ist keine Browser-Seite
    dieser Anwendung. Der Port wird auf den Standardport normalisiert, damit
    `https://dev.example.org:443` und `https://dev.example.org` gleich sind
    (so bildet auch der Browser `Origin`).
    """
    from urllib.parse import urlsplit

    try:
        teile = urlsplit(url)
    except ValueError:
        return None
    if teile.scheme not in ("http", "https"):
        return None
    netz = teile.netloc.split("@")[-1]
    host, port = _host_und_port(netz)
    if not host:
        return None
    try:
        standard = 443 if teile.scheme == "https" else 80
        port_nummer = int(port) if port else standard
    except ValueError:
        return None
    if not (0 < port_nummer < 65536):
        return None
    return (teile.scheme, host, str(port_nummer))


def _client_ip() -> str:
    """Die IP des Absenders fuer den IP-Zaehler — **ohne** X-Forwarded-For.

    Bewusst nicht `X-Forwarded-For`: dieser Header wird von jedem Client
    frei gesetzt. Ein Angreifer, der 1000 Adressen vortaeuscht, wuerde den
    IP-Zaehler 1000-mal neu anfangen und die halbe Sperre umgehen. `request.
    client.host` ist der einzige Wert, den der Client nicht bestimmen kann
    (hinter einem Reverse-Proxy ist das dessen Adresse — dann greift
    zusaetzlich der Benutzerzaehler, der sich nicht austauschen laesst).

    **A1c2**: Hinter einem ausdruecklich vorausgesetzten Proxy
    (`BEHIND_PROXY=1`) gilt stattdessen die erste Adresse aus
    `X-Forwarded-For` — sonst waere der IP-Zaehler hinter dem Proxy fuer
    alle Benutzer identisch und nach fuenf Fehlversuchen eines Menschen
    tot. Der Schalter ist fail closed, siehe
    `request_context.zaehler_client_ip()`.

    Folgen fuer den Betrieb: hinter einem NAT sitzen mehrere Personen unter
    derselben IP. Fuenf Fehlversuche einer Person sperren die anderen. Das ist
    der bewusst gewaehlte Preis — der Benutzerzaehler bleibt verfuegbar, und
    die Sperre ist durch den Backoff zeitlich begrenzt.
    """
    from diakronos_app import request_context

    return request_context.zaehler_client_ip()


def _pseudo(roh: str) -> str:
    """Pseudonym eines Bezeichners fuer das Audit-Log — `sha256:<hex>`.

    Dieselbe Form wie `api/audit_policy/anonymize.py::_hash_identifier`, damit
    ein Eintrag aus dem Login und einer aus dem DSGVO-Nachtjob nicht
    unterscheidbar sind. Gesalzen mit `secret_key`: ein Angreifer mit
    Zugriff auf das Audit-Log kann die Liste der Benutzer nicht gegen eine
    E-Mail-Liste testen.
    """
    if not roh:
        return ""
    salz = str(getattr(settings, "secret_key", "") or "")
    return "sha256:" + hashlib.sha256(f"{salz}|{roh.strip().lower()}".encode()).hexdigest()


def _audit_gesperrt(grund: str, benutzer: str, client_ip: str) -> None:
    """Audit-Eintrag fuer einen abgewiesenen Versuch — **nur die Tatsache**.

    Nichts von dem, was verboten ist, steht hier drin: kein Passwort, kein
    Hash, kein `sid`, kein CSRF-Token und **kein E-Mail-Klartext**. Der
    Benutzer erscheint als `sha256:`-Pseudonym, die IP ebenfalls (ein
    Audit-Log mit Klartext-Adressen waere bei einem Angriff auf den Log
    selbst genau das Einfallstor, das man schliessen wollte).

    `actor` ist ein Fremdschluessel auf `user.name` — dort steht `Guest`
    (der Aufruf hatte ja keine Sitzung), das ist der ehrliche Akteur.

    Schlaegt das Schreiben fehl, bleibt die Anmeldung gesperrt: der
    Audit-Eintrag ist Dokumentation, keine Sperrvoraussetzung.
    """
    try:
        from diakronos_app.frappe_compat.api_helpers import _create, _now

        _create(
            "Audit Log",
            {
                "zeitstempel": _now(),
                # "Sonstiges" ist der einzige zulaessige Typ fuer diesen Fall
                # (siehe `api/audit.py::VALID_ACTIONS`).
                "action_typ": "Sonstiges",
                "actor": "Guest",
                "target_doctype": "User",
                "target_name": _pseudo(benutzer) or "unbekannt",
                "begruendung": (
                    "Login abgewiesen: Brute-Force-Sperre aktiv "
                    f"(Grund={grund or 'unbekannt'}, "
                    f"Benutzer={_pseudo(benutzer) or 'unbekannt'}, "
                    f"IP={_pseudo(client_ip) or 'unbekannt'})"
                ),
                "ip_address": _pseudo(client_ip) or None,
                "notification_gesendet": 0,
            },
        )
    except Exception as exc:  # noqa: BLE001 — Sperre darf nicht an der Logbuchhaltung haengen
        logger.warning("Audit-Eintrag fuer abgewiesenen Login nicht moeglich: %s", exc.__class__.__name__)


def _ist_formular_post(request) -> bool:
    """True, wenn der Login als HTML-Formular kam (nicht per `fetch`/JSON).

    `request` ist der FastAPI-Request, den der Compat-Router wegen des
    `request`-Parameters durchreicht (siehe `frappe_compat/router.py:117-118`).
    Fehlt er (Direktaufruf im Test), ist es kein Formular.
    """
    if request is None:
        return False
    ctype = (request.headers.get("content-type") or "").lower()
    return "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype


def login_formular_fehler(request, args: dict | None = None) -> Response:
    """LOGIN-1: Fehlschlag eines BROWSER-Formulars -> zurueck auf die Anmeldeseite.

    Ohne diese Antwort sah ein Mensch nach einem Tippfehler im Passwort die
    rohe JSON-Antwort `{"message": "Ungueltige Anmeldedaten", …}` als Seite —
    und mit ihr die Frappe-Exception-Namen, die niemand verstehen muss.

    Aufgerufen vom Compat-Router (`frappe_compat/router.py`) NUR, wenn

      * der Endpunkt der Login ist,
      * der Aufruf ein Formular-POST war (`application/x-www-form-urlencoded`
        bzw. `multipart/form-data`) und
      * der Aufrufer kein JSON erwartet (`Accept`, `X-Requested-With`).

    Alle anderen Aufrufer bekommen unveraendert 401 + JSON.

    Was hier NICHT passiert: keine Unterscheidung der Fehlschlagarten. Die
    Meldung ist fuer unbekannten Benutzer, falsches Passwort, deaktiviertes
    Konto und die Brute-Force-Bremse dieselbe (`UNGUELTIGE_ANMELDEDATEN` ist
    im Login bereits eine Konstante). Auch das Flash-Cookie sieht in allen
    Faellen gleich aus — es enthaelt nur die E-Mail, nie eine Ursache.

    Ziel: `303 /login?noredirect=1&redirect-to=<ziel>` — `noredirect=1` ist
    der Rückkehrpunkt der Fehlermeldung (dort wird IMMER die Maske gezeigt,
    auch bei aktivem OIDC), gefolgt vom Ziel. Der Frageteil des Ziels reist
    mit, das `#Fragment` steht hinter dem `?` der Weiterleitung (Fragmente
    gehören nicht in die `redirect-to`-Kopfzeile; die Anmeldeseite setzt es
    clientseitig wieder an, siehe `spa.render_login`/`anmeldung/routen.py`).
    `_redirect_ziel` filtert wie beim Erfolgsfall: offene Weiterleitung gibt
    es auch im Fehlerpfad nicht.
    """
    from urllib.parse import quote

    from diakronos_app.anmeldung import flash

    kandidat = (args or {}).get("redirect-to")
    ziel = _redirect_ziel(kandidat)

    # Der Frageteil gehoert zum Ziel (`/diakonos?x=1`), das Fragment nicht.
    #
    # LOGIN-2/M1: Das GANZE Ziel wandert in `redirect-to` — nicht nur sein
    # Pfad. Vorher wurde der Frageteil roh an die /login-URL gehaengt; damit
    # verlor `/diakonos?x=1&y=2` seine Parameter, und ein Ziel konnte die
    # /login-Parameter selbst setzen (`?noredirect=0` schaltete bei aktivem
    # OIDC die Maske ab — Starlette nimmt bei doppelten Parametern den
    # LETZTEN). Jetzt hat die /login-Abfrage genau `noredirect` (und ggf.
    # `frag`); alles andere steckt kodiert im Ziel.
    pfad, _, fragment = ziel.partition("#")
    location = f"/login?noredirect=1&redirect-to={quote(pfad, safe='')}"
    if fragment:
        # Nicht in die `redirect-to`-Kopfzeile, aber auch nicht verlieren: der
        # Handler von `/login` nimmt `frag` aus der ABFRAGE (Browser senden
        # alles ab `#` nie an den Server, ein echtes Fragment im Location-Header
        # kaeme also nie an) und reicht es an die Maske weiter, die es
        # clientseitig wieder anhaengt (OP-CHOR-4).
        location = f"{location}&frag={quote(fragment, safe='')}"

    antwort = RedirectResponse(location, status_code=303)
    antwort.headers["Cache-Control"] = "no-store"
    # LOGIN-2/N1: hoechstens 254 Zeichen — die Laenge einer E-Mail-Adresse.
    # Ohne Grenze erzeugte ein `usr` mit 6000 Zeichen ein `Set-Cookie` von
    # 8140 Bytes (gemessen im Review); Browser verwerfen alles ueber 4096
    # Bytes, und ein Proxy mit 4-k-Puffer antwortet mit 502. Die Kuerzung ist
    # fuer alle Fehlschlagarten gleich und verraet deshalb nichts.
    email = str((args or {}).get("usr") or "").strip()[:254]
    flash.setze_flash(antwort, email)
    # Nur die Tatsache — kein Benutzername, kein Passwort, kein Grund.
    logger.info("Formular-Anmeldung fehlgeschlagen; zurueck zur Anmeldeseite.")
    return antwort


def _redirect_ziel(kandidat: Any) -> str:
    """Ziel nach der Formular-Anmeldung — ausschliesslich lokal.

    Offene Weiterleitung ist ein Einfallstor: ein `?redirect-to=https://evil.de`
    wuerde nach erfolgreicher Anmeldung samt `sid`-Cookie auf eine fremde Seite
    zeigen. Deshalb werden nur pfadrelative Ziele akzeptiert; alles andere
    faellt auf `/diakonos` zurueck. Genau das Verhalten von Frappes
    `validate_redirect_url`.

    A1c3, Notiz 2 — **Steuerzeichen werden gefiltert**. `\r`, `\n`, NUL, Tab
    und der Rest der C0-Menge kommen sonst unveraendert in den `Location`-Header
    eines `RedirectResponse`. Heute ist das unkritisch, weil der ASGI-Server
    CR/LF in Kopfzeilen zurueckweist — aber das ist eine Zusage ueber diesen
    Codebestand hinaus, nicht ueber diese Funktion. Sie ist die EINZIGE Stelle,
    die `redirect-to` prueft, und wird bei der naechsten
    Auth-Implementierung geerbt; dann faellt der Schutz ersatzlos weg und ein
    Kopfzeilenumbruch im Zielpfad ist plötzlich ein offener Redirect bzw. ein
    Smuggling-Vektor.

    Gefiltert wird deshalb **vor** dem Bauen der Antwort, und der Fallback ist
    derselbe Pfad wie bei allen anderen bösen Kandidaten: `/diakonos`.

    Zwei Reihenfolgen sind bewusst so und nicht anders:

      1. `unquote()` **vor** der Pruefung. Sonst kaeme `%0d%0a` gefiltert
         durch, obwohl es nach dem Dekodieren ein Zeilenumbruch ist — und ob
         ein Proxy vorher oder nachher dekodiert, entscheidet der Angreifer
         nicht, sondern die Konfiguration davor.
      2. Der Zeichenfilter **zuletzt**, nach Pfadrelativitaet und Backslash.
         Die Reihenfolge aendert das Ergebnis nicht (jeder verbotene Wert geht
         ohnehin auf `SPA_ZIEL`); sie bestimmt nur, welcher Grund im Log steht.
         Ein Kandidat mit beidem — etwa `"/\\evil.de"` mit Tab — ist ein
         fremder Pfad und wird auch ohne den Zeichenfilter abgelehnt.

    Erfasst wird, was ein HTTP-Kopfzeilenwert nicht enthalten darf: die
    gesamte C0-Menge einschliesslich Tab, DEL, NEL (U+0085) und die beiden
    Unicode-Zeilenenden (U+2028/U+2029), die JavaScript als Zeilenumbruch
    liest. Zum Tab steht die Begruendung an `_KOPFZEILEN_VERBOT`.
    """
    from urllib.parse import unquote

    ziel = unquote(str(kandidat or "")).strip()
    if not ziel.startswith("/") or ziel.startswith("//"):
        return SPA_ZIEL
    # `\` wird von manchen Browsern wie `/` behandelt — `\/evil.de` waere
    # sonst ein Weg aus der Anwendung heraus.
    if "\\" in ziel:
        return SPA_ZIEL
    if any(c in _KOPFZEILEN_VERBOT for c in ziel):
        logger.warning("redirect-to mit Steuerzeichen verworfen (gekuerzt).")
        return SPA_ZIEL
    return ziel


@whitelist(allow_guest=True)
def logout(request=None):
    """Beendet die Sitzung: `sid` in Redis loeschen, Cookie entfernen.

    Idempotent — ein Logout ohne gueltige Sitzung ist trotzdem HTTP 200 (die
    SPA leitet danach ohnehin auf /login um).

    PT1 — **kein Logout per GET, wenn eine Sitzung existiert.** Der
    Frappe-Router erlaubt fuer `/api/method/*` auch GET; die CSRF-Middleware
    deckt nur schreibende Methoden ab. Ein GET-Logout mit gueltigem `sid`
    waere damit von jeder fremden Seite per `<img src="/api/method/logout">`
    ausloesbar (Forced Logout). Es gibt keinen Aufrufer, der das nutzt (die
    SPA ruft den Logout nicht per GET). Ein GET ohne Sitzung bleibt der
    harmlose idempotente No-op.

    `request` wird vom Compat-Router explizit durchgereicht (siehe
    `frappe_compat/router.py`), weil der Request-Kontext wegen
    `BaseHTTPMiddleware` + Sync-Endpunkt hier nicht verlaesslich steht.
    """
    sid = _sid_aus_request(request)
    if sid and sitzungen.lesen(sid) is not None and _methode(request) != "POST":
        from diakronos_app.frappe_compat.auth_middleware import _csrf_ablehnung

        return _csrf_ablehnung()
    if sid:
        sitzungen.loeschen(sid)

    response = JSONResponse(content={"message": "Logged Out"})
    _loesche_cookie(response)
    return response


def _methode(request) -> str:
    """HTTP-Methode des Aufrufs; ohne Request konservativ `POST`.

    Der Direktaufruf im Test (`logout()` ohne Request) soll den bestehenden
    Pfad behalten — die Sperre greift nur, wenn wir die Methode wirklich
    kennen.
    """
    if request is None:
        return "POST"
    return str(getattr(request, "method", "") or "").upper()


def _sid_aus_request(request) -> str | None:
    """Liest `sid` aus dem Request (Cookie-Header oder Cookie-Jar)."""
    if request is None:
        # Fallback, wenn kein Request durchgereicht wurde (direkte Aufrufe).
        from diakronos_app.request_context import get_header

        cookie_header = get_header("Cookie")
    else:
        cookie_header = request.headers.get("cookie", "")
    if not cookie_header:
        return None
    for teil in cookie_header.split(";"):
        name, _, wert = teil.strip().partition("=")
        if name == COOKIE_NAME and wert:
            return wert
    return None
