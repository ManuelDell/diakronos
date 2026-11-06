import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

/**
 * UX-A2a — Mitglieder: Navigationsliste links statt Reiter.
 *
 * Entwurf A2 (Manuel 23.10.): Der Reiterstreifen des Bereichs Mitglieder wird
 * zu EINER festen Liste links neben dem Inhalt (Desktop) bzw. einer
 * waagerechten Reiterzeile (Handy). „Anfragen“ IST die Anfragenliste (mit der
 * Zahl); darunter stehen eingerückt nur „Links & QR-Codes“ und „Formulare“ —
 * die zweite Reiterzeile entfällt.
 *
 * Geprüft wird:
 *  1. die Einträge kommen aus EINER Quelle (menue.js) und tragen echte Ziele,
 *  2. Rechte: ohne Mitgliederadministrator bleibt nur „Liste“ sichtbar —
 *     Admin-Seiten bleiben admin-only (auch für die Unterbereiche),
 *  3. Unterbereiche: eigene Einträge mit eigener Adresse `?bereich=`, KEIN
 *     doppelter Punkt „Anfragen“; der Hauptpunkt führt die Liste,
 *  4. die Kennzahl kommt als QUELLE durch (kein erfundenes 0) und wird NICHT
 *     doppelt abgefragt (gemeinsamer Stand mit der Seitenleiste),
 *  5. alte Adressen leiten weiter (echter Router in der vm),
 *  6. der Rahmen (Bereich.vue) hat KEINEN Reiterstreifen mehr, die Anfragen-
 *     Seite keine zweite Reiterzeile und keinen toten Wechsel mehr,
 *  7. Barrierefreiheit: NAVIGATION-Muster (nav > ul > Links, aria-current),
 *     KEIN Reiter-Muster (role=tab/tablist/aria-controls/aria-orientation),
 *  8. am Handy wird der aktive Eintrag ins Bild gescrollt (Punkt 2 des
 *     Operator-Reviews).
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
  const eintraege = m.mitgliederBereichEintraege(ADMIN)
  assert.deepEqual(
    eintraege.map(e => e.label),
    ['Liste', 'Anfragen', 'Datenschutz', 'Import'],
    'die vier Reiter des Entwurfs A3 (UX3b: Liste ist zugleich die Adressbuch-Sicht)',
  )
  for (const e of eintraege) {
    assert.ok(/^#\/personen\//.test(e.href), `${e.label}: eigene Adresse`)
    assert.ok(e.seite, `${e.label}: Seitennamen für die Markierung`)
  }
  // Die Einträge sind aus MITGLIEDER_REITER abgeleitet — keine zweite Liste.
  assert.deepEqual(
    eintraege.map(e => e.href),
    m.sichtbareMitgliederReiter(ADMIN).map(r => r.href),
    'dieselbe Quelle wie sichtbareMitgliederReiter',
  )
  // Kein toter Eintrag: jede Adresse löst im Router auf eine Mitglieder-Seite
  // auf (Textprüfung der Routentabelle, Details in Fall 5).
  const router = lies('router.js')
  for (const e of eintraege) {
    assert.ok(router.includes(`'${e.href}'`), `${e.href} steht in der Routentabelle`)
  }
}

// ── 2. Rechte: Admin-only bleibt admin-only ─────────────────────────────────
{
  const m = await menue()
  const ohne = m.mitgliederBereichEintraege(MITGLIED)
  // UX3b: Ohne Recht bleibt EINE Ansicht — „Liste“. Sie zeigt dann die
  // Adressbuch-Sicht (Kontaktdaten der Gemeinde, dieselbe Zeile); alle
  // Verwaltungsreiter bleiben admin-only.
  assert.deepEqual(ohne.map(e => e.label), ['Liste'],
    'ohne Mitgliederadministrator bleibt die Liste (Adressbuch-Sicht)')
  assert.equal(ohne[0].unterpunkte, undefined, 'ohne Recht auch keine Unterbereiche')
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

// ── 3. Unterbereiche: eigene Einträge, kein doppelter „Anfragen“ ────────────
{
  const m = await menue()
  const eintraege = m.mitgliederBereichEintraege(ADMIN)
  const anfragen = eintraege.find(e => e.id === 'anfragen')

  // Entwurf A2 / Review Punkt 3: der Hauptpunkt IST die Anfragenliste, darunter
  // stehen nur „Links & QR-Codes“ und „Formulare“ — kein zweiter Punkt
  // „Anfragen“.
  assert.deepEqual(m.ANFRAGEN_UNTERBEREICHE.map(u => u.id), ['links', 'formulare'],
    'kein doppelter Unterpunkt „Anfragen“ in der Quelle')
  assert.ok(Array.isArray(anfragen.unterpunkte), 'Anfragen hat Unterpunkte')
  assert.deepEqual(
    anfragen.unterpunkte.map(u => u.label),
    ['Links & QR-Codes', 'Formulare'],
  )
  assert.ok(!anfragen.unterpunkte.some(u => u.label === 'Anfragen'),
    'der Hauptpunkt „Anfragen“ erscheint nicht ein zweites Mal eingerückt')
  // Die Beschriftung „Anfragen“ steht genau EINMAL in der ganzen Liste.
  const alleLabels = [
    ...eintraege.map(e => e.label),
    ...eintraege.flatMap(e => (e.unterpunkte || []).map(u => u.label)),
  ]
  assert.equal(alleLabels.filter(l => l === 'Anfragen').length, 1,
    'genau ein Eintrag heisst „Anfragen“')

  assert.deepEqual(
    anfragen.unterpunkte.map(u => u.href),
    ['#/personen/anfragen?bereich=links', '#/personen/anfragen?bereich=formulare'],
    'jeder Unterbereich hat eine eigene, teilbare Adresse',
  )
  // Der Hauptpunkt führt auf die Anfragenliste (dieselbe Seite, erster Bereich).
  assert.equal(anfragen.href, '#/personen/anfragen', 'Hauptpunkt führt auf die Anfragenliste')
  for (const u of anfragen.unterpunkte) {
    assert.equal(u.seite, 'MitgliederAnfragen', 'gleiche Seite → gleicher Rechte-Guard')
  }
  // Die anderen Einträge haben KEINE Unterpunkte (keine zweite Ebene).
  for (const e of eintraege) {
    if (e.id !== 'anfragen') assert.equal(e.unterpunkte, undefined, `${e.label} ohne Unterpunkte`)
  }
  // Genau EIN Eintrag ist gewählt: Ober- und Unterpunkte teilen sich nicht den
  // Wert (im Browser gefunden: alle drei standen als „gewählt“).
  const werte = [anfragen.value, ...anfragen.unterpunkte.map(u => u.value)]
  assert.equal(new Set(werte).size, werte.length, 'jeder Eintrag hat einen eigenen Wert')
  for (const u of anfragen.unterpunkte) {
    assert.equal(u.value, m.unterbereichsWert(u.seite, u.bereich), 'Wert = Seite:Unterbereich')
  }
  assert.equal(anfragen.value, 'MitgliederAnfragen', 'der Oberpunkt trägt den reinen Seitennamen')

  // Aus der Adresse den richtigen Eintrag/Unterbereich bestimmen.
  const faelle = [
    ['#/personen/anfragen', 'anfragen', null],
    ['#/personen/anfragen?bereich=anfragen', 'anfragen', null],
    ['#/personen/anfragen?bereich=links', 'anfragen', 'links'],
    ['#/personen/anfragen?bereich=formulare', 'anfragen', 'formulare'],
    // alte/unbekannte Werte bleiben gültig: der Hauptpunkt trägt die Markierung
    ['#/personen/anfragen?bereich=gibtsnicht', 'anfragen', null],
    ['#/personen/anfragen?x=1', 'anfragen', null],
    ['#/personen/liste?status=Mitglied', 'liste', null],
    ['#/personen/import', 'import', null],
    // UX3b2: „#/personen/adressbuch“ leitet im Router DAUERHAFT auf die Liste
    // um (die alte Adressbuch-Seite ist nicht mehr erreichbar) und ist kein
    // eigener Reiter — die Liste IST die Adressbuch-Sicht ohne Verwaltungsrecht.
    ['#/personen/adressbuch', null, null, 'kein Eintrag (Weiterleitung im Router)'],
  ]
  for (const [hash, id, unter, hinweis] of faelle) {
    const treffer = m.bereichsEintragAusHash(hash, ADMIN)
    if (hinweis === 'kein Eintrag (Weiterleitung im Router)') {
      assert.equal(treffer, null, `${hash}: ${hinweis}`)
      continue
    }
    assert.ok(treffer, `${hash}: Eintrag gefunden`)
    assert.equal(treffer.eintrag.id, id, `${hash} → ${id}`)
    assert.equal(treffer.unterbereich ? treffer.unterbereich.bereich : null, unter,
      `${hash} → Unterbereich ${unter}`)
  }
  // Adressen ausserhalb des Bereichs liefern nichts (kein stiller Treffer).
  for (const hash of ['#/', '#/kalender', '#/mitglied/MT-0001', '']) {
    assert.equal(m.bereichsEintragAusHash(hash, ADMIN), null, `${hash}: kein Bereichstreffer`)
  }
}

// ── 4. Kennzahl: Quelle, nie eine erfundene 0, keine doppelte Abfrage ───────
{
  const m = await menue()
  const ohne = m.mitgliederBereichEintraege({ istAdmin: true })
  assert.equal(ohne.find(e => e.id === 'anfragen').zahl, null,
    'ohne Serverzahl bleibt der Eintrag ohne Kennzahl')
  const mit = m.mitgliederBereichEintraege({ istAdmin: true, anfragenZahl: 7 })
  assert.equal(mit.find(e => e.id === 'anfragen').zahl, 7, 'die Serverzahl wird durchgereicht')
  for (const e of mit) {
    if (e.id !== 'anfragen') assert.equal(e.zahl, null, `${e.label} trägt keine Kennzahl`)
  }
  // Punkt 4 des Reviews: EINE Abfrage, EIN Stand für Seitenleiste und
  // Bereichsliste. Beide lesen den gemeinsamen Zähler aus useVerwaltung.js;
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
  const bereich = lies('pages/mitglieder/Bereich.vue')
  // UX-A2a2: die Seitenleiste hält den gemeinsamen Takt
  // (`anfragenZaehlerBeobachten`), der Bereich LIEST den Stand nur — beide
  // hängen an der gemeinsamen Abfrage, keine fragt selbst.
  for (const [name, quelle] of [['Seitenleiste', sidebar], ['Bereichsliste', bereich]]) {
    assert.ok(quelle.includes('anfragenZaehler'), `${name}: liest den gemeinsamen Stand`)
    assert.ok(!quelle.includes('navigationZaehler()'), `${name}: fragt NICHT selbst`)
  }
  // … aber „Mitglieder“ in der Seitenleiste und „Anfragen“ im Bereich zeigen
  // dieselbe Zahl.
  assert.ok(badgeQuelle(sidebar), 'Seitenleiste hängt an `anfragen`')
  assert.ok(badgeQuelle(bereich), 'Bereichsliste hängt an `anfragen`')
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
    ['#/personen/anfragen?bereich=anfragen', 'MitgliederAnfragen'],
    ['#/personen/anfragen?bereich=links', 'MitgliederAnfragen'],
    ['#/personen/anfragen?bereich=formulare', 'MitgliederAnfragen'],
    ['#/personen/anfragen/', 'MitgliederAnfragen'],
    ['#/personen/datenschutz', 'MitgliederDatenschutz'],
    ['#/personen/loeschantraege', 'MitgliederLoeschantraege'],
    ['#/personen/import', 'MitgliederImport'],
  ]
  for (const [hash, seite] of seiten) {
    h.gehe(hash)
    assert.equal(h.router.currentPageName.value, seite, `${hash} → ${seite}`)
  }
  // Der Abfrageteil bleibt für die Seite lesbar (dort steht `bereich`).
  h.gehe('#/personen/anfragen?bereich=links')
  assert.equal(h.router.currentHash.value, '#/personen/anfragen?bereich=links')

  // Nicht-Admin: die Admin-Adressen führen weiterhin aufs Dashboard.
  const g = routerAusfuehren({ is_admin: false, hash: '#/' })
  for (const hash of ['#/personen/anfragen', '#/personen/anfragen?bereich=links',
    '#/personen/import', '#/personen/loeschantraege']) {
    g.gehe(hash)
    assert.equal(g.window.location.hash, '#/', `${hash}: ohne Recht zum Dashboard`)
  }
  // …die Liste bleibt erlaubt.
  g.gehe('#/personen/liste')
  assert.equal(g.router.currentPageName.value, 'Personen', 'Liste für alle (UX3b: Personen-Seite)')
}

// ── 6. Rahmen: EINE Liste, kein Reiterstreifen, kein toter Wechsel ─────────
{
  const bereich = lies('pages/mitglieder/Bereich.vue')
  const vorlage = vorlageOhneKommentare(bereich)
  const skript = bereich.slice(bereich.indexOf('<script setup>'))

  // Die Liste steht im Rahmen, der Reiterstreifen ist entfallen.
  assert.ok(vorlage.includes('<DkBereichsliste'), 'Bereichsliste im Rahmen')
  assert.ok(!/<DkTabs/.test(bereich), 'kein Reiterstreifen (DkTabs) mehr im Rahmen')
  assert.ok(!/\bDkTabs\b/.test(skript), 'kein DkTabs-Import mehr')
  assert.ok(!skript.includes('reiterWechseln'), 'kein Reiterwechsel mehr')
  // Einträge und Auswahl kommen aus menue.js (eine Quelle).
  assert.ok(skript.includes('mitgliederBereichEintraege('), 'Einträge aus menue.js')
  assert.ok(skript.includes('bereichsEintragAusHash('), 'Auswahl aus der Adresse')

  // In der Vorlage keine Ref-Ausdrücke (N1b-Regel gilt weiter).
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverEintrag|aktiveAuswahl)\.[a-zA-Z_]+/.test(vorlage),
    'kein Eigenschaftszugriff auf Refs in v-if')
  assert.ok(vorlage.includes('zeigeExportKnopf'), 'Export-Knopf über fertigen Wahrheitswert')
  assert.ok(vorlage.includes('zeigtBereichsliste'), 'Liste über fertigen Wahrheitswert')
  assert.match(skript, /aktiverEintrag\.value\?\.id === 'liste'/, 'Export hängt am Eintrag „Liste“')
  assert.match(skript, /aktiverEintrag\.value\?\.id === 'import'/, 'Direkt-Export hängt am Eintrag „Import“')

  // Der Inhalt ist KEIN Reiterbereich mehr (kein tabpanel/aria-controls).
  assert.ok(!/role="tabpanel"/.test(vorlage), 'kein tabpanel im Rahmen')
  assert.ok(!skript.includes('aktiverBereichId'), 'keine tabpanel-Kennung mehr')
  assert.ok(vorlage.includes('role="region"'), 'Inhaltsbereich als benannte Region')

  // Die Anfragen-Seite: keine zweite Reiterzeile im eingebetteten Betrieb,
  // der Unterbereich kommt über die Eigenschaft, der Umschalter bleibt nur
  // ohne Rahmen — und der tote Wechsel ist weg (Punkt 4 des Reviews).
  const reg = lies('pages/Registrierung.vue')
  const regVorlage = vorlageOhneKommentare(reg)
  const regSkript = reg.slice(reg.indexOf('<script setup>'))
  assert.ok(regVorlage.includes('<div v-if="!eingebettet" class="reg-bereich">'),
    'eigener Unterbereichs-Umschalter nur ohne Rahmen')
  assert.ok(regSkript.includes("unterbereich: { type: String, default: '' }"),
    'Unterbereich kommt über die Eigenschaft')
  assert.ok(!regSkript.includes("emit('unterbereich-wechsel'"),
    'kein toter Wechsel mehr (die Bereichsliste ist die Navigation)')
  assert.ok(!regSkript.includes("'unterbereich-wechsel'"), 'auch kein defineEmits dafür')
  assert.ok(regSkript.includes('const eingebettet = computed('), 'eingebettet als Wahrheitswert')

  // Kein zweiter Reiterstreifen über dem Inhalt: an EINER Stelle steht eine
  // Navigation, und das ist die Bereichsliste.
  const ui = lies('components/ui/DkBereichsliste.vue')
  const uiVorlage = vorlageOhneKommentare(ui)
  assert.ok(uiVorlage.includes('class="dk-ui-bereichsliste"'), 'Komponente vorhanden')
  assert.ok(ui.includes("'ArrowRight'") && ui.includes("'ArrowDown'"), 'Pfeiltasten bedienbar')
  assert.ok(ui.includes("'is-aktiv'"), 'aktiver Eintrag wird markiert')
  assert.ok(ui.includes('dk-ui-bz-unter'), 'Unterpunkte eingerückt')
  assert.ok(ui.includes('@media (max-width: 720px)'), 'am Handy waagerechte Reiterzeile')
  // Verweise: `href` aus dem Ziel der Option, NICHT aus dem gewählten Wert.
  assert.ok(ui.includes(':href="ziel(o)"') && ui.includes(':href="ziel(u)"'),
    'Adressen kommen aus `href`')
  // EIN Tabstopp für die ganze Liste (roving tabindex, Einträge sind Links).
  assert.ok(ui.includes(':tabindex="tabStopp('), 'Tabstopp je Eintrag berechnet')
  assert.ok(ui.includes('alleWerte'), 'Tabstopp kennt alle Werte der Liste')
  assert.ok(vorlage.includes('tabindex="0"') || vorlage.includes("tabindex='0'"),
    'der Inhaltsbereich ist über die Tastatur erreichbar')
  // Keine neuen Farbwerte: nur Tokens.
  const style = ui.slice(ui.indexOf('<style'))
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(style) && !/rgb\(/.test(style),
    'keine festen Farbwerte in der Komponente (nur Tokens)')
}

// ── 7. Barrierefreiheit: Navigations-Muster, KEIN Reiter-Muster ─────────────
{
  const ui = lies('components/ui/DkBereichsliste.vue')
  const uiVorlage = vorlageOhneKommentare(ui)
  // Punkt 1 des Reviews: <nav aria-label> → Liste von Links, aktiver Link
  // aria-current="page". Ein Reiter-Muster wäre hier falsch (`aria-orientation`
  // ist bei einer Navigation ungültig, `role="group"`/`li` in einer tablist
  // ebenfalls).
  assert.ok(/<nav[\s\S]*?:aria-label="ariaLabel/.test(uiVorlage), 'Navigation mit Namen')
  assert.ok(/<nav[\s\S]*?<ul[\s\S]*?<a\b/.test(uiVorlage), 'Liste von Links in der Navigation')
  assert.ok(uiVorlage.includes(`:aria-current="istAktiv(o) ? 'page' : undefined"`),
    'aktiver Hauptpunkt ist aria-current="page"')
  assert.ok(uiVorlage.includes(`:aria-current="istAktiv(u) ? 'page' : undefined"`),
    'aktiver Unterpunkt ist aria-current="page"')
  for (const verboten of ['role="tab"', 'role="tablist"', 'role="group"',
    'aria-selected', 'aria-controls', 'aria-orientation']) {
    assert.ok(!uiVorlage.includes(verboten), `${verboten} gehört nicht zum Navigations-Muster`)
  }
  assert.ok(ui.includes('scrollIntoView'), 'Pfeiltasten halten den Fokus im Bild')
  // Die Rolle `navigation` darf höchstens EINMAL vorkommen (keine
  // verschachtelte Navigation).
  assert.equal((uiVorlage.match(/<nav\b/g) || []).length, 1, 'genau eine Navigation')
}

// ── 8. Handy: aktiver Eintrag wird ins Bild gescrollt ──────────────────────
{
  const ui = lies('components/ui/DkBereichsliste.vue')
  // Beim Aufbau und bei jedem Wechsel — mit inline:'nearest', damit die Seite
  // nicht selbst springt (Punkt 2 des Reviews).
  assert.ok(ui.includes(`scrollIntoView({ inline: 'nearest', block: 'nearest' })`),
    'scrollIntoView mit inline:nearest')
  assert.equal((ui.match(/scrollIntoView\(/g) || []).length, 2,
    'beim Aufbau und beim Wechsel')
  assert.ok(/onMounted\(\(\) => \{ nextTick\(aktivenEintragZeigen\) \}\)/.test(ui),
    'beim Laden ins Bild')
  assert.ok(/watch\(\(\) => props\.modelValue, \(\) => \{ nextTick\(aktivenEintragZeigen\) \}\)/.test(ui),
    'beim Wechsel ins Bild')
  assert.ok(ui.includes('merkeEintrag'), 'Einträge werden für das Scrollen gemerkt')
  // Kein Abschneiden: die Zeile scrollt waagerecht, nichts wird umgebrochen.
  assert.ok(/overflow-x: auto/.test(ui), 'waagerechte Leiste scrollt')
  assert.ok(/white-space: nowrap/.test(ui), 'Einträge werden nicht umgebrochen')
}

// ── 9. Kennzahl nur als echte Zahl anzeigen ────────────────────────────────
{
  const ui = lies('components/ui/DkBereichsliste.vue')
  const skript = ui.slice(ui.indexOf('<script setup>'), ui.indexOf('<style'))
  assert.ok(skript.includes('Number.isFinite(n)'), 'Kennzahl wird geprüft')
  assert.ok(skript.includes('return null'), 'keine Kennzahl → nichts anzeigen')
  assert.ok(ui.includes('v-if="zahl(o) !== null"'), 'Punkt erscheint nur mit Zahl')
}

console.log('UX-A2a Mitglieder-Bereichsliste: bestanden')
