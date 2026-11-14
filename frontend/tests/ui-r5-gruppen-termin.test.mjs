// UI-R5 — „+ Termin“ auf der Gruppenseite.
//
// Reine Regeln der Oberfläche (`components/gruppen/gruppenTermin.mjs`):
// welche Kalender gehören zu dieser Gruppe, wann erscheint der Knopf, welcher
// Kalender ist vorbelegt, wann steht der Prüfhinweis. Die Rechte selbst
// entscheidet der Server — hier wird nur gelesen, was er liefert.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { vorschlagZeitraum } from '../src/diakonos/composables/datumZeit.mjs'
import {
    PRUEFHINWEIS,
    STATUS_DIREKT,
    kalenderDerGruppe,
    vorbelegterKalender,
    wirdGeprueft,
    statusFuerKalender,
    kalenderOptionen,
    formularZeitraum,
    stufenName,
    meldungNachSpeichern,
    ortszeitTeile,
} from '../src/diakonos/components/gruppen/gruppenTermin.mjs'

/** Quelle als Text (für „eine Quelle, keine Kopie“-Prüfungen). */
const lies = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')

// Serverliste wie `get_accessible_calendars` (R-5): je Kalender `write`,
// `direkt`, `stufen`, `pruefstufen`, `gruppe`, `untergruppe`.
const CHOR = {
    name: 'chorkal', title: 'Chor', write: true, direkt: true, stufen: ['gruppe'],
    pruefstufen: ['gruppe'], gruppe: 'chor', untergruppe: null,
}
const SOPRAN = {
    name: 'sopran-kal', title: 'Sopran', write: true, direkt: true, stufen: [],
    pruefstufen: [], gruppe: 'chor', untergruppe: 'sopran',
}
const SOPRAN_OEFFENTLICH = {
    name: 'sopran-offen', title: 'Sopran öffentlich', write: true, direkt: false,
    stufen: ['gruppe'], geschuetzt: true, pruefstufen: ['gruppe'], gruppe: 'chor', untergruppe: 'sopran',
}
const GEMEINDE = {
    name: 'gemeinde-kal', title: 'Gemeinde', write: true, direkt: true, stufen: [],
    pruefstufen: ['gemeinde'], gruppe: null, untergruppe: null,
}
const FREMD = {
    name: 'jugendkal', title: 'Jugend', write: false, direkt: false, stufen: [],
    pruefstufen: [], gruppe: 'jugend', untergruppe: null,
}
const ALLE = [CHOR, SOPRAN, SOPRAN_OEFFENTLICH, GEMEINDE, FREMD]

test('Gruppenseite: nur der Kalender DIESER Gruppe, nicht der Untergruppe', () => {
    const namen = kalenderDerGruppe(ALLE, { gruppenId: 'chor' }).map((c) => c.name)
    assert.deepEqual(namen, ['chorkal'])
})

test('Untergruppenseite: Kalender der Untergruppe UND der Hauptgruppe', () => {
    const lage = { gruppenId: 'sopran', hauptgruppe: 'chor', istUntergruppe: true }
    const namen = kalenderDerGruppe(ALLE, lage).map((c) => c.name)
    assert.deepEqual(namen, ['chorkal', 'sopran-kal', 'sopran-offen'])
})

test('Gemeinde-Kalender erscheint NICHT auf der Gruppenseite (auch mit Schreibrecht)', () => {
    assert.ok(!kalenderDerGruppe(ALLE, { gruppenId: 'chor' }).some((c) => c.name === 'gemeinde-kal'))
})

test('ohne Schreibrecht kein Eintrag (die Oberfläche bietet nichts an, was der Server verweigert)', () => {
    assert.ok(!kalenderDerGruppe(ALLE, { gruppenId: 'jugend' }).some((c) => c.name === 'jugendkal'))
    assert.equal(kalenderDerGruppe(ALLE, { gruppenId: 'jugend' }).length, 0)
})

test('Knopf nur bei mindestens einem beschreibbaren Kalender der Gruppe', () => {
    // Review 6: Die Knopf-Bedingung der Seite IST „kalenderDerGruppe liefert
    // etwas“ — die frühere zweite Funktion (`darfTerminAnbieten`) war getestet,
    // aber unbenutzt. Hier steht die Regel selbst, ohne Doppelquelle.
    assert.equal(kalenderDerGruppe(ALLE, { gruppenId: 'chor' }).length > 0, true)
    assert.equal(kalenderDerGruppe(ALLE, { gruppenId: 'unbekannt' }).length > 0, false)
    assert.equal(kalenderDerGruppe([], { gruppenId: 'chor' }).length > 0, false)
    assert.equal(kalenderDerGruppe(null, { gruppenId: 'chor' }).length, 0)
})

