/**
 * UX3i — Kalender Desktop nach Entwurf A4.
 *
 * Karte t_086b6229. Geprüft wird, was der Nutzer SIEHT und anklicken kann,
 * plus die Regeln, die dafür gelten — nicht ein Quelltext-Muster:
 *
 *  1. Die reinen Regeln (`chipText.mjs`, `kalenderKopf.mjs`, `pruefZeile.mjs`)
 *     werden AUSGEFÜHRT: Chip-Beschriftung mit Uhrzeit, voller Titel für
 *     `aria-label`, Kalenderwochen im Kopf, „+n weitere“, Kontrast der
 *     Chipfarbe, Menü-Einträge je nach Recht.
 *  2. Die Bauteile werden gemountet (jsdom, wie `ux3d-kalender-pruefen`):
 *     Kopfzeile ohne Auswahlfeld „Monat“, genau EIN Primärknopf, Zähler am
 *     Kalender-Knopf, Popover blendet Kalender aus und ein (Escape), Panel
 *     „Zu prüfen“ nur für Moderatoren.
 *  3. Die Seite als Quelltext: keine Emoji, keine KW-Beschriftung in Zellen
 *     (`weekNumbers: false`), KW-Bereich im Kartenkopf, kein zweiter
 *     Umschalter.
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

const chip = await import(pathToFileURL(join(SRC, 'components/kronos/chipText.mjs')).href)
const kopf = await import(pathToFileURL(join(SRC, 'components/kronos/kalenderKopf.mjs')).href)
const rechte = await import(pathToFileURL(join(SRC, 'components/kronos/kalenderRechte.mjs')).href)
const breiten = await import(pathToFileURL(join(SRC, 'components/kronos/breiten.mjs')).href)
const zeile = await import(pathToFileURL(join(SRC, 'components/kronos/pruefZeile.mjs')).href)
const symbole = await import(pathToFileURL(join(SRC, 'components/ui/symbole.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Chips: Titel und Uhrzeit, voller Titel im aria-label
// ══════════════════════════════════════════════════════════════════════════
const termin = (start, ende, zusatz = {}) => ({
  title: zusatz.title ?? 'Gottesdienst am 1. Advent',
  start: new Date(start),
  end: ende === null ? null : new Date(ende),
  allDay: zusatz.allDay ?? false,
})

test('UX3i: Chip zeigt „19:00 Titel“ — eine Variante, durchgängig', () => {
  const t = termin('2026-11-08T19:00:00', '2026-11-08T20:30:00')
  assert.equal(chip.chipText(t), '19:00 Gottesdienst am 1. Advent',
    'Uhrzeit steht VOR dem Titel (A4), nicht dahinter')
  // Dieselbe Regel für jeden Tag — kein Sonderfall Montag/Sonntag.
  const montag = termin('2026-11-02T09:05:00', '2026-11-02T10:00:00', { title: 'Chorprobe' })
  assert.equal(chip.chipText(montag), '09:05 Chorprobe')
})

test('UX3i: ganztägig und mehrtägig tragen KEINE Uhrzeit', () => {
  assert.equal(chip.chipText({ title: 'Herbstfreizeit', start: new Date('2026-11-07T00:00:00'), end: new Date('2026-11-09T00:00:00'), allDay: true }),
    'Herbstfreizeit', 'ganztägig: nur der Titel')
  assert.equal(chip.chipText(termin('2026-11-07T18:00:00', '2026-11-08T12:00:00', { title: 'Nacht der Lieder' })),
    'Nacht der Lieder', 'mehrtägig: nur der Titel (die Uhrzeit gehörte an den falschen Tag)')
  // Bestandsdaten: 00:00–00:00 ohne allDay-Flag gilt als ganztägig (BLD-R6).
  assert.equal(chip.chipText(termin('2026-11-08T00:00:00', '2026-11-08T00:00:00', { title: 'Gemeindefest' })),
    'Gemeindefest')
})

test('UX3i: voller Titel steht in title/aria-label — auch wenn der Chip kürzt', () => {
  const lang = termin('2026-11-08T19:00:00', '2026-11-08T21:00:00', {
    title: 'Gottesdienst am Christkönigssonntag mit Abendmahl und Kirchenchor',
  })
  const titel = chip.chipTitel(lang)
  assert.match(titel, /^Gottesdienst am Christkönigssonntag mit Abendmahl und Kirchenchor · /,
    'der volle Titel steht am Anfang (nichts wird abgeschnitten)')
  assert.match(titel, /19:00–21:00/, 'dazu Datum und Zeit')
  // Der sichtbare Text ist kurz genug, um nicht sofort zu kürzen.
  assert.ok(chip.chipText(lang).length < titel.length)
})

test('UX3i: „+n weitere“ — Zahl und Einzahl/Mehrzahl, nie „+0“', () => {
  assert.equal(chip.weitereText(1), '+1 weitere')
  assert.equal(chip.weitereText(3), '+3 weitere')
  assert.equal(chip.weitereText(0), '')
  assert.equal(chip.weitereText(null), '')
  assert.equal(chip.CHIPS_JE_TAG, 3, 'so viele Chips stehen in A4 je Tag')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Kartenkopf: Monat und „KW a–b“ (keine KW in den Zellen)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i: Kartenkopf „KW 44–49“ aus dem gezeigten Bereich', () => {
  // A4 zeigt 26.10.–06.12.2026 — sechs Wochen, KW 44 bis KW 49.
  assert.equal(chip.kwBereich('2026-10-26T00:00:00', '2026-12-07T00:00:00'), 'KW 44–49',
    'erster Tag 26.10. (KW 44), letzter gezeigter Tag 06.12. (KW 49)')
  // Eine einzelne Woche: eine Zahl, kein Bereich.
  assert.equal(chip.kwBereich('2026-11-02T00:00:00', '2026-11-09T00:00:00'), 'KW 45')
  // Ohne Daten keine erfundene Zahl.
  assert.equal(chip.kwBereich(null, null), '')
  // Jahreswechsel: 28.12.2026 ist KW 53, 03.01.2027 KW 53 (ISO).
  assert.equal(chip.isoWoche('2026-12-28').nummer, 53)
  assert.equal(chip.isoWoche('2027-01-03').nummer, 53)
})

test('UX3i: Monatstitel „November 2026“ (auch ohne Leerzeichen der Bibliothek)', () => {
  assert.equal(chip.monatstitel('November 2026'), 'November 2026')
  assert.equal(chip.monatstitel('November2026'), 'November 2026')
  assert.equal(chip.monatstitel(''), '')
})

test('UX3i: der Kalender zeichnet KEINE Kalenderwoche in den Zellen', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  assert.match(quelle, /weekNumbers:\s*false/,
    'weekNumbers muss aus sein — die KW stand in der Montagszelle und drängte die Termine')
  assert.doesNotMatch(quelle, /weekNumbers:\s*true/)
  assert.doesNotMatch(quelle, /W\{?\{?\s*(week|info\.view)/, 'keine eigene W-Nummer im Zellinhalt')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Chipfarben: Kontrast erreicht AA (4,5:1)
// ══════════════════════════════════════════════════════════════════════════
function kontrast(hex1, hex2) {
  const f = (h) => {
    const n = parseInt(h.replace('#', ''), 16)
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  }
  const lum = ([r, g, b]) => {
    const k = (c) => { const s = c / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b)
  }
  const a = lum(f(hex1))
  const b = lum(f(hex2))
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** Die Marken-Schriftfarben aus `chipText.mjs` (hell/dunkel). */
const MARKEN = { hell: { ink: '#00051f', hinter: '#ffffff' }, dunkel: { ink: '#ffffff', hinter: '#1a1f2e' } }
const FARBEN = ['#16a34a', '#2563eb', '#db2777', '#78716c', '#c9952f', '#1c2850', '#f7eee0', '#ffe600']

