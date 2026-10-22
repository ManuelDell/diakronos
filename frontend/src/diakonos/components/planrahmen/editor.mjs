/**
 * Plantyp-Editor: reine Helfer ohne Vue und ohne Seiteneffekte.
 *
 * Alles hier ist testbar mit `node --test`: Wiederholungsregeln in
 * verständliche Sätze übersetzen (und zurück), Feld-Bäume verschieben/
 * einrücken, Knoten-Baukasten (Rollenfilter & Bedingungen), das
 * regelgetriebene Parameterformular aus der Baustein-Registry sowie den
 * verlustfreien JSON-Synchronisation der zweiten Reiterseite.
 */

// ── Statische Kataloge ─────────────────────────────────────────────────────

export const WOCHENTAGE = [
  { kuerzel: 'mo', name: 'Montag' },
  { kuerzel: 'di', name: 'Dienstag' },
  { kuerzel: 'mi', name: 'Mittwoch' },
  { kuerzel: 'do', name: 'Donnerstag' },
  { kuerzel: 'fr', name: 'Freitag' },
  { kuerzel: 'sa', name: 'Samstag' },
  { kuerzel: 'so', name: 'Sonntag' },
]

/** Feiertags-Katalog aus REFERENZ.md — Schlüssel ist zugleich Anlassname.
 *  Die Namen tragen Umlaute („Gründonnerstag“, „Buß- und Bettag“); zur
 *  Laufzeit kann die Oberfläche sie über `feiertage_holen` aus dem
 *  Server-Katalog überschreiben (siehe `setzeFeiertagskatalog`).
 *
 *  P3-1d (W3): Das ist eine MUTABLE Liste, kein normales `const`-Array — der
 *  Editiere rendert sie direkt (`v-for="f in FEIERTAGE"`). `setzeFeiertagskatalog`
 *  ersetzt sie in place (`splice`), damit der Server-Katalog ohne Neuladen
 *  sichtbar wird. Ein Neu-Zuweisen der Bindung ginge an den Importen vorbei. */
export const FEIERTAGE = [
  { schluessel: 'aschermittwoch', name: 'Aschermittwoch', art: 'oster' },
  { schluessel: 'palmsonntag', name: 'Palmsonntag', art: 'oster' },
  { schluessel: 'gruendonnerstag', name: 'Gründonnerstag', art: 'oster' },
  { schluessel: 'karfreitag', name: 'Karfreitag', art: 'oster' },
  { schluessel: 'ostersonntag', name: 'Ostersonntag', art: 'oster' },
  { schluessel: 'ostermontag', name: 'Ostermontag', art: 'oster' },
  { schluessel: 'himmelfahrt', name: 'Christi Himmelfahrt', art: 'oster' },
  { schluessel: 'pfingstsonntag', name: 'Pfingstsonntag', art: 'oster' },
  { schluessel: 'pfingstmontag', name: 'Pfingstmontag', art: 'oster' },
  { schluessel: 'fronleichnam', name: 'Fronleichnam', art: 'oster' },
  { schluessel: 'neujahr', name: 'Neujahr', art: 'fest' },
  { schluessel: 'silvester', name: 'Silvester', art: 'fest' },
  { schluessel: '1_advent', name: '1. Advent', art: 'advent' },
  { schluessel: '2_advent', name: '2. Advent', art: 'advent' },
  { schluessel: '3_advent', name: '3. Advent', art: 'advent' },
  { schluessel: '4_advent', name: '4. Advent', art: 'advent' },
  { schluessel: 'heiligabend', name: 'Heiligabend', art: 'fest' },
  { schluessel: '1_weihnachtstag', name: '1. Weihnachtstag', art: 'fest' },
  { schluessel: '2_weihnachtstag', name: '2. Weihnachtstag', art: 'fest' },
  { schluessel: 'buss_und_bettag', name: 'Buß- und Bettag', art: 'advent' },
  { schluessel: 'erntedank', name: 'Erntedank', art: 'erntedank' },
]

export const FELD_ARTEN = [
  { wert: 'person', name: 'Person (genau eine)' },
  { wert: 'personen', name: 'Personen (eine oder mehrere)' },
  { wert: 'eintrag', name: 'Eintrag aus einer Liste' },
  { wert: 'text', name: 'Text' },
  { wert: 'zahl', name: 'Zahl' },
  { wert: 'datum', name: 'Datum' },
  { wert: 'auswahl', name: 'Auswahl aus einer Liste' },
  { wert: 'gruppe', name: 'Gruppe mit Unterfeldern' },
  { wert: 'team', name: 'Team (Diakonos-Gruppe)' },
  { wert: 'ablauf', name: 'Ablauf (Elementtypen)' },
]

