/**
 * UX2a — Rückgängig-Meldung + Strg+Z.
 *
 * Was dieser Test festhält (Karte UX2a):
 *
 *  A  Der Stapel (`rueckgaengigStapel.mjs`, reine Logik):
 *     Reihenfolge (zuletzt zuerst), Grenze, Ablauf, Rücknahme genau einmal,
 *     Fehler werden weitergereicht, ungültige Einträge abgewiesen.
 *
 *  B  Das Verbundstück (`useRueckgaengig.js` + `useToast.js`) mit einer
 *     kleinen DOM-Attrappe:
 *     „Rückgängig“ steht als EIN Knopf in der Meldung, Frist = Anzeige
 *     (10 s, `ANZEIGE_MS`),
 *     aria-live/role, Esc schließt, Tastatur (Strg+Z / Cmd+Z) nimmt zurück —
 *     aber NICHT in Eingabefeldern, und nur solange etwas offen ist.
 *
 *  C  Statische Prüfungen an den Quellen: die Meldung bekommt ihr Aussehen
 *     aus tokens.css (keine Rohfarben, Streifen links statt Volltonfläche),
 *     der Fristwert steht an EINER Stelle, und die Tastatur ist angekündigt.
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
// MT-3: die zentrale ANZEIGEdauer (10 s) — sie ist ZUGLEICH die Aktionsfrist.
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

// ── A · Der reine Stapel ────────────────────────────────────────────────────

test('A1 Stapel nimmt zuletzt angemeldete Aktion zuerst zurück (LIFO)', async () => {
  const folge = []
  const stapel = new RueckgaengigStapel()
  stapel.registrieren('Beitrag gelöscht', async () => folge.push('beitrag'))
  stapel.registrieren('Aus Gruppe entfernt', async () => folge.push('gruppe'))

  const eins = await stapel.zuruecknehmen({ jetzt: 0 })
  const zwei = await stapel.zuruecknehmen({ jetzt: 0 })
  const drei = await stapel.zuruecknehmen({ jetzt: 0 })

  assert.equal(eins.beschreibung, 'Aus Gruppe entfernt')
  assert.equal(zwei.beschreibung, 'Beitrag gelöscht')
  assert.equal(drei, null, 'leerer Stapel gibt null zurück, nicht undefined')
  assert.deepEqual(folge, ['gruppe', 'beitrag'])
})

test('A2 Stapel merkt sich höchstens GRENZE Einträge — ältere fallen heraus', () => {
  const stapel = new RueckgaengigStapel()
  for (let i = 1; i <= GRENZE + 2; i += 1) {
    stapel.registrieren(`Aktion ${i}`, async () => {})
  }
  assert.equal(stapel.laenge, GRENZE)
  assert.equal(stapel.oberster().beschreibung, `Aktion ${GRENZE + 2}`)
  assert.equal(
    stapel.alle()[0].beschreibung,
    `Aktion 3`,
    'die zwei ältesten sind nicht mehr zurückholbar',
  )
})

test('A3 Frist: ABlaufMS nach Anmeldung, danach abgelaufen und weg', async () => {
  const stapel = new RueckgaengigStapel()
  let zurueck = 0
  const eintrag = stapel.registrieren('Termin gelöscht', async () => { zurueck += 1 }, { jetzt: 1_000 })

  assert.equal(eintrag.ablauf, 1_000 + ABlaufMS)
  assert.equal(stapel.pruefen(1_000 + ABlaufMS - 1).length, 0, 'kurz davor noch gültig')
  assert.equal(stapel.laenge, 1)

  const abgelaufen = stapel.pruefen(1_000 + ABlaufMS)
  assert.equal(abgelaufen.length, 1)
  assert.equal(stapel.laenge, 0)
  assert.equal(await stapel.zuruecknehmen({ jetzt: 1_000 + ABlaufMS }), null)
  assert.equal(zurueck, 0, 'eine abgelaufene Aktion wird NICHT ausgeführt')
})

test('A4 Rücknahme läuft genau einmal — auch bei gleichzeitigem Klick und Tastatur', async () => {
  const stapel = new RueckgaengigStapel()
  let zurueck = 0
  const eintrag = stapel.registrieren('Buchung storniert', async () => {
    zurueck += 1
    await new Promise(r => setTimeout(r, 5))
  }, { jetzt: 0 })

  // Klick auf die Meldung und Strg+Z treffen praktisch gleichzeitig ein.
  const [perMeldung, perTaste] = await Promise.all([
    stapel.zuruecknehmen(eintrag.id, { jetzt: 0 }),
    stapel.zuruecknehmen({ jetzt: 0 }),
  ])
  assert.equal(zurueck, 1, 'die Gegenbuchung darf nicht doppelt laufen')
  assert.ok((perMeldung === null) !== (perTaste === null), 'genau einer der beiden Wege greift')
})

test('A5 Fehler der Rücknahme werden weitergereicht, die Aktion bleibt verbraucht', async () => {
  const stapel = new RueckgaengigStapel()
  stapel.registrieren('Beitrag gelöscht', async () => { throw new Error('Server weg') }, { jetzt: 0 })

  await assert.rejects(() => stapel.zuruecknehmen({ jetzt: 0 }), /Server weg/)
  assert.equal(stapel.laenge, 0, 'kein Endlos-Wiederholen derselben Gegenbuchung')
})

test('A6 Ungültige Anmeldungen werden abgewiesen (keine wirkungslose Meldung)', () => {
  const stapel = new RueckgaengigStapel()
  assert.throws(() => stapel.registrieren('   ', async () => {}), /Beschreibung fehlt/)
  assert.throws(() => stapel.registrieren('Beitrag gelöscht', null), /keine Funktion/)
  assert.equal(stapel.laenge, 0)
})

// ── B · Verbundstück mit DOM-Attrappe ───────────────────────────────────────

/**
 * Minimale DOM-Attrappe: nur was `useToast.js` und `useRueckgaengig.js`
 * anfassen (createElement, appendChild, Klasse, Attribute, Ereignisse,
 * querySelector, body). Kein jsdom, keine Abhängigkeit.
 */
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
    for (const fn of this.listeners[k] || []) fn(ereignis)
    return this
  }
}

