/**
 * MT-3 — Meldungen (Toasts) blenden nach 10 s automatisch aus.
 *
 * BEFUND (Manuel 11.11.): Meldungen oben rechts blieben dauerhaft stehen.
 * SOLL: automatisch nach 10 Sekunden ausblenden — auch Fehler-/Warnmeldungen
 * und Meldungen mit Handlung (z. B. „Rückgängig“). Schließen-Knopf bleibt,
 * Hover/Fokus pausieren (Barrierefreiheit), EINE Zahl als Konstante.
 *
 *  A  Eine Anzeigedauer für ALLE Meldungen (`DAUER_MS` → 10 000 ms), keine
 *     Ausnahme für `error` (vorher 0 = bis zum Schließen). Auch die
 *     Meldung mit Handlung und die Rückgängig-Meldung: Anzeige und
 *     Aktionsfrist sind DIESELBE Zeit (`ANZEIGE_MS`, 10 s) — das
 *     Rückgängig-FENSTER ist nicht mehr kurz und die Anzeige lang.
 *  B  Verhalten mit Fake-Timern: nach 10 s ist die Meldung weg (`frist`),
 *     Schließen-Knopf bleibt, Hover/Fokus halten die Uhr an (Restzeit läuft
 *     danach weiter), und der Halte-Deckel (20 s) nimmt eine liegengebliebene
 *     Bremse weg — eine Meldung hängt nie für immer.
 *  C  Quelle: die Zeit steht EINMAL (`ANZEIGE_MS`), abgeleitet aus der
 *     gemeinsamen Basis — nicht als zweite Zahl abgeschrieben.
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

// ── DOM-Attrappe (gleiche Form wie ux2a2-meldung.test.mjs) ─────────────────

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
    for (const fn of [...(this.listeners[k] || [])]) fn(ereignis)
  }
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
    const treffer = (knoten) => {
      if (auswahl.startsWith('[data-meldung="')) {
        const id = auswahl.slice('[data-meldung="'.length, -2)
        if (knoten.getAttribute?.('data-meldung') === id) return knoten
      } else if (auswahl.startsWith('.')) {
        if (`${knoten.className}`.split(/\s+/).includes(auswahl.slice(1))) return knoten
      } else if (auswahl.includes('[role="dialog"]')) {
        const rollen = (auswahl.match(/\[role="([a-z]+)"\]/g) || []).map(r => r.slice(7, -2))
        const modal = auswahl.includes('aria-modal')
        if (rollen.includes(knoten.getAttribute?.('role'))
            && (!modal || knoten.getAttribute?.('aria-modal') === 'true')) return knoten
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

/**
 * Fake-Uhr: die Zeit läuft NUR, wenn der Test sie schiebt. Damit prüft der
 * Test „nach 10 s ist die Meldung weg“ ohne echtes Warten.
 */
function uhrVorbereiten() {
  const document = new Dokument()
  const timer = []
  let jetzt = 1_000_000
  globalThis.document = document
  globalThis.window = new Knoten('window')
  globalThis.Date.now = () => jetzt
  globalThis.requestAnimationFrame = (fn) => { fn(); return 1 }
  const echte = { timeout: globalThis.setTimeout, interval: globalThis.setInterval }
  globalThis.setTimeout = (fn, ms) => { timer.push({ fn, ms, um: jetzt + Number(ms || 0) }); return timer.length }
  globalThis.setInterval = () => 1
  globalThis.clearTimeout = (id) => { const t = timer[id - 1]; if (t) t.weg = true }
  globalThis.clearInterval = () => {}
  /** Zeit vorschieben: alle fälligen Timer (in Reihenfolge) laufen lassen. */
  const schieben = (ms) => {
    const ziel = jetzt + ms
    for (let runde = 0; runde < 20; runde += 1) {
      const faellig = timer
        .filter(t => !t.weg && t.um <= ziel)
        .sort((a, b) => a.um - b.um)[0]
      if (!faellig) break
      jetzt = faellig.um
      faellig.weg = true
      faellig.fn()
    }
    jetzt = ziel
  }
  return {
    document,
    timer,
    schieben,
    setze: (t) => { jetzt = t },
    zurueck() {
      globalThis.setTimeout = echte.timeout
      globalThis.setInterval = echte.interval
      delete globalThis.document
      delete globalThis.window
    },
  }
}

