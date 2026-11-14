// UI-R8b — die ROLLENZEILE im Mount: das Erklärfeld ist eine eigene volle
// Zeile UNTER der Rollenzeile, nicht ein Feld in einem Inline-Element.
//
// Review R8-2 (Desktop) und Beleg 06 (Handy) hatten zwei Folgen, die man nur
// am gerenderten Baum sieht:
//   * `.zug-rolle`/`.rr-rolle` wuchsen (`flex: 1 1 auto`) — der ⓘ stand am
//     rechten Kartenrand, ~1400 px vom Rollennamen entfernt.
//   * Das Feld lag IN einem inline-flex-Behälter (der alten RrInfo-Wurzel);
//     beim Aufklappen schrumpfte die Zeile, am Handy verschwand die Checkbox.
// Darum prüft dieser Test den Baum, den RrInfo zusammen mit der Rollenzeile
// erzeugt: ⓘ und Feld sind GESCHWISTER der Rollenbeschriftung, und die
// Rollenzeile trägt `flex-wrap: wrap` — die Bedingung dafür, dass das Feld mit
// `flex-basis: 100%` in die nächste Zeile rutschen kann.
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

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'KeyboardEvent', 'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'uir8b-'))
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

const ERKLAERUNG = {
  titel: 'Mitgliederverwaltung',
  kurz: 'Verwaltet Konten und Rollen der Mitglieder.',
  darf: ['Konten anlegen'],
  darf_nicht: ['Rechte vergeben, die sie selbst nicht hat'],
}

/**
 * Genau der Aufbau der echten Rollenzeile (RollenRechte.vue/ZugangKarte.vue):
 * Beschriftung mit Rollenname + RrInfo als zweites Kind, ohne eigenen
 * Behälter dazwischen. Genau daran hing der Fehler.
 */
async function zeileMounten() {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/RrInfo.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({ erklaerung: ERKLAERUNG, name: 'Mitgliederadministrator' }),
    template: `<div class="zeile">
      <label class="rolle"><input type="checkbox" /><span>{{ name }}</span></label>
      <Geprueft :name="name" :erklaerung="erklaerung" />
    </div>`,
  })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.mount(host)
  await tick()
  return { host, app, warnungen }
}

test('UI-R8b: ⓘ und Erklärfeld sind Geschwister der Rollenbeschriftung', async () => {
  const { host, warnungen } = await zeileMounten()
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem (Fragment ohne Wurzel)')

  const zeile = host.querySelector('.zeile')
  const kinder = [...zeile.children].map((k) => k.tagName + (k.className ? `.${k.className}` : ''))
  assert.equal(kinder.length, 2, `Zeile hat ${kinder.length} Kinder statt 2: ${kinder}`)

  const knopf = zeile.querySelector(':scope > .rr-info-knopf')
  assert.ok(knopf, 'der ⓘ liegt nicht direkt in der Rollenzeile')

  // Aufklappen: das Feld ist KEIN Nachfahre des Labels und kein Kind des ⓘ.
  knopf.click()
  await tick()
  const feld = zeile.querySelector(':scope > .rr-info-panel')
  assert.ok(feld, 'das Erklärfeld liegt nicht direkt in der Rollenzeile (eigene volle Zeile)')
  assert.equal(zeile.querySelector('label').contains(feld), false,
    'Feld steckt im Label — die Checkbox würde am Handy weggedrückt')
  assert.equal(knopf.contains(feld), false, 'Feld steckt im ⓘ-Knopf')
  assert.equal(zeile.children.length, 3, 'Feld ist nicht das dritte Element der Zeile')
})

/**
 * Die `<style>`-Blöcke der SFCs in ein Dokument legen, damit `getComputedStyle`
 * die ECHTEN Regeln auflöst. `scoped` bleibt wirkungslos (jsdom kennt die
 * data-v-Attribute des Builds nicht) — gemessen werden die Eigenschaften, die
 * hier eindeutig vergeben sind. Genau das ist der Punkt: nicht der Quelltext
 * soll passen, sondern das, was der Browser daraus macht.
 */
function stileEinbinden() {
  const dateien = [
    'pages/einstellungen/RollenRechte.vue',
    'components/ZugangKarte.vue',
    'components/ui/RrInfo.vue',
  ]
  for (const datei of dateien) {
    const inhalt = readFileSync(join(SRC, datei), 'utf8')
    for (const treffer of inhalt.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) {
      const stil = document.createElement('style')
      stil.textContent = treffer[1]
      document.head.appendChild(stil)
    }
  }
}

