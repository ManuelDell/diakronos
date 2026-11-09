import { JSDOM } from 'jsdom'
const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://x/#/personen/liste' })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'SVGElement',
  'MouseEvent', 'navigator', 'location', 'getComputedStyle', 'requestAnimationFrame',
  'cancelAnimationFrame', 'hashchange']) {
  try { globalThis[k] = dom.window[k] } catch {}
}
globalThis.requestAnimationFrame ||= (f) => setTimeout(f, 0)
globalThis.window.addEventListener ||= () => {}
globalThis.window.removeEventListener ||= () => {}

import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'

const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
// Der Zwischenordner liegt NEBEN `frontend/` (Build-Tests laufen in einer
// Kopie des Bäumes) — über `process.cwd()` wäre er im Image woanders.
// Der Zwischenordner steht IM `frontend/`-Ordner (dort liegen `node_modules`
// und `src/`) — woanders fände node die Pakete der App nicht. Die Tests laufen
// im Image in einer KOPIE des Ordners; ein Rest dort wird am Ende entfernt.
const TMP = mkdtempSync(join(process.cwd(), '.zz-ux3b2-'))
process.on('exit', () => { try { rmSync(TMP, { recursive: true, force: true }) } catch {} })
const VUE_URL = import.meta.resolve('vue')
const SRC = resolve('src')

// ── Stummel: die Seiten reden nicht mit dem Server ────────────────────────
const STUBS = {
  [resolve(SRC, 'diakonos/composables/useApi.js')]: resolve(TMP, 'useApi.mjs'),
  [resolve(SRC, 'diakonos/composables/useSession.js')]: resolve(TMP, 'useSession.mjs'),
  [resolve(SRC, 'diakonos/router.js')]: resolve(TMP, 'router.mjs'),
  [resolve(SRC, 'diakonos/composables/useToast.js')]: resolve(TMP, 'useToast.mjs'),
}
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useApi.js')],
  `export async function apiCall(m, a){ return globalThis.__api(m, a) }\nexport default { apiCall }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useSession.js')],
  `import { computed } from '${VUE_URL}'\nexport function useSession(){ return { isAdmin: computed(() => globalThis.__isAdmin === true) } }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/router.js')],
  `export function navigate(h){ globalThis.__nav = h; try { globalThis.window.location.hash = h } catch {} }\n`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useToast.js')],
  `export function showToast(){}\n`)

