/**
 * DEV-B4a — Beziehungen im Bearbeitungsmodus eintragen/entfernen
 * (Befund DMB-72325633c6b5).
 *
 * Vorher zeigte `MitgliedDetail.vue:228-239` die Beziehungen NUR an: im
 * Bearbeiten-Modus gab es weder „Beziehung eintragen" noch „Entfernen", und der
 * Server hatte nur den Lese-Endpunkt. Die Server-Seite sichern die
 * pytest-Tests `backend/tests/test_devb4a_beziehungen.py`; dieser Test haelt
 * fest, was beim Umbau leicht kaputtgeht:
 *
 *  1. Detailseite: der Reiter nutzt den Baustein, reicht `bearbeitbar` aus
 *     dem Bearbeiten-Modus und hat einen ECHTEN Rückgängig-Weg (UX2c) statt
 *     einer Rückfrage.
 *  2. Baustein: „Beziehung eintragen" (Person suchen + Beziehungsart), „Eintragen"
 *     erst wenn Person UND Art gewaehlt sind, „Entfernen" nur im
 *     Bearbeiten-Modus, Rücknahme erst NACH dem Entfernen.
 *  3. Die Beziehungsarten und die Gegenrichtung stimmen mit dem Server
 *     ueberein (eine Quelle — kein zweites Vokabular im Frontend).
 *  4. Alle Aufrufe gehen an die drei whitelist-Endpunkte
 *     `api.beziehungen.*`; nichts schreibt direkt.
 *
 * Mount: der Baustein laeuft im echten DOM (jsdom + @vue/compiler-sfc wie
 * `bs2d2-mount.test.mjs`), gegen eine Attrappe der API.
 */
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const QUELLE = path.join(SRV, 'diakonos')
const BAUTEIL = path.join(SRV, 'diakonos/components/mitglieder/MitgliedBeziehungen.vue')
const DETAIL = path.join(SRV, 'diakonos/pages/MitgliedDetail.vue')
// Das Frontend-Stage des Image-Builds legt gelesene Server-Dateien flach
// nach /backend (backend/Dockerfile, Regel 13); im Worktree liegen sie unter
// backend/src. Beides wird gesucht (Muster `ux2c-endgueltig.test.mjs`).
const BACKEND = [
  resolve(HIER, '..', '..', 'backend'),
  resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app'),
].find(p => existsSync(resolve(p, 'api', 'beziehungen.py')))
  || resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app')

const lies = (abs) => readFileSync(abs, 'utf8')

// ═══ 1. Detailseite: Reiter, Bearbeiten-Zustand, Rückgängig ═══════════════

test('DEV-B4a: der Reiter „Beziehungen" nutzt den Baustein und reicht den Bearbeiten-Modus', () => {
  const quelle = lies(DETAIL)
  assert.match(quelle,
    /import MitgliedBeziehungen from '\.\.\/components\/mitglieder\/MitgliedBeziehungen\.vue'/)
  const stelle = quelle.match(/<MitgliedBeziehungen[\s\S]*?\/>/)
  assert.ok(stelle, 'Baustein im Reiter „Beziehungen"')
  assert.match(stelle[0], /activeTab === 'beziehungen'/, 'haengt am Reiter')
  assert.match(stelle[0], /:bearbeitbar="isEditing && canEdit"/, 'Nachtrag nur im Bearbeiten-Modus')
  assert.match(stelle[0], /:beziehungen="mitglied\?\.beziehungen \|\| \[\]"/, 'Liste aus der Detailantwort')
  assert.match(stelle[0], /@entfernen="beziehungEntfernen"/)
  assert.match(stelle[0], /@geaendert="loadMitglied"/, 'nach dem Eintragen neu laden')
  // Die alte, nur lesende Fassung ist weg (kein zweiter Beziehungs-Block).
  assert.ok(!/<div v-for="b in mitglied\.beziehungen"/.test(quelle),
    'die alte Nur-Anzeige ist ersetzt, nicht verdoppelt')
})