let ladeZaehler = 0

/** `useToast.js` frisch laden (eigener Modulzustand je Test). */
async function ladeToast() {
  ladeZaehler += 1
  const quelle = lies('frontend/src/diakonos/composables/useToast.js')
    .replace(
      "from '../../shared/fehlertexte.js'",
      `from '${dateiUrl('frontend/src/shared/fehlertexte.js')}'`,
    )
    .replace(
      "from './rueckgaengigStapel.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')}'`,
    )
    // MT-3: die eine Zeit steht in einer eigenen Datei — in einer data:-URL
    // loest kein relativer Pfad auf (ERR_UNSUPPORTED_RESOLVE_REQUEST).
    .replace(
      "from './meldungszeit.mjs'",
      `from '${dateiUrl('frontend/src/diakonos/composables/meldungszeit.mjs')}'`,
    )
  const url = 'data:text/javascript;base64,' + Buffer.from(quelle).toString('base64')
  return import(`${url}#mt3-${ladeZaehler}`)
}

const meldungIn = (document) => document.querySelector('.diakonos-toast-container')?.children[0]

// ── A · Eine Zeit für alle Meldungen ──────────────────────────────────────

test('A1 DAUER_MS gilt für ALLE Typen mit 10 000 ms — auch für Fehler', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    const d = toast.DAUER_MS
    assert.equal(d.error, 10000, 'Fehlermeldungen laufen jetzt auch ab')
    assert.equal(d.warning, 10000, 'Warnmeldungen ebenso')
    assert.equal(d.normal, 10000)
    assert.equal(d.mitAktion, 10000, 'Meldung mit Handlung: Anzeige 10 s')
    assert.equal(toast.ANZEIGE_MS, 10000, 'eine benannte Zeit für die Anzeige')

    // Jeder Typ, wirklich gezeigt, meldet GENAU diese Frist an.
    for (const typ of ['info', 'success', 'error', 'warning']) {
      toast.schliesseAlle()
      welt.timer.length = 0
      toast.showToast(`Meldung ${typ}`, typ)
      assert.ok(welt.timer.some(t => !t.weg && t.ms === 10000),
        `${typ}: 10 s angemeldet; gefunden: ${welt.timer.map(t => t.ms).join(', ')}`)
    }
    // Mit Handlung: dieselbe Anzeigedauer.
    toast.schliesseAlle()
    welt.timer.length = 0
    toast.showToast('Ansehen', 'success', { text: 'Ansehen', onClick: () => {} })
    assert.ok(welt.timer.some(t => !t.weg && t.ms === 10000), 'Meldung mit Aktion: 10 s')
  } finally {
    welt.zurueck()
  }
})

test('A2 Rückgängig-Meldung: Anzeige UND Frist sind dieselbe Zeit (10 s)', async () => {
  // MT-3 Review-Nacharbeit (Operator 11.11.): Hier stand „Frist bleibt 8 s"
  // und eine Regex-Prüfung, die nur belegte, dass `dauer` NICHT `ABlaufMS`
  // ist. Genau diese Entkopplung war der Fehler: der Takt räumte die Meldung
  // nach 8 s ab, der 10-s-Timer griff nie. Entscheidung: Frist = Anzeige =
  // EINE Konstante. Das VERHALTEN prüft `tests/mt3b-rueckgaengig-kopplung.test.mjs`
  // (Fake-Uhr: 9,9 s da / 10,1 s beides weg, Hover hält beide) — hier bleibt
  // nur die Quellprüfung auf die Kopplung.
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    const { ABlaufMS } = await import(
      dateiUrl('frontend/src/diakonos/composables/rueckgaengigStapel.mjs') + '?mt3')
    assert.equal(ABlaufMS, toast.ANZEIGE_MS,
      'Frist der Aktion = Anzeigedauer (10 s)')
    const quelle = lies('frontend/src/diakonos/composables/useRueckgaengig.js')
    assert.match(quelle, /dauer:\s*(?:ANZEIGE_MS|toastAnzeigeMs\(\)|10000)/,
      'Rückgängig-Meldung nutzt die zentrale Anzeigedauer')
    const zuweisung = /^\s*dauer:\s*([A-Za-z_$][\w$]*)/gm
    const werte = [...quelle.matchAll(zuweisung)].map(m => m[1])
    assert.ok(werte.length > 0, 'die Meldung übergibt eine Dauer')
    assert.ok(werte.includes('ANZEIGE_MS'), 'die Meldung nutzt die zentrale Zeit')
  } finally {
    welt.zurueck()
  }
})

