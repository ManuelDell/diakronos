/**
 * UX2a2b — Restbefunde der Rückgängig-Meldung.
 *
 * Was dieser Test festhält, Punkt für Punkt nach der Karte:
 *
 *  1  Hover/Fokus halten die FRIST WIRKLICH an — nicht nur den Toast-Timer.
 *     Der 250-ms-Takt (`useRueckgaengig.js` → `stapel.pruefen`) darf den
 *     Eintrag nicht abräumen, solange der Zeiger auf der Meldung steht oder
 *     der Fokus darin ist; danach läuft die RESTZEIT weiter (gedeckelt).
 *     Geprüft wird der Takt selbst (Fake-Uhr), nicht ein Quelltext-Regex.
 *  2  Fokusdiebstahl: `beiMeldungZu` sichert den Fokus nur, wenn er in der
 *     schließenden Meldung lag (oder schon auf `body` verloren war). Ein
 *     Eingabefeld bleibt bei einem alten, ablaufenden Toast unberührt.
 *  3  Fokus-Rückfall kennt das Ziel aus `App.vue` (`#dk-inhalt`,
 *     `.dk-content`, tabindex="-1") — nie `<body>`.
 *  4  Esc schließt nur die OBERSTE Meldung (gleich welcher Art) und keine,
 *     solange ein Dialog offen ist.
 *  5  Keine Debug-Ausgabe mehr; die 56 px/420 px des Meldungsblocks stehen
 *     als Tokens in tokens.css.
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

/**
 * UX2a2b: Der Deckel kam mit dieser Karte. Auf dem alten Stand fehlt die
 * Konstante — die Tests sollen dann ROT werden (mit klarer Meldung), nicht
 * schon beim Laden der Datei abbrechen.
 */
let HALTE_DECKEL_MS = 20_000
try {
  const stapelModul = await import('../src/diakonos/composables/rueckgaengigStapel.mjs')
  if (Number.isFinite(stapelModul.HALTE_DECKEL_MS)) HALTE_DECKEL_MS = stapelModul.HALTE_DECKEL_MS
} catch { /* alter Stand: Standardwert bleibt, die Tests scheitern einzeln */ }
void GRENZE

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

// ── DOM-Attrappe ───────────────────────────────────────────────────────────
// Wie in ux2a2-meldung.test.mjs, plus: `focus()` feuert `focusin`, `closest`
// versteht zusammengesetzte Auswahlen (Selektorliste) und Id-Auswahlen.