class Dokument extends Knoten {
  constructor() {
    super('#document')
    this.body = new Knoten('body')
    this.appendChild(this.body)
  }
  querySelector(auswahl) {
    const finden = (knoten) => {
      if (`${knoten.className}`.split(/\s+/).includes(auswahl.replace(/^\./, ''))) return knoten
      for (const k of knoten.children) {
        const t = finden(k)
        if (t) return t
      }
      return null
    }
    return finden(this.body)
  }
  createElement(tag) { return new Knoten(tag) }
}

/** Alle Knöpfe einer Meldung (rekursiv). */
function knoepfe(el, gefunden = []) {
  if (el.tagName === 'BUTTON') gefunden.push(el)
  for (const k of el.children) knoepfe(k, gefunden)
  return gefunden
}

/**
 * Lädt `useRueckgaengig.js` ausführbar: `vue` wird durch kleine Attrappen
 * ersetzt (ref), die echten Nachbardateien werden per file:-URL importiert.
 * Der Modulzustand ist modulweit — deshalb je Test eine frische Kopie über
 * einen Zähler an der data:-URL.
 */
let ladeZaehler = 0
const geladeneModule = []

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

async function ladeRueckgaengig() {
  let quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
  quelle = quelle.replace(
    "import { ref } from 'vue'",
    'const ref = (v) => ({ value: v })',
  )
  quelle = quelle.replace(
    "from './rueckgaengigStapel.mjs'",
    `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}'`,
  )
  // UX2a2c: Der Fehlerkatalog wird in einer data:-URL geladen — ein relativer
  // Pfad loest dort nicht auf (ERR_UNSUPPORTED_RESOLVE_REQUEST). Der
  // Meldungsdienst kommt aus der echten Datei, `fehlertexte.js` ebenfalls.
  quelle = quelle.replace(
    "from '../../shared/fehlertexte.js'",
    `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
  )
  quelle = quelle.replace(
    "from './useToast.js'",
    `from '${dateiUrl('frontend/src/diakonos/composables/useToast.js')}'`,
  )
  ladeZaehler += 1
  const mod = await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#ux2a-${ladeZaehler}`)
  geladeneModule.push(mod)
  return mod
}

