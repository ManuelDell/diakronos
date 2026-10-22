/**
 * N10 — Abschnitte „Rollen & Rechte“ und „Dev-Modus“ der Seite Einstellungen.
 *
 * Geprüft wird die Verdrahtung:
 *   * beide Abschnitte stehen in `pages/Einstellungen.vue` (mit eigener Adresse),
 *   * der Router kennt die Adressen und schuetzt sie wie die uebrigen
 *     Verwaltungsseiten (Admin-Guard),
 *   * das Menue zaehlt die neuen Seitennamen zum Eintrag „Einstellungen“,
 *   * die Dev-Modus-Seite erscheint nur, wenn die Instanz ihn zulaesst,
 *   * die Rollenuebersicht fasst Verwaltungsrollen zusammen und der Dialog
 *     warnt Nicht-System-Manager.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

test('N10: beide Abschnitte sind als Dateien vorhanden', () => {
  for (const datei of ['pages/einstellungen/RollenRechte.vue', 'pages/einstellungen/DevModus.vue',
                       'composables/useRollenRechte.js']) {
    assert.ok(existsSync(new URL(datei, root)), `Neue Datei vorhanden: ${datei}`)
  }
})

test('N10: Einstellungen bindet beide Abschnitte mit eigener Adresse ein', () => {
  const seite = lies('pages/Einstellungen.vue')
  assert.ok(seite.includes("import('./einstellungen/RollenRechte.vue')"))
  assert.ok(seite.includes("import('./einstellungen/DevModus.vue')"))
  assert.ok(seite.includes("href: '#/einstellungen/rollen'"))
  assert.ok(seite.includes("href: '#/einstellungen/dev-modus'"))
  // Dev-Modus nur, wenn die Instanz ihn zulaesst (Konzept §7).
  assert.ok(seite.includes('nurDevmodus'))
  assert.ok(seite.includes('sichtbareAbschnitte'))
  assert.ok(seite.includes('boot?.devmode') || seite.includes('__DIakonosBOOT') )
})

test('N10: Router kennt die Adressen und schuetzt sie (Admin-Guard)', () => {
  const router = lies('router.js')
  assert.ok(router.includes("'#/einstellungen/rollen':        'EinstellungenRollen'"))
  assert.ok(router.includes("'#/einstellungen/dev-modus':     'EinstellungenDevModus'"))
  assert.ok(router.includes("EinstellungenRollen:    () => import('./pages/Einstellungen.vue')"))
  assert.ok(router.includes("EinstellungenDevModus:  () => import('./pages/Einstellungen.vue')"))
  assert.ok(router.includes("'EinstellungenRollen', 'EinstellungenDevModus'"),
    'beide Seiten stehen im Admin-Guard')
})

test('N10: Menue zaehlt die neuen Seiten zum Eintrag Einstellungen', () => {
  const menue = lies('menue.js')
  assert.ok(menue.includes("'EinstellungenRollen'"))
  assert.ok(menue.includes("'EinstellungenDevModus'"))
})

test('N10: Rollenuebersicht kommt vom Server, zeigt Rollen und warnt bei Verwaltung', () => {
  const seite = lies('pages/einstellungen/RollenRechte.vue')
  assert.ok(seite.includes('rollenUebersicht'))
  assert.ok(seite.includes('rollenSetzen'))
  assert.ok(seite.includes('VerantwortlicheKarte'), 'Verantwortliche je Bereich/Gruppe')
  assert.ok(seite.includes('Dienstbereich'), 'K1: auch Dienstbereiche')
  assert.ok(seite.includes('VERWALTUNGSROLLEN'))
  assert.ok(seite.includes('System Manager'))
})

test('N10: Dev-Modus-Seite laesst keine toten Knoepfe stehen', () => {
  const seite = lies('pages/einstellungen/DevModus.vue')
  // 404/403 heissen „nicht verfuegbar“ -> Hinweis statt Fehler, kein Schalter.
  assert.ok(seite.includes('404') && seite.includes('403'))
  assert.ok(seite.includes('nichtVerfuegbar'))
  // Der Dev-Modus ist eine Server-Einstellung: keinen Umschalter vortaeuschen.
  assert.ok(!seite.includes('devmodusStarten') && !seite.includes('devmodusBeenden'),
    'kein Schalter in der Oberflaeche (Server-Einstellung)')
})

console.log('N10 Einstellungen (Rollen & Rechte + Dev-Modus): bestanden')
