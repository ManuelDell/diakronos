// UI-R9: die Regeln der Aufgaben-Oberfläche (rot → grün).
//
// Geprüft wird NUR, was die Oberfläche entscheidet: Kästchen/Menü nach den
// Server-Flags, Trennung offen/erledigt, Zuweisungstext, Fälligkeit,
// Zuweisungs-Auswahl und die Sperre des leeren Zuweisungsziels. Die
// Rechte-Logik selbst liegt beim Server (backend/tests/test_r7b_aufgaben.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
    darfAbhaken, darfBearbeiten, teileNachErledigt, zuweisungsText,
    offenZahlText, faelligkeit, zuweisungsOptionen, gruppenHref,
    gruppenName, darfEigeneAnlegen, anzeigeName, datumText,
} from '../src/diakonos/composables/aufgaben.mjs'

const zeile = (extra = {}) => ({
    name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
    erstellt_von: 'M-Rebekka', zugewiesen_an: null, zugewiesen_name: null,
    darf_abhaken: false, darf_bearbeiten: false, ...extra,
})

test('Kästchen nur, wenn der Server das Abhaken erlaubt', () => {
    assert.equal(darfAbhaken(zeile()), false)
    assert.equal(darfAbhaken(zeile({ darf_abhaken: true })), true)
    // Ohne Feld (alter Server / Fehlerzeile) gilt nein — fail closed.
    assert.equal(darfAbhaken({ name: 'x' }), false)
    assert.equal(darfAbhaken(null), false)
})

test('Menü „Zuweisung/Löschen“ nur, wenn der Server Bearbeiten erlaubt', () => {
    assert.equal(darfBearbeiten(zeile()), false)
    assert.equal(darfBearbeiten(zeile({ darf_bearbeiten: true })), true)
    assert.equal(darfBearbeiten(undefined), false)
})

test('offen und erledigt werden getrennt, Reihenfolge bleibt', () => {
    const liste = [zeile({ name: 'a' }), zeile({ name: 'b', erledigt: true }), zeile({ name: 'c' })]
    const { offen, erledigt } = teileNachErledigt(liste)
    assert.deepEqual(offen.map(a => a.name), ['a', 'c'])
    assert.deepEqual(erledigt.map(a => a.name), ['b'])
    // Kein Fehler bei fehlender Liste (Ladezustand vor der Antwort).
    assert.deepEqual(teileNachErledigt(undefined), { offen: [], erledigt: [] })
})

test('Zuweisung als Text: Name, „Niemandem zugewiesen“, eigene Aufgabe ohne Text', () => {
    assert.equal(zuweisungsText(zeile({ zugewiesen_name: 'Miriam Saenger' })), 'Zugewiesen an Miriam Saenger')
    assert.equal(zuweisungsText(zeile({ gruppe: 'Chor' })), 'Niemandem zugewiesen')
    assert.equal(zuweisungsText(zeile({ eigene: true })), '')
    assert.equal(zuweisungsText(zeile({ zugewiesen_name: '   ' , gruppe: 'Chor' })), 'Niemandem zugewiesen')
    // Auch eine Gruppenaufgabe OHNE `gruppen`-Felder (alte Form) bleibt sichtbar.
    assert.equal(zuweisungsText(zeile({ untergruppe: 'Sopran' })), 'Niemandem zugewiesen')
})

test('Zuweisungstext mit NUR den Server-Feldern der Gruppenseite', () => {
    // UI-R9c: `get_gruppe_detail` liefert je Aufgabe ausschliesslich
    // name, titel, erledigt, faellig, erstellt_von, zugewiesen_an,
    // zugewiesen_name, darf_abhaken, darf_bearbeiten — KEIN gruppe/untergruppe/
    // eigene. Die alte Kopplung an `gruppe` liess den Text deshalb leer.
    const gruppenseite = (extra = {}) => ({
        name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
        erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
        darf_abhaken: true, darf_bearbeiten: false, ...extra,
    })
    assert.equal(zuweisungsText(gruppenseite()), 'Niemandem zugewiesen')
    assert.equal(zuweisungsText(gruppenseite({ zugewiesen_an: 'M-MIRA', zugewiesen_name: 'Miriam Saenger' })),
        'Zugewiesen an Miriam Saenger')
    // Eigene Aufgabe der Kachel (mit `eigene`) sagt weiterhin nichts.
    assert.equal(zuweisungsText({ ...gruppenseite(), eigene: true }), '')
})

test('Zähltext ohne Klammerplural', () => {
    assert.equal(offenZahlText([]), '0 offen')
    assert.equal(offenZahlText([zeile()]), '1 offen')
    assert.equal(offenZahlText([zeile(), zeile({ name: 'b' })]), '2 offen')
    assert.equal(offenZahlText([zeile(), zeile({ name: 'b', erledigt: true })]), '1 offen, 1 erledigt')
    assert.equal(offenZahlText([zeile({ erledigt: true }), zeile({ name: 'b', erledigt: true })]), '0 offen, 2 erledigt')
})

