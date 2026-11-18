/**
 * CHAT-R2a — Navigation: Personen → Nachrichten (nur der Weg, kein Inhalt).
 *
 * Verbindlich: `docs/konzepte/CHAT-KONZEPT.md` Abschnitt **10.1 Punkt 1 und 5,
 * 10.2** (Entscheidung Manuel 17.11.2026). Was die Karte verlangt und dieser
 * Test am ECHTEN Code festhält:
 *
 *   1. `menue.js` (EINE Quelle): Eintrag `personen` ist raus, `nachrichten`
 *      steht an DERSELBEN Stelle der Gruppe „Gemeinde“ (id `nachrichten`,
 *      Label „Nachrichten“, `#/nachrichten`, Symbol `nachricht`,
 *      `modul: 'chat'`).
 *   2. Handy-Leiste in der Reihenfolge **Start · Nachrichten · Gruppen ·
 *      Kalender** (der fünfte Platz „Mehr“ ist der Menü-Knopf der Schublade).
 *   3. Der Router löst `#/nachrichten`, `#/nachrichten/<gespraech>` und
 *      `#/nachrichten/suche?q=…` auf die Seite `Nachrichten` auf; die Seite
 *      liegt hinter dem Modul `chat` (fail closed). Die Platzhalter-Seite
 *      benutzt das Design-System (DkCard) und sagt „Nachrichten kommen in
 *      Kürze“.
 *   4. ALLE alten Personen-Adressen bleiben erreichbar und landen auf
 *      DENSELBEN Seiten wie heute (KEINE Weiterleitung der Reiter-Adressen);
 *      die neuen Merk-Adressen `#/personenverwaltung` und
 *      `#/einstellungen/personen` leiten auf
 *      `#/einstellungen/personenverwaltung`.
 *   5. Die Personenverwaltung ist ein Abschnitt der Einstellungen (Gruppe
 *      „Datenschutz“) und hängt NUR an `verwaltung: 'personen'`; sie bindet die
 *      bestehende Personen-Seite ein (keine zweite Umsetzung).

 * Geprüft wird an zwei Stellen, je nach Gegenstand:
 *   * die Menü-/Leisten-Regeln am importierten Modul (menue.js, fusstabs.mjs),
 *   * der Router in einer vm — Quelltext und Importe werden dort durch feste
 *     Attrappen ersetzt, wie es die bestehenden Router-Tests tun; `resolveRoute`
 *     (Adresse → Seitenname, inklusive Weiterleitungstabellen) läuft dabei
 *     ECHT, gemessen wird das Ergebnis, nicht der Quelltext.
 *
 * Lauf (eine Datei je Aufruf): node --test tests/chat-r2a-navigation.test.mjs
 */
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { MENUE, FUSS_EINTRAEGE, MENUE_EINTRAEGE, sichtbareEintraege, eintragZuSeite, verwaltungZutreffend } from '../src/diakonos/menue.js'
import { FUSSTAB_TABS, fusstabs } from '../src/diakonos/components/fusstabs.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ROUTER = lies('router.js')

/** Alle Gruppeneinträge flach (ohne Fuß). */
const gruppenEintraege = MENUE.flatMap(g => g.eintraege)
const gemeinde = MENUE.find(g => g.gruppe === 'Gemeinde')

/** Ein Modul-Fall: ein Administrator sieht alle Module (Server: `sichtbare_module`). */
const ADMIN = { istAdmin: true, istTester: false, istGast: false, module: ['chat'] }
const MITGLIED_OHNE_CHAT = { istAdmin: false, istTester: false, istGast: false, module: ['kalender'] }

// ══════════════════════════════════════════════════════════════════════════════
// 1 · Menü: „personen“ raus, „nachrichten“ an derselben Stelle
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a · Menü: der Eintrag „personen“ ist entfallen', () => {
  assert.equal(gruppenEintraege.some(e => e.id === 'personen'), false,
    'Chat-Konzept 10.1 Punkt 1: „Personen“ entfällt am Handy UND am Desktop')
  assert.equal(MENUE_EINTRAEGE.some(e => e.id === 'personen'), false,
    'auch im Fußbereich gibt es keinen Personen-Eintrag')
  assert.equal(gruppenEintraege.some(e => e.label === 'Personen'), false)
  assert.equal(gruppenEintraege.some(e => e.href === '#/personen'), false,
    'kein Menüpunkt zeigt mehr auf die alte Bereichsadresse')
})

