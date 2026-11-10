/**
 * DEV-B2 — Kalender „Zu prüfen“: Ansichtsreiter bleiben, „‹ Kalender“ nur mobil.
 *
 * Karte t_360093a4, Befund DMB-8e166c0aacff (Demo, 09.11.): Unter „Zu prüfen“
 * verschwanden Monat/Woche/Liste, das Design war inkonsistent, und „‹ Kalender“
 * stand auf jeder Breite da. Ursachen:
 *
 *   1. `KronosTopbar.vue` filterte auf der Prüf-Tafel ALLE Ansichts-Reiter weg
 *      (`liste.filter(r => r.ansicht !== true)`) — `Moderation.vue` verspricht
 *      seit UX3d das Gegenteil („Monat/Woche/Liste führen zurück“).
 *   2. `.dk-moderation-mobile-back` hatte GAR KEIN CSS — der für das Handy
 *      gedachte Knopf stand auch am Desktop im Weg.
 *
 * Geprüft wird, was der Nutzer SIEHT und wohin er kommt — nicht nur ein
 * Quelltext-Muster:
 *
 *   A · Kopfzeile auf der Prüf-Tafel: vier Reiter, beschriftet wie im
 *       Kalender, „Monat/Woche/Liste“ sind LINKS auf `#/kalender?ansicht=…`,
 *       „Zu prüfen“ ist die markierte aktuelle Seite. Die Kalender-Werkzeuge
 *       (Heute, ‹ ›, Termin anlegen) stehen dort NICHT.
 *   B · Kalender-Seite: `ansicht=` aus der Adresse wird ausgewertet (Desktop:
 *       Raster, Handy: Segmentsteuerung) und danach aus der Adresse entfernt;
 *       eine unbekannte Angabe ändert nichts.
 *   C · „‹ Kalender“: das Bauteil markiert den Rückweg als Handy-Weg
 *       (Klasse im Markup, `display: none` über der Handy-Grenze im CSS),
 *       die Grenze ist dieselbe wie im Rest der App (720 px).
 *   D · Bestand unverändert: die Tafel selbst (Alle freigeben, Erklärung,
 *       Änderungen, Brett) bleibt, wie sie war.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz — Vue-SFCs werden wie in `ux3d-kalender-pruefen.test.mjs` in einer
 * jsdom gemountet.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

// ── menue.js in einer vm ausführen (dieselbe Technik wie UX3d) ────────────
function menueAusfuehren() {
  let source = lies('menue.js')
  source = source.replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
    "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
  source = source.replace(/^export /gm, '')
  source += '\nglobalThis.menue = { kalenderReiter, KALENDER_PRUEF_REITER };'
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.menue
}

const M = menueAusfuehren()

// ── SFC-Mount (wie ux3d-kalender-pruefen.test.mjs) ────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'devb2-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function kompilieren(abs) {
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
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (!spec.startsWith('.')) return v
    const ziel = resolve(dirname(abs), spec)
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))

async function mounten(datei, eigenschaften, vorkommen) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil, ...(vorkommen || {}) },
    setup: () => ({ p: eigenschaften }),
    template: '<Geprueft v-bind="p" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen }
}

const reiterFuerTafel = Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: 2 }))

// ══════════════════════════════════════════════════════════════════════════
// A · Kopfzeile der Prüf-Tafel
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B2: die Prüf-Tafel zeigt DIESELBE Reiterzeile wie der Kalender', async () => {
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host, warnungen } = await mounten(
    'components/kronos/KronosTopbar.vue',
    {
      canModerate: true, offeneZahl: 2, aktiverReiter: 'pruefen',
      pruefTafel: true, dateTitle: 'Zu prüfen', currentView: 'pruefen',
    },
    { KalenderReiter: Reiter },
  )
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')

  const leiste = host.querySelector('.kal-reiter')
  assert.ok(leiste, 'Reiterleiste fehlt auf der Tafel')
  const punkte = [...leiste.querySelectorAll('.kal-reiter-punkt')]
  assert.deepEqual(punkte.map((p) => p.dataset.reiter),
    ['monat', 'woche', 'liste', 'pruefen'],
    'Monat · Woche · Liste · Zu prüfen — genau wie im Kalender')
  assert.deepEqual(punkte.map((p) => (p.querySelector('.kal-reiter-name') || p).textContent.trim()),
    ['Monat', 'Woche', 'Liste', 'Zu prüfen'], 'Beschriftungen wörtlich')
})

test('DEV-B2: „Monat/Woche/Liste“ führen auf der Tafel als LINKS in den Kalender', async () => {
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: null, aktiverReiter: 'pruefen', pruefTafel: true },
    { KalenderReiter: Reiter },
  )
  for (const id of ['monat', 'woche', 'liste']) {
    const punkt = host.querySelector(`[data-reiter="${id}"]`)
    assert.ok(punkt, `„${id}“ fehlt auf der Tafel`)
    assert.equal(punkt.tagName, 'A', `„${id}“ ist auf der Tafel ein Link (kein toter Umschalter)`)
    assert.equal(punkt.getAttribute('href'), `#/kalender?ansicht=${id}`,
      `„${id}“ führt zurück in den Kalender mit der gewünschten Ansicht`)
    assert.equal(punkt.getAttribute('aria-pressed'), null, 'Link trägt kein aria-pressed')
  }
  // „Zu prüfen“ ist die aktuelle Seite — markiert, nicht zweimal vorhanden.
  const pruefen = host.querySelector('[data-reiter="pruefen"]')
  assert.equal(pruefen.tagName, 'A')
  assert.equal(pruefen.getAttribute('aria-current'), 'page')
  assert.ok(pruefen.classList.contains('is-aktiv'), 'sichtbare Markierung')
})

test('DEV-B2: auf der Tafel stehen KEINE Kalender-Werkzeuge', async () => {
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: null, aktiverReiter: 'pruefen', pruefTafel: true, canWrite: true },
    { KalenderReiter: Reiter },
  )
  for (const auswahl of ['.header-right', '.termin-anlegen-btn', '.todaybutton', '.prev-month', '.next-month']) {
    assert.equal(host.querySelector(auswahl), null, `${auswahl} gehört nicht auf die Tafel`)
  }
})

test('DEV-B2: im KALENDER bleiben die Ansichten Umschalter (Knöpfe, kein Link)', async () => {
  // Gegenprobe: die Tafel-Regel darf den Kalender nicht verändern.
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: 2, currentView: 'timeGridWeek', aktiverReiter: 'kalender' },
    { KalenderReiter: Reiter },
  )
  for (const id of ['monat', 'woche', 'liste']) {
    const punkt = host.querySelector(`[data-reiter="${id}"]`)
    assert.equal(punkt.tagName, 'BUTTON', `„${id}“ ist im Kalender ein Umschalter`)
  }
  assert.equal(host.querySelector('[data-reiter="woche"]').getAttribute('aria-pressed'), 'true')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Die Kalender-Seite wertet `?ansicht=` aus
// ══════════════════════════════════════════════════════════════════════════
/**
 * `ansichtsWunschAusAdresse` ist eine Funktion der Seite (kein eigener
 * Export). Sie wird hier aus der Datei gelöst und mit einem nachgebauten
 * `location`/`history` wirklich AUSGEFÜHRT — ein Quelltext-Muster genügt nicht.
 */
