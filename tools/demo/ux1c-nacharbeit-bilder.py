"""UX1c Nacharbeit (Review 07.11., Punkt 7) — Bilder + Messung mobil 390 px.

Zeigt die drei Stellen, an denen die Nacharbeit Wirkung zeigen muss:

  1. Kalender, Ansicht MONAT  — Termin-Kacheln muessen sichtbar sein
     (Review-Punkt 3: `min-height` an `.ec-event` liess sie verschwinden).
  2. Kalender, Ansicht LISTE  — Zeilhoehe der Termine.
  3. Formular „Neue Gruppe“   — Feldschrift 16 px (OP-HANDY-14, Review-Punkt 2).

Danach laeuft die C3-Messung ueber die fuenf Seiten (ohne die gestrichenen
Regeln). Laeuft IM Playwright-Image gegen einen Wegwerf-Stack.

Aufruf::

    docker run --rm --network ux1c_default \
        -v <repo>:/w:ro -v <ziel>:/ausgabe \
        -e SPA=http://app:8000/diakronos/diakonos \
        -e BENUTZER=admin@example.org -e PASSWORT=... \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux1c-nacharbeit-bilder.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

from playwright.sync_api import sync_playwright

# Die SPA-Wurzel braucht den abschliessenden Schraegstrich (ohne ihn
# antwortet der Server 404, weil der Pfad dann als Datei gesucht wird).
SPA = os.environ.get("SPA", "http://app:8000/diakronos/diakonos/").rstrip("/") + "/"
BENUTZER = os.environ.get("BENUTZER", "admin@example.org")
PASSWORT = os.environ.get("PASSWORT", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MIN = float(os.environ.get("MIN", "44"))

# Messung: jedes klickbare Element mind. MIN x MIN. Ausnahmen MIT BEGRUENDUNG;
# jede Ausnahme prueft sich selbst — faellt der Grund weg, zaehlt sie wieder.
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

  const AUSNAHMEN = [
    // Der Sprunglink ist per `translateY(-200%)` ausserhalb des Bildes und
    // wird NUR bei Tastaturfokus sichtbar — kein Fingertippziel.
    [/^dk-sprunglink$/, 'Sprunglink: nur bei Tastaturfokus sichtbar', (el) => {
      const cs = getComputedStyle(el)
      return cs.transform !== 'none' && el.getBoundingClientRect().top < 0
    }],
    // Text-Links im Fliesstext: kein Bedienelement mit Trefferflaeche.
    [/^(msv-link|wl-wiki-title|wl-event-titel|dk-zellen-link)$/, 'Text-Link im Fliesstext'],
    // Termin-Kachel im Monatsraster (Review-Punkt 3): die Zelle ist bei sieben
    // Spalten auf 390 px nur ~53 px breit, und die Hoehe folgt dem Raster —
    // eine Hoehenregel liess die Termine ganz verschwinden. Die Kachel bleibt
    // deshalb, wie die Bibliothek sie zeichnet.
    // `ec-event` traegt je nach Zustand weitere Klassen (u. a.
    // `ec-event-draggable`) — die Pruefung haengt an der Wortgrenze, nicht am
    // ganzen Namen. `.ec-event-dot-style` (Punkt-Darstellung) ist NICHT
    // gemeint und bleibt ein Verstoss, wenn es zu klein ist.
    [/^ec-event(?![\w-]*dot-style)[\w-]*$/, 'Monatsraster: Kachel folgt Zellbreite und Rasterzeile (7 Spalten auf 390 px)', (el) => {
      // Begruendung mit BELEG, nicht mit Klassenname: gemessen (C3) ist die
      // Kachel 47x22 px. Die BREITE ist physikalisch begrenzt — das Raster
      // teilt die 374 px Kalenderbreite durch sieben Spalten (≈53 px) und
      // zieht Innenabstand ab; eine Kachel kann nicht breiter sein als ihre
      // Spalte. Die HOEHE vergibt die Rasterzeile (Monatsansicht auf 844 px
      // Hoehe: sechs Wochen muessen ins Bild, sonst verschwinden die Termine
      // ganz — genau der Review-Befund zu `min-height`).
      // Beides wird AM ELEMENT geprueft: waechst die Kachel ueber 60 px
      // Breite (Querformat, Tablet, Wochen-/Listenansicht), greift die
      // Ausnahme NICHT mehr und sie zaehlt wieder als Verstoss.
      const r = el.getBoundingClientRect()
      return r.width < 60
    }],
    // „+N weitere“ ist ein Textlink IN der Tagesspalte (~53 px breit) und
    // traegt selbst einen Absatz-Zeilenabstand.
    [/^ec-more-link$/, 'Textlink in der Tagesspalte (Monatsraster)'],
  ]

  function ausnahme(el) {
    const kl = (el.className || '').toString().split(/\s+/).filter(Boolean)
    for (const [muster, grund, extra] of AUSNAHMEN) {
      if (!kl.some((k) => muster.test(k))) continue
      if (extra && !extra(el)) continue
      return grund
    }
    // Reiter „+N weitere“ der Bibliothek traegt keine Klasse am Link selbst.
    if (el.closest('.ec-day-foot')) {
      const tag = el.closest('[class*="ec-day"]')
      if (tag && tag.getBoundingClientRect().width < 60) {
        return 'Textlink in der Tagesspalte (Monatsraster)'
      }
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
      const grund = ausnahme(el)
      if (grund) {
        ausgenommen.push({ selektor: selektor(el), grund,
                           breite: Math.round(r.width), hoehe: Math.round(r.height) })
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
      })
    }
  }
  return { geprueft, klein, ausgenommen, breite: window.innerWidth }
}
"""