class Knoten {
  constructor(tag = 'div') {
    this.tagName = String(tag).toUpperCase()
    this.children = []
    this.parentNode = null
    this.attrs = {}
    this.listeners = {}
    this.style = {}
    this.className = ''
    this.id = ''
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
    return this
  }
  focus() {
    this.focused = true
    if (this.ownerDocument) this.ownerDocument.activeElement = this
    if (this.ownerDocument?.listeners?.focusin) {
      this.ownerDocument.dispatch('focusin', { target: this })
    }
  }
  /** `closest` für „.klasse“, „#id“ und Selektorlisten (`a, b`). */
  closest(auswahl) {
    const teile = String(auswahl).split(',').map(s => s.trim()).filter(Boolean)
    const passt = (el, sel) => {
      if (sel.startsWith('.')) return `${el.className}`.split(/\s+/).includes(sel.slice(1))
      if (sel.startsWith('#')) return el.id === sel.slice(1)
      if (sel.startsWith('[')) {
        const name = sel.slice(1, sel.indexOf(']')).split('=')[0]
        return name in el.attrs
      }
      return `${el.tagName}`.toLowerCase() === sel.toLowerCase()
    }
    const passend = (el) => teile.some(sel => passt(el, sel))
    let knoten = this
    while (knoten) {
      if (passend(knoten)) return knoten
      knoten = knoten.parentNode
    }
    return null
  }
  querySelector(auswahl) {
    const teile = String(auswahl).split(',').map(s => s.trim()).filter(Boolean)
    const pruefe = (knoten, sel) => {
      if (sel.startsWith('[data-meldung="')) {
        const id = sel.slice('[data-meldung="'.length, -2)
        return knoten.getAttribute?.('data-meldung') === id
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
  }
  createElement(tag) { const k = new Knoten(tag); k.ownerDocument = this; return k }
}

function knoepfe(el, gefunden = []) {
  if (el.tagName === 'BUTTON') gefunden.push(el)
  for (const k of el.children) knoepfe(k, gefunden)
  return gefunden
}

let ladeZaehler = 0

/**
 * `useRueckgaengig.js` ausführbar laden (vue → Attrappe, Nachbardateien als
 * echte Module). Je Test eine frische Kopie: der Modulzustand ist modulweit.
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
    + Buffer.from(quelle).toString('base64') + `#ux2a2b-${ladeZaehler}`)
  return { mod, toast: toastMod }
}

/**
 * Welt mit ECHTER Zeit: `setTimeout`/`setInterval` laufen auf der echten Uhr,
 * damit der Takt wirklich tickt (die Karte verlangt es ausdrücklich — kein
 * Quelltext-Regex). `Date.now` bleibt manipulierbar für Sprünge.
 */
function weltVorbereiten() {
  const document = new Dokument()
  const window = new Knoten('window')
  globalThis.document = document
  globalThis.window = window
  Object.defineProperty(globalThis, 'navigator', {
    value: { platform: 'Linux x86_64', userAgent: 'node' }, configurable: true, writable: true,
  })
  globalThis.requestAnimationFrame = (fn) => { fn(); return 1 }
  return { document, window }
}

function weltZurueck() {
  delete globalThis.document
  delete globalThis.window
}

const warten = (ms) => new Promise(r => setTimeout(r, ms))
const tick = () => new Promise(r => setImmediate(r))

// ══════════════════════════════════════════════════════════════════════════
// 1 · Der Stapel selbst: Anhalten und Fortsetzen (reine Logik)
// ══════════════════════════════════════════════════════════════════════════

test('1a Stapel: pausieren haelt die Frist an, fortsetzen verlaengert um die Standzeit', () => {
  const stapel = new RueckgaengigStapel()
  const eintrag = stapel.registrieren('Zeile entfernt', async () => {}, { jetzt: 1_000 })
  const ablaufVorher = eintrag.ablauf
  assert.equal(ablaufVorher, 1_000 + ABlaufMS)

  // Zeiger steht 3 s auf der Meldung — der Takt prüft jede Viertelsekunde.
  assert.equal(stapel.pausieren(eintrag.id, 2_000), true, 'angehalten')
  for (let t = 2_000; t < 5_000; t += 250) {
    assert.deepEqual(stapel.pruefen(t), [], `angehalten laeuft nicht ab (t=${t})`)
  }
  assert.equal(stapel.laenge, 1, 'der Eintrag bleibt im Stapel')

  const fortgesetzt = stapel.fortsetzen(eintrag.id, { jetzt: 5_000 })
  assert.ok(fortgesetzt, 'fortgesetzt')
  assert.equal(fortgesetzt.ablauf, ablaufVorher + 3_000,
    'die Frist waechst genau um die Standzeit (3 s), Restzeit bleibt erhalten')
  assert.equal(stapel.pruefen(ablaufVorher + 3_000 - 1).length, 0, 'kurz davor noch gueltig')
  assert.equal(stapel.pruefen(ablaufVorher + 3_000).length, 1, 'danach abgelaufen')
})

test('1b Stapel: der Deckel begrenzt die Verlaengerung (liegengebliebener Zeiger)', () => {
  const stapel = new RueckgaengigStapel()
  const eintrag = stapel.registrieren('Zeile entfernt', async () => {}, { jetzt: 0 })
  const ablaufVorher = stapel.alle()[0].ablauf
  assert.equal(ablaufVorher, ABlaufMS)
  stapel.pausieren(eintrag.id, 1_000)
  // Der Zeiger steht eine Stunde lang auf der Meldung (Tab-Schlaf), die letzte
  // Bewegung war kurz vor dem Verlassen.
  stapel.pausieren(eintrag.id, 60 * 60 * 1000 - 5)
  stapel.fortsetzen(eintrag.id, { jetzt: 60 * 60 * 1000, deckelMs: HALTE_DECKEL_MS })
  const fortgesetzt = stapel.alle().find(e => e.id === eintrag.id)
  assert.ok(fortgesetzt, 'der Eintrag lebt weiter')
  // Angehalten bei 8 s Ablauf, 3599 s stehen geblieben: die Frist waechst um
  // die Standzeit — aber der Deckel (HALTE_DECKEL_MS Restzeit ab dem
  // Fortsetzen) begrenzt sie.
  assert.equal(fortgesetzt.ablauf, ablaufVorher + 3_599_000,
    'die Frist waechst um die Standzeit, nicht um die Uhrzeit-Position')
  assert.ok(fortgesetzt.ablauf <= 60 * 60 * 1000 + HALTE_DECKEL_MS,
    'nie mehr als HALTE_DECKEL_MS Restzeit ab dem Fortsetzen')

  // Ganz ohne Deckel-Freigabe: ebenfalls hoechstens halteDeckelMs.
  const stapelZwei = new RueckgaengigStapel()
  const zwei = stapelZwei.registrieren('Zweite', async () => {}, { jetzt: 0 })
  // Ohne Deckel steckt die Frist schon abgelaufen (ablauf 8000 < 3600000).
  stapelZwei.pausieren(zwei.id, 0)
  stapelZwei.pausieren(zwei.id, 3_000)
  stapelZwei.fortsetzen(zwei.id, { jetzt: 3_000 })
  assert.equal(stapelZwei.alle()[0].ablauf, ABlaufMS + 3_000,
    'jenseits des Deckels gilt die Obergrenze, nicht das Wachsen')
})

test('1c Stapel: fortsetzen ohne pausieren ist wirkungslos, Ruecknahme geht weiter', async () => {
  const stapel = new RueckgaengigStapel()
  let zurueck = 0
  const eintrag = stapel.registrieren('Zeile entfernt', async () => { zurueck += 1 }, { jetzt: 0 })
  assert.equal(stapel.fortsetzen(eintrag.id, { jetzt: 5_000 }), null,
    'nichts angehalten — nichts fortzusetzen')
  assert.equal(stapel.alle()[0].ablauf, ABlaufMS, 'die Frist bleibt unveraendert')
  await stapel.zuruecknehmen(eintrag.id, { jetzt: 1 })
  assert.equal(zurueck, 1)
})

// ══════════════════════════════════════════════════════════════════════════
// 1d · Die VERBINDUNG: der Takt (250 ms) laesst waehrend Hover/Fokus nichts
//      ablaufen — vorher raeumte er den Eintrag nach 8 s weg, waehrend die
//      Meldung stehen blieb (Befund aus dem Review).
// ══════════════════════════════════════════════════════════════════════════

test('1d Takt raeumt NICHT ab, solange Hover/Fokus auf der Meldung liegt', async () => {
  const welt = weltVorbereiten()
  const echterJetzt = Date.now
  let uhr = 100_000
  Date.now = () => uhr
  try {
    const { mod } = await ladeRueckgaengig()
    let zurueck = 0
    mod.registrieren('Aus Gruppe entfernt', async () => { zurueck += 1 })
    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]
    assert.equal(mod.getStapel().laenge, 1, 'angemeldet')

    // Zeiger auf die Meldung, dann laeuft die Zeit 20 s weiter — der Takt
    // tickt dabei wirklich (echtes setInterval, 250 ms).
    meldung.dispatch('mouseenter', {})
    const ende = uhr + 20_000
    while (uhr < ende) {
      uhr += 1_000
      await warten(260)
    }
    assert.equal(mod.getStapel().laenge, 1,
      'der Eintrag bleibt zurueckholbar, solange die Meldung festgehalten wird')
    assert.equal(mod.rueckgaengigAnzahl.value, 1)

    // Der Knopf tut auch nach 20 s noch etwas: die Frist stand.
    const knopf = knoepfe(meldung)[0]
    knopf.dispatch('click', {})
    await tick()
    await tick()
    assert.equal(zurueck, 1, 'Ruecknahme nach 20 s Hover wirkt noch')

    // Und OHNE Hover laeuft die Frist: nach 8 s raeumt der Takt ab.
    mod.rueckgaengigZuruecksetzen()
    mod.registrieren('Zweite Aktion', async () => {})
    assert.equal(mod.getStapel().laenge, 1)
    const endeZwei = uhr + ABlaufMS + 1_500
    while (uhr < endeZwei) {
      uhr += 1_000
      await warten(260)
    }
    assert.equal(mod.getStapel().laenge, 0, 'ohne Hover laeuft die Aktion nach 8 s ab')
  } finally {
    Date.now = echterJetzt
    weltZurueck()
  }
})

test('1e Verlassen der Meldung laesst die RESTZEIT weiterlaufen (nicht neu starten)', async () => {
  const welt = weltVorbereiten()
  const echterJetzt = Date.now
  let uhr = 200_000
  Date.now = () => uhr
  try {
    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Aktion', async () => {})
    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]
    const eintrag = mod.getStapel().oberster()
    const ablaufVorher = eintrag.ablauf

    // 5 s von 8 s vergehen, dann kommt der Zeiger (anhalten, 3 s stehen).
    for (let i = 0; i < 5; i += 1) { uhr += 1_000; await warten(120) }
    meldung.dispatch('mouseenter', {})
    await warten(60)
    uhr += 3_000
    await warten(60)
    meldung.dispatch('mouseleave', {})
    await tick()

    const nachher = mod.getStapel().alle().find(e => e.id === eintrag.id)
    assert.ok(nachher, 'der Eintrag lebt')
    assert.ok(nachher.ablauf >= ablaufVorher + 2_500 && nachher.ablauf <= ablaufVorher + 3_000,
      `Frist um die Standzeit (~3 s) verlaengert, nicht neu gestartet `
      + `(vorher ${ablaufVorher}, jetzt ${nachher.ablauf})`)
  } finally {
    Date.now = echterJetzt
    weltZurueck()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Fokusdiebstahl
// ══════════════════════════════════════════════════════════════════════════

test('2 Fokus bleibt im Eingabefeld, wenn ein Toast ablaeuft (kein Fokusdiebstahl)', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    // Ein Namensfeld, in dem der Nutzer gerade tippt.
    const feld = welt.document.createElement('input')
    feld.className = 'dk-ui-eingabe'
    feld.id = 'name'
    welt.document.body.appendChild(feld)
    // Zwei Meldungen: die des Stapels („Rückgängig“) und ein älterer Erfolg.
    const alter = toast.showToast('Gespeichert', 'success', null, { dauer: 4000 })
    mod.registrieren('Telefonnummer entfernt', async () => {})
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const knopf = knoepfe(behaelter.children.at(-1))[0]

    // Der Nutzer stand vorhin auf „Rückgängig“ und tippt JETZT im Feld — der
    // Fokuswechsel kam ohne `focusin` (Seitenwechsel, Klick in ein Feld, das
    // der Browser ohne Fokus-Ereignis setzt; `fokusVorher` haelt also noch
    // die MELDUNG). Genau dann hat das alte `fokusSichern()` den Fokus aus
    // dem Feld gerissen, weil es `fokusVorher` ungeprueft fokussierte.
    knopf.focus()
    welt.document.activeElement = feld          // Wechsel ohne focusin-Ereignis
    assert.equal(welt.document.activeElement, feld)

    alter('frist')
    await tick()
    assert.equal(welt.document.activeElement, feld,
      'das Eingabefeld bleibt fokussiert — ein alter Toast stiehlt keinen Fokus')

    // Auch die Rückgängig-Meldung selbst: läuft sie nebenbei ab, während der
    // Nutzer tippt, darf sie den Fokus nicht mitnehmen.
    welt.document.activeElement = feld
    mod.getStapel().pruefen(Date.now() + 60_000)
    await tick()
    assert.equal(welt.document.activeElement, feld,
      'auch der Ablauf der Rueckgaengig-Meldung laesst den Fokus im Feld')

    // Die Regel steht an EINER Stelle und prüft die HERKUNFT des Fokus.
    // UX2a2c: nur der SCHLIESSENDE Toast zählt (`ausMeldung.contains`), nicht
    // irgendein `.diakonos-toast` — sonst riss eine ablaufende
    // Rückgängig-Meldung den Fokus vom ✕ einer Fehlermeldung weg.
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /const inMeldung = Boolean\(aktiv[\s\S]{0,200}?ausMeldung\.contains\(aktiv\)/,
      'fokusSichern prueft, ob der Fokus in DIESER Meldung steht')
    // Und nicht mehr über irgendeinen Toast: der Zweig `fokusSichern` fragt
    // nicht mehr `.closest('.diakonos-toast')`, sondern vergleicht mit
    // `ausMeldung`.
    const abSichern = quelle.slice(quelle.indexOf('function fokusSichern'),
      quelle.indexOf('function meldungZeigen'))
      .split('\n').filter(z => !/^\s*(\/\/|\*|\/\*)/.test(z)).join('\n')   // Kommentare zaehlen nicht
    assert.doesNotMatch(abSichern, /closest\(['"]\.diakonos-toast['"]\)/,
      'nicht irgendeine Meldung — nur der schliessende Toast')
    assert.match(quelle, /if \(!inMeldung\) \{[\s\S]{0,200}?return/,
      'sonst fasst fokusSichern den Fokus nicht an')
  } finally {
    weltZurueck()
  }
})

test('2b Fokus in einer Meldung, die schliesst, wandert auf den naechsten Knopf', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Erste Aktion', async () => {})
    mod.registrieren('Zweite Aktion', async () => {})
    const meldungen = welt.document.querySelector('.diakonos-toast-container').children
    const oberste = meldungen[meldungen.length - 1]
    const knopf = knoepfe(oberste)[0]

    knopf.focus()
    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal(welt.document.activeElement, knoepfe(meldungen[0])[0],
      'Fokus steht auf „Rueckgaengig“ der verbleibenden Meldung')
  } finally {
    weltZurueck()
  }
})

/**
 * UX2a2c: Der Fokus auf dem ✕ einer FEHLERmeldung bleibt, wenn eine
 * Rückgängig-Meldung schließt, in der er NICHT stand. Vorher genügte
 * `closest('.diakonos-toast')` — jede offene Meldung galt als „Herkunft“,
 * und `fokusSichern` schob den Fokus vom ✕ weg (auf den Knopf der nächsten
 * Meldung oder die Hauptfläche).
 *
 * Ablauf: Der Rückgängig-Toast hält seine Frist an, weil der Zeiger darauf
 * stand (Hover). Dann wandert der Fokus auf das ✕ der Fehlermeldung, und der
 * Rückgängig-Toast wird verdrängt (neue Meldungen, Frist abgelaufen): genau
 * der Fall „Toast schließt, Fokus steht woanders“.
 */
test('2c Fokus auf dem ✕ einer Fehlermeldung bleibt, wenn ein Rueckgaengig-Toast schliesst', async () => {
  const welt = weltVorbereiten()
  try {
    // Hauptfläche wie App.vue — dorthin fiele der Fokus beim alten Verhalten.
    const inhalt = welt.document.createElement('div')
    inhalt.className = 'dk-content'
    inhalt.id = 'dk-inhalt'
    inhalt.setAttribute('tabindex', '-1')
    welt.document.body.appendChild(inhalt)

    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Zeile entfernt', async () => {})
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const rueckgaengig = behaelter.children[0]
    // Zeiger stand auf der Rückgängig-Meldung: die Frist der Aktion ist angehalten.
    rueckgaengig.dispatch('mouseenter', {})
    assert.equal(mod.getStapel().alle()[0].haelt, true, 'Frist angehalten (Hover)')

    toast.showToast('Das hat nicht geklappt.', 'error')
    const fehler = behaelter.children.at(-1)
    const kreuz = knoepfe(fehler).at(-1)
    assert.equal(kreuz.getAttribute('aria-label'), 'Meldung schließen',
      'der letzte Knopf der Fehlermeldung ist das ✕')
    kreuz.focus()
    assert.equal(welt.document.activeElement, kreuz, 'Ausgangslage: Fokus auf dem ✕')

    // Der Rückgängig-Toast schließt, während der Fokus auf dem ✕ steht
    // (Grund „frist“/Verdrängung — NICHT „klick“; genau dort griff der Fehler).
    toast.entferneToast(mod.getStapel().alle()[0] && `rueckgaengig-${mod.getStapel().alle()[0].id}-1`)
    await tick()

    assert.equal(welt.document.activeElement, kreuz,
      'der Fokus bleibt auf dem ✕ der Fehlermeldung — nicht auf body/Hauptfläche')
    assert.notEqual(welt.document.activeElement, inhalt)
    assert.notEqual(welt.document.activeElement, welt.document.body)
  } finally {
    weltZurueck()
  }
})

/**
 * UX2a2c: Ein VERDRÄNGTER Toast gibt seine Frist wieder frei.
 *
 * Befund: `beiMeldungZu` sicherte nur bei „klick“/„esc“ den Stapel. Wurde die
 * Meldung verdrängt (Grenze erreicht), blieb `eintrag.haelt = true` stehen —
 * `pruefen` räumt angehaltene Einträge NIE ab, die Aktion blieb also ewig
 * zurückholbar, ohne dass eine Meldung den Knopf noch anbot.
 */
test('2d Ein verdraengter Rueckgaengig-Toast haelt die Frist nicht ewig', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    const stapel = mod.getStapel()
    // Der Stapel haelt GRENZE Meldungen (HOECHSTENS === GRENZE). Die aelteste
    // MELDUNG wird verdrängt, sobald eine weitere hinzukommt — ihr EINTRAG
    // bleibt dann noch im Stapel (Grenze 5, es fällt keiner heraus). Genau
    // dieser Zustand ist der Befund: „Meldung weg, Frist hält ewig“.
    for (let i = 0; i < GRENZE; i += 1) mod.registrieren(`Aktion ${i + 1}`, async () => {})
    const aelteste = stapel.alle()[0]
    assert.equal(aelteste.beschreibung, 'Aktion 1', 'aelteste Aktion im Stapel')

    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const elAelteste = behaelter.children.find(el => knoepfe(el)
      .some(k => `${k.getAttribute('aria-label')}`.includes(aelteste.beschreibung)))
    assert.ok(elAelteste, 'die Meldung der aeltesten Aktion steht')
    // Der Zeiger stand auf der Meldung: die Frist ist angehalten.
    elAelteste.dispatch('mouseenter', {})
    assert.equal(stapel.alle()[0].haelt, true, 'Frist angehalten (Hover)')

    // Eine weitere Meldung: die aelteste wird verdrängt (Fehler zählt nicht
    // mit — er ist nie entbehrlich, also eine normale Erfolgsmeldung).
    toast.showToast('Gespeichert.')
    await tick()

    const nachher = stapel.alle().find(e => e.beschreibung === 'Aktion 1')
    assert.ok(nachher, 'der Eintrag steht noch im Stapel (Grenze haelt 5)')
    assert.equal(nachher.haelt, false,
      'die Frist ist freigegeben — der Eintrag haengt nicht mehr')
    // `deckelMs: 0` heisst: keine neue Gnadenfrist — der Ablauf liegt jetzt.
    stapel.pruefen(Date.now() + 1)
    assert.equal(stapel.alle().some(e => e.beschreibung === 'Aktion 1'), false,
      'und er laeuft beim naechsten Takt ab (kein ewiges Strg+Z ins Leere)')
  } finally {
    weltZurueck()
  }
})

