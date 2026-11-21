/**
 * CHAT-12b — Anhänge im Chat: Oberfläche (Vue 3, Frontend). Karte t_0aa9fe5b.
 *
 * Grundlage ist das FERTIGE Backend (CHAT-12a,
 * `backend/src/diakronos_app/api/chat.py`), nicht eine Erfindung:
 *
 *   POST chat.anhang_hochladen(gespraech, datei=<Multipart>)
 *        → {name, dateiname, mime, groesse, gespraech}
 *        Typen per MAGIE (jpg/png/webp/heic, pdf, mp3/m4a/ogg/opus),
 *        Grenze `ANHANG_MAX_BYTES` = 10 MB, Tagesgrenze 20 je Person → 429.
 *   chat.senden(…, anhaenge=[name, …]) — höchstens 3 (`_anhaenge_pruefen`);
 *        mit Anhang darf der TEXT LEER sein (`_pruefe_text(mit_anhang=True)`).
 *   Der Verlauf trägt je Nachricht `anhaenge: [{name, dateiname, mime,
 *        groesse}]`; eine GELÖSCHTE Nachricht trägt `[]` (`_zeile`).
 *   GET chat.anhang?name=<name> — offene Anhänge sind dort 404.
 *
 * Geprüft wird VERHALTEN, nicht Quelltext:
 *
 *   A  Die Regeln ohne DOM (`components/chat/anhaenge.mjs`): Grenzen (10 MB,
 *      3 Anhänge), Vorab-Prüfung, Chip-Zustände, Kennungen fürs Senden,
 *      Sende-Erlaubnis (Text ODER Anhang, gesperrt während eines Uploads),
 *      Antwort-Auslegung inkl. 429, Anhänge einer Zeile (gelöscht → keine),
 *      Anzeigeart je Typ, Adresse über `chat.anhang?name=`.
 *   B  ChatBlase/ChatAnhangBlase gemountet: Bild als Vorschau mit `alt` =
 *      Dateiname, PDF als Dateizeile mit Herunterladen, Audio als `<audio
 *      preload="none">`, gelöschte Nachricht ohne Anhänge, richtige URL.
 *   C  Nachrichten.vue gemountet (API gemockt): Auswahl → Upload mit
 *      FormData (`gespraech` + `datei`); >10 MB und >3 abgewiesen OHNE Upload;
 *      Senden schickt `anhaenge` mit den Kennungen; Senden gesperrt während
 *      eines Uploads; 429-Meldung; Gesprächswechsel verwirft späte Antworten.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat12b-anhaenge.test.mjs
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
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent', 'HashChangeEvent',
  'AbortController', 'AbortSignal', 'File', 'Blob', 'FileList']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
globalThis.CSS = dom.window.CSS || { escape: (s) => String(s) }
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat12b-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

const T = await import(new URL('components/chat/anhaenge.mjs', SRC).href)
const SPEICHER = await import(new URL('components/ui/symbole.mjs', SRC).href)

// ── SFC → ES-Modul (derselbe Weg wie die übrigen chat*-UI-Tests) ───────────
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
    const wurzel = resolve(SRC_ROOT.pathname)
    const voll = resolve(quellDatei)
    const relativ = voll.startsWith(wurzel) ? 'x' + voll.slice(wurzel.length) : voll
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

/** Mounten mit Horcher für die Ereignisse der Komponente. */
async function mounten(baustein, props = {}, { horcher = null, propNamen = null, vertreter = null } = {}) {
  let vertreten = null
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  let seite = null
  const kennung = Math.random().toString(36).slice(2)
  globalThis.__HORCHER = globalThis.__HORCHER || {}
  globalThis.__HORCHER[kennung] = horcher
  const melde = (art, wert) => {
    const h = globalThis.__HORCHER[kennung]
    if (h) h(art, wert)
  }
  const namen = propNamen || []
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      let kind = null
      Vue.onMounted(() => {
        const kandidat = innerProps.refKasten
        if (kandidat) kandidat.value = kind
      })
      seite = Vue.getCurrentInstance()
      const eigene = Vue.ref({ ...innerProps.p })
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (name, wert) => {
        eigene.value = { ...eigene.value, [name]: wert }
      }
      const rueckrufe = Object.fromEntries(
        namen.map((n) => [`on${n[0].toUpperCase()}${n.slice(1)}`, (x) => melde(n, x)]),
      )
      const kinderRef = typeof vertreter === 'function'
        ? (r) => { vertreten = r; vertreter(r) }
        : null
      return () => Vue.h(baustein, {
        ...(kinderRef ? { ref: kinderRef } : {}),
        ...eigene.value,
        ...rueckrufe,
      })
    },
  }
  const app = Vue.createApp({ render: () => Vue.h(Wrapper, { p: props }) })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(10)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  return {
    host, app, abbaum, warnungen,
    instanz: () => seite,
    exposed: () => vertreten,
    Vue,
    setze: (n, w) => globalThis.__PROP_SETZEN[kennung](n, w),
  }
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln ohne DOM
// ════════════════════════════════════════════════════════════════════════════

/** Eine Datei-Attrappe, wie der Browser sie in `input.files` legt. */
function datei(name, groesse, typ = 'image/jpeg') {
  const d = new File([new Uint8Array(1)], name, { type: typ })
  Object.defineProperty(d, 'size', { configurable: true, value: groesse })
  return d
}

test('CHAT-12b/A: Grenzen sind DIESELBEN Zahlen wie im Server', () => {
  // models/chat.py: ANHANG_MAX_BYTES = 10 * 1024 * 1024, ANHAENGE_MAX = 3,
  // ANHAENGE_PRO_TAG = 20.
  assert.equal(T.ANHANG_MAX_BYTES, 10 * 1024 * 1024)
  assert.equal(T.ANHAENGE_MAX, 3)
  assert.equal(T.ANHAENGE_PRO_TAG, 20)
  // `accept` bietet die Kamera an und nennt die erlaubten Endungen.
  assert.match(T.ANHANG_ACCEPT, /image\/\*/)
  for (const endung of ['.jpg', '.png', '.webp', '.heic', '.pdf', '.mp3', '.m4a', '.ogg', '.opus']) {
    assert.ok(T.ANHANG_ACCEPT.includes(endung), `${endung} steht in der Auswahl`)
  }
})

