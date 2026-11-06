/**
 * FIX-7 — Werkzeug: findet Template-Bezeichner in `.vue`-Dateien, die im
 * `<script setup>` nicht gebunden sind.
 *
 * Hintergrund: `ModerationCard.vue` rief im Template `fmtDate(…)` auf, die
 * Funktion stand aber im `<script setup>` gar nicht — Vue laesst den Ausdruck
 * zur Laufzeit mit „Property "fmtDate" was accessed during render but is not
 * defined" auflaufen, die Stelle bleibt leer. Der Compiler prueft das nicht
 * (er kennt den Inhalt des Templates nicht gegen die Bindings).
 *
 * Vorgehen:
 *   1. `.vue` per `@vue/compiler-sfc` zerlegen (`parse`).
 *   2. Ausdruecke des Templates sammeln (Interpolation, `v-if`/`v-for`/`v-model`
 *      usw., Ausdruecke von Bindungswerten) und per `@babel/parser` zu einem
 *      AST wandeln. Daraus die FREIEN Bezeichner nach Abzug der lokal
 *      eingefuehrten (`v-for="x in y"`, `v-slot="{ a }"`, Arrow-Parameter).
 *   3. Im Skript die Bindungen der obersten Blockebene sammeln — am
 *      einfachsten am Ergebnis von `compileScript` (`export default { setup()
 *      {…} }`): dessen `setup`-Rumpf enthaelt alle Deklarationen und Importe.
 *      Aus `props`/`emits` kommen die Requisiten-Namen und `emit`/`$event`
 *      hinzu, weil Vue sie im Template unter ihren NAMEN bereitstellt.
 *   4. Gemeldet wird jeder freie Template-Name, der weder im Skript steht noch
 *      in `ERLAUBT` (Sprache, Vue-Globals, Projekt-Globals). Ausnahmen in der
 *      Erlaubt-Liste tragen eine Begruendung.
 *
 * Ausgabe ueber `pruefeBaum`/`pruefeQuelle`; die Testdatei
 * `tests/fix7-vorlagen-bezeichner.test.mjs` haelt den Baum sauber.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Bezeichner, die im Template stehen duerfen, ohne im Skript deklariert zu sein.
 * Jeder Eintrag braucht einen Grund — die Liste ist Teil des Vertrags.
 */
export const ERLAUBT = new Map([
  // Sprache / eingebaute Objekte, die in Ausdruecken vorkommen.
  ['true', 'Sprache: Wahrheitswert'],
  ['false', 'Sprache: Wahrheitswert'],
  ['null', 'Sprache: leerer Wert'],
  ['undefined', 'Sprache: nicht gesetzt'],
  ['NaN', 'Sprache: Zahlenwert'],
  ['Infinity', 'Sprache: Zahlenwert'],
  ['Math', 'eingebautes Objekt (Rundung, min/max)'],
  ['Date', 'eingebautes Objekt (Datum im Ausdruck)'],
  ['Number', 'eingebautes Objekt'],
  ['String', 'eingebautes Objekt'],
  ['Boolean', 'eingebautes Objekt'],
  ['Array', 'eingebautes Objekt'],
  ['Object', 'eingebautes Objekt'],
  ['JSON', 'eingebautes Objekt'],
  ['parseInt', 'eingebaute Funktion'],
  ['parseFloat', 'eingebaute Funktion'],
  ['isNaN', 'eingebaute Funktion'],
  ['encodeURIComponent', 'eingebaute Funktion (Linkziele)'],
  ['decodeURIComponent', 'eingebaute Funktion (Linkziele)'],
  ['console', 'Diagnose in der Entwicklung'],
  // Vue-Globals im Template — von Vue je Instanz bereitgestellt.
  ['$emit', 'Vue-Global ($emit)'],
  ['$attrs', 'Vue-Global ($attrs)'],
  ['$slots', 'Vue-Global ($slots)'],
  ['$props', 'Vue-Global ($props)'],
  ['$el', 'Vue-Global ($el)'],
  ['$refs', 'Vue-Global ($refs)'],
  ['$parent', 'Vue-Global ($parent)'],
  ['$root', 'Vue-Global ($root)'],
  ['$nextTick', 'Vue-Global ($nextTick)'],
  // vue-router haengt beide an JEDE Komponente (app.use(router)).
  ['$router', 'vue-router-Global (app.use(router))'],
  ['$route', 'vue-router-Global (app.use(router))'],
])