/**
 * Eine Rollenzeile wie in RollenRechte.vue/ZugangKarte.vue rendern —
 * Beschriftung + RrInfo als direkte Geschwister, in der echten Zeilenklasse.
 * `vollZeile` schaltet das Erklärfeld auf, damit es messbar wird.
 */
async function rollenzeileMounten(zeileKlasse, rolleKlasse) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/RrInfo.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    components: { Geprueft: bauteil },
    setup: () => ({ erklaerung: ERKLAERUNG, name: 'Mitgliederadministrator' }),
    template: `<ul class="liste"><li class="${zeileKlasse}">
      <label class="${rolleKlasse}"><input type="checkbox" /><span>{{ name }}</span></label>
      <Geprueft :name="name" :erklaerung="erklaerung" />
    </li></ul>`,
  })
  app.mount(host)
  await tick()
  return { host, app }
}

test('UI-R8b: gemessen — Zeile bricht um, Label wächst nicht, Feld ist eigene volle Zeile', async () => {
  stileEinbinden()
  for (const [zeileKlasse, rolleKlasse] of [
    ['.rr-rollen-zeile', '.rr-rolle'],
    ['.zug-rollen-zeile', '.zug-rolle'],
  ]) {
    const { host, app } = await rollenzeileMounten(zeileKlasse.slice(1), rolleKlasse.slice(1))
    const zeile = host.querySelector(zeileKlasse)
    assert.ok(zeile, `${zeileKlasse}: Zeile fehlt`)

    // Die Zeile ist ein umbrechender Flex-Behälter — sonst kann das Feld nicht
    // in die nächste Zeile rutschen.
    const zeilenStil = dom.window.getComputedStyle(zeile)
    assert.equal(zeilenStil.display, 'flex', `${zeileKlasse}: kein Flex-Behälter`)
    assert.equal(zeilenStil.flexWrap, 'wrap', `${zeileKlasse}: ohne wrap bleibt das Feld in der Zeile`)

    // Die Beschriftung darf NICHT wachsen: `flex: 0 1 auto`, also grow 0.
    const rolle = zeile.querySelector(rolleKlasse)
    const rollenStil = dom.window.getComputedStyle(rolle)
    assert.equal(rollenStil.flexGrow, '0',
      `${zeileKlasse}: die Beschriftung wächst — der ⓘ stünde am rechten Rand der Karte`)
    assert.equal(rollenStil.flexShrink, '1', `${zeileKlasse}: Beschriftung darf schrumpfen`)

    // Aufklappen und das Feld messen: eigene volle Zeile, kein Schweben.
    zeile.querySelector('.rr-info-knopf').click()
    await tick()
    const feld = zeile.querySelector(':scope > .rr-info-panel')
    assert.ok(feld, `${zeileKlasse}: Feld ist kein Kind der Zeile`)
    const feldStil = dom.window.getComputedStyle(feld)
    assert.equal(feldStil.position, 'static',
      `${zeileKlasse}: Feld schwebt (position:${feldStil.position}) und würde abgeschnitten`)
    assert.equal(feldStil.flexBasis, '100%', `${zeileKlasse}: Feld nimmt keine volle Zeile`)
    assert.equal(feldStil.width, '100%', `${zeileKlasse}: Feld ist nicht über die volle Breite`)
    assert.ok(!feldStil.zIndex || feldStil.zIndex === 'auto', `${zeileKlasse}: Feld liegt über der Karte`)

    // Der ⓘ darf nicht wachsen (sonst stünde er nicht direkt hinter dem Namen).
    const knopf = zeile.querySelector(':scope > .rr-info-knopf')
    assert.equal(dom.window.getComputedStyle(knopf).flexGrow, '0',
      `${zeileKlasse}: der ⓘ wächst mit — er steht dann nicht hinter dem Namen`)

    // Die Checkbox darf nicht schrumpfen (Beleg 06: sie verschwand am Handy).
    assert.equal(dom.window.getComputedStyle(rolle.querySelector('input')).flexShrink, '0',
      `${zeileKlasse}: die Checkbox darf schrumpfen (verschwindet am Handy)`)

    app.unmount()
    zeile.closest('ul').remove()
  }
})
