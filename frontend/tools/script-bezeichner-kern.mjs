/**
 * FIX-8 — Prüfung einer Skript-Quelle (`.js`/`.mjs`/SFC-Skriptblock).
 *
 * Ergebnis: `{ fehlend: [{ name, zeile }], fehler: string|null }`.
 */
import * as babel from '@babel/parser'
import { ERLAUBT } from './script-erlaubt.mjs'

/** Alle Namen, die ein Bindungsmuster (id/param/Muster) einfuehrt. */
export function sammleBindungsMuster(muster, namen) {
  if (!muster || typeof muster !== 'object') return namen
  switch (muster.type) {
    case 'Identifier':
      namen.add(muster.name)
      break
    case 'AssignmentPattern':
      sammleBindungsMuster(muster.left, namen)
      break
    case 'RestElement':
      sammleBindungsMuster(muster.argument, namen)
      break
    case 'ArrayPattern':
      for (const e of muster.elements) sammleBindungsMuster(e, namen)
      break
    case 'ObjectPattern':
      for (const p of muster.properties) sammleBindungsMuster(p.value || p.argument || p, namen)
      break
    case 'TSParameterProperty':
      sammleBindungsMuster(muster.parameter, namen)
      break
    default:
      break
  }
  return namen
}

/**
 * Analyse eines Skript-AST.
 * Liefert `{ bindungen: Set, verwendungen: [{name, zeile}] }`.
 */
export function analysiereSkript(programm) {
  const bindungen = new Set()
  const verwendungen = []

  const nimmKnoten = (knoten) => {
    if (!knoten || typeof knoten !== 'object') return
    if (Array.isArray(knoten)) {
      for (const k of knoten) nimmKnoten(k)
      return
    }
    switch (knoten.type) {
      // ── Bindungen ────────────────────────────────────────────────────────
      case 'ImportDeclaration':
        for (const s of knoten.specifiers || []) {
          if (s.local) bindungen.add(s.local.name)
        }
        return // `source` ist Text, kein Bezeichner
      case 'VariableDeclarator':
        sammleBindungsMuster(knoten.id, bindungen)
        nimmKnoten(knoten.init)
        return
      case 'FunctionDeclaration':
      case 'FunctionExpression':
      case 'ArrowFunctionExpression':
        if (knoten.id) bindungen.add(knoten.id.name)
        for (const p of knoten.params || []) {
          sammleBindungsMuster(p, bindungen)
          // Vorgabewerte der Parameter sind Verwendungen im aeusseren Rahmen.
          if (p && p.type === 'AssignmentPattern') nimmKnoten(p.right)
        }
        nimmKnoten(knoten.body)
        return
      case 'ClassDeclaration':
      case 'ClassExpression':
        if (knoten.id) bindungen.add(knoten.id.name)
        nimmKnoten(knoten.superClass)
        nimmKnoten(knoten.body)
        return
      case 'ClassMethod':
      case 'ClassProperty':
      case 'ClassPrivateMethod':
      case 'ClassPrivateProperty':
      case 'ObjectMethod':
        if (knoten.computed) nimmKnoten(knoten.key)
        // Feld-Initialisierer (`static s = zzz`) sind Verwendungen.
        nimmKnoten(knoten.value)
        for (const p of knoten.params || []) {
          sammleBindungsMuster(p, bindungen)
          if (p && p.type === 'AssignmentPattern') nimmKnoten(p.right)
        }
        nimmKnoten(knoten.body)
        return
      case 'CatchClause':
        sammleBindungsMuster(knoten.param, bindungen)
        nimmKnoten(knoten.body)
        return
      case 'LabeledStatement':
        nimmKnoten(knoten.body)
        return
      case 'BreakStatement':
      case 'ContinueStatement':
        return
      // ── Verwendungen ─────────────────────────────────────────────────────
      case 'MemberExpression':
      case 'OptionalMemberExpression':
        nimmKnoten(knoten.object)
        if (knoten.computed) nimmKnoten(knoten.property)
        return // `a.b`: `b` ist Eigenschaft, kein freier Name
      case 'ObjectProperty':
      case 'Property':
        if (knoten.computed) nimmKnoten(knoten.key)
        nimmKnoten(knoten.value)
        return
      case 'ExportSpecifier':
        // `export { a }` verweist auf `a`; `export { a as b }` auf `a`.
        nimmKnoten(knoten.local)
        // Der EXPORTIERTE Name (`a as b`) ist ein neuer Name, keine Verwendung.
        return
      case 'ExportNamedDeclaration':
        // `export { a } from './x'` — nur ein Durchreichen, kein Verweis auf
        // eine LOKALE Bindung. Mit `declaration`/`source === null` greift die
        // normale Abarbeitung der Kinder (`declaration` wird gebunden).
        if (knoten.source) return
        break
      case 'Identifier':
        verwendungen.push({ name: knoten.name, zeile: knoten.loc ? knoten.loc.start.line : 0 })
        return
      case 'MetaProperty':
        return // `import.meta`, `new.target`
      case 'PrivateIdentifier':
        return
      case 'TSQualifiedName':
        nimmKnoten(knoten.left)
        return
      default:
        break
    }
    for (const [schluessel, wert] of Object.entries(knoten)) {
      if (schluessel === 'loc' || schluessel === 'start' || schluessel === 'end' || schluessel === 'type') continue
      if (wert && typeof wert === 'object') nimmKnoten(wert)
    }
  }

  nimmKnoten(programm)
  return { bindungen, verwendungen }
}

/**
 * Alle in einer Skript-Quelle deklarierten Namen (oder `null` bei Syntaxfehler).
 */
export function bindungenVon(code, sprache = 'js') {
  try {
    const programm = babel.parse(code, {
      sourceType: 'module',
      plugins: sprache === 'ts' ? ['typescript'] : ['jsx'],
    })
    return analysiereSkript(programm.program).bindungen
  } catch {
    return null
  }
}

/**
 * Prueft eine Skript-Quelle. `sprache` = 'js' | 'ts'.
 * Ergebnis: `{ fehlend: [{ name, zeile }], fehler: string|null }`.
 */
export function pruefeSkriptCode(code, datei, sprache = 'js', erlaubt = ERLAUBT, zusatzBindungen = null) {
  let programm
  try {
    programm = babel.parse(code, {
      sourceType: 'module',
      plugins: sprache === 'ts' ? ['typescript'] : ['jsx'],
      allowReturnOutsideFunction: false,
    })
  } catch (e) {
    return { fehlend: [], fehler: `${datei}: Syntaxfehler — ${e.message}` }
  }
  const { bindungen, verwendungen } = analysiereSkript(programm.program)
  const fehlend = []
  const gesehen = new Set()
  for (const { name, zeile } of verwendungen) {
    if (bindungen.has(name)) continue
    if (zusatzBindungen && zusatzBindungen.has(name)) continue
    if (erlaubt.has(name)) continue
    if (gesehen.has(name)) continue
    gesehen.add(name)
    fehlend.push({ name, zeile })
  }
  fehlend.sort((a, b) => a.zeile - b.zeile || a.name.localeCompare(b.name))
  return { fehlend, fehler: null }
}
