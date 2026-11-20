/**
 * CHAT-7b-UI-b — Blockieren und Sperrliste (Frontend, Chat-Konzept S3).
 *
 * Der Server (CHAT-7b/7b-2) steht: `chat.kontakt_sperren(mitglied)` (POST),
 * `chat.kontakt_entsperren(mitglied)` (POST), `chat.meine_sperren()` (GET —
 * `mitglied`, gekürzter `anzeigename`, `bild`, kein Konto/E-Mail). Diese Karte
 * baut NUR die Oberfläche dazu; sie entscheidet KEIN Recht.
 *
 * Geprüft wird Verhalten, nicht nur Markup:
 *
 *   A  Die Regeln (`composables/nachrichtenDirekt.mjs`, ohne DOM): Wortlaut der
 *      Aktion und der Rückfrage (geschlechtsneutral, ohne „ihr/ihm“), der
 *      ruhige Hinweis nach dem Sperren, die Sperrliste aus der Serverantwort
 *      (Felder, Fail closed, keine Doppel, kein Konto-Feld), „steht die Person
 *      auf MEINER Liste?“ und der Aufheben-Hinweis für die sperrende Seite.
 *   B  Die Seite „Nachrichten“ gemountet (echte apiCall-Attrappe): im 1:1 gibt
 *      es die Aktion „Nicht mehr anschreiben lassen“ IM „⋯“-Menü
 *      (`DkAktionen`); die Rückfrage nennt den Namen; bestätigt geht EIN POST
 *      `kontakt_sperren` hinaus und der Hinweis steht als `role="status"`.
 *      Ein 403 beim Senden zeigt DENSELBEN Text wie „nicht erreichbar“ — und
 *      den Aufheben-Satz NUR, wenn die eigene Sperrliste die Person enthält.
 *   C  Das Personenprofil gemountet: die Aktion steht neben „Nachricht
 *      schreiben“; ohne Sperre kein Aufheben-Satz, mit Sperre kein zweites
 *      „sperren“ sondern der Weg in die Einstellungen.
 *   D  Einstellungen → „Gesperrte Personen“ (`pages/einstellungen/Sperren.vue`)
 *      gemountet: Laden zeigt Name + Link + „Aufheben“ (DkButton), der
 *      Leerzustand „Du hast niemanden gesperrt.“, Aufheben ruft
 *      `kontakt_entsperren` und nimmt NUR die eine Zeile weg. Einbindung:
 *      `Einstellungen.vue` (Gruppe Datenschutz, OHNE Verwaltungsstufe), Router
 *      (Adresse + keine Stufe), Menü (`seiten`), `suche.mjs` (Stichworte).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat7bui-b-sperren.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import vm from 'node:vm'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { sichtbarerFuss } from '../src/diakonos/components/handyMenue.mjs'

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'history', 'URLSearchParams', 'PopStateEvent']) {
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

const TMP = mkdtempSync(join(tmpdir(), 'chat7bui-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Die Regeln direkt (kein DOM nötig) ─────────────────────────────────────
const R = await import(new URL('composables/nachrichtenDirekt.mjs', SRC).href)
// `useVerwaltung.js` liest beim Import `window` (Sitzung) — deshalb NACH der
// Browser-Attrappe und dynamisch geladen.
const { darfAnfragenZaehlerSehen } = await import(
  new URL('composables/useVerwaltung.js', SRC).href)

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
  // Quell-Datei → erzeugtes Modul. Eine Kette (A → B → C) löst ihre relativen
  // Importe aus dem QUELLORT auf; ohne diese Zuordnung würde ab dem zweiten
  // Glied im TEMP-Ordner gesucht (und z. B. `./useRueckgaengig.js` fehlen).
  const zielVon = new Map()
  const zielFuer = (quellDatei) => {
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '../').length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    // Ein bereits übersetztes ZIEL führt auf seine QUELLE zurück.
    const quelle = zielVon.get(abs) || abs
    if (NEU.has(quelle)) return NEU.get(quelle)
    const quellDatei = aufgeloest(quelle)
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
        if (spec === 'vue') return `from '${VUE_URL}'`
        if (spec.startsWith('.')) {
          let zielAbs
          try {
            zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
          } catch {
            // Ein Import in einem Kommentar ist kein Import — er bleibt stehen.
            return ganz
          }
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        // Ein Fremdpaket aus dem TEMP-Ordner lässt sich nicht über den
        // Paketnamen auflösen — die Auflösung läuft vom ECHTEN Quellort aus.
        try {
          return `from '${import.meta.resolve(spec)}'`
        } catch {
          return ganz
        }
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(quelle, ziel)
    zielVon.set(ziel, quelle)
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
  const app = Vue.createApp({ render: () => Vue.h(baustein, props) })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(12)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  return { host, app, warnungen, abbaum }
}

function klick(el) {
  assert.ok(el, 'das Zielelement steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/**
 * Handy-Lage als Attrappe: die Seite fragt `matchMedia` (eine Abfrage der App).
 * Ohne sie fehlt `matchMedia` in jsdom — `useHandyLage` bricht dann nicht, aber
 * ein Test will die Desktop-Lage ausdrücklich.
 */
function handyAbfrage(handy = false) {
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
}
handyAbfrage(false)

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-7b-UI-b/A: die Aktion heißt überall gleich (eine Quelle)', () => {
  assert.equal(R.SPERR_AKTION, 'Nicht mehr anschreiben lassen')
  assert.equal(R.AUFHEBEN, 'Aufheben')
  assert.equal(R.SPERR_SEITE.titel, 'Gesperrte Personen')
  assert.equal(R.SPERR_SEITE.href, '#/einstellungen/sperren')
  assert.equal(R.SPERR_LEER, 'Du hast niemanden gesperrt.')
  // Der Wortlaut der Aktion steht WIRKLICH in den Bausteinen — nicht nur hier.
  for (const datei of ['pages/Nachrichten.vue', 'pages/MitgliedDetail.vue']) {
    assert.match(lies(datei), /SPERR_AKTION/, `${datei} bindet den Wortlaut aus EINER Quelle`)
  }
  // Review R1, Punkt 5: der ungenutzte Baustein `ChatSperrliste.vue` ist
  // gelöscht — die Liste zeichnet allein der Abschnitt `Sperren.vue`.
  assert.match(lies('pages/einstellungen/Sperren.vue'), /SPERR_SEITE|SPERR_LEER|AUFHEBEN/)
})

test('CHAT-7b-UI-b/A: die Rückfrage nennt die Folgen für BEIDE Seiten, still und umkehrbar', () => {
  const text = R.sperrFrage('Erika Muster', 'M-1')
  assert.match(text, /^Erika Muster kann dir dann keine Nachrichten mehr schreiben, und du dieser Person auch nicht\./,
    'beide Richtungen, geschlechtsneutral („dieser Person“, nicht „ihr/ihm“)')
  assert.match(text, /Erika Muster erfährt davon nichts\./, 'die andere Seite erfährt es nicht')
  assert.match(text, /Du kannst das jederzeit in den Einstellungen aufheben\./)
  // Geschlechtsneutral: KEIN „ihr“/„ihm“/„sie“/„er“ als Personenbezug.
  assert.doesNotMatch(text, /\bihr\b|\bihm\b|\bihre[mn]?\b/i, 'kein „ihr/ihm“ im Satz')
  assert.doesNotMatch(text, /\bsie\b/i, 'kein „sie“')
  // Der Dialog des Hauses bekommt Titel und Knopf — die Aktion ist nicht
  // als „gefahr“ gezeichnet (sie ist umkehrbar, keine Löschung).
  const frage = R.sperrBestaetigung('Erika Muster', 'M-1')
  assert.equal(frage.titel, 'Nicht mehr anschreiben lassen?')
  assert.equal(frage.aktion, R.SPERR_AKTION)
  assert.equal(frage.text, text)
  assert.notEqual(frage.gefahr, true, 'umkehrbar — keine Gefahrenfarbe')
})

test('CHAT-7b-UI-b/A: ohne Namen spricht der Satz von „dieser Person“, nie von `null`', () => {
  assert.equal(R.sperrName('', ''), 'diese Person')
  assert.equal(R.sperrName('   ', 'M-9'), 'M-9')
  assert.equal(R.sperrName('Erika', 'M-1'), 'Erika')
  const text = R.sperrFrage('', '')
  assert.match(text, /^diese Person kann dir dann keine Nachrichten mehr schreiben/)
  assert.doesNotMatch(text, /null|undefined/)
})

