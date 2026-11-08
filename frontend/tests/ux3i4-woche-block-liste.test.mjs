/**
 * UX3i4 — Kalender: Termine im Zeitraster so hoch wie ihre DAUER, Liste ohne
 * Farbbalken, Ganztags-Zeile nur bei Inhalt.
 *
 * Karte t_7b393ed7 (live-Befund Manuel, 08.11.): Seit UX3i3 trug JEDER Termin
 * die Klasse `ec-chip-event`. Im Zeitraster (Woche/Tag) setzt die Bibliothek
 * die Höhe aus der Dauer als Inline-Stil; die Chip-Regeln nahmen Fläche und
 * Innenabstand zurück — der Termin schrumpfte auf eine ~16 px hohe Pille an
 * der Startzeit („Gottesdienst 10:00“). Geprüft wird, was der Test WIRKLICH
 * ausführen kann:
 *
 *   1. `zeitBlockText` (ausgeführt): Titel ZEILE 1, Uhrzeit ZEILE 2 — dieselben
 *      Regeln wie `chipText` (ganztägig/mehrtägig/00:00 tragen keine Uhrzeit,
 *      ein Folgetag zeigt keinen fremden Startpunkt).
 *   2. Die ANSICHT entscheidet über die Optik: `istZeitrasterAnsicht()` vergibt
 *      im Zeitraster KEINE Chip-Klasse, in Monat/Liste schon — an EINER Stelle
 *      für Klasse und Inhalt (zwei Prüfungen könnten auseinanderlaufen).
 *   3. Das CSS: Der Block FÜLLT die Höhe (`block-size: 100 %`), er SETZT sie
 *      nicht — die Dauer bleibt die eine Wahrheit; Titel + Uhrzeit stehen oben.
 *   4. Liste: kein Farbbalken (Zeile und Tageshülle tragen keine eigene Fläche),
 *      das „⋯“ liegt auf DERSELBEN Zeile wie der Chip.
 *   5. Leere Ganztags-Zeile im Zeitraster ist weg (`:not(:has(article))`).
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const chip = await import(pathToFileURL(join(SRC, 'components/kronos/chipText.mjs')).href)

/**
 * Quelltext ohne Kommentare — geprüft wird Code, nicht Prosa.
 *
 * WICHTIG: nicht mit einer Regex über die GANZE Datei. Mehrere Kommentare
 * dieser Dateien ERWÄHNEN eine Media-Query in Prosa — eine Regex über den
 * ganzen Text hielt das spätere Kommentarende für einen Anweisungsanfang und
 * schnitt den Code dazwischen weg. Ergebnis: Regeln „fehlten“ in Blöcken, die
 * im Browser einwandfrei stehen. Deshalb wird Kommentar für Kommentar von
 * VORNE abgearbeitet; jedes Ende beendet den Lauf genau dort.
 *
 * `//`-Zeilen werden nur in `.vue`/`.mjs`-Quellen entfernt (`js = true`) —
 * in CSS käme `url(https://…)` sonst abhanden.
 */
function ohneKommentare(text, { js = true } = {}) {
  const quelle = String(text)
  let rest = quelle
  let aus = ''
  for (;;) {
    const start = rest.indexOf('/*')
    if (start < 0) { aus += rest; break }
    aus += rest.slice(0, start)
    const ende = rest.indexOf('*/', start + 2)
    if (ende < 0) { aus += rest.slice(start); break }
    rest = rest.slice(ende + 2)
  }
  return js ? aus.replace(/\/\/.*$/gm, '') : aus
}
const ohneCssKommentare = (text) => ohneKommentare(text, { js: false })

/**
 * Ein CSS-Block zu einem Selektor (erster Treffer, Kommentare davor/darin weg).
 *
 * Der Selektor wird bis zur öffnenden Klammer GESUCHT und der Block dann ab
 * genau dieser Klammer gelesen — so liefert die Funktion für `a.b {` und für
 * den Rest einer Selektorliste (`…, a.b {`) denselben Inhalt.
 */
