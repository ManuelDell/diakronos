/**
 * CHAT-5-UI — Umfragen in der Oberfläche (Vue 3, Frontend).
 *
 * Karte: „CHAT-5-UI — Umfragen in der Oberfläche (Frontend)“. Geprüft wird
 * VERHALTEN (gemountet, mit Netzatttrappe), nicht nur Klassen:
 *
 *   A  Die Regeln (`components/chat/umfrage.mjs`, ohne DOM): Frist als
 *      Wandzeit in Europe/Berlin, Bedienprüfung (Frage, 2–15 Antworten),
 *      Knopfbeschriftung, Anonymität, Balkenbreite, Zustand, Schließen.
 *   B  ChatUmfrage.vue gemountet: Abstimmen/ändern, Mehrfachauswahl, anonym
 *      (keine Namen + Hinweis), Ergebnis-Balken, geschlossen fest, Frist.
 *   C  ChatUmfrageDialog.vue gemountet: POST mit den richtigen Feldern,
 *      2–15 Antworten, anonym als Voreinstellung, Frist in der Ortszeit.
 *   D  Seite Nachrichten.vue: Knopf „Umfrage starten“ nur bei `darf_senden`,
 *      Karte im Verlauf, 403 beim Schließen bleibt ruhig am Ort.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat5-umfrage-ui.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat5-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Die Regeln direkt (kein DOM nötig) ─────────────────────────────────────
const U = await import(new URL('components/chat/umfrage.mjs', SRC).href)
const logik = await import(new URL('composables/nachrichtenLogik.mjs', SRC).href)

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

const VUE_SCHIM = join(TMP, 'vue-schim.mjs')
writeFileSync(VUE_SCHIM, [
  `export * from '${VUE_URL}'`,
  'export function nextTick(fn) {',
  '  const p = globalThis.__NAECHSTER_TAKT()',
  '  return fn ? p.then(fn) : p',
  '}',
].join('\n'))

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function baum(seite, { frisch = false, ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const zielFuer = (quellDatei) => {
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '../').length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    const quellDatei = aufgeloest(abs)
    const quanten = []
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
      quanten.push(code)
    } else {
      quanten.push(readFileSync(quellDatei, 'utf8'))
    }
    const code = quanten.join('\n').replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${quellDatei.endsWith('.vue') ? VUE_SCHIM : VUE_URL}'`
        if (spec.startsWith('.')) {
          const zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        return `from '${spec}'`
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(abs, ziel)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

const tickWarteschlange = []
globalThis.__NAECHSTER_TAKT = () => new Promise((loese) => { tickWarteschlange.push(loese) })
async function rendern(n = 6) {
  for (let i = 0; i < n; i += 1) {
    const offen = tickWarteschlange.splice(0, tickWarteschlange.length)
    if (!offen.length) { await tick(); continue }
    for (const loese of offen) loese()
    await tick()
  }
}

async function mounten(baustein, props = {}, { horcher = null } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  let seite = null
  const kennung = Math.random().toString(36).slice(2)
  globalThis.__HORCHER = globalThis.__HORCHER || {}
  globalThis.__HORCHER[kennung] = horcher
  const melde = (art, wert) => {
    const h = globalThis.__HORCHER[kennung]
    if (h) h(art, wert)
  }
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      seite = Vue.getCurrentInstance()
      const eigene = Vue.ref({ ...innerProps.p })
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (name, wert) => {
        eigene.value = { ...eigene.value, [name]: wert }
      }
      const prop = (name) => (name in eigene.value ? eigene.value[name] : innerProps.p[name])
      return () => Vue.h(baustein, {
        ...eigene.value,
        // Die Rückrufe der geprüften Komponenten einsammeln.
        onAbstimmen: (x) => melde('abstimmen', x),
        onSchliessen: (x) => melde('schliessen', x),
        onAnlegen: (x) => melde('anlegen', x),
        'onUpdate:modelValue': (x) => melde('modelValue', x),
        ...(prop('modelValue') !== undefined ? { modelValue: prop('modelValue') } : {}),
      })
    },
  }
  const app = Vue.createApp({ render: () => Vue.h(Wrapper, { p: props }) })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(10)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  const propSetzen = (name, wert) => {
    const f = globalThis.__PROP_SETZEN?.[kennung]
    if (!f) return false
    f(name, wert)
    return true
  }
  const offen = () => {
    const kind = seite?.subTree?.component
    const instanz = kind && kind !== seite ? kind : null
    return instanz?.exposed || {}
  }
  return { host, app, warnungen, offen, propSetzen, abbaum }
}

/** Ein Klick, wie ihn der Browser auslöst (Knöpfe sind echte <button>). */
function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/** Die Texte einer Auswahl als Liste (ohne Rand-Leerzeichen). */
const texte = (host, auswahl) => [...host.querySelectorAll(auswahl)].map((e) => e.textContent.trim())

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════

/** Eine Umfrage, wie der Server sie liefert (offene Form). */
function umfrageForm(überschreiben = {}) {
  return {
    name: 'chat-umfrage-1',
    gespraech: 'CHAT-1',
    frage: 'Wann proben wir?',
    mehrfach: false,
    anonym: true,
    frist_am: null,
    geschlossen_am: null,
    geschlossen_von: null,
    offen: true,
    stimmen_gesamt: 2,
    abgegeben: 2,
    hinweis: null,
    abgestimmt: false,
    eigene_stimme: null,
    optionen: [
      { nummer: 1, text: 'Samstag', stimmen: 2, namen: [] },
      { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] },
    ],
    ...überschreiben,
  }
}

test('CHAT-5-UI/A: Frist ist Wandzeit in Europe/Berlin, nicht UTC', () => {
  // Der Server LIEST „JJJJ-MM-TT HH:MM“ in der Zeitzone der Gemeinde
  // (`_frist_lesen`). `toISOString()` schriebe 18:30 UTC → 20:30 Ortszeit.
  assert.equal(U.ZEITZONE, 'Europe/Berlin')
  const frist = U.umfrageAnlegenFrist('2026-11-20', '18:30')
  assert.deepEqual(frist, { ok: true, wert: '2026-11-20 18:30' }, 'kein Z/kein UTC-Versatz')
  // Ohne Uhrzeit: Ende des Tages (keine erfundene Uhrzeit).
  assert.equal(U.umfrageAnlegenFrist('2026-11-20', '').wert, '2026-11-20 23:59')
  // Leeres Datum = „bis zur Schließung“ (der Server bekommt `null`).
  assert.deepEqual(U.umfrageAnlegenFrist('', ''), { ok: true, wert: null })
  // Vergangenheit, falsche Form, unmöglicher Tag: abgelehnt, mit Satz.
  const vorbei = U.umfrageAnlegenFrist('2020-01-01', '10:00')
  assert.equal(vorbei.ok, false)
  assert.match(vorbei.fehler, /Vergangenheit/)
  assert.equal(U.umfrageAnlegenFrist('20.11.2026', '18:30').ok, false)
  assert.equal(U.umfrageAnlegenFrist('2026-02-31', '10:00').ok, false, '31.02. gibt es nicht')

  // Anzeige: dieselbe Wandzeit, deutsches Format.
  assert.equal(U.umfrageZeitText('2026-11-20T18:30:00'), '20.11.2026, 18:30')
  assert.equal(U.umfrageZeitText('2026-11-20 18:30:00'), '20.11.2026, 18:30')
  assert.equal(U.umfrageDatumEingabe('2026-11-20 18:30'), '2026-11-20')
  assert.equal(U.umfrageUhrEingabe('2026-11-20 18:30'), '18:30')
  // Unlesbares bleibt leer — nie „Invalid Date“ auf dem Bildschirm.
  assert.equal(U.umfrageZeitText('unsinn'), '')
})

