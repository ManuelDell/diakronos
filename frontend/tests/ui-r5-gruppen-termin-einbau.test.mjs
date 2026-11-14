// UI-R5 — Einbau in GruppeDetail.vue und KronosEventCreate.vue.
//
// Die reinen Regeln stehen in `ui-r5-gruppen-termin.test.mjs`; hier wird
// geprüft, dass die Bauteile sie auch BENUTZEN (sonst wäre die Regel toter
// Code) und dass die Oberfläche keine eigene Rechte-Entscheidung trifft:
//
//   * Der Knopf „+ Termin“ hängt an `darfTermin` (Serverliste), NICHT an
//     `canManage` — auch eine MV ohne Verwaltungsrecht darf Termine
//     vorschlagen, und der Server entscheidet ohnehin.
//   * Die Kalenderliste kommt aus `get_accessible_calendars` (nur dort stehen
//     `direkt`/`pruefstufen`), nicht aus einer zweiten Rechte-Quelle.
//   * Das Formular bekommt die Auswahl der Seite als `kalender-vorgabe` und
//     meldet Erfolg zurück (Liste wird nachgezogen).
//   * Der Prüfhinweis steht im Formular VOR dem Speichern und hängt an
//     `wirdGeprueft` (also an `direkt`).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')
const GRUPPE = lies('../src/diakonos/pages/GruppeDetail.vue')
const FORM = lies('../src/diakonos/components/kronos/KronosEventCreate.vue')
const ohneKommentare = (t) => t.replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

test('UI-R5: der Knopf „+ Termin“ steht an der Karte „Nächste Termine“', () => {
  const t = ohneKommentare(GRUPPE)
  const karte = t.slice(t.indexOf('title="Nächste Termine"'), t.indexOf('<!-- Ankündigungen -->'))
  assert.ok(karte.includes('+ Termin') || karte.includes('aria-label="Termin anlegen"'),
    'Knopf fehlt an der Terminkarte')
  assert.match(karte, /v-if="darfTermin"/, 'Knopf hängt nicht an der Serverliste')
  assert.match(karte, /@click="terminAnlegen"/)
})

test('UI-R5: die Sichtbarkeit kommt aus den Rechten, NICHT aus canManage', () => {
  const t = ohneKommentare(GRUPPE)
  // Der Knopf selbst (nicht die ganze Karte) — die Mitgliederkarte darunter
  // trägt weiterhin `canManage`, das ist ihre eigene Regel.
  const knopf = t.slice(t.indexOf('aria-label="Termin anlegen"') - 300,
    t.indexOf('aria-label="Termin anlegen"'))
  assert.ok(!/canManage/.test(knopf),
    '„+ Termin“ hängt an der Verwaltungsrolle statt an den Kalenderrechten')
})

