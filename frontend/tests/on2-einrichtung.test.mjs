/**
 * ON-2 — Oberflaechen-Rechnung der Einrichtungs-Karte und des Monogramms.
 *
 * Warum ein eigener Test: die Karte „Einrichtung abschliessen“ (Entwurf Frame
 * 10) und das Monogramm (Frame 04, „Ohne Logo verwendet Diakronos ein
 * Monogramm“) haengen an Regeln, die man im Browser leicht falsch sieht — eine
 * Karte, die nach „Spaeter erinnern“ verschwindet und einen Tag zu frueh wieder
 * auftaucht, faellt niemandem auf. Genauso still waere ein Monogramm, das aus
 * einer leeren Zeichenkette ein leeres Kaestchen macht.
 *
 * Geprueft wird das Modul, das die Komponenten benutzen
 * (`src/diakonos/composables/einrichtung.mjs`) — keine Nachbildung.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  erinnerungAktiv,
  fortschrittAnteil,
  fortschrittText,
  karteZeigen,
  logoQuelle,
  monogramm,
  offenePunkte,
  tagIso,
} from '../src/diakonos/composables/einrichtung.mjs'

/** Ein Status wie ihn `einrichtung.status` liefert (gekuerzt). */
function status(werte = {}) {
  const punkte = werte.punkte || [
    { schluessel: 'gemeindename', erledigt: true, titel: 'Gemeindename gesetzt' },
    { schluessel: 'kontakt', erledigt: true, titel: 'Kontakt hinterlegt' },
    { schluessel: 'module', erledigt: true, titel: 'Module festgelegt' },
    { schluessel: 'kalender', erledigt: true, titel: 'Kalender angelegt' },
    { schluessel: 'logo', erledigt: false, titel: 'Logo' },
    { schluessel: 'mailversand', erledigt: false, titel: 'Mailversand' },
    { schluessel: 'mitglieder', erledigt: false, titel: 'Mitglieder' },
  ]
  const offen = punkte.filter((p) => p.erledigt === false).length
  return {
    assistent_abgeschlossen: true,
    schritte: [],
    punkte,
    offen_anzahl: offen,
    erledigt_anzahl: punkte.length - offen,
    gesamt_anzahl: punkte.length,
    erinnerung_ab: null,
    ...werte,
  }
}

const TAG = new Date(2026, 9, 31) // 31.10.2026 (Entwurfsdatum)

// ── Karte zeigen ────────────────────────────────────────────────────────────

test('Karte erscheint nach abgeschlossenem Assistenten mit offenen Punkten', () => {
  assert.equal(karteZeigen(status(), TAG), true)
})

test('Karte fehlt, solange der Assistent laeuft', () => {
  assert.equal(karteZeigen(status({ assistent_abgeschlossen: false }), TAG), false)
})

test('Karte fehlt, wenn nichts mehr offen ist', () => {
  const alle = status()
  alle.punkte = alle.punkte.map((p) => ({ ...p, erledigt: true }))
  alle.offen_anzahl = 0
  alle.erledigt_anzahl = 7
  assert.equal(karteZeigen(alle, TAG), false)
})

test('Karte fehlt ohne Status (Ladefehler, kein Objekt)', () => {
  assert.equal(karteZeigen(null, TAG), false)
  assert.equal(karteZeigen(undefined, TAG), false)
  assert.equal(karteZeigen({}, TAG), false)
})

test('Spaeter erinnern blendet die Karte bis einschliesslich zum Tag aus', () => {
  const s = status({ erinnerung_ab: '2026-11-07' })
  assert.equal(karteZeigen(s, new Date(2026, 9, 31)), false)
  assert.equal(karteZeigen(s, new Date(2026, 10, 7)), false) // letzter Tag
  assert.equal(karteZeigen(s, new Date(2026, 10, 8)), true) // Tag danach
})

test('erinnerungAktiv rechnet in lokaler Zeit, nicht in UTC', () => {
  // 1. November 2026, 00:30 lokal: in UTC noch der 31.10. — ein Vergleich in
  // UTC wuerde die Erinnerung einen Tag zu frueh beenden.
  const lokalFrueh = new Date(2026, 10, 1, 0, 30)
  assert.equal(tagIso(lokalFrueh), '2026-11-01')
  assert.equal(erinnerungAktiv({ erinnerung_ab: '2026-11-01' }, lokalFrueh), true)
  assert.equal(erinnerungAktiv({ erinnerung_ab: '2026-10-31' }, lokalFrueh), false)
})

