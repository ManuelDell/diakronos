/**
 * UI-R1 — Gruppen-Einstellungen: Rollen (HV, MV, GL).
 *
 * Die Oberfläche entscheidet nicht über Rechte — sie blendet nur aus, was der
 * Server ohnehin verweigert. Was hier geprüft wird, ist genau das:
 *
 *   T1  Rollenliste: HV oben, dann MV, dann GL je Untergruppe (Namen statt
 *       Kennungen), Untergruppen alphabetisch.
 *   T2  Knöpfe hängen an den Serverfeldern `darf_hv_mv_ernennen` (MV, HV
 *       übertragen) und `darf_verwalten` (GL).
 *   T3  HV-Übertragung: Sicherheitsabfrage — der getippte Name muss passen,
 *       sonst wird nicht gesendet; „Bisherige/r HV wird MV“ ist Standard an.
 *   T4  Die Komponente ruft AUSSCHLIESSLICH die Endpunkte des EINEN
 *       Rechtesystems (`diakronos_app.api.rechte.*`) und benutzt den alten
 *       Endpunkt `verantwortliche.set_verantwortliche` nicht.
 *   T5  Die Detailseite tauscht die alte Karte „Verantwortliche“ gegen den
 *       neuen Bereich (weiterhin nur für Verwalter sichtbar).
 *   T6  Erklärtext: Das HV-Amt kann nur übertragen, nicht entfernt werden.
 *   T7  Keine festen Farben und keine eigenen Abstandsmaße in den neuen
 *       Dateien (Tokens, Prinzip Ä4/UX1a).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ROLLEN_NAME,
  HV_HINWEIS,
  normalName,
  rollenOrdnen,
  darfMvPflegen,
  darfGlPflegen,
  darfHvUebertragen,
  darfEinstellungenSehen,
  hvUebertragenPruefen,
  freiePersonen,
} from '../src/diakonos/components/gruppen/gruppenEinstellungen.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ohneKommentare = (t) => t.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')

const ROLLEN = lies('components/gruppen/RollenEinstellungen.vue')
const KARTE = lies('components/gruppen/GruppenEinstellungen.vue')
const LOGIK = lies('components/gruppen/gruppenEinstellungen.mjs')
const DETAIL = lies('pages/GruppeDetail.vue')

/** R-12c: die Antwort von get_gruppenrollen — Name und Untergruppenname
 *  kommen vom Server, `benutzer` nur für die Leitung. */
const WELT = [
  { benutzer: 'samuel@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Samuel Fink' },
  { benutzer: 'rebekka@example.org', rolle: 'HV', untergruppe: null, untergruppe_name: null, name: 'Rebekka Fink' },
  { benutzer: 'mira@example.org', rolle: 'MV', untergruppe: null, untergruppe_name: null, name: 'Mira Mit' },
  { benutzer: 'anna@example.org', rolle: 'GL', untergruppe: 'UG-E', untergruppe_name: 'Chor-Eltern', name: 'Anna Beispiel' },
  { benutzer: 'jonas@example.org', rolle: 'GL', untergruppe: 'UG-K', untergruppe_name: 'Kinderchor', name: 'Jonas Jung' },
]

// ── T1 · Rollenliste ──────────────────────────────────────────────────────
test('UI-R1 · Rollenliste ordnet HV, dann MV, dann GL je Untergruppe', () => {
  const o = rollenOrdnen(WELT)
  assert.deepEqual(o.hv.map((r) => r.name), ['Rebekka Fink'])
  assert.deepEqual(o.mv.map((r) => r.name), ['Mira Mit'])
  assert.deepEqual(o.glJeUntergruppe.map((g) => g.anzeige), ['Chor-Eltern', 'Kinderchor'],
    'Untergruppen nach ANZEIGENAME alphabetisch')
  assert.deepEqual(o.glJeUntergruppe[1].eintraege.map((e) => e.name), ['Jonas Jung', 'Samuel Fink'],
    'innerhalb der Untergruppe nach Name')
  assert.equal(o.anzahl, 5)
})

