/**
 * MT-3 — Review-Nacharbeit: Die Rückgängig-Meldung lebt GENAU SO LANGE wie
 * ihre Aktion (Anzeige = Frist = `ANZEIGE_MS`).
 *
 * BEFUND DES OPERATORS (11.11.): Der erste Durchgang hatte zwei Zeiten —
 * Anzeige 10 s, Aktionsfrist 8 s. In `useRueckgaengig.js` rief der 250-ms-Takt
 * `entferneToast()`, sobald der Stapel-Eintrag ablief: die ganze MELDUNG war
 * nach 8 s weg, der 10-s-Timer des Meldungsdienstes hat sie nie erreicht. Der
 * damalige Nachweis (9,2 s) lief also am Stapel vorbei und war falsch.
 *
 * ENTSCHEIDUNG (Operator, nach Manuels Vorgabe „Meldungen nach 10 s
 * ausblenden“ und „mit Handlung ebenfalls 10 s“): Frist = Anzeige = EINE
 * Konstante `ANZEIGE_MS` (10 s). Diese Datei prüft das am VERHALTEN (Fake-Uhr
 * gegen den echten Code), nicht per Quelltext-Regex:
 *
 *  1  Meldung UND Rückgängig-Knopf stehen bei 9,9 s noch, bei 10,1 s sind
 *     beide weg (Grund `frist`), die Aktion ist dann nicht mehr zurückholbar.
 *  2  Hover pausiert beide GEMEINSAM: Frist und Anzeige stehen, nach dem
 *     Verlassen laufen beide mit ihrer Restzeit weiter.
 *  3  EINE Zahl: `ABlaufMS === ANZEIGE_MS`, und die Frist steht nicht als
 *     zweite Zahl in der Quelle.
 *
 * Läuft im Docker-Build (`node --test`, frontend/tests/testliste.txt) und
 * lokal mit `node --test frontend/tests/mt3-*.test.mjs`. Der Test liest NUR
 * Dateien unter `frontend/` (Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { test } from 'node:test'

import { ABlaufMS, RueckgaengigStapel } from '../src/diakonos/composables/rueckgaengigStapel.mjs'
import { ANZEIGE_MS } from '../src/diakonos/composables/useToast.js'

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

// ── DOM-Attrappe (Form wie ux2a-rueckgaengig.test.mjs, mit focus()) ────────

class Knoten {
  constructor(tag = 'div') {
    this.tagName = String(tag).toUpperCase()
    this.children = []
    this.parentNode = null
    this.attrs = {}
    this.listeners = {}
    this.style = {}
    this.id = ''
    this.className = ''
    this.textContent = ''
    this.isConnected = false
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
    if (this.ownerDocument) {
      this.ownerDocument.activeElement = this
      this.ownerDocument.dispatch('focusin', { target: this })
    }
  }
  closest(auswahl) {
    const teile = String(auswahl).split(',').map(s => s.trim()).filter(Boolean)
    const passt = (el, sel) => {
      if (sel.startsWith('.')) return `${el.className}`.split(/\s+/).includes(sel.slice(1))
      if (sel.startsWith('#')) return el.id === sel.slice(1)
      if (sel.startsWith('[')) return Boolean(el.attrs && sel.slice(1, -1).split('=')[0] in el.attrs)
      return false
    }
    let knoten = this
    while (knoten) {
      if (teile.some(sel => passt(knoten, sel))) return knoten
      knoten = knoten.parentNode
    }
    return null
  }
  querySelector(auswahl) {
    const teile = String(auswahl).split(',').map(s => s.trim()).filter(Boolean)
    const pruefe = (knoten, sel) => {
      if (sel.startsWith('[data-meldung="')) {
        return knoten.getAttribute?.('data-meldung') === sel.slice('[data-meldung="'.length, -2)
      }
      if (sel.startsWith('[role="')) {
        const rollen = (sel.match(/\[role="([a-z]+)"\]/g) || []).map(r => r.slice(7, -2))
        const modal = sel.includes('aria-modal')
        return rollen.includes(knoten.getAttribute?.('role'))
          && (!modal || knoten.getAttribute?.('aria-modal') === 'true')
      }
      if (sel.startsWith('.')) return `${knoten.className}`.split(/\s+/).includes(sel.slice(1))
      if (sel.startsWith('#')) return knoten.id === sel.slice(1)
      if (sel.startsWith('[')) {
        const name = sel.slice(1, -1).split('=')[0]
        return Boolean(knoten.attrs && name in knoten.attrs)
      }
      return `${knoten.tagName}`.toLowerCase() === sel.toLowerCase()
    }
    const suchen = (knoten) => {
      if (teile.some(sel => pruefe(knoten, sel))) return knoten
      for (const k of knoten.children) {
        const t = suchen(k)
        if (t) return t
      }
      return null
    }
    return suchen(this)
  }
}

class Dokument extends Knoten {
  constructor() {
    super('#document')
    this.body = new Knoten('body')
    this.body.ownerDocument = this
    this.appendChild(this.body)
    this.activeElement = this.body
    // F3-Ziel der App (App.vue) — damit der Fokus-Rückfall nicht beißt.
    this.inhalt = new Knoten('main')
    this.inhalt.id = 'dk-inhalt'
    this.inhalt.ownerDocument = this
    this.body.appendChild(this.inhalt)
  }
  createElement(tag) { const k = new Knoten(tag); k.ownerDocument = this; return k }
}

function knoepfe(el, gefunden = []) {
  if (el.tagName === 'BUTTON') gefunden.push(el)
  for (const k of el.children) knoepfe(k, gefunden)
  return gefunden
}

/**
 * Fake-Uhr: Zeit läuft nur, wenn der Test schiebt. `setInterval` ist ein
 * echter Attrappen-Takt, den `schieben` mitzieht — sonst sähe der Test den
 * 250-ms-Takt nicht, der (laut Befund) die Meldung vorzeitig abräumte.
 */