function block(css, selektor) {
  const code = ohneCssKommentare(css)
  // Der LETZTE Treffer einer Selektorliste ist die abschließende Regel
  // (`…,\n a.b {`); steht der Selektor mehrfach (Rücknahme + eigene Regel),
  // gilt die ERSTE — die Rücknahme steht immer vor der Form.
  const i = code.indexOf(selektor)
  assert.ok(i >= 0, `Regel fehlt: ${selektor}`)
  const start = code.indexOf('{', i + selektor.length - 1)
  assert.ok(start > 0, `keine öffnende Klammer nach: ${selektor}`)
  return code.slice(start + 1, code.indexOf('}', start))
}
/** Alle CSS-Regeln, deren Selektorliste den Text enthält. */
function regeln(css, text) {
  const code = ohneCssKommentare(css)
  const gefunden = []
  for (const m of code.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (m[1].includes(text)) gefunden.push(m[2])
  }
  return gefunden
}
/** Die letzte Regel mit diesem Selektor (Gewinner der Kaskade). */
function letzteRegel(css, text) {
  const treffer = regeln(css, text)
  assert.ok(treffer.length > 0, `Regel fehlt: ${text}`)
  return treffer[treffer.length - 1]
}

const termin = (start, ende, zusatz = {}) => ({
  title: zusatz.title ?? 'Gottesdienst am 1. Advent',
  start: new Date(start),
  end: ende === null ? null : new Date(ende),
  allDay: zusatz.allDay ?? false,
})

// ══════════════════════════════════════════════════════════════════════════
// 1 · Block-Text: Titel oben, Uhrzeit darunter (Befund 1)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i4: der Zeitraster-Block zeigt Titel und Uhrzeit als ZWEI Stücke', () => {
  const t = termin('2026-11-08T10:00:00', '2026-11-08T11:30:00')
  const { titel, zeit } = chip.zeitBlockText(t)
  assert.equal(titel, 'Gottesdienst am 1. Advent',
    'der Titel steht allein in Zeile 1 — die Uhrzeit darf ihn nicht verdrängen')
  assert.equal(zeit, '10:00–11:30',
    'die Uhrzeit steht in Zeile 2 als Zeitraum (die Dauer ist der Block selbst)')
})

test('UX3i4: ohne echtes Ende steht nur die Startzeit', () => {
  assert.deepEqual(chip.zeitBlockText(termin('2026-11-02T19:00:00', null, { title: 'Chor' })),
    { titel: 'Chor', zeit: '19:00' })
  // Gleiche Uhrzeit = Dauer 0 (Bestandsdaten) — keine „10:00–10:00“-Zeile.
  assert.deepEqual(chip.zeitBlockText(termin('2026-11-02T10:00:00', '2026-11-02T10:00:00', { title: 'Andacht' })),
    { titel: 'Andacht', zeit: '10:00' })
})

test('UX3i4: ganztägig und mehrtägig tragen im Block keine Uhrzeit', () => {
  assert.deepEqual(chip.zeitBlockText({
    title: 'Herbstfreizeit', start: new Date('2026-11-07T00:00:00'),
    end: new Date('2026-11-09T00:00:00'), allDay: true,
  }), { titel: 'Herbstfreizeit', zeit: '' })
  assert.deepEqual(chip.zeitBlockText(termin('2026-11-07T18:00:00', '2026-11-08T12:00:00', { title: 'Nacht der Lieder' })),
    { titel: 'Nacht der Lieder', zeit: '' })
  // 00:00–00:00 ohne allDay-Flag = ganztägig (Bestandsdaten).
  assert.deepEqual(chip.zeitBlockText(termin('2026-11-08T00:00:00', '2026-11-08T00:00:00', { title: 'Gemeindefest' })),
    { titel: 'Gemeindefest', zeit: '' })
})

