/**
 * CHAT-R2d — Aufräumen nach „Personen → Nachrichten“: alte Adressen, Anfragen-
 * Hilfen, keine toten Links (Chat-Konzept Abschnitt 10, Zeile CHAT-R2d in 10.5).
 *
 * Diese Karte ist ein NACHWEIS. Sie ändert fast nichts — sie hält fest, dass
 * beim Umzug nichts liegen geblieben ist. Geprüft wird an drei Stellen:
 *
 *   1. ALTE PERSONEN-ADRESSEN (`#/personen…`). Die Liste stammt nicht aus dem
 *      Kopf, sondern aus der GIT-HISTORIE des Routers (letzter Stand vor
 *      CHAT-R2a, `d4827eac^`) — jede dort auflösbare Adresse muss heute
 *      entweder an ihrem Ziel ankommen oder per Weiterleitung dorthin führen.
 *      Gemessen an der ECHTEN Router-Logik: `router.js` läuft in einer vm
 *      (Importe ersetzt, wie in den bestehenden Router-Tests), befragt werden
 *      `weiterleitungsZiel` + `routeMap`/`dynamicRoutes` + die Wächter aus
 *      `beforeEachGuards` — je für eine Sitzung **Mitglied** und
 *      **Verwaltung**. „Seite nicht gefunden“ ist in KEINEM Fall erlaubt.
 *   2. `ANFRAGEN_*`-HILFEN. Sie bestehen weiter und werden benutzt (Adressen,
 *      Unterbereiche, Hauptbereich). Das Anfragen-Abzeichen erscheint nur für
 *      die Verwaltung — geprüft an der Anzeige selbst: die Seitenleiste
 *      (AppSidebar.vue) und die Handy-Schublade (AppMenueSchublade.vue) werden
 *      in jsdom WIRKLICH gemountet, die Befehlspalette läuft als echtes Modul.
 *   3. TOTE LINKS. Jede `#/…`-Adresse in Backend-Mailvorlagen/Benachrichtigungen
 *      und in den Frontend-Texten muss vom Router aufgelöst werden (Liste unten,
 *      gegen routeMap/dynamicRoutes/Weiterleitungen). Dazu EINE Regel, die in
 *      einer Kette alter Adressen enden muss (`#/mitglieder/anfragen` →
 *      `#/personen/anfragen` → Seite `MitgliederAnfragen`) — sonst wäre die
 *      Weiterleitung selbst der tote Link.
 *
 * Lauf (eine Datei je Aufruf): node --test tests/chat-r2d-aufraeumen.test.mjs
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'
import vm from 'node:vm'

import { JSDOM } from 'jsdom'
import * as sfc from 'vue/compiler-sfc'

// Die Seitenleisten-/Schubladen-Regeln (`useSession`, `useVerwaltung`) lesen
// `window` schon beim LADEN des Moduls. Deshalb steht das jsdom-Fenster VOR den
// Modul-Importen unten — dynamische Importe, keine `import`-Zeilen (die würden
// vor diesem Code ausgeführt).
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/diakonos#' })
const FensterVorbereiten = (boot) => {
  const w = dom.window
  w.__DIakonosBOOT = boot
  globalThis.window = w
  globalThis.document = w.document
  Object.defineProperty(globalThis, 'navigator', { value: w.navigator, configurable: true })
  globalThis.localStorage = w.localStorage
  globalThis.sessionStorage = w.sessionStorage
  globalThis.location = w.location
  globalThis.history = w.history
  for (const n of ['HTMLElement', 'Element', 'Node', 'SVGElement', 'Event', 'MouseEvent', 'KeyboardEvent', 'getComputedStyle']) {
    globalThis[n] = w[n]
  }
  w.matchMedia = () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {}, addListener() {}, removeListener() {} })
  globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0)
  globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
  class Beobachter { observe() {} unobserve() {} disconnect() {} }
  globalThis.ResizeObserver = Beobachter
  globalThis.IntersectionObserver = Beobachter
  w.ResizeObserver = Beobachter
  w.IntersectionObserver = Beobachter
  return dom
}
FensterVorbereiten({})

const {
  MENUE, FUSS_EINTRAEGE, MENUE_EINTRAEGE,
  ANFRAGEN_UNTERBEREICHE, ANFRAGEN_HAUPTBEREICH,
  sichtbareEintraege,
  personenReiter, anfragenUnterbereichHref, anfragenUnterbereichAusHash,
  personenReiterAusHash, verwaltungZutreffend, PERSONENVERWALTUNG_BASIS,
} = await import('../src/diakonos/menue.js')
const { schubladeMenue, sichtbarerFuss } = await import('../src/diakonos/components/handyMenue.mjs')
const { seitenEintraege, aktionsEintraege } = await import('../src/diakonos/composables/befehlspalette.mjs')
const { profilAdresse, sucheAdresse } = await import('../src/diakonos/composables/nachrichtenDirekt.mjs')
const {
  anfragenZaehler, anfragenZaehlerBeobachten, anfragenZahlAuffrischen,
  darfAnfragenZaehlerSehen, __setzeAnfragenRechte,
} = await import('../src/diakonos/composables/useVerwaltung.js')

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRC = path.join(FRONTEND, 'src')
const WURZEL = path.resolve(FRONTEND, '..')

const lies = (rel) => readFileSync(path.join(SRC, rel), 'utf8')

/** Zeilennummer zur Zeichenstelle (für lesbare Fehlermeldungen). */
const zeile = (text, stelle) => text.slice(0, stelle).split('\n').length

/** Die drei Sitzungsarten, die die Karte nennt. */
// CHAT-R2d: Der Boot ist der des SERVERS (`spa.py`): `is_admin` = Kern-Admin,
// `ist_mitgliederverwaltung` = `is_admin || Systemrolle Mitgliederadministrator`.
// `module_sichtbar` nennt die Module, in denen gelesen werden darf — `chat`
// muss dabei sein, sonst greift der Nachrichten-Wächter (andere Fälle prüft
// `chat-r2a-navigation`). Die Attrappe ist damit NICHT freundlicher als der
// Server, sondern gleich streng.
const BASIS = PERSONENVERWALTUNG_BASIS
const MITGLIED = {
  istAdmin: false, istMitgliederverwaltung: false,
  boot: {
    is_admin: false, ist_mitgliederverwaltung: false,
    module_sichtbar: ['chat'], mitglied: { status: 'Mitglied' },
  },
}
const VERWALTUNG = {
  istAdmin: true, istMitgliederverwaltung: true,
  boot: {
    is_admin: true, ist_mitgliederverwaltung: true,
    module_sichtbar: ['chat'], mitglied: { status: 'Mitglied' },
  },
}
// Die Mitgliederverwaltung OHNE Kern-Admin (R-11a): eigener Fall, weil die
// Umleitung ausdrücklich an `verwaltung: 'personen'` hängt, nicht an `is_admin`.
const MITGLIEDERADMIN = {
  istAdmin: false, istMitgliederverwaltung: true,
  boot: {
    is_admin: false, ist_mitgliederverwaltung: true,
    module_sichtbar: ['chat'], mitglied: { status: 'Mitglied' },
  },
}
const SITZUNGEN = [
  ['Mitglied', MITGLIED],
  ['Verwaltung', VERWALTUNG],
  // Die Mitgliederverwaltung ohne Kern-Admin: derselbe Personenbereich (R-11a).
  ['Mitgliederverwaltung', MITGLIEDERADMIN],
]

// ══════════════════════════════════════════════════════════════════════════════
// 0 · Die ECHTE Router-Logik in einer vm (Muster: r10-menue-routen.test.mjs)
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Adresse → Ziel, in DERSELBEN Reihenfolge wie `resolveRoute`:
 *   1. `weiterleitungsZiel` (feste Regeln, Rollenregeln, Muster) — ersetzt die
 *      Adresse, dann geht es von vorn los (so oft, wie der Router springt),
 *   2. sonst `routeMap[pfad]`,
 *   3. sonst das erste passende Muster aus `dynamicRoutes`,
 *   4. sonst `NichtGefunden` (die Seite „Seite nicht gefunden“).
 *
 * Der Aufbau der vm ist absichtlich der der bestehenden Router-Tests: die
 * Importe werden gestrichen und durch feste Attrappen ersetzt, damit der
 * Quelltext unverändert ECHT läuft.
 */
