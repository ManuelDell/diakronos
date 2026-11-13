/**
 * MT-1b — Eingeklappte Leiste: Ausklapp-Knopf sichtbar + Avatar-Klick.
 *
 * Folgekarte aus dem Review von MT-1 (t_1e896d54). Seit MT-1 ist der Knopf
 * `.dk-sb-collapse` am Desktop der EINZIGE Einstieg in die volle Leiste. Drei
 * Befunde (Karte t_f942cc78):
 *
 *   1. Der Knopf war mit 14-px-Symbol in gedämpfter Farbe kaum zu erkennen →
 *      er trägt jetzt ein eigenes, sichtbares Symbol (ausgeklappt: „einklappen“,
 *      eingeklappt: „ausklappen“) in normaler Textfarbe, mit `aria-expanded`,
 *      `aria-hidden` am SVG und einem verständlichen `aria-label`.
 *   2. In der eingeklappten Leiste setzte ein Klick aufs Avatar `profilOffen`
 *      und `aria-expanded="true"`, das Menü erschien aber nicht
 *      (`v-if="profilOffen && !collapsed"`) — Klick ins Leere. Jetzt: in der
 *      eingeklappten Leiste klappt der Avatar die Leiste AUS (der einzige
 *      sichtbare Weg zum Menü) und `aria-expanded` sagt die Wahrheit.
 *   3. Veraltete Kommentare, die der MT-1-Umbau überholt hat (Hamburger der
 *      Kopfzeile als zweiter Einstieg, 40-px-Mausziel am Laptop,
 *      „(eingeklappte) Seitenleiste mit Menü-Knopf“ im schmalen Maus-Fenster),
 *      sind berichtigt — und der 40-px-Zweig von `--dk-menue-knopf-h` ist weg:
 *      der Knopf existiert nur noch in der Handy-Lage (grober Zeiger).
 *
 * MT-1b2 (Review der Karte oben): Das Popover aus MT-1b ist ZURÜCKGENOMMEN —
 * eingeklappt klappt der Avatar die Leiste aus, das Profilmenü steht wieder im
 * Fluss der ausgeklappten Leiste (Kasten `x 8…264` lag AUF der Leiste
 * `0…256`, `.dk-sidebar` schnitt es mit `overflow: hidden` ab, `bottom: 0`
 * verdeckte „Abmelden“ und Avatar). Escape gibt den Fokus an den Avatar
 * zurück, `aria-haspopup` kündigt eingeklappt kein Menü an.
 *
 * Geprüft wird, was das Bauteil WIRKLICH TUT: `AppSidebar.vue` wird in einer
 * jsdom gemountet (dieselbe Technik wie `dev-b2-prueftafel-reiter.test.mjs`),
 * geklickt und danach am DOM nachgesehen; CSS/Texte als Quelltext-Muster.
 * Nur Dateien innerhalb von frontend/, kein Netz (Regel 13).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
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

/** CSS ohne Kommentare — Muster dürfen nicht in alten Erklärtexten greifen. */
function ohneCssKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}
function ohneHtmlKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

// ── SFC-Mount (wie dev-b2-prueftafel-reiter.test.mjs) ──────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'SVGElement', 'CSS']) {
  globalThis[schluessel] = dom.window[schluessel]
}
// Das Boot-Objekt liest `useSession.js` beim Modulstart.
dom.window.__DIakonosBOOT = {
  user_fullname: 'Test Nutzer',
  user_email: 'test@example.org',
  is_admin: true,
  roles: ['Administrator', 'System Manager'],
  modules: [],
}
globalThis.window = dom.window

const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'mt1b-'))
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
    if (!spec.startsWith('.')) return v
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

/**
 * Montiert `AppSidebar.vue` mit den echten Eigenschaften (`collapsed`, `theme`)
 * und sammelt die ausgelösten Ereignisse des Bauteils.
 */
async function leisteMounten({ collapsed }) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/AppSidebar.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const ereignisse = []
  const warnungen = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({
      p: {
        collapsed,
        theme: 'light',
        onToggleCollapse: () => ereignisse.push('toggle-collapse'),
        onToggleTheme: () => ereignisse.push('toggle-theme'),
        onCloseMobile: () => ereignisse.push('close-mobile'),
      },
    }),
    template: '<Geprueft v-bind="p" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, ereignisse, warnungen }
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Der Ausklapp-Knopf ist der EINZIGE Einstieg — und er sagt, was er tut
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b: der Knopf der Leiste trägt aria-expanded, aria-hidden-SVG und ein klares Label', async () => {
  const zu = await leisteMounten({ collapsed: true })
  assert.deepEqual(zu.warnungen, [], 'Vue meldet kein Problem')
  const knopf = zu.host.querySelector('.dk-sb-collapse')
  assert.ok(knopf, 'der Ausklapp-Knopf fehlt in der eingeklappten Leiste')
  assert.equal(knopf.getAttribute('aria-expanded'), 'false', 'eingeklappt: aria-expanded=false')
  assert.match(knopf.getAttribute('aria-label') || '', /ausklappen/i,
    'Label sagt, was der Klick bewirkt („Menü ausklappen“)')
  assert.ok(knopf.querySelector('svg'), 'der Knopf trägt ein sichtbares Symbol')
  assert.equal(knopf.querySelector('svg').getAttribute('aria-hidden'), 'true',
    'das Symbol selbst ist Zierrat (Name steht im aria-label)')
  zu.app.unmount()

  const auf = await leisteMounten({ collapsed: false })
  const knopfAuf = auf.host.querySelector('.dk-sb-collapse')
  assert.equal(knopfAuf.getAttribute('aria-expanded'), 'true', 'ausgeklappt: aria-expanded=true')
  assert.match(knopfAuf.getAttribute('aria-label') || '', /einklappen/i,
    'ausgeklappt sagt der Name „einklappen“')
  auf.app.unmount()
})

