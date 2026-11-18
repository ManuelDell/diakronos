/**
 * CHAT-R2a-2 — Nachbesserung Navigation Personen → Nachrichten (Review-Befunde).
 *
 * Der Test hält die SECHS Befunde der Karte am ECHTEN Code fest. Er prüft
 * Verhalten, wo Verhalten prüfbar ist (menue.js, fusstabs.mjs, fenstertitel.js,
 * befehlspalette.mjs, Router in der vm) — und Quelltext nur dort, wo es keine
 * aufrufbare Funktion gibt (SFC-Vorlagen).
 *
 *   a) Einstellungen → Personenverwaltung: die Reiter bleiben EINGEBETTET
 *      (`#/einstellungen/personenverwaltung/<reiter>`), die alten
 *      `#/personen/*`-Adressen bleiben unverändert funktionsfähig.
 *   b) Fußleiste: Tab „Nachrichten“ trägt `modul: 'chat'` und wird über
 *      `bootModule()` gefiltert — ohne Chat-Modul kein Tab (keine Sackgasse).
 *   c) Fenstertitel: alle Personen-Seiten heißen „Personenverwaltung“.
 *   d) Anfragen-Zähler (`badge: 'anfragen'`) liegt am Einstellungen-Eintrag.
 *   e) Befehlspalette: „Person anlegen“ zielt auf die Personenverwaltung;
 *      „pers“ findet sie.
 *   f) Brotkrumen: alle Personen-Reiter einheitlich „Einstellungen ›
 *      Personenverwaltung“; die alten Seiten markieren den Einstellungen-Eintrag.
 *
 * Lauf (eine Datei je Aufruf): node --test tests/chat-r2a-2-navigation.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  MENUE, FUSS_EINTRAEGE, MITGLIEDER_REITER, personenReiter, personenAnfragenReiter,
  personenReiterAusHash, anfragenUnterbereichAusHash, anfragenUnterbereichHref,
  personenReiterHref, PERSONENVERWALTUNG_BASIS, eintragZuSeite, krumenZuSeite,
  sichtbareEintraege,
} from '../src/diakonos/menue.js'
import { FUSSTAB_TABS, fusstabs } from '../src/diakonos/components/fusstabs.mjs'
import { modulChatErlaubt } from '../src/diakonos/modulRechte.mjs'
import { SEITENTITEL_NICHT_IM_MENUE, baueTitel } from '../src/diakonos/fenstertitel.js'
import { aktionsEintraege, paletteZeilen, seitenEintraege, passtZu } from '../src/diakonos/composables/befehlspalette.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ohneKommentare = (text) => text
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')

const MITGLIED_VERWALTUNG = { istAdmin: false, istMitgliederverwaltung: true }
const GRUPPEN_EINTRAEGE = MENUE.flatMap(g => g.eintraege)

// ══════════════════════════════════════════════════════════════════════════════
// a) Reiter bleiben INNERHALB der Einstellungen
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2a · eingebettet tragen die Reiter die Adresse des Einstellungen-Abschnitts', () => {
  const reiter = personenReiter({ ...MITGLIED_VERWALTUNG, eingebettet: true })
  assert.deepEqual(reiter.map(r => r.label), ['Liste', 'Anfragen', 'Datenschutz', 'Import'])
  for (const r of reiter) {
    assert.ok(r.href.startsWith(`${PERSONENVERWALTUNG_BASIS}/`),
      `${r.label}: Adresse bleibt im Rahmen (${r.href})`)
    assert.ok(!r.href.startsWith('#/personen'), `${r.label}: kein Sprung auf die alte Bereichsadresse`)
  }
  assert.equal(reiter.find(r => r.id === 'liste').href, `${PERSONENVERWALTUNG_BASIS}/liste`)
  assert.equal(reiter.find(r => r.id === 'anfragen').href, `${PERSONENVERWALTUNG_BASIS}/anfragen`)

  // Auch die zweite Ebene (Unterbereiche von „Anfragen“) bleibt im Rahmen.
  const unter = personenAnfragenReiter({ ...MITGLIED_VERWALTUNG, eingebettet: true })
  assert.deepEqual(unter.map(u => u.label), ['Anfragen', 'Links & QR-Codes', 'Formulare'])
  for (const u of unter) {
    assert.ok(u.href.startsWith(`${PERSONENVERWALTUNG_BASIS}/anfragen`),
      `${u.label}: Unterbereich bleibt im Rahmen (${u.href})`)
  }
  assert.equal(anfragenUnterbereichHref('links', true), `${PERSONENVERWALTUNG_BASIS}/anfragen/links`)
})

test('CHAT-R2a-2a · die alten #/personen/*-Adressen bleiben unverändert (ohne Rahmen)', () => {
  // Ohne `eingebettet` ändert sich NICHTS an den bestehenden Adressen.
  assert.deepEqual(personenReiter({ ...MITGLIED_VERWALTUNG }).map(r => r.href), [
    '#/personen/liste', '#/personen/anfragen', '#/personen/datenschutz', '#/personen/import',
  ])
  assert.equal(personenReiterHref('anfragen', false), '#/personen/anfragen')
  assert.equal(anfragenUnterbereichHref('formulare', false), '#/personen/anfragen/formulare')
})

test('CHAT-R2a-2a · personenReiterAusHash versteht BEIDE Adressformen', () => {
  // Der alte Bereich (unverändert).
  for (const [hash, id] of [
    ['#/personen/liste', 'liste'],
    ['#/personen/anfragen', 'anfragen'],
    ['#/personen/anfragen/links', 'anfragen'],
    ['#/personen/anfragen/formulare', 'anfragen'],
    ['#/personen/datenschutz', 'datenschutz'],
    ['#/personen/import', 'import'],
  ]) {
    assert.equal(personenReiterAusHash(hash, MITGLIED_VERWALTUNG), id, `${hash} → ${id}`)
  }
  // Der Einstellungen-Abschnitt: der Abschnitt selbst IST die Liste.
  assert.equal(personenReiterAusHash(PERSONENVERWALTUNG_BASIS, MITGLIED_VERWALTUNG), 'liste')
  for (const [hash, id] of [
    [`${PERSONENVERWALTUNG_BASIS}/liste`, 'liste'],
    [`${PERSONENVERWALTUNG_BASIS}/anfragen`, 'anfragen'],
    [`${PERSONENVERWALTUNG_BASIS}/anfragen/links`, 'anfragen'],
    [`${PERSONENVERWALTUNG_BASIS}/anfragen/formulare`, 'anfragen'],
    [`${PERSONENVERWALTUNG_BASIS}/datenschutz`, 'datenschutz'],
    [`${PERSONENVERWALTUNG_BASIS}/import`, 'import'],
  ]) {
    assert.equal(personenReiterAusHash(hash, MITGLIED_VERWALTUNG), id, `${hash} → ${id}`)
  }
  // Ein Abfrageteil stört nicht (der `?anlegen=1`-Schalter der Palette).
  assert.equal(personenReiterAusHash(`${PERSONENVERWALTUNG_BASIS}?anlegen=1`, MITGLIED_VERWALTUNG), 'liste')
  // Fremde Adressen bleiben fremd.
  assert.equal(personenReiterAusHash('#/einstellungen/gemeinde', MITGLIED_VERWALTUNG), null)
  assert.equal(personenReiterAusHash('#/nachrichten', MITGLIED_VERWALTUNG), null)
  // Ohne Recht gibt es keinen Verwaltungs-Reiter — auch eingebettet nicht.
  assert.equal(personenReiterAusHash(`${PERSONENVERWALTUNG_BASIS}/datenschutz`, {}), null)
})

test('CHAT-R2a-2a · anfragenUnterbereichAusHash liest beide Basen, Unbekanntes fällt zurück', () => {
  assert.equal(anfragenUnterbereichAusHash('#/personen/anfragen/links'), 'links')
  assert.equal(anfragenUnterbereichAusHash(`${PERSONENVERWALTUNG_BASIS}/anfragen/formulare`), 'formulare')
  assert.equal(anfragenUnterbereichAusHash(`${PERSONENVERWALTUNG_BASIS}/anfragen`), 'anfragen')
  assert.equal(anfragenUnterbereichAusHash(`${PERSONENVERWALTUNG_BASIS}/anfragen/quatsch`), 'anfragen')
})

test('CHAT-R2a-2a · Router: die eingebetteten Reiter-Adressen lösen auf den Abschnitt auf', () => {
  const quelle = lies('router.js')
  for (const pfad of [
    `${PERSONENVERWALTUNG_BASIS}/liste`,
    `${PERSONENVERWALTUNG_BASIS}/anfragen`,
    `${PERSONENVERWALTUNG_BASIS}/anfragen/links`,
    `${PERSONENVERWALTUNG_BASIS}/anfragen/formulare`,
    `${PERSONENVERWALTUNG_BASIS}/datenschutz`,
    `${PERSONENVERWALTUNG_BASIS}/import`,
  ]) {
    const m = new RegExp(`'${pfad.replace(/[/]/g, '\\/')}':\\s*'([A-Za-z]+)'`).exec(quelle)
    assert.ok(m, `Route ${pfad} steht in router.js`)
    assert.equal(m[1], 'EinstellungenPersonenverwaltung', `${pfad} → EinstellungenPersonenverwaltung`)
  }
  // Die ALTEN Reiter-Adressen stehen unverändert daneben (kein Ersatz).
  for (const [pfad, seite] of [
    ['#/personen/liste', 'Personen'],
    ['#/personen/anfragen', 'MitgliederAnfragen'],
    ['#/personen/datenschutz', 'MitgliederDatenschutz'],
    ['#/personen/import', 'MitgliederImport'],
  ]) {
    assert.match(quelle, new RegExp(`'${pfad.replace(/[/]/g, '\\/')}':\\s*'${seite}'`),
      `${pfad} bleibt ${seite}`)
  }
  // Keine Weiterleitung der neuen Reiter-Adressen (sonst schluckte sie ein Sprung).
  const weiter = quelle.slice(quelle.indexOf('const WEITERLEITUNGEN'))
  assert.ok(!weiter.includes(`${PERSONENVERWALTUNG_BASIS}/`),
    'die Reiter-Adressen sind Ziele, keine Weiterleitungen')
})

test('CHAT-R2a-2a · Personen.vue schreibt die Reiter-Adresse an den Rahmen (eingebettet)', () => {
  const quelle = lies('pages/Personen.vue')
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  assert.match(skript, /const props = defineProps\(\{\s*embedded: \{ type: Boolean, default: false \},?\s*\}\)/)
  assert.match(skript, /const eingebettetWert = computed\(\(\) => props\.embedded === true\)/,
    'der Rahmen kennt seinen Zustand')
  assert.match(skript, /personenReiter\(\{[\s\S]*?eingebettet: eingebettetWert\.value/,
    'die Reiterzeile bekommt den eingebetteten Zustand')
  assert.match(skript, /personenAnfragenReiter\(\{[\s\S]*?eingebettet: eingebettetWert\.value/,
    'die Unterbereiche ebenso')
  // Der Seitenkopf weicht im Rahmen (kein zweiter Titel).
  assert.match(quelle, /<DkPageHeader v-if="!embedded"/)
})

// ══════════════════════════════════════════════════════════════════════════════
// b) Fußleiste: „Nachrichten“ hängt am Modul `chat`
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2b · der Tab „Nachrichten“ trägt `modul: \'chat\'`', () => {
  const nachrichten = FUSSTAB_TABS.find(t => t.href === '#/nachrichten')
  assert.ok(nachrichten, 'der Tab existiert')
  assert.equal(nachrichten.modul, 'chat', 'Chat-Konzept 10.2: Modul `chat`')
  assert.equal(nachrichten.nurMitglied, true, 'Gäste sehen ihn nicht')
})

test('CHAT-R2a-2b · ohne Chat-Modul kein Tab „Nachrichten“ (keine Sackgasse)', () => {
  // CHAT-3a: Der fünfte Platz „Mehr“ (Chat-Konzept 10.1/10.2) hängt an KEINEM
  // Modul — er öffnet die Menü-Schublade und bleibt deshalb in jeder Lage.
  const mitChat = fusstabs({ istGast: false, module: ['chat', 'kalender'] })
  assert.deepEqual(mitChat.map(t => t.label), ['Start', 'Nachrichten', 'Gruppen', 'Kalender', 'Mehr'])

  const ohneChat = fusstabs({ istGast: false, module: ['kalender'] })
  assert.deepEqual(ohneChat.map(t => t.label), ['Start', 'Gruppen', 'Kalender', 'Mehr'],
    'ohne Chat-Leserecht verschwindet der Tab — der Router-Guard hätte sonst auf den Start geworfen')
  assert.ok(!ohneChat.some(t => t.href === '#/nachrichten'))

  // Die übrigen Tabs hängen an KEINEM Modul (unverändert sichtbar).
  const alle = fusstabs({ istGast: false, module: [] })
  assert.deepEqual(alle.map(t => t.href), ['#/', '#/gruppen', '#/kalender', ''])

  // Gäste: Modul hin oder her — Start und Kalender (N5, unverändert); „Mehr“
  // zeigt ihnen die Schublade mit ihrer eigenen Seitenleiste.
  assert.deepEqual(fusstabs({ istGast: true, module: ['chat', 'kalender'] }).map(t => t.label),
    ['Start', 'Kalender', 'Mehr'])
})

test('CHAT-R2a-2b · dieselbe Regel wie der Router-Guard `modulChatErlaubt`', () => {
  // Review R1, Punkt 1 MUSS: ohne Modulliste (null / kein Array) ist der Tab
  // NICHT sichtbar — genau wie der Wächter, der den Klick sonst auf den Start
  // zurückwirft (vorher: fail open, der Tab blieb stehen).
  assert.deepEqual(fusstabs({ istGast: false, module: null }).map(t => t.label),
    ['Start', 'Gruppen', 'Kalender', 'Mehr'],
    'fehlende Modulliste → kein Tab')
  assert.ok(!fusstabs({ istGast: false, module: null }).some(t => t.href === '#/nachrichten'),
    'fehlt die Liste, verschwindet „Nachrichten“ (fail closed)')

  // Der Administrator kommt durch — wie im Wächter (`is_admin === true`), auch
  // ohne Modulliste und ohne `chat` in der Liste.
  assert.deepEqual(fusstabs({ istGast: false, istAdmin: true, module: null }).map(t => t.label),
    ['Start', 'Nachrichten', 'Gruppen', 'Kalender', 'Mehr'])
  assert.deepEqual(fusstabs({ istGast: false, istAdmin: true, module: ['kalender'] }).map(t => t.label),
    ['Start', 'Nachrichten', 'Gruppen', 'Kalender', 'Mehr'])

  // Fail closed: nur ein echtes `true` zählt (wie `modulChatErlaubt`).
  assert.ok(!fusstabs({ istGast: false, istAdmin: 'true', module: null })
    .some(t => t.href === '#/nachrichten'), 'is_admin als Zeichenkette zählt nicht')

  // Ohne Angabe gilt das Boot-Objekt — dieselben Felder wie im Wächter.
  assert.ok(fusstabs({ istGast: false, boot: { is_admin: true } })
    .some(t => t.href === '#/nachrichten'))
  assert.ok(!fusstabs({ istGast: false, boot: {} })
    .some(t => t.href === '#/nachrichten'))
})

test('CHAT-R2a-2b · der Tab fragt die EINE Regel (kein Nachbau)', () => {
  // Review R1: die Logik wird wiederverwendet, nicht kopiert. Sie steht in
  // `modulRechte.mjs` (DOM-frei), der Router exportiert sie weiter — der
  // Wächter und die Leiste rufen DIESELBE Funktion.
  const quelle = lies('components/fusstabs.mjs')
  assert.match(quelle, /import \{ modulChatErlaubt as modulChatErlaubtRouter \} from '\.\.\/modulRechte\.mjs'/,
    'die Regel wird geholt')
  assert.match(quelle, /modulChatErlaubtRouter\(\{/, 'und dort aufgerufen')
  // Kein zweiter Nachbau der Bedingungen in der Leiste.
  const ohneKommentar = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.ok(!/\.includes\(['"]chat['"]\)/.test(ohneKommentar),
    'die Leiste prüft `chat` nicht selbst')
  assert.match(lies('router.js'), /import \{ modulChatErlaubt \} from '\.\/modulRechte\.mjs'\n\nexport \{ modulChatErlaubt \}/,
    'der Router bindet dieselbe Funktion und gibt sie weiter (Guard + bisherige Tests)')

  // Gemessen an der echten Funktion: Leiste und Wächter stimmen in jeder Lage
  // überein — auch dort, wo die alte Fassung der Leiste fail open war.
  for (const lage of [
    { is_admin: true, module_sichtbar: null },
    { is_admin: true, module_sichtbar: ['kalender'] },
    { is_admin: false, module_sichtbar: null },
    { is_admin: false, module_sichtbar: [] },
    { is_admin: false, module_sichtbar: ['chat'] },
    { is_admin: false, module_sichtbar: ['kalender'] },
    { is_admin: 'true', module_sichtbar: null },
    {},
  ]) {
    const erwartet = modulChatErlaubt(lage)
    const tab = fusstabs({
      istGast: false,
      istAdmin: lage.is_admin === true,
      module: Array.isArray(lage.module_sichtbar) ? lage.module_sichtbar : null,
    }).some(t => t.href === '#/nachrichten')
    assert.equal(tab, erwartet, `Leiste und Wächter stimmen überein (${JSON.stringify(lage)})`)
  }
})

test('CHAT-R2a-2b · dieselbe Regel wie `sichtbareEintraege` (EINE Quelle)', () => {
  // Der Menüeintrag und der Tab verschwinden zusammen — sonst zeigte die
  // Leiste ein Ziel, das die Seitenleiste versteckt.
  const gemeinde = MENUE.find(g => g.gruppe === 'Gemeinde')
  const menueOhne = gemeinde.eintraege.filter(e => !e.modul || ['kalender'].includes(e.modul))
  const tabOhne = fusstabs({ istGast: false, module: ['kalender'] })
  assert.deepEqual(menueOhne.map(e => e.id), ['gruppen'])
  assert.ok(!tabOhne.some(t => t.href === '#/nachrichten'))
})

test('CHAT-R2a-2b · AppBottomNav reicht die Modulliste der Sitzung durch', () => {
  const quelle = lies('components/AppBottomNav.vue')
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  assert.match(skript, /window\.__DIakonosBOOT\?\.module_sichtbar/, 'die Serverliste wird gelesen')
  assert.match(skript, /fusstabs\(\{\s*istGast: isGast\.value,\s*istAdmin: isAdmin\.value === true,\s*module: module\.value,?\s*\}\)/,
    'die Leiste fragt mit derselben Liste und demselben Admin-Recht')
  // Der Kommentar in fusstabs.mjs nennt den Grund (Review-Befund b).
  assert.match(lies('components/fusstabs.mjs'), /Sackgasse/,
    'der Kommentar erklärt die Sackgasse, die der Filter schließt')
})

// ══════════════════════════════════════════════════════════════════════════════
// c) Fenstertitel: „Personenverwaltung“
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2c · alle Personen-Seiten tragen den Titel „Personenverwaltung“', () => {
  for (const seite of ['Personen', 'MitgliederListe', 'MitgliederAnfragen', 'MitgliederDatenschutz',
    'MitgliederImport', 'MitgliederUebersicht', 'MitgliederLoeschantraege']) {
    assert.equal(SEITENTITEL_NICHT_IM_MENUE[seite], 'Personenverwaltung', `${seite}: Titel`)
  }
  // Der fertige Titel (mit Gemeindename) — gemessen, nicht nur die Tabelle.
  assert.equal(baueTitel('MitgliederAnfragen', null, { __DIakonosBOOT: { church_name: 'St. Test' } }),
    'Personenverwaltung – St. Test')
  // Ein anderer Bereich bleibt, was er ist.
  assert.equal(SEITENTITEL_NICHT_IM_MENUE.MitgliedDetail, 'Mitglied')
})

// ══════════════════════════════════════════════════════════════════════════════
// d) Anfragen-Zähler am Einstellungen-Eintrag
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2d · `badge: \'anfragen\'` liegt am Einstellungen-Eintrag', () => {
  const einstellungen = FUSS_EINTRAEGE.find(e => e.id === 'einstellungen')
  assert.ok(einstellungen, 'der Fuß-Eintrag existiert')
  assert.equal(einstellungen.badge, 'anfragen', 'offene Registrierungsanfragen bleiben sichtbar')
  // Kein zweiter Träger der Kennzahl (eine Zahl, ein Ort).
  const badgeTraeger = [...GRUPPEN_EINTRAEGE, ...FUSS_EINTRAEGE].filter(e => e.badge === 'anfragen')
  assert.deepEqual(badgeTraeger.map(e => e.id), ['einstellungen'])
})

test('CHAT-R2a-2d · Schublade bekommt die Zahl von App.vue', () => {
  // Review R1, Punkt 2: `anfragenZahl` war als Prop deklariert, aber nie
  // übergeben — am Handy blieb der Zähler immer leer.
  const app = ohneKommentare(lies('App.vue'))
  assert.match(app, /:anfragen-zahl="anfragenZahl"/, 'App.vue reicht die Zahl an die Schublade')
  // Die Zahl kommt aus dem GEMEINSAMEN Stand (useVerwaltung), nicht aus einer
  // zweiten Abfrage — und die App führt den Takt, damit auch die Schublade
  // allein (ohne Seitenleiste) aktuell bleibt.
  assert.match(app, /import \{ anfragenZaehler, anfragenZaehlerBeobachten \} from '\.\/composables\/useVerwaltung\.js'/)
  assert.match(app, /const anfragenZahl = anfragenZaehler/)
  assert.match(app, /anfragenAbmelden = anfragenZaehlerBeobachten\(\)/, 'ein Beobachter an der Wurzel')
  assert.match(app, /if \(anfragenAbmelden\) anfragenAbmelden\(\)/, 'und wieder abgemeldet')

  // Gemessen: die Zahl der Schublade hängt an diesem Prop (nicht an einer
  // zweiten Quelle). Die Regel steht in der SFC — hier am Quelltext geprüft,
  // weil `badgeFuer` im `<script setup>` liegt.
  const schublade = ohneKommentare(lies('components/AppMenueSchublade.vue'))
  assert.match(schublade, /anfragenZahl: \{ type: \[Number, null\], default: null \}/)
  assert.match(schublade, /if \(e\.badge === 'anfragen' && props\.anfragenZahl > 0\) return props\.anfragenZahl/)
})

test('CHAT-R2a-2d · Seitenleiste UND Schublade zeichnen die Kennzahl am Fuß-Eintrag', () => {
  const seite = ohneKommentare(lies('components/AppSidebar.vue'))
  // Vorher stand hier `:badge="null"` — die Zahl des entfallenen
  // Personen-Eintrags wäre damit nirgends mehr aufgetaucht.
  const fussBlock = seite.slice(seite.indexOf('dk-sb-foot'), seite.indexOf('dk-sb-profil'))
  assert.match(fussBlock, /:badge="badgeFuer\(e\)"/, 'die Seitenleiste fragt die Kennzahl ab')
  assert.match(seite, /if \(eintrag\.badge === 'anfragen' && zaehler\.value > 0\) return zaehler\.value/)

  const schublade = ohneKommentare(lies('components/AppMenueSchublade.vue'))
  const fussListe = schublade.slice(schublade.indexOf('dk-schublade-fussliste'), schublade.indexOf('</nav>'))
  assert.match(fussListe, /v-if="badgeFuer\(e\)"[\s\S]*?dk-schublade-zaehler/,
    'die Schublade zeigt die Zahl ebenfalls am Fuß-Eintrag')
})

// ══════════════════════════════════════════════════════════════════════════════
// e) Befehlspalette
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2e · „Person anlegen“ zielt auf die Personenverwaltung in den Einstellungen', () => {
  const aktionen = aktionsEintraege({ darfPerson: true })
  assert.deepEqual(aktionen.map(a => a.titel), ['Person anlegen'])
  assert.equal(aktionen[0].ziel, `${PERSONENVERWALTUNG_BASIS}?anlegen=1`)
  // Das Ziel öffnet wirklich den Dialog: Personen.vue liest denselben Schalter
  // — eingebettet wie als eigene Seite.
  const personen = lies('pages/Personen.vue')
  assert.match(personen, /werte\.get\('anlegen'\)/, 'Personen.vue liest den Schalter')
  assert.match(personen, /if \(!darfVerwalten\.value\) return/, 'ohne Recht kein Dialog')
  // Der Router kennt die Zielseite (sonst „Seite nicht gefunden“).
  assert.match(lies('router.js'), /'#\/einstellungen\/personenverwaltung': 'EinstellungenPersonenverwaltung'/)
})

test('CHAT-R2a-2e · „pers“ findet die Personenverwaltung', () => {
  // 1) Lokal über den Seiten-Eintrag der Palette (der Bereich ist ein
  //    Abschnitt der Einstellungen — der Abschnitt selbst ist ein Server-
  //    Treffer, aber die Palette filtert Seiten auch lokal).
  assert.equal(passtZu('pers', 'Personenverwaltung'), true)
  // 2) Review R1, Punkt 3: der LOKALE Eintrag „Personenverwaltung“ mit
  //    demselben Gating wie jeder Personen-Eintrag (`verwaltung: 'personen'`).
  //    Ein Mitgliederverwalter OHNE Admin findet ihn damit — der Server würde
  //    ihn ihm zwar auch liefern, aber die Palette soll ihn sofort zeigen.
  const mitglied = { istAdmin: false, istMitgliederverwaltung: true }
  const lokal = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: mitglied })
  const eintrag = lokal.find(z => z.titel === 'Personenverwaltung')
  assert.ok(eintrag, 'die Personenverwaltung steht als Seiten-Eintrag in der Palette')
  assert.equal(eintrag.ziel, PERSONENVERWALTUNG_BASIS)
  assert.equal(eintrag.ort, 'Einstellungen')
  // „pers“ trifft sie — ohne Server-Antwort, nur aus den lokalen Seiten.
  const zeilen = paletteZeilen({ begriff: 'pers', seiten: lokal, aktionen: [], treffer: [] })
  assert.ok(zeilen.zeilen.some(z => z.titel === 'Personenverwaltung' && z.ziel === PERSONENVERWALTUNG_BASIS),
    '„pers“ zeigt die Personenverwaltung')

  // Gating: ohne Personenrecht kein Eintrag (fail closed), Gäste ebenso.
  const ohneRecht = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: {} })
  assert.ok(!ohneRecht.some(z => z.titel === 'Personenverwaltung'), 'ohne Recht kein Eintrag')
  const gast = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege,
    rechte: { istGast: true, istAdmin: true, istMitgliederverwaltung: true } })
  assert.ok(!gast.some(z => z.titel === 'Personenverwaltung'), 'Gäste sehen den Bereich nicht')
  // Der Administrator sieht ihn (er ist in `personen` enthalten).
  const admin = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege,
    rechte: { istAdmin: true, istMitgliederverwaltung: true } })
  assert.ok(admin.some(z => z.titel === 'Personenverwaltung'))

  // 3) Die Palette baut aus Server-Treffern der Art `einstellung` eine
  //    Seiten-Zeile mit diesem Ziel (gemessen, nicht behauptet) — und
  //    entdoppelt gegen den lokalen Eintrag (eine Zeile, ein Ziel).
  const zeilenServer = paletteZeilen({
    begriff: 'pers',
    seiten: lokal,
    aktionen: [],
    treffer: [{
      id: 'einstellung:#/einstellungen/personenverwaltung:Personenverwaltung',
      abschnitt: 'seiten', titel: 'Personenverwaltung', ort: 'Einstellungen',
      ziel: '#/einstellungen/personenverwaltung', symbol: 'notiz', gruppe: '',
    }],
  })
  const treffer = zeilenServer.zeilen.filter(z => z.ziel === PERSONENVERWALTUNG_BASIS)
  assert.equal(treffer.length, 1, 'eine Zeile je Ziel — lokaler Name gilt')
  assert.equal(treffer[0].titel, 'Personenverwaltung')
})

// Seiten-Einträge und Palette: importiert oben.

// ══════════════════════════════════════════════════════════════════════════════
// f) Brotkrumen und Seitenleisten-Markierung
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-R2a-2f · alle Personen-Reiter tragen EINE Brotkrume', () => {
  const topbar = ohneKommentare(lies('components/AppTopbar.vue'))
  for (const seite of ['Personen', 'MitgliederListe', 'MitgliederUebersicht', 'MitgliederAnfragen',
    'MitgliederDatenschutz', 'MitgliederImport', 'MitgliederLoeschantraege',
    'EinstellungenPersonenverwaltung']) {
    assert.match(topbar, new RegExp(`${seite}:\\s*\\['Einstellungen', 'Personenverwaltung'\\]`),
      `${seite}: Brotkrume „Einstellungen › Personenverwaltung“`)
  }
  // Kein abweichender Untertitel mehr für dieselbe Ebene (Review-Befund).
  assert.ok(!topbar.includes("'Personenverwaltung', 'Löschanträge'"),
    'kein eigener dritter Krümel für einen Personen-Reiter')
})

test('CHAT-R2a-2f · die alten Personen-Seiten markieren den Einstellungen-Eintrag', () => {
  for (const seite of ['Personen', 'MitgliederListe', 'MitgliederUebersicht', 'MitgliederAnfragen',
    'MitgliederDatenschutz', 'MitgliederImport', 'MitgliederLoeschantraege',
    'EinstellungenPersonenverwaltung']) {
    const treffer = eintragZuSeite(seite)
    assert.ok(treffer, `${seite}: ein Eintrag markiert die Seite`)
    assert.equal(treffer.eintrag.id, 'einstellungen', `${seite} → Seitenleiste markiert „Einstellungen“`)
    assert.deepEqual(krumenZuSeite(seite), ['Einstellungen'], 'Krumen-Fallback nennt den Ort')
  }
  // Kein zweiter Menüeintrag für den Personenbereich.
  assert.ok(!GRUPPEN_EINTRAEGE.some(e => e.id === 'personen'))
  // Das Personenprofil bleibt sein eigener Ort (10.2, Tabelle).
  assert.equal(eintragZuSeite('MitgliedDetail'), null)
})

test('CHAT-R2a-2 · die Fußleiste: vier Bereiche plus „Mehr“ (CHAT-3a löst die alte Regel ab)', () => {
  // ANGEPASST (CHAT-3a, Chat-Konzept 10.1/10.2, von Manuel am 17.11. mit den
  // Entwürfen freigegeben): Der fünfte Platz heißt „Mehr“ und öffnet die
  // bestehende Menü-Schublade. Die Regel „kein Mehr in der Leiste“ vom 03.11.
  // ist damit abgelöst — nicht gelöscht, sondern durch die neuere Entscheidung
  // ersetzt. Vier BEREICHE bleiben es trotzdem (Mehr ist kein Bereich).
  assert.equal(FUSSTAB_TABS.length, 5, 'fünf Plätze (N5)')
  const mehr = FUSSTAB_TABS.filter(t => /mehr/i.test(t.label))
  assert.equal(mehr.length, 1, 'genau EIN „Mehr“-Platz')
  assert.equal(mehr[0].schublade, true, '„Mehr“ öffnet die Schublade, es verlinkt nichts')
  assert.equal(mehr[0].href, '')
  assert.equal(FUSSTAB_TABS.filter(t => !t.schublade).length, 4, 'vier echte Ziele')
  assert.deepEqual(MITGLIEDER_REITER.map(r => r.label), ['Liste', 'Anfragen', 'Datenschutz', 'Import'],
    'die vier Personen-Reiter bleiben unverändert')
})

test('CHAT-R2a-2 · diese Datei steht in der Testliste des Baus (FE-TEST-1)', () => {
  const liste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8')
  assert.match(liste, /^tests\/chat-r2a-2-.*\.test\.mjs$/m, 'das Muster ist eingetragen')
})
