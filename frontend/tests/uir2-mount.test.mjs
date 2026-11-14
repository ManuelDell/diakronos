/**
 * UI-R2 — Mountet die ECHTEN Bausteine in jsdom.
 *
 * Die reine Logik (tests/uir2-kalender-rechte.test.mjs) sagt, WAS gezeigt
 * werden soll. Hier wird gemessen, dass die Oberfläche es auch TUT:
 *
 *   M1  Die Kalenderliste zeigt genau die Kalender dieser Gruppe (keine
 *       fremden, keine Gemeinde-Kalender) — Quelle `get_kalender_verwaltung`.
 *   M2  Aufklappen lädt die Freigaben GENAU EINES Kalenders
 *       (`get_objekt_rechte`) — nicht aller.
 *   M3  Ein Kästchen umschalten sendet `setze_freigabe` mit genau einer
 *       Kennung und den vollständigen Stufen.
 *   M4  „Moderieren“ fehlt ohne Serverrecht (kein Kästchen) — mit Recht steht es.
 *   M5  „An die ganze Gruppe freigeben“ gibt es NUR bei Untergruppen-Kalendern.
 *   M6  Anlegen sendet `create_kalender` mit Titel, Farbe, Ziel und der
 *       Ja/Nein-Antwort; ein Fachfehler des Servers steht IM Dialog.
 *
 * Lauf: node --test tests/uir2-mount.test.mjs   (cwd = frontend/)
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

// ── Testwelt ──────────────────────────────────────────────────────────────
const GRUPPE = 'G-Chor'
const UNTERGRUPPE = 'UG-K'

/** `get_kalender_verwaltung` — auch fremde Kalender, die NICHT erscheinen dürfen. */
const VERWALTUNG = {
  kalender: [
    { name: 'Proben', titel: 'Proben', farbe: '#3366cc', gruppe: GRUPPE, untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' },
    { name: 'Kinderchor', titel: 'Kinderchor', farbe: '#cc3366', gruppe: GRUPPE, untergruppe: UNTERGRUPPE,
      standard_gruppe_lesen: false, gemeinde_status: 'beantragt', gruppe_status: 'aktiv' },
    { name: 'Gemeinde', titel: 'Gemeinde', farbe: '#333333', gruppe: null, untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aktiv', gruppe_status: 'aus' },
    { name: 'Fremd', titel: 'Fremdkalender', farbe: '#999999', gruppe: 'G-Andere', untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' },
  ],
  darf_gemeinde_kalender: false,
  anlegen_gruppen: [GRUPPE],
  anlegen_untergruppen: [UNTERGRUPPE],
  farbe_standard: '#2266aa',
}

/** `rechte.get_objekt_rechte` je Kalender. */
const OBJEKTE = {
  Proben: {
    typ: 'kalender', objekt: 'Proben', gruppe: GRUPPE, untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
    freigaben: [{ benutzer: 'anna@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: false }],
  },
  Kinderchor: {
    typ: 'kalender', objekt: 'Kinderchor', gruppe: GRUPPE, untergruppe: UNTERGRUPPE,
    standard_gruppe_lesen: false, gemeinde_status: 'beantragt', gruppe_status: 'aktiv',
    freigaben: [],
  },
}

const aufrufe = []
let ueberschreibungen = {}

globalThis.__uiR2ApiMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_kalender_verwaltung$/.test(methode)) return JSON.parse(JSON.stringify(VERWALTUNG))
  if (/rechte\.get_objekt_rechte$/.test(methode)) {
    return JSON.parse(JSON.stringify(OBJEKTE[args?.objekt] || { freigaben: [] }))
  }
  if (/get_personen_auswahl$/.test(methode)) {
    return { personen: [{ benutzer: 'anna@example.org', name: 'Anna Beispiel' }, { benutzer: 'bea@example.org', name: 'Bea Neu' }] }
  }
  return { success: true }
}

// ── SFC-Übersetzer (Muster wie tests/ui-r1-reiter-mount.test.mjs) ─────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir2-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR2ApiMock(methode, args)\n'
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
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
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

/**
 * Nach jedem Test: Hosts und per Teleport eingefügte Dialoge entfernen.
 * Sonst fände `#ke-form` den Dialog eines FRÜHEREN Tests (gleiche Kennung),
 * und ein Fehlerfall hinge an einer Karte, die niemand mehr bedient.
 */
test.afterEach(() => {
  for (const el of [...document.body.querySelectorAll('.dk-ui-dialog-overlay, [data-uir2-host]')]) el.remove()
})

const warte = async (n = 16) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/**
 * Wartet, bis ein Element im Dokument steht. Der Dialog wird per `Teleport`
 * an `body` gehängt und erst nach dem nächsten Zeichentakt eingefügt — ein
 * sofortiges `querySelector` liefe ins Leere (im Browser unsichtbar, hier
 * messbar).
 */
async function bereit(auswahl, versuche = 40) {
  for (let i = 0; i < versuche; i += 1) {
    const treffer = document.querySelector(auswahl)
    if (treffer) return treffer
    await warte(2)
  }
  return null
}

/** Mountet die echte Karte `KalenderEinstellungen.vue`. */
async function karteMounten({ untergruppe = '', antworten = {} } = {}) {
  aufrufe.length = 0
  ueberschreibungen = antworten
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderEinstellungen.vue'))
  const Karte = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Karte },
    data: () => ({ untergruppe }),
    template: '<Karte :gruppe="\'G-Chor\'" :untergruppe="untergruppe" gruppe-name="Chor" '
      + 'untergruppe-name="Kinderchor" :untergruppen="[{ name: \'UG-K\', anzeigename: \'Kinderchor\' }]" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte()
  return { host, app, meldungen }
}

/** Antworten einer bestimmten Methode (Teilstring). */
const mit = (methode) => aufrufe.filter(([m]) => String(m).includes(methode))

// ══════════════════════════════════════════════════════════════════════════
// M1 · Liste
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2/M1: die Karte zeigt NUR die Kalender dieser Gruppe', async () => {
  const { host, meldungen } = await karteMounten()
  const text = host.textContent
  assert.ok(text.includes('Proben'), 'Kalender „Proben“ fehlt | ' + meldungen.slice(0, 3).join(' | '))
  assert.ok(text.includes('Kinderchor'), 'Kalender der Untergruppe fehlt')
  assert.ok(!text.includes('Fremdkalender'), 'ein fremder Kalender wird gezeigt')
  assert.ok(!/Gemeinde\b/.test(host.querySelector('.ke-liste')?.textContent || ''),
    'der Gemeinde-Kalender gehört nicht in die Gruppenliste')
  assert.equal(mit('get_kalender_verwaltung').length, 1, 'die Liste wird EINMAL geladen')
})

