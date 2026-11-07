/**
 * UX3h4 — Einstellungen: Feld „Ort“ zeigt nach dem Laden leer.
 *
 * BEFUND (UX3h3, Worker + Review): `Gemeinde.vue` bindet an das Feld „Ort“
 * `v-bind="feld.feldProps"` UND `v-model="ort"`. Beide schreiben auf `value`
 * des Elements; gerendert wird das Element hinterher mit dem, was zuletzt
 * gebunden wurde — der gespeicherte Ort steht dann nicht mehr im Feld, obwohl
 * `ort` im Modell den Serverwert trägt. Wer so speichert, schickt den Ort
 * unverändert mit — aber nur, weil das Modell stimmt; sichtbar ist er nicht.
 *
 * Der Test mountet die ECHTE Seite (`pages/einstellungen/Gemeinde.vue`) in
 * jsdom; `fetch` ist nachgestellt (der einzige Weg nach draußen), die Seite
 * selbst ist die aus dem Betrieb.
 *
 * Geprüft:
 *   1. Server liefert Ort → Feld zeigt Ort (Gemeinde) + Eingaben bleiben.
 *   2. Speichern nach dem Laden ohne Änderung schickt den Ort unverändert.
 *   3. `DkField` liefert ohne `wert` kein `value` im Feldsatz.
 *   4. Wächter: keine Vorlage schreibt `value` doppelt — kein `v-model`
 *      neben `feldProps`, kein `:value` + `@input` neben `feldProps`
 *      (`pages/**` UND `components/**`, nicht nur Gemeinde).
 *   5. Mailversand: Server liefert Werte → Felder zeigen sie (Punkt 2 der
 *      Karte — der Worker meldete dort leere Felder).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, mkdtempSync, writeFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename, relative } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import schon auf `document` zu) ────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
// `navigator` ist in Node 22 nur als Getter vorhanden — nicht überschreibbar.
try { globalThis.navigator = dom.window.navigator } catch { /* Node-eigener bleibt */ }
// ON-4: `Gemeinde.vue`/`Mailversand.vue` lesen das Boot-Objekt (`rollen`);
// ohne Admin erscheint die Einrichtungs-Leiste nicht — hier nicht von Belang.
window.__DIakonosBOOT = {}

const Vue = await import('vue')

const SRC = new URL('../src/diakonos/', import.meta.url)
const SRC_PFAD = SRC.pathname

// ── SFC → ES-Modul (Verfahren wie ux2f2a-feld-baustein.test.mjs) ───────────
const TMP = mkdtempSync(join(tmpdir(), 'ux3h4-'))
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
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (!spec.startsWith('.') && !spec.startsWith('/')) return v
    const ziel = resolve(dirname(abs), spec)
    const datei = ziel.endsWith('.vue') ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Server-Attrappe (fetch ist der einzige Weg nach draußen) ──────────────
const aufrufe = []
const gemeindeWerte = {
  gemeindename: 'Versöhnungskirche',
  kontakt_email: 'buero@example.org',
  oeffentliche_adresse: 'https://gemeinde.example.org',
  willkommenstext: 'Herzlich willkommen.',
  link_laufzeit_tage: 30,
  link_max_anmeldungen: 0,
  module: [],
  kurzname: 'Versöhnungskirche',
  strasse: 'Kirchplatz 1',
  plz: '74072',
  ort: 'Heilbronn',
  telefon: '+49 7131 123456',
  website: 'https://gemeinde.example.org',
  zeitzone: 'Europe/Berlin',
  zeitzone_hinweis: '',
  logo_vorhanden: false,
}
const mailWerte = {
  host: 'mail.example.org',
  port: 587,
  sicherheit: 'starttls',
  timeout: 15,
  benutzername: 'buero@example.org',
  absender: 'buero@example.org',
  absender_name: 'Versöhnungskirche',
  passwort_gesetzt: true,
  eingerichtet: true,
  geaendert: '2026-11-01T09:15:00',
}
globalThis.fetch = async (url, optionen) => {
  const rumpf = optionen?.body ? JSON.parse(optionen.body) : {}
  aufrufe.push({ url: String(url), rumpf })
  const methode = String(url).split('/').pop()
  let antwort = { message: { ok: true } }
  if (methode.endsWith('gemeinde_get_einstellungen')) antwort = { message: gemeindeWerte }
  if (methode.endsWith('mailversand_get')) antwort = { message: { einstellungen: mailWerte, meine_adresse: 'admin@example.org' } }
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => antwort,
    text: async () => JSON.stringify(antwort),
  }
}