test('UI-R5: die Kalender dieser Seite kommen aus get_accessible_calendars', () => {
  assert.match(GRUPPE, /get_accessible_calendars/)
  assert.match(GRUPPE, /kalenderDerGruppe\(meineKalender\.value/)
  // Bei einer Untergruppe zählt auch der Kalender der Hauptgruppe.
  assert.match(GRUPPE, /hauptgruppe:\s*untergruppe\.value\?\.gruppe/)
  assert.match(GRUPPE, /istUntergruppe:\s*isUntergruppe\.value/)
})

test('UI-R5b: das Formular bekommt die Kalender der Seite und meldet Erfolg', () => {
  const t = ohneKommentare(GRUPPE)
  // Punkt 3: `terminVorgabeBekannt` steckt schon im `v-if` des Formulars
  // (`darfTermin`), der frühere Ternary war dort IMMER wahr — weggeräumt.
  assert.match(t, /<KronosEventCreate[\s\S]*?:kalender-vorgabe="terminKalender"/)
  assert.ok(!/terminVorgabeBekannt\s*\?\s*terminKalender/.test(t),
    'immer wahrer Ternary steht wieder im Baum')
  // Die Bekannt-Prüfung bleibt am Knopf (siehe `darfTermin`).
  assert.match(GRUPPE, /const terminVorgabeBekannt = computed\(\(\) => meineKalender\.value\.length > 0\)/)
  assert.match(GRUPPE, /const darfTermin = computed\(\(\) => terminVorgabeBekannt\.value/)
  assert.match(t, /<KronosEventCreate[\s\S]*?@created="onTerminAngelegt"/)
  // Nach dem Anlegen werden die nächsten Termine nachgezogen.
  const fn = GRUPPE.slice(GRUPPE.indexOf('function onTerminAngelegt'))
  assert.match(fn.slice(0, 200), /fetchGruppe\(\)/)
})

test('UI-R5: ein Kalender → vorbelegt, mehrere → offen (kein Vorgabewert)', () => {
  const fn = GRUPPE.slice(GRUPPE.indexOf('function terminAnlegen'))
  const rumpf = fn.slice(0, 700)
  assert.match(rumpf, /vorbelegterKalender\(terminKalender\.value\)/)
  // Vorbelegung NUR aus `vorbelegterKalender` — kein festes `element_calendar`.
  assert.ok(!/element_calendar:\s*['"]/.test(rumpf), 'Kalender ist fest verdrahtet')
})

test('UI-R5: der Zeitwert des Formulars kommt in Gemeinde-Ortszeit ohne Anhang', () => {
  // Review 2 (MITTEL): Beginn UND Ende — sonst überspringt `resetForm` den
  // DEV-5-Vorschlag und es entsteht ein Termin ohne Dauer.
  assert.match(GRUPPE, /formularZeitraum\(new Date\(\)\)/)
  const fn = GRUPPE.slice(GRUPPE.indexOf('function terminAnlegen'))
  const rumpf = fn.slice(0, 1400)
  // Der ganze Zeitraum geht ins Formular (Spread), nicht nur ein Zeitpunkt.
  assert.match(rumpf, /\.\.\.zeitraum/)
  // Kein nackter Zeitpunkt mehr (formularZeitpunkt gab nur den Beginn).
  assert.ok(!/formularZeitpunkt/.test(GRUPPE), 'alter Zeitpunkt-Aufruf steht noch da')
})

test('UI-R5: das Formular wird erst beim ersten Klick eingebunden (v-if)', () => {
  // Review 5: dauerhaft eingebunden = 5 Anfragen je Seitenaufruf für jeden,
  // samt Wettlauf „kein Schreibrecht“.
  const t = ohneKommentare(GRUPPE)
  assert.match(t, /<KronosEventCreate\s+v-if="terminFormEingebunden && darfTermin"/)
  assert.match(GRUPPE, /const terminFormEingebunden = ref\(false\)/)
  const fn = GRUPPE.slice(GRUPPE.indexOf('function terminAnlegen'))
  assert.match(fn.slice(0, 900), /terminFormEingebunden\.value = true/)
})

test('UI-R5: die Gruppenkennung ist reaktiv (Router, nicht window.location.hash)', () => {
  // Review 6: `window.location.hash` in einem computed ist keine reaktive
  // Quelle — der Watcher lief ins Leere, die Zuordnung rechnete mit der alten ID.
  const stelle = GRUPPE.slice(GRUPPE.indexOf('const gruppeId = computed'))
  assert.match(stelle.slice(0, 200), /getRouteParam\('id', 'GruppeDetail'\)/)
  assert.ok(!/const gruppeId = computed\(\(\) => \{[^}]*window\.location\.hash/.test(GRUPPE),
    'Kennung liest weiter den Hash (nicht reaktiv)')
})

test('UI-R5b: der Kalenderhinweis steht IM Formular über der Kalenderwahl', () => {
  // Punkt 2: Der Satz „N Kalender … bitte wählen“ stand auf der Gruppenseite
  // HINTER dem Dialog — der Teleport hängt den Dialog ans <body>-Ende, der
  // Satz war dort nicht zu sehen. Er steht jetzt im Formular selbst.
  const gruppe = ohneKommentare(GRUPPE)
  assert.ok(!/dieser Gruppe — bitte im Formular wählen/.test(gruppe),
    'Satz steht weiter auf der Seite hinter dem Dialog')
  assert.ok(!/v-if="showTerminForm && terminKalender\.length > 1"/.test(gruppe),
    'alter Kalenderhinweis der Seite ist noch da')

  const form = ohneKommentare(FORM)
  const hinweis = form.indexOf('data-ui-r5b="kalender-wahl"')
  assert.ok(hinweis > -1, 'Hinweis fehlt im Formular')
  const wahl = form.indexOf('label="Kalender"')
  assert.ok(wahl > -1, 'Kalenderfeld nicht gefunden')
  assert.ok(hinweis < wahl, 'Hinweis steht NACH der Kalenderwahl')
  assert.match(form.slice(hinweis - 200, hinweis), /v-if="kalenderWahlHinweis"/)
  assert.match(form.slice(hinweis - 200, hinweis), /variant="info"/)
  // Gezählt wird ohne Klammerplural, und nur bei MEHREREN Kalendern.
  assert.match(FORM, /zahlWort\(anzahl, 'Kalender', 'Kalender'\)/)
  const regel = FORM.slice(FORM.indexOf('const kalenderWahlHinweis'))
  assert.match(regel.slice(0, 400), /anzahl < 2/)
})

test('UI-R5: der Prüfhinweis steht im Formular vor dem Speichern', () => {
  const t = ohneKommentare(FORM)
  const speichern = t.indexOf('@click="save"')
  const hinweis = t.indexOf('data-ui-r5="pruefhinweis"')
  assert.ok(hinweis > -1, 'Prüfhinweis fehlt')
  assert.ok(hinweis < speichern, 'Prüfhinweis steht NACH dem Speichern-Knopf')
  const umfeld = t.slice(hinweis - 200, speichern)
  assert.match(umfeld, /variant="info"/, 'Hinweis ist kein informativer Hinweis')
  assert.match(umfeld, /v-if="wirdGeprueft"/)
})

test('UI-R5: das Formular benutzt die EINE Prüfregel des Moduls (nicht eine Kopie)', () => {
  const stelle = FORM.slice(FORM.indexOf('const wirdGeprueft'))
  // Review 1 (HOCH) und 6: Keine zweite Bedingung im Bauteil — die Regel steht
  // in gruppenTermin.mjs und ist dort getestet (direkt === false).
  assert.match(stelle.slice(0, 300), /wirdGeprueftRegel\(gewaehlterKalender\.value\)/)
  assert.ok(!/\.direkt\s*!==/.test(ohneKommentare(FORM)),
    'Formular prüft `direkt` selbst statt über das Modul')
  // Und sie kommt wirklich aus dem Modul.
  assert.match(FORM, /wirdGeprueft as wirdGeprueftRegel/)
})

test('UI-R5: Der Prüfhinweis überschreibt die Hinweisfläche NICHT (Abstand am Wrapper)', () => {
  const t = ohneKommentare(FORM)
  const hinweis = t.indexOf('data-ui-r5="pruefhinweis"')
  assert.ok(hinweis > -1)
  // Der Hinweis ist Kind eines Wrappers, nicht selbst die gepolsterte Fläche.
  assert.match(t.slice(hinweis - 400, hinweis), /<div v-if="wirdGeprueft" class="dk-pruefhinweis">\s*<DkHint variant="info"/)
  // Kein `class` mehr AUF DkHint (das überschrieb Polsterung/Hintergrund).
  assert.ok(!/<DkHint[^>]*class="dk-pruefhinweis"/.test(t),
    'Klasse liegt wieder auf DkHint und überschreibt deren Polsterung')
})

test('UI-R5: Erfolgsmeldung kommt aus dem Modul (Stufe statt „(Vorschlag)“)', () => {
  assert.match(FORM, /meldungNachSpeichern\(angelegt, stufenTitel\.value\)/)
  assert.ok(!/\(zu prüfen|\(Vorschlag\)/.test(ohneKommentare(FORM)),
    'Formular baut die Vorschlagsmeldung selbst')
  // Die Stufen-Titel kommen vom Server (get_rollen_erklaerung), nicht aus einer
  // zweiten Wortliste im Frontend.
  assert.match(FORM, /get_rollen_erklaerung/)
  assert.match(FORM, /stufen_titel/)
})

test('UI-R5: das Formular lädt bei Vorgabe die Rechtefelder mit (get_accessible_calendars)', () => {
  assert.match(FORM, /hatVorgabe\.value\s*\?\s*'diakronos\.kronos\.api\.permissions\.get_accessible_calendars'/)
  // Ohne Vorgabe bleibt der bisherige Weg.
  assert.match(FORM, /get_writable_calendars/)
})

test('UI-R5: nur als beschreibbar gemeldete Kalender erscheinen in der Auswahl', () => {
  assert.match(FORM, /props\.kalenderVorgabe\.some\(v => v && v\.name === c\.name\)/)
  assert.match(FORM, /c\.write === true/)
})

test('UI-R5: der Wortlaut des Hinweises steht an EINER Stelle', () => {
  const modul = lies('../src/diakonos/components/gruppen/gruppenTermin.mjs')
  assert.match(modul, /export const PRUEFHINWEIS = 'Der Termin wird vor der Veröffentlichung geprüft\.'/)
  // Kein zweiter Satz dieses Wortlauts im Formular (Kommentare zählen nicht —
  // dort steht die Begründung, nicht die Anzeige).
  assert.ok(!ohneKommentare(FORM).includes('wird vor der Veröffentlichung geprüft'),
    'Formular schreibt den Satz selbst statt ihn aus dem Modul zu nehmen')
})