test('UI-R2/M1: eine Untergruppen-Seite zeigt nur Kalender DIESER Untergruppe', async () => {
  const { host } = await karteMounten({ untergruppe: UNTERGRUPPE })
  assert.ok(host.textContent.includes('Kinderchor'))
  assert.ok(!host.textContent.includes('Proben'), 'der Gruppen-Kalender steht auf der Untergruppen-Seite')
})

// ══════════════════════════════════════════════════════════════════════════
// M2 · Aufklappen lädt genau EINEN Kalender
// ══════════════════════════════════════════════════════════════════════════

async function aufklappen(host, name) {
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => b.closest(`[data-kalender="${name}"]`) && /Freigaben & Sichtbarkeit/.test(b.textContent))
  assert.ok(knopf, `Aufklapp-Knopf für ${name} fehlt`)
  knopf.click()
  await warte()
  return knopf
}

test('UI-R2/M2: Aufklappen lädt die Freigaben GENAU dieses Kalenders', async () => {
  const { host } = await karteMounten()
  assert.equal(mit('get_objekt_rechte').length, 0, 'vor dem Aufklappen wird nichts geladen')
  await aufklappen(host, 'Proben')
  const laden = mit('get_objekt_rechte')
  assert.equal(laden.length, 1)
  assert.deepEqual(laden[0][1], { typ: 'kalender', objekt: 'Proben' })
  assert.ok(host.textContent.includes('Anna Beispiel'), 'die Freigabe steht in der Matrix')
  assert.match(host.textContent, /gilt sofort/)
})

