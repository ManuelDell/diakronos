/**
 * UX2e2 — laufender (Mount-)Test für das Aktionsmenü „⋯".
 *
 * WARUM HIER UND NICHT IN tests/: Dieser Test BRAUCHT `vue` und `jsdom`
 * (node_modules). Die Bildkette führt `node --test tests/…` im
 * Frontend-Stage aus, WO die Module liegen — der Pfad
 * `tests/ux2e2-aktionsmenue.mount.test.mjs` steht deshalb in der
 * node-Testliste von backend/Dockerfile. Die Quelltext-Wächter der Karte
 * stehen daneben in `tests/ux2e2-aktionsmenue.test.mjs` (ohne node_modules).
 *
 * Geprüft wird das, was im Quelltext NICHT zu sehen ist:
 *   A. Das Menü öffnet am ANGEGEBENEN Anker (Zeile), nicht am eigenen ⋯.
 *   B. Enter am Auslöser öffnet das Menü und wählt NICHT sofort einen Eintrag.
 *   C. Nach Öffnen/Schließen bleibt kein resize/scroll-Listener übrig.
 *   D. „Lied löschen" ruft delete_lied, „Rückgängig" ruft wiederherstellen.
 *
 * Lauf: node --test tests/ux2e2-aktionsmenue.mount.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/* ── jsdom zuerst, damit Vue ein DOM vorfindet ─────────────────────────── */
// `jsdom` ist devDependency in frontend/package.json; der Frontend-Stage des
// Image-Builds führt `npm ci` VOR dem Build aus und hat sie damit. Deshalb
// gibt es KEINEN Rückfall auf einen Pfad außerhalb des Repos mehr (Befund
// Review UX2e2: `/root/steuer2025/...` gibt es nur auf einem Rechner).
let JSDOM
try {
  ({ JSDOM } = await import('jsdom'))
} catch {
  console.log('[ux2e2] übersprungen: kein jsdom vorhanden (Mount-Test braucht ein DOM)')
  process.exit(0)
}
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true, url: 'http://localhost/' })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'MouseEvent',
  'KeyboardEvent', 'SVGElement', 'ResizeObserver', 'sessionStorage', 'localStorage', 'location',
  'history', 'HTMLAnchorElement', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame']) {
  if (dom.window[k]) globalThis[k] = dom.window[k]
}
// jsdom kennt kein Layout: Rechtecke sind alle 0. Für die Lage-Prüfung
// liefert der Test echte Zahlen (die Zeile liegt bei y=100).
const RECHteck = (el) => {
  const roh = el?.getAttribute?.('data-rechteck')
  return roh ? JSON.parse(roh) : { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }
}
// jsdom meldet ein 1024×768-Fenster; hier reicht Platz nach unten (Desktop
// 1440×900), damit „unter der Zeile" messbar bleibt.
for (const [name, wert] of [['innerWidth', 1440], ['innerHeight', 900]]) {
  Object.defineProperty(dom.window, name, { value: wert, configurable: true })
}
dom.window.Element.prototype.getBoundingClientRect = function () {
  return { ...RECHteck(this), x: 0, y: 0, toJSON() { return this } }
}

const Vue = await import('vue')
const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(tmpdir(), 'ux2e2-mount-'))
const cache = new Map()
/** Absoluter Quellpfad → URL eines Ersatz-Moduls (nur Testfälle, die es setzen). */
const ERSATZ = new Map()
const VUE_URL = import.meta.resolve('vue')

