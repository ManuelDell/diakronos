"""UX3h3 — Screenshots „Speichern nur, wenn geändert“ (nachher).

Läuft im Playwright-Image gegen den Wegwerf-Stack. Je Seite zwei Aufnahmen:

  * `-gesperrt` : direkt nach dem Laden — „Speichern“ ist zu (ausgegraut,
                  aria-disabled) und trägt den Grund als `title`.
  * `-geaendert`: nach einer echten Eingabe über die TASTATUR (im Stack
                  gemessen: `fill` setzte an Mailversand und am Ort-Feld den
                  Anzeigewert, ließ den Vue-Zustand aber stehen — der Knopf
                  blieb gesperrt). Der Tastatur-Weg ist ohnehin der, den ein
                  Mensch geht.

Zusätzlich hell/dunkel und Desktop 1366 px / Mobil 390 px. Der Zustand des
Knopfes wird mitgelesen und in `belege.json` festgehalten (eine Aufnahme zeigt
keinen Tooltip).

Aufruf:
    docker run --rm --network ux3h3_default -v "$PWD":/w -v "$ZIEL_HOST":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e ADMIN_PASS=… \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        bash -c "pip install -q playwright==1.49.0 && python /w/tools/demo/ux3h3-screens.py"
"""
import json
import os
import sys

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

# (Name, Adresse, Feld zum Ändern, neuer Wert)
SEITEN = [
    ("gemeinde", "#/einstellungen/gemeinde", "textarea", "Ein kurzer Willkommensgruß."),
    ("anmeldung", "#/einstellungen/anmeldung", None, None),
    # Bei Datenschutz/Mailversand/Gemeinde ist der Unterschied zwischen „vorher
    # leer“ und „jetzt Text“ der ehrliche Fall (der Seed legt für Mailversand und
    # den Willkommenstext NICHTS an — geprüft über die API).
    ("datenschutz", "#/einstellungen/datenschutz", "textarea", "Einwilligungstext, geändert."),
    ("datensicherung", "#/einstellungen/datensicherung", 'input[type="time"]', "04:30"),
    ("mailversand", "#/einstellungen/mailversand", 'input[type="text"]', "mail2.example.org"),
    ("registrierung", "#/einstellungen/registrierung", 'input[type="number"]', "60"),
]

befunde = []


def speichern_knopf(page):
    return page.locator("button[type=submit]", has_text="Speichern").first


def zustand(page):
    knopf = speichern_knopf(page)
    return {
        "disabled": knopf.is_disabled(),
        "aria_disabled": knopf.get_attribute("aria-disabled"),
        "title": knopf.get_attribute("title"),
    }


def dunkel(page, an):
    page.evaluate(
        "(an) => { document.documentElement.dataset.theme = an ? 'dark' : 'light';"
        " document.documentElement.classList.toggle('dark', an); }",
        an,
    )
    page.wait_for_timeout(400)


def lauf():
    with sync_playwright() as p:
        b = p.chromium.launch()
        for modus, breite, hoehe in (("desktop", 1366, 900), ("mobil", 390, 844)):
            ctx = b.new_context(viewport={"width": breite, "height": hoehe})
            page = ctx.new_page()
            fehler = []
            page.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
            page.goto(BASE + "/", wait_until="networkidle")
            page.fill('input[name="usr"]', EMAIL)
            page.fill('input[name="pwd"]', PASSWORT)
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)

            for name, adresse, feld, neu_wert in SEITEN:
                for thema in ("hell", "dunkel"):
                    # je Aufnahme NEU laden: der vorige Durchlauf darf den
                    # Ausgangszustand nicht verändern.
                    page.goto(BASE + "/" + adresse, wait_until="networkidle")
                    page.wait_for_timeout(2200)
                    dunkel(page, thema == "dunkel")

                    vorher = zustand(page)
                    page.screenshot(
                        path=f"{ZIEL}/{name}-{modus}-{thema}-gesperrt.png", full_page=True)

                    if feld:
                        ziel = page.locator(feld).first
                        ziel.click()
                        ziel.press("Control+a")
                        ziel.type(neu_wert, delay=25)
                        page.wait_for_timeout(900)
                    # „anmeldung“: Authentik ist im Wegwerf-Stack AUS → die
                    # Felder sind absichtlich gesperrt (die Seite sagt es
                    # selbst). Dort wird nur der Zustand des Knopfes gemessen.
                    nachher = zustand(page)
                    page.screenshot(
                        path=f"{ZIEL}/{name}-{modus}-{thema}-geaendert.png", full_page=True)
                    befunde.append({
                        "seite": name, "modus": modus, "thema": thema,
                        "gesperrt": vorher, "geaendert": nachher,
                    })
            if fehler:
                print("KONSOLENFEHLER:", fehler[:5])
            ctx.close()
        b.close()


lauf()
with open(f"{ZIEL}/belege.json", "w", encoding="utf-8") as f:
    json.dump(befunde, f, ensure_ascii=False, indent=1)

schlecht = []
for b in befunde:
    if b["seite"] == "anmeldung":
        # Ohne Authentik gesperrt — der Knopf ist zu RECHT zu.
        ok = b["gesperrt"]["disabled"] is True and b["gesperrt"]["aria_disabled"] == "true"
    else:
        ok = (b["gesperrt"]["disabled"] is True
              and b["gesperrt"]["aria_disabled"] == "true"
              and b["geaendert"]["disabled"] is False)
    if not ok:
        schlecht.append(b)
    print(f'{b["seite"]:16} {b["modus"]:8} {b["thema"]:7} '
          f'gesperrt={b["gesperrt"]["disabled"]!s:5} geaendert={b["geaendert"]["disabled"]!s:5} '
          f'grund={b["gesperrt"]["title"]!r}')
print("BEFUNDE", len(befunde), "ABWEICHUNGEN", len(schlecht))
sys.exit(1 if schlecht else 0)
