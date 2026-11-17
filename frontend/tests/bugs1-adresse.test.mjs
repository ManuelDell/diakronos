/**
 * BUG-S1 — Dienste → Stammdaten luden nicht (Skelett blieb stehen).
 *
 * Befund (Manuel, 12.11.): `#/dienste/vorlagen/-/stammdaten/kindergottesdienst`
 * zeigte dauerhaft das Lade-Skelett. Ursache waren ZWEI Reihenfolgen derselben
 * Adresse:
 *
 *   Router (vorher):      `vorlagen/([^/]+)/stammdaten/(.+)`, param `plantyp`
 *                         -> las die Marke „-“ als Plantyp
 *   Weiterleitung (vorher): `vorlagen/${plantyp}/stammdaten/-`
 *
 * Beide Richtungen sind hier festgenagelt: Die eine gültige Form ist
 * `vorlagen/-/stammdaten/‹plantyp›` (so baut es `stammdatenRoute`), alte Links
 * der anderen Reihenfolge bleiben gültig und landen auf der Stammdaten-Seite.
 *
 * Läuft den ECHTEN Router in einer vm aus (Muster: tests/p1-11-router-ladefehler).
 */
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { stammdatenRoute } from '../src/diakonos/components/planrahmen/einrichten-flow.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

function routerAusfuehren({ hash = '#/' } = {}) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
    .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    .replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {currentPageName, getRouteParams, weiterleitungsZiel};'
  let hashchange
  const window = {
    location: { hash, replace(h) { this.hash = h } },
    __DIakonosBOOT: { is_admin: true },
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, h) { window.location.hash = h } }
  const context = {
    window, console, setzeFenstertitel() {},
    verwaltungZutreffend: () => true,
    fehlertext: () => 'Fehler',
    ref: (value) => ({ value }),
    shallowRef: (value) => ({ value }),
    computed: (fn) => ({ get value() { return fn() } }),
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  const gehe = (ziel) => { window.location.hash = ziel; hashchange() }
  return { context, window, gehe }
}

// ── A: Die Adresse, die der Baum BAUET, öffnet die Stammdaten-Seite ────────
{
  const adresse = stammdatenRoute('kindergottesdienst')
  assert.equal(adresse, '#/dienste/vorlagen/-/stammdaten/kindergottesdienst',
    'stammdatenRoute baut die eine gültige Reihenfolge (Plantyp HINTER dem Platzhalter)')

  const h = routerAusfuehren({ hash: adresse })
  assert.equal(h.context.router.currentPageName.value, 'PlanrahmenStammdaten',
    `${adresse} öffnet die Stammdaten-Seite (Befund Manuel: Skelett blieb stehen)`)
  // Der Plantyp darf NICHT als Routen-Parameter `plantyp` aus der Marke kommen —
  // genau das führte zur Abfrage `stammdaten_holen('-')` (Befund: main lieferte
  // hier `{ plantyp: '-' }`).
  assert.notEqual(h.context.router.getRouteParams().plantyp, '-',
    'die Marke „-“ darf nicht als Plantyp gelesen werden')
}

// ── B: Die alte Reihenfolge bleibt gültig (Umleitung + Ziel) ───────────────
{
  const h = routerAusfuehren({ hash: '#/' })
  h.gehe('#/planrahmen/stammdaten/chorplan')
  const ziel = '#/dienste/vorlagen/-/stammdaten/chorplan'
  assert.equal(h.window.location.hash, ziel,
    'alte Adresse leitet auf die gültige Reihenfolge um (main baute vorher die umgekehrte)')
  // Weiterleitung ändert die Adresse per `window.location.replace` — der
  // Browser meldet danach selbst den `hashchange` für das Ziel.
  h.gehe(ziel)
  assert.equal(h.context.router.currentPageName.value, 'PlanrahmenStammdaten',
    'und das Ziel öffnet die Stammdaten-Seite')

  // Die zweite alte Form — umgekehrte Reihenfolge — bleibt ebenfalls offen
  // (der Platzhalter „-“ ist eindeutig, Stammdaten.vue nimmt den echten Typ).
  for (const alt of ['#/dienste/vorlagen/chorplan/stammdaten/-', '#/dienste/vorlagen/-/stammdaten/chorplan']) {
    const i = routerAusfuehren({ hash: alt })
    assert.equal(i.context.router.currentPageName.value, 'PlanrahmenStammdaten',
      `${alt} führt zur Stammdaten-Seite`)
  }
}

// ── C: Der Vorlagen-Editor bleibt ein eigener Treffer ──────────────────────
{
  const h = routerAusfuehren({ hash: '#/dienste/vorlagen/chorplan' })
  assert.equal(h.context.router.currentPageName.value, 'PlanrahmenPlantypEditor',
    'der Editor wird nicht vom Stammdaten-Muster geschluckt')
}

console.log('BUG-S1 Router: beide Link-Formen führen zur Stammdaten-Seite: bestanden')
