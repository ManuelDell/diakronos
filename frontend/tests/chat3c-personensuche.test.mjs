/**
 * CHAT-3c — Nachrichten: Personensuche (Vue 3, Frontend).
 *
 * Review R1 hat drei MUSS und sieben SOLL gefordert; für JEDEN MUSS-Punkt
 * steht hier ein VERHALTENSTEST (kein Quelltext-Regex):
 *
 *   MUSS 1  Abschnittsüberschriften: im Listenmodus keine, bei Treffern genau
 *           eine „Personen“ (nicht zwei, keine leere).
 *   MUSS 2  Der Verlauf bekommt GENAU EINEN Eintrag beim Öffnen der Suche;
 *           weitere Tastenanschläge ersetzen ihn; Zurück (popstate) schließt
 *           die Suche und stellt Liste bzw. offenes Gespräch wieder her.
 *   MUSS 3  Feldinhalt ist die Quelle der Wahrheit: Löschen unter 2 Zeichen
 *           bei geladenem `?q=…` lässt das Getippte stehen, schließt das
 *           Gespräch nicht und zeigt Treffer und Liste nicht doppelt.
 *
 * Gegengeprüft werden die SOLL-Punkte: roher Begriff in der Adresse (a),
 * offener Entpreller fällt beim Zurücksetzen weg (b), EIN Leer-Text (c),
 * `#/nachrichten/suche` ohne `q` wie die Liste (d), Zurück vom Profil findet
 * die Suche wieder (e), keine Rohwerte für Sperrung/Ausgrauung (f), kein
 * `aria-disabled` am nicht fokussierbaren <span> (g).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat3c-personensuche.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import vm from 'node:vm'
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
// Der Chat-Takt fragt nur bei SICHTBAREM Tab (jsdom meldet ohne
// PretendToBeVisual „verborgen“) — sonst prüfte man den Hintergrund-Zweig.
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)
const WURZEL = SRC

const TMP = mkdtempSync(join(tmpdir(), 'chat3c-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Die Regeln direkt (kein DOM nötig) ─────────────────────────────────────
const S = await import(new URL('composables/nachrichtenSuche.mjs', WURZEL).href)

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

/**
 * `vue` mit einer EIGENEN `nextTick`: der Warteschlange-Mechanismus läuft auf
 * der Schleife (sonst landete jede Wartemarke in einem Mikrotask, der ohne
 * echtes Rendern nie käme). Alles andere kommt unverändert aus `vue`.
 */
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
    // Der Pfad ab `frontend/` — `../shared/` liegt AUSSERHALB von `src/diakonos/`.
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
      code = code.replace(/defineAsyncComponent\(\(\) => import\([^)]*\)\)/g,
        'defineAsyncComponent(() => Promise.resolve({ render: () => null }))')
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
/** Warten, bis `bedingung` gilt — für asynchrone Ketten (mehrere `await` je
 *  Antwort) verlässlicher als eine feste Zahl von Ticks. */
async function bis(bedingung, { ms = 2000, schritt = 5 } = {}) {
  const ende = Date.now() + ms
  while (Date.now() < ende) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, schritt))
    await rendern()
  }
  return Boolean(bedingung())
}
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

async function mounten(baustein, props = {}, { horcher = null } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  // Die INSTANZ der geprüften Komponente: `app.mount()` gibt die Wurzel
  // zurück, nicht das Kind. Der Wrapper reicht darum seine eigene Instanz nach
  // draußen — sie hängt DAVOR im Baum und sieht das Kind als Kind.
  let seite = null
  // Die Rückrufe hängen am GLOBALEN Haken, nicht an dieser Montage: sonst
  // zeigte ein Geflecht, das den Wrapper eines früheren Laufs weiterbenutzt,
  // weiter auf dessen (inzwischen leeren) Horcher.
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
      // Die Probe darf einen Prop nachreichen — der Elternteil setzt ihn neu
      // (so wie die Seite es mit `startBegriff` aus der Adresse tut).
      const start = Vue.ref(innerProps.p?.startBegriff ?? '')
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (wert) => { start.value = wert }
      return () => Vue.h(baustein, {
        ...innerProps.p,
        startBegriff: start.value,
        onSucht: (q) => melde('sucht', q),
        onTreffer: (x) => melde('treffer', x),
      })
    },
  }
  const app = Vue.createApp({
    render: () => Vue.h(Wrapper, { p: props }),
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(10)
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
  /**
   * Einen Prop von außen neu setzen — so wie die Seite `startBegriff` aus der
   * Adresse nachreicht (Zurück vom Profil).
   */
  const propSetzen = (wert) => {
    const f = globalThis.__PROP_SETZEN?.[kennung]
    if (!f) return false
    f(wert)
    return true
  }
  /**
   * Was die GEPRÜFTE Komponente über `exposed` herausgibt: `defineExpose` und
   * `instanz.exposed` stehen auf dem Kind des Wrappers (`subTree.component`).
   */
  const offen = () => {
    const kind = seite?.subTree?.component
    const instanz = kind && kind !== seite ? kind : null
    return instanz?.exposed || {}
  }
  return { host, app, warnungen, vm, offen, propSetzen, abbaum }
}

/** Ein Tastendruck ins Suchfeld (wie der Browser ihn auslöst: `input`). */
async function tippen(host, wert) {
  const feld = host.querySelector('input#chat-suche')
  assert.ok(feld, 'das Suchfeld steht im DOM')
  feld.value = wert
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(6)
}

/**
 * `nextTick`-Attrappe: sammelt die Rückrufe und lässt sie auf Befehl laufen.
 *
 * Der Prüfstand läuft im selben Makrotask wie Vue; ohne echtes `nextTick`
 * rendert eine geänderte Adresse nicht mehr (das kostete je Test 40 s
 * Testzeitlimit). Die SEITE importiert `nextTick` aus `vue` — der SFC-Baum
 * ersetzt diesen Import durch diese Datei (siehe `vueUmleitung`).
 */
const tickWarteschlange = []
function naechsterTakt() {
  return new Promise((loese) => { tickWarteschlange.push(loese) })
}
globalThis.__NAECHSTER_TAKT = naechsterTakt

/** Alle wartenden `nextTick`-Rückrufe laufen lassen (bis nichts mehr kommt). */
async function rendern(n = 6) {
  for (let i = 0; i < n; i += 1) {
    const offen = tickWarteschlange.splice(0, tickWarteschlange.length)
    if (!offen.length) { await tick(); continue }
    for (const loese of offen) loese()
    await tick()
  }
}

/** Termine zählen und von Hand abspulen (Entprellung ohne echtes Warten). */
function uhrAttrappe() {
  let kennung = 0
  const termine = new Map()
  return {
    // Der Schlüssel ist eine Zahl (wie bei `setTimeout`), nicht die Funktion —
    // sonst hielte die Map zwei Aufrufe derselben Funktion für denselben Termin.
    timer: (fn, ms) => { kennung += 1; termine.set(kennung, { fn, ms }); return kennung },
    timerAus: (id) => { termine.delete(id) },
    offen: () => termine.size,
    /** Alle geplanten Termine feuern (der jüngste ist der gültige). */
    async feuern() {
      const faellig = [...termine.values()]
      termine.clear()
      for (const t of faellig) t.fn()
      await warte(6)
    },
  }
}

// ── Gemeinsame Proben ──────────────────────────────────────────────────────

const GESPRAECHE = [
  { name: 'CHAT-1', art: 'gruppe', gruppe: 'leitung', untergruppe: null, titel: 'Leitung',
    geoeffnet: true, ungelesen: 2, teilnehmer: 4, letzte_nachricht: 'Hallo',
    letzte_am: '2026-11-18 10:00:00' },
  { name: 'CHAT-2', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
    geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte_nachricht: 'Moin',
    letzte_am: '2026-11-18 09:00:00' },
]

const PERSONEN = { treffer: [
  { mitglied: 'M-1', anzeigename: 'Anna Beispiel', bild: '', hat_konto: true, darf_schreiben: true },
  { mitglied: 'M-2', anzeigename: 'Bert Brandner', bild: '/files/b.jpg', hat_konto: true, darf_schreiben: true },
], limit: 20 }

/** Kleine Hilfe: ein Abschnitt mit genau einem Gesprächstreffer. */
function gespraechstrefferTest() {
  return S.gespraechsTreffer(GESPRAECHE, 'chor')
}

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-3c/A: die Suche hat eine Adresse — `?q=` hin und zurück', async () => {
  assert.equal(S.SUCH_HASH, '#/nachrichten/suche')
  assert.equal(S.suchHash(''), S.SUCH_HASH)
  assert.equal(S.suchHash('   '), S.SUCH_HASH, 'nur Leerzeichen ist kein Begriff')
  assert.equal(S.suchHash('anna b'), '#/nachrichten/suche?q=anna%20b')

  assert.equal(S.istSuchHash('#/nachrichten/suche'), true)
  assert.equal(S.istSuchHash('#/nachrichten/suche?q=anna'), true)
  assert.equal(S.istSuchHash('#/nachrichten/suche/'), true, 'Schluss-Schrägstrich egal')
  assert.equal(S.istSuchHash('#/nachrichten'), false, 'die Liste ist keine Suche')
  assert.equal(S.istSuchHash('#/nachrichten/CHAT-1'), false, 'ein Gespräch ist keine Suche')

  // Hin und zurück: der Begriff überlebt den Weg durch die Adresse.
  assert.equal(S.qAusHash(S.suchHash('Anna Müller')), 'Anna Müller')
  assert.equal(S.qAusHash('#/nachrichten/suche'), '')
  assert.equal(S.qAusHash('#/nachrichten/CHAT-1?q=anna'), '', 'fremde Adresse trägt keinen Begriff')

  // `gespraechAusHash` (CHAT-3a) liest `suche` NICHT als Gesprächskennung.
  const { gespraechAusHash } = await import(new URL('composables/nachrichtenLogik.mjs', WURZEL).href)
  assert.equal(gespraechAusHash('#/nachrichten/suche?q=anna'), null)
})

test('CHAT-3c/A (SOLL a/d): roher Begriff in der Adresse, Suche ohne `q` = Liste', () => {
  // Der ROHE, getrimmte Begriff steht in der Adresse — nicht der gefaltete.
  assert.equal(S.suchHash('Müller'), '#/nachrichten/suche?q=M%C3%BCller')
  assert.equal(S.qAusHash(S.suchHash('Müller')), 'Müller', 'die Adresse trägt keinen Suchbegriff, sondern die Eingabe')
  assert.equal(S.suchHash('  Grün Weiß  '), '#/nachrichten/suche?q=Gr%C3%BCn%20Wei%C3%9F')

  // `#/nachrichten/suche` OHNE Begriff verhält sich wie die Liste.
  assert.equal(S.sucheOffenBei('#/nachrichten/suche'), false, 'ohne `q` keine offene Suche')
  assert.equal(S.sucheOffenBei('#/nachrichten/suche?q=anna'), true)
  assert.equal(S.sucheOffenBei('#/nachrichten'), false)
  assert.equal(S.sucheSichtbar(''), false)
  assert.equal(S.sucheSichtbar('   '), false)
  assert.equal(S.sucheSichtbar('a'), true, 'ein Zeichen öffnet die Suche (keine Doppelanzeige)')
})

