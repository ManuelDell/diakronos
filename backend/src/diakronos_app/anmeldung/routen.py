"""Anmelde-Routen (SEC1): ``/login``, ``/auth/oidc/*``, ``/logout``.

Der EINE Login-Weg:

  * Ist OIDC aktiv, leitet ``/login`` automatisch zum Anbieter weiter
    (``/auth/oidc/start`` bzw. direkt). Das lokale Formular erscheint nur, wenn
    ``AUTH_LOCAL_LOGIN`` es erlaubt — dann als NOTZUGANG, mit dem Anbieter als
    Hauptweg.
  * ``/auth/oidc/callback`` verarbeitet die Rueckkehr: ``state`` pruefen (aus dem
    Transaktionsspeicher, Einmalverwendung), Code einloesen, ID-Token pruefen
    (Signatur/iss/aud/exp/nonce/azp), Konto zuordnen, Sitzung anlegen.
  * ``redirect-to`` wird nur als RELATIVER Pfad akzeptiert (kein Open Redirect).
  * Sitzungsfixierung: vor dem Anlegen der neuen Sitzung wird eine alte
    ``sid`` geloescht.
  * ``/logout`` ist NUR POST und NICHT von der CSRF-Pruefung ausgenommen:
    ohne das koennte eine fremde Seite die Sitzung per eingebettetem
    Bild/Formular beenden (Forced Logout). Es gibt daneben weiterhin den
    Frappe-kompatiblen, CSRF-geschuetzten ``/api/method/logout``.

Diese Routen sind eine eigene ASGI-Ebene (Register via `registriere_routen`),
weil sie keinen Frappe-Envelope brauchen und teils HTML/Redirect liefern.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import quote, unquote, urlencode

from fastapi import FastAPI, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from diakronos_app.anmeldung import konfiguration as konf
from diakronos_app.anmeldung import oidc, transaktionen
from diakronos_app.anmeldung.zuordnung import (
    ExternesKonto,
    loese_konto_auf,
    merke_ablehnung_separat,
)

logger = logging.getLogger("diakronos_app.anmeldung.routen")

__all__ = ["registriere_routen", "SPA_ZIEL", "LOKALES_LOGIN_ERLAUBT"]

# Ziel nach erfolgreicher Anmeldung (SPA-Startseite).
SPA_ZIEL = "/diakonos"

# Pfade, die ein Forward-Auth-Proxy AUSSCHLIESSEN muss (TEIL C). Hier nur als
# Konstante dokumentiert; die Durchsetzung ist eine Proxy-Konfiguration.
FORWARD_AUTH_AUSNAHMEN = (
    "/healthz",
    "/dav/",
    "/.well-known/caldav",
    "/google-calendar-callback",
    "/auth/oidc/",
    "/login",
    "/logout",
)


def _relatives_ziel(kandidat: str | None) -> str:
    """Nur pfadrelative Ziele zulassen (Open-Redirect verhindern).

    Dieselbe Strenge wie `api/auth.py::_redirect_ziel`: führende ``/`` ja,
    ``//`` (protokollrelativ) und Backslashes nein, Steuerzeichen gefiltert.
    """
    ziel = unquote(str(kandidat or "")).strip()
    if not ziel.startswith("/") or ziel.startswith("//"):
        return SPA_ZIEL
    if "\\" in ziel:
        return SPA_ZIEL
    if any(ord(c) < 0x20 or c in "\x7f\x85\u2028\u2029" for c in ziel):
        return SPA_ZIEL
    return ziel


def _lokales_login_erlaubt() -> bool:
    """True, wenn das lokale Formular ueberhaupt erreichbar sein darf.

    Ausgewertet wird erst im Kontext eines Requests (der Knopf/Nologin haengt
    an der Konfiguration). Bei ausgeschaltetem OIDC ist der lokale Login immer
    erlaubt — Bestandsschutz.
    """
    cfg = konf.oidc_konfiguration()
    if not konf.oidc_aktiv():
        return True
    return cfg.local_login in ("an", "nur-admin")


LOKALES_LOGIN_ERLAUBT = _lokales_login_erlaubt


def _anbieter_knopf_html() -> str:
    """HTML-Knopf „Mit <Anbietername> anmelden" (Hauptweg)."""
    import html

    cfg = konf.oidc_konfiguration()
    name = html.escape(cfg.anbietername or "Anbieter", quote=True)
    return (
        '<a class="dk-sso" href="/login?sso=1">'
        f"Mit {name} anmelden</a>"
    )


