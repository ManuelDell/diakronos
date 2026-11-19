/**
 * CHAT-5-UI · Umfragen — die Regeln (ohne DOM prüfbar).
 *
 * Konzept: `docs/konzepte/CHAT-KONZEPT.md` Abschnitt S2. Der Server
 * (`backend/src/diakronos_app/api/chat.py`) entscheidet alles, was Rechte,
 * Anonymität und Fristen angeht; hier stehen NUR die Anzeige- und
 * Bedienregeln, damit die Komponenten (`ChatUmfrage.vue`,
 * `ChatUmfrageDialog.vue`) keine zweite Wahrheit bauen:
 *
 *   * `umfrageAnsehen`  — was zeigt die Karte im Verlauf (Balken, Zahlen,
 *     Frist, Zustand, eigener Stand, „schließen“ ja/nein)?
 *   * `umfrageAnlegenFrist`/`umfrageFristEingabe` — Frist als Wandzeit in
 *     Europe/Berlin (der Server liest „JJJJ-MM-TT HH:MM“ in der Zeitzone der
 *     Gemeinde; ein `toISOString()` würde die Uhr verschieben).
 *   * `umfragePruefen`  — die Bedienprüfung des Dialogs (leere Felder, 2–15
 *     Optionen). Rechte prüft NUR der Server.
 *   * `umfrageZeileLesen` — die Hülle-Nachricht (`umfrage`-Schlüssel) prüfen,
 *     ob sie eine Umfrage trägt (für Verlauf und Tests).
 *
 * ANONYM: Namen werden hier NIE gelesen. `eigene_stimme` ist bei einer anonymen
 * Umfrage `null` (der Server liefert keine), `abgestimmt` sagt nur DASS jemand
 * (die eigene Person) abgestimmt hat. Der Hinweis „erratbar“ kommt vom Server
 * (`hinweis`) oder — falls er fehlt — aus derselben Schwelle (`abgegeben < 5`).
 */

import { wandZeit } from '../../../shared/zeit.mjs'

/** Optionen: mindestens 2, höchstens 15 (Server: ``OPTIONEN_MIN``/``_MAX``). */
export const OPTIONEN_MIN = 2
export const OPTIONEN_MAX = 15

/** Ab wie vielen Abgegebenen der Hinweis entfällt (Server: ``HINWEIS_AB``). */
export const HINWEIS_AB = 5

/** Zeichengrenzen der Frage (Server: ``FRAGE_MAX`` = 1000) und einer Option. */
export const FRAGE_MAX = 1000
export const OPTION_MAX = 200

/** Die Zeitzone der Gemeinde — dieselbe Uhr, in der der Server die Frist liest. */
export const ZEITZONE = 'Europe/Berlin'

/** Beschriftungen des Bereichs — EINE Stelle, Tests lesen sie hier. */
export const TEXTE = {
  titel: 'Umfrage',
  neu: 'Umfrage starten',
  abstimmen: 'Abstimmen',
  aendern: 'Stimme ändern',
  schliessen: 'Umfrage schließen',
  anonym: 'Anonym',
  offen: 'Offen — Namen sichtbar',
  mehrfach: 'Mehrfachauswahl möglich',
  laeuft: 'läuft bis zur Schließung',
  keine: 'Noch keine Stimme abgegeben.',
  stimmen: 'Stimmen',
  anonymHinweis: 'anonym — bei wenigen Teilnehmenden ist das Ergebnis trotzdem erratbar',
  anonymFest: 'Eine anonyme Stimme lässt sich nicht ändern.',
  erratbar: 'Ergebnis bei wenigen Teilnehmenden erratbar',
  abgestimmt: 'Du hast abgestimmt.',
  abgestimmtAnonym: 'Du hast abgestimmt — anonym, deine Wahl lässt sich nicht mehr zeigen oder ändern.',
  geschlossen: 'geschlossen',
}

const ZWEI = (n) => String(n).padStart(2, '0')

/**
 * Zeitpunkt aus Servertext (`2026-11-18T19:30:00`, `2026-11-18 19:30:00`) —
 * als WANDZEIT gelesen, nicht als UTC: der Server schreibt ohne Zeitzone, und
 * `new Date('…T19:30:00')` läse ihn als UTC (die Uhr verschöbe sich im
 * Sommer um zwei Stunden).
 */
export function umfrageZeit(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  // Zonenangabe abstreifen: die Frist ist immer Wandzeit (siehe oben).
  const text = String(wert).trim().replace(/(\.\d+)?(Z|[+-]\d{2}:?\d{2})$/, '')
  if (!/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(text)) return null
  return wandZeit(text)
}

