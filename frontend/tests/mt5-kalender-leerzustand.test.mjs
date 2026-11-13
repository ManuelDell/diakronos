/**
 * MT-5 — Wächter: im Kalender steht KEIN englischer Bibliothekstext mehr.
 *
 * BEFUND (Manuel, Live 11.11.): Die Ansicht „Liste“ zeigte ohne Termine
 * „No events“ — der fest eingebaute Text von `@event-calendar/build`.
 *
 * GEPRÜFT WIRD:
 *  A. Die Leerzustand-Quelle (`kalenderLeerzustand.mjs`) liefert deutschen
 *     Text und KEINEN englischen.
 *  A2. Die Quelle baut kein HTML: sie liefert Angaben (reiner Text), die Vue
 *     in DkEmpty setzt — damit kann fremder Text gar nicht in Auszeichnung
 *     gelangen.
 *  B. Die Option, die der Bibliothek untergelegt wird, heißt `noEventsContent`
 *     — die eine Stelle, die das Paket dafür kennt (Bundle 5.18.0) — und ihr
 *     Inhalt sind DOM-Knoten der ECHT GERENDERTEN DkEmpty-Komponente
 *     (`{ domNodes }`). Eine Zeichenkette würde maskiert, selbstgebautes HTML
 *     trüge die (scoped) Gestaltung nicht (Review 11.11.).
 *  C. `KronosCalendar.vue` setzt sie EINMAL beim Aufbau — kein Nachziehen je
 *     Ansichtswechsel: die Bibliothek erwartet `setOption(name, value)`, ein
 *     Objekt als erstes Argument bliebe still wirkungslos.
 *  D. Die bisher übersetzten Bibliothekstexte stehen weiter da: „ganztägig“
 *     (statt „all-day“) und „+n weitere“ (statt „+n more“).
 *  E. Der Leerzustand ist wirklich der App-Baustein DkEmpty — gemessen am
 *     GERENDERTEN DOM (Symbol, Titel, Erklärung), Gestaltung aus dessen
 *     eigenen Regeln, keine Kopie im Kalender-Baustein.
 *  F. Der Wächter erkennt englische Texte wirklich (Gegenprobe): er muss
 *     „No events“, „all-day“ und „+2 more“ melden und deutschen Text nicht.
 *
 * Der Test liest nur Dateien innerhalb von frontend/ (Regel 13), braucht kein
 * Netz und rendert DkEmpty wirklich (vue + jsdom aus `node_modules`).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const hier = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(hier, '..')
const SRC = path.join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(path.join(SRC, rel), 'utf8')

const L = await import(pathToFileURL(path.join(SRC, 'components/kronos/kalenderLeerzustand.mjs')).href)

// ── Wächter für englische Bibliothekstexte ────────────────────────────────
// Eigene Kopie statt eines Exports aus dem Quellmodul (Review 11.11., Punkt 4):
// die Prüfung wird im Betrieb nirgends gebraucht, nur für Belege.
// ACHTUNG — keine Deckungsgleichheit mit dem Beleg-Skript: die Liste in
// `tools/demo/mt5-screenshots.mjs` führt FÜNF Wörter (dazu „All Day“ und
// „Today“), dieser Wächter prüft bewusst nur die DREI Wortfamilien, die die
// Bibliothek hier selbst setzt. Test F belegt nur die eigene Liste.
const ENGLISCHE_MUSTER = [
  { name: 'no-events', re: /\bNo events\b/i },
  { name: 'all-day', re: /\ball[- ]day\b/i },
  { name: 'more', re: /^\s*\+\s*\d+\s+more\b/i },
]

/**
 * Enthält ein Textstück noch einen ENGLISCHEN Bibliothekstext? Prüft genau
 * die Texte, die die Bibliothek selbst setzt (nicht die Termine des Nutzers).
 * Rückgabe: Liste der gefundenen englischen Stücke (leer = sauber).
 *
 * „Today“ steht bewusst NICHT in der Liste: die Knopfleiste der Bibliothek
 * ist abgeschaltet (`headerToolbar: false`) und ein Termin darf „Today“
 * heißen — ein Wächter, der darauf anspringt, wäre wertlos.
 */
