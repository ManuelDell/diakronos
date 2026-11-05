/**
 * UX2f2a — Feld mit Prüfung: Baustein (DkField/DkEingabe) und Regeln reparieren.
 *
 * Die Karte verlangt einen Test, der `DkField` WIRKLICH mountet: Slot
 * `v-slot="feld"`, `<input v-bind="feld.feldProps">`, tippen → `update:wert`,
 * blur → Meldung, `aria-describedby` nur mit Meldung. Der erste Anlauf prüfte
 * nur einen SSR-String mit von Hand gerufenen Handlern — das beweist weder,
 * dass Vue den Feldsatz ans Element hängt, noch dass das Feld seinen Wert
 * behält (Review-Befund, Punkt 5).
 *
 * Deshalb: echtes DOM (`jsdom`, devDependency, s. Begründung unten), echtes
 * `createApp().mount()`, echte Ereignisse (`input`/`blur`), echte Re-Render.
 * Die SFCs werden vorher mit `vue/compiler-sfc` übersetzt — dasselbe Verfahren
 * wie in `planrahmen-pfad-meldungen.test.mjs`; die Seite bindet die Komponenten
 * im Betrieb über Vite, hier eben von Hand.
 *
 * WARUM jsdom (Review-Punkt 5 verlangt eine Begründung): Die Karte erlaubt
 * ausdrücklich „@vue/test-utils oder … was im Frontend schon vorhanden ist".
 * Vorhanden war KEIN DOM: dieses Projekt testet mit `node --test` ohne
 * Browser-Umgebung. vue/test-utils brächte jsdom ohnehin mit, und `happy-dom`
 * ist für `blur`/`activeElement`/`Event`-Weitergabe unzuverlässiger. jsdom ist
 * damit die kleinste Ergänzung, die den geforderten Mount erlaubt; sie steht
 * nur in `devDependencies` und landet NICHT im Laufzeit-Image (der
 * Frontend-Stage baut und wirft `node_modules` danach weg, der App-Stage ist
 * ein Python-Image).
 *
 * Der Test läuft im Image-Build (`node --test`, backend/Dockerfile) und liest
 * ausschließlich Dateien INNERHALB von frontend/ — keine zusätzliche
 * COPY-Zeile nach Regel 13 nötig.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import schon auf `document` zu) ────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}

const Vue = await import('vue')

const SRC = new URL('../src/diakonos/', import.meta.url)

// ── SFC → ES-Modul (wie planrahmen-pfad-meldungen.test.mjs) ────────────────
const TMP = mkdtempSync(join(tmpdir(), 'ux2f2a-'))
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

const UI = new URL('components/ui/', SRC).pathname
const DkField = (await import(pathToFileURL(kompilieren(UI + 'DkField.vue')).href)).default
const DkEingabe = (await import(pathToFileURL(kompilieren(UI + 'DkEingabe.vue')).href)).default
const { email, url, plz, pflicht, laenge } =
  await import(new URL('composables/feldPruefung.mjs', SRC).href)

test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Mount-Hilfen ──────────────────────────────────────────────────────────
const tick = () => new Promise((loese) => setTimeout(loese, 0))

/**
 * Mountet eine Vorlage mit DkField/DkEingabe in ein echtes DOM-Element und
 * liefert Wurzel, reaktiven Zustand und die Vue-Warnungen dieses Mounts.
 */
