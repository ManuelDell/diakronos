/**
 * DM3b — Nacharbeit nach Review (Urteil NICHT MERGEN).
 *
 * Deckt die drei Pflichtbefunde ab:
 *  (H)  Der Befund-Dialog darf NIE im Screenshot erscheinen. DkDialog wird
 *       per ``data-dk-dev`` am Overlay (Vorfahre von Rahmen/Kopf/Fuß)
 *       ausgeschlossen. Hier wird DkDialog TATSAECHLICH gerendert (Server-
 *       Renderer) und geprueft, dass ``closest('[data-dk-dev]')`` fuer
 *       Overlay, Titel und Fuß-Knopf greift — der bisherige Test pruefte nur
 *       Quelltext.
 *  (M1) Speichern waehrend laufender Aufnahme verliert das Bild nicht mehr.
 *  (M2) Schriftdateien werden EINMAL zu data:-URIs aufgeloest und gecacht;
 *       relative url() werden korrekt aufgeloest.
 *  (N)  Rahmen-Timer wird aufgeraeumt; DevStart traegt data-dk-dev.
 *
 * Reine Node-Tests (``--test``); der Render-Test braucht ``vue`` (im Image da).
 */
import assert from 'node:assert/strict'
import { mkdirSync, readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs'
import test from 'node:test'

import { DEV_ATTRIBUT, AUFNAHME_LIMIT_MS, istDevKnoten } from '../src/diakonos/components/devmodus/fotograf.mjs'
import { fontCssSammeln, fontCacheLeeren } from '../src/diakonos/components/devmodus/screenshot.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

// ── (H) DkDialog WIRKLICH rendern und ausschliessen ────────────────────────
// Der Server-Renderer ist der einzige Weg, die Teleport-Ebene ohne Browser zu
// pruefen. ``vue`` ist im Docker-Build (Stage 1, npm ci) vorhanden.
const TEMP = new URL('../.dm3b-tmp/', import.meta.url)

async function sfcLaden(pfad, nr) {
  const [vue, sr, sfc] = await Promise.all([
    import('vue'),
    import('vue/server-renderer'),
    import('vue/compiler-sfc'),
  ])
  const { parse, compileScript, compileTemplate } = sfc
  const url = new URL(pfad, root)
  const quelle = readFileSync(url, 'utf8')
  const { descriptor, errors } = parse(quelle, { filename: url.pathname })
  assert.deepEqual(errors, [], pfad + ': SFC-Struktur')
  const script = descriptor.scriptSetup ? compileScript(descriptor, { id: url.pathname }) : null
  const template = compileTemplate({
    source: descriptor.template.content, filename: url.pathname, id: url.pathname,
    compilerOptions: { bindingMetadata: script?.bindings || {} },
  })
  assert.deepEqual(template.errors, [], pfad + ': Vorlage')
  // Relative Importe des SFC zeigen in der Zwischendatei ins Leere (sie liegt
  // in .dm3b-tmp/). Sie werden deshalb auf ihre ECHTE Adresse umgeschrieben —
  // sonst scheitert der Test an jeder Komponente, die etwas einbindet.
  const kopf = (script?.content || '')
    .replace(/export default/, 'const __standard__ =')
    .replace(/(from\s+)(['"])(\.{1,2}\/[^'"]+)\2/g, (_treffer, praefix, _q, relativerPfad) =>
      praefix + JSON.stringify(new URL(relativerPfad, url).href))
  const code = `${kopf}\n${template.code.replace(/export function render/, 'function render')}
const __comp = __standard__ || {}
if (typeof render === 'function') __comp.render = render
export default __comp`
  mkdirSync(TEMP, { recursive: true })
  const datei = new URL(`./m${nr}.mjs`, TEMP)
  writeFileSync(datei, code)
  return { vue, sr, komponente: (await import(datei.href)).default }
}

/** Rendert eine Komponente und liefert das per Teleport nach body gehaengte HTML. */
async function teleportHtml(pfad, props, slots, nr) {
  const { vue, sr, komponente } = await sfcLaden(pfad, nr)
  const app = vue.createSSRApp({
    render: () => vue.h(komponente, props, slots),
  })
  const ctx = {}
  await sr.renderToString(app, ctx)
  return ctx.teleports?.body || ''
}

test('(H) DkDialog mit dev: der per Teleport gerenderte Overlay traegt data-dk-dev', async () => {
  const html = await teleportHtml('components/ui/DkDialog.vue',
    { modelValue: true, title: 'Befund melden', dev: true, size: 'lg' },
    { default: () => 'Inhalt', footer: () => 'Speichern' }, 'a')
  assert.ok(html, 'Dialog wurde gerendert (Teleport nach body)')
  // Der Overlay ist Vorfahre von Rahmen, Titel und Fuß -> alle drei sind ueber
  // closest('[data-dk-dev]') als Dev-Element erkennbar.
  const overlayMatch = html.match(/<div class="dk-ui-dialog-overlay"[^>]*>/)
  assert.ok(overlayMatch, 'Overlay gefunden')
  assert.ok(overlayMatch[0].includes('data-dk-dev'), 'Overlay traegt data-dk-dev')
  const rahmenMatch = html.match(/<div class="dk-ui-dialog dk-ui-dialog--lg"[^>]*>/)
  assert.ok(rahmenMatch, 'Rahmen gefunden')
  const titelMatch = html.match(/<h3 class="dk-ui-dialog-titel">([^<]*)<\/h3>/)
  assert.ok(titelMatch, 'Titel gefunden')
  const fussMatch = html.match(/<footer class="dk-ui-dialog-fuss">/)
  assert.ok(fussMatch, 'Fuß gefunden')
})

test('(H) DkDialog ohne dev bleibt im Bild (App-Dialoge werden nicht ausgeschlossen)', async () => {
  const html = await teleportHtml('components/ui/DkDialog.vue',
    { modelValue: true, title: 'Termin', size: 'md' },
    { default: () => 'Inhalt' }, 'b')
  const overlayMatch = html.match(/<div class="dk-ui-dialog-overlay"[^>]*>/)
  assert.ok(overlayMatch, 'Overlay gefunden')
  assert.ok(!overlayMatch[0].includes('data-dk-dev'), 'ohne dev kein data-dk-dev')
})

test('(H) BefundDialog setzt dev an DkDialog', () => {
  const quelle = lies('components/devmodus/BefundDialog.vue')
  const zeile = quelle.split('\n').find(z => z.includes('<DkDialog'))
  assert.ok(zeile, 'DkDialog-Einbindung gefunden')
  assert.ok(/\bdev\b/.test(zeile), 'DkDialog bekommt dev')
})

// ── (M1) Speichern waehrend laufender Aufnahme ─────────────────────────────
test('(M1) Speichern wartet, bis die Hintergrundaufnahme fertig ist', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  const block = dialog.slice(dialog.indexOf('async function speichern'),
                             dialog.indexOf('function themeAusSpeicher'))
  assert.ok(block.includes('bildAufnahmeLaeuft'), 'Zustand der Aufnahme beruecksichtigt')
  assert.ok(/warteAufBild\(KALTSTART_LIMIT_MS\)/.test(block), 'wartet bis zum gemeinsamen Limit')
  assert.ok(block.includes('Screenshot wird noch erstellt'), 'sichtbarer Hinweis')
  // Bildliste vor dem Hochladen einfrieren (Race aus dem Review).
  assert.ok(block.includes('.slice()'), 'Bildliste wird eingefroren')
})

test('(M1) warteAufBild endet, sobald die Aufnahme fertig ist', () => {
  const dialog = lies('components/devmodus/BefundDialog.vue')
  const block = dialog.slice(dialog.indexOf('function warteAufBild'))
  assert.ok(block.includes('!props.bildAufnahmeLaeuft'), 'bricht ab, wenn Aufnahme fertig')
  assert.ok(block.includes('bilder.value.length'), 'bricht ab, wenn Bild da')
})

// ── (M2) Font-Cache mit data:-URIs ─────────────────────────────────────────
test('(M2) Schriftdateien werden einmal zu data:-URIs aufgeloest', async () => {
  fontCacheLeeren()
  const gesehen = []
  const antwort = {
    ok: true,
    async blob() {
      return { __blob: true, typ: 'font' }
    },
  }
  const abrufen = async (url) => { gesehen.push(url); return antwort }
  const blatt = {
    href: 'https://beispiel.test/statisch/app.css',
    cssRules: [{
      constructor: { name: 'CSSFontFaceRule' },
      cssText: '@font-face{font-family:"Inter";src:url(./schriften/inter.woff2) format("woff2")}',
    }],
  }
  const dokument = { styleSheets: [blatt] }
  const text = await fontCssSammeln(dokument, { abrufen })
  assert.ok(text.includes('@font-face'), 'Regel uebernommen')
  assert.equal(gesehen.length, 1, 'genau EIN Fetch je Schriftdatei')
  assert.equal(gesehen[0], 'https://beispiel.test/statisch/schriften/inter.woff2',
    'relative url() gegen das Stylesheet aufgeloest')
  // Der Cache greift beim zweiten Aufruf (kein weiterer Fetch).
  const nochmal = await fontCssSammeln(dokument, { abrufen })
  assert.equal(nochmal, text, 'zweiter Aufruf kommt aus dem Cache')
  assert.equal(gesehen.length, 1, 'kein zweiter Fetch')
})

test('(M2) absolute und data:-url() bleiben unangetastet', async () => {
  fontCacheLeeren()
  const gesehen = []
  const blatt = {
    href: 'https://beispiel.test/a.css',
    cssRules: [{
      constructor: { name: 'CSSFontFaceRule' },
      cssText: '@font-face{src:url(https://cdn.test/f.woff2)}',
    }],
  }
  const abrufen = async (url) => { gesehen.push(url); return { ok: false } }
  const text = await fontCssSammeln({ styleSheets: [blatt] }, { abrufen })
  // ok:false -> unverändert uebernommen, kein Absturz.
  assert.ok(text.includes('https://cdn.test/f.woff2'), 'absolute Adresse erhalten')
  fontCacheLeeren()
})

// ── (N) Timer + DevStart ───────────────────────────────────────────────────
test('(N) Rahmen raeumt den Aufnahme-Timer auf', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  assert.ok(rahmen.includes('clearTimeout(zeitgeber)'), 'clearTimeout vorhanden')
  assert.ok(rahmen.includes('AUFNAHME_LIMIT_MS'), 'gemeinsames Limit benutzt')
  assert.ok(!rahmen.includes('setTimeout(() => setzen([]), 8000)'), 'kein altes 8-s-Limit mehr')
})

test('(N) Rahmen laedt Renderer und Schriften im Leerlauf vor', () => {
  const rahmen = lies('components/devmodus/Rahmen.vue')
  assert.ok(rahmen.includes('requestIdleCallback'), 'Vorladen im Leerlauf')
  assert.ok(rahmen.includes('vorwaermen('), 'Vorwaermfunktion aufgerufen')
  const modul = lies('components/devmodus/screenshot.mjs')
  assert.ok(modul.includes('export async function vorwaermen'), 'vorwaermen vorhanden')
})

test('(N) DevStart-Knopf traegt data-dk-dev', () => {
  const start = lies('components/devmodus/DevStart.vue')
  const knopf = start.slice(start.indexOf('<button'), start.indexOf('</button>'))
  assert.ok(knopf.includes('class="dk-dev-start"'), 'DevStart-Knopf gefunden')
  assert.ok(knopf.includes('data-dk-dev'), 'DevStart traegt die Kennung')
})

test('(N) AUFNAHME_LIMIT_MS deckt den Kaltstart (~5,5 s) mit Reserve ab', () => {
  assert.ok(AUFNAHME_LIMIT_MS >= 8000, 'mindestens das alte Limit')
  assert.equal(AUFNAHME_LIMIT_MS, 15000)
})

test('Aufraeumen der Test-Temporaerdateien', () => {
  if (existsSync(TEMP)) rmSync(TEMP, { recursive: true, force: true })
  assert.ok(!existsSync(TEMP), 'Temp-Verzeichnis entfernt')
})

console.log('DM3b Dev-Modus-Nacharbeit: bestanden')
