import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const quelle = name => readFileSync(new URL(`../src/diakonos/${name}`, import.meta.url), 'utf8')

/*
 * UX2c: „destruktive Rückfragen benutzen die gemeinsame Warteschlange“ galt
 * für VIER Seiten, die vor Rückfragen fragten. Drei davon sind inzwischen
 * umkehrbar (GruppeDetail: aus der Gruppe entfernen; Ressourcen: stornieren;
 * — und keiner dieser Wege braucht mehr eine Rückfrage). Sie melden die
 * Aktion stattdessen am Rückgängig-Stapel an (Prinzip I2, geprüft in
 * `ux2c-endgueltig.test.mjs`). Geblieben sind die Seiten mit WIRKLICH
 * endgültigen Aktionen: dort gilt weiter die gemeinsame Warteschlange —
 * jetzt über den EINEN Endgültig-Dialog `DkEndgueltig` (Frage + Folge).
 */
for (const name of ['pages/MitgliedDetail.vue']) {
  test(`${name}: destruktive Rückfragen benutzen die gemeinsame Warteschlange`, () => {
    const text = quelle(name)
    assert.doesNotMatch(text, /(?:window\.)?\bconfirm\(/)
    assert.match(text, /await bestaetigen\(/)
    assert.match(text, /aktion: /)
    assert.doesNotMatch(text, /knopf: /)
    assert.match(text, /import \{ bestaetigen \}/)
  })
}

for (const name of ['pages/devmodus/Befunde.vue']) {
  test(`${name}: endgültiges Löschen läuft über den EINEN Endgültig-Dialog`, () => {
    const text = quelle(name)
    assert.doesNotMatch(text, /(?:window\.)?\bconfirm\(/)
    // UX2c (C1): nicht mehr die Ein-Zeilen-Rückfrage, sondern Frage + Folge
    // im gemeinsamen Baustein (Warteschlange: DkDialog/useDialogFokus).
    assert.match(text, /import DkEndgueltig from '..\/..\/components\/ui\/DkEndgueltig\.vue'/)
    assert.match(text, /<DkEndgueltig/)
    assert.match(text, /aktion="Befund endgültig löschen"/)
  })
}
test('Profil: kein eigener JSON-/Sitzungsweg und keine nativen Fehlerfenster', () => {
  const text = quelle('pages/Profile.vue')
  assert.doesNotMatch(text, /\balert\(/)
  assert.match(text, /return apiCall\(/)
  assert.match(text, /await apiAntwortPruefen\(res\)/)
})