test('UX3i: Chipfläche „22 % Kalenderfarbe“ trägt lesbare Schrift (hell und dunkel)', () => {
  for (const theme of ['hell', 'dunkel']) {
    for (const farbe of FARBEN) {
      const ergebnis = chip.chipFarben(farbe, { theme })
      // N2-Nachtrag: Die Schrift kommt als `light-dark(hell, dunkel)` — die
      // für DIESES Theme geltende Marke ist der zweite (dunkel) bzw. erste
      // (hell) Teil. Seiteneffekt: ein Theme-Wechsel nimmt den Chip mit.
      const ld = /light-dark\((var\([^)]*\)),\s*(var\([^)]*\))\)/.exec(ergebnis.schrift)
      // `light-dark(HELL, DUNKEL)` — der ERSTE Teil gilt hell, der zweite dunkel.
      const token = ld ? (theme === 'dunkel' ? ld[2] : ld[1]).trim() : ergebnis.schrift
      const marke = token.includes('navy-900') ? '#00051f' : '#ffffff'
      const grund = MARKEN[theme].hinter
      const n = parseInt(farbe.replace('#', ''), 16)
      const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
      const g = groundRgb(theme)
      const anteil = ergebnis.flaeche ? 0.55 : 0.22
      const gemischt = rgb.map((c, i) => Math.round(c * anteil + g[i] * (1 - anteil)))
        .map((c) => c.toString(16).padStart(2, '0')).join('')
      const verhaeltnis = kontrast('#' + gemischt, marke)
      assert.ok(verhaeltnis >= 4.5 || ergebnis.flaeche !== '',
        `${theme}/${farbe}: Kontrast ${verhaeltnis.toFixed(2)} < 4,5 — die Fläche muss dunkler werden`)
      // Bei dunklerer Fläche ist Weiß die Schrift und der Kontrast muss passen.
      if (ergebnis.flaeche) {
        assert.ok(kontrast('#' + gemischt, marke) >= 4.5,
          `${theme}/${farbe}: dunklere Fläche muss AA tragen`)
      }
      assert.ok(kontrast(marke, grund) > 4.5, 'die Marke selbst steht im Theme')
    }
  }
})

function groundRgb(theme) {
  return theme === 'dunkel' ? [26, 31, 46] : [255, 255, 255]
}

