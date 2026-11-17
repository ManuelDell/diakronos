/**
 * DES-1 — Kartentitel brachen unnötig um (Befund Manuel 17.11., hoch).
 *
 * Befund (Dev-Modus, Gruppe → Einstellungen und Übersicht, `DkCard`):
 * „Rollen der / Gruppe“, „Kalender der / Gruppe“, „Nächste / Termine“ standen
 * auf ZWEI Zeilen, obwohl die Karte breit war; Manuel: „Design nicht SSOT
 * konform und entspricht nicht den Design-Richtlinien“.
 *
 * Ursache (im gemeinsamen Baustein, nicht auf der Seite): die Kopfzeile von
 * `DkCard` war `display: flex` mit `justify-content: space-between` und
 * `flex-wrap: wrap`. Der Titel war KEIN eigenes Flex-Kind (er lag nackt neben
 * dem Aktionsbereich), also bekam er nur seine Inhaltsbreite — und die
 * Inhaltsbreite eines Textes im Flex-Kasten ist die längste ZEILE, nicht das
 * längste Wort. `flex-wrap` warf den Aktionsbereich trotz freier Zeile in
 * Zeile 2, `space-between` quetschte den Titel. Dazu kamen seitenlokale
 * Überschreibungen des Kartenkopfs (`GruppeDetail.vue`), die den Rahmen
 * zusätzlich einengten.
 *
 * Geprüft wird am ECHTEN Bauteil (jsdom-Mount, kein Quelltext-Muster):
 *
 *   1. Kopfstruktur: Titel und Unterzeile liegen in EINEM Textfeld
 *      (`.dk-ui-card-kopftext`), der Aktionsbereich steht DANEBEN als eigenes
 *      Geschwister — nicht im selben Feld, nicht im Körper.
 *   2. Der Titel ist einzeilig vorgesehen (`white-space: nowrap` in der
 *      Bildschirm-Regel), das Textfeld darf wachsen und schrumpfen
 *      (`flex: 1 1 auto; min-width: 0`), die Aktionen behalten ihre Breite.
 *   3. Ohne `sub` gibt es keine leere Unterzeile im DOM.
 *   4. `sub` steht UNTER dem Titel im selben Textfeld (über die volle
 *      Textbreite) — nicht als erster Absatz im Körper.
 *   5. Am Handy (390 px) bekommt das Textfeld die volle Breite, der Titel
 *      darf dort wieder umbrechen (ganze Wörter statt abgeschnittener Ellipse).
 *   6. Die Gruppenseite benutzt den Baustein, statt den Kopf lokal zu
 *      überschreiben: keine `min-height`-Vorgabe für den Kopf mehr, die
 *      Beschreibungen kommen als `sub` an (Rollen + Kalender), und die
 *      Bausteine melden ihren Text über `@hinweis` (EINE Quelle).
 *
 * Lauf: node --test tests/des1-*.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
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
W.__DIakonosBOOT = { csrf_token: 'x', modules: [], user_email: 'ich@example.org' }
globalThis.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {} })
W.matchMedia = globalThis.matchMedia
Element.prototype.scrollIntoView = function () {}

const Vue = await import('vue')

// ── SFC-Übersetzung (wie uir8c/aufr2): Stellvertreter je Modul ──────────────
const TMP = mkdtempSync(join(tmpdir(), 'des1-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'sprung.mjs'), `
export function sprungId(anker) { return anker ? 'dk-sprung-' + anker : undefined }
`)
const STELLVERTRETER = new Map([[join(SRC, 'pages/sprung'), join(STUB, 'sprung.mjs')]])

const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function stellvertreterFuer(abs) {
  const ohne = String(abs).replace(/\.(js|mjs|vue)$/, '')
  return STELLVERTRETER.get(ohne) || null
}

function kompilieren(abs) {
  const ersatz = stellvertreterFuer(abs)
  if (ersatz) return ersatz
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
    if (!spec.startsWith('.')) return v
    const ziel = resolve(dirname(abs), spec)
    const datei = spec.endsWith('.vue') || stellvertreterFuer(ziel) ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const txt = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')

/** `DkCard` mit optionalem Aktionsbereich mounten. */
async function karte({ title = '', sub = '', aktion = false } = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    setup: () => ({ p: { title, sub } }),
    render: () => Vue.h(bauteil, { title, sub }, {
      ...(aktion ? { actions: () => Vue.h('button', { class: 'test-aktion' }, '+') } : {}),
      default: () => Vue.h('p', { class: 'test-inhalt' }, 'Inhalt'),
    }),
  })
  app.mount(host)
  await tick()
  return { host, weg: () => { try { app.unmount() } catch (_) {} host.remove() } }
}

