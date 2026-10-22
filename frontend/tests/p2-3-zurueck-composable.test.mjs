/**
 * P2-3 · OP-HANDY-7 — Regression: „Zurück“ schließt ein Fenster wirklich.
 *
 * Die frühere Fassung band den Fensterstapel (fensterstapel.mjs) an
 * `history.pushState`/`popstate` — dort lag aber der Fehler: der Wächter in
 * `schliessenRegistriert` prüfte `schliessFunktionen.has(schliessen)` statt
 * `.has(schliessenRegistriert)`. Die Menge enthält die registrierte Funktion,
 * nie `schliessen` — der Wächter kehrte deshalb IMMER früh zurück und
 * `popstate` schloss kein Fenster (nur im Browser sichtbar; der reine
 * Stapel-Test blieb grün). Dieser Test fährt die echte Composable mit einer
 * gefälschten `window`/`history`-Umgebung und einem `popstate`.
 *
 * ``vue`` und ``vue/server-renderer`` sind im Docker-Build vorhanden.
 */
import assert from 'node:assert/strict'
import test from 'node:test'

// ── Minimaler Browser-Ersatz ────────────────────────────────────────────────
const listener = new Map() // Ereignis -> Menge von Rückrufen
const historyEintraege = [{ state: null }]

globalThis.window = {
  addEventListener(art, fn) {
    if (!listener.has(art)) listener.set(art, new Set())
    listener.get(art).add(fn)
  },
  removeEventListener(art, fn) {
    listener.get(art)?.delete(fn)
  },
  history: {
    pushState(state) { historyEintraege.push({ state }) },
    back() {
      // Wie der Browser: Eintrag abwerfen, dann popstate melden.
      if (historyEintraege.length > 1) historyEintraege.pop()
      const neu = historyEintraege[historyEintraege.length - 1].state
      for (const fn of listener.get('popstate') || []) fn({ state: neu })
    },
    get length() { return historyEintraege.length },
  },
}

function popstateAusloesen() {
  const neu = historyEintraege[historyEintraege.length - 1].state
  for (const fn of listener.get('popstate') || []) fn({ state: neu })
}

const { useZurueckSchliesst } = await import(
  '../src/diakonos/composables/useZurueckSchliesst.js')
const { ref, nextTick } = await import('vue')

// P2-3b: Der Eintrag wird nicht mehr sofort, sondern einen Makrotask später
// verbraucht (damit eine Navigation per Link Zeit hat, die Adresse zu setzen).
const makrotask = () => new Promise(r => setTimeout(r, 0))

test('OP-HANDY-7 · popstate schließt ein offenes Fenster wirklich', async () => {
  const offen = ref(false)
  let geschlossen = 0
  useZurueckSchliesst(offen, () => { geschlossen += 1; offen.value = false })

  offen.value = true
  await nextTick()
  assert.equal(historyEintraege.length, 2, 'Öffnen legt einen History-Eintrag an')
  assert.equal(historyEintraege.at(-1).state?.dkFenster, 1)

  popstateAusloesen()
  await nextTick()
  assert.equal(geschlossen, 1, 'popstate muss das Fenster schließen')
  assert.equal(offen.value, false, 'Zustand nach popstate geschlossen')
})

test('OP-HANDY-7 · ohne offenes Fenster greift popstate nicht ein', async () => {
  const offen = ref(false)
  let geschlossen = 0
  useZurueckSchliesst(offen, () => { geschlossen += 1 })
  popstateAusloesen()
  await nextTick()
  assert.equal(geschlossen, 0, 'kein Fenster offen → kein Eingriff')
})

test('OP-HANDY-7 · Schließen über die Oberfläche verbraucht den Eintrag', async () => {
  const offen = ref(false)
  useZurueckSchliesst(offen, () => { offen.value = false })
  const vorher = historyEintraege.length
  offen.value = true
  await nextTick()
  assert.equal(historyEintraege.length, vorher + 1)
  offen.value = false
  await nextTick()
  await makrotask()
  assert.equal(historyEintraege.length, vorher,
    'eigener History-Eintrag wird beim Schließen verbraucht')
})

console.log('OP-HANDY-7 Composable: popstate-Schließen, Leerlauf und Eintrag-Verbrauch bestanden')
