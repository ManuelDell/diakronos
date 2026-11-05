/**
 * UX2a2 — Nachbesserung der Rückgängig-Meldung (Befunde aus dem Review).
 *
 * Was dieser Test festhält, Punkt für Punkt nach der Karte:
 *
 *  F1  Eine gescheiterte Rücknahme wird als Fehlermeldung GEZEIGT
 *      (Fehlerkatalog-Text bzw. Meldung des Servers), nicht verschluckt.
 *  F2  Der Ablauf greift IMMER: `zuruecknehmen(id)` gibt die Uhrzeit mit,
 *      nach einem Tab-Schlaf ist eine zehn Minuten alte Aktion nicht mehr
 *      rückgängig zu machen.
 *  F3  Pause bei Hover/Fokus gilt auch für Rückgängig-Meldungen, und der
 *      Fokus fällt nach dem Schließen auf ein sinnvolles Ziel — nie `<body>`.
 *  F4  Der Esc-Zuhörer eines Meldungsdienstes wird beim Entfernen abgemeldet
 *      (keine Anhäufung); Esc schließt nur die oberste Meldung, nicht bei
 *      offenem Dialog, und nimmt den Eintrag aus dem Stapel.
 *  F5  Die Positionsklasse `--undo` fällt weg, sobald keine Rückgängig-Meldung
 *      mehr offen ist (Fehlermeldungen bleiben an ihrem Ort).
 *  F6  Strg+UMSCHALT+Z ist kein Rückgängig, `repeat` wird ignoriert, und die
 *      Meldungsgrenze verdrängt keine Fehlermeldungen.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`).
 * Der Test liest NUR Dateien unter `frontend/` (Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { test } from 'node:test'

import {
  RueckgaengigStapel,
  ABlaufMS,
  GRENZE,
} from '../src/diakonos/composables/rueckgaengigStapel.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))

/** Datei im Repo ODER im Frontend-Stage des Images finden (Regel 13). */
function lies(relativ) {
  const formen = [relativ, relativ.replace(/^frontend\//, '')]
  const hoch = HIER.split('/')
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of formen) {
      const pfad = join(hoch.join('/'), form)
      if (existsSync(pfad)) return readFileSync(pfad, 'utf8')
    }
    hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${relativ} (gesucht ab ${HIER})`)
}

// ── DOM-Attrappe (wie in ux2a-rueckgaengig.test.mjs) ────────────────────────

class Knoten {
  constructor(tag = 'div') {
    this.tagName = String(tag).toUpperCase()
    this.children = []
    this.parentNode = null
    this.attrs = {}
    this.listeners = {}
    this.style = {}
    this.className = ''
    this.textContent = ''
    this.isConnected = false
    this.focused = false
    this.classList = {
      add: (k) => { this.className = `${this.className} ${k}`.trim() },
      remove: (k) => { this.className = this.className.split(/\s+/).filter(x => x && x !== k).join(' ') },
      contains: (k) => this.className.split(/\s+/).includes(k),
    }
  }
  setAttribute(k, v) { this.attrs[k] = String(v) }
  getAttribute(k) { return this.attrs[k] ?? null }
  appendChild(el) {
    el.parentNode = this
    el.isConnected = true
    this.children.push(el)
    return el
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter(k => k !== this)
      this.parentNode = null
    }
    this.isConnected = false
  }
  contains(el) {
    if (!el) return false
    return this.children.includes(el) || this.children.some(k => k.contains?.(el))
  }
  addEventListener(k, fn) { (this.listeners[k] ||= []).push(fn) }
  removeEventListener(k, fn) {
    this.listeners[k] = (this.listeners[k] || []).filter(f => f !== fn)
  }
  dispatch(k, ereignis = {}) {
    for (const fn of [...(this.listeners[k] || [])]) fn(ereignis)
  }
  focus() {
    this.focused = true
    if (this.ownerDocument) this.ownerDocument.activeElement = this
    // Wie im Browser: das Dokument meldet den Fokuswechsel (Capture-Phase).
    if (this.ownerDocument?.listeners?.focusin) {
      this.ownerDocument.dispatch('focusin', { target: this })
    }
  }
  /* F3: Fokus-Herkunft wie im Browser (`closest`). */
  closest(auswahl) {
    const klassen = auswahl.split(/\s+/).map(s => s.replace(/^\./, ''))
    let knoten = this
    while (knoten) {
      if (klassen.every(k => `${knoten.className}`.split(/\s+/).includes(k))) return knoten
      knoten = knoten.parentNode
    }
    return null
  }
  querySelector(auswahl) {
    // Nur die beiden Formen, die der Quelltext braucht.
    const treffer = (knoten) => {
      if (auswahl.startsWith('[data-meldung="')) {
        const id = auswahl.slice('[data-meldung="'.length, -2)
        if (knoten.getAttribute?.('data-meldung') === id) return knoten
      } else if (auswahl.startsWith('.')) {
        if (`${knoten.className}`.split(/\s+/).includes(auswahl.slice(1))) return knoten
      } else if (auswahl.includes('[role="dialog"]')) {
        // „[role=\"dialog\"][aria-modal=\"true\"]" bzw. „[role=\"dialog\"], [role=\"menu\"] …"
        const rollen = (auswahl.match(/\[role="([a-z]+)"\]/g) || [])
          .map(r => r.slice(7, -2))
        const modal = auswahl.includes('aria-modal')
        if (rollen.includes(knoten.getAttribute?.('role'))
            && (!modal || knoten.getAttribute?.('aria-modal') === 'true')) return knoten
      } else if (auswahl.includes('data-fokus-start')) {
        if (knoten.getAttribute?.('data-fokus-start') !== null
            && knoten.attrs && 'data-fokus-start' in knoten.attrs) return knoten
      } else if (auswahl === 'button') {
        if (`${knoten.tagName}`.toUpperCase() === 'BUTTON') return knoten
      }
      for (const k of knoten.children) {
        const t = treffer(k)
        if (t) return t
      }
      return null
    }
    return treffer(this)
  }
}

class Dokument extends Knoten {
  constructor() {
    super('#document')
    this.body = new Knoten('body')
    this.body.ownerDocument = this
    this.appendChild(this.body)
    this.activeElement = this.body
  }
  createElement(tag) { const k = new Knoten(tag); k.ownerDocument = this; return k }
}

/** Alle Knöpfe einer Meldung (rekursiv). */
function knoepfe(el, gefunden = []) {
  if (el.tagName === 'BUTTON') gefunden.push(el)
  for (const k of el.children) knoepfe(k, gefunden)
  return gefunden
}

function dateiUrl(rel) {
  const formen = [rel, rel.replace(/^frontend\//, '')]
  const hoch = HIER.split('/')
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of formen) {
      const pfad = join(hoch.join('/'), form)
      if (existsSync(pfad)) return pathToFileURL(pfad).href
    }
    hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${rel}`)
}

