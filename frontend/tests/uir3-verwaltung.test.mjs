/**
 * UI-R3 — Kalenderverwaltung auf dem EINEN Rechtesystem (reine Logik).
 *
 * Die Oberfläche entscheidet NICHTS über Rechte. Hier stehen die Regeln, die
 * die Seite und die gemeinsame Fläche aus UI-R2 brauchen:
 *
 *   L1  `alleKalenderZeilen`  zeigt JEDEN Kalender der Serverliste mit seiner
 *                             Zuordnung (Gemeinde / Gruppe / Untergruppe).
 *   L2  `verwaltungAnlegeZiele` nennt die Orte aus `anlegen_gruppen` /
 *                             `anlegen_untergruppen`; „Gemeinde“ NUR mit
 *                             `darf_gemeinde_kalender`.
 *   L3  `kalenderVerwaltungSichtbar` ist genau dann true, wenn der Server
 *                             etwas zum Verwalten oder Anlegen liefert.
 *                             (UI-R3b: `hatVerwaltbares` ist entfallen — es
 *                             war dieselbe Regel ein zweites Mal.)
 *   L4  `anlegeAnfrage`       schickt genau die Felder, die `create_kalender`
 *                             erwartet (ein Ziel, Ja/Nein der Anlege-Frage).
 *   L5  Die Seite selbst zeigt KEINE Rollen-Auswahlen mehr (leserechte/
 *                             schreibrechte/moderatoren sind entfernt) und
 *                             bindet die gemeinsame Fläche ein.
 *
 * Lauf: node --test tests/uir3-verwaltung.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import * as modul from '../src/diakonos/components/gruppen/kalenderRechte.mjs'
import {
  KALENDER_ANLEGEN_FRAGE,
  GEMEINDE_TITEL,
  alleKalenderZeilen,
  anlegeAnfrage,
  ausGruppenbaum,
  verwaltungAnlegeZiele,
} from '../src/diakonos/components/gruppen/kalenderRechte.mjs'
import {
  kalenderMenue,
  kalenderVerwaltungSichtbar,
} from '../src/diakonos/components/kronos/kalenderRechte.mjs'

const TESTS = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(resolve(TESTS, '..', 'src', 'diakonos', rel), 'utf8')

/** Die Kalenderliste, wie `get_kalender_verwaltung` sie liefert. */
const KALENDER = [
  { name: 'Gemeinde', titel: 'Gemeindeleben', farbe: '#111111', gruppe: null, untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aktiv', gruppe_status: 'aus', zuordnung: '' },
  { name: 'Proben', titel: 'Proben', farbe: '#222222', gruppe: 'G-Chor', untergruppe: null,
    standard_gruppe_lesen: false, gemeinde_status: 'aus', gruppe_status: 'aus', zuordnung: 'Chor' },
  { name: 'Kinderchor', titel: 'Kinderchor', farbe: '#333333', gruppe: 'G-Chor', untergruppe: 'UG-K',
    standard_gruppe_lesen: true, gemeinde_status: 'beantragt', gruppe_status: 'aktiv', zuordnung: 'Kinderchor' },
  { name: '', titel: 'kaputt', gruppe: null, untergruppe: null },
]

test('UI-R3/L1: alleKalenderZeilen zeigt JEDEN Kalender mit Zuordnung', () => {
  const zeilen = alleKalenderZeilen(KALENDER, { 'G-Chor': 'Chor', 'UG-K': 'Kinderchor' })
  assert.deepEqual(zeilen.map((z) => z.name), ['Kinderchor', 'Proben', 'Gemeinde'],
    'Untergruppe zuerst, dann Gruppe, Gemeinde zuletzt; kaputte Zeile fällt heraus')
  const kinder = zeilen.find((z) => z.name === 'Kinderchor')
  assert.equal(kinder.untergruppe, 'UG-K')
  assert.equal(kinder.gemeinde_status, 'beantragt')
  assert.equal(kinder.gruppe_status, 'aktiv')
  const gemeinde = zeilen.find((z) => z.name === 'Gemeinde')
  assert.equal(gemeinde.gruppe, null)
  assert.equal(gemeinde.untergruppe, null)
  assert.deepEqual(alleKalenderZeilen(null), [], 'keine Antwort → keine Zeilen')
})

test('UI-R3/L2: Anlegeziele kommen vom Server, Gemeinde nur mit darf_gemeinde_kalender', () => {
  const ziele = verwaltungAnlegeZiele({
    darf_gemeinde_kalender: true,
    anlegen_gruppen: ['G-Chor'],
    anlegen_untergruppen: ['UG-K'],
  }, { 'G-Chor': 'Chor', 'UG-K': 'Kinderchor' })
  assert.deepEqual(ziele.map((z) => z.art).sort(), ['gemeinde', 'gruppe', 'untergruppe'])
  assert.equal(ziele.at(-1).art, 'gemeinde')
  assert.equal(ziele.at(-1).anzeige, GEMEINDE_TITEL)
  assert.match(GEMEINDE_TITEL, /alle Mitglieder der Gemeinde/, 'nie „öffentlich“')
  const nachArt = (art) => ziele.find((z) => z.art === art)
  assert.equal(nachArt('untergruppe').anzeige, 'Untergruppe Kinderchor')
  assert.equal(nachArt('gruppe').anzeige, 'Gruppe Chor')
  // Ohne Recht gibt es KEINEN Gemeinde-Kalender — auch nicht als Auswahl.
  const ohne = verwaltungAnlegeZiele({ anlegen_gruppen: ['G-Chor'] })
  assert.deepEqual(ohne.map((z) => z.art), ['gruppe'])
  assert.equal(ohne[0].anzeige, 'G-Chor', 'ohne Namen steht die Kennung — kein erfundener Name')
  assert.deepEqual(verwaltungAnlegeZiele(null), [])
})

test('UI-R3/L3: kalenderVerwaltungSichtbar — dieselbe Lage, in der der Server kein 403 gibt', () => {
  // UI-R3b: EINE Regel statt zweier Kopien (`hatVerwaltbares` ist entfernt).
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [{ name: 'A' }] }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], anlegen_gruppen: ['G'] }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], anlegen_untergruppen: ['UG'] }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], darf_gemeinde_kalender: true }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [] }), false, 'nichts zu verwalten')
  assert.equal(kalenderVerwaltungSichtbar(null), false)
  // Kein zweiter Name für dieselbe Regel: die Datei exportiert ihn nicht mehr.
  assert.equal(modul.hatVerwaltbares, undefined,
    'hatVerwaltbares ist doppelt zu kalenderVerwaltungSichtbar und muss weg sein')
})

