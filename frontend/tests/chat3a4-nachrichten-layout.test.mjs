/**
 * CHAT-3a-4 — Nachrichten: Layout (Vue 3, Frontend).
 *
 * Vier Mängel aus den Abnahme-Screenshots; je Punkt ein VERHALTENSTEST am
 * gemounteten Baum (keine Quelltext-Regex als Beweis):
 *
 *   MUSS 1  Der Verlauf ist ein EIGENER Scroll-Container; die Eingabe steht
 *           AUSSERHALB davon (Geschwister, nicht darin) und direkt im
 *           Verlaufsrahmen unter der Liste. Die Seite trägt die Klasse
 *           `dk-chat--fuellt` (der Kasten `.dk-content` wird zur Flex-Spalte,
 *           index.css) — sonst scrollte die ganze Seite und die Eingabe
 *           läge unter dem Rand.
 *   MUSS 2  Avatar links OBEN an der Blase: er steht in DERSELBEN Zeile wie
 *           die Blase, VOR dem Inhalt — nicht unter der Blase in der
 *           Aktionszeile. Folge-Zeilen desselben Autors tragen keinen Avatar.
 *   SOLL 3  Am Handy (Handy-Lage der App) gibt es NUR den Verlaufskopf
 *           (Zurück, Titel, Untertitel, Stumm als Symbolknopf mit
 *           aria-label): der Seitenkopf fehlt. Am Desktop steht er — mit dem
 *           Bereich („Nachrichten“), nicht noch einmal dem Gespräch.
 *   SOLL 4  Die Aktionen stehen kompakt in EINER Zeile (Symbolknöpfe mit
 *           aria-label) und sind per Tastatur erreichbar; „+“ steht nur, wenn
 *           noch KEINE Reaktion gesetzt ist.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat3a4-nachrichten-layout.test.mjs
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

const TMP = mkdtempSync(join(tmpdir(), 'chat3a4-'))
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

async function mounten(baustein, props = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Seite: baustein },
    data: () => ({ p: props }),
    template: '<Seite v-bind="p" />',
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(12)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  return { host, app, warnungen, vm, abbaum }
}

// ── Proben: Nachrichten und Server ─────────────────────────────────────────

/** Eine Nachricht, wie `_zeile` sie liefert (nur die hier zählenden Felder). */
function zeile(name, text, { am = '2026-11-18 10:00:00', eigene = false, autor = 'Anna Beispiel', ...rest } = {}) {
  return {
    name, text, eigene, autor, erstellt_am: am,
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

  // Handy-Lage: `matchMedia` beantwortet die EINE Abfrage der App.
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })

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

// ══ MUSS 1 · Verlauf scrollt innen, Eingabe steht fest am Fuß ══════════════

test('CHAT-3a-4/MUSS 1: Verlauf ist eigener Scroll-Container, die Eingabe steht AUSSERHALB', async () => {
  const { host, warnungen, abbaum } = await seiteMontieren()
  assert.deepEqual(warnungen.filter((w) => /error|Error/.test(String(w))), [],
    'die Seite baut ohne Fehler auf')

  const verlauf = host.querySelector('.dk-chat-nachrichten')
  const eingabe = host.querySelector('form.dk-chat-eingabe')
  assert.ok(verlauf, 'der Verlauf (.dk-chat-nachrichten) steht im DOM')
  assert.ok(eingabe, 'die Eingabe (form.dk-chat-eingabe) steht im DOM')

  // Die Eingabe ist NICHT im Scroll-Container — sonst scrollte sie mit.
  assert.equal(verlauf.contains(eingabe), false,
    'die Eingabe liegt NICHT im scrollenden Verlauf')
  // Beide sind Kinder DESSELBEN Verlaufsrahmens, die Eingabe NACH dem Verlauf.
  assert.equal(eingabe.parentElement, verlauf.parentElement,
    'Verlauf und Eingabe sind Geschwister im Verlaufsrahmen (.dk-chat-verlauf)')
  assert.equal(eingabe.parentElement.classList.contains('dk-chat-verlauf'), true)
  const kinder = [...eingabe.parentElement.children]
  assert.ok(kinder.indexOf(eingabe) > kinder.indexOf(verlauf),
    'die Eingabe steht im Fluss NACH dem Verlauf (also unten)')

  // Die Seite trägt die Marke für „füllt den Kasten“ — nur mit ihr macht
  // `.dk-content` die Seite zur Flex-Spalte (index.css), und nur dann hat der
  // Verlauf eine feste Höhe, innerhalb derer er scrollt.
  const seite = host.querySelector('.dk-chat')
  assert.ok(seite, 'die Seite trägt .dk-chat')
  assert.equal(seite.classList.contains('dk-chat--fuellt'), true,
    'die Seite trägt .dk-chat--fuellt (Kastenhöhe, innen scrollender Verlauf)')
  abbaum()
})