const cache = new Map()
let n = 0
function compile(abs) {
  if (STUBS[abs]) return STUBS[abs]
  if (cache.has(abs)) return cache.get(abs)
  const z = resolve(TMP, basename(abs) + (n++) + '.mjs')
  cache.set(abs, z)
  let c
  if (abs.endsWith('.vue')) {
    const filename = basename(abs)
    const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename })
    const s = compileScript(descriptor, { id: filename, inlineTemplate: false })
    const t = compileTemplate({
      source: descriptor.template.content, filename, id: filename,
      compilerOptions: { bindingMetadata: s.bindings },
    })
    c = s.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      + '\n' + t.code.replace(/^export function render/m, 'function render')
      + '\n__sfc__.render = render\nexport default __sfc__\n'
  } else c = readFileSync(abs, 'utf8')
  writeFileSync(z, rewrite(c, dirname(abs)))
  return z
}
function rewrite(code, fromDir) {
  return code.replace(/(from\s+|import\s*\(\s*)(['"])([^'"]+)\2/g, (all, pre, q, spec) => {
    if (spec === 'vue') return `${pre}'${VUE_URL}'`
    if (!spec.startsWith('.')) return all
    const abs = resolve(fromDir, spec)
    return `${pre}'${pathToFileURL(compile(abs)).href}'`
  }).replace(/^import\s+['"][^'"]+\.css['"];?$/gm, '')
}

const Vue = await import('vue')
const Personen = (await import(pathToFileURL(compile(resolve(SRC, 'diakonos/pages/Personen.vue'))).href)).default
const tick = (ms = 0) => new Promise(r => setTimeout(r, ms))

// ── Prüfsumme ─────────────────────────────────────────────────────────────
const fehler = []
function pruefe(bedingung, text) {
  if (!bedingung) fehler.push(text)
}

/** Personenzeilen für den Stummel-Server. */
function personen(anzahl, { geloescht = false } = {}) {
  return Array.from({ length: anzahl }, (_, i) => (geloescht && i === 0
    ? {
      name: 'geloescht-abc', vorname: 'Gelöschte Person', nachname: '', email: null,
      telefonnummer: null, postleitzahl: null, wohnort: null, status: 'geloescht',
      gruppen: [],
    }
    : {
      name: `M-${i}`, vorname: `V${i}`, nachname: `N${i}`, full_name: `V${i} N${i}`,
      email: i % 2 ? null : `p${i}@example.org`, telefonnummer: '07071 1',
      postleitzahl: '72070', wohnort: 'Tübingen', 'straße': 'Am Anger', nummer: '3',
      status: i % 3 === 0 ? 'Gast' : 'Mitglied', gruppen: i % 2 ? ['Technik', 'Chor'] : [],
      creation: '2019-05-04 10:00:00', geburtstag: '1980-01-02',
    }))
}

async function starte({ admin, total = 0, breite = 1280, fehlerfall = false, geloescht = false,
  hash = '#/personen/liste', adressbuch = null }) {
  const calls = []
  globalThis.__isAdmin = admin
  globalThis.__nav = null
  dom.window.innerWidth = breite
  globalThis.innerWidth = breite
  try { dom.window.location.hash = hash } catch {}
  globalThis.__api = async (modul, argumente) => {
    calls.push([String(modul).split('.').pop(), argumente || {}])
    if (fehlerfall) throw Object.assign(new Error('Server weg'), { status: 500 })
    if (String(modul).endsWith('get_adressbuch')) {
      const daten = (adressbuch ?? personen(total, { geloescht }))
        .map(({ status, gruppen, creation, ...rest }) => rest)
      return { data: daten }
    }
    if (String(modul).endsWith('get_gruppen_page_data')) return { gruppen_auswahl: [] }
    if (String(modul).includes('wartende')) return { konten: [] }
    const start = Number(argumente?.start) || 0
    const limit = Number(argumente?.limit) || 20
    let daten = personen(total, { geloescht })
    if (argumente?.status) daten = daten.filter(p => p.status === argumente.status)
    return {
      data: daten.slice(start, start + limit),
      total: daten.length,
      gesamt_alle: total,
      status_zaehler: { Mitglied: 20, Gast: 10, 'Passives Mitglied': 3, 'Passiver Gast': 1, Ausgetreten: 2 },
    }
  }
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp(Personen)
  const warns = []
  app.config.warnHandler = (m) => warns.push(String(m).slice(0, 120))
  const vm = app.mount(host)
  await tick(60)
  return { host, app, vm, calls, warns }
}

function aufraeumen(ctx) {
  try { ctx.app.unmount() } catch {}
  ctx.host.remove()
}

const knopf = (host, text) => [...host.querySelectorAll('button')]
  .find(b => b.textContent.trim().includes(text))
const fussText = (host) => host.querySelector('.pz-fuss-text')?.textContent?.trim() ?? null

// ═══ 1. Mitglied (kein Verwaltungsrecht) ═══════════════════════════════════
{
  const ctx = await starte({ admin: false, total: 25, geloescht: true })
  const { host, calls, warns } = ctx
  pruefe(warns.length === 0, `Mitglied: Vue-Warnungen ${JSON.stringify(warns)}`)
  // Quelle: Adressbuch; KEINE Verwaltungsabfrage.
  pruefe(calls.length === 1 && calls[0][0] === 'get_adressbuch',
    `Mitglied: nur get_adressbuch (war ${JSON.stringify(calls.map(c => c[0]))})`)
  // Keine Reiterleiste für eine einzige Ansicht.
  const reiter = host.querySelector('.p3-reiter')
  pruefe(!reiter, 'Mitglied: keine Reiterleiste (eine Ansicht ist keine Wahl)')
  // Keine Verwaltungsfunktionen.
  for (const text of ['Persönliche Daten anzeigen', 'A–Z', 'Tabelle', 'Karten', 'Export', 'Status-Filter']) {
    pruefe(!knopf(host, text), `Mitglied: „${text}“ darf nicht da sein`)
  }
  pruefe(!host.querySelector('.p3-wartende'), 'Mitglied: keine Karte „wartende Konten“')
  // Auch ohne Verwaltungsrecht: die Fußzeile nennt die Anzahl (kein Blättern).
  pruefe(fussText(host) === '25 Personen', `Mitglied: Fußzeile „25 Personen“ (war ${fussText(host)})`)
  pruefe(!knopf(host, 'Weiter') && !knopf(host, 'Zurück'),
    'Mitglied: keine Blätter-Knöpfe ohne serverseitiges Blättern')
  // Gelöschte Person: kein Profil-Link (DSGVO-2d, Befund 5).
  const zeileGeloescht = host.querySelector('[data-name="geloescht-abc"]')
  pruefe(Boolean(zeileGeloescht), 'Mitglied: gelöschte Zeile steht in der Liste')
  pruefe(!zeileGeloescht?.querySelector('a.pz-zeilenziel'),
    'gelöschte Person bekommt KEINEN Profil-Link')
  aufraeumen(ctx)
}

// ═══ 2. Mitgliederadministrator: Funktionen der Mitgliederseite ═══════════
{
  const ctx = await starte({ admin: true, total: 42 })
  const { host, calls, warns } = ctx
  pruefe(warns.length === 0, `Admin: Vue-Warnungen ${JSON.stringify(warns)}`)
  // Reiter: alle vier.
  // UX3j: Reiter sind LINKS (Adresse), keine Umschalter-Knöpfe.
  const reiterText = [...host.querySelectorAll('.p3-reiter a, .p3-reiter button')]
    .map(b => b.textContent.trim())
  for (const label of ['Liste', 'Anfragen', 'Datenschutz', 'Import']) {
    pruefe(reiterText.includes(label), `Admin: Reiter „${label}“ (war ${JSON.stringify(reiterText)})`)
  }
  // Quelle: Mitgliederliste, persönliche Daten NICHT ungefragt.
  const liste = calls.find(c => c[0] === 'get_mitglieder_liste')
  pruefe(Boolean(liste), 'Admin: Quelle ist get_mitglieder_liste')
  pruefe(liste?.[1]?.persoenliche_daten === false,
    'Admin: persönliche Daten werden zuerst NICHT angefordert')
  // Statusfilter mit den echten Werten.
  const alle = knopf(host, 'Alle')
  pruefe(Boolean(alle), 'Admin: Statusfilter „Alle“ steht da')
  for (const status of ['Mitglied', 'Gast', 'Ausgetreten']) {
    pruefe(Boolean(knopf(host, status)), `Admin: Statusfilter „${status}“`)
  }
  // Schalter, Sortierung, Ansicht, wartende Konten, Export.
  pruefe(Boolean(knopf(host, 'Persönliche Daten anzeigen')),
    'Admin: Schalter „persönliche Daten zeigen“ ist da')
  pruefe(Boolean(knopf(host, 'A–Z')), 'Admin: Sortierung ist da')
  pruefe(Boolean(knopf(host, 'Tabelle')) && Boolean(knopf(host, 'Karten')),
    'Admin: Karten/Tabelle-Umschalter ist da')
  pruefe(Boolean(host.querySelector('.p3-wartende')), 'Admin: Karte „wartende Konten“ ist da')
  pruefe(calls.some(c => c[0] === 'get_wartende_konten'),
    'Admin: wartende Konten werden geladen (keine leere Karte)')
  pruefe(Boolean(knopf(host, 'Export')), 'Admin: Export ist da')
  // Status- und Gruppenspalten.
  const kopf = [...host.querySelectorAll('thead th')].map(th => th.textContent.trim())
  for (const spalte of ['Name', 'Status', 'Gruppen', 'E-Mail', 'Dabei seit']) {
    pruefe(kopf.includes(spalte), `Admin: Spalte „${spalte}“ (war ${JSON.stringify(kopf)})`)
  }
  // Ohne Anforderung KEIN persönlicher Wert im Bild, und die Zeile behauptet
  // nicht, das Mitglied habe etwas verborgen.
  pruefe(!host.textContent.includes('@example.org'),
    `Admin: keine E-Mail ohne Anforderung (Text: ${host.textContent.replace(/\s+/g, ' ').slice(0, 300)})`)
  pruefe(!host.textContent.includes('E-Mail verborgen'),
    'Admin: ohne Anforderung steht NICHT „E-Mail verborgen“ (das Mitglied verbirgt nichts)')
  pruefe(host.textContent.includes('nicht angefordert'),
    'Admin: die Zelle sagt ehrlich „nicht angefordert“')

  // Schalter einschalten → Anfrage MIT persönlichen Daten.
  knopf(host, 'Persönliche Daten anzeigen').click()
  await tick(60)
  const mitDaten = calls.filter(c => c[0] === 'get_mitglieder_liste').at(-1)
  pruefe(mitDaten?.[1]?.persoenliche_daten === true,
    'Admin: Schalter an → Server wird um persönliche Daten gebeten')

  // Statusfilter: Klick auf „Gast“ filtert (eine Abfrage mit status).
  knopf(host, 'Gast').click()
  await tick(60)
  const mitStatus = calls.filter(c => c[0] === 'get_mitglieder_liste').at(-1)
  pruefe(mitStatus?.[1]?.status === 'Gast', 'Admin: Statusfilter geht an den Server')
  pruefe(mitStatus?.[1]?.start === 0, 'Admin: Filterwechsel beginnt auf Seite 1')

  // Sortierung: A–Z → Z–A.
  knopf(host, 'A–Z').click()
  await tick(60)
  const sortiert = calls.filter(c => c[0] === 'get_mitglieder_liste').at(-1)
  pruefe(sortiert?.[1]?.sort_order === 'desc', 'Admin: Sortierung umgeschaltet (Z–A)')
  pruefe(Boolean(knopf(host, 'Z–A')), 'Admin: der Knopf zeigt jetzt Z–A')
  aufraeumen(ctx)
}

// ═══ 3. Blättern über drei Seiten, letzte Seite kurz ═══════════════════════
{
  const ctx = await starte({ admin: true, total: 42 })
  const { host, calls } = ctx
  pruefe(fussText(host)?.includes('Seite 1 von 3'), `Admin: Seite 1 von 3 (war ${fussText(host)})`)
  pruefe(host.querySelectorAll('tr.pz-zeile').length === 20, 'Admin: 20 Zeilen auf Seite 1')
  knopf(host, 'Weiter').click(); await tick(60)
  pruefe(fussText(host)?.includes('Seite 2 von 3'), `Admin: Seite 2 von 3 (war ${fussText(host)})`)
  knopf(host, 'Weiter').click(); await tick(60)
  // LETZTE Seite: nur 2 Zeilen — die Form bleibt TABELLE (Befund 2).
  const letzte = calls.filter(c => c[0] === 'get_mitglieder_liste').at(-1)
  pruefe(letzte?.[1]?.start === 40, 'Admin: letzte Seite lädt ab Position 40')
  pruefe(host.querySelectorAll('tr.pz-zeile').length === 2, 'Admin: letzte Seite hat 2 Zeilen')
  pruefe(Boolean(host.querySelector('.pz-tabelle')),
    'Admin: die letzte, kurze Seite bleibt eine Tabelle (kein Umschalten auf Karten)')
  pruefe(fussText(host)?.includes('Seite 3 von 3'), `Admin: Seite 3 von 3 (war ${fussText(host)})`)
  // Fußzeile und Knöpfe bleiben — genau hier verschwand vorher alles.
  pruefe(Boolean(knopf(host, 'Zurück')) && Boolean(knopf(host, 'Weiter')),
    'Admin: Zurück/Weiter stehen auf der letzten Seite noch da')
  pruefe(knopf(host, 'Weiter')?.disabled === true, 'Admin: „Weiter“ ist auf der letzten Seite aus')
  pruefe(knopf(host, 'Zurück')?.disabled === false, 'Admin: „Zurück“ ist auf der letzten Seite an')
  knopf(host, 'Zurück').click(); await tick(60)
  pruefe(fussText(host)?.includes('Seite 2 von 3'), 'Admin: „Zurück“ führt auf Seite 2')

  // Ansicht von Hand auf Karten → bleibt auch nach dem Blättern Karten.
  knopf(host, 'Karten').click(); await tick(20)
  knopf(host, 'Weiter').click(); await tick(60)
  pruefe(!host.querySelector('tr.pz-zeile'), 'Admin: gewählte Karten-Ansicht bleibt beim Blättern')
  aufraeumen(ctx)
}

// ═══ 4. Handy (390 px): Karten UND Fußzeile ═══════════════════════════════
{
  const ctx = await starte({ admin: true, total: 42, breite: 390 })
  const { host } = ctx
  // Die Tabelle steht im DOM (CSS blendet sie aus), die Fußzeile steht
  // AUSSERHALB der Tabelle — deshalb ist sie am Handy da (Befund 3).
  const tabelle = host.querySelector('.pz-tabelle')
  const fuss = host.querySelector('.pz-fuss')
  pruefe(Boolean(tabelle) && Boolean(fuss), 'Handy: Tabelle und Fußzeile stehen im DOM')
  pruefe(!tabelle?.contains(fuss),
    'Handy: die Fußzeile steckt NICHT in der ausgeblendeten Tabelle')
  pruefe(host.querySelector('.pz-fuss')?.parentElement?.className.includes('pz-flaeche'),
    'Handy: die Fußzeile hängt am Kasten (nicht an der Tabelle)')
  pruefe(Boolean(knopf(host, 'Weiter')), 'Handy: „Weiter“ ist da')
  knopf(host, 'Weiter').click(); await tick(60)
  pruefe(fussText(host)?.includes('Seite 2 von 3'), 'Handy: Blättern funktioniert')
  aufraeumen(ctx)
}

// ═══ 5. Mitglied 390 px ═══════════════════════════════════════════════════
{
  const ctx = await starte({
    admin: false, total: 25, breite: 390,
    // Ein Freigabe-Datensatz, wie ihn der Server liefert (ohne Status/Gruppen).
    adressbuch: personen(25).map(({ status, gruppen, creation, full_name, ...rest }) => rest),
  })
  const { host } = ctx
  pruefe(fussText(host) === '25 Personen', `Mitglied Handy: Fußzeile (war ${fussText(host)})`)
  pruefe(!knopf(host, 'Weiter'), 'Mitglied Handy: keine „Weiter“-Lüge')
  // Kein Statuskennzeichen, das die Quelle nicht kennt (keine „Unbekannt“-Marke).
  pruefe(!host.textContent.includes('Unbekannt'),
    'Mitglied: ohne Statusangabe steht keine erfundene Marke „Unbekannt“')
  aufraeumen(ctx)
}

// ═══ 6. Fehler: gestalteter Zustand mit „Erneut versuchen“ ════════════════
{
  const ctx = await starte({ admin: true, total: 5, fehlerfall: true })
  const { host } = ctx
  pruefe(Boolean(host.querySelector('.dk-ui-empty')), 'Fehler: gestalteter Zustand (DkEmpty)')
  const erneut = knopf(host, 'Erneut versuchen')
  pruefe(Boolean(erneut), 'Fehler: „Erneut versuchen“ ist da')
  const vorher = ctx.calls.length
  erneut.click(); await tick(60)
  pruefe(ctx.calls.length > vorher, 'Fehler: „Erneut versuchen“ lädt wirklich neu')
  aufraeumen(ctx)
}

// ═══ 7. Reiter steht in der Adresse ══════════════════════════════════════
// UX3j (Entwurf A3): Die Reiterzeile ist eine Leiste aus LINKS (der Reiter
// steckt in der Adresse, menue.js `personenReiter`) — kein Umschalter, der
// einen Zustand im Speicher ändert. Die Adresse bleibt die Wahrheit, „zurück“
// und Lesezeichen wirken unverändert.
{
  const ctx = await starte({ admin: true, total: 5 })
  const { host } = ctx
  const anfragen = [...host.querySelectorAll('.p3-reiter a')]
    .find(a => a.textContent.trim().startsWith('Anfragen'))
  pruefe(Boolean(anfragen), 'Reiter „Anfragen“ ist ein Link')
  pruefe(anfragen?.getAttribute('href') === '#/personen/anfragen',
    `Reiter-Link zeigt auf die Reiter-Adresse (war ${anfragen?.getAttribute('href')})`)
  // Die beiden übrigen Reiter ebenso — EINE Zeile, echte Adressen.
  for (const [label, href] of [['Liste', '#/personen/liste'], ['Datenschutz', '#/personen/datenschutz'],
    ['Import', '#/personen/import']]) {
    const a = [...host.querySelectorAll('.p3-reiter a')].find(x => x.textContent.trim() === label)
    pruefe(a?.getAttribute('href') === href, `Reiter „${label}“ → ${href}`)
  }
  aufraeumen(ctx)
}

// ═══ 8. Unbekannter Reiter in der Adresse fällt auf die Liste ════════════
{
  const ctx = await starte({ admin: false, total: 3, hash: '#/personen/gibtsnicht' })
  pruefe(ctx.calls[0]?.[0] === 'get_adressbuch',
    'unbekannter Reiter in der Adresse → Liste (kein leerer Bildschirm)')
  aufraeumen(ctx)
}

// ═══ 9. Übersicht-Kachel: ?status=Mitglied wählt den Filter vor ═══════════
{
  const ctx = await starte({ admin: true, total: 30, hash: '#/personen/liste?status=Mitglied' })
  const { calls } = ctx
  const erste = calls.find(c => c[0] === 'get_mitglieder_liste')
  pruefe(erste?.[1]?.status === 'Mitglied',
    `Kachel: erste Abfrage mit status=Mitglied (war ${JSON.stringify(erste?.[1])})`)
  knopf(ctx.host, 'Gast').click(); await tick(60)
  pruefe(dom.window.location.hash === '#/personen/liste?status=Gast',
    `Filterwechsel schreibt die Adresse (war ${dom.window.location.hash})`)
  knopf(ctx.host, 'Gast').click(); await tick(60)
  pruefe(dom.window.location.hash === '#/personen/liste',
    `Abwählen entfernt den Status aus der Adresse (war ${dom.window.location.hash})`)
  aufraeumen(ctx)
}
{
  const ctx = await starte({ admin: true, total: 30, hash: '#/personen/liste?status=Unsinn' })
  const erste = ctx.calls.find(c => c[0] === 'get_mitglieder_liste')
  pruefe(erste?.[1]?.status === undefined, 'unbekannter Status in der Adresse → Alle')
  aufraeumen(ctx)
}

// ═══ 10. Mitglied: verborgene E-Mail heißt „E-Mail verborgen“ ════════════
{
  const ctx = await starte({ admin: false, total: 4 })
  pruefe(ctx.host.textContent.includes('E-Mail verborgen'),
    'Mitglied: leere E-Mail in der Freigabe-Sicht → „E-Mail verborgen“')
  pruefe(!ctx.host.textContent.includes('nicht angefordert'),
    'Mitglied: kein „nicht angefordert“ (es gibt keinen Schalter)')
  aufraeumen(ctx)
}

if (fehler.length) {
  console.error('UX3b2 Mount: ' + fehler.length + ' Fehlschlag/Fehlschläge')
  for (const f of fehler) console.error(' - ' + f)
  process.exit(1)
}
console.log('UX3b2 Mount: alle Proben grün')
process.exit(0)
