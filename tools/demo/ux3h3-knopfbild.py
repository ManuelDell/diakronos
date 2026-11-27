"""UX3h3: Bild NUR vom „Speichern“-Knopf (gesperrt / geändert, hell/dunkel).

Ein Vollbild zeigt den Knopf je Seite an wechselnder Stelle — für die Abnahme
zählt der Knopf selbst: Blässe, Beschriftung, Fläche. Er wird über Playwright
an die Knopfposition gescrollt und als Element-Aufnahme gesichert.
"""
import sys
import os

from playwright.sync_api import sync_playwright

# SEC-DEF2: KEIN eingebauter Standard-Zugang. Fehlt die Variable (oder ist sie
# leer), bricht das Skript mit erklaerender Meldung und Exit-Code 2 ab. Der
# oeffentliche Musterhausen-Demo-Standard steht in ``tools/demo/TESTKONTEN.md``,
# wird aber nicht stillschweigend eingesetzt: ein Skript, das versehentlich auf
# einer ECHTEN Instanz laeuft, soll nicht mit bekannten Zugangsdaten weiterlaufen.
# Absichtlich INLINE (kein Import aus ``tools/demo/zugang.py``): viele dieser
# Skripte laufen als EINZELNE Datei in einen Container eingehaengt, andere
# liegen ausserhalb von ``tools/demo`` — ein Nachbarmodul waere dort nicht da.
def wert_oder_abbruch(name: str, hinweis: str = "") -> str:
    wert = os.environ.get(name, "")
    if str(wert).strip():
        return wert
    zusatz = f" {hinweis.strip()}" if hinweis.strip() else ""
    print(
        f"[abbruch] Umgebungsvariable {name} ist nicht gesetzt.{zusatz} "
        "Die Demo-Skripte haben absichtlich KEINEN eingebauten Standard-Zugang "
        "(SEC-DEF2): der oeffentliche Musterhausen-Demo-Standard steht in "
        "tools/demo/TESTKONTEN.md, muss aber ausdruecklich uebergeben werden.",
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(2)


BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
EMAIL = wert_oder_abbruch("ADMIN_EMAIL")
PASSWORT = wert_oder_abbruch("ADMIN_PASS")

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
