import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

/**
 * UX3a — Neue Navigation: Menü, Umbenennungen, Adressen.
 *
 * Prüft den ECHTEN Code (keine Textsuche):
 *  - menue.js wird in einer vm ausgeführt und liefert die Entwurfs-Struktur A1
 *    (Übersicht · Gemeinde · Planen · Inhalte · Einstellungen im Fuß),
 *  - die früheren Einzelpunkte sind KEINE Menüeinträge mehr,
 *  - die Sichtbarkeit je Rolle (Admin, Gast, Tester, Website-Rollen),
 *  - der echte Router leitet JEDE alte Adresse dauerhaft weiter (Lesezeichen),
 *  - der Einstieg `#/personen` / `#/dienste` löst rollenabhängig auf.
 */

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

/** menue.js ohne Importe in einer vm ausführen (website.mjs wird ersetzt). */
function menueAusfuehren() {
  let source = lies('menue.js')
  // `import { WEBSITE_ROLLEN } from './composables/website.mjs'` ersetzen:
  // der Vertrag (drei Rollen) steht in der Quelle und wird hier fest gesetzt.
  source = source.replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
    "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
  source = source.replace(/^export /gm, '')
  source += `
globalThis.menue = {
  MENUE, FUSS_EINTRAEGE, MENUE_EINTRAEGE, GAST_SEITEN, DIENSTE_REITER,
  LIEDER_REITER, MITGLIEDER_REITER, KALENDER_PRUEF_REITER,
  sichtbareEintraege, sichtbareReiter, sichtbareMitgliederReiter,
  eintragZuSeite, krumenZuSeite, reiterAusHash,
};`
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.menue
}

const M = menueAusfuehren()

/** Werte aus der vm in Host-Arrays kopieren (eigene Prototypkette). */
const liste = a => Array.from(a)

/** Alle Einträge einer Gruppe nach Beschriftung. */
function labels(gruppe) {
  const g = M.MENUE.find(x => x.gruppe === gruppe)
  assert.ok(g, `Gruppe "${gruppe}" fehlt`)
  return liste(g.eintraege).map(e => e.label)
}

// ── Struktur nach Entwurf A1 ────────────────────────────────────────────────
{
  // Gruppen und Reihenfolge — EINE Quelle für Seitenleiste, Mehr-Blatt und
  // Brotkrumen. „Übersicht“ steht allein in der Gruppe ohne Überschrift.
  assert.deepEqual(liste(M.MENUE).map(g => g.gruppe), ['', 'Gemeinde', 'Planen', 'Inhalte'],
    'Gruppenreihenfolge nach Entwurf A1')

  assert.deepEqual(labels(''), ['Übersicht'], 'Übersicht steht allein oben')
  assert.deepEqual(labels('Gemeinde'), ['Personen', 'Gruppen'])
  assert.deepEqual(labels('Planen'), ['Kalender', 'Dienste', 'Ressourcen'])
  assert.deepEqual(labels('Inhalte'), ['Beiträge', 'Wiki', 'Lieder', 'Website'])

  // Einstellungen liegt im Fuß, NICHT in der Gruppenliste.
  assert.deepEqual(liste(M.FUSS_EINTRAEGE).map(e => e.label), ['Einstellungen'])
  assert.ok(!M.MENUE.some(g => g.eintraege.some(e => e.label === 'Einstellungen')),
    'Einstellungen ist kein Gruppenpunkt')

  // Alte Adressen der zusammengelegten Bereiche/Reiter.
  assert.equal(M.MENUE.find(g => g.eintraege.some(e => e.id === 'personen')).eintraege[0].href, '#/personen')
  const planen = M.MENUE.find(g => g.gruppe === 'Planen').eintraege
  assert.equal(planen.find(e => e.id === 'dienste').href, '#/dienste')
  // „Ressourcen“ BLEIBT (Konzept-Entscheidung).
  assert.ok(planen.some(e => e.id === 'ressourcen'), 'Ressourcen bleibt ein Menüpunkt')
}

