/**
 * CHAT-3a — die Regeln der Seite „Nachrichten“, ohne DOM und ohne Vue.
 *
 * Die Seite (`pages/Nachrichten.vue`) zeichnet nur. Was sie zeigt und wann sie
 * nachlädt, steht HIER — prüfbar im Node-Test (`tests/chat3a-nachrichten.test.mjs`).
 *
 * Grundlagen (Chat-Konzept, Entscheidungen Manuel 17.11.2026):
 *   * 1/S1        — Verlauf je Gruppe/Untergruppe, Antwort-Zitat, Reaktionen,
 *                   „bearbeitet“, Soft-Delete als Hinweiszeile.
 *   * 6.2         — Variante B: Liste links, offenes Gespräch rechts; am Handy
 *                   zwei Ansichten (`#/nachrichten` und `#/nachrichten/<id>`).
 *   * 9 (F1–F11)  — Lesestand NUR als Summe „gelesen von N“ (F2), Stumm je
 *                   Person (F3), Untergruppe eigener Raum (F4), kein E2E (F6).
 *   * 10.1/10.2   — fünf Plätze in der Handy-Leiste, „Mehr“ öffnet die
 *                   bestehende Schublade; Ungelesen-Zähler am Tab.
 *
 * WAS HIER NICHT STEHT: kein Netzaufruf (die Seite benutzt `apiGet`/`apiCall`),
 * kein Timer (die Seite gibt `setInterval`/`visibilitychange` hinein), keine
 * Farben. Nur die Regel.
 */

// ZEIT-2: Chat-Zeitstempel sind WANDZEITEN (Uhr der Gemeinde, keine UTC) —
// dieselbe zentrale Deutung wie bei Terminen. Kein eigener Date-Weg hier.
import { wandZeit } from '../../shared/zeit.mjs'

// ── Grenzen (eine Stelle) ───────────────────────────────────────────────────

/** Takt der Aktualisierung (Karte: „z. B. 10 s“). */
export const TAKT_MS = 10_000

/** Höchstlänge einer Nachricht — dieselbe Zahl wie im Server (`NACHRICHT_MAX`). */
export const NACHRICHT_MAX = 4000

/**
 * Seitengröße des Verlaufs — dieselbe Zahl wie `SEITE` in `api/chat.py`.
 *
 * Sie entscheidet auch, ob es noch ÄLTERE Nachrichten geben kann: eine volle
 * Seite (`>= SEITE`) heißt „vielleicht ja“, eine kurze „der Anfang ist da“.
 */
export const SEITE = 50

/** Bearbeiten-Frist wie im Server (`BEARBEITEN_MINUTEN`). */
export const BEARBEITEN_MINUTEN = 15

/**
 * Das feste Reaktions-Set — DIESELBEN Zeichen wie `REAKTIONEN` in
 * `backend/src/diakronos_app/models/chat.py`. Eine andere Liste hier hieße:
 * die Oberfläche bietet ein Zeichen an, das der Server mit „Unbekannte
 * Reaktion.“ ablehnt.
 */
export const REAKTIONEN = ['👍', '❤', '🙏', '✅', '😀', '😢']

/** Höchstzahl der Vorschau-Zeichen einer letzten Nachricht (wie `_zitat`). */
export const VORSCHAU_MAX = 140

// ── Adresse ─────────────────────────────────────────────────────────────────

/** Grundadresse des Bereichs. */
export const BEREICH = '#/nachrichten'

/**
 * Gesprächs-Kennung aus der Adresse (`#/nachrichten/chat-gespraech-abc?x=1`).
 *
 * Der Bereich hat ZWEI Adressformen (Chat-Konzept 10.2):
 *   `#/nachrichten`          die Liste
 *   `#/nachrichten/<id>`     ein offenes Gespräch
 * `suche` ist KEINE Kennung, sondern der Platz der Personensuche (CHAT-3c/R2b)
 * — sie liefert deshalb `null` wie die Liste.
 *
 * @param {string} hash
 * @returns {string|null}
 */
export function gespraechAusHash(hash) {
  const roh = String(hash || '').split('?')[0].replace(/\/+$/, '')
  if (!roh.startsWith(`${BEREICH}/`)) return null
  const rest = roh.slice(BEREICH.length + 1)
  if (!rest || rest === 'suche' || rest.includes('/')) return null
  try {
    return decodeURIComponent(rest)
  } catch {
    // Unlesbare Kodierung ist keine Kennung (§ „nicht raten“) — dann Liste.
    return null
  }
}

/** Adresse eines Gesprächs (für Links und `location.hash`). */
export function gespraechHash(name) {
  const kennung = String(name || '').trim()
  if (!kennung) return BEREICH
  return `${BEREICH}/${encodeURIComponent(kennung)}`
}

// ── Zeit ────────────────────────────────────────────────────────────────────

/**
 * Server-Zeitstempel einer Chat-Nachricht als `Date`.
 *
 * `chat_nachricht.erstellt_am` ist eine WANDZEIT ohne Zeitzone (Model: `DateTime
 * (timezone=False)`, gefüllt aus `zeit.jetzt_wanduhr`) — sie beschreibt die Uhr
 * an der Wand der Gemeinde, NICHT UTC. Deshalb geht sie über `wandZeit` aus
 * `src/shared/zeit.mjs`: dieselbe Deutung wie bei jedem Termin, EINE Stelle für
 * die Umrechnung (ZEIT-2: kein eigener `new Date(replace(' ', 'T'))`-Weg).
 *
 * @returns {Date|null} `null` bei unlesbarem Wert (nie „Invalid Date“ anzeigen)
 */