test('CHAT-3c-2/A (MUSS B): die Suchadresse kann das offene Gespräch mitführen', () => {
  // Ohne Kennung bleibt alles wie bisher.
  assert.equal(S.suchHash('anna'), '#/nachrichten/suche?q=anna')
  assert.equal(S.suchHash('anna', ''), '#/nachrichten/suche?q=anna')
  // Mit Kennung: ein zusätzlicher Parameter, der Begriff bleibt roh.
  assert.equal(S.suchHash('anna', 'CHAT-2'), '#/nachrichten/suche?q=anna&offen=CHAT-2')
  assert.equal(S.qAusHash(S.suchHash('Anna Müller', 'CHAT-2')), 'Anna Müller')
  assert.equal(S.offenAusHash(S.suchHash('anna', 'CHAT-2')), 'CHAT-2')
  // Kein Begriff, aber eine Kennung: die Suche ist dann nicht OFFEN (SOLL d).
  assert.equal(S.suchHash('', 'CHAT-2'), '#/nachrichten/suche?offen=CHAT-2')
  assert.equal(S.sucheOffenBei('#/nachrichten/suche?offen=CHAT-2'), false)
  assert.equal(S.offenAusHash('#/nachrichten/suche?offen=CHAT-2'), 'CHAT-2')
  // Fremde Adressen tragen keine Kennung.
  assert.equal(S.offenAusHash('#/nachrichten/CHAT-1'), '')
  assert.equal(S.offenAusHash('#/nachrichten/suche?q=anna'), '')
  assert.equal(S.offenAusHash(''), '')
})

test('CHAT-3c-2/A (SOLL 7): `geschwisterAdresse` ist weg — `zeilenAdresse` trifft Ziel und Ort', async () => {
  // Review R1, SOLL 7: keine Sonderadresse mehr. Ein Treffer geht schlicht auf
  // seine Kennung — oder, wenn er noch keine hat, auf seinen Ortesschlüssel,
  // den die Seite beim Öffnen anlegt (`gespraech_anlegen`).
  const L = await import(new URL('composables/nachrichtenLogik.mjs', WURZEL).href)
  assert.equal(typeof L.geschwisterAdresse, 'undefined', 'die Sonderregel ist entfernt')
  assert.equal(L.zeilenAdresse({ name: 'CHAT-2', gruppe: 'chor' }), 'CHAT-2')
  assert.equal(L.zeilenAdresse({ name: null, gruppe: 'leitung', untergruppe: 'leitung-team' }), 'leitung-team')
  assert.equal(L.zeilenAdresse({ name: '', gruppe: 'leitung' }), 'leitung')
  assert.equal(L.zeilenAdresse(null), '')
  // Dieselbe Adresse wie die Listenzeile: der Treffer öffnet den Ort, nicht
  // einen Umweg über das offene Gespräch.
  assert.equal(L.gespraechHash(L.zeilenAdresse({ name: 'CHAT-2' })), '#/nachrichten/CHAT-2')
})

test('CHAT-3c/A: unter 2 Zeichen wird NICHT gefragt', () => {
  assert.equal(S.SUCHE_MIN_ZEICHEN, 2)
  assert.equal(S.darfPersonenFragen(''), false)
  assert.equal(S.darfPersonenFragen('a'), false)
  assert.equal(S.darfPersonenFragen(' a '), false, 'Leerzeichen zählen nicht')
  assert.equal(S.darfPersonenFragen('  a  '), false)
  assert.equal(S.darfPersonenFragen('an'), true)
  assert.equal(S.darfPersonenFragen('Öl'), true, 'Umlaute sind Zeichen')

  // Der Entpreller plant unterhalb der Grenze NICHTS — und ein offener Termin
  // fällt weg (sonst fragte die Suche nach „an“, während „a“ im Feld steht).
  const uhr = uhrAttrappe()
  const gefragt = []
  const b = S.entpreller({ ...uhr, beiFaelligkeit: (q) => gefragt.push(q) })
  assert.equal(b.tippen('a'), false, 'ein Zeichen plant keinen Termin')
  assert.equal(uhr.offen(), 0)
  assert.equal(b.tippen('an'), true, 'zwei Zeichen planen einen')
  assert.equal(uhr.offen(), 1)
  assert.equal(b.tippen('a'), false, 'zurück auf ein Zeichen: der Termin fällt weg')
  assert.equal(uhr.offen(), 0, 'kein Termin mehr offen')
  b.beenden()
})

test('CHAT-3c/A: Entprellung — nur der letzte Tastendruck fragt (300 ms)', () => {
  assert.equal(S.ENTPRELLUNG_MS, 300)
  const geplant = []
  let kennung = 0
  const gefragt = []
  const b = S.entpreller({
    timer: (fn, ms) => { kennung += 1; geplant.push({ id: kennung, fn, ms }); return kennung },
    timerAus: (id) => { const t = geplant.find((g) => g.id === id); if (t) t.weg = true },
    beiFaelligkeit: (q) => gefragt.push(q),
  })
  b.tippen('an'); b.tippen('ann'); b.tippen('anna')
  assert.equal(geplant.filter((g) => !g.weg).length, 1, 'immer nur EIN offener Termin')
  assert.equal(geplant.filter((g) => !g.weg)[0].ms, 300, 'nach 300 ms Ruhe')
  // Nur der letzte Termin ist noch da — er trägt den letzten Begriff.
  geplant.filter((g) => !g.weg)[0].fn()
  assert.deepEqual(gefragt, ['anna'], 'gefragt wird der letzte Begriff, nicht jeder Anschlag')

  // `abbrechen` (Review R1, SOLL b) lässt den Termin fallen, ohne zu beenden.
  b.tippen('bert')
  assert.equal(b.istGeplant(), true)
  b.abbrechen()
  assert.equal(b.istGeplant(), false, 'abbrechen räumt den offenen Termin weg')
  assert.equal(b.tippen('berta'), true, 'danach geht es weiter')

  // Nach `beenden` (Abbau der Seite) kommt kein Aufruf mehr.
  b.beenden()
  assert.equal(b.tippen('bert'), false)
})

test('CHAT-3c/A: veraltete Antwort wird verworfen (nur die letzte Eingabe zählt)', () => {
  assert.equal(S.istAktuell('anna', 'anna'), true)
  assert.equal(S.istAktuell('anna', 'Anna '), true, 'Groß/Klein und Rand zählen nicht')
  assert.equal(S.istAktuell('anna', 'annabell'), false, 'eine neuere Eingabe gewinnt')
  assert.equal(S.istAktuell('annabell', 'anna'), false)
  assert.equal(S.istAktuell('Müller', 'mueller'), true, 'dieselbe Faltung wie der Server')
  assert.equal(S.istAktuell('anna', ''), false, 'ein geleertes Feld ist keine Eingabe')
})

test('CHAT-3c/A: Personentreffer — Profil-Link nur MIT Konto', () => {
  const mit = S.personTreffer({ mitglied: 'M-1', anzeigename: 'Bert Brandner', bild: '/f/x.jpg',
    hat_konto: true, darf_schreiben: true })
  assert.equal(mit.href, '#/mitglied/M-1', 'mit Konto führt aufs bestehende Profil')
  assert.equal(mit.hinweis, '')
  assert.equal(mit.bild, '/f/x.jpg')

  const ohne = S.personTreffer({ mitglied: 'M-2', anzeigename: 'Olaf Ohnberg', bild: '',
    hat_konto: false, darf_schreiben: false })
  assert.equal(ohne.href, '', 'ohne Konto KEIN Ziel — nicht antippbar')
  assert.equal(ohne.hinweis, S.OHNE_KONTO_TEXT)
  assert.equal(ohne.hinweis, 'hat kein Konto')

  // Auch `darf_schreiben: false` bei vorhandenem Konto bleibt antippbar: der
  // Knopf „Nachricht schreiben“ ist CHAT-7, hier gibt es nur das Profil.
  assert.equal(S.personTreffer({ mitglied: 'M-3', anzeigename: 'Self', hat_konto: true,
    darf_schreiben: false }).href, '#/mitglied/M-3')

  assert.equal(S.personTreffer(null), null)
  assert.equal(S.personTreffer({ anzeigename: 'ohne Kennung' }), null, 'ohne Kennung kein Ziel')
  // Die Server-Antwort in Form bringen (unbekannte Treffer fallen weg).
  const liste = S.personenAusAntwort({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', hat_konto: true },
    { mitglied: 'M-2', anzeigename: 'Olaf Ohnberg', hat_konto: false },
    null,
  ], limit: 20 })
  assert.deepEqual(liste.map((p) => p.mitglied), ['M-1', 'M-2'])
  assert.deepEqual(S.personenAusAntwort(null), [], 'kein Trefferfeld → leere Liste')
})

test('CHAT-3c/A: Gespräche werden aus der geladenen Liste gefiltert (Titel)', () => {
  const liste = GESPRAECHE.concat([
    { name: 'CHAT-3', art: 'untergruppe', gruppe: 'chor', untergruppe: 'chor-noten',
      titel: 'Chor – Noten', geoeffnet: true, ungelesen: 0, teilnehmer: 3,
      letzte_nachricht: 'x', letzte_am: '2026-11-18 08:00:00' },
  ])
  const titel = (q) => S.gespraechsTreffer(liste, q).flatMap((a) => a.eintraege.map((z) => z.titel))

  assert.deepEqual(titel('chor'), ['Chor', 'Chor – Noten'], 'Titel-Filter, beide Treffer')
  assert.deepEqual(titel('CHO'), ['Chor', 'Chor – Noten'], 'Groß/Klein egal')
  assert.deepEqual(titel('leitung'), ['Leitung'])
  assert.deepEqual(titel('  '), [], 'leere Suche filtert nicht ins Leere — sie filtert gar nicht')
  assert.deepEqual(titel('gibtsnicht'), [])
  // Die Abschnitte bleiben die der Liste (Gruppe/Untergruppe), nur gefiltert.
  const abschnitte = S.gespraechsTreffer(liste, 'chor')
  assert.deepEqual(abschnitte.map((a) => a.id), ['gruppe', 'untergruppe'])
  assert.equal(abschnitte[0].label, 'Gruppen')
})

