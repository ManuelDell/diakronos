/**
 * „Kalender verwalten“ in der Kalenderliste — je Rolle und je Serverantwort.
 *
 * Der Aufbau der Leiste (`onMounted` aus `KronosSidebar.vue`) wird im
 * VM-Kontext ausgeführt; die importierten Funktionen und der geteilte
 * Ladestand werden hereingereicht.
 *
 * UI-R3: Der Import bleibt bei der Admin-Rolle; „Verwalten“ gilt zusätzlich
 * für alle, denen der Server Kalender zum Anlegen gibt.
 *
 * UI-R3c: Der Endpunkt kommt aus dem geteilten Stand
 * (`composables/useKalenderVerwaltung.js`) — die Leiste ruft ihn nicht mehr
 * selbst. Und es gibt KEINEN Rollen-Rückfall: ohne Serverantwort steht der
 * Eintrag auch für einen Administrator nicht (fail closed, kein Flackern).
 *
 * UI-R3e (MUSS 2 / SOLL 7): Die Leiste lädt gar nicht mehr — sie liest den
 * reaktiven Stand. Geprüft wird deshalb der ECHTE geteilte Lader (nicht ein
 * Ersatz): der Aufbau der Leiste darf `get_kalender_verwaltung` NICHT rufen,
 * und der 403-/Netz-Pfad muss über ihn zum verborgenen Eintrag führen.
 *
 * UI-R3f (Punkt 4): Der Rollen-Test setzte `zeigeVerwalten` SELBST und prüfte
 * damit nur eine Tautologie (`kalenderVerwaltungSichtbar(stand) === sichtbar`).
 * Jetzt wird die Leiste mit dem geteilten Stand GEMOUNTET und im gerenderten
 * Template geprüft, ob „Kalender verwalten“ wirklich dasteht — inklusive des
 * 403-Falls für ein einfaches Mitglied.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(hier, '..', 'src', 'diakonos')
const source = fs.readFileSync(join(SRC, 'components', 'kronos', 'KronosSidebar.vue'), 'utf8')
const mounted = source.match(/onMounted\(([\s\S]*?)\);\s*<\/script>/)[1]
const { istKalenderAdmin, kalenderVerwaltungSichtbar } = await import('../src/diakonos/components/kronos/kalenderRechte.mjs')

/** Zählt die Aufrufe des Endpunkts (die Leiste selbst darf keinen auslösen). */
const aufrufe = []
const ersatzApi = async (methode) => {
  aufrufe.push(methode)
  return { kalender: [] }
}

// ── jsdom + Vue für den GEMOUNTETEN Fall ──────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'MouseEvent',
  'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement', 'HTMLButtonElement',
  'requestAnimationFrame', 'getComputedStyle', 'MutationObserver', 'localStorage',
  'sessionStorage', 'NodeList', 'KeyboardEvent', 'Document', 'ShadowRoot']) {
  if (dom.window[k] !== undefined) globalThis[k] = dom.window[k]
}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
})

/** Der geteilte Lader — Aufrufe zählen, sonst nichts. */
let standAntwort = null
let standFehler = null
globalThis.__googleSidebarStand = async () => {
  aufrufe.push('get_kalender_verwaltung')
  if (standFehler) throw standFehler
  return standAntwort
}

