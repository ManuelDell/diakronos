// UI-R8 — der ⓘ-Knopf (RrInfo.vue) im MOUNT, nicht als Quelltext-Muster.
//
// Review R8-4 verlangt zwei Dinge, die man nur am gerenderten Bauteil sieht:
//   A · Escape schließt das offene Popover UND gibt den Fokus an den ⓘ zurück.
//   B · Escape am ⓘ bei GESCHLOSSENEM Popover wird NICHT verschluckt — sonst
//       ließe sich der umgebende Dialog per Tastatur nicht mehr abbrechen.
// Dazu die Punkte, die man am Markup prüfen kann:
//   C · Der ⓘ ist ein <DkButton> (also ein <button>), aria-expanded wechselt,
//       fehlt die Erklärung, erscheint gar kein Knopf.
//   D · Das Popover trägt den Rollentitel und die „Darf/Darf nicht“-Listen aus
//
// Die Prüfung hängt bewusst NICHT an `.rr-gruppe` oder `.rr-erklaerung`: dieser
// Test liest seine Quelldateien über einen relativen Pfad, und in einem
// Image-Build kann das Bündel unter einer ANDEREN Wurzel liegen (NODE_TESTLISTE
// in `tests/`). Dann misst er die falschen Seiten-Marken und meldet falsch-rot.
// Geprüft wird deshalb das, was immer eindeutig dem Bauteil gehört.
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

// ── jsdom + SFC-Mount (gleiche Technik wie dev-b2-prueftafel-reiter) ───────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'KeyboardEvent', 'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'uir8-'))
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

/** RrInfo mit gegebener Erklärung in einem Host mounten. */
async function mounten(erklaerung, name = 'Kalender-Moderation') {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/RrInfo.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({ p: { name, erklaerung } }),
    template: '<Geprueft v-bind="p" />',
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen }
}

const ERKLAERUNG = {
  titel: 'Kalender-Moderation',
  kurz: 'Prüft, was für die ganze Gemeinde sichtbar wird.',
  darf: ['Termine prüfen'],
  darf_nicht: ['in Gruppen-Kalender schreiben'],
}

// ── A · ⓘ und Popover im Markup ───────────────────────────────────────────

test('UI-R8: ⓘ ist ein echter Knopf mit „Was bewirkt <Titel>?“', async () => {
  const { host, warnungen } = await mounten(ERKLAERUNG)
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  const knopf = host.querySelector('.rr-info-knopf')
  assert.ok(knopf, 'ⓘ-Knopf fehlt')
  assert.equal(knopf.tagName, 'BUTTON', 'ⓘ ist ein Knopf (DkButton), kein <a>')
  // UI-R8b: Name und Titel sind hier gleich — es bleibt beim kurzen Satz.
  assert.equal(knopf.getAttribute('aria-label'), 'Was bewirkt Kalender-Moderation?')
  assert.equal(knopf.getAttribute('aria-expanded'), 'false')
  assert.equal(knopf.getAttribute('aria-haspopup'), 'dialog')
  assert.equal(host.querySelector('.rr-info-panel'), null, 'Popover ist zu Beginn geschlossen')
})

test('UI-R8b: gleicher Name und Titel ⇒ kurzes aria-label, abweichend ⇒ beide', async () => {
  const gleich = await mounten({ ...ERKLAERUNG, titel: 'Ressourcenmoderator' }, 'Ressourcenmoderator')
  assert.equal(gleich.host.querySelector('.rr-info-knopf').getAttribute('aria-label'),
    'Was bewirkt Ressourcenmoderator?')

  const anders = await mounten({ ...ERKLAERUNG, titel: 'Raumverwaltung' }, 'Ressourcenmoderator')
  assert.equal(anders.host.querySelector('.rr-info-knopf').getAttribute('aria-label'),
    'Was bewirkt Ressourcenmoderator (Raumverwaltung)?',
    'rollenname und Titel müssen beide im aria-label stehen')

  const ohneTitel = await mounten({ ...ERKLAERUNG, titel: '' }, 'Ressourcenmoderator')
  assert.equal(ohneTitel.host.querySelector('.rr-info-knopf').getAttribute('aria-label'),
    'Was bewirkt Ressourcenmoderator?', 'ohne Titel bleibt der Rollenname')
})

test('UI-R8: ohne Erklärung erscheint KEIN ⓘ', async () => {
  const { host } = await mounten(null)
  assert.equal(host.querySelector('.rr-info-knopf'), null)
  const leer = await mounten({ titel: 'Tester', kurz: '', darf: [], darf_nicht: [] })
  assert.equal(leer.host.querySelector('.rr-info-knopf'), null, 'leere Erklärung ⇒ kein Knopf')
})

