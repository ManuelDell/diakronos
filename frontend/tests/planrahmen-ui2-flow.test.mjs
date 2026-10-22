import assert from 'node:assert/strict'
import { fehlenderBedarf, stammdatenRoute } from '../src/diakonos/components/planrahmen/einrichten-flow.mjs'
assert.deepEqual(fehlenderBedarf([{einstufung:'ok'},{einstufung:'eingeschraenkt',meldung:'Fehlt'},{einstufung:'blockiert_automatik'}]).length,2)
assert.equal(stammdatenRoute('chor plan'), '#/planrahmen/stammdaten/chor%20plan')
assert.equal(stammdatenRoute('freizeit','plan/1'), '#/planrahmen/vorbereiten/plan%2F1')
console.log('UI2 Bedarf- und Stammdatenrouting: bestanden')
