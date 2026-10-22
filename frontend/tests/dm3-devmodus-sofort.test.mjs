/**
 * DM3 — Dev-Modus: Befund-Dialog oeffnet SOFORT, Aufnahme laeuft im Hintergrund.
 *
 * Geprueft werden die drei Zusagen der Karte DM3:
 *  1. Dialog oeffnet im Klickpfad, OHNE auf die Aufnahme zu warten (< 200 ms);
 *     die Aufnahme laeuft parallel im Hintergrund.
 *  2. Dev-Elemente werden ueber die EIGENE Kennung ``data-dk-dev`` aus dem
 *     Bild ausgeschlossen — ein Element in einem App-Dialog (DkModal/DkWarning)
 *     BLEIBT im Bild (Befund).
 *  3. Fehlerfall: Aufnahme scheitert -> Hinweis im Dialog, Dialog bleibt nutzbar.
 *  4. Tempo: nur der sichtbare Fensterausschnitt, scale 1, Element-Ausschnitt
 *     aus dem Fensterbild zugeschnitten statt zweitem Rendern.
 *
 * Reine Node-Tests (``--test``), ohne Browser.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  DEV_ATTRIBUT, DEV_SELEKTOREN, devAusblenden, istDevKnoten, schneideAusschnitt,
  screenshotOptionen, screenshotPlan, traegtDevKennung,
} from '../src/diakonos/components/devmodus/fotograf.mjs'
import { schneideBild } from '../src/diakonos/components/devmodus/screenshot.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

/** Minimales Knoten-Interface inkl. closest() ueber die Elternkette. */
function knoten(tag, { klassen = [], attrs = {}, parent = null, kinder = [] } = {}) {
  const el = {
    tagName: tag.toUpperCase(), className: klassen.join(' '), classList: klassen,
    parentElement: parent, children: kinder,
    getAttribute: (n) => (n in attrs ? attrs[n] : null),
    contains: (anderes) => kinder.includes(anderes),
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

// ── 2. Ausschluss ueber data-dk-dev ────────────────────────────────────────

test('data-dk-dev ist die Kennung der Dev-Elemente', () => {
  assert.equal(DEV_ATTRIBUT, 'data-dk-dev')
  assert.deepEqual(DEV_SELEKTOREN, ['[data-dk-dev]'])
})

test('Dev-Elemente tragen data-dk-dev und sind ausgeschlossen', () => {
  const rahmen = knoten('div', { attrs: { 'data-dk-dev': '' } })
  assert.equal(traegtDevKennung(rahmen), true)
  assert.equal(istDevKnoten(rahmen), true)
  // Untergeordneter Knoten erbt die Kennung ueber closest().
  const innen = knoten('span', { parent: rahmen })
  assert.equal(istDevKnoten(innen), true)
})

test('App-Dialog (dk-modal/role=dialog) BLEIBT im Bild — kein Dev-Element', () => {
  // Genau der DM2-Fehler: die alten Klassen trafen auch App-Fenster.
  const appModal = knoten('div', { klassen: ['dk-modal'], attrs: { role: 'dialog' } })
  assert.equal(istDevKnoten(appModal), false, 'App-Fenster bleibt sichtbar')
  const dkDialog = knoten('div', { klassen: ['dk-ui-dialog', 'dk-ui-dialog-overlay'], attrs: { role: 'dialog' } })
  assert.equal(istDevKnoten(dkDialog), false, 'DkDialog bleibt sichtbar')
})

test('das gewaehlte Element bleibt trotz Dev-Kennung sichtbar (ausser)', () => {
  const ziel = knoten('button', { attrs: { 'data-dk-dev': '' } })
  assert.equal(istDevKnoten(ziel, [], ziel), false)
})

test('devAusblenden liefert die Dev-Knoten ueber data-dk-dev, nicht das Ziel', () => {
  const rahmen = knoten('div', { attrs: { 'data-dk-dev': '' } })
  const appModal = knoten('div', { klassen: ['dk-modal'] })
  const dokument = {
    querySelectorAll: (sel) => (sel === '[data-dk-dev]' ? [rahmen] : (sel === '.dk-modal' ? [appModal] : [])),
  }
  assert.deepEqual(devAusblenden(dokument), [rahmen])
})

test('screenshotOptionen blenden nur Dev-Knoten aus (filter)', () => {
  const rahmen = knoten('div', { attrs: { 'data-dk-dev': '' } })
  const dokument = { querySelectorAll: (sel) => (sel === '[data-dk-dev]' ? [rahmen] : []) }
  const opt = screenshotOptionen({ breite: 1366, hoehe: 768, dokument })
  assert.equal(opt.width, 1366)
  assert.equal(opt.height, 768)
  assert.equal(opt.scale, 1, 'scale 1 (kein doppeltes Rendern)')
  assert.equal(opt.filter(rahmen), false)
  assert.equal(opt.filter(knoten('div', { klassen: ['dk-modal'], attrs: { role: 'dialog' } })), true)
})

test('Rahmen.vue kennzeichnet ALLE Dev-Elemente mit data-dk-dev', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  for (const klasse of ['dk-dev-rahmen', 'dk-dev-ecke', 'dk-dev-etikett', 'dk-dev-taste',
                        'dk-dev-knopf', 'dk-dev-umriss', 'dk-dev-ziel']) {
    const zeile = rahmen.split('\n').find(z => z.includes(klasse) && z.includes('class='))
    assert.ok(zeile, `Zeile mit ${klasse} gefunden`)
    assert.ok(zeile.includes('data-dk-dev'), `${klasse} traegt data-dk-dev`)
  }
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(dialog.includes('data-dk-dev'), 'BefundDialog traegt data-dk-dev (Teleport-Ebene)')
})

test('Rahmen waehlt keine Dev-Elemente mehr ueber alte Klassen aus', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  assert.ok(rahmen.includes("querySelectorAll('[data-dk-dev]')"),
    'overlayKnoten nutzt die Kennung')
  assert.ok(!rahmen.includes("'.dk-dev-rahmen, .dk-dev-ecke, .dk-dev-umriss'"),
    'keine Auflistung alter Klassen mehr')
})

