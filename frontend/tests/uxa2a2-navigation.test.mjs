import assert from 'node:assert/strict'
import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

/**
 * UX-A2a2 — Mitglieder-Navigation: ARIA-Verweis, toter Code, EIN Zähler-Takt.
 *
 * Nacharbeit aus dem Opus-Re-Review zu UX-A2a (drei Punkte):
 *  1. DkBereichsliste.vue: `aria-describedby` zeigte auf `unter-anfragen`, der
 *     unsichtbare Text hiess `unter-anfragen-text` — der Verweis lief ins
 *     Leere. Jetzt dieselbe Kennung, und der unsichtbare Text steht NUR beim
 *     Eintrag mit Unterpunkten (v-if), nicht bei jedem Eintrag.
 *  2. Bereich.vue: der Rest des toten Ereignisses `unterbereich-wechsel`
 *     (Empfänger in der Vorlage + Funktion `unterbereichWechseln`) ist weg.
 *  3. Zähler: EIN gemeinsamer Takt für Seitenleiste und Bereich — ein
 *     Intervall, eine Anfrage je Takt, keine Anfrage beim Bereichswechsel,
 *     Abfrage nur für Administratoren.
 *
 * Punkt 1 wird am ECHTEN DOM geprüft (SFC mit @vue/compiler-sfc übersetzt,
 * serverseitig gerendert), Punkt 3 am ECHTEN Composable (mit nachgebautem
 * Vue und gefälschtem `apiCall`). Nur so fallen ein toter ARIA-Verweis und
 * zwei laufende Intervalle überhaupt auf — ein Textvergleich sieht beides
 * nicht.
 *
 * UX3j (Entwurf A3, 08.11.): Der Befund „aria-describedby läuft ins Leere“
 * galt für die SEITLICHE Bereichsliste, die A3 abgeschafft hat (die
 * Komponente `DkBereichsliste.vue` lebt unverändert, wird im Personen-Bereich
 * aber nicht mehr benutzt). Die Prüfung läuft deshalb jetzt gegen die
 * Reiterzeile (`DkReiter.vue`), die in JEDEM Reiter steht: EINE Leiste,
 * eindeutige Werte, aktiver Eintrag barrierefrei markiert. Der Personen-Rahmen
 * ist seit A3 `pages/Personen.vue` (Bereich.vue ist nur sein Adress-Ziel).
 */
const root = new URL('../src/diakonos/', import.meta.url)
const quellePfad = name => fileURLToPath(new URL(name, root))
const lies = name => readFileSync(new URL(name, root), 'utf8')

/** Oberer Teil der Vorlage einer .vue-Datei (ohne HTML-Kommentare). */
function vorlage(quelle) {
  const anfang = quelle.indexOf('<template>')
  const ende = quelle.lastIndexOf('</template>')
  return quelle.slice(anfang, ende).replace(/<!--[\s\S]*?-->/g, '')
}

/** Skript-Teil einer .vue-Datei. */
function skript(quelle) {
  const a = quelle.indexOf('<script setup>') + '<script setup>'.length
  return quelle.slice(a, quelle.indexOf('</script>'))
}

/**
 * Verzeichnis, in dem nebenmodule `vue`/`@vue/compiler-sfc` auflösen: dort,
 * wo die node_modules liegen. Im Image-Build ist das `<repo>/frontend`
 * (Arbeitsverzeichnis = `frontend`), im Repo ist es derselbe Ordner
 * (`frontend/node_modules` neben `tests/`).
 */
function modulVerzeichnis() {
  // 1) das Arbeitsverzeichnis und seine Eltern (im Image-Build: <repo>/frontend),
  // 2) das App-Verzeichnis der Quelle (dort liegt im Repo die node_modules).
  const kandidaten = []
  let lauf = process.cwd()
  for (let tiefe = 0; tiefe < 4; tiefe += 1) {
    kandidaten.push(lauf)
    const hoch = dirname(lauf)
    if (hoch === lauf) break
    lauf = hoch
  }
  kandidaten.push(fileURLToPath(root))
  for (const kandidat of kandidaten) {
    for (const paket of ['vue', '@vue/compiler-sfc']) {
      if (existsSync(join(kandidat, 'node_modules', ...paket.split('/'), 'package.json'))) {
        return kandidat
      }
    }
  }
  throw new Error('node_modules mit vue nicht gefunden — Test braucht das App-Verzeichnis')
}
const MODUL_DIR = modulVerzeichnis()
/** Pfad für ein nebenmodul, das Imports aus dem App-Verzeichnis auflöst. */
const beiModulen = name => join(MODUL_DIR, name)

