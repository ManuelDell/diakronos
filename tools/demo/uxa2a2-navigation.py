"""UX-A2a2 — Belege zur Mitglieder-Navigation (ARIA, toter Code, EIN Zählertakt).

Laeuft im Playwright-Image gegen den Wegwerf-Stack (Projekt ``uxa2a2``, Port
8391). Aufgenommen wird die Seite ``#/mitglieder/liste`` als Administrator:

  * 1366 px (Desktop) und 390 px (Handy), je hell und dunkel,
  * je Aufnahme wird die DOM GEMESSEN (nicht nur ein Bild gemacht):
      - unsichtbare Texte der Bereichsliste und ihr Ziel (aria-describedby),
      - Zahl der Anfragen-Erwaehnungen im Menue (EIN Punkt, keine Dublette),
      - Anfragen an ``get_navigation_zaehler`` waehrend eines Bereichswechsels
        (darf 0 sein: der Bereich fragt nicht selbst, der Takt ist gemeinsam).

Aufruf:
    docker run --rm --network uxa2a2_default -v "$PWD":/w:ro -v <ziel>:/ausgabe \
        -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uxa2a2-navigation.py
"""
import json
import os
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

SEITE = "#/mitglieder/liste"
ZAEHLER_ENDPUNKT = "get_navigation_zaehler"

fehler: list[str] = []
gemessen: list[dict] = []


def kontext(browser, breite, hoehe, dunkel):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True)
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


def anmelden(page):
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.fill("#dk-usr", ADMIN)
    page.fill("#dk-pwd", ADMIN_PASS)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")


def dom_messen(page):
    """ARIA-Verweis und Menue am lebenden DOM pruefen."""
    return page.evaluate(
        """() => {
            const liste = document.querySelector('.dk-ui-bereichsliste');
            if (!liste) return { fehlt: 'Bereichsliste nicht im DOM' };
            const sr = [...liste.querySelectorAll('.dk-ui-bz-sr')];
            const verweise = [...liste.querySelectorAll('[aria-describedby]')]
                .map(el => el.getAttribute('aria-describedby'));
            const eintraege = [...liste.querySelectorAll('a.dk-ui-bz')]
                .map(a => ({
                    text: (a.querySelector('.dk-ui-bz-name') || a).textContent.trim(),
                    wert: a.dataset.wert,
                    ziel: a.getAttribute('href'),
                    aktuell: a.getAttribute('aria-current'),
                    zahl: (a.querySelector('.dk-ui-bz-zahl') || {}).textContent || null,
                }));
            const menue = [...document.querySelectorAll('.dk-sb-nav .dk-nav-item')]
                .map(a => a.textContent.trim());
            return {
                srTexte: sr.map(el => ({
                    id: el.id,
                    text: el.textContent.trim(),
                    zielVorhanden: !!document.getElementById(el.id),
                    imBild: (() => { const r = el.getBoundingClientRect();
                        return r.width > 1 || r.height > 1; })(),
                })),
                verweise,
                alleVerweiseAufloesbar: verweise.every(id => !!document.getElementById(id)),
                eintraege,
                menueAnfragen: menue.filter(t => t.includes('Mitglieder')).length,
                aktuelle: eintraege.filter(e => e.aktuell === 'page').map(e => e.text),
            };
        }"""
    )


def pruefe(name, bedingung, meldung):
    if not bedingung:
        fehler.append(f"{name}: {meldung}")


def schuss(page, name, breite, voll):
    datei = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=datei, full_page=voll)
    print("geschrieben", os.path.basename(datei))


