import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  rruleAus, rruleLesen, wiederholungText, versatzLesen, versatzAus, versatzText,
  anzahlLesen, anzahlAus, feldVerschieben, feldEinruecken, feldEinfuegen, feldLoeschen,
  feldPfadListe, topFeldIds, knotenSchluessel, leerenKnoten, knotenWechseln, knotenText,
  regelParameterForm, regelWerte, regelBauen, jsonText, jsonUebernehmen,
  abschnittsSchluessel, meldungenNachAbschnitt, hoechsteStufe,
  istParameterRef, wertOderRefLesen, wertOderRefAus, kennungGueltig, merkmalsZiele,
  leereDefinition, leeresFeld, FEIERTAGE, WOCHENTAGE, alsListe,
} from './editor.mjs'

// ── Wiederholung: verständlich ↔ RRULE ─────────────────────────────────────

test('jeden Sonntag wird zur RRULE und zurück', () => {
  assert.equal(rruleAus({ frequenz: 'weekly', tage: ['so'] }), 'FREQ=WEEKLY;BYDAY=SU')
  assert.equal(rruleAus({ frequenz: 'weekly', tage: ['mi', 'fr'] }), 'FREQ=WEEKLY;BYDAY=WE,FR')
  assert.equal(rruleAus({ frequenz: 'daily' }), 'FREQ=DAILY')
  assert.deepEqual(rruleLesen('FREQ=WEEKLY;BYDAY=SU'), { frequenz: 'weekly', intervall: 1, tage: ['so'] })
  assert.deepEqual(rruleLesen('FREQ=WEEKLY;INTERVAL=2;BYDAY=SA'), { frequenz: 'weekly', intervall: 2, tage: ['sa'] })
  assert.equal(rruleLesen('keine Regel'), null)
  assert.equal(rruleLesen('FREQ='), null)
})

test('wiederholungText schreibt deutsche Sätze', () => {
  assert.equal(wiederholungText('FREQ=WEEKLY;BYDAY=SU'), 'jeden Sonntag')
  assert.equal(wiederholungText('FREQ=WEEKLY;BYDAY=MO,WE'), 'jeden Montag und Mittwoch')
  assert.equal(wiederholungText('FREQ=WEEKLY;BYDAY=MO,WE,FR'), 'jeden Montag, Mittwoch und Freitag')
  assert.equal(wiederholungText('FREQ=DAILY'), 'jeden Tag')
  assert.equal(wiederholungText('FREQ=WEEKLY;INTERVAL=2;BYDAY=SU'), 'alle 2 Wochen am Sonntag')
  // Unlesbare Regel wird unverändert gezeigt, nie ersetzt.
  assert.equal(wiederholungText('BYDAY'), 'BYDAY')
  assert.equal(wiederholungText(''), '')
})

// ── Abgeleitete Termine ────────────────────────────────────────────────────

test('Versatz lesen, bauen und erklären', () => {
  assert.deepEqual(versatzLesen('-2T'), { signum: '-', zahl: 2, einheit: 'T' })
  assert.deepEqual(versatzLesen('+1W'), { signum: '+', zahl: 1, einheit: 'W' })
  assert.deepEqual(versatzLesen('-3h'), { signum: '-', zahl: 3, einheit: 'h' })
  assert.deepEqual(versatzLesen('-15min'), { signum: '-', zahl: 15, einheit: 'min' })
  assert.equal(versatzLesen('2T'), null)
  assert.equal(versatzLesen('x'), null)
  assert.equal(versatzAus({ signum: '-', zahl: 2, einheit: 'T' }), '-2T')
  assert.equal(versatzAus({ signum: '+', zahl: 1, einheit: 'W' }), '+1W')
  assert.equal(versatzText('-2T'), '2 Tag(e) vor dem Ursprungstermin')
  assert.equal(versatzText('+1W'), '1 Woche(n) nach dem Ursprungstermin')
})

// ── Anzahl ─────────────────────────────────────────────────────────────────