test('fehlende Kennung: keine Zuordnung (fail closed)', () => {
    assert.deepEqual(kalenderDerGruppe(ALLE, {}), [])
    assert.deepEqual(kalenderDerGruppe(ALLE, { gruppenId: '' }), [])
})

test('ein alter Server ohne `untergruppe`-Feld zählt als Kalender der Gruppe', () => {
    const alt = [{ name: 'chorkal', title: 'Chor', write: true, gruppe: 'chor' }]
    assert.deepEqual(kalenderDerGruppe(alt, { gruppenId: 'chor' }).map((c) => c.name), ['chorkal'])
})

test('ein Kalender → vorbelegt; mehrere → offen (Diakronos fragt)', () => {
    assert.equal(vorbelegterKalender(kalenderDerGruppe(ALLE, { gruppenId: 'chor' })), 'chorkal')
    const lage = { gruppenId: 'sopran', hauptgruppe: 'chor', istUntergruppe: true }
    assert.equal(vorbelegterKalender(kalenderDerGruppe(ALLE, lage)), '')
    assert.equal(vorbelegterKalender([]), '')
})

test('Prüfhinweis genau bei `direkt === false`', () => {
    // Review 1 (HOCH): Vorher hieß die Regel `direkt !== true` — ein Kalender
    // OHNE das Feld (Kalenderseite) bekam den Hinweis, auch für HV und Admin.
    assert.equal(wirdGeprueft(CHOR), false)
    assert.equal(wirdGeprueft(SOPRAN_OEFFENTLICH), true)
    assert.equal(wirdGeprueft({ name: 'x', write: true }), false)
    assert.equal(wirdGeprueft(null), false)
    assert.equal(PRUEFHINWEIS, 'Der Termin wird vor der Veröffentlichung geprüft.')
})

test('HV/Admin: `direkt: true` heißt KEIN Prüfhinweis', () => {
    // Positiv-Kontrolle: derselbe Kalender mit direkt=false prüft.
    assert.equal(wirdGeprueft({ ...CHOR }), false)
    const direkt = { name: 'chorkal', title: 'Chor', write: true, direkt: true, gruppe: 'chor', untergruppe: null }
    assert.equal(wirdGeprueft(direkt), false)
    // Negativ-Kontrolle: nur die Umkehrung des Feldes kippt die Aussage.
    assert.equal(wirdGeprueft({ ...direkt, direkt: false }), true)
})

test('unbekanntes `direkt` behauptet NICHTS (kein falscher Hinweis)', () => {
    assert.equal(wirdGeprueft({ name: 'x', write: true, direkt: undefined }), false)
    assert.equal(wirdGeprueft({ name: 'x', write: true, direkt: 'false' }), false)
})

test('Auswahlliste: nur die übergebenen Kalender, in Serverreihenfolge, keine Doppelten', () => {
  const gruppe = kalenderDerGruppe(ALLE, { gruppenId: 'chor' })
  // Punkt 3: EIN Argument — das zweite war wirkungslos (die Kalender kommen
  // schon gefiltert an), und der Kommentar „danach die übrigen“ war falsch.
  assert.deepEqual(kalenderOptionen(gruppe).map((o) => o.value), ['chorkal'])
  assert.deepEqual(kalenderOptionen(gruppe)[0], { value: 'chorkal', label: 'Chor' })
  // Untergruppe: alle drei Kalender dieser Seite, Gemeinde bleibt draußen.
  const lage = { gruppenId: 'sopran', hauptgruppe: 'chor', istUntergruppe: true }
  assert.deepEqual(kalenderOptionen(kalenderDerGruppe(ALLE, lage)).map((o) => o.value),
    ['chorkal', 'sopran-kal', 'sopran-offen'])
  // Doppelter Name = Fehler des Servers, kein zweiter Eintrag.
  assert.deepEqual(kalenderOptionen([CHOR, { ...CHOR, title: 'Chor (doppelt)' }]).map((o) => o.value),
    ['chorkal'])
  assert.deepEqual(kalenderOptionen(null), [])
  assert.deepEqual(kalenderOptionen([]), [])
  // Ein alter Eintrag ohne `title` bleibt lesbar (`calendar_name`, sonst Name).
  assert.deepEqual(kalenderOptionen([{ name: 'x', calendar_name: 'X-Kalender' }]),
    [{ value: 'x', label: 'X-Kalender' }])
})