test('UI-R1 · Rollenliste zeigt den ANZEIGENAMEN des Servers (R-12c), nie die Kennung', () => {
  const o = rollenOrdnen(WELT)
  assert.equal(o.hv[0].name, 'Rebekka Fink')
  // Lesende bekommen `benutzer: null` — der Name steht trotzdem da.
  const lesend = rollenOrdnen(WELT.map((r) => ({ ...r, benutzer: null })))
  assert.equal(lesend.anzahl, 5, 'Zeilen ohne Kontokennung erscheinen weiterhin')
  assert.equal(lesend.hv[0].name, 'Rebekka Fink')
  assert.equal(lesend.hv[0].benutzer, null, 'ohne Konto keine Aktion anbieten')
  // Eine E-Mail darf NIE als Name erscheinen.
  for (const e of lesend.alle) assert.ok(!String(e.name).includes('@'), 'Kennung als Name: ' + e.name)

  for (const leer of [null, undefined, [], 'kaputt']) {
    const l = rollenOrdnen(leer)
    assert.equal(l.anzahl, 0)
    assert.deepEqual(l.alle, [])
  }
  const unbekannt = rollenOrdnen([{ benutzer: 'x@example.org', rolle: 'XY', name: 'X' }])
  assert.equal(unbekannt.anzahl, 0, 'unbekannte Rolle wird nicht angezeigt')
})

test('UI-R1 · auf einer Untergruppen-Seite bleibt nur die GL dieser Untergruppe', () => {
  const o = rollenOrdnen(WELT, { nurUntergruppe: 'UG-K' })
  assert.deepEqual(o.alle.map((r) => r.name), ['Jonas Jung', 'Samuel Fink'],
    'nur die GL dieser Untergruppe, kein HV/MV, keine fremde Untergruppe')
  assert.ok(o.alle.every((r) => r.rolle === 'GL'))
})

// ── T2 · Knöpfe folgen den Serverfeldern ──────────────────────────────────
test('UI-R1 · MV-Knopf nur bei darf_hv_mv_ernennen', () => {
  assert.equal(darfMvPflegen({ darf_hv_mv_ernennen: true }), true)
  assert.equal(darfMvPflegen({ darf_hv_mv_ernennen: false, darf_verwalten: true }), false,
    'Verwalten allein erlaubt kein MV-Ernennen')
  assert.equal(darfMvPflegen({}), false)
  assert.equal(darfMvPflegen(null), false)
})

test('UI-R1 · GL-Knopf nur bei darf_verwalten', () => {
  assert.equal(darfGlPflegen({ darf_verwalten: true }), true)
  assert.equal(darfGlPflegen({ darf_hv_mv_ernennen: true }), false)
  assert.equal(darfGlPflegen({}), false)
})

test('UI-R1 · HV-Übertragung und Sichtbarkeit des Reiters', () => {
  assert.equal(darfHvUebertragen({ darf_hv_mv_ernennen: true }), true)
  assert.equal(darfHvUebertragen({ darf_verwalten: true }), false)
  assert.equal(darfEinstellungenSehen({ darf_verwalten: true }), true)
  assert.equal(darfEinstellungenSehen({ darf_hv_mv_ernennen: true }), true)
  assert.equal(darfEinstellungenSehen({}), false, 'reines Mitglied sieht den Reiter nicht')
})

// ── T3 · Sicherheitsabfrage der HV-Übertragung ────────────────────────────
test('UI-R1 · HV-Übertragung verlangt den Namen der neuen Person', () => {
  const wer = { benutzer: 'mira@example.org', name: 'Mira Mit' }
  assert.equal(hvUebertragenPruefen({ neuerHv: wer.benutzer, name: wer.name, eingabe: 'Mira Mit' }).ok, true)
  assert.equal(hvUebertragenPruefen({ neuerHv: wer.benutzer, name: wer.name, eingabe: '  mira   MIT ' }).ok, true,
    'Groß/Klein und Leerzeichen sind egal')
  assert.equal(hvUebertragenPruefen({ neuerHv: wer.benutzer, name: wer.name, eingabe: 'Mira' }).ok, false,
    'halber Name genügt nicht')
  assert.equal(hvUebertragenPruefen({ neuerHv: wer.benutzer, name: wer.name, eingabe: '' }).ok, false)
  assert.equal(hvUebertragenPruefen({ neuerHv: '', name: '', eingabe: '' }).grund, 'person')
})

