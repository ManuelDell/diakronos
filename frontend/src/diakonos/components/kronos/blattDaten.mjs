/**
 * A11 — die Zeilen und Handlungen des Termin-Blatts am Handy.
 *
 * Der Entwurf A11 („A11 Mobil Termin.png“, BERICHT.md Abschnitt 2/3) zeigt
 * das Blatt von unten mit FÜNF Angaben in fester Reihenfolge:
 *
 *   Zeit      „Fr 7. – So 9. November · ganztägig“
 *   Ort       „Freizeitheim Sonnenhof, Musterstadt“
 *   Kalender  (Entwurf: „Jugend · 12 Teilnehmer“ — die Kalender-/Gruppenzuordnung)
 *   Beschreibung
 *   Status    „Zu prüfen · eingetragen von …“ (Abzeichen)
 *
 * Warum eine eigene Datei ohne Vue/DOM: Die Karte verlangt prüfbares
 * Verhalten („Moderator + offener Vorschlag → Freigeben/Ablehnen; Mitglied →
 * nur Ansicht“, Schließen per Wischen/Escape/Fläche, Fokusfalle, Ziele
 * ≥ 44 px). Die Regeln stehen hier als reine Funktionen und werden in
 * `tests/a11-*.test.mjs` WIRKLICH ausgeführt; die Komponente
 * (`TerminBlatt.vue`) zeichnet nur.
 *
 * Nichts wird hier erfunden: fehlt eine Angabe in den Daten, liefert die
 * Zeile `null` und wird gar nicht gezeichnet (kein „—“-Rauschen, Prinzip Ä2).
 */

const MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
const TAGE = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag']

/** Wandelt Server-/Kalenderwerte in ein Datum; `null`, wenn unbrauchbar. */
export function alsDatum(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  // Termin-Zeiten sind WANDZEITEN (ZEIT-2): zu Fuß als Ortszeit gebaut, auch
  // ein reines Datum (`new Date('2026-11-07')` wäre UTC-Mitternacht).
  // TODO nach ZEIT-2: durch `wandZeit` aus `shared/zeit.mjs` ersetzen.
  const text = String(wert).trim()
  const m = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/)
  const d = m
    ? new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0))
    : new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

const kurz = (d) => `${TAGE[d.getDay()].slice(0, 2)} ${d.getDate()}.`
const lang = (d) => `${TAGE[d.getDay()]}, ${d.getDate()}. ${MONATE[d.getMonth()]}`

/**
 * Wie `lang`, aber ohne Wochentag — für den ZEITRAUM „Fr 7. – So 9. November“:
 * dort steht der Wochentag einmal links und das Monatswort einmal rechts.
 *
 * ACHTUNG: für die zwei Kalendertage derselben Anzeige wird `kurz()` benutzt —
 * damit der Test nicht von der Zeitzone des Rechners abhängt, vergleicht er
 * Wochentage über `Intl` mit `timeZone: 'UTC'`.
 */