/** Namen, die Vue in Ereignis- und Modellbindungen selbst bereitstellt. */
const EVENT_LOKAL = ['$event']

/** Nicht-Funktionsbezeichner, die im AST keine freien Namen sind. */
const WORTE = new Set([
  'this', 'arguments', 'super', 'new', 'typeof', 'void', 'delete', 'in', 'of',
  'instanceof', 'await', 'yield',
])

/** Alle freien Bezeichner eines Ausdrucks-AST (babel `parseExpression`). */
export function freieNamen(knoten, lokal = new Set(), ergebnis = new Set()) {
  if (!knoten || typeof knoten !== 'object') return ergebnis
  if (Array.isArray(knoten)) {
    for (const kind of knoten) freieNamen(kind, lokal, ergebnis)
    return ergebnis
  }
  switch (knoten.type) {
    case 'Identifier':
      if (!lokal.has(knoten.name) && !WORTE.has(knoten.name)) ergebnis.add(knoten.name)
      return ergebnis
    case 'MemberExpression':
    case 'OptionalMemberExpression':
      freieNamen(knoten.object, lokal, ergebnis)
      if (knoten.computed) freieNamen(knoten.property, lokal, ergebnis)
      return ergebnis
    case 'ObjectProperty':
    case 'ObjectMethod':
    case 'ClassProperty':
    case 'ClassMethod': {
      if (knoten.computed) freieNamen(knoten.key, lokal, ergebnis)
      if (knoten.params) {
        const inner = new Set(lokal)
        sammleParams(knoten.params, inner)
        freieNamen(knoten.body, inner, ergebnis)
      } else {
        freieNamen(knoten.value, lokal, ergebnis)
      }
      return ergebnis
    }
    case 'Property':
      if (knoten.computed) freieNamen(knoten.key, lokal, ergebnis)
      freieNamen(knoten.value, lokal, ergebnis)
      return ergebnis
    case 'VariableDeclarator': {
      const inner = new Set(lokal)
      sammleBindungsMuster(knoten.id, inner)
      freieNamen(knoten.init, inner, ergebnis)
      return ergebnis
    }
    case 'FunctionDeclaration':
    case 'FunctionExpression':
    case 'ArrowFunctionExpression': {
      const inner = new Set(lokal)
      if (knoten.id) inner.add(knoten.id.name)
      sammleParams(knoten.params, inner)
      freieNamen(knoten.body, inner, ergebnis)
      return ergebnis
    }
    case 'UnaryExpression':
      // `typeof x` ist KEIN freier Verweis auf `x` (nur eine Typprüfung) —
      // alles andere (`!x`, `-x`, `void x`) schon.
      if (knoten.operator === 'typeof') return ergebnis
      freieNamen(knoten.argument, lokal, ergebnis)
      return ergebnis
    case 'TSAsExpression':
    case 'TSSatisfiesExpression':
    case 'TSNonNullExpression':
    case 'ParenthesizedExpression':
      freieNamen(knoten.expression, lokal, ergebnis)
      return ergebnis
    default:
      for (const [schluessel, wert] of Object.entries(knoten)) {
        if (schluessel === 'loc' || schluessel === 'start' || schluessel === 'end') continue
        if (wert && typeof wert === 'object') freieNamen(wert, lokal, ergebnis)
      }
      return ergebnis
  }
}

export function sammleParams(params, lokal) {
  if (!params) return
  for (const p of params) sammleBindungsMuster(p, lokal)
}

