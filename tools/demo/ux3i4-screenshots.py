"""UX3i4 — Belege: Woche (Zeitraster) mit Blöcken, Liste ohne Balken.

Aufgenommen wird gegen den Wegwerf-Stack mit Musterhausen-Daten:
Woche + Tag (hell/dunkel, Desktop 1440) und Liste Desktop 1440 hell+dunkel
sowie Mobil 390. Dazu Messwerte in `ux3i4-messung.json` (Höhe eines Termins
gegen seine DAUER, Fläche/Farbe der Liste, Lage des „⋯" zur Zeile).

Aufruf (Netz des eigenen Compose-Projekts, nie der Betrieb):

    docker run --rm --network ux3i4_default \\
        -v "<repo>":/w:ro -v "<ziel>":/ausgabe \\
        -e BASE=http://app:8000 -e ZIEL=/ausgabe \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        python /w/tools/demo/ux3i4-screenshots.py
"""

import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

os.makedirs(ZIEL, exist_ok=True)
messung: dict = {}


def anmelden(seite) -> None:
    # Die Anmeldemaske heißt `usr`/`pwd` (id dk-usr/dk-pwd) — wie im Betrieb.
    seite.goto(f"{BASE}/login", wait_until="domcontentloaded")
    seite.fill('#dk-usr, input[name="usr"]', EMAIL)
    seite.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    seite.click('button[type="submit"]')
    seite.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    seite.wait_for_load_state("networkidle")


def thema(seite, dunkel: bool) -> None:
    wert = "dark" if dunkel else "light"
    seite.evaluate(
        "d => { document.documentElement.setAttribute('data-theme', d);"
        " localStorage.setItem('dk-theme', d); }",
        wert,
    )
    seite.wait_for_timeout(400)


def kalender(seite, ansicht: str) -> None:
    seite.goto(f"{BASE}/#/kalender", wait_until="networkidle")
    seite.wait_for_timeout(1200)
    # Ansicht über den Reiter der Kopfzeile (Woche/Liste) — dieselbe eine
    # Wahrheit wie im Betrieb, kein direktes setOption.
    knopf = seite.locator(f"button:has-text('{ansicht}'), a:has-text('{ansicht}')").first
    if knopf.count():
        knopf.click()
    seite.wait_for_timeout(1500)


def messen_woche(seite) -> dict:
    return seite.evaluate(
        """() => {
        const raus = { ansicht: document.querySelector('.ec-time-grid') ? 'time-grid' : 'andere' };
        const block = document.querySelector('.ec-time-grid .ec-block');
        if (block) {
          const r = block.getBoundingClientRect();
          const zeile = block.closest('article');
          const z = zeile.getBoundingClientRect();
          const st = getComputedStyle(block);
          raus.block = { breite: Math.round(r.width), hoehe: Math.round(r.height),
                         oben: Math.round(r.top), text: block.innerText.replace(/\\n/g, ' | '),
                         flaeche: st.backgroundColor, schrift: st.color };
          raus.zeile = { hoehe: Math.round(z.height),
                         inlineBlockSize: zeile.style.blockSize || '(leer)' };
          raus.hatPillenKlasse = zeile.classList.contains('ec-chip-event');
          raus.decktSich = Math.abs(r.height - z.height) <= 2;
        }
        raus.allDay = (() => {
          const a = document.querySelector('.ec-time-grid .ec-all-day');
          if (!a) return 'fehlt';
          const st = getComputedStyle(a);
          return { sichtbar: st.display !== 'none', hoehe: Math.round(a.getBoundingClientRect().height),
                   inhalt: a.querySelectorAll('article').length };
        })();
        return raus;
      }"""
    )


def messen_liste(seite) -> dict:
    return seite.evaluate(
        """() => {
        const zeile = document.querySelector('.ec-list article.ec-event');
        if (!zeile) return { zeile: null };
        const chip = zeile.querySelector('.ec-chip');
        const z = zeile.getBoundingClientRect();
        const c = chip ? chip.getBoundingClientRect() : null;
        const halter = zeile.nextElementSibling;
        const h = halter ? halter.getBoundingClientRect() : null;
        const stZ = getComputedStyle(zeile);
        const stC = chip ? getComputedStyle(chip) : null;
        return {
          zeile: { breite: Math.round(z.width), hoehe: Math.round(z.height),
                   flaeche: stZ.backgroundColor, links: Math.round(z.left) },
          chip: c ? { breite: Math.round(c.width), hoehe: Math.round(c.height),
                      flaeche: stC.backgroundColor, schrift: stC.color,
                      links: Math.round(c.left) } : null,
          balkenBreite: c ? Math.round(c.left - z.left) : null,
          tag: (() => {
            const t = zeile.querySelector('.ec-event-tag');
            if (!t) return null;
            const r = t.getBoundingClientRect();
            const s = getComputedStyle(t);
            return { breite: Math.round(r.width), hoehe: Math.round(r.height),
                     flaeche: s.backgroundColor, eltern: t.parentElement?.className };
          })(),
          aktionen: h ? { gleicheZeile: Math.abs(h.top - z.top) < Math.max(h.height, z.height),
                          obenDifferenz: Math.round(h.top - z.top),
                          anzahlHalter: document.querySelectorAll('.kronos-liste-aktionen-halter').length,
                          anzahlZeilen: document.querySelectorAll('.ec-list article.ec-event').length } : null,
        };
      }"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    for dunkel in (False, True):
        mode = "dunkel" if dunkel else "hell"
        kontext = browser.new_context(viewport={"width": 1440, "height": 900})
        seite = kontext.new_page()
        anmelden(seite)
        thema(seite, dunkel)

        kalender(seite, "Woche")
        messung.setdefault("woche", {})[f"1440-{mode}"] = messen_woche(seite)
        seite.screenshot(path=os.path.join(ZIEL, f"{MARKER}-woche-1440-{mode}.png"))

        kalender(seite, "Liste")
        messung.setdefault("liste", {})[f"1440-{mode}"] = messen_liste(seite)
        seite.screenshot(path=os.path.join(ZIEL, f"{MARKER}-liste-1440-{mode}.png"))
        kontext.close()

    # Mobil 390 — Liste
    kontext = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True,
                                  has_touch=True)
    seite = kontext.new_page()
    anmelden(seite)
    thema(seite, False)
    kalender(seite, "Liste")
    messung.setdefault("liste", {})["390-hell"] = messen_liste(seite)
    seite.screenshot(path=os.path.join(ZIEL, f"{MARKER}-liste-390-hell.png"), full_page=True)
    kontext.close()
    browser.close()

with open(os.path.join(ZIEL, "ux3i4-messung.json"), "w", encoding="utf-8") as fh:
    json.dump(messung, fh, ensure_ascii=False, indent=2)
print(json.dumps(messung, ensure_ascii=False, indent=2)[:4000])