let ladeZaehler = 0

/**
 * `useRueckgaengig.js` ausführbar laden: `vue` wird durch eine Attrappe
 * ersetzt, die Nachbardateien werden als echte Module importiert. Je Test
 * eine frische Kopie (Modulzustand ist modulweit) — UND je Test eine frische
 * Kopie von `useToast.js`, damit die Zuhörer-Zählung nicht überläuft.
 */
async function ladeRueckgaengig() {
  let quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
  quelle = quelle.replace(
    "import { ref } from 'vue'",
    'const ref = (v) => ({ value: v })',
  )
  // UX2a2c: Der Fehlerkatalog wird in einer data:-URL geladen — ein relativer
  // Pfad loest dort nicht auf (ERR_UNSUPPORTED_RESOLVE_REQUEST). Beide Quellen
  // zeigen deshalb auf die echte Datei (Regel 13: nur unter frontend/).
  quelle = quelle.replace(
    "from '../../shared/fehlertexte.js'",
    `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
  )
  quelle = quelle.replace(
    "from './rueckgaengigStapel.mjs'",
    `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}'`,
  )
  ladeZaehler += 1
  // Frischer Meldungsdienst je Test: eine Kopie mit eigenem Modulzustand
  // (sonst teilte sich der Lauf die Zuhörer-Liste des Dokuments).
  const toastQuelle = lies('frontend/src/diakonos/composables/useToast.js')
    .replace(
      "from '../../shared/fehlertexte.js'",
      `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
    )
    .replace(
      "from './rueckgaengigStapel.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}?t=${ladeZaehler}'`,
    )
  const toastUrl = 'data:text/javascript;base64,'
    + Buffer.from(toastQuelle).toString('base64')
  const toastMod = await import(`${toastUrl}#toast-${ladeZaehler}`)
  quelle = quelle.replace("from './useToast.js'", `from '${toastUrl}#toast-${ladeZaehler}'`)
  const mod = await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#ux2a2-${ladeZaehler}`)
  return { mod, toast: toastMod }
}