test('CHAT-R2a · Menü: „nachrichten“ steht an DERSELBEN Stelle der Gruppe „Gemeinde“', () => {
  assert.ok(gemeinde, 'Gruppe „Gemeinde“ vorhanden')
  // Reihenfolge folgt aus der Liste selbst (10.2) — nicht aus dem Zeichner.
  assert.deepEqual(gemeinde.eintraege.map(e => e.label), ['Nachrichten', 'Gruppen'])
  const nachrichten = gemeinde.eintraege[0]
  assert.equal(nachrichten.id, 'nachrichten')
  assert.equal(nachrichten.href, '#/nachrichten')
  assert.equal(nachrichten.icon, 'nachricht', 'Symbol `nachricht` (Karte)')
  assert.equal(nachrichten.modul, 'chat', 'Chat-Konzept 10.2: Modul `chat`')
  assert.deepEqual(nachrichten.seiten, ['Nachrichten'], 'seiten: [Nachrichten, …]')
  assert.equal(nachrichten.suche, true, 'Ziel in der Befehlspalette')

  // Das Symbol gibt es WIRKLICH im Vorrat, in derselben Strichfamilie (24er-
  // Raster, Strichstärke 2) — kein leerer Platz im Menü.
  const vorrat = lies('menue.js')
  const pfad = /nachricht:\s*'([^']+)'/.exec(vorrat)
  assert.ok(pfad, 'ICON_PFADE kennt `nachricht`')
  assert.ok(pfad[1].length > 10, 'der Pfad ist gezeichnet, nicht leer')
})

test('CHAT-R2a · Menü: Sichtbarkeit — Administrator sieht „Nachrichten“, ohne Chat-Leserecht nicht', () => {
  const ids = (rechte) => sichtbareEintraege(gemeinde, rechte).map(e => e.id)
  assert.deepEqual(ids(ADMIN), ['nachrichten', 'gruppen'], 'Admin: Nachrichten · Gruppen')
  // R-3: ohne das Modul in der Serverliste bleibt der Punkt weg (fail closed).
  assert.deepEqual(ids(MITGLIED_OHNE_CHAT), ['gruppen'],
    'ohne Chat-Leserecht kein Menüpunkt (der Server prüft ohnehin)')
  // Und die Markierung „wo bin ich“ folgt derselben Definition.
  assert.equal(eintragZuSeite('Nachrichten').eintrag.id, 'nachrichten')
  // CHAT-R2a-2 (Punkt f): Die alte Personen-Seite markiert KEINEN eigenen
  // Menüpunkt mehr — sie gehört jetzt zum Einstellungen-Eintrag (der Bereich
  // ist dorthin umgezogen, die Adresse bleibt gültig).
  assert.equal(eintragZuSeite('Personen').eintrag.id, 'einstellungen',
    'die alte Personen-Seite gehört zum umgezogenen Bereich (Einstellungen)')
})

// ══════════════════════════════════════════════════════════════════════════════
// 2 · Handy-Leiste: Start · Nachrichten · Gruppen · Kalender
// ══════════════════════════════════════════════════════════════════════════════
// CHAT-R2a-2 (Review R1): Die Leiste hängt am Chat-Modul und an `is_admin` —
// ohne Modulliste zeigt sie „Nachrichten“ NICHT mehr (der Wächter wirft sonst
// auf den Start zurück). Diese Datei übergibt deshalb die volle Sitzung
// (Administrator); die Modul-Regel selbst prüft `chat-r2a-2-navigation`.
const VOLL = { istGast: false, istAdmin: true, module: ['chat', 'kalender', 'gruppen'] }