test('CHAT-5-UI/A: Fristzeile und Zustand', () => {
  assert.equal(U.fristText(umfrageForm({ frist_am: '2026-11-20T18:30:00' })), 'endet am 20.11.2026, 18:30')
  assert.equal(U.fristText(umfrageForm()), 'läuft bis zur Schließung')
  assert.equal(U.zustandText(umfrageForm()), 'offen')
  assert.equal(U.zustandText(umfrageForm({
    offen: false, geschlossen_am: '2026-11-19T12:00:00', geschlossen_von: 'hv@x.org',
  })), 'geschlossen')
  assert.equal(U.zustandText(umfrageForm({ offen: false, frist_am: '2026-11-19T12:00:00' })), 'Frist abgelaufen')
})

test('CHAT-5-UI/A: Bedienprüfung — Frage, 2–15 Antworten, keine Dubletten', () => {
  const gut = U.umfragePruefen({ frage: '  Wann?  ', optionen: ['Samstag', 'Sonntag'] })
  assert.equal(gut.ok, true)
  assert.equal(gut.frage, 'Wann?', 'getrimmt')
  assert.deepEqual(gut.optionen, ['Samstag', 'Sonntag'])
  assert.equal(gut.anonym, true, 'Voreinstellung anonym')
  assert.equal(gut.frist, null)

  // Leere Frage, zu wenige Antworten (leere Zeilen zählen nicht).
  assert.match(U.umfragePruefen({ frage: '  ', optionen: ['A', 'B'] }).fehler, /Frage/)
  assert.match(U.umfragePruefen({ frage: 'F?', optionen: ['A', '  '] }).fehler, /mindestens 2/)
  // Zu viele Antworten: 16 sind eine zu viel, 15 gehen.
  const fuenfzehn = Array.from({ length: 15 }, (_, i) => `A${i + 1}`)
  assert.equal(U.umfragePruefen({ frage: 'F?', optionen: fuenfzehn }).ok, true)
  assert.match(U.umfragePruefen({ frage: 'F?', optionen: [...fuenfzehn, 'A16'] }).fehler, /Höchstens 15/)
  // Dieselbe Antwort zweimal ist ein Versehen, keine Wahl.
  assert.match(U.umfragePruefen({ frage: 'F?', optionen: ['Ja', 'ja'] }).fehler, /doppelt/)
  // Frist läuft in derselben Prüfung mit.
  assert.equal(U.umfragePruefen({ frage: 'F?', optionen: ['A', 'B'], datum: '2020-01-01' }).ok, false)
})

test('CHAT-5-UI/A: Anonym — nur Summen, keine Namen, Hinweis bei wenigen', () => {
  const anonym = umfrageForm({
    anonym: true, abgestimmt: true, eigene_stimme: null, abgegeben: 3,
    optionen: [
      { nummer: 1, text: 'Samstag', stimmen: 2, namen: ['Anna Beispiel'] },
      { nummer: 2, text: 'Sonntag', stimmen: 1, namen: [] },
    ],
  })
  assert.deepEqual(U.eigeneWahl(anonym), [], 'keine eigene Option bei anonym')
  assert.deepEqual(U.ergebnisZeilen(anonym).map((z) => z.namen), [[], []],
    'Namen werden verworfen, auch wenn eine Antwort sie trüge')
  assert.match(U.eigenerStandText(anonym), /anonym/)
  assert.match(U.ergebnisZeilen.length ? U.erratbarText(anonym) : '', /erratbar/)
  // Ab 5 Abgegebenen fällt der Hinweis weg (Server: `HINWEIS_AB`).
  assert.equal(U.erratbarText(umfrageForm({ abgegeben: 5 })), '')
  assert.equal(U.erratbarText(umfrageForm({ abgegeben: 2 })), U.TEXTE.erratbar)
  // Der Servertext hat Vorrang (er kennt die Schwelle).
  assert.equal(U.erratbarText(umfrageForm({ hinweis: 'Eigener Text' })), 'Eigener Text')

  // Offen: Namen stehen dort, wo der Server sie schickt.
  const offen = umfrageForm({
    anonym: false, abgestimmt: true, eigene_stimme: [2],
    optionen: [{ nummer: 1, text: 'A', stimmen: 1, namen: ['Bert B.'] },
      { nummer: 2, text: 'B', stimmen: 1, namen: ['Anna A.'] }],
  })
  assert.deepEqual(U.eigeneWahl(offen), [2])
  assert.deepEqual(U.ergebnisZeilen(offen).map((z) => z.namen), [['Bert B.'], ['Anna A.']])
})

test('CHAT-5-UI/A: Balken relativ zur höchsten Antwort, Zahl daneben', () => {
  const zeilen = U.ergebnisZeilen(umfrageForm({
    stimmen_gesamt: 6,
    optionen: [
      { nummer: 1, text: 'A', stimmen: 0, namen: [] },
      { nummer: 2, text: 'B', stimmen: 3, namen: [] },
      { nummer: 3, text: 'C', stimmen: 6, namen: [] },
    ],
  }))
  assert.deepEqual(zeilen.map((z) => z.anteil), [0, 50, 100], 'der höchste Balken ist voll')
  assert.deepEqual(zeilen.map((z) => z.stimmen), [0, 3, 6], 'die Zahl bleibt die Wahrheit')
  // Keine Stimme: kein Balken, keine Division durch null.
  assert.deepEqual(U.ergebnisZeilen(umfrageForm({ optionen: [{ nummer: 1, text: 'A', stimmen: 0 }] }))
    .map((z) => z.anteil), [0])
})

