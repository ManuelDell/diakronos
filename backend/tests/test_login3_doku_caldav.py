"""LOGIN-3 / M-1 — Doku: CalDAV prueft das KONTOPASSWORT, nicht „App-Passwoerter".

Befund R-LOGIN-2 (M-1): `settings.py`, `.env.example` und die
BETRIEBSANLEITUNG behaupteten, CalDAV sei von `AUTH_LOCAL_LOGIN` nicht
betroffen, weil es „App-Passwoerter" nutze. Das ist falsch: es gibt in diesem
Projekt KEINE App-Passwoerter. `caldav/auth.py::_check_credentials` prueft
`user.password_hash` — also dasselbe Kontopasswort wie die SPA.

Das Verhalten wird hier NICHT geaendert (die Fachentscheidung, ob CalDAV ein
eigenes Passwort bekommen soll, liegt beim Operator). Geaendert wird die
Aussage darueber: die Doku muss sagen, was der Code tut, und die Folge
benennen — wer `AUTH_LOCAL_LOGIN=aus` setzt, sperrt damit NUR den Login, nicht
CalDAV; ein Kalender-Client mit gueltigem Kontopasswort kommt weiterhin durch.

Zusaetzlich (Kartentext M-1): die Voraussetzung fuer den Herkunftsvergleich
gehoert in die BETRIEBSANLEITUNG — der Reverse-Proxy MUSS den `Host`-Header
durchreichen (`proxy_set_header Host $http_host`) und `X-Forwarded-Proto`
melden, sonst kann der Server die Herkunft nicht mit dem eigenen Host
vergleichen und der legitime Login hinter dem Proxy scheitert.
"""

from __future__ import annotations

from pathlib import Path

import pytest

#: Kandidaten fuer die Projektwurzel. Im Worktree-Lauf liegt das Backend unter
#: <wurzel>/backend (parents[1] = backend), im gebauten Image unter /app
#: (parents[1] = /app). `docs/` steht in .dockerignore und ist im Image NICHT
#: vorhanden — die Tests, die es lesen, werden dort uebersprungen (LOGIN-4/T),
#: statt still gruen zu sein: `_repo()` liefert `None`, `_lies()` skippt mit
#: Begruendung.
_REPO_KANDIDATEN = (
    Path(__file__).resolve().parents[2],  # <repo>/backend/tests -> <repo>
    Path(__file__).resolve().parents[1],  # /app/tests -> /app (Image)
    Path("/app"),
    Path("/repo"),
)


def _repo() -> Path | None:
    """Projektwurzel — im Worktree-Lauf gefunden, im Image bewusst nicht.

    Gesucht wird das Verzeichnis, das `docs/BETRIEBSANLEITUNG.md` enthaelt.
    Im gebauten Image fehlt `docs/` (siehe .dockerignore); dort gibt es
    keinen zweiten Ort, an dem die Betriebsdoku liegt — der Test kann also
    nichts pruefen und wird uebersprungen, nie still bestanden.
    """
    for kandidat in _REPO_KANDIDATEN:
        if (kandidat / "docs" / "BETRIEBSANLEITUNG.md").is_file():
            return kandidat
    return None


def _repo_pflicht() -> Path:
    """Projektwurzel oder `pytest.skip` mit Begruendung (Image ohne `docs/`)."""
    wurzel = _repo()
    if wurzel is None:
        pytest.skip(
            "docs/ ist im Image nicht vorhanden (.dockerignore) — die Pruefung "
            f"gegen die Betriebsdoku entfaellt; gesucht in {[str(k) for k in _REPO_KANDIDATEN]}"
        )
    return wurzel


def _lies(relativ: str) -> str:
    return (_repo_pflicht() / relativ).read_text(encoding="utf-8")


def _zeilen(relativ: str) -> list[str]:
    return _lies(relativ).splitlines()


# ── Die falsche Behauptung ist weg ────────────────────────────────────────


def test_settings_erwaehnt_keine_app_passwoerter():
    quelle = _lies("backend/src/diakronos_app/settings.py")
    assert "App-Passwoerter" not in quelle
    assert "App-Passwort" not in quelle


def test_env_beispiel_erwaehnt_keine_app_passwoerter():
    quelle = _lies(".env.example")
    assert "App-Passwoerter" not in quelle
    assert "App-Passwort" not in quelle


def test_betriebsanleitung_erwaehnt_keine_app_passwoerter():
    quelle = _lies("docs/BETRIEBSANLEITUNG.md")
    assert "App-Passwörter" not in quelle
    assert "App-Passwoerter" not in quelle


# ── Und die richtige Aussage steht da ─────────────────────────────────────


@pytest.mark.parametrize(
    "relativ",
    ["backend/src/diakronos_app/settings.py", ".env.example", "docs/BETRIEBSANLEITUNG.md"],
)
def test_doku_nennt_das_kontopasswort_als_caldav_anmeldedaten(relativ):
    quelle = _lies(relativ)
    assert "Kontopasswort" in quelle, (
        f"{relativ}: CalDAV meldet sich mit dem normalen Kontopasswort an — "
        "das muss dort stehen (M-1)"
    )


def test_betriebsanleitung_nennt_host_durchreichen_als_voraussetzung():
    """`proxy_set_header Host` ist die Voraussetzung der Herkunftspruefung."""
    quelle = _lies("docs/BETRIEBSANLEITUNG.md")
    assert "proxy_set_header Host" in quelle
    assert "X-Forwarded-Proto" in quelle


def test_betriebsanleitung_ordnet_das_durchreichen_dem_proxy_zu():
    """Die Anweisung steht nicht irgendwo, sondern beim Reverse-Proxy-Kapitel."""
    zeilen = _zeilen("docs/BETRIEBSANLEITUNG.md")
    treffer = [i for i, z in enumerate(zeilen) if "proxy_set_header Host" in z]
    assert treffer, "Anweisung fehlt"
    # Kontext: innerhalb von 60 Zeilen davor muss der Proxy/Abschnitt stehen.
    umfeld = "\n".join(
        "\n".join(zeilen[max(0, i - 60) : i + 10]) for i in treffer
    )
    assert "NPM" in umfeld or "Proxy" in umfeld or "nginx" in umfeld.lower()


# ── Keine erfundene Fachtatsache: CalDAV prueft das Kontopasswort ─────────


def test_caldav_prueft_das_kontopasswort_das_ist_der_beleg():
    """Die Doku-Aussage oben ist am Code belegt, nicht behauptet.

    `caldav/auth.py::_check_credentials` prueft `user.password_hash` mit
    `passwoerter.pruefe` — dasselbe Kontopasswort wie der Login. Gaebe es
    App-Passwoerter, muesste hier eine zweite Passworttabelle/-spalte stehen;
    die gibt es nicht.
    """
    quelle = _lies("backend/src/diakronos_app/caldav/auth.py")
    assert "password_hash" in quelle
    assert "pruefe(" in quelle
    # Kein zweiter Geheimnisspeicher fuer Kalender.
    for verboten in ("app_passwort", "app_password", "kalender_passwort", "dav_passwort"):
        assert verboten not in quelle.lower()