test('CHAT-3a-4/MUSS 1: der Kasten wird für die Chat-Seite zur Flex-Spalte (index.css)', () => {
  // Die Regel, die den Verlauf erst möglich macht: `.dk-content` ist sonst
  // `overflow-y: auto` (die GANZE Seite scrollte). Sie hängt an der Marke
  // `dk-content--fuellt`, die `App.vue` für `#/nachrichten…` setzt — geprüft
  // wird die Regel, nicht ein Kommentar. Bewusst KEIN `:has()` und KEIN
  // `.dk-content--kronos` (das trägt nur der Kalender).
  const css = readFileSync(new URL('index.css', SRC), 'utf8')
  const block = /\n\.dk-content--fuellt\s*\{([^}]*)\}/.exec(css)
  assert.ok(block, 'die Regel für .dk-content--fuellt steht in index.css')
  assert.match(block[1], /overflow:\s*hidden/, 'der Kasten scrollt nicht mehr als Ganzes')
  assert.match(block[1], /display:\s*flex/, 'er ist eine Flex-Spalte')
  assert.match(block[1], /flex-direction:\s*column/)
  assert.match(block[1], /min-height:\s*0/)
  const kind = /\n\.dk-content--fuellt\s*>\s*\.dk-chat--fuellt\s*\{([^}]*)\}/.exec(css)
  assert.ok(kind, 'die Seite füllt den Kasten')
  assert.match(kind[1], /flex:\s*1/)
  assert.match(kind[1], /min-height:\s*0/)
  const ohneKommentare = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(ohneKommentare, /\.dk-content[^{}]*:has\(/,
    'keine :has()-Kastenregel mehr (Entscheidung des Reviews)')
})

