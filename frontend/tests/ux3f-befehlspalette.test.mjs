/**
 * UX3f — Befehlspalette (Strg+K): Regeln, Markup und Verkabelung.
 *
 * Der Test läuft OHNE Browser (node --test, im Docker-Frontend-Build) und
 * deckt drei Ebenen ab:
 *
 *   1. Die Regeln in `composables/befehlspalette.mjs` (Abschnitte, Tastatur,
 *      Verlauf, Einsortieren der Server-Treffer, Auswahl, Leerzustand).
 *   2. Das Markup der Palette und ihre Verkabelung in App.vue/AppTopbar.vue —
 *      inklusive der beiden Anlege-Wege (`?neu=1`, `?anlegen=1`), die sonst zu
 *      toten Knöpfen würden (die Palette öffnet eine Seite, die den Dialog
 *      nicht kennt).
 *   3. Die Design-Regeln der Karte: nur Tokens (keine festen Farben), nur
 *      Abstände/Fonts aus den Tokens, Klickflächen ≥ --control-h, Strg+K am
 *      Suchfeld der Kopfzeile, Esc schließt.
 *
 * Die beiden Fehler, die der Wegwerf-Stack gezeigt hat (POST auf einen
 * GET-Endpunkt → 405; leere Abschnittsüberschrift „TERMINE" über der
 * Fußzeile), sind hier als eigene Fälle festgehalten.
 *
 * Er liest ausschließlich Dateien INNERHALB von frontend/ (Regel 13: keine
 * zusätzliche COPY-Zeile im Image nötig).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  ABSCHNITTE, KUERZEL, MIN_ZEICHEN, VERLAUF_MAX, VERLAUF_SCHLUESSEL,
  aktionsEintraege, darfKuerzelGreifen, gesuchteArten, istLeer, istOeffnenTaste,
  naechsteAuswahl, paletteZeilen, passtZu, richtungstaste, seitenEintraege,
  trefferEinsortieren, verlaufLesen, verlaufNachWahl, verlaufSchreiben,
  verlaufSchluessel as verlaufFuerNutzer,
  verlaufFuerNutzerAufraeumen as verlaufFuerAufraeumen,
} from '../src/diakonos/composables/befehlspalette.mjs'
import { SYMBOLE } from '../src/diakonos/components/ui/symbole.mjs'
import { MENUE, FUSS_EINTRAEGE, sichtbareEintraege } from '../src/diakonos/menue.js'

const hier = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(resolve(hier, '..', rel), 'utf8')

const paletteQuelle = lies('src/diakonos/components/Befehlspalette.vue')
const appQuelle = lies('src/diakonos/App.vue')
const topbarQuelle = lies('src/diakonos/components/AppTopbar.vue')
const regelQuelle = lies('src/diakonos/composables/befehlspalette.mjs')
const indexCss = lies('src/diakonos/index.css')
const kalenderQuelle = lies('src/diakonos/pages/Kalender.vue')
const personenQuelle = lies('src/diakonos/pages/Personen.vue')

const rechteAdmin = { istAdmin: true, istTester: false, istGast: false, rollen: ['System Manager'] }
const rechteMitglied = { istAdmin: false, istTester: false, istGast: false, rollen: ['All'] }

/**
 * Speicher-Attrappe mit der vollen localStorage-Oberfläche (`length`, `key`,
 * `getItem`, `setItem`, `removeItem`). `verlaufFuerNutzerAufraeumen` läuft über
 * die Schlüsselliste — ein einfaches Map-Objekt reicht dafür nicht.
 */
function fakeSpeicher() {
  const daten = new Map()
  return {
    get length() { return daten.size },
    key: (i) => (i >= 0 && i < daten.size ? [...daten.keys()][i] : null),
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => { daten.set(String(k), String(v)) },
    removeItem: (k) => { daten.delete(k) },
  }
}

// ── 1. Abschnitte (Entwurf A5) ───────────────────────────────────────────────

test('A5: die Abschnitte und ihre Reihenfolge stehen fest', () => {
  assert.deepEqual(
    ABSCHNITTE.map(a => a.id),
    ['zuletzt', 'seiten', 'person', 'gruppe', 'termin', 'lied', 'aktion'],
  )
  assert.deepEqual(
    ABSCHNITTE.map(a => a.label),
    ['Zuletzt verwendet', 'Seiten', 'Personen', 'Gruppen', 'Termine', 'Lieder', 'Aktionen'],
  )
  // Jeder Abschnitt hat ein Symbol aus dem VORHANDENEN Vorrat — ein fehlender
  // Name zeichnet nichts (DkSymbol).
  for (const [abschnitt, symbol] of Object.entries({
    zuletzt: 'erneut', seiten: 'notiz', person: 'gruppe', gruppe: 'rolle',
    termin: 'kalender', lied: 'nachricht', aktion: 'hinzufuegen',
  })) {
    assert.ok(SYMBOLE[symbol], `${abschnitt}: Symbol „${symbol}“ fehlt im Vorrat`)
  }
})

// ── 2. Tastatur ──────────────────────────────────────────────────────────────

