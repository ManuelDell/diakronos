"""WEB-5a — EIN Praefix fuer den ganzen Betrieb (`DIAKRONOS_BASE_PATH`).

Warum es dieses Modul gibt
--------------------------
Diakronos soll unter einer Gemeinde-Domain neben einer statischen Website
laufen: `/` gehoert der Website, ALLES von Diakronos liegt unter z. B.
`/diakronos/…`. Der Eingang (nginx, Karte WEB-4) reicht `/diakronos/…`
UNVERAENDERT durch — es wird nichts abgeschnitten. Deshalb muss die App ihre
Routen selbst unter dem Praefix anbieten und alle von ihr erzeugten Adressen
(Weiterleitungen, Cookies, Links, Datei-URLs) damit bauen.

Umsetzung: ein Starlette-`Mount` um die gesamte Anwendung
--------------------------------------------------------
`praefigiere(app, pfad)` haengt die komplette Anwendung unter den Praefix:

    app.mount("/diakronos", inner)          # Routen, socket.io, /healthz …

Innerhalb des Mounts sieht die Anwendung ihre gewohnten Pfade (`/login`,
`/api/method/…`). Starlette setzt dabei `root_path` und schneidet den Praefix
ab — die Routen bleiben also unveraendert.

Warum NICHT `FastAPI(root_path=…)` (die Karte verbietet es ausdruecklich):
`root_path` ist genau der Proxy-Trick, der hinter einem Eingang bricht. Er
sagt "der Proxy hat den Praefix schon entfernt" — hier ist es umgekehrt: der
Eingang reicht den Praefix DURCH. Mit `root_path` wuerden die Routen weiter
unter `/login` liegen (also mit dem Praefix 404 liefern) und nur die
erzeugten Links waeren praefigiert.

Folgen des Mounts, die bewusst so sind:

  * Ohne Praefix antworten `/login`, `/api/…` usw. NICHT mehr (404) — sonst
    koennte eine Website-Seite mit dem App-Pfad kollidieren (Karten-Ziel).
  * Die Wurzel `/` gehoert dann dem Eingang. Die App antwortet auf `/` mit
    404, damit sie nichts ueberschreibt. Der Alias `/diakronos` (ohne
    Schraegstrich) leitet auf `/diakronos/diakonos` (die App) um; Starlette
    wuerde dafuer sonst einen 307 auf `/diakronos/` schicken. BASEPATH-2:
    `/diakronos/` (MIT Schraegstrich) leitet genauso um — wer die Adresse
    abtippt oder verlinkt, landet nicht im Leeren. Vorher antwortete die
    Wurzel des Mounts mit 404.

Normalisierung (`normalisiere`)
-------------------------------
   ""            -> ""            (Default: heutiges Verhalten, keine Aenderung)
   "/diakronos"  -> "/diakronos"
   "diakronos/"  -> "/diakronos"
   "/"           -> ""            (wie "kein Praefix")
   "/a/b//"      -> "/a/b"
Ein Praefix, der kein Pfad sein kann (`?`, `#`, Leerzeichen, Backslash,
Steuerzeichen, `//`), wird im Betrieb ABGELEHNT (Start bricht) — ein still
verworfener Wert waere schlimmer: der Betreiber haelt ihn fuer gesetzt.

Der aktive Praefix steht als Prozessgroesse in `aktiver_praefix()`
(gesetzt von `main.erstelle_app` aus der Konfiguration). Laufzeitcode, der
Adressen baut, ruft `pfad()` / `datei_url()` — nie eine Kopie der Einstellung.
"""

from __future__ import annotations

import re

__all__ = [
    "normalisiere",
    "pfad",
    "aktiver_praefix",
    "setze_praefix",
    "datei_url",
    "praefigiere",
]

# Aktiver Praefix dieses Prozesses ("" = kein Praefix). Gesetzt von
# `main.erstelle_app`; Tests, die eine Anwendung mit Praefix bauen, setzen ihn
# ueber `setze_praefix` zurueck bzw. stellen den alten Wert wieder her.
_AKTIV: str = ""

# Zeichen, die in einem URL-Pfad nichts zu suchen haben. Der Praefix landet in
# Cookies (`Path=`), in `Location`-Kopfzeilen und in der Datenbank-Anzeige von
# Links — ein Leerzeichen oder `?` waere dort eine stille Fehlerquelle.
_VERBOTEN = re.compile(r"[\s?#\\\x00-\x1f\x7f\x85\u2028\u2029]")

# MT-2c (zweites Review, NIEDRIG 5): „absolute Adresse“ nur AM ANFANG erkennen
# (`http(s)://…` und protokollrelativ `//host/…`). Ein Teilstring-Test wie
# `"://" in wert` hielt `/files/a.jpg?u=http://x` fuer absolut — die Adresse
# blieb unpraefigiert (toter Link) — und `/files/../../etc/passwd?a=://` kam
# damit an der Praefigierung vorbei.
_ABSOLUTE_ADRESSE = re.compile(r"(?:https?:)?//", re.IGNORECASE)