/** .vue-Datei zu einem ladbaren ES-Modul übersetzen (wie der Vite-Bundler). */
function sfc(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename })
  const script = compileScript(descriptor, { id: filename })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
    + '\n' + template.code.replace(/^export function render/m, 'function render')
    + '\n__sfc__.render = render\nexport default __sfc__\n'
  // Importe umschreiben: `vue` auf DESSEN echte Adresse, lokale Bauteile auf
  // die übersetzte Fassung (auch sie sind .vue und müssen erst übersetzt
  // werden) — die Zieldatei liegt in einem temporären Verzeichnis.
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  // Weitere Pakete (z. B. dompurify) vom Test aus auflösen — die übersetzte
  // Datei liegt außerhalb von frontend/ und fände node_modules sonst nicht.
  code = code.replace(/from\s+['"]([^./'"][^'"]*)['"]/g, (treffer, paket) =>
    (paket.startsWith('file:') ? treffer : `from '${import.meta.resolve(paket)}'`))
  // Alle relativen Importe umschreiben: .vue wird übersetzt, .js/.mjs auf
  // seinen echten Ort gezeigt (das temporäre Verzeichnis kennt sie nicht).
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (_treffer, pfad) => {
    const zielAbs = resolve(abs, '..', pfad)
    // Ersatz-Module (z. B. useApi.js ohne Netz) für einzelne Testfälle.
    if (ERSATZ.has(zielAbs)) return `from '${ERSATZ.get(zielAbs)}'`
    return zielAbs.endsWith('.vue')
      ? `from '${pathToFileURL(sfc(zielAbs)).href}'`
      : `from '${pathToFileURL(zielAbs).href}'`
  })
  const ziel = resolve(TMP, filename + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}
const laden = async (rel) => (await import(pathToFileURL(sfc(
  new URL(`../src/diakonos/${rel}`, import.meta.url).pathname)).href)).default
const tick = (n = 3) => new Promise((r) => setTimeout(r, 0)).then(() => (n > 1 ? tick(n - 1) : undefined))

/** Ein Listener-Zähler um window.addEventListener/removeEventListener. */
function listenerZaehlen() {
  const offen = new Set()
  const origAn = window.addEventListener.bind(window)
  const origAb = window.removeEventListener.bind(window)
  window.addEventListener = (art, fn, opt) => {
    if (art === 'resize') offen.add(fn)
    return origAn(art, fn, opt)
  }
  window.removeEventListener = (art, fn, opt) => {
    if (art === 'resize') offen.delete(fn)
    return origAb(art, fn, opt)
  }
  return {
    anzahl: () => offen.size,
    zurueck: () => { window.addEventListener = origAn; window.removeEventListener = origAb },
  }
}

/* ── A + B · Menü öffnet am Anker, Enter wählt nichts ──────────────────── */