const QUELLE = readFileSync(join(SRC, 'components/ui/DkCard.vue'), 'utf8')
/** Eine Regel `selektor { … }` — ohne Kommentare, erste Fundstelle. */
function regel(text, selektor) {
  const t = text.replace(/\/\*[\s\S]*?\*\//g, '')
  const i = t.indexOf(selektor)
  assert.ok(i >= 0, `Regel ${selektor} fehlt`)
  const auf = t.indexOf('{', i)
  const zu = t.indexOf('}', auf)
  return t.slice(auf + 1, zu)
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Kopfstruktur am ECHTEN Bauteil
// ══════════════════════════════════════════════════════════════════════════
test('DES-1 · Titel und Aktionsbereich sind GESCHWISTER im Kopf', async () => {
  const { host, weg } = await karte({ title: 'Rollen der Gruppe', aktion: true })
  const kopf = host.querySelector('.dk-ui-card-kopf')
  assert.ok(kopf, 'Kartenkopf fehlt')
  const text = kopf.querySelector(':scope > .dk-ui-card-kopftext')
  assert.ok(text, 'Titel und Unterzeile sitzen nicht in EINEM Textfeld (.dk-ui-card-kopftext)')
  assert.equal(text.querySelector('.dk-ui-card-titel')?.textContent, 'Rollen der Gruppe',
    'der Titel steht nicht im Textfeld')
  const aktionen = kopf.querySelector(':scope > .dk-ui-card-aktionen')
  assert.ok(aktionen, 'der Aktionsbereich ist kein Geschwister des Textfelds')
  assert.ok(aktionen.querySelector('.test-aktion'), 'der Aktionsinhalt fehlt')
  // NICHT im Textfeld und nicht im Körper: der Aktionsbereich darf den Titel
  // nicht einengen.
  assert.equal(text.querySelector('.dk-ui-card-aktionen'), null,
    'der Aktionsbereich sitzt IM Textfeld und quetscht den Titel')
  assert.equal(host.querySelector('.dk-ui-card-koerper .dk-ui-card-aktionen'), null,
    'der Aktionsbereich steht im Körper statt im Kopf')
  weg()
})

test('DES-1 · der Titel bleibt einzeilig, solange Platz ist', async () => {
  const { host, weg } = await karte({ title: 'Kalender der Gruppe' })
  const titel = host.querySelector('.dk-ui-card-titel')
  assert.ok(titel, 'Titel fehlt')
  // Bildschirm-Regel (nicht die Handy-Regel): einzeilig mit Ellipse.
  assert.match(regel(QUELLE, '.dk-ui-card-titel {'), /white-space:\s*nowrap/,
    'der Titel darf nicht mehr grundsätzlich umbrechen')
  assert.match(regel(QUELLE, '.dk-ui-card-titel {'), /text-overflow:\s*ellipsis/,
    'abgeschnitten wird mit Ellipse, nicht mitten im Wort')
  // Das Textfeld darf wachsen UND schrumpfen (Review 7: mit Mindestbreite).
  const feld = regel(QUELLE, '.dk-ui-card-kopftext {')
  assert.match(feld, /flex:\s*1 1 12rem/, 'das Textfeld bekommt nicht den freien Platz (flex: 1 1 12rem)')
  assert.match(feld, /min-width:\s*0/, 'das Textfeld darf nicht schrumpfen (Inhalt sprengt den Kopf)')
  // Die Aktionen behalten ihre natürliche Breite.
  assert.match(regel(QUELLE, '.dk-ui-card-aktionen {'), /flex:\s*0 0 auto/,
    'die Aktionen schrumpfen zugunsten des Titels')
  weg()
})

test('DES-1 · Review 6: der Titel trägt den vollen Text als `title`-Attribut', async () => {
  // Ein per Ellipse abgeschnittener Titel wäre sonst nur gekürzt lesbar.
  const { host, weg } = await karte({ title: 'Registrierung Sommerfreizeit 2027' })
  const titel = host.querySelector('.dk-ui-card-titel')
  assert.ok(titel, 'Titel fehlt')
  assert.equal(titel.getAttribute('title'), 'Registrierung Sommerfreizeit 2027',
    'der Titel hat kein `title`-Attribut mit dem vollen Text')
  weg()
})

test('DES-1 · Review 2: `ebene` wählt die Überschriftsebene (Standard h2, Zeile h3)', async () => {
  const bauteilUrl = pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href
  const bauteil = (await import(bauteilUrl)).default
  for (const [ebene, erwartet] of [[undefined, 'H2'], [3, 'H3']]) {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = Vue.createApp({
      render: () => Vue.h(bauteil, { title: 'Proben', ebene }, {}),
    })
    app.mount(host)
    await tick()
    const titel = host.querySelector('.dk-ui-card-titel')
    assert.equal(titel.tagName, erwartet,
      `Titel ist ${titel.tagName}, erwartet ${erwartet} (ebene=${ebene})`)
    app.unmount()
    host.remove()
  }
})

test('DES-1 · Review 7: der Kopf bricht NUR bei Platzmangel um', () => {
  // Nicht `space-between` (presste den Titel auf seine längste Wortbreite),
  // aber `wrap` — sonst quetscht ein Kopf mit zwei Abzeichen (Registrierung)
  // den Titel in einer 300-px-Karte.
  const kopf = regel(QUELLE, '.dk-ui-card-kopf {')
  assert.ok(!/justify-content:\s*space-between/.test(kopf),
    'space-between presste den Titel auf seine längste Wortbreite')
  assert.match(kopf, /flex-wrap:\s*wrap/,
    'ohne `wrap` quetscht ein voller Aktionsbereich den Titel')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Unterzeile (`sub`) gehört in den Kopf, nicht in den Körper
// ══════════════════════════════════════════════════════════════════════════
test('DES-1 · `sub` steht unter dem Titel im Textfeld, über die volle Breite', async () => {
  const { host, weg } = await karte({ title: 'Rollen der Gruppe', sub: 'Auswählbar sind nur Personen mit einem Zugang (Konto).', aktion: true })
  const text = host.querySelector('.dk-ui-card-kopftext')
  assert.ok(text, 'Textfeld fehlt')
  const unter = text.querySelector('.dk-ui-card-sub')
  assert.ok(unter, 'die Unterzeile fehlt im Textfeld')
  assert.ok(txt(unter).startsWith('Auswählbar sind nur Personen'),
    `Unterzeile lautet „${txt(unter)}“`)
  // Reihenfolge: Titelzeile, dann Unterzeile.
  // DES-1b (Review 4): der Titel liegt jetzt in `.dk-ui-card-titelzeile`
  // (Punkt und Titel in einer Zeile), die Unterzeile steht darunter über die
  // volle Breite des Textfelds.
  const kinder = [...text.children].map((k) => k.className)
  assert.deepEqual(kinder.slice(0, 2), ['dk-ui-card-titelzeile', 'dk-ui-card-sub'],
    'Titel und Unterzeile stehen nicht untereinander')
  assert.ok(text.children[0].querySelector('.dk-ui-card-titel'),
    'der Titel liegt nicht in der Titelzeile')
  // NICHT im Körper: dort wäre sie ein Absatz neben Titel/Aktionen.
  assert.equal(host.querySelector('.dk-ui-card-koerper .dk-ui-card-sub'), null,
    'die Unterzeile steht im Körper statt im Kopf')
  // Der Körper bleibt der Inhalt.
  assert.equal(txt(host.querySelector('.dk-ui-card-koerper')), 'Inhalt')
  weg()
})

test('DES-1 · ohne `sub` steht keine leere Unterzeile im DOM', async () => {
  const { host, weg } = await karte({ title: 'Details' })
  assert.equal(host.querySelector('.dk-ui-card-sub'), null, 'leere Unterzeile im DOM')
  weg()
})

test('DES-1 · nur `sub` (ohne Titel) ergibt trotzdem einen Kopf', async () => {
  // Eigenschaft `sub` allein muss den Kopf aufbauen — sonst verschluckt eine
  // Karte mit Unterzeile aber ohne Titel ihre Beschreibung.
  const { host, weg } = await karte({ sub: 'Nur eine Beschreibung.' })
  const unter = host.querySelector('.dk-ui-card-kopf .dk-ui-card-sub')
  assert.ok(unter, 'der Kopf fehlt, obwohl es eine Unterzeile gibt')
  assert.equal(txt(unter), 'Nur eine Beschreibung.')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Handy (390 px)
// ══════════════════════════════════════════════════════════════════════════
test('DES-1 · am Handy bekommt der Titel die volle Breite', () => {
  const t = QUELLE.replace(/\/\*[\s\S]*?\*\//g, '')
  const i = t.indexOf('@media (max-width: 720px)')
  assert.ok(i >= 0, 'es gibt keine Handy-Regel für den Kartenkopf')
  const block = t.slice(i)
  assert.match(block, /\.dk-ui-card-kopftext\s*\{[^}]*flex-basis:\s*100%/,
    'am Handy steht der Titel nicht über die volle Breite')
  assert.match(block, /\.dk-ui-card-kopf\s*\{[^}]*flex-wrap:\s*wrap/,
    'am Handy bricht der Aktionsbereich nicht auf eine eigene Zeile')
  assert.match(block, /\.dk-ui-card-titel\s*\{[^}]*white-space:\s*normal/,
    'am Handy bliebe der Titel einzeilig und würde abgeschnitten')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Die Gruppenseite überschreibt den Kopf nicht mehr lokal
// ══════════════════════════════════════════════════════════════════════════
const SEITE = readFileSync(join(SRC, 'pages/GruppeDetail.vue'), 'utf8')
const ROLLEN = readFileSync(join(SRC, 'components/gruppen/RollenEinstellungen.vue'), 'utf8')
const KALENDER = readFileSync(join(SRC, 'components/gruppen/KalenderEinstellungen.vue'), 'utf8')

test('DES-1 · die Gruppenseite erzwingt keine Titelhöhe mehr (Review 4)', () => {
  const t = SEITE.replace(/\/\*[\s\S]*?\*\//g, '')
  // Höchstens in einer Desktop-Media-Query, und NIE als `line-height` auf dem
  // Titel (das machte am Handy jede Titelzeile 56 px hoch).
  assert.ok(!/\.dk-ui-card-titel\s*\{[^}]*line-height/.test(t),
    'die Seite setzt noch eine `line-height` auf dem Titel')
  assert.ok(!/\.dk-ui-card-titel\s*\{[^}]*min-height/.test(t),
    'die Seite setzt noch eine Mindesthöhe auf dem Titel')
  const i = t.indexOf(':deep(.dk-ui-card-kopf)')
  if (i >= 0) {
    const vorher = t.slice(Math.max(0, i - 400), i)
    assert.match(vorher, /@media\s*\(min-width:/,
      'die Kopf-Mindesthöhe gilt nicht nur ab Desktop-Breite')
  }
})

test('DES-1 · die Beschreibungen der Einstellungs-Karten kommen als `sub` an', () => {
  const tpl = SEITE.slice(SEITE.indexOf('<template>'), SEITE.lastIndexOf('</template>'))
  assert.match(tpl, /<DkCard title="Rollen der Gruppe" :sub="rollenHinweis">/,
    '„Rollen der Gruppe“ bekommt keine Unterzeile aus der einen Quelle')
  assert.match(tpl, /title="Kalender der Gruppe"\s*\n?\s*:sub="kalenderHinweis"/,
    '„Kalender der Gruppe“ bekommt keine Unterzeile aus der einen Quelle')
  // EINE Quelle: die Bausteine melden ihren Text, die Seite schreibt ihn nicht.
  assert.match(tpl, /@hinweis="rollenHinweis = \$event"/,
    'der Rollen-Baustein meldet seine Beschreibung nicht')
  assert.match(tpl, /@hinweis="kalenderHinweis = \$event"/,
    'der Kalender-Baustein meldet seine Beschreibung nicht')
  assert.match(QUELLE, /sub:\s*\{ type: String/, 'DkCard kennt die Eigenschaft `sub` nicht')
})

test('DES-1 · kein nachgebauter Kartenkopf mehr (Kalenderzeile = DkCard-Kopf)', () => {
  // Die Kalenderzeile baute Titel, Farbpunkt und Zuordnung als eigenen Kopf im
  // Kartenkörper nach (`.ke-kopf`, `.ke-name`, `.ke-meta`) — genau die zweite
  // Fassung, die die SSOT umging. Jetzt trägt der Baustein sie.
  const tpl = KALENDER.slice(KALENDER.indexOf('<template>'), KALENDER.lastIndexOf('</template>'))
  assert.match(tpl, /<DkCard[\s\S]{0,400}?:title="k\.titel"[\s\S]{0,120}?:sub="kalenderZeileText\(k\)"/,
    'die Kalenderzeile bekommt Titel und Zuordnung nicht aus dem Kartenkopf')
  assert.match(tpl, /flach[\s\S]{0,200}:ebene="3"/,
    'die Kalenderzeile ist keine flache Zeile auf Ebene h3')
  assert.ok(!/class="ke-kopf"/.test(tpl), 'der nachgebaute Kopf (.ke-kopf) steht noch da')
  assert.ok(!/class="ke-name"/.test(tpl), 'der nachgebaute Titel (.ke-name) steht noch da')
  const stil = KALENDER.slice(KALENDER.lastIndexOf('<style'))
  for (const selektor of ['.ke-kopf {', '.ke-karten-titel {', '.ke-name {', '.ke-meta {']) {
    assert.ok(!stil.includes(selektor), `eigene Kartenkopf-Regel ${selektor} steht noch im Stil`)
  }
})

test('DES-1 · Review 2/3: die Kalenderzeile ist flach, h3 und zeigt ihren Farbpunkt', () => {
  const tpl = KALENDER.slice(KALENDER.indexOf('<template>'), KALENDER.lastIndexOf('</template>'))
  // Review 3: der Farbpunkt vor dem Titel (er war vorher sichtbar).
  assert.match(tpl, /<span[\s\S]{0,200}class="ke-farbe"[\s\S]{0,200}:style="\{ background: k\.farbe/,
    'der Farbpunkt des Kalenders fehlt in der Zeile')
  // DES-1b: der Punkt steht im Slot VOR dem Bauteil-Titel — kein nachgebautes
  // h3 (`.ke-titel`) und keine eigene Ellipse (`.ke-titel-text`) mehr.
  assert.match(tpl, /<template #vor-titel>/,
    'die Zeile bringt den Farbpunkt nicht über den Slot `#vor-titel` an')
  // DES-1b (Review 4): die Zeile trägt `zeile` — nur so gibt der Bauteil-Kopf
  // seine Polsterung ab; `flach` trägt sie weiterhin für den Körper.
  assert.match(tpl, /class="ke-zeile"\s*\n?\s*flach\s*\n?\s*zeile/,
    'die Kalenderzeile trägt nicht `zeile` (Kopf-Polsterung bleibt stehen)')
  assert.ok(!/<h3 class="dk-ui-card-titel/.test(tpl),
    'die Zeile baut ihren Titel (h3.dk-ui-card-titel) noch selbst')
  ASSERT_KEIN_EIGENBAU: {
    // (`ke-titel` steht im Quelltext nur noch in Kommentaren — geprüft wird der
    // Vorlagenrest ohne Kommentare.)
    assert.ok(!/ke-titel/.test(tpl.replace(/<!--[\s\S]*?-->/g, '')),
      'die Zeile hat noch ein eigenes Titelmakup (.ke-titel)')
    assert.ok(!/ke-titel-text/.test(KALENDER.replace(/\/\*[\s\S]*?\*\//g, '')),
      'die eigene Ellipse (.ke-titel-text) steht noch im Bauteil')
    const stil = KALENDER.slice(KALENDER.lastIndexOf('<style'))
    assert.ok(!/\.ke-titel\s*\{/.test(stil), 'die Regel .ke-titel steht noch im Stil')
    assert.ok(!/\.ke-titel-text\s*\{/.test(stil), 'die Regel .ke-titel-text steht noch im Stil')
  }
  // Review 2: keine Karte in der Karte — kein Schatten, keine eigene Fläche.
  const zeile = regel(KALENDER, '.ke-zeile {')
  assert.match(zeile, /box-shadow:\s*none/, 'die Kalenderzeile wirft noch einen eigenen Schatten')
  assert.match(zeile, /background:\s*transparent/, 'die Kalenderzeile hat noch eine eigene Kartenfläche')
})

test('DES-1 · Review 1: EIN Weg zum Aufklappen — der Kopfknopf (Klick-Test)', async () => {
  // Der Kopfknopf hieß „Freigaben“ und rief `freigabenOeffnen(k)` — eine
  // Funktion, die es nicht gibt (TypeError beim Klick). Jetzt hängt er an
  // `umschalten`, und der doppelte Körperknopf ist entfallen. Geprüft wird der
  // KLICK am echten Bauteil: Knopf drücken → Freigaben-Bereich erscheint.
  const tpl = KALENDER.slice(KALENDER.indexOf('<template>'), KALENDER.lastIndexOf('</template>'))
  assert.ok(!/freigabenOeffnen/.test(KALENDER),
    'der Aufruf einer nicht existierenden Funktion steht noch im Bauteil')
  assert.equal((tpl.match(/class="ke-aufklappen"/g) || []).length, 1,
    'es gibt mehr als einen Aufklapp-Knopf (EIN Weg verlangt)')
  assert.ok(!/Freigaben & Sichtbarkeit/.test(tpl),
    'der zweite Knopf „Freigaben & Sichtbarkeit“ steht noch im Körper')
  assert.match(tpl, /class="ke-aufklappen"[\s\S]{0,400}@click="umschalten\(k\.name\)"/,
    'der Kopfknopf hängt nicht an `umschalten`')
})

test('DES-1 · die Bausteine tragen den Text als EINE Quelle (kein Absatz im Körper)', () => {
  for (const [datei, name] of [[ROLLEN, 'RollenEinstellungen'], [KALENDER, 'KalenderEinstellungen']]) {
    assert.match(datei, /defineEmits\(\[[^\]]*'hinweis'/,
      `${name}: meldet die Beschreibung nicht an die Seite`)
    assert.match(datei, /emit\('hinweis', text\)/,
      `${name}: der gemeldete Wert fehlt`)
  }
  // Der alte Absatz im Kartenkörper ist weg (er quetschte den Titel daneben).
  assert.ok(!/class="gr-rollen-hinweis"/.test(ROLLEN),
    'RollenEinstellungen: der Beschreibungs-Absatz steht noch im Körper')
  assert.ok(!/class="ke-hinweis"/.test(KALENDER),
    'KalenderEinstellungen: der Beschreibungs-Absatz steht noch im Körper')
  // Der Wortlaut bleibt unverändert (EINE Fassung, nicht zwei).
  assert.match(ROLLEN, /Die Gruppenleitung führt diese Untergruppe/,
    'der Untergruppen-Text fehlt in der einen Quelle')
  assert.match(KALENDER, /Hier stehen die Kalender \$\{wo\}/,
    'der Kalender-Text fehlt in der einen Quelle')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Auch die übrigen Karten der Gruppenseite folgen der SSOT
// ══════════════════════════════════════════════════════════════════════════
test('DES-1 · Mengen-Angaben stehen als Unterzeile, nicht im Aktionsbereich', () => {
  const tpl = SEITE.slice(SEITE.indexOf('<template>'), SEITE.lastIndexOf('</template>'))
  // Mitgliederzahl: vorher ein `span.grup-zahl` im #actions-Slot (eine
  // Aussage dort, wo eine Handlung hingehört), in der Leseansicht ein Absatz
  // am Kartenende. Jetzt EINE Unterzeile am Kopf.
  assert.match(tpl, /title="Mitglieder"\s*\n?\s*:sub="zahlWort\(mitglieder\.length, 'Mitglied', 'Mitglieder'\)"/,
    'die Mitgliederzahl steht nicht als Unterzeile im Kartenkopf')
  assert.match(tpl, /:sub="`\$\{zahlWort\(mitglieder\.length, 'Mitglied', 'Mitglieder'\)\} in dieser Gruppe`"/,
    'die Mitgliederzahl der Leseansicht steht nicht als Unterzeile')
  assert.ok(!/class="grup-zahl"/.test(tpl), 'die Zahl steht noch im Aktionsbereich/Text der Karte')
  assert.ok(!/grup-muted">\{\{ zahlWort\(mitglieder/.test(tpl),
    'die Mitgliederzahl steht noch als Absatz am Kartenende')
  // Aufgaben: „3 offen“ als Unterzeile, die alte Absatzzeile im Körper ist weg.
  assert.match(tpl, /<DkCard title="Aufgaben" :sub="aufgabenSub">/,
    '„3 offen“ steht nicht als Unterzeile im Kartenkopf')
  assert.ok(!/class="grup-zahl grup-aufgaben-zahl"/.test(tpl),
    'die Aufgabenzeile steht noch als eigener Absatz über der Liste')
  // Der Fokusanker der Tastatur bleibt an derselben Stelle.
  assert.match(tpl, /ref="aufgabenUeberschrift"[\s\S]{0,120}class="grup-fokusanker"[\s\S]{0,80}tabindex="-1"/,
    'der Fokusanker nach dem Abhaken fehlt')
  // Die Unterzeile kommt aus der EINEN Quelle.
  assert.match(SEITE, /const aufgabenSub = computed\(\(\) => \(aufgaben\.value\.length \? offenZahlText\(aufgaben\.value\) : ''\)\)/,
    'die Aufgaben-Unterzeile hat keine eigene Quelle (offenZahlText)')
})

test('DES-1 · auf der Gruppenseite baut keine Karte ihren Kopf selbst', () => {
  const tpl = SEITE.slice(SEITE.indexOf('<template>'), SEITE.lastIndexOf('</template>'))
  assert.ok(!/class="[^"]*dk-ui-card-titel/.test(tpl), 'ein eigener Kartentitel in der Seite')
  const stil = SEITE.slice(SEITE.lastIndexOf('<style'))
  for (const selektor of ['.dk-ui-card-kopf {', '.dk-ui-card-titel {', '.dk-ui-card-sub {']) {
    assert.ok(!stil.includes(selektor), `eigene Kartenkopf-Regel ${selektor} in der Seite`)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · DES-1b — Kalenderzeilen-Kopf ohne nachgebautes Markup
// ══════════════════════════════════════════════════════════════════════════

/** `DkCard` mit Kennzeichen VOR dem Titel mounten (Slot `vor-titel`). */
async function karteMitPunkt({ title = '', sub = '', ebene } = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    render: () => Vue.h(bauteil, { title, sub, ebene }, {
      'vor-titel': () => Vue.h('span', { class: 'test-punkt' }, ''),
      default: () => Vue.h('p', { class: 'test-inhalt' }, 'Inhalt'),
    }),
  })
  app.mount(host)
  await tick()
  return { host, weg: () => { try { app.unmount() } catch (_) {} host.remove() } }
}

test('DES-1b · der Titel im Slot-Kopf ist der DkCard-eigene Titel (h3), kein Eigenbau', async () => {
  // Der `#header`-Slot der Kalenderzeile baute `<h3 class="dk-ui-card-titel">`
  // von Hand. `DkCards <style scoped>` erreicht Slot-Inhalt NICHT — im Browser
  // galt der Standard für h3/p (Größe, ~1em Rand, falsche Farbe), die Zeile war
  // viel höher als jeder andere Kopf, und `ebene`/`title`/`sub` der Karte waren
  // toter Code. Jetzt liefert den Titel der Baustein selbst.
  const { host, weg } = await karteMitPunkt({ title: 'Chor', sub: 'Gruppe · Lesen nur bei Freigabe', ebene: 3 })
  const titel = host.querySelector('.dk-ui-card-kopftext .dk-ui-card-titel')
  assert.ok(titel, 'der Titel fehlt im Textfeld des Bausteins')
  assert.equal(titel.tagName, 'H3', `der Titel ist ${titel.tagName}, erwartet H3 (ebene=3)`)
  assert.equal(txt(titel), 'Chor')
  // DER Punkt: es gibt KEINEN nachgebauten Titel mehr — genau ein Titel im Kopf.
  assert.equal(host.querySelectorAll('.dk-ui-card-titel').length, 1,
    'es stehen mehrere Titel im Kopf (Eigenbau neben dem Bauteil-Titel)')
  assert.equal(host.querySelector('.ke-titel, .ke-titel-text'), null,
    'ein nachgebautes Titelmakup steht noch im Kopf')
  // Der Punkt steht VOR dem Titel (gleiche Titelzeile, davor).
  const feld = host.querySelector('.dk-ui-card-kopftext')
  // DES-1b (Review 4): Punkt und Titel liegen in EINER Zeile
  // (`.dk-ui-card-titelzeile`) — vorher stand der Punkt im Spaltenblock und
  // damit in eigener Zeile ÜBER dem Titel.
  const kinder = [...feld.children].map((k) => k.className)
  assert.deepEqual(kinder, ['dk-ui-card-titelzeile', 'dk-ui-card-sub'],
    `Reihenfolge im Textfeld: ${kinder.join(' | ')}`)
  const zeile = feld.children[0]
  const zeileKinder = [...zeile.children].map((k) => k.className)
  assert.deepEqual(zeileKinder, ['dk-ui-card-vor', 'dk-ui-card-titel'],
    `Reihenfolge in der Titelzeile: ${zeileKinder.join(' | ')}`)
  assert.ok(zeile.children[0].querySelector('.test-punkt'),
    'das Kennzeichen-Feld steht nicht VOR dem Titel')
  assert.equal(zeile.children[1].tagName, 'H3', 'der Titel ist nicht das zweite Kind der Titelzeile')
  assert.equal(txt(host.querySelector('.dk-ui-card-sub')), 'Gruppe · Lesen nur bei Freigabe')
  weg()
})

test('DES-1b · ohne `vor-titel`-Slot steht kein leeres Kennzeichen im Kopf', async () => {
  const { host, weg } = await karte({ title: 'Rollen der Gruppe' })
  assert.equal(host.querySelector('.dk-ui-card-vor'), null,
    'ein leeres Kennzeichen-Feld belegt Platz im Kopf')
  weg()
})

test('DES-1b · `ebene` hat einen Prüfer (nur 2, 3, 4)', async () => {
  const quelle = readFileSync(join(SRC, 'components/ui/DkCard.vue'), 'utf8')
  assert.match(quelle, /validator:\s*\(v\)\s*=>\s*\[2,\s*3,\s*4\]\.includes\(Number\(v\)\)/,
    '`ebene` nimmt jeden Wert an (ein h7 hat keinen Gliederungswert)')
  // Am echten Bauteil: erlaubte Ebenen liefern ihre Überschrift, `7` nicht.
  const bauteilUrl = pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href
  const bauteil = (await import(bauteilUrl)).default
  for (const [ebene, erwartet] of [[2, 'H2'], [3, 'H3'], [4, 'H4']]) {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = Vue.createApp({ render: () => Vue.h(bauteil, { title: 'Proben', ebene }, {}) })
    app.mount(host)
    await tick()
    assert.equal(host.querySelector('.dk-ui-card-titel')?.tagName, erwartet,
      `ebene=${ebene} ergibt nicht ${erwartet}`)
    app.unmount()
    host.remove()
  }
})

test('DES-1b · `zeile` nimmt dem KOPF die Karteninnen-Polsterung — nicht `flach`', async () => {
  // Review 4: Review 3 hing die Kopf-Polsterung an `flach`. Das trafen auch
  // eigenständige Seitenleisten-Karten (Beiträge, Wiki: `title` + `flach`) —
  // dort klebte der Titel am Kartenrand. Jetzt entscheidet `zeile` („diese
  // Karte IST eine Zeile in einer anderen Karte“).
  assert.match(regel(QUELLE, '.dk-ui-card.is-zeile .dk-ui-card-kopf {'), /padding:\s*0/,
    'die Zeilen-Regel für den Kopf fehlt')
  assert.ok(!/is-flach\s+\.dk-ui-card-kopf\s*\{[^}]*padding:\s*0/.test(QUELLE),
    '`flach` nimmt dem Kopf noch die Polsterung (Regression an Beiträge/Wiki)')
  // `flach` regelt weiter NUR den Körper.
  assert.match(regel(QUELLE, '.dk-ui-card-koerper.is-flach {'), /padding:\s*0/,
    'der flache Körper hat keine eigene Regel mehr')
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href)).default
  for (const [props, erwartet] of [
    [{ title: 'Chor', flach: '' }, false],
    [{ title: 'Chor', zeile: '' }, true],
    [{ title: 'Chor' }, false],
  ]) {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = Vue.createApp({ render: () => Vue.h(bauteil, props, {}) })
    app.mount(host)
    await tick()
    const karteEl = host.querySelector('.dk-ui-card')
    const kopfEl = karteEl.querySelector(':scope > .dk-ui-card-kopf')
    assert.ok(kopfEl, 'der Kopf ist kein direktes Kind der Karte — die Regel greift nicht')
    assert.equal(kopfEl.matches('.dk-ui-card.is-zeile .dk-ui-card-kopf'), erwartet,
      `Kopf-Polsterung-Regel bei ${JSON.stringify(props)}: erwartet ${erwartet}`)
    // `zeile` ist eine Boolean-Eigenschaft: Vue macht `zeile=""` zu `true`,
    // fehlt sie, ist sie `false` (nicht '' — deshalb hier NICHT Boolean(props.zeile)).
    assert.equal(karteEl.classList.contains('is-zeile'), 'zeile' in props,
      `\`zeile\` zeichnet sich nicht an der Kartenwurzel aus (class="${karteEl.className}")`)
    app.unmount()
    host.remove()
  }
})

test('DES-1b · der Aufklapp-Knopf zeigt mit `aria-controls` auf sein Feld', async () => {
  const tpl = KALENDER.slice(KALENDER.indexOf('<template>'), KALENDER.lastIndexOf('</template>'))
  assert.match(tpl, /class="ke-aufklappen"[\s\S]{0,500}:aria-controls="freigabenFeldId\(k\.name\)"/,
    'der Aufklapp-Knopf nennt sein Feld nicht (kein `aria-controls`)')
  assert.match(tpl, /:id="freigabenFeldId\(k\.name\)"[\s\S]{0,200}class="ke-koerper"/,
    'das aufklappbare Feld hat keine id, auf die `aria-controls` zeigen könnte')
  // Die Kennung ist ein gültiger HTML-id-Wert, auch für krumme Kalendernamen.
  const m = KALENDER.match(/function freigabenFeldId\(name\) \{[\s\S]*?\n\}/)
  assert.ok(m, 'die id-Kennung hat keine eine Quelle (`freigabenFeldId`)')
  const fn = new Function(`${m[0]}; return freigabenFeldId;`)()
  assert.equal(fn('op2'), 'ke-freigaben-op2')
  assert.equal(fn('team: 2027 A'), 'ke-freigaben-team--2027-A',
    'Doppelpunkt/Leerzeichen landen ungefiltert in der id')
})
