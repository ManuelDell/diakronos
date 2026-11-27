/**
 * ABN-3 — Versionsanzeige: EINE Zahl im Zustandspruefer und in der Oberflaeche.
 *
 * Was hier festgehalten wird (die Zusagen der Karte ABN-3, Punkt 1):
 *
 * 1. Die Oberflaeche liest die Version aus dem Boot-Objekt — derselbe Wert,
 *    den `/healthz` meldet (Server: `diakronos_app.version_auskunft()`).
 *    Kein zweiter Abruf, keine zweite Formatierung.
 * 2. Fehlt der Wert, zeigt die Oberflaeche einen sichtbaren Platzhalter —
 *    nicht eine plausible Zahl. Die FUSSZEILE bleibt in diesem Fall weg
 *    (kein Stoerfeuer in jeder Ansicht).
 * 3. Der Git-Kurz-Hash wird nur gezeigt, wenn er da ist; geraten wird nichts.
 * 4. „Einstellungen → Über Diakronos“ steht im Katalog, hat eine Adresse im
 *    Router und ist KEINE Verwaltungsseite (jede Sitzung darf ihre eigene
 *    Version ablesen).
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  VERSION_UNBEKANNT, versionAusBoot, fusszeilenText,
} from '../src/diakonos/pages/einstellungen/version.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))

/**
 * Eine Datei aus dem FRONTEND-Quellbaum lesen.
 *
 * Der Frontend-Stage des Images enthaelt NUR `frontend/` (`COPY frontend/ ./`)
 * — `backend/` liegt dort nicht (Regel 13). Der Test liest aus dem
 * Build-Verzeichnis deshalb AUSNAHMSLOS Frontend-Dateien; die Backend-Seite
 * pruefen die Backend-Tests im app-Image (`backend/tests/test_abn3_version.py`)
 * — dort liegt der Code, dort laeuft er.
 */
function lies(pfad) {
  return readFileSync(join(HIER, '..', pfad), 'utf8')
}

// ── 1. Die Funktion selbst ──────────────────────────────────────────────────

test('ABN-3/A: Version und Hash kommen aus dem Boot-Objekt', () => {
  assert.deepEqual(
    versionAusBoot({ version: '2.0.0', git: '3900e4504ed1' }),
    { version: '2.0.0', git: '3900e4504ed1' },
  )
  // Leerraum wird abgeschnitten (der Server sendet keine, ein Proxy koennte).
  assert.deepEqual(versionAusBoot({ version: ' 2.1.0 ', git: ' abc123 ' }),
    { version: '2.1.0', git: 'abc123' })
})

test('ABN-3/A: ohne Version steht ein sichtbarer Platzhalter, keine Zahl', () => {
  for (const boot of [{}, { version: '' }, { version: null }, null, undefined]) {
    const { version } = versionAusBoot(boot)
    assert.equal(version, VERSION_UNBEKANNT)
    assert.notEqual(version, '2.0.0')
  }
  // Die Form "unbekannt" ist gewollt — sie sagt dem Betreiber, dass etwas fehlt.
  assert.match(VERSION_UNBEKANNT, /^unbekannt$/)
})

test('ABN-3/A: ohne Git-Kennung bleibt das Feld LEER (nicht "unbekannt")', () => {
  assert.equal(versionAusBoot({ version: '2.0.0' }).git, '')
  assert.equal(versionAusBoot({ version: '2.0.0', git: null }).git, '')
})

test('ABN-3/A: Fusszeilentext — dezent, ohne Hash (ABN-3b/N9)', () => {
  // Der Hash steht NUR in "Einstellungen -> Ueber Diakronos", nicht in einer
  // Zeile, die jede Sitzung auf jeder Seite sieht.
  assert.equal(fusszeilenText({ version: '2.0.0', git: '3900e4504ed1' }),
    'Version 2.0.0')
  assert.equal(fusszeilenText({ version: '2.0.0' }), 'Version 2.0.0')
  // Ohne Version bleibt die Fusszeile WEG (leerer Text -> v-if false).
  assert.equal(fusszeilenText({}), '')
  assert.equal(fusszeilenText(null), '')
})

// ── 2. Die Oberflaeche liest genau die Felder, die der Server sendet ────────
//
// Der Server-Teil (Boot-Objekt, /healthz, VERSION-Datei) steht in
// `backend/tests/test_abn3_version.py` und laeuft IM app-Image — hier waere
// `backend/` gar nicht vorhanden (der Frontend-Stage kopiert nur `frontend/`).