test('CHAT-3c/A: Zustand der Personenfläche — ruhe/laedt/fehler/leer/treffer', () => {
  assert.equal(S.personenZustand({ begriff: 'a' }), 'ruhe')
  assert.equal(S.personenZustand({ begriff: '' }), 'ruhe')
  assert.equal(S.personenZustand({ begriff: 'an', laedt: true }), 'laedt')
  // Ein Fehler schlägt das Laden — der Satz bleibt stehen.
  assert.equal(S.personenZustand({ begriff: 'an', laedt: true, fehler: 'Server weg' }), 'fehler')
  assert.equal(S.personenZustand({ begriff: 'an', laedt: false, treffer: [] }), 'leer')
  assert.equal(S.personenZustand({ begriff: 'an', treffer: [S.personTreffer({ mitglied: 'M-1',
    anzeigename: 'Anna', hat_konto: true })] }), 'treffer')
})

test('CHAT-3c/A (MUSS 1): Abschnitte — keine leere „Personen“-Überschrift', () => {
  // Listenmodus: kein Begriff, keine Anfrage → gar nichts.
  const ruhe = S.suchAbschnitte({ gespraeche: [], zustand: 'ruhe', personen: [] })
  assert.equal(ruhe.personen, false, 'im Listenmodus KEIN Abschnitt Personen')
  assert.equal(ruhe.gespraeche.length, 0)
  assert.equal(ruhe.leer, false, 'im Listenmodus kein „Nichts gefunden“')

  // Ein Zeichen: Suche offen, aber niemand gefragt → kein Abschnitt.
  assert.equal(S.suchAbschnitte({ zustand: S.personenZustand({ begriff: 'a' }) }).personen, false)

  // Treffer: GENAU EIN Abschnitt Personen, mit Zeilen und OHNE Status.
  const treffer = S.suchAbschnitte({
    gespraeche: S.gespraechsTreffer(GESPRAECHE, 'chor'),
    zustand: 'treffer',
    personen: [S.personTreffer({ mitglied: 'M-1', anzeigename: 'Anna', hat_konto: true })],
  })
  assert.equal(treffer.personen, true, 'der Abschnitt steht da')
  assert.equal(treffer.personenZeilen.length, 1)
  assert.equal(treffer.personenStatus, false, 'keine zweite Fläche (doppelte Überschrift)')
  assert.equal(treffer.leer, false)

  // Laden/Fehler/leer: Überschrift + Status, keine Zeilen.
  for (const zustand of ['laedt', 'fehler']) {
    const lage = S.suchAbschnitte({ zustand, personen: [] })
    assert.equal(lage.personen, true, `${zustand}: der Abschnitt steht da`)
    assert.equal(lage.personenZeilen.length, 0, `${zustand}: keine Zeilen`)
    assert.equal(lage.personenStatus, true, `${zustand}: die Statusfläche steht`)
  }

  // Leer: der Abschnitt steht (die Trefferfläche bleibt offen), aber OHNE
  // eigenen Leer-Text — den trägt allein `leer` (CHAT-3c-2, SOLL c).
  const leer = S.suchAbschnitte({ zustand: 'leer', personen: [] })
  assert.equal(leer.personen, false, 'leer: KEINE zweite Fläche — sonst stünde die Überschrift über zwei Texten')
  assert.equal(leer.personenZeilen.length, 0, 'leer: keine Zeilen')
  assert.equal(leer.personenStatus, false, 'leer: KEINE zweite Statusfläche')
  assert.equal(leer.leer, true, 'und der EINE Leerzustand steht da')
})

test('CHAT-3c/A (MUSS 1, SOLL c): GENAU EIN Leer-Text', () => {
  // Nichts gefunden (kein Gespräch, keine Person) → GENAU EIN Leerzustand, und
  // KEIN zweiter Text daneben (vorher: „Niemand gefunden …“ UND „Nichts
  // gefunden“).
  const nichts = S.suchAbschnitte({ gespraeche: [], zustand: 'leer', personen: [] })
  assert.equal(nichts.leer, true, 'der Leerzustand steht da')
  assert.equal(nichts.personenStatus, false, 'kein zweiter Leer-Text in der Personenfläche')
  assert.equal(nichts.personenZeilen.length, 0)
  // Gesprächstreffer, aber keine Person: kein globales „Nichts gefunden“.
  const halb = S.suchAbschnitte({
    gespraeche: gespraechstrefferTest(), zustand: 'leer', personen: [],
  })
  assert.equal(halb.leer, false, 'ein Gesprächstreffer reicht — kein zweiter Leer-Text')
  // Fehler: kein „Nichts gefunden“ über der Fehlermeldung.
  assert.equal(S.suchAbschnitte({ zustand: 'fehler', personen: [] }).leer, false)
  // Treffer: kein Leer-Text.
  assert.equal(S.suchAbschnitte({ zustand: 'treffer', personen: [{ mitglied: 'M-1' }] }).leer, false)
})

// ════════════════════════════════════════════════════════════════════════════
// B · ChatSuche.vue gemountet
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

