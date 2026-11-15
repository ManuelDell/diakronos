/**
 * UI-R2e — Kalender der Gruppe: der 500-Fehler und das Aufblitzen bei 403.
 *
 * Folgekarte zu UI-R2d. Gemessen wird am ECHTEN Baum (jsdom, API gestubbt) —
 * nicht am Quelltext:
 *
 *   E1  500 aus `get_kalender_verwaltung`: der Inhalt der Karte (DkEmpty
 *       „Kalender nicht geladen“ + „Erneut versuchen“) ist WIRKLICH sichtbar,
 *       also in der Vorfahrenkette ohne `display:none`. Vorher meldete der
 *       Baustein bei jedem Fehler „keine Antwort da“, die Fläche blieb
 *       `v-show`-versteckt und der Hinweis war nie zu sehen.
 *   E2  Kein Aufblitzen: die GANZE Karte (DkCard „Kalender der Gruppe“, also
 *       Titel UND Rahmen) bleibt unsichtbar, bis die erste Antwort da ist —
 *       bei 403 danach für immer, bei 200 und 500 erscheint sie. Das Kind
 *       bleibt dabei GEMOUNTET (`display:none`, kein `v-if`), sonst lädt
 *       niemand und die Antwort käme nie an.
 *   E3  Derselbe Reset beim Gruppenwechsel — an DERSELBEN Instanz gemessen
 *       (Adresse/Gruppenkennung ändern, kein neues Mounten).
 *   E4  „Gruppe freigeben“ ist gesperrt, solange `busy` gesetzt ist (auch
 *       während einer FREMDEN Aktion) — sonst ginge die Anfrage still
 *       verloren.
 *   E5  Die Gruppenfreigabe bleibt bei einem Fehlschlag stehen und wird bei
 *       Erfolg geleert.
 *
 * Lauf: TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir2e-mount.test.mjs
 *       (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')

// ── jsdom zuerst, dann Vue ────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot', 'HTMLButtonElement', 'sessionStorage', 'localStorage',
  'Location', 'History', 'PopStateEvent', 'HashChangeEvent', 'Navigator', 'NodeList']) {
  if (dom.window[schluessel] !== undefined) globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)

const { HANDY_LAGE_ABFRAGE } = await import('../src/diakonos/composables/handyLageAbfrage.mjs')
function matchMediaNachbau(abfrage) {
  return {
    media: String(abfrage),
    matches: String(abfrage) !== HANDY_LAGE_ABFRAGE,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
  }
}
Object.defineProperty(globalThis.window, 'matchMedia', { configurable: true, value: matchMediaNachbau })
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })

// ── API-Attrappe ──────────────────────────────────────────────────────────
/**
 * `antworten` bildet Methodenmuster auf eine ANTWORT ab. Ein Promise als Wert
 * wird NICHT aufgelöst, bevor der Test es freigibt — so lässt sich die erste
 * Antwort zurückhalten („die Antwort schwebt noch“) und danach genau der
 * Zustandswechsel messen, der vorher aufblitzte.
 */
const aufrufe = []
let antworten = {}

globalThis.__uiR2eMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(antworten)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_kalender_verwaltung$/.test(methode)) {
    return {
      kalender: [{ name: 'Proben', titel: 'Proben', farbe: '#2266aa',
        gruppe: 'G-Chor', untergruppe: null, standard_gruppe_lesen: true,
        gemeinde_status: 'aus', gruppe_status: 'aus' }],
      darf_gemeinde_kalender: false, anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [],
    }
  }
  if (/get_gruppe_detail$/.test(methode)) return gruppe(gruppeKennung)
  if (/get_objekt_rechte$/.test(methode)) {
    return {
      typ: 'kalender', objekt: 'Proben', gruppe: 'G-Chor', untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
      darf_moderieren_vergeben: false,
      freigaben: [{ benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel',
        lesen: true, schreiben: false, moderieren: false }],
    }
  }
  return { success: true }
}

/** Die Serverantwort von `get_gruppe_detail` für eine Gruppenkennung. */
let gruppeKennung = 'G-Chor'
function gruppe(name) {
  return {
    gruppe: { name, gruppenname: name === 'G-Band' ? 'Band' : 'Chor', dienstbereich: 'DB-1' },
    untergruppe: null, mitglieder: [], verantwortliche: [],
    rechte: { verwalten: true, rollen: true },
    untergruppen: [],
  }
}

