import test from 'node:test'
import assert from 'node:assert/strict'
import { rueckmeldeText } from '../src/diakonos/composables/useToast.js'

test('Unbekannte Fehler nennen einen nächsten Schritt statt nur Fehler',()=>{
  for (const wert of ['',null,'Fehler','Unbekannter Fehler','API-Fehler']) {
    assert.equal(rueckmeldeText(wert,'error'),'Das hat nicht geklappt. Bitte versuche es später noch einmal.')
  }
  assert.equal(rueckmeldeText('Das Ende muss nach dem Beginn liegen.','error'),'Das Ende muss nach dem Beginn liegen.')
  assert.equal(rueckmeldeText('Gespeichert','success'),'Gespeichert')
})