/** Alle Namen, die ein Bindungsmuster (id/param/Muster) einfuehrt. */
export function sammleBindungsMuster(muster, lokal) {
  if (!muster || typeof muster !== 'object') return
  switch (muster.type) {
    case 'Identifier':
      lokal.add(muster.name)
      break
    case 'AssignmentPattern':
      sammleBindungsMuster(muster.left, lokal)
      break
    case 'RestElement':
      sammleBindungsMuster(muster.argument, lokal)
      break
    case 'ArrayPattern':
      for (const e of muster.elements) sammleBindungsMuster(e, lokal)
      break
    case 'ObjectPattern':
      for (const p of muster.properties) sammleBindungsMuster(p.value || p.argument, lokal)
      break
    case 'TSParameterProperty':
      sammleBindungsMuster(muster.parameter, lokal)
      break
    default:
      break
  }
}

/**
 * Prueft eine einzelne SFC-Quelle.
 *
 * `sfc` = `@vue/compiler-sfc`, `babel` = `@babel/parser` (wird hereingereicht,
 * damit dieses Werkzeug ohne Abhaengigkeit importierbar bleibt).
 *
 * Ergebnis: { fehlend: [{name, stelle}], fehler: string|null }
 */
export function pruefeQuelle(quelle, datei, sfc, babel) {
  const { descriptor, errors } = sfc.parse(quelle, { filename: datei })
  if (errors && errors.length) {
    return { fehlend: [], fehler: 'SFC-Fehler: ' + errors.map((e) => e.message || String(e)).join('; ') }
  }
  if (!descriptor.template) return { fehlend: [], fehler: null }

  // ── 1. Template-Ausdruecke einsammeln ───────────────────────────────────
  // Ein Ausdruck ist jeder Bindungswert (`:x`, `@x`, `v-if`, …), jede
  // Interpolation und jeder `v-slot`-Wert. `v-for` fuehrt Laufvariablen ein,
  // die im Teilbaum gelten — sie werden als `lokal` mitgefuehrt.
  const ausdruecke = [] // { code, lokal: Set, zeile }
  const AST = descriptor.template.ast

  const sammleAusdruck = (inhalt, knoten, zusatzLokal, extra = []) => {
    const code = inhalt && typeof inhalt.content === 'string' ? inhalt.content.trim() : ''
    if (!code) return
    const lokal = new Set(zusatzLokal || [])
    for (const n of extra) lokal.add(n)
    ausdruecke.push({
      code,
      lokal,
      zeile: knoten && knoten.loc ? knoten.loc.start.line : 0,
    })
  }

  /** Namen, die ein `v-slot`-Wert einfuehrt (`{ a, b }`, `props`, `[a]`). */
  const slotNamen = (code) => {
    const namen = new Set()
    const text = (code || '').trim()
    if (!text) return namen
    try {
      const ast = babel.parseExpression(text, { plugins: ['jsx'] })
      // `parseExpression('{ a, b }')` liefert ein Objekt-Muster, `v-slot="feld"`
      // einen einfachen Bezeichner — beides bindet sich selbst.
      sammleBindungsMuster(ast, namen)
    } catch {
      // `v-slot="feld"` ist ein blosser Name, kein Ausdruck — `parseExpression`
      // liefert dafuer keinen Wert. Ein reiner Bezeichner bindet sich selbst.
      if (/^[A-Za-z_$][\w$]*$/.test(text)) namen.add(text)
    }
    return namen
  }

  const gehe = (knoten, lokal) => {
    if (!knoten || typeof knoten !== 'object') return
    if (Array.isArray(knoten)) {
      for (const k of knoten) gehe(k, lokal)
      return
    }
    if (knoten.type === 1 /* ELEMENT */ || knoten.type === 0 /* ROOT */) {
      const eigen = new Set(lokal)
      for (const prop of knoten.props || []) {
        // Nur DIREKTIVEN tragen Ausdruecke (`:title`, `@click`, `v-if`, …).
        // Ein normales Attribut (`class="…"`, `type="text"`) ist Text, kein
        // Ausdruck — sonst gaelte jedes Wort im Klassennamen als Name.
        if (prop.type === 6 /* ATTRIBUTE */) continue
        if (prop.type !== 7 /* DIRECTIVE */) continue
        if (prop.name === 'for') {
          if (prop.forParseResult) {
            const r = prop.forParseResult
            if (r.source) sammleAusdruck(r.source, knoten, eigen)
            // Die Aliasse sind Knoten der Template-Syntax (Typ 4 = einfacher
            // Ausdruck) mit dem Namen in `content` — keine Babel-Identifier.
            for (const alias of [r.value, r.key, r.index]) {
              const name = alias && (alias.content || (alias.type === 'Identifier' ? alias.name : null))
              if (name && /^[A-Za-z_$][\w$]*$/.test(name)) eigen.add(name)
            }
          }
          continue
        }
        // `v-slot` fuehrt Muster ein (`v-slot="feld"`, `#{ a, b }`); das
        // Muster selbst ist KEIN Ausdruck (sonst gaelte `feld` als frei).
        if (prop.name === 'slot') continue
        // `$event` fuehrt JEDE Ereignisbindung ein (`@click="f($event)"`).
        if (prop.exp) sammleAusdruck(prop.exp, knoten, eigen, EVENT_LOKAL)
      }
      // `v-slot` gilt fuer den Teilbaum; die Namen sind dort lokal.
      const slot = (knoten.props || []).find((p) => p.type === 7 && p.name === 'slot')
      const kinderLokal = new Set(eigen)
      if (slot && slot.exp) {
        // Die `exp` eines `v-slot` traegt den Rohtext in `.content` und das
        // geparste Muster in `.ast` (Typ `ArrowFunctionExpression`, die Namen
        // haengen in `params`). Beide Wege werden genommen, damit
        // `v-slot="{ a }"` wie `v-slot="feld"` gebunden ist.
        for (const n of slotNamen(slot.exp.content)) kinderLokal.add(n)
        const ast = slot.exp.ast
        if (ast) {
          if (Array.isArray(ast.params)) sammleParams(ast.params, kinderLokal)
          else sammleBindungsMuster(ast, kinderLokal)
        }
      }
      for (const kind of knoten.children || []) gehe(kind, kinderLokal)
      return
    }
    if (knoten.type === 5 /* INTERPOLATION */) {
      sammleAusdruck(knoten.content, knoten, lokal)
      return
    }
    if (knoten.type === 2 /* TEXT */ || knoten.type === 3 /* COMMENT */) return
    if (knoten.type === 9 /* IF */) {
      for (const zweig of knoten.branches || []) {
        if (zweig.condition) sammleAusdruck(zweig.condition, knoten, lokal)
        for (const kind of zweig.children || []) gehe(kind, lokal)
      }
      return
    }
    if (knoten.type === 11 /* FOR */) {
      const eigen = new Set(lokal)
      if (knoten.source) sammleAusdruck(knoten.source, knoten, lokal)
      for (const alias of [knoten.valueAlias, knoten.keyAlias, knoten.objectIndexAlias]) {
        if (alias) sammleBindungsMuster({ type: 'Identifier', name: alias.content || alias }, eigen)
      }
      for (const kind of knoten.children || []) gehe(kind, eigen)
      return
    }
    if (knoten.type === 12 /* TEXT_CALL */ || knoten.type === 15 /* JS_CONDITIONAL */) {
      if (knoten.content) sammleAusdruck(knoten.content, knoten, lokal)
      return
    }
    for (const [schluessel, wert] of Object.entries(knoten)) {
      if (schluessel === 'loc' || schluessel === 'start' || schluessel === 'end') continue
      if (wert && typeof wert === 'object') gehe(wert, lokal)
    }
  }
  if (AST) gehe(AST, new Set())

  // ── 2. Skript-Bindungen einsammeln ──────────────────────────────────────
  const bindungen = new Set()
  const skript = descriptor.scriptSetup || descriptor.script
  if (skript) {
    let code = skript.content
    if (descriptor.scriptSetup) {
      // `compileScript` wandelt das Setup-Skript in `export default { setup() {…} }`
      // um; `sammleSkriptBindings` liest daraus die Deklarationen der
      // setup-Funktion. Es erwartet das DESKRIPTOR (nicht den SFC-Rumpf) und
      // wirft sonst „SFC contains no <script> tags." — dann bleibt der
      // Klartext als Rueckfallebene (Options-API, `lang="ts"`).
      try {
        const erg = sfc.compileScript(descriptor, { id: 'fix7', inlineTemplate: false })
        code = erg.content
        // Vues eigene Bindungsliste (u. a. Props aus `defineProps` ohne Variable).
        for (const n of Object.keys(erg.bindings || {})) bindungen.add(n)
      } catch {
        code = skript.content
      }
    }
    for (const name of sammleSkriptBindings(code, babel)) bindungen.add(name)
  }

  // ── 3. Freie Namen je Ausdruck ──────────────────────────────────────────
  const fehlend = []
  const gesehen = new Set()
  for (const { code, lokal, stelle } of ausdruecke) {
    let ast
    try {
      ast = babel.parseExpression(code, { plugins: ['jsx', 'typescript'], errorRecovery: false })
    } catch {
      try {
        ast = babel.parseExpression(code.replace(/^\s*\{|\}\s*$/g, ''), { plugins: ['jsx', 'typescript'] })
      } catch {
        continue // kein Ausdruck (z. B. statischer Wert): nichts zu pruefen
      }
    }
    // Namensregel: In Vue-Bindungen ist `feld.aria-describedby` ein
    // PROPERTY-Zugriff (`feld['aria-describedby']`). `parseExpression` liest
    // daraus eine Subtraktion (`feld.aria - describedby`) und meldete
    // `describedby` faelschlich als freien Namen. Deshalb zaehlen Namen, die
    // direkt links neben einem `-` stehen (und ein `.` tragen), wie ein
    // Member-Zugriff; `a - b` mit einfachen Namen bleibt unberuehrt.
    const eigenschaftsNamen = new Set()
    for (const knoten of alleKnoten(ast)) {
      if (knoten.type !== 'BinaryExpression' || knoten.operator !== '-') continue
      if (knoten.left && knoten.left.type === 'MemberExpression') {
        sammleBindungsMuster(knoten.right, eigenschaftsNamen)
      }
    }
    for (const name of eigenschaftsNamen) lokal.add(name)
    for (const name of freieNamen(ast, new Set(lokal))) {
      if (ERLAUBT.has(name)) continue
      if (bindungen.has(name)) continue
      if (gesehen.has(name)) continue
      gesehen.add(name)
      fehlend.push({ name, stelle })
    }
  }
  fehlend.sort((a, b) => a.stelle - b.stelle || a.name.localeCompare(b.name))
  return { fehlend, fehler: null }
}

