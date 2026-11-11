/**
 * A11-N2 — Termin-Blatt am Handy: Restpunkte aus den Reviews A11 + A10-N3
 * (Karte t_1c627f29).
 *
 * Fünf Befunde, je ein Block:
 *
 *  1. KALENDER-ZEILE zeigte den internen Schlüssel („gruppen“) statt des
 *     Anzeigenamens. Geprüft: reine Regel (`blattKalender`) UND die
 *     Serverantwort (`get_calendar_events` liefert `calendar_title`).
 *  2. DUNKELMODUS: der Schleier hinter dem Blatt dunkelte über einer dunklen
 *     Seite praktisch nicht ab. Geprüft: der Schleier nimmt die EINE
 *     Überlagerungs-Quelle (`--overlay`), nicht mehr die feste Navy-Mischung.
 *  3. ABSTAND Titel → Abzeichen und das Ort-Symbol: Abstände aus der Skala,
 *     ALLE Zeilensymbole als Umriss (der Pin war gefüllt).
 *  4. TIPP im Monats-/Wochenraster öffnet IMMER zuerst das Blatt — auch im
 *     Bearbeiten-Modus (vorher sprang er direkt ins Formular).
 *  5. Escape wird GENAU EINMAL behandelt (Blatt UND `document`-Listener der
 *     View schlossen nacheinander) — am echten Mount gezählt.
 *
 * Der Test liest nur Dateien innerhalb von frontend/ bzw. backend/src
 * (Regel 13) und braucht kein Netz. Kein Test wird übersprungen.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
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
const REPO = resolve(FRONTEND, '..')
const liesBackend = (rel) => readFileSync(join(REPO, 'backend', 'src', 'diakronos_app', rel), 'utf8')

const B = await import(pathToFileURL(join(SRC, 'components/kronos/blattDaten.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Kalender-Zeile zeigt den Anzeigenamen, nie den internen Schlüssel
// ══════════════════════════════════════════════════════════════════════════
test('A11-N2: Kalender-Zeile — Anzeigename statt internem Schlüssel', () => {
  // Die Serverantwort trägt jetzt BEIDES: Schlüssel (Rechte/Filter) und Name.
  assert.equal(
    B.blattKalender({ element_calendar: 'gruppen', calendar_title: 'Gruppen & Kreise' }),
    'Gruppen & Kreise',
    'der Anzeigename steht im Blatt',
  )
  // Teilnehmerzahl bleibt daneben, wenn es sie gibt.
  assert.equal(
    B.blattKalender({ element_calendar: 'gruppen', calendar_title: 'Gruppen & Kreise', teilnehmer: 12 }),
    'Gruppen & Kreise · 12 Teilnehmer',
  )
  // `calendar_name` ist der zweite Name (andere Antwortformen) — auch er gilt.
  assert.equal(B.blattKalender({ element_calendar: 'gruppen', calendar_name: 'Gruppen' }), 'Gruppen')
  // Sieht der Server keinen Namen, bleibt KEIN roher Schlüssel stehen: der
  // Rückfall macht daraus einen lesbaren Namen (Muster A10-N2/Begriffsregel).
  assert.equal(B.blattKalender({ element_calendar: 'gruppen' }), 'Gruppen')
  assert.equal(B.blattKalender({ element_calendar: 'jugend_2026' }), 'Jugend 2026')
  // Eine echte Kennung (Ziffernblock) wird NICHT „verschönert“ — sie bleibt
  // erkennbar, statt einen erfundenen Namen vorzutäuschen.
  assert.equal(B.blattKalender({ element_calendar: 'cal-7f3a91' }), 'cal-7f3a91')
  // Nichts vorhanden → keine Zeile (kein „—“-Rauschen).
  assert.equal(B.blattKalender({}), '')
})

test('A11-N2: Zeilen — die Kalender-Zeile trägt den Anzeigenamen (ganzer Weg)', () => {
  const zeilen = B.blattZeilen({
    element_name: 'Herbstfreizeit Jugend',
    start: '2026-11-07 00:00:00',
    end: '2026-11-10 00:00:00',
    all_day: true,
    element_calendar: 'gruppen',
    calendar_title: 'Gruppen & Kreise',
  })
  const kalender = zeilen.find((z) => z.key === 'kalender')
  assert.ok(kalender, 'die Zeile existiert')
  assert.equal(kalender.text, 'Gruppen & Kreise')
  assert.notEqual(kalender.text, 'gruppen', 'nicht der interne Schlüssel')
  assert.equal(kalender.label, 'Kalender: Gruppen & Kreise')
})

test('A11-N2: Server — `get_calendar_events` liefert den Kalender-Anzeigenamen mit', () => {
  const quelle = liesBackend('api/kronos/calendar_get.py')
  const abschnitt = quelle.slice(quelle.indexOf('def get_calendar_events'),
    quelle.indexOf('def get_mein_termin'))
  // Der Name wird EINMAL je Termin aus dem Kalender gelesen …
  assert.match(abschnitt, /get_value\(\s*"Kalender",\s*element_calendar,\s*\["calendar_name", "calendar_color"\],\s*as_dict=True,?\s*\)/,
    'Kalendername wird gelesen')
  // … und liegt in den extendedProps, wo das Blatt ihn findet.
  assert.match(quelle, /"calendar_title": cal_info\.get\("calendar_name"\) or element_calendar/,
    'Anzeigename in extendedProps')
  // Der interne Schlüssel bleibt für Rechte/Filter erhalten.
  assert.match(abschnitt, /"element_calendar": element_calendar/)
  // Kein neuer Endpunkt: der Abschnitt bringt KEINE Schreibfunktion mit
  // (nur das vorhandene Lesen, ein Feld mehr).
  assert.doesNotMatch(abschnitt, /methods=\[/, 'keine schreibende whitelist-Funktion')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Dunkelmodus: der Schleier dunkelt ab (eine Überlagerungs-Quelle)
// ══════════════════════════════════════════════════════════════════════════
const BLATT_QUELLE = lies('components/kronos/TerminBlatt.vue')
const TOKENS = lies('tokens.css')

const schleierRegel = (quelle) => {
  const ohneKommentare = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  const treffer = ohneKommentare.match(/(^|\n)\.dk-blatt-schleier\s*\{([\s\S]*?)\}/)
  return treffer ? treffer[2] : ''
}

test('A11-N2: Schleier — nimmt die EINE Überlagerungs-Quelle (hell UND dunkel)', () => {
  const regel = schleierRegel(BLATT_QUELLE)
  assert.ok(regel, '.dk-blatt-schleier ist gestaltet')
  assert.match(regel, /background:\s*var\(--overlay\)/,
    'Abdunklung über das Token (Prinzip Ä4: Dark Mode über Variablen)')
  // Die alte feste Navy-Mischung war über einer dunklen Seite fast unsichtbar.
  assert.doesNotMatch(regel, /--dk-navy-900/,
    'keine Navy-Mischung mehr (dunkelt im Dunkelmodus nicht ab)')
  assert.doesNotMatch(regel, /color-mix\(/, 'keine eigene Mischung im Bauteil')
  // Das Token ist genau EINMAL definiert — die einzige Quelle.
  const definitionen = TOKENS.split('\n').filter((z) => /^\s*--overlay\s*:/.test(z))
  assert.equal(definitionen.length, 1, `--overlay genau einmal definiert (${definitionen.length})`)
  // Deckend genug, dass der Kalender dahinter klar zurücktritt (~50 %).
  assert.match(definitionen[0], /rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*(0?\.\d+|1)\s*\)/,
    'eine echte Abdunklung (Alpha)')
})

test('A11-N2: Schleier — gleiche Abdunklung wie jeder andere Dialog', () => {
  const modal = lies('components/kronos/KronosEventView.vue')
  assert.match(modal, /background:\s*color-mix\(in oklch, var\(--dk-navy-900\) 55%, transparent\)/,
    'der Desktop-Dialog bleibt wie er ist (A4)')
  // Beleg, dass `--overlay` die gemeinsame Quelle von Masken ist:
  assert.match(lies('index.css'), /background:\s*var\(--overlay\)/)
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Abstand Titel → Abzeichen, Ort-Symbol als Umriss
// ══════════════════════════════════════════════════════════════════════════
const cssBlock = (quelle, selektor) => {
  const ohneKommentare = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  const treffer = ohneKommentare.match(new RegExp('(^|\\n)\\.' + selektor + '\\s*\\{([\\s\\S]*?)\\}'))
  return treffer ? treffer[2] : ''
}

test('A11-N2: Abstände im Blatt — Kopf, Körper und Zeilen aus der Skala', () => {
  // Der Kopf schließt mit EINEM Abstand aus der Skala zum Körper ab …
  const kopf = cssBlock(BLATT_QUELLE, 'dk-blatt-kopf')
  assert.match(kopf, /padding:\s*0 var\(--pad\) var\(--sp-[1-8]\)/, `Kopf-Abstand aus der Skala: ${kopf}`)
  // … und der Körper stapelt danach einen ebenso kleinen Abstand, nicht zwei
  // große hintereinander (das war die „große Lücke“ unter dem Titel).
  const koerper = cssBlock(BLATT_QUELLE, 'dk-blatt-koerper')
  assert.match(koerper, /gap:\s*var\(--sp-[12]\)/, `Körper-Abstand klein: ${koerper}`)
  // Die Titelzeile selbst trägt keine zusätzliche Luft nach unten. `margin: 0`
  // ist der Reset (Browser geben `h2` sonst 0.83em) — der Abstand kommt allein
  // aus dem Kopf (Skala).
  const titel = cssBlock(BLATT_QUELLE, 'dk-blatt-titel')
  assert.match(titel, /margin:\s*0/, 'Absatz-Reset: kein eigener Abstand am Titel')
  // Das Abzeichen bringt keinen zweiten Abstand mit (der Körper regelt ihn).
  const status = cssBlock(BLATT_QUELLE, 'dk-blatt-status')
  assert.doesNotMatch(status, /margin|padding/, `Abzeichen ohne eigene Luft: ${status}`)
})

test('A11-N2: Ort-Symbol — Umriss wie die übrigen Symbole', () => {
  // Kein gefülltes Einzelstück mehr: alle Zeilensymbole werden gleich gezeichnet.
  assert.doesNotMatch(BLATT_QUELLE, /:gefuellt=/, 'kein Sonderweg für ein Symbol')
  assert.match(BLATT_QUELLE, /<DkSymbol :name="z\.symbol" :groesse="18"\s*\/>/,
    'ein Aufruf für alle Zeilen')
  // Der Vorrat bleibt unangetastet: der Pin ist weiter als Umriss definiert
  // und wird NICHT mehr gefüllt gezeichnet (kein `GEFUELLT`-Einsatz im Blatt).
  const symbole = lies('components/ui/symbole.mjs')
  assert.match(symbole, /\n  ort:\s*\{/)
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Tipp im Raster: IMMER zuerst das Blatt (auch im Bearbeiten-Modus)
// ══════════════════════════════════════════════════════════════════════════
const SEITE = lies('pages/Kalender.vue')

/** Der Quelltext-Abschnitt einer Funktion, bis zur nächsten Deklaration. */
function funktion(quelle, name) {
  const start = quelle.indexOf(`function ${name}(`)
  assert.ok(start > -1, `Funktion ${name} fehlt`)
  const rest = quelle.slice(start)
  const ende = rest.search(/\n(?=(\/\*\*|function |const |let |onMounted|watch\())/)
  return ende === -1 ? rest : rest.slice(0, ende)
}

test('A11-N2: Raster-Tipp öffnet IMMER das Blatt — kein Sprung ins Formular', () => {
  const klick = funktion(SEITE, 'onEventClickMobil')
  assert.doesNotMatch(klick, /showEdit\.value\s*=\s*true/, 'kein direkter Formular-Sprung mehr')
  assert.doesNotMatch(klick, /isViewMode|hasWriteRight|series_id/,
    'kein Sonderweg nach Modus/Recht/Serie (ein Verhalten für alle)')
  assert.match(klick, /terminOeffnenMobil\(daten\)/, 'derselbe Weg wie die Listenzeile')
})

test('A11-N2: Listenzeile und Raster-Tipp führen in DIESELBE Funktion', () => {
  // Die Zeile der Tagesliste ruft `terminOeffnenMobil`, das Raster ebenfalls —
  // ein Verhalten, eine Stelle (Prinzip S4).
  const klick = funktion(SEITE, 'onEventClickMobil')
  const oeffnen = funktion(SEITE, 'terminOeffnenMobil')
  assert.match(klick, /terminOeffnenMobil\(/)
  assert.match(oeffnen, /showView\.value = true/, 'das Blatt öffnet sich')
  // Aus dem Blatt führt der vorhandene Knopf ins Formular (mit Recht).
  assert.match(SEITE, /@bearbeiten="ausBlattBearbeiten"/)
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Escape genau einmal — am echten Mount gezählt
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'TouchEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'a11n2-'))
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
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (v, spec) => {
    const ziel = resolve(dirname(abs), spec)
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const zielDatei = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
const tick = () => new Promise((loese) => setTimeout(loese, 0))

/** Termin des Entwurfs A11 (Moderator, offener Vorschlag). */
function herbstfreizeit(extra = {}) {
  return {
    name: 'EV-1',
    id: 'EV-1',
    element_name: 'Herbstfreizeit Jugend',
    start: '2026-11-07 00:00:00',
    end: '2026-11-10 00:00:00',
    all_day: true,
    status: 'Vorschlag',
    antragsteller: 'J. Rehberg',
    ressource_name: 'Freizeitheim Sonnenhof, Musterstadt',
    element_calendar: 'gruppen',
    calendar_title: 'Gruppen & Kreise',
    teilnehmer: 12,
    description: 'Anreise Freitag ab 16:00 mit dem Bus.',
    ...extra,
  }
}

/** Mountet das Blatt und sammelt, was es nach oben meldet. */
async function blattMounten(eigenschaften) {
  document.body.innerHTML = ''
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/TerminBlatt.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const gemeldet = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({ p: eigenschaften, gemeldet }),
    template: '<Geprueft v-bind="p" @schliessen="gemeldet.push(1)" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { app, warnungen, gemeldet, weg: () => app.unmount() }
}

test('A11-N2: GEMOUNTET — Escape im Blatt schließt GENAU EINMAL', async () => {
  const { app, gemeldet, warnungen, weg } = await blattMounten({
    show: true, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true,
  })
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  const blatt = document.body.querySelector('.dk-blatt')
  assert.ok(blatt, 'Blatt ist offen')
  const ereignis = new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
  blatt.dispatchEvent(ereignis)
  await tick()
  assert.equal(ereignis.defaultPrevented, true, 'Escape ist verarbeitet')
  assert.equal(gemeldet.length, 1, `genau EIN Schließen (${gemeldet.length})`)
  weg()
  document.body.innerHTML = ''
})

test('A11-N2: GEMOUNTET — Escape außerhalb des Blattes schließt ebenfalls genau einmal', async () => {
  const { app, gemeldet, weg } = await blattMounten({
    show: true, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true,
  })
  // Fokus liegt irgendwo in der Seite (z. B. im Raster): nur der
  // `document`-Verteiler des Blattes sieht das Ereignis. Der Zielpunkt ist
  // EIN Element im Dokument — wie beim Tippen im Raster.
  const aussen = document.createElement('div')
  aussen.tabIndex = 0
  document.body.appendChild(aussen)
  const ereignis = new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
  aussen.dispatchEvent(ereignis)
  await tick()
  assert.equal(ereignis.defaultPrevented, true, 'der Verteiler hat es verarbeitet')
  assert.equal(gemeldet.length, 1, `genau EIN Schließen (${gemeldet.length})`)
  weg()
  document.body.innerHTML = ''
})

test('A11-N2: View — am Handy kein zweiter Escape-Weg, am Desktop bleibt er', () => {
  const view = lies('components/kronos/KronosEventView.vue')
  const keydown = view.slice(view.indexOf('function onKeydown'), view.indexOf('// A11: Blatt (Handy)'))
  assert.match(keydown, /key === 'Escape' && !props\.handyLage/,
    'der document-Listener übernimmt am Handy NICHT (das Blatt schließt)')
  assert.match(keydown, /emit\('update:show', false\)/, 'am Desktop schließt Escape das Fenster')
  // Der Verteiler im Blatt hält doppelte Behandlung auf: markiert + stoppt.
  assert.match(BLATT_QUELLE, /__dkBlattVerteilt/,
    'das Blatt merkt sich verteilte Ereignisse und meldet sie nur einmal')
  assert.match(BLATT_QUELLE, /ereignis\.stopPropagation\(\)/,
    'das Blatt hält sein Escape an')
})

test('A11-N2: GEMOUNTET — das Blatt zeigt den Kalender-Anzeigenamen', async () => {
  const { app, weg } = await blattMounten({
    show: true, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true,
  })
  const zeile = document.body.querySelector('[data-zeile="kalender"]')
  assert.ok(zeile, 'die Kalender-Zeile steht im Blatt')
  assert.equal(zeile.querySelector('.dk-blatt-text').textContent.trim(), 'Gruppen & Kreise · 12 Teilnehmer')
  assert.ok(!zeile.textContent.includes('gruppen'), 'kein interner Schlüssel im Blatt')
  // Alle drei Zeilensymbole sind Umrisse (kein gefülltes Einzelstück).
  const gefuellt = document.body.querySelectorAll('.dk-blatt-symbol .is-gefuellt')
  assert.equal(gefuellt.length, 0, `kein gefülltes Zeilensymbol (${gefuellt.length})`)
  weg()
  document.body.innerHTML = ''
})