export function zeitpunkt(wert) {
  return wandZeit(wert)
}

/** Ist derselbe Kalendertag (Ortszeit)? */
export function gleicherTag(a, b) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate()
}

const WOCHENTAGE = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag']
const MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

const zwei = (n) => String(n).padStart(2, '0')

/** „09:12“ */
export function uhrzeit(wert) {
  const d = zeitpunkt(wert)
  if (!d) return ''
  return `${zwei(d.getHours())}:${zwei(d.getMinutes())}`
}

/**
 * Zeitangabe der Gesprächsliste — kurz, weil die Spalte schmal ist:
 *   heute    → „09:12“
 *   gestern  → „gestern“
 *   älter    → „18.11.“ (anderes Jahr: „18.11.25“)
 */
export function listenZeit(wert, jetzt = new Date()) {
  const d = zeitpunkt(wert)
  if (!d) return ''
  const heute = zeitpunkt(jetzt) || new Date()
  if (gleicherTag(d, heute)) return `${zwei(d.getHours())}:${zwei(d.getMinutes())}`
  const gestern = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() - 1, 12)
  if (gleicherTag(d, gestern)) return 'gestern'
  const datum = `${zwei(d.getDate())}.${zwei(d.getMonth() + 1)}.`
  return d.getFullYear() === heute.getFullYear() ? datum : `${datum}${String(d.getFullYear()).slice(2)}`
}

/**
 * Tages-Überschrift im Verlauf:
 *   heute        → „Heute“
 *   gestern      → „Gestern“
 *   diese Woche  → „Montag“ (Wochentagsname)
 *   älter        → „18. November 2026“
 */
export function tagesUeberschrift(wert, jetzt = new Date()) {
  const d = zeitpunkt(wert)
  if (!d) return ''
  const heute = zeitpunkt(jetzt) || new Date()
  if (gleicherTag(d, heute)) return 'Heute'
  const gestern = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() - 1, 12)
  if (gleicherTag(d, gestern)) return 'Gestern'
  // „diese Woche“ = die letzten sieben Tage (kein Wochenwechsel-Effekt am
  // Montag: am Montagmorgen ist der Sonntag „gestern“, der Samstag „Sonntag“ —
  // verwirrend. Die lückenhafte Liste „Heute/Gestern/Wochentag“ gibt es nicht;
  // innerhalb von sieben Tagen steht der Wochentag, darüber das Datum.
  const tage = Math.round((new Date(heute.getFullYear(), heute.getMonth(), heute.getDate(), 12)
    - new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12)) / 86_400_000)
  if (tage >= 0 && tage < 7) return WOCHENTAGE[d.getDay()]
  return `${d.getDate()}. ${MONATE[d.getMonth()]} ${d.getFullYear()}`
}

/** Steht hinter `wert` ein anderer Kalendertag als hinter `vorher`? */
export function neuerTag(wert, vorher) {
  const a = zeitpunkt(wert)
  if (!a) return false
  const b = zeitpunkt(vorher)
  if (!b) return true // erste Nachricht des Verlaufs bekommt ihren Tag
  return !gleicherTag(a, b)
}

/**
 * Verlauf mit Tages-Marken: jede Nachricht bekommt `tag` (die Überschrift), die
 * beim Anzeigen vor ihr steht, oder `null`. Der Verlauf ist alt → neu sortiert.
 */
export function mitTagesmarken(nachrichten, jetzt = new Date()) {
  let vorher = null
  return (Array.isArray(nachrichten) ? nachrichten : []).map((n) => {
    const tag = neuerTag(n?.erstellt_am, vorher) ? tagesUeberschrift(n?.erstellt_am, jetzt) : null
    if (n?.erstellt_am) vorher = n.erstellt_am
    return { ...n, tag }
  })
}

// ── Gesprächsliste ──────────────────────────────────────────────────────────

/** Abschnitt einer Zeile: Gruppen zuerst? Nein — Direkt/Runden existieren in
 *  S1 noch nicht (nur Gruppen und Untergruppen). Zwei Abschnitte, in dieser
 *  Reihenfolge (Entwurf B-desktop: Gruppen, darunter die Untergruppen). */
export const ABSCHNITTE = [
  { id: 'gruppe', label: 'Gruppen' },
  { id: 'untergruppe', label: 'Untergruppen' },
]

/**
 * Abschnitt einer Zeile aus der Server-Antwort (`art`: `gruppe` |
 * `untergruppe`, sonst aus `untergruppe` abgeleitet).
 */
export function abschnittVon(eintrag) {
  if (!eintrag) return 'gruppe'
  if (eintrag.art === 'untergruppe') return 'untergruppe'
  if (eintrag.art === 'gruppe') return 'gruppe'
  return eintrag.untergruppe ? 'untergruppe' : 'gruppe'
}

/**
 * Die sichtbare Zeile einer Server-Zeile.
 *
 * Der Server liefert bei einem NIE geöffneten Gespräch `name: null`
 * (`geoeffnet: false`, Review-Punkt 5 von CHAT-2) — es gibt dann weder
 * Nachricht noch Teilnahme. Die Oberfläche darf den Eintrag trotzdem zeigen
 * (er ist lesbar), muss ihn aber als „noch keine Nachrichten“ zeichnen und
 * beim Tippen erst `gespraech_anlegen` rufen. Hier wird das in EINEN Zustand
 * übersetzt, damit die Seite nicht an drei Stellen dieselbe Bedingung prüft.
 */
