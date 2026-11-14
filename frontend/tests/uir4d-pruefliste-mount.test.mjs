/**
 * UI-R4d — Prüfliste: Verhalten am GEMOUNTETEN Bauteil.
 *
 * Warum diese Datei: UI-R4b/R4c hatten drei Lücken, die ein Review zu Recht
 * bemängelt hat — jede davon war „grün, obwohl der Fehler wieder eingebaut
 * war“:
 *
 *   1. Der gemeinsame Stufen-Lader (`stufenTitelEinmalLaden`) war nur DIREKT
 *      geprüft (vier Aufrufe nebeneinander). Stellte man `ModerationCard.vue`
 *      auf den Lader JE KARTE (`stufenTitelLaden`) zurück, blieb alles grün.
 *      → Hier werden mehrere echte `ModerationCard` UND `ModerationAntraege`
 *      auf EINER Seite gemountet, und die Datenschicht zählt die Aufrufe von
 *      `get_rollen_erklaerung`: genau EINER.
 *
 *   2. Der „Stufe: …“-Test baute das `computed` aus `ModerationAntraege.vue`
 *      im Test nach. Ein Rückbau im Bauteil wäre unbemerkt geblieben.
 *      → Hier wird das ECHTE `ModerationAntraege.vue` gemountet, die Titel
 *      treffen NACH den Anträgen ein, und die Zeile muss nachziehen.
 *
 *   3. Die Konflikt-Schranke der Tafel (`istKonfliktItem`) war über die
 *      Vorlage geprüft (kein Knopf), nicht über den Weg `onFreigeben`. Ein
 *      Rückbau auf `item?.column === 'konflikte'` blieb grün.
 *      → Hier wird `onFreigeben` mit einer Konfliktkarte DIREKT ausgelöst
 *      (Kind-Ereignis am gemounteten Baum) und erwartet: keine Freigabe-API,
 *      dafür der Hinweis auf den Konflikt-Dialog.
 *
 * Dazu (UI-R4d Punkt 5): die Warteline wird als STUFE gelesen
 * („wartet auf Freigabe für: …“), geprüft am gemounteten `ModerationCard`.
 *
 * Lauf: node --test tests/uir4d-pruefliste-mount.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { domVorbereiten, uebersetzer, tick, warte, text, mounten } from './hilfen/sfc-mount.mjs'

// ── DOM zuerst (Vue greift beim Import auf `document` zu) ─────────────────
domVorbereiten()
const Vue = await import('vue')

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(HIER, '..', 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const U = uebersetzer({ pruefungsVerzeichnis: HIER, srcDiakonos: SRC })
test.after(() => U.aufraeumen())

// ══════════════════════════════════════════════════════════════════════════
// Attrappen der Datenschicht — alles, was die Bauteile anfassen
// ══════════════════════════════════════════════════════════════════════════
const lage = {
  titelAufrufe: 0,
  brettAufrufe: 0,
  freigaben: [],
  brett: { vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] },
  titelAntwort: {
    stufen_titel: { untergruppe: 'Untergruppe', gruppe: 'Gruppe', gemeinde: 'Alle Mitglieder der Gemeinde' },
  },
  antraege: [],
  /** Angehaltene Titel-Antwort (`Promise`) oder `null` = sofort antworten. */
  titelTor: null,
}

U.attrappe('kanbanApi.js', `
export async function getBoardData() {
  globalThis.__r4dBrettAufruf()
  return JSON.parse(JSON.stringify(globalThis.__r4dBrett()))
}
export async function saveStagingState() { return { ok: true } }
export async function getRessources() { return { resources: [], types: [] } }
export async function resolveConflict(id, action, edits) {
  globalThis.__r4dFreigabe(id, action, edits || {})
  return { id, new_status: 'Festgelegt', action: 'festlegen', offen: [], naechste_stufe: null }
}
export async function getConflictPartner() { return null }
export async function getModerationCount() { return { count: 0 } }
export async function updateSeriesBatchFast() { return { ok: true } }
export async function deleteSeriesBatchFast() { return { ok: true } }
`)

