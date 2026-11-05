"""UX1e — Screenshots des Kalender-/Moderationsbereichs vorher/nachher.

Läuft im Playwright-Image gegen einen Wegwerf-Stack mit den Demo-Daten
(`tools/demo/musterhausen.py`). Der Stack wird NICHT hier gestartet.

Aufruf (aus dem Projektverzeichnis):

    docker run --rm --network <projekt>_default -v "$PWD":/w \
        -e BASE=http://app:8000 -e ZIEL=/w/<ausgabe> \
        -e ADMIN_PASS=... \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux1e-knoepfe.py

Aufgenommen wird, was Karte UX1e umstellt: Kalender (Monat, Kopfzeile),
der Termin-Dialog (Anlegen/Bearbeiten, Fuß mit den Knöpfen), der
Serien-Dialog und die Moderationsseite — je Desktop 1440 und Mobil 390,
hell und dunkel.

Der Lauf endet mit Rückgabewert 1 und einer Liste, sobald eine Seite einen
Konsolenfehler wirft.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ.get("ZIEL", "/ausgabe")
PRAEFIX = os.environ.get("PRAEFIX", "")

fehler: list[str] = []


def anmelden(page) -> None:
    """Anmeldung wie in tools/demo/screenshots.py (die Seite liefert die
    Anmeldemaske direkt unter `/`, nicht unter einem eigenen Hash-Pfad)."""
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(
        viewport={"width": breite, "height": hoehe},
        color_scheme="dark" if dunkel else "light",
        locale="de-DE",
    )
    page = ctx.new_page()
    page.on("pageerror", lambda e: fehler.append(f"{page.url}: JS {e}"))
    page.on("console", lambda m: fehler.append(f"{page.url}: {m.text}")
            if m.type == "error" else None)
    return ctx, page


def schuss(page, name, ziel, waage="auto") -> None:
    os.makedirs(ziel, exist_ok=True)
    pfad = os.path.join(ziel, f"{name}.png")
    page.screenshot(path=pfad, full_page=(waage == "full"))
    print(f"  {pfad}", flush=True)


def monat_weiter(page, schritte: int = 1) -> None:
    """Der Demo-Zeitraum liegt im November 2026 — der Kalender startet heute."""
    for _ in range(schritte):
        knopf = page.locator("button[aria-label='Nächster Monat']").first
        if knopf.count():
            knopf.click()
            page.wait_for_timeout(700)


def termin_dialog(page) -> bool:
    """Öffnet den ANLEGE-Dialog für einen Termin.

    Im Ansichtsmodus öffnet ein Klick auf einen Tag die Tagesliste; erst im
    Bearbeitungsmodus (Stift) entsteht ein neuer Termin (`onDateClick` in
    pages/Kalender.vue). Der Dialog trägt die Knopfleiste, die UX1e umstellt.
    Die Terminzellen heissen `.ec-day` (@event-calendar, nicht FullCal).
    """
    stift = page.locator("button[aria-label='Bearbeitungsmodus']").first
    if stift.count():
        stift.click()
        page.wait_for_timeout(800)
    pfeil = page.evaluate("""() => {
      for (const d of document.querySelectorAll('div.ec-day:not(.ec-other-month)')) {
        if (!d.querySelector('.ec-event')) {
          const r = d.getBoundingClientRect(); return {x: r.x + 30, y: r.y + 30};
        }
      }
      return null;
    }""")
    if not pfeil:
        return False
    page.mouse.click(pfeil["x"], pfeil["y"])
    page.wait_for_timeout(2000)
    return page.locator(".diakronos-modal-footer").count() > 0


def lauf(browser, breite, hoehe, marke, ziel) -> None:
    ctx, page = kontext(browser, breite, hoehe)
    anmelden(page)
    page.goto(f"{BASE}/{PRAEFIX}#/kalender".replace("//#", "/#"), wait_until="networkidle")
    page.wait_for_timeout(1500)
    monat_weiter(page)
    schuss(page, f"{marke}-01-kalender", ziel)

    if termin_dialog(page):
        schuss(page, f"{marke}-02-neuer-termin", ziel)
        # Der Fuß mit den Knöpfen (Abbrechen | Speichern) ist die Stelle, die
        # UX1e umstellt — als eigener, nah herangezogener Schuss.
        fuss = page.locator(".diakronos-modal-footer").first
        if fuss.count():
            fuss.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            schuss(page, f"{marke}-03-termin-fuss", ziel)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

    page.goto(f"{BASE}/{PRAEFIX}#/moderation".replace("//#", "/#"), wait_until="networkidle")
    page.wait_for_timeout(1500)
    schuss(page, f"{marke}-04-moderation", ziel)
    ctx.close()

    ctx, page = kontext(browser, breite, hoehe, dunkel=True)
    anmelden(page)
    page.goto(f"{BASE}/{PRAEFIX}#/kalender".replace("//#", "/#"), wait_until="networkidle")
    page.wait_for_timeout(1500)
    monat_weiter(page)
    schuss(page, f"{marke}-05-kalender-dunkel", ziel)
    if termin_dialog(page):
        schuss(page, f"{marke}-06-neuer-termin-dunkel", ziel)
        page.keyboard.press("Escape")
    ctx.close()


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        print("Desktop 1440", flush=True)
        lauf(browser, 1440, 900, "desktop", ziel=os.path.join(ZIEL, "desktop"))
        print("Mobil 390", flush=True)
        lauf(browser, 390, 844, "mobil", ziel=os.path.join(ZIEL, "mobil"))
        browser.close()
    if fehler:
        print("Konsolenfehler:", file=sys.stderr)
        for f in fehler:
            print("  " + f, file=sys.stderr)
        return 1
    print("fertig", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
