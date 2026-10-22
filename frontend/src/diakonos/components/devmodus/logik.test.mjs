import assert from 'node:assert/strict'
import test from 'node:test'

import {
  kuerzelPasst, istEingabefeld, selektorFuer, komponentenkette, elementKontext,
  redigiereHtml, formularwerte, wechsleElement, sichtbarerText, elementEtikett,
} from './logik.mjs'

// ── Tastenkuerzel ──────────────────────────────────────────────────────────

test('kuerzelPasst: Strg+Shift+F (auch mit ctrlKey auf macOS)', () => {
  assert.equal(kuerzelPasst({ key: 'F', ctrlKey: true, shiftKey: true }), true)
  assert.equal(kuerzelPasst({ key: 'f', ctrlKey: true, shiftKey: true }), true)
  assert.equal(kuerzelPasst({ key: 'F', ctrlKey: true, shiftKey: true, altKey: true }), false)
  assert.equal(kuerzelPasst({ key: 'F', ctrlKey: true }), false)
  assert.equal(kuerzelPasst({ key: 'F', shiftKey: true }), false)
  assert.equal(kuerzelPasst({ key: 'D', ctrlKey: true, shiftKey: true }), false)
  assert.equal(kuerzelPasst(null), false)
})

test('istEingabefeld erkennt Felder', () => {
  assert.equal(istEingabefeld({ tagName: 'INPUT' }), true)
  assert.equal(istEingabefeld({ tagName: 'textarea' }), true)
  assert.equal(istEingabefeld({ tagName: 'DIV' }), false)
  assert.equal(istEingabefeld({ tagName: 'DIV', isContentEditable: true }), true)
})

// ── Minimale Knoten-Attrappen (nur das Interface, das logik.mjs liest) ──────

function knoten(tag, { id = '', klassen = [], attribute = {}, kinder = [], parent = null } = {}) {
  const el = {
    nodeType: 1, tagName: tag.toUpperCase(), id, className: klassen.join(' '),
    attributes: Object.entries(attribute).map(([name, value]) => ({ name, value })),
    children: kinder, parentNode: parent, parentElement: parent,
    childNodes: kinder, classList: klassen,
    getAttribute: (n) => (n in attribute ? attribute[n] : null),
    getBoundingClientRect: () => ({ left: 1, top: 2, width: 30, height: 40, x: 1, y: 2 }),
    querySelectorAll: () => [],
    outerHTML: `<${tag.toLowerCase()}>`,
    innerText: '',
    get firstElementChild() { return kinder[0] || null },
  }
  for (const k of kinder) { k.parentNode = el; k.parentElement = el }
  return el
}

test('selektorFuer nutzt eine eindeutige id', () => {
  const el = knoten('button', { id: 'neu' })
  // kein Dokument: id wird ohne Eindeutigkeitspruefung genommen
  assert.equal(selektorFuer(el), '#neu')
})

test('selektorFuer nutzt stabile data-Attribute', () => {
  const el = knoten('button', { attribute: { 'data-testid': 'speichern' } })
  assert.equal(selektorFuer(el), '[data-testid="speichern"]')
})

test('selektorFuer baut einen Pfad mit nth-of-type', () => {
  const eins = knoten('span')
  const zwei = knoten('span')
  const parent = knoten('div', { kinder: [eins, zwei] })
  assert.match(selektorFuer(zwei), /span:nth-of-type\(2\)/)
})

test('komponentenkette: ohne Vue leer, mit Vue-Kette aufsteigend', () => {
  const unten = knoten('button')
  const mitte = knoten('div')
  const oben = knoten('section')
  unten.__vueParentComponent = { type: { name: 'DkButton' } }
  mitte.__vueParentComponent = { type: { name: 'DkTable' } }
  oben.__vueParentComponent = { type: { name: 'Lieder', __file: 'Lieder.vue' } }
  unten.parentElement = mitte
  mitte.parentElement = oben
  assert.deepEqual(komponentenkette(unten), ['Lieder', 'DkTable', 'DkButton'])
})

test('komponentenkette: nutzt die Dev-Modus-Anmerkung __dkName', () => {
  const innen = knoten('button')
  const mitte = knoten('div')
  const aussen = knoten('section')
  innen.__dkName = 'DkButton'
  mitte.__dkName = 'DkTable'
  aussen.__dkName = 'Lieder'
  innen.parentElement = mitte
  mitte.parentElement = aussen
  assert.deepEqual(komponentenkette(innen), ['Lieder', 'DkTable', 'DkButton'])
})

test('sichtbarerText kuerzt', () => {
  const el = { innerText: '  Hallo   Welt  ' }
  assert.equal(sichtbarerText(el, 5), 'Hallo…')
  assert.equal(sichtbarerText(el), 'Hallo Welt')
  assert.equal(sichtbarerText(null), '')
})

// ── Redaktion ──────────────────────────────────────────────────────────────

test('redigiereHtml entfernt Passwortwerte', () => {
  const html = '<input type="password" name="pw" value="geheim123">'
  const aus = redigiereHtml(html)
  assert.ok(!aus.includes('geheim123'))
  assert.ok(aus.includes('[entfernt]'))
})

test('redigiereHtml entfernt Werte bei value vor type', () => {
  const html = '<input value="geheim" type="hidden">'
  assert.ok(!redigiereHtml(html).includes('geheim'))
})

test('formularwerte: Passwort/hidden/file immer [entfernt], Auswahl sichtbar', () => {
  const felder = [
    { name: 'pw', type: 'password', value: 'geheim' },
    { name: 'ticket', type: 'hidden', value: 'abc' },
    { name: 'datei', type: 'file', value: 'x' },
    { name: 'ort', type: 'text', value: 'Kirche' },
    { name: 'ok', type: 'checkbox', checked: true, value: 'on' },
  ]
  const el = { querySelectorAll: () => felder }
  const aus = formularwerte(el)
  assert.equal(aus.pw, '[entfernt]')
  assert.equal(aus.ticket, '[entfernt]')
  assert.equal(aus.datei, '[entfernt]')
  assert.equal(aus.ort, 'Kirche')
  assert.equal(aus.ok, true)
})

test('elementKontext liefert Selektor, Tag und redigiertes outerHTML', () => {
  const el = knoten('button', { id: 'save', attribute: { 'data-testid': 'save' } })
  el.outerHTML = '<input type="password" value="geheim">'
  const k = elementKontext(el)
  assert.equal(k.tag, 'button')
  assert.ok(k.selektor.includes('save'))
  assert.ok(!String(k.outer_html).includes('geheim'))
})

// ── Navigation ─────────────────────────────────────────────────────────────

test('wechsleElement: Eltern und Kind', () => {
  const kind = knoten('span')
  const eltern = knoten('div', { kinder: [kind] })
  const oben = knoten('section', { kinder: [eltern] })
  assert.equal(wechsleElement(kind, 'eltern'), eltern)
  assert.equal(wechsleElement(eltern, 'kind'), kind)
  assert.equal(wechsleElement(kind, 'kind'), kind)  // kein Kind -> bleibt
  assert.equal(wechsleElement(eltern, 'eltern'), oben)
})

test('elementEtikett nennt Komponente und Tag', () => {
  const el = knoten('button', { id: 'save' })
  assert.ok(elementEtikett(el).includes('button#save'))
})
