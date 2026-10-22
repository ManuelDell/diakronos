import { test } from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/diakonos/composables/useAnmeldeEinstellungen.js', import.meta.url), 'utf8')
function start(apiCall) {
  const ctx = vm.createContext({ ref: value => ({ value }), computed: f => ({ get value() { return f() } }), apiCall })
  vm.runInContext(source.replace(/^import .*$/gm, '').replace('export function', 'function') + '\nglobalThis.s = useAnmeldeEinstellungen()', ctx)
  return ctx.s
}
const antwort = aktiv => ({ oidc_aktiv: aktiv, rollen: ['Mitglied', 'Kalenderadministrator'], rollen_zuordnung: [] })

test('OP-ADMIN-13: ausgeschaltetes Authentik verhindert Schreiben', async () => {
  const calls = []
  const s = start(async (m, d) => { calls.push(m); return antwort(false) })
  await s.laden()
  assert.equal(s.oidcAktiv.value, false)
  assert.equal(s.bedienbar.value, false)
  assert.equal(await s.speichern(), false)
  assert.equal(calls.length, 1)
})

test('Ladefehler bleibt gesperrt, erneutes Laden funktioniert', async () => {
  let kaputt = true
  const s = start(async () => { if (kaputt) throw Error('Keine Verbindung'); return antwort(true) })
  await s.laden()
  assert.equal(s.geladen.value, false)
  assert.equal(s.bedienbar.value, false)
  assert.match(s.fehler.value, /Verbindung/)
  kaputt = false
  await s.laden()
  assert.equal(s.bedienbar.value, true)
})

test('UXM-R18: unvollständige, doppelte und unbekannte Rollen blockieren ohne Datenverlust', async () => {
  const calls = []
  const s = start(async (m, d) => { calls.push(m); return antwort(true) })
  await s.laden()
  for (const zeilen of [[{ gruppe: 'chor', rolle: '' }], [{ gruppe: 'chor', rolle: 'Unbekannt' }],
    [{ gruppe: 'chor', rolle: 'Mitglied' }, { gruppe: 'chor', rolle: 'Mitglied' }]]) {
    s.zuordnungen.value = zeilen
    assert.equal(await s.speichern(), false)
    assert.ok(Object.keys(s.zeilenFehler.value).length)
    assert.deepEqual(s.zuordnungen.value, zeilen)
  }
  assert.equal(calls.length, 1)
})

test('N8: exakt ein atomarer Speicheraufruf und Fehler erhält Eingaben', async () => {
  const calls = []
  let kaputt = true
  const s = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('anmeldung_get_einstellungen')) return antwort(true)
    if (kaputt) throw Error('Speichern fehlgeschlagen')
    return { gespeichert: true }
  })
  await s.laden()
  s.zuordnungen.value = [{ gruppe: ' chor ', rolle: 'Mitglied' }]
  assert.equal(await s.speichern(), false)
  assert.equal(s.zuordnungen.value[0].gruppe, ' chor ')
  kaputt = false
  assert.equal(await s.speichern(), true)
  assert.equal(calls.length, 3)
  assert.equal(calls[2][0], 'diakronos.anmeldung.anmeldung_speichern')
  assert.equal(calls[2][1].zuordnungen[0].gruppe, 'chor')
})

test('OP-ADMIN-3/UXM-R6: neue Oberfläche nutzt Design-System, Kontenprüfung und kein Pagination-Layout', () => {
  const vue = readFileSync(new URL('../src/diakonos/pages/einstellungen/Anmeldung.vue', import.meta.url), 'utf8')
  for (const baustein of ['DkCard', 'DkField', 'DkButton', 'DkDialog', 'get_wartende_konten', 'konto_freischalten']) assert.ok(vue.includes(baustein))
  assert.ok(!vue.includes('class="dk-page"'))
  assert.ok(vue.includes(':close-on-overlay="false"'))
  assert.ok(vue.includes('Authentik: nicht eingerichtet'))
  assert.ok(vue.includes('bleibt gesperrt'))
})
