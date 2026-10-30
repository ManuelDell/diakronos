/**
 * FIX-2 — „Plan drucken ohne Hinweise/Fehler“ (Befund DMB-a48b13606d12).
 *
 * Befund Manuel (24.10.): „Drucken nimmt Hinweise und Fehler mit in den
 * Druck.“ Der Knopf [data-test=pr-drucken] sitzt in PrAnsicht; die
 * Druckregeln werden von `druckCss()` als Text in ein eigenes <style>
 * geschrieben (beforeprint + deklarierte Druckansicht). Pruef-Meldungen
 * (PrMeldungen, kompakt je Termin) stehen aber IN den Plantabellen-Zellen und
 * der Warnblock, der Handy-Hinweis (PLAN-M1), das Archiv-Band und der
 * Erststart-Wegweiser stehen ueber der Ansicht — die Ausblendliste kannte
 * davon nur `.pr-plan-meldungen` und `.pr-erststart`.
 *
 * Dieser Test prueft die QUELLE: die Ausblendliste von PrAnsicht.vue muss
 * jeden dieser Knoten fassen, die Tabellen-/Ablauf-Koerper muessen druckbar
 * bleiben und der Druckkopf (Titel + Zeitraum) muss auf Papier erscheinen.
 * Die visuelle Abnahme (PDF/emulateMedia('print')) laeuft im Wegwerf-Stack.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')
const ansicht = lies('../src/diakonos/components/planrahmen/PrAnsicht.vue')
const plan = lies('../src/diakonos/pages/planrahmen/Plan.vue')
const meldungen = lies('../src/diakonos/components/planrahmen/PrMeldungen.vue')
const handy = lies('../src/diakonos/components/planrahmen/PrHandyHinweis.vue')
const tabelle = lies('../src/diakonos/components/planrahmen/PrTabelle.vue')

/** Inhalt der Ausblendliste DRUCK_AUSBLENDEN aus PrAnsicht.vue. */
function ausblendliste(quelle) {
  const treffer = quelle.match(/const DRUCK_AUSBLENDEN\s*=\s*\[([\s\S]*?)\]/)
  assert.ok(treffer, 'PrAnsicht.vue: DRUCK_AUSBLENDEN nicht gefunden')
  return treffer[1]
}
const liste = ausblendliste(ansicht)
const imDruckCss = [ansicht.match(/function druckCss[\s\S]*?\n\}/)?.[0] || '']

// 1) Alle Befund-Knoten stehen in der Ausblendliste.
const PFLICHT = [
  '.pr-meldungen',              // PrMeldungen (normal/kompakt) — Pruef-Meldungen
  '.pr-meldungen-uebersicht',   // Warnblock „Regelpruefung des aktuellen Plans“
  '.pr-meldungen-termin',       // kompakte Meldung in der Plantabelle je Termin
  '.pr-meldung',                // einzelne Meldung
  '.pr-hinweis-handy',          // PLAN-M1 Handy-Hinweisband
  '.pr-plan-archiv',            // Archiv-Hinweisband
  '.pr-plan-leiste',            // Ansichts-/Terminwahl (Bearbeitungsbedienung)
  '.pr-plan-meldungen',         // Meldungen der letzten Aktion
  '.dk-screen-actions',         // Bearbeitungsknoepfe der Kopfzeile
  '.dk-screen-header',          // Titel/Knopfleiste am Bildschirm
  '.dk-sidebar', '.dk-topbar', '.dk-bottom-nav',  // Navigation
  '.diakonos-toast-container',  // Hinweis-Toasts
]
for (const knoten of PFLICHT) {
  assert.ok(liste.includes(`'${knoten}'`),
    `PrAnsicht.vue: ${knoten} fehlt in der Druck-Ausblendliste (Befund DMB-a48b13606d12)`)
}

// 2) Die Klassen gibt es wirklich — sonst verpufft die Druckregel still.
for (const [datei, name, knoten] of [
  [meldungen, 'PrMeldungen.vue', 'pr-meldungen'],
  [meldungen, 'PrMeldungen.vue', 'pr-meldung'],
  [meldungen, 'PrMeldungen.vue', 'pr-meldungen-termin'],
  [meldungen, 'PrMeldungen.vue', 'pr-meldungen-uebersicht'],
  [handy, 'PrHandyHinweis.vue', 'pr-hinweis-handy'],
  [plan, 'Plan.vue', 'pr-plan-archiv'],
  [plan, 'Plan.vue', 'pr-plan-leiste'],
  [plan, 'Plan.vue', 'pr-plan-meldungen'],
]) {
  assert.ok(datei.includes(knoten), `${name}: Klasse ${knoten} existiert nicht mehr — Druckregel anpassen`)
}

