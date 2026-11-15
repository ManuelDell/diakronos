/**
 * UI-R2 — Gruppen-Einstellungen: Kalender der Gruppe, Freigaben, Sichtbarkeit.
 *
 * Die Oberfläche entscheidet nichts über Rechte. Was hier geprüft wird, ist
 * genau das, was die Oberfläche entscheidet:
 *
 *   T1  Kalenderzuordnung: Welche Kalender gehören zu DIESER Gruppe bzw. zu
 *       dieser Untergruppe? (Felder `gruppe`/`untergruppe` der Serverliste.)
 *   T2  Sichtbarkeits-Zustände: aus / beantragt / aktiv — je Ziel (Gemeinde,
 *       Gruppe) mit Erklärsatz; „an die ganze Gruppe“ nur bei Untergruppen.
 *   T3  Freigaben-Matrix: Zeilen aus Serverfreigaben, Stufen Text, Moderieren
 *       nur, wenn der Server es hergibt; Person schon drin → nicht erneut.
 *   T4  Anlegen: Ziele aus `anlegen_gruppen`/`anlegen_untergruppen` (Gemeinde
 *       nur mit `darf_gemeinde_kalender`), Titel-/Farbprüfung vor dem Senden.
 *   T5  Anlege-Anfrage: genau die Felder, die `create_kalender` erwartet.
 *   T6  Serverfehler (403/417) werden zu Sätzen, nicht zu Codes.
 *   T7  Die Bausteine: `KalenderRechte.vue` ist getrennt (UI-R3 nutzt es mit),
 *       die Karte bindet es ein; Endpunkte nur aus dem EINEN Rechtesystem.
 *   T8  Tokens statt Hartwerte; „öffentlich“ gibt es nicht.
 *
 * Die Rechte-Logik selbst liegt beim Server
 * (`backend/tests/test_r5_*`, `backend/src/diakronos_app/rechte/`).
 *
 * Lauf: node --test tests/uir2-kalender-rechte.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  SICHTBARKEIT_WORT,
  KALENDER_ANLEGEN_FRAGE,
  kalenderZuordnung,
  sichtbarkeitLage,
  sichtbarkeitKnoepfe,
  freigabeZeilen,
  freigabeStufenText,
  freigabeKnoepfe,
  personenAuswahlOhne,
  anlegeZiele,
  pruefeNeuenKalender,
  anlegeAnfrage,
  freigabeAnfrage,
  sichererFehlertext,
} from '../src/diakonos/components/gruppen/kalenderRechte.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ohneKommentare = (t) => t.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

const KARTE = lies('components/gruppen/GruppenEinstellungen.vue')
const KALENDERDATEI = lies('components/gruppen/KalenderEinstellungen.vue')
const RECHTE = lies('components/gruppen/KalenderRechte.vue')
const LOGIK = lies('components/gruppen/kalenderRechte.mjs')

/** Ausschnitt der Antwort von `get_kalender_verwaltung` — so, wie der Server sie liefert. */
const KALENDER = [
  { name: 'Chor', titel: 'Chor', farbe: '#3366cc', gruppe: 'G-Chor', untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' },
  { name: 'Kinderchor', titel: 'Kinderchor', farbe: '#cc6633', gruppe: 'G-Chor', untergruppe: 'UG-K',
    standard_gruppe_lesen: true, gemeinde_status: 'beantragt', gruppe_status: 'aktiv' },
  { name: 'Gemeinde', titel: 'Gemeinde', farbe: '#333333', gruppe: null, untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aktiv', gruppe_status: 'aus' },
  { name: 'Fremd', titel: 'Fremd', farbe: '#999999', gruppe: 'G-Andere', untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus' },
]

// ══════════════════════════════════════════════════════════════════════════
// T1 · Zuordnung
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · Gruppe: Kalender der Gruppe UND ihrer Untergruppen, keine fremden', () => {
  const liste = kalenderZuordnung(KALENDER, { gruppe: 'G-Chor' })
  assert.deepEqual(liste.map((k) => k.name), ['Chor', 'Kinderchor'])
  // Der Gemeinde-Kalender und die fremde Gruppe gehören nicht dazu.
  assert.ok(!liste.some((k) => k.name === 'Gemeinde' || k.name === 'Fremd'))
})

test('UI-R2 · Untergruppe: nur die Kalender DIESER Untergruppe', () => {
  const liste = kalenderZuordnung(KALENDER, {
    gruppe: 'G-Chor', untergruppe: 'UG-K', namen: { 'UG-K': 'Kinderchor', 'G-Chor': 'Chor' },
  })
  assert.deepEqual(liste.map((k) => k.name), ['Kinderchor'])
  // Zuordnung steht als Anzeigename an der Zeile — der Server liefert nur die
  // Kennung, die Seite reicht die Namen der (Unter-)Gruppen durch.
  assert.equal(liste[0].zuordnung, 'Kinderchor')
})

test('UI-R2 · Zuordnung ohne Kennungen (Ladezustand) ergibt eine leere Liste', () => {
  assert.deepEqual(kalenderZuordnung(undefined, { gruppe: 'G-Chor' }), [])
  assert.deepEqual(kalenderZuordnung(KALENDER, {}), [])
  // Eine kaputte Zeile (kein `name`) fällt heraus, statt die Liste zu kippen.
  assert.deepEqual(kalenderZuordnung([null, { titel: 'x' }, ...KALENDER], { gruppe: 'G-Chor' })
    .map((k) => k.name), ['Chor', 'Kinderchor'])
})

test('UI-R2 · Liste sortiert nach Titel (deutsch, unabhängig von Groß/Klein)', () => {
  const liste = kalenderZuordnung([
    { name: 'b', titel: 'zebra', gruppe: 'G-1' },
    { name: 'a', titel: 'Äpfel', gruppe: 'G-1' },
    { name: 'c', titel: 'Chor', gruppe: 'G-1' },
  ], { gruppe: 'G-1' })
  assert.deepEqual(liste.map((k) => k.titel), ['Äpfel', 'Chor', 'zebra'])
})

// ══════════════════════════════════════════════════════════════════════════
// T2 · Sichtbarkeit
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · Sichtbarkeit: aus / beantragt / aktiv als Wort und Erklärung', () => {
  assert.equal(SICHTBARKEIT_WORT.aus, 'Aus')
  assert.equal(SICHTBARKEIT_WORT.beantragt, 'Beantragt')
  assert.equal(SICHTBARKEIT_WORT.aktiv, 'Aktiv')

  const aus = sichtbarkeitLage('aus', 'gemeinde', { untergruppe: null })
  assert.equal(aus.zustand, 'aus')
  assert.match(aus.erlaeuterung, /nur\b|Freigabe/i)
  assert.equal(aus.darfBeantragen, true)
  assert.equal(aus.darfZuruecknehmen, false)

  // UI-R2b (Punkt 11): Die Stufe „gruppe“ prüfen HV/MV der Gruppe — NICHT die
  // Gruppenleitung (die dürfte sich sonst selbst freigeben).
  const gruppenStufe = sichtbarkeitLage('beantragt', 'gruppe', { untergruppe: 'UG-K' })
  assert.match(gruppenStufe.erlaeuterung, /HV\/MV der Gruppe/)
  assert.ok(!/Gruppenleitung/.test(gruppenStufe.erlaeuterung),
    '„wartet auf die Zustimmung der Gruppenleitung“ ist falsch')

  const beantragt = sichtbarkeitLage('beantragt', 'gemeinde', { untergruppe: 'UG-K' })
  assert.equal(beantragt.zustand, 'beantragt')
  assert.match(beantragt.erlaeuterung, /wartet auf die Prüfung durch die Gemeinde/)
  // Ein Satz, der ALLE drei Zustände nennt (für die ⓘ-Erklärung der Stufe).
  assert.match(beantragt.saetze.aktiv, /pr(ü|ue)ft|gepr/)
  // UX2h: „Moderation“ ist gesperrt, „Prüfen“ ist das Wort der Oberfläche.
  assert.match(beantragt.erlaeuterung, /Prüfung durch die Gemeinde/)
  assert.ok(!/Moderation/.test(beantragt.saetze.aus + beantragt.saetze.beantragt + beantragt.saetze.aktiv),
    '„Moderation“ steht in der Fläche')
  // Während eines Antrags gibt es nichts zurückzunehmen und nichts erneut zu beantragen.
  assert.equal(beantragt.darfBeantragen, false)
  assert.equal(beantragt.darfZuruecknehmen, true)

  const aktiv = sichtbarkeitLage('aktiv', 'gemeinde', { untergruppe: 'UG-K' })
  assert.equal(aktiv.zustand, 'aktiv')
  assert.match(aktiv.erlaeuterung, /Jeder neue Termin wird geprüft/)
  assert.equal(aktiv.darfBeantragen, false)
  assert.equal(aktiv.darfZuruecknehmen, true)
})