/** Frische Browser-Attrappe; liefert das Beschreibungsobjekt für Prüfungen. */
function weltVorbereiten() {
  const document = new Dokument()
  const window = new Knoten('window')
  const timer = []
  globalThis.document = document
  globalThis.window = window
  // `navigator` ist in neueren Node-Fassungen nur lesbar — über
  // defineProperty setzen (die Attrappe braucht `platform`/`userAgent`).
  Object.defineProperty(globalThis, 'navigator', {
    value: { platform: 'Linux x86_64', userAgent: 'node' },
    configurable: true, writable: true,
  })
  globalThis.requestAnimationFrame = fn => { fn(); return 1 }
  // Fristen werden NICHT abgewartet: die Attrappe merkt sich nur, was
  // angemeldet wurde, damit der Test die Dauer prüfen kann.
  const echtesTimeout = globalThis.setTimeout
  globalThis.setTimeout = (fn, ms) => { timer.push({ fn, ms }); return timer.length }
  return { document, window, timer, echtesTimeout }
}

function weltZurueck(retten) {
  globalThis.setTimeout = retten.echtesTimeout
  delete globalThis.document
  delete globalThis.window
}

test('B1 Meldung: „Rückgängig“ als EIN Knopf, Frist = Anzeige (10 s), aus EINER Quelle', async () => {
  const welt = weltVorbereiten()
  try {
    const mod = await ladeRueckgaengig()
    mod.registrieren('Aus Gruppe entfernt', async () => {})

    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    assert.ok(behaelter, 'Meldungsbehälter angelegt')
    const meldung = behaelter.children[0]
    assert.match(meldung.className, /diakonos-toast--undo/, 'Rückgängig hat ein eigenes Aussehen')

    const knopfText = knoepfe(meldung).map(k => k.textContent)
    assert.deepEqual(knopfText, ['Rückgängig'], 'genau ein Knopf — kein zusätzliches ✕ daneben')

    const aktion = knoepfe(meldung)[0]
    assert.equal(aktion.getAttribute('aria-label'), 'Rückgängig: Aus Gruppe entfernt (Strg+Z)')
    assert.ok(
      meldung.children.some(k => k.className === 'diakonos-toast-text'
        && k.textContent === 'Aus Gruppe entfernt'),
      'der Text steht als Textknoten (nie als HTML)',
    )
    assert.equal(meldung.getAttribute('role'), 'status')
    assert.equal(meldung.getAttribute('aria-live'), 'polite')
    assert.equal(meldung.getAttribute('aria-atomic'), 'true')

    // MT-3 Review-Nacharbeit: Die Meldung steht die zentrale Anzeigedauer
    // (10 s) — und die Frist der Aktion ist DIESELBE Zeit (`ABlaufMS` leitet
    // sich daraus ab). Vorher stand hier „das Rückgängig-Fenster bleibt 8 s“;
    // das war die Trennung, die den Befund erzeugte (Aktion lief mitten in der
    // sichtbaren Meldung ab).
    assert.ok(
      welt.timer.some(t => t.ms === ANZEIGE_MS),
      `${ANZEIGE_MS} ms Anzeige angemeldet (MT-3); gefunden: `
      + welt.timer.map(t => t.ms).join(', '),
    )
    assert.equal(ABlaufMS, ANZEIGE_MS, 'Frist der Aktion = Anzeigedauer (10 s)')
  } finally {
    weltZurueck(welt)
  }
})

test('B2 Klick auf „Rückgängig“ führt die Gegenrichtung aus und räumt die Meldung weg', async () => {
  const welt = weltVorbereiten()
  try {
    const mod = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Beitrag gelöscht', async () => { zurueck += 1 })
    assert.equal(mod.rueckgaengigAnzahl.value, 1)

    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]
    knoepfe(meldung)[0].dispatch('click', {})
    // Der Klick ruft die asynchrone Rücknahme an — einen Mikrotask warten.
    await new Promise(r => setImmediate(r))

    assert.equal(zurueck, 1)
    assert.equal(mod.rueckgaengigAnzahl.value, 0, 'kein zweiter Rückgängig-Knopf bleibt stehen')
    assert.equal(mod.getStapel().oberster(), null)
  } finally {
    weltZurueck(welt)
  }
})