U.attrappe('useApi.js', `
export class AuditConfirmationRequired extends Error {}
const warte = (ms) => new Promise((l) => setTimeout(l, ms))
export async function apiCall(endpunkt) {
  const pfad = String(endpunkt)
  if (pfad.includes('get_rollen_erklaerung')) {
    globalThis.__r4dTitelAufruf()
    // Der Test kann die Antwort ANHALTEN (\`__r4dTitelTor\`): damit lässt sich
    // der Zustand „Anträge gezeichnet, Titel noch nicht da“ überhaupt treffen
    // — sonst trifft die Antwort im selben Tick ein wie der Mount.
    const tor = globalThis.__r4dTitelTor()
    if (tor === 'leer') return { stufen_titel: {} }
    if (tor) await tor
    return globalThis.__r4dTitelAntwort()
  }
  if (pfad.includes('get_offene_sichtbarkeits_antraege')) {
    return { antraege: globalThis.__r4dAntraege() }
  }
  if (pfad.includes('entscheide_sichtbarkeit')) {
    return { success: true, gruppe_status: 'aktiv', gemeinde_status: 'aus' }
  }
  return {}
}
export async function apiAntwortPruefen(r) { return r }
export const navigate = () => {}
`)

U.attrappe('useToast.js', `
export const showToast = (nachricht, typ, aktion) => globalThis.__r4dToast(nachricht, typ, aktion)
`)

// Die Lage liegt als EIN Objekt auf `globalThis`: die Attrappen sind eigene
// ES-Module, ein Modul-Variable der Testdatei sähen sie nicht.
// `__r4dLage` wird bei JEDEM Zurücksetzen NEU gesetzt (siehe unten): sonst
// hinge die Attrappe an einem veralteten Objekt und die Zählung bliebe 0.
// Auf EINE Form festgelegt: gelesen und geschrieben wird ausschließlich
// `globalThis.__r4dLage`. Ein zweiter Zugriff über die Modul-Variable `lage`
// wäre im Fehlerfall ein stiller 0-Wert (jeder Test sah „0 Aufrufe“).
globalThis.__r4dLage = lage
// WICHTIG: Die Attrappen sind eigene ES-Module. Sie greifen deshalb über
// `globalThis.__r4dLage` zu — und zwar AUSSCHLIESSLICH. Ein Zugriff über die
// Modul-Variable `lage` dieser Datei ist ein Treffer ins Leere (die frühere
// Fassung zählte so und meldete jeden Ladeaufruf als „0“). Die Zusagen im
// Test lesen deshalb ebenfalls `globalThis.__r4dLage`.
globalThis.__r4dTitelAufruf = () => { globalThis.__r4dLage.titelAufrufe += 1 }
globalThis.__r4dTitelAntwort = () => JSON.parse(JSON.stringify(globalThis.__r4dLage.titelAntwort))
// Das „Tor“ für die Stufen-Titel: der Test öffnet es, wenn er den Zustand
// davor prüfen will. `null` = offen (sofort antworten).
globalThis.__r4dTitelTor = () => globalThis.__r4dLage.titelTor
globalThis.__r4dBrettAufruf = () => { globalThis.__r4dLage.brettAufrufe += 1 }
globalThis.__r4dBrett = () => globalThis.__r4dLage.brett
globalThis.__r4dFreigabe = (id, action, edits) => {
  globalThis.__r4dLage.freigaben.push({ id, action, edits })
}
globalThis.__r4dAntraege = () => globalThis.__r4dLage.antraege
globalThis.__r4dToasts = []
globalThis.__r4dToast = (nachricht, typ, aktion) => {
  globalThis.__r4dToasts.push({ nachricht, typ, aktion })
}

function zuruecksetzen() {
  lage.titelAufrufe = 0
  lage.brettAufrufe = 0
  lage.freigaben = []
  lage.antraege = []
  lage.titelTor = null
  lage.brett = { vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] }
  // Die Attrappen lesen/schreiben über `globalThis.__r4dLage`; hier wird es
  // ausdrücklich auf DIESES Objekt gesetzt (ein späterer Test darf nicht am
  // Objekt eines früheren hängen).
  globalThis.__r4dLage = lage
  globalThis.__r4dToasts = []
}

/**
 * EINE Seite aus mehreren Bauteilen: `ModerationBoard` (mehrere Karten) und
 * `ModerationAntraege` nebeneinander in EINEM App-Baum. Genau so stehen sie in
 * der Prüfliste — und nur so teilen sie sich den Modul-Merker des
 * gemeinsamen Laders (`freigabeStufenReaktiv.mjs`).
 *
 * @param {{ vorschlaege?: object[], konflikte?: object[], antraege?: object[] }} lageNeu
 */
