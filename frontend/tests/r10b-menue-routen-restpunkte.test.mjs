/**
 * UI-R10b — Restpunkte aus dem zweiten Review zu UI-R10 (Menü/Routen).
 *
 * Vier kleine, aber sichtbare Löcher blieben offen; diese Datei hält je Loch
 * die Zusage am ECHTEN Code fest (vm bzw. Quelltext, keine Attrappen-Simulation
 * der Regel selbst):
 *
 *   1. MITTEL — `Registrierung.vue` lud die Link-Vorgaben über
 *      `gemeinde_get_einstellungen` (nur Kern-Admin). Die Mitgliederverwaltung
 *      bekam 403, der Fehler blieb still, und neue Links fielen auf fest
 *      eingebaute 30 Tage zurück. Jetzt: `registrierungslink_api.get_link_vorgaben`
 *      (R-12f, dieselbe Prüfung wie `create_link`); schlägt der Abruf fehl,
 *      bleibt `gueltig_bis` LEER (= der Server wendet die Vorgabe an) und der
 *      Hinweis sagt „Vorgabe der Gemeinde“ — nie eine feste Zahl.
 *   2. NIEDRIG — `Einstellungen/Anmeldung.vue`: Modus `anlegen_mit_rollen`,
 *      Verwaltungsrollen im Auswahlfeld und der Schalter „Verwaltungsrollen
 *      über Authentik-Gruppen zulassen“ verlangen beim Server System Manager.
 *      Für alle anderen sind sie gesperrt und nennen den Grund.
 *   3. NIEDRIG — die Verwaltungsregel stand zweimal (`router.js::
 *      verwaltungErlaubt` und `menue.js::verwaltungZutreffend`). Der Router
 *      delegiert jetzt; `is_admin: 1` (Zahl, nicht `true`) öffnet keine
 *      Admin-Seite.
 *   4. NIEDRIG — `pages/Einstellungen.vue` aktivierte ohne sichtbare
 *      Abschnitte „Gemeinde“; jetzt `null` + Leerzustand.
 */
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import test from 'node:test'
// UI-R10b (Review, Punkt 2): die echte Verwaltungsregel für die Router-vm.
import { echteVerwaltungsregel } from './helpers/verwaltungsregel.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const kette = (liste) => [...liste].join(',')

// ── 1. Link-Vorgaben für alle, die die Seite sehen ─────────────────────────

/** Ein `<script setup>`-Rumpf bis zur ersten Stil-/Templategrenze. */
function skript(quelle) {
  const start = quelle.indexOf('<script setup>')
  const ende = quelle.indexOf('</script>', start)
  return quelle.slice(start, ende)
}

test('UI-R10b: Link-Vorgaben kommen aus get_link_vorgaben, nicht aus den Gemeinde-Einstellungen', () => {
  const quelle = lies('pages/Registrierung.vue')
  const block = quelle.slice(quelle.indexOf('async function ladeLinkVorgaben'))
  const rumpf = block.slice(0, block.indexOf('\nasync function linkSchliessen'))

  assert.match(rumpf, /registrierungslink_api\.get_link_vorgaben/,
    'die Vorgaben kommen aus dem Endpunkt, den auch die Mitgliederverwaltung darf (R-12f)')
  assert.doesNotMatch(rumpf, /gemeinde_get_einstellungen/,
    'kein Aufruf der Kern-Admin-Einstellungen mehr (403 für die Verwaltung)')
  // Die Zahl 30 darf im Vorgabe-Block NICHT mehr als Rückfall stehen.
  assert.doesNotMatch(quelle.slice(quelle.indexOf('// ── Links ─'), quelle.indexOf('// ── Verlängern')),
    /\?\?\s*30|:\s*30\b/,
    'kein fest eingebauter 30-Tage-Rückfall mehr — leer heißt Vorgabe')
})

/**
 * Die beiden Funktionen aus `Registrierung.vue` in einer vm ausführen:
 * `leererLink()` (Vorbelegung) und `ladeLinkVorgaben()` (Abruf/Fehlerfall).
 * `ref` ist die kleinste Attrappe, die reicht (`.value`).
 */