test('UX3i: ohne Kalenderfarbe nimmt der Chip die Textsorte des Themes', () => {
  const hell = chip.chipFarben('', { theme: 'hell' })
  assert.match(hell.schrift, /navy-900/)
  const dunkel = chip.chipFarben('kein-farbwert', { theme: 'dunkel' })
  assert.match(dunkel.schrift, /warm-0/)
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Kopfzeilen-Menü und Kalenderauswahl
// ══════════════════════════════════════════════════════════════════════════
test('UX3i: ⋯-Menü — Verwalten/Import nur für Kalenderadministratoren (Rollenprüfung)', () => {
  const alle = rechte.kalenderMenue()
  assert.deepEqual(alle.map((e) => e.key), ['ressourcenplan', 'abgelehnte', 'hilfe'],
    'ohne Verwaltungsrecht: kein Verwalten, kein Import; abgelehnte Termine und Hilfe für alle')
  // Review 07.11.: Der Lesemodus-Schalter erscheint nur mit Schreibrecht.
  assert.deepEqual(rechte.kalenderMenue({ hatSchreibrecht: true }).map((e) => e.key),
    ['ressourcenplan', 'bearbeiten', 'abgelehnte', 'hilfe'])
  const admin = rechte.kalenderMenue({ istKalenderAdmin: true, hatSchreibrecht: true, lesemodus: false })
  assert.deepEqual(admin.map((e) => e.key),
    ['ressourcenplan', 'verwalten', 'importieren', 'bearbeiten', 'abgelehnte', 'hilfe'])
  // Ziele bleiben dieselben wie bisher (kein neuer Weg, keine neue Adresse).
  const ziel = (k) => admin.find((e) => e.key === k)
  assert.equal(ziel('verwalten').href, '#/kalender/verwalten')
  assert.equal(ziel('importieren').href, '#/kalender/import')
  // Der Schalter heißt nach der HANDLUNG: im Lesemodus „einschalten“.
  assert.equal(rechte.kalenderMenue({ hatSchreibrecht: true, lesemodus: true })
    .find((e) => e.key === 'bearbeiten').label, 'Bearbeiten einschalten')
  assert.equal(rechte.kalenderMenue({ hatSchreibrecht: true, lesemodus: false })
    .find((e) => e.key === 'bearbeiten').label, 'Bearbeiten ausschalten')
  // Symbole: nur bekannte Namen aus dem Vorrat (DkSymbol zeichnet sonst nichts).
  for (const e of admin) {
    assert.ok(symbole.SYMBOLE[e.icon], `„${e.icon}“ fehlt im Symbolvorrat`)
  }
})

test('UX3i: Verwalten/Import hängt an der ROLLE, nicht an is_admin (je Rolle)', () => {
  // Dieselbe Regel wie bisher in KronosSidebar.vue:322-332.
  assert.equal(rechte.istKalenderAdmin({ user: 'Administrator', roles: [] }), true,
    'Konto des Systemadministrators')
  assert.equal(rechte.istKalenderAdmin({ user: 'manuel', roles: ['Administrator'] }), true)
  assert.equal(rechte.istKalenderAdmin({ user: 'hanna', roles: ['Kalenderadministrator'] }), true,
    'die Rolle „Kalenderadministrator“ behält Verwalten und Import (vorher NUR is_admin)')
  assert.equal(rechte.istKalenderAdmin({ user: 'jonas', roles: ['Mitglied', 'Moderator'] }), false,
    'Mitgliederadmins sehen keine Einträge, die der Server ablehnt')
  assert.equal(rechte.istKalenderAdmin(null), false, 'ohne Kontext kein Recht (fail closed)')
  assert.equal(rechte.istKalenderAdmin({}), false)
  assert.equal(rechte.istKalenderAdmin({ user: 42, roles: 'Administrator' }), false,
    'kaputte Antworten geben kein Recht')
  // Die Seite entscheidet über DIESE Funktion, nicht über das Boot-Objekt.
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /istKalenderAdmin as kalenderAdmin/)
  assert.doesNotMatch(quelle, /istKalenderAdmin\s*=\s*computed\(\(\)\s*=>\s*window\.__DIakonosBoot|istKalenderAdmin\s*=\s*computed\(\(\)\s*=>\s*window\.__DIakonos/,
    'kein is_admin aus dem Boot-Objekt mehr für die Verwaltungs-Einträge')
  assert.match(quelle, /get_current_user_context/, 'die Rollen kommen vom Server')
})

test('UX3i: Einschalten von „Bearbeiten“ — ohne Schreibrecht bleibt der Lesemodus', () => {
  assert.equal(rechte.lesemodusNachSchalter(true, true), false, 'mit Schreibrecht: Bearbeiten an')
  assert.equal(rechte.lesemodusNachSchalter(false, true), true, 'zurück in den Lesemodus')
  assert.equal(rechte.lesemodusNachSchalter(true, false), true,
    'ohne Schreibrecht gibt es keinen Bearbeiten-Modus (UXK-R10)')
})

test('UX3i: Lesemodus startet im LESEN (Standard wie vor UX3i)', () => {
  assert.equal(rechte.startLesemodus(null), true, 'ohne gemerkten Zustand: Lesemodus')
  assert.equal(rechte.startLesemodus('view'), true)
  assert.equal(rechte.startLesemodus('edit'), false, 'gemerkter Bearbeiten-Zustand gilt weiter')
  // Nacharbeit 07.11. Punkt 8: Die Seite hält den Modus nur im ARBEITSSPEICHER
  // (wie vor UX3i) — kein localStorage, also auch kein gemerkter Zustand.
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /store\.setViewMode\(startLesemodus\(null\)\)/,
    'die Seite startet im Lesemodus')
  assert.doesNotMatch(quelle, /localStorage\.(get|set|remove)Item/,
    'der Modus wird NICHT gemerkt (Punkt 8: nur Arbeitsspeicher)')
  assert.doesNotMatch(quelle, /setViewMode\(!hasWriteRight/, 'der always-edit-Start ist zurückgebaut')
})


test('UX3i: Kalenderauswahl — Zähler zählt nur wirklich eingeblendete Kalender', () => {
  const alle = [{ name: 'gottesdienste' }, { name: 'gruppen' }, { name: 'gemeindeleben' }]
  assert.equal(kopf.eingeblendeteZahl(alle, ['gottesdienste', 'gruppen']), 2)
  assert.equal(kopf.eingeblendeteZahl(alle, ['gottesdienste', 'alter-kalender']), 1,
    'ein Eintrag, den es nicht mehr gibt, blendet nichts ein')
  assert.equal(kopf.eingeblendeteZahl(alle, []), 0)
})

test('UX3i: Auswahl umschalten — Reihenfolge bleibt die der Liste', () => {
  const alle = [{ name: 'a' }, { name: 'b' }, { name: 'c' }]
  assert.deepEqual(kopf.auswahlUmschalten(alle, ['a'], 'c', true), ['a', 'c'],
    'neue Auswahl folgt der Liste, nicht der Klickfolge')
  assert.deepEqual(kopf.auswahlUmschalten(alle, ['a', 'c'], 'a', false), ['c'])
  assert.deepEqual(kopf.auswahlUmschalten(alle, ['a', 'geloescht'], 'b', true), ['a', 'b'],
    'unbekannte Einträge fallen weg')
})

test('UX3i: Panel-Zeile „von … · vor …“ — ohne Herkunft kein leerer Punkt', () => {
  const jetzt = new Date('2026-11-07T12:00:00Z')
  const mit = zeile.pruefZeile({
    id: 'e1', title: 'Herbstfreizeit', start: '2026-11-07T09:00:00',
    antragsteller: 'Jonas Rehberg', erstellt_am: '2026-11-04T12:00:00Z',
  }, jetzt)
  assert.equal(mit.titel, 'Herbstfreizeit')
  assert.match(mit.datum, /Sa\.|Sa,/, 'deutsches Kurzdatum')
  assert.equal(mit.herkunft, 'von Jonas Rehberg · vor 3 Tagen')
  // Der Server liefert `creation` (Erstellung) — die Wartezeit zaehlt ab da.
  const mitCreation = zeile.pruefZeile({
    id: 'e3', title: 'Jugendkreis', start: '2026-11-15 19:00:00',
    antragsteller: 'Guest', creation: '2026-11-06T12:00:00Z',
    modified: '2026-11-07T11:00:00Z',
  }, jetzt)
  assert.match(mitCreation.herkunft, /vor 1 Tag$/, 'die Wartezeit zaehlt ab `creation`, nicht ab `modified`')
  // Die Kalender-Bibliothek liefert `start` als OBJEKT `{ year, month, day }`
  // (Monat 0-basiert) — im Stack gemessen: daraus wurde „getTime is not a
  // function“ und die Spalte blieb leer.
  const objekt = zeile.pruefZeile({ id: 'e4', title: 'Hauskreis', start: { year: 2026, month: 10, day: 11 } }, jetzt)
  assert.ok(objekt, 'Objekt-Datum darf die Zeile nicht verschlucken')
  assert.match(objekt.datum, /11\.11\./, 'Objekt-Datum wird gelesen (Monat 0-basiert)')
  const ohne = zeile.pruefZeile({ id: 'e2', title: 'Chorprobe' }, jetzt)
  assert.equal(ohne.herkunft, '', 'ohne Antragsteller und Zeit kein „·“-Rest')
  assert.equal(zeile.pruefZeile(null), null)
  assert.equal(zeile.pruefZeile({ title: 'ohne Id' }), null, 'ohne Kennung keine Zeile')
  assert.equal(zeile.vorText('2026-11-07T11:59:30Z', jetzt), 'gerade eben')
  assert.equal(zeile.vorText('2026-11-07T10:00:00Z', jetzt), 'vor 2 Stunden')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Die Bauteile im DOM
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'ux3i-'))
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

/** Mountet eine SFC. `bausteine` ersetzt gleichnamige Kind-Komponenten. */
async function mounten(datei, eigenschaften, bausteine = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const gemeldet = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil, ...bausteine },
    setup: () => ({ p: eigenschaften, gemeldet }),
    template: '<Geprueft v-bind="p" v-on="gemeldet.$events || {}" @viewChange="v => gemeldet.push([\'viewChange\', v])" @kalenderAuswahlUmschalten="() => gemeldet.push([\'auswahl\'])" @terminAnlegen="() => gemeldet.push([\'anlegen\'])" @resourceToggle="() => gemeldet.push([\'ressource\'])" @hilfe="() => gemeldet.push([\'hilfe\'])" @lesemodusWechsel="v => gemeldet.push([\'lesemodusWechsel\', v])" @abgelehnteTermine="() => gemeldet.push([\'abgelehnte\'])" @update:ausgewaehlt="v => gemeldet.push([\'auswahlNeu\', v])" @schliessen="() => gemeldet.push([\'schliessen\'])" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen, gemeldet, neu: async (neue) => { Object.assign(eigenschaften, neue); await tick() } }
}

const KalenderReiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default

test('UX3i: Kopfzeile hat KEIN Auswahlfeld „Monat“ und genau EINEN Primärknopf', async () => {
  window.__DIakonosBOOT = { can_moderate: true }
  const { host, warnungen } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: 3, currentView: 'dayGridMonth', eingeblendet: 2 },
    { KalenderReiter },
  )
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')

  // 1 · kein zweiter Weg zur Ansicht
  assert.equal(host.querySelector('select'), null, 'kein Auswahlfeld mehr in der Kopfzeile')
  assert.equal(host.querySelector('#view-selector'), null, 'auch das frühere Feld ist weg')
  assert.equal(host.querySelector('.view-dropdown'), null)

  // 2 · genau ein gefüllter Knopf je Ansicht
  const primaer = [...host.querySelectorAll('.dk-ui-btn--primary')]
  assert.equal(primaer.length, 1, 'genau ein Primärknopf (A4/UX1h)')
  assert.match(primaer[0].textContent, /Termin anlegen/)
  assert.equal(primaer[0].getAttribute('aria-label'), 'Termin anlegen')
  // Der frühere Umschalter Ansehen/Bearbeiten ist fort (er war ein zweiter
  // gefüllter Knopf neben der Hauptaktion).
  assert.equal(host.querySelector('[data-toggle-group="edit-mode"]'), null)
  assert.equal(host.querySelector('.toggle-container'), null)

  // 3 · Reiter links, Werkzeuge rechts, Zähler am Kalender-Knopf
  assert.ok(host.querySelector('.header-left .kal-reiter'), 'Reiter stehen links in der Kopfzeile')
  const kalBtn = host.querySelector('[data-kalender-ausloeser="1"]')
  assert.ok(kalBtn, 'Knopf „Kalender“ fehlt')
  assert.match(kalBtn.textContent, /Kalender/)
  assert.match(kalBtn.textContent, /2/, 'Zähler der eingeblendeten Kalender')
  assert.equal(kalBtn.getAttribute('aria-haspopup'), 'dialog')
  assert.ok(host.querySelector('[aria-label="Vorheriger Zeitraum"]'), '‹ mit aria-label')
  assert.ok(host.querySelector('[aria-label="Nächster Zeitraum"]'), '› mit aria-label')
  assert.ok(host.querySelector('.dk-ui-aktionen-ausloeser'), '⋯-Menü fehlt')
})

