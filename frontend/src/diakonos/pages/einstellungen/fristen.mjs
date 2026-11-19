/**
 * fristen.mjs — Aufbewahrungsfristen des Chats (Karte CHAT-8-UI).
 *
 * Der Server liefert (`chat.fristen_lesen`) die gespeicherten Fristen, die
 * Standardwerte, den erlaubten Bereich und die FESTEN Fristen:
 *
 *   { chat_frist_gruppe_monate, chat_frist_direkt_monate,
 *     standard: { gruppe, direkt }, minimum, maximum,
 *     nachricht_monate, umfrage_stimmen_monate, meldung_monate }
 *
 * Diese Datei rechnet damit — ohne Vue und ohne DOM, damit die Regeln im
 * Node-Test prüfbar sind (`frontend/tests/chat8-fristen-ui.test.mjs`):
 * Vorbelegung der Felder, Prüfung der Eingabe, der Satz zum Verkürzen und die
 * lesenden Sätze der festen Fristen.
 *
 * GRUNDSATZ: Keine Zahl wird hier erfunden. Was der Server nicht schickt, wird
 * nicht behauptet — fehlt ein Feld, bleibt der Satz weg. Die Grenzen des
 * Bereichs (`minimum`…`maximum`) sind dieselben, die der Server beim Speichern
 * prüft; die Oberfläche prüft nur vorher, damit man den Fehler am Feld sieht.
 */

/** Die zwei Felder — Reihenfolge und Beschriftung der Oberfläche. */
export const FELDER = [
  { id: 'gruppe', label: 'Gruppengespräche', feld: 'chat_frist_gruppe_monate' },
  { id: 'direkt', label: 'Direktnachrichten und Runden', feld: 'chat_frist_direkt_monate' },
]

/** Vorgaben, wenn der Server (alter Stand) keine Grenzen mitschickt. */
export const GRENZEN_VORGABE = { minimum: 1, maximum: 120 }

/**
 * Der Satz beim Verkürzen — Wortlaut der Karte. Er wird NUR gezeigt, wenn die
 * neue Frist kleiner ist als die gespeicherte: der nächtliche Lauf löscht
 * Älteres endgültig, und das soll niemand nebenbei auslösen.
 */
export const VERKUERZEN_SATZ = 'Ältere Nachrichten werden beim nächsten nächtlichen Lauf endgültig gelöscht.'

/** „Monate“ mit richtiger Endung — 1 Monat, 2 Monate. */
export function monateText(zahl) {
  const n = Number(zahl)
  if (!Number.isFinite(n)) return ''
  return n === 1 ? '1 Monat' : `${n} Monate`
}

/**
 * Dativ: „nach einem Monat“, „nach 6 Monaten“. Deutsche Sätze über eine Frist
 * mit „nach …“ brauchen diese Form — sonst stünde „nach 6 Monate“ da.
 */
export function monateDativ(zahl) {
  const n = Number(zahl)
  if (!Number.isFinite(n)) return ''
  return n === 1 ? 'einem Monat' : `${n} Monaten`
}

/**
 * Die Zahlen aus der Serverantwort — nur ganze Zahlen, sonst `null`.
 * Ein fehlender oder unbrauchbarer Wert wird NICHT durch eine geratene Zahl
 * ersetzt (die Anzeige sagt dann lieber nichts).
 */
export function zahl(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  const n = Number(wert)
  return Number.isInteger(n) ? n : null
}

/**
 * Der Anzeigestand aus der Antwort: gespeicherte Werte, Standard, Grenzen und
 * die festen Fristen — jeweils nur, wenn der Server sie liefert.
 */
export function standLesen(antwort) {
  const a = antwort || {}
  const standard = a.standard || {}
  const min = zahl(a.minimum)
  const max = zahl(a.maximum)
  return {
    gespeichert: {
      gruppe: zahl(a.chat_frist_gruppe_monate),
      direkt: zahl(a.chat_frist_direkt_monate),
    },
    standard: {
      gruppe: zahl(standard.gruppe ?? standard.chat_frist_gruppe_monate),
      direkt: zahl(standard.direkt ?? standard.chat_frist_direkt_monate),
    },
    minimum: min === null ? GRENZEN_VORGABE.minimum : min,
    maximum: max === null ? GRENZEN_VORGABE.maximum : max,
    fest: {
      nachricht: zahl(a.nachricht_monate),
      umfrage: zahl(a.umfrage_stimmen_monate),
      meldung: zahl(a.meldung_monate),
    },
  }
}

/**
 * Die festen Fristen als Sätze — NUR aus den Feldern der Antwort. Fehlt eine
 * Zahl, fehlt ihr Satz (keine erfundene Frist auf dem Bildschirm).
 */
