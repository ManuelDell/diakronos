/**
 * UI-R8c — ⓘ an den Gruppenrollen HV, MV und GL (Reiter „Rollen“ der
 * Gruppeneinstellungen).
 *
 * Geprüft wird am ECHTEN Bauteil (`components/gruppen/RollenEinstellungen.vue`,
 * jsdom-Mount wie uir9d/uir9e, `apiCall` über ein Stellvertreter-Modul — kein
 * Netz):
 *
 *   1. Erklärung geladen → genau drei ⓘ (HV, MV, GL), alle an der
 *      BLOCK-ÜBERSCHRIFT (`.gr-rollen-kopf`), mit dem kurzen Rollennamen im
 *      `aria-label`; ein Klick öffnet das Feld mit dem `kurz`-Text AUS DER
 *      QUELLE.
 *   2. Leerzustand (keine HV/MV eingetragen) → trotzdem drei ⓘ.
 *   3. Mehrere MV → weiterhin genau EIN MV-ⓘ (am Kopf, nicht je Zeile).
 *   4. Quelle wirft (Ladefehler) → KEIN ⓘ (RrInfo zeigt ohne Erklärung nichts),
 *      kein Fehlerbanner, und der Block hat so viele Kindelemente wie auf
 *      `main` (keine leeren Reste), die Rollenliste steht weiter.
 *   5. Untergruppen-Seite (HV/MV-Blöcke unsichtbar) → nur das GL-ⓘ.
 *
 * Auf dem `main`-Stand vor dieser Karte gibt es in der Datei kein `RrInfo` —
 * die ⓘ-Fälle sind dort rot.
 *
 * Lauf: node --test tests/uir8c-*.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')

// ── Browser-Ersatz: jsdom, dann Vue + Bauteile laden ────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
})
const { window: W } = dom
for (const name of ['window', 'document', 'HTMLElement', 'Element', 'Node', 'SVGElement',
  'HTMLInputElement', 'HTMLButtonElement', 'Text', 'Comment', 'DocumentFragment',
  'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'MutationObserver',
  'CustomEvent', 'Event', 'MouseEvent', 'KeyboardEvent', 'localStorage', 'sessionStorage']) {
  if (W[name] === undefined) continue
  try {
    globalThis[name] = W[name]
  } catch (_) {
    Object.defineProperty(globalThis, name, { value: W[name], configurable: true, writable: true })
  }
}
if (W.navigator) {
  try {
    Object.defineProperty(globalThis, 'navigator', { value: W.navigator, configurable: true })
  } catch (_) { /* Node-Behelf bleibt */ }
}
globalThis.window = W
W.__DIakonosBOOT = { csrf_token: 'x', modules: ['gruppen'], user_email: 'ich@example.org' }
globalThis.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {} })
W.matchMedia = globalThis.matchMedia
Element.prototype.scrollIntoView = function () {}

// Nur der Takt wird ersetzt: ein Prüfintervall hielte den Prozess sonst am
// Leben (dieselbe Technik wie uir9e).
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}
// `useLadeSkelett` schiebt den Platzhalter über einen Timer an — im Test soll
// sofort die Liste stehen, nicht erst nach 300 ms.
const echterTimeout = globalThis.setTimeout
globalThis.setTimeout = (fn, ms, ...rest) => echterTimeout(fn, 0, ...rest)

const VUE_URL = import.meta.resolve('vue')
const Vue = await import(VUE_URL)
// Vue MUSS vor dem Import des Bauteils geladen sein: das SFC bindet
// `vue`-Reaktivität (`watch`, `ref`) aus demselben Modul. Eine spätere Instanz
// (hier) hätte einen anderen `watch`-Sammler — der `immediate`-Wächter des
// Ladeskeletts lief dann ins Leere und die Rollenliste blieb im Skelett-Zustand.