test('UX3i: ohne Schreibrecht kein Primärknopf, aber „Nur lesen“', async () => {
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canWrite: false, canModerate: false, currentView: 'listMonth' },
    { KalenderReiter },
  )
  assert.equal(host.querySelectorAll('.dk-ui-btn--primary').length, 0)
  assert.match(host.textContent, /Nur lesen/)
  assert.equal(host.querySelector('[data-reiter="pruefen"]'), null, 'kein Reiter für Nicht-Moderatoren')
})

test('UX3i: Klick auf einen Reiter wechselt die Ansicht (kein zweiter Weg)', async () => {
  const { host, gemeldet } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { currentView: 'dayGridMonth' },
    { KalenderReiter },
  )
  const liste = host.querySelector('[data-reiter="liste"]')
  assert.ok(liste, 'Reiter „Liste“ fehlt')
  liste.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['viewChange', 'listMonth'])
})

test('UX3i: ⋯-Menü öffnet und meldet Ressourcenplan/Hilfe (ohne neue Adresse)', async () => {
  const { host, gemeldet } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { istKalenderAdmin: true },
    { KalenderReiter },
  )
  const ausloeser = host.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(ausloeser)
  assert.equal(ausloeser.getAttribute('aria-haspopup'), 'menu')
  ausloeser.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  const menue = document.querySelector('.dk-ui-aktionen-menue')
  assert.ok(menue, 'das Menü liegt nach dem Klick im DOM')
  const eintraege = [...menue.querySelectorAll('.dk-ui-aktionen-eintrag')].map((e) => e.textContent.trim())
  assert.deepEqual(eintraege, ['Ressourcenplan', 'Kalender verwalten', 'Kalender importieren',
    'Bearbeiten einschalten', 'Abgelehnte Termine', 'Hilfe & Infos'])
  // Hilfe meldet sich bei der Seite (die zeigt die vorhandene Erklärung).
  const hilfe = [...menue.querySelectorAll('.dk-ui-aktionen-eintrag')].find((e) => /Hilfe/.test(e.textContent))
  hilfe.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['hilfe'])
})

