/**
 * CHAT-8-UI — Einstellungen: „Nachrichten aufbewahren“ (Aufbewahrungsfristen,
 * Chat-Konzept 4.2 / Entscheidung F8). Frontend.
 *
 * Geprüft wird VERHALTEN, nicht nur Klassen:
 *
 *   A  Die Regeln (`pages/einstellungen/fristen.mjs`, ohne DOM): Lesen der
 *      Serverantwort (gespeichert, Standard, Grenzen, feste Fristen), Prüfung
 *      der Eingabe gegen minimum…maximum, der Satz beim Verkürzen, die Sätze
 *      der festen Fristen — und KEINE erfundene Zahl, wenn der Server keine
 *      schickt.
 *   B  Fristen.vue gemountet (echte apiCall-Attrappe): Laden zeigt die Werte
 *      und den Standard, die Grenzen stehen am Feld, Speichern schickt BEIDE
 *      Felder an `chat.fristen_speichern`, die Warnung erscheint NUR beim
 *      Verkürzen (mit Rückfrage vor dem Senden), ein 403 bleibt ruhig stehen.
 *   C  Sichtbarkeit: der Abschnitt hängt in `pages/Einstellungen.vue` an
 *      `verwaltung: 'admin'`, die Adresse steht im Router und im
 *      Admin-Wächter — dieselbe Quelle wie die übrigen Admin-Unterseiten,
 *      KEINE eigene Rollenprüfung im Abschnitt.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat8-fristen-ui.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, SRC), 'utf8')

const TMP = mkdtempSync(join(tmpdir(), 'chat8-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Die Regeln direkt (kein DOM nötig) ─────────────────────────────────────
const F = await import(new URL('pages/einstellungen/fristen.mjs', SRC).href)

/** Eine Antwort, wie `chat.fristen_lesen` sie liefert. */
function antwort(überschreiben = {}) {
  return {
    chat_frist_gruppe_monate: 24,
    chat_frist_direkt_monate: 12,
    standard: { gruppe: 24, direkt: 12 },
    minimum: 1,
    maximum: 120,
    nachricht_monate: 6,
    umfrage_stimmen_monate: 6,
    meldung_monate: 12,
    ...überschreiben,
  }
}

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

const VUE_SCHIM = join(TMP, 'vue-schim.mjs')
writeFileSync(VUE_SCHIM, [
  `export * from '${VUE_URL}'`,
  'export function nextTick(fn) {',
  '  const p = globalThis.__NAECHSTER_TAKT()',
  '  return fn ? p.then(fn) : p',
  '}',
].join('\n'))

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function baum(seite, { frisch = false, ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const zielFuer = (quellDatei) => {
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '../').length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    const quellDatei = aufgeloest(abs)
    const quanten = []
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
      quanten.push(code)
    } else {
      quanten.push(readFileSync(quellDatei, 'utf8'))
    }
    const code = quanten.join('\n').replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${quellDatei.endsWith('.vue') ? VUE_SCHIM : VUE_URL}'`
        if (spec.startsWith('.')) {
          const zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        return `from '${spec}'`
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(abs, ziel)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

const tickWarteschlange = []
globalThis.__NAECHSTER_TAKT = () => new Promise((loese) => { tickWarteschlange.push(loese) })
async function rendern(n = 6) {
  for (let i = 0; i < n; i += 1) {
    const offen = tickWarteschlange.splice(0, tickWarteschlange.length)
    if (!offen.length) { await tick(); continue }
    for (const loese of offen) loese()
    await tick()
  }
}

function mounten(baustein) {
  return import('vue').then(async (Vue) => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const warnungen = []
    const app = Vue.createApp({ render: () => Vue.h(baustein) })
    app.config.warnHandler = (m) => warnungen.push(m)
    app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
    app.mount(host)
    await warte(10)
    return {
      host, app, warnungen,
      abbaum: () => {
        try { app.unmount() } catch { /* egal */ }
        try { host.remove() } catch { /* egal */ }
      },
    }
  })
}

/** Ein Klick, wie ihn der Browser auslöst (Knöpfe sind echte <button>). */
function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/** Ein Feld füllen, wie der Browser es tut (`v-model` hört auf `input`). */
async function fuellen(el, wert) {
  assert.ok(el, 'das Feld steht im DOM')
  el.value = wert
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(2)
}

/**
 * Speichern anklicken und warten, bis die Rückfrage des Hauses steht.
 *
 * WARUM NICHT `await rendern(n)`: `rendern` gibt jedem offenen `nextTick`
 * einen echten Takt — sind gerade keine offen, wartet es nur einen Tick. Die
 * Rückfrage entsteht aber erst, nachdem die Prüfung gelaufen ist; deshalb
 * wird hier auf die BEDINGUNG gewartet (mit Zeitgrenze), nicht auf Takte.
 */
async function speichernUndWarten(host, test) {
  klick(knopf(host, /^Speichern$/))
  for (let i = 0; i < 60; i += 1) {
    if (test()) return true
    await warte(2)
    await rendern(2)
  }
  return test()
}

const texte = (host, auswahl) => [...host.querySelectorAll(auswahl)].map((e) => e.textContent.trim())

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-8-UI/A: die Serverantwort wird vollständig gelesen', () => {
  const stand = F.standLesen(antwort())
  assert.deepEqual(stand.gespeichert, { gruppe: 24, direkt: 12 })
  assert.deepEqual(stand.standard, { gruppe: 24, direkt: 12 })
  assert.equal(stand.minimum, 1)
  assert.equal(stand.maximum, 120)
  assert.deepEqual(stand.fest, { nachricht: 6, umfrage: 6, meldung: 12 })
  // Die Felder sind mit den GESPEICHERTEN Werten vorbelegt (nicht mit dem Standard).
  assert.deepEqual(F.feldTexte(stand), { gruppe: '24', direkt: '12' })
  assert.equal(F.standardHinweis(stand, 'gruppe'), 'Standard: 24 Monate')
  assert.equal(F.standardHinweis(stand, 'direkt'), 'Standard: 12 Monate')
})

