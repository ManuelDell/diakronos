"""UX3h4 — Tipp-Beleg: angehaengt statt ersetzt?

Tippt in das Feld „Ort“ und liest Wert, Cursor-Stelle und Modell-Stand.
Ein Feld, das beim Tippen den Modellwert zurueckschreibt, setzt den Cursor an
das Ende (alte Eingabe steht VORN) — genau das Fehlerbild des alten Musters.
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:15970")
ZIEL = os.environ.get("ZIEL", "/out")
os.makedirs(ZIEL, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1366, "height": 800})
    page.goto(BASE + "/diakonos", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.fill('input[name="usr"]', "admin@example.org")
    page.fill('input[name="pwd"]', os.environ["ADMIN_PASS"])
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