test('UX3i: Kalender-Popover blendet Kalender aus und ein, Escape schließt', async () => {
  const kalender = [
    { name: 'gottesdienste', title: 'Gottesdienste', color: '#16a34a', write: true },
    { name: 'gruppen', title: 'Gruppen & Kreise', color: '#2563eb', write: true },
    { name: 'gemeindeleben', title: 'Gemeindeleben', color: '#db2777', write: false },
  ]
  document.body.innerHTML = ''
  const { host, gemeldet } = await mounten(
    'components/kronos/KalenderAuswahl.vue',
    { open: true, kalender, ausgewaehlt: ['gottesdienste', 'gruppen', 'gemeindeleben'], loading: false },
  )
  const flaeche = document.querySelector('.dk-kal-pop')
  assert.ok(flaeche, 'Popover fehlt')
  assert.ok(!host.textContent.includes('Eintragen erlaubt'),
    '„Eintragen erlaubt“ steht NICHT als Satz in der Zeile (nur Symbol mit title)')
  const kaestchen = [...document.querySelectorAll('.dk-kal-pop-zeile input[type=checkbox]')]
  assert.equal(kaestchen.length, 3, 'je Kalender ein Kästchen')
  // Ausblenden: „Gruppen & Kreise“ abwählen -> Auswahl ohne diesen Kalender.
  kaestchen[1].checked = false
  kaestchen[1].dispatchEvent(new window.Event('change', { bubbles: true }))
  await tick()
  const neu = gemeldet.find((g) => g[0] === 'auswahlNeu')
  assert.deepEqual(neu[1], ['gottesdienste', 'gemeindeleben'], 'Kalender wird ausgeblendet')
  // Wieder einblenden.
  kaestchen[1].checked = true
  kaestchen[1].dispatchEvent(new window.Event('change', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.filter((g) => g[0] === 'auswahlNeu').at(-1)[1],
    ['gottesdienste', 'gruppen', 'gemeindeleben'], 'und wieder eingeblendet')
  // Escape schließt.
  flaeche.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.ok(gemeldet.some((g) => g[0] === 'schliessen'), 'Escape meldet „schließen“')
})

test('UX3i: Panel „Zu prüfen“ erscheint NUR für Moderatoren — und lädt erst als Moderator', async () => {
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /v-if="darfPruefen/,
    'das Panel hängt am Moderationsrecht der Seite')
  // Und das Recht gilt nur bei echtem true (fail closed).
  assert.match(quelle, /__DIakonosBOOT\??\.can_moderate\s*===\s*true/)
  // Die Kopfzeile bekommt das Recht als Eigenschaft; ohne sie gibt es keinen
  // Reiter „Zu prüfen“ (UX3d) und keine Spalte.
  const topbar = lies('components/kronos/KronosTopbar.vue')
  assert.match(topbar, /canModerate: \{ type: Boolean, default: false \}/)
  assert.match(topbar, /can_moderate: props\.canModerate === true/)
})

test('UX3i: „Abgelehnte Termine“ ist am Desktop über das ⋯-Menü erreichbar', async () => {
  // R-P1-8/FIX-7: Die Kalenderliste ist am Desktop ausgeblendet — ohne diesen
  // Weg waren die eigenen abgelehnten Termine dort nicht erreichbar.
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /@abgelehnteTermine="abgelehnteListeOeffnen"/,
    'die Seite empfängt den Menüeintrag')
  assert.match(quelle, /get_meine_abgelehnten_termine/,
    'dieselbe Abfrage wie in der Kalenderliste (kein neuer Endpunkt)')
  assert.match(quelle, /Abgelehnte Termine/, 'der Dialog ist beschriftet')
  const topbar = lies('components/kronos/KronosTopbar.vue')
  assert.match(topbar, /emit\('abgelehnteTermine'\)/, 'der Eintrag meldet sich bei der Seite')
})

test('UX3i: ⋯-Menü schaltet den Lesemodus (dezenter Schalter, kein zweiter Hauptknopf)', async () => {
  document.body.innerHTML = ''
  const { host, gemeldet } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { istKalenderAdmin: false, canWrite: true, lesemodus: true, currentView: 'dayGridMonth' },
    { KalenderReiter },
  )
  // Genau ein Primärknopf bleibt: der Schalter ist KEIN Knopf in der Leiste.
  assert.equal(host.querySelectorAll('.dk-ui-btn--primary').length, 1)
  const ausloeser = host.querySelector('.dk-ui-aktionen-ausloeser')
  ausloeser.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  const menue = document.querySelector('.dk-ui-aktionen-menue')
  assert.ok(menue, 'Menü offen')
  const eintraege = [...menue.querySelectorAll('.dk-ui-aktionen-eintrag')].map((e) => e.textContent.trim())
  assert.ok(eintraege.includes('Bearbeiten einschalten'),
    `Menü ohne Lesemodus-Schalter: ${JSON.stringify(eintraege)}`)
  assert.ok(eintraege.includes('Abgelehnte Termine'))
  const schalter = [...menue.querySelectorAll('.dk-ui-aktionen-eintrag')]
    .find((e) => /Bearbeiten/.test(e.textContent))
  schalter.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(gemeldet.at(-1), ['lesemodusWechsel', true],
    'im Lesemodus schaltet der Eintrag das Bearbeiten EIN')
})

