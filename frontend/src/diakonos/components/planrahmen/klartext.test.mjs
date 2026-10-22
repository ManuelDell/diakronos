import test from 'node:test'
import assert from 'node:assert/strict'
import { feldInfo, feldBeschriftung, diffGruppen, anzeigeWert, regelTitel, diffAnzeigeLaden, meldungsKurz } from './klartext.mjs'

const definition = { felder: [
  { id: 'lieder', name: 'Lied', art: 'eintrag', inhalt: [{ id: 'dirigent', name: 'Dirigent', art: 'person' }] },
  { id: 'abend', name: 'Abend', art: 'gruppe', varianten: ['sonne', { id: 'regen', name: 'Regen' }], teile: [{ id: 'abschluss', name: 'Abschluss', inhalt: [{ id: 'lied', name: 'Abendlied' }] }] },
  { id: 'ablauf', name: 'Programm', art: 'ablauf', elemente: [{ typ: 'lied', name: 'Lied', inhalt: [{ id: 'dirigent', name: 'Dirigent' }] }] },
] }
test('Feldpfade werden mit Namen, Nummern und Zweigen verständlich', () => {
  assert.equal(feldBeschriftung('lieder[0].dirigent', definition), 'Lied 1 · Dirigent')
  assert.equal(feldBeschriftung('abend@regen#abschluss.lied', definition), 'Abend (Regen) · Abschluss · Abendlied')
  assert.equal(feldBeschriftung('ablauf/abc.dirigent', definition, { ablauf: { ablauf: [{ id: 'abc', typ: 'lied' }] } }), 'Programm · Lied 1 · Dirigent')
  assert.equal(feldBeschriftung('gd:leitung', { terminreihen: [{ id: 'gd', name: 'Gottesdienst', felder: [{ id: 'leitung', name: 'Leitung' }] }] }), 'Gottesdienst · Leitung')
})
test('Vorlagen ohne name haben lesbare Begriffe statt Schlüssel', () => {
  assert.equal(feldBeschriftung('frohe_stunde.leitung', { felder: [{ id: 'frohe_stunde', inhalt: [{ id: 'leitung' }] }] }), 'Frohe Stunde · Leitung')
})
test('Werte zeigen Namen, leere Werte und keine internen Personenkennungen', () => {
  assert.equal(anzeigeWert('m-1', 'person', { 'm-1': { name: 'Mara Test' } }), 'Mara Test')
  assert.equal(anzeigeWert(null, 'person', {}), '(leer)')
  assert.equal(anzeigeWert(['m-1', 'm-2'], 'personen', { 'm-1': { name: 'Mara Test' } }), 'Mara Test, Nicht mehr verfügbar')
  assert.equal(anzeigeWert('Freier Text', 'text', {}), 'Freier Text')
})
test('Alle Vorschläge sind nach Termin gruppiert, nichts wird abgeschnitten', () => {
  const diff = Array.from({length: 87}, (_, i) => ({ termin: i % 2 ? 'b' : 'a', feld_pfad: 'lieder[0].dirigent', vorher: null, nachher: 'm-1' }))
  const groups = diffGruppen(diff, [{ id: 'b', datum: '2026-12-13', plantyp_version: 'v' }, { id: 'a', datum: '2026-12-06', plantyp_version: 'v' }], new Map([['v', definition]]), { 'm-1': { name: 'Mara Test' } })
  assert.equal(groups.length, 2)
  assert.equal(groups[0].datum, '2026-12-06')
  assert.equal(groups.flatMap(g => g.zeilen).length, 87)
  assert.equal(groups[0].zeilen[0].feld, 'Lied 1 · Dirigent')
  assert.equal(groups[0].zeilen[0].nachher, 'Mara Test')
})
test('Vorschlagswerte werden vor Anzeige aus echten Kandidaten aufgelöst', async () => {
  let aufrufe = 0
  const laden = async () => { aufrufe++; return { kandidaten: [{ kennung: 'm-1', name: 'Mara Test' }, { kennung: 'm-2', name: 'Tim Test' }] } }
  const result = await diffAnzeigeLaden([
    { termin: 't', feld_pfad: 'lieder[0].dirigent', vorher: null, nachher: 'm-1' },
    { termin: 't', feld_pfad: 'lieder[1].dirigent', vorher: null, nachher: 'm-2' },
  ], [{ id: 't', plantyp_version: 'v' }], new Map([['v', definition]]), {}, laden)
  assert.equal(result['m-1'].name, 'Mara Test')
  assert.equal(result['m-2'].name, 'Tim Test')
  assert.equal(aufrufe, 1)
})