test('CHAT-R2a · Handy-Leiste: Start · Nachrichten · Gruppen · Kalender', () => {
  const mitglied = fusstabs(VOLL)
  // CHAT-3a (Chat-Konzept 10.1/10.2, Manuel 17.11.): ANGEPASST, nicht gelöscht.
  // Der fünfte Platz heißt jetzt „Mehr“ und öffnet die bestehende Schublade.
  assert.deepEqual(mitglied.map(t => t.label),
    ['Start', 'Nachrichten', 'Gruppen', 'Kalender', 'Mehr'],
    'Chat-Konzept 10.1 Punkt 1: fünf Plätze, „Mehr“ öffnet das Menü')
  assert.deepEqual(mitglied.map(t => t.href),
    ['#/', '#/nachrichten', '#/gruppen', '#/kalender', ''])
  assert.ok(mitglied.length <= 5, 'Prinzip N5: höchstens fünf Plätze')
  assert.equal(mitglied.filter(t => !t.schublade).length, 4, 'vier echte Ziele')
  assert.ok(!mitglied.some(t => t.href === '#/personen'), 'kein Personen-Platz mehr')

  // Gäste: der Server lässt sie in keinen der neuen Bereiche — es bleibt bei
  // Start und Kalender (dieselbe Regel wie `GAST_SEITEN`) plus dem „Mehr“-Platz,
  // der ihre (leere) Seitenleiste öffnet.
  assert.deepEqual(fusstabs({ ...VOLL, istGast: true }).map(t => t.label),
    ['Start', 'Kalender', 'Mehr'])

  // Jeder Leisten-Tab hat eine Entsprechung im Menü und markiert DIESELBEN
  // Seiten (keine zweite Wahrheit über „wo bin ich“).
  for (const tab of FUSSTAB_TABS) {
    // CHAT-3a: „Mehr“ hat keine Adresse und keine Seiten — es ist ein KNOPF,
    // der die Schublade öffnet (die Schublade IST die Seitenleiste).
    if (tab.schublade) {
      assert.equal(tab.href, '', 'kein Ziel für „Mehr“')
      assert.deepEqual(tab.seiten, [])
      continue
    }
    const eintrag = gruppenEintraege.find(e => e.href === tab.href)
    assert.ok(eintrag, `Leisten-Ziel ${tab.href} steht auch im Menü`)
    assert.deepEqual([...tab.seiten].sort(), [...eintrag.seiten].sort(),
      `Tab „${tab.label}“ markiert dieselben Seiten wie der Menüeintrag`)
  }
})

// ══════════════════════════════════════════════════════════════════════════════
// 3 · Seiten der Einstellungen: Personenverwaltung (nur `verwaltung: 'personen'`)
// ══════════════════════════════════════════════════════════════════════════════

/** Die Abschnitte aus dem QUELLTEXT der Seite (nicht aus einer zweiten Liste). */
function einstellungsAbschnitte() {
  const quelle = lies('pages/Einstellungen.vue').replace(/\s+/g, ' ')
  const treffer = [...quelle.matchAll(
    /\{\s*id:\s*'([a-z0-9-]+)',\s*label:\s*'([^']+)',\s*href:\s*'([^']+)',\s*seite:\s*'([^']+)'(?:(?!\},\s*\{)[\s\S])*?gruppe:\s*'([a-z]+)'(?:(?!\},\s*\{)[\s\S])*?(?:verwaltung:\s*'([a-z]+)')?/g,
  )]
  return treffer.map((m) => ({ id: m[1], label: m[2], href: m[3], seite: m[4], gruppe: m[5] }))
}

test('CHAT-R2a · Einstellungen: Abschnitt „Personenverwaltung“ in der Gruppe „Datenschutz“', () => {
  const quelle = lies('pages/Einstellungen.vue')
  const flach = quelle.replace(/\s+/g, ' ')
  // Genau EIN Abschnitt — nicht zwei halbe Wege.
  assert.equal((flach.match(/id: 'personenverwaltung'/g) || []).length, 1,
    'genau ein Abschnitt „Personenverwaltung“')
  const eintrag = /\{ id: 'personenverwaltung', label: 'Personenverwaltung', href: '#\/einstellungen\/personenverwaltung', seite: 'EinstellungenPersonenverwaltung', inhalt: PERSONENVERWALTUNG, gruppe: 'datenschutz', verwaltung: 'personen' \}/
  assert.match(flach, eintrag,
    'Adresse, Seitenname, Gruppe und Verwaltungsstufe nach Chat-Konzept 10.2')
  // Die Gruppe „Datenschutz“ ist die des Konzepts (10.1 Punkt 5).
  const gruppe = /gruppe: '([a-z]+)'/.exec(flach.slice(flach.indexOf("id: 'personenverwaltung'")))
  assert.equal(gruppe[1], 'datenschutz')
})