test('MT-1b: der Knopf ist ein echtes Knopf-Element mit Beschriftung im Barrierebaum', async () => {
  const { host, app } = await leisteMounten({ collapsed: true })
  const knopf = host.querySelector('.dk-sb-collapse')
  // DkButton rendert ein <button type="button"> — per Tastatur erreichbar.
  assert.equal(knopf.tagName, 'BUTTON')
  assert.equal(knopf.getAttribute('type'), 'button')
  assert.ok(!knopf.disabled, 'der einzige Einstieg ist nie gesperrt')
  app.unmount()
})

test('MT-1b: der Knopf schickt toggle-collapse (Ausklappen funktioniert)', async () => {
  const { host, app, ereignisse } = await leisteMounten({ collapsed: true })
  host.querySelector('.dk-sb-collapse').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(ereignisse, ['toggle-collapse'], 'genau EIN Ausklapp-Ereignis')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Avatar-Klick in der eingeklappten Leiste ist kein Klick ins Leere
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b: eingeklappt klappt der Avatar die Leiste aus — kein Profilmenü ohne Inhalt', async () => {
  const { host, app, ereignisse, warnungen } = await leisteMounten({ collapsed: true })
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  const avatar = host.querySelector('.dk-sb-user')
  assert.ok(avatar, 'Avatar-Knopf fehlt')
  // Der Klick darf KEIN Menü ankündigen, das gar nicht gerendert wird.
  assert.equal(avatar.getAttribute('aria-expanded'), null,
    'eingeklappt führt der Avatar nicht in ein Menü — also kein aria-expanded')
  assert.equal(avatar.getAttribute('aria-label'), 'Menü ausklappen',
    'der Avatar sagt, was er eingeklappt bewirkt')

  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.deepEqual(ereignisse, ['toggle-collapse'], 'Klick klappt die Leiste aus (der Weg zum Menü)')
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null, 'kein leeres Menü gerendert')
  app.unmount()
})

test('MT-1b: ausgeklappt öffnet der Avatar das Profilmenü — und aria-expanded stimmt', async () => {
  const { host, app, ereignisse, warnungen } = await leisteMounten({ collapsed: false })
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  const avatar = host.querySelector('.dk-sb-user')
  assert.equal(avatar.getAttribute('aria-expanded'), 'false', 'zu Beginn geschlossen')
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null)

  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(avatar.getAttribute('aria-expanded'), 'true', 'offen — und das steht dran')
  const menue = host.querySelector('.dk-sb-profil-menu')
  assert.ok(menue, 'das Profilmenü ist jetzt DA (der Klick führt nicht ins Leere)')
  assert.ok(menue.querySelector('a[href="#/profile"]'), 'Menüpunkt „Profil“')
  assert.deepEqual(ereignisse, [], 'das Öffnen ist kein Ausklappen der Leiste')

  // Zweiter Klick schließt wieder.
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(avatar.getAttribute('aria-expanded'), 'false')
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null)
  app.unmount()
})

test('MT-1b: Klick neben das Profilmenü schließt es (kein hängendes Menü)', async () => {
  const { host, app } = await leisteMounten({ collapsed: false })
  const avatar = host.querySelector('.dk-sb-user')
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.ok(host.querySelector('.dk-sb-profil-menu'), 'erst offen')
  document.body.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null, 'Klick daneben schließt das Menü')
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.ok(host.querySelector('.dk-sb-profil-menu'), 'der Avatar öffnet es weiterhin')
  app.unmount()
})

test('MT-1b: Escape schließt das Profilmenü', async () => {
  const { host, app } = await leisteMounten({ collapsed: false })
  const avatar = host.querySelector('.dk-sb-user')
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.ok(host.querySelector('.dk-sb-profil-menu'), 'erst offen')
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null, 'Escape schließt')
  assert.equal(avatar.getAttribute('aria-expanded'), 'false', 'und sagt es an')
  app.unmount()
})

