import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * P3-4b/B2 — „ganze Tabellenzeile anklickbar" (Restpunkt 4).
 *
 * Der Namenslink wird per ::after über die ganze Zeile gedehnt. Das braucht
 * einen positionierten Vorfahren. Steht der Bezugsrahmen auf einer ZELLE oder
 * fehlt er ganz, greift der absolute Kasten der Linkfläche auf den nächsten
 * positionierten Vorfahren (den Hauptbereich) — dann liegt der Link der
 * ERSTEN Zeile unsichtbar über Kopfleiste, Suchfeld und Filtern und die Seite
 * ist nicht mehr bedienbar (Befund B2). Steht er auf jeder Zelle, deckt der
 * Kasten nur die Namenszelle ab; die übrigen Spalten reagieren nicht (W2).
 *
 * Deshalb: Bezugsrahmen = die ZEILE, in BEIDEN Tabellenarten
 * (`.dk-table` = Lieder/Adressbuch, `.dk-ui-table` = DkTable-Komponente),
 * und KEINE Positionierung auf Zellen.
 */
const root = new URL('../', import.meta.url)
const css = readFileSync(new URL('src/diakonos/index.css', root), 'utf8')

/** Regeln des Stilblatts ohne Kommentare, in Deklarationsblöcke zerlegt. */
function regeln() {
  const ohneKommentare = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const treffer = [...ohneKommentare.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
  return treffer.map(m => ({
    selektoren: m[1].split(',').map(s => s.trim().replace(/\s+/g, ' ')).filter(Boolean),
    koerper: m[2],
  }))
}

function hatPositionRelative(selektor) {
  return regeln().some(r => r.selektoren.includes(selektor) && /position:\s*relative/.test(r.koerper))
}

test('B2: Bezugsrahmen liegt an der Zeile — in beiden Tabellenarten', () => {
  assert.ok(hatPositionRelative('.dk-table tbody tr'),
    '.dk-table tbody tr braucht position:relative (Lieder-Tabelle)')
  assert.ok(hatPositionRelative('.dk-ui-table tbody tr'),
    '.dk-ui-table tbody tr braucht position:relative (DkTable/Mitglieder-Tabelle)')
})

test('B2/W2: keine Zelle ist Bezugsrahmen (sonst deckt die Linkflaeche nur eine Zelle)', () => {
  const zellen = ['.dk-table tbody td', '.dk-ui-table tbody td']
  for (const zelle of zellen) {
    assert.ok(!hatPositionRelative(zelle),
      `${zelle} darf nicht positioniert sein — sonst greift die Linkfläche nur dort`)
  }
})

test('B2: die gedehnte Linkflaeche bleibt ein ::after des Namenslinks', () => {
  const regel = regeln().find(r => r.selektoren.includes('a.dk-zellen-link.dk-zellen-link--dehnen::after'))
  assert.ok(regel, 'gedehnte Linkflaeche fehlt')
  assert.match(regel.koerper, /position:\s*absolute/)
  assert.match(regel.koerper, /inset:\s*0/)
})

test('B2: Bedienelemente in der Zeile bleiben über der Linkflaeche', () => {
  const regel = regeln().find(r => r.selektoren.some(s => s.endsWith('tbody tr button')))
  assert.ok(regel, 'Knoepfe in der Zeile brauchen position:relative; z-index:1')
  assert.match(regel.koerper, /position:\s*relative/)
  assert.match(regel.koerper, /z-index:\s*1/)
})

test('B2: beide Tabellenarten nutzen das gedehnte Linkmuster an der Namenszelle', () => {
  const mitglieder = readFileSync(new URL('src/diakonos/pages/Mitglieder.vue', root), 'utf8')
  const lieder = readFileSync(new URL('src/diakonos/pages/Lieder.vue', root), 'utf8')
  const muster = /class="[^"]*dk-zellen-link[^"]*dk-zellen-link--dehnen[^"]*"(?=[^>]*:href)/
  assert.match(mitglieder, muster, 'Mitglieder.vue: Namenslink ohne gedehnte Linkfläche')
  assert.match(lieder, muster, 'Lieder.vue: Namenslink ohne gedehnte Linkfläche')
})
