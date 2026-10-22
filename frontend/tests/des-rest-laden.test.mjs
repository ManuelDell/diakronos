/**
 * OP-UI-19 · Laden und Leerzustände (Standard S10).
 *
 * Befund: Beim Laden blieb die alte Seite stehen, Platzhalter wie „0“ und
 * „Unbekannt“ täuschten Inhalt vor, es gab sechs Ladeformen, und die
 * Leerzustände sagten das Falsche (Beiträge: „Suche oder Filter anpassen.“
 * bei 0 Beiträgen).
 *
 * Festlegung: EINE Ladeform (`DkSkelett`), keine Zahl vor dem Laden,
 * `DkEmpty` mit getrennten Fällen (kein Treffer / noch nichts da / gesucht).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const ohneKommentare = (q) => String(q)
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

test('OP-UI-19 · der Baustein DkSkelett existiert und wird für das Laden benutzt', () => {
  const pfad = new URL('../src/diakonos/components/ui/DkSkelett.vue', import.meta.url)
  assert.ok(existsSync(pfad), 'DkSkelett fehlt')
  assert.match(readFileSync(pfad, 'utf8'), /role="status"/)
  for (const seite of ['pages/Gruppen.vue', 'pages/Lieder.vue', 'pages/Beitraege.vue',
    'pages/Ressourcen.vue', 'pages/GruppeDetail.vue', 'pages/LiedDetail.vue', 'pages/Registrierung.vue']) {
    assert.match(lies(seite), /<DkSkelett/, `${seite} nutzt die gemeinsame Ladeform nicht`)
  }
})

test('OP-UI-19 · kein nacktes „Lade…“ mehr auf den umgestellten Seiten', () => {
  for (const seite of ['pages/Gruppen.vue', 'pages/LiedDetail.vue', 'pages/GruppeDetail.vue']) {
    assert.ok(
      !/>\s*Lade\b/.test(ohneKommentare(lies(seite))),
      `${seite} zeigt noch einen nackten Lade-Text statt eines Skeletts`,
    )
  }
})

test('OP-UI-19 · Beiträge: Leertext unterscheidet Suche und leeren Bestand', () => {
  const quelle = lies('pages/Beitraege.vue')
  assert.ok(!/'Suche oder Filter anpassen\.\.\.\.'|text: 'Suche oder Filter anpassen\.'/.test(quelle),
    'Der alte Leertext „Suche oder Filter anpassen.“ ist zurück')
  assert.match(quelle, /Noch keine Beiträge/)
  assert.match(quelle, /filterZuruecksetzen/)
})

test('OP-UI-19 · Ressourcen: keine Zahl im Seitenkopf, solange geladen wird', () => {
  const quelle = lies('pages/Ressourcen.vue')
  assert.ok(!/:sub="filteredCount \+ ' Räume/.test(quelle), 'Zähler steht wieder fest im Seitenkopf')
  assert.match(quelle, /kopfUntertitel/)
  assert.match(quelle, /if \(loading\.value\) return 'Räume & Gegenstände werden geladen …'/)
  // Der Zähler startet als „lädt", damit nicht kurz „0“ erscheint.
  assert.match(quelle, /const loading = ref\(true\)/)
})

test('OP-UI-19 · Gruppen: „Unbekannt“ ist kein Dienstbereichsname mehr', () => {
  const quelle = lies('pages/Gruppen.vue')
  assert.ok(!/\|\| 'Unbekannt'/.test(ohneKommentare(quelle)), 'erfundener Name „Unbekannt“ ist zurück')
})

test('OP-UI-19/S8 · UI-Bausteine stehen im README', () => {
  const readme = lies('components/ui/README.md')
  assert.match(readme, /`DkDatumZeit`/, 'DkDatumZeit fehlt im README')
  assert.match(readme, /`DkSkelett`/, 'DkSkelett fehlt im README')
  assert.match(readme, /`DkFilterChips`/, 'DkFilterChips fehlt im README')
  assert.match(readme, /`DkEmpty`/, 'DkEmpty steht nicht im README')
})