function registrierungLogik(apiCall) {
  const quelle = lies('pages/Registrierung.vue')
  // Genau die drei Stücke, die die Vorbelegung ausmachen — sie hängen NICHT
  // voneinander ab und brauchen keine weitere Attrappe.
  const teil = (start, ende) => {
    const von = quelle.indexOf(start)
    assert.ok(von > 0, `Anker fehlt: ${start}`)
    const bis = ende ? quelle.indexOf(ende, von) : undefined
    assert.ok(bis === undefined || bis > von, `Ende fehlt: ${ende}`)
    return quelle.slice(von, bis === undefined ? von + 2000 : bis)
  }
  const block = [
    teil('const linkVorgaben = ref(', 'const linkSpeichert'),
    teil('async function ladeLinkVorgaben()', 'const laufzeitHinweis = computed'),
    teil('const laufzeitHinweis = computed', 'async function linkSchliessen'),
  ].join('\n')
  const context = {
    console,
    ref: (v) => ({ value: v }),
    computed: (fn) => ({ get value() { return fn() } }),
    apiCall,
  }
  vm.createContext(context)
  vm.runInContext(`${block}
globalThis.erg = { leererLink, ladeLinkVorgaben, linkVorgaben, laufzeitHinweis, ohneAblaufHinweis };`,
  context)
  return context.erg
}

test('UI-R10b: Mitgliederverwaltung — Vorbelegung aus get_link_vorgaben (7 Tage / 42)', async () => {
  const aufrufe = []
  const erg = registrierungLogik(async (pfad, args) => {
    aufrufe.push({ pfad, args })
    if (pfad === 'diakronos.diakonos.api.registrierungslink_api.get_link_vorgaben') {
      return { message: { link_laufzeit_tage: 7, link_max_anmeldungen: 42 } }
    }
    throw new Error(`unerwarteter Aufruf: ${pfad}`)
  })

  await erg.ladeLinkVorgaben()
  assert.deepEqual(aufrufe.map((a) => a.pfad),
    ['diakronos.diakonos.api.registrierungslink_api.get_link_vorgaben'],
    'kein gemeinde_get_einstellungen-Aufruf (der wäre für die Verwaltung 403)')

  const link = erg.leererLink()
  assert.equal(link.max_anmeldungen, 42, 'Platzzahl aus der Vorgabe')
  // 7 Tage ab heute — auf den Tag genau, nicht auf die Sekunde.
  const erwartet = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)
  assert.equal(link.gueltig_bis, erwartet, 'Laufzeit 7 Tage aus get_link_vorgaben')
  assert.match(erg.laufzeitHinweis.value, /7 Tage/, 'der Hinweis nennt die gelesene Vorgabe')
})

test('UI-R10b: Fehlerfall — gueltig_bis bleibt LEER, Hinweis „Vorgabe der Gemeinde“', async () => {
  const erg = registrierungLogik(async () => { throw new Error('403') })
  await erg.ladeLinkVorgaben()

  assert.equal(erg.linkVorgaben.value, null, 'keine Vorgabe bekannt — keine geratene Zahl')
  const link = erg.leererLink()
  assert.equal(link.gueltig_bis, '', 'leeres Datum heißt: der Server wendet die Vorgabe an')
  assert.equal(link.max_anmeldungen, 0, 'keine geratene Platzzahl')
  assert.match(erg.laufzeitHinweis.value, /Laufzeit: Vorgabe der Gemeinde/,
    'der sichtbare Hinweis sagt, wer die Laufzeit bestimmt')
  assert.match(erg.ohneAblaufHinweis.value, /Vorgabe der Gemeinde/)
})

// ── 2. Anmeldung: System-Manager-Stellen gesperrt ──────────────────────────
//
// UI-R10b (Review, Punkt 3): die Sperre wird GE MOUNTET gemessen (disabled-
// Status je Feld, sichtbare Gründe, R-12i: Mitglied-Zeilen bleiben bedienbar) —
// `r10b2-anmeldung-einstellungen-mount.test.mjs`. Hier steht nur noch, dass die
// Rollenliste EINE Quelle hat und dass die Seite diese Quelle benutzt.