test('UI-R2 · Sichtbarkeit: „an die ganze Gruppe“ nur bei Untergruppen-Kalendern', () => {
  const gruppe = sichtbarkeitKnoepfe({ untergruppe: 'UG-K', gemeinde_status: 'aus', gruppe_status: 'aus' })
  assert.deepEqual(gruppe.map((k) => k.ziel), ['gruppe', 'gemeinde'])
  assert.match(gruppe[0].text.toLowerCase(), /an die ganze gruppe freigeben/)

  // Ein Kalender der HAUPTgruppe kennt die Stufe „Gruppe“ nicht.
  const haupt = sichtbarkeitKnoepfe({ untergruppe: null, gemeinde_status: 'aus', gruppe_status: 'aus' })
  assert.deepEqual(haupt.map((k) => k.ziel), ['gemeinde'])

  // Ist die Gruppenstufe aktiv, steht sie als Zustand — kein zweiter Antrag.
  const aktiv = sichtbarkeitKnoepfe({ untergruppe: 'UG-K', gemeinde_status: 'aus', gruppe_status: 'aktiv' })
  assert.equal(aktiv.find((k) => k.ziel === 'gruppe').zustand, 'aktiv')
  assert.ok(aktiv.find((k) => k.ziel === 'gruppe').zuruecknehmen)
})

