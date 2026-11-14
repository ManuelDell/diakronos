/**
 * UI-R10 — Menü und Routen: Admin vs. Mitgliederverwaltung.
 *
 * Manuel 11.11.: „Der Admin ist ja der einzige der alles darf“ — die
 * Mitgliederverwaltung ist eine EIGENE Fachverwaltung (Personen, Konten,
 * Registrierung, Datenschutz), kein Vollzugriff. Seit R-11a liefert der Server
 * zwei Flags im Boot-Objekt:
 *
 *   is_admin                  — nur Administrator, root, System Manager
 *   ist_mitgliederverwaltung  — Admin ODER Systemrolle Mitgliederadministrator
 *
 * Geprüft wird der ECHTE Code (keine Textsuche) in einer vm:
 *   1. die Menüdefinition (menue.js) je Rolle: Mitgliederadministrator sieht
 *      Personen · Konten/Registrierung/Datenschutz · Einstellungen, aber nicht
 *      Gemeinde/Einrichtung/Papierkorb/„Gruppe anlegen“,
 *   2. der Administrator sieht alles, ein Mitglied nichts davon,
 *   3. die Handy-Schublade (`handyMenue.mjs`) zeigt dieselbe Sicht,
 *   4. die Routen-Wächter (router.js) halten die richtigen Seiten an,
 *   5. `useSession` ist die EINE Quelle (`istMitgliederverwaltung`).
 */
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

// ── Hilfen ─────────────────────────────────────────────────────────────────

/** menue.js ohne Importe in einer vm ausführen (website.mjs wird ersetzt). */
function menueAusfuehren() {
  let source = lies('menue.js')
  source = source.replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
    "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
  source = source.replace(/^export /gm, '')
  source += `
globalThis.menue = {
  MENUE, FUSS_EINTRAEGE, MITGLIEDER_REITER, ANFRAGEN_UNTERBEREICHE, DIENSTE_REITER,
  sichtbareEintraege, sichtbarerFuss: null, sichtbareReiter,
  sichtbareMitgliederReiter, sichtbareAnfragenUnterbereiche,
  personenReiter, personenAnfragenReiter, personenReiterAusHash,
  verwaltungZutreffend,
};`
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.menue
}

// UI-R10b (Review, Punkt 2): der Router führt keine eigene Fassung der
// Verwaltungsregel mehr — sein Rückfall ist `false` (fail closed). Harnesse,
// die Verwaltungsseiten öffnen, setzen deshalb die ECHTE Regel ein: einmal
// hier aus `menue.js` geholt und für die vm bereitgestellt (über
// `globalThis`, weil der Router-Quelltext pro Aufruf in einer EIGENEN vm läuft —
// eine Variable dieser Testdatei ist dort nicht sichtbar).
globalThis.__verwaltungZutreffend = menueAusfuehren().verwaltungZutreffend

/** handyMenue.mjs mit dem echten menue.js in derselben vm. */
function handyMenueAusfuehren() {
  const menueQuelle = lies('menue.js')
    .replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
      "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
    .replace(/^export /gm, '')
  const handyQuelle = lies('components/handyMenue.mjs')
    .replace(/^import \{[^}]*\} from '\.\.\/menue\.js'$/m, '')
    .replace(/^export /gm, '')
  const source = `${menueQuelle}\n${handyQuelle}\nglobalThis.handy = { schubladeMenue, sichtbarerFuss, sichtbareEintraege, MENUE, FUSS_EINTRAEGE };`
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.handy
}

const ids = (eintraege) => eintraege.map((e) => e.id)
/**
 * Reiter/Seiten-Kennungen als Zeichenkette vergleichen.
 * `deepEqual` taugt hier NICHT: die Listen entstehen in einer vm (eigener
 * Realm), und zwei Arrays aus verschiedenen Realms gelten als ungleich.
 */
const kette = (liste) => [...liste].join(',')

/** Die drei Lagen, um die es in dieser Karte geht. */
const MITGLIEDERVERWALTUNG = { istAdmin: false, istMitgliederverwaltung: true }
const ADMIN = { istAdmin: true, istMitgliederverwaltung: true }
const MITGLIED = { istAdmin: false, istMitgliederverwaltung: false }

