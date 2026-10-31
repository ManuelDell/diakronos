/**
 * BS-1a — Website-Freigaben: was der Server zusichert (Vertragstest).
 *
 * Der Baustein selbst ist Backend (Migration + Verwaltungs-API); die
 * Oberfläche kommt mit einer eigenen Karte. Dieser Test hält deshalb den
 * VERTRAG fest, damit diese Oberfläche (und BS-1b/1c/1d) nicht gegen eine
 * erfundene Form baut:
 *
 *   (1) Es gibt genau die sechs Endpunkte, alle `allow_guest=False`.
 *   (2) Die Antwortfelder von `freigaben_lesen` stehen im Quelltext.
 *   (3) Jeder Freigabe-Schalter hat Default AUS (G1: nichts ist öffentlich,
 *       solange es nicht freigegeben ist) — nicht nur im Modell, auch in der
 *       Migration (`server_default`).
 *   (4) Die Rollenprüfung ist DIESELBE wie bei der Primo-Anbindung
 *       (`_require_website_rolle`), also System Manager / Administrator /
 *       Website-Moderator.
 *   (5) Die reservierten Slugs der Karte sind im Regelmodul zu finden.
 *   (6) Ohne Zeile im Postfach gilt `WEBSITE_KONTAKT_EMPFAENGER` (WEB-10).
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
const API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py')
const REGELN = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'freigaben.py')
const MIGRATION = join(REPO, 'backend', 'alembic', 'versions', 'bs1a_website_freigaben.py')
const MODELLE = join(REPO, 'backend', 'src', 'diakronos_app', 'models', 'website_kontakt.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('BS-1a: die sechs Verwaltungs-Endpunkte sind whitelisted und nur angemeldet', () => {
  const quelle = lies(API)
  for (const name of [
    'freigaben_lesen',
    'freigabe_setzen',
    'beitrag_auf_website',
    'postfach_speichern',
    'postfach_loeschen',
    'kategorie_oeffentlich',
  ]) {
    assert.match(
      quelle,
      new RegExp(`@whitelist\\((?:methods=\\["POST"\\], )?allow_guest=False\\)\\ndef ${name}\\(`),
      `Endpunkt ${name} fehlt oder ist für Gäste offen`,
    )
  }
})

test('BS-1a: alle Endpunkte laufen durch dieselbe Rollenprüfung wie WEB-1', () => {
  const quelle = lies(API)
  const block = quelle.slice(quelle.indexOf('BS-1a — Website-Freigaben'))
  const rufe = [...block.matchAll(/def (\w+)\(/g)].map((m) => m[1])
  assert.ok(rufe.length >= 6, `zu wenige Endpunkte gefunden: ${rufe.join(', ')}`)
  for (const name of [
    'freigaben_lesen',
    'freigabe_setzen',
    'beitrag_auf_website',
    'postfach_speichern',
    'postfach_loeschen',
    'kategorie_oeffentlich',
  ]) {
    const start = block.indexOf(`def ${name}(`)
    const naechste = block.indexOf('\ndef ', start + 1)
    const rumpf = block.slice(start, naechste === -1 ? undefined : naechste)
    assert.match(rumpf, /_require_website_rolle\(\)/, `${name} prüft die Rolle nicht`)
  }
})

test('BS-1a: freigaben_lesen liefert die im Vertrag genannten Felder', () => {
  const quelle = lies(API)
  for (const feld of [
    'kalender',
    'gruppen',
    'beitraege_anzahl',
    'postfaecher',
    'nur_oeffentliche_kategorien',
    'postfach_fallback',
  ]) {
    assert.ok(quelle.includes(`"${feld}"`), `Feld ${feld} fehlt in freigaben_lesen`)
  }
})

test('BS-1a: jeder Freigabe-Schalter steht auf AUS — im Modell und in der Migration', () => {
  const modelle = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'models', 'kronos.py'))
    + lies(join(REPO, 'backend', 'src', 'diakronos_app', 'models', 'diakonos.py'))
  for (const feld of [
    'website_freigabe',
    'website_nur_oeffentliche_kategorien',
    'auf_website',
  ]) {
    assert.match(
      modelle,
      new RegExp(`${feld}: Mapped\\[bool\\] = mapped_column\\(Boolean, default=False`),
      `${feld} hat keinen Default AUS im Modell`,
    )
  }
  const migration = lies(MIGRATION)
  assert.ok(
    (migration.match(/sa\.text\("false"\)/g) || []).length >= 4,
    'Migration setzt die Schalter nicht serverseitig auf false',
  )
  assert.match(migration, /website_kontakt_postfach/)
})

test('BS-1a: Slugs sind eindeutig — partielle Unique-Indizes in der Migration', () => {
  const migration = lies(MIGRATION)
  assert.match(migration, /uq_kalender_website_slug/)
  assert.match(migration, /uq_gruppe_website_slug/)
  assert.match(migration, /unique=True/)
})

test('BS-1a: die reservierten Slugs der Karte stehen im Regelmodul', () => {
  const regeln = lies(REGELN)
  for (const slug of ['diakronos', 'primo', 'admin', 'api', 'login', 'standard']) {
    assert.match(regeln, new RegExp(`"${slug}"`), `reservierter Slug ${slug} fehlt`)
  }
  assert.match(regeln, /\[a-z0-9-\]/)
})

test('BS-1a: ohne Postfach-Zeile gilt WEBSITE_KONTAKT_EMPFAENGER (WEB-10)', () => {
  const regeln = lies(REGELN)
  assert.match(regeln, /postfaecher_oeffentlich/)
  assert.match(regeln, /empfaenger_standard/)
  assert.match(regeln, /POSTFACH_STANDARD = "standard"/)
})

test('BS-1a: das Postfach-Modell trägt Slug, Bezeichnung, Adresse, aktiv, Sortierung', () => {
  const modell = lies(MODELLE)
  assert.match(modell, /__tablename__ = "website_kontakt_postfach"/)
  for (const spalte of ['slug', 'bezeichnung', 'email', 'aktiv', 'sortierung']) {
    assert.match(modell, new RegExp(`\\b${spalte}: Mapped`), `Spalte ${spalte} fehlt`)
  }
})