test('CHAT-12b/A: Größe in Worten — dezimal, wie im Dateimanager', () => {
  assert.equal(T.groesseText(824), '824 B')
  assert.equal(T.groesseText(1200), '1,2 kB')
  assert.equal(T.groesseText(12_000), '12 kB')
  assert.equal(T.groesseText(1_400_000), '1,4 MB')
  assert.equal(T.groesseText(0), '0 B')
  assert.equal(T.groesseText(null), '')
  assert.equal(T.groesseText(-1), '')
})

test('CHAT-12b/A: die Anzeigeart entscheidet der SERVER-Typ, nicht der Name', () => {
  assert.equal(T.anhangArt({ mime: 'image/jpeg' }), 'bild')
  assert.equal(T.anhangArt({ mime: 'image/png' }), 'bild')
  assert.equal(T.anhangArt({ mime: 'image/webp' }), 'bild')
  // HEIC ist ABSICHTLICH eine Dateizeile: die meisten Browser zeigen es nicht.
  assert.equal(T.anhangArt({ mime: 'image/heic' }), 'datei')
  assert.equal(T.anhangArt({ mime: 'application/pdf' }), 'pdf')
  assert.equal(T.anhangArt({ mime: 'audio/mpeg' }), 'audio')
  assert.equal(T.anhangArt({ mime: 'audio/mp4' }), 'audio')
  assert.equal(T.anhangArt({ mime: 'audio/ogg' }), 'audio')
  assert.equal(T.anhangArt({ mime: 'audio/opus' }), 'audio')
  // Ein Name sagt hier nichts: ohne geprüften Typ bleibt es eine Datei.
  assert.equal(T.anhangArt({ dateiname: 'foto.jpg' }), 'datei')
  // Die Symbole stehen im Vorrat (sonst zeichnete DkSymbol nichts).
  for (const mime of ['image/png', 'application/pdf', 'audio/mpeg', 'image/heic']) {
    assert.ok(SPEICHER.SYMBOLNAMEN.includes(T.anhangSymbol({ mime })), `${mime}: Symbol im Vorrat`)
  }
  assert.ok(SPEICHER.SYMBOLNAMEN.includes('klammer'), 'die Büroklammer steht im Vorrat')
})

test('CHAT-12b/A: die Adresse eines Anhangs ist chat.anhang?name=… — mit Präfix', () => {
  const basis = (m) => `/diakonos/api/method/${m}`
  assert.equal(T.anhangUrl('CHAT-A-1', basis), '/diakonos/api/method/chat.anhang?name=CHAT-A-1')
  // Ohne Basis der nackte Pfad (dieselbe Form wie ohne Betriebs-Präfix).
  assert.equal(T.anhangUrl('CHAT-A-1'), '/api/method/chat.anhang?name=CHAT-A-1')
  // Die Kennung wird kodiert — sie ist eine Adresse, kein Freitext.
  assert.equal(T.anhangUrl('a b&c', basis), '/diakonos/api/method/chat.anhang?name=a%20b%26c')
  assert.equal(T.anhangUrl('', basis), '')
})

test('CHAT-12b/A: Vorab-Prüfung — >10 MB und >3 werden OHNE Upload abgewiesen', () => {
  const ok = T.auswahlPruefen([datei('a.jpg', 1000)], 0)
  assert.equal(ok.ok, true)
  assert.equal(ok.dateien.length, 1)

  // Zu groß: der Satz nennt Grenze UND Datei, kein Upload.
  const gross = T.auswahlPruefen([datei('riessig.jpg', T.ANHANG_MAX_BYTES + 1)], 0)
  assert.equal(gross.ok, false)
  assert.deepEqual(gross.dateien, [], 'keine Datei geht hoch')
  assert.match(gross.text, /zu groß/)
  assert.match(gross.text, /10 MB/)
  assert.match(gross.text, /riessig\.jpg/)

  // Genau 10 MB ist erlaubt (die Grenze ist ≤).
  assert.equal(T.auswahlPruefen([datei('genau.jpg', T.ANHANG_MAX_BYTES)], 0).ok, true,

    'genau 10 MB geht')

  // Mehr als 3: freundliche Meldung, KEIN Upload — auch gemischt mit schon
  // vorhandenen Chips.
  const vier = T.auswahlPruefen([
    datei('1.jpg', 10), datei('2.jpg', 10), datei('3.jpg', 10), datei('4.jpg', 10),
  ], 0)
  assert.equal(vier.ok, false)
  assert.deepEqual(vier.dateien, [])
  assert.match(vier.text, /Es sind schon 3 Anhänge ausgewählt/)
  const nachZwei = T.auswahlPruefen([datei('3.jpg', 10), datei('4.jpg', 10)], 2)
  assert.equal(nachZwei.ok, false, 'zwei vorhandene + zwei neue sind vier')
  assert.equal(T.auswahlPruefen([datei('3.jpg', 10)], 2).ok, true, 'drei gehen')

  // Leere Datei: nichts zu senden (der Server weist sie auch ab).
  assert.equal(T.auswahlPruefen([datei('leer.jpg', 0)], 0).ok, false)

})

test('CHAT-12b/A: ein Chip trägt Name, Größe, Stand — und die Kennung erst nach dem Upload', () => {
  const chip = T.chipBauen(datei('probe.jpg', 2048), { lauf: 7, gespraech: 'CHAT-2' })
  assert.equal(chip.dateiname, 'probe.jpg')
  assert.equal(chip.groesse, 2048)
  assert.equal(chip.stand, 'laedt')
  assert.equal(chip.name, '', 'vor der Antwort gibt es keine Kennung')
  assert.equal(chip.gespraech, 'CHAT-2')
  assert.ok(chip.schluessel.includes('probe.jpg'), 'der Schlüssel nennt die Datei')

  const fertig = T.chipAendern([chip], chip.schluessel, { stand: 'fertig', name: 'CHAT-A-1' })
  assert.equal(fertig[0].stand, 'fertig')
  assert.equal(fertig[0].name, 'CHAT-A-1')
  assert.equal(fertig[0].schluessel, chip.schluessel, 'der Schlüssel bleibt')
  // Entfernen nimmt NUR den Eintrag aus der Liste.
  assert.deepEqual(T.chipEntfernen(fertig, chip.schluessel), [])
  assert.deepEqual(T.chipEntfernen(fertig, 'anderer'), fertig)
})