def _hash_bruecke_seite(ziel: str) -> str:
    """Zwischenseite vor dem OIDC-Redirect — rettet den Deeplink-Hash.

    OP-CHOR-4/P0-4b: Browser senden `location.hash` NIE an den Server. Ist
    OIDC aktiv, leitet `/login` sofort serverseitig zum Anbieter weiter — das
    Hash-Skript der Anmeldemaske laeuft also nie, und `#/planrahmen/plan/…`
    ging beim Anbieter-Roundtrip verloren (das Mitglied landete auf dem
    Dashboard).

    Diese Seite laeuft VOR der Weiterleitung im Browser: sie legt den Hash in
    `sessionStorage` ab und geht dann auf `/login?sso=1&redirect-to=<ziel>` —
    ab da uebernimmt der Server (OIDC-Start mit `ziel`). Nach der Rueckkehr
    stellt `_hash_wiederherstellen_seite` den Hash wieder her.

    `sessionStorage` und nicht `localStorage`: der Merker gehoert zu DIESEM
    Anmeldevorgang, nicht zu einem geteilten Geraet. Ein Schluessel, der einen
    Plan-Deeplink eines anderen Nutzers haelt, bliebe sonst liegen.
    """
    # `json.dumps` escaped fuer ein JS-Literal; `<` wird zusaetzlich als
    # `\u003c` geschrieben, damit ein `</script>` im Ziel das Tag nicht
    # schliesst (derselbe Schutz wie `spa._boot_json`).
    import html
    from urllib.parse import quote
    noscript_ziel = html.escape('/login?sso=1&redirect-to=' + quote(_relatives_ziel(ziel), safe=''), quote=True)
    ziel_js = json.dumps(ziel).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anmelden</title></head>
<body>
<p>Weiterleitung zur Anmeldung …</p>
<noscript><p><a href="{noscript_ziel}">Weiter zur Anmeldung</a> (ohne JavaScript wird die Unterseite nicht automatisch wiederhergestellt).</p></noscript>
<script>
    (function () {{
        var ziel = {ziel_js};
        try {{
            // Nur der Hash (ab '#') wird gemerkt — nie der volle Pfad.
            var hash = window.location.hash || '';
            if (hash) {{ sessionStorage.setItem('dk-login-hash', hash); }}
        }} catch (e) {{ /* kein Speicher -> Anmeldung laeuft ohne Hash */ }}
        try {{
            window.location.replace('/login?sso=1&redirect-to=' + encodeURIComponent(ziel));
        }} catch (e) {{
            window.location.href = '/login?sso=1&redirect-to=' + encodeURIComponent(ziel);
        }}
    }})();
</script>
</body>
</html>"""


def _hash_wiederherstellen_seite(ziel: str) -> str:
    """Zwischenseite nach dem OIDC-Roundtrip — setzt den Hash wieder an.

    Liest den in `_hash_bruecke_seite` gemerkten Hash und leitet auf
    `ziel + hash` weiter. Der Server kennt den Hash nie; er wird erst hier im
    Browser wieder angehaengt. `ziel` kommt aus der serverseitigen
    Transaktion und ist bereits als relativer Pfad geprueft.
    """
    # Wie in `_hash_bruecke_seite`: JS-Literal, `<`/`>` als Unicode-Escape.
    ziel_js = json.dumps(ziel).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anmeldung abgeschlossen</title></head>
<body>
<p>Anmeldung abgeschlossen — weiter …</p>
<script>
    (function () {{
        var ziel = {ziel_js};
        var hash = '';
        try {{
            hash = sessionStorage.getItem('dk-login-hash') || '';
            sessionStorage.removeItem('dk-login-hash');
        }} catch (e) {{ /* kein Speicher -> ohne Hash weiter */ }}
        // Nur ein sauberes Fragment anhaengen: beginnt mit '#' und traegt
        // keine Steuerzeichen (der Wert stammt aus dem Browser, nicht vom
        // Server — trotzdem wird er geprueft, bevor er in die URL geht).
        if (hash.charAt(0) !== '#' || /[\\u0000-\\u001f]/.test(hash)) {{ hash = ''; }}
        window.location.replace(ziel + hash);
    }})();
</script>
</body>
</html>"""


