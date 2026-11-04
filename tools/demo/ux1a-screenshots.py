"""UX1a — Vorher/Nachher-Bilder der Seiten, die die Karte beruehrt.

Laeuft im Playwright-Image gegen einen Wegwerf-Stack mit Musterhausen-Daten
(`tools/demo/musterhausen.py`). Aufgenommen wird je Seite:

  Desktop 1440x900 hell · Mobil 390x844 hell · Mobil 390 dunkel

Aufruf (aus dem Worktree):

    docker run --rm --network container:<app-container> \
        -v "$PWD":/w -e BASE=http://127.0.0.1:8000 \
        -e ZIEL=/w/<zielordner> -e ADMIN_PASS=... \
        -e PRAEFIX=nachher \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux1a-screenshots.py

Die Seiten sind die mit den meisten umgestellten Werten (A4): Seitenleiste/
Topbar (jede Seite), Ressourcen, Planrahmen (Uebersicht, Plantyp-Editor,
Stammdaten, Meine Dienste), Lieder, Dienstplan, Mitglieder, Formular-Seite
(Anmeldung) und die Server-Seite (Passwort setzen).
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ["ZIEL"]
PRAEFIX = os.environ.get("PRAEFIX", "")

# Name -> Pfad (Hash-Router der SPA)
SEITEN = [
    ("uebersicht", "#/"),
    ("ressourcen", "#/ressourcen"),
    ("lieder", "#/lieder"),
    ("dienstplan", "#/dienstplan"),
    ("mitglieder", "#/mitglieder/liste"),
    ("gruppen", "#/gruppen"),
    ("planrahmen", "#/planrahmen"),
    ("meine-dienste", "#/planrahmen/meine-dienste"),
    ("stammdaten", "#/planrahmen/stammdaten"),
    ("einstellungen", "#/einstellungen/datensicherung"),
]

GERAETE = [
    ("desktop", {"viewport": {"width": 1440, "height": 900}}, "light"),
    ("mobil", {"viewport": {"width": 390, "height": 844}, "is_mobile": True,
               "has_touch": True, "device_scale_factor": 2}, "light"),
    ("mobil-dunkel", {"viewport": {"width": 390, "height": 844}, "is_mobile": True,
                      "has_touch": True, "device_scale_factor": 2}, "dark"),
]

fehler: list[str] = []


def anmelden(page):
    page.goto(BASE + "/", wait_until="domcontentloaded")
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
        page.wait_for_load_state("networkidle")


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for geraet, optionen, schema in GERAETE:
            ctx = browser.new_context(locale="de-DE", color_scheme=schema, **optionen)
            ctx.set_default_timeout(20000)
            page = ctx.new_page()

            def meldung(msg, _g=geraet):
                if msg.type != "error":
                    return
                if "devmodus.api.uebersicht" in msg.text or "404" in msg.text:
                    return
                fehler.append(f"{_g}: {msg.text}")

            page.on("console", meldung)
            page.on("pageerror", lambda exc, _g=geraet: fehler.append(f"{_g}: {exc}"))

            # Anmeldeseite (Server-Seite, seiten.css) ohne Sitzung.
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(500)
            name = f"{PRAEFIX}{geraet}-anmeldung.png"
            page.screenshot(path=os.path.join(ZIEL, name))
            print("geschrieben", name)

            anmelden(page)
            for seite, pfad in SEITEN:
                page.goto(BASE + "/" + pfad, wait_until="networkidle")
                page.wait_for_timeout(900)
                name = f"{PRAEFIX}{geraet}-{seite}.png"
                page.screenshot(path=os.path.join(ZIEL, name))
                print("geschrieben", name)
            ctx.close()
        browser.close()

    if fehler:
        print("KONSOLENFEHLER:", *fehler, sep="\n  ")
        return 1
    print("keine Konsolenfehler")
    return 0


if __name__ == "__main__":
    sys.exit(main())