function weltVorbereiten() {
  const document = new Dokument()
  const window = new Knoten('window')
  const timer = []
  globalThis.document = document
  globalThis.window = window
  Object.defineProperty(globalThis, 'navigator', {
    value: { platform: 'Linux x86_64', userAgent: 'node' }, configurable: true, writable: true,
  })
  globalThis.requestAnimationFrame = (fn) => { fn(); return 1 }
  const echtesTimeout = globalThis.setTimeout
  // Fristen werden NICHT abgewartet: die Attrappe merkt sich nur, was
  // angemeldet wurde.
  globalThis.setTimeout = (fn, ms) => { timer.push({ fn, ms }); return timer.length }
  return { document, window, timer, echtesTimeout }
}

function weltZurueck(retten) {
  globalThis.setTimeout = retten.echtesTimeout
  delete globalThis.document
  delete globalThis.window
}

const warten = () => new Promise(r => setImmediate(r))

// ── F1 · Fehler werden gemeldet ────────────────────────────────────────────

test('F1 Gescheiterte Rücknahme wird als Fehlermeldung gezeigt (nicht verschluckt)', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Beitrag gelöscht', async () => {
      const fehler = new Error('Der Beitrag ist bereits endgültig gelöscht.')
      fehler.status = 409
      throw fehler
    })
    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]
    // Kein Absturz: der Knopf ruft die asynchrone Rücknahme ohne .catch.
    knoepfe(meldung)[0].dispatch('click', {})
    await warten()
    await warten()

    const fehler = toast.offeneMeldungen.filter(m => m.type === 'error')
    assert.equal(fehler.length, 1, 'genau EINE Fehlermeldung')
    const text = fehler[0].el.children
      .find(k => k.className === 'diakonos-toast-text').textContent
    assert.equal(text, 'Der Beitrag ist bereits endgültig gelöscht.',
      'die Meldung des Servers gewinnt — sie sagt, was jetzt ist')
    assert.equal(fehler[0].el.getAttribute('role'), 'alert', 'Fehler werden vorgelesen')
    // Die Aktion bleibt verbraucht (genau ein Versuch).
    assert.equal(mod.getStapel().laenge, 0)
  } finally {
    weltZurueck(welt)
  }
})

test('F1b Fehler ohne eigene Meldung bekommt den Katalog-Text (nie „undefined“)', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    const faelle = [
      [{ status: 403 }, 'Dafür fehlt dir die Berechtigung.'],
      [{ status: 401 }, 'Die Sitzung ist abgelaufen — bitte neu anmelden.'],
      [{ status: 500 }, 'Das hat nicht geklappt. Bitte versuche es später noch einmal.'],
      [new Error('Fehler'), 'Das hat nicht geklappt. Bitte versuche es später noch einmal.'],
    ]
    for (const [fehler, erwartet] of faelle) {
      mod.rueckgaengigZuruecksetzen()
      mod.registrieren('Etwas entfernt', async () => { throw fehler })
      await mod.zuruecknehmen().catch(() => {})
      const alle = toast.offeneMeldungen.filter(m => m.type === 'error')
      const text = alle.at(-1).el.children
        .find(k => k.className === 'diakonos-toast-text').textContent
      assert.equal(text, erwartet, `Status ${fehler.status ?? '—'}`)
      toast.schliesseAlle()
    }
    // Die Quelle: `zuruecknehmen` lehnt NICHT ab (sonst verlöre ein
    // onClick-Aufruf den Fehler still) — geprüft am Quelltext.
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /catch \(fehler\) \{[\s\S]{0,400}?showToast\(fehlerMeldung\(fehler\), 'error'\)/)
    assert.doesNotMatch(quelle, /\.catch\(e => showToast/, 'kein stilles .catch am Aufrufer')
  } finally {
    weltZurueck(welt)
  }
})