/** Die Komponente mit Attrappen für Netz, Session und Timer. */
async function sucheMontieren({
  antwort = async () => PERSONEN, fehler = null, begriff = '', gespraeche = GESPRAECHE,
} = {}) {
  const ordner = join(TMP, 'suche-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__SUCH')
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const aufrufe = []
  globalThis.__SUCH_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SUCH_SERVER = async (aufruf) => {
    if (/personen_suchen$/.test(String(aufruf?.methode))) {
      if (fehler) throw fehler
      return antwort(aufruf)
    }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten'

  const uhr = uhrAttrappe()
  const gemeldet = []
  const mod = (await import(pathToFileURL(baum('components/chat/ChatSuche.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {
    gespraeche, startBegriff: begriff,
    timer: uhr.timer, timerAus: uhr.timerAus,
    // CHAT-11b: Der Abschnitt „In Nachrichten“ bekommt einen EIGENEN Timer. Er
    // wird hier stillgelegt (kein Termin in DER Uhr dieser Fälle) — die Namen
    // und das Ereignis der Personensuche bleiben sonst unverändert prüfbar;
    // den dritten Abschnitt prüft `tests/chat11b-suche.test.mjs`.
    trefferHolen: async () => ({ treffer: [], mehr: false, vor: null, limit: 20 }),
  }, { horcher: (art, wert) => gemeldet.push({ art, wert }) })
  return { ...gemountet, aufrufe, uhr, gemeldet }
}

/** Die Abschnittsüberschriften der SUCHE (nicht der Liste: `ChatListe.vue`
 *  trägt denselben Klassennamen für „Gruppen“/„Untergruppen“). */
const suchUeberschriften = (host) => [...host.querySelectorAll('.dk-chat-suchergebnis h3.dk-chat-abschnitt-titel')]
  .map((h) => h.textContent.trim())

/**
 * Nur die Abschnitte der PERSONENSUCHE. CHAT-11b stellt einen dritten Abschnitt
 * („In Nachrichten“) daneben — den prüft `tests/chat11b-suche.test.mjs`.
 */
const personenAbschnitte = (host) => suchUeberschriften(host).filter((t) => t !== 'In Nachrichten')

test('CHAT-3c/B (MUSS 1): im Listenmodus keine Überschrift, bei Treffern genau zwei', async () => {
  // CHAT-11b: Die Trefferfläche der Nachrichtensuche wird hier abgeschaltet
  // (Attrappe ohne Treffer), damit dieser Fall weiter GENAU die zwei
  // Abschnitte der Personensuche prüft — den dritten prüft `chat11b-suche`.
  const s = await sucheMontieren()
  // Ohne Eingabe: keine Abschnitte, keine leere „Personen“-Überschrift.
  assert.deepEqual(suchUeberschriften(s.host), [], 'Listenmodus: keine Abschnittsüberschrift')
  assert.equal(s.host.querySelector('.dk-chat-suchergebnis section'), null,
    'im Listenmodus steht KEIN Abschnitt (auch keine leere „Personen“-Überschrift)')
  assert.equal(s.host.textContent.includes('hat kein Konto'), false, 'keine leere Personentreffer-Fläche')

  // Treffer: „Gespräche“ und „Personen“ — jede GENAU EINMAL. Der Begriff
  // „leitung“ trifft das Gespräch „Leitung“ UND (laut Attrappe) die Personen.
  await tippen(s.host, 'leitung')
  await s.uhr.feuern()
  assert.deepEqual(personenAbschnitte(s.host), ['Gespräche', 'Personen'],
    'zwei Abschnitte der Personensuche, untereinander')
  assert.equal(s.host.querySelectorAll('.dk-chat-suchleer').length, 0, 'kein Leer-Text bei Treffern')
  s.abbaum()

  // Nur Personen (kein Gespräch passt): EINE „Personen“-Überschrift.
  const p = await sucheMontieren()
  await tippen(p.host, 'anna')
  await p.uhr.feuern()
  assert.deepEqual(personenAbschnitte(p.host), ['Personen'], 'genau eine Überschrift „Personen“')
  assert.equal(p.host.querySelectorAll('.dk-chat-person').length, 2,
    'die zwei Zeilen der Attrappe — KEINE zweite Fläche daneben')
  p.abbaum()
})

test('CHAT-3c/B (SOLL g): „hat kein Konto“ ist kein Link und trägt kein aria-disabled', async () => {
  const s = await sucheMontieren({ antwort: async () => ({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', bild: '', hat_konto: true, darf_schreiben: true },
    { mitglied: 'M-2', anzeigename: 'Olaf Ohnberg', bild: '', hat_konto: false, darf_schreiben: false },
  ], limit: 20 }) })
  await tippen(s.host, 'an')
  await s.uhr.feuern()

  // Mit Konto: Link auf das bestehende Profil.
  const link = [...s.host.querySelectorAll('a.dk-chat-person')]
  assert.equal(link.length, 1, 'genau EIN Personentreffer ist ein Link')
  assert.equal(link[0].getAttribute('href'), '#/mitglied/M-1')
  assert.match(link[0].textContent, /Anna Beispiel/)

  // Ohne Konto: KEIN Link, ausgegraut, Hinweis — und kein aria-disabled an
  // einem Element, das gar nicht fokussierbar ist.
  const ohne = s.host.querySelector('.dk-chat-person.is-ohne-konto')
  assert.ok(ohne, 'die Person ohne Konto steht da')
  assert.equal(ohne.tagName, 'SPAN', 'ohne Konto ist ein <span>, kein <a> — nicht antippbar')
  assert.equal(ohne.hasAttribute('href'), false)
  assert.equal(ohne.hasAttribute('aria-disabled'), false, 'kein aria-disabled am nicht fokussierbaren <span>')
  assert.match(ohne.textContent, /hat kein Konto/)
  assert.equal(s.host.querySelectorAll('.dk-chat-person.is-ohne-konto a').length, 0,
    'kein Link INNERHALB des Treffers ohne Konto')

  // Ein Klick darauf öffnet nichts.
  const vorher = s.gemeldet.filter((m) => m.art === 'treffer').length
  ohne.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(4)
  assert.equal(s.gemeldet.filter((m) => m.art === 'treffer').length, vorher,
    'ein Klick auf „hat kein Konto“ öffnet nichts')
  s.abbaum()
})

test('CHAT-3c/B: Gesprächstreffer ist ein normaler Link in den Verlauf', async () => {
  const s = await sucheMontieren()
  await tippen(s.host, 'cho')
  const treffer = [...s.host.querySelectorAll('a.dk-chat-treffer')]
    .filter((a) => /Chor/.test(a.textContent))
  assert.equal(treffer.length, 1, 'der Gesprächstreffer steht unter „Gespräche“')
  assert.equal(treffer[0].getAttribute('href'), '#/nachrichten/CHAT-2',
    'Tipp öffnet den Verlauf (dieselbe Adresse wie die Listenzeile)')
  // CHAT-3c-2, MUSS A: Das ist ein Link, kein Knopf mit `pushState` — sonst
  // sähe der Browser nur eine neue Adresse ohne `hashchange` und der Router
  // bliebe stehen. Strg-/Mittelklick findet so ebenfalls sein Ziel.
  assert.equal(treffer[0].tagName, 'A', 'ein echtes <a href>')
  assert.equal(treffer[0].hasAttribute('target'), false, 'kein target — der Sprung bleibt im Tab')
  assert.doesNotMatch(s.host.textContent, /Leitung/, 'die anderen Gespräche sind weg')
  s.abbaum()
})

test('CHAT-3c-2/A (SOLL 7): ein Gesprächstreffer führt auf seine EIGENE Kennung — kein Sonderweg', async () => {
  // Der Such-Eintrag ist kein Zustand eines offenen Gesprächs mehr: der Treffer
  // geht auf sein eigenes Ziel. Am Desktop bleibt das offene Gespräch dadurch
  // stehen (es hängt an `offeneKennung`, nicht an der Trefferadresse).
  const s = await sucheMontieren()
  await tippen(s.host, 'chor')
  const chor = [...s.host.querySelectorAll('a.dk-chat-treffer')].find((a) => /Chor/.test(a.textContent))
  assert.ok(chor, 'der Treffer steht da')
  assert.equal(chor.getAttribute('href'), '#/nachrichten/CHAT-2')
  await tippen(s.host, 'leitung')
  const leitung = [...s.host.querySelectorAll('a.dk-chat-treffer')].find((a) => /Leitung/.test(a.textContent))
  assert.equal(leitung.getAttribute('href'), '#/nachrichten/CHAT-1')
  s.abbaum()

  // Ein nie geöffnetes Geschwister (keine Kennung) → der Ortesschlüssel, den
  // die Seite beim Öffnen anlegt — dieselbe Adresse wie in der Liste.
  const namenlos = [{ ...GESPRAECHE[0] }, {
    name: null, art: 'untergruppe', gruppe: 'leitung', untergruppe: 'leitung-team', titel: 'Leitung – Team',
    geoeffnet: false, ungelesen: 0, teilnehmer: 2, letzte_nachricht: 'x', letzte_am: '2026-11-18 08:00:00',
  }]
  const geschwister = await sucheMontieren({ gespraeche: namenlos })
  await tippen(geschwister.host, 'team')
  const team = [...geschwister.host.querySelectorAll('a.dk-chat-treffer')].find((a) => /Team/.test(a.textContent))
  assert.ok(team, 'der Treffer steht da')
  assert.equal(team.getAttribute('href'), '#/nachrichten/leitung-team',
    'ohne Kennung bleibt es beim Ort — dieselbe Adresse, die die Seite anlegt')
  geschwister.abbaum()
})

test('CHAT-3c/B: Fehlerzustand mit „Erneut versuchen“, leeres Ergebnis mit Text', async () => {
  const s = await sucheMontieren({ fehler: Object.assign(new Error('Kaputt'), { status: 500 }) })
  await tippen(s.host, 'an')
  await s.uhr.feuern()
  assert.match(s.host.textContent, /Personensuche hat nicht geklappt/, 'der Fehler ist sichtbar')
  const erneut = [...s.host.querySelectorAll('button')]
    .filter((b) => /Erneut versuchen/.test(b.textContent || ''))
  assert.equal(erneut.length, 1, '„Erneut versuchen“ steht als Handlung da')

  // Erneut versuchen fragt SOFORT (ohne neue Entprellung) — hier wieder mit Fehler.
  const vorher = s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)).length
  erneut[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(8)
  assert.equal(s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)).length, vorher + 1,
    'der zweite Versuch geht sofort raus')
  // Genau EINE „Personen“-Überschrift — daneben steht CHAT-11b „In Nachrichten“.
  assert.deepEqual(personenAbschnitte(s.host), ['Personen'],
    'die Fehlerfläche steht unter EINER Überschrift „Personen“')
  s.abbaum()

  // Leeres Ergebnis: GENAU EIN Text, kein Fehler, keine zweite Leer-Fläche.
  const leer = await sucheMontieren({ antwort: async () => ({ treffer: [], limit: 20 }) })
  await tippen(leer.host, 'xyz')
  await leer.uhr.feuern()
  assert.match(leer.host.textContent, /Nichts gefunden/, 'der eine Leer-Text steht da')
  assert.doesNotMatch(leer.host.textContent, /Niemand gefunden/,
    'kein zweiter Leer-Text daneben (SOLL c)')
  assert.doesNotMatch(leer.host.textContent, /hat nicht geklappt/)
  assert.equal(leer.host.querySelectorAll('.dk-chat-suchleer').length, 0,
    'kein Leer-Text der Personenfläche mehr')
  assert.equal(leer.host.querySelectorAll('.dk-chat-suchnichts').length, 1,
    'GENAU EIN Leerzustand — gezählt werden beide Klassen')
  assert.deepEqual(personenAbschnitte(leer.host), [], 'und keine Überschrift darüber')
  leer.abbaum()
})

test('CHAT-3c/B: veraltete Antwort wird verworfen (späte Antwort zur alten Eingabe)', async () => {
  // Der Server antwortet für „an“ ERST, wenn schon „bert“ im Feld steht.
  let loeseAn = null
  const antwort = (q) => (q === 'an'
    ? new Promise((loese) => { loeseAn = () => loese({ treffer: [
      { mitglied: 'M-1', anzeigename: 'Anna Beispiel', hat_konto: true },
    ], limit: 20 }) })
    : { treffer: [{ mitglied: 'M-2', anzeigename: 'Bert Brandner', hat_konto: true }], limit: 20 })
  const s = await sucheMontieren({ antwort: ({ parameter }) => antwort(parameter?.q) })

  await tippen(s.host, 'an')
  await s.uhr.feuern() // „an“ ist unterwegs (offen)
  await tippen(s.host, 'bert')
  await s.uhr.feuern() // „bert“ kommt zuerst an und steht
  assert.match(s.host.textContent, /Bert Brandner/)

  // Jetzt kommt die SPÄTE Antwort für „an“ — sie darf nichts mehr ändern.
  loeseAn?.()
  await warte(10)
  assert.doesNotMatch(s.host.textContent, /Anna Beispiel/,
    'die Antwort zur alten Eingabe wird verworfen')
  assert.match(s.host.textContent, /Bert Brandner/, 'die Antwort zur letzten Eingabe bleibt')
  s.abbaum()
})

test('CHAT-3c/B: unter 2 Zeichen kein Aufruf — Suche bleibt offen, Liste nicht darunter', async () => {
  const s = await sucheMontieren()
  await tippen(s.host, 'a')
  await s.uhr.feuern()
  assert.deepEqual(s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)), [],
    'ein Zeichen fragt nicht')
  assert.equal(s.host.querySelector('.dk-chat-suchergebnis') !== null, true, 'die Trefferfläche bleibt stehen')
  assert.match(s.host.textContent, /mindestens 2 Zeichen/, 'und sagt, was fehlt')
  await tippen(s.host, 'an')
  await tippen(s.host, 'a')
  await s.uhr.feuern()
  assert.deepEqual(s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)), [],
    'auch zurück auf ein Zeichen fragt nicht')
  s.abbaum()
})

test('CHAT-3c/B (SOLL b): ein geleertes Feld räumt den offenen Termin weg', async () => {
  const s = await sucheMontieren()
  await tippen(s.host, 'ann')
  // CHAT-11b: Der Abschnitt „In Nachrichten“ hat einen EIGENEN Entpreller und
  // legt SEINEN Termin in DIESE Uhr (der Test gibt beiden dieselbe Attrappe).
  // Beide Termine müssen beim Leeren fallen — genau darum geht es hier.
  assert.equal(s.uhr.offen(), 2, 'je ein Termin (Personen und Nachrichten)')
  await tippen(s.host, '')
  assert.equal(s.uhr.offen(), 0, 'das Leeren nimmt die Termine zurück')
  await s.uhr.feuern()
  assert.deepEqual(s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)), [],
    'nach dem Leeren wird nicht mehr gefragt')
  s.abbaum()
})

test('CHAT-3c/B (MUSS 3): das Feld ist die Quelle — ein neuer `startBegriff` schreibt es nicht weg', async () => {
  // Der Baustein hängt an `gespraeche`; sein `startBegriff` kommt von der
  // Adresse. Tippen und Adresse können sich widersprechen (das war der Fehler:
  // die Adresse schrieb ins Feld und löschte das „a“). Der Baustein muss dem
  // FELD folgen, nicht dem Prop.
  const s = await sucheMontieren({ antwort: async () => ({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', bild: '', hat_konto: true, darf_schreiben: true },
  ], limit: 20 }) })
  await tippen(s.host, 'an')
  await s.uhr.feuern()
  assert.match(s.host.textContent, /Anna Beispiel/, 'Treffer zu „an“ stehen da')

  // Jetzt tippt jemand weiter auf ein Zeichen — der Prop bleibt „an“.
  await tippen(s.host, 'a')
  assert.equal(s.host.querySelector('input#chat-suche').value, 'a', 'das „a“ steht im Feld')
  assert.doesNotMatch(s.host.textContent, /Anna Beispiel/,
    'der Treffer zu „an“ ist weg — die Personenfläche wurde zurückgesetzt')
  assert.match(s.host.textContent, /mindestens 2 Zeichen/, 'stattdessen steht der Hinweis zur Länge')

  // Und ein NEUER `startBegriff` (Zurück vom Profil) wird übernommen.
  assert.equal(s.propSetzen('bert'), true, 'der Prop lässt sich von außen setzen')
  await rendern()
  await warte(10)
  assert.equal(s.host.querySelector('input#chat-suche').value, 'bert',
    'der Begriff von außen ersetzt das Feld (Zurück vom Profil)')
  s.abbaum()
})