// ── SFC-Übersetzer (Muster wie tests/uir2c-mount.test.mjs) ────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir2e-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR2eMock(methode, args)\n'
  + 'export default { apiCall }\n')

function uebersetze(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (/^vue/.test(spec)) return `from '${VUE_URL}'`
    if (/composables\/useApi/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(() => {
  for (const el of [...document.body.querySelectorAll('[data-uir2e-host], .dk-ui-dialog-overlay')]) el.remove()
})

const warte = async (n = 16) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

// ══════════════════════════════════════════════════════════════════════════
// Sichtbarkeit messen — `textContent` enthält auch VERSTECKTEN Text
// ══════════════════════════════════════════════════════════════════════════

/**
 * Steht das Element WIRKLICH im Bild? Geprüft wird die ganze Vorfahrenkette
 * bis zum Host: `display:none` an sich selbst oder einem Vorfahren genügt,
 * um es unsichtbar zu machen. `textContent` allein genügt NICHT — genau davon
 * lebte das Aufblitzen (die Fläche stand im Baum, war aber `v-show`-versteckt).
 */
function sichtbar(el, wurzel) {
  if (!el) return false
  for (let knoten = el; knoten && knoten !== wurzel?.parentElement; knoten = knoten.parentElement) {
    if (knoten.nodeType !== 1) continue
    if (knoten.style && knoten.style.display === 'none') return false
    if (knoten.hasAttribute && knoten.hasAttribute('hidden')) return false
  }
  return true
}

/** Die DkCard „Kalender der Gruppe“ — nur die KARTE zählt (Titel + Fläche). */
function kalenderKarte(host) {
  return [...host.querySelectorAll('section.dk-ui-card')]
    .find((k) => (k.querySelector('h2.dk-ui-card-titel')?.textContent || '').trim() === 'Kalender der Gruppe')
}

const kartenTitel = (host) => [...host.querySelectorAll('h2.dk-ui-card-titel')]
  .map((h) => h.textContent.trim())

/** Steht die Karte „Kalender der Gruppe“ sichtbar im Bild? */
const karteSichtbar = (host) => sichtbar(kalenderKarte(host), host)

/** Mountet die ECHTE Seite `pages/GruppeDetail.vue` auf `#/gruppe/<id>/einstellungen`. */
async function seiteMounten({ antworten: gesetzt = {}, gruppeId = 'G-Chor' } = {}) {
  aufrufe.length = 0
  antworten = gesetzt
  gruppeKennung = gruppeId
  globalThis.window.__DIakonosBOOT = { roles: [], devmode: false, user: { email: 'ruth.hv@example.org' } }
  document.body.innerHTML = ''
  // Der Router liest die Adresse über `acceptedRoute`; ein Hash aus dem
  // vorigen Test darf nicht nachwirken.
  window.location.hash = `#/gruppe/${gruppeId}/einstellungen`
  await warte(2)
  window.dispatchEvent(new Event('hashchange'))
  await warte(2)
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2e-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(40)
  return { host, app, meldungen }
}

/**
 * Eine zurückgehaltene Antwort: `freigeben()` löst sie auf, `fehlschlagen()`
 * lässt sie mit dem gegebenen Fehler platzen. Bis dahin hängt der Aufruf.
 */
function schleuse() {
  let oeffnen, schliessen
  const versprechen = new Promise((ja, nein) => { oeffnen = ja; schliessen = nein })
  return {
    versprechen,
    freigeben: (wert) => { oeffnen(wert) },
    fehlschlagen: (fehler) => { schliessen(fehler) },
  }
}

const VERWALTUNG = {
  kalender: [{ name: 'Proben', titel: 'Proben', farbe: '#2266aa', gruppe: 'G-Chor',
    untergruppe: null, standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' }],
  darf_gemeinde_kalender: false, anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [],
}

// ══════════════════════════════════════════════════════════════════════════
// E1 · 500: der Hinweis ist WIRKLICH sichtbar
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2e/E1: bei 500 sind „Kalender nicht geladen“ und „Erneut versuchen“ sichtbar', async () => {
  // BEFUND UI-R2d: `KalenderEinstellungen.verwaltungLaden` rief im catch-Zweig
  // `emit('gesperrt', false, false)` — also „keine Antwort da“. Die Seite hielt
  // den Inhalt per `v-show` versteckt, das DkEmpty stand nur im Quelltext.
  // Der alte Test las `host.textContent` und war deshalb grün.
  const { host, meldungen } = await seiteMounten({
    antworten: { 'get_kalender_verwaltung$': Object.assign(new Error('HTTP 500'), { status: 500 }) },
  })
  assert.ok(aufrufe.some(([m]) => /get_kalender_verwaltung$/.test(m)),
    'Vorbedingung: die Verwaltung wurde nicht geladen | ' + meldungen.slice(0, 2).join(' | '))
  assert.ok(karteSichtbar(host),
    'die Karte „Kalender der Gruppe“ ist bei einem 500 unsichtbar | Karten: ' + kartenTitel(host).join(' | '))

  // Der Hinweis steht im Baum …
  assert.ok(host.textContent.includes('Kalender nicht geladen'), 'der Hinweis-Text fehlt ganz')

  // … und ist SICHTBAR: genau das war vorher falsch. NICHT über `textContent`
  // geprüft — der enthält auch versteckten Text.
  const flaeche = host.querySelector('[data-kalender-flaeche]')
  assert.ok(flaeche, 'die Kalenderfläche fehlt')
  assert.ok(sichtbar(flaeche, host),
    'die Kalenderfläche bleibt nach dem 500 versteckt (display: ' + JSON.stringify(flaeche.style.display) + ')')
  const titelzeile = [...flaeche.querySelectorAll('*')]
    .find((el) => el.children.length === 0 && /Kalender nicht geladen/.test(el.textContent))
  assert.ok(titelzeile, 'die Überschrift „Kalender nicht geladen“ fehlt in der Fläche')
  assert.ok(sichtbar(titelzeile, host), 'die Überschrift „Kalender nicht geladen“ ist unsichtbar')

  const erneut = [...host.querySelectorAll('button')]
    .find((b) => /Erneut versuchen/.test(b.textContent.trim()))
  assert.ok(erneut, 'der Knopf „Erneut versuchen“ fehlt')
  assert.ok(sichtbar(erneut, host), 'der Knopf „Erneut versuchen“ steht im Baum, ist aber unsichtbar')
})

test('UI-R2e/E1: Gegenprobe — bei 200 ist der Hinweis NICHT da (kein Dauersatz)', async () => {
  const { host } = await seiteMounten()
  assert.ok(karteSichtbar(host), 'die Karte fehlt ohne Fehler')
  const flaeche = host.querySelector('[data-kalender-flaeche]')
  assert.ok(flaeche && sichtbar(flaeche, host), 'die Kalenderfläche ist ohne Fehler versteckt')
  assert.ok(!host.textContent.includes('Kalender nicht geladen'),
    'der Fehlersatz steht auch bei 200 in der Fläche')
})

// ══════════════════════════════════════════════════════════════════════════
// E2 · Kein Aufblitzen: die GANZE Karte wartet auf die erste Antwort
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2e/E2: solange die Antwort schwebt, ist der Kartentitel NICHT sichtbar', async () => {
  // BEFUND UI-R2d: die Karte selbst stand sofort (nur ihr INHALT war
  // `v-show`-versteckt). Bei 403 blitzte Titel + Rahmung kurz auf und
  // verschwand wieder. Gemessen wird der KARTENTITEL — nicht die Fläche.
  const tor = schleuse()
  const { host, meldungen } = await seiteMounten({
    antworten: { 'get_kalender_verwaltung$': tor.versprechen },
  })
  assert.ok(aufrufe.some(([m]) => /get_kalender_verwaltung$/.test(m)),
    'Vorbedingung: die Karte hat die Verwaltung nicht geladen | ' + meldungen.slice(0, 2).join(' | '))

  // 1. Die Antwort schwebt noch: der Titel steht NICHT im Bild …
  assert.equal(karteSichtbar(host), false,
    'der Kartentitel „Kalender der Gruppe“ ist sichtbar, bevor eine Antwort da ist — das ist das Aufblitzen'
      + ' | Karten: ' + kartenTitel(host).join(' | '))
  // … und das Kind ist trotzdem GEMOUNTET (sonst lädt niemand, s. nächste Prüfung).
  assert.deepEqual(meldungen.filter((m) => m.startsWith('err:')), [],
    'das Zurückhalten der Antwort hat einen Fehler ausgelöst: ' + meldungen.slice(0, 3).join(' | '))

  // 2. Antwort freigeben (200): jetzt steht die Karte.
  tor.freigeben(VERWALTUNG)
  await warte(20)
  assert.equal(karteSichtbar(host), true, 'die Karte erscheint auch mit Antwort nicht')
  assert.ok(sichtbar(host.querySelector('[data-kalender-flaeche]'), host),
    'die Kalenderfläche bleibt nach der Antwort versteckt')
})