async function seite({ vorschlaege = [], konflikte = [], antraege = [] } = {}) {
  zuruecksetzen()
  lage.brett = { vorschlaege, konflikte, staging: [], notifications: {}, abgelehnt: [] }
  lage.antraege = antraege
  U.cacheLeeren()   // frische „Seite“: eigener Modulgraph
  const Tafel = await U.laden('components/kronos/ModerationBoard.vue')
  const Antraege = await U.laden('components/kronos/ModerationAntraege.vue')
  const Seite = {
    components: { Tafel, Antraege },
    data: () => ({ freigaben: [] }),
    template: `
      <div>
        <Antraege />
        <Tafel @freigeben="(e) => freigaben.push(e)" />
      </div>`,
  }
  return mounten(Vue, Seite)
}


/**
 * Eine frische Seite mit NUR dem Anträge-Bauteil (Board bleibt weg).
 *
 * `seite()` mountet zusätzlich die Tafel; für die Frage „Anträge VOR Titeln“
 * würde dieselbe Seite den gemeinsamen Lader aber einmal mehr anstoßen und
 * den Ablauf verwischen. Hier wird deshalb bewusst nur das eine Bauteil
 * gemountet — auf einer FRISCHEN Seite (`U.cacheLeeren()`), damit der
 * Titelstand wirklich leer startet.
 */
async function antraegeSeite(antraege = [ANTRAG]) {
  U.cacheLeeren()
  const Reaktiv = await U.laden('components/kronos/freigabeStufenReaktiv.mjs')
  Reaktiv.stufenTitelZuruecksetzen()
  const Antraege = await U.laden('components/kronos/ModerationAntraege.vue')
  const mounted = await mounten(Vue, Antraege)
  return { host: mounted.host, mounted, Reaktiv }
}

/** Ein Vorschlag, den der Aufrufer auf der Gruppenstufe prüfen darf. */
function vorschlag(id, extra = {}) {
  return {
    id, type: 'event', title: 'Chorprobe', start: '2026-11-20 18:00:00', end: '2026-11-20 19:00:00',
    all_day: false, calendar: 'chor', calendar_title: 'Chor', calendar_color: '#336699',
    status: 'Vorschlag', stufe: 'gruppe', darf_pruefen: true, ...extra,
  }
}

/** Eine Konfliktkarte: Status „Konflikt“, prüfbar — aber NUR über den Dialog. */
function konflikt(id, extra = {}) {
  return {
    id, type: 'event', title: 'Chorprobe (Konflikt)', start: '2026-11-20 18:00:00',
    end: '2026-11-20 19:00:00', all_day: false, calendar: 'chor', calendar_title: 'Chor',
    calendar_color: '#336699', status: 'Konflikt', stufe: 'gruppe', darf_pruefen: true, ...extra,
  }
}

/** Ein Antrag der Prüfliste (Server-Felder von `get_offene_sichtbarkeits_antraege`). */
const ANTRAG = {
  typ: 'kalender', objekt: 'chor-kg', stufe: 'gruppe', titel: 'Chorproben',
  gruppe: 'chor', gruppe_name: 'Chor', untergruppe_name: 'Sopran', ziel: 'gemeinde',
}

/** Alle Kind-Komponenten-Instanzen eines vnode-Baums (rekursiv). */
function kindInstanzen(vnode) {
  const liste = []
  const besuch = (n) => {
    if (!n || typeof n !== 'object') return
    if (n.component) liste.push(n.component)
    if (Array.isArray(n.children)) n.children.forEach(besuch)
    if (Array.isArray(n.dynamicChildren)) n.dynamicChildren.forEach(besuch)
  }
  besuch(vnode)
  return liste
}

/**
 * Alle Komponenten-Instanzen im gemounteten Baum (Breitensuche über
 * Komponenten-Knoten). Nur so lässt sich `onFreigeben` der Tafel auslösen,
 * ohne über die Karte zu klicken (die Konfliktkarte hat ja keinen Knopf;
 * genau das ist der Punkt).
 *
 * In Vue 3 sind Komponenten-Knoten (`shapeFlag & 4` / `n.type` ist ein Objekt
 * ohne `__isFragment`) VNodes mit eigener Instanz in `n.component`. Primitive
 * Knoten (Text, `#text`) und reine Element-Knoten werden NICHT betreten — ein
 * `vnode.component` an einem Fragment gehört nicht dazu.
 */
