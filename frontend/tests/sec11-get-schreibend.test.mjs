/**
 * SEC-11 (C3) · WÄCHTER — kein GET-Aufruf an einen schreibenden Endpunkt.
 *
 * BEFUND (Opus-Review 2026-10-31, HOCH): `call_method` nahm GET/POST/PUT/PATCH
 * für JEDE whitelist-Funktion an. Ein Link
 * `GET {Präfix}/api/method/<schreibende_funktion>?…`, den ein angemeldeter
 * Admin auf einer fremden Seite anklickt, führte die Aktion aus.
 *
 * Im Backend ist das geschlossen (SEC-11/C1+C2): schreibende Endpunkte tragen
 * `@whitelist(methods=["POST"])`, alles andere endet mit 405. Damit darf im
 * Frontend NIEMALS ein GET an einen solchen Endpunkt gehen — sonst wäre die
 * Funktion für die SPA kaputt (405 statt Daten).
 *
 * Dieser Test ist die Gegenprobe. Er liest
 *   1. `backend/src/diakronos_app/frappe_compat/inventar/whitelist.json`
 *      (erzeugt von tools/whitelist_inventar.py; im Image per COPY-Zeile der
 *      `backend/Dockerfile` vorhanden, weil `docs/` in .dockerignore steht)
 *      für die Liste aller schreibenden Funktionsnamen,
 *   2. `frontend/src` nach Aufrufen, die bekanntermaßen GET schicken:
 *      `apiGet(<pfad>)` und `fetch(<adresse>, { ... })` OHNE `method: 'POST'`
 *      im selben Optionsobjekt.
 *
 * Läuft im Image (backend/Dockerfile) und lokal:
 *   node --test tests/sec11-get-schreibend.test.mjs
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const WURZEL = new URL('../', import.meta.url)
const SRC = new URL('src/', WURZEL)
const INVENTAR = new URL(
  '../backend/src/diakronos_app/frappe_compat/inventar/whitelist.json', WURZEL)

const SRC_PFAD = fileURLToPath(SRC)
const INVENTAR_PFAD = fileURLToPath(INVENTAR)

function alleQuellen(verzeichnis = '') {
  const pfad = new URL(verzeichnis, SRC)
  let ausgabe = []
  for (const eintrag of readdirSync(pfad)) {
    const kind = statSync(new URL(eintrag, pfad))
    if (kind.isDirectory()) {
      ausgabe = ausgabe.concat(alleQuellen(verzeichnis + eintrag + '/'))
    } else if (/\.(js|mjs|vue)$/.test(eintrag) && !/\.test\.mjs$/.test(eintrag)) {
      ausgabe.push(verzeichnis + eintrag)
    }
  }
  return ausgabe
}

/**
 * Schreibende Endpunkte als Name-Menge.
 *
 * Nötig sind nur die Funktionsnamen: die Aufrufer schreiben entweder den
 * vollen Frappe-Pfad (`diakronos.…api.mitglieder.set_mitglied_status`) oder
 * einen Kurzpfad — in beiden Fällen steht der Name am Ende.
 */
function schreibendeNamen() {
  assert.ok(existsSync(INVENTAR_PFAD),
    'inventar/whitelist.json fehlt — tools/whitelist_inventar.py laufen lassen')
  const daten = JSON.parse(readFileSync(INVENTAR_PFAD, 'utf8'))
  const namen = new Set()
  for (const eintrag of daten.eintraege) {
    if (eintrag.einstufung === 'schreibend') namen.add(eintrag.name)
  }
  return namen
}

/** Namen aus einem Methoden-Ausdruck (`API + 'create_mitglied'`, `pfad + name`). */
function endName(ausdruck) {
  const teile = ausdruck.split(/[.?]/).map((t) => t.trim()).filter(Boolean)
  return teile.length ? teile[teile.length - 1].replace(/[^\w]/g, '') : ''
}

/** Alle Quelltexte mit Zeilennummern. */
function quellzeilen() {
  const ausgabe = []
  for (const rel of alleQuellen()) {
    const text = readFileSync(new URL(rel, SRC), 'utf8')
    text.split('\n').forEach((zeile, i) => ausgabe.push({ datei: rel, nr: i + 1, zeile }))
  }
  return ausgabe
}

