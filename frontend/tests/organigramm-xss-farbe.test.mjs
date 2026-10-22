/**
 * UXD-R5 / UXD-R28 / DES-04 — Organigramm und Gruppenkacheln.
 *
 * Beweist die Befunde der Nachtpruefung am echten Quelltext:
 *   UXD-R5   d3-org-chart bekommt HTML-Strings; Name/Treffzeit/Kennung
 *            muessen unmaskiert werden (sonst gespeichertes XSS). Gilt fuer
 *            BEIDE Renderer: diakonos/components/gruppen/OrganigrammAnsicht.vue
 *            UND die eigenstaendige organigramm/App.vue.
 *   UXD-R28  Die Dienstbereich-Farbe wird geprueft, ein Textwert wird nicht
 *            mehr gespeichert.
 *   DES-04   Die Gruppenkachel schreibt keinen Rohwert mehr in einen
 *            style-String; eine ungueltige Farbe ergibt die Standardfarbe
 *            statt einer weissen Leerkachel.
 *
 * Die sicheren Helfer liegen seit P0-5b in EINEM Modul
 * (src/shared/sichere-ausgabe.js) — dieser Test prueft genau dieses Modul, so
 * dass beide Renderer dieselbe Regel benutzen. Der Test liest die echten
 * Quelltexte (keine Kopie) — ein Rueckfall auf unsichere Interpolation faellt
 * damit sofort auf.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { escapeHtml, sichereFarbe, sichereBildUrl, STANDARD_FARBE } from '../src/shared/sichere-ausgabe.js'

const ORG = new URL('../src/diakonos/components/gruppen/OrganigrammAnsicht.vue', import.meta.url)
const ALT_APP = new URL('../src/organigramm/App.vue', import.meta.url)
const GRUPPEN = new URL('../src/diakonos/pages/Gruppen.vue', import.meta.url)

function scriptBlock(url) {
  const s = readFileSync(url, 'utf8')
  return s.split('<script setup>')[1].split('</script>')[0]
}

/**
 * Laedt einen <script setup>-Block mit den Importen der beiden Ausgabe-Helfer
 * und ersetzt die Vue-Importe durch Attrappen. `zusatz` haengt weitere
 * Globals an, die der Block beim Auswerten braucht.
 *
 * Die sicheren Helfer werden NICHT nachgebaut, sondern aus dem echten Modul
 * importiert — so prueft der Test genau den Code, den auch die Oberflaeche
 * benutzt (keine Test-Kopie, die auseinanderlaufen koennte).
 */
async function ladeRenderer(url, { exporte, zusatz = '' }) {
  let code = scriptBlock(url)
  // Nur die Vue-/Fremd-Importe entfernen; der Import der sicheren Helfer wird
  // durch einen echten Import aus dem Modul ersetzt.
  code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
  const modulUrl = new URL('../src/shared/sichere-ausgabe.js', import.meta.url).href
  code = `
import { escapeHtml, sichereFarbe, sichereBildUrl, STANDARD_FARBE } from ${JSON.stringify(modulUrl)};
const ref = (v) => ({ value: v });
const computed = (f) => ({ get value() { return f() } });
const onMounted = () => {};
const onBeforeUnmount = () => {};
const nextTick = () => Promise.resolve();
// In <script setup> stellt Vue defineProps/onBeforeUnmount bereit; die Attrappen
// genuegen, weil dieser Test nur die reinen Ausgabe-Funktionen prueft.
const defineProps = () => ({});
const OrgChart = function () {};
const apiCall = async () => ({});
globalThis.window = globalThis.window || {};
${zusatz}
${code}
export { ${exporte.join(', ')} };
`
  return import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
}

async function ladeGruppenFarbe() {
  let code = scriptBlock(GRUPPEN)
  code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
  code = `
const ref = (v) => ({ value: v });
const computed = (f) => ({ get value() { return f() } });
const onMounted = () => {};
const defineProps = () => ({});
const watch = () => {};
const navigate = () => {};
const currentHash = { value: '#/gruppen' };
${code}
export { kachelFarbe };
`
  return import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
}

// ── UXD-R5: kein HTML aus Gruppendaten (Organigramm-Ansicht in Gruppen) ─────