test('Strg+K und ⌘+K öffnen — Enter-Taste nicht', () => {
  assert.equal(istOeffnenTaste({ key: 'k', ctrlKey: true }), true)
  assert.equal(istOeffnenTaste({ key: 'K', ctrlKey: true, shiftKey: true }), true)
  assert.equal(istOeffnenTaste({ key: 'k', metaKey: true }), true, 'Mac: ⌘+K')
  assert.equal(istOeffnenTaste({ key: 'k' }), false, 'ohne Zusatztaste kein Kürzel')
  assert.equal(istOeffnenTaste({ key: 'x', ctrlKey: true }), false)
  assert.equal(istOeffnenTaste({ key: 'k', ctrlKey: true, repeat: true }), false,
    'gehaltene Taste darf nicht mehrfach umschalten')
  // Auf einer Tastatur mit anderer Belegung liefert `key` ein anderes Zeichen,
  // `code` bleibt „KeyK“.
  assert.equal(istOeffnenTaste({ key: 'κ', code: 'KeyK', ctrlKey: true }), true)
})

test('in Eingabefeldern greift das Kürzel nicht (dort gehört es dem Feld)', () => {
  assert.equal(darfKuerzelGreifen({ tagName: 'INPUT' }), false)
  assert.equal(darfKuerzelGreifen({ tagName: 'textarea' }), false)
  assert.equal(darfKuerzelGreifen({ tagName: 'SELECT' }), false)
  assert.equal(darfKuerzelGreifen({ tagName: 'DIV', isContentEditable: true }), false)
  assert.equal(darfKuerzelGreifen({ tagName: 'DIV' }), true)
  assert.equal(darfKuerzelGreifen(null), true)
})

test('↑ ↓ bewegen die Auswahl im Ring, ohne Auswahl beginnt ↓ oben und ↑ unten', () => {
  assert.equal(richtungstaste({ key: 'ArrowDown' }), 1)
  assert.equal(richtungstaste({ key: 'ArrowUp' }), -1)
  assert.equal(richtungstaste({ key: 'Enter' }), 0)
  assert.equal(naechsteAuswahl(-1, 3, 1), 0)
  assert.equal(naechsteAuswahl(-1, 3, -1), 2)
  assert.equal(naechsteAuswahl(0, 3, 1), 1)
  assert.equal(naechsteAuswahl(2, 3, 1), 0, 'unter dem letzten Treffer kommt der erste')
  assert.equal(naechsteAuswahl(0, 3, -1), 2, 'über dem ersten der letzte')
  assert.equal(naechsteAuswahl(0, 0, 1), -1, 'leere Liste bleibt ohne Auswahl')
  assert.equal(naechsteAuswahl(7, 3, 1), 0, 'veralteter Index beginnt wieder oben')
})

// ── 3. Seiten und Aktionen ───────────────────────────────────────────────────

test('Seiten kommen aus der Menüdefinition und ehren die Rollen', () => {
  const alle = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: rechteAdmin })
  const titel = alle.map(e => e.titel)
  for (const pflicht of ['Übersicht', 'Personen', 'Gruppen', 'Kalender', 'Dienste', 'Ressourcen',
    'Beiträge', 'Wiki', 'Lieder', 'Website', 'Einstellungen']) {
    assert.ok(titel.includes(pflicht), `Seite „${pflicht}“ fehlt in der Palette`)
  }
  // Ort = Menügruppe (N7: Treffer zeigen ihren Ort).
  const personen = alle.find(e => e.titel === 'Personen')
  assert.equal(personen.ort, 'Gemeinde')
  assert.equal(personen.ziel, '#/personen')
  assert.equal(alle.find(e => e.titel === 'Einstellungen').ort, 'Verwaltung')

  // Ohne Verwaltungsrecht: „Einstellungen“ und „Website“ fehlen (dieselbe
  // Regel wie die Seitenleiste — fail closed).
  const ohne = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: rechteMitglied })
  const titelOhne = ohne.map(e => e.titel)
  assert.ok(!titelOhne.includes('Einstellungen'), 'Einstellungen gehört nicht in die Palette eines Mitglieds')
  assert.ok(!titelOhne.includes('Website'), 'Website ist rollengeschützt')
})

test('nur Einträge mit `suche: true` erscheinen — und die tragen ein Ziel', () => {
  const alle = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: rechteAdmin })
  for (const e of alle) {
    assert.ok(e.ziel.startsWith('#/'), `${e.titel}: Ziel „${e.ziel}“ ist keine Adresse`)
    assert.ok(e.id.startsWith('seite:'), `${e.titel}: Kennung ohne Abschnitts-Präfix`)
  }
})

test('Aktionen erscheinen nur bei Recht', () => {
  assert.deepEqual(aktionsEintraege({ darfTermin: false, darfPerson: false }), [])
  const nurPerson = aktionsEintraege({ darfPerson: true })
  assert.deepEqual(nurPerson.map(a => a.titel), ['Person anlegen'])
  assert.equal(nurPerson[0].ziel, '#/personen?anlegen=1')
  const beide = aktionsEintraege({ darfTermin: true, darfPerson: true })
  assert.deepEqual(beide.map(a => a.titel), ['Termin anlegen', 'Person anlegen'])
  assert.equal(beide[0].ziel, '#/kalender?neu=1')
  assert.equal(beide[0].ort, 'Aktion')
})