// ── 1. ARIA: Kennung und Verweis stimmen überein (gerendertes DOM) ─────────
{
  const { parse, compileScript, compileTemplate } = await import('@vue/compiler-sfc')
  const { createSSRApp, h } = await import('vue')
  const { renderToString } = await import('vue/server-renderer')

  const datei = quellePfad('components/ui/DkReiter.vue')
  const { descriptor } = parse(readFileSync(datei, 'utf8'), { filename: datei })
  const sfcSkript = compileScript(descriptor, { id: 'uxa2a2' })
  const sfcVorlage = compileTemplate({
    source: descriptor.template.content,
    filename: datei,
    id: 'uxa2a2',
    compilerOptions: { bindingMetadata: sfcSkript.bindings },
  })
  assert.equal(sfcVorlage.errors.length, 0,
    `Vorlage übersetzt: ${sfcVorlage.errors[0]?.message || ''}`)

  // Skript + Render-Funktion in EIN ladbares Modul legen — im App-Verzeichnis,
  // damit `vue` und `@vue/compiler-sfc` auflösen (anderswo findet Node sie
  // nicht). Der Name beginnt mit `.tmp-`, wird also nie als Test geladen.
  const ziel = beiModulen(`.tmp-uxa2a2-bz-${process.pid}-${Date.now()}.mjs`)
  writeFileSync(ziel, [
    `import { createSSRApp } from 'vue'`,
    sfcSkript.content.replace(/export default/, 'const __sfc ='),
    sfcVorlage.code.replace('export function render', 'function render'),
    '__sfc.render = render',
    'export default __sfc',
  ].join('\n'))
  const { default: Komponente } = await import(pathToFileURL(ziel).href)
  rmSync(ziel, { force: true })
  const optionen = [
    { value: 'liste', label: 'Liste', href: '#/personen/liste' },
    { value: 'anfragen', label: 'Anfragen', href: '#/personen/anfragen', zahl: 3 },
    { value: 'datenschutz', label: 'Datenschutz', href: '#/personen/datenschutz' },
    { value: 'import', label: 'Import', href: '#/personen/import' },
  ]
  const html = await renderToString(createSSRApp({
    render: () => h(Komponente, { modelValue: 'anfragen', options: optionen, ariaLabel: 'Bereiche von Personen' }),
  }))

  // GENAU EINE Reiterzeile mit Namen (kein zweiter Navigationsblock).
  assert.equal((html.match(/<nav\b/g) || []).length, 1, 'genau eine Reiterzeile')
  assert.ok(html.includes('aria-label="Bereiche von Personen"'), 'die Leiste hat einen Namen')
  // Jeder Eintrag ist ein Link mit eigener Adresse; der aktive trägt
  // `aria-current="page"` (Farbe ist nie der einzige Träger, Ä4).
  const punkte = [...html.matchAll(/<a\b[^>]*>/g)].map(m => m[0])
  assert.equal(punkte.length, 4, `vier Reiter (gefunden: ${punkte.length})`)
  for (const [wert, href] of [['liste', '#/personen/liste'], ['anfragen', '#/personen/anfragen'],
    ['datenschutz', '#/personen/datenschutz'], ['import', '#/personen/import']]) {
    assert.ok(punkte.some(p => p.includes(`href="${href}"`) && p.includes(`data-reiter="${wert}"`)),
      `Reiter „${wert}“ verlinkt ${href}`)
  }
  const aktiv = punkte.filter(p => p.includes('aria-current="page"'))
  assert.equal(aktiv.length, 1, 'genau EIN aktiver Eintrag (kein doppeltes aria-current)')
  assert.ok(aktiv[0].includes('data-reiter="anfragen"'), 'aktiv ist der offene Reiter')
  assert.ok(aktiv[0].includes('class="dk-ui-reiter-punkt is-active"'), 'der aktive Eintrag ist markiert')
  // Kennzahl nur als echte Zahl — und nur am Eintrag, der sie trägt.
  const zahlen = [...html.matchAll(/<span class="dk-ui-reiter-zahl">([^<]*)<\/span>/g)].map(m => m[1])
  assert.deepEqual(zahlen, ['3'], 'die Zahl steht genau einmal (an „Anfragen“)')
  // Keine Kennung doppelt (IDs müssen eindeutig sein).
  const alleIds = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1])
  assert.equal(new Set(alleIds).size, alleIds.length, 'keine doppelten IDs im DOM')
}

