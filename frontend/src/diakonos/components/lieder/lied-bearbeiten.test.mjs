/**
 * LI1 — Tests der reinen Formular-Logik „Lied anlegen und bearbeiten“.
 *
 * Deckt die Abnahmebedingungen des Karten-Texts ab:
 *  - Quelle 'Kopie' blendet Buch/Nummer/Seite aus (und leert sie),
 *  - Titel ist Pflicht,
 *  - Anlegen ohne `name`, Ändern mit `name`,
 *  - Strophen hinzufügen/entfernen/verschieben mit fortlaufenden Nummern.
 */
import assert from 'node:assert/strict'
import test from 'node:test'

import {
  QUELLEN, quellenfelderSichtbar, quelleLabel,
  STROPHEN_TYPEN, typNormalisieren, stropheHinzufuegen, stropheEntfernen,
  stropheVerschieben, strophenNummerieren,
  leeresFormular, formularAusLied, ableiteteQuelle, quelleGewechselt,
  formularAnzeige, formularIstKopie, pruefen, nutzlast, istNeuanlage,
} from './lied-bearbeiten.mjs'

/* ── Quelle ──────────────────────────────────────────────────────────────── */

test('Quelle: nur „Liederbuch“ zeigt Buch/Nummer/Seite', () => {
  assert.equal(quellenfelderSichtbar('buch'), true)
  assert.equal(quellenfelderSichtbar('kopie'), false)
  assert.equal(quellenfelderSichtbar('ohne'), false)
  assert.equal(quellenfelderSichtbar(''), false)
})

test('Quelle: jede Quelle hat eine verständliche Beschriftung ohne Fachbegriff', () => {
  for (const q of QUELLEN) {
    assert.ok(q.label.length > 0, q.wert + ' hat eine Beschriftung')
    assert.ok(q.hilfe.length > 0, q.wert + ' hat eine Hilfe')
    assert.doesNotMatch(q.label, /slot/i)
  }
  assert.equal(quelleLabel('kopie'), QUELLEN[1].label)
  assert.equal(quelleLabel('unbekannt'), QUELLEN[2].label, 'Unbekanntes fällt auf „Ohne Angabe“')
})

test('Quellenwechsel auf „Kopie“ leert Buch/Nummer/Seite', () => {
  const formular = { ...leeresFormular(), quelle: 'buch', buch: 'JN', gesangbuch_nummer: '1297', seite: '12' }
  const neu = quelleGewechselt(formular, 'kopie')
  assert.equal(neu.quelle, 'kopie')
  assert.equal(neu.buch, '')
  assert.equal(neu.gesangbuch_nummer, '')
  assert.equal(neu.seite, '')
})

test('Quellenwechsel auf „Ohne Angabe“ leert Buch/Nummer/Seite ebenfalls', () => {
  const formular = { ...leeresFormular(), quelle: 'buch', buch: 'JN', gesangbuch_nummer: '1297' }
  const neu = quelleGewechselt(formular, 'ohne')
  assert.equal(neu.buch, '')
  assert.equal(neu.gesangbuch_nummer, '')
})

test('Quellenwechsel auf „Liederbuch“ erhält bestehende Angaben', () => {
  const formular = { ...leeresFormular(), quelle: 'kopie', buch: '', gesangbuch_nummer: '' }
  const neu = quelleGewechselt(formular, 'buch')
  assert.equal(neu.quelle, 'buch')
  assert.equal(neu.buch, '')
})

/* ── Kennung / Anzeige ───────────────────────────────────────────────────── */

test('Kennung: Nummer hat Vorrang vor Seite, Kopie zeigt keine Nummer', () => {
  assert.equal(formularAnzeige({ quelle: 'buch', buch: 'JN', gesangbuch_nummer: '1297' }), 'JN 1297')
  assert.equal(formularAnzeige({ quelle: 'buch', buch: 'WH', seite: '150' }), 'WH S. 150')
  assert.equal(formularAnzeige({ quelle: 'kopie', buch: 'JN', gesangbuch_nummer: '1297' }), 'Kopie')
  assert.equal(formularAnzeige({ quelle: 'ohne', buch: 'JN' }), '')
  assert.equal(formularIstKopie({ quelle: 'kopie' }), true)
  assert.equal(formularIstKopie({ quelle: 'buch' }), false)
})

/* ── Vorbelegung ─────────────────────────────────────────────────────────── */

