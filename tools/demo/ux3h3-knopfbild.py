"""UX3h3: Bild NUR vom „Speichern“-Knopf (gesperrt / geändert, hell/dunkel).

Ein Vollbild zeigt den Knopf je Seite an wechselnder Stelle — für die Abnahme
zählt der Knopf selbst: Blässe, Beschriftung, Fläche. Er wird über Playwright
an die Knopfposition gescrollt und als Element-Aufnahme gesichert.
"""
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")

SEITEN = [
    ("gemeinde", "#/einstellungen/gemeinde", "textarea", "Ein kurzer Willkommensgruß."),
    ("datenschutz", "#/einstellungen/datenschutz", "textarea", "Einwilligungstext, geändert."),
    ("datensicherung", "#/einstellungen/datensicherung", 'input[type="time"]', "04:30"),
    ("registrierung", "#/einstellungen/registrierung", 'input[type="number"]', "60"),
    ("mailversand", "#/einstellungen/mailversand", 'input[type="text"]', "mail2.example.org"),
    ("anmeldung", "#/einstellungen/anmeldung", None, None),
]


def dunkel(page, an):
    page.evaluate("(a)=>{document.documentElement.dataset.theme=a?'dark':'light';}", an)
    page.wait_for_timeout(300)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    page.fill('input[name="usr"]', EMAIL)
    page.fill('input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_timeout(2500)

    for name, adresse, feld, wert in SEITEN:
        for thema in ("hell", "dunkel"):
            page.goto(BASE + "/" + adresse, wait_until="networkidle")
            page.wait_for_timeout(2200)
            dunkel(page, thema == "dunkel")
            knopf = page.locator("button[type=submit]", has_text="Speichern").first
            knopf.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            knopf.screenshot(path=f"{ZIEL}/knopf-{name}-{thema}-gesperrt.png")
            if feld:
                ziel = page.locator(feld).first
                ziel.click()
                ziel.press("Control+a")
                ziel.type(wert, delay=25)
                page.wait_for_timeout(800)
                knopf.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                knopf.screenshot(path=f"{ZIEL}/knopf-{name}-{thema}-geaendert.png")
    ctx.close()
    b.close()
print("fertig")
