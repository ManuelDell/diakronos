/**
 * CHAT-3a-5 — Nachrichten: Handy-Aktionen und Feinschliff (Vue 3, Frontend).
 *
 * Aus dem Opus-Review von CHAT-3a-4; je Punkt ein VERHALTENSTEST am
 * gemounteten Baum (keine Quelltext-Regex als Beweis, wo sich Verhalten
 * mounten lässt):
 *
 *   A  Am HANDY stehen Antworten, Bearbeiten und Löschen in EINEM „⋯“-Menü
 *      (`DkAktionen`), das „＋“ (Reaktion) bleibt eigener Knopf. Das Menü
 *      bietet genau die ERLAUBTEN Aktionen (fremde Nachricht: Antworten;
 *      eigene: Antworten, Löschen; mit Frist: zusätzlich Bearbeiten), ruft
 *      beim Wählen das richtige Ereignis und gibt den Fokus zurück. Am
 *      DESKTOP bleibt es bei den drei Symbolknöpfen (Hover/Fokus-Zeile).
 *      Keine Überbreite: die Aktionszeile hat kein Mindestmaß, das über den
 *      Inhalt hinausgeht.
 *   B  Am Handy trägt nur das OFFENE GESPRÄCH keinen Seitenrand; die LISTE
 *      behält ihn.
 *   C  Der leere `#actions`-Slot im Seitenkopf ist WEG (sonst stand dort eine
 *      leere Aktionsleiste).
 *   D  Wer oben liest, wird NICHT nach unten gerissen: kein Sprung im Verlauf
 *      UND kein `scrollIntoView` der Seite (`nachfuehren` entfällt).
 *   E  Das Verhalten der drei Punkte zusammengefasst: `.dk-chat-beitrag:
 *      focus-within .dk-chat-aktionen` zeigt die Zeile bei Tastaturfokus, und
 *      die dvh-Regel hängt NUR an `.dk-app--handy`.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat3a5-nachrichten-handy.test.mjs
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
  'sessionStorage', 'location']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat3a5-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

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
      code = code.replace(/defineAsyncComponent\(\(\) => import\([^)]*\)\)/g,
        'defineAsyncComponent(() => Promise.resolve({ render: () => null }))')
      quanten.push(code)
    } else {
      quanten.push(readFileSync(quellDatei, 'utf8'))
    }
    const code = quanten.join('\n').replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${VUE_URL}'`
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

async function mounten(baustein, props = {}, { ereignisse = [] } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const merker = {}
  for (const name of ereignisse) merker[name] = []
  const app = Vue.createApp({
    components: { Seite: baustein },
    data: () => ({ p: props }),
    methods: Object.fromEntries(ereignisse.map((n) => [n, function (wert) { merker[n].push(wert) }])),
    template: `<Seite v-bind="p" ${ereignisse.map((n) => `@${n}="${n}"`).join(' ')} />`,
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(12)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  return { host, app, warnungen, vm, abbaum, merker }
}

/**
 * Handy-Lage: `matchMedia` beantwortet die EINE Abfrage der App
 * (`HANDY_LAGE_ABFRAGE`, GROBER Zeiger + schmal bzw. flach-quer).
 */
function handyAbfrage(handy) {
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
}

// ── Proben ─────────────────────────────────────────────────────────────────

/** Eine Nachricht, wie `_zeile` sie liefert (nur die hier zählenden Felder). */
function zeile(name, text, { am = '2026-11-18 10:00:00', eigene = false, autor = 'Anna Beispiel', ...rest } = {}) {
  return {
    name, ident: name, id: name, text, eigene, autor, erstellt_am: am, zeit: '10:00',
    bearbeitet: false, geloescht: false, geloescht_grund: null, reaktionen: [],
    antwort_auf: null, antwort_auf_text: null, gelesen_von: eigene ? 0 : null, ...rest,
  }
}

const GESPRAECHE = [{ name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null,
  titel: 'Chor', geoeffnet: true, ungelesen: 0, teilnehmer: 24,
  letzte_nachricht: 'Guten Morgen', letzte_am: '2026-11-18 10:01:00', stumm: false }]

/**
 * Die Seite mounten: Netz und Sitzung als Attrappe, Handy-Lage über
 * `matchMedia` (dieselbe Abfrage wie `useHandyLage()`).
 */
