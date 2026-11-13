/**
 * A10 — Kalender auf dem Handy nach Entwurf A10 (Karte t_4fd6dcff).
 *
 * Geprüft wird, was die Karte VERLANGT — ausgeführt, nicht als Quelltext-
 * Muster:
 *
 *  1. STANDARDANSICHT JE BENUTZER (Entscheidung Manuel 08.11.): setzen,
 *     nach Neuladen aktiv, ein anderer Benutzer sieht seine eigene Wahl,
 *     ohne Wahl gilt „Liste“, Abmelden löscht den lokalen Wert.
 *  2. MODERATIONSZEILE nur für Moderatoren — dieselbe Prüfung wie das
 *     Desktop-Panel (can_moderate), kein leerer Platz, kein Abzeichen.
 *  3. SCHWEBENDER KNOPF nur mit Schreibrecht.
 *  4. TAGESLISTE: „Sonntag, 8. November“, Zeilen mit Uhrzeit/Titel/Ort ·
 *     Zusatz, Reihenfolge (ganztägig zuerst, dann nach Beginn).
 *  5. MINI-MONAT: Mo–So, volle Wochen, Punkte an Tagen mit Terminen
 *     (gold = zu prüfen), gewählter Tag markiert.
 *  6. GEMOUNTET (jsdom): Segmentsteuerung „Monat · Woche · Liste“ mit
 *     44-px-Zielen, Abzeichen „Moderator“ nur mit Recht, „+ Termin anlegen“
 *     mit 56 px, Standard-Eintrag im „⋯“-Menü, A11-Blatt mit genau EINEM
 *     Primärknopf („Freigeben“) für Moderatoren.
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

const M = await import(pathToFileURL(join(SRC, 'components/kronos/mobilAnsicht.mjs')).href)
const MOD = await import(pathToFileURL(join(SRC, 'components/kronos/mobilModeration.mjs')).href)
const TERMIN = await import(pathToFileURL(join(SRC, 'components/kronos/mobilTermin.mjs')).href)

/** Kleiner Browserspeicher für die Prüfung ohne Browser. */
function speicher(inhalt = {}) {
  const daten = new Map(Object.entries(inhalt))
  return {
    get length() { return daten.size },
    key: (i) => Array.from(daten.keys())[i] ?? null,
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => daten.set(k, String(v)),
    removeItem: (k) => daten.delete(k),
    daten,
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Standardansicht je Benutzer
// ══════════════════════════════════════════════════════════════════════════
test('A10: ohne eigene Wahl gilt „Liste“ (Entwurf A10)', () => {
  const s = speicher()
  assert.equal(M.STANDARD_VORGABE, 'liste')
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'liste')
  assert.equal(M.standardLesen(null, 'anna.beispiel@example.org'), 'liste', 'ohne Speicher: Vorgabe')
})

test('A10: Standard setzen, nach Neuladen aktiv, fremder Wert wird nicht übernommen', () => {
  const s = speicher()
  assert.equal(M.standardSetzen(s, 'anna.beispiel@example.org', 'woche'), true)
  // „Neuladen“: derselbe Speicher, neue Abfrage.
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'woche')
  // Unsinn wird nicht gespeichert und nicht gelesen.
  assert.equal(M.standardSetzen(s, 'anna.beispiel@example.org', 'jahr'), false)
  s.setItem(M.standardSchluessel('anna.beispiel@example.org'), 'quatsch')
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'liste', 'fremder Wert -> Vorgabe')
})

test('A10: jeder Benutzer hat seinen EIGENEN Standard', () => {
  const s = speicher()
  M.standardSetzen(s, 'anna.beispiel@example.org', 'woche')
  M.standardSetzen(s, 'admin@example.org', 'monat')
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'woche')
  assert.equal(M.standardLesen(s, 'admin@example.org'), 'monat')
  // Der Schlüssel trägt die Nutzerkennung NICHT im Klartext (wie UX3f).
  const schluessel = Array.from(s.daten.keys())
  for (const k of schluessel) {
    assert.ok(!k.includes('anna.beispiel'), `Schlüssel ohne Klartext-Adresse: ${k}`)
  }
  assert.equal(M.standardSchluessel('anna.beispiel@example.org'),
    M.standardSchluessel('  ANNA.beispiel@example.org  '), 'Hash ist unabhängig von Schreibweise/Leerzeichen')
})

test('A10: Abmelden löscht den lokalen Wert (alle fremden Schlüssel)', () => {
  const s = speicher()
  M.standardSetzen(s, 'anna.beispiel@example.org', 'woche')
  M.standardSetzen(s, 'admin@example.org', 'monat')
  const weg = M.standardFuerNutzerAufraeumen(s, '')
  assert.equal(weg, 2, 'beide Einträge entfernt')
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'liste', 'nach dem Abmelden: Vorgabe')
  // Identitätswechsel: nur der neue Nutzer behält seinen Wert.
  M.standardSetzen(s, 'anna.beispiel@example.org', 'woche')
  M.standardSetzen(s, 'admin@example.org', 'monat')
  M.standardFuerNutzerAufraeumen(s, 'admin@example.org')
  assert.equal(M.standardLesen(s, 'admin@example.org'), 'monat')
  assert.equal(M.standardLesen(s, 'anna.beispiel@example.org'), 'liste')
})

