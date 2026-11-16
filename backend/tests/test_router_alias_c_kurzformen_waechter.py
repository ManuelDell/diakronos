"""ROUTER-ALIAS-c — Waechter: niemand benutzt die verbotenen Kurzformen.

SOLL 4 der Karte: Kurzformen sind nur noch erlaubt, wenn sie EINDEUTIG und
ausdruecklich zugesagt sind. Bevor das gilt, muss belegt sein, dass
`frontend/src`, `tools/` und `backend/src` die gestrichenen Schreibweisen
nicht benutzen — sonst faellt die SPA beim naechsten Klick auf 404.

Geprueft wird der QUELLTEXT (wie der SPA-Waechter daneben): jeder Aufruf
`api/method/<pfad>` bzw. `apiCall('…')`/`apiUrl('…')`/`fetch('…')` mit einem
gestrichenen Pfad ist ein Befund. Die Frappe-Schreibweisen (`frappe.client.
insert`, `upload_file`, `logout`, `frappe.sessions.get_csrf_token`) bleiben
zugesagt und sind deshalb nicht betroffen.
"""

from __future__ import annotations

import os
import re

import pytest

_WURZELN = (
    "/frontend/src",
    "/repo/frontend/src",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"),
)
_TOOLS = (os.path.join(os.path.dirname(__file__), "..", "..", "tools"),)
_BACKEND = (os.path.join(os.path.dirname(__file__), "..", "src"),)

#: Gestrichene Kurzformen (SOLL 4 der Karte). Getrennt gehalten, weil der
#: stumme Name (`insert`) nur als GANZER Pfad verboten ist, `session.insert`
#: dagegen eine Modulbahn waere.
_VERBOTEN = (
    # Mehrdeutig im Register (mehrere gleichnamige Fassungen).
    "sitzung_status",
    "status",
    "liste",
    # Vorlauf statt Kurzform.
    "api.insert",
    "api.upload_file",
    "api.logout",
    "api.root_uebertragen",
    # Frappe-Kernfunktion: nur ihre zugesagte Schreibweise.
    "insert",
)

#: Ein Methodenpfad, wie ihn Frontend/Tools schreiben. Auch die
#: Konstanten-Bauform `ruf('name')` zaehlt: `PRAEFIX + methode` wird beim
#: Scannen zusammengesetzt (`_praefix_von`).
_MUSTER = re.compile(
    r"(?:api/method/|apiCall\(\s*[`'\"]|apiUrl\(\s*[`'\"]|apiPost\(\s*[`'\"]"
    r"|apiGet\(\s*[`'\"]|ruf\(\s*[`'\"])([A-Za-z0-9_.]+)"
)
#: `const PRAEFIX = 'diakronos.x.api.'` — Bahnen fuer `ruf('<fn>')`.
_PRAEFIX = re.compile(r"const\s+PRAEFIX\s*=\s*[`'\"]([A-Za-z0-9_.]+)[`'\"]")


def _dateien(wurzeln: tuple[str, ...]) -> list[str]:
    gefunden: list[str] = []
    for wurzel in wurzeln:
        if not os.path.isdir(wurzel):
            continue
        for ordner, _u, dateien in os.walk(wurzel):
            for name in dateien:
                if name.endswith((".js", ".mjs", ".vue", ".py", ".cjs", ".html")):
                    gefunden.append(os.path.join(ordner, name))
    return gefunden


def _frontend_wurzel() -> str:
    for pfad in _WURZELN:
        if os.path.isdir(pfad):
            return pfad
    pytest.skip("frontend/src nicht gefunden")


@pytest.mark.parametrize("bereich", ["frontend", "tools", "backend"])
def test_keine_gestrichene_kurzform_im_quelltext(bereich):
    """Kein Aufrufer benutzt eine gestrichene Kurzform (sonst 404 im Betrieb)."""
    wurzeln = {
        "frontend": (_frontend_wurzel(),),
        "tools": _TOOLS,
        "backend": _BACKEND,
    }[bereich]
    befund: list[str] = []
    for datei in _dateien(wurzeln):
        with open(datei, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # Bahn der Datei (`const PRAEFIX = 'diakronos.x.api.'`) fuer `ruf('<fn>')`.
        bahn = _PRAEFIX.search(text)
        praefix = bahn.group(1) if bahn else ""
        for nummer, zeile in enumerate(text.splitlines(), 1):
            for treffer in _MUSTER.finditer(zeile):
                ziel = treffer.group(1).rstrip(".")
                # `ruf('sitzung_status')` in einer Datei mit `PRAEFIX` baut den
                # vollen Pfad `diakronos.x.api.sitzung_status`.
                voll = f"{praefix}{ziel}" if praefix and "." not in ziel else ziel
                # Nur der GANZE Pfad zaehlt: `diakronos.x.api.status` ist eine
                # Modulbahn, `status` die gestrichene Kurzform.
                if voll in _VERBOTEN:
                    befund.append(f"{datei}:{nummer}: {voll}")
    assert befund == [], "gestrichene Kurzform im Quelltext:\n" + "\n".join(befund[:20])


def test_frontend_pfade_nutzen_keine_kurzform():
    """Gegenprobe am Scanner des SPA-Waechters: nur volle Modulbahnen."""
    import test_router_alias_waechter as W

    kurz = [p for p in W._frontend_pfade() if "." not in p and p != "diakronos.x.y"]
    kurz = [p for p in kurz if p not in {"upload_file"}]
    assert kurz == [], f"SPA ruft Kurzformen ohne Modulbahn: {kurz}"
