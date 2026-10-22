// Sichere Textvorlagen, keine Auswertung von JavaScript und kein HTML.
// Das Ergebnis ausschließlich als Text interpolieren (niemals v-html).
const forbidden = new Set(['__proto__', 'prototype', 'constructor'])
function lookup(context, path) {
  const keys = path.trim().split('.')
  if (keys.some(key => forbidden.has(key) || !key)) return undefined
  function descend(value, index) {
    if (index === keys.length) return value
    if (Array.isArray(value)) return value.map(item => descend(item, index)).flat().filter(item => item != null)
    if (value == null || typeof value !== 'object' || !Object.hasOwn(value, keys[index])) return undefined
    return descend(value[keys[index]], index + 1)
  }
  return descend(context, 0)
}
function present(value) {
  return value != null && value !== '' && value !== false && (!Array.isArray(value) || value.some(present))
}
function text(value) {
  if (value == null) return ''
  if (Array.isArray(value)) return value.map(text).filter(Boolean).join(', ')
  if (typeof value === 'object') return text(value.name ?? value.titel ?? value.kuerzel ?? '')
  if (typeof value === 'boolean') return value ? 'Ja' : 'Nein'
  // UXP-R24: ISO-Daten nicht roh in den Programmkopf schreiben
  // („2026-12-30“ → „30.12.2026“).
  return lokalisiereDatum(String(value))
}

const ISO_DATUM = /^\d{4}-\d{2}-\d{2}$/

/** Reines ISO-Datum deutsch formatieren; alles andere bleibt unverändert. */
function lokalisiereDatum(wert) {
  if (!ISO_DATUM.test(wert)) return wert
  const d = new Date(wert + 'T12:00:00')
  return isNaN(d) ? wert : d.toLocaleDateString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  })
}
export function formatTemplate(template, context = {}) {
  if (typeof template !== 'string') return ''
  let result = ''
  for (let index = 0; index < template.length;) {
    if (template[index] !== '{') { result += template[index++]; continue }
    let end = index + 1, depth = 1
    for (; end < template.length && depth; end++) {
      if (template[end] === '{') depth++
      if (template[end] === '}') depth--
    }
    if (depth) { result += template.slice(index); break }
    const body = template.slice(index + 1, end - 1)
    const colon = body.indexOf(':')
    if (colon < 0) result += text(lookup(context, body))
    else if (present(lookup(context, body.slice(0, colon)))) result += formatTemplate(body.slice(colon + 1), context)
    index = end
  }
  return result
}

/**
 * Numerus-Helfer — EINE Quelle für die ganze Oberfläche (OP-CHOR-12/OP-UI-27).
 * Sie stehen bei den Begriffen (`components/ui/begriffe.mjs`), weil das
 * Glossar S15 dort wohnt; hier nur weitergereicht, damit der Plan-Rahmen und
 * seine Tests sie weiter aus `./format.mjs` ziehen können.
 *
 * Vorher standen überall feste Pluralformen („1 Änderungen für 1 Termine“,
 * „mit 1 weiteren Personen“) und Klammerplurale („1 Lied(er)“).
 */
export { zahlWort, wortImNumerus } from '../ui/begriffe.mjs'
