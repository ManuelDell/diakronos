/**
 * DEV-B1 · Wächter: die Kalender-Abfrage der Termin-Dialoge trägt keine
 * Backslashes und die `fields` sind korrekt serialisiert.
 *
 * Befund DMB-da438eb70703 + DMB-734e07deb09b (Demo, 09.11.): `KronosEventCreate.vue`
 * und `KronosEventEdit.vue` bauten `Eventkategorie?fields=[\"name\",…]` — die
 * Backslashes landeten wörtlich in der Adresse, der Server antwortete 417, und
 * weil die Abrufe in `Promise.all` standen, riss der Fehler die Kalenderliste
 * mit: „Du hast auf keinen Kalender Schreibrecht“, obwohl das Recht da war
 * (Regression seit 22a7be28 / WEB-5b).
 *
 * Geprüft wird:
 *   A) Die fertige Adresse (so wie sie `fetch` bekommt) enthält KEINEN
 *      Backslash und gültiges JSON in `fields`.
 *   B) Kein `fields=[`-Literal mehr in `src/` — die Angabe läuft über
 *      `encodeURIComponent` (wie an allen anderen Aufrufstellen).
 *   C) Das Laden steht auf `Promise.allSettled`; ein Kalender-Ladefehler wird
 *      als solcher benannt statt als fehlendes Recht.
 *
 * Der Mount-Test (gerendertes DOM) liegt in `dev-b1-mount.test.mjs`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HIER, '../src')
const KRONOS = path.join(SRC, 'diakonos/components/kronos')

function quelle(name) {
  return readFileSync(path.join(KRONOS, name), 'utf8')
}

/** Die `fields` der Kategorie-Abfrage — wie sie im Code gebaut werden. */
function kategorieFelder(text, name) {
  const m = text.match(/Eventkategorie\?fields='\s*\+\s*encodeURIComponent\(([\s\S]*?)\)\s*\+\s*'&limit_page_length=500'/)
  assert.ok(m, `${name}: Kategorie-Abfrage mit encodeURIComponent(fields) nicht gefunden`)
  const argument = m[1].trim()
  assert.match(argument, /^'[^']*'$|^"[^"]*"$/, `${name}: fields-Argument ist kein Literal: ${argument}`)
  return argument.slice(1, -1)
}

function dateien(ordner) {
  const out = []
  for (const name of readdirSync(ordner)) {
    const abs = path.join(ordner, name)
    if (statSync(abs).isDirectory()) out.push(...dateien(abs))
    else if (/\.(vue|js|mjs)$/.test(name)) out.push(abs)
  }
  return out
}

for (const name of ['KronosEventCreate.vue', 'KronosEventEdit.vue']) {
  test(`DEV-B1 · ${name}: fields der Kategorie-Abfrage sind gültiges JSON ohne Backslash`, () => {
    const felder = JSON.parse(kategorieFelder(quelle(name), name))
    assert.deepEqual(felder, ['name', 'event_category_name'])
    // Die Adresse, die wirklich rausgeht — genau hier standen die Backslashes.
    const adresse = '/api/resource/Eventkategorie?fields=' + encodeURIComponent(kategorieFelder(quelle(name), name))
      + '&limit_page_length=500'
    assert.equal(adresse.includes('\\'), false, `Backslash in der fertigen Adresse: ${adresse}`)
    const feld = new URL('http://x' + adresse).searchParams.get('fields')
    assert.deepEqual(JSON.parse(feld), ['name', 'event_category_name'])
  })

  test(`DEV-B1 · ${name}: Laden nutzt Promise.allSettled und trennt Lade-Fehler von „kein Recht“`, () => {
    const text = quelle(name)
    const laden = text.slice(text.indexOf('async function loadData'), text.indexOf('async function checkConflict'))
    assert.match(laden, /Promise\.allSettled\(/, 'Promise.all reißt bei einem Fehler die Kalenderliste mit')
    assert.doesNotMatch(laden, /await Promise\.all\(/, 'Promise.all ist noch da')
    // Der Kalender-Zweig hat einen eigenen Fehlerzustand.
    assert.match(laden, /kalenderFehler\.value\s*=/, 'Lade-Fehler der Kalender wird nicht gemerkt')
    // Die Vorlage zeigt ihn als eigenen Fall (NICHT als „kein Schreibrecht“).
    assert.match(text, /v-if="kalenderFehler"/, 'Lade-Fehler wird in der Vorlage nicht gezeigt')
    assert.match(text, /Kalenderliste konnte nicht geladen werden/)
  })
}

test('DEV-B1: nirgends in src/ ein `fields=[`-Literal (Backslash-Falle)', () => {
  const verstoesse = []
  for (const abs of dateien(SRC)) {
    // Kommentare zählen nicht — dort steht `fields=[…]` als Prosa.
    const text = readFileSync(abs, 'utf8')
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
    text.split('\n').forEach((zeile, i) => {
      if (/fields=\[/.test(zeile)) verstoesse.push(`${path.relative(SRC, abs)}:${i + 1}: ${zeile.trim()}`)
    })
  }
  assert.deepEqual(verstoesse, [], 'fields-Angabe bitte über encodeURIComponent bauen:\n' + verstoesse.join('\n'))
})
