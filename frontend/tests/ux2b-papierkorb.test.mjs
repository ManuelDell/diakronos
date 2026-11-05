/**
 * UX2b — Papierkorb im Server: Oberfläche sagt die Wahrheit (7 Tage).
 *
 * Der Server legt Gelöschtes in den Papierkorb und liefert beim Löschen
 * `wiederherstellbar_bis`. Dieser Test prüft das Modul, das die Seiten
 * WIRKLICH benutzen (`src/diakonos/composables/papierkorb.mjs`) — nicht eine
 * Nachbildung:
 *
 *  1. Die Frist wird als deutsches Datum gelesen (auch leer/unbrauchbar).
 *  2. Die Meldung nennt die Frist und behauptet NICHT „gelöscht“.
 *  3. Die Rückfrage sagt nicht mehr „unwiderruflich“ (das wäre falsch).
 *  4. Der Rückgängig-Weg ruft den richtigen Endpunkt je Bereich (POST-Feld).
 *
 * Zusätzlich als Wächter:
 *  - Beiträge und Wiki zeigen keine „unwiderruflich gelöscht“-Meldung mehr.
 *  - Die Papierkorb-Seite ist eine Einstellungsseite mit Adresse (Router +
 *    Abschnittsliste) und nutzt das DkButton/DkTable-System (UIKit, keine
 *    eigenen Farben).
 *
 * Läuft im Docker-Build (`node --test`, backend/Dockerfile).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

import {
  WIEDERHERSTELLEN,
  fristText,
  loeschFrage,
  papierkorbMeldung,
} from '../src/diakonos/composables/papierkorb.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const QUELLE = resolve(HIER, '..', 'src', 'diakonos')

function lies(relativ) {
  return readFileSync(resolve(QUELLE, relativ), 'utf8')
}

// ── 1. Frist lesen ──────────────────────────────────────────────────────────

test('fristText liest das Serverformat als deutsches Datum', () => {
  assert.equal(fristText('2026-11-11 13:30:07'), '11.11.2026')
  assert.equal(fristText('2026-11-11'), '11.11.2026')
})

test('fristText erfindet kein Datum bei fehlender/unsinniger Angabe', () => {
  assert.equal(fristText(''), '')
  assert.equal(fristText(undefined), '')
  assert.equal(fristText('irgendwann'), '')
  // Kein „NaN“ und kein halbes Datum in der Meldung.
  assert.ok(!/NaN/.test(fristText('kaputt')))
})

// ── 2./3. Meldung und Rückfrage ─────────────────────────────────────────────

test('Meldung nennt die Frist und behauptet nicht „gelöscht“', () => {
  const text = papierkorbMeldung('Sommerfest', '2026-11-11 13:30:07')
  assert.match(text, /Sommerfest/)
  assert.match(text, /Papierkorb/)
  assert.match(text, /bis zum 11\.11\.2026/)
  assert.ok(!/gelöscht/i.test(text), text)
})

test('Meldung ohne Frist bleibt ehrlich (kein Datum, kein Fehler)', () => {
  const text = papierkorbMeldung('Sommerfest', '')
  assert.match(text, /Papierkorb/)
  assert.ok(!/bis am|NaN/.test(text), text)
})

test('Löschfrage sagt nicht „unwiderruflich“ und nennt die 7 Tage', () => {
  const frage = loeschFrage('Sommerfest', 'Beitrag')
  assert.match(frage.titel, /löschen\?$/)
  assert.ok(!/unwiderruflich/i.test(frage.text), frage.text)
  assert.match(frage.text, /7 Tage/)
  assert.match(frage.text, /wiederherstellbar/)
  assert.equal(frage.gefahr, true)          // rot: Löschen bleibt gefährlich
  assert.equal(frage.aktion, 'In den Papierkorb')
})

test('Löschfrage ohne Titel benennt den Bereich statt eines leeren „“', () => {
  const frage = loeschFrage('', 'Termin')
  assert.match(frage.text, /Diese Termin/)
})

// ── 4. Rückgängig-Weg ───────────────────────────────────────────────────────

test('jeder der fünf Bereiche hat seinen eigenen Wiederherstellen-Endpunkt', () => {
  const erwartet = {
    beitrag: ['diakronos.diakonos.api.beitraege.wiederherstellen_beitrag', 'beitrag_id'],
    artikel: ['diakronos.diakonos.api.wiki.wiederherstellen_wiki_artikel', 'artikel_id'],
    gruppe: ['diakronos.diakonos.api.gruppen.wiederherstellen_gruppe', 'name'],
    termin: ['diakronos.kronos.api.event_crud.wiederherstellen_event', 'name'],
    lied: ['diakronos.psalmos.api.musik.wiederherstellen_lied', 'lied'],
  }
  for (const [bereich, [pfad, feld]] of Object.entries(erwartet)) {
    assert.ok(WIEDERHERSTELLEN[bereich], bereich)
    assert.equal(WIEDERHERSTELLEN[bereich].pfad, pfad)
    assert.equal(WIEDERHERSTELLEN[bereich].feld, feld)
  }
})

// ── Wächter: keine falsche Zusage mehr in den Seiten ────────────────────────

test('Beiträge und Wiki melden nicht mehr „unwiderruflich gelöscht“', () => {
  for (const datei of ['pages/Beitraege.vue', 'pages/Wiki.vue']) {
    const text = lies(datei)
    assert.ok(!/wird unwiderruflich gelöscht/.test(text), datei)
    assert.match(text, /papierkorb\.mjs/, `${datei}: benutzt das Papierkorb-Modul`)
    assert.match(text, /papierkorbMeldung\(/, datei)
    assert.match(text, /wiederherstellen\(/, `${datei}: Rückgängig-Weg`)
  }
})

test('Termin- und Serien-Meldung sprechen vom Papierkorb', () => {
  const termin = lies('components/kronos/KronosEventEdit.vue')
  assert.match(termin, /papierkorbMeldung\(/)
  const serie = lies('components/kronos/KronosSeriesDialog.vue')
  assert.match(serie, /Papierkorb/)
  assert.match(serie, /wiederherstellbar/)
})

test('Papierkorb-Seite hängt an einer eigenen Einstellungs-Adresse', () => {
  assert.match(lies('router.js'), /'#\/einstellungen\/papierkorb': 'EinstellungenPapierkorb'/)
  const einstellungen = lies('pages/Einstellungen.vue')
  assert.match(einstellungen, /EinstellungenPapierkorb/)
  assert.match(einstellungen, /label: 'Papierkorb'/)
  // Der Menüpunkt führt auf dieselbe Seite (S4: ein Ort je Konzept).
  assert.match(lies('menue.js'), /EinstellungenPapierkorb/)
})

test('Papierkorb-Seite nutzt das Knopf-/Tabellen-System und nur Tokens', () => {
  const seite = lies('pages/einstellungen/Papierkorb.vue')
  assert.match(seite, /DkButton/)
  assert.match(seite, /DkTable/)
  assert.match(seite, /wiederherstellen\(/)
  // CSS-SSOT: keine festen Farbwerte in der Komponente.
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(seite), 'keine Hex-Farbe')
  assert.ok(!/rgb\(/.test(seite), 'kein rgb()')
  // Keine Frist-Neuberechnung in der Oberfläche: die Zahl kommt vom Server.
  assert.match(seite, /aufbewahrung_tage/)
})