def normalisiere(wert) -> str:
    """Bringt `DIAKRONOS_BASE_PATH` in die Form "/pfad" (oder "").

    Regeln (Karte WEB-5a, S1): fuehrender Schraegstrich, kein abschliessender.
    Ein Wert, der kein Pfad sein kann, wirft `ValueError` — siehe Modulkopf.
    """
    roh = str(wert or "").strip()
    if not roh or roh == "/":
        return ""
    if _VERBOTEN.search(roh):
        raise ValueError(
            "DIAKRONOS_BASE_PATH darf keine Leerzeichen, Steuerzeichen, "
            "'?', '#' oder '\\' enthalten."
        )
    teile = [t for t in roh.split("/") if t]
    if not teile:
        return ""
    for teil in teile:
        if teil in (".", ".."):
            raise ValueError("DIAKRONOS_BASE_PATH darf keine '.'/'..'-Segmente enthalten.")
    return "/" + "/".join(teile)


def setze_praefix(wert) -> str:
    """Setzt den Prozess-Praefix (normalisiert) und gibt ihn zurueck."""
    global _AKTIV
    _AKTIV = normalisiere(wert)
    return _AKTIV


def aktiver_praefix() -> str:
    """Der aktive Praefix dieses Prozesses ("" = keiner)."""
    return _AKTIV


def pfad(ziel: str) -> str:
    """Setzt den aktiven Praefix vor einen app-eigenen Pfad.

        pfad("/login")        -> "/login"           (ohne Praefix)
        pfad("/login")        -> "/diakronos/login" (Praefix /diakronos)

    Bereits praefigierte Pfade bleiben unveraendert (idempotent) — sonst
    wuerde ein doppelt durchlaufener Aufruf `/diakronos/diakronos/...` bauen.
    Absolute Adressen (`https://…`) und fremde Schemata bleiben unangetastet.
    """
    wert = str(ziel or "")
    if not wert:
        return _AKTIV or ""
    if "://" in wert or wert.startswith("//"):
        return wert
    if not _AKTIV:
        return wert
    if not wert.startswith("/"):
        wert = "/" + wert
    if wert == _AKTIV or wert.startswith(_AKTIV + "/"):
        return wert
    return _AKTIV + wert


def datei_url(url) -> str:
    """Datei-URL mit Praefix — DB-Werte bleiben unveraendert.

    In der Datenbank stehen `file_url`-Werte der Form `/files/…` bzw.
    `/private/files/…` (Frappe-Erbe, Karte: DB NICHT migrieren). Bei der
    AUSGABE werden sie praefigiert. Alles andere (leer, absolute Adresse,
    schon praefigiert) bleibt, wie es ist.

    Absolute Adressen werden nur AM ANFANG erkannt (`http(s)://…`, `//host/…`).

    MT-2d (drittes Review, NIEDRIG 3): praefigiert wird hier DIREKT, nicht
    mehr ueber `pfad()`. `pfad()` prueft weiter `"://" in wert` — damit blieb
    `/files/a.jpg?u=http://x` entgegen diesem Docstring unpraefigiert (toter
    Link). `pfad()` gehoert nicht zu dieser Karte, die Ausgabe von
    Datei-Adressen schon.
    """
    wert = str(url or "")
    if not wert:
        return wert
    if _ABSOLUTE_ADRESSE.match(wert) or not wert.startswith("/"):
        return wert
    if not _AKTIV:
        return wert
    if wert == _AKTIV or wert.startswith(_AKTIV + "/"):
        return wert
    return _AKTIV + wert


def praefigiere(app, praefix: str):
    """Haengt die gesamte Anwendung unter `praefix`.

    `praefix == ""` gibt die Anwendung unveraendert zurueck — der Default
    (heutige Installationen) verhaelt sich exakt wie bisher.
    """
    wert = normalisiere(praefix)
    if not wert:
        return app
    from starlette.applications import Starlette
    from starlette.responses import RedirectResponse
    from starlette.routing import Mount, Route

    app_ziel = wert + "/diakonos"

    async def _alias(request):  # noqa: ANN001 — Starlette-Endpunkt
        """`/diakronos` -> `/diakronos/diakonos` (Karte WEB-5a, S4).

        Ohne diese Route schickt der Mount einen 307 auf `/diakronos/`.
        """
        return RedirectResponse(app_ziel, status_code=302)

    async def _mount_wurzel(request):  # noqa: ANN001
        """`/diakronos/` -> `/diakronos/diakonos` (BASEPATH-2).

        Diese Route steht VOR dem Mount; ohne sie beantwortete der Mount
        seine eigene Wurzel mit 404 — wer die Adresse mit Schraegstrich
        eintippt oder verlinkt, landete im Leeren. Ziel ist dasselbe wie
        beim Alias ohne Schraegstrich, damit beide Schreibweisen ankommen.
        """
        return RedirectResponse(app_ziel, status_code=302)

    # Reihenfolge = Prioritaet: die beiden genauen Pfade VOR dem Mount.
    return Starlette(
        routes=[
            Route(wert, endpoint=_alias, methods=["GET", "HEAD"]),
            Route(wert + "/", endpoint=_mount_wurzel, methods=["GET", "HEAD"]),
            Mount(wert, app=app),
        ]
    )