test('UI-R3/L4: anlegeAnfrage schickt genau EIN Ziel und die Antwort der Anlege-Frage', () => {
  const ug = anlegeAnfrage({ titel: 'Proben', farbe: '#2266aa', standardGruppeLesen: false,
    ziel: { wert: 'UG-K', art: 'untergruppe' } })
  assert.deepEqual(ug, { titel: 'Proben', farbe: '#2266aa', standard_gruppe_lesen: 0, untergruppe: 'UG-K' })
  const gruppe = anlegeAnfrage({ titel: 'Chor', ziel: { wert: 'G-Chor', art: 'gruppe' } })
  assert.deepEqual(gruppe, { titel: 'Chor', farbe: '', standard_gruppe_lesen: 1, gruppe: 'G-Chor' })
  const gemeinde = anlegeAnfrage({ titel: 'Gemeindeleben', ziel: { wert: '', art: 'gemeinde' } })
  assert.deepEqual(gemeinde, { titel: 'Gemeindeleben', farbe: '', standard_gruppe_lesen: 1 },
    'Gemeinde-Kalender trägt KEIN Ziel-Feld')
  assert.equal(KALENDER_ANLEGEN_FRAGE, 'Sollen alle Gruppenmitglieder diesen Kalender standardmäßig lesen dürfen?')
})

test('UI-R3/L6: Menüpunkt „Kalender verwalten“ hängt am Serverrecht, Import an der Rolle', () => {
  // Sichtbarkeit: nur echte Serverantwort zählt, nie die Rolle.
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [{ name: 'A' }] }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], darf_gemeinde_kalender: true }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], anlegen_gruppen: ['G'] }), true)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [], anlegen_untergruppen: ['UG'] }), true)
  // 403 / leere Antwort: der Eintrag bleibt weg — auch für einen Admin.
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [] }, true), false)
  assert.equal(kalenderVerwaltungSichtbar(null, false), false)
  // Ohne Antwort (Leiste lädt vor dem Server) darf der Admin den Eintrag sehen.
  assert.equal(kalenderVerwaltungSichtbar(null, true), true)

  // Menü: HV/MV/GL (kein Admin) sieht „Verwalten“ — aber NICHT den Import.
  const hv = kalenderMenue({ istKalenderAdmin: false, darfVerwalten: true, hatSchreibrecht: true })
  assert.deepEqual(hv.filter((e) => e.key === 'verwalten').map((e) => e.href),
    ['#/kalender/verwalten'], 'Verwalten steht HV/MV/GL offen')
  assert.equal(hv.some((e) => e.key === 'importieren'), false, 'Import bleibt der Admin-Rolle')
  // Ohne Serverrecht: kein „Verwalten“, auch nicht als Admin-Zufall.
  const ohne = kalenderMenue({ istKalenderAdmin: false, darfVerwalten: false })
  assert.equal(ohne.some((e) => e.key === 'verwalten'), false, 'ohne Recht kein Eintrag')
  // Admin sieht beides.
  const admin = kalenderMenue({ istKalenderAdmin: true })
  assert.equal(admin.some((e) => e.key === 'verwalten'), true)
  assert.equal(admin.some((e) => e.key === 'importieren'), true)
})