// ── 1. Die eine Verwaltungsregel ───────────────────────────────────────────

test('UI-R10: verwaltungZutreffend — Mitgliederverwaltung sieht Personen, nicht Administration', () => {
  const M = menueAusfuehren()
  // 'personen' = Personenbereich: beide Verwaltungsstufen.
  assert.equal(M.verwaltungZutreffend('personen', MITGLIEDERVERWALTUNG), true,
    'Mitgliederverwaltung darf den Personenbereich')
  assert.equal(M.verwaltungZutreffend('personen', ADMIN), true, 'Admin darf alles')
  assert.equal(M.verwaltungZutreffend('personen', MITGLIED), false, 'Mitglied nicht')
  // 'admin' = Vollzugriff: NUR der Administrator.
  assert.equal(M.verwaltungZutreffend('admin', MITGLIEDERVERWALTUNG), false,
    'Mitgliederverwaltung ist kein Administrator')
  assert.equal(M.verwaltungZutreffend('admin', ADMIN), true)
  assert.equal(M.verwaltungZutreffend('admin', MITGLIED), false)
  // Fail closed: fehlende/ungültige Werte zählen nicht.
  assert.equal(M.verwaltungZutreffend('personen', { istAdmin: 'true', istMitgliederverwaltung: 1 }), false)
  assert.equal(M.verwaltungZutreffend('personen', {}), false)
})

// ── 2. Seitenleiste / Menü ─────────────────────────────────────────────────

test('UI-R10: Seitenleiste — Mitgliederverwaltung sieht den Personenbereich, nicht die Administration', () => {
  const M = menueAusfuehren()
  const sichtbar = (rechte) => M.MENUE.flatMap((g) => ids(M.sichtbareEintraege(g, rechte)))

  // Die Hauptpunkte sind für alle Mitglieder dieselben (Personen, Gruppen,
  // Planen, Inhalte) — kein Menüpunkt verschwindet für die Verwaltung.
  assert.equal(kette(sichtbar(MITGLIEDERVERWALTUNG)), kette(sichtbar(MITGLIED)),
    'die Hauptpunkte hängen nicht an der Verwaltungsstufe')

  // Der Fuß („Einstellungen“) ist Verwaltungsarbeit — beide Stufen sehen ihn.
  const fuss = (rechte) => M.FUSS_EINTRAEGE.filter((e) => !e.verwaltung
    || M.verwaltungZutreffend(e.verwaltung, rechte)).map((e) => e.id)
  assert.equal(kette(fuss(MITGLIEDERVERWALTUNG)), 'einstellungen')
  assert.equal(kette(fuss(ADMIN)), 'einstellungen')
  assert.equal(kette(fuss(MITGLIED)), '', 'ein Mitglied sieht keine Einstellungen')
})

test('UI-R10: Personen-Reiter — Anfragen, Datenschutz und Import für die Mitgliederverwaltung', () => {
  const M = menueAusfuehren()
  assert.equal(kette(ids(M.sichtbareMitgliederReiter(MITGLIEDERVERWALTUNG))),
    'liste,anfragen,datenschutz,import',
    'Mitgliederverwaltung sieht alle vier Reiter')
  assert.equal(kette(ids(M.sichtbareMitgliederReiter(ADMIN))),
    'liste,anfragen,datenschutz,import')
  assert.equal(kette(ids(M.sichtbareMitgliederReiter(MITGLIED))), 'liste',
    'ein Mitglied sieht nur die Liste (Adressbuch-Sicht)')
  // Die Anfragen-Unterbereiche (Registrierungslinks und -formulare) ebenso.
  assert.equal(kette(ids(M.sichtbareAnfragenUnterbereiche(MITGLIEDERVERWALTUNG))),
    'anfragen,links,formulare')
  assert.equal(kette(ids(M.sichtbareAnfragenUnterbereiche(MITGLIED))), '')
  // Auch die fertige Reiterzeile der Seite folgt derselben Regel.
  assert.equal(kette(M.personenReiter(MITGLIEDERVERWALTUNG).map((r) => r.id)),
    'liste,anfragen,datenschutz,import')
  assert.equal(M.personenReiter(MITGLIEDERVERWALTUNG)[1].verwaltung, 'personen',
    'der Reiter trägt seine Stufe am Eintrag')
  // Adressen: der Datenschutz-Reiter ist für die Verwaltung erreichbar.
  assert.equal(M.personenReiterAusHash('#/personen/datenschutz', MITGLIEDERVERWALTUNG), 'datenschutz')
  assert.equal(M.personenReiterAusHash('#/personen/datenschutz', MITGLIED), null)
})