test('B3 Strg+Z nimmt zurück — außerhalb von Eingabefeldern, nur wenn etwas offen ist', async () => {
  const welt = weltVorbereiten()
  try {
    const mod = await ladeRueckgaengig()
    const folge = []
    mod.registrieren('Zeile entfernt', async () => folge.push('zeile'))
    // Der Zuhörer hängt am Fenster, sobald eine Aktion offen ist.
    assert.equal(welt.window.listeners.keydown?.length, 1, 'Tastatur angemeldet')

    // Ein anderes Zeichen tut nichts.
    welt.window.dispatch('keydown', { key: 'y', ctrlKey: true, target: new Knoten('body') })
    await new Promise(r => setImmediate(r))
    assert.deepEqual(folge, [])

    // In einem Eingabefeld gilt Strg+Z dem TEXT, nicht der App.
    const feld = new Knoten('input')
    let abgebrochenImFeld = false
    welt.window.dispatch('keydown', {
      key: 'z', ctrlKey: true, target: feld, preventDefault() { abgebrochenImFeld = true },
    })
    await new Promise(r => setImmediate(r))
    assert.deepEqual(folge, [], 'im Feld darf die App nichts zurücknehmen')
    assert.equal(abgebrochenImFeld, false, 'und der Browser-Textrücknahme nicht in die Quere kommen')

    // contenteditable ebenso.
    const bereich = new Knoten('div')
    bereich.setAttribute('contenteditable', 'true')
    welt.window.dispatch('keydown', { key: 'z', ctrlKey: true, target: bereich })
    await new Promise(r => setImmediate(r))
    assert.deepEqual(folge, [])

    // Auf der Seite: Strg+Z nimmt zurück und schluckt das Ereignis.
    let abgebrochen = false
    welt.window.dispatch('keydown', {
      key: 'z', ctrlKey: true, target: new Knoten('body'), preventDefault() { abgebrochen = true },
    })
    await new Promise(r => setImmediate(r))
    assert.deepEqual(folge, ['zeile'])
    assert.equal(abgebrochen, true, 'die Standard-Rücknahme des Browsers wird ersetzt')
    assert.equal(mod.rueckgaengigAnzahl.value, 0)

    // Danach ist der Zuhörer wieder abgemeldet — nichts hält die Seite.
    assert.equal(welt.window.listeners.keydown?.length, 0, 'Zuhörer abgemeldet, wenn nichts offen ist')
  } finally {
    weltZurueck(welt)
  }
})

test('B4 Jede zurückholbare Aktion hat eine sichtbare Meldung (EINE Grenze)', async () => {
  const welt = weltVorbereiten()
  try {
    const mod = await ladeRueckgaengig()
    const toast = lies('frontend/src/diakonos/composables/useToast.js')
    // Die Meldungsgrenze kommt aus dem Stapel — keine zweite, kleinere Zahl.
    assert.match(toast, /import \{ GRENZE as STAPEL_GRENZE \} from '\.\/rueckgaengigStapel\.mjs'/)
    assert.match(toast, /export const HOECHSTENS = STAPEL_GRENZE/)
    assert.doesNotMatch(toast, /HOECHSTENS = \d/, 'keine abgeschriebene Zahl')

    // Über die Grenze hinaus: gleich viele Meldungen wie Stapel-Einträge.
    for (let i = 1; i <= GRENZE + 2; i += 1) {
      mod.registrieren(`Aktion ${i}`, async () => {})
    }
    // Die offene Liste des Meldungsdienstes (die Attrappe entfernt Knoten erst
    // nach dem Ausblenden — der Bestand ist die belastbare Quelle).
    const { offeneMeldungen } = await import(
      dateiUrl('frontend/src/diakonos/composables/useToast.js'))
    const kasten = welt.document.querySelector('.diakonos-toast-container')
    assert.equal(offeneMeldungen.length, GRENZE, 'Meldungen und Stapel halten gleich viele Aktionen')
    assert.equal(mod.getStapel().laenge, GRENZE)
    // Die offenen Meldungen nennen genau die noch offenen Aktionen — in
    // derselben Reihenfolge (älteste zuerst).
    const texte = offeneMeldungen.map(m => m.el.children
      .find(c => c.className === 'diakonos-toast-text').textContent)
    assert.deepEqual(texte, mod.getStapel().alle().map(e => e.beschreibung))
    assert.equal(kasten.classList.contains('diakonos-toast-container--undo'), true)
  } finally {
    weltZurueck(welt)
  }
})