test('CHAT-8-UI/A: fehlende Angaben werden NICHT durch geratene Zahlen ersetzt', () => {
  const stand = F.standLesen({ chat_frist_gruppe_monate: 18 })
  assert.equal(stand.gespeichert.gruppe, 18)
  assert.equal(stand.gespeichert.direkt, null, 'ohne Wert kein Wert')
  assert.deepEqual(F.feldTexte(stand), { gruppe: '18', direkt: '' })
  assert.equal(F.standardHinweis(stand, 'direkt'), '', 'ohne Standard kein Standard-Hinweis')
  // Feste Fristen: nur die Sätze, deren Zahl der Server schickt.
  const saetze = F.festeFristen(F.standLesen({ nachricht_monate: 6 }))
  assert.equal(saetze.length, 1)
  assert.match(saetze[0].text, /nach 6 Monaten/)
  assert.deepEqual(F.festeFristen(F.standLesen({})), [], 'ohne Felder keine Behauptung')
})

test('CHAT-8-UI/A: die festen Fristen kommen aus den Feldern der Antwort', () => {
  const saetze = F.festeFristen(F.standLesen(antwort({ nachricht_monate: 9, umfrage_stimmen_monate: 3, meldung_monate: 24 })))
  assert.deepEqual(saetze.map((s) => s.id), ['nachricht', 'umfrage', 'meldung'])
  assert.equal(saetze[0].text, 'Gelöschte Nachrichten werden nach 9 Monaten endgültig entfernt.')
  assert.match(saetze[1].text, /nach 3 Monaten/)
  assert.match(saetze[2].text, /nach 24 Monaten/)
  // Einzahl wird richtig gebeugt (1 Monat, nicht „1 Monate“).
  assert.equal(F.monateText(1), '1 Monat')
  assert.equal(F.monateText(24), '24 Monate')
})