// ── Frühere Einzelpunkte sind keine Menüeinträge mehr ───────────────────────
{
  const alleLabels = M.MENUE_EINTRAEGE.map(e => e.label)
  for (const alt of ['Adressbuch', 'Dienstplan', 'Pläne', 'Meine Dienste', 'Liedgruppen',
    'Moderation', 'Datenschutz', 'Einrichtung']) {
    assert.ok(!alleLabels.includes(alt), `"${alt}" ist kein eigener Menüpunkt mehr`)
  }
  // Sie leben als Reiter bzw. Ansichten weiter (Meine Dienste → Dienste,
  // Liedgruppen → Lieder). UX3b (Entscheidung Manuel): „Adressbuch“ ist KEIN
  // eigener Reiter mehr — „Personen → Liste“ IST die Adressbuch-Sicht für alle
  // Rollen ohne Verwaltungsrecht. „Datenschutz“ bleibt ein Reiter.
  const personen = M.MITGLIEDER_REITER.map(r => r.label)
  assert.deepEqual([...personen], ['Liste', 'Anfragen', 'Datenschutz', 'Import'],
    'die vier Reiter des Entwurfs A3 (UX3b)')
  assert.ok(!personen.includes('Adressbuch'), 'Adressbuch ist keine eigene Ansicht mehr')
  assert.deepEqual(liste(M.DIENSTE_REITER).map(r => r.label), ['Meine Dienste', 'Dienstpläne', 'Vorlagen'])
  assert.deepEqual(liste(M.LIEDER_REITER).map(r => r.label), ['Lieder', 'Liedgruppen'])
  assert.equal(M.KALENDER_PRUEF_REITER.label, 'Zu prüfen')
  assert.equal(M.KALENDER_PRUEF_REITER.href, '#/kalender/pruefen')
}

// ── Jede Adresse kommt genau einmal vor (kein doppelter Menüpunkt) ──────────
{
  const hrefs = M.MENUE_EINTRAEGE.map(e => e.href)
  assert.equal(new Set(hrefs).size, hrefs.length, 'keine doppelte Menüadresse')
}

// ── Sichtbarkeit je Rolle ───────────────────────────────────────────────────
{
  const planen = M.MENUE.find(g => g.gruppe === 'Planen')
  const gemeinde = M.MENUE.find(g => g.gruppe === 'Gemeinde')
  const inhalte = M.MENUE.find(g => g.gruppe === 'Inhalte')

  // Administrator sieht alles inklusive der rollengeschützten „Website“.
  const adminLabels = [gemeinde, planen, inhalte]
    .flatMap(g => liste(M.sichtbareEintraege(g, { istAdmin: true, rollen: ['System Manager'] })).map(e => e.label))
  for (const pflicht of ['Personen', 'Kalender', 'Dienste', 'Ressourcen', 'Lieder', 'Website']) {
    assert.ok(adminLabels.includes(pflicht), `Admin sieht "${pflicht}"`)
  }

  // Mitglied ohne Admin: kein Eintrag mit rolle 'admin'; „Website“ fail closed
  // ohne passende Rolle.
  const mitgliedRollen = ['Mitglied']
  const ohneWebsite = M.sichtbareEintraege(inhalte, { istAdmin: false, rollen: mitgliedRollen })
  assert.ok(!ohneWebsite.some(e => e.id === 'website'), 'Website ohne Rolle nicht sichtbar')
  assert.ok(ohneWebsite.some(e => e.id === 'lieder'), 'Lieder für Mitglieder sichtbar')

  // Website-Moderator sieht „Website“ (WEB-3-Rollenliste).
  const websiteMod = M.sichtbareEintraege(inhalte, { istAdmin: false, rollen: ['Website-Moderator'] })
  assert.ok(websiteMod.some(e => e.id === 'website'), 'Website-Moderator sieht Website')

  // Fuß „Einstellungen“ ist Verwaltungsarbeit — UI-R10: Stufe
  // `verwaltung: 'personen'` (Administrator ODER Mitgliederverwaltung),
  // seit R-11a nicht mehr „nur Admin“. Der Server prüft zusätzlich.
  assert.equal(M.FUSS_EINTRAEGE[0].verwaltung, 'personen')
  // Vorlagen (Dienste-Reiter) Admin-only, Meine Dienste für alle.
  // UX3c: „Dienstpläne“ hängt am PLANUNGSRECHT (Administration oder
  // Planer-Rolle), nicht an „alle“ — ohne Rechte bleibt der Start-Reiter.
  assert.deepEqual(liste(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: false })).map(r => r.id),
    ['meine-dienste'])
  assert.deepEqual(liste(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: false, darfPlanen: true })).map(r => r.id),
    ['meine-dienste', 'dienstplaene'],
    'Planer ohne Admin sieht den Planungs-Reiter')
  assert.equal(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: true, darfPlanen: true }).length, 3)
  // UX3b: für alle bleibt die Liste (sie zeigt die Adressbuch-Sicht);
  // Anfragen/Datenschutz/Import sind Admin-Reiter.
  assert.deepEqual(liste(M.sichtbareMitgliederReiter({ istAdmin: false })).map(r => r.id),
    ['liste'])

  // Gast (N5/Entwurf A8): nur Start und Kalender — „Dienste“ hat UX3a2
  // wieder entfernt (vor UX3a war der Bereich nicht für Gäste freigegeben).
  const gast = [...liste(M.MENUE).flatMap(g => liste(g.eintraege))]
    .filter(e => M.sichtbareEintraege({ eintraege: [e] }, { istGast: true }).length)
    .map(e => e.id)
    .sort()
  assert.deepEqual(gast, ['dashboard', 'kalender'],
    'Gäste sehen Start und Kalender')
  assert.deepEqual(liste(M.GAST_SEITEN), ['Home', 'Kalender'],
    'GAST_SEITEN ohne Dienste/PlanrahmenDienste')
}

