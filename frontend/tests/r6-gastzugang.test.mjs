/**
 * R6 — Beiträge/Wiki: Gruppe wählen, Gast-Links, Gastseite.
 *
 * Prüft die Regeln der Oberfläche (`composables/r6Gastzugang.mjs`) — die
 * Rechte selbst entscheidet der Server; hier wird nur geprüft, dass die
 * Oberfläche seine Antworten richtig deutet und nichts erfindet.
 *
 * UI-R6b: Die Orte kommen FERTIG vom Server (`rechte.get_anlegeorte` →
 * `{orte: [{gruppe, untergruppe, titel, tiefe, gemeinde}]}`, Anzeigereihenfolge).
 * Die früheren Prüfungen der eigenen Gruppenhierarchie und der Einzelfragen je
 * Gruppe (`gruppenAuswahl`, `anlegenOptionen`) sind entfallen — es gibt sie
 * nicht mehr. An ihre Stelle tritt `anlegeorteAusAntwort`, das die Serverliste
 * unverändert übernimmt.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
    GAST_FEHLER_ABGELAUFEN, GAST_FEHLER_PASSWORT, GAST_FEHLER_ZUVIELE,
    GAST_TAGE_STANDARD,
    anlegeorteAusAntwort, einheitText, einheitWert, gewaehlteEinheit,
    gastFehlertext, gastLinkAdresse, gastLinkAdresseFuer, gastlinkAktiv, gastNutzlast,
    gastlinkPruefung, gastlinkStatus, ortAusWert, vorauswahl, zeitpunkt,
} from '../src/diakonos/composables/r6Gastzugang.mjs'
import * as modul from '../src/diakonos/composables/r6Gastzugang.mjs'
import { serverZeitText } from '../src/shared/zeit.mjs'

/**
 * So antwortet `rechte.get_anlegeorte` einem Administrator: Gemeinde zuerst,
 * dann je Gruppe die Gruppe und ihre Untergruppen (Anzeigereihenfolge).
 */
