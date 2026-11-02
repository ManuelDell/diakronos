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

#: SEC-11c (R4): im App-IMAGE liegt der Quellbaum unter `/app` (BACKEND=/app),
#: der Repo-Elternordner `/` ist KEIN Quellbaum. Frueher rechnete `_lies` mit
#: `REPO / "frontend/…"` -> `/frontend/…` und fand die SPA-Quellen nie; der
#: Dockerfile-Pfad `BACKEND / "Dockerfile"` existiert im Image ebenfalls nicht
#: (backend/Dockerfile wird nicht ins Image kopiert). Beides ist jetzt eine
#: ausdrueckliche Ortsbestimmung statt einer Rechnung mit `..`: das Image
#: traegt seine Quellen unter `/app/frontend` mit, das Repo unter `<repo>/frontend`.
_IMAGE_WURZELN = ("/app",)


def _wurzel() -> Path:
    """Quellbaum-Wurzel: `<repo>` im Worktree, `/app` im Image."""
    for kandidat in (REPO, BACKEND, *map(Path, _IMAGE_WURZELN)):
        if (kandidat / "frontend").is_dir():
            return kandidat
    # Kein frontend/ gefunden: REPO ist der aussagekraeftigste Pfad fuer die
    # Fehlermeldung (der Test nennt ihn).
    return REPO


WURZEL = _wurzel()

TOUCH_CSS = "@media (pointer: coarse)"
IMAGE_NETZ = ("fix6-zeigegeraet.test.mjs", "fix6-keine-zeiger-syntax.test.mjs")


def _ohne_kommentare(text: str) -> str:
    """CSS-Kommentare entfernen — Kommentartext ist keine Regel."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


# ON-0b (F5): Seit ON-0a/ON-0b tragen die Login-Masken KEIN eigenes CSS mehr —
# die 16-px-Regel fuer den groben Zeiger steht EINMAL im gemeinsamen
# Grund-Stylesheet der Server-Seiten (`src/ssot/seiten.css`, ausgeliefert als
# diakronos-seiten.css). Die Regel gilt weiterhin (der Test prueft sie jetzt
# dort); die Masken pruefen wir darauf, dass sie sie nicht wieder selbst
# nachbauen.
@pytest.mark.parametrize(
    "pfad",
    [
        "src/diakronos_app/spa.py",
        "src/diakronos_app/anmeldung/routen.py",
        "frontend/src/ssot/seiten.css",
    ],
)
def test_fix6_login_maske_nutzt_zeiger_kriterium(pfad: str) -> None:
    try:
        gefunden = next(k for k in (BACKEND / pfad, WURZEL / pfad, REPO / pfad)
                        if k.is_file())
    except StopIteration:
        # SEC-11c (R4): das App-Image traegt von `frontend/` nur `dist/` —
        # die QUELLE `frontend/src/ssot/seiten.css` gibt es dort nicht. Ein
        # Skip mit Begruendung ist richtig; der gebaute Stand wird ohnehin vom
        # Frontend-Bau-Stage geprueft (`backend/Dockerfile --target frontend`).
        pytest.skip(
            f"{pfad} liegt im Image nicht vor (nur backend/-Quellen und "
            f"frontend/dist sind dort) — gesucht unter {BACKEND}, {WURZEL}, {REPO}")
    text = _ohne_kommentare(gefunden.read_text(encoding="utf-8"))
    if not pfad.endswith("seiten.css"):
        # Die Maske selbst: KEIN eigenes @media mehr (eine Quelle).
        assert TOUCH_CSS not in text and "font-size: 16px" not in text, (
            f"{pfad}: baut die 16-px-Regel wieder selbst — sie gehoert in seiten.css"
        )
        return
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
    # ON-0b: der Wert kommt aus dem Token --fs-in-zeiger (16 px, tokens.css) —
    # die Regel bleibt 16 px, nur die Zahl steht nicht mehr hier.
    assert "font-size: var(--fs-in-zeiger)" in block or "font-size: 16px" in block, (
        f"{pfad}: `{TOUCH_CSS}` ohne 16-px-Felder"
    )


def test_fix6_node_tests_stehen_im_image() -> None:
    """Der Dockerfile-Waechter braucht den Dockerfile — und wenn er fehlt, sagt
    der Test WARUM er uebersprungen wird (SEC-11c/R4).

    BEFUND (Image-Abnahme SEC-11c): `backend/Dockerfile` wird nicht ins Image
    kopiert; im Image gab es die Datei nie, der Test brach mit `AssertionError`
    ab. Richtig ist ein SKIP mit Begruendung: die eine Aussage („das Glob steht
    in der node --test-Zeile") ist am gebauten Image nicht mehr zu treffen —
    sie ist bereits Teil des Baus. Im Repo/Worktree laeuft der Test wie bisher.
    """
    dockerfile = ((BACKEND / "Dockerfile").read_text(encoding="utf-8")
                  if (BACKEND / "Dockerfile").is_file() else None)
    if dockerfile is None:
        pytest.skip(
            "backend/Dockerfile liegt nicht im Image (wird nicht kopiert) — "
            f"gesucht unter {BACKEND / 'Dockerfile'}; die node --test-Liste "
            "wird im Repo/Worktree geprueft, nicht im gebauten Image"
        )
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
        assert (WURZEL / "frontend/tests" / name).is_file(), (
            f"frontend/tests/{name} fehlt (gesucht unter {WURZEL})"
        )