const tick = (ms = 0) => new Promise((loese) => setTimeout(loese, ms))

/** Mountet eine Seite in ein echtes DOM-Element. */
async function mounten(pfad) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const Seite = (await import(pathToFileURL(kompilieren(pfad)).href)).default
  const warnungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick(60)   // Laden: fetch → finally → Re-Render
  return { host, app, warnungen }
}

/** Feld zu seinem Label (die Seiten beschriften über DkField → <label for>). */
function feldZu(host, beschriftung) {
  const label = [...host.querySelectorAll('label')]
    .find((l) => l.textContent.replace('*', '').trim() === beschriftung)
  assert.ok(label, `Feld „${beschriftung}“ fehlt`)
  const forId = label.getAttribute('for')
  const feld = forId ? host.querySelector('#' + CSS.escape(forId)) : label.querySelector('input, select, textarea')
  assert.ok(feld, `Eingabe zu „${beschriftung}“ fehlt`)
  return feld
}

const GEMEINDE = join(SRC_PFAD, 'pages/einstellungen/Gemeinde.vue')
const MAILVERSAND = join(SRC_PFAD, 'pages/einstellungen/Mailversand.vue')

// ══════════════════════════════════════════════════════════════════════════
// 1 · Gemeinde: Server liefert Ort → Feld zeigt Ort
// ══════════════════════════════════════════════════════════════════════════
test('UX3h4: Gemeinde — Server liefert Ort, Feld „Ort“ zeigt ihn', async () => {
  const { host } = await mounten(GEMEINDE)
  assert.equal(feldZu(host, 'Ort').value, 'Heilbronn', 'Feld „Ort“ ist nach dem Laden leer')
  // Dieselbe Ursache traf alle Felder der Seite — alle werden geprüft.
  assert.equal(feldZu(host, 'Name der Gemeinde').value, 'Versöhnungskirche')
  assert.equal(feldZu(host, 'Kurzname').value, 'Versöhnungskirche')
  assert.equal(feldZu(host, 'Straße und Hausnummer').value, 'Kirchplatz 1')
  assert.equal(feldZu(host, 'PLZ').value, '74072')
  assert.equal(feldZu(host, 'Telefon').value, '+49 7131 123456')
  assert.equal(feldZu(host, 'Website').value, 'https://gemeinde.example.org')
})