# Prueft die drei Nacharbeits-Stellen am laufenden Browser.
PRUEF = r"""
() => {
  const out = {}
  // (a) Termin-Kacheln im Monatsraster: wie viele sind sichtbar, wie hoch?
  const kacheln = [...document.querySelectorAll('.ec-event')].filter((el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  })
  out.kacheln = kacheln.length
  out.kachel_hoehen = kacheln.slice(0, 12).map((el) => Math.round(el.getBoundingClientRect().height))
  out.kachel_titel = kacheln.slice(0, 6).map((el) => (el.textContent || '').trim().slice(0, 30))
  // Kette der Kachel bis zum Raster: welches Element gibt Breite/Hoehe vor?
  if (kacheln.length) {
    const kette = []
    let k = kacheln[0]
    for (let i = 0; k && i < 6; i++) {
      const r = k.getBoundingClientRect()
      kette.push({ tag: k.tagName.toLowerCase(),
                   klasse: (k.className || '').toString().slice(0, 40),
                   breite: Math.round(r.width), hoehe: Math.round(r.height) })
      k = k.parentElement
    }
    out.kachel_kette = kette
  }
  // (b) Feldschrift (OP-HANDY-14): alle Felder im Formular.
  const felder = [...document.querySelectorAll('input, select, textarea')]
    .filter((el) => el.getBoundingClientRect().height > 0)
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      typ: el.getAttribute('type') || '',
      klasse: (el.className || '').toString().slice(0, 60),
      schrift: getComputedStyle(el).fontSize,
      hoehe: Math.round(el.getBoundingClientRect().height),
    }))
  out.felder = felder
  // (c) Kopfleiste des Kalenders: bricht sie um? (Review-Punkt 3)
  const kopf = document.querySelector('.kronos-topbar, .kronos-toolbar, [class*="topbar"]')
  if (kopf) {
    const r = kopf.getBoundingClientRect()
    out.kopf = { hoehe: Math.round(r.height), breite: Math.round(r.width) }
  }
  return out
}
"""


def anmelden(page):
    page.goto(SPA, wait_until="networkidle")
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2500)
        return page.locator("input[type=password]").count() == 0
    return True


