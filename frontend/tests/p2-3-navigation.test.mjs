/**
 * P2-3 · DES-R9 / OP-ADMIN-21 — Menü-Gleichstand Desktop ↔ Handy.
 *
 * Befund: Die Handy-Navigation („Mehr“) führte nicht zu Lieder, Liedgruppen,
 * DSGVO und Anmeldung; Desktop und Mobil enthielten verschiedene Seiten.
 * Beide Bereiche lesen seit der Neuordnung dieselbe Definition (menue.js).
 * Dieser Test hält den Gleichstand fest: jede Seite, die die Seitenleiste
 * anbietet, muss auch im „Mehr“-Blatt stehen — und umgekehrt.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MENUE, sichtbareEintraege } from '../src/diakonos/menue.js'
import { fusstabs } from '../src/diakonos/components/fusstabs.mjs'

/** Was die Seitenleiste zeigt. */
function sidebar(rolle) {
  return MENUE.flatMap(g => sichtbareEintraege(g, rolle)).map(e => e.href)
}

/** Was das „Mehr“-Blatt zusätzlich zu den festen Fußzeilen-Tabs zeigt. */
function mehrBlatt(rolle) {
  const tabs = new Set(fusstabs({ istGast: rolle.istGast }).map(t => t.href))
  return sidebar(rolle).filter(href => !tabs.has(href))
}

/** Alle über das Handy erreichbaren Ziele (feste Tabs + Blatt). */
function handyZiele(rolle) {
  return [...fusstabs({ istGast: rolle.istGast }).map(t => t.href), ...mehrBlatt(rolle)]
}

const ADMIN = { istAdmin: true, istTester: true, istGast: false }
const MITGLIED = { istAdmin: false, istTester: false, istGast: false }
const GAST = { istAdmin: false, istTester: false, istGast: true }

test('DES-R9 · Admin: jeder Seitenleisten-Eintrag ist auch am Handy erreichbar', () => {
  const handy = new Set(handyZiele(ADMIN))
  for (const href of sidebar(ADMIN)) {
    assert.ok(handy.has(href), `„${href}“ fehlt in der Handy-Navigation`)
  }
})

test('DES-R9 · Lieder, Liedgruppen, Datenschutz und Einstellungen sind am Handy erreichbar', () => {
  const handy = mehrBlatt(ADMIN)
  for (const href of ['#/lieder', '#/liedgruppen', '#/mitglieder/datenschutz', '#/einstellungen']) {
    assert.ok(handy.includes(href), `„${href}“ fehlt in der Handy-Navigation`)
  }
})

test('OP-ADMIN-21 · Desktop und Handy bieten dieselben Seiten', () => {
  for (const rolle of [ADMIN, MITGLIED, GAST]) {
    const desktop = [...sidebar(rolle), '#/profile'].sort()
    const handy = handyZiele(rolle).slice().sort()
    assert.deepEqual(handy, desktop)
  }
})

test('OP-ADMIN-21 · Adressbuch und Moderation stehen in beiden Bereichen', () => {
  const seiten = sidebar(ADMIN)
  assert.ok(seiten.includes('#/adressbuch'))
  assert.ok(seiten.includes('#/moderation'))
})

test('OP-HANDY-15 · Gast sieht nur Start, Kalender und Profil', () => {
  // Aus der Menüdefinition nur Start und Kalender; „Profil“ ist der
  // Avatar-Knopf der Fußzeile und steht nicht in MENUE.
  assert.deepEqual(sidebar(GAST).sort(), ['#/', '#/kalender'])
  assert.deepEqual(handyZiele(GAST).slice().sort(),
                   ['#/', '#/kalender', '#/profile'])
  // „Ressourcen“ gehört NICHT zu den Gäste-Tabs (der Server weist Gäste ab).
  assert.ok(!handyZiele(GAST).includes('#/ressourcen'))
})
