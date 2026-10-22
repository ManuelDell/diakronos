/**
 * DSGVO-2d — Frontend-Darstellung „Gelöschte Person“.
 *
 * Geprüft wird die reine Regel (`composables/geloeschte-person.mjs`) und ihre
 * Verwendung an den Stellen, die den Namen selbst bauen:
 *
 *  * `anzeigename.mjs` — Begrüssung und Avatar. Vor dem Fix stand hier die
 *    neutrale Kennung `geloescht-9f3a` als „Vorname“ (`fullname` war der
 *    erste Namensteil), und der Avatar zeigte „GE“.
 *  * `datenschutz.mjs` — die DSGVO-Liste (Name je Zeile).
 *  * Die Seiten (Adressbuch, Mitgliederliste, Gruppe, Datenschutz) dürfen für
 *    eine gelöschte Person KEINEN Profil-Link mehr setzen — der führte auf
 *    eine Fehlerseite.
 *  * Auswahllisten bieten sie nicht an (Server filtert; der Prädikatstest
 *    hält die Regel bereit).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  GELOESCHT_ANZEIGE, istGeloescht, personenName, darfProfilLink,
  personenKuerzel,
} from '../src/diakonos/composables/geloeschte-person.mjs'
import { anzeigename, ersterName, initialen } from '../src/diakonos/composables/anzeigename.mjs'
import { personenAnzeige } from '../src/diakonos/components/mitglieder/datenschutz.mjs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')

const TOT = 'geloescht-9f3a'
const TOT_ZEILE = {
  name: TOT, vorname: 'Gelöschte', nachname: 'Person', status: 'geloescht',
}
// Rest-Name aus einem alten Sicherungsstand: Status/Kennung entscheiden.
const TOT_REST = {
  name: TOT, vorname: 'Elvira', nachname: 'Dorn', status: 'geloescht',
}

test('DSGVO-2d · Anzeigetext ist überall derselbe Satz', () => {
  assert.equal(GELOESCHT_ANZEIGE, 'Gelöschte Person')
  assert.equal(personenName(TOT_ZEILE), GELOESCHT_ANZEIGE)
  assert.equal(personenName(TOT_REST), GELOESCHT_ANZEIGE)
  assert.equal(personenName(TOT), GELOESCHT_ANZEIGE)
  assert.equal(personenAnzeige(TOT_REST), GELOESCHT_ANZEIGE)
})

test('DSGVO-2d · Status „geloescht“ und Kennung „geloescht-…“ zählen beide', () => {
  assert.ok(istGeloescht({ status: 'geloescht' }))
  assert.ok(istGeloescht({ status: ' GELOESCHT ' }))
  assert.ok(istGeloescht(TOT))
  assert.ok(istGeloescht({ name: TOT }))
  assert.ok(istGeloescht({ mitglied: TOT }))
  assert.ok(!istGeloescht({ name: 'M-0001', status: 'Mitglied' }))
  assert.ok(!istGeloescht({ name: 'M-0002', status: 'Ausgetreten' }))
  assert.ok(!istGeloescht(null) && !istGeloescht(''))
})

test('DSGVO-2d · Begrüssung zeigt nie die Kennung `geloescht-…`', () => {
  // Vor dem Fix: `ersterName('geloescht-9f3a')` === 'geloescht-9f3a'.
  assert.equal(anzeigename(null, TOT), GELOESCHT_ANZEIGE)
  assert.equal(anzeigename(null, `${TOT} Gelöschte`), GELOESCHT_ANZEIGE)
  assert.equal(anzeigename(TOT_ZEILE, TOT), GELOESCHT_ANZEIGE)
  assert.ok(!anzeigename(TOT_ZEILE, TOT).includes('geloescht-'))
  // Gegenprobe: normale Namen bleiben wie bisher.
  assert.equal(anzeigename({ vorname: 'Lea', nachname: 'Sommer' }, 'mitglied'), 'Lea')
  assert.equal(ersterName('geloescht-9f3a'), 'geloescht-9f3a', 'die reine Funktion bleibt neutral')
})

test('DSGVO-2d · Avatar einer gelöschten Person zeigt kein „GE“ aus der Kennung', () => {
  assert.equal(initialen(TOT_ZEILE, TOT), 'U')
  assert.equal(initialen(null, TOT), 'U')
  assert.equal(initialen(null, 'Jonas Berger'), 'JB', 'Gegenprobe: normaler Name')
})

test('DSGVO-2d · kein Profil-Link, kein Kürzel, keine leeren Klammern', () => {
  assert.equal(darfProfilLink(TOT_ZEILE), false)
  assert.equal(darfProfilLink({ name: 'M-0001', status: 'Mitglied' }), true)
  assert.equal(darfProfilLink({ name: '', status: 'Mitglied' }), false)
  assert.equal(personenKuerzel(TOT_REST), '')
  assert.equal(personenKuerzel({ name: 'M-0001', kuerzel: 'E. D.' }), 'E. D.')
  // Kein Aushängeschild für die Kennung, wenn sonst nichts da ist.
  assert.equal(personenName({ name: 'person@example.org' }), 'Ehemaliges Mitglied')
  assert.equal(personenName({ name: 'M-0001', vorname: 'Lea', nachname: 'Sommer' }), 'Lea Sommer')
})

test('DSGVO-2d · Gruppenzeile: Kennung in `mitglied`, Anzeigename in `name`', () => {
  // Gestalt der Gruppen-/Kalenderantwort: `mitglied` = Kennung (hier die
  // neutrale), `name` = Anzeigename („Gelöschte Person“). Der Link hing
  // vorher an `m.mitglied` und führte deshalb ins Leere.
  const zeile = { mitglied: TOT, name: GELOESCHT_ANZEIGE, status: 'Aktiv' }
  assert.equal(darfProfilLink(zeile), false)
  assert.equal(istGeloescht(zeile), true, 'die Kennung allein genügt')
  assert.equal(personenName(zeile), GELOESCHT_ANZEIGE)
  // Gegenprobe: eine lebende Zeile bleibt verlinkbar, eine leere nie.
  assert.equal(darfProfilLink({ mitglied: 'Timo Keller', name: 'Timo Keller' }), true)
  assert.equal(darfProfilLink({ mitglied: '', name: '' }), false)
})

test('DSGVO-2d · Avatar einer gelöschten Person zeigt kein „GP“', () => {
  const quelle = lies('pages/Mitglieder.vue')
  assert.match(quelle, /if \(istGeloescht\(String\(name\)\)\) return 'U'/)
  assert.match(quelle, /import \{ darfProfilLink, istGeloescht \}/)
  // Die Seite hat in der Karte nur `full_name` — der fertige Anzeigetext
  // selbst muss als „gelöscht“ erkannt werden (sonst „GP“ aus dem Platzhalter).
  assert.equal(istGeloescht(GELOESCHT_ANZEIGE), true)
  assert.equal(initialen({ vorname: 'Gelöschte', nachname: 'Person' }, GELOESCHT_ANZEIGE), 'U')
})

test('DSGVO-2d · Adressbuch setzt keinen Profil-Link für Gelöschte', () => {
  const quelle = lies('pages/Adressbuch.vue')
  assert.match(quelle, /v-if="darfProfilLink\(m\)"/, 'Link hängt am Prädikat')
  assert.match(quelle, /import \{ darfProfilLink \} from '\.\.\/composables\/geloeschte-person\.mjs'/)
  // Beide Ansichten (Karte + Tabelle) sind versorgt.
  assert.ok((quelle.match(/darfProfilLink\(m\)/g) || []).length >= 3)
})

test('DSGVO-2d · Mitgliederliste verlinkt Gelöschte nicht ins Profil', () => {
  const quelle = lies('pages/Mitglieder.vue')
  assert.match(quelle, /import \{ darfProfilLink, istGeloescht \} from '\.\.\/composables\/geloeschte-person\.mjs'/)
  // Karte: Linkform bleibt (DES-R5), aber ohne Ziel/Tabstopp und mit
  // abgefangenem Klick — das Profil einer gelöschten Person gibt es nicht.
  assert.match(quelle, /:href="'#\/mitglied\/' \+ m\.name"/)
  assert.match(quelle, /v-bind="ohneProfilZiel\(m\)"/)
  assert.match(quelle, /function ohneProfilZiel\(m\) \{\n  return darfProfilLink\(m\) \? \{\} : \{ href: '#' \}/)
  assert.match(quelle, /:aria-disabled="darfProfilLink\(m\) \? null : 'true'"/)
  assert.match(quelle, /:tabindex="darfProfilLink\(m\) \? null : -1"/)
  assert.match(quelle, /@click="profilOeffnen\(\$event, m\)"/)
  assert.match(quelle, /function profilOeffnen\(ereignis, m\) \{\n  if \(darfProfilLink\(m\)\) return\n  ereignis\.preventDefault\(\)/)
  assert.match(quelle, /\.dk-member-card--ohne-profil \{ cursor: default; \}/)
  // Tabelle: Zeile ohne Link, mit Begründung statt leerer Stelle.
  assert.match(quelle, /<a v-if="darfProfilLink\(m\)" class="dk-cell-person/)
  assert.match(quelle, /Kein Profil mehr vorhanden/)
})

test('DSGVO-2d · Mitgliederliste: Filter „geloescht“ wird nicht still zu „Alle“', () => {
  const quelle = lies('pages/Mitglieder.vue')
  // Vor dem Fix fiel ein unbekannter Status in `_statusAusAdresse` auf ''
  // zurück — `#/mitglieder/liste?status=geloescht` zeigte damit ALLE Zeilen.
  assert.match(quelle, /const MT_GELOESCHT = 'geloescht'/)
  assert.match(quelle, /MT_STATUS\.push\(MT_GELOESCHT\)/)
  assert.match(quelle, /return MT_STATUS\.includes\(wert\) \? wert : ''/)
  // Chip nur, wenn es solche Zeilen gibt, mit verständlichem Wort.
  assert.match(quelle, /const MT_STATUS_WORT = \{ \[MT_GELOESCHT\]: 'Gelöschte Person' \}/)
  assert.match(quelle, /\.filter\(s => s !== MT_GELOESCHT \|\| \(statusZaehler\.value\[s\] \?\? 0\) > 0\)/)
  // Kennzeichen und Chip zeigen Deutsch statt des Speicherwerts.
  assert.match(quelle, /const statusText|function statusText\(s\) \{\n  if \(!s\) return 'Unbekannt'\n  return MT_STATUS_WORT\[s\] \|\| s/)
})

test('DSGVO-2d · Gruppe verlinkt Gelöschte nicht ins Profil', () => {
  const quelle = lies('pages/GruppeDetail.vue')
  assert.match(quelle, /import \{ darfProfilLink \} from '\.\.\/composables\/geloeschte-person\.mjs'/)
  assert.match(quelle, /darfProfilLink\(m\) && m\.mitglied/)
})

test('DSGVO-2d · DSGVO-Seite: Gelöschte ohne Link, ohne „Anonymisieren“', () => {
  const quelle = lies('pages/mitglieder/Datenschutz.vue')
  assert.match(quelle, /const name = personenAnzeige/)
  assert.match(quelle, /v-if="!m\.geloescht"/)
  assert.match(quelle, /<div v-if="!m\.geloescht" class="ds-aktionen">/)
})

test('DSGVO-2d · Plan-Rahmen zeigt keine nackte Kennung in der Zelle', () => {
  const quelle = lies('composables/usePlanrahmen.js')
  assert.match(quelle, /import \{ GELOESCHT_ANZEIGE, istGeloescht \} from '\.\/geloeschte-person\.mjs'/)
  const fn = quelle.slice(quelle.indexOf('export function nameZeigen'))
  const rumpf = fn.slice(0, fn.indexOf('\n}\n'))
  assert.match(rumpf, /istGeloescht\(kennung\)/, 'Prädikat vor dem Rückfall auf die Kennung')
})
