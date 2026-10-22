/**
 * DES-REST-b — Nacharbeit aus dem Opus-Review.
 *
 * B1  Symlink frontend/node_modules war committet (Merge-Blocker)
 * B2  DkDatumZeit: mehrtägige Termine wurden still auf einen Tag gekürzt
 * W1  Liedgruppen: ReferenceError isAlle (Chips bei leerer Liste)
 * W2  Organigramm-Treffzeit: Freitext wurde beim Speichern verfälscht
 * K3  Zeitfeld step=60, damit 19:07 gültig ist
 *
 * Reine Logiktests (Node, ohne Browser). Die Bedienprobe im Browser steht im
 * Abschlusskommentar der Karte.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (rel) => readFileSync(new URL('../' + rel, import.meta.url), 'utf8')

import {
  zerlegeDatumZeit, baueDatumZeit, endeMitBeginn, pruefeZeitraumMitDatum,
  endeAusBeginnMitDatum, datumNach, tageDazwischen, zeitraumText,
  vorschau, wochentag,
} from '../src/diakonos/composables/datumZeit.mjs'

// ── B1 (nicht hier prüfbar) ─────────────────────────────────────────────────
//
// B1 ist eine Eigenschaft des REPOSITORY-Zustands (ein Link im Git-Index und
// eine Ignorierregel), keine der Anwendung. Das Image hat weder `.git` noch
// `.gitignore` (beide stehen in .dockerignore), ein Node-Test dort könnte nur
// falsch-negativ scheitern. Der Nachweis steht deshalb im Abschlusskommentar
// der Karte und ist mit `git ls-files` / `git check-ignore` belegt:
//   git ls-files -s frontend/node_modules   -> leer
//   git check-ignore -v frontend/node_modules -> .gitignore:frontend/node_modules
// Diese Datei prüft ab hier, was die ANWENDUNG betrifft (B2, W1, W2, K3).

// ── B2: mehrtägige Termine ──────────────────────────────────────────────────

test('B2 · Enddatum und Beginn: das Ende wandert nur mit, wenn es hinterherhinkt', () => {
  // Mehrtaegig, unveraendert: nichts wandert.
  assert.equal(endeMitBeginn('2026-02-23', '2026-02-25'), '2026-02-25')
  // Beginn auf den letzten Tag geschoben: Ende zieht nach.
  assert.equal(endeMitBeginn('2026-02-26', '2026-02-25'), '2026-02-26')
  // Eintaegig bleibt eintaegig.
  assert.equal(endeMitBeginn('2026-02-23', '2026-02-23'), '2026-02-23')
  assert.equal(endeMitBeginn('2026-02-23', ''), '')
})

test('B2 · datumNach rechnet über Monats- und Jahresgrenzen', () => {
  assert.equal(datumNach('2026-03-01', '2026-02-28'), true)
  assert.equal(datumNach('2026-02-28', '2026-03-01'), false)
  assert.equal(datumNach('2027-01-01', '2026-12-31'), true)
  assert.equal(datumNach('', '2026-12-31'), false)
  assert.equal(datumNach('2026-02-31', '2026-02-28'), false, '31.02. ist kein Tag')
})

test('B2 · mehrtägig ist gültig, auch wenn die Endzeit vor der Beginnzeit liegt', () => {
  // Genau der Befund: 23.02. 09:00 – 25.02. 18:00 wurde als „Ende vor Beginn“
  // abgelehnt bzw. still gekürzt.
  assert.equal(pruefeZeitraumMitDatum('2026-02-23', '09:00', '2026-02-25', '18:00'), '')
  assert.equal(pruefeZeitraumMitDatum('2026-02-23', '09:00', '2026-02-25', '08:00'), '')
  // Eintaegig bleibt die Prüfung wie bisher.
  assert.equal(pruefeZeitraumMitDatum('2026-02-23', '09:00', '2026-02-23', '08:00'),
    'Das Ende liegt vor dem Beginn.')
  // Ende vor dem Beginn (Datum): Fehler.
  assert.equal(pruefeZeitraumMitDatum('2026-02-23', '09:00', '2026-02-22', '18:00'),
    'Das Ende liegt vor dem Beginn.')
  // Ganztägig zählt nur das Datum.
  assert.equal(pruefeZeitraumMitDatum('2026-03-05', '', '2026-03-08', '', true), '')
  assert.equal(pruefeZeitraumMitDatum('2026-03-05', '', '2026-03-05', '', true), '')
  assert.equal(pruefeZeitraumMitDatum('2026-03-05', '', '2026-03-01', '', true),
    'Das Ende liegt vor dem Beginn.')
})

test('B2 · ganztägig mehrtägig bleibt erhalten (Jugendtag 05.–08.03.)', () => {
  // Der Baustein baut das Ende aus dem EIGENEN Datum — nicht aus dem Beginn.
  const anfang = zerlegeDatumZeit('2026-03-05')
  const ende = zerlegeDatumZeit('2026-03-08')
  assert.equal(baueDatumZeit(anfang.datum, ''), '2026-03-05')
  assert.equal(baueDatumZeit(ende.datum, ''), '2026-03-08')
  assert.equal(endeMitBeginn(anfang.datum, ende.datum), '2026-03-08')
  assert.equal(zeitraumText('2026-03-05', '2026-03-08'), '4 Tage (Do.–So.)')
})

test('B2 · die Endzeit eines mehrtägigen Termins bleibt stehen', () => {
  // Ändert der Bearbeiter nur den Beginn, darf das Ende (Datum UND Zeit)
  // nicht auf den Vorschlag „Beginn + 1 Stunde“ zurückfallen.
  assert.equal(endeAusBeginnMitDatum('2026-02-23', '09:00', '2026-02-25', '18:00'), '18:00')
  assert.equal(endeAusBeginnMitDatum('2026-02-23', '09:00', '2026-02-25', ''), '10:00')
  // Eintaegig: Vorschlag wie bisher (S8).
  assert.equal(endeAusBeginnMitDatum('2026-02-23', '19:00', '2026-02-23', ''), '20:00')
  // Ganztägig: keine Uhrzeit erfinden.
  assert.equal(endeAusBeginnMitDatum('2026-03-05', '', '2026-03-08', '', true), '')
})

test('B2 · Tage und Dauer werden richtig gezählt', () => {
  assert.equal(tageDazwischen('2026-02-23', '2026-02-25'), 2)
  assert.equal(tageDazwischen('2026-02-25', '2026-02-23'), -2)
  assert.equal(tageDazwischen('2026-02-23', '2026-02-23'), 0)
  assert.equal(tageDazwischen('2026-02-23', ''), null)
  assert.equal(zeitraumText('2026-02-23', '2026-02-25'), '3 Tage (Mo.–Mi.)')
  assert.equal(zeitraumText('2026-02-23', '2026-02-24'), '2 Tage (Mo.–Di.)')
  assert.equal(zeitraumText('2026-02-23', '2026-02-23'), '')
  assert.equal(zeitraumText('2026-02-23', ''), '')
})

// ── B2: Verdrahtung im Baustein und in den Dialogen ─────────────────────────

test('B2 · DkDatumZeit führt ein eigenes Enddatum', () => {
  const quelle = lies('src/diakonos/components/ui/DkDatumZeit.vue')
  assert.match(quelle, /const endeDatum = ref\(''\)/, 'Enddatum fehlt')
  assert.match(quelle, /baueDatumZeit\(bisDatum \|\| datum\.value/, 'Ende wird noch am Beginndatum gebaut')
  assert.match(quelle, /endeAusBeginnMitDatum/, 'Zeitraumprüfung ohne Datum')
  // Das alte, kürzende Verhalten darf nicht zurückkommen.
  assert.ok(!/baueDatumZeit\(datum\.value, endeZeit\.value\)/.test(quelle),
    'Ende wird wieder am Beginndatum gebaut (B2)')
})

test('B2 · Anlegen, Bearbeiten und Moderationsfenster binden das Enddatum', () => {
  const dateien = [
    'src/diakonos/components/kronos/KronosEventCreate.vue',
    'src/diakonos/components/kronos/KronosEventEdit.vue',
    'src/diakonos/components/kronos/ModerationModals.vue',
  ]
  for (const datei of dateien) {
    const quelle = lies(datei)
    assert.match(quelle, /v-model:ende-model-value=/, `${datei}: ende-model-value fehlt`)
    assert.match(quelle, /:mit-ende="true"/, `${datei}: mit-ende fehlt`)
  }
})

// ── W1 ──────────────────────────────────────────────────────────────────────

test('W1 · Liedgruppen benutzt istAlle (kein ReferenceError mehr)', () => {
  const quelle = lies('src/diakonos/pages/Liedgruppen.vue')
  assert.ok(!/\bisAlle\(/.test(quelle), 'isAlle ist wieder da (ReferenceError W1)')
  assert.match(quelle, /istAlle\(c\.id\)/)
})

test('W1 · Chips einer leeren Liste werden fehlerfrei berechnet', async () => {
  const { chipsAus, istAlle } = await import('../src/diakonos/composables/filterChips.mjs')
  const chips = chipsAus([], (g) => g.typ)
  assert.ok(Array.isArray(chips), 'chipsAus liefert kein Feld')
  // Genau die Zeile aus Liedgruppen.vue — früher warf sie den ReferenceError.
  const sichtbar = chips.filter(c => c.anzahl > 0 || istAlle(c.id))
  assert.equal(sichtbar.length, 1, 'genau der „Alle“-Chip bleibt sichtbar')
  assert.equal(sichtbar[0].anzahl, 0)
})

test('W1 · Liedgruppen-Chips zeichnen sich in allen Modi ohne Fehler', () => {
  // Die Seite als Modul laden und die Chip-Berechnung nachrechnen — die Formel
  // steht im Quelltext, also wird sie hier aus dem Quelltext gelesen und
  // gegen echte Daten gerechnet (kein Vue-Renderer nötig).
  const quelle = lies('src/diakonos/pages/Liedgruppen.vue')
  const formel = /\.filter\(c => ([^\n]+)\)\)/.exec(quelle)
  assert.ok(formel, 'Chip-Filterzeile nicht gefunden')
  assert.match(formel[1], /istAlle/)
})

// ── W2 ──────────────────────────────────────────────────────────────────────

test('W2 · Treffzeit-Freitext bleibt beim Speichern unverändert', () => {
  const quelle = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  // Zwei getrennte Regeln: leere Felder => Altext, sonst das Gewählte.
  assert.match(quelle, /if \(!gebaut\) return editForm\.value\.treffzeit \|\| ''/,
    'der Altext fällt wieder weg')
  // Beim Öffnen wird NICHT aus dem Altext vorbelegt.
  assert.ok(!/treffzeitTag\.value = normiereWochentag\(/.test(quelle),
    'die Felder werden wieder aus dem Altext gefüllt (W2)')
  assert.ok(!/treffzeitUhr\.value = normiereUhrzeit\(/.test(quelle))
})

test('W2 · die vier Befund-Beispiele bleiben Text', async () => {
  const { baueTreffzeit, normiereWochentag, normiereUhrzeit } =
    await import('../src/diakonos/composables/treffzeit.mjs')
  const faelle = [
    'jeden 2. Dienstag im Monat, 19:30',
    '1. Sonntag im Monat 17:00',
    '14-tägig Freitag 18 Uhr',
    'Di + Do 19 Uhr',
    'nach Absprache',
  ]
  for (const text of faelle) {
    // Der Baustein kennt nur erkannte Wochentage/Zeiten; die Felder sind leer,
    // also bleibt der Text stehen.
    assert.equal(baueTreffzeit('', ''), '', text)
    // Gegenprobe: das alte Verhalten hätte daraus etwas anderes gebaut.
    const alt = baueTreffzeit(normiereWochentag(text), normiereUhrzeit(text))
    if (alt) assert.notEqual(alt, text, `Beispiel ${text}: Zugprobe greift nicht`)
  }
})

// ── K3 ──────────────────────────────────────────────────────────────────────

test('K3 · Zeitfelder lassen Minuten zu, die nicht auf 5 fallen (19:07)', () => {
  const baustein = lies('src/diakonos/components/ui/DkDatumZeit.vue')
  assert.ok(!/type="time"\s*\n?\s*step="300"/.test(baustein), 'step=300 verbietet 19:07')
  assert.ok((baustein.match(/type="time"/g) || []).length >= 2)
  for (const treffer of baustein.matchAll(/type="time"[\s\S]{0,80}?step="(\d+)"/g)) {
    assert.equal(treffer[1], '60', `step=${treffer[1]} verbietet krumme Minuten`)
  }
  // Auch die Uhrzeit der Treffzeit im Organigramm.
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  assert.match(org, /type="time" step="60"/)
})

// ── K4: Beiträge nutzt die gemeinsame Chip-Zeile ────────────────────────────

test('K4 · Beiträge filtert mit DkFilterChips statt DkSegment', () => {
  const quelle = lies('src/diakonos/pages/Beitraege.vue')
  assert.match(quelle, /<DkFilterChips/, 'Chip-Zeile fehlt')
  assert.match(quelle, /import DkFilterChips/, 'Baustein nicht eingebunden')
  assert.match(quelle, /chipsAus\(/, 'Chips werden nicht aus dem Baustein gebaut')
  assert.ok(!/<DkSegment/.test(quelle), 'DkSegment ist zurück (zweite Optik, K4)')
  assert.ok(!/import DkSegment/.test(quelle))
})

test('K4 · der Ruhezustand der Beiträge-Chips ist „alle“ (nicht „all“)', async () => {
  // Befund im Browser: alle vier Chips standen auf aria-pressed="false", weil
  // `activeCategory` auf 'all' stand, `DkFilterChips` als Ruhezustand aber
  // `alleWert` = 'alle' erwartet. Folge: „Alle“ sah ungewählt aus und
  // `filterAktiv` hielt jeden Besuch für einen gesetzten Filter.
  const quelle = lies('src/diakonos/pages/Beitraege.vue')
  assert.match(quelle, /const activeCategory = ref\('alle'\)/, 'Ruhezustand ist nicht „alle“')
  assert.ok(!/activeCategory\.value !== 'all'/.test(quelle), 'filterAktiv vergleicht noch mit „all“')

  // Und der Baustein selbst muss diesen Wert als gewählt erkennen.
  const chips = [{ id: 'alle', label: 'Alle', anzahl: 3 }, { id: 'Jugend', label: 'Jugend', anzahl: 2 }]
  const { istAlle } = await import('../src/diakonos/composables/filterChips.mjs')
  const gewaehlt = chips.map(c => 'alle' === c.id || (istAlle('alle') && c.id === 'alle'))
  assert.equal(gewaehlt[0], true, '„Alle“ ist im Ruhezustand gewählt')
  assert.equal(gewaehlt[1], false)
})

test('K4 · die Zahl am Chip kommt aus dem Baustein, nicht aus dem Label', async () => {
  const { chipsAus } = await import('../src/diakonos/composables/filterChips.mjs')
  const posts = [{ kategorie: 'Jugend' }, { kategorie: 'Jugend' }, { kategorie: 'Gottesdienst' }]
  const chips = chipsAus(posts, (p) => p.kategorie, null, { alleLabel: 'Alle' })
  assert.equal(chips[0].label, 'Alle', 'das Label darf die Zahl nicht doppelt tragen')
  assert.equal(chips[0].anzahl, 3)
  assert.deepEqual(chips.find(c => c.id === 'Jugend'), { id: 'Jugend', label: 'Jugend', anzahl: 2 })
})

// ── REST-3 K-a: die Vorschau sagt die Zeit EINMAL ───────────────────────────
//
// Befund R-DES-REST-b (K-a): Bei einem mehrtägigen Termin stand die Beginnzeit
// doppelt („Mo., 23.02.2026, 09:00 Uhr, 09:00 – Mi., 25.02.2026 …“), und bei
// ganztägig mehrtägig ein überzähliges „Uhr“ („So., 08.03.2026 Uhr“).
//
// Der Baustein ist ein SFC — die Vorschau-Zeile wird hier aus der Quelle
// nachgebaut (dieselben Bausteine: vorschau() + wochentagKurz + Datum), damit
// die Zeichenkette selbst geprüft wird und nicht nur ihr Vorhandensein.

/**
 * Die Vorschau-Zeile von DkDatumZeit für einen mehrtägigen Termin — wörtlich
 * der Ausdruck aus der Komponente (unten zusätzlich an der Quelle geprüft,
 * damit dieser Nachbau nicht stillschweigend auseinanderläuft).
 */
