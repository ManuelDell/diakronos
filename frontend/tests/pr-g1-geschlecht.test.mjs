import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// PR-G1 — Stammdaten: nach Geschlecht filtern und sortieren.
//
// Geprüft wird die ECHTE Rechnung der Seite
// (src/diakonos/pages/planrahmen/stammdaten-geschlecht.mjs) und die
// Verdrahtung in Stammdaten.vue (Filterfeld, Spaltenkopf, Hinweis,
// Massenauswahl). Kein node_modules, kein Browser — Muster wie
// tests/planrahmen-stammdaten.test.mjs.

const { geschlechtNormalisieren, geschlechtKurz, geschlechtLang, passtGeschlecht,
  passtSuche, passtGruppe, personenFiltern, nachGeschlechtSortieren, sortierungUmschalten,
  anzahlOhneAngabe, personenAnzeigen, GESCHLECHT_FILTER } =
  await import('../src/diakonos/pages/planrahmen/stammdaten-geschlecht.mjs')

const seite = readFileSync(new URL('../src/diakonos/pages/planrahmen/Stammdaten.vue', import.meta.url), 'utf8')

// ── 1. Normalisierung (Server liefert schon m/w/d, Rohwerte müssen auch gehen) ─
assert.equal(geschlechtNormalisieren('m'), 'm')
assert.equal(geschlechtNormalisieren('Männlich'), 'm')
assert.equal(geschlechtNormalisieren('  MÄNNLICH '), 'm')
assert.equal(geschlechtNormalisieren('maennlich'), 'm')
assert.equal(geschlechtNormalisieren('W'), 'w')
assert.equal(geschlechtNormalisieren('Weiblich'), 'w')
assert.equal(geschlechtNormalisieren('Divers'), 'd')
assert.equal(geschlechtNormalisieren('d'), 'd')
assert.equal(geschlechtNormalisieren(''), '')
assert.equal(geschlechtNormalisieren(null), '')
assert.equal(geschlechtNormalisieren(undefined), '')
assert.equal(geschlechtNormalisieren('unbekannt'), '', 'Unbekanntes gilt als keine Angabe')
assert.equal(geschlechtNormalisieren('m/w'), '')
assert.equal(geschlechtKurz('Männlich'), 'm')
assert.equal(geschlechtKurz(''), '–', 'Ohne Angabe zeigt einen Gedankenstrich')
assert.equal(geschlechtLang('w'), 'Weiblich')
assert.equal(geschlechtLang(''), 'Nicht angegeben')

// Filteroptionen: Alle · Männlich · Weiblich · Divers · Nicht angegeben
assert.deepEqual(GESCHLECHT_FILTER.map((o) => o.label),
  ['Alle Geschlechter', 'Männlich', 'Weiblich', 'Divers', 'Nicht angegeben'])
assert.deepEqual(GESCHLECHT_FILTER.map((o) => o.value), ['', 'm', 'w', 'd', 'ohne'])

// ── 2. Personen der Stammdaten (mit leeren Werten, wie im Betrieb) ────────────
const personen = [
  { id: 'p1', name: 'Anna A', kuerzel: 'AA', gruppen: ['Chor'], geschlecht: 'w' },
  { id: 'p2', name: 'Bernd B', kuerzel: 'BB', gruppen: ['Chor', 'Technik'], geschlecht: 'm' },
  { id: 'p3', name: 'Chris C', kuerzel: 'CC', gruppen: ['Technik'], geschlecht: '' },
  { id: 'p4', name: 'Dieter D', kuerzel: 'DD', gruppen: ['Chor'], geschlecht: 'm' },
  { id: 'p5', name: 'Eva E', kuerzel: 'EE', gruppen: ['Technik'], geschlecht: 'd' },
]

assert.deepEqual(personenFiltern(personen, { geschlecht: 'm' }).map((p) => p.id), ['p2', 'p4'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'w' }).map((p) => p.id), ['p1'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'd' }).map((p) => p.id), ['p5'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'ohne' }).map((p) => p.id), ['p3'])
assert.deepEqual(personenFiltern(personen, {}).map((p) => p.id), ['p1', 'p2', 'p3', 'p4', 'p5'],
  'Ohne Wahl bleiben alle Personen')

// Zusammenwirken mit Suche und Gruppe (alle Filter wirken gemeinsam)
assert.deepEqual(personenFiltern(personen, { geschlecht: 'm', gruppe: 'Technik' }).map((p) => p.id), ['p2'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'w', gruppe: 'Technik' }).map((p) => p.id), [])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'm', suche: 'die' }).map((p) => p.id), ['p4'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'ohne', suche: 'chris' }).map((p) => p.id), ['p3'])
assert.deepEqual(personenFiltern(personen, { geschlecht: 'm', suche: 'eva' }).map((p) => p.id), [])

// Einzelfilter bleiben einzeln prüfbar
assert.equal(passtGeschlecht(personen[2], ''), true)
assert.equal(passtGeschlecht(personen[2], 'ohne'), true)
assert.equal(passtGeschlecht(personen[2], 'm'), false)
assert.equal(passtSuche(personen[1], 'bb'), true)
assert.equal(passtGruppe(personen[1], 'Technik'), true)
assert.equal(passtGruppe(personen[1], 'Chor'), true)
assert.equal(passtGruppe(personen[2], 'Chor'), false)

// Leere/NULL-Werte aus dem Server: kein Absturz, keine falsche Zuordnung
const roh = [{ id: 'x1', name: 'Roh Eins', geschlecht: null },
  { id: 'x2', name: 'Roh Zwei', geschlecht: 'Männlich' },
  { id: 'x3', name: 'Roh Drei' }]