/**
 * Bindungen der obersten Blockebene eines (kompilierten) Skripts.
 * Liest nur, was nach `parseScript` auf Programm-Ebene steht — Funktions-
 * koerper und Bloecke zaehlen nicht, ihre Namen sind keine Template-Bindings.
 */
export function sammleSkriptBindings(code, babel) {
  const namen = new Set()
  let programm
  try {
    programm = babel.parse(code, {
      sourceType: 'module',
      plugins: ['jsx', 'typescript'],
      allowReturnOutsideFunction: true,
    })
  } catch {
    return namen
  }
  const nimm = (id) => sammleBindungsMuster(id, namen)
  for (const knoten of programm.program.body) {
    switch (knoten.type) {
      case 'ImportDeclaration':
        for (const s of knoten.specifiers) namen.add(s.local.name)
        break
      case 'VariableDeclaration':
        for (const d of knoten.declarations) nimm(d.id)
        break
      case 'FunctionDeclaration':
      case 'ClassDeclaration':
        if (knoten.id) namen.add(knoten.id.name)
        break
      case 'ExportNamedDeclaration':
        if (knoten.declaration) {
          if (knoten.declaration.id) namen.add(knoten.declaration.id.name)
          if (knoten.declaration.declarations) {
            for (const d of knoten.declaration.declarations) nimm(d.id)
          }
        }
        break
      case 'ExportDefaultDeclaration':
        // `<script setup>`: der Compiler legt alles in `export default { setup() {…} }`.
        // Die Bindungen stehen dort als Body-Anweisungen der `setup`-Funktion
        // (nebst `__returned__`). Ohne diesen Zweig waere JEDE Deklaration
        // unsichtbar und der Waechter meldete den ganzen Baum.
        nimmOptionenBindings(knoten.declaration, namen)
        break
      default:
        break
    }
  }
  return namen
}

