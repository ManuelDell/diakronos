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
  // UI-R3: die Seite holt die Verwaltungsliste direkt (`get_kalender_verwaltung`)
  // und überlässt Freigaben, Bearbeiten und Löschen der gemeinsamen Fläche aus
  // UI-R2. UI-R3b: dort stehen `update_kalender` und `delete_kalender` wieder —
  // also ist der Kalender-Weg der Verwaltung vollständig.
  assert.match(seite, /kalender_verwaltung\.get_kalender_verwaltung/)
  assert.match(seite, /KalenderEinstellungen/)
  // UX2c: Löschen ist umkehrbar (der Kalender wird mit denselben Angaben neu
  // angelegt) — also KEINE Rueckfrage, sondern „Rueckgaengig“ am Stapel
  // (Prinzip I2). UI-R3b: der Weg liegt in der gemeinsamen Flaeche
  // (`delete_kalender` + `mitRueckgaengig` in `KalenderEinstellungen.vue`) —
  // es gibt keinen eigenen Kalender-Weg mehr in `useVerwaltung.js`;
  // geprueft in `ux2c-endgueltig.test.mjs`.
  const flaeche = lies('components/gruppen/KalenderEinstellungen.vue')
  assert.match(flaeche, /create_kalender/)
  assert.match(flaeche, /update_kalender/)
  assert.match(flaeche, /delete_kalender/)
  // Die Anfrage-Bauer der Fläche stehen in EINEM reinen Logik-Modul.
  const rechte = lies('components/gruppen/kalenderRechte.mjs')
  assert.match(rechte, /export function aenderungsAnfrage/)
  assert.match(rechte, /export function loeschAnfrage/)
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
  // UX-A2a: die Abfrage liegt im gemeinsamen Composable (eine Abfrage für
  // Seitenleiste UND Mitglieder-Bereichsliste) — die Seitenleiste nutzt sie.
  // UX-A2a2: die Leiste hält auch den gemeinsamen Takt und holt die Zahl nicht
  // mehr selbst (`anfragenZahlLaden` steht nur noch im Composable).
  assert.match(sidebar, /anfragenZaehlerBeobachten/)
  assert.match(lies('composables/useVerwaltung.js'), /navigationZaehler/)
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