// ── Seitentitel = Menüname (Brotkrumen) ─────────────────────────────────────
{
  assert.equal(M.krumenZuSeite('Personen').join(''), 'Personen')
  assert.equal(M.krumenZuSeite('MitgliederListe').join(''), 'Personen', 'Reiter trägt den Menünamen')
  assert.equal(M.krumenZuSeite('DiensteDienstplaene').join(''), 'Dienste')
  assert.equal(M.krumenZuSeite('Moderation').join(''), 'Kalender', 'Zu prüfen liegt im Kalender')
  assert.equal(M.krumenZuSeite('EinstellungenAnmeldung').join(''), 'Einstellungen')
  assert.equal(M.eintragZuSeite('Einrichtung').eintrag.id, 'einstellungen',
    'Einrichtung ist kein Menüpunkt, sondern Einstellungen')
}

// ── Reiter-Auflösung aus der Adresse ────────────────────────────────────────
{
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/vorlagen'), 'DiensteVorlagen')
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/dienstplaene'), 'DiensteDienstplaene')
  assert.equal(M.reiterAusHash(M.LIEDER_REITER, '#/lieder/gruppen'), 'Liedgruppen')
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/personen/liste'), null)
}

// ── Router: alte Adressen leiten DAUERHAFT weiter ───────────────────────────
function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
    .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
  let hashchange
  const window = {
    location: {
      hash: boot.hash || '#/',
      replace(hash) { this.hash = hash },
    },
    __DIakonosBOOT: boot,
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
  const context = { window, console, setzeFenstertitel() {},
    ref: value => ({ value }), shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}

{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  const erwartet = {
    '#/mitglieder/liste': '#/personen/liste',
    '#/mitglieder/uebersicht': '#/personen/uebersicht',
    '#/mitglieder/anfragen': '#/personen/anfragen',
    '#/adressbuch': '#/personen/liste',
    '#/datenschutz': '#/personen/datenschutz',
    '#/moderation': '#/kalender/pruefen',
    '#/dienstplan': '#/dienste/meine-dienste',
    '#/meine-dienste': '#/dienste/meine-dienste',
    '#/plaene': '#/dienste/dienstplaene',
    '#/planrahmen': '#/dienste/dienstplaene',
    '#/planrahmen/meine-dienste': '#/dienste/meine-dienste',
    '#/planrahmen/einrichten': '#/dienste/vorlagen',
    '#/liedgruppen': '#/lieder/gruppen',
    // UX3a2: alte Lesezeichen MIT Kennung (Tippfehler-Muster aus UX3a).
    '#/liedgruppen/42': '#/lieder/gruppen/42',
  }
  for (const [alt, neu] of Object.entries(erwartet)) {
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }
  // `#/liedergruppen/‹id›` (Tippfehler-Muster aus UX3a) ist eine Weiterleitung
  // auf den Reiter „Lieder → Liedgruppen“ — dieselbe Kennung, saubere Adresse.
  // (Bis UX3c öffnete die Adresse direkt das Detail; nach dem Zusammenlegen
  // beider Muster auf EIN Ziel ist das Ziel selbst die gültige Adresse.)
  const alt = routerAusfuehren({ is_admin: true, hash: '#/liedergruppen/42' })
  assert.equal(alt.window.location.hash, '#/lieder/gruppen/42', 'Weiterleitung mit Kennung')
  const ziel = routerAusfuehren({ is_admin: true, hash: '#/lieder/gruppen/42' })
  assert.equal(ziel.router.currentPageName.value, 'LiedgruppeDetail')
}

// ── UX3a2 F1: `#/liedgruppen/‹id›` behält den Abfrageteil ───────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  h.gehe('#/liedgruppen/42?reiter=noten')
  assert.equal(h.window.location.hash, '#/lieder/gruppen/42?reiter=noten',
    'Abfrage wird wie bei den übrigen Weiterleitungen mitgenommen')
  // Die Zieladresse öffnet die Detailseite der Liedgruppe (kein „nicht gefunden“).
  const ziel = routerAusfuehren({ is_admin: true, hash: '#/lieder/gruppen/42' })
  assert.equal(ziel.router.currentPageName.value, 'LiedgruppeDetail')
}