test('beide Anlege-Aktionen haben ein Ziel, das den Dialog wirklich öffnet', () => {
  // Ohne diesen Griff wäre „Termin anlegen“ ein Knopf, der nur eine Seite
  // zeigt — der tote Knopf, den die Karte verbietet.
  assert.match(kalenderQuelle, /werte\.get\('neu'\)/, 'Kalender.vue liest den Schalter `neu` nicht')
  assert.match(kalenderQuelle, /showCreate\.value = true/, 'Kalender.vue öffnet den Anlege-Dialog nicht')
  assert.match(kalenderQuelle, /history\.replaceState/, 'Kalender.vue räumt den Schalter nicht aus der Adresse')
  assert.match(personenQuelle, /werte\.get\('anlegen'\)/, 'Personen.vue liest den Schalter `anlegen` nicht')
  assert.match(personenQuelle, /personAnlegen\(\)/, 'Personen.vue öffnet das Anlege-Formular nicht')
  assert.match(personenQuelle, /history\.replaceState/, 'Personen.vue räumt den Schalter nicht aus der Adresse')
  // Beide prüfen das Recht — ohne Recht bleibt es beim Seitenwechsel.
  assert.match(kalenderQuelle, /if \(hasWriteRight\.value\)/)
  assert.match(personenQuelle, /if \(!istAdmin\.value\) return/)
})

// ── 4. Zuletzt verwendet ─────────────────────────────────────────────────────

