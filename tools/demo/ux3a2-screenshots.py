"""UX3a2 — Screenshots der Navigation (Liedgruppen-Weiterleitung, Moderatoren,
Gäste-Sichtbarkeit, Tokens).

Läuft im Playwright-Image gegen einen Wegwerf-Stack mit den Demo-Daten
(Musterhausen). Aufgenommen werden die Stellen, die UX3a2 berührt:

* die Weiterleitung `#/liedgruppen/‹id›` → `#/lieder/gruppen/‹id›`
  (Adresszeile nach dem Laden = Beleg, dass die Seite öffnet),
* „Zu prüfen“ (`#/kalender/pruefen`) als Kalender-Reiter,
* die Gäste-Sicht (untere Leiste + „Mehr“-Blatt ohne „Dienste“),
* die Zähler-Marke am Reiter „Zu prüfen“ und die Seitenleiste mit den
  Gruppen-Überschriften (Abstand --sp-2),

je Desktop (1440×900) und Mobil (390×844), hell und dunkel.

Aufruf (Netz des eigenen Compose-Projekts, nie der Betrieb)::

    docker run --rm --network ux3a2_default \
        -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e MARKER=nachher \
        -e ADMIN_PASS=musterhausen-demo -e GAST_PASS=... \
        -e LIEDGRUPPE=<kennung> \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux3a2-screenshots.py

Die Bilder sind Abnahme-Belege, keine Veröffentlichung: erfundene Demo-Daten.
"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
GAST_EMAIL = os.environ.get("GAST_EMAIL", "")
GAST_PASS = os.environ.get("GAST_PASS", "")
LIEDGRUPPE = os.environ.get("LIEDGRUPPE", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

fehler: list[str] = []

# (Name, Adresse) — Seiten, die UX3a2 berührt.
SEITEN = [
    ("01-uebersicht-seitenleiste", "#/"),
    ("02-kalender-pruefen", "#/kalender/pruefen"),
    ("03-lieder-gruppen", "#/lieder/gruppen"),
]


def anmelden(page, benutzer, passwort) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('#dk-usr, input[name="usr"]', benutzer)
    page.fill('#dk-pwd, input[name="pwd"]', passwort)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def schuss(page, ordner: str, name: str, pfad: str) -> str:
    page.goto(f"{BASE}/{pfad}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    ziel = os.path.join(ordner, f"{name}.png")
    page.screenshot(path=ziel, full_page=False)
    print(f"[ux3a2] {os.path.basename(ziel)} ← {pfad} → {page.url}")
    return page.url


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for lage, groesse in (("desktop", {"width": 1440, "height": 900}),
                              ("mobil", {"width": 390, "height": 844})):
            for thema in ("hell", "dunkel"):
                ordner = os.path.join(ZIEL, MARKER, lage, thema)
                os.makedirs(ordner, exist_ok=True)
                context = browser.new_context(
                    viewport=groesse,
                    has_touch=(lage == "mobil"),
                    is_mobile=(lage == "mobil"),
                    locale="de-DE",
                )
                page = context.new_page()
                page.on("console", lambda m: fehler.append(f"{lage}/{thema}: {m.text}")
                        if m.type == "error" else None)
                page.on("pageerror", lambda e: fehler.append(f"{lage}/{thema}: {e}"))
                anmelden(page, BENUTZER, PASSWORT)
                if thema == "dunkel":
                    page.evaluate("() => localStorage.setItem('dk-theme','dark')")
                    page.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
                for name, pfad in SEITEN:
                    schuss(page, ordner, name, pfad)
                if thema == "hell":
                    # UX3a2 F1: altes Lesezeichen mit Kennung. Die Adresszeile
                    # nach dem Laden ist der Beleg (sie muss auf
                    # #/lieder/gruppen/… stehen, nicht auf „nicht gefunden“).
                    if LIEDGRUPPE:
                        url = schuss(page, ordner, "04-alt-liedgruppen-kennung",
                                     f"#/liedgruppen/{LIEDGRUPPE}")
                        if f"/lieder/gruppen/{LIEDGRUPPE}" not in url:
                            fehler.append(f"{lage}/{thema}: Liedgruppen-Weiterleitung "
                                          f"landete auf {url}")
                context.close()

        # UX3a2 F4: Gäste-Sicht — untere Leiste und „Mehr“-Blatt ohne „Dienste“.
        if GAST_EMAIL and GAST_PASS:
            for lage, groesse in (("mobil", {"width": 390, "height": 844}),
                                  ("desktop", {"width": 1440, "height": 900})):
                ordner = os.path.join(ZIEL, MARKER, lage, "hell")
                os.makedirs(ordner, exist_ok=True)
                context = browser.new_context(
                    viewport=groesse,
                    has_touch=(lage == "mobil"),
                    is_mobile=(lage == "mobil"),
                    locale="de-DE",
                )
                page = context.new_page()
                anmelden(page, GAST_EMAIL, GAST_PASS)
                schuss(page, ordner, "05-gast-startseite", "#/")
                if lage == "mobil":
                    mehr = page.locator(".dk-bn-tab", has_text="Mehr").first
                    if mehr.count():
                        mehr.click()
                        page.wait_for_timeout(400)
                        page.screenshot(path=os.path.join(ordner, "06-gast-mehr-blatt.png"))
                        print(f"[ux3a2] 06-gast-mehr-blatt.png")
                context.close()
        browser.close()
    if fehler:
        print("[ux3a2] Konsolen-/Seitenfehler:", *fehler, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
