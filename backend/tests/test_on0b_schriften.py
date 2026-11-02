"""ON-0b (F3) — Schriften der Server-Seiten müssen wirklich ankommen.

DER BEFUND
----------
`frontend/vite.config.mjs` setzte die `@import`-Zeilen von `tokens.css`
wörtlich in die ausgelieferte `diakronos-tokens.css`, ließ aber die `url()`-
Angaben von `@fontsource/inter` unverändert: `url(./files/inter-latin-400-normal.woff2)`.
Unter `/diakonos/assets/files/…` gibt es diese Datei nicht — die Anfrage
lief in den Catch-all, der „keine Datei" als *Seite* deutet und die
Anmeldeschranke antwortet (HTML statt Schrift). Ergebnis: Anmeldung und
Passwort-Seite standen in der Systemschrift.

WAS HIER FESTGENAGELT WIRD
--------------------------
 1. Der Build benennt die Schriften NACH DER QUELLE und legt sie in
    `dist/schriften/` (`SCHRIFT_ORDNER` in `vite.config.mjs`).
 2. Jede `url()` der ausgelieferten Server-Stylesheets zeigt auf eine
    ausgelieferte Datei und liefert 200 mit Typ `font/woff2` — mit und ohne
    `DIAKRONOS_BASE_PATH`.
 3. Die Adressen stehen VOR der Anmeldeschranke (sonst kommt HTML statt
    Schrift).
 4. Die CSP der Passwort-Seite erlaubt `font-src 'self'`.
 5. Ohne Build warnt der Start (F6).

Läuft IM Image (dort liegt der Build unter /app/frontend/dist). Fehlt der
Build, wird der Auslieferungsteil ÜBERSPRUNGEN — die Quelltext-Prüfungen
laufen immer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def setze_setting(name: str, wert: str) -> None:
    """Eine Einstellung für die Dauer des Tests setzen (WEB-5a)."""
    from diakronos_app.settings import settings

    setattr(settings, name, wert)
REPO = BACKEND.parent
VITE = REPO / "frontend" / "vite.config.mjs"
TOKENS = REPO / "frontend" / "src" / "diakonos" / "tokens.css"


# ── 1 · Der Build schreibt die Schriften unter festen Namen ────────────────


def test_build_legt_schriften_unter_festem_namen_ab() -> None:
    """Der Vite-Plugin gibt jede gebrauchte Schrift als eigenes Asset aus."""
    assert VITE.is_file(), f"vite.config.mjs fehlt ({VITE})"
    text = VITE.read_text(encoding="utf-8")
    assert "SCHRIFT_ORDNER" in text, "kein Schriftordner im Build"
    assert re.search(r"SCHRIFT_ORDNER\s*=\s*'[a-z]+'", text), "Schriftordner ohne festen Namen"
    # Die Datei wird mit dem Namen aus der QUELLE ausgegeben (kein Umbenennen).
    assert "path.basename(" in text, "der Schriftname kommt nicht aus der Quelle"
    assert "emitFile(" in text and "schriften" in text, "Schriften werden nicht ausgegeben"


def test_tokens_css_bindet_schriften_nur_ueber_fontsource_ein() -> None:
    """Die Quelle bleibt `tokens.css` — hier wird nur gelesen, nichts kopiert."""
    assert TOKENS.is_file(), f"tokens.css fehlt ({TOKENS})"
    text = TOKENS.read_text(encoding="utf-8")
    assert "@fontsource/inter/latin-400.css" in text
    assert "--font:" in text


# ── 2 · Die Adresse baut seitenrahmen (präfixbewusst) ─────────────────────


def test_schrift_adresse_ist_praefixbewusst() -> None:
    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        adresse = seitenrahmen.schrift_url("inter-latin-400-normal.woff2")
        assert adresse == "/diakonos/assets/schriften/inter-latin-400-normal.woff2"

        base_path.setze_praefix("/gemeinde")
        adresse = seitenrahmen.schrift_url("inter-latin-400-normal.woff2")
        assert adresse == "/gemeinde/diakonos/assets/schriften/inter-latin-400-normal.woff2"
    finally:
        base_path.setze_praefix(alt)


def test_passwortseite_erlaubt_schriften() -> None:
    """Ohne `font-src 'self'` blockt `default-src 'none'` die Schriftdatei."""
    from diakronos_app.anmeldung import passwortseite

    kopf = passwortseite.passwort_seite().headers
    csp = kopf.get("content-security-policy", "")
    assert "font-src 'self'" in csp, f"font-src fehlt in der CSP: {csp}"
    assert "style-src 'self'" in csp, f"style-src fehlt in der CSP: {csp}"


# ── 3 · Die Dateien kommen aus dem Build (Auslieferung) ───────────────────


def _build_hat_schriften() -> bool:
    from diakronos_app.spa import SEITENRAHMEN_SCHRIFT_NAMEN, SPA_DIST, SEITENRAHMEN_SCHRIFTEN

    if SPA_DIST is None:
        return False
    ordner = SPA_DIST / SEITENRAHMEN_SCHRIFTEN
    return ordner.is_dir() and all((ordner / n).is_file() for n in SEITENRAHMEN_SCHRIFT_NAMEN)


def _css_urls(text: str) -> list[str]:
    """Alle `url(…)`-Angaben eines Stylesheets (ohne `data:`/`http`)."""
    treffer = []
    for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", text):
        ziel = m.group(1).strip()
        if ziel.startswith(("data:", "http:", "https:")):
            continue
        treffer.append(ziel)
    return treffer


@pytest.mark.skipif(not _build_hat_schriften(), reason="Kein Frontend-Build mit Schriften")
def test_alle_schrift_urls_der_server_stylesheets_liefern_200(fake_redis) -> None:
    """Kernbeweis von F3: JEDE url() führt zu einer echten Datei vom Typ font/*.

    Geprüft wird über HTTP (nicht über das Dateisystem): nur so ist belegt,
    dass die Adresse VOR der Anmeldeschranke liegt und der Typ stimmt.

    Zwei Läufe — OHNE Präfix (`/diakonos/assets/…`) und MIT Betriebs-Präfix
    (`/gemeinde/…`). Der Präfix wird beim BAU der Anwendung gesetzt
    (`setze_setting` + `erstelle_app`), nicht nur am Helfer: nur so landen die
    Routen wirklich unter dem Präfix (WEB-5a).
    """
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.anmeldung import seitenrahmen
    from diakronos_app.main import erstelle_app

    def _pruefe(client, praefix: str) -> None:
        for stylesheet in (seitenrahmen.tokens_url(), seitenrahmen.seiten_url()):
            assert stylesheet.startswith(praefix), f"{stylesheet}: Präfix fehlt"
            antwort = client.get(stylesheet)
            assert antwort.status_code == 200, f"{stylesheet}: HTTP {antwort.status_code}"
            if stylesheet != seitenrahmen.tokens_url():
                # Das Grund-Stylesheet trägt keine eigene Schriftquelle.
                continue
            urls = _css_urls(antwort.text)
            assert urls, f"{stylesheet}: keine url()-Angaben — Schrift verloren?"
            for ziel in urls:
                adresse = (
                    ziel if ziel.startswith("/")
                    else f"{stylesheet.rsplit('/', 1)[0]}/{ziel[2:] if ziel.startswith('./') else ziel}"
                )
                antwort_schrift = client.get(adresse)
                assert antwort_schrift.status_code == 200, (
                    f"{adresse}: HTTP {antwort_schrift.status_code} "
                    f"(Anmeldeschranke statt Schrift?)"
                )
                typ = antwort_schrift.headers.get("content-type", "")
                erwartet = "font/woff2" if ziel.endswith(".woff2") else "font/woff"
                assert typ.startswith(erwartet), f"{adresse}: Typ {typ!r}"
                signatur = antwort_schrift.content[:4]
                assert signatur in (b"wOF2", b"wOFF"), (
                    f"{adresse}: keine Schriftdatei (Signatur {signatur!r})"
                )

    alt = base_path.aktiver_praefix()
    try:
        setze_setting("diakronos_base_path", "")
        base_path.setze_praefix("")
        with TestClient(erstelle_app()) as client:
            _pruefe(client, "")

        setze_setting("diakronos_base_path", "/gemeinde")
        try:
            with TestClient(erstelle_app()) as client:
                _pruefe(client, "/gemeinde")
        finally:
            setze_setting("diakronos_base_path", "")
    finally:
        base_path.setze_praefix(alt)


@pytest.mark.skipif(not _build_hat_schriften(), reason="Kein Frontend-Build mit Schriften")
def test_spa_stylesheet_schriften_finden_ihre_datei(fake_redis) -> None:
    """Auch die SPA lädt ihre Schrift über `css/<hash>.css` → 200, nicht 302/HTML.

    Die SPA bindet das gebündelte Stylesheet unter `/diakonos/assets/css/…`
    ein; die `url()`-Angaben darin sind relativ zu `css/`. Ausgeliefert werden
    muss die Schrift deshalb UNTER `assets/css/` — sonst löst der Browser
    `/diakonos/assets/<name>-<hash>.woff2` auf, was eine unbekannte Seite ist.
    """
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.main import app
    from diakronos_app.spa import SPA_DIST

    assert SPA_DIST is not None
    css_dateien = sorted((SPA_DIST / "css").glob("*.css"))
    assert css_dateien, "kein gebündeltes Stylesheet unter dist/css"
    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        with TestClient(app) as client:
            for datei in css_dateien:
                antwort = client.get(f"/diakonos/assets/css/{datei.name}")
                assert antwort.status_code == 200, f"{datei.name}: HTTP {antwort.status_code}"
                for ziel in _css_urls(antwort.text):
                    if not ziel.startswith("./"):
                        continue
                    adresse = f"/diakonos/assets/css/{ziel[2:]}"
                    schrift = client.get(adresse)
                    assert schrift.status_code == 200, (
                        f"{adresse}: HTTP {schrift.status_code} (SPA-Schrift nicht erreichbar)"
                    )
                    assert "woff" in schrift.headers.get("content-type", "")
    finally:
        base_path.setze_praefix(alt)


# ── 4 · F4: der Auslieferungstest aus ON-0a läuft wirklich ────────────────


def test_auslieferungstest_laeuft_im_image() -> None:
    """F4: `test_ssot_stylesheets_werden_ausgeliefert` darf nicht übersprungen werden.

    Er stand in `test_on0a_css_ssot.py` und nannte die Datei
    „diakonos-seiten.css" (fehlendes „r") — der Skip griff deshalb IMMER, und
    kein Lauf hat die Auslieferung je geprüft. Dieser Test schlägt an, sobald
    die Voraussetzung wieder fehlt: er verlangt, dass der Build im Image da
    ist UND dass der ON-0a-Test ohne `skipif` läuft.

    Fehlt der Build (Worktree ohne `npm run build`), wird der INHALT
    übersprungen — im Image ist er Pflicht (dort liegt `/app/frontend/dist`).
    """
    quelle = (BACKEND / "tests" / "test_on0a_css_ssot.py").read_text(encoding="utf-8")
    # Der Tippfehler stand in der Prüfung selbst (`build/` statt `spa.py`):
    # gesucht wird die Zeichenkette im CODE, nicht im erklärenden Kommentar.
    code = "\n".join(
        zeile for zeile in quelle.splitlines() if not zeile.lstrip().startswith("#")
    )
    assert "diakonos-seiten.css" not in code, (
        "Tippfehler im Dateinamen ist zurück — der Test würde wieder übersprungen"
    )
    assert "diakronos-seiten.css" in quelle
    if not _build_hat_schriften():
        pytest.skip("Kein Frontend-Build in diesem Lauf (im Image Pflicht)")
    # Der Lauf ist da -> der ON-0a-Auslieferungstest muss ausführbar sein.
    from diakronos_app.spa import SEITENRAHMEN_STIL, SEITENRAHMEN_TOKENS, SPA_DIST

    assert SPA_DIST is not None
    for name in (SEITENRAHMEN_TOKENS, SEITENRAHMEN_STIL):
        assert (SPA_DIST / name).is_file(), f"{name} fehlt im Build"
    # Und er läuft wirklich durch (nicht: „skip").
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    with TestClient(app) as client:
        for name in (SEITENRAHMEN_TOKENS, SEITENRAHMEN_STIL):
            antwort = client.get(f"/diakonos/assets/{name}")
            assert antwort.status_code == 200, f"{name}: HTTP {antwort.status_code}"
            assert "no-cache" in antwort.headers.get("cache-control", "")
            assert "immutable" not in antwort.headers.get("cache-control", "")


# ── 5 · F6: ohne Build wird gewarnt ───────────────────────────────────────


def test_ohne_build_wird_beim_start_gewarnt(caplog, monkeypatch) -> None:
    from diakronos_app import frontend_build, spa

    monkeypatch.setattr(spa, "SPA_DIST", None)
    with caplog.at_level("WARNING", logger="diakronos_app.frontend_build"):
        assert frontend_build.pruefe() is False
    assert any("Frontend-Build fehlt" in r.getMessage() for r in caplog.records), (
        "ohne Build fehlt die Warnung"
    )
    assert "Gestaltung" in spa.FRONTEND_FEHLT_MELDUNG


def test_unvollstaendiger_build_wird_erkannt(caplog, monkeypatch, tmp_path) -> None:
    """Ein Build ohne die beiden Server-Stylesheets ist genauso unbrauchbar."""
    from diakronos_app import frontend_build, spa

    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)
    with caplog.at_level("WARNING", logger="diakronos_app.frontend_build"):
        assert frontend_build.pruefe() is False
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "diakronos-tokens.css" in text, f"fehlende Dateien nicht benannt: {text}"
    assert frontend_build.main() == 0, "die Pruefung darf den Start nie abbrechen"


# ── 6 · F2: der Backend-Scan sieht auch Bruchstuecke (style=) ─────────────


def test_backend_scan_prueft_auch_html_bruchstuecke(tmp_path) -> None:
    """F2: nicht nur Dateien mit `<html`, sondern JEDE Zeichenkette mit HTML.

    Befund: `_ist_html_quelle` verlangte `<html`, `<style` oder `<!doctype`.
    Eine Vorlage, die nur ein Bruchstueck ausgibt (`<p style="color:#123">`),
    wurde damit NIE geprueft.
    """
    import importlib.util

    pfad = BACKEND / "tests" / "test_on0a_css_ssot.py"
    spec = importlib.util.spec_from_file_location("on0a_waechter", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    assert modul._HTML_MERKMAL.search('<p style="color:#123">x</p>'), (
        "ein Bruchstueck mit style= wird nicht als HTML erkannt"
    )
    assert modul._HTML_MERKMAL.search("<div class='a'>"), "Bruchstueck ohne <html wird nicht erkannt"
    assert not modul._HTML_MERKMAL.search("x = 1  # nur Python"), "reiner Python-Code gilt als HTML"

    # Und im ECHTEN Quellbaum: eine Vorlage mit Bruchstueck + Farbe faellt auf.
    # (Geschrieben wird im tmp-Pfad — das Image ist zur Testzeit nur lesbar.)
    probe = tmp_path / "vorlage_mit_bruchstueck.py"
    probe.write_text('HTML = \'<p style="color:#123456">x</p>\'\n', encoding="utf-8")
    assert modul._befunde(probe) >= 1, "Bruchstueck mit Farbwert wird nicht gezaehlt"
    ohne = tmp_path / "reiner_code.py"
    ohne.write_text("x = 1\n", encoding="utf-8")
    assert modul._befunde(ohne) == 0, "reiner Python-Code gilt als HTML-Vorlage"


# ── 7 · F5: Schriftgroessen der Server-Seiten bleiben (mindestens) so gross ──

# Vorher (ON-0a-Basis): Label 13 px, Unterzeile 14 px, Eingabe 15 px,
# Hinweis 12 px. Diese vier Werte sind die Untergrenze.
# ON-0c (R1): dazu die drei Restrollen der Server-Seiten — Knopf war 14 px
# (--fs), Meldung 12 px (--fs-sm), Titel 19 px (--fs-h2); der Fliesstext der
# Passwort-Seite stand mit 14 px. Sie waren also KLEINER als vor ON-0a, und
# diese Tabelle ist die Untergrenze.
MINIMUM = {
    "--fs-feld": 13,
    "--fs-unterzeile": 14,
    "--fs-eingabe": 15,
    "--fs-hinweis": 12,
    "--fs-knopf": 15,
    "--fs-meldung": 14,
    "--fs-titel": 20,
    "--fs-fliess": 16,
}


def _tokens_px() -> dict[str, float | None]:
    """Wert (px) der vier Rollen-Tokens aus tokens.css; None = nicht definiert."""
    import re as _re

    text = TOKENS.read_text(encoding="utf-8")
    werte: dict[str, float | None] = {}
    for name in MINIMUM:
        m = _re.search(rf"{_re.escape(name)}\s*:\s*([0-9.]+)(px|rem)", text)
        if not m:
            werte[name] = None
            continue
        zahl = float(m.group(1))
        werte[name] = zahl * 16 if m.group(2) == "rem" else zahl
    return werte


def test_keine_schrift_der_anmeldung_wird_kleiner() -> None:
    """F5: die vier Rollen-Tokens stehen in tokens.css und sind nicht kleiner."""
    werte = _tokens_px()
    fehlend = [n for n, v in werte.items() if v is None]
    assert not fehlend, f"Rollen-Tokens fehlen in tokens.css: {fehlend}"
    kleiner = {n: (werte[n], MINIMUM[n]) for n in MINIMUM if werte[n] < MINIMUM[n]}
    assert not kleiner, f"Schrift waere kleiner als vorher (ist, soll): {kleiner}"


def test_seiten_stylesheet_nutzt_die_rollen_tokens() -> None:
    """F5: das Grund-Stylesheet bindet die Rollen-Tokens ein (keine Zahlen)."""
    text = (REPO / "frontend" / "src" / "ssot" / "seiten.css").read_text(encoding="utf-8")
    assert ".dk-feld" in text and "var(--fs-feld)" in text
    assert "var(--fs-eingabe)" in text
    assert "var(--fs-hinweis)" in text
    # ON-0c (R1): die drei Restrollen — und der Fliesstext statt der Unterzeile.
    assert "var(--fs-knopf)" in text, "Knopf nutzt keine eigene Rolle"
    assert "var(--fs-meldung)" in text, "Meldung nutzt keine eigene Rolle"
    assert "var(--fs-titel)" in text, "Ueberschrift nutzt keine eigene Rolle"
    assert "var(--fs-fliess)" in text, "Fliesstext nutzt keine eigene Rolle"
    # Die alten, zu kleinen Zuordnungen sind weg (Groesse kommt aus der Rolle,
    # nicht aus dem allgemeinen Token).
    for eigenschaft, alt in (
        ("h1", "var(--fs-h2)"),
        (".dk-knopf", "var(--fs)"),
        (".dk-meldung", "var(--fs-sm)"),
    ):
        block = text.split(eigenschaft, 1)[1].split("}", 1)[0]
        assert f"font-size: {alt};" not in block, (
            f"{eigenschaft} nutzt weiter die allgemeine Groesse {alt}"
        )
    # Und im groben Zeiger weiterhin 16 px gegen den iOS-Zoom.
    assert "var(--fs-in-zeiger)" in text
    # Der iOS-Kommentar steht bei SEINER Regel (F7): im `:root`-Block (der nur
    # `color-scheme` und die Theme-Regeln traegt) hat er nichts zu suchen.
    wurzel = text[text.index(":root {"):text.index(":root[data-theme=\"dark\"]")]
    assert "iOS-Safari zoomt" not in wurzel, "iOS-Kommentar steht wieder am `:root`"
    assert "iOS-Safari zoomt" in text.split("@media (pointer: coarse)")[0][-1200:], (
        "iOS-Kommentar steht nicht bei der Regel, die er erklaert"
    )


def test_anmeldeseite_hat_den_weg_zur_startseite() -> None:
    """ON-0b: Nach dem Abmelden landet man auf /login — die Seite war eine Sackgasse.

    Geprueft wird der Server-Render (ohne Browser): die Seite traegt einen
    Verweis auf die (praefixbewusste) Startseite; bei der Fehlermeldung nach
    einem Fehlversuch (`no_redirect=True`) steht er NICHT (dort ist das
    Formular der naechste Schritt).
    """
    from diakronos_app import base_path
    from diakronos_app.anmeldung import routen

    alt = base_path.aktiver_praefix()
    try:
        base_path.setze_praefix("")
        seite = routen.erstelle_anmeldeseite("/diakonos")
        assert 'href="/diakonos"' in seite and "Zur Startseite" in seite, (
            "Anmeldeseite ohne Weg zur Startseite"
        )
        base_path.setze_praefix("/gemeinde")
        seite = routen.erstelle_anmeldeseite("/gemeinde/diakonos")
        assert 'href="/gemeinde/diakonos"' in seite, "Verweis ignoriert den Praefix"
        fehler = routen.erstelle_anmeldeseite("/diakonos", no_redirect=True)
        assert "Zur Startseite" not in fehler, "Fehlermeldung traegt unnoetigen Verweis"
    finally:
        base_path.setze_praefix(alt)