function wunschFunktionAusSeite() {
  const quelle = lies('pages/Kalender.vue')
  const start = quelle.indexOf('function ansichtsWunschAusAdresse()')
  assert.ok(start > 0, 'ansichtsWunschAusAdresse fehlt in pages/Kalender.vue')
  // Bis zur nächsten Funktion auf oberster Ebene (Dokumentation davor stört nicht).
  const rest = quelle.slice(start)
  const ende = rest.search(/\n}\n/)
  const rumpf = rest.slice(0, ende + 3)
  return { quelle, rumpf }
}

function fuhreAus(hash, istAnsicht) {
  const { rumpf } = wunschFunktionAusSeite()
  const ersetzt = []
  const ctx = {
    location: { hash },
    history: { replaceState: (_a, _b, ziel) => ersetzt.push(ziel) },
    URLSearchParams,
    istAnsicht,
    console,
  }
  vm.createContext(ctx)
  vm.runInContext(rumpf + '\nglobalThis.ergebnis = ansichtsWunschAusAdresse();', ctx)
  return { ergebnis: ctx.ergebnis, ersetzt }
}

function echteIstAnsicht() {
  // Dieselbe Prüfung wie `mobilAnsicht.mjs` (monat/woche/liste).
  const quelle = lies('components/kronos/mobilAnsicht.mjs')
  const start = quelle.indexOf('export function istAnsicht(')
  const rest = quelle.slice(start)
  const ende = rest.search(/\n}\n/)
  const ctx = {
    MOBIL_ANSICHTEN: [{ id: 'monat' }, { id: 'woche' }, { id: 'liste' }],
  }
  vm.createContext(ctx)
  vm.runInContext(rest.slice(0, ende + 3).replace('export function', 'function')
    + '\nglobalThis.istAnsicht = istAnsicht;', ctx)
  return ctx.istAnsicht
}

test('DEV-B2: `#/kalender?ansicht=woche` ergibt „woche“ und räumt die Adresse auf', () => {
  const istAnsicht = echteIstAnsicht()
  for (const id of ['monat', 'woche', 'liste']) {
    const { ergebnis, ersetzt } = fuhreAus(`#/kalender?ansicht=${id}`, istAnsicht)
    assert.equal(ergebnis, id, `?ansicht=${id} wird gelesen`)
    assert.deepEqual(ersetzt, ['#/kalender'],
      'der Abfrageteil verschwindet nach dem Lesen (kein Wieder-Setzen beim Neuladen)')
  }
})

