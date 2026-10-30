"""WEB-1 — API des optionalen Website-Moduls (Primo-Anbindung).

Drei Endpunkte, alle ueber den normalen Methoden-Router erreichbar
(`/api/method/<pfad>`, `allow_guest=False` — die Anmeldung prueft der Router
schon):

    diakronos_app.api.website.status             (GET)  -> Zustand der Anbindung
    diakronos_app.api.website.login_uebergabe    (POST) -> Browser-URL mit Token
    diakronos_app.api.website.rollen             (GET)  -> Rollen-Auskunft

Kurzpfade ueber das Register: `website.status`, `website.login_uebergabe`,
`website.rollen`.

S3 — Rollen-Gate
----------------
Zugriff haben NUR `System Manager`, `Administrator` und `Website-Moderator`.
Alle anderen bekommen **403** (`PermissionError` der Compat-Schicht, also
HTTP 403 mit `exc_type=PermissionError`). Die Pruefung steht VOR jedem Aufruf
nach Primo: eine Rolle, die in Diakronos entzogen wird, sperrt den Zugang
sofort — auch wenn in Primo noch ein Konto mit Serverrolle liegt.

CSRF
----
`login_uebergabe` ist ein POST und laeuft damit durch die CSRF-Middleware
(`X-Frappe-CSRF-Token` gegen die Sitzung). Ein Aufruf ohne gueltiges Token
endet mit 417 `CSRFTokenError` — das ist gewollt und wird im Test festgehalten.

Secrets
-------
Der Endpunkt gibt AUSSCHLIESSLICH die Browser-URL zurueck (Token im
Fragment). Superuser-Zugang, Passwoerter und das Superuser-Token bleiben im
Prozess und tauchen in keiner Antwort und keiner Log-Zeile auf.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakronos.api.website"

import logging

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DienstNichtVerfuegbarError,
    KonfliktError,
    PermissionError as FrappePermissionError,
    throw,
)
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.session import session
from diakronos_app.website import primo

logger = logging.getLogger("diakronos_app.api.website")

#: Rollen mit Zugriff auf die Website-Funktionen (S3). EINE Wahrheit steht
#: im Adapter (`primo.WEBSITE_ROLLEN`); hier nur der sprechende Alias.
#: `Website-Moderator` steht bewusst NICHT in `VERANTWORTLICHE.ZUGANGS_ROLLEN`
#: (Vergabe bleibt System-Manager-Sache, WEB-1b).
WEBSITE_ROLLEN = primo.WEBSITE_ROLLEN


def _aktuelle_rollen() -> list[str]:
    return list(get_roles())


def _im_thread(fn, *args):
    """Fuehrt einen blockierenden Aufruf in einem eigenen Thread aus.

    Der Methoden-Router ruft Endpunkte SYNCHRON auf (er laeuft im
    Starlette-Threadpool), deshalb ist `async`/`run_in_threadpool` hier kein
    Weg. Ein eigener Thread mit hartem Zeitlimit haelt den Worker trotzdem
    frei: Primo ist ein Fremdsystem, und dessen Zeitlimit
    (`PRIMO_TIMEOUT_SEKUNDEN`) gilt je Aufruf, nicht fuer den ganzen Weg.
    """
    from concurrent.futures import ThreadPoolExecutor

    from diakronos_app.settings import settings

    limit = max(
        5.0,
        float(settings.primo_timeout_sekunden or 5.0) * 4 + 5.0,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn, *args).result(timeout=limit)


def _require_website_rolle() -> list[str]:
    """Weist alles ab, was keine Website-Rolle hat (403, fail closed)."""
    if session.user in ("", "Guest"):
        throw("Zugriff verweigert.", FrappePermissionError)
    rollen = _aktuelle_rollen()
    if not primo.darf_website(rollen):
        throw(
            "Nur für Systemmanager, Administratoren und Website-Moderatoren.",
            FrappePermissionError,
        )
    return rollen


def _email_des_benutzers() -> str:
    """E-Mail des angemeldeten Benutzers (Konto-Mail, nicht die Mitgliedsmail).

    Primo konten sind an der E-Mail identifiziert (`identityFields: [email]`).
    Ohne Adresse gibt es keinen Zugang — und keine erfundene Ersatzadresse.
    """
    from diakronos_app.frappe_compat.query import get_value

    user = session.user
    email = ""
    try:
        email = str(get_value("User", user, "email") or "").strip()
    except Exception:  # noqa: BLE001 — fehlende Zeile darf nicht 500 ergeben
        email = ""
    if not email:
        email = str(user or "").strip()
    if "@" not in email:
        throw(
            "Dein Benutzerkonto hat keine E-Mail-Adresse für die Website-Anmeldung.",
            FrappePermissionError,
        )
    return email


@whitelist(allow_guest=False)
def status():
    """Zustand der Primo-Anbindung (S2) — nur fuer berechtigte Rollen.

    Rueckgabe:

        {"status": "nicht_konfiguriert" | "nicht_erreichbar" | "verbunden",
         "version": str|null, "site_count": int|null, "url": str|null}

    Wirft nie wegen Primo: ein nicht erreichbarer Server ist der Zustand
    "nicht_erreichbar", keine Ausnahme.
    """
    _require_website_rolle()
    return primo.status()


@whitelist(allow_guest=False)
def rollen():
    """Auskunft fuer die Oberflaeche: darf dieser Benutzer Websites verwalten?

    Rueckgabe: `{"berechtigt": bool, "rollen": [...], "primo_rolle": str|null}`

    `primo_rolle` ist die Primo-Serverrolle, die beim naechsten Login gesetzt
    wird (`developer`/`editor`) — oder `null`, wenn keine Rolle passt.
    """
    _require_website_rolle()
    aktuelle = _aktuelle_rollen()
    return {
        "berechtigt": True,
        "rollen": aktuelle,
        "primo_rolle": primo.primaere_primo_rolle(aktuelle),
    }


@whitelist(allow_guest=False)
def login_uebergabe(request=None):
    """Uebergabe in Primo (S4) — gibt die Browser-URL zurueck.

    Rueckgabe: `{"url": "{PRIMO_PUBLIC_URL}/diakronos-sso.html#token=…&record=…"}`

    Ablauf: Rollen-Gate -> Superuser-Login -> Konto **per Zuordnung**
    sicherstellen (WEB-1b) -> Impersonate-Token -> Fragment-URL.

    (B2) NUR POST. Der Endpunkt stellt einen fremden Zugang aus; per GET
    (`<img src="…">`, geteilter Link, Vorabruf durch einen Proxy) waere das
    ohne Willen des Benutzers ausloesbar. Frappe liest Argumente zwar auch aus
    dem Query-String — deshalb steht die Methodenpruefung hier und nicht erst
    im Router, der GET/PUT/PATCH fuer alle Endpunkte offen laesst. Ergebnis
    ist 403 `PermissionError` (Frappe-Konvention fuer "darfst du nicht"), und
    Primo wird dabei NICHT angesprochen.

    Fehlerbilder (bewusst ohne Interna):
      * keine Berechtigung / andere Methode als POST -> 403 `PermissionError`
      * Zuordnung unklar (Adresse schon in Primo, Mail weicht ab, Systemkonto)
        -> 409 `ValidationError`
      * Primo nicht eingerichtet          -> 503 (`DienstNichtVerfuegbarError`)
      * Primo nicht erreichbar/Fehler     -> 503 (`DienstNichtVerfuegbarError`)

    Nach SEC-8 geht der Klassenname nur noch nach Allowlist nach aussen —
    `DienstNichtVerfuegbarError` erscheint dort als `exc_type = "Error"`. Die
    Oberflaeche unterscheidet am **HTTP-Status 503**, nicht am Namen.
    """
    from diakronos_app.frappe_compat.router import _ist_browser_navigation

    if str(getattr(request, "method", "POST") or "POST").upper() != "POST":
        logger.info(
            "Website-Uebergabe per %s abgewiesen (nur POST).",
            getattr(request, "method", "?"),
        )
        if request is not None and _ist_browser_navigation(request):
            # Ein Browser, der die Adresse als Seite aufruft, bekommt die
            # SPA statt rohem JSON — dieselbe Behandlung wie beim Login.
            from starlette.responses import RedirectResponse

            antwort = RedirectResponse("/", status_code=303)
            antwort.headers["Cache-Control"] = "no-store"
            return antwort
        throw(
            "Diese Adresse darf nur per POST aufgerufen werden.",
            FrappePermissionError,
        )

    rollen_liste = _require_website_rolle()
    if primo.primaere_primo_rolle(rollen_liste) is None:
        # Theoretisch unerreichbar: `darf_website` und die Zuordnung teilen
        # sich die Rollenliste. Fail closed statt stillschweigend "editor".
        throw(
            "Für dieses Konto ist in Primo keine Rolle hinterlegt.",
            FrappePermissionError,
        )

    benutzer = str(session.user or "").strip()
    email = _email_des_benutzers()
    try:
        # Synchroner Netz-/DB-Aufruf: in einem eigenen Thread, damit ein
        # langsamer Primo nicht den Worker blockiert.
        url = _im_thread(primo.login_uebergabe, benutzer, email, rollen_liste)
    except primo.PrimoKontoKonflikt as exc:
        # WEB-1b/B1: die Zuordnung ist nicht eindeutig — nichts wurde
        # geaendert. 409, damit die Oberflaeche "Verknuepfung noetig" zeigen
        # kann (ValidationError ist Frappes Standard fuer diesen Status).
        logger.info("Primo-Uebergabe: Zuordnungskonflikt.")
        throw(exc.meldung, KonfliktError)
    except primo.PrimoNichtKonfiguriert:
        # 503: die Anbindung ist nicht eingeschaltet — kein Fehler des
        # Benutzers, sondern eine fehlende Voraussetzung der Installation.
        throw(
            "Die Website-Anbindung (Primo) ist auf dieser Installation nicht eingerichtet.",
            DienstNichtVerfuegbarError,
        )
    except primo.PrimoAbgelehnt as exc:
        # Grund ohne Interna weitergeben: Statuscode + Kurztext von Primo.
        logger.warning("Primo-Uebergabe abgelehnt: HTTP %s", exc.status)
        throw(
            "Die Anmeldung an der Website ist gerade nicht möglich "
            "(Primo hat den Zugang abgelehnt).",
            DienstNichtVerfuegbarError,
        )
    except primo.PrimoNichtErreichbar:
        logger.warning("Primo-Uebergabe: Server nicht erreichbar.")
        throw(
            "Die Website ist gerade nicht erreichbar.",
            DienstNichtVerfuegbarError,
        )
    return {"url": url}