async function seiteMontieren({ handy = false, nachrichten = null, hash = '#/nachrichten/CHAT-1' } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  return globalThis.__L_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    "  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref({ name: 'M-1' }),",
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref(''),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
  ].join('\n'))

  const zeilen = nachrichten || [
    zeile('N-1', 'Guten Morgen', { am: '2026-11-18 10:00:00', autor: 'Anna Beispiel' }),
    zeile('N-2', 'Hallo Anna', { am: '2026-11-18 10:01:00', eigene: true }),
  ]
  globalThis.__L_SERVER = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'verlauf') return { gespraech: 'CHAT-1', richtung: 'neueste',
      nachrichten: zeilen.map((n) => ({ ...n })) }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash

  handyAbfrage(handy)

  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const mod = await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)
  const { host, app, warnungen, vm, abbaum } = await mounten(mod.default, {})
  await warte(10)
  void app; void vm
  return { host, warnungen, abbaum }
}

/** Die Blase direkt mounten (Handy- oder Desktop-Lage). */
async function blaseMontieren(nachricht, props = {}) {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true })).href)).default
  return mounten(mod, { nachricht, ...props }, { ereignisse: ['reaktion', 'antworten', 'bearbeiten', 'loeschen'] })
}

/** Regelblock aus einem Stil-Abschnitt (ohne Kommentare, erstes Vorkommen). */
function stilRegel(quelle, selektor) {
  const ohne = String(quelle).replace(/\/\*[\s\S]*?\*\//g, '')
  const idx = ohne.indexOf(selektor)
  assert.ok(idx >= 0, `Regel fehlt: ${selektor}`)
  const start = ohne.indexOf('{', idx)
  const ende = ohne.indexOf('}', start)
  assert.ok(start > 0 && ende > start, `Regel ohne Körper: ${selektor}`)
  return ohne.slice(start + 1, ende)
}

const STIL = (rel) => {
  const ganz = readFileSync(new URL(rel, SRC), 'utf8')
  const m = /<style[^>]*>([\s\S]*?)<\/style>/.exec(ganz)
  assert.ok(m, rel + ': kein <style>')
  return m[1]
}

// ══ A · Handy: EIN „⋯“-Menü, „＋“ bleibt eigener Knopf ═════════════════════

test('CHAT-3a-5/A: am Handy zeigt die Blase „＋“ und „⋯“ — KEINE einzelnen Aktionsknöpfe', async () => {
  // CHAT-N3: Die Lage kommt als PROP von der Seite (nicht mehr aus
  // `matchMedia` in der Blase) — hier wird sie ausdrücklich gesetzt.
  handyAbfrage(true)
  const s = await blaseMontieren(zeile('N-1', 'Guten Morgen'), { bearbeitbar: false, handyLage: true })
  await warte(6)
  const aktionen = s.host.querySelector('.dk-chat-aktionen')
  assert.ok(aktionen, 'die Aktionszeile steht im Beitrag')

  // Genau zwei Bedienelemente: „＋“ (DkButton) und der „⋯“-Auslöser.
  const knoepfe = [...aktionen.querySelectorAll('button')]
  assert.equal(knoepfe.length, 2,
    'am Handy stehen nur zwei Knöpfe: ' + knoepfe.map((k) => k.getAttribute('aria-label')).join(', '))
  const namen = knoepfe.map((k) => k.getAttribute('aria-label'))
  assert.ok(namen.includes('Reaktion setzen'), 'das „＋“ (Reaktion) ist ein eigener Knopf')
  assert.ok(namen.some((n) => /^Aktionen für die Nachricht/.test(String(n))),
    'und das „⋯“ ist da: ' + namen.join(' | '))
  // Die drei Einzelaktionen sind NICHT mehr als Knöpfe da.
  assert.ok(!namen.includes('Antworten'), 'kein einzelner Antworten-Knopf am Handy')
  assert.ok(!namen.includes('Bearbeiten'), 'kein einzelner Bearbeiten-Knopf am Handy')

  // Der „⋯“ ist der vorhandene Baustein, kein roher Knopf (UX1g2).
  const punkte = aktionen.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(punkte, 'der Auslöser kommt aus DkAktionen (.dk-ui-aktionen-ausloeser)')
  assert.equal(punkte.getAttribute('aria-haspopup'), 'menu')
  assert.equal(punkte.getAttribute('aria-expanded'), 'false', 'erst zu, kein Menü offen')
  assert.equal(aktionen.querySelector('.dk-ui-aktionen-menue'), null, 'und kein Menü im DOM')
  s.abbaum()
})

test('CHAT-3a-5/A: das Handy-Menü bietet genau die ERLAUBTEN Aktionen und führt sie aus', async () => {
  handyAbfrage(true)
  // Fremde Nachricht: nur Antworten.
  let s = await blaseMontieren(zeile('N-1', 'Guten Morgen', { eigene: false }), { bearbeitbar: false, handyLage: true })
  await warte(6)
  s.host.querySelector('.dk-ui-aktionen-ausloeser').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(6)
  let eintraege = [...document.querySelectorAll('.dk-ui-aktionen-eintrag')]
  assert.deepEqual(eintraege.map((e) => e.textContent.trim()), ['Antworten'],
    'fremde Nachricht: im Menü steht nur Antworten')
  eintraege[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(6)
  assert.equal(s.merker.antworten.length, 1, 'ein Tipp auf den Eintrag meldet `antworten`')
  assert.equal(s.merker.loeschen.length, 0)
  assert.equal(document.querySelector('.dk-ui-aktionen-menue'), null, 'das Menü schließt nach der Wahl')
  s.abbaum()

  // Eigene Nachricht mit Frist: Antworten, Bearbeiten, Löschen (Löschen
  // gefährlich und abgesetzt am Ende — Entwurf B1).
  s = await blaseMontieren(
    zeile('N-2', 'Hallo Anna', { eigene: true, bearbeitbar: true, am: new Date().toISOString() }),
    { bearbeitbar: true, handyLage: true },
  )
  await warte(6)
  s.host.querySelector('.dk-ui-aktionen-ausloeser').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(6)
  eintraege = [...document.querySelectorAll('.dk-ui-aktionen-eintrag')]
  assert.deepEqual(eintraege.map((e) => e.textContent.trim()), ['Antworten', 'Bearbeiten', 'Löschen'],
    'eigene Nachricht innerhalb der Frist: alle drei Aktionen im Menü')
  assert.equal(eintraege[2].classList.contains('is-gefahr'), true, 'Löschen ist als gefährlich markiert')
  eintraege[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(6)
  assert.equal(s.merker.bearbeiten.length, 1, 'der Eintrag Bearbeiten meldet `bearbeiten`')
  assert.equal(s.merker.bearbeiten[0].ident, 'N-2', 'mit der Nachricht der Blase')
  s.abbaum()
})

test('CHAT-3a-5/A: am Desktop bleibt es bei den Symbolknöpfen (kein Menü)', async () => {
  handyAbfrage(false)
  const s = await blaseMontieren(
    zeile('N-2', 'Hallo Anna', { eigene: true, bearbeitbar: true, am: new Date().toISOString() }),
    { bearbeitbar: true },
  )
  await warte(6)
  const aktionen = s.host.querySelector('.dk-chat-aktionen')
  const namen = [...aktionen.querySelectorAll('button')].map((k) => k.getAttribute('aria-label'))
  assert.ok(namen.includes('Reaktion setzen'), 'das „＋“ steht auch am Desktop')
  assert.ok(namen.includes('Antworten'), 'Antworten als eigener Knopf')
  assert.ok(namen.includes('Bearbeiten'), 'Bearbeiten als eigener Knopf')
  assert.ok(namen.includes('Löschen'), 'Löschen als eigener Knopf')
  assert.equal(aktionen.querySelector('.dk-ui-aktionen-ausloeser'), null,
    'am Desktop gibt es KEIN „⋯“-Menü an der Nachricht')
  // Alle Aktionen sind weiterhin Bausteine (UX1g2/F3).
  for (const k of aktionen.querySelectorAll('button')) {
    assert.equal(k.classList.contains('dk-ui-btn'), true, 'jeder Desktop-Knopf ist ein DkButton')
  }
  // Und sie melden dieselben Ereignisse wie bisher.
  const antworten = [...aktionen.querySelectorAll('button')]
    .find((k) => k.getAttribute('aria-label') === 'Antworten')
  antworten.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(4)
  assert.equal(s.merker.antworten.length, 1)
  s.abbaum()
})

test('CHAT-3a-5/A: keine Überbreite — die Aktionszeile hat kein Mindestmaß über dem Inhalt', () => {
  // Die Zeile darf ihren Inhalt nicht überragen: kein `min-width` über der
  // Inhaltsbreite, kein Umbrechen erzwingendes `flex-wrap`, und der Inhalt
  // darf schrumpfen (`min-width: 0`).
  const css = STIL('components/chat/ChatBlase.vue')
  const zeile = stilRegel(css, '\n.dk-chat-aktionen {')
  assert.match(zeile, /min-width:\s*0/, 'die Zeile darf schrumpfen')
  assert.doesNotMatch(zeile, /min-width:\s*(?!0)[1-9]/, 'kein Mindestmaß > 0')
  assert.doesNotMatch(zeile, /width:\s*(?!auto|100%)\d+px/, 'keine feste Breite')
  assert.match(zeile, /margin-left:\s*auto/, 'sie sitzt rechts am Kopf')
  // Am Handy: nur zwei Bedienelemente à 44 px — das ist der Grund für das Menü.
  const handyRegel = stilRegel(css, '.dk-app--handy .dk-chat-aktion ')
  assert.match(handyRegel, /width:\s*var\(--control-h\)/)
  assert.match(handyRegel, /height:\s*var\(--control-h\)/)
})

// ══ B · Handy: randlos nur das offene Gespräch ═════════════════════════════

test('CHAT-3a-5/B: am Handy ist nur das OFFENE GESPRÄCH randlos, die Liste behält ihren Rand', async () => {
  const css = STIL('pages/Nachrichten.vue')

  // Basis-Regel: Seitenrand bleibt.
  const basis = stilRegel(css, '\n.dk-app--handy .dk-chat {')
  assert.match(basis, /padding:\s*0 var\(--sp-4\)/, 'die Seite trägt links/rechts den Seitenrand')
  assert.match(basis, /max-width:\s*none/, 'und keine Breitenbegrenzung')
  assert.match(basis, /padding-bottom:\s*0 !important/, 'der Fußabstand gehört dem Inhaltskasten')
  assert.match(basis, /overflow:\s*hidden/, 'die Seite scrollt nicht als Ganzes')

  // Das offene Gespräch hebt den Rand auf.
  const gespraech = stilRegel(css, '.dk-app--handy .dk-chat.is-gespraech ')
  assert.match(gespraech, /padding:\s*0/, 'das offene Gespräch ist randlos')

  // Und an der gemounteten Seite: die Klasse hängt an der Lage.
  const handy = await seiteMontieren({ handy: true, hash: '#/nachrichten/CHAT-1' })
  const seite = handy.host.querySelector('.dk-chat')
  assert.equal(seite.classList.contains('is-gespraech'), true, 'offenes Gespräch trägt is-gespraech')
  handy.abbaum()

  const liste = await seiteMontieren({ handy: true, hash: '#/nachrichten' })
  const seiteListe = liste.host.querySelector('.dk-chat')
  assert.equal(seiteListe.classList.contains('is-gespraech'), false,
    'die Liste trägt is-gespraech NICHT (sie behält den Rand)')
  liste.abbaum()
})

// ══ C · Kein leerer #actions-Slot im Seitenkopf ════════════════════════════

test('CHAT-3a-5/C: der Seitenkopf bringt KEINE leere Aktionsleiste mit', async () => {
  // Am Desktop mit Gespräch steht der Seitenkopf — ohne Aktionen darf die
  // 40-px-Leiste nicht entstehen.
  const s = await seiteMontieren({ handy: false, hash: '#/nachrichten/CHAT-1' })
  const kopf = s.host.querySelector('.dk-ui-pageheader')
  assert.ok(kopf, 'der Seitenkopf steht da')
  assert.equal(kopf.querySelector('.dk-ui-pageheader-aktionen'), null,
    'keine leere Aktionsleiste im Seitenkopf')
  s.abbaum()

  // Und im Quelltext ist der leere Slot wirklich weg (nicht nur leer gerendert).
  const ganz = readFileSync(new URL('pages/Nachrichten.vue', SRC), 'utf8')
  const tpl = ganz.slice(0, ganz.indexOf('<script'))
  assert.doesNotMatch(tpl, /#actions/, 'kein #actions-Slot mehr in der Vorlage')
})

// ══ D · Kein Sprung nach unten, wenn oben gelesen wird ═════════════════════

test('CHAT-3a-5/D: wer oben liest, wird nicht nach unten gerissen (nachfuehren entfällt)', () => {
  // `nachfuehren()` zieht die SEITE per `form.scrollIntoView` nach unten. Im
  // Zweig „liest oben“ darf es nicht mehr laufen — der Verlauf bleibt stehen
  // UND die Seite springt nicht.
  const ganz = readFileSync(new URL('pages/Nachrichten.vue', SRC), 'utf8')
  const skript = ganz.slice(ganz.indexOf('<script'))
  const start = skript.indexOf('async function nachUntenScrollen')
  assert.ok(start > 0, 'die Funktion steht im Skript')
  const ende = skript.indexOf('async function nachfuehren')
  const koerper = skript.slice(start, ende)
  const zweig = /if \(!erzwingen && !istUnten\(\)\) \{([\s\S]*?)\n  \}/.exec(koerper)
  assert.ok(zweig, 'der Zweig „liest oben“ existiert')
  // Der Zweig OHNE Kommentare prüfen — der Kommentar NENNT `nachfuehren`,
  // damit niemand es wieder einbaut; er ist kein Aufruf.
  const ohneKommentar = zweig[1].replace(/\/\/.*$/gm, '')
  assert.match(ohneKommentar, /return/, 'er kehrt zurück')
  assert.doesNotMatch(zweig[1].replace(/\/\/.*$/gm, ''), /nachfuehren/, 'und ruft NICHT nachfuehren() — kein Sprung der Seite')
  assert.doesNotMatch(ohneKommentar, /scrollIntoView/, 'kein scrollIntoView der Seite im Zweig')
  assert.doesNotMatch(ohneKommentar, /nachfuehren\(/, 'und kein Nachführen — kein Sprung der Seite')
  assert.doesNotMatch(zweig[1], /scrollTop\s*=/, 'keine Scroll-Zuweisung im Zweig')
  // Der Pflichtlauf (erzwingen) führt weiterhin ans Ende und rückt nach.
  const rest = koerper.slice(koerper.indexOf(zweig[0]) + zweig[0].length)
  assert.match(rest, /scrollTop = verlaufEl\.value\.scrollHeight/, 'erzwingen springt ans Ende')
  assert.match(rest, /nachfuehren\(\)/, 'und holt die Eingabe ins Bild')
})

// ══ E · Fokusregel, dvh nur am Handy ═══════════════════════════════════════

test('CHAT-3a-5/E: Tastaturfokus zeigt die Aktionszeile (focus-within), gelesen am gerenderten Beitrag', async () => {
  handyAbfrage(false)
  const s = await blaseMontieren(zeile('N-1', 'Guten Morgen'), { bearbeitbar: false })
  await warte(6)
  const beitrag = s.host.querySelector('.dk-chat-beitrag')
  assert.ok(beitrag, 'der Beitrag steht im DOM')
  // Die Knöpfe sind fokussierbar (nicht aus der Tab-Folge genommen) …
  const knoepfe = [...beitrag.querySelectorAll('.dk-chat-aktionen button')]
  assert.ok(knoepfe.length >= 2)
  for (const k of knoepfe) {
    assert.notEqual(k.getAttribute('tabindex'), '-1', 'keiner ist aus der Tab-Folge genommen')
    assert.equal(k.hasAttribute('disabled'), false)
  }
  // … und Fokus INNERHALB des Beitrags ist die Bedingung der Sichtbarkeit.
  knoepfe[1].focus()
  await warte(4)
  assert.equal(beitrag.contains(document.activeElement), true,
    'der Fokus steht im Beitrag — :focus-within greift')
  const css = STIL('components/chat/ChatBlase.vue')
  const regel = stilRegel(css, '.dk-chat-beitrag:focus-within .dk-chat-aktionen')
  assert.match(regel, /opacity:\s*1/, 'die Regel macht die Zeile sichtbar')
  // Und ohne Fokus/Hover ist sie ruhig (Desktop).
  const basis = stilRegel(css, '\n.dk-chat-aktionen {')
  assert.match(basis, /opacity:\s*0/, 'am Desktop erst bei Hover/Fokus sichtbar')
  s.abbaum()
})

test('CHAT-3a-5/E: die dvh-Höhe hängt NUR an .dk-app--handy', () => {
  const css = readFileSync(new URL('index.css', SRC), 'utf8')
  const ohne = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const treffer = [...ohne.matchAll(/100dvh/g)]
  assert.ok(treffer.length >= 1, 'die dvh-Regel existiert')
  // Jede Fundstelle liegt in einem Block, dessen Selektor die Handy-Klasse
  // trägt: der Block beginnt bei der letzten öffnenden Klammer davor.
  for (const t of treffer) {
    const vor = ohne.slice(0, t.index)
    const blockStart = vor.lastIndexOf('{')
    const kopfStart = Math.max(vor.lastIndexOf('}'), vor.lastIndexOf('\n\n'), 0) + 1
    const kopf = vor.slice(kopfStart, blockStart)
    assert.match(kopf, /\.dk-app--handy/, 'dvh nur in einem .dk-app--handy-Block: ' + kopf.trim())
  }
  const block = stilRegel(css, '.dk-app--handy.dk-app {')
  assert.match(block, /height:\s*100vh/, 'mit Rückfall auf 100vh')
  assert.match(block, /height:\s*100dvh/, 'und dvh für den sichtbaren Ausschnitt')
})