// ── UX3a2 F2: Kalender-Moderator OHNE Admin erreicht „Zu prüfen“ ────────────
// Das Recht kommt vom Server (`can_moderate`); der Router hält ihn nicht auf
// (wie auf main — dort gab es keinen Admin-Guard für die Moderationsseite).
{
  const moderator = routerAusfuehren({
    is_admin: false,
    mitglied: { status: 'Mitglied' },
    rollen: ['Website-Moderator'],
    can_moderate: true,
    hash: '#/',
  })
  for (const hash of ['#/kalender/pruefen', '#/moderation']) {
    moderator.gehe(hash)
    assert.equal(moderator.router.currentPageName.value, 'Pruefen',
      `${hash} bleibt für Moderatoren ohne Admin erreichbar`)
  }
  // Die alte Adresse wird dauerhaft weitergeleitet, nicht gesperrt.
  moderator.gehe('#/moderation')
  assert.equal(moderator.window.location.hash, '#/kalender/pruefen')
}

// ── UX3a2 F4: Gäste kommen NICHT auf „Dienste“ ──────────────────────────────
{
  const gast = routerAusfuehren({ is_admin: false, mitglied: { status: 'Gast' }, hash: '#/' })
  // Weiterleitung (`location.replace`) und Guard laufen im Browser als Kette
  // (`hashchange` nach jedem Ersetzen) — hier wird sie nachgespielt, bis die
  // Adresse steht.
  const folgeBisStill = (h, max = 5) => {
    for (let i = 0; i < max; i++) {
      const vorher = h.window.location.hash
      h.gehe(vorher)
      if (h.window.location.hash === vorher) return vorher
    }
    return h.window.location.hash
  }
  for (const hash of ['#/dienste', '#/dienste/meine-dienste', '#/planrahmen/meine-dienste']) {
    gast.window.location.hash = hash
    assert.equal(folgeBisStill(gast, 6), '#/', `${hash} → Dashboard (Gast)`)
  }
  // Erlaubt bleiben Start, Kalender und Profil.
  gast.window.location.hash = '#/kalender'
  folgeBisStill(gast)
  assert.equal(gast.router.currentPageName.value, 'Kalender', 'Kalender bleibt offen')
}

