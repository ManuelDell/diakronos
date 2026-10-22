import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Echte Panel-Handler aus der SFC, nur Vue/Netzwerk werden ersetzt.
const quelle = await readFile(new URL('../src/diakonos/components/AppTopbar.vue', import.meta.url), 'utf8')
const handler = quelle.slice(quelle.indexOf('const listeOffen ='), quelle.indexOf('function kurz('))
// REST-1: derselbe Helfer wie in AppTopbar.vue (Dependency des Ausschnitts).
const { darfAlsGelesenMarkieren } = await import('../src/diakonos/composables/glocke.mjs')
const offen = () => {
  const anfragen = []
  const gelesen = []
  let beimAbbau
  const panel = new Function('ref', 'nextTick', 'onMounted', 'onUnmounted', 'document',
    'ladeListe', 'markAsRead', 'unreadCount', 'fehler', 'darfAlsGelesenMarkieren', handler + `
    return { toggleListe, schliesseBeiKlick, beiFlucht, listeOffen }
  `)(v => ({ value: v }), async () => {}, () => {}, fn => { beimAbbau = fn },
    { removeEventListener() {} },
    () => new Promise(resolve => anfragen.push(resolve)),
    async () => gelesen.push(true), { value: 1 }, { value: '' }, darfAlsGelesenMarkieren)
  return { panel, anfragen, gelesen, abbau: () => beimAbbau() }
}

for (const schliessen of ['Glocke', 'Escape', 'Außenklick', 'Schließen', 'Abbau']) {
  test(`Geschlossen per ${schliessen}: späte Antwort bleibt ungelesen`, async () => {
    const { panel, anfragen, gelesen, abbau } = offen()
    const laden = panel.toggleListe()
    if (schliessen === 'Glocke') await panel.toggleListe()
    else if (schliessen === 'Escape') panel.beiFlucht({ key: 'Escape' })
    else if (schliessen === 'Außenklick') panel.schliesseBeiKlick({ target: {} })
    else if (schliessen === 'Abbau') abbau()
    else panel.listeOffen.value = false
    anfragen[0]([{ name: 'N-1', read: 0 }])
    await laden
    assert.equal(gelesen.length, 0)
  })
}

test('Überholte Öffnung markiert nicht, aktuelle erfolgreiche Öffnung genau einmal', async () => {
  const { panel, anfragen, gelesen } = offen()
  const alt = panel.toggleListe()
  await panel.toggleListe()
  const aktuell = panel.toggleListe()
  anfragen[0]([{ name: 'ALT', read: 0 }])
  await alt
  assert.equal(gelesen.length, 0)
  anfragen[1]([{ name: 'NEU', read: 0 }])
  await aktuell
  assert.equal(gelesen.length, 1)
})

test('Fehlgeschlagenes Laden markiert keine alte Liste', async () => {
  const { panel, anfragen, gelesen } = offen()
  const laden = panel.toggleListe()
  anfragen[0](null)
  await laden
  assert.equal(gelesen.length, 0)
})

test('Composable verwirft überholte Antworten und liefert bei Fehler keine alte Liste', async () => {
  let code = await readFile(new URL('../src/diakonos/composables/useNotifications.js', import.meta.url), 'utf8')
  const offen = []
  globalThis.__raceGet = () => new Promise((resolve, reject) => offen.push({ resolve, reject }))
  code = code.replace("import { ref, onMounted, onUnmounted } from 'vue'",
    'const ref = v => ({value:v}); const onMounted = () => {}; const onUnmounted = () => {}')
  code = code.replace("import { apiGet, apiCall } from './useApi.js'",
    'const apiGet = globalThis.__raceGet; const apiCall = async () => {}')
  const { useNotifications } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
  const n = useNotifications()
  const alt = n.ladeListe()
  const neu = n.ladeListe()
  offen[1].resolve({ data: [{ name: 'NEU' }] })
  assert.deepEqual(await neu, [{ name: 'NEU' }])
  offen[0].resolve({ data: [{ name: 'ALT' }] })
  assert.equal(await alt, null)
  assert.deepEqual(n.notifications.value, [{ name: 'NEU' }])
  const fehler = n.ladeListe()
  const original = console.error
  try {
    console.error = () => {}
    offen[2].reject(new Error('Netzwerkfehler'))
    assert.equal(await fehler, null)
  } finally { console.error = original }
  assert.ok(n.fehler.value)
  assert.equal(n.laden.value, false)
})
