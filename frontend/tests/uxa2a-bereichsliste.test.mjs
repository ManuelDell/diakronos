import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

/**
 * UX-A2a — Personen-Navigation (seit UX3j: EINE Reiterzeile statt Seitenliste).
 *
 * Entwurf A2 (Manuel 23.10.) hatte den Reiterstreifen des Bereichs Personen
 * durch EINE feste Liste links neben dem Inhalt ersetzt. UX3j (Entwurf A3,
 * Manuel 08.11.) nimmt das zurück: In ALLEN Reitern steht dieselbe Reiterzeile
 * oben; die Unterbereiche von „Anfragen“ stehen als zweite, kleinere Ebene
 * darunter. Diese Datei prüft, was von UX-A2a weiterhin gilt:
 *
 *  1. die Einträge kommen aus EINER Quelle (menue.js) und tragen echte Ziele,
 *  2. Rechte: ohne Mitgliederadministrator bleibt nur „Liste“ sichtbar —
 *     Admin-Seiten bleiben admin-only (auch für die Unterbereiche),
 *  3. Unterbereiche: eigene Adresse als PFADTEIL (`#/personen/anfragen/<unter>`),
 *     kein zweiter Punkt „Anfragen“ im Reiter, der Hauptbereich führt die Liste,
 *  4. die Kennzahl kommt als QUELLE durch (kein erfundenes 0) und wird NICHT
 *     doppelt abgefragt (gemeinsamer Stand mit der Seitenleiste),
 *  5. alte Adressen leiten weiter (echter Router in der vm),
 *  6. der Rahmen (Personen.vue) hat EINE Reiterzeile und keine Seitenliste,
 *     die Anfragen-Seite keinen zweiten Umschalter und keinen toten Wechsel,
 *  7. Barrierefreiheit: eine Leiste aus Links mit `aria-current` — Farbe ist
 *     nie der einzige Träger; am Handy scrollt die Zeile waagerecht.
 *
 * „Übersicht“ und „Löschanträge“ sind mit A3 KEINE Reiter mehr; ihre Adressen
 * bleiben gültig (Router prüft Fall 5).
 *
 * Die menue.js-Prüfungen laufen gegen das ECHTE Modul (kein Textvergleich),
 * die Router-Prüfungen gegen den echten Router in einer vm.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')
const menuePfad = fileURLToPath(new URL('menue.js', root))

async function menue() {
  // Frischer Import je Fall: die Datei ist importfrei und cachefrei ladbar.
  return import(menuePfad + '?t=' + Math.random().toString(36).slice(2))
}

const ADMIN = { istAdmin: true }
const MITGLIED = { istAdmin: false }

// Vorlage ohne Kommentare (Kommentare nennen dieselben Wörter und hatten den
// Test schon einmal getäuscht).
function vorlageOhneKommentare(quelle) {
  return quelle.slice(0, quelle.indexOf('<script setup>')).replace(/<!--[\s\S]*?-->/g, '')
}

// ── 1. Eine Quelle, echte Ziele, Reihenfolge ────────────────────────────────
{
  const m = await menue()
  const reiter = m.personenReiter({ istAdmin: true, anfragenZahl: 3 })
  assert.deepEqual(
    reiter.map(e => e.label),
    ['Liste', 'Anfragen', 'Datenschutz', 'Import'],
    'die vier Reiter des Entwurfs A3 (Liste ist zugleich die Adressbuch-Sicht)',
  )
  for (const e of reiter) {
    assert.ok(/^#\/personen\//.test(e.href), `${e.label}: eigene Adresse`)
    assert.ok(e.seite, `${e.label}: Seitennamen für die Markierung`)
    assert.equal(e.value, e.id, `${e.label}: Wert ist die Reiter-Kennung`)
  }
  // Die Einträge sind aus MITGLIEDER_REITER abgeleitet — keine zweite Liste.
  assert.deepEqual(
    reiter.map(e => e.href),
    m.sichtbareMitgliederReiter(ADMIN).map(r => r.href),
    'dieselbe Quelle wie sichtbareMitgliederReiter',
  )
  // Kein toter Eintrag: jede Adresse steht in der Routentabelle (Details in
  // Fall 5).
  const router = lies('router.js')
  for (const e of reiter) {
    assert.ok(router.includes(`'${e.href}'`), `${e.href} steht in der Routentabelle`)
  }
  // „Übersicht“ und „Löschanträge“ sind KEINE Reiter mehr (A3).
  for (const id of ['uebersicht', 'loeschantraege']) {
    assert.ok(!reiter.some(e => e.id === id), `„${id}“ ist kein Reiter mehr (A3)`)
  }
}

// ── 2. Rechte: Admin-only bleibt admin-only ─────────────────────────────────
{
  const m = await menue()
  const ohne = m.personenReiter(MITGLIED)
  // UX3b: Ohne Recht bleibt EINE Ansicht — „Liste“. Sie zeigt dann die
  // Adressbuch-Sicht (Kontaktdaten der Gemeinde, dieselbe Zeile); alle
  // Verwaltungsreiter bleiben admin-only.
  assert.deepEqual(ohne.map(e => e.label), ['Liste'],
    'ohne Mitgliederadministrator bleibt die Liste (Adressbuch-Sicht)')
  assert.deepEqual(m.personenAnfragenReiter(MITGLIED), [],
    'ohne Recht auch keine Unterbereiche')
  assert.equal(m.sichtbareAnfragenUnterbereiche(MITGLIED).length, 0,
    'Unterbereiche von Anfragen sind admin-only')

  // Die Rechte-Seite im Router deckt alle Einträge ausser „Liste“ ab.
  const router = lies('router.js')
  const guard = router.slice(router.indexOf('const ADMIN_ONLY_PAGES'))
  for (const seite of ['MitgliederUebersicht', 'MitgliederAnfragen',
    'MitgliederDatenschutz', 'MitgliederLoeschantraege', 'MitgliederImport']) {
    assert.ok(guard.includes(`'${seite}'`), `${seite} bleibt im Rechte-Guard`)
  }
  assert.ok(!guard.includes("'MitgliederListe'"), 'die Liste ist für alle')
}

// ── 3. Unterbereiche: Pfad-Adressen, kein doppelter „Anfragen“ ──────────────
{
  const m = await menue()
  const unter = m.personenAnfragenReiter(ADMIN)

  // UX3j: „Anfragen“ selbst ist der erste Unterbereich (die Liste), darunter
  // „Links & QR-Codes“ und „Formulare“ — kein zweiter Eintrag im Hauptreiter.
  assert.deepEqual(m.ANFRAGEN_UNTERBEREICHE.map(u => u.id), ['anfragen', 'links', 'formulare'],
    'die drei Unterbereiche in EINER Quelle')
  assert.deepEqual(unter.map(u => u.label), ['Anfragen', 'Links & QR-Codes', 'Formulare'])
  // Die Beschriftung „Anfragen“ steht in der zweiten Ebene genau EINMAL.
  assert.equal(unter.filter(u => u.label === 'Anfragen').length, 1,
    'genau ein Eintrag heisst „Anfragen“')

  // Adressen: PFADTEIL, wie die Karte UX3j es vorgibt
  // (`#/personen/<reiter>[/<unter>]`), keine Abfrage mehr.
  assert.equal(m.anfragenUnterbereichHref('anfragen'), '#/personen/anfragen')
  assert.equal(m.anfragenUnterbereichHref('links'), '#/personen/anfragen/links')
  assert.equal(m.anfragenUnterbereichHref('formulare'), '#/personen/anfragen/formulare')
  for (const u of unter) {
    assert.ok(!u.href.includes('?'), `${u.label}: Adresse ohne Abfrageteil`)
    assert.equal(u.href, m.anfragenUnterbereichHref(u.id), `${u.label}: eine Adress-Regel`)
    assert.equal(u.seite, 'MitgliederAnfragen', 'gleiche Seite → gleicher Rechte-Guard')
  }
  // Genau EIN Eintrag ist gewählt: jeder Eintrag hat einen eigenen Wert.
  const werte = unter.map(u => u.value)
  assert.equal(new Set(werte).size, werte.length, 'jeder Eintrag hat einen eigenen Wert')

  // Aus der Adresse zurückgelesen — inklusive Alt-Werten und Schluss-Schrägstrich.
  const faelle = [
    ['#/personen/anfragen', 'anfragen'],
    ['#/personen/anfragen/', 'anfragen'],
    ['#/personen/anfragen/anfragen', 'anfragen'],
    ['#/personen/anfragen/links', 'links'],
    ['#/personen/anfragen/formulare', 'formulare'],
    // unbekannt → Hauptbereich (keine leere Seite über einer getippten Adresse)
    ['#/personen/anfragen/gibtsnicht', 'anfragen'],
    ['#/personen/liste', 'anfragen'],
  ]
  for (const [hash, erwartet] of faelle) {
    assert.equal(m.anfragenUnterbereichAusHash(hash), erwartet, `${hash} → ${erwartet}`)
  }

  // Welcher Reiter gehört zu einer Adresse? (auch Unteradressen)
  const reiterFaelle = [
    ['#/personen/liste', 'liste'],
    ['#/personen/anfragen', 'anfragen'],
    ['#/personen/anfragen/links', 'anfragen'],
    ['#/personen/anfragen/formulare', 'anfragen'],
    ['#/personen/datenschutz', 'datenschutz'],
    ['#/personen/import', 'import'],
    ['#/', null],
    ['#/kalender', null],
    ['', null],
  ]
  for (const [hash, erwartet] of reiterFaelle) {
    assert.equal(m.personenReiterAusHash(hash, ADMIN), erwartet, `${hash} → ${erwartet}`)
  }
}

// ── 4. Kennzahl: Quelle, nie eine erfundene 0, keine doppelte Abfrage ───────
{
  const m = await menue()
  const ohne = m.personenReiter({ istAdmin: true })
  assert.equal(ohne.find(e => e.id === 'anfragen').zahl, null,
    'ohne Serverzahl bleibt der Eintrag ohne Kennzahl')
  const mit = m.personenReiter({ istAdmin: true, anfragenZahl: 7 })
  assert.equal(mit.find(e => e.id === 'anfragen').zahl, 7, 'die Serverzahl wird durchgereicht')
  for (const e of mit) {
    if (e.id !== 'anfragen') assert.equal(e.zahl, null, `${e.label} trägt keine Kennzahl`)
  }
  // Punkt 4 des Reviews: EINE Abfrage, EIN Stand für Seitenleiste und
  // Reiterzeile. Beide lesen den gemeinsamen Zähler aus useVerwaltung.js;
  // der Server wird nur an EINER Stelle gerufen.
  const verwaltung = lies('composables/useVerwaltung.js')
  assert.ok(verwaltung.includes('export const anfragenZaehler'),
    'gemeinsamer Stand in useVerwaltung.js')
  assert.ok(verwaltung.includes('export async function anfragenZahlLaden'),
    'gemeinsame Abfrage in useVerwaltung.js')
  // UX-A2a2: der Endpunkt steht EINMAL als Code — der zweite Treffer ist der
  // Kommentar der Rechte-Prüfung, die dieselbe Rolle wie der Server nennt.
  const endpunktStellen = verwaltung.split('\n')
    .filter(z => z.includes('get_navigation_zaehler') && !/^\s*(\*|\/\/|\/\*)/.test(z))
  assert.equal(endpunktStellen.length, 1,
    'der Server-Endpunkt steht genau einmal im Code der Quelle')
  const sidebar = lies('components/AppSidebar.vue')
  const bereich = lies('pages/Personen.vue')
  // UX-A2a2: die Seitenleiste hält den gemeinsamen Takt
  // (`anfragenZaehlerBeobachten`), der Rahmen LIEST den Stand nur — beide
  // hängen an der gemeinsamen Abfrage, keine fragt selbst.
  for (const [name, quelle] of [['Seitenleiste', sidebar], ['Reiterzeile', bereich]]) {
    assert.ok(quelle.includes('anfragenZaehler'), `${name}: liest den gemeinsamen Stand`)
    assert.ok(!quelle.includes('navigationZaehler()'), `${name}: fragt NICHT selbst`)
  }
  // … aber „Personen“ in der Seitenleiste und „Anfragen“ im Bereich zeigen
  // dieselbe Zahl.
  assert.ok(badgeQuelle(sidebar), 'Seitenleiste hängt an `anfragen`')
  assert.ok(badgeQuelle(bereich), 'Reiterzeile hängt an `anfragen`')
}
function badgeQuelle(quelle) {
  return quelle.includes('anfragenZaehler') || quelle.includes('anfragenZahl')
}

// ── 5. Alte Adressen leiten weiter (echter Router in der vm) ────────────────
function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  // ON-3b: die Leitungsregel (einrichtungLeitung.mjs) wird durch
  // feste Rückgaben ersetzt — dieser Lauf prueft den Router selbst.
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
    ref: value => ({ value }),
    shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  // Die alten Adressen des Bereichs bleiben gültig (Deep-Links, Lesezeichen).
  const weiter = [
    ['#/registrierung', '#/personen/anfragen'],
    ['#/anmeldungen', '#/personen/anfragen'],
    ['#/registrierung?token=abc', '#/personen/anfragen?token=abc'],
    ['#/statistik', '#/personen/uebersicht'],
    // UX3b2: der Bereichsname führt auf die Liste (der Einstieg), nicht mehr
    // auf die Übersicht.
    ['#/mitglieder', '#/personen/liste'],
    // UX3j: Die frühere Unterbereichs-Form mit Abfrageteil leitet auf die
    // PFAD-Adresse (`#/personen/anfragen/<unter>`), Lesezeichen bleiben gültig.
    ['#/personen/anfragen?bereich=links', '#/personen/anfragen/links'],
    ['#/personen/anfragen?bereich=formulare', '#/personen/anfragen/formulare'],
    ['#/personen/anfragen?bereich=anfragen', '#/personen/anfragen'],
  ]
  for (const [alt, neu] of weiter) {
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }
  // Alle neuen Adressen lösen auf — auch die Unterbereichs-Adressen, mit
  // Abfrageteil und Schluss-Schrägstrich.
  const seiten = [
    ['#/personen/uebersicht', 'MitgliederUebersicht'],
    ['#/personen/liste', 'Personen'],  // UX3b: zusammengelegte Personen-Seite
    ['#/personen/anfragen', 'MitgliederAnfragen'],
    ['#/personen/anfragen/anfragen', 'MitgliederAnfragen'],
    ['#/personen/anfragen/links', 'MitgliederAnfragen'],
    ['#/personen/anfragen/formulare', 'MitgliederAnfragen'],
    ['#/personen/anfragen/', 'MitgliederAnfragen'],
    ['#/personen/datenschutz', 'MitgliederDatenschutz'],
    ['#/personen/loeschantraege', 'MitgliederLoeschantraege'],
    ['#/personen/import', 'MitgliederImport'],
  ]
  for (const [hash, seite] of seiten) {
    h.gehe(hash)
    assert.equal(h.router.currentPageName.value, seite, `${hash} → ${seite}`)
  }
  // Der Abfrageteil der Liste bleibt für die Seite lesbar (`?status=`).
  h.gehe('#/personen/liste?status=Mitglied')
  assert.equal(h.router.currentHash.value, '#/personen/liste?status=Mitglied')

  // Nicht-Admin: die Admin-Adressen führen weiterhin aufs Dashboard.
  const g = routerAusfuehren({ is_admin: false, hash: '#/' })
  for (const hash of ['#/personen/anfragen', '#/personen/anfragen/links',
    '#/personen/anfragen/formulare', '#/personen/import', '#/personen/loeschantraege']) {
    g.gehe(hash)
    assert.equal(g.window.location.hash, '#/', `${hash}: ohne Recht zum Dashboard`)
  }
  // …die Liste bleibt erlaubt.
  g.gehe('#/personen/liste')
  assert.equal(g.router.currentPageName.value, 'Personen', 'Liste für alle (UX3b: Personen-Seite)')
}

// ── 6. Rahmen: EINE Reiterzeile oben, keine Seitenliste ─────────────────────
{
  const bereich = lies('pages/Personen.vue')
  const vorlage = vorlageOhneKommentare(bereich)
  const skript = bereich.slice(bereich.indexOf('<script setup>'))

  // Die Reiterzeile steht im Rahmen — als EIN Baustein, in jedem Reiter.
  assert.ok(vorlage.includes('<DkReiter'), 'Reiterzeile im Rahmen')
  assert.ok(!/<DkBereichsliste/.test(vorlage), 'keine seitliche Bereichsliste mehr (A3)')
  assert.ok(!/class="mb-raster"/.test(vorlage), 'kein Zwei-Spalten-Raster mehr (A3)')
  // Die zweite, kleinere Ebene steht direkt darunter (Anfragen-Unterbereiche).
  assert.match(vorlage, /<DkReiter[\s\S]*?<DkReiter[\s\S]*?klein/,
    'zweite Ebene (klein) direkt unter der Reiterzeile')
  // Einträge und Auswahl kommen aus menue.js (eine Quelle).
  assert.ok(skript.includes('personenReiter('), 'Einträge aus menue.js')
  assert.ok(skript.includes('personenAnfragenReiter('), 'Unterbereiche aus menue.js')
  assert.ok(skript.includes('personenReiterAusHash('), 'Reiter aus der Adresse')
  assert.ok(skript.includes('anfragenUnterbereichAusHash('), 'Unterbereich aus der Adresse')

  // In der Vorlage keine Ref-Ausdrücke (N1b-Regel gilt weiter).
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverReiter|aktiverUnterbereich)\.[a-zA-Z_]+/.test(vorlage),
    'kein Eigenschaftszugriff auf Refs in v-if')
  for (const fertig of ['zeigeReiter', 'zeigeUnterreiter', 'zeigeAnlegenKnopf', 'unterbereichHauptaktion']) {
    assert.ok(skript.includes(`${fertig} = computed`), `„${fertig}“ als fertiger Wahrheitswert`)
  }

  // Die Anfragen-Seite: kein eigener Umschalter für die UNTERBEREICHE, kein
  // toter Wechsel — der Unterbereich kommt über die Eigenschaft. Ein
  // DkSegment ist hier erlaubt: das ist der STATUSFILTER der Tabelle
  // (UX3j-Nacharbeit Punkt 1), nicht die Unterbereichs-Wahl.
  const reg = lies('pages/Registrierung.vue')
  const regVorlage = vorlageOhneKommentare(reg)
  const regSkript = reg.slice(reg.indexOf('<script setup>'))
  assert.ok(!/:options="unterReiterOptionen"/.test(regVorlage),
    'kein eigener Unterbereichs-Umschalter mehr')
  assert.ok(!/DkReiter/.test(regVorlage),
    'die Unterbereichs-Reiterzeile zeichnet der Rahmen (DkReiter)')
  assert.ok(regSkript.includes("unterbereich: { type: String, default: '' }"),
    'Unterbereich kommt über die Eigenschaft')
  assert.ok(!regSkript.includes("emit('unterbereich-wechsel'"),
    'kein toter Wechsel mehr (die Reiterzeile ist die Navigation)')
  assert.ok(!regSkript.includes('unterbereichLokal'), 'kein zweiter Speicher für dieselbe Wahl')

  // Das Adress-Ziel der alten Seitennamen lädt denselben Rahmen.
  const ziel = lies('pages/mitglieder/Bereich.vue')
  assert.ok(vorlageOhneKommentare(ziel).includes('<Personen'),
    'Bereich.vue lädt den EINEN Personen-Rahmen')
}

// ── 7. Barrierefreiheit und Handy: EINE Leiste aus Links ───────────────────
{
  const ui = lies('components/ui/DkReiter.vue')
  const uiVorlage = vorlageOhneKommentare(ui)
  // Genau eine Leiste mit Namen; Links für Seiten, Knöpfe nur für Umschalter.
  assert.equal((uiVorlage.match(/<nav\b/g) || []).length, 1, 'genau eine Leiste')
  assert.ok(/<nav[\s\S]*?:aria-label="ariaLabel/.test(uiVorlage), 'Leiste mit Namen')
  assert.ok(uiVorlage.includes(`:aria-current="wert(o) === modelValue ? 'page' : undefined"`),
    'aktiver Eintrag ist aria-current="page"')
  assert.ok(uiVorlage.includes(':aria-pressed='), 'Umschalter tragen aria-pressed')
  // Am Handy scrollt die Zeile waagerecht, nichts bricht um (Punkt 5 der Karte).
  assert.ok(/overflow-x: auto/.test(ui), 'waagerechte Leiste scrollt')
  assert.ok(/white-space: nowrap/.test(ui), 'Einträge werden nicht umgebrochen')
  // Klickfläche aus dem Token (K4: 44 px bei Fingerbedienung).
  assert.ok(/min-height: var\(--control-h\)/.test(ui), 'Klickfläche aus --control-h')
  assert.ok(/@media \(pointer: coarse\)[\s\S]*min-height: 44px/.test(ui), '44 px bei Fingerbedienung')
  // Kennzahl nur als echte Zahl — nie ein leerer oder geratener Punkt.
  const uiSkript = ui.slice(ui.indexOf('<script setup>'), ui.indexOf('<style'))
  assert.ok(uiSkript.includes('Number.isFinite(n)'), 'Kennzahl wird geprüft')
  assert.ok(uiVorlage.includes('v-if="zahl(o) !== null"'), 'Punkt erscheint nur mit Zahl')
  // Keine neuen Farbwerte: nur Tokens.
  const style = ui.slice(ui.indexOf('<style'))
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(style) && !/rgb\(/.test(style),
    'keine festen Farbwerte in der Komponente (nur Tokens)')
}

console.log('UX-A2a/UX3j Personen-Navigation: bestanden')