export const FUELLSTRATEGIEN = [
  { wert: '', name: 'Automatisch (Vorgabe)' },
  { wert: 'manuell', name: 'manuell — nur von Hand' },
  { wert: 'reihum', name: 'reihum — Personen der Reihe nach' },
  { wert: 'der_reihe_nach', name: 'der Reihe nach — Listenreihenfolge' },
  { wert: 'vorbelegen', name: 'vorbelegen — aus anderem Feld / einer Angabe' },
  { wert: 'optimieren', name: 'optimieren — beste Wahl nach Regeln' },
]

export const PARAMETER_ARTEN = [
  { wert: 'text', name: 'Text' },
  { wert: 'zahl', name: 'Zahl' },
  { wert: 'datum', name: 'Datum' },
  { wert: 'zeitraum', name: 'Zeitraum (von bis)' },
  { wert: 'auswahl', name: 'Auswahl aus einer Liste' },
]

export const MERKMALS_ARTEN = [
  { wert: 'tag', name: 'Ja/Nein' },
  { wert: 'auswahl', name: 'Auswahl aus einer Liste' },
  { wert: 'text', name: 'Text' },
  { wert: 'zahl', name: 'Zahl' },
  { wert: 'datum', name: 'Datum' },
  { wert: 'person', name: 'Person' },
]

export const ANSICHTS_ARTEN = [
  { wert: 'tabelle', name: 'Tabelle (Termin × Felder)' },
  { wert: 'raster', name: 'Raster (Tag × Block)' },
  { wert: 'ablauf', name: 'Ablauf (ein Termin als Liste)' },
  { wert: 'meine_dienste', name: 'Personensicht (Meine Dienste)' },
  { wert: 'druck', name: 'Druckausgabe' },
  { wert: 'ical', name: 'Kalender-Export (iCal)' },
  { wert: 'kalender', name: 'Monats-Aushang' },
  { wert: 'programm', name: 'Programmheft / Liedzettel' },
]

export const DRUCK_FORMATE = [
  { wert: '', name: 'keine Angabe' },
  { wert: 'A4-quer', name: 'A4 quer' },
  { wert: 'A4-hoch', name: 'A4 hoch' },
]

export const STUFEN = [
  { wert: 'muss', name: 'muss — wird nie verletzt' },
  { wert: 'sollte', name: 'sollte — möglichst erfüllt' },
  { wert: 'hinweis', name: 'Hinweis — wird nur angezeigt' },
]

// ── Prüfmeldungen am rekursiven Formularfeld ──────────────────────────────

export function feldPruefPfad(basis, index) {
  const prefix = String(basis || '').replace(/^\/+|\/+$/g, '')
  return prefix ? `${prefix}/${index}` : String(index)
}

export function meldungenAmFeld(meldungen, feldPfad) {
  const pfad = '/' + String(feldPfad).replace(/^\/+|\/+$/g, '')
  return (meldungen || []).filter(m => m?.pfad === pfad || m?.pfad?.startsWith(pfad + '/'))
}

// ── Leere Definition und Felder ────────────────────────────────────────────

export function leereDefinition() {
  return { schema: 'diakronos/plantyp@1', id: '', name: '', bereich: '', beschreibung: '' }
}

export function leeresFeld(art) {
  const feld = { id: '', art: art || 'text' }
  if (art === 'gruppe') feld.inhalt = []
  if (art === 'ablauf') feld.elemente = []
  return feld
}

// ── Wiederholung (RRULE) verständlich ──────────────────────────────────────

const BYDAY = { mo: 'MO', di: 'TU', mi: 'WE', do: 'TH', fr: 'FR', sa: 'SA', so: 'SU' }
const BYDAY_ZURUECK = Object.fromEntries(Object.entries(BYDAY).map(([k, v]) => [v, k]))

/**
 * Verständliche Angaben → iCalendar-RRULE.
 * @param {{frequenz?: string, tage?: string[], intervall?: number}} angaben
 * z. B. {frequenz:'weekly', tage:['so']} → 'FREQ=WEEKLY;BYDAY=SU'
 */