/** „18.11.2026, 19:30“ (Wandzeit) — die Anzeige der Frist. */
export function umfrageZeitText(wert) {
  const d = umfrageZeit(wert)
  if (!d) return ''
  return `${ZWEI(d.getDate())}.${ZWEI(d.getMonth() + 1)}.${d.getFullYear()}, ${ZWEI(d.getHours())}:${ZWEI(d.getMinutes())}`
}

/** `JJJJ-MM-TT` (Wert eines `<input type="date">`). */
export function umfrageDatumEingabe(wert) {
  const d = umfrageZeit(wert)
  if (!d) return ''
  return `${d.getFullYear()}-${ZWEI(d.getMonth() + 1)}-${ZWEI(d.getDate())}`
}

/** `HH:MM` (Wert eines `<input type="time">`). */
export function umfrageUhrEingabe(wert) {
  const d = umfrageZeit(wert)
  if (!d) return ''
  return `${ZWEI(d.getHours())}:${ZWEI(d.getMinutes())}`
}

/**
 * Frist aus Datum + Uhrzeit des Dialogs für den Server: `JJJJ-MM-TT HH:MM`.
 *
 * Die Eingaben sind Wandzeit in Europe/Berlin — genau so, wie der Server sie
 * liest (`_frist_lesen`). KEIN `toISOString()`: das rechnete nach UTC um.
 *
 * @returns {{ok: boolean, wert?: string|null, fehler?: string}}
 */
export function umfrageAnlegenFrist(datum, uhrzeit) {
  const tag = String(datum || '').trim()
  if (!tag) return { ok: true, wert: null } // keine Frist = „bis zur Schließung“
  if (!/^\d{4}-\d{2}-\d{2}$/.test(tag)) {
    return { ok: false, fehler: 'Bitte ein gültiges Datum wählen.' }
  }
  const zeit = String(uhrzeit || '').trim()
  if (zeit && !/^\d{2}:\d{2}$/.test(zeit)) {
    return { ok: false, fehler: 'Bitte eine gültige Uhrzeit wählen.' }
  }
  const wert = `${tag} ${zeit || '23:59'}`
  const d = umfrageZeit(wert)
  if (!d) return { ok: false, fehler: 'Bitte ein gültiges Datum wählen.' }
  // Wandzeit-Prüfung: 31.02. würde im Date zum 03.03. „übersprungen“.
  if (umfrageDatumEingabe(wert) !== tag) {
    return { ok: false, fehler: 'Dieses Datum gibt es nicht.' }
  }
  if (d.getTime() <= Date.now()) {
    return { ok: false, fehler: 'Die Frist liegt in der Vergangenheit.' }
  }
  return { ok: true, wert }
}

/** Hat die Umfrage eine Frist? */
export function hatFrist(umfrage) {
  return Boolean(umfrage?.frist_am)
}

/**
 * Ist die Umfrage noch offen? Der Server sagt es (`offen`); fehlt das Feld
 * (alte Antwort), entscheiden Schließung und Frist.
 */
export function istOffen(umfrage, jetzt = new Date()) {
  if (!umfrage) return false
  if (typeof umfrage.offen === 'boolean') return umfrage.offen
  if (umfrage.geschlossen_am) return false
  const frist = umfrageZeit(umfrage.frist_am)
  return !(frist && frist.getTime() <= umfrageZeit(jetzt)?.getTime())
}

/** Darf die eigene Person noch abstimmen (offen UND anonym nicht schon gewesen)? */
export function darfAbstimmen(umfrage, jetzt = new Date()) {
  if (!istOffen(umfrage, jetzt)) return false
  if (umfrage?.anonym === true && umfrage?.abgestimmt === true) return false
  return true
}

/** Darf die eigene Person die Stimme ändern (offen + offene Umfrage + schon abgestimmt)? */
export function darfAendern(umfrage, jetzt = new Date()) {
  if (!istOffen(umfrage, jetzt)) return false
  if (umfrage?.anonym === true) return false // anonym: eine Stimme, fest
  return umfrage?.abgestimmt === true
}

/**
 * Der Beschriftungstext des Absende-Knopfs — oder `''`, wenn es keinen gibt.
 * Anonym nach der ersten Stimme: kein Knopf (die Stimme ist endgültig).
 */
export function abstimmKnopfText(umfrage, jetzt = new Date()) {
  if (darfAendern(umfrage, jetzt)) return TEXTE.aendern
  if (darfAbstimmen(umfrage, jetzt)) return TEXTE.abstimmen
  return ''
}

/**
 * Die Fristzeile: „endet am 18.11.2026, 19:30“ oder „läuft bis zur Schließung“.
 * Eine abgelaufene Frist behält ihren Zeitpunkt — sonst wüsste niemand, warum
 * nichts mehr geht.
 */