// ── F2 · Der Ablauf greift immer ──────────────────────────────────────────

test('F2 zuruecknehmen(id) gibt die Uhrzeit mit — späte Klicks laufen ab', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Termin gelöscht', async () => { zurueck += 1 })
    const eintrag = mod.getStapel().oberster()

    // Der Nutzer kommt nach dem Tab-Schlaf zurück: zehn Minuten später.
    const echterJetzt = Date.now
    Date.now = () => echterJetzt() + 10 * 60 * 1000
    try {
      const ergebnis = await mod.zuruecknehmen(eintrag.id)
      assert.equal(ergebnis, null, 'die Aktion ist abgelaufen — kein spätes Zurücknehmen')
      assert.equal(zurueck, 0, 'die Gegenrichtung wurde NICHT ausgeführt')
      assert.equal(mod.getStapel().laenge, 0, 'der abgelaufene Eintrag ist weg')
    } finally {
      Date.now = echterJetzt
    }
  } finally {
    weltZurueck(welt)
  }
})

test('F2b Beide Aufrufformen übergeben „jetzt" — geprüft am Stapel selbst', async () => {
  const stapel = new RueckgaengigStapel()
  const folge = []
  const a = stapel.registrieren('A', async () => folge.push('a'), { jetzt: 0 })
  stapel.registrieren('B', async () => folge.push('b'), { jetzt: 0 })
  // Mit Uhrzeit: die Frist ist um, beide sind weg.
  assert.equal(await stapel.zuruecknehmen({ jetzt: ABlaufMS + 1 }), null)
  assert.equal(await stapel.zuruecknehmen(a.id, { jetzt: ABlaufMS + 1 }), null)
  assert.deepEqual(folge, [], 'nach der Frist nimmt niemand mehr zurück')
  assert.equal(stapel.laenge, 0)

  // Die Karte verlangt ausdrücklich BEIDE Formen mit Uhrzeit im Verbundstück.
  const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
  assert.match(quelle, /const jetzt = Number\.isFinite\(vorgaben\.jetzt\) \? vorgaben\.jetzt : Date\.now\(\)/,
    'ohne Angabe gilt die aktuelle Uhrzeit — nie 0 („vor Äonen")')
  assert.match(quelle, /zuruecknehmen\(\{ jetzt: Date\.now\(\), kraft: vorgang \}\)/,
    'auch Strg+Z gibt die Uhrzeit mit')
})

// ── F3 · Pause und Fokus ──────────────────────────────────────────────────

test('F3 Hover und Fokus halten die Meldung — die Frist bleibt stehen', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Aus Gruppe entfernt', async () => {})
    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]

    // Zeiger darüber: Uhr anhalten (die Attrappe merkt sich `pause` daran,
    // dass kein neuer Timer angemeldet wird).
    welt.timer.length = 0
    meldung.dispatch('mouseenter', {})
    meldung.dispatch('mouseleave', {})
    assert.ok(welt.timer.some(t => t.ms <= 8000 && t.ms > 0),
      'nach dem Verlassen läuft die RESTLICHE Frist weiter')

    // Fokus im Knopf: ebenso.
    welt.timer.length = 0
    meldung.dispatch('focusin', {})
    meldung.dispatch('focusout', { relatedTarget: null })
    assert.ok(welt.timer.some(t => t.ms > 0), 'nach dem Fokusverlust läuft die Restfrist weiter')

    // Der Quelltext behandelt Hover/Fokus für ALLE Typen gleich — die
    // Rückgängig-Meldung ist keine Ausnahme. UX2a2b: die Handler heißen
    // `haltenAn`/`haltenAusFuer`; sie halten die Uhr UND (über `onPause`/
    // `onWeiter`) die Frist der Aktion an.
    const quelle = lies('frontend/src/diakonos/composables/useToast.js')
    assert.match(quelle, /el\.addEventListener\('mouseenter', \(\) => haltenAn\('maus'\)\)/)
    assert.match(quelle, /el\.addEventListener\('mouseleave', \(\) => haltenAusFuer\('maus'\)\)/)
    assert.match(quelle, /el\.addEventListener\('focusin', \(\) => haltenAn\('fokus'\)\)/)
    assert.match(quelle, /function haltenAn\(quelle\) \{[\s\S]{0,300}?onPause\)/)
    assert.match(quelle, /function haltenAusFuer\(quelle\) \{[\s\S]{0,400}?onWeiter\)/)
    assert.doesNotMatch(quelle, /type !== 'undo'[^\n]*pause/, 'kein Sonderweg für undo')
  } finally {
    weltZurueck(welt)
  }
})

