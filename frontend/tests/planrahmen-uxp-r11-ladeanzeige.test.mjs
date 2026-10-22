/**
 * UXP-R11 — „Vorschlag erzeugen“ ohne Ladeanzeige, „Übernehmen“ unerreichbar.
 *
 * Befund (Nachtpruefung 16.10.): „Vorschlag erzeugen“ dauerte bei einem
 * Chorplan mit 56 Terminen 21–28 s, der Knopf wurde nur grau (kein Hinweis,
 * dass gerechnet wird), und „Übernehmen“ im Ergebnisdialog lag bei 390 px
 * Breite rund 2500 px unter dem Inhalt — sichtbar erst nach langem Scrollen.
 *
 * Dieser Test prueft die QUELLE (die Bedienung selbst wird in einem echten
 * Teststack im Browser abgenommen): die drei Massnahmen muessen vorhanden und
 * nicht wieder herausnehmbar sein, ohne dass der Test rot wird.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const plan = readFileSync(new URL('../src/diakonos/pages/planrahmen/Plan.vue', import.meta.url), 'utf8')
const modal = readFileSync(new URL('../src/diakonos/components/DkModal.vue', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/diakonos/index.css', import.meta.url), 'utf8')

// 1) Ladeanzeige: eigener Zustand + Spinner + sprechender Text am Knopf.
assert.match(plan, /generatorLaeuft\s*=\s*ref\(false\)/, 'Plan.vue: generatorLaeuft-Zustand fehlt')
assert.match(plan, /'Wird berechnet …'/, 'Plan.vue: Knopftext „Wird berechnet …“ fehlt')
assert.match(plan, /dk-spinner/, 'Plan.vue: Spinner am Erzeugen-Knopf fehlt')
// Der Zustand muss waehrend der Berechnung gesetzt und danach zurueckgesetzt
// werden — sonst bleibt der Knopf haengen bzw. zeigt nie etwas an.
const oeffnen = plan.slice(plan.indexOf('async function generatorOeffnen'))
assert.match(oeffnen, /generatorLaeuft\.value\s*=\s*true/, 'generatorOeffnen setzt generatorLaeuft nicht')
assert.match(oeffnen.slice(0, oeffnen.indexOf('async function generatorAnwenden')),
  /generatorLaeuft\.value\s*=\s*false/, 'generatorOeffnen setzt generatorLaeuft nicht zurueck')

// 2) Fusszeile festhalten: Prop an DkModal + sticky-Klasse + CSS.
assert.match(plan, /footer-sticky/, 'Plan.vue: footer-sticky fehlt am Generator-Dialog')
assert.match(modal, /footerSticky/, 'DkModal.vue: footerSticky-Prop fehlt')
assert.match(modal, /dk-modal-actions--sticky/, 'DkModal.vue: sticky-Klasse wird nicht gesetzt')
assert.match(css, /\.dk-modal-actions--sticky\s*\{[^}]*position:\s*sticky/s,
  'index.css: .dk-modal-actions--sticky fehlt oder ist nicht sticky')

// 3) Der Spinner war referenziert, aber nie definiert — jetzt muss er es sein.
assert.match(css, /\.dk-spinner\s*\{/, 'index.css: .dk-spinner ist nicht definiert')
assert.match(css, /@keyframes\s+dk-spin/, 'index.css: dk-spin-Animation fehlt')

// 4) P0-2b (K3): auch „Veröffentlichen“ und „Neu laden“ zeigen eine Ladeanzeige,
// und der Veröffentlichungs-Dialog hat eine feste Fusszeile.
assert.match(plan, /veroeffentlichLaeuft\s*=\s*ref\(false\)/,
  'Plan.vue: veroeffentlichLaeuft-Zustand fehlt')
assert.match(plan, /'Wird geladen …'/, 'Plan.vue: Knopftext „Wird geladen …“ für Neu laden fehlt')
const veroeffOeffnen = plan.slice(plan.indexOf('async function veroeffentlichungOeffnen'))
assert.match(veroeffOeffnen, /veroeffentlichLaeuft\.value\s*=\s*true/,
  'veroeffentlichungOeffnen setzt veroeffentlichLaeuft nicht')
assert.match(veroeffOeffnen.slice(0, veroeffOeffnen.indexOf('async function veroeffentlichenDurchfuehren')),
  /veroeffentlichLaeuft\.value\s*=\s*false/, 'veroeffentlichungOeffnen setzt veroeffentlichLaeuft nicht zurueck')
// Der Veröffentlichungs-Dialog traegt selbst footer-sticky (der Generator-Dialog
// hatte es schon — jetzt beide).
const veroeffModal = plan.slice(plan.indexOf('v-model="veroeffentlichOffen"'))
assert.match(veroeffModal.slice(0, veroeffModal.indexOf('>')), /footer-sticky/,
  'Plan.vue: footer-sticky fehlt am Veröffentlichungs-Dialog')

console.log('UXP-R11: Ladeanzeige und feste Fusszeile sind verdrahtet')