function englischeBibliothekstexte(text) {
  const roh = String(text ?? '')
  const treffer = []
  for (const { name, re } of ENGLISCHE_MUSTER) {
    if (re.test(roh)) treffer.push(name)
  }
  return treffer
}

// ── DkEmpty wirklich rendern (vue/compiler-sfc + jsdom) ───────────────────

function bauteilSchreiben(abs, ausgabe, wache = new Set()) {
  if (wache.has(abs)) return
  wache.add(abs)
  const quelle = readFileSync(abs, 'utf8')
  const { descriptor } = parse(quelle, { filename: abs })
  assert.ok(descriptor.script || descriptor.scriptSetup, `${abs}: kein Skript`)

  const skript = compileScript(descriptor, { id: path.basename(abs), inlineTemplate: true })
  let code = skript.content
  if (!/_createElementVNode|_createCommentVNode|_createBlock/.test(code)) {
    const tpl = compileTemplate({
      id: path.basename(abs),
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${abs}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
    const ohneExport = tpl.code.replace(/export function render/, 'function render')
    const importe = new Set()
    const rest = []
    for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
      if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
        for (const name of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
          if (name.trim()) importe.add(name.trim())
        }
        continue
      }
      rest.push(zeile)
    }
    const rumpf = rest.join('\n')
      .replace(/\bexport const /g, 'const ')
      .replace(/export default /g, 'const __bauteil = ')
    code = `import { ${[...importe].join(', ')} } from 'vue'\n${rumpf}`
      + '\n__bauteil.render = render\nexport default __bauteil\n'
  }
  code = code.replace(/from\s+'(\.\.?\/[^']+)'/g, (ganz, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue')) {
      bauteilSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.vue$/, '.mjs'))
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, path.relative(SRC, abs).replace(/\.vue$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

/** DkEmpty mit den Angaben aus der Quelle rendern — Rückgabe: DOM-Element. */
async function leerzustandRendern() {
  const { JSDOM } = await import('jsdom')
  const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  globalThis.Node = dom.window.Node
  globalThis.Element = dom.window.Element
  globalThis.SVGElement = dom.window.SVGElement

  const ausgabe = mkdtempSync(path.join(tmpdir(), 'mt5-'))
  const bauteil = path.join(SRC, 'components/ui/DkEmpty.vue')
  bauteilSchreiben(bauteil, ausgabe)
  // `vue` als Paketname finden: ein Zeiger auf die echten Pakete des Frontends.
  symlinkSync(path.join(FRONTEND, 'node_modules'), path.join(ausgabe, 'node_modules'), 'dir')
  try {
    const { createApp, h, nextTick } = await import('vue')
    const modul = await import(pathToFileURL(
      path.join(ausgabe, path.relative(SRC, bauteil).replace(/\.vue$/, '.mjs')),
    ).href)
    const ziel = dom.window.document.createElement('div')
    dom.window.document.body.appendChild(ziel)
    const app = createApp({ render: () => h(modul.default, L.leerzustandInhalt()) })
    app.mount(ziel)
    await nextTick()
    return { el: ziel, app }
  } finally {
    rmSync(ausgabe, { recursive: true, force: true })
  }
}

const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()

// ══════════════════════════════════════════════════════════════════════════
// A · Der Leerzustand ist deutsch
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · A: Leerzustand ist deutsch und ohne englischen Bibliothekstext', () => {
  const inhalt = L.leerzustandInhalt()
  const ganz = `${inhalt.title} ${inhalt.text}`
  assert.deepEqual(englischeBibliothekstexte(ganz), [],
    'im Leerzustand steht kein englischer Bibliothekstext')
  assert.equal(inhalt.title, 'Keine Termine', 'Titel „Keine Termine“')
  assert.equal(inhalt.text, 'In diesem Zeitraum ist nichts eingetragen.', 'erklärender Satz')
  assert.ok(!/No events/i.test(ganz), 'der englische Text ist weg')
  // Begriff der App: „Termin“, nie „Event“/„Element“.
  assert.ok(!/\bEvent(s)?\b/.test(ganz), 'kein „Event“ im sichtbaren Text')
})