test('Standardreihe löst ungepräfixte Personenfelder für Diff und Bearbeiten auf', async () => {
  const def = { terminreihen: [{ id: 'standard', name: 'Gottesdienst', felder: [{ id: 'leitung', name: 'Leitung', art: 'person' }] }] }
  const termine = [{ id: 't', plantyp_version: 'v' }]
  const defs = new Map([['v', def]])
  const diff = [{ termin: 't', feld_pfad: 'leitung', nachher: 'm-1' }]
  assert.equal(feldInfo('leitung', def).art, 'person')
  assert.equal(feldBeschriftung('leitung', def), 'Gottesdienst · Leitung')
  const namen = await diffAnzeigeLaden(diff, termine, defs, {}, async (t, pfad) => {
    assert.equal(pfad, 'leitung')
    return { kandidaten: [{ kennung: 'm-1', name: 'Mara Test' }] }
  })
  assert.equal(diffGruppen(diff, termine, defs, namen)[0].zeilen[0].nachher, 'Mara Test')
})

test('Unbekannte Feldarten zeigen keine internen Referenzwerte', () => {
  assert.equal(anzeigeWert('m-1', ''), 'Nicht mehr verfügbar')
  assert.equal(anzeigeWert('ab675ffa-7243-4000-9999-b12554322865', ''), 'Nicht mehr verfügbar')
})

test('Meldungen übersetzen reale Kandidaten- und Generatorpfade statt sie anzuhängen', () => {
  assert.equal(meldungsKurz({ code: 'kandidaten.leer', meldung: "Feld 'lieder[0].dirigent' hat keine Kandidaten." }, definition), 'Für Lied 1 · Dirigent sind noch keine passenden Vorschläge vorhanden. Bitte Stammdaten prüfen.')
  // UXP-R14: den Pfad liefert die Meldung (feld_pfad) — so sendet die API ihn
  // (dienste.py: feld_kandidaten -> {"feld_pfad": …, "meldungen": [...]}).
  const text = meldungsKurz({ code: 'kandidaten.leer', feld_pfad: 'lieder[0].dirigent', meldung: "Feld 'lieder[0].dirigent' hat keine Kandidaten." }, definition)
  assert.match(text, /Lied 1 · Dirigent/)
  assert.doesNotMatch(text, /lieder\[|\.dirigent/)
  assert.equal(meldungsKurz({ meldung: 'Kein Kandidat erfuellt die Muss-Regeln fuer lieder[0].dirigent (Quelle leer oder aufgebraucht).', feld_pfad: 'lieder[0].dirigent' }, definition),
    'Für Lied 1 · Dirigent gibt es keinen passenden Vorschlag: Die Liste ist leer oder niemand erfüllt alle Pflichtregeln.')
  assert.equal(meldungsKurz("Vorbelegen-Quelle 'eintrag.dirigent' fuer lieder[0].dirigent ist leer.", definition), 'Für Lied 1 · Dirigent fehlt eine vorbereitete Angabe. Bitte Stammdaten prüfen oder einen Wert von Hand wählen.')
  assert.doesNotMatch(meldungsKurz("Feld 'ablauf/ab675ffa-7243-4000-9999-b12554322865.dirigent' ist leer.", definition), /ab675ffa|ablauf\//)
  assert.equal(meldungsKurz('Bitte Angaben prüfen.'), 'Bitte Angaben prüfen.')
})

test('Regelzusammenfassung spricht Alltagssprache', () => {
  assert.equal(regelTitel('vorher_geuebt', 5, { regeln: [{ baustein: 'vorher_geuebt', mindestens: 2 }] }), '5 Lieder sind vor ihrem Termin noch nicht 2× geübt')
})