// ── 2. Personen-Rahmen: EINE Reiterzeile, kein toter Wechsel ──────────────
{
  const bereich = lies('pages/Personen.vue')
  const t = vorlage(bereich)
  const s = skript(bereich)

  assert.ok(!t.includes('unterbereich-wechsel'), 'kein Empfänger für das tote Ereignis in der Vorlage')
  assert.ok(!t.includes('unterbereichWechseln'), 'keine Bindung an die entfallene Funktion')
  assert.ok(!/\bunterbereichWechseln\b/.test(bereich), 'die Funktion selbst ist entfernt')
  // UX3j: Der Unterbereich kommt über die Eigenschaft aus der Adresse.
  assert.ok(t.includes(':unterbereich="aktiverUnterbereich"'), 'Unterbereich kommt als Eigenschaft')
  // Genau EINE Hauptebene: die Reiterzeile als Baustein (DkReiter), keine
  // seitliche Liste mehr daneben.
  assert.ok(t.includes('<DkReiter'), 'Reiterzeile ist der EINE Baustein')
  assert.ok(!/DkBereichsliste/.test(t), 'keine seitliche Bereichsliste (A3)')
  assert.ok(!/class="mb-raster"/.test(t), 'kein Zwei-Spalten-Raster (A3)')
  // Das Adress-Ziel der alten Seitennamen lädt denselben Rahmen.
  const ziel = lies('pages/mitglieder/Bereich.vue')
  assert.ok(vorlage(ziel).includes('<Personen'), 'Bereich.vue lädt den EINEN Personen-Rahmen')
}

// ── 3. EIN Takt: Seitenleiste + Bereich, eine Anfrage, nur für Admins ─────
{
  const pfad = quellePfad('composables/useVerwaltung.js')
  let quelle = readFileSync(pfad, 'utf8')

  // `apiCall` fälschen: Aufrufe zählen, Antwort mit einer Zahl liefern.
  // Die Hilfsmodule liegen im App-Verzeichnis (dort löst `vue` auf; ein
  // Nachbarmodul ohne eigene package.json erbt den Typ `module`).
  const fakeUseApi = pathToFileURL(beiModulen(`.tmp-uxa2a2-api-${process.pid}-${Date.now()}.mjs`)).href
  writeFileSync(fileURLToPath(fakeUseApi), [
    'export const aufrufe = { anzahl: 0, zahl: 7 }',
    'export async function apiCall() {',
    '  aufrufe.anzahl += 1',
    '  return { anfragen: aufrufe.zahl }',
    '}',
  ].join('\n'))
  quelle = quelle.replace(/from '\.\/useApi\.js'/, `from '${fakeUseApi}'`)
  // `useSession` fälschen (kein window/Boot im Test).
  const fakeSession = pathToFileURL(beiModulen(`.tmp-uxa2a2-session-${process.pid}-${Date.now()}.mjs`)).href
  writeFileSync(fileURLToPath(fakeSession), [
    'import { ref, computed } from "vue"',
    'export const rechte = { istAdmin: false, istSystemManager: false }',
    'export function useSession() {',
    '  return {',
    '    isAdmin: computed(() => rechte.istAdmin),',
    '    istSystemManager: computed(() => rechte.istSystemManager),',
    '  }',
    '}',
  ].join('\n'))
  quelle = quelle.replace(/from '\.\/useSession\.js'/, `from '${fakeSession}'`)

  const modulDatei = beiModulen(`.tmp-uxa2a2-verwaltung-${process.pid}-${Date.now()}.mjs`)
  writeFileSync(modulDatei, quelle)
  // 'vue' loest die Datei im Repo auf (das Composable importiert es regulaer).
  const modul = await import(pathToFileURL(modulDatei).href)
  const api = await import(fakeUseApi)
  const session = await import(fakeSession)
  const { nextTick } = await import('vue')

  // Intervalle mitzählen: setInterval/clearInterval umlegen.
  const echteIntervalle = { start: globalThis.setInterval, stop: globalThis.clearInterval }
  let laufende = new Set()
  let gestartet = 0
  globalThis.setInterval = (fn, ms) => {
    gestartet += 1
    const id = echteIntervalle.start(fn, ms)
    laufende.add(id)
    return id
  }
  globalThis.clearInterval = (id) => { laufende.delete(id); return echteIntervalle.stop(id) }

  try {
    // Ohne Administrator: zwei Anzeigen beobachten, es wird NICHT gefragt.
    session.rechte.istAdmin = false
    session.rechte.istSystemManager = false
    const abmeldenA = modul.anfragenZaehlerBeobachten()
    const abmeldenB = modul.anfragenZaehlerBeobachten()
    await nextTick()
    assert.equal(api.aufrufe.anzahl, 0, 'ohne Mitgliederadministrator wird nicht gefragt')
    assert.equal(gestartet, 1, 'ein gemeinsames Intervall für beide Anzeigen')
    assert.equal(modul.anfragenZaehler.value, null, 'ohne Recht bleibt die Zahl leer (keine erfundene 0)')

    // Speichern/Schalten simulieren: jetzt Administrator.
    session.rechte.istAdmin = true
    await modul.anfragenZahlAuffrischen()
    assert.equal(api.aufrufe.anzahl, 1, 'als Administrator genau eine Anfrage')
    assert.equal(modul.anfragenZaehler.value, 7, 'der Stand kommt aus der Antwort')

    // Kein zweites Intervall für die zweite Anzeige (Bereich neben Leiste).
    assert.equal(gestartet, 1, 'Seitenleiste + Bereich teilen EIN Intervall')
    assert.equal(laufende.size, 1, 'genau ein laufendes Intervall')

    // Zwei Takt-Schläge hintereinander: JEDER holt genau einmal. So ist
    // belegt, dass ein Schlag EINE Anfrage auslöst, egal wie viele Anzeigen
    // beobachten (der Beobachter-Zähler oben ist 2).
    await modul.anfragenZahlAuffrischen()
    await modul.anfragenZahlAuffrischen()
    assert.equal(api.aufrufe.anzahl, 3, 'je Takt eine Anfrage, obwohl zwei Anzeigen beobachten')
    // Erste Anzeige abmelden: das Intervall läuft weiter, noch ein Beobachter.
    abmeldenB()
    assert.equal(laufende.size, 1, 'ein Beobachter übrig — Intervall bleibt')
    // Letzter Beobachter meldet sich ab: kein Intervall mehr.
    abmeldenA()
    assert.equal(laufende.size, 0, 'ohne Anzeige läuft kein Intervall mehr')
  } finally {
    globalThis.setInterval = echteIntervalle.start
    globalThis.clearInterval = echteIntervalle.stop
    for (const id of laufende) echteIntervalle.stop(id)
    rmSync(modulDatei, { force: true })
    rmSync(fileURLToPath(fakeUseApi), { force: true })
    rmSync(fileURLToPath(fakeSession), { force: true })
  }
}

