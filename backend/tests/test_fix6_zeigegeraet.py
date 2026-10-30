"""FIX-6 — Zeiger-Kriterium in den serverseitigen Login-Masken und in der
node-Testliste des Images.

Der Node-Test `frontend/tests/fix6-zeigegeraet.test.mjs` prüft die SPA-Seite.
Die Login-Masken kann er im gebauten Image nicht sehen, weil `backend/` in
`.dockerignore` steht — dort liegt nur `frontend/`. Diesen Test fährt das
App-Image deshalb mit.

Kriterien der Karte (Operator-Entscheidung 27.10.):

  LAYOUT  → nur die Breite: `@media (max-width: 720px)`
  TOUCH   → nur der Zeiger: `@media (pointer: coarse)` (ohne Breite)

Die Login-Masken haben keine Breiten-Umschaltung (das Formular ist immer
schmal) und tragen nur die Touch-Regel (OP-HANDY-14: 16 px gegen den
iOS-Zoom). Geprüft wird ausserdem:

  * keine Stufe-4-Syntax (`not (... or ...)`) — Safari < 16.4 kennt sie nicht,
  * kein `any-pointer` / `hover: none` (Touch-Fähigkeit ist kein Kriterium),
  * die beiden FIX-6-Node-Testdateien stehen in der `node --test`-Liste der
    `backend/Dockerfile` (sonst laufen sie im Image nie).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DATEI = Path(__file__).resolve()
# /backend/tests/test_fix6_zeigegeraet.py -> /backend  |  <repo>/backend/tests/... -> <repo>
BACKEND = DATEI.parent.parent if DATEI.parent.name == "tests" else DATEI.parent
REPO = BACKEND.parent

TOUCH_CSS = "@media (pointer: coarse)"
IMAGE_NETZ = ("fix6-zeigegeraet.test.mjs", "fix6-keine-zeiger-syntax.test.mjs")


def _lies(pfad: Path) -> str:
    assert pfad.is_file(), f"{pfad} fehlt"
    return pfad.read_text(encoding="utf-8")


def _ohne_kommentare(text: str) -> str:
    """CSS-Kommentare entfernen — Kommentartext ist keine Regel."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


@pytest.mark.parametrize(
    "pfad",
    ["src/diakronos_app/spa.py", "src/diakronos_app/anmeldung/routen.py"],
)
def test_fix6_login_maske_nutzt_zeiger_kriterium(pfad: str) -> None:
    text = _ohne_kommentare(_lies(BACKEND / pfad))
    assert TOUCH_CSS in text, (
        f"{pfad}: 16-px-Regel der Login-Maske hängt nicht an "
        f"`{TOUCH_CSS}` (nur der Zeiger, ohne Breite)"
    )
    assert "hover: none" not in text, f"{pfad}: hover: none ist noch aktiv"
    assert "any-pointer" not in text, f"{pfad}: any-pointer ist noch aktiv"
    assert not re.search(r"@media[^{]*\bnot\s*\(", text), (
        f"{pfad}: `not (...)` in einer @media-Regel (Safari < 16.4)"
    )
    # Die 16-px-Regel steht im Block dieses @media — bis zum nächsten @media.
    block = text.split(TOUCH_CSS)[1].split("@media")[0]
    assert "font-size: 16px" in block, (
        f"{pfad}: `{TOUCH_CSS}` ohne 16-px-Felder"
    )


def test_fix6_node_tests_stehen_im_image() -> None:
    dockerfile = _lies(BACKEND / "Dockerfile")
    # Die Zeile mit der node --test-Liste (sie endet auf `--test \`).
    zeile = next(
        (z for z in dockerfile.splitlines() if "node --test" in z),
        "",
    )
    assert "tests/fix6-*.test.mjs" in zeile, (
        "backend/Dockerfile: tests/fix6-*.test.mjs fehlt in der node --test-Liste"
    )
    # Die Testdateien selbst müssen im Quellbaum existieren, sonst läuft das
    # Glob im Image ins Leere.
    for name in IMAGE_NETZ:
        assert (REPO / "frontend/tests" / name).is_file(), (
            f"frontend/tests/{name} fehlt"
        )
