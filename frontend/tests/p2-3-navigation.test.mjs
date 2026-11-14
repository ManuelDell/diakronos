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
import { MENUE, FUSS_EINTRAEGE, sichtbareEintraege, verwaltungZutreffend } from '../src/diakonos/menue.js'
import { fusstabs } from '../src/diakonos/components/fusstabs.mjs'

/** Was die Seitenleiste zeigt — Gruppenliste UND Fußbereich (UX3a: seit
 *  Entwurf A1 steht „Einstellungen“ unten im Fuß der Seitenleiste). */
function sidebar(rolle) {
  const gruppen = MENUE.flatMap(g => sichtbareEintraege(g, rolle)).map(e => e.href)
  // UI-R10: Der Fuß („Einstellungen“) trägt eine Verwaltungsstufe
  // (`verwaltung`), keine feste Rolle mehr — dieselbe Regel wie die Leiste.
  const fuss = FUSS_EINTRAEGE
    .filter(e => !e.verwaltung || verwaltungZutreffend(e.verwaltung, rolle))
    .map(e => e.href)
  return [...gruppen, ...fuss]
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

test('DES-R9 · Lieder, Datenschutz und Einstellungen sind am Handy erreichbar', () => {
  const handy = [...mehrBlatt(ADMIN), ...FUSS_EINTRAEGE.map(e => e.href), '#/profile']
  // UX3a: Liedgruppen sind ein REITER unter „Lieder“ (kein eigener Eintrag);
  // Datenschutz ist ein Reiter unter „Personen“.
  for (const href of ['#/lieder', '#/personen', '#/einstellungen']) {
    assert.ok(handy.includes(href), `„${href}“ fehlt in der Handy-Navigation`)
  }
  assert.ok(!handy.includes('#/lieder/gruppen'), 'kein eigener Menüpunkt Liedgruppen')
})

test('OP-ADMIN-21 · Desktop und Handy bieten dieselben Seiten', () => {
  for (const rolle of [ADMIN, MITGLIED, GAST]) {
    // UX3a (Entwurf A8): Das Profil ist am Handy kein eigener Reiter mehr —
    // es steht im Profilmenü der Seitenleiste wie am Desktop.
    const desktop = [...sidebar(rolle)].sort()
    const handy = handyZiele(rolle).slice().sort()
    assert.deepEqual(handy, desktop)
  }
})

test('OP-ADMIN-21 · Adressbuch und „Zu prüfen“ sind über den Bereich erreichbar', () => {
  // UX3a: Beides sind Reiter geworden (Adressbuch unter Personen, „Zu prüfen“
  // unter Kalender) — erreichbar über den jeweiligen Bereich, nicht als
  // eigener Menüpunkt.
  const seiten = sidebar(ADMIN)
  assert.ok(seiten.includes('#/personen'))
  assert.ok(seiten.includes('#/kalender'))
  assert.ok(!seiten.includes('#/adressbuch'), 'kein eigener Menüpunkt mehr')
  assert.ok(!seiten.includes('#/moderation'), 'kein eigener Menüpunkt mehr')
})

test('OP-HANDY-15 · Gast sieht nur Start, Kalender und Profil', () => {
  // Aus der Menüdefinition nur Start und Kalender; „Profil“ ist der
  // Avatar-Knopf der Fußzeile und steht nicht in MENUE.
  // UX3a2: „Dienste“ ist für Gäste wieder gesperrt (Stand vor UX3a) — weder
  // Menüpunkt noch Tab der unteren Leiste.
  assert.deepEqual(sidebar(GAST).sort(), ['#/', '#/kalender'])
  assert.ok(!handyZiele(GAST).includes('#/dienste'), 'kein „Dienste“-Tab für Gäste')
  // „Ressourcen“ gehört NICHT zu den Gäste-Tabs (der Server weist Gäste ab).
  assert.ok(!handyZiele(GAST).includes('#/ressourcen'))
})