test('DEV-B2: ohne oder mit unbekanntem `ansicht` ändert sich nichts', () => {
  const istAnsicht = echteIstAnsicht()
  assert.equal(fuhreAus('#/kalender', istAnsicht).ergebnis, null)
  assert.deepEqual(fuhreAus('#/kalender', istAnsicht).ersetzt, [], 'ohne Angabe kein Eingriff in die Adresse')
  const unsinn = fuhreAus('#/kalender?ansicht=quatsch', istAnsicht)
  assert.equal(unsinn.ergebnis, null, 'eine unbekannte Ansicht wird NICHT geraten')
  assert.deepEqual(unsinn.ersetzt, ['#/kalender'], 'der Unsinn bleibt aber nicht in der Adresse stehen')
})

test('DEV-B2: `?neu=1` (Befehlspalette) bleibt unberührt', () => {
  const istAnsicht = echteIstAnsicht()
  // Der Anlege-Wunsch gehört `anlegeWunschAusAdresse` — hier wird er weder
  // gelesen noch entfernt (sonst öffnete der Dialog nie).
  const { ergebnis, ersetzt } = fuhreAus('#/kalender?neu=1', istAnsicht)
  assert.equal(ergebnis, null)
  assert.deepEqual(ersetzt, [], '„neu“ darf nicht aus der Adresse fliegen')
})

test('DEV-B2: die Seite setzt den Wunsch VOR dem persönlichen Standard', () => {
  const quelle = lies('pages/Kalender.vue')
  const standard = quelle.indexOf('standardLaden()')
  const wunsch = quelle.indexOf('ansichtsWunschAusAdresse()')
  assert.ok(standard > 0 && wunsch > 0, 'Standard und Wunsch müssen in onMounted stehen')
  assert.ok(wunsch > standard, 'der Wunsch gilt nach dem Standard (er gewinnt)')
  assert.match(quelle, /mobilAnsichtId\.value = wunsch/, 'am Handy gilt er für die Segmentsteuerung')
  assert.match(quelle, /currentView\.value = bibliothekAnsicht\(wunsch\)/, 'am Desktop für das Raster')
})

// ══════════════════════════════════════════════════════════════════════════
// C · „‹ Kalender“ nur am Handy
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B2: der Rückweg zur Kalenderliste ist im Markup der Tafel vorhanden', () => {
  const quelle = lies('pages/Moderation.vue')
  assert.match(quelle, /class="dk-moderation-mobile-back"/, 'der Rückweg fehlt')
  assert.match(quelle, /href="#\/kalender"/, 'er ist ein echter Link (auch ohne Skript bedienbar)')
})

test('DEV-B2: „‹ Kalender“ steht nur in der Handy-Lage (echtes CSS)', () => {
  const quelle = lies('pages/Moderation.vue')
  const stil = quelle.slice(quelle.indexOf('<style'))
  // Grundzustand: weg. Vorher gab es zu dieser Klasse KEINE Regel — der Knopf
  // stand deshalb auf jeder Breite (Befund).
  assert.match(stil, /\.dk-moderation-mobile-back\s*\{\s*display:\s*none;?\s*\}/,
    'außerhalb der Handy-Lage ist der Rückweg ausgeblendet')
  // In der Handy-Lage: sichtbar, mit 44 px Klickfläche (K4).
  assert.match(stil, /\.dk-app--handy \.dk-moderation-mobile-back\s*\{[^}]*display:\s*inline-flex[^}]*min-height:\s*44px/,
    'in der Handy-Lage wird er mit 44 px Klickfläche eingeblendet')
})

test('DEV-B2: der Rückweg hängt an der EINEN Handy-Lage, nicht an einer eigenen Breite', () => {
  const quelle = lies('pages/Moderation.vue')
  const stil = quelle.slice(quelle.indexOf('<style')).replace(/\/\*[\s\S]*?\*\//g, '')
  // Keine @media-Regel darf den Rückweg einblenden (DEV-B6: Gerüst/Navigation
  // hängt an `.dk-app--handy`, nicht an `max-width`).
  for (const m of stil.matchAll(/@media[^{]*\{([\s\S]*?)\n\}/g)) {
    assert.ok(!/dk-moderation-mobile-back/.test(m[1]), 'Rückweg hängt an einer Breitenabfrage')
  }
})

// ══════════════════════════════════════════════════════════════════════════
// D · Die Tafel selbst bleibt unverändert
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B2: die Prüf-Tafel behält ihre Funktion', () => {
  const quelle = lies('pages/Moderation.vue')
  for (const teil of ['Alle freigeben', 'data-test="moderation-erklaerung"',
    'ModerationAenderungen', 'ModerationBoard', 'can_moderate']) {
    assert.ok(quelle.includes(teil), `${teil} fehlt auf der Tafel`)
  }
  assert.match(quelle, /aktiverReiter="pruefen"/, 'der vierte Reiter ist dort aktiv')
})