export function rruleAus(angaben = {}) {
  const frequenz = (angaben.frequenz || 'weekly').toUpperCase()
  const intervall = Number(angaben.intervall) > 1 ? Math.floor(Number(angaben.intervall)) : null
  const teile = ['FREQ=' + frequenz]
  if (intervall) teile.push('INTERVAL=' + intervall)
  const tage = (angaben.tage || []).filter((t) => BYDAY[t])
  if (frequenz === 'WEEKLY' && tage.length) teile.push('BYDAY=' + tage.map((t) => BYDAY[t]).join(','))
  return teile.join(';')
}

/** iCalendar-RRULE → verständliche Angaben (leer bei unlesbarer Regel). */
export function rruleLesen(regel) {
  if (typeof regel !== 'string' || !regel.trim()) return null
  const teile = regel.split(';').map((t) => t.trim().toUpperCase()).filter(Boolean)
  const werte = {}
  for (const t of teile) {
    const i = t.indexOf('=')
    if (i > 0) werte[t.slice(0, i)] = t.slice(i + 1)
  }
  if (!werte.FREQ) return null
  const tage = (werte.BYDAY || '').split(',').map((d) => BYDAY_ZURUECK[d.trim()]).filter(Boolean)
  return {
    frequenz: werte.FREQ.toLowerCase(),
    intervall: werte.INTERVAL ? parseInt(werte.INTERVAL, 10) : 1,
    tage,
  }
}

/** 'FREQ=WEEKLY;BYDAY=SU' → 'jeden Sonntag'. Rohformat bei keiner Deutung. */
export function wiederholungText(regel) {
  const g = rruleLesen(regel)
  if (!g) return regel ? String(regel) : ''
  const intervall = g.intervall > 1 ? `alle ${g.intervall} ` : ''
  if (g.frequenz === 'daily') return g.intervall > 1 ? `alle ${g.intervall} Tage` : 'jeden Tag'
  if (g.frequenz === 'monthly') return g.intervall > 1 ? `alle ${g.intervall} Monate` : 'jeden Monat'
  if (g.frequenz === 'yearly') return g.intervall > 1 ? `alle ${g.intervall} Jahre` : 'jedes Jahr'
  const namen = g.tage.map((t) => (WOCHENTAGE.find((w) => w.kuerzel === t) || {}).name).filter(Boolean)
  const tagText = namen.length === 0 ? 'Wochentag'
    : namen.length === 1 ? namen[0]
    : namen.slice(0, -1).join(', ') + ' und ' + namen[namen.length - 1]
  return g.intervall > 1 ? `alle ${g.intervall} Wochen am ${tagText}` : `jeden ${tagText}`
}

// ── Abgeleitete Termine (Versatz) ──────────────────────────────────────────

const EINHEITEN = { T: 'Tag(e)', W: 'Woche(n)', h: 'Stunde(n)', min: 'Minute(n)' }

/** '-2T' → {signum:'-', zahl:2, einheit:'T'}; null bei unlesbarem Versatz. */
export function versatzLesen(versatz) {
  const m = String(versatz || '').match(/^([+-])(\d+)(T|W|h|min)$/)
  if (!m) return null
  return { signum: m[1], zahl: parseInt(m[2], 10), einheit: m[3] }
}

/** {signum, zahl, einheit} → '-2T'. */
export function versatzAus(angaben = {}) {
  const zahl = Math.max(0, Math.floor(Number(angaben.zahl) || 0))
  const einheit = EINHEITEN[angaben.einheit] ? angaben.einheit : 'T'
  return `${angaben.signum === '+' ? '+' : '-'}${zahl}${einheit}`
}

/** '-2T' → '2 Tage vor dem Ursprungstermin'. */
export function versatzText(versatz) {
  const g = versatzLesen(versatz)
  if (!g) return versatz ? String(versatz) : ''
  return `${g.zahl} ${EINHEITEN[g.einheit]} ${g.signum === '-' ? 'vor' : 'nach'} dem Ursprungstermin`
}

// ── Anzahl ─────────────────────────────────────────────────────────────────

/** anzahl (Zahl oder 'min..max'/'1..*') → {min, max|null, offen}. */
export function anzahlLesen(anzahl) {
  if (anzahl === undefined || anzahl === null || anzahl === '') return { min: 1, max: 1, offen: false }
  if (typeof anzahl === 'number') return { min: anzahl, max: anzahl, offen: false }
  const m = String(anzahl).match(/^(\d+)\.\.(\d+|\*)$/)
  if (!m) return { min: 1, max: 1, offen: false }
  return { min: parseInt(m[1], 10), max: m[2] === '*' ? null : parseInt(m[2], 10), offen: m[2] === '*' }
}