function routerVm(boot) {
  let quelle = lies('diakonos/router.js').replace(/^import .*$/gm, '')
  quelle = quelle.replace(/^export \{ modulChatErlaubt \}$/gm,
    'const modulChatErlaubt = (b = {}) => { if (b.is_admin === true) return true; if (!Array.isArray(b.module_sichtbar)) return false; return b.module_sichtbar.includes("chat") }')
  quelle = quelle.replace(/^export \{([^}]*)\}$/gm, '')
  quelle = quelle.replace(/^export /gm, '')
  const ersetzt = []
  const windowStub = {
    __DIakonosBOOT: boot,
    location: { hash: '#/', replace(ziel) { this.hash = ziel; ersetzt.push(ziel) } },
    addEventListener: () => {},
    matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
    history: { replaceState: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  }
  const context = {
    console,
    window: windowStub,
    document: { title: '', addEventListener: () => {}, querySelector: () => null },
    location: windowStub.location,
    history: windowStub.history,
    sessionStorage: windowStub.sessionStorage,
    localStorage: windowStub.localStorage,
    navigator: { language: 'de-DE' },
    setTimeout, clearTimeout, setInterval, clearInterval, Promise,
    __vue: {
      ref: (v) => ({ value: v }),
      computed: (fn) => ({ get value() { return fn() } }),
      shallowRef: (v) => ({ value: v }),
    },
  }
  vm.createContext(context)
  vm.runInContext(`
const ref = globalThis.__vue.ref
const computed = globalThis.__vue.computed
const shallowRef = globalThis.__vue.shallowRef
// CHAT-R2d: die Adressen des umgezogenen Personenbereichs — hier die Werte aus
// menue.js (dieselben Konstanten importiert der Test oben). Damit prüft die vm
// DENSELBEN Weg wie der Betrieb (Tabelle + Rollenregel), nicht nur das Muster
// ohne menue.js.
const PERSONENVERWALTUNG_BASIS = ${JSON.stringify(PERSONENVERWALTUNG_BASIS)}
// Adresse eines Personen-Reiters — wörtlich wie in menue.js (\`personenReiterHref\`).
const personenReiterHref = (id, eingebettet = false) => eingebettet
  ? PERSONENVERWALTUNG_BASIS + '/' + id
  : '#/personen/' + id
const anfragenUnterbereichHref = (bereich, eingebettet = false) => {
  const id = bereich || 'anfragen'
  if (!eingebettet) return id === 'anfragen' ? '#/personen/anfragen' : '#/personen/anfragen/' + id
  return id === 'anfragen'
    ? PERSONENVERWALTUNG_BASIS + '/anfragen'
    : PERSONENVERWALTUNG_BASIS + '/anfragen/' + id
}
// Die EINE Verwaltungsregel aus menue.js (dort importfrei geprüft) — hier als
// wörtliche Fassung, weil der Router seine Importe in der vm verliert.
const verwaltungZutreffend = ${verwaltungZutreffend.toString()}
const setzeFenstertitel = () => {}
const darfWebsite = () => true
const fehlertext = (e) => String(e)
const einrichtungLeitung = {
  EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
  einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
  einrichtungGesehen: () => false,
}
const rueckwegBleibtGueltig = () => true
const rueckwegVergessen = () => {}
${quelle}
globalThis.routerApi = {
  weiterleitungsZiel, routeMap, dynamicRoutes, verwaltungsStufeSeite, verwaltungErlaubt,
}
globalThis.__guards = beforeEachGuards.slice()
`, context)

  const api = context.routerApi
  const pfadVon = (hash) => {
    const [roh] = String(hash).split('?')
    return roh.length > 2 && roh.endsWith('/') ? roh.replace(/\/+$/, '') : roh
  }

  /** Ziel der Weiterleitung (ohne Abfrage) oder null. */
  const wohin = (hash) => {
    const pfad = pfadVon(hash)
    const [, abfrage = ''] = String(hash).split(/(?=\?)/)
    return api.weiterleitungsZiel(pfad, pfad + abfrage) || null
  }

  /** Seitenname nach Weiterleitung, unter Einhaltung der Rechte-Wächter. */
  const aufloesen = (hash) => {
    let aktuell = String(hash)
    const kette = [aktuell]
    for (let i = 0; i < 8; i += 1) {
      const ziel = wohin(aktuell)
      if (!ziel || ziel === aktuell) break
      aktuell = ziel
      kette.push(aktuell)
    }
    const pfad = pfadVon(aktuell)
    let seite = api.routeMap[pfad] || null
    if (!seite) {
      for (const r of api.dynamicRoutes) {
        if (pfad.match(r.pattern)) { seite = r.page; break }
      }
    }
    seite = seite || (pfad === '#/' ? 'Home' : 'NichtGefunden')
    // Die Wächter aus `beforeEachGuards` entscheiden, ob die Seite geladen
    // wird (`false` = der Router bricht den Wechsel ab, `navigate('#/')`).
    const waechter = []
    for (const guard of context.__guards) {
      const r = guard({ to: aktuell, name: seite, params: {} })
      waechter.push(r)
      if (r === false) break
    }
    const abgebrochen = waechter.some((r) => r === false)
    return {
      hash: aktuell, pfad, seite, kette,
      waechter: abgebrochen ? 'gesperrt' : 'offen',
      // Was der Nutzer am Ende sieht: die Seite selbst oder das Dashboard
      // (der Wächter navigiert dorthin).
      sichtbar: abgebrochen ? api.routeMap['#/'] : seite,
    }
  }

  return { api, aufloesen, wohin, ersetzt }
}

// ══════════════════════════════════════════════════════════════════════════════
// 1 · Alte Personen-Adressen (aus der Git-Historie vor CHAT-R2a)
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Die Personen-Adressen des Routers im Stand VOR CHAT-R2a (`d4827eac^`) —
 * fest eingetragen, damit der Test nicht vom Repo-Zustand abhängt; der
 * Herkunftsnachweis steht als eigener Test darunter.
 */
const ALTE_PERSONEN_ADRESSEN = [
  // Verweise auf den Bereich und seine Adressen (Kommentare/Weiterleitungen)
  '#/personen',
  '#/personen/',
  '#/personen/anfragen/',
  '#/personen/anfragen',
  '#/personen/anfragen/anfragen',
  '#/personen/anfragen/formulare',
  '#/personen/anfragen/links',
  '#/personen/datenschutz',
  '#/personen/import',
  '#/personen/liste',
  '#/personen/loeschantraege',
  '#/personen/uebersicht',
  '#/personen/adressbuch',
  // Der Bereich, den die Adressen seit UX3b ersetzt haben (aus denselben
  // Tabellen: sie zeigen heute auf den Personenbereich).
  '#/mitglieder',
  '#/mitglieder/liste',
  '#/mitglieder/uebersicht',
  '#/mitglieder/anfragen',
  '#/mitglieder/datenschutz',
  '#/mitglieder/loeschantraege',
  '#/mitglieder/import',
  '#/adressbuch',
  '#/datenschutz',
  // Personenprofil und die alten Anfragen-Formen mit Abfrageteil.
  '#/mitglied/anna-beispiel',
  '#/personen/anfragen?bereich=anfragen',
  '#/personen/anfragen?bereich=links',
  '#/personen/anfragen?bereich=formulare',
]

