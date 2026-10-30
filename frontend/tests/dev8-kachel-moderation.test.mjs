/**
 * DEV-8 — Startseiten-Kachel „Zu moderierende Termine“ zaehlt das Falsche
 * (Befund DMB-7bee65f6c32b).
 *
 * Der Befund auf der Oberflaeche: die Kachel zeigt eine Zahl (Badge), die
 * Liste darunter und die Moderationsseite bleiben leer. Ursache war der
 * Backend-Zaehler (Ressourcen-Ueberschneidungen statt Vorschlaege) — der ist
 * in `backend/tests/test_dev8_kachel_moderation.py` rot->gruen belegt.
 *
 * Diese Datei haelt die Oberflaechen-Seite fest: die Kachel darf keine EIGENE
 * Zahl erzeugen, die von der Liste abweichen kann. Geprueft wird deshalb:
 *
 *   * Die Kachel holt Daten und Badge ueber `pending-registrations` — also
 *     ueber DENSELBEN Schluessel wie ihr Inhalt (`get_widget_data`), und
 *     zeigt nie eine Zahl aus einer zweiten Quelle (z.B. `get_conflict_events`).
 *   * Sie zaehlt/kuerzt in der Vorschau genauso wie die Liste: `alle` ist die
 *     Antwort des Servers (kein zusaetzlicher Filter, keine eigene Zaehlung
 *     „nur kuenftige“), Rest = alle - VORSCHAU_MAX.
 *   * Der Sprung geht auf die Moderationsseite (`#/moderation`) — dorthin,
 *     wo die gezaehlten Vorschlaege stehen.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const WIDGET = lies('components/widgets/PendingRegistrationsWidget.vue')
const HOME = lies('pages/Home.vue')
const REGISTRY = lies('composables/useWidgetRegistry.js')

test('DEV-8: Kachel laedt Inhalt und Badge ueber denselben Schluessel', () => {
  // Badge-Zahl und Liste muessen aus DERSELBEN Quelle kommen.
  assert.match(WIDGET, /useWidgetData\('pending-registrations'/)
  assert.match(WIDGET, /'pending-registrations'/)
})

test('DEV-8: Kachel fragt keine Ressourcen-Konflikte ab', () => {
  // Der alte Weg (Konflikte als Zahl auf einer Moderationskachel) darf nicht
  // zurueckkommen — sonst zeigt die Kachel wieder eine andere Menge.
  assert.ok(!/get_conflict_events/.test(WIDGET), 'Kachel fragt Konflikte ab')
})

test('DEV-8: die Liste der Kachel ist die Server-Antwort, ungefiltert', () => {
  // `alle` ohne Zeit-/Statusfilter: sonst zaehlt die Kachel anders als die
  // Moderationsseite (die vergangene Vorschlaege ebenfalls zeigt).
  assert.match(WIDGET, /const alle = computed\(\(\) => \(Array\.isArray\(data\.value\) \? data\.value : \[\]\)\)/)
  assert.ok(!/element_start\s*[<>]/.test(WIDGET), 'Kachel filtert nach Zeit')
  assert.ok(!/status\s*===?\s*'Vorschlag'/.test(WIDGET), 'Kachel filtert nach Status')
  // Restzahl ist reine Rechnung aus derselben Liste.
  assert.match(WIDGET, /const rest = computed\(\(\) => Math\.max\(0, alle\.value\.length - VORSCHAU_MAX\)\)/)
})

test('DEV-8: Kachel springt auf die Moderationsseite', () => {
  assert.match(WIDGET, /window\.location\.hash = '#\/moderation'/)
  assert.match(WIDGET, /Zur Terminmoderation/)
})

test('DEV-8: Badge-Zahl kommt von der Startseite, nicht aus der Kachel selbst', () => {
  // Home.vue laedt `get_widget_badge_counts` und reicht `badgeCounts` an den
  // WidgetGrid weiter -> die Kachel selbst rechnet keine Zahl.
  assert.match(HOME, /get_widget_badge_counts/)
  assert.match(HOME, /badge-counts/)
  assert.ok(!/pending-registrations/.test(HOME), 'Home.vue kennt die Kachel nicht einzeln')
})

test('DEV-8: Kachel ist registriert', () => {
  assert.match(REGISTRY, /'pending-registrations': defineAsyncComponent/)
})