test('F3c Hover kurz nach dem Aufruf hält die VOLLE Frist (Uhr startet nach dem Anzeigen)', async () => {
  const welt = weltVorbereiten()
  try {
    const { toast } = await ladeRueckgaengig()
    // Im Browser gemessen (Playwright, UX2a2): der Zeiger stand schon über der
    // Stelle, als die Meldung erschien. Vorher lief die Uhr INNERHALB von
    // `showToast` an; `pause()` merkte sich dann fast 0 ms Rest, und die
    // Meldung verschwand nach dem Verlassen der Fläche sofort (Befund).
    const entfernen = toast.showToast('Aktion', 'success', null, { dauer: 4000 })
    const meldung = welt.document.querySelector('.diakonos-toast-container').children.at(-1)
    welt.timer.length = 0

    // Zeiger kommt im selben Zug darüber, wie im Browser: die Uhr wird
    // angehalten, gleich nachdem sie angelaufen ist.
    meldung.dispatch('mouseenter', {})
    assert.deepEqual(welt.timer, [], 'kein Timer, solange der Zeiger steht')
    meldung.dispatch('mouseleave', {})

    assert.equal(welt.timer.length, 1, 'nach dem Verlassen läuft genau eine Frist')
    assert.ok(welt.timer[0].ms > 3000,
      `die volle Restzeit läuft weiter (gefunden: ${welt.timer[0].ms} ms) — nicht 0`)
    entfernen()
  } finally {
    weltZurueck(welt)
  }
})

test('F3b Fokus fällt nach dem Schließen auf ein sinnvolles Ziel, nie auf body', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Aktion eins', async () => {})
    mod.registrieren('Aktion zwei', async () => {})
    const meldungen = welt.document.querySelector('.diakonos-toast-container').children
    const oberste = meldungen[meldungen.length - 1]
    const knopf = knoepfe(oberste)[0]

    // Der Nutzer steht mit der Tastatur auf „Rückgängig" der obersten Meldung
    // (`focus` setzt im Browser auch `document.activeElement`).
    knopf.focus()

    // Esc schließt sie — der Fokus darf nicht auf <body> fallen.
    welt.document.dispatch('keydown', { key: 'Escape' })
    await warten()
    assert.notEqual(welt.document.activeElement, welt.document.body,
      'Fokus NICHT auf body (WCAG 2.2.1)')
    const naechste = knoepfe(meldungen[0])[0]
    assert.equal(welt.document.activeElement, naechste,
      'Fokus steht auf „Rückgängig" der verbleibenden Meldung')

    // Quelle: es gibt ein Ziel und einen Rückfall auf die Hauptfläche.
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /export function fokusZiel\(gehabt\)/)
    assert.match(quelle, /\[data-fokus-start\], \.dk-main, main, \[role="main"\]/)
    assert.doesNotMatch(quelle, /function fokusSichern\(\) \{[\s\S]{0,300}?body\.focus/,
      'body ist kein Fokusziel')
  } finally {
    weltZurueck(welt)
  }
})

// ── F4 · Esc: keine Anhäufung, nur oberste, nicht bei Dialog, Eintrag weg ──