export function fristText(umfrage) {
  if (!hatFrist(umfrage)) return TEXTE.laeuft
  const text = umfrageZeitText(umfrage.frist_am)
  return text ? `endet am ${text}` : TEXTE.laeuft
}

/**
 * Der Zustandstext rechts im Kopf: „geschlossen“, „offen“ oder (ohne
 * Schließung, mit abgelaufener Frist) „Frist abgelaufen“.
 */
export function zustandText(umfrage, jetzt = new Date()) {
  if (!umfrage) return ''
  if (umfrage.geschlossen_am) return TEXTE.geschlossen
  if (istOffen(umfrage, jetzt)) return 'offen'
  return 'Frist abgelaufen'
}

/** Die Zahl der abgegebenen Personen (nicht der Stimmen). */
export function abgegebenZahl(umfrage) {
  const n = Number(umfrage?.abgegeben)
  return Number.isFinite(n) && n > 0 ? Math.trunc(n) : 0
}

/**
 * Ist das Ergebnis „bei wenigen erratbar“? Der Server schickt den Text
 * (`hinweis`); fehlt er, gilt dieselbe Schwelle wie dort.
 */
export function erratbar(umfrage) {
  if (typeof umfrage?.hinweis === 'string' && umfrage.hinweis.trim()) return true
  return abgegebenZahl(umfrage) < HINWEIS_AB
}

/** Der Hinweistext unter dem Ergebnis (Servertext zuerst, sonst die Schwelle). */
export function erratbarText(umfrage) {
  const eigener = String(umfrage?.hinweis || '').trim()
  if (eigener) return eigener
  if (abgegebenZahl(umfrage) < HINWEIS_AB) return TEXTE.erratbar
  return ''
}

/**
 * Die Optionen mit Balkenbreite und Beschriftung — die Anzeige des Ergebnisses.
 *
 * `anteil` ist der Zähler im Verhältnis zur HÖCHSTEN Option (so ist der
 * längste Balken immer voll; bei „Summen zählen“ wäre ein voller Balken erst
 * bei 100 % aller Stimmen zu sehen, was bei Mehrfachauswahl nie eintritt).
 * Die ZAHL steht immer daneben — der Balken ist Beiwerk, die Zahl die Wahrheit.
 *
 * Namen stehen NUR an einer offenen Umfrage (der Server schickt sie dort);
 * bei `anonym` werden sie verworfen, auch wenn eine Antwort sie trüge.
 */
export function ergebnisZeilen(umfrage) {
  const liste = Array.isArray(umfrage?.optionen) ? umfrage.optionen : []
  const zahlen = liste.map((o) => Number(o?.stimmen) || 0)
  const hoechste = zahlen.reduce((a, b) => Math.max(a, b), 0)
  const anonym = umfrage?.anonym === true
  return liste.map((o, i) => ({
    nummer: Number(o?.nummer) || i + 1,
    text: String(o?.text ?? ''),
    stimmen: zahlen[i],
    anteil: hoechste > 0 ? Math.round((zahlen[i] / hoechste) * 100) : 0,
    namen: anonym ? [] : (Array.isArray(o?.namen) ? o.namen.map(String) : []),
  }))
}

/** Die eigenen gewählten Nummern (anonym: NIE eine — der Server schickt `null`). */
export function eigeneWahl(umfrage) {
  if (!umfrage || umfrage.anonym === true) return []
  const roh = umfrage.eigene_stimme
  if (!Array.isArray(roh)) return []
  return roh.map((n) => Number(n)).filter((n) => Number.isInteger(n) && n > 0)
}

/**
 * Der Hinweis zur eigenen Stimme — oder `''`.
 * Anonym: nur DASS abgestimmt wurde, nie WAS.
 */
export function eigenerStandText(umfrage) {
  if (!umfrage || umfrage.abgestimmt !== true) return ''
  if (umfrage.anonym === true) return TEXTE.abgestimmtAnonym
  return TEXTE.abgestimmt
}

/**
 * Darf der „Umfrage schließen“-Knopf stehen?
 *
 * Der Server nennt das Recht an JEDER Umfrage in `darf_schliessen` (aus
 * `_darf_umfrage_schliessen`, denselben Zweigen wie `umfrage_schliessen`).
 * Gelesen wird AUSSCHLIESSLICH dieses Feld — keine Rolle, keine
 * Mitgliedschaft, keine `eigene`-Ableitung, keine zweite Prop am Bauteil.
 * Fehlt das Feld (alter Server), gilt es als „nicht erlaubt“: der Server
 * entscheidet, und ein geratener Knopf wäre eine zweite Wahrheit.
 *
 * Sobald der Knopf nichts mehr zu tun hätte (schon geschlossen / Frist
 * vorbei), steht er NICHT — das ist kein Recht, sondern der Zustand.
 */
