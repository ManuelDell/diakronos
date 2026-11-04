/**
 * UX3g — Ziele der Befehlspalette müssen im Router ankommen.
 *
 * Der Endpunkt `suche.global` liefert je Treffer `ziel: "#/…"`. Ein Tippfehler
 * im Ziel ist ein Treffer, der ins Nichts führt (Seite „nicht gefunden") — und
 * das fällt weder im Backend-Test noch im Browser sofort auf. Dieser Wächter
 * hält die vom Backend erzeugten Ziel-MUSTER gegen die Routen der SPA.
 *
 * Er liest ausschließlich Dateien INNERHALB von frontend/ — Regel 13 bleibt
 * damit erfüllt, keine zusätzliche COPY-Zeile im Image nötig.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const hier = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(resolve(hier, '..', rel), 'utf8')

const router = lies('src/diakonos/router.js')

/** Ziele, die `api/suche.py` erzeugt: [art, ziel, dynamisch?]. */
const ZIELE = [
  ['person', '#/mitglied/M-001', true],
  ['gruppe', '#/gruppe/G-1', true],
  ['termin', '#/kalender?termin=E-1', false],
  ['lied', '#/lieder/L-1', true],
  ['wiki', '#/wiki/W-1', true],
  ['beitrag', '#/beitraege?id=B-1', false],
  ['einstellung', '#/einstellungen/gemeinde', false],
]

test('jedes Ziel der Palette ist im Router bekannt', () => {
  for (const [art, ziel, dynamisch] of ZIELE) {
    const pfad = ziel.split('?')[0]
    if (dynamisch) {
      // Dynamische Routen stehen als Musterobjekte: { pattern: /^#\/mitglied\/(.+)$/, … }
      const segment = pfad.split('/')[1]
      assert.ok(
        router.includes(`/^#\\/${segment}\\/(.+)$/`),
        `${art}: für „${pfad}“ fehlt das Muster in dynamicRoutes (router.js)`,
      )
    } else {
      assert.ok(
        router.includes(`'${pfad}'`),
        `${art}: „${pfad}“ steht nicht in der Routentabelle (router.js)`,
      )
    }
  }
})

test('der Router reicht Abfrageteile an die Seite weiter', () => {
  // `#/kalender?termin=…` und `#/beitraege?id=…` verlassen sich darauf, dass
  // der VOLLE Hash (mit Abfrageteil) in `acceptedRoute` bleibt — wird er
  // abgeschnitten, verliert die Seite die Auswahl beim Öffnen über die Palette.
  assert.match(router, /zerlegeHash/, 'Router zerlegt die Adresse nicht mehr in Pfad + Abfrage')
  assert.match(
    router,
    /acceptedRoute\.value\s*=\s*\{\s*hash:\s*vollerHash/,
    'Router verwirft den Abfrageteil (acceptedRoute.hash ist nicht der volle Hash)',
  )
})

test('Seiten-Treffer der Palette zeigen Beschriftungen aus der Menüdefinition', () => {
  // Die Palette zeigt für Seiten den Menünamen (Prinzip N4: Seitentitel =
  // Menüname). Dieser Wächter hält fest, dass `menue.js` die eine Quelle der
  // Beschriftungen bleibt — eine zweite Wortliste in der Palette würde
  // auseinanderlaufen. Gelesen wird nur innerhalb von frontend/.
  const menue = lies('src/diakonos/menue.js')
  assert.match(menue, /export const MENUE/, 'Menüdefinition (MENUE) fehlt')
  assert.match(menue, /href:\s*'#\/einstellungen'/, 'Einstellungen fehlt im Menü')
})