test('UI-R2e/E2: bei 403 bleibt die Karte weg — vorher war sie unsichtbar, nicht abwesend', async () => {
  const tor = schleuse()
  const { host } = await seiteMounten({ antworten: { 'get_kalender_verwaltung$': tor.versprechen } })
  assert.equal(karteSichtbar(host), false, 'Vorbedingung: die Karte ist schon vor der Antwort sichtbar')
  tor.fehlschlagen(Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 }))
  await warte(20)
  assert.equal(karteSichtbar(host), false,
    'die Karte „Kalender der Gruppe“ steht nach einem 403 im Bild: ' + kartenTitel(host).join(' | '))
  // Die Schwester-Karte bleibt (es geht nur um die Kalenderkarte).
  assert.ok(kartenTitel(host).includes('Rollen der Gruppe'),
    'die Rollen-Karte ist mit verschwunden: ' + kartenTitel(host).join(' | '))
})

test('UI-R2e/E2: bei 500 WAR die Karte unsichtbar und erscheint mit der Antwort', async () => {
  // Der 500 ist keine Lage, sondern ein Fehler mit Hinweis: die Karte muss
  // kommen — aber erst mit der Antwort, nicht vorher.
  const tor = schleuse()
  const { host } = await seiteMounten({ antworten: { 'get_kalender_verwaltung$': tor.versprechen } })
  assert.equal(karteSichtbar(host), false, 'Vorbedingung: die Karte ist schon vor der Antwort sichtbar')
  tor.fehlschlagen(Object.assign(new Error('HTTP 500'), { status: 500 }))
  await warte(20)
  assert.equal(karteSichtbar(host), true, 'die Karte fehlt nach dem 500 — der Hinweis ist nirgends zu sehen')
  const flaeche = host.querySelector('[data-kalender-flaeche]')
  assert.ok(sichtbar(flaeche, host), 'die Fläche mit dem Hinweis bleibt versteckt')
})