test('MT-1b2: das Profilmenü bleibt im Fluss der Leiste (kein Popover)', () => {
  const css = ohneCssKommentare(lies('index.css'))
  const regel = /\.dk-sb-profil-menu\s*\{([^}]*)\}/.exec(css)
  assert.ok(regel, 'Regel `.dk-sb-profil-menu` fehlt')
  const rumpf = regel[1]
  // Review MT-1b, Punkt 1: Das Popover lag mit x = 8…264 AUF der Leiste
  // (0…256), `.dk-sidebar` schnitt es mit `overflow: hidden` ab, und
  // `bottom: 0` verdeckte „Abmelden“ und den Avatar. Es ist zurückgenommen:
  // das Menü steht wieder als Block im Fuß der ausgeklappten Leiste.
  assert.ok(!/position:\s*absolute/.test(rumpf),
    'kein absolut gesetztes Popover mehr (es lag auf der Leiste und wurde abgeschnitten)')
  assert.ok(!/right:/.test(rumpf), 'kein `right`-Versatz mehr — es gibt kein „neben“')
  assert.ok(!/bottom:/.test(rumpf), 'kein `bottom: 0` mehr (das verdeckte „Abmelden“ und den Avatar)')
  assert.ok(!/z-index:/.test(rumpf), 'keine Überlagerungsebene mehr')
  assert.ok(!/width:/.test(rumpf), 'keine eigene Breite (256 px) mehr — das Menü füllt den Fuß')
  assert.ok(!/box-shadow:/.test(rumpf), 'kein Schatten eines schwebenden Kastens')
  assert.match(rumpf, /background:\s*var\(--dk-sb-hover\)/, 'Töne der Leiste, aus Tokens')
  assert.match(rumpf, /padding:\s*var\(--sp-1\)/, 'Innenabstand aus Tokens')
  // Kein Bezugsrahmen und keine Handy-Sonderregel mehr: die Sonderregel
  // `.dk-app--handy .dk-sb-profil-menu` existierte nur, um das Popover
  // zurückzunehmen — ohne Popover braucht sie niemand.
  assert.ok(!/\.dk-sb-profil\s*\{\s*position:/.test(css),
    '`.dk-sb-profil` setzt keinen Bezugsrahmen mehr')
  assert.ok(!/\.dk-app--handy\s+\.dk-sb-profil-menu/.test(css),
    'keine Handy-Sonderregel für ein Menü, das es dort gar nicht gibt')
  // Der alte Fußanker (`position: relative` für das Popover) ist mit entfallen.
  const fuss = /\.dk-sb-foot\s*\{([^}]*)\}/.exec(css)
  assert.ok(fuss, 'Regel `.dk-sb-foot` fehlt')
  assert.ok(!/position:\s*relative/.test(fuss[1]),
    '`.dk-sb-foot` ist kein Popover-Anker mehr')
  assert.match(fuss[1], /padding:\s*var\(--sp-2\)/, 'Innenabstand des Fußes aus Tokens (kein 8px)')
  // `--control-line-rand` diente allein dem Popover-Versatz. Erwähnt werden
  // darf es nur noch als „ist entfallen“ (hier und in tokens.css).
  const stellen = (lies('index.css') + lies('tokens.css')).split('--control-line-rand').slice(1)
  for (const umgebung of stellen) {
    assert.match(umgebung.slice(0, 120), /entfallen/,
      '`--control-line-rand` steht nirgends mehr als Token — nur noch als „entfallen“-Notiz')
  }
  assert.ok(!/--control-line-rand\s*:/.test(ohneCssKommentare(lies('tokens.css'))),
    'und gesetzt wird es auch nicht mehr')
})

test('MT-1b2: Escape gibt den Fokus an den Avatar zurück (nicht an <body>)', async () => {
  const { host, app } = await leisteMounten({ collapsed: false })
  const avatar = host.querySelector('.dk-sb-user')
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  const punkt = host.querySelector('.dk-sb-profil-menu .dk-sb-profil-punkt')
  assert.ok(punkt, 'ein Menüpunkt steht bereit')
  punkt.focus()
  assert.equal(document.activeElement, punkt, 'Fokus liegt im Menü')
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null, 'Escape schließt')
  assert.equal(document.activeElement, avatar,
    'der Fokus steht wieder auf dem Avatar — sonst landet die Tastatur auf <body>')
  app.unmount()
})

test('MT-1b2: der Avatar trägt keinen doppelten Escape-Handler (Dokument reicht)', () => {
  const seite = lies('components/AppSidebar.vue')
  const tpl = ohneHtmlKommentare(seite)
  assert.ok(!/@keydown(\.esc|\.esc\.stop|\.stop)?="profilOffen = false"/.test(tpl),
    'kein eigener Escape-Handler am Knopf — der Dokument-Listener schließt und setzt den Fokus')
  assert.match(seite, /document\.addEventListener\('keydown', beiDokumentTaste\)/,
    'genau EIN Weg: der Listener am Dokument')
  assert.match(seite, /function beiDokumentTaste[\s\S]{0,400}?fokusZurueckholen\(\)/,
    'und er holt den Fokus zurück')
})

