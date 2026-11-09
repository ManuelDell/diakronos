"""WEB-1 — Adapter zu Primo (Website-Builder).

Primo ist ein GETRENNTES System: ein Go-Binary mit eingebettetem PocketBase
(http://<host>:8095, Primo v3.3.1). Diakronos haengt OPTIONAL daran; ohne
Konfiguration (`settings.primo_konfiguriert`) passiert hier **nichts** —
kein Aufruf nach aussen, kein Fehler.

Warum eine eigene, kleine Schicht
---------------------------------
Die Primo-Endpunkte (`/api/primo/*`, PocketBase-REST) sind NICHT als
stabiler Vertrag dokumentiert (Umbenennung `/api/palacms/*` -> `/api/primo/*`
in v3.3.x). Diese Datei kapselt deshalb jede HTTP-Beruehrung an EINER Stelle,
mit festem Timeout, begrenzter Antwortgroesse und ohne Exception nach aussen.

Sicherheitsregeln (gelten fuer jeden Aufruf hier)
-------------------------------------------------
* **Secrets nie loggen.** Das Superuser-Passwort und das daraus gewonnene
  Superuser-Token stehen in keiner Log-Zeile und in keiner Antwort. Meldungen
  nennen hoechstens Statuscode und einen Kurzgrund.
* **Kein Passwort im Browser.** Die Uebergabe laeuft ueber ein kurzlebiges
  PocketBase-Impersonate-Token (Default 300 s) im URL-FRAGMENT (geht nicht an
  Server-Logs).
* **Fail geschlossen.** Ein nicht erreichbarer/abweichender Primo ist ein
  Zustand ("nicht_erreichbar"), keine 500.

Zustaende (`status_zustand`)
----------------------------
    nicht_konfiguriert  -> `PRIMO_URL`/Superuser fehlen (Modul schlaeft)
    nicht_erreichbar    -> Adresse gesetzt, aber /api/primo/info antwortet nicht
    verbunden           -> /api/primo/info antwortet mit gueltigem JSON

Der Login-Endpunkt (`login_uebergabe`) prueft die Verbindung selbst noch
einmal, weil dort ein echter Zugang entsteht — der Status-Endpunkt ist nur
Anzeige.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import threading
import time
from typing import Any

import httpx

from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.website.primo")

# ── Zustaende (Vertrag fuer WEB-2/WEB-3) ────────────────────────────────────
ZUSTAND_NICHT_KONFIGURIERT = "nicht_konfiguriert"
ZUSTAND_NICHT_ERREICHBAR = "nicht_erreichbar"
ZUSTAND_VERBUNDEN = "verbunden"

# PocketBase-Pfade (0.35). Bewusst als Konstanten: die Umbenennung
# palacms->primo hat gezeigt, dass ein Pfad an mehreren Stellen driftet.
PFAD_INFO = "/api/primo/info"
PFAD_SUPERUSER_AUTH = "/api/collections/_superusers/auth-with-password"
PFAD_USERS = "/api/collections/users/records"
PFAD_IMPERSONATE = "/api/collections/users/impersonate/{record_id}"

# Primo-Antworten sind klein (Instanzinfo, ein Datensatz). Die Grenze
# verhindert, dass eine falsch konfigurierte Adresse (die irgendetwas anderes
# ausliefert) den Speicher fuellt.
MAX_ANTWORT_BYTES = 256 * 1024


class PrimoFehler(Exception):
    """Basisfehler des Adapters — niemals mit Secret-Inhalt im Text."""


class PrimoNichtKonfiguriert(PrimoFehler):
    """`PRIMO_URL`/Superuser fehlen. Aufrufer antwortet 409/503, nicht 500."""


class PrimoNichtErreichbar(PrimoFehler):
    """Netz-/Protokollfehler oder Timeout gegenueber Primo."""


class PrimoAbgelehnt(PrimoFehler):
    """Primo hat den Aufruf mit einem Fehlerstatus beantwortet.

    `status` ist der HTTP-Status, `grund` ein kurzer, secret-freier Text.
    """

    def __init__(self, status: int, grund: str):
        super().__init__(f"Primo antwortete {status}: {grund}")
        self.status = status
        self.grund = grund


class PrimoKontoKonflikt(PrimoFehler):
    """Die Zuordnung Benutzer <-> Primo-Konto ist nicht eindeutig (WEB-1b).

    Drei Lagen, alle ein **409** und alle OHNE Aenderung in Primo:

      * die Adresse gehoert trotz gesperrtem Konto zu einer Zuordnung
        (Superuser/geschuetztes Konto),
      * die Zuordnung zeigt auf ein Konto, dessen Mail in Primo abweicht,
      * es gibt keine Zuordnung, aber in Primo existiert bereits ein Konto
        mit der Adresse — dann darf nur ein Admin verknuepfen.

    `meldung` ist der Klartext fuer den Benutzer (kein Secret, kein Internum).
    """

    def __init__(self, meldung: str):
        super().__init__(meldung)
        self.meldung = meldung


# ── HTTP-Grundlage ──────────────────────────────────────────────────────────


def _client() -> httpx.Client:
    """Kurzlebiger Client mit hartem Timeout (nie der Default von httpx)."""
    return httpx.Client(
        timeout=settings.primo_timeout_sekunden,
        follow_redirects=False,
        trust_env=False,
    )


def _url(pfad: str) -> str:
    return f"{settings.primo_url_effektiv}{pfad}"


def _json_aus_antwort(antwort: httpx.Response) -> dict[str, Any]:
    """Antwort als dict; zu grosse/falsche Antworten sind ein Fehler."""
    if len(antwort.content or b"") > MAX_ANTWORT_BYTES:
        raise PrimoAbgelehnt(antwort.status_code, "Antwort zu gross")
    try:
        daten = antwort.json()
    except ValueError as exc:  # JSONDecodeError ist ein ValueError
        raise PrimoAbgelehnt(antwort.status_code, "Antwort ist kein JSON") from exc
    if not isinstance(daten, dict):
        raise PrimoAbgelehnt(antwort.status_code, "Antwort ist kein Objekt")
    return daten


def _fehlertext(antwort: httpx.Response) -> str:
    """Kurzer Grund aus einer PocketBase-Fehlerantwort — ohne Echo von Eingaben.

    PocketBase liefert `{"message": ..., "data": {...}}`. Nur `message` wird
    uebernommen und auf eine Zeile gekuerzt; `data` kann Feldwerte enthalten
    und bleibt draussen.
    """
    try:
        daten = antwort.json()
    except ValueError:
        return "ohne Begruendung"
    if isinstance(daten, dict):
        text = str(daten.get("message") or "").strip()
        if text:
            return text.splitlines()[0][:200]
    return "ohne Begruendung"


def _ist_konfiguriert() -> bool:
    return settings.primo_konfiguriert


# ── S2: Status ──────────────────────────────────────────────────────────────


def status() -> dict[str, Any]:
    """Zustand der Primo-Anbindung — wirft nie.

    Rueckgabe (Vertrag fuer WEB-2/WEB-3):

        {"status": "nicht_konfiguriert" | "nicht_erreichbar" | "verbunden",
         "version": str | None,
         "site_count": int | None,
         "url": str | None,
         "warnung": str | None}

    `url` ist die BROWSER-Adresse (`PRIMO_PUBLIC_URL`, Default `PRIMO_URL`)
    und nur bei konfigurierter Anbindung gefuellt. Secrets sind nie Teil der
    Antwort.

    `warnung` (WEB-1b, H) ist gesetzt, wenn die Browser-Adresse kein `https`
    benutzt — ein Hinweis, keine Sperre (im LAN ist http in Ordnung).
    """
    warnung = settings.primo_public_url_warnung
    if not _ist_konfiguriert():
        return {
            "status": ZUSTAND_NICHT_KONFIGURIERT,
            "version": None,
            "site_count": None,
            "url": None,
            "warnung": None,
        }

    info = instanz_info()
    if info is None:
        return {
            "status": ZUSTAND_NICHT_ERREICHBAR,
            "version": None,
            "site_count": None,
            "url": settings.primo_public_url_effektiv or None,
            "warnung": warnung,
        }
    return {
        "status": ZUSTAND_VERBUNDEN,
        "version": info.get("version"),
        "site_count": info.get("site_count"),
        "url": settings.primo_public_url_effektiv or None,
        "warnung": warnung,
    }


def instanz_info() -> dict[str, Any] | None:
    """`GET /api/primo/info` — `None`, wenn nicht erreichbar/kein JSON."""
    try:
        with _client() as client:
            antwort = client.get(_url(PFAD_INFO))
        if antwort.status_code != 200:
            logger.warning("Primo-Info: HTTP %s", antwort.status_code)
            return None
        return _json_aus_antwort(antwort)
    except (httpx.HTTPError, PrimoFehler) as exc:
        # Typname statt Text: der Text koennte eine interne Adresse enthalten,
        # die im Log nichts zu suchen hat (die Adresse steht in der Config).
        logger.warning("Primo-Info nicht erreichbar (%s).", type(exc).__name__)
        return None


# ── Superuser-Anmeldung ─────────────────────────────────────────────────────


def superuser_token() -> str:
    """Superuser-Token von PocketBase (`auth-with-password`), fuer den Prozess gemerkt.

    Warum ein Merker
    ----------------
    PocketBase bremst `auth-with-password`. Ohne Merker meldeten sich Stand-Lesen
    und Import kurz hintereinander neu an; der zweite Aufruf bekam **429** und die
    Oberflaeche meldete faelschlich "die Website hat den Zugriff abgelehnt"
    (Befund BS-2d3). Der Merker lebt deshalb an DIESER einen Stelle und wird von
    allen Wegen benutzt (`bausteine`, `login_uebergabe`, Nachziehen) -- so gibt
    es genau eine Anmeldung pro Prozess und Token-Laufzeit.

    Bindung
    -------
    Der Merker gilt nur fuer dasselbe Paar (URL, E-Mail). Wechselt die
    Konfiguration, wird der alte Wert verworfen -- ein Token von Instanz A
    darf nie gegen Instanz B laufen.

    Laufzeit
    --------
    Gelesen wird `exp` aus dem JWT-Rumpf (base64, OHNE Signaturpruefung -- es
    geht nur um die Ablaufzeit, nicht um Vertrauen). Gemerkt wird bis
    `min(exp - 60 s, PRIMO_TOKEN_SEKUNDEN)`; fehlt `exp`, gilt
    `PRIMO_TOKEN_SEKUNDEN` (Superuser-Token, NICHT die Impersonate-Dauer).
    `exp` ist ein Unix-Zeitpunkt, der Merker rechnet mit `time.monotonic()`.

    Fehler: `PrimoNichtKonfiguriert`, `PrimoNichtErreichbar`, `PrimoAbgelehnt`.
    """
    schluessel = _auth_schluessel()
    token = _merker_gueltig(schluessel)
    if token:
        return token
    token, gueltig_sekunden = _anmelden()
    # `gueltig_sekunden` ist eine DAUER (aus exp - jetzt) -- der Merker laeuft
    # deshalb auf der monotonen Uhr und wird von einer Uhrumstellung korrekt
    # nicht verlaengert.
    with _token_sperre:
        _token_merker_schreiben(token, time.monotonic() + gueltig_sekunden, schluessel)
    return token


def _merker_gueltig(schluessel: tuple[str, str]) -> str:
    """Das gemerkte Token, wenn es zu `schluessel` passt und noch gilt -- sonst ""."""
    with _token_sperre:
        token, bis, gemerkt = _token_merker_lesen()
    if token and gemerkt == schluessel and time.monotonic() < bis:
        return token
    return ""


def token_verwerfen(*, nur_wenn: str | None = None) -> None:
    """Vergisst das gemerkte Superuser-Token (401/403, `merker_zuruecksetzen`).

    `nur_wenn` schuetzt gegen Wettlauf: haben zwei Threads gleichzeitig ein 401
    bekommen und der eine hat sich schon neu angemeldet, darf der andere das
    FRISCHE Token nicht wieder loeschen. Angegeben wird das Token, das das 401
    bekam -- nur wenn es noch der gemerkte Wert ist, wird verworfen.
    """
    with _token_sperre:
        token, _bis, _schluessel = _token_merker_lesen()
        if nur_wenn is not None and token != nur_wenn:
            return
        _token_merker_leeren()


def anmeldung_zuruecksetzen() -> None:
    """Kurzform fuer `token_verwerfen()` ohne Bedingung."""
    token_verwerfen()


def _auth_schluessel() -> tuple[str, str]:
    """(URL, E-Mail) des Superuser-Zugangs -- die Bindung des Merkers."""
    return (
        str(settings.primo_url_effektiv or "").strip(),
        str(settings.primo_superuser_email or "").strip().lower(),
    )


def _anmelden() -> tuple[str, float]:
    """Ein echter `auth-with-password`-Aufruf: `(token, gueltige_sekunden)`."""
    if not _ist_konfiguriert():
        raise PrimoNichtKonfiguriert(
            "Primo ist nicht konfiguriert (PRIMO_URL/Superuser fehlen)."
        )
    daten = {
        "identity": str(settings.primo_superuser_email or "").strip(),
        "password": settings.primo_superuser_password_effektiv,
    }
    try:
        with _client() as client:
            antwort = client.post(_url(PFAD_SUPERUSER_AUTH), json=daten)
    except httpx.HTTPError as exc:
        raise PrimoNichtErreichbar("Primo ist nicht erreichbar.") from exc
    if antwort.status_code != 200:
        # NIE die Antwort oder die Anfrage loggen: die Anfrage enthaelt das
        # Passwort, die Antwort das Token.
        raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
    koerper = _json_aus_antwort(antwort)
    token = str(koerper.get("token") or "").strip()
    if not token:
        raise PrimoAbgelehnt(200, "Antwort ohne Token")
    return token, _gueltigkeit_sekunden(token)


def _gueltigkeit_sekunden(token: str) -> float:
    """Wie lange das Token laut `exp` gilt (mindestens 60 s), sonst Konfiguration.

    `exp` wird aus dem JWT-Rumpf gelesen, OHNE Signaturpruefung: die Pruefung
    ist Sache von Primo, hier wird nur eine Merkdauer bestimmt. Ein unlesbares
    Token faellt auf `PRIMO_TOKEN_SEKUNDEN` zurueck -- nie auf 0, sonst waere
    jeder Aufruf wieder eine Anmeldung (429).
    """
    standard = max(60.0, float(settings.primo_token_sekunden))
    teile = str(token or "").split(".")
    if len(teile) < 2:
        return standard
    try:
        rumpf = teile[1] + "=" * (-len(teile[1]) % 4)
        daten = json.loads(base64.urlsafe_b64decode(rumpf.encode("ascii")))
        exp = float(daten["exp"])
    except (ValueError, KeyError, TypeError):
        return standard
    rest = exp - time.time() - 60.0
    if rest <= 0:
        # Schon (fast) abgelaufen: nicht merken, aber den Standard als
        # Untergrenze behalten, damit der Aufrufer kein Sonderfall wird.
        return 60.0
    return min(rest, standard)


#: Merker-Sperre: `auth-with-password` ist gebremst, also darf ein zweiter
#: Thread nicht parallel anmelden.
_token_sperre = threading.Lock()
_token_wert = ""
_token_bis = 0.0
_token_schluessel: tuple[str, str] | None = None


def _token_merker_lesen() -> tuple[str, float, tuple[str, str] | None]:
    return _token_wert, _token_bis, _token_schluessel


def _token_merker_schreiben(
    token: str, bis: float, schluessel: tuple[str, str]
) -> None:
    global _token_wert, _token_bis, _token_schluessel
    _token_wert = token
    _token_bis = bis
    _token_schluessel = schluessel


def _token_merker_leeren() -> None:
    global _token_wert, _token_bis, _token_schluessel
    _token_wert = ""
    _token_bis = 0.0
    _token_schluessel = None


#: Status, bei denen ein Merker ungueltig ist (PocketBase: Token abgelaufen
#: oder Superuser geloescht). Dann GENAU EINE neue Anmeldung -- nicht mehr.
TOKEN_UNGUELTIG_STATUS = frozenset({401, 403})


def _mit_token(aufruf):
    """Fuehrt `aufruf(token)` aus; bei 401/403 einmal neu anmelden.

    `aufruf` bekommt das Superuser-Token und gibt das Ergebnis zurueck. Wirft
    er `PrimoAbgelehnt` mit 401/403, wird der Merker verworfen (nur wenn er
    noch der benutzte ist -- siehe `token_verwerfen`) und der Aufruf mit einem
    frischen Token wiederholt. Ein zweites 401/403 wird durchgereicht: dann
    stimmen die Zugangsdaten nicht, und weiteres Anmelden waere nur Last.
    """
    token = superuser_token()
    try:
        return aufruf(token)
    except PrimoAbgelehnt as fehler:
        if fehler.status not in TOKEN_UNGUELTIG_STATUS:
            raise
        token_verwerfen(nur_wenn=token)
        logger.info("Primo: Superuser-Token abgelehnt (HTTP %s), neue Anmeldung.", fehler.status)
    return aufruf(superuser_token())


# ── S4b: Konto sicherstellen ────────────────────────────────────────────────


def _auth_kopf(token: str) -> dict[str, str]:
    return {"Authorization": token, "Content-Type": "application/json"}


def _hole_benutzer(client: httpx.Client, token: str, email: str) -> dict[str, Any] | None:
    """Sucht den `users`-Datensatz zur E-Mail (exakter Filter, ohne LIKE)."""
    filter_ausdruck = f"email = {json.dumps(email)}"
    antwort = client.get(
        _url(PFAD_USERS),
        params={"filter": filter_ausdruck, "perPage": 1},
        headers=_auth_kopf(token),
    )
    if antwort.status_code != 200:
        raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
    daten = _json_aus_antwort(antwort)
    eintraege = daten.get("items") or []
    if not isinstance(eintraege, list) or not eintraege:
        return None
    erster = eintraege[0]
    return erster if isinstance(erster, dict) else None


#: Zuordnung Diakronos-Rolle -> Primo-`serverRole`.
#:
#: `System Manager` und `Administrator` sind Voll-Admins und bekommen die
#: Primo-Serverrolle `developer`; `Website-Moderator` bekommt `editor`.
#: Die Reihenfolge ist die Rangfolge: bei mehreren Rollen gewinnt die erste.
ROLLEN_ZUORDNUNG: tuple[tuple[str, str], ...] = (
    ("System Manager", "developer"),
    ("Administrator", "developer"),
    ("Website-Moderator", "editor"),
)

#: Rollen, die ueberhaupt in den Website-Bereich duerfen (S3).
WEBSITE_ROLLEN: tuple[str, ...] = (
    "System Manager",
    "Administrator",
    "Website-Moderator",
)

#: Primo-Passwort fuer neu angelegte Konten ist ein Zufallswert, den niemand
#: kennt: die Anmeldung laeuft ausschliesslich ueber das Uebergabe-Token.
#: PocketBase verlangt mindestens 10 Zeichen (Default-Mindestlaenge 8).
_ZUFALLS_PASSWORT_LAENGE = 32


def primaere_primo_rolle(rollen: list[str] | tuple[str, ...]) -> str | None:
    """Primo-`serverRole` fuer die Diakronos-Rollen — `None`, wenn keine passt."""
    vorhanden = {str(r or "").strip() for r in rollen}
    for diakronos_rolle, primo_rolle in ROLLEN_ZUORDNUNG:
        if diakronos_rolle in vorhanden:
            return primo_rolle
    return None


def darf_website(rollen: list[str] | tuple[str, ...]) -> bool:
    """True, wenn die Rollenliste Zugriff auf die Website-Funktionen hat."""
    vorhanden = {str(r or "").strip() for r in rollen}
    return any(rolle in vorhanden for rolle in WEBSITE_ROLLEN)


# ── WEB-1b: Zuordnung Diakronos-Benutzer <-> Primo-Konto ────────────────────

#: Meldungen der Konfliktfaelle (409). Eine Quelle fuer Adapter, Endpunkt und
#: Tests — der Benutzer liest sie so, die Verwaltung findet sie in der
#: Betriebsanleitung wieder.
KONFLIKT_MAIL_ABWEICHEND = (
    "Das verknüpfte Website-Konto hat eine andere E-Mail-Adresse als die "
    "Zuordnung erwartet. Bitte die Verknüpfung durch einen Administrator "
    "prüfen lassen."
)
KONFLIKT_KONTO_EXISTIERT = (
    "Konto besteht bereits in Primo – Verknüpfung durch Admin nötig."
)
KONFLIKT_GESCHUETZT = (
    "Diese E-Mail-Adresse ist für die Website-Anmeldung gesperrt "
    "(Systemkonto). Bitte einen Administrator ansprechen."
)


def _zuordnung(user: str) -> tuple[str, str] | None:
    """Liest die Zuordnung zur Diakronos-Benutzerkennung — `(primo_id, email)`.

    Fehler beim Lesen (Tabelle fehlt, DB weg) werden NICHT zu "keine
    Zuordnung": das waere eine Uebernahme per Adressgleichheit auf dem
    Fehlerweg. Sie fliegen als Exception nach oben und der Endpunkt antwortet
    generisch (fail closed).

    Eine eigene Sitzung, weil der Aufruf aus dem Request-Thread kommt und
    `SessionLocal` dort ohnehin die konfigurierte Datenbank ist (Tests patchen
    sie mit).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.website import PrimoKonto

    with SessionLocal() as sess:
        zeile = sess.get(PrimoKonto, str(user or "").strip())
        if zeile is None:
            return None
        return str(zeile.primo_id or "").strip(), str(zeile.email or "").strip()


