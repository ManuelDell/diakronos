/**
 * UI-R10b (Review, Punkte 1 + 3) — die Sperren und der Leerzustand GE MOUNTET.
 *
 * Das zweite Review zu UI-R10b hat bemängelt, dass die Zusagen nur als Regex
 * über den Quelltext geprüft waren: „gesperrt“ und „Leerzustand“ sind aber
 * Eigenschaften der gerenderten Seite (disabled-Status, sichtbarer Grund,
 * angezeigter Text). Hier laufen die ECHTEN Seiten in jsdom:
 *
 *   A · Anmeldung.vue als MITGLIEDERVERWALTUNG (kein System Manager, R-12i):
 *       1. gespeicherte Admin-Zuordnung + Modus „abweisen“ → die Admin-Zeile
 *          ist ganz gesperrt (Gruppe, Rolle, Entfernen), eine Mitglied-Zeile
 *          bleibt bedienbar, die Verwaltungs-Option im Auswahlfeld ist
 *          `disabled` mit „(nur Administrator)“, „Zuordnung ergänzen“ ist FREI;
 *       2. Modus GESPEICHERT als „anlegen_mit_rollen“ → die GANZE Liste ist
 *          gesperrt (auch die Mitglied-Zeile) und sagt warum; zusätzlich
 *          (UI-R10c) sind ALLE Modus-Radios gesperrt und ein Wechsel im
 *          Formular entsperrt die Liste NICHT — der Server verlangt den System
 *          Manager auch beim Wechsel HERAUS (A2, A2b, A2c);
 *       3. Schalter „Verwaltungsrollen über Gruppen“ + Modus „anlegen“ sind
 *          gesperrt, mit sichtbarem Grund;
 *       4. Administrator → nichts davon gesperrt (Gegenprobe);
 *   B · Einstellungen.vue ohne sichtbaren Abschnitt → DkEmpty mit dem Satz
 *       „Für dich gibt es hier keine Einstellungen.“ und KEIN eingebetteter
 *       Abschnitt (Test 8 aus UI-R10b war vorher grün, weil er nur `kette`
 *       prüfte — jetzt misst er das DOM).
 *
 * Verfahren wie `ux3h3-speichern-nur-wenn-geaendert.test.mjs`: SFCs werden
 * neben dem Quellbaum kompiliert, `useApi` wird auf eine Attrappe umgebogen.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

// Ein temporäres Verzeichnis des Systems — im Image (`/build`) gibt es kein
// `/root/...`; `tmpdir()` liefert, was die Laufzeit anbietet (`TMPDIR`).
const TMP = mkdtempSync(join(tmpdir(), 'uir10b-mount-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

/**
 * Die Seite in einem FRISCHEN Modul-Graph laden.
 *
 * `useSession.js` liest `window.__DIakonosBOOT` EINMAL beim Modulstart. Ein
 * Cache-Treffer (z. B. aus `Anmeldung.vue`, das `useSession` schon geladen
 * hat) würde den Administrator-Boot von A4 weiterverwenden und die Regel hier
 * stillschweigend verfälschen. Deshalb bekommt dieser Test seine eigene
 * Übersetzung in einem eigenen Unterordner — die relativen Importe (Komponenten,
 * Composables) zeigen ins Leere, soweit sie nicht gleich mitübersetzt werden;
 * deshalb wird der GANZE Baum aus dem Quelltext frisch abgelegt.
 */