test('B5 Cmd+Z (Mac) wirkt genauso, und Esc schließt die Meldung', async () => {
  const welt = weltVorbereiten()
  try {
    const mod = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Termin gelöscht', async () => { zurueck += 1 })

    // Esc schließt die Meldung; seit UX2a2 (F4) nimmt sie dabei ihren Eintrag
    // aus dem Stapel — ein späteres Strg+Z darf nichts Unsichtbares treffen.
    // Geprüft in tests/ux2a2-meldung.test.mjs (F4b/F4c); hier nur: Esc führt
    // KEINE Rücknahme aus.
    welt.document.dispatch('keydown', { key: 'Escape' })
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    assert.equal(
      behaelter.children[0].className.includes('show'), false,
      'Meldung wird ausgeblendet',
    )
    assert.equal(zurueck, 0, 'Esc nimmt nichts zurück (keine Gegenbuchung)')

    // Cmd+Z (macOS) nimmt zurück.
    Object.defineProperty(globalThis, 'navigator', {
      value: { platform: 'MacIntel', userAgent: 'Mac' }, configurable: true, writable: true,
    })
    mod.registrieren('Termin gelöscht', async () => { zurueck += 1 })
    welt.window.dispatch('keydown', {
      key: 'Z', metaKey: true, target: new Knoten('body'), preventDefault() {},
    })
    await new Promise(r => setImmediate(r))
    assert.equal(zurueck, 1, 'Cmd+Shift+… bzw. Cmd+Z wirkt auf dem Mac')
  } finally {
    weltZurueck(welt)
  }
})

// ── C · Quellen: Aussehen aus tokens.css, eine Frist, angekündigte Tastatur ──