test('erinnerungAktiv ohne Datum / mit Unsinn ist false', () => {
  assert.equal(erinnerungAktiv({}, TAG), false)
  assert.equal(erinnerungAktiv({ erinnerung_ab: '' }, TAG), false)
  assert.equal(erinnerungAktiv({ erinnerung_ab: null }, TAG), false)
  assert.equal(erinnerungAktiv(null, TAG), false)
})

// ── Punkte und Fortschritt ──────────────────────────────────────────────────

test('offenePunkte behaelt die Serverreihenfolge (Frame 10)', () => {
  const schluessel = offenePunkte(status()).map((p) => p.schluessel)
  assert.deepEqual(schluessel, ['logo', 'mailversand', 'mitglieder'])
})

test('offenePunkte ist leer, wenn alles erledigt ist, und wirft nie', () => {
  const alle = status()
  alle.punkte = alle.punkte.map((p) => ({ ...p, erledigt: true }))
  assert.deepEqual(offenePunkte(alle), [])
  assert.deepEqual(offenePunkte(null), [])
  assert.deepEqual(offenePunkte({ punkte: 'kaputt' }), [])
})

test('fortschrittText sagt „3 von 7 offen“ und „4 von 7 Punkten erledigt“', () => {
  const s = status()
  assert.equal(fortschrittText(s), '3 von 7 offen')
  // Der zweite Satz des Entwurfs, wenn alles erledigt ist:
  const alle = { ...s, punkte: s.punkte.map((p) => ({ ...p, erledigt: true })) }
  assert.equal(fortschrittText({ ...alle, offen_anzahl: 0, erledigt_anzahl: 7 }),
    '7 von 7 Punkten erledigt')
  assert.equal(fortschrittText(null), '')
  assert.equal(fortschrittText({ gesamt_anzahl: 0 }), '')
})

test('fortschrittAnteil liegt zwischen 0 und 1', () => {
  assert.equal(fortschrittAnteil(status()), 4 / 7)
  assert.equal(fortschrittAnteil({ gesamt_anzahl: 7, erledigt_anzahl: 7 }), 1)
  assert.equal(fortschrittAnteil({ gesamt_anzahl: 0, erledigt_anzahl: 0 }), 0)
  // Zu grosse Werte werden gekappt, keine Balken ueber 100 %.
  assert.equal(fortschrittAnteil({ gesamt_anzahl: 7, erledigt_anzahl: 99 }), 1)
  assert.equal(fortschrittAnteil({ gesamt_anzahl: 7, erledigt_anzahl: -3 }), 0)
})

// ── Monogramm ───────────────────────────────────────────────────────────────

test('Monogramm nimmt den Kurznamen vor dem Gemeindenamen', () => {
  assert.equal(monogramm({ kurzname: 'Musterstadt' }, 'Ev. Gemeinde Musterstadt'), 'M')
  // ``status.gemeindename`` steht vor dem durchgereichten Namen.
  assert.equal(monogramm({ kurzname: '', gemeindename: 'Versöhnungskirche' }, 'X'), 'V')
  assert.equal(monogramm({}, 'Versöhnungskirche Heilbronn'), 'V')
})

test('Monogramm reduziert Umlaute und Akzente auf den Grundbuchstaben', () => {
  assert.equal(monogramm({ kurzname: 'Ökumene' }), 'O')
  assert.equal(monogramm({ kurzname: 'Église' }), 'E')
  assert.equal(monogramm({ kurzname: 'übrig' }), 'U')
})

test('Monogramm ueberspringt fuehrende Satzzeichen und Leerraum', () => {
  assert.equal(monogramm({ kurzname: '  „Gemeinde“' }), 'G')
  assert.equal(monogramm({ kurzname: '   ' }, '  St. Michael'), 'S')
})

test('Monogramm liefert „?“ statt eines leeren Zeichens', () => {
  assert.equal(monogramm({}), '?')
  assert.equal(monogramm(null), '?')
  assert.equal(monogramm({ kurzname: '' }, ''), '?')
})

// ── Logo ────────────────────────────────────────────────────────────────────