test('CHAT-8-UI/A: Eingabe wird an minimum…maximum geprüft (wie der Server)', () => {
  const stand = F.standLesen(antwort({ minimum: 3, maximum: 60 }))
  assert.equal(F.eingabePruefen({ gruppe: '24', direkt: '12' }, stand).ok, true)
  const zuKlein = F.eingabePruefen({ gruppe: '2', direkt: '12' }, stand)
  assert.equal(zuKlein.ok, false)
  assert.match(zuKlein.fehler.gruppe, /zwischen 3 und 60/)
  assert.equal(zuKlein.fehler.direkt, undefined, 'das andere Feld bleibt sauber')
  assert.match(F.eingabePruefen({ gruppe: '61', direkt: '12' }, stand).fehler.gruppe, /zwischen 3 und 60/)
  // Leer und Bruchzahlen sind keine Monate.
  assert.match(F.eingabePruefen({ gruppe: '', direkt: '12' }, stand).fehler.gruppe, /ganze Zahl/)
  assert.match(F.eingabePruefen({ gruppe: '1.5', direkt: '12' }, stand).fehler.gruppe, /ganze Zahl/)
  // Leerzeichen sind LEER, nicht 0: `Number(' ')` wäre 0 und damit ein gültiger
  // Wert — die Meldung muss die richtige sein (nicht „zwischen 3 und 60“).
  assert.match(F.eingabePruefen({ gruppe: ' ', direkt: '12' }, stand).fehler.gruppe, /ganze Zahl/)
  assert.equal(F.eingabePruefen({ gruppe: '  12  ', direkt: '12' }, stand).ok, true, 'Leerraum um die Zahl stört nicht')
  // Grenzen selbst sind erlaubt.
  assert.equal(F.eingabePruefen({ gruppe: '3', direkt: '60' }, stand).ok, true)
})

test('CHAT-8-UI/A: die Warnung gilt NUR beim Verkürzen', () => {
  const stand = F.standLesen(antwort())
  // Gleich groß: keine Warnung (nichts wird gelöscht).
  assert.deepEqual(F.verkuerzt({ gruppe: '24', direkt: '12' }, stand), [])
  assert.equal(F.verkuerzenFrage({ gruppe: '24', direkt: '12' }, stand), '')
  // Verlängern: keine Warnung.
  assert.deepEqual(F.verkuerzt({ gruppe: '36', direkt: '24' }, stand), [])
  assert.equal(F.verkuerzenFrage({ gruppe: '36', direkt: '24' }, stand), '')
  // EIN Wert kleiner: Warnung mit dem festen Satz und beiden Zahlen.
  assert.deepEqual(F.verkuerzt({ gruppe: '24', direkt: '6' }, stand), ['direkt'])
  const frage = F.verkuerzenFrage({ gruppe: '24', direkt: '6' }, stand)
  assert.match(frage, /Direktnachrichten und Runden: 12 Monate → 6 Monate/)
  assert.match(frage, /Ältere Nachrichten werden beim nächsten nächtlichen Lauf endgültig gelöscht\./)
  assert.doesNotMatch(frage, /Gruppengespräche/, 'das unveränderte Feld steht nicht im Satz')
  // Beide kleiner: beide im Satz.
  const beide = F.verkuerzenFrage({ gruppe: '6', direkt: '6' }, stand)
  assert.match(beide, /Gruppengespräche: 24 Monate → 6 Monate/)
  assert.match(beide, /Direktnachrichten und Runden: 12 Monate → 6 Monate/)
  // Unbekannter alter Wert: kein Anlass für eine Warnung.
  assert.deepEqual(F.verkuerzt({ gruppe: '1', direkt: '1' }, F.standLesen({ chat_frist_gruppe_monate: null, chat_frist_direkt_monate: null })), [])
})

test('CHAT-8-UI/A: Nutzlast trägt BEIDE Felder als ganze Zahlen; „geändert“ erkennt den Unterschied', () => {
  assert.deepEqual(F.speicherNutzlast({ gruppe: '30', direkt: '18' }), {
    chat_frist_gruppe_monate: 30,
    chat_frist_direkt_monate: 18,
  })
  const stand = F.standLesen(antwort())
  assert.equal(F.geaendert({ gruppe: '24', direkt: '12' }, stand), false)
  assert.equal(F.geaendert({ gruppe: '24', direkt: '18' }, stand), true)
  assert.deepEqual(F.standardTexte(stand), { gruppe: '24', direkt: '12' })
})

// ════════════════════════════════════════════════════════════════════════════
// B · Fristen.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

