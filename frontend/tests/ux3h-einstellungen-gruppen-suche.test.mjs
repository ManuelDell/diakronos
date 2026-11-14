/**
 * UX3h — Einstellungen: Gruppen + Suche.
 *
 * Die Karte verlangt (Entwurf A6, Prinzip N3/N7/N8):
 *
 *   1. die linke Liste in FÜNF Gruppen — Gemeinde · Zugang · Kommunikation ·
 *      Datenschutz · Erweitert;
 *   2. ein Suchfeld OBEN, das Bereiche UND Feldnamen filtert (Stichwortliste
 *      je Bereich) und zum Feld springt;
 *   3. kein Karte-in-Karte.
 *
 * Der Test prüft DREI Dinge, in dieser Reihenfolge:
 *
 *   A · die Ordnung (`suche.mjs`): fünf Gruppen, jeder Bereich genau eine
 *       Gruppe, 1–9 Einträge je Gruppe, kein Bereich ohne Stichworte, kein
 *       Stichwort/Feld, das es im Abschnitt nicht gibt;
 *   B · die Suche (`suche.mjs`): Bereichstreffer, Feldtreffer, Umlaute,
 *       leerer Begriff trifft nichts (die Seite zeigt dann alles), unbekannter
 *       Begriff trifft nichts;
 *   C · die Seite selbst (MOUNTET Einstellungen.vue in jsdom): Suchfeld
 *       vorhanden, Gruppenüberschriften sichtbar, Tippen filtert die Liste,
 *       ein Feldtreffer erscheint als eigener Link auf
 *       `#/einstellungen/<bereich>/<feld>`.
 *
 * WAS HIER NICHT GEMOUNTET WIRD: die Abschnitte (`pages/einstellungen/*.vue`).
 * Sie sind asynchron eingebunden und laden über die API; ihr Verhalten prüfen
 * ihre eigenen Tests. Das Suchfeld der Seite wird über einen leeren Stellvertreter
 * für den Inhalt geprüft — die Liste ist der Gegenstand dieser Karte.
 *
 * Die Sprungmarke selbst wird an `DkField` gemountet (`anker="host"` →
 * `id="dk-sprung-host"`): sie ist der Grund, warum ein Feldtreffer ankommt.
 *
 * BEWUSST NICHT geprüft: das Aussehen (Screenshots gehören in die Abnahme)
 * und die API der Abschnitte (die haben ihre eigenen Tests).
 *
 * Lauf: node --test tests/ux3h-einstellungen-gruppen-suche.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, readdirSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

import {
  GRUPPEN, STICHWORTE, FELDER, gruppiere, normalisiere, trefferBereiche, trefferFelder,
} from '../src/diakonos/pages/einstellungen/suche.mjs'
import { SPRUNG_PRAEFIX, sprungId, sprungZiel, feldAusAdresse } from '../src/diakonos/pages/sprung.mjs'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
/** `frontend/src/diakonos/pages` — Bezugspunkt der relativen Importe. */
const SEITEN_DIR = resolve(TESTS_DIR, '..', 'src', 'diakonos', 'pages')
/** `frontend/src` — aus dem Testverzeichnis gerechnet (`tests/..`). */
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const SRC_ROOT = pathToFileURL(SRC_DIR + '/')
const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (relativ) => readFileSync(new URL(relativ, SRC), 'utf8')

// ══════════════════════════════════════════════════════════════════════════
// A · Ordnung: fünf Gruppen, Bereich → Gruppe, Stichworte
// ══════════════════════════════════════════════════════════════════════════

/**
 * Die Bereiche aus dem QUELLTEXT der Seite — nicht aus einer zweiten Liste im
 * Test. Sonst prüfte der Test seine eigene Meinung statt der Seite.
 */