/** Die Adressen, die der Router VOR CHAT-R2a (`d4827eac^`) kannte. */
function altePersonenAdressenAusGit() {
  const git = (...args) => execFileSync('git', ['-C', WURZEL, ...args], { encoding: 'utf8' })
  const quellen = [
    git('show', 'd4827eac^:frontend/src/diakonos/router.js'),
    git('show', 'd4827eac^:frontend/src/diakonos/menue.js'),
  ].join('\n')
  const gefunden = new Set()
  for (const m of quellen.matchAll(/#\/(?:personen|mitglieder|adressbuch|datenschutz|mitglied)[A-Za-z0-9/_-]*/g)) {
    gefunden.add(m[0].replace(/\/+$/, '') || m[0])
  }
  return [...gefunden].sort()
}

// Im Image-Build (backend/Dockerfile, Frontend-Stage) gibt es weder `.git` noch
// `backend/` — die Tests, die Historie bzw. Backend-Quellen lesen, laufen dort
// nicht (lokal und in der Integrations-Testliste laufen sie voll).
const OHNE_GIT = existsSync(path.join(WURZEL, '.git')) ? false : 'keine Git-Historie (Image-Build)'
const OHNE_BACKEND = existsSync(path.join(WURZEL, 'backend/src/diakronos_app/api/suche.py')) ? false : 'keine Backend-Quellen (Image-Build)'

test('CHAT-R2d · die geprüfte Adressliste deckt die Git-Historie vor CHAT-R2a ab', { skip: OHNE_GIT }, () => {
  let historisch
  try {
    historisch = altePersonenAdressenAusGit()
  } catch (fehler) {
    assert.fail(`Git-Historie nicht lesbar (${fehler.message}) — die Liste muss belegbar sein`)
  }
  assert.ok(historisch.includes('#/personen'), 'der Router kannte `#/personen`')
  assert.ok(historisch.includes('#/personen/anfragen/links'), 'auch die Reiter-Unteradresse')
  // JEDE damals bekannte Personen-Adresse (auch `…`-Kurzformen und die
  // Bereichsadresse mit Schluss-Schrägstrich) steht in der geprüften Liste.
  const ohneSchluss0 = (a) => (a.length > 2 ? a.replace(/\/+$/, '') : a)
  const geprueft = new Set(ALTE_PERSONEN_ADRESSEN.map(ohneSchluss0))
  const fehlend = historisch.filter((a) => !geprueft.has(ohneSchluss0(a)))
  assert.deepEqual(fehlend, [],
    'jede damals bekannte Personen-Adresse steht in der geprüften Liste')
  // Die Liste ist kein Sammelbecken: nichts erfinden, was es nie gab. Die
  // Schreibweise mit Schluss-Schrägstrich vergleicht der Router ebenfalls
  // (`ohneSchlussslash`) — sie zählt deshalb als dieselbe Adresse.
  const ohneSchluss = (a) => (a.length > 2 ? a.replace(/\/+$/, '') : a)
  const bekannt = new Set(historisch.map(ohneSchluss))
  const erfunden = ALTE_PERSONEN_ADRESSEN.filter((a) => a.startsWith('#/personen')
    && !/[?]/.test(a) && !bekannt.has(ohneSchluss(a)))
  assert.deepEqual(erfunden, [], 'keine erfundene Personen-Adresse in der Liste')
})

for (const [name, sitzung] of SITZUNGEN) {
  test(`CHAT-R2d · alte Personen-Adressen kommen für die ${name}-Sitzung an (nie „Seite nicht gefunden“)`, () => {
    const { aufloesen } = routerVm(sitzung.boot)
    const befunde = []
    for (const adresse of ALTE_PERSONEN_ADRESSEN) {
      const r = aufloesen(adresse)
      befunde.push(`${adresse} → ${r.hash} · ${r.seite} · ${r.waechter}`)
      assert.notEqual(r.seite, 'NichtGefunden',
        `${adresse}: landet auf „Seite nicht gefunden“ (Kette ${r.kette.join(' → ')})`)
      assert.notEqual(r.pfad, '#/nicht-gefunden', `${adresse}: tote Adresse`)
      // Angekommen heißt: eine Seite wird geöffnet ODER der Wächter führt auf
      // das Dashboard (Recht fehlt) — aber nie eine leere/404-Seite.
      assert.ok(r.sichtbar && r.sichtbar !== 'NichtGefunden',
        `${adresse}: keine anzeigbare Seite`)
    }
    assert.equal(befunde.length, ALTE_PERSONEN_ADRESSEN.length)
  })
}

test('CHAT-R2d · die VERWALTUNG kommt über jede alte Adresse an IHREM heutigen Ort an', () => {
  const verwaltung = routerVm(VERWALTUNG.boot)
  // Operator-Review R1: Die Verwaltung darf NICHT auf dem Dashboard landen —
  // das wäre genau der tote Weg (Lesezeichen). Jede alte Adresse führt sie an
  // die heutige Stelle des umgezogenen Bereichs: den Einstellungen-Abschnitt
  // `#/einstellungen/personenverwaltung[/<reiter>[/<unter>]]`.
  const ziele = {
    // Der Bereichseinstieg führt auf den Abschnitt selbst.
    '#/personen': `${BASIS}`,
    '#/personen/': `${BASIS}`,
    // Die Reiter, je unter ihrem heutigen Pfadteil.
    //
    // AUSNAHME `#/personen/liste`: Das ist die EINE Adresse, die laut
    // Chat-Konzept 10.2 ein gültiges ZIEL bleibt (der Reiter „Liste“ — die
    // Liste selbst, die der Wächter ohnehin nicht schließt: `Personen`).
    // Sie wird deshalb NICHT umgeleitet; die Verwaltung landet dort direkt.
    '#/personen/liste': '#/personen/liste',
    '#/personen/anfragen': `${BASIS}/anfragen`,
    '#/personen/anfragen/anfragen': `${BASIS}/anfragen`,
    '#/personen/anfragen/links': `${BASIS}/anfragen/links`,
    '#/personen/anfragen/formulare': `${BASIS}/anfragen/formulare`,
    '#/personen/datenschutz': `${BASIS}/datenschutz`,
    '#/personen/import': `${BASIS}/import`,
    // „Übersicht“ und „Löschanträge“ sind seit UX3j keine Reiter mehr: es gibt
    // heute keinen eigenen Ort — sie führen auf den Abschnitt.
    '#/personen/uebersicht': `${BASIS}`,
    '#/personen/loeschantraege': `${BASIS}`,
    // Die alte Abfrage-Form der Unterbereiche (UX-A2a) nimmt den Bereich mit.
    '#/personen/anfragen?bereich=links': `${BASIS}/anfragen/links`,
    '#/personen/anfragen?bereich=formulare': `${BASIS}/anfragen/formulare`,
    '#/personen/anfragen?bereich=anfragen': `${BASIS}/anfragen`,
    // Die alten Rollen-/Bereichsnamen davor.
    '#/mitglieder/anfragen': `${BASIS}/anfragen`,
    '#/mitglieder/uebersicht': `${BASIS}`,
    '#/mitglieder/import': `${BASIS}/import`,
    '#/datenschutz': `${BASIS}/datenschutz`,
    '#/statistik': `${BASIS}`,
  }
  for (const [adresse, ziel] of Object.entries(ziele)) {
    const r = verwaltung.aufloesen(adresse)
    assert.equal(r.hash, ziel, `${adresse}: führt die Verwaltung an ihren heutigen Ort`)
    assert.notEqual(r.seite, 'NichtGefunden', `${adresse}: keine tote Adresse`)
    // Die heutige Adresse wird WIRKLICH geöffnet (kein Wächter davor) und ist
    // der eingebettete Personenbereich — kein Dashboard.
    assert.equal(r.waechter, 'offen', `${adresse}: der Abschnitt ist für die Verwaltung offen`)
    const erwarteteSeite = adresse === '#/personen/liste' ? 'Personen' : 'EinstellungenPersonenverwaltung'
    assert.equal(r.seite, erwarteteSeite,
      `${adresse}: landet im Personenbereich (${r.kette.join(' → ')})`)
  }
  // Die alten Adressbucheintritte bleiben für ALLE die Liste (Adressbuch-Sicht).
  for (const adresse of ['#/personen/adressbuch', '#/adressbuch']) {
    assert.equal(verwaltung.aufloesen(adresse).hash, '#/personen/liste', `${adresse} → Liste`)
  }
})

test('CHAT-R2d · ein MITGLIED ohne Recht landet weiter auf dem Dashboard, nie auf einer leeren Seite', () => {
  const mitglied = routerVm(MITGLIED.boot)
  // Die Liste ist für alle da (Adressbuch-Sicht der Seite).
  assert.equal(mitglied.aufloesen('#/personen/liste').hash, '#/personen/liste')
  assert.equal(mitglied.aufloesen('#/personen/liste').seite, 'Personen')
  // Der Bereichseinstieg bleibt die Liste — die Verwaltungsumleitung gilt NICHT.
  for (const adresse of ['#/personen', '#/personen/']) {
    assert.equal(mitglied.aufloesen(adresse).hash, '#/personen/liste', `${adresse} → Liste`)
  }
  // Alle Verwaltungsadressen bleiben auflösbar (keine 404) und enden über den
  // Wächter auf dem Dashboard — nie auf einer leeren Seite.
  for (const adresse of ['#/personen/anfragen', '#/personen/anfragen/links', '#/personen/datenschutz',
    '#/personen/import', '#/personen/uebersicht', '#/personen/loeschantraege',
    '#/personen/anfragen?bereich=links', '#/mitglieder/anfragen', '#/datenschutz']) {
    const r = mitglied.aufloesen(adresse)
    assert.notEqual(r.seite, 'NichtGefunden', `${adresse}: Seite existiert (${r.hash})`)
    assert.equal(r.sichtbar, 'Home', `${adresse}: ohne Recht aufs Dashboard`)
    // Kein Sprung der Kette führt in den Verwaltungsabschnitt: das Mitglied
    // darf ihn nie auch nur BETRETEN (der Wächter führt aufs Dashboard).
    for (const sprung of r.kette) {
      assert.equal(sprung.startsWith(BASIS), false,
        `${adresse}: die Kette führt nie über ${BASIS} (${r.kette.join(' → ')})`)
    }
    // Kein ANKOMMEN im Verwaltungsabschnitt: die Adresse des Abschnitts selbst
    // bleibt gesperrt (der Wächter führt aufs Dashboard).
    if (r.hash.startsWith(BASIS)) {
      assert.equal(r.waechter, 'gesperrt',
        `${adresse}: der Verwaltungsabschnitt bleibt für das Mitglied zu (${r.hash})`)
    }
  }
})

test('CHAT-R2d · Mitglied mit `#/personen/anfragen?bereich=links` — nie über die Personenverwaltung, am Ende Dashboard', () => {
  // Der Weg des Mitglieds über die alte Abfrage-Form: die Muster greifen NUR
  // noch ohne Verwaltungsrecht und führen zurück in den alten Personenbereich.
  const mitglied = routerVm(MITGLIED.boot)
  const r = mitglied.aufloesen('#/personen/anfragen?bereich=links')
  assert.equal(r.kette.some((s) => s.startsWith(BASIS)), false,
    `die Kette berührt den Verwaltungsabschnitt nicht (${r.kette.join(' → ')})`)
  assert.equal(r.waechter, 'gesperrt', 'die Anfragen-Seite bleibt ohne Recht zu')
  assert.equal(r.sichtbar, 'Home', `das Mitglied landet auf dem Dashboard (${r.hash})`)
  // … und auch der direkte Sprung der Tabelle zeigt nicht dorthin.
  const ziel = mitglied.wohin('#/personen/anfragen?bereich=links')
  assert.equal(ziel, '#/personen/anfragen/links',
    'das Muster der alten Abfrage-Form zeigt auf den ALTEN Personenbereich')
  // Gegenprobe: MIT Recht führt dieselbe Adresse in den heutigen Abschnitt.
  const verwaltung = routerVm(VERWALTUNG.boot)
  assert.equal(verwaltung.wohin('#/personen/anfragen?bereich=links'),
    `${BASIS}/anfragen/links`, 'die Verwaltung kommt im Abschnitt an')
})

// ══════════════════════════════════════════════════════════════════════════════
// 2 · `ANFRAGEN_*`-Hilfen bestehen und werden benutzt
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2d · `ANFRAGEN_*`-Hilfen bestehen weiter (Unterbereiche, Hauptbereich, Adressen)', () => {
  assert.deepEqual(ANFRAGEN_UNTERBEREICHE.map((u) => u.id), ['anfragen', 'links', 'formulare'])
  assert.equal(ANFRAGEN_HAUPTBEREICH, 'anfragen')
  for (const u of ANFRAGEN_UNTERBEREICHE) {
    assert.equal(u.seite, 'MitgliederAnfragen', `${u.id}: derselbe Seitenname wie vorher`)
    assert.equal(u.verwaltung, 'personen', `${u.id}: Personenbereich (R-11a)`)
  }
  // Adressen: alter Bereich und eingebetteter Abschnitt — beide Formen.
  assert.equal(anfragenUnterbereichHref('links', false), '#/personen/anfragen/links')
  assert.equal(anfragenUnterbereichHref('links', true), `${PERSONENVERWALTUNG_BASIS}/anfragen/links`)
  assert.equal(anfragenUnterbereichHref(ANFRAGEN_HAUPTBEREICH, false), '#/personen/anfragen')
  // Aus einer Adresse gelesen (Pfadform) — unbekanntes fällt auf den Hauptbereich.
  assert.equal(anfragenUnterbereichAusHash('#/personen/anfragen/formulare'), 'formulare')
  assert.equal(anfragenUnterbereichAusHash(`${PERSONENVERWALTUNG_BASIS}/anfragen/links`), 'links')
  assert.equal(anfragenUnterbereichAusHash('#/personen/anfragen/quatsch'), 'anfragen')
  // Die Reiterzeile trägt den Unterbereich als `anfragen`-Reiter.
  const reiter = personenReiter({ istAdmin: true, istMitgliederverwaltung: true })
  assert.equal(reiter.find((r) => r.id === 'anfragen').href, '#/personen/anfragen')
  assert.equal(personenReiterAusHash('#/personen/anfragen/links', { istAdmin: true, istMitgliederverwaltung: true }),
    'anfragen')
})