/**
 * UX2a2c (nach UX2g): Die Floskel-Erkennung von `fehlerMeldung` ist die des
 * Fehlerkatalogs — nicht mehr eine eigene Drei-Wörter-Liste. Sonst gingen
 * „Fehler beim Laden“, „Ein Fehler ist aufgetreten“ … als Toast durch.
 */
test('2e fehlerMeldung kennt dieselben Floskeln wie der Fehlerkatalog (UX2g)', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod } = await ladeRueckgaengig()
    assert.equal(typeof mod.fehlerMeldung, 'function', 'fehlerMeldung ist da')
    const katalog = await import(pathToFileURL(
      join(HIER, '..', 'src', 'shared', 'fehlertexte.js')).href)
    const floskeln = ['Fehler', 'Unbekannter Fehler', 'API-Fehler',
      'Ein Fehler ist aufgetreten', 'Fehler beim Laden', 'Fehler beim Speichern']
    for (const floskel of floskeln) {
      assert.ok(katalog.istFloskel(floskel), `Katalog kennt die Floskel: ${floskel}`)
      const text = mod.fehlerMeldung({ message: floskel })
      assert.notEqual(text, floskel, `„${floskel}" wird nicht angezeigt`)
      assert.equal(text, 'Das hat nicht geklappt. Bitte versuche es später noch einmal.',
        `„${floskel}" -> Ersatzsatz`)
    }
    // Ein fachlicher Satz des Servers geht wörtlich durch.
    const fachlich = 'Das Ende muss nach dem Beginn liegen.'
    assert.equal(mod.fehlerMeldung({ message: fachlich }), fachlich)
    // Und die Quelle benutzt den Katalog, nicht eine eigene Kopie.
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /import \{ istFloskel \} from '\.\.\/\.\.\/shared\/fehlertexte\.js'/,
      'istFloskel kommt aus dem Katalog')
    assert.doesNotMatch(quelle, /Unbekannter Fehler\|API-Fehler/,
      'keine eigene Floskel-Liste mehr')
  } finally {
    weltZurueck()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Fokus-Rueckfall: das Ziel aus App.vue

test('3 Fokus faellt auf #dk-inhalt/.dk-content zurueck (App.vue), nie auf body', async () => {
  const welt = weltVorbereiten()
  try {
    // DOM wie App.vue: <div id="dk-inhalt" class="dk-content" tabindex="-1">.
    const inhalt = welt.document.createElement('div')
    inhalt.className = 'dk-content'
    inhalt.id = 'dk-inhalt'
    inhalt.setAttribute('tabindex', '-1')
    welt.document.body.appendChild(inhalt)

    const { mod } = await ladeRueckgaengig()
    mod.registrieren('Einzige Aktion', async () => {})
    const meldung = welt.document.querySelector('.diakonos-toast-container').children[0]
    knoepfe(meldung)[0].focus()

    // Esc schliesst die einzige Meldung: kein Knopf mehr da — das Ziel aus
    // App.vue muss greifen.
    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal(welt.document.activeElement, inhalt,
      'Fokus steht in der Hauptflaeche (#dk-inhalt/.dk-content)')
    assert.notEqual(welt.document.activeElement, welt.document.body)

    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /#dk-inhalt, \.dk-content/,
      'der Rueckfall kennt das Ziel aus App.vue')
    assert.match(lies('frontend/src/diakonos/App.vue'),
      /id="dk-inhalt"[\s\S]{0,200}?tabindex="-1"/,
      'App.vue haelt das Ziel fokussierbar')
  } finally {
    weltZurueck()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Esc: nur die OBERSTE Meldung, gleich welcher Art
// ══════════════════════════════════════════════════════════════════════════

test('4a Esc schliesst die oberste FEHLERmeldung, nicht die Rueckgaengig-Meldung darunter', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Zeile entfernt', async () => {})
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const rueckgaengig = behaelter.children[0]

    // Eine Fehlermeldung erscheint SPAETER (oben bzw. rechts) — Esc gehoert ihr.
    toast.showToast('Das hat nicht geklappt.', 'error')
    const fehler = behaelter.children.at(-1)

    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal(fehler.className.includes('show'), false, 'die oberste (Fehler-)Meldung ist zu')
    assert.equal(rueckgaengig.className.includes('show'), true,
      'die Rueckgaengig-Meldung darunter bleibt stehen')
    assert.equal(mod.getStapel().laenge, 1, 'ihr Eintrag bleibt zurueckholbar')

    // Noch ein Esc: jetzt faellt die Rueckgaengig-Meldung (samt Eintrag).
    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal(rueckgaengig.className.includes('show'), false, 'jetzt ist sie dran')
    assert.equal(mod.getStapel().laenge, 0, 'Esc verwirft den Eintrag (kein spaetes Strg+Z)')
  } finally {
    weltZurueck()
  }
})

test('4b Esc schliesst gar nichts, solange ein Dialog offen ist — auch keine Fehlermeldung', async () => {
  const welt = weltVorbereiten()
  try {
    const { mod, toast } = await ladeRueckgaengig()
    mod.registrieren('Zeile entfernt', async () => {})
    toast.showToast('Das hat nicht geklappt.', 'error')
    const behaelter = welt.document.querySelector('.diakonos-toast-container')
    const vorher = behaelter.children.map(k => k.className.includes('show'))

    const dialog = welt.document.createElement('div')
    dialog.className = 'dk-ui-dialog'
    dialog.setAttribute('role', 'dialog')
    dialog.setAttribute('aria-modal', 'true')
    welt.document.body.appendChild(dialog)

    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.deepEqual(behaelter.children.map(k => k.className.includes('show')), vorher,
      'kein Toast schliesst, solange der Dialog offen ist')
    assert.equal(mod.getStapel().laenge, 1, 'der Eintrag bleibt')

    // Dialog zu — Esc greift wieder.
    dialog.remove()
    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal(behaelter.children.at(-1).className.includes('show'), false)
  } finally {
    weltZurueck()
  }
})

test('4c Esc beruehrt keine Meldungen, wenn gar keine offen ist (kein Fehler)', async () => {
  const welt = weltVorbereiten()
  try {
    const { toast } = await ladeRueckgaengig()
    toast.schliesseAlle()
    // Kein Zuhörer, kein Absturz.
    const anzahl = (welt.document.listeners.keydown || []).length
    welt.document.dispatch('keydown', { key: 'Escape' })
    await tick()
    assert.equal((welt.document.listeners.keydown || []).length, anzahl)
    assert.equal(toast.offeneMeldungen.length, 0)
  } finally {
    weltZurueck()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Keine Debug-Ausgabe, 56/420 px als Tokens
// ══════════════════════════════════════════════════════════════════════════

test('5a Keine Debug-Ausgabe (DBG) mehr in den Tests der Rueckgaengig-Meldung', () => {
  for (const datei of [
    'frontend/tests/ux2a-rueckgaengig.test.mjs',
    'frontend/tests/ux2a2-meldung.test.mjs',
    'frontend/tests/ux2a2b-meldung.test.mjs',
  ]) {
    const quelle = lies(datei)
    assert.doesNotMatch(quelle, /console\.(error|log|debug)\(\s*['"]DBG/,
      `${datei}: keine DBG-Ausgabe`)
  }
})

test('5c Kein Abnahme-Haken mehr: der Wegwerf-Haken der Abnahme ist entfernt', () => {
  // UX2a2c: Der Dev-Haken (`window.__diakronosRueckgaengig`) war nur für die
  // Abnahme da und ist NICHT bestellt. Ein stehengebliebener Haken im Bundle
  // wäre ein offenes Fenster in die App-Mechanik — er muss weg sein, samt
  // Aufruf in `App.vue`.
  assert.equal(existsSync(join(HIER, '..', 'src', 'diakonos', 'composables',
    'abnahmeRueckgaengig.js')), false, 'abnahmeRueckgaengig.js ist entfernt')
  const app = lies('frontend/src/diakonos/App.vue')
  assert.doesNotMatch(app, /abnahmeHakenPruefen|abnahmeRueckgaengig/,
    'App.vue kennt den Abnahme-Haken nicht mehr')
  for (const datei of ['frontend/src/diakonos/App.vue',
    'frontend/src/diakonos/composables/useRueckgaengig.js',
    'frontend/src/diakonos/composables/useToast.js']) {
    assert.doesNotMatch(lies(datei), /__diakronosRueckgaengig/,
      `${datei}: kein Haken am Fenster`)
  }
})

test('5b 56 px und 420 px stehen als Token in tokens.css, nicht im Meldungsblock', () => {
  const tokens = lies('frontend/src/diakonos/tokens.css')
  assert.match(tokens, /--melde-w:\s*420px/, 'Breite der Meldung als Token')
  assert.match(tokens, /--melde-min-h:\s*56px/, 'Mindesthoehe der Meldung als Token')

  const css = lies('frontend/src/diakonos/index.css')
  const start = css.indexOf('Meldungen (früher: Toast)')
  const block = css.slice(start, css.indexOf('Widget Grid & Cards', start))
  assert.ok(block.length > 500, 'Meldungsblock gefunden')
  assert.doesNotMatch(block, /min-height:\s*56px/, 'keine nackte 56px mehr')
  assert.doesNotMatch(block, /\b420px/, 'keine nackte 420px mehr')
  assert.match(block, /min-height:\s*var\(--melde-min-h\)/)
  assert.match(block, /min\(var\(--melde-w\),/)
})
