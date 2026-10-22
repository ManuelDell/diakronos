import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { formatTemplate } from '../src/diakonos/components/planrahmen/format.mjs'
import { stammdatenNormalisieren } from '../src/diakonos/components/planrahmen/stammdaten.mjs'

// API-Grenze isolieren, reale Helfer/Cache-/Payloadlogik ausführen.
const aufrufe = []
globalThis.__ui1Api = async (name, args) => {
  aufrufe.push({ name, args })
  if (name.endsWith('plan_holen') && args.plan === 'themenplan') return { anzeige: { thema: { titel: 'Auftakt', stelle: 'Psalm 23' } } }
  if (name.endsWith('feld_kandidaten') && args.feld_pfad === 'thema') return { kandidaten: [{ kennung: 'thema', titel: 'Auftakt', stelle: 'Psalm 23', merkmale: { stelle: 'Psalm 23' } }] }
  return name.endsWith('feld_kandidaten') ? { kandidaten: [{ kennung: 'mia', name: 'Mia', kuerzel: 'MT' }] } : {}
}
globalThis.__ui1Format = formatTemplate
globalThis.__ui2Stamm = stammdatenNormalisieren
let source = await readFile(new URL('../src/diakonos/composables/usePlanrahmen.js', import.meta.url), 'utf8')
source = source.replace("import { ref, computed } from 'vue'", 'const ref = value => ({value}); const computed = f => ({get value(){return f()}})')
source = source.replace("import { apiCall } from './useApi.js'", 'const apiCall = globalThis.__ui1Api')
// Der Upload verwendet die echte Antwortprüfung, nur die JSON-Fachaufrufe sind isoliert.
source = source.replace("import { apiAntwortPruefen } from './useApi.js'",
  `import { apiAntwortPruefen } from '${new URL('../src/diakonos/composables/useApi.js', import.meta.url).href}'`)
source = source.replace("import { formatTemplate } from '../components/planrahmen/format.mjs'", 'const formatTemplate = globalThis.__ui1Format')
source = source.replace("import { stammdatenNormalisieren } from '../components/planrahmen/stammdaten.mjs'", 'const stammdatenNormalisieren = globalThis.__ui2Stamm')
// P3-1c: die beiden neuen Helfer-Importe auf Inline-Ersatz umstellen, damit
// der data:-URL-Import keine relativen Pfade aufloesen muss.
source = source.replace("import { setzeFeiertagskatalog } from '../components/planrahmen/anlaesse.mjs'",
  'const setzeFeiertagskatalog = () => {}')
source = source.replace("import { merkeKatalogDefinition, merkeKochbuchVorlage } from '../components/planrahmen/auswahlwerte.mjs'",
  'const merkeKatalogDefinition = () => {}\nconst merkeKochbuchVorlage = () => {}')
source = source.replace("import { wertAnzeige } from '../components/planrahmen/auswahlwerte.mjs'",
  'const wertAnzeige = (d, w) => (d && d.anzeigenamen && d.anzeigenamen[w]) || w')
// PF1: Browser-Cache-Modul aushebeln — diese Testdatei prueft die Composable-
// Logik (Anzeige/Invalidierung), nicht den Cache. Ohne Ersatz wuerde der
// data:-URL-Import des neuen Moduls nicht aufloesen.
source = source.replace(
  /import \{\s*cacheNutzerSetzen[\s\S]*?\} from '\.\/usePlanrahmenCache\.js'/,
  'const cacheNutzerSetzen = () => {}; const standLesen = () => null; ' +
  'const standSchreiben = () => {}; const staendeGleich = () => false; ' +
  'const eintragVerwerfen = () => {}; const browserCacheLeeren = () => {}')
