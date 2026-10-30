/**
 * UX-C3b — Auswahllisten statt Freitext im Plantyp-Editor (Befund
 * DMB-674355ec0e2b: „wo man bestimmte dinge exakt referenzieren muss, soll
 * keine freitexteingabe sondern auswahl über dropdown geschehen“).
 *
 * Reine Helfer ohne Vue und ohne Seiteneffekte (mit `node --test` geprüft):
 *
 *   1. `auswahlMitAltwert` — die Optionen einer Auswahlliste. Ein gespeicherter
 *      Wert, den die Liste nicht kennt (Altwert, Tippfehler, gelöschte
 *      Sammlung), wird ANGEZEIGT statt still verworfen: er bleibt als eigene
 *      Option stehen und wird als „unbekannter Wert“ benannt.
 *
 *   2. Herkunftslisten für die Auswahlfelder: Felder der Definition,
 *      Feldpfade, Sammlungen, Listenmerkmale, Anlässe, Varianten sowie die
 *      Kennungen fremder Planvorlagen (`plantyp_optionen`). Alle nehmen den
 *      Wert, der gerade gespeichert ist, unverändert mit auf.
 *
 *   3. `beschriftung` — Text einer Option: bevorzugt der Anzeigename, sonst
 *      die Kennung. Freitext bleibt nur, wo er wirklich frei ist (Name,
 *      Beschreibung, Wochen, Uhrzeit).
 */

import { feldPfadListe as feldPfadListeAus } from './editor.mjs'

/** Beschriftung eines gespeicherten Werts, der in der Liste nicht vorkommt. */
export const UNBEKANNT = 'unbekannter Wert'

/**
 * Eine Option der Auswahlliste: `{ wert, text, unbekannt }`.
 * @param {string} wert gespeicherter Wert
 * @param {string} [text] Anzeigename
 * @param {{ unbekannt?: boolean, hinweis?: string }} [zusatz]
 */
export function option(wert, text, zusatz = {}) {
  return {
    wert: wert === undefined || wert === null ? '' : String(wert),
    text: text === undefined || text === null || text === '' ? String(wert ?? '') : String(text),
    unbekannt: zusatz.unbekannt === true,
    hinweis: zusatz.hinweis || '',
  }
}

/** Bekannte Werte einer Optionsliste (als Menge). */
export function bekannteWerte(optionen) {
  return new Set((optionen || []).map((o) => (o && typeof o === 'object' ? o.wert : o)))
}

/**
 * Optionsliste mit dem gespeicherten Wert.
 *
 * @param {Array} optionen bekannte Optionen (`{wert, text}` oder Skalare)
 * @param {*} wert aktuell gespeicherter Wert
 * @param {{ leerName?: string, unbekanntName?: string }} [texte]
 * @returns {Array<{wert: string, text: string, unbekannt: boolean, hinweis: string}>}
 *   Bei `leerName` steht zusätzlich eine leere Option („— keinen Bereich —“)
 *   vorn. Ein unbekannter Wert wird als eigene Option angehängt.
 */
export function auswahlMitAltwert(optionen, wert, texte = {}) {
  const liste = (optionen || []).map((o) => (o && typeof o === 'object'
    ? option(o.wert, o.text, { unbekannt: o.unbekannt === true, hinweis: o.hinweis })
    : option(o, o)))
  const gespeichert = wert === undefined || wert === null ? '' : String(wert)
  const ergebnis = []
  if (texte.leerName !== undefined && texte.leerName !== null) {
    ergebnis.push(option('', texte.leerName))
  }
  ergebnis.push(...liste)
  if (gespeichert && !bekannteWerte(liste).has(gespeichert)) {
    ergebnis.push(option(gespeichert, `${gespeichert} (${texte.unbekanntName || UNBEKANNT})`,
      { unbekannt: true, hinweis: `${gespeichert} (${texte.unbekanntName || UNBEKANNT})` }))
  }
  return ergebnis
}

/** Ist der gespeicherte Wert in der Liste unbekannt (und nicht leer)? */
export function istUnbekannt(optionen, wert) {
  const gespeichert = wert === undefined || wert === null ? '' : String(wert)
  if (!gespeichert) return false
  return !bekannteWerte(optionen).has(gespeichert)
}

