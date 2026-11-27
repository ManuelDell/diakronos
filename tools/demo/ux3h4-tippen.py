"""UX3h4 — Tipp-Beleg: angehaengt statt ersetzt?

Tippt in das Feld „Ort“ und liest Wert, Cursor-Stelle und Modell-Stand.
Ein Feld, das beim Tippen den Modellwert zurueckschreibt, setzt den Cursor an
das Ende (alte Eingabe steht VORN) — genau das Fehlerbild des alten Musters.
"""
import sys
import json
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


BASE = os.environ.get("BASE", "http://127.0.0.1:15970")
ZIEL = os.environ.get("ZIEL", "/out")
# SEC-DEF2: Zugangsdaten ausdruecklich aus der Umgebung, kein Demo-Standard.
ADMIN_EMAIL = wert_oder_abbruch("ADMIN_EMAIL")
ADMIN_PASS = wert_oder_abbruch("ADMIN_PASS")
os.makedirs(ZIEL, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1366, "height": 800})
    page.goto(BASE + "/diakonos", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.fill('input[name="usr"]', ADMIN_EMAIL)
    page.fill('input[name="pwd"]', ADMIN_PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    page.goto(BASE + "/diakonos#/einstellungen/gemeinde", wait_until="networkidle")
    page.wait_for_timeout(2500)

    feld_id = page.evaluate(
        """() => {
            const l = [...document.querySelectorAll('label')]
              .find((x) => x.textContent.replace('*', '').trim() === 'Ort')
            return l && l.getAttribute('for')
        }""")
    ort = page.locator("#" + feld_id)
    start = ort.input_value()
    # Alles markieren und ueberschreiben — wie ein Mensch es taete.
    ort.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("Musterstadt neu", delay=60)
    page.wait_for_timeout(300)
    ende = page.evaluate(
        """(id) => {
            const e = document.getElementById(id)
            return { wert: e.value, cursor: e.selectionStart, laenge: e.value.length }
        }""", feld_id)
    page.screenshot(path=os.path.join(ZIEL, "ux3h4-ort-tippen-nachher.png"), full_page=True)

    bericht = {
        "feld_vor_dem_tippen": start,
        "nach_dem_tippen": ende,
        "angehaengt_statt_ersetzt": ende["wert"] != "Musterstadt neu",
    }
    with open(os.path.join(ZIEL, "ux3h4-ort-tippen-nachher.json"), "w", encoding="utf-8") as f:
        json.dump(bericht, f, ensure_ascii=False, indent=2)
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
    b.close()