/** Bindungen aus einem Options- oder Setup-Objekt (`export default {…}`). */
function nimmOptionenBindings(obj, namen) {
  if (!obj || typeof obj !== 'object') return
  if (obj.type === 'ObjectExpression') {
    for (const prop of obj.properties) {
      if (prop.type !== 'ObjectProperty' && prop.type !== 'Property' && prop.type !== 'ObjectMethod' && prop.type !== 'MethodDefinition') {
        // spread: nichts zu binden
        continue
      }
      const schluessel = prop.key && (prop.key.name || prop.key.value)
      // Methoden (`setup() {…}`, `data() {…}`) tragen den Rumpf direkt in
      // `prop.body`; Properties (`setup: () => …`) in `prop.value`.
      const funktion = prop.value || (prop.type === 'ObjectMethod' ? prop : null)
      if (schluessel === 'setup' && funktion && funktion.body) {
        // Setup-Funktion: nur die obersten Anweisungen binden.
        for (const anweisung of funktion.body.body || []) {
          if (anweisung.type === 'VariableDeclaration') {
            for (const d of anweisung.declarations) sammleBindungsMuster(d.id, namen)
          } else if (
            (anweisung.type === 'FunctionDeclaration' || anweisung.type === 'ClassDeclaration') &&
            anweisung.id
          ) {
            namen.add(anweisung.id.name)
          }
        }
        continue
      }
      // `props` aus `defineProps` — Vue gibt das Objekt unter dem Namen
      // `props` an das Template (sprechende Bezeichner UND `props.x`).
      // `emits` aus `defineEmits` — das Rumpfobjekt der Komponente traegt nur
      // die Options-API auf, das Setup-Skript liefert dagegen `emit` als
      // Variable. Beides wird als Bindung gefuehrt.
      if (schluessel === 'emits') {
        namen.add('emit')
        namen.add('$event')
        continue
      }
      // Requisiten: Vue reicht sie im Template unter ihrem NAMEN herein
      // (`embedded`), unabhaengig von `props.embedded` im Skript.
      if (schluessel === 'props' && prop.value && prop.value.type === 'ObjectExpression') {
        namen.add('props')
        for (const p of prop.value.properties) {
          const k = p.key && (p.key.name || p.key.value)
          if (k) namen.add(String(k))
        }
        continue
      }
      if (schluessel) namen.add(String(schluessel))
      // Options-API: `setup: () => ({ a, b })` — die Rueckgabe ist der Bestand.
      if (schluessel === 'setup' && prop.value && prop.value.type === 'ArrowFunctionExpression') {
        const koerper = prop.value.body
        const ausdruck = koerper && koerper.type === 'ObjectExpression' ? koerper : null
        if (ausdruck) {
          for (const p of ausdruck.properties) {
            const k = p.key && (p.key.name || p.key.value)
            if (k && p.type !== 'SpreadElement') namen.add(String(k))
          }
        }
      }
    }
  }
}