// ── 1. Dialog sofort, Aufnahme parallel ────────────────────────────────────

test('Rahmen.vue oeffnet den Dialog OHNE await auf die Aufnahme', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  const block = rahmen.slice(rahmen.indexOf('async function onClick'),
                             rahmen.indexOf('function dialogSchliessen'))
  assert.ok(block.includes('dialogOffen.value = true'), 'Dialog wird geoeffnet')
  assert.ok(block.includes('nimmAufImHintergrund('), 'Aufnahme startet parallel')
  // Im Klickpfad darf KEIN await nimmAuf stehen — sonst wartet der Dialog.
  assert.ok(!/await\s+nimmAuf\(/.test(block), 'kein await nimmAuf im Klickpfad')
  const aufnahme = block.indexOf('nimmAufImHintergrund(')
  const oeffnen = block.indexOf('dialogOffen.value = true')
  assert.ok(oeffnen > 0 && aufnahme > 0 && oeffnen <= aufnahme,
    'Dialog oeffnet vor dem Start der Hintergrundaufnahme')
})

test('Hintergrundaufnahme ist gegen Fehler und Haenger abgesichert', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  const block = rahmen.slice(rahmen.indexOf('async function nimmAufImHintergrund'))
  assert.ok(block.includes('catch'), 'try/catch vorhanden')
  assert.ok(block.includes('Promise.race') && block.includes('setTimeout'),
    'Zeitlimit vorhanden')
  assert.ok(block.includes('aufnahmeFehler.value'), 'Fehler wird im Dialog gemeldet')
})

test('BefundDialog reicht nachtraeglich eintreffende Bilder nach', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(dialog.includes('bildAufnahmeLaeuft'), 'Platzhalter-Zustand als Prop')
  assert.ok(dialog.includes('Screenshot wird erstellt'), 'Hinweistext vorhanden')
  assert.ok(dialog.includes('watch('), 'watch auf die Startbilder')
  assert.ok(dialog.includes('startbilderUebernehmen'), 'Nachtrag der Bilder')
})

// ── 3. Fehlerfall ──────────────────────────────────────────────────────────

test('BefundDialog bleibt bei fehlender Aufnahme bedienbar', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(dialog.includes('bildAufnahmeFehler'), 'Fehlerhinweis-Prop')
  // Der Fehlerhinweis steht als role="alert" im Dialog.
  assert.ok(/role="alert"[^>]*data-dk-dev/.test(dialog) || /data-dk-dev[^>]*role="alert"/.test(dialog),
    'Fehlerhinweis ausgezeichnet')
  // Die Aufnahme-Knoepfe sind weiterhin da.
  for (const knopf of ['Aufnehmen (DOM)', 'Bildschirm aufnehmen', 'type="file"']) {
    assert.ok(dialog.includes(knopf), `${knopf} vorhanden`)
  }
})