// ── „Anderer Wert …“ (Operator-Entscheidung aus dem Review UX-C3b) ────────
//
// Eine Auswahl mit bekannter Liste darf nie unbedienbar sein: Wer einen Wert
// braucht, den die Liste nicht kennt (freie Werte, geleerte Definition), wählt
// „Anderer Wert …“ und tippt ihn ins Textfeld. Ist die Liste leer, zeigt die
// Oberfläche NUR das Textfeld.

/** Optionswert des Eintrags „Anderer Wert …“ (kein gültiger Kennungswert). */
export const ANDERER_WERT = '\u0000anderer-wert'

/** Text des Eintrags „Anderer Wert …“. */
export const ANDERER_WERT_TEXT = 'Anderer Wert …'

/**
 * Optionsliste mit dem Eintrag „Anderer Wert …“.
 * @param {Array} optionen bekannte Optionen (`{wert, text}` oder Skalare)
 * @param {{ text?: string }} [texte]
 * @returns {Array<{wert: string, text: string, unbekannt: boolean, hinweis: string}>}
 */
export function mitAnderemWert(optionen, texte = {}) {
  const liste = (optionen || []).map((o) => (o && typeof o === 'object'
    ? option(o.wert, o.text, { unbekannt: o.unbekannt === true, hinweis: o.hinweis })
    : option(o, o)))
  liste.push(option(ANDERER_WERT, texte.text || ANDERER_WERT_TEXT,
    { hinweis: 'Der Wert wird eingetippt und muss exakt passen.' }))
  return liste
}

/**
 * Darstellung eines Kennungswerts als Auswahl + „Anderer Wert …“.
 *
 * `auswahl` ist `'liste'` (gespeicherter Wert steht in der Liste oder ist leer),
 * `'anderer'` (gespeicherter Wert ist unbekannt → Textfeld mit genau diesem
 * Wert, NICHTS geht verloren) oder `'text'` (die Liste ist leer → direkt
 * Textfeld; ein gespeicherter Altwert steht darin).
 *
 * @param {Array} optionen bekannte Optionen (`{wert, text}` oder Skalare)
 * @param {*} wert gespeicherter Wert
 * @param {{ text?: string }} [texte] Text des Eintrags „Anderer Wert …“
 */
export function wertAuswahl(optionen, wert, texte = {}) {
  const liste = (optionen || []).map((o) => (o && typeof o === 'object'
    ? option(o.wert, o.text, { unbekannt: o.unbekannt === true, hinweis: o.hinweis })
    : option(o, o)))
  const gespeichert = wert === undefined || wert === null ? '' : String(wert)
  const alt = gespeichert !== '' && !bekannteWerte(liste).has(gespeichert)
  return {
    leer: liste.length === 0,
    altwert: alt,
    modus: liste.length === 0 ? 'text' : (alt ? 'anderer' : 'liste'),
    optionen: liste.length === 0 ? [] : mitAnderemWert(liste, texte),
    text: gespeichert,
    andererText: texte.text || ANDERER_WERT_TEXT,
  }
}

/** Anzeigename einer Kennung aus einer Liste `{kennung|id|wert, name|text}`. */
export function nameZu(optionen, wert, ersatz) {
  const gespeichert = wert === undefined || wert === null ? '' : String(wert)
  for (const o of optionen || []) {
    const kennung = o && typeof o === 'object' ? (o.wert ?? o.kennung ?? o.id) : o
    if (String(kennung) === gespeichert) {
      const name = o && typeof o === 'object' ? (o.text ?? o.name ?? o.anzeige) : o
      return name || gespeichert
    }
  }
  return ersatz === undefined ? gespeichert : ersatz
}

// ── Quellen aus der Definition ─────────────────────────────────────────────

/** Alle Felder eines Baums (Gruppen, Varianten, Teile, Ablauf) — flach. */
export function alleFelder(felder, gefunden = []) {
  for (const f of felder || []) {
    if (!f || typeof f !== 'object') continue
    gefunden.push(f)
    if (Array.isArray(f.inhalt)) alleFelder(f.inhalt, gefunden)
    for (const zweig of [...(f.varianten || []), ...(f.teile || [])]) {
      const obj = typeof zweig === 'string' ? { id: zweig } : zweig
      if (Array.isArray(obj?.inhalt)) alleFelder(obj.inhalt, gefunden)
    }
    for (const elem of f.elemente || []) {
      const e = typeof elem === 'string' ? { typ: elem } : elem
      if (Array.isArray(e?.inhalt)) alleFelder(e.inhalt, gefunden)
    }
  }
  return gefunden
}