/** Alle Knoten eines AST (Tiefensuche). */
function* alleKnoten(knoten) {
  if (!knoten || typeof knoten !== 'object') return
  if (Array.isArray(knoten)) {
    for (const k of knoten) yield* alleKnoten(k)
    return
  }
  yield knoten
  for (const [schluessel, wert] of Object.entries(knoten)) {
    if (schluessel === 'loc' || schluessel === 'start' || schluessel === 'end') continue
    if (wert && typeof wert === 'object') yield* alleKnoten(wert)
  }
}

/** Alle `.vue`-Dateien unter einem Ordner (ohne `node_modules`/`dist`). */
export function vueDateien(wurzel) {
  const ergebnis = []
  const lauf = (ordner) => {
    for (const eintrag of readdirSync(ordner)) {
      if (eintrag === 'node_modules' || eintrag === 'dist') continue
      const voll = join(ordner, eintrag)
      if (statSync(voll).isDirectory()) lauf(voll)
      else if (voll.endsWith('.vue')) ergebnis.push(voll)
    }
  }
  lauf(wurzel)
  return ergebnis.sort()
}

/**
 * Prueft alle `.vue` unter `wurzel`. Liefert eine Liste
 * `{ datei, fehlend, fehler }`. Mit `nurAbweichende` bleiben saubere Dateien weg.
 */