test('logoQuelle gibt die Server-Adresse unveraendert zurueck (kein Nachbauen)', () => {
  // Der Server liefert die Adresse MIT Betriebspraefix (WEB-5a) — hier darf
  // kein zweiter Praefix entstehen.
  assert.equal(logoQuelle({ logo_url: '/diakronos/gemeinde/logo', logo_vorhanden: true }),
    '/diakronos/gemeinde/logo')
  assert.equal(logoQuelle({ logo_url: '/gemeinde/logo', logo_vorhanden: true }),
    '/gemeinde/logo')
})

test('logoQuelle reicht das Cache-Busting ?v= unveraendert durch (ON-2b/F8)', () => {
  // Der Server haengt nach jedem Upload einen neuen Kurzhash an. Die Adresse
  // wird NICHT zerlegt oder neu zusammengesetzt — sonst ginge das Busting
  // verloren und der Browser zeigte bis zu 300 s das alte Logo.
  const mitVersion = '/diakronos/gemeinde/logo?v=1a2b3c4d'
  assert.equal(logoQuelle({ logo_url: mitVersion, logo_vorhanden: true }), mitVersion)
})

test('logoQuelle ist null, wenn kein Logo hinterlegt ist', () => {
  assert.equal(logoQuelle({ logo_url: '', logo_vorhanden: false }), null)
  assert.equal(logoQuelle({ logo_vorhanden: false }), null)
  assert.equal(logoQuelle({}), null)
  assert.equal(logoQuelle(null), null)
})

test('das Logo wird nur per <img> eingebunden, nie als Markup (SVG-Schutz)', () => {
  // ON-2b: SVG ist als Logo zugelassen. Die Sicherheit kommt aus der
  // Einbindung — in einem <img> laufen keine Skripte. Würde jemand das Logo
  // per v-html, <object>/<embed> oder als Inline-SVG einbetten, waere das der
  // Weg, auf dem ein hochgeladenes SVG doch ausgefuehrt wird. Dieser Test
  // haelt die Einbindungsart fest.
  for (const datei of [
    '../src/diakonos/components/AppSidebar.vue',
    '../src/diakonos/components/kronos/ModerationSidebar.vue',
  ]) {
    const quelle = readFileSync(new URL(datei, import.meta.url), 'utf8')
    // ON-4/H4: Die Seitenleiste bindet die Marke seit ON-4 über `LogoMarke`
    // ein (Logo ODER Monogramm). Das Logo kommt dabei aus dem Boot-Objekt
    // (`logo_url`, Zeile `logoQuelleMarke`) statt aus `logoUrl`; entscheidend
    // bleibt, dass es überhaupt eingebunden wird und NICHT als Markup.
    const bindetEin = /logoUrl|logo_url|LogoMarke/.test(quelle)
    assert.ok(bindetEin, `${datei} bindet das Logo nicht ein`)
    assert.equal(/v-html[^>]*logo/i.test(quelle), false,
      `${datei} gibt das Logo als Markup aus`)
    assert.equal(/<(object|embed|iframe)[^>]*logo/i.test(quelle), false,
      `${datei} bettet das Logo als Dokument ein`)
  }
  // Die Marken-Komponente selbst: nur `<img :src>` — kein Markup, kein Objekt.
  const marke = readFileSync(
    new URL('../src/diakonos/components/einrichtung/LogoMarke.vue', import.meta.url), 'utf8')
  assert.match(marke, /<img v-if="quelle" :src="quelle"/)
  assert.equal(/v-html/.test(marke), false, 'LogoMarke gibt das Logo als Markup aus')
})

// ── Single Source of Truth fuer die CSS ─────────────────────────────────────

test('das Modul traegt keine Farben, Schriften oder Radien', () => {
  // Vorgabe der Karte: Farben/Schriften/Radien kommen ausschliesslich aus
  // tokens.css. Diese Datei ist reine Logik und darf nichts davon enthalten.
  const quelle = readFileSync(
    new URL('../src/diakonos/composables/einrichtung.mjs', import.meta.url), 'utf8')
  assert.equal(/#[0-9a-f]{3,8}\b/i.test(quelle), false, 'Hex-Farbe gefunden')
  assert.equal(/\brgba?\(/i.test(quelle), false, 'rgb()/rgba() gefunden')
  assert.equal(/\bhsla?\(/i.test(quelle), false, 'hsl()/hsla() gefunden')
  assert.equal(/border-radius|font-family/i.test(quelle), false,
    'Radius/Schriftfamilie gefunden')
})