function vorschauMehrtaegig({ datum, zeit, endeDatum, endeZeit, ganztags = false }) {
  const kopf = vorschau(datum, ganztags ? '' : zeit)
  const zEnde = ganztags ? '' : `, ${endeZeit}`
  const uhr = ganztags ? '' : ' Uhr'
  const wt = (d) => wochentag(d).kurz
  const dd = (d) => `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.slice(0, 4)}`
  return `${kopf} – ${wt(endeDatum)}, ${dd(endeDatum)}${zEnde}${uhr}`
}

test('K-a · mehrtägig nennt die Beginnzeit nur einmal', () => {
  const text = vorschauMehrtaegig({
    datum: '2026-02-23', zeit: '09:00', endeDatum: '2026-02-25', endeZeit: '00:00',
  })
  assert.equal(text, 'Mo., 23.02.2026, 09:00 Uhr – Mi., 25.02.2026, 00:00 Uhr')
  assert.equal((text.match(/09:00/g) || []).length, 1, 'Beginnzeit steht doppelt')
})

test('K-a · ganztägig mehrtägig ohne Uhrzeit und ohne „Uhr“', () => {
  const text = vorschauMehrtaegig({
    datum: '2026-03-05', zeit: '', endeDatum: '2026-03-08', endeZeit: '', ganztags: true,
  })
  assert.equal(text, 'Do., 05.03.2026 – So., 08.03.2026')
  assert.ok(!text.includes('Uhr'), 'ganztägig darf kein „Uhr“ tragen')
  assert.ok(!/\d{2}:\d{2}/.test(text), 'ganztägig darf keine Uhrzeit erfinden')
})

test('K-a · der Baustein selbst baut die Vorschau so', () => {
  const quelle = lies('src/diakonos/components/ui/DkDatumZeit.vue')
  // Der mehrtägige Zweig der Vorschau: „kopf“ nennt die Beginnzeit schon,
  // danach kommt NUR noch der Zeitraum bis zum Ende.
  const zweig = quelle.match(/if \(mehrtaegig\.value\) \{([\s\S]*?)\n  \}/)
  assert.ok(zweig, 'mehrtägiger Vorschau-Zweig nicht gefunden')
  assert.ok(!/zStart/.test(zweig[1]),
    'zStart hängt die Beginnzeit wieder an (Doppelung)')
  assert.match(zweig[1], /return `\$\{kopf\} – \$\{wochentagKurz\(endeDatum\.value\)\}/,
    'die mehrtägige Vorschau beginnt nicht mit „kopf – “')
  assert.match(zweig[1], /const uhr = props\.ganztags \? '' : ' Uhr'/,
    'ganztägig bekommt weiterhin ein „Uhr“')
})