/**
 * Die Seite mit einer echten apiCall-Attrappe. `server` liefert je Endpunkt
 * (`fristen_lesen`, `fristen_speichern`) die Antwort; ein Fehler wird geworfen
 * und mit `status` versehen (so wie `useApi` es tut).
 */
async function seiteMontieren({ server = {} } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__FRISTEN_PUSH({ methode, parameter })',
    '  return globalThis.__FRISTEN_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
  ].join('\n'))
  // Die Rückfrage mitschneiden — UND wie der echte Dialog beantworten
  // (`bestaetigungAntwort`), damit der Ablauf im Stack zu Ende läuft.
  const bst = join(ordner, 'bestaetigen.mjs')
  writeFileSync(bst, [
    `import { bestaetigen as echt, bestaetigungAntwort } from `
      + `'${pathToFileURL(join(SRC.pathname, 'composables/useBestaetigen.js')).href}'`,
    'export { bestaetigungAntwort }',
    'export async function bestaetigen(frage) {',
    '  globalThis.__FRISTEN_FRAGE = frage',
    '  return echt(frage)',
    '}',
  ].join('\n'))
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useBestaetigen.js'), pathToFileURL(bst).href)

  const aufrufe = []
  globalThis.__FRISTEN_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__FRISTEN_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'fristen_lesen') return antwort()
    if (kurz === 'fristen_speichern') {
      return { ...antwort(parameter), gespeichert: true }
    }
    // CHAT-12c: der Abschnitt „Nachrichten aufbewahren“ trägt seit dieser
    // Karte AUCH die Höchstgröße je Anhang (`chat.chat_einstellungen_lesen`).
    // Sie ist nicht Thema dieses Tests; die Attrappe liefert den Standard, so
    // wie es der echte Server tut.
    if (kurz === 'chat_einstellungen_lesen') {
      return { anhang_max_mb: 10, standard: 10, minimum: 1, maximum: 50 }
    }
    if (kurz === 'chat_einstellungen_speichern') {
      return { anhang_max_mb: parameter?.anhang_max_mb, gespeichert: true,
        standard: 10, minimum: 1, maximum: 50 }
    }
    return {}
  }

  const mod = (await import(pathToFileURL(baum('pages/einstellungen/Fristen.vue', { frisch: true, ordner })).href)).default
  const s = await mounten(mod)
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...s, aufrufe }
}

const feld = (host, id) => host.querySelector(`#cfg-${id}`)
/**
 * Ein Feld über SEIN LABEL finden — so, wie ein Screenreader die Verbindung
 * liest: `label[for]` → Element mit dieser Kennung. Findet das Label kein
 * Ziel, sucht `querySelector('#…')` nichts: der Test fällt dann durch.
 */
function feldUeberLabel(host, beschriftung) {
  const label = [...host.querySelectorAll('label')]
    .find((l) => l.textContent.trim() === beschriftung)
  if (!label) return null
  const ziel = label.getAttribute('for')
  return ziel ? host.querySelector(`#${ziel}`) : null
}

const knopf = (host, muster) => [...host.querySelectorAll('button')].find((b) => muster.test(b.textContent))

test('CHAT-8-UI/B: Laden zeigt die gespeicherten Werte, den Standard und die festen Fristen', async () => {
  const s = await seiteMontieren()
  assert.match(s.host.textContent, /Nachrichten aufbewahren/, 'die Überschrift der Karte steht da')
  // Die Felder werden über ihre Beschriftung gefunden: das Label zeigt per
  // `for` auf das Eingabeelement (eine Kennung, nicht zwei Wahrheiten).
  const gruppe = feldUeberLabel(s.host, 'Gruppengespräche')
  const direkt = feldUeberLabel(s.host, 'Direktnachrichten und Runden')
  assert.ok(gruppe && direkt, 'beide Zahlenfelder stehen und sind mit ihrem Label verbunden')
  assert.equal(gruppe.type, 'number')
  assert.equal(gruppe.value, '24', 'gespeicherter Wert, nicht der Standard')
  assert.equal(direkt.value, '12')
  // Genau EIN Feld mit dieser Beschriftung (keine zweite Kennung daneben).
  // CHAT-12c: DAS DRITTE Zahlenfeld ist die „Höchstgröße je Anhang“ — sie
  // steht im selben Abschnitt (eigene Karte, eigene Tests in
  // `chat12c-anhang-groesse.test.mjs`).
  assert.equal(s.host.querySelectorAll('input[type="number"]').length, 3)
  assert.ok(feldUeberLabel(s.host, 'Höchstgröße je Anhang'), 'das Größenfeld der Anhänge steht daneben')
  // Der Standard steht als Hinweis unter dem Feld (aus der Antwort).
  assert.match(s.host.textContent, /Standard: 24 Monate/)
  assert.match(s.host.textContent, /Standard: 12 Monate/)
  // Die festen Fristen stehen lesend darunter.
  assert.match(s.host.textContent, /Gelöschte Nachrichten werden nach 6 Monaten endgültig entfernt\./)
  assert.match(s.host.textContent, /geschlossenen Umfrage/)
  assert.match(s.host.textContent, /Erledigte Meldungen werden nach 12 Monaten entfernt\./)
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
})

