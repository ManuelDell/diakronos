/**
 * FIX-8 — Werkzeug: findet Bezeichner im SKRIPT von `.vue`-Dateien (sowie in
 * `.js`/`.mjs` unter `frontend/src`), die nirgends gebunden sind.
 *
 * Anlass: In UX2d3a rief `MitgliedDetail.vue` `useLadeSkelett()` ohne Import
 * auf — ein `ReferenceError` zur Laufzeit, die Seite war tot. FIX-7
 * (`vorlagen-bezeichner.mjs`) prueft nur TEMPLATE-Ausdruecke gegen die
 * Skript-Bindungen; ein im `<script setup>` vergessener Import ist dort
 * unsichtbar.
 *
 * Vorgehen (ohne neues Werkzeug — Begruendung im Kopf der Testdatei):
 *   1. `.vue` per `@vue/compiler-sfc` zerlegen; geprueft werden `<script>`
 *      und `<script setup>` (auch `lang="ts"`).
 *   2. Jedes Skript per `@babel/parser` (`sourceType: module`) zu einem AST
 *      wandeln — die Scope-Analyse liegt in `script-bezeichner-kern.mjs`.
 *   3. Jede Verwendung ohne Bindung ist ein Befund, sofern der Name nicht in
 *      `ERLAUBT` (`script-erlaubt.mjs`) mit Grund steht.
 *   4. Namen aus `ERLAUBT_ZUSAMMENGESETZT` (zusammengesetzte Browser-Typen wie
 *      `Uint8Array`) sind nur erlaubt, wenn die DATEI sie bereits ueber
 *      `globalThis.<Name>` anspricht. Sonst lautet der Befund: „als
 *      globalThis.X schreiben“.
 *
 * Grenzen (Test haelt sie fest):
 *   * keine Datenfluss-Analyse (`let x` bindet, auch wenn `x` erst spaeter
 *     zugewiesen wird — das ist `undefined`, kein `ReferenceError`).
 *   * Vue-Compiler-Makros (`defineProps` …) stehen in der Erlaubt-Liste.
 *   * `*.test.mjs` sind ausgenommen: sie laufen unter `node --test`, nicht im
 *     Browser, und gehoeren zu den Testlaeufen (die sie selbst aufrufen).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { analysiereSkript, bindungenVon, pruefeSkriptCode } from './script-bezeichner-kern.mjs'
import { ERLAUBT, ERLAUBT_ZUSAMMENGESETZT } from './script-erlaubt.mjs'

export { ERLAUBT, ERLAUBT_ZUSAMMENGESETZT }
export { analysiereSkript, pruefeSkriptCode }

/**
 * Dateien, die NICHT geprueft werden. Jeder Eintrag braucht einen Grund.
 */
export const AUSGENOMMEN = new Map([
  [
    '*.test.mjs',
    'Node-Testdatei: laeuft unter `node --test` (Buffer/process/import.meta.url), nicht im Browser; ' +
      'sie wird von der node-Testliste in backend/Dockerfile aufgerufen',
  ],
])

/** Ist diese Datei eine Testdatei (von der Pruefung ausgenommen)? */
export function istTestdatei(datei) {
  return basename(datei).endsWith('.test.mjs')
}

/**
 * Hat die Datei den Namen schon ueber `globalThis.` angesprochen?
 * `code` ist die Quelldatei. Ein Vorkommen als `globalThis.Name` genuegt —
 * dann ist die Abhaengigkeit sichtbar und der Node-Test geht denselben Weg.
 */
export function sprichtGlobalThisAn(code, name) {
  return new RegExp(`globalThis\\s*\\.\\s*${name.replace(/[$]/g, '\\$')}\\b`).test(code)
}

