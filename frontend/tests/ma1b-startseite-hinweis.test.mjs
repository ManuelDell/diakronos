/**
 * MAIL-1b (N3): der Hinweis auf der ADMIN-STARTSEITE.
 *
 * Die Karte (S5) verlangt „Hinweis für System Manager auf der Admin-Startseite“.
 * MAIL-1 lieferte ihn nur bei den Löschanträgen und auf der Mailversand-Seite;
 * R-MAIL-1/N3 hat das als Abweichung vermerkt. Hier stehen die zwei Zusagen, die
 * am Quelltext pruefbar sind:
 *
 * 1. `Home.vue` zeigt den Hinweis der DSGVO-Kachel (System Manager) auch dann,
 *    wenn der Administrator sie sich ausgeblendet hat — sonst waere „die
 *    Startseite warnt“ eine unbelegbare Behauptung.
 * 2. Die Kachel ist im Katalog vorhanden, und ihr Hinweis haengt an
 *    `eingerichtet && darf_aendern` (nur System Manager, nur wenn es fehlt).
 * 3. Ohne Auskunft des Servers (Fehler) erscheint KEIN Hinweis — kein falsches
 *    „nicht eingerichtet“.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')

/** Quelltext ohne Kommentare — Aussagen ueber „es gibt kein X“ stehen dort. */
const liesCode = (pfad) => {
  const roh = lies(pfad)
  const ohneBloecke = roh.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  return ohneBloecke.replace(/^\s*\/\/.*$/gm, '')
}

// ── 1. Admin-Startseite ───────────────────────────────────────────────────

test('MAIL-1b: die Startseite haelt die System-Manager-Kachel auch ausgeblendet sichtbar', () => {
  const seite = liesCode('pages/Home.vue')
  assert.ok(seite.includes("const DSGVO_COMPLIANCE = 'dsgvo-compliance'"),
    'die Kachel hat eine benannte Kennung')
  assert.ok(seite.includes('function istErzwungen'),
    'erzwungene Kacheln entscheidet eine eigene Regel')
  assert.ok(seite.includes('widget.visible || istErzwungen(widget)'),
    'ausgeblendete Kacheln fallen nur weg, wenn sie nicht erzwungen sind')
  assert.ok(/:widgets="sichtbareWidgets"/.test(seite),
    'das Raster bekommt die Liste MIT der erzwungenen Kachel')
})

test('MAIL-1b: nur System Manager bekommen die Kachel aufgezwungen', () => {
  const seite = liesCode('pages/Home.vue')
  const block = seite.slice(seite.indexOf('function istErzwungen'),
    seite.indexOf('function istErzwungen') + 300)
  assert.ok(block.includes('widget_id === DSGVO_COMPLIANCE'), 'nur diese eine Kachel')
  assert.ok(block.includes('.isSystemManager'), 'und nur fuer System Manager')
  // Die Rolle kommt aus der Sitzung (Server-Boot), nicht aus einer festen Annahme.
  assert.ok(seite.includes('useSession'))
  // `useSession()` liefert `istSystemManager` erst seit MAIL-1b (aus `boot.roles`).
  assert.ok(liesCode('composables/useSession.js').includes('istSystemManager'))
})

// ── 2. Die Kachel selbst ─────────────────────────────────────────────────

test('MAIL-1b: die DSGVO-Kachel zeigt den Mailversand-Hinweis nur System Managern', () => {
  const kachel = liesCode('components/widgets/DsgvoComplianceWidget.vue')
  assert.ok(kachel.includes('mailversand_status'), 'Auskunft kommt vom Server')
  assert.ok(kachel.includes('darf_aendern'), 'nur wer aendern darf, sieht den Hinweis')
  assert.ok(kachel.includes('eingerichtet'), 'und nur wenn es fehlt')
  assert.ok(kachel.includes('#/einstellungen/mailversand'), 'mit Link auf die Seite')
  assert.ok(kachel.includes('Mailversand ist noch nicht eingerichtet'),
    'Wortlaut der Karte')
  // Keine Kontaktdaten des Postfachs auf der Startseite.
  for (const feld of ['host', 'absender', 'benutzername']) {
    assert.ok(!kachel.includes(feld + ':'), `kein ${feld} in der Kachel`)
  }
})

test('MAIL-1b: die Kachel steht im Katalog der Startseite', () => {
  const registry = liesCode('composables/useWidgetRegistry.js')
  assert.ok(registry.includes("'dsgvo-compliance'"), 'Widget-Kennung registriert')
  assert.ok(registry.includes('DsgvoComplianceWidget.vue'))
})