export function darfSchliessenZeigen(umfrage) {
  return Boolean(umfrage) && istOffen(umfrage) && umfrage.darf_schliessen === true
}

/**
 * Eine Knopfwahl (Radio bzw. Checkbox) in die Liste der Nummern bringen.
 *
 * EINFACH: die neue Nummer ERSETZT die alte (ein Klick, eine Stimme — die
 * Auswahl bleibt so lange bestehen, bis eine andere Option gewählt wird).
 * MEHRFACH: an- und abschalten.
 *
 * @param {number[]} alt gewählte Nummern
 * @param {number} nummer angetippte Option
 * @param {boolean} mehrfach
 * @returns {number[]} sortiert, ohne Dubletten
 */
export function wahlUmschalten(alt, nummer, mehrfach = false) {
  const n = Number(nummer)
  const bisher = (Array.isArray(alt) ? alt : []).map(Number).filter((x) => Number.isInteger(x) && x > 0)
  if (!Number.isInteger(n) || n <= 0) return bisher
  if (!mehrfach) return [n]
  const ohne = bisher.filter((x) => x !== n)
  return (ohne.length === bisher.length ? [...ohne, n] : ohne).sort((a, b) => a - b)
}

/**
 * Die Bedienprüfung des Dialogs — NUR für die Bedienung (leere Felder, Anzahl,
 * Länge). Ob die Person darf, entscheidet ausschließlich der Server.
 *
 * @returns {{ok: boolean, fehler: string, frage?: string, optionen?: string[],
 *            mehrfach?: boolean, anonym?: boolean, frist?: string|null}}
 */
export function umfragePruefen({ frage = '', optionen = [], mehrfach = false, anonym = true, datum = '', uhrzeit = '' } = {}) {
  const frageText = String(frage || '').trim()
  if (!frageText) return { ok: false, fehler: 'Bitte eine Frage eingeben.' }
  if (frageText.length > FRAGE_MAX) {
    return { ok: false, fehler: `Die Frage darf höchstens ${FRAGE_MAX} Zeichen lang sein.` }
  }
  const texte = (Array.isArray(optionen) ? optionen : [])
    .map((o) => String(o ?? '').trim())
    .filter(Boolean)
  if (texte.length < OPTIONEN_MIN) {
    return { ok: false, fehler: `Bitte mindestens ${OPTIONEN_MIN} Antworten eingeben.` }
  }
  if (texte.length > OPTIONEN_MAX) {
    return { ok: false, fehler: `Höchstens ${OPTIONEN_MAX} Antworten sind möglich.` }
  }
  if (texte.some((t) => t.length > OPTION_MAX)) {
    return { ok: false, fehler: `Eine Antwort darf höchstens ${OPTION_MAX} Zeichen lang sein.` }
  }
  // Zwei gleiche Antworten sind keine Wahl, sondern ein Versehen.
  const doppelt = texte.filter((t, i) => texte.findIndex((u) => u.toLowerCase() === t.toLowerCase()) !== i)
  if (doppelt.length) {
    return { ok: false, fehler: `„${doppelt[0]}“ steht doppelt in den Antworten.` }
  }
  const frist = umfrageAnlegenFrist(datum, uhrzeit)
  if (!frist.ok) return { ok: false, fehler: frist.fehler }
  return {
    ok: true,
    fehler: '',
    frage: frageText,
    optionen: texte,
    mehrfach: mehrfach === true,
    anonym: anonym !== false,
    frist: frist.wert ?? null,
  }
}

/**
 * Eine Hülle-Nachricht prüfen: trägt sie eine Umfrage? Rückgabe ist die Zeile
 * selbst (mit `umfrage` oder `null`), oder `null`, wenn der Schlüssel fehlt.
 *
 * Eine GELÖSCHTE Nachricht trägt keine Umfrage (`null`): das Ergebnis einer
 * gelöschten Umfrage hat im Verlauf nichts mehr zu suchen (Serverregel).
 */
export function umfrageZeileLesen(nachricht) {
  if (!nachricht || typeof nachricht !== 'object') return null
  if (!('umfrage' in nachricht)) return null
  return { ...nachricht, umfrage: nachricht.umfrage || null }
}

/** Traegt die Zeile eine (nicht gelöschte) Umfrage? */
export function istUmfrageZeile(nachricht) {
  return Boolean(nachricht && nachricht.umfrage && !nachricht.geloescht)
}
