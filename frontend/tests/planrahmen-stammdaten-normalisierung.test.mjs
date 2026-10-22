import assert from 'node:assert/strict'
import { stammdatenNormalisieren } from '../src/diakonos/components/planrahmen/stammdaten.mjs'
const roh = { definition:{merkmale:{person:[{id:'leitung',art:'tag'}]}}, darf_bearbeiten:true,
  personen:[{kennung:'mia',name:'Mia',merkmale:{leitung:true}}],
  sammlungen:[{schluessel:'themen',eintraege:[{kennung:'e1',titel:'Auftakt',aktiv:false,reihenfolge:4,merkmale:{stelle:'Psalm 1'}}]}],
  lieder:[{kennung:'l1',titel:'Lied'}] }
const d = stammdatenNormalisieren(roh)
assert.equal(d.personen[0].id,'mia')
assert.equal(d.sammlungen.themen[0].id,'e1')
assert.equal(d.sammlungen.themen[0].aktiv,false)
assert.equal(d.sammlungen.themen[0].reihenfolge,4)
assert.deepEqual(d.sammlungen.themen[0].merkmale,{stelle:'Psalm 1'})
assert.equal(d.sammlungen.lieder[0].daten.titel,'Lied')
assert.ok(!('id' in roh.personen[0]),'Originalantwort nicht mutiert')
console.log('Stammdaten: Kennungen, inaktive Zeilen und Liedmerkmale normalisiert')
