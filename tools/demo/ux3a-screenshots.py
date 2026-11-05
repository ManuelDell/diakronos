"""UX3a — Screenshots vorher/nachher der neuen Navigation.

Läuft im Playwright-Image gegen einen Wegwerf-Stack mit den Demo-Daten
(Musterhausen). Aufgenommen werden die Seiten, die UX3a berührt:
Seitenleiste (Menü, Fußbereich mit Profilmenü), Personen-Bereich mit
Adressbuch-Reiter, der Bereich Dienste mit seinen Reitern, „Zu prüfen“ im
Kalender, Lieder mit Liedgruppen-Reiter — je Desktop (1440×900) und Mobil
(390×844), hell und dunkel.

Aufruf (Netz des eigenen Compose-Projekts, nie der Betrieb):

    docker run --rm --network ux3a-nachher_default \
        -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e MARKER=nachher \
        -e ADMIN_PASS=musterhausen-demo \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux3a-screenshots.py

Die Bilder sind Abnahme-Belege, keine Veröffentlichung: erfundene Demo-Daten.
"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "jetzt")

fehler: list[str] = []

# Seiten, die UX3a betrifft: (Name, Adresse)
SEITEN = [
    ("01-uebersicht", "#/"),
    ("02-personen-liste", "#/personen/liste"),
    ("03-personen-adressbuch", "#/personen/adressbuch"),
    ("04-dienste-meine", "#/dienste/meine-dienste"),
    ("05-dienste-dienstplaene", "#/dienste/dienstplaene"),
    ("06-dienste-vorlagen", "#/dienste/vorlagen"),
    ("07-kalender-pruefen", "#/kalender/pruefen"),
    ("08-lieder", "#/lieder"),
    ("09-lieder-gruppen", "#/lieder/gruppen"),
    ("10-einstellungen", "#/einstellungen"),
]

# Alte Adressen, die weiterleiten müssen (Lesezeichen): Name → Adresse
ALT = [
    ("11-alt-mitglieder-liste", "#/mitglieder/liste"),
    ("12-alt-adressbuch", "#/adressbuch"),
    ("13-alt-dienstplan", "#/dienstplan"),
    ("14-alt-planrahmen", "#/planrahmen"),
    ("15-alt-moderation", "#/moderation"),
    ("16-alt-liedgruppen", "#/liedgruppen"),
]


def anmelden(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    # Die Anmeldemaske des Betriebs heißt `usr`/`pwd` (id dk-usr/dk-pwd).
    page.fill('#dk-usr, input[name="usr"]', BENUTZER)
    page.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def schuss(page, ordner: str, name: str, pfad: str) -> None:
    page.goto(f"{BASE}/{pfad}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)
    ziel = os.path.join(ordner, f"{name}.png")
    page.screenshot(path=ziel, full_page=False)
    print(f"[ux3a] {os.path.basename(ziel)} ← {pfad} → {page.url}")


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
                anmelden(page)
                if thema == "dunkel":
                    page.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
                    # Der Umschalter merkt sich das Theme im localStorage — damit
                    # jede weitere Seite ebenso dunkel startet.
                    page.evaluate("() => localStorage.setItem('dk-theme','dark')")
                for name, pfad in SEITEN:
                    schuss(page, ordner, name, pfad)
                if lage == "desktop" and thema == "hell":
                    # Profilmenü offen (UX3a: Werkzeuge liegen dort).
                    page.goto(f"{BASE}/#/", wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle")
                    knopf = page.locator('.dk-sb-profil .dk-sb-user').first
                    if knopf.count():
                        knopf.click()
                        page.wait_for_timeout(300)
                        page.screenshot(path=os.path.join(ordner, "20-profilmenue-offen.png"))
                if lage == "mobil" and thema == "hell":
                    page.goto(f"{BASE}/#/", wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle")
                    mehr = page.locator('.dk-bn-tab', has_text="Mehr").first
                    if mehr.count():
                        mehr.click()
                        page.wait_for_timeout(400)
                        page.screenshot(path=os.path.join(ordner, "21-mehr-blatt.png"))
                if thema == "hell":
                    for name, pfad in ALT:
                        schuss(page, ordner, name, pfad)
                context.close()
        browser.close()
    if fehler:
        print("[ux3a] Konsolen-/Seitenfehler:", *fehler, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