def _cookies_aus_request(request) -> object:
    """Cookie-Jar des Requests (oder ein leerer Ersatz).

    Der Request wird durchgereicht statt aus einem KontextVar geholt:
    `render_login` laeuft auch fuer die ALTpfad-Routen und in Tests ohne
    Request-Kontext; dort ist schlicht kein Flash da.
    """
    return getattr(request, "cookies", None) or {}


def erstelle_anmeldeseite(
    next_url: str = SPA_ZIEL,
    *,
    meldung: str = "",
    email: str = "",
    request=None,
) -> str:
    """Anmeldeseite: Anbieter-Knopf (Hauptweg) + optionales lokales Formular.

    Baut auf der bestehenden Optik von `spa.render_login` auf, ergaenzt aber den
    OIDC-Weg. Das lokale Formular wird nur gezeigt, wenn erlaubt.

    LOGIN-1: `meldung` (role="alert", ueber dem Formular) und `email`
    (vorausgefuellt) stammen aus dem Flash-Cookie der fehlgeschlagenen
    Formular-Anmeldung — gesetzt in `api/auth.py::login_formular_fehler`,
    gelesen und geloescht in `login_route`.
    """
    import html

    from diakronos_app.spa import DEFAULT_CHURCH_NAME, _settings_zeile

    oidc_an = konf.oidc_aktiv()
    lokal = _lokales_login_erlaubt()
    # LOGIN-1: Meldung/Email auch dann anzeigen, wenn das lokale Formular
    # gerade nicht erlaubt ist — sonst verschwaende der Grund des Fehlschlags
    # still (der Nutzer saehe nur "Anmeldung nicht verfuegbar").
    _flash_meldung = ""
    _flash_email = ""
    if lokal:
        from diakronos_app.anmeldung import flash

        _gelesen = flash.lese_flash(_cookies_aus_request(request))
        if _gelesen is not None:
            _flash_email, _leer = _gelesen
            _flash_meldung = flash.MELDUNG_LEER if _leer else flash.MELDUNG_FALSCH
    gemeinde = html.escape(
        _settings_zeile().get("organisationsname") or DEFAULT_CHURCH_NAME, quote=True
    )
    ziel_kodiert = html.escape(quote(next_url, safe=""), quote=True)
    # Die aus dem Flash gelesenen Werte GEWINNEN gegen die Parameter: die
    # Parameter existieren nur fuer direkte Aufrufe (Tests, Vorschau).
    meldung = _flash_meldung or meldung
    email = _flash_email or email
    meldung_html = html.escape(meldung, quote=True)
    email_html = html.escape(email, quote=True)
    meldung_block = (
        f'\n        <p class="dk-meldung" role="alert">{meldung_html}</p>' if meldung else ""
    )

    sso_block = ""
    if oidc_an:
        sso_block = _anbieter_knopf_html()

    # LOGIN-3/N-3: Hier stand ein `hinweis_block` fuer den Fall „lokaler Login
    # aus UND kein Anbieter eingerichtet". Diesen Zustand gibt es nicht:
    # `_lokales_login_erlaubt()` liefert ohne OIDC immer True (Bestandsschutz),
    # und bei aktivem OIDC ist `lokal` nur dann False, wenn der Anbieter da
    # ist. Die Bedingung war nie wahr, der Block also toter Code — entfernt,
    # statt eine Meldung fuer einen unerreichbaren Zustand zu rendern.

    formular_block = ""
    if lokal:
        # Bei aktivem OIDC ist das Formular der Notzugang (klein, unter dem Knopf).
        # LOGIN-2/K: Der Fokus gehoert nach einem Fehlschlag ins PASSWORTFELD —
        # die E-Mail steht ja schon drin, der naechste Griff ist das Passwort.
        formular_block = f"""
        <form method="post" action="/api/method/login" accept-charset="utf-8">
            <input type="hidden" name="redirect-to" value="{ziel_kodiert}">
            <label for="dk-usr">E-Mail oder Benutzername</label>
            <input id="dk-usr" name="usr" type="text" autocomplete="username"
                   autocapitalize="none" autocorrect="off" spellcheck="false" required
                   value="{email_html}">
            <label for="dk-pwd">Passwort</label>
            <input id="dk-pwd" name="pwd" type="password"
                   autocomplete="current-password" required{" autofocus" if meldung else ""}>
            <button type="submit" class="dk-sekundaer">Mit Passwort anmelden</button>
        </form>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anmelden — {gemeinde}</title>
    <style>
        :root {{ color-scheme: light dark; }}
        body {{ margin: 0; min-height: 100vh; display: flex; align-items: center;
            justify-content: center; padding: 1.5rem;
            font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
            background: #f5f6f8; color: #1f2430; }}
        .dk-login {{ width: 100%; max-width: 24rem; background: #fff; padding: 2rem;
            border-radius: .75rem; box-shadow: 0 1px 3px rgba(16,24,40,.1),
            0 12px 32px rgba(16,24,40,.08); }}
        .dk-login h1 {{ margin: 0 0 .25rem; font-size: 1.25rem; font-weight: 600; }}
        .dk-login p.sub {{ margin: 0 0 1.5rem; color: #5b6474; font-size: .875rem; }}
        label {{ display: block; font-size: .8125rem; font-weight: 500; margin-bottom: .375rem; }}
        input {{ width: 100%; box-sizing: border-box; padding: .625rem .75rem; margin-bottom: 1rem;
            font-size: .9375rem; font-family: inherit; color: inherit; background: #fff;
            border: 1px solid #d3d8e0; border-radius: .5rem; }}
        button, a.dk-sso {{ display: block; width: 100%; box-sizing: border-box;
            padding: .6875rem 1rem; font-size: .9375rem; font-weight: 600;
            font-family: inherit; text-align: center; text-decoration: none;
            border: 0; border-radius: .5rem; }}
        button {{ color: #fff; background: #2f5d8a; cursor: pointer; }}
        button.dk-sekundaer {{ color: #2f5d8a; background: #eef3f8; }}
        a.dk-sso {{ color: #fff; background: #2f5d8a; margin-bottom: 1rem; }}
        a.dk-sso:hover, button:hover {{ filter: brightness(.95); }}
        .hinweis {{ margin: 1rem 0 0; font-size: .75rem; color: #5b6474; }}
        /* LOGIN-1: Meldung der fehlgeschlagenen Anmeldung — gleiche Optik wie
           in `spa.render_login`, `role="alert"` steht im Markup. */
        .dk-meldung {{ margin: 0 0 1rem; padding: .625rem .75rem; font-size: .875rem;
            color: #8a1f1f; background: #fdecec; border: 1px solid #f3c7c7;
            border-left: 3px solid #b03030; border-radius: .5rem; }}
        /* LOGIN-2/S1: erklaert, warum kein Passwortformular da ist. */
        /* LOGIN-3/N-3: die Regel fuer den entfallenen Hinweisblock ist weg
           (der Block war toter Code, Bedingung nie erreichbar). */
        /* OP-HANDY-14: iOS-Safari zoomt beim Antippen in Felder unter 16 px
           (hier 15 px). Im groben Zeiger deshalb 16 px — dieselbe Regel wie im
           SPA-Stylesheet und in spa.py. */
        @media (hover: none) and (pointer: coarse) {{
            input, select, textarea {{ font-size: 16px; }}
        }}
    </style>
</head>
<body>
    <main class="dk-login">
        <h1>{gemeinde}</h1>
        <p class="sub">Bitte melde dich an, um fortzufahren.</p>{meldung_block}
        {sso_block}
        {formular_block}
        <p class="hinweis">Anmeldelinks fuer Registrierung und Gastzugriff
            findest du in der Nachricht der Gemeindeleitung.</p>
    </main>
    <script>
        // OP-CHOR-4: Der Hash erreicht den Server NIE (Browser senden ihn
        // nicht mit). Ein geteilter Deeplink `#/planrahmen/plan/…` ging
        // dadurch bei der Anmeldung verloren — das Mitglied landete auf dem
        // Dashboard. Hier wird der aktuelle Hash an das Feld `redirect-to`
        // angehaengt; `_redirect_ziel` (auth.py) laesst ein Fragment zu und
        // weist fremde Ziele weiterhin ab.
        try {{
            var hash = window.location.hash || '';
            var feld = document.querySelector('input[name="redirect-to"]');
            if (hash && feld) {{
                var ziel = decodeURIComponent(feld.value || '');
                if (ziel.indexOf('#') === -1) {{
                    feld.value = encodeURIComponent(ziel + hash);
                }}
            }}
        }} catch (e) {{ /* Formular bleibt ohne Hash nutzbar */ }}
    </script>
</body>
</html>
"""