test('CHAT-3c/B: ein Treffer ist ein Link (Router folgt), kein totes „treffer“-Ereignis', async () => {
  const s = await sucheMontieren({ antwort: async () => ({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', bild: '', hat_konto: true, darf_schreiben: true },
  ], limit: 20 }) })
  await tippen(s.host, 'cho')
  await s.uhr.feuern()
  // Klick auf den Hintergrund: keine Meldung.
  s.host.querySelector('.dk-chat-suchergebnis')
    .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  assert.deepEqual(s.gemeldet.filter((m) => m.art === 'treffer'), [])

  // CHAT-7a-UI Review R1 Punkt 3: die Komponente fängt den Klick NICHT ab und
  // meldet kein Ziel — der Treffer ist ein normaler `<a href>`, der Browser
  // springt, der Router folgt. Genau das wird hier festgehalten.
  const treffer = [...s.host.querySelectorAll('.dk-chat-suchergebnis a.dk-chat-treffer')]
    .find((a) => /Chor/.test(a.textContent))
  assert.ok(treffer, 'der Gesprächstreffer ist ein Link')
  assert.equal(treffer.getAttribute('href'), '#/nachrichten/CHAT-2', 'sein Ziel steht im href')
  treffer.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  assert.deepEqual(s.gemeldet.filter((m) => m.art === 'treffer'), [],
    'kein zweiter Meldungsweg — der Link trägt das Ziel selbst')

  // Ein Personen-Treffer MIT Konto führt ins Profil — ebenfalls als Link.
  await tippen(s.host, 'anna')
  await s.uhr.feuern()
  const person = s.host.querySelector('a.dk-chat-person')
  assert.ok(person, 'der Personentreffer ist ein Link')
  assert.equal(person.getAttribute('href'), '#/mitglied/M-1')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Nachrichten.vue gemountet — Suchfeld, Verlauf, Quelle der Wahrheit
// ════════════════════════════════════════════════════════════════════════════

/**
 * Der Browser-Verlauf als Attrappe: Einträge, Zeiger, Zurück/Vor.
 * `pushState` schneidet den Vorwärts-Zweig ab (wie ein echter Browser),
 * `replaceState` überschreibt den aktuellen Eintrag.
 *
 * CHAT-3c-2: `pushState`/`replaceState` setzen die Adresse, lösen aber KEIN
 * `hashchange` aus (so macht es der Browser; der Router wartet genau darauf).
 * Ein normaler Link-Sprung (`location.hash = …`) feuert es sehr wohl — das
 * prüfen die neuen Tests, indem sie auf `hashchange` warten.
 */
function verlaufAttrappe(start) {
  const eintraege = [{ hash: start, state: null }]
  let zeiger = 0
  /**
   * Die Adresse setzen (jsdoms `location` — die Seite liest sie von dort).
   * CHAT-3c-2: Ein LINK-Sprung (`location.hash = …`) ist eine Navigation und
   * legt im Browser einen NEUEN Eintrag an — genau das tut `sprung`. Die
   * History-API (`pushState`/`replaceState`) schreibt in ihren eigenen Eintrag.
   */
  // `dom.window.location.hash` ist die Adresse, die die Seite liest — der
  // Verlauf und die Adresse werden zusammen geschrieben (wie im Browser).
  const adresseSchreiben = (wert) => {
    try { dom.window.location.hash = wert } catch { /* egal */ }
  }
  const sprung = (wert) => {
    eintraege.length = zeiger + 1
    eintraege.push({ hash: wert, state: null })
    zeiger = eintraege.length - 1
    adresseSchreiben(wert)
  }
  const attrappe = {
    eintraege,
    stand: () => ({ eintraege: eintraege.map((e) => e.hash), zeiger }),
    get state() { return eintraege[zeiger].state },
    pushState(state, _t, hash) {
      eintraege.length = zeiger + 1
      eintraege.push({ hash, state: state ?? null })
      zeiger = eintraege.length - 1
      if (hash) adresseSchreiben(hash)
    },
    replaceState(state, _t, hash) {
      // EIN Schritt, zwei Wirkungen: Eintrag UND Adresse.
      eintraege[zeiger] = { hash: hash || eintraege[zeiger].hash, state: state ?? null }
      if (hash) adresseSchreiben(hash)
    },
    zurueck(n = 1) {
      zeiger = Math.max(0, zeiger - n)
      adresseSchreiben(eintraege[zeiger].hash)
      dom.window.dispatchEvent(new dom.window.PopStateEvent('popstate', { state: null }))
    },
  }
  attrappe.sprung = sprung
  attrappe.adresseSchreiben = adresseSchreiben
  attrappe.adresse = () => adresse
  return attrappe
}

/**
 * Ein Verlauf MIT Inhalt: zwei Zeilen, damit ein „geleertes Gespräch“ sichtbar
 * wäre (Review R1, MUSS 1: „Test MIT Inhalt“). `halten` lässt den Abruf offen
 * — so prüft der Test, dass ein Takt-Abruf WÄHREND der Suche weiterläuft.
 */
function verlaufMitInhalt(gespraech) {
  return {
    gespraech: gespraech || 'CHAT-1',
    richtung: 'neueste',
    nachrichten: [
      { name: `${gespraech || 'CHAT-1'}-N1`, gespraech: gespraech || 'CHAT-1', text: 'Guten Morgen',
        eigene: false, absender_name: 'Anna Beispiel', erstellt_am: '2026-11-18 09:00:00' },
      { name: `${gespraech || 'CHAT-1'}-N2`, gespraech: gespraech || 'CHAT-1', text: 'Hallo Anna',
        eigene: true, absender_name: 'Ich', erstellt_am: '2026-11-18 09:05:00' },
    ],
  }
}

async function seiteMontieren({ hash = '#/nachrichten', server = null } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__SEITE')
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const aufrufe = []
  globalThis.__SEITE_PUSH = (eintrag) => aufrufe.push(eintrag)
  const gespraechAusAufruf = (liste) => {
    for (let i = liste.length - 1; i >= 0; i -= 1) {
      const p = liste[i]?.parameter
      if (p && typeof p.gespraech === 'string') return p.gespraech
    }
    return ''
  }
  globalThis.__SEITE_SERVER = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz]()
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'personen_suchen') return { treffer: [
      { mitglied: 'M-2', anzeigename: 'Bert Brandner', bild: '', hat_konto: true, darf_schreiben: true },
    ], limit: 20 }
    // Mit INHALT: ein leeres Gespräch ließe „bleibt offen“ und „wird geleert“
    // gleich aussehen (Review R1, MUSS 1).
    if (kurz === 'verlauf') return server?.verlauf
      ? server.verlauf({ gespraech: gespraechAusAufruf(aufrufe) })
      : verlaufMitInhalt(gespraechAusAufruf(aufrufe))
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'gespraech_anlegen') return { name: 'CHAT-1', art: 'gruppe', gruppe: 'leitung' }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  const verlauf = verlaufAttrappe(hash)
  // Die Adresse kommt aus der Attrappe — sie hält ihre eigene (`location.hash`
  // in jsdom ist nicht zuverlässig beschreibbar) und spiegelt sie nur.
  verlauf.adresseSchreiben(hash)
  // `jsdom` gibt `history.state` nur lesend heraus und hält `location` privat
  // — beides ersetzt die Attrappe, sonst schriebe die Seite in einen fremden
  // Verlauf (und `location.hash` bliebe auf einem alten Stand).
  Object.defineProperty(dom.window, 'history', { configurable: true, writable: true, value: verlauf })
  // `location` ist in jsdom nicht ersetzbar: die Attrappe hält Verlauf und
  // Adresse zusammen, indem JEDER Schreibweg auf jsdoms `location` geht.

  // Die Seite führt einen Chat-Takt (echter `setTimeout`, 10 s). Beim Abbau
  // räumt `onUnmounted` ihn ab — was dann noch steht, wird hier eingesammelt,
  // damit der Prozess nach dem letzten Test endet statt ins Zeitlimit zu laufen.
  const gestartet = new Set()
  const origT = globalThis.setTimeout
  const origI = globalThis.setInterval
  globalThis.setTimeout = (fn, ms) => { const id = origT(fn, ms); gestartet.add(id); return id }
  globalThis.setInterval = (fn, ms) => { const id = origI(fn, ms); gestartet.add(id); return id }
  let gemountet = null
  let mod = null
  try {
    mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)).default
    gemountet = await mounten(mod, {})
  } finally {
    globalThis.setTimeout = origT
    globalThis.setInterval = origI
  }
  const abraeumen = () => { for (const t of gestartet) { try { clearTimeout(t); clearInterval(t) } catch { /* egal */ } } }
  const abbaumVorher = gemountet.abbaum
  gemountet.abbaum = () => { abbaumVorher(); abraeumen() }
  // Die Seite gibt `sucheStand` selbst heraus; der Wrapper in `mounten` reicht
  // die Instanz der Seite nach draußen (`instanz.exposed`).
  const stand = () => {
    try {
      const f = gemountet.offen().sucheStand
      return typeof f === 'function' ? f() : null
    } catch { return null }
  }
  // `verlauf` IMMER neu aus `window.history` lesen: die Attrappe wird bei jedem
  // Aufbau ersetzt, und die Seite überschreibt `replaceState` nicht selten.
  const aktuellerVerlauf = () => dom.window.history
  return {
    ...gemountet,
    aufrufe,
    mod,
    verlauf: new Proxy({}, {
      get(_z, name) {
        const v = aktuellerVerlauf()
        if (name === 'sprung') return v.sprung
        const wert = v[name]
        return typeof wert === 'function' ? wert.bind(v) : wert
      },
    }),
    stand,
    zurueck: (n = 1) => aktuellerVerlauf().zurueck(n),
  }
}

/** Tippen im Echtzeit-Entpreller der Seite (300 ms) und fertig warten. */
async function echtTippen(host, wert) {
  const feld = host.querySelector('input#chat-suche')
  assert.ok(feld, 'das Suchfeld steht im DOM')
  feld.value = wert
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern()
  await warte(10)
  await new Promise((loese) => setTimeout(loese, 330))
  await warte(10)
  await rendern()
  return feld
}