test('CHAT-5-UI/A: Knopfbeschriftung und Auswahl — anonym fest, offen änderbar', () => {
  // Noch nichts abgestimmt, offen: „Abstimmen“.
  assert.equal(U.abstimmKnopfText(umfrageForm()), U.TEXTE.abstimmen)
  // Offen + abgestimmt: „Stimme ändern“.
  assert.equal(U.abstimmKnopfText(umfrageForm({ anonym: false, abgestimmt: true, eigene_stimme: [1] })),
    U.TEXTE.aendern)
  // Anonym + abgestimmt: KEIN Knopf (die Stimme ist endgültig).
  assert.equal(U.abstimmKnopfText(umfrageForm({ anonym: true, abgestimmt: true })), '')
  // Geschlossen: kein Knopf, auch mit offener Umfrage.
  assert.equal(U.abstimmKnopfText(umfrageForm({ anonym: false, abgestimmt: true, offen: false })), '')

  // Einfachauswahl: ein Klick ersetzt die Stimme.
  assert.deepEqual(U.wahlUmschalten([], 2, false), [2])
  assert.deepEqual(U.wahlUmschalten([2], 1, false), [1])
  // Mehrfach: an- und abschalten, sortiert.
  assert.deepEqual(U.wahlUmschalten([], 2, true), [2])
  assert.deepEqual(U.wahlUmschalten([2], 1, true), [1, 2])
  assert.deepEqual(U.wahlUmschalten([1, 2], 2, true), [1])
  // Unsinn wird nicht zur Auswahl.
  assert.deepEqual(U.wahlUmschalten([1], 0, true), [1])
})

test('CHAT-5-UI/A: Schließen-Knopf — NUR das Feld des Servers, keine zweite Prop', () => {
  // Der Server sagt „ja“ (Feld an der Umfrage, aus `_darf_umfrage_schliessen`).
  assert.equal(U.darfSchliessenZeigen(umfrageForm({ darf_schliessen: true })), true)
  // Der Server sagt „nein“ — der Knopf steht NICHT.
  assert.equal(U.darfSchliessenZeigen(umfrageForm({ darf_schliessen: false })), false)
  // Fehlt das Feld (alter Server), gilt „nicht erlaubt“: der Server
  // entscheidet, ein geratener Knopf wäre eine zweite Wahrheit (R2 MUSS A).
  assert.equal(U.darfSchliessenZeigen(umfrageForm()), false)
  assert.equal(U.darfSchliessenZeigen(umfrageForm({ darf_schliessen: null })), false)
  // Keine Umfrage, kein Knopf.
  assert.equal(U.darfSchliessenZeigen(null), false)
  // Nichts zu schließen: kein Knopf (Zustand, kein Recht).
  assert.equal(U.darfSchliessenZeigen(umfrageForm({
    offen: false, geschlossen_am: '2026-11-19T10:00:00', darf_schliessen: true,
  })), false)
  // Die Funktion nimmt NUR das Feld — einen zweiten Weg gibt es nicht mehr.
  const quelle = readFileSync(new URL('../src/diakonos/components/chat/umfrage.mjs', import.meta.url), 'utf8')
  assert.doesNotMatch(quelle, /darfSchliessen = undefined/,
    'die Prop-Ableitung ist gestrichen: eine Quelle (das Feld der Umfrage)')
})

test('CHAT-5-UI/A: eine Änderung von `darf_schliessen` gilt als neuer Stand', () => {
  const L = logik
  const zeile = (darf) => L.verlaufsZeile({
    name: 'chat-n-9', gespraech: 'CHAT-1', text: 'Wann proben wir?',
    erstellt_am: '2026-11-18 09:05:00',
    umfrage: umfrageForm({ darf_schliessen: darf }),
  }, { ich: 'saenger@x.org' })
  // Gleicher Inhalt, anderes Recht: die Seite zählt es als Aktualisierung —
  // sonst bliebe der Schließen-Knopf nach einem Rechtewechsel stehen (SOLL 3).
  const alt = L.seiteEinordnen({ richtung: 'neueste', nachrichten: [{
    name: 'chat-n-9', gespraech: 'CHAT-1', text: 'Wann proben wir?',
    erstellt_am: '2026-11-18 09:05:00',
    umfrage: umfrageForm({ darf_schliessen: true }),
  }] }, { ich: 'saenger@x.org' })
  const neu = L.seiteEinordnen({ richtung: 'seit', nachrichten: [{
    name: 'chat-n-9', gespraech: 'CHAT-1', text: 'Wann proben wir?',
    erstellt_am: '2026-11-18 09:05:00',
    umfrage: umfrageForm({ darf_schliessen: false }),
  }] }, { alt: alt.nachrichten, ich: 'saenger@x.org' })
  assert.equal(neu.aktualisiert, 1, 'der Rechtewechsel ist ein neuer Stand')
  assert.equal(neu.nachrichten[0].umfrage.darf_schliessen, false)
  // Gleicher Stand (nur neu geliefert): keine Aktualisierung — kein Flackern.
  const gleich = L.seiteEinordnen({ richtung: 'seit', nachrichten: [zeile(false)] },
    { alt: neu.nachrichten, ich: 'saenger@x.org' })
  assert.equal(gleich.aktualisiert, 0)
})

test('CHAT-5-UI/A: die Umfrage-Zeile des Verlaufs', () => {
  const zeile = U.umfrageZeileLesen({ name: 'chat-n-1', text: 'Frage?', umfrage: umfrageForm() })
  assert.equal(zeile.umfrage.name, 'chat-umfrage-1')
  assert.equal(U.istUmfrageZeile(zeile), true)
  // Eine gelöschte Umfrage trägt keine Daten (`umfrage: null`) → keine Karte.
  assert.equal(U.istUmfrageZeile(U.umfrageZeileLesen({ name: 'x', umfrage: null, geloescht: true })), false)
  // Keine Umfrage-Nachricht: kein Schlüssel, keine Karte.
  assert.equal(U.umfrageZeileLesen({ name: 'x', text: 'Hallo' }), null)
})

// ════════════════════════════════════════════════════════════════════════════
// B · ChatUmfrage.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