function komponenten(vm) {
  const gesehen = new Set()
  const gefunden = []
  const lauf = (instanz) => {
    if (!instanz || gesehen.has(instanz)) return
    gesehen.add(instanz)
    gefunden.push(instanz)
    if (!instanz.subTree) return
    kindInstanzen(instanz.subTree).forEach(lauf)
  }
  lauf(vm)
  return gefunden
}

test('UI-R4d · „Stufe: …“ am echten Anträge-Bauteil zeichnet nach, wenn die Titel später kommen', async () => {
  // Die Anträge antworten SOFORT, die Stufen-Titel erst 40 ms später — genau
  // die Reihenfolge, bei der früher „Stufe: —“ stehen blieb. Geprüft wird das
  // echte `ModerationAntraege.vue`, nicht ein nachgebautes `computed`.
  //
  // Hier wird bewusst NUR das Anträge-Bauteil gemountet (nicht die ganze
  // Seite): die Titel-Ablage ist ein Modul-Singleton je Seite.
  // Die Attrappen nur EINMAL aufsetzen: `zuruecksetzen()` setzt bewusst KEINE
  // Attrappen (es läuft in jedem Test und schriebe sonst useApi.js neu — dessen
  // `import()`-Cache behielte aber die ERSTE Fassung).
  zuruecksetzen()
  lage.antraege = [ANTRAG]
  // Die Titel-Antwort wird ANGEHALTEN: die Anträge kommen an, die Titel nicht.
  // Das ist genau der Befund von UI-R4b/6 — vorher blieb dann „Stufe: —“.
  lage.titelTor = 'leer'
  const { host, Reaktiv } = await antraegeSeite()
  await warte(10)

  // Zustand VOR den Titeln: die Zeile steht, aber ohne Stufe (kein Dauer-„—“).
  assert.equal(host.querySelectorAll('.dk-antrag-karte').length, 1, 'die Antragszeile fehlt')
  assert.equal(host.querySelector('.dk-antrag-stufe'), null,
    'ohne Titel steht gar keine Stufe (kein „—“ als Dauerzustand)')

  // Jetzt treffen die Titel ein — die Zeile zieht VON SELBST nach.
  lage.titelTor = null
  await Reaktiv.stufenTitelLaden(async (pfad) => {
    if (!String(pfad).includes('get_rollen_erklaerung')) return {}
    return globalThis.__r4dLage.titelAntwort
  })
  await Vue.nextTick()
  const stufe = host.querySelector('.dk-antrag-stufe')
  assert.ok(stufe, 'die Stufe fehlt nach der Titel-Antwort (kein Nachzeichnen)')
  assert.equal(text(stufe), 'Stufe: Gruppe')
  // Und es blieb beim EINEN Aufruf, obwohl die Titel später kamen.
  assert.equal(globalThis.__r4dLage.titelAufrufe, 1,
    `get_rollen_erklaerung lief ${globalThis.__r4dLage.titelAufrufe}×`)
})

// ══════════════════════════════════════════════════════════════════════════
// 1 · Der gemeinsame Stufen-Lader: EIN Aufruf für die ganze Seite
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · mehrere Karten UND die Anträge laden die Stufen-Titel gemeinsam EINMAL', async () => {
  // Vier Vorschlagskarten + zwei Anträge + ein Konflikt auf EINER Seite.
  // Rückbau-Gegenprobe: `ModerationCard.vue` auf `stufenTitelLaden` (Lader je
  // Karte) → sechs bis acht Aufrufe, dieser Test wird rot.
  const { host, warnungen } = await seite({
    vorschlaege: [vorschlag('EV-1'), vorschlag('EV-2'), vorschlag('EV-3'), vorschlag('EV-4')],
    konflikte: [konflikt('EV-K1')],
    antraege: [ANTRAG, { ...ANTRAG, objekt: 'chor-sopran', stufe: 'untergruppe' }],
  })

  // Karten und Anträge sind da (sonst prüfte der Test nichts).
  const karten = [...host.querySelectorAll('.dk-mcard')].map((e) => e.dataset.id)
  assert.deepEqual(karten.sort(), ['EV-1', 'EV-2', 'EV-3', 'EV-4', 'EV-K1'],
    'die Karten fehlen — der Test misst sonst nichts')
  assert.ok(host.querySelectorAll('.dk-antrag-karte').length === 2,
    'die Anträge fehlen — der Test misst sonst nichts')

  // Die Titel treffen erst nach dem Mount ein (jede Karte fragt im onMounted).
  assert.equal(globalThis.__r4dLage.titelAufrufe, 1,
    `get_rollen_erklaerung wurde ${globalThis.__r4dLage.titelAufrufe}× geladen — je Seite genau EINMAL`)

  await warte(40)
  assert.equal(globalThis.__r4dLage.titelAufrufe, 1, 'auch nach dem Zeichnen lädt keine weitere Karte nach')
  // Und die Namen sind angekommen (der eine Lader hat gewirkt).
  assert.match(text(host), /Stufe: Gruppe/, 'die Stufe steht mit Server-Titel an der Karte')
  assert.deepEqual(warnungen, [], 'Vue-Warnungen beim Zeichnen')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · „Stufe: …“ am ECHTEN ModerationAntraege (kein nachgebautes computed)