test('DEV-B4a: der Reiter „Beziehungen" ist nur für die Verwaltung sichtbar', () => {
  // Review 10.11.: Die Endpunkte verlangen Verwaltungsrecht — die Auswahl
  // zählt alle Personen auf. Also darf der Reiter nicht bei jedem stehen
  // (wie „Zugang", P1-8/OP-ADMIN-2).
  const quelle = lies(DETAIL)
  const stelle = quelle.match(/const tabs = computed\(\(\) => \{[\s\S]*?\n\}\)/)
  assert.ok(stelle, 'Reiterliste vorhanden')
  assert.match(stelle[0], /\.\.\.\(canEdit\.value \? \[\{ key: 'beziehungen'/,
    '„Beziehungen" nur mit Verwaltungsrecht')
  assert.ok(!/^\s*\{ key: 'beziehungen'/m.test(stelle[0]),
    'kein unbedingter Beziehungen-Reiter')
})

test('DEV-B4a: Entfernen ist sofort wirksam mit „Rückgängig" (UX2c) — keine Rückfrage', () => {
  const quelle = lies(DETAIL)
  const koerper = quelle.match(/async function beziehungEntfernen\(b\) \{[\s\S]*?\n\}/)
  assert.ok(koerper, 'beziehungEntfernen vorhanden')
  const code = koerper[0]
  assert.match(code, /api\.beziehungen\.remove_beziehung/)
  // Kein Bestätigungsdialog fuer etwas Umkehrbares (I2).
  assert.ok(!/\bbestaetigen\(/.test(code), 'kein Bestätigungsdialog beim Entfernen')
  assert.ok(!/\bconfirm\(/.test(code), 'kein Browser-confirm')
  // Die Rücknahme laeuft ueber den EINEN Rückgängig-Weg.
  assert.match(code, /mitRueckgaengig\(\{/)
  assert.match(code, /api\.beziehungen\.add_beziehung/)
  const rueck = code.match(/zurueck: \(\) => apiCall\('diakronos\.diakonos\.api\.beziehungen\.add_beziehung'[\s\S]*?\}\),/)
  assert.ok(rueck, 'Rücknahme trägt dieselbe Beziehung wieder ein')
  assert.match(rueck[0], /person_id: rueck\.beziehung_zu/, 'Rücknahme nutzt die Server-Angabe')
  assert.match(rueck[0], /beziehungsart: rueck\.beziehungsart/)
  assert.match(code, /danach: loadMitglied/, 'Liste nach der Rücknahme neu laden')
})

// ═══ 2. Beziehungsarten und Gegenrichtung: eine Quelle ═════════════════════

test('DEV-B4a: Arten und Gegenrichtung stimmen mit dem Server überein', () => {
  // Der Server haelt BEZIEHUNGSARTEN und INVERS (api/beziehungen.py).
  const server = lies(resolve(BACKEND, 'api', 'beziehungen.py'))
  const artenBlock = server.match(/BEZIEHUNGSARTEN[^=]*=\s*\(([\s\S]*?)\)/)
  assert.ok(artenBlock, 'BEZIEHUNGSARTEN im Server')
  const arten = [...artenBlock[1].matchAll(/"([^"]+)"/g)].map(m => m[1])
  assert.deepEqual([...arten].sort(), ['Ehepartner', 'Elternteil', 'Geschwister', 'Kind', 'Sonstiges'])

  const bauteil = lies(BAUTEIL)
  const frontBlock = bauteil.match(/^export const BEZIEHUNGSARTEN = \[([^\]]*)\]/m)
  assert.ok(frontBlock, 'BEZIEHUNGSARTEN im Baustein')
  const frontArten = [...frontBlock[1].matchAll(/'([^']+)'/g)].map(m => m[1])
  assert.deepEqual([...frontArten].sort(), [...arten].sort(),
    'Frontend und Server nennen dieselben Beziehungsarten')

  const inversBlock = server.match(/INVERS[^=]*=\s*\{([\s\S]*?)\}/)
  assert.ok(inversBlock, 'INVERS im Server')
  const serverInvers = Object.fromEntries(
    [...inversBlock[1].matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(m => [m[1], m[2]]))
  const frontInversBlock = bauteil.match(/^export const GEGENRICHTUNG = \{([\s\S]*?)\n\}/m)
  assert.ok(frontInversBlock, 'INVERS im Baustein')
  const frontInvers = Object.fromEntries(
    [...frontInversBlock[1].matchAll(/(\w+):\s*'([^']+)'/g)].map(m => [m[1], m[2]]))
  assert.deepEqual(frontInvers, serverInvers, 'Gegenrichtung ist im Frontend dieselbe')
  for (const art of Object.keys(serverInvers)) {
    assert.equal(serverInvers[serverInvers[art]], art, `INVERS ist involutiv (${art})`)
  }
})

// ═══ 3. Server-Endpunkte: POST + Rechte ════════════════════════════════════

test('DEV-B4a: die schreibenden Endpunkte sind POST (CSRF) und pruefen die Verwaltung', () => {
  const server = lies(resolve(BACKEND, 'api', 'beziehungen.py'))
  for (const fn of ['add_beziehung', 'remove_beziehung']) {
    const stelle = server.match(new RegExp(`@whitelist\\(methods=\\["POST"\\], allow_guest=False\\)\\ndef ${fn}\\(`))
    assert.ok(stelle, `${fn} ist @whitelist(methods=["POST"])`)
    const koerper = server.slice(server.indexOf(`def ${fn}(`)).split('\n\n\n')[0]
    // Review 10.11.: nicht mehr das Zeilenrecht, sondern die Rolle.
    assert.match(koerper, /_pruefe_verwaltung\(\)/, `${fn} prueft das Verwaltungsrecht`)
  }
  // Auch der Lese-Endpunkt der Auswahlliste verlangt die Verwaltung: er zaehlt
  // ALLE waehlbaren Personen auf und ginge an der Sichtbarkeit vorbei.
  const auswahl = server.slice(server.indexOf('def get_beziehungen_auswahl('))
    .split('\n\n\n')[0]
  assert.match(auswahl, /_pruefe_verwaltung\(\)/)
  assert.ok(!/_pruefe_edit\(/.test(server), 'die alte Zeilenrecht-Pruefung ist weg')
})

// ═══ 4. Mount-Test: der Baustein im echten DOM ═════════════════════════════

function dokumentBauen() {
  return import('jsdom').then(({ JSDOM }) => {
    const dom = new JSDOM('<!doctype html><html><body></body></html>', {
      url: 'http://localhost/diakronos/',
      pretendToBeVisual: true,
    })
    const { window } = dom
    globalThis.window = window
    globalThis.document = window.document
    globalThis.localStorage = window.localStorage
    globalThis.HTMLElement = window.HTMLElement
    globalThis.SVGElement = window.SVGElement
    globalThis.Element = window.Element
    globalThis.Node = window.Node
    globalThis.Event = window.Event
    globalThis.MouseEvent = window.MouseEvent
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    window.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token' }
    return window
  })
}

/** .vue-Bauteil als `.mjs` neben seinen Quellbaum schreiben (wie bs2d2). */
function bauteilSchreiben(abs, ausgabe, wache = new Set(), zielVorgabe = undefined) {
  if (wache.has(abs)) return
  wache.add(abs)
  const quelle = lies(abs)
  const { descriptor } = parse(quelle, { filename: abs })
  const id = path.basename(abs)
  assert.ok(descriptor.script || descriptor.scriptSetup, `${id}: kein Skript`)
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  // Der ERSTE `<script>`-Block (ohne `setup`) eines Bauteils wird beim
  // Kompilieren NICHT mitgenommen — er steht hier nicht zur Pruefung an.
  // Ein Export daraus (`mitgliedBeziehungenApi`) wird durch einen Ersatz
  // bedient, damit der Baustein allein laedt (siehe Test 5).
  skript.content = skript.content.replace(
    /\nexport const mitgliedBeziehungenApi = \{[\s\S]*?\n\}\n/,
    '\nconst mitgliedBeziehungenApi = { auswahl: async () => ({ data: [] }), eintragen: async () => ({}) }\n',
  )
  let code = skript.content
  // Ziel im Temp-Baum: Vorgabe der Aufrufer (Geschwister-Bauteil NEBEN dem
  // Elternteil), sonst der eigene Pfad ab `src/`.
  const rel = zielVorgabe === undefined ? path.relative(SRV, abs) : zielVorgabe
  // Nur IMPORTE werden umgeschrieben — nicht jeder Text in Anfuehrungszeichen
  // (Kompilierter Vorlagencode baut Klassennamen wie `dk-ma-eintrag`, ein
  // Muster ueber `from` hinaus wuerde daran haengen bleiben).
  // Die Ersetzungsfunktion muss das GANZE Trefferstueck liefern (`vor + q +
  // pfad + q`) — sonst steht das `from ` bei jedem Treffer noch einmal davor.
  code = code.replace(/(from\s+|import\s*\()(['"])(\.\.?\/[^'"]+)\2/g,
    (ganz, vor, q, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue') || pfad.endsWith('.js') || pfad.endsWith('.mjs')) {
      // Der Import im Temp-Baum behaelt SEINE Form (`./x` oder `../ui/x`) —
      // nur die Endung wird `.mjs`. Umbauen wuerde die Ordnerlage verfaelschen.
      const neuPfad = pfad.replace(/\.(vue|js|mjs)$/, '.mjs')
      // Geschwister (`.vue`) und Module (`.js`) landen im Temp-Baum unter
      // demselben Weg wie die Quelle ab `src/`: `../MitgliedAuswahl.vue` ->
      // `diakonos/components/MitgliedAuswahl.mjs`, `../ui/DkCard.vue` ->
      // `diakonos/components/ui/DkCard.mjs`. Dann stimmt der Import gleich
      // darunter ohne Umbau.
      const zielRel = path.posix.join(path.posix.dirname(rel), neuPfad)
      if (zielAbs.endsWith('.vue')) {
        bauteilSchreiben(zielAbs, ausgabe, wache, zielRel)
      } else {
        modulSchreiben(zielAbs, ausgabe, wache, zielRel)
      }
      return vor + q + neuPfad + q
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, rel.replace(/\.vue$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

/**
 * Ein JS-Modul kopieren. `abs` ist der ECHTE Pfad (zum Lesen), `rel` der Pfad
 * im Temp-Baum (zum Schreiben) — beim Kopieren einer `.vue` liegen beide
 * auseinander (Quelle: `src/diakonos/...`, Ziel: `src/diakonos/...mjs`).
 */
function modulSchreiben(abs, ausgabe, wache = new Set(), rel = null) {
  if (wache.has(abs)) return
  wache.add(abs)
  let code = lies(abs)
  // Nur IMPORTE werden umgeschrieben — nicht jeder Text in Anfuehrungszeichen
  // (Kompilierter Vorlagencode baut Klassennamen wie `dk-ma-eintrag`, ein
  // Muster ueber `from` hinaus wuerde daran haengen bleiben).
  // Die Ersetzungsfunktion muss das GANZE Trefferstueck liefern (`vor + q +
  // pfad + q`) — sonst steht das `from ` bei jedem Treffer noch einmal davor.
  code = code.replace(/(from\s+|import\s*\()(['"])(\.\.?\/[^'"]+)\2/g,
    (ganz, vor, q, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue')) {
      const neuPfad = pfad.replace(/\.vue$/, '.mjs')
      bauteilSchreiben(
        zielAbs, ausgabe, wache,
        path.posix.join(path.posix.dirname(rel || path.relative(SRV, abs)),
                        path.posix.basename(neuPfad)),
      )
      return vor + q + neuPfad + q
    }
    if (pfad.endsWith('.js') || pfad.endsWith('.mjs')) {
      const neuPfad = pfad.replace(/\.(js|mjs)$/, '.mjs')
      modulSchreiben(
        zielAbs, ausgabe, wache,
        path.posix.join(path.posix.dirname(rel || path.relative(SRV, abs)), neuPfad),
      )
      return vor + q + neuPfad + q
    }
    return ganz
  })
  const zielRel = rel || path.relative(SRV, abs)
  const zielDatei = path.join(ausgabe, zielRel.replace(/\.(js|mjs)$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

/** Baustein rendern; `antwort` beantwortet jeden API-Aufruf. */
async function rendern({ bearbeitbar = true, beziehungen = [], antwort = null } = {}) {
  const window = await dokumentBauen()
  const rufe = []
  const gemeldet = []
  // Der Baustein bekommt die Server-Aufrufe als Eigenschaft (die Seite
  // reicht `mitgliedBeziehungenApi` durch) — hier zaehlt die Attrappe mit.
  const api = async (methode, argumente) => {
    rufe.push({ methode, rumpf: argumente })
    const daten = antwort
      ? antwort(`diakronos.diakonos.api.beziehungen.${methode}`, argumente)
      : { success: true, data: [] }
    return daten
  }

  // Jeder Zeitgeber des Laufs wird gemerkt (jsdom/Node): nach dem Unmount
  // muessen alle aus sein, sonst greift ein spaeter Tick in das gerade
  // geloeschte Temp-Verzeichnis (im Image gemessen: 10 gruen, Prozess rot).
  const zeitgeber = new Set()
  const setTimeoutOriginal = globalThis.setTimeout
  globalThis.setTimeout = (fn, ms, ...rest) => {
    const t = setTimeoutOriginal((...a) => { zeitgeber.delete(t); fn(...a) }, ms, ...rest)
    zeitgeber.add(t)
    return t
  }
  const ausgabe = mkdtempSync(path.join(tmpdir(), 'devb4a-'))
  bauteilSchreiben(BAUTEIL, ausgabe)
  const modules = path.join(ausgabe, 'node_modules')
  symlinkSync(path.join(FRONTEND, 'node_modules'), modules, 'dir')
  {
    const { createApp, nextTick } = await import('vue')
    const modul = await import(pathToFileURL(
      path.join(ausgabe, path.relative(SRV, BAUTEIL).replace(/\.vue$/, '.mjs')),
    ).href)
    const bauteil = modul.default
    const ziel = window.document.createElement('div')
    window.document.body.appendChild(ziel)
    const app = createApp(bauteil, {
      mitgliedId: 'M-anna', beziehungen, bearbeitbar, api,
      melden: (text, art) => { gemeldet.push({ text, art }) },
    })
    app.config.warnHandler = () => {}
    app.mount(ziel)
    await warte()
    await nextTick()
    return { window, ziel: app._container, rufe, app, nextTick, gemeldet, ausgabe, zeitgeber }
  }
}

/**
 * Abbau NACH dem Unmount: ein offener Vue-Scheduler (nextTick) oder ein
 * Zeitgeber aus dem Bauteil wuerde auf das geloeschte Temp-Verzeichnis
 * zugreifen und den Lauf mit ENOENT scheitern lassen (im Image gemessen:
 * „10 gruen, Prozess rot“). Erst `abwarten(ms)`, dann `rmSync`.
 */
async function abbauen(ctx) {
  try { ctx.app.unmount() } catch { /* schon weg */ }
  ctx.zeitgeber?.forEach((t) => clearTimeout(t))
  await ruhe(80)
  try { ctx.window?.close?.() } catch { /* jsdom */ }
  try { rmSync(ctx.ausgabe, { recursive: true, force: true }) } catch { /* egal */ }
}

const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()

/** Kurz warten — begrenzt, damit ein haengendes Laden den Lauf nicht blockiert. */
const warte = (ms = 30) => new Promise((r) => setTimeout(r, ms))
// refresh:false fuer den Warte-Timer: ein Neuladen (rerender) innerhalb des
// Bauteils wuerde sonst in den Scheduler greifen, waehrend das Temp-Verzeichnis
// gerade abgebaut wird (im Image gemessen: 10 gruen, Prozess rot).
const ruhe = (ms = 30) => new Promise((r) => setTimeout(r, ms)).then(() => undefined)
const knopf = (el, teil) => [...el.querySelectorAll('button')].find(b => text(b).includes(teil))

const BEISPIEL = [
  { name: 'MBZ-1', beziehung_zu: 'M-bruno', beziehung_zu_name: 'Bruno Beispiel', beziehungstyp: 'Kind' },
  { name: 'MBZ-2', beziehung_zu: 'M-clara', beziehung_zu_name: 'Clara Beispiel', beziehungstyp: 'Ehepartner' },
]

test('DEV-B4a: Ansicht zeigt die Beziehungen, OHNE Bearbeiten keine Aktionen', async () => {
  const ctx = await rendern({ bearbeitbar: false, beziehungen: BEISPIEL })
  const { ziel, app } = ctx
  const inhalt = text(ziel)
  assert.match(inhalt, /Bruno Beispiel/)
  assert.match(inhalt, /Clara Beispiel/)
  assert.match(inhalt, /2 Beziehungen/)
  assert.ok(!knopf(ziel, 'Beziehung eintragen'), 'kein Nachtrag ohne Bearbeiten-Modus')
  assert.ok(!knopf(ziel, 'Entfernen'), 'kein Entfernen ohne Bearbeiten-Modus')
  await abbauen(ctx)
})

test('DEV-B4a: leerer Zustand nennt die Lage und bietet im Bearbeiten „Beziehung eintragen"', async () => {
  const ctx = await rendern({ beziehungen: [] })
  const { ziel, app } = ctx
  assert.match(text(ziel), /Keine Beziehungen eingetragen\./)
  assert.ok(knopf(ziel, 'Beziehung eintragen'), '„Beziehung eintragen" im Bearbeiten-Modus')
  await abbauen(ctx)
})

test('DEV-B4a: „Eintragen" erst mit Person UND Art; der Klick ruft add_beziehung', async () => {
  const ctx = await rendern({
    beziehungen: [],
    antwort: (url) => {
      if (url.includes('get_beziehungen_auswahl')) {
        return { success: true, data: [
          { mitglied: 'M-bruno', name: 'Bruno Beispiel', in_beziehung: false },
        ] }
      }
      return { success: true, bestand: false }
    },
  })
  const { ziel, app, rufe, nextTick } = ctx
  knopf(ziel, 'Beziehung eintragen').dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await nextTick()
  await warte()

  // Formular offen: Person-Suche und Beziehungsart stehen da.
  assert.match(text(ziel), /Beziehungsart/)
  const eintragen = knopf(ziel, 'Eintragen')
  assert.ok(eintragen, 'Eintragen-Knopf')
  assert.equal(eintragen.disabled, true, 'ohne Person gesperrt (ungültiges nicht anbieten)')

  // Auswahlliste oeffnen -> Server filtert -> Bruno waehlen.
  const eingabe = ziel.querySelector('.dk-ma-input')
  assert.ok(eingabe, 'Personensuche vorhanden')
  eingabe.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await nextTick()
  await warte(350)   // Auswahlliste entprellt (250 ms) und laedt dann
  await nextTick()
  assert.ok(rufe.some(r => r.methode === 'get_beziehungen_auswahl'),
    'Auswahl kommt vom Server')
  const eintrag = [...ziel.querySelectorAll('.dk-ma-eintrag')]
    .find(e => text(e).includes('Bruno Beispiel'))
  assert.ok(eintrag, 'Bruno steht in der Auswahlliste')
  eintrag.dispatchEvent(new globalThis.MouseEvent('mousedown', { bubbles: true }))
  await nextTick()
  assert.equal(knopf(ziel, 'Eintragen').disabled, false, 'mit Person UND Art eintragbar')

  knopf(ziel, 'Eintragen').dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await warte()
  const ruf = rufe.find(r => r.methode === 'add_beziehung')
  assert.ok(ruf, 'add_beziehung wurde aufgerufen')
  // Der volle whitelist-Pfad steht in `mitgliedBeziehungenApi` (Test 5).
  assert.equal(ruf.rumpf.mitglied_id, 'M-anna')
  assert.equal(ruf.rumpf.person_id, 'M-bruno')
  assert.equal(ruf.rumpf.beziehungsart, 'Kind')
  await abbauen(ctx)
})

test('DEV-B4a: „Entfernen" meldet die Zeile nach oben (Seite zeigt „Rückgängig")', async () => {
  const ctx = await rendern({ beziehungen: BEISPIEL })
  const { ziel, app } = ctx
  const weg = knopf(ziel, 'Entfernen')
  assert.ok(weg, 'Entfernen-Knopf im Bearbeiten-Modus')
  // K4/N8: der Knopf nennt die Person (aria-label), nicht nur „Entfernen".
  // `DkButton` reicht `aria-label` durch; geprueft wird am Knopf MIT Text
  // (die anderen Knoepfe am Bauteil tragen keines).
  const beschriftet = [...ziel.querySelectorAll('button')]
    .filter(b => (b.getAttribute('aria-label') || '').includes('Bruno Beispiel'))
  assert.equal(beschriftet.length, 1, 'genau der Entfernen-Knopf nennt Bruno Beispiel')
  let zeile = null
  // Der Emit geht an die Detailseite (`@entfernen="beziehungEntfernen"`).
  const vm = app._instance
  const original = vm.emit
  vm.emit = (name, ...args) => {
    if (name === 'entfernen') zeile = args[0]
    return original.call(vm, name, ...args)
  }
  weg.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await warte()
  assert.ok(zeile && zeile.name === 'MBZ-1', 'die Zeile wird nach oben gemeldet')
  await abbauen(ctx)
})

// ═══ 5. Testliste (Build) ══════════════════════════════════════════════════

test('DEV-B4a: der Server-Vertrag nennt die whitelist-Pfade (Seite reicht sie durch)', () => {
  const quelle = lies(DETAIL)
  // Die Aufrufe stehen in `mitgliedBeziehungenApi` (reines <script>): volle
  // whitelist-Namen, damit die Seite nur durchreichen muss.
  for (const fn of ['get_beziehungen_auswahl', 'add_beziehung']) {
    assert.match(quelle, new RegExp(`diakronos\\.diakonos\\.api\\.beziehungen\\.${fn}`),
      `Aufruf nennt diakronos.diakonos.api.beziehungen.${fn}`)
  }
  // Die Detailseite reicht die Aufrufe durch (eine Stelle im Seiten-Skript).
  assert.match(quelle, /:api="beziehungenApi"/)
  assert.match(quelle, /get_beziehungen_auswahl/)
  assert.match(quelle, /add_beziehung/)
  // Der Baustein selbst spricht nicht mit dem Server (kein eigenes apiCall).
  const bauteil = lies(BAUTEIL)
  assert.ok(!/apiCall\(/.test(bauteil), 'der Baustein ruft kein apiCall selbst')
})

test('DEV-B4a: der Test laeuft im Image-Build (frontend/tests/testliste.txt)', () => {
  const liste = lies(path.join(FRONTEND, 'tests', 'testliste.txt'))
  const muster = liste.split('\n').map(z => z.trim()).filter(z => z && !z.startsWith('#'))
  assert.ok(muster.some(m => m === 'tests/dev-b4a-*.test.mjs'),
    'Muster tests/dev-b4a-*.test.mjs fehlt in frontend/tests/testliste.txt')
})