function bausteinFrisch(seite) {
  const unterordner = join(TMP, 'frisch-' + Math.random().toString(36).slice(2))
  const zielFuer = (abs) => {
    const relativ = abs.slice(SRC_ROOT.pathname.length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const NEU = new Map()
  const frisch = (abs) => {
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
          return `from '${pathToFileURL(frisch(zielAbs)).href}'`
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
  return frisch(new URL(seite, SRC).pathname)
}

// ── API-Attrappe ──────────────────────────────────────────────────────────
const aufrufe = []
let antwort = () => ({ message: {} })
globalThis.__DK_PUSH = (eintrag) => aufrufe.push(eintrag)
globalThis.__DK_API_ANTWORT = (methode, parameter) => antwort(methode, parameter)
const apiDatei = join(TMP, '_api.mjs')
writeFileSync(apiDatei, [
  'export async function apiCall(methode, parameter) {',
  '  globalThis.__DK_PUSH({ methode, parameter })',
  '  return globalThis.__DK_API_ANTWORT(methode, parameter)',
  '}',
  'export const apiGet = apiCall',
  "export const apiUrl = (pfad) => 'https://pruefstand.invalid/api/method/' + String(pfad).replace(/\\./g, '/')",
  'export class AuditConfirmationRequired extends Error {}',
  'export const pruefeSitzungsAntwort = () => false',
  'export async function apiAntwortPruefen() { return { message: { ok: true } } }',
].join('\n'))

globalThis.fetch = async () => ({
  ok: true, status: 200,
  headers: { get: () => 'application/json' },
  json: async () => ({ message: {} }),
  text: async () => '{}',
  clone() { return this },
})

// ── SFC → ES-Modul ────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map([
  [pathToFileURL(SRC_ROOT.pathname + 'diakonos/composables/useApi.js').href,
    pathToFileURL(apiDatei).href],
])

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const quellDatei = aufgeloest(abs)
  const relativ = quellDatei.slice(SRC_ROOT.pathname.length)
  const ziel = join(TMP, relativ.replace(/[\\/]/g, '_') + '.mjs')
  mkdirSync(dirname(ziel), { recursive: true })
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
    // Die Einstellungen-Seite lädt ihre Abschnitte asynchron. Für DIESEN Test
    // zählt der Rahmen (Leerzustand/aktiver Abschnitt), nicht der Abschnitt —
    // ein Stellvertreter verhindert, dass jeder Abschnitt sein eigenes Netz
    // braucht (`ux3h-einstellungen-gruppen-suche.test.mjs`, gleiches Verfahren).
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
        const gerichtet = umleitung.get(url)
        if (gerichtet) return `from '${gerichtet}'`
        return `from '${pathToFileURL(kompilieren(zielAbs)).href}'`
      }
      if (spec.startsWith('node:')) return ganz
      return `from '${spec}'`
    },
  )
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

async function mounten(baustein) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({ components: { Seite: baustein }, template: '<Seite />' })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(12)
  return { host, app, warnungen }
}

// ── A · Anmeldung.vue, gemountet ──────────────────────────────────────────

const ADMIN_ZEILE = { gruppe: 'leitung', rolle: 'Mitgliederadministrator' }
const MITGLIED_ZEILE = { gruppe: 'chor', rolle: 'Mitglied' }

function anmeldeAntwort(modus, zuordnungen) {
  return (methode) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'anmeldung_get_einstellungen') {
      return { message: { oidc_aktiv: true, unbekannte_nutzer: modus, admin_ueber_gruppen: false,
        rollen: ['System Manager', 'Mitgliederadministrator', 'Mitglied', 'Kalender-Moderator'],
        rollen_zuordnung: zuordnungen } }
    }
    if (kurz === 'get_wartende_konten') return { message: { konten: [] } }
    return { message: {} }
  }
}