test('UI-R10b: die Verwaltungsrollen stehen EINMAL (verwaltungsrollen.mjs) und beide Seiten nutzen sie', () => {
  const quelle = lies('verwaltungsrollen.mjs')
  assert.match(quelle, /export const VERWALTUNGSROLLEN = \['System Manager', 'Mitgliederadministrator'\]/,
    'die Liste entspricht `permissions.ADMIN_ROLES` des Servers')
  for (const seite of ['pages/einstellungen/Anmeldung.vue', 'pages/einstellungen/RollenRechte.vue']) {
    assert.match(lies(seite), /from '\.\.\/\.\.\/verwaltungsrollen\.mjs'/,
      `${seite} importiert die gemeinsame Liste`)
  }
  // Keine zweite Kopie mehr in den Seiten.
  assert.doesNotMatch(lies('pages/einstellungen/Anmeldung.vue'),
    /const VERWALTUNGSROLLEN = \[/, 'Anmeldung.vue kopiert die Liste nicht')
  assert.doesNotMatch(lies('pages/einstellungen/RollenRechte.vue'),
    /const VERWALTUNGSROLLEN = \[/, 'RollenRechte.vue kopiert die Liste nicht')
})

// ── 3. Eine Regel: der Router delegiert ───────────────────────────────────

/** router.js in einer vm; die Importe werden durch Attrappen ersetzt. */
function routerMitBoot(boot, { ohneRegel = false } = {}) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
  source = source.replace(/^export \{([^}]*)\}$/gm, '')
  source = source.replace(/^export /gm, '')
  source = `
const ref = globalThis.__vue.ref
const computed = globalThis.__vue.computed
const shallowRef = globalThis.__vue.shallowRef
const setzeFenstertitel = () => {}
const darfWebsite = () => true
const fehlertext = (e) => String(e)
const einrichtungLeitung = {
  EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
  einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
  einrichtungGesehen: () => false,
}
const verwaltungZutreffend = globalThis.__regelStub
${source}
globalThis.router = { verwaltungErlaubt, verwaltungsStufeSeite };
`
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
    // UI-R10b (Review, Punkt 2): der Router führt KEINE eigene Kopie der Regel
    // mehr (Rückfall = `false`). Dieser Harness prüft, WER die Seiten öffnet —
    // also setzt er die ECHTE Regel aus `menue.js` ein.
    __regelStub: ohneRegel ? undefined : echteVerwaltungsregel(),
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  context.__guards = []
  vm.runInContext('globalThis.__guards = beforeEachGuards.slice()', context)
  context.router.oeffnet = (name) => {
    for (const guard of context.__guards) {
      if (guard({ to: '#/x', name, params: {} }) === false) return false
    }
    return true
  }
  return context.router
}

test('UI-R10b: Boot mit `is_admin: 1` (Zahl) öffnet KEINE Admin-Seite', () => {
  // Fail closed: nur ein echtes `true` zählt. Vorher prüfte der Router
  // `!!boot.is_admin` für den Personenbereich — und `1` ist wahr.
  const ctx = routerMitBoot({ is_admin: 1, ist_mitgliederverwaltung: 1 })
  assert.equal(ctx.verwaltungErlaubt('admin'), false, 'is_admin als Zahl ist kein Admin')
  assert.equal(ctx.verwaltungErlaubt('personen'), false, 'ist_mitgliederverwaltung als Zahl zählt nicht')
  assert.equal(ctx.oeffnet('EinstellungenGemeinde'), false, 'keine Admin-Seite für `is_admin: 1`')
  assert.equal(ctx.oeffnet('MitgliederUebersicht'), false, 'auch keine Personen-Seite')

  // Gegenprobe: echte Flags öffnen wie bisher.
  const echt = routerMitBoot({ is_admin: true, ist_mitgliederverwaltung: true })
  assert.equal(echt.oeffnet('EinstellungenGemeinde'), true)
  assert.equal(echt.oeffnet('MitgliederUebersicht'), true)
  const verwaltung = routerMitBoot({ is_admin: false, ist_mitgliederverwaltung: true })
  assert.equal(verwaltung.oeffnet('MitgliederUebersicht'), true)
  assert.equal(verwaltung.oeffnet('EinstellungenGemeinde'), false)
})