// ── Stellvertreter: `apiCall` ohne Netz, Toast ohne Oberfläche ─────────────
const TMP = mkdtempSync(join(tmpdir(), 'uir8c-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
// Zustand über "process": die Testdatei und dieses Modul laufen in GETRENNTEN
// Kontexten (globalThis ist dort NICHT dasselbe Objekt), process ist es.
process.__API_STUB ||= { aufrufe: [], antworten: {} }
export function setzeAntworten(neu) { process.__API_STUB.antworten = { ...neu } }
export async function apiCall(methode, args) {
  const speicher = process.__API_STUB
  speicher.aufrufe.push([methode, args])
  const kurz = String(methode).split('.').pop()
  const antworten = speicher.antworten
  const wert = typeof antworten[kurz] === 'function' ? antworten[kurz](args) : antworten[kurz]
  if (wert instanceof Error) throw wert
  return wert === undefined ? { success: true } : wert
}
export class AuditConfirmationRequired extends Error {}
export async function apiAntwortPruefen(res) { return res && typeof res.json === 'function' ? res.json() : res }
export function pruefeSitzungsAntwort() {}
export function mitAntwort(wert) { return wert }
export async function apiGet(methode, args) { return apiCall(methode, args) }
`)
writeFileSync(join(STUB, 'toast.mjs'), `
export const toasts = []
export function showToast(text, art) { toasts.push([text, art]) }
`)

const STELLVERTRETER = new Map([
  [join(SRC, 'composables/useApi'), join(STUB, 'api.mjs')],
  [join(SRC, 'composables/useToast'), join(STUB, 'toast.mjs')],
])

const cache = new Map()

/**
 * Stellvertreter auch dann, wenn der Import mit `.js`/`.mjs`/`.vue` endet —
 * der Schlüssel der Liste trägt KEINE Endung (`…/useApi`), ein aufgelöster
 * Pfad schon (`…/useApi.js`).
 */
function stellvertreterFuer(abs) {
  return STELLVERTRETER.get(String(abs).replace(/\.(js|mjs|vue)$/, '')) || null
}



function kompilieren(abs) {
  const ersatz = stellvertreterFuer(abs)
  if (ersatz) return ersatz
  if (cache.has(abs)) return cache.get(abs)
  // Schlüssel = PFAD unter `src/diakonos`, nicht der DATEINAME: es gibt
  // mehrere `RollenEinstellungen.vue`/`*.mjs` gleichen Namens, und der
  // Modul-Import-Cache gäbe sonst das falsche Bauteil zurück.
  const name = String(abs).replace(String(SRC), '').replace(/^[/\\]/, '')
  // Nur `.vue` wird übersetzt. Alles andere (`.mjs`, `.js`, Stellvertreter)
  // geht unverändert weiter — sonst landete ein `.js`-Modul im SFC-Zweig und
  // der Parser warf „At least one <template> or <script> is required“.
  if (!abs.endsWith('.vue')) {
    // Import-Ziel wie Node auflösen (`./x` → `x.js`). Danach die Importe des
    // Moduls GENAU WIE BEI DEN SFC umschreiben — sonst ginge `useApi` (echtes
    // `fetch`) an seinem Stellvertreter vorbei. Die Datei selbst bleibt an
    // ihrem Ort: ein umgeschriebenes `.js` muss Node laden können.
    const datei = abs.endsWith('.js') || abs.endsWith('.mjs')
      ? abs
      : [abs + '.js', abs + '.mjs'].find((k) => existsSync(k)) || abs
    let text = readFileSync(datei, 'utf8')
    // `vue` ebenso auf DENSELBEN Modulpfad ziehen wie bei den SFC (`VUE_URL`);
    // sonst lüde die Kopie unter `TMP` ein zweites Vue und damit einen zweiten
    // Reaktivitäts-Sammler.
    text = text.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
    text = text.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
      if (!spec.startsWith('.')) return v // Paket-Import bleibt
      return `from '${pathToFileURL(kompilieren(resolve(dirname(abs), spec))).href}'`
    })
    const zielDatei = resolve(TMP, name.replace(/[\\/]/g, '__'))
    writeFileSync(zielDatei, text)
    cache.set(abs, zielDatei)
    return zielDatei
  }
  const dateiname = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename: dateiname })
  assert.deepEqual(errors, [], dateiname + ': SFC-Struktur')
  // Eigene `id` je Datei (nicht der Dateiname): `useId()`/`_id` der Vorlage
  // hängt daran, und zwei Dateien desselben Namens bekämen sonst dieselbe.
  const sfcId = name.replace(/[^\w]/g, '-')
  const script = compileScript(descriptor, { id: sfcId })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: dateiname,
    id: sfcId,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], dateiname + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (!spec.startsWith('.')) return v // Paket-Import bleibt
    const ziel = resolve(dirname(abs), spec)
    // IMMER über `kompilieren` — auch `.js`/`.mjs`: nur dort wird der
    // Stellvertreter eingesetzt. Am Stellvertreter vorbei riefe das echte
    // `useApi.js` sein `fetch`.
    return `from '${pathToFileURL(kompilieren(ziel)).href}'`
  })
  const ziel = resolve(TMP, name.replace(/[\\/]/g, '__').replace(/\.vue$/, '') + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))
async function warten(bedingung, versuche = 80) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, 10))
  }
  return bedingung()
}

// Der api-Stellvertreter läuft in einem EIGENEN Modulkontext — `process` ist
// der gemeinsame Träger (wie uir9e).
const setzeAntworten = (neu) => {
  const speicher = (process.__API_STUB ||= {})
  speicher.aufrufe = Array.isArray(speicher.aufrufe) ? speicher.aufrufe : []
  speicher.antworten = { ...neu }
}
const aufrufe = () => process.__API_STUB?.aufrufe || []

async function mounten(datei, eigenschaften = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    setup: () => ({ p: eigenschaften }),
    render: () => Vue.h(bauteil, eigenschaften),
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler && fehler.stack ? fehler.stack : fehler))
  app.mount(host)
  await tick()
  return {
    host,
    app,
    warnungen,
    weg: () => { try { app.unmount() } catch (_) { /* weg */ } host.remove() },
  }
}

const txt = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')

// ── Die Quelle: `api.rechte.get_rollen_erklaerung` → `gruppenrollen` ────────
// Wortlaut wie im Backend (`backend/src/diakronos_app/rechte/erklaerung.py`,
// GRUPPENROLLEN). Der Test prüft, dass GENAU DIESER Text im Feld steht — es
// gibt keine zweite Fassung im Frontend.
const GRUPPENROLLEN = {
  HV: {
    titel: 'Hauptverantwortliche(r) (HV)',
    kurz: 'Leitet die Gruppe. Genau eine Person je Gruppe.',
    darf: ['alles, was die Module der Gruppe erlauben (anlegen, bearbeiten, prüfen)',
      'Mitverantwortliche (MV) ernennen und entfernen'],
    darf_nicht: ['Module der Gruppe ändern (macht der Administrator)'],
  },
  MV: {
    titel: 'Mitverantwortliche(r) (MV)',
    kurz: 'Darf alles wie die HV — außer HV und MV ernennen.',
    darf: ['alles, was die Module der Gruppe erlauben'],
    darf_nicht: ['HV oder MV ernennen'],
  },
  GL: {
    titel: 'Gruppenleitung (GL, Untergruppe)',
    kurz: 'Leitet eine Untergruppe; was an die Gruppe oder Gemeinde geht, prüfen zuerst HV/MV.',
    darf: ['Kalender und Inhalte der Untergruppe anlegen und pflegen'],
    darf_nicht: ['in der Hauptgruppe direkt schreiben'],
  },
}
const QUELLE = { success: true, gruppenrollen: GRUPPENROLLEN }

// Die Block-Kennungen im Bauteil (`data-rolle`) — je Block EIN ⓘ am Kopf.
const BLOCK = { HV: 'HV', MV: 'MV', GL: 'GL' }

/** Antwort von `get_gruppenrollen` — eine Person je Rolle (HV, MV, GL). */
const ROLLEN = {
  success: true,
  rollen: [
    { benutzer: 'rebekka@example.org', rolle: 'HV', untergruppe: null, untergruppe_name: null, name: 'Rebekka Fink' },
    { benutzer: 'mira@example.org', rolle: 'MV', untergruppe: null, untergruppe_name: null, name: 'Mira Mit' },
    { benutzer: 'jonas@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Jonas Jung' },
  ],
  darf_hv_mv_ernennen: true,
  darf_verwalten: true,
}

/** Mehrere MV — der ⓘ darf davon NICHT mehr werden. */
const ROLLEN_VIELE_MV = {
  success: true,
  rollen: [
    { benutzer: 'rebekka@example.org', rolle: 'HV', untergruppe: null, untergruppe_name: null, name: 'Rebekka Fink' },
    { benutzer: 'mira@example.org', rolle: 'MV', untergruppe: null, untergruppe_name: null, name: 'Mira Mit' },
    { benutzer: 'nils@example.org', rolle: 'MV', untergruppe: null, untergruppe_name: null, name: 'Nils Neben' },
    { benutzer: 'olga@example.org', rolle: 'MV', untergruppe: null, untergruppe_name: null, name: 'Olga Ohne' },
    { benutzer: 'jonas@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Jonas Jung' },
  ],
  darf_hv_mv_ernennen: true,
  darf_verwalten: true,
}

/** Leerzustand: keine HV, keine MV — der ⓘ muss trotzdem stehen. */
const ROLLEN_LEER = {
  success: true,
  rollen: [
    { benutzer: 'jonas@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Jonas Jung' },
  ],
  darf_hv_mv_ernennen: true,
  darf_verwalten: true,
}

// Auf einer Untergruppen-Seite führt der Server nur die GL DIESER Untergruppe.
const ROLLEN_UNTER = {
  success: true,
  rollen: [
    { benutzer: 'jonas@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Jonas Jung' },
  ],
  darf_hv_mv_ernennen: true,
  darf_verwalten: true,
}
const UNTERGRUPPEN = [{ name: 'UG-K', anzeigename: 'Kinderchor' }]

/**
 * Der kurze Rollenname, der als `:name` an `RrInfo` geht. `RrInfo` beschriftet
 * seinen Knopf mit „Was bewirkt <Name>?“ — weicht der Titel der Erklärung ab,
 * stellt es beides nebeneinander. Mit dem KURZEN Namen klingt das aria-label
 * nicht mehr doppelt („Was bewirkt HV (Hauptverantwortliche(r) (HV))?“).
 */
const NAME = { HV: 'HV', MV: 'MV', GL: 'GL' }

/** Erwarteter Wortlaut je Rolle: `RrInfo` baut ihn aus `name` + Quellentitel. */
function erwartetesLabel(rolle) {
  return `Was bewirkt ${NAME[rolle]} (${GRUPPENROLLEN[rolle].titel})?`
}

/** Alle ⓘ-ähnlichen Knöpfe der Seite. */
const alleInfos = (host) => [...host.querySelectorAll('button[aria-label^="Was bewirkt"]')]

/** Die ⓘ innerhalb des Blocks einer Rolle. */
function infosImBlock(host, rolle) {
  const block = host.querySelector(`section[data-rolle="${BLOCK[rolle]}"]`)
  if (!block) return []
  return [...block.querySelectorAll('button[aria-label^="Was bewirkt"]')]
}

/** Der Knopf, dessen Feld gerade offen ist (aria-expanded="true"). */
const offen = (host) => [...host.querySelectorAll('button[aria-expanded="true"]')]

async function rollenBauteil({ erklaerung = QUELLE, antwort = ROLLEN, untergruppe = '', reparatur } = {}) {
  setzeAntworten({
    get_gruppenrollen: () => antwort,
    get_rollen_erklaerung: () => {
      if (reparatur) return reparatur()
      return erklaerung
    },
    get_personen_auswahl: { personen: [] },
  })
  const gemountet = await mounten('components/gruppen/RollenEinstellungen.vue', {
    gruppe: 'G-CHOR',
    untergruppe,
    untergruppen: UNTERGRUPPEN,
  })
  // Die Rollenliste ist da, sobald der Rollenname „Rebekka Fink“ steht; im
  // Leerzustand genügt der GL-Name beziehungsweise die Überschrift.
  const da = await warten(() => txt(gemountet.host).includes('Rebekka Fink')
    || txt(gemountet.host).includes('Jonas Jung')
    || txt(gemountet.host).includes('Gruppenleitung'))
  assert.ok(da, `Rollenliste nicht aufgebaut: ${gemountet.warnungen.join(' | ')}`)
  // Die Erklärung wird asynchron nachgeladen — einen Takt warten, bis die ⓘ
  // den Antwortwert gesehen haben.
  await warten(() => alleInfos(gemountet.host).length > 0 || aufrufe()
    .some(([m]) => String(m).endsWith('get_rollen_erklaerung')))
  await tick()
  return gemountet
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Erklärung geladen → drei ⓘ an den Block-Überschriften, kurzes aria-label
// ══════════════════════════════════════════════════════════════════════════
test('UI-R8c · HV, MV und GL tragen je ein ⓘ an der Block-Überschrift', async () => {
  const { host, weg } = await rollenBauteil()
  // Genau drei — kein vierter Knopf dieser Art („Mitglied“ steht hier nicht).
  assert.equal(alleInfos(host).length, 3, 'es sollen genau drei ⓘ stehen (HV, MV, GL)')
  for (const rolle of ['HV', 'MV', 'GL']) {
    const imBlock = infosImBlock(host, rolle)
    assert.equal(imBlock.length, 1, `kein ⓘ im Block ${rolle}`)
    // „An der Überschrift“ ist keine Auslegungssache: der ⓘ hängt direkt im
    // Kopf (`.gr-rollen-kopf`) neben dem `h4.gr-rollen-titel`.
    const kopf = imBlock[0].closest('.gr-rollen-kopf')
    assert.ok(kopf, `${rolle}: der ⓘ hängt nicht an der Block-Überschrift`)
    assert.ok(kopf.querySelector('h4.gr-rollen-titel'), `${rolle}: der Kopf trägt keinen Titel`)
    // NICHT in der Personenzeile (`.gr-rollen-eintrag`).
    assert.equal(imBlock[0].closest('.gr-rollen-eintrag'), null,
      `${rolle}: der ⓘ sitzt in einer Personenzeile statt an der Überschrift`)
    // Kurzer Name im aria-label, der Quellentitel in Klammern — nicht doppelt.
    assert.equal(imBlock[0].getAttribute('aria-label'), erwartetesLabel(rolle),
      `${rolle}: aria-label lautet „${imBlock[0].getAttribute('aria-label')}“`)
  }
  // Kein Rollenwissen im Frontend: das aria-label kommt aus Name + Quellentitel.
  assert.equal(txt(host).includes('Hauptverantwortliche(r) (HV)'), false,
    'der Quellentitel steht ungefragt im Seiten-Text (er gehört ins Erklärfeld)')
  // Die Quelle wird EINMAL je Bauteil geladen, nicht je Zeile.
  const ladungen = aufrufe().filter(([m]) => String(m).endsWith('get_rollen_erklaerung'))
  assert.equal(ladungen.length, 1, 'die Erklärung wird einmal je Bauteil geladen')
  weg()
})

test('UI-R8c · Klick auf das ⓘ öffnet den `kurz`-Text AUS DER QUELLE', async () => {
  const { host, weg } = await rollenBauteil()
  for (const rolle of ['HV', 'MV', 'GL']) {
    const [knopf] = infosImBlock(host, rolle)
    assert.ok(knopf, `kein ⓘ an ${rolle}`)
    assert.equal(knopf.getAttribute('aria-expanded'), 'false', `${rolle}: Feld ist schon offen`)
    knopf.click()
    await warten(() => offen(host).length === 1)
    // Das Feld ist Geschwister des ⓘ im selben Kopf — eine eigene volle Zeile
    // (kein absolut gesetztes Feld, kein zweiter Container).
    const panel = knopf.parentElement.querySelector(':scope > .rr-info-panel')
    assert.ok(panel, `${rolle}: Klick öffnet kein Erklärfeld im Block-Kopf`)
    assert.equal(panel.parentElement.classList.contains('gr-rollen-kopf'), true,
      `${rolle}: das Erklärfeld hängt nicht im Block-Kopf`)
    assert.ok(txt(panel).includes(GRUPPENROLLEN[rolle].kurz),
      `${rolle}: der \`kurz\`-Text der Quelle fehlt im Feld („${txt(panel)}“)`)
    // Kein Rollenwissen im Frontend: jede Zeile der Quelle erscheint wörtlich.
    for (const satz of GRUPPENROLLEN[rolle].darf) {
      assert.ok(txt(panel).includes(satz), `${rolle}: „darf“-Zeile aus der Quelle fehlt: ${satz}`)
    }
    // Schließen, damit das nächste ⓘ frisch gemessen wird.
    const zu = [...panel.querySelectorAll('button')].find((b) => txt(b) === 'Schließen')
    assert.ok(zu, `${rolle}: kein Schließen-Knopf im Feld`)
    zu.click()
    await warten(() => offen(host).length === 0)
  }
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Leerzustand (keine HV/MV) → trotzdem drei ⓘ
// ══════════════════════════════════════════════════════════════════════════
test('UI-R8c · ohne eingetragene HV/MV stehen trotzdem drei ⓘ', async () => {
  const { host, weg } = await rollenBauteil({ antwort: ROLLEN_LEER })
  assert.equal(alleInfos(host).length, 3,
    'im Leerzustand fehlen ⓘ — die Rolle bleibt dann unerklärt')
  for (const rolle of ['HV', 'MV', 'GL']) {
    assert.equal(infosImBlock(host, rolle).length, 1, `Leerzustand: kein ⓘ im Block ${rolle}`)
  }
  // Der HV-Block zeigt seinen Leerzustand — der ⓘ sitzt am Kopf, nicht darin.
  const hv = host.querySelector('section[data-rolle="HV"]')
  assert.ok(hv?.querySelector('[data-hv-leer]'), 'der HV-Leerzustand fehlt')
  assert.equal(hv.querySelector('[data-hv-leer] button[aria-label^="Was bewirkt"]'), null,
    'der ⓘ sitzt im Leerzustand-Kasten statt an der Überschrift')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Mehrere MV → weiterhin genau EIN MV-ⓘ
// ══════════════════════════════════════════════════════════════════════════
test('UI-R8c · mehrere MV ergeben weiterhin genau ein MV-ⓘ', async () => {
  const { host, weg } = await rollenBauteil({ antwort: ROLLEN_VIELE_MV })
  // Drei Personen in der MV-Liste …
  const mv = host.querySelector('section[data-rolle="MV"]')
  assert.equal(mv.querySelectorAll('.gr-rollen-eintrag').length, 3, 'die MV-Liste ist nicht vollständig')
  // … aber nur ein ⓘ am Kopf.
  assert.equal(infosImBlock(host, 'MV').length, 1, 'je MV-Person ein ⓘ statt einem an der Überschrift')
  assert.equal(alleInfos(host).length, 3, 'die Zahl der ⓘ hängt an der Personenzahl')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Quelle wirft → kein ⓘ, kein Fehlerbanner, keine leeren Reste
// ══════════════════════════════════════════════════════════════════════════
test('UI-R8c · Ladefehler der Quelle → kein ⓘ, kein Fehlerbanner, Rollenliste bleibt', async () => {
  const { host, weg } = await rollenBauteil({
    reparatur: () => { throw new Error('HTTP 500') },
  })
  assert.equal(alleInfos(host).length, 0,
    'ohne Erklärung darf kein ⓘ stehen (ein ⓘ, das nichts erklärt, ist schlimmer als keiner)')
  assert.equal(host.querySelector('.rr-info-panel'), null, 'ohne Erklärung kein leeres Feld')
  // KEIN Fehlerbanner: die Rollenfläche hat ihren eigenen Fehlerzustand
  // („Rollen nicht geladen“) — der gehört den ROLLEN, nicht der Erklärung.
  assert.equal(txt(host).includes('Rollen nicht geladen'), false,
    'der Ladefehler der Erklärung schlägt auf die Rollenliste durch')
  assert.equal(host.querySelector('.dk-ui-hint'), null, 'die Erklärung zeigt ein Fehlerbanner')
  // KEINE leeren Reste: ohne Erklärung liefert `RrInfo` gar nichts, und die
  // Kopfzeile jedes Blocks hat genau so viele Kindelemente wie auf `main`
  // (Titel + Zahl) — kein zusätzliches leeres Element, keine Leerzeile.
  for (const rolle of ['HV', 'MV', 'GL']) {
    const kopf = host.querySelector(`section[data-rolle="${rolle}"] .gr-rollen-kopf`)
    assert.ok(kopf, `Kopf des Blocks ${rolle} fehlt`)
    assert.equal(kopf.children.length, 2,
      `${rolle}: der Kopf hat ${kopf.children.length} Kindelemente statt 2 (Titel + Zahl)`)
  }
  // Die Seite funktioniert weiter: Rollen stehen, Knöpfe sind da.
  assert.ok(txt(host).includes('Rebekka Fink'), 'die Rollenliste ist verschwunden')
  assert.ok(txt(host).includes('Mira Mit'), 'die MV-Zeile ist verschwunden')
  assert.ok([...host.querySelectorAll('button')].some((b) => txt(b) === 'HV-Amt übertragen'),
    'die Rollenfläche ist ohne die Erklärung nicht mehr bedienbar')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Untergruppen-Seite → nur das GL-ⓘ
// ══════════════════════════════════════════════════════════════════════════
test('UI-R8c · Untergruppen-Seite zeigt nur das GL-ⓘ', async () => {
  const { host, weg } = await rollenBauteil({ antwort: ROLLEN_UNTER, untergruppe: 'UG-K' })
  assert.equal(infosImBlock(host, 'HV').length, 0, 'HV gehört zur Hauptgruppe — hier kein ⓘ')
  assert.equal(infosImBlock(host, 'MV').length, 0, 'MV gehört zur Hauptgruppe — hier kein ⓘ')
  assert.equal(infosImBlock(host, 'GL').length, 1, 'das GL-ⓘ fehlt auf der Untergruppen-Seite')
  assert.equal(alleInfos(host).length, 1, 'auf der Untergruppen-Seite steht genau ein ⓘ')
  // Gegenprobe: die Seite ist wirklich die Untergruppen-Seite.
  assert.ok(txt(host).includes('Die Gruppenleitung führt diese Untergruppe'),
    'die Seite zeigt nicht den Untergruppen-Text')
  weg()
})