test('CHAT-R2d · die `ANFRAGEN_*`-Hilfen werden im Frontend noch benutzt', () => {
  // Nicht „irgendwo importiert“: die Stellen, an denen die Anfragen-Adressen
  // entstehen und gelesen werden, rufen die Hilfen selbst auf.
  const menue = lies('diakonos/menue.js')
  assert.match(menue, /export function anfragenUnterbereichHref/,
    'die Adresse eines Unterbereichs entsteht in menue.js')
  assert.match(menue, /export function anfragenUnterbereichAusHash/,
    'und wird dort auch zurückgelesen')
  assert.match(menue, /sichtbareAnfragenUnterbereiche\(\{ istAdmin: true \}\)/,
    'die Rücklese-Funktion prüft gegen dieselbe Liste')
  // Die Anfragen-Seite liest ihre Adresse mit den Hilfen (pages/Personen.vue),
  // und der Reiter selbst kommt aus `personenReiter` — keine zweite Liste.
  const personen = lies('diakonos/pages/Personen.vue')
  assert.match(personen, /\banfragenUnterbereichAusHash\b/,
    'pages/Personen.vue liest den Unterbereich mit der Hilfe')
  assert.match(personen, /\bpersonenReiter\b/,
    'die Reiterzeile kommt aus menue.js (EINE Quelle)')
  assert.match(personen, /\bpersonenAnfragenReiter\b/,
    'die zweite Reiterzeile der Anfragen ebenso')
  // Und der Router kennt die Adressen der Unterbereiche. CHAT-R2d (R1): die
  // VERWALTUNG kommt dort an ihrem HEUTIGEN Ort an (der eingebettete
  // Personenbereich), nicht mehr auf der alten `#/personen/…`-Seite.
  const router = routerVm(VERWALTUNG.boot)
  for (const u of ANFRAGEN_UNTERBEREICHE) {
    const alt = anfragenUnterbereichHref(u.id, false)
    const r = router.aufloesen(alt)
    assert.equal(r.seite, 'EinstellungenPersonenverwaltung',
      `${u.id}: ${alt} führt die Verwaltung in den umgezogenen Bereich`)
    assert.equal(r.hash, anfragenUnterbereichHref(u.id, true),
      `${u.id}: Ziel ist die eingebettete Adresse (${r.hash})`)
  }
})