def ansicht(page, wert):
    """Kalender-Ansicht ueber das Dropdown stellen (Werte wie im Select)."""
    page.select_option("#view-selector", wert)
    page.wait_for_timeout(1500)


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    bericht = {"basis": SPA, "ansicht": "mobil 390x844 hasTouch isMobile",
               "minimum": MIN, "bilder": [], "seiten": [], "pruefungen": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("hell", "dunkel"):
            dunkel = theme == "dunkel"
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=1,
                locale="de-DE", has_touch=True, is_mobile=True,
                color_scheme="dark" if dunkel else "light",
            )
            ctx.add_init_script(
                "try { window.localStorage.setItem('dk-theme', '%s') } catch (e) {}"
                % ("dark" if dunkel else "light"))
            ctx.set_default_timeout(25000)
            page = ctx.new_page()
            angemeldet = anmelden(page)
            bericht["angemeldet"] = angemeldet

            def foto(name):
                pfad = os.path.join(ZIEL, f"{name}-{theme}-mobil.png")
                page.screenshot(path=pfad, full_page=True)
                bericht["bilder"].append(pfad)

            # 1./2. Kalender: Monat und Liste
            for name, wert in (("kalender-monat", "dayGridMonth"),
                               ("kalender-liste", "listMonth")):
                try:
                    page.goto(SPA + "#/kalender", wait_until="networkidle")
                    page.wait_for_timeout(1500)
                    page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)",
                                  "dark" if dunkel else "light")
                    ansicht(page, wert)
                    foto(name)
                    bericht["pruefungen"][f"{name}/{theme}"] = page.evaluate(PRUEF)
                except Exception as fehler:  # noqa: BLE001
                    print(f"{name}/{theme}:", fehler)
                    traceback.print_exc()

            # 3. Formular mobil: „Neue Gruppe“ (Felder, Knoepfe, Kaestchen)
            try:
                page.goto(SPA + "#/gruppen", wait_until="networkidle")
                page.wait_for_timeout(1500)
                page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)",
                              "dark" if dunkel else "light")
                # Beschriftung nach dem Begriffskatalog: „Gruppe anlegen“
                knopf = page.get_by_role("button", name="Gruppe anlegen")
                if knopf.count():
                    knopf.first.click()
                    page.wait_for_timeout(1200)
                    foto("formular-gruppe-anlegen")
                    bericht["pruefungen"][f"formular/{theme}"] = page.evaluate(PRUEF)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(400)
                else:
                    print("Knopf „Gruppe anlegen“ nicht gefunden")
            except Exception as fehler:  # noqa: BLE001
                print("formular:", fehler)
                traceback.print_exc()

            # 4. C3-Messung ueber die fuenf Seiten
            for name, route in (("uebersicht", "#/"), ("mitglieder", "#/mitglieder/liste"),
                                ("kalender", "#/kalender"), ("gruppen", "#/gruppen"),
                                ("einstellungen", "#/einstellungen")):
                eintrag = {"seite": name, "theme": theme, "route": route, "fehler": []}
                try:
                    page.goto(SPA + route, wait_until="networkidle")
                    page.wait_for_timeout(1200)
                    page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)",
                                  "dark" if dunkel else "light")
                    page.wait_for_timeout(300)
                    eintrag.update(page.evaluate(MESS, [MIN]))
                    foto(f"c3-{name}")
                except Exception as fehler:  # noqa: BLE001
                    eintrag["fehler"].append(f"{type(fehler).__name__}: {fehler}")
                    traceback.print_exc()
                bericht["seiten"].append(eintrag)
            ctx.close()
        browser.close()

    with open(os.path.join(ZIEL, "nacharbeit.json"), "w", encoding="utf-8") as fh:
        json.dump(bericht, fh, ensure_ascii=False, indent=1)

    zeilen = [f"# UX1c Nacharbeit — mobil 390 px, Minimum {MIN:.0f} px", ""]
    verletzt = 0
    for s in bericht["seiten"]:
        klein = s.get("klein", [])
        verletzt += len(klein)
        zeilen.append(f"## {s['seite']} / {s['theme']}: {len(klein)} zu klein "
                      f"von {s.get('geprueft', 0)}")
        for k in klein:
            zeilen.append(f"  - {k['breite']}x{k['hoehe']} {k['selektor']} — „{k['text']}“")
        for a in s.get("ausgenommen", []):
            zeilen.append(f"  + Ausnahme ({a['grund']}): {a['breite']}x{a['hoehe']} "
                          f"{a['selektor']}")
        for f in s["fehler"]:
            zeilen.append(f"  ! {f}")
    zeilen.append("")
    zeilen.append(f"GESAMT zu klein: {verletzt}")
    zeilen.append("")
    zeilen.append("## Nacharbeits-Stellen (am Browser gemessen)")
    for k, v in bericht["pruefungen"].items():
        if "kacheln" in v:
            zeilen.append(f"- {k}: {v['kacheln']} Termin-Kacheln sichtbar, "
                          f"Hoehen {v['kachel_hoehen']}, Titel {v['kachel_titel']}")
        if v.get("felder"):
            ohne16 = [f for f in v["felder"] if f["schrift"] not in ("16px",)]
            zeilen.append(f"- {k}: {len(v['felder'])} Felder, davon {len(ohne16)} nicht 16 px"
                          + (f" → {ohne16[:5]}" if ohne16 else ""))
        if v.get("kopf"):
            zeilen.append(f"- {k}: Kopfleiste {v['kopf']['hoehe']} px hoch")
    text = "\n".join(zeilen)
    with open(os.path.join(ZIEL, "nacharbeit.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    return 1 if verletzt else 0


if __name__ == "__main__":
    sys.exit(main())