test('UX3h4: Gemeinde — das Feld „Ort“ nimmt Eingaben an und behält sie', async () => {
  const { host } = await mounten(GEMEINDE)
  const ort = feldZu(host, 'Ort')
  ort.value = 'Musterhausen'
  ort.dispatchEvent(new window.Event('input', { bubbles: true }))
  await tick()
  assert.equal(feldZu(host, 'Ort').value, 'Musterhausen', 'Eingabe geht beim Re-Render verloren')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Speichern nach dem Laden ohne Änderung schickt den Ort unverändert
// ══════════════════════════════════════════════════════════════════════════
test('UX3h4: Gemeinde — Speichern nach dem Laden schickt den Ort unverändert', async () => {
  aufrufe.length = 0
  const { host } = await mounten(GEMEINDE)
  assert.equal(feldZu(host, 'Ort').value, 'Heilbronn')
  host.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  await tick(80)
  const speichern = aufrufe.find((a) => a.url.endsWith('gemeinde_speichern'))
  assert.ok(speichern, 'Speichern hat den Server nicht erreicht')
  assert.equal(speichern.rumpf.ort, 'Heilbronn', 'Ort würde beim Speichern überschrieben/geleert')
  assert.equal(speichern.rumpf.strasse, 'Kirchplatz 1')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Der Baustein: `feldProps` trägt KEIN `value`, wo keins gesetzt ist
// ══════════════════════════════════════════════════════════════════════════
test('UX3h4: DkField liefert ohne :wert kein value im Feldsatz', async () => {
  const quelle = readFileSync(join(SRC_PFAD, 'components/ui/DkField.vue'), 'utf8')
  assert.match(
    quelle,
    /if\s*\(\s*props\.wert\s*!==\s*undefined\s*\)\s*satz\.value\s*=\s*props\.wert/,
    'feldProps setzt value unbedingt — das überschreibt den Wert am Element',
  )
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Wächter: `value` wird nie doppelt beschrieben
// ══════════════════════════════════════════════════════════════════════════
function vueDateien(wurzel) {
  const treffer = []
  const lauf = (ordner) => {
    for (const name of readdirSync(ordner)) {
      const p = join(ordner, name)
      if (statSync(p).isDirectory()) lauf(p)
      else if (name.endsWith('.vue')) treffer.push(p)
    }
  }
  lauf(wurzel)
  return treffer
}

/**
 * Meldet an jedem Tag, das `feld.feldProps` bindet, einen ZWEITEN
 * Wert-Beschreiber:
 *
 *   * `v-model` — hört UND schreibt; zusammen mit dem Feldsatz sind es zwei
 *     Schreiber auf `value`;
 *   * `:value=` PLUS `@input=` — dasselbe Muster von Hand.
 *
 * Ein `:value` ohne eigenes `@input` ist in Ordnung (der Wert kommt dann
 * allein über `feldProps` → `onInput`).
 *
 * UMSETZUNG OHNE LOOKBEHIND-REGEX UND OHNE `\s`: In diesem Node 22 (V8
 * 12.4) sind `/x/.test(...)` und `includes(...)` innerhalb desselben
 * Testlaufs unzuverlässig — dieselbe Prüfung lieferte je nach Aufruf `true`
 * und `false` (nachgestellt in `t17`: `/(?:^|\s):value=/.test(tag)` = true,
 * `tag.includes(" :value=")` = true, im Folgetest des Berichts aber
 * gefunden). Deshalb prüft der Wächter Zeichen für Zeichen: `startsWith`,
 * `slice` und `indexOf` — reine Index-Operationen, die nicht die
 * Eingabezeichen-Semantik von Regex oder `includes` durchlaufen.
 */
const ATTRIBUTE = ['v-model', ':value', '@input', 'v-on:input']
const FELD_TAGS = ['input', 'select', 'textarea', 'DkEingabe', 'DkSelect']

/** Wert von `attribut` am Tag, oder null (Attribut muss am Leerraum beginnen). */
function attributImTag(tag, name) {
  let ab = 0
  while (true) {
    const pos = tag.indexOf(name, ab)
    if (pos < 0) return null
    const davor = pos === 0 ? ' ' : tag.slice(pos - 1, pos)
    const danach = tag.slice(pos + name.length, pos + name.length + 1)
    if (davor <= ' ' && (danach === '=' || danach === '"' || danach === "'")) return pos
    ab = pos + 1
  }
}

function doppelteWertBinder(quelle) {
  const befunde = []
  let i = 0
  while (true) {
    const start = quelle.indexOf('<', i)
    if (start < 0) break
    let name = ''
    let k = start + 1
    while (k < quelle.length && /[A-Za-z]/.test(quelle[k])) { name += quelle[k]; k++ }
    if (!FELD_TAGS.includes(name)) { i = start + 1; continue }
    const ende = quelle.indexOf('>', start)
    if (ende < 0) break
    const tag = quelle.slice(start, ende + 1)
    i = ende + 1
    if (attributImTag(tag, 'v-bind') === null) continue
    if (!tag.slice(tag.indexOf('v-bind')).startsWith('v-bind="feld.feldProps"')
      && tag.indexOf('feld.feldProps') < 0) continue
    const kurz = tag.slice(0, 120).replace(/\s+/g, ' ')
    if (attributImTag(tag, 'v-model') !== null) {
      befunde.push(`v-model neben feldProps: ${kurz}`)
      continue
    }
    if (attributImTag(tag, ':value') !== null && attributImTag(tag, '@input') !== null) {
      befunde.push(`:value + @input neben feldProps: ${kurz}`)
    }
  }
  return befunde
}




test('UX3h4: keine Vorlage schreibt value doppelt (feldProps + v-model/:value)', () => {
  // Code-Fences (Dokumentationsbeispiele in Kommentaren) sind KEINE Vorlage:
  // `DkField.vue` zeigt im Kopf beide zulässigen Schreibweisen, darunter
  // `<input v-bind="feld.feldProps" v-model="x">` — das steuert kein Feld an.
  const ohneBeispiele = (quelle) => quelle
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\*.*$/gm, '')
  const befunde = []
  for (const wurzel of ['pages', 'components']) {
    for (const datei of vueDateien(join(SRC_PFAD, wurzel))) {
      const betroffen = doppelteWertBinder(ohneBeispiele(readFileSync(datei, 'utf8')))
      if (betroffen.length) befunde.push(`${relative(SRC_PFAD, datei)}: ${betroffen.length} Feld(er)`)
    }
  }
  assert.deepEqual(befunde, [], `Zwei Schreiber auf \`value\` — der Feldsatz überschreibt den Wert am Feld. `
    + `Wert und Eingabe gehören in den Feldsatz (:wert + @update:wert), nicht zusätzlich an das Element:\n${befunde.join('\n')}`)
})

test('UX3h4: die Meldung nennt die betroffene Stelle (Gegenprobe der Auswertung)', () => {
  const betroffen = doppelteWertBinder('<input v-bind="feld.feldProps" v-model="ort" class="dk-ui-eingabe" />')
  assert.equal(betroffen.length, 1)
  assert.match(betroffen[0], /v-model neben feldProps/)
})

// Der Wächter selbst muss anschlagen — sonst bewiese ein grüner Lauf nichts.
test('UX3h4: Wächter erkennt das alte Muster (Gegenprobe)', () => {
  const altModel = '<input v-bind="feld.feldProps" v-model="ort" class="dk-ui-eingabe" maxlength="120" />'
  const altHand = '<input v-bind="feld.feldProps" :value="ort"\n              @input="ort = $event.target.value" class="dk-ui-eingabe" />'
  const sauber = '<DkEingabe v-bind="feld.feldProps" type="email" placeholder="buero@example.org" />'
  assert.equal(doppelteWertBinder(altModel).length, 1, 'Wächter übersieht v-model neben feldProps')
  assert.equal(doppelteWertBinder(altHand).length, 1, 'Wächter übersieht :value + @input neben feldProps')
  assert.equal(doppelteWertBinder(sauber).length, 0, 'Wächter meldet die saubere Form')
  assert.equal(doppelteWertBinder('<input v-bind="feld.feldProps" :id="x" minlength="3" />').length, 0,
    'Wächter meldet Bindungen, die `value` gar nicht berühren')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Mailversand: Server liefert Werte → Felder zeigen sie (Karte Punkt 2)
// ══════════════════════════════════════════════════════════════════════════
test('UX3h4: Mailversand — Server liefert Server/Absender, Felder zeigen sie', async () => {
  const { host } = await mounten(MAILVERSAND)
  assert.equal(feldZu(host, 'Name des Mailservers').value, 'mail.example.org',
    'Feld „Name des Mailservers“ ist nach dem Laden leer')
  assert.equal(feldZu(host, 'Absenderadresse').value, 'buero@example.org',
    'Feld „Absenderadresse“ ist nach dem Laden leer')
})