// ══════════════════════════════════════════════════════════════════════════
// M3 · Stufe umschalten
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2/M3: ein Kästchen sendet setze_freigabe mit genau einer Kennung', async () => {
  const { host } = await karteMounten()
  await aufklappen(host, 'Proben')
  const kaestchen = [...host.querySelectorAll('input[type="checkbox"]')]
    .find((i) => /Anna Beispiel: Schreiben/.test(i.getAttribute('aria-label') || ''))
  assert.ok(kaestchen, 'das Kästchen „Schreiben“ für Anna fehlt')
  kaestchen.click()
  await warte()
  const senden = mit('rechte.setze_freigabe')
  assert.equal(senden.length, 1, 'genau eine Freigabe-Anfrage')
  const [, args] = senden[0]
  assert.equal(args.typ, 'kalender')
  assert.equal(args.objekt, 'Proben')
  assert.equal(args.benutzer, 'anna@example.org')
  assert.equal(args.gruppe, undefined, 'kein Gruppen-Ziel neben der Person')
  assert.equal(args.lesen, true, 'Schreiben ohne Lesen ergibt keinen Sinn')
  assert.equal(args.schreiben, true)
  assert.equal(args.moderieren, false)
  // Danach wird still nachgeladen (die Karte bleibt stehen).
  assert.ok(mit('get_objekt_rechte').length >= 2, 'nach der Änderung werden die Freigaben nachgeladen')
})

// ══════════════════════════════════════════════════════════════════════════
// M4 · Moderieren nur mit Serverrecht
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2/M4: ohne Serverrecht ist „Moderieren“ nur Anzeige, nicht bedienbar', async () => {
  // UI-R2b (Punkt 1/13): ohne Vergaberecht wird Moderieren GEZEIGT, wenn die
  // Zeile es trägt (sonst sähe niemand, wer prüfen darf) — aber gesperrt.
  const { host } = await karteMounten({
    antworten: {
      'rechte\\.get_objekt_rechte$': {
        ...OBJEKTE.Proben,
        darf_moderieren_vergeben: false,
        freigaben: [{ benutzer: 'anna@example.org', gruppe: null, name: 'Anna Beispiel',
          lesen: true, schreiben: true, moderieren: true }],
      },
    },
  })
  await aufklappen(host, 'Proben')
  const kaestchen = [...host.querySelectorAll('input[type="checkbox"]')]
    .find((i) => /Anna Beispiel: Moderieren/.test(i.getAttribute('aria-label') || ''))
  assert.ok(kaestchen, 'die Zeile trägt Moderieren — der Wert muss sichtbar bleiben')
  assert.equal(kaestchen.disabled, true, 'Moderieren ist ohne Vergaberecht bedienbar')
  assert.match(host.textContent, /Das Prüfrecht vergeben nur HV und MV/)
})

test('UI-R2b/M4: ohne Moderationszeile steht Moderieren gar nicht erst da', async () => {
  const { host } = await karteMounten()
  await aufklappen(host, 'Proben')
  const kaestchen = [...host.querySelectorAll('input[type="checkbox"]')]
    .find((i) => /Anna Beispiel: Moderieren/.test(i.getAttribute('aria-label') || ''))
  assert.ok(!kaestchen, 'Moderieren steht in einer Zeile ohne Moderieren')
  assert.match(host.textContent, /Das Prüfrecht vergeben nur HV und MV/)
})

test('UI-R2/M4: mit Serverrecht steht „Moderieren“ als Kästchen', async () => {
  const { host } = await karteMounten({
    antworten: {
      'rechte\\.get_objekt_rechte$': {
        ...OBJEKTE.Proben,
        darf_moderieren_vergeben: true,
      },
    },
  })
  await aufklappen(host, 'Proben')
  const kaestchen = [...host.querySelectorAll('input[type="checkbox"]')]
    .find((i) => /Anna Beispiel: Moderieren/.test(i.getAttribute('aria-label') || ''))
  assert.ok(kaestchen, 'das Kästchen „Moderieren“ fehlt trotz Serverrecht')
})

// ══════════════════════════════════════════════════════════════════════════
// M5 · Sichtbarkeit
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2/M5: „an die ganze Gruppe“ NUR bei Untergruppen-Kalendern', async () => {
  const { host } = await karteMounten()
  await aufklappen(host, 'Proben')
  assert.ok(!host.textContent.includes('An die ganze Gruppe freigeben'),
    'der Hauptgruppen-Kalender bietet die Gruppenstufe an')
  assert.ok(host.textContent.includes('Für alle Mitglieder der Gemeinde freigeben'))

  const zweite = await karteMounten()
  await aufklappen(zweite.host, 'Kinderchor')
  assert.ok(zweite.host.textContent.includes('An die ganze Gruppe freigeben'),
    'der Untergruppen-Kalender bietet die Gruppenstufe an')
  assert.match(zweite.host.textContent, /wartet auf die Prüfung durch die Gemeinde/)
})