test('CHAT-12b/A: welche Kennungen gehen beim Senden mit? — NUR fertige', () => {
  const liste = [
    { schluessel: 'a', stand: 'fertig', name: 'CHAT-A-1' },
    { schluessel: 'b', stand: 'laedt', name: '' },
    { schluessel: 'c', stand: 'fehler', name: '' },
    { schluessel: 'd', stand: 'fertig', name: 'CHAT-A-2' },
  ]
  assert.deepEqual(T.anhangKennungen(liste), ['CHAT-A-1', 'CHAT-A-2'])
  assert.equal(T.laedtNoch(liste), true)
  assert.equal(T.laedtNoch(liste.filter((c) => c.stand !== 'laedt')), false)

  // Senden: der Text geht ungetrimmt hinaus, `anhaenge` nur, wenn es welche gibt.
  const rumpf = T.sendeRumpf({ gespraech: 'CHAT-2', text: '  Hallo\nWelt  ', anhaenge: ['CHAT-A-1'] })
  assert.deepEqual(rumpf, { gespraech: 'CHAT-2', text: '  Hallo\nWelt  ', anhaenge: ['CHAT-A-1'] })
  const ohne = T.sendeRumpf({ gespraech: 'CHAT-2', text: 'Hallo', anhaenge: [] })
  assert.equal('anhaenge' in ohne, false, 'ohne Anhang steht das Feld gar nicht da')
})

test('CHAT-12b/A: Senden ist gesperrt, solange ein Upload läuft', () => {
  const fertig = [{ schluessel: 'a', stand: 'fertig', name: 'CHAT-A-1' }]
  const laedt = [...fertig, { schluessel: 'b', stand: 'laedt', name: '' }]
  assert.equal(T.darfSenden({ gespraech: 'CHAT-2', text: 'Hallo', liste: [] }), true)
  assert.equal(T.darfSenden({ gespraech: 'CHAT-2', text: '', liste: [] }), false, 'leer geht nicht')
  assert.equal(T.darfSenden({ gespraech: 'CHAT-2', text: '', liste: fertig }), true,
    '„Foto ohne Worte“ ist erlaubt (mit_anhang im Server)')
  assert.equal(T.darfSenden({ gespraech: 'CHAT-2', text: 'Hallo', liste: laedt }), false,
    'während des Uploads kein Senden')
  assert.equal(T.darfSenden({ gespraech: '', text: 'Hallo', liste: [] }), false, 'ohne Gespräch nichts')
})

test('CHAT-12b/A: 429 bekommt den festen Satz „Tageslimit“', () => {
  assert.equal(T.uploadFehlerText({ status: 429, message: 'irgendwas vom Server' }),
    T.TEXTE.tageslimit)
  assert.match(T.TEXTE.tageslimit, /Tageslimit für Anhänge erreicht/)
  // Alles andere ist die Server-Meldung — für Menschen geschrieben.
  assert.equal(T.uploadFehlerText({ status: 417, message: 'Die Datei ist zu groß (max. 10 MB).' }),
    'Die Datei ist zu groß (max. 10 MB).')
  assert.equal(T.uploadFehlerText({}, { ersatz: 'Ersatz' }), 'Ersatz')
})

test('CHAT-12b/A: die Antwort des Uploads braucht eine Kennung', () => {
  const gut = T.uploadAntwort({ name: 'CHAT-A-9', dateiname: 'probe.jpg', mime: 'image/jpeg', groesse: 99 })
  assert.equal(gut.ok, true)
  assert.equal(gut.name, 'CHAT-A-9')
  assert.equal(gut.groesse, 99)
  // Ohne Kennung ist der Upload NICHT geglückt (senden könnte ihn nicht mitnehmen).
  assert.equal(T.uploadAntwort({ dateiname: 'x.jpg' }).ok, false)
  assert.equal(T.uploadAntwort(null).ok, false)
})

test('CHAT-12b/A: eine gelöschte Nachricht zeigt KEINE Anhänge', () => {
  const anhaenge = [
    { name: 'CHAT-A-1', dateiname: 'foto.jpg', mime: 'image/jpeg', groesse: 100 },
    { name: 'CHAT-A-2', dateiname: 'brief.pdf', mime: 'application/pdf', groesse: 200 },
  ]
  const offen = T.zeilenAnhaenge({ text: 'Hallo', anhaenge })
  assert.deepEqual(offen.map((a) => a.name), ['CHAT-A-1', 'CHAT-A-2'])
  assert.equal(offen[0].art, 'bild')
  assert.equal(offen[1].art, 'pdf')
  assert.equal(T.zeilenAnhaenge({ geloescht: true, anhaenge }).length, 0,
    'gelöscht → nichts, auch wenn eine alte Liste noch dranhängt')
  assert.deepEqual(T.zeilenAnhaenge({ text: 'Hallo' }), [], 'ohne Feld: keine Anhänge')
  assert.deepEqual(T.zeilenAnhaenge(null), [])
  // Eine Zeile ohne Kennung ist kein Anhang (nichts, was man abrufen könnte).
  assert.deepEqual(T.zeilenAnhaenge({ anhaenge: [{ dateiname: 'x.jpg' }] }), [])
})

test('CHAT-12b/A: die Laufnummer gilt je GESPRÄCH — gleichzeitige Uploads entwerten sich nicht', () => {
  const lauf = T.uploadLauf()
  // Zwei Dateien auf einmal: BEIDE Antworten gehören zum selben Gespräch.
  const erste = lauf.neu()
  const zweite = lauf.neu()
  assert.equal(erste, zweite, 'neu() erhöht nicht — eine Generation je Gespräch')
  assert.equal(lauf.gilt(erste), true, 'die erste Antwort gilt')
  assert.equal(lauf.gilt(zweite), true, 'die zweite ebenfalls')
  // Erst der Wechsel entwertet alle laufenden Uploads.
  lauf.abbrechen()
  assert.equal(lauf.gilt(erste), false, 'nach dem Gesprächswechsel gilt keine mehr')
  assert.equal(lauf.gilt(lauf.neu()), true, 'das neue Gespräch hat eine gültige Nummer')
  // Eine frische Nummer ist von Anfang an gültig.
  const frisch = T.uploadLauf()
  assert.equal(frisch.gilt(frisch.neu()), true)
})