test('CHAT-3a-4/MUSS 1: App.vue setzt die Kasten-Marke genau für #/nachrichten…', () => {
  // Quelltext-Prüfung mit Absicht: die Marke hängt an der ADRESSE in App.vue
  // (wie `isVollbildMode`) — gemountet ließe sie sich nur mit dem halben
  // Router nachstellen, und genau dieser Zustand war der Fehler (die Klasse
  // `dk-content--kronos` des Kalenders griff auf #/nachrichten nie).
  const app = readFileSync(new URL('App.vue', SRC), 'utf8')
  assert.match(app, /const CHAT_PFAD = '#\/nachrichten'/,
    'der Chat-Pfad steht einmal als Konstante')
  assert.match(app, /currentHash\.value === CHAT_PFAD[\s\S]{0,120}startsWith\(`\$\{CHAT_PFAD\}\/`\)/,
    'die Marke gilt für #/nachrichten UND seine Unterpfade (z. B. /suche)')
  assert.match(app, /const istFuellModus = computed\(/,
    'sie ist eine berechnete Klasse wie isVollbildMode')
  assert.match(app, /id="dk-inhalt"[\s\S]{0,400}'dk-content--fuellt': istFuellModus/,
    'und steht an `#dk-inhalt` (.dk-content)')
})

// ══ MUSS 2 · Avatar links oben, in derselben Zeile wie die Blase ═══════════

test('CHAT-3a-4/MUSS 2: Avatar steht in DERSELBEN Zeile wie die Blase, vor dem Inhalt', async () => {
  const { host, abbaum } = await seiteMontieren()
  const beitraege = [...host.querySelectorAll('.dk-chat-beitrag')]
  assert.equal(beitraege.length, 2, 'zwei Nachrichten stehen im Verlauf')

  const fremd = beitraege[0]
  const av = fremd.querySelector(':scope > .dk-chat-av')
  const inhalt = fremd.querySelector(':scope > .dk-chat-inhalt')
  assert.ok(av, 'die fremde Nachricht trägt einen Avatar')
  assert.ok(inhalt, 'und ihren Inhalt')
  assert.equal(av.parentElement, fremd, 'der Avatar ist ein Kind der BEITRAGS-Zeile')
  assert.equal(inhalt.parentElement, fremd, 'der Inhalt ebenfalls — beide in EINER Zeile')
  // Er steht VOR dem Inhalt (Grid-Spalte 1) und trägt die Initialen.
  assert.equal(av.nextElementSibling, inhalt, 'der Avatar steht VOR dem Inhalt')
  assert.match(av.textContent.trim(), /^[A-ZÄÖÜ]{1,3}$/, 'der Avatar zeigt Initialen')
  // Er hängt NICHT in der Aktions- oder Fußzeile (dort stand er vorher).
  assert.equal(fremd.querySelector('.dk-chat-fuss .dk-chat-av'), null,
    'kein Avatar in der Fußzeile')
  assert.equal(fremd.querySelector('.dk-chat-aktionen .dk-chat-av'), null,
    'kein Avatar in der Aktionszeile')

  // Eigene Nachricht: Avatar-Spalte bleibt (die Blase springt nicht), aber
  // kein Kreis.
  const eigen = beitraege[1]
  assert.ok(eigen.classList.contains('is-ich'), 'die zweite Nachricht ist die eigene')
  const avEigen = eigen.querySelector(':scope > .dk-chat-av')
  assert.ok(avEigen, 'eigene Nachrichten tragen die (leere) Avatar-Spalte')
  assert.equal(avEigen.textContent.trim(), '', 'und keine Initialen')
  abbaum()
})

test('CHAT-3a-4/MUSS 2: Folge-Zeilen desselben Autors tragen keinen zweiten Avatar', async () => {
  // Die Regel direkt (dieselbe Funktion, die die Seite je Zeile aufruft):
  const { folgeStarten } = await import(pathToFileURL(baum('composables/nachrichtenLogik.mjs')).href)
  const zeilen = [
    { ident: 'N-1', autor: 'Beate Beispiel', eigene: false, tag: 'Gestern' },
    { ident: 'N-2', autor: 'Beate Beispiel', eigene: false, tag: null },
    { ident: 'N-3', autor: 'Carla Cramer', eigene: false, tag: null },
    { ident: 'N-4', autor: 'Carla Cramer', eigene: false, tag: null },
  ]
  assert.deepEqual(folgeStarten(zeilen), [true, false, true, false],
    'Avatar nur am Anfang einer Folge — Tages-Marke und Autorenwechsel trennen')

  // Und an der gemounteten Blase: `folgeStart=false` lässt die Zelle LEER,
  // die Spalte bleibt (kein Sprung der Blase).
  const blase = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue')).href)).default
  const nachricht = { id: 'N-2', ident: 'N-2', text: 'Zweite', eigene: false, autor: 'Beate Beispiel',
    zeit: '10:01', geloescht: false, reaktionen: [], antwort_auf: null, bearbeitet: false, gelesen_von: null }
  const zwei = await mounten(blase, { nachricht, folgeStart: false })
  const avZwei = zwei.host.querySelector('.dk-chat-beitrag > .dk-chat-av')
  assert.ok(avZwei, 'die Avatar-SPALTE steht auch in der Folge-Zeile')
  assert.equal(avZwei.textContent.trim(), '', 'sie ist aber leer (kein zweiter Kreis)')
  zwei.abbaum()

  const eins = await mounten(blase, { nachricht, folgeStart: true })
  const avEins = eins.host.querySelector('.dk-chat-beitrag > .dk-chat-av')
  assert.equal(avEins.textContent.trim(), 'BB', 'am Folgenanfang stehen die Initialen')
  eins.abbaum()
})

// ══ SOLL 3 · Handy: nur der Verlaufskopf · Desktop: Seitenkopf ohne Doppelung ══

test('CHAT-3a-4/SOLL 3: am Handy mit offenem Gespräch steht NUR der Verlaufskopf', async () => {
  const { host, abbaum } = await seiteMontieren({ handy: true })
  const seite = host.querySelector('.dk-chat')
  assert.equal(seite.classList.contains('is-handy'), true, 'die Seite kennt die Handy-Lage')

  // Kein Seitenkopf (Brotkrumen + Titel + „Stumm schalten“) …
  assert.equal(host.querySelector('.dk-ui-pageheader'), null,
    'der Seitenkopf fehlt am Handy mit offenem Gespräch')
  // … aber der EINE Verlaufskopf: Zurück, Titel, Untertitel.
  const kopf = host.querySelector('.dk-chat-verlauf-kopf')
  assert.ok(kopf, 'der Verlaufskopf steht da')
  assert.match(kopf.querySelector('.dk-chat-verlauf-titel h2')?.textContent || '', /Chor/,
    'er trägt den Titel')
  assert.match(kopf.querySelector('.dk-chat-verlauf-unter')?.textContent || '', /im Gespräch/,
    'und den Untertitel')
  assert.ok(kopf.querySelector('a.dk-chat-zurueck'), 'der Zurück-Weg ist da')
  // Stumm als SYMBOLKNOPF mit aria-label (früher Textknopf im Seitenkopf).
  const stumm = kopf.querySelector('button.dk-chat-stumm-knopf')
  assert.ok(stumm, 'der Stumm-Schalter steht im Verlaufskopf')
  assert.equal(stumm.getAttribute('aria-label'), 'Stumm',
    'der Name ist FEST („Stumm“), der Zustand steht in aria-pressed')
  assert.equal(stumm.getAttribute('aria-pressed'), 'false', 'nicht stumm geschaltet')
  assert.equal(stumm.querySelector('[aria-hidden="true"]') !== null, true,
    'das Symbol selbst ist für die Vorlesehilfe ausgeblendet')
  // Der Titel steht nur EINMAL im Kopfbereich.
  const titel = [...host.querySelectorAll('h1, h2')]
    .filter((h) => /Chor/.test(h.textContent || ''))
  assert.equal(titel.length, 1, 'der Titel steht genau einmal (nicht dreifach)')
  abbaum()
})

test('CHAT-3a-4/SOLL 3: am Desktop nennt der Seitenkopf den Bereich — kein Titel dreifach', async () => {
  const { host, abbaum } = await seiteMontieren({ handy: false })
  const seite = host.querySelector('.dk-chat')
  assert.equal(seite.classList.contains('is-handy'), false, 'Desktop-Lage')

  // Desktop MIT Gespräch: der Seitenkopf steht — er nennt den BEREICH; den
  // Gesprächstitel trägt der Verlaufskopf daneben. Vorher stand dort „Chor“
  // mit Brotkrume „Nachrichten / Chor“, und im Rahmenkopf noch einmal „Chor“.
  const kopf = host.querySelector('.dk-ui-pageheader')
  assert.ok(kopf, 'der Seitenkopf steht am Desktop mit Gespräch')
  assert.equal(kopf.querySelector('.dk-ui-pageheader-titel')?.textContent.trim(), 'Nachrichten',
    'er nennt den BEREICH („Nachrichten“), nicht noch einmal das Gespräch')
  assert.equal(kopf.querySelector('.dk-ui-brot'), null, 'keine Brotkrumen-Doppelung')
  assert.match(host.querySelector('.dk-chat-verlauf-titel h2')?.textContent || '', /Chor/,
    'der Titel des Gesprächs steht im Verlaufskopf')
  // Der Stumm-Schalter steht EINMAL — im Verlaufskopf, nicht zusätzlich im
  // Seitenkopf.
  assert.equal(kopf.querySelector('.dk-chat-stumm-knopf'), null,
    'der Seitenkopf trägt keinen zweiten Stumm-Schalter')
  abbaum()

  // Desktop in der LISTE (kein Gespräch offen): Seitenkopf „Nachrichten“.
  const liste = await seiteMontieren({ handy: false, hash: '#/nachrichten' })
  const kopfListe = liste.host.querySelector('.dk-ui-pageheader')
  assert.ok(kopfListe, 'am Desktop in der Liste steht der Seitenkopf')
  assert.equal(kopfListe.querySelector('.dk-ui-pageheader-titel')?.textContent.trim(),
    'Nachrichten')
  liste.abbaum()

  // Und am Handy in der LISTE bleibt der Seitenkopf ebenfalls — dort gibt es
  // keinen Verlaufskopf, der ihn ersetzen könnte.
  const handyListe = await seiteMontieren({ handy: true, hash: '#/nachrichten' })
  const kopfHandy = handyListe.host.querySelector('.dk-ui-pageheader')
  assert.ok(kopfHandy, 'am Handy in der Liste steht der Seitenkopf')
  assert.equal(kopfHandy.querySelector('.dk-ui-pageheader-titel')?.textContent.trim(),
    'Nachrichten')
  handyListe.abbaum()
})

// ══ SOLL 4 · Aktionen kompakt in EINER Zeile, per Tastatur erreichbar ══════

test('CHAT-3a-4/SOLL 4: Aktionen sind Symbolknöpfe mit aria-label in EINER Zeile', async () => {
  const { host, abbaum } = await seiteMontieren()
  const beitrag = host.querySelectorAll('.dk-chat-beitrag')[0]
  const aktionen = beitrag.querySelector('.dk-chat-aktionen')
  assert.ok(aktionen, 'die Aktionszeile steht im Beitrag')

  const knoepfe = [...aktionen.querySelectorAll('button')]
  assert.ok(knoepfe.length >= 2, 'mehrere Aktionen in EINER Zeile')
  for (const k of knoepfe) {
    // Kompakt: das sichtbare Zeichen ist ein Symbol, der NAME steht im
    // aria-label (die Vorlesehilfe hört „Antworten“, nicht „↩“).
    assert.ok((k.getAttribute('aria-label') || '').length > 2,
      'jeder Aktionsknopf trägt ein aria-label')
    assert.ok((k.textContent || '').trim().length <= 3,
      'und nur ein Symbol als sichtbaren Text: ' + JSON.stringify(k.textContent))
  }
  // „Antworten“ ist immer da, „Löschen“ nur an eigenen Nachrichten.
  const namen = knoepfe.map((k) => k.getAttribute('aria-label'))
  assert.ok(namen.includes('Antworten'), 'Antworten steht an JEDER Nachricht')
  assert.ok(!namen.includes('Löschen'), 'Löschen steht NICHT an fremden Nachrichten')
  const eigen = host.querySelectorAll('.dk-chat-beitrag')[1]
  const namenEigen = [...eigen.querySelectorAll('.dk-chat-aktionen button')]
    .map((k) => k.getAttribute('aria-label'))
  assert.ok(namenEigen.includes('Löschen'), 'an der eigenen Nachricht steht Löschen')

  // Die alte Dauer-Textzeile (Antworten/Löschen als sichtbarer Fließtext in der
  // Fußzeile) ist weg — die Fußzeile trägt nur noch den Lesestand.
  const fuss = beitrag.querySelector('.dk-chat-fuss')
  assert.equal(fuss, null, 'fremde Nachricht ohne Lesestand: keine Fußzeile mehr')
  abbaum()
})

test('CHAT-3a-4/SOLL 4: Aktionen sind per Tastatur erreichbar (Fokus zeigt sie)', async () => {
  const { host, abbaum } = await seiteMontieren()
  const beitrag = host.querySelectorAll('.dk-chat-beitrag')[0]
  const aktionen = beitrag.querySelector('.dk-chat-aktionen')
  // Sie stehen im DOM und sind fokussierbar — die Zeile wird nur per
  // `opacity` verborgen, nicht aus der Fokusfolge genommen.
  const knoepfe = [...aktionen.querySelectorAll('button')]
  assert.ok(knoepfe.length >= 2, 'die Aktionsknöpfe stehen im DOM')
  for (const k of knoepfe) {
    assert.equal(k.hasAttribute('disabled'), false, 'kein Knopf ist gesperrt')
    assert.notEqual(k.getAttribute('tabindex'), '-1', 'keiner ist aus der Tab-Folge genommen')
    assert.equal(k.hasAttribute('hidden'), false, 'keiner ist verborgen')
  }
  const antworten = knoepfe.find((b) => b.getAttribute('aria-label') === 'Antworten')
  assert.ok(antworten, 'der Antworten-Knopf ist da')

  // Fokus hinein: die Zeile steht dauerhaft (Regel `.dk-chat-beitrag:focus-within
  // .dk-chat-aktionen { opacity: 1 }`) — hier belegt durch `document.activeElement`
  // und die ausgelöste Aktion (ein Tipp auf „Antworten“ öffnet die Antwort-Zeile).
  antworten.dispatchEvent(new dom.window.Event('focus', { bubbles: true }))
  antworten.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(8)
  assert.ok(host.querySelector('.dk-chat-antwortzeile'),
    'ein Tipp auf „Antworten“ öffnet die Antwort-Zeile über der Eingabe')
  abbaum()
})

test('CHAT-3a-4/SOLL 4: „+“ steht nur, wenn NOCH KEINE Reaktion gesetzt ist', async () => {
  // Ohne Reaktionen: das Plus ist der erste Knopf der Aktionszeile.
  let s = await seiteMontieren()
  let beitrag = s.host.querySelectorAll('.dk-chat-beitrag')[0]
  let namen = [...beitrag.querySelectorAll('.dk-chat-aktionen button')]
    .map((k) => k.getAttribute('aria-label'))
  assert.ok(namen.includes('Reaktion setzen'), 'ohne Reaktion gibt es das Plus')
  assert.equal(beitrag.querySelector('.dk-chat-reaktionen'), null,
    'und keine leere Reaktionszeile')
  s.abbaum()

  // MIT Reaktion: das Plus steht bei den vorhandenen Reaktionen, die
  // Aktionszeile trägt es nicht noch einmal.
  s = await seiteMontieren({
    nachrichten: [
      zeile('N-1', 'Guten Morgen', { reaktionen: [{ reaktion: '👍', anzahl: 2, eigene: false }] }),
      zeile('N-2', 'Hallo', { eigene: true }),
    ],
  })
  beitrag = s.host.querySelectorAll('.dk-chat-beitrag')[0]
  namen = [...beitrag.querySelectorAll('.dk-chat-aktionen button')]
    .map((k) => k.getAttribute('aria-label'))
  assert.ok(!namen.includes('Reaktion setzen'),
    'mit vorhandener Reaktion steht das Plus NICHT in der Aktionszeile')
  const reaktionen = beitrag.querySelector('.dk-chat-reaktionen')
  assert.ok(reaktionen, 'die gesetzte Reaktion steht da')
  const plus = reaktionen.querySelector('.dk-chat-reaktion.is-plus')
  assert.ok(plus, 'und das Plus steht NEBEN der vorhandenen Reaktion')
  assert.equal(plus.getAttribute('aria-label'), 'Reaktion setzen')
  s.abbaum()
})

test('CHAT-3a-4/Review R1: die Aktionen sind BAUSTEINE (DkButton), keine rohen Knöpfe', async () => {
  // UX1g2/F3 führt den Bestand roher `<button class="eigen">` und darf nur
  // schrumpfen. Die vier Symbole und der Stumm-Schalter kommen deshalb aus
  // `DkButton` (variant="ghost", size="sm") — geprüft am gerenderten Element.
  const { host, abbaum } = await seiteMontieren()
  const aktionen = [...host.querySelectorAll('.dk-chat-aktionen button')]
  assert.ok(aktionen.length >= 2, 'die Aktionszeile ist besetzt')
  for (const k of aktionen) {
    assert.equal(k.classList.contains('dk-ui-btn'), true,
      'jede Aktion ist ein DkButton: ' + k.outerHTML.slice(0, 80))
  }
  assert.equal(host.querySelector('.dk-chat-stumm-knopf')?.classList.contains('dk-ui-btn'), true,
    'auch der Stumm-Schalter ist ein DkButton')
  abbaum()
})
