/**
 * BS-1a2 — Nachbesserung Website-Freigaben: was der Server jetzt zusichert.
 *
 * Ergänzt `bs1a-website-freigaben.test.mjs` um die Befunde des Opus-Reviews
 * (die Oberfläche kommt mit einer eigenen Karte, dieser Test hält den
 * VERTRAG fest, damit sie nicht gegen eine erfundene Form baut):
 *
 *   (F0) Bauprobe: dieser Test läuft wirklich — so ist das rote Ergebnis
 *        eines Vertragsbruchs von einem stillen Nichtlauf zu unterscheiden.
 *   (F2) `freigaben_lesen` ist GET, die fünf schreibenden Endpunkte prüfen
 *        die Methode selbst (`_nur_post`) und antworten auf alles außer POST
 *        mit 405 — sonst wäre jeder Freigabe-Schalter per Link auslösbar.
 *   (F3) Ein abgeleiteter Slug weicht auf `-2`/`-3` aus (Regelmodul).
 *   (F4) Ein Wettlauf auf den Unique-Index endet in 417 „bereits vergeben“.
 *   (F5) `sortierung` wird vor beiden Zweigen geprüft.
 *   (F7) DEL (0x7f) ist ein Steuerzeichen und wird abgelehnt.
 *   (F1) Das Frappe-Drift-Overlay ist wieder da und trägt die BS-1a-Spalten
 *        nicht (sie sind EIGENE_SPALTEN).
 *
 * Geprüft wird Quelltext (Regex), nicht das Aussehen; Lauf im Docker-Build
 * über `node --test`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py')
const REGELN = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'freigaben.py')
const MIGRATION = join(REPO, 'backend', 'alembic', 'versions', 'bs1a_website_freigaben.py')
const OVERLAY = join(REPO, 'inventar', 'schema_overlay.json')
const QUELLEN = join(REPO, 'backend', 'tests', 'test_schema_drift.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

/** Rumpf einer Endpunkt-Funktion (bis zur nächsten `def` auf Spalte 1). */
function rumpf(quelle, name) {
  const start = quelle.indexOf(`def ${name}(`)
  assert.ok(start !== -1, `Endpunkt ${name} fehlt`)
  const naechste = quelle.indexOf('\ndef ', start + 1)
  return quelle.slice(start, naechste === -1 ? undefined : naechste)
}

const SCHREIBEND = [
  'freigabe_setzen',
  'beitrag_auf_website',
  'postfach_speichern',
  'postfach_loeschen',
  'kategorie_oeffentlich',
]

test('BS-1a2 (F0): Bauprobe — der Nachbesserungs-Vertragstest läuft', () => {
  assert.equal(1 + 1, 2)
})