test('UI-R2 · „öffentlich“ gibt es nicht — „Für alle Mitglieder der Gemeinde“', () => {
  const text = RECHTE + LOGIK + KARTE
  assert.ok(!/öffentlich/i.test(ohneKommentare(text)), 'das Wort „öffentlich“ steht in der Fläche')
  assert.match(RECHTE, /Für alle Mitglieder der Gemeinde/)
})

// ══════════════════════════════════════════════════════════════════════════
// T3 · Freigaben-Matrix
// ══════════════════════════════════════════════════════════════════════════

/** Antwort von `rechte.get_objekt_rechte` (Kalender der Untergruppe). */
const OBJEKT = {
  typ: 'kalender', objekt: 'Kinderchor', gruppe: 'G-Chor', untergruppe: 'UG-K',
  standard_gruppe_lesen: true, gemeinde_status: 'beantragt', gruppe_status: 'aktiv',
  freigaben: [
    { benutzer: 'anna@example.org', gruppe: null, lesen: true, schreiben: false, moderieren: false },
    { benutzer: null, gruppe: 'G-Chor', lesen: true, schreiben: true, moderieren: false },
    { benutzer: 'mm@example.org', gruppe: null, lesen: true, schreiben: true, moderieren: true },
  ],
}

test('UI-R2 · Freigabezeilen: Personen und Gruppen, Stufen als Text', () => {
  const zeilen = freigabeZeilen(OBJEKT.freigaben)
  assert.equal(zeilen.length, 3)
  // Kennung der Zeile: Person ODER Gruppe — der Server verlangt genau eine.
  // Sortiert nach Art (Personen zuerst), innerhalb nach Anzeigename.
  assert.deepEqual(zeilen.map((z) => z.art), ['person', 'person', 'gruppe'])
  assert.equal(zeilen[2].gruppe, 'G-Chor')
  assert.equal(freigabeStufenText(zeilen[0]), 'Lesen')
  assert.equal(freigabeStufenText(zeilen[1]), 'Lesen · Schreiben · Moderieren')
  assert.equal(freigabeStufenText(zeilen[2]), 'Lesen · Schreiben')
  // Namen kommen vom Server; fehlt einer, steht die Kennung — nie „undefined“.
  const ohneNamen = freigabeZeilen([{ benutzer: 'x@example.org', lesen: true }])
  assert.equal(ohneNamen[0].anzeige, 'x@example.org')
})

