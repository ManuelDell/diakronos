import assert from 'node:assert/strict'
import { formatTemplate } from './format.mjs'
import { meldungsGruppen } from './meldungen.mjs'

const context = {
  plan: { titel: 'Adventssingen' }, eintrag: { titel: 'Freude', buch: 'WH', seite: 150 },
  team: { name: 'Gruppe 3' }, gaeste: [{ vorname: 'Anna' }, { vorname: 'Ben' }],
  klavier: [{ kuerzel: 'AB' }, { kuerzel: 'CD' }], leer: [], nullwert: null,
}
assert.equal(formatTemplate('{plan.titel}: {eintrag.titel}', context), 'Adventssingen: Freude')
assert.equal(formatTemplate('{team.name}{gaeste: + {gaeste.vorname}}', context), 'Gruppe 3 + Anna, Ben')
assert.equal(formatTemplate('{eintrag.buch}{eintrag.seite: S. {eintrag.seite}}', context), 'WH S. 150')
assert.equal(formatTemplate('{leer: + {leer.name}}{nullwert: fehlt}{unbekannt}', context), '')
assert.equal(formatTemplate('{klavier.kuerzel}', context), 'AB, CD')
assert.equal(formatTemplate('{wert}', { wert: 0 }), '0')
assert.equal(formatTemplate('{wert}', { wert: false }), 'Nein')
assert.equal(formatTemplate('{wert: vorhanden}', { wert: false }), '')
assert.equal(formatTemplate('{eintrag.titel}', { eintrag: { titel: '<script>alert(1)</script>' } }), '<script>alert(1)</script>')
assert.equal(formatTemplate('{__proto__.polluted}{constructor.name}', context), '')
assert.equal(formatTemplate('Text {offen', context), 'Text {offen')
assert.equal(formatTemplate('{team: {gaeste: Gäste {gaeste.vorname}}}', context), '  Gäste Anna, Ben')
assert.equal(formatTemplate('{team: {leer: niemals}}', context), ' ')
// Unveränderte Formatvorlagen der geprüften Musikteam-/Programm-Kochbücher.
const musik = '{team.name}{gaeste: + {gaeste.vorname}}{anlass: ({anlass})} {monatslied: Monatslied „{monatslied.titel}“}'
assert.equal(formatTemplate(musik, { team: { name: 'Gruppe 3' } }), 'Gruppe 3 ')
assert.equal(formatTemplate(musik, { ...context, anlass: 'Abendmahl', monatslied: { titel: 'Freude' } }), 'Gruppe 3 + Anna, Ben (Abendmahl)  Monatslied „Freude“')
const programm = '{nr} | {lied.buch}{lied.seite: S. {lied.seite}} | {lied.titel} | {ensemble} {begleitung} | {dirigent.kuerzel}/{klavier.kuerzel}'
assert.equal(formatTemplate(programm, { ...context, nr: 1, lied: context.eintrag, ensemble: ['Chor', 'Solo'], begleitung: ['Klavier'], dirigent: { kuerzel: 'DA' } }), '1 | WH S. 150 | Freude | Chor, Solo Klavier | DA/AB, CD')
assert.equal(formatTemplate('Predigt{prediger: ({prediger.name})}', { prediger: null }), 'Predigt')
console.log('Formatvorlagen: 17 Prüfungen bestanden')
const chor = '{eintrag.buch}{eintrag.nummer: Nr.{eintrag.nummer}}{dirigent.kuerzel: /{dirigent.kuerzel}}{klavier.kuerzel: /{klavier.kuerzel}}{eintrag.titel: {eintrag.titel}}'
assert.equal(formatTemplate(chor, { eintrag: { nummer: 108 } }).trim(), 'Nr.108')
assert.equal(formatTemplate(chor, {}), '')
assert.equal(formatTemplate(chor, { eintrag: { titel: 'Freude' }, dirigent: { kuerzel: 'DA' } }).trim(), '/DA Freude')
const bedingt = '{nr}{lied.buch: | {lied.buch}}{lied.seite: S. {lied.seite}}{lied.titel: | {lied.titel}}{ensemble: | {ensemble}}{begleitung: | {begleitung}}{dirigent.kuerzel: /{dirigent.kuerzel}}{klavier.kuerzel: /{klavier.kuerzel}}'
assert.equal(formatTemplate(bedingt, { nr: 1 }), '1')
assert.equal(formatTemplate(bedingt, { nr: 1, lied: { titel: 'Freude' }, ensemble: [], klavier: [] }), '1 | Freude')
const zusammen = meldungsGruppen([{ stufe: 'sollte', code: 'abstand' }, { stufe: 'warnung', code: 'abstand' }, { stufe: 'muss', baustein: 'abwesend' }])
assert.deepEqual(zusammen.anzahl, { fehler: 1, warnung: 2, hinweis: 0 })
assert.equal(zusammen.gruppen.length, 2)
assert.equal(zusammen.gruppen[0].meldungen.length, 2)
console.log('Bedingte Leerwerte und gruppierte Regelübersicht bestanden')
