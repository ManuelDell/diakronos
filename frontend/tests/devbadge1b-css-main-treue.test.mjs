/**
 * DEVBADGE-1b — CSS-Wächter: ohne Dev-Eintrag ist der Handy-Kopf der main-Stand
 * (Review Opus, Punkt 3: „jede `.dk-app--handy`-Regel für Kopfzeile/Krumen ist
 * entweder gleich main oder trägt `.dk-app--dev`“).
 *
 * Verglichen wird gegen den main-Stand — aus `.git` (`git show main:…`), wenn
 * vorhanden; sonst (Image-Build ohne `.git`) gegen die eingefrorene Liste
 * `tools/main-kopfregeln.txt` (erzeugt von `node tools/main-kopfregeln.mjs
 * --schreiben`). Die Liste wird NICHT von Hand gepflegt.
 *
 * Geprüft wird je Regel des Bereichs „Kopfzeile/Krumen“:
 *
 *   C1  Jede Regel des Branch mit `.dk-app--handy` im Wähler trägt
 *       `.dk-app--dev` — ODER sie ist wortgleich mit main.
 *   C2  Keine main-Regel des Bereichs ist still ersetzt: sie steht entweder
 *       unverändert im Branch oder eine dev-gekoppelte Fassung übernimmt sie.
 *   C3  Der konkrete Befund aus dem Review (Krumen-Kasten) ist main-gleich.
 *
 * Kein Browser, kein Vue-Mount — reine Quelltext-Rechnung, läuft im Image mit.
 */
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
import test from 'node:test'

import { kopfRegeln, ausMain, ausListe, LISTE } from '../tools/main-kopfregeln.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const CSS = join(HIER, '..', 'src', 'diakonos', 'index.css')

const jetzt = kopfRegeln(readFileSync(CSS, 'utf8'))

/**
 * Der main-Stand: bevorzugt aus git (immer aktuell), sonst die eingefrorene
 * Liste. `quelle` steht im Fehlertext, damit man weiß, wogegen geprüft wurde.
 */
function mainStand() {
  try {
    return { regeln: ausMain(), quelle: 'git:main' }
  } catch {
    return { regeln: ausListe(), quelle: `Liste ${LISTE}` }
  }
}

const schluessel = (r) => `${r.media}|${r.waehler}`
const { regeln: mainRegeln, quelle } = mainStand()

test('DEVBADGE-1b · C0: der main-Stand liegt vor (git oder eingefrorene Liste)', () => {
  assert.ok(mainRegeln.length > 0, `keine main-Regeln (${quelle})`)
  assert.ok(mainRegeln.some((r) => r.waehler === '.dk-app--handy .dk-crumbs'),
    'die Liste enthält den Krumen-Kasten (Anker des Befunds)')
})

test('DEVBADGE-1b · C1: jede Kopfzeilen-Regel mit `.dk-app--handy` ist main-gleich oder dev-gekoppelt', () => {
  const nachSchluessel = new Map(mainRegeln.map((r) => [schluessel(r), r]))
  const verstoesse = []
  for (const r of jetzt) {
    if (!/\.dk-app--handy/.test(r.waehler)) continue
    if (/\.dk-app--dev/.test(r.waehler)) continue // gekoppelt: in Ordnung
    const gleich = nachSchluessel.get(schluessel(r))
    if (gleich && gleich.inhalt === r.inhalt) continue // identisch mit main
    verstoesse.push(`${r.media ? r.media + ' ' : ''}${r.waehler} { ${r.inhalt} }`)
  }
  assert.deepEqual(verstoesse, [],
    `Regeln ohne \`.dk-app--dev\`, die von main abweichen (${quelle}) — sie träfen ALLE Handy-Nutzer`)
})

test('DEVBADGE-1b · C2: keine main-Regel des Bereichs ist still ersetzt (Leck-Gegenprobe)', () => {
  const nachSchluessel = new Map(jetzt.map((r) => [schluessel(r), r]))
  const fehlend = []
  for (const r of mainRegeln) {
    const eigen = nachSchluessel.get(schluessel(r))
    if (eigen && eigen.inhalt === r.inhalt) continue // unverändert übernommen
    // Erlaubt: dieselbe Regel steht jetzt dev-gekoppelt.
    const devWaehler = r.waehler.replace(/^\.dk-app--handy /, '.dk-app--dev.dk-app--handy ')
    if (jetzt.some((k) => k.waehler === devWaehler && k.media === r.media && k.inhalt === r.inhalt)) continue
    // Erlaubt: eine unveränderte Handy-Regel ersetzt sie mit denselben
    // Eigenschaften (z. B. der Krumen-Kasten mit `flex: 1 1 auto` wie main).
    if (eigen && /\.dk-app--handy/.test(eigen.waehler) && !/\.dk-app--dev/.test(eigen.waehler)) {
      const eigenschaften = eigen.inhalt.split(';').map((t) => t.split(':')[0].trim()).filter(Boolean)
      const mainEigenschaften = r.inhalt.split(';').map((t) => t.split(':')[0].trim()).filter(Boolean)
      if (eigenschaften.every((e) => mainEigenschaften.includes(e))) continue
    }
    fehlend.push(`${r.media ? r.media + ' ' : ''}${r.waehler} { ${r.inhalt} }`)
  }
  assert.deepEqual(fehlend, [],
    `main-Regeln, die der Branch ohne Ersatz verändert (${quelle}) — ohne Dev-Modus sichtbar`)
})

test('DEVBADGE-1b · C3: der main-Stand des Krumen-Kastens ist unverändert (Anker)', () => {
  // Positiv-Nachweis am konkreten Befund aus dem Review: `flex: 1 1 auto`
  // (main) und KEIN `overflow: hidden` ohne Dev-Klausel.
  const krumen = jetzt.filter((r) => r.waehler === '.dk-app--handy .dk-crumbs')
  assert.equal(krumen.length, 1, 'genau EINE Handy-Regel für den Krumen-Kasten')
  assert.match(krumen[0].inhalt, /flex: 1 1 auto/, 'main-Stand: flex 1 1 auto')
  assert.ok(!/overflow/.test(krumen[0].inhalt), 'main-Stand: kein overflow-Beschnitt')
  const dev = jetzt.filter((r) => r.waehler === '.dk-app--dev.dk-app--handy .dk-crumbs')
  assert.equal(dev.length, 1, 'genau EINE dev-gekoppelte Krumen-Regel')
  assert.match(dev[0].inhalt, /overflow: hidden/, 'mit Dev: Beschnitt für den Titel')
  // Und der Titel bleibt auch ohne Dev fett (Review-Runde 2: `font-weight`
  // fiel beim Umbau weg — C2 hat es gefangen).
  const titel = jetzt.filter((r) => r.waehler === '.dk-app--handy .dk-crumb-current')
  assert.equal(titel.length, 1, 'genau EINE Handy-Regel für den Titel')
  assert.match(titel[0].inhalt, /font-weight: var\(--fw-fett\)/, 'main-Stand: Titel fett')
  assert.ok(!/ellipsis/.test(titel[0].inhalt), 'main-Stand: kein „…“-Beschnitt ohne Dev')
})