function uhrVorbereiten() {
  const document = new Dokument()
  const timer = []
  let jetzt = 1_000_000
  globalThis.document = document
  globalThis.window = new Knoten('window')
  Object.defineProperty(globalThis, 'navigator', {
    value: { platform: 'Linux x86_64', userAgent: 'node' }, configurable: true, writable: true,
  })
  globalThis.Date.now = () => jetzt
  globalThis.requestAnimationFrame = (fn) => { fn(); return 1 }
  const echte = { timeout: globalThis.setTimeout, interval: globalThis.setInterval }
  let laufend = 0
  globalThis.setTimeout = (fn, ms) => {
    laufend += 1
    timer.push({ id: laufend, fn, ms: Number(ms) || 0, alle: false, um: jetzt + (Number(ms) || 0), weg: false })
    return laufend
  }
  globalThis.setInterval = (fn, ms) => {
    laufend += 1
    timer.push({ id: laufend, fn, ms: Number(ms) || 1, alle: true, um: jetzt + (Number(ms) || 1), weg: false })
    return laufend
  }
  globalThis.clearTimeout = (id) => { const t = timer.find(t => t.id === id); if (t) t.weg = true }
  globalThis.clearInterval = (id) => { const t = timer.find(t => t.id === id); if (t) t.weg = true }
  /** Zeit vorschieben: alle fälligen Timer (auch Takt-Timer) laufen lassen. */
  const schieben = (ms) => {
    const ziel = jetzt + ms
    for (let runde = 0; runde < 5000; runde += 1) {
      const faellig = timer
        .filter(t => !t.weg && t.um <= ziel)
        .sort((a, b) => a.um - b.um)[0]
      if (!faellig) break
      jetzt = faellig.um
      if (faellig.alle) faellig.um = jetzt + faellig.ms
      else faellig.weg = true
      faellig.fn()
    }
    jetzt = ziel
  }
  return {
    document,
    timer,
    schieben,
    zurueck() {
      globalThis.setTimeout = echte.timeout
      globalThis.setInterval = echte.interval
      delete globalThis.document
      delete globalThis.window
      delete globalThis.requestAnimationFrame
    },
  }
}

let ladeZaehler = 0

/**
 * `useRueckgaengig.js` ausführbar laden: `vue` → Attrappe, Nachbardateien als
 * echte Module. `useToast.js` wird EINMAL geladen und mitgegeben — der Test
 * braucht seinen Zustand (offene Meldungen), um „die Meldung ist weg" zu
 * sehen, und die Verbindung braucht dieselbe Instanz.
 */