test('UX3i: die Seite hat KEINE Emoji mehr (Systemsymbole statt ⚙/⬆/?)', () => {
  const quellen = [
    'pages/Kalender.vue',
    'components/kronos/KronosTopbar.vue',
    'components/kronos/KronosSidebar.vue',
    'components/kronos/KalenderAuswahl.vue',
    'components/kronos/KalenderPruefPanel.vue',
  ]
  const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/u
  for (const datei of quellen) {
    const text = lies(datei)
    // Der Textinhalt (nicht CSS) ist gemeint: Kommentare dürfen Zeichen nennen.
    const ohneKommentare = text.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
    const treffer = ohneKommentare.match(emoji)
    assert.equal(treffer, null, `${datei}: Emoji „${treffer?.[0]}“ in der sichtbaren Oberfläche`)
  }
})

test('UX3i: die Seite baut den Kartenkopf „Monat / KW a–b“ und die rechte Spalte', () => {
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /kwBereich\(/, 'die Kalenderwochen kommen aus der reinen Funktion')
  assert.match(quelle, /kal-karte-titel/, 'Kartenkopf links (Monat)')
  assert.match(quelle, /kal-karte-kw/, 'Kartenkopf rechts (KW)')
  assert.match(quelle, /KalenderPruefPanel/, 'rechte Spalte fehlt')
  // Ziehen/Ändern (ICAL-1b) bleibt erreichbar: der Lesemodus ist der
  // Standard, „Bearbeiten“ schaltet der Eintrag im ⋯-Menü (Review 07.11.).
  assert.match(quelle, /store\.setViewMode\(startLesemodus\(null\)\)/,
    'die Seite startet im Lesemodus')
  assert.match(quelle, /@lesemodusWechsel="onLesemodusWechsel"/,
    'der Schalter im Menü ist angeschlossen')
  assert.match(quelle, /function onLesemodusWechsel/, 'der Schalter setzt den Modus')
})

test('UX3i: die rechte Spalte zieht nach jeder Termin-Änderung nach', () => {
  const quelle = lies('pages/Kalender.vue')
  const teil = quelle.slice(quelle.indexOf('function nachAenderung'), quelle.indexOf('function nachAenderung') + 600)
  assert.match(teil, /offeneZahlLaden\(\)/, 'die Kennzahl wird neu geholt')
  assert.match(teil, /pruefPanel\.value\?\.laden\?\.\(\)/, 'die Zeilen der Spalte werden neu geladen')
  for (const fn of ['onEventCreated', 'onEventUpdated', 'onEventDeleted']) {
    assert.match(quelle, new RegExp(`function ${fn}\\(\\) \\{[\\s\\S]{0,80}nachAenderung\\(\\)`),
      `${fn} ruft nachAenderung()`)
  }
})