// ── 2b · Das Anfragen-Abzeichen erscheint NUR für die Verwaltung ────────────

/** Einträge mit `badge: 'anfragen'` — Quelle des Abzeichens in allen Leisten. */
const ANFRAGEN_EINTRAEGE = MENUE_EINTRAEGE.filter((e) => e.badge === 'anfragen')

test('CHAT-R2d · das Anfragen-Abzeichen hängt an genau EINEM Eintrag (Einstellungen)', () => {
  assert.deepEqual(ANFRAGEN_EINTRAEGE.map((e) => e.id), ['einstellungen'],
    'seit CHAT-R2a-2 trägt „Einstellungen“ den Zähler — nicht ein zweiter Eintrag')
  // CHAT-7b-UI-b: „Einstellungen“ hängt seit dem Abschnitt „Gesperrte Personen“
  // an KEINER Verwaltungsstufe mehr (jede angemeldete Person darf hinein). Das
  // Abzeichen ist deshalb nicht am Eintrag entschieden, sondern an der Sitzung:
  // gezeichnet wird es nur mit `darfAnfragenZaehlerSehen` (Test darunter).
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: true }), true,
    'mit Mitgliederverwaltung sieht die Sitzung das Abzeichen')
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: false }), false,
    'ohne Recht nicht — unabhängig davon, wer den Eintrag sieht')
  assert.equal(MENUE_EINTRAEGE.some((e) => e.id === 'personen'), false,
    'der alte Personen-Eintrag (früher Träger des Zählers) ist entfallen')
})

test('CHAT-R2d · `darfAnfragenZaehlerSehen` — nur die Mitgliederverwaltung (fail closed)', () => {
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: true }), true)
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: false }), false)
  assert.equal(darfAnfragenZaehlerSehen({}), false)
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: 'true' }), false,
    'nur ein echtes `true` zählt')
})

test('CHAT-R2d · der Zähler wird ohne Verwaltungsrecht gar nicht erst gefragt', async () => {
  const aufrufe = []
  const echtesFetch = globalThis.fetch
  globalThis.fetch = async (url) => {
    aufrufe.push(String(url))
    return { ok: true, status: 200, text: async () => JSON.stringify({ message: { anfragen: 3 } }) }
  }
  try {
    __setzeAnfragenRechte(() => ({ istMitgliederverwaltung: false }))
    await anfragenZahlAuffrischen()
    assert.deepEqual(aufrufe, [], 'ohne Recht geht keine Anfrage hinaus')
    __setzeAnfragenRechte(() => ({ istMitgliederverwaltung: true }))
    await anfragenZahlAuffrischen()
    assert.equal(aufrufe.length, 1, 'mit Recht genau eine Anfrage')
    assert.equal(String(aufrufe[0]).includes('get_navigation_zaehler'), true,
      `der Aufruf gilt der Kennzahl (${aufrufe[0]})`)
  } finally {
    __setzeAnfragenRechte(null)
    globalThis.fetch = echtesFetch
  }
})

// ── 2c · Seitenleiste und Handy-Schublade WIRKLICH gemountet ────────────────

/**
 * Ein SFC-Lader wie in `mt7b-lese-unterseiten.test.mjs`: die Quelldateien
 * werden in einen Temp-Baum übersetzt (`.vue` über `vue/compiler-sfc`) und von
 * dort geladen. `fetch` ist eine Attrappe, die den Kennzahlen-Endpunkt mit
 * einer festen Zahl beantwortet — alles andere bleibt still.
 */