/** {min, max, offen} → Zahl oder 'min..max'/'min..*'. */
export function anzahlAus(angaben = {}) {
  const min = Math.max(0, Math.floor(Number(angaben.min) || 0))
  if (angaben.offen) return `${min}..*`
  const max = Math.max(min, Math.floor(Number(angaben.max) || min))
  return min === max ? min : `${min}..${max}`
}

// ── Feld-Baum ──────────────────────────────────────────────────────────────

/**
 * Alle Felder eines Baums als flache Liste mit Pfad (inkl. Gruppen-,
 * Varianten-, Teil- und Ablauf-Unterfeldern).
 */
export function feldPfadListe(felder, basis = '') {
  const result = []
  for (const f of felder || []) {
    if (!f || typeof f !== 'object') continue
    const pfad = basis + (f.id || '?')
    result.push({ pfad, name: f.name || f.id || '', art: f.art || '' })
    if (Array.isArray(f.inhalt)) result.push(...feldPfadListe(f.inhalt, pfad + '.'))
    for (const zweig of [...(f.varianten || []), ...(f.teile || [])]) {
      const obj = typeof zweig === 'string' ? { id: zweig } : zweig
      if (Array.isArray(obj.inhalt)) result.push(...feldPfadListe(obj.inhalt, pfad + '.'))
    }
    for (const elem of f.elemente || []) {
      const e = typeof elem === 'string' ? { typ: elem } : elem
      if (Array.isArray(e.inhalt)) result.push(...feldPfadListe(e.inhalt, `${pfad}/${e.typ || '?'}.`))
    }
  }
  return result
}

/** Nur die Kennungen der obersten Ebene (für Anlass-Wirkung 'ohne'). */
export function topFeldIds(felder) {
  return (felder || []).map((f) => f?.id).filter(Boolean)
}

/**
 * Top-Level-Feldkennungen einer vollständigen Definition - Kurzform
 * (`felder`) oder mehrere Terminreihen. Reihenfelder tragen das Praefix
 * `<reihe>:` (Standardreihe ohne Praefix), damit Anlass-Wirkungen sie
 * eindeutig adressieren; Parameterfelder wie `{parameter.x}` bleiben aus.
 */
export function feldKennungen(definition) {
  const def = definition || {}
  const kennungen = []
  for (const f of def.felder || []) if (f?.id) kennungen.push(f.id)
  for (const reihe of def.terminreihen || []) {
    for (const f of reihe?.felder || []) {
      if (!f?.id) continue
      kennungen.push(!reihe.id || reihe.id === 'standard' ? f.id : `${reihe.id}:${f.id}`)
    }
  }
  return kennungen
}

/** Feld zwei Positionen nach oben/unten tauschen. true bei Erfolg. */
export function feldVerschieben(liste, index, delta) {
  const ziel = index + delta
  if (!Array.isArray(liste) || index < 0 || index >= liste.length || ziel < 0 || ziel >= liste.length) return false
  const [feld] = liste.splice(index, 1)
  liste.splice(ziel, 0, feld)
  return true
}

/** Feld in das vorherige Geschwisterteil einrücken (nur gruppe/eintrag). */
export function feldEinruecken(liste, index) {
  if (!Array.isArray(liste) || index <= 0 || index >= liste.length) return false
  const vorher = liste[index - 1]
  if (!vorher || !['gruppe', 'eintrag'].includes(vorher.art)) return false
  if (!Array.isArray(vorher.inhalt)) vorher.inhalt = []
  const [feld] = liste.splice(index, 1)
  vorher.inhalt.push(feld)
  return true
}

/** Feld an Position index in eine Liste einfügen. */
export function feldEinfuegen(liste, index, feld) {
  if (!Array.isArray(liste)) return false
  liste.splice(Math.max(0, Math.min(index, liste.length)), 0, feld)
  return true
}

/** Feld an Position index entfernen und zurückgeben. */
export function feldLoeschen(liste, index) {
  if (!Array.isArray(liste) || index < 0 || index >= liste.length) return null
  return liste.splice(index, 1)[0] || null
}