test('MT-5 · A2: Quelle baut kein HTML — ihre Angaben sind reiner Text', () => {
  // Korrigiert (Review 11.11., Punkt 5): die frühere Fassung prüfte das Fehlen
  // von `<script` in einem HTML, das es hier gar nicht mehr gibt. Die richtige
  // Aussage: die Quelle liefert ANGABEN, keinen Auszeichnungstext — DkEmpty
  // setzt `{{ title }}`/`{{ text }}`, Vue maskiert. Fremdtext kann nicht in
  // HTML gelangen, weil niemand hier HTML baut.
  const inhalt = L.leerzustandInhalt()
  for (const [feld, wert] of Object.entries(inhalt)) {
    assert.equal(typeof wert, 'string', `${feld} ist reiner Text`)
    assert.ok(!/[<>]/.test(wert), `${feld} enthält keine Auszeichnung`)
  }
  const quelle = lies('components/kronos/kalenderLeerzustand.mjs')
  assert.ok(!/innerHTML|'<div|<p /.test(quelle), 'die Quelle baut keine HTML-Zeichenkette')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Die eine Stelle der Bibliothek: noEventsContent
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · B: Option heißt noEventsContent und trägt den GERENDERTEN Baustein', () => {
  const q = lies('components/kronos/KronosCalendar.vue')
  assert.match(q, /noEventsContent: \{ domNodes: \[leerzustandKnoten\(\)\.el\] \}/,
    'die Option bekommt DOM-Knoten (kein String, kein fremdes HTML)')
  assert.match(q, /import DkEmpty from '\.\.\/ui\/DkEmpty\.vue'/, 'DkEmpty ist eingebunden')
  // Der Knoten entsteht mit der ECHTEN Komponente, nicht als HTML-Kopie.
  const rumpf = q.slice(q.indexOf('function leerzustandKnoten()'))
  const bisEnde = rumpf.slice(0, rumpf.indexOf('\n}\n'))
  assert.match(bisEnde, /createApp\(\{ render: \(\) => h\(DkEmpty, leerzustandInhalt\(\)\) \}\)/,
    'DkEmpty wird als Komponente gerendert (h/createApp)')
  assert.match(bisEnde, /\.mount\(halter\)/, 'und wirklich gemountet')
  assert.ok(!/innerHTML/.test(bisEnde), 'kein selbstgebautes HTML')
})

test('MT-5 · B3: EIN Text für alle Listen — die Auswahl „Liste“ ist listMonth', () => {
  // Korrigiert (Review 11.11., Punkt 3): die Bibliothek liest
  // `noEventsContent` NUR im Listen-Plugin; die Annahme „Raster zeigt einen
  // anderen Text“ war falsch. Es gibt genau EINEN Text.
  const inhalt = L.leerzustandInhalt()
  assert.equal(inhalt.text, 'In diesem Zeitraum ist nichts eingetragen.')
  assert.ok(!('liste' in inhalt) && !('raster' in inhalt), 'keine Unterscheidung nach Lage')
  // Bodenprobe an der echten Quelle der Ansichten (mobilAnsicht.mjs).
  const ansichten = lies('components/kronos/mobilAnsicht.mjs')
  assert.match(ansichten, /id: 'liste', label: 'Liste', ansicht: 'listMonth'/,
    'die Auswahl „Liste“ ist listMonth')
})

test('MT-5 · B2: Der ersetzte englische Text ist benannt', () => {
  assert.equal(L.ENGLISCHER_LEERTEXT, 'No events')
  assert.deepEqual(englischeBibliothekstexte(L.ENGLISCHER_LEERTEXT), ['no-events'])
})

// ══════════════════════════════════════════════════════════════════════════
// C · Der Kalender setzt sie — EINMAL beim Aufbau
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · C: KronosCalendar unterlegt die Option beim Aufbau', () => {
  const q = lies('components/kronos/KronosCalendar.vue')
  assert.match(q, /import \{ leerzustandInhalt \} from '\.\/kalenderLeerzustand\.mjs'/,
    'die eine Quelle wird eingebunden')
  assert.match(q, /noEventsContent: \{ domNodes: \[leerzustandKnoten\(\)\.el\] \}/,
    'beim Aufbau wird der Leerzustand gesetzt')
})

