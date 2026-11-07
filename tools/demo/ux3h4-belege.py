"""UX3h4 — Bildschirm-Belege: Feld „Ort“ in Einstellungen › Gemeinde sowie
Mailversand (Server/Absender) und Registrierung.

Laeuft im Playwright-Image gegen den Wegwerf-Stack (Projekt `ux3h4`,
BASE=http://127.0.0.1:15970). Der Stack steht auf demselben Host; das Image
bekommt `--network host`, damit 127.0.0.1:15970 erreichbar ist.

    docker run --rm --network host -v /tmp:/out \\
        -e BASE=http://127.0.0.1:15970 -e ZIEL=/out \\
        -e ADMIN_EMAIL=admin@example.org -e ADMIN_PASS=musterhausen-demo \\
        -e PRAEFIX=nachher \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        python -c "$(cat tools/demo/ux3h4-belege.py)"

Je Seite ein Bild (Desktop 1366x800) plus die GELESENEN Feldwerte als JSON —
das Bild allein beweist den Wert nicht, der Text schon.
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:15970")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ.get("ZIEL", "/out")
PRAEFIX = os.environ.get("PRAEFIX", "stand")

os.makedirs(ZIEL, exist_ok=True)
ergebnis = {}


def feldwert(page, beschriftung):
    """Wert des Feldes mit genau dieser Beschriftung (DkField -> <label for>).

    `id` und `wert` kommen GETRENNT aus dem DOM: `id` per Attribut (verrät, ob
    ein Label-Ziel im Feld steht), `wert` über JS (das Attribut `value` bleibt
    bei `v-model` leer, nur die LIVE-Eigenschaft trägt den Wert).
    """
    return page.evaluate(
        """(beschriftung) => {
            const label = [...document.querySelectorAll('label')]
              .find((l) => l.textContent.replace('*', '').trim() === beschriftung)
            if (!label) return null
            const id = label.getAttribute('for')
            const feld = id ? document.getElementById(id) : label.querySelector('input,select,textarea')
            if (!feld) return { wert: null, id }
            const attributWert = feld.getAttribute('value')
            return { wert: feld.value, attributWert }
        }""",
        beschriftung,
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 800})
    page.goto(BASE + "/diakonos", wait_until="networkidle")
    page.wait_for_timeout(1200)
    # Anmeldemaske: die Kennung ist ein Textfeld (`name="email"`), das Passwort
    # steht in `input[type="password"]`.
    page.fill('input[name="usr"]', BENUTZER)
    page.fill('input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # ── Einstellungen › Gemeinde ───────────────────────────────────────────
    page.goto(BASE + "/diakonos#/einstellungen/gemeinde", wait_until="networkidle")
    page.wait_for_timeout(2000)
    ergebnis["gemeinde"] = {
        b: feldwert(page, b)
        for b in ["Name der Gemeinde", "Kurzname", "Straße und Hausnummer", "PLZ",
                  "Ort", "Telefon", "Website"]
    }
    page.screenshot(path=os.path.join(ZIEL, f"ux3h4-gemeinde-{PRAEFIX}.png"), full_page=True)

    # ── Einstellungen › Mailversand ────────────────────────────────────────
    page.goto(BASE + "/diakonos#/einstellungen/mailversand", wait_until="networkidle")
    page.wait_for_timeout(2000)
    ergebnis["mailversand"] = {
        b: feldwert(page, b)
        for b in ["Name des Mailservers", "Benutzername", "Absenderadresse", "Absendername"]
    }
    page.screenshot(path=os.path.join(ZIEL, f"ux3h4-mailversand-{PRAEFIX}.png"), full_page=True)

    # Wo stand die Seite wirklich? (Hash-Router: der Hash kommt erst im
    # Browser an — ohne diese Probe sähe ein Fehlschlag wie ein Datenfehler aus.)
    ergebnis["_seite"] = {"url": page.url, "titel": page.title()}
    # Und was liefert die API SELBST? Trennt „Daten fehlen“ von „Oberfläche
    # zeigt sie nicht“ — der Befund betrifft nur das Anzeigen.
    ergebnis["_api"] = page.evaluate(
        """async () => {
            const antwort = await fetch(
              '/api/method/diakronos.diakronos.api.gemeinde.gemeinde_get_einstellungen',
              { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}) })
            const text = await antwort.text()
            try { return { status: antwort.status, daten: JSON.parse(text).message } }
            catch { return { status: antwort.status, text: text.slice(0, 200) } }
        }""")

    browser.close()

print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
with open(os.path.join(ZIEL, f"ux3h4-werte-{PRAEFIX}.json"), "w", encoding="utf-8") as f:
    json.dump(ergebnis, f, ensure_ascii=False, indent=2)
