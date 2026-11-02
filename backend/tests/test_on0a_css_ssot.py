"""ON-0a — CSS-Single-Source-of-Truth: tokens.css ist die EINZIGE Farbquelle.

WARUM
-----
Die Anmeldeseite (`anmeldung/routen.py`), die Passwort-Seite
(`anmeldung/passwortseite.py`) und die Inline-Maske (`spa.py::render_login`)
trugen eigene Hex-Farben und eigene `font-family`-Werte — Duplikate der Tokens
in `frontend/src/diakonos/tokens.css`. Eine Aenderung an der Marke musste an
vier Stellen nachgezogen werden, und der Dunkelmodus lief auseinander.

WAS HIER FESTGENAGELT WIRD
--------------------------
 1. Serverseitige Seiten binden die gebaute Token-Datei und ein gemeinsames
    Grund-Stylesheet ein (`anmeldung/seitenrahmen.py`), praefixbewusst.
 2. In `backend/src/**/*.py`-HTML-Vorlagen stehen KEINE Hex-/rgb()/hsl()-
    Farben und KEINE festen Schriftfamilien mehr — ausser in den dokumentierten
    Ausnahmen.
 3. Der Bestand ist in `tools/css-ssot-bestand.txt` eingefroren und darf nur
    SCHRUMPFEN: eine neue Fundstelle bricht den Test, eine behobene muss aus
    der Liste gestrichen werden (der Test meldet sonst eine zu grosse Liste).

Der Test laeuft IM Image. Dort liegt `docs/` nicht (`.dockerignore`), der
Quellbaum aber schon (`/app/backend/src`). Fehlt eine Datei, wird der
entsprechende Teil uebersprungen statt rot zu werden — die Gegenprobe im
vollstaendigen Repo macht `frontend/tests/on0a-*.test.mjs` beim Frontend-Bau.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# `backend/tests/` -> parents[1] ist `backend/`; das Repo ist eine Ebene hoeher.
BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
QUELLE = BACKEND / "src"
# ON-0b: die eingefrorene Liste fuer VUE-Quellen liegt seit ON-0b in
# `frontend/tools/` (der Rechner dazu ebenso — beide IN `frontend/`, damit der
# Image-Build sie ohne zusaetzliche COPY-Zeile sieht).
# ON-0c (R5): Diese Liste (`tools/css-ssot-bestand.txt`) gilt AUSSCHLIESSLICH
# fuer die SERVER-Seiten (`backend/src/**/*.py`). Sie steht hier, NICHT in
# `frontend/` — deshalb fehlt sie im Frontend-Stage des Images, und ein
# fehlender Bestand gilt als leer. Fuer die Backend-Pruefung ist das korrekt
# (`test_bestand_ist_leer_und_bleibt_leer` verlangt ohnehin den leeren
# Bestand); der Test `test_bestandsliste_schrumpft_und_ist_aktuell` wird im
# Image deshalb uebersprungen — im Repo laeuft er.
BESTAND = REPO / "tools" / "css-ssot-bestand.txt"

# Feste Farbe: #rgb/#rrggbb/#rrggbbaa, rgb()/rgba(), hsl()/hsla().
FARB = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(", re.IGNORECASE)
# Feste Schriftfamilie: `font-family: Inter, …`. `inherit` und `var(--…)` sind
# erlaubt — sie sind keine eigene Wahrheit, sondern erben die Token.
SCHRIFT = re.compile(r"font-family\s*:\s*(?!inherit\b|var\()", re.IGNORECASE)
# ON-0c (R2): die `font:`-Kurzschreibweise MIT Anfuehrungszeichen oder Komma
# nennt eine Schriftfamilie (`font: 12px/1.2 "Inter", sans-serif`) — genau wie
# `font-family:`. Ohne Anfuehrungszeichen/Komma ist es eine reine Groessen-
# Angabe (`font: 600 14px/1.4`) und keine eigene Schriftwahl.
SCHRIFT_KURZ = re.compile(r"\bfont\s*:[^;{}\n]*[\"',]", re.IGNORECASE)

# ON-0c (R2): Dokumentierte Ausnahme — EIN Literal, nicht die ganze Datei.
# `kalender_verwaltung.py` liefert die Kalenderfarbe als Nutzdatensatz. Der
# Wert steht seit ON-0c in `api/farbe.py`; DORT ist die Sammelstelle der
# Standardfarben, die die Oberflaeche als `style`-Wert malt (Nutzdaten, keine
# Gestaltung). Ihre Werte sind der Vertrag mit dem Frontend.
AUSNAHME_LITERALE = {
    "backend/src/diakronos_app/api/farbe.py": (
        "#667eea",
        "#3b82f6",
        "#4f7cff",
        "#ef4444",
        "#9ca3af",
        "#4285F4",
    ),
}


def _ist_html_quelle(text: str) -> bool:
    """Trägt die Datei ueberhaupt HTML/CSS, das im Browser landet?"""
    return "<html" in text or "<style" in text or "<!doctype" in text.lower()


# ON-0b (F2): Merkmale einer HTML-Zeichenkette. Bewusst breit — der Befund war,
# dass nur ganze Seiten (`<html …`) geprueft wurden und ein Bruchstueck wie
# `<p style="color:#123">` durchs Raster fiel. `style=` zaehlt deshalb mit.
_HTML_MERKMAL = re.compile(
    r"<html|<style|<!doctype|</(?:div|p|span|form|label|input|button|main|a|h[1-6])\b"
    r"|<(?:div|p|span|form|label|input|button|main|body|a)\b|\bstyle\s*=",
    re.IGNORECASE,
)


def _befunde(datei: Path) -> int:
    """Zahl der Fundstellen in einer Datei (0, wenn sie kein HTML traegt).

    ON-0c (R2) — DREI Verschaerfungen gegenueber ON-0b:

    1. Geprueft wird JEDE Datei, in der ein HTML-Merkmal ODER eine Schreibweise
       fuer Schrift/Farbe steht. Vorher fiel eine Zeichenkette ohne `<div`/
       `style=` komplett durch (`CSS = "body { font-family: Inter }"`).
    2. Auch `font:`-Kurzschreibweise mit Anfuehrungszeichen/Komma zaehlt.
    3. Die Ausnahme fuer `kalender_verwaltung.py` gilt fuer das LITERAL
       `#9ca3af` (Datendaten), nicht fuer die Datei: jedes weitere Literal in
       derselben Datei ist wieder eine Fundstelle.
    """
    quelle = datei.read_text(encoding="utf-8", errors="replace")
    # Der Ausnahme-Schluessel ist der Repo-Pfad (`backend/src/…`), nicht der
    # absolute Pfad der Datei — im Image liegt sie unter /app/backend/src.
    try:
        rel = datei.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        rel = datei.as_posix()
    # Ausnahme-Literale entfernen, BEVOR gezaehlt wird. Steht das Literal nicht
    # (mehr) in der Datei, bleibt sie unveraendert — die Ausnahme ist dann nur
    # veraltet, nie ein Freibrief fuer andere Werte.
    for marke in AUSNAHME_LITERALE.get(rel, ()):
        quelle = quelle.replace(marke, " ")
    # ON-0c (R2): HTML-Merkmal ODER eigene Schrift-/Farb-Schreibweise.
    if not (
        _HTML_MERKMAL.search(quelle)
        or SCHRIFT.search(quelle)
        or SCHRIFT_KURZ.search(quelle)
        or FARB.search(quelle)
    ):
        return 0
    return (
        len(FARB.findall(quelle))
        + len(SCHRIFT.findall(quelle))
        + len(SCHRIFT_KURZ.findall(quelle))
    )


def _hat_html_merkmale(datei: Path) -> bool:
    return bool(_HTML_MERKMAL.search(datei.read_text(encoding="utf-8", errors="replace")))


def _bestand() -> dict[str, int]:
    """Eingefrorene Fundstellen: `relativer/pfad.py<TAB>anzahl` je Zeile.

    Kommentare (`#`) und Leerzeilen werden ignoriert. Die Datei darf FEHLEN —
    dann gilt ein leerer Bestand (nichts ist erlaubt).
    """
    if not BESTAND.is_file():
        return {}
    werte: dict[str, int] = {}
    for zeile in BESTAND.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        pfad, _, zahl = zeile.partition("\t")
        werte[pfad.strip()] = int(zahl.strip() or 0)
    return werte


@pytest.mark.skipif(not QUELLE.is_dir(), reason="Quellbaum im Image nicht vorhanden")
def test_keine_neuen_farbwerte_in_server_seiten() -> None:
    """Eine Fundstelle ausserhalb des Bestands -> rot.

    Der Bestand ist die Liste der heute vorhandenen Duplikate; er darf nur
    schrumpfen (Karte ON-0a, S3).
    """
    erlaubt = _bestand()
    neue: list[str] = []
    for datei in sorted(QUELLE.rglob("*.py")):
        rel = datei.relative_to(REPO).as_posix()
        ist = _befunde(datei)
        soll = erlaubt.get(rel, 0)
        if ist > soll:
            neue.append(f"{rel}: {ist} Fundstellen (erlaubt {soll})")
    assert not neue, (
        "Neue feste Farb-/Schriftwerte in serverseitigem HTML. Farben, Schriften "
        "und Radien kommen aus tokens.css (var(--…)) bzw. dem gemeinsamen "
        "Grund-Stylesheet (anmeldung/seitenrahmen.py):\n  " + "\n  ".join(neue)
    )


@pytest.mark.skipif(not QUELLE.is_dir(), reason="Quellbaum im Image nicht vorhanden")
def test_bestand_ist_leer_und_bleibt_leer() -> None:
    """ON-0c (R2): der Bestand ist 0 — HART geprueft, nicht nur „nicht groesser".

    `test_bestandsliste_schrumpft_und_ist_aktuell` vergleicht die Liste nur mit
    sich selbst; ein Eintrag, der nie behoben wurde, bliebe damit gueltig.
    Hier steht die Zusage absolut: es gibt KEINEN Eintrag, und es darf keiner
    hinzukommen. Ein neuer Freibrief ist damit unmoeglich — auch nicht als
    „bekannter Altfall".
    """
    assert _bestand() == {}, (
        "tools/css-ssot-bestand.txt muss leer sein (Bestand 0). "
        f"Eintraege: {_bestand()}"
    )


@pytest.mark.skipif(not QUELLE.is_dir(), reason="Quellbaum im Image nicht vorhanden")
def test_ausnahme_gilt_nur_fuer_die_sammelstelle(tmp_path) -> None:
    """ON-0c (R2): Ausnahmen gelten fuer LITERALE, nie fuer ganze Dateien.

    Vorher gab `_befunde` fuer `kalender_verwaltung.py` pauschal 0 zurueck —
    eine neue Farbe darin waere unsichtbar geblieben. Jetzt gilt die Ausnahme
    fuer die dokumentierten Werte der Sammelstelle `api/farbe.py`; jedes
    WEITERE Literal dort (und jede Farbe in jeder anderen Datei) ist eine
    Fundstelle.
    """
    datei = REPO / "backend/src/diakronos_app/api/farbe.py"
    assert datei.is_file(), f"Datei fehlt: {datei}"
    assert _befunde(datei) == 0, "die dokumentierten Standardfarben wurden gezaehlt"

    original = datei.read_text(encoding="utf-8")
    probe = tmp_path / "farbe.py"
    probe.write_text(
        original.replace(
            'GOOGLE_STANDARD_FARBE = "#4285F4"',
            'GOOGLE_STANDARD_FARBE = "#4285F4"\nNEUE_FARBE = "#123456"',
        ),
        encoding="utf-8",
    )
    text_probe = probe.read_text(encoding="utf-8")
    assert 'NEUE_FARBE = "#123456"' in text_probe
    # Die Probe liegt unter tmp_path (kein Repo-Pfad) -> keine Ausnahme:
    # das neue Literal MUSS gezaehlt werden.
    assert _befunde(probe) >= 1, "eine neue Farbe in der Sammelstelle bleibt unsichtbar"

    # Und die Ausnahme greift nur fuer die Sammelstelle: dieselben Literale in
    # einer ANDEREN Datei sind Fundstellen.
    fremd = tmp_path / "andere.py"
    fremd.write_text('FARBE = "#3b82f6"\n', encoding="utf-8")
    assert _befunde(fremd) == 1, (
        "ein Literal ausserhalb der Sammelstelle wird nicht gezaehlt"
    )


@pytest.mark.skipif(not BESTAND.is_file(), reason="Bestandsliste nicht im Image")
def test_bestandsliste_schrumpft_und_ist_aktuell() -> None:
    """Behobene Fundstelle muss aus der Liste gestrichen werden.

    Sonst waere die Ausnahme ein Freibrief: eine Datei, die wieder Farben
    bekommt, bliebe unter der alten Obergrenze unauffaellig.
    """
    veraltet: list[str] = []
    for rel, soll in sorted(_bestand().items()):
        datei = REPO / rel
        if not datei.is_file():
            veraltet.append(f"{rel}: Datei fehlt (Eintrag entfernen)")
            continue
        ist = _befunde(datei)
        if ist < soll:
            veraltet.append(f"{rel}: nur noch {ist} statt {soll} (Eintrag senken/entfernen)")
    assert not veraltet, "Bestandsliste tools/css-ssot-bestand.txt ist veraltet:\n  " + "\n  ".join(
        veraltet
    )


def test_seitenrahmen_liefert_tokens_und_grund_stylesheet(monkeypatch) -> None:
    """S1: der Helfer liefert den <head>-Block mit beiden Stylesheets.

    Ohne Praefix sind die Adressen absolut ab `/`; mit Praefix tragen BEIDE
    Adressen den Praefix (WEB-5a) — das ist die einzige Stelle, an der die
    Adressen gebaut werden.
    """
    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        block = seitenrahmen.head_block()
        assert "/diakonos/assets/diakronos-tokens.css" in block
        assert "/diakonos/assets/diakronos-seiten.css" in block
        assert block.count('rel="stylesheet"') == 2

        base_path.setze_praefix("/gemeinde")
        block = seitenrahmen.head_block()
        # ON-0b (F7): hinter dem Namen steht der Cache-Buster (`?v=…`).
        assert "/gemeinde/diakonos/assets/diakronos-tokens.css" in block
        assert "/gemeinde/diakonos/assets/diakronos-seiten.css" in block
        assert "?v=" in block, "Cache-Buster fehlt hinter den Adressen"
    finally:
        base_path.setze_praefix(alt)


def test_head_block_traegt_einen_cache_buster() -> None:
    """ON-0b (F7): beide `<link>`-Adressen tragen `?v=<Inhalts-Hash>`.

    Die Dateinamen sind fest (damit Server-Seiten sie ohne Build-Hash nennen
    koennen). `no-cache` + ETag reicht dem Browser, aber nicht jedem
    Zwischenspeicher — der Versionswert macht aus jeder Aenderung eine neue
    Adresse. Er muss ein HASH sein (kein Zeitstempel: sonst wechselt jede
    Anfrage die Adresse und der Cache waere wirkungslos).
    """
    import re

    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        block = seitenrahmen.head_block()
    finally:
        base_path.setze_praefix(alt)
    versionen = re.findall(r'href="([^"?]+)\?v=([0-9a-f]{8,})"', block)
    assert len(versionen) == 2, f"Cache-Buster fehlt: {block}"
    werte = {w for _, w in versionen}
    assert len(werte) == 1, "beide Stylesheets muessen DENSELBEN Versionswert tragen"
    assert seitenrahmen.versions_hash() in werte, "der Versionswert ist kein Inhalts-Hash"


def test_seitenrahmen_setzt_das_theme(monkeypatch) -> None:
    """Hell/Dunkel auf Server-Seiten (REG-1c, dieselbe Regel wie die SPA).

    `tokens.css` kennt dunkle Werte NUR unter `[data-theme="dark"]`; ohne
    diesen Schritt blieb die Anmeldung auf einem dunkel eingestellten Gerät
    hell (bei der Abnahme gemessen).
    """
    from diakronos_app.anmeldung import seitenrahmen

    block = seitenrahmen.head_block()
    assert 'name="color-scheme"' in block
    assert "prefers-color-scheme: dark" in block
    assert "dk-theme" in block, "Theme-Wahl aus dem Speicher wird nicht gelesen"
    assert "data-theme" in block, "das Merkmal am <html> wird nicht gesetzt"
    # Kein Umschalter auf einer oeffentlichen Seite.
    assert "button" not in block.lower()


def test_seiten_sind_ohne_eigene_farbwerte(monkeypatch) -> None:
    """S2: die ausgelieferten Seiten tragen keine Hex-/rgb()-Werte mehr."""
    from diakronos_app import base_path
    from diakronos_app.anmeldung import passwortseite, routen
    from diakronos_app.spa import render_login

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        seiten = {
            "anmeldung": routen.erstelle_anmeldeseite("/diakonos"),
            "spa-login": render_login("/diakonos"),
            "passwort": bytes(passwortseite.passwort_seite().body).decode("utf-8"),
            "fehlerseite": bytes(routen._fehler_seite("Test").body).decode("utf-8"),
        }
        for name, seite in seiten.items():
            assert not FARB.findall(seite), f"{name}: feste Farbwerte im HTML"
            assert not SCHRIFT.findall(seite), f"{name}: feste Schriftfamilie im HTML"
            assert "diakronos-tokens.css" in seite, f"{name}: Token-Datei fehlt"
            assert "diakronos-seiten.css" in seite, f"{name}: Grund-Stylesheet fehlt"
    finally:
        base_path.setze_praefix(alt)


# ── Auslieferung: die Dateien muessen wirklich erreichbar sein ──────────────


def _build_hat_ssot() -> bool:
    """Liegt der Frontend-Build mit den beiden stabilen Dateien vor?"""
    from diakronos_app.spa import SPA_DIST

    if SPA_DIST is None:
        return False
    return all((SPA_DIST / name).is_file() for name in ("diakronos-tokens.css", "diakronos-seiten.css"))


# ON-0b (F4): Der Auslieferungstest HIER lief nie — er nannte die Datei
# "diakonos-seiten.css" (fehlendes "r") und wurde deshalb stillschweigend
# übersprungen. Der Name kommt jetzt aus `spa.py` (eine Wahrheit); der Skip
# gilt nur noch für "kein Build". Im Image MUSS der Test laufen — das
# erzwingt `test_on0b_schriften.py::test_auslieferungstest_laeuft_im_image`.


@pytest.mark.skipif(not _build_hat_ssot(), reason="Kein Frontend-Build mit den SSOT-Dateien")
def test_ssot_stylesheets_werden_ausgeliefert(fake_redis) -> None:
    """S1: beide Dateien kommen unter `/diakonos/assets/…` an.

    `no-cache` statt `immutable`: die Namen sind fest, eine Änderung an der
    Marke muss wiederkehrende Besucher erreichen (`_asset_response`).
    """
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    with TestClient(app) as client:
        from diakronos_app.spa import SEITENRAHMEN_STIL, SEITENRAHMEN_TOKENS

        for name in (SEITENRAHMEN_TOKENS, SEITENRAHMEN_STIL):
            antwort = client.get(f"/diakonos/assets/{name}")
            assert antwort.status_code == 200, f"{name}: HTTP {antwort.status_code}"
            assert "css" in antwort.headers.get("content-type", "")
            assert "immutable" not in antwort.headers.get("cache-control", "")
            assert "no-cache" in antwort.headers.get("cache-control", "")

        token_css = client.get("/diakonos/assets/diakronos-tokens.css").text
        # Der Beweis, dass die ECHTE Token-Datei kam (und nicht eine leere Hülle).
        assert "--dk-navy-500" in token_css
        assert "--font" in token_css

        seiten_css = client.get("/diakonos/assets/diakronos-seiten.css").text
        assert ".dk-karte" in seiten_css
        assert ".dk-knopf" in seiten_css
        assert FARB.findall(seiten_css) == [], "Grund-Stylesheet traegt feste Farbwerte"
