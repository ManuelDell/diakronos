import test from 'node:test'
import assert from 'node:assert/strict'
import {
  sammlungMerkmale, pflegbareWertMerkmale, personMerkmale, liederFiltern, asListe, tagWerte,
  materialNachArt, artFuerDateiname, MATERIAL_REIHENFOLGE,
} from './lieder-pflege.mjs'

const definition = {
  merkmale: {
    person: [{ id: 'dirigent', art: 'tag', name: 'dirigiert' }],
    lieder: [
      { id: 'dirigent', art: 'person', rolle: { merkmal: 'dirigent' } },
      { id: 'thema', art: 'auswahl', mehrfach: true, werte: ['Advent', 'Passion'] },
      { id: 'instrument', art: 'auswahl', mehrfach: true, werte: ['Geige', 'Gitarre'] },
    ],
  },
}

test('merkmale je Sammlung, nur Auswahl/Tag sind pflegbar', () => {
  assert.deepEqual(sammlungMerkmale(definition, 'lieder').map((m) => m.id), ['dirigent', 'thema', 'instrument'])
  assert.deepEqual(pflegbareWertMerkmale(definition, 'lieder').map((m) => m.id), ['thema', 'instrument'])
  assert.deepEqual(sammlungMerkmale(definition, 'gibtsnicht'), [])
})

test('Personen-Merkmale werden erkannt (Standard-Dirigent/Klavier)', () => {
  assert.deepEqual(personMerkmale(definition, 'lieder').map((m) => m.id), ['dirigent'])
  assert.deepEqual(personMerkmale(definition, 'gibtsnicht'), [])
})

const lieder = [
  { id: 'L1', titel: 'Komm, sag es allen', merkmale: { instrument: ['Geige'] } },
  { id: 'L2', titel: 'Macht hoch die Tür', merkmale: { instrument: ['Geige', 'Gitarre'], thema: 'Advent' } },
  { id: 'L3', titel: 'O du fröhliche', merkmale: { thema: ['Advent'] } },
  { id: 'L4', titel: 'Geige solo', merkmale: {} },
]

test('Filter nach Tag: nur Lieder mit Geige', () => {
  const treffer = liederFiltern(lieder, { tagFilter: { instrument: ['Geige'] } })
  assert.deepEqual(treffer.map((l) => l.id), ['L1', 'L2'])
})

test('Filter kombiniert mehrere Tags (UND) und die Suche', () => {
  assert.deepEqual(
    liederFiltern(lieder, { tagFilter: { instrument: ['Geige', 'Gitarre'] } }).map((l) => l.id),
    ['L2'])
  assert.deepEqual(liederFiltern(lieder, { suche: 'macht' }).map((l) => l.id), ['L2'])
  assert.deepEqual(liederFiltern(lieder, { suche: 'geige' }).map((l) => l.id), ['L4'])
})

test('Merkmalswerte werden immer als Liste behandelt', () => {
  assert.deepEqual(asListe('Geige'), ['Geige'])
  assert.deepEqual(asListe(['Geige', 'Gitarre']), ['Geige', 'Gitarre'])
  assert.deepEqual(asListe(null), [])
  assert.deepEqual(asListe(''), [])
})

test('Verfuegbare Tag-Werte kommen aus Definition UND Verwendung', () => {
  const werte = tagWerte(definition, 'lieder', lieder)
  assert.deepEqual(werte.instrument, ['Geige', 'Gitarre'])
  assert.deepEqual(werte.thema, ['Advent', 'Passion'])
})

test('Material wird nach Art gruppiert und in fester Reihenfolge geliefert', () => {
  const material = [
    { art: 'audio', dateiname: 'a.mp3' },
    { art: 'noten_pdf', dateiname: 'n.pdf' },
    { art: 'audio', dateiname: 'b.ogg' },
    { art: 'musescore', dateiname: 's.mscz' },
  ]
  const gruppen = materialNachArt(material)
  assert.deepEqual(gruppen.map((g) => g.art), MATERIAL_REIHENFOLGE.filter((a) => ['noten_pdf', 'audio', 'musescore'].includes(a)))
  assert.equal(gruppen.find((g) => g.art === 'audio').eintraege.length, 2)
  assert.ok(gruppen.find((g) => g.art === 'audio').label.includes('Audio'))
})

test('Endung bestimmt die Material-Art', () => {
  assert.equal(artFuerDateiname('noten.PDF'), 'noten_pdf')
  assert.equal(artFuerDateiname('aufnahme.mp3'), 'audio')
  assert.equal(artFuerDateiname('satz.MSCZ'), 'musescore')
  assert.equal(artFuerDateiname('partitur.mxl'), 'musicxml')
  assert.equal(artFuerDateiname('video.mp4'), null)
})