test('Anzahl als Zahl oder Bereich', () => {
  assert.deepEqual(anzahlLesen(3), { min: 3, max: 3, offen: false })
  assert.deepEqual(anzahlLesen('0..2'), { min: 0, max: 2, offen: false })
  assert.deepEqual(anzahlLesen('1..*'), { min: 1, max: null, offen: true })
  assert.deepEqual(anzahlLesen(undefined), { min: 1, max: 1, offen: false })
  assert.equal(anzahlAus({ min: 3, max: 3 }), 3)
  assert.equal(anzahlAus({ min: 0, max: 2 }), '0..2')
  assert.equal(anzahlAus({ min: 1, offen: true }), '1..*')
})

// ── Feld-Baum-Operationen ──────────────────────────────────────────────────

test('Felder verschieben, einrücken, einfügen, löschen', () => {
  const felder = [{ id: 'a', art: 'text' }, { id: 'b', art: 'gruppe', inhalt: [] }, { id: 'c', art: 'text' }]
  assert.equal(feldVerschieben(felder, 0, 1), true)
  assert.deepEqual(felder.map((f) => f.id), ['b', 'a', 'c'])
  assert.equal(feldVerschieben(felder, 2, 1), false)
  // a rückt in die Gruppe b ein (Vorgänger ist gruppe)
  assert.equal(feldEinruecken(felder, 1), true)
  assert.deepEqual(felder.map((f) => f.id), ['b', 'c'])
  assert.deepEqual(felder[0].inhalt.map((f) => f.id), ['a'])
  // c hat Vorgänger b (gruppe) — ebenfalls einrücken
  assert.equal(feldEinruecken(felder, 1), true)
  assert.deepEqual(felder[0].inhalt.map((f) => f.id), ['a', 'c'])
  assert.deepEqual(felder.map((f) => f.id), ['b'])
  // einrücken an Position 0 nie
  assert.equal(feldEinruecken(felder, 0), false)
  feldEinfuegen(felder, 1, { id: 'neu', art: 'text' })
  assert.deepEqual(felder.map((f) => f.id), ['b', 'neu'])
  assert.deepEqual(feldLoeschen(felder, 1), { id: 'neu', art: 'text' })
  assert.equal(feldLoeschen(felder, 9), null)
})

test('feldPfadListe zeigt Gruppen, Varianten, Teile und Ablauf-Elemente', () => {
  const felder = [
    { id: 'lieder', art: 'eintrag', inhalt: [{ id: 'dirigent', art: 'person' }] },
    { id: 'abend', art: 'gruppe', inhalt: [{ id: 'leitung', art: 'person' }],
      varianten: [{ id: 'regen', inhalt: [{ id: 'halle', art: 'text' }] }],
      teile: [{ id: 'abschluss', inhalt: [{ id: 'abendlied', art: 'eintrag' }] }] },
    { id: 'ablauf', art: 'ablauf', elemente: [{ typ: 'lied', inhalt: [{ id: 'nr', art: 'zahl' }] }] },
  ]
  const pfade = feldPfadListe(felder).map((f) => f.pfad)
  assert.deepEqual(pfade, ['lieder', 'lieder.dirigent', 'abend', 'abend.leitung', 'abend.halle', 'abend.abendlied', 'ablauf', 'ablauf/lied.nr'])
  assert.deepEqual(topFeldIds(felder), ['lieder', 'abend', 'ablauf'])
})

// ── Knoten-Baukasten ───────────────────────────────────────────────────────

test('Knoten: genau ein Schlüssel, sauberes Wechseln, deutscher Text', () => {
  assert.equal(knotenSchluessel({ anlass: 'abendmahl' }), 'anlass')
  assert.equal(knotenSchluessel({}), '')
  assert.equal(knotenSchluessel({ a: 1, b: 2 }), '')
  assert.deepEqual(leerenKnoten('bedingung', 'wochentag'), { wochentag: ['so'] })
  assert.deepEqual(leerenKnoten('bedingung', 'termin_nr'), { termin_nr: { jede: 2 } })
  assert.deepEqual(leerenKnoten('rolle'), { merkmal: '' })
  assert.deepEqual(knotenWechseln({ anlass: 'x' }, 'bedingung', 'variante'), { variante: '' })
})

