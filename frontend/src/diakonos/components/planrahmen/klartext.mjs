/** Reine Darstellung: Serverpfade bleiben unverändert, nur Beschriftungen ändern sich. */
const WORTE = { frohe_stunde: 'Frohe Stunde', lieder: 'Lied', dirigent: 'Dirigent', klavier: 'Klavier', solo: 'Solo', einsingen: 'Einsingen', einueben: 'Einüben', sonne: 'Sonne', regen: 'Regen', abschluss: 'Abschluss' }
export function lesbarerName(id = '') {
  if (WORTE[id]) return WORTE[id]
  const text = String(id).replaceAll('_', ' ')
  return text ? text[0].toLocaleUpperCase('de-DE') + text.slice(1) : 'Eintrag'
}
function zweig(liste, id) {
  return (liste || []).map(x => typeof x === 'string' ? { id: x } : x).find(x => x.id === id)
}

export function feldInfo(pfad, definition = {}, termin = {}) {
  let rest = String(pfad || '')
  const namen = []
  const standard = definition?.terminreihen?.find(r => !r.id || r.id === 'standard')
  let felder = definition?.felder || standard?.felder || []
  if (!rest.includes(':') && !definition?.felder && standard) namen.push(standard.name || 'Termine')
  if (rest.includes(':')) {
    const [reihe, ...teile] = rest.split(':')
    const r = definition?.terminreihen?.find(r => r.id === reihe)
    if (r) { namen.push(r.name || lesbarerName(r.id)); felder = r.felder || [] }
    rest = teile.join(':')
  }
  let feld = null
  let basis = ''
  for (const segment of rest.split('.')) {
    const m = segment.match(/^([^\[@#/]+)(?:\[(\d+)\])?(?:@([^#\/]+))?(?:#([^\/]+))?(?:\/(.+))?$/)
    if (!m) continue
    const [, id, index, variante, teil, elementId] = m
    feld = felder.find(f => f.id === id)
    // Unbekannte gelöschte Strukturen nicht als UUID/Feldpfad in die Oberfläche tragen.
    if (!feld) { namen.push('Eintrag'); break }
    basis = basis ? basis + '.' + id : id
    let name = feld.name || lesbarerName(id)
    if (index !== undefined) name += ' ' + (Number(index) + 1)
    const v = zweig(feld.varianten, variante)
    if (variante) name += ` (${v?.name || lesbarerName(variante)})`
    namen.push(name)
    const t = zweig(feld.teile, teil)
    if (teil) namen.push(t?.name || lesbarerName(teil))
    felder = [...(feld.inhalt || []), ...(v?.inhalt || []), ...(t?.inhalt || [])]
    if (elementId) {
      const elemente = termin?.ablauf?.[basis] || termin?.ablauf?.[id] || []
      const position = elemente.findIndex(e => e.id === elementId)
      const e = elemente[position]
      const typ = feld.elemente?.find(x => x.typ === e?.typ)
      const nummer = elemente.slice(0, position + 1).filter(x => x.typ === e?.typ).length
      namen.push(typ ? `${typ.name || lesbarerName(typ.typ)} ${nummer}` : 'Entfernter Programmpunkt')
      felder = typ?.inhalt || []
    }
  }
  return { name: namen.join(' · ') || 'Eintrag', art: feld?.art || '', feld }
}
export function feldBeschriftung(pfad, definition, termin) { return feldInfo(pfad, definition, termin).name }

export function anzeigeWert(wert, art, anzeige = {}) {
  if (wert === null || wert === undefined || wert === '') return '(leer)'
  if (Array.isArray(wert)) return wert.length ? wert.map(w => anzeigeWert(w, art, anzeige)).join(', ') : '(leer)'
  if (typeof wert === 'boolean') return wert ? 'Ja' : 'Nein'
  if (typeof wert === 'object') return wert.name || wert.titel || 'Eintrag'
  const a = anzeige[wert]
  if (a) return typeof a === 'string' ? a : (a.name || a.titel || a.anzeige || 'Eintrag')
  return !art || ['person', 'personen', 'team', 'eintrag'].includes(art) ? 'Nicht mehr verfügbar' : String(wert)
}
export function diffGruppen(diff, termine, definitionen, anzeige) {
  const defs = definitionen instanceof Map ? definitionen : new Map(Object.entries(definitionen || {}))
  const ts = new Map(termine.map(t => [t.id, t]))
  const gruppen = new Map()
  for (const d of diff) {
    const t = ts.get(d.termin) || { id: d.termin, datum: d.datum }
    if (!gruppen.has(t.id)) gruppen.set(t.id, { id: t.id, datum: t.datum || '', titel: t.titel || '', zeilen: [] })
    const info = feldInfo(d.feld_pfad, defs.get(t.plantyp_version), t)
    gruppen.get(t.id).zeilen.push({ feld: info.name, vorher: anzeigeWert(d.vorher, info.art, anzeige), nachher: anzeigeWert(d.nachher, info.art, anzeige) })
  }
  return [...gruppen.values()].sort((a, b) => a.datum.localeCompare(b.datum))
}
/** Vorschläge können neue optionale Plätze enthalten, die noch nicht abfragbar sind. */
export function kandidatenZiel(termin, pfad, termine, definitionen, slotsProTermin) {
  const vorhandene = slotsProTermin.get(termin) || []
  if (vorhandene.some(s => s.feld_pfad === pfad)) return { termin, pfad }
  const t = termine.find(t => t.id === termin)
  const info = feldInfo(pfad, definitionen.get(t?.plantyp_version), t)
  for (const [id, slots] of slotsProTermin) {
    const s = slots.find(s => s.art === info.art && (
      info.art === 'eintrag' ? s.sammlung === info.feld?.sammlung :
      JSON.stringify(s.rolle || null) === JSON.stringify(info.feld?.rolle || null)))
    if (s) return { termin: id, pfad: s.feld_pfad }
  }
  return null
}
/** Namen nur bei fehlenden Zuordnungen nachladen; eine Kandidatenliste löst viele IDs. */
export async function diffAnzeigeLaden(diff, termine, definitionen, initial, kandidatenLaden) {
  const anzeige = { ...initial }
  const ts = new Map(termine.map(t => [t.id, t]))
  for (const d of diff) {
    const t = ts.get(d.termin)
    if (!t) continue
    const info = feldInfo(d.feld_pfad, definitionen.get(t.plantyp_version), t)
    if (!['person', 'personen', 'team', 'eintrag'].includes(info.art)) continue
    const werte = [d.vorher, d.nachher].flat().filter(w => typeof w === 'string' && w)
    if (!werte.some(w => !anzeige[w])) continue
    const result = await kandidatenLaden(t.id, d.feld_pfad)
    for (const k of result?.kandidaten || []) if (k?.kennung) anzeige[k.kennung] = k
  }
  return anzeige
}
export function kandidatenHinweise(k, deklarationen = [], anzeige = {}) {
  const teile = []
  if (k?.abwesend) teile.push('im Urlaub / abwesend')
  for (const [id, wert] of Object.entries(k?.merkmale || {})) {
    const d = deklarationen.find(d => d.id === id)
    if (!d) continue
    teile.push(`${d.name || lesbarerName(id)}: ${anzeigeWert(wert, d.art, anzeige)}`)
  }
  if (k?.mitglieder) teile.push(k.mitglieder + ' Mitglieder')
  if (k?.kuerzel) teile.push(k.kuerzel)
  return teile.join(' · ')
}
/** Auch in Sätzen eingebettete Serverpfade gehören nicht in die Alltagssicht.
 *  UXP-R14: Der Pfad kommt NUR aus `feld_pfad`/`pfad` bzw. aus dem
 *  ausdrücklichen `Feld '…'`-Muster. Früher wurde zusätzlich hinter „für“ /
 *  „fuer“ ein „Pfad“ geraten und dann per replaceAll im ganzen Text ersetzt:
 *  aus „Dank für Golgatha“ wurde „Dank für Eintrag“, aus „Dafür fehlt dir die
 *  Berechtigung.“ ein „Dafür Eintrag dir die Berechtigung.“. */
export function meldungsKurz(m, definition = {}, termin = {}, anzeige = {}) {
  if (!m) return ''
  const text = typeof m === 'string' ? m : (m.meldung || '')
  const pfad = m.feld_pfad || m.bewertung?.feld_pfad || m.pfad
    || text.match(/Feld ['"]([^'"]+)['"]/)?.[1]
  const feld = feldBeschriftung(pfad, definition, termin)
  // UXP-R14: EIN ausdrueckliches Servermuster nennt den Pfad im Satz
  // ("Vorbelegen-Quelle 'eintrag.dirigent' für lieder[0].dirigent ist leer.",
  // engine/fuellen.py:150). Nur dort wird der Pfad aus dem Text gelesen —
  // nie aus freiem Deutsch nach „für“.
  const pfadAusText = text.startsWith('Vorbelegen-Quelle ')
    ? text.match(/ f(?:ü|ue)r ([a-zA-Z_][\w\[.\]:@#/-]*?) ist /)?.[1]
    : null
  const feldAusText = pfadAusText ? feldBeschriftung(pfadAusText, definition, termin) : feld
  if (m.code === 'kandidaten.leer') return `Für ${feld} sind noch keine passenden Vorschläge vorhanden. Bitte Stammdaten prüfen.`
  if (text.startsWith('Vorbelegen-Quelle ')) return `Für ${feldAusText} fehlt eine vorbereitete Angabe. Bitte Stammdaten prüfen oder einen Wert von Hand wählen.`
  if (text.startsWith('Kein Kandidat erfüllt die Muss-Regeln') || text.startsWith('Kein Kandidat erfuellt die Muss-Regeln')) return `Für ${feld} gibt es keinen passenden Vorschlag: Die Liste ist leer oder niemand erfüllt alle Pflichtregeln.`
  let result = text
  if (pfad && pfad !== '/') result = result.replaceAll(pfad, feld)
  if (pfadAusText) result = result.replaceAll(pfadAusText, feldAusText)
  // Einzelne Referenzen sowie verschachtelte/indexierte Pfade, auch ohne Kontext.
  result = result.replace(/\b[a-zA-Z_][\w-]*(?:\[\d+\]|[.:@#/][\w-]+)+(?:\[\d+\]|[.:@#/][\w-]+)*/g,
    token => {
      const info = feldInfo(token, definition, termin)
      return info.feld || /\[|@|#|\/[0-9a-f-]{36}/i.test(token) ? info.name : token
    })
  const felder = definition?.felder || definition?.terminreihen?.find(r => !r.id || r.id === 'standard')?.felder || []
  result = result.replace(/\b[a-zA-Z_][\w-]*\b/g, token => felder.some(f => f.id === token) ? feldBeschriftung(token, definition, termin) : token)
  result = result.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi,
    token => anzeigeWert(token, 'person', anzeige))
  for (const [id, wert] of Object.entries(anzeige || {})) {
    if (id && result.includes(id)) result = result.replaceAll(id, anzeigeWert(id, 'person', { [id]: wert }))
  }
  // UXP-R14: ASCII-Ersatz aus der Engine als echtes Deutsch ausgeben.
  return result.replace(/\bUebungen\b/g, 'Übungen').replace(/\bfuer\b/g, 'für')
}
const REGELN = {
  abwesenheit_beachten: 'Eingeteilte Personen sind abwesend', mindestabstand: 'Einträge wurden kürzlich schon eingeplant',
  max_pro_zeitraum: 'Personen sind zu oft eingeteilt', min_pro_zeitraum: 'Personen sind noch zu selten eingeteilt',
  nicht_gleichzeitig: 'Aufgaben überschneiden sich', gleich_verteilen: 'Aufgaben sind noch ungleich verteilt',
  passend_zum_anlass: 'Einträge passen nicht zum Anlass', verfuegbarkeit: 'Personen sind nicht verfügbar',
  zusammen: 'Gemeinsame Einteilung prüfen', nicht_zusammen: 'Getrennte Einteilung prüfen',
}
export function regelTitel(regel, anzahl, definition = {}) {
  if (regel === 'vorher_geuebt') {
    const n = definition?.regeln?.find(r => r.baustein === regel)?.mindestens
    return `${anzahl} ${anzahl === 1 ? 'Lied ist' : 'Lieder sind'} vor ihrem Termin noch nicht ${n ? n + '×' : 'ausreichend'} geübt`
  }
  return `${anzahl} · ${REGELN[regel] || 'Bitte Angaben prüfen'}`
}