test('UXD-R5: Gruppenname wird als Text ausgegeben, nicht als HTML', async () => {
  const m = await ladeRenderer(ORG, { exporte: ['buildNodeContent'] })
  const html = m.buildNodeContent({
    width: 190,
    height: 72,
    data: { id: 'g_XSS', type: 'gruppe', name: 'NACHT-RUXD <img src=x onerror="window.__xss=1">Gruppe' },
  })
  assert.ok(!html.includes('<img'), `Rohes <img> im Knoten: ${html}`)
  assert.ok(html.includes('&lt;img'), 'Name muss entity-kodiert sein')
  assert.ok(!html.includes('onerror="window.__xss=1"'), 'Skript-Attribut darf nicht roh vorkommen')
})

test('UXD-R5: Treffzeit und Kennung werden ebenfalls unmaskiert', async () => {
  const m = await ladeRenderer(ORG, { exporte: ['buildNodeContent'] })
  const html = m.buildNodeContent({
    width: 190,
    height: 72,
    data: {
      id: "g_';window.__xss=1;//",
      type: 'gruppe',
      name: 'Team',
      treffzeit: '<b id="nacht-ruxd-zeit">20:00</b>',
    },
  })
  assert.ok(html.includes('&lt;b'), 'Treffzeit muss entity-kodiert sein')
  assert.ok(!html.includes('<b id='), 'kein rohes Markup aus der Treffzeit')
  // Die Kennung darf das Attribut nicht verlassen: Anfuehrungszeichen sind
  // entity-kodiert, ein roher Ausbruch (')kaeme sonst im onclick vor.
  assert.ok(!html.includes("')window"), 'Kennung darf nicht aus dem Attribut ausbrechen')
  assert.ok(html.includes('&quot;') && html.includes('&#39;'), 'Anfuehrungszeichen entity-kodiert')
})

// ── UXD-R5: zweiter Renderer organigramm/App.vue ────────────────────────────

test('UXD-R5: zweiter Renderer (App.vue) kodiert Name/Leiter/Typ/Rolle', async () => {
  const m = await ladeRenderer(ALT_APP, {
    exporte: ['nodeContent'],
    // window.__diakronos wird beim Auswerten des Blocks gelesen.
    zusatz: "globalThis.window.__diakronos = {}; globalThis.document = { querySelector: () => null };",
  })
  const html = m.nodeContent({
    data: {
      node_type: 'gruppe',
      name: '<img src=x onerror="window.__xss=1">',
      leiter: '<script>window.__xss=2</script>',
      gruppentyp: '<b onmouseover="x()">Chor</b>',
      member_count: '7',
    },
  })
  assert.ok(!html.includes('<img'), 'Name darf kein rohes <img> erzeugen')
  assert.ok(!html.includes('<script'), 'Leiter darf kein rohes <script> erzeugen')
  assert.ok(!html.includes('<b onmouseover'), 'Gruppentyp darf kein rohes Markup erzeugen')
  assert.ok(html.includes('&lt;img') && html.includes('&lt;script'), 'Werte sind entity-kodiert')
})

test('UXD-R5: zweiter Renderer laesst nur http(s)/relative Foto-URLs zu', async () => {
  const m = await ladeRenderer(ALT_APP, {
    exporte: ['nodeContent'],
    zusatz: "globalThis.window.__diakronos = {}; globalThis.document = { querySelector: () => null };",
  })
  const mitglied = (foto) => m.nodeContent({
    data: { node_type: 'mitglied', name: 'Anna & Co', rolle: 'Sopran', foto },
  })

  // Erlaubt: http(s) und relative Pfade.
  assert.ok(mitglied('https://cloud.example/foto.jpg').includes('src="https://cloud.example/foto.jpg"'))
  assert.ok(mitglied('/uploads/foto.jpg').includes('src="/uploads/foto.jpg"'))
  assert.ok(mitglied('./foto.jpg').includes('src="./foto.jpg"'))

  // Verworfen: Skript-/Daten-URLs und protokoll-relative Hosts.
  for (const boese of [
    'javascript:window.__xss=1',
    'JaVaScRiPt:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    '//evil.example/foto.jpg',
    '" onerror="window.__xss=1',
  ]) {
    const html = mitglied(boese)
    assert.ok(!html.includes('<img'), `Foto-URL "${boese}" muss verworfen werden: ${html}`)
    // Ohne gueltige URL bleibt der Initialen-Kreis.
    assert.ok(html.includes('oc-mitglied-avatar'), `Ersatzkreis fehlt bei "${boese}"`)
  }
})

