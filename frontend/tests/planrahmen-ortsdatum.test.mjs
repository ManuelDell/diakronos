import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

test('Probelauf beginnt um 00:30 Europe/Berlin am örtlichen Tag', () => {
  const source = readFileSync(new URL('../src/diakonos/components/planrahmen/Probelauf.vue', import.meta.url), 'utf8')
  const expression = source.match(/const ab = ref\((.*)\)/)[1]
  const previous = process.env.TZ
  process.env.TZ = 'Europe/Berlin'
  try {
    const instant = Date.parse('2026-10-09T00:30:00+02:00')
    class Clock extends Date { constructor(...args) { super(...(args.length ? args : [instant])) } }
    assert.equal(vm.runInNewContext(expression, { Date: Clock, String }), '2026-10-09')
  } finally {
    if (previous === undefined) delete process.env.TZ
    else process.env.TZ = previous
  }
})