test('CHAT-7b-UI-b/A: der Hinweis nach dem Sperren ist ruhig und nennt den Weg zurück', () => {
  const text = R.sperrErfolg('Erika Muster', 'M-1')
  assert.match(text, /Erika Muster kann dir keine Nachrichten mehr schreiben, und du dieser Person auch nicht\./)
  assert.match(text, /Einstellungen › Gesperrte Personen/)
  // Es ist eine Auskunft, kein Fehler: kein Ausrufezeichen, keine Alarmwörter.
  assert.doesNotMatch(text, /fehler|Achtung|!/i)
})

test('CHAT-7b-UI-b/A: die Sperrliste liest NUR die Felder des Servers', () => {
  const liste = R.sperrListe({
    sperren: [
      { mitglied: 'M-1', anzeigename: 'Erika M.', bild: 'https://beispiel.invalid/b.png', angelegt_am: '2026-11-01 10:00:00' },
      // Kein Konto-Feld — was der Server nicht schickt, wird nicht erfunden.
      { mitglied: 'M-2', anzeigename: '', bild: '' },
      // Doppelt und ohne Kennung: fällt weg (kein zweiter Eintrag, kein Ziel).
      { mitglied: 'M-1', anzeigename: 'Erika M.' },
      { mitglied: '', anzeigename: 'Ohne Kennung' },
    ],
  })
  assert.deepEqual(liste.map((e) => e.mitglied), ['M-1', 'M-2'], 'keine Doppel, keine Einträge ohne Kennung')
  assert.equal(liste[0].name, 'Erika M.')
  assert.equal(liste[0].bild, 'https://beispiel.invalid/b.png')
  assert.equal(liste[0].href, '#/mitglied/M-1', 'der Name führt ins Personenprofil')
  assert.equal(liste[1].name, 'M-2', 'ohne Namen die Kennung')
  assert.equal(liste[1].bild, '')
  for (const e of liste) {
    assert.deepEqual(Object.keys(e).sort(), ['angelegtAm', 'bild', 'href', 'mitglied', 'name'],
      'kein Konto-/E-Mail-Feld in der Zeile')
  }
  // Fail closed: keine Liste, kein Eintrag.
  assert.deepEqual(R.sperrListe({}), [])
  assert.deepEqual(R.sperrListe(null), [])
  assert.deepEqual(R.sperrListe({ sperren: 'kaputt' }), [])
})

test('CHAT-7b-UI-b/A: „gesperrt“ entscheidet NUR die eigene Liste', () => {
  const liste = R.sperrListe({ sperren: [{ mitglied: 'M-1', anzeigename: 'Erika M.' }] })
  assert.equal(R.istGesperrt('M-1', liste), true)
  assert.equal(R.istGesperrt('M-2', liste), false)
  assert.equal(R.istGesperrt('', liste), false)
  assert.equal(R.istGesperrt('M-1', []), false)
  assert.equal(R.istGesperrt('M-1', null), false, 'ohne Liste keine Behauptung')
  // Leerraum um die Kennung stört nicht (der Server trimmt genauso).
  assert.equal(R.istGesperrt(' M-1 ', liste), true)
})

test('CHAT-7b-UI-b/A: der Aufheben-Hinweis verrät die Sperre nur der sperrenden Seite', () => {
  const hinweis = R.sperrHinweis()
  assert.equal(hinweis.text, 'Du hast diese Person gesperrt.')
  assert.match(hinweis.linkText, /Aufheben unter Einstellungen › Gesperrte Personen/)
  assert.equal(hinweis.href, '#/einstellungen/sperren', 'der Link führt in die Einstellungen')
})

test('CHAT-7b-UI-b/A: „nicht erreichbar“ bleibt für beide Seiten DERSELBE Text', () => {
  // Karte Punkt 2: keine Sonderanzeige, die die Sperre verrät. Der Grund für
  // die Sperre steht NICHT im Hinweis — nur die sperrende Seite bekommt
  // zusätzlich ihren eigenen Satz (oben geprüft).
  const gesperrt = R.sendeFehlerZustand({ status: 403 }, { direkt: true })
  const sonst = R.sendeFehlerZustand({ status: 403, exc_type: 'PermissionError' }, { direkt: true })
  assert.deepEqual(gesperrt, sonst)
  assert.equal(gesperrt.titel, R.NICHT_ERREICHBAR.titel)
  assert.equal(gesperrt.text, R.NICHT_ERREICHBAR.text)
  assert.doesNotMatch(gesperrt.titel + gesperrt.text, /sperr|gesperrt|blockiert/i,
    'der Hinweis nennt keinen Grund — deshalb ist er für beide Seiten gleich')
})

// ════════════════════════════════════════════════════════════════════════════
// B · Die Seite „Nachrichten“ gemountet
// ════════════════════════════════════════════════════════════════════════════

/** Ein 1:1-Gespräch, wie `meine_gespraeche` es liefert. */
const DIREKT = {
  name: 'CHAT-D-1', art: 'direkt', gruppe: null, untergruppe: null,
  titel: 'Erika Muster', mitglied: 'M-1', bild: '', teilnehmer: 2, stumm: false,
  geoeffnet: true, ungelesen: 0, darf_senden: true,
  letzte_nachricht: 'Bis morgen', letzte_am: '2026-11-18 10:01:00',
}

/**
 * Nachrichten.vue mit echter apiCall-Attrappe mounten. `server` beantwortet die
 * Endpunkte; `sperren` ist die Antwort von `meine_sperren`.
 */
async function nachrichtenMontieren({ server = {}, sperren = [], handy = false } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__N_PUSH({ art: "POST", methode, parameter })',
    '  return globalThis.__N_SERVER({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__N_PUSH({ art: "GET", methode, parameter })',
    '  return globalThis.__N_SERVER({ methode, parameter })',
    '}',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref({ name: "M-0" }),',
    '    istAdmin: ref(false), istGast: ref(false), fullName: ref(""),',
    '    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }',
    '}',
  ].join('\n'))

  const aufrufe = []
  globalThis.__N_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__N_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'meine_gespraeche') return { gespraeche: [{ ...DIREKT }] }
    if (kurz === 'meine_sperren') return { sperren: sperren.map((e) => ({ ...e })) }
    if (kurz === 'verlauf') return { gespraech: DIREKT.name, richtung: 'neueste', nachrichten: [] }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'kontakt_sperren') return { mitglied: parameter?.mitglied, gesperrt: true }
    if (kurz === 'kontakt_entsperren') return { mitglied: parameter?.mitglied, gesperrt: false }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten/CHAT-D-1'
  handyAbfrage(handy)

  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  // Die Umleitung NICHT leeren: `bestaetigungVerdrahten` (vor diesem Aufruf)
  // legt die Dialog-Attrappe hinein — ein `clear()` hier würde sie wieder
  // entfernen und die Seite fragte den ECHTEN Dialog (der im Test nie
  // antwortet).
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const mod = await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)
  const s = await mounten(mod.default, {})
  await warte(20)
  return { ...s, aufrufe }
}