test('Direktschreiber schickt „Festgelegt“, sonst KEIN status', () => {
  // Punkt 1: Der Server legt ohne `status` immer nur einen Vorschlag an
  // (BF1-A) und verwirft „Festgelegt“ von Nicht-Direktschreibern.
  assert.equal(statusFuerKalender(CHOR), 'Festgelegt')
  assert.equal(statusFuerKalender({ name: 'x', write: true, direkt: true }), 'Festgelegt')
  assert.equal(STATUS_DIREKT, 'Festgelegt')
  // Geprüfter Kalender, fehlendes Feld, kein Kalender → nichts behaupten.
  assert.equal(statusFuerKalender(SOPRAN_OEFFENTLICH), '')
  assert.equal(statusFuerKalender({ name: 'x', write: true }), '')
  assert.equal(statusFuerKalender({ name: 'x', write: true, direkt: 'true' }), '')
  assert.equal(statusFuerKalender(null), '')
  assert.equal(statusFuerKalender(undefined), '')
  // Genau die Umkehrung von `wirdGeprueft`: nie beides zugleich.
  for (const k of [CHOR, SOPRAN_OEFFENTLICH, { name: 'y', write: true }, null]) {
    assert.ok(!(statusFuerKalender(k) && wirdGeprueft(k)),
      `Kalender ${JSON.stringify(k)} meldet gleichzeitig direkt und geprüft`)
  }
})

test('Formularzeitraum: Beginn UND Ende (DEV-5), Ortszeit, ohne Zeitzonen-Anhang', () => {
    // Review 2 (MITTEL): Früher kam nur der Beginn (aktuelle Minute) — der
    // DEV-5-Vorschlag griff nicht und der Termin hatte keine Dauer.
    // 2026-12-01T18:05:00Z ist in Berlin 19:05 (Winterzeit) → nächste volle
    // Stunde 20:00, Ende 21:00 am selben Tag.
    const zeitraum = formularZeitraum(new Date('2026-12-01T18:05:00Z'))
    assert.equal(zeitraum.element_start, '2026-12-01T20:00')
    assert.equal(zeitraum.element_end, '2026-12-01T21:00')
    // Der Server lehnt Werte mit Anhang ab (`parse_iso_datetime_raw`).
    assert.doesNotMatch(zeitraum.element_start, /Z|[+-]\d{2}:?$/)
    assert.doesNotMatch(zeitraum.element_end, /Z|[+-]\d{2}:?$/)
    // Genau zur vollen Stunde bleibt es bei dieser Stunde (nicht eine weiter).
    assert.deepEqual(formularZeitraum(new Date('2026-12-01T19:00:00Z')),
        { element_start: '2026-12-01T20:00', element_end: '2026-12-01T21:00' })
})

test('Formularzeitraum über Mitternacht: Ende liegt am Folgetag', () => {
    // 2026-12-01T22:30Z = 23:30 Ortszeit → Beginn 00:00 des Folgetags.
    const zeitraum = formularZeitraum(new Date('2026-12-01T22:30:00Z'))
    assert.equal(zeitraum.element_start, '2026-12-02T00:00')
    assert.equal(zeitraum.element_end, '2026-12-02T01:00')
})

test('Formularzeitraum: Sommerzeit wird berücksichtigt', () => {
    // 2026-07-01T18:05Z = 20:05 Ortszeit → Beginn 21:00, Ende 22:00.
    const zeitraum = formularZeitraum(new Date('2026-07-01T18:05:00Z'))
    assert.deepEqual(zeitraum, { element_start: '2026-07-01T21:00', element_end: '2026-07-01T22:00' })
})

test('Formularzeitraum: EINE Quelle (DEV-5-Regel aus vorschlagZeitraum)', () => {
    // Punkt 4: Die Regel stand hier als zweite Fassung von `vorschlagZeitraum`
    // (datumZeit.mjs) und konnte davon abweichen. Belegt wird die
    // Wiederverwendung: dieselbe Antwort für denselben Ortszeitpunkt, und die
    // Ortszeit-Mitternacht (23:30 Ortszeit) ist der Folgetag — ohne
    // Sonderzweig in gruppenTermin.mjs.
    const quelle = lies('../src/diakonos/components/gruppen/gruppenTermin.mjs')
    assert.match(quelle, /import \{ vorschlagZeitraum \} from '\.\.\/\.\.\/composables\/datumZeit\.mjs'/)
    // Keine eigene Rundung/Tageswechsel-Rechnung mehr im Modul.
    assert.ok(!/rohStunde|ueberMitternacht|beginnStunde/.test(quelle),
        'DEV-5-Regel wird im Modul nachgebaut')

    const jetzt = new Date('2026-12-01T18:05:00Z') // 19:05 Ortszeit
    const teile = ortszeitTeile(jetzt)
    const v = vorschlagZeitraum(new Date(`${teile.datum}T${teile.uhrzeit}:00`))
    assert.deepEqual(formularZeitraum(jetzt), {
        element_start: `${v.datum}T${v.beginn}`,
        element_end: `${v.endeDatum}T${v.ende}`,
    })

    // Mitternacht in Ortszeit (hier 22:30Z = 23:30 Ortszeit) → Beginn Folgetag
    // 00:00, Ende 01:00 — genau die Regel der Quelle, ohne Zeitzonen-Anhang.
    const mitternacht = formularZeitraum(new Date('2026-12-01T22:30:00Z'))
    assert.deepEqual(mitternacht, { element_start: '2026-12-02T00:00', element_end: '2026-12-02T01:00' })
    assert.doesNotMatch(mitternacht.element_start, /Z|[+-]\d{2}:?\d{0,2}$/)
})