test('UI-R2 · Moderieren hängt an `darf_moderieren_vergeben` (Server), nicht an der Oberfläche', () => {
  const ohne = freigabeKnoepfe({ darf_moderieren_vergeben: false, art: 'person' })
  assert.equal(ohne.modus, false)
  assert.match(ohne.hinweis, /HV und MV/)

  const mit = freigabeKnoepfe({ darf_moderieren_vergeben: true, art: 'person' })
  assert.equal(mit.modus, true)
  assert.deepEqual(mit.stufen, ['lesen', 'schreiben', 'moderieren'])

  // UI-R2b (Punkt 2): „Moderieren“ gilt für JEDE Freigabe-Art. Der Server
  // prüft beim EINTRAG, nicht bei der Art — Gruppenzeilen bekommen die Spalte
  // genauso wie Personen (der frühere Kommentar „nur Personen“ war falsch).
  const gruppe = freigabeKnoepfe({ darf_moderieren_vergeben: true, art: 'gruppe' })
  assert.equal(gruppe.modus, true)
  assert.deepEqual(gruppe.stufen, ['lesen', 'schreiben', 'moderieren'])
})

test('UI-R2 · Personen-Auswahl blendet aus, wer schon eingetragen ist', () => {
  const offen = personenAuswahlOhne(
    [{ benutzer: 'anna@example.org', name: 'Anna' }, { benutzer: 'bea@example.org', name: 'Bea' }],
    OBJEKT.freigaben,
  )
  assert.deepEqual(offen.map((p) => p.benutzer), ['bea@example.org'])
})

test('UI-R2 · Freigabe-Anfrage: alles false entfernt (Serverregel), sonst genau eine Kennung', () => {
  const person = freigabeAnfrage({ objekt: 'Kinderchor', art: 'person', kennung: 'a@example.org', lesen: true })
  assert.equal(person.typ, 'kalender')
  assert.equal(person.objekt, 'Kinderchor')
  assert.equal(person.benutzer, 'a@example.org')
  assert.equal(person.gruppe, undefined)
  assert.equal(person.lesen, true)
  assert.equal(person.schreiben, false)
  assert.equal(person.moderieren, false)

  const gruppe = freigabeAnfrage({ objekt: 'Kinderchor', art: 'gruppe', kennung: 'G-Chor', schreiben: true })
  assert.equal(gruppe.gruppe, 'G-Chor')
  assert.equal(gruppe.benutzer, undefined)
  assert.equal(gruppe.lesen, false)
})

// ══════════════════════════════════════════════════════════════════════════
// T4 · Anlegen
// ══════════════════════════════════════════════════════════════════════════

const VERWALTUNG = {
  kalender: KALENDER,
  darf_gemeinde_kalender: false,
  anlegen_gruppen: ['G-Chor'],
  anlegen_untergruppen: ['UG-K'],
  farbe_standard: '#2266aa',
}

test('UI-R2 · Anlegeziele: nur was der Server erlaubt, Gemeinde nur mit Recht', () => {
  const ziele = anlegeZiele(VERWALTUNG, {
    gruppe: 'G-Chor', untergruppe: 'UG-K',
    gruppeName: 'Chor', untergruppeName: 'Kinderchor',
  })
  // Auf einer Untergruppen-Seite steht die Untergruppe oben (die Leitung legt
  // dort an), die Gruppe darunter — Gemeinde NICHT (kein Recht).
  assert.deepEqual(ziele.map((z) => z.wert), ['UG-K', 'G-Chor'])
  assert.deepEqual(ziele.map((z) => z.art), ['untergruppe', 'gruppe'])
  assert.equal(ziele[0].anzeige, 'Kinderchor')

  const mitGemeinde = anlegeZiele({ ...VERWALTUNG, darf_gemeinde_kalender: true },
    { gruppe: 'G-Chor', gruppeName: 'Chor' })
  assert.deepEqual(mitGemeinde.map((z) => z.wert), ['G-Chor', ''])
  assert.equal(mitGemeinde[1].art, 'gemeinde')
  assert.match(mitGemeinde[1].anzeige, /Für alle Mitglieder der Gemeinde/)
})

