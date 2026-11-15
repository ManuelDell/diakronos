/**
 * UI-R3g — SOLL 3/4: der geteilte Lader trägt keinen toten Weg mehr.
 *
 * Kein Betriebscode ruft `laden()` ohne `frisch` und niemand benutzt `teilen()`
 * (die Seiten laden selbst und übernehmen die Antwort direkt). Beides ist
 * entfernt; der nicht-frische Zweig samt `FEHLSCHLAG_GEDULD_MS` und `teilen()`
 * wäre sonst Code, den nur Tests noch am Leben hielten.
 *
 * Die früheren Prüfungen bleiben erhalten (nur der Weg dorthin ist ein
 * anderer): der 403 setzt `sperrt`, ein Netzfehler leert den Stand und setzt
 * `fehler` — hier über den ECHTEN Lader geprüft, nicht über `teilen()`.
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3g-lader.test.mjs
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const lies = (rel) => readFileSync(resolve(SRC_DIR, 'diakonos', rel), 'utf8')

/** Ein Kalender, wie `get_kalender_verwaltung` ihn liefert. */
const kalender = (name) => ({ name, titel: name, gruppe: 'G-Chor', untergruppe: null })

async function stand() {
  const modul = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  modul.__leeren()
  return modul
}

const warte = async (n = 20) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Eine zurückgehaltene Antwort: `oeffnen(wert)` löst sie auf. */
function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
}

// ══════════════════════════════════════════════════════════════════════════
// S1 · Toter Weg ist weg
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3g/S1: `teilen` und der nicht-frische Zweig (samt FEHLSCHLAG_GEDULD_MS) sind entfernt', () => {
  const quelle = lies('composables/useKalenderVerwaltung.js')
  assert.doesNotMatch(quelle, /export function teilen/, '`teilen()` lebt noch im geteilten Lader')
  assert.doesNotMatch(quelle, /FEHLSCHLAG_GEDULD_MS/, '`FEHLSCHLAG_GEDULD_MS` lebt noch')
  assert.doesNotMatch(quelle, /\bfehlschlagAm\b/, '`fehlschlagAm` (Geduld des Fehlschlags) lebt noch')
  assert.doesNotMatch(quelle, /frisch\s*=\s*false/, '`laden()` hat noch einen Weg ohne `frisch`')
  // Und kein Betriebscode benutzt die Wege.
  for (const datei of ['pages/Kalender.vue', 'pages/KalenderVerwaltung.vue',
    'components/kronos/KronosSidebar.vue', 'components/gruppen/KalenderEinstellungen.vue']) {
    const text = lies(datei)
    if (/useKalenderVerwaltung/.test(text)) {
      assert.doesNotMatch(text, /\bteilen\b/, `${datei} benutzt noch \`teilen\``)
      assert.doesNotMatch(text, /laden(?:KalenderVerwaltung)?\(\s*\{[^}]*frisch/, `${datei} verlangt noch \`frisch\``)
    }
  }
})

// ══════════════════════════════════════════════════════════════════════════
// S2 · Die früheren Prüfungen bleiben — über den echten Lader
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3g/S2: 403 setzt `sperrt` (kein Fehler), ein Netzfehler leert den Stand und setzt `fehler`', async () => {
  const geteilt = await stand()
  let antwort = null
  geteilt.__setzeApiAufruf(async () => {
    if (antwort instanceof Error) throw antwort
    return antwort
  })
  const sicht = geteilt.useKalenderVerwaltung()

  // 1) Erst ein Stand, dann 403: der Stand wird GELEERT, `sperrt` gesetzt.
  antwort = { kalender: [kalender('Proben')], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false }
  geteilt.aktuellerSatz()
  assert.deepEqual((await geteilt.laden({ frisch: true }))?.kalender?.map((k) => k.name), ['Proben'])
  assert.equal(sicht.sperrt.value, false)

  antwort = Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 })
  geteilt.aktuellerSatz()
  assert.equal(await geteilt.laden({ frisch: true }), null, '403: `laden()` gibt keinen Stand')
  assert.equal(sicht.sperrt.value, true, 'der Lader kennt die Sperre nicht')
  assert.equal(sicht.fehler.value, '', 'ein 403 ist eine Lage, kein Fehler')
  assert.equal(sicht.verwaltung.value, null, 'nach dem 403 steht noch ein Stand')
  assert.equal(sicht.antwortDa.value, true, 'die Antwort (403) gilt nicht als eingetroffen')

  // 2) Ein anderer Fehler: Stand leer, `sperrt` zurück, `fehler` gesetzt.
  antwort = Object.assign(new Error('Netz weg.'), { status: 500 })
  geteilt.aktuellerSatz()
  assert.equal(await geteilt.laden({ frisch: true }), null)
  assert.equal(sicht.verwaltung.value, null, 'der alte Stand überlebt den Fehlschlag (fail closed verletzt)')
  assert.equal(sicht.sperrt.value, false, '`sperrt` bleibt nach einem Netzfehler stehen')
  assert.equal(sicht.fehler.value, 'Netz weg.', 'der Fehlertext fehlt')
  geteilt.__setzeApiAufruf(null)
})

// ══════════════════════════════════════════════════════════════════════════
// S3 · Überholte Ladung übernimmt nichts (SOLL 4)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3g/S3: eine überholte Ladung gibt „überholt“ zurück und schreibt den Stand nicht', async () => {
  const geteilt = await stand()
  const alt = schleuse()
  const neu = schleuse()
  const antworten = [alt.versprechen, neu.versprechen]
  let gezaehlt = 0
  geteilt.__setzeApiAufruf(async () => antworten[gezaehlt++])

  const satzAlt = geteilt.aktuellerSatz()
  const ladungAlt = geteilt.laden({ frisch: true })
  await warte(4)
  const satzNeu = geteilt.aktuellerSatz()
  const ladungNeu = geteilt.laden({ frisch: true })
  await warte(4)
  assert.equal(gezaehlt, 2, 'beide Ladungen müssen gefragt haben')

  // Die JÜNGERE Antwort kommt zuerst: sie schreibt den Stand.
  neu.oeffnen({ kalender: [kalender('Neu')], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  const standNeu = await ladungNeu
  assert.deepEqual(standNeu?.kalender?.map((k) => k.name), ['Neu'])
  assert.equal(geteilt.ueberholt(standNeu), false, 'die jüngste Ladung gilt als überholt')

  // Die ÄLTERE Antwort kommt danach: sie übernimmt NICHTS und gibt nicht den
  // (neuen) geteilten Stand zurück — sie sagt „überholt“.
  alt.oeffnen({ kalender: [kalender('Alt')], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  const standAlt = await ladungAlt
  assert.equal(geteilt.ueberholt(standAlt), true,
    'die überholte Ladung gibt den geteilten Stand zurück statt der Kennung „überholt“: '
      + JSON.stringify(standAlt))
  assert.deepEqual(geteilt.useKalenderVerwaltung().verwaltung.value?.kalender?.map((k) => k.name), ['Neu'],
    'die überholte Antwort hat den Stand überschrieben')
  assert.equal(geteilt.gehoertZu(satzNeu), true, 'der jüngste Satz gilt nicht als beantwortet')
  assert.equal(geteilt.gehoertZu(satzAlt), false, 'ein überholter Satz gilt als beantwortet')
  geteilt.__setzeApiAufruf(null)
})