function bereicheAusQuelle() {
  const quelle = lies('pages/Einstellungen.vue')
  // Zeilenumbrüche und mehrfache Leerzeichen einebnen: die Einträge stehen
  // über zwei bis drei Zeilen, `gruppe:` kommt darin erst NACH `seite:` —
  // ohne diese Normalisierung trafe das Muster über den nächsten Eintrag
  // hinweg (und lieferte die falsche Gruppe).
  const flach = quelle.replace(/\s+/g, ' ')
  const treffer = [...flach.matchAll(
    /\{\s*id:\s*'([a-z0-9-]+)',\s*label:\s*'([^']+)',\s*href:\s*'([^']+)',\s*seite:\s*'([^']+)'(?:(?!\},\s*\{)[\s\S])*?gruppe:\s*'([a-z]+)'/g)]
  return treffer.map((m) => ({ id: m[1], label: m[2], href: m[3], seite: m[4], gruppe: m[5] }))
}

const BEREICHE = bereicheAusQuelle()

test('UX3h: die Seite nennt fünf Gruppen in der Reihenfolge des Entwurfs', () => {
  assert.deepEqual(GRUPPEN.map((g) => g.titel),
    ['Gemeinde', 'Zugang', 'Kommunikation', 'Datenschutz', 'Erweitert'])
})

test('UX3h: jeder Bereich der Seite hat genau eine der fünf Gruppen', () => {
  assert.equal(BEREICHE.length, 11,
    'Bereiche der Seite nicht erkannt (' + BEREICHE.length + ') — Muster geändert?')
  const ids = new Set(GRUPPEN.map((g) => g.id))
  const falsch = BEREICHE.filter((b) => !ids.has(b.gruppe))
  assert.deepEqual(falsch, [], 'Bereich ohne gültige Gruppe: ' + JSON.stringify(falsch))
  // Die frühere Sammelgruppe „Einstellungen“ gibt es nicht mehr.
  assert.equal(BEREICHE.some((b) => b.gruppe === 'einstellungen'), false,
    'Sammelgruppe „Einstellungen“ lebt noch')
})

test('UX3h: Gruppen tragen 1–9 Einträge (Prinzip N3), keine ist leer', () => {
  const gruppen = gruppiere(BEREICHE)
  assert.equal(gruppen.length, 5, 'nicht alle fünf Gruppen erscheinen: '
    + gruppen.map((g) => g.id + '=' + g.eintraege.length).join(', '))
  for (const g of gruppen) {
    assert.ok(g.eintraege.length >= 1 && g.eintraege.length <= 9,
      `Gruppe „${g.titel}“ hat ${g.eintraege.length} Einträge`)
  }
  // Zuordnung nach Entwurf A6 — wörtlich, damit ein Umzug auffällt.
  const zuordnung = Object.fromEntries(gruppen.map((g) => [g.id, g.eintraege.map((e) => e.id)]))
  assert.deepEqual(zuordnung.gemeinde, ['gemeinde', 'website'])
  assert.deepEqual(zuordnung.zugang, ['anmeldung', 'registrierung', 'rollen'])
  assert.deepEqual(zuordnung.kommunikation, ['mailversand'])
  assert.deepEqual(zuordnung.datenschutz, ['datenschutz', 'datensicherung', 'papierkorb'])
  assert.deepEqual(zuordnung.erweitert, ['gestaltung', 'dev-modus'])
})

test('UX3h: jeder Bereich hat Stichworte, keine sind erfunden', () => {
  const ohne = BEREICHE.filter((b) => !(STICHWORTE[b.id] || []).length)
  assert.deepEqual(ohne.map((b) => b.id), [], 'Bereich ohne Stichworte')
  const ueberzaehlig = Object.keys(STICHWORTE).filter((id) => !BEREICHE.some((b) => b.id === id))
  assert.deepEqual(ueberzaehlig, [], 'Stichworte für einen Bereich, den es nicht gibt')
  for (const [id, liste] of Object.entries(STICHWORTE)) {
    assert.ok(liste.length >= 3, `${id}: nur ${liste.length} Stichworte`)
  }
})

/**
 * Eine Stichwortliste ist nur dann nützlich, wenn ihre Wörter im ABSCHNITT
 * vorkommen: ein Stichwort, das nirgends steht, ist eine Behauptung über die
 * Seite (Review 06.11., Punkt 4: „Sprache“, „Zwei-Faktor“, „Frist“ standen
 * nirgends). Geprüft wird gegen den Quelltext des Abschnitts + `suche.mjs`;
 * „Primo“ bleibt ausdrücklich erlaubt, weil der Begriff im Website-Abschnitt
 * als Produktname vorkommt.
 */
test('UX3h: jedes Stichwort kommt im Abschnitt wirklich vor (keine erfundenen)', () => {
  const datei = {
    gemeinde: 'Gemeinde.vue', website: 'Website.vue', anmeldung: 'Anmeldung.vue',
    registrierung: 'Registrierung.vue', rollen: 'RollenRechte.vue',
    mailversand: 'Mailversand.vue', datenschutz: 'DatenschutzTexte.vue',
    datensicherung: 'Datensicherung.vue', papierkorb: 'Papierkorb.vue',
    gestaltung: 'Gestaltung.vue', 'dev-modus': 'DevModus.vue',
  }
  // Beschriftungen, die die Suche selbst setzt (Gruppentitel, eigene Wörter)
  // gelten ebenfalls als „kommt vor“ — sonst wäre der Wächter zahnlos.
  const eigen = JSON.stringify(FELDER) + lies('pages/einstellungen/suche.mjs')
  const erlaubt = new Set(['Primo'])
  const fehlend = []
  for (const [bereich, liste] of Object.entries(STICHWORTE)) {
    const quelle = lies('pages/einstellungen/' + datei[bereich])
    const heu = normalisiere(quelle + ' ' + eigen)
    for (const wort of liste) {
      if (erlaubt.has(wort)) continue
      if (!heu.includes(normalisiere(wort))) fehlend.push(`${bereich}: „${wort}“`)
    }
  }
  assert.deepEqual(fehlend, [],
    'Stichwort steht nirgends im Abschnitt (erfunden?):\n' + fehlend.join('\n'))
})

test('UX3h: jedes Suchfeld (FELDER) steht wirklich im Abschnitt — Name und Sprungmarke', () => {
  const datei = {
    gemeinde: 'Gemeinde.vue', anmeldung: 'Anmeldung.vue',
    registrierung: 'Registrierung.vue', mailversand: 'Mailversand.vue',
    datenschutz: 'DatenschutzTexte.vue', datensicherung: 'Datensicherung.vue',
    gestaltung: 'Gestaltung.vue',
  }
  // Die Gestaltung hat KEINE Feldbeschriftungen mit festen Namen (die Maße
  // kommen aus dem Server) — ihre Suchziele sind die Gruppenüberschriften,
  // gesetzt über `ankerDerGruppe` (unten geprüft).
  assert.match(lies('pages/einstellungen/Gestaltung.vue'), /ankerDerGruppe\(/, 
    'Gestaltung ohne Sprungmarken an den Gruppen')
  const fehlend = []
  const ohneAnker = []
  for (const [bereich, felder] of Object.entries(FELDER)) {
    const name = datei[bereich]
    assert.ok(name, `kein Abschnitt für FELDER.${bereich} bekannt`)
    const quelle = lies('pages/einstellungen/' + name)
    for (const f of felder) {
      if (!quelle.includes(`label="${f.label}"`) && !quelle.includes(f.label)) {
        fehlend.push(`${bereich}: „${f.label}“`)
      }
      // Die Suche springt GENAU auf diese Marke — sie muss im Abschnitt stehen.
      // Die Gestaltung vergibt ihre Marken erst zur Laufzeit
      // (`ankerDerGruppe(gruppe.id)`, unten geprüft) — dort steht der Name im
      // Zuordnungsobjekt, nicht als Attribut.
      const marke = bereich === 'gestaltung'
        ? new RegExp(`'${f.id}'`, '').test(quelle)
        : quelle.includes(`anker="${f.id}"`)
      if (!marke) ohneAnker.push(`${bereich}: ${f.id}`)
    }
  }
  assert.deepEqual(fehlend, [], 'Feldname steht nicht im Abschnitt (erfunden?):\n' + fehlend.join('\n'))
  assert.deepEqual(ohneAnker, [], 'Feld ohne Sprungmarke `anker=…`:\n' + ohneAnker.join('\n'))
})

// ══════════════════════════════════════════════════════════════════════════
// B · Suche (ohne DOM)
// ══════════════════════════════════════════════════════════════════════════

test('UX3h: leere Suche trifft nichts — die Seite zeigt dann alle Bereiche', () => {
  assert.equal(trefferBereiche(BEREICHE, '').size, 0)
  assert.equal(trefferBereiche(BEREICHE, '   ').size, 0)
  assert.deepEqual(trefferFelder('gemeinde', ''), [])
})

test('UX3h: Bereichsname trifft den Bereich ("Mailversand", "Papierkorb")', () => {
  // „Mail“ trifft bewusst AUCH „Gemeinde“ — dort steht das Feld
  // „Kontakt-E-Mail“ mit dem Stichwort „E-Mail“. Genau das ist der Zweck:
  // Bereiche UND Felder in einem Zug.
  const mail = trefferBereiche(BEREICHE, 'Mail')
  assert.deepEqual([...mail.keys()], ['gemeinde', 'mailversand'])
  assert.equal(mail.get('mailversand').bereich.label, 'Mailversand')
  assert.deepEqual(mail.get('gemeinde').felder.map((f) => f.id), ['kontakt-email'])

  const topf = trefferBereiche(BEREICHE, 'Papierkorb')
  assert.deepEqual([...topf.keys()], ['papierkorb'])
  assert.deepEqual(topf.get('papierkorb').felder, [])
})

test('UX3h: Feldname trifft das FELD im richtigen Bereich ("Logo", "SMTP", "Aufbewahrung")', () => {
  const logo = trefferFelder('gemeinde', 'Logo')
  assert.deepEqual(logo.map((f) => f.id), ['logo'])
  const smtp = trefferFelder('mailversand', 'SMTP')
  assert.deepEqual(smtp.map((f) => f.id), ['host'], 'SMTP gehört zum Mailserver')
  // „Aufbewahrung“ steht in ZWEI Bereichen — jeder findet sein eigenes Feld.
  assert.ok(trefferFelder('datenschutz', 'Aufbewahrung').some((f) => f.id === 'aufbewahrung'))
  assert.ok(trefferFelder('datensicherung', 'Aufbewahrung').some((f) => f.id === 'aufbewahrungstage'))
})

test('UX3h: Suche ist groß/klein- und umlautblind', () => {
  assert.equal(normalisiere('Öffentliche Adresse'), 'oeffentliche adresse')
  assert.deepEqual(trefferFelder('gemeinde', 'öffentliche').map((f) => f.id), ['oeffentliche-adresse'])
  assert.deepEqual(trefferFelder('gemeinde', 'OEFFENTLICHE').map((f) => f.id), ['oeffentliche-adresse'])
  assert.deepEqual(trefferFelder('gemeinde', 'verschluesselung'), [],
    'ein deutsches Feld ohne Umlaut fand sich selbst — nur zur Kontrolle')
  assert.deepEqual(trefferFelder('mailversand', 'verschluesselung').map((f) => f.id), ['verschluesselung'])
})

test('UX3h: unbekannter Begriff trifft nichts (kein „alles trifft alles“)', () => {
  assert.equal(trefferBereiche(BEREICHE, 'xyzzy').size, 0)
  assert.deepEqual(trefferFelder('gemeinde', 'xyzzy'), [])
})

test('UX3h: Sprungziele bauen sich aus Bereichsadresse + Feldname', () => {
  assert.equal(sprungZiel('#/einstellungen/gemeinde', 'name'), '#/einstellungen/gemeinde/name')
  assert.equal(sprungZiel('#/einstellungen/gemeinde/', 'name'), '#/einstellungen/gemeinde/name')
  assert.equal(sprungId('name'), SPRUNG_PRAEFIX + 'name')
  assert.equal(feldAusAdresse('#/einstellungen/gemeinde/name'), 'name')
  assert.equal(feldAusAdresse('#/einstellungen/gemeinde'), '')
  assert.equal(feldAusAdresse('#/kalender'), '')
})

// ══════════════════════════════════════════════════════════════════════════
// C · Die Seite selbst: mounten
// ══════════════════════════════════════════════════════════════════════════

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/#/einstellungen' })
// WICHTIG: `Document` und `ShadowRoot` gehören dazu. Ohne sie wirft Vues
// `v-model`-Nebenläufigkeit (`rootNode instanceof Document`) bei JEDEM
// Re-Render — der Fehler landet im globalen `error`-Ereignis und JEDER Klick
// danach läuft ins Leere, ohne dass ein Test das merkt. Genau das hat diesen
// Test lange rot gehalten.
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot', 'HTMLButtonElement', 'sessionStorage']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.fetch = async () => ({
  ok: true, status: 200,
  headers: { get: () => 'application/json' },
  json: async () => ({ message: {} }),
  text: async () => '{"message":{}}',
  clone() { return this },
})