test('UI-R3/L7: Anlegeorte zeigen Klarnamen aus dem Gruppenbaum, sonst die Kennung', () => {
  // Der Gruppenbaum des Servers (`get_gruppen_hierarchie`).
  const baum = [
    { name: 'G-Chor', gruppenname: 'Chor', untergruppen: [{ name: 'UG-K', untergruppenname: 'Kinderchor' }] },
    { name: 'G-Ohne', gruppenname: null, untergruppen: [{ name: 'UG-X', untergruppenname: null }] },
  ]
  const namen = ausGruppenbaum(baum)
  assert.deepEqual(namen, { 'G-Chor': 'Chor', 'UG-K': 'Kinderchor' },
    'nur echte Namen — eine leere Bezeichnung erfindet keinen')
  // Mit Namen: die Auswahl nennt „Gruppe Chor“ statt der Kennung.
  const mit = verwaltungAnlegeZiele({ anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: ['UG-K'] }, namen)
  assert.equal(mit.find((z) => z.art === 'gruppe').anzeige, 'Gruppe Chor')
  assert.equal(mit.find((z) => z.art === 'untergruppe').anzeige, 'Untergruppe Kinderchor')
  // Ohne Baum (kein Recht/Fehler): Kennung, kein Absturz.
  const ohne = verwaltungAnlegeZiele({ anlegen_gruppen: ['G-Chor'] }, {})
  assert.equal(ohne[0].anzeige, 'G-Chor')
  assert.deepEqual(ausGruppenbaum(null), {})
  // Die Seite holt den Baum und nutzt ihn — kein Backend-Eingriff.
  const seite = lies('pages/KalenderVerwaltung.vue')
  assert.match(seite, /get_gruppen_hierarchie/, 'die Seite holt die Klarnamen vom Server')
  assert.match(seite, /ausGruppenbaum|gruppenname/, 'und wertet sie aus')
  // Die gemeinsame Fläche setzt „Gruppe“/„Untergruppe“ SELBST davor
  // (`zuordnungsText`) — ein fertig beschrifteter Name ergäbe
  // „Untergruppe: Untergruppe Kinderchor“.
  assert.doesNotMatch(seite, /anzeigename:\s*z\.anzeige/,
    'keine doppelte Vorsilbe an die gemeinsame Fläche')
  assert.match(seite, /anzeigename:\s*namen\.value\[z\.wert\]/,
    'reiner Name aus dem Baum')
})

test('UI-R3/L5: die Seite zeigt keine Rollen-Auswahlen mehr (leserechte/schreibrechte/moderatoren)', () => {
  const seite = lies('pages/KalenderVerwaltung.vue')
  assert.doesNotMatch(seite, /form\.leserechte/, 'Leserechte-Auswahl ist entfernt')
  assert.doesNotMatch(seite, /form\.schreibrechte/, 'Schreibrechte-Auswahl ist entfernt')
  assert.doesNotMatch(seite, /form\.moderatoren/, 'Moderatoren-Auswahl ist entfernt')
  assert.doesNotMatch(seite, /v-for="r in rollen"/, 'keine Rollenliste mehr')
  // Auch ein wieder eingefügtes Rollenfeld (ohne `form.`-Präfix) fällt auf:
  // die Seite kennt die drei Altfelder gar nicht mehr, in keiner Form.
  assert.doesNotMatch(seite, /leserechte|schreibrechte|moderatoren/,
    'kein Altfeld mehr — auch nicht als Objektschlüssel oder Hinweistext')
  // Freigaben laufen über die GEMEINSAME Fläche aus UI-R2.
  assert.match(seite, /KalenderEinstellungen/, 'gemeinsame Fläche fehlt')
  assert.match(seite, /<KalenderEinstellungen[\s\S]*?alle-kalender/, 'die Fläche zeigt alle verwaltbaren Kalender')
  assert.match(seite, /get_objekt_rechte|KalenderRechte|KalenderEinstellungen/,
    'Freigaben kommen aus dem EINEN Rechtesystem')
  // Keine eigene Rechte-Logik: der Server entscheidet.
  assert.doesNotMatch(seite, /is_admin/, 'kein Boot-Wert für Rechte')
  // UI-R3b: auch KEIN Rollen-Rückfall. `istKalenderAdmin`/`useSession` prüften
  // im Client eine Rolle — `get_kalender_verwaltung` liefert beide Anlege-
  // Rechte ohnehin immer in der Antwort.
  assert.doesNotMatch(seite, /istKalenderAdmin|useSession|session\.rollen/,
    'nur die Serverantwort zählt — keine Rolle im Client')
})
