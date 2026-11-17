/**
 * R6 — Nacharbeit nach dem Review (12.11.): Detail-Dialoge, Vorauswahl von der
 * Gruppenseite, „Neuer Beitrag“ nur mit Recht.
 *
 * Geprüft werden die Regeln, die die Oberfläche braucht — ohne Vue, damit sie
 * mit `node --test` laufen. Die Rechte entscheidet NIE diese Datei: sie liest
 * nur, was der Server antwortet.
 *
 * UI-R6b: Die Orte kommen in EINER Abfrage (`rechte.get_anlegeorte`), in
 * Anzeigereihenfolge und mit fertigem Titel — die früheren Prüfungen von
 * `anlegenOptionen`/`anlegenOptionenParallel` (eine Frage je Gruppe) sind
 * entfallen; an ihre Stelle tritt `anlegeorteAusAntwort` +
 * `darfIrgendwoAnlegen` + `vorauswahlOrt`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import { darfBearbeiten } from '../src/diakonos/composables/r6Detail.js'
import {
    darfIrgendwoAnlegen, gruppeAusAdresse, vorauswahlOrt,
} from '../src/diakonos/composables/r6AnlegenSichtbar.mjs'
import { anlegeorteAusAntwort, einheitWert, vorauswahl } from '../src/diakonos/composables/r6Gastzugang.mjs'

/** Antwort von `rechte.get_anlegeorte` — hier für einen Administrator. */
const ORTE_ADMIN = {
    orte: [
        { gruppe: null, untergruppe: null, titel: 'Alle Mitglieder der Gemeinde', tiefe: 0, gemeinde: true },
        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
        { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
    ],
}

const ORTE_HV = {
    orte: [
        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
    ],
}

// ── Punkt 1: Das Recht kommt aus dem Detail (Server entscheidet) ────────────
// AUFR-1: Die drei Prüfungen der Zusammenlegung `detailMitListe` (Liste + Detail)
// sind entfallen — seit UI-R6e tragen BEIDE Detail-Aufrufe `darf_bearbeiten`,
// die Hilfsfunktion hatte keinen Aufrufer mehr.

test('darfBearbeiten: nur echtes `true` zählt', () => {
    assert.equal(darfBearbeiten({ darf_bearbeiten: true }), true)
    assert.equal(darfBearbeiten({ darf_bearbeiten: false }), false)
    assert.equal(darfBearbeiten({ darf_bearbeiten: 'true' }), false, 'kein Text als Recht')
    assert.equal(darfBearbeiten({}), false)
    assert.equal(darfBearbeiten(null), false)
})

// ── Punkt 2: Vorauswahl von der Gruppenseite ───────────────────────────────

test('gruppeAusAdresse: Gruppe und Untergruppe aus dem Abfrageteil', () => {
    assert.deepEqual(
        gruppeAusAdresse('#/wiki?gruppe=GR-Chor&untergruppe=UG-Blas'),
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas' },
    )
    assert.deepEqual(gruppeAusAdresse('#/wiki?gruppe=GR-Chor'), { gruppe: 'GR-Chor', untergruppe: null })
    // Kodierte Kennungen (Leerzeichen, Umlaute) kommen richtig an.
    assert.deepEqual(
        gruppeAusAdresse('#/wiki?gruppe=GR%20Chor&untergruppe=UG%20Bl%C3%A4ser'),
        { gruppe: 'GR Chor', untergruppe: 'UG Bläser' },
    )
    // Ohne Abfrageteil: keine Vorauswahl.
    assert.equal(gruppeAusAdresse('#/wiki'), null)
    assert.equal(gruppeAusAdresse('#/wiki?foo=bar'), null)
    assert.equal(gruppeAusAdresse(''), null)
    assert.equal(gruppeAusAdresse(undefined), null)
})

test('gruppeAusAdresse → vorauswahl: die Gruppe der Seite steht im Feld', () => {
    const orte = anlegeorteAusAntwort(ORTE_ADMIN)
    const fest = gruppeAusAdresse('#/wiki?gruppe=GR-Chor&untergruppe=UG-Blas')
    assert.equal(vorauswahl(orte, fest), 'GR-Chor|UG-Blas')

    // Gruppe der Seite, für die die Person KEIN Anlege-Recht hat: keine
    // Vorauswahl bei mehreren Möglichkeiten (der Server bleibt die Wahrheit).
    const fremd = gruppeAusAdresse('#/wiki?gruppe=GR-Fremd')
    assert.equal(vorauswahl(orte, fremd), '')
})

// ── Punkt 2b (UI-R6b): der Sprung wird OHNE zweiten Klick eingelöst ───────

test('vorauswahlOrt: Hauptgruppe der Gruppenseite unter den Orten → dieser Ort', () => {
    const orte = anlegeorteAusAntwort(ORTE_HV)
    const treffer = vorauswahlOrt({ gruppe: 'GR-Chor', untergruppe: null }, orte, einheitWert)
    assert.ok(treffer, 'kein Ort gefunden')
    assert.equal(treffer.gruppe, 'GR-Chor')
    assert.equal(treffer.untergruppe, null)
    assert.equal(treffer.titel, 'Chor')
})

test('vorauswahlOrt: Untergruppe der Gruppenseite → genau diese Untergruppe', () => {
    const orte = anlegeorteAusAntwort(ORTE_HV)
    const treffer = vorauswahlOrt({ gruppe: 'GR-Chor', untergruppe: 'UG-Blas' }, orte, einheitWert)
    assert.ok(treffer, 'kein Ort gefunden')
    assert.equal(einheitWert(treffer), 'GR-Chor|UG-Blas')
    assert.equal(treffer.tiefe, 1)
})

test('vorauswahlOrt: kein Recht auf diese Einheit → KEIN Editor (kein zweiter Klick ins Leere)', () => {
    const orte = anlegeorteAusAntwort(ORTE_HV)
    assert.equal(vorauswahlOrt({ gruppe: 'GR-Fremd', untergruppe: null }, orte, einheitWert), null)
    // Untergruppe genannt, aber nur die Hauptgruppe erlaubt: kein Treffer.
    assert.equal(vorauswahlOrt({ gruppe: 'GR-Chor', untergruppe: 'UG-Saiten' }, orte, einheitWert), null)
    // Ohne Adresseinheit wird nichts geöffnet.
    assert.equal(vorauswahlOrt(null, orte, einheitWert), null)
    assert.equal(vorauswahlOrt({ gruppe: null, untergruppe: null }, orte, einheitWert), null)
    // Ohne Orte (Mitglied) ebenfalls nicht — und kein Absturz.
    assert.equal(vorauswahlOrt({ gruppe: 'GR-Chor' }, [], einheitWert), null)
    assert.equal(vorauswahlOrt({ gruppe: 'GR-Chor' }, null, einheitWert), null)
})

// ── Punkt 3: „Neuer Beitrag“ nur mit Recht ─────────────────────────────────

test('anlegeorteAusAntwort → darfIrgendwoAnlegen: der Kopfknopf hängt an der Serverantwort', () => {
    // Admin und HV: der Server nennt Orte → Knopf.
    assert.equal(darfIrgendwoAnlegen(anlegeorteAusAntwort(ORTE_ADMIN)), true)
    assert.equal(darfIrgendwoAnlegen(anlegeorteAusAntwort(ORTE_HV)), true)
    // Mitglied: der Server nennt KEINE → kein Knopf.
    assert.equal(darfIrgendwoAnlegen(anlegeorteAusAntwort({ orte: [] })), false,
        'ohne Ort KEIN „Neuer Beitrag/Artikel“')
    assert.equal(darfIrgendwoAnlegen([]), false)
    assert.equal(darfIrgendwoAnlegen(null), false)
    assert.equal(darfIrgendwoAnlegen(undefined), false)
})

test('Orte: Gemeinde nur für den Admin, und sie steht vorn', () => {
    const admin = anlegeorteAusAntwort(ORTE_ADMIN)
    const hv = anlegeorteAusAntwort(ORTE_HV)
    assert.equal(einheitWert(admin[0]), 'gemeinde', 'Gemeinde-Eintrag steht vorn')
    assert.ok(!hv.some(o => einheitWert(o) === 'gemeinde'), 'HV bekommt KEINE Gemeinde')
    // Der Titel ist der des Servers — kein eigener Text im Frontend.
    assert.equal(admin[0].titel, 'Alle Mitglieder der Gemeinde')
})