test('CHAT-12b/A: Auswahl-Prüfung — gescheiterte Chips belegen keinen Platz', () => {
  // Drei Fehlschläge hintereinander dürfen die nächste Auswahl nicht sperren.
  assert.equal(T.auswahlPruefen([datei('neu.jpg', 10)], 3, 3).ok, true,
    'drei Fehler-Chips zählen nicht als belegt')
  assert.equal(T.auswahlPruefen([datei('neu.jpg', 10)], 2, 1).ok, true,
    'zwei belegt + ein Fehler → ein Platz bleibt')
  assert.equal(T.auswahlPruefen([datei('1.jpg', 10), datei('2.jpg', 10)], 2, 0).ok, false,
    'drei Belegte + zwei neue sind fünf')
})

// ════════════════════════════════════════════════════════════════════════════
// B · Die Blase gemountet — Bild, PDF, Audio, gelöschte Nachricht
// ════════════════════════════════════════════════════════════════════════════

const BASIS = (m) => `/diakonos/api/method/${m}`

function nachrichtMit(anhaenge, extra = {}) {
  return {
    ident: 'N-1', id: 'N-1', text: 'Schau mal', autor: 'Anna Beispiel', eigene: false,
    zeit: '10:00', erstellt_am: '2026-11-18T10:00:00', geloescht: false,
    reaktionen: [], antwort_auf: null, bearbeitbar: false, anhaenge,
    ...extra,
  }
}

test('CHAT-12b/B: Bild als Vorschau — lazy, mit alt = Dateiname, Klick öffnet groß', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatAnhangBlase.vue', { frisch: true })).href)).default
  const m = await mounten(mod, {
    nachricht: nachrichtMit([
      { name: 'CHAT-A-1', dateiname: 'probe.jpg', mime: 'image/jpeg', groesse: 2048 },
    ]),
    basis: BASIS,
  })
  await rendern(3)
  const bild = m.host.querySelector('img')
  assert.ok(bild, 'die Vorschau steht da')
  assert.equal(bild.getAttribute('alt'), 'probe.jpg', 'alt ist der Dateiname (Karte Punkt 4)')
  assert.equal(bild.getAttribute('loading'), 'lazy')
  assert.equal(bild.getAttribute('src'), '/diakonos/api/method/chat.anhang?name=CHAT-A-1')
  // Klick öffnet groß: das Bild steckt in einem Link auf dieselbe Adresse.
  const link = bild.closest('a')
  assert.ok(link, 'die Vorschau ist ein Link')
  assert.equal(link.getAttribute('href'), '/diakonos/api/method/chat.anhang?name=CHAT-A-1')
  assert.equal(link.getAttribute('target'), '_blank')
  assert.equal(link.getAttribute('rel'), 'noopener')
  assert.equal(m.host.querySelector('audio'), null, 'kein Abspieler für ein Bild')
  m.abbaum()
})

test('CHAT-12b/B: PDF und HEIC als Dateizeile mit Herunterladen', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatAnhangBlase.vue', { frisch: true })).href)).default
  const m = await mounten(mod, {
    nachricht: nachrichtMit([
      { name: 'CHAT-A-2', dateiname: 'brief.pdf', mime: 'application/pdf', groesse: 1_400_000 },
      { name: 'CHAT-A-3', dateiname: 'foto.heic', mime: 'image/heic', groesse: 900 },
    ]),
    basis: BASIS,
  })
  await rendern(3)
  assert.equal(m.host.querySelectorAll('img').length, 0, 'kein Vorschaubild für PDF/HEIC')
  const zeilen = [...m.host.querySelectorAll('.dk-chat-anhang-zeile')]
  assert.equal(zeilen.length, 2)
  assert.match(zeilen[0].textContent, /brief\.pdf/)
  assert.match(zeilen[0].textContent, /1,4 MB/, 'die Größe steht dabei')
  assert.match(zeilen[1].textContent, /foto\.heic/, 'HEIC ist eine Dateizeile, keine Vorschau')
  const laden = zeilen[0].querySelector('a.dk-chat-anhang-laden')
  assert.ok(laden, 'es gibt einen Herunterladen-Link')
  assert.equal(laden.getAttribute('href'), '/diakonos/api/method/chat.anhang?name=CHAT-A-2')
  assert.equal(laden.getAttribute('download'), 'brief.pdf')
  assert.match(laden.getAttribute('aria-label'), /Herunterladen: brief\.pdf/)
  m.abbaum()
})

test('CHAT-12b/B: Audio als <audio controls preload="none">', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatAnhangBlase.vue', { frisch: true })).href)).default
  const m = await mounten(mod, {
    nachricht: nachrichtMit([
      { name: 'CHAT-A-4', dateiname: 'sprachnachricht.m4a', mime: 'audio/mp4', groesse: 400_000 },
    ]),
    basis: BASIS,
  })
  await rendern(3)
  const ton = m.host.querySelector('audio')
  assert.ok(ton, 'der Abspieler steht da')
  assert.equal(ton.getAttribute('preload'), 'none', 'nichts vorladen (ein Verlauf voller Ton)')
  assert.ok(ton.hasAttribute('controls'))
  assert.equal(ton.getAttribute('src'), '/diakonos/api/method/chat.anhang?name=CHAT-A-4')
  m.abbaum()
})

test('CHAT-12b/B: in der BLASE hängt der Anhang an der Nachricht; gelöscht zeigt nichts', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true })).href)).default
  const m = await mounten(mod, {
    nachricht: nachrichtMit([
      { name: 'CHAT-A-1', dateiname: 'probe.png', mime: 'image/png', groesse: 500 },
    ]),
    basis: BASIS,
    handyLage: false,
  })
  await rendern(3)
  const bild = m.host.querySelector('.dk-chat-anhaenge-blase img')
  assert.ok(bild, 'die Blase zeigt den Anhang')
  assert.equal(bild.getAttribute('src'), '/diakonos/api/method/chat.anhang?name=CHAT-A-1')
  m.abbaum()

  // Gelöschte Nachricht: der Hinweis steht da, KEINE Anhänge — auch wenn eine
  // alte Liste noch mitkäme.
  const g = await mounten(mod, {
    nachricht: nachrichtMit(
      [{ name: 'CHAT-A-1', dateiname: 'probe.png', mime: 'image/png', groesse: 500 }],
      { geloescht: true, hinweis: 'Du hast diese Nachricht gelöscht.' },
    ),
    basis: BASIS,
  })
  await rendern(3)
  assert.equal(g.host.querySelector('.dk-chat-anhaenge-blase'), null, 'gelöscht → keine Anhänge')
  assert.equal(g.host.querySelector('img'), null)
  assert.match(g.host.textContent, /Du hast diese Nachricht gelöscht\./)
  g.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Die Seite „Nachrichten“ gemountet — Auswahl, Upload, Senden
