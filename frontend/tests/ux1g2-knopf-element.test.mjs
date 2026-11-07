/**
 * UX1g2 — Knopf-Waechter JE ELEMENT (Schlupfloch aus UX1g).
 *
 * BEFUND aus dem Review zu UX1g: `fundstellenOhneBausteine()` in
 * `tools/ux1g-knopf-bestand.mjs` wandte die Bausteinregel (`dk-ui-chip`,
 * `dk-ui-aktionen-ausloeser/-eintrag`) auf die GANZE Datei an. Steht irgendwo
 * in einer Datei ein Chip, fielen ALLE klassenlosen `<button>` derselben Datei
 * aus dem Bestand — `pages/planrahmen/Plan.vue` hatte so einen Reiter-Knopf
 * `class="dk-tab"`, der nie gezaehlt wurde.
 *
 * Geprueft wird, was diese Karte zusagt:
 *
 *   F1  Die Bausteinregel gilt JE ELEMENT: nur ein `<button>`, dessen EIGENES
 *       `class` eine Baustein-Klasse traegt, ist ausgenommen. Selbsttest mit
 *       synthetischer Datei (Chip + klassenloser Knopf → Fund).
 *
 *   F2  Der Bestand der Alt-Knoepfe (UX1g, F1) bleibt auf 0 — mit der
 *       strengeren Zaehlweise.
 *
 *   F3  Rohe `<button class="eigen">` mit Eigenklasse sind als BESTAND
 *       eingefroren (`tools/ux1g2-knopf-eigenklasse.txt`) und duerfen NUR
 *       SCHRUMPFEN: neue kommen nicht dazu, behobene muessen nachgezogen sein.
 *
 *   F4  Der Tag-Leser bricht nicht an `>` innerhalb von Attributwerten ab
 *       (Pfeilfunktion `:ref="el => …"`, Vergleich `:disabled="a > b"`) — sonst
 *       waere die Eigenklasse eines solchen Knopfes unsichtbar.
 *
 *   F5  Die Listen der Nachbarkarten (UX1e/UX1f) bleiben unberuehrt.
 *
 * Laeuft im Docker-Build (`node --test`, Muster in `tests/testliste.txt`); die
 * Datei liegt in `frontend/tests/` und liest nur `frontend/**`.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import {
  LISTE,
  bestand,
  bestandEigenklasse,
  dateienDesBereichs,
  fundstellenJeElement,
  istBaustein,
  klassenNamen,
  knopfElemente,
  liesBestandEigenklasse,
  roheMitEigenklasse,
  verstoesseEigenklasse,
  imFremdenBereich,
} from '../tools/ux1g2-knopf-bestand.mjs'
import { fundstellenOhneBausteine } from '../tools/ux1g-knopf-bestand.mjs'
import { FRONTEND } from '../tools/ux1e-knopf-bestand.mjs'

/** Quelle einer Datei (Pfad in Listen-Schreibweise, `frontend/…`). */
function lies(rel) {
  const abs = path.join(FRONTEND, rel.replace(/^frontend\//, ''))
  assert.ok(existsSync(abs), `Datei fehlt: ${rel}`)
  return readFileSync(abs, 'utf8')
}

// ── F1: die Regel gilt je Element ─────────────────────────────────────────

test('UX1g2/F1: Chip + klassenloser Knopf in EINER Datei → der Knopf ist ein Fund', () => {
  // Genau der Fall, den UX1g uebersah: die Datei enthaelt einen Chip, der
  // Knopf daneben hat aber keinerlei Klasse.
  const probe = [
    '<template>',
    '  <button class="dk-ui-chip" :class="{ aktiv }" @click="waehlen">Chip</button>',
    '  <button @click="los">Los</button>',
    '</template>',
  ].join('\n')
  assert.deepEqual(fundstellenJeElement(probe), ['<button>'],
    'der klassenlose Knopf neben einem Chip MUSS gezaehlt werden')
})

test('UX1g2/F1: die alte dateiweite Regel haette diesen Knopf verschluckt', () => {
  // Beleg des Befunds: die fruehere Fassung von `fundstellenOhneBausteine()`
  // prueft `quelle.includes('class="dk-ui-chip')` gegen die GANZE Datei und
  // stellt damit jeden klassenlosen <button> derselben Datei frei.
  const alteRegel = (text, bausteine) => {
    const quelle = text
    return ['<button>'].filter(() => !bausteine.some((k) => quelle.includes(`class="${k}`)))
  }
  const probe = '<button class="dk-ui-chip">C</button><button>roh</button>'
  assert.deepEqual(alteRegel(probe, ['dk-ui-chip']), [],
    'Vorbedingung: die alte Regel uebersieht den rohen Knopf — sonst prueft dieser Test nichts')
  // Die aktuelle Fassung meldet ihn.
  assert.deepEqual(fundstellenOhneBausteine(probe), ['<button>'])
})

test('UX1g2/F1: das Baustein-ELEMENT selbst bleibt ausgenommen', () => {
  const probe = '<template><button class="dk-ui-chip" @click="x">Chip</button></template>'
  assert.deepEqual(fundstellenJeElement(probe), [],
    'ein Element, dessen EIGENES class ein Baustein ist, ist die dokumentierte Ausnahme')
  const eintrag = '<template><button class="dk-ui-aktionen-eintrag" role="menuitem">A</button></template>'
  assert.deepEqual(fundstellenJeElement(eintrag), [])
})

test('UX1g2/F1: mehrere Knoepfe je Datei werden einzeln entschieden', () => {
  const probe = [
    '<template>',
    '  <button class="dk-ui-chip">Chip</button>',
    '  <button>ohne</button>',
    '  <button class="dk-ui-aktionen-ausloeser">⋯</button>',
    '  <button @click.stop.prevent="y">zwei</button>',
    '</template>',
  ].join('\n')
  assert.deepEqual(fundstellenJeElement(probe), ['<button>', '<button>'],
    'zwei Bausteine ausgenommen, zwei rohe Knoepfe gezaehlt')
})

test('UX1g2/F1: Alt-Klassen zaehlen unveraendert weiter', () => {
  const probe = '<template><button class="dk-ui-chip">C</button>'
    + '<button class="dk-btn dk-btn-sm">alt</button></template>'
  assert.deepEqual(fundstellenJeElement(probe), ['dk-btn', 'dk-btn-sm'],
    'die Bausteinregel darf die Alt-Reihe nicht mitfreistellen')
})

test('UX1g2/F1: istBaustein prueft nur das eigene class', () => {
  assert.ok(istBaustein('dk-ui-chip'))
  assert.ok(istBaustein('dk-ui-chip is-aktiv'))
  assert.ok(istBaustein("{ 'dk-ui-aktionen-eintrag': offen }"))
  assert.ok(!istBaustein('dk-ui-chip-liste'), 'nur exakte Baustein-Namen')
  assert.ok(!istBaustein(''))
  assert.ok(!istBaustein('dk-tab'))
})

// ── F2: der Bestand der Alt-Knoepfe bleibt 0 ──────────────────────────────

test('UX1g2/F2: im Rest der Anwendung steht kein Alt-Knopf (je Element gezaehlt)', () => {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}: ${zahl}`)
  assert.deepEqual(zeilen, [],
    'Alt-Knoepfe im Rest — bitte <DkButton> benutzen '
    + '(components/ui/DkButton.vue):\n  ' + zeilen.join('\n  '))
})

test('UX1g2/F2: die Zaehlung sieht alle Dateien des Bereichs', () => {
  // Nicht nur die, die der UX1e-Kern als „hat Fundstellen" liefert — sonst
  // kaeme ein `<button class="dk-tab">` nie in den Blick.
  const dateien = dateienDesBereichs()
  assert.ok(dateien.length > 100, `nur ${dateien.length} Dateien im Bereich — Zaehlung zu eng`)
  assert.ok(dateien.includes('frontend/src/diakonos/pages/planrahmen/Plan.vue'),
    'Plan.vue gehoert zum Bereich (dort sitzt der Reiter-Knopf)')
})

// ── F3: Eigenklasse-Knoepfe eingefroren, nur schrumpfen ───────────────────

test('UX1g2/F3: die eingefrorene Liste passt zum Stand (nur schrumpfen)', () => {
  assert.ok(existsSync(LISTE), 'tools/ux1g2-knopf-eigenklasse.txt fehlt')
  const fehler = verstoesseEigenklasse()
  assert.deepEqual(fehler, [],
    'Die Liste tools/ux1g2-knopf-eigenklasse.txt passt nicht zum Stand:\n  '
    + fehler.join('\n  ')
    + '\nBehoben? Dann nachziehen: node tools/ux1g2-knopf-bestand.mjs --schreiben')
})

test('UX1g2/F3: jeder Eintrag der Liste steht im Bereich und hat Eigenklasse', () => {
  const jetzt = bestandEigenklasse()
  const frueher = liesBestandEigenklasse()
  assert.ok(frueher.size > 0, 'die Liste ist leer — dann schuetzt sie nichts')
  for (const pfad of frueher.keys()) {
    assert.ok(jetzt.has(pfad),
      `${pfad}: in der Liste, aber ohne Fund — bitte nachziehen (--schreiben)`)
    assert.ok(roheMitEigenklasse(lies(pfad)).length > 0,
      `${pfad}: kein roher Knopf mit Eigenklasse mehr — bitte nachziehen`)
  }
})

test('UX1g2/F3: Bausteine stehen NICHT in der Eigenklasse-Liste', () => {
  for (const pfad of liesBestandEigenklasse().keys()) {
    for (const name of roheMitEigenklasse(lies(pfad))) {
      assert.ok(!istBaustein(name), `${pfad}: Baustein "${name}" ist eingefroren statt ausgenommen`)
    }
  }
})

test('UX1g2/F3: der Bestand zaehlt nur Knoepfe ohne Alt-Klasse', () => {
  assert.deepEqual(roheMitEigenklasse('<template><button class="dk-tab">A</button></template>'),
    ['dk-tab'])
  assert.deepEqual(roheMitEigenklasse('<template><button class="dk-btn dk-btn-sm">A</button></template>'),
    [], 'Alt-Knoepfe gehoeren in den UX1g-Bestand, nicht hierher')
  assert.deepEqual(roheMitEigenklasse('<template><button>A</button></template>'),
    ['<button>'], 'ganz ohne Klasse ist ebenfalls ein roher Knopf')
  assert.deepEqual(roheMitEigenklasse('<template><button class="dk-ui-chip">C</button></template>'),
    [], 'Bausteine sind ausgenommen')
})

// ── F4: der Tag-Leser bricht nicht an `>` im Attribut ab ──────────────────

test('UX1g2/F4: `>` in einem Attributwert zerlegt den Tag nicht', () => {
  const probe = [
    '<template>',
    '  <button',
    '    :ref="el => (els[i] = el)"',
    '    :disabled="anzahl > 3"',
    '    class="dk-eigen"',
    '  >Text</button>',
    '</template>',
  ].join('\n')
  const elemente = knopfElemente(probe)
  assert.equal(elemente.length, 1)
  assert.equal(elemente[0].klassen, 'dk-eigen',
    'das class-Attribut MUSS gelesen werden, auch wenn vorher `>` in Attributen steht')
  assert.deepEqual(roheMitEigenklasse(probe), ['dk-eigen'])
  // Und die Baustein-Erkennung greift ebenso.
  const baustein = '<template><button :ref="el => (a = el)" class="dk-ui-chip">C</button></template>'
  assert.deepEqual(knopfElemente(baustein)[0].klassen, 'dk-ui-chip')
})

test('UX1g2/F4: mehrzeilige Tags mit Bindung und Bedingung', () => {
  const probe = [
    '<template>',
    '  <button',
    '    v-if="offen"',
    '    type="button"',
    '    class="dk-ui-aktionen-ausloeser"',
    '    :class="{ \'is-offen\': offen }"',
    '    :aria-label="label"',
    '    @click.stop="umschalten"',
    '  >⋯</button>',
    '</template>',
  ].join('\n')
  assert.deepEqual(fundstellenJeElement(probe), [],
    'der Aktionsmenue-Ausloeser ist ein Baustein — auch wenn der Tag mehrzeilig ist')
})

test('UX1g2/F4: klassenNamen zerlegt gebundene Klassen', () => {
  assert.deepEqual(klassenNamen("dk-ui-chip is-aktiv"), ['dk-ui-chip', 'is-aktiv'])
  assert.deepEqual(klassenNamen("{ 'dk-ui-chips': x, aktiv }"), ['dk-ui-chips', 'x', 'aktiv'])
  assert.deepEqual(klassenNamen(''), [])
})

// ── F5: Nachbarlisten bleiben unberuehrt ──────────────────────────────────

test('UX1g2/F5: die Listen von UX1e und UX1f bleiben stehen', () => {
  for (const name of ['ux1e-knopf-bestand.txt', 'ux1f-knopf-bestand.txt']) {
    const p = path.join(FRONTEND, 'tools', name)
    assert.ok(existsSync(p), `${name} fehlt — die Nachbarkarten fuehren eigene Listen`)
  }
  // Diese Karte fuehrt ihre eigene Liste — kein Pfad aus einem fremden
  // Bereich (UX1e/UX1f) darf hineingeraten, dort zaehlt er schon.
  for (const pfad of bestandEigenklasse().keys()) {
    assert.ok(pfad.startsWith('frontend/src/'), `${pfad}: ausserhalb von frontend/src`)
    assert.ok(!imFremdenBereich(pfad),
      `${pfad}: gehoert zum Bereich von UX1e/UX1f — dort steht der Bestand`)
  }
})