test('CHAT-8-UI/B: Hilfe und Fehler hängen am Feld (aria-describedby, aria-invalid)', async () => {
  const s = await seiteMontieren({ server: { fristen_lesen: () => antwort({ minimum: 6, maximum: 60 }) } })
  const gruppe = feldUeberLabel(s.host, 'Gruppengespräche')
  // Ohne Meldung beschreibt der Standard-Hinweis das Feld — und die Kennung
  // steht wirklich an dem Absatz, auf den sie zeigt.
  const hilfeId = gruppe.getAttribute('aria-describedby')
  assert.ok(hilfeId, 'das Feld nennt eine Beschreibung')
  const hilfe = s.host.querySelector(`#${hilfeId}`)
  assert.ok(hilfe, 'die genannte Beschreibung steht im DOM')
  assert.match(hilfe.textContent, /Standard: 24 Monate/)
  assert.equal(gruppe.getAttribute('aria-invalid'), null, 'ohne Fehler kein aria-invalid')

  // Mit einem ungültigen Wert: die MELDUNG wird zur Beschreibung, das Feld ist
  // als ungültig gezeichnet.
  await fuellen(gruppe, '2')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  const meldungId = gruppe.getAttribute('aria-describedby')
  const meldung = s.host.querySelector(`#${meldungId}`)
  assert.ok(meldung, 'die genannte Meldung steht im DOM')
  assert.match(meldung.textContent, /zwischen 6 und 60/)
  assert.equal(gruppe.getAttribute('aria-invalid'), 'true', 'das Feld weiß, dass es nicht stimmt')
  s.abbaum()
})

test('CHAT-8-UI/B: die Grenzen minimum…maximum stehen im Hinweis und am Feld', async () => {
  const s = await seiteMontieren({
    server: { fristen_lesen: () => antwort({ minimum: 3, maximum: 48 }) },
  })
  assert.match(s.host.textContent, /Erlaubt sind 3 bis 48 Monate/)
  const ids = [...s.host.querySelectorAll('.dk-ui-field')].map((e) => e.id)
  // CHAT-12c: das dritte Feld (Anhangsgröße) trägt `dk-sprung-anhang`.
  assert.deepEqual(ids, ['dk-sprung-gruppe', 'dk-sprung-direkt', 'dk-sprung-anhang'],
    'Felder tragen die Sprungmarken der Suche')
  const direkt = feldUeberLabel(s.host, 'Direktnachrichten und Runden')
  assert.equal(direkt.getAttribute('max'), '48')
  assert.equal(feldUeberLabel(s.host, 'Gruppengespräche').getAttribute('min'), '3')
  s.abbaum()
})

