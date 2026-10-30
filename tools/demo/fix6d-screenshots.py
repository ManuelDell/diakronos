"""FIX-6d — Screenshots + Messung der Umbruchstellen.

Läuft im Playwright-Abbild (Python). Aufruf:

    BASE=http://fix6d-abnahme-app-1:8000
    ZIEL=/ausgabe/nachher MARKER=nachher
    ADMIN_EMAIL=admin@example.org ADMIN_PASS=musterhausen-demo

Gemessen wird zusätzlich, was die 640px-Regeln tatsächlich tun:
* überläuft die Seite waagerecht? (scrollWidth vs. innerWidth)
* ist der App-Rahmen ab 720 mobil? (Seitenleiste sichtbar / nicht)
* bei 640 vs. 660: greift der Inhaltsumbruch genau an der Grenze?
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")

BREITEN = [
    ("1366", 1366, 900),
    ("700", 700, 900),
    ("640", 640, 900),
    ("390", 390, 844),
]

SEITEN = [
    ("start", "/#/"),
    ("mitglieder", "/#/mitglieder"),
    ("kalender", "/#/kalender"),
    ("ressourcen", "/#/ressourcen"),
    ("anfragen", "/#/mitglieder/anfragen"),
    ("planrahmen", "/#/planrahmen"),
    ("meine-dienste", "/#/planrahmen/meine-dienste"),
]

MESSUNG = """() => {
  const sb = document.querySelector('.dk-sidebar')
  const nav = document.querySelector('.dk-bottom-nav, [class*=bottom-nav]')
  return {
    scroll: document.documentElement.scrollWidth,
    innen: window.innerWidth,
    sidebarSichtbar: !!sb && getComputedStyle(sb).display !== 'none',
    untenLeiste: !!nav && getComputedStyle(nav).display !== 'none',
  }
}"""


def main():
    os.makedirs(ZIEL, exist_ok=True)
    befunde = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        page = ctx.new_page()

        page.goto(BASE + "/#/", wait_until="networkidle")
        feld = page.locator('input[name="usr"], #dk-usr')
        if feld.count():
            feld.first.fill(EMAIL)
            page.fill('input[name="pwd"], #dk-pwd', PASSWORT)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

        for thema in ("hell", "dunkel"):
            for name, breite, hoehe in BREITEN:
                page.set_viewport_size({"width": breite, "height": hoehe})
                for seite, pfad in SEITEN:
                    page.evaluate(
                        "(t) => localStorage.setItem('dk-theme', t)", "dark" if thema == "dunkel" else "light"
                    )
                    page.goto(BASE + pfad, wait_until="networkidle")
                    page.wait_for_timeout(1000)
                    page.evaluate(
                        "(t) => document.documentElement.setAttribute('data-theme', t)",
                        "dark" if thema == "dunkel" else "light",
                    )
                    page.wait_for_timeout(400)
                    m = page.evaluate(MESSUNG)
                    m.update(seite=seite, breite=breite, thema=thema)
                    if m["scroll"] - m["innen"] > 1:
                        befunde.append(m)
                        print(f"UEBERLAUF {seite} @{breite} {thema}: {m['scroll'] - m['innen']}px")
                    datei = os.path.join(ZIEL, f"{MARKER}-{seite}-{name}-{thema}.png")
                    page.screenshot(path=datei, full_page=False)
                    print("BILD " + datei)

        # Grenzmessung: Inhaltsumbruch 645 -> 640 am Kartenraster (Ressourcen,
        # dort ist `.dk-card-grid` ohne die -sm-Variante im Einsatz).
        grenze = []
        for breite in (660, 645, 644, 640, 635):
            page.set_viewport_size({"width": breite, "height": 900})
            page.goto(BASE + "/#/ressourcen", wait_until="networkidle")
            page.wait_for_timeout(900)
            spalten = page.evaluate(
                """() => {
                  const g = document.querySelector('.dk-card-grid')
                  if (!g) return null
                  const s = getComputedStyle(g).gridTemplateColumns
                  return { spalten: s, anzahl: s.split(' ').filter(Boolean).length }
                }"""
            )
            grenze.append({"breite": breite, **(spalten or {})})
            print(f"RASTER @{breite}: {spalten}")

        browser.close()

    with open(os.path.join(ZIEL, "messung.json"), "w", encoding="utf-8") as f:
        json.dump({"ueberlauf": befunde, "raster": grenze}, f, ensure_ascii=False, indent=2)
    print(f"FERTIG ueberlauf={len(befunde)}")
    return 3 if befunde else 0


if __name__ == "__main__":
    sys.exit(main())