test('F4a Esc-Zuhörer wird beim Entfernen abgemeldet (keine Anhäufung)', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    for (let i = 1; i <= 20; i += 1) {
      mod.registrieren(`Aktion ${i}`, async () => {})
      mod.rueckgaengigZuruecksetzen()
    }
    // Der Stapel ist nach jedem Durchgang leer, alle Meldungen sind weg —
    // also darf kein Zuhörer am Dokument hängen bleiben.
    const haengen = welt.document.listeners.keydown?.length || 0
    assert.ok(haengen <= 1, `höchstens ein Esc-Zuhörer (gefunden: ${haengen})`)

    // Und nach dem letzten Schließen: null.
    const { toast } = await ladeRueckgaengig()
    toast.schliesseAlle()
    assert.equal((welt.document.listeners.keydown || []).length, 0,
      'removeEventListener wird beim Entfernen gerufen')
    // Quelle: EIN Zuhörer für alle Meldungen (UX2a2b E1) — angehängt, solange
    // etwas offen ist, und im Entfernen-Pfad wieder abgemeldet.
    const quelle = lies('frontend/src/diakonos/composables/useToast.js')
    assert.match(quelle, /function escSichern\(\)[\s\S]{0,1200}?removeEventListener\('keydown', beiEscTaste\)/)
    assert.doesNotMatch(quelle, /document\.addEventListener\('keydown', beiTaste\)/,
      'kein Zuhörer je Meldung mehr')
  } finally {
    weltZurueck(welt)
  }
})

test('F4b Esc schließt nur die oberste Meldung — nicht bei offenem Dialog', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Erste Aktion', async () => {})
    mod.registrieren('Zweite Aktion', async () => {})
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const [ersteMel, zweiteMel] = behaelter.children

    // Offener Dialog: Esc gehört dem Dialog, die Meldung bleibt stehen.
    const dialog = welt.document.createElement('div')
    dialog.className = 'dk-modal-overlay'
    dialog.setAttribute('role', 'dialog')
    dialog.setAttribute('aria-modal', 'true')
    welt.document.body.appendChild(dialog)
    welt.document.dispatch('keydown', { key: 'Escape' })
    assert.equal(ersteMel.className.includes('show'), true, 'Meldung 1 bleibt (Dialog hat Vorrang)')
    assert.equal(zweiteMel.className.includes('show'), true, 'Meldung 2 bleibt')
    dialog.remove()

    // Ohne Dialog: genau die OBERSTE (zuletzt angemeldete) geht.
    welt.document.dispatch('keydown', { key: 'Escape' })
    assert.equal(zweiteMel.className.includes('show'), false, 'oberste Meldung geschlossen')
    assert.equal(ersteMel.className.includes('show'), true, 'die darunter bleibt stehen')
    assert.equal(mod.getStapel().laenge, 1, 'nur der Eintrag der obersten ist weg')
  } finally {
    weltZurueck(welt)
  }
})

test('F4c Eine per Esc geschlossene Meldung nimmt ihren Eintrag aus dem Stapel', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    const folge = []
    mod.registrieren('Zeile entfernt', async () => folge.push('zeile'))
    assert.equal(mod.getStapel().laenge, 1)

    welt.document.dispatch('keydown', { key: 'Escape' })
    assert.equal(mod.getStapel().laenge, 0,
      'die weggeschobene Meldung lässt keinen Eintrag zurück (kein spätes Strg+Z)')

    // Ein Strg+Z danach nimmt nichts mehr zurück.
    welt.window.dispatch('keydown', {
      key: 'z', ctrlKey: true, target: new Knoten('body'), preventDefault() {},
    })
    await warten()
    assert.deepEqual(folge, [], 'keine unsichtbare Rücknahme')

    // Gegenprobe: der ABLAUF verwirft nichts — nur Esc tut das.
    mod.registrieren('Zweite Aktion', async () => folge.push('zwei'))
    assert.equal(mod.getStapel().laenge, 1)
  } finally {
    weltZurueck(welt)
  }
})

// ── F5 · Positionsklasse fällt weg ────────────────────────────────────────

