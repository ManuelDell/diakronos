/**
 * P1-12 / UXP-R7 + OP-EVENT-5 — Druck der Plaene.
 *
 * Befund der Nachtpruefung (16.10.): Die Druckausgabe enthielt Seitenleiste,
 * Kopfzeile und Knoepfe; der Plan stand in einer 256 px breiten Spalte links,
 * und alles nach der ersten Seite fehlte („Programm: 1 Seite, 0 Treffer
 * Stille Nacht“). Der Chorplan hatte gar keinen „Drucken“-Knopf, weil seine
 * Vorlage keine Ansicht mit `druck` deklariert.
 *
 * Gemessen (R-UXP, `t78_printfix.py`): ein blosses `.dk-app{display:block}`
 * genuegt NICHT — ohne `height:auto`/`overflow:visible` bricht die Ausgabe
 * ab Lied 6 ab. Ursache sind drei Regeln in `index.css`:
 *   :15  html,body,#app { height:100%; overflow:hidden }
 *   :21  .dk-app { display:grid; grid-template-columns:256px 1fr; height:100vh }
 *   :41  .dk-main-wrap { overflow:hidden }   (und .dk-content scrollt intern)
 *
 * Dieser Test prueft die QUELLE (die Druckabnahme selbst laeuft im
 * isolierten Teststack im echten Browser, mit PDF-Emulation): die Regeln
 * muessen vorhanden und nicht ohne roten Test wieder herausnehmbar sein.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const ansicht = readFileSync(new URL('../src/diakonos/components/planrahmen/PrAnsicht.vue', import.meta.url), 'utf8')
const plan = readFileSync(new URL('../src/diakonos/pages/planrahmen/Plan.vue', import.meta.url), 'utf8')
const chorplan = readFileSync(new URL('../../backend/src/diakronos_app/planrahmen/doku/kochbuch/chorplan.json', import.meta.url), 'utf8')

// 1) Die drei gemessenen Ursachen werden im Druckzustand aufgehoben.
assert.match(ansicht, /html,\s*body,\s*#app\s*\{\s*height:\s*auto\s*!important;\s*overflow:\s*visible\s*!important/,
  'PrAnsicht.vue: Hoehen-/Overflow-Sperre von html,body,#app wird im Druck nicht geloest')
assert.match(ansicht, /body\.pr-druck-aktiv\s+\.dk-app\s*\{[^}]*display:\s*block\s*!important[^}]*height:\s*auto\s*!important/s,
  'PrAnsicht.vue: .dk-app wird im Druck nicht vom Raster auf Block gestellt')
assert.match(ansicht, /body\.pr-druck-aktiv\s+\.dk-main-wrap[^{]*\{[^}]*(height:\s*auto\s*!important|overflow:\s*visible\s*!important)/s,
  'PrAnsicht.vue: .dk-main-wrap/.dk-content bleiben im Druck beschnitten')

// 2) Die Nicht-Plan-Bereiche verschwinden mitgedruckt nicht (UXP-R7: sonst
//    stehen Erststart-Wegweiser und Regelpruefung im PDF).
for (const rest of ['.dk-sidebar', '.dk-topbar', '.pr-erststart', '.pr-plan-meldungen',
  '.pr-legende', '.pr-ansicht-druckleiste', '.diakonos-toast-container']) {
  assert.ok(ansicht.includes(rest), `PrAnsicht.vue: ${rest} fehlt in der Druck-Ausblendliste`)
}

// 3) Der Chorplan ist druckbar: Ansicht `druck` samt Papierformat, damit der
//    Aushang A4-quer gesetzt wird (Befund: „Chorplan ohne Drucken-Knopf“).
const definition = JSON.parse(chorplan)
const ansichten = Array.isArray(definition.ansichten) ? definition.ansichten : []
const druck = ansichten.find(a => a.art === 'druck')
assert.ok(druck, 'chorplan.json: es fehlt eine Ansicht mit art "druck" (Chorplan-Aushang)')
assert.match(String(druck.druck || ''), /A4-quer/,
  'chorplan.json: die Druckansicht des Chorplans muss A4-quer deklarieren')
for (const spalte of ['anlass', 'lieder', 'einueben', 'einsingen']) {
  assert.ok((druck.spalten || []).includes(spalte),
    `chorplan.json: Druckansicht ohne Spalte ${spalte} — der Aushang waere unvollstaendig`)
}

// 4) Jede Planansicht bekommt den Drucken-Knopf (nicht nur die Druckansicht),
//    und Plan.vue reicht ihn durch.
assert.match(ansicht, /class="pr-druck-leiste"/, 'PrAnsicht.vue: Druckleiste fuer alle Ansichten fehlt')
assert.match(ansicht, /data-test="pr-drucken"/, 'PrAnsicht.vue: Drucken-Knopf fehlt')
assert.match(ansicht, /function drucken\(\)\s*\{\s*window\.print\(\)\s*\}/,
  'PrAnsicht.vue: drucken() ruft window.print() nicht auf')
assert.match(plan, /<PrAnsicht[\s\S]*?druck-knopf[\s\S]*?\/>/,
  'Plan.vue: der Drucken-Knopf wird nicht an PrAnsicht durchgereicht')

// 5) Strg+P (ohne Knopf) muss genauso sauber drucken: beforeprint/afterprint
//    schalten die Druckregeln scharf und raeumen danach wieder auf.
assert.match(ansicht, /beforeprint'?,\s*druckVorbereiten|beforeprint", druckVorbereiten/,
  'PrAnsicht.vue: kein beforeprint-Handler fuer den normalen Druck')
assert.match(ansicht, /afterprint'?,\s*druckAufraeumen|afterprint", druckAufraeumen/,
  'PrAnsicht.vue: kein afterprint-Handler — die Druckklasse bliebe haengen')

console.log('P1-12 Druck: Regeln, Chorplan-Druckansicht und Drucken-Knopf sind verdrahtet')