export function listenZeile(eintrag, jetzt = new Date()) {
  if (!eintrag || typeof eintrag !== 'object') return null
  const ungelesen = Math.max(0, Number(eintrag.ungelesen) || 0)
  const teilnehmer = Math.max(0, Number(eintrag.teilnehmer) || 0)
  return {
    ...eintrag,
    abschnitt: abschnittVon(eintrag),
    titel: String(eintrag.titel || eintrag.untergruppe || eintrag.gruppe || '').trim(),
    untergruppe: eintrag.untergruppe || null,
    // Ein Eintrag ohne Gesprächszeile ist NICHT antippbar-gesperrt, aber er
    // hat keinen Verlauf: `geoeffnet` sagt, ob `name` schon existiert.
    geoeffnet: Boolean(eintrag.name) && eintrag.geoeffnet !== false,
    stumm: eintrag.stumm === true,
    ungelesen,
    teilnehmer,
    letzte: String(eintrag.letzte_nachricht || '').trim(),
    zeit: listenZeit(eintrag.letzte_am, jetzt),
  }
}

/**
 * Die Liste, gruppiert und sortiert — EINE Quelle für Anzeige und Tests.
 *
 * Sortierung: nach der letzten Nachricht, die neueste oben; ein Gespräch ohne
 * Nachricht steht hinten (der Server sortiert schon so, aber die Oberfläche
 * sortiert selbst, weil ein Polling-Treffer die Reihenfolge ändern kann).
 * Innerhalb derselben Zeit entscheidet der Titel.
 *
 * @returns {Array<{id: string, label: string, eintraege: Array<object>}>}
 *   Leere Abschnitte fallen weg (kein „Untergruppen“-Kopf über nichts).
 */
export function gruppierteListe(gespraeche, jetzt = new Date()) {
  const zeilen = (Array.isArray(gespraeche) ? gespraeche : [])
    .map((e) => listenZeile(e, jetzt))
    .filter(Boolean)
  zeilen.sort((a, b) => {
    const ta = zeitpunkt(a.letzte_am)
    const tb = zeitpunkt(b.letzte_am)
    if (ta && tb && ta.getTime() !== tb.getTime()) return tb.getTime() - ta.getTime()
    if (ta && !tb) return -1
    if (!ta && tb) return 1
    return a.titel.localeCompare(b.titel, 'de')
  })
  return ABSCHNITTE
    .map((abschnitt) => ({
      id: abschnitt.id,
      label: abschnitt.label,
      eintraege: zeilen.filter((z) => z.abschnitt === abschnitt.id),
    }))
    .filter((abschnitt) => abschnitt.eintraege.length > 0)
}

/** Summe aller ungelesenen Nachrichten — der Zähler am Tab „Nachrichten“. */
export function ungelesenSumme(gespraeche) {
  return (Array.isArray(gespraeche) ? gespraeche : [])
    .reduce((summe, e) => summe + Math.max(0, Number(e?.ungelesen) || 0), 0)
}

/** Die Zeile zu einer Kennung (oder `null`). */
export function findeGespraech(gespraeche, name) {
  const kennung = String(name || '')
  if (!kennung) return null
  return (Array.isArray(gespraeche) ? gespraeche : []).find((e) => String(e?.name || '') === kennung) || null
}

/**
 * Schlüssel eines Eintrags, der auch dann eindeutig ist, wenn es (noch) keine
 * Kennung gibt: die Kennung, sonst Gruppe + Untergruppe.
 *
 * Review R1: Ein nie geöffnetes Gespräch hat `name: null` — es wurde bisher
 * über den TITEL adressiert. Titel sind keine Adresse: zwei Untergruppen
 * derselben Gruppe können denselben Anzeigenamen tragen, und der Titel ist
 * frei. Der Schlüssel ist deshalb der ORT (`gruppe` + `untergruppe`), so wie
 * der Server das Gespräch findet (`gespraech_anlegen`).
 */
export function zeilenSchluessel(eintrag) {
  if (!eintrag || typeof eintrag !== 'object') return ''
  const kennung = String(eintrag.name || '').trim()
  if (kennung) return `n:${kennung}`
  const gruppe = String(eintrag.gruppe || '').trim()
  const untergruppe = String(eintrag.untergruppe || '').trim()
  if (!gruppe && !untergruppe) return ''
  return `o:${gruppe}/${untergruppe}`
}

/**
 * Die Adresse eines Eintrags: die Kennung, wenn es sie gibt — sonst der
 * Ortesschlüssel ohne Präfix (`gruppe` bzw. `gruppe/untergruppe`). Die Seite
 * legt das Gespräch beim Öffnen daraus an (`gespraech_anlegen`).
 */
export function zeilenAdresse(eintrag) {
  if (!eintrag) return ''
  const kennung = String(eintrag.name || '').trim()
  if (kennung) return kennung
  const gruppe = String(eintrag.gruppe || '').trim()
  const untergruppe = String(eintrag.untergruppe || '').trim()
  if (untergruppe) return untergruppe
  return gruppe
}

/** Der Eintrag der Liste zu einem Schlüssel (`zeilenSchluessel`) — oder `null`. */
export function eintragZuSchluessel(gespraeche, schluessel) {
  const s = String(schluessel || '')
  if (!s) return null
  return (Array.isArray(gespraeche) ? gespraeche : []).find((e) => zeilenSchluessel(e) === s) || null
}

// ── Verlauf ─────────────────────────────────────────────────────────────────