// ── 4. Die Seitenleiste hält den Takt NICHT selbst ─────────────────────────
{
  const sidebar = lies('components/AppSidebar.vue')
  // UX3j: Der Personen-Rahmen ist `pages/Personen.vue` (Bereich.vue ist nur
  // noch sein Adress-Ziel und hat gar kein Skript mehr).
  const bereich = lies('pages/Personen.vue')
  // Kommentare zählen nicht (sie nennen die Wörter absichtlich).
  const ohneKommentare = q => q
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
  const s = ohneKommentare(skript(sidebar))
  const b = ohneKommentare(skript(bereich))

  assert.ok(s.includes('anfragenZaehlerBeobachten()'), 'Seitenleiste beobachtet die gemeinsame Kennzahl')
  assert.ok(!s.includes('setInterval'), 'die Seitenleiste setzt kein eigenes Intervall mehr')
  assert.ok(!b.includes('setInterval'), 'der Bereich setzt kein eigenes Intervall')
  assert.ok(!b.includes('anfragenZahlLaden'), 'der Bereich fragt nicht selbst')
  assert.ok(b.includes('anfragenZaehler'), 'der Bereich LIEST den gemeinsamen Stand')
  // Kein Nachladen bei jedem Wechsel (Review-Punkt 3): kein watch auf den Wert.
  assert.ok(!/watch\(\s*aktiverEintragValue/.test(b), 'kein Nachladen bei jedem Reiterwechsel')
  // Die Anfragen-Seite zieht die Kennzahl nach einer Handlung nach.
  const reg = ohneKommentare(skript(lies('pages/Registrierung.vue')))
  assert.ok(reg.includes('anfragenZahlAuffrischen'), 'Aufnehmen/Ablehnen frischt die Kennzahl auf')
}

console.log('UX-A2a2 Mitglieder-Navigation: bestanden')