test('F5 --undo verschwindet mit der letzten Rückgängig-Meldung, Fehler bleiben oben', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Aktion', async () => {})
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    assert.equal(behaelter.classList.contains('diakonos-toast-container--undo'), true,
      'solange eine Rückgängig-Meldung offen ist: unten links')

    // Frist abgelaufen: der Takt räumt auf — die Klasse muss mitgehen.
    const eintrag = mod.getStapel().oberster()
    mod.getStapel().pruefen(eintrag.ablauf + 1)
    assert.equal(behaelter.classList.contains('diakonos-toast-container--undo'), false,
      'keine Rückgängig-Meldung mehr → zurück an den Ort der Fehlermeldungen')

    // Eine Fehlermeldung allein bringt die Klasse NICHT wieder.
    toast.showToast('Das hat nicht geklappt.', 'error')
    assert.equal(behaelter.classList.contains('diakonos-toast-container--undo'), false,
      'Fehlermeldungen bleiben oben rechts')
    toast.schliesseAlle()
  } finally {
    weltZurueck(welt)
  }
})

// ── F6 · Tastenkombination und Grenze ─────────────────────────────────────

test('F6a Strg+UMSCHALT+Z ist kein Rückgängig, gehaltene Taste zählt nicht', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    const folge = []
    mod.registrieren('Zeile entfernt', async () => folge.push('zeile'))
    mod._tastaturAnmelden()

    // Strg+Umschalt+Z = „Wiederholen" (Windows) — NICHT zurücknehmen.
    for (const ereignis of [
      { key: 'z', ctrlKey: true, shiftKey: true },
      { key: 'Z', metaKey: true, shiftKey: true },
      { key: 'z', ctrlKey: true, altKey: true },
      { key: 'z', ctrlKey: true, repeat: true },
    ]) {
      welt.window.dispatch('keydown', { ...ereignis, target: new Knoten('body'), preventDefault() {} })
      await warten()
    }
    assert.deepEqual(folge, [], 'Umschalt/Alt/gehalten nehmen nichts zurück')

    // Reines Strg+Z wirkt weiterhin.
    welt.window.dispatch('keydown', {
      key: 'z', ctrlKey: true, target: new Knoten('body'), preventDefault() {},
    })
    await warten()
    assert.deepEqual(folge, ['zeile'])

    // Quelle: die Prüfung steht an EINER Stelle und ist benannt.
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /if \(ereignis\.altKey === true \|\| ereignis\.shiftKey === true\) return false/)
    assert.match(quelle, /if \(ereignis\.repeat === true\) return false/)
  } finally {
    weltZurueck(welt)
  }
})

test('F6b Die Meldungsgrenze verdrängt keine Fehlermeldungen', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Aktion eins', async () => {})
    toast.schliesseAlle()
    // Ein Fehler, dann über die Grenze hinaus Erfolge.
    toast.showToast('Das hat nicht geklappt.', 'error')
    for (let i = 1; i <= GRENZE + 2; i += 1) {
      toast.showToast(`Gespeichert ${i}`, 'success')
    }
    const typen = toast.offeneMeldungen.map(m => m.type)
    assert.ok(typen.includes('error'), 'die Fehlermeldung steht noch')
    assert.ok(toast.offeneMeldungen.length <= GRENZE, `Grenze ${GRENZE} eingehalten`)
    // Quelle: Verdrängung überspringt Fehler und bricht ab, wenn nur Fehler offen sind.
    const quelle = lies('frontend/src/diakonos/composables/useToast.js')
    assert.match(quelle, /const index = offeneMeldungen\.findIndex\(m => m\.type !== 'error'\)/)
    assert.match(quelle, /if \(index < 0\) return/)
    toast.schliesseAlle()
  } finally {
    weltZurueck(welt)
  }
})

// ── C · Quellen: eine Frist, eine Grenze, keine Rohfarben ─────────────────

test('C1 Entscheidung der Karte: 8 s Frist und Grenze 5 bleiben', () => {
  const stapel = lies('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')
  assert.match(stapel, /export const ABlaufMS = 8000/)
  assert.match(stapel, /export const GRENZE = 5/)
  const toast = lies('frontend/src/diakonos/composables/useToast.js')
  assert.match(toast, /mitAktion: 8000/, 'dieselbe Dauer im Meldungsdienst')
  assert.match(toast, /export const HOECHSTENS = STAPEL_GRENZE/, 'eine Grenze, importiert')
})
