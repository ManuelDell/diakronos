import assert from 'node:assert/strict'
import { test, after } from 'node:test'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { readFileSync, mkdirSync, writeFileSync, rmSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve, basename, join } from 'node:path'
import { pathToFileURL } from 'node:url'

/**
 * Inline-Pfadmeldungen im Plantyp-Editor (Review-Anforderung): Prüfmeldungen
 * erscheinen am betroffenen Eingabepfad — in allen Abschnitten jenseits des
 * Feldbaums (Termine inkl. mehrerer Reihen/Zeilen, Regeln inkl. generierter
 * Parameter, Deklarationen, Ansichten). Verhalten wird echt gerendert
 * (vue/server-renderer), nicht nur per Quelltext-Regex geprüft.
 */

// ── SFC → ESModul → SSR (Helfer) ──────────────────────────────────────────

const SRC = resolve(import.meta.dirname, '../src/diakonos')
const TMP = mkdtempSync(join(tmpdir(), 'pr-pfadmeldungen-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
after(() => rmSync(TMP, { recursive: true, force: true }))

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({ source: descriptor.template.content, filename, id: filename,
    compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (v, spec) => {
    const ziel = resolve(dirname(abs), spec)
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const { createSSRApp } = await import('vue')
const { renderToString } = await import('@vue/server-renderer')

async function renderen(name, props, anzeige) {
  const modul = kompilieren(resolve(SRC, 'components/planrahmen/' + name + '.vue'))
  const komponente = (await import(pathToFileURL(modul).href)).default
  const app = createSSRApp(komponente, props)
  if (anzeige) app.provide('planrahmenAnzeige', { value: anzeige })
  return renderToString(app)
}

test('Echte Meldungsansicht rendert API- und Generatorfehler ohne technische Pfade', async () => {
  const definition = { felder: [{ id: 'lieder', name: 'Lied', inhalt: [{ id: 'dirigent', name: 'Dirigent', art: 'person' }] }] }
  const html = await renderen('PrMeldungen', { meldungen: [
    { code: 'kandidaten.leer', termin: 't', feld_pfad: 'lieder[0].dirigent', meldung: "Feld 'lieder[0].dirigent' hat keine Kandidaten." },
    { termin: 't', feld_pfad: 'lieder[1].dirigent', meldung: 'Kein Kandidat erfuellt die Muss-Regeln fuer lieder[1].dirigent (Quelle leer oder aufgebraucht).' },
  ] }, { termine: [{ id: 't', plantyp_version: 'v' }], definitionen: new Map([['v', definition]]), anzeige: {} })
  assert.match(html, /Für Lied 1 · Dirigent sind noch keine passenden Vorschläge/)
  assert.match(html, /Für Lied 2 · Dirigent gibt es keinen passenden Vorschlag/)
  assert.doesNotMatch(html, /lieder\[|\.dirigent/)
})
const vorkommen = (html, text) => html.split(text).length - 1

// ── PrPfadMeldungen: geteilte Komponente ──────────────────────────────────

test('PrPfadMeldungen zeigt Meldung mit Hinweis und Beispiel am betroffenen Pfad', async () => {
  const html = await renderen('PrPfadMeldungen', {
    pfad: 'parameter/0',
    meldungen: [
      { stufe: 'fehler', pfad: '/parameter/0/id', meldung: 'Kennung fehlt.', hinweis: 'Vergib eine eindeutige Kennung.', beispiel: 'zeitraum' },
      { stufe: 'warnung', pfad: '/felder/1/id', meldung: 'Fremde Meldung.', hinweis: 'Gehört nicht hierher.' },
    ],
  })
  assert.ok(html.includes('Kennung fehlt.'), 'Meldung am Pfad erscheint')
  assert.ok(html.includes('Vergib eine eindeutige Kennung.'), 'Hinweis erscheint')
  assert.ok(html.includes('Beispiel: zeitraum'), 'Beispiel erscheint')
  assert.ok(!html.includes('Fremde Meldung.'), 'Meldung fremden Pfads erscheint nicht')
})

test('PrPfadMeldungen bleibt ohne Treffer leer', async () => {
  const html = await renderen('PrPfadMeldungen', {
    pfad: 'regeln/0',
    meldungen: [{ stufe: 'fehler', pfad: '/regeln/1/baustein', meldung: 'Andere Reihe.' }],
  })
  assert.ok(!html.includes('pr-meldung'), 'keine Meldung ohne Treffer')
  const leer = await renderen('PrPfadMeldungen', { pfad: '', meldungen: [{ stufe: 'fehler', pfad: '/id', meldung: 'Root.' }] })
  assert.ok(!leer.includes('Root.'), 'ohne Pfad keine Treffer')
})

// ── Deklarationen: Parameter, Merkmale, Sammlungen, Rollen (mehrere Zeilen) ──

test('PrDeklarationenEditor zeigt Inline-Meldungen je Deklarationszeile', async () => {
  const definition = {
    id: 'chorplan', name: 'Chorplan',
    parameter: [{ id: 'zeitraum', art: 'zeitraum' }, { id: 'zeitraum', art: 'text' }],
    merkmale: { person: [{ id: 'name', art: 'text' }, { id: 'klavier', art: 'person' }] },
    sammlungen: [{ id: 'bibel', name: 'Bibel' }, { id: 'bibel', name: 'Bibel 2' }],
    rollen: [{ id: 'mitarbeiter', name: 'Mitarbeiter' }],
  }
  const meldungen = [
    { stufe: 'fehler', pfad: '/parameter/1/id', meldung: 'Doppelte Parameterkennung.', hinweis: 'Nur einmal verwenden.' },
    { stufe: 'warnung', pfad: '/merkmale/person/1', meldung: 'Personenmerkmal ohne Rolle.' },
    { stufe: 'fehler', pfad: '/sammlungen/1/id', meldung: 'Doppelte Sammlungskennung.' },
    { stufe: 'warnung', pfad: '/rollen/0', meldung: 'Rolle ohne Filter.' },
    { stufe: 'fehler', pfad: '/felder/0/id', meldung: 'Feldbaum-Meldung gehört nicht hier.' },
  ]
  const html = await renderen('PrDeklarationenEditor', { definition, kontext: {}, meldungen })
  assert.ok(html.includes('Doppelte Parameterkennung.'), 'Parameterzeile 1')
  assert.ok(html.includes('Personenmerkmal ohne Rolle.'), 'Merkmalzeile je Ziel')
  assert.ok(html.includes('Doppelte Sammlungskennung.'), 'Sammlungszeile 1')
  assert.ok(html.includes('Rolle ohne Filter.'), 'Rollenzeile 0')
  assert.ok(!html.includes('Feldbaum-Meldung'), ' fremder Abschnitt bleibt draußen')
})

// ── Ansichten: mehrere Zeilen inkl. Formatpfaden ──────────────────────────

test('PrAnsichtenEditor zeigt Inline-Meldungen je Ansicht und Formatzeile', async () => {
  const ansichten = [
    { art: 'tabelle', name: 'Aushang', format: { dirigent: '{dirigent.name}' } },
    { art: 'raster', name: 'Raster', zeilen: 'termin' },
  ]
  const meldungen = [
    { stufe: 'warnung', pfad: '/ansichten/0/format/dirigent', meldung: 'Unbekanntes Attribut im Format.' },
    { stufe: 'fehler', pfad: '/ansichten/1/zeilen', meldung: 'Zeilenangabe ungültig.' },
    { stufe: 'warnung', pfad: '/ansichten/1', meldung: 'Ansicht unvollständig.' },
    { stufe: 'fehler', pfad: '/parameter/0/id', meldung: 'Fremder Abschnitt.' },
  ]
  const html = await renderen('PrAnsichtenEditor', { ansichten, definition: { id: 'x', felder: [] }, meldungen })
  assert.equal(vorkommen(html, 'Unbekanntes Attribut im Format.'), 1, 'Formatmeldung genau einmal (an der Vorlagenzeile, nicht doppelt auf Karte)')
  assert.ok(html.indexOf('Unbekanntes Attribut im Format.') > html.indexOf('placeholder="{eintrag.buch} {eintrag.titel}"'), 'Formatmeldung erscheint nach der Vorlagen-Eingabe')
  assert.ok(html.includes('Zeilenangabe ungültig.'), 'Ansicht 1')
  assert.equal(vorkommen(html, 'Ansicht unvollständig.'), 1, 'Kartenebene exakt, ohne Dopplung')
  assert.ok(!html.includes('Fremder Abschnitt.'), 'fremder Abschnitt bleibt draußen')
})

// ── Regeln: Karte + generierte Parametereingaben, ohne Dopplung ────────────

const BAUSTEINE = {
  mindestabstand: {
    beschreibung: 'Mindestabstand zwischen zwei Einsätzen.',
    parameter_schema: {
      type: 'object',
      required: ['wochen'],
      properties: {
        wochen: { type: 'integer', description: 'Mindestabstand in Wochen', examples: [2] },
        feld: { type: 'string', description: 'Bezogenes Feld' },
      },
    },
  },
}

test('PrRegelnEditor zeigt Meldungen am Regelparameter und auf Kartenebene — genau einmal', async () => {
  const regeln = [{ baustein: 'mindestabstand', stufe: 'sollte', wochen: 9 }]
  const meldungen = [
    { stufe: 'fehler', pfad: '/regeln/0/wochen', meldung: 'Parameter wochen ungültig.', hinweis: 'Ganze Zahl, z. B.' },
    { stufe: 'warnung', pfad: '/regeln/0', meldung: 'Regel verweist auf kein Feld.' },
    { stufe: 'fehler', pfad: '/regeln/3/wochen', meldung: 'Meldung einer anderen Regel.' },
  ]
  const html = await renderen('PrRegelnEditor', { regeln, bausteine: BAUSTEINE, kontext: {}, meldungen })
  assert.equal(vorkommen(html, 'Parameter wochen ungültig.'), 1, 'Parameterpfad genau einmal (keine Dopplung Karte/Eingabe)')
  assert.ok(html.includes('Regel verweist auf kein Feld.'), 'Kartenebene /regeln/0')
  assert.ok(!html.includes('Meldung einer anderen Regel.'), 'andere Regelindexe bleiben draußen')
})

// ── Termine: Regel, Ausnahmen-/Manuell-Zeilen, Feiertage, abgeleitet ───────

test('PrTermineEditor zeigt Inline-Meldungen an betroffenen Terminpfaden (mehrere Zeilen)', async () => {
  const termine = {
    regel: 'FREQ=WEEKLY;BYDAY=SO',
    ausnahmen: [{ datum: '2026-01-01' }, { datum: '2026-01-02' }],
    manuell: [{ datum: '2026-02-01' }],
  }
  const meldungen = [
    { stufe: 'fehler', pfad: '/termine/regel', meldung: 'RRULE unlesbar.' },
    { stufe: 'warnung', pfad: '/termine/ausnahmen/1/datum', meldung: 'Ausnahme ohne Datum.' },
    { stufe: 'fehler', pfad: '/termine/manuell/0/datum', meldung: 'Manueller Termin ohne Datum.' },
    { stufe: 'warnung', pfad: '/termine/feiertage/2', meldung: 'Unbekannter Feiertag.' },
    { stufe: 'warnung', pfad: '/termine/uhrzeit', meldung: 'Uhrzeit ungültig.' },
    { stufe: 'warnung', pfad: '/termine/wochentage/1', meldung: 'Wochentag unbekannt.' },
    { stufe: 'fehler', pfad: '/regeln/0/baustein', meldung: 'Fremder Abschnitt.' },
  ]
  const html = await renderen('PrTermineEditor', { termine, reihenIds: ['standard'], kontext: {}, meldungen, basisPfad: 'termine' })
  assert.ok(html.includes('RRULE unlesbar.'), 'Wiederholungsregel')
  assert.ok(html.includes('Ausnahme ohne Datum.'), 'Ausnahmenzeile 1')
  assert.ok(html.includes('Manueller Termin ohne Datum.'), 'Manuelle Zeile 0')
  assert.ok(html.includes('Unbekannter Feiertag.'), 'Feiertagspfad')
  assert.ok(html.includes('Uhrzeit ungültig.'), 'Uhrzeitpfad')
  assert.ok(html.includes('Wochentag unbekannt.'), 'Wochentage der Freizeit-Zeitraumswahl')
  assert.ok(!html.includes('Fremder Abschnitt.'), 'fremder Abschnitt bleibt draußen')
})

test('PrTermineEditor leitet Meldungen abgeleiteter Reihen über basisPfad weiter', async () => {
  const termine = { abgeleitet: { von: 'standard', versatz: '-2T' } }
  const meldungen = [
    { stufe: 'fehler', pfad: '/terminreihen/1/termine/abgeleitet/von', meldung: 'Unbekannte Ursprungsreihe.' },
    { stufe: 'fehler', pfad: '/termine/regel', meldung: 'Kurzform-Meldung darf hier nicht erscheinen.' },
  ]
  const html = await renderen('PrTermineEditor', { termine, reihenIds: ['standard'], kontext: {}, meldungen, basisPfad: 'terminreihen/1/termine' })
  assert.ok(html.includes('Unbekannte Ursprungsreihe.'), 'abgeleitete Reihe mit eigenem basisPfad')
  assert.ok(!html.includes('Kurzform-Meldung'), 'Pfade anderer Basis bleiben draußen')
})

// ── Schemawidrige Werte: Formular darf nicht abstürzen (Review Runde 2) ────

test('PrTermineEditor rendert schemawidrige Feiertagswerte werftrei und zeigt die Pfadmeldung', async () => {
  const meldungen = [{ stufe: 'fehler', pfad: '/termine/feiertage', meldung: 'Feiertage müssen eine Liste sein.', hinweis: 'Als JSON-Array angeben.' }]
  for (const [name, feiertage] of [['Array', ['ostermontag']], ['String', 'ostermontag'], ['Objekt', {}], ['Zahl', 42]]) {
    const termine = { feiertage }
    const html = await renderen('PrTermineEditor', { termine, reihenIds: ['standard'], kontext: {}, meldungen, basisPfad: 'termine' })
    assert.ok(html.includes('Feiertage müssen eine Liste sein.'), name + ': Pfadmeldung erscheint statt TypeError')
    assert.deepEqual(termine.feiertage, feiertage, name + ': Rohdefinition bleibt unverändert')
  }
})

test('PrTermineEditor rendert schemawidrige Geschwisterwerte (wochentage, kontext.parameter) werftrei', async () => {
  const html = await renderen('PrTermineEditor', {
    termine: { wochentage: {} }, reihenIds: ['standard'], kontext: { parameter: 'kein-array' }, meldungen: [], basisPfad: 'termine',
  })
  assert.ok(html.includes('Wiederholung'), 'Wochentage-Objekt (Freizeit-Zeitraumswahl) rendert')
  const html2 = await renderen('PrTermineEditor', {
    termine: { zeitraum: '{parameter.zeitraum}' }, reihenIds: ['standard'], kontext: { parameter: 'kein-array' }, meldungen: [], basisPfad: 'termine',
  })
  assert.ok(html2.includes('Freizeit'), 'kontext.parameter als String rendert')
})

test('PrTermineEditor Kontrollfall: eigene Feiertage werden gelistet, Duplikate vermieden, Entfernen angeboten', async () => {
  const termine = { feiertage: ['ostermontag', 'osterdienstag'] }
  const html = await renderen('PrTermineEditor', { termine, reihenIds: ['standard'], kontext: {}, meldungen: [], basisPfad: 'termine' })
  assert.ok(html.includes('>osterdienstag</span>'), 'eigener Feiertag erscheint in der Liste')
  assert.equal(vorkommen(html, '>osterdienstag</span>'), 1, 'eigener Feiertag genau einmal gelistet (kein Duplikat)')
  assert.ok(!html.includes('>ostermontag</span>'), 'Katalogfeiertag wird nicht zusätzlich als eigener geführt')
  assert.ok(html.includes('aria-label="Feiertag osterdienstag entfernen"'), 'Entfernen-Schaltfläche je eigenem Feiertag')
})

// ── Reihen: Kurzform vs. mehrere Reihen (mehrere Zeilen) ───────────────────

test('PrReihenEditor verdrahtet Termine je Reihe mit eigenem Pfadpräfix', async () => {
  const definition = {
    id: 'chorplan', name: 'Chorplan',
    terminreihen: [
      { id: 'gottesdienst', name: 'Gottesdienst', termine: { regel: 'FREQ=WEEKLY;BYDAY=SO' }, felder: [] },
      { id: 'probe', name: 'Probe', termine: { abgeleitet: { von: 'standard', versatz: '-2T' } }, felder: [] },
    ],
  }
  const meldungen = [
    { stufe: 'fehler', pfad: '/terminreihen/0/termine/regel', meldung: 'RRULE der Reihe 0.' },
    { stufe: 'fehler', pfad: '/terminreihen/1/id', meldung: 'Reihenkennung fehlt.' },
    { stufe: 'warnung', pfad: '/terminreihen/1/termine/abgeleitet/von', meldung: 'Unbekannte Ursprungsreihe.' },
    { stufe: 'fehler', pfad: '/termine/regel', meldung: 'Kurzform-Meldung bei Reihen unzulässig.' },
  ]
  const html = await renderen('PrReihenEditor', { definition, kontext: {}, meldungen })
  assert.ok(html.includes('RRULE der Reihe 0.'), 'Terminpfad der Reihe 0')
  assert.ok(html.includes('Reihenkennung fehlt.'), 'Reihenkennung /terminreihen/1/id')
  assert.ok(html.includes('Unbekannte Ursprungsreihe.'), 'abgeleitete Reihe 1')
  assert.ok(!html.includes('Kurzform-Meldung'), 'Kurzform-Pfad kommt nicht vor Reihen vor')
})

test('PrReihenEditor-Kurzform verdrahtet Termine unter „termine“', async () => {
  const definition = { id: 'chorplan', name: 'Chorplan', termine: { regel: 'FREQ=WEEKLY;BYDAY=SO' }, felder: [] }
  const html = await renderen('PrReihenEditor', {
    definition, kontext: {},
    meldungen: [{ stufe: 'fehler', pfad: '/termine/regel', meldung: 'Kurzform-RRULE unlesbar.' }],
  })
  assert.ok(html.includes('Kurzform-RRULE unlesbar.'), 'Kurzform zeigt /termine/... inline')
})