// ════════════════════════════════════════════════════════════════════════════

const GESPRAECH = {
  name: 'CHAT-2', art: 'gruppe', gruppe: 'Chor', untergruppe: null,
  titel: 'Chor', teilnehmer: 2, stumm: false, geoeffnet: true,
  ungelesen: 0, letzte_nachricht: 'Hallo', letzte_am: '2026-11-18T10:00:00', darf_senden: true,
}
const GESPRAECH_ZWEI = { ...GESPRAECH, name: 'CHAT-5', titel: 'Runde', art: 'runde', teilnehmer: 3 }

/** Eine Verlaufszeile (`chat.verlauf`). */
function zeile(name, { text = 'Hallo', anhaenge = [] } = {}) {
  return {
    name, gespraech: 'CHAT-2', text, autor: 'M-1', eigene: false,
    erstellt_am: '2026-11-18T10:00:00', anhaenge,
  }
}

/**
 * Die Seite mit Attrappen mounten.
 *
 * Der Upload geht über `fetch` (Multipart) — deshalb fängt der Test auch
 * `fetch` ab und sammelt die FormData. Die Antworten stellt `globalThis.
 * __UPLOAD12B` je Aufruf.
 */
async function seite12b({
  hash = '#/nachrichten/CHAT-2',
  verlauf = [zeile('N-1')],
  gespraeche = [GESPRAECH, GESPRAECH_ZWEI],
} = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  const uploads = []
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH12B({ art: "POST", methode, parameter })',
    '  return globalThis.__SERVER12B({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH12B({ art: "GET", methode, parameter })',
    '  return globalThis.__SERVER12B({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "/diakonos/api/method/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async (res, { anfrage } = {}) => {',
    '  const daten = globalThis.__ANTWORT12B(res)',
    '  try { Object.defineProperty(daten, "dkAntwort", { value: res, enumerable: false }) } catch {}',
    '  return daten',
    '}',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  globalThis.__PUSH12B = (e) => aufrufe.push(e)
  globalThis.__SERVER12B = async ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche }
    if (kurz === 'verlauf') return { richtung: 'neueste', nachrichten: verlauf }
    if (kurz === 'nachrichten_suchen') return { treffer: [], mehr: false, vor: null }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    if (kurz === 'senden') return zeile('N-NEU', { text: parameter?.text || '', anhaenge: [] })
    return {}
  }
  // Die Upload-Antwort je Aufruf: `globalThis.__UPLOAD12B` liefert sie.
  globalThis.__UPLOAD12B = async ({ form, nummer }) => ({ name: `CHAT-A-${nummer}` })
  // Offene Anfragen, die ein Test absichtlich hängen lässt — `abbaum` löst sie
  // auf, damit keine wartende Zusage den Prozess am Leben hält.
  const offene = []
  globalThis.__OFFENE12B = offene
  globalThis.__AUFLOESEN12B = () => {
    while (offene.length) { try { offene.shift()() } catch { /* egal */ } }
  }
  globalThis.__ANTWORT12B = (res) => res.__daten || {}
  const echtesFetch = globalThis.fetch
  globalThis.fetch = async (url, optionen = {}) => {
    const form = optionen.body
    const felder = {}
    if (form && typeof form.forEach === 'function') {
      form.forEach((wert, schluessel) => { felder[schluessel] = wert })
    }
    uploads.push({ url: String(url), felder, datei: felder.datei })
    const antwort = await globalThis.__UPLOAD12B({ form, felder, nummer: uploads.length })
    if (antwort && antwort.__fehler) {
      return { ok: false, status: antwort.status || 400, __daten: { message: antwort.__fehler }, async text() { return '' } }
    }
    return {
      ok: true, status: 200,
      __daten: { message: { name: antwort.name, dateiname: antwort.dateiname || '', mime: antwort.mime || '', groesse: antwort.groesse || 0 } },
      async text() { return '' },
    }
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage), matches: false,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
  const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)).default
  const m = await mounten(mod, {})
  for (let i = 0; i < 15; i += 1) { await warte(8); await rendern(4) }
  const abbaum = m.abbaum
  return {
    ...m,
    aufrufe,
    uploads,
    abbaum: () => {
      // Offene Uploads (der Test hält sie absichtlich an) freigeben, damit
      // keine wartende Zusage den Prozess am Leben hält.
      if (typeof globalThis.__AUFLOESEN12B === 'function') globalThis.__AUFLOESEN12B()
      globalThis.fetch = echtesFetch
      abbaum()
    },
  }
}