// DSGVO-2d: dasselbe fuer die Anzeige-Regel geloeschter Personen — der
// data:-URL-Import kann keine relativen Pfade aufloesen. Geprueft wird hier
// die Composable-Logik, die Regel selbst hat ihren eigenen Test
// (dsgvo2d-geloeschte-person.test.mjs).
source = source.replace(
  "import { GELOESCHT_ANZEIGE, istGeloescht } from './geloeschte-person.mjs'",
  "const GELOESCHT_ANZEIGE = 'Gelöschte Person'; " +
  "const istGeloescht = (p) => { if (!p) return false; if (typeof p === 'string') " +
  "return p.trim().toLowerCase().startsWith('geloescht-'); " +
  "const s = String(p.status ?? '').trim().toLowerCase(); if (s === 'geloescht') return true; " +
  "const k = String(p.name ?? p.mitglied ?? p.kennung ?? ''); " +
  "return k.trim().toLowerCase().startsWith('geloescht-') }")
const m = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
const api = m.usePlanrahmen()
await api.feldKandidaten('p', 't', 'f')
assert.equal(m.anzeigeZu('mia').kuerzel, 'MT')
await api.feldKandidaten('p', 't', 'f')
assert.equal(aufrufe.length, 1)
await api.eintragSetzen('p', 't', 'f', 'mia')
await api.feldKandidaten('p', 't', 'f')
assert.equal(aufrufe.length, 3, 'Schreiben invalidiert veraltete Kandidatenbewertungen')
await api.ablaufAendern('p', 't', [{ aktion: 'hinzufuegen', feld_pfad: 'ablauf', typ: 'lied', position: 0 }])
assert.deepEqual(aufrufe.at(-1).args, { plan: 'p', termin: 't', feld: 'ablauf', aktion: 'hinzufuegen', element_typ: 'lied', element_id: null, position: 0 })
m.anzeigeUebernehmen({ lied: { titel: 'Advent' }, tim: { name: 'Tim', kuerzel: 'TO' } })
const ctx = m.zellenKontext({ titel: 'Chor' }, { datum: '2026-12-13' }, {
  selbst: { wert: 'lied' }, unter: new Map([['dirigent', { wert: 'tim' }]])
}, { art: 'eintrag', inhalt: [{ id: 'dirigent', art: 'person' }] })
assert.equal(m.formatVorlage('{eintrag.titel} {dirigent.kuerzel}', ctx), 'Advent TO')
await api.planHolen('anderer-plan')
assert.equal(m.anzeigeZu('tim'), 'tim', 'Planwechsel entfernt fremde Anzeigecaches')
m.anzeigeUebernehmen({ lied: { titel: 'Advent', nr: '101' } })
assert.equal(m.anzeigeZu('lied').nummer, '101', 'Originales Kochbuch verwendet nummer')
assert.equal(m.feldGehoertZu('abend@regen#abschluss.leitung', 'abend'), true)
assert.equal(m.feldGehoertZu('gottesdienst:gaeste', 'gottesdienst:'), true)
assert.equal(m.feldGehoertZu('abendlied', 'abend'), false)
await api.feldKandidaten('themenplan', 't', 'thema')
const themaText = () => m.formatVorlage('{eintrag.titel} {eintrag.stelle}', m.zellenKontext(
  {}, {}, { selbst: { wert: 'thema' }, unter: new Map() }, { art: 'eintrag' }))
assert.equal(themaText(), 'Auftakt Psalm 23', 'Generische Kandidatenattribute im Formatkontext')
await api.planHolen('themenplan')
assert.equal(themaText(), 'Auftakt Psalm 23', 'Reload nutzt minimierte Anzeige statt Kandidaten')
await api.kochbuchHolen('freizeit')
assert.deepEqual(aufrufe.at(-1), { name: 'diakronos.planrahmen.api.kochbuch_holen', args: { name: 'freizeit' } })
await api.stammdatenHolen('freizeit', 'p')
assert.deepEqual(aufrufe.at(-1).args, { plantyp: 'freizeit', plan: 'p' })
await api.einrichtenRechte()
assert.equal(aufrufe.at(-1).name, 'diakronos.planrahmen.api.einrichten_rechte')
console.log('Planrahmen-Composable: Anzeige, generische Sammlungsformate/Reload, Invalidierung, Feldpfade, Einrichtung und Ablauf-Payload bestanden')