async function mounten(vorlage, zustand = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const s = Vue.reactive(zustand)
  const warnungen = []
  const app = Vue.createApp({
    components: { DkField, DkEingabe },
    setup: () => ({ s, email, url, plz, pflicht, laenge }),
    template: vorlage,
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, s, app, warnungen }
}

/** Tippt in ein Feld wie ein Mensch: Wert setzen + `input`-Ereignis. */
function tippen(element, wert) {
  element.value = wert
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}

/** Verlässt das Feld: `blur`-Ereignis. */
function verlassen(element) {
  element.dispatchEvent(new window.Event('blur', { bubbles: true }))
}

/** Was ein Mensch (und ein Screenreader) am Feld sieht. */
function zustandAmFeld(host) {
  const feld = host.querySelector('input, select, textarea')
  const beschreibt = feld.getAttribute('aria-describedby')
  return {
    wert: feld.value,
    invalid: feld.getAttribute('aria-invalid'),
    beschreibt,
    beschreibtExistiert: beschreibt ? Boolean(host.querySelector('#' + CSS.escape(beschreibt))) : null,
    meldung: host.querySelector('[role="alert"]')?.textContent.trim() ?? null,
    hilfe: host.querySelector('.dk-ui-field-hilfe')?.textContent.trim() ?? null,
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Der Feldsatz trägt alles, was das Feld braucht
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: Feldsatz am echten Feld — id, Wert, Eingabe, Blur, aria', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="E-Mail" :regel="email()" :wert="s.x"
              @update:wert="v => s.x = v">
       <input v-bind="feld.feldProps" type="email">
     </DkField>`,
    { x: 'maria@example.org' },
  )
  const feld = host.querySelector('input')
  assert.ok(feld, 'Eingabefeld fehlt')
  assert.match(feld.id, /^dk-field-/, 'Feld ohne id (Label-Ziel)')
  assert.equal(host.querySelector('label').getAttribute('for'), feld.id, 'Label zeigt nicht auf das Feld')
  assert.equal(feld.value, 'maria@example.org', 'Wert aus :wert steht nicht im Feld')
  assert.equal(feld.getAttribute('aria-invalid'), null, 'ohne Meldung kein aria-invalid')
  assert.equal(feld.getAttribute('aria-describedby'), null, 'ohne Meldung/Hilfe kein aria-describedby')
  // Der Feldsatz darf NICHT als Objekt-Attribut am Element landen.
  assert.equal(feld.getAttribute('feldprops'), null, 'Feldsatz wurde als Attribut geschrieben')
  assert.equal(s.x, 'maria@example.org')
})

test('UX2f2a: Tippen reicht update:wert — der Wert steht danach im Modell UND im Feld', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="Name" :wert="s.x" @update:wert="v => s.x = v">
       <input v-bind="feld.feldProps">
     </DkField>`,
    { x: '' },
  )
  const feld = host.querySelector('input')
  tippen(feld, 'Musterhausen')
  await tick()
  assert.equal(s.x, 'Musterhausen', 'update:wert kam nicht an')
  assert.equal(feld.value, 'Musterhausen', 'Feld zeigt den Wert nicht (Re-Render leerte es)')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Review-Punkt 2: v-model am Feld OHNE :wert leert das Feld nicht mehr
//     (Registrierung.vue: `<input v-bind="feld.feldProps" v-model="x">`)
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: v-model am Feld ohne :wert bleibt erhalten (kein Leeren bei jedem Zeichen)', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="Bezeichnung">
       <input v-bind="feld.feldProps" v-model="s.x">
     </DkField>`,
    { x: '' },
  )
  const feld = host.querySelector('input')
  for (const zwischenstand of ['G', 'Ge', 'Gem']) {
    tippen(feld, zwischenstand)
    await tick()
    assert.equal(feld.value, zwischenstand, `Feld leert sich bei "${zwischenstand}"`)
    assert.equal(s.x, zwischenstand)
  }
})

test('UX2f2a: ein nicht gesetzter Wert erscheint NICHT als leeres value-Attribut', async () => {
  const { host } = await mounten(
    `<DkField v-slot="feld" label="Ort">
       <input v-bind="feld.feldProps" v-model="s.x">
     </DkField>`,
    { x: 'Heilbronn' },
  )
  // `wert` hat die Vorgabe `undefined`: der Feldsatz darf `value` gar nicht
  // mitbringen, sonst überschreibt er das v-model.
  assert.equal(host.querySelector('input').value, 'Heilbronn')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Verlassen prüft, Meldung + aria hängen zusammen
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: beim Tippen keine Meldung, beim Verlassen die Meldung (I4)', async () => {
  const { host } = await mounten(
    `<DkField v-slot="feld" label="E-Mail" :regel="email()" :wert="s.x"
              @update:wert="v => s.x = v">
       <input v-bind="feld.feldProps" type="email">
     </DkField>`,
    { x: '' },
  )
  const feld = host.querySelector('input')
  tippen(feld, 'maria')
  await tick()
  assert.equal(zustandAmFeld(host).meldung, null, 'Meldung erscheint schon beim Tippen')
  assert.equal(feld.getAttribute('aria-invalid'), null)

  verlassen(feld)
  await tick()
  const danach = zustandAmFeld(host)
  assert.match(danach.meldung ?? '', /fehlt das @/, 'keine Meldung nach dem Verlassen')
  assert.equal(danach.invalid, 'true', 'aria-invalid fehlt an der Meldung')
  assert.match(danach.beschreibt ?? '', /^dk-field-desc-/, 'aria-describedby zeigt nicht auf die Meldung')
  assert.equal(danach.beschreibtExistiert, true, 'aria-describedby zeigt auf ein Element, das es nicht gibt')

  // Fehler beheben → Meldung verschwindet beim Tippen (danach wird geprüft).
  tippen(feld, 'maria@example.org')
  await tick()
  const behoben = zustandAmFeld(host)
  assert.equal(behoben.meldung, null, 'Meldung bleibt trotz behobenem Fehler stehen')
  assert.equal(behoben.invalid, null)
  assert.equal(feld.value, 'maria@example.org', 'Eingabe wurde beim Prüfen verändert')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Review-Punkt 1: aria-describedby zeigt nur auf EXISTIERENDE Ziele
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: Hilfe ohne Meldung beschreibt über die HILFE-Kennung, nicht ins Leere', async () => {
  const { host } = await mounten(
    `<DkField v-slot="feld" label="PLZ" help="Fünf Ziffern, z. B. 74072.">
       <input v-bind="feld.feldProps">
     </DkField>`,
  )
  const feld = host.querySelector('input')
  const beschreibt = feld.getAttribute('aria-describedby')
  assert.ok(beschreibt, 'Hilfetext ohne aria-describedby')
  assert.match(beschreibt, /^dk-field-hilfe-/, 'aria-describedby nennt nicht die Hilfe-Kennung')
  assert.equal(Boolean(host.querySelector('#' + CSS.escape(beschreibt))), true,
    'aria-describedby zeigt auf ein Element, das es im DOM nicht gibt')
  assert.equal(host.querySelector('.dk-ui-field-hilfe').textContent.trim(), 'Fünf Ziffern, z. B. 74072.')
  assert.equal(feld.getAttribute('aria-invalid'), null, 'Hilfe allein darf kein aria-invalid setzen')
})

test('UX2f2a: mit Meldung gewinnt die MELDUNG als Beschreibung (nicht der Tipp)', async () => {
  const { host } = await mounten(
    `<DkField v-slot="feld" label="E-Mail" help="An diese Adresse gehen Fragen."
              error="Es fehlt das @.">
       <input v-bind="feld.feldProps">
     </DkField>`,
  )
  const zustand = zustandAmFeld(host)
  assert.match(zustand.beschreibt ?? '', /^dk-field-desc-/, 'bei Meldung muss die Meldung beschrieben werden')
  assert.equal(zustand.beschreibtExistiert, true)
  assert.equal(host.querySelector('.dk-ui-field-hilfe'), null, 'Meldung und Hilfetext stehen gleichzeitig da')
})

test('UX2f2a: ohne Meldung und ohne Hilfe KEIN aria-describedby', async () => {
  const { host } = await mounten(
    `<DkField v-slot="feld" label="Ort"><input v-bind="feld.feldProps"></DkField>`,
  )
  assert.equal(host.querySelector('input').getAttribute('aria-describedby'), null)
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Review-Punkt 3: DkEingabe — Wert aus dem Feldsatz, EIN Emit je Eingabe
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: DkEingabe zeigt den Wert aus dem Feldsatz (Gemeinde-Muster)', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="Kontakt-E-Mail" :wert="s.x" @update:wert="v => s.x = v">
       <DkEingabe v-bind="feld.feldProps" type="email" />
     </DkField>`,
    { x: 'buero@gemeinde.example' },
  )
  const feld = host.querySelector('input')
  assert.equal(feld.value, 'buero@gemeinde.example', 'DkEingabe zeigt den Feldsatz-Wert nicht (Feld bleibt leer)')
  tippen(feld, 'neu@gemeinde.example')
  await tick()
  assert.equal(s.x, 'neu@gemeinde.example', 'Tippen kommt nicht im Modell an')
  assert.equal(feld.value, 'neu@gemeinde.example', 'DkEingabe zeigt das Getippte nicht')
})

