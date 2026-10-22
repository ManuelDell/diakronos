import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
const source = readFileSync(new URL('../src/diakonos/pages/planrahmen/PlantypEditor.vue', import.meta.url), 'utf8')
test('Grunddaten koppeln Eingabe und Prüfpfad, weitere Abschnitte erhalten Meldungen', () => {
  for (const key of ['id', 'name', 'bereich', 'beschreibung']) {
    assert.ok(source.includes(`:meldungen="pruefMeldungen" pfad="${key}"`), `${key} fehlt`)
  }
  for (const tag of ['PrDeklarationenEditor', 'PrRegelnEditor', 'PrAnsichtenEditor']) {
    for (const match of source.matchAll(new RegExp(`<${tag}[^>]+>`, 'g'))) assert.match(match[0], /:meldungen="pruefMeldungen"/)
  }
})