def _neue_sitzung_nach_login(request: Request, user: str) -> tuple[str, str]:
    """Sitzungsfixierung vermeiden: alte ``sid`` loeschen, neue anlegen."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers

    alt = sid_aus_headers(request.headers)
    if alt:
        sitzungen.loeschen(alt)
    return sitzungen.anlegen(user, sso=True)


def _sitzungscookie(response: Response, sid: str) -> None:
    """Setzt das ``sid``-Cookie in derselben Form wie der lokale Login."""
    from diakronos_app.api.auth import _secure_flag
    from diakronos_app.settings import settings

    response.set_cookie(
        key="sid",
        value=sid,
        httponly=True,
        samesite="lax",
        path="/",
        secure=_secure_flag(),
        max_age=int(settings.session_ttl_seconds),
    )


def _start_weiterleitung(request: Request, ziel: str | None = None) -> Response:
    """Leitet zum Anbieter weiter und merkt state/nonce/verifier serverseitig.

    ``ziel`` (OP-CHOR-4/P0-4b): das Weiterleitungsziel nach der Rueckkehr.
    Wird zusammen mit der Transaktion gespeichert, damit der Deeplink einen
    OIDC-Roundtrip uebersteht — vorher landete jedes Mitglied nach der
    Anmeldung auf dem Dashboard, egal welchen Plan-Link es geteilt bekam.
    """
    cfg = konf.oidc_konfiguration()
    meta = oidc.hole_metadaten(cfg)
    autorisiert = oidc.autorisierungs_url(cfg, meta)
    transaktionen.ablegen(
        autorisiert.state, autorisiert.nonce, autorisiert.code_verifier, ziel
    )
    return RedirectResponse(autorisiert.url, status_code=303)


def _fehler_seite(meldung: str, status: int = 403) -> Response:
    """Einfache Fehlerseite fuer abgelehnte Anmeldungen (deutsch, ohne Details)."""
    import html

    text = html.escape(meldung, quote=True)
    seite = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anmeldung nicht moeglich</title>
<style>body{{font-family:Inter,system-ui,sans-serif;background:#f5f6f8;color:#1f2430;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:1.5rem}}
main{{max-width:28rem;background:#fff;padding:2rem;border-radius:.75rem;
box-shadow:0 1px 3px rgba(16,24,40,.1)}}a{{color:#2f5d8a}}</style></head>
<body><main><h1 style="font-size:1.15rem">Anmeldung nicht moeglich</h1>
<p>{text}</p><p><a href="/login">Erneut versuchen</a></p></main></body></html>"""
    return HTMLResponse(seite, status_code=status)