// ══════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════
// 3 · Die Konflikt-Schranke der Tafel greift im Weg `onFreigeben`
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · onFreigeben mit einer Konfliktkarte gibt NICHT frei und verweist auf den Dialog', async () => {
  // Der Fehler, den das Review fand: `istKonfliktItem` prüfte
  // `item?.column === 'konflikte'` — ein Feld, das keine Karte trägt. Die
  // Schranke war nie wahr; ein Rückbau blieb grün, weil nur die Vorlage
  // (kein Knopf) geprüft war. Hier wird der Weg SELBST ausgelöst: das
  // `freigeben`-Ereignis der Tafel mit einer Konfliktkarte.
  const { vm } = await seite({
    // Der Konflikt steht bewusst in der VORSCHLAGS-Spalte: dort gibt es den
    // Knopf nur, wenn die Schranke der Karte versagt — und der zweite Weg
    // (`onFreigeben`) ist genau der, den die Tafel zusätzlich absichern muss.
    vorschlaege: [konflikt('EV-K2')],
    konflikte: [],
  })
  await warte(30)

  // Die Tafel-Instanz im Baum finden und den Freigabe-Weg direkt auslösen.
  // `ModerationBoard` reicht ihn über `defineExpose` heraus (Produktionsweg
  // bleibt die Karte; hier gibt es bewusst keinen Knopf zum Klicken).
  // `vm.$` ist die öffentliche Instanz — der Komponentenbaum hängt an ihrer
  // internen `subTree`.
  const tafel = komponenten(vm.$).find((i) => typeof i.exposed?.onFreigeben === 'function')
  assert.ok(tafel, 'die Tafel gibt `onFreigeben` nicht her — die Schranke ist dann nicht prüfbar')

  // Der Aufruf, den die Karte im Fehlerfall auslösen würde.
  await tafel.exposed.onFreigeben({ item: konflikt('EV-K2'), stufe: 'gruppe' })
  await warte(50)
  assert.equal(globalThis.__r4dLage.freigaben.length, 0,
    'eine Konfliktkarte darf NICHT ohne Konflikt-Dialog freigegeben werden')
  const hinweis = globalThis.__r4dToasts.filter((t) => t.typ === 'warning' || t.typ === 'error')
  assert.ok(hinweis.some((t) => /Konflikt-Dialog|Konflikt/i.test(t.nachricht)),
    `kein Hinweis auf den Konflikt-Dialog — Toasts: ${JSON.stringify(globalThis.__r4dToasts)}`)
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Warteline als STUFE lesbar (UI-R4d Punkt 5) — am echten Bauteil
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · die Warteline der Karte nennt die Stufe als Stufe, nicht als Empfänger', async () => {
  const { host } = await seite({
    vorschlaege: [vorschlag('EV-1', { stufe: 'gemeinde', darf_pruefen: false })],
  })
  await warte(40)

  const zeile = host.querySelector('.dk-mcard-wartet')
  assert.ok(zeile, 'die Warteline fehlt an der Karte')
  assert.equal(text(zeile), 'wartet auf Freigabe für: Alle Mitglieder der Gemeinde',
    'die Warteline muss die Stufe als STUFE lesen („Freigabe für: …“)')
  host.remove()
})
