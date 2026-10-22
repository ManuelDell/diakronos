/**
 * P2-3b · Regression — Nacharbeit aus dem Code-Review (R-P2-3-code B1/W1).
 *
 * B1: Ein Fenster, das über einen LINK IM FENSTER geschlossen wird (z. B. der
 *     Eintrag im „Mehr“-Blatt), darf NICHT per `history.back()` zurückspringen.
 *     Die Zielseite muss stehen bleiben; erst ein echtes „Zurück“ führt zur
 *     Ausgangsseite. Vorher lief `back()` an und riss die Zielseite mit — der
 *     Nutzer landete wieder auf der Ausgangsseite.
 *
 * W1: „Zurück“ schließt bei gestapelten Fenstern NUR das oberste. Das obere
 *     per ✕/Esc zu schließen lässt das untere offen; das eigene Aufräum-`back()`
 *     darf nicht als Nutzer-„Zurück“ gelten und ein zweites Fenster schließen.
 *
 * Der Test fährt die echte Composable mit einem Browser-Ersatz, der AUCH die
 * Adresse (`location.hash`) kennt — ohne diesen Teil war der Fehler unsichtbar
 * (der alte Test fälschte `history` ohne Fragment-Sprung).
 *
 * ``vue`` ist im Docker-Build vorhanden.
 */
import assert from 'node:assert/strict'
import test from 'node:test'

// ── Browser-Ersatz mit echter Vor/Zurück-Folge ──────────────────────────────
const listener = new Map()
let eintraege = [{ state: null, hash: '#/anfang' }]
let position = 0

function melden(art, payload) {
  for (const fn of listener.get(art) || []) fn(payload)
}

/** Minimales Klick-Ereignis (P3-4c): `target` muss ein Link sein. */
class Ereignis {
  constructor(art) {
    this.type = art
    this.target = null
    this.defaultPrevented = false
    this.button = 0
    this.metaKey = false
    this.ctrlKey = false
    this.shiftKey = false
    this.altKey = false
    this._gestoppt = false
  }
  preventDefault() { this.defaultPrevented = true }
  stopPropagation() { this._gestoppt = true }
}

/** Link-Attrappe: nur die Attribute, die `hashZielVon` liest. */
function zielLink(href) {
  const attribute = { href }
  const link = {
    getAttribute: name => attribute[name] ?? null,
    hasAttribute: name => name in attribute,
    target: '',
    closest: sel => (sel === 'a[href]' ? link : null),
  }
  return link
}

globalThis.window = {
  addEventListener(art, fn) {
    if (!listener.has(art)) listener.set(art, new Set())
    listener.get(art).add(fn)
  },
  removeEventListener(art, fn) { listener.get(art)?.delete(fn) },
  // P3-4c: `location.hash = …` navigiert (neuer Eintrag, danach `hashchange`).
  get location() {
    return {
      get hash() { return eintraege[position].hash },
      set hash(wert) {
        const neuerHash = String(wert)
        if (neuerHash.startsWith('#')) {
          eintraege = eintraege.slice(0, position + 1)
          eintraege.push({ state: null, hash: neuerHash })
          position = eintraege.length - 1
          // `hashchange` wird wie im Browser als eigene Aufgabe zugestellt.
          setTimeout(() => melden('hashchange', {}), 0)
        }
      },
    }
  },
  history: {
    // Öffnen/Setzen legt einen neuen Eintrag an (wie pushState mit leerer
    // Adresse: die Adresse bleibt, der Zustand ist neu).
    pushState(state, _titel, url) {
      eintraege = eintraege.slice(0, position + 1)
      eintraege.push({ state, hash: url ? String(url) : eintraege[position].hash })
      position = eintraege.length - 1
      // pushState ändert die Adresse VORWÄRTS, ohne hashchange (gleich oder
      // per url) — hier bewusst gleich gehalten: der Hash bleibt beim Öffnen.
    },
    // Navigation über einen Link ändert die Adresse und legt einen Eintrag an.
    navigate(hash) {
      eintraege = eintraege.slice(0, position + 1)
      eintraege.push({ state: null, hash })
      position = eintraege.length - 1
    },
    back() {
      if (position > 0) position -= 1
      melden('popstate', { state: eintraege[position].state })
    },
    // P3-4 (Restpunkt 11): Die Marke `dkFenster` wird beim Navigieren aus dem
    // Eintrag entfernt, ohne einen neuen anzulegen. Wie im echten Browser
    // aendert `replaceState(state, titel, url)` BEIDES: Zustand und Adresse.
    replaceState(state, _titel, url) {
      eintraege[position] = {
        ...eintraege[position],
        state,
        hash: url ? String(url) : eintraege[position].hash,
      }
    },
    get state() { return eintraege[position].state },
    get length() { return eintraege.length },
    // Zeiger auf den aktuellen Eintrag (wie der echte Browser: `back()`
    // entfernt KEINEN Eintrag, es verschiebt nur den Zeiger).
    get _position() { return position },
  },
  // P3-4c: Klicks werden in der Capture-Phase abgefangen. `document` meldet
  // sie hier direkt an die angemeldeten Listener. Die übrigen Methoden sind
  // nur da, damit Vue beim Laden nicht scheitert (kein echtes DOM im Test).
  document: {
    addEventListener(art, fn) {
      if (!listener.has('document:' + art)) listener.set('document:' + art, new Set())
      listener.get('document:' + art).add(fn)
    },
    removeEventListener(art, fn) { listener.get('document:' + art)?.delete(fn) },
    dispatchEvent(ereignis) {
      for (const fn of listener.get('document:' + ereignis.type) || []) fn(ereignis)
      return !ereignis.defaultPrevented
    },
    createElement: () => ({ style: {}, setAttribute() {}, removeAttribute() {} }),
    createTextNode: () => ({}),
    createComment: () => ({}),
    querySelector: () => null,
    body: { appendChild() {}, removeChild() {}, childNodes: [] },
    documentElement: { style: {} },
  },
  Event: Ereignis,
}