test('UX3i4: ein Folgetag zeigt keinen falschen Startpunkt', () => {
  // Die Prüfung der Zelle gilt auch hier (dieselbe Regel wie `chipText`).
  assert.equal(chip.zeitBlockText(termin('2026-11-08T10:00:00', '2026-11-08T11:30:00'), { tag: '2026-11-09' }).zeit, '',
    'am Folgetag steht keine Startzeit, die dort nicht stimmt')
  assert.equal(chip.zeitBlockText(termin('2026-11-08T10:00:00', '2026-11-08T11:30:00'), { tag: '2026-11-08' }).zeit,
    '10:00–11:30')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Die Ansicht entscheidet über die Optik (Befund 1/2)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i4: das Zeitraster vergibt KEINE Chip-Klasse — Monat/Liste schon', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const code = ohneKommentare(quelle)
  // EINE Prüfung für Klasse UND Inhalt (S4: ein Begriff, ein Ort, ein Verhalten).
  assert.equal((code.match(/function istZeitrasterAnsicht/g) || []).length, 1,
    'die Ansichts-Prüfung liegt an genau einer Stelle')
  assert.match(code, /const istZeitraster = istZeitrasterAnsicht\(\)/,
    'eventClassNames fragt die Ansicht ab')
  assert.match(code, /if \(!istZeitraster\) classes\.push\('ec-chip-event'\)/,
    'die Chip-Klasse hängt an der Ansicht (nicht „überall“, das war der Befund)')
  assert.doesNotMatch(code, /const classes = \['ec-chip-event'\]/,
    'die Klasse darf nicht mehr pauschal vergeben werden')
})