/**
 * Eine Nachricht, wie die Blase sie braucht.
 *
 * Der Server liefert `text: null` + `geloescht: true` bei einer gelöschten
 * Nachricht; bei einer Moderations-Entfernung trägt die Zeile `entfernt_grund`
 * (CHAT-2-Datenmodell; der Endpunkt liefert den Grund heute NICHT mit — dann
 * steht die neutrale Zeile). Was die Oberfläche daraus macht:
 *   eigene Löschung     „Du hast diese Nachricht gelöscht.“
 *   fremde Löschung     „Von der Leitung entfernt.“ + Grund, wenn bekannt
 *   fremde, gelöschte   „Diese Nachricht wurde gelöscht.“
 * Der Text einer gelöschten Nachricht wird NIE gezeigt (auch wenn er ankäme).
 */
export function verlaufsZeile(n, { ich = '', jetzt = new Date() } = {}) {
  if (!n || typeof n !== 'object') return null
  const eigene = n.eigene === true
    || (Boolean(n.autor_mitglied) && String(n.autor_mitglied) === String(ich || ''))
  const geloescht = n.geloescht === true || n.text === null || n.text === undefined
  const kennung = String(n.name || '')
  const grund = String(n.geloescht_grund || n.entfernt_grund || '').trim()
  return {
    ...n,
    ident: kennung,
    eigene,
    geloescht,
    text: geloescht ? '' : String(n.text ?? ''),
    autor: String(n.autor || '').trim(),
    zeit: uhrzeit(n.erstellt_am, jetzt),
    bearbeitet: n.bearbeitet === true,
    antwortText: String(n.antwort_auf_text || '').trim(),
    reaktionen: Array.isArray(n.reaktionen) ? n.reaktionen : [],
    // F2: die Summe steht NUR an eigenen Nachrichten; an fremden ist sie
    // `null` (der Server schickt sie so, die Oberfläche prüft es nochmal).
    gelesen_von: eigene && Number.isInteger(n.gelesen_von) ? n.gelesen_von : null,
    hinweis: hinweisText({ eigene, geloescht, grund }),
    bearbeitbar: eigene && !geloescht && innerhalbFrist(n.erstellt_am, jetzt),
  }
}

/**
 * Hinweiszeile einer gelöschten Nachricht ('' = keine).
 *
 * Wortwahl (UX2h-Sperrliste): „Moderation“ heißt in der Oberfläche „Prüfen“,
 * die handelnde Stelle „Leitung“ (HV/MV/GL — dieselbe Rolle, die der Rechte-Kern
 * als MODERIEREN führt). Der GRUND steht daneben, sobald der Server ihn liefert.
 */
export function hinweisText({ eigene = false, geloescht = false, grund = '' } = {}) {
  if (!geloescht) return ''
  const g = String(grund || '').trim()
  if (eigene) return 'Du hast diese Nachricht gelöscht.'
  if (g) return `Von der Leitung entfernt: ${g}`
  return 'Diese Nachricht wurde gelöscht.'
}

/**
 * Darf diese Nachricht noch bearbeitet werden? Dieselbe Frist wie im Server
 * (`BEARBEITEN_MINUTEN`, 15 Minuten) — die Oberfläche zeigt den Stift nur so
 * lange, der Server prüft es erneut (er ist die Wahrheit).
 */
export function innerhalbFrist(erstellt_am, jetzt = new Date()) {
  const d = zeitpunkt(erstellt_am)
  const jetztD = zeitpunkt(jetzt)
  if (!d || !jetztD) return false
  const minuten = (jetztD.getTime() - d.getTime()) / 60_000
  return minuten >= 0 && minuten <= BEARBEITEN_MINUTEN
}

/** „gelesen von N“ / „gelesen“ (1:1) — leer, wenn nichts anzuzeigen ist. */
export function lesestandText(nachricht, { direkt = false } = {}) {
  const n = Number(nachricht?.gelesen_von)
  if (!Number.isInteger(n) || n < 0) return ''
  if (n === 0) return ''
  if (direkt) return 'gelesen'
  return `gelesen von ${n}`
}

/**
 * Darf eine Seite als „ältere Seite“ (nachladen nach oben) gelten?
 *
 * MUSS 1: NICHT am Zufall der Kennungen entscheiden. Der Server sagt es
 * (`richtung`): nur `'vor'` ist eine ältere Seite. `'neueste'` (erstes Öffnen)
 * und `'seit'` (Polling) gehören IMMER in die jüngere Richtung — auch wenn die
 * Seite eine bekannte Zeile trägt, auch wenn sie voll ist und sich um eins
 * verschoben hat.
 *
 * Fehlt `richtung` (alte Antwort, handgebauter Aufruf), entscheidet die
 * Kennung: trägt die Seite die erste bekannte Zeile, ist sie die jüngere.
 * Sonst bleibt sie älter. Die Absicht des Aufrufers hat KEIN Gewicht — zwei
 * Wahrheiten über dieselbe Seite liefen auseinander.
 *
 * @param {object} antwort `{richtung, nachrichten}` des Servers
 * @param {Array<object>} vorher bekannter Verlauf (alt → neu)
 * @returns {boolean}
 */
export function istAeltereSeite(antwort, vorher = []) {
  const richtung = String(antwort?.richtung || '').trim()
  if (richtung) return richtung === 'vor'
  const seite = Array.isArray(antwort?.nachrichten) ? antwort.nachrichten : []
  const bekannt = Array.isArray(vorher) ? vorher : []
  if (!seite.length || !bekannt.length) return false
  return String(seite[0]?.name || '') !== String(bekannt[0]?.name || bekannt[0]?.ident || '')
}

