/**
 * UX3d — Kalender-Reiter „Zu prüfen“ (nur Moderatoren).
 *
 * Karte t_88f5c997. Geprüft wird, was der Nutzer SIEHT und was er drücken kann
 * — nicht ein Quelltext-Muster:
 *
 *  1. Die Reiterliste selbst (`menue.kalenderReiter`, die EINE Quelle für
 *     Beschriftung, Reihenfolge und Sichtbarkeit): „Monat · Woche · Liste“
 *     für alle, „Zu prüfen (n)“ NUR für Moderatoren. Die Zahl erscheint nur,
 *     wenn sie bekannt und > 0 ist — nie eine erfundene 0.
 *  2. Die Reiterleiste als Bauteil: gemountet in echtes DOM (jsdom, wie
 *     `ux2f2a-feld-baustein.test.mjs`), Klick auf „Woche“ meldet die Ansicht,
 *     „Zu prüfen“ ist ein Link auf `#/kalender/pruefen` mit `aria-current`,
 *     der aktive Eintrag trägt `aria-pressed`.
 *  3. Die Kopfzeile des Kalenders: der frühere eigene „Zu prüfen“-Knopf ist
 *     WEG (die Aktion gibt es genau einmal), die Reiterleiste kommt mit den
 *     Rechten der Seite, und auf „Zu prüfen“ ist der vierte Reiter aktiv.
 *  4. Der Server liefert das Recht im Boot-Objekt (`can_moderate`) — dieselbe
 *     Quelle wie `get_session_info`. Ohne Schlüssel: kein Reiter.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13 — keine
 * zusätzliche COPY-Zeile im Image) und braucht kein Netz.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

// ── menue.js in einer vm ausführen (website.mjs wird ersetzt) ──────────────
function menueAusfuehren() {
  let source = lies('menue.js')
  source = source.replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
    "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
  source = source.replace(/^export /gm, '')
  source += '\nglobalThis.menue = { kalenderReiter, KALENDER_PRUEF_REITER };'
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.menue
}

const M = menueAusfuehren()
const ids = (liste) => Array.from(liste).map(r => r.id)
const label = (liste, id) => Array.from(liste).find(r => r.id === id)?.label

// ══════════════════════════════════════════════════════════════════════════
// 1 · Die Reiterliste: Reihenfolge und Sichtbarkeit je Rolle
// ══════════════════════════════════════════════════════════════════════════
test('UX3d: ohne Moderationsrecht keine Spur von „Zu prüfen“', () => {
  for (const optionen of [
    {},                                   // kein Angabewert (fail closed)
    { can_moderate: false },
    { can_moderate: 'ja' },               // nur echtes true zählt
  ]) {
    const reiter = M.kalenderReiter(optionen)
    assert.deepEqual(ids(reiter), ['monat', 'woche', 'liste'],
      `Nicht-Moderator sieht genau Monat/Woche/Liste (${JSON.stringify(optionen)})`)
  }
})

test('UX3d: Moderator sieht den vierten Reiter „Zu prüfen“ als LETZTEN', () => {
  const reiter = M.kalenderReiter({ can_moderate: true })
  assert.deepEqual(ids(reiter), ['monat', 'woche', 'liste', 'pruefen'],
    'Reihenfolge nach Entwurf A4')
  assert.equal(label(reiter, 'pruefen'), 'Zu prüfen', 'Beschriftung nach Glossar')
  assert.equal(M.KALENDER_PRUEF_REITER.href, '#/kalender/pruefen',
    'eigene Adresse (teilbar, Lesezeichen)')
  const pruefen = Array.from(reiter).find(r => r.id === 'pruefen')
  assert.equal(pruefen.href, '#/kalender/pruefen', '„Zu prüfen“ ist ein Link, keine Ansicht')
  // Die Ansichten sind Umschalter derselben Seite: ihre Adresse ist der
  // Kalender selbst (`#/kalender`) — das Bauteil zeichnet sie trotzdem als
  // Knopf, damit der Klick keinen Seitenaufbau auslöst. NUR „Zu prüfen“ ist
  // eine eigene Seite und deshalb ein Link.
  for (const id of ['monat', 'woche', 'liste']) {
    const r = Array.from(reiter).find(x => x.id === id)
    assert.equal(r.seite, 'Kalender', `${id} gehört zur Kalender-Seite`)
    assert.notEqual(r.id, 'pruefen', `${id} ist keine eigene Seite`)
  }
})

test('UX3d: die Zahl am Reiter ist eine Kennzahl — keine erfundene 0', () => {
  const mit = (n) => Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: n }))
    .find(r => r.id === 'pruefen').zahl
  assert.equal(mit(3), 3)
  assert.equal(mit('3'), 3, 'Zahl aus JSON (String) wird gelesen')
  assert.equal(mit(0), null, '„0 offen“ heißt: keine Zahl')
  assert.equal(mit(null), null, 'unbekannt: keine Zahl')
  assert.equal(mit(undefined), null)
  assert.equal(mit(''), null)
  assert.equal(mit('viele'), null, 'Unsinn ergibt keine Zahl')
  // Die anderen Reiter tragen nie eine Zahl.
  for (const r of Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: 3 }))) {
    if (r.id !== 'pruefen') assert.equal(r.zahl, null, `${r.id} ohne Zahl`)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Das Bauteil: echte Knöpfe und Links im DOM
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'ux3d-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function kompilieren(abs) {
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
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (v, spec) => {
      const ziel = resolve(dirname(abs), spec)
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))

async function mounten(datei, eigenschaften, vorkommen) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const gemeldet = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil, ...(vorkommen || {}) },
    setup: () => ({ p: eigenschaften, gemeldet }),
    template: '<Geprueft v-bind="p" @waehlen="r => gemeldet.push(r)" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen, gemeldet, neu: async (neue) => { Object.assign(eigenschaften, neue); await tick() } }
}

test('UX3d: Moderator — vier Reiter, „Zu prüfen“ mit Zahl, Anklicken meldet die Ansicht', async () => {
  const reiter = Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: 3 }))
  const { host, gemeldet, warnungen } = await mounten(
    'components/kronos/KalenderReiter.vue',
    { modelValue: 'monat', options: reiter },
    { KalenderReiter: null },
  )
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')

  const punkte = [...host.querySelectorAll('.kal-reiter-punkt')]
  assert.equal(punkte.length, 4, 'vier Reiter')
  assert.deepEqual(punkte.map(p => p.textContent.replace(/\s+/g, ' ').trim()),
    ['Monat', 'Woche', 'Liste', 'Zu prüfen3'], 'Beschriftungen wörtlich (Zahl als eigener Span)')

  // Ansichten sind Knöpfe (kein Adresswechsel), „Zu prüfen“ ist ein Link.
  const [monat, woche, liste, pruefen] = punkte
  for (const p of [monat, woche, liste]) assert.equal(p.tagName, 'BUTTON', 'Ansicht ist ein Knopf')
  assert.equal(pruefen.tagName, 'A', '„Zu prüfen“ ist ein Link')
  assert.equal(pruefen.getAttribute('href'), '#/kalender/pruefen')

  // Aktiv ist der erste Eintrag — nicht nur über Farbe, sondern über ARIA.
  assert.equal(monat.getAttribute('aria-pressed'), 'true', 'aktive Ansicht ist gedrückt')
  assert.equal(woche.getAttribute('aria-pressed'), 'false')
  assert.equal(pruefen.getAttribute('aria-current'), null, 'Link nicht als „aktuelle Seite“ markiert')

  // Klick auf „Woche“ meldet genau diese Ansicht — kein zweiter Weg.
  woche.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(gemeldet.length, 1, 'genau eine Meldung')
  assert.equal(gemeldet[0].id, 'woche')
  assert.equal(gemeldet[0].aktiv, 'timeGridWeek', 'die Ansicht, die der Kalender versteht')
})

test('UX3d: Nicht-Moderator — drei Reiter, kein „Zu prüfen“', async () => {
  const reiter = Array.from(M.kalenderReiter({ can_moderate: false }))
  const { host } = await mounten(
    'components/kronos/KalenderReiter.vue',
    { modelValue: 'liste', options: reiter },
    { KalenderReiter: null },
  )
  const punkte = [...host.querySelectorAll('.kal-reiter-punkt')]
  assert.equal(punkte.length, 3, 'drei Reiter')
  assert.ok(!host.textContent.includes('Zu prüfen'), 'kein „Zu prüfen“ im Baum')
  assert.equal(host.querySelector('a'), null, 'kein Link (kein Ziel, das der Server verweigert)')
  const liste = punkte.find(p => p.dataset.reiter === 'liste')
  assert.equal(liste.getAttribute('aria-pressed'), 'true', 'aktive Ansicht gemäß modelValue')
})

test('UX3d: auf der Prüf-Tafel ist „Zu prüfen“ der aktive Link', async () => {
  const reiter = Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: 2 }))
  const { host } = await mounten(
    'components/kronos/KalenderReiter.vue',
    { modelValue: 'pruefen', options: reiter },
    { KalenderReiter: null },
  )
  const pruefen = host.querySelector('a[data-reiter="pruefen"]')
  assert.ok(pruefen, '„Zu prüfen“ fehlt')
  assert.equal(pruefen.getAttribute('aria-current'), 'page', 'aktuelle Seite ist markiert')
  assert.ok(pruefen.classList.contains('is-aktiv'), 'sichtbare Markierung')
  for (const p of [...host.querySelectorAll('button')]) {
    assert.equal(p.getAttribute('aria-pressed'), 'false', 'keine Ansicht ist gedrückt')
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Die Kopfzeile des Kalenders
// ══════════════════════════════════════════════════════════════════════════
test('UX3d: Kopfzeile zeigt die Reiter und hat KEINEN zweiten „Zu prüfen“-Knopf', async () => {
  const reiter = Array.from(M.kalenderReiter({ can_moderate: true, offeneZahl: 4 }))
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: 4, currentView: 'dayGridMonth', aktiverReiter: 'kalender' },
    { KalenderReiter: Reiter },
  )
  const leiste = host.querySelector('.kal-reiter')
  assert.ok(leiste, 'Reiterleiste fehlt unter dem Kopf')
  assert.equal(leiste.querySelectorAll('.kal-reiter-punkt').length, 4, 'vier Reiter')
  assert.equal(leiste.querySelectorAll('.kal-reiter-punkt').length,
    reiter.length, 'die Kopfzeile zeichnet die Liste aus menue.js')
  // Die Aktion existiert genau EINMAL: nur als Reiter, nicht zusätzlich als Knopf.
  const texte = [...host.querySelectorAll('button, a')].map(e => e.textContent.trim())
  assert.equal(texte.filter(t => t.startsWith('Zu prüfen')).length, 1,
    '„Zu prüfen“ steht genau einmal in der Kopfzeile')
  assert.equal(host.querySelector('.moderation-knopf'), null, 'alter Kopfzeilen-Knopf ist weg')
  // Aktive Ansicht folgt der Kalender-Ansicht.
  assert.equal(leiste.querySelector('[data-reiter="monat"]').getAttribute('aria-pressed'), 'true')
  await Promise.resolve()
})

test('UX3d: ohne Moderationsrecht keine Reiterleiste mit „Zu prüfen“', async () => {
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: false, offeneZahl: null, currentView: 'timeGridWeek' },
    { KalenderReiter: Reiter },
  )
  const leiste = host.querySelector('.kal-reiter')
  assert.ok(leiste, 'Reiterleiste fehlt')
  assert.ok(!leiste.textContent.includes('Zu prüfen'), '„Zu prüfen“ fehlt für Nicht-Moderatoren')
  assert.equal(leiste.querySelector('[data-reiter="woche"]').getAttribute('aria-pressed'), 'true',
    '„Woche“ ist aktiv, wenn der Kalender die Woche zeigt')
})

test('UX3d: im Vollbild der Prüf-Tafel bleiben die Ansichts-Umschalter weg', async () => {
  const Reiter = (await import(pathToFileURL(kompilieren(join(SRC, 'components/kronos/KalenderReiter.vue'))).href)).default
  const { host } = await mounten(
    'components/kronos/KronosTopbar.vue',
    { canModerate: true, offeneZahl: 1, aktiverReiter: 'pruefen', pruefTafel: true, dateTitle: 'Zu prüfen' },
    { KalenderReiter: Reiter },
  )
  assert.ok(host.textContent.includes('Zu prüfen'), 'der Titel steht in der Kopfzeile')
  const leiste = host.querySelector('.kal-reiter')
  assert.ok(leiste, 'die Leiste bleibt (aktive Markierung), statt ganz zu verschwinden')
  // Monat/Woche/Liste sind im Brett tote Schaltflächen — sie fehlen dort.
  for (const id of ['monat', 'woche', 'liste']) {
    assert.equal(host.querySelector(`[data-reiter="${id}"]`), null,
      `„${id}“ ist im Vollbild der Tafel eine tote Schaltfläche`)
  }
  const pruefen = leiste.querySelector('[data-reiter="pruefen"]')
  assert.ok(pruefen, '„Zu prüfen“ markiert die Stelle')
  assert.equal(pruefen.getAttribute('aria-current'), 'page')
})

// Regression (im Wegwerf-Stack gemessen): `<KalenderReiter v-if="…">` am
// Komponenten-Element ließ die Leiste nach dem Wechsel auf „Zu prüfen“
// GAR NICHT entstehen — die Tafel hatte keine Reiter. Deshalb rendert die
// Komponente immer und blendet INNEN aus (leere Liste = keine Leiste).
test('UX3d: die Kopfzeile baut die Leiste immer ein (kein v-if an der Komponente)', () => {
  const quelle = lies('components/kronos/KronosTopbar.vue')
  assert.match(quelle, /<KalenderReiter/, 'KalenderReiter fehlt')
  assert.doesNotMatch(quelle, /<KalenderReiter\s[^>]*\bv-if=/,
    'kein v-if an <KalenderReiter> — sonst entstehen die Reiter nach dem Wechsel nicht')
  // Leere Liste -> keine leere Leiste im Baum.
  const reiterBauteil = lies('components/kronos/KalenderReiter.vue')
  assert.match(reiterBauteil, /v-if="options && options\.length"/,
    'ohne Einträge darf keine leere Leiste stehen')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Woher die Seite ihr Recht nimmt
// ══════════════════════════════════════════════════════════════════════════
test('UX3d: Kalender-Seite liest das Recht aus dem Boot-Objekt (fail closed)', () => {
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /__DIakonosBOOT\??\.can_moderate\s*===\s*true/,
    'das Recht kommt aus dem Boot-Objekt und gilt nur bei echtem true')
  assert.match(quelle, /:canModerate="darfPruefen"/,
    'die Kopfzeile bekommt das Recht von der Seite')
  assert.match(quelle, /:offeneZahl="offeneZahl"/, 'die Kennzahl kommt von der Seite')
  assert.match(quelle, /getModerationCount/, 'die Zahl kommt aus der EINEN Abfrage des Servers')
})

test('UX3d: die Tafel nutzt denselben Kopf und lässt die Funktion unverändert', () => {
  const quelle = lies('pages/Moderation.vue')
  assert.match(quelle, /<KronosTopbar/, 'die Prüf-Tafel nutzt die Kalender-Kopfzeile')
  assert.match(quelle, /aktiverReiter="pruefen"/, 'der vierte Reiter ist dort aktiv')
  assert.match(quelle, /pruefTafel/, 'kein zweiter Reiter-Streifen im Vollbild')
  // Die Funktion bleibt: Alle freigeben, Erklärung, Änderungen, Brett.
  for (const teil of ['Alle freigeben', 'data-test="moderation-erklaerung"',
    'ModerationAenderungen', 'ModerationBoard']) {
    assert.ok(quelle.includes(teil), `${teil} fehlt auf der Tafel`)
  }
  // Die Sichtbarkeit ist NICHT neu entschieden: die Tafel prüft weiter selbst.
  assert.match(quelle, /get_session_info/, 'Serverrecht wird weiterhin abgefragt')
  assert.match(quelle, /can_moderate/, 'can_moderate bleibt die Prüfung der Tafel')
})

// Regression (im Wegwerf-Stack gemessen, 390 px): „Zu prüfen“ ist ein LINK.
// Ohne `flex: 0 0 auto` wuchs er in der Flex-Zeile auf die Restbreite, seine
// Mitte lag unter dem Nachbarn — die halbe Klickfläche war unsichtbar belegt.
test('UX3d: jeder Reiter bleibt auf seiner Textbreite (kein wachsender Link)', () => {
  const quelle = lies('components/kronos/KalenderReiter.vue')
  const start = quelle.indexOf('.kal-reiter-punkt {')
  assert.ok(start > 0, 'Regel .kal-reiter-punkt fehlt')
  const regel = quelle.slice(start, quelle.indexOf('}', start))
  assert.match(regel, /flex:\s*0\s+0\s+auto/,
    'Einträge dürfen weder wachsen (Klickziel spannt die Zeile) noch schrumpfen')
})

// Regression (im Wegwerf-Stack gemessen): ein nicht geschlossener
// `/* …` Kommentar im <style>-Block verschluckte die folgende @media-Regel.
// Der Browser verwarf sie still — die Bedienzeile blieb am Handy einzeilig
// und legte sich über die Reiterzeile. Ein Quelltext-Test, der nur nach
// Selektoren sucht, sieht das nicht.
test('UX3d: CSS-Kommentare in den berührten Bauteilen sind geschlossen', () => {
  for (const datei of ['components/kronos/KronosTopbar.vue',
    'components/kronos/KalenderReiter.vue',
    'pages/Moderation.vue', 'pages/Kalender.vue']) {
    const quelle = lies(datei)
    // Nur die <style>-Blöcke: davor steht JS (mit //-Kommentaren) und die
    // Vorlage (mit <!-- -->).
    const stile = [...quelle.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1])
    assert.ok(stile.length > 0, `${datei}: kein <style>-Block gefunden`)
    for (const css of stile) {
      let tiefe = 0
      for (let i = 0; i < css.length; i += 1) {
        if (css.startsWith('/*', i)) { tiefe += 1; i += 1; continue }
        if (css.startsWith('*/', i)) { tiefe -= 1; i += 1; continue }
        if (tiefe < 0) assert.fail(`${datei}: „*/“ ohne öffnenden Kommentar`)
      }
      assert.equal(tiefe, 0, `${datei}: ${tiefe} ungeschlossene(r) CSS-Kommentar(e)`)
    }
  }
})

test('UX3d: die mobile Bedienzeile der Kopfzeile bleibt am Fenster', () => {
  const quelle = lies('components/kronos/KronosTopbar.vue')
  // UX3i: Die Handy-Regeln der Kopfzeile stehen jetzt im 720er Block (die
  // Layout-Grenze der App); der 768er Block schaltet nur noch den
  // Umschalter der Kalenderliste. Gesucht wird die Regel dort, wo
  // `.header-right` seine Breite bekommt — die Absicht ist dieselbe.
  const block = quelle.slice(quelle.indexOf('@media (max-width: 720px)'))
  const regel = block.slice(block.indexOf('.header-right {'), block.indexOf('}', block.indexOf('.header-right {')))
  assert.match(regel, /flex:\s*0\s+0\s+100%/, 'die Zeile darf nicht über den Kopf hinauswachsen')
})
