"""BS-1b — HTTP-Rahmen der oeffentlichen Website-Ausgabe.

Vier Regeln gelten fuer JEDEN oeffentlichen Endpunkt (Kartenvorgabe G4) und
stehen deshalb EINMAL hier statt sechsmal im Endpunkt:

1. **Nur GET.** Leseendpunkte nehmen ausschliesslich GET (und HEAD) an; jede
   andere Methode endet mit 405 ``MethodNotAllowed`` und ``Allow: GET, HEAD``
   — nichts wird gelesen, nichts gezaehlt.
2. **CORS nur fuer die Herkunft aus ``PRIMO_PUBLIC_URL``** (und nur, wenn sie
   sich vom eigenen Host unterscheidet). Erlaubt sind GET (und der POST der
   Kontaktroute, siehe ``website/kontakt.py``); KEINE Credentials; die
   Antwort traegt ``Access-Control-Allow-Origin`` genau fuer diese eine
   Herkunft — nie ``*``. Eine fremde Herkunft bekommt den Kopf NICHT
   (der Browser blockt dann, das ist die Grenze).
3. **``Cache-Control: public, max-age=300``** plus ``Vary: Origin`` (sonst
   liefert ein Zwischenspeicher die Antwort MIT CORS-Kopf an einen Aufrufer
   ohne Berechtigung aus).
4. **Bremse** (``website/oeffentlich_bremse.py``): je Adresse 120/min. Greift
   sie, antwortet der Endpunkt 429 mit einer generischen deutschen Meldung
   (SEC-7: kein Interna).

Die Herkunftspruefung ist bewusst eine POSITIVLISTE: verglichen werden
Schema, Host und Port der Herkunft mit ``PRIMO_PUBLIC_URL``. Fehlt die
Einstellung (Website auf derselben Herkunft wie Diakronos), gibt es keinen
CORS-Kopf — das braucht auch niemand, weil gleiche Herkunft kein CORS ist.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import JSONResponse, Response

__all__ = [
    "CACHE_SEKUNDEN",
    "ERLAUBTE_METHODEN",
    "ORIGIN_HEADER",
    "cors_kopf",
    "erlaubte_herkunft",
    "fehler",
    "json_antwort",
    "methoden_abweisung",
    "primo_herkunft",
]

#: Erlaubte Methoden der Leseendpunkte.
ERLAUBTE_METHODEN = ("GET", "HEAD")
#: Cache-Dauer der oeffentlichen Antworten (Karte: „z. B. 300“).
CACHE_SEKUNDEN = 300
#: Kopfzeilen, die ein Zwischenspeicher beruecksichtigen MUSS.
ORIGIN_HEADER = "Vary"


def _normalisiert(url: str) -> tuple[str, str, int | None] | None:
    """``(schema, host, port)`` einer absoluten Adresse (``None``, wenn leer)."""
    roh = str(url or "").strip()
    if not roh:
        return None
    if "://" not in roh:
        roh = "//" + roh
    teile = urlsplit(roh)
    schema = (teile.scheme or "").lower()
    host = (teile.hostname or "").lower().strip(".")
    if not host:
        return None
    port = teile.port
    if port is None:
        port = 443 if schema == "https" else 80 if schema == "http" else None
    return schema, host, port


def primo_herkunft() -> str:
    """Die CORS-Herkunft aus ``PRIMO_PUBLIC_URL`` (ohne Schluss-``/``, sonst ``""``)."""
    from diakronos_app.settings import settings

    adresse = ""
    try:
        adresse = str(settings.primo_public_url_effektiv or "").strip()
    except Exception:  # noqa: BLE001 — eine kaputte Einstellung != 500
        adresse = str(getattr(settings, "primo_public_url", "") or "").strip()
    if not adresse:
        return ""
    teile = _normalisiert(adresse)
    if teile is None:
        return ""
    schema, host, port = teile
    standard = (schema == "https" and port == 443) or (schema == "http" and port == 80)
    return f"{schema}://{host}" if standard else f"{schema}://{host}:{port}"


def erlaubte_herkunft(request) -> str:
    """Die Herkunft dieser Anfrage, wenn sie zu ``PRIMO_PUBLIC_URL`` passt.

    ``""`` heisst: kein CORS. Verglichen wird die Herkunft (``Origin``) —
    NICHT ``Host``, weil der Proxy den ``Host`` der Diakronos-Domain setzt.
    ``Origin: null`` (Sandbox-iframe, ``file://``) ist nie eine Website.
    """
    erwartet = primo_herkunft()
    if not erwartet:
        return ""
    geliefert = str(request.headers.get("origin", "") or "").strip()
    if not geliefert or geliefert.lower() == "null":
        return ""
    if _normalisiert(geliefert) != _normalisiert(erwartet):
        return ""
    return erwartet


def cors_kopf(antwort: Response, request) -> Response:
    """Setzt die CORS-Kopfzeilen — nur fuer die Herkunft aus ``PRIMO_PUBLIC_URL``."""
    herkunft = erlaubte_herkunft(request)
    if not herkunft:
        return antwort
    antwort.headers["Access-Control-Allow-Origin"] = herkunft
    antwort.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
    antwort.headers["Access-Control-Max-Age"] = "600"
    # OHNE Credentials: die oeffentliche Ausgabe braucht keine Sitzung, und
    # `*` zusammen mit Credentials waere ohnehin verboten.
    return antwort


def json_antwort(
    daten,
    request=None,
    *,
    status: int = 200,
    cache: bool = True,
) -> Response:
    """JSON-Antwort mit Cache-/CORS-Kopfzeilen der oeffentlichen Ausgabe.

    Der Koerper ist der von ``json_antwort`` erzeugte Response — die
    Leseendpunkte geben ihn NUR dann zurueck, wenn eine Kopfzeile noetig ist.
    Im Normalfall geben sie die Daten ROH zurueck: der Methoden-Router
    verpackt sie in ``{"message": …}`` (Frappe-Envelope), wie bei jedem
    anderen Endpunkt der App.
    """
    antwort = JSONResponse(status_code=status, content={"message": daten})
    if cache:
        antwort.headers["Cache-Control"] = f"public, max-age={CACHE_SEKUNDEN}"
        antwort.headers[ORIGIN_HEADER] = "Origin"
    else:
        antwort.headers["Cache-Control"] = "no-store"
    if request is not None:
        cors_kopf(antwort, request)
    return antwort


def fehler(meldung: str, exc_type: str, status: int, request=None) -> Response:
    """Fehlerkoerper in Frappe-Form (``message``/``exception``/``exc_type``).

    Dieselbe Form wie ``frappe_compat.router._fehler_koerper`` — die
    Oberflaeche und die Tests kennen nur diese. Fehler werden NICHT
    zwischengespeichert (``no-store``): ein später freigegebener Kalender soll
    nicht 5 Minuten lang 404 bleiben.
    """
    # SEC-8: der Klassenname geht NUR nach Allowlist nach aussen
    # (CSRFTokenError/SessionExpired/PermissionError), alles andere als
    # generisches "Error". DIESELBE Funktion wie im Methoden-Router — sonst
    # gaebe es zwei Fehlervertraege, und der offenere gewaenne.
    from diakronos_app.frappe_compat.router import _fehler_koerper

    antwort = JSONResponse(
        status_code=status,
        content=_fehler_koerper(meldung, exc_type, status),
    )
    antwort.headers["Cache-Control"] = "no-store"
    if request is not None:
        cors_kopf(antwort, request)
    return antwort


def methoden_abweisung(request) -> Response | None:
    """``None``, wenn die Methode erlaubt ist — sonst die 405-Antwort.

    Ein Browser, der die Adresse als Seite aufruft (``GET`` ist erlaubt, das
    betrifft also nur POST/PUT/…), bekommt dieselbe JSON-Antwort wie ein
    Skript: es gibt hier keinen Formularweg, den eine Maske abfangen muesste.
    """
    methode = str(getattr(request, "method", "GET") or "GET").upper()
    if methode in ERLAUBTE_METHODEN:
        return None
    antwort = fehler(
        "Diese Adresse darf nur per GET aufgerufen werden.",
        "MethodNotAllowed",
        405,
        request,
    )
    antwort.headers["Allow"] = ", ".join(ERLAUBTE_METHODEN)
    return antwort


def optionen_antwort(request) -> Response:
    """Antwort auf ``OPTIONS`` (CORS-Vorabfrage) fuer die erlaubte Herkunft.

    Eine fremde Herkunft bekommt 403 — der Browser sendet den eigentlichen
    Aufruf dann nicht. Ohne CORS-Bedarf (keine ``PRIMO_PUBLIC_URL``) bleibt
    es bei 405: es gibt nichts vorabzufragen.
    """
    herkunft = erlaubte_herkunft(request)
    if not herkunft:
        antwort = fehler(
            "Diese Adresse darf nur per GET aufgerufen werden.",
            "MethodNotAllowed",
            405,
            request,
        )
        antwort.headers["Allow"] = ", ".join(ERLAUBTE_METHODEN)
        return antwort
    antwort = Response(status_code=204)
    antwort.headers["Access-Control-Allow-Origin"] = herkunft
    antwort.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
    antwort.headers["Access-Control-Max-Age"] = "600"
    antwort.headers[ORIGIN_HEADER] = "Origin"
    antwort.headers["Cache-Control"] = "no-store"
    return antwort