test('Fälligkeit: heute, überfällig, künftig, erledigt ohne Text', () => {
    const jetzt = new Date(2026, 10, 12, 9, 0, 0) // 12.11.2026, lokale Zeit
    assert.deepEqual(faelligkeit(zeile({ faellig: '2026-11-12' }), jetzt),
        { text: 'Heute fällig', ueberfaellig: false })
    const alt = faelligkeit(zeile({ faellig: '2026-11-05' }), jetzt)
    assert.equal(alt.ueberfaellig, true)
    assert.equal(alt.text, 'Überfällig seit 5.11.2026')
    const spaeter = faelligkeit(zeile({ faellig: '2026-12-01' }), jetzt)
    assert.equal(spaeter.ueberfaellig, false)
    assert.equal(spaeter.text, 'Fällig am 1.12.2026')
    // Abgehakt: keine Frist mehr — auch nicht „überfällig“.
    assert.deepEqual(faelligkeit(zeile({ faellig: '2026-11-05', erledigt: true }), jetzt),
        { text: '', ueberfaellig: false })
    assert.deepEqual(faelligkeit(zeile(), jetzt), { text: '', ueberfaellig: false })
})

test('Ein Zeitstempel gilt an seinem Tag als „heute“ (lokale Zeit, nicht UTC)', () => {
    const jetzt = new Date(2026, 10, 12, 23, 30, 0)
    // Ein Zeitstempel mit Uhrzeit am selben Tag in lokaler Zeit.
    const eigener = new Date(2026, 10, 12, 8, 0, 0).toISOString()
    assert.equal(faelligkeit(zeile({ faellig: eigener }), jetzt).text, 'Heute fällig')
})

test('datumText ist deutsches Datum, unbekanntes bleibt lesbar', () => {
    // Reines Datum wird zerlegt — kein Zeitzonen-Versatz, keine führende Null.
    assert.equal(datumText('2026-11-05'), '5.11.2026')
    assert.equal(datumText(''), '')
    assert.equal(datumText('kein-datum'), 'kein-datum')
    // Zeitstempel: derselbe Kalendertag in lokaler Zeit.
    assert.equal(datumText(new Date(2026, 0, 2, 23, 30).toISOString()), '2.1.2026')
})

test('Auswahl „Zuweisen an“: nur echte Personen, einmal, alphabetisch, mit „niemand“', () => {
    const mitglieder = [
        { mitglied: 'M-Sa', vollstaendiger_name: 'Samuel Saenger' },
        { mitglied: 'M-Mira', vollstaendiger_name: 'Miriam Abraham' },
        { mitglied: 'M-Sa', vollstaendiger_name: 'Samuel Saenger' }, // Dublette
        { name: 'Zeile ohne Person' },                                // keine Kennung
        { mitglied: 'M-Ohne', name: 'Ohne Nachname' },                // Name als Ersatz
    ]
    const optionen = zuweisungsOptionen(mitglieder)
    assert.deepEqual(optionen.map(o => o.value), ['', 'M-Mira', 'M-Ohne', 'M-Sa'])
    assert.equal(optionen[0].label, 'Niemanden (offen für die Gruppe)')
    assert.equal(optionen[2].label, 'Ohne Nachname')
    // Leere/fremde Eingabe: nur der „niemand“-Eintrag.
    assert.deepEqual(zuweisungsOptionen(null).map(o => o.value), [''])
})

test('Link zur Gruppe: Untergruppe vor Gruppe, ohne Gruppe leer', () => {
    assert.equal(gruppenHref(zeile({ gruppe: 'Chor' })), '#/gruppe/Chor')
    assert.equal(gruppenHref(zeile({ gruppe: 'Chor', untergruppe: 'Sopran' })), '#/gruppe/Sopran')
    assert.equal(gruppenHref(zeile({ eigene: true })), '')
})

test('Kachel-Name einer Gruppenaufgabe: `gruppe_name` vom Server, NICHT die Kennung', () => {
    // UI-R9c: `get_meine_aufgaben` schickt seit R-12k den Anzeigenamen —
    // vorher nannte die Kachel die Kennung („UG-2“).
    assert.equal(gruppenName(zeile({ gruppe: 'GRU-1', untergruppe: 'UG-2', gruppe_name: 'Sopranstimmen' })),
        'Sopranstimmen')
    assert.equal(gruppenName(zeile({ gruppe: 'GRU-1', gruppe_name: 'Chor' })), 'Chor')
    // Ohne `gruppe_name` (alter Server / eigene Aufgabe): Leertext, keine Kennung.
    assert.equal(gruppenName(zeile({ gruppe: 'GRU-1', untergruppe: 'UG-2' })), '')
    assert.equal(gruppenName(zeile({ eigene: true, gruppe_name: null })), '')
    assert.equal(gruppenName(null), '')
})

test('Eigene Aufgabe anlegen nur bei klarem Ja des Servers', () => {
    assert.equal(darfEigeneAnlegen({ darf_eigene_aufgabe: true }), true)
    assert.equal(darfEigeneAnlegen({ darf_eigene_aufgabe: false }), false)
    assert.equal(darfEigeneAnlegen({}), false)
    assert.equal(darfEigeneAnlegen(undefined), false)
})

test('Anzeigename einer Gruppe: Name vor Kennung', () => {
    // UI-R9b: der Link „Zur Gruppe“ zeigte „GRU-1“ — gelesen wird der Name.
    assert.equal(anzeigeName({ name: 'GRU-1', gruppenname: 'Chor' }, 'GRU-1'), 'Chor')
    assert.equal(anzeigeName({ name: 'UG-2', untergruppenname: 'Sopran' }, 'UG-2'), 'Sopran')
    assert.equal(anzeigeName({ name: 'GRU-1', gruppen_name: 'Chor' }, 'GRU-1'), 'Chor')
    // Ohne Namen bleibt der Ersatztext (und nur der ist die Kennung).
    assert.equal(anzeigeName({ name: 'GRU-1' }, 'GRU-1'), 'GRU-1')
    assert.equal(anzeigeName(null, ''), '')
    assert.equal(anzeigeName(undefined), '')
})