/**
 * Bringt diese Zeile gegenüber dem bisherigen Stand sichtbar etwas Neues?
 *
 * Verglichen werden die Felder, die die Oberfläche zeigt und die durch
 * Bearbeitung, Löschung, Reaktionen oder den Lesestand wechseln können — nicht
 * die Uhrzeit-Ableitungen (`zeit`, `hinweis`, `bearbeitbar`), die aus
 * `erstellt_am` und der laufenden Uhr folgen und sich deshalb auch ohne
 * Serveränderung verschieben dürfen.
 */
export function zeileGleich(a, b) {
  if (!a || !b) return false
  if (String(a.text ?? '') !== String(b.text ?? '')) return false
  if (Boolean(a.geloescht) !== Boolean(b.geloescht)) return false
  if (Boolean(a.bearbeitet) !== Boolean(b.bearbeitet)) return false
  if (String(a.geloescht_grund ?? '') !== String(b.geloescht_grund ?? '')) return false
  if (String(a.antwort_auf ?? '') !== String(b.antwort_auf ?? '')) return false
  if (Number(a.gelesen_von ?? -1) !== Number(b.gelesen_von ?? -1)) return false
  return reaktionenGleich(a.reaktionen, b.reaktionen)
}

/** Reaktionen als vergleichbare Liste (Emoji → Namen, sortiert). */
function reaktionenGleich(a, b) {
  const form = (liste) => (Array.isArray(liste) ? liste : [])
    .map((r) => `${String(r?.reaktion ?? r?.emoji ?? '')}:${String(r?.anzahl ?? r?.count ?? '')}`)
    .sort()
    .join('|')
  return form(a) === form(b)
}

/**
 * Eine Seite des Verlaufs (Antwort von `chat.verlauf`) in den Zustand bringen,
 * den die Seite hält.
 *
 * @param {object} antwort  `{richtung, nachrichten, vor, seit}` des Servers
 * @param {{alt?: Array<object>, ich?: string, jetzt?: Date}} lage
 *   `alt` ist der bisherige Verlauf — beim Nachladen nach OBEN wird er ANGEHÄNGT
 *   (ältere Seite davor), in der jüngeren Richtung werden bekannte Zeilen
 *   ERSETZT (Bearbeitung, Löschung, Reaktionen) und neue hinten angehängt.
 * @returns {{nachrichten: Array<object>, vor: string|null, seit: string|null,
 *            aelterMoeglich: boolean|null, neuHinzugefuegt: number,
 *            aktualisiert: number}} `aktualisiert` zählt nur bekannte Zeilen,
 *            deren Inhalt sich wirklich geändert hat (siehe `zeileGleich`) —
 *            unveränderte Zeilen einer vollen Seite zählen nicht mit.
 */
export function seiteEinordnen(antwort, { alt = [], ich = '', jetzt = new Date() } = {}) {
  const roh = Array.isArray(antwort?.nachrichten) ? antwort.nachrichten : []
  const seite = roh.map((n) => verlaufsZeile(n, { ich, jetzt })).filter(Boolean)
  // Der bisherige Verlauf ist schon gedeutet (kommt aus dieser Funktion) —
  // fremde/rohe Zeilen werden nachgedeutet, damit `ident` überall steht.
  const vorher = (Array.isArray(alt) ? alt : [])
    .map((n) => (n && n.ident !== undefined ? n : verlaufsZeile(n, { ich, jetzt })))
    .filter(Boolean)
  // MUSS 1: Die RICHTUNG entscheidet der Server (`richtung`) — nicht der
  // Zufall der Kennungen. Nur `'vor'` ist eine ältere Seite; `'neueste'`
  // (erstes Öffnen) und `'seit'` (Poll) sind IMMER die jüngere Richtung, auch
  // wenn die Seite eine bekannte Zeile trägt und auch wenn sie voll ist und
  // sich durch neue Nachrichten um eins verschoben hat.
  let zusammen
  let neuHinzugefuegt = 0
  /** Wie viele BEKANNTE Zeilen die Seite auf einen neuen Stand gebracht hat. */
  let aktualisiert = 0
  if (!vorher.length) {
    zusammen = seite
    neuHinzugefuegt = seite.length
  } else if (istAeltereSeite(antwort, vorher)) {
    // Ältere Seite (nachladen nach oben): davorhängen. Doppelte an der Naht
    // fallen weg — die Kennung entscheidet, nicht die Anzahl.
    const bekannt = new Set(vorher.map((n) => n.ident))
    zusammen = [...seite.filter((n) => !bekannt.has(n.ident)), ...vorher]
  } else {
    // Jüngere Richtung (neueste Seite und Polling): bekannte Zeilen ERSETZEN,
    // unbekannte hinten anhängen. Gezählt wird NUR, was wirklich NEU ist — ein
    // Austausch (bearbeitet, gelöscht, Reaktion) ist kein neuer Beitrag und
    // darf das Nachscrollen nicht auslösen; `aktualisiert` sagt dem Aufrufer,
    // dass sich bekannte Zeilen geändert haben — es zählt nur die, deren
    // Inhalt sich WIRKLICH unterscheidet (nicht jede mitgelieferte Zeile).
    const index = new Map(vorher.map((n, i) => [n.ident, i]))
    const anhaengen = []
    for (const n of seite) {
      if (index.has(n.ident)) {
        const stelle = index.get(n.ident)
        if (zeileGleich(vorher[stelle], n)) continue
        vorher[stelle] = n
        aktualisiert += 1
      } else {
        anhaengen.push(n)
        neuHinzugefuegt += 1
      }
    }
    zusammen = [...vorher, ...anhaengen]
  }
  // Endgültig nach Zeit sortieren (die Seiten sind schon sortiert; das hier
  // fängt gleiche Zeitstempel ab, damit „vor“/„seit“ stimmen).
  zusammen.sort((a, b) => {
    const ta = zeitpunkt(a.erstellt_am)
    const tb = zeitpunkt(b.erstellt_am)
    if (!ta || !tb) return 0
    if (ta.getTime() !== tb.getTime()) return ta.getTime() - tb.getTime()
    return a.ident < b.ident ? -1 : a.ident > b.ident ? 1 : 0
  })
  const erste = zusammen[0]?.ident || null
  return {
    nachrichten: zusammen,
    vor: erste,
    seit: zusammen[zusammen.length - 1]?.ident || null,
    // „nachladen nach oben“ ist NUR möglich, wenn eine ÄLTERE Seite kam und
    // diese VOLL war (`length >= SEITE`): eine kurze Seite heißt „der Anfang
    // ist erreicht“. Die neueste Seite und der Poll sagen darüber nichts aus —
    // `null` = keine Aussage, die Seite behält ihren Stand (`aelterStand`),
    // sonst schaltete jeder Poll das Nachladen wieder an.
    aelterMoeglich: istAeltereSeite(antwort, vorher) ? seite.length >= SEITE : null,
    neuHinzugefuegt,
    aktualisiert,
  }
}

