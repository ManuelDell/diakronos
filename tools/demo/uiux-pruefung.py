"""
UX1i — Automatischer Bildschirmtest (macht die UI-Release-Checkliste messbar).

Läuft IM Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
gegen einen laufenden Stack und LIEST NUR (keine Schreibvorgänge außer der
Anmeldung). Für jede Hauptseite werden zwei Ansichten geprüft:

    Desktop  1440 × 900, feiner Zeiger      hell + dunkel
    Mobil     390 × 844, hasTouch, coarse   hell + dunkel

Prüfpunkte je Ansicht (Karte UX1i):

  (1) Kontrast Text/Hintergrund >= 4,5:1 — berechnet aus den berechneten
      Stilen (getComputedStyle), Hintergrund durch die Vorfahrenkette
      zusammengerechnet; Verstöße mit Selektor, Text und Ist-Wert.
  (2) Trefferflächen >= 44 px — nur Mobil (pointer: coarse), wie die
      Token-Regel --control-h 40 px / 44 px bei grobem Zeiger.
  (3) Anzahl sichtbarer Primärknöpfe (.dk-ui-btn--primary, sichtbar und
      nicht abgeschaltet) — Soll: genau 1 je Ansicht.
  (4) Graustufen-Screenshot je Ansicht.
  (5) Horizontaler Überlauf bei 375 px (gesondert gemessen, eigenes Fenster).
  (6) Netzwerkfehler (>= 400) und Konsolenfehler je Ansicht.

Ergebnis: JSON (`ergebnis.json`) + kurzer Markdown-Bericht (`bericht.md`) im
Zielverzeichnis. Rückgabewert 1, sobald ein Prüfpunkt verletzt ist — so bricht
ein Regress in der CI laut ab.

Aufruf (Beispiel, Netz des eigenen Wegwerf-Stacks):

    docker run --rm --network ux1i_default -v "$PWD":/w -v /ziel:/ausgabe \
        --user 1000:1000 \
        -e BASE=http://app:8000/diakronos -e ZIEL=/ausgabe \
        -e ADMIN_EMAIL=admin@example.org -e ADMIN_PASS=… \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uiux-pruefung.py

Ohne Zugang (nur Anmeldeseite): ADMIN_PASS leer lassen — dann wird nur die
Anmeldeseite geprüft (die übrigen Seiten sind ohne Sitzung nicht erreichbar).
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
UEBERLAUF_BREITE = 375

# Die SPA hängt NICHT an der Wurzel, sondern an `/diakonos` (spa.py:SPA_PREFIX),
# ggf. unter dem Betriebs-Präfix (`DIAKRONOS_BASE_PATH`): `BASE` ist der
# Betriebsteil, `SPA` die eigentliche App-Adresse. `BASE` allein liefert 404 —
# das ist richtig so (die Wurzel gehört der statischen Website).
SPA = os.environ.get("SPA", BASE + "/diakonos").rstrip("/")

# Mindestwerte der Checkliste (Prinzip Ä4 „Kontrast >= 4,5:1“, K4 „Touch >= 44 px“)
KONTRAST_MIN = 4.5
TREFFER_MIN = 44.0

# Hauptseiten (Karte UX1i). `vorbereiten` ist ein optionaler Klick nach dem
# Laden (z. B. im Kalender ein Monat weiter, damit echte Einträge sichtbar sind).
SEITEN: list[tuple[str, str | None, str | None]] = [
    ("uebersicht", "#/", None),
    ("mitglieder", "#/mitglieder/liste", None),
    ("kalender", "#/kalender", None),
    ("gruppen", "#/gruppen", None),
    ("dienstplan", "#/dienstplan", None),
    ("plaene", "#/planrahmen", None),
    ("lieder", "#/lieder", None),
    ("beitraege", "#/beitraege", None),
    ("wiki", "#/wiki", None),
    ("ressourcen", "#/ressourcen", None),
    ("einstellungen", "#/einstellungen", None),
    ("einstellungen-gemeinde", "#/einstellungen/gemeinde", None),
    ("einstellungen-anmeldung", "#/einstellungen/anmeldung", None),
    ("einstellungen-rollen", "#/einstellungen/rollen", None),
    ("einstellungen-datenschutz", "#/einstellungen/datenschutz", None),
    ("einstellungen-datensicherung", "#/einstellungen/datensicherung", None),
    ("website", "#/website", None),
    ("anmeldung", None, None),          # ohne Sitzung: die Anmeldemaske selbst
]

ANSICHTEN = (
    # (Name, Breite, Höhe, hastouch)
    ("desktop", 1440, 900, False),
    ("mobil", 390, 844, True),
)
THEMES = ("hell", "dunkel")

# ── Reine Rechen-Helfer (ohne Browser) ───────────────────────────────────────
# Sie stehen bewusst hier und nicht im Mess-Skript: so prüft
# `frontend/tests/ux1i-*.test.mjs` GENAU diesen Code im Docker-Build, ohne
# einen Browser zu brauchen. Das Skript im Browser (MESS_SKRIPT) führt
# dieselbe Formel aus — es kann nur `getComputedStyle` auslesen.

def zerlege(farbe):
    """'rgb(1, 2, 3)' / 'rgba(1,2,3,.5)' → (r, g, b, a) oder None."""
    treffer = re.match(r"rgba?\(([^)]+)\)", str(farbe or "").strip())
    if not treffer:
        return None
    teile = [t for t in re.split(r"[,\s/]+", treffer.group(1).strip()) if t]
    if len(teile) < 3:
        return None
    try:
        werte = [float(t) for t in teile]
    except ValueError:
        return None
    alpha = werte[3] if len(werte) > 3 else 1.0
    return (werte[0], werte[1], werte[2], alpha)


def ueber(vorn, hinten):
    """Quelle `vorn` über Ziel `hinten` legen (Alpha-Blending in sRGB)."""
    a = vorn[3] + hinten[3] * (1 - vorn[3])
    if a == 0:
        return (0.0, 0.0, 0.0, 0.0)
    misch = [(vorn[i] * vorn[3] + hinten[i] * hinten[3] * (1 - vorn[3])) / a for i in range(3)]
    return (misch[0], misch[1], misch[2], a)


def kante(wert):
    """sRGB-Kanal → linearer Anteil (WCAG 2.x, 1.4.3)."""
    v = wert / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def leuchtdichte(farbe):
    """Relative Leuchtdichte L einer Farbe (0 = schwarz, 1 = weiß)."""
    return 0.2126 * kante(farbe[0]) + 0.7152 * kante(farbe[1]) + 0.0722 * kante(farbe[2])


def kontrast(vorn, hinten):
    """Kontrastverhältnis zweier (deckender) Farben — 1:1 bis 21:1."""
    hell, dunkel = sorted((leuchtdichte(vorn), leuchtdichte(hinten)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


def text_kontrast(schriftfarbe, grundfarben):
    """
    Kontrast der Schrift über einer Kette von Grundflächen (Element bis Wurzel,
    vorn zuerst). Teilweise durchsichtige Flächen werden von unten nach oben
    gemischt; fehlt eine Fläche, gilt Weiß (Papier) — wie im Mess-Skript.
    """
    grund = (255.0, 255.0, 255.0, 1.0)
    for f in reversed(list(grundfarben)):
        grund = ueber(f, grund) if f[3] > 0 else grund
    schrift = ueber(schriftfarbe, grund)
    return kontrast(schrift, grund)


def verstoesse(wert, minimum=KONTRAST_MIN):
    """Kurzform für Berichte: kein Befund → [], sonst der Wert."""
    return [] if wert >= minimum else [round(wert, 2)]


# ── Prüf-Logik im Browser ────────────────────────────────────────────────────
# Der Code läuft per page.evaluate() und liefert reine Zahlen/Listen zurück.
#
# UX1i2 (Befund 2026-11-04, „36 von 36 ohne Verstoß“ trotz 28-px-Knöpfen):
# Die Parameter stehen als ENTSTRUKTURIERENDES Array in der Signatur,
# `([minKontrast, minTreffer]) => {…}`. Mit zwei Einzelparametern
# (`(a, b) => …`) übergibt playwright 1.62 den Python-Wert `[4.5, 44.0]` nur
# an den ERSTEN Parameter — `b` ist dann `undefined`. Folge: jeder Vergleich
# `… < minTreffer` (und `wert < minKontrast`) war gegen `undefined` falsch,
# der Bericht meldete 0 Verstöße bei 0 Treffern. Gegenprobe:
# `tools/demo/ux1i2-probe.py` (Testseite mit bekannt 28-px-Knopf) und der
# Wächter `frontend/tests/ux1i2-*.test.mjs`.
MESS_SKRIPT = r"""
([minKontrast, minTreffer]) => {
  // ── Farb-Hilfen ──────────────────────────────────────────────────────────
  const zerlege = (farbe) => {
    const m = String(farbe || '').match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const teile = m[1].split(/[,\s/]+/).filter(Boolean).map(Number)
    if (teile.length < 3) return null
    return { r: teile[0], g: teile[1], b: teile[2], a: teile.length > 3 ? teile[3] : 1 }
  }
  const ueber = (vorn, hinten) => {
    // Quelle über Ziel legen (einfaches Alpha-Blending in sRGB).
    const a = vorn.a + hinten.a * (1 - vorn.a)
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 }
    const misch = (x, y) => (x * vorn.a + y * hinten.a * (1 - vorn.a)) / a
    return { r: misch(vorn.r, hinten.r), g: misch(vorn.g, hinten.g), b: misch(vorn.b, hinten.b), a }
  }
  const lum = (c) => {
    const k = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * k(c.r) + 0.7152 * k(c.g) + 0.0722 * k(c.b)
  }
  const kontrast = (a, b) => {
    const la = lum(a), lb = lum(b)
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
  }

  /** Grundfarbe eines Elements: eigene Fläche durch die Vorfahren bis zur Wurzel. */
  function grundfarbe(el) {
    const stapel = []
    let knoten = el
    while (knoten && knoten.nodeType === 1) {
      const st = getComputedStyle(knoten)
      const f = zerlege(st.backgroundColor)
      if (f && f.a > 0) {
        stapel.push(f)
        if (f.a >= 1) break
      }
      // Hintergrundbilder (Verläufe) sind hier nicht auswertbar — dann gilt
      // die erste deckende Fläche darunter (konservativ, kein stiller Fehler).
      knoten = knoten.parentElement
    }
    // Von unten (Wurzel/letzte deckende Fläche) nach oben mischen.
    let grund = { r: 255, g: 255, b: 255, a: 1 }
    for (let i = stapel.length - 1; i >= 0; i--) grund = ueber(stapel[i], grund)
    return grund
  }

  /** Textknoten-Blätter (Elemente, die selbst Text zeigen). */
  function textElemente() {
    const ergebnis = []
    const lauf = (el) => {
      for (const kind of el.childNodes) {
        if (kind.nodeType === 3) {
          if (kind.textContent.trim()) ergebnis.push(el)
          continue
        }
        if (kind.nodeType !== 1) continue
        const tag = kind.tagName.toLowerCase()
        if (tag === 'script' || tag === 'style' || tag === 'noscript') continue
        lauf(kind)
      }
    }
    lauf(document.body)
    return ergebnis
  }

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
    let knoten = el
    for (let tiefe = 0; knoten && knoten.nodeType === 1 && tiefe < 4; tiefe++) {
      let s = knoten.tagName.toLowerCase()
      if (knoten.id) { s += '#' + knoten.id; teile.unshift(s); break }
      const klassen = (knoten.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 2)
      if (klassen.length) s += '.' + klassen.join('.')
      teile.unshift(s)
      knoten = knoten.parentElement
    }
    return teile.join(' > ')
  }

  // ── (1) Kontrast ─────────────────────────────────────────────────────────
  const verstoesse = []
  const gesehen = new Set()
  let geprueft = 0
  for (const el of textElemente()) {
    if (!sichtbar(el)) continue
    const st = getComputedStyle(el)
    const vorn = zerlege(st.color)
    if (!vorn) continue
    const grund = grundfarbe(el)
    const text = ueber(vorn, grund)
    const wert = kontrast(text, grund)
    geprueft++
    // Nur die schlechtesten Stellen je Selektor melden (Rauschen begrenzen).
    const sig = selektor(el)
    if (wert < minKontrast && !gesehen.has(sig)) {
      gesehen.add(sig)
      verstoesse.push({
        selektor: sig,
        text: (el.textContent || '').trim().slice(0, 40),
        kontrast: Math.round(wert * 100) / 100,
        schriftfarbe: st.color,
        grundflaeche: `rgba(${Math.round(grund.r)}, ${Math.round(grund.g)}, ${Math.round(grund.b)}, ${grund.a})`,
        schriftgroesse: st.fontSize,
        fett: st.fontWeight,
      })
    }
  }
  verstoesse.sort((a, b) => a.kontrast - b.kontrast)

  // ── (2) Trefferflächen (nur Mobil/coarse geprüft, Messung immer) ─────────
  const trefferSelektoren = 'button, a[href], input, select, textarea, [role="button"], [role="tab"], [role="menuitem"], [tabindex]:not([tabindex="-1"])'
  const zuKlein = []
  const zuKleinSig = new Set()
  let trefferGeprueft = 0
  for (const el of document.querySelectorAll(trefferSelektoren)) {
    if (!sichtbar(el)) continue
    if (el.disabled) continue
    // Versteckte Feld-Eingaben (Checkbox-Muster) zählen nicht.
    const r = el.getBoundingClientRect()
    trefferGeprueft++
    if (Math.min(r.width, r.height) + 0.5 < minTreffer) {
      const sig = selektor(el) + '@' + Math.round(r.width) + 'x' + Math.round(r.height)
      if (zuKleinSig.has(sig)) continue
      zuKleinSig.add(sig)
      zuKlein.push({
        selektor: selektor(el),
        text: (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 30),
        breite: Math.round(r.width * 10) / 10,
        hoehe: Math.round(r.height * 10) / 10,
      })
    }
  }

  // ── (3) Sichtbare Primärknöpfe ───────────────────────────────────────────
  const primaer = [...document.querySelectorAll('.dk-ui-btn--primary')]
    .filter((el) => sichtbar(el) && !el.disabled)
    .map((el) => ({ selektor: selektor(el), text: (el.textContent || '').trim().slice(0, 40) }))

  return {
    kontrast: { geprueft, verstoesse, grenze: minKontrast },
    treffer: { geprueft: trefferGeprueft, zu_klein: zuKlein, grenze: minTreffer },
    primaer,
    ueberlauf: {
      breite: document.documentElement.scrollWidth,
      fenster: window.innerWidth,
      ueberlauf: document.documentElement.scrollWidth > window.innerWidth + 1,
    },
    titel: document.title,
  }
}
"""

ZAEHL_SKRIPT = r"""
([minTreffer]) => {
  const sichtbar = (el) => {
    if (!el.getClientRects().length) return false
    const st = getComputedStyle(el)
    if (st.visibility === 'hidden' || st.display === 'none') return false
    if (parseFloat(st.opacity || '1') < 0.1) return false
    return true
  }
  const treffer = 'button, a[href], input, select, textarea, [role="button"], [role="tab"], [role="menuitem"], [tabindex]:not([tabindex="-1"])'
  let klein = 0, geprueft = 0
  const beispiele = []
  for (const el of document.querySelectorAll(treffer)) {
    if (!sichtbar(el) || el.disabled) continue
    const r = el.getBoundingClientRect()
    geprueft++
    if (Math.min(r.width, r.height) + 0.5 < minTreffer) {
      klein++
      if (beispiele.length < 10) beispiele.push(el.tagName.toLowerCase() + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (el.textContent || '').trim().slice(0, 20))
    }
  }
  return {
    geprueft, klein, beispiele,
    scrollbreite: document.documentElement.scrollWidth,
    fenster: window.innerWidth,
  }
}
"""


def neuer_kontext(browser, breite, hoehe, hastouch, dunkel):
    ctx = browser.new_context(
        viewport={"width": breite, "height": hoehe},
        device_scale_factor=1,
        locale="de-DE",
        color_scheme="dark" if dunkel else "light",
        has_touch=hastouch,
        # UX1i2: `is_mobile` gehört zum Mobil-Kontext. Ohne es meldet Chromium
        # für `(pointer: coarse)` schon mit `has_touch` wahr, aber die
        # Touch-Regeln der App (`@media (pointer: coarse)`) und der
        # Trefferflächen-Sollwert hängen an GENAU diesem Zeiger-Merkmal —
        # ein Kontext, der Mobil nachstellt ohne Mobil zu sein, misst die
        # falsche Oberfläche (Befund UX1i2).
        is_mobile=hastouch,
    )
    ctx.set_default_timeout(20000)
    if dunkel:
        # Das Theme der App kommt aus localStorage (composables/theme.mjs) bzw.
        # aus prefers-color-scheme — beides gesetzt, damit der Startwert sicher
        # dunkel ist.
        ctx.add_init_script(
            "try { window.localStorage.setItem('dk-theme', 'dark') } catch (e) {}"
        )
    else:
        ctx.add_init_script(
            "try { window.localStorage.setItem('dk-theme', 'light') } catch (e) {}"
        )
    return ctx


def anmelden(page):
    page.goto(SPA + "/", wait_until="networkidle")
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
    return page.locator("input[type=password]").count() == 0


def sammeln(page, ansicht, seite):
    """Hängt Fehler-Listener an und liefert die Sammellisten."""
    konsolen: list[str] = []
    netz: list[str] = []

    def konsole(msg):
        if msg.type != "error":
            return
        text = msg.text
        # Der Dev-Modus-Endpunkt antwortet bei abgeschaltetem Dev-Modus mit
        # 404 — das ist der Normalfall (composables/useDevmodus.js fängt es ab).
        if "devmodus.api.uebersicht" in text:
            return
        if "Failed to load resource" in text and "404" in text:
            return
        konsolen.append(text[:300])

    def antwort(resp):
        if resp.status < 400:
            return
        if "devmodus.api.uebersicht" in resp.url:
            return
        # Abgemeldete Prüfseiten fragen teils Weiterleitungen ab; alles >= 400
        # ist ein Befund.
        netz.append(f"{resp.status} {resp.request.method} {resp.url[:200]}")

    page.on("console", konsole)
    page.on("pageerror", lambda exc: konsolen.append(("pageerror: " + str(exc))[:300]))
    page.on("response", antwort)
    return konsolen, netz


def screenshot_graustufen(page, pfad):
    """Screenshot nach Graustufen wandeln (Prinzip „Graustufen-Test“)."""
    page.screenshot(path=pfad, full_page=False)
    try:
        from PIL import Image

        with Image.open(pfad) as bild:
            bild.convert("L").save(pfad)
    except Exception as fehler:  # Pillow fehlt im Image? Dann bleibt das Farbbild.
        print("WARNUNG: Graustufen-Wandlung fehlgeschlagen:", fehler, file=sys.stderr)


def pruefe_ansicht(browser, seite, route, breite, hoehe, hastouch, theme, bildpfad):
    dunkel = theme == "dunkel"
    ctx = neuer_kontext(browser, breite, hoehe, hastouch, dunkel)
    ergebnis = {"seite": seite, "ansicht": "mobil" if hastouch else "desktop",
                "theme": theme, "route": route, "fehler": []}
    try:
        page = ctx.new_page()
        konsolen, netz = sammeln(page, ergebnis["ansicht"], seite)
        if route is None:
            page.goto(SPA + "/", wait_until="networkidle")
            page.wait_for_timeout(600)
            # Ohne Sitzung muss die Anmeldemaske stehen bleiben.
            ergebnis["angemeldet"] = page.locator("input[type=password]").count() > 0
        else:
            if not anmelden(page):
                ergebnis["fehler"].append("Anmeldung fehlgeschlagen")
            page.goto(SPA + "/" + route, wait_until="networkidle")
            page.wait_for_timeout(900)
            ergebnis["angemeldet"] = True
        # Hell/Dunkel am Wurzelelement erzwingen (die App setzt data-theme).
        page.evaluate(
            "(t) => document.documentElement.setAttribute('data-theme', t)",
            "dark" if dunkel else "light",
        )
        page.wait_for_timeout(250)

        messung = page.evaluate(MESS_SKRIPT, [KONTRAST_MIN, TREFFER_MIN])
        # Selbstprüfung (UX1i2): kamen die Grenzwerte im Browser wirklich an?
        # Fehlt einer, prüfte der Lauf gegen `undefined` und meldete still
        # „0 Verstöße“ — genau der Befund, der diese Karte ausgelöst hat.
        if messung["kontrast"]["grenze"] != KONTRAST_MIN or messung["treffer"]["grenze"] != TREFFER_MIN:
            raise RuntimeError(
                "Grenzwerte nicht im Browser angekommen: "
                f"kontrast={messung['kontrast']['grenze']!r} treffer={messung['treffer']['grenze']!r}"
            )
        ergebnis.update({
            "titel": messung["titel"],
            "kontrast": messung["kontrast"],
            "treffer": messung["treffer"],
            "primaer": messung["primaer"],
            "primaer_anzahl": len(messung["primaer"]),
            "ueberlauf": messung["ueberlauf"],
        })

        # 44-px-Regel gilt laut Konzept nur bei grobem Zeiger (Mobil).
        if hastouch:
            ergebnis["treffer_regel"] = {
                "kleiner_44": len(messung["treffer"]["zu_klein"]),
                "verletzt": len(messung["treffer"]["zu_klein"]) > 0,
            }
        else:
            ergebnis["treffer_regel"] = {"hinweis": "44 px wird nur mobil geprüft"}

        # (5) Überlauf bei 375 px — eigenes Fenster, gleiche Sitzung/Theme.
        if breite > UEBERLAUF_BREITE:
            page.set_viewport_size({"width": UEBERLAUF_BREITE, "height": hoehe})
            page.wait_for_timeout(400)
            zaehlung = page.evaluate(ZAEHL_SKRIPT, [TREFFER_MIN])
            ergebnis["ueberlauf_375"] = {
                "scrollbreite": zaehlung["scrollbreite"],
                "fenster": zaehlung["fenster"],
                "ueberlauf": zaehlung["scrollbreite"] > zaehlung["fenster"] + 1,
            }
            page.set_viewport_size({"width": breite, "height": hoehe})
            page.wait_for_timeout(250)

        # (4) Graustufen-Screenshot der Ansicht.
        screenshot_graustufen(page, bildpfad)
        ergebnis["bild"] = os.path.basename(bildpfad)

        ergebnis["konsolenfehler"] = sorted(set(konsolen))
        ergebnis["netzwerkfehler"] = sorted(set(netz))
    except Exception as fehler:  # eine gebrochene Seite darf den Lauf nicht kippen
        ergebnis["fehler"].append(f"{type(fehler).__name__}: {fehler}")
    finally:
        ctx.close()
    return ergebnis


def verletzt(e):
    """Verletzt diese Ansicht einen der Prüfpunkte?"""
    if e.get("fehler"):
        return True
    if e.get("kontrast", {}).get("verstoesse"):
        return True
    if e.get("treffer_regel", {}).get("verletzt"):
        return True
    if e.get("primaer_anzahl", 0) != 1:
        return True
    if e.get("ueberlauf", {}).get("ueberlauf"):
        return True
    if e.get("ueberlauf_375", {}).get("ueberlauf"):
        return True
    if e.get("konsolenfehler") or e.get("netzwerkfehler"):
        return True
    return False


def bericht(daten):
    """Kurzer Markdown-Bericht: Zahlen je Prüfpunkt, Verstöße mit Selektor."""
    zeilen = []
    z = zeilen.append
    z(f"# Bildschirmtest — {daten['stand']}")
    z("")
    z(f"Ziel: `{daten['basis']}` — {len(daten['ansichten'])} Ansichten "
      f"({len(daten['seiten'])} Seiten × Desktop/Mobil × hell/dunkel).")
    z("")
    gesamt = daten["zusammenfassung"]
    z("## Gesamt")
    z("")
    z("| Prüfpunkt | Ergebnis |")
    z("|---|---|")
    z(f"| Kontrast >= 4,5:1 | {gesamt['kontrast_ansichten_frei']} von {gesamt['ansichten']} Ansichten ohne Verstoß "
      f"({gesamt['kontrast_verstoesse']} Stellen) |")
    z(f"| Trefferflächen >= 44 px (mobil) | {gesamt['treffer_ansichten_frei']} von {gesamt['mobil_ansichten']} mobilen Ansichten ohne Verstoß "
      f"({gesamt['treffer_klein']} Stellen) |")
    z(f"| Primärknöpfe genau 1 | {gesamt['primaer_ok']} von {gesamt['ansichten']} Ansichten |")
    z(f"| Horizontaler Überlauf 375 px | {gesamt['ueberlauf_ok']} von {gesamt['ansichten']} Ansichten |")
    z(f"| Konsolen-/Netzwerkfehler | {gesamt['fehlerfrei']} von {gesamt['ansichten']} Ansichten |")
    z(f"| **Ansichten gesamt** | **{gesamt['verletzt']} von {gesamt['ansichten']} mit Befund** |")
    z("")

    def tabelle(titel, spalten, zeilen_daten):
        if not zeilen_daten:
            return
        z(f"## {titel}")
        z("")
        z("| " + " | ".join(spalten) + " |")
        z("|" + "---|" * len(spalten))
        for werte in zeilen_daten:
            z("| " + " | ".join(str(w) for w in werte) + " |")
        z("")

    tabelle("Primärknöpfe (Soll: genau 1)",
            ["Seite", "Ansicht", "Theme", "Anzahl", "Knöpfe"],
            [[e["seite"], e["ansicht"], e["theme"], e.get("primaer_anzahl", "—"),
              "; ".join(k["text"] or k["selektor"] for k in e.get("primaer", [])) or "—"]
             for e in daten["ansichten"] if e.get("primaer_anzahl") != 1])

    tabelle("Kontrast-Verstöße",
            ["Seite", "Ansicht", "Theme", "Selektor", "Text", "Ist"],
            [[e["seite"], e["ansicht"], e["theme"], v["selektor"], v["text"], f"{v['kontrast']}:1"]
             for e in daten["ansichten"] for v in e.get("kontrast", {}).get("verstoesse", [])][:80])

    tabelle("Trefferflächen < 44 px (mobil)",
            ["Seite", "Theme", "Selektor", "Text", "B×H"],
            [[e["seite"], e["theme"], v["selektor"], v["text"], f"{v['breite']}×{v['hoehe']}"]
             for e in daten["ansichten"] for v in e.get("treffer", {}).get("zu_klein", [])][:80])

    tabelle("Horizontaler Überlauf",
            ["Seite", "Ansicht", "Theme", "Fenster", "Scrollbreite"],
            [[e["seite"], e["ansicht"], e["theme"], "375" if e.get("ueberlauf_375", {}).get("ueberlauf") else e["ueberlauf"]["fenster"],
              e.get("ueberlauf_375", {}).get("scrollbreite", e["ueberlauf"]["breite"])]
             for e in daten["ansichten"]
             if e.get("ueberlauf", {}).get("ueberlauf") or e.get("ueberlauf_375", {}).get("ueberlauf")])

    tabelle("Konsolen- und Netzwerkfehler",
            ["Seite", "Ansicht", "Theme", "Art", "Meldung"],
            [[e["seite"], e["ansicht"], e["theme"], art, meldung[:120]]
             for e in daten["ansichten"]
             for art, liste in (("Konsole", e.get("konsolenfehler", [])),
                                ("Netz", e.get("netzwerkfehler", [])))
             for meldung in liste][:80])

    tabelle("Seiten ohne Messung",
            ["Seite", "Ansicht", "Theme", "Fehler"],
            [[e["seite"], e["ansicht"], e["theme"], "; ".join(e["fehler"])]
             for e in daten["ansichten"] if e.get("fehler")])

    z("## Ansichten im Einzelnen")
    z("")
    z("| Seite | Ansicht | Theme | Kontrast-Verstöße | < 44 px | Primär | Überlauf | Konsole/Netz |")
    z("|---|---|---|---|---|---|---|---|")
    for e in daten["ansichten"]:
        z(f"| {e['seite']} | {e['ansicht']} | {e['theme']} | "
          f"{len(e.get('kontrast', {}).get('verstoesse', []))} | "
          f"{len(e.get('treffer', {}).get('zu_klein', [])) if e['ansicht'] == 'mobil' else '—'} | "
          f"{e.get('primaer_anzahl', '—')} | "
          f"{'ja' if (e.get('ueberlauf', {}).get('ueberlauf') or e.get('ueberlauf_375', {}).get('ueberlauf')) else 'nein'} | "
          f"{len(e.get('konsolenfehler', [])) + len(e.get('netzwerkfehler', []))} |")
    z("")
    z("Bilder: `bilder/‹seite›-‹ansicht›-‹theme›.png` (Graustufen).")
    return "\n".join(zeilen) + "\n"


def zusammenfassen(ansichten):
    mobil = [a for a in ansichten if a["ansicht"] == "mobil"]
    return {
        "ansichten": len(ansichten),
        "mobil_ansichten": len(mobil),
        "verletzt": sum(1 for a in ansichten if verletzt(a)),
        "kontrast_verstoesse": sum(len(a.get("kontrast", {}).get("verstoesse", [])) for a in ansichten),
        "kontrast_ansichten_frei": sum(1 for a in ansichten if not a.get("kontrast", {}).get("verstoesse")),
        "treffer_klein": sum(len(a.get("treffer", {}).get("zu_klein", [])) for a in mobil),
        "treffer_ansichten_frei": sum(1 for a in mobil if not a.get("treffer", {}).get("zu_klein")),
        "primaer_ok": sum(1 for a in ansichten if a.get("primaer_anzahl") == 1),
        "ueberlauf_ok": sum(1 for a in ansichten
                            if not a.get("ueberlauf", {}).get("ueberlauf")
                            and not a.get("ueberlauf_375", {}).get("ueberlauf")),
        "fehlerfrei": sum(1 for a in ansichten
                          if not a.get("konsolenfehler") and not a.get("netzwerkfehler")),
    }


def main() -> int:
    bilder = os.path.join(ZIEL, "bilder")
    os.makedirs(bilder, exist_ok=True)
    seiten = [s for s in SEITEN if PASSWORT or s[1] is None]
    daten = {
        "stand": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "basis": BASE,
        "spa": SPA,
        "seiten": [s[0] for s in seiten],
        "grenzen": {"kontrast_min": KONTRAST_MIN, "treffer_min_px": TREFFER_MIN,
                    "ueberlauf_breite": UEBERLAUF_BREITE},
        "ansichten": [],
    }
    with sync_playwright() as p:
        # --no-proxy-server: der Start des Browsers darf einen gesetzten
        # HTTP(S)_PROXY der Umgebung nicht erben, sonst geht der Aufruf an
        # 127.0.0.1/localhost durch den Proxy und scheitert (ERR_SOCKET_NOT_CONNECTED).
        browser = p.chromium.launch(args=["--no-sandbox", "--no-proxy-server"])
        for name, route, _extra in seiten:
            for ansicht, breite, hoehe, hastouch in ANSICHTEN:
                for theme in THEMES:
                    bild = os.path.join(bilder, f"{name}-{ansicht}-{theme}.png")
                    e = pruefe_ansicht(browser, name, route, breite, hoehe, hastouch, theme, bild)
                    e["befund"] = verletzt(e)
                    daten["ansichten"].append(e)
                    print(f"{name:28s} {ansicht:8s} {theme:6s} "
                          f"kontrast={len(e.get('kontrast', {}).get('verstoesse', [])):3d} "
                          f"klein={len(e.get('treffer', {}).get('zu_klein', [])):3d} "
                          f"primaer={e.get('primaer_anzahl', '?')} "
                          f"ueberlauf={'ja' if (e.get('ueberlauf', {}).get('ueberlauf') or e.get('ueberlauf_375', {}).get('ueberlauf')) else 'nein'} "
                          f"fehler={len(e.get('konsolenfehler', [])) + len(e.get('netzwerkfehler', [])) + len(e.get('fehler', []))}")
        browser.close()

    daten["zusammenfassung"] = zusammenfassen(daten["ansichten"])
    with open(os.path.join(ZIEL, "ergebnis.json"), "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(ZIEL, "bericht.md"), "w", encoding="utf-8") as fh:
        fh.write(bericht(daten))
    print("\nGesamt:", json.dumps(daten["zusammenfassung"], ensure_ascii=False))
    return 1 if daten["zusammenfassung"]["verletzt"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