test('CHAT-3c/C: das Suchfeld steht ÜBER der Liste — und nur einmal', async () => {
  const s = await seiteMontieren()
  await rendern()
  await warte(12)
  const felder = s.host.querySelectorAll('input#chat-suche')
  assert.equal(felder.length, 1, 'EIN Feld, auch wenn Suche und Liste zusammen stehen')
  assert.equal(felder[0].getAttribute('placeholder'), 'Personen und Gespräche suchen')

  // Es steht in der Listenspalte und VOR der Gesprächsliste.
  const spalte = felder[0].closest('.dk-chat-liste-spalte')
  assert.ok(spalte, 'das Feld steht in der Listenspalte')
  const liste = s.host.querySelector('.dk-chat-liste')
  assert.ok(liste, 'die Gesprächsliste steht da')
  assert.equal(felder[0].compareDocumentPosition(liste) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING,
    dom.window.Node.DOCUMENT_POSITION_FOLLOWING, 'das Feld steht VOR der Liste')
  // Listenmodus: keine Abschnittsüberschrift über der Liste.
  assert.deepEqual(suchUeberschriften(s.host), [], 'im Listenmodus keine „Personen“-Überschrift')
  s.abbaum()
})

test('CHAT-3c/C (MUSS 2): die Suche bekommt EINEN Verlaufseintrag, Tippen ersetzt ihn', async () => {
  const s = await seiteMontieren()
  await warte(12)
  assert.deepEqual(s.verlauf.stand().eintraege, ['#/nachrichten'], 'am Anfang: nur die Liste im Verlauf')

  await echtTippen(s.host, 'b')
  const nachErstem = s.verlauf.stand()
  assert.deepEqual(nachErstem.eintraege, ['#/nachrichten', '#/nachrichten/suche?q=b'],
    'das Öffnen der Suche legt EINEN Eintrag an (push, nicht replace)')
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=b')

  await echtTippen(s.host, 'bert')
  const nachZweitem = s.verlauf.stand()
  assert.deepEqual(nachZweitem.eintraege, ['#/nachrichten', '#/nachrichten/suche?q=bert'],
    'weitere Anschläge ERSETZEN den Eintrag — keine Lesemarke je Tastendruck')
  assert.equal(nachZweitem.eintraege.length, 2)
  assert.match(s.host.textContent, /Bert Brandner/, 'die Treffer stehen da')
  s.abbaum()
})

test('CHAT-3c/C (MUSS 2): Zurück schließt die Suche und zeigt die Liste wieder', async () => {
  const s = await seiteMontieren()
  await warte(12)
  await echtTippen(s.host, 'bert')
  assert.equal(s.host.querySelector('.dk-chat-liste'), null, 'die Suche ersetzt die Liste')
  assert.equal(s.stand()?.offen, true)

  s.zurueck(1)
  await rendern()
  await warte(10)
  assert.equal(dom.window.location.hash, '#/nachrichten', 'Zurück führt auf den Bereich')
  assert.equal(s.stand()?.offen, false, 'und die Suche ist zu')
  assert.ok(s.host.querySelector('.dk-chat-liste'), 'die Liste ist wieder da')
  assert.equal(s.host.querySelector('.dk-chat-suchergebnis section'), null,
    'die Trefferfläche ist leer — keine Treffer mehr')
  s.abbaum()
})

test('CHAT-3c/C (MUSS 2): Zurück aus der Suche stellt ein offenes Gespräch wieder her', async () => {
  // Desktop: ein Gespräch ist offen (`#/nachrichten/CHAT-1`), dann wird gesucht.
  const s = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await warte(14)
  await echtTippen(s.host, 'bert')
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=bert&offen=CHAT-1')
  assert.equal(s.stand()?.offenGespraech, 'CHAT-1', 'das Gespräch bleibt offen, während gesucht wird')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'die rechte Spalte zeigt es weiter')
  assert.equal(s.verlauf.stand().eintraege.length, 2,
    'der Wechsel war EIN Schritt (der Verlauf des Gesprächs bleibt der erste Eintrag)')

  s.zurueck(1)
  await rendern()
  await warte(14)
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-1', 'Zurück führt ins Gespräch zurück')
  assert.equal(s.stand()?.kennung, 'CHAT-1', 'und das Gespräch ist wieder offen')
  assert.equal(s.stand()?.offen, false, 'die Suche ist zu')
  s.abbaum()
})

/**
 * Kurzschreibweisen für die Inhalts-Prüfungen (Review R1): Titel, Zeilen,
 * Abrufe einer Art. Alles, was „ist noch da / ist geleert“ belegen soll,
 * hängt an DIESEN Werten — nicht an Klassen.
 */
const titelDerSeite = (host) => host.querySelector('.dk-chat-verlauf-titel h2')?.textContent.trim() || ''
const zeilenTexte = (host) => [...host.querySelectorAll('.dk-chat-verlaufsliste .dk-chat-blase')]
  .map((el) => el.textContent.trim())
const abrufe = (seite, kurz) => seite.aufrufe.filter((a) => String(a.methode).split('.').pop() === kurz)

test('CHAT-3c-2 (MUSS 1): das erste Zeichen leert das offene Gespräch NICHT — Titel, Zeilen, Takt, Senden', async () => {
  // MIT INHALT (Review R1, MUSS 1): zwei Nachrichten im Verlauf von CHAT-1.
  const s = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await rendern()
  await warte(14)
  await rendern()
  assert.equal(titelDerSeite(s.host), 'Leitung', 'der Titel des offenen Gesprächs steht da')
  assert.deepEqual(zeilenTexte(s.host), ['Guten Morgen', 'Hallo Anna'], 'die Zeilen stehen im Verlauf')
  const verlaufAufrufe = abrufe(s, 'verlauf').length
  const lesestandAufrufe = abrufe(s, 'lesestand_setzen').length
  assert.ok(verlaufAufrufe >= 1, 'der Verlauf wurde geholt')

  // EIN Zeichen: die Suche geht auf. Rechts bleibt ALLES, wie es war.
  await echtTippen(s.host, 'c')
  await rendern()
  await warte(10)
  await rendern()
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=c&offen=CHAT-1')
  assert.equal(titelDerSeite(s.host), 'Leitung', 'der Titel ist NICHT „Gespräch“ geworden')
  assert.deepEqual(zeilenTexte(s.host), ['Guten Morgen', 'Hallo Anna'],
    'die Nachrichten sind NICHT geleert')
  assert.ok(s.host.querySelector('.dk-chat-verlauf'), 'der Verlauf steht rechts')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'die rechte Spalte hängt an der EINEN Kennung')
  // Kein zweites Laden, kein zweiter Lesestand durch die Suche.
  assert.equal(abrufe(s, 'verlauf').length, verlaufAufrufe, 'kein zusätzlicher Verlaufsabruf')
  assert.equal(abrufe(s, 'lesestand_setzen').length, lesestandAufrufe, 'kein zweiter Lesestand')

  // Ein Takt-Abruf läuft weiter — und er holt den Verlauf DES GESPRÄCHS, auch
  // während die Adresse die Suche nennt.
  const vorherTakt = abrufe(s, 'verlauf').length
  // Weit nach dem letzten Abruf: der Takt ist fällig (10 s Grundtakt).
  await s.offen().taktAbrufen(Date.now() + 60000)
  await bis(() => abrufe(s, 'verlauf').length > vorherTakt)
  const neueAbrufe = abrufe(s, 'verlauf').slice(vorherTakt)
  assert.equal(neueAbrufe.length, 1, 'der Takt holt den Verlauf weiter')
  assert.equal(neueAbrufe[0].parameter?.gespraech, 'CHAT-1',
    'der Takt fragt das offene Gespräch, nicht die Suche')
  assert.equal(titelDerSeite(s.host), 'Leitung', 'der Titel bleibt nach dem Takt')

  // Senden aus dem rechten Feld geht an das offene Gespräch.
  const feld = s.host.querySelector('textarea#chat-eingabe')
  assert.ok(feld, 'das Eingabefeld steht da')
  feld.value = 'Noch da'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern()
  const form = s.host.querySelector('form.dk-chat-eingabe')
  form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(12)
  const gesendet = abrufe(s, 'senden')
  assert.equal(gesendet.length, 1, 'die Nachricht ging raus')
  assert.equal(gesendet[0].parameter?.gespraech, 'CHAT-1', '… an das offene Gespräch')
  assert.equal(gesendet[0].parameter?.text, 'Noch da')
  s.abbaum()
})

test('CHAT-3c-2 (SOLL 3): Leeren (✕/Escape/letztes Zeichen) lässt Fokus und Verlauf in Ruhe', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await rendern()
  await warte(14)
  await rendern()
  const verlaufVor = abrufe(s, 'verlauf').length
  const lesestandVor = abrufe(s, 'lesestand_setzen').length

  // Leeren über die ✕-Taste der Suche (der sichtbare Weg) — der Fokus bleibt
  // im Suchfeld, das Gespräch wird NICHT neu geladen.
  const suchFeld = await echtTippen(s.host, 'chor')
  suchFeld.focus()
  const weg = s.host.querySelector('.dk-chat-suchweg')
  assert.ok(weg, 'die ✕-Taste steht da')
  weg.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await rendern()
  await warte(12)
  await rendern()
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-1', 'die Adresse führt ins Gespräch')
  assert.equal(s.stand()?.offen, false, 'die Suche ist zu')
  assert.equal(abrufe(s, 'verlauf').length, verlaufVor, 'der Verlauf wurde NICHT neu geladen')
  assert.equal(abrufe(s, 'lesestand_setzen').length, lesestandVor, 'kein zweiter Lesestand')
  assert.equal(titelDerSeite(s.host), 'Leitung', 'der Titel steht')
  assert.deepEqual(zeilenTexte(s.host), ['Guten Morgen', 'Hallo Anna'], 'die Zeilen stehen')
  assert.equal(dom.window.document.activeElement?.id, 'chat-suche', 'der Fokus bleibt im Suchfeld')

  // Letztes Zeichen löschen (Feld wird leer) — kein Neuladen, gleiche Inhalte.
  const feld = await echtTippen(s.host, 'b')
  feld.focus()
  await echtTippen(s.host, '')
  assert.equal(abrufe(s, 'verlauf').length, verlaufVor, 'auch hier kein dritter Verlaufsabruf')
  assert.equal(abrufe(s, 'lesestand_setzen').length, lesestandVor)
  assert.equal(titelDerSeite(s.host), 'Leitung')
  assert.deepEqual(zeilenTexte(s.host), ['Guten Morgen', 'Hallo Anna'])
  s.abbaum()
})