export function festeFristen(stand) {
  const fest = (stand && stand.fest) || {}
  const saetze = []
  if (fest.nachricht !== null && fest.nachricht !== undefined) {
    saetze.push({
      id: 'nachricht',
      text: `Gelöschte Nachrichten werden nach ${monateDativ(fest.nachricht)} endgültig entfernt.`,
    })
  }
  if (fest.umfrage !== null && fest.umfrage !== undefined) {
    saetze.push({
      id: 'umfrage',
      text: `Die Stimmen einer geschlossenen Umfrage werden nach ${monateDativ(fest.umfrage)} entfernt;`
        + ' das Ergebnis bleibt.',
    })
  }
  if (fest.meldung !== null && fest.meldung !== undefined) {
    saetze.push({
      id: 'meldung',
      text: `Erledigte Meldungen werden nach ${monateDativ(fest.meldung)} entfernt.`,
    })
  }
  return saetze
}

/**
 * Eingabe prüfen — dieselben Grenzen wie der Server (`chat_aufbewahrung`).
 * `werte` sind die Feldwerte (Text aus `input type="number"`); leer ist keine
 * Zahl. Ergebnis: `{ ok, fehler: {feldId: Satz}, werte: {feldId: Zahl} }`.
 */
export function eingabePruefen(werte, stand) {
  const min = stand?.minimum ?? GRENZEN_VORGABE.minimum
  const max = stand?.maximum ?? GRENZEN_VORGABE.maximum
  const fehler = {}
  const geprueft = {}
  for (const f of FELDER) {
    const roh = werte?.[f.id]
    // Text zuerst BESCHNEIDEN: `Number(' ')` wäre 0 und damit eine gültige
    // Zahl — eine Eingabe aus lauter Leerzeichen ist aber leer.
    const text = roh === null || roh === undefined ? '' : String(roh).trim()
    const leer = text === ''
    const n = leer ? NaN : Number(text)
    if (leer || !Number.isInteger(n)) {
      fehler[f.id] = 'Bitte eine ganze Zahl in Monaten eingeben.'
    } else if (n < min || n > max) {
      fehler[f.id] = `Bitte eine Zahl zwischen ${min} und ${max} eingeben.`
    } else {
      geprueft[f.id] = n
    }
  }
  return { ok: Object.keys(fehler).length === 0, fehler, werte: geprueft }
}

/**
 * Wird eine der Fristen KÜRZER als gespeichert? Nur dann fragt die Seite nach
 * und warnt (Karte Punkt 3). Vergleiche nur, wo beide Zahlen bekannt sind —
 * eine unbekannte alte Frist ist kein Anlass für eine Warnung.
 */
export function verkuerzt(neu, stand) {
  const alt = stand?.gespeichert || {}
  const felder = []
  for (const f of FELDER) {
    const neuerWert = zahl(neu?.[f.id])
    const alterWert = zahl(alt[f.id])
    if (neuerWert === null || alterWert === null) continue
    if (neuerWert < alterWert) felder.push(f.id)
  }
  return felder
}

/** Der Bestätigungstext beim Verkürzen: was gilt künftig, und was löscht das? */
export function verkuerzenFrage(neu, stand) {
  const betroffen = verkuerzt(neu, stand)
  if (!betroffen.length) return ''
  const alt = stand?.gespeichert || {}
  const teile = betroffen.map((id) => {
    const f = FELDER.find((x) => x.id === id)
    return `${f.label}: ${monateText(alt[id])} → ${monateText(neu[id])}`
  })
  return `${teile.join(' · ')}. ${VERKUERZEN_SATZ}`
}

/** Feldwerte als Text für die Eingabefelder (leer, wenn der Wert fehlt). */
export function feldTexte(stand) {
  const g = stand?.gespeichert || {}
  const texte = {}
  for (const f of FELDER) {
    const n = zahl(g[f.id])
    texte[f.id] = n === null ? '' : String(n)
  }
  return texte
}

/** Die Vorbelegung „Auf Standard zurücksetzen“ (nur bekannte Standardwerte). */
export function standardTexte(stand) {
  const s = stand?.standard || {}
  const texte = {}
  for (const f of FELDER) {
    const n = zahl(s[f.id])
    texte[f.id] = n === null ? '' : String(n)
  }
  return texte
}

/**
 * Der Hinweis unter jedem Feld: „Standard: 24 Monate“. Der Server schickt den
 * Standard mit, damit die Oberfläche ihn nicht kennen muss.
 */
export function standardHinweis(stand, feldId) {
  const n = zahl(stand?.standard?.[feldId])
  return n === null ? '' : `Standard: ${monateText(n)}`
}

/** Die Nutzlast für `chat.fristen_speichern` — beide Werte, ganze Zahlen. */
export function speicherNutzlast(neu) {
  return {
    chat_frist_gruppe_monate: zahl(neu?.gruppe),
    chat_frist_direkt_monate: zahl(neu?.direkt),
  }
}

/**
 * Ist etwas geändert? (Speichern-Knopf nur, wenn ja — wie im übrigen Haus.)
 */
export function geaendert(neu, stand) {
  const alt = stand?.gespeichert || {}
  return FELDER.some((f) => {
    const neuerWert = zahl(neu?.[f.id])
    return neuerWert !== zahl(alt[f.id])
  })
}
