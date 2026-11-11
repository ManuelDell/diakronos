/**
 * A11 — Termin-Blatt auf dem Handy nach Entwurf A11 (Karte t_3c23f0a5).
 *
 * Geprüft wird, was die Karte VERLANGT — ausgeführt, nicht als Quelltext-
 * Muster, wo es ausführbar ist:
 *
 *  1. ZEILEN des Blattes (`blattDaten.mjs`): Titel, Datum/Zeit (auch der
 *     ganztägige Mehrtages-Fall des Entwurfs „Fr 7. – So 9. November ·
 *     ganztägig“), Ort, Kalender, Beschreibung, Status.
 *  2. HANDLUNGEN: Moderator + offener Vorschlag → „Freigeben“ als EIN
 *     Primärknopf, „Ablehnen/Absagen“ und „Löschen“ im ⋯; Mitglied bzw.
 *     bestätigter Termin → nur Ansicht (kein Knopf, kein ⋯).
 *  3. SCHLIESSEN: Escape, Fläche dahinter, Wischen nach unten (Strecke und
 *     Tempo), Fokusfalle (Tab bleibt im Blatt).
 *  4. TIPPZIELE ≥ 44 px (K4) und Notfall-Größen aus `tokens.css`.
 *  5. GEMOUNTET (jsdom, echte SFC): das Blatt mit Moderator-Daten, das Blatt
 *     als Mitglied, und der Weg der Seite (Tipp auf eine Zeile öffnet das
 *     Blatt, nicht das Formular).
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz.
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

const B = await import(pathToFileURL(join(SRC, 'components/kronos/blattDaten.mjs')).href)
const T = await import(pathToFileURL(join(SRC, 'components/kronos/mobilTermin.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 0 · Beispiel-Daten des Entwurfs („Herbstfreizeit Jugend“, Fr 7. – So 9. 11.)
// ══════════════════════════════════════════════════════════════════════════
/** Termin aus `get_mein_termin` (Detailantwort, flache Felder). */
function herbstfreizeit(extra = {}) {
  return {
    name: 'EV-1',
    id: 'EV-1',
    element_name: 'Herbstfreizeit Jugend',
    title: 'Herbstfreizeit Jugend',
    start: '2026-11-07 00:00:00',
    end: '2026-11-10 00:00:00',     // exklusiv: bis einschließlich 9.11.
    all_day: true,
    status: 'Vorschlag',
    antragsteller: 'J. Rehberg',
    ressource_name: 'Freizeitheim Sonnenhof, Musterstadt',
    element_calendar: 'Jugend',
    teilnehmer: 12,
    description: 'Anreise Freitag ab 16:00 mit dem Bus.\n\nBibelarbeit, Geländespiele und Lagerfeuer.\nRückkehr Sonntag gegen 17:00.',
    ...extra,
  }
}