test('MT-1b2: eingeklappt kündigt der Avatar kein Menü an (aria-haspopup)', async () => {
  // Eingeklappt öffnet der Avatar die Leiste — ein `aria-haspopup="menu"`
  // verspräche ein Menü, das gar nicht erscheint (Review-Punkt 5).
  const zu = await leisteMounten({ collapsed: true })
  const knopfZu = zu.host.querySelector('.dk-sb-user')
  assert.equal(knopfZu.getAttribute('aria-haspopup'), null,
    'eingeklappt: kein aria-haspopup')
  zu.app.unmount()
  const auf = await leisteMounten({ collapsed: false })
  assert.equal(auf.host.querySelector('.dk-sb-user').getAttribute('aria-haspopup'), 'menu',
    'ausgeklappt: das Menü gibt es — es wird angekündigt')
  auf.app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Sichtbarkeit des Knopfes (Farbe, Fläche, Fokus) — aus Tokens
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b: der Knopf ist deutlich sichtbar (Textfarbe, Trefferfläche, Fokusring)', () => {
  const css = ohneCssKommentare(lies('index.css'))
  // MT-1b2 (Review-Punkt 1): Die Form steht in EINER Regel mit drei Klassen.
  // Mit einer Klasse (`.dk-sb-collapse`) verlor sie gegen DkButtons `scoped`
  // `.dk-ui-btn[data-v]` / `.dk-ui-btn--md[data-v]` / `.dk-ui-btn--ghost[data-v]`
  // — gemessen kam `border: 1px solid transparent`, `padding: 0 14px`,
  // `border-radius: 8px` und `color: var(--muted)` heraus.
  const regel = /\.dk-sidebar \.dk-sb-top \.dk-sb-collapse\s*\{([^}]*)\}/.exec(css)
  assert.ok(regel, 'Regel `.dk-sidebar .dk-sb-top .dk-sb-collapse` fehlt')
  const rumpf = regel[1]
  assert.match(rumpf, /color:\s*var\(--dk-sb-text\)/, 'normale Textfarbe statt gedämpft')
  assert.match(rumpf, /width:\s*var\(--control-h\)/, 'Trefferfläche aus --control-h')
  assert.match(rumpf, /height:\s*var\(--control-h\)/, 'Höhe aus --control-h')
  assert.match(rumpf, /padding:\s*0/, 'kein Innenabstand aus DkButton (sonst wird das Symbol gequetscht)')
  assert.match(rumpf, /border:\s*var\(--dk-sb-rahmen\)/,
    'Symbolfläche ist umrandet (Token --dk-sb-rahmen)')
  assert.match(rumpf, /border-radius:\s*var\(--radius-sm\)/,
    'quadratische Form aus dem Token, nicht DkButtons --radius')
  const fokus = /\.dk-sidebar :focus-visible[\s\S]{0,400}?\{([^}]*)\}/.exec(css)
  assert.ok(fokus, 'Seitenleisten-Fokusring fehlt')
  assert.match(fokus[1], /outline:\s*2px solid var\(--focus-ring-side\)/,
    'der Knopf erbt den deckenden Fokusring der Leiste')
  // Hover bleibt ein Token — keine harten Farbwerte.
  // MT-1b3 (Review-Punkt 1): Der Hover setzt sich gegen DkButtons `scoped`
  // `.dk-ui-btn--ghost[data-v]:hover:not(:disabled)` (0,4,0) nur mit derselben
  // Bauform durch — drei Klassen + `:not(:disabled)` + `:hover` (0,5,0),
  // und ohne hartes `#fff` (Leisten-Token).
  const hover = /\.dk-sidebar \.dk-sb-top \.dk-sb-collapse:not\(:disabled\):hover\s*\{([^}]*)\}/.exec(css)
  assert.ok(hover, 'Hover-Regel `.dk-sidebar .dk-sb-top .dk-sb-collapse:not(:disabled):hover` fehlt')
  assert.match(hover[1], /background:\s*var\(--dk-sb-hover\)/)
  assert.match(hover[1], /color:\s*var\(--dk-sb-text\)/,
    'Hover-Schrift aus dem Leisten-Token, kein hartes #fff')
  assert.ok(!/#fff\b/i.test(hover[1]), 'kein harter Weißwert im Hover')
  // Das alte Ein-Klassen-Token ist umbenannt: `--control-line` gibt es nicht
  // mehr, `--dk-sb-rahmen` ist der Name (sonst bliebe ein Token ohne die
  // Leisten-Bedeutung im Bestand).
  const tokens = ohneCssKommentare(lies('tokens.css'))
  assert.match(tokens, /--dk-sb-rahmen:\s*1px solid var\(--dk-sb-border\)/,
    '`--dk-sb-rahmen` ist das benannte Maß der Leisten-Umrandung')
  assert.ok(!/--control-line\s*:/.test(tokens),
    '`--control-line` ist umbenannt (kein zweiter Name für dasselbe Maß)')
  assert.ok(!/var\(--control-line\)/.test(css), 'und wird nirgends mehr benutzt')
})