test('knotenText beschreibt Bedingungen verständlich', () => {
  assert.equal(knotenText({ anlass: 'abendmahl' }), 'Anlass „abendmahl“')
  assert.equal(knotenText({ nicht: { wochentag: ['mo'] } }), 'nicht Wochentag Montag')
  assert.equal(knotenText({ alle: [{ anlass: 'abendmahl' }, { variante: 'regen' }] }), '(Anlass „abendmahl“ und Variante „regen“)')
  assert.equal(knotenText({ eine: [{ merkmal: 'a' }, { merkmal: 'b' }] }), '(Eigenschaft „a“ oder Eigenschaft „b“)')
  assert.equal(knotenText({ parameter: { id: 'thema', gleich: 'herbst' } }), 'Parameter „thema“ = „herbst“')
  assert.equal(knotenText({ termin_nr: { jede: 2 } }), 'jeder 2. Termin')
  assert.equal(knotenText({ termin_im_monat: -1 }), '-1. Termin im Monat')
})

// ── Regel-Bausteine (schema-getriebenes Formular) ──────────────────────────

const mindestabstandSchema = {
  properties: {
    feld: { type: 'string', description: 'Kennung des Felds.', examples: ['lieder'] },
    wochen: { type: 'integer', minimum: 1, description: 'Mindestabstand in Wochen.' },
    fuer: { type: 'string', enum: ['eintrag', 'person'] },
  },
  required: ['feld', 'wochen'],
}

test('regelParameterForm baut Felder aus dem Parameter-Schema', () => {
  const felder = regelParameterForm({ beschreibung: 'Test', parameter_schema: mindestabstandSchema })
  assert.deepEqual(felder.map((f) => f.name), ['feld', 'wochen', 'fuer'])
  assert.equal(felder[0].pflicht, true)
  assert.equal(felder[1].pflicht, true)
  assert.equal(felder[2].pflicht, false)
  assert.equal(felder[0].typ, 'text')
  assert.equal(felder[1].typ, 'zahl')
  assert.equal(felder[2].typ, 'auswahl')
  assert.deepEqual(felder[2].werte, ['eintrag', 'person'])
  assert.equal(felder[0].beispiel, 'lieder')
  // Pflichtfelder zuerst
  const gemischt = regelParameterForm({ parameter_schema: { properties: { a: { type: 'string' }, b: { type: 'string' } }, required: ['b'] } })
  assert.deepEqual(gemischt.map((f) => f.name), ['b', 'a'])
})

test('regelParameterForm erkennt Filter, Fremdfeld und Muster', () => {
  const schema = {
    properties: {
      rolle: { oneOf: [{ $ref: '#/$defs/rollen_filter' }, { type: 'string', pattern: '^@' }] },
      uebung: { $ref: '#/$defs/fremd_feld' },
      muster: { oneOf: [{ type: 'string' }, { type: 'object' }] },
      felder: { type: 'array', items: { type: 'string' } },
      vorbelegte_mitzaehlen: { type: 'boolean' },
    },
  }
  const typen = Object.fromEntries(regelParameterForm({ parameter_schema: schema }).map((f) => [f.name, f.typ]))
  assert.equal(typen.rolle, 'filter')
  assert.equal(typen.uebung, 'fremd_feld')
  assert.equal(typen.muster, 'text_oder_json')
  assert.equal(typen.felder, 'liste')
  assert.equal(typen.vorbelegte_mitzaehlen, 'schalter')
})

test('regelWerte und regelBauen arbeiten verlustfrei und ohne Leerwerte', () => {
  const regel = { baustein: 'mindestabstand', feld: 'lieder', wochen: 8, stufe: 'sollte', gewicht: 1.5 }
  assert.deepEqual(regelWerte(regel), { feld: 'lieder', wochen: 8 })
  const leer = { baustein: 'x', feld: '', personen: [], extra: 'wert' }
  assert.deepEqual(regelWerte(leer), { extra: 'wert' })
  const neu = regelBauen('mindestabstand', 'muss', '', { feld: 'lieder', wochen: 8, leerer: '', liste: [] })
  assert.deepEqual(neu, { baustein: 'mindestabstand', stufe: 'muss', feld: 'lieder', wochen: 8 })
  const mitGewicht = regelBauen('gleich_verteilen', 'sollte', '2.5', { feld: 'team' })
  assert.equal(mitGewicht.gewicht, 2.5)
})