export function pruefeBaum(wurzel, sfc, babel, nurAbweichende = false) {
  const befunde = []
  for (const datei of vueDateien(wurzel)) {
    const befund = pruefeQuelle(readFileSync(datei, 'utf8'), datei, sfc, babel)
    const eintrag = {
      datei: relative(wurzel, datei),
      fehlend: befund.fehlend,
      fehler: befund.fehler,
    }
    if (nurAbweichende && !eintrag.fehlend.length && !eintrag.fehler) continue
    befunde.push(eintrag)
  }
  return befunde
}

// ══════════════════════════════════════════════════════════════════════════
// UX2d3c — Komponenten im Template muessen AUFGELOEST sein
// ══════════════════════════════════════════════════════════════════════════
/**
 * BEFUND (Review UX2d3b): `LoeschantraegeListe.vue` und `Ressourcen.vue`
 * benutzten `<DkSkelett …>` im Template, ohne die Komponente zu importieren.
 * `pruefeQuelle` oben uebersieht das: ein PascalCase-TAG ist im AST ein
 * Element, kein Ausdrucks-Bezeichner. Vue rendert es dann als unbekanntes
 * HTML-Element — ohne Fehler, ohne Warnung im Betrieb: das Skelett fehlte
 * einfach.
 *
 * Diese Pruefung sammelt jedes PascalCase-Tag des Templates und verlangt,
 * dass der Name im Skript steht (Import, `const X = defineAsyncComponent(…)`,
 * Options-`components: { … }`) oder in `KOMPONENTEN_ERLAUBT` (begruendet)
 * steht. Ein Tag, das den DATEINAMEN der SFC selbst traegt, ist rekursiv und
 * braucht keinen Import (Vue bindet den eigenen Namen automatisch).
 */
export const KOMPONENTEN_ERLAUBT = new Map([
  ['Teleport', 'Vue-eingebauter Baustein (<Teleport to="body">)'],
  ['Transition', 'Vue-eingebauter Baustein (<Transition name="…">)'],
  ['TransitionGroup', 'Vue-eingebauter Baustein (<TransitionGroup>)'],
  ['KeepAlive', 'Vue-eingebauter Baustein (<KeepAlive>)'],
  ['Suspense', 'Vue-eingebauter Baustein (<Suspense>)'],
  ['Component', 'Vue-eingebauter Baustein (<component :is="…">)'],
])