const ORTE_ADMIN = {
    orte: [
        { gruppe: null, untergruppe: null, titel: 'Alle Mitglieder der Gemeinde', tiefe: 0, gemeinde: true },
        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
        { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
    ],
}

/** So antwortet er einer Hauptverantwortlichen (HV): Gruppe + eine Untergruppe. */
const ORTE_HV = {
    orte: [
        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
    ],
}

// ── Orte vom Server ─────────────────────────────────────────────────────────

test('anlegeorteAusAntwort: übernimmt Titel, Tiefe und Reihenfolge des Servers', () => {
    const zeilen = anlegeorteAusAntwort(ORTE_ADMIN)
    // Reihenfolge 1:1 wie geliefert (Gemeinde zuerst, dann Gruppe/Untergruppe) —
    // die Oberfläche sortiert NICHT nach.
    assert.deepEqual(zeilen.map(z => [z.gruppe, z.untergruppe, z.titel, z.tiefe]), [
        [null, null, 'Alle Mitglieder der Gemeinde', 0],
        ['GR-Chor', null, 'Chor', 0],
        ['GR-Chor', 'UG-Blas', 'Bläsergruppe', 1],
        ['GR-Jugend', null, 'Jugendkreis', 0],
    ])
    assert.equal(zeilen[0].gemeinde, true, 'Gemeinde-Eintrag ist als solcher erkennbar')
    assert.equal(zeilen[1].gemeinde, false)
})

test('anlegeorteAusAntwort: HV bekommt Gruppe + Untergruppe, KEINE Gemeinde', () => {
    const zeilen = anlegeorteAusAntwort(ORTE_HV)
    assert.deepEqual(zeilen.map(einheitWert), ['GR-Chor', 'GR-Chor|UG-Blas'])
    assert.ok(!zeilen.some(z => z.gemeinde), 'ohne Admin-Recht KEIN Gemeinde-Eintrag')
})

test('anlegeorteAusAntwort: Mitglied ohne Orte → leere Liste (kein erfundenes Recht)', () => {
    assert.deepEqual(anlegeorteAusAntwort({ orte: [] }), [])
    assert.deepEqual(anlegeorteAusAntwort({}), [])
    // Ein Ort ohne Gruppe zählt NUR als Gemeinde-Eintrag — kein Eintrag mit
    // leerer Kennung, der beim Anlegen ins Leere liefe.
    assert.deepEqual(anlegeorteAusAntwort({ orte: [{ titel: 'kaputt', tiefe: 0 }] }), [])
    // Nichts davon ist ein Absturzgrund.
    assert.deepEqual(anlegeorteAusAntwort(null), [])
    assert.deepEqual(anlegeorteAusAntwort(undefined), [])
})

test('anlegeorteAusAntwort: nimmt auch die nackte Liste und überspringt Leeres', () => {
    const zeilen = anlegeorteAusAntwort([
        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
        null,
        { gruppe: '', untergruppe: null, titel: 'ohne Kennung', tiefe: 0, gemeinde: false },
    ])
    assert.equal(zeilen.length, 1)
    assert.equal(zeilen[0].gruppe, 'GR-Chor')
})

test('anlegeorteAusAntwort: Ort OHNE `titel` wird verworfen (UI-R6c: kein Ersatztext erfunden)', () => {
    // UI-R6c (Punkt 4): Frueher stand hier die rohe Kennung („GR-Chor“) bzw.
    // bei Gemeinde ein eigener Text — und genau der landete bei genau EINEM
    // Anlegeort im Editor. Jetzt gilt: fehlt der `titel`, ist die Antwort des
    // Servers unvollstaendig; die Oberflaeche zeigt lieber nichts als eine
    // Kennung. `tiefe` bleibt unabhaengig davon berechnet.
    const zeilen = anlegeorteAusAntwort({
        orte: [
            { gruppe: 'GR-Chor', untergruppe: null },
            { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe' },
            { gruppe: null, untergruppe: null, gemeinde: true },
            { gruppe: null, untergruppe: null, titel: 'Alle Mitglieder der Gemeinde', gemeinde: true },
        ],
    })
    assert.deepEqual(zeilen.map(z => z.titel), ['Bläsergruppe', 'Alle Mitglieder der Gemeinde'],
        'nur Orte MIT Server-Titel bleiben')
    assert.equal(zeilen[0].tiefe, 1, 'Untergruppe ohne `tiefe` wird eingerueckt')
    assert.equal(zeilen[1].gemeinde, true)
})

test('einheitWert/ortAusWert: hin und zurück, Gemeinde als eigener Wert', () => {
    assert.equal(einheitWert({ gruppe: 'GR-Chor', untergruppe: null }), 'GR-Chor')
    assert.equal(einheitWert({ gruppe: 'GR-Chor', untergruppe: 'UG-Blas' }), 'GR-Chor|UG-Blas')
    assert.equal(einheitWert({ gruppe: null }), 'gemeinde')
    assert.equal(einheitWert(null), '')

    assert.deepEqual(ortAusWert('GR-Chor|UG-Blas'), { gruppe: 'GR-Chor', untergruppe: 'UG-Blas' })
    assert.deepEqual(ortAusWert('GR-Chor'), { gruppe: 'GR-Chor', untergruppe: null })
    assert.deepEqual(ortAusWert('gemeinde'), { gruppe: null, untergruppe: null })
    assert.deepEqual(ortAusWert(''), { gruppe: null, untergruppe: null })
})

test('ortAusWert: der Server-Titel reist mit (UI-R6c: auch beim Weg über die Auswahl)', () => {
    const orte = anlegeorteAusAntwort(ORTE_ADMIN)
    const chor = ortAusWert('GR-Chor', orte)
    assert.deepEqual(chor, { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false })
    assert.equal(ortAusWert('GR-Chor|UG-Blas', orte).titel, 'Bläsergruppe')
    assert.equal(ortAusWert('gemeinde', orte).titel, 'Alle Mitglieder der Gemeinde')
    // Kein Treffer: nur die Kennungen, KEIN erfundener Titel.
    assert.deepEqual(ortAusWert('GR-Fremd', orte), { gruppe: 'GR-Fremd', untergruppe: null })
})

test('einheitText: allein der Titel des Servers — kein eigener Gemeinde-Text, keine Kennung', () => {
    const [gemeinde, chor, blas] = anlegeorteAusAntwort(ORTE_ADMIN).slice(0, 3)
    assert.equal(einheitText(gemeinde), 'Alle Mitglieder der Gemeinde')
    assert.equal(einheitText(chor), 'Chor')
    assert.equal(einheitText(blas), 'Bläsergruppe')
    // UI-R6c (Punkt 4): `GEMEINDE_TEXT` ist entfallen — ohne Titel bleibt es
    // leer, statt einen eigenen Text oder die Kennung zu erfinden.
    assert.equal(einheitText({ gruppe: null }), '')
    assert.equal(einheitText({ gruppe: 'GR-Chor', untergruppe: 'UG-Blas' }), '')
    assert.equal(einheitText(undefined), '')
    // Und die Groesse gibt es nicht mehr (Gegenprobe: ein Wiedereinbau bricht).
    assert.equal('GEMEINDE_TEXT' in modul, false, 'GEMEINDE_TEXT ist wieder da')
})

// ── Vorauswahl ──────────────────────────────────────────────────────────────

test('vorauswahl: Gruppe der Gruppen-Seite hat Vorrang', () => {
    const orte = anlegeorteAusAntwort(ORTE_ADMIN)
    assert.equal(vorauswahl(orte, { gruppe: 'GR-Chor' }), 'GR-Chor')
    assert.equal(vorauswahl(orte, { gruppe: 'GR-Chor', untergruppe: 'UG-Blas' }), 'GR-Chor|UG-Blas')
})

test('vorauswahl: feste Gruppe nicht in der Liste → keine Vorauswahl bei mehreren', () => {
    const orte = anlegeorteAusAntwort(ORTE_ADMIN)
    assert.equal(vorauswahl(orte, { gruppe: 'GR-Fremd' }), '')
})

test('vorauswahl: genau eine Möglichkeit wird gewählt, mehrere nicht', () => {
    assert.equal(vorauswahl([{ gruppe: 'A' }]), 'A')
    assert.equal(vorauswahl(anlegeorteAusAntwort(ORTE_ADMIN)), '')
    assert.equal(vorauswahl([]), '')
    assert.equal(vorauswahl(null), '')
})

// ── Was steht im Auswahlfeld wirklich? ─────────────────────────────────────

test('gewaehlteEinheit: angezeigt wird der erste Eintrag, also zählt er auch', () => {
    const orte = anlegeorteAusAntwort(ORTE_ADMIN)
    // Ohne Vorauswahl: der Browser ZEIGT den ersten Eintrag — „Weiter“ darf
    // nicht gesperrt sein (Befund aus dem Beleg-Lauf).
    assert.equal(gewaehlteEinheit(orte), 'gemeinde')
    // Vorauswahl hat Vorrang vor dem ersten Eintrag.
    assert.equal(gewaehlteEinheit(orte, { start: 'GR-Chor|UG-Blas' }), 'GR-Chor|UG-Blas')
    // Eigene Wahl schlägt die Vorauswahl.
    assert.equal(
        gewaehlteEinheit(orte, { eigeneWahl: 'GR-Jugend', start: 'GR-Chor' }),
        'GR-Jugend',
    )
    // Unbekannte eigene Wahl (Liste hat sich geändert) fällt zurück.
    assert.equal(gewaehlteEinheit(orte, { eigeneWahl: 'GR-Weg', start: 'GR-Jugend' }), 'GR-Jugend')
    // Leere Liste: nichts gewählt.
    assert.equal(gewaehlteEinheit([]), '')
    assert.equal(gewaehlteEinheit(null), '')
})

// ── Gast-Link: Prüfung im Dialog ────────────────────────────────────────────

test('gastlinkPruefung: Passwort zweimal, mindestens 8 Zeichen, 1–30 Tage', () => {
    assert.equal(gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim123' }), null)
    assert.deepEqual(
        gastlinkPruefung({ passwort: 'kurz', wiederholung: 'kurz' }),
        { feld: 'passwort', meldung: 'Das Passwort braucht mindestens 8 Zeichen.' },
    )
    assert.deepEqual(
        gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim124' }),
        { feld: 'wiederholung', meldung: 'Die beiden Passwörter sind nicht gleich.' },
    )
    for (const tage of [0, 31, 2.5, 'viele', null]) {
        assert.equal(
            gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim123', tage }).feld,
            'tage',
            `Gültigkeit ${tage} muss abgelehnt werden`,
        )
    }
    assert.equal(gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim123', tage: 1 }), null)
    assert.equal(gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim123', tage: 30 }), null)
    // Standard ohne Angabe: 3 Tage (Karte).
    assert.equal(GAST_TAGE_STANDARD, 3)
    assert.equal(gastlinkPruefung({ passwort: 'geheim123', wiederholung: 'geheim123' }), null)
})

test('gastLinkAdresse: Token kodiert, Betriebs-Präfix und alter Hash bleiben draußen', () => {
    assert.equal(
        gastLinkAdresse('https://gemeinde.example/diakronos/gastinhalt', 'abC-123_x'),
        'https://gemeinde.example/diakronos/gastinhalt#/gast/abC-123_x',
    )
    // Ein vorhandener Hash (die Person ist gerade in der App) fliegt raus.
    assert.equal(
        gastLinkAdresse('https://gemeinde.example/diakronos/gastinhalt#/beitraege', 'tok/en'),
        'https://gemeinde.example/diakronos/gastinhalt#/gast/tok%2Fen',
    )
})

test('gastLinkAdresseFuer: Adresse des ANSEHENDEN Dokuments, mit und ohne Präfix', () => {
    assert.equal(
        gastLinkAdresseFuer({ ursprung: 'https://gemeinde.example', pfad: '' }, 'tok'),
        'https://gemeinde.example/gastinhalt#/gast/tok',
    )
    assert.equal(
        gastLinkAdresseFuer({ ursprung: 'https://gemeinde.example/', pfad: '/diakronos/' }, 'tok'),
        'https://gemeinde.example/diakronos/gastinhalt#/gast/tok',
    )
    // Kein `//` und kein doppelter Schrägstrich, auch ohne Ursprung.
    assert.equal(gastLinkAdresseFuer({}, 'tok'), '/gastinhalt#/gast/tok')
})

test('gastlinkStatus: Aktiv / Abgelaufen / Widerrufen', () => {
    const jetzt = Date.UTC(2026, 10, 12, 10, 0, 0)
    assert.equal(gastlinkStatus({ ablauf: '2026-11-15 09:00:00' }, jetzt), 'Aktiv')
    assert.equal(gastlinkStatus({ ablauf: '2026-11-11 09:00:00' }, jetzt), 'Abgelaufen')
    assert.equal(gastlinkStatus({ ablauf: '2026-11-15 09:00:00', widerrufen: true }, jetzt), 'Widerrufen')
    assert.equal(gastlinkStatus({ ablauf: '' }, jetzt), 'Abgelaufen')
    assert.equal(gastlinkAktiv({ ablauf: '2026-11-15 09:00:00' }, jetzt), true)
    assert.equal(gastlinkAktiv({ ablauf: '2026-11-15 09:00:00', widerrufen: true }, jetzt), false)
    assert.equal(gastlinkAktiv({ ablauf: '2026-11-11 09:00:00' }, jetzt), false)
})

test('zeitpunkt: Serverzeit ist UTC (nicht Ortszeit), Text in der Gemeindezone', () => {
    // 15:30 UTC = 16:30 in Berlin (Winterzeit).
    assert.equal(zeitpunkt('2026-11-15 15:30:00'), Date.UTC(2026, 10, 15, 15, 30, 0))
    // ISO-Form mit T wird genauso gelesen.
    assert.equal(zeitpunkt('2026-11-15T15:30:00'), Date.UTC(2026, 10, 15, 15, 30, 0))
    assert.equal(zeitpunkt(''), null)
    assert.equal(zeitpunkt(null), null)
})

test('zeitpunktText: die Anzeige kommt aus `shared/zeit.mjs` (Wrapper entfallen)', () => {
    // UI-R6b: `r6Gastzugang.zeitpunktText` war nur eine Umleitung auf
    // `serverZeitText` — der tote Wrapper ist weg, die Anzeige unverändert.
    assert.equal(serverZeitText('2026-11-15 15:30:00'), '15.11.2026, 16:30')
    assert.equal(serverZeitText(''), '')
})

// ── Gastseite: Fehlertexte ─────────────────────────────────────────────────

test('gastFehlertext: 404 = ungültig/abgelaufen, 403 = Passwort, Bremse = zu viele', () => {
    assert.equal(gastFehlertext(404, 'egal'), GAST_FEHLER_ABGELAUFEN)
    assert.equal(gastFehlertext(403, 'Das Passwort stimmt nicht.'), GAST_FEHLER_PASSWORT)
    assert.equal(gastFehlertext(403, 'Zu viele Versuche. Bitte versuche es später erneut.'), GAST_FEHLER_ZUVIELE)
    assert.equal(gastFehlertext(429, ''), GAST_FEHLER_ZUVIELE)
    // Unerwartete Antwort erfindet keine „ungültig“-Meldung.
    const text = gastFehlertext(500, 'Serverfehler')
    assert.equal(text, 'Serverfehler')
    assert.notEqual(text, GAST_FEHLER_ABGELAUFEN)
})

test('Gastfehler-Wortlaut ist der der Karte', () => {
    assert.equal(GAST_FEHLER_ABGELAUFEN, 'Dieser Link ist ungültig oder abgelaufen.')
    assert.equal(GAST_FEHLER_PASSWORT, 'Das Passwort stimmt nicht.')
    assert.match(GAST_FEHLER_ZUVIELE, /^Zu viele Versuche/)
})

// ── Nutzlast auspacken (Befund: leere öffentliche Seite) ───────────────────

test('gastNutzlast: die Compat-Schicht liefert die Nutzlast unter `message`', () => {
    // So antwortet der Server wirklich (Messung am Wegwerf-Stack).
    const antwort = {
        message: { typ: 'beitrag', titel: 'Chorprobe am Mittwoch', inhalt: '<p>Text</p>', datum: '2026-11-12' },
    }
    assert.deepEqual(gastNutzlast(antwort), {
        typ: 'beitrag', titel: 'Chorprobe am Mittwoch', inhalt: '<p>Text</p>', datum: '2026-11-12',
    })
    assert.equal(gastNutzlast(antwort).titel, 'Chorprobe am Mittwoch')
})

test('gastNutzlast: Fehlertext bleibt Text, ungepackte Antwort bleibt sie selbst', () => {
    // 404/403 tragen `message` als TEXT — der darf nicht als Nutzlast gelten.
    const fehler = { message: 'Dieser Link ist ungültig oder abgelaufen.' }
    assert.deepEqual(gastNutzlast(fehler), fehler)
    // Antwort ohne Hülle (falls der Server sie später direkt liefert).
    const direkt = { typ: 'wiki', titel: 'Ordnung', inhalt: '', datum: null }
    assert.deepEqual(gastNutzlast(direkt), direkt)
    // Nichts davon ist ein Absturzgrund.
    assert.deepEqual(gastNutzlast(null), {})
    assert.deepEqual(gastNutzlast(undefined), {})
    assert.deepEqual(gastNutzlast({ message: [{ a: 1 }] }), { message: [{ a: 1 }] })
})