const klick = (el) => {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/** Dateien in das (versteckte) Feld legen und `change` auslösen. */
const auswaehlen = async (host, dateien) => {
  const feld = host.querySelector('input[type="file"]')
  assert.ok(feld, 'das Dateifeld steht im DOM')
  Object.defineProperty(feld, 'files', { configurable: true, value: dateien })
  feld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
}

/** Ein echtes `File`-Objekt mit gewünschter Größe. */
function dateiEcht(name, groesse, typ = 'image/jpeg') {
  const inhalt = new Uint8Array(Math.min(groesse, 64))
  const d = new dom.window.File([inhalt], name, { type: typ })
  Object.defineProperty(d, 'size', { configurable: true, value: groesse })
  return d
}

const chiptexte = (host) => [...host.querySelectorAll('.dk-chat-anhang-chip')]
  .map((c) => c.textContent.replace(/\s+/g, ' ').trim())

test('CHAT-12b/C: Auswahl → Upload mit FormData (gespraech + datei), Chip „bereit“', async () => {
  const s = await seite12b()
  // Das Dateifeld trägt die Auswahl-Grenzen; die Büroklammer öffnet es.
  const feld = s.host.querySelector('input[type="file"]')
  assert.ok(feld, 'ein Dateifeld steht im DOM')
  assert.match(feld.getAttribute('accept'), /image\/\*/, 'die Kamera wird angeboten')
  assert.ok(feld.hasAttribute('multiple'), 'mehrere Dateien auf einmal')
  assert.equal(feld.hasAttribute('disabled'), false)
  const klammer = s.host.querySelector('.dk-chat-anhang-knopf')
  assert.ok(klammer, 'die Büroklammer steht in der Eingabezeile')
  assert.equal(klammer.getAttribute('aria-label'), 'Datei anhängen', 'mit aria-label (Karte Punkt 4)')

  await auswaehlen(s.host, [dateiEcht('probe.jpg', 2048, 'image/jpeg')])
  assert.equal(s.uploads.length, 1, 'genau EIN Upload')
  assert.equal(s.uploads[0].url, '/diakonos/api/method/chat.anhang_hochladen')
  assert.ok(s.uploads[0].felder.gespraech, 'das Gespräch geht mit')
  assert.equal(s.uploads[0].felder.gespraech, 'CHAT-2')
  assert.ok(s.uploads[0].datei, 'die Datei geht als `datei` mit')
  assert.equal(s.uploads[0].datei.name, 'probe.jpg')

  const chips = chiptexte(s.host)
  assert.equal(chips.length, 1, 'ein Chip je Datei')
  assert.match(chips[0], /probe\.jpg/)
  assert.match(chips[0], /2,0 kB|2048 B/, 'die Größe steht dabei')
  assert.match(chips[0], /bereit/, 'nach der Antwort: bereit')
  s.abbaum()
})

test('CHAT-12b/C: >10 MB und >3 abgewiesen — OHNE Upload, mit Meldung', async () => {
  const s = await seite12b()
  await auswaehlen(s.host, [dateiEcht('riessig.jpg', T.ANHANG_MAX_BYTES + 1)])
  assert.equal(s.uploads.length, 0, 'kein Upload einer zu großen Datei')
  assert.equal(chiptexte(s.host).length, 0, 'und kein Chip')
  const meldung = s.host.querySelector('.dk-chat-fehler')
  assert.ok(meldung, 'es steht eine Meldung da')
  assert.match(meldung.textContent, /zu groß/)
  assert.match(meldung.textContent, /10 MB/)

  // Vier Dateien auf einmal: ebenfalls kein Upload.
  await auswaehlen(s.host, [
    dateiEcht('1.jpg', 100), dateiEcht('2.jpg', 100), dateiEcht('3.jpg', 100), dateiEcht('4.jpg', 100),
  ])
  assert.equal(s.uploads.length, 0, 'kein Upload bei mehr als drei')
  assert.match(s.host.querySelector('.dk-chat-fehler').textContent, /Es sind schon 3 Anhänge ausgewählt/)
  s.abbaum()
})

test('CHAT-12b/C: Senden schickt `anhaenge` mit den Kennungen — und leert die Liste', async () => {
  const s = await seite12b()
  await auswaehlen(s.host, [dateiEcht('probe.jpg', 2048)])
  assert.equal(chiptexte(s.host).length, 1)

  // Text dazu, dann senden (das Formular abschicken).
  const feld = s.host.querySelector('#chat-eingabe')
  assert.ok(feld, 'das Eingabefeld steht da')
  feld.value = 'Schau mal'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(3)
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }

  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.equal(senden.length, 1, 'genau EIN Sendeaufruf')
  assert.deepEqual(senden[0].parameter.anhaenge, ['CHAT-A-1'], 'die Kennung des fertigen Anhangs')
  assert.equal(senden[0].parameter.text, 'Schau mal')
  assert.equal(chiptexte(s.host).length, 0, 'nach dem Senden ist die Liste leer')
  s.abbaum()
})

test('CHAT-12b/C: „Foto ohne Worte“ — nur ein Anhang, kein Text, geht raus', async () => {
  const s = await seite12b()
  await auswaehlen(s.host, [dateiEcht('probe.jpg', 2048)])
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.equal(senden.length, 1, 'die Nachricht geht auch ohne Text hinaus')
  assert.deepEqual(senden[0].parameter.anhaenge, ['CHAT-A-1'])
  assert.equal(senden[0].parameter.text, '')
  s.abbaum()
})

test('CHAT-12b/C: Senden ist gesperrt, solange der Upload läuft', async () => {
  const s = await seite12b()
  // Der Upload hängt: die Antwort kommt erst, wenn der Test sie öffnet.
  let loese = null
  globalThis.__UPLOAD12B = () => new Promise((fertig) => {
    loese = fertig
    globalThis.__OFFENE12B.push(() => fertig({ name: 'CHAT-A-X' }))
  })
  const feld = s.host.querySelector('#chat-eingabe')
  feld.value = 'Schau mal'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(3)

  const dateiFeld = s.host.querySelector('input[type="file"]')
  Object.defineProperty(dateiFeld, 'files', { configurable: true, value: [dateiEcht('probe.jpg', 2048)] })
  dateiFeld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await warte(10)
  await rendern(3)

  assert.equal(s.uploads.length, 1, 'der Upload läuft')
  assert.match(chiptexte(s.host).join(' '), /wird hochgeladen/, 'der Chip sagt „lädt“')
  // Die Eingabezeile steht — während des Uploads wird sie NICHT durch den
  // Sperr-Hinweis ersetzt (gesperrt ist nur der Knopf).
  const form = s.host.querySelector('#chat-eingabe-form')
  assert.ok(form, 'die Eingabezeile steht während des Uploads')
  const knopf = form.querySelector('button[type="submit"]')
  assert.ok(knopf, 'der Sende-Knopf steht da')
  assert.equal(knopf.hasAttribute('disabled'), true, 'Senden ist gesperrt')

  // Ein Abschicken in dieser Lage schickt NICHTS.
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(6)
  await rendern(3)
  assert.equal(s.aufrufe.filter((a) => /\.senden$/.test(a.methode)).length, 0,
    'während des Uploads geht keine Nachricht hinaus')

  // Antwort freigeben: jetzt ist Senden wieder möglich.
  loese({ name: 'CHAT-A-1' })
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  assert.match(chiptexte(s.host).join(' '), /bereit/)
  const danach = s.host.querySelector('#chat-eingabe-form button[type="submit"]')
  assert.equal(danach.hasAttribute('disabled'), false, 'nach dem Upload ist Senden frei')
  s.abbaum()
})

test('CHAT-12b/C: 429 zeigt „Tageslimit für Anhänge erreicht“', async () => {
  const s = await seite12b()
  globalThis.__UPLOAD12B = async () => ({ __fehler: 'Zu viele Anhänge heute.', status: 429 })
  await auswaehlen(s.host, [dateiEcht('probe.jpg', 2048)])
  assert.equal(s.uploads.length, 1, 'der Versuch wurde gemacht')
  const chip = s.host.querySelector('.dk-chat-anhang-chip')
  assert.ok(chip, 'der Chip bleibt stehen (mit Begründung)')
  assert.match(chip.textContent, /ging nicht/)
  assert.match(chip.textContent, /Tageslimit für Anhänge erreicht/,
    'bei 429 der FESTE Satz, nicht der Servertext')
  s.abbaum()
})