test('C3: kein apiGet auf einen schreibenden Endpunkt', () => {
  const schreibend = schreibendeNamen()
  const verstoesse = []
  for (const { datei, nr, zeile } of quellzeilen()) {
    if (/^\s*(\*|\/\/|\/\*)/.test(zeile)) continue
    const treffer = zeile.match(/apiGet\(\s*([^,)]+)/g) || []
    for (const t of treffer) {
      const name = endName(t.replace(/^apiGet\(\s*/, ''))
      if (schreibend.has(name)) verstoesse.push(`${datei}:${nr} apiGet(…${name}…)`)
    }
    // `apiGet(API + 'name')`
    const ohneName = zeile.match(/apiGet\([^)]*\+\s*['"]([^'"]+)['"]/)
    if (ohneName && schreibend.has(endName(ohneName[1]))) {
      verstoesse.push(`${datei}:${nr} apiGet(…${ohneName[1]}…)`)
    }
  }
  assert.deepEqual(verstoesse, [],
    'SEC-11/C3: diese Aufrufer schicken GET an einen POST-only-Endpunkt:\n  ' +
    verstoesse.join('\n  '))
})

test('C3: kein fetch ohne POST-Methode auf einen schreibenden Endpunkt', () => {
  const schreibend = schreibendeNamen()
  const verstoesse = []
  const zeilen = quellzeilen()
  for (let i = 0; i < zeilen.length; i++) {
    const { datei, nr, zeile } = zeilen[i]
    if (/^\s*(\*|\/\/|\/\*)/.test(zeile)) continue
    if (!/\bfetch\(/.test(zeile)) continue
    // Nur fetch-Aufrufe, deren Adresse eine Methode benennt (`apiUrl(…)`).
    const methode = zeile.match(/apiUrl\(\s*['"]([^'"]+)['"]\s*\)/)
      || zeile.match(/apiUrl\([^)]*\+\s*['"]([^'"]+)['"]/)
    if (!methode) continue
    const name = endName(methode[1])
    if (!schreibend.has(name)) continue
    // Die Options stehen meist in den folgenden Zeilen bis `)`.
    const block = zeilen.slice(i, i + 8).map((z) => z.zeile).join('\n')
    if (!/method:\s*['"](POST|PUT|PATCH|DELETE)['"]/i.test(block)) {
      verstoesse.push(`${datei}:${nr} fetch(apiUrl('${methode[1]}')) ohne POST`)
    }
  }
  assert.deepEqual(verstoesse, [],
    'SEC-11/C3: diese fetch-Aufrufer schicken GET an einen POST-only-Endpunkt:\n  ' +
    verstoesse.join('\n  '))
})

test('C3: apiCall schickt POST und den CSRF-Kopf (Gegenprobe)', () => {
  const text = readFileSync(new URL('diakonos/composables/useApi.js', SRC), 'utf8')
  assert.match(text, /export async function apiCall/,
    'useApi.js exportiert apiCall nicht mehr')
  const block = text.slice(text.indexOf('export async function apiCall'))
  assert.match(block.slice(0, 800), /method:\s*'POST'/,
    'apiCall schickt keinen POST mehr — dann trifft SEC-11/C1 jeden Aufrufer')
  assert.match(block.slice(0, 800), /'X-Frappe-CSRF-Token'/,
    'apiCall sendet den CSRF-Kopf nicht mehr')
})

test('C3: apiGet trägt KEINE schreibende Semantik (Gegenprobe)', () => {
  const text = readFileSync(new URL('diakonos/composables/useApi.js', SRC), 'utf8')
  const block = text.slice(text.indexOf('export async function apiGet'))
  assert.ok(block.length > 0, 'apiGet fehlt in useApi.js')
  // Kein `method:` im apiGet-Block = Browser-Default GET.
  assert.doesNotMatch(block.slice(0, 600), /method:\s*['"]POST['"]/,
    'apiGet schickt jetzt POST — dann ist der Name irreführend (C3)')
})

test('C3: Inventar nennt lesende und schreibende Endpunkte', () => {
  const daten = JSON.parse(readFileSync(INVENTAR_PFAD, 'utf8'))
  assert.ok(daten.zaehlung.schreibend > 100,
    `nur ${daten.zaehlung.schreibend} schreibende Endpunkte im Inventar`)
  assert.ok(daten.zaehlung.lesend > 100,
    `nur ${daten.zaehlung.lesend} lesende Endpunkte im Inventar`)
})

test('C3: die Prüfung sieht einen echten Verstoß (Selbsttest)', () => {
  // Ohne diesen Selbsttest wäre ein Wächter, der nie anschlägt, nicht von
  // einem Wächter zu unterscheiden, der nichts zu prüfen hat.
  const schreibend = schreibendeNamen()
  assert.ok(schreibend.has('set_mitglied_status'),
    'set_mitglied_status fehlt im Inventar — Wächter prüft ins Leere')
  const probe = "const x = await apiGet('diakronos.diakonos.api.mitglieder.set_mitglied_status')"
  const treffer = probe.match(/apiGet\(\s*([^,)]+)/)
  assert.ok(treffer, 'Selbsttest: apiGet-Muster erkennt den Aufruf nicht')
  assert.ok(schreibend.has(endName(treffer[1])),
    'Selbsttest: der Name wird nicht als schreibend erkannt')
})