test('MT-5 · C2: Kein Nachziehen je Ansichtswechsel (setOption nimmt Name + Wert)', () => {
  const q = lies('components/kronos/KronosCalendar.vue')
  // Die Bibliothek (5.18.0) ruft `setOption(e, t, n)` — ein OBJEKT als erstes
  // Argument landete unter dem Schlüssel „[object Object]“ und blieb still
  // wirkungslos (Review 11.11., Punkt 2). Der Nachzieher ist deshalb weg.
  assert.ok(!/leerzustandNachziehen/.test(q), 'kein Nachzieher mehr im Baustein')
  assert.ok(!/setOption\(leerzustandOptionen/.test(q), 'kein setOption mit einem Options-Objekt')
  // Und der Text steht genau EINMAL in der Quelle (Prinzip S4).
  const treffer = q.match(/noEventsContent:/g) || []
  assert.equal(treffer.length, 1, 'noEventsContent wird genau einmal gesetzt')
})

// ══════════════════════════════════════════════════════════════════════════
// D · Die übrigen englischen Bibliothekstexte bleiben übersetzt
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · D: „all-day“ und „+n more“ der Bibliothek bleiben übersetzt', () => {
  const q = lies('components/kronos/KronosCalendar.vue')
  assert.match(q, /allDayContent:\s*\{ text: 'ganztägig' \}/, 'all-day → ganztägig')
  assert.match(q, /moreLinkContent:\s*\(info\) => `\+\$\{info\.num\} weitere`/, '+n more → +n weitere')
})

// ══════════════════════════════════════════════════════════════════════════
// E · WIRKUNG: der Leerzustand IST der App-Baustein DkEmpty
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · E: der Leerzustand trägt die Anatomie von DkEmpty (gerendert gemessen)', async () => {
  const { el, app } = await leerzustandRendern()
  try {
    assert.match(el.firstElementChild.className, /\bdk-ui-empty\b/, 'Wurzel ist die des Bausteins')
    const symbol = el.querySelector('.dk-ui-empty-icon')
    const titel = el.querySelector('.dk-ui-empty-title')
    const satz = el.querySelector('.dk-ui-empty-text')
    assert.ok(symbol, 'Symbol des Bausteins steht da')
    assert.equal(symbol.getAttribute('aria-hidden'), 'true', 'Symbol ist für Vorleser ausgeblendet')
    assert.equal(text(titel), 'Keine Termine')
    assert.equal(text(satz), 'In diesem Zeitraum ist nichts eingetragen.')
    // Kein zweiter Primärknopf in der Fläche (S1) — DkEmpty ohne Handler.
    assert.equal(el.querySelectorAll('button').length, 0, 'kein Knopf im Leerzustand')
    assert.deepEqual(englischeBibliothekstexte(text(el)), [], 'kein englischer Rest im Gerüst')
  } finally {
    app.unmount()
  }
  // Die Gestaltung kommt aus DkEmpty.vue selbst (scoped) — der
  // Kalender-Baustein baut sie NICHT nach.
  const leer = lies('components/ui/DkEmpty.vue')
  for (const regel of ['.dk-ui-empty-icon', '.dk-ui-empty-title', '.dk-ui-empty-text']) {
    assert.ok(leer.includes(regel), 'Regel existiert in DkEmpty.vue: ' + regel)
  }
  const q = lies('components/kronos/KronosCalendar.vue')
  const stil = q.slice(q.indexOf(':deep(.ec-no-events)'))
  assert.ok(!/dk-ui-empty-(icon|title|text)/.test(stil), 'keine nachgebaute Optik im Kalender-Baustein')
  assert.match(q, /:deep\(\.ec-no-events\)\s*\{/, 'der Leerkasten der Bibliothek wird gestaltet')
})