async function karteMontieren(props = {}, { horcher = null } = {}) {
  const ordner = join(TMP, 'karte-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  umleitung.clear()
  const mod = (await import(pathToFileURL(baum('components/chat/ChatUmfrage.vue', { frisch: true, ordner })).href)).default
  return mounten(mod, props, { horcher })
}

test('CHAT-5-UI/B: Karte zeigt Frage, Antworten, Balken und Zahl', async () => {
  const umfrage = umfrageForm({
    stimmen_gesamt: 3,
    optionen: [
      { nummer: 1, text: 'Samstag', stimmen: 2, namen: [] },
      { nummer: 2, text: 'Sonntag', stimmen: 1, namen: [] },
    ],
  })
  const s = await karteMontieren({ umfrage })
  assert.match(s.host.textContent, /Wann proben wir\?/, 'die Frage steht da')
  assert.deepEqual(texte(s.host, '.dk-umfrage-option-text').map((t) => t.replace(/\s+/g, ' ')),
    ['1. Samstag', '2. Sonntag'])
  // Balken: Breite aus dem Anteil der HÖCHSTEN Antwort; die Zahl steht daneben.
  const balken = [...s.host.querySelectorAll('.dk-umfrage-balken-fuellung')].map((e) => e.style.width)
  assert.deepEqual(balken, ['100%', '50%'])
  assert.deepEqual(texte(s.host, '.dk-umfrage-zahl'), ['2', '1'])
  // Die Vorlesefassung nennt die Stimmen in Worten (die Zahl allein ist karg).
  assert.ok(s.host.querySelector('.dk-umfrage-balken-zeile .dk-umfrage-nur-vorlesen'), 'Stimmen auch vorgelesen')
  assert.match(s.host.textContent, /läuft bis zur Schließung/)
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
})

test('CHAT-5-UI/B: Abstimmen und ändern — ein Klick ersetzt die Stimme', async () => {
  const gemeldet = []
  const s = await karteMontieren(
    { umfrage: umfrageForm({ anonym: false }) },
    { horcher: (art, wert) => gemeldet.push({ art, wert }) },
  )
  // Einfachauswahl: Radio-Knöpfe, ein Name für alle.
  const radios = [...s.host.querySelectorAll('input[type="radio"]')]
  assert.equal(radios.length, 2)
  assert.equal(radios[0].name, radios[1].name, 'ein Name je Umfrage (eine Wahl)')
  assert.equal(radios[0].checked, false)

  radios[1].checked = true
  radios[1].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick([...s.host.querySelectorAll('button')].find((b) => /Abstimmen/.test(b.textContent)))
  await warte(4)
  // Der Rückruf trägt die Umfrage und die Nummern — der Elternteil schickt sie.
  const ruf = gemeldet.filter((g) => g.art === 'abstimmen').at(-1)
  assert.ok(ruf, 'die Karte meldet „abstimmen“')
  assert.deepEqual(ruf.wert.optionen, [2])
  assert.equal(ruf.wert.umfrage.name, 'chat-umfrage-1')
  s.abbaum()
})

test('CHAT-5-UI/B: Mehrfachauswahl — Checkboxen, an- und abschaltbar', async () => {
  const gemeldet = []
  const s = await karteMontieren(
    { umfrage: umfrageForm({ anonym: false, mehrfach: true }) },
    { horcher: (art, wert) => gemeldet.push({ art, wert }) },
  )
  const kaestchen = [...s.host.querySelectorAll('input[type="checkbox"]')]
  assert.equal(kaestchen.length, 2, 'Mehrfach zeigt Checkboxen')
  kaestchen[0].checked = true
  kaestchen[0].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  kaestchen[1].checked = true
  kaestchen[1].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick([...s.host.querySelectorAll('button')].find((b) => /Abstimmen/.test(b.textContent)))
  await warte(4)
  assert.deepEqual(gemeldet.filter((g) => g.art === 'abstimmen').at(-1).wert.optionen, [1, 2])
  // Abwählen: die zweite Antwort fällt wieder heraus.
  kaestchen[1].checked = false
  kaestchen[1].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick([...s.host.querySelectorAll('button')].find((b) => /Abstimmen/.test(b.textContent)))
  await warte(4)
  assert.deepEqual(gemeldet.filter((g) => g.art === 'abstimmen').at(-1).wert.optionen, [1])
  s.abbaum()
})

test('CHAT-5-UI/B: eigene offene Stimme ist markiert, Knopf sagt „Stimme ändern“', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({
      anonym: false, abgestimmt: true, eigene_stimme: [2],
      optionen: [{ nummer: 1, text: 'Samstag', stimmen: 0, namen: [] },
        { nummer: 2, text: 'Sonntag', stimmen: 1, namen: ['Anna A.'] }],
    }),
  })
  const radios = [...s.host.querySelectorAll('input[type="radio"]')]
  assert.deepEqual(radios.map((r) => r.checked), [false, true], 'die eigene Wahl steht im Radio')
  assert.ok([...s.host.querySelectorAll('button')].some((b) => /Stimme ändern/.test(b.textContent)))
  // Der Name steht an der Antwort — die Umfrage IST offen.
  assert.match(s.host.textContent, /Anna A\./)
  s.abbaum()
})

test('CHAT-5-UI/B: anonym — keine Namen, kein ändern, Hinweis auf Erratbarkeit', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({
      anonym: true, abgestimmt: true, abgegeben: 2,
      optionen: [
        { nummer: 1, text: 'Samstag', stimmen: 2, namen: ['Anna Beispiel', 'Bert B.'] },
        { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] },
      ],
    }),
  })
  const text = s.host.textContent
  assert.doesNotMatch(text, /Anna Beispiel|Bert B\./, 'NIE Namen bei einer anonymen Umfrage')
  assert.match(text, /Du hast abgestimmt/, 'dass abgestimmt wurde, steht da')
  assert.match(text, /anonym/, 'und zwar als anonym')
  assert.match(text, /erratbar/, 'Hinweis „bei wenigen Teilnehmenden erratbar“')
  assert.equal(s.host.querySelectorAll('input').length, 0, 'nach der anonymen Stimme gibt es keine Wahl mehr')
  assert.ok(![...s.host.querySelectorAll('button')].some((b) => /Abstimmen|Stimme ändern/.test(b.textContent)),
    'kein Knopf: eine anonyme Stimme ist endgültig')
  s.abbaum()
})

test('CHAT-5-UI/B: anonymer Hinweis steht schon VOR der ersten Stimme (und „nicht änderbar“)', async () => {
  // 5 Abgegebene anderer Personen: der Erratbarkeits-Hinweis des Servers
  // fehlt dann (`hinweis: null`) — an einer ANONYMEN Umfrage steht der Hinweis
  // trotzdem, denn er gilt der Anonymität, nicht der Zahl.
  const s = await karteMontieren({
    umfrage: umfrageForm({ anonym: true, abgestimmt: false, abgegeben: 5, hinweis: null }),
  })
  const text = s.host.textContent
  assert.match(text, /anonym — bei wenigen Teilnehmenden ist das Ergebnis trotzdem erratbar/,
    'der Hinweis steht an JEDER anonymen Umfrage')
  assert.match(text, /lässt sich nicht ändern/, 'vor der Abgabe steht der Satz zur Endgültigkeit')
  assert.equal(s.host.querySelectorAll('input[type="radio"]').length, 2, 'wählen ist noch möglich')
  const abstimmen = [...s.host.querySelectorAll('button')].find((b) => /^Abstimmen/.test(b.textContent.trim()))
  assert.ok(abstimmen, '„Abstimmen“ steht da')
  s.abbaum()
})

