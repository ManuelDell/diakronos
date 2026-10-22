/**
 * DM2 — Reparaturen am Dev-Modus (Node `--test`).
 *
 * 1. Screenshot-Zeitpunkt: der Aufnahmeplan laeuft VOR dem Dialog, und alle
 *    Dev-Elemente sind aus dem Rendern ausgeschlossen (Filter/ignore).
 * 2. Bilder in #/dev-befunde laufen ueber den Dev-Modus-Endpunkt, nicht /files.
 * 3. Dialog-Layout: Knoepfe der Bibliothek statt gequetschter Eigenbauten.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import test from 'node:test'

import {
  DEV_KLASSEN, DEV_SELEKTOREN, devAusblenden, istDevKnoten, screenshotOptionen, screenshotPlan,
  traegtDevKennung,
} from '../src/diakonos/components/devmodus/fotograf.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

function knoten(tag, klassen = [], { role = null, kinder = [], attrs = {}, parent = null } = {}) {
  const el = {
    tagName: tag.toUpperCase(), className: klassen.join(' '), classList: klassen,
    children: kinder, parentElement: parent,
    contains: (anderes) => kinder.includes(anderes),
    getAttribute: (n) => (n === 'role' ? role : (n in attrs ? attrs[n] : null)),
    closest: (sel) => {
      const name = sel.replace(/[[\]]/g, '')
      let e = el
      while (e) {
        if (e.getAttribute && e.getAttribute(name) !== null) return e
        e = e.parentElement
      }
      return null
    },
  }
  for (const k of kinder) k.parentElement = el
  return el
}

// Ein Dev-Element im Sinne von DM3.
const devKnoten = (tag, klassen = [], extra = {}) =>
  knoten(tag, klassen, { ...extra, attrs: { 'data-dk-dev': '' } })

// ── 1. Screenshot-Zeitpunkt und Dev-Ausschluss ─────────────────────────────

test('Aufnahmeplan: nur das Fenster (Element-Ausschnitt per Zuschnitt)', () => {
  const plan = screenshotPlan({ tagName: 'BUTTON' })
  assert.deepEqual(plan.map(s => s.art), ['fenster'])
  assert.equal(plan[0].name, 'fenster.png')
})

test('Aufnahmeplan ohne Element: nur das Fenster', () => {
  assert.deepEqual(screenshotPlan(null).map(s => s.art), ['fenster'])
})

test('Dev-Elemente tragen data-dk-dev und sind im Bild ausgeschlossen', () => {
  assert.deepEqual(DEV_SELEKTOREN, ['[data-dk-dev]'])
  assert.equal(traegtDevKennung(knoten('div', [], { attrs: { 'data-dk-dev': '' } })), true)
  for (const klasse of ['dk-dev-rahmen', 'dk-dev-ecke', 'dk-dev-knopf', 'dk-dev-umriss']) {
    assert.ok(DEV_KLASSEN.includes(klasse), klasse)
    assert.equal(istDevKnoten(devKnoten('div', [klasse])), true, klasse)
  }
  assert.equal(istDevKnoten(knoten('div', ['dk-screen'])), false)
})

test('App-Dialog bleibt im Bild (keine generischen Klassen mehr)', () => {
  // DM3: dk-modal/dk-ui-dialog/role=dialog sind KEINE Dev-Elemente mehr.
  assert.equal(istDevKnoten(knoten('div', ['dk-modal'])), false)
  assert.equal(istDevKnoten(knoten('div', [], { role: 'dialog' })), false)
  // Mit eigener Kennung ist ein Dialog (z. B. BefundDialog) ausgeschlossen.
  assert.equal(istDevKnoten(devKnoten('div', ['dk-dev-dialog'], { role: 'dialog' })), true)
})

test('das gewaehlte Element bleibt trotz Umriss sichtbar', () => {
  const ziel = knoten('button', ['dk-ui-btn'])
  assert.equal(istDevKnoten(ziel, [], ziel), false)
  const zielDev = devKnoten('button', ['dk-dev-knopf'])
  assert.equal(istDevKnoten(zielDev, [], zielDev), false)
})

test('devAusblenden liefert die Dev-Knoten, aber nicht das Zielelement', () => {
  const rahmen = devKnoten('div', ['dk-dev-rahmen'])
  const ziel = devKnoten('button', ['dk-dev-knopf'])
  const alle = [rahmen, ziel]
  const dokument = {
    querySelectorAll: (sel) => (sel === '[data-dk-dev]' ? alle : []),
  }
  const aus = devAusblenden(dokument, ziel)
  assert.deepEqual(aus, [rahmen])
})

test('devAusblenden liefert jeden Dev-Knoten nur einmal', () => {
  const knopf = devKnoten('button', ['dk-dev-knopf', 'dk-dev-etikett'])
  const dokument = { querySelectorAll: (sel) => (sel === '[data-dk-dev]' ? [knopf] : []) }
  assert.deepEqual(devAusblenden(dokument), [knopf])
})

test('screenshotOptionen blenden Dev-Knoten aus (filter)', () => {
  const rahmen = devKnoten('div', ['dk-dev-rahmen'])
  const dokument = { querySelectorAll: (sel) => (sel === '[data-dk-dev]' ? [rahmen] : []) }
  const opt = screenshotOptionen({ breite: 1366, hoehe: 768, dokument })
  assert.equal(opt.width, 1366)
  assert.equal(opt.height, 768)
  assert.equal(opt.filter(rahmen), false)
  assert.equal(opt.filter(knoten('div', ['dk-screen'])), true)
})

test('Rahmen.vue oeffnet den Dialog SOFORT, die Aufnahme laeuft parallel (DM3)', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  const block = rahmen.slice(rahmen.indexOf('async function onClick'),
                             rahmen.indexOf('function dialogSchliessen'))
  const oeffnen = block.indexOf('dialogOffen.value = true')
  assert.ok(oeffnen > 0, 'Dialog wird geoeffnet')
  assert.ok(block.includes('nimmAufImHintergrund('), 'Aufnahme laeuft im Hintergrund')
  assert.ok(!/await\s+nimmAuf\(/.test(block), 'kein await auf die Aufnahme im Klickpfad')
  // Fehler/Haenger der Aufnahme duerfen den Dialog nicht verhindern.
  assert.ok(block.includes('catch') && block.includes('setTimeout'), 'Aufnahme abgesichert (catch + Zeitlimit)')
})

test('BefundDialog nimmt keine Aufnahme mehr in onMounted', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  const mounted = dialog.slice(dialog.indexOf('onMounted('), dialog.indexOf('onUnmounted('))
  assert.ok(!mounted.includes('aufnehmen()'), 'kein aufnehmen() beim Oeffnen')
  assert.ok(dialog.includes('startbilder'), 'Startbilder werden uebernommen')
})

test('screenshot.mjs blendet Dev-Elemente beim Rendern aus', () => {
  const modul = lies('components/devmodus/screenshot.mjs')
  assert.ok(modul.includes('screenshotOptionen'), 'Aufnahmeoptionen aus fotograf.mjs')
  assert.ok(modul.includes('devAusblenden'), 'Dev-Ausschluss benutzt')
  assert.ok(modul.includes('export async function nimmAuf'), 'Sammelaufnahme vorhanden')
})

// ── 2. Bilder in #/dev-befunde ─────────────────────────────────────────────

test('Befund-Bilder laufen ueber den Dev-Modus-Endpunkt, nicht /files', () => {
  const seite = lies('pages/devmodus/Befunde.vue')
  assert.ok(!seite.includes("'/files/'"), 'kein /files-Weg mehr in der Seite')
  assert.ok(seite.includes('bildUrl'), 'Seite nutzt bildUrl aus dem Composable')
  const composable = lies('composables/useDevmodus.js')
  assert.ok(composable.includes('export function bildUrl'))
  assert.ok(composable.includes(".devmodus.api.' + 'bild") ||
            /PRAEFIX \+ 'bild/.test(composable), 'Endpunkt bild im Composable')
  assert.ok(composable.includes('encodeURIComponent'), 'Pfad wird kodiert')
})

test('Befunde-Seite zeigt Titel, Vorschau und Grossansicht', () => {
  const seite = lies('pages/devmodus/Befunde.vue')
  assert.ok(seite.includes('b.titel'), 'Titel aus dem Befund')
  assert.ok(seite.includes('ersteZeile(b.text)'), 'Rueckfall auf die erste Kommentarzeile')
  assert.ok(seite.includes('dk-dm-vorschau'), 'Vorschau im Detail')
  assert.ok(seite.includes('grossesBild'), 'Grossansicht vorhanden')
})

// ── 3. Dialog-Layout ───────────────────────────────────────────────────────

test('BefundDialog nutzt das Design-System (DkDialog/DkButton)', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(dialog.includes("from '../ui/DkDialog.vue'"), 'DkDialog benutzt')
  assert.ok(dialog.includes("from '../ui/DkButton.vue'"), 'DkButton benutzt')
  assert.ok(!dialog.includes("from '../DkModal.vue'"), 'kein DkModal mehr')
  assert.ok(!dialog.includes('dk-dm-knopf'), 'Eigenbau-Knopf entfernt')
})

test('BefundDialog: Knopfzeilen brechen um statt zu quetschen', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(/\.dk-dm-aktionen\s*\{[^}]*flex-wrap:\s*wrap/.test(dialog),
    '.dk-dm-aktionen bricht um')
  assert.ok(dialog.includes('@media (max-width: 600px)'), 'schmale Breite geregelt')
  assert.ok(dialog.includes('min-width: 0'), 'kein Ueberlauf durch min-width')
})

test('DEV-Ecke bricht um (kein Ueberlauf von „Element wählen“)', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  const block = rahmen.slice(rahmen.indexOf('.dk-dev-ecke {'))
  assert.ok(/\.dk-dev-ecke\s*\{[^}]*flex-wrap:\s*wrap/.test(block), 'flex-wrap gesetzt')
  assert.ok(/\.dk-dev-ecke\s*\{[^}]*max-width:\s*calc\(100vw/.test(block), 'max-width gesetzt')
})

test('Dev-Befunde-Seite nutzt DkPageHeader statt undefinierter Klasse', () => {
  const seite = lies('pages/devmodus/Befunde.vue')
  assert.ok(seite.includes('DkPageHeader'), 'DkPageHeader benutzt')
  assert.ok(!seite.includes('dk-seite-kopf'), 'alte ungestylte Klasse entfernt')
})

test('Datei existiert: fotograf.mjs und screenshot.mjs', () => {
  for (const datei of ['components/devmodus/fotograf.mjs', 'components/devmodus/screenshot.mjs']) {
    assert.ok(existsSync(new URL(datei, root)), `vorhanden: ${datei}`)
  }
})
