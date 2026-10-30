"""SEC-4 — Sicherheits-Kopfzeilen auf jeder Antwort.

Befund (Pentest dev.ecg-hn.de, Bericht Punkt 2): Antworten — auch `/api/*` —
trugen kein HSTS, keine CSP, kein X-Frame-Options, kein
X-Content-Type-Options und keine Referrer-Policy. Die vorhandenen Stellen
(`files.py`, `formularbilder_api.py`, `anmeldung/passwortseite.py`,
`google_callback.py`) setzen einzelne Kopfzeilen jeweils fuer ihren eigenen
Endpunkt — deshalb fehlten sie ueberall sonst.

Hier steht die eine Stelle, die es fuer ALLE Antworten nachholt. Warum
`BaseHTTPMiddleware` als AEUSSERSTE Schicht (`main.py` fuegt sie zuletzt
hinzu): so laeuft sie auch fuer Antworten, die eine innere Schicht kurz
abschliesst (CSRF 417, Anmeldung 401, Fehlerseiten) — ein Dekorator am
Endpunkt wuerde genau diese Faelle verpassen.

Warum „nur setzen, wenn noch nicht da“ und nicht „immer ueberschreiben“:
einige Endpunkte setzen bewusst eine ENGERE Policy als die pauschale.
`formularbilder_api.py` liefert Bilder mit `default-src 'none'; sandbox`;
diese Regel ist strenger als die App-Policy und darf nicht aufgeweicht
werden. Wo eine Kopfzeile schon steht, bleibt sie stehen.

Die App-Policy ist bewusst ohne `'unsafe-eval'`: die SPA (Vue 3, Vite-Build)
und die Anmeldemaske brauchen keinen `eval`. `'unsafe-inline'` bleibt fuer
Skripte und Stile, weil die ausgelieferte `index.html` ein Inline-Skript (das
Boot-Objekt `__DIakonosBOOT`) und die Anmeldemaske ein Inline-`<style>` und
ein Inline-Skript traegt. Nachziehen, wenn dort ein Nonce-Hash eingefuehrt
wird.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

#: HSTS: ein Jahr, Unterdomains. Gesetzt auch auf HTTP-Antworten — der Header
#: wirkt nur ueber TLS, und hinter dem nginx (Karte SEC-4) sieht die App das
#: Originalschema nicht zuverlaessig. Ein `includeSubDomains` verpflichtet
#: ALLE Unterdomains der Gemeinde auf HTTPS; das ist gewollt (dev/prod laufen
#: ohnehin nur ueber TLS) und steht so in der BETRIEBSANLEITUNG.
HSTS = "max-age=31536000; includeSubDomains"

#: App-Policy fuer API und SPA. `frame-ancestors 'none'` ist der moderne
#: Ersatz fuer X-Frame-Options (Clickjacking); `X-Frame-Options: DENY` steht
#: zusaetzlich fuer Browser, die nur den kennen.
#:
#: `default-src 'none'` heisst: alles, was nicht ausdruecklich erlaubt ist,
#: ist verboten. Erlaubt sind nur die Dinge, die die SPA nachweislich braucht:
#: eigene Skripte/Stile (Buendel unter /diakonos/assets), Bilder/Schriften
#: von der eigenen Adresse und `data:`/`blob:` (Vorschau hochgeladener
#: Anmeldeformular-Bilder laeuft ueber `blob:`), Fetch/XHR und Socket.IO auf
#: die eigene Adresse (`connect-src 'self'`), Formulare zurueck an die eigene
#: Adresse (Anmeldemaske POST /api/method/login).
APP_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "manifest-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

#: Reihenfolge = Setzreihenfolge. Die CSP steht vor den alten Kopfzeilen,
#: damit eine vorhandene, engere Policy unangetastet bleibt.
KOPFZEILEN = (
    ("Strict-Transport-Security", HSTS),
    ("Content-Security-Policy", APP_CSP),
    ("X-Frame-Options", "DENY"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
)


def sicherheits_header_setzen(antwort) -> None:
    """Setzt die Kopfzeilen auf einer Antwort — nur, wo noch keine steht.

    `antwort` braucht nur ein `.headers`-Objekt (Starlette `Response`,
    Testdoppel). Damit ist die Funktion auch ohne Request pruefbar.
    """
    kopf = antwort.headers
    for name, wert in KOPFZEILEN:
        if name not in kopf:
            kopf[name] = wert


class SicherheitsHeaderMiddleware(BaseHTTPMiddleware):
    """Legt die Kopfzeilen nach JEDER Antwort an — auch an Fehlerantworten."""

    async def dispatch(self, request: Request, call_next):
        antwort = await call_next(request)
        sicherheits_header_setzen(antwort)
        return antwort
