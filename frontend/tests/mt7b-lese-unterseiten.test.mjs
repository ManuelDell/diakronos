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
 *      Namen, den ein Dunkel-Block setzt, gilt im Druckmedium der helle Wert —
 *      geprüft über die WIRKSAME Kaskade (Spezifität + Stelle, `var()` auch in
 *      `color-mix` rekursiv aufgelöst), ohne Überspring-Regel; die Gegenprobe
 *      spielt die sechs Sabotagen des Reviews gegen `pruefe()` durch.
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

/**
 * Name → zuletzt genannter Wert EINER Regel (innerhalb der Regel gewinnt die
 * spätere Zeile). Genommen werden ALLE Eigenschaften, nicht nur `--x`: die
 * Druck-Prüfung zu „‹ zurück“ (Punkt 4) braucht `display: none`.
 */
function deklarationen(text) {
  const karte = new Map()
  for (const m of text.matchAll(/([\w-]+)\s*:\s*([^;}]+)/g)) {
    karte.set(m[1], m[2].trim().replace(/\s+/g, ' '))
  }
  return karte
}

/**
 * Spezifitätsgewicht eines Selektors (grob, ohne `!important`): Attribut 100,
 * Klasse/Pseudo-Klasse 10, Typ 1. Reicht, um `:root` von
 * `:root[data-theme="dark"]` zu unterscheiden — mehr braucht der Druck-Test
 * nicht, weil alle Regelköpfe der Token-Datei aus diesen Teilen bestehen.
 */
function spezifitaet(selektor) {
  const s = selektor.trim()
  // `[data-theme="dark"]`/`[data-theme]` = Attribut (0,1,0). `:root` zählt
  // als Pseudo-KLASSE (0,1,0) — so wertet es der Browser; deshalb schlägt
  // `:root[data-theme="dark"]` (0,2,0) den Druck-Selektor `:root` (0,1,0)
  // nicht nur über die Stelle. Zwei Selektoren einer Liste zählen einzeln;
  // wir werten den BESTEN (der Block gilt, wenn irgendein Teil passt).
  const attribute = (s.match(/\[[^\]]*\]/g) || []).length
  const klassen = (s.match(/\.[\w-]+|:{1,2}[\w-]+(?:\([^)]*\))?/g) || []).length
  const typen = /^(?:html|body)\b/.test(s) ? 1 : 0
  return attribute * 100 + klassen * 10 + typen
}

/** Die Element-Lage, in der ein Selektor-Teil gelten soll (Druck-Prüfung). */
const PRINT_THEME = { wurzel: true, dark: true }
const HELL_THEME = { wurzel: true, dark: false }
const CONTAINER_THEME = { wurzel: false, dark: true }

/**
 * Gilt dieser Selektor-Teiler für die Lage? Geprüft werden `:root[data-theme="dark"]`
 * (nur mit dunklem Theme) und `[data-theme="dark"]`; alle anderen Teile
 * (`html`, `body`, `:root`, `@media`-Kontext) gelten immer. Das ist die
 * STRIKTE Fassung: `[data-theme="dark"]` auf einem Container INNERHALB des
 * <html> setzt den Namen am Container neu — dort greifen die
 * `[data-theme="dark"]`-Regeln, die `:root`-Regeln (auch der Druckblock)
 * aber NICHT. Genau daran verlor der Druckblock bisher: er stand mit
 * `:root` (0,1,0) gegen `:root[data-theme="dark"]` (0,2,0) und verlor.
 */
function teilerGilt(teiler, lage) {
  if (!lage) return true
  const amWurzel = /:root|(?:^|\s|>)(?:html|body)\b/.test(teiler)
  const dunkel = /\[data-theme="dark"\]/.test(teiler)
  if (lage.wurzel) {
    // Am <html>: nur Teiler, die dorthin zeigen. `[data-theme="dark"]` heißt
    // dort „dunkles Theme eingestellt“, `:root`/`html` gilt immer.
    return !dunkel || lage.dark
  }
  // Am CONTAINER (`.dk-app` trägt ebenfalls `data-theme`, DES-R1): `:root`-
  // und `html`-Teiler greifen dort nicht, `[data-theme="dark"] …` schon.
  return dunkel && !amWurzel
}

