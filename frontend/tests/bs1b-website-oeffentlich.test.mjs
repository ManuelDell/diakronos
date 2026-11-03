/**
 * BS-1b — Öffentliche Lese-API für Website-Bausteine + iCal-Feed (Vertragstest).
 *
 * Der Baustein selbst ist Backend; die Primo-Bausteine (BS-2*) bauen gegen
 * seine Form. Dieser Test hält deshalb den VERTRAG fest, damit niemand gegen
 * eine erfundene Form baut:
 *
 *   (1) Genau sechs Leseendpunkte, alle `allow_guest=True` und `methods=["GET"]`.
 *   (2) Die Feldlisten (Positivlisten, G1) stehen im Quelltext — und KEIN
 *       verbotenes Feld (mitarbeiter, ablehnungs_grund, email, autor, …).
 *   (3) Nur der Status "Festgelegt" gilt als öffentlich; Default ist AUS.
 *   (4) Die drei HTTP-Routen (iCal, Bild, CORS-Variante) sind registriert und
 *       werden VOR dem SPA-Catch-all eingetragen.
 *   (5) CORS nur für `PRIMO_PUBLIC_URL`, ohne Credentials; Cache 300 s.
 *   (6) Die Bremse hat eigene Einstellungen (120/min je Adresse).
 *
 * Geprüft wird Quelltext (Regex), nicht das Aussehen; Lauf im Docker-Build
 * über `node --test`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const PKT = join(REPO, 'backend', 'src', 'diakronos_app', 'website')
const API = join(PKT, 'oeffentlich_api.py')
const AUSWAHL = join(PKT, 'oeffentlich_auswahl.py')
const DATEN = join(PKT, 'oeffentlich_daten.py')
const HTTP = join(PKT, 'oeffentlich_http.py')
const BREMSE = join(PKT, 'oeffentlich_bremse.py')
const INHALT = join(PKT, 'oeffentlich_inhalt.py')
const MAIN = join(REPO, 'backend', 'src', 'diakronos_app', 'main.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('BS-1b: die sechs Leseendpunkte sind für Gäste offen und nur GET', () => {
  const quelle = lies(API)
  for (const name of [
    'kalender',
    'termine',
    'naechster_termin',
    'gruppen',
    'gruppe',
    'beitraege',
  ]) {
    assert.match(
      quelle,
      new RegExp(
        `@whitelist\\(methods=\\["GET"\\], allow_guest=True\\)\\ndef ${name}\\(`,
      ),
      `Endpunkt ${name} fehlt, ist nicht öffentlich oder nimmt andere Methoden als GET an`,
    )
  }
  // Kein schreibender Endpunkt in diesem Modul (Karte: nur GET).
  assert.ok(
    !/@whitelist\(methods=\["POST"\]/.test(quelle),
    'die Lese-API darf keinen POST-Endpunkt enthalten',
  )
})

test('BS-1b: Feld-Positivlisten (G1) — und keine verbotenen Felder', () => {
  const quelle = lies(AUSWAHL)
  for (const feld of [
    '"id"',
    '"titel"',
    '"beginn"',
    '"ende"',
    '"ganztaegig"',
    '"beschreibung"',
    '"ort"',
    '"kategorie"',
    '"gruppe"',
    '"farbe"',
    '"anmeldung_url"',
  ]) {
    assert.ok(
      quelle.includes(feld),
      `Feld ${feld} fehlt in der Positivliste der Termin-Ausgabe`,
    )
  }
  for (const verboten of [
    '"mitarbeiter"',
    '"ablehnungs_grund"',
    '"autor"',
    '"autor_email"',
    '"email"',
    '"owner"',
    '"ablaufplan"',
    '"dienstplan"',
    '"teilnehmer"',
  ]) {
    assert.ok(
      !quelle.includes(verboten),
      `verbotenes Feld ${verboten} steht in der Positivliste (G1)`,
    )
  }
  // Nie eine ganze Zeile serialisieren: JEDE Ausgabefunktion baut ihr Dict
  // aus ausdruecklich genannten Feldern (kein `dict(zeile)`/`vars()`).
  const ohneKommentar = quelle
    .split('\n')
    .map((z) => z.replace(/#.*$/, ''))
    .join('\n')
  assert.ok(
    !/dict\(\s*zeile\s*\)|dict\(\s*row\s*\)|vars\(|__dict__/.test(ohneKommentar),
    'es wird eine ganze Zeile serialisiert — das verletzt G1',
  )
})

test('BS-1b: Beitragsinhalt nur nach Allowlist, keine Skripte', () => {
  const quelle = lies(INHALT)
  for (const tag of ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'h2', 'h3', 'blockquote']) {
    assert.ok(
      new RegExp(`"${tag}"`).test(quelle),
      `erlaubtes Element <${tag}> fehlt in der Allowlist`,
    )
  }
  assert.match(quelle, /"script",\s*"style"/, 'script/style müssen MIT Inhalt verworfen werden')
  for (const schema of ['http://', 'https://', 'mailto:']) {
    assert.ok(quelle.includes(`"${schema}"`), `Link-Schema ${schema} fehlt`)
  }
})

test('BS-1b: nur "Festgelegt" ist öffentlich, Default AUS', () => {
  const quelle = lies(DATEN)
  assert.match(
    quelle,
    /STATUS_OEFFENTLICH = "Festgelegt"/,
    'der öffentliche Status ist nicht "Festgelegt"',
  )
  // Freigabe-Schalter müssen abgefragt werden (nicht "alles ist öffentlich").
  assert.match(quelle, /website_freigabe\.is_\(True\)/, 'Kalender-/Gruppenfreigabe wird nicht geprüft')
  assert.match(quelle, /Beitrag\.veroeffentlicht\.is_\(True\)/, 'Beitrags-Freigabe fehlt')
  assert.match(quelle, /Beitrag\.auf_website\.is_\(True\)/, 'auf_website wird nicht geprüft')
  assert.match(
    quelle,
    /website_nur_oeffentliche_kategorien/,
    'Kategorie-Einschränkung des Kalenders wird nicht beachtet',
  )
})

test('BS-1b: die drei HTTP-Routen liegen VOR dem SPA-Catch-all', () => {
  const main = lies(MAIN)
  const routen = lies(API)
  assert.match(routen, /"\/website\/ical\/\{kalender_slug\}"/)
  assert.match(routen, /"\/website\/bild\/\{art\}\/\{slug\}"/)
  assert.match(routen, /"\/website\/oeffentlich\/\{funktion\}"/)
  const i = main.indexOf('_website_oeffentlich_routen(app)')
  // Der AUFRUF (nicht der Import oben in der Datei).
  const spa = main.indexOf('\n    mount_spa(app)')
  assert.ok(i > 0, 'die Website-Routen werden in main.py nicht registriert')
  assert.ok(spa > 0, 'mount_spa(app) nicht gefunden')
  assert.ok(
    i < spa,
    'die Website-Routen stehen NACH dem SPA-Catch-all — die SPA würde sie schlucken',
  )
})

test('BS-1b: CORS nur für PRIMO_PUBLIC_URL, ohne Credentials', () => {
  const quelle = lies(HTTP)
  assert.match(quelle, /primo_public_url_effektiv/, 'CORS liest PRIMO_PUBLIC_URL nicht')
  assert.match(quelle, /Access-Control-Allow-Origin/)
  assert.ok(
    !/Allow-Credentials/.test(quelle),
    'CORS darf keine Credentials erlauben (G4)',
  )
  assert.ok(
    !/Access-Control-Allow-Origin"\]\s*=\s*"\*"/.test(quelle),
    'CORS darf nicht "*" senden',
  )
  assert.match(quelle, /max-age=\{CACHE_SEKUNDEN\}|max-age=/, 'Cache-Control fehlt')
  assert.match(quelle, /CACHE_SEKUNDEN = 300/, 'Cache-Dauer ist nicht 300 s')
})

test('BS-1b: Bremse mit eigenen Einstellungen (120/min)', () => {
  const quelle = lies(BREMSE)
  assert.match(quelle, /website_oeffentlich_max_ip/, 'Bremse liest keine eigene Grenze')
  assert.match(quelle, /120/, 'Vorgabe 120/min fehlt')
  assert.ok(
    !/kontakt-versuche/.test(quelle),
    'die Bremse darf den Kontakt-Zähler nicht mitbenutzen',
  )
})

test('BS-1b: Pfade sind präfixbewusst (keine festen Adressen im Code)', () => {
  const daten = lies(DATEN)
  const inhalt = lies(INHALT)
  assert.ok(
    inhalt.includes('from diakronos_app.base_path import pfad'),
    'Bild-URL ohne base_path.pfad',
  )
  assert.ok(
    daten.includes('from diakronos_app.anmeldung.registrierungslink import link_anzeige'),
    'die Anmelde-Adresse wird nicht über registrierungslink.link_anzeige gebaut',
  )
})
