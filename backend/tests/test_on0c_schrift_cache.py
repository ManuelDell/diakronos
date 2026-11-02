"""ON-0c (R3) — Schriften der Server-Seiten: Cache-Falle geschlossen.

DER BEFUND
----------
Die Schriften der Server-Seiten liegen im Build unter `dist/schriften/` und
tragen den Namen aus der Quelle (`inter-latin-400-normal.woff2`). `spa.py`
entscheidet die Cache-Regel ueber `_HASH_NAME` — und dieser Ausdruck hielt
`inter-latin-400-normal` fuer einen Inhalts-Hash (`400` ist hex, `normal`
passt auf `[A-Za-z0-9_\\-]{6,}`). Ergebnis: die Datei wurde
`Cache-Control: public, max-age=31536000, immutable` ausgeliefert — OHNE dass
die Adresse einen Versionswert trug. Nach einem Schriften-Wechsel haette ein
wiederkehrender Besucher bis zu EIN JAHR die alte Datei behalten.

WAS HIER FESTGENAGELT WIRD
--------------------------
 1. `_adress_unterordner` nimmt `schriften/` aus: keine Umleitung, kein
    `immutable`. Die Datei kommt mit `no-cache` (und damit mit Rueckfrage).
 2. Der Vite-Plugin haengt `?v=<Inhalts-Hash>` an JEDE Schrift-Adresse der
    Server-Stylesheets. Zwei gleiche Schriften ergeben denselben Wert, eine
    geaenderte einen anderen.
 3. Ausgeliefert wird sie trotzdem unter `{Praefix}/diakonos/assets/schriften/
    <name>` — auch MIT `?v=` in der Adresse (der Wert aendert die Aufloesung
    nicht, er entwertet nur den Zwischenspeicher).
 4. Die Schriften der SPA (`assets/<name>-<hash>.woff2`) bleiben `immutable` —
    dort IST der Name der Inhalts-Hash.

Laeuft IM Image (dort liegt der Build unter /app/frontend/dist). Fehlt der
Build, wird der Auslieferungsteil uebersprungen — die Quelltext-Pruefungen
laufen immer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
VITE = REPO / "frontend" / "vite.config.mjs"


def _build_hat_schriften() -> bool:
    from diakronos_app.spa import SEITENRAHMEN_SCHRIFT_NAMEN, SEITENRAHMEN_SCHRIFTEN, SPA_DIST

    if SPA_DIST is None:
        return False
    ordner = SPA_DIST / SEITENRAHMEN_SCHRIFTEN
    return ordner.is_dir() and all((ordner / n).is_file() for n in SEITENRAHMEN_SCHRIFT_NAMEN)


# ── 1 · Der Build haengt den Inhalts-Hash an die Adresse ───────────────────


def test_build_haengt_inhalts_hash_an_die_schrift_adresse() -> None:
    """Der Plugin schreibt `url(./schriften/<name>?v=<hash>)`."""
    assert VITE.is_file(), f"vite.config.mjs fehlt ({VITE})"
    text = VITE.read_text(encoding="utf-8")
    # Der Hash kommt aus dem INHALT (sha256), nicht aus der Zeit.
    assert "createHash('sha256')" in text, "kein Inhalts-Hash im Schriftpfad"
    assert re.search(r"\.slice\(0,\s*HASH_LAENGE\)", text), "Hash ohne feste Laenge"
    # Und er steht wirklich in der erzeugten `url()`-Angabe.
    assert re.search(r"url\(\$\{quote\}\./\$\{SCHRIFT_ORDNER\}/\$\{name\}\?v=", text), (
        "die Schrift-Adresse traegt kein ?v=<hash>"
    )


def test_hash_laenge_passt_zu_seitenrahmen() -> None:
    """`?v=` in seitenrahmen.py nimmt 12 Zeichen — der Build muss dasselbe tun.

    Ein kuerzerer Wert im CSS waere kein Fehler, ein LAENGERER aber auch nicht
    — die Zusage ist: beide Seiten sprechen von derselben Laenge, damit ein
    Vergleich in einem Protokoll ohne Umrechnen funktioniert.
    """
    vite = VITE.read_text(encoding="utf-8")
    rahmen = (
        REPO / "backend" / "src" / "diakronos_app" / "anmeldung" / "seitenrahmen.py"
    ).read_text(encoding="utf-8")
    m = re.search(r"HASH_LAENGE\s*=\s*(\d+)", vite)
    assert m, "HASH_LAENGE fehlt im Build"
    n = int(m.group(1))
    assert f"[:{n}]" in rahmen or f":{n}]" in rahmen, (
        f"seitenrahmen.py nutzt nicht die Laenge {n} des Builds"
    )


# ── 2 · spa.py liefert die Schriften NICHT immutable ──────────────────────


def test_schriften_unterordner_ist_ausgenommen() -> None:
    """`_adress_unterordner` gibt fuer `schriften/<name>.woff2` None zurueck.

    Das ist die Stelle, an der die Cache-Regel entschieden wird: mit einem
    Unterordner waere die Antwort `immutable`.
    """
    from diakronos_app import spa

    ordner = spa.SPA_DIST if spa.SPA_DIST is not None else Path("/tmp")
    probe = ordner / spa.SEITENRAHMEN_SCHRIFTEN / "inter-latin-400-normal.woff2"
    assert spa._adress_unterordner(probe) is None, (
        "die feste Schrift landet wieder im immutable-Zweig"
    )
    # Gegenprobe: eine echte Hash-Datei der SPA bekommt ihren Unterordner.
    hashed = ordner / "assets" / "inter-latin-400-normal-a1b2c3.woff2"
    assert spa._adress_unterordner(hashed) == "assets", (
        "SPA-Schriften verlieren ihre Umleitung"
    )


@pytest.mark.skipif(not _build_hat_schriften(), reason="Kein Frontend-Build mit Schriften")
def test_schriftdatei_kommt_mit_no_cache(fake_redis) -> None:
    """Auslieferung per HTTP: 200, Typ font/, `no-cache`, KEIN `immutable`.

    Geprueft wird die Adresse aus dem CSS — mit `?v=` und ohne. Beides muss
    dieselbe Datei liefern; der Versionswert entwertet nur den Cache.
    """
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen
    from diakronos_app.main import app
    from diakronos_app.spa import SEITENRAHMEN_SCHRIFT_NAMEN

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        with TestClient(app) as client:
            tokens = client.get(seitenrahmen.tokens_url())
            assert tokens.status_code == 200
            urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", tokens.text)
            schrift_urls = [u for u in urls if u.endswith(".woff2") or ".woff2?" in u]
            assert schrift_urls, "die Token-Datei nennt keine Schrift"
            for ziel in schrift_urls:
                assert re.search(r"\?v=[0-9a-f]{6,}", ziel), (
                    f"{ziel}: kein Inhalts-Hash in der Schrift-Adresse"
                )
                adresse = (
                    ziel if ziel.startswith("/")
                    else f"/diakonos/assets/{ziel[2:] if ziel.startswith('./') else ziel}"
                )
                antwort = client.get(adresse)
                assert antwort.status_code == 200, f"{adresse}: HTTP {antwort.status_code}"
                assert antwort.headers.get("content-type", "").startswith("font/")
                cache = antwort.headers.get("cache-control", "")
                assert "immutable" not in cache, f"{adresse}: immutable ohne Hash-Namen ({cache})"
                assert "no-cache" in cache, f"{adresse}: kein no-cache ({cache})"

            # Auch OHNE `?v=` (alte Verknuepfung) kommt dieselbe Datei — und
            # ebenfalls ohne `immutable`.
            for name in SEITENRAHMEN_SCHRIFT_NAMEN:
                antwort = client.get(f"/diakonos/assets/schriften/{name}")
                assert antwort.status_code == 200, f"{name}: HTTP {antwort.status_code}"
                cache = antwort.headers.get("cache-control", "")
                assert "immutable" not in cache, f"{name}: noch immutable ({cache})"
    finally:
        base_path.setze_praefix(alt)


@pytest.mark.skipif(not _build_hat_schriften(), reason="Kein Frontend-Build mit Schriften")
def test_spa_schriften_bleiben_immutable(fake_redis) -> None:
    """Gegenprobe: die SPA-Schrift `assets/<name>-<hash>.woff2` bleibt `immutable`.

    Die Ausnahme gilt NUR fuer `schriften/`. Ohne diesen Test waere ein zu
    breiter Fix (alles `no-cache`) unbemerkt.
    """
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.main import app
    from diakronos_app.spa import SPA_DIST

    assert SPA_DIST is not None
    kandidaten = sorted((SPA_DIST / "assets").glob("*.woff2"))
    if not kandidaten:
        pytest.skip("keine gehashten Schriften im Build")
    datei = kandidaten[0]
    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        with TestClient(app) as client:
            antwort = client.get(f"/diakonos/assets/assets/{datei.name}")
            assert antwort.status_code == 200, f"HTTP {antwort.status_code}"
            assert "immutable" in antwort.headers.get("cache-control", ""), (
                "die gehashte SPA-Schrift verliert ihren Dauer-Cache"
            )
    finally:
        base_path.setze_praefix(alt)