/** Prueft eine `.vue`-Quelle: nur die Skriptbloecke. */
export function pruefeVueQuelle(quelle, datei, sfc) {
  const { descriptor, errors } = sfc.parse(quelle, { filename: datei })
  if (errors && errors.length) {
    return {
      fehlend: [],
      fehler: `${datei}: SFC-Fehler — ${errors.map((e) => e.message || String(e)).join('; ')}`,
    }
  }
  const fehlend = []
  const bloecke = [descriptor.script, descriptor.scriptSetup].filter((b) => b && b.content)
  const spracheVon = (block) => ((block.lang || 'js').toLowerCase() === 'ts' ? 'ts' : 'js')
  // Vue kompiliert `<script>` und `<script setup>` zu EINEM Modul: die in
  // beiden Bloecken deklarierten Namen bilden eine gemeinsame Menge.
  const gemeinsam = new Set()
  for (const block of bloecke) {
    for (const n of bindungenVon(block.content, spracheVon(block)) || []) gemeinsam.add(n)
  }
  for (const block of bloecke) {
    const befund = pruefeSkriptCode(block.content, datei, spracheVon(block), ERLAUBT, gemeinsam)
    if (befund.fehler) return befund
    const versatz = block.loc ? block.loc.start.line : 0
    for (const f of befund.fehlend) {
      fehlend.push({ name: f.name, zeile: f.zeile + versatz, hinweis: null })
    }
  }
  return { fehlend, fehler: null }
}

/**
 * Prueft eine einzelne Datei (`.vue`, `.js` oder `.mjs`).
 * Ergebnis: `{ fehlend: [{ name, zeile, hinweis }], fehler: string|null }`.
 */
export function pruefeDatei(datei, sfc, nurQuelle = null) {
  if (istTestdatei(datei)) return { fehlend: [], fehler: null }
  const quelle = nurQuelle ?? readFileSync(datei, 'utf8')
  const befund = datei.endsWith('.vue')
    ? pruefeVueQuelle(quelle, datei, sfc)
    : pruefeSkriptCode(quelle, datei, 'js')
  if (befund.fehler) return befund
  // Klasse 2: zusammengesetzte Browser-Typen ohne globalThis.
  const fehlend = befund.fehlend.map((f) => {
    if (!ERLAUBT_ZUSAMMENGESETZT.has(f.name)) return { ...f, hinweis: null }
    if (sprichtGlobalThisAn(quelle, f.name)) return null
    return { ...f, hinweis: ERLAUBT_ZUSAMMENGESETZT.get(f.name) }
  })
  const bereinigt = fehlend.filter(Boolean)
  if (bereinigt.length !== befund.fehlend.length) {
    // Ein erlaubter Klasse-2-Name war erlaubt — er faellt still weg.
    return { fehlend: bereinigt, fehler: null }
  }
  return { fehlend: bereinigt, fehler: null }
}

/** Alle `.vue`/`.js`/`.mjs` unter einem Ordner (ohne `node_modules`/`dist`). */
export function skriptDateien(wurzel) {
  const ergebnis = []
  const lauf = (ordner) => {
    for (const eintrag of readdirSync(ordner).sort()) {
      if (eintrag === 'node_modules' || eintrag === 'dist') continue
      const voll = join(ordner, eintrag)
      if (statSync(voll).isDirectory()) lauf(voll)
      else if (voll.endsWith('.vue') || voll.endsWith('.js') || voll.endsWith('.mjs')) ergebnis.push(voll)
    }
  }
  lauf(wurzel)
  return ergebnis
}

/**
 * Prueft alle Skripte unter `wurzel`. Liefert `{ datei, fehlend, fehler }` je
 * Datei; mit `nurAbweichende` bleiben saubere Dateien weg.
 */
export function pruefeBaum(wurzel, sfc, nurAbweichende = false) {
  const befunde = []
  for (const datei of skriptDateien(wurzel)) {
    const befund = pruefeDatei(datei, sfc)
    const eintrag = { datei: relative(wurzel, datei), fehlend: befund.fehlend, fehler: befund.fehler }
    if (nurAbweichende && !eintrag.fehlend.length && !eintrag.fehler) continue
    befunde.push(eintrag)
  }
  return befunde
}

/** `frontend/` — Wurzel fuer den Standardaufruf (auch im Image `/build/`). */
export const FRONTEND = fileURLToPath(new URL('../', import.meta.url))
