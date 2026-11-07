"""UX3h4 — Vorher-Beleg am Bildschirm: das ALTE Muster am Feld „Ort“.

Fuer den Vorher-Stand sind zwei Aufnahmen noetig, weil das alte Muster zwei
Fehlerbilder hat:

  vorher-wert-verloren.png   Wert aus `:wert` (Serverwert) und `v-model` am
                             selben Element — der Feldsatz setzt das Attribut,
                             die Anzeige bleibt leer (jsdom-Test belegt es).

  Diese Datei zeigt das ZWEITE Bild: `v-model` am Element OHNE `:wert`. Dann
  setzt Vue `el.value` beim Tippen zurueck auf den Modellwert (vor der
  Eingabe) — das Feld LEERT sich beim ersten Zeichen. Genau das hat der
  Worker in UX3h3 gemeldet („wer dann speichert, koennte den Ort
  ueberschreiben/leeren“).

Der Stack traegt dafuer Gemeinde.vue im Stand `v-model` ohne `:wert`; die
API liefert weiterhin `ort: "Musterhausen"` (im Beleg unten mit abgedruckt).
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:15970")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ.get("ZIEL", "/out")
os.makedirs(ZIEL, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 800})
    page.goto(BASE + "/diakonos", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.fill('input[name="usr"]', BENUTZER)
    page.fill('input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    page.goto(BASE + "/diakonos#/einstellungen/gemeinde", wait_until="networkidle")
    page.wait_for_timeout(2500)

    # Die API-Antwort, gegen die geprueft wird (Nachweis: der Server HAT den Ort).
    api = page.evaluate(
        """async () => {
            const t = window.__DIakonosBOOT && window.__DIakonosBOOT.csrf_token
            const r = await fetch('/api/method/diakronos.diakronos.api.gemeinde.gemeinde_get_einstellungen',
              { method: 'POST', headers: { 'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': t || '' }, body: '{}' })
            const j = JSON.parse(await r.text())
            return { status: r.status, ort: (j.message || {}).ort, kurzname: (j.message || {}).kurzname }
        }""")

    ziel_id = page.evaluate(
        """() => {
            const l = [...document.querySelectorAll('label')]
              .find((x) => x.textContent.replace('*', '').trim() === 'Ort')
            return l && l.getAttribute('for')
        }""")
    assert ziel_id, 'Feld „Ort“ nicht gefunden'
    ort = page.locator("#" + ziel_id)
    # Beweis, dass es DIESES Feld ist und dass der Server den Ort liefert:
    # der sichtbare Wert steht vor dem Tippen im Beleg.
    vorher = ort.input_value()
    ort.click()
    ort.press_sequentially("Musterstadt neu", delay=40)
    nachher = ort.input_value()
    page.screenshot(path=os.path.join(ZIEL, "ux3h4-ort-tippen-vorher.png"), full_page=True)

    bericht = {
        "api_ort": api.get("ort"),
        "api_status": api.get("status"),
        "feld_vor_dem_tippen": vorher,
        "feld_nach_dem_tippen": nachher,
        "tippen_verloren": nachher != "Musterstadt neu",
    }
    with open(os.path.join(ZIEL, "ux3h4-ort-tippen-vorher.json"), "w", encoding="utf-8") as f:
        json.dump(bericht, f, ensure_ascii=False, indent=2)
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
    browser.close()
