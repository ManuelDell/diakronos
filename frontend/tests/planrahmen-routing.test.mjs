import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
const root = new URL('../src/diakonos/', import.meta.url)
const router = readFileSync(new URL('router.js', root), 'utf8')
for (const name of ['Uebersicht', 'Plan', 'MeineDienste', 'Einrichten', 'PlantypEditor', 'Stammdaten']) {
  assert.ok(router.includes(`./pages/planrahmen/${name}.vue`), `Neue Seite ${name} registriert`)
}
assert.ok(router.includes("'#/planrahmen'"))
assert.ok(router.includes("'#/planrahmen/meine-dienste'"))
assert.ok(router.includes("'#/planrahmen/einrichten'"))
// Seit N0 liegen die Weiterleitungen in EINER Tabelle (WEITERLEITUNGEN).
assert.ok(router.includes("'#/plaene':"), 'Alte Übersicht wird umgeleitet')
assert.match(router, /'#\/plaene':\s*'#\/planrahmen'/, 'Weiterleitung zeigt auf den neuen Bereich')
for (const file of ['pages/Plaene.vue', 'pages/PlanDetail.vue', 'pages/PlanWizard.vue', 'components/planung/TerminLeiste.vue']) {
  assert.ok(!existsSync(new URL(file, root)), `Alte Datei entfernt: ${file}`)
}
// Seit N0 (S12) stammen Seitenleiste und „Mehr“-Blatt aus EINER Definition.
const menue = readFileSync(new URL('menue.js', root), 'utf8')
assert.ok(menue.includes("'#/planrahmen'"))
assert.ok(menue.includes("'#/planrahmen/meine-dienste'"))
assert.ok(!menue.includes('#/plaene'), 'kein alter Pläne-Eintrag mehr im Menü')
for (const file of ['components/AppSidebar.vue', 'components/AppBottomNav.vue']) {
  const nav = readFileSync(new URL(file, root), 'utf8')
  assert.ok(nav.includes('menue.js'), `${file} nutzt die zentrale Menüdefinition`)
  assert.ok(!nav.includes('#/plaene'))
}
console.log('Planrahmen-Routen und Navigation: bestanden')