test('A10: „Als Standard verwenden“ steht im ⋯-Menü an der aktuellen Ansicht', () => {
  const menue = M.mobilMenue({ ansicht: 'woche', standard: 'liste', hatSchreibrecht: true })
  const eintrag = menue.find((e) => e.key === 'standard')
  assert.ok(eintrag, 'Eintrag vorhanden')
  assert.match(eintrag.label, /„Woche“ als Standard verwenden/)
  assert.equal(eintrag.haekchen, false)
  assert.equal(eintrag.disabled, false)
  // Ist die Ansicht schon der Standard: Häkchen, kein zweiter Schreibweg.
  const aktiv = M.mobilMenue({ ansicht: 'woche', standard: 'woche' })
    .find((e) => e.key === 'standard')
  assert.equal(aktiv.haekchen, true)
  assert.equal(aktiv.disabled, true)
  assert.match(aktiv.label, /„Woche“ ist dein Standard/)
  // Und: das Menü bleibt bei höchstens acht Einträgen (DkAktionen/B1).
  const voll = M.mobilMenue({
    ansicht: 'monat', standard: 'liste', istKalenderAdmin: true, hatSchreibrecht: true,
  })
  assert.ok(voll.length <= 8, `Menü hat ${voll.length} Einträge`)
})

// ══════════════════════════════════════════════════════════════════════════
// 1b · Nacharbeit 09.11.: ohne Nutzerkennung NICHT speichern (Punkt 3)
// ══════════════════════════════════════════════════════════════════════════
test('A10: ohne Nutzerkennung wird NICHT gespeichert (kein gemeinsamer Basisschlüssel)', () => {
  const s = speicher()
  for (const leer of ['', null, undefined, '   ']) {
    assert.equal(M.standardSetzen(s, leer, 'monat'), false,
      `Kennung ${JSON.stringify(leer)} darf nichts speichern`)
  }
  assert.equal(s.length, 0, 'der Speicher bleibt leer — kein Basisschlüssel für alle')
  assert.equal(M.standardSchluessel(''), '', 'ohne Kennung gibt es keinen Schlüssel')
  // Lesen ergibt die Vorgabe, auch wenn ein alter Basisschlüssel herumliegt.
  s.setItem(M.STANDARD_SCHLUESSEL, 'monat')
  assert.equal(M.standardLesen(s, ''), 'liste', 'alter Basisschlüssel gilt nicht')
  // Und er wird beim Aufräumen entfernt (er gehört niemandem).
  assert.equal(M.standardFuerNutzerAufraeumen(s, ''), 1)
  assert.equal(s.length, 0)
})