// ── Knoten-Baukasten (Rollenfilter & Bedingungen) ──────────────────────────

export const ROLLEN_KNOTEN = [
  { wert: 'merkmal', name: 'Fähigkeit / Eigenschaft', typ: 'text' },
  { wert: 'gruppe', name: 'Gruppe', typ: 'text' },
  { wert: 'anmeldung', name: 'Anmeldung', typ: 'text' },
  { wert: 'person', name: 'Bestimmte Person', typ: 'text' },
]

export const BEDINGUNGS_KNOTEN = [
  { wert: 'anlass', name: 'Anlass', typ: 'text' },
  { wert: 'wochentag', name: 'Wochentag', typ: 'wochentage' },
  { wert: 'variante', name: 'Variante', typ: 'text' },
  { wert: 'parameter', name: 'Parameterwert', typ: 'parameter' },
  { wert: 'feld_gesetzt', name: 'Feld ist gefüllt', typ: 'text' },
  { wert: 'datum_ab', name: 'Termin ab Datum', typ: 'datum' },
  { wert: 'datum_bis', name: 'Termin bis Datum', typ: 'datum' },
  { wert: 'termin_nr', name: 'Jeder n-te Termin', typ: 'termin_nr' },
  { wert: 'termin_im_monat', name: 'n-ter Termin im Monat', typ: 'zahl' },
]

/** Den genau einen gesetzten Schlüssel eines Knotens. */
export function knotenSchluessel(knoten) {
  if (!knoten || typeof knoten !== 'object') return ''
  const keys = Object.keys(knoten)
  return keys.length === 1 ? keys[0] : ''
}

/** Neuen Blattknoten für einen Baukasten bauen. */
export function leerenKnoten(modus, schluessel) {
  const start = modus === 'bedingung' ? 'anlass' : 'merkmal'
  const key = schluessel || start
  if (key === 'wochentag') return { wochentag: ['so'] }
  if (key === 'parameter') return { parameter: { id: '', gleich: '' } }
  if (key === 'termin_nr') return { termin_nr: { jede: 2 } }
  if (key === 'termin_im_monat') return { termin_im_monat: 1 }
  return { [key]: '' }
}

/** Einen Knoten auf einen anderen Schlüssel umstellen (Wert wird zurückgesetzt). */
export function knotenWechseln(knoten, modus, schluessel) {
  return leerenKnoten(modus, schluessel)
}

/** Knoten in einem verständlichen deutschen Satz. */
export function knotenText(knoten) {
  if (!knoten || typeof knoten !== 'object') return ''
  const key = knotenSchluessel(knoten)
  const wert = knoten[key]
  switch (key) {
    case 'alle':
      return '(' + (wert || []).map(knotenText).filter(Boolean).join(' und ') + ')'
    case 'eine':
      return '(' + (wert || []).map(knotenText).filter(Boolean).join(' oder ') + ')'
    case 'nicht':
      return 'nicht ' + knotenText(wert)
    case 'merkmal': return `Eigenschaft „${wert}“`
    case 'gruppe': return `Gruppe „${wert}“`
    case 'anmeldung': return `Anmeldung „${wert}“`
    case 'person': return `Person „${wert}“`
    case 'anlass': return `Anlass „${wert}“`
    case 'variante': return `Variante „${wert}“`
    case 'wochentag': {
      const namen = (wert || []).map((k) => (WOCHENTAGE.find((w) => w.kuerzel === k) || {}).name).filter(Boolean)
      return `Wochentag ${namen.join('/') || '–'}`
    }
    case 'parameter': return `Parameter „${wert?.id || '…'}“ = „${wert?.gleich ?? ''}“`
    case 'feld_gesetzt': return `Feld „${wert}“ ist gefüllt`
    case 'datum_ab': return `ab ${wert}`
    case 'datum_bis': return `bis ${wert}`
    case 'termin_nr': return `jeder ${wert?.jede ?? '?'}. Termin`
    case 'termin_im_monat': return `${wert}. Termin im Monat`
    default: return key ? `${key}: ${JSON.stringify(wert)}` : ''
  }
}

// ── Regel-Bausteine (schema-getriebenes Formular) ─────────────────────────

/**
 * Parameterformular-Deskriptoren aus dem parameter_schema eines Bausteins
 * (x-regel-bausteine der Registry). Reihenfolge: Pflicht zuerst.
 */