test('UI-R10b: verwaltungErlaubt delegiert an menue.js::verwaltungZutreffend — Rückfall fail closed', () => {
  // Der Import steht im Quelltext, und im Betrieb wird er benutzt.
  const quelle = lies('router.js')
  assert.match(quelle, /import \{ verwaltungZutreffend \} from '\.\/menue\.js'/,
    'die eine Regel wird aus dem Menü-Modul übernommen')
  assert.match(quelle, /const verwaltungRegel = typeof verwaltungZutreffend === 'function'\s*\n?\s*\? verwaltungZutreffend\s*\n?\s*: \(\) => false/,
    'im Betrieb gilt die importierte Regel; ohne sie gilt NICHTS (fail closed, Review Punkt 2)')
  const rumpf = quelle.slice(quelle.indexOf('export function verwaltungErlaubt'))
  assert.match(rumpf.slice(0, 900), /return verwaltungRegel\(stufe, \{/,
    'die Entscheidung fällt in der EINEN Regel')

  // Der Rückfall ist keine zweite Fassung mehr: OHNE `menue.js` bleibt eine
  // Verwaltungsseite zu, statt nach einer nachgebauten Regel zu öffnen.
  const ohneMenue = routerMitBoot({ is_admin: true, ist_mitgliederverwaltung: true }, { ohneRegel: true })
  assert.equal(ohneMenue.verwaltungErlaubt('admin'), false,
    'ohne die eine Regel öffnet der Router KEINE Admin-Seite (fail closed)')
  assert.equal(ohneMenue.verwaltungErlaubt('personen'), false,
    'ohne die eine Regel öffnet der Router KEINEN Personenbereich')
  assert.equal(ohneMenue.verwaltungErlaubt(null), true,
    'Seiten ohne Verwaltungsstufe bleiben erreichbar (keine Schranke)')
  assert.equal(ohneMenue.oeffnet('EinstellungenGemeinde'), false)

  // Dieselbe Regel wie im Menü — gegen die ECHTE Regel aus `menue.js` geprüft.
  const regel = echteVerwaltungsregel()
  const ctx = routerMitBoot({})
  const lagen = [
    { istAdmin: true, istMitgliederverwaltung: true },
    { istAdmin: false, istMitgliederverwaltung: true },
    { istAdmin: false, istMitgliederverwaltung: false },
    { istAdmin: 1, istMitgliederverwaltung: 1 },
  ]
  for (const stufe of ['admin', 'personen']) {
    for (const lage of lagen) {
      const boot = { is_admin: lage.istAdmin, ist_mitgliederverwaltung: lage.istMitgliederverwaltung }
      assert.equal(ctx.verwaltungErlaubt(stufe, boot), regel(stufe, lage),
        `${stufe} / ${JSON.stringify(lage)}: Router und Menü müssen dasselbe sagen`)
    }
  }
})

// ── 4. Einstellungen: Leerzustand statt „Gemeinde“ ─────────────────────────

test('UI-R10b: ohne sichtbaren Abschnitt ist KEINER aktiv (null) und der Leerzustand steht', () => {
  const quelle = lies('pages/Einstellungen.vue')

  // Kein Rückfall auf `abschnitte[0]` mehr — weder bei der Auswahl …
  assert.doesNotMatch(quelle, /sichtbareAbschnitte\.value\[0\] \|\| abschnitte\[0\]/,
    'kein stiller Rückfall auf „Gemeinde“')
  assert.match(quelle, /if \(!sichtbareAbschnitte\.value\.length\) return null/,
    'ohne sichtbare Abschnitte ist die Auswahl `null`')
  // … noch beim Inhalt.
  const inhalt = quelle.slice(quelle.indexOf('const inhalt = computed'))
  assert.match(inhalt.slice(0, 700), /if \(keineAbschnitte\.value\) return null/,
    'der Inhalt ist dann leer (kein fremder Abschnitt)')
  // Der Leerzustand nennt den Satz wörtlich.
  assert.match(quelle, /<DkEmpty v-if="keineAbschnitte"[\s\S]{0,240}Für dich gibt es hier keine Einstellungen\./,
    'der Leerzustand sagt den Satz aus der Karte')
  assert.match(quelle, /<component :is="inhalt" v-else embedded \/>/,
    'sonst wird wie bisher der Abschnitt gezeigt')
})

// ── 5. Die eine Regel bleibt EINE (Gegenprobe zum Router) ─────────────────

test('UI-R10b: `boot.ist_mitgliederverwaltung` wird im Router nur an EINER Stelle gelesen', () => {
  // Der Router übersetzt den Boot-Stand genau einmal in die Sitzungs-Flags;
  // alles Weitere entscheidet `menue.js::verwaltungZutreffend`.
  const stellen = lies('router.js').split('\n')
    .filter((z) => !/^\s*(?:\/\/|\*|\/\*)/.test(z))
    .filter((z) => /boot\.ist_mitgliederverwaltung/.test(z))
  assert.equal(stellen.length, 1,
    `nur die eine Übersetzung liest \`boot.ist_mitgliederverwaltung\` (gefunden: ${stellen.length})`)
  assert.equal(kette(['ok']), 'ok')
})