test('UX2f2a: DkEingabe reicht EINE Eingabe genau EINMAL weiter (kein doppeltes update:wert)', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="Name" :wert="s.x" @update:wert="v => { s.anzahl++; s.x = v }">
       <DkEingabe v-bind="feld.feldProps" />
     </DkField>`,
    { x: 'a', anzahl: 0 },
  )
  tippen(host.querySelector('input'), 'ab')
  await tick()
  assert.equal(s.anzahl, 1, `update:wert feuerte ${s.anzahl}-mal statt einmal`)
  assert.equal(s.x, 'ab')
})

test('UX2f2a: DkEingabe mit eigenem v-model feuert trotzdem nur einmal', async () => {
  const { host, s } = await mounten(
    `<DkField v-slot="feld" label="Name" :wert="s.x" @update:wert="v => { s.anzahl++; s.x = v }">
       <DkEingabe v-bind="feld.feldProps" v-model="s.eigen" />
     </DkField>`,
    { x: 'a', eigen: 'a', anzahl: 0 },
  )
  tippen(host.querySelector('input'), 'abc')
  await tick()
  assert.equal(s.eigen, 'abc', 'eigenes v-model der DkEingabe kam nicht an')
  assert.equal(s.anzahl, 1, `update:wert feuerte ${s.anzahl}-mal statt einmal`)
  assert.equal(host.querySelector('input').value, 'abc', 'Feld zeigt den Wert nicht')
})

test('UX2f2a: DkEingabe bleibt ohne Feldsatz benutzbar (einfaches v-model)', async () => {
  const { host, s } = await mounten(
    `<DkField label="Ort"><DkEingabe v-model="s.x" placeholder="Ort" /></DkField>`,
    { x: 'Heilbronn' },
  )
  const feld = host.querySelector('input')
  assert.equal(feld.value, 'Heilbronn')
  assert.equal(feld.getAttribute('placeholder'), 'Ort')
  tippen(feld, 'Böckingen')
  await tick()
  assert.equal(s.x, 'Böckingen')
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Review-Punkt 4: keine Vue-Warnung beim Render (Slot-Prop `pruefen`)
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: DkField rendert ohne Vue-Warnung (Slot liefert `pruefe`, nicht `pruefen`)', async () => {
  const { host, s, warnungen } = await mounten(
    `<DkField v-slot="feld" label="E-Mail" :regel="email()" :wert="s.x"
              @update:wert="v => s.x = v">
       <input v-bind="feld.feldProps">
     </DkField>`,
    { x: 'maria' },
  )
  verlassen(host.querySelector('input'))
  await tick()
  const eigene = warnungen.filter((w) => /pruefen/i.test(w))
  assert.deepEqual(eigene, [], 'Vue warnt über das Slot-Prop `pruefen`: ' + eigene.join(' | '))
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Regeln: leere Werte, http://
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2a: leeres Feld zeigt keine Meldung — nur pflicht beanstandet Leeres', async () => {
  for (const [name, regel] of [['email', email()], ['url', url()], ['plz', plz()],
    ['laenge', laenge({ max: 10 })]]) {
    assert.equal(regel(''), '', `${name}() beanstandet ein leeres Feld`)
    // Und am Feld: verlassen ohne Eingabe ergibt keine Meldung.
    const { host } = await mounten(
      `<DkField v-slot="feld" label="${name}">
         <input v-bind="feld.feldProps">
       </DkField>`,
    )
    verlassen(host.querySelector('input'))
    await tick()
    assert.equal(host.querySelector('[role="alert"]'), null, `${name}: leeres Feld zeigt eine Meldung`)
  }
  // pflicht bleibt die Ausnahme — auch am Feld.
  const { host } = await mounten(
    `<DkField v-slot="feld" label="Vorname" required>
       <input v-bind="feld.feldProps">
     </DkField>`,
  )
  verlassen(host.querySelector('input'))
  await tick()
  assert.match(zustandAmFeld(host).meldung ?? '', /Bitte .*Vorname.* angeben/, 'Pflichtfeld meldet sich nicht')
  assert.equal(pflicht('einen Namen')(''), 'Bitte einen Namen angeben.')
})

test('UX2f2a: url() lässt http:// wieder zu (LAN-Instanzen, gespeicherte Websites)', () => {
  for (const gut of ['http://192.168.1.11:8100', 'http://gemeinde.example.org',
    'https://www.example.org', 'HTTP://example.org', 'http://example.org:8443/x?y=1']) {
    assert.equal(url()(gut), '', `muss gültig sein: ${gut}`)
  }
  assert.match(url()('example.org'), /muss mit http:\/\/ oder https:\/\/ beginnen/)
  assert.match(url()('ftp://example.org'), /muss mit http:\/\/ oder https:\/\/ beginnen/)
  assert.equal(url()('http://'),
    'Es fehlt der Name der Website nach http:// bzw. https:// – z. B. www.example.org.')
})