async function ladeRueckgaengig() {
  ladeZaehler += 1
  const stempel = `?mt3k=${ladeZaehler}`
  const toastQuelle = lies('frontend/src/diakonos/composables/useToast.js')
    .replace(
      "from '../../shared/fehlertexte.js'",
      `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
    )
    .replace(
      "from './meldungszeit.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/meldungszeit.mjs')}${stempel}'`,
    )
    .replace(
      "from './rueckgaengigStapel.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}${stempel}'`,
    )
  const toastUrl = 'data:text/javascript;base64,' + Buffer.from(toastQuelle).toString('base64')
  const toast = await import(`${toastUrl}#toast-${ladeZaehler}`)

  let quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    .replace("import { ref } from 'vue'", 'const ref = (v) => ({ value: v })')
    .replace(
      "from '../../shared/fehlertexte.js'",
      `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
    )
    .replace(
      "from './rueckgaengigStapel.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}${stempel}'`,
    )
    .replace("from './useToast.js'", `from '${toastUrl}#toast-${ladeZaehler}'`)
  const mod = await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#mt3kopplung-${ladeZaehler}`)
  return { mod, toast }
}

const meldungIn = (document) => document.querySelector('.diakonos-toast-container')?.children[0]

// ── 1 · Meldung und Aktion enden GEMEINSAM nach 10 s ──────────────────────

test('1a Meldung + Rückgängig: bei 9,9 s beides da, bei 10,1 s beides weg', async () => {
  const welt = uhrVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Aus Gruppe entfernt', async () => { zurueck += 1 })

    const meldung = meldungIn(welt.document)
    assert.ok(meldung, 'die Meldung steht')
    assert.deepEqual(knoepfe(meldung).map(k => k.textContent), ['Rückgängig'],
      'genau ein Knopf: Rückgängig')
    assert.equal(mod.getStapel().laenge, 1, 'die Aktion ist angemeldet')
    // Der Eintrag im Stapel lebt 10 s (nicht 8): EINE Zahl für beides.
    assert.equal(mod.getStapel().alle()[0].ablauf, 1_000_000 + ANZEIGE_MS,
      'Frist der Aktion = Anzeigedauer')

    welt.schieben(ANZEIGE_MS - 100)
    assert.equal(toast.offeneMeldungen.length, 1, `bei ${ANZEIGE_MS - 100} ms steht die Meldung`)
    assert.equal(mod.getStapel().laenge, 1, 'und die Aktion ist noch zurückholbar')
    assert.ok(meldungIn(welt.document), 'der Knoten hängt noch im Behälter')

    welt.schieben(200)
    assert.equal(toast.offeneMeldungen.length, 0, 'bei 10,1 s ist die Meldung weg')
    assert.equal(mod.getStapel().laenge, 0, 'und die Aktion abgelaufen')
    // Der Knopf ist mit der Meldung weg — die Aktion lässt sich nicht mehr
    // zurücknehmen (kein „Rückgängig“ ohne Meldung).
    const nachher = await mod.zuruecknehmen({ jetzt: 1_000_000 + ANZEIGE_MS + 200 })
    assert.equal(nachher, null, 'nichts mehr zurückzunehmen')
    assert.equal(zurueck, 0, 'die Gegenrichtung wurde nicht ausgeführt')
  } finally {
    welt.zurueck()
  }
})

test('1b Ohne Hover ist die Aktion vorher NICHT weg (kein 8-s-Abbau mehr)', async () => {
  const welt = uhrVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Beitrag gelöscht', async () => { zurueck += 1 })
    // Der alte Befund: bei 8 s räumte der Takt die Meldung ab.
    welt.schieben(8_500)
    assert.equal(toast.offeneMeldungen.length, 1,
      'bei 8,5 s steht die Meldung noch (der Befund ist behoben)')
    assert.equal(mod.getStapel().laenge, 1, 'und die Aktion ist noch zurückholbar')

    const knopf = knoepfe(meldungIn(welt.document))[0]
    knopf.dispatch('click', {})
    await new Promise(r => setImmediate(r))
    assert.equal(zurueck, 1, 'der Klick nach 8,5 s nimmt wirklich zurück')
  } finally {
    welt.zurueck()
  }
})

// ── 2 · Hover pausiert beide GEMEINSAM ────────────────────────────────────