const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'ux3h-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')


function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  // RELATIVE Importe müssen auf die übersetzte Datei zeigen (die liegt im
  // TMP-Ordner) — sonst sucht der Importeur sie neben der Kopie. `.vue` wird
  // dabei gleich mitübersetzt; `.mjs`/`.js` unverändert auf die Quelle.
  // RELATIVE Importe zeigen auf die ÜBERSETZTE Nachbardatei (in TMP) bzw.
  // unverändert auf die Quelle (`.mjs`/`.js`). Bezugspunkt ist das Verzeichnis
  // der Datei, wie sie auf der Platte liegt — bei der Test-Kopie
  // (`_ux3h-leer.vue`) also ihr eigenes, neben der Quelle.
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    // Auf der TEST-KOPIE (in TMP) zeigen `../../…` auf die QUELLE.
    // Bezugspunkt ist das Verzeichnis, in dem die Datei liegt: für die
    // Test-Kopie (`_ux3h-mount.vue` neben der Quelle) ist das das echte
    // Verzeichnis; für Dateien aus tests/ ist es ihr eigenes.
    // Bezugspunkt ist das VERZEICHNIS DER DATEI — bei der Kopie ist das ihr
    // eigenes (neben der Quelle), sonst das der Quell-Datei.
    const dateiVerzeichnis = dirname(abs)
    // Dateien unter TMP sind Kopien (die Seite samt entkernten Abschnitten) —
    // ihre relativen Importe gehören ins Seiten-Verzeichnis des Quellbaums.
    const bezug = abs.startsWith(TMP) ? SEITEN_DIR : dirname(abs)
    const ziel = resolve(bezug, spec)
    const datei = /\.vue$/.test(spec) ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const warte = async (n = 6) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/**
 * Die Seite lädt ihre Abschnitte asynchron (`defineAsyncComponent`). Für den
 * Test der LISTE genügt ein Stellvertreter für den Inhalt: die Seite ist der
 * Gegenstand, nicht die Abschnitte (die haben eigene Tests).
 */