test('Altbestand ohne Quelle: Quelle wird aus Buch/Nummer/Seite abgeleitet', () => {
  assert.equal(ableiteteQuelle({ buch: 'JN' }), 'buch')
  assert.equal(ableiteteQuelle({ gesangbuch_nummer: '42' }), 'buch')
  assert.equal(ableiteteQuelle({ seite: '9' }), 'buch')
  assert.equal(ableiteteQuelle({}), 'ohne')
  assert.equal(ableiteteQuelle({ quelle: 'kopie', buch: 'JN' }), 'kopie', 'Serverwert gewinnt')
})

test('Kopie-Vorbelegung zeigt keine Nummernfelder, obwohl das Lied eine Nummer hatte', () => {
  const formular = formularAusLied(
    { name: 'L1', titel: 'Alt', quelle: 'kopie', buch: 'JN', gesangbuch_nummer: '99', kategorien: ['Lob'], anlaesse: ['Gottesdienst'] },
    [{ nummer: 1, typ: 'Refrain', text: 'Text', sprache: 'de', nur_chor: true }],
  )
  assert.equal(formular.quelle, 'kopie')
  assert.equal(formular.buch, '')
  assert.equal(formular.gesangbuch_nummer, '')
  assert.equal(quellenfelderSichtbar(formular.quelle), false)
  assert.deepEqual(formular.kategorien, ['Lob'])
  assert.deepEqual(formular.anlaesse, ['Gottesdienst'])
  assert.equal(formular.strophen.length, 1)
  assert.equal(formular.strophen[0].typ, 'Refrain')
  assert.equal(formular.strophen[0].nur_chor, true)
})

test('Formular-Aufbau nummeriert Strophen neu durch', () => {
  const formular = formularAusLied({ name: 'L1', titel: 'T', quelle: 'ohne' },
    [{ nummer: 7, text: 'a' }, { nummer: 9, text: 'b' }])
  assert.deepEqual(formular.strophen.map((s) => s.nummer), [1, 2])
})

/* ── Prüfung ─────────────────────────────────────────────────────────────── */

test('Prüfung: Titel ist Pflicht (auch nur Leerzeichen zählt nicht)', () => {
  assert.equal(pruefen(leeresFormular()).ok, false)
  assert.ok(pruefen(leeresFormular()).fehler.titel)
  assert.equal(pruefen({ ...leeresFormular(), titel: '   ' }).ok, false)
  assert.equal(pruefen({ ...leeresFormular(), titel: 'Komm, Herr' }).ok, true)
})

test('Prüfung: überlanger Titel wird abgelehnt', () => {
  const lang = 'x'.repeat(141)
  assert.equal(pruefen({ ...leeresFormular(), titel: lang }).ok, false)
  assert.equal(pruefen({ ...leeresFormular(), titel: 'x'.repeat(140) }).ok, true)
})

test('Prüfung: jede Strophe braucht Text', () => {
  const formular = { ...leeresFormular(), titel: 'T', strophen: [{ text: 'ok' }, { text: '   ' }] }
  const ergebnis = pruefen(formular)
  assert.equal(ergebnis.ok, false)
  assert.ok(ergebnis.fehler['strophe-1'], 'zweite Strophe wird benannt')
  assert.equal(ergebnis.fehler['strophe-0'], undefined)
})

test('Prüfung: Anlegen ohne Strophen ist erlaubt', () => {
  assert.equal(pruefen({ ...leeresFormular(), titel: 'Neu' }).ok, true)
})

/* ── Nutzlast ────────────────────────────────────────────────────────────── */

test('Nutzlast: Neuanlage ohne `name`, Änderung mit `name`', () => {
  assert.equal(istNeuanlage(leeresFormular()), true)
  const neu = nutzlast({ ...leeresFormular(), titel: 'Neu' })
  assert.equal('name' in neu, false, 'Anlegen schickt keinen Namen')

  const aenderung = nutzlast({ ...leeresFormular(), name: 'L1', titel: 'Anders' })
  assert.equal(istNeuanlage({ ...leeresFormular(), name: 'L1' }), false)
  assert.equal(aenderung.name, 'L1')
})

test('Nutzlast: Kopie schickt weder Buch noch Nummer noch Seite', () => {
  const formular = {
    ...leeresFormular(), name: 'L1', titel: 'Kopie-Lied', quelle: 'kopie',
    buch: 'JN', gesangbuch_nummer: '1297', seite: '3',
  }
  const werte = nutzlast(formular)
  assert.equal(werte.quelle, 'kopie')
  assert.equal(werte.buch, '')
  assert.equal(werte.gesangbuch_nummer, '')
  assert.equal(werte.seite, '')
})

