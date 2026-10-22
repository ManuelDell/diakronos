import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

/**
 * N0 — Router und Menü für die Neuordnung.
 *
 * Läuft den ECHTEN Router in einer vm aus (keine Textsuche) und prüft:
 *  - neue Adressen lösen auf die richtigen Seiten auf,
 *  - alte Adressen werden weitergeleitet (Konzept Abschnitt 8, Entscheidung 9),
 *  - die rollenabhängige Weiterleitung von #/mitglieder und #/dsgvo,
 *  - der Admin-Guard sperrt Verwaltungsseiten ohne Recht.
 * Zusätzlich: EINE Menüdefinition (S12) speist Seitenleiste und Mehr-Blatt.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
  let hashchange
  const window = {
    location: {
      hash: boot.hash || '#/',
      replace(hash) { this.hash = hash },
    },
    __DIakonosBOOT: boot,
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
  const context = { window, console, setzeFenstertitel() {},
    ref: value => ({ value }),
    shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}

// ── Neue Adressen (Entscheidung 4) ──────────────────────────────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/mitglieder/uebersicht' })
  const erwartet = {
    '#/mitglieder/uebersicht': 'MitgliederUebersicht',
    '#/mitglieder/liste': 'MitgliederListe',
    '#/mitglieder/anfragen': 'MitgliederAnfragen',
    '#/mitglieder/datenschutz': 'MitgliederDatenschutz',
    '#/einstellungen': 'Einstellungen',
    '#/einstellungen/anmeldung': 'EinstellungenAnmeldung',
    // N9: jeder Einstellungs-Abschnitt hat eine eigene Adresse.
    '#/einstellungen/gemeinde': 'EinstellungenGemeinde',
    '#/einstellungen/registrierung': 'EinstellungenRegistrierung',
    '#/einstellungen/datenschutz': 'EinstellungenDatenschutz',
    '#/gruppen/organigramm': 'GruppenBereich',
  }
  for (const [hash, seite] of Object.entries(erwartet)) {
    h.gehe(hash)
    assert.equal(h.router.currentPageName.value, seite, `${hash} → ${seite}`)
  }
}

// ── Weiterleitungen alter Adressen ──────────────────────────────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  const erwartet = {
    '#/registrierung': '#/mitglieder/anfragen',
    '#/anmeldungen': '#/mitglieder/anfragen',
    '#/statistik': '#/mitglieder/uebersicht',
    '#/anmeldung': '#/einstellungen/anmeldung',
    '#/organigramm': '#/gruppen/organigramm',
    '#/plaene': '#/planrahmen',
  }
  for (const [alt, neu] of Object.entries(erwartet)) {
    h.window.location.hash = alt
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }
}

// ── Rollenabhängige Weiterleitung ───────────────────────────────────────────
{
  const admin = routerAusfuehren({ is_admin: true, hash: '#/' })
  admin.gehe('#/mitglieder')
  assert.equal(admin.window.location.hash, '#/mitglieder/uebersicht', 'Admin → Übersicht')
  admin.gehe('#/dsgvo')
  assert.equal(admin.window.location.hash, '#/mitglieder/datenschutz', 'Admin-DSGVO → Datenschutz-Reiter')

  const mitglied = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  mitglied.gehe('#/mitglieder')
  assert.equal(mitglied.window.location.hash, '#/mitglieder/liste', 'Mitglied → Liste')
  mitglied.gehe('#/dsgvo')
  assert.equal(mitglied.window.location.hash, '#/profile', 'Mitglied-DSGVO → Profil')
}

// ── Admin-Guard für Verwaltungsseiten ───────────────────────────────────────
{
  const ohneRecht = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  for (const hash of ['#/mitglieder/uebersicht', '#/mitglieder/anfragen', '#/mitglieder/datenschutz', '#/einstellungen', '#/einstellungen/anmeldung']) {
    ohneRecht.gehe(hash)
    assert.equal(ohneRecht.window.location.hash, '#/', `${hash} ohne Recht → Dashboard`)
  }
  const mitRecht = routerAusfuehren({ is_admin: true, hash: '#/' })
  mitRecht.gehe('#/einstellungen/anmeldung')
  assert.equal(mitRecht.router.currentPageName.value, 'EinstellungenAnmeldung', 'Admin darf Einstellungen')
}

// ── EINE Menüdefinition (S12) ───────────────────────────────────────────────
{
  const menue = lies('menue.js')
  for (const pflicht of ["'#/mitglieder'", "'#/einstellungen'", "'#/gruppen'", "'#/planrahmen'", "MITGLIEDER_REITER"]) {
    assert.ok(menue.includes(pflicht), `Menüdefinition enthält ${pflicht}`)
  }
  // Alte Einzelpunkte dürfen nicht mehr als eigene Menüeinträge erscheinen.
  for (const alt of ["'#/registrierung'", "'#/statistik'", "'#/dsgvo'", "'#/anmeldung'", "'#/organigramm'"]) {
    assert.ok(!menue.includes(alt), `kein alter Menüpunkt ${alt}`)
  }
  for (const datei of ['components/AppSidebar.vue', 'components/AppBottomNav.vue', 'components/AppTopbar.vue']) {
    assert.ok(lies(datei).includes('menue.js'), `${datei} liest die zentrale Menüdefinition`)
  }
}

console.log('N0 Navigation: Adressen, Weiterleitungen und zentrale Menüdefinition: bestanden')