test('UI-R2e/E2: das Kind bleibt während der schwebenden Antwort gemountet', async () => {
  // Ohne das Kind im Baum lädt niemand — die Karte bliebe für immer leer.
  // Nachweis: die Verwaltung WIRD gerufen, obwohl die Karte unsichtbar ist,
  // und ihre Antwort kommt an (siehe E2 oben). Hier zusätzlich: die Fläche
  // steht im Baum, nur eben ohne Anzeige.
  const tor = schleuse()
  const { host } = await seiteMounten({ antworten: { 'get_kalender_verwaltung$': tor.versprechen } })
  const karte = kalenderKarte(host)
  assert.ok(karte, 'die Karte steht während der schwebenden Antwort NICHT im Baum — dann lädt das Kind nie')
  assert.equal(karte.style.display, 'none',
    'die Karte wird nicht über `display:none` versteckt, sondern ist abwesend (v-if)')
  assert.ok(host.querySelector('[data-kalender-flaeche]'),
    'die Fläche des Kindes fehlt, obwohl die Karte unsichtbar im Baum steht')
  tor.freigeben(VERWALTUNG)
  await warte(20)
})

// ══════════════════════════════════════════════════════════════════════════
// E3 · Gruppenwechsel an DERSELBEN Instanz
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2e/E3: nach dem Gruppenwechsel ist die Karte wieder unsichtbar (dieselbe Instanz)', async () => {
  // Der Reset-Watch in GruppeDetail läuft nur, wenn die Gruppenkennung
  // wechselt, WÄHREND die Seite steht. Ein zweites Mounten beweist davon
  // nichts (Befund am alten Test C7).
  const { host } = await seiteMounten()
  assert.equal(karteSichtbar(host), true, 'Vorbedingung: die Karte steht nach der ersten Antwort')

  // Gruppenwechsel: die (Unter-)Gruppen-Kennung ändert sich, die Seite bleibt.
  const tor = schleuse()
  antworten = { 'get_kalender_verwaltung$': tor.versprechen }
  gruppeKennung = 'G-Band'
  window.location.hash = '#/gruppe/G-Band/einstellungen'
  window.dispatchEvent(new Event('hashchange'))
  await warte(20)

  assert.equal(karteSichtbar(host), false,
    'nach dem Gruppenwechsel steht die Karte der ALTEN Gruppe sofort wieder im Bild — das ist das Aufblitzen')
  assert.ok(aufrufe.filter(([m]) => /get_kalender_verwaltung$/.test(m)).length >= 2,
    'nach dem Wechsel wurde die Verwaltung nicht neu geladen | ' + aufrufe.map(([m]) => m).join(', '))

  tor.freigeben({ ...VERWALTUNG,
    kalender: [{ name: 'Proben2', titel: 'Proben der Band', farbe: '#2266aa', gruppe: 'G-Band',
      untergruppe: null, standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' }] })
  await warte(20)
  assert.equal(karteSichtbar(host), true, 'die Karte erscheint nach dem Wechsel auch mit Antwort nicht')
})

// ══════════════════════════════════════════════════════════════════════════
// E4/E5 · „Gruppe freigeben“: Sperre bei fremder Aktion, Auswahl bei Fehler
// ══════════════════════════════════════════════════════════════════════════

const gruppeFreigebenKnopf = (host) => [...host.querySelectorAll('button')]
  .find((b) => /^Gruppe freigeben$/.test(b.textContent.trim()))

/**
 * Mountet den ECHTEN `KalenderEinstellungen`-Baustein mit aufgeklapptem
 * Kalender und steuerbarem `busy` — die Sperre kommt vom Elternteil, genau
 * wie auf der Seite.
 */
async function karteMounten({ antworten: gesetzt = {} } = {}) {
  aufrufe.length = 0
  antworten = gesetzt
  document.body.innerHTML = ''
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderEinstellungen.vue'))
  const Karte = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2e-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Karte },
    data: () => ({ gesperrtMeldungen: [] }),
    template: '<Karte gruppe="G-Chor" gruppe-name="Chor" '
      + '@gesperrt="(a, b) => gesperrtMeldungen.push([a, b])" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  const vm = app.mount(host)
  await warte(20)
  return { host, vm, meldungen }
}

/** Klappt den ersten Kalender auf und wartet auf die Freigaben. */
async function aufklappen(host) {
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => /Freigaben & Sichtbarkeit/.test(b.textContent.trim()))
  assert.ok(knopf, 'der Knopf „Freigaben & Sichtbarkeit“ fehlt')
  knopf.click()
  await warte(20)
}