test('UI-R10: „Vorlagen“ der Dienste — Administration, „Dienstpläne“ am Planungsrecht', () => {
  const M = menueAusfuehren()
  // Mit Planungsrecht, aber ohne Administration: keine „Vorlagen“.
  assert.equal(kette(ids(M.sichtbareReiter(M.DIENSTE_REITER,
    { ...MITGLIEDERVERWALTUNG, darfPlanen: true }))), 'meine-dienste,dienstplaene',
    'Mitgliederverwaltung legt keine Vorlagen an')
  assert.equal(kette(ids(M.sichtbareReiter(M.DIENSTE_REITER, { ...ADMIN, darfPlanen: true }))),
    'meine-dienste,dienstplaene,vorlagen', 'der Administrator sieht alle drei')
})

// ── 3. „Gruppe anlegen“ (Gruppen-Seite) ────────────────────────────────────

test('UI-R10: „Alle Gruppen“ und „Gruppe anlegen“ bleiben beim Administrator', () => {
  // Der Server nimmt nur den Kern-Admin an (`gruppen.py::create_gruppe` →
  // `_is_admin()`): `get_gruppen_page_data` füllt `andere_gruppen` und
  // `create_permissions.can_create_gruppe` nur für ihn — die Seite ist damit
  // unverändert richtig, sie liest den Serverwert (`data.is_admin`).
  const gruppen = lies('pages/Gruppen.vue')
  assert.match(gruppen, /isAdmin\.value = data\?\.is_admin \|\| false/,
    '„Alle Gruppen“ kommt aus der Server-Antwort, nicht aus dem Boot')
  assert.match(gruppen, /v-if="isAdmin && alleGruppenFlach\.length > 0"/,
    'der Abschnitt „Alle Gruppen“ hängt an diesem Serverwert')
})

// ── 4. Handy-Schublade: dieselbe Sicht ─────────────────────────────────────

test('UI-R10: Handy-Schublade zeigt dieselbe Sicht wie die Seitenleiste', () => {
  const H = handyMenueAusfuehren()
  const eintraege = (rechte) => H.schubladeMenue(rechte)
    .flatMap((g) => g.eintraege.map((e) => e.id))
  assert.equal(kette(eintraege(MITGLIEDERVERWALTUNG)), kette(eintraege(MITGLIED)),
    'die Hauptpunkte sind für die Verwaltung unverändert')
  assert.equal(kette(H.sichtbarerFuss(MITGLIEDERVERWALTUNG).map((e) => e.id)), 'einstellungen',
    'die Mitgliederverwaltung kommt am Handy zu den Einstellungen')
  assert.equal(kette(H.sichtbarerFuss(MITGLIED)), '')
  assert.equal(kette(H.sichtbarerFuss(ADMIN).map((e) => e.id)), 'einstellungen')
})

// ── 5. Routen-Wächter ──────────────────────────────────────────────────────

/**
 * router.js in einer vm ausführen und die Zahl der Weiterleitungen auf das
 * Dashboard zählen. Die Importe werden durch feste Attrappen ersetzt (wie in
 * den bestehenden Router-Tests); `window` ist ein Stub mit dem Boot-Objekt.
 */