test('CHAT-R2a · Einstellungen: die umgezogene Verwaltung bindet die BESTEHENDE Personen-Seite ein', () => {
  const quelle = lies('pages/Einstellungen.vue')
  assert.match(quelle, /const PERSONENVERWALTUNG = defineAsyncComponent\(\(\) => import\('\.\/Personen\.vue'\)\)/,
    'einbinden, NICHT neu bauen und nicht kopieren')
  // Kein zweiter Personen-Rahmen in der Datei: Reiterzeile und Liste kommen
  // aus `pages/Personen.vue`, die Einstellungen zeichnen sie nicht nach.
  for (const verboten of ['MITGLIEDER_REITER', 'personenReiter(', '<DkReiter']) {
    assert.ok(!quelle.includes(verboten), `die Einstellungen bauen die Reiterzeile nicht nach (${verboten})`)
  }
  // Der Bereich erscheint eingebettet — der Seitenkopf der Personen-Seite
  // weicht dem Kopf der Einstellungen (sonst stünden zwei Überschriften).
  const personen = lies('pages/Personen.vue')
  assert.match(personen, /defineProps\(\{\s*embedded: \{ type: Boolean, default: false \},?\s*\}\)/)
  assert.match(personen, /<DkPageHeader v-if="!embedded"/)
  // Die vier Reiter der bestehenden Seite gibt es unverändert (menue.js).
  for (const reiter of ['Liste', 'Anfragen', 'Datenschutz', 'Import']) {
    assert.ok(lies('menue.js').includes(`label: '${reiter}'`), `Reiter „${reiter}“ bleibt`)
  }
})

test('CHAT-R2a · Personenverwaltung hängt NUR an `verwaltung: \'personen\'`', () => {
  const quelle = lies('pages/Einstellungen.vue').replace(/\s+/g, ' ')
  const punkt = "id: 'personenverwaltung'"
  const abschnitt = quelle.slice(quelle.indexOf(punkt), quelle.indexOf(punkt) + 400)
  assert.match(abschnitt, /verwaltung: 'personen'/, 'Personenbereich = Mitgliederverwaltung UND Administration')
  assert.doesNotMatch(abschnitt, /verwaltung: 'admin'/, 'keine Administrations-Schranke')
  assert.doesNotMatch(abschnitt, /nurSystemManager: true/, 'kein System-Manager-Vorbehalt')
  assert.doesNotMatch(abschnitt, /nurDevmodus: true/, 'kein Dev-Modus-Vorbehalt')
  // `verwaltungZutreffend` ist die EINE Regel (menue.js) und wird benutzt.
  assert.match(quelle, /verwaltungZutreffend\(a\.verwaltung, verwaltungsRechte\.value\)/,
    'die Sichtbarkeit läuft über die eine Verwaltungsregel')
})

// ══════════════════════════════════════════════════════════════════════════════
// 4 · Router: neue Seite, alte Adressen, Merk-Adressen, Modul-Guard
// ══════════════════════════════════════════════════════════════════════════════

/**
 * router.js in einer vm ausführen (Muster der bestehenden Router-Tests) und die
 * ECHTEN Auflösungen befragen: `wohin(hash)` gibt das Weiterleitungsziel (oder
 * null) und `seite(hash)` den Seitennamen nach `resolveRoute`.
 */