test('CHAT-8-UI/B: Speichern schickt BEIDE Felder an chat.fristen_speichern', async () => {
  const s = await seiteMontieren()
  await fuellen(feldUeberLabel(s.host, 'Gruppengespräche'), '30')
  await fuellen(feldUeberLabel(s.host, 'Direktnachrichten und Runden'), '18')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  const ruf = s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'chat.fristen_speichern wurde gerufen')
  assert.equal(ruf.methode, 'diakronos_app.api.chat.fristen_speichern')
  assert.deepEqual(ruf.parameter, {
    chat_frist_gruppe_monate: 30,
    chat_frist_direkt_monate: 18,
  })
  await rendern(6)
  assert.match(s.host.textContent, /Gespeichert/, 'die Rückmeldung steht da')
  // Nach dem Speichern wird NICHT neu geladen (kein Skelett über dem Formular):
  // der Stand kommt aus der Antwort des Speicherns.
  assert.equal(s.aufrufe.filter((a) => /fristen_lesen$/.test(a.methode)).length, 1,
    'genau EIN Ladevorgang — der beim Öffnen')
  assert.equal(feldUeberLabel(s.host, 'Gruppengespräche').value, '30', 'die Felder zeigen den neuen Stand')
  // Die Erklärung des Abschnitts trägt einen Namen (aria-labelledby → die
  // Überschrift, deren Kennung wirklich im DOM steht).
  const region = s.host.querySelector('[role="region"]')
  assert.ok(region, 'der Abschnitt ist eine benannte Region')
  const titelId = region.getAttribute('aria-labelledby')
  assert.ok(titelId, 'die Region nennt ihren Namen')
  assert.equal(s.host.querySelector(`#${titelId}`).textContent.trim(), 'Nachrichten aufbewahren')
  s.abbaum()
})

test('CHAT-8-UI/B: ein ungültiger Wert geht NICHT hinaus und wird am Feld gesagt', async () => {
  const s = await seiteMontieren({ server: { fristen_lesen: () => antwort({ minimum: 6, maximum: 60 }) } })
  await fuellen(feldUeberLabel(s.host, 'Gruppengespräche'), '2')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  assert.equal(s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).length, 0,
    'kein Aufruf mit einem Wert außerhalb des Bereichs')
  assert.match(s.host.textContent, /zwischen 6 und 60/, 'der Satz steht am Feld')
  s.abbaum()
})

test('CHAT-8-UI/B: die Warnung erscheint NUR beim Verkürzen — und fragt vor dem Speichern', async () => {
  const s = await seiteMontieren()
  // Verlängern: keine Warnung.
  await fuellen(feldUeberLabel(s.host, 'Direktnachrichten und Runden'), '24')
  await rendern(4)
  assert.doesNotMatch(s.host.textContent, /nächtlichen Lauf/, 'beim Verlängern keine Warnung')
  // Verkürzen: die Warnung steht da.
  await fuellen(feldUeberLabel(s.host, 'Direktnachrichten und Runden'), '6')
  await rendern(4)
  assert.match(s.host.textContent,
    /Ältere Nachrichten werden beim nächsten nächtlichen Lauf endgültig gelöscht\./,
    'die Klartext-Warnung beim Verkürzen')

  const gespeichert = () => s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).length
  // Die BESTÄTIGUNG vor dem Speichern ist der EINE Bestätigungs-Dialog des
  // Hauses (`useBestaetigen`, wie in Website.vue/GruppeDetail.vue); das
  // Formular selbst zeigt den Warnsatz nur. Der Auftrag trägt danach beide
  // WERTE — und zwar genau einer (kein Doppel, kein Verlust des Feldes).
  await speichernUndWarten(s.host, () => Boolean(globalThis.__FRISTEN_FRAGE))
  const frage = globalThis.__FRISTEN_FRAGE
  assert.ok(frage, 'vor dem Speichern wird gefragt')
  assert.equal(frage.titel, 'Fristen verkürzen?')
  assert.match(frage.text, /Direktnachrichten und Runden: 12 Monate → 6 Monate/)
  assert.match(frage.text,
    /Ältere Nachrichten werden beim nächsten nächtlichen Lauf endgültig gelöscht\./)
  assert.equal(frage.gefahr, true, 'die Rückfrage ist als gefährlich gezeichnet')
  assert.equal(gespeichert(), 0, 'ohne Antwort geht nichts hinaus')

  // Abbrechen: kein Auftrag, das Formular bleibt stehen.
  const { bestaetigung, bestaetigungAntwort } = await import(
    new URL('composables/useBestaetigen.js', SRC).href)
  assert.ok(bestaetigung.value, 'die Rückfrage steht im Dialog des Hauses')
  bestaetigungAntwort(false)
  await warte(10)
  await rendern(6)
  assert.equal(gespeichert(), 0, 'nach dem Abbrechen kein Auftrag')

  // Noch einmal speichern und zustimmen: jetzt geht genau EIN Auftrag hinaus.
  globalThis.__FRISTEN_FRAGE = null
  await speichernUndWarten(s.host, () => Boolean(globalThis.__FRISTEN_FRAGE))
  bestaetigungAntwort(true)
  for (let i = 0; i < 40 && gespeichert() === 0; i += 1) { await warte(2); await rendern(2) }
  await warte(14)
  await rendern(6)
  const ruf = s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode))
  assert.equal(ruf.length, 1, 'genau EIN Auftrag — kein Doppel beim zweiten Blick')
  assert.deepEqual(ruf[0].parameter, { chat_frist_gruppe_monate: 24, chat_frist_direkt_monate: 6 })
  s.abbaum()
})

