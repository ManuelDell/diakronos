/**
 * P2-5 — Wächter: Verwaltungsoberflächen sind verdrahtet und behaupten nichts.
 *
 * Geprüft wird, was in der Nachtprüfung schiefging:
 *   OP-ADMIN-10  Die Kalenderverwaltung ist erreichbar und der Pseudo-Stift weg.
 *   OP-ADMIN-11  Die Ressourcenverwaltung ist erreichbar.
 *   OP-ADMIN-12  Der Knopf „Als Mitglied anzeigen“ ist WEG (er zeigte die
 *                Administrator-Sicht und führte zu falschen Rückschlüssen).
 *   UXD-R18      Die Seitenleiste lädt die Kennzahl vom Server statt einer 0.
 *   UXD-R26      Kein Reiter zeigt mehr einen Platzhaltertext.
 *
 * Die Tests lesen Quelltext (wie die übrigen Wächter dieser Suite) — sie
 * prüfen Verdrahtung, nicht Laufzeitverhalten des Browsers. Das Verhalten
 * belegt die Abnahme am laufenden Stack.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const lies = (rel) => fs.readFileSync(new URL('../src/diakonos/' + rel, import.meta.url), 'utf8')

test('OP-ADMIN-10: Kalenderverwaltung ist als Seite, Route und Menuepunkt verdrahtet', () => {
  const router = lies('router.js')
  assert.match(router, /KalenderVerwaltung: \(\) => import\('\.\/pages\/KalenderVerwaltung\.vue'\)/)
  assert.match(router, /'#\/kalender\/verwalten': 'KalenderVerwaltung'/)
  // Der Kalender-Menuepunkt gilt auch auf der Verwaltungsseite als aktiv.
  assert.match(lies('menue.js'), /'Kalender', 'KalenderImport', 'KalenderVerwaltung'/)

  const seite = lies('pages/KalenderVerwaltung.vue')
  // Rechte kommen vom Server; die Seite ruft die Verwaltungsendpunkte.
  assert.match(seite, /kalenderVerwaltungLaden/)
  assert.match(seite, /kalenderLoeschen/)
  // Loeschen hat eine Rueckfrage (Befund: „Kalender nicht loeschbar“).
  assert.match(seite, /bestaetigen\(/)
})

test('OP-ADMIN-10: das ✎ der Kalenderliste behauptet kein Bearbeiten mehr', () => {
  const sidebar = lies('components/kronos/KronosSidebar.vue')
  assert.doesNotMatch(sidebar, /pencil-icon/)
  assert.match(sidebar, /ksb-recht-hinweis/)
  // Der Weg zur Verwaltung haengt an derselben Rolle wie der Import.
  assert.match(sidebar, /#\/kalender\/verwalten/)
  assert.match(sidebar, /zeigeVerwalten/)
})

test('OP-ADMIN-11: Ressourcenverwaltung ist verdrahtet und bietet Anlegen/Ändern/Löschen', () => {
  const router = lies('router.js')
  assert.match(router, /RessourcenVerwaltung: \(\) => import\('\.\/pages\/RessourcenVerwaltung\.vue'\)/)
  assert.match(router, /'#\/ressourcen\/verwalten': 'RessourcenVerwaltung'/)

  const seite = lies('pages/RessourcenVerwaltung.vue')
  assert.match(seite, /ressourcenVerwaltungLaden/)
  assert.match(seite, /ressourceAnlegen/)
  assert.match(seite, /ressourceAendern/)
  assert.match(seite, /ressourceLoeschen/)
  // „Wartung“ ist der Weg, einen Raum aus der Buchung zu nehmen.
  assert.match(seite, /wartung/)
})

test('OP-ADMIN-12: „Als Mitglied anzeigen“ ist entfernt', () => {
  const detail = lies('pages/MitgliedDetail.vue')
  assert.doesNotMatch(detail, /startImpersonation/)
  assert.doesNotMatch(detail, /Als Mitglied anzeigen/)
  assert.doesNotMatch(detail, /useImpersonation/)
})

test('UXD-R18: die Seitenleiste holt die Kennzahl vom Server', () => {
  const sidebar = lies('components/AppSidebar.vue')
  assert.match(sidebar, /navigationZaehler/)
  // Kein fester Platzhalter mehr.
  assert.doesNotMatch(sidebar, /pendingCount = computed\(\(\) => 0\)/)
})

test('UXD-R26: Mitglied-Detail lädt Gruppen und hat keine Platzhalter-Reiter', () => {
  const detail = lies('pages/MitgliedDetail.vue')
  assert.match(detail, /get_gruppen_for_mitglied/)
  assert.doesNotMatch(detail, /Gruppen-Zugehörigkeit wird hier angezeigt/)
  assert.doesNotMatch(detail, /Dienst-Übersicht wird hier angezeigt/)
  assert.doesNotMatch(detail, /Audit-Log wird hier angezeigt/)
  assert.doesNotMatch(detail, /key: 'historie'/)
  assert.doesNotMatch(detail, /key: 'dienste'/)
})

test('OP-ADMIN-19: Formulare werden geladen, geändert und gelöscht', () => {
  const seite = lies('pages/Registrierung.vue')
  assert.match(seite, /get_anmeldeformular_felder/)
  assert.match(seite, /delete_anmeldeformular/)
  // „Felder“ darf nicht mehr fest „–“ sein, sondern die Zahl zeigen.
  assert.match(seite, /felder_anzahl/)
})
