/**
 * N11 — Reiter „Import + Export“: Aufbau der Oberflaeche.
 *
 * Statische Pruefung der Quelldateien (kein vue-Paket noetig, laeuft im
 * Docker-Build mit). Sie haelt fest, was der Reiter leisten MUSS:
 * drei Schritte, Muster-Datei, Export aus der Kopfzeile, keine Fachbegriffe,
 * und das Anlegen von Dubletten nur nach ausdruecklicher Bestaetigung.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const hier = dirname(fileURLToPath(import.meta.url))
const lies = pfad => readFileSync(join(hier, '..', 'src', 'diakonos', pfad), 'utf8')

test('Import-Seite: drei Schritte sind benannt', () => {
  const seite = lies('pages/mitglieder/Import.vue')
  assert.match(seite, /1\. Datei wählen/, 'Schritt 1')
  assert.match(seite, /2\. Spalten zuordnen/, 'Schritt 2')
  assert.match(seite, /3\. Prüfen und übernehmen/, 'Schritt 3')
  // Hinweisleiste zeigt die Schrittfolge (DkHint mit schritte/aktiv)
  assert.match(seite, /:schritte="\['Datei wählen', 'Spalten zuordnen'/, 'Schrittfolge sichtbar')
})

test('Import-Seite: Muster-Datei und Vorschau mit den drei Ergebnissen', () => {
  const seite = lies('pages/mitglieder/Import.vue')
  assert.match(seite, /Muster-Datei/, 'Muster-Datei angeboten')
  assert.match(seite, /musterHerunterladen/, 'Muster-Datei laedt herunter')
  assert.match(seite, /zusammenfassung\.neu/, 'Zahl „neu“')
  assert.match(seite, /zusammenfassung\.dubletten/, 'Zahl „doppelt“')
  assert.match(seite, /zusammenfassung\.fehler/, 'Zahl „fehlerhaft“')
})

test('Import-Seite: Dubletten nur nach ausdruecklicher Bestaetigung', () => {
  const seite = lies('pages/mitglieder/Import.vue')
  // Auswahl „überspringen“ ist die Vorgabe
  assert.match(seite, /dublettenBehandlung = ref\('ueberspringen'\)/, 'Vorgabe: überspringen')
  // Haken erscheint nur, wenn „trotzdem anlegen“ gewaehlt ist
  assert.match(seite, /v-if="!dublettenUeberspringen"[\s\S]{0,80}v-model="bestaetigt"/, 'Haken nur bei „trotzdem anlegen“')
  // Bestaetigung wird als 1/0 an den Server gegeben (Server-Vorgabe 0)
  assert.match(lies('composables/useMitgliederImport.js'), /bestaetigt: bestaetigt \? 1 : 0/, 'Bestaetigung als 1/0')
})

test('Import-Seite: keine Fachbegriffe in sichtbaren Texten', () => {
  const seite = lies('pages/mitglieder/Import.vue')
  const vorlage = seite.slice(0, seite.indexOf('<script setup>'))
  for (const wort of ['Slot', 'Dublette', 'CSV-Import', 'Entity', 'Payload']) {
    assert.ok(!vorlage.includes(wort), `kein Fachbegriff „${wort}“ in der Anzeige`)
  }
  // Der Nutzer liest „möglicherweise doppelt“ statt „Dublette“.
  assert.match(vorlage, /möglich doppelt/, 'verstaendliches Wort für Dubletten')
})

test('Mitglieder-Rahmen: Reiter Import mit eigener Adresse und Export', () => {
  const bereich = lies('pages/mitglieder/Bereich.vue')
  assert.match(bereich, /import\('\.\/Import\.vue'\)/, 'Rahmen bindet die Import-Seite')
  assert.match(bereich, /case 'import':/, 'Reiter „import“ ist verdrahtet')
  assert.match(bereich, /zeigeImportExportKnopf/, 'Export-Knopf im Import-Reiter')

  const menue = lies('menue.js')
  assert.match(menue, /id: 'import', label: 'Import', href: '#\/mitglieder\/import'/, 'Reiter im Menue')

  const router = lies('router.js')
  assert.match(router, /'#\/mitglieder\/import':\s*'MitgliederImport'/, 'eigene Adresse')
  assert.match(router, /MitgliederImport:[\s\S]{0,40}Bereich\.vue/, 'Seitenname verdrahtet')
  assert.match(router, /'MitgliederImport'/, 'Import ist eine Verwaltungsseite (Guard)')
})

test('Export kommt vom Server, ohne clientseitige Zellteilung', () => {
  const composable = lies('composables/useMitgliederImport.js')
  assert.match(composable, /exportiere_mitglieder_csv/, 'Server-Export')
  const liste = lies('pages/Mitglieder.vue')
  assert.ok(!liste.includes('_csvZelleSicher'), 'keine naive Zellteilung mehr')
  assert.match(liste, /statusZaehler/, 'Statuszahlen aus dem Server')
})

test('K1: Filter „Alle n“ zaehlt ohne Statusfilter (gesamt_alle)', () => {
  // N11b/K1: `gesamt` ist das `total` der GEFILTERTEN Abfrage und stand bei
  // aktivem Statusfilter faelschlich an „Alle“. Der Server liefert
  // `gesamt_alle` (ohne Statusfilter) — das Frontend muss es benutzen.
  const liste = lies('pages/Mitglieder.vue')
  assert.match(liste, /label: `Alle \$\{gesamtAlle\.value\}`/,
    '„Alle n“ nimmt gesamtAlle, nicht gesamt')
  assert.doesNotMatch(liste, /label: `Alle \$\{gesamt\.value\}`/,
    'nicht mehr die gefilterte Zahl an „Alle“')

  const composable = lies('composables/useMitglieder.js')
  assert.match(composable, /const gesamtAlle = ref\(0\)/, 'gesamtAlle-Ref vorhanden')
  assert.match(composable, /payload\.gesamt_alle/, 'gesamt_alle aus der Server-Antwort')
  assert.match(composable, /gesamtAlle: computed/, 'gesamtAlle nach außen sichtbar')
})
