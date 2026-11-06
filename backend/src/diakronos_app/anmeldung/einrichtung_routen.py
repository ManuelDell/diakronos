"""ON-1 — die Seiten der Ersteinrichtung (`/einrichtung/<token>`).

WAS HIER PASSIERT
-----------------
  GET  …/einrichtung/<token>   gueltig -> „Administrator anlegen" (Entwurf 02/13)
                               sonst   -> „Link ungueltig" (Entwurf 03), 404
  POST …/einrichtung/<token>   legt den Administrator + sein Mitglied an,
                               verbraucht den Token, legt die Sitzung an und
                               leitet in die App (303)

Warum eine EIGENE Route und nicht `/api/method/...`: die Seite wird wie die
Anmeldung serverseitig gerendert (ON-0a-Rahmen, ``einrichtung_seiten``), hat ein
echtes HTML-Formular und braucht keine JSON-Huelle. Sie liegt deshalb bei den
Server-Seiten (`anmeldung/routen.py`, `passwortseite.py`) und nicht im
Frappe-kompatiblen Methodenregister — damit taucht sie auch nicht im
whitelist-Inventar auf (sie ist keine Methode unter `/api/method`).

SICHERHEIT (Karte E3/E4)
------------------------
  * **Kein Orakel**: „nie gueltig", „abgelaufen" und „Einrichtung schon
    abgeschlossen" liefern DIESELBE Seite mit demselben Status (404) und
    demselben Text.
  * **Herkunft wie die Anmeldung (SEC-4)**: ein FREMDER `Origin`/`Referer` oder
    `Sec-Fetch-Site: cross-site` wird abgewiesen. Fehlt die Kopfzeile, entscheidet
    der signierte Masken-Token `_csrf` (aus derselben Quelle wie die
    Anmeldemaske). Ohne beides — und ohne Browser-Merkmal — bleibt es wie bei
    der Anmeldung erlaubt (Skripte, Abnahme-Tools).
  * **Ratenbegrenzung**: die vorhandene Bremse der oeffentlichen
    Registrierung (`registrierungsbremse.zaehle_validierung` fuer den
    Seitenaufruf, `pruefe(ip, token)` fuer das Absenden) — keine zweite,
    eigene Zaehllogik.
  * **Passwortregeln**: dieselben wie beim Passwort-Setzen (`pruefe_passwort`
    aus `anmeldung/passwortzugang.py`) PLUS die Regeln aus dem Entwurf
    (mindestens 12 Zeichen, ein Grossbuchstabe, eine Zahl).
  * **EINE Transaktion**: Token pruefen + verbrauchen, Benutzer + Rollen +
    Mitglied anlegen. Scheitert etwas, bleibt der Link gueltig.
  * **Wettlauf**: `einrichtung.verbrauche_mit` sperrt die Zeile; der zweite
    parallele POST findet keinen gueltigen Token und bekommt „Link ungueltig".
  * **Logs**: nur „Systemadministrator ueber Einrichtungslink angelegt." —
    nie Token, nie Passwort, nie E-Mail.
"""

from __future__ import annotations

import logging
import re

from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from diakronos_app import base_path, einrichtung
from diakronos_app.anmeldung.registrierungslink import jetzt_gemeinde
from diakronos_app.einrichtung_seiten import (
    EINRICHTUNGSLINK_BEFEHL,
    seite_anlegen,
    seite_ungueltig,
)

logger = logging.getLogger("diakronos_app.einrichtung.routen")

__all__ = ["registriere_routen", "ZIEL_NACH_ANLAGE", "EinrichtungsAccessLogFilter"]

#: Ziel nach dem Anlegen. Der Assistent (ON-3) wohnt in der SPA unter
#: `#/einrichtung`; bis dahin landet man auf der Uebersicht. Das ist KEIN
#: Fehler — die SPA kennt die Adresse noch nicht und zeigt ihre Seite
#: „Seite nicht gefunden" mit einem Weg zurueck. Bewusst KEIN `#/`: ein
#: spaeterer Assistent haengt sich an genau diese Adresse an.
ZIEL_NACH_ANLAGE = "/diakonos#/einrichtung"

#: Abgelehnter POST ohne gueltigen Token: 404 wie der GET (kein Unterschied).
STATUS_UNGUELTIG = 404