// ── Einstiege `#/personen` und `#/dienste` lösen rollenabhängig auf ─────────
// Die Weiterleitung läuft über `location.replace` (ein Lesezeichen wird
// ERSETZT, kein Verlaufseintrag) — im Browser löst das ein zweites
// hashchange aus. Hier wird darum zusätzlich geprüft, dass die Zieladresse
// selbst auf die erwartete Seite auflöst.
{
  const admin = routerAusfuehren({ is_admin: true, hash: '#/personen/liste' })
  assert.equal(admin.router.currentPageName.value, 'Personen')
  // UX3b: Der Einstieg `#/personen` führt BEIDE Rollen auf die Liste — sie
  // zeigt je Rolle die passende Quelle (Admin: Mitgliederliste, sonst
  // Adressbuch-Sicht). Die alte Adresse `#/mitglieder` und die frühere
  // Übersicht bleiben als Lesezeichen erreichbar.
  admin.gehe('#/personen')
  assert.equal(admin.window.location.hash, '#/personen/liste', '#/personen → Liste')
  admin.gehe('#/mitglieder')
  // UX3b2: alle Rollen landen auf der Liste (Entwurf A3: sie ist der Einstieg).
  assert.equal(admin.window.location.hash, '#/personen/liste', 'Admin → Liste (Lesezeichen)')

  const mitglied = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/personen/liste' })
  assert.equal(mitglied.router.currentPageName.value, 'Personen')
  mitglied.gehe('#/mitglieder')
  assert.equal(mitglied.window.location.hash, '#/personen/liste', 'Mitglied → Liste')

  // `#/dienste` öffnet „Meine Dienste“ (Entwurf A2) — für jede Rolle.
  admin.gehe('#/dienste')
  assert.equal(admin.window.location.hash, '#/dienste/meine-dienste')
  const dienste = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/dienste/meine-dienste' })
  assert.equal(dienste.router.currentPageName.value, 'PlanrahmenDienste',
    'Zieladresse öffnet „Meine Dienste“ auch für Mitglieder')
}

// ── Rechte-Guard: Reiter-Adressen bleiben geschützt ─────────────────────────
{
  const ohneRecht = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  // UX3j (A3): Die Reiter-Adressen bleiben geschützt. „Übersicht“ und
  // „Löschanträge“ sind KEINE Reiter mehr — ihre Adressen tragen den
  // Personen-Rahmen (Liste je Rolle), und der Server liefert die Felder.
  for (const hash of ['#/personen/anfragen', '#/personen/datenschutz', '#/personen/import',
    '#/personen/anfragen/links', '#/personen/anfragen/formulare']) {
    ohneRecht.gehe(hash)
    assert.equal(ohneRecht.window.location.hash, '#/', `${hash} ohne Recht → Dashboard`)
  }
  // A3: „Übersicht“ ist kein Reiter mehr — die Adresse bleibt gültig und
  // zeigt den Personen-Rahmen in der Sicht der Rolle (kein Abschieben auf
  // das Dashboard). Geprüft wird der Seitenname, nicht die Adresse: der
  // Router rollt `#/personen` auf `#/personen/liste` weiter.
  ohneRecht.gehe('#/personen/uebersicht')
  assert.notEqual(ohneRecht.window.location.hash, '#/personen/uebersicht',
    'Übersicht ist kein Reiter mehr — die Adresse leitet (A3)')
  // Die Adressbuch-Weiterleitung führt NICHT ins Dashboard: sie zeigt auf den
  // Personen-Rahmen (die Liste ist für alle da).
  ohneRecht.gehe('#/adressbuch')
  assert.notEqual(ohneRecht.window.location.hash, '#/', 'Adressbuch (alle) bleibt offen')
}

console.log('UX3a Navigation: Menü A1, Sichtbarkeit je Rolle und Weiterleitungen: bestanden')