test('MT-1b: ausgeklappt und eingeklappt zeigt der Knopf das passende Symbol', async () => {
  // Zwei verschiedene Symbole: eingeklappt „aufklappen“, ausgeklappt „zuklappen“.
  const zu = await leisteMounten({ collapsed: true })
  const pfadZu = zu.host.querySelector('.dk-sb-collapse').innerHTML
  zu.app.unmount()
  const auf = await leisteMounten({ collapsed: false })
  const pfadAuf = auf.host.querySelector('.dk-sb-collapse').innerHTML
  auf.app.unmount()
  assert.notEqual(pfadZu, pfadAuf, 'das Symbol wechselt mit dem Zustand (sonst zeigt es das Gegenteil an)')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Veraltete Kommentare und der tote 40-px-Zweig
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b2: kein Kommentar verspricht im schmalen Maus-Fenster einen Menü-Knopf', () => {
  const index = lies('index.css')
  const tokens = lies('tokens.css')
  // Review-Punkt 2: Die Gerüst-Kommentare sagten weiter, ein schmales Fenster
  // MIT MAUS bekomme die „(eingeklappte) Seitenleiste mit Menü-Knopf“. Seit
  // MT-1 existiert dieser Knopf außerhalb der Handy-Lage NICHT — der einzige
  // Einstieg ist der Ausklapp-Knopf der Leiste selbst.
  assert.ok(!/\(eingeklappte\) Seitenleiste mit Menü-Knopf/.test(index),
    'index.css: die alte Formulierung ist berichtigt')
  assert.ok(!/schmalen Fenstern eingeklappt, mit Menü-Knopf/.test(tokens),
    'tokens.css: die alte Formulierung ist berichtigt')
  assert.ok(!/Seitenleiste mit Menü-Knopf/.test(tokens + index),
    'keine Stelle verspricht mehr „Seitenleiste mit Menü-Knopf“')
  // Und die Stellen sagen, was WIRKLICH gilt: der Ausklapp-Knopf der Leiste.
  // (Gesucht wird im Gerüst-Abschnitt, dort steht der Satz.)
  const geruest = index.slice(0, index.indexOf('--- Layout: Handy-Gerüst nur bei grobem Zeiger'))
  assert.ok(geruest.length > 1000, 'Gerüst-Abschnitt in index.css gefunden')
  assert.match(geruest, /\.dk-sb-collapse/, 'index.css nennt den einen Einstieg')
  const tokenBlock = tokens.slice(tokens.indexOf('── DEV-B6 (Manuel 09.11.)'),
    tokens.indexOf('--layout-mobil:') + 400)
  assert.ok(tokenBlock.length > 200, 'Abschnitt „Handy-Bedingung“ in tokens.css gefunden')
  assert.match(tokenBlock, /Ausklapp-Knopf/, 'tokens.css nennt den einen Einstieg')
})

test('MT-1b: kein Kommentar nennt mehr den Hamburger der Kopfzeile als 2. Einstieg', () => {
  const index = lies('index.css')
  // Der Satz im Sidebar-Abschnitt beschrieb eine Regel als lebend, die MT-1
  // entfernt hat (`.dk-app.is-collapsed .dk-topbar-symbol.dk-menue-knopf`).
  assert.ok(!/weiter oben/.test(index.slice(index.indexOf('DEV-B6b (Review 10.11., Punkt 5)'),
    index.indexOf('DEV-B6b (Review 10.11., Punkt 5)') + 900)),
    'der alte Verweis auf eine nicht mehr vorhandene Regel ist berichtigt')
  const sidebarUmgebung = index.slice(index.indexOf('DEV-B6b (Review 10.11.', index.indexOf('Sidebar')), index.indexOf('DEV-B6b (Review', index.indexOf('Sidebar')) + 1200)
  assert.ok(!/die Navigation schmaler Maus-Fenster regelt allein/.test(sidebarUmgebung),
    'es gibt keine zweite Navigation für schmale Maus-Fenster mehr')
  // Die Stelle sagt jetzt, was WIRKLICH gilt.
  assert.match(sidebarUmgebung, /\.dk-sb-collapse/, 'und nennt den einen Einstieg beim Namen')
})