function baueLader() {
  const AUS = mkdtempSync(path.join(FRONTEND, '.kanban-r2d-'))
  const geschrieben = new Set()
  const ziel = (abs) => abs.replace(SRC, AUS).replace(/\.(vue|js)$/, '.mjs')

  const umschreiben = (zeilen, datei, abs) => zeilen.map((z) => {
    const m = /^(\s*(?:(?:import|export)\b[^'"]*?from\s+|\}?\s*from\s+))(['"])(\.\.?\/[^'"]+)\2/.exec(z)
    if (!m) return z
    const p = path.resolve(path.dirname(abs), m[3])
    let neu = path.relative(path.dirname(datei), p.replace(SRC, AUS).replace(/\.(vue|js)$/, '.mjs'))
    if (!neu.startsWith('.')) neu = './' + neu
    return `${m[1]}${m[2]}${neu}${m[2]}${z.slice(m[0].length)}`
  }).join('\n')

  const schreiben = (abs) => {
    if (geschrieben.has(abs)) return ziel(abs)
    const kandidat = [abs, abs + '.js', abs + '.mjs', abs + '/index.js']
      .find((k) => { try { return statSync(k).isFile() } catch { return false } })
    if (!kandidat) return null
    if (kandidat.endsWith('.vue')) {
      const datei = ziel(kandidat)
      const id = path.basename(kandidat, '.vue').replace(/\W/g, '_')
      const { parse, compileScript, compileTemplate } = sfc
      const { descriptor } = parse(readFileSync(kandidat, 'utf8'), { filename: kandidat })
      const skript = compileScript(descriptor, { id, inlineTemplate: true })
      for (const m of skript.content.matchAll(/from\s+['"](\.\.?\/[^'"]+)['"]/g)) {
        schreiben(path.resolve(path.dirname(kandidat), m[1]))
      }
      geschrieben.add(kandidat)
      let code = skript.content
      if (!/_createCommentVNode|_createElementVNode|_createBlock/.test(code)) {
        const tpl = compileTemplate({
          id, filename: kandidat, source: descriptor.template.content,
          compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
        })
        assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
        const rumpf = tpl.code.replace(/export function render/, 'function render')
          .replace(/^import .*$/gm, '').replace(/\bexport const /g, 'const ')
        code = `${skript.content}\n${rumpf}\n__bauteil.render = render\nexport default __bauteil\n`
          .replace('export default ', 'const __bauteil = ')
      }
      mkdirSync(path.dirname(datei), { recursive: true })
      writeFileSync(datei, umschreiben(code.split('\n'), datei, kandidat), 'utf8')
      return datei
    }
    for (const m of readFileSync(kandidat, 'utf8').matchAll(/from\s+['"](\.\.?\/[^'"]+)['"]/g)) {
      schreiben(path.resolve(path.dirname(kandidat), m[1]))
    }
    geschrieben.add(kandidat)
    const datei = ziel(kandidat)
    mkdirSync(path.dirname(datei), { recursive: true })
    writeFileSync(datei, umschreiben(readFileSync(kandidat, 'utf8').split('\n'), datei, kandidat), 'utf8')
    return datei
  }
  return { schreiben, aufraeumen: () => rmSync(AUS, { recursive: true, force: true }) }
}

/** Frisches jsdom-Fenster + leerer Körper (wie `FensterVorbereiten` oben). */
function jsdomFenster(boot = {}) {
  dom.window.document.body.innerHTML = ''
  dom.window.location.hash = ''
  return FensterVorbereiten(boot)
}

/** `fetch`-Attrappe: Kennzahlen-Endpunkt liefert `zahl`, alles andere `{}`. */
function fetchMitZahl(zahl) {
  const aufrufe = []
  const antwort = (roh) => ({
    ok: true, status: 200,
    text: async () => JSON.stringify(roh),
    json: async () => roh,
  })
  globalThis.fetch = async (url) => {
    aufrufe.push(String(url))
    if (String(url).includes('get_navigation_zaehler')) return antwort({ message: { anfragen: zahl } })
    return antwort({ message: {} })
  }
  return aufrufe
}

const BADGES = (dokument) => [...dokument.querySelectorAll('.dk-nav-badge, .dk-schublade-zaehler')]
  .map((e) => e.textContent.trim())

for (const [name, lage] of [
  ['Verwaltung', { is_admin: true, ist_mitgliederverwaltung: true }],
  ['Mitgliederverwaltung', { is_admin: false, ist_mitgliederverwaltung: true }],
  ['Mitglied', { is_admin: false, ist_mitgliederverwaltung: false, mitglied: { status: 'Mitglied' } }],
]) {
  const erwartet = lage.ist_mitgliederverwaltung === true

  test(`CHAT-R2d · Seitenleiste (${name}): Anfragen-Abzeichen ${erwartet ? 'sichtbar' : 'nicht sichtbar'}`, async () => {
    jsdomFenster({ church_name: 'Muster', ...lage })
    fetchMitZahl(3)
    const lader = baueLader()
    try {
      const datei = lader.schreiben(path.join(SRC, 'diakonos/components/AppSidebar.vue'))
      const bauteil = (await import(pathToFileURL(datei).href + `?v=${Math.random()}`)).default
      const { createApp, h, nextTick } = await import('vue')
      const knoten = document.createElement('div')
      document.body.appendChild(knoten)
      const app = createApp({ render: () => h(bauteil, { collapsed: false }) })
      app.config.warnHandler = () => {}
      app.mount(knoten)
      for (let i = 0; i < 6; i += 1) { await new Promise((r) => setTimeout(r, 25)); await nextTick() }
      const abzeichen = BADGES(document)
      const text = document.body.textContent.replace(/\s+/g, ' ')
      if (erwartet) {
        assert.deepEqual(abzeichen, ['3'], `Seitenleiste zeigt den Zähler (Text: ${text})`)
        // Der Zähler steht am Einstellungen-Eintrag — dem Fuß-Eintrag, nicht am
        // entfallenen Personen-Punkt (den gibt es nicht mehr).
        assert.match(text, /Einstellungen3|Einstellungen 3/, 'die 3 steht hinter „Einstellungen“')
        assert.doesNotMatch(text, /Personen/, 'kein Menüpunkt „Personen“ mehr')
      } else {
        assert.deepEqual(abzeichen, [], `kein Abzeichen ohne Verwaltungsrecht (Text: ${text})`)
      }
      app.unmount()
    } finally {
      lader.aufraeumen()
    }
  })
}

for (const [name, lage] of [
  ['Verwaltung', { is_admin: true, ist_mitgliederverwaltung: true }],
  ['Mitglied', { is_admin: false, ist_mitgliederverwaltung: false, mitglied: { status: 'Mitglied' } }],
]) {
  const erwartet = lage.ist_mitgliederverwaltung === true

  test(`CHAT-R2d · Handy-Schublade (${name}): Anfragen-Abzeichen ${erwartet ? 'sichtbar' : 'nicht sichtbar'}`, async () => {
    jsdomFenster({ church_name: 'Muster', ...lage })
    fetchMitZahl(5)
    const lader = baueLader()
    try {
      const datei = lader.schreiben(path.join(SRC, 'diakonos/components/AppMenueSchublade.vue'))
      const bauteil = (await import(pathToFileURL(datei).href + `?v=${Math.random()}`)).default
      const { createApp, h, nextTick } = await import('vue')
      const knoten = document.createElement('div')
      document.body.appendChild(knoten)
      // Die Schublade bekommt die Zahl wie in App.vue aus dem EINEN Stand.
      const app = createApp({ render: () => h(bauteil, { offen: true, anfragenZahl: 5 }) })
      app.config.warnHandler = () => {}
      app.mount(knoten)
      for (let i = 0; i < 4; i += 1) { await new Promise((r) => setTimeout(r, 25)); await nextTick() }
      const abzeichen = BADGES(document)
      const text = document.body.textContent.replace(/\s+/g, ' ')
      if (erwartet) {
        assert.deepEqual(abzeichen, ['5'], `Schublade zeigt den Zähler (Text: ${text})`)
        assert.match(text, /Einstellungen5|Einstellungen 5/, 'die 5 steht hinter „Einstellungen“')
      } else {
        assert.deepEqual(abzeichen, [], `kein Abzeichen ohne Verwaltungsrecht (Text: ${text})`)
      }
      app.unmount()
    } finally {
      lader.aufraeumen()
    }
  })
}

test('CHAT-R2d · Handy-Schublade: die Zahl kommt vom Zähler-Stand, nie erfunden', () => {
  // 0 und null zeigen nichts (keine „0“) — dieselbe Regel wie in der Leiste.
  const eintraege = schubladeMenue({ istAdmin: true, istMitgliederverwaltung: true })
    .flatMap((g) => g.eintraege)
  assert.equal(eintraege.some((e) => e.badge === 'anfragen'), false,
    'der Zähler sitzt im Fuß, nicht in der Gruppenliste')
  // CHAT-7b-UI-b: „Einstellungen“ ist für ALLE sichtbar (Abschnitt „Gesperrte
  // Personen“) — auch das Mitglied sieht den Fuß-Eintrag.
  assert.deepEqual(sichtbarerFuss({ istAdmin: true, istMitgliederverwaltung: true }).map((e) => e.id),
    ['einstellungen'])
  assert.deepEqual(sichtbarerFuss({ istAdmin: false, istMitgliederverwaltung: false }).map((e) => e.id),
    ['einstellungen'], 'ein Mitglied sieht „Einstellungen“ — die Zahl aber nicht')
  // Die ZAHL selbst bleibt am Recht: ohne Mitgliederverwaltung liefert der
  // Stand `null`, damit nichts gezeichnet wird.
  assert.equal(darfAnfragenZaehlerSehen({ istMitgliederverwaltung: false }), false,
    'ohne Recht keine Zahl (der Eintrag bleibt trotzdem sichtbar)')
})

test('CHAT-R2d · Befehlspalette: „Personenverwaltung“ nur für die Verwaltung, mit gültiger Adresse', () => {
  const eintraege = (rechte) => seitenEintraege({
    menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte,
  })
  const verwaltung = eintraege({ istAdmin: false, istMitgliederverwaltung: true })
  const personenverwaltung = verwaltung.filter((e) => e.titel === 'Personenverwaltung')
  assert.equal(personenverwaltung.length, 1, 'genau EIN Eintrag (kein zweiter Weg)')
  assert.equal(personenverwaltung[0].ziel, PERSONENVERWALTUNG_BASIS)
  const mitglied = eintraege({ istAdmin: false, istMitgliederverwaltung: false })
  assert.equal(mitglied.some((e) => e.titel === 'Personenverwaltung'), false,
    'ein Mitglied findet die Personenverwaltung nicht in der Palette')
  // Einstellungen (Träger des Abzeichens) ist seit CHAT-7b-UI-b für ALLE da —
  // der Abschnitt „Gesperrte Personen“ gehört jeder angemeldeten Person.
  assert.equal(verwaltung.some((e) => e.titel === 'Einstellungen'), true)
  assert.equal(mitglied.some((e) => e.titel === 'Einstellungen'), true,
    'ein Mitglied findet „Einstellungen“ (nur die Personenverwaltung fehlt ihm)')
  // „Person anlegen“ zielt auf den umgezogenen Bereich, nicht auf `#/personen`.
  const aktion = aktionsEintraege({ darfPerson: true })
  assert.equal(aktion.length, 1)
  assert.ok(aktion[0].ziel.startsWith(PERSONENVERWALTUNG_BASIS),
    `„Person anlegen“ bleibt im Personenbereich (${aktion[0].ziel})`)
  assert.equal(verwaltungZutreffend('personen', { istMitgliederverwaltung: true }), true)
  assert.equal(verwaltungZutreffend('personen', {}), false)
})

test('CHAT-R2d · Frontend-Adressen für Personen: keine Umwege über `#/personen`', () => {
  // CHAT-R2d (Korrektur): `profilAdresse` ohne Kennung führte auf `#/personen`
  // — seit CHAT-R2a nur noch eine Umleitung, also ein Umweg.
  assert.equal(profilAdresse(''), '#/nachrichten/suche')
  assert.equal(profilAdresse('  '), '#/nachrichten/suche')
  assert.equal(profilAdresse('anna-beispiel'), '#/mitglied/anna-beispiel')
  assert.equal(sucheAdresse('anna'), '#/nachrichten/suche?q=anna')
  // Der Zurück-Weg aus einem Personenprofil richtet sich nach dem RECHT
  // (Operator-Review R1): Verwaltung → Personenverwaltung, alle anderen → die
  // Personensuche der Nachrichten (dort kommen die Profile im Chat her). Der
  // Test misst das am GEBAUTEN Bauteil (jsdom-Mount), nicht an einem Regex.
  const kopf = lies('diakonos/components/AppTopbar.vue')
  assert.match(kopf, /\bverwaltungZutreffend\('personen'/, 'das Recht kommt aus der vorhandenen Hilfe')
  assert.match(kopf, /\bPERSONENVERWALTUNG_BASIS\b/, 'das Ziel kommt aus menue.js (eine Quelle)')
  assert.match(kopf, /\bsucheAdresse\(\)/, 'der Weg ohne Recht führt in die Personensuche')
  assert.doesNotMatch(kopf, /navigate\('(#\/[^']+)'\)\s*\n\s*else if/, 'kein fest verdrahtetes Ziel')
})

test('CHAT-R2d · Zurück aus dem Personenprofil: Verwaltung → Personenverwaltung, Mitglied → Personensuche', async () => {
  // CHAT-R2d (Operator-Review R1, Punkt 2): `navigateBack` führt NICHT mehr
  // jeden in die Einstellungen. Geprüft am GEBAUTEN Bauteil: die Kopfzeile wird
  // in jsdom gemountet, der Zurück-Knopf geklickt, das Ziel an `location.hash`
  // gemessen. Zwei Sitzungen, zwei Ziele.
  for (const [name, lage, erwartet] of [
    ['Verwaltung', { is_admin: true, ist_mitgliederverwaltung: true }, PERSONENVERWALTUNG_BASIS],
    ['Mitgliederverwaltung', { is_admin: false, ist_mitgliederverwaltung: true }, PERSONENVERWALTUNG_BASIS],
    ['Mitglied', { is_admin: false, ist_mitgliederverwaltung: false, mitglied: { status: 'Mitglied' } },
      '#/nachrichten/suche'],
  ]) {
    jsdomFenster({ church_name: 'Muster', ...lage })
    fetchMitZahl(0)
    const lader = baueLader()
    try {
      const datei = lader.schreiben(path.join(SRC, 'diakonos/components/AppTopbar.vue'))
      const bauteil = (await import(pathToFileURL(datei).href + `?v=${Math.random()}`)).default
      const { createApp, h, nextTick } = await import('vue')
      // Den Seitennamen setzt der ECHTE Router: `#/mitglied/<id>` öffnet
      // `MitgliedDetail` — erst dann zeigt die Kopfzeile den Zurück-Knopf. Kein
      // Griff in den Router-Zustand, sondern ein echter Adresswechsel.
      const routerModul = await import('../src/diakonos/router.js')
      window.location.hash = '#/mitglied/anna-beispiel'
      for (let i = 0; i < 4; i += 1) { await new Promise((r) => setTimeout(r, 20)); await nextTick() }
      assert.equal(routerModul.currentPageName.value, 'MitgliedDetail',
        'der Router steht auf dem Personenprofil')
      const knoten = document.createElement('div')
      document.body.appendChild(knoten)
      const app = createApp({ render: () => h(bauteil, { collapsed: false }) })
      app.config.warnHandler = () => {}
      app.mount(knoten)
      for (let i = 0; i < 4; i += 1) { await new Promise((r) => setTimeout(r, 20)); await nextTick() }
      const knopf = document.querySelector('.dk-zurueck')
      assert.ok(knopf, 'Zurück-Knopf vorhanden')
      knopf.click()
      await nextTick()
      assert.equal(window.location.hash, erwartet, `${name}: Zurück führt nach ${erwartet}`)
      app.unmount()
    } finally {
      lader.aufraeumen()
    }
  }
})

// ══════════════════════════════════════════════════════════════════════════════
// 3 · Keine toten Links: Backend-Vorlagen, Benachrichtigungen, Frontend-Texte
// ══════════════════════════════════════════════════════════════════════════════
/**
 * Alle `#/…`-Adressen einer Datei, OHNE Kommentare (eine Adresse in einem
 * Erklärtext ist kein Link; die Erklärtexte nennen bewusst alte Adressen).
 */
function adressenIn(text, istPython, istVue) {
  let ohne = text
  if (istVue) ohne = ohne.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  if (istPython) {
    // Nur ganze Kommentarzeilen („# …“ am Zeilenanfang) — ein `#/…` in einer
    // Zeichenkette beginnt nie am Zeilenanfang.
    ohne = ohne.split('\n').filter((z) => !/^\s*#/.test(z)).join('\n')
  } else {
    ohne = ohne.replace(/^\s*\/\/.*$/gm, '')
  }
  const treffer = []
  for (const m of ohne.matchAll(/(['"`])(#\/[^'"`\s]*)\1/g)) {
    // Nach der Zeichenkette darf KEIN Fließtext mehr folgen. In den Daten
    // stehen Ziele in Tupeln und Wörterbüchern (`("#/x",` / `"#/x"}`), in
    // Code-Zeilen ein `)` oder `+ …`; ein Erklärsatz (`… (`#/ziel`). Der …`)
    // trägt danach Wörter und fällt hier heraus.
    const nach = ohne.slice(m.index + m[0].length, ohne.indexOf('\n', m.index) === -1
      ? ohne.length : ohne.indexOf('\n', m.index))
    if (!/^\s*$/.test(nach) && /[A-Za-zÄÖÜäöüß]{3,}/.test(nach)) continue
    treffer.push({ adresse: m[2], zeile: zeile(ohne, m.index) })
  }
  return treffer
}

/** Alle Dateien unter `dir` mit einer der Endungen. */
function sammle(dir, endungen, ohne = []) {
  const ergebnis = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const voll = path.join(dir, e.name)
    if (e.isDirectory()) {
      if (ohne.includes(e.name)) continue
      ergebnis.push(...sammle(voll, endungen, ohne))
    } else if (endungen.some((end) => e.name.endsWith(end))) {
      ergebnis.push(voll)
    }
  }
  return ergebnis
}

/** Adressen mit Kennungen (`<id>`, `${…}`, `‹…›`) → ein Beispielwert. */
function mitBeispiel(adresse) {
  return String(adresse)
    .replace(/\$\{[^}]*\}/g, 'beispiel')
    .replace(/[{<][^}>]*[}>]/g, 'beispiel')
    .replace(/‹[^›]*›/g, 'beispiel')
    .replace(/…/g, 'beispiel')
    .replace(/\/<route>$/g, '')
}

/** Keine Adresse: Muster (`#/<route>`, `#/{werkzeug}`), Doku (`#/…`) und
 *  JSON-Schema-Fragmente (`#/$defs/…` — das ist ein Schlüssel IM Dokument). */
const keinLink = (adresse) => adresse.startsWith('#/$') || /[{}<>…*]/.test(adresse)
  // Nur ein PRÄFIX (`#/mitglied/` + Kennung im Code): keine Adresse für sich.
  || /\/$/.test(adresse)

const BACKEND_QUELLEN = OHNE_BACKEND ? [] : [
  ...sammle(path.join(WURZEL, 'backend/src'), ['.py', '.html', '.txt', '.j2'], ['node_modules']),
]
const FRONTEND_TEXTE = [...sammle(SRC, ['.vue', '.mjs', '.js'])]
  // Der Router selbst NENNT die alten Adressen als Ziele und Muster — er ist die
  // Auflösung, kein Link. Seine Adressen prüfen die Tests oben.
  .filter((f) => !f.endsWith(path.join('diakonos', 'router.js')))

test('CHAT-R2d · alle `#/…`-Adressen aus Backend-Vorlagen/Benachrichtigungen löst der Router auf', { skip: OHNE_BACKEND }, () => {
  const { aufloesen } = routerVm(VERWALTUNG.boot)
  const tote = []
  const geprueftAdressen = new Set()
  let geprueft = 0
  for (const datei of BACKEND_QUELLEN) {
    const text = readFileSync(datei, 'utf8')
    for (const { adresse, zeile: nr } of adressenIn(text, datei.endsWith('.py'), false)) {
      if (adresse === '#/' || adresse === '#/gast/' || keinLink(adresse)) continue
      const beispiel = mitBeispiel(adresse)
      if (!beispiel.startsWith('#/')) continue
      geprueft += 1
      geprueftAdressen.add(beispiel)
      const r = aufloesen(beispiel)
      if (r.seite === 'NichtGefunden') {
        tote.push(`${path.relative(WURZEL, datei)}:${nr} ${adresse}`)
      }
    }
  }
  assert.deepEqual(tote, [],
    'tote Adressen in Backend-Vorlagen/Benachrichtigungen (NICHT selbst ändern — melden)')
  // Keine stille Leerprüfung: die Adressen der Suche, der Einrichtungs-Checkliste
  // und des Kalender-OAuth-Rückwegs müssen durch die Prüfung gegangen sein.
  assert.ok(geprueft >= 10, `geprüfte Backend-Adressen: ${geprueft}`)
  for (const pflicht of ['#/einstellungen/gemeinde', '#/mitglieder/liste', '#/kalender/verwalten',
    PERSONENVERWALTUNG_BASIS]) {
    assert.ok(geprueftAdressen.has(pflicht), `${pflicht} wurde geprüft`)
  }
})

test('CHAT-R2d · alle `#/…`-Adressen der Frontend-Texte löst der Router auf', () => {
  const { aufloesen } = routerVm(VERWALTUNG.boot)
  const tote = []
  const geprueftAdressen = new Set()
  let geprueft = 0
  for (const datei of FRONTEND_TEXTE) {
    const text = readFileSync(datei, 'utf8')
    for (const { adresse, zeile: nr } of adressenIn(text, false, datei.endsWith('.vue'))) {
      // Platzhalter-Formen in Kommentaren/Doku (`#/…`, `#/{…}`, `#/diakonos`)
      // sind keine Links — der letzte ist das Adressbeispiel der Doku.
      if (adresse === '#' || adresse === '#/' || adresse === '#/diakonos' || keinLink(adresse)) continue
      const beispiel = mitBeispiel(adresse)
      if (!beispiel.startsWith('#/') || /[…{}<>‹›']/.test(beispiel)) continue
      geprueft += 1
      geprueftAdressen.add(beispiel)
      const r = aufloesen(beispiel)
      // Gesperrt ist NICHT tot: der Wächter führt aufs Dashboard (Recht fehlt).
      if (r.seite === 'NichtGefunden') {
        tote.push(`${path.relative(SRC, datei)}:${nr} ${adresse}`)
      }
    }
  }
  assert.deepEqual(tote, [], 'keine tote Frontend-Adresse')
  assert.ok(geprueft >= 50, `geprüfte Frontend-Adressen: ${geprueft}`)
  assert.ok(geprueftAdressen.has('#/nachrichten'), 'die Nachrichten-Adresse wurde geprüft')
  assert.ok(geprueftAdressen.has(PERSONENVERWALTUNG_BASIS), 'die Personenverwaltung wurde geprüft')
})

test('CHAT-R2d · die Prüfung findet tote Adressen wirklich (Gegenprobe)', () => {
  const { aufloesen } = routerVm(VERWALTUNG.boot)
  // Eine Adresse, die es nie gab, MUSS als tot erkannt werden — sonst wäre der
  // Test oben grün, ohne etwas zu beweisen.
  assert.equal(aufloesen('#/personen/gibtsnicht').seite, 'NichtGefunden')
  // `#/nachrichten/<kennung>` ist ABSICHTLICH offen: jede Kennung ist ein
  // Gespräch; ob es existiert, sagt der Server (kein 404 im Router).
  assert.equal(aufloesen('#/nachrichten/gibtsnicht').seite, 'Nachrichten')
  assert.equal(aufloesen('#/gibtsnicht/egal').seite, 'NichtGefunden',
    'eine erfundene Adresse bleibt erfunden')
  assert.equal(aufloesen('#/nachrichten').seite, 'Nachrichten',
    'und eine gültige Adresse bleibt gültig')
})

test('CHAT-R2d · Backend und Frontend nennen dieselben Personen-Ziele (Suche, Einrichtung)', { skip: OHNE_BACKEND }, () => {
  // Die zwei Backend-Stellen, die Personen-Adressen an die Oberfläche geben,
  // führen beide in den BESTEHENDEN Personenbereich (kein toter Verweis auf
  // den entfallenen Menüpunkt).
  const suche = readFileSync(path.join(WURZEL, 'backend/src/diakronos_app/api/suche.py'), 'utf8')
  const { aufloesen } = routerVm(VERWALTUNG.boot)
  const ziele = [...suche.matchAll(/"(#\/(?:einstellungen|personen|mitglied|mitglieder)[^"]*)"/g)]
    .map((m) => m[1])
  assert.ok(ziele.includes(PERSONENVERWALTUNG_BASIS), 'die Suche kennt die Personenverwaltung')
  for (const ziel of ziele) {
    const r = aufloesen(ziel)
    assert.notEqual(r.seite, 'NichtGefunden', `suche.py: ${ziel} ist kein toter Link`)
  }
  const einrichtung = readFileSync(path.join(WURZEL, 'backend/src/diakronos_app/api/einrichtung.py'), 'utf8')
  for (const m of einrichtung.matchAll(/"(#\/[^"]+)"/g)) {
    const r = aufloesen(m[1])
    assert.notEqual(r.seite, 'NichtGefunden', `einrichtung.py: ${m[1]} ist kein toter Link`)
  }
})

test('CHAT-R2d · eine Weiterleitungskette endet in einer SEITE (kein Link auf eine tote Adresse)', () => {
  const { aufloesen } = routerVm(VERWALTUNG.boot)
  // CHAT-R2d (R1): Die Kette führt die VERWALTUNG bis in den heutigen Ort des
  // Personenbereichs — die letzte Adresse muss eine echte SEITE öffnen.
  for (const [start, ende] of [
    ['#/mitglieder/anfragen', `${BASIS}/anfragen`],
    ['#/mitglieder', '#/personen/liste'],
    ['#/datenschutz', `${BASIS}/datenschutz`],
    ['#/statistik', BASIS],
    ['#/registrierung', `${BASIS}/anfragen`],
  ]) {
    const r = aufloesen(start)
    assert.equal(r.hash, ende, `${start} → ${ende}`)
    assert.notEqual(r.seite, 'NichtGefunden', `${start}: Ziel existiert`)
    // Die letzte Adresse der Kette wird geöffnet (kein Wächter davor) und ist
    // eine echte Seite — sonst wäre die Weiterleitung selbst der tote Link.
    assert.equal(r.waechter, 'offen', `${start}: ${ende} ist für die Verwaltung offen`)
    assert.ok(r.seite && r.seite !== 'NichtGefunden', `${start}: ${ende} öffnet eine Seite`)
  }
})
