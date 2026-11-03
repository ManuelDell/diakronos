// BS-1b2 — Vertragstest der Nachbesserung an der öffentlichen Lese-API.
//
// Der Schwestertest `bs1b-website-oeffentlich.test.mjs` hält fest, WAS die
// Lese-API liefert. Dieser Test hält fest, dass die vier Reparaturen aus dem
// Review nicht wieder herausfallen — er liest den Quelltext, weil die
// jeweilige Regel an einer bestimmten Stelle stehen MUSS:
//
//   F1  Der Link-Typ wird geprüft (`TYPG_GAST`) — ein Mitglieds-Registrierungs-
//       link darf nie als `anmeldung_url` erscheinen.
//   F2  Kein N+1: Gruppen/Links über `IN (…)`, die Gemeinde-Adresse EINMAL je
//       Aufruf.
//   F4  iCal: keine Leerzeilen im Dokument, DTEND exklusiv, DTSTAMP aus
//       `modified`.
//   F6  `Vary: Origin` auch auf der iCal- und der Bild-Antwort.
//   F7  `docstatus != 2` im SQL-Filter, kein festes Salz, keine nackten
//       Registernamen.
//   F8  Der Kommentar in `auth_middleware` nennt den Pfad außerhalb `/api/`.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const PKT = join(REPO, 'backend', 'src', 'diakronos_app', 'website')
const API = join(PKT, 'oeffentlich_api.py')
const AUSWAHL = join(PKT, 'oeffentlich_auswahl.py')
const DATEN = join(PKT, 'oeffentlich_daten.py')
const INHALT = join(PKT, 'oeffentlich_inhalt.py')
const REGISTRY = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'registry.py')
const MW = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'auth_middleware.py')
const LINK = join(REPO, 'backend', 'src', 'diakronos_app', 'anmeldung', 'registrierungslink.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('BS-1b2/F1: anmeldung_url prüft den Link-Typ (nur Gast-Anmeldung)', () => {
  const quelle = lies(DATEN)
  assert.match(quelle, /TYPG_GAST/, 'der Link-Typ wird nicht gegen TYPG_GAST geprüft')
  assert.match(
    quelle,
    /str\(link\.typ or ""\) != str\(TYPG_GAST\)/,
    'der Vergleich mit dem Gast-Typ fehlt',
  )
})

test('BS-1b2/F2: kein N+1 — Gruppen/Links als IN-Abfrage, Basis einmal', () => {
  const quelle = lies(DATEN)
  assert.match(quelle, /def _anmeldung_links/, 'Sammel-Abfrage für Links fehlt')
  assert.match(quelle, /def _oeffentliche_gruppen/, 'Sammel-Abfrage für Gruppen fehlt')
  assert.match(quelle, /Registrierungslink\.name\.in_\(/, 'Links nicht als IN-Abfrage')
  assert.match(quelle, /Gruppe\.name\.in_\(/, 'Gruppen nicht als IN-Abfrage')
  // Die Gruppen-Adresse wird EINMAL je Aufruf gelesen, nicht je Link.
  assert.match(quelle, /basis = _oeffentliche_basis\(sess\)/, 'Basis nicht vor der Schleife')
  // In `termine()` steht keine Einzel-Abfrage je Zeile mehr.
  const termine = quelle.slice(quelle.indexOf('def termine('))
  const rumpf = termine.slice(0, termine.indexOf('\ndef '))
  assert.ok(
    !/_oeffentliche_gruppe\(sess, zeile\.get\("gruppe"\)\)/.test(rumpf),
    'termine() fragt die Gruppe noch je Zeile ab',
  )
  assert.ok(
    !/_anmeldung_url\(sess, zeile\)/.test(rumpf),
    'termine() fragt den Anmeldelink noch je Zeile ab',
  )
})

test('BS-1b2/F2: die Basis wird über link_anzeige gebaut (Vertrag bleibt)', () => {
  // `link_anzeige` ist die EINE Stelle für die Anmelde-Adresse; Kopieren der
  // Pfadlogik würde Präfix und Gemeinde-Adresse auseinanderlaufen lassen.
  const quelle = lies(DATEN)
  assert.match(quelle, /from diakronos_app\.anmeldung\.registrierungslink import link_anzeige/)
  const link = lies(LINK)
  assert.match(link, /def link_anzeige\(typ, slug, session=None, basis: str \| None = None\)/)
  assert.match(link, /def oeffentliche_basis\(session=None\)/)
})

test('BS-1b2/F4: iCal — DTEND exklusiv, DTSTAMP aus modified, keine Leerzeilen', () => {
  const quelle = lies(INHALT)
  // Leerzeilen: der Rumpf kennt kein `+ [""]` und kein `append("")` mehr.
  const kalender = quelle.slice(quelle.indexOf('def kalender_ics('))
  assert.ok(!/\[\s*""\s*\]/.test(kalender), 'das VCALENDAR baut noch eine Leerzeile ein')
  assert.ok(!/\.append\(""\)/.test(kalender), 'das VCALENDAR hängt noch eine Leerzeile an')
  // DTEND bei Ganztagsterminen kommt aus dem gespeicherten Ende.
  assert.match(quelle, /def _ohne_eine_tagesspanne/, 'DTEND-Regel fehlt')
  // DTSTAMP: `stand` (aus `modified`), nicht `jetzt`.
  assert.match(quelle, /zeile\.get\('stand'\)|zeile\.get\("stand"\)/)
  // Die Zeile der Daten-Schicht trägt `modified`.
  assert.match(lies(DATEN), /"modified": zeile\.modified/)
})

test('BS-1b2/F4: Steuerzeichen werden entfernt (nicht nur \\r\\n ersetzt)', () => {
  const quelle = lies(INHALT)
  const escape = quelle.slice(quelle.indexOf('def _escape_i('))
  const rumpf = escape.slice(0, escape.indexOf('\ndef '))
  assert.match(rumpf, /ord\(zeichen\) >= 0x20/, 'die Steuerzeichen-Filterung fehlt')
})

test('BS-1b2/F6: Vary: Origin auch auf iCal und Bild', () => {
  const quelle = lies(API)
  const ical = quelle.slice(quelle.indexOf('def ical_route('))
  const bild = quelle.slice(quelle.indexOf('def bild_route('))
  assert.match(ical.slice(0, 2500), /ORIGIN_HEADER\] = "Origin"/, 'Vary fehlt im iCal')
  assert.match(bild.slice(0, 2500), /ORIGIN_HEADER\] = "Origin"/, 'Vary fehlt im Bild')
})