/**
 * Was danach für „ältere Nachrichten laden“ gilt: nur ein VOLLER älterer Abruf
 * hält es an; alles andere (`null`) lässt den bisherigen Stand stehen.
 *
 * @param {boolean} bisher
 * @param {boolean|null} aussage Ergebnis von `seiteEinordnen(...).aelterMoeglich`
 */
export function aelterStand(bisher, aussage) {
  if (aussage === null || aussage === undefined) return bisher === true
  return aussage === true
}

// ── Lesestand beim Poll ─────────────────────────────────────────────────────

/**
 * Muss nach einem stillen Abruf der Lesestand gesetzt werden? (MUSS 2.)
 *
 * Der Verlauf gilt als gelesen, sobald er SICHTBAR ist — also nur, wenn der
 * Tab sichtbar ist. Gemeldet wird, wenn
 *   * fremde Nachrichten dazugekommen sind (`neueFremde > 0`), oder
 *   * das Gespräch laut Liste noch ungelesene trägt (`ungelesen > 0`).
 *
 * Eigene Nachrichten zählen nicht: wer selbst schreibt, hat nichts zu lesen —
 * sonst liefe bei jedem Poll ein `lesestand_setzen` hinterher.
 */
export function lesestandFaellig({ neuHinzugefuegt = 0, neueFremde = null, ungelesen = 0, sichtbar = true } = {}) {
  if (!sichtbar) return false
  // `neueFremde` ist die genauere Aussage; fehlt sie (`null`), zählt jede neue
  // Zeile — lieber einmal zu viel melden als ungelesen stehen lassen. Eigene
  // Nachrichten erreichen diesen Zweig im Betrieb nie (`fremdeNeue` zählt sie
  // nicht mit).
  if (neueFremde === null || neueFremde === undefined) {
    if (Number(neuHinzugefuegt) > 0) return true
  } else if (Number(neueFremde) > 0) {
    return true
  }
  return Number(ungelesen) > 0
}

/** Wie viele der neu hinzugekommenen Nachrichten sind fremd (nicht `eigene`)? */
export function fremdeNeue(vorher, nachher) {
  const bekannt = new Set((Array.isArray(vorher) ? vorher : []).map((n) => n.ident))
  return (Array.isArray(nachher) ? nachher : [])
    .filter((n) => n && !bekannt.has(n.ident) && n.eigene !== true).length
}

// ── Eingabe ─────────────────────────────────────────────────────────────────

/**
 * Prüfung eines Nachrichtentextes VOR dem Senden. Dieselben Regeln wie im
 * Server (`_pruefe_text`): am Rand nicht leer, höchstens `NACHRICHT_MAX`
 * ZEICHEN, Absätze bleiben erhalten (der Text wird NICHT getrimmt).
 *
 * @returns {{ok: boolean, text: string, fehler: string}}
 */
export function pruefeText(text) {
  const wert = text === null || text === undefined ? '' : String(text)
  if (!wert.trim()) return { ok: false, text: wert, fehler: 'Bitte einen Text eingeben.' }
  if (wert.length > NACHRICHT_MAX) {
    return {
      ok: false,
      text: wert,
      fehler: `Eine Nachricht darf höchstens ${NACHRICHT_MAX} Zeichen lang sein `
        + `(eingegeben: ${wert.length}).`,
    }
  }
  return { ok: true, text: wert, fehler: '' }
}

/**
 * Was ENTER im Eingabefeld tut (Karte: „Enter sendet, Shift+Enter
 * Zeilenumbruch“): `senden` | `umbruch`.
 */
export function tasteImFeld({ key, shiftKey = false, isComposing = false } = {}) {
  if (key !== 'Enter') return 'sonst'
  if (isComposing) return 'sonst' // IME (chinesisch/japanisch) nicht stören
  return shiftKey ? 'umbruch' : 'senden'
}

/** Vorlesetext des Sende-Knopfes (N8: beschriften statt nur Symbol). */
export const SENDEN_TEXT = 'Nachricht senden'