// Die Composable liest `document` und `history` als nackte Globale
// (`typeof document !== 'undefined'`, `window.history`).
globalThis.document = globalThis.window.document

/** Klick auf einen Link (wie ein Tipp auf den Menüeintrag). */
function klicke(href) {
  const ereignis = new Ereignis('click')
  ereignis.target = zielLink(href)
  window.document.dispatchEvent(ereignis)
  // Der Browser folgt dem Link nur, wenn der Klick nicht abgefangen wurde.
  if (!ereignis.defaultPrevented) window.history.navigate(href)
  return ereignis
}

function zuruecksetzen() {
  eintraege = [{ state: null, hash: '#/start' }]
  position = 0
}

const { useZurueckSchliesst } = await import(
  '../src/diakonos/composables/useZurueckSchliesst.js')
const { ref, nextTick } = await import('vue')

// Das Verbrauchen läuft seit P2-3b in einem Makrotask (damit eine Navigation
// per Link Zeit hat). Deshalb nach dem Schließen zusätzlich einen Makrotask
// abwarten — nicht nur den Vue-Mikrotask.
const makrotask = () => new Promise(r => setTimeout(r, 0))

test('B1 · Schließen per Link im Fenster springt NICHT zur Ausgangsseite zurück', async () => {
  zuruecksetzen()
  const offen = ref(false)
  useZurueckSchliesst(offen, () => { offen.value = false })

  offen.value = true                       // Blatt öffnen (Adresse bleibt #/start)
  await nextTick()
  assert.equal(window.location.hash, '#/start')

  // Nutzer tippt einen Eintrag an: die Adresse wechselt VORWÄRTS, dann
  // schließt der @click-Handler das Fenster. Bewusst über `navigate` (kein
  // Klick-Ereignis): deckt den Weg ab, in dem die Adresse schon steht, bevor
  // der Watcher schließt — hier darf kein `back()` die Zielseite anreißen.
  // Der Klick-Weg läuft über den Capture-Listener (Test W1 unten).
  window.history.navigate('#/lieder')
  offen.value = false
  await nextTick()
  await makrotask()

  assert.equal(window.location.hash, '#/lieder',
    'die Zielseite bleibt stehen (kein history.back())')
  assert.equal(window.history._position, 2,
    'der Zeiger steht auf der Zielseite — es wurde nicht zurückgesprungen')

  // Erst ein echtes „Zurück“ führt zur Ausgangsseite — und schließt nichts.
  window.history.back()
  await nextTick()
  assert.equal(window.location.hash, '#/start',
    'ein echtes Zurück führt zur Ausgangsseite')
})

test('B1 · Schließen über die Oberfläche (✕/Esc) verbraucht den Eintrag', async () => {
  zuruecksetzen()
  const offen = ref(false)
  useZurueckSchliesst(offen, () => { offen.value = false })

  offen.value = true
  await nextTick()
  assert.equal(window.history.length, 2, 'Öffnen legt einen Eintrag an')
  assert.equal(window.history._position, 1, 'Zeiger auf dem Fenster-Eintrag')

  offen.value = false                      // ✕ — keine Navigation
  await nextTick()
  await makrotask()
  assert.equal(window.history._position, 0,
    'der Eintrag des Fensters wurde verbraucht (eine Stufe zurück)')
  assert.equal(window.location.hash, '#/start')
})