test('BS-1b2/F3: die Bild-Route prüft über freigegebene_gruppe', () => {
  const quelle = lies(API)
  const bild = quelle.slice(quelle.indexOf('def _oeffentliches_bild('))
  const rumpf = bild.slice(0, bild.indexOf('\ndef bild_route('))
  assert.match(
    rumpf,
    /freigegebene_gruppe\(sess, kennung\)/,
    'die Bild-Route prüft die Gruppe nicht über die gemeinsame Freigabe',
  )
})

test('BS-1b2/F7: docstatus != 2 im SQL-Filter', () => {
  const quelle = lies(DATEN)
  assert.match(quelle, /Element\.docstatus != 2/, 'gelöschte Termine bleiben im SQL-Filter drin')
})

test('BS-1b2/F7: kein festes Salz, kein Rückfall auf den internen Namen', () => {
  const quelle = lies(AUSWAHL)
  assert.ok(
    !/"diakronos-website"/.test(quelle),
    'das alte feste Salz steht noch im Code',
  )
  assert.match(quelle, /secrets\.token_hex/, 'das Prozesssalz wird nicht zufällig gezogen')
  assert.match(quelle, /def _prozesssalz\(\)/)
})

test('BS-1b2/F7: keine nackten Registernamen der Lese-API', () => {
  const quelle = lies(API)
  assert.match(
    quelle,
    /nackte_namen_entfernen\(_funktionen\(\)\)/,
    'die nackten Registernamen werden nicht entfernt',
  )
  const registry = lies(REGISTRY)
  assert.match(registry, /def nackte_namen_entfernen/)
  // Entfernt werden nur Einträge OHNE Punkt (nackte Namen).
  assert.match(registry, /if "\.\." not in key|if "\." not in key/)
})

test('BS-1b2/F8: der Kommentar nennt den Pfad außerhalb von /api/', () => {
  const quelle = lies(MW)
  assert.match(quelle, /\/website\/oeffentlich\//, 'der Pfad fehlt im Kommentar')
  assert.ok(
    !/`website\.oeffentlich\.\*` steht als eigener/.test(quelle),
    'der alte, falsche Kommentar steht noch da',
  )
  // BS-1bc (Querfix): die sechs öFFENTLICHEN LESE-Endpunkte stehen NICHT in
  // der Ausnahmemenge. Die Postfach-Liste (BS-1c2) ist bewusst drin — sie
  // braucht die Ausnahme für die Primo-Herkunft.
  const menge = quelle.slice(quelle.indexOf('_OEFFENTLICHE_WEBSITE_NAMEN = frozenset'))
  const block = menge.slice(0, menge.indexOf('})'))
  for (const name of [
    'website.oeffentlich.kalender',
    'website.oeffentlich.termine',
    'website.oeffentlich.naechster_termin',
    'website.oeffentlich.gruppen',
    'website.oeffentlich.gruppe',
    'website.oeffentlich.beitraege',
  ]) {
    assert.ok(!block.includes(name), `Lese-Endpunkt steht in der Ausnahmemenge: ${name}`)
  }
  assert.ok(
    !/(?<![\w.])oeffentlich\.[a-z_]+/.test(block.replace(/postfaecher/g, '')),
    'ein Lese-Endpunkt steht in der Ausnahmemenge',
  )
})