function seiteMitLeeremInhalt() {
  // QUELLE vor dem Übersetzen entschärfen: die Abschnitte werden asynchron
  // eingebunden und laden über die API — für den Test der LISTE genügt ein
  // Stellvertreter (die Abschnitte haben eigene Tests).
  const quelle = lies('pages/Einstellungen.vue')
    .replace(/defineAsyncComponent\(\(\) => import\([^)]*\)\)/g,
      "defineAsyncComponent(() => Promise.resolve({ render: () => null }))")
  assert.equal(/defineAsyncComponent\(\(\) => import/.test(quelle), false,
    'Abschnitte nicht ersetzt — Muster geändert?')

  // Übersetzen wie `kompilieren`, aber AUS DER QUELLE — ohne Datei im Baum.
  // Bezugspunkt der relativen Importe ist `src/diakronos/pages` (dort liegt
  // die Seite); das Ergebnis darf in TMP liegen.
  const filename = 'Einstellungen-leer.vue'
  const { descriptor, errors } = parse(quelle, { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    const ziel = resolve(SEITEN_DIR, spec)
    const datei = /\.vue$/.test(spec) ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename + '.mjs')
  writeFileSync(ziel, code)
  return ziel
}

test('UX3h: die Seite zeigt Suchfeld, fünf Gruppen und filtert beim Tippen', async () => {
  // UI-R10: Die Abschnitte tragen ihre Verwaltungsstufe (`verwaltung`); der
  // System Manager ist Administrator, also sind BEIDE Flags im Boot `true`
  // (genau so liefert es der Server: `ist_mitgliederverwaltung` = admin || …).
  globalThis.window.__DIakonosBOOT = {
    roles: ['System Manager'], devmode: false,
    is_admin: true, ist_mitgliederverwaltung: true,
  }
  const pfad = seiteMitLeeremInhalt()
  globalThis.Vue = Vue
  const Seite = (await import(pathToFileURL(pfad).href)).default

  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({ components: { Einstellungen: Seite }, template: '<Einstellungen />' })
  app.config.warnHandler = (m) => warnungen.push(String(m))
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(10)

  // EIN Leeren-Knopf, kein zweites natives × (Befund im Stack: `type="search"`
  // bringt seine eigene Lösch-Schaltfläche mit — am Handy standen zwei ×).
  const suche = host.querySelector('.ei-suche-eingabe')
  assert.equal(host.querySelector('input[type="search"]'), null,
    'type="search" bringt ein zweites × in das Feld')
  assert.equal(host.querySelectorAll('.ei-suche-loeschen').length, 0,
    'im Ruhezustand darf kein × stehen')
  assert.ok(suche, 'Suchfeld fehlt' + (warnungen.length ? ' | ' + warnungen.slice(0, 3).join(' | ') : ''))

  const gruppen = () => [...host.querySelectorAll('.ei-gruppe-titel')].map((el) => el.textContent.trim())
  // Ohne Suchbegriff: alle fünf Gruppen. „Erweitert“ ist da, weil der Test
  // System Manager ist (Gestaltung sichtbar); der Entwicklermodus hängt
  // zusätzlich an `devmode` (hier aus).
  assert.deepEqual(gruppen(), ['Gemeinde', 'Zugang', 'Kommunikation', 'Datenschutz', 'Erweitert'],
    'Gruppen ohne Suchbegriff fehlen')

  // „SMTP“ → nur Kommunikation, darunter das Feld „Name des Mailservers“.
  const tippen = (el, wert) => {
    el.value = wert
    el.dispatchEvent(new window.Event('input', { bubbles: true }))
  }
  tippen(suche, 'SMTP')
  await warte(8)
  assert.deepEqual(gruppen(), ['Kommunikation'], 'Suche filtert die Gruppen nicht')
  const felder = [...host.querySelectorAll('.ei-feld')].map((a) => a.textContent.trim())
  assert.deepEqual(felder, ['Name des Mailservers'], 'Feldtreffer fehlt: ' + felder.join(', '))
  const ziel = host.querySelector('.ei-feld').getAttribute('href')
  assert.equal(ziel, '#/einstellungen/mailversand/host', 'Feldtreffer zeigt nicht auf das Feld')

  // Nichts gefunden: sagt es und bietet den Rückweg.
  tippen(suche, 'xyzzy')
  await warte(8)
  assert.deepEqual(gruppen(), [], 'Gruppen bleiben trotz Nulltreffer stehen')
  assert.match(host.textContent, /Kein Bereich und kein Feld enthält/,
    'Leerzustand der Suche fehlt')

  // Rückweg 1: der KNOPF im Leerzustand — nach dem Neuzeichnen frisch holen.
  const rueckweg = () => [...host.querySelectorAll('.ei-suche-leer button')]
    .find((b) => /Alle Bereiche zeigen/.test(b.textContent))
  assert.ok(rueckweg(), 'Rückweg-Knopf im Leerzustand fehlt')
  rueckweg().click()
  await warte(10)
  assert.equal(suche.value, '', 'Rückweg-Knopf leert die Suche nicht')
  assert.deepEqual(gruppen(), ['Gemeinde', 'Zugang', 'Kommunikation', 'Datenschutz', 'Erweitert'],
    'nach dem Leeren erscheinen nicht wieder alle Gruppen')

  // Rückweg 2: das × im Suchfeld (am Handy der nächste Weg).
  tippen(suche, 'Logo')
  await warte(8)
  assert.deepEqual([...host.querySelectorAll('.ei-feld')].map((a) => a.textContent.trim()),
    ['Logo'], 'Feldtreffer „Logo“ fehlt')
  host.querySelector('.ei-suche-loeschen').click()
  await warte(10)
  assert.equal(suche.value, '', '× leert die Suche nicht')

  // Rückweg 3: Escape am Feld (Tastatur).
  tippen(suche, 'Logo')
  await warte(6)
  suche.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await warte(10)
  assert.equal(suche.value, '', 'Escape leert die Suche nicht')

  assert.deepEqual(warnungen, [], 'Vue meldet Warnungen: ' + warnungen.join(' | '))
  app.unmount()
})

test('UX3h: DkField mit `anker` schreibt die Sprungmarke ins Markup', async () => {
  const Feld = (await import(pathToFileURL(
    kompilieren(new URL('diakonos/components/ui/DkField.vue', SRC_ROOT).pathname)).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    components: { DkField: Feld },
    template: '<DkField label="Name des Mailservers" anker="host" v-slot="feld">'
      + '<input v-bind="feld.feldProps" /></DkField>',
  })
  app.mount(host)
  await warte(4)
  const marke = host.querySelector('#dk-sprung-host')
  assert.ok(marke, 'Sprungmarke `dk-sprung-host` fehlt am Feld')
  assert.ok(marke.classList.contains('dk-ui-field'), 'Marke sitzt nicht an der Feldhülle')
  app.unmount()

  // Ohne `anker` keine Marke (keine leere `dk-sprung-`-Kennung im DOM).
  const host2 = document.createElement('div')
  document.body.appendChild(host2)
  const app2 = Vue.createApp({
    components: { DkField: Feld },
    template: '<DkField label="Ohne" v-slot="feld"><input v-bind="feld.feldProps" /></DkField>',
  })
  app2.mount(host2)
  await warte(4)
  assert.equal(host2.querySelector('[id^="dk-sprung-"]'), null, 'Marke ohne anker gesetzt')
  app2.unmount()
})

test('UX3h: der Router kennt die Feldadresse (#/einstellungen/<bereich>/<feld>)', () => {
  // BEFUND im Wegwerf-Stack: der Feldtreffer führte auf „Seite nicht
  // gefunden“, weil der Router nur die Bereichsadressen kannte. Eine Adresse
  // ohne Route ist ein toter Link — deshalb steht das Muster im Router und
  // wird hier festgehalten.
  const router = lies('router.js')
  // Das Muster steht als Regex im Quelltext — verglichen wird der Wortlaut,
  // nicht ein zweites Regex (das wäre eine Kopie, die auseinanderläuft).
  assert.ok(router.includes('einstellungen\\/([a-z0-9-]+)\\/[a-z0-9-]+$'),
    'kein Mustersatz für Feldadressen im Router')
  assert.match(router, /page: 'Einstellungen', param: 'bereich'/,
    'Feldadresse zeigt nicht auf die Einstellungen-Seite')
})

test('UX3h: kein Karte-in-Karte — die Navigation ist getönte Fläche ohne Rahmen', () => {
  const css = lies('pages/Einstellungen.vue')
  const block = css.slice(css.indexOf('.ei-navi {'), css.indexOf('.ei-suche-feld {'))
  assert.match(block, /background:\s*var\(--surface-2\)/, 'Navigation ohne getönte Fläche')
  assert.match(block, /box-shadow:\s*var\(--schatten-karte\)/, 'Navigation ohne sanften Schatten')
  assert.equal(/border:\s*(?!0)\S/.test(block), false,
    'Navigation zieht einen Rahmen — das wäre die Karte in der Karte (Prinzip Ä2)')
  // Und keine festen Farbwerte in der Seite (ON-0b-Regel).
  assert.equal(/#[0-9a-fA-F]{3,8}\b|rgba?\(/.test(css.replace(/\/\*[\s\S]*?\*\//g, '')), false,
    'feste Farbwerte in Einstellungen.vue')
})

// ══════════════════════════════════════════════════════════════════════════
// D · Review 06.11. (Opus) — die Nacharbeit dieser Runde
// ══════════════════════════════════════════════════════════════════════════

test('UX3h: KEIN eigenes Tastenkürzel — Strg+K gehört der Befehlspalette (UX3f)', () => {
  // Kollision aus dem Review: die Befehlspalette (UX3f) belegt Strg+K global.
  // Zwei Fänger auf derselben Taste heißt: einer gewinnt zufällig.
  const quelle = lies('pages/Einstellungen.vue')
  assert.equal(/ctrlKey|metaKey/.test(quelle), false,
    'Einstellungen.vue fängt Strg/Meta-Tasten ab — das gehört der Befehlspalette')
  assert.equal(/toLowerCase\(\) === 'k'/.test(quelle), false, 'Strg+K steckt noch in der Seite')
  // Escape bleibt: es steht am Feld selbst (`@keydown.escape`).
  assert.match(quelle, /@keydown\.escape="sucheLeeren"/, 'Escape leert die Suche nicht mehr')
})

test('UX3h: der aktive Eintrag ist leise markiert, nicht die volle Primärfläche', () => {
  // A6 (Review, Punkt 1): eine volle Primärfläche konkurriert mit dem EINEN
  // Primärknopf der Ansicht (Prinzip K1).
  const css = lies('pages/Einstellungen.vue')
  const block = css.slice(css.indexOf('.ei-eintrag.is-active {'),
    css.indexOf('}', css.indexOf('.ei-eintrag.is-active {')))
  assert.match(block, /color:\s*var\(--primary\)/, 'aktiver Eintrag ohne Primärfarbe als Text')
  assert.match(block, /background:\s*var\(--accent-soft\)/, 'aktiver Eintrag ohne leise Fläche')
  assert.match(block, /box-shadow:\s*inset var\(--ring-breite\) 0 0 var\(--primary\)/,
    'aktiver Eintrag ohne Balken (Markierung nur über Farbe wäre Ä4-widrig)')
  assert.match(block, /font-weight:\s*var\(--fw-fett\)/, 'aktiver Eintrag nicht fett')
  assert.equal(/background:\s*var\(--primary\)/.test(block), false,
    'aktiver Eintrag nutzt die VOLLE Primärfläche — Kollision mit dem Primärknopf')
})

test('UX3h: Hartwerte der Marke sind Tokens (Ring, Fokusring-Abstand)', () => {
  // Review, Punkt 9: `0 0 0 2px` und `outline-offset: 2px` standen als Zahlen.
  const css = lies('pages/Einstellungen.vue')
  const ringe = lies('index.css')
  assert.equal(/outline-offset:\s*\d+px/.test(css), false,
    'fester outline-offset in Einstellungen.vue (Token --ring-breite)')
  assert.equal(/0 0 0 \d+px/.test(ringe), false, 'fester Ring im Sprungziel (Token --ring-breite)')
  assert.match(ringe, /\.dk-ui-field\.is-sprungziel \{[\s\S]*?var\(--ring-breite\)/,
    'Sprungziel-Ring nutzt das Token nicht')
  const tokens = lies('tokens.css')
  assert.match(tokens, /--ring-breite:\s*\d+px/, 'Token --ring-breite fehlt in tokens.css')
  assert.match(tokens, /--schatten-eingabe:/, 'Token --schatten-eingabe fehlt in tokens.css')
})

test('UX3h: das Suchfeld ist Fläche + Schatten, kein Rahmen (A6/UX1d)', () => {
  // Review, Punkt 6. Der Rahmen bleibt nur als durchsichtige Linie stehen,
  // damit der Fokuswechsel die Höhe nicht verschiebt.
  const css = lies('pages/Einstellungen.vue')
  const block = css.slice(css.indexOf('.ei-suche-feld {'), css.indexOf('.ei-suche-symbol'))
  assert.match(block, /box-shadow:\s*var\(--schatten-eingabe\)/, 'Suchfeld ohne sanften Schatten')
  assert.match(block, /border:\s*var\(--rahmen-breite\) solid transparent/,
    'Suchfeld zieht einen sichtbaren Rahmen')
  assert.equal(/border:\s*var\(--rahmen-breite\) solid var\(--rahmen-farbe\)/.test(block), false,
    'Suchfeld nutzt noch den Standardrahmen')
})

test('UX3h: Platzhalter und Spalte passen zusammen (A6: „Einstellungen durchsuchen“)', () => {
  // Review, Punkt 5: der Wortlaut ist vorgegeben, also wächst die SPALTE.
  const quelle = lies('pages/Einstellungen.vue')
  assert.match(quelle, /placeholder="Einstellungen durchsuchen"/, 'Platzhalter nicht nach A6')
  const spalte = Number((quelle.match(/grid-template-columns:\s*(\d+)px minmax\(0, 1fr\)/) || [])[1])
  assert.ok(spalte >= 240, `Spalte ${spalte} px — zu schmal für den Platzhalter`)
  // Grobe Rechnung: 25 Zeichen × ~0,5 em bei --fs-xs (12 px) ≈ 151 px. Davon
  // gehen Innenabstand (24), Symbol (16) und ein Abstand (8) ab.
  assert.ok(spalte - 24 - 16 - 8 >= 160, `Spalte ${spalte} px lässt dem Platzhalter zu wenig Platz`)
  assert.match(quelle, /\.ei-suche-eingabe \{[\s\S]*?font-size:\s*var\(--fs-xs\)/,
    'Suchfeld-Schrift nicht auf der Stufe des Entwurfs (12 px)')
})

test('UX3h: kein toter Code — keine ungenutzten Klasse/Exporte', () => {
  // Review, Punkt 10.
  const quelle = lies('pages/Einstellungen.vue')
  assert.equal(/ei-suche-fuss/.test(quelle), false, 'totes CSS .ei-suche-fuss steht noch')
  assert.equal(/defineExpose/.test(quelle), false, 'ungenutztes defineExpose steht noch')
  assert.equal(/sucheEingabe/.test(quelle), false, 'ungenutzte Feld-Referenz steht noch')
  assert.equal(/onUnmounted/.test(quelle), false, 'onUnmounted ohne Anmeldung ist tot')
})

test('UX3h: der Suchbegriff überlebt den Seitenneuaufbau (sessionStorage)', () => {
  // Review, Punkt 3: App.vue zeichnet die Seite bei jedem Adresswechsel neu
  // (`:key="currentHash"`) — ein Begriff nur im `ref` wäre beim Klick auf einen
  // Treffer weg, und `gemerkterTreffer` liefe ins Leere.
  const quelle = lies('pages/Einstellungen.vue')
  assert.match(quelle, /sessionStorage\?\.getItem\(BEGRIFF_SCHLUESSEL\)/,
    'Begriff wird nicht aus sessionStorage gelesen')
  assert.match(quelle, /sessionStorage\?\.setItem\(BEGRIFF_SCHLUESSEL, wert\)/,
    'Begriff wird nicht in sessionStorage geschrieben')
  // try/catch: Privatmodus und jsdom haben keinen Speicher — ohne Fänger
  // bricht die ganze Seite ab.
  assert.match(quelle, /try \{[\s\S]*?sessionStorage[\s\S]*?\} catch \{/, 'sessionStorage ohne Fänger')
  // Und `gemerkterTreffer` wird tatsächlich benutzt (sonst wäre der Speicher
  // der einzige Zweck und die Marker-Logik tot).
  assert.match(quelle, /gemerkterTreffer\.value[\s\S]*?sichtbareAbschnitte\.value\.some/,
    'gemerkterTreffer wird nicht gegen die sichtbaren Bereiche geprüft')
})

test('UX3h: der Sprung setzt den Fokus ins Bedienelement, nicht an die Hülle', async () => {
  // Review, Punkt 2: `dk-ui-field` ist ein `div` — `div.focus()` gibt es nicht,
  // der Fokus blieb also aus.
  const { springeZu } = await import('../src/diakonos/pages/sprung.mjs')
  const host = document.createElement('div')
  host.innerHTML = '<div id="dk-sprung-host" class="dk-ui-field">'
    + '<label for="f1">Name des Mailservers</label><input id="f1" /></div>'
  document.body.appendChild(host)
  const marke = host.querySelector('#dk-sprung-host')
  let fokusiert = null
  marke.focus = () => { fokusiert = 'huelle' }
  const eingabe = host.querySelector('#f1')
  eingabe.focus = (opts) => { fokusiert = { ziel: 'eingabe', opts } }
  assert.equal(springeZu('host', document), true, 'Sprungmarke nicht gefunden')
  assert.deepEqual(fokusiert, { ziel: 'eingabe', opts: { preventScroll: true } },
    'Fokus landete nicht im Eingabefeld')
  assert.ok(marke.classList.contains('is-sprungziel'), 'Sprungziel nicht markiert')
  marke.classList.remove('is-sprungziel')
})