test('CHAT-8-UI/B: beim Verlängern wird OHNE Rückfrage gespeichert', async () => {
  const s = await seiteMontieren()
  await fuellen(feldUeberLabel(s.host, 'Gruppengespräche'), '36')
  await rendern(4)
  const { bestaetigung } = await import(new URL('composables/useBestaetigen.js', SRC).href)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  assert.equal(bestaetigung.value, null, 'keine Rückfrage beim Verlängern')
  assert.equal(s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).length, 1)
  s.abbaum()
})

test('CHAT-8-UI/B: ein 403 bleibt ruhig an der Seite', async () => {
  const s = await seiteMontieren({
    server: {
      fristen_speichern: () => {
        const fehler = new Error('Kein Zugriff')
        fehler.status = 403
        throw fehler
      },
    },
  })
  await fuellen(feldUeberLabel(s.host, 'Direktnachrichten und Runden'), '18')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  await rendern(4)
  const meldung = [...s.host.querySelectorAll('[role="alert"]')]
    .find((e) => /Administration/.test(e.textContent))
  assert.ok(meldung, 'die Ablehnung steht als Hinweis da')
  assert.equal(meldung.getAttribute('role'), 'alert', 'sie wird vorgelesen')
  assert.match(meldung.textContent, /Nur die Administration darf die Aufbewahrungsfristen ändern\./)
  // Kein Absturz, keine leere Fläche: die Felder stehen weiter da.
  assert.ok(feldUeberLabel(s.host, 'Direktnachrichten und Runden'), 'das Formular bleibt')
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
})

test('CHAT-8-UI/B: „Auf Standard zurücksetzen“ füllt die Standardwerte — gespeichert wird danach', async () => {
  // Gespeichert 48, Standard 24: der Knopf ist bedienbar und füllt 24 ein.
  const s = await seiteMontieren({
    server: { fristen_lesen: () => antwort({ chat_frist_gruppe_monate: 48 }) },
  })
  assert.equal(feldUeberLabel(s.host, 'Gruppengespräche').value, '48', 'die Felder zeigen den gespeicherten Wert')
  const zurueck = knopf(s.host, /Auf Standard zurücksetzen/)
  assert.ok(zurueck)
  assert.equal(zurueck.disabled, false, 'mit einer Abweichung vom Standard ist der Knopf bedienbar')
  klick(zurueck)
  await warte(4)
  await rendern(6)
  assert.equal(feldUeberLabel(s.host, 'Gruppengespräche').value, '24', 'der Standardwert steht im Feld')
  // Verkürzen von 48 auf 24 — die Rückfrage kommt, dann wird der Standard gesendet.
  // 48 → 24 ist ein Verkürzen: der Warnsatz steht VOR dem Speichern da.
  const gespeichert = () => s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).length
  assert.match(s.host.textContent,
    /Ältere Nachrichten werden beim nächsten nächtlichen Lauf endgültig gelöscht\./,
    'das Zurücksetzen unter den gespeicherten Wert warnt')
  await speichernUndWarten(s.host, () => Boolean(globalThis.__FRISTEN_FRAGE))
  assert.ok(globalThis.__FRISTEN_FRAGE, 'auch das Zurücksetzen fragt nach')
  const { bestaetigungAntwort } = await import(
    new URL('composables/useBestaetigen.js', SRC).href)
  bestaetigungAntwort(true)
  for (let i = 0; i < 40 && gespeichert() === 0; i += 1) { await warte(2); await rendern(2) }
  await warte(14)
  await rendern(8)
  const ruf = s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'der Standardwert wird gespeichert')
  assert.deepEqual(ruf.parameter, { chat_frist_gruppe_monate: 24, chat_frist_direkt_monate: 12 })
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Sichtbarkeit — dieselbe Quelle wie die übrigen Admin-Unterseiten
// ════════════════════════════════════════════════════════════════════════════