test('MT-1b: der Menü-Knopf wird nirgends als Mausziel am Laptop beschrieben', () => {
  const index = lies('index.css')
  const tokens = lies('tokens.css')
  const start = index.indexOf('UX3e (Entwurf A8)')
  const block = index.slice(start, start + 1400)
  assert.ok(start > 0, 'Abschnitt zum Menü-Knopf fehlt')
  // Der Knopf existiert am Laptop gar nicht mehr — also darf er dort auch
  // nicht mehr als Mausziel beschrieben werden (nur im „früher war …“-Satz).
  assert.ok(!/Trefferfläche `--dk-menue-knopf-h`: 40 px am\s*\n?\s*Maus-Laptop/.test(block),
    'der Knopf ist am Laptop gar nicht mehr da — kein „40-px-Mausziel“ mehr behaupten')
  assert.ok(!/^\.dk-topbar-symbol[^{]*\{[^}]*--dk-menue-knopf/m.test(block),
    'die Regel nimmt kein eigenes Höhen-Token mehr')
  // Am Touchgerät ist er 44 px: das sagt jetzt --control-h selbst.
  assert.ok(!/--dk-menue-knopf-h\s*:/.test(tokens),
    '--dk-menue-knopf-h ist entfernt (nur noch ein Zweig, also kein Token nötig)')
  assert.ok(!/--dk-menue-knopf-h\s*:/.test(ohneCssKommentare(index)),
    'auch index.css setzt das Token nirgends mehr')
})

test('MT-1b: der Menü-Knopf nimmt --control-h (40 am Zeiger, 44 am Finger)', () => {
  const css = ohneCssKommentare(lies('index.css'))
  const regel = /\.dk-topbar-symbol\.dk-menue-knopf\s*\{([^}]*)\}/.exec(css)
  assert.ok(regel, 'Grundregel `.dk-topbar-symbol.dk-menue-knopf` fehlt')
  assert.match(regel[1], /width:\s*var\(--control-h\)/, 'Breite aus --control-h')
  assert.match(regel[1], /height:\s*var\(--control-h\)/, 'Höhe aus --control-h')
  assert.match(regel[1], /display:\s*none/, 'ohne Handy-Lage bleibt der Knopf aus')
})

test('MT-1b: die Handy-Grenze bleibt EINE Quelle (kein neues Media im Gerüst)', () => {
  const css = ohneCssKommentare(lies('index.css'))
  const tokens = lies('tokens.css')
  // MT-1b2 (Review-Punkt 3): Hier stand „Das neue Popover darf die
  // Gerüst-Regel nicht über eine eigene Breite bauen“. Ein Popover gibt es
  // nicht mehr — das Menü steht im Fluss der ausgeklappten Leiste. Was bleibt:
  // keine eigene Breiten-Regel am Profilmenü.
  assert.ok(!/dk-sb-profil-menu[\s\S]{0,200}@media/.test(css),
    'am Profilmenü hängt keine eigene Breite (kein zweites Gerüst)')
  assert.ok(!/dk-sb-profil-menu[^{}]*\{[^}]*position:\s*absolute/.test(css),
    'das Menü ist kein Popover mehr — es steht im Fluss')
  assert.ok(!/dk-sb-profil-menu[\s\S]{0,120}\.dk-app--handy/.test(css),
    'und es hängt nicht an der Handy-Lage')
  assert.match(tokens, /--layout-mobil:\s*\(pointer: coarse\) and \(max-width: 720px\)/,
    'Handy-Lage = grober Zeiger UND schmal — unverändert')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · MT-1b2 — Kontrast der Fußzeilen-Knöpfe und der Fokus-Rückweg
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b2: „Dunkel-Modus“ und „Abmelden“ tragen die Textfarbe der Leiste', () => {
  // Review-Punkt 2: DkButton ghost setzt `color: var(--muted)` (Textfarbe für
  // HELLE Flächen) in einer `scoped` Zwei-Klassen-Regel und schlug die
  // Ein-Klassen-Regeln der Leiste — gemessen 2,4:1 („Dunkel-Modus“) und
  // 2,8:1 („Abmelden“) im hellen Modus. Beide Farben stehen jetzt in Regeln
  // mit drei Klassen; --dk-sb-text ist die eigentliche Textfarbe der Leiste.
  // MT-1b3 (Review-Punkt 3): Die hier genannten Zahlen (hell 11,15:1, dunkel
  // 7,35:1) waren falsch — sie stammten aus einer Näherung. Neu gemessen im
  // Chromium-Nachbau auf dem jeweiligen Grund: „Dunkel-Modus“ auf dem
  // Menügrund 9,34:1 (hell) / 10,83:1 (dunkel), „Abmelden“ 10,93:1 (hell) /
  // 12,24:1 (dunkel) — alle über 4,5:1.
  const css = ohneCssKommentare(lies('index.css'))
  // MT-1b3b (Review, Punkt 3): Diese beiden Prüfungen waren auf `[^}]*`
  // gelockert — damit konnten sie auch eine Regel treffen, in der `color`
  // erst nach einem `}` einer ANDEREN Regel stand. Wieder geschärft: der
  // Rumpf endet am ersten `}` (`[^}]*` bleibt nötig, weil die Regel mehrere
  // Zeilen hat), und `color` muss darin vorkommen — nur eben ohne Schlupf
  // über Regelgrenzen hinweg.
  const umschalter = /\.dk-sidebar \.dk-sb-profil-menu \.dk-sb-theme-punkt\s*\{([^}]*)\}/.exec(css)
  assert.ok(umschalter, 'Regel `.dk-sidebar .dk-sb-profil-menu .dk-sb-theme-punkt` fehlt')
  assert.match(umschalter[1], /color:\s*var\(--dk-sb-text\)/,
    'der Umschalter nimmt die Leisten-Textfarbe (drei Klassen schlagen DkButton)')
  assert.ok(!/#(fff|ffffff)\b/i.test(umschalter[1]), 'und kein harter Weißwert im Rumpf')
  const abmelden = /\.dk-sidebar \.dk-sb-foot \.dk-sb-logout\s*\{([^}]*)\}/.exec(css)
  assert.ok(abmelden, 'Regel `.dk-sidebar .dk-sb-foot .dk-sb-logout` fehlt')
  assert.match(abmelden[1], /color:\s*var\(--dk-sb-text\)/, '„Abmelden“ ebenso')
  assert.ok(!/#(fff|ffffff)\b/i.test(abmelden[1]), 'und kein harter Weißwert im Rumpf')
  // Die Quelle der beiden Töne ist die Leiste, nicht eine helle Fläche.
  const tpl = ohneHtmlKommentare(lies('components/AppSidebar.vue'))
  assert.match(tpl, /class="[^"]*dk-sb-theme-punkt[^"]*"/,
    'der Umschalter trägt die Klasse, an der die Farbe hängt')
  assert.match(tpl, /class="dk-sb-logout"/)
})