test('CHAT-5-UI/B: ohne Schließrecht (darf_schliessen false) gibt es keinen Schließen-Knopf', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({ anonym: false, darf_schliessen: false }),
  })
  assert.ok(![...s.host.querySelectorAll('button')].some((b) => /Umfrage schließen/.test(b.textContent)),
    'das „Nein“ des Servers wird respektiert')
  s.abbaum()
  // Fehlt das Feld ganz (alter Server): auch kein Knopf (R2 MUSS A).
  const ohneFeld = await karteMontieren({ umfrage: umfrageForm({ anonym: false }) })
  assert.ok(![...ohneFeld.host.querySelectorAll('button')].some((b) => /Umfrage schließen/.test(b.textContent)),
    'ohne ausdrückliches Recht kein Knopf')
  ohneFeld.abbaum()
  // Mit dem Recht steht er (Gegenprobe).
  const mit = await karteMontieren({
    umfrage: umfrageForm({ anonym: false, darf_schliessen: true }),
  })
  assert.ok([...mit.host.querySelectorAll('button')].some((b) => /Umfrage schließen/.test(b.textContent)))
  mit.abbaum()
})

test('CHAT-5-UI/B: der Ladezustand des Schließen-Knopfs kommt als Prop (kein setTimeout)', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({ anonym: false, darf_schliessen: true }),
    schliesst: true,
  })
  const knopf = [...s.host.querySelectorAll('button')].find((b) => /Umfrage schließen/.test(b.textContent))
  assert.ok(knopf, 'der Knopf steht')
  assert.ok(knopf.disabled || knopf.getAttribute('aria-busy') === 'true' || knopf.className.includes('is-loading'),
    'während des Schließens ist er beschäftigt')
  // Gegenprobe: ohne laufendes Schließen ist er es nicht.
  const ruhig = await karteMontieren({
    umfrage: umfrageForm({ anonym: false, darf_schliessen: true }),
    schliesst: false,
  })
  const k2 = [...ruhig.host.querySelectorAll('button')].find((b) => /Umfrage schließen/.test(b.textContent))
  assert.ok(!(k2.disabled || k2.getAttribute('aria-busy') === 'true' || k2.className.includes('is-loading')),
    'ohne laufendes Schließen kein Ladezustand')
  ruhig.abbaum()

  // Die Seite reicht den Zustand durch; das Bauteil hält keinen eigenen Timer.
  const quelle = readFileSync(new URL('../src/diakonos/components/chat/ChatUmfrage.vue', import.meta.url), 'utf8')
  assert.match(quelle, /schliesst: \{ type: Boolean, default: false \}/,
    '`schliesst` ist eine Prop')
  assert.doesNotMatch(quelle, /setTimeout\(/, 'kein setTimeout(0) als Sperre')
  const seite = readFileSync(new URL('../src/diakonos/pages/Nachrichten.vue', import.meta.url), 'utf8')
  assert.match(seite, /:schliesst="umfrageSchliessenLaeuft === n\.umfrage\.name"/,
    'die Seite gibt den laufenden Namen weiter')
  s.abbaum()
})

test('CHAT-5-UI/B: nur ein Schließen-Auftrag je Klick, solange es läuft', async () => {
  const gemeldet = []
  const s = await karteMontieren({
    umfrage: umfrageForm({ anonym: false, darf_schliessen: true }),
    schliesst: true,
  }, { horcher: (art, wert) => gemeldet.push({ art, wert }) })
  const knopf = [...s.host.querySelectorAll('button')].find((b) => /Umfrage schließen/.test(b.textContent))
  klick(knopf)
  await rendern()
  assert.equal(gemeldet.filter((g) => g.art === 'schliessen').length, 0,
    'solange es läuft, kein zweiter Auftrag')
  // Gegenprobe: ist der Zustand vorbei, meldet der Klick.
  s.propSetzen('schliesst', false)
  await rendern(4)
  klick([...s.host.querySelectorAll('button')].find((b) => /Umfrage schließen/.test(b.textContent)))
  await rendern()
  assert.equal(gemeldet.filter((g) => g.art === 'schliessen').length, 1, 'ohne laufendes Schließen: ein Auftrag')
  s.abbaum()
})

test('CHAT-5-UI/B: eine angefangene Auswahl überlebt einen neuen Serverstand', async () => {
  const s = await karteMontieren({ umfrage: umfrageForm({ anonym: false, abgegeben: 1 }) })
  const radios = [...s.host.querySelectorAll('input[type="radio"]')]
  radios[1].checked = true
  radios[1].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  assert.deepEqual([...s.offen().auswahl.value], [2], 'die Auswahl steht')
  // Der Takt holt den Verlauf: NEUES Objekt, gleiche eigene Wahl (keine).
  const neu = umfrageForm({
    anonym: false, abgegeben: 3, stimmen_gesamt: 4, eigene_stimme: null,
    optionen: [
      { nummer: 1, text: 'Samstag', stimmen: 3, namen: [] },
      { nummer: 2, text: 'Sonntag', stimmen: 1, namen: [] },
    ],
  })
  assert.equal(s.propSetzen('umfrage', neu), true)
  await rendern(6)
  assert.deepEqual([...s.offen().auswahl.value], [2],
    'ein neuer Stand ohne eigene Stimme löscht die angefangene Auswahl NICHT')
  assert.deepEqual(texte(s.host, '.dk-umfrage-zahl'), ['3', '1'], 'die Zahlen ziehen nach')
  s.abbaum()
})

test('CHAT-5-UI/B: geschlossen — Ergebnis fest, nichts mehr wählbar', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({
      anonym: false, offen: false, geschlossen_am: '2026-11-19T12:00:00', geschlossen_von: 'hv@x.org',
      eigene_stimme: [1], abgestimmt: true,
      optionen: [{ nummer: 1, text: 'Samstag', stimmen: 4, namen: ['Anna A.'] },
        { nummer: 2, text: 'Sonntag', stimmen: 1, namen: [] }],
    }),
  })
  assert.match(s.host.textContent, /geschlossen/)
  assert.equal(s.host.querySelectorAll('input').length, 0, 'keine Wahl mehr')
  assert.ok(![...s.host.querySelectorAll('button')].some((b) => /Schließen/.test(b.textContent)),
    'kein „Schließen“ an einer geschlossenen Umfrage')
  // Das Ergebnis bleibt stehen (Balken + Zahl).
  assert.deepEqual(texte(s.host, '.dk-umfrage-zahl'), ['4', '1'])
  assert.deepEqual([...s.host.querySelectorAll('.dk-umfrage-balken-fuellung')].map((e) => e.style.width),
    ['100%', '25%'])
  s.abbaum()
})

test('CHAT-5-UI/B: Frist steht in der Ortszeit, Schließen meldet sich', async () => {
  const gemeldet = []
  const s = await karteMontieren(
    // `darf_schliessen: true` — ohne ausdrückliches Recht steht der Knopf
    // nicht (R2 MUSS A); hier geht es nur um die Meldung des Klicks.
    { umfrage: umfrageForm({ frist_am: '2026-12-01T19:30:00', darf_schliessen: true }) },
    { horcher: (art, wert) => gemeldet.push({ art, wert }) },
  )
  assert.match(s.host.textContent, /endet am 01\.12\.2026, 19:30/)
  klick([...s.host.querySelectorAll('button')].find((b) => /Umfrage schließen/.test(b.textContent)))
  await warte(4)
  assert.equal(gemeldet.filter((g) => g.art === 'schliessen').at(-1).wert.umfrage.name, 'chat-umfrage-1')
  s.abbaum()
})