/** Die `verwaltung`-Stufe je Abschnitts-Kennung aus `pages/Einstellungen.vue`. */
function einstellungsAbschnitte() {
  const quelle = lies('pages/Einstellungen.vue')
  const liste = quelle.slice(quelle.indexOf('const abschnitte = ['))
  const ergebnis = {}
  for (const m of liste.matchAll(/id: '([^']+)'[\s\S]{0,400}?verwaltung: '([^']+)'/g)) {
    ergebnis[m[1]] = m[2]
  }
  return ergebnis
}

test('CHAT-8-UI/C: der Abschnitt steht in den Einstellungen — Stufe „admin“, Adresse, Gruppe Datenschutz', () => {
  const abschnitte = einstellungsAbschnitte()
  assert.equal(abschnitte.fristen, 'admin',
    'die Fristen ändert nur die Administration (Server: chat.fristen_speichern, 403 sonst)')
  const quelle = lies('pages/Einstellungen.vue')
  assert.match(quelle, /id: 'fristen', label: 'Nachrichten aufbewahren'/)
  assert.match(quelle, /href: '#\/einstellungen\/fristen'/)
  assert.match(quelle, /gruppe: 'datenschutz'/, 'bei den Fristen der übrigen Daten (Papierkorb, Datensicherung)')
})

test('CHAT-8-UI/C: Adresse und Admin-Wächter stehen im Router', () => {
  const router = lies('router.js')
  assert.match(router, /EinstellungenFristen: \(\) => import\('\.\/pages\/Einstellungen\.vue'\)/)
  assert.match(router, /'#\/einstellungen\/fristen': 'EinstellungenFristen'/)
  const waechter = router.slice(router.indexOf('const ADMIN_ONLY_PAGES = new Set(['))
  assert.match(waechter.slice(0, waechter.indexOf('])')), /'EinstellungenFristen'/,
    'die Seite hängt an derselben Liste wie Papierkorb und Datenschutz-Texte')
  assert.match(lies('menue.js'), /'EinstellungenFristen'/,
    'die Seitenleiste markiert „Einstellungen“ auch auf dieser Seite')
})

test('CHAT-8-UI/C: KEINE eigene Rollenprüfung im Abschnitt (der Server entscheidet)', () => {
  const seite = lies('pages/einstellungen/Fristen.vue')
  assert.doesNotMatch(seite, /isAdmin|istMitgliederverwaltung|useSession\(\)|__DIakonosBOOT/,
    'der Abschnitt liest keine Rollen — die Sichtbarkeit regelt der Rahmen')
  // Ein 403 wird ruhig erklärt, nicht als Panne behandelt.
  assert.match(seite, /status === 403/)
})

test('CHAT-8-UI/C: Suche findet den Bereich und seine zwei Felder', async () => {
  const S = await import(new URL('pages/einstellungen/suche.mjs', SRC).href)
  assert.ok(S.STICHWORTE.fristen.includes('Nachrichten aufbewahren'))
  // CHAT-12c: das dritte Feld „Höchstgröße je Anhang“ steht im selben
  // Abschnitt (eigene Karte).
  assert.deepEqual(S.FELDER.fristen.map((f) => f.id), ['gruppe', 'direkt', 'anhang'])
  const treffer = S.trefferBereiche([
    { id: 'fristen', label: 'Nachrichten aufbewahren', gruppe: 'datenschutz' },
  ], 'aufbewahrung')
  assert.equal(treffer.has('fristen'), true, '„Aufbewahrung“ findet den Bereich')
  assert.equal(S.trefferFelder('fristen', 'Gruppengespräche').length, 1, 'der Feldname findet das Feld')
})