test('CHAT-3c-2 (SOLL 2): Suche offen + Gespräch offen überlebt den Aufbau (Neuladen, Zurück vom Profil)', async () => {
  // Einen Aufbau mit SUCH-UND-GESPRÄCH-Adresse gibt es im Betrieb nur auf einem
  // Weg: ein Gespräch ist offen (CHAT-1), dann beginnt eine Suche — die
  // Suchadresse führt es als `&offen=` mit. Der Wechsel der Seite ist ein
  // frischer Aufbau (der Router baut die Seite je Adresse neu), also: bauen,
  // suchen, Seite abbauen, mit DIESER Adresse neu bauen. Vorher stellte der
  // Aufbau die Adresse auf das Gespräch und schloss die Suche (Regression
  // gegen Review R1, SOLL e).
  const erst = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await rendern()
  await warte(14)
  await rendern()
  await echtTippen(erst.host, 'bert')
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=bert&offen=CHAT-1',
    'so sieht die Adresse aus (Suche + offenes Gespräch)')
  erst.abbaum()

  const s = await seiteMontieren({ hash: '#/nachrichten/suche?q=bert&offen=CHAT-1' })
  await rendern()
  await warte(16)
  await rendern()

  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=bert&offen=CHAT-1',
    'die Adresse bleibt, wie sie war — nichts wird ersetzt')
  assert.equal(s.stand()?.offen, true, 'die Suche ist offen')
  assert.equal(s.stand()?.begriff, 'bert', 'der Begriff steht')
  assert.equal(s.host.querySelector('input#chat-suche')?.value, 'bert', 'und im Feld')
  assert.ok(s.host.querySelector('.dk-chat-suchergebnis'), 'die Trefferfläche steht da')
  assert.match(s.host.textContent, /Bert Brandner/, 'die Personentreffer sind da')
  assert.equal(s.stand()?.offenGespraech, 'CHAT-1', 'das Gespräch aus `&offen=` steht')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'die rechte Spalte zeigt es')
  assert.equal(titelDerSeite(s.host), 'Leitung', '… mit seinem Titel')
  assert.deepEqual(zeilenTexte(s.host), ['Guten Morgen', 'Hallo Anna'], '… und seinem Verlauf')

  // SOLL 6: GENAU EIN Öffnen (ein Verlaufsabruf, ein Lesestand) — kein
  // Doppel-Abruf aus `onMounted` und Watcher.
  assert.equal(abrufe(s, 'verlauf').length, 1, `genau EIN Verlaufsabruf (war: ${abrufe(s, 'verlauf').length})`)
  assert.equal(abrufe(s, 'lesestand_setzen').length, 1, 'genau EIN Lesestand')
  s.abbaum()
})

test('CHAT-3c-2 (SOLL 5): `offen` gilt nur für ein EIGENES Gespräch', async () => {
  // Fremde Kennung und Ortesschlüssel (Gruppenname) sind KEINE eigenen
  // Gespräche: sie werden ignoriert, es wird nichts geladen und vor allem
  // nichts angelegt (`gespraech_anlegen` darf ein Link nie auslösen).
  for (const wert of ['FREMD-9', 'leitung']) {
    const s = await seiteMontieren({ hash: `#/nachrichten/suche?q=bert&offen=${encodeURIComponent(wert)}` })
    await rendern()
    await warte(16)
    await rendern()
    assert.equal(s.stand()?.offen, true, `${wert}: die Suche bleibt offen`)
    assert.equal(s.stand()?.offenGespraech, '', `${wert}: wird NICHT übernommen`)
    assert.equal(s.stand()?.kennungGesamt, '', `${wert}: rechts steht kein Gespräch`)
    assert.equal(titelDerSeite(s.host), '', `${wert}: kein Verlaufskopf`)
    assert.deepEqual(abrufe(s, 'verlauf'), [], `${wert}: kein Verlaufsabruf`)
    assert.deepEqual(abrufe(s, 'gespraech_anlegen'), [], `${wert}: NIE ein Gespräch anlegen`)
    assert.deepEqual(abrufe(s, 'lesestand_setzen'), [], `${wert}: kein Lesestand`)
    assert.equal(s.host.querySelector('input#chat-suche')?.value, 'bert', `${wert}: die Suche bleibt bedienbar`)
    s.abbaum()
  }

  // Gegenprobe: die EIGENE Kennung wird im selben Weg übernommen.
  const eigen = await seiteMontieren({ hash: '#/nachrichten/suche?q=bert&offen=CHAT-2' })
  await rendern()
  await warte(16)
  await rendern()
  assert.equal(eigen.stand()?.offenGespraech, 'CHAT-2', 'das eigene Gespräch wird übernommen')
  assert.equal(titelDerSeite(eigen.host), 'Chor', '… und steht rechts')
  assert.deepEqual(abrufe(eigen, 'gespraech_anlegen'), [], 'nichts angelegt')
  eigen.abbaum()
})

test('CHAT-3c/C (MUSS 3a): das Feld führt — Zurücklöschen lässt das Getippte stehen', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/suche?q=bert' })
  await warte(14)
  const feld = s.host.querySelector('input#chat-suche')
  assert.equal(feld.value, 'bert', 'der Begriff steht im Feld')
  const eintraegeVorher = s.verlauf.stand().eintraege.length

  // Zwei Zeichen, dann eines weg: das Feld führt, die Adresse folgt still.
  for (const wert of ['an', 'a']) {
    feld.value = wert
    feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
    await warte(10)
    assert.equal(feld.value, wert, `das „${wert}“ bleibt im Feld stehen (die Adresse schreibt es nicht weg)`)
    assert.equal(dom.window.location.hash, `#/nachrichten/suche?q=${wert}`,
      'die Adresse trägt den getippten Begriff (roh, nicht gefaltet)')
    assert.equal(s.stand()?.offen, true, 'die Suche bleibt offen')
    assert.equal(s.verlauf.stand().eintraege.length, eintraegeVorher,
      'Tippen legt keinen zweiten Verlaufseintrag an')
  }
  s.abbaum()
})

test('CHAT-3c-2/B (MUSS B): das erste Zeichen lässt das Gespräch offen, Leeren bringt es zurück', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await warte(14)
  assert.equal(s.stand()?.kennung, 'CHAT-1', 'das Gespräch ist offen')
  assert.deepEqual(s.verlauf.stand().eintraege, ['#/nachrichten/CHAT-1'])

  // EIN Zeichen tippen: Trefferfläche statt Liste — die Liste steht NICHT
  // darunter, das GESPRÄCH aber bleibt rechts offen (Desktop, zweispaltig).
  await echtTippen(s.host, 'c')
  assert.equal(s.host.querySelector('.dk-chat-liste'), null, 'keine volle Liste unter den Treffern')
  assert.ok(s.host.querySelector('.dk-chat-suchergebnis'), 'nur die Trefferfläche')
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=c&offen=CHAT-1',
    'die Suchadresse führt das offene Gespräch mit')
  assert.equal(s.stand()?.offen, true, 'die Suche ist offen')
  assert.equal(s.stand()?.kennung, null, 'die Adresse ist eine Suche — `kennung` bleibt leer')
  assert.equal(s.stand()?.offenGespraech, 'CHAT-1', 'das Gespräch hinter der Suche bleibt offen')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'die rechte Spalte zeigt weiter das Gespräch')
  assert.equal(s.host.querySelector('.dk-chat-liste-spalte.nur-handy-aus'), null,
    'die Listenspalte ist am Desktop NICHT ausgeblendet (Suche braucht sie)')
  assert.ok(s.host.querySelector('.dk-chat-verlauf'), 'rechts steht der Verlauf')
  assert.equal(s.verlauf.stand().eintraege.length, 2,
    'das Öffnen der Suche bleibt EIN Schritt')

  // Weiter tippen: derselbe Eintrag, weiterhin offen.
  await echtTippen(s.host, 'cho')
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=cho&offen=CHAT-1',
    'weitere Anschläge ziehen nur den Begriff nach — das Gespräch bleibt an der Adresse')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'weiterhin dasselbe Gespräch rechts')
  assert.equal(s.verlauf.stand().eintraege.length, 2, 'kein Eintrag je Anschlag')

  // Feld leeren: das Gespräch kommt zurück (ersetzend — kein zweiter Schritt).
  await echtTippen(s.host, '')

  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-1',
    'die Adresse geht auf das Gespräch zurück, nicht auf die Liste')
  assert.equal(s.stand()?.offen, false, 'die Suche ist zu')
  assert.equal(s.stand()?.kennung, 'CHAT-1', 'und das Gespräch ist noch offen')
  assert.ok(s.host.querySelector('.dk-chat-liste'), 'die Liste steht wieder unter dem Feld')
  assert.equal(s.host.querySelectorAll('.dk-chat-liste').length, 1, 'genau EINE Liste')
  assert.equal(s.host.querySelector('.dk-chat-suchergebnis section'), null, 'keine Treffer mehr')
  // „Leeren“ ersetzt den Such-Eintrag durch das Gespräch — der Verlauf endet
  // damit auf dem Gespräch, KEIN zweiter Such-Schritt dazwischen.
  assert.deepEqual(s.verlauf.stand().eintraege.slice(-1), ['#/nachrichten/CHAT-1'],
    'der letzte Eintrag ist das Gespräch (der Such-Eintrag wurde ersetzt)')
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-1')
  s.abbaum()
})

test('CHAT-3c/C (SOLL d): `#/nachrichten/suche` ohne `q` verhält sich wie die Liste', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/suche' })
  await warte(14)
  assert.ok(s.host.querySelector('.dk-chat-liste'), 'die Liste steht da')
  assert.equal(s.host.querySelector('.dk-chat-suchergebnis section'), null,
    'keine Trefferabschnitte')
  assert.equal(s.host.querySelectorAll('h3.dk-chat-abschnitt-titel').length, 1,
    'nur die Abschnitte der LISTE („Gruppen“) — kein Suchabschnitt')
  assert.equal(s.stand()?.offen, false, 'ohne Begriff ist die Suche nicht offen')
  s.abbaum()
})