test('CHAT-5-UI/B: eine Meldung des Servers steht ruhig an der Karte', async () => {
  const s = await karteMontieren({
    umfrage: umfrageForm({ anonym: false }),
    fehler: 'Das hat nicht geklappt. Für diese Umfrage haben Sie bereits abgestimmt.',
  })
  const meldung = s.host.querySelector('.dk-umfrage-fehler')
  assert.ok(meldung, 'die Meldung steht in der Karte')
  assert.equal(meldung.getAttribute('role'), 'alert', 'sie wird vorgelesen')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · ChatUmfrageDialog.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

/**
 * Der Dialog hängt per `Teleport` an `document.body` (DkDialog) — gesucht wird
 * deshalb im DOKUMENT, nicht im Mount-Host.
 */
async function dialogMontieren(props = {}) {
  const ordner = join(TMP, 'dialog-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  umleitung.clear()
  const gemeldet = []
  const mod = (await import(pathToFileURL(baum('components/chat/ChatUmfrageDialog.vue', { frisch: true, ordner })).href)).default
  const s = await mounten(mod, { modelValue: true, ...props },
    { horcher: (art, wert) => gemeldet.push({ art, wert }) })
  await rendern(6)
  const ziel = () => document.querySelector('form.dk-umfrage-form')
  const abbaumVorher = s.abbaum
  s.abbaum = () => {
    abbaumVorher()
    for (const el of document.querySelectorAll('.dk-ui-dialog-overlay')) el.remove()
  }
  return { ...s, gemeldet, ziel }
}

/** Ein Feld füllen, wie der Browser es tut (`v-model` hört auf `input`). */
async function fuellen(el, wert) {
  assert.ok(el, 'das Feld steht im DOM')
  el.value = wert
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(2)
}

test('CHAT-5-UI/C: Anlegen schickt Frage, Antworten, anonym und Frist', async () => {
  const s = await dialogMontieren()
  const form = s.ziel()
  await fuellen(form.querySelector('#umfrage-frage'), 'Wann proben wir?')
  await fuellen(form.querySelector('#umfrage-option-0'), 'Samstag')
  await fuellen(form.querySelector('#umfrage-option-1'), 'Sonntag')
  await fuellen(form.querySelector('#umfrage-datum'), '2026-12-01')
  await fuellen(form.querySelector('#umfrage-uhrzeit'), '19:30')
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(4)
  const ruf = s.gemeldet.filter((g) => g.art === 'anlegen').at(-1)
  assert.ok(ruf, 'der Dialog meldet „anlegen“')
  assert.deepEqual(ruf.wert, {
    frage: 'Wann proben wir?',
    optionen: ['Samstag', 'Sonntag'],
    mehrfach: false,
    anonym: true, // Voreinstellung ANONYM (Konzept F5)
    frist: '2026-12-01 19:30',
  })
  s.abbaum()
})

test('CHAT-5-UI/C: Antworten hinzufügen/entfernen, 2–15 Grenzen', async () => {
  const s = await dialogMontieren()
  const zahl = () => s.ziel().querySelectorAll('input[id^="umfrage-option-"]').length
  assert.equal(zahl(), 2, 'zwei Antworten zum Start')
  // Bei nur zwei Antworten gibt es kein „Entfernen“.
  assert.equal([...s.ziel().querySelectorAll('button')].filter((b) => /Entfernen/.test(b.textContent)).length, 0)
  klick([...s.ziel().querySelectorAll('button')].find((b) => /Antwort anlegen/.test(b.textContent)))
  await rendern()
  assert.equal(zahl(), 3)
  // Die Zahl im Namen des Knopfs gehört zur Zeile; alle drei sind entfernbar.
  const weg = [...s.ziel().querySelectorAll('button')].filter((b) => /Entfernen/.test(b.textContent))
  assert.deepEqual(weg.map((b) => b.getAttribute('aria-label')),
    ['Antwort 1 entfernen', 'Antwort 2 entfernen', 'Antwort 3 entfernen'])
  klick(weg[2])
  await rendern()
  assert.equal(zahl(), 2)
  // Bis 15 aufstocken, dann ist der Knopf weg (max. 15).
  for (let i = 2; i < 15; i += 1) {
    klick([...s.ziel().querySelectorAll('button')].find((b) => /Antwort anlegen/.test(b.textContent)))
    await rendern(1)
  }
  assert.equal(zahl(), 15)
  assert.ok(![...s.ziel().querySelectorAll('button')].some((b) => /Antwort anlegen/.test(b.textContent)),
    'bei 15 Antworten gibt es kein Hinzufügen mehr')
  s.abbaum()
})

test('CHAT-5-UI/C: leere Felder werden gemeldet, nichts geht hinaus', async () => {
  const s = await dialogMontieren()
  const form = s.ziel()
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(4)
  assert.equal(s.gemeldet.filter((g) => g.art === 'anlegen').length, 0, 'ohne Frage kein Aufruf')
  assert.match(s.ziel().textContent, /Bitte eine Frage eingeben/)
  // Frage da, aber nur EINE Antwort: dieselbe Regel wie im Server (2–15).
  await fuellen(form.querySelector('#umfrage-frage'), 'Frage?')
  await fuellen(form.querySelector('#umfrage-option-0'), 'Nur eine')
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(4)
  assert.equal(s.gemeldet.filter((g) => g.art === 'anlegen').length, 0)
  assert.match(s.ziel().textContent, /mindestens 2/)
  s.abbaum()
})

test('CHAT-5-UI/C: offen statt anonym, Mehrfachauswahl', async () => {
  const s = await dialogMontieren()
  const form = s.ziel()
  await fuellen(form.querySelector('#umfrage-frage'), 'Wer kommt?')
  await fuellen(form.querySelector('#umfrage-option-0'), 'Anna')
  await fuellen(form.querySelector('#umfrage-option-1'), 'Bert')
  // „Offen“ wählen (Radio) und Mehrfach ankreuzen.
  const offen = [...form.querySelectorAll('input[type="radio"]')].find((r) => r.value === 'offen')
  assert.equal([...form.querySelectorAll('input[type="radio"]')].find((r) => r.value === 'anonym').checked,
    true, 'anonym ist voreingestellt')
  offen.checked = true
  offen.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  const mehrfach = form.querySelector('input[type="checkbox"]')
  mehrfach.checked = true
  mehrfach.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(4)
  const ruf = s.gemeldet.filter((g) => g.art === 'anlegen').at(-1)
  assert.ok(ruf, 'der Dialog meldet „anlegen“')
  assert.equal(ruf.wert.anonym, false, 'offen heißt anonym = false')
  assert.equal(ruf.wert.mehrfach, true)
  s.abbaum()
})

// Regeln ohne DOM zur Auswahl-Regel der Karte (Review SOLL 5): die Karte
// beobachtet NUR die eigene Wahl — ein neuer Serverstand darf eine angefangene
// Auswahl nicht löschen. Der Code liest dafür `eigeneWahl(…)`.
test('CHAT-5-UI/B (Quelle): die Karte beobachtet nur die eigene Wahl', () => {
  const quelle = readFileSync(new URL('../src/diakonos/components/chat/ChatUmfrage.vue', import.meta.url), 'utf8')
  assert.match(quelle, /watch\(\(\) => eigeneWahl\(props\.umfrage\)\.join\(','\), ausServer\)/,
    'kein watch auf das ganze Objekt')
  assert.doesNotMatch(quelle, /watch\(\(\) => props\.umfrage, ausServer\)/)
})

// ════════════════════════════════════════════════════════════════════════════
// D · Seite Nachrichten.vue (Karte im Verlauf, Knopf, 403)
// ════════════════════════════════════════════════════════════════════════════

function apiAttrappe(ordner, praefix) {
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    `  globalThis.${praefix}_PUSH({ methode, parameter })`,
    `  return globalThis.${praefix}_SERVER({ methode, parameter })`,
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    "  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref({ name: 'M-1' }),",
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref(''),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
  ].join('\n'))
  return { api, session }
}

const GESPRAECHE = [
  { name: 'CHAT-1', art: 'gruppe', gruppe: 'leitung', untergruppe: null, titel: 'Leitung',
    geoeffnet: true, ungelesen: 0, teilnehmer: 4, letzte_nachricht: 'Hallo',
    letzte_am: '2026-11-18 10:00:00', darf_senden: true },
  { name: 'CHAT-2', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
    geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte_nachricht: 'Moin',
    letzte_am: '2026-11-18 09:00:00' },
]

async function seiteMontieren({ hash = '#/nachrichten/CHAT-1', server = {} } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__SEITE')
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)

  const aufrufe = []
  globalThis.__SEITE_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SEITE_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'verlauf') return server.verlauf ? server.verlauf(parameter) : VERLAUF
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash

  const gestartet = new Set()
  const origT = globalThis.setTimeout
  const origI = globalThis.setInterval
  globalThis.setTimeout = (fn, ms) => { const id = origT(fn, ms); gestartet.add(id); return id }
  globalThis.setInterval = (fn, ms) => { const id = origI(fn, ms); gestartet.add(id); return id }
  let gemountet = null
  try {
    const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)).default
    gemountet = await mounten(mod, {})
  } finally {
    globalThis.setTimeout = origT
    globalThis.setInterval = origI
  }
  const abraeumen = () => {
    for (const t of gestartet) { try { clearTimeout(t); clearInterval(t) } catch { /* egal */ } }
  }
  const abbaumVorher = gemountet.abbaum
  gemountet.abbaum = () => { abbaumVorher(); abraeumen() }
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...gemountet, aufrufe }
}

