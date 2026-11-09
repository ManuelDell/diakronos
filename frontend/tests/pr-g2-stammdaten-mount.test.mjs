/**
 * PR-G2 (Review PR-G1, 09.11.) — Massenauswahl der Stammdaten am ECHTEN Mount.
 *
 * Ersetzt den Nachbau aus `tests/pr-g1-massenauswahl.test.mjs` (dort wurde das
 * script-setup mit Vue-Attrappen ausgeführt und der `watch` von Hand
 * ausgelöst — das prüfte die Absicht, nicht die Seite). Hier wird
 * `pages/planrahmen/Stammdaten.vue` wie im Betrieb gebaut (jsdom +
 * @vue/compiler-sfc, Muster `tests/ux3b2-personen-mount.test.mjs`) und über
 * echte Klicks/Felder bedient:
 *
 *   1. „alle wählen“ → Filter Geschlecht „Männlich“ → „Anwenden“ →
 *      geschrieben werden nur Männer (Payload der API prüfen).
 *   2. Auswahl über die Suche bzw. die Gruppe, dann Filterwechsel →
 *      die Auswahl ist auf das Sichtbare beschnitten.
 *   3. Zähler „N Personen ausgewählt“ und Knopf „Auf N … anwenden“ zeigen
 *      die SICHTBARE Auswahl — auch nach dem Neuladen der Personenliste
 *      (Schreibvorgang), ohne dass ein Filter gewechselt wurde. Dabei liefert
 *      der Server eine bereits gewählte Person so, dass sie aus dem Filter
 *      fällt (Berta jetzt „m“ bei Filter „Weiblich“): Zähler, Knopf und die
 *      Massenaktion müssen auf 1 zurückgehen (Payload nur [w2]).
 *
 * Nur Tests: die Seite selbst bleibt unverändert (die Proben sind alle grün).
 */
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://x/#/dienste/vorlagen/chorplan' })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'SVGElement',
  'MouseEvent', 'navigator', 'location', 'getComputedStyle', 'requestAnimationFrame',
  'cancelAnimationFrame', 'hashchange']) {
  try { globalThis[k] = dom.window[k] } catch {}
}
globalThis.requestAnimationFrame ||= (f) => setTimeout(f, 0)
globalThis.window.addEventListener ||= () => {}
globalThis.window.removeEventListener ||= () => {}

import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'

const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
// Zwischenordner IM `frontend/` (dort liegen node_modules und src); im Image
// läuft der Test in einer Kopie des Ordners — ein Rest wird am Ende entfernt.
const TMP = mkdtempSync(join(process.cwd(), '.zz-prg2-'))
process.on('exit', () => { try { rmSync(TMP, { recursive: true, force: true }) } catch {} })
const VUE_URL = import.meta.resolve('vue')
const SRC = resolve('src')

