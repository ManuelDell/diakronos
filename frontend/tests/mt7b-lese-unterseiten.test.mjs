/**
 * MT-7b — Lese-Unterseiten: zurück zur GEFILTERTEN Liste, Fokus, Druck-Tokens.
 *
 * Folgekarte zu MT-7 (drittes Review). Geprüft wird VERHALTEN, nicht nur
 * Quelltext — die Seiten werden in jsdom wirklich gemountet (SFC über
 * `vue/compiler-sfc` übersetzt, `fetch` wie der Server, `window.location` als
 * echter jsdom-Verlauf):
 *
 *   A  Liste mit `?q=` → Beitrag öffnen → „‹ zurück“ landet auf der Liste MIT
 *      `?q=`, und zwar über den Router in EINEM Schritt (kein `history.back()`,
 *      das dort ohnehin nie gegriffen hat: die Leseseite liest IHREN
 *      Verlaufs-Eintrag, das Merkmal lag im Eintrag der Liste).
 *   B  Der Fokus auf der Überschrift kommt NACH dem Laden — bei einer Antwort
 *      über 300 ms steht vorher das Skelett, und der Seitenkopf existiert noch
 *      nicht (`fokusAufTitel` lief bisher im Versuch, also zu früh).
 *   C  Der Druck-Block in `tokens.css` leitet aus dem HELLEN Satz ab: für JEDEN
 *      Namen, den ein Dunkel-Block setzt, gilt im Druckmedium der helle Wert.
 *   D  Mittelklick/Strg-Klick auf „Ähnliche Artikel“ öffnet normal (kein
 *      `preventDefault`) — der Router greift nur beim einfachen Klick ein.
 *   E  `?bearbeiten=` holt die Liste EINMAL (nicht zweimal).
 *   F  403 auf der Leseseite → „keine Berechtigung“-Katalogtext, KEIN
 *      „Erneut versuchen“.
 *
 * Läuft ohne Browser (`node --test`), braucht `node_modules` (vue, jsdom).
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

// Der Rückweg-Merker ist importfrei — direkt aus dem Quellbaum laden, nicht aus
// dem Temp-Baum (der je Test wieder verschwindet).
import { rueckwegBleibtGueltig, rueckwegKennung, rueckwegMerken, rueckwegVergessen, rueckwegZiel } from '../src/diakonos/composables/zurueckWege.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRC = path.join(FRONTEND, 'src')

function lies(rel) {
  return readFileSync(path.join(FRONTEND, rel), 'utf8')
}

// ── CSS ohne Kommentare (Erklärungen dürfen Befunde nicht „grün machen“) ───
function ohneCssKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}

// ═══════════════════════════════════════════════════════════════════════════
// C — Druck-Tokens (reine Dateiprüfung, kein Browser nötig)
// ═══════════════════════════════════════════════════════════════════════════

/** Deklarationen eines CSS-Blocks ab `start` (Klammer-Zählung, bis sie zu ist). */
function blockAb(text, start) {
  let depth = 0
  let i = start
  for (; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1
    else if (text[i] === '}') {
      depth -= 1
      if (depth === 0) return text.slice(start + 1, i)
    }
  }
  throw new Error('CSS-Block ohne schließende Klammer')
}

/**
 * EIN Umleitungsschritt: `var(--x)` → `--x`, sonst der Wert selbst. Der Druck-
 * Test braucht genau einen Schritt — der Druckblock setzt JEDEN Namen, auch die
 * Ziele; eine Kette würde einen Fehler (`--text: var(--dk-warm-100)`) über den
 * hellen Wert „glattbügeln“ und der Test wäre blind.
 */
function einSprung(wert) {
  const m = /^var\(\s*(--[\w-]+)\s*\)$/.exec(String(wert || '').trim())
  return m ? `var(${m[1]})` : String(wert || '').trim()
}

/** Name → zuletzt genannter Wert (so entscheidet die Kaskade innerhalb einer Ebene). */
function deklarationen(text) {
  const karte = new Map()
  // Verschachtelte Regeln (`:root { .x { --a: … } }`) würden sonst die äußere
  // Karte verfälschen: der Text bis zur ersten `{` gehört der Regel selbst —
  // alles ab einer `{` wird abgeschnitten.
  const eigene = text.includes('{') ? text.slice(0, text.indexOf('{')) : text
  for (const m of eigene.matchAll(/(--[\w-]+)\s*:\s*([^;}]+)/g)) {
    karte.set(m[1], m[2].trim().replace(/\s+/g, ' '))
  }
  return karte
}

/**
 * Media-Bereiche einer CSS-Datei: für jeden `@media print`-Block seine Grenzen
 * (Inhalt zwischen den zugehörigen Klammern, inklusive verschachtelter Blöcke).
 * Die Token-Datei hat genau EINEN Druckblock.
 */