/** Beschriftung des Eingabefelds. */
export function eingabePlatzhalter(titel) {
  const t = String(titel || '').trim()
  return t ? `Nachricht an ${t} …` : 'Nachricht schreiben …'
}

// ── Aktualisierung (Polling) ────────────────────────────────────────────────

/**
 * Darf JETZT abgefragt werden? Nur, wenn
 *   * der Tab sichtbar ist (`document.hidden` falsch) — ein Hintergrund-Tab
 *     fragt nicht (Konzept 3.1: das Grundpolling dient der Anzeige, nicht der
 *     Zustellung),
 *   * gerade kein Abruf läuft (kein Stau: ein langsamer Server erzeugt sonst
 *     eine Warteschlange von Anfragen),
 *   * nicht schon wieder eins fällig ist (`letzterAbruf`; ein Tab, der lange
 *     verborgen war, holt mit EINEM Abruf nach, nicht mit zwanzig).
 */
export function darfAbfragen({ sichtbar = true, laeuft = false, letzterAbruf = 0, jetzt = Date.now(), takt = TAKT_MS } = {}) {
  if (!sichtbar) return false
  if (laeuft) return false
  const letzter = Number(letzterAbruf) || 0
  if (!letzter) return true
  return Number(jetzt) - letzter >= takt
}

/**
 * Wartezeit bis zum nächsten Versuch nach einem Fehler — Verdopplung bis zur
 * Obergrenze (Review R1: „Backoff nach Fehlern (verdoppeln bis 60 s)“).
 *
 * Ein Server, der gerade nicht kann (500, Netz weg, 503 hinter dem Proxy),
 * wird von einem 10-Sekunden-Polling sonst im Minutentakt beworfen; nach einem
 * Fehler verdoppelt sich die Wartezeit mit jedem weiteren Fehlschlag —
 * beginnend beim GRUNDTAKT (10 s, 20 s, 40 s, dann 60 s), höchstens
 * `BACKOFF_MAX_MS`. Der ERSTE Erfolg setzt zurück (`backoffMs(0)` → 0).
 *
 * @param {number} fehlschlag  wie viele Fehler in Folge (0 = keiner)
 * @param {number} takt        Grundtakt (Standard `TAKT_MS`)
 */
export function backoffMs(fehlschlag, takt = TAKT_MS) {
  const n = Math.max(0, Math.trunc(Number(fehlschlag) || 0))
  if (!n) return 0
  return Math.min(takt * 2 ** Math.min(n, 6), BACKOFF_MAX_MS)
}

/** Obergrenze des Backoffs: eine Minute. */
export const BACKOFF_MAX_MS = 60_000

/**
 * Der Takt der Seite als kleiner Gegenstand: er kennt den EINEN Timer, den
 * EINEN Beobachter der Sichtbarkeit und den Lauf-Zustand. `starten` und
 * `anhalten` sind idempotent — zweimal starten ergibt nicht zwei Timer.
 *
 * WARUM HIER UND NICHT IN DER SEITE: „Timer beim Verlassen aufräumen“ ist
 * genau die Regel, die man in einer Komponente vergisst. Hier ist sie eine
 * Zusicherung, die der Test ohne Browser prüfen kann.
 *
 * MUSS 3 (Timer-Leck): Nach `anhalten` ist der Takt GESTOPPT — ein spät
 * eintreffendes `starten` (Seite wartet auf eine Antwort, ist aber schon
 * abgebaut) öffnet KEINEN zweiten Timer. Nur `starten({ wieder: true })` weckt
 * ihn ausdrücklich wieder (Neustart). Jeder Lauf kann eine neue Wartezeit
 * melden (`rueckmeldung.dauer` — der Backoff nach einem Fehler); geplant wird
 * immer aus der EINEN Stelle hier.
 *
 * Die Umgebung wird hineingegeben (Timer, Sichtbarkeit, Uhr) — im Betrieb sind
 * das `setTimeout`, `document.hidden`/`visibilitychange` und `Date.now`, im
 * Test Attrappen. Kein Aufruf von außen, keine zweite Wahrheit.
 *
 * @param {{takt?: number,
 *          jetzt?: () => number,
 *          timer?: (fn: () => void, ms: number) => any,
 *          timerAus?: (id: any) => void,
 *          sichtbar?: () => boolean,
 *          sichtbarkeitBeobachten?: (fn: () => void) => (() => void),
 *          abfragen: () => any}} optionen
 */