// ══════════════════════════════════════════════════════════════════════════
// 5b · MT-1b3b — Hover-Selektoren, Leistenform, eingeklappter Abmelde-Knopf
// ══════════════════════════════════════════════════════════════════════════
test('MT-1b3b: alle drei Leisten-Knöpfe haben Hover-Regeln mit 0,6,0', () => {
  // Review-Punkt 3: Vorher wurde gegen main nur der Ausklapp-Knopf-Hover rot.
  // DkButton bringt `.dk-ui-btn--ghost[data-v]:hover:not(:disabled)` (0,5,0)
  // mit; die Leisten-Regel muss deshalb drei Klassen + `:not(:disabled)` +
  // `:hover` haben (0,6,0) und den Hover-Grund aus dem Leisten-Token setzen.
  const css = ohneCssKommentare(lies('index.css'))
  const faelle = [
    ['Ausklapp-Knopf', '.dk-sidebar .dk-sb-top .dk-sb-collapse:not(:disabled):hover'],
    ['Dunkel-Modus', '.dk-sidebar .dk-sb-profil-menu .dk-sb-theme-punkt:not(:disabled):hover'],
    ['Abmelden', '.dk-sidebar .dk-sb-foot .dk-sb-logout:not(:disabled):hover'],
  ]
  for (const [name, selektor] of faelle) {
    const flucht = selektor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regel = new RegExp(flucht + '\\s*\\{([^}]*)\\}').exec(css)
    assert.ok(regel, `Hover-Regel für „${name}“ fehlt: ${selektor}`)
    assert.match(regel[1], /background:\s*var\(--dk-sb-hover\)/,
      `„${name}“: Hover-Grund aus dem Leisten-Token (kein --surface-hover)`)
    assert.match(regel[1], /color:\s*var\(--dk-sb-text\)/,
      `„${name}“: Hover-Schrift aus dem Leisten-Token`)
    assert.ok(!/#(fff|ffffff)\b/i.test(regel[1]), `„${name}“: kein harter Weißwert`)
  }
  // Und die alte, zu schwache Form (0,4,0 ohne `:not(:disabled)`) ist für
  // „Dunkel-Modus“ und „Abmelden“ nirgends mehr zu finden.
  for (const alt of ['.dk-sidebar .dk-sb-profil-menu .dk-sb-theme-punkt:hover',
    '.dk-sidebar .dk-sb-foot .dk-sb-logout:hover']) {
    assert.ok(!css.includes(alt), `die schwache Hover-Regel ${alt} ist ersetzt`)
  }
})

test('MT-1b3b: „Dunkel-Modus“ und „Abmelden“ stehen linksbündig in Leistenform', () => {
  // Review-Punkt 3: Ohne diese Prüfung blieb die Form ungeschützt — DkButtons
  // `.dk-ui-btn[data-v]` (0,2,0) setzte `justify-content: center`, `0 14px`
  // Innenabstand, `--radius`, `font-weight: 550`. Die Formregeln der Leiste
  // haben drei Klassen (0,3,0) und müssen linksbündig + Rand-frei sein.
  const css = ohneCssKommentare(lies('index.css'))
  const faelle = [
    ['Dunkel-Modus', '.dk-sidebar .dk-sb-profil-menu .dk-sb-theme-punkt'],
    ['Abmelden', '.dk-sidebar .dk-sb-foot .dk-sb-logout'],
  ]
  for (const [name, selektor] of faelle) {
    const flucht = selektor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regel = new RegExp(flucht + '\\s*\\{([^}]*)\\}').exec(css)
    assert.ok(regel, `Formregel für „${name}“ fehlt: ${selektor}`)
    assert.match(regel[1], /justify-content:\s*flex-start/, `„${name}“ steht linksbündig`)
    assert.match(regel[1], /padding:\s*0 var\(--sp-3\)|padding:\s*var\(--sp-2\) var\(--sp-3\)/,
      `„${name}“ nimmt den Innenabstand der Leiste`)
    assert.match(regel[1], /border-radius:\s*var\(--radius-sm\)/, `„${name}“ nimmt den Leisten-Radius`)
    assert.match(regel[1], /font-weight:\s*inherit/, `„${name}“ erbt die Leisten-Schriftstärke`)
    assert.match(regel[1], /border-width:\s*0/,
      `„${name}“ verliert den transparenten 1-px-Rand von DkButton (Text-x um 1 px verschoben)`)
    assert.ok(!/font-weight:\s*550/.test(regel[1]), `„${name}“ nicht 550 fett`)
  }
})

test('MT-1b3b: eingeklappt sitzt das Abmelde-Symbol wieder mittig', () => {
  // Review-Punkt 1 (MITTEL): Die Formregel `.dk-sidebar .dk-sb-foot .dk-sb-logout`
  // (0,3,0) schlug `.dk-sb-logout.is-collapsed` (0,2,0) — eingeklappt saß das
  // Symbol links (13/19 px statt 16/16 px). Der Ersatz hat mehr Klassen (0,4,0)
  // und steht NACH der Formregel.
  const css = ohneCssKommentare(lies('index.css'))
  const regel = /\.dk-sidebar \.dk-sb-foot \.dk-sb-logout\.is-collapsed\s*\{([^}]*)\}/.exec(css)
  assert.ok(regel, 'eingeklappte Regel `.dk-sidebar .dk-sb-foot .dk-sb-logout.is-collapsed` fehlt')
  assert.match(regel[1], /justify-content:\s*center/, 'Symbol wieder mittig')
  assert.match(regel[1], /padding:\s*var\(--sp-2\) 0/, 'waagerechter Innenabstand 0, senkrecht Token')
  // Die alte Zwei-Klassen-Regel daneben darf es nicht mehr geben (sonst
  // entscheidet wieder die Reihenfolge im Bündel).
  assert.ok(!/^\s*\.dk-sb-logout\.is-collapsed\s*\{/m.test(css),
    'die schwache Regel `.dk-sb-logout.is-collapsed` ist ersetzt')
  // Und die Klasse hängt im Bauteil weiter am Knopf (sonst greift nichts).
  const tpl = ohneHtmlKommentare(lies('components/AppSidebar.vue'))
  assert.match(tpl, /'is-collapsed':\s*collapsed/, 'der Knopf trägt `is-collapsed` im Zustand')
})

test('MT-1b2: Escape holt den Fokus nur zurück, wenn er im Profilbereich war', async () => {
  // Review-Punkt 4: Vorher zog Escape den Fokus BEDINGUNGSLOS zum Avatar —
  // auch dann, wenn er per Tab längst im Inhalt eines Dialogs stand.
  const { host, app } = await leisteMounten({ collapsed: false })
  const avatar = host.querySelector('.dk-sb-user')
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  assert.ok(host.querySelector('.dk-sb-profil-menu'), 'Menü offen')

  // (a) Fokus steht im INHALT (nicht im Profilbereich) → bleibt dort.
  const fremd = document.createElement('input')
  document.body.appendChild(fremd)
  fremd.focus()
  assert.equal(document.activeElement, fremd)
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(host.querySelector('.dk-sb-profil-menu'), null, 'Escape schließt das Menü')
  assert.equal(document.activeElement, fremd,
    'der Fokus wird NICHT aus dem Inhalt entführt')
  fremd.remove()

  // (b) Fokus im Profilbereich → zurück auf den Avatar.
  avatar.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await tick()
  const punkt = host.querySelector('.dk-sb-profil-menu .dk-sb-profil-punkt')
  punkt.focus()
  document.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(document.activeElement, avatar,
    'war der Fokus im Menü, steht er danach auf dem Avatar')
  app.unmount()
})

test('MT-1b2: der Fokus-Rückweg prüft die Herkunft (Quelle)', () => {
  const seite = lies('components/AppSidebar.vue')
  assert.match(seite, /wurzel\.contains\(document\.activeElement\)|wurzel\.contains\(aktiv\)/,
    'die Bedingung fragt, ob der Fokus im Profilbereich steht')
  assert.match(seite, /aktiv === document\.body/,
    'und ob er gar nicht gesetzt ist (body)')
})
