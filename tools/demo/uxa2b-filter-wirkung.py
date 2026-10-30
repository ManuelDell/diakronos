"""UX-A2b — der Statusfilter WIRKT: Klick auf einen Chip wechselt die Liste.

Ergaenzung zum Beleg-Skript: Chips mit Zahlen koennten auch nur Zierde sein.
Hier wird im Browser geklickt und die Tabelle danach gemessen.

Aufruf:
    docker run --rm --network t_c37ea235-test_default -v "$PWD":/w:ro \
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uxa2b-filter-wirkung.py
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

fehler: list[str] = []
verlauf: list[dict] = []


def tabelle(page):
    return page.evaluate(
        """() => {
            const t = document.querySelector('table.dk-table') || document.querySelector('table');
            if (!t) return { zeilen: [], leer: null };
            const zeilen = [...t.querySelectorAll('tbody tr')].map(tr =>
                [...tr.children].map(td => td.textContent.replace(/\\s+/g, ' ').trim()));
            const leer = document.querySelector('.dk-ui-leer, .dk-empty');
            return { zeilen, leer: leer ? leer.textContent.replace(/\\s+/g, ' ').trim() : null };
        }"""
    )


def chips(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('.reg-statusfilter button.dk-ui-chip')].map(b => ({
            label: (b.childNodes[0] && b.childNodes[0].textContent || '').trim(),
            zahl: (b.querySelector('.dk-ui-chip-zahl') || {}).textContent || null,
            aktiv: b.classList.contains('is-active'),
            gedrueckt: b.getAttribute('aria-pressed'),
        }))"""
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for breite, hoehe, marke in [(1366, 900, "desktop"), (390, 844, "mobil")]:
            ctx = browser.new_context(viewport={"width": breite, "height": hoehe}, locale="de-DE")
            page = ctx.new_page()
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(400)
            page.fill("#dk-usr", ADMIN)
            page.fill("#dk-pwd", ADMIN_PASS)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)
            page.goto(BASE + "/#/mitglieder/anfragen", wait_until="networkidle")
            page.wait_for_timeout(1500)

            for ziel in ("Alle", "Aufgenommen", "Abgelehnt", "Offen"):
                page.click(f'.reg-statusfilter button.dk-ui-chip:has-text("{ziel}")')
                page.wait_for_timeout(500)
                daten = tabelle(page)
                stand = chips(page)
                verlauf.append({"marke": marke, "chip": ziel, "chips": stand,
                                "zeilen": daten["zeilen"]})
                aktiv = [c["label"] for c in stand if c["aktiv"]]
                if aktiv != [ziel]:
                    fehler.append(f"{marke}/{ziel}: gewaehlt {aktiv}")
                # Jede sichtbare Zeile muss den gewaehlten Status tragen.
                # „Alle“ ist die Ausnahme: dort steht jeder Status, auch
                # Warteliste — die Zahl am Chip muss zur Zeilenzahl passen.
                if ziel == "Alle":
                    zahl = next((c["zahl"] for c in stand if c["label"] == "Alle"), None)
                    if str(len(daten["zeilen"])) != str(zahl):
                        fehler.append(f"{marke}/Alle: Chip sagt {zahl}, "
                                      f"Tabelle {len(daten['zeilen'])} Zeilen")
                    if not daten["zeilen"]:
                        fehler.append(f"{marke}/Alle: keine Zeilen")
                else:
                    for z in daten["zeilen"]:
                        if len(z) >= 5 and z[4] != ziel:
                            fehler.append(f"{marke}/{ziel}: Zeile mit Status „{z[4]}“")
                if ziel in ("Aufgenommen", "Abgelehnt"):
                    if len(daten["zeilen"]) != 1:
                        fehler.append(f"{marke}/{ziel}: {len(daten['zeilen'])} Zeilen (erwartet 1)")
                page.screenshot(path=os.path.join(ZIEL, f"uxa2b-filter-{ziel.lower()}-{marke}.png"))
            ctx.close()
        browser.close()

    with open(os.path.join(ZIEL, "uxa2b-filter-wirkung.json"), "w", encoding="utf-8") as f:
        json.dump({"verlauf": verlauf, "fehler": fehler}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"fehler": fehler, "schritte": len(verlauf)}, ensure_ascii=False))
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