test('UI-R2 · Anlegeziele: fremde (Unter-)Gruppen tauchen nicht auf', () => {
  const ziele = anlegeZiele(VERWALTUNG, { gruppe: 'G-Andere', untergruppe: 'UG-X', gruppeName: 'Andere' })
  assert.deepEqual(ziele, [])
})

test('UI-R2 · Titel und Farbe werden VOR dem Senden geprüft', () => {
  assert.equal(pruefeNeuenKalender({ titel: '  ', farbe: '#2266aa' }).ok, false)
  assert.match(pruefeNeuenKalender({ titel: '  ' }).titel, /Namen/)
  // 140 Zeichen ist die Grenze des Servers (create_kalender) — nicht mehr.
  assert.equal(pruefeNeuenKalender({ titel: 'x'.repeat(141) }).ok, false)
  assert.equal(pruefeNeuenKalender({ titel: 'x'.repeat(140) }).ok, true)
  // Farbe: leer ist erlaubt (Server setzt die Standardfarbe), sonst #rrggbb.
  assert.equal(pruefeNeuenKalender({ titel: 'Jugend', farbe: '' }).ok, true)
  assert.equal(pruefeNeuenKalender({ titel: 'Jugend', farbe: '#12345' }).ok, false)
  assert.match(pruefeNeuenKalender({ titel: 'Jugend', farbe: '#12345' }).farbe, /#rrggbb/)
  assert.equal(pruefeNeuenKalender({ titel: 'Jugend', farbe: '#ABCDEF' }).ok, true)
})

test('UI-R2 · Die Anlege-Frage lautet wie in der Karte gefordert', () => {
  assert.equal(KALENDER_ANLEGEN_FRAGE,
    'Sollen alle Gruppenmitglieder diesen Kalender standardmäßig lesen dürfen?')
})

// ══════════════════════════════════════════════════════════════════════════
// T5 · Anlege-Anfrage
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · Anlege-Anfrage trägt Titel, Farbe, Ziel und die Ja/Nein-Antwort', () => {
  const unter = anlegeAnfrage({
    titel: '  Jugend  ', farbe: '#123456', ziel: { wert: 'UG-K', art: 'untergruppe' },
    standardGruppeLesen: true,
  })
  assert.equal(unter.titel, 'Jugend', 'Titel getrimmt')
  assert.equal(unter.farbe, '#123456')
  assert.equal(unter.untergruppe, 'UG-K')
  assert.equal(unter.gruppe, undefined, 'genau EIN Ziel')
  assert.equal(unter.standard_gruppe_lesen, 1)

  const nein = anlegeAnfrage({ titel: 'Jugend', farbe: '#123456',
    ziel: { wert: 'G-Chor', art: 'gruppe' }, standardGruppeLesen: false })
  assert.equal(nein.gruppe, 'G-Chor')
  assert.equal(nein.untergruppe, undefined)
  assert.equal(nein.standard_gruppe_lesen, 0)

  // Gemeinde-Kalender: KEIN gruppe/untergruppe (der Server legt ihn ohne an).
  const gemeinde = anlegeAnfrage({ titel: 'Gemeinde', farbe: '', ziel: { wert: '', art: 'gemeinde' },
    standardGruppeLesen: true })
  assert.equal(gemeinde.gruppe, undefined)
  assert.equal(gemeinde.untergruppe, undefined)
  assert.equal(gemeinde.farbe, '')
})

// ══════════════════════════════════════════════════════════════════════════
// T6 · Fehlertexte
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · Serverfehler werden zu Sätzen, technische Codes nicht angezeigt', () => {
  const rechte = sichererFehlertext(Object.assign(new Error('HTTP 403'), { status: 403 }),
    { text: 'Das hat nicht geklappt.' })
  assert.ok(!/HTTP|403|417/.test(rechte), 'kein Statuscode im Text: ' + rechte)

  const fachlich = sichererFehlertext(Object.assign(
    new Error('Das Prüfrecht vergeben nur HV und MV.'), { status: 403 }),
  { text: 'Das hat nicht geklappt.' })
  assert.equal(fachlich, 'Das Prüfrecht vergeben nur HV und MV.',
    'der fachliche Satz des Servers geht vor')
})