test('UI-R1 · normalName vereinheitlicht Leerraum und Groß/Klein', () => {
  assert.equal(normalName('  Samuel \n Fink '), 'samuel fink')
  assert.equal(normalName(null), '')
})

test('UI-R1 · Auswahlliste lässt bereits Eingetragene weg', () => {
  const personen = [
    { benutzer: 'mira@example.org', name: 'Mira Mit' },
    { benutzer: 'anna@example.org', name: 'Anna Beispiel' },
    { benutzer: 'jonas@example.org', name: 'Jonas Jung', email: 'nicht@zeigen' },
  ]
  const frei = freiePersonen(personen, WELT)
  assert.deepEqual(frei.map((p) => p.benutzer), [], 'alle drei haben im Beispiel schon eine Rolle')

  const nurGl = freiePersonen(personen,
    [{ benutzer: 'anna@example.org', rolle: 'GL', untergruppe: 'Chor-Eltern' }], ['GL'])
  assert.deepEqual(nurGl.map((p) => p.benutzer), ['mira@example.org', 'jonas@example.org'],
    'nur wer die GL schon hat, fällt weg')
  assert.deepEqual(Object.keys(frei[0] || { benutzer: 1, name: 1 }), ['benutzer', 'name'],
    'keine weiteren Felder (der Server liefert nur Namen)')
})

// ── T4 · Nur die Endpunkte des EINEN Rechtesystems ────────────────────────
test('UI-R1 · die Komponente spricht nur diakronos_app.api.rechte an', () => {
  const quelle = ohneKommentare(ROLLEN)
  for (const fn of ['get_gruppenrollen', 'ernenne_mv', 'entferne_mv', 'ernenne_gl',
    'entferne_gl', 'uebertrage_hv', 'get_personen_auswahl']) {
    assert.ok(quelle.includes(fn), `Endpunkt ${fn} wird benutzt`)
  }
  assert.match(quelle, /diakronos_app\.api\.rechte/,
    'Pfad des EINEN Rechtesystems')
  assert.ok(!quelle.includes('set_verantwortliche'),
    'der alte Endpunkt darf hier nicht mehr benutzt werden')
  assert.ok(!/verantwortliche\.(get|set)_verantwortliche/.test(quelle))
})

test('UI-R1 · HV-Übertragung sendet bestaetigt=true und die MV-Option', () => {
  const quelle = ohneKommentare(ROLLEN)
  assert.match(quelle, /bestaetigt:\s*true/, 'Server verlangt bestaetigt=true')
  assert.match(quelle, /alter_hv_wird_mv/, 'Checkbox „Bisherige/r HV wird MV“')
  assert.match(quelle, /alterHvWirdMv\s*=\s*ref\(true\)/,
    'Standard: an')
})

// ── T5 · Ersetzt die alte Karte auf der Gruppenseite ─────────────────────
test('UI-R1 · die Gruppenseite ersetzt „Verantwortliche“ durch die Einstellungen', () => {
  const quelle = ohneKommentare(DETAIL)
  assert.ok(!quelle.includes('VerantwortlicheKarte'),
    'die alte Karte ist von der Gruppenseite entfernt')
  assert.match(quelle, /GruppenEinstellungen/, 'der neue Bereich wird eingebunden')
  assert.match(quelle, /darfEinstellungenSehen/, 'Sichtbarkeit aus den Serverdaten')
})

test('UI-R1 · die Detailseite trägt den Reiter in der Adresse', () => {
  const quelle = ohneKommentare(DETAIL)
  assert.match(quelle, /reiter/, 'Reiterzeile (Übersicht · Einstellungen)')
  assert.match(quelle, /einstellungen/, 'Reiter „Einstellungen“')
})