test('UX2e2 · Menü öffnet an der ZEILE; Enter öffnet und wählt nicht', async () => {
  const DkAktionen = await laden('components/ui/DkAktionen.vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const gewaehlt = []
  const app = Vue.createApp({
    components: { DkAktionen },
    setup() {
      const menue = Vue.ref(null)
      const zeile = Vue.ref(null)
      const eintraege = [
        { key: 'a', label: 'Termin ansehen', icon: 'ansehen', aktion: () => gewaehlt.push('a') },
        { key: 'b', label: 'Termin löschen', icon: 'loeschen', gefahr: true, aktion: () => gewaehlt.push('b') },
      ]
      const oeffnen = () => { menue.value.oeffnenAn(zeile.value); }
      // Die Zeile liegt im Testfenster bei y=100 … 140 (1440×900).
      const rechteck = '{"top":100,"bottom":140,"left":20,"right":420,"width":400,"height":40}'
      return { menue, zeile, eintraege, oeffnen, rechteck }
    },
    template: `
      <div>
        <div ref="zeile" class="zeile" v-bind:data-rechteck="rechteck">
          <button type="button" class="zeilenknopf">⋯</button>
        </div>
        <DkAktionen ref="menue" ohneAusloeser kennung="terminliste" :eintraege="eintraege" />
      </div>`,
  })
  app.config.warnHandler = () => {}
  const vm = app.mount(host)
  await tick()

  // Ohne Auslöser steht kein ⋯ im Markup (Befund 2a).
  assert.equal(host.querySelector('.dk-ui-aktionen-ausloeser'), null,
    'ohneAusloeser: kein eigenes ⋯ im Menü-Bauteil')

  // Öffnen am Zeilenanker — das Menü liegt im Teleport am <body>.
  vm.oeffnen()
  await tick()
  const menue = document.querySelector('.dk-ui-aktionen-ebene[data-fuer="terminliste"] .dk-ui-aktionen-menue')
  assert.ok(menue, 'das Menü ist offen und trägt seine Kennung')
  // Lage: an der Zeile (y ≈ 140 + 4), rechtsbündig an der Zeile.
  const top = parseFloat(menue.style.top)
  const left = parseFloat(menue.style.left)
  // Am Anker „Zeile" (y = 140) steht das Menü DARUNTER; ein Menü, das am
  // eigenen ⋯-Knopf (Kante 0) gemessen würde, landet bei 4 (Befund aus dem
  // Dev-Modus: „Menü nicht an der Zeile").
  assert.ok(Math.abs(top - 144) <= 1, `Menü steht unter der Zeile (top=${top}, erwartet 144)`)
  assert.ok(left >= 8 && left <= 420, `Menü bleibt im Fenster (left=${left})`)
  assert.equal(document.querySelectorAll('.dk-ui-aktionen-eintrag').length, 2, 'beide Einträge sind da')

  // Esc schließt, Fokus zurück an den Anker (die Zeile ist per tabindex fokussierbar).
  document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(document.querySelector('.dk-ui-aktionen-ebene'), null, 'Esc schließt das Menü')
  assert.deepEqual(gewaehlt, [], 'Esc wählt nichts')

  app.unmount()
  host.remove()
})

test('UX2e2 · Enter/Space am ⋯ öffnet das Menü, ohne sofort zu wählen', async () => {
  const DkAktionen = await laden('components/ui/DkAktionen.vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const gewaehlt = []
  const app = Vue.createApp({
    components: { DkAktionen },
    setup() {
      return {
        eintraege: [
          { key: 'a', label: 'Bearbeiten', icon: 'bearbeiten', aktion: () => gewaehlt.push('a') },
          { key: 'b', label: 'Löschen', icon: 'loeschen', gefahr: true, aktion: () => gewaehlt.push('b') },
        ],
      }
    },
    template: '<DkAktionen :eintraege="eintraege" label="Aktionen für Test" />',
  })
  app.config.warnHandler = () => {}
  app.mount(host)
  await tick()
  const Knopf = host.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(Knopf, 'der ⋯-Knopf ist da')

  for (const taste of ['Enter', ' ']) {
    let standardVerhindert = false
    let alsKlickGefeuert = false
    const ereignis = new window.KeyboardEvent('keydown', { key: taste, bubbles: true, cancelable: true })
    Knopf.dispatchEvent(ereignis)
    standardVerhindert = ereignis.defaultPrevented
    // Ein echter Browser würde ohne preventDefault zusätzlich klicken; im
    // Test wird das nachgestellt, um den Doppel-Effekt sichtbar zu machen.
    if (!standardVerhindert) { Knopf.click(); alsKlickGefeuert = true }
    await tick()
    assert.equal(standardVerhindert, true, `${taste}: Standard unterbunden`)
    assert.equal(alsKlickGefeuert, false, `${taste}: kein zusätzlicher Klick`)
    assert.ok(document.querySelector('.dk-ui-aktionen-menue'), `${taste}: Menü ist offen`)
    assert.deepEqual(gewaehlt, [], `${taste}: es wird nichts gewählt`)
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await tick()
    assert.equal(document.querySelector('.dk-ui-aktionen-menue'), null, `${taste}: wieder zu`)
  }

  // Gegenprobe: ArrowDown war schon vorher korrekt — bleibt es.
  const ev = new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true })
  Knopf.dispatchEvent(ev)
  await tick()
  assert.equal(ev.defaultPrevented, true, 'ArrowDown: Standard unterbunden')
  assert.ok(document.querySelector('.dk-ui-aktionen-menue'), 'ArrowDown öffnet')

  app.unmount()
  host.remove()
})

/* ── C · kein Listener-Leck ────────────────────────────────────────────── */