export function regelParameterForm(baustein) {
  const schema = baustein?.parameter_schema || {}
  const props = schema.properties || {}
  const pflicht = Array.isArray(schema.required) ? schema.required : []
  const felder = []
  for (const [name, def] of Object.entries(props)) {
    const istPflicht = pflicht.includes(name)
    felder.push({ name, pflicht: istPflicht, typ: paramTyp(def), werte: paramEnum(def), beschreibung: def?.description || '', beispiel: paramBeispiel(def) })
  }
  felder.sort((a, b) => Number(b.pflicht) - Number(a.pflicht))
  return felder
}

function paramRef(def) {
  if (typeof def?.$ref === 'string') return def.$ref
  if (Array.isArray(def?.oneOf)) {
    const treffer = def.oneOf.find((t) => typeof t?.$ref === 'string')
    if (treffer) return treffer.$ref
  }
  return ''
}

function paramTyp(def) {
  const ref = paramRef(def)
  if (ref.endsWith('rollen_filter')) return 'filter'
  if (ref.endsWith('fremd_feld')) return 'fremd_feld'
  if (Array.isArray(def?.oneOf) && def.oneOf.some((t) => t?.type === 'string') && def.oneOf.some((t) => t?.type === 'object')) return 'text_oder_json'
  if (def?.enum) return 'auswahl'
  const typ = def?.type
  if (typ === 'array') return 'liste'
  if (typ === 'integer' || typ === 'number') return 'zahl'
  if (typ === 'boolean') return 'schalter'
  if (typ === 'object') return 'json'
  return 'text'
}

function paramEnum(def) {
  return Array.isArray(def?.enum) ? def.enum : []
}

function paramBeispiel(def) {
  if (Array.isArray(def?.examples) && def.examples.length) return def.examples[0]
  if (def?.example !== undefined) return def.example
  return undefined
}

/** Nur die Baustein-Parameter einer Regel (ohne baustein/stufe/gewicht). */
export function regelWerte(regel) {
  const { baustein, stufe, gewicht, ...rest } = regel || {}
  const result = {}
  for (const [k, v] of Object.entries(rest)) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    result[k] = v
  }
  return result
}