test('ABN-3/A: die Feldnamen sind die des Servers (version, git)', () => {
  // Absichtlich als Zeichenketten festgehalten: aendert der Server die Namen,
  // faellt es HIER auf, bevor die Oberflaeche leer bleibt.
  assert.deepEqual(Object.keys(versionAusBoot({ version: 'x', git: 'y' })).sort(),
    ['git', 'version'])
})

// ── 3. Die Einbauorte ──────────────────────────────────────────────────────

test('ABN-3/B: die Seitenleiste traegt die Fusszeile und liest dieselbe Quelle', () => {
  const seite = lies('src/diakonos/components/AppSidebar.vue')
  assert.match(seite, /dk-sb-version/, 'Fusszeile fehlt')
  assert.match(seite, /fusszeilenText/, 'Fusszeile muss fusszeilenText() lesen')
  // Nicht im eingeklappten Zustand (dort ist kein Platz) und nicht, wenn leer.
  assert.match(seite, /v-if="!collapsed && versionsText"/)
})

test('ABN-3/B: "Ueber Diakronos" steht im Katalog und im Router', () => {
  const katalog = lies('src/diakonos/pages/Einstellungen.vue')
  assert.match(katalog, /id: 'ueber-diakronos'/, 'Bereich fehlt im Katalog')
  assert.match(katalog, /seite: 'EinstellungenUeberDiakronos'/)
  assert.match(katalog, /UeberDiakronos\.vue/, 'Abschnitt wird nicht geladen')

  const router = lies('src/diakonos/router.js')
  assert.match(router, /'#\/einstellungen\/ueber-diakronos': 'EinstellungenUeberDiakronos'/)
  assert.match(router, /EinstellungenUeberDiakronos: \(\) => import\('\.\/pages\/Einstellungen\.vue'\)/)
  // Keine Verwaltungsseite: die eigene Version ablesen darf jede Sitzung.
  const adminOnly = router.split('const ADMIN_ONLY_PAGES')[1].split('const PERSONEN_VERWALTUNG_PAGES')[0]
  assert.doesNotMatch(adminOnly, /EinstellungenUeberDiakronos/)
})

test('ABN-3/B: der Abschnitt ist durchsuchbar (Stichworte im Katalog)', () => {
  const suche = lies('src/diakonos/pages/einstellungen/suche.mjs')
  assert.match(suche, /'ueber-diakronos': \['Über Diakronos', 'Version'/)
})

test('ABN-3/B: der Abschnitt nennt Version, Stand und den Weg zur Anleitung', () => {
  const abschnitt = lies('src/diakonos/pages/einstellungen/UeberDiakronos.vue')
  // Beide Felder stehen sichtbar im Markup (dieselbe Kennung wie im Test oben).
  assert.match(abschnitt, /data-ue-feld="version"/)
  assert.match(abschnitt, /data-ue-feld="git"/)
  // Ohne Hash: die Zeile sagt das ausdruecklich, statt leer zu bleiben.
  assert.match(abschnitt, /nicht im Build vermerkt/)
  // Verweis auf die Betriebsanleitung (Abschnitt 18) — kein zweiter Weg.
  assert.match(abschnitt, /Betriebsanleitung/)
  // Und die Werte kommen aus der einen Funktion.
  assert.match(abschnitt, /versionAusBoot\(\)/)
})

test('ABN-3/B: Farben und Maße kommen aus den Projekt-Tokens', () => {
  const abschnitt = lies('src/diakonos/pages/einstellungen/UeberDiakronos.vue')
  const style = abschnitt.split('<style scoped>')[1]
  assert.ok(style, 'Abschnitt hat keinen Stilblock')
  // Keine festen Farben — hell und dunkel laufen dann von selbst mit.
  assert.doesNotMatch(style, /#[0-9a-fA-F]{3,8}\b/, 'feste Farbe im Stilblock')
  assert.doesNotMatch(style, /rgba?\(/, 'feste Farbe im Stilblock')
  assert.match(style, /var\(--dk-text\)/)
  assert.match(style, /var\(--dk-text-muted\)/)
  assert.match(style, /var\(--dk-border\)/)
  assert.match(style, /var\(--sp-/)
  // Handy 390 px: eine eigene Regel, in der Schluessel und Wert untereinander stehen.
  assert.match(style, /@media \(max-width: 30rem\)/)
  assert.match(style, /flex-direction: column/)
})
