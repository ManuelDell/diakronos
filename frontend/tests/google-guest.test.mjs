import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

test('real guest guard redirects a direct import URL before loading its component', () => {
  const source = fs.readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export \{.*\}$/gm, '')
    .replace(/export (function|const|let|var) /g, '$1 ')
  const context = { ref: value => ({ value }), shallowRef: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
    window: { __DIakonosBOOT: { mitglied: { status: 'Gast' }, is_admin: false }, location: { hash: '#/kalender/import' }, addEventListener: () => {} } }
  vm.createContext(context)
  vm.runInContext(source, context)
  assert.equal(context.window.location.hash, '#/')
})