test('2a Hover hält Frist UND Anzeige an — beide laufen danach weiter', async () => {
  const welt = uhrVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Termin entfernt', async () => { zurueck += 1 })
    const meldung = meldungIn(welt.document)

    welt.schieben(4_000)                    // 4 s gelaufen, 6 s Rest
    meldung.dispatch('mouseenter', {})
    assert.equal(mod.getStapel().alle()[0].haelt, true, 'die Frist der Aktion steht')

    welt.schieben(15_000)                   // Zeiger liegt 15 s (unter dem Deckel)
    assert.equal(toast.offeneMeldungen.length, 1, 'die Meldung bleibt')
    assert.equal(mod.getStapel().laenge, 1, 'die Aktion bleibt zurückholbar')

    meldung.dispatch('mouseleave', {})
    assert.equal(mod.getStapel().alle()[0]?.haelt, false, 'die Frist läuft wieder')

    // Restzeit 6 s: kurz davor steht beides, kurz danach ist beides weg.
    welt.schieben(5_800)
    assert.equal(toast.offeneMeldungen.length, 1, 'nach 5,8 s Restzeit steht die Meldung noch')
    assert.equal(mod.getStapel().laenge, 1, 'und die Aktion ist noch da')
    welt.schieben(400)
    assert.equal(toast.offeneMeldungen.length, 0,
      'nach der Restzeit sind Meldung UND Aktion gemeinsam weg')
    assert.equal(mod.getStapel().laenge, 0)
    assert.equal(zurueck, 0)
  } finally {
    welt.zurueck()
  }
})

test('2b Fokus hält ebenso beide — nach dem Verlassen wieder gemeinsam ab', async () => {
  const welt = uhrVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Lied entfernt', async () => {})
    const meldung = meldungIn(welt.document)
    meldung.dispatch('focusin', {})
    welt.schieben(30_000)
    assert.equal(toast.offeneMeldungen.length, 1, 'Fokus: die Meldung bleibt')
    assert.equal(mod.getStapel().laenge, 1, 'Fokus: die Aktion bleibt')
    meldung.dispatch('focusout', { relatedTarget: null })
    welt.schieben(ANZEIGE_MS + 200)
    assert.equal(toast.offeneMeldungen.length, 0)
    assert.equal(mod.getStapel().laenge, 0)
  } finally {
    welt.zurueck()
  }
})

// ── 3 · Eine Zahl für Frist und Anzeige ───────────────────────────────────

test('3a ABlaufMS IST ANZEIGE_MS (eine Zahl, abgeleitet)', () => {
  assert.equal(ANZEIGE_MS, 10_000, 'die eine Zeit: 10 s')
  assert.equal(ABlaufMS, ANZEIGE_MS, 'Frist der Aktion = Anzeigedauer')
})

test('3b Die Frist steht nicht als zweite Zahl im Quelltext', () => {
  const stapel = lies('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')
  assert.match(stapel, /export const ABlaufMS = ANZEIGE_MS/,
    'die Frist leitet sich ab, statt als 8000 danebenzustehen')
  assert.doesNotMatch(stapel, /\b8000\b/, 'die alte 8-s-Zahl steht nirgends mehr')
  const zeit = lies('frontend/src/diakonos/composables/meldungszeit.mjs')
  assert.match(zeit, /export const ANZEIGE_MS = 10_?000/, 'die eine Zahl hat EINE Quelle')
  // Der Stapel holt sie von dort (nicht aus useToast — das wäre ein Zyklus,
  // der beim Laden `Cannot access … before initialization` wirft).
  assert.match(stapel, /from '\.\/meldungszeit\.mjs'/)
  assert.doesNotMatch(stapel, /from '\.\/useToast\.js'/,
    'kein Import-Zyklus Stapel ↔ Meldungsdienst')
})

test('3c Der Stapel rechnet mit der übergebenen Frist (Vorgabe = ABlaufMS)', async () => {
  const stapel = new RueckgaengigStapel()
  const eintrag = stapel.registrieren('Aktion', async () => {}, { jetzt: 500 })
  assert.equal(eintrag.ablauf, 500 + ABlaufMS)
  assert.deepEqual(stapel.pruefen(500 + ABlaufMS - 1), [], 'kurz davor noch gültig')
  assert.equal(stapel.pruefen(500 + ABlaufMS).length, 1, 'genau bei der Anzeigedauer abgelaufen')
})
