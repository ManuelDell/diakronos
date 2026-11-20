import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
// UI-R10b (Review, Punkt 2): der Router führt keine eigene Fassung der
// Verwaltungsregel mehr — sein Rückfall ist `false` (fail closed). Dieser
// Harness setzt deshalb die ECHTE Regel aus `menue.js` ein.
import { echteVerwaltungsregel } from './helpers/verwaltungsregel.mjs'

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

// UI-R10b (Review, Punkt 2): die echte Regel für die Router-vm (fail closed
// im Router ohne `menue.js` — die Harnesse wollen aber Seiten ÖFFNEN).
globalThis.__regel = echteVerwaltungsregel()

function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  // ON-3b: die Leitungsregel (einrichtungLeitung.mjs) wird durch
  // feste Rückgaben ersetzt — dieser Lauf prueft den Router selbst.
  .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    // CHAT-R2a-2: `router.js` bindet `modulChatErlaubt` aus `modulRechte.mjs` (EINE
    // Fassung der Regel, DOM-frei) und gibt sie weiter. Die VM streicht Importe und
    // Exporte — hier tritt dieselbe Funktion als Attrappe ein.
    .replace(/^export \{ modulChatErlaubt \}$/gm,
      "const modulChatErlaubt = (boot = {}) => { if (boot.is_admin === true) return true; if (!Array.isArray(boot.module_sichtbar)) return false; return boot.module_sichtbar.includes('chat') }")
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
    verwaltungZutreffend: globalThis.__regel,
    ref: value => ({ value }),
    shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}