// ── JSON-Reiter ────────────────────────────────────────────────────────────

test('JSON synchron und verlustfrei: Format roundtrip, Lesefehler behalten den Text', () => {
  const def = { schema: 'diakronos/plantyp@1', id: 'chorplan', name: 'Chorplan', felder: [{ id: 'lieder', art: 'eintrag', anzahl: 3 }] }
  const text = jsonText(def)
  assert.ok(text.includes('\n  "schema"'), 'schön formatiert')
  const erg = jsonUebernehmen(text)
  assert.equal(erg.ok, true)
  assert.deepEqual(erg.definition, def)
  const kaputt = jsonUebernehmen('{ "id": ')
  assert.equal(kaputt.ok, false)
  assert.match(kaputt.fehler, /nicht lesbar/)
  const array = jsonUebernehmen('[1,2]')
  assert.equal(array.ok, false)
  assert.match(array.fehler, /Objekt/)
})

// ── Meldungen nach Abschnitt ───────────────────────────────────────────────

test('Prüfpfade werden Formularabschnitten zugeordnet', () => {
  assert.equal(abschnittsSchluessel('/felder/0/art'), 'felder:0')
  assert.equal(abschnittsSchluessel('/felder/2/inhalt/1/id'), 'felder:2')
  assert.equal(abschnittsSchluessel('/terminreihen/1/felder/0/sammlung'), 'terminreihe:1:felder:0')
  assert.equal(abschnittsSchluessel('/regeln/2/baustein'), 'regeln:2')
  assert.equal(abschnittsSchluessel('/ansichten/0/art'), 'ansichten:0')
  assert.equal(abschnittsSchluessel('/anlaesse/1/wirkung'), 'anlaesse:1')
  assert.equal(abschnittsSchluessel('/parameter/0/id'), 'parameter:0')
  assert.equal(abschnittsSchluessel(''), '')
  assert.equal(abschnittsSchluessel('/id'), 'id')

  const gruppen = meldungenNachAbschnitt([
    { pfad: '/felder/0/art', stufe: 'fehler' },
    { pfad: '/felder/0/id', stufe: 'warnung' },
    { pfad: '/felder/1/id', stufe: 'hinweis' },
  ])
  assert.equal(gruppen.get('felder:0').length, 2)
  assert.equal(gruppen.get('felder:1').length, 1)
  assert.equal(hoechsteStufe([{ stufe: 'hinweis' }, { stufe: 'warnung' }]), 'warnung')
  assert.equal(hoechsteStufe([{ stufe: 'warnung' }, { stufe: 'fehler' }]), 'fehler')
  assert.equal(hoechsteStufe([]), '')
})

// ── Kleine Helfer ──────────────────────────────────────────────────────────

test('Parameterreferenzen und Kennungen', () => {
  assert.equal(istParameterRef('{parameter.zeitraum}'), true)
  assert.equal(istParameterRef('{parameter.x} '), false)
  assert.equal(istParameterRef('2026-01-01'), false)
  assert.deepEqual(wertOderRefLesen('{parameter.zeitraum}'), { modus: 'parameter', wert: 'zeitraum', datum: '' })
  assert.deepEqual(wertOderRefLesen('2026-01-01'), { modus: 'datum', wert: '', datum: '2026-01-01' })
  assert.equal(wertOderRefAus({ modus: 'parameter', wert: 'zeitraum' }), '{parameter.zeitraum}')
  assert.equal(wertOderRefAus({ modus: 'datum', datum: '2026-01-01' }), '2026-01-01')
  assert.equal(wertOderRefAus({ modus: 'datum', datum: '' }), '')
  assert.equal(kennungGueltig('chorplan'), true)
  assert.equal(kennungGueltig('Chorplan'), false)
  assert.equal(kennungGueltig('1start'), true)
})