def lauf(browser, breite, hoehe, dunkel, marke):
    voll = breite <= 720
    ctx = kontext(browser, breite, hoehe, dunkel)
    page = ctx.new_page()

    # Zaehler der Abfragen an den Kennzahl-Endpunkt mitschreiben.
    aufrufe = {"takt": 0}
    page.on("request", lambda req: aufrufe.__setitem__(
        "takt", aufrufe["takt"] + (1 if ZAEHLER_ENDPUNKT in urlparse(req.url).path else 0)))

    anmelden(page)
    page.goto(BASE + "/" + SEITE, wait_until="networkidle")
    page.wait_for_timeout(1200)

    daten = dom_messen(page)
    daten["breite"] = breite
    daten["dunkel"] = dunkel
    daten["marke"] = marke
    gemessen.append(daten)

    pruefe(marke, not daten.get("fehlt"), daten.get("fehlt", ""))
    # Punkt 1: genau EIN unsichtbarer Text, nur beim Eintrag mit Unterpunkten,
    # und jeder aria-describedby-Verweis loest auf.
    sr = daten.get("srTexte", [])
    pruefe(marke, len(sr) == 1, f"unsichtbare Texte: {len(sr)} (erwartet 1)")
    if sr:
        pruefe(marke, sr[0]["text"].startswith("Unterbereiche von"),
               f"Text lautet {sr[0]['text']!r}")
        pruefe(marke, sr[0]["zielVorhanden"], f"id {sr[0]['id']!r} nicht im DOM")
        pruefe(marke, not sr[0]["imBild"], "unsichtbarer Text ist sichtbar")
        pruefe(marke, daten.get("verweise") == [sr[0]["id"]],
               f"aria-describedby {daten.get('verweise')} != {[sr[0]['id']]}")
    pruefe(marke, daten.get("alleVerweiseAufloesbar") is True,
           "ein aria-describedby zeigt ins Leere")
    # Genau EIN gewaehlter Eintrag, und „Anfragen“ steht genau einmal.
    pruefe(marke, len(daten.get("aktuelle", [])) == 1,
           f"gewaehlte Eintraege: {daten.get('aktuelle')}")
    labels = [e["text"] for e in daten.get("eintraege", [])]
    pruefe(marke, labels.count("Anfragen") == 1, f"Eintraege mit „Anfragen“: {labels.count('Anfragen')}")

    schuss(page, f"uxa2a2-mitglieder-{marke}-{'dunkel' if dunkel else 'hell'}",
           breite, voll)

    # Punkt 3: ein Bereichswechsel darf KEINE eigene Kennzahl-Abfrage ausloesen.
    # Gewechselt wird ueber den LINK der Bereichsliste (so wechselt ein Mensch);
    # ein `page.goto` waere ein voller Neuladen der Seite und wuerde den Takt
    # neu starten — das misst nicht den Wechsel.
    vorher = aufrufe["takt"]
    ziel = next((e for e in daten["eintraege"] if e["text"] == "Datenschutz"), None) or \
        next((e for e in daten["eintraege"] if e["aktuell"] != "page"), None)
    if ziel:
        page.click(f'a.dk-ui-bz[data-wert="{ziel["wert"]}"]')
        page.wait_for_timeout(2000)
        nachher = aufrufe["takt"]
        gemessen[-1]["wechselAbfragen"] = nachher - vorher
        gemessen[-1]["wechselZiel"] = page.url
        pruefe(marke, nachher - vorher == 0,
               f"Bereichswechsel loeste {nachher - vorher} Kennzahl-Abfrage(n) aus")
        schuss(page, f"uxa2a2-wechsel-{marke}-{'dunkel' if dunkel else 'hell'}",
               breite, voll)

    ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        lauf(browser, 1366, 900, False, "desktop")
        lauf(browser, 1366, 900, True, "desktop")
        lauf(browser, 390, 844, False, "mobil")
        lauf(browser, 390, 844, True, "mobil")
        browser.close()

    with open(os.path.join(ZIEL, "uxa2a2-messung.json"), "w", encoding="utf-8") as f:
        json.dump({"gemessen": gemessen, "fehler": fehler}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"fehler": fehler, "aufnahmen": len(gemessen)}, ensure_ascii=False))
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