test('Meldung nach dem Speichern: Vorschlag nennt die offene Stufe', () => {
    // Review 3: statt „(Vorschlag)“ steht die Stufe, auf die gewartet wird.
    const titel = { gruppe: 'Gruppe', gemeinde: 'Alle Mitglieder der Gemeinde' }
    const gruppe = meldungNachSpeichern({ status: 'Vorschlag', naechste_stufe: 'gruppe' }, titel)
    assert.equal(gruppe.text, 'Termin gespeichert — wartet auf Gruppe.')
    assert.equal(gruppe.variante, 'info')
    const gemeinde = meldungNachSpeichern({ status: 'Vorschlag', naechste_stufe: 'gemeinde' }, titel)
    assert.equal(gemeinde.text, 'Termin gespeichert — wartet auf Alle Mitglieder der Gemeinde.')
    // Ohne `naechste_stufe` keine erfundene Stufe, aber ehrlich „wird geprüft“.
    const ohne = meldungNachSpeichern({ status: 'Vorschlag' }, titel)
    assert.equal(ohne.text, 'Termin gespeichert — wird zum Prüfen vorgelegt.')
})

test('Meldung nach dem Speichern: `Festgelegt` meldet Erfolg ohne Prüfstufe', () => {
    const ok = meldungNachSpeichern({ status: 'Festgelegt' }, {})
    assert.equal(ok.text, 'Termin gespeichert.')
    assert.equal(ok.variante, 'success')
    // `offen`/`naechste_stufe` sind bei Festgelegt leer — die Meldung erfindet nichts.
    assert.doesNotMatch(ok.text, /wartet/)
})

test('Meldung nach dem Speichern: Serie nimmt `status` der Antwort, keine Pauschale', () => {
    // Review 3: Serien meldeten pauschal „(Vorschlag)“, auch wenn sie sofort galten.
    const sofort = meldungNachSpeichern({ status: 'Festgelegt', created_count: 12 }, {})
    assert.equal(sofort.text, 'Termin gespeichert (12 Termine).')
    assert.equal(sofort.variante, 'success')
    const vorgeschlagen = meldungNachSpeichern(
        { status: 'Vorschlag', created_count: 8, naechste_stufe: 'untergruppe' },
        { untergruppe: 'Untergruppe' })
    assert.equal(vorgeschlagen.text, 'Termin gespeichert (8 Termine) — wartet auf Untergruppe.')
})

test('Meldung nach dem Speichern: leerer/alter Antwortkörper behauptet nichts', () => {
    assert.equal(meldungNachSpeichern(null, {}).text, 'Termin gespeichert.')
    assert.equal(meldungNachSpeichern({}, {}).text, 'Termin gespeichert.')
    // Nur EIN angelegter Termin wird nicht als Serie ausgewiesen.
    assert.equal(meldungNachSpeichern({ status: 'Festgelegt', created_count: 1 }, {}).text,
        'Termin gespeichert.')
})

test('Stufentitel: Servertext gewinnt, sonst bleibt die Stufe lesbar', () => {
    assert.equal(stufenName('gruppe', { gruppe: 'Gruppe' }), 'Gruppe')
    // Fehlt der Servertext, wird KEINE Bezeichnung erfunden.
    assert.equal(stufenName('gemeinde', {}), 'gemeinde')
    assert.equal(stufenName('', { gruppe: 'Gruppe' }), '')
    assert.equal(stufenName(null), '')
})

test('Ortszeit-Teile liefern Datum und Uhrzeit zweistellig', () => {
    const teile = ortszeitTeile(new Date('2026-01-05T07:03:00Z'))
    assert.deepEqual(teile, { datum: '2026-01-05', uhrzeit: '08:03' })
})