const tagMonat = (d) => `${d.getDate()}. ${MONATE[d.getMonth()]}`
const uhr = (d) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`

/**
 * Ganztägige Termine enden in den Daten EXKLUSIV (Kalender-Konvention: der
 * 9.11. 00:00 als Ende heißt „bis einschließlich 8.11.“). Für die Anzeige
 * zählt der LETZTE Tag im Termin — deshalb ein Tag zurück. Dieselbe Rechnung
 * wie in `ical1-ganztags-ende` (dort serverseitig geprüft).
 */
export function letzterTag(start, ende) {
  const s = alsDatum(start)
  const e = alsDatum(ende)
  if (!s) return null
  if (!e) return s
  const zurueck = new Date(e.getTime())
  zurueck.setDate(zurueck.getDate() - 1)
  // Ende am selben Tag (00:00 des Folgetags) oder davor: es bleibt beim Start.
  return zurueck.getTime() < s.getTime() ? s : zurueck
}

/**
 * Zeitzeile des Blattes (Entwurf A11: „Fr 7. – So 9. November · ganztägig“).
 *
 *   gleicher Tag, mit Uhrzeit   „So 8. November · 10:00 – 11:30“
 *   gleicher Tag, ganztägig     „So 8. November · ganztägig“
 *   mehrere Tage                „Fr 7. – So 9. November · ganztägig“
 *   mehrere Tage, mit Uhrzeit   „Fr 7. – So 9. November“
 *   ohne Ende                   „So 8. November · 10:00“
 *
 * Ohne brauchbares Datum: `''` (die Zeile erscheint dann nicht).
 */
export function blattZeile(termin) {
  const start = alsDatum(termin?.start ?? termin?.element_start)
  if (!start) return ''
  const ganztags = termin?.allDay === true || termin?.all_day === true
  const ende = alsDatum(termin?.end ?? termin?.element_end)
  const letzter = letzterTag(start, ende)
  const mehrtags = letzter && letzter.toDateString() !== start.toDateString()

  if (mehrtags) {
    // Entwurf A11: „Fr 7. – So 9. November · ganztägig“ — Wochentag einmal
    // links, Monatswort einmal rechts (nicht „Fr 7. – So 9. November“ doppelt).
    const zeitraum = `${kurz(start)} – ${kurz(letzter)} ${MONATE[letzter.getMonth()]}`
    return ganztags ? `${zeitraum} · ganztägig` : zeitraum
  }

  const tag = lang(start)
  if (ganztags) return `${tag} · ganztägig`
  if (!ende) return `${tag} · ${uhr(start)}`
  const gleicherTag = ende.toDateString() === start.toDateString()
  return gleicherTag ? `${tag} · ${uhr(start)} – ${uhr(ende)}` : `${tag} · ${uhr(start)}`
}

/** Ort des Termins (Hauptressource, sonst die erste zusätzliche). */
export function blattOrt(termin) {
  if (!termin) return ''
  const haupt = String(termin.ressource_name || termin.ressource || '').trim()
  if (haupt) return haupt
  const weitere = Array.isArray(termin.zusaetzliche_ressourcen) ? termin.zusaetzliche_ressourcen : []
  const erste = weitere
    .map((r) => String(r?.ressource_name || r?.freitext_ressource || '').trim())
    .find(Boolean)
  return erste || ''
}

/**
 * Kalender-/Gruppenzuordnung (Entwurf A11: „Jugend · 12 Teilnehmer“).
 * Der Kalender ist die Zuordnung, die der Server mitliefert; der Zusatz
 * (Teilnehmerzahl) kommt aus den Daten, wenn es ihn gibt — sonst nur der
 * Kalender, nie eine erfundene Zahl.
 *
 * A11-N2 (Review): Angezeigt wird der ANZEIGENAME (`calendar_title` /
 * `calendar_name`), NIE der interne Schlüssel (`element_calendar`, z. B.
 * „gruppen“). Der Schlüssel bleibt der letzte Rückfall — aber nur, solange es
 * keinen Namen gibt (alte Antworten ohne `calendar_title`).
 */
export function blattKalender(termin) {
  if (!termin) return ''
  const anzeige = String(termin.calendar_title || termin.calendar_name || '').trim()
  const schluessel = String(termin.element_calendar || termin.calendar || '').trim()
  // A10-N2-Muster: Aus dem Schlüssel wird nur dann ein Anzeigename, wenn der
  // Server keinen mitliefert — „gruppen“ bleibt NICHT als Text stehen.
  const kalender = anzeige || anzeigenameAusSchluessel(schluessel)
  const zahl = Number(termin.teilnehmer ?? termin.teilnehmerzahl ?? NaN)
  const zusatz = Number.isFinite(zahl) && zahl > 0 ? `${zahl} Teilnehmer` : ''
  return [kalender, zusatz].filter(Boolean).join(' · ')
}

/**
 * Rückfall für alte Antworten ohne `calendar_title`: „gruppen“ → „Gruppen“,
 * „jugend_2026“ → „Jugend 2026“. Enthält der Schlüssel einen Namen, wird nur
 * das erste Wort groß geschrieben — eine reine Kennung (z. B. „cal-7f3a91“)
 * bleibt, wie sie ist, statt einen erfundenen Namen vorzutäuschen.
 */
export function anzeigenameAusSchluessel(schluessel) {
  const text = String(schluessel || '').trim()
  if (!text) return ''
  if (/\s/.test(text)) return text
  // Kennungen („cal-7f3a91“) bleiben unverändert, damit kein erfundener Name
  // vorgetäuscht wird: ein Teil aus Buchstaben UND Ziffern mit Ziffern-Block
  // (ab zwei Stellen) ist eine Kennung; „jugend_2026“ (Wort + bloßes Jahr)
  // bleibt ein Name.
  const teile = text.split(/[_-]+/).filter(Boolean)
  if (teile.some((t) => /\d{2,}/.test(t) && /[A-Za-zÄÖÜäöüß]/.test(t))) return text
  const woerter = teile.join(' ')
  return woerter.charAt(0).toUpperCase() + woerter.slice(1)
}

/** Beschreibung, Zeile für Zeile (leere Zeilen fallen weg). */
export function blattBeschreibung(termin) {
  const text = String(termin?.description ?? termin?.beschreibung ?? '').trim()
  if (!text) return []
  return text.split('\n').map((z) => z.trim()).filter(Boolean)
}

/**
 * Die Zeilen des Blattes in der Reihenfolge des Entwurfs. Jede Zeile:
 * `{ key, symbol, text, label }` — `symbol` ist ein Name aus
 * `components/ui/symbole.mjs` (A11: Uhr, Ort, Gruppe mit Symbolen), `label`
 * ist die Vorlesehilfe.
 *
 * @returns {Array<{key: string, symbol: string, text: string, label: string}>}
 */
export function blattZeilen(termin) {
  const zeilen = []
  const zeit = blattZeile(termin)
  if (zeit) zeilen.push({ key: 'zeit', symbol: 'uhr', text: zeit, label: `Zeit: ${zeit}` })
  const ort = blattOrt(termin)
  if (ort) zeilen.push({ key: 'ort', symbol: 'ort', text: ort, label: `Ort: ${ort}` })
  const kalender = blattKalender(termin)
  if (kalender) zeilen.push({ key: 'kalender', symbol: 'gruppe', text: kalender, label: `Kalender: ${kalender}` })
  return zeilen
}

/**
 * Die Handlungsleiste des Blattes — was als KNOPF unter dem Inhalt steht.
 *
 * Entwurf A11 (verbindlich): „Freigeben“ ist der EINE Primärknopf
 * (Moderator + offener Vorschlag); „Bearbeiten“ steht daneben als sekundärer
 * Knopf und NUR im Bearbeiten-Modus (Lesemodus-Regeln aus UX3i). Alles
 * Gefährliche (Absagen/Löschen) steht NICHT hier, sondern im „⋯“ (K4).
 *
 * @param {{darfPruefen?: boolean, darfBearbeiten?: boolean, offen?: boolean}} lage
 * @returns {Array<{key: string, label: string, variant: string, primaer: boolean}>}
 */
export function blattKnoepfe({ darfPruefen = false, darfBearbeiten = false, offen = false } = {}) {
  const knoepfe = []
  if (darfBearbeiten === true) {
    knoepfe.push({ key: 'bearbeiten', label: 'Bearbeiten', variant: 'secondary', primaer: false })
  }
  if (darfPruefen === true && offen === true) {
    knoepfe.push({ key: 'freigeben', label: 'Freigeben', variant: 'primary', primaer: true })
  }
  return knoepfe
}

/**
 * Darf das Blatt überhaupt Handlungen anbieten? Nicht-Moderator und
 * bestätigter Termin (im Lesemodus): NUR Ansicht — kein ⋯, keine Knöpfe.
 */
export function blattHatAktionen({ darfPruefen = false, darfBearbeiten = false, offen = false } = {}) {
  return blattKnoepfe({ darfPruefen, darfBearbeiten, offen }).length > 0
}

// ── Schließen: Wischen nach unten ──────────────────────────────────────────
/** Ab dieser Zugstrecke (px) schließt das Blatt. */
export const WISCH_SCHLIESSEN = 96
/** Ab dieser Geschwindigkeit (px/ms) schließt es auch bei kürzerem Weg. */
export const WISCH_TEMPO = 0.5

/**
 * Wischen nach unten auswerten. `startY` → `endeY` (Bildschirmkoordinaten).
 * `dauer` in ms, optional — ohne Dauer zählt nur die Strecke.
 *
 * @returns {{schliessen: boolean, zug: number}}
 */
export function wischAuswerten({ startY = 0, endeY = 0, dauer = 0 } = {}) {
  const zug = Math.max(0, Number(endeY) - Number(startY))
  const tempo = dauer > 0 ? zug / dauer : 0
  return { schliessen: zug >= WISCH_SCHLIESSEN || (zug > 16 && tempo >= WISCH_TEMPO), zug }
}

// ── Fokusfalle ─────────────────────────────────────────────────────────────
/** Elemente, die den Fokus bekommen können (Tastatur erreichbar). */
const FOKUSIERBAR = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Fokusfalle: Aus einer Liste fokussierbarer Elemente den bestimmen, der als
 * Nächstes dran ist. `richtung` ist +1 (Tab) oder −1 (Umschalt+Tab); `null`
 * heißt „der Browser soll es tun“ (Fokus liegt mitten in der Liste).
 *
 * Am Ende → vorne (bzw. umgekehrt); außerhalb der Liste → erster/letzter.
 * `-1` heißt: nichts fokussierbar (dann bleibt der Fokus beim Halter).
 *
 * @param {ArrayLike<object>} elemente
 * @param {object|null} aktiv das gerade fokussierte Element
 * @param {number} richtung +1 / −1
 * @returns {number} Index in `elemente` oder −1
 */
export function fokusIndex(elemente, aktiv, richtung = 1) {
  const liste = Array.from(elemente || [])
  if (!liste.length) return -1
  const drin = liste.indexOf(aktiv)
  if (drin === -1) return richtung < 0 ? liste.length - 1 : 0
  const naechster = drin + richtung
  if (naechster < 0) return liste.length - 1
  if (naechster >= liste.length) return 0
  return naechster
}

/** Attributwert für die Fokusfalle (ein Selektor, EINE Quelle). */
export const FOKUS_SELEKTOR = FOKUSIERBAR

/** Ganztägig? (Server: `all_day`, Bibliothek: `allDay`.) */
export function istGanztags(termin) {
  return termin?.allDay === true || termin?.all_day === true
}

export default {
  alsDatum, letzterTag, blattZeile, blattOrt, blattKalender, anzeigenameAusSchluessel,
  blattBeschreibung,
  blattZeilen, blattKnoepfe, blattHatAktionen, wischAuswerten, fokusIndex,
  FOKUS_SELEKTOR, WISCH_SCHLIESSEN, WISCH_TEMPO, istGanztags,
}
