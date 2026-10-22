import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const quelle = name => readFileSync(new URL(`../src/diakonos/${name}`, import.meta.url), 'utf8')

for (const name of ['pages/GruppeDetail.vue', 'pages/Ressourcen.vue', 'pages/MitgliedDetail.vue', 'pages/devmodus/Befunde.vue']) {
  test(`${name}: destruktive Rückfragen benutzen die gemeinsame Warteschlange`, () => {
    const text = quelle(name)
    assert.doesNotMatch(text, /(?:window\.)?\bconfirm\(/)
    assert.match(text, /await bestaetigen\(/)
    assert.match(text, /aktion: /)
    assert.doesNotMatch(text, /knopf: /)
    assert.match(text, /import \{ bestaetigen \}/)
  })
}
test('Profil: kein eigener JSON-/Sitzungsweg und keine nativen Fehlerfenster', () => {
  const text = quelle('pages/Profile.vue')
  assert.doesNotMatch(text, /\balert\(/)
  assert.match(text, /return apiCall\(/)
  assert.match(text, /await apiAntwortPruefen\(res\)/)
})