// ══════════════════════════════════════════════════════════════════════════
// 1c · Nacharbeit 09.11.: Markenfläche des FAB in BEIDEN Themes (Punkt 1)
// ══════════════════════════════════════════════════════════════════════════
test('A10: der schwebende Knopf hat in Hell UND Dunkel eine lesbare Fläche', () => {
  const tokens = readFileSync(join(SRC, 'tokens.css'), 'utf8')
  const seite = lies('pages/Kalender.vue')
  // Die Fläche ist ein eigenes Token (Navy), NICHT `--primary`: das ist im
  // Dunkelmodus Weiß und ergab mit weißer Schrift eine leere weiße Pille.
  // A10-N3 (Punkt 3, 10.11.): Die Zusage gilt unverändert — nur heißt das
  // Token des FAB jetzt `--fab-flaeche`. Es steht in BEIDEN Themes im Hell-
  // bzw. Dunkelblock getrennt, weil im Dunkeln der 2-px-Dauerring entfallen
  // ist (er wirkte fremd) und die Fläche selbst tragen muss.
  assert.match(tokens, /--marke-flaeche:\s*var\(--dk-navy-500\)/, 'Markenfläche = Navy')
  assert.match(tokens, /--marke-ink:\s*#ffffff/, 'Schrift auf der Markenfläche weiß')
  assert.match(tokens, /--fab-flaeche:\s*var\(--dk-navy-500\)/, 'FAB-Fläche hell = Navy')
  assert.match(tokens, /--fab-ink:\s*#ffffff/, 'FAB-Schrift hell = weiß')
  const fab = seite.slice(seite.indexOf('.kal-fab {'))
  assert.match(fab.slice(0, 1200), /background:\s*var\(--fab-flaeche\)/,
    'FAB nimmt die FAB-Fläche (Marken-Navy), nicht --primary')
  assert.ok(!/background:\s*var\(--primary\)/.test(fab.slice(0, 1200)),
    'FAB darf NICHT --primary tragen (im Dunkeln weiß)')
  assert.ok(!/var\(--primary-hover\)/.test(fab.slice(0, 1200)), 'auch der Hover bleibt bei der Marke')

  // Kontrast nachrechnen: #1c2850 gegen #ffffff.
  const kontrast = (a, b) => {
    const lum = (hex) => {
      const n = parseInt(hex.replace('#', ''), 16)
      const kanal = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
        const c = v / 255
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * kanal[0] + 0.7152 * kanal[1] + 0.0722 * kanal[2]
    }
    const [h, t] = [lum(a), lum(b)].sort((x, y) => y - x)
    return (h + 0.05) / (t + 0.05)
  }
  const wert = kontrast('#1c2850', '#ffffff')
  assert.ok(wert >= 4.5, `Kontrast Schrift/Fläche ${wert.toFixed(2)}:1 — verlangt ≥ 4,5:1`)
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Moderationszeile und Abzeichen nur für Moderatoren
// ══════════════════════════════════════════════════════════════════════════
test('A10: „Zu prüfen“-Zeile nur für Moderatoren — sonst nichts, auch kein leerer Platz', () => {
  for (const lage of [{}, { darfPruefen: false }, { darfPruefen: 'ja' }, { darfPruefen: 1 }]) {
    assert.equal(MOD.moderationsZeile(lage), null,
      `Nicht-Moderator bekommt keine Zeile (${JSON.stringify(lage)})`)
  }
  const zeile = MOD.moderationsZeile({ darfPruefen: true, zahl: 3 })
  assert.equal(zeile.sichtbar, true)
  assert.equal(zeile.text, 'Zu prüfen (3) · Von Gruppen eingetragen')
  assert.equal(zeile.ziel, '#/kalender/pruefen', 'vorhandene Tafel, kein vierter Reiter')
  // Unbekannte Zahl: Text ohne erfundene 0.
  assert.equal(MOD.moderationsZeile({ darfPruefen: true, zahl: null }).text,
    'Zu prüfen · Von Gruppen eingetragen')
  assert.equal(M.zeigeModerationszeile({ can_moderate: true }), true)
  assert.equal(M.zeigeModerationszeile({}), false, 'fehlender Schlüssel -> fail closed')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Schwebender Knopf nur mit Schreibrecht
// ══════════════════════════════════════════════════════════════════════════
test('A10: „+ Termin anlegen“ nur mit Schreibrecht auf mindestens einen Kalender', () => {
  assert.equal(M.zeigeAnlegenKnopf([]), false, 'keine Kalender -> kein Knopf')
  assert.equal(M.zeigeAnlegenKnopf(null), false)
  assert.equal(M.zeigeAnlegenKnopf([{ name: 'a', write: false }]), false, 'nur Leserecht')
  assert.equal(M.zeigeAnlegenKnopf([{ name: 'a', write: false }, { name: 'b', write: true }]), true)
  assert.equal(M.zeigeAnlegenKnopf([{ name: 'a', write: 'ja' }]), false, 'nur echtes true zählt')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Tagesliste (Entwurf A10)
// ══════════════════════════════════════════════════════════════════════════
const SONNTAG = '2026-11-08'
const termine = [
  { id: '1', title: 'Hauptgottesdienst', start: '2026-11-08 09:30:00', end: '2026-11-08 11:00:00', ressource_name: 'Gemeindehaus', description: 'Predigt A. Weber' },
  { id: '2', title: 'Kirchencafé', start: '2026-11-08 11:00:00', end: '2026-11-08 12:00:00', ressource_name: 'Gemeindesaal', description: 'Team Kaffee' },
  { id: '3', title: 'Hauskreis Nord', start: '2026-11-08 18:00:00', end: '2026-11-08 19:30:00', zusaetzliche_ressourcen: [{ ressource_name: 'Fam. Kirsch' }], description: '8 Personen' },
  { id: '4', title: 'Herbstfreizeit Jugend', start: '2026-11-07 00:00:00', end: '2026-11-09 00:00:00', all_day: true, ressource_name: 'Freizeitheim Sonnenhof' },
  { id: '5', title: 'Montagstreffen', start: '2026-11-09 19:00:00', end: '2026-11-09 20:00:00' },
]

test('A10: Tagesliste — Kopf, Zeilen, Reihenfolge, Zusatz', () => {
  assert.equal(M.tagTitel(SONNTAG), 'Sonntag, 8. November')
  const zeilen = M.tagesTermine(termine, SONNTAG)
  assert.deepEqual(zeilen.map((z) => z.titel),
    ['Herbstfreizeit Jugend', 'Hauptgottesdienst', 'Kirchencafé', 'Hauskreis Nord'],
    'ganztägig zuerst, dann nach Beginn — der Montagstermin fehlt')
  assert.equal(zeilen[0].zeit, '', 'ganztägig trägt keine Uhrzeit')
  assert.equal(zeilen[1].zeit, '09:30')
  assert.equal(zeilen[1].zusatz, 'Gemeindehaus · Predigt A. Weber', 'Ort · Zusatz')
  assert.equal(zeilen[3].zusatz, 'Fam. Kirsch · 8 Personen', 'erste zusätzliche Ressource als Ort')
})

test('A10: mehrtägiger Termin hängt an JEDEM Tag seines Zeitraums', () => {
  assert.equal(M.terminAmTag(termine[3], '2026-11-07'), true, 'erster Tag')
  assert.equal(M.terminAmTag(termine[3], '2026-11-08'), true, 'mittlerer Tag')
  assert.equal(M.terminAmTag(termine[3], '2026-11-09'), true, 'letzter Tag (Ende einschließend)')
  assert.equal(M.terminAmTag(termine[3], '2026-11-10'), false)
  // Am zweiten Tag steht keine Startzeit (sie gehört zum ersten).
  assert.equal(M.terminZeit({ ...termine[3], all_day: false }, '2026-11-08'), '')
})

test('A10: Zusatz wird gekürzt statt abgeschnitten-umgebrochen', () => {
  const lang = { id: 'x', title: 'T', start: '2026-11-08 10:00:00', description: 'a'.repeat(120) }
  const zusatz = M.terminZusatz(lang, 40)
  assert.equal(zusatz.length, 40)
  assert.ok(zusatz.endsWith('…'))
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Mini-Monat
// ══════════════════════════════════════════════════════════════════════════
test('A10: Mini-Monat — Mo–So, volle Wochen, November 2026 beginnt am Sonntag', () => {
  assert.deepEqual(M.WOCHENTAGE.map(String), ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'])
  const raster = M.miniRaster('2026-11', new Date('2026-11-08T12:00:00'))
  assert.equal(raster.length, 6, 'November 2026 braucht sechs Wochen (Ende am 6.12.)')
  assert.deepEqual(raster[0].map((d) => d.zahl), [26, 27, 28, 29, 30, 31, 1],
    'erste Zeile 26.10.–1.11. (der 1.11. ist ein Sonntag)')
  for (const woche of raster) assert.equal(woche.length, 7, 'jede Zeile hat sieben Tage')
  const alle = raster.flat()
  assert.equal(alle.find((d) => d.tag === '2026-11-08').istHeute, true)
  assert.equal(alle.find((d) => d.tag === '2026-10-26').imMonat, false, 'Vormonatstage grau')
  assert.equal(M.monatsTitel('2026-11'), 'November 2026')
  assert.deepEqual(M.miniRaster(''), [], 'ohne Monat kein Raster')
})

test('A10: Mini-Monat — Punkte an Tagen mit Terminen, gold für „zu prüfen“', () => {
  const raster = M.miniRaster('2026-11', new Date('2026-11-08T12:00:00'))
  const spanne = [raster[0][0].tag, raster[raster.length - 1][6].tag]
  const punkte = M.punkteJeTag(termine, ['2'], spanne)
  assert.equal(punkte.get('2026-11-08').anzahl, 4, 'vier Termine am Sonntag')
  assert.equal(punkte.get('2026-11-09').anzahl, 2, 'Montag: Montagstreffen + Herbstfreizeit')
  assert.equal(punkte.get('2026-11-08').pruefen, true, 'Kirchencafé ist zu prüfen (gold)')
  assert.equal(punkte.get('2026-11-09').normal, true)
  assert.equal(punkte.get('2026-11-09').pruefen, false)
  assert.equal(punkte.get('2026-11-10'), undefined, 'kein Termin, kein Punkt')
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Termin-Blatt A11: Handlungen je Recht
// ══════════════════════════════════════════════════════════════════════════
test('A10: A11-Blatt — Moderator bekommt „Freigeben“ primär, Absagen/Löschen ins ⋯', () => {
  assert.equal(TERMIN.istPruefStatus({ status: 'Vorschlag' }), true)
  assert.equal(TERMIN.istPruefStatus({ status: 'Konflikt' }), true)
  assert.equal(TERMIN.istPruefStatus({ status: 'Festgelegt' }), false)
  const menue = TERMIN.terminBlattAktionen({ darfPruefen: true, darfBearbeiten: true, primaerFreigeben: true })
  assert.deepEqual(menue.map((e) => e.key), ['absagen', 'loeschen'], 'Freigeben steht als Knopf, nicht doppelt im ⋯')
  assert.equal(menue.find((e) => e.key === 'loeschen').gefahr, true, 'Löschen ist gefährlich (zuletzt, rot)')
  // Nicht-Moderator: kein Freigeben, kein Absagen.
  const ohne = TERMIN.terminBlattAktionen({ darfPruefen: false, darfBearbeiten: true, primaerFreigeben: false })
  assert.deepEqual(ohne.map((e) => e.key), ['bearbeiten', 'loeschen'])
  // Nur Lesen: gar keine Handlung.
  assert.deepEqual(TERMIN.terminBlattAktionen({}), [])
})

test('A10: A11-Blatt — Status-Badge „Zu prüfen · eingetragen von …“', () => {
  assert.deepEqual(TERMIN.statusBadgeFuer({ status: 'Vorschlag', antragsteller: 'J. Rehberg' }),
    { text: 'Zu prüfen · eingetragen von J. Rehberg', variant: 'warn' })
  assert.deepEqual(TERMIN.statusBadgeFuer({ status: 'Festgelegt', antragsteller: 'J. Rehberg' }),
    { text: 'Bestätigt', variant: 'ok' }, 'Herkunft nur bei den Prüf-Status')
  assert.equal(TERMIN.statusBadgeFuer({}), null, 'kein Status, kein erfundenes Abzeichen')
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Gemountete Bauteile (jsdom) — was der Nutzer sieht und tippen kann
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')
// Die App-Kopfzeile holt beim Aufbau Benachrichtigungen und setzt einen
// Sekundentakt (`setInterval`). Im Node-Test gibt es keine Uhr, die darauf
// wartet — der Takt würde den Prozess nach dem letzten Test AM LEBEN halten
// (der Testlauf lief in die Zeitgrenze, obwohl alle Prüfungen grün waren).
// Ersatz: ein Takt, der sofort eine Nummer liefert und NIE feuert.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  // Nur blindness-freie Prüfintervalle ersetzen: alles, was sofort laufen
  // müsste (`ms` fehlt oder 0), bleibt beim echten Takt.
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const TMP = mkdtempSync(join(tmpdir(), 'a10-'))
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
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
const tick = () => new Promise((loese) => setTimeout(loese, 0))

async function mounten(datei, eigenschaften) {
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
      @ansichtWechsel="merke('ansicht', $event)"
      @standardSetzen="merke('standard')"
      @heute="merke('heute')"
      @kalenderauswahl="merke('auswahl')"
      @tagWechsel="merke('tag', $event)"
      @terminOeffnen="merke('termin', $event)"
      @terminAktion="merke('aktion', $event)"
      @woche="merke('woche')"
      @oeffnen="merke('pruefen')"
      @freigeben="merke('freigeben', $event)"
      @bearbeiten="merke('bearbeiten', $event)"
    />`,
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen, gemeldet, neu: async (neue) => { Object.assign(eigenschaften, neue); await tick() } }
}

test('A10: Mobil-Kopf — Segmente Monat · Woche · Liste, 44-px-Ziele, EIN Kopf ohne Titel', async () => {
  const { host, warnungen, gemeldet } = await mounten('components/kronos/KalenderKopfMobil.vue', {
    ansicht: 'liste', standard: 'liste', darfPruefen: true, hatSchreibrecht: true,
  })
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  const segmente = [...host.querySelectorAll('.dk-mobilkopf-segment')]
  assert.deepEqual(segmente.map((s) => s.textContent.trim()), ['Monat', 'Woche', 'Liste'])
  assert.equal(segmente[2].getAttribute('aria-selected'), 'true', 'Liste ist aktiv (Standard)')
  // Review 09.11., Punkt 4: „Kalender“ und „Moderator“ stehen NICHT mehr im
  // Bereichskopf — sie stehen EINMAL in der App-Kopfzeile (dort prüft es der
  // Test „App-Kopfzeile …“ weiter unten). Zwei Titel übereinander waren der
  // Befund; der Bereichskopf trägt nur Segmente und Werkzeuge.
  assert.equal(host.querySelector('h1'), null, 'kein zweiter Bereichstitel')
  assert.ok(!host.textContent.includes('Moderator'), 'kein zweites Abzeichen')
  assert.equal(host.querySelector('.dk-kalender-heute'), null, '„Heute“ steht nur im Mini-Monat')
  assert.ok(![...host.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Heute'),
    'kein zweiter „Heute“-Knopf (Entwurf A10: einmal, im Mini-Monat)')

  // Jedes sichtbare Bedienelement (Knopf, Segment, Menü-Auslöser) ist
  // mindestens 44 px hoch — die Regel K4 der Karte.
  const ziele = [...host.querySelectorAll('button')]
  // A10-N2 (Review 09.11., Punkt 2): EINE Kopfzeile statt Werkzeugzeile —
  // drei Segmente + Kalender-Auswahl + „⋯“ = fünf Knöpfe. ‹ › stehen am
  // Mini-Monat (Liste) bzw. an der Monatszeile des Rasters (Monat/Woche).
  assert.equal(ziele.length, 5, `Kopf = Segmente + Kalender + ⋯ (${ziele.length})`)
  for (const ziel of ziele) {
    const eigen = ziel.className.includes('dk-mobilkopf')
    const menue = ziel.className.includes('dk-ui-aktionen-ausloeser')   // „⋯“ (eigener Baustein)
    assert.ok(eigen || menue, `Knopf aus dem Mobil-Kopf: ${ziel.className}`)
  }

  // Klick auf „Woche“ meldet die Kennung — die Seite wechselt die Ansicht.
  segmente[1].dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['ansicht', 'woche'])
})

test('A10: App-Kopfzeile — Abzeichen nur wenn die Seite eine Rolle meldet', async () => {
  // Die Kopfzeile ist App-Rahmen (viele Abhängigkeiten: Benachrichtigungen,
  // Router, Emits). Geprüft wird deshalb EINZELN, was A10 verlangt: der
  // Halter hängt am Prop `rollenMarke`, und ohne Meldung ist er nicht im DOM
  // (kein leerer Platz). Der Leerfall läuft im jsdom wirklich.
  const ohne = await mounten('components/AppTopbar.vue', { rollenMarke: '' })
  assert.equal(ohne.host.querySelector('.dk-topbar-rolle'), null, 'ohne Rolle kein Abzeichen')

  const quelle = lies('components/AppTopbar.vue')
  assert.match(quelle, /v-if="rollenMarke"/, 'Halter nur mit gemeldeter Rolle')
  assert.match(quelle, /<DkBadge variant="info">\{\{ rollenMarke \}\}<\/DkBadge>/, 'Abzeichen zeigt den Text')
  assert.match(quelle, /rollenMarke: \{ type: String, default: '' \}/, 'Prop mit leerem Grundwert')

  // Und die Kopfzeile der App reicht das Prop durch (eine Quelle).
  const app = lies('App.vue')
  assert.match(app, /:rollen-marke="rollenMarke"/, 'App gibt die Meldung weiter')
  assert.match(app, /import \{ rollenMarke \} from '\.\/composables\/useBereichskopf\.js'/)

  // Der Speicher der Meldung ist ein reiner Text-Zustand, kein Rechte-Objekt.
  const regeln = await import(pathToFileURL(join(SRC, 'composables/useBereichskopf.js')).href)
  regeln.setzeRollenMarke('Moderator')
  assert.equal(regeln.rollenMarke.value, 'Moderator')
  regeln.setzeRollenMarke(null)
  assert.equal(regeln.rollenMarke.value, '', 'Abmelden/Seitenwechsel leert die Meldung')
  regeln.setzeRollenMarke('x'.repeat(50))
  assert.equal(regeln.rollenMarke.value.length, 24, 'nur kurzer Text, kein Freitext-Kanal')
  regeln.setzeRollenMarke('')
})


test('A10: Mobil-Kopf — ohne Moderationsrecht KEIN Abzeichen, KEINE Prüfspur', async () => {
  const { host } = await mounten('components/kronos/KalenderKopfMobil.vue', {
    ansicht: 'liste', darfPruefen: false,
  })
  assert.equal(host.querySelector('.dk-ui-badge'), null, 'kein Abzeichen')
  assert.ok(!host.textContent.includes('Moderator'), 'auch kein Text „Moderator“')
  // Und die Prüf-Zeile fehlt vollständig (kein leerer Platz).
  const zeile = await mounten('components/kronos/KalenderPruefZeile.vue', { darfPruefen: false, zahl: 3 })
  assert.equal(zeile.host.querySelector('.dk-pruefzeile'), null)
  assert.equal(zeile.host.textContent.trim(), '', 'nichts gerendert')
})

test('A10: Prüf-Zeile — Zahl im goldenen Kreis, Titel + Untertitel, vorhandene Tafel', async () => {
  const { host, gemeldet } = await mounten('components/kronos/KalenderPruefZeile.vue',
    { darfPruefen: true, zahl: 3 })
  const zeile = host.querySelector('.dk-pruefzeile')
  assert.ok(zeile)
  // A10 (Review 09.11., Punkt 4): Zahl und Texte stehen getrennt — die Zahl
  // sitzt im Kreis, darunter NICHT eine lange Zeile, sondern Titel und
  // Untertitel untereinander („Zu prüfen“ / „Von Gruppen eingetragen“).
  assert.equal(zeile.querySelector('.dk-pruefzeile-kreis').textContent.trim(), '3')
  assert.equal(zeile.querySelector('.dk-pruefzeile-titel').textContent.trim(), 'Zu prüfen')
  assert.equal(zeile.querySelector('.dk-pruefzeile-unter').textContent.trim(), 'Von Gruppen eingetragen')
  assert.ok(zeile.querySelector('.dk-pruefzeile-pfeil'), 'Pfeil zur Tafel')
  // Die Vorlesehilfe trägt den vollen Satz (Farbe/Zahl sind nicht alleiniger
  // Träger).
  assert.match(zeile.getAttribute('aria-label'), /Zu prüfen \(3\) · Von Gruppen eingetragen/)
  assert.equal(zeile.getAttribute('href'), '#/kalender/pruefen')
  zeile.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['pruefen'])
})

test('A10: Prüf-Zeile — unbekannte Zahl: leerer Kreis, keine erfundene 0', async () => {
  const { host } = await mounten('components/kronos/KalenderPruefZeile.vue',
    { darfPruefen: true, zahl: null })
  const kreis = host.querySelector('.dk-pruefzeile-kreis')
  assert.ok(kreis.classList.contains('ist-leer'), 'Kreis bleibt als Anker, aber leer')
  assert.equal(kreis.textContent.trim(), '')
  assert.equal(host.querySelector('.dk-pruefzeile-titel').textContent.trim(), 'Zu prüfen')
})

test('A10: Tagesliste — Kopf, Zeilen und „Woche ›“ im DOM', async () => {
  const { host, gemeldet } = await mounten('components/kronos/KalenderTagesliste.vue', {
    termine, tag: SONNTAG, lesemodus: true,
  })
  assert.equal(host.querySelector('.dk-tagesliste-titel').textContent.trim(), 'Sonntag, 8. November')
  const zeilen = [...host.querySelectorAll('.dk-tagesliste-zeile')]
  assert.equal(zeilen.length, 4)
  assert.equal(zeilen[1].querySelector('.dk-tagesliste-zeit').textContent.trim(), '09:30')
  assert.equal(zeilen[1].querySelector('.dk-tagesliste-name').textContent.trim(), 'Hauptgottesdienst')
  assert.match(zeilen[1].querySelector('.dk-tagesliste-zusatz').textContent, /Gemeindehaus · Predigt/)
  // Die ganze Zeile ist ein Knopf; Klick öffnet den Termin.
  const knopf = zeilen[1].querySelector('.dk-tagesliste-knopf')
  knopf.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(gemeldet.at(-1)[0], 'termin')
  assert.equal(gemeldet.at(-1)[1].title, 'Hauptgottesdienst')
  // Im Lesemodus bietet das ⋯ nur „Ansehen“ (UX3i bleibt erhalten).
  const eintraege = zeilen[1].querySelectorAll('.dk-ui-aktionen-eintrag')
  if (eintraege.length) {
    assert.deepEqual([...eintraege].map((e) => e.textContent.trim()), ['Ansehen'])
  }
  // „Woche ›“ führt in die Wochenansicht (gleicher Zustand, anderer Blick).
  const woche = host.querySelector('.dk-tagesliste-woche')
  woche.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['woche'])
})

test('A10: Mini-Monat — gewählter Tag markiert, Punkte gesetzt, Tipp wählt den Tag', async () => {
  const { host, gemeldet } = await mounten('components/kronos/KalenderMiniMonat.vue', {
    monat: '2026-11', gewaehlt: SONNTAG, termine, pruefIds: ['2'], farbe: '#1c2850',
  })
  assert.equal(host.querySelectorAll('.dk-minimonat-tag').length, 42, 'sechs Wochen × sieben Tage')
  const gewaehlt = host.querySelector('.dk-minimonat-tag.is-gewaehlt')
  assert.equal(gewaehlt.getAttribute('data-tag'), SONNTAG)
  assert.equal(gewaehlt.getAttribute('aria-current'), 'date')
  // Drei Tage haben Termine (7., 8., 9. November) — je Zelle EIN Punkt.
  assert.equal(host.querySelectorAll('.dk-minimonat-punkt').length, 3, 'Punkte an Tagen mit Terminen')
  // Die goldene Kennzeichnung ist eine Eigenschaft des PUNKTS, nicht des
  // gewählten Tages: der 8.11. ist gewählt, dort wäre der Punkt weiß.
  assert.ok(host.querySelector('[data-tag="2026-11-08"] .dk-minimonat-punkt'),
    'Punkt am gewählten Tag (weiß, damit er auf der gefüllten Fläche sichtbar ist)')
  assert.match(host.textContent, /November 2026/)
  const zelle = host.querySelector('[data-tag="2026-11-09"]')
  zelle.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['tag', '2026-11-09'])
})

test('A10: A11-Blatt — genau EIN Primärknopf „Freigeben“ für Moderatoren', async () => {
  dom.window.__DIakonosBOOT = { can_moderate: true }
  globalThis.__DIakonosBOOT = dom.window.__DIakonosBOOT
  // Das Blatt hängt an der HANDY-Lage, die die Seite durchreicht (A11-Review).
  const { host, gemeldet } = await mounten('components/kronos/KronosEventView.vue', {
    show: true,
    handyLage: true,
    bearbeitenErlaubt: true,
    event: {
      element_name: 'Herbstfreizeit Jugend', status: 'Vorschlag', antragsteller: 'J. Rehberg',
      element_start: '2026-11-07 00:00:00', element_end: '2026-11-09 00:00:00', all_day: true,
    },
  })
  // Das Blatt liegt im Teleport am <body> (wie im Betrieb), nicht im Halter.
  const knopf = (text) => [...document.body.querySelectorAll('button')]
    .find((b) => b.textContent.trim() === text)
  const freigeben = knopf('Freigeben')
  assert.ok(freigeben, 'Moderator sieht „Freigeben“')
  assert.equal(freigeben.getAttribute('data-primaer'), '1')
  const primaer = document.body.querySelectorAll('[data-primaer="1"]')
  assert.equal(primaer.length, 1, 'genau ein Primärknopf je Ansicht')
  freigeben.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(gemeldet.at(-1)[0], 'freigeben')
  assert.equal(gemeldet.at(-1)[1].aktion, 'freigeben')
  // Und: Löschen/Absagen stehen im ⋯, nicht als Knopf daneben.
  assert.equal(knopf('Löschen'), undefined, 'Löschen ist keine eigene Schaltfläche')
  assert.equal(knopf('Absagen'), undefined, 'Absagen ist keine eigene Schaltfläche')
  // Badge steht im Blatt (Teleport am <body>), nicht im Halter.
  assert.match(document.body.textContent, /Zu prüfen · eingetragen von J\. Rehberg/,
    'Status-Badge nach Entwurf A11')
  document.body.innerHTML = ''   // Blatt für die folgenden Prüfungen schließen
})

test('A10: die Seite zeigt am Handy den Mobil-Kopf und KEINE Werkzeugzeilen', () => {
  const seite = lies('pages/Kalender.vue')
  assert.match(seite, /<KalenderKopfMobil/, 'Mobil-Kopf wird gerendert')
  assert.match(seite, /<KalenderPruefZeile/, 'goldene Statuszeile')
  assert.match(seite, /<KalenderListeMobil/, 'Listen-Ansicht aus Mini-Monat + Tagesliste')
  // Beide Köpfe stehen im Markup; welcher gilt, entscheidet die Lage.
  assert.match(seite, /<KronosTopbar\s+v-if="!istSchmal"/, 'Desktop-Kopfzeile (A4) nur am Desktop')
  assert.match(seite, /<template v-if="istSchmal">/, 'Mobil-Bau hängt an derselben Grenze')
  // Der schwebende Knopf ist der EINE Primärknopf und hängt am Schreibrecht.
  assert.match(seite, /v-if="istSchmal && hasWriteRight"[\s\S]{0,400}class="kal-fab"/)
  // Kein vierter Reiter und keine zweite Moderation: das Panel „Zu prüfen“
  // hängt am DESKTOP-Block (`!istSchmal`), am Handy trägt die Zeile die Spur.
  const desktopBlock = seite.slice(seite.indexOf('<div v-if="!istSchmal" class="kal-flaeche">'))
  assert.match(desktopBlock.slice(0, 1600), /<KalenderPruefPanel/, 'Panel steht im Desktop-Block')
  const mobilBlock = seite.slice(seite.indexOf('<template v-if="istSchmal">'), seite.indexOf('<KronosTopbar'))
  assert.ok(!mobilBlock.includes('KalenderPruefPanel'), 'Panel fehlt im Mobil-Block')
  // Die Standard-Ansicht kommt aus dem Speicher (je Benutzer), nicht fest.
  assert.match(seite, /standardLesen\(window\.localStorage/)
  // A10 (Review 09.11., Punkt 4): EIN Kopf „Kalender“ — Titel und Abzeichen
  // meldet die Seite an die App-Kopfzeile, der Bereichskopf hat keinen.
  assert.match(seite, /setzeRollenMarke\(darf \? 'Moderator' : ''\)/, 'Abzeichen nur mit Recht gemeldet')
  assert.match(seite, /onUnmounted\([^}]*\}?[\s\S]{0,600}setzeRollenMarke\(''\)/, 'beim Verlassen abgeräumt')
  // Review 12.11., Punkt 5: Der Escape-Zuhörer entsteht VOR den `await`s in
  // onMounted (sonst blieb die erste Ladezeit ohne Tastatur) — angebunden wird
  // er dort und beim Verlassen wieder abgehängt (kein Doppel-Zuhörer).
  const montiert = seite.slice(seite.indexOf('onMounted(async () => {'),
    seite.indexOf('onUnmounted(', seite.indexOf('onMounted(async () => {')))
  assert.ok(montiert.indexOf("window.addEventListener('keydown', listeTaste)") < montiert.indexOf('await '),
    'keydown-Zuhörer steht in onMounted vor dem ersten await')
  assert.equal(montiert.split("addEventListener('keydown', listeTaste)").length, 2,
    'genau EINE Anbindung des Escape-Zuhörers')
  assert.match(seite, /onUnmounted\([\s\S]{0,600}removeEventListener\('keydown', listeTaste\)/,
    'der Zuhörer wird beim Verlassen abgehängt')
  const kopfMobil = lies('components/kronos/KalenderKopfMobil.vue')
  assert.ok(!/<h1/.test(kopfMobil.split('<script')[0]), 'kein zweiter Titel im Bereichskopf')
  assert.ok(!kopfMobil.includes('>Heute<'), '„Heute“ nur einmal (im Mini-Monat)')
  // Nacharbeit 09.11.: Der Lesemodus-Schalter muss die MOBILE Liste neu
  // laden — sonst zeigt sie nach dem Umschalten Vorschläge bzw. leere Tage
  // (im Wegwerf-Stack gesehen).
  const wechsel = seite.slice(seite.indexOf('function onLesemodusWechsel'), seite.indexOf('const lesemodus ='))
  assert.match(wechsel, /mobilTermineLaden\(\)/, 'Lesemodus-Wechsel lädt die Tagesliste neu')
})