// 3) PrMeldungen je Termin haengt in den Zellen der Plantabelle; die
//    Ausblendliste muss deshalb auch die INNEREN Knoten fassen (die
//    Kindkomponenten sind scoped, aber ihre Klassennamen bleiben gleich).
assert.match(tabelle, /<PrMeldungen\s+v-if="meldungenZeigen"/,
  'PrTabelle.vue: die Pruef-Meldungen je Termin fehlen — Befund nicht reproduzierbar')
for (const innen of ['.pr-meldung-meldung', '.pr-meldung-hinweis', '.pr-meldung-piktogramm',
  '.pr-meldungen-kopf', '.pr-meldungen-anzeigen']) {
  assert.ok(ansicht.includes(innen),
    `PrAnsicht.vue: innerer Meldungsknoten ${innen} wird im Druck nicht ausgeblendet`)
}
assert.match(ansicht, /body\.pr-druck-aktiv\s+\.pr-meldung\s*,/,
  'PrAnsicht.vue: keine Druckregel fuer .pr-meldung (Meldungstext bliebe im PDF)')

// 4) Der Plan selbst bleibt vollstaendig: Tabellenkoerper, Ablauf und Kopf
//    duerfen NICHT in der Ausblendliste stehen.
for (const planKnoten of ['.pr-tabelle', '.pr-raster', '.pr-ablauf', '.pr-kalender', '.pr-druck-kopf']) {
  assert.ok(!liste.includes(`'${planKnoten}'`),
    `PrAnsicht.vue: ${planKnoten} ist der Plan selbst und darf im Druck nicht entfallen`)
}
assert.match(ansicht, /\.pr-druck-kopf\s*\{\s*display:\s*none;?\s*\}/,
  'PrAnsicht.vue: Druckkopf muss am Bildschirm ausgeblendet sein')
assert.match(ansicht, /@media print\s*\{[\s\S]*?\.pr-druck-kopf\s*\{[\s\S]*?display:\s*block/,
  'PrAnsicht.vue: Druckkopf (Titel + Zeitraum) erscheint auf dem Papier nicht')

// 5) 📌 ist Bildschirmsprache der Legende (die im Druck entfaellt) und die
//    Zellen sind am Papier nicht klickbar.
assert.match(ansicht, /\.pr-tabelle-pin\s*\{\s*display:\s*none\s*!important\s*;?\s*\}/,
  'PrAnsicht.vue: die 📌-Markierung wandert in den Druck')
assert.match(ansicht, /\.pr-tabelle-karte-wert--klickbar[\s\S]{0,120}cursor:\s*auto\s*!important/,
  'PrAnsicht.vue: klickbare Zellen behalten im Druck den Zeiger')

// 6) Die Regel haengt an der Druckklasse, die beforeprint/afterprint setzen —
//    sonst wirkt sie am Bildschirm.
assert.match(ansicht, /document\.body\.classList\.add\('pr-druck-aktiv'\)/,
  'PrAnsicht.vue: Druckklasse wird nicht gesetzt')
assert.match(ansicht, /document\.body\.classList\.remove\('pr-druck-aktiv'\)/,
  'PrAnsicht.vue: Druckklasse wird nach dem Druck nicht entfernt')
assert.ok(!/^\s*\.pr-meldungen\s*\{\s*display:\s*none/m.test(ansicht),
  'PrAnsicht.vue: Meldungen duerfen am Bildschirm nicht global ausgeblendet werden')
// 4) Planinhalt bleibt: Badges (entfallen, Anlass) werden NICHT ausgeblendet.
assert.ok(!/['"]\.dk-badge['"]/.test(liste), 'DRUCK_AUSBLENDEN darf .dk-badge nicht enthalten (entfallen/Anlass sind Planinhalt)')
assert.ok(imDruckCss[0].includes('@media print'), 'PrAnsicht.vue: druckCss() enthaelt kein @media print')

console.log('FIX-2 Druck: Meldungen, Hinweise und Bedienung bleiben weg — der Plan wird gedruckt')