async function anmeldungMounten({ istSystemManager, modus = 'abweisen', zuordnungen = [] }) {
  aufrufe.length = 0
  document.body.innerHTML = ''
  globalThis.window.__DIakonosBOOT = {
    roles: istSystemManager ? ['System Manager', 'Administrator'] : ['Mitgliederadministrator'],
    is_admin: istSystemManager === true,
    ist_mitgliederverwaltung: true,
  }
  antwort = anmeldeAntwort(modus, zuordnungen)
  const mod = await import(pathToFileURL(bausteinFrisch('pages/einstellungen/Anmeldung.vue')).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(12)
  return { host, warnungen }
}

/** Die Zuordnungszeilen der Seite (jede hat ein Gruppen-Eingabefeld + Rolle-Auswahl). */
function zeilen(host) {
  return [...host.querySelectorAll('.an-zuordnung')]
}

/** Ist die Option „richtig gesperrt“? `<option disabled>` im geschlossenen <select> ist im DOM nicht wählbar. */
function optionen(host, i) {
  return [...zeilen(host)[i].querySelectorAll('option')]
}

test('UI-R10b/A1: Verwaltung — Admin-Zeile ganz gesperrt, Mitglied-Zeile bedienbar, „ergänzen“ frei', async () => {
  const { host, warnungen } = await anmeldungMounten({
    istSystemManager: false, modus: 'abweisen', zuordnungen: [ADMIN_ZEILE, MITGLIED_ZEILE],
  })
  assert.equal(zeilen(host).length, 2, 'zwei Zuordnungen erwartet. Warnungen: ' + warnungen.slice(0, 2).join(' | '))

  // Zeile 1 (Verwaltungsrolle): Gruppe, Rolle UND Entfernen gesperrt.
  const [admin, mitglied] = zeilen(host)
  assert.equal(admin.dataset.test, 'an-zuordnung-admin-rolle', 'die Admin-Zeile ist als gesperrt markiert')
  assert.equal(admin.querySelector('input').disabled, true, 'Gruppen-Feld der Admin-Zeile gesperrt')
  assert.equal(admin.querySelector('select').disabled, true, 'Rollen-Auswahl der Admin-Zeile gesperrt')
  const entfernen = [...admin.querySelectorAll('button')].find((b) => /Entfernen/.test(b.textContent))
  assert.ok(entfernen, 'Entfernen-Knopf fehlt')
  assert.equal(entfernen.disabled, true, '„Entfernen“ der Admin-Zeile gesperrt')
  assert.match(admin.textContent, /Nur der Administrator/, 'der Grund steht an der Zeile')

  // Zeile 2 (Mitglied): alles bedienbar — das ist die R-12i-Zusage.
  assert.equal(mitglied.dataset.test, undefined)
  assert.equal(mitglied.querySelector('input').disabled, false, 'Mitglied-Zeile: Gruppe bedienbar')
  assert.equal(mitglied.querySelector('select').disabled, false, 'Mitglied-Zeile: Rolle bedienbar')
  const entfernen2 = [...mitglied.querySelectorAll('button')].find((b) => /Entfernen/.test(b.textContent))
  assert.equal(entfernen2.disabled, false, 'Mitglied-Zeile: „Entfernen“ bedienbar')

  // Die Verwaltungs-Optionen im Auswahlfeld sind gesperrt und sagen es.
  const opts = optionen(host, 1)
  const sm = opts.find((o) => o.value === 'System Manager')
  const ma = opts.find((o) => o.value === 'Mitgliederadministrator')
  const mi = opts.find((o) => o.value === 'Mitglied')
  assert.ok(sm && ma && mi, 'die drei Rollen stehen im Auswahlfeld')
  assert.equal(sm.disabled, true, '„System Manager“ ist für die Verwaltung nicht wählbar')
  assert.equal(ma.disabled, true, '„Mitgliederadministrator“ ist für die Verwaltung nicht wählbar')
  assert.match(sm.textContent, /nur Administrator/, 'die gesperrte Option nennt den Grund')
  assert.equal(mi.disabled, false, '„Mitglied“ bleibt wählbar')

  // „Zuordnung ergänzen“ ist FREI (nur im Modus „anlegen“ wäre die Liste zu).
  const ergaenzen = host.querySelector('[data-test="an-zuordnung-ergaenzen"]')
  assert.ok(ergaenzen, '„Zuordnung ergänzen“ fehlt')
  assert.equal(ergaenzen.disabled, false, 'im Modus „abweisen“ darf die Verwaltung Zuordnungen ergänzen')

  // Der Hinweis sagt die Regel, nicht „alles andere ist bedienbar“.
  const hinweis = host.querySelector('[data-test="an-nur-admin"]')
  assert.ok(hinweis, 'der Hinweis oben fehlt')
  assert.match(hinweis.textContent, /Verwaltungsrolle/)
  assert.doesNotMatch(hinweis.textContent, /Alles andere ist bedienbar/)
})

test('UI-R10b/A2: Modus „anlegen_mit_rollen“ gespeichert → ganze Liste gesperrt, mit Grund', async () => {
  const { host } = await anmeldungMounten({
    istSystemManager: false, modus: 'anlegen_mit_rollen', zuordnungen: [MITGLIED_ZEILE],
  })
  const [zeile] = zeilen(host)
  assert.equal(zeile.querySelector('input').disabled, true, 'Gruppe gesperrt (Zugangsweg, R-N8)')
  assert.equal(zeile.querySelector('select').disabled, true, 'Rolle gesperrt')
  const entfernen = [...zeile.querySelectorAll('button')].find((b) => /Entfernen/.test(b.textContent))
  assert.equal(entfernen.disabled, true, '„Entfernen“ gesperrt')

  const ergaenzen = host.querySelector('[data-test="an-zuordnung-ergaenzen"]')
  assert.equal(ergaenzen.disabled, true, '„Zuordnung ergänzen“ ist im Modus „anlegen“ gesperrt')
  const grund = host.querySelector('[data-test="an-liste-nur-admin"]')
  assert.ok(grund, 'der Grund für die gesperrte Liste fehlt')
  assert.match(grund.textContent, /Im Modus „anlegen“ pflegt der Administrator die Zuordnungen/)

  // UI-R10c: Gespeichert ist „anlegen_mit_rollen“ — der Server verlangt den
  // System Manager auch beim Wechsel HERAUS. Deshalb sind ALLE Modus-Radios zu,
  // nicht nur der „anlegen“-Radio.
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  assert.equal(radios.length, 3, 'drei Modi erwartet')
  for (const radio of radios) {
    assert.equal(radio.disabled, true, `Modus „${radio.value}“ ist gesperrt (Wechsel heraus = 403)`)
  }
  assert.equal(host.querySelector('input[type="radio"]:checked').value, 'anlegen_mit_rollen',
    'der gespeicherte Modus bleibt gewählt')
  const modusGrund = host.querySelector('[data-test="an-modus-nur-admin"]')
  assert.ok(modusGrund, 'der Grund für die gesperrte Modus-Auswahl fehlt')
  assert.match(modusGrund.textContent, /Sofort anlegen/)
})

test('UI-R10c/A2b: Modus-Wechsel im Formular entsperrt die Liste NICHT (gesperrter Modus zählt)', async () => {
  // Der gemeldete Fehler: `systemManagerPflicht` hing am AKTUELLEN Formularwert.
  // Ein Klick auf „Abweisen“ entsperrte sofort die ganze Liste, blendete den
  // Grund aus — und der Server antwortete beim Speichern mit 403.
  const { host } = await anmeldungMounten({
    istSystemManager: false, modus: 'anlegen_mit_rollen', zuordnungen: [MITGLIED_ZEILE],
  })
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  const abweisen = radios.find((r) => r.value === 'abweisen')
  assert.equal(abweisen.disabled, true, '„Abweisen“ ist im gespeicherten Modus „anlegen“ gesperrt')

  // Der Versuch, den Wert direkt zu setzen (Tastatur, Vorlesehilfe, Test-Skript),
  // darf die Sperren NICHT aufheben: sie hängen am GESPEICHERTEN Modus.
  abweisen.checked = true
  abweisen.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await warte(6)

  const [zeile] = zeilen(host)
  assert.equal(zeile.querySelector('input').disabled, true, 'Gruppe bleibt gesperrt')
  assert.equal(zeile.querySelector('select').disabled, true, 'Rolle bleibt gesperrt')
  const entfernen = [...zeile.querySelectorAll('button')].find((b) => /Entfernen/.test(b.textContent))
  assert.equal(entfernen.disabled, true, '„Entfernen“ bleibt gesperrt')
  assert.equal(host.querySelector('[data-test="an-zuordnung-ergaenzen"]').disabled, true,
    '„Zuordnung ergänzen“ bleibt gesperrt')
  assert.ok(host.querySelector('[data-test="an-liste-nur-admin"]'),
    'der Grund für die gesperrte Liste bleibt sichtbar')
  assert.ok(host.querySelector('[data-test="an-modus-nur-admin"]'),
    'der Grund an der Modus-Auswahl bleibt sichtbar')

  // Gegenprobe: der gespeicherte Stand (Zuordnungen, Schalter) hat sich nicht
  // geändert — die Zuordnungs-Änderung, die den 403 auslöste, ist gar nicht
  // erst möglich. (Der Modus-Wert im Formular zählt als Änderung, das ist die
  // EHRLICHE Anzeige; der Server verweigert genau diesen Wechsel mit 403.)
  assert.equal(host.querySelector('[data-test="an-zuordnung-ergaenzen"]').disabled, true,
    '„Zuordnung ergänzen“ bleibt gesperrt')
})

test('UI-R10c/A2c: Administrator darf den gespeicherten Modus „anlegen“ wechseln (Gegenprobe)', async () => {
  const { host } = await anmeldungMounten({
    istSystemManager: true, modus: 'anlegen_mit_rollen', zuordnungen: [MITGLIED_ZEILE],
  })
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  for (const radio of radios) {
    assert.equal(radio.disabled, false, `Administrator: Modus „${radio.value}“ bedienbar`)
  }
  const [zeile] = zeilen(host)
  assert.equal(zeile.querySelector('input').disabled, false, 'Administrator: Liste bedienbar')
  assert.equal(host.querySelector('[data-test="an-modus-nur-admin"]'), null, 'kein Modus-Sperrhinweis')
  assert.equal(host.querySelector('[data-test="an-liste-nur-admin"]'), null, 'kein Listen-Sperrhinweis')
})

test('UI-R10b/A3: Modus „anlegen“ und der Gruppen-Schalter sind für die Verwaltung gesperrt (mit Grund)', async () => {
  const { host } = await anmeldungMounten({ istSystemManager: false, zuordnungen: [] })
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  const anlegen = radios.find((r) => r.value === 'anlegen_mit_rollen')
  assert.ok(anlegen, 'die Modus-Auswahl fehlt')
  assert.equal(anlegen.disabled, true, 'Modus „anlegen“ ist gesperrt')
  assert.match(host.textContent, /Nur der Administrator/, 'der Grund steht in der Auswahl')

  const schalter = host.querySelector('input[type="checkbox"]')
  assert.ok(schalter, 'der Schalter fehlt')
  assert.equal(schalter.disabled, true, '„Verwaltungsrollen über Authentik-Gruppen“ ist gesperrt')
  assert.equal(schalter.checked, false)
})

test('UI-R10b/A4: Administrator — nichts davon ist gesperrt (Gegenprobe)', async () => {
  const { host } = await anmeldungMounten({
    istSystemManager: true, modus: 'abweisen', zuordnungen: [ADMIN_ZEILE, MITGLIED_ZEILE],
  })
  assert.equal(host.querySelector('[data-test="an-nur-admin"]'), null, 'kein Sperr-Hinweis für den Administrator')
  assert.equal(host.querySelector('[data-test="an-liste-nur-admin"]'), null, 'keine gesperrte Liste für den Administrator')
  for (const zeile of zeilen(host)) {
    assert.equal(zeile.querySelector('input').disabled, false)
    assert.equal(zeile.querySelector('select').disabled, false)
    const entfernen = [...zeile.querySelectorAll('button')].find((b) => /Entfernen/.test(b.textContent))
    assert.equal(entfernen.disabled, false)
  }
  const opts = optionen(host, 0)
  assert.equal(opts.find((o) => o.value === 'System Manager').disabled, false,
    'der Administrator darf die Verwaltungsrollen wählen')
  assert.equal(host.querySelector('[data-test="an-zuordnung-ergaenzen"]').disabled, false)
  assert.equal(host.querySelector('input[type="checkbox"]').disabled, false)
  assert.equal([...host.querySelectorAll('input[type="radio"]')]
    .find((r) => r.value === 'anlegen_mit_rollen').disabled, false)
})

// ── B · Einstellungen.vue: Leerzustand (Test 8 aus Runde 1, jetzt am DOM) ──

test('UI-R10b/B: Einstellungen ohne sichtbaren Abschnitt → DkEmpty, KEIN eingebetteter Abschnitt', async () => {
  document.body.innerHTML = ''
  // Ein Mitglied (kein Admin, keine Mitgliederverwaltung): alle Abschnitte
  // hängen an `verwaltung: 'admin' | 'personen'` → sichtbar bleibt nichts.
  globalThis.window.__DIakonosBOOT = {
    roles: [], is_admin: false, ist_mitgliederverwaltung: false, devmode: false,
  }
  antwort = () => ({ message: {} })
  const mod = await import(pathToFileURL(bausteinFrisch('pages/Einstellungen.vue')).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(12)

  const leer = host.querySelector('[data-test="ei-keine-einstellungen"]')
  assert.ok(leer, 'der Leerzustand fehlt. Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.match(leer.textContent, /Für dich gibt es hier keine Einstellungen\./,
    'der Satz aus der Karte steht im Leerzustand')
  // KEIN Abschnitt wurde eingebettet (früher „Gemeinde“).
  assert.equal(host.querySelectorAll('.ei-inhalt .an-abschnitt').length, 0,
    'kein fremder Abschnitt eingebettet')
  assert.equal(host.querySelectorAll('.ei-inhalt .an-felder').length, 0,
    'kein Abschnittsformular eingebettet')
  // Die Liste ist leer — kein Eintrag ist als „aktiv“ markiert.
  assert.equal(host.querySelectorAll('.ei-eintrag').length, 0, 'keine sichtbaren Abschnitte in der Liste')
})

test('UI-R10b/B: Administrator sieht die Abschnitte — kein Leerzustand (Gegenprobe)', async () => {
  document.body.innerHTML = ''
  globalThis.window.__DIakonosBOOT = {
    roles: ['System Manager', 'Administrator'], is_admin: true, ist_mitgliederverwaltung: true, devmode: false,
  }
  antwort = () => ({ message: {} })
  const mod = await import(pathToFileURL(bausteinFrisch('pages/Einstellungen.vue')).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(12)
  assert.equal(host.querySelector('[data-test="ei-keine-einstellungen"]'), null,
    'der Administrator sieht keinen Leerzustand. Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.ok(host.querySelectorAll('.ei-eintrag').length > 5, 'die Bereichsliste ist gefüllt')
  // Genau EIN Eintrag ist aktiv — nie keiner (solange Abschnitte sichtbar sind).
  assert.equal(host.querySelectorAll('.ei-eintrag.is-active').length, 1, 'genau ein aktiver Abschnitt')
})