const MITGLIED_TERMIN = {
  name: 'EV-2',
  element_name: 'Gottesdienst',
  start: '2026-11-08 10:00:00',
  end: '2026-11-08 11:30:00',
  all_day: false,
  status: 'Festgelegt',
  ressource_name: 'Gemeindehaus',
  element_calendar: 'Gottesdienste',
  description: 'Predigt: A. Weber',
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Zeitzeile — Datum und Zeit wie im Entwurf
// ══════════════════════════════════════════════════════════════════════════
test('A11: Zeitzeile — „Fr 7. – So 9. November · ganztägig“ (Entwurf A11)', () => {
  const zeile = B.blattZeile(herbstfreizeit())
  // Der Mehrtages-Fall des Entwurfs: Wochentag KURZ links und rechts, Monat
  // EINMAL rechts (der Wochentag hängt an der Zeitzone des Rechners — die
  // FORM ist der Vertrag, nicht das „Fr“; im Betrieb steht dort dasselbe wie
  // im Entwurf, weil der Server Ortszeit liefert).
  assert.match(zeile, /^[A-ZÄÖÜ][a-zäöü]{1} 7\. – [A-ZÄÖÜ][a-zäöü]{1} 9\. November · ganztägig$/,
    `Zeile: ${zeile}`)
  // Ende EXKLUSIV: der 10.11. 00:00 gehört nicht mehr dazu.
  assert.equal(B.letzterTag('2026-11-07 00:00:00', '2026-11-10 00:00:00').getDate(), 9)
  // Ohne Ende bleibt es beim Starttag — dort MIT ausgeschriebenem Wochentag.
  assert.match(B.blattZeile({ start: '2026-11-07 00:00:00', all_day: true }),
    /^Samstag, 7\. November · ganztägig$/)
})

test('A11: Zeitzeile — Uhrzeiten werden angezeigt, nicht erfunden', () => {
  assert.equal(B.blattZeile(MITGLIED_TERMIN), 'Sonntag, 8. November · 10:00 – 11:30')
  assert.equal(B.blattZeile({ start: '2026-11-08 10:00:00' }), 'Sonntag, 8. November · 10:00',
    'ohne Ende nur der Beginn')
  // Kaputte/fehlende Daten: keine Zeile (kein „Invalid Date“).
  assert.equal(B.blattZeile({}), '')
  assert.equal(B.blattZeile(null), '')
  assert.equal(B.blattZeile({ start: 'kein datum' }), '')
})

test('A11: Zeitzeile — mehrtägig MIT Uhrzeit nennt keinen falschen „ganztägig“-Hinweis', () => {
  const zeile = B.blattZeile({
    start: '2026-11-07 16:00:00', end: '2026-11-09 18:00:00', all_day: false,
  })
  assert.match(zeile, /^[A-ZÄÖÜ][a-zäöü]{1} 7\. – [A-ZÄÖÜ][a-zäöü]{1} 8\. November$/,
    `ohne „ganztägig“: ${zeile}`)
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Ort, Kalender, Beschreibung
// ══════════════════════════════════════════════════════════════════════════
test('A11: Ort — Hauptressource, sonst die erste zusätzliche, sonst nichts', () => {
  assert.equal(B.blattOrt(herbstfreizeit()), 'Freizeitheim Sonnenhof, Musterstadt')
  assert.equal(B.blattOrt({
    zusaetzliche_ressourcen: [{ ressource_name: 'Fam. Kirsch' }],
  }), 'Fam. Kirsch', 'ohne Hauptressource zählt die erste zusätzliche')
  assert.equal(B.blattOrt({ zusaetzliche_ressourcen: [{ freitext_ressource: 'Garten' }] }), 'Garten')
  assert.equal(B.blattOrt({}), '', 'kein Ort → keine Zeile')
})

test('A11: Kalender-Zeile — Kalender, Teilnehmerzahl nur wenn vorhanden', () => {
  assert.equal(B.blattKalender(herbstfreizeit()), 'Jugend · 12 Teilnehmer')
  assert.equal(B.blattKalender({ element_calendar: 'Jugend' }), 'Jugend', 'keine erfundene Zahl')
  assert.equal(B.blattKalender({}), '')
})

test('A11: Zeilen — Entwurfsreihenfolge Zeit · Ort · Kalender mit Symbolen', () => {
  const zeilen = B.blattZeilen(herbstfreizeit())
  assert.deepEqual(zeilen.map((z) => z.key), ['zeit', 'ort', 'kalender'])
  assert.deepEqual(zeilen.map((z) => z.symbol), ['uhr', 'ort', 'gruppe'])
  // Vorlesehilfe nennt, worum es geht (Farbe/Symbol nie alleiniger Träger).
  assert.match(zeilen[0].label,
    /^Zeit: [A-ZÄÖÜ][a-zäöü]{1} 7\. – [A-ZÄÖÜ][a-zäöü]{1} 9\. November · ganztägig$/)
  // Symbole stehen im Vorrat (sonst zeichnet DkSymbol still nichts).
  const vorrat = lies('components/ui/symbole.mjs')
  for (const name of ['uhr', 'ort', 'gruppe']) {
    assert.match(vorrat, new RegExp(`\\b${name}:\\s*\\{`), `Symbol „${name}“ fehlt im Vorrat`)
  }
})

test('A11: Beschreibung — Zeilen ohne Leerzeilen, leer bleibt leer', () => {
  assert.deepEqual(B.blattBeschreibung(herbstfreizeit()), [
    'Anreise Freitag ab 16:00 mit dem Bus.',
    'Bibelarbeit, Geländespiele und Lagerfeuer.',
    'Rückkehr Sonntag gegen 17:00.',
  ])
  assert.deepEqual(B.blattBeschreibung({}), [])
})

test('A11: Status — offener Vorschlag trägt „Zu prüfen · eingetragen von …“', () => {
  assert.deepEqual(T.statusBadgeFuer(herbstfreizeit()),
    { text: 'Zu prüfen · eingetragen von J. Rehberg', variant: 'warn' })
  assert.deepEqual(T.statusBadgeFuer(MITGLIED_TERMIN), { text: 'Bestätigt', variant: 'ok' })
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Handlungen: Freigeben primär, Gefährliches ins ⋯, Mitglied nur Ansicht
// ══════════════════════════════════════════════════════════════════════════
test('A11: Moderator + offener Vorschlag — EIN Primärknopf „Freigeben“', () => {
  const knoepfe = B.blattKnoepfe({ darfPruefen: true, darfBearbeiten: true, offen: true })
  assert.deepEqual(knoepfe.map((k) => k.label), ['Bearbeiten', 'Freigeben'])
  assert.equal(knoepfe.filter((k) => k.primaer).length, 1, 'genau ein Primärknopf je Ansicht')
  assert.equal(knoepfe.find((k) => k.key === 'freigeben').variant, 'primary')
  assert.equal(knoepfe.find((k) => k.key === 'bearbeiten').variant, 'secondary')
})

test('A11: „Ablehnen/Absagen“ und „Löschen“ stehen im ⋯, nie neben dem Primärknopf (K4)', () => {
  const menue = T.terminBlattAktionen({ darfPruefen: true, darfBearbeiten: true, primaerFreigeben: true })
  assert.deepEqual(menue.map((e) => e.key), ['absagen', 'loeschen'])
  assert.equal(menue.find((e) => e.key === 'loeschen').gefahr, true, 'Löschen zuletzt und rot')
  const knoepfe = B.blattKnoepfe({ darfPruefen: true, darfBearbeiten: true, offen: true })
  for (const verboten of ['Absagen', 'Ablehnen', 'Löschen']) {
    assert.ok(!knoepfe.some((k) => k.label === verboten), `„${verboten}“ darf kein Knopf sein`)
  }
})

test('A11: Mitglied bzw. bestätigter Termin — NUR Ansicht, keine Handlung', () => {
  // Mitglied (kein Prüfrecht), bestätigter Termin, Lesemodus: nichts.
  assert.deepEqual(B.blattKnoepfe({ darfPruefen: false, darfBearbeiten: false, offen: false }), [])
  assert.equal(B.blattHatAktionen({}), false)
  assert.deepEqual(T.terminBlattAktionen({}), [])
  // Moderator bei einem BESTÄTIGTEN Termin: kein Freigeben (nichts zu prüfen).
  const bestaetigt = B.blattKnoepfe({ darfPruefen: true, darfBearbeiten: false, offen: false })
  assert.deepEqual(bestaetigt, [], 'kein „Freigeben“ für einen bestätigten Termin')
  assert.equal(B.blattHatAktionen({ darfPruefen: true, offen: false }), false,
    'ohne offenen Vorschlag und ohne Bearbeiten-Recht: kein ⋯ (nur Ansicht)')
  // Das ⋯ eines offenen Vorschlags trägt das Absagen (getrennt vom Übrigen);
  // Löschen steht dort nur mit Löschrecht (Bearbeiten-Modus), hier ohne.
  assert.deepEqual(
    T.terminBlattAktionen({ darfPruefen: true, primaerFreigeben: true }).map((e) => e.key),
    ['absagen'])
  assert.deepEqual(
    T.terminBlattAktionen({ darfPruefen: true, primaerFreigeben: true, darfBearbeiten: true })
      .map((e) => e.key),
    ['absagen', 'loeschen'])
})

test('A11: Bearbeiten nur mit Recht UND im Bearbeiten-Modus (Lesemodus UX3i)', () => {
  assert.deepEqual(B.blattKnoepfe({ darfPruefen: true, offen: true, darfBearbeiten: false })
    .map((k) => k.key), ['freigeben'], 'ohne Bearbeiten-Recht kein „Bearbeiten“')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Schließen: Wischen nach unten, Fokusfalle
// ══════════════════════════════════════════════════════════════════════════
test('A11: Wischen nach unten — Strecke, Tempo und „nach oben zählt nicht“', () => {
  assert.equal(B.wischAuswerten({ startY: 100, endeY: 100 + B.WISCH_SCHLIESSEN }).schliessen, true)
  assert.equal(B.wischAuswerten({ startY: 100, endeY: 140 }).schliessen, false, 'wenig Weg, langsam')
  // Kurzer, schneller Wisch (Flick) schließt ebenfalls.
  assert.equal(B.wischAuswerten({ startY: 100, endeY: 140, dauer: 40 }).schliessen, true,
    '40 px in 40 ms = 1 px/ms')
  // Nach OBEN schließt nie.
  assert.equal(B.wischAuswerten({ startY: 300, endeY: 120, dauer: 30 }).schliessen, false)
  assert.equal(B.wischAuswerten({ startY: 300, endeY: 120, dauer: 30 }).zug, 0)
})

test('A11: Fokusfalle — Tab bleibt im Blatt, Umschalt+Tab läuft rückwärts', () => {
  const a = { id: 'a' }, b = { id: 'b' }, c = { id: 'c' }
  const liste = [a, b, c]
  assert.equal(B.fokusIndex(liste, a, 1), 1)
  assert.equal(B.fokusIndex(liste, c, 1), 0, 'am Ende geht es vorne weiter')
  assert.equal(B.fokusIndex(liste, a, -1), 2, 'rückwärts vom ersten zum letzten')
  assert.equal(B.fokusIndex(liste, null, 1), 0, 'Fokus außerhalb → erster')
  assert.equal(B.fokusIndex(liste, { id: 'x' }, -1), 2, 'Fokus außerhalb rückwärts → letzter')
  assert.equal(B.fokusIndex([], a, 1), -1)
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Bauteil: Quelltext-Vertrag (Tippziele, Schließen, keine festen Farben)
// ══════════════════════════════════════════════════════════════════════════
const BLATT_QUELLE = lies('components/kronos/TerminBlatt.vue')

test('A11: Blatt — Schließen über Escape, Fläche dahinter und Wischen', () => {
  assert.match(BLATT_QUELLE, /@click="beiSchleierKlick"/, 'Fläche dahinter schließt')
  assert.match(BLATT_QUELLE, /@pointerdown="beiDruck"/,
    'ein Klick, der IM Blatt beginnt, schließt nicht (Lage am Druck gemerkt)')
  assert.match(BLATT_QUELLE, /ereignis\.key === 'Escape'/, 'Escape schließt')
  assert.match(BLATT_QUELLE, /@touchstart\.passive="wischStart"/, 'Wischen wird gemessen')
  assert.match(BLATT_QUELLE, /wischAuswerten\(/, 'dieselbe Wisch-Regel wie oben geprüft')
  assert.match(BLATT_QUELLE, /role="dialog"[\s\S]{0,200}aria-modal="true"/, 'Fenster-Semantik')
})

test('A11: Blatt — Tippziele ≥ 44 px und Abstände aus der Skala', () => {
  assert.match(BLATT_QUELLE, /\.dk-blatt-schliessen[\s\S]{0,400}width: var\(--treffer-handy\)/,
    'Schließen auf 44 px')
  assert.match(BLATT_QUELLE, /\.dk-blatt-(mehr|griff-zone)[\s\S]{0,400}var\(--treffer-handy\)/)
  assert.match(BLATT_QUELLE, /\.dk-blatt-knopf[\s\S]{0,200}min-height: var\(--control-h\)/)
  // KEINE festen Farben (Wächter-Regel): nur `var(--…)` und `color-mix` auf Tokens.
  const ohneKommentare = BLATT_QUELLE.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(ohneKommentare, /#[0-9a-fA-F]{3,8}\b/, 'keine Hex-Farben')
  assert.doesNotMatch(ohneKommentare, /\brgba?\s*\(/, 'kein rgb()/rgba()')
  // A11-N2 (Punkt 2): Die Abdunklung kommt aus dem EINEN Überlagerungs-Token
  // (`--overlay`, hell wie dunkel deckend) — die frühere feste Navy-Mischung
  // war über einer dunklen Seite praktisch unsichtbar. Geprüft in
  // `tests/a11n2-termin-blatt-restpunkte.test.mjs`.
  assert.match(BLATT_QUELLE, /background: var\(--overlay\)/)
})

test('A11: Blatt — Kopf mit Titel und ⋯, Handlungsleiste mit EINEM Primärknopf', () => {
  assert.match(BLATT_QUELLE, /class="dk-blatt-titel"/)
  assert.match(BLATT_QUELLE, /<DkAktionen[\s\S]{0,300}eintraege="menueEintraege"/)
  assert.match(BLATT_QUELLE, /:data-primaer="k\.primaer \? '1' : null"/)
  // Symbole sitzen auf der Textlinie (Auflage Manuel 04.11.): Zeile ist
  // Flex mit `align-items: center`, das Symbol eine feste Spalte.
  assert.match(BLATT_QUELLE, /\.dk-blatt-zeile \{[\s\S]{0,120}align-items: center/)
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · GEMOUNTET (jsdom): das echte Blatt, als Moderator und als Mitglied
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'TouchEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'a11-'))
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
/** Zwei Runden: Zustand → Render → Zustand (Fokus/Teleport-Nachlauf). */
const nextTickZwei = async () => {
  await Vue.nextTick()
  await Vue.nextTick()
}

/** AUFRÄUMEN — frische Fläche je Test.
 *
 * `document.body.innerHTML = ''` am Testende reicht NICHT: Vue hielte Effekte
 * und Fokus-Registrierungen des alten Blattes weiter (der Fokus sprang dann
 * in einen Rest aus dem vorigen Test). Jeder Test räumt deshalb VORHER auf.
 */
function leeren() {
  document.body.innerHTML = ''
}

let letzte = null
async function mounten(datei, eigenschaften) {
  leeren()
  try { letzte?.app?.unmount() } catch (_) { /* schon weg */ }
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const gemeldet = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({
      p: eigenschaften,
      gemeldet,
      merke: (name, ...args) => gemeldet.push([name, ...args]),
    }),
    template: `<Geprueft v-bind="p"
      @schliessen="merke('schliessen')"
      @update:show="merke('schliessen')"
      @freigeben="merke('freigeben', $event)"
      @bearbeiten="merke('bearbeiten', $event)"
    />`,
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  letzte = { app }
  return {
    host, app, warnungen, gemeldet,
    neu: async (neue) => { Object.assign(eigenschaften, neue); await tick() },
    // Nur für Tests, die das Blatt über `show` öffnen/schließen: altes
    // Gerüst abräumen, sonst bliebe sein Fokus-Listener lebendig.
    weg: () => app.unmount(),
  }
}

const knopf = (text) => [...document.body.querySelectorAll('button')]
  .find((b) => b.textContent.trim() === text)

test('A11: GEMOUNTET — Moderator sieht Freigeben (primär), Absagen/Löschen nur im ⋯', async () => {
  const { warnungen, gemeldet } = await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: herbstfreizeit(), laedt: false,
    darfPruefen: true, bearbeitenErlaubt: true,
  })
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  // Inhalt des Entwurfs steht da.
  assert.equal(document.body.querySelector('.dk-blatt-titel').textContent.trim(), 'Herbstfreizeit Jugend')
  assert.match(document.body.textContent, /[A-ZÄÖÜ][a-zäöü]{1} 7\. – [A-ZÄÖÜ][a-zäöü]{1} 9\. November · ganztägig/)
  assert.match(document.body.textContent, /Freizeitheim Sonnenhof, Musterstadt/)
  assert.match(document.body.textContent, /Jugend · 12 Teilnehmer/)
  assert.match(document.body.textContent, /Zu prüfen · eingetragen von J\. Rehberg/)
  assert.match(document.body.textContent, /Anreise Freitag ab 16:00/)

  // Genau EIN Primärknopf, und zwar „Freigeben“.
  const primaer = document.body.querySelectorAll('[data-primaer="1"]')
  assert.equal(primaer.length, 1, 'genau ein Primärknopf je Ansicht')
  assert.equal(primaer[0].textContent.trim(), 'Freigeben')
  assert.ok(knopf('Bearbeiten'), '„Bearbeiten“ als sekundärer Knopf')
  assert.equal(knopf('Löschen'), undefined, 'Löschen ist kein Knopf (K4)')
  assert.equal(knopf('Absagen'), undefined, 'Absagen ist kein Knopf (K4)')

  // „Freigeben“ meldet die Handlung nach oben — die Seite führt sie aus.
  primaer[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(gemeldet.at(-1)[0], 'freigeben')
  assert.equal(gemeldet.at(-1)[1].aktion, 'freigeben')

  // Das ⋯ trägt Absagen und Löschen (Löschen zuletzt, gefährlich).
  document.body.querySelector('.dk-blatt-mehr .dk-ui-aktionen-ausloeser')
    .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  const eintraege = [...document.body.querySelectorAll('.dk-ui-aktionen-eintrag')]
    .map((e) => e.textContent.trim())
  assert.deepEqual(eintraege, ['Absagen', 'Löschen'])

  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Mitglied sieht nur an, kein Knopf, kein ⋯', async () => {
  const { warnungen } = await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: MITGLIED_TERMIN, laedt: false,
    darfPruefen: false, bearbeitenErlaubt: false,
  })
  assert.deepEqual(warnungen, [])
  assert.equal(document.body.querySelector('.dk-blatt-aktionen'), null, 'keine Handlungsleiste')
  assert.equal(document.body.querySelector('.dk-blatt-mehr'), null, 'kein ⋯')
  assert.equal(document.body.querySelectorAll('[data-primaer="1"]').length, 0)
  // Ansicht bleibt vollständig: Titel, Zeit, Ort, Kalender, Status.
  assert.match(document.body.textContent, /Gottesdienst/)
  assert.match(document.body.textContent, /Sonntag, 8\. November · 10:00 – 11:30/)
  assert.match(document.body.textContent, /Gemeindehaus/)
  assert.match(document.body.textContent, /Bestätigt/)
  // Schließen bleibt möglich (44-px-Knopf statt ⋯).
  const zu = document.body.querySelector('.dk-blatt-schliessen')
  assert.ok(zu, 'ohne Menü gibt es den Schließen-Knopf')
  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Moderator bei BESTÄTIGTEM Termin: kein Freigeben', async () => {
  await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: { ...MITGLIED_TERMIN }, laedt: false,
    darfPruefen: true, bearbeitenErlaubt: true,
  })
  const primaer = [...document.body.querySelectorAll('[data-primaer="1"]')]
    .map((b) => b.textContent.trim())
  assert.deepEqual(primaer, [], 'nichts freizugeben → kein Primärknopf')
  assert.ok(knopf('Bearbeiten'), 'Bearbeiten bleibt (Bearbeiten-Modus)')
  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Moderator im Lesemodus: Absagen im ⋯, kein Löschen/Bearbeiten (Review)', async () => {
  await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: herbstfreizeit(), laedt: false,
    darfPruefen: true, bearbeitenErlaubt: false,
  })
  assert.equal(knopf('Bearbeiten'), undefined, 'ohne Bearbeiten-Modus kein Bearbeiten')
  document.body.querySelector('.dk-blatt-mehr .dk-ui-aktionen-ausloeser')
    .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  const eintraege = [...document.body.querySelectorAll('.dk-ui-aktionen-eintrag')]
    .map((e) => e.textContent.trim())
  assert.deepEqual(eintraege, ['Absagen'], 'Absagen hängt am offenen Vorschlag, Löschen am Recht')
  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Escape und Fläche dahinter schließen das Blatt', async () => {
  const { gemeldet } = await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true,
  })
  const schleier = document.body.querySelector('.dk-blatt-schleier')
  assert.ok(schleier, 'Schleier liegt über der Seite')
  // Ein Tipp beginnt und endet auf der Fläche dahinter (pointerdown + click).
  schleier.dispatchEvent(new dom.window.Event('pointerdown', { bubbles: true }))
  schleier.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['schliessen'], 'Fläche dahinter schließt')
  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Escape schließt (Tastatur) und setzt den Fokus zurück', async () => {
  const lage = Vue.reactive({ show: false, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true })
  const { gemeldet, weg } = await mounten('components/kronos/TerminBlatt.vue', lage)
  // Öffnen wie im Betrieb: ein Knopf der Seite trägt den Fokus, die Seite
  // schaltet `show` ein.
  const zurueck = document.createElement('button')
  zurueck.textContent = 'Aufrufer'
  document.body.appendChild(zurueck)
  zurueck.focus()
  lage.show = true
  await nextTickZwei()
  const blatt = document.body.querySelector('.dk-blatt')
  assert.ok(blatt, 'Blatt ist offen')
  // Der Fokus liegt nach dem Öffnen im Blatt (nicht dahinter).
  assert.ok(blatt.contains(document.activeElement), 'Fokus im Blatt')
  blatt.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['schliessen'], 'Escape schließt')
  // Das Ziel des Fokus-Nachlaufs ist gemerkt (der Auslöser, nicht `<body>`).
  // `focus()` selbst führt jsdom hier nicht aus (das Blatt liegt im Teleport
  // an `<body>`, die Fokusprüfung von jsdom greift dort nicht) — das Muster
  // „Fokus vor dem Schließen zurückgeben“ steht im Quelltext-Vertrag unten.
  assert.equal(blatt.dataset.fokusZurueck, 'Aufrufer', 'Fokus geht zum Aufrufer zurück')
  // Und nach dem Schließen ist das Blatt aus dem DOM.
  lage.show = false
  await nextTickZwei()
  assert.equal(document.body.querySelector('.dk-blatt'), null)
  weg()
  document.body.innerHTML = ''
})

test('A11: GEMOUNTET — Fokusfalle: Tab am letzten Knopf springt zum ersten', async () => {
  const { weg } = await mounten('components/kronos/TerminBlatt.vue', {
    show: true, event: herbstfreizeit(), darfPruefen: true, bearbeitenErlaubt: true,
  })
  const blatt = document.body.querySelector('.dk-blatt')
  // Drei Bedienelemente im Blatt: ⋯, „Bearbeiten“, „Freigeben“.
  const fokus = [...blatt.querySelectorAll(B.FOKUS_SELEKTOR)]
  assert.equal(fokus.length, 3, `das Blatt hat drei Bedienelemente (${fokus.length})`)
  const letzter = fokus[fokus.length - 1]
  letzter.focus()
  const ereignis = new dom.window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
  letzter.dispatchEvent(ereignis)
  await tick()
  assert.equal(ereignis.defaultPrevented, true, 'der Browser springt NICHT aus dem Blatt')
  // Ziel der Fokusfalle: der ERSTE Eintrag (die Regel `fokusIndex` ist oben
  // ohne DOM geprüft, hier wird ihre Anwendung am gemounteten Blatt geprüft).
  assert.equal(blatt.dataset.fokusZiel, '0', 'Fokus läuft vorne weiter')
  weg()
  document.body.innerHTML = ''
})

test('A11: Seite — ein Tipp auf einen Termin öffnet das BLATT, nicht das Formular', () => {
  const seite = lies('pages/Kalender.vue')
  // A11-N2: Der Abschnitt endet an der Klammer von `terminOeffnenMobil` — die
  // nächste Deklaration ist jetzt `onEventClickMobil` (Raster-Tipp), und der
  // Weg ins Formular (`ausBlattBearbeiten`) steht weiter unten.
  const start = seite.indexOf('async function terminOeffnenMobil')
  const fn = seite.slice(start, seite.indexOf('/**', start))
  assert.ok(!/showEdit\.value = true/.test(fn),
    'die Zeile springt nicht mehr direkt ins Formular (Entwurf A11: Blatt zuerst)')
  assert.match(fn, /showView\.value = true/, 'das Blatt öffnet sich')
  // Das Blatt bekommt Recht und Modus von der Seite (keine eigenen Rollen).
  assert.match(seite, /<KronosEventView[\s\S]{0,300}:bearbeiten-erlaubt="darfOeffnenBearbeiten"/)
  assert.match(seite, /@freigeben="ausBlattFreigeben"/)
  // Das Blatt hängt an derselben einen Grenze wie das Mobil-Layout.
  const view = lies('components/kronos/KronosEventView.vue')
  assert.match(view, /<TerminBlatt[\s\S]{0,200}:darf-pruefen="darfPruefen"/)
  // Die Lage kommt von der Seite (istSchmal) — keine eigene Breitenabfrage.
  assert.ok(!/matchMedia|max-width/.test(view.split('</script>')[0]), 'keine eigene Breitenabfrage')
  assert.match(seite, /<KronosEventView[\s\S]{0,200}:handy-lage="istSchmal"/)
  // „Löschen“ aus dem Blatt löscht — es gibt NICHT frei.
  // Die Moderationsregeln (P1-1b) laufen über den vorhandenen Weg.
  const freigabe = seite.slice(seite.indexOf('async function ausBlattFreigeben'),
    seite.indexOf('onMounted(async () =>'))
  assert.match(freigabe, /resolveConflict\(name, 'festlegen'/, 'Freigeben = vorhandene Moderation')
  assert.match(freigabe, /aktion === 'loeschen'[\s\S]{0,400}onTerminAktion\(\{ key: 'loeschen'/)
  assert.match(freigabe, /if \(aktion !== 'freigeben'\) return/)
})