def _zuordnung_speichern(user: str, primo_id: str, email: str) -> None:
    """Legt die Zuordnung an; idempotent fuer dieselbe `primo_id`."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.website import PrimoKonto

    kennung = str(user or "").strip()
    with SessionLocal() as sess:
        vorhanden = sess.get(PrimoKonto, kennung)
        if vorhanden is None:
            sess.add(PrimoKonto(user=kennung, primo_id=primo_id, email=email))
        else:
            vorhanden.primo_id = primo_id
            vorhanden.email = email
        sess.commit()


def _geschuetzt(adresse: str) -> bool:
    return settings.primo_ist_geschuetzt(adresse)


def konto_sicherstellen(
    user: str,
    email: str,
    server_rolle: str,
    superuser_token_: str,
) -> dict[str, Any]:
    """Stellt das Primo-Konto des Benutzers sicher (WEB-1b, Zuordnung).

    Reihenfolge — die Zuordnung entscheidet, NIE die Adresse allein:

      1. Adresse gesperrt (`primo_superuser_email`, `PRIMO_GESCHUETZTE_KONTEN`)
         -> `PrimoKontoKonflikt`, und zwar VOR jedem Primo-Aufruf.
      2. Zuordnung vorhanden -> NUR diese `primo_id` benutzen. Weicht die Mail
         des Kontos in Primo ab -> `PrimoKontoKonflikt`. Sonst wird die
         `serverRole` angeglichen (Rollenwechsel wirkt beim naechsten Login).
      3. Keine Zuordnung, in Primo existiert KEIN Konto mit der Adresse ->
         anlegen (Zufallspasswort, `verified=true`) und Zuordnung speichern.
      4. Keine Zuordnung, aber ein Konto mit der Adresse existiert ->
         `PrimoKontoKonflikt`: kein Uebernehmen, kein PATCH, kein impersonate.
         Verknuepfen ist eine Admin-Handlung.

    Rueckgabe: der `users`-Datensatz (mindestens `id`, `email`, `serverRole`).
    """
    kennung = str(user or "").strip()
    if not kennung:
        raise PrimoAbgelehnt(400, "Konto ohne Benutzerkennung")
    adresse = str(email or "").strip()
    if not adresse:
        raise PrimoAbgelehnt(400, "Benutzer ohne E-Mail-Adresse")
    if server_rolle not in ("editor", "developer"):
        # Fail closed: eine unbekannte Rolle wuerde PocketBase entweder
        # ablehnen oder stillschweigend verwerfen.
        raise PrimoAbgelehnt(400, "unbekannte Primo-Serverrolle")
    if _geschuetzt(adresse):
        # Vor jedem HTTP-Aufruf: das Superuser-/Maschinenkonto ist kein
        # Benutzerkonto und darf nie Ziel einer Uebergabe sein.
        raise PrimoKontoKonflikt(KONFLIKT_GESCHUETZT)

    try:
        with _client() as client:
            zuordnung = _zuordnung(kennung)

            if zuordnung is not None:
                primo_id, zuordnung_mail = zuordnung
                if not primo_id:
                    raise PrimoKontoKonflikt(KONFLIKT_MAIL_ABWEICHEND)
                konto = _hole_benutzer_per_id(client, superuser_token_, primo_id)
                if konto is None:
                    raise PrimoKontoKonflikt(KONFLIKT_MAIL_ABWEICHEND)
                mail_in_primo = str(konto.get("email") or "").strip().lower()
                if mail_in_primo != zuordnung_mail.lower():
                    raise PrimoKontoKonflikt(KONFLIKT_MAIL_ABWEICHEND)
                return _rolle_angleichen(
                    client, superuser_token_, konto, server_rolle
                )

            vorhanden = _hole_benutzer(client, superuser_token_, adresse)
            if vorhanden is not None:
                # Adressgleichheit ist KEIN Nachweis: das Konto kann von Hand
                # angelegt worden sein, jemand anderem gehoeren oder das
                # Maschinenkonto sein. Nicht anfassen.
                raise PrimoKontoKonflikt(KONFLIKT_KONTO_EXISTIERT)

            # PocketBase verlangt passwordConfirm == password (live geprueft:
            # leer -> 400 "validation_required"). Das Passwort wird nie benutzt;
            # Anmeldung laeuft ausschliesslich ueber impersonate.
            zufall = secrets.token_urlsafe(_ZUFALLS_PASSWORT_LAENGE)
            antwort = client.post(
                _url(PFAD_USERS),
                json={
                    "email": adresse,
                    "password": zufall,
                    "passwordConfirm": zufall,
                    "verified": True,
                    "serverRole": server_rolle,
                },
                headers=_auth_kopf(superuser_token_),
            )
            if antwort.status_code not in (200, 201):
                raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
            konto = _json_aus_antwort(antwort)
            neue_id = str(konto.get("id") or "").strip()
            if not neue_id:
                raise PrimoAbgelehnt(502, "Antwort ohne id")
            _zuordnung_speichern(kennung, neue_id, adresse)
            return konto
    except httpx.HTTPError as exc:
        raise PrimoNichtErreichbar("Primo ist nicht erreichbar.") from exc


def _hole_benutzer_per_id(
    client: httpx.Client, token: str, record_id: str
) -> dict[str, Any] | None:
    """Liest den `users`-Datensatz zu einer PocketBase-id (kein Filter-Ratespiel)."""
    antwort = client.get(_url(f"{PFAD_USERS}/{record_id}"), headers=_auth_kopf(token))
    if antwort.status_code == 404:
        return None
    if antwort.status_code != 200:
        raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
    return _json_aus_antwort(antwort)


def _rolle_angleichen(
    client: httpx.Client,
    token: str,
    konto: dict[str, Any],
    server_rolle: str,
) -> dict[str, Any]:
    """Setzt die Primo-Serverrolle auf einem ZUGEORDNETEN Konto (sonst nichts)."""
    if str(konto.get("serverRole") or "") == server_rolle and konto.get("verified") is True:
        return konto
    antwort = client.patch(
        _url(f"{PFAD_USERS}/{konto.get('id')}"),
        json={"serverRole": server_rolle, "verified": True},
        headers=_auth_kopf(token),
    )
    if antwort.status_code != 200:
        raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
    return _json_aus_antwort(antwort)


# ── S4c: Uebergabe-Token ────────────────────────────────────────────────────


def uebergabe_token(record_id: str, superuser_token_: str) -> str:
    """Kurzlebiges Token fuer `record_id` (PocketBase `impersonate`).

    Gepruefte PocketBase-0.35-Route (gegen die laufende Instanz verifiziert):
    `POST /api/collections/users/impersonate/{id}` mit Superuser-Token und
    `{"duration": <Sekunden>}`. Antwort ist ein Auth-Datensatz mit `token`.
    """
    if not str(record_id or "").strip():
        raise PrimoAbgelehnt(400, "Konto ohne id")
    try:
        with _client() as client:
            antwort = client.post(
                _url(PFAD_IMPERSONATE.format(record_id=record_id)),
                json={"duration": int(settings.primo_token_sekunden)},
                headers=_auth_kopf(superuser_token_),
            )
    except httpx.HTTPError as exc:
        raise PrimoNichtErreichbar("Primo ist nicht erreichbar.") from exc
    if antwort.status_code != 200:
        raise PrimoAbgelehnt(antwort.status_code, _fehlertext(antwort))
    koerper = _json_aus_antwort(antwort)
    token = str(koerper.get("token") or "").strip()
    if not token:
        raise PrimoAbgelehnt(200, "Antwort ohne Token")
    return token


# ── S4d: Fragment-Format ────────────────────────────────────────────────────


def _base64url(daten: bytes) -> str:
    """base64url ohne Auffuellzeichen (URL-Fragment-tauglich)."""
    return base64.urlsafe_b64encode(daten).decode("ascii").rstrip("=")


def uebergabe_url(token: str, record: dict[str, Any]) -> str:
    """Browser-URL: `{PRIMO_PUBLIC_URL}/diakronos-sso.html#token=…&record=…`.

    Das Token steht AUSSCHLIESSLICH im Fragment (`#`): ein Fragment wird vom
    Browser nicht an einen Server gesendet und landet damit in keinem
    Proxy-/Server-Log. `record` ist das JSON des `users`-Datensatzes,
    base64url-kodiert (damit keine `#`/`&` im Fragment kollidieren).
    """
    basis = settings.primo_public_url_effektiv
    if not basis:
        raise PrimoNichtKonfiguriert("PRIMO_PUBLIC_URL/PRIMO_URL fehlt.")
    roh = json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return (
        f"{basis}/diakronos-sso.html"
        f"#token={token}&record={_base64url(roh)}"
    )


def login_uebergabe(
    user: str, email: str, rollen: list[str] | tuple[str, ...]
) -> str:
    """Kompletter Uebergabeweg (S4a-d) — Rueckgabe ist die Browser-URL.

    Reihenfolge:
      1. Superuser-Token holen (`auth-with-password`).
      2. Primo-Konto per Zuordnung sicherstellen + Serverrolle angleichen.
      3. Kurzlebiges Impersonate-Token holen.
      4. Fragment-URL bauen.

    Der Aufrufer prueft die Rollen VORHER (S3, `darf_website`) — hier wird
    nur noch die Primo-Rolle bestimmt. Fehlt eine passende Rolle, ist das ein
    Programmierfehler des Aufrufers, kein Primo-Fehler.

    `user` ist die Diakronos-Benutzerkennung: sie ist der Schluessel der
    Zuordnung (`website_primo_konto`). Kommt `PrimoKontoKonflikt`, hat der
    Aufrufer das zu 409 zu machen — hier wird nichts angefasst.
    """
    primo_rolle = primaere_primo_rolle(rollen)
    if primo_rolle is None:
        raise PrimoAbgelehnt(403, "keine fuer Primo freigegebene Rolle")

    adresse = str(email or "").strip()
    # (B1) Gesperrte Adressen VOR jedem Aufruf nach Primo ablehnen — auch vor
    # dem Superuser-Login. Sonst waere das Merkmal "Adresse gesperrt" erst
    # nach einem HTTP-Aufruf bekannt, und ein gesperrtes Konto koennte im
    # Fehlerfall doch angelegt werden.
    if settings.primo_ist_geschuetzt(adresse):
        raise PrimoKontoKonflikt(KONFLIKT_GESCHUETZT)

    # BS-2d3-Nacharbeit: der Merker steht an EINER Stelle (hier in
    # `superuser_token`). Wer uebergibt, meldet sich damit nicht erneut an,
    # wenn kurz vorher ein Import/Stand-Lesen dasselbe Token geholt hat.
    for _versuch in range(2):
        superuser = superuser_token()
        try:
            konto = konto_sicherstellen(user, email, primo_rolle, superuser)
            record_id = str(konto.get("id") or "").strip()
            if not record_id:
                raise PrimoAbgelehnt(502, "Konto ohne id")
            token = uebergabe_token(record_id, superuser)
            return uebergabe_url(token, konto)
        except PrimoAbgelehnt as fehler:
            # Nur der Token-Fall wird wiederholt (401/403 aus einem der beiden
            # Aufrufe): Merker verwerfen und GENAU EINMAL neu anmelden.
            if fehler.status not in TOKEN_UNGUELTIG_STATUS or _versuch:
                raise
            token_verwerfen(nur_wenn=superuser)
    # Unerreichbar: die Schleife wiederholt genau zweimal und kehrt oben zurueck
    # oder reicht den Fehler durch.
    raise PrimoAbgelehnt(502, "Anmeldung nicht abgeschlossen")
