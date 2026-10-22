import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const editor = readFileSync(new URL('../src/diakonos/pages/planrahmen/PlantypEditor.vue', import.meta.url), 'utf8')
const probe = readFileSync(new URL('../src/diakonos/components/planrahmen/Probelauf.vue', import.meta.url), 'utf8')

test('Editor übergibt das erforderliche Definition-Prop an den Probelauf', () => {
  assert.match(probe, /definition: \{ type: Object, required: true \}/)
  assert.match(editor, /<Probelauf\s+:definition="definition"\s*\/>/)
})