test('BS-1a2 (F2): die fünf schreibenden Endpunkte nehmen nur POST', () => {
  const quelle = lies(API)
  for (const name of SCHREIBEND) {
    const block = rumpf(quelle, name)
    assert.match(
      block,
      /def \w+\(request=None/,
      `${name} nimmt keinen request entgegen — die Methode ist damit unprüfbar`,
    )
    assert.match(block, /_nur_post\(request\)/, `${name} prüft die Methode nicht`)
    // Die Prüfung steht VOR Rollen-Gate und DB-Zugriff.
    const posPruefung = block.indexOf('_nur_post(request)')
    const posRolle = block.indexOf('_require_website_rolle()')
    assert.ok(posPruefung !== -1 && posRolle !== -1 && posPruefung < posRolle,
      `${name}: Methodenprüfung muss vor dem Rollen-Gate stehen`)
  }
})

test('BS-1a2 (F2): 405 ist der Vertrag, freigaben_lesen bleibt GET', () => {
  const quelle = lies(API)
  assert.match(quelle, /status_code=405/)
  assert.match(quelle, /"MethodNotAllowed"/)
  assert.match(quelle, /"Allow": "POST"/)
  // Lesen ist bewusst NICHT in der Nur-POST-Menge.
  const menge = quelle.slice(quelle.indexOf('_NUR_POST = frozenset('), quelle.indexOf('def _nur_post('))
  assert.doesNotMatch(menge, /freigaben_lesen/)
  for (const name of SCHREIBEND) {
    assert.match(menge, new RegExp(`"${name}"`), `${name} fehlt in _NUR_POST`)
  }
})

test('BS-1a2 (F3): abgeleiteter Slug weicht auf -2/-3 aus, eingegebener nicht', () => {
  const regeln = lies(REGELN)
  assert.match(regeln, /def slug_verfuegbar\(/)
  assert.match(regeln, /SLUG_ZUSATZ_AB = 2/)
  assert.match(regeln, /f"-\{nummer\}"/)
  assert.match(regeln, /SLUG_MAX - len\(zusatz\)/, 'Längengrenze beim Ausweichen fehlt')
  const quelle = lies(API)
  assert.match(quelle, /regeln\.slug_verfuegbar\(/)
  // Der eingegebene Slug läuft NICHT durch slug_verfuegbar (Konflikt bleibt 417).
  const block = rumpf(quelle, 'freigabe_setzen')
  const posEingabe = block.indexOf('regeln.slug_pruefen, slug')
  const posAbleitung = block.indexOf('regeln.slug_verfuegbar(')
  assert.ok(posEingabe !== -1 && posAbleitung !== -1 && posEingabe < posAbleitung,
    'Reihenfolge Slug-Prüfung/Ableitung stimmt nicht')
})

test('BS-1a2 (F4): Wettlauf auf den Unique-Index wird zu 417 "vergeben"', () => {
  const block = rumpf(lies(API), 'freigabe_setzen')
  assert.match(block, /except IntegrityError/)
  assert.match(block, /bereits vergeben/)
  assert.match(block, /ValidationError/)
})

test('BS-1a2 (F5): sortierung wird vor beiden Zweigen geprüft', () => {
  const block = rumpf(lies(API), 'postfach_speichern')
  const posPruefung = block.indexOf('wert_sortierung = int(')
  const posZweig = block.indexOf('zeile = sess.get(')
  assert.ok(posPruefung !== -1 && posZweig !== -1 && posPruefung < posZweig,
    'sortierung muss VOR dem Anlegen/Ändern geprüft werden')
  assert.match(block, /Die Sortierung muss eine Zahl sein/)
})

test('BS-1a2 (F7): DEL (0x7f) gilt als Steuerzeichen', () => {
  const quelle = lies(API)
  assert.match(quelle, /ord\(c\) == 0x7F/)
})

test('BS-1a2 (F1): Overlay ist da, ohne BS-1a-Spalten; Wächter kennt EIGENE_SPALTEN', () => {
  const overlay = JSON.parse(lies(OVERLAY))
  assert.ok(Object.keys(overlay.docTypes || {}).length > 0, 'Overlay ohne docTypes')
  for (const [doctype, feld] of [
    ['Kalender', 'website_freigabe'],
    ['Kalender', 'website_slug'],
    ['Gruppe', 'website_freigabe'],
    ['Beitrag', 'auf_website'],
  ]) {
    const felder = (overlay.docTypes[doctype] || []).map((f) => f.fieldname)
    assert.ok(!felder.includes(feld), `${doctype}.${feld} darf nicht im Overlay stehen`)
  }
  const waechter = lies(QUELLEN)
  for (const eintrag of [
    'Kalender.website_freigabe',
    'Kalender.website_slug',
    'Kalender.website_nur_oeffentliche_kategorien',
    'Gruppe.website_freigabe',
    'Gruppe.website_slug',
    'Beitrag.auf_website',
  ]) {
    assert.ok(waechter.includes(`"${eintrag}"`), `EIGENE_SPALTEN nennt ${eintrag} nicht`)
  }
})

test('BS-1a2 (F6): Migration ist auf SQLite fahrbar (kein "public" dort)', () => {
  const migration = lies(MIGRATION)
  assert.match(migration, /bind\.dialect\.name != "sqlite"/,
    'die Bestandsprüfungen fragen SQLite nach dem Schema public')
})