// ── B · Verhalten mit der Fake-Uhr ────────────────────────────────────────

test('B1 Nach 10 s ist die Meldung weg — Grund „frist“', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    let grund = null
    toast.showToast('Gespeichert', 'success', null, { beiSchliessen: (g) => { grund = g } })
    assert.equal(toast.offeneMeldungen.length, 1, 'Meldung steht')
    welt.schieben(9_900)
    assert.equal(toast.offeneMeldungen.length, 1, 'nach 9,9 s steht sie noch')
    welt.schieben(200)
    assert.equal(toast.offeneMeldungen.length, 0, 'nach 10,1 s ist sie weg')
    assert.equal(grund, 'frist')
  } finally {
    welt.zurueck()
  }
})

test('B2 Fehlermeldung blendet ebenfalls nach 10 s aus (Befund behoben)', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    let grund = null
    toast.showToast('Das Speichern hat nicht geklappt. Bitte erneut versuchen.', 'error',
      null, { beiSchliessen: (g) => { grund = g } })
    welt.schieben(9_900)
    assert.equal(toast.offeneMeldungen.length, 1)
    welt.schieben(200)
    assert.equal(toast.offeneMeldungen.length, 0, 'Fehlermeldung bleibt nicht mehr ewig stehen')
    assert.equal(grund, 'frist')
  } finally {
    welt.zurueck()
  }
})

test('B3 Hover hält die Uhr an — die Restzeit läuft danach weiter', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    toast.showToast('Gespeichert', 'success')
    const meldung = meldungIn(welt.document)
    welt.schieben(4_000)                 // 4 s gelaufen, 6 s Rest
    meldung.dispatch('mouseenter', {})
    welt.schieben(15_000)                // Zeiger bleibt 15 s liegen (unter dem Deckel)
    assert.equal(toast.offeneMeldungen.length, 1, 'solange der Zeiger steht, bleibt sie')
    welt.timer.length = 0
    meldung.dispatch('mouseleave', {})
    const rest = welt.timer.filter(t => !t.weg).map(t => t.ms)
    assert.ok(rest.includes(6_000), `Restzeit 6 s läuft weiter; gefunden: ${rest.join(', ')}`)
    welt.schieben(6_100)
    assert.equal(toast.offeneMeldungen.length, 0, 'danach ist sie weg')
  } finally {
    welt.zurueck()
  }
})

test('B4 Fokus hält die Uhr an (Tastatur) und gibt sie wieder frei', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    toast.showToast('Termin angelegt.', 'success', { text: 'Ansehen', onClick: () => {} })
    const meldung = meldungIn(welt.document)
    meldung.dispatch('focusin', {})
    welt.schieben(30_000)
    assert.equal(toast.offeneMeldungen.length, 1, 'Fokus in der Meldung: sie bleibt')
    meldung.dispatch('focusout', { relatedTarget: null })
    welt.schieben(10_100)
    assert.equal(toast.offeneMeldungen.length, 0)
  } finally {
    welt.zurueck()
  }
})