test('CHAT-12b/C: Gesprächswechsel verwirft die späte Upload-Antwort', async () => {
  const s = await seite12b()
  // Der Upload hängt in CHAT-2.
  let loese = null
  globalThis.__UPLOAD12B = () => new Promise((fertig) => {
    loese = fertig
    globalThis.__OFFENE12B.push(() => fertig({ name: 'CHAT-A-X' }))
  })
  const dateiFeld = s.host.querySelector('input[type="file"]')
  Object.defineProperty(dateiFeld, 'files', { configurable: true, value: [dateiEcht('probe.jpg', 2048)] })
  dateiFeld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await warte(10)
  await rendern(3)
  assert.equal(s.uploads.length, 1)
  assert.equal(chiptexte(s.host).length, 1, 'der Chip steht noch in CHAT-2')

  // Wechsel in ein anderes Gespräch: die Seite lädt neu (erkennbar an der
  // zweiten Verlaufsabfrage), die Liste gehört zum GESPRÄCH.
  dom.window.location.hash = '#/nachrichten/CHAT-5'
  dom.window.dispatchEvent(new dom.window.HashChangeEvent('hashchange'))
  for (let i = 0; i < 15; i += 1) { await warte(8); await rendern(4) }
  assert.equal(chiptexte(s.host).length, 0, 'im neuen Gespräch steht kein Anhang des alten')
  assert.ok(s.aufrufe.some((a) => /\.verlauf$/.test(a.methode) && a.parameter?.gespraech === 'CHAT-5'),
    'die Seite steht wirklich in CHAT-5 (der Wechsel ist angekommen)')

  // Jetzt kommt die späte Antwort des ALTEN Laufs.
  loese({ name: 'CHAT-A-1' })
  for (let i = 0; i < 15; i += 1) { await warte(6); await rendern(3) }
  assert.equal(chiptexte(s.host).length, 0,
    'die späte Antwort trägt nichts mehr ein')

  // Und sie geht auch nicht als Anhang der nächsten Nachricht hinaus.
  const feld = s.host.querySelector('#chat-eingabe')
  feld.value = 'Hallo Runde'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(3)
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.equal(senden.length, 1)
  assert.equal(senden[0].parameter.gespraech, 'CHAT-5')
  assert.equal('anhaenge' in senden[0].parameter, false, 'der fremde Anhang reist NICHT mit')
  s.abbaum()
})

test('CHAT-12b/C: zwei Dateien gleichzeitig — beide werden bereit, Senden nimmt beide mit', async () => {
  const s = await seite12b()
  // Beide Uploads hängen; die Antworten kommen in UMGEKEHRTER Reihenfolge.
  const haengend = []
  globalThis.__UPLOAD12B = ({ nummer }) => new Promise((fertig) => {
    haengend.push({ nummer, fertig })
    globalThis.__OFFENE12B.push(() => fertig({ name: `CHAT-A-${nummer}` }))
  })
  const dateiFeld = s.host.querySelector('input[type="file"]')
  Object.defineProperty(dateiFeld, 'files', {
    configurable: true,
    value: [dateiEcht('a.jpg', 2048), dateiEcht('b.jpg', 4096)],
  })
  dateiFeld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await warte(10)
  await rendern(4)
  assert.equal(s.uploads.length, 2, 'beide Dateien gehen sofort hoch')
  assert.equal(chiptexte(s.host).length, 2, 'zwei Chips')
  assert.match(chiptexte(s.host).join(' | '), /wird hochgeladen/)
  const knopfVorher = s.host.querySelector('#chat-eingabe-form button[type="submit"]')
  assert.equal(knopfVorher.hasAttribute('disabled'), true, 'Senden ist gesperrt, solange etwas lädt')

  // Antwort der ZWEITEN zuerst — das darf den ersten Chip NICHT entwerten.
  haengend[1].fertig({ name: 'CHAT-A-B' })
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const zwischen = chiptexte(s.host)
  assert.equal(zwischen.filter((t) => /bereit/.test(t)).length, 1, 'ein Chip ist fertig')
  assert.equal(zwischen.filter((t) => /wird hochgeladen/.test(t)).length, 1,
    'der andere lädt NOCH (seine Antwort ist nicht untergegangen)')

  haengend[0].fertig({ name: 'CHAT-A-A' })
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const alle = chiptexte(s.host)
  assert.equal(alle.length, 2)
  assert.equal(alle.filter((t) => /bereit/.test(t)).length, 2, 'BEIDE sind bereit')
  const knopfNachher = s.host.querySelector('#chat-eingabe-form button[type="submit"]')
  assert.equal(knopfNachher.hasAttribute('disabled'), false, 'Senden ist frei')

  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.equal(senden.length, 1, 'die Nachricht geht auch ohne Text hinaus')
  assert.deepEqual([...senden[0].parameter.anhaenge].sort(), ['CHAT-A-A', 'CHAT-A-B'],
    'beide Kennungen reisen mit')
  s.abbaum()
})

test('CHAT-12b/C: zwei Dateien mit demselben Namen bleiben zwei Chips', async () => {
  const s = await seite12b()
  // Die Antworten tragen bewusst KEINEN Dateinamen — der Chip behält seinen.
  globalThis.__UPLOAD12B = async ({ nummer }) => ({ name: `CHAT-A-${nummer}` })
  const dateiFeld = s.host.querySelector('input[type="file"]')
  const eins = dateiEcht('gleich.jpg', 2048)
  const zwei = dateiEcht('gleich.jpg', 2048)
  Object.defineProperty(dateiFeld, 'files', { configurable: true, value: [eins, zwei] })
  dateiFeld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  assert.equal(s.uploads.length, 2, 'beide werden hochgeladen')
  const chips = chiptexte(s.host)
  assert.equal(chips.length, 2, 'zwei Chips — der zweite ist nicht am gleichen Schlüssel verschwunden')
  assert.equal(chips.filter((t) => /bereit/.test(t)).length, 2, 'beide sind bereit')
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.deepEqual(senden[0].parameter.anhaenge, ['CHAT-A-1', 'CHAT-A-2'], 'beide Kennungen gehen mit')
  s.abbaum()
})