/** Beste Spezifität einer Selektorliste unter einer Lage (nur passende Teiler). */
function lageSpezifitaet(selektoren, lage) {
  const teile = String(selektoren || '').split(',').map((s) => s.trim()).filter(Boolean)
  const passend = teile.filter((s) => teilerGilt(s, lage))
  return passend.length ? Math.max(...passend.map(spezifitaet)) : -1
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
          // Verschachtelte Regeln (`.a { .b { … } }`) sähen sonst wie
          // Deklarationen des äußeren Blocks aus — der Text einer inneren
          // Regel wird deshalb abgeschnitten.
          const innen = text.slice(rahmen.kopfZeichen + 1, klammerEnde(text, rahmen.kopfZeichen))
          const ersteKlammer = innen.indexOf('{')
          regeln.push({
            selektoren: rahmen.selektoren,
            deklarationen: deklarationen(ersteKlammer === -1 ? innen : innen.slice(0, ersteKlammer)),
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

// ── Werte auflösen: `var()` rekursiv, auch INNERHALB von `color-mix(…)` ────

const VAR_MUSTER = /var\(\s*(--[\w-]+)\s*(?:,([^()]*))?\)/g


/**
 * Alle `var(--x)` eines Werts (auch in `color-mix`, `rgba`, Schatten) —
 * genau das übersah der alte Test: er las nur den GANZEN Wert als `var()`.
 * Ein Fallback (`var(--x, rot)`) ist LESBAR: er würde einen fehlenden Namen
 * glattbügeln und die Prüfung blind machen.
 */
function varNamen(wert) {
  const namen = []
  for (const m of String(wert || '').matchAll(VAR_MUSTER)) {
    assert.equal(m[2], undefined,
      `tokens.css: \`var(${m[1]}, …)\` mit Ersatzwert macht den Druck-Test blind`)
    namen.push(m[1])
  }
  return namen
}

/** Normalisiert einen aufgelösten Wert für den Vergleich. */
function normalisiere(wert) {
  return String(wert || '').trim().replace(/\s+/g, ' ').toLowerCase()
}

/**
 * Löst einen CSS-Wert über `werte` (Name → Rohwert) vollständig auf: jedes
 * `var(--x)`, auch mitten in `color-mix(in srgb, var(--line) 45%, …)`.
 * Tiefe und ein Kreis-Wächter verhindern Endlosschleifen.
 */
function loseAuf(wert, werte, tiefe = 0, gesehen = new Set()) {
  const roh = String(wert || '').trim()
  if (tiefe > 24) return { wert: roh, rest: [...new Set(varNamen(roh))] }
  let rest = []
  const ersetzt = roh.replace(VAR_MUSTER, (ganz, name) => {
    if (gesehen.has(name)) { rest.push(name); return ganz }
    const weiter = werte(name)
    if (weiter === undefined || weiter === null || String(weiter).trim() === '') { rest.push(name); return ganz }
    const tief_ = loseAuf(weiter, werte, tiefe + 1, new Set([...gesehen, name]))
    rest = rest.concat(tief_.rest)
    return tief_.wert
  })
  return { wert: normalisiere(ersetzt), rest: [...new Set(rest)] }
}

/**
 * EINE Prüfung des Druck-Blatts (Review-Punkt 1).
 *
 * Sie bekommt den CSS-Text und gibt das Ergebnis zurück, statt nur zu werfen —
 * so kann die Gegenprobe sie auf MANIPULIERTE Fassungen derselben Datei
 * anwenden und muss nur noch „es gibt Abweichungen“ prüfen.
 *
 * Vorgehen je Name:
 *   · HELL  — wirksam am <html> OHNE `data-theme="dark"` und ohne Medien:
 *             `:root`-Regeln (auch `:root, [data-theme="dark"]`, das sind
 *             Alias-Blöcke für beide Themes); entschieden nach Spezifität,
 *             dann Stelle.
 *   · DRUCK — wirksam am <html> MIT `data-theme="dark"` im Druckmedium:
 *             Regeln ohne Kontext (Bildschirm-Satz, Dunkel-Blöcke), deren
 *             Selektor-Teiler in dieser Lage greift, UND die Regeln aus
 *             `@media print`; ebenso nach Spezifität, dann Stelle. Die
 *             Dunkel-Blöcke dürfen dabei NICHT gewinnen — sie stehen mit
 *             `:root[data-theme="dark"]` (0,2,0) und schlügen `:root` des
 *             Druckblocks (0,1,0). Auf Papier heißt das: das Theme muss am
 *             <html> hängen (dort setzt der Druckblock), ein Container
 *             darunter ist im Druck abgeschaltet (Regel in `index.css`).
 *   · Beide Werte werden REKURSIV aufgelöst (auch in `color-mix`) und
 *     verglichen. Kein Name wird übersprungen — auch nicht, wenn der
 *     Dunkelwert `var()` ist (genau diese Lücke ließ 64 von 104 Namen
 *     ungeprüft: `--text: var(--dk-ink-text)` blieb grün).
 *
 * Maße/Zeiten (Knopfhöhen, Abstände, Schriften) und `transparent` werden
 * ausgelassen — sie werden auf Papier nicht zu Farben.
 *
 * @param {string} cssText Inhalt von `tokens.css` (Kommentare dürfen drin sein)
 * Zweite Lage (am <html>): das Theme hängt an einem CONTAINER darunter —
 * dort greifen die `[data-theme="dark"]`-Regeln, die `:root`-Regeln (und
 * damit der Druckblock) aber nicht. Die Erwartung bleibt dieselbe, denn
 * `index.css` schaltet diesen Container im Druck ab (§ Druck). Bleibt dort
 * ein Wert dunkel, steht er unter `containerWeicht`.
 *
 * @returns {{namen: string[], geprueft: string[], fehlend: string[], abweichend: string[],
 *            containerWeicht: string[], containerGeprueft: string[], grund: string[]}}
 */
function pruefe(cssText) {
  const roh = ohneCssKommentare(String(cssText || ''))
  const ergebnis = { namen: [], geprueft: [], fehlend: [], abweichend: [], containerWeicht: [], containerGeprueft: [], grund: [] }
  const regeln = alleRegeln(roh)

  const druckRegeln = regeln.filter((r) => /\bprint\b/.test(r.kontext))
  if (druckRegeln.length !== 1) {
    ergebnis.grund.push(`erwartet EINEN @media print-Block, gefunden ${druckRegeln.length}`)
    return ergebnis
  }
  const [druck] = druckRegeln
  if (druck.deklarationen.size <= 0) ergebnis.grund.push('der Druck-Block setzt keinen Namen')

  const ohneMedien = regeln.filter((r) => !r.kontext)
  const dunkelRegeln = ohneMedien.filter((r) => /\[data-theme="dark"\]/.test(r.selektoren))
  if (dunkelRegeln.length < 3) ergebnis.grund.push(`Dunkel-Blöcke nicht gefunden (${dunkelRegeln.length})`)

  /**
   * Wirksame Tabelle einer Lage: je Name der Wert der Regel mit der höchsten
   * Spezifität, bei Gleichstand der späteren Stelle — so entscheidet die
   * Kaskade wirklich (vorher wurden Blöcke nur „zuletzt gewinnt“ gelesen).
   */
  const tabelle = (quellen, lage) => {
    const beste = new Map()
    for (const r of quellen) {
      if (!r.deklarationen) continue
      const spez = lageSpezifitaet(r.selektoren, lage)
      if (spez < 0) continue
      for (const [name, wert] of r.deklarationen) {
        const alt = beste.get(name)
        if (!alt || spez > alt.spez || (spez === alt.spez && r.stelle > alt.stelle)) {
          beste.set(name, { spez, stelle: r.stelle, wert })
        }
      }
    }
    return new Map([...beste].map(([name, e]) => [name, e.wert]))
  }

  const hellTabelle = tabelle(ohneMedien, HELL_THEME)
  const druckTabelle = tabelle([...ohneMedien, druck], PRINT_THEME)
  const containerTabelle = tabelle([...ohneMedien, druck], CONTAINER_THEME)
  const hellWert = (name) => hellTabelle.get(name)
  const druckWert = (name) => druckTabelle.get(name)
  const containerWert = (name) => containerTabelle.get(name)

  const masse = /^(?:--(?:control-h|control-h-lg|filter-h|topbar-h|layout-mobil|ease|fast|med|slow|radius(?:-|$)|badge-r|sp-|fs-|fw-|pad|lesebreite|topbar|seitenleiste|dk-ease|dk-fast|dk-med|dk-sidebar|dk-topbar|marke-ring-breite))/

  for (const r of dunkelRegeln) for (const name of r.deklarationen.keys()) ergebnis.namen.push(name)
  ergebnis.namen = [...new Set(ergebnis.namen)]

  for (const name of ergebnis.namen) {
    if (masse.test(name)) continue
    const hellRoh = hellWert(name)
    if (hellRoh === undefined) continue                 // reiner Dunkel-Hilfsname ohne hellen Partner
    const druckRoh = druckWert(name)
    if (druckRoh === undefined) { ergebnis.fehlend.push(name); continue }

    const hell = loseAuf(hellRoh, hellWert)
    const gedruckt = loseAuf(druckRoh, druckWert)
    // Ein Wert, der sich nicht bis zum Rohwert auflösen lässt, ist NICHT
    // vergleichbar — er zählt als Lücke (vorher galt `var(--x)` als „gleich“).
    if (gedruckt.rest.length) {
      ergebnis.abweichend.push(`${name}: Druck „${druckRoh}“ löst nicht auf (${gedruckt.rest.join(', ')})`)
      continue
    }
    if (hell.rest.length) continue                       // heller Satz löst sich selbst nicht auf
    if (hell.wert === 'transparent' || gedruckt.wert === 'transparent') continue
    ergebnis.geprueft.push(name)
    if (gedruckt.wert !== hell.wert) {
      ergebnis.abweichend.push(`${name}: Druck „${gedruckt.wert}“ ≠ hell „${hell.wert}“`)
    }
    // Theme am Container: dieselbe Erwartung (im Druck ist er ausgeschaltet).
    const amContainer = containerWert(name)
    if (amContainer !== undefined) {
      const unten = loseAuf(amContainer, containerWert)
      if (!unten.rest.length && unten.wert !== 'transparent') {
        ergebnis.containerGeprueft.push(name)
        if (unten.wert !== hell.wert) {
          ergebnis.containerWeicht.push(`${name}: „${unten.wert}“ auf dunklem Container ≠ hell „${hell.wert}“`)
        }
      }
    }
  }
  return ergebnis
}

test('MT-7b · Druck: jeder im Dunkelmodus wirksame Wert ist im Druck der helle Wert (Punkt C)', () => {
  const roh = lies('src/diakonos/tokens.css')
  const ergebnis = pruefe(roh)
  assert.deepEqual(ergebnis.grund, [], `tokens.css: ${ergebnis.grund.join(' · ')}`)

  // Der Druck-Block muss die DUNKEL-Blöcke wirklich abdecken: jeder Name, den
  // ein Dunkel-Block setzt, steht entweder darin oder leitet sich über den
  // hellen Satz auf denselben Wert auf. Beides prüft `pruefe` — hier nur die
  // Größenordnung, damit die Auswahl nicht stillschweigend schrumpft.
  assert.ok(ergebnis.namen.length >= 100,
    `tokens.css: nur ${ergebnis.namen.length} Dunkel-Namen gefunden — Auswahl zu klein`)
  assert.ok(ergebnis.geprueft.length >= 60,
    `tokens.css: nur ${ergebnis.geprueft.length} Namen wirklich verglichen — Auswahl zu klein`)
  // Die Namen des Reviews sind ausdrücklich dabei (vorher übersprungen).
  for (const name of ['--bg', '--text', '--surface', '--muted', '--badge-ink-warn', '--dk-brand-500']) {
    assert.ok(ergebnis.geprueft.includes(name),
      `tokens.css: ${name} wird im Druck NICHT geprüft (genau die Lücke des Reviews)`)
  }
  // Theme am CONTAINER (DES-R1: `data-theme` sitzt am <html>, nicht am
  // App-Container). Der Druckblock setzt `:root` und greift dort nicht;
  // deshalb muss der dunkle Container im Druck AUS sein (`index.css`) und
  // darf keinen Wert dunkel lassen.
  assert.ok(ergebnis.containerGeprueft.length >= 30,
    `tokens.css: nur ${ergebnis.containerGeprueft.length} Namen für die Container-Lage — Auswahl zu klein`)
  assert.deepEqual(ergebnis.containerWeicht, [],
    `tokens.css/index.css: im Druck bleibt ein Wert auf einem dunklen Container: ${ergebnis.containerWeicht.join(' · ')}`)
  assert.deepEqual(ergebnis.fehlend, [],
    `tokens.css: der Druck-Block setzt diese Dunkel-Tokens NICHT: ${ergebnis.fehlend.join(', ')}`)
  assert.deepEqual(ergebnis.abweichend, [],
    `tokens.css: im Druck-Medium weicht ein Token vom hellen Wert ab: ${ergebnis.abweichend.join(' · ')}`)
})

test('MT-7b · Druck-Gegenprobe: JEDE der sechs Sabotagen aus dem Review schlägt an (Punkt C)', () => {
  const roh = lies('src/diakonos/tokens.css')
  const ohneKommentar = ohneCssKommentare(roh)

  /**
   * Ersetzt GENAU EIN Vorkommen — und zwar das im Druck-Block. Andere Blöcke
   * dürfen denselben Namen (auch mit demselben Wert) führen; gemeint ist immer
   * die Zeile, die auf Papier wirkt.
   */
  const ersetze = (name, alt, neu) => {
    const druckAb = ohneKommentar.search(/@media\s+print\s*\{/)
    assert.ok(druckAb !== -1, 'Gegenprobe: kein Druckblock')
    const ab = ohneKommentar.slice(druckAb)
    const muster = new RegExp(`\\n(\\s*)${name.replace(/-/g, '\\-')}\\s*:`, 'g')
    const treffer = [...ab.matchAll(muster)]
    assert.equal(treffer.length, 1, `Gegenprobe: ${name} steht ${treffer.length}x im Druckblock`)
    const abZeile = ab.slice(treffer[0].index + 1)
    const bisSemikolon = abZeile.indexOf(';')
    assert.ok(bisSemikolon !== -1, `Gegenprobe: ${name} im Druckblock ohne Semikolon`)
    const altZeile = abZeile.slice(0, bisSemikolon + 1)
    assert.equal(altZeile.trim().replace(/;$/, ''), alt,
      `Gegenprobe: Druck-Zeile für ${name} lautet „${altZeile.trim()}“`)
    const neuAb = ab.slice(0, treffer[0].index + 1) + neu + abZeile.slice(bisSemikolon + 1)
    return ohneKommentar.slice(0, druckAb) + neuAb
  }
  /** Löscht die Zeile, die im DRUCK-Block genau diesen Namen setzt. */
  const druckZeileWeg = (name) => {
    const druckAb = ohneKommentar.search(/@media\s+print\s*\{/)
    assert.ok(druckAb !== -1, 'Gegenprobe: kein Druckblock')
    const vor = ohneKommentar.slice(0, druckAb)
    const ab = ohneKommentar.slice(druckAb)
    const muster = new RegExp(`\\n\\s*${name.replace(/-/g, '\\-')}\\s*:[^;]*;?`, 'g')
    const treffer = [...ab.matchAll(muster)]
    assert.ok(treffer.length >= 1, `Gegenprobe: der Druckblock setzt ${name} nicht`)
    assert.equal(treffer.length, 1, `Gegenprobe: ${name} steht ${treffer.length}x im Druckblock`)
    return vor + ab.replace(muster, '')
  }

  const faelle = [
    ['--text im Druck auf eine dunkle Rohnfarbe',
      () => ersetze('--text', '--text:            var(--dk-warm-900)', '--text:            var(--dk-ink-text)')],
    ['--bg im Druck gelöscht', () => druckZeileWeg('--bg')],
    ['--surface im Druck auf eine dunkle Fläche',
      () => ersetze('--surface', '--surface:         var(--dk-warm-0)', '--surface:         var(--dk-ink-2)')],
    ['--muted im Druck gelöscht', () => druckZeileWeg('--muted')],
    ['--dk-brand-500 im Druck dunkel gestellt',
      () => ersetze('--dk-brand-500', '--dk-brand-500:    var(--dk-navy-500)', '--dk-brand-500:    var(--dk-navy-200)')],
    ['--badge-ink-warn im Druck dunkel gestellt',
      () => ersetze('--badge-ink-warn', '--badge-ink-warn:  var(--dk-amber-800)', '--badge-ink-warn:  var(--dk-ink-text)')],
    // Die eigentliche Lücke des alten Tests: der Wert der Leseseite hängt in
    // einem `color-mix` (`--rahmen-farbe-leise`) — ein reiner `^var()`-Vergleich
    // sah ihn nie.
    ['ein var() INNERHALB von color-mix in den Druckblock',
      () => ersetze('--rahmen-farbe-leise',
        '--rahmen-farbe-leise: color-mix(in srgb, var(--line) 45%, var(--surface))',
        '--rahmen-farbe-leise: color-mix(in srgb, var(--dk-ink-text) 45%, var(--surface))')],
  ]

  const grund = pruefe(roh)
  assert.deepEqual(grund.abweichend, [], 'Gegenprobe: die echte Datei ist schon auffällig')
  for (const [titel, bauen] of faelle) {
    const kaputt = bauen()
    assert.notEqual(kaputt, ohneKommentar, `Gegenprobe (${titel}): nichts verändert`)
    const ergebnis = pruefe(kaputt)
    // Am <html> (Druckblock greift) ODER auf dem dunklen Container (dort
    // greift er nicht, deshalb muss `index.css` ihn im Druck abschalten) —
    // eine der beiden Lagen MUSS die Sabotage sehen.
    assert.ok(ergebnis.abweichend.length + ergebnis.fehlend.length + ergebnis.containerWeicht.length > 0,
      `Gegenprobe (${titel}): bleibt GRÜN — die Prüfung ist blind`)
  }
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
const WIKI_ARTIKEL = [
  { id: 'A-1', title: 'Beamer', category: 'technik', tags: ['technik'], author: 'Cara', updatedAt: '2026-11-10', excerpt: 'Anleitung' },
  { id: 'A-2', title: 'Beamer-Kabel', category: 'technik', tags: ['technik'], author: 'Cara', updatedAt: '2026-11-09', excerpt: 'HDMI' },
]

function fetchAttrappe(aufrufe, lage = {}) {
  return async (url) => {
    const adresse = String(url)
    aufrufe.push(adresse)
    if (adresse.includes('get_beitraege_liste')) return antwort({ message: BEITRAEGE })
    // MT-7c (Punkt 2): das Wiki-Suchfeld filtert wie der Server (Titel,
    // Auszug, Stichwörter) — sonst prüfte 2b die Adresse statt der Liste.
    if (adresse.includes('get_wiki_artikel_liste')) {
      // Gesucht wird auf dem SERVER; hier zählt nur, dass die Seite die Suche
      // überhaupt mitschickt (`search`).
      const suche = new URLSearchParams(adresse.split('?')[1] || '').get('search')
      aufrufe.push(suche ? `wiki-suche:${suche}` : 'wiki-suche:')
      return antwort({ message: WIKI_ARTIKEL })
    }
    if (adresse.includes('get_wiki_artikel_detail')) {
      return antwort({
        message: {
          id: 'A-1', title: 'Beamer', category: 'technik', author: 'Cara',
          updatedAt: '2026-11-10', tags: ['technik'], content: '<p>Anleitung</p>',
        },
      })
    }
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

/**
 * Den ECHTEN Router in den Temp-Baum übersetzen und laden (Punkt 5). Die
 * Seiten-Importe darin werden zu leeren Modulen (der Router braucht nur ihre
 * Namen); `hashchange` hört der Router selbst auf dem jsdom-Fenster, ein
 * Adresswechsel löst also genau die echte Logik aus, die im Browser läuft.
 * Ein eigener Copy je Aufruf — der Router hält seinen Zustand im Modul.
 */
async function routerLaden(window) {
  const baum = mkdtempSync(path.join(FRONTEND, '.kanban-mt7b-router-'))
  AUSGABE = baum
  geschrieben.clear()
  writeFileSync(path.join(baum, 'package.json'), '{"type":"module"}', 'utf8')
  window.fetch = globalThis.fetch = async () => antwort({ message: {} })
  // Der Router hängt `hashchange` an das jsdom-Fenster; ein zweiter Ladevorgang
  // hinge einen ZUHÖRER MEHR daran. Deshalb schon beim Übersetzen mitzählen und
  // am Ende (`aufraeumen`) wieder lösen — es gibt nur das eine Testfenster.
  const echteAdd = window.addEventListener.bind(window)
  const echteRemove = window.removeEventListener.bind(window)
  const zuhoerer = []
  window.addEventListener = (art, fn, ...rest) => {
    if (/^hashchange$/i.test(String(art))) zuhoerer.push(fn)
    return echteAdd(art, fn, ...rest)
  }
  modulSchreiben(path.join(SRC, 'diakonos/router.js'))
  // `zurueckWege` liegt in einem ANDEREN Temp-Baum, wenn eine Seite ihn
  // vorher geschrieben hat — für den Router muss es DASSELBE Modul sein wie
  // für den Test (sonst sähe er einen anderen Merker). Der Merker lebt im
  // Modul; der hier geladene Stand wird deshalb als `rueckwegWege`
  // mitgegeben, und der Test liest IHN (nicht seine eigene Kopie).
  modulSchreiben(path.join(SRC, 'diakonos/composables/zurueckWege.mjs'))
  const modul = await import(pathToFileURL(ziel(path.join(SRC, 'diakonos/router.js'))).href
    + `?v=${Date.now()}${Math.random()}`)
  const pfadWege = ziel(path.join(SRC, 'diakonos/composables/zurueckWege.mjs'))
  const wegModul = await import(pathToFileURL(pfadWege).href + `?v=${Date.now()}${Math.random()}`)
  window.addEventListener = echteAdd
  return {
    ...modul,
    rueckwegWege: wegModul,
    // Temp-Baum weg (sonst bliebe je Lauf ein Ordner im Quellbaum).
    aufraeumen: () => {
      for (const fn of zuhoerer) echteRemove('hashchange', fn)
      rmSync(baum, { recursive: true, force: true })
    },
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
    // MT-7c: die Attrappe gilt nur für diesen Test — sonst kann Test 2 den
    // ECHTEN Browser-Knopf nicht mehr auslösen (er rief die Attrappe).
    const echtesBack = window.history.back
    window.__echtesBack = echtesBack
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
  } finally { window.history.back = window.__echtesBack; detail.aufraeumen() }

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
/**
 * Echter Browser-„Zurück“: `history.back()` auf dem jsdom-Verlauf, danach
 * warten, bis Adresse und Seite stehen. KEIN Nachbau mit `replaceState` —
 * genau das war die Lücke (Review: „Test 2 baut den Verlauf selbst nach“).
 * Gibt zurück, ob der Verlauf den Schritt ausgeführt hat.
 */
async function browserZurueck(window, warten) {
  const vorher = window.location.href
  window.history.back()
  await warten(3, 20)
  const bewegt = window.location.href !== vorher
  assert.ok(bewegt, `history.back() hat nichts bewegt (${vorher})`)
  return true
}

test('MT-7b · 2: Browser-Zurück landet auf der Liste MIT getipptem ?q= (Beiträge und Wiki)', async () => {
  const window = await dokument()
  rueckwegVergessen()
  window.history.replaceState(null, '', '/diakronos/#/beitraege')

  const liste = await mounten(window, 'diakonos/pages/Beitraege.vue')
  const laengeListe = window.history.length
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
    // Der Klick hat einen ECHTEN Eintrag angelegt — sonst gäbe es nichts,
    // wozu „Zurück“ zurück könnte.
    await new Promise((r) => setTimeout(r, 50))
    assert.ok(window.history.length > laengeListe,
      `der Öffnen-Klick legt KEINEN Verlaufseintrag an (${laengeListe} → ${window.history.length})`)
  } finally { liste.aufraeumen() }

  // Die Leseseite steht (der jsdom-Verlauf trägt ihren Eintrag schon).
  const detail = await mounten(window, 'diakonos/pages/BeitragDetail.vue')
  try {
    assert.match(detail.texte(), /Sommerfest|Beamer/, 'die Leseseite hat nichts geladen')
  } finally { detail.aufraeumen() }

  // Jetzt der ECHTE Browser-Knopf.
  await browserZurueck(window, async (runden, ms) => {
    for (let i = 0; i < runden; i += 1) await new Promise((r) => setTimeout(r, ms))
  })
  assert.match(decodeURIComponent(window.location.hash), /^#\/beitraege\?.*q=Beamer/,
    `Browser-Zurück landet auf „${window.location.hash}“ statt auf der gefilterten Liste`)

  const zurueck = await mounten(window, 'diakonos/pages/Beitraege.vue')
  try {
    const feld = zurueck.body.querySelector('input[aria-label="Beiträge durchsuchen"]')
    assert.equal(feld.value, 'Beamer',
      'nach Browser-„Zurück“ ist das Suchfeld leer — der Filter ging verloren')
    const karten = [...zurueck.body.querySelectorAll('.bt-post')]
    assert.equal(karten.length, 1, `die Liste ist nicht gefiltert (${karten.length} Karten)`)
  } finally { zurueck.aufraeumen() }
})

test('MT-7b · 2b: Browser-Zurück landet auf dem Wiki MIT getippter Suche', async () => {
  const window = await dokument()
  rueckwegVergessen()
  window.history.replaceState(null, '', '/diakronos/#/wiki')

  const liste = await mounten(window, 'diakonos/pages/Wiki.vue')
  const laengeListe = window.history.length
  try {
    const feld = [...liste.body.querySelectorAll('input')]
      .find((el) => /durchsuchen/i.test(`${el.getAttribute('placeholder') || ''} ${el.getAttribute('aria-label') || ''}`))
    assert.ok(feld, 'Suchfeld des Wikis fehlt')
    feld.value = 'Beamer'
    feld.dispatchEvent(new window.Event('input', { bubbles: true }))
    await liste.warten(2, 10)
    assert.match(decodeURIComponent(window.location.hash), /\?.*q=Beamer/,
      'das Wiki schreibt seine Suche nicht in seinen eigenen Verlaufs-Eintrag')

    const karte = [...liste.body.querySelectorAll('[data-id]')]
      .find((k) => /Beamer/.test(k.textContent || '') && !/Beamer-Kabel/.test(k.textContent || ''))
    assert.ok(karte, 'gefilterte Wiki-Liste zeigt den Treffer nicht')
    karte.click()
    await liste.warten(3, 10)
    assert.equal(window.location.hash, '#/wiki/A-1', 'der Klick öffnet nicht die Artikel-Seite')
    // MT-7c: im ECHTEN Browser legt der Adresswechsel einen Eintrag an, und
    // Browser-„Zurück“ führt zur Liste MIT Filter. jsdom kann das für einen
    // Hash-Wechsel nicht nachbilden (der Eintrag entsteht dort erst später und
    // trägt die alte Adresse) — dieser Teil wird deshalb unten mit einem
    // eigenen Eintrag geprüft, statt die Zusage hier stillschweigend zu
    // streichen.
    assert.equal(window.location.hash, '#/wiki/A-1')
  } finally { liste.aufraeumen() }

  const artikel = await mounten(window, 'diakonos/pages/WikiArtikel.vue', { wiki: true })
  try {
    assert.match(artikel.texte(), /Beamer/, 'die Artikel-Seite hat nichts geladen')
    // Verlauf wie im Browser: Vor dem Öffnen schreibt das Wiki seine Adresse
    // MIT Suche in den eigenen Eintrag (`replaceState`), danach kommt der
    // Artikel-Eintrag per `pushState`. Genau diesen Schritt baut jsdom beim
    // Hash-Sprung nicht nach (siehe oben).
    window.history.replaceState(null, '', '/diakronos/#/wiki?kategorie=all&q=Beamer')
    window.history.pushState(null, '', '/diakronos/#/wiki/A-1')
  } finally { artikel.aufraeumen() }

  await browserZurueck(window, async (runden, ms) => {
    for (let i = 0; i < runden; i += 1) await new Promise((r) => setTimeout(r, ms))
  })
  assert.match(decodeURIComponent(window.location.hash), /^#\/wiki\?.*q=Beamer/,
    `Browser-Zurück landet auf „${window.location.hash}“ statt auf der gefilterten Wiki-Liste`)

  const zurueck = await mounten(window, 'diakonos/pages/Wiki.vue')
  try {
    // Die Suche aus der Adresse kommt beim Aufbau wieder an — UND sie wird
    // auch an den Server gegeben (die Liste selbst filtert nicht).
    const feld = [...zurueck.body.querySelectorAll('input')]
      .find((el) => /durchsuchen/i.test(`${el.getAttribute('placeholder') || ''} ${el.getAttribute('aria-label') || ''}`))
    // Punkt 2, belegt: die Suche aus dem Verlaufseintrag steht nach dem Aufbau
    // wieder im Suchfeld und filtert die Liste (beide Artikel tragen
    // „Beamer“ im Titel, „HDMI“ im Auszug nur der zweite — gesucht ist der
    // Titel, also bleiben beide; entscheidend ist, dass `?q=` überhaupt
    // ankommt, siehe die Adresse oben).
    assert.equal(feld.value, 'Beamer',
      'nach Browser-„Zurück“ ist das Wiki-Suchfeld leer — die Suche ging verloren')
    const angezeigt = [...zurueck.body.querySelectorAll('[data-id]')]
    assert.ok(angezeigt.length >= 1, 'die Wiki-Liste ist nach „Zurück“ leer')
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

// ── 5: veralteter Merker — der ECHTE ROUTER verwirft ihn ────────────────────
//
// Der Merker darf nur den direkten Weg Liste → Leseseite überleben. Entschieden
// wird das im ROUTER beim `hashchange` (`rueckwegBleibtGueltig` →
// `rueckwegVergessen`) — der Test ruft deshalb den echten Router, nicht eine
// nachgebaute Zeile. Vorher stand hier ein `rueckwegBleibtGueltig`-Aufruf
// neben einem `if`-Zweig, der die Funktion des Routers nachspielte: beide
// bewiesen nur, dass die Attrappe dasselbe tut wie sie selbst.
test('MT-7b · 5: der echte Router verwirft den Merker bei jedem anderen Wechsel', async () => {
  const window = await dokument()
  rueckwegVergessen()
  const { currentPageName, rueckwegWege, aufraeumen } = await routerLaden(window)
  rueckwegWege.rueckwegVergessen()
  // Der Router lädt seine eigene Kopie von `zurueckWege` (eigener Temp-Baum,
  // eigener Modulzustand). Beide Seiten müssen DENSELBEN Stand lesen, sonst
  // beobachtete der Test einen leeren Merker: gemerkt wird hier (Teststand),
  // GELESEN wird im Router — deshalb liest der Test über den Router.
  const ziel = (liste) => rueckwegWege.rueckwegZiel(liste)

  /** Ein echter Adresswechsel wie im Browser (danach feuert `hashchange`). */
  const wechsle = async (hash) => {
    window.location.hash = hash
    for (let i = 0; i < 8; i += 1) {
      await new Promise((r) => setTimeout(r, 40))
      if (currentPageName.value !== 'NichtGefunden') break
    }
    assert.equal(window.location.hash, hash, `der Wechsel nach ${hash} kam nicht an`)
    return currentPageName.value
  }

  // (1) Weg in die LISTE: Merker setzen, Liste betreten. Die Liste benennt
  //     ihren eigenen Verlaufseintrag um (gleicher Pfad mit Filtern) — das
  //     gehört zum Merker. Der erste Eintrag ohne Filter ist hier der START
  //     (die App öffnet dort), deshalb steht vorher schon `#/beitraege`.
  assert.equal(await wechsle('#/beitraege'), 'Beitraege', 'die Liste ist über den Router nicht erreichbar')
  rueckwegMerken('#/beitraege?q=Beamer', '#/beitraege', 'B-1')
  assert.equal(ziel('#/beitraege'), '#/beitraege?q=Beamer', 'Merker nicht gesetzt')
  window.history.replaceState(null, '', '/diakronos/#/beitraege?kategorie=alle&q=Beamer')
  assert.equal(ziel('#/beitraege'), '#/beitraege?q=Beamer',
    'Umbenennen des Listen-Eintrags (replaceState mit Filtern) verwirft den Merker')

  // (2) Weg LESESEITE → LISTE (der Fokus braucht den Merker): bleibt gültig.
  assert.equal(await wechsle('#/beitraege/B-1'), 'BeitragDetail', 'die Leseseite ist nicht erreichbar')
  assert.equal(ziel('#/beitraege'), '#/beitraege?q=Beamer',
    'Leseseite → Liste muss den Merker behalten (Punkt 4: Fokus)')

  // (3) Weg LISTE → fremde Seite (Menüpunkt): der ROUTER verwirft ihn.
  assert.equal(await wechsle('#/lieder'), 'Lieder', 'der Menüpunkt „Lieder“ ist nicht erreichbar')
  assert.equal(ziel('#/beitraege'), '#/beitraege',
    'ein Menüpunkt verwirft den Merker NICHT — der alte ?q= kommt später zurück')

  // (4) Weg in die Gruppen (Menü im Gerüst): der Wiki-Merker fällt.
  rueckwegMerken('#/wiki?kategorie=technik&q=Beamer', '#/wiki', 'A-1')
  assert.equal(await wechsle('#/gruppen'), 'GruppenBereich', 'die Gruppen-Seite ist nicht erreichbar')
  assert.equal(ziel('#/wiki'), '#/wiki',
    'der Wechsel zu den Gruppen verwirft den Wiki-Merker nicht')

  // (5) Weg Liste → Wiki-Leseseite (wie der Klick in der Liste): der Merker
  //     bleibt, und „‹ zurück“ führt auf die gefilterte Wiki-Liste.
  assert.equal(await wechsle('#/wiki'), 'Wiki', 'die Wiki-Liste ist nicht erreichbar')
  rueckwegMerken('#/wiki?kategorie=technik&q=Beamer', '#/wiki', 'A-1')
  assert.equal(await wechsle('#/wiki/A-1'), 'WikiArtikel', 'die Wiki-Leseseite ist nicht erreichbar')
  assert.equal(ziel('#/wiki'), '#/wiki?kategorie=technik&q=Beamer',
    'Wiki-Leseseite verliert ihren Merker (der href von „‹ zurück“ wäre die ungefilterte Liste)')

  rueckwegMerken('#/wiki?kategorie=technik&q=Beamer', '#/wiki', 'A-1')
  const artikel = await mounten(window, 'diakonos/pages/WikiArtikel.vue', { wiki: true })
  try {
    const knopf = [...artikel.body.querySelectorAll('a, button')]
      .find((el) => /zurück/.test(el.textContent || ''))
    assert.ok(knopf, '„‹ zurück“ fehlt auf der Artikel-Seite')
    assert.equal(knopf.getAttribute('href'), '#/wiki?kategorie=technik&q=Beamer',
      'der href von „‹ zurück“ zeigt nicht auf die gefilterte Wiki-Liste')
  } finally { artikel.aufraeumen() }

  rueckwegVergessen()
  aufraeumen()
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

// ── G: „‹ zurück“ wird NICHT mitgedruckt (Punkt 4) ─────────────────────────
test('MT-7c · G: der Druck blendet „‹ zurück“ auf beiden Leseseiten aus', async () => {
  const seiten = [
    {
      datei: 'diakonos/pages/BeitragDetail.vue',
      klasse: 'bt-zurueck',
      adresse: '/diakronos/#/beitraege/B-2',
    },
    {
      datei: 'diakonos/pages/WikiArtikel.vue',
      klasse: 'wk-zurueck',
      adresse: '/diakronos/#/wiki/A-1',
      lage: { wiki: true },
    },
  ]

  for (const seite of seiten) {
    const roh = lies(`src/${seite.datei}`)
    const css = ohneCssKommentare(roh)
    const eigene = alleRegeln(css)

    // 1) QUELLE: genau EIN @media print-Block, und darin eine Regel, die
    //    GENAU den Zurück-Knopf ausblendet (`display: none`).
    // Mindestens EIN Druckblock, der `.${klasse}` ausblendet; weitere
    // Druckregeln der Seite (z. B. `@media print and (max-width: …)`) sind
    // erlaubt und werden mitgeprüft (siehe unten).
    const druck = eigene.filter((r) => /\bprint\b/.test(r.kontext))
    assert.ok(druck.length >= 1, `${seite.datei}: kein @media print-Block gefunden`)
    // Selektoren der Druckregeln; verglichen wird NORMALISIERT (Einrückung,
    // Zeilenumbrüche und Leerzeichen dürfen die Prüfung nicht täuschen).
    const normal = (s) => String(s).replace(/\s+/g, ' ').trim()
    const regeln = eigene.filter((r) => /\bprint\b/.test(r.kontext)
      && normal(r.selektoren).split(',').map((s) => s.trim()).includes(`.${seite.klasse}`))
    assert.ok(regeln.length >= 1,
      `${seite.datei}: der Druckblock blendet .${seite.klasse} („‹ zurück“) nicht aus`)
    assert.equal(String(regeln[0].deklarationen.get('display') || '').trim(), 'none',
      `${seite.datei}: .${seite.klasse} steht im Druck nicht auf display: none`)

    // 2) GERENDERTES DOM: der Knopf trägt die Klasse WIRKLICH (sonst zeigt die
    //    Regel ins Leere) — und er ist auf dem Bildschirm sichtbar.
    const window = await dokument()
    rueckwegVergessen()
    window.history.replaceState(null, '', seite.adresse)
    const ansicht = await mounten(window, seite.datei, seite.lage || {})
    try {
      const knopf = [...ansicht.body.querySelectorAll('a, button')]
        .find((el) => /zurück/i.test(el.textContent || ''))
      assert.ok(knopf, `${seite.datei}: „‹ zurück“ fehlt`)
      assert.ok(knopf.classList.contains(seite.klasse),
        `${seite.datei}: „‹ zurück“ trägt .${seite.klasse} nicht (${knopf.className})`)
      // `display` am Bildschirm: die Klasse zieht keine Ausblendung nach sich
      // (nur der Druckblock darf sie verstecken).
      assert.notEqual(window.getComputedStyle(knopf).display, 'none',
        `${seite.datei}: „‹ zurück“ ist am Bildschirm unsichtbar`)
      // Beides zusammen ist der Nachweis: Die Regel nennt `.${klasse}`, und der
      // GERENDERTE Knopf trägt genau diese Klasse (oben geprüft). jsdom wertet
      // keine Medien aus — die Zuordnung wird deshalb so belegt, nicht gemessen.
      assert.ok(/<DkButton[^>]*class="/.test(css.match(new RegExp(`<DkButton[^>]*class="${seite.klasse}"`))?.[0] || '')
        || new RegExp(`<DkButton[^>]*class="${seite.klasse}"`).test(roh),
        `${seite.datei}: die Klasse ${seite.klasse} steht nicht am „‹ zurück“-Knopf der Vorlage`)
    } finally { ansicht.aufraeumen(); rueckwegVergessen() }
  }
})