export function taktGeber({
  takt = TAKT_MS,
  jetzt = () => Date.now(),
  timer = (fn, ms) => setTimeout(fn, ms),
  timerAus = (id) => clearTimeout(id),
  sichtbar = () => true,
  sichtbarkeitBeobachten = null,
  abfragen = () => {},
} = {}) {
  let laufend = null
  let abmelden = null
  let laeuft = false
  let letzterAbruf = 0
  let letzterLauf = null
  let anlaeufe = 0
  let wartezeit = takt
  let gestoppt = false

  /** Einen Lauf planen — nur wenn er laufen soll und sichtbar ist. */
  function planen(ms = wartezeit) {
    if (gestoppt || laufend) return
    if (!sichtbar()) return // verborgen: der Beobachter weckt uns
    laufend = timer(() => takt_(jetzt()), Math.max(0, Number(ms) || 0))
  }

  /**
   * Ein Takt. `augenblick` ist der Zeitpunkt des Takts — im Betrieb die Uhr,
   * im Test eine feste Zahl.
   */
  function takt_(augenblick = jetzt()) {
    laufend = null
    if (gestoppt) return false
    if (!darfAbfragen({ sichtbar: sichtbar(), laeuft, letzterAbruf, jetzt: augenblick, takt })) {
      planen()
      return false
    }
    laeuft = true
    letzterAbruf = augenblick
    anlaeufe += 1
    letzterLauf = augenblick
    let antwort
    try {
      antwort = abfragen()
    } catch {
      laeuft = false
      planen()
      return false
    }
    if (antwort && typeof antwort.then === 'function') {
      // Fehler gehören der Abfrage (sie zeigt sie an) — hier darf keine
      // unbehandelte Ablehnung entstehen. Meldet der Lauf eine Wartezeit
      // (`{dauer}` — Backoff), gilt sie für den nächsten Termin.
      antwort
        .then((rueckmeldung) => {
          const dauer = Number(rueckmeldung?.dauer)
          if (Number.isFinite(dauer) && dauer >= 0) wartezeit = dauer
        }, () => {})
        .finally(() => {
          laeuft = false
          planen()
        })
    } else {
      laeuft = false
      planen()
    }
    return true
  }

  /** Start: Timer setzen und die Sichtbarkeit beobachten (idempotent).
   *  Nach `anhalten` bleibt er aus — außer mit `{ wieder: true }`. */
  function starten({ wieder = false } = {}) {
    if (gestoppt && !wieder) return null
    gestoppt = false
    planen()
    if (!abmelden && typeof sichtbarkeitBeobachten === 'function') {
      abmelden = sichtbarkeitBeobachten(() => {
        // Wieder sichtbar: sofort holen, was verpasst wurde (ein Abruf, nicht
        // der ganze Rückstand). Verborgen: nichts tun — der Takt selbst fragt
        // wegen `darfAbfragen` nicht; der geplante Termin entfällt.
        if (sichtbar()) {
          planen(0)
        } else if (laufend) {
          timerAus(laufend)
          laufend = null
        }
      })
    }
    return laufend
  }

  /** Halt: EIN Timer weg, EIN Beobachter abgemeldet, ein laufender Abruf
   *  darf zu Ende laufen (sein Ergebnis ändert dann nichts mehr). Ein danach
   *  eintreffendes `starten()` bleibt wirkungslos (`gestoppt`). */
  function anhalten() {
    gestoppt = true
    if (laufend) {
      timerAus(laufend)
      laufend = null
    }
    if (typeof abmelden === 'function') {
      try { abmelden() } catch { /* ein kaputter Beobachter darf nicht blocken */ }
    }
    abmelden = null
    laeuft = false
  }

  return {
    starten,
    anhalten,
    takt: takt_,
    istGestartet: () => laufend !== null,
    istGestoppt: () => gestoppt,
    // Nur für den Test: der Stand von innen, ohne ihn zu erraten.
    stand: () => ({ letzterAbruf, laeuft, anlaeufe, letzterLauf, gestoppt, wartezeit }),
  }
}

// ── Zustände der Fläche ─────────────────────────────────────────────────────

/**
 * Was die Seite in einer Fehlerlage zeigt.
 *
 * 403 der Chat-Endpunkte heißt OHNE Inhalt „kein Zugriff“ (Server: `_h()`)
 * — das ist KEIN Fehler des Aufrufs, sondern eine Auskunft über Rechte. Sie
 * bekommt einen eigenen Satz; „Modul aus“ erkennt die Oberfläche daran, dass
 * die Liste leer ist UND das Modul im Boot fehlt (`modulChatErlaubt` false) —
 * dann steht dort ein Hinweis, keine leere Liste.
 */
export function fehlerZustand(fehler) {
  const status = Number(fehler?.status) || 0
  const art = String(fehler?.exc_type || fehler?.excType || '')
  if (status === 403 || art === 'PermissionError') {
    return {
      art: 'kein-zugriff',
      titel: 'Kein Zugriff auf die Nachrichten',
      text: 'Du bist nicht Mitglied eines Gesprächs mit Chat, oder der Chat ist in deinen Gruppen nicht eingeschaltet. '
        + 'Wende dich an die Leitung deiner Gruppe.',
    }
  }
  if (status === 404 || art === 'DoesNotExistError') {
    return {
      art: 'weg',
      titel: 'Dieses Gespräch gibt es nicht',
      text: 'Vielleicht wurde es gelöscht. Wähle ein anderes Gespräch aus der Liste.',
    }
  }
  if (status === 417 || status === 422 || status === 400) {
    return {
      art: 'eingabe',
      titel: 'Das hat nicht geklappt',
      text: String(fehler?.message || '').trim() || 'Bitte prüfe deine Eingabe und versuche es noch einmal.',
    }
  }
  return null
}

/** Hinweis, wenn das Modul `chat` für diese Sitzung aus ist. */
export const MODUL_AUS = {
  titel: 'Nachrichten sind nicht eingeschaltet',
  text: 'In deinen Gruppen ist der Chat nicht freigegeben, oder du bist noch keinem Gespräch zugeordnet. '
    + 'Die Leitung deiner Gruppe kann den Chat einschalten.',
}

/** Leerzustand der Liste. */
export const LISTE_LEER = {
  titel: 'Noch keine Gespräche',
  text: 'Sobald der Chat in einer deiner Gruppen eingeschaltet ist, steht das Gespräch hier.',
}

/** Leerzustand im Verlauf (Gespräch ohne Nachricht). */
export const VERLAUF_LEER = {
  titel: 'Noch keine Nachrichten',
  text: 'Schreib die erste Nachricht — alle im Gespräch sehen sie.',
}