assert.deepEqual(personenFiltern(roh, { geschlecht: 'm' }).map((p) => p.id), ['x2'])
assert.deepEqual(personenFiltern(roh, { geschlecht: 'ohne' }).map((p) => p.id), ['x1', 'x3'])

// ── 3. Sortierung nach Geschlecht, dann Name ─────────────────────────────────
const unsortiert = [
  { id: 'q1', name: 'Zoe', geschlecht: 'w' },
  { id: 'q2', name: 'Anton', geschlecht: '' },
  { id: 'q3', name: 'Bernd', geschlecht: 'm' },
  { id: 'q4', name: 'Anna', geschlecht: 'm' },
  { id: 'q5', name: 'Cem', geschlecht: 'd' },
]
assert.deepEqual(nachGeschlechtSortieren(unsortiert).map((p) => p.id), ['q4', 'q3', 'q1', 'q5', 'q2'],
  'Auf: Männer (Name), Frauen, Divers, ohne Angabe zuletzt')
assert.deepEqual(nachGeschlechtSortieren(unsortiert, 'ab').map((p) => p.id), ['q2', 'q5', 'q1', 'q4', 'q3'],
  'Ab: umgekehrte Geschlechtsfolge, Name bleibt aufsteigend')
assert.deepEqual(unsortiert.map((p) => p.id), ['q1', 'q2', 'q3', 'q4', 'q5'],
  'Sortieren verändert die Eingabe nicht')
// Deutsche Sortierung inkl. Umlauten
assert.deepEqual(nachGeschlechtSortieren([
  { id: 'u1', name: 'Öttinger', geschlecht: 'm' },
  { id: 'u2', name: 'Ober', geschlecht: 'm' },
]).map((p) => p.id), ['u2', 'u1'])
// Ohne Sortierung: Server-Reihenfolge bleibt
assert.deepEqual(personenAnzeigen(unsortiert, {}).map((p) => p.id), ['q1', 'q2', 'q3', 'q4', 'q5'])
assert.deepEqual(personenAnzeigen(unsortiert, { sortierung: { spalte: 'geschlecht', richtung: 'auf' } })
  .map((p) => p.id), ['q4', 'q3', 'q1', 'q5', 'q2'])
// Sortierung wirkt NACH dem Filter (nur die Auswahl wird sortiert)
assert.deepEqual(personenAnzeigen(unsortiert, {
  geschlecht: 'm', sortierung: { spalte: 'geschlecht', richtung: 'auf' },
}).map((p) => p.id), ['q4', 'q3'])

// Spaltenkopf: auf → ab → ohne
let s = sortierungUmschalten(null, 'geschlecht')
assert.deepEqual(s, { spalte: 'geschlecht', richtung: 'auf' })
s = sortierungUmschalten(s, 'geschlecht')
assert.deepEqual(s, { spalte: 'geschlecht', richtung: 'ab' })
s = sortierungUmschalten(s, 'geschlecht')
assert.deepEqual(s, { spalte: '', richtung: 'auf' }, 'Dritter Klick hebt die Sortierung auf')

// ── 4. Hinweis bei fehlenden Angaben ─────────────────────────────────────────
assert.equal(anzahlOhneAngabe(personen), 1)
assert.equal(anzahlOhneAngabe(roh), 2)
assert.equal(anzahlOhneAngabe([]), 0)
assert.equal(anzahlOhneAngabe(null), 0)

// ── 5. Massenauswahl: „Alle sichtbaren auswählen" folgt dem Geschlechtsfilter ─
// Die Seite wählt über `gefiltertePersonen` — hier nachgestellt:
const sichtbar = personenAnzeigen(personen, { geschlecht: 'm' })
assert.equal(sichtbar.length, 2, 'Alle sichtbaren = nur die gefilterten Männer')
const auswahl = new Set(sichtbar.map((p) => p.id))
assert.deepEqual([...auswahl].sort(), ['p2', 'p4'], 'Massenaktion trifft nur die Männer')

// ── 6. Verdrahtung in der Seite ──────────────────────────────────────────────
assert.match(seite, /import \{[^}]*personenAnzeigen[^}]*\} from '\.\/stammdaten-geschlecht\.mjs'/s,
  'Seite nutzt die gemeinsame Rechnung')
assert.match(seite, /GESCHLECHT_FILTER/, 'Filteroptionen kommen aus der gemeinsamen Liste')
assert.match(seite, /v-model="geschlechtWahl"/, 'Auswahlfeld Geschlecht ist gebunden')
assert.match(seite, /aria-label="Nach Geschlecht filtern"/, 'Filterfeld hat eine Beschriftung')
assert.match(seite, /class="dk-form-select pr-stamm-geschlechtwahl"/,
  'Gleiche Optik wie Gruppenauswahl (dk-form-select)')
assert.match(seite, /sortierungUmschalten/, 'Spaltenkopf schaltet die Sortierung')
assert.match(seite, /aria-sort=/, 'Spaltenkopf meldet die Sortierung an Screenreader')
assert.match(seite, /geschlechtKurz\(/, 'Kurzanzeige je Person')
assert.match(seite, /geschlechtLang\(/, 'aria-label je Anzeige')
assert.match(seite, /ohne Angabe zum Geschlecht/, 'Hinweis bei fehlenden Angaben')
assert.match(seite, /#\/personen/, 'Hinweis verlinkt auf „Personen“')
// Kein neuer Primärknopf, keine festen Farb-/Abstandswerte in den neuen Regeln
assert.doesNotMatch(seite, /pr-stamm-geschlechtwahl[^}]*#[0-9a-fA-F]{3}/,
  'Keine eigenen Farbwerte für das neue Feld')

console.log('pr-g1: alle Prüfungen grün')