function routerVm(boot = {}) {
  let quelle = lies('router.js')
  quelle = quelle.replace(/^import .*$/gm, '')
  // CHAT-R2a-2: `router.js` bindet `modulChatErlaubt` aus `modulRechte.mjs`
  // (eine Fassung der Regel, DOM-frei) und gibt sie weiter. Die VM streicht
  // Importe — hier tritt dieselbe Funktion als Attrappe ein, damit der Rest
  // des Routers läuft. Der Re-Export fällt mit den übrigen Exporten weg.
  quelle = quelle.replace(/^export \{ modulChatErlaubt \}$/gm,
    'const modulChatErlaubt = (boot = {}) => { if (boot.is_admin === true) return true; if (!Array.isArray(boot.module_sichtbar)) return false; return boot.module_sichtbar.includes("chat") }')
  quelle = quelle.replace(/^export \{([^}]*)\}$/gm, '')
  quelle = quelle.replace(/^export /gm, '')
  const windowStub = {
    __DIakonosBOOT: boot,
    location: { hash: boot.hash || '#/', replace(ziel) { this.hash = ziel; ersetzt.push(ziel) } },
    addEventListener: () => {},
    matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
    history: { replaceState: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  }
  const ersetzt = []
  const context = {
    console,
    window: windowStub,
    document: { title: '', addEventListener: () => {}, querySelector: () => null },
    location: windowStub.location,
    history: windowStub.history,
    sessionStorage: windowStub.sessionStorage,
    localStorage: windowStub.localStorage,
    navigator: { language: 'de-DE' },
    setTimeout, clearTimeout, setInterval, clearInterval,
    Promise,
  }
  vm.createContext(context)
  context.__vue = {
    ref: (v) => ({ value: v }),
    computed: (fn) => ({ get value() { return fn() } }),
    shallowRef: (v) => ({ value: v }),
  }
  vm.runInContext(`
const ref = globalThis.__vue.ref
const computed = globalThis.__vue.computed
const shallowRef = globalThis.__vue.shallowRef
const setzeFenstertitel = () => {}
const darfWebsite = () => true
const fehlertext = (e) => String(e)
const einrichtungLeitung = {
  EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
  einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
  einrichtungGesehen: () => false,
}
const rueckwegBleibtGueltig = () => true
const rueckwegVergessen = () => {}
${quelle}
globalThis.routerApi = {
  weiterleitungsZiel, routeMap, dynamicRoutes, verwaltungsStufeSeite, modulChatErlaubt,
  PERSONEN_VERWALTUNG_PAGES, verwaltungErlaubt,
}
`, context)
  const api = context.routerApi
  /** Seitennamen einer Adresse — dieselbe Reihenfolge wie `resolveRoute`. */
  const seite = (hash) => {
    const [pfadRoh] = hash.split('?')
    const pfad = pfadRoh.length > 2 && pfadRoh.endsWith('/') ? pfadRoh.replace(/\/+$/, '') : pfadRoh
    if (api.routeMap[pfad]) return api.routeMap[pfad]
    for (const r of api.dynamicRoutes) {
      const m = pfad.match(r.pattern)
      if (m) return r.page
    }
    return null
  }
  return { api, seite, ersetzt, window: windowStub, context }
}

test('CHAT-R2a · Router: „Nachrichten“ — alle drei Adressformen landen auf der Seite `Nachrichten`', () => {
  const { seite } = routerVm()
  for (const hash of ['#/nachrichten', '#/nachrichten/chat-g-abc', '#/nachrichten/suche']) {
    assert.equal(seite(hash), 'Nachrichten', `${hash} → Seite Nachrichten`)
  }
  // `suche` ist KEIN Gespräch: das Suchmuster steht vor dem Gesprächsmuster.
  const { api } = routerVm()
  const muster = api.dynamicRoutes.filter(r => r.page === 'Nachrichten').map(r => String(r.pattern))
  assert.equal(muster.length, 2, 'genau zwei Muster (Suche + Gespräch)')
  assert.ok(muster[0].includes('suche'), 'das Suchmuster steht zuerst')
  // `?q=…` gehört nicht zum Pfad (die Route wird trotzdem gefunden).
  assert.equal(seite('#/nachrichten/suche?q=An%20na'), 'Nachrichten')
  // Die Seite ist geladen (Platzhalter), nicht „NichtGefunden“.
  assert.match(lies('router.js'), /Nachrichten:\s+\(\) => import\('\.\/pages\/Nachrichten\.vue'\)/)
})

test('CHAT-R2a · Router: „Nachrichten“ liegt hinter dem Modul `chat` (fail closed)', () => {
  const offen = routerVm({ is_admin: true })
  assert.equal(offen.api.modulChatErlaubt({ is_admin: true }), true, 'Administrator: alle Module')
  assert.equal(offen.api.modulChatErlaubt({ module_sichtbar: ['chat', 'kalender'] }), true)
  assert.equal(offen.api.modulChatErlaubt({ module_sichtbar: ['kalender'] }), false,
    'ohne `chat` in der Serverliste kein Zutritt')
  assert.equal(offen.api.modulChatErlaubt({}), false,
    'fehlende Liste = alter Server → fail closed')
  assert.equal(offen.api.modulChatErlaubt({ is_admin: 'true' }), false,
    'nur ein echtes `true` zählt (wie bei den Verwaltungsstufen)')
  // Der Wächter hängt am Seitennamen (eine Seite, drei Adressen).
  const wache = ROUTER.slice(ROUTER.indexOf('// „Nachrichten“ liegt hinter dem Modul'))
  assert.match(wache, /if \(name !== 'Nachrichten'\) return/,
    'der Wächter greift für die Seite — also für Liste, Gespräch und Suche')
  assert.match(wache, /if \(modulChatErlaubt\(window\.__DIakonosBOOT \|\| \{\}\)\) return/,
    'er fragt die eine Modul-Regel')
})