// ══════════════════════════════════════════════════════════════════════════
// F · Gegenprobe: der Wächter erkennt englische Texte wirklich
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · F: Gegenprobe — englische Bibliothekstexte werden erkannt', () => {
  assert.deepEqual(englischeBibliothekstexte('No events'), ['no-events'])
  assert.deepEqual(englischeBibliothekstexte('<div>all-day</div>'), ['all-day'])
  assert.deepEqual(englischeBibliothekstexte('+2 more'), ['more'])
  // Unser Text schlägt NICHT an (sonst wäre der Wächter wertlos).
  assert.deepEqual(englischeBibliothekstexte('Keine Termine'), [])
  assert.deepEqual(englischeBibliothekstexte('ganztägig'), [])
  assert.deepEqual(englischeBibliothekstexte('+2 weitere'), [])
  // „Today“ (ein Termintitel) soll NICHT anschlagen — Eigennamen bleiben.
  assert.deepEqual(englischeBibliothekstexte('Today'), [],
    'ein Termin darf „Today“ heißen — der Wächter springt darauf nicht an')
  // Die Beleg-Wortliste im Skript `tools/demo/mt5-screenshots.mjs` liegt
  // AUSSERHALB von frontend/ (Regel 13) — im Abbild nicht lesbar. Sie ist auch
  // NICHT deckungsgleich: dort stehen fünf Wörter („All Day“ und „Today“
  // zusätzlich, weil das Skript nur das Bibliotheks-Gerüst prüft). Hier zählt
  // allein die eigene Liste.
  assert.deepEqual(ENGLISCHE_MUSTER.map((m) => m.name), ['no-events', 'all-day', 'more'],
    'der Wächter prüft die drei Wortfamilien der Bibliothek')
})

// ══════════════════════════════════════════════════════════════════════════
// G · Die Mobil-Liste (A10) bleibt deutsch — Fremdbausteine, NICHT das Beleg-Skript
// ══════════════════════════════════════════════════════════════════════════
test('MT-5 · G: Mini-Monat stellt den Monat weiter, Mobile-Liste bleibt deutsch', () => {
  // Umbenannt (MT-5b): der frühere Name sprach vom Beleg-Skript, geprüft
  // werden hier aber FREMDE Bausteine — das Skript selbst liegt unter
  // tools/demo/ (ausserhalb frontend/, Regel 13) und ist hier nicht lesbar.
  // Der Blätter-Weg der Oberfläche (Mini-Monat → Seite → Bibliothek) ist die
  // Angabe für den Operator.
  const quelle = lies('components/kronos/KalenderMiniMonat.vue')
  assert.match(quelle, /\$emit\('vor'\)/, 'Mini-Monat kann den Monat weiterstellen')
  const seite = lies('pages/Kalender.vue')
  // MINIMONAT-1: Der Pfeil bewegt den HANDY-Monat selbst (`monatVor` →
  // `monatBewegen`), nicht mehr die Bibliothek — in der Listenansicht ist der
  // Raster gar nicht gemountet (`calendarRef` = null). Das Verhalten prüft
  // `tests/minimonat1-blaettern.test.mjs`; hier bleibt nur der Anschluss.
  assert.match(seite, /@vor="monatVor"/,
    'der Pfeil „nächster Monat“ ist an den Monatsschritt der Seite angeschlossen')
  // Der Klartext der Mobil-Liste bleibt deutsch und ohne „Event“.
  assert.ok(!/\bNo events\b/.test(lies('components/kronos/KalenderTagesliste.vue')))
  assert.match(lies('components/kronos/KalenderTagesliste.vue'), /An diesem Tag ist nichts eingetragen\./)
})