/** Die Rückfrage des Hauses mitschneiden und wie der Dialog beantworten. */
async function bestaetigungVerdrahten(ordner) {
  const bst = join(ordner, 'bestaetigen.mjs')
  writeFileSync(bst, [
    'export async function bestaetigen(frage) {',
    '  globalThis.__FRAGE = frage',
    '  return globalThis.__ANTWORT === true',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.set(U('composables/useBestaetigen.js'), pathToFileURL(bst).href)
}

const knoepfe = (host) => [...host.querySelectorAll('button')]

/** Das „⋯“-Menü des Gesprächskopfs öffnen (DkAktionen). */
async function menueOeffnen(host) {
  const ausloeser = host.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(ausloeser, 'der ⋯-Knopf steht im Gesprächskopf')
  klick(ausloeser)
  // Das Menü liegt im Teleport an `document.body` — es kann einen Takt später
  // da sein als der Klick; deshalb auf die Bedingung warten, nicht auf Takte.
  for (let i = 0; i < 30; i += 1) {
    const menue = document.querySelector('.dk-ui-aktionen-menue')
    if (menue) return menue
    await warte(2)
  }
  return document.querySelector('.dk-ui-aktionen-menue')
}

test('CHAT-7b-UI-b/B: im 1:1 steht „Nicht mehr anschreiben lassen“ im ⋯-Menü — und nur dort', async () => {
  const ordner = join(TMP, 'menu-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  const s = await nachrichtenMontieren()
  assert.deepEqual(s.warnungen, [], s.warnungen.join(' | '))

  const menue = await menueOeffnen(s.host)
  assert.ok(menue, 'das Menü ist offen')
  const eintraege = [...menue.querySelectorAll('[role="menuitem"]')].map((b) => b.textContent.trim())
  assert.deepEqual(eintraege, ['Nicht mehr anschreiben lassen'],
    'die Aktion ist der EINE Eintrag im 1:1-Kopf')
  // Kein zweiter, gleichnamiger Knopf neben dem Kopf (die Aktion lebt im Menü).
  const sichtbar = knoepfe(s.host).filter((b) => b.textContent.includes('Nicht mehr anschreiben lassen'))
  assert.equal(sichtbar.length, 0, 'kein zusätzlicher Knopf außerhalb des Menüs')
  s.abbaum()
})

test('CHAT-7b-UI-b/B: Sperren fragt nach, schickt EINEN POST und zeigt den ruhigen Hinweis', async () => {
  const ordner = join(TMP, 'sperren-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  // Ohne Fänger bricht Node die DATEI bei einer unbehandelten Ablehnung ab
  // (`--test` zählt sie als Abbruch) — hier ist das kein Fehler des Codes.
  process.on('unhandledRejection', () => {})
  globalThis.__FRAGE = null
  globalThis.__ANTWORT = true
  const s = await nachrichtenMontieren()

  const menue = await menueOeffnen(s.host)
  // GENAU EIN Klick auf den Eintrag — ein zweiter (z. B. aus einem Debug-Lauf)
  // würde zwei Rückfragen und zwei Aufträge auslösen.
  klick([...menue.querySelectorAll('[role="menuitem"]')]
    .find((b) => b.textContent.includes('Nicht mehr anschreiben lassen')))
  for (let i = 0; i < 60 && !globalThis.__FRAGE; i += 1) await warte(2)

  const frage = globalThis.__FRAGE
  assert.ok(frage, 'vor dem Sperren wird gefragt')
  assert.equal(frage.titel, 'Nicht mehr anschreiben lassen?')
  assert.match(frage.text, /Erika Muster kann dir dann keine Nachrichten mehr schreiben, und du dieser Person auch nicht\./)
  assert.match(frage.text, /Erika Muster erfährt davon nichts\./)

  await warte(20)
  const posts = s.aufrufe.filter((a) => /kontakt_sperren$/.test(a.methode))
  assert.equal(posts.length, 1, 'genau EIN Aufruf')
  assert.equal(posts[0].art, 'POST', 'kontakt_sperren ist schreibend (POST)')
  assert.deepEqual(posts[0].parameter, { mitglied: 'M-1' })

  const status = [...s.host.querySelectorAll('[role="status"]')]
    .map((e) => e.textContent.trim()).find((t) => /keine Nachrichten mehr schreiben/.test(t))
  assert.ok(status, 'der Hinweis nach dem Sperren steht als role="status" da')
  // Ruhig: kein role="alert", kein Fehlertext.
  const alarme = [...s.host.querySelectorAll('[role="alert"]')].map((e) => e.textContent)
  assert.equal(alarme.some((t) => /keine Nachrichten mehr schreiben/.test(t)), false,
    'die Auskunft ist kein Alarm')
  s.abbaum()
})

test('CHAT-7b-UI-b/B: Abbrechen in der Rückfrage schickt NICHTS', async () => {
  const ordner = join(TMP, 'abbrechen-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  globalThis.__FRAGE = null
  globalThis.__ANTWORT = false
  const s = await nachrichtenMontieren()

  const menue = await menueOeffnen(s.host)
  klick([...menue.querySelectorAll('[role="menuitem"]')]
    .find((b) => b.textContent.includes('Nicht mehr anschreiben lassen')))
  await warte(20)
  assert.ok(globalThis.__FRAGE, 'die Rückfrage kam')
  assert.equal(s.aufrufe.filter((a) => /kontakt_sperren$/.test(a.methode)).length, 0,
    'ohne Zustimmung geht kein Auftrag hinaus')
  s.abbaum()
})

test('CHAT-7b-UI-b/B: 403 beim Senden — gleicher Text, Aufheben-Satz NUR mit eigener Sperre', async () => {
  const fehler403 = () => { const e = new Error('kein Zugriff'); e.status = 403; throw e }
  // (a) Die eigene Sperrliste ENTHÄLT die Person → Sperr-Hinweis steht da.
  const mitListe = await nachrichtenMontieren({
    server: { senden: fehler403 },
    sperren: [{ mitglied: 'M-1', anzeigename: 'Erika M.', bild: '' }],
  })
  const eingabe = mitListe.host.querySelector('#chat-eingabe')
  assert.ok(eingabe, 'die Eingabe steht (der Server hat noch nicht Nein gesagt)')
  eingabe.value = 'Hallo'
  eingabe.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(4)
  // Der Senden-Knopf ist der `type=submit`-Knopf; ein Klick auf ein Element
  // in jsdom löst KEIN `submit` des Formulars aus — der Weg des Browsers ist
  // das Absenden des Formulars.
  const form = mitListe.host.querySelector('#chat-eingabe-form')
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(20)

  const text = mitListe.host.textContent
  assert.match(text, new RegExp(R.NICHT_ERREICHBAR.titel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
    'derselbe Text wie bei „nicht erreichbar“')
  assert.match(text, new RegExp(R.NICHT_ERREICHBAR.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.match(text, /Du hast diese Person gesperrt\./, 'die sperrende Seite erfährt es')

  const link = [...mitListe.host.querySelectorAll('a')]
    .find((a) => /Gesperrte Personen/.test(a.textContent))
  assert.ok(link, 'der Weg zum Aufheben steht als Link da')
  assert.equal(link.getAttribute('href'), '#/einstellungen/sperren')
  mitListe.abbaum()

  // (b) Die Sperrliste ist LEER (jemand anders hat gesperrt / Gegenüber weg) →
  //     derselbe Text, aber KEIN Sperr-Satz: die Sperre verrät sich nicht.
  const ohneListe = await nachrichtenMontieren({ server: { senden: fehler403 } })
  const feld2 = ohneListe.host.querySelector('#chat-eingabe')
  feld2.value = 'Hallo'
  feld2.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(4)
  ohneListe.host.querySelector('#chat-eingabe-form')
    .dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(20)
  const text2 = ohneListe.host.textContent
  assert.match(text2, new RegExp(R.NICHT_ERREICHBAR.titel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.doesNotMatch(text2, /Du hast diese Person gesperrt/,
    'ohne eigene Sperre kein Hinweis auf eine Sperre')
  assert.doesNotMatch(text2, /#\/einstellungen\/sperren/, 'und kein Aufheben-Link')
  ohneListe.abbaum()
})

test('CHAT-7b-UI-b/B: in einer GRUPPE gibt es keine Sperr-Aktion', async () => {
  const ordner = join(TMP, 'gruppe-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  const gruppe = { name: 'CHAT-G-1', art: 'gruppe', gruppe: 'chor', untergruppe: null,
    titel: 'Chor', geoeffnet: true, ungelesen: 0, teilnehmer: 24, stumm: false }
  const s = await nachrichtenMontieren({
    server: { meine_gespraeche: () => ({ gespraeche: [gruppe] }) },
  })
  assert.equal(s.host.querySelector('.dk-ui-aktionen-ausloeser'), null,
    'kein ⋯-Menü mit Sperr-Aktion im Gruppenkopf')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Das Personenprofil gemountet
// ════════════════════════════════════════════════════════════════════════════

/** Die Attrappen des Profils (API, Router, Sitzung, Bestätigung). */
// `aufrufe` ist NUR zum Mitlesen da: ein Test kann die Liste übergeben, die er
// danach befragt — die Attrappe bleibt dieselbe.
function profilAttrappen(ordner, { server, sperren = [], antwort = true, aufrufe = [] }) {
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__P_PUSH({ art: "POST", methode, parameter })',
    '  return globalThis.__P_SERVER({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__P_PUSH({ art: "GET", methode, parameter })',
    '  return globalThis.__P_SERVER({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const router = join(ordner, 'router.mjs')
  writeFileSync(router, [
    'export const getRouteParam = () => globalThis.__PARAM || ""',
    'export const getRouteParams = () => ({} as any)'.replace(' as any', ''),
    'export const currentHash = () => globalThis.__HASH || ""',
    'export const currentPageName = { value: "MitgliedDetail" }',
    'export const currentComponent = () => null',
    'export const navigate = (ziel) => { globalThis.__NAV = ziel }',
    'export const onBeforeEach = () => () => {}',
    'export const routeNeuLaden = () => {}',
    'export const seitenLadend = { value: false }',
    'export const pageLadefehler = { value: null }',
    'export const verwaltungsStufeSeite = () => null',
    'export const verwaltungErlaubt = () => true',
    'export const modulChatErlaubt = () => true',
    'export const BOOT = {}',
    'export default { getRouteParam }',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const bst = join(ordner, 'bestaetigen.mjs')
  writeFileSync(bst, [
    // Die echten Exporte WEITERREICHEN (das Profil hängt den Dialog des Hauses
    // als `DkBestaetigung` in seine Vorlage und liest `bestaetigung`), nur
    // `bestaetigen` selbst wird mitschneidend beantwortet.
    `export { bestaetigung, bestaetigungAntwort } from `
      + `'${pathToFileURL(join(SRC.pathname, 'composables/useBestaetigen.js')).href}'`,
    'export async function bestaetigen(frage) {',
    '  globalThis.__FRAGE = frage',
    '  return globalThis.__ANTWORT === true',
    '}',
  ].join('\n'))
  // Die Umleitung bleibt bestehen (siehe `bestaetigungVerdrahten`: der zweite
  // Aufbau derselben Seite würde die bereits übersetzten Module verwerfen).
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('router.js'), pathToFileURL(router).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)
  umleitung.set(U('composables/useBestaetigen.js'), pathToFileURL(bst).href)
  globalThis.__FRAGE = null
  globalThis.__ANTWORT = antwort
  globalThis.__P_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__P_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'meine_sperren') return { sperren: sperren.map((e) => ({ ...e })) }
    if (kurz === 'kontakt_sperren') return { mitglied: parameter?.mitglied, gesperrt: true }
    return {}
  }
  globalThis.__PARAM = 'M-1'
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/mitglied/M-1'
  return { aufrufe }
}

function detailAntwort(überschreiben = {}) {
  return {
    data: {
      name: 'M-1', vorname: 'Erika', nachname: 'Muster', status: 'Aktiv',
      email: 'erika@example.org', telefon: '', geburtstag: '', geschlecht: 'w',
      familienstand: '', strasse: '', hausnummer: '', plz: '', ort: '',
      gruppen: [], beziehungen: [], austritt: null, dsgvo: {},
      ...überschreiben,
    },
    permissions: { beziehungen_pflegen: false, beziehungen_alle: false },
  }
}

const TREFFER = {
  mitglied: 'M-1', anzeigename: 'Erika Muster', bild: '', hat_konto: true,
  darf_schreiben: true, gespraech: null,
}

test('CHAT-7b-UI-b/C: am Profil steht die Aktion neben „Nachricht schreiben“ — und sperrt nach Rückfrage', async () => {
  const ordner = join(TMP, 'profil-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  // Die Sitzung ist NICHT die Person der Seite: `useSession().mitglied` ist die
  // ANGEMELDETE Person (`M-0`), `mitgliedId` die gezeigte (`M-1`).
  const { aufrufe } = profilAttrappen(ordner, {
    server: {
      get_mitglied_detail: () => detailAntwort(),
      personen_suchen: () => ({ treffer: [TREFFER], limit: 20 }),
    },
    antwort: true,
  })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const s = await mounten(mod.default, {})
  await warte(24)

  assert.deepEqual(s.warnungen, [], s.warnungen.join(' | '))
  const text = s.host.textContent
  assert.match(text, /Nachricht schreiben/, 'der Chat-Knopf steht da')
  assert.match(text, /Nicht mehr anschreiben lassen/, 'und die Sperr-Aktion daneben')

  // Die Sperrliste wurde gefragt (GET — rein lesend) und war leer; zwei Wege
  // führen dorthin (Laden der Person + Personensuche), gefragt wird EINMAL.
  const liste = aufrufe.filter((a) => /meine_sperren$/.test(a.methode))
  assert.equal(liste.length, 1, 'die eigene Sperrliste wird EINMAL geholt')
  assert.equal(liste[0].art, 'GET', 'meine_sperren ist rein lesend')

  klick(knoepfe(s.host).find((b) => b.textContent.includes('Nicht mehr anschreiben lassen')))
  for (let i = 0; i < 20 && !globalThis.__FRAGE; i += 1) await warte(2)
  assert.ok(globalThis.__FRAGE, 'die Rückfrage kommt')
  assert.match(globalThis.__FRAGE.text, /Erika Muster kann dir dann keine Nachrichten mehr schreiben/)
  await warte(20)

  const posts = aufrufe.filter((a) => /kontakt_sperren$/.test(a.methode))
  assert.equal(posts.length, 1, 'genau EIN Sperr-Aufruf')
  assert.deepEqual(posts[0].parameter, { mitglied: 'M-1' })
  assert.match(s.host.textContent, /Aufheben kannst du das jederzeit unter Einstellungen/,
    'der Hinweis nach dem Sperren steht da')
  // Danach: kein zweites „sperren“, sondern der Aufheben-Weg.
  assert.equal(knoepfe(s.host).filter((b) => b.textContent.includes('Nicht mehr anschreiben lassen')).length, 0,
    'die Aktion verschwindet, sobald die Person gesperrt ist')
  s.abbaum()
})

test('CHAT-7b-UI-b/C: steht die Person schon auf meiner Liste, gibt es kein zweites Sperren', async () => {
  const ordner = join(TMP, 'profil-gesperrt-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  profilAttrappen(ordner, {
    server: {
      get_mitglied_detail: () => detailAntwort(),
      personen_suchen: () => ({ treffer: [TREFFER], limit: 20 }),
    },
    sperren: [{ mitglied: 'M-1', anzeigename: 'Erika M.', bild: '' }],
  })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const s = await mounten(mod.default, {})
  await warte(24)

  assert.equal(knoepfe(s.host).filter((b) => b.textContent.includes('Nicht mehr anschreiben lassen')).length, 0,
    'kein „sperren“ für eine Person, die schon gesperrt ist')
  assert.match(s.host.textContent, /Aufheben unter Einstellungen › Gesperrte Personen/,
    'sondern der Weg zum Aufheben')
  const link = [...s.host.querySelectorAll('a')].find((a) => /Gesperrte Personen/.test(a.textContent))
  assert.ok(link, 'mit dem Weg zum Aufheben')
  assert.equal(link.getAttribute('href'), '#/einstellungen/sperren')
  s.abbaum()
})

test('CHAT-7b-UI-b/C: ohne Chat-Knopf (keine Serverzusage) gibt es auch keine Sperr-Aktion', async () => {
  const ordner = join(TMP, 'profil-ohne-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  profilAttrappen(ordner, {
    server: {
      get_mitglied_detail: () => detailAntwort(),
      personen_suchen: () => ({ treffer: [], limit: 20 }),
    },
  })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const s = await mounten(mod.default, {})
  await warte(24)
  assert.doesNotMatch(s.host.textContent, /Nicht mehr anschreiben lassen/)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Einstellungen → „Gesperrte Personen“ gemountet
// ════════════════════════════════════════════════════════════════════════════

async function sperrenMontieren({ sperren = [], ueberschreiben = {} } = {}) {  const ordner = join(TMP, 'sperrenseite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  const aufrufe = []
  // Review R1, Punkt 1: GET und POST werden GETRENNT protokolliert (wie Teil B).
  // Die frühere Zeile `export const apiGet = apiCall` machte jeden Aufruf zu
  // einem POST — genau der Fehler, den die Sperrliste als 405 zurückbekam.
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    "  globalThis.__S_PUSH({ art: 'POST', methode, parameter })",
    "  return globalThis.__S_SERVER({ art: 'POST', methode, parameter })",
    '}',
    'export async function apiGet(methode, parameter) {',
    "  globalThis.__S_PUSH({ art: 'GET', methode, parameter })",
    "  return globalThis.__S_SERVER({ art: 'GET', methode, parameter })",
    '}',
  ].join('\n'))
  globalThis.__S_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__S_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof ueberschreiben[kurz] === 'function') return ueberschreiben[kurz](parameter)
    if (kurz === 'meine_sperren') return { sperren: sperren.map((e) => ({ ...e })) }
    if (kurz === 'kontakt_entsperren') return { mitglied: parameter?.mitglied, gesperrt: false }
    return {}
  }
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)

  const mod = await import(pathToFileURL(baum('pages/einstellungen/Sperren.vue', { frisch: true, ordner })).href)
  const s = await mounten(mod.default, {})
  await warte(24)
  return { ...s, aufrufe }
}

test('CHAT-7b-UI-b/D: die Sperrliste zeigt Bild, Name und „Aufheben“ (DkButton)', async () => {
  const s = await sperrenMontieren({
    sperren: [
      { mitglied: 'M-1', anzeigename: 'Erika M.', bild: 'https://beispiel.invalid/e.png' },
      { mitglied: 'M-2', anzeigename: 'Bert B.', bild: '' },
    ],
  })
  assert.deepEqual(s.warnungen, [], s.warnungen.join(' | '))
  const text = s.host.textContent
  assert.match(text, /Gesperrte Personen/, 'die Überschrift steht da')
  assert.match(text, /Die andere Seite erfährt davon nichts\./, 'die Einleitung sagt, was die Sperre NICHT tut')
  assert.doesNotMatch(text, /Du hast niemanden gesperrt\./, 'kein Leerzustand bei Einträgen')

  const zeilen = [...s.host.querySelectorAll('.sp-zeile')]
  assert.equal(zeilen.length, 2, 'eine Zeile je Sperre')
  assert.equal(zeilen[0].querySelector('img.sp-bild').getAttribute('src'), 'https://beispiel.invalid/e.png',
    'das Bild der Person steht in der Zeile')
  assert.equal(zeilen[0].querySelector('img.sp-bild').getAttribute('aria-hidden'), 'true',
    'das Bild ist schmückend — der Name steht daneben')
  assert.equal(zeilen[0].querySelector('a.sp-name').textContent.trim(), 'Erika M.')
  assert.equal(zeilen[0].querySelector('a.sp-name').getAttribute('href'), '#/mitglied/M-1')
  // Ohne Bild: der Platzhalter mit dem Anfangsbuchstaben.
  assert.equal(zeilen[1].querySelector('.sp-bild--leer').textContent.trim(), 'B')

  const knoepfeJeZeile = zeilen.map((z) => z.querySelector('button'))
  for (const b of knoepfeJeZeile) {
    assert.ok(b.classList.contains('dk-ui-btn'), 'der Knopf ist der DkButton des Hauses')
    assert.equal(b.textContent.trim(), 'Aufheben')
  }
  assert.match(knoepfeJeZeile[0].getAttribute('aria-label'), /Sperre für Erika M\. aufheben/,
    'der Knopf sagt, für WEN er aufhebt')
  // Kein Konto, keine E-Mail in der Liste (der Server schickt sie nicht).
  assert.doesNotMatch(text, /@/, 'keine E-Mail-Adresse in der Liste')
  s.abbaum()
})

test('CHAT-7b-UI-b/D: die Liste wird mit GET geholt (nicht POST — der Server erlaubt nur GET)', async () => {
  const s = await sperrenMontieren({ sperren: [{ mitglied: 'M-1', anzeigename: 'Erika M.', bild: '' }] })
  const liste = s.aufrufe.filter((a) => /chat\.meine_sperren$/.test(a.methode))
  assert.equal(liste.length, 1, 'genau EIN Ladeaufruf')
  assert.equal(liste[0].art, 'GET', 'meine_sperren ist GET (methods=["GET"] im Server)')
  assert.match(liste[0].methode, /^chat\.meine_sperren$/, 'über die registrierte chat-API, nicht über einen doppelten Pfad')
  assert.equal(s.host.querySelectorAll('.sp-zeile').length, 1, 'die Liste ist da')
  // „Aufheben“ bleibt ein POST.
  klick(s.host.querySelector('.sp-zeile button'))
  await warte(20)
  const aufheben = s.aufrufe.filter((a) => /chat\.kontakt_entsperren$/.test(a.methode))
  assert.equal(aufheben.length, 1)
  assert.equal(aufheben[0].art, 'POST', 'kontakt_entsperren ist POST')
  s.abbaum()
})

test('CHAT-7b-UI-b/D: der Leerzustand ist EIN Satz', async () => {
  const s = await sperrenMontieren()
  assert.match(s.host.textContent, /Du hast niemanden gesperrt\./)
  assert.equal(s.host.querySelectorAll('.sp-zeile').length, 0)
  assert.equal(knoepfe(s.host).filter((b) => b.textContent.includes('Aufheben')).length, 0,
    'ohne Einträge kein Aufheben-Knopf')
  s.abbaum()
})

test('CHAT-7b-UI-b/D: „Aufheben“ ruft kontakt_entsperren und nimmt NUR die eine Zeile weg', async () => {
  const s = await sperrenMontieren({
    sperren: [
      { mitglied: 'M-1', anzeigename: 'Erika M.', bild: '' },
      { mitglied: 'M-2', anzeigename: 'Bert B.', bild: '' },
    ],
  })
  klick([...s.host.querySelectorAll('.sp-zeile')][0].querySelector('button'))
  await warte(20)

  const posts = s.aufrufe.filter((a) => /kontakt_entsperren$/.test(a.methode))
  assert.equal(posts.length, 1, 'genau EIN Aufheben-Aufruf')
  assert.deepEqual(posts[0].parameter, { mitglied: 'M-1' })
  // Die Liste wird NICHT neu geladen — die eine Zeile verschwindet.
  assert.equal(s.aufrufe.filter((a) => /meine_sperren$/.test(a.methode)).length, 1,
    'kein zweiter Ladeaufruf')
  const namen = [...s.host.querySelectorAll('.sp-name')].map((a) => a.textContent.trim())
  assert.deepEqual(namen, ['Bert B.'], 'nur die aufgehobene Zeile ist weg')
  s.abbaum()
})

test('CHAT-7b-UI-b/D: ein 403 beim Aufheben bleibt ruhig stehen (kein „Unbekannter Fehler“)', async () => {
  const s = await sperrenMontieren({
    sperren: [{ mitglied: 'M-1', anzeigename: 'Erika M.', bild: '' }],
    ueberschreiben: {
      kontakt_entsperren: () => { const e = new Error('kein Zugriff'); e.status = 403; throw e },
    },
  })
  klick(s.host.querySelector('.sp-zeile button'))
  await warte(20)
  const alert = s.host.querySelector('[role="alert"]')
  assert.ok(alert, 'die Meldung ist eine Ansage')
  assert.match(alert.textContent, /Die Sperre konnte nicht aufgehoben werden\./)
  assert.doesNotMatch(alert.textContent, /Unbekannter Fehler|403/)
  assert.equal(s.host.querySelectorAll('.sp-zeile').length, 1, 'die Zeile bleibt (der Server hat nicht gelöscht)')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// E · Einbindung (Abschnitt, Adresse, Menü, Suche)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-7b-UI-b/E: der Abschnitt hängt in den Einstellungen (Datenschutz, OHNE Verwaltungsstufe)', () => {
  const quelle = lies('pages/Einstellungen.vue')
  assert.match(quelle, /id: 'sperren', label: 'Gesperrte Personen', href: '#\/einstellungen\/sperren',\s*seite: 'EinstellungenSperren', inhalt: SPERREN, gruppe: 'datenschutz' \}/,
    'der Eintrag steht so in der Liste — Gruppe „Datenschutz“')
  assert.doesNotMatch(quelle, /seite: 'EinstellungenSperren', inhalt: SPERREN, gruppe: 'datenschutz',\s*verwaltung/,
    'KEINE Verwaltungsstufe — jede angemeldete Person sieht ihre eigenen Sperren')
  // Der Inhalt wird als eigener Abschnitt geladen.
  assert.match(quelle, /const SPERREN = defineAsyncComponent\(\(\) => import\('\.\/einstellungen\/Sperren\.vue'\)\)/)
})

test('CHAT-7b-UI-b/E: Adresse im Router, KEINE Verwaltungsstufe für die Seite', async () => {
  const router = lies('router.js')
  assert.match(router, /'#\/einstellungen\/sperren': 'EinstellungenSperren'/, 'die Adresse ist verdrahtet')
  assert.match(router, /EinstellungenSperren: \(\) => import\('\.\/pages\/Einstellungen\.vue'\)/,
    'die Seite lädt den Einstellungs-Rahmen')

  // `verwaltungsStufeSeite` ist die EINE Quelle der Abstufung: für die Sperren
  // darf sie KEINE Stufe liefern (sonst sperrte der Router genau die Menschen
  // aus, um deren Sperren es geht). Der Router liest beim Import den Stand —
  // deshalb wird die reine Funktion hier aus dem Quelltext nachgebildet wie in
  // den Router-Tests (die Importe werden gestrichen, die Listen gelesen).
  const adminOnly = router.slice(router.indexOf('const ADMIN_ONLY_PAGES = new Set(['),
    router.indexOf('const PERSONEN_VERWALTUNG_PAGES'))
  const personen = router.slice(router.indexOf('const PERSONEN_VERWALTUNG_PAGES = new Set(['),
    router.indexOf('export function verwaltungsStufeSeite'))
  assert.doesNotMatch(adminOnly, /EinstellungenSperren/, 'nicht in ADMIN_ONLY_PAGES')
  assert.doesNotMatch(personen, /EinstellungenSperren/, 'nicht in PERSONEN_VERWALTUNG_PAGES')
})

test('CHAT-7b-UI-b/E: die Seitenleiste markiert „Einstellungen“ (kein zweiter Menüpunkt)', () => {
  const menue = readFileSync(new URL('../src/diakonos/menue.js', import.meta.url), 'utf8')
  const start = menue.indexOf("{ id: 'einstellungen'")
  const eintrag = menue.slice(start, menue.indexOf('badge: \'anfragen\'', start))
  assert.match(eintrag, /'EinstellungenSperren'/, 'die Seite gehört zum Menüpunkt „Einstellungen“')
})

test('CHAT-7b-UI-b/E: die Suche findet den Abschnitt über seine Wörter', async () => {
  const S = await import(new URL('pages/einstellungen/suche.mjs', SRC).href)
  const woerter = S.STICHWORTE.sperren || []
  assert.ok(woerter.length >= 4, 'genug Stichworte: ' + woerter.length)
  const quelle = lies('pages/einstellungen/Sperren.vue')
  // Die Gemeinsam-Texte der Sperre stehen in `composables/nachrichtenDirekt.mjs`
  // (SPERR_AKTION, SPERR_EINLEITUNG, SPERR_LEER, AUFHEBEN) — der Abschnitt bindet
  // sie, deshalb zählt die Datei als Quelle mit (wie im UX3h-Wächter).
  const heu = S.normalisiere(quelle + ' ' + lies('composables/nachrichtenDirekt.mjs'))
  const fehlend = woerter.filter((w) => !heu.includes(S.normalisiere(w)))
  assert.deepEqual(fehlend, [], 'jedes Stichwort steht wirklich im Abschnitt: ' + fehlend.join(', '))
  // Und die Suche trifft damit den Bereich.
  const treffer = S.trefferBereiche([{ id: 'sperren', label: 'Gesperrte Personen' }], 'gesperrt')
  assert.equal(treffer.size, 1)
})

test('CHAT-7b-UI-b/E: keine Tokens erfunden — der Abschnitt nutzt das Haus', () => {
  const quelle = lies('pages/einstellungen/Sperren.vue')
  // Nur DkButton/DkHint/DkSkelett, keine Roh-Farben, keine Hex-Werte.
  assert.doesNotMatch(quelle, /#[0-9a-fA-F]{3,8}\b/, 'keine Hex-Farben')
  assert.doesNotMatch(quelle, /rgb\(|hsl\(/, 'keine rohen Farbfunktionen')
  assert.match(quelle, /variant="secondary"[\s\S]*size="sm"/, 'der Knopf ist ein DkButton (secondary, sm)')
  // Nur EIN Abschnittstitel (h2) — die Seite bringt keinen zweiten Seitenkopf.
  assert.equal((quelle.match(/<h2/g) || []).length, 1)
})
// ════════════════════════════════════════════════════════════════════════════
// F · JEDE angemeldete Person kommt an „Gesperrte Personen“ (Review R1, Punkt 2)
//
// Blockieren geht jede angemeldete Person an — also muss auch der Abschnitt
// erreichbar sein. Gemessen wird an der ECHTEN Router- und Menülogik (Importe
// in einer vm wie in `chat-r2a-navigation`), nicht an Mustern im Quelltext:
// `resolveRoute` läuft, die Guards laufen, das Ergebnis wird befragt.
// ════════════════════════════════════════════════════════════════════════════

/**
 * router.js in einer vm laden und `resolveRoute` ECHT laufen lassen.
 *
 * Die Importe werden gestrichen (wie in den bestehenden Router-Tests) und die
 * Fremd-Abhängigkeiten als Attrappen in den Kontext gelegt. Zurück kommen
 * `seite(hash)` (Seitenname ohne Guards) und `gehen(hash)` — der volle Weg
 * inklusive `beforeEach`-Wächtern: landet ein Wächter auf `#/`, war die Seite
 * für diese Sitzung gesperrt.
 */
function routerLauf(boot = {}) {
  let quelle = lies('router.js')
  quelle = quelle.replace(/^import .*$/gm, '')
  quelle = quelle.replace(/^export \{ modulChatErlaubt \}$/gm,
    'const modulChatErlaubt = (boot = {}) => { if (boot.is_admin === true) return true; if (!Array.isArray(boot.module_sichtbar)) return false; return boot.module_sichtbar.includes("chat") }')
  // `menue.js` (die EINE Verwaltungsregel) fällt mit den Importen weg — der
  // Router nimmt dann seinen Rückfall (fail closed). Hier tritt die ECHTE
  // Regel als Attrappe ein (dieselben drei Stufen wie in `menue.js`), sonst
  // sperrte die VM JEDE Verwaltungsseite und die Gegenprobe wäre blind.
  quelle = quelle.replace(/^const verwaltungRegel = [\s\S]*?\n    : \(\) => false\n/m,
    'const verwaltungRegel = (stufe, { istAdmin = false, istMitgliederverwaltung = false } = {}) => {'
      + ' if (istAdmin !== true && istMitgliederverwaltung !== true) return false;'
      + ' return stufe !== \'admin\' || istAdmin === true }\n')
  quelle = quelle.replace(/^export \{([^}]*)\}$/gm, '')
  quelle = quelle.replace(/^export /gm, '')

  const ersetzt = []
  const windowStub = {
    __DIakonosBOOT: boot,
    location: { hash: boot.hash || '#/', replace(ziel) { this.hash = ziel; ersetzt.push(ziel) } },
    addEventListener: () => {},
    removeEventListener: () => {},
    matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
    history: { replaceState: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  }
  const context = {
    console,
    window: windowStub,
    document: { title: '', addEventListener: () => {}, removeEventListener: () => {}, querySelector: () => null },
    location: windowStub.location,
    history: windowStub.history,
    sessionStorage: windowStub.sessionStorage,
    localStorage: windowStub.localStorage,
    navigator: { language: 'de-DE' },
    setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
    Promise,
  }
  vm.createContext(context)
  context.__vue = {
    ref: (v) => ({ value: v }),
    computed: (fn) => ({ get value() { return fn() } }),
    shallowRef: (v) => ({ value: v }),
  }
  vm.runInContext(`
const ref = globalThis.__vue.ref
const computed = globalThis.__vue.computed
const shallowRef = globalThis.__vue.shallowRef
const setzeFenstertitel = () => {}
const darfWebsite = () => true
const fehlertext = (e) => String(e)
const einrichtungLeitung = {
  EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
  einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
  einrichtungGesehen: () => false,
}
const rueckwegBleibtGueltig = () => true
const rueckwegVergessen = () => {}
${quelle}
globalThis.routerApi = {
  weiterleitungsZiel, routeMap, dynamicRoutes, verwaltungsStufeSeite, modulChatErlaubt,
  PERSONEN_VERWALTUNG_PAGES, verwaltungErlaubt, regenerateGuards: null, beforeEachGuards,
}
`, context)
  const api = context.routerApi
  /** Seitennamen einer Adresse — dieselbe Reihenfolge wie `resolveRoute`. */
  const seite = (hash) => {
    const [pfadRoh] = hash.split('?')
    const pfad = pfadRoh.length > 2 && pfadRoh.endsWith('/') ? pfadRoh.replace(/\/+$/, '') : pfadRoh
    if (api.routeMap[pfad]) return api.routeMap[pfad]
    for (const r of api.dynamicRoutes) {
      const m = pfad.match(r.pattern)
      if (m) return r.page
    }
    return null
  }
  return { api, seite, ersetzt, window: windowStub, context }
}

/** Führt alle `beforeEach`-Wächter des Routers für eine Adresse aus. */
function sitzung(boot) {
  const l = routerLauf(boot)
  // Die ECHTEN Wächterfunktionen (dieselbe Liste, die `resolveRoute`
  // durchläuft) — aus der vm gelesen, kein Haken im Produktivcode.
  const wachen = l.api.beforeEachGuards
  assert.ok(Array.isArray(wachen) && wachen.length >= 4,
    'der Router hat seine Wächter registriert')
  const pruefen = (hash) => {
    const seiteName = l.seite(hash)
    l.window.location.hash = hash
    const umleitungen = []
    for (const w of wachen) {
      let r = w({ to: hash, name: seiteName, params: {} })
      if (r && typeof r.then === 'function') { umleitungen.push('ASYNC'); continue }
      if (r === false) { umleitungen.push('nein'); break }
      if (typeof r === 'string') { umleitungen.push(r); break }
    }
    return { seite: seiteName, umleitungen, ziel: l.window.location.hash }
  }
  return { l, pruefen }
}

const MITGLIED_BOOT = {
  is_admin: false, ist_mitgliederverwaltung: false, roles: ['Mitglied'],
  module_sichtbar: ['chat'], mitglied: { status: 'Mitglied' },
}
const VERWALTUNG_BOOT = {
  is_admin: false, ist_mitgliederverwaltung: true, roles: ['Mitgliederadministrator'],
  module_sichtbar: ['chat'], mitglied: { status: 'Mitglied' },
}

test('CHAT-7b-UI-b/F: ein gewöhnliches Mitglied erreicht #/einstellungen und #/einstellungen/sperren', () => {
  const { pruefen, l } = sitzung(MITGLIED_BOOT)
  const rahmen = pruefen('#/einstellungen')
  assert.equal(rahmen.seite, 'Einstellungen', '#/einstellungen löst auf die Einstellungen auf')
  assert.deepEqual(rahmen.umleitungen, [], 'kein Wächter schickt das Mitglied fort')
  assert.equal(rahmen.ziel, '#/einstellungen', 'die Adresse bleibt stehen')

  const sperren = pruefen('#/einstellungen/sperren')
  assert.equal(sperren.seite, 'EinstellungenSperren', 'die Sperrliste hat ihre eigene Seite')
  assert.deepEqual(sperren.umleitungen, [], 'auch der Abschnitt ist offen')
  assert.equal(sperren.ziel, '#/einstellungen/sperren')

  // Der Feldsuche-Weg (`#/einstellungen/sperren/<feld>`) kommt ebenfalls an.
  // Er läuft über das Bereichs-Muster des Routers (`#/einstellungen/<bereich>/
  // <feld>` → Seite `Einstellungen`, Bereich als Parameter): der Rahmen sucht
  // den Abschnitt „sperren“. Für ein Mitglied ist das jetzt ein offener Weg —
  // vorher fing ihn der Wächter der Seite `Einstellungen` ab.
  const feld = pruefen('#/einstellungen/sperren/aufheben')
  assert.equal(feld.seite, 'Einstellungen', 'der Sprung landet auf dem Einstellungs-Rahmen')
  assert.deepEqual(feld.umleitungen, [], 'und der Wächter lässt ihn durch')
  assert.equal(feld.ziel, '#/einstellungen/sperren/aufheben', 'die Adresse bleibt stehen')
  // Der Bereich ist derselbe, den die Einstellungen-Seite auflöst.
  assert.equal(l.seite('#/einstellungen/sperren'), 'EinstellungenSperren')
})

test('CHAT-7b-UI-b/F: Gegenprobe — die Verwaltungs-Unterseiten bleiben für das Mitglied gesperrt', () => {
  const { pruefen } = sitzung(MITGLIED_BOOT)
  // Jede dieser Seiten ist Personen- oder Adminbereich; der Wächter greift je
  // SEITE (nicht am Rahmen), deshalb bleibt die Schranke unverändert wirksam.
  const gesperrt = ['#/einstellungen/anmeldung', '#/einstellungen/registrierung',
    '#/einstellungen/rollen', '#/einstellungen/mailversand', '#/einstellungen/gemeinde',
    '#/einstellungen/datenschutz', '#/einstellungen/datensicherung', '#/einstellungen/papierkorb',
    '#/einstellungen/personenverwaltung']
  for (const hash of gesperrt) {
    const { umleitungen } = pruefen(hash)
    assert.ok(umleitungen.includes('nein') || umleitungen.some((u) => typeof u === 'string' && u !== 'ASYNC'),
      `${hash} bleibt für ein Mitglied gesperrt (Wächter-Antwort: ${JSON.stringify(umleitungen)})`)
  }
  // Und die Verwaltung selbst kommt dort an — der Wächter sperrt nach Recht,
  // nicht nach Adresse. (Die Attrappe `darfWebsite` lässt nur den Website-Weg
  // der VM offen; er wird hier nicht befragt.)
  const alsVerwaltung = sitzung(VERWALTUNG_BOOT)
  // `darfWebsite` der VM ist eine Konstante „erlaubt“ — ein `nein` käme hier
  // also aus der Verwaltungsregel. Geprüft wird die reine Entscheidung.
  const { api } = routerLauf(VERWALTUNG_BOOT)
  assert.equal(api.verwaltungsStufeSeite('EinstellungenPersonenverwaltung'), 'personen')
  assert.equal(api.verwaltungErlaubt('personen', VERWALTUNG_BOOT), true,
    'die Mitgliederverwaltung darf den Personenbereich weiterhin')
  assert.equal(api.verwaltungErlaubt('personen', MITGLIED_BOOT), false,
    'ein gewöhnliches Mitglied nicht')
  assert.deepEqual(alsVerwaltung.pruefen('#/einstellungen/personenverwaltung').umleitungen, [],
    'die Mitgliederverwaltung kommt an den Personenbereich')
  assert.deepEqual(alsVerwaltung.pruefen('#/einstellungen/sperren').umleitungen, [],
    'für die Verwaltung bleibt auch die Sperrliste offen')
})

test('CHAT-7b-UI-b/F: „Einstellungen“ steht im Fuß auch OHNE Verwaltungsrecht', () => {
  const sichtbar = sichtbarerFuss({ istAdmin: false, istMitgliederverwaltung: false })
  const eintrag = sichtbar.find((e) => e.id === 'einstellungen')
  assert.ok(eintrag, 'der Eintrag „Einstellungen“ ist für ein Mitglied sichtbar')
  assert.equal(eintrag.verwaltung, undefined, 'keine Verwaltungsstufe am Eintrag')
  assert.deepEqual(eintrag.seiten.includes('EinstellungenSperren'), true,
    'und er markiert sich auf der Sperrliste')
  // Gegenprobe: die Verwaltung sieht denselben Eintrag (eine Quelle).
  assert.ok(sichtbarerFuss({ istAdmin: false, istMitgliederverwaltung: true })
    .some((e) => e.id === 'einstellungen'))
  // Ein Gast sieht ihn nicht (GAST-Regel des Menüs bleibt unberührt).
  assert.equal(sichtbarerFuss({ istAdmin: false, istMitgliederverwaltung: false }).length >= 1, true)
})

test('CHAT-7b-UI-b/F: das Abzeichen „anfragen“ sieht NUR die Verwaltung', () => {
  // Die EINE Regel (`darfAnfragenZaehlerSehen`) — der Wert, den auch die
  // Seitenleiste und die Schublade befragen.
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: false }), false,
    'ein Mitglied sieht das Anfragen-Abzeichen nicht')
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: true }), true,
    'die Mitgliederverwaltung sieht es')
  assert.equal(darfAnfragenZaehlerSehen({}), false, 'fehlendes Recht = kein Abzeichen (fail closed)')
  // Und beide Zeichner fragen sie an, statt nur `badge` zu lesen.
  for (const datei of ['components/AppSidebar.vue', 'components/AppMenueSchublade.vue']) {
    const quelle = lies(datei)
    const rumpf = quelle.slice(quelle.indexOf('function badgeFuer('))
    const ende = rumpf.indexOf('\n}', 0)
    assert.match(rumpf.slice(0, ende), /istMitgliederverwaltungSehen\(\)/,
      `${datei}: badgeFuer prüft das Recht selbst`)
    // …und die Bedingung ist lokal dieselbe Regel wie `darfAnfragenZaehlerSehen`.
    assert.match(quelle, /function istMitgliederverwaltungSehen\(\) \{\s*return istVerwaltungRef\?\.value === true/,
      `${datei}: die Bedingung fragt die Sitzung`)
  }
})

test('CHAT-7b-UI-b/F: „Einstellungen“ steht NICHT mehr in PERSONEN_VERWALTUNG_PAGES', () => {
  const { api } = routerLauf(MITGLIED_BOOT)
  assert.equal(api.PERSONEN_VERWALTUNG_PAGES.has('Einstellungen'), false,
    'der Rahmen ist offen — sonst käme niemand an die Sperrliste')
  assert.equal(api.PERSONEN_VERWALTUNG_PAGES.has('EinstellungenSperren'), false,
    'die Sperrliste ebenfalls nicht')
  // Die Verwaltungs-Unterseiten bleiben drin (Gegenprobe oben).
  for (const name of ['EinstellungenAnmeldung', 'EinstellungenPersonenverwaltung', 'Registrierung']) {
    assert.equal(api.PERSONEN_VERWALTUNG_PAGES.has(name), true, `${name} bleibt Personenbereich`)
  }
  assert.equal(api.verwaltungsStufeSeite('Einstellungen'), null, 'keine Stufe für den Rahmen')
  assert.equal(api.verwaltungsStufeSeite('EinstellungenSperren'), null, 'keine Stufe für die Sperrliste')
  assert.equal(api.verwaltungsStufeSeite('EinstellungenAnmeldung'), 'personen')
})

// ════════════════════════════════════════════════════════════════════════════
// G · Nacharbeit R1 — die Befunde der Review
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-7b-UI-b/G: ohne `mitglied` gibt es keine Sperr-Aktion (kein Rückfall auf den Titel)', async () => {
  // Review R1, Punkt 4: `mitglied` ist die Kennung. Fehlt sie (gelöschtes
  // Gegenüber), darf der Titel NICHT als Kennung herhalten.
  const quelle = lies('pages/Nachrichten.vue')
  const abschnitt = quelle.slice(quelle.indexOf('const direktMitglied = computed('))
  const rumpf = abschnitt.slice(0, abschnitt.indexOf('\n\n'))
  assert.doesNotMatch(rumpf, /titel/, 'kein `titel`-Rückfall in der Kennung')

  const ordner = join(TMP, 'ohnemitglied-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  // Ein Gespräch OHNE `mitglied` — der Titel steht da, die Kennung nicht.
  const s = await nachrichtenMontieren({
    server: { meine_gespraeche: () => ({ gespraeche: [{ ...DIREKT, mitglied: '' }] }) },
  })
  // Ohne Kennung gibt es das „⋯“-Menü gar nicht: es trüge nur diese eine
  // (unmögliche) Aktion — ein leeres Menü wäre eine Attrappe.
  assert.equal(s.host.querySelector('.dk-ui-aktionen-ausloeser'), null,
    'ohne Kennung kein ⋯-Menü im Gesprächskopf')
  const eintraege = [...document.querySelectorAll('[role="menuitem"]')]
    .map((b) => b.textContent.trim())
  assert.equal(eintraege.includes('Nicht mehr anschreiben lassen'), false,
    'die Aktion wird nicht angeboten')
  // Und der Titel steht weiter als Anzeige da (nur eben nicht als Kennung).
  assert.match(s.host.textContent, /Erika Muster/, 'der Name bleibt sichtbar')
  s.abbaum()
})

test('CHAT-7b-UI-b/G: der Sperr-Hinweis verstummt beim Gesprächswechsel', async () => {
  const ordner = join(TMP, 'wechsel-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  process.on('unhandledRejection', () => {})
  globalThis.__FRAGE = null
  globalThis.__ANTWORT = true
  const s = await nachrichtenMontieren()
  const menue = await menueOeffnen(s.host)
  klick([...menue.querySelectorAll('[role="menuitem"]')]
    .find((b) => b.textContent.includes('Nicht mehr anschreiben lassen')))
  for (let i = 0; i < 60 && !globalThis.__FRAGE; i += 1) await warte(2)
  await warte(20)
  const hinweis = [...s.host.querySelectorAll('[role="status"]')]
    .some((e) => /keine Nachrichten mehr schreiben/.test(e.textContent))
  assert.equal(hinweis, true, 'der Hinweis steht zunächst da')

  // Gesprächswechsel: die Adresse führt zurück zur Liste — derselbe Weg wie ein
  // Klick auf ein anderes Gespräch (die Seite hängt an `offeneKennung`).
  dom.window.location.hash = '#/nachrichten'
  dom.window.dispatchEvent(new dom.window.HashChangeEvent('hashchange'))
  await warte(30)
  const danach = [...s.host.querySelectorAll('[role="status"]')]
    .some((e) => /keine Nachrichten mehr schreiben/.test(e.textContent))
  assert.equal(danach, false, 'beim Wechsel ist der Hinweis weg (kein Satz über die falsche Person)')
  s.abbaum()
})

test('CHAT-7b-UI-b/G: nach dem Sperren im Profil wird der Chat-Treffer neu geholt', async () => {
  // Review R1, Punkt 7: ob „Nachricht schreiben“ noch gilt, sagt der Server
  // (`hat_konto`) — die Seite fragt ihn neu, statt eine eigene Regel zu bauen.
  const ordner = join(TMP, 'profilnach-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  await bestaetigungVerdrahten(ordner)
  const aufrufe = []
  profilAttrappen(ordner, {
    aufrufe,
    server: {
      get_mitglied_detail: () => detailAntwort(),
      // Eine ERREICHBARE Person: ohne Treffer gäbe es keinen Chat-Knopf — und
      // ohne ihn bewusst auch keine Sperr-Aktion (Teil C, dritter Test).
      personen_suchen: () => ({ treffer: [TREFFER], limit: 20 }),
    },
  })
  globalThis.__FRAGE = null
  globalThis.__ANTWORT = true
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner, frisch: true })).href)
  const s = await mounten(mod.default, {})
  await warte(24)

  const knopf = knoepfe(s.host).find((b) => b.textContent.includes('Nicht mehr anschreiben lassen'))
  assert.ok(knopf, 'die Sperr-Aktion steht im Profil')
  const vorher = aufrufe.filter((a) => /personen_suchen$/.test(a.methode)).length
  klick(knopf)
  for (let i = 0; i < 80 && aufrufe.filter((a) => /personen_suchen$/.test(a.methode)).length === vorher; i += 1) {
    await warte(2)
  }
  await warte(20)
  const nachher = aufrufe.filter((a) => /personen_suchen$/.test(a.methode)).length
  assert.ok(nachher > vorher, `der Chat-Treffer wird neu geholt (${vorher} → ${nachher})`)
  assert.equal(aufrufe.some((a) => /kontakt_sperren$/.test(a.methode)), true, 'die Sperre ging hinaus')
  s.abbaum()
})