def registriere_routen(app: FastAPI) -> None:
    """Registriert die Anmelde-Routen. MUSS vor `mount_spa(app)` laufen."""

    @app.get("/login", include_in_schema=False)
    def login_route(request: Request) -> Response:
        # LOGIN-1: `noredirect=1` ist der Rueckkehrpunkt einer fehlgeschlagenen
        # Formular-Anmeldung (`api/auth.py::login_formular_fehler`). Hier wird
        # IMMER die lokale Maske MIT Meldung ausgeliefert — auch bei aktivem
        # OIDC. Grund: der Mensch hat gerade das Passwortfeld ausgefuellt; ihn
        # wortlos zum Anbieter zu schicken, waere ein Sprung ohne Erklaerung.
        # Der Parameter kommt ausschliesslich vom Server, ist aber harmlos,
        # wenn ihn jemand selbst setzt (dann sieht er die Maske).
        no_redirect = request.query_params.get("noredirect") == "1"
        ziel = _relatives_ziel(request.query_params.get("redirect-to"))
        # LOGIN-1: Das `#Fragment` des Ziels reist als ABFRAGE-Parameter
        # (`frag=`), weil Browser Fragmente nie an den Server schicken. Es wird
        # hier an das Ziel angehaengt, damit die Maske es wieder in ihr
        # `redirect-to`-Feld uebernimmt (das Skript unten tat das schon fuer den
        # eigenen `location.hash`; ohne JavaScript bleibt es so wenigstens im
        # Feld erhalten).
        frag = unquote(str(request.query_params.get("frag") or "")).strip()
        if frag and not any(ord(c) < 0x20 for c in frag):
            ziel = f"{ziel}#{frag}" if "#" not in ziel else ziel
        if konf.oidc_aktiv() and not no_redirect:
            # Ist OIDC aktiv, ist der Anbieter der Hauptweg. Ohne ``sso=0`` wird
            # direkt weitergeleitet — der Nutzer merkt nur EINEN Login.
            # OP-CHOR-4: das Ziel (inkl. spaeter ergaenztem Hash) wird MIT
            # uebergeben, sonst ginge der Deeplink beim OIDC-Roundtrip verloren.
            #
            # WICHTIG: Der Hash kommt NIE beim Server an. Beim ERSTEN Aufruf
            # (Browser, kein sso/lokal) wird deshalb eine Zwischenseite
            # ausgeliefert, die ihn in `sessionStorage` merkt und erst dann
            # `/login?sso=1&redirect-to=…` aufruft. Erst dieser zweite Aufruf
            # leitet serverseitig zum Anbieter weiter.
            if request.query_params.get("sso") != "0" and not request.query_params.get(
                "lokal"
            ):
                if request.query_params.get("sso") != "1":
                    return HTMLResponse(_hash_bruecke_seite(ziel))
                return _start_weiterleitung(request, ziel)
        if not _lokales_login_erlaubt() and not no_redirect:
            # Kein lokaler Login erlaubt und OIDC aus -> Zugang nur ueber Anbieter.
            return _fehler_seite(
                "Die Anmeldung ist derzeit nicht verfuegbar. Bitte wende dich an die "
                "Gemeindeleitung.",
                status=503,
            )
        # LOGIN-1: Meldung der fehlgeschlagenen Anmeldung anzeigen und den
        # Flash dabei VERBRAUCHEN (Einmal-Gebrauch) — sonst stuende die alte
        # Meldung nach jedem Neuladen weiter da.
        from diakronos_app.anmeldung import flash

        antwort: Response = HTMLResponse(erstelle_anmeldeseite(ziel, request=request))
        flash.loesche_flash(antwort)
        return antwort

    @app.get("/auth/oidc/start", include_in_schema=False)
    def oidc_start(request: Request) -> Response:
        if not konf.oidc_aktiv():
            return _fehler_seite("OIDC ist nicht aktiviert.", status=404)
        return _start_weiterleitung(request)

    @app.get("/auth/oidc/callback", include_in_schema=False)
    def oidc_callback(request: Request) -> Response:
        if not konf.oidc_aktiv():
            return _fehler_seite("OIDC ist nicht aktiviert.", status=404)

        fehler = request.query_params.get("error")
        if fehler:
            # Anbieter-Fehlertext NICHT spiegeln.
            return _fehler_seite("Die Anmeldung wurde abgebrochen oder abgelehnt.")

        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if not state or not code:
            return _fehler_seite("Ungueltige Rueckkehr vom Anbieter.", status=400)

        tx = transaktionen.entnehmen(state)
        if tx is None:
            # Unbekannter/abgelaufener/zweimal benutzter state -> CSRF-Schutz.
            return _fehler_seite("Die Anmeldung ist abgelaufen. Bitte erneut anmelden.",
                                 status=400)

        cfg = konf.oidc_konfiguration()
        meta = oidc.hole_metadaten(cfg)
        try:
            token = oidc.hole_token(
                cfg, meta, code=code, code_verifier=str(tx.get("code_verifier") or "")
            )
            id_token = str(token.get("id_token") or "")
            claims = oidc.pruefe_id_token(
                cfg, meta, id_token, nonce=str(tx.get("nonce") or "")
            )
        except oidc.OidcFehler as exc:
            logger.warning("OIDC-Anmeldung fehlgeschlagen: %s", exc)
            return _fehler_seite("Die Anmeldung konnte nicht geprueft werden.")

        konto = _konto_aus_claims(meta.issuer, claims)
        return _schliesse_login_ab(request, konto, ziel=tx.get("ziel"))

    # `/logout` NUR als POST: ein GET-Logout ist per eingebettetem Bild
    # (`<img src="/logout">`) von jeder fremden Seite aus ausloesbar und
    # beendet die Sitzung des angemeldeten Nutzers (Forced Logout). POST
    # laeuft durch die CSRF-Pruefung und verlangt den `X-Frappe-CSRF-Token`.
    @app.post("/logout", include_in_schema=False)
    def logout_post_route(request: Request) -> Response:
        # W3: Die SPA ruft mit `Accept: application/json` auf und kann einer
        # 303-Antwort im `fetch` NICHT folgen (der Browser liefert bei
        # `redirect: 'manual'` eine undurchsichtige `opaqueredirect`-Antwort
        # ohne lesbaren `Location`-Header). Deshalb liefert der Endpunkt fuer
        # JSON-Aufrufer den Zielpfad im Koerper — die SPA setzt ihn dann selbst
        # per `window.location`. Ein Formular/Browser-POST (kein JSON-Accept)
        # bekommt weiterhin die 303-Weiterleitung.
        als_json = "application/json" in (request.headers.get("accept") or "")
        return _abmelden(request, redirect=not als_json)