test('B5 Der Halte-Deckel hebt eine liegengebliebene Bremse auf (nie für immer)', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    toast.showToast('Gespeichert', 'success')
    const meldung = meldungIn(welt.document)
    meldung.dispatch('mouseenter', {})
    // Deckel: dauer + HALTE_ZUSATZ_MS. Er wirft die Bremse weg und gibt die
    // gedeckelte Restzeit frei — die läuft dann normal ab (max. 20 s).
    welt.schieben(10_000 + toast.HALTE_ZUSATZ_MS + 200)
    welt.schieben(toast.HALTE_ZUSATZ_MS + 200)
    assert.equal(toast.offeneMeldungen.length, 0,
      'auch ein liegengebliebener Zeiger hält die Meldung nicht unbegrenzt')
  } finally {
    welt.zurueck()
  }
})

test('B6 Schließen-Knopf bleibt und schließt sofort', async () => {
  const welt = uhrVorbereiten()
  try {
    const toast = await ladeToast()
    let grund = null
    toast.showToast('Gespeichert', 'success', null, { beiSchliessen: (g) => { grund = g } })
    const meldung = meldungIn(welt.document)
    const knopf = meldung.children.find(k => k.className === 'diakonos-toast-schliessen')
    assert.ok(knopf, 'der Schließen-Knopf ist da')
    // Review-Nacharbeit (A11y): Die Fläche steht am Ende von `<body>`; der
    // Name nennt deshalb den schnellen Weg (Esc), sonst ist das ✕ in 10 s
    // per Tab kaum erreichbar.
    assert.equal(knopf.getAttribute('aria-label'), 'Meldung schließen (Esc)')
    knopf.dispatch('click', {})
    assert.equal(toast.offeneMeldungen.length, 0)
    assert.equal(grund, 'x')
    // Die Uhr ist abgemeldet — kein spätes zweites Schließen.
    const nachher = welt.timer.filter(t => !t.weg && t.ms === 10_000).length
    assert.equal(nachher, 0, 'kein weiterer 10-s-Timer nach dem Schließen')
  } finally {
    welt.zurueck()
  }
})

// ── C · Quelle: eine Zeit, keine zweite Zahl ──────────────────────────────

test('C1 Die Anzeigedauer steht genau EINMAL im Meldungsdienst', () => {
  // Review-Nacharbeit: Die Zahl steht in `meldungszeit.mjs` (der Stapel
  // braucht sie auch; in `useToast.js` entstünde ein Import-Zyklus). Der
  // Meldungsdienst holt sie von dort und reicht sie weiter.
  const zeit = lies('frontend/src/diakonos/composables/meldungszeit.mjs')
  const toast = lies('frontend/src/diakonos/composables/useToast.js')
  assert.match(zeit, /export const ANZEIGE_MS = 10_?000/, 'eine benannte Konstante')
  assert.match(toast, /export \{ ANZEIGE_MS \}/, 'der Dienst reicht sie weiter')
  assert.match(toast, /import \{ ANZEIGE_MS \} from '\.\/meldungszeit\.mjs'/,
    'geholt, nicht abgeschrieben')
  assert.match(toast, /export const DAUER_MS = \{[^}]*normal:\s*ANZEIGE_MS/,
    'die Typ-Dauer leitet sich aus ANZEIGE_MS ab')
  // Kein `error: 0` mehr — das war der Befund „bleibt dauerhaft stehen“.
  const sonderregel = /^\s*error:\s*0\b/m
  assert.ok(!sonderregel.test(toast), 'Fehler haben keine Sonderregel „bis zum Schließen“ mehr')
  assert.match(toast, /mitAktion:\s*ANZEIGE_MS/, 'auch die Meldung mit Handlung nutzt ANZEIGE_MS')
  assert.doesNotMatch(toast, /\b4000\b/, 'die alten 4 s stehen nicht mehr im Quelltext')
  // Die Frist des Rückgängig-Stapels leitet sich aus DERSELBEN Zeit ab.
  const stapel = lies('frontend/src/diakonos/composables/rueckgaengigStapel.mjs')
  assert.match(stapel, /export const ABlaufMS = ANZEIGE_MS/,
    'Frist der Aktion = Anzeigedauer (keine zweite Zahl)')
})