// ── B · Öffnen, Inhalt, Escape, Fokus ─────────────────────────────────────

test('UI-R8: Klick öffnet das Popover mit den Texten AUS DER QUELLE', async () => {
  const { host } = await mounten(ERKLAERUNG)
  const knopf = host.querySelector('.rr-info-knopf')
  knopf.click()
  await tick()
  const panel = host.querySelector('.rr-info-panel')
  assert.ok(panel, 'Popover fehlt nach dem Klick')
  assert.equal(knopf.getAttribute('aria-expanded'), 'true')
  assert.equal(knopf.getAttribute('aria-controls'), panel.id, 'aria-controls zeigt auf das Popover')
  assert.equal(panel.getAttribute('role'), 'dialog')
  assert.equal(panel.textContent.includes('Kalender-Moderation'), true)
  assert.equal(panel.textContent.includes('Termine prüfen'), true, '„Darf“-Punkt fehlt')
  assert.equal(panel.textContent.includes('in Gruppen-Kalender schreiben'), true, '„Darf nicht“-Punkt fehlt')
  assert.equal(document.activeElement, panel, 'Fokus wandert ins Popover')
})

test('UI-R8: Escape schließt das Popover und gibt den Fokus an den ⓘ zurück', async () => {
  const { host } = await mounten(ERKLAERUNG)
  const knopf = host.querySelector('.rr-info-knopf')
  knopf.click()
  await tick()
  const panel = host.querySelector('.rr-info-panel')
  panel.focus()
  // UI-R8b: der Listener hängt an einem ECHTEN VORFAHREN des Felds (dem
  // Mount-Host) — an einem fremden Element hörte er nie ein Ereignis aus dem
  // Popover und „weitergereicht === false“ wäre wirkungslos.
  let weitergereicht = false
  host.addEventListener('keydown', () => { weitergereicht = true })
  assert.equal(host.contains(panel), true, 'das Feld liegt im Host (Vorfahre)')
  panel.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(host.querySelector('.rr-info-panel'), null, 'Popover bleibt offen')
  assert.equal(knopf.getAttribute('aria-expanded'), 'false')
  assert.equal(document.activeElement, knopf, 'Fokus kehrt zum ⓘ zurück')
  assert.equal(weitergereicht, false, 'Escape im offenen Popover wird gestoppt')
})

test('UI-R8: Escape am ⓘ bei GESCHLOSSENEM Popover wird NICHT verschluckt', async () => {
  const { host } = await mounten(ERKLAERUNG)
  const knopf = host.querySelector('.rr-info-knopf')
  // Simulierter umgebender Dialog: er hört bubblend auf Escape.
  let dialogEscape = 0
  const dialog = document.createElement('div')
  dialog.addEventListener('keydown', (e) => { if (e.key === 'Escape') dialogEscape += 1 })
  dialog.appendChild(host)
  document.body.appendChild(dialog)

  knopf.focus()
  knopf.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await tick()
  assert.equal(dialogEscape, 1, 'der umgebende Dialog bekommt Escape weiterhin')

  // Und mit offenem Popover stoppt der ⓘ es sehr wohl.
  knopf.click()
  await tick()
  host.querySelector('.rr-info-panel').dispatchEvent(
    new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
  )
  await tick()
  assert.equal(dialogEscape, 1, 'im offenen Popover wird Escape gestoppt')
  assert.equal(host.querySelector('.rr-info-panel'), null)
  dialog.remove()
})

// ── C · Erkennbarkeit in Ruhe (Review R8-6) ───────────────────────────────

test('UI-R8: der ⓘ ist in Ruhe als Bedienelement erkennbar (Rahmen per Token)', () => {
  const baustein = readFileSync(join(SRC, 'components/ui/RrInfo.vue'), 'utf8')
  // Kreis/Rahmen um das Zeichen statt eines nackten kursiven „i“.
  assert.match(baustein, /\.rr-info-zeichen\s*\{[\s\S]*?border:\s*var\(--rahmen-breite\) solid var\(--muted\)/)
  assert.match(baustein, /\.rr-info-zeichen\s*\{[\s\S]*?display:\s*inline-flex/)
  // Kein toter Code mehr (Review R8-5): kein `border-width: 0` direkt nach
  // gesetzten Rahmen-Tokens, keine erfundene Klasse.
  assert.ok(!/border-width:\s*0/.test(baustein), 'widersprüchliche Rahmen-Angabe')
})