def _konto_aus_claims(issuer: str, claims: dict) -> ExternesKonto:
    """Baut ein `ExternesKonto` aus den verifizierten Claims."""
    email = str(claims.get("email") or "").strip()
    verifiziert = claims.get("email_verified") is True
    gruppen_roh = claims.get("groups") or claims.get("group") or []
    if isinstance(gruppen_roh, str):
        gruppen = tuple(g.strip() for g in gruppen_roh.split(",") if g.strip())
    elif isinstance(gruppen_roh, (list, tuple)):
        gruppen = tuple(str(g).strip() for g in gruppen_roh if str(g).strip())
    else:
        gruppen = ()
    return ExternesKonto(
        issuer=issuer,
        sub=str(claims.get("sub") or "").strip(),
        email=email,
        email_verified=verifiziert,
        name=str(
            claims.get("name") or claims.get("preferred_username") or email or ""
        ).strip(),
        gruppen=gruppen,
        quelle="oidc",
    )


def _schliesse_login_ab(
    request: Request, konto: ExternesKonto, ziel: str | None = None
) -> Response:
    """Gemeinsamer Abschluss fuer OIDC und Forward-Auth: zuordnen + Sitzung.

    ``ziel`` (OP-CHOR-4/P0-4b): das in der Transaktion gespeicherte
    Weiterleitungsziel. Es wird NOCH EINMAL durch `_relatives_ziel` gefuehrt,
    obwohl es beim Ablegen schon geprueft wurde: der Wert geht hier in einen
    `Location`-Header, und diese eine Stelle darf sich nicht darauf verlassen,
    dass ein frueherer Aufrufer sauber war (dieselbe Lehre wie bei
    `_redirect_ziel`, auth.py).
    """
    from diakronos_app.db import SessionLocal

    if not konto.sub:
        return _fehler_seite("Der Anbieter hat keine stabile Kennung geliefert.", 400)

    sess = SessionLocal()
    try:
        ergebnis = loese_konto_auf(sess, konto)
        if not ergebnis.erlaubt:
            sess.rollback()
            # R-N8 (Punkt 2): die abgelehnte E-Mail-Zuordnung fuer die
            # Verwaltung festhalten — in EIGENER Transaktion, sonst wuerde der
            # soeben ausgefuehrte rollback sie wieder verwerfen.
            merke_ablehnung_separat(konto, ergebnis)
            return _fehler_seite(ergebnis.meldung or "Anmeldung abgelehnt.")
        sess.commit()
        user = ergebnis.user
    except Exception as exc:  # noqa: BLE001 — Zuordnung darf nie roh durchschlagen
        sess.rollback()
        logger.exception("Konto-Zuordnung fehlgeschlagen: %s", exc.__class__.__name__)
        return _fehler_seite("Die Anmeldung konnte nicht abgeschlossen werden.", 500)
    finally:
        sess.close()

    # OP-ADMIN-3: Ein im Modus „Als Gast anlegen" erzeugtes Konto ist bis zur
    # Freischaltung INAKTIV (`enabled=False`). Frueher wurde ihm trotzdem eine
    # Sitzung ausgestellt — die `SessionMiddleware` verwarf sie beim naechsten
    # Aufruf sofort, und die Meldung „wartet auf Freischaltung" sah niemand
    # (der Benutzer landete wortlos wieder auf der Anmeldeseite bzw. beim
    # naechsten Anbieter-Login auf „Dieses Konto ist gesperrt"). Jetzt wird
    # KEINE Sitzung ausgestellt und die Meldung des Zuordnungsergebnisses
    # gezeigt — der Benutzer weiss, woran er ist.
    if ergebnis.als_gast:
        from diakronos_app.frappe_compat import benutzer_status

        # Der Cache darf hier nicht greifen: direkt nach dem Anlegen steht die
        # Wahrheit in der DB, und genau sie soll gelten.
        benutzer_status.vergiss(str(user))
        if not benutzer_status.ist_aktiv(str(user)):
            meldung = ergebnis.meldung or (
                "Dein Konto wurde angelegt und wartet auf Freischaltung. "
                "Bitte wende dich an die Gemeindeleitung."
            )
            return _fehler_seite(meldung, 403)

    sid, _csrf = _neue_sitzung_nach_login(request, str(user))
    # OP-CHOR-4: das gespeicherte Ziel hat Vorrang vor dem Standardpfad.
    # Der Hash wurde im Browser gemerkt — kann also hier nicht angehaengt
    # werden. Deshalb geht es ueber die Wiederherstellungsseite, die den Hash
    # anhaengt und DANN auf das Ziel springt.
    if ziel:
        response = HTMLResponse(_hash_wiederherstellen_seite(_relatives_ziel(ziel)))
    else:
        response = RedirectResponse(SPA_ZIEL, status_code=303)
    _sitzungscookie(response, sid)
    logger.info("Anmeldung ueber Anbieter erfolgreich (Benutzer siehe Audit-Log).")
    return response