/** Felder der Definition: Kurzform (`felder`) ODER alle Terminreihen. */
export function felderDerDefinition(definition) {
  const def = definition || {}
  if (Array.isArray(def.felder)) return alleFelder(def.felder)
  const liste = []
  for (const reihe of def.terminreihen || []) liste.push(...alleFelder(reihe?.felder))
  return liste
}

/**
 * Feldkennungen (oberste Ebene, für Regel-Parameter „Feld“).
 * Bei mehreren Terminreihen tragen die Felder der zweiten Reihe das Präfix
 * `<reihe>:` — nur so ist der Verweis eindeutig (der Server prüft beide Formen).
 */
export function feldOptionen(definition) {
  const def = definition || {}
  // NICHT `liste` nennen: das würde den Import `option` beschatten (dann
  // liefert die Funktion still eine leere/fehlerhafte Liste).
  const optionen = []
  // WICHTIG: for..of über `felder` — ein Callback an `.forEach` bekäme
  // `(feld, index, liste)`, also den INDEX als Präfix.
  const sammeln = (felder, praefix) => {
    for (const f of felder || []) {
      if (!f?.id) continue
      const wert = `${praefix}${f.id}`
      optionen.push(option(wert, f.name ? `${f.name} (${wert})` : wert))
    }
  }
  // Hat die Definition ein (auch leeres) Feld-Array, gilt die Kurzform:
  // dann kommt kein Reihenfeld mehr dazu — genau wie beim Speichern.
  if (Array.isArray(def.felder)) sammeln(def.felder, '')
  else {
    for (const reihe of def.terminreihen || []) {
      const id = reihe?.id
      sammeln(reihe?.felder, !id || id === 'standard' ? '' : `${id}:`)
    }
  }
  return optionen
}

/**
 * Feld-Pfade des Baums (für „nicht gleichzeitig“, „Feld dort“,
 * Formatvorlagen). Enthält auch die Pfade der Unterfelder.
 */
export function feldPfadOptionen(definition) {
  const def = definition || {}
  const optionen = []
  const pfade = (felder, basis) => {
    for (const eintrag of feldPfadListeAus(felder || []) || []) {
      if (!eintrag?.pfad) continue
      const pfad = basis + eintrag.pfad
      optionen.push(option(pfad, eintrag.name ? `${eintrag.name} (${pfad})` : pfad))
    }
  }
  if (Array.isArray(def.felder)) pfade(def.felder, '')
  else {
    for (const reihe of def.terminreihen || []) {
      const id = reihe?.id
      pfade(reihe?.felder, !id || id === 'standard' ? '' : `${id}:`)
    }
  }
  return optionen
}

/** Sammlungen: „lieder“ (eingebaut) + eigene Deklarationen. */
export function sammlungOptionen(definition) {
  const liste = [option('lieder', 'lieder — eingebaute Liedliste')]
  for (const s of (definition || {}).sammlungen || []) {
    if (!s?.id || s.id === 'lieder') continue
    liste.push(option(s.id, s.name ? `${s.name} (${s.id})` : s.id))
  }
  return liste
}

/** Merkmale einer Merkmals-Gruppe (`merkmale[ziel]`), als Auswahl. */
export function merkmalOptionen(definition, ziel) {
  const gruppe = (definition || {}).merkmale?.[ziel]
  if (!Array.isArray(gruppe)) return []
  return gruppe
    .filter((m) => m && typeof m.id === 'string' && m.id)
    .map((m) => option(m.id, m.name ? `${m.name} (${m.id})` : m.id))
}

/** Merkmale der Personen — häufigster Fall einer Merkmals-Referenz. */
export function personenMerkmalOptionen(definition) {
  return merkmalOptionen(definition, 'person')
}

/** Anlässe der Definition (`anlaesse[].id`). */
export function anlassOptionen(definition) {
  return ((definition || {}).anlaesse || [])
    .filter((a) => a && typeof a.id === 'string' && a.id)
    .map((a) => option(a.id, a.name ? `${a.name} (${a.id})` : a.id))
}

