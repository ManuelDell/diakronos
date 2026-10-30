/**
 * DEV-1 · Gruppen: „Neue Gruppe“ in der Listenansicht (Befund DMB-7bc7150a146e)
 * und Gruppen-Filterchips bei nur einem Bereich (Befund DMB-c6f79cf0f5c6).
 *
 * Befund: Die Knöpfe „Neue Gruppe/Untergruppe“ standen in `pages/Gruppen.vue`
 * nur bei `v-if="!embedded"`. Der Rahmen `pages/gruppen/Bereich.vue` bindet die
 * Liste aber eingebettet ein und hatte selbst keinen Knopf — Anlegen war nur
 * über die Ansicht Organigramm möglich.
 *
 * Der Test liest die echten Quelltexte (keine Kopien) und prüft die reine
 * Logik (Bereichs-Zahl, Rechte, Anlege-Aufruf) als Verhalten. Läuft im
 * Docker-Build über den Globb `tests/dev1-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  bereicheAus, anlegenRechte, anlegeAufruf,
} from '../src/diakonos/composables/gruppenAnlegen.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, root), 'utf8')

// ── Rahmen: Knopf im Seitenkopf, gleicher Dialog wie im Organigramm ─────────
test('DEV-1 · Bereichs-Ansicht bietet „Neue Gruppe/Untergruppe“ im Seitenkopf an', () => {
  const bereich = read('pages/gruppen/Bereich.vue')
  assert.match(bereich, /<DkPageHeader[\s\S]*?<template #actions>/,
    'Bereich: der Seitenkopf hat einen Aktionen-Bereich')
  assert.match(bereich, /\+ Neue Gruppe/, 'Bereich: Knopf „Neue Gruppe“')
  assert.match(bereich, /\+ Neue Untergruppe/, 'Bereich: Knopf „Neue Untergruppe“')
  assert.match(bereich, /rechte\.canCreateAny/, 'Bereich: Knopf hängt an den Server-Rechten')
  assert.match(bereich, /rechte\.canCreateGruppe/, 'Bereich: „Neue Gruppe“ hängt am Einzelrecht')
  assert.match(bereich, /rechte\.canCreateUntergruppe/, 'Bereich: „Neue Untergruppe“ hängt am Einzelrecht')
})

test('DEV-1 · der Anlege-Dialog ist derselbe wie im Organigramm (geteilter Baustein)', () => {
  const bereich = read('pages/gruppen/Bereich.vue')
  assert.match(bereich, /components\/gruppen\/GruppeAnlegenDialog\.vue/,
    'Bereich: nutzt den gemeinsamen Anlege-Dialog')
  const liste = read('pages/Gruppen.vue')
  assert.match(liste, /components\/gruppen\/GruppeAnlegenDialog\.vue/,
    'Liste: nutzt denselben Anlege-Dialog')
  const dialog = read('components/gruppen/GruppeAnlegenDialog.vue')
  // Derselbe Serveraufruf wie im Organigramm (OP-ADMIN-6/UXD-R4) — aus EINER
  // Quelle, damit die Feldnamen nicht auseinanderlaufen.
  assert.match(dialog, /anlegeAufruf\(f\.typ, f\)/,
    'Dialog: der Aufruf kommt aus dem gemeinsamen Baustein')
})

test('DEV-1 · Anlege-Aufruf: Methode und Feldnamen wie im Organigramm (UXD-R4)', () => {
  const gruppe = anlegeAufruf('gruppe', { name: ' Chor ', parent: 'Musik' })
  assert.equal(gruppe.methode, 'diakronos.diakonos.api.gruppen.create_gruppe')
  assert.deepEqual(gruppe.parameter, { name: 'Chor', dienstbereich: 'Musik' })

  const untergruppe = anlegeAufruf('untergruppe', { name: 'Band', parent: 'Chor' })
  assert.equal(untergruppe.methode, 'diakronos.diakonos.api.gruppen.create_untergruppe')
  assert.deepEqual(untergruppe.parameter, { name: 'Band', gruppe: 'Chor' })

  const dienstbereich = anlegeAufruf('dienstbereich', { name: 'Musik', farbe: '#112233' })
  assert.equal(dienstbereich.methode, 'diakronos.diakonos.api.gruppen.create_dienstbereich')
  assert.deepEqual(dienstbereich.parameter, { name: 'Musik', farbe: '#112233' })
})

test('DEV-1 · Liste im eingebetteten Modus zeigt den Seitenkopf-Knopf nicht doppelt', () => {
  const liste = read('pages/Gruppen.vue')
  // Der eigene Kopf bleibt an `!embedded` — im Bereich liefert ihn der Rahmen.
  assert.match(liste, /v-if="!embedded"/, 'Liste: eigener Kopf nur ohne Rahmen')
})

test('DEV-1 · Rechte kommen aus derselben Quelle wie im Organigramm', () => {
  const bereich = read('pages/gruppen/Bereich.vue')
  assert.match(bereich, /get_user_create_permissions/,
    'Bereich: Anlege-Rechte über den Server-Aufruf (gleiche Rechte wie Organigramm)')
  assert.match(bereich, /get_gruppen_page_data/,
    'Bereich: Auswahllisten kommen aus den Seitendaten der Liste')
})

test('DEV-1 · nach dem Anlegen wird die eingebettete Liste neu geladen', () => {
  const bereich = read('pages/gruppen/Bereich.vue')
  assert.match(bereich, /@angelegt="nachAnlegen"/, 'Bereich: hört auf das Anlegen-Ereignis')
  const liste = read('pages/Gruppen.vue')
  assert.match(liste, /defineExpose\(\{ reload: loadData \}\)/,
    'Liste: bietet dem Rahmen ein Neuladen an')
})

// ── Filterchips nur bei mehr als einem Bereich (DMB-c6f79cf0f5c6) ──────────
test('DEV-1 · Chips werden ab zwei Bereichen gezeigt, nicht bei einem', () => {
  assert.deepEqual(bereicheAus([{ dienstbereich_name: 'Jugendarbeit' }]), ['Jugendarbeit'])
  assert.deepEqual(bereicheAus([
    { dienstbereich_name: 'Musik' }, { dienstbereich_name: 'Musik' },
    { dienstbereich_name: 'Jugendarbeit' },
  ]), ['Jugendarbeit', 'Musik'])
  // Fehlende Zuordnung zählt als eigener Bereich („Ohne Zuordnung“).
  assert.deepEqual(bereicheAus([{ dienstbereich_name: '' }]), [''])
  assert.deepEqual(bereicheAus([]), [])
})

test('DEV-1 · die Liste blendet die Chip-Zeile bei nur einem Bereich aus', () => {
  const liste = read('pages/Gruppen.vue')
  assert.match(liste, /zeigeMeineChips/, 'Liste: Chip-Zeile „Meine“ hängt an der Bereichszahl')
  assert.match(liste, /zeigeAlleChips/, 'Liste: Chip-Zeile „Alle“ hängt an der Bereichszahl')
  assert.match(liste, /v-if="zeigeMeineChips"/, 'Liste: Zeile „Meine“ ist abschaltbar')
  assert.match(liste, /v-if="zeigeAlleChips"/, 'Liste: Zeile „Alle“ ist abschaltbar')
  assert.match(liste, /bereicheAus/, 'Liste: Bereichszahl kommt aus dem gemeinsamen Baustein')
})

// ── Verhalten: Rechte ──────────────────────────────────────────────────────
test('DEV-1 · Knopf-Zustand folgt den Server-Rechten', () => {
  assert.deepEqual(anlegenRechte(null), {
    canCreateAny: false, canCreateGruppe: false, canCreateUntergruppe: false, canCreateDienstbereich: false,
  })
  assert.deepEqual(
    anlegenRechte({ can_create_gruppe: true, can_create_untergruppe: false }),
    { canCreateAny: true, canCreateGruppe: true, canCreateUntergruppe: false, canCreateDienstbereich: false },
  )
  assert.equal(anlegenRechte({ can_create_dienstbereich: true }).canCreateAny, true)
  // Ein Nutzer ohne jedes Recht sieht keinen Knopf.
  assert.equal(anlegenRechte({ can_create_gruppe: false }).canCreateAny, false)
})

console.log('DEV-1 Gruppen anlegen/Chips: bestanden')
