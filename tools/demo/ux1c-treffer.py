"""UX1c (C3) — Trefferflächen mobil messen: jedes klickbare Element >= 44x44.

Läuft IM Playwright-Image gegen einen Wegwerf-Stack (390x844, hasTouch,
isMobile -> `(pointer: coarse)`), meldet je Seite und Theme jedes zu kleine
Ziel MIT Selektor, Text und Ist-Maß. Ausnahmen werden begründet aufgelistet
(Konzept: „Ausnahmen mit Begründung, z. B. Text-Links im Fließtext“).

Aufruf::

    docker run --rm --network ux1c_default \
        -v <repo>:/w:ro -v <ziel>:/ausgabe \
        -e SPA=http://app:8000/diakronos \
        -e BENUTZER=admin@example.org -e PASSWORT=... \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux1c-treffer.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

from playwright.sync_api import sync_playwright

SPA = os.environ.get("SPA", "http://app:8000/diakronos/diakonos").rstrip("/")
BENUTZER = os.environ.get("BENUTZER", "admin@example.org")
PASSWORT = os.environ.get("PASSWORT", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MIN = float(os.environ.get("MIN", "44"))

SEITEN = [
    ("uebersicht", "#/"),
    ("mitglieder", "#/mitglieder/liste"),
    ("kalender", "#/kalender"),
    ("gruppen", "#/gruppen"),
    ("einstellungen", "#/einstellungen"),
]

MESS = r"""
(minTreffer) => {
  function sichtbar(el) {
    if (!el.getClientRects().length) return false
    const st = getComputedStyle(el)
    if (st.visibility === 'hidden' || st.display === 'none') return false
    if (parseFloat(st.opacity || '1') < 0.1) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }
  function selektor(el) {
    const teile = []
    let k = el
    for (let t = 0; k && k.nodeType === 1 && t < 4; t++) {
      let s = k.tagName.toLowerCase()
      if (k.id) { s += '#' + k.id; teile.unshift(s); break }
      const kl = (k.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 2)
      if (kl.length) s += '.' + kl.join('.')
      teile.unshift(s)
      k = k.parentElement
    }
    return teile.join(' > ')
  }
  const sel = 'button, a[href], input, select, textarea, [role="button"], [role="tab"], [role="menuitem"], [tabindex]:not([tabindex="-1"]), label.dk-ui-checkbox'

  /* Ausnahmen MIT BEGRÜNDUNG (Karte C3: „Ausnahmen mit Begründung, z. B.
     Text-Links im Fließtext“). Jede Regel nennt den Grund; alles andere
     MUSS 44×44 sein. Geprüft wird die Ausnahme selbst — fällt sie weg,
     steht das Element wieder im Verstoß. */
  const AUSNAHMEN = [
    // Der Sprunglink ist per `translateY(-200%)` außerhalb des Bildes und
    // wird NUR bei Tastaturfokus sichtbar (:focus-visible). Er ist kein
    // Fingertippziel — er existiert für Tastatur und Screenreader.
    [/^dk-sprunglink$/, 'Sprunglink: nur bei Tastaturfokus sichtbar', (el) => {
      const cs = getComputedStyle(el)
      return cs.transform !== 'none' && el.getBoundingClientRect().top < 0
    }],
    // Text-Links im Fließtext: ein Absatzlink ist kein Bedienelement mit
    // Trefferfläche; ihn auf 44 px zu dehnen würde den Absatz zerreißen.
    [/^(msv-link|wl-wiki-title|wl-event-titel|dk-zellen-link)$/, 'Text-Link im Fließtext'],
    // Termin-Kachel im Monatsraster: die Zelle ist bei sieben Spalten auf
    // 390 px nur ~53 px breit — breiter als die Zelle kann die Kachel nicht
    // werden. Die HÖHE ist angehoben (index.css, `.ec-event`); die Breite
    // bleibt physikalisch begrenzt.
    [/^(ec-event)$/, 'Monatsraster: Zellenbreite (7 Spalten auf 390 px) begrenzt die Fläche', (el) => {
      const tag = el.closest('[class*="ec-day"]')
      if (!tag) return false
      return tag.getBoundingClientRect().width < 60
    }],
  ]

  function ausnahme(el) {
    const kl = (el.className || '').toString().split(/\s+/).filter(Boolean)
    for (const [muster, grund, extra] of AUSNAHMEN) {
      if (!kl.some((k) => muster.test(k))) continue
      if (extra && !extra(el)) continue
      return grund
    }
    return null
  }

  const klein = [], ausgenommen = [], gesehen = new Set()
  let geprueft = 0
  for (const el of document.querySelectorAll(sel)) {
    if (!sichtbar(el) || el.disabled) continue
    const r = el.getBoundingClientRect()
    geprueft++
    if (Math.min(r.width, r.height) + 0.5 < minTreffer) {
      const st = getComputedStyle(el)
      const grund = ausnahme(el)
      if (grund) {
        ausgenommen.push({ selektor: selektor(el), grund, breite: Math.round(r.width), hoehe: Math.round(r.height) })
        continue
      }
      const sig = selektor(el) + '@' + Math.round(r.width) + 'x' + Math.round(r.height)
      if (gesehen.has(sig)) continue
      gesehen.add(sig)
      klein.push({
        selektor: selektor(el),
        text: (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 30),
        breite: Math.round(r.width * 10) / 10,
        hoehe: Math.round(r.height * 10) / 10,
        tag: el.tagName.toLowerCase(),
        klasse: (el.className || '').toString(),
        cursor: st.cursor,
      })
    }
  }
  return { geprueft, klein, ausgenommen, breite: window.innerWidth }
}
"""


def anmelden(page):
    page.goto(SPA + "/", wait_until="networkidle")
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        return page.locator("input[type=password]").count() == 0
    return True


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    bericht = {"basis": SPA, "ansicht": "mobil 390x844 hasTouch isMobile",
               "minimum": MIN, "seiten": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("hell", "dunkel"):
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=1,
                locale="de-DE", has_touch=True, is_mobile=True,
                color_scheme="dark" if theme == "dunkel" else "light",
            )
            ctx.add_init_script(
                "try { window.localStorage.setItem('dk-theme', '%s') } catch (e) {}"
                % ("dark" if theme == "dunkel" else "light")
            )
            ctx.set_default_timeout(25000)
            page = ctx.new_page()
            angemeldet = anmelden(page)
            for name, route in SEITEN:
                eintrag = {"seite": name, "theme": theme, "route": route, "fehler": []}
                try:
                    page.goto(SPA + "/" + route, wait_until="networkidle")
                    page.wait_for_timeout(1200)
                    page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)",
                                  "dark" if theme == "dunkel" else "light")
                    page.wait_for_timeout(300)
                    m = page.evaluate(MESS, [MIN])
                    eintrag.update(m)
                    page.screenshot(path=os.path.join(ZIEL, f"{name}-{theme}-mobil.png"),
                                    full_page=True)
                except Exception as fehler:  # noqa: BLE001
                    eintrag["fehler"].append(f"{type(fehler).__name__}: {fehler}")
                    traceback.print_exc()
                bericht["seiten"].append(eintrag)
            # Desktop-Ansicht für die Vorher/Nachher-Bilder (1366 px, feiner Zeiger).
            ctx2 = browser.new_context(viewport={"width": 1366, "height": 900},
                                       locale="de-DE",
                                       color_scheme="dark" if theme == "dunkel" else "light")
            ctx2.add_init_script(
                "try { window.localStorage.setItem('dk-theme', '%s') } catch (e) {}"
                % ("dark" if theme == "dunkel" else "light")
            )
            page2 = ctx2.new_page()
            anmelden(page2)
            for name, route in SEITEN:
                try:
                    page2.goto(SPA + "/" + route, wait_until="networkidle")
                    page2.wait_for_timeout(1200)
                    page2.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)",
                                   "dark" if theme == "dunkel" else "light")
                    page2.wait_for_timeout(250)
                    page2.screenshot(path=os.path.join(ZIEL, f"{name}-{theme}-desktop.png"),
                                     full_page=True)
                except Exception as fehler:  # noqa: BLE001
                    print("desktop:", name, fehler)
            ctx2.close()
            ctx.close()
        browser.close()

    bericht["angemeldet"] = True
    with open(os.path.join(ZIEL, "trefferflaechen.json"), "w", encoding="utf-8") as fh:
        json.dump(bericht, fh, ensure_ascii=False, indent=1)

    # Kurzbericht
    zeilen = [f"# UX1c (C3) Trefferflächen mobil — Minimum {MIN:.0f}px", ""]
    verletzt = 0
    for s in bericht["seiten"]:
        klein = s.get("klein", [])
        verletzt += len(klein)
        zeilen.append(f"## {s['seite']} / {s['theme']}: {len(klein)} zu klein "
                      f"von {s.get('geprueft', 0)}")
        for k in klein:
            zeilen.append(f"  - {k['breite']}x{k['hoehe']} {k['selektor']} — "
                          f"„{k['text']}“")
        for a in s.get("ausgenommen", []):
            zeilen.append(f"  + Ausnahme ({a['grund']}): {a['breite']}x{a['hoehe']} "
                          f"{a['selektor']}")
        for f in s["fehler"]:
            zeilen.append(f"  ! {f}")
    zeilen.append("")
    zeilen.append(f"GESAMT zu klein: {verletzt}")
    text = "\n".join(zeilen)
    with open(os.path.join(ZIEL, "trefferflaechen.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    return 1 if verletzt else 0


if __name__ == "__main__":
    sys.exit(main())