/** Ist der Name im Skript dieses SFC gebunden ODER in `components:` registriert? */
function komponenteGebunden(name, descriptor, babel) {
  const teile = []
  if (descriptor.scriptSetup) teile.push(descriptor.scriptSetup.content)
  if (descriptor.script) teile.push(descriptor.script.content)
  const code = teile.join('\n')
  if (!code) return false
  // Schneller, belastbarer Weg: der Name kommt als Deklaration/Import vor.
  const deklariert = new RegExp(
    String.raw`(?:^|\n)\s*(?:import\s+[^;\n]*\b${name}\b[^;\n]*from|(?:const|let|var)\s+${name}\b|function\s+${name}\b|class\s+${name}\b)`,
  )
  if (deklariert.test(code)) return true
  try {
    const bindungen = sammleSkriptBindings(code, babel)
    if (bindungen.has(name)) return true
  } catch {
    // Rueckfall oben reicht
  }
  // Options-API: `components: { DkSkelett }` / `components: { DkSkelett: X }`
  const block = code.match(/components\s*:\s*\{([\s\S]*?)\}/)
  if (block && new RegExp(String.raw`(?:^|[\s{,])${name}\s*(?::|,|\}|$)`, 'm').test(block[1])) return true
  return false
}

/**
 * Prueft eine SFC-Quelle auf nicht aufgeloeste Komponenten-Tags.
 *
 * Ergebnis: `{ fehlend: [{ name, zeile }], fehler: string|null }`
 */
export function pruefeKomponenten(quelle, datei, sfc, babel) {
  const { descriptor, errors } = sfc.parse(quelle, { filename: datei })
  if (errors && errors.length) {
    return { fehlend: [], fehler: 'SFC-Fehler: ' + errors.map((e) => e.message || String(e)).join('; ') }
  }
  if (!descriptor.template || !descriptor.template.ast) return { fehlend: [], fehler: null }

  const eigenname = String(datei).split(/[\\/]/).pop().replace(/\.vue$/, '')
  const tags = new Map() // name -> kleinste Zeile
  const sammle = (knoten) => {
    if (!knoten || typeof knoten !== 'object') return
    if (Array.isArray(knoten)) {
      for (const k of knoten) sammle(k)
      return
    }
    if (knoten.type === 1) {
      const tag = knoten.tag || ''
      // PascalCase ODER Namensraum-Punkt (z. B. `<Form.Input>`) — Vue loest
      // beides gegen das Skript auf. Ausnahmen: reine Kleinschreibung (HTML)
      // und eine Fuehrung mit `-` oder `:` (Attribut-Reste) gibt es nicht.
      if (/^[A-Z]/.test(tag) && !tags.has(tag)) {
        tags.set(tag, knoten.loc ? knoten.loc.start.line : 0)
      }
    }
    for (const kind of knoten.children || []) sammle(kind)
    for (const zweig of knoten.branches || []) for (const kind of zweig.children || []) sammle(kind)
  }
  sammle(descriptor.template.ast)

  const fehlend = []
  for (const [name, zeile] of tags) {
    if (KOMPONENTEN_ERLAUBT.has(name)) continue
    if (name === eigenname) continue // rekursive Komponente
    if (komponenteGebunden(name, descriptor, babel)) continue
    fehlend.push({ name, zeile })
  }
  fehlend.sort((a, b) => a.zeile - b.zeile || a.name.localeCompare(b.name))
  return { fehlend, fehler: null }
}

/** Prueft alle `.vue` unter `wurzel` auf nicht aufgeloeste Komponenten. */
export function pruefeKomponentenBaum(wurzel, sfc, babel, nurAbweichende = false) {
  const befunde = []
  for (const datei of vueDateien(wurzel)) {
    const befund = pruefeKomponenten(readFileSync(datei, 'utf8'), datei, sfc, babel)
    const eintrag = {
      datei: relative(wurzel, datei),
      fehlend: befund.fehlend,
      fehler: befund.fehler,
    }
    if (nurAbweichende && !eintrag.fehlend.length && !eintrag.fehler) continue
    befunde.push(eintrag)
  }
  return befunde
}
