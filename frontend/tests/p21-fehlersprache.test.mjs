import test from 'node:test'
import assert from 'node:assert/strict'
import { rueckmeldeText } from '../src/diakonos/composables/useToast.js'
import { FEHLERTEXTE, katalogText } from '../src/shared/fehlertexte.js'

test('Unbekannte Fehler nennen einen nächsten Schritt statt nur Fehler',()=>{
  // UX2g: der Toast fragt den Fehlerkatalog statt eines eigenen Ersatzsatzes.
  // Eine leere Meldung oder eine der alten Floskeln ergibt den neutralen
  // Katalogtext („was ist passiert · was jetzt hilft").
  for (const wert of ['',null,'Fehler','Unbekannter Fehler','API-Fehler']) {
    assert.equal(rueckmeldeText(wert,'error'), katalogText('unbekannt'))
  }
  // Ein Satz des Servers bleibt stehen.
  assert.equal(rueckmeldeText('Das Ende muss nach dem Beginn liegen.','error'),'Das Ende muss nach dem Beginn liegen.')
  assert.equal(rueckmeldeText('Gespeichert','success'),'Gespeichert')
  // Eine Floskel mit technischem Anhang ist ebenfalls keine Auskunft.
  assert.equal(rueckmeldeText('Fehler beim Speichern','error'), katalogText('unbekannt'))
  // Der Text nennt immer einen nächsten Schritt, nie nur „Fehler".
  assert.match(rueckmeldeText('','error'), /versuche|lade|melde/i)
  assert.ok(FEHLERTEXTE.unbekannt.jetzt.length > 10)
})