test('UXD-R5: zweiter Renderer kodiert den alternativen Text (alt)', async () => {
  const m = await ladeRenderer(ALT_APP, {
    exporte: ['nodeContent'],
    zusatz: "globalThis.window.__diakronos = {}; globalThis.document = { querySelector: () => null };",
  })
  const html = m.nodeContent({ data: { node_type: 'mitglied', name: 'x" onerror="y', foto: '/a.jpg' } })
  assert.ok(!html.includes('alt="x" onerror'), 'Name darf nicht aus dem alt-Attribut ausbrechen')
  assert.ok(html.includes('alt="x&quot; onerror=&quot;y"'), 'alt-Text muss entity-kodiert sein')
})

// ── UXD-R5 / UXD-R28: die gemeinsamen Helfer (shared/sichere-ausgabe.js) ────

test('UXD-R5: escapeHtml deckt alle fuenf Sonderzeichen', () => {
  assert.equal(escapeHtml(`&<>"'`), '&amp;&lt;&gt;&quot;&#39;')
})

test('UXD-R5: escapeHtml entschaerft "><script>, javascript: und expression()', () => {
  // "><script> — Ausbruch aus einem Attribut- und Tag-Kontext.
  assert.equal(
    escapeHtml('"><script>window.__xss=1</script>'),
    '&quot;&gt;&lt;script&gt;window.__xss=1&lt;/script&gt;',
  )
  // javascript:-URL bleibt als Text, aber ohne ausfuehrbaren Kontext.
  assert.equal(escapeHtml('javascript:alert(1)'), 'javascript:alert(1)')
  assert.ok(!escapeHtml('javascript:alert(1)').includes('<'))
  // expression() (Alt-IE-CSS) — die Klammern bleiben, aber der Wert ist ein
  // reiner Text und kann nicht als CSS durchkommen (sichereFarbe verwirft ihn).
  assert.equal(escapeHtml('expression(alert(1))'), 'expression(alert(1))')
  assert.equal(sichereFarbe('expression(alert(1))'), '')
})

test('UXD-R28: sichereFarbe laesst nur Hex-Werte durch, sonst leer', () => {
  assert.equal(sichereFarbe('#3b82f6'), '#3b82f6')
  assert.equal(sichereFarbe('#abc'), '#abc')
  assert.equal(sichereFarbe('zzz-keine-farbe'), '')
  assert.equal(sichereFarbe('red;background-image:url(x)'), '')
  assert.equal(sichereFarbe('3b82f6'), '', 'ohne # ist kein gueltiger CSS-Wert')
})

test('UXD-R5: sichereBildUrl verwirft Skript- und Daten-URLs', () => {
  assert.equal(sichereBildUrl('https://x.example/a.png'), 'https://x.example/a.png')
  assert.equal(sichereBildUrl('/a.png'), '/a.png')
  assert.equal(sichereBildUrl('javascript:alert(1)'), '')
  assert.equal(sichereBildUrl('data:image/svg+xml,<svg onload=alert(1)>'), '')
  assert.equal(sichereBildUrl('//evil.example/a.png'), '')
  assert.equal(sichereBildUrl(''), '')
})

test('UXD-R28: ungueltige Farbe erzeugt keinen border-left im Knoten', async () => {
  const m = await ladeRenderer(ORG, { exporte: ['buildNodeContent'] })
  const html = m.buildNodeContent({
    width: 200, height: 60,
    data: { id: 'db_A', type: 'dienstbereich', name: 'A', farbe: 'red;background-image:url(x)' },
  })
  assert.ok(!html.includes('border-left:3px solid red'), 'roher CSS-Wert darf nicht in den style-String')
  assert.ok(!html.includes('background-image'), 'Fremd-CSS darf nicht durchkommen')
})

test('DES-04: Gruppenkachel nutzt bei ungueltiger Farbe die Standardfarbe', async () => {
  const m = await ladeGruppenFarbe()
  assert.equal(m.kachelFarbe({ dienstbereich_farbe: '#3b82f6' }), '#3b82f6')
  assert.equal(m.kachelFarbe({ dienstbereich_farbe: 'zzz-keine-farbe' }), '#667eea')
  assert.equal(m.kachelFarbe({ dienstbereich_farbe: 'x;background-image:url(y)' }), '#667eea')
  assert.equal(m.kachelFarbe({}), '#667eea')
})

