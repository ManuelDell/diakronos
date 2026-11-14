/**
 * UI-R1 — Mountet die ECHTE `pages/GruppeDetail.vue` in jsdom.
 *
 * Der Wegwerf-Stack zeigte zwei Anzeigefehler, die sich NICHT über die reine
 * Logik (`gruppenEinstellungen.mjs`) prüfen lassen:
 *
 *   1. Der Inhalt des Reiters „Einstellungen“ wurde nicht gezeichnet
 *      (Screenshot: nur Seitenkopf + Reiterzeile).
 *   2. Die Übersicht zeichnete nach einem Wechsel des Reiters/Hashes
 *      nicht zuverlässig.
 *
 * Dieser Test stellt beide Fälle nach: `apiCall` ist gemockt (die Antwort von
 * `gruppen.get_gruppe_detail` mit echten Rechtefeldern), der Hash wird
 * umgeschaltet, und geprüft wird, was im DOM steht.
 *
 * Lauf: node --test tests/ui-r1-reiter-mount.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, readFileSync as rf } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (relativ) => readFileSync(new URL(relativ, SRC), 'utf8')

// ── jsdom zuerst, dann Vue ────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot', 'HTMLButtonElement', 'sessionStorage', 'localStorage',
  'Location', 'History', 'PopStateEvent', 'HashChangeEvent', 'Navigator', 'NodeList']) {
  if (dom.window[schluessel] !== undefined) globalThis[schluessel] = dom.window[schluessel]
}

// ── API-Mock ──────────────────────────────────────────────────────────────
/** Antwort von `gruppen.get_gruppe_detail` für die Gruppe „Chor“ (HV = Rebekka). */
export const GRUPPE_ANTWORT = {
  gruppe: { name: 'Chor', gruppenname: 'Chor', status: 'Aktiv', beschreibung: 'Singt.' },
  mitglieder: [{ name: 'CH-1', mitglied: 'M-1', vollstaendiger_name: 'Anna Beispiel', rolle: 'Mitglied', status: 'Aktiv' }],
  verantwortliche: [{ email: 'rebekka.fink@example.org', name: 'Rebekka Fink' }],
  untergruppen: [{ name: 'UG-1', untergruppenname: 'Sopran' }],
  aufgaben: [{ name: 'A-1', titel: 'Noten kopieren', erledigt: false }],
  ankuendigungen: [{ name: 'K-1', titel: 'Probe verschoben' }],
  wiki_artikel: [],
  is_member: true,
  rechte: { verwalten: true, rollen: true, ankuendigung_anlegen: true, aufgabe_anlegen: true },
}

const ROLLEN_ANTWORT = {
  rollen: [
    { benutzer: 'rebekka.fink@example.org', rolle: 'HV', untergruppe: null, name: 'Rebekka Fink', untergruppe_name: null },
    { benutzer: 'melanie.mustermann@example.org', rolle: 'MV', untergruppe: null, name: 'Melanie Mustermann', untergruppe_name: null },
  ],
  darf_hv_mv_ernennen: true,
  darf_verwalten: true,
}

/** `get_personen_auswahl` — Personen für die Rollen-Auswahl (Konto + Name). */
const PERSONEN_ANTWORT = {
  personen: [
    { benutzer: 'rebekka.fink@example.org', name: 'Rebekka Fink' },
    { benutzer: 'melanie.mustermann@example.org', name: 'Melanie Mustermann' },
    { benutzer: 'neu@example.org', name: 'Neue Person' },
  ],
}

/** Aufrufe der API: [methode, argumente]. */
const aufrufe = []

/**
 * Überschreibungen für einzelne Tests (z. B. Mitglied ohne Rechte). Sie
 * ersetzen die Standardantwort, ohne dass ein Test die anderen beeinflusst.
 */
let ueberschreibungen = {}

globalThis.__uiR1ApiMock = async (methode, args) => {
  // Reihenfolge: SOFORT beim Aufruf festhalten (`index`) — `aufrufe` wächst in
  // der Zeit, in der dieser Aufruf wartet, und `indexOf` fände danach einen
  // späteren gleichnamigen Eintrag.
  const index = aufrufe.push([methode, args]) - 1
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    // Ein Versprechen (verzögerte/abweisende Antwort) wird ERWARTET, sonst
    // käme `{}` heraus und der Ladezustand wäre nicht prüfbar.
    const wert = antwort instanceof Promise ? await antwort : antwort
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppe_detail$/.test(methode)) return JSON.parse(JSON.stringify(GRUPPE_ANTWORT))
  if (/get_gruppe_termine$/.test(methode)) return { termine: [] }
  if (/rechte\.get_gruppenrollen$/.test(methode)) return JSON.parse(JSON.stringify(ROLLEN_ANTWORT))
  if (/rechte\.get_meine_rechte$/.test(methode)) return { verwalten: true, rollen: true }
  if (/get_personen_auswahl$/.test(methode)) return JSON.parse(JSON.stringify(PERSONEN_ANTWORT))
  return { success: true }
}

// ── SFC-Übersetzer (Muster wie tests/ux3h-…) ──────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir1-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

/**
 * EIN Stellvertreter für `composables/useApi.js`: alle Bauteile (Seite UND
 * Kinder) holen `apiCall` hier — sonst spräche die halbe Oberfläche den Mock
 * und die andere Hälfte das echte `fetch`, und der Test prüfte ein Zwitter.
 */
mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  // Sammel-Integration (UI-R1c + UI-R5b): GruppeDetail bindet seit UI-R5 das
  // Termin-Formular samt Kalender-Store ein, die weitere Helfer aus useApi
  // brauchen. Alles außer `apiCall` kommt deshalb aus dem ECHTEN Modul
  // (eine lokale Ausfuhr überdeckt die gleichnamige aus `export *`).
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR1ApiMock(methode, args)\n'
  + 'export default { apiCall }\n')

function uebersetze(abs, bezug = dirname(abs)) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  // Relative Importe zeigen ins QUELLVERZEICHNIS (`bezug`) — die übersetzte
  // Datei liegt in TMP und würde sonst dort nach ihren Nachbarn suchen.
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    // EINE Umleitung für ALLE Bauteile: `apiCall` kommt aus dem Stellvertreter,
    // nie aus dem echten `useApi.js` (das `fetch` ruft und eine Sitzung braucht).
    if (/composables\/useApi/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    const ziel = resolve(bezug, spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

/**
 * Die Seite wird übersetzt; `apiCall` zeigt über den Stellvertreter auf den
 * Mock (siehe `uebersetze`). Der Quelltext bleibt unangetastet.
 */
function seiteMitApiMock() {
  return uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'))
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const warte = async (n = 12) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/**
 * Mountet die Seite und misst, ob der Rückfall die Adresse ERSETZT hat.
 *
 * UI-R1c: Der Rückfall geht jetzt über `window.location.replace(…)`. Diesen
 * Aufruf kann jsdom nicht abhören (an `Location` lässt sich nichts zuweisen,
 * die Methoden liegen nicht am Prototyp) — der Weg wird darum am QUELLTEXT
 * geprüft (Test 9). Messbar bleibt `history.replaceState`, der frühere Weg
 * (UI-R1b); er darf NICHT mehr benutzt werden, weil er kein `hashchange`
 * auslöst. Die Länge des Verlaufs meldet jsdom hier nicht zuverlässig, weil
 * jeder Testaufbau selbst einen Eintrag anlegt.
 */
async function seiteMitVerlaufsMessung({ hash, warteMs, router = false }) {
  let ersetzt = false
  const echt = window.history.replaceState.bind(window.history)
  window.history.replaceState = (...args) => { ersetzt = true; return echt(...args) }
  try {
    const ergebnis = await seiteMounten({ hash, warteMs, router })
    return { ...ergebnis, ersetzt }
  } finally {
    window.history.replaceState = echt
  }
}

/**
 * Die laufende `GruppeDetail`-Instanz hinter einem Mount (für Wege, deren
 * Knopf an der SITZUNG hängt — z. B. `canManage` für den Administrator).
 */
function komponente(host) {
  return host.__vue_app__._instance.subTree.component
}

/**
 * Setzt `document.baseURI` für die Link-Auflösung auf die WURZEL zurück.
 *
 * UI-R1c (im Test belegt, nicht vermutet): jsdom lässt `baseURI` auf der
 * Adresse des ERSTEN Aufbaus stehen, auch nach `location.hash`/`replace`. Ein
 * Verweis `href="#/…"` wird beim Klick daraus aufgelöst — in dieser Datei
 * gegen den Rückfall-Stand der Karte davor, und der Klick landete auf der
 * ALTEN Seite (Reihenfolge-Abhängigkeit von Test 9 auf Test 11). Ein
 * `<base href="/">` stellt die Auflösung auf die Wurzel — genau das, was ein
 * Browser nach dem Rückfall tut.
 */
function basisZuruecksetzen() {
  const erzeugen = () => {
    const basis = document.createElement('base')
    basis.setAttribute('data-test', 'r1c')
    basis.setAttribute('href', 'http://localhost/')
    return basis
  }
  // Ein <base href="/"> ist der richtige Weg — jsdom behält aber die am
  // ELEMENT schon aufgelöste Adresse, wenn nur `href` geändert wird. Darum das
  // Element austauschen: HEAD leeren (er trägt in dieser Datei nur das <base>)
  // und neu einsetzen. `querySelector` wird dafür NICHT benutzt — es lief in
  // jsdom bei vorhandenem <base> in den falschen Zweig.
  const alt = [...document.head.children].filter((el) => el.tagName === 'BASE')
  for (const el of alt) el.remove()
  document.head.appendChild(erzeugen())
}

/**
 * Wechselt nach dem Mounten auf den Reiter „Einstellungen“. Ein Test, der
 * diesen Reiter braucht, mountet die Übersicht und schaltet hier um — so wie
 * ein Mensch klickt; ein Mount DIREKT in `…/einstellungen` lief mit der
 * Adresse des Vorgängertests und damit gegen den Rückfall.
 */
async function zumReiter(host) {
  basisZuruecksetzen()
  const reiter = [...host.querySelectorAll('.dk-ui-reiter-punkt, button, a')]
    .find((e) => e.textContent.trim() === 'Einstellungen')
  assert.ok(reiter, 'Vorbedingung: Reiter „Einstellungen“ fehlt')
  // jsdom-Eigenheit (UI-R1c, im Test belegt): ein Klick auf `href="#/…"`
  // landet in dieser Datei auf der ALTEN Seite — jsdom setzt beim Aufbau des
  // Dokuments eine Bezugsadresse fest, und die trägt hier den Rückfall-Stand
  // der Karte davor (Reihenfolge-Abhängigkeit: Test 9 machte Test 11 rot).
  // Verlässlich ist der Weg über `location.href` — dasselbe Ziel, nur ohne
  // die Auflösung über die Bezugsadresse. Im Browser ist der Klick auf den
  // Reiter gleichwertig (die Adresse steht im `href`).
  window.location.href = 'http://localhost/' + reiter.getAttribute('href')
  reiter.click()
  await warte(24)
}

/** EIN abweisendes Versprechen (mehrfach erwartet, ohne zweite Ablehnung). */
function abweisen(fehler = Object.assign(new Error('weg'), { status: 403 })) {
  const p = Promise.reject(fehler)
  p.catch(() => {})
  return p
}

/**
 * Lädt den ECHTEN Router (einmal je Prozess).
 *
 * UI-R1c: Der Rückfall ist nur dann richtig, wenn er den ROUTER bewegt. Ohne
 * Router konnte der Test nicht sehen, dass `history.replaceState` zwar die
 * Adresse umschreibt, `aktiverReiter` aber auf „einstellungen“ stehen lässt —
 * gezeichnet wurde die leere Karte „Rollen der Gruppe“ bei der Adresse
 * `…#/gruppe/Chor`. `window` ist hier das jsdom-Fenster; `router.js` meldet
 * sich beim Import selbst am `hashchange` an.
 */
let routerModul = null
async function routerLaden() {
  if (!routerModul) {
    routerModul = await import(new URL('../src/diakonos/router.js', import.meta.url).href)
  }
  return routerModul
}

/** Meldungen der Vue-App hinter einem Mount (für aussagekräftige Fehlertexte). */
function meldungenVon(host) {
  return [...(host.__meldungen || [])].slice(0, 6).join(' | ')
}

async function seiteMounten({ hash = '#/gruppe/Chor', warteMs = 12, antworten, router = false } = {}) {
  aufrufe.length = 0
  // `antworten` überschreibt den Mock für den MOUNT dieses Tests (Tests 1–9
  // setzen ihre Überschreibungen selbst; die UI-R1b-Tests mounten direkt in
  // den gewünschten Zustand und stellen ihn danach um). Fehlt der Parameter,
  // bleibt die Überschreibung des Tests stehen.
  if (antworten) ueberschreibungen = antworten
  globalThis.window.__DIakonosBOOT = { roles: [], devmode: false, user: { email: 'rebekka.fink@example.org' } }
  // UI-R1b: IMMER erst auf die Übersicht — ein Test, der eine andere Adresse
  // will, schaltet sie nach dem Mounten selbst um (`adresseWechseln`). Vorher
  // blieb die Adresse des Vorgängertests stehen, und der Reiter-Rückfall
  // („ohne Rechte → Übersicht“) hat den Testaufbau überholt.
  if (window.location.hash !== '#/gruppe/Chor') window.location.hash = '#/gruppe/Chor'
  await new Promise((l) => setTimeout(l, 0))
  if (hash !== '#/gruppe/Chor') {
    window.location.hash = hash
    window.dispatchEvent(new window.HashChangeEvent('hashchange'))
  }
  // UI-R1c: Den Router NACH dem Setzen der Adresse laden — er liest den Hash
  // beim Import und meldet sich am `hashchange` an. Der folgende Wechsel lässt
  // ihn die aktuelle Adresse aufnehmen.
  if (router) {
    await routerLaden()
    window.dispatchEvent(new window.HashChangeEvent('hashchange'))
    await new Promise((l) => setTimeout(l, 0))
  }
  // Ein Bauteilstand wird EINMAL übersetzt; ein erneuter Import im zweiten
  // Test desselben Prozesses gäbe aber nur diesen Pfad zurück — das
  // `await import` liefert dann SOFORT (mikrotask), der Mount liefe vor der
  // Hash-Änderung. Darum ein echter Zeittakt vor jeden Mount.
  await new Promise((l) => setTimeout(l, 0))
  const pfad = seiteMitApiMock()
  const Seite = (await import('file://' + pfad)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { GruppeDetail: Seite }, template: '<GruppeDetail />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  host.__meldungen = meldungen
  await warte(warteMs)
  return { host, app, meldungen }
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Übersicht zeichnet (Grundzustand, kein Reiter aktiv)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: Übersicht zeichnet Karten (Details, Aufgaben)', async () => {
  const { host, meldungen } = await seiteMounten()
  const text = host.textContent
  assert.ok(text.includes('Details'), 'Karte „Details“ fehlt | ' + meldungen.slice(0, 4).join(' | '))
  assert.ok(text.includes('Aufgaben'), 'Karte „Aufgaben“ fehlt')
  assert.ok(text.includes('Noten kopieren'), 'Aufgabe nicht gezeichnet')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Reiterzeile nur mit Server-Rechten
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: Reiter „Einstellungen“ erscheint bei rechte.verwalten=true', async () => {
  const { host, meldungen } = await seiteMounten()
  const reiter = [...host.querySelectorAll('button, a')].map((e) => e.textContent.trim())
  assert.ok(reiter.some((t) => t === 'Einstellungen'),
    'Reiter fehlt | ' + meldungen.slice(0, 4).join(' | '))
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Kernfehler: Inhalt des Reiters „Einstellungen“ nach Hash-Wechsel
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: nach #/gruppe/Chor/einstellungen wird der Rollen-Inhalt gezeichnet', async () => {
  const { host, meldungen } = await seiteMounten()
  assert.ok(host.textContent.includes('Noten kopieren'), 'Vorbedingung: Übersicht zeichnet')

  window.location.hash = '#/gruppe/Chor/einstellungen'
  window.dispatchEvent(new window.HashChangeEvent('hashchange'))
  await warte(16)

  const text = host.textContent
  assert.ok(!text.includes('Noten kopieren'), 'Übersicht steht noch (kein Reiterwechsel)')
  assert.ok(text.includes('Rollen') || text.includes('Hauptverantwortliche'),
    'Inhalt des Reiters „Einstellungen“ fehlt | ' + meldungen.slice(0, 6).join(' | '))
  assert.ok(text.includes('Rebekka Fink'),
    'HV-Name fehlt — Rollenliste leer | ' + meldungen.slice(0, 6).join(' | '))
  // Der alte Weg (verantwortliche.set_verantwortliche) darf von der
  // Gruppenseite nicht mehr benutzt werden (Karte, Punkt 4).
  assert.equal(aufrufe.some(([m]) => /verantwortliche\.set_verantwortliche/.test(m)), false,
    'die Gruppenseite schreibt noch über den alten Endpunkt')

  // zurück auf die Übersicht
  window.location.hash = '#/gruppe/Chor'
  window.dispatchEvent(new window.HashChangeEvent('hashchange'))
  await warte(16)
  assert.ok(host.textContent.includes('Noten kopieren'),
    'Übersicht zeichnet nach dem Zurückwechseln nicht')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Die Rollenliste spricht NUR die Rechte-Endpunkte der Karte an
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: die Rollenliste nutzt get_personen_auswahl, nicht die Gruppenauswahl', async () => {
  const { meldungen } = await seiteMounten()
  window.location.hash = '#/gruppe/Chor/einstellungen'
  window.dispatchEvent(new window.HashChangeEvent('hashchange'))
  await warte(16)

  const methoden = aufrufe.map(([m]) => m)
  assert.ok(methoden.some((m) => /rechte\.get_gruppenrollen$/.test(m)),
    'get_gruppenrollen wurde nicht gerufen | ' + meldungen.slice(0, 4).join(' | '))
  // Der stille Fehler: `get_gruppe_mitglieder_auswahl` liefert `mitglied`,
  // nicht das KONTO — `ernenne_mv` wiese die Kennung ab.
  assert.equal(methoden.some((m) => /get_gruppe_mitglieder_auswahl$/.test(m)), false,
    'Personensuche läuft über get_gruppe_mitglieder_auswahl (liefert kein Konto)')
  // R-12c: die Namen kommen aus `get_gruppenrollen` — kein zweiter Weg über
  // die Personensuche (die diente nur zum Nachschlagen der Namen).
  assert.equal(methoden.some((m) => /rechte\.get_personen_auswahl$/.test(m)), false,
    'Namen werden weiterhin über get_personen_auswahl nachgeschlagen')
  // Der Anzeigename des Servers steht in der Liste.
  assert.ok(window.document.body.textContent.includes('Rebekka Fink'),
    'Anzeigename aus get_gruppenrollen fehlt')
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Gegenprobe: Mitglied OHNE Rechte sieht den Reiter nicht (fail closed)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: ohne Serverrechte erscheint der Reiter „Einstellungen“ nicht', async () => {
  ueberschreibungen = {
    'get_gruppe_detail$': {
      ...GRUPPE_ANTWORT,
      verantwortliche: [],
      rechte: { verwalten: false, rollen: false, ankuendigung_anlegen: false, aufgabe_anlegen: false },
    },
    'rechte\\.get_gruppenrollen$': {
      rollen: [], darf_hv_mv_ernennen: false, darf_verwalten: false,
    },
  }
  try {
    const { host, meldungen } = await seiteMounten()
    const reiter = [...host.querySelectorAll('.dk-ui-reiter-punkt')].map((e) => e.textContent.trim())
    assert.ok(!reiter.includes('Einstellungen'),
      'Reiter „Einstellungen“ trotz fehlender Rechte sichtbar | ' + meldungen.slice(0, 4).join(' | '))
    // Die Übersicht bleibt bedienbar.
    assert.ok(host.textContent.includes('Details'), 'Übersicht fehlt ohne Rechte')

    // Auch der direkte Weg über die Adresse zeigt keine Rollenliste.
    window.location.hash = '#/gruppe/Chor/einstellungen'
    window.dispatchEvent(new window.HashChangeEvent('hashchange'))
    await warte(16)
    assert.equal(host.querySelectorAll('.gr-rollen').length, 0,
      'Rollenliste erscheint, obwohl der Server keine Rechte meldet')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Ladezustand: Skelett statt leerer/erfundener Übersicht (Review 1, OP-UI-19)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: während des Ladens steht das Skelett, nicht die leere Übersicht', async () => {
  ueberschreibungen = {
    'get_gruppe_detail$': new Promise((fertig) => setTimeout(() => fertig(GRUPPE_ANTWORT), 1500)),
  }
  try {
    const { host, meldungen } = await seiteMounten({ warteMs: 0 })
    // über die Schwelle von useLadeSkelett (300 ms), die Antwort braucht 1,5 s
    await new Promise((l) => setTimeout(l, 450))
    assert.equal(host.querySelectorAll('.dk-ui-skelett:not(.is-kurz)').length, 1,
      'kein Ladeskelett | ' + meldungen.slice(0, 4).join(' | '))
    assert.equal(host.querySelectorAll('.grup-grid').length, 0,
      'die Übersicht zeichnet schon während des Ladens (erfundene „0 Mitglieder“)')

    await new Promise((l) => setTimeout(l, 1500))
    await warte(6)
    assert.equal(host.querySelectorAll('.grup-grid').length, 1, 'Übersicht fehlt nach dem Laden')
    assert.equal(host.querySelectorAll('.dk-ui-skelett:not(.is-kurz)').length, 0,
      'Skelett bleibt nach dem Laden stehen')
  } finally {
    ueberschreibungen = {}
  }
})

test('UI-R1: bei einem Ladefehler steht nur der Hinweis, keine Übersicht', async () => {
  // EIN Versprechen für alle Aufrufe — sonst bliebe jede weitere Ablehnung
  // unbehandelt (der zweite Aufruf der Seite sieht sie nicht mehr).
  ueberschreibungen = { 'get_gruppe_detail$': abweisen() }
  try {
    const { host } = await seiteMounten()
    await warte(20)
    assert.equal(host.querySelectorAll('.grup-grid').length, 0,
      'die Übersicht zeichnet zusätzlich unter dem Fehlerhinweis')
    const hinweis = host.querySelector('.dk-ui-hint--err')
    assert.ok(hinweis, 'kein Fehlerhinweis gezeichnet')
    // Der Hinweis sagt, WAS nicht ging — nicht bloß „irgendein Text steht da“.
    // Ein 403 heißt: es fehlt die Berechtigung (Fehlerkatalog).
    assert.match(hinweis.textContent, /Berechtigung/,
      'der Fehlerhinweis nennt nicht die Ursache: ' + hinweis.textContent.trim())
    assert.ok(!host.textContent.includes('Noten kopieren'),
      'der Seiteninhalt steht trotz Fehler da (erfundene Nullen)')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 8 · Untergruppen-Seite: nur GL dieser Untergruppe (Review 2)
// ══════════════════════════════════════════════════════════════════════════

/** Antwort für die UNTERGRUPPE „Sopran“ — die Obergruppe ist „Chor“. */
const UNTERGRUPPE_ANTWORT = {
  untergruppe: {
    name: 'UG-1', untergruppenname: 'Sopran', gruppe: 'Chor', gruppe_name: 'Chor',
    status: 'Aktiv', beschreibung: 'Hohe Stimmen.',
  },
  mitglieder: [],
  verantwortliche: [{ email: 'samuel@example.org', name: 'Samuel Fink' }],
  aufgaben: [], ankuendigungen: [], wiki_artikel: [],
  is_member: true,
  rechte: { verwalten: true, rollen: false, ankuendigung_anlegen: true, aufgabe_anlegen: true },
}

test('UI-R1: auf einer Untergruppen-Seite holt die Rollenliste die OBERGRUPPE', async () => {
  ueberschreibungen = {
    'get_gruppe_detail$': UNTERGRUPPE_ANTWORT,
    'get_gruppe_termine$': { termine: [] },
    'rechte\\.get_gruppenrollen$': {
      rollen: [
        { benutzer: null, rolle: 'HV', untergruppe: null, name: 'Rebekka Fink', untergruppe_name: null },
        { benutzer: null, rolle: 'GL', untergruppe: 'UG-1', name: 'Samuel Fink', untergruppe_name: 'Sopran' },
        { benutzer: null, rolle: 'GL', untergruppe: 'UG-2', name: 'Jonas Jung', untergruppe_name: 'Alt' },
      ],
      darf_hv_mv_ernennen: true,
      darf_verwalten: true,
    },
  }
  try {
    const { host, meldungen } = await seiteMounten({ hash: '#/gruppe/UG-1/einstellungen', warteMs: 40 })
    const text = host.textContent
    assert.ok(!text.includes('Jonas Jung'), 'GL einer FREMDEN Untergruppe erscheint')
    assert.equal(host.querySelectorAll('section[data-rolle="HV"]').length, 0,
      'auf einer Untergruppen-Seite steht ein HV-Abschnitt')
    assert.equal(host.querySelectorAll('section[data-rolle="MV"]').length, 0,
      'auf einer Untergruppen-Seite steht ein MV-Abschnitt')

    // UI-R1b: Die Rollenliste einen Moment später gelesen — die Obergruppe
    // steht erst nach dem Detail-Laden fest, und eine veraltete Antwort darf
    // die richtige nicht ersetzen.
    await warte(20)
    const rollenAufrufe = aufrufe.filter(([m]) => /rechte\.get_gruppenrollen$/.test(m))
    assert.ok(rollenAufrufe.length > 0, 'get_gruppenrollen wurde nicht gerufen | ' + meldungen.slice(0, 4).join(' | '))
    assert.equal(rollenAufrufe.at(-1)[1].gruppe, 'Chor',
      'die Rollenliste fragt die UNTERGRUPPE statt der Obergruppe')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 9 · Deeplink ohne Rechte fällt auf die Übersicht zurück (Review 3)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1: #/…/einstellungen ohne Rechte fällt auf die Übersicht zurück', async () => {
  ueberschreibungen = {
    'get_gruppe_detail$': {
      ...GRUPPE_ANTWORT,
      verantwortliche: [],
      rechte: { verwalten: false, rollen: false, ankuendigung_anlegen: false, aufgabe_anlegen: false },
    },
    'rechte\\.get_gruppenrollen$': { rollen: [], darf_hv_mv_ernennen: false, darf_verwalten: false },
  }
  try {
    // UI-R1c: MIT dem echten Router. `history.replaceState` schrieb nur die
    // Adresszeile um, ohne `hashchange` auszulösen — der Router behielt
    // `…#/einstellungen`, `aktiverReiter` blieb „einstellungen“, und gezeichnet
    // wurde die leere Karte „Rollen der Gruppe“ statt der Übersicht. Belegt
    // wird darum der ganze Weg: Adresse, gezeichneter Inhalt, Router-Stand.
    const { host, ersetzt } = await seiteMitVerlaufsMessung({
      hash: '#/gruppe/Chor/einstellungen', warteMs: 40, router: true,
    })
    const text = host.textContent
    assert.ok(text.includes('Details'), 'Übersicht fehlt | ' + meldungenVon(host))
    // Der Inhalt der ÜBERSICHT (Aufgabenliste) steht da …
    assert.ok(text.includes('Noten kopieren'),
      'der Inhalt der Übersicht fehlt (leere Karte statt Übersicht) | ' + meldungenVon(host))
    // … und die Rollen-Karte des verworfenen Reiters NICHT.
    assert.ok(!text.includes('Rollen der Gruppe'),
      'die Rollen-Karte wird weiter gezeichnet (aktiverReiter blieb „einstellungen“)')
    assert.equal(window.location.hash, '#/gruppe/Chor',
      'die Adresse zeigt weiter den Reiter ohne Rechte (leere Karte)')
    // UI-R1b/UI-R1c: Die Adresse wird ERSETZT — kein eigener Verlaufseintrag,
    // sonst hätte die Seite ihre eigene Zurück-Falle. `location.replace` ist in
    // jsdom nicht abhörbar, darum am Quelltext geprüft.
    const quelltext = readFileSync(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'), 'utf8')
    assert.match(quelltext, /window\.location\.replace\(`#\/gruppe\/\$\{gruppeId\.value\}`\)/,
      'der Rückfall nutzt nicht `location.replace(…)`')
    assert.ok(!/reiter !== 'einstellungen'\) return[\s\S]{0,300}navigate\(/.test(quelltext),
      'der Rückfall schreibt die Adresse per `navigate()` (neuer Verlaufseintrag)')
    // `history.replaceState` (der frühere Weg) löst kein `hashchange` aus und
    // wird nicht mehr benutzt.
    assert.equal(ersetzt, false,
      'der Rückfall geht noch über `history.replaceState` (löst kein hashchange aus)')
    // UI-R1c: Der ROUTER muss nachgezogen haben — `currentHash` ist die Route,
    // die der Router angenommen hat.
    assert.equal(routerModul.currentHash.value, '#/gruppe/Chor',
      'der Router steht noch auf dem Reiter ohne Rechte (kein hashchange ausgelöst)')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 10 · UI-R1b: stilles Nachladen — der Inhalt bleibt stehen (Review 3)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1b: nach einer Aktion bleibt der Inhalt stehen (kein Zusammenfallen, Fokus bleibt)', async () => {
  const { host, app, meldungen } = await seiteMounten({ warteMs: 40 })
  try {
    // Vorbedingung: die Übersicht IST da (Inhalt, nicht Skelett), und ihre
    // Karte „Details“ ist auf Bearbeiten gestellt — der Fokus steht in deren
    // Namensfeld. Eine Aktion von hier (`saveDesc`) lädt still nach.
    assert.ok(host.textContent.includes('Noten kopieren'),
      'Vorbedingung: Übersicht fehlt | ' + meldungen.slice(0, 6).join(' | '))
    // Der Bearbeiten-Knopf ist der stille Knopf (ohne Text) in der Karte „Details“.
    const detailKarte = [...host.querySelectorAll('.dk-ui-card')]
      .find((karte) => karte.textContent.includes('Beschreibung'))
    // Der Bearbeiten-Weg ist die Methode `startEditDesc` der Seite: `canManage`
    // hängt an der SITZUNG (Administrator) — eine feste E-Mail im Testlauf darf
    // davon nicht abhängen. Der echte Klick auf den Stift ist im Browser
    // abgenommen; hier zählt der Weg (Aktion → stilles Nachladen).
    assert.ok(detailKarte, 'Vorbedingung: Karte „Details“ fehlt | ' + meldungen.slice(0, 6).join(' | '))
    komponente(host).setupState.startEditDesc()
    await warte(6)

    const eingabe = host.querySelector('.grup-formular input')
    assert.ok(eingabe, 'Vorbedingung: Namensfeld der Bearbeitung fehlt')
    eingabe.focus()
    eingabe.value = 'Chor (neu)'
    eingabe.dispatchEvent(new window.Event('input', { bubbles: true }))
    await warte(4)

    // Jetzt kommt die Antwort LANGSAM zurück (deutlich über der Skelett-Schwelle):
    // beim sichtbaren Laden stünde in dieser Zeit das Skelett, der Inhalt wäre
    // weg — und mit ihm das Feld samt Fokus.
    ueberschreibungen = {
      'get_gruppe_detail$': new Promise((fertig) => setTimeout(() => fertig({
        ...GRUPPE_ANTWORT, gruppe: { ...GRUPPE_ANTWORT.gruppe, gruppenname: 'Chor (neu)' },
      }), 900)),
    }

    const speichern = [...host.querySelectorAll('.grup-formular button')]
      .find((b) => b.textContent.trim() === 'Speichern')
    assert.ok(speichern, 'Knopf „Speichern“ fehlt')
    speichern.click()

    // `saveDesc` ruft `fetchGruppe()` OHNE Nachlade-Kennzeichen — der stärkste
    // Fall: allein das Merkmal `geladen` verhindert hier das Zusammenfallen.
    await new Promise((l) => setTimeout(l, 550))
    assert.equal(host.querySelectorAll('.grup-grid').length, 1,
      'während des Nachladens ist der Inhalt aus dem DOM gefallen (Skelett statt Inhalt)')
    assert.equal(host.querySelectorAll('.dk-ui-skelett:not(.is-kurz)').length, 0,
      'das Ladenskelett erscheint beim NACHLADEN')
    assert.ok(host.textContent.includes('Noten kopieren'), 'die Aufgabenliste ist während des Nachladens verschwunden')
    // Kein Zusammenfallen: die Übersicht steht, die Seite ist nicht gescrollt
    // worden und der Seitentitel bleibt stehen (das frühere Verhalten hätte
    // den Inhalt bis zur Antwort ganz entfernt).
    assert.ok(host.textContent.includes('Chor'), 'der Seitenkopf ist während des Nachladens verschwunden')
    assert.equal(window.scrollY, 0, 'die Seite ist beim Nachladen gesprungen')

    await new Promise((l) => setTimeout(l, 500))
    await warte(10)
    assert.ok(host.textContent.includes('Chor (neu)'), 'der neue Name steht nach dem stillen Nachladen nicht da')
    assert.equal(host.querySelectorAll('.grup-grid').length, 1, 'Inhalt fehlt nach dem Nachladen')

    // … und ein Nachladen ÜBER DEN STILLEN WEG (`nachladen`, wie nach jeder
    // Aktion in den Karten) lässt eine offene Bearbeitung samt Fokus stehen.
    komponente(host).setupState.startEditDesc()
    await warte(4)
    const feld2 = host.querySelector('.grup-formular input')
    assert.ok(feld2, 'Vorbedingung: Bearbeitung offen')
    feld2.focus()
    const vorher = host.querySelector('.grup-formular input')
    await komponente(host).setupState.nachladen()
    await warte(10)
    assert.equal(host.querySelector('.grup-formular input'), vorher,
      'das stille Nachladen hat die offene Bearbeitung ausgetauscht (Fokus weg)')
    assert.equal(window.document.activeElement, feld2, 'der Fokus ging beim stillen Nachladen verloren')
    app.unmount()
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 11 · UI-R1b: EIN Abruf je Rollen-Aktion (nur stille Wege, keine Suche)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1b: eine Rollen-Aktion lädt einmal nach und sucht niemanden', async () => {
  // MV mit Konto, damit der „Entfernen“-Knopf erscheint (nur HV darf ihn nutzen).
  const rollenMitMv = {
    'rechte\\.get_gruppenrollen$': {
      rollen: [
        { benutzer: 'rebekka.fink@example.org', rolle: 'HV', untergruppe: null, name: 'Rebekka Fink', untergruppe_name: null },
        { benutzer: 'melanie.mustermann@example.org', rolle: 'MV', untergruppe: null, name: 'Melanie Mustermann', untergruppe_name: null },
      ],
      darf_hv_mv_ernennen: true,
      darf_verwalten: true,
    },
  }
  try {
    const { host, meldungen } = await seiteMounten({ warteMs: 30, antworten: rollenMitMv })
    await zumReiter(host)
    const entfernen = [...host.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Entfernen')
    assert.ok(entfernen, 'Vorbedingung: Knopf „Entfernen“ fehlt | ' + meldungen.slice(0, 4).join(' | '))

    const rollenAufrufeVorher = aufrufe.filter(([m]) => /rechte\.get_gruppenrollen$/.test(m)).length

    // Der Server antwortet OHNE die MV — wie nach einem echten Entfernen.
    ueberschreibungen['rechte\\.entferne_mv$'] = { success: true }
    ueberschreibungen['rechte\\.get_gruppenrollen$'] = {
      rollen: [
        { benutzer: 'rebekka.fink@example.org', rolle: 'HV', untergruppe: null, name: 'Rebekka Fink', untergruppe_name: null },
      ],
      darf_hv_mv_ernennen: true,
      darf_verwalten: true,
    }
    const klickIndex = aufrufe.length
    entfernen.click()
    await warte(60)

    // Nur die Aufrufe NACH dem Klick zählen (vorher steht der ganze Aufbau da).
    const methoden = aufrufe.slice(klickIndex).map(([m]) => m)
    const rollenAufrufe = methoden.filter((m) => /rechte\.get_gruppenrollen$/.test(m)).length
    assert.equal(rollenAufrufe, 1,
      `je Aktion EIN get_gruppenrollen (war ${rollenAufrufe}; vorher: laden() UND Remount)`)
    const detailAufrufe = methoden.filter((m) => /get_gruppe_detail$/.test(m)).length
    assert.equal(detailAufrufe, 1,
      `je Aktion EIN get_gruppe_detail (war ${detailAufrufe})`)
    // Die Personensuche gehört NUR zum Öffnen einer Auswahlliste — beim
    // Reiterwechsel holt sie der Remount der Karte, nicht die Aktion.
    assert.equal(methoden.some((m) => /rechte\.get_personen_auswahl$/.test(m)), false,
      'die Personensuche läuft bei einer Rollen-Aktion mit (Ergebnis wird verworfen)')
    assert.ok(!host.textContent.includes('Melanie Mustermann'),
      'die entfernte MV steht nach dem stillen Nachladen noch in der Liste')
    assert.ok(rollenAufrufeVorher >= 1, 'Vorbedingung: das erste Laden hat die Rollen geholt')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 12 · UI-R1b: Namen statt Kennung in der Erfolgsmeldung (Untergruppen-Seite)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1b: auf der Untergruppen-Seite nennt die Meldung den Namen der Untergruppe', async () => {
  // Tippen in die GL-Suche liefert die Person; die Auswahl löst `ernenne_gl` aus.
  const untergruppeWelt = {
    'get_gruppe_detail$': UNTERGRUPPE_ANTWORT,
    'get_gruppe_termine$': { termine: [] },
    'rechte\\.get_gruppenrollen$': {
      rollen: [
        { benutzer: null, rolle: 'HV', untergruppe: null, name: 'Rebekka Fink', untergruppe_name: null },
        { benutzer: null, rolle: 'GL', untergruppe: 'UG-1', name: 'Samuel Fink', untergruppe_name: 'Sopran' },
      ],
      darf_hv_mv_ernennen: true,
      darf_verwalten: true,
    },
    'rechte\\.get_personen_auswahl$': {
      personen: [{ benutzer: 'neu@example.org', name: 'Neue Person' }],
    },
    'rechte\\.ernenne_gl$': { success: true, bestand: false },
  }
  try {
    const { host, meldungen } = await seiteMounten({ hash: '#/gruppe/UG-1', warteMs: 30, antworten: untergruppeWelt })
    await zumReiter(host)

    // Die sichtbare Beschriftung des Suchfelds (nicht nur ein Platzhalter).
    assert.ok(host.textContent.includes('Gruppenleitung hinzufügen'),
      'die sichtbare Beschriftung „Gruppenleitung hinzufügen“ fehlt | '
      + meldungen.slice(0, 4).join(' | '))
    // UI-R1c: derselbe Text ist der ZUGÄNGLICHE NAME des Eingabefelds.
    // `MitgliedAuswahl` nimmt die Kennung aus dem Feld-Slot nicht an, das
    // `<label for>` von `DkField` zeigte ins Leere — ohne eigenes `aria-label`
    // wäre der Name nur der Platzhalter („Name eingeben …“).
    const glFeld = host.querySelector('.dk-ma-input')
    assert.ok(glFeld, 'Suchfeld der Gruppenleitung fehlt | ' + meldungen.slice(0, 4).join(' | '))
    assert.equal(glFeld.getAttribute('aria-label'), 'Gruppenleitung hinzufügen',
      'der zugängliche Name des GL-Suchfelds ist nicht die sichtbare Beschriftung')
    // Die sichtbare Beschriftung hängt an einem <label>, das auf KEIN Element
    // zeigt (`for` ohne Ziel) — darum trägt das Feld den Namen selbst.
    const beschriftung = [...host.querySelectorAll('label')]
      .find((l) => l.textContent.trim() === 'Gruppenleitung hinzufügen')
    assert.ok(beschriftung, 'die sichtbare Beschriftung ist kein <label>')
    assert.equal(host.querySelector(`#${CSS.escape(beschriftung.getAttribute('for') || '')}`), null,
      'das <label for> zeigt inzwischen auf ein Element — dann wäre das aria-label überflüssig')
    // Die eigene GL dieser Untergruppe steht da.
    assert.ok(host.textContent.includes('Samuel Fink'),
      'die eigene Gruppenleitung wird auf der Untergruppen-Seite nicht angezeigt')

    const feld = host.querySelector('.dk-ma-input')
    assert.ok(feld, 'Suchfeld für die Gruppenleitung fehlt')
    feld.focus()
    feld.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }))
    feld.value = 'Neu'
    feld.dispatchEvent(new window.Event('input', { bubbles: true }))
    await new Promise((l) => setTimeout(l, 320))
    await warte(12)

    const treffer = [...host.querySelectorAll('.dk-ma-eintrag')]
      .find((li) => li.textContent.includes('Neue Person'))
    assert.ok(treffer, 'Vorbedingung: Personensuche zeigt keinen Treffer | ' + meldungen.slice(0, 4).join(' | '))
    treffer.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true }))
    await warte(30)

    const meldungenText = [...host.querySelectorAll('.dk-ui-toast, .toast, .dk-toast')]
      .map((e) => e.textContent).join(' ')
    const gezeigt = meldungenText || host.textContent
    assert.ok(gezeigt.includes('Sopran'),
      'die Erfolgsmeldung nennt nicht den Namen der Untergruppe')
    assert.ok(!gezeigt.includes('leitet jetzt UG-1'),
      'die Erfolgsmeldung nennt die Kennung statt des Namens')
  } finally {
    ueberschreibungen = {}
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 13 · UI-R1b: ein gescheitertes STILLES Nachladen nimmt den Inhalt nicht weg
// ══════════════════════════════════════════════════════════════════════════

test('UI-R1b: scheitert ein stilles Nachladen, bleibt der Inhalt stehen (Meldung statt Seitenfehler)', async () => {
  const { host, meldungen } = await seiteMounten({ warteMs: 30 })
  try {
    assert.ok(host.textContent.includes('Noten kopieren'),
      'Vorbedingung: Übersicht fehlt | ' + meldungen.slice(0, 6).join(' | '))
    assert.equal(host.querySelectorAll('.grup-grid').length, 1, 'Vorbedingung: Übersicht steht')

    // Das Nachladen scheitert (403) — der Inhalt ist aber schon da.
    ueberschreibungen = { 'get_gruppe_detail$': abweisen() }
    await komponente(host).setupState.nachladen()
    await warte(10)

    assert.equal(host.querySelectorAll('.grup-grid').length, 1,
      'das gescheiterte stille Nachladen hat den Inhalt aus dem DOM genommen')
    assert.equal(host.querySelectorAll('.dk-ui-hint--err').length, 0,
      'ein stilles Nachladen zeigt den SEITEN-Fehlerhinweis (Inhalt weg)')
    // Meldungen hängen am Dokument (`useToast` legt seinen eigenen Behälter
    // an), nicht im Baum der Seite.
    const gezeigt = [...window.document.querySelectorAll('.diakonos-toast')]
      .map((e) => e.textContent).join(' ')
    assert.match(gezeigt, /Berechtigung/,
      'der Fehler des stillen Nachladens wird nicht gemeldet: ' + gezeigt)
  } finally {
    ueberschreibungen = {}
  }
})