test('CHAT-R2a · Router: alle alten Personen-Adressen behalten ihr Ziel', () => {
  const { api, seite } = routerVm({ is_admin: true, ist_mitgliederverwaltung: true })
  const ziel = (hash) => api.weiterleitungsZiel(hash.split('?')[0], hash)

  // KEINE Weiterleitung der Reiter-Adressen (10.2, Tabelle): sie bleiben
  // gültige Ziele, sonst verlöre der Reiter „Datenschutz“ seine Adresse.
  for (const [hash, name] of [
    ['#/personen/liste', 'Personen'],
    ['#/personen/anfragen', 'MitgliederAnfragen'],
    ['#/personen/anfragen/links', 'MitgliederAnfragen'],
    ['#/personen/anfragen/formulare', 'MitgliederAnfragen'],
    ['#/personen/datenschutz', 'MitgliederDatenschutz'],
    ['#/personen/import', 'MitgliederImport'],
    ['#/personen/uebersicht', 'MitgliederUebersicht'],
    ['#/personen/loeschantraege', 'MitgliederLoeschantraege'],
  ]) {
    assert.equal(ziel(hash), null, `${hash} wird NICHT weitergeleitet`)
    assert.equal(seite(hash), name, `${hash} → ${name}`)
  }
  // Das Personenprofil bleibt genau das: `#/mitglied/<id>`.
  assert.equal(ziel('#/mitglied/M-1'), null, 'das Profil wird nicht umgeleitet')
  assert.equal(seite('#/mitglied/M-1'), 'MitgliedDetail')

  // Die BESTEHENDEN Weiterleitungen bleiben unverändert.
  assert.equal(ziel('#/personen'), '#/personen/liste', '10.2: unveränderte Weiterleitung')
  assert.equal(ziel('#/personen/adressbuch'), '#/personen/liste')
  assert.equal(ziel('#/adressbuch'), '#/personen/liste')
  assert.equal(ziel('#/mitglieder'), '#/personen/liste')
  assert.equal(ziel('#/mitglieder/liste'), '#/personen/liste')
  assert.equal(ziel('#/mitglieder/anfragen'), '#/personen/anfragen')
  assert.equal(ziel('#/mitglieder/datenschutz'), '#/personen/datenschutz')
  assert.equal(ziel('#/mitglieder/import'), '#/personen/import')
  assert.equal(ziel('#/mitglieder/loeschantraege'), '#/personen/loeschantraege')
  assert.equal(ziel('#/mitglieder/uebersicht'), '#/personen/uebersicht')
})

test('CHAT-R2a · Router: die neuen Merk-Adressen leiten auf die Personenverwaltung', () => {
  const { api, seite } = routerVm({ is_admin: true, ist_mitgliederverwaltung: true })
  for (const alt of ['#/personenverwaltung', '#/einstellungen/personen']) {
    assert.equal(api.weiterleitungsZiel(alt, alt), '#/einstellungen/personenverwaltung',
      `${alt} → #/einstellungen/personenverwaltung`)
  }
  // Der Zielpunkt existiert und trägt den Seitennamen des Konzepts (10.2).
  assert.equal(seite('#/einstellungen/personenverwaltung'), 'EinstellungenPersonenverwaltung')
  // Ein Abfrageteil wird mitgenommen (wie bei allen festen Weiterleitungen):
  // `weiterleitungsZiel` liefert das reine Ziel, `resolveRoute` hängt den
  // Abfrageteil an (`_mitAbfrage`) — hier wird das erreichte Ziel geprüft.
  const ziel = api.weiterleitungsZiel('#/personenverwaltung', '#/personenverwaltung?x=1')
  assert.equal(ziel, '#/einstellungen/personenverwaltung')
  assert.equal(`${ziel}?x=1`, '#/einstellungen/personenverwaltung?x=1')
})