function druckBereich(text) {
  const treffer = /@media\s+print\s*\{/g.exec(text)
  assert.ok(treffer, 'tokens.css: kein `@media print`-Block gefunden')
  const ab = treffer.index + treffer[0].length - 1 // die Klammer selbst
  let depth = 0
  for (let i = ab; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1
    else if (text[i] === '}') {
      depth -= 1
      if (depth === 0) return { ab, bis: i }
    }
  }
  throw new Error('tokens.css: Druckblock ohne schließende Klammer')
}

/**
 * KASKADE-AUFLÖSUNG (Review-Punkt 3): Wert eines Namens unter einer Menge von
 * Regeln. Die Regeln stehen in Dateireihenfolge; entschieden wird nach
 * Spezifität, bei Gleichstand nach der späteren Stelle — genau wie im Browser.
 */
function spezifitaet(selektor) {
  const s = selektor.trim()
  // `[data-theme="dark"]`/`[data-theme]` = Attribut (0,1,0). `:root` zählt
  // hier als Typ (0,0,1), `:root` IN einem Attribut (`:root[data-theme=…]`)
  // ebenso. Zwei Selektoren einer Liste zählen einzeln; wir werten den
  // BESTEN (der Block gilt für das Element, wenn irgendein Teil passt).
  const attribute = (s.match(/\[[^\]]*\]/g) || []).length
  const klassen = (s.match(/\.[\w-]+|:[\w-]+\(/g) || []).length
  const typen = /:root/.test(s) || /^(?:html|body)\b/.test(s) ? 1 : 0
  return attribute * 100 + klassen * 10 + typen
}

/**
 * Position der schließenden Klammer zu der `{` an `start` (Klammer-Zählung).
 */
function klammerEnde(text, start) {
  let depth = 0
  for (let i = start; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1
    else if (text[i] === '}') {
      depth -= 1
      if (depth === 0) return i
    }
  }
  return text.length
}

/**
 * Regeln einer Datei in Reihenfolge: { selektoren, deklarationen, stelle,
 * kontext } — `kontext` ist leer für Regeln auf oberster Ebene und trägt bei
 * verschachtelten Regeln den Text der umgebenden At-Regel (z. B. `@media print`).
 * Der Druck-Block wird also NICHT als eigener Block ersetzt (der alte Fehler,
 * Review-Punkt 3), sondern mit seinem Kontext gefunden.
 */
function alleRegeln(text) {
  const regeln = []
  // Stapel der offenen Blöcke: at-Regeln (mit ihrem Kopf, z. B. `@media print`)
  // und die eigentliche Regeln. Beim Schließen entsteht aus dem Stapel der
  // Kontext einer Regel — so taucht der Druckblock mit `@media print` auf.
  const stapel = []
  let kopfAb = 0
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i]
    if (c === '{') {
      const kopf = text.slice(kopfAb, i).trim()
      const atTreffer = /^@(?:media|supports|layer|scope)\b([^{]*)$/.exec(kopf)
      stapel.push({
        art: atTreffer ? 'at' : 'regel',
        kopf,
        selektoren: atTreffer ? '' : kopf,
        at: atTreffer ? `@${atTreffer[0].replace(/^@/, '').trim()}` : '',
        deklarationen: atTreffer ? null : new Map(),
        kopfZeichen: i,
      })
      kopfAb = i + 1
    } else if (c === '}') {
      const rahmen = stapel.pop()
      if (rahmen) {
        const kontext = stapel.filter((r) => r.art === 'at').map((r) => r.at).join(' ')
        if (rahmen.art === 'regel') {
          // Deklarationen stehen zwischen der eigenen `{` und dem passenden `}`.
          // Die Lage ergibt sich aus Tiefe und Klammer-Zählung (ein `ende`
          // mitten aus dem Stapel wäre falsch, sobald Regeln verschachtelt sind).
          regeln.push({
            selektoren: rahmen.selektoren,
            deklarationen: deklarationen(text.slice(rahmen.kopfZeichen + 1, klammerEnde(text, rahmen.kopfZeichen))),
            stelle: rahmen.kopfZeichen,
            kontext,
          })
        }
      }
      kopfAb = i + 1
    } else if (c === ';') {
      kopfAb = i + 1
    }
  }
  return regeln
}

/**
 * Wert eines Namens im DUNKELMODUS (Bildschirm) — Druckblock aussen vor.
 * Dient als Nachweis, dass die Dunkelwerte wirklich anders sind.
 */
function dunkelWert(regeln, name) {
  const treffer = regeln
    .filter((r) => /\[data-theme="dark"\]/.test(r.selektoren) && r.deklarationen.has(name))
    .sort((a, b) => a.stelle - b.stelle)
  return treffer.length ? treffer[treffer.length - 1].deklarationen.get(name) : ''
}

/**
 * Ermittelt im DRUCKMEDIUM (Dunkelmodus am <html>) den wirksamen Wert eines
 * Namens: Kandidaten aus dem Druckblock und den Dunkel-Blöcken, entschieden
 * nach Spezifität und Stelle; `var()`-Ketten werden bis zum Rohwert aufgelöst.
 */
function druckAufloesen(name, regeln, druck, tiefe = 0, gesehen = new Set()) {
  if (tiefe > 12 || gesehen.has(name)) return { wert: '', quelle: name }
  gesehen.add(name)
  const kandidaten = [druck, ...regeln.filter((r) => /\[data-theme="dark"\]/.test(r.selektoren))]
    .filter((r) => r.deklarationen && r.deklarationen.has(name))
    .map((r) => ({ r, spez: Math.max(...r.selektoren.split(',').map(spezifitaet)) }))
    .sort((a, b) => (a.spez - b.spez) || (a.r.stelle - b.r.stelle))
  if (!kandidaten.length) return { wert: '', quelle: name }
  const gewaehlt = kandidaten[kandidaten.length - 1]
  const roh = gewaehlt.r.deklarationen.get(name)
  const m = /^var\(\s*(--[\w-]+)\s*\)$/.exec(String(roh).trim())
  if (!m) return { wert: String(roh).trim(), quelle: name }
  const weiter = druckAufloesen(m[1], regeln, druck, tiefe + 1, gesehen)
  return weiter.wert ? weiter : { wert: String(roh).trim(), quelle: name }
}

