/**
 * N12 — Aufräumen nach der Neuordnung (Frontend).
 *
 * Die Neuordnung hat alte Seiten und „admin“-Einstiegspunkte ersetzt. Dieser
 * Test hält fest, dass die Aufräumarbeit nicht zurückfällt:
 *
 *   1. Die alte Seite `pages/Anmeldung.vue` samt ihrem Einstiegspunkt ist weg;
 *      ihre Aufgaben leben in „Einstellungen → Anmeldung“ und „Mitglieder →
 *      Anfragen“ weiter.
 *   2. `src/admin/*` (eigener Build-Einstieg der ausgebauten Verwaltung) ist
 *      entfernt und wird in keiner Konfiguration mehr gebaut.
 *   3. Die früheren Adressen bleiben als Weiterleitung erhalten (Konzept
 *      Abschnitt 8) — dass die alten Router-Namen selbst NICHT mehr existieren.
 *   4. Kein Code nennt noch einen gelöschten Komponentennamen.
 *
 * Läuft echt (Router in einer vm) statt per Textsuche.
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const hier = path.dirname(fileURLToPath(import.meta.url))
const src = path.resolve(hier, '../src')
const lies = (rel) => fs.readFileSync(path.join(src, rel), 'utf8')

function routerAusfuehren(boot) {
  let source = lies('diakonos/router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
  let hashchange
  const window = {
    location: { hash: boot.hash || '#/', replace(hash) { this.hash = hash } },
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

// ── 1. Die alte Seite und ihr Einstiegspunkt sind entfernt ──────────────────
{
  assert.ok(!fs.existsSync(path.join(src, 'diakonos/pages/Anmeldung.vue')),
    'die alte Seite pages/Anmeldung.vue ist entfernt')
  const router = lies('diakonos/router.js')
  assert.doesNotMatch(router, /pages\/Anmeldung\.vue/,
    'der Router importiert die alte Seite nicht mehr')
  assert.doesNotMatch(router, /\bAnmeldung:\s*\(\)\s*=>/,
    'die Seitenkennung „Anmeldung“ ist entfernt')
  // In der Weiterleitungstabelle DARF die alte Adresse stehen (Abschnitt 8) —
  // sie darf aber nicht mehr als eigene Route aufgelöst werden.
  const routeBlock = router.slice(router.indexOf('const routeMap'), router.indexOf('const dynamicRoutes'))
  assert.doesNotMatch(routeBlock, /'#\/anmeldung'\s*:/,
    'die Route „#/anmeldung“ ist aus routeMap entfernt (sie leitet nur noch weiter)')
}

// ── 2. src/admin/* ist entfernt und wird nicht mehr gebaut ──────────────────
{
  assert.ok(!fs.existsSync(path.join(src, 'admin')),
    'der Ordner src/admin ist entfernt')
  const vite = fs.readFileSync(path.resolve(hier, '../vite.config.mjs'), 'utf8')
  assert.doesNotMatch(vite, /src\/admin\/main\.js/,
    'vite.config.mjs baut den admin-Einstieg nicht mehr')
}

// ── 3. Die alten Adressen leiten weiter ─────────────────────────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  const erwartet = {
    '#/anmeldung': '#/einstellungen/anmeldung',
    '#/registrierung': '#/mitglieder/anfragen',
    '#/anmeldungen': '#/mitglieder/anfragen',
    '#/statistik': '#/mitglieder/uebersicht',
    '#/organigramm': '#/gruppen/organigramm',
    '#/plaene': '#/planrahmen',
  }
  for (const [alt, neu] of Object.entries(erwartet)) {
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }
}

// ── 4. Keine lebende Quelle nennt noch einen gelöschten Komponentennamen ────
{
  const verboten = [
    'src/admin/', 'admin/main.js', 'pages/Anmeldung.vue',
  ]
  const quellen = []
  const durchlaufe = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const voll = path.join(dir, e.name)
      if (e.isDirectory()) durchlaufe(voll)
      else if (/\.(vue|js|mjs)$/.test(e.name)) quellen.push(voll)
    }
  }
  durchlaufe(src)
  const treffer = []
  for (const datei of quellen) {
    const inhalt = fs.readFileSync(datei, 'utf8')
    for (const wort of verboten) {
      if (inhalt.includes(wort)) treffer.push(`${path.relative(src, datei)} -> ${wort}`)
    }
  }
  assert.deepEqual(treffer, [], `gelöschter Baustein wird noch genannt:\n${treffer.join('\n')}`)
}

console.log('N12 Aufräumen: alte Seite/Administration entfernt, Weiterleitungen erhalten')