test('UI-R2e/E4: „Gruppe freigeben“ ist gesperrt, während eine FREMDE Aktion läuft', async () => {
  // BEFUND UI-R2d: der Knopf las nur seinen eigenen Schlüssel
  // (`gruppeLaeuft`). Lief eine andere Aktion der Karte (`busy` gesetzt, aber
  // nicht der Gruppen-Schlüssel), war er bedienbar — `freigabeSetzen` stieg
  // mit `if (busy.value) return` aus, und die Anfrage ging STILL verloren.
  //
  // Die andere Aktion wird hier ECHT ausgelöst („Für alle sichtbar machen“,
  // `beantrage_sichtbarkeit`), deren Antwort zurückgehalten wird. `busy` ist
  // im Kartenbaustein interne `ref` — kein Prop; deshalb der echte Weg.
  const tor = schleuse()
  const { host, meldungen } = await karteMounten({
    antworten: { beantrage_sichtbarkeit$: tor.versprechen },
  })
  await aufklappen(host)
  const select = host.querySelector('select')
  assert.ok(select, 'die Gruppenauswahl fehlt | ' + meldungen.slice(0, 2).join(' | '))
  select.value = 'G-Chor'
  select.dispatchEvent(new Event('change'))
  await warte(4)
  assert.equal(gruppeFreigebenKnopf(host).disabled, false,
    'Vorbedingung: der Knopf ist mit Wahl schon gesperrt')

  // Eine FREMDE Aktion der Karte läuft: Sichtbarkeit beantragen.
  const sichtKnopf = [...host.querySelectorAll('button')]
    .find((b) => /Für alle Mitglieder der Gemeinde freigeben/.test(b.textContent.trim()))
  assert.ok(sichtKnopf, 'der Knopf für die Sichtbarkeit fehlt | '
    + [...host.querySelectorAll('button')].map((b) => b.textContent.trim()).join(' | '))
  sichtKnopf.click()
  await warte(8)

  assert.equal(gruppeFreigebenKnopf(host).disabled, true,
    '„Gruppe freigeben“ ist während einer fremden Aktion bedienbar — die Anfrage geht still verloren')
  assert.equal(host.querySelector('select').disabled, true,
    'die Gruppenauswahl ist während einer fremden Aktion bedienbar')

  // Antwort freigeben: danach ist der Knopf (mit Wahl) wieder frei.
  tor.freigeben({ gruppe_status: 'beantragt', gemeinde_status: 'aus' })
  await warte(20)
  if (host.querySelector('select').value !== 'G-Chor') {
    host.querySelector('select').value = 'G-Chor'
    host.querySelector('select').dispatchEvent(new Event('change'))
    await warte(4)
  }
  assert.equal(gruppeFreigebenKnopf(host).disabled, false,
    'der Knopf bleibt nach der fremden Aktion gesperrt')
})