// ── Neue Adressen (Entscheidung 4) ──────────────────────────────────────────
{
  // UX3a: Der Bereich heißt „Personen“ (vorher „Mitglieder“); die alten
  // Adressen leiten dauerhaft weiter (eigener Abschnitt unten).
  const h = routerAusfuehren({ is_admin: true, hash: '#/personen/uebersicht' })
  const erwartet = {
    '#/personen/uebersicht': 'MitgliederUebersicht',
    // UX3b: der Reiter „Liste“ ist die zusammengelegte Personen-Seite.
    '#/personen/liste': 'Personen',
    '#/personen/anfragen': 'MitgliederAnfragen',
    '#/personen/datenschutz': 'MitgliederDatenschutz',
    // UX3b2: die alte Adressbuch-Seite ist entfallen. Die Adresse leitet im
    // Router auf die Liste; hier (feste Routentabelle ohne Weiterleitungen)
    // steht deshalb KEIN Eintrag mehr. Die Weiterleitung selbst prüft der
    // eigene Abschnitt unten bzw. ux3b2-navigation.test.mjs.
    '#/kalender/pruefen': 'Pruefen',
    '#/dienste/meine-dienste': 'PlanrahmenDienste',
    '#/dienste/dienstplaene': 'DiensteDienstplaene',
    '#/dienste/vorlagen': 'DiensteVorlagen',
    '#/lieder/gruppen': 'Liedgruppen',
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
    '#/registrierung': '#/personen/anfragen',
    '#/anmeldungen': '#/personen/anfragen',
    '#/statistik': '#/personen/uebersicht',
    '#/anmeldung': '#/einstellungen/anmeldung',
    '#/organigramm': '#/gruppen/organigramm',
    '#/plaene': '#/dienste/dienstplaene',
    // UX3a: umbenannte und zusammengelegte Bereiche — Lesezeichen bleiben gültig.
    '#/mitglieder/liste': '#/personen/liste',
    '#/mitglieder/uebersicht': '#/personen/uebersicht',
    '#/mitglieder/anfragen': '#/personen/anfragen',
    '#/mitglieder/datenschutz': '#/personen/datenschutz',
    '#/mitglieder/loeschantraege': '#/personen/loeschantraege',
    '#/mitglieder/import': '#/personen/import',
    '#/adressbuch': '#/personen/liste',
    '#/datenschutz': '#/personen/datenschutz',
    '#/moderation': '#/kalender/pruefen',
    '#/dienstplan': '#/dienste/meine-dienste',
    '#/meine-dienste': '#/dienste/meine-dienste',
    '#/planrahmen': '#/dienste/dienstplaene',
    '#/planrahmen/meine-dienste': '#/dienste/meine-dienste',
    '#/planrahmen/einrichten': '#/dienste/vorlagen',
    '#/liedgruppen': '#/lieder/gruppen',
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
  // UX3b: der Einstieg führt BEIDE Rollen auf die Liste (dort zeigt die
  // Seite je Rolle die passende Quelle); die Übersicht bleibt Lesezeichen.
  admin.gehe('#/personen')
  assert.equal(admin.window.location.hash, '#/personen/liste', 'Einstieg → Liste')
  admin.gehe('#/mitglieder')
  // UX3b2: auch die alte Bereichsadresse führt auf die Liste — vorher landeten
  // Administratoren auf der Übersicht, obwohl die Liste der Einstieg ist.
  assert.equal(admin.window.location.hash, '#/personen/liste', 'alte Adresse → Liste')
  admin.gehe('#/dsgvo')
  assert.equal(admin.window.location.hash, '#/personen/datenschutz', 'Admin-DSGVO → Datenschutz-Reiter')

  const mitglied = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  mitglied.gehe('#/personen')
  assert.equal(mitglied.window.location.hash, '#/personen/liste', 'Mitglied → Liste')
  mitglied.gehe('#/dsgvo')
  assert.equal(mitglied.window.location.hash, '#/profile', 'Mitglied-DSGVO → Profil')
}

// ── Admin-Guard für Verwaltungsseiten ───────────────────────────────────────
{
  const ohneRecht = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  // CHAT-7b-UI-b (Review R1, Punkt 2): `#/einstellungen` (der RAHMEN) ist
  // wieder erreichbar — er trägt den Abschnitt „Gesperrte Personen“, der jeder
  // angemeldeten Person gehört. Die UNTERSEITEN der Verwaltung bleiben zu.
  for (const hash of ['#/personen/uebersicht', '#/personen/anfragen', '#/personen/datenschutz', '#/einstellungen/anmeldung']) {
    ohneRecht.gehe(hash)
    assert.equal(ohneRecht.window.location.hash, '#/', `${hash} ohne Recht → Dashboard`)
  }
  ohneRecht.gehe('#/einstellungen')
  assert.equal(ohneRecht.window.location.hash, '#/einstellungen', 'der Rahmen ist offen (eigene Sperren)')
  const mitRecht = routerAusfuehren({ is_admin: true, hash: '#/' })
  mitRecht.gehe('#/einstellungen/anmeldung')
  assert.equal(mitRecht.router.currentPageName.value, 'EinstellungenAnmeldung', 'Admin darf Einstellungen')
}

// ── EINE Menüdefinition (S12) ───────────────────────────────────────────────
{
  const menue = lies('menue.js')
  // CHAT-R2a (Chat-Konzept 10.1 Punkt 1/5, Manuel 17.11.) — ANGEPASST, nicht
  // gelöscht: „Personen“ ist kein Menüpunkt mehr, die Gruppe „Gemeinde“ führt
  // „Nachrichten“; der Personenbereich (samt `MITGLIEDER_REITER`) zieht als
  // Abschnitt in die Einstellungen um und bleibt über dieselbe Definition
  // (`menue.js`, Reiterzeile unverändert) erreichbar.
  for (const pflicht of ["'#/nachrichten'", "'#/dienste'", "'#/einstellungen'", "'#/gruppen'", "'#/kalender'", "MITGLIEDER_REITER"]) {
    assert.ok(menue.includes(pflicht), `Menüdefinition enthält ${pflicht}`)
  }
  assert.ok(!menue.includes("label: 'Personen'"), 'kein Menüpunkt „Personen“ mehr')
  // Alte Einzelpunkte dürfen nicht mehr als eigene Menüeinträge erscheinen.
  for (const alt of ["'#/registrierung'", "'#/statistik'", "'#/dsgvo'", "'#/anmeldung'", "'#/organigramm'"]) {
    assert.ok(!menue.includes(alt), `kein alter Menüpunkt ${alt}`)
  }
  for (const datei of ['components/AppSidebar.vue', 'components/AppBottomNav.vue', 'components/AppTopbar.vue']) {
    assert.ok(lies(datei).includes('menue.js'), `${datei} liest die zentrale Menüdefinition`)
  }
}

console.log('N0 Navigation: Adressen, Weiterleitungen und zentrale Menüdefinition: bestanden')