// ── Stummel: die Seite redet nicht mit dem Server ─────────────────────────
// Nur die Grenzen, die den Server berühren, werden ersetzt; alles andere
// (Komponenten, `stammdaten-geschlecht.mjs`, Composables) läuft echt.
const STUBS = {
  [resolve(SRC, 'diakonos/composables/usePlanrahmen.js')]: resolve(TMP, 'usePlanrahmen.mjs'),
  [resolve(SRC, 'diakonos/router.js')]: resolve(TMP, 'router.mjs'),
  [resolve(SRC, 'diakonos/composables/useToast.js')]: resolve(TMP, 'useToast.mjs'),
  // Das Ziehen der Sammlungszeilen braucht SortableJS und Berührung — hier
  // nicht Gegenstand; die Attrappe gibt den Steckplatz weiter.
  [resolve(SRC, 'diakonos/components/planrahmen/LiederPflege.vue')]: resolve(TMP, 'LiederPflege.mjs'),
}
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/usePlanrahmen.js')],
  `export function usePlanrahmen(){ return globalThis.__planrahmen }\n`
  + `export function fehlerMeldungen(e){ return [{ pfad: '', code: '', meldung: e?.message || 'Fehler', hinweis: '', stufe: 'fehler' }] }\n`
  + `export function datumText(x){ return String(x ?? '') }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/router.js')],
  `export function getRouteParam(key){ return (globalThis.__routen || {})[key] || '' }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useToast.js')],
  `export function showToast(t){ (globalThis.__toasts ||= []).push(String(t)) }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/components/planrahmen/LiederPflege.vue')],
  `export default { name: 'LiederPflegeAttrappe', props: ['lieder'], template: '<div class="zz-liederpflege"></div>' }\n`)

const cache = new Map()
let n = 0
function compile(abs) {
  if (STUBS[abs]) return STUBS[abs]
  if (cache.has(abs)) return cache.get(abs)
  const z = resolve(TMP, basename(abs) + (n++) + '.mjs')
  cache.set(abs, z)
  let c
  if (abs.endsWith('.vue')) {
    const filename = basename(abs)
    const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename })
    const s = compileScript(descriptor, { id: filename, inlineTemplate: false })
    const t = compileTemplate({
      source: descriptor.template.content, filename, id: filename,
      compilerOptions: { bindingMetadata: s.bindings },
    })
    c = s.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      + '\n' + t.code.replace(/^export function render/m, 'function render')
      + '\n__sfc__.render = render\nexport default __sfc__\n'
  } else c = readFileSync(abs, 'utf8')
  writeFileSync(z, rewrite(c, dirname(abs)))
  return z
}
function rewrite(code, fromDir) {
  return code.replace(/(from\s+|import\s*\(\s*)(['"])([^'"]+)\2/g, (all, pre, q, spec) => {
    if (spec === 'vue' || spec === 'vue-draggable-plus') return `${pre}'${import.meta.resolve(spec)}'`
    if (!spec.startsWith('.')) return all
    return `${pre}'${pathToFileURL(compile(resolve(fromDir, spec))).href}'`
  }).replace(/^import\s+['"][^'"]+\.css['"];?$/gm, '')
}

const Vue = await import('vue')
const Stammdaten = (await import(pathToFileURL(compile(resolve(SRC, 'diakonos/pages/planrahmen/Stammdaten.vue'))).href)).default
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms))
async function ruhig(ms = 60) { await tick(ms); await Vue.nextTick(); await tick(ms) }

// ── Prüfsumme ─────────────────────────────────────────────────────────────
const fehler = []
function pruefe(bedingung, text) {
  if (!bedingung) fehler.push(text)
}

// ── Server-Attrappe ───────────────────────────────────────────────────────
const definition = {
  plantyp: 'chorplan',
  name: 'Chorplan',
  merkmale: {
    person: [
      { id: 'predigt', name: 'Predigt', art: 'tag' },
      { id: 'klavier', name: 'Spielt Klavier', art: 'tag' },
    ],
    bibelarbeiten: [],
  },
  sammlungen: [],
}
const PERSONEN = [
  { id: 'm1', name: 'Anton M', kuerzel: 'AM', geschlecht: 'm', gruppen: ['Chor'], merkmale: {} },
  { id: 'w1', name: 'Berta W', kuerzel: 'BW', geschlecht: 'w', gruppen: ['Chor'], merkmale: {} },
  // Rohwert wie aus einer alten Antwort — die Seite normalisiert ihn selbst.
  { id: 'm2', name: 'Carl M', kuerzel: 'CM', geschlecht: 'Männlich', gruppen: ['Technik'], merkmale: {} },
  { id: 'w2', name: 'Dora W', kuerzel: 'DW', geschlecht: 'w', gruppen: ['Technik'], merkmale: {} },
  // Keine Angabe: darf NIE in einem Geschlechtsfilter auftauchen.
  { id: 'o1', name: 'Emil X', kuerzel: 'EX', gruppen: ['Chor'], merkmale: {} },
]

/** Der Schreibvorgang wirkt auf die Folie — wie der echte Server. */
function personenMitWerten(werte) {
  const kopie = PERSONEN.map((p) => ({ ...p, merkmale: { ...(p.merkmale || {}) } }))
  for (const w of werte || []) {
    const p = kopie.find((x) => x.id === w.ziel_id)
    if (p && w.ziel === 'person') p.merkmale = { ...p.merkmale, [w.schluessel]: w.wert }
  }
  return kopie
}

async function starte({ geschrieben = null } = {}) {
  const aufrufe = []
  let stand = PERSONEN
  globalThis.__toasts = []
  globalThis.__routen = { plantyp: 'chorplan' }
  const stammdaten = () => ({
    definition,
    personen: stand,
    sammlungen: {},
    darf_bearbeiten: true,
    darf_globale_stammdaten_bearbeiten: true,
  })
  globalThis.__planrahmen = {
    stammdatenHolen: async (typ, plan) => { aufrufe.push({ name: 'stammdatenHolen', typ, plan }); return stammdaten() },
    planHolen: async (id) => { aufrufe.push({ name: 'planHolen', id }); return { plan: {} } },
    bedarf: async () => [],
    merkmalePflegen: async (typ, werte, plan) => {
      aufrufe.push({ name: 'merkmalePflegen', typ, werte, plan })
      if (geschrieben) stand = geschrieben(werte)
      else stand = personenMitWerten(werte)
      return {}
    },
    sammlungPflegen: async () => ({ eintraege: [] }),
  }
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp(Stammdaten, { plantyp: 'chorplan', plan: '' })
  const warns = []
  app.config.warnHandler = (m) => warns.push(String(m).slice(0, 160))
  const vm = app.mount(host)
  await ruhig()
  return { host, app, vm, aufrufe, warns, stand: () => stand }
}

function aufraeumen(ctx) {
  try { ctx.app.unmount() } catch {}
  ctx.host.remove()
}

// ── Bedienung wie ein Mensch (echte Felder und Klicks) ────────────────────
const $ = (host, sel) => host.querySelector(sel)
const $$ = (host, sel) => [...host.querySelectorAll(sel)]
const knopf = (host, text) => $$(host, 'button')
  .find((b) => b.textContent.replace(/\s+/g, ' ').trim().includes(text))
const masseText = (host) => $(host, '.pr-stamm-masse-zahl')?.textContent?.replace(/\s+/g, ' ').trim() ?? null
const masseKnopf = (host) => $$(host, '.pr-stamm-masse button')
  .find((b) => /anwenden/.test(b.textContent))
const zeilenIds = (host) => $$(host, 'tbody tr').map((tr) => $(tr, '.pr-stamm-name-haupt')?.textContent?.trim())
const nameZelle = (tr) => $(tr, '.pr-stamm-name-haupt')?.textContent?.trim()

/** Auswahlfeld setzen und das echte `change` auslösen (v-model). */
async function waehle(el, wert) {
  el.value = wert
  el.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await ruhig(30)
}
/** Suchfeld tippen wie ein Mensch (v-model auf `input`). */
async function tippe(el, text) {
  el.value = text
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await ruhig(30)
}
/** Kontrollkästchen einer Zeile umschalten (das Klicken löst `change` aus). */
async function klicke(el) {
  el.click()
  await ruhig(30)
}

const geschlechtFeld = (host) => $(host, '.pr-stamm-geschlechtwahl')
const gruppenFeld = (host) => $(host, '.pr-stamm-gruppenwahl')
const sucheFeld = (host) => $(host, '.pr-stamm-suche')
const allesFeld = (host) => $(host, 'thead input[type="checkbox"]')
const zeileMit = (host, id) => $$(host, 'tbody tr').find((tr) =>
  $(tr, 'input[type="checkbox"]')?.getAttribute('aria-label') === 'Person auswählen: ' + id
  || nameZelle(tr) === id)

// ═══ 1. Alle wählen → Geschlecht „Männlich“ → Anwenden: nur Männer ═══════
{
  const ctx = await starte()
  const { host, aufrufe, warns } = ctx
  pruefe(warns.length === 0, `1: Vue-Warnungen ${JSON.stringify(warns)}`)
  pruefe(zeilenIds(host).length === 5, `1: fünf Personen in der Tabelle (waren ${zeilenIds(host).length})`)
  pruefe(Boolean(masseText(host)) === false, '1: ohne Auswahl keine Massenzeile')

  // „Alle sichtbaren Personen auswählen“ — der Kontrollkasten im Kopf.
  const alle = allesFeld(host)
  pruefe(Boolean(alle), '1: Kontrollkasten „alle sichtbaren“ ist da')
  await klicke(alle)
  pruefe(masseText(host) === '5 Personen ausgewählt',
    `1: Zähler nach „alle wählen“ (war ${masseText(host)})`)
  pruefe(Boolean(masseKnopf(host)) && /Auf 5 Personen anwenden/.test(masseKnopf(host).textContent),
    `1: Knopf „Auf 5 Personen anwenden“ (war ${masseKnopf(host)?.textContent?.trim()})`)

  // Filter über das ECHTE Auswahlfeld auf „Männlich“.
  const feld = geschlechtFeld(host)
  pruefe(Boolean(feld), '1: Auswahlfeld Geschlecht ist da')
  await waehle(feld, 'm')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Anton M', 'Carl M']),
    `1: Filter „Männlich“ zeigt beide Schreibweisen (waren ${JSON.stringify(zeilenIds(host))})`)
  pruefe(masseText(host) === '2 Personen ausgewählt',
    `1: Zähler folgt der sichtbaren Auswahl (war ${masseText(host)})`)
  pruefe(/Auf 2 Personen anwenden/.test(masseKnopf(host)?.textContent || ''),
    `1: Knopf zählt ebenfalls 2 (war ${masseKnopf(host)?.textContent?.trim()})`)

  // Eigenschaft wählen, Wert setzen, anwenden.
  const merkmalFeld = $(host, '.pr-stamm-masse-merkmal')
  pruefe(Boolean(merkmalFeld), '1: Auswahlfeld Eigenschaft ist da')
  await waehle(merkmalFeld, 'predigt')
  const wertFeld = $(host, '.pr-stamm-masse-wert input[type="checkbox"]')
  pruefe(Boolean(wertFeld), '1: Ja/Nein-Feld der Massenaktion ist da')
  await klicke(wertFeld)
  const anwenden = masseKnopf(host)
  pruefe(anwenden?.disabled === false, '1: „Anwenden“ ist nach der Wertwahl bedienbar')
  anwenden.click()
  await ruhig()

  const schreiben = aufrufe.filter((a) => a.name === 'merkmalePflegen').at(-1)
  pruefe(Boolean(schreiben), '1: die Massenaktion hat geschrieben')
  const ids = (schreiben?.werte || []).map((w) => w.ziel_id).sort()
  pruefe(JSON.stringify(ids) === JSON.stringify(['m1', 'm2']),
    `1: geschrieben werden NUR die sichtbaren Männer (waren ${JSON.stringify(ids)})`)
  pruefe((schreiben?.werte || []).every((w) => w.ziel === 'person' && w.schluessel === 'predigt' && w.wert === true),
    `1: Payload trägt Predigt=ja für Personen (war ${JSON.stringify(schreiben?.werte)})`)
  pruefe(schreiben?.typ === 'chorplan', `1: Plantyp im Aufruf (war ${schreiben?.typ})`)
  pruefe(masseText(host) === null, `1: Auswahl nach dem Anwenden geleert (war ${masseText(host)})`)
  // Die Folie wurde neu geladen — die gespeicherten Werte stehen im Bild.
  const anna = zeileMit(host, 'Anton M')
  pruefe($(anna, 'input[type="checkbox"]')?.disabled === false, '1: Zeile nach dem Neuladen bedienbar')
  aufraeumen(ctx)
}

// ═══ 2a. Auswahl über die SUCHE, dann Filterwechsel → beschnitten ════════
{
  const ctx = await starte()
  const { host } = ctx
  // Erst alles wählen (ohne Filter), DANN die Suche eingrenzen: nur so
  // entsteht überhaupt eine unsichtbare Auswahl, die beschnitten werden muss.
  const alle = allesFeld(host)
  await klicke(alle)
  pruefe(masseText(host) === '5 Personen ausgewählt', `2a: alle fünf gewählt (war ${masseText(host)})`)

  // Suche auf „Carl“ → nur Carl sichtbar, die Auswahl schrumpft auf ihn.
  await tippe(sucheFeld(host), 'Carl')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Carl M']),
    `2a: Suche zeigt nur Carl (waren ${JSON.stringify(zeilenIds(host))})`)
  pruefe(masseText(host) === '1 Person ausgewählt', `2a: Zähler „1 Person ausgewählt“ (war ${masseText(host)})`)
  pruefe(/Auf 1 Person anwenden/.test(masseKnopf(host)?.textContent || ''),
    `2a: Knopf „Auf 1 Person anwenden“ (war ${masseKnopf(host)?.textContent?.trim()})`)

  // Suche zurücknehmen: die Auswahl ist BESCHNITTEN, nicht wiederhergestellt.
  await tippe(sucheFeld(host), '')
  pruefe(zeilenIds(host).length === 5, '2a: ohne Suche stehen wieder alle fünf da')
  pruefe(masseText(host) === '1 Person ausgewählt',
    `2a: nach dem Zurücknehmen bleibt nur die gezeigte Auswahl (war ${masseText(host)})`)
  aufraeumen(ctx)
}

// ═══ 2b. Auswahl über die GRUPPE, dann Filterwechsel → beschnitten ═══════
{
  const ctx = await starte()
  const { host } = ctx
  const gruppen = $$(host, '.pr-stamm-gruppenwahl option').map((o) => o.value)
  pruefe(JSON.stringify(gruppen) === JSON.stringify(['', 'Chor', 'Technik']),
    `2b: Gruppenwahl aus der Liste (waren ${JSON.stringify(gruppen)})`)

  // In der Gruppe „Chor“ alle wählen (Anton, Berta, Emil).
  await waehle(gruppenFeld(host), 'Chor')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Anton M', 'Berta W', 'Emil X']),
    `2b: Gruppe „Chor“ (waren ${JSON.stringify(zeilenIds(host))})`)
  await klicke(allesFeld(host))
  pruefe(masseText(host) === '3 Personen ausgewählt', `2b: drei aus der Gruppe (war ${masseText(host)})`)

  // Gruppenwechsel auf „Technik“ → Auswahl auf die Technik-Personen beschnitten.
  await waehle(gruppenFeld(host), 'Technik')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Carl M', 'Dora W']),
    `2b: Gruppe „Technik“ (waren ${JSON.stringify(zeilenIds(host))})`)
  pruefe(masseText(host) === null,
    `2b: Überschneidung leer → keine Massenzeile (war ${masseText(host)})`)
  pruefe(!masseKnopf(host), '2b: ohne sichtbare Auswahl kein Anwenden-Knopf')

  // Zurück auf „Chor“: die Auswahl ist weg (beschneiden ist keine Zwischenablage).
  await waehle(gruppenFeld(host), 'Chor')
  pruefe(masseText(host) === null, `2b: Zurückwechseln stellt nichts wieder her (war ${masseText(host)})`)
  aufraeumen(ctx)
}

// ═══ 3. Zähler nach dem NEULADEN der Liste (ohne Filterwechsel) ═══════════
{
  // Der Server liefert nach dem Schreiben eine ANDERE Reihenfolge UND Berta
  // fällt aus dem aktiven Filter (Geschlecht jetzt „m“, Filter steht auf
  // „Weiblich“) — ohne Filterwechsel. Zähler und Knopf müssen der SICHTBAREN
  // Auswahl folgen, nicht der rohen (die noch w1 enthält).
  const ctx = await starte({
    geschrieben: (werte) => personenMitWerten(werte)
      .map((p) => (p.id === 'w1' ? { ...p, geschlecht: 'm' } : p))
      .reverse(),
  })
  const { host, aufrufe } = ctx
  await waehle(geschlechtFeld(host), 'w')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Berta W', 'Dora W']),
    `3: Filter „Weiblich“ (waren ${JSON.stringify(zeilenIds(host))})`)
  await klicke(allesFeld(host))
  pruefe(masseText(host) === '2 Personen ausgewählt', `3: zwei Frauen gewählt (war ${masseText(host)})`)

  // EINE Person einzeln schreiben (Klick auf Predigt bei Berta) → die Seite
  // lädt die Personenliste neu, der Filter bleibt stehen.
  const berta = zeileMit(host, 'Berta W')
  const predigt = $(berta, 'td.pr-stamm-zelle input[type="checkbox"]')
  pruefe(Boolean(predigt), '3: Predigt-Kästchen in der Zeile ist da')
  const vorher = aufrufe.length
  await klicke(predigt)
  pruefe(aufrufe.length > vorher, '3: Einzeländerung hat geschrieben')
  pruefe(aufrufe.slice(vorher).some((a) => a.name === 'stammdatenHolen'),
    '3: die Personenliste wurde neu geladen')
  pruefe(geschlechtFeld(host)?.value === 'w', '3: der Filter steht nach dem Neuladen noch auf „Weiblich“')
  pruefe(JSON.stringify(zeilenIds(host)) === JSON.stringify(['Dora W']),
    `3: Berta ist aus dem Filter gefallen (waren ${JSON.stringify(zeilenIds(host))})`)
  // Berta (w1) steckt noch in der ROHEN Auswahl, ist aber nicht mehr sichtbar
  // → Zähler und Knopf zeigen 1, nicht 2.
  pruefe(masseText(host) === '1 Person ausgewählt',
    `3: Zähler nach dem Neuladen zeigt die sichtbare Auswahl 1 (war ${masseText(host)})`)
  pruefe(/Auf 1 Person anwenden/.test(masseKnopf(host)?.textContent || ''),
    `3: Knopf zählt nach dem Neuladen 1 (war ${masseKnopf(host)?.textContent?.trim()})`)

  // Und die Massenaktion wirkt nur auf die noch sichtbare Frau (Dora).
  await waehle($(host, '.pr-stamm-masse-merkmal'), 'predigt')
  await klicke($(host, '.pr-stamm-masse-wert input[type="checkbox"]'))
  masseKnopf(host).click()
  await ruhig()
  const schreiben = aufrufe.filter((a) => a.name === 'merkmalePflegen').at(-1)
  const ids = (schreiben?.werte || []).map((w) => w.ziel_id).sort()
  pruefe(JSON.stringify(ids) === JSON.stringify(['w2']),
    `3: angewendet wird nur die sichtbare Frau (waren ${JSON.stringify(ids)})`)
  aufraeumen(ctx)
}

if (fehler.length) {
  console.error('PR-G2 Massenauswahl (Mount): ' + fehler.length + ' Fehlschlag/Fehlschläge')
  for (const f of fehler) console.error(' - ' + f)
  process.exit(1)
}
console.log('PR-G2 Massenauswahl (Mount): alle Proben grün')
process.exit(0)