test('UI-R2/M5: „Beantragen“ sendet beantrage_sichtbarkeit mit dem Ziel', async () => {
  const { host } = await karteMounten()
  await aufklappen(host, 'Proben')
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => /Für alle Mitglieder der Gemeinde freigeben/.test(b.textContent))
  assert.ok(knopf)
  knopf.click()
  await warte()
  const senden = mit('beantrage_sichtbarkeit')
  assert.equal(senden.length, 1)
  assert.deepEqual(senden[0][1], { typ: 'kalender', objekt: 'Proben', ziel: 'gemeinde' })
})

// ══════════════════════════════════════════════════════════════════════════
// M6 · Anlegen
// ══════════════════════════════════════════════════════════════════════════

async function anlegenAusfuellen(host, { titel = 'Jugend', nein = false, untergruppe = '' } = {}) {
  const knopf = [...host.querySelectorAll('button')].find((b) => b.classList.contains('ke-anlegen-knopf'))
  assert.ok(knopf, 'der Knopf „Kalender anlegen“ fehlt')
  knopf.click()
  await warte()
  const form = await bereit('#ke-form')
  assert.ok(form, 'der Anlege-Dialog fehlt')
  // `DkEingabe`-Felder tragen die Klasse `dk-ui-eingabe`; das Namensfeld ist
  // das ERSTE Textfeld im Formular.
  const feld = await bereit('#ke-form input.dk-ui-eingabe')
  assert.ok(feld, 'das Namensfeld fehlt | ' + form.innerHTML.slice(0, 300))
  feld.value = titel
  feld.dispatchEvent(new window.Event('input'))
  await warte(2)
  if (nein) {
    // UI-R2b (Punkt 7): die Frage ist eine echte RADIOGRUPPE — zwei Punkte,
    // genau einer gewählt. Vorher waren es zwei Kästchen, die beide leer
    // stehen konnten („nichts gewählt“).
    const punkte = [...form.querySelectorAll('input[type="radio"]')]
      .filter((i) => /nur mit eigener Freigabe/.test(i.closest('label')?.textContent || ''))
    assert.equal(punkte.length, 1, 'die Antwort „Nein“ ist kein Radiopunkt')
    punkte[0].click()
    await warte(2)
    assert.equal(punkte[0].checked, true, 'der Klick auf „Nein“ wählt nichts')
  }
  return form
}

test('UI-R2/M6: Anlegen sendet Titel, Farbe, Ziel und die Ja/Nein-Antwort', async () => {
  const { host } = await karteMounten({ untergruppe: UNTERGRUPPE })
  const form = await anlegenAusfuellen(host, { titel: 'Jugend', nein: true })
  const absenden = [...document.querySelectorAll('button')].find((b) => b.getAttribute('form') === 'ke-form')
  absenden.click()
  await warte()
  const senden = mit('kalender_verwaltung.create_kalender')
  assert.equal(senden.length, 1, 'genau eine Anlege-Anfrage')
  const [, args] = senden[0]
  assert.equal(args.titel, 'Jugend')
  assert.equal(args.farbe, '#2266aa', 'die Standardfarbe des Servers ist vorgewählt')
  assert.equal(args.untergruppe, UNTERGRUPPE, 'die Untergruppe ist das Ziel')
  assert.equal(args.gruppe, undefined, 'genau EIN Ziel')
  assert.equal(args.standard_gruppe_lesen, 0, 'Antwort „Nein“')
  assert.ok(form)
})

test('UI-R2/M6: ein Fachfehler des Servers steht IM Dialog, die Eingabe bleibt', async () => {
  const { host } = await karteMounten()
  ueberschreibungen = {
    'create_kalender$': Object.assign(new Error('Ein Kalender mit dem Namen „Jugend“ gibt es schon.'),
      { status: 417 }),
  }
  await anlegenAusfuellen(host, { titel: 'Jugend' })
  const absenden = [...document.querySelectorAll('button')].find((b) => b.getAttribute('form') === 'ke-form')
  absenden.click()
  await warte(40)
  const form = await bereit('#ke-form')
  assert.ok(form, 'der Dialog bleibt offen')
  assert.match(form.textContent, /gibt es schon/)
  assert.equal(form.querySelector('input.dk-ui-eingabe').value, 'Jugend', 'die Eingabe bleibt stehen')
})