test('Nutzlast: Buchlied überträgt Buch, Nummer und Seite', () => {
  const werte = nutzlast({
    ...leeresFormular(), name: 'L1', titel: 'Buchlied', quelle: 'buch',
    buch: 'JN', gesangbuch_nummer: '1297', seite: '5',
  })
  assert.equal(werte.buch, 'JN')
  assert.equal(werte.gesangbuch_nummer, '1297')
  assert.equal(werte.seite, '5')
})

test('Nutzlast: Listen ersetzen den Bestand und werden bereinigt', () => {
  const werte = nutzlast({
    ...leeresFormular(), name: 'L1', titel: 'T',
    kategorien: ['Lob', '  ', 'Abendmahl'],
    anlaesse: ['Gottesdienst', ''],
    strophen: [{ text: ' Erste ', typ: 'strophe', sprache: 'de', nur_chor: false }],
  })
  assert.deepEqual(werte.kategorien, ['Lob', 'Abendmahl'])
  assert.deepEqual(werte.anlaesse, ['Gottesdienst'])
  assert.equal(werte.strophen.length, 1)
  assert.equal(werte.strophen[0].nummer, 1)
  assert.equal(werte.strophen[0].typ, 'Strophe', 'Typ wird auf die bekannte Schreibweise gebracht')
  assert.equal(werte.strophen[0].text, ' Erste ', 'Text bleibt unverändert (Zeilenumbrüche!)')
})

test('Nutzlast: Titel wird außen beschnitten', () => {
  assert.equal(nutzlast({ ...leeresFormular(), titel: '  Komm  ' }).titel, 'Komm')
})

/* ── Strophen bearbeiten ─────────────────────────────────────────────────── */

test('Strophe hinzufügen zählt fortlaufend weiter und nimmt den Typ mit', () => {
  let strophen = []
  strophen = stropheHinzufuegen(strophen)
  strophen = stropheHinzufuegen(strophen, 'Refrain')
  strophen = stropheHinzufuegen(strophen, 'Bridge')
  assert.deepEqual(strophen.map((s) => s.nummer), [1, 2, 3])
  assert.deepEqual(strophen.map((s) => s.typ), ['Strophe', 'Refrain', 'Bridge'])
  assert.equal(strophen[0].text, '')
})

test('Strophe entfernen nummeriert die übrigen neu', () => {
  const strophen = stropheEntfernen(
    [{ nummer: 1, text: 'a' }, { nummer: 2, text: 'b' }, { nummer: 3, text: 'c' }], 1)
  assert.deepEqual(strophen.map((s) => s.text), ['a', 'c'])
  assert.deepEqual(strophen.map((s) => s.nummer), [1, 2])
})

test('Strophen verschieben tauscht die Reihenfolge und nummeriert neu', () => {
  const start = [{ nummer: 1, text: 'a' }, { nummer: 2, text: 'b' }, { nummer: 3, text: 'c' }]
  const hoch = stropheVerschieben(start, 2, -1)
  assert.deepEqual(hoch.map((s) => s.text), ['a', 'c', 'b'])
  assert.deepEqual(hoch.map((s) => s.nummer), [1, 2, 3])
  const runter = stropheVerschieben(start, 0, 1)
  assert.deepEqual(runter.map((s) => s.text), ['b', 'a', 'c'])
})

test('Strophen verschieben über den Rand ist wirkungslos', () => {
  const start = [{ nummer: 1, text: 'a' }, { nummer: 2, text: 'b' }]
  assert.deepEqual(stropheVerschieben(start, 0, -1), start)
  assert.deepEqual(stropheVerschieben(start, 1, 1), start)
})

test('Typ: bekannte Typen werden erkannt, Unbekanntes bleibt erhalten', () => {
  assert.deepEqual(STROPHEN_TYPEN, ['Strophe', 'Refrain', 'Bridge'])
  assert.equal(typNormalisieren('refrain'), 'Refrain')
  assert.equal(typNormalisieren('  BRIDGE '), 'Bridge')
  assert.equal(typNormalisieren(''), 'Strophe')
  assert.equal(typNormalisieren(null), 'Strophe')
  assert.equal(typNormalisieren('Zwischenspiel'), 'Zwischenspiel')
})

test('Nummerieren ändert die Texte nicht', () => {
  const strophen = strophenNummerieren([{ text: 'a', typ: 'Refrain' }, { text: 'b' }])
  assert.equal(strophen[0].text, 'a')
  assert.equal(strophen[0].typ, 'Refrain')
  assert.deepEqual(strophen.map((s) => s.nummer), [1, 2])
})