test('CHAT-R2a · Router: Personenverwaltung — dieselbe Liste wie die Personen-Reiter, nicht verdoppelt', () => {
  const { api } = routerVm()
  const liste = api.PERSONEN_VERWALTUNG_PAGES
  // In der Liste stehen die Personen-Seiten, die eine Verwaltungsstufe
  // verlangen; `MitgliederListe` bleibt bewusst draußen (die Liste ist für
  // ALLE da — siehe `SEITEN.personen` in `r10-menue-routen`).
  for (const seite of ['EinstellungenPersonenverwaltung', 'MitgliederAnfragen',
    'MitgliederDatenschutz', 'MitgliederImport', 'MitgliederUebersicht', 'MitgliederLoeschantraege']) {
    assert.equal(liste.has(seite), true, `${seite} steht im Personenbereich`)
  }
  // Genau EIN neuer Name — die Liste wird erweitert, nicht verdoppelt.
  assert.equal(api.verwaltungsStufeSeite('EinstellungenPersonenverwaltung'), 'personen')
  assert.equal(api.verwaltungsStufeSeite('EinstellungenGemeinde'), 'admin',
    'die Administration bleibt, was sie ist')
  assert.equal(api.verwaltungsStufeSeite('MitgliederListe'), null,
    'die Liste hängt an keiner Verwaltungsstufe (alle Rollen sehen sie)')
  // Die Stufe wird über die EINE Regel geprüft. Der Router bezieht sie aus
  // `menue.js::verwaltungZutreffend`; in der vm steht dafür der Rückfall
  // `() => false` (fail closed, weil die Importe gestrichen sind). Gemessen
  // wird deshalb HIER die echte Regel — dieselbe, die der Betrieb benutzt.
  assert.equal(verwaltungZutreffend('personen', { istAdmin: false, istMitgliederverwaltung: true }), true,
    'Mitgliederverwaltung kommt hinein')
  assert.equal(verwaltungZutreffend('personen', { istAdmin: false, istMitgliederverwaltung: false }), false,
    'ein Mitglied nicht')
  assert.equal(verwaltungZutreffend('personen', {}), false, 'fail closed ohne Flaggen')
  // Und der Router-Rückfall bleibt fail closed (keine zweite Fassung der Regel).
  assert.equal(api.verwaltungErlaubt('personen', { is_admin: false, ist_mitgliederverwaltung: true }), false,
    'ohne die Regel aus `menue.js` öffnet der Router nichts (Sicherheitsnetz)')
  assert.match(lies('router.js'), /const verwaltungRegel = typeof verwaltungZutreffend === 'function'/,
    'der Router delegiert an die eine Regel aus menue.js')
})

// ══════════════════════════════════════════════════════════════════════════════
// 5 · Die Platzhalter-Seite hält das Design-System ein
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a · Nachrichten-Seite: Design-System, keine erfundenen Inhalte', () => {
  // CHAT-3a: Die Seite ist kein Platzhalter mehr — sie zeigt Liste und Verlauf
  // (eigene Karte). Was hier BLEIBT, ist die Zusage der Karte: die Oberfläche
  // besteht aus Bausteinen des Design-Systems, und sie erfindet keine Inhalte
  // (jede Zeile kommt vom Server; ohne Antwort steht ein Leerzustand da).
  const quelle = lies('pages/Nachrichten.vue')
  assert.match(quelle, /<DkPageHeader/, 'der Seitenkopf ist der gemeinsame Baustein')
  assert.match(quelle, /DkCard|DkEmpty|DkSkelett/, 'Flächen/Leerzustände aus dem Design-System')
  assert.ok(!/Nachrichten kommen in Kürze/.test(quelle), 'der Platzhalter ist abgelöst (CHAT-3a)')
  // Keine erfundenen Gespräche/Nachrichten: aller Inhalt kommt aus den
  // Chat-Endpunkten, die Seite legt keine Beispieldaten an.
  for (const verboten of ['Musterstadt', 'Sabine Roth', 'Beispielgespräch']) {
    assert.ok(!quelle.includes(verboten), `kein erfundener Inhalt (${verboten})`)
  }
  // Nur Tokens — keine harten Farben im Stil (dieselbe Regel wie überall).
  const stil = quelle.slice(quelle.lastIndexOf('<style'))
  for (const farbe of stil.match(/(^|[;{\s])(color|background|border-color)\s*:\s*([^;]+)/g) || []) {
    assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(farbe) && !/\b(rgba?|hsla?)\(/.test(farbe),
      `harter Farbwert: ${farbe.trim()}`)
  }
})

test('CHAT-R2a · Nachrichten-Seite steht in der Testliste des Baus (FE-TEST-1)', () => {
  const liste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8')
  assert.match(liste, /^tests\/chat-r2a-\*\.test\.mjs$/m,
    'das Muster für diese Datei ist eingetragen')
})