/** Varianten-Kennungen aller Gruppen-Felder (für Bedingungen). */
export function varianteOptionen(definition) {
  const liste = []
  for (const f of felderDerDefinition(definition)) {
    for (const v of f.varianten || []) {
      const obj = typeof v === 'string' ? { id: v } : v
      if (!obj?.id) continue
      liste.push(option(obj.id, obj.name ? `${obj.name} (${obj.id})` : obj.id))
    }
  }
  return liste
}

/**
 * Kennungen fremder Planvorlagen (planübergreifender Verweis „uebung“,
 * „auch_in“). `typen` ist `plantypen_liste` des Servers (`{id, schluessel,
 * name}`); die eigene Vorlage steht nicht zur Wahl.
 */
export function plantypOptionen(typen, eigenerPlantyp) {
  const liste = []
  for (const t of typen || []) {
    const kennung = t?.schluessel || t?.id
    if (!kennung) continue
    if (eigenerPlantyp && (kennung === eigenerPlantyp || t?.id === eigenerPlantyp)) continue
    liste.push(option(kennung, t.name ? `${t.name} (${kennung})` : kennung))
  }
  return liste
}

/**
 * Gruppen der Gemeinde (Feld „team“ → Obergruppe, Personenpool). Quelle ist
 * `einrichten_rechte.gruppen` des Servers (`{kennung, name}`).
 */
export function gruppenOptionen(gruppen) {
  const liste = []
  for (const g of gruppen || []) {
    const kennung = g && typeof g === 'object' ? (g.kennung ?? g.id ?? g.name) : g
    if (!kennung) continue
    const name = g && typeof g === 'object' ? (g.name ?? g.gruppenname) : g
    liste.push(option(kennung, name && name !== kennung ? `${name} (${kennung})` : kennung))
  }
  return liste
}

/**
 * Bezugsfelder der Vorbelegung (Feld-Einstellung „Wert kommt aus“).
 *
 * Die Prüfung akzeptiert „eintrag.x“, „bezug.x“ und Feldpfade der Definition
 * (`unbekanntes_bezugsfeld`). Deshalb stehen hier BEIDE Formen: die
 * Eigenschaften der Sammlung (aus den Merkmalen) und die Feldpfade. Ein
 * gespeicherter Altwert bleibt als „unbekannter Wert“ sichtbar.
 */
export function bezugOptionen(definition) {
  const def = definition || {}
  const liste = []
  const sammlungen = (def.sammlungen || []).map((s) => s?.id).filter(Boolean)
  if (!sammlungen.includes('lieder')) sammlungen.unshift('lieder')
  const merkmale = def.merkmale && typeof def.merkmale === 'object' ? def.merkmale : {}
  for (const sammlung of sammlungen) {
    for (const m of merkmale[sammlung] || []) {
      if (!m?.id) continue
      const wert = `eintrag.${m.id}`
      liste.push(option(wert, m.name ? `${wert} — ${m.name}` : wert))
    }
  }
  for (const eintrag of feldPfadOptionen(def)) {
    liste.push(option(`bezug.${eintrag.wert}`, `bezug.${eintrag.text}`))
  }
  for (const eintrag of feldPfadOptionen(def)) {
    liste.push(option(eintrag.wert, eintrag.text))
  }
  return liste
}

// ── Prüfstand: unbekannte Werte im Formular finden ────────────────────────

/**
 * Die Prüfmeldungen des Servers, die einen „unbekannten“ Wert benennen
 * (`unbekannte_sammlung`, `unbekanntes_regel_feld`, `unbekannter_anlass`,
 * `unbekannte_variante`, `unbekanntes_merkmal`, `unbekannter_feiertag`).
 * Die Oberfläche markiert damit genau die Felder, deren gespeicherter Wert
 * nicht (mehr) in der Auswahlliste steht.
 */
export const UNBEKANNT_CODES = [
  'unbekannte_sammlung', 'unbekanntes_regel_feld', 'unbekannter_anlass',
  'unbekannte_variante', 'unbekanntes_merkmal', 'unbekannter_feiertag',
  'unbekannter_baustein', 'unbekannte_fuellstrategie', 'unbekannter_parameter',
]

/** Prüfmeldungen, die an einem JSON-Pfad einen unbekannten Wert melden. */
export function unbekanntAmPfad(meldungen, pfad) {
  const ziel = '/' + String(pfad || '').replace(/^\/+|\/+$/g, '')
  return (meldungen || []).filter((m) => m
    && m.pfad === ziel
    && UNBEKANNT_CODES.includes(m.code || m.schluessel || ''))
}
