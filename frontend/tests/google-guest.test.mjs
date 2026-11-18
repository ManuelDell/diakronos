import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

test('real guest guard redirects a direct import URL before loading its component', () => {
  const source = fs.readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '')
    // ON-3b: die Leitungsregel (einrichtungLeitung.mjs) wird durch feste
    // Rückgaben ersetzt — dieser Lauf prueft den Router selbst.
    .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    // CHAT-R2a-2: `router.js` bindet `modulChatErlaubt` aus `modulRechte.mjs` (EINE
    // Fassung der Regel, DOM-frei) und gibt sie weiter. Die VM streicht Importe und
    // Exporte — hier tritt dieselbe Funktion als Attrappe ein.
    .replace(/^export \{ modulChatErlaubt \}$/gm,
      "const modulChatErlaubt = (boot = {}) => { if (boot.is_admin === true) return true; if (!Array.isArray(boot.module_sichtbar)) return false; return boot.module_sichtbar.includes('chat') }")
    .replace(/^export \{.*\}$/gm, '')
    .replace(/export (function|const|let|var) /g, '$1 ')
  const context = { ref: value => ({ value }), shallowRef: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
    window: { __DIakonosBOOT: { mitglied: { status: 'Gast' }, is_admin: false }, location: { hash: '#/kalender/import' }, addEventListener: () => {} } }
  vm.createContext(context)
  vm.runInContext(source, context)
  assert.equal(context.window.location.hash, '#/')
})