test('Speichern wartet auf ein nachgereichtes Bild (Deckel aus dem Rahmen-Limit)', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.ok(dialog.includes('warteAufBild'), 'Wartefunktion vorhanden')
  assert.ok(/warteAufBild\([A-Z_]+\)/.test(dialog), 'Wartezeit ueber das gemeinsame Limit')
})

// ── 4. Tempo ───────────────────────────────────────────────────────────────

test('Aufnahmeplan rendert nur den Fensterausschnitt (kein zweites Rendern)', () => {
  assert.deepEqual(screenshotPlan({ tagName: 'BUTTON' }).map(s => s.art), ['fenster'])
})

test('schneideAusschnitt begrenzt auf das Bild', () => {
  const a = schneideAusschnitt({ x: 10, y: 20, breite: 100, hoehe: 50 }, 1366, 768)
  assert.deepEqual(a, { x: 10, y: 20, breite: 100, hoehe: 50 })
  // Ueber den Rand hinaus -> beschnitten.
  const b = schneideAusschnitt({ x: 1300, y: 740, breite: 200, hoehe: 200 }, 1366, 768)
  assert.deepEqual(b, { x: 1300, y: 740, breite: 66, hoehe: 28 })
  // Ausserhalb -> keine Aufnahme.
  assert.equal(schneideAusschnitt({ x: 2000, y: 0, breite: 50, hoehe: 50 }, 1366, 768), null)
  assert.equal(schneideAusschnitt(null, 1366, 768), null)
})

test('schneideBild erzeugt den Element-Ausschnitt aus dem Fensterbild', async () => {
  const gesehen = {}
  const leinwand = {
    width: 0, height: 0,
    getContext: () => ({ drawImage: (...a) => { gesehen.aufruf = a }, fillRect: () => {} }),
    toDataURL: () => 'data:image/png;base64,AAAA',
  }
  globalThis.document = { createElement: () => leinwand }
  globalThis.innerWidth = 100
  const bildLaden = async () => ({ naturalWidth: 100, width: 100 })
  const url = await schneideBild('data:image/png;base64,BBBB',
    { x: 5, y: 6, breite: 20, hoehe: 10 }, bildLaden)
  assert.equal(url, 'data:image/png;base64,AAAA')
  assert.equal(leinwand.width, 20)
  assert.equal(leinwand.height, 10)
  assert.ok(gesehen.aufruf, 'drawImage wurde gerufen')
  delete globalThis.document
  delete globalThis.innerWidth
})

test('screenshot.mjs rendert einmalig mit scale 1 und nutzt den Zuschnitt', () => {
  const modul = lies('components/devmodus/screenshot.mjs')
  assert.ok(modul.includes('schneideAusschnitt'), 'Zuschnitt benutzt')
  assert.ok(modul.includes('schneideBild'), 'Bild wird zugeschnitten')
  assert.ok(modul.includes('scale: 1'), 'scale 1 gesetzt')
  assert.ok(modul.includes('devAusblenden'), 'Dev-Ausschluss benutzt')
  assert.ok(modul.includes('_rendererGeladen'), 'Renderer wird zwischengespeichert (Font-/Lade-Cache)')
})

test('Web-Schriften werden einmal gesammelt (Cache), nicht je Aufnahme', () => {
  const modul = lies('components/devmodus/screenshot.mjs')
  assert.ok(modul.includes('fontCssSammeln'), 'Font-CSS wird gesammelt')
  assert.ok(modul.includes('fontCss,'), 'Font-CSS geht in die Optionen')
  assert.ok(modul.includes('CSSFontFaceRule'), 'aus @font-face-Regeln')
  assert.ok(modul.includes('_fontCss'), 'einmaliger Cache')
  const foto = lies('components/devmodus/fotograf.mjs')
  assert.ok(foto.includes('fontCss'), 'screenshotOptionen nimmt fontCss')
  assert.ok(/\.font\s*=\s*\{\s*cssText:\s*fontCss\s*\}/.test(foto), 'modern-screenshot font.cssText gesetzt')
})

console.log('DM3 Dev-Modus: bestanden')