test('UXD-R28: Farbwaehler-Startwert faellt auf Hex zurueck, nie auf leer', async () => {
  // Kein Token (kein getComputedStyle) und ein oklch()-Token: der Waehler
  // braucht zwingend #RRGGBB, sonst zeigt er Schwarz.
  const ohneToken = await ladeRenderer(ORG, {
    exporte: ['standardFarbe'],
    zusatz: 'delete globalThis.getComputedStyle;',
  })
  assert.equal(ohneToken.standardFarbe(), STANDARD_FARBE)

  const oklchToken = await ladeRenderer(ORG, {
    exporte: ['standardFarbe'],
    zusatz: "globalThis.getComputedStyle = () => ({ getPropertyValue: () => 'oklch(0.7 0.1 240)' });",
  })
  assert.equal(oklchToken.standardFarbe(), STANDARD_FARBE)

  const hexToken = await ladeRenderer(ORG, {
    exporte: ['standardFarbe'],
    zusatz: "globalThis.getComputedStyle = () => ({ getPropertyValue: () => '#3b82f6' });",
  })
  assert.equal(hexToken.standardFarbe(), '#3b82f6')
})

// ── UXD-R28 (P1-5b): Kronos-Farb-Bindings ──────────────────────────────────
//
// Nachtbefund R-P0-5b (Punkt 7): ModerationCard.vue, ModerationModals.vue,
// UpcomingEventsWidget.vue, KronosSeriesDialog.vue und KronosSidebar.vue
// schrieben `calendar_color`/`element_color`/`color` roh in einen style-String
// bzw. in eine CSS-Variable. Ein Altbestand wie `red;background-image:url(..)`
// oder `url(javascript:..)` landete damit als CSS in der Seite. Der Test liest
// die echten Quelltexte: ein Rueckfall auf die rohe Interpolation faellt auf.

const KRONOS_FARBQUELLEN = [
  ['ModerationCard.vue', new URL('../src/diakonos/components/kronos/ModerationCard.vue', import.meta.url)],
  ['ModerationModals.vue', new URL('../src/diakonos/components/kronos/ModerationModals.vue', import.meta.url)],
  ['UpcomingEventsWidget.vue', new URL('../src/diakonos/components/widgets/UpcomingEventsWidget.vue', import.meta.url)],
  ['KronosSeriesDialog.vue', new URL('../src/diakonos/components/kronos/KronosSeriesDialog.vue', import.meta.url)],
  ['KronosSidebar.vue', new URL('../src/diakonos/components/kronos/KronosSidebar.vue', import.meta.url)],
  // W-C (R-P1-8): KronosDayEventsDialog.vue und KronosEventView.vue trugen
  // eine eigene `safeColor`-Kopie mit abweichendem Muster (`/^var\(/` erlaubte
  // rohe `var(...)`-Werte). Jetzt laufen beide ueber die EINE Quelle.
  ['KronosDayEventsDialog.vue', new URL('../src/diakonos/components/kronos/KronosDayEventsDialog.vue', import.meta.url)],
  ['KronosEventView.vue', new URL('../src/diakonos/components/kronos/KronosEventView.vue', import.meta.url)],
]

for (const [name, url] of KRONOS_FARBQUELLEN) {
  test(`UXD-R28: ${name} bindet die Farbe nur ueber sichereFarbe`, () => {
    const quelle = readFileSync(url, 'utf8')
    assert.ok(quelle.includes("shared/sichere-ausgabe.js"),
      `${name} importiert sichereFarbe nicht`)
    // W-C: keine eigene Farb-Hilfsfunktion mehr (nur die gemeinsame Quelle).
    assert.ok(!/function\s+safeColor\s*\(/.test(quelle),
      `${name} hat weiterhin eine eigene safeColor-Funktion`)
    // Jede Verwendung der bekannten Farbfelder MUSS durch sichereFarbe laufen.
    for (const feld of ['calendar_color', 'element_color']) {
      const roh = new RegExp(`background:\\s*(item\\.|eventData\\?\\.|seriesGroup\\?\\.)?${feld}`)
      assert.ok(!roh.test(quelle),
        `${name} schreibt ${feld} roh in den style-String`)
    }
    assert.ok(!/background:\s*item\.calendar_color/.test(quelle),
      `${name} bindet item.calendar_color ungeschuetzt`)
  })
}

test('UXD-R28: eine ungueltige Farbe wird von sichereFarbe verworfen', () => {
  assert.equal(sichereFarbe('red;background-image:url(x)'), '')
  assert.equal(sichereFarbe('url(javascript:alert(1))'), '')
  assert.equal(sichereFarbe('#3b82f6'), '#3b82f6')
  assert.equal(sichereFarbe('#abc'), '#abc')
})