const VERLAUF = {
  gespraech: 'CHAT-1',
  richtung: 'neueste',
  nachrichten: [
    { name: 'CHAT-1-N1', gespraech: 'CHAT-1', text: 'Guten Morgen', eigene: false,
      autor: 'Anna Beispiel', erstellt_am: '2026-11-18 09:00:00' },
    { name: 'CHAT-1-N2', gespraech: 'CHAT-1', text: 'Wann proben wir?', eigene: false,
      autor: 'Anna Beispiel', erstellt_am: '2026-11-18 09:05:00',
      // CHAT-5-UI R2 (MUSS A): der Knopf steht NUR bei ausdrücklichem Recht
      // des Servers — der Verlauf der Seite trägt es deshalb hier.
      umfrage: umfrageForm({ darf_schliessen: true }) },
  ],
}

test('CHAT-5-UI/D: Umfrage steht als Karte im Verlauf, „Umfrage starten“ neben dem Senden', async () => {
  const s = await seiteMontieren()
  const karte = s.host.querySelector('.dk-umfrage')
  assert.ok(karte, 'die Umfrage steht als Karte im Verlauf')
  assert.equal(karte.closest('.dk-chat-blase'), null, 'statt der Blase, nicht daneben')
  assert.match(karte.textContent, /Wann proben wir\?/)
  const start = [...s.host.querySelectorAll('button')].find((b) => /Umfrage starten/.test(b.textContent))
  assert.ok(start, 'der Knopf steht im Eingabebereich')
  assert.equal(start.classList.contains('dk-ui-btn'), true, 'als DkButton, keine Eigenklasse')
  s.abbaum()
})

test('CHAT-5-UI/D: ohne Senderecht (darf_senden false) gibt es keinen Umfrage-Knopf', async () => {
  const ohne = GESPRAECHE.map((g) => (g.name === 'CHAT-1' ? { ...g, darf_senden: false } : g))
  const s = await seiteMontieren({ server: { meine_gespraeche: () => ({ gespraeche: ohne.map((g) => ({ ...g })) }) } })
  assert.equal([...s.host.querySelectorAll('button')].filter((b) => /Umfrage starten/.test(b.textContent)).length,
    0, 'kein Knopf ohne Senderecht')
  assert.ok(s.host.querySelector('.dk-umfrage'), 'die vorhandene Umfrage bleibt lesbar')
  // Und das Senden selbst sagt, warum es nicht geht (dieselbe Quelle).
  assert.ok(s.host.querySelector('.dk-chat-gesperrt'), 'die Eingabe weicht dem Hinweis')
  assert.equal(s.host.querySelector('#chat-eingabe'), null, 'kein Eingabefeld')
  assert.equal(s.host.textContent.includes('Diese Person ist nicht mehr erreichbar.'), true)
  assert.ok(![...s.host.querySelectorAll('button')].some((b) => /Umfrage starten/.test(b.textContent)))
  s.abbaum()
})

test('CHAT-5-UI/D: ohne Feld darf_senden ist Senden und Umfrage möglich', async () => {
  // CHAT-2 liefert kein Feld (alter Server/anderer Aufruf): der Server
  // entscheidet beim Senden erneut — die Oberfläche sperrt nicht.
  const ohne = GESPRAECHE.map((g) => {
    const { darf_senden, ...rest } = g
    return rest
  })
  const s = await seiteMontieren({ server: { meine_gespraeche: () => ({ gespraeche: ohne.map((g) => ({ ...g })) }) } })
  assert.ok([...s.host.querySelectorAll('button')].some((b) => /Umfrage starten/.test(b.textContent)),
    'ohne Feld gilt „ja“')
  assert.ok(s.host.querySelector('#chat-eingabe'), 'die Eingabe steht')
  s.abbaum()
})

