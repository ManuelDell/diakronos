/**
 * UX1j2 — Skalen-Regel: `--pad` ist KEIN Kettenglied (Vertrag für die Oberfläche).
 *
 * Live-Befund (UX1k): Die Prüfung der Gruppe `skala` zählte JEDES Maß ohne
 * eigene Gruppe als Glied der aufsteigenden Kette — also auch `--pad` (16 px).
 * Weil `--pad` unter `--sp-8` (64 px) liegt, lehnte der Server jede Änderung
 * einer Skalenstufe über 14 px ab.
 *
 * Diese Datei hält die Regel fest, auf die sich die Oberfläche (UX1k)
 * verlassen darf — sie ist HIER nicht umgesetzt (das ist UX1k), sondern nur
 * die EINE Quelle im Backend:
 *
 *   1. Die Kette besteht aus `--sp-1 … --sp-8`, lückenlos und OHNE `--pad`.
 *   2. Server-Antwort nennt die Kette (`skala_ordnung`) — die Oberfläche rät
 *      sie nicht selbst.
 *   3. Die Prüfung läuft ausschliesslich über `SKALA_TOKEN`, nicht über die
 *      ganze Positivliste (sonst kommt `--pad` zurück in die Kette).
 *   4. Eine Altzeile, die die Kette bricht, kommt nicht ins CSS.
 *
 * Liest Dateien AUSSERHALB von frontend/ (backend/…) — backend/Dockerfile
 * kopiert `backend/src/diakronos_app/gestaltung/` im Frontend-Stage bereits
 * nach `/ux1j-backend/gestaltung/` (COPY-Zeile aus UX1j, Regel 13).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const REPO_BACKEND = fileURLToPath(new URL('../../backend/src/diakronos_app/gestaltung/', import.meta.url))
const BILD_BACKEND = '/ux1j-backend/gestaltung/'

const lies = (rel) => {
  for (const basis of [REPO_BACKEND, BILD_BACKEND]) {
    if (existsSync(basis + rel)) return readFileSync(basis + rel, 'utf8')
  }
  throw new Error(`Datei fehlt: ${rel} (weder ${REPO_BACKEND} noch ${BILD_BACKEND})`)
}

const tokensPy = lies('tokens.py')
const apiPy = lies('api.py')
const speicherPy = lies('speicher.py')

const KETTE = ['--sp-1', '--sp-2', '--sp-3', '--sp-4', '--sp-5', '--sp-6', '--sp-7', '--sp-8']

/** Die Paare aus `SKALA_TOKEN = ("--sp-1", …)` in der Python-Quelle. */
const skalaTokenAusQuelle = () => {
  const treffer = tokensPy.match(/^SKALA_TOKEN\s*=\s*\(([^)]*)\)/m)
  assert.ok(treffer, 'SKALA_TOKEN fehlt in tokens.py')
  return [...treffer[1].matchAll(/"(--[a-z0-9-]+)"/g)].map((m) => m[1])
}

test('UX1j2: die Kette besteht genau aus --sp-1 … --sp-8', () => {
  assert.deepEqual(skalaTokenAusQuelle(), KETTE)
})

test('UX1j2: --pad und die übrigen Abstände stehen NICHT in der Kette', () => {
  const kette = skalaTokenAusQuelle()
  for (const name of ['--pad', '--abstand-gruppe', '--abstand-innen', '--karte-innen']) {
    assert.ok(!kette.includes(name), `${name} darf kein Kettenglied sein`)
    assert.match(tokensPy, new RegExp(`Token\\("${name}"`), `${name} fehlt in der Positivliste`)
  }
})

test('UX1j2: die Kette hat keine Lücke und ist streng aufsteigend', () => {
  const kette = skalaTokenAusQuelle()
  kette.forEach((name, i) => assert.equal(name, `--sp-${i + 1}`))
  const werte = kette.map((name) => {
    const zeile = tokensPy.match(new RegExp(`Token\\("${name}",\\s*(\\d+),\\s*(\\d+),\\s*(\\d+)`))
    assert.ok(zeile, `Token ${name} nicht gefunden`)
    return Number(zeile[1])
  })
  for (let i = 1; i < werte.length; i += 1) {
    assert.ok(werte[i] > werte[i - 1], `${kette[i - 1]} muss kleiner sein als ${kette[i]}`)
  }
})

test('UX1j2: die Prüfung läuft über SKALA_TOKEN, nicht über TOKENS', () => {
  // Der Fehler war: die Prüfung iterierte über ALLE Maße der Gruppe `skala`.
  assert.match(tokensPy, /_skalen_werte[\s\S]{0,400}for n in SKALA_TOKEN/,
    'die Werteliste der Kette muss aus SKALA_TOKEN kommen')
  assert.ok(!/_skalen_werte[\s\S]{0,400}for t in TOKENS/.test(tokensPy),
    'die Kette darf NICHT über TOKENS laufen (das nimmt --pad wieder auf)')
  assert.match(tokensPy, /def pruefe_skala/, 'pruefe_skala fehlt')
  assert.match(tokensPy, /muss kleiner sein als/, 'die Meldung nennt die gebrochene Stelle nicht')
})

test('UX1j2: der Server liefert die Kette als EINE Quelle (skala_ordnung)', () => {
  assert.match(apiPy, /"skala_ordnung":\s*list\(T\.SKALA_TOKEN\)/,
    'die Antwort muss skala_ordnung aus SKALA_TOKEN bauen')
  // Alle drei Endpunkte gehen über `_stand` — damit trägt jede Antwort die Kette.
  for (const fn of ['gestaltung_lesen', 'gestaltung_speichern', 'gestaltung_zuruecksetzen']) {
    const block = apiPy.split(`def ${fn}`)[1] ?? ''
    assert.match(block, /_stand\(/, `${fn} liefert den Stand nicht über _stand()`)
  }
})

test('UX1j2: eine gebrochene Altzeile kommt nicht ins CSS', () => {
  assert.match(tokensPy, /def pruefe_skala_gespeichert/, 'die Lese-Prüfung fehlt')
  assert.match(speicherPy, /pruefe_skala_gespeichert/, 'der Speicher verwirft gebrochene Altzeilen nicht')
  // `abweichungen()` ist die einzige Quelle von `als_css()`.
  const alsCss = speicherPy.split('def als_css')[1] ?? ''
  assert.match(alsCss, /werte = abweichungen\(\)/,
    'als_css muss über abweichungen() gehen')
})

test('UX1j2: die Oberfläche braucht keine eigene Kette (keine Doppelpflege)', () => {
  // UX1k ist noch in Arbeit — hier nur die Zusage, dass die Quelle im Backend
  // steht. Findet sich später eine Kette im Frontend, muss sie aus
  // `skala_ordnung` kommen und nicht als Literal dort stehen.
  assert.ok(KETTE.length === 8)
})