test('UX3i4: der Inhalt im Zeitraster ist ein BLOCK, in Monat/Liste ein Chip', () => {
  const code = ohneKommentare(lies('components/kronos/KronosCalendar.vue'))
  assert.match(code, /if \(istZeitrasterAnsicht\(\)\) \{\s*const zeilen = zeitBlockText\(/,
    'im Zeitraster baut der Kalender den Block (Titel + Uhrzeit getrennt)')
  assert.equal((code.match(/class="ec-block"/g) || []).length, 1,
    'genau EIN Block-Aufbau (kein zweiter Sonderweg)')
  assert.equal((code.match(/class="ec-chip"/g) || []).length, 1,
    'genau EIN Chip-Aufbau für Monat/Liste')
  // Beide tragen denselben Kontrast-Weg: die Fläche/Schrift aus `chipStil`.
  assert.equal((code.match(/chipStil\(sichereFarbe\(/g) || []).length, 1,
    'Fläche und Schrift werden EINMAL gerechnet und für beide Aufbauten benutzt')
  // Der volle Titel steht in beiden Aufbauten in title/aria-label.
  assert.equal((code.match(/title="' \+ safe\(titel\)/g) || []).length, 2,
    'Block und Chip tragen den vollen Titel (kein gekürzter aria-label)')
})

test('UX3i4: Zeitraster heißt Woche und Tag — nicht die Ressourcen-Zeitleiste', () => {
  const code = ohneKommentare(lies('components/kronos/KronosCalendar.vue'))
  const i = code.indexOf('function istZeitrasterAnsicht')
  const blockText = code.slice(i, code.indexOf('\n}', i))
  assert.match(blockText, /'timeGridWeek'/)
  assert.match(blockText, /'timeGridDay'/)
  assert.doesNotMatch(blockText, /resourceTimeline/,
    'die Zeitleiste stapelt je Ressource und bleibt beim Chip')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · CSS des Blocks: Höhe kommt von der DAUER, Text steht oben
// ══════════════════════════════════════════════════════════════════════════
test('UX3i4: der Block FÜLLT die Höhe der Bibliothek und setzt sie nicht', () => {
  const css = lies('kronos.css')
  const b = block(css, '.ec-block {')
  assert.match(b, /block-size:\s*100%/, 'der Block füllt die Höhe aus der Dauer')
  assert.doesNotMatch(b, /(^|;|\s)(min-)?block-size:\s*\d+px/, 'keine feste Höhe — die Dauer ist die Wahrheit')
  assert.match(b, /justify-content:\s*flex-start/, 'Titel + Uhrzeit stehen OBEN (Fläche zeigt den Rest der Dauer)')
  assert.match(b, /flex-direction:\s*column/, 'Titel und Uhrzeit stehen untereinander')
  assert.match(b, /var\(--chip-flaeche/, 'getönte Fläche aus derselben Token-Mischung wie der Monat')
  assert.match(b, /var\(--chip-ink/, 'Schrift aus derselben Kontrastrechnung wie der Monat')
  assert.doesNotMatch(b, /#[0-9a-fA-F]{3,8}/, 'keine festen Farbwerte (Dark Mode über Variablen)')
  // Die Zeile der Bibliothek darf den Block nicht mehr einrücken/umbauen.
  const zeile = block(css, '.ec-time-grid .ec-event {')
  assert.match(zeile, /padding:\s*0/, 'die Bibliothek setzt 2 px Innenabstand — der Block bringt ihn selbst mit')
  assert.match(zeile, /border:\s*0/, 'kein Rahmen: getönte Fläche statt Linie (Ä2)')
})

test('UX3i4: Block-Titel und -Uhrzeit sind eigene Zeilen mit Ellipse', () => {
  const css = lies('kronos.css')
  for (const [sel, name] of [['.ec-block-titel {', 'Titel'], ['.ec-block-zeit {', 'Uhrzeit']]) {
    const b = block(css, sel)
    assert.match(b, /display:\s*block/, `${name} ist eine eigene Zeile`)
    assert.match(b, /text-overflow:\s*ellipsis/, `${name} kürzt optisch (voller Text im title)`)
    assert.match(b, /white-space:\s*nowrap/, `${name} bricht nicht in eine zweite Zeile um`)
  }
  assert.match(block(css, '.ec-block:focus-visible {'), /outline:/, 'Tastaturfokus sichtbar')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Liste: kein Farbbalken, „⋯“ auf derselben Zeile (Befund 2)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i4: in der Liste trägt KEINE Hülle eine eigene Fläche (kein Balken)', () => {
  const css = lies('kronos.css')
  // Der sichtbare Balken links ist das eigene `span.ec-event-tag` der
  // Bibliothek (im Browser gemessen: 4 px, volle Kachelfarbe) — in der Liste
  // entfällt er; die Farbe trägt allein die Chipfläche.
  assert.match(letzteRegel(css, '.ec-list article.ec-event .ec-event-tag'),
    /display:\s*none/,
    'der Farbbalken links am Chip ist das ec-event-tag der Bibliothek')
  // Nur die Liste: Monat (Punkt) und Zeitraster (Block) bleiben unberührt.
  for (const r of regeln(css, 'ec-event-tag')) {
    assert.ok(!/^\s*\.ec-(month|time)-view/.test(r) && !/ec-time-grid/.test(r),
      'der Monat und das Zeitraster behalten ihre Darstellung')
  }
  // Die Zeile selbst (Bibliotheksfläche) bleibt zurückgenommen …
  // Geprüft werden ALLE Regeln für diese Zeile: die frühe Rücknahme (nur
  // `padding: 0`) zählt nicht — die FORM-Regel muss die Fläche aufheben.
  assert.ok(regeln(css, '.ec-list .ec-event.ec-chip-event')
    .some((r) => /background-color:\s*transparent/.test(r)),
    'die Bibliothekszeile malt sonst einen Balken über die ganze Breite')
  // … und die Tageshülle ebenso (sonst entsteht derselbe Balken eine Ebene höher).
  const huellen = regeln(css, '.ec-list .ec-day')
  assert.ok(huellen.length > 0, 'die Regel für die Listen-Tageshülle fehlt')
  assert.ok(huellen.some((r) => /--ec-day-bg-color:\s*transparent/.test(r)),
    'die Tageshülle der Liste trägt keine eigene Fläche mehr')
})

test('UX3i4: der Chip in der Liste steht auf Inhaltsbreite statt voller Zeile', () => {
  const b = block(lies('kronos.css'), '.ec-list .ec-chip {')
  assert.match(b, /inline-size:\s*fit-content/, 'sonst bleibt rechts eine eingefärbte Restfläche stehen')
  assert.match(b, /max-inline-size:\s*100%/, 'der Chip darf die Zeile nicht überlaufen')
  assert.match(b, /min-height:\s*var\(--control-h\)/, 'Klickfläche bleibt das Konzeptmaß (40/44 px)')
})

test('UX3i4: das „⋯“ liegt auf DERSELBEN Zeile wie der Chip', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const stil = quelle.slice(quelle.indexOf('<style scoped>'))
  // Die Zeile wird auf Inhaltsbreite begrenzt …
  const zeile = block(stil, '.ec-list .ec-day > article.ec-event[data-aktionen-zeile]')
  assert.match(zeile, /display:\s*inline-flex/, 'Zeile und Halter stehen nebeneinander')
  assert.match(zeile, /max-inline-size:\s*calc\(100% - var\(--control-h\)\)/,
    'rechts bleibt Platz für das „⋯“ — es schiebt den Chip nicht in die nächste Zeile')
  // … und der Halter der Liste ist kein eigener Block mehr.
  const halter = block(stil, ':deep(.ec-list .kronos-liste-aktionen-halter)')
  assert.match(halter, /display:\s*inline-flex/, 'der Halter stand vorher als Block unter dem Chip')
  assert.match(halter, /margin:\s*0/, 'kein Abstand unter der Zeile (das war die zusätzliche Zeile)')
  // Die Kennzeichnung setzt das Skript NUR für Listenzeilen (idempotent).
  const code = ohneKommentare(quelle)
  assert.match(code, /function zeilenHerrichten\(/, 'die Kennzeichnung fehlt')
  assert.match(code, /\.ec-list article\.ec-event/, 'nur Listenzeilen werden gekennzeichnet')
  assert.match(code, /removeAttribute\('data-aktionen-zeile'\)/, 'beim Verlassen der Liste wird sie zurückgenommen')
  assert.match(code, /^\s*zeilenHerrichten\(\)$/m, 'der Abgleich ruft sie auf (sonst greift keine der Regeln)')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Leere Ganztags-Zeile im Zeitraster (Befund 3)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i4: die leere Ganztags-Zeile der Woche ist weg', () => {
  const css = lies('kronos.css')
  const code = ohneKommentare(css)
  const regel = block(css, '.ec-time-grid .ec-all-day:not(:has(article)):not(:has(.ec-bg-event)) {')
  assert.match(regel, /display:\s*none/, 'die leere Zeile entfällt ganz')
  // Nichts ist ohne Bedingung ausgeblendet: mit einem Ganztagstermin MUSS die
  // Zeile stehen (sonst verschwänden die Termine selbst).
  assert.doesNotMatch(code, /\.ec-all-day\s*\{[^}]*display:\s*none/, 'die Zeile darf nicht pauschal verschwinden')
  assert.match(code, /\.ec-time-grid \.ec-all-day:not\(:has\(article\)\)/,
    'die Bedingung ist der Inhalt der Zeile, nicht die Ansicht allein')
})

test('UX3i4: `:has()` prüft hier ein KIND — die wirkungslose Form bleibt verbannt', () => {
  const code = ohneKommentare(lies('kronos.css'))
  // `:has(.ec-month-view)` an einem Knoten, der die Klasse selbst trägt, ergab
  // in Chromium 0 Treffer (UX3i3); `:not(:has(article))` eint ein Kind.
  assert.doesNotMatch(code, /:has\(\s*\.ec-(month|list|time)-view\s*\)/)
})