test('MT-7b · Druck: jedes im Dunkelmodus gesetzte Token entspricht dem hellen Wert (Punkt C)', () => {
  const roh = ohneCssKommentare(lies('src/diakonos/tokens.css'))

  // Alle Regeln MIT ihrem At-Regel-Kontext: der Druckblock ist damit eindeutig
  // als `kontext: @media print` erkennbar — und seine Werte können die
  // Dunkel-Karte NICHT mehr überschreiben (der alte Fehler: der Dunkel-Regex
  // traf auch den Druckblock; `--text` im Druck auf `var(--dk-warm-100)` blieb
  // dadurch grün).
  const regeln = alleRegeln(roh)
  const druckRegeln = regeln.filter((r) => /\bprint\b/.test(r.kontext))
  assert.equal(druckRegeln.length, 1,
    `tokens.css: erwartet EINEN @media print-Block, gefunden ${druckRegeln.length}`)
  const [druck] = druckRegeln
  assert.ok(druck.deklarationen.size > 40,
    `tokens.css: der Druck-Block setzt nur ${druck.deklarationen.size} Namen`)

  const ohneMedien = regeln.filter((r) => !r.kontext)
  const dunkelRegeln = ohneMedien.filter((r) => /\[data-theme="dark"\]/.test(r.selektoren))
  assert.ok(dunkelRegeln.length >= 3, `tokens.css: Dunkel-Blöcke nicht gefunden (${dunkelRegeln.length})`)

  // Heller Satz: `:root`-Blöcke und der Alias-Block §4 (`:root, [data-theme=…]`)
  // — er setzt die --dk-Namen für BEIDE Themes. Die Dunkel-Blöcke zählen NICHT
  // dazu (dort ist `--accent-soft` eine Transparenz, hell ist es `--dk-gold-50`).
  const hell = new Map()
  const hellQuellen = ohneMedien
    .filter((x) => /^\s*:root\s*(?:,|$)/.test(x.selektoren))
    .map((x) => ({ ...x, spez: Math.max(...x.selektoren.split(',').map(spezifitaet)) }))
    .sort((a, b) => (a.spez - b.spez) || (a.stelle - b.stelle))
  for (const r of hellQuellen) for (const [name, wert] of r.deklarationen) hell.set(name, wert)
  assert.ok(hell.size > 60, `tokens.css: heller Satz fehlt (${hell.size} Namen)`)

  /** `var()`-Kette über eine Wert-Tabelle bis zum Rohwert auflösen. */
  const kette = (wert, tabelle, tiefe = 0) => {
    if (tiefe > 12) return String(wert).trim()
    const m = /^var\(\s*(--[\w-]+)\s*\)$/.exec(String(wert).trim())
    if (!m) return String(wert).trim()
    const naechster = tabelle(m[1])
    return naechster ? kette(naechster, tabelle, tiefe + 1) : String(wert).trim()
  }
  /**
   * Druckmedium mit Dunkelmodus am <html>: für einen Namen gewinnt die Regel
   * mit der höchsten Spezifität (bei Gleichstand die spätere Stelle) — der
   * Druckblock steht hinten und setzt gegen die Dunkel-Blöcke.
   */
  const druckTabelle = (name) => {
    const treffer = [...ohneMedien, druck]
      .filter((r) => r.deklarationen && r.deklarationen.has(name))
      .map((r) => ({ r, spez: Math.max(...r.selektoren.split(',').map(spezifitaet)) }))
      .sort((a, b) => (a.spez - b.spez) || (a.r.stelle - b.r.stelle))
    return treffer.length ? treffer[treffer.length - 1].r.deklarationen.get(name) : ''
  }

  // Maße/Zeiten sind keine Farben (der Zeiger-Block setzt `--control-h` genau
  // einmal, FIX-3 wacht darüber) — sie bleiben außen vor.
  const masse = /^(?:--(?:control-h|control-h-lg|filter-h|topbar-h|layout-mobil|ease|fast|med|slow|radius(?:-|$)|badge-r|sp-|fs-|fw-|pad|lesebreite|topbar|seitenleiste|dk-ease|dk-fast|dk-med|dk-sidebar|dk-topbar))/
  /** Reine Weiterleitung (`--dk-bg: var(--bg)`) — folgt allen anderen Regeln. */
  const istWeiterleitung = (wert) => /^var\(--[\w-]+\)$/.test(String(wert).trim())
  const namen = new Set()
  for (const r of dunkelRegeln) for (const name of r.deklarationen.keys()) namen.add(name)

  const fehlend = []
  const abweichend = []
  const geprueft = []
  for (const name of namen) {
    if (masse.test(name)) continue
    const hellWert = hell.get(name)
    if (!hellWert) continue                       // reiner Dunkel-Hilfsname ohne hellen Partner
    // Reine Weiterleitungen brauchen keinen Eintrag im Druckblock — aber nur,
    // wenn sie auf einen HELLEN Namen zeigen (`--dk-bg: var(--bg)`); ein Alias
    // auf einen dunklen Rohnamen (`--dk-text: var(--dk-ink-text)`) muss hier
    // stehen, sonst bliebe das Papier dunkel.
    const dunkelWert = [...dunkelRegeln].reverse().find((r) => r.deklarationen.has(name))?.deklarationen.get(name) || ''
    const ziel = /^var\(\s*(--[\w-]+)\s*\)$/.exec(String(dunkelWert).trim())
    if (ziel && hell.has(ziel[1])) continue       // zeigt auf einen hellen Namen
    if (!druck.deklarationen.has(name)) { fehlend.push(name); continue }
    geprueft.push(name)
    const druckWert = einSprung(druck.deklarationen.get(name))
    const sollHell = einSprung(hellWert)
    if (druckWert !== sollHell) abweichend.push(`${name}: Druck „${druckWert}“ ≠ hell „${sollHell}“`)
  }
  assert.ok(geprueft.length >= 38, `tokens.css: nur ${geprueft.length} Namen geprüft — Auswahl zu klein`)
  assert.deepEqual(fehlend, [],
    `tokens.css: der Druck-Block setzt diese Dunkel-Tokens NICHT: ${fehlend.join(', ')}`)
  assert.deepEqual(abweichend, [],
    `tokens.css: im Druck-Medium weicht ein Token vom hellen Wert ab: ${abweichend.join(' · ')}`)

  // GEGENPROBE (Review-Punkt 3): Die Prüfung wird mit einem KAPUTTEN Druckblock
  // (aus der echten Datei, `--text` → dunkle Rohnfarbe) wiederholt — sie MUSS
  // anschlagen. Der alte Test blieb hier grün, weil er `var(…)`-Werte
  // übersprang.
  const druckAnfang = roh.search(/@media\s+print\s*\{/)
  assert.ok(druckAnfang !== -1, 'Gegenprobe (a): kein Druckblock gefunden')
  const abDruck = roh.slice(druckAnfang)
  const kaputtStelle = /(--text\s*:\s*)[^;]+;/.exec(abDruck)
  assert.ok(kaputtStelle, 'Gegenprobe (a): --text im Druckblock nicht gefunden')
  const kaputtText = `${roh.slice(0, druckAnfang)}${abDruck.slice(0, kaputtStelle.index)}`
    + `${kaputtStelle[1]}var(--dk-warm-100);${abDruck.slice(kaputtStelle.index + kaputtStelle[0].length)}`
  assert.notEqual(kaputtText, roh, 'Gegenprobe (a): der Druckblock ließ sich nicht verändern')
  const kaputtDruck = alleRegeln(kaputtText).filter((r) => /\bprint\b/.test(r.kontext))[0]
  assert.equal(einSprung(kaputtDruck.deklarationen.get('--text')), 'var(--dk-warm-100)',
    'Gegenprobe (a): der veränderte Druckwert kommt nicht an')
  assert.notEqual(einSprung(kaputtDruck.deklarationen.get('--text')), einSprung(hell.get('--text')),
    'Gegenprobe (a): ein dunkler Druckwert fällt NICHT auf — der Vergleich ist blind')
  // (b) Ein fehlender Eintrag im Druckblock wird als Lücke erkannt.
  assert.ok(namen.has('--badge-ink-ok') && !(new Map([...druck.deklarationen].filter(([n]) => n !== '--badge-ink-ok')).has('--badge-ink-ok')),
    'Gegenprobe (b): ein fehlender Druckwert wird nicht als Lücke erkannt')
})


// ═══════════════════════════════════════════════════════════════════════════
// A/B/D/E/F — Verhalten im echten jsdom-Dokument
// ═══════════════════════════════════════════════════════════════════════════

let AUSGABE = null
const geschrieben = new Set()

function ziel(abs) {
  const rel = path.relative(SRC, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(AUSGABE, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

/** Relative Importe auf den Temp-Baum umschreiben (wie dev-b1-mount). */
function pfadUmschreiben(abs, pfad) {
  const zielAbs = path.resolve(path.dirname(abs), pfad)
  if (!/\.(vue|js|mjs)$/.test(pfad)) return null
  if (pfad.endsWith('.vue')) {
    bauteilSchreiben(zielAbs)
    return pfad.replace(/\.vue$/, '.mjs')
  }
  modulSchreiben(zielAbs)
  // Auch in `.mjs`-Modulen bleiben `./x.js`-Importe stehen (Node löst sie nur
  // so auf) — sie müssen ebenfalls auf den Temp-Baum zeigen.
  return pfad.replace(/\.(js|mjs)$/, '.mjs')
}

function bauteilSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const id = path.basename(abs, '.vue').replace(/\W/g, '_')
  const datei = ziel(abs)
  writeFileSync(datei, 'export default {}\n', 'utf8')

  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  const hoisted = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${id}_${n}`)
  code = hoisted(code)
  const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
  if (!renderImSkript) {
    const tpl = compileTemplate({
      id,
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
    const ohneExport = hoisted(tpl.code.replace(/export function render/, 'function render'))
    const importe = new Set()
    const rest = []
    for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
      if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
        for (const n of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
          if (n.trim()) importe.add(n.trim())
        }
        continue
      }
      if (/^const _hoisted_\d+\b/.test(zeile.trim())) continue
      rest.push(zeile)
    }
    const rumpf = rest.join('\n')
      .replace(/\bexport const /g, 'const ')
      .replace(/export default /g, 'const __bauteil = ')
    code = `import { ${[...importe].join(', ')} } from 'vue'\n${hoisted(rumpf)}`
      + '\n__bauteil.render = render\nexport default __bauteil\n'
  }
  code = code.split('\n').map((zeile) => {
    // Auch die FORTSETZUNGSZEILE eines mehrzeiligen Imports (`} from './x.mjs'`).
    const m = /^(\s*(?:(?:import|export)\b[^'"]*?from\s+|\}?\s*from\s+))(['"])(\.\.?\/[^'"]+)\2/.exec(zeile)
    if (!m) return zeile
    const neu = pfadUmschreiben(abs, m[3])
    return neu ? `${m[1]}${m[2]}${neu}${m[2]}${zeile.slice(m[0].length)}` : zeile
  }).join('\n')
  writeFileSync(datei, code, 'utf8')
}

function modulSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const zeilen = readFileSync(abs, 'utf8').split('\n')
  const code = zeilen.map((zeile) => {
    // Auch die FORTSETZUNGSZEILE eines mehrzeiligen Imports (`} from './x.mjs'`).
    const m = /^(\s*(?:(?:import|export)\b[^'"]*?from\s+|\}?\s*from\s+))(['"])(\.\.?\/[^'"]+)\2/.exec(zeile)
    if (!m) return zeile
    const zielPfad = pfadUmschreiben(abs, m[3])
    if (!zielPfad) return zeile
    return `${m[1]}${m[2]}${zielPfad}${m[2]}${zeile.slice(m[0].length)}`
  }).join('\n')
  writeFileSync(ziel(abs), code, 'utf8')
}

// ── fetch wie der Server ────────────────────────────────────────────────────
function antwort(daten, status = 200) {
  const text = JSON.stringify(daten)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => JSON.parse(text),
    headers: { get: () => 'application/json' },
  }
}

const BEITRAEGE = [
  { id: 'B-2', title: 'Sommerfest', excerpt: 'Am See', category: 'gemeindeleben', image: '', author: 'Anna', date: '2026-11-10', comments: 0, auf_website: false },
  { id: 'B-1', title: 'Beamer-Abend', excerpt: 'Technik', category: 'ankuendigung', image: '', author: 'Bert', date: '2026-11-08', comments: 0, auf_website: false },
]

/**
 * @param {{detailStatus?: number, verzoegerungMs?: number, artikel?: boolean}} lage
 */
function fetchAttrappe(aufrufe, lage = {}) {
  return async (url) => {
    const adresse = String(url)
    aufrufe.push(adresse)
    if (adresse.includes('get_beitraege_liste')) return antwort({ message: BEITRAEGE })
    if (adresse.includes('get_beitrag_detail')) {
      if (lage.verzoegerungMs) await new Promise((r) => setTimeout(r, lage.verzoegerungMs))
      // So antwortet die Compat-Schicht bei fehlendem Recht (Frappe-Form).
      // Ein frei erfundener deutscher Satz würde vom Fehlerkatalog bewusst
      // stehen gelassen — die Form unten ist die echte.
      if (lage.detailStatus === 403) {
        return antwort({ exception: 'frappe.exceptions.PermissionError: Not permitted', exc_type: 'PermissionError' }, 403)
      }
      return antwort({
        message: {
          id: 'B-2', title: 'Sommerfest', excerpt: 'Am See', category: 'gemeindeleben',
          image: '', author: 'Anna', date: '2026-11-10', comments: 0, auf_website: false,
          content: '<p>Am See treffen wir uns.</p>', commentList: [],
        },
      })
    }
    if (adresse.includes('get_session_info')) return antwort({ message: { roles: [] } })
    return antwort({ message: {} })
  }
}

let DOKUMENT = null
async function dokument() {
  if (!DOKUMENT) {
    const { JSDOM } = await import('jsdom')
    const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
      url: 'http://localhost/diakronos/#/beitraege',
      pretendToBeVisual: true,
    })
    const { window } = dom
    globalThis.window = window
    globalThis.document = window.document
    globalThis.localStorage = window.localStorage
    globalThis.sessionStorage = window.sessionStorage
    globalThis.HTMLElement = window.HTMLElement
    globalThis.SVGElement = window.SVGElement
    globalThis.Element = window.Element
    globalThis.Node = window.Node
    // Vues DOM-Laufzeit prüft `instanceof Document` (Formular-Elemente) —
    // ohne diese Klasse bricht jedes v-model-Update mit „Document is not defined“.
    globalThis.Document = window.Document
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
    window.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token', roles: [], modules: [] }
    DOKUMENT = window
  }
  DOKUMENT.document.body.innerHTML = ''
  return DOKUMENT
}

async function bauteilLaden(window, relPfad) {
  bauteilSchreiben(path.join(SRC, relPfad))
  const datei = ziel(path.join(SRC, relPfad))
  const modul = await import(pathToFileURL(datei).href + `?v=${Date.now()}${Math.random()}`)
  return modul.default
}

/** Mountet eine Seite; `fetch` wird gesetzt, alle Aufrufe landen in `aufrufe`. */
async function mounten(window, relPfad, lage = {}) {
  const aufrufe = []
  window.fetch = globalThis.fetch = fetchAttrappe(aufrufe, lage)
  const baum = mkdtempSync(path.join(FRONTEND, '.kanban-mt7b-'))
  AUSGABE = baum
  geschrieben.clear()
  const bauteilKlasse = await bauteilLaden(window, relPfad)
  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  const app = createApp({ render: () => h(bauteilKlasse) })
  app.config.warnHandler = () => {}
  app.mount(knoten)
  /** Warten, bis die Seite „steht“ (fetch + Vue + Skelett 300 ms). */
  const warten = async (runden = 14, ms = 40) => {
    for (let i = 0; i < runden; i += 1) {
      await new Promise((r) => setTimeout(r, ms))
      await nextTick()
    }
  }
  await warten()
  return {
    app, aufrufe, window, baum,
    body: window.document.body,
    texte: () => (window.document.body.textContent || '').replace(/\s+/g, ' ').trim(),
    aufraeumen: () => { app.unmount(); rmSync(baum, { recursive: true, force: true }) },
    warten,
  }
}

// ── A: echter Verlauf — „zurück“ ERSETZT, Browser-Zurück behält die Filter ──
test('MT-7b · A: „‹ zurück“ ersetzt den Eintrag (kein Push) — die Filter kommen aus dem Merker', async () => {
  const window = await dokument()
  rueckwegVergessen()   // sauberer Anfang (der Merker lebt im Modul)
  // ECHTE Verlaufsfolge: Suche in der Liste, dann den Eintrag öffnen.
  window.history.replaceState(null, '', '/diakronos/#/beitraege?q=Beamer')

  // 1) Liste mit Suchbegriff
  const liste = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    // Der Suchbegriff aus der Adresse steht im Feld (sonst wäre „zurück“ ohne
    // Filter richtig — die Liste hätte ihn nie gehabt).
    const suche = liste.body.querySelector('input[aria-label="Beiträge durchsuchen"]')
    assert.ok(suche, 'Suchfeld der Liste fehlt')
    assert.equal(suche.value, 'Beamer', 'die Liste übernimmt ?q= nicht aus der Adresse')

    // Klick auf den Treffer öffnet die Leseseite (Routenwechsel) und merkt sich
    // die Volladresse der Liste (mit Filter UND Kennung für den Fokus).
    const karte = [...liste.body.querySelectorAll('.bt-post')]
      .find((k) => /Beamer-Abend/.test(k.textContent || ''))
    assert.ok(karte, 'Beitragskarte „Beamer-Abend“ fehlt (Suche filtert nicht)')
    karte.click()
    await liste.warten(3, 10)
    assert.equal(window.location.hash, '#/beitraege/B-1', 'der Klick öffnet nicht die Leseseite')
    const gemerkt = rueckwegZiel('#/beitraege')
    assert.match(gemerkt, /^#\/beitraege\?/, 'die Liste merkt sich ihre Adresse NICHT mit Filter')
    assert.match(gemerkt, /q=Beamer/, `der Suchbegriff fehlt im Merker („${gemerkt}“)`)
    assert.equal(rueckwegKennung('#/beitraege'), 'B-1',
      'die Kennung des geöffneten Beitrags steht nicht im Merker (Punkt 4: Fokus)')
    // Punkt 2: Der Listen-Eintrag im VERLAUF trägt die Filter schon — nicht nur
    // der Merker. Sonst landet Browser-„Zurück“ auf der ungefilterten Liste.
    assert.match(decodeURIComponent(window.location.hash), /^#\/beitraege\/B-1$/)
  } finally { liste.aufraeumen() }

  // 2) Leseseite — wie nach dem Routenwechsel (neuer Verlaufseintrag).
  const vorher = window.history.length
  const detail = await mounten(window, 'diakonos/pages/BeitragDetail.vue')
  try {
    // Ein echtes Verlaufsobjekt, das `back()` NICHT ausführen kann: der Test
    // belegt damit, dass der Knopf den Verlauf gar nicht mehr anfasst.
    let backGerufen = false
    window.history.back = () => { backGerufen = true }

    const knopf = [...detail.body.querySelectorAll('a, button')]
      .find((el) => /zurück/.test(el.textContent || ''))
    assert.ok(knopf, '„‹ zurück“ fehlt auf der Leseseite')
    assert.match(decodeURIComponent(knopf.getAttribute('href')), /^#\/beitraege\?.*q=Beamer/,
      'der Zurück-Link zeigt nicht auf die gefilterte Liste')
    knopf.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
    await detail.warten(2, 10)

    assert.equal(backGerufen, false, '„zurück“ nutzt weiterhin history.back()')
    assert.match(decodeURIComponent(window.location.hash), /^#\/beitraege\?.*q=Beamer/,
      '„zurück“ landet nicht auf der Liste mit Filter')
    // ERSETZEN statt Anhängen (Review-Punkt 1, Zurück-Falle): kein neuer
    // Eintrag. Vorher wuchs der Verlauf um eins, und Browser-„Zurück“ führte
    // wieder auf die Leseseite.
    assert.equal(window.history.length, vorher,
      `„zurück“ legt einen neuen Verlaufseintrag an (${vorher} → ${window.history.length})`)
  } finally { detail.aufraeumen() }

  // 3) Ohne Merker (geteilter Link, frischer Tab) → Liste ohne Filter.
  rueckwegVergessen()
  window.history.replaceState(null, '', '/diakronos/#/beitraege/B-2')
  const frisch = await mounten(window, 'diakonos/pages/BeitragDetail.vue')
  try {
    const knopf = [...frisch.body.querySelectorAll('a, button')]
      .find((el) => /zurück/.test(el.textContent || ''))
    assert.equal(knopf.getAttribute('href'), '#/beitraege',
      'ohne Merker muss „zurück“ in die Liste OHNE Filter führen')
  } finally { frisch.aufraeumen() }
})

// ── 2: Browser-Zurück → gefilterte Liste (Suchbegriff getippt) ──────────────
test('MT-7b · 2: Browser-Zurück landet auf der Liste MIT getipptem ?q=', async () => {
  const window = await dokument()
  rueckwegVergessen()
  window.history.replaceState(null, '', '/diakronos/#/beitraege')

  const liste = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    // GESUCHT wird getippt, nicht per Adresse vorgegeben.
    const feld = liste.body.querySelector('input[aria-label="Beiträge durchsuchen"]')
    feld.value = 'Beamer'
    feld.dispatchEvent(new window.Event('input', { bubbles: true }))
    await liste.warten(2, 10)
    // Der Eintrag der Liste trägt die Suche jetzt (wie `Lieder.vue`, Punkt 2).
    assert.match(decodeURIComponent(window.location.hash), /\?.*q=Beamer/,
      'die Liste schreibt ihren Filter nicht in ihren eigenen Verlaufs-Eintrag')

    const karte = [...liste.body.querySelectorAll('.bt-post')]
      .find((k) => /Beamer-Abend/.test(k.textContent || ''))
    assert.ok(karte, 'gefilterte Liste zeigt den Treffer nicht')
    karte.click()
    await liste.warten(3, 10)
    assert.equal(window.location.hash, '#/beitraege/B-1')
  } finally { liste.aufraeumen() }

  // Nach dem Wechsel steht das in der Adresse (der Listen-Eintrag davor hat
  // die Suche). Jetzt Browser-„Zurück“ nachstellen: die Liste wird mit der
  // Adresse des VORIGEN Eintrags neu aufgebaut — genau das prüft Punkt 2.
  window.history.replaceState(null, '', '/diakronos/#/beitraege?kategorie=alle&q=Beamer')
  const zurueck = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    const feld = zurueck.body.querySelector('input[aria-label="Beiträge durchsuchen"]')
    assert.equal(feld.value, 'Beamer',
      'nach Browser-„Zurück“ ist das Suchfeld leer — der Filter ging verloren')
    const karten = [...zurueck.body.querySelectorAll('.bt-post')]
    assert.equal(karten.length, 1, `die Liste ist nicht gefiltert (${karten.length} Karten)`)
  } finally { zurueck.aufraeumen() }
})

// ── 4: Fokus auf der zuletzt geöffneten Karte ──────────────────────────────
test('MT-7b · 4: die Liste setzt den Fokus zurück auf die zuletzt geöffnete Karte', async () => {
  const window = await dokument()
  rueckwegVergessen()
  // Merker aus dem Öffnen: Liste `?kategorie=alle&q=` + Kennung B-2.
  rueckwegMerken('#/beitraege?kategorie=alle&q=', '#/beitraege', 'B-2')
  window.history.replaceState(null, '', '/diakronos/#/beitraege?kategorie=alle&q=')

  const liste = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    const karte = liste.body.querySelector('.bt-post[data-id="B-2"]')
    assert.ok(karte, 'die Beitragskarte trägt kein data-id (Fokus unauffindbar)')
    assert.equal(window.document.activeElement, karte,
      'der Fokus steht nach dem Zurück nicht auf der zuletzt geöffneten Karte')
  } finally { liste.aufraeumen(); rueckwegVergessen() }
})

// ── 5: veralteter Merker — der ROUTER verwirft ihn ─────────────────────────
test('MT-7b · 5: jeder Wechsel außer „Liste → eigene Leseseite“ verwirft den Merker', async () => {
  // Der Merker darf nur den direkten Weg Liste → Leseseite überleben. Der
  // Router entscheidet das beim Routenwechsel (eine Stelle) — auch für
  // Menüpunkte im Gerüst, die keine Seite als Klick sieht.
  const beitraege = '#/beitraege'
  // Aus der Liste heraus: Eintrag öffnen (auch ein weiterer Eintrag derselben
  // Liste) und das Umbenennen des Listen-Eintrags (replaceState mit Filtern).
  assert.equal(rueckwegBleibtGueltig('#/beitraege?q=Beamer', '#/beitraege/B-1', beitraege), true)
  assert.equal(rueckwegBleibtGueltig('#/beitraege/B-1', '#/beitraege/B-2', beitraege), true)
  assert.equal(rueckwegBleibtGueltig('#/beitraege?kategorie=alle&q=', '#/beitraege?kategorie=jugend&q=info', beitraege), true)
  // Von der Leseseite zurück auf die Liste (der Fokus braucht den Merker).
  assert.equal(rueckwegBleibtGueltig('#/beitraege/B-1', '#/beitraege?q=Beamer', beitraege), true)
  // Alles andere: Menü (Gerüst), Gruppen-Detail, fremde Listen, Wiki.
  assert.equal(rueckwegBleibtGueltig('#/beitraege?q=Beamer', '#/lieder', beitraege), false,
    'ein Menüpunkt verwirft den Merker nicht (veraltetes ?q= bleibt)')
  assert.equal(rueckwegBleibtGueltig('#/beitraege?q=Beamer', '#/', beitraege), false)
  assert.equal(rueckwegBleibtGueltig('#/wiki/A-1', '#/werkzeuge', beitraege), false)
  assert.equal(rueckwegBleibtGueltig('#/beitraege/B-1', '#/wiki/A-1', beitraege), false,
    'der Wechsel in die andere Liste darf den Merker nicht behalten')

  // Ende-zu-Ende: Merker setzen, Wechsel „Liste → Lieder“ — danach ist er weg
  // und „zurück“ führt in die Liste OHNE Filter.
  const window = await dokument()
  rueckwegMerken('#/beitraege?q=Beamer', '#/beitraege', 'B-1')
  assert.equal(rueckwegZiel('#/beitraege'), '#/beitraege?q=Beamer')
  if (!rueckwegBleibtGueltig(window.location.hash || '#/beitraege', '#/lieder', '#/beitraege')) {
    rueckwegVergessen('#/beitraege')      // genau das tut der Router
  }
  assert.equal(rueckwegZiel('#/beitraege'), '#/beitraege',
    'ein veralteter Merker bringt den alten Filter zurück (Punkt 5)')
  rueckwegVergessen()
})

// ── B: Fokus erst nach dem Laden ───────────────────────────────────────────
test('MT-7b · B: der Fokus steht nach dem Laden auf der Überschrift (auch bei langsamer Antwort)', async () => {
  const window = await dokument()
  window.history.replaceState(null, '', '/diakronos/#/beitraege/B-2')
  // Antwort erst nach 450 ms: das Skelett (ab 300 ms) steht, wenn der Focus
  // zu früh liefe — der Seitenkopf existiert dann noch nicht.
  const seite = await mounten(window, 'diakonos/pages/BeitragDetail.vue', { verzoegerungMs: 450 })
  try {
    assert.match(seite.texte(), /Sommerfest/, 'der Beitrag wurde nicht geladen')
    const titel = seite.body.querySelector('.dk-ui-pageheader-titel')
    assert.ok(titel, 'Seitenkopf fehlt')
    assert.equal(titel.getAttribute('tabindex'), '-1', 'die Überschrift ist nicht programmatisch erreichbar')
    assert.equal(window.document.activeElement, titel,
      'der Fokus steht nicht auf der Überschrift (Punkt B: zu früh gesetzt)')
  } finally { seite.aufraeumen() }
})

test('MT-7b · D: Modifier-Klick auf „Ähnliche Artikel“ öffnet normal (neuer Tab)', async () => {
  const window = await dokument()
  window.history.replaceState(null, '', '/diakronos/#/wiki/A-1')
  const aufrufe = []
  window.fetch = globalThis.fetch = async (url) => {
    aufrufe.push(String(url))
    if (String(url).includes('get_wiki_artikel_detail')) {
      return antwort({ message: { id: 'A-1', title: 'Beamer', category: 'technik', author: 'Cara', updatedAt: '2026-11-10', tags: ['technik'], content: '<p>x</p>' } })
    }
    if (String(url).includes('get_wiki_artikel_liste')) {
      return antwort({ message: [
        { id: 'A-1', title: 'Beamer', category: 'technik', tags: ['technik'] },
        { id: 'A-2', title: 'Beamer-Kabel', category: 'technik', tags: ['technik'] },
      ] })
    }
    return antwort({ message: {} })
  }
  const baum = mkdtempSync(path.join(FRONTEND, '.kanban-mt7b-d-'))
  AUSGABE = baum
  geschrieben.clear()
  try {
    const { createApp, h, nextTick } = await import('vue')
    const klasse = await bauteilLaden(window, 'diakonos/pages/WikiArtikel.vue')
    const knoten = window.document.createElement('div')
    window.document.body.appendChild(knoten)
    const app = createApp({ render: () => h(klasse) })
    app.config.warnHandler = () => {}
    app.mount(knoten)
    for (let i = 0; i < 14; i += 1) { await new Promise((r) => setTimeout(r, 40)); await nextTick() }

    const link = [...window.document.querySelectorAll('.wk-lese-aehnlich-link')]
      .find((a) => /Beamer-Kabel/.test(a.textContent || ''))
    assert.ok(link, 'Link „Ähnliche Artikel“ fehlt')

    // JEDER Modifier und der Mittelklick: der Browser behält das Ereignis.
    for (const art of [
      { ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 },
    ]) {
      const ereignis = new window.MouseEvent('click', { bubbles: true, cancelable: true, ...art })
      link.dispatchEvent(ereignis)
      assert.equal(ereignis.defaultPrevented, false,
        `Modifier-Klick ${JSON.stringify(art)} wird abgeschaltet — der neue Tab öffnet nicht`)
    }
    // Der einfache Klick gehört dem Router (kein Voll-Neuladen).
    const einfach = new window.MouseEvent('click', { bubbles: true, cancelable: true })
    link.dispatchEvent(einfach)
    assert.equal(einfach.defaultPrevented, true, 'der einfache Klick läuft nicht über den Router')
    await nextTick()
    assert.equal(window.location.hash, '#/wiki/A-2', 'der einfache Klick öffnet den Artikel nicht')
    app.unmount()
  } finally { rmSync(baum, { recursive: true, force: true }) }
})

// ── E: ?bearbeiten= lädt die Liste EINMAL ──────────────────────────────────
test('MT-7b · E: ?bearbeiten= holt die Liste genau einmal (Punkt E)', async () => {
  const window = await dokument()
  window.history.replaceState(null, '', '/diakronos/#/beitraege?bearbeiten=B-2')
  const seite = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    const listen = seite.aufrufe.filter((u) => u.includes('get_beitraege_liste'))
    assert.equal(listen.length, 1,
      `die Liste wurde ${listen.length}x geholt — mit ?bearbeiten= reicht EIN Abruf`)
    // Der Editor ist offen (die Kennung wurde aus der Adresse genommen).
    assert.ok(!window.location.hash.includes('bearbeiten'),
      'die Kennung steht noch in der Adresse — Neuladen risse den Editor erneut auf')
  } finally { seite.aufraeumen() }
})

// ── F: 403 → „keine Berechtigung“, kein „Erneut versuchen“ ─────────────────
test('MT-7b · F: 403 auf der Leseseite zeigt „keine Berechtigung“ ohne „Erneut versuchen“', async () => {
  const window = await dokument()
  window.history.replaceState(null, '', '/diakronos/#/beitraege/B-2')
  const seite = await mounten(window, 'diakonos/pages/BeitragDetail.vue', { detailStatus: 403 })
  try {
    const inhalt = seite.texte()
    assert.match(inhalt, /Berechtigung/i,
      `403 zeigt nicht den Rechte-Text, sondern: „${inhalt.slice(0, 160)}“`)
    assert.ok(!/Erneut versuchen/.test(inhalt),
      'bei 403 steht „Erneut versuchen“ — der Knopf bliebe ohne Wirkung')
    // Der Weg zurück bleibt (er ist der nächste Schritt).
    assert.match(inhalt, /Zurück zu den Beiträgen/)
  } finally { seite.aufraeumen() }
})