test('CHAT-5-UI/D: Abstimmen in der Karte geht über den Server, Ergebnis zieht nach', async () => {
  const stand = umfrageForm({
    anonym: false, abgestimmt: true, eigene_stimme: [1], abgegeben: 1, stimmen_gesamt: 1,
    optionen: [{ nummer: 1, text: 'Samstag', stimmen: 1, namen: ['Anna A.'] },
      { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] }],
  })
  const s = await seiteMontieren({
    server: { umfrage_abstimmen: () => stand },
  })
  const kaestchen = [...s.host.querySelectorAll('.dk-umfrage input[type="radio"]')]
  assert.equal(kaestchen.length, 2)
  kaestchen[0].checked = true
  kaestchen[0].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick([...s.host.querySelectorAll('.dk-umfrage button')].find((b) => /Abstimmen/.test(b.textContent)))
  await rendern(8)
  await warte(14)
  const ruf = s.aufrufe.filter((a) => /umfrage_abstimmen$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'der Server wurde gefragt')
  assert.deepEqual(ruf.parameter, { umfrage: 'chat-umfrage-1', optionen: [1] })
  // Der neue Stand steht in der Karte (kein zweiter Verlaufsabruf nötig).
  await rendern(6)
  assert.deepEqual(texte(s.host, '.dk-umfrage .dk-umfrage-zahl'), ['1', '0'])
  s.abbaum()
})

test('CHAT-5-UI/D: 403 beim Schließen bleibt ruhig an der Karte', async () => {
  const s = await seiteMontieren({
    server: {
      umfrage_schliessen: () => {
        const fehler = new Error('Kein Zugriff')
        fehler.status = 403
        throw fehler
      },
    },
  })
  klick([...s.host.querySelectorAll('.dk-umfrage button')].find((b) => /Umfrage schließen/.test(b.textContent)))
  await rendern(8)
  await warte(14)
  await rendern(6)
  const meldung = s.host.querySelector('.dk-umfrage-fehler')
  assert.ok(meldung, 'die Ablehnung steht an der Karte')
  assert.match(meldung.textContent, /Zugriff|nicht/, 'mit verständlichem Satz')
  assert.equal(meldung.getAttribute('role'), 'alert')
  // Der Verlauf bleibt stehen — kein Sprung, keine leere Fläche.
  assert.ok(s.host.querySelector('.dk-umfrage'), 'die Karte bleibt sichtbar')
  s.abbaum()
})

test('CHAT-5-UI/D: „Umfrage starten“ legt über chat.umfrage_anlegen an', async () => {
  // Die ECHTE Serverantwort von `umfrage_anlegen` ist nur `{name, umfrage}` —
  // ohne `text`, ohne Anzeigenamen. Ein halbes Zeilen-Objekt daraus zu bauen
  // ließe die Zeile bis zum nächsten Abruf als „gelöscht“ erscheinen; deshalb
  // lädt die Seite den Verlauf nach dem Anlegen still neu.
  const neu = { name: 'CHAT-1-N9', gespraech: 'CHAT-1', text: 'Neue Frage', eigene: true,
    autor: 'M-1', autor_mitglied: 'M-1', geloescht: false,
    erstellt_am: '2026-11-18 09:20:00', umfrage: umfrageForm({ name: 'chat-umfrage-9', frage: 'Neue Frage' }) }
  let verlaufAufrufe = 0
  const s = await seiteMontieren({
    server: {
      umfrage_anlegen: () => ({ name: 'CHAT-1-N9', umfrage: umfrageForm({ name: 'chat-umfrage-9', frage: 'Neue Frage' }) }),
      verlauf: () => {
        verlaufAufrufe += 1
        if (verlaufAufrufe === 1) return VERLAUF
        return { ...VERLAUF, nachrichten: [...VERLAUF.nachrichten, neu] }
      },
    },
  })
  klick([...s.host.querySelectorAll('button')].find((b) => /Umfrage starten/.test(b.textContent)))
  await rendern(8)
  const form = document.querySelector('form.dk-umfrage-form')
  assert.ok(form, 'der Dialog steht offen')
  await fuellen(form.querySelector('#umfrage-frage'), 'Neue Frage')
  await fuellen(form.querySelector('#umfrage-option-0'), 'Ja')
  await fuellen(form.querySelector('#umfrage-option-1'), 'Nein')
  const vorher = verlaufAufrufe
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await rendern(8)
  await warte(14)
  const ruf = s.aufrufe.filter((a) => /umfrage_anlegen$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'chat.umfrage_anlegen wurde gerufen')
  assert.equal(ruf.parameter.gespraech, 'CHAT-1')
  assert.equal(ruf.parameter.frage, 'Neue Frage')
  assert.deepEqual(ruf.parameter.optionen, ['Ja', 'Nein'])
  assert.equal(ruf.parameter.anonym, true)
  assert.equal(ruf.parameter.mehrfach, false)
  assert.equal(ruf.parameter.frist, undefined, 'ohne Frist kein Wert (Server: offen bis zur Schließung)')
  await rendern(6)
  assert.ok(verlaufAufrufe > vorher, 'der Verlauf wurde still neu geladen')
  // Die neue Umfrage steht als Karte da — und NICHTS steht als gelöscht da.
  assert.ok(texte(s.host, '.dk-umfrage-frage').includes('Neue Frage'), 'die neue Frage steht im Verlauf')
  assert.ok(texte(s.host, '.dk-umfrage-frage').includes('Wann proben wir?'), 'die alte Karte bleibt')
  assert.equal(s.host.querySelectorAll('.dk-chat-geloescht, .dk-chat-blase--geloescht').length, 0,
    'keine Zeile behauptet „gelöscht“')
  assert.doesNotMatch(s.host.textContent, /wurde gelöscht/, 'kein „Diese Nachricht wurde gelöscht.“')
  s.abbaum()
})

test('CHAT-5-UI/D: Schließen-Knopf erscheint nur nach dem Recht des Servers', async () => {
  const mitRecht = umfrageForm({ darf_schliessen: true })
  const ohne = umfrageForm({ name: 'chat-umfrage-2', darf_schliessen: false })
  const s = await seiteMontieren({
    server: {
      verlauf: () => ({
        ...VERLAUF,
        nachrichten: [
          { ...VERLAUF.nachrichten[0] },
          { ...VERLAUF.nachrichten[1], umfrage: mitRecht },
          { name: 'CHAT-1-N3', gespraech: 'CHAT-1', text: 'Zweite Frage', eigene: false,
            autor: 'Anna Beispiel', erstellt_am: '2026-11-18 09:06:00', umfrage: ohne },
        ],
      }),
    },
  })
  const knoepfe = [...s.host.querySelectorAll('.dk-umfrage button')]
    .filter((b) => /Umfrage schließen/.test(b.textContent))
  assert.equal(knoepfe.length, 1, 'genau an der Umfrage mit `darf_schliessen: true`')
  s.abbaum()
})