test('W1 · Zurück schließt bei zwei Fenstern nur das oberste', async () => {
  zuruecksetzen()
  const unten = ref(false)
  const oben = ref(false)
  let untenZu = 0
  let obenZu = 0
  useZurueckSchliesst(unten, () => { untenZu += 1; unten.value = false })
  useZurueckSchliesst(oben, () => { obenZu += 1; oben.value = false })

  unten.value = true
  await nextTick()
  oben.value = true
  await nextTick()
  assert.equal(window.history.length, 3, 'zwei Fenster → zwei Einträge')

  window.history.back()                    // Nutzer drückt Zurück
  await nextTick()
  assert.equal(obenZu, 1, 'oberstes Fenster schließt')
  assert.equal(untenZu, 0, 'unteres Fenster bleibt offen')
  assert.equal(unten.value, true, 'unteres Fenster bleibt offen (Zustand)')
  assert.equal(window.location.hash, '#/start', 'die Seite bleibt')
  assert.equal(window.history._position, 1, 'Zeiger auf dem unteren Fenster')
})

test('W1 · oberes per Esc schließt nur das obere, kein zweites back()', async () => {
  zuruecksetzen()
  const unten = ref(false)
  const oben = ref(false)
  let untenZu = 0
  let obenZu = 0
  // Esc ruft beim Fenster dieselbe Schließen-Funktion auf wie ✕ — genau die,
  // die auch useDialogFokus/DkDialog verwenden.
  const schliesseOben = () => { obenZu += 1; oben.value = false }
  useZurueckSchliesst(unten, () => { untenZu += 1; unten.value = false })
  useZurueckSchliesst(oben, schliesseOben)

  unten.value = true
  await nextTick()
  oben.value = true
  await nextTick()

  schliesseOben()                          // oberes per Esc/✕
  await nextTick()
  await makrotask()
  assert.equal(obenZu, 1, 'oberstes geschlossen')
  assert.equal(untenZu, 0, 'unteres NICHT mitgeschlossen')
  assert.equal(unten.value, true, 'unteres bleibt offen')
  assert.equal(window.history._position, 1,
    'nur der EIGENE Eintrag wurde verbraucht (kein zweites back())')
})

test('D · Deep-Link: ohne offenes Fenster greift Zurück nicht ein', async () => {
  zuruecksetzen()
  const offen = ref(false)
  let zu = 0
  useZurueckSchliesst(offen, () => { zu += 1 })
  window.history.navigate('#/kalender')
  window.history.back()                    // normales Zurück (Deep-Link)
  await nextTick()
  assert.equal(zu, 0, 'kein Fenster offen → Zurück verhält sich normal')
  assert.equal(window.location.hash, '#/start')
})

// R-P3-4b W1 / P3-4c: Der ECHTE Fall hat für Ausgangsseite und Fenster-Eintrag
// DIESELBE Adresse (das Fenster öffnet mit `pushState(state, '')`, die Adresse
// bleibt). Genau dabei entstand der tote Eintrag. Der Ablauf wird hier
// nachgestellt: Klick auf einen Link im Fenster (Capture-Listener fängt ihn
// ab), danach `back()`, im `popstate` setzt die Composable das Ziel.
test('W1/OP-HANDY-7 · Navigieren aus dem Fenster (gleiche Adresse) laesst keinen toten Eintrag', async () => {
  zuruecksetzen()
  // Seite VOR A → A. Damit ist „Zurück 2“ nachprüfbar.
  window.history.navigate('#/anfang')
  window.history.navigate('#/start')
  // Der Ausgangseintrag trägt den Listenzustand der Seite (OP-UI-8).
  window.history.replaceState({ dkListe: '?q=Komm' }, '', '#/start?q=Komm')
  const offen = ref(false)
  useZurueckSchliesst(offen, () => { offen.value = false })

  offen.value = true
  await nextTick()
  assert.equal(window.history.length, 4, 'Oeffnen legt einen Eintrag an')
  assert.equal(window.location.hash, '#/start?q=Komm',
    'das Fenster hat DIESELBE Adresse wie die Ausgangsseite (der reale Fall)')

  // Nutzer tippt einen Menueeintrag an: der Capture-Listener (Klick-Phase)
  // faengt ihn ab, das Fenster schliesst, der Fenster-Eintrag wird verbraucht.
  klicke('#/lieder')
  offen.value = false                     // @click-Handler des Links (Vue)
  await nextTick()
  await makrotask()
  await makrotask()

  assert.equal(window.location.hash, '#/lieder', 'die Zielseite steht')
  assert.equal(window.history.length, 4,
    'der Fenster-Eintrag wurde verbraucht — kein fuenfter Eintrag')

  // EIN echtes Zurueck fuehrt zur Ausgangsseite …
  window.history.back()
  await nextTick()
  assert.equal(window.location.hash, '#/start?q=Komm',
    'Zurueck 1 fuehrt zur Ausgangsseite (der Listenzustand bleibt)')

  // … und ZWEITE echtes Zurueck wirklich weg (der tote Eintrag ist weg).
  window.history.back()
  await nextTick()
  assert.equal(window.location.hash, '#/anfang',
    'Zurueck 2 fuehrt auf die Seite VOR der Ausgangsseite — kein leerer Zwischenschritt')
})

console.log('P2-3b Zurück-Mechanik: Navigation, Oberfläche, gestapelte Fenster, Deep-Link bestanden')