test('CHAT-3c/C (SOLL e/A): Zurück vom Profil findet die Suche mit Begriff und Treffern', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/suche?q=bert' })
  await rendern()
  await warte(14)
  await rendern()
  const feld = s.host.querySelector('input#chat-suche')
  assert.equal(feld.value, 'bert')

  // Der Profil-Link eines Personentreffers: die Suchadresse BLEIBT stehen.
  const person = s.host.querySelector('a.dk-chat-person')
  assert.ok(person, 'es gibt einen Personentreffer mit Konto')
  assert.match(person.textContent, /Bert Brandner/, 'der Treffer steht vor dem Klick da')
  const vorher = s.verlauf.stand().eintraege.slice()

  // CHAT-3c-2 (MUSS A): Der Klick wird NICHT abgefangen. Er läuft als normaler
  // Link — hier nachgestellt wie im Browser: neue Adresse, dann `hashchange`.
  // Ein `preventDefault`/`pushState` hinterließe eine neue Adresse OHNE
  // `hashchange`; der Router bliebe auf „Nachrichten“ stehen.
  const ereignis = new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })
  const nichtAbgefangen = person.dispatchEvent(ereignis)
  assert.equal(nichtAbgefangen, true, 'der Klick wird nicht abgefangen (kein preventDefault)')
  const hashWache = []
  const horcher = () => hashWache.push(dom.window.location.hash)
  dom.window.addEventListener('hashchange', horcher)
  s.verlauf.sprung(person.getAttribute('href'))
  await tick() // `hashchange` kommt als eigene Aufgabe, nicht im selben Tick
  assert.deepEqual(hashWache, ['#/mitglied/M-2'], 'der Link-Sprung feuert `hashchange` — der Router folgt')
  await warte(6)
  dom.window.removeEventListener('hashchange', horcher)
  assert.deepEqual(s.verlauf.stand().eintraege, [...vorher, '#/mitglied/M-2'],
    'der Treffer hängt sein Ziel an den SUCH-Eintrag (die Suche bleibt davor stehen)')
  assert.equal(s.verlauf.stand().eintraege.length, 2, 'KEIN zusätzlicher Eintrag durch die Seite selbst')

  // Zurück: die Suche steht wieder — mit Begriff und Treffern.
  s.zurueck(1)
  await rendern()
  await warte(14)
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=bert')
  assert.equal(s.host.querySelector('input#chat-suche')?.value, 'bert', 'der Begriff ist wieder da')
  // Die Komponente blieb stehen und kannte den Begriff nicht mehr — die
  // Rückkehr über die Adresse lässt sie NEU fragen (entprellt wie jeder
  // Tastendruck); erst danach stehen die Treffer wieder da.
  await rendern()
  await warte(10)
  await new Promise((loese) => setTimeout(loese, 330))
  await rendern()
  await warte(10)
  // Aufbau aus der Adresse (1), Rückkehr über die Adresse (2, denn `feld`
  // bleibt stehen), „Erneut versuchen“/Rückkehr fragt ein drittes Mal.
  const personenAufrufe = s.aufrufe.filter((a) => /personen_suchen/.test(a.methode)).length
  assert.ok(personenAufrufe >= 2,
    `die Rückkehr über die Adresse fragt erneut (war: ${personenAufrufe})`)
  assert.match(s.host.textContent, /Bert Brandner/, 'und der Treffer auch')
  assert.equal(s.stand()?.offen, true)
  s.abbaum()
})

test('CHAT-3c-2/A: ein Gesprächstreffer öffnet den Verlauf (Link-Sprung, kein pushState)', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/suche?q=chor' })
  await rendern()
  await warte(14)
  await rendern()
  const treffer = [...s.host.querySelectorAll('.dk-chat-suchergebnis a.dk-chat-treffer')]
    .find((a) => /Chor/.test(a.textContent))
  assert.ok(treffer, 'der Gesprächstreffer steht da')
  const vorher = s.verlauf.stand().eintraege.slice()

  const ereignis = new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })
  assert.equal(treffer.dispatchEvent(ereignis), true, 'kein preventDefault am Treffer')

  // Wie im Browser: der Sprung des Links setzt die Adresse und feuert
  // `hashchange` — der Router wechselt darauf die Seite und die Seite öffnet
  // den Verlauf. Ohne das Ereignis bliebe sie auf „Nachrichten“ stehen.
  const hashWache = []
  const horcher = () => hashWache.push(dom.window.location.hash)
  dom.window.addEventListener('hashchange', horcher)
  s.verlauf.sprung(treffer.getAttribute('href'))
  await tick()
  assert.deepEqual(hashWache, ['#/nachrichten/CHAT-2'], 'der Link-Sprung feuert `hashchange`')
  await rendern()
  await warte(14)
  dom.window.removeEventListener('hashchange', horcher)
  assert.deepEqual(s.verlauf.stand().eintraege, [...vorher, '#/nachrichten/CHAT-2'],
    'das Gespräch hängt sich hinter den Such-Eintrag')
  assert.equal(s.stand()?.offen, false, 'die Suche ist zu')
  assert.equal(s.stand()?.kennung, 'CHAT-2', 'und das Gespräch ist offen')
  assert.ok(s.host.querySelector('.dk-chat-verlauf'), 'rechts steht der Verlauf')
  s.abbaum()
})

test('CHAT-3c-2/A/B: am Handy überdeckt die Suche das Gespräch, „zurück“ stellt es her', async () => {
  const s = await seiteMontieren({ hash: '#/nachrichten/CHAT-1' })
  await warte(14)
  await echtTippen(s.host, 'bert')
  // Die Suche trägt das Gespräch hinter sich; das Handy zeigt EINE Spalte —
  // die Trefferfläche überdeckt den Verlauf (Klassen wie die Media-Query sie
  // ausblendet: `nur-handy-aus` an der Liste, `nur-handy-aus-in-rechts` am
  // Verlauf, wenn die Suche ihn überdeckt).
  assert.equal(dom.window.location.hash, '#/nachrichten/suche?q=bert&offen=CHAT-1')
  const spalte = s.host.querySelector('.dk-chat-verlauf-spalte')
  assert.ok(spalte, 'der Verlauf steht im DOM')
  assert.equal(spalte.classList.contains('nur-handy-aus-in-rechts'), false,
    'der Verlauf ist am Handy NICHT ausgeblendet — er IST das Gespräch hinter der Suche')
  const liste = s.host.querySelector('.dk-chat-liste-spalte')
  assert.equal(liste.classList.contains('nur-handy-aus'), false,
    'die Listenspalte trägt die Treffer und bleibt sichtbar')
  assert.ok(s.host.querySelector('.dk-chat-suchergebnis'), 'die Treffer stehen da')

  // Das Gespräch hinter der Suche steht MIT Verlaufskopf im DOM — am Handy
  // blendet die Suchfläche die Spalte aus, „Zurück“ im Kopf ist der Weg
  // dorthin zurück, ohne die Suche zu verlieren.
  assert.ok(s.host.querySelector('.dk-chat-verlauf-kopf'), 'der Verlaufskopf steht da')
  assert.equal(s.stand()?.kennungGesamt, 'CHAT-1', 'und zeigt weiter dasselbe Gespräch')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Router: die Suchadresse bleibt „Nachrichten“ (Verhalten, nicht Regex)
// ════════════════════════════════════════════════════════════════════════════

/**
 * Den ECHTEN Router in einer vm ausführen (Muster von
 * `chat-r2a-navigation.test.mjs`) und die Auflösung befragen — mit Attrappen
 * für Seite, Titel und die Chat-Regel.
 */
function routerVm() {
  let quelle = readFileSync(new URL('router.js', WURZEL), 'utf8')
  quelle = quelle.replace(/^import .*$/gm, '')
  quelle = quelle.replace(/^export \{ modulChatErlaubt \}$/gm,
    "const modulChatErlaubt = (boot = {}) => !!(boot && (boot.is_admin === true || (boot.module_sichtbar || []).includes('chat')))")
  quelle = quelle.replace(/^export \{([^}]*)\}$/gm, '')
  quelle = quelle.replace(/^export /gm, '')
  quelle += '\nglobalThis.routerApi = { routeMap, dynamicRoutes, setzeFenstertitel }'
  const titel = []
  const context = {
    console,
    window: {
      location: { hash: '#/', replace() {} },
      addEventListener: () => {},
      __DIakonosBOOT: { is_admin: true },
      history: { replaceState() {} },
      sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
      localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
      matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    },
    document: { title: '', addEventListener: () => {}, querySelector: () => null },
    // Die Attrappe MERKT sich den Titel — hier wird das Verhalten geprüft.
    setzeFenstertitel: (seite, _win, optionen) => titel.push({ seite, titel: optionen?.titel || '' }),
    darfWebsite: () => true,
    fehlertext: (e) => String(e),
    einrichtungLeitung: {
      EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
      einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
      einrichtungGesehen: () => false,
    },
    rueckwegBleibtGueltig: () => true,
    rueckwegVergessen: () => {},
    ref: (v) => ({ value: v }),
    computed: (fn) => ({ get value() { return fn() } }),
    shallowRef: (v) => ({ value: v }),
    setTimeout, clearTimeout, setInterval, clearInterval, Promise,
  }
  vm.createContext(context)
  vm.runInContext(quelle, context)
  const api = context.routerApi
  /** Seitennamen + Beschriftung einer Adresse — dieselbe Reihenfolge wie der Router. */
  const seite = (hash) => {
    const [pfadRoh] = hash.split('?')
    const pfad = pfadRoh.length > 2 && pfadRoh.endsWith('/') ? pfadRoh.replace(/\/+$/, '') : pfadRoh
    if (api.routeMap[pfad]) return { page: api.routeMap[pfad], titel: '' }
    for (const r of api.dynamicRoutes) {
      if (pfad.match(r.pattern)) return { page: r.page, titel: String(r.titel || '') }
    }
    return null
  }
  return { api, seite, titel }
}

test('CHAT-3c/D: `#/nachrichten/suche` ist die Seite Nachrichten, kein Gespräch', () => {
  const { seite } = routerVm()
  for (const hash of ['#/nachrichten', '#/nachrichten/chat-g-abc', '#/nachrichten/suche', '#/nachrichten/suche?q=anna']) {
    assert.equal(seite(hash)?.page, 'Nachrichten', `${hash} → Seite Nachrichten`)
  }
  // Ein echtes Gespräch bleibt ein Gespräch — die Suche ist KEINE Kennung.
  assert.equal(seite('#/nachrichten/chat-g-abc')?.titel, '', 'ein Gespräch trägt keine Suchbeschriftung')
  // Und die Suche trägt ihren Tab-Titel (SOLL e: Zurück vom Profil).
  assert.equal(seite('#/nachrichten/suche?q=anna')?.titel, 'Suche', 'die Suche nennt ihren Tab „Suche“')
})

// ════════════════════════════════════════════════════════════════════════════
// E · Tokens (SOLL f): keine Rohwerte für Sperrung/Ausgrauung
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-3c/E (SOLL f): Sperrung und Ausgrauung kommen aus Tokens', async () => {
  const tokens = readFileSync(new URL('tokens.css', WURZEL), 'utf8')
  assert.match(tokens, /--ls-klein:\s*[^;]+;/, 'ein Token für die Sperrung kleiner Überschriften')
  assert.match(tokens, /--ausgegraut:\s*[^;]+;/, 'ein Token für die Ausgrauung')

  // Die Komponente setzt beides über das Token — keine Rohwerte mehr.
  const { sucheMontieren: _nichtNoetig } = { sucheMontieren: null }
  const quelle = readFileSync(new URL('components/chat/ChatSuche.vue', WURZEL), 'utf8')
  const stil = quelle.slice(quelle.indexOf('<style'))
  assert.match(stil, /letter-spacing:\s*var\(--ls-klein\)/, 'Sperrung über das Token')
  assert.match(stil, /opacity:\s*var\(--ausgegraut\)/, 'Ausgrauung über das Token')
  assert.doesNotMatch(stil, /letter-spacing:\s*0?\.\d/, 'kein Rohwert für die Sperrung')
  assert.doesNotMatch(stil, /opacity:\s*0?\.\d/, 'kein Rohwert für die Ausgrauung')
})