const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'gsidebar-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
const ERSATZ = new Map([
  ['@event-calendar/build', 'export default {}'],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
])
function fremdesModul(spec) {
  if (!ERSATZ.has(spec)) return null
  const datei = resolve(TMP, 'ersatz-' + spec.replace(/[^a-z0-9]+/gi, '-') + '.mjs')
  if (!cache.has(datei)) {
    writeFileSync(datei, ERSATZ.get(spec) + '\n')
    cache.set(datei, datei)
  }
  return datei
}
function uebersetze(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename.replace(/\W/g, '_') })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename.replace(/\W/g, '_'),
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (/^vue/.test(spec)) return `from '${VUE_URL}'`
    if (!spec.startsWith('.')) {
      const ersatz = fremdesModul(spec)
      return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
    }
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const ziel = resolve(TMP, filename.replace(/\.\w+$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const satzJetzt = () => globalThis.__letzterSatz
const warte = async (n = 30) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Die ECHTE Leiste mit dem ECHTEN geteilten Stand mounten. */
/** Den geteilten Stand MIT Antwort füllen — der Weg des Besitzers (Satz + Ladung). */
async function standFuellen(geteilt) {
  if (!standFehler && !standAntwort) return
  globalThis.__letzterSatz = geteilt.aktuellerSatz()
  await geteilt.laden()
  await new Promise((l) => setTimeout(l, 0))
}

async function leisteMounten() {
  const geteilt = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  geteilt.__leeren()
  geteilt.__setzeApiAufruf(() => globalThis.__googleSidebarStand())
  // UI-R3g: Die Leiste zeigt „Verwalten“ nur mit der Antwort DIESES Besuchs —
  // die Antwort entsteht deshalb VOR dem Aufbau, wie auf der Kalenderseite.
  await standFuellen(geteilt)
  const Leiste = (await import('file://' + uebersetze(join(SRC, 'components', 'kronos', 'KronosSidebar.vue')) + '?t=' + Date.now())).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Leiste }, template: '<Leiste :open="false" />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte()
  return { host, app, geteilt, meldungen }
}

/** Der Eintrag „Kalender verwalten“ als gerenderter Knopf (oder null). */
const verwaltenKnopf = (host) => [...host.querySelectorAll('button, a')]
  .find((el) => /^\s*Kalender verwalten\s*$/.test(el.textContent || ''))

for (const [roles, serverAntwort, sichtbar, warum] of [
  // UI-R3c: Admin-Rollen OHNE Serverantwort → KEIN Eintrag mehr (früher true).
  [['Kalenderadministrator'], null, false, 'ohne Serverantwort kein Eintrag (kein Rollen-Rückfall)'],
  [['Administrator'], null, false, 'ohne Serverantwort kein Eintrag (kein Rollen-Rückfall)'],
  [['System Manager'], null, false, 'ohne Serverantwort kein Eintrag'],
  [['Kalenderadministrator'], { kalender: [{ name: 'Gemeinde' }] }, true, 'Admin mit Serverantwort'],
  [['Mitglied'], { kalender: [], anlegen_gruppen: [] }, false, 'nichts zu verwalten'],
  // UI-R3: eine Gruppenleitung darf anlegen, obwohl sie keine Admin-Rolle hat.
  [['Mitglied'], { kalender: [], anlegen_gruppen: ['G-Chor'], darf_gemeinde_kalender: false }, true,
    'GL darf anlegen'],
]) {
  // Import bleibt bei der Admin-Rolle (unabhängig von der Serverantwort).
  const importSichtbar = ['Kalenderadministrator', 'Administrator']
    .some((r) => roles.includes(r))
  test(`sidebar: ${roles.join(',')} — ${warum}`, async () => {
    aufrufe.length = 0
    // Der geteilte Lader lebt zwischen den Fällen weiter — erst den Zustand
    // dieses Falls setzen (sonst trägt der nächste Fall die Antwort des vorigen).
    standAntwort = null
    standFehler = null
    // UI-R3e: Der GETROFFENE geteilte Stand — die Leiste liest `verwaltung`
    // (readonly-Ref), sie fragt nicht.
    const stand = { verwaltung: serverAntwort }
    const context = {
      window: {},
      showImport: { value: false },
      geteilteVerwaltung: { value: serverAntwort },
      // K-A: die Liste der eigenen abgelehnten Termine — der Aufbau der Leiste
      // darf davon nicht abhängen. Der Rumpf ruft `ladeAbgelehnteTermine`.
      abgelehnteTermine: { value: [] },
      ladeAbgelehnteTermine: async () => {},
      // Punkt 7: die gemeinsame Rollenprüfung (Import der Komponente).
      istKalenderAdmin,
      kalenderVerwaltungSichtbar,
      // UI-R3f (Punkt 4): KEIN selbst gesetztes `zeigeVerwalten` mehr — der
      // Wert der Vorlage entsteht aus `geteilteVerwaltung` und wird unten im
      // GERENDERTEN Template geprüft.
      apiCall: async (method) => {
        assert.equal(method, 'diakronos.diakonos.api.session.get_current_user_context')
        return { roles, user: '' }
      },
    }
    vm.createContext(context)
    await vm.runInContext(`(${mounted})()`, context)
    assert.deepEqual(aufrufe, [], 'der Aufbau der Leiste fragt den Endpunkt selbst (kein zweiter Besitzer)')
    assert.doesNotMatch(mounted, /ladenKalenderVerwaltung/,
      'die Leiste lädt die Verwaltung noch selbst statt sie zu lesen')
    assert.equal(mounted.includes('zeigeVerwalten.value ='), false,
      '„Verwalten“ wird noch als einmaliger Wert gesetzt statt abgeleitet')
    assert.equal(context.showImport.value, importSichtbar,
      'Import hängt weiter an der Admin-Rolle')

    // Und jetzt das ECHTE Bild: Leiste mit dem geteilten Stand mounten.
    aufrufe.length = 0
    standAntwort = serverAntwort
    standFehler = null
    const { host, meldungen, geteilt } = await leisteMounten()
    assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
    if (serverAntwort) {
      await warte(10)
    }
    const knopf = verwaltenKnopf(host)
    assert.equal(Boolean(knopf), sichtbar,
      `„Kalender verwalten“ ${sichtbar ? 'fehlt' : 'steht'} im gerenderten Bild: `
        + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
    // Der Eintrag der Vorlage ist die Aussage der gemeinsamen Regel — hier
    // NICHT selbst gesetzt, sondern aus dem Stand abgeleitet.
    assert.equal(kalenderVerwaltungSichtbar(stand.verwaltung), sichtbar,
      'die gemeinsame Regel sagt etwas anderes als das gerenderte Bild')
    geteilt.__setzeApiAufruf(null)
    await warte(4)
  })
}

test('sidebar: 403 für ein einfaches Mitglied — „Kalender verwalten“ fehlt im Bild', async () => {
  // UI-R3f (Punkt 4): der 403-Fall wird ebenfalls GEMOUNTET geprüft, nicht als
  // Regel-Tautologie. Die Vorbedingung (ein Mitglied, das vorher den Eintrag
  // hatte) wird über den echten Lader gesetzt — fail closed nimmt ihn wieder weg.
  aufrufe.length = 0
  standAntwort = null
  standFehler = Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 })
  const { host, meldungen, geteilt } = await leisteMounten()
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))


  // Vorbedingung: mit Recht steht der Eintrag (der Stand kommt aus einer
  // gewöhnlichen Ladung des Besitzers; `standFehler` gilt erst danach).
  standFehler = null
  standAntwort = { kalender: [{ name: 'Gemeinde' }] }
  await standFuellen(geteilt)
  await new Promise((l) => setTimeout(l, 20))
  await warte(10)
  assert.ok(verwaltenKnopf(host), 'Vorbedingung: der Eintrag fehlt trotz Recht')

  // Jetzt der 403 des Servers über den ECHTEN geteilten Lader.
  aufrufe.length = 0
  standAntwort = null
  standFehler = Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 })
  geteilt.aktuellerSatz()
  const ergebnis = await geteilt.laden()
  await warte(20)
  assert.equal(ergebnis, null, '403: laden() gibt keinen Stand')
  assert.equal(geteilt.useKalenderVerwaltung().sperrt.value, true, 'der Lader kennt die Sperre nicht')
  assert.equal(verwaltenKnopf(host), undefined,
    'der Eintrag „Kalender verwalten“ steht nach dem 403 noch im Bild: '
      + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  assert.equal(aufrufe.filter((m) => m === 'get_kalender_verwaltung').length, 1,
    'genau EINE Anfrage der frischen Ladung erwartet')
  geteilt.__leeren()
  geteilt.__setzeApiAufruf(null)
})

test('sidebar: 403 und Netzfehler über den ECHTEN geteilten Lader — kein Eintrag (fail closed, alt)', async () => {
  const geteilt = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  for (const [antwort, warum] of [
    [Object.assign(new Error('gesperrt'), { status: 403 }), '403 des Servers'],
    [new Error('Netz weg'), 'Netzfehler'],
  ]) {
    geteilt.__leeren()
    geteilt.__setzeApiAufruf(async () => { throw antwort })
    const stand = await geteilt.laden({ frisch: true })
    assert.equal(stand, null, warum + ': laden() gibt keinen Stand')
    // Die Vorlage der Leiste liest `verwaltung` — daraus wird der Eintrag.
    assert.equal(kalenderVerwaltungSichtbar(geteilt.useKalenderVerwaltung().verwaltung.value), false,
      warum + ': der Eintrag „Kalender verwalten“ bliebe stehen')
  }
  geteilt.__leeren()
  geteilt.__setzeApiAufruf(null)
})
