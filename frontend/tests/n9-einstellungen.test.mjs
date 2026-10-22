import { test } from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/diakonos/composables/useGemeinde.js', import.meta.url), 'utf8')

function start(apiCall) {
  const ctx = vm.createContext({
    ref: value => ({ value }),
    computed: f => ({ get value() { return f() } }),
    apiCall,
  })
  vm.runInContext(
    source.replace(/^import .*$/gm, '')
      .replace('export function useGemeinde', 'function useGemeinde')
      .replace('export function useDatenschutzTexte', 'function useDatenschutzTexte')
      + '\nglobalThis.g = useGemeinde()\nglobalThis.t = useDatenschutzTexte()',
    ctx,
  )
  return ctx
}

const gemeindeAntwort = {
  gemeindename: 'Versöhnungskirche', kontakt_email: 'buero@example.org',
  oeffentliche_adresse: 'https://gemeinde.example.org', willkommenstext: 'Hallo',
  link_laufzeit_tage: 14, link_max_anmeldungen: 50,
  module: [{ schluessel: 'kronos', anzeige: 'Kronos', sichtbar: false }],
}
const texteAntwort = {
  einwilligung: 'Ich willige ein.', datenschutzerklaerung: 'Erklärung',
  aufbewahrung: 'Aufbewahrung', version: 3, veroeffentlicht: true,
}

test('N9 Gemeinde: Laden liefert Werte, Speichern ist EIN Aufruf', async () => {
  const calls = []
  const { g } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('gemeinde_get_einstellungen')) return gemeindeAntwort
    return { gespeichert: true }
  })
  await g.laden()
  assert.equal(g.geladen.value, true)
  assert.equal(g.linkLaufzeitTage.value, 14)
  assert.equal(g.module.value.length, 1)
  assert.equal(await g.speichern(), true)
  assert.equal(calls.length, 2)
  assert.equal(calls[1][0], 'diakronos.diakonos.api.gemeinde.gemeinde_speichern')
})

test('N9 Gemeinde: leere Karten lassen die Link-Vorgaben unberührt', async () => {
  const calls = []
  const { g } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('gemeinde_get_einstellungen')) return gemeindeAntwort
    return { gespeichert: true }
  })
  await g.laden()
  await g.speichern({ mitLinkVorgaben: false })
  const nutzlast = calls[1][1]
  assert.ok(!('link_laufzeit_tage' in nutzlast))
  assert.ok(!('link_max_anmeldungen' in nutzlast))
})

test('N9 Gemeinde: fehlender Name blockiert ohne Aufruf', async () => {
  const calls = []
  const { g } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('gemeinde_get_einstellungen')) return gemeindeAntwort
    return { gespeichert: true }
  })
  await g.laden()
  g.gemeindename.value = '   '
  assert.equal(await g.speichern(), false)
  assert.match(g.fehler.value, /Gemeindenamen/)
  assert.equal(calls.length, 1)  // nur das Laden
})

test('N9 Gemeinde: Ladefehler bleibt gesperrt, erneutes Laden geht', async () => {
  let kaputt = true
  const { g } = start(async () => {
    if (kaputt) throw Error('Keine Verbindung')
    return gemeindeAntwort
  })
  await g.laden()
  assert.equal(g.geladen.value, false)
  assert.equal(g.bedienbar.value, false)
  assert.match(g.fehler.value, /Verbindung/)
  kaputt = false
  await g.laden()
  assert.equal(g.bedienbar.value, true)
})

test('N9 Gemeinde: Modulschalter schreibt gezielt, Fehler erhält Zustand', async () => {
  const calls = []
  let kaputt = false
  const { g } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('gemeinde_get_einstellungen')) return gemeindeAntwort
    if (kaputt) throw Error('Speichern fehlgeschlagen')
    return { schluessel: d.schluessel, sichtbar: d.sichtbar }
  })
  await g.laden()
  await g.modulSchalten('kronos', true)
  assert.equal(calls.at(-1)[0], 'diakronos.diakonos.api.gemeinde.gemeinde_setze_modul')
  assert.equal(g.module.value[0].sichtbar, true)
  kaputt = true
  await g.modulSchalten('kronos', false)
  assert.match(g.fehler.value, /Speichern fehlgeschlagen/)
  assert.equal(g.module.value[0].sichtbar, true)  // Zustand bleibt bei Fehler
})

test('N9 Registrierung: nur die Link-Vorgaben werden geschrieben', async () => {
  const calls = []
  const { g } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('gemeinde_get_einstellungen')) return gemeindeAntwort
    return { link_laufzeit_tage: d.link_laufzeit_tage, link_max_anmeldungen: d.link_max_anmeldungen }
  })
  await g.laden()
  g.linkMaxAnmeldungen.value = 99
  assert.equal(await g.linkvorgabenSpeichern(), true)
  assert.equal(calls.at(-1)[0], 'diakronos.diakonos.api.gemeinde.gemeinde_setze_linkvorgaben')
  assert.equal(calls.at(-1)[1].link_max_anmeldungen, 99)
})

test('N9 Datenschutz: Profile fehlen blockiert, echte Änderung erhöht die Fassung', async () => {
  const calls = []
  let antwort = texteAntwort
  const { t } = start(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('datenschutz_get_texte')) return antwort
    antwort = { ...antwort, version: 4 }
    return { gespeichert: true, version: 4 }
  })
  await t.laden()
  assert.equal(t.version.value, 3)
  t.einwilligung.value = ''
  assert.equal(await t.speichern(), false)
  assert.match(t.fehler.value, /drei Texte/)
  t.einwilligung.value = 'Neu'
  assert.equal(await t.speichern(), true)
  assert.equal(t.version.value, 4)
  assert.match(t.erfolg.value, /Fassung 4/)
})

test('N9 Datenschutz: Speicherfehler erhält die Eingaben', async () => {
  let kaputt = true
  const { t } = start(async (m) => {
    if (m.endsWith('datenschutz_get_texte')) return texteAntwort
    if (kaputt) throw Error('Speichern fehlgeschlagen')
    return { gespeichert: true, version: 3 }
  })
  await t.laden()
  t.einwilligung.value = 'Anders'
  assert.equal(await t.speichern(), false)
  assert.equal(t.einwilligung.value, 'Anders')
  assert.match(t.fehler.value, /fehlgeschlagen/)
})