test('UI-R2e/E5: bei einem Fehlschlag bleibt die Auswahl stehen, bei Erfolg wird sie geleert', async () => {
  // BEFUND UI-R2d: der Watch in `KalenderRechte` leerte die Wahl, sobald
  // `busy` fiel — gleich, ob die Freigabe geklappt hatte. Nach einem 403/417
  // stand das Feld leer da, und die Person musste die Gruppe neu suchen.
  //
  // ── Fehlschlag ────────────────────────────────────────────────────────
  const tor = schleuse()
  const fehler = await karteMounten({ antworten: { 'setze_freigabe$': tor.versprechen } })
  await aufklappen(fehler.host)
  const selectF = () => fehler.host.querySelector('select')
  selectF().value = 'G-Chor'
  selectF().dispatchEvent(new Event('change'))
  await warte(4)
  assert.equal(gruppeFreigebenKnopf(fehler.host).disabled, false,
    'Vorbedingung: der Knopf ist trotz Wahl gesperrt | ' + fehler.meldungen.slice(0, 2).join(' | '))

  gruppeFreigebenKnopf(fehler.host).click()
  await warte(10)
  tor.fehlschlagen(Object.assign(new Error('Das darfst du nicht.'), { status: 403 }))
  await warte(20)
  assert.equal(selectF().value, 'G-Chor',
    'nach dem Fehlschlag ist die Gruppenauswahl geleert — die Person muss die Gruppe neu suchen')
  assert.equal(gruppeFreigebenKnopf(fehler.host).disabled, false,
    'der Knopf ist nach dem Fehlschlag gesperrt, obwohl die Wahl noch steht')

  // ── Erfolg (Gegenprobe) ───────────────────────────────────────────────
  const erfolg = await karteMounten()
  await aufklappen(erfolg.host)
  const selectE = () => erfolg.host.querySelector('select')
  selectE().value = 'G-Chor'
  selectE().dispatchEvent(new Event('change'))
  await warte(4)
  gruppeFreigebenKnopf(erfolg.host).click()
  await warte(20)
  assert.equal(selectE().value, '', 'nach dem Erfolg bleibt die Auswahl stehen — sie soll geleert werden')
})


// ══════════════════════════════════════════════════════════════════════════
// E6 · Reste
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2e/E6: der doppelte UI-R2c-Kommentar im return-Block ist weg', () => {
  const SEITE = readFileSync(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'), 'utf8')
  const treffer = [...SEITE.matchAll(/UI-R2c: 403 aus get_kalender_verwaltung blendet die ganze Karte/g)]
  assert.ok(treffer.length <= 1,
    'der Kommentar „UI-R2c: 403 aus get_kalender_verwaltung blendet die ganze Karte“ steht '
      + treffer.length + '× im Dokument (einmal zu viel)')
  // Und die Erklärung steht überhaupt noch da (nicht einfach alles gelöscht).
  assert.match(SEITE, /403 aus get_kalender_verwaltung/,
    'die Begründung zum 403 ist ganz aus GruppeDetail.vue verschwunden')
})

test('UI-R2e/E6: `handyStufen` trägt kein ungenutztes Feld `gesperrt`', async () => {
  const { handyStufen } = await import('../src/diakonos/components/gruppen/kalenderRechte.mjs')
  const zeile = { art: 'person', kennung: 'a@b', anzeige: 'A', lesen: true, schreiben: false, moderieren: false }
  const ergebnis = handyStufen(zeile, ['lesen', 'schreiben'], {}, () => false)
  assert.equal(Object.prototype.hasOwnProperty.call(ergebnis, 'gesperrt'), false,
    'die Rückgabe von `handyStufen` trägt noch `gesperrt` — niemand liest es')
  for (const feld of ergebnis.felder.filter(Boolean)) {
    assert.deepEqual(Object.keys(feld).sort(), ['gesperrt', 'stufe', 'wort'],
      'die Felder der Handy-Stufe haben eine unerwartete Form: ' + Object.keys(feld).join(', '))
  }
})
