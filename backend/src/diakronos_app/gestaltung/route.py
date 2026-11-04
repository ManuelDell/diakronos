"""UX1j — Öffentliche Route ``{Präfix}/gestaltung.css``.

Sie liefert AUSSCHLIESSLICH ``:root { --token: 16px; … }`` der gespeicherten
Abweichungen — nichts sonst: keine Selektoren aus Nutzereingaben, keine
``url()``, keinen Kommentar-Inhalt aus der Datenbank. Der Text wird aus der
Positivliste gebaut (`speicher.als_css`: nur bekannte Namen, nur ganze Zahlen
mit ``px``); die Werte kommen als Zahlen aus der Datenbank. CSS-Injection ist
damit strukturell ausgeschlossen, nicht durch Escaping.

WARUM VOR DER ANMELDESCHRANKE
-----------------------------
Die Werte gelten für die ganze Oberfläche — auch für die Anmeldeseite (die
serverseitig aus ``anmeldung/seitenrahmen.py`` gebaut wird). Eine Datei, die
erst nach der Anmeldung erreichbar wäre, könnte die Anmeldeseite nicht
einstellen. Sie verrät auch nichts: die Abweichungen sind Gestaltungsmaße,
keine Personen- oder Bestandsdaten — und ohne Abweichungen ist die Datei LEER.

Cache
-----
``ETag`` aus dem Inhalts-Hash und ``Cache-Control: no-cache`` — derselbe
Vertrag wie bei ``diakronos-tokens.css`` (``spa._asset_response``): der Browser
fragt bei jedem Aufruf nach und bekommt bei unverändertem Inhalt 304. Der
Hash wird zusätzlich als ``?v=`` an die Adresse gehängt (siehe
``seitenrahmen.head_block``), damit auch Zwischenspeicher eine Änderung sehen.
"""

from __future__ import annotations

import logging

from starlette.responses import Response

from diakronos_app import base_path

from . import speicher

logger = logging.getLogger("diakronos_app.gestaltung.route")

__all__ = ["CSS_PFAD", "css_url", "gestaltung_css", "css_hash", "registriere_routen"]

#: App-eigener Pfad (der Betriebs-Präfix kommt beim Bauen der Adresse davor).
CSS_PFAD = "/gestaltung.css"

#: Ein Tag Zwischenspeicher, aber mit Nachfrage (304 bei unverändertem ETag).
_CACHE = "no-cache"


def css_url() -> str:
    """Adresse der Datei (präfixbewusst) — ohne ``?v=``."""
    return base_path.pfad(CSS_PFAD)


def css_hash() -> str:
    """Inhalts-Hash der Abweichungen (ETag und ``?v=``)."""
    return speicher.css_hash()


async def gestaltung_css(request):  # noqa: ANN001, ARG001 — Starlette-Signatur
    """Die CSS-Antwort: ETag-Vergleich, dann Inhalt oder 304."""
    inhalt = speicher.als_css()
    etag = '"' + speicher.css_hash() + '"'

    vorhanden = request.headers.get("if-none-match") or ""
    # `*` und eine Liste von Tags sind beide möglich; der Vergleich genügt
    # wörtlich, weil WIR das ETag bauen (ein schwaches `W/` gibt es hier nicht).
    if vorhanden and etag in [teil.strip() for teil in vorhanden.split(",")]:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": _CACHE})

    return Response(
        content=inhalt,
        media_type="text/css; charset=utf-8",
        headers={"ETag": etag, "Cache-Control": _CACHE},
    )


def registriere_routen(app) -> None:
    """Trägt die Route ein (idempotent).

    MUSS vor der Anmeldeschranke und vor dem SPA-Catch-all laufen
    (``main.erstelle_app``) — sonst liefert die SPA HTML statt CSS.
    """
    ziele = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    if CSS_PFAD not in ziele:
        app.add_route(CSS_PFAD, gestaltung_css, methods=["GET", "HEAD", "OPTIONS"])