function routerMitBoot(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
  // Die vm führt klassisches Skript aus — `export` gibt es dort nicht.
  source = source.replace(/^export \{([^}]*)\}$/gm, '')
  source = source.replace(/^export /gm, '')
  // Attrappen für die Importe (die Testdatei setzt sie vorher global).
  source = `
const ref = globalThis.__vue.ref
const computed = globalThis.__vue.computed
const shallowRef = globalThis.__vue.shallowRef
const verwaltungZutreffend = globalThis.__regel
const setzeFenstertitel = () => {}
const darfWebsite = () => true
const fehlertext = (e) => String(e)
const einrichtungLeitung = {
  EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
  einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
  einrichtungGesehen: () => false,
}

${source}
globalThis.router = { verwaltungsStufeSeite, ADMIN_ONLY_PAGES, PERSONEN_VERWALTUNG_PAGES };
`
  const weiter = []
  const windowStub = {
    __DIakonosBOOT: boot,
    location: { hash: '#/' },
    addEventListener: () => {},
    matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
    history: { replaceState: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  }
  const context = {
    console,
    window: windowStub,
    document: { title: '', addEventListener: () => {}, querySelector: () => null },
    location: windowStub.location,
    history: windowStub.history,
    sessionStorage: windowStub.sessionStorage,
    localStorage: windowStub.localStorage,
    navigator: { language: 'de-DE' },
    setTimeout, clearTimeout, setInterval, clearInterval,
    __vue: { ref: (v) => ({ value: v }), computed: (fn) => ({ get value() { return fn() } }), shallowRef: (v) => ({ value: v }) },
    __weiter: weiter,
    __regel: globalThis.__verwaltungZutreffend,
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  // R10-Review (Punkt 5): die Wächter-ENTSCHEIDUNG prüfen, nicht nur die
  // Zuordnung. `beforeEachGuards` liegt im Modul-Scope — über den gesammelten
  // Stand lassen sich die Wächter einzeln befragen, genau wie `resolveRoute`
  // es tut (`guard({ to, name, params })`, `false` = Routenwechsel abgebrochen).
  context.__guards = []
  vm.runInContext('globalThis.__guards = beforeEachGuards.slice()', context)
  context.router = {
    verwaltungsStufeSeite: context.verwaltungsStufeSeite,
    verwaltungErlaubt: context.verwaltungErlaubt,
    ADMIN_ONLY_PAGES: context.ADMIN_ONLY_PAGES,
    PERSONEN_VERWALTUNG_PAGES: context.PERSONEN_VERWALTUNG_PAGES,
    /** Ergebnis ALLER Wächter für eine Seite: `true` = Seite wird geöffnet. */
    oeffnet(name, hash = '#/irgendwas') {
      for (const guard of context.__guards) {
        const r = guard({ to: hash, name, params: {} })
        if (r === false) return false
      }
      return true
    },
    /** Wie oft `navigate('#/')` gerufen wurde (= Umleitung aufs Dashboard). */
    umleitungen: context.__umleitungen,
  }
  return context
}


// ── 5. Routen-Wächter: die ENTSCHEIDUNG je Rolle ──────────────────────────
//
// R10-Review (Punkt 2/5): die Zuordnung (Stufe) allein sagt nichts darüber,
// wer die Seite am Ende öffnet — genau dort lagen beide Fehler (Vorlagen im
// Personen-Wächter, Datenschutz-Texte in der Personen-Sicht). Geprüft wird
// deshalb der Wächter SELBST: `oeffnet(seite, rolle)` führt alle Wächter aus
// und sagt, ob die Seite geladen wird.

const SEITEN = {
  // Personenbereich — der Server lässt die Mitgliederverwaltung hier zu.
  personen: [
    'MitgliederUebersicht', 'MitgliederAnfragen', 'MitgliederDatenschutz',
    'MitgliederImport', 'MitgliederLoeschantraege', 'Registrierung',
    'Einstellungen', 'EinstellungenAnmeldung',
  ],
  // Administration — der Server nimmt nur den Kern-Admin an (403 sonst).
  admin: [
    'EinstellungenGemeinde', 'EinstellungenRollen', 'EinstellungenDatensicherung',
    'EinstellungenMailversand', 'EinstellungenWebsite', 'EinstellungenGestaltung',
    'EinstellungenDevModus', 'EinstellungenPapierkorb', 'Einrichtung',
    // R10-Review (Punkt 1 und 2): Datenschutz-TEXTE (`gemeinde._angemeldeter_admin`)
    // und die Dienste-Vorlagen (Menü `rolle: 'admin'`).
    'EinstellungenDatenschutz', 'DiensteVorlagen', 'PlanrahmenEinrichten',
    // LIVE-Befund im Wegwerf-Stack: der Abschnitt „Registrierung“ hängt
    // vollständig am Kern-Admin — er liest `gemeinde_get_einstellungen` und
    // speichert über `gemeinde_setze_linkvorgaben` (beide
    // `gemeinde._angemeldeter_admin`), also 403 für die Verwaltung.
    'EinstellungenRegistrierung',
  ],
}

for (const stufe of ['personen', 'admin']) {
  test(`UI-R10: Wächter — Zuordnung der ${stufe === 'admin' ? 'Administrations' : 'Personen'}-Seiten`, () => {
    const ctx = routerMitBoot({})
    for (const seite of SEITEN[stufe]) {
      assert.equal(ctx.router.verwaltungsStufeSeite(seite), stufe, `${seite} → Stufe ${stufe}`)
    }
  })
}

test('UI-R10: Wächter — Mitgliederverwaltung öffnet Personen-Seiten, nicht die Administration', () => {
  const ctx = routerMitBoot({ is_admin: false, ist_mitgliederverwaltung: true })
  for (const seite of SEITEN.personen) {
    assert.equal(ctx.router.oeffnet(seite), true, `Mitgliederverwaltung öffnet ${seite}`)
  }
  for (const seite of SEITEN.admin) {
    assert.equal(ctx.router.oeffnet(seite), false,
      `Mitgliederverwaltung wird von ${seite} aufs Dashboard geführt`)
  }
})

test('UI-R10: Wächter — Administrator öffnet alles', () => {
  const ctx = routerMitBoot({ is_admin: true, ist_mitgliederverwaltung: true })
  for (const seite of [...SEITEN.personen, ...SEITEN.admin]) {
    assert.equal(ctx.router.oeffnet(seite), true, `Administrator öffnet ${seite}`)
  }
})

test('UI-R10: Wächter — Mitglied öffnet keine der Verwaltungsseiten', () => {
  const ctx = routerMitBoot({ is_admin: false, ist_mitgliederverwaltung: false, mitglied: { status: 'Mitglied' } })
  for (const seite of [...SEITEN.personen, ...SEITEN.admin]) {
    assert.equal(ctx.router.oeffnet(seite), false, `Mitglied wird von ${seite} aufs Dashboard geführt`)
  }
})

test('UI-R10: Wächter — alter Server ohne `ist_mitgliederverwaltung` bleibt fail closed', () => {
  // Nur der Personenbereich fällt auf `is_admin` zurück (wie bisher); ein
  // Mitgliederadministrator-Konto ohne das neue Feld sieht dort nichts.
  const ohneFeld = routerMitBoot({ is_admin: false })
  assert.equal(ohneFeld.router.oeffnet('MitgliederUebersicht'), false)
  const adminOhneFeld = routerMitBoot({ is_admin: true })
  assert.equal(adminOhneFeld.router.oeffnet('MitgliederUebersicht'), true,
    'der Kern-Admin kommt auch ohne das neue Feld hinein')
  assert.equal(adminOhneFeld.router.oeffnet('EinstellungenDatenschutz'), true)
})

test('UI-R10: Wächter — keine Verwaltungsstufe für Kalender, Dienstpläne und Planübersicht', () => {
  const ctx = routerMitBoot({})
  for (const seite of ['Kalender', 'KalenderVerwaltung', 'KalenderImport', 'Pruefen',
    'DiensteDienstplaene', 'PlanrahmenUebersicht', 'Personen', 'Home', 'Profile']) {
    assert.equal(ctx.router.verwaltungsStufeSeite(seite), null,
      `${seite} bleibt ohne Verwaltungs-Wächter`)
  }
})

// ── 6. Einstellungen: sichtbare Abschnitte je Rolle ────────────────────────
//
// R10-Review (Punkt 5): nicht nur die Route, sondern der Rahmen der
// Einstellungen muss je Rolle die richtigen Abschnitte zeigen. Die Liste steht
// als `abschnitte` in `pages/Einstellungen.vue`; gelesen wird sie über die
// echten `verwaltung`-Stufen und die EINE Regel aus `menue.js`.

/** Die `verwaltung`-Stufe je Abschnitts-Kennung aus `pages/Einstellungen.vue`. */
function einstellungsAbschnitte() {
  const quelle = lies('pages/Einstellungen.vue')
  const liste = quelle.slice(quelle.indexOf('const abschnitte = ['))
  const ergebnis = {}
  for (const m of liste.matchAll(/id: '([^']+)'[\s\S]{0,400}?verwaltung: '([^']+)'/g)) {
    ergebnis[m[1]] = m[2]
  }
  return ergebnis
}

test('UI-R10: Einstellungen — Mitgliederverwaltung sieht nur die Anmeldung', () => {
  const M = menueAusfuehren()
  const abschnitte = einstellungsAbschnitte()
  const sichtbar = (rechte) => Object.entries(abschnitte)
    .filter(([, stufe]) => M.verwaltungZutreffend(stufe, rechte))
    .map(([id]) => id)
  assert.equal(kette(sichtbar(MITGLIEDERVERWALTUNG)), 'anmeldung',
    'Verwaltung: nur Anmeldung — ohne Gemeinde, Registrierung, Rollen, Mailversand, Datenschutz-Texte, Datensicherung, Papierkorb')
  for (const verboten of ['gemeinde', 'website', 'rollen', 'registrierung', 'mailversand',
    'datenschutz', 'datensicherung', 'papierkorb', 'gestaltung', 'dev-modus']) {
    assert.equal(abschnitte[verboten], 'admin', `${verboten} bleibt Administration`)
    assert.equal(sichtbar(MITGLIEDERVERWALTUNG).includes(verboten), false)
  }
  // Der Administrator sieht alles, ein Mitglied keinen Abschnitt.
  assert.equal(sichtbar(ADMIN).length, Object.keys(abschnitte).length)
  assert.equal(kette(sichtbar(MITGLIED)), '')
})

// ── 7. Umleitung (DSGVO → Datenschutz-Reiter) und EINE Regel ───────────────

test('UI-R10: „#/dsgvo“ führt die Mitgliederverwaltung auf den Datenschutz-Reiter', () => {
  const quelle = lies('router.js')
  // Die Umleitung benutzt dieselbe Regel wie die Wächter (R10-Review Punkt 5):
  // NICHT eine zweite Fassung der Bedingung.
  assert.match(quelle, /const verwaltung = verwaltungErlaubt\('personen', boot\)/,
    'die Umleitung ruft die EINE Regel')
  assert.match(quelle, /return verwaltung \? '#\/personen\/datenschutz' : '#\/profile'/)
  // Ein fehlendes Feld (alter Server) fällt in der Regel auf `is_admin` zurück.
  const ctx = routerMitBoot({ is_admin: true })
  assert.equal(ctx.router.verwaltungErlaubt('personen', { is_admin: true }), true)
  assert.equal(ctx.router.verwaltungErlaubt('personen', {}), false)
  assert.equal(ctx.router.verwaltungErlaubt('admin', { ist_mitgliederverwaltung: true }), false)
})

test('UI-R10: die Verwaltungsregel steht im Router genau EINMAL', () => {
  const quelle = lies('router.js')
  // Nur `verwaltungErlaubt` entscheidet über `ist_mitgliederverwaltung` — ein
  // zweiter Vergleich im Wächter oder in einer Weiterleitung wäre eine zweite
  // Wahrheit (R10-Review Punkt 5).
  const stellen = quelle.split('\n')
    .filter((z) => !/^\s*(?:\/\/|\*|\/\*)/.test(z))
    .filter((z) => /boot\.ist_mitgliederverwaltung/.test(z))
  assert.equal(stellen.length, 1,
    `nur die eine Regel liest \`boot.ist_mitgliederverwaltung\` (gefunden: ${stellen.length})`)
})

// ── 8. useSession: EINE Quelle ─────────────────────────────────────────────

test('UI-R10: useSession ist die EINE Quelle (istMitgliederverwaltung aus dem Boot)', () => {
  const quelle = lies('composables/useSession.js')
  assert.match(quelle, /istMitgliederverwaltung: boot\.ist_mitgliederverwaltung \|\| false/,
    'der Wert kommt aus dem Boot-Objekt, Vorgabe false (fail closed)')
  assert.match(quelle, /const istMitgliederverwaltung = computed\(\(\) =>\s*\n?\s*imp\.isActive\.value \? false : state\.value\.user\.istMitgliederverwaltung === true\)/,
    'während der Identitätsübernahme gilt das Konto (fail closed)')
  assert.match(quelle, /istMitgliederverwaltung,\n\s*hasMitglied,/,
    'der Wert steht im Rückgabewert von useSession')
  // Nur `useSession` liest das Boot-Feld; Seiten und Menü fragen die Sitzung
  // oder benutzen die eine Regel — keine dritte Fassung im Baum.
  const direkt = ['menue.js', 'router.js', 'pages/Personen.vue', 'pages/Einstellungen.vue']
    .filter((q) => /boot\.ist_mitgliederverwaltung|__DIakonosBOOT\?\.ist_mitgliederverwaltung/.test(lies(q)))
  assert.deepEqual(direkt, ['router.js'],
    'nur der Router liest das Boot-Feld direkt (das Menü bekommt die Rechte übergeben)')
})

// ── 9. Registrierung: Kern-Admin-Bereich ─────────────────────────────────
//
// R10-Review (Punkt 1, LIVE-Befund aus dem Wegwerf-Stack): der Abschnitt
// „Registrierung“ rief beim Öffnen `gemeinde_get_einstellungen` und beim
// Speichern `gemeinde_setze_linkvorgaben` — beide prüfen
// `gemeinde._angemeldeter_admin` (`permissions.is_admin`, Kern-Admin) und
// antworten der Mitgliederverwaltung mit 403. Er stand anfangs im
// Personen-Wächter; richtig ist die Administration.

test('UI-R10: „Registrierung“ ist Administration (Server: gemeinde._angemeldeter_admin)', () => {
  const ctx = routerMitBoot({ is_admin: false, ist_mitgliederverwaltung: true })
  assert.equal(ctx.router.verwaltungsStufeSeite('EinstellungenRegistrierung'), 'admin',
    'der Abschnitt verlangt Administration')
  assert.equal(ctx.router.oeffnet('EinstellungenRegistrierung'), false,
    'die Mitgliederverwaltung wird aufs Dashboard geführt statt 403 zu sehen')
  // Der Server verweigert beides — die Zuordnung deckt sich damit. Gelesen
  // wird nur, wenn der Quellbaum im Build mitliegt (im Frontend-Stage liegt er
  // unter `/backend`, im Repo unter `../backend`).
  const backendPfad = new URL('../../backend/src/diakronos_app/api/gemeinde.py', root)
  if (existsSync(backendPfad)) {
    const backend = readFileSync(backendPfad, 'utf8')
    const reg = backend.slice(backend.indexOf('def gemeinde_setze_linkvorgaben'))
    assert.match(reg.slice(0, 1200), /_angemeldeter_admin\(\)/,
      'gemeinde_setze_linkvorgaben prüft den Kern-Admin')
  }
})

// ── 10. Einstellungen-Rahmen lädt keinen verborgenen Abschnitt ────────────
//
// R10-Review (Punkt 1, LIVE-Befund): der Rahmen wählte den Abschnitt nach der
// Adresse (`a.seite === currentPageName`) — auch wenn die Sitzung ihn gar
// nicht sehen darf. Die Mitgliederverwaltung bekam so beim Aufruf von
// `#/einstellungen/registrierung` eine 403-Meldung von
// `gemeinde_get_einstellungen` statt einer Weiterleitung.

test('UI-R10: Einstellungen — nur ein SICHTBARER Abschnitt wird aktiv', () => {
  const quelle = lies('pages/Einstellungen.vue')
  const aktiv = quelle.slice(quelle.indexOf('const aktiverAbschnitt = computed'))
  assert.match(aktiv.slice(0, 1600),
    /if \(trefferAbschnitt && sichtbareAbschnitte\.value\.some\(a => a\.id === trefferAbschnitt\.id\)\)/,
    'die Adresse gewinnt nur bei einem sichtbaren Abschnitt')
})