test('merkmalsZiele bietet person, lieder und eigene Sammlungen', () => {
  const ziele = merkmalsZiele({ sammlungen: [{ id: 'bibelarbeiten' }] }).map((z) => z.wert)
  assert.deepEqual(ziele, ['person', 'lieder', 'bibelarbeiten'])
  const leer = merkmalsZiele({}).map((z) => z.wert)
  assert.deepEqual(leer, ['person', 'lieder'])
})

test('leere Definition und leeres Feld tragen die Kennzeichnung', () => {
  assert.equal(leereDefinition().schema, 'diakronos/plantyp@1')
  assert.deepEqual(leeresFeld('gruppe'), { id: '', art: 'gruppe', inhalt: [] })
  assert.deepEqual(leeresFeld('ablauf'), { id: '', art: 'ablauf', elemente: [] })
  assert.deepEqual(leeresFeld('text'), { id: '', art: 'text' })
})

// ── Kochbuch-Roundtrip (echte Definitionsdateien) ──────────────────────────

test('Kochbuch-Chorplan überlebt den Editor-Roundtrip unverändert', () => {
  const pfad = '../../../../../backend/src/diakronos_app/planrahmen/doku/kochbuch/chorplan.json'
  const chor = JSON.parse(readFileSync(new URL(pfad, import.meta.url), 'utf8'))
  // JSON-Reiter: speichern, zurücklesen, identisch
  const erg = jsonUebernehmen(jsonText(chor))
  assert.equal(erg.ok, true)
  assert.deepEqual(erg.definition, chor)
  // Wiederholung verständlich
  assert.equal(wiederholungText(chor.termine.regel), 'jeden Sonntag')
  // Feldpfade für Spalten-/Regel-Auswahlen
  const pfade = feldPfadListe(chor.felder).map((f) => f.pfad)
  assert.ok(pfade.includes('lieder') && pfade.includes('lieder.dirigent') && pfade.includes('einsingen'))
  // Regeln: Formularfelder aus dem echten Schema kommen nicht zum Tragen
  // (Registry kommt per API) — aber Werte bleiben verlustfrei erhalten.
  assert.deepEqual(regelWerte(chor.regeln[1]), { feld: 'lieder', wochen: 8 })
})

test('Kochbuch-Musikteams: abgeleitete Reihe und Kalenderansicht bleiben lesbar', () => {
  const pfad = '../../../../../backend/src/diakronos_app/planrahmen/doku/kochbuch/musikteams.json'
  const musik = JSON.parse(readFileSync(new URL(pfad, import.meta.url), 'utf8'))
  const probe = musik.terminreihen.find((r) => r.id === 'probe')
  assert.equal(versatzText(probe.termine.abgeleitet.versatz), '2 Tag(e) vor dem Ursprungstermin')
  assert.equal(knotenText(probe.termine.abgeleitet.nur_wenn), 'nicht Anlass „feiertag“')
  const kalender = musik.ansichten.find((a) => a.art === 'kalender')
  assert.equal(kalender.spalten, 'monat')
  assert.equal(jsonUebernehmen(jsonText(musik)).ok, true)
})

test('alsListe liefert nur echte Arrays, sonst leer — ohne den Rohwert zu verändern', () => {
  const arr = ['a']
  assert.equal(alsListe(arr), arr, 'gültiges Array wird unverändert zurückgegeben')
  assert.deepEqual(alsListe('ostermontag'), [], 'String → leer')
  assert.deepEqual(alsListe({}), [], 'Objekt → leer')
  assert.deepEqual(alsListe(42), [], 'Zahl → leer')
  assert.deepEqual(alsListe(null), [], 'null → leer')
  assert.deepEqual(alsListe(undefined), [], 'undefined → leer')
})

test('Feiertags-Katalog und Wochentage sind vollständig und deutsch', () => {
  assert.equal(FEIERTAGE.length, 21)
  assert.ok(FEIERTAGE.some((f) => f.schluessel === 'karfreitag' && f.name === 'Karfreitag'))
  assert.ok(FEIERTAGE.some((f) => f.schluessel === '1_advent' && f.name === '1. Advent'))
  assert.equal(WOCHENTAGE.length, 7)
  assert.equal(WOCHENTAGE[6].name, 'Sonntag')
})