test('CHAT-12b/C: gescheiterte Chips sperren die nächste Auswahl nicht', async () => {
  const s = await seite12b()
  // Jeder Upload scheitert mit 429.
  globalThis.__UPLOAD12B = async () => ({ __fehler: 'Zu viele Anhänge heute.', status: 429 })
  for (let i = 0; i < 3; i += 1) {
    await auswaehlen(s.host, [dateiEcht(`fehler${i}.jpg`, 1024)])
  }
  assert.equal(s.uploads.length, 3, 'drei Versuche, drei Fehlschläge')
  assert.equal(chiptexte(s.host).length, 3)
  assert.equal(chiptexte(s.host).filter((t) => /Tageslimit/.test(t)).length, 3)

  // Trotzdem darf eine neue Datei es versuchen (Fehler belegen keinen Platz).
  globalThis.__UPLOAD12B = async ({ nummer }) => ({ name: `CHAT-A-${nummer}` })
  await auswaehlen(s.host, [dateiEcht('klappt.jpg', 1024)])
  assert.equal(s.uploads.length, 4, 'die neue Datei wird hochgeladen — nicht grundlos abgewiesen')
  assert.equal(chiptexte(s.host).filter((t) => /klappt\.jpg.*bereit/.test(t)).length, 1,
    'die neue Datei ist bereit')
  // Senden nimmt nur die fertige Kennung mit.
  s.host.querySelector('#chat-eingabe-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
  const senden = s.aufrufe.filter((a) => /\.senden$/.test(a.methode))
  assert.deepEqual(senden[0].parameter.anhaenge, ['CHAT-A-4'])
  s.abbaum()
})

test('CHAT-12b/C: Entfernen nimmt den Chip aus der Liste (kein weiterer Aufruf)', async () => {
  const s = await seite12b()
  await auswaehlen(s.host, [dateiEcht('probe.jpg', 2048)])
  assert.equal(chiptexte(s.host).length, 1)
  const vorher = s.aufrufe.length
  const weg = s.host.querySelector('.dk-chat-anhang-chip-weg')
  assert.ok(weg, 'der Entfernen-Knopf steht am Chip')
  assert.match(weg.getAttribute('aria-label'), /Anhang entfernen: probe\.jpg/,
    'mit Dateinamen im aria-label (Karte Punkt 4)')
  klick(weg)
  for (let i = 0; i < 8; i += 1) { await warte(6); await rendern(3) }
  assert.equal(chiptexte(s.host).length, 0, 'der Chip ist weg')
  assert.equal(s.aufrufe.length, vorher, 'kein Löschaufruf — der Server räumt selbst auf')
  s.abbaum()
})

test('CHAT-12b/C: der Verlauf zeigt Anhänge an der Nachricht (Bild mit richtiger URL)', async () => {
  const s = await seite12b({
    verlauf: [zeile('N-1', {
      text: 'Schau mal',
      anhaenge: [{ name: 'CHAT-A-7', dateiname: 'probe.jpg', mime: 'image/jpeg', groesse: 2048 }],
    })],
  })
  const bild = s.host.querySelector('.dk-chat-verlaufsliste .dk-chat-anhaenge-blase img')
  assert.ok(bild, 'der Verlauf zeigt die Vorschau')
  assert.equal(bild.getAttribute('src'), '/diakonos/api/method/chat.anhang?name=CHAT-A-7')
  assert.equal(bild.getAttribute('alt'), 'probe.jpg')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Die Wechsel-Prüfung selbst (Review R1/M1)
// ════════════════════════════════════════════════════════════════════════════
//
// Durch die Seite ist der Gesprächswechsel NICHT prüfbar: die Testumgebung
// (jsdom) führt keine Navigation aus — ein `location.hash`-Wechsel baut die
// Seite nicht neu auf (nachgeprüft: die Instanz und ihre Refs bleiben
// dieselben). Die Prüfung „gehört diese Antwort noch hierher?“ steht deshalb
// als eigene, benannte Funktion in `components/chat/anhaenge.mjs`
// (`anhangAntwortGilt`) und wird hier EINZELN geprüft — eine Mutation macht
// diesen Test nachweislich rot.

test('CHAT-12b/D: eine Antwort gilt nur im eigenen Gespräch und nur bei gültiger Laufnummer', () => {
  const gilt = T.anhangAntwortGilt
  assert.equal(typeof gilt, 'function', 'die Prüfung ist einzeln prüfbar')

  const lauf = T.uploadLauf()
  const nummer = lauf.neu()
  const chip = T.chipBauen(datei('probe.jpg', 2048), { lauf: nummer, gespraech: 'CHAT-2', id: 'anhang-1' })

  // Normalfall: dasselbe Gespräch, Laufnummer gilt → die Antwort darf schreiben.
  assert.equal(gilt(chip, { nummer, gespraech: 'CHAT-2', gilt: lauf.gilt }), true)

  // Gesprächswechsel: der Chip gehört zu CHAT-2, offen ist CHAT-5.
  assert.equal(gilt(chip, { nummer, gespraech: 'CHAT-5', gilt: lauf.gilt }), false,
    'die Antwort des alten Gesprächs trägt im neuen nichts ein')

  // Laufnummer entwertet (der Wechsel hat `abbrechen` gerufen): selbst wenn die
  // Adresse zufällig wieder dieselbe ist, gilt sie nicht mehr.
  lauf.abbrechen()
  assert.equal(gilt(chip, { nummer, gespraech: 'CHAT-2', gilt: lauf.gilt }), false,
    'eine entwertete Laufnummer gilt nicht')

  // Zwei gleichzeitige Uploads desselben Gesprächs: beide gelten (S1).
  const lauf2 = T.uploadLauf()
  const n1 = lauf2.neu()
  const n2 = lauf2.neu()
  const a = T.chipBauen(datei('a.jpg', 10), { lauf: n1, gespraech: 'CHAT-2', id: 'anhang-2' })
  const b = T.chipBauen(datei('b.jpg', 10), { lauf: n2, gespraech: 'CHAT-2', id: 'anhang-3' })
  assert.equal(gilt(a, { nummer: n1, gespraech: 'CHAT-2', gilt: lauf2.gilt }), true)
  assert.equal(gilt(b, { nummer: n2, gespraech: 'CHAT-2', gilt: lauf2.gilt }), true,
    'der zweite Upload entwertet den ersten nicht')
})