def beende_lokale_sitzung(request: Request) -> None:
    """Loescht die Diakronos-Sitzung des laufenden Requests (fuer Logout)."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers

    sid = sid_aus_headers(request.headers)
    if sid:
        sitzungen.loeschen(sid)


def _abmelden(request: Request, *, redirect: bool) -> Response:
    """Diakronos-Sitzung beenden + optional RP-Logout beim Anbieter.

    Der RP-initiated Logout nutzt ``end_session_endpoint`` mit
    ``id_token_hint``. Da wir das ID-Token nicht speichern, wird der Aufruf
    OHNE ``id_token_hint`` gebaut — Authentik beendet die Sitzung dann anhand
    der aktiven Sitzung; die ``post_logout_redirect_uri`` zeigt zurueck.
    """
    beende_lokale_sitzung(request)

    cfg = konf.oidc_konfiguration()
    ziel = SPA_ZIEL
    if konf.oidc_aktiv() and cfg.logout:
        try:
            meta = oidc.hole_metadaten(cfg)
            if meta.end_session_endpoint:
                parameter = {"client_id": cfg.client_id}
                if cfg.redirect_url:
                    # Basis der Redirect-URL als Rueckkehr nach dem Logout.
                    from urllib.parse import urlsplit

                    teile = urlsplit(cfg.redirect_url)
                    parameter["post_logout_redirect_uri"] = (
                        f"{teile.scheme}://{teile.netloc}{SPA_ZIEL}"
                    )
                trenner = "&" if "?" in meta.end_session_endpoint else "?"
                ziel = meta.end_session_endpoint + trenner + urlencode(parameter)
        except oidc.OidcFehler:
            ziel = SPA_ZIEL

    if redirect:
        response: Response = RedirectResponse(ziel, status_code=303)
    else:
        from starlette.responses import JSONResponse

        # W3: `redirect` ist der Zielpfad, den die SPA mit `window.location`
        # ansteuert (`/login` lokal oder der RP-Logout des Anbieters). `ziel`
        # heisst hier so, wie der Server seinen eigenen Rueckweg nennt.
        response = JSONResponse({"message": "Logged Out", "redirect": ziel})

    from diakronos_app.api.auth import _loesche_cookie

    _loesche_cookie(response)
    return response