// ══════════════════════════════════════════════════════════════════════════
// T7 · Bausteine und Endpunkte
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · KalenderRechte ist ein eigener Baustein, den die Karte einbindet', () => {
  // GruppenEinstellungen (UI-R1) trägt beide Teile: Rollen + Kalender.
  assert.match(KARTE, /KalenderEinstellungen/, 'GruppenEinstellungen bindet die Kalenderkarte ein')
  assert.match(KALENDERDATEI, /KalenderRechte/, 'die Kalenderkarte bindet KalenderRechte ein')
  // Der Baustein nimmt nur Daten und meldet Änderungen — er lädt NICHT selbst
  // (sonst lüde UI-R3 ihn doppelt in seine Seite).
  assert.match(RECHTE, /defineProps/)
  assert.match(RECHTE, /defineEmits/)
  assert.ok(!/apiCall/.test(ohneKommentare(RECHTE)), 'KalenderRechte ruft selbst keine API')
})

test('UI-R2 · nur die Endpunkte des EINEN Rechtesystems', () => {
  const quelle = ohneKommentare(KALENDERDATEI)
  for (const name of ['get_objekt_rechte', 'setze_freigabe', 'setze_standard_gruppe_lesen',
    'beantrage_sichtbarkeit', 'nimm_sichtbarkeit_zurueck']) {
    assert.ok(quelle.includes(name), `Endpunkt ${name} wird benutzt`)
  }
  // Der alte Verwaltungs-Endpunkt schreibt Alt-Tabellen — für RECHTE gilt das
  // weiter. UI-R3b: `update_kalender` ist wieder da, aber ausschließlich für
  // Titel, Farbe und `selbstverwaltet` (die Rechte laufen über
  // `rechte.setze_freigabe`); die Alt-Felder schickt die Fläche nicht mit.
  const aendert = quelle.match(/update_kalender[\s\S]{0,400}?\)/)?.[0] || ''
  assert.doesNotMatch(aendert, /leserechte|schreibrechte|moderatoren/,
    'update_kalender wird mit Alt-Rechten gerufen — die überschreiben die Freigaben')
  assert.match(quelle, /kalender_verwaltung\.get_kalender_verwaltung/)
  assert.match(quelle, /kalender_verwaltung\.create_kalender/)
  // UI-R3b: Löschen steht wieder in der Fläche — mit Bestätigung.
  assert.match(quelle, /kalender_verwaltung\.delete_kalender/)
  assert.match(quelle, /delete_kalender`|delete_kalender'/,
    'der Lösch-Endpunkt wird nicht über die gemeinsame Konstante gerufen')
})

test('UI-R2 · „gilt sofort“ steht als Hinweis an der Matrix', () => {
  assert.match(RECHTE, /gilt sofort/)
})

// ══════════════════════════════════════════════════════════════════════════
// T8 · Tokens
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2 · keine festen Farben in den neuen Dateien', () => {
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/
  for (const [name, text] of [['KalenderRechte.vue', RECHTE], ['KalenderEinstellungen.vue', KALENDERDATEI],
    ['GruppenEinstellungen.vue', KARTE]]) {
    const stil = text.includes('<style') ? text.slice(text.indexOf('<style')) : text
    assert.ok(!farbe.test(stil), `${name}: keine festen Farbwerte`)
  }
})

test('UI-R2 · eigene Abstände/Rahmen nur als Token', () => {
  const abstand = /(margin|padding|gap|row-gap|column-gap|border|border-radius|inset|top|right|bottom|left)[\w-]*\s*:\s*[^;]*\d+(px|rem|em)/g
  for (const [name, text] of [['KalenderRechte.vue', RECHTE], ['KalenderEinstellungen.vue', KALENDERDATEI],
    ['GruppenEinstellungen.vue', KARTE]]) {
    const stil = text.slice(text.indexOf('<style'))
    const treffer = [...stil.matchAll(abstand)].filter((m) => !m[0].includes('var(--'))
    assert.deepEqual(treffer.map((m) => m[0]), [], `${name}: Maße aus Tokens`)
  }
})