// ── T6 · Begriffe und Erklärtext ──────────────────────────────────────────
test('UI-R1 · Begriffe HV/MV/GL sind ausgeschrieben', () => {
  assert.equal(ROLLEN_NAME.HV, 'Hauptverantwortliche/r')
  assert.equal(ROLLEN_NAME.MV, 'Mitverantwortliche/r')
  assert.equal(ROLLEN_NAME.GL, 'Gruppenleitung')
  assert.match(HV_HINWEIS, /nur übertragen, nicht entfernt/)
  // Die ausgeschriebenen Rollen stehen in der Rollenliste (die Karte selbst
  // bindet nur noch ein).
  for (const name of ['Hauptverantwortliche/r', 'Mitverantwortliche/r']) {
    assert.ok(ROLLEN.includes(name), `RollenEinstellungen.vue: ${name} ausgeschrieben`)
  }
  assert.ok(KARTE.includes('RollenEinstellungen'), 'die Karte bindet die Rollenliste ein')
  // „öffentlich“ gibt es in der Rollenfläche nicht (Begriffsregel der Karte).
  assert.ok(!/öffentlich/i.test(ohneKommentare(ROLLEN)))
})

// ── T7 · Tokens statt Hartwerte ───────────────────────────────────────────
test('UI-R1 · keine festen Farben, nur Tokens', () => {
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/
  for (const [name, text] of [['RollenEinstellungen.vue', ROLLEN],
    ['GruppenEinstellungen.vue', KARTE],
    ['gruppenEinstellungen.mjs', LOGIK]]) {
    const stil = text.includes('<style') ? text.slice(text.indexOf('<style')) : text
    assert.ok(!farbe.test(stil), `${name}: keine festen Farbwerte`)
  }
})

test('UI-R1 · eigene Abstände/Rahmen nur als Token', () => {
  const abstand = /(margin|padding|gap|row-gap|column-gap|border|border-radius|inset|top|right|bottom|left)[\w-]*\s*:\s*[^;]*\d+(px|rem|em)/g
  for (const [name, text] of [['RollenEinstellungen.vue', ROLLEN],
    ['GruppenEinstellungen.vue', KARTE]]) {
    const stil = text.slice(text.indexOf('<style'))
    const treffer = [...stil.matchAll(abstand)].filter((m) => !m[0].includes('var(--'))
    assert.deepEqual(treffer.map((m) => m[0]), [], `${name}: Maße aus Tokens`)
  }
})

// ── UI-R1b · Kleinigkeiten des zweiten Reviews ────────────────────────────
test('UI-R1b · GL-Suchfeld hat eine sichtbare Beschriftung UND denselben zugänglichen Namen', () => {
  const quelle = ohneKommentare(ROLLEN)
  // `DkField :label="istUntergruppe ? 'Gruppenleitung hinzufügen' : …` — die
  // Beschriftung steht im Markup (nicht nur als `placeholder`/`aria-label`).
  assert.match(quelle, /<DkField[\s\S]{0,200}:label="istUntergruppe \? 'Gruppenleitung hinzufügen'/,
    'die sichtbare Beschriftung des GL-Suchfelds fehlt')
  assert.match(quelle, /<DkField[\s\S]{0,200}<MitgliedAuswahl/,
    'das Suchfeld steht nicht in einem Feld mit Beschriftung')
  // UI-R1c: `MitgliedAuswahl` nimmt die Kennung aus dem Feld-Slot NICHT an
  // (es trägt keine `id` und kein `v-bind="$attrs"`), das `<label for>` zeigt
  // ins Leere — der zugängliche Name war nur der Platzhalter. Das Feld trägt
  // darum denselben Text selbst als `aria-label`.
  // Gesucht wird am GL-Feld (Beschriftung „Gruppenleitung“), nicht am MV-Feld:
  // das MV-Feld hat eine feste `aria-label` und steht weiter oben.
  const glFeld = quelle.slice(quelle.indexOf('Gruppenleitung hinzufügen'))
  const feld = glFeld.match(/<MitgliedAuswahl[\s\S]{0,400}?\/>/)
  assert.ok(feld, 'MitgliedAuswahl im GL-Feld nicht gefunden')
  assert.match(feld[0], /:aria-label="istUntergruppe \? 'Gruppenleitung hinzufügen'/,
    'das GL-Suchfeld hat keinen zugänglichen Namen aus der sichtbaren Beschriftung')
})