test('UX3i: Panel lädt die Daten aus UX3d (kein neuer Endpunkt)', () => {
  const quelle = lies('components/kronos/KalenderPruefPanel.vue')
  assert.match(quelle, /getBoardData/, 'dieselbe Abfrage wie die Tafel „Zu prüfen“')
  assert.doesNotMatch(quelle, /fetch\(/, 'kein eigener Abruf')
  assert.match(quelle, /#\/kalender\/pruefen/, 'jede Zeile führt auf die Tafel')
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Nacharbeit Review 07.11.: Chipfläche, Grenzen, Panel-Texte
// ══════════════════════════════════════════════════════════════════════════
test('UX3i: der Chip setzt seine FLÄCHE (Kalenderfarbe) — nicht nur die Schrift', () => {
  // kronos.css liest --chip-flaeche; vorher wurde nur --chip-ink gesetzt, der
  // Chip fiel auf --primary zurück und zeigte nicht die Kalenderfarbe.
  const stil = chip.chipStil('#16a34a99', { theme: 'hell' })
  assert.match(stil, /--chip-flaeche:/, '--chip-flaeche fehlt im Inline-Stil')
  assert.match(stil, /--chip-ink:/, '--chip-ink fehlt')
  assert.match(stil, /color-mix\(in srgb, #16a34a99/, 'die Fläche mischt die KALENDERFARBE')
  assert.doesNotMatch(stil, /background:/, 'kein roher Hintergrund (Token-Mischung)')
  // Ohne Kalenderfarbe bleibt es beim Standardthema — keine erfundene Fläche.
  const ohne = chip.chipStil('', { theme: 'hell' })
  assert.doesNotMatch(ohne, /--chip-flaeche:/)
})

test('UX3i: Chip-Kontrast rechnet gegen die ECHTE (durchscheinende) Fläche', () => {
  // Der Server liefert `#RRGGBBAA` (Deckkraft, z. B. 99 = 60 %). Die Rechnung
  // muss die sichtbare Fläche nehmen — vorher wurde der volle Farbton gerechnet.
  const farben = [
    '#16a34a99', '#2563eb99', '#db277799', '#78716c99',
    '#c9952f99', '#1c285099', '#f7eee099', '#ffe60099',
    '#16a34a', '#ffffff', '#000000',
  ]
  for (const theme of ['hell', 'dunkel']) {
    for (const farbe of farben) {
      const { schrift } = chip.chipFarben(farbe, { theme })
      assert.ok(/var\(--dk-(navy-900|warm-0)\)/.test(schrift),
        `${theme}/${farbe}: Schriftfarbe muss ein Theme-Token sein (war ${schrift})`)
    }
  }
  // Ein voll deckender, sehr heller Ton (Gelb) braucht dunkle Schrift.
  assert.match(chip.chipFarben('#ffe600', { theme: 'hell' }).schrift, /navy-900/)
  // Ein dunkler Ton mit Deckkraft (60 %) wird über Weiß sehr hell — dann ist
  // DUNKLE Schrift richtig und AA wird erreicht.
  const dunkelMitAlpha = chip.chipFarben('#00000099', { theme: 'hell' })
  assert.match(dunkelMitAlpha.schrift, /navy-900/)
  // Bleibt es trotz Mischung dunkel, wird die Fläche dunkler und weiß beschriftet.
  const dunkelTheme = chip.chipFarben('#000000', { theme: 'dunkel' })
  assert.match(dunkelTheme.schrift, /warm-0/)
  // Eine gesättigte Farbe, die auf BEIDEN Marken unter AA liegt, braucht die
  // dunklere Fläche (55 %) — hier geprüft über einen Ton, der auf Weiß zu
  // dunkel für dunkle Schrift und zu hell für weiße ist.
  const mittel = chip.chipFarben('#7f7f7f', { theme: 'hell' })
  assert.ok(mittel.flaeche === '' || /color-mix\(in srgb, #7f7f7f 55%/.test(mittel.flaeche),
    'entweder Standardfläche mit passender Marke oder die dunklere Fläche')
})

test('UX3i: EINE Layout-Grenze im Kalender (720 px, wie die App)', () => {
  assert.equal(breiten.KALENDER_HANDY_PX, 720)
  assert.equal(breiten.istHandyBreite(720), true, 'die Grenze gehört dazu')
  assert.equal(breiten.istHandyBreite(721), false)
  assert.equal(breiten.istHandyBreite(0), false, '0 ist keine Breite (kein Mobil-Layout)')
  assert.equal(breiten.istEngeBreite(430), true)
  assert.equal(breiten.istEngeBreite(431), false)
  // Keine eigene Layout-Zahl mehr in den Kalender-Dateien.
  const dateien = [
    'pages/Kalender.vue',
    'components/kronos/KronosCalendar.vue',
    'components/kronos/KronosTopbar.vue',
    'components/kronos/KronosSidebar.vue',
    'kronos.css',
  ]
  for (const datei of dateien) {
    const text = lies(datei)
    assert.doesNotMatch(text, /max-width:\s*768px|min-width:\s*769px/,
      `${datei}: eigene 768/769-px-Grenze neben der App-Grenze`)
    assert.doesNotMatch(text, /innerWidth\s*<=\s*(768|430)\b/,
      `${datei}: eigene Breiten-Zahl im Skript — breiten.mjs nehmen`)
  }
})

test('UX3i: Panel „Zu prüfen“ trägt Untertitel und Fußtext aus A4', () => {
  const quelle = lies('components/kronos/KalenderPruefPanel.vue')
  assert.match(quelle, /Von Gruppen eingetragen/, 'Untertitel fehlt')
  assert.match(quelle, /bis ein Administrator sie freigibt/, 'Fußtext aus A4 fehlt')
  assert.match(quelle, /dk-pruef-panel-herkunft/, 'die Zeile „von … · vor …“ fehlt')
  // Die Herkunft wird NICHT abgeschnitten (overflow hidden/ellipsis verboten).
  const stil = quelle.slice(quelle.indexOf('.dk-pruef-panel-herkunft'))
  const block = stil.slice(0, stil.indexOf('}'))
  assert.doesNotMatch(block, /text-overflow:\s*ellipsis|white-space:\s*nowrap/,
    'die Herkunft muss vollständig stehen')
})

test('UX3i: „+n weitere“ führt in die Tagesansicht und ist tastaturbedienbar', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  // Nacharbeit 07.11. Punkt 3: `moreLinkClick` gibt es in @event-calendar 5.4
  // nicht — der Klick sitzt jetzt als eigener Zuhörer in `mehrZeilenHerrichten`.
  assert.doesNotMatch(quelle, /^\s*moreLinkClick:/m, 'die Option gibt es in 5.4 nicht')
  assert.doesNotMatch(quelle, /mehrLinkDidMount/, 'der erfundene Hook ist weg')
  assert.match(quelle, /mehrZeilenHerrichten/, 'die Rest-Zeile wird beschriftet')
  assert.match(quelle, /addEventListener\('click', oeffnen\)/, 'der Klick-Zuhörer fehlt')
  assert.match(quelle, /addEventListener\('keydown'/, 'Tastatur (Enter/Leertaste) fehlt')
  assert.match(quelle, /timeGridDay/, 'Ziel ist die Tagesansicht (A4)')
  assert.match(quelle, /dayMaxEvents: true/, 'die Option ist gesetzt (Punkt 3)')
})

test('UX3i: Mobil bleibt erreichbar — Monatstitel und „Heute“ mit Symbol', () => {
  const seite = lies('pages/Kalender.vue')
  assert.match(seite, /kal-monat-mobil/, 'der Monatstitel für die Handy-Lage fehlt')
  const topbar = lies('components/kronos/KronosTopbar.vue')
  // „Heute“ war am Handy ein LEERER Knopf (Beschriftung ausgeblendet).
  assert.match(topbar, /class="todaybutton"[\s\S]{0,300}name="kalender"/,
    'das Symbol im „Heute“-Knopf fehlt')
  assert.match(topbar, /aria-label="Zum heutigen Tag springen"/)
})

// ══════════════════════════════════════════════════════════════════════════
// NACHARBEIT 2 UX3i (Nach-Review Opus, 07.11.) — sichtbare A4-Merkmale
// ══════════════════════════════════════════════════════════════════════════

test('N2-1: Chipfläche ist die GERECHNETE Fläche (kein zweites color-mix)', () => {
  const css = lies('kronos.css')
  const block = css.slice(css.indexOf('.ec-chip {'), css.indexOf('.ec-chip {'))
  const regeln = css.slice(css.indexOf('\n.ec-chip {'), css.indexOf('\n.ec-chip {'))
    .split('\n')
  // Die Deklaration des Chips isolieren: zwischen `.ec-chip {` und `}`.
  const start = css.indexOf('.ec-chip {')
  const chipBlock = css.slice(start, css.indexOf('}', start))
  assert.match(chipBlock,
    /background:\s*var\(--chip-flaeche,/,
    '`--chip-flaeche` ist die FERTIGE Fläche — sie darf nicht nochmals gemischt werden')
  assert.doesNotMatch(chipBlock,
    /color-mix\(in srgb, var\(--chip-flaeche/,
    'zweites color-mix über --chip-flaeche (Punkt 1)')
  // `chipStil` setzt die Fläche als die Mischung, gegen die gerechnet wurde.
  const stilHell = chip.chipStil('#16a34a', { theme: 'hell' })
  assert.match(stilHell, /--chip-flaeche:color-mix\(in srgb, #16a34a 22%, var\(--surface\)\)/,
    'die gesetzte Fläche ist die 22-%-Mischung, gegen die der Kontrast gerechnet wird')
  assert.match(stilHell, /--chip-ink:/, 'die Schriftfarbe reist mit')

  // Kontrast: gegen GENAU die gesetzte Fläche gerechnet, ≥ 4,5:1. Die
  // Schriftfarbe ist ein Token (--dk-navy-900 / --dk-warm-0) — für die Rechnung
  // gelten die Marken-Rohwerte, dieselben, die `chipFarben` benutzt.
  const MARKE = { 'var(--dk-navy-900)': '#00051f', 'var(--dk-warm-0)': '#ffffff' }
  for (const farbe of ['#16a34a', '#7c3aed', '#e11d48', '#16a34a99']) {
    const stil = chip.chipStil(farbe, { theme: 'hell' })
    const flaeche = /--chip-flaeche:([^;]+);/.exec(stil)?.[1]
    const inkRoh = /--chip-ink:([^;]+);/.exec(stil)?.[1]
    // Schrift = light-dark(hell, dunkel): im HELLEN gilt der erste Teil.
    const ld = /light-dark\((var\([^)]*\)),\s*(var\([^)]*\))\)/.exec(inkRoh || '')
    const inkToken = ld ? ld[1].trim() : inkRoh
    const ink = MARKE[inkToken] || inkToken
    const m = flaeche && /color-mix\(in srgb, ([^ ]+) (\d+)%, var\(--surface\)\)/.exec(flaeche)
    assert.ok(m, `Fläche für ${farbe} ist die Mischung über der Karte: ${flaeche}`)
    const anteil = Number(m[2]) / 100
    const hex = m[1].slice(0, 7)
    const deckkraft = m[1].length === 9 ? parseInt(m[1].slice(7), 16) / 255 : 1
    const basis = (() => {
      const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
      return c.map((x) => Math.round(x * deckkraft + 255 * (1 - deckkraft)))
    })()
    const ton = basis.map((x) => Math.round(x * anteil + 255 * (1 - anteil)))
    const lum = (rgb) => {
      const [r, g, b] = rgb.map((v) => {
        const c = v / 255
        return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }
    const inkC = [1, 3, 5].map((i) => parseInt(ink.slice(i, i + 2), 16))
    const l1 = lum(ton)
    const l2 = lum(inkC)
    const kontrast = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
    assert.ok(kontrast >= 4.5, `${farbe}: Kontrast gegen die gesetzte Fläche nur ${kontrast.toFixed(2)}:1`)
  }
})

test('N2-2: nur EIN eventDidMount, und er richtet die Rest-Zeile mit ein', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const treffer = quelle.match(/eventDidMount:/g) || []
  assert.equal(treffer.length, 1, 'doppelter Optionsschlüssel eventDidMount (Punkt 2)')
  const i = quelle.indexOf('eventDidMount:')
  const rumpf = quelle.slice(i, i + 420)
  assert.match(rumpf, /mehrZeilenHerrichten\(info\)/, 'als ERSTE Zeile: „+n weitere“ herrichten')
  assert.match(rumpf, /data-event-id/, 'danach: Kennung der Kachel (UX2e5)')
  assert.match(rumpf, /abgleichPlanen\(\)/, 'und der Knopf-Abgleich')
})

test('N2-4: Tageszahl-Selektor trifft den Aufbau der Bibliothek', () => {
  const css = lies('kronos.css')
  // ec-day-grid UND ec-month-view liegen auf DEMSELBEN Element — ein
  // Nachfahren-Selektor `.ec-month-view .ec-day-grid .ec-day-head` trifft nie.
  // Kommentare vorher ausblenden — der Hinweistext nennt den falschen Selektor.
  const regelnCss = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(regelnCss, /\.ec-month-view \.ec-day-grid \.ec-day-head/,
    'Nachfahren-Selektor über zwei Klassen desselben Elements (Punkt 4)')
  assert.match(css, /\.ec-month-view\.ec-day-grid \.ec-day-head \{[^}]*justify-content: flex-start/,
    'Tageszahl oben links')
  assert.match(css, /\.ec-month-view\.ec-day-grid \.ec-day-head \{[^}]*background: transparent/,
    'graues Band weg')
})

test('N2-5/N2-6: Moduswechsel baut die Menüs neu, Serien-Löschung zieht alles nach', () => {
  const quelle = lies('pages/Kalender.vue')
  const start = quelle.indexOf('function onLesemodusWechsel')
  const block = quelle.slice(start, quelle.indexOf('\n}', start))
  assert.match(block, /neuZuordnen\?\.\(\)/, '⋯-Menüs passend zum Modus (Punkt 5)')
  // Punkt 6: Serien-„deleted“ geht denselben Weg wie jede Änderung.
  const klick = quelle.slice(quelle.indexOf('function onEventClick'))
  const zweig = klick.slice(klick.indexOf("action === 'deleted'"))
  const zeilen = zweig.slice(0, zweig.indexOf('}'))
  assert.match(zeilen, /nachAenderung\(\)/, 'Serien-Löschung ruft nachAenderung (Punkt 6)')
  assert.doesNotMatch(zeilen, /refetchEvents\(\)/, 'kein nacktes refetchEvents mehr')
})

test('N2-7: die Rolle kommt aus kalenderRechte.mjs (EINE Stelle)', () => {
  const quelle = lies('components/kronos/KronosSidebar.vue')
  assert.match(quelle, /import \{ istKalenderAdmin \} from '\.\/kalenderRechte\.mjs'/,
    'die gemeinsame Prüfung wird importiert')
  assert.match(quelle, /const darfVerwalten = istKalenderAdmin\(context\)/)
  assert.doesNotMatch(quelle, /userRoles\.includes\('Kalenderadministrator'\)/,
    'kein zweites Exemplar der Rollenprüfung (Punkt 7)')
})