#: Platzhalter im Zugriffsprotokoll statt des Tokens.
TOKEN_PLATZHALTER = "***"

#: Praefix des Einrichtungspfads (ohne Betriebs-Praefix, das davor steht).
_SEITEN_PRAEFIX = "/einrichtung/"


def _ohne_praefix(pfad: str) -> str:
    """Pfad ohne ``DIAKRONOS_BASE_PATH`` — der Token steht dahinter."""
    from diakronos_app.settings import settings

    praefix = str(
        getattr(settings, "diakronos_base_path", "")
        or getattr(settings, "base_path", "")
        or ""
    ).strip().rstrip("/")
    if praefix and pfad.startswith(praefix):
        return pfad[len(praefix):] or "/"
    return pfad


class EinrichtungsAccessLogFilter(logging.Filter):
    """ON-1b (F1): der Einrichtungs-Token darf nicht ins Zugriffsprotokoll.

    Gleiche Bauform wie ``OAuthAccessLogFilter`` (``google_callback``) fuer den
    OAuth-Code: ``uvicorn.access`` protokolliert sonst jede Anfrage mit vollem
    Pfad — und der Pfad IST hier das Geheimnis. Ein Token im Log ist ein
    benutzbarer Generalschluessel, solange er nicht abgelaufen ist.

    Umgeschrieben wird die Anfragezeile zu ``/einrichtung/***``; der Betriebs-
    Praefix bleibt davor stehen (``/diakronos/einrichtung/***``). Kopfzeilen,
    Status und Zeiten bleiben unveraendert — das Log bleibt brauchbar.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 — logging-API
        args = record.args
        # uvicorn.access: (client_addr, method, full_path, http_version, status)
        if not (isinstance(args, tuple) and len(args) == 5):
            return True
        ziel = str(args[2])
        pfad, fragezeichen, query = ziel.partition("?")
        app_pfad = _ohne_praefix(pfad)
        if not app_pfad.startswith(_SEITEN_PRAEFIX):
            return True
        praefix = pfad[: len(pfad) - len(app_pfad)]
        neu = list(args)
        neu[2] = f"{praefix}{_SEITEN_PRAEFIX}{TOKEN_PLATZHALTER}{fragezeichen}{query}"
        record.args = tuple(neu)
        return True


def installiere_log_filter() -> None:
    """Haengt den Filter EINMAL an ``uvicorn.access`` (idempotent)."""
    zugriff = logging.getLogger("uvicorn.access")
    for vorhanden in zugriff.filters:
        if isinstance(vorhanden, EinrichtungsAccessLogFilter):
            return
    zugriff.addFilter(EinrichtungsAccessLogFilter())


installiere_log_filter()

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Antworten ──────────────────────────────────────────────────────────────


#: Kopfzeilen, die die Sicherheitsschicht (`sec_header`) NICHT setzt und die
#: eine Server-Seite trotzdem braucht. `Content-Security-Policy` steht hier
#: BEWUSST nicht: sie wird zentral angehaengt, und zwei Policies im selben
#: Feld kombiniert der Browser zur SCHNITTMENGE — eine zweite, eigene Policy
#: haette das Formular unbedienbar gemacht (im Abnahme-Lauf gemessen).
_EIGENE_KOPFZEILEN = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def _html(text: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(text, status_code=status, headers=dict(_EIGENE_KOPFZEILEN))


def _login_adresse() -> str:
    return base_path.pfad("/login")


def _api_adresse(token: str) -> str:
    """POST-Adresse des Formulars (Praefix-bewusst, Token kodiert)."""
    from urllib.parse import quote

    return base_path.pfad(f"/einrichtung/{quote(token, safe='')}")


def _ungueltig(fehler: str = "", status: int = STATUS_UNGUELTIG) -> HTMLResponse:
    return _html(seite_ungueltig(login=_login_adresse(), status_fehler=fehler), status)


# ── Herkunft und CSRF (SEC-4, dieselbe Quelle wie die Anmeldung) ───────────


def _herkunft_abgelehnt(request: Request) -> bool:
    """Fremder Browser-Kontext? Dann wird der POST abgewiesen.

    Gelesen wird die EINE Regel der Anmeldung (`api/auth._herkunft_ist_fremd`),
    nicht eine zweite Kopie: ein FREMDES `Origin`/`Referer` oder
    `Sec-Fetch-Site: cross-site`. Fehlen alle Merkmale, ist es kein Browser —
    dann entscheidet der Masken-Token (``_csrf``) bzw. bleibt es erlaubt
    (Skripte, Abnahme-Tools). Dieselbe Bewertung wie `_browser_formular_ohne_token`
    in `api/auth.py`.
    """
    from diakronos_app.api.auth import _herkunft_ist_fremd

    kopf = request.headers
    if str(kopf.get("sec-fetch-site") or "").strip().lower() == "cross-site":
        return True
    return _herkunft_ist_fremd(kopf)


def _maske_token_gueltig(wert: str) -> bool:
    if not wert:
        return False
    try:
        from diakronos_app.anmeldung.maske_token import token_ist_gueltig

        return token_ist_gueltig(wert)
    except Exception:  # noqa: BLE001 — jeder Fehler heisst „nicht nachweisbar"
        return False


def _masken_pruefung_noetig(request: Request, felder: dict) -> bool:
    """Muss der ``_csrf`` gelten, oder ist das ein reiner Skript-Aufruf?

    ON-1b (F6): frueher hing beides zusammen — ``_maske_token_gueltig("")``
    war ``False``, und erst ein zusätzliches ``_ist_browser()`` entschied, ob
    das ein Fehler ist. Ein POST mit gueltigem ``_csrf`` im Koerper, aber
    ohne Browser-Kopfzeilen (Abnahme-Tools), gehoert ebenfalls hierher: dann
    ist der Masken-Token die Pruefung.

    ``True`` heisst: ``_csrf`` ist Pflicht (Browser erkennbar — auch wenn ein
    Token mitgeschickt wurde).
    """
    value = _text(felder, "_csrf")
    if value and _maske_token_gueltig(value):
        return False
    return _ist_browser(request)


# ── Formularpruefung ───────────────────────────────────────────────────────


class FormularFehler(Exception):
    """Eine Meldung fuer den Menschen — keine internen Daten."""


def _text(felder: dict, name: str) -> str:
    return str(felder.get(name) or "").strip()


def _pruefe_werte(felder: dict) -> dict:
    """Prueft das Formular und gibt die bereinigten Werte zurueck.

    Reihenfolge wie im Entwurf: Vorname, Nachname, E-Mail, Passwort,
    Wiederholung. Die Passwortregeln sind die der bestehenden
    Passwort-Setzen-Logik (`pruefe_passwort`) — bewusst KEINE zweite Fassung.
    """
    from diakronos_app.anmeldung.passwortzugang import pruefe_passwort

    vorname = _text(felder, "vorname")
    nachname = _text(felder, "nachname")
    email = _text(felder, "email").lower()
    passwort = str(felder.get("passwort") or "")
    wiederholung = str(felder.get("wiederholung") or "")

    if not vorname or not nachname:
        raise FormularFehler("Bitte Vor- und Nachnamen angeben.")
    if len(vorname) > 140 or len(nachname) > 140:
        raise FormularFehler("Vor- und Nachname dürfen höchstens 140 Zeichen haben.")
    if not _EMAIL.match(email) or len(email) > 320:
        raise FormularFehler("Bitte eine gültige E-Mail-Adresse angeben.")
    if passwort != wiederholung:
        raise FormularFehler("Die Passwörter stimmen nicht überein.")
    # Die Regeln des Entwurfs (Frame 02) ZUERST — sie sind strenger als die
    # allgemeine Mindestlaenge und nennen dem Menschen den naechsten Schritt.
    if len(passwort) < 12:
        raise FormularFehler("Das Passwort muss mindestens 12 Zeichen haben.")
    if not re.search(r"[A-ZÄÖÜ]", passwort):
        raise FormularFehler("Das Passwort muss einen Großbuchstaben enthalten.")
    if not re.search(r"[0-9]", passwort):
        raise FormularFehler("Das Passwort muss eine Zahl enthalten.")
    # Und die BESTEHENDE Passwortregel (Laenge 8..1024) — keine zweite Fassung.
    try:
        pruefe_passwort(passwort)
    except Exception as exc:  # noqa: BLE001 — Meldung der bestehenden Regeln
        raise FormularFehler(getattr(exc, "message", "") or str(exc)) from None
    return {
        "vorname": vorname,
        "nachname": nachname,
        "email": email,
        "passwort": passwort,
    }


# ── Anlegen (EINE Transaktion) ─────────────────────────────────────────────


def _email_belegt(sess, email: str) -> bool:
    """Ist die Adresse schon ein Konto ODER schon ein Mitglied? (case-insensitiv)

    `mitglied.email` traegt seit SEC-b einen partiellen Unique-Index auf
    `lower(trim(email))`; ein doppelter Wert wuerde hier sonst als
    Datenbankfehler auftauchen statt als verstaendliche Meldung.
    """
    from sqlalchemy import func, select

    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    if sess.scalar(select(func.count()).select_from(User).where(func.lower(User.email) == email)):
        return True
    if sess.scalar(select(func.count()).select_from(User).where(func.lower(User.name) == email)):
        return True
    return bool(
        sess.scalar(
            select(func.count())
            .select_from(Mitglied)
            .where(func.lower(func.trim(Mitglied.email)) == email)
        )
    )


def _stand_anlegen(sess) -> None:
    """Legt die Stand-Zeile der Ersteinrichtung an (ON-3b, Orchestrator-Nachtrag).

    Idempotent: existiert die Zeile schon, bleibt sie unveraendert (ein zweiter
    Aufruf darf einen laufenden Assistenten NICHT zuruecksetzen). Die Zeile ist
    die Voraussetzung dafuer, dass `einrichtung_offen` true meldet und die SPA
    den frisch angelegten Admin in den Assistenten fuehrt.
    """
    from diakronos_app.models.einrichtung import EINRICHTUNG_STAND_NAME, EinrichtungStand

    if sess.get(EinrichtungStand, EINRICHTUNG_STAND_NAME) is not None:
        return
    jetzt = jetzt_gemeinde().replace(tzinfo=None, microsecond=0)
    sess.add(EinrichtungStand(
        name=EINRICHTUNG_STAND_NAME,
        assistent_abgeschlossen=False,
        created=jetzt,
        modified=jetzt,
    ))
    sess.flush()


def _mitglied_anlegen(sess, *, vorname: str, nachname: str, email: str, konto: str) -> str:
    """Legt das Mitglied zur Person an (Vorname/Nachname/E-Mail, verknuepft ueber `user`).

    Die Kennung vergibt der Server — dieselbe Regel wie ueberall (ID-1d):
    `api_helpers._new_name()`, nie ein Klarname. Fachliche Ableitung aus der
    Karte: „zugehoeriges Mitglied (Vorname/Nachname/E-Mail, verknuepft ueber
    Mitglied.user)".
    """
    from diakronos_app.frappe_compat.api_helpers import _new_name
    from diakronos_app.models.diakonos import Mitglied

    jetzt = jetzt_gemeinde().replace(tzinfo=None, microsecond=0)
    mitglied = Mitglied(
        name=_new_name(),
        vorname=vorname,
        nachname=nachname,
        email=email,
        user=konto,
        docstatus=0,
        idx=0,
        creation=jetzt,
        modified=jetzt,
        owner=konto,
        modified_by=konto,
    )
    sess.add(mitglied)
    sess.flush()
    return mitglied.name


def _konto_anlegen(sess, *, email: str, vorname: str, nachname: str, passwort: str) -> None:
    """Legt Benutzer + Rollen an — Rollen aus `erstinstallation.ADMIN_ROLLEN`.

    Dieselbe Rollenquelle wie der Weg ueber `ADMIN_EMAIL` (A1c3: EINE Wahrheit
    fuer „wer ist Administrator"), nicht eine dritte Kopie.
    """
    from diakronos_app.erstinstallation import ADMIN_ROLLEN
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User

    sess.add(
        User(
            name=email,
            email=email,
            full_name=f"{vorname} {nachname}".strip(),
            enabled=True,
            user_type="System User",
            password_hash=neuer_hash(passwort),
        )
    )
    sess.flush()
    # ON-6: der ERSTE Administrator ist root — alle Rechte, geschuetzt. Die
    # Kennzeichnung (Eintrag in `gemeinde_einstellungen.root_benutzer` +
    # Kennrolle) entsteht in DIESER Transaktion, damit es nie ein Konto mit
    # Root-Rolle ohne Eintrag gibt (und umgekehrt).
    from diakronos_app import root_benutzer

    root_benutzer.markiere(sess, email)
    for idx, rolle in enumerate(ADMIN_ROLLEN, start=1):
        sess.add(
            HasRole(
                name=f"{email}-{rolle}",
                parent=email,
                parenttype="User",
                parentfield="roles",
                role=rolle,
                docstatus=0,
                idx=idx,
            )
        )
    sess.flush()


def _benutzer_vorhanden(sess) -> bool:
    from diakronos_app.models.core import User

    return sess.query(User).first() is not None


# ── Routen ─────────────────────────────────────────────────────────────────


def _bremse_get(token: str) -> bool:
    """Ratenbegrenzung des Seitenaufrufs (eigener Zaehler, wie Registrierungsseite)."""
    from diakronos_app import request_context

    from diakronos_app.anmeldung import registrierungsbremse

    return registrierungsbremse.zaehle_validierung(
        request_context.zaehler_client_ip(), token=token
    )


def _bremse_post(token: str) -> bool:
    """Ratenbegrenzung des Absendens (Adresse + Token)."""
    from diakronos_app import request_context
    from diakronos_app.anmeldung import registrierungsbremse

    erlaubt, _grund = registrierungsbremse.pruefe(
        request_context.zaehler_client_ip(), token
    )
    return erlaubt


def registriere_routen(app: FastAPI) -> None:
    """Registriert GET und POST unter `/einrichtung/<token>`.

    MUSS vor `mount_spa(app)` laufen (wie die Anmelde-Routen) und liegt damit
    automatisch unter dem Betriebs-Praefix (der Praefix umschliesst die ganze
    App, `base_path.praefigiere`).
    """

    @app.get("/einrichtung/{token}", include_in_schema=False)
    def einrichtung_seite(request: Request, token: str) -> Response:
        from diakronos_app.db import SessionLocal

        if not _bremse_get(token):
            return _ungueltig(
                "Es sind gerade zu viele Aufrufe eingegangen. Bitte versuchen Sie es "
                "in ein paar Minuten erneut.",
                status=429,
            )

        # Ungueltig, abgelaufen ODER schon eingerichtet: dieselbe Antwort.
        # ON-1b (F3/F6): der GET SCHREIBT NICHT — `zaehle=False` laesst den
        # Diagnose-Zaehler unberuehrt. Ein GET, der eine Spalte fortschreibt,
        # ist ein schreibender GET (SEC-11) und liess sich ausserdem von
        # aussen vermehren, indem jemand den Link oft genug laedt.
        with SessionLocal() as sess:
            if _benutzer_vorhanden(sess) or not einrichtung.pruefe_token(token, zaehle=False):
                return _ungueltig()

        csrf_token = ""
        try:
            from diakronos_app.anmeldung.maske_token import erzeuge_token

            csrf_token = erzeuge_token()
        except Exception:  # noqa: BLE001 — ohne Schluessel bleibt die Maske bedienbar
            logger.warning("Einrichtungsseite ohne Masken-Token (SECRET_KEY fehlt?)")
        return _html(
            seite_anlegen(
                api=_api_adresse(token), login=_login_adresse(), csrf_token=csrf_token
            )
        )

    @app.post("/einrichtung/{token}", include_in_schema=False)
    async def einrichtung_anlegen(request: Request, token: str) -> Response:
        from diakronos_app.db import SessionLocal
        from diakronos_app.frappe_compat import sitzungen
        from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers

        if not _bremse_post(token):
            return _ungueltig(
                "Es sind gerade zu viele Versuche eingegangen. Bitte versuchen Sie es "
                "in ein paar Minuten erneut.",
                status=429,
            )

        if _herkunft_abgelehnt(request):
            logger.info("Einrichtung: Absendung von fremder Herkunft abgewiesen.")
            return _ungueltig("Die Anfrage konnte nicht geprüft werden.", status=403)

        felder = await _formular_felder(request)
        if _masken_pruefung_noetig(request, felder):
            # Fehlender/falscher Masken-Token: nur dann ein Fehler, wenn die
            # Anfrage nach einem BROWSER aussieht (Origin/Referer/Sec-Fetch).
            # Reine Skript-Aufrufe (Abnahme, Tests) bleiben wie bei der Anmeldung.
            logger.info("Einrichtung: Absendung ohne gueltigen Masken-Token.")
            return _ungueltig("Die Anfrage konnte nicht geprüft werden.", status=403)

        # ON-1b (F6): der TOKEN zuerst, ohne Zaehlen. Ein ungueltiger Link
        # bekommt IMMER „Link ungueltig" — auch wenn die Formularfelder zusaetzlich
        # falsch sind. Sonst verriete die Meldung („Passwort zu kurz") indirekt,
        # dass der Token gueltig war, waehrend der GET „ungueltig" sagte. Das
        # Loeschen bleibt `verbrauche_mit` in der Transaktion unten vorbehalten
        # (hier wird nichts geschrieben).
        if not einrichtung.pruefe_token(token, zaehle=False):
            return _ungueltig()

        try:
            werte = _pruefe_werte(felder)
        except FormularFehler as fehler:
            # Formular erneut zeigen — der Link bleibt gueltig (nichts verbraucht).
            return _html(
                _fehlerseite(str(fehler), api=_api_adresse(token), login=_login_adresse()),
                status=417,
            )

        sess = SessionLocal()
        try:
            if _benutzer_vorhanden(sess):
                sess.rollback()
                return _ungueltig()
            if not einrichtung.verbrauche_mit(sess, token):
                sess.rollback()
                return _ungueltig()
            if _email_belegt(sess, werte["email"]):
                # Nichts angelegt worden ist noch nicht geschehen: die
                # Token-Zeile wurde in DIESER Transaktion geloescht — der
                # rollback stellt sie wieder her, der Link bleibt nutzbar.
                sess.rollback()
                return _html(
                    _fehlerseite(
                        "Diese E-Mail-Adresse ist bereits für ein Konto oder ein "
                        "Mitglied vergeben. Bitte verwenden Sie eine andere Adresse.",
                        api=_api_adresse(token),
                        login=_login_adresse(),
                    ),
                    status=417,
                )
            _konto_anlegen(
                sess,
                email=werte["email"],
                vorname=werte["vorname"],
                nachname=werte["nachname"],
                passwort=werte["passwort"],
            )
            _mitglied_anlegen(
                sess,
                vorname=werte["vorname"],
                nachname=werte["nachname"],
                email=werte["email"],
                konto=werte["email"],
            )
            # ON-3b (Orchestrator-Nachtrag): Ab jetzt LAEUFT die Ersteinrichtung.
            # Die Stand-Zeile wird hier angelegt (nicht erst beim ersten
            # `einrichtung.status`-Aufruf) — sonst meldete die SPA beim ersten
            # Oeffnen „kein Stand“ und der Admin landete NICHT im Assistenten.
            # Fehlt die Zeile, ist `einrichtung_offen` false (keine Leitung).
            _stand_anlegen(sess)
            sess.commit()
        except Exception as exc:  # noqa: BLE001 — nie rohe Fehler an den Browser
            sess.rollback()
            logger.warning("Einrichtung fehlgeschlagen (%s).", exc.__class__.__name__)
            return _html(
                _fehlerseite(
                    "Der Administrator konnte nicht angelegt werden. Bitte versuchen "
                    "Sie es erneut.",
                    api=_api_adresse(token),
                    login=_login_adresse(),
                ),
                status=500,
            )
        finally:
            sess.close()

        # Sitzung wie beim Login (Sitzungsfixierung vermeiden): alte sid weg.
        alt = sid_aus_headers(request.headers)
        if alt:
            try:
                sitzungen.loeschen(alt)
            except Exception:  # noqa: BLE001 — alte Sitzung ist nicht kritisch
                pass
        # ON-1b (F4): KEINE SSO-Kennzeichnung. Das Kennzeichen `sso=True`
        # ueberspringt in `auth_middleware` die Pruefung „Passwortwechsel
        # noetig" — richtig fuer einen bestaetigten Anbieter-Login, falsch
        # hier: angelegt wird ein lokales Konto mit einem selbst gewaehlten
        # Passwort. Ein `sso=True` haette eine spaeter gesetzte
        # Wechselpflicht (z. B. nach einer Zuruecksetzung durch einen
        # Administrator) stillschweigend ausgehebelt. Der neue Benutzer hat
        # keinen `Passwortzugang` mit `wechsel_noetig` — die Pruefung greift
        # also nicht und die Sitzung bleibt gueltig.
        sid, _csrf = sitzungen.anlegen(werte["email"], sso=False)

        ziel = base_path.pfad(ZIEL_NACH_ANLAGE)
        antwort: Response = RedirectResponse(
            ziel, status_code=303, headers=dict(_EIGENE_KOPFZEILEN)
        )
        from diakronos_app.api.auth import _cookie_path, _loesche_wurzel_cookie, _secure_flag
        from diakronos_app.settings import settings

        antwort.set_cookie(
            key="sid",
            value=sid,
            httponly=True,
            samesite="lax",
            path=_cookie_path(),
            secure=_secure_flag(),
            max_age=int(settings.session_ttl_seconds),
        )
        _loesche_wurzel_cookie(antwort)
        # Nur die Kopfzeilen, die NICHT schon von der Sicherheitsschicht
        # gesetzt sind: `sec_header` haengt eine strengere Policy an jede
        # Antwort (mit `form-action`), und die darf hier nicht ueberschrieben
        # werden (der Browser nimmt die RESTRIKTIVERE von beiden — eine
        # zweite Policy im selben Feld macht die Seite unbedienbar).
        for name, wert in _EIGENE_KOPFZEILEN.items():
            antwort.headers[name] = wert
        logger.info("Systemadministrator ueber Einrichtungslink angelegt.")
        return antwort


# ── Helfer: Formular lesen, Fehlerseite ────────────────────────────────────


async def _formular_felder(request: Request) -> dict:
    """Formularfelder lesen — ``x-www-form-urlencoded`` UND ``multipart``.

    Ein Browser schickt das Formular urlencoded; Tests/Abnahme duerfen auch
    JSON schicken (dann liegen die Felder direkt im Koerper). Alles andere
    ergibt ein leeres Formular — der Aufruf faellt dann in die Validierung.
    """
    art = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if art == "application/json":
        try:
            daten = await request.json()
        except Exception:  # noqa: BLE001 — kaputter Koerper = leeres Formular
            return {}
        return daten if isinstance(daten, dict) else {}
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001 — kein Formular im Koerper
        return {}
    return {k: v for k, v in form.items() if isinstance(v, str)}


def _ist_browser(request: Request) -> bool:
    """Sieht die Anfrage nach einem Browser aus? (dann gilt der Masken-Token)"""
    kopf = request.headers
    return bool(
        str(kopf.get("origin") or "").strip()
        or str(kopf.get("referer") or "").strip()
        or str(kopf.get("sec-fetch-site") or "").strip()
    )


def _escape(text: str) -> str:
    import html as _html_mod

    return _html_mod.escape(text, quote=True)


def _fehlerseite(meldung: str, *, api: str, login: str) -> str:
    """Seite „Administrator anlegen" mit einer Meldung ueber dem Formular.

    Dieselbe Maske wie der GET (kein zweites Markup): der Mensch soll seine
    Eingabe wiederholen koennen, ohne den Link neu zu laden.

    ON-1b (F2): die Maske braucht ein FRISCHES ``_csrf``. Vorher stand hier
    ``csrf_token=""`` — der Browser schickte beim naechsten Absenden einen
    leeren Masken-Token, und die Herkunftspruefung wies ihn mit 403 ab: ein
    einziger Tippfehler im Passwort machte den Link im Browser unbrauchbar
    (Neuladen half, weil der GET ein neues Token setzt). Ohne Schluessel
    bleibt es wie beim GET bei einer Maske ohne Token (Skripte, Tests).
    """
    csrf_token = ""
    try:
        from diakronos_app.anmeldung.maske_token import erzeuge_token

        csrf_token = erzeuge_token()
    except Exception:  # noqa: BLE001 — ohne Schluessel bleibt die Maske bedienbar
        logger.warning("Einrichtungs-Fehlerseite ohne Masken-Token (SECRET_KEY fehlt?)")
    seite = seite_anlegen(api=api, login=login, csrf_token=csrf_token)
    return seite.replace(
        '<p id="fehler" class="dk-meldung" role="alert" tabindex="-1" hidden></p>',
        '<p id="fehler" class="dk-meldung" role="alert" tabindex="-1">'
        + _escape(meldung)
        + "</p>",
    )