test('Verlauf: lesen und schreiben sind abgesichert (privater Modus, Müll)', () => {
  const kaputt = { getItem: () => '{kein json', setItem: () => {} }
  assert.deepEqual(verlaufLesen(kaputt), [])

  const werfend = { getItem: () => { throw new Error('gesperrt') }, setItem: () => { throw new Error('gesperrt') } }
  assert.deepEqual(verlaufLesen(werfend), [])
  assert.doesNotThrow(() => verlaufSchreiben(werfend, [{ id: 'a', titel: 'A', ziel: '#/personen' }]))

  const speicher = new Map()
  const fake = {
    getItem: (k) => (speicher.has(k) ? speicher.get(k) : null),
    setItem: (k, v) => speicher.set(k, v),
  }
  verlaufSchreiben(fake, [
    { id: 'a', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' },
    { id: 'b', titel: 'Kalender', ziel: '#/kalender', ort: 'Planen' },
  ])
  assert.equal(speicher.get(VERLAUF_SCHLUESSEL), JSON.stringify([
    { id: 'a', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' },
    { id: 'b', titel: 'Kalender', ziel: '#/kalender', ort: 'Planen' },
  ]))
  assert.equal(verlaufLesen(fake).length, 2)

  // Fremde/kaputte Einträge werden verworfen, nicht angezeigt.
  verlaufSchreiben(fake, [
    { id: 'x', titel: 'Ohne Ziel' },
    { id: 'y', titel: 'Falsch', ziel: 'http://extern' },
    'quatsch',
  ])
  assert.deepEqual(verlaufLesen(fake), [])
})

test('Verlauf: die letzte Wahl steht vorn, gleiche Ziele bleiben einmal', () => {
  const start = [
    { id: 'a', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' },
    { id: 'b', titel: 'Kalender', ziel: '#/kalender', ort: 'Planen' },
  ]
  const neu = verlaufNachWahl(start, { id: 'c', titel: 'Einstellungen', ziel: '#/einstellungen', ort: 'Verwaltung' })
  assert.deepEqual(neu.map(e => e.ziel), ['#/einstellungen', '#/personen', '#/kalender'])
  const nochmal = verlaufNachWahl(neu, { id: 'a2', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' })
  assert.deepEqual(nochmal.map(e => e.ziel), ['#/personen', '#/einstellungen', '#/kalender'])
  assert.equal(nochmal.filter(e => e.ziel === '#/personen').length, 1)
  // Deckel: höchstens VERLAUF_MAX Einträge.
  let lang = []
  for (let i = 0; i < 9; i++) lang = verlaufNachWahl(lang, { id: 'i' + i, titel: 'T' + i, ziel: '#/x' + i })
  assert.equal(lang.length, VERLAUF_MAX)
})

// ── 5. Server-Treffer einsortieren ───────────────────────────────────────────

test('Server-Treffer landen im richtigen Abschnitt, Unbekanntes fällt weg', () => {
  const roh = [
    { art: 'person', titel: 'Miriam Seifert', ort: 'Person · Chor', ziel: '#/mitglied/M-001' },
    { art: 'gruppe', titel: 'Mitarbeiterkreis', ort: 'Gruppe', ziel: '#/gruppe/G-1' },
    { art: 'termin', titel: 'Dienstplan November', ort: 'Termin', ziel: '#/kalender?termin=E-1' },
    { art: 'lied', titel: 'Großer Gott', ort: 'Lied', ziel: '#/lieder/L-1' },
    { art: 'wiki', titel: 'Wer darf was?', ort: 'Wiki', ziel: '#/wiki/W-1' },
    { art: 'beitrag', titel: 'Grußwort', ort: 'Beiträge', ziel: '#/beitraege?id=B-1' },
    { art: 'einstellung', titel: 'Gemeinde', ort: 'Einstellungen', ziel: '#/einstellungen/gemeinde' },
    { art: 'unbekannt', titel: 'Nichts', ort: '', ziel: '#/irgendwas' },
    { art: 'person', titel: 'Kaputt', ort: '', ziel: 'http://extern' },
  ]
  const zeilen = trefferEinsortieren(roh)
  assert.deepEqual(zeilen.map(z => z.abschnitt), [
    'person', 'gruppe', 'termin', 'lied', 'seiten', 'seiten', 'seiten',
  ])
  assert.equal(zeilen[0].ort, 'Person · Chor', 'der Ort des Servers bleibt erhalten')
  assert.equal(zeilen.length, 7, 'unbekannte Art und fremdes Ziel fallen weg')
})

test('BEFUND Stack: kein leerer Abschnitt — nur Arten aus `quellen` (Wegwerf-Stack)', () => {
  // Im Wegwerf-Stack stand eine leere Überschrift „TERMINE“ über der Fußzeile,
  // weil der Server für diesen Begriff nur Seiten und Personen gefunden hatte.
  // `quellen` aus `suche.global` nennt die Arten, für die er WIRKLICH gesucht
  // hat: die Palette baut nur daraus Abschnitte.
  const antwort = {
    q: 'be',
    treffer: [
      { art: 'person', titel: 'Benjamin Adler', ort: 'Person', ziel: '#/mitglied/M-1' },
    ],
    quellen: { person: 1, gruppe: 0, termin: 0, lied: 0, wiki: 2, beitrag: 3, einstellung: 0 },
  }
  const arten = gesuchteArten(antwort)
  const zeilen = trefferEinsortieren(antwort.treffer, { gefragt: true, quellen: Object.fromEntries([...arten].map(a => [a, true])) })
  assert.ok(!zeilen.some(z => z.abschnitt === 'termin'), 'leerer Abschnitt „Termine“ steht im Bild')
  const { gruppen } = paletteZeilen({ begriff: 'be', seiten: [], aktionen: [], treffer: zeilen })
  assert.deepEqual(gruppen.map(g => g.id), ['person'])

  // Fehlt `quellen` (alte Antwort), bleibt es beim bisherigen Verhalten.
  assert.equal(gesuchteArten({ treffer: [] }), null)
  assert.equal(gesuchteArten(null), null)

  // Widerspruch in der Antwort: Zähler > 0, aber kein Treffer (eine Quelle
  // fiel im Server aus). Dann darf KEINE leere Überschrift stehenbleiben.
  const widerspruch = trefferEinsortieren(
    [{ art: 'person', titel: 'Benjamin Adler', ort: 'Person', ziel: '#/mitglied/M-1' }],
    { quellen: { person: 1, termin: 5 } },
  )
  assert.deepEqual(widerspruch.map(z => z.abschnitt), ['person'],
    'Abschnitt „Termine“ mit Zähler 5, aber ohne Treffer — leere Überschrift')
  // Ein Treffer einer Art, für die der Server NICHT gesucht hat, fällt weg
  // (zweite Absicherung gegen „Einstellungen“ ohne Recht).
  const gefiltert = trefferEinsortieren(
    [{ art: 'einstellung', titel: 'Gemeinde', ort: 'Einstellungen', ziel: '#/einstellungen/gemeinde' }],
    { quellen: { person: true } },
  )
  assert.deepEqual(gefiltert, [])
})

// ── 6. Gesamtliste ───────────────────────────────────────────────────────────

const seitenProbe = seitenEintraege({ menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: rechteAdmin })

test('leere Eingabe: Zuletzt verwendet, Seiten, Aktionen — keine Server-Treffer', () => {
  const { zeilen, gruppen } = paletteZeilen({
    begriff: '',
    verlauf: [{ id: 'a', titel: 'Michaela Sommer', ziel: '#/mitglied/M-9', ort: 'Person · Chor' }],
    seiten: seitenProbe,
    aktionen: aktionsEintraege({ darfTermin: true, darfPerson: true }),
    treffer: [{ art: 'person', titel: 'Alt', ort: '', ziel: '#/mitglied/M-1' }],
  })
  assert.deepEqual(gruppen.map(g => g.id), ['zuletzt', 'seiten', 'aktion'])
  assert.equal(gruppen[0].zeilen[0].titel, 'Michaela Sommer')
  // Positionen laufen über ALLE Abschnitte (nicht je Abschnitt).
  assert.deepEqual(zeilen.map(z => z.position), zeilen.map((_, i) => i))
})

test('mit Eingabe: Seiten werden lokal gefiltert, Verlauf verschwindet', () => {
  const ohneServer = paletteZeilen({ begriff: 'pers', seiten: seitenProbe, aktionen: [] })
  assert.deepEqual(ohneServer.zeilen.map(z => z.titel), ['Personen'])

  const mitServer = paletteZeilen({
    begriff: 'mie',
    seiten: seitenProbe,
    aktionen: [],
    treffer: trefferEinsortieren([
      { art: 'person', titel: 'Michaela Sommer', ort: 'Person · Chor', ziel: '#/mitglied/M-1' },
    ]),
  })
  assert.deepEqual(mitServer.gruppen.map(g => g.id), ['person'])
  assert.equal(mitServer.zeilen[0].titel, 'Michaela Sommer')
})

test('„Einstellungen“ erscheint nicht doppelt (Menü gewinnt gegen Server-Treffer)', () => {
  const { zeilen } = paletteZeilen({
    begriff: 'ein',
    seiten: seitenProbe,
    aktionen: [],
    treffer: trefferEinsortieren([
      { art: 'einstellung', titel: 'Einstellungen', ort: 'Einstellungen', ziel: '#/einstellungen' },
      { art: 'einstellung', titel: 'Gemeinde', ort: 'Einstellungen', ziel: '#/einstellungen/gemeinde' },
    ]),
  })
  const seitenZeilen = zeilen.filter(z => z.abschnitt === 'seiten')
  assert.equal(seitenZeilen.filter(z => z.ziel === '#/einstellungen').length, 1)
  assert.ok(seitenZeilen.some(z => z.ziel === '#/einstellungen/gemeinde'))
})

test('Leerzustand nur nach einer echten Antwort des Servers', () => {
  // Noch keine Antwort für diesen Begriff → nicht behaupten, es sei leer.
  assert.equal(istLeer({ begriff: 'zzz', zeilen: [], trefferGefragt: false }), false)
  assert.equal(istLeer({ begriff: 'zzz', zeilen: [], trefferGefragt: true }), true)
  // Mit lokal gefundener Seite nie „nichts gefunden“.
  assert.equal(istLeer({ begriff: 'pers', zeilen: [{ id: 'x' }], trefferGefragt: true }), false)
  // Ohne Eingabe ist der Startzustand kein Leerzustand.
  assert.equal(istLeer({ begriff: '', zeilen: [], trefferGefragt: true }), false)
})

test('Textvergleich findet Wortanfänge und Wortteile, Umlaute egal', () => {
  assert.equal(passtZu('per', 'Personen'), true)
  assert.equal(passtZu('EIN', 'Einstellungen'), true)
  assert.equal(passtZu('glied', 'Gruppenmitglieder'), true)
  assert.equal(passtZu('ue', 'Übersicht'), true, 'ue findet Ü')
  assert.equal(passtZu('weiss', 'Weiß'), true)
  assert.equal(passtZu('xyz', 'Personen'), false)
  assert.equal(passtZu('', 'irgendwas'), true, 'leere Eingabe passt auf alles')
})

// ── 7. Markup und Verkabelung ────────────────────────────────────────────────

test('Palette: Rolle, Tastatur, Zustände und Tastenhinweise stehen im Markup', () => {
  assert.match(paletteQuelle, /role="dialog"/, 'die Palette ist kein Dialog')
  assert.match(paletteQuelle, /aria-modal="true"/)
  assert.match(paletteQuelle, /role="combobox"/, 'das Suchfeld ist keine Combobox (Vorlesehilfe)')
  assert.match(paletteQuelle, /aria-activedescendant/, 'die Auswahl wird nicht angesagt')
  assert.match(paletteQuelle, /role="listbox"/)
  assert.match(paletteQuelle, /role="option"/)
  for (const taste of ['ArrowDown', 'ArrowUp', 'Escape', 'Enter']) {
    assert.ok(regelQuelle.includes(`'${taste}'`) || paletteQuelle.includes(`'${taste}'`),
      `Taste ${taste} wird nicht behandelt`)
  }
  // Die drei Zustände: Ladeanzeige, Fehler mit „Erneut versuchen“, Leerzustand.
  assert.match(paletteQuelle, /DkSpinner/, 'kein Ladezustand')
  assert.match(paletteQuelle, /Erneut versuchen/, 'kein „Erneut versuchen“ im Fehlerzustand')
  assert.match(paletteQuelle, /dk-palette-leer/, 'kein Leerzustand')
  // Fußzeile des Entwurfs.
  for (const wort of ['wählen', 'öffnen', 'schließen']) {
    assert.ok(paletteQuelle.includes(wort), `Fußzeile ohne „${wort}“`)
  }
})

test('Palette hängt im App-Rahmen und öffnet über Strg+K und das Suchfeld', () => {
  assert.match(appQuelle, /<Befehlspalette ref="befehlspalette" \/>/, 'die Palette wird nicht gerendert')
  assert.match(appQuelle, /@suche="befehlspalette\?\.oeffnen\(\)"/,
    'das Suchfeld der Kopfzeile öffnet die Palette nicht')
  assert.match(topbarQuelle, /\$emit\('suche'\)/, 'die Kopfzeile meldet den Klick nicht')
  assert.match(topbarQuelle, /dk-topbar-suche/, 'das Suchfeld der Kopfzeile fehlt (Entwurf A5)')
  assert.match(topbarQuelle, /Strg K/, 'das Tastenkürzel steht nicht am Suchfeld')
  // Die Palette hört das Kürzel selbst — am Fenster, damit es überall gilt.
  assert.match(paletteQuelle, /window\.addEventListener\('keydown', beiKuerzel\)/,
    'Strg+K wird nirgends gehört')
  assert.match(paletteQuelle, /removeEventListener\('keydown', beiKuerzel\)/,
    'der Zuhörer wird beim Abbau nicht entfernt (Leck)')
  assert.match(paletteQuelle, /istOeffnenTaste/, 'die Tastaturregel wird nicht benutzt')
})

test('Palette ruft den vorhandenen Such-Endpunkt per GET — und filtert Rechte nicht selbst', () => {
  assert.match(paletteQuelle, /diakronos\.diakonos\.api\.suche\.global/,
    'die Palette benutzt nicht den Such-Endpunkt aus UX3g')
  // Der Endpunkt deklariert `methods=["GET"]` (SEC-11): ein POST bekommt 405.
  // Im Wegwerf-Stack gemessen — deshalb `apiGet`, nicht `apiCall`.
  assert.match(paletteQuelle, /await apiGet\('diakronos\.diakonos\.api\.suche\.global'/,
    'die Suche wird per POST aufgerufen — der Endpunkt erlaubt nur GET (405)')
  assert.doesNotMatch(paletteQuelle, /apiCall\('diakronos\.diakonos\.api\.suche\.global'/,
    'apiCall schickt POST — die Palette muss apiGet benutzen')
  // Keine zweite Rechte-Auslegung auf Treffern: der Server entscheidet.
  assert.doesNotMatch(paletteQuelle, /treffer\.filter\([^)]*istAdmin/,
    'die Palette filtert Server-Treffer nach Rollen — das ist Serversache')
  // Mindestlänge wie im Endpunkt (kein Aufruf unter zwei Zeichen).
  assert.equal(MIN_ZEICHEN, 2)
  assert.match(regelQuelle, /MIN_ZEICHEN = 2/)
})

test('„Zuletzt verwendet“ liegt lokal und wird nie zum Server geschickt', () => {
  assert.match(regelQuelle, /localStorage|getItem\(VERLAUF_SCHLUESSEL\)/)
  assert.match(regelQuelle, /VERLAUF_SCHLUESSEL = 'dk-befehlspalette-zuletzt'/)
  // Der Verlauf speichert nur Zeilen (Titel/Ort/Ziel), keinen Suchtext.
  const schreibBlock = regelQuelle.slice(regelQuelle.indexOf('export function verlaufSchreiben'))
  assert.ok(schreibBlock.length > 0)
  assert.doesNotMatch(schreibBlock.slice(0, 1200), /begriff/i,
    'im Verlauf landet der getippte Begriff — das ist kein „Zuletzt verwendet“')
})

// ── 8. Design-Regeln (Tokens, Skala, Klickflächen) ──────────────────────────

test('Palette hat eine feste Höhe — die Fußzeile darf nicht aus dem Bild rutschen', () => {
  // Im Wegwerf-Stack gemessen: mit nur `max-height` wuchs der Scrollbereich in
  // einem Flex-Container ohne definite Höhe (959 px Inhalt in 508 px Fläche),
  // und die Fußzeile mit ↑↓ / ↵ / Esc lag unterhalb des Bildschirms.
  const block = paletteQuelle.slice(paletteQuelle.indexOf('.dk-palette {'), paletteQuelle.indexOf('.dk-palette-suchzeile {'))
  // Review UX3f: das Maß steht jetzt als Token (`--palette-h: 624px` in
  // tokens.css, wie --melde-w) — die Palette selbst führt kein Literal.
  assert.match(block, /\n\s+height:\s*min\(var\(--palette-h\)/, 'die Palette hat keine feste Höhe (max-height reicht nicht)')
  assert.doesNotMatch(block, /max-height:\s*min\(var\(--palette-h\)/, 'max-height statt height — die Fußzeile rutscht hinaus')
  assert.match(block, /overflow:\s*hidden/)
  // Der Scrollbereich bleibt der einzige, der scrollt.
  assert.match(paletteQuelle, /\.dk-palette-liste \{[^}]*overflow-y:\s*auto/)
})

test('keine festen Farbwerte in der Palette (tokens.css ist die Quelle)', () => {
  assert.doesNotMatch(paletteQuelle, /#[0-9a-fA-F]{3,8}\b/, 'Hex-Farbe in der Palette')
  assert.doesNotMatch(paletteQuelle, /\brgba?\s*\(|\bhsla?\s*\(/, 'rgb()/hsl() in der Palette')
  assert.match(paletteQuelle, /var\(--overlay\)/, 'Abdunkelung nicht aus dem Token')
  assert.match(paletteQuelle, /var\(--surface\)/, 'Fläche nicht aus dem Token')
  assert.match(paletteQuelle, /var\(--focus-ring\)/, 'kein Fokusring (Tastaturbedienung)')
})

test('Abstände nur aus der Skala, Klickflächen mindestens --control-h', () => {
  // Alle padding/margin/gap-Werte in der Palette nennen ein Token.
  const bloecke = [...paletteQuelle.matchAll(/(?:padding|margin|gap)(?:-[\w-]+)?\s*:\s*([^;]+);/g)]
  assert.ok(bloecke.length > 0)
  for (const [, wert] of bloecke) {
    for (const teil of wert.split(/\s+/).filter(Boolean)) {
      assert.ok(
        /^(var\(--[\w-]+\)|0|auto|inherit)$/.test(teil),
        `fester Abstand „${teil}“ — nur Tokens aus der Skala sind erlaubt`,
      )
    }
  }
  // Zeilen und Kopfzeile halten die Klickhöhe.
  assert.match(paletteQuelle, /min-height:\s*var\(--control-h\)/)
  // Mobil/Zeiger: 44 px kommen aus `--control-h: 44px` (index.css,
  // @media pointer: coarse) — die Palette führt KEIN Literal mehr, sondern
  // holt die Zeilenhöhe aus dem Token (Review UX3f, Wächter ux1a).
  assert.doesNotMatch(paletteQuelle, /min-height:\s*44px/, 'Literal 44px statt --control-h')
  assert.match(indexCss, /@media \(pointer: coarse\)[\s\S]*?--control-h:\s*44px/, 'grobe Zeiger: --control-h 44 px fehlt')
})

test('Suchfeld der Kopfzeile ist groß genug und nur mit Tokens gestaltet', () => {
  const block = indexCss.slice(indexCss.indexOf('.dk-topbar-suche {'), indexCss.indexOf('.dk-topbar-search {'))
  assert.ok(block.includes('min-height: var(--control-h)'), 'Suchfeld unter 40 px')
  assert.doesNotMatch(block, /#[0-9a-fA-F]{3,8}\b/, 'Hex-Farbe am Suchfeld')
})

test('Suchfeld der Kopfzeile ist kein Tastatur-Element (kein Bedienelement-Look)', () => {
  const suchBlock = topbarQuelle.slice(topbarQuelle.indexOf('dk-topbar-suche'), topbarQuelle.indexOf('dk-topbar-divider'))
  assert.ok(suchBlock.length > 0)
  assert.doesNotMatch(suchBlock, /<kbd>/, 'Tastenkürzel als Tastatur-Element — wirkt wie eine Taste')
})

// ── 9. Review Opus 07.11. — DSGVO, Tastatur, Kalender, Begriffskatalog ─────
//
// Fünf Befunde der Nacharbeit, jeder mit seinem eigenen Fall:
//   * der Verlauf „Zuletzt verwendet“ hing NICHT am Nutzer,
//   * die aktive Zeile blieb bei ↑↓ aus dem Bild,
//   * Tab fiel aus dem Dialog und der Fokus kehrte nicht zurück,
//   * „Termin anlegen“ wirkte nur beim Mounten der Kalender-Seite,
//   * die Fehlermeldung zeigte `err.message` roh.

test('Review: der Verlauf hängt am Nutzer — zwei Nutzer sehen sich nicht', () => {
  // Der Schlüssel trägt einen Hash der Nutzerkennung, nicht die Kennung selbst.
  const a = verlaufFuerNutzer('anna@example.org')
  const b = verlaufFuerNutzer('bernd@example.org')
  assert.notEqual(a, b, 'beide Nutzer teilen einen Verlaufsschlüssel')
  assert.ok(a.startsWith(VERLAUF_SCHLUESSEL + ':'), 'Nutzerkennung fehlt im Schlüssel')
  assert.ok(!a.includes('anna@example.org'), 'die E-Mail steht im Klartext im Schlüssel')
  assert.equal(verlaufFuerNutzer('anna@example.org'), a, 'der Schlüssel ist nicht stabil')
  // Ohne Kennung bleibt der alte, ungeteilte Schlüssel (Gastaussicht).

  // Geteilter Speicher: Annas Wahl landet NICHT in Bernds Verlauf.
  const speicher = fakeSpeicher()
  verlaufSchreiben(speicher, [{ id: 'a', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' }], 'anna@example.org')
  assert.equal(verlaufLesen(speicher, 'anna@example.org').length, 1)
  assert.deepEqual(verlaufLesen(speicher, 'bernd@example.org'), [], 'Bernd sieht Annas Verlauf')
})

test('Review: Abmelden und Nutzerwechsel räumen fremde Verläufe weg', () => {
  const speicher = fakeSpeicher()
  const eintrag = [{ id: 'a', titel: 'Personen', ziel: '#/personen', ort: 'Gemeinde' }]
  verlaufSchreiben(speicher, eintrag, 'anna@example.org')
  verlaufSchreiben(speicher, eintrag, 'bernd@example.org')
  // Altbestand ohne Nutzerkennung (Fassung vor diesem Fix) liegt noch da.
  speicher.setItem(VERLAUF_SCHLUESSEL, JSON.stringify(eintrag))
  // Fremder Schlüssel, der nicht zum Verlauf gehört, bleibt unangetastet.
  speicher.setItem('dk-anders', 'bleibt')

  verlaufFuerAufraeumen(speicher, 'bernd@example.org')
  assert.equal(verlaufLesen(speicher, 'bernd@example.org').length, 1, 'eigener Verlauf wurde gelöscht')
  assert.deepEqual(verlaufLesen(speicher, 'anna@example.org'), [], 'fremder Verlauf blieb stehen')
  assert.equal(speicher.getItem(VERLAUF_SCHLUESSEL), null, 'Altbestand ohne Nutzer blieb stehen')
  assert.equal(speicher.getItem('dk-anders'), 'bleibt', 'fremder Speicherstand wurde gelöscht')

  // Abmelden (keine Kennung) räumt ALLE Verläufe weg.
  verlaufFuerAufraeumen(speicher, '')
  assert.deepEqual(verlaufLesen(speicher, 'bernd@example.org'), [], 'Abmelden ließ den Verlauf stehen')
})

test('Review: Abmelden und App-Start rufen das Aufräumen wirklich auf', () => {
  const abmelden = lies('src/diakonos/composables/useAbmelden.js')
  assert.match(abmelden, /verlaufFuerNutzerAufraeumen\(window\.localStorage, ''\)/,
    'beim Abmelden wird der Verlauf der Palette nicht geleert')
  const main = lies('src/diakonos/main.js')
  assert.match(main, /verlaufFuerNutzerAufraeumen\(window\.localStorage, kennung\)/,
    'beim Start der SPA wird kein fremder Verlauf weggeräumt')
  // Die Palette gibt die Kennung weiter — sonst schriebe sie in den Gast-Schlüssel.
  assert.match(paletteQuelle, /verlaufLesen\(speicher\(\), nutzerKennung\.value\)/)
  assert.match(paletteQuelle, /verlaufSchreiben\(speicher\(\), verlauf\.value, nutzerKennung\.value\)/)
})

test('Review: die aktive Zeile bleibt im Bild (scrollIntoView, block nearest)', () => {
  assert.match(paletteQuelle, /scrollIntoView\(\{ block: 'nearest'/,
    'die Auswahl kann bei ↑↓ aus dem sichtbaren Bereich wandern')
  // Ausgelöst bei JEDER Auswahländerung, nicht nur beim Öffnen.
  assert.match(paletteQuelle, /watch\(auswahl,[\s\S]{0,200}aktiveZeileSichtbar/,
    'scrollIntoView hängt nicht an der Auswahl')
})

test('Review: Fokusfalle und Fokus-Rückgabe wie bei DkDialog', () => {
  assert.match(paletteQuelle, /useDialogFokus\(offen, fensterEl, schliessen/,
    'die Palette hat keine Fokusfalle (Tab fällt aus dem Dialog)')
  // Genau EIN Esc-Weg: `taste` am Fenster behandelt Esc bereits.
  assert.match(paletteQuelle, /useDialogFokus\([^)]*\{ esc: false \}\)/,
    'Esc würde doppelt behandelt')
  const fokus = lies('src/diakonos/composables/useDialogFokus.js')
  assert.match(fokus, /vorherFokus = document\.activeElement/, 'Fokus wird vor dem Öffnen nicht gemerkt')
  assert.match(fokus, /vorherFokus\.focus\?\.\(\)/, 'Fokus geht beim Schließen nicht zurück')
})

test('Review: „Termin anlegen“ wirkt auch bei offenem Kalender (hashchange)', () => {
  // Ohne Zuhörer bleibt es beim bloßen Adresswechsel: der Hash ändert nur den
  // Abfrageteil, die Seite wird nicht neu gebaut, `onMounted` läuft nie wieder.
  assert.match(kalenderQuelle, /addEventListener\('hashchange', anlegeWunschAusAdresse\)/,
    '„Termin anlegen“ wirkt nur beim ersten Öffnen des Kalenders')
  assert.match(kalenderQuelle, /removeEventListener\('hashchange', anlegeWunschAusAdresse\)/,
    'der Zuhörer wird beim Verlassen der Seite nicht abgemeldet')
  // Die Rechteprüfung steht NACH dem Warten auf den Kalender-Speicher.
  const block = kalenderQuelle.slice(kalenderQuelle.indexOf('function anlegeWunschAusAdresse'))
  const warten = block.indexOf('const start = Date.now()')
  const rechte = block.indexOf('if (hasWriteRight.value)')
  assert.ok(warten > 0 && rechte > warten, 'Rechte werden geprüft, bevor der Kalender-Speicher da ist')
})

test('Review: Fehlermeldung kommt aus dem Begriffskatalog, nicht aus err.message', () => {
  assert.doesNotMatch(paletteQuelle, /err\?\.message/,
    'rohe Servermeldung wird angezeigt (Prinzip I4)')
  assert.match(paletteQuelle, /fehlertext\(err \|\| \{\}/,
    'die Palette benutzt nicht den gemeinsamen Fehlerkatalog')
  // Ein Satz mit „was ist passiert“ UND „was jetzt hilft“.
  assert.match(paletteQuelle, /text: 'Die Suche hat gerade nicht geklappt\. Versuche es noch einmal\.'/)
})

test('Review: Abschnittsüberschriften sind Gruppen mit Namen, keine Deko', () => {
  assert.doesNotMatch(paletteQuelle, /class="dk-palette-abschnitt"\s+role="presentation"/,
    'die Überschrift wird vor Screenreadern versteckt')
  assert.match(paletteQuelle, /role="group"[\s\S]{0,120}:aria-labelledby="abschnittId\(gruppe\.id\)"/,
    'Abschnitt ohne role="group"/aria-labelledby')
  // Jeder Abschnitt hat eine eindeutige ID für aria-labelledby.
  assert.match(paletteQuelle, /:id="abschnittId\(gruppe\.id\)"/)
})