/** Regel aus Formularwerten bauen — leere Werte werden nie mitgeschleppt. */
export function regelBauen(baustein, stufe, gewicht, werte) {
  const regel = { baustein }
  if (stufe && stufe !== 'sollte') regel.stufe = stufe
  else if (stufe) regel.stufe = stufe
  if (gewicht !== undefined && gewicht !== null && gewicht !== '' && !Number.isNaN(Number(gewicht))) {
    regel.gewicht = Number(gewicht)
  }
  for (const [k, v] of Object.entries(werte || {})) {
    if (v === undefined || v === null || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    regel[k] = v
  }
  return regel
}

// ── JSON-Reiter (synchron, verlustfrei) ────────────────────────────────────

/** Definition → schön formatierter JSON-Text. */
export function jsonText(definition) {
  return JSON.stringify(definition ?? {}, null, 2)
}

/**
 * JSON-Text übernehmen. {ok, definition?, fehler?} — bei Fehlern bleibt der
 * vorherige Stand erhalten (verlustfrei: der Text selbst wird nie verworfen).
 */
export function jsonUebernehmen(text) {
  let wert
  try {
    wert = JSON.parse(text)
  } catch (err) {
    return { ok: false, fehler: `Das JSON ist nicht lesbar: ${err.message}` }
  }
  if (!wert || typeof wert !== 'object' || Array.isArray(wert)) {
    return { ok: false, fehler: 'Die Datei muss ein JSON-Objekt sein.' }
  }
  return { ok: true, definition: wert }
}

// ── Formular gegen schemawidrige JSON-Werte absichern ──────────────────────

/**
 * Wert als Liste — nur wenn er wirklich ein Array ist. Sonst leer.
 *
 * Der JSON-Reiter übernimmt syntaktisch gültige, aber schemawidrige Werte
 * (z. B. `feiertage: "ostermontag"` oder `{}`) unverändert. Solche Werte
 * dürfen das Formular nicht abstürzen lassen (`(wert || []).filter is not a
 * function`), bevor die übergebenen Prüfmeldungen sichtbar werden. Die
 * Rohdefinition bleibt unangetastet — der Wert wird nur zum Rendern in eine
 * leere Liste überführt, damit er im JSON-Reiter korrigierbar bleibt.
 */
export function alsListe(wert) {
  return Array.isArray(wert) ? wert : []
}

// ── Meldungen nach Pfad ────────────────────────────────────────────────────

/**
 * Prüfmeldungen (JSON-Pointer-Pfade) zu Formularabschnitten gruppieren:
 * '/felder/0/art' → Schlüssel 'felder:0'. Abschnitte ohne Treffer → ''.
 */
export function abschnittsSchluessel(pfad) {
  if (typeof pfad !== 'string' || !pfad.startsWith('/')) return ''
  const teile = pfad.split('/').filter(Boolean)
  const zahl = (t) => /^\d+$/.test(t || '')
  // Reihenfelder zuerst prüfen — sonst fängt der allgemeine Index-Fall sie ab.
  if (teile[0] === 'terminreihen' && teile.length >= 4 && zahl(teile[1]) && teile[2] === 'felder' && zahl(teile[3])) {
    return `terminreihe:${teile[1]}:felder:${teile[3]}`
  }
  if (teile.length >= 2 && zahl(teile[1])) return `${teile[0]}:${teile[1]}`
  return teile[0] || ''
}

/** Meldungen nach Abschnitt gruppieren (Schlüssel → Meldungen). */
export function meldungenNachAbschnitt(meldungen) {
  const gruppen = new Map()
  for (const m of meldungen || []) {
    const key = abschnittsSchluessel(m?.pfad || '')
    if (!gruppen.has(key)) gruppen.set(key, [])
    gruppen.get(key).push(m)
  }
  return gruppen
}

/** Höchste Stufe einer Meldungsliste ('fehler' > 'warnung' > 'hinweis'). */
export function hoechsteStufe(meldungen) {
  const list = meldungen || []
  if (list.some((m) => m?.stufe === 'fehler')) return 'fehler'
  if (list.some((m) => m?.stufe === 'warnung')) return 'warnung'
  if (list.length) return 'hinweis'
  return ''
}

// ── Sonstiges ──────────────────────────────────────────────────────────────

/** Parameterreferenz '{parameter.x}' erkennen. */
export function istParameterRef(wert) {
  // Exakt — ohne trimmen: nur die saubere Speicherform ist eine Referenz.
  return typeof wert === 'string' && /^\{parameter\.[a-z0-9][a-z0-9_-]*\}$/.test(wert)
}

/** Datum oder Parameterreferenz in Eingabewert + Referenzmodus zerlegen. */
export function wertOderRefLesen(wert) {
  if (istParameterRef(wert)) {
    return { modus: 'parameter', wert: String(wert).trim().slice(11, -1), datum: '' }
  }
  return { modus: 'datum', wert: '', datum: typeof wert === 'string' ? wert : '' }
}

/** Eingabewert + Modus → JSON-Wert ('{parameter.x}' oder Datum). */
export function wertOderRefAus(angaben = {}) {
  if (angaben.modus === 'parameter') {
    return angaben.wert ? `{parameter.${angaben.wert}}` : ''
  }
  return angaben.datum || ''
}

/** Kennung ist für ein JSON-Schema-Muster gültig (Kleinbuchstaben-Kurzname). */
export function kennungGueltig(id) {
  return typeof id === 'string' && /^[a-z0-9][a-z0-9_-]*$/.test(id)
}

/** Merkmals-Ziele einer Definition: person + lieder + eigene Sammlungen. */
export function merkmalsZiele(definition) {
  const ziele = [
    { wert: 'person', name: 'Fähigkeiten / Eigenschaften der Personen' },
    // 'lieder' ist eingebaut — immer wählbar, auch wenn noch nichts deklariert ist.
    { wert: 'lieder', name: 'Angaben der Liedliste „lieder“ (eingebaut)' },
  ]
  const sammlungsIds = new Set((definition?.sammlungen || []).map((s) => s?.id).filter(Boolean))
  const deklariert = new Set(Object.keys(definition?.merkmale || {}))
  for (const id of sammlungsIds) {
    if (id === 'lieder') continue
    ziele.push({ wert: id, name: `Angaben der Liste „${id}“` })
  }
  for (const id of deklariert) {
    if (!ziele.some((z) => z.wert === id)) ziele.push({ wert: id, name: `Angaben „${id}“` })
  }
  return ziele
}

/** Stabile Abschnitts-/Feldkennung für Automatisierungsselektoren. */
export function abschnittsKennung(titel) {
  return 'pr-pe-' + String(titel).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}