test('UI-R1c · MitgliedAuswahl nimmt die Kennung des Feld-Slots nicht an (Grund für das aria-label)', () => {
  const quelle = ohneKommentare(lies('components/MitgliedAuswahl.vue'))
  // Der Kommentar am GL-Feld behauptet: `MitgliedAuswahl` trägt keine `id` und
  // gibt `$attrs` nicht weiter — dann bleibt nur das eigene `aria-label`.
  assert.ok(!/<input[\s\S]{0,400}:id=|\$attrs/.test(quelle),
    'MitgliedAuswahl nimmt inzwischen eine Kennung an — dann ist das aria-label überflüssig')
})

test('UI-R1b · „ändern“ im HV-Dialog ist keine Gefahr', () => {
  const quelle = ohneKommentare(ROLLEN)
  assert.match(quelle, /class="gr-rollen-aendern"[^>]*>ändern</,
    'der Knopf „ändern“ trägt nicht die neutrale Klasse')
  assert.ok(!/class="gr-rollen-entfernen"[^>]*>ändern</.test(quelle),
    'der Knopf „ändern“ trägt weiter die Gefahr-Klasse gr-rollen-entfernen')
})

test('UI-R1b · :key der Rollenzeilen ist eindeutig (Konto bzw. Rolle + Position), nie der Name', () => {
  const quelle = ohneKommentare(ROLLEN)
  for (const alt of [':key="\'hv-\' + e.name"', ':key="\'mv-\' + e.name"', ':key="\'gl-\' + e.name"']) {
    assert.ok(!quelle.includes(alt), `Name als :key (${alt}) — zwei gleiche Namen kollidieren`)
  }
  const schluessel = [...quelle.matchAll(/:key="'(hv|mv|gl)-' \+ schluessel\(e, i\)"/g)].map((m) => m[1])
  assert.deepEqual(schluessel, ['hv', 'mv', 'gl'],
    ':key muss je Zeile Konto bzw. Rolle + Position verwenden')
})

test('UI-R1b · die Erfolgsmeldung nennt den NAMEN der Untergruppe, nicht die Kennung', () => {
  const quelle = ohneKommentare(ROLLEN)
  assert.match(quelle, /leitet jetzt \$\{untergruppeName\(untergruppe\)\}/,
    'die Meldung baut den Namen nicht über untergruppeName()')
  // Der Name kommt notfalls aus `untergruppe_name` der Rollenantwort (auf der
  // Untergruppen-Seite ist `props.untergruppen` leer).
  const fn = quelle.slice(quelle.indexOf('function untergruppeName('))
  assert.match(fn, /untergruppe_name/, 'kein Rückgriff auf untergruppe_name')
})

test('UI-R1b · die Rollenliste lädt je Aktion einmal nach (kein Doppelabruf im Aufbau)', () => {
  const quelle = ohneKommentare(ROLLEN)
  // Genau EIN `laden(` im Aktionsweg, und zwar still.
  assert.match(quelle, /await laden\(\{ still: true \}\)/, 'der stille Nachladeweg fehlt')
  assert.ok(!/await laden\(\)\s*\n\s*emit/.test(quelle),
    'je Aktion wird sichtbar UND über emit neu geladen (Doppelabruf)')
  // Kein zusätzliches Nachladen der Personensuche nach einer Aktion.
  assert.ok(!/mvAuswahl/.test(quelle),
    'die Personensuche wird nach einer Aktion zusätzlich geladen (Ergebnis verworfen)')
})