test('C1 Aussehen: Meldung dunkel mit Gold-Aktion, keine Rohfarben (tokens.css)', () => {
  const css = lies('frontend/src/diakonos/index.css')
  const start = css.indexOf('Meldungen (früher: Toast)')
  const block = css.slice(start, css.indexOf('Widget Grid & Cards', start))
  assert.ok(block.length > 500, 'Meldungsblock gefunden')

  // Entwurf B1: dunkle Fläche, helle Schrift, Gold für die Aktion.
  assert.match(block, /\.diakonos-toast\s*\{[\s\S]*?background:\s*var\(--side-bg\)/)
  assert.match(block, /\.diakonos-toast\s*\{[\s\S]*?color:\s*var\(--side-text\)/)
  assert.match(block, /\.diakonos-toast-aktion\s*\{[\s\S]*?color:\s*var\(--accent\)/)
  // Gold ist Status/Marke — die Rückgängig-Meldung trägt es an der Kante,
  // nicht als Volltonfläche (Prinzip Ä4 „Farbe nie alleiniger Träger“).
  assert.match(block, /\.diakonos-toast--undo\s*\{[^}]*var\(--accent\)/)

  // Keine festen Farbwerte im Block (ON-0b: der Bestand darf nur schrumpfen).
  // `.match` mit `g` gibt bei keinem Treffer `null` zurück — hier immer eine Liste.
  const rohfarben = block
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .match(/#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g) || []
  assert.deepEqual(rohfarben, [], 'Meldungs-Aussehen ausschließlich aus tokens.css')

  // Trefferflächen: am Desktop 40 px (--control-h-lg aus tokens.css), nicht
  // als nackte Zahl in der Komponente; am Handy 44 px im EINEN Grob-Zeiger-Block.
  const aktionRegel = block.slice(
    block.indexOf('.diakonos-toast-aktion'),
    block.indexOf('}', block.indexOf('.diakonos-toast-aktion')),
  )
  assert.match(aktionRegel, /min-height:\s*var\(--control-h-lg\)/)
  const token = lies('frontend/src/diakonos/tokens.css')
  assert.match(token, /--control-h-lg:\s*40px/, 'Konzept-Vorgabe 40 px als Token')
  assert.doesNotMatch(aktionRegel, /min-height:\s*\d+px/, 'keine nackte px-Zahl am Knopf')
  // UX1c: Der Grob-Zeiger-Block steht ungeschichtet am Dateianfang (Layer-Falle);
  // das Maß kommt aus `--control-h` (44 px am groben Zeiger) statt 44 als Zahl.
  const grob = css.slice(css.indexOf('@media (pointer: coarse) {'))
  assert.match(grob, /\.diakonos-toast-aktion,\s*\n\s*\.diakonos-toast-schliessen\s*\{\s*\n\s*min-height:\s*var\(--control-h\)/)
  assert.equal(
    (css.match(/@media \(pointer: coarse\)\s*\{/g) || []).length, 1,
    'genau ein Grob-Zeiger-Block (p3-4c)',
  )
  // Die Meldungsfläche selbst: am Handy volle Breite, Rückgängig unten links.
  // DEV-B6 (Review-Nacharbeit 10.11.): „Handy“ ist die Handy-Lage-Klasse
  // (`.dk-app--handy`, Quelle `composables/handyLage.mjs`), nicht die nackte
  // Breite — ein 702-px-Mausfenster behält die Desktop-Meldung.
  assert.match(block, /\.dk-app--handy \.diakonos-toast-container--undo/)
  // Am Desktop liegt sie IM Inhaltsbereich (hinter der Seitenleiste), nicht
  // auf der dunklen Seitenleiste — sonst dunkle Fläche auf dunklem Grund.
  const undoRegel = block.slice(
    block.indexOf('.diakonos-toast-container--undo {'),
    block.indexOf('}', block.indexOf('.diakonos-toast-container--undo {')),
  )
  assert.match(undoRegel, /left:\s*calc\(var\(--sidebar-w\)\s*\+\s*var\(--sp-6\)\)/)
})

test('C2 Eine Frist: ABlaufMS leitet sich aus ANZEIGE_MS ab (10 s)', () => {
  // MT-3 Review-Nacharbeit (Operator 11.11.): Vorher stand hier „8000 ms steht
  // nur in rueckgaengigStapel.mjs“ — Frist (8 s) und Anzeige (10 s) waren
  // getrennte Zeiten, und die Aktion lief mitten in der sichtbaren Meldung ab.
  // Entscheidung: Frist = Anzeige = EINE Konstante `ANZEIGE_MS`. Der Test
  // prüft jetzt die KOPPLUNG (und dass die Zahl nur EINE Quelle hat); das
  // Verhalten selbst prüft `tests/mt3b-rueckgaengig-kopplung.test.mjs`.
  const stapel = lies('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')
  const toast = lies('frontend/src/diakonos/composables/useToast.js')
  const composable = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
  const zeit = lies('frontend/src/diakonos/composables/meldungszeit.mjs')

  assert.match(stapel, /export const ABlaufMS = ANZEIGE_MS/,
    'die Frist leitet sich aus der Anzeigedauer ab')
  assert.doesNotMatch(stapel, /\b8000\b/, 'keine eigene 8-s-Zahl mehr')
  assert.equal(ABlaufMS, ANZEIGE_MS, 'Frist der Aktion = Anzeigedauer')
  assert.match(zeit, /export const ANZEIGE_MS = 10_?000/, 'die Zahl hat EINE Quelle')
  // Der Verbund nennt die Zahl NICHT selbst — er holt sie aus ANZEIGE_MS.
  assert.doesNotMatch(composable, /\b8000\b|\b10_?000\b/, 'useRueckgaengig kennt die Zahl nicht')
  assert.match(composable, /dauer:\s*ANZEIGE_MS/)
  assert.match(toast, /mitAktion:\s*ANZEIGE_MS/, 'Anzeige aus EINER Konstante')

  // Pflicht aus dem Konzept: „Rückgängig“ für einen einzelnen Eintrag geht
  // auch über die Meldung genau DIESER Aktion (id), nicht nur über Strg+Z.
  assert.match(composable, /zuruecknehmen\(eintrag\.id\)/)
  assert.match(composable, /tastaturHinweis\(\)/)
})
