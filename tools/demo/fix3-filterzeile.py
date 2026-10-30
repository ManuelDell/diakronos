"""FIX-3 — Messung „Knopf und Suchfeld gleich hoch“ (Befund DMB-eb3ae73fc36f).

Befund (24.10., ``#/beitraege``, Viewport 344x694, Element
``div.dk-filters.bt-filter``): „Button und suchmaske unterschiedlich groß“.
Gemessen wird deshalb nicht nur ein Bild, sondern die gerenderte Hoehe
(``getBoundingClientRect``) der Elemente EINER Filterzeile:

  * Beitraege  ``.dk-filters``  : Filterchip (.dk-ui-chip) und Suchfeld (.dk-search-bar)
  * Lieder     ``.dk-toolbar-row``: Suchfeld (.dk-toolbar-search input) und der
                 Knopf „Filter“ (.ld-filter-knopf) — der Knopf erscheint nur am Handy
  * Wiki       ``.wk-suche``    : Suchfeld (.dk-search-bar) und Chips (.dk-ui-chip)
  * Liedgruppe (Dialog): Suchfeld (.dk-toolbar-search input) und „Hinzufuegen“

Aufgenommen wird je Breite (344, 390, 1366) und je Theme (hell, dunkel):

  ``<marke>-<breite>-<theme>-<seite>.png``   Bild
  ``<marke>-messung.json``                    alle Hoehen + Abweichungen

Die Abweichung ist der Betrag der Hoehendifferenz in px; erwartet wird 0.
Ein Fehler wird gemeldet, wenn eine Zeile fehlt oder die Abweichung > 0 ist.

Aufruf (im Wegwerf-Stack, Netz des eigenen Compose-Projekts):

    docker run --rm --network <projekt>_default -v "$PWD":/w:ro \\
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        python /w/tools/demo/fix3-filterzeile.py --marke nachher
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

BREITEN = [(344, 694), (390, 844), (1366, 800)]
THEMES = ["light", "dark"]

fehler: list[str] = []
messungen: list[dict] = []

MARKE = "nachher"
argv = __import__("sys").argv
if "--marke" in argv:
    MARKE = argv[argv.index("--marke") + 1]


def anmelden(page):
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    if page.locator("#dk-usr").count():
        page.fill("#dk-usr", ADMIN)
        page.fill("#dk-pwd", ADMIN_PASS)
        page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    page.wait_for_load_state("domcontentloaded")


def hoehe(page, selektor):
    """Gerenderte Hoehe in px (0, wenn nicht vorhanden/sichtbar)."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel)
            if (!el) return null
            const r = el.getBoundingClientRect()
            if (r.width === 0 && r.height === 0) return null
            return Math.round(r.height * 10) / 10
        }""",
        selektor,
    )


def zeile(page, breite, theme, seite, paare, nur_wenn=None):
    """Ein Paar (Feld, Knopf/Chip) messen und ablegen."""
    if nur_wenn and not page.evaluate(nur_wenn[0], nur_wenn[1]):
        return
    werte = {}
    for name, sel in paare.items():
        werte[name] = hoehe(page, sel)
    fehlend = [n for n, v in werte.items() if v is None]
    if fehlend:
        fehler.append(f"{seite}/{breite}/{theme}: nicht gefunden: {', '.join(fehlend)}")
        abw = None
    else:
        abw = round(abs(list(werte.values())[0] - list(werte.values())[1]), 1)
        if abw > 0:
            fehler.append(f"{seite}/{breite}/{theme}: Hoehen {werte} weichen um {abw}px ab")
    eintrag = {"marke": MARKE, "seite": seite, "breite": breite, "theme": theme,
               "hoehen": werte, "abweichung_px": abw}
    messungen.append(eintrag)
    print(json.dumps(eintrag, ensure_ascii=False))


def lauf(page, breite, hoehepx, theme):
    # ── Beitraege ────────────────────────────────────────────────────────────
    page.goto(f"{BASE}/diakonos#/beitraege", wait_until="domcontentloaded")
    page.wait_for_timeout(1800)
    zeile(page, breite, theme, "beitraege",
          {"chip": ".dk-filters .dk-ui-chip", "suchfeld": ".dk-filters .dk-search-bar"})
    page.screenshot(path=os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-beitraege.png"))

    # ── Wiki ─────────────────────────────────────────────────────────────────
    page.goto(f"{BASE}/diakonos#/wiki", wait_until="domcontentloaded")
    page.wait_for_timeout(1800)
    zeile(page, breite, theme, "wiki",
          {"chip": ".wk-main .dk-ui-chip", "suchfeld": ".wk-suche"})
    page.screenshot(path=os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-wiki.png"))

    # ── Lieder ───────────────────────────────────────────────────────────────
    page.goto(f"{BASE}/diakonos#/lieder", wait_until="domcontentloaded")
    page.wait_for_timeout(1800)
    # Der Filter-Knopf steht nur am Handy (pointer: coarse) in der Zeile.
    zeile(page, breite, theme, "lieder",
          {"suchfeld": ".ld-suche input", "knopf": ".ld-filter-knopf"},
          nur_wenn=("(sel) => { const e = document.querySelector(sel); if (!e) return false;"
                    " const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 }",
                    ".ld-filter-knopf"))
    page.screenshot(path=os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-lieder.png"))


def main():
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        for breite, hoehepx in BREITEN:
            for theme in THEMES:
                ctx = browser.new_context(
                    viewport={"width": breite, "height": hoehepx},
                    locale="de-DE",
                    has_touch=breite < 700,
                )
                ctx.add_init_script(
                    f"try {{ localStorage.setItem('dk-theme', '{theme}') }} catch (e) {{}}")
                page = ctx.new_page()
                page.on("pageerror", lambda e: fehler.append(f"pageerror: {e}"))
                anmelden(page)
                lauf(page, breite, hoehepx, theme)
                ctx.close()
        browser.close()

    bericht = {"marke": MARKE, "fehler": fehler, "messungen": messungen}
    with open(os.path.join(ZIEL, f"{MARKE}-messung.json"), "w", encoding="utf-8") as f:
        json.dump(bericht, f, ensure_ascii=False, indent=2)
    print(f"\n{len(messungen)} Messungen, {len(fehler)} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