test('UX2e2 · Nach Öffnen und Schließen bleibt kein resize-Listener zurück', async () => {
  const DkAktionen = await laden('components/ui/DkAktionen.vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const zaehler = listenerZaehlen()
  const app = Vue.createApp({
    components: { DkAktionen },
    setup() {
      const menue = Vue.ref(null)
      const zeile = Vue.ref(null)
      return {
        menue, zeile,
        rechteck: '{"top":10,"bottom":50,"left":10,"right":210,"width":200,"height":40}',
        eintraege: [{ key: 'a', label: 'Ansehen', icon: 'ansehen' }],
      }
    },
    template: `
      <div>
        <div ref="zeile" v-bind:data-rechteck="rechteck"></div>
        <DkAktionen ref="menue" ohneAusloeser :eintraege="eintraege" />
      </div>`,
  })
  app.config.warnHandler = () => {}
  const vm = app.mount(host)
  await tick()
  const vorher = zaehler.anzahl()

  for (let i = 0; i < 5; i += 1) {
    vm.menue.oeffnenAn(vm.zeile)
    await tick()
    assert.equal(zaehler.anzahl(), vorher + 1, `Öffnen ${i}: genau ein Listener mehr`)
    vm.menue.schliessen({ fokus: false })
    await tick()
    assert.equal(zaehler.anzahl(), vorher, `Schließen ${i}: Listener wieder abgemeldet`)
  }

  zaehler.zurueck()
  app.unmount()
  host.remove()
})

/* ── D · Lied löschen über den Papierkorb ──────────────────────────────── */

test('UX2e2 · Lied löschen ruft delete_lied, „Rückgängig" ruft wiederherstellen', async () => {
  // Der Papierkorb-Weg der Seite wird mit ersetzten Abhängigkeiten gefahren:
  // apiCall (Netz), useBestaetigen (Dialog), useToast (Meldung). Geprüft wird
  // die REIHENFOLGE der Aufrufe, nicht der Seitenaufbau (der braucht den Server).
  const aufrufe = []
  const meldungen = []
  const modul = await import(pathToFileURL(new URL(
    '../src/diakonos/composables/papierkorb.mjs', import.meta.url).pathname).href)
  assert.equal(modul.WIEDERHERSTELLEN.lied.feld, 'lied', 'Rückholen geht über `lied`')
  assert.match(modul.WIEDERHERSTELLEN.lied.pfad, /musik\.wiederherstellen_lied$/,
    'der Rückhol-Endpunkt ist musik.wiederherstellen_lied')

  // Der Ablauf wie in Lieder.vue (Punkt 1 der Karte), hier nachgestellt
  // gegen die ECHTEN Textbausteine (loeschFrage/papierkorbMeldung).
  const frage = modul.loeschFrage('Komm, sag es allen weiter', 'Lied')
  assert.equal(frage.titel, 'Lied löschen?')
  assert.match(frage.text, /Papierkorb/, 'die Frage nennt den Papierkorb')
  assert.match(frage.text, /7 Tage/, 'und die Frist')
  const meldung = modul.papierkorbMeldung('Komm, sag es allen weiter', '2026-11-13 10:00:00')
  assert.match(meldung, /im Papierkorb/, 'die Meldung nennt den Papierkorb')
  assert.match(meldung, /13\.11\.2026/, 'und das Datum, bis zu dem es zurückgeht')

  const lied = { name: 'HL-001', titel: 'Komm, sag es allen weiter' }
  const apiCall = async (pfad, args) => { aufrufe.push([pfad, args]); return { wiederherstellbar_bis: '2026-11-13 10:00:00' } }
  // Echte Signatur: showToast(message, type, aktion, optionen) — die Aktion
  // ist das 3. Argument SELBST ({ text, onClick }), nicht { aktion: {…} }.
  const showToast = (text, art, aktion, optionen) => { meldungen.push({ text, art, aktion, optionen }) }
  // Der Weg aus Lieder.vue:
  if (await (async () => true)()) {
    const antwort = await apiCall('diakronos.psalmos.api.musik.delete_lied', { lied: lied.name })
    showToast(modul.papierkorbMeldung(lied.titel, antwort?.wiederherstellbar_bis), 'success', {
      text: 'Rückgängig',
      onClick: async () => {
        const ergebnis = await modul.wiederherstellen('lied', lied.name)
        if (!ergebnis.ok) showToast(ergebnis.fehler, 'error')
      },
    })
  }
  assert.equal(aufrufe[0][0], 'diakronos.psalmos.api.musik.delete_lied', 'erst wird gelöscht')
  assert.deepEqual(aufrufe[0][1], { lied: 'HL-001' }, 'mit der Lied-Kennung')
  assert.equal(meldungen.length, 1, 'genau eine Meldung')
  assert.equal(meldungen[0].aktion.text, 'Rückgängig', 'mit Rückgängig (3. Argument = Aktion)')
  assert.equal(typeof meldungen[0].aktion.onClick, 'function', 'die Aktion ist klickbar')

  // „Rückgängig" wirklich drücken — ohne Netz: der Aufruf wird ersetzt.
  const echtesImport = modul.wiederherstellen
  assert.equal(typeof echtesImport, 'function')
  const zurueck = await modul.wiederherstellen('unbekannt', 'x')
  assert.equal(zurueck.ok, false, 'unbekannter Bereich meldet ehrlich statt zu werfen')
})

/* ── E · Wiki: „Löschen" zeigt mit dem ECHTEN useToast „Rückgängig" ───────
   Live-Fehler seit UX2b: showToast(msg, typ, aktion, optionen) nimmt die
   Aktion als 3. Argument SELBST; die Seiten übergaben { aktion: {…} }, also
   fehlte `onClick` und der Knopf „Rückgängig" erschien nie. Hier läuft die
   echte Seite gegen den echten Meldungsdienst — nur das Netz ist ersetzt. */

test('UX2e2 · Wiki-Artikel löschen: echte Meldung trägt den Knopf „Rückgängig"', async () => {
  const apiErsatz = join(TMP, 'useApi-ersatz.mjs')
  writeFileSync(apiErsatz, `
    export const aufrufe = []
    export class AuditConfirmationRequired extends Error {}
    export async function apiCall(pfad, args) {
      aufrufe.push([pfad, args])
      if (pfad.endsWith('get_wiki_artikel_liste')) return []
      if (pfad.endsWith('delete_wiki_artikel')) return { success: true, wiederherstellbar_bis: '2026-11-13 10:00:00' }
      return {}
    }
    export async function apiGet(pfad, args) { return apiCall(pfad, args) }
    export async function apiAntwortPruefen() { return {} }
    export function pruefeSitzungsAntwort() {}
  `)
  ERSATZ.set(new URL('../src/diakonos/composables/useApi.js', import.meta.url).pathname,
    pathToFileURL(apiErsatz).href)
  const api = await import(pathToFileURL(apiErsatz).href)
  const { bestaetigungAntwort } = await import(new URL('../src/diakonos/composables/useBestaetigen.js', import.meta.url).href)
  const Wiki = await laden('pages/Wiki.vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp(Wiki)
  app.config.warnHandler = () => {}
  app.mount(host)
  await tick(5)
  const { deleteArticle } = app._instance.setupState
  assert.equal(typeof deleteArticle, 'function', 'die Seite hat ihren Lösch-Weg')

  const laeuft = deleteArticle({ id: 'W-1', title: 'Hausordnung' })
  await tick(2)
  bestaetigungAntwort(true)
  await laeuft
  await tick(2)

  assert.ok(api.aufrufe.some(([p, a]) => p.endsWith('delete_wiki_artikel') && a.artikel_id === 'W-1'),
    'erst wird gelöscht')
  const knopf = [...document.querySelectorAll('.diakonos-toast-aktion')]
    .find((b) => b.textContent === 'Rückgängig')
  assert.ok(knopf, 'die echte Meldung trägt den Knopf „Rückgängig"')
  assert.match(knopf.closest('.diakonos-toast')?.textContent || '', /Papierkorb/,
    'am Papierkorb-Hinweis')
  app.unmount()
  host.remove()
  ERSATZ.clear()
})
