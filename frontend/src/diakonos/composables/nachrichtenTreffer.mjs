/**
 * CHAT-11b — die Regeln der Suche IN Nachrichten, ohne DOM und ohne Vue.
 *
 * Der Server (`api/chat.py` → `nachrichten_suchen`, Karte CHAT-11a) antwortet:
 *
 *   { treffer: [ { gespraech: {name, art, titel},
 *                  nachricht: <kennung>, zeit: <ISO>, absender: <Anzeigename>,
 *                  ausschnitt: {vor, treffer, nach} } … ],
 *     mehr: <bool>, vor: <kennung|None>, limit: <Zahl> }
 *
 * Der Ausschnitt kommt als DREI TEILE reiner Text — es gibt KEINE Offsets
 * (Review R1/6 des Backends: JavaScript zählt UTF-16-Einheiten, Python
 * Codepoints; ein Emoji vor dem Treffer hätte jede Offset-Markierung
 * verschoben). Die Oberfläche setzt die drei Teile zusammen und hebt
 * `treffer` hervor — über Vue-Textinterpolation, KEIN `v-html`.
 *
 * Was hier steht, ist alles, was man ohne Browser prüfen kann:
 *   * wann gefragt wird (ab `SUCHE_MIN_ZEICHEN` Zeichen, entprellt),
 *   * welche Antwort zählt (`darfFragen` — überholte Antworten fallen weg,
 *     laufende Abrufe werden abgebrochen),
 *   * wie aus der Serverantwort Zeilen werden (Titel, Absender, Zeit,
 *     Ausschnitt-Stücke),
 *   * das Blättern über `vor` und wann „mehr“ gilt,
 *   * der Sprung in den Verlauf: wie viele Seiten nachgeladen werden
 *     (höchstens `SPRUNG_MAX_SEITEN`) und was passiert, wenn die Nachricht
 *     nicht mehr da ist.
 *
 * WAS HIER NICHT STEHT: kein Netzaufruf (der Aufrufer gibt `holen` hinein),
 * kein Timer (den stellt `entpreller` aus `nachrichtenSuche.mjs`), keine
 * Farben, kein Vokabular für die Markierung (das ist Gestaltung).
 */

import { listenZeit } from './nachrichtenLogik.mjs'
import { SUCHE_MIN_ZEICHEN, darfPersonenFragen, istAktuell } from './nachrichtenSuche.mjs'

// ── Grenzen und Texte (je EINE Stelle) ──────────────────────────────────────

/**
 * Kürzeste Eingabe. Dieselbe Zahl wie beim Server (`_verlauf_begriff`: unter
 * 2 Zeichen antwortet er leer) und wie die vorhandene Suche — die Oberfläche
 * fragt darunter gar nicht erst.
 */
export const TREFFER_MIN_ZEICHEN = SUCHE_MIN_ZEICHEN

/** Überschrift des dritten Abschnitts in der Suche (Karte Punkt 1). */
export const ABSCHNITT_NACHRICHTEN = 'In Nachrichten'

/** Die eine Zeile, wenn die Suche in Nachrichten nichts findet (Karte
 *  Punkt 1: „Keine Treffer: ein ruhiger Satz“). */
export const KEINE_TREFFER_TEXT = 'Keine Nachricht enthält diesen Begriff.'

/** Ruhiger Hinweis, wenn die Nachricht eines Treffers nicht mehr existiert
 *  (Karte Punkt 2: gelöscht). */
export const WEG_TEXT = 'Diese Nachricht gibt es nicht mehr.'

/** Höchstens so viele Seiten lädt der Sprung nach (Karte Punkt 2). */
export const SPRUNG_MAX_SEITEN = 10

/**
 * CHAT-11b-2: Eigene Obergrenze (ms) für das WARTEN AUF DIE ADRESSE
 * (`sprungBereit`/`wartetAufAdresse`) — der `hashchange` des Browsers kommt als
 * eigener Task, aber wenn er nie kommt, darf der Sprung nicht hängen. Ein
 * Abbruch über diese Frist ist STILL (kein Hinweis), wie ein Gesprächswechsel.
 */
export const SPRUNG_ADRESSE_MS = 5000

/** Platzhalter des Suchfelds im Gesprächskopf (Karte Punkt 3). */
export const GESPRAECH_PLATZHALTER = 'In diesem Gespräch suchen'

/** Knopfbeschriftung: die nächste Seite Treffer. */
export const MEHR_TEXT = 'Weitere Treffer'

/** Der Satz über der Liste, wenn es Treffer gibt — die Zahl sagt die
 *  Vorlesehilfe (`aria-live`), hier steht die sichtbare Fassung. */
export function trefferzahlText(anzahl) {
  const n = Math.max(0, Number(anzahl) || 0)
  if (n === 0) return ''
  return n === 1 ? '1 Treffer' : `${n} Treffer`
}

/** Die ANSAGE der Trefferzahl (`aria-live`, Karte „Prinzipien“). Leer, solange
 *  nichts zu sagen ist — eine Ansage über 0 Treffer stünde zweimal da
 *  (einmal als Satz). */
export function trefferAnsage({ anzahl = 0, laedt = false, fehler = '' } = {}) {
  if (String(fehler || '').trim()) return 'Die Suche in den Nachrichten hat nicht geklappt.'
  if (laedt) return 'Nachrichten werden gesucht …'
  const n = Math.max(0, Number(anzahl) || 0)
  if (!n) return ''
  return n === 1 ? '1 Treffer in den Nachrichten' : `${n} Treffer in den Nachrichten`
}

// ── Wann gefragt wird ───────────────────────────────────────────────────────

/**
 * Darf für diese Eingabe gefragt werden? (ab `TREFFER_MIN_ZEICHEN` Zeichen,
 * gezählt nach dem Trimmen.) Dieselbe Regel wie bei Personen und Gesprächen —
 * eine Zahl, eine Prüfung.
 */
export function darfTrefferFragen(wert) {
  return darfPersonenFragen(wert)
}

/**
 * Darf DIESE Seite noch angezeigt werden?
 *
 * Es gilt die Regel der vorhandenen Suche („nur die Antwort zur letzten
 * Eingabe zählt“), aber mit einem ZUSATZ: Ein leerer Begriff ist keine Frage
 * — `istAktuell` antwortet auf `''` immer `false`, und eine Antwort auf den
 * letzten (nicht mehr vorhandenen) Begriff fiele damit durch, obwohl niemand
 * etwas anderes gefragt hat.
 *
 * Verglichen wird FALT-GLEICH („Anna “ und „anna“ sind dieselbe Frage). Das
 * betrifft NUR diese Prüfung im Browser — was an den Server geht, steht in
 * `frageParameter` und wird NICHT gefaltet.
 */
export function darfFragen(gefragt, eingabe) {
  if (String(eingabe ?? '').trim() === '') return true
  return istAktuell(gefragt, eingabe)
}

/**
 * Die laufende Nummer, die eine Antwort zählen lässt (Karte Punkt 1:
 * „`darfFragen`: Eine überholte Antwort wird verworfen, ein laufender Abruf
 * wird abgebrochen“).
 *
 * Jeder neue Abruf erhöht die Nummer; ein Aufrufer merkt sich seine Nummer
 * und schreibt nur, wenn sie noch die jüngste ist. `abbrechen()` macht ALLE
 * laufenden Abrufe ungültig, ohne einen neuen zu starten (Feld geleert,
 * Gespräch gewechselt, Seite abgebaut). Den Abbruch selbst meldet der
 * Aufrufer seinem Transport (`signal`) — hier wird nichts abgebrochen, was
 * dieser Baustein nicht kennt.
 *
 * @returns {{ neu: () => number, gilt: (nummer: number) => boolean,
 *             abbrechen: () => void, stand: () => number }}
 */
export function laufNummer() {
  let juengste = 0
  return {
    neu() {
      juengste += 1
      return juengste
    },
    gilt(nummer) {
      return Number(nummer) === juengste
    },
    abbrechen() {
      juengste += 1
    },
    stand: () => juengste,
  }
}

/**
 * Parameter EINES Abrufs beim Server. `gespraech` nur, wenn wirklich eines
 * gefragt ist (der Server liest ein leeres Feld als „alle“) — und `vor` nur
 * beim Blättern.
 *
 * Der Begriff geht NUR GETRIMMT hinaus — NICHT gefaltet, NICHT
 * kleingeschrieben (Review R1/2). Der Server nimmt ihn wörtlich
 * (`_verlauf_begriff`: „NICHT gefaltet und NICHT kleingeschrieben“) und baut
 * daraus `websearch_to_tsquery('german', q)`, das selbst stammt und Umlaute
 * kennt. Ein gefaltetes „mueller“ fände auf PostgreSQL kein „Müller“ — die
 * Umlaut-Faltung täte hier also das Gegenteil von helfen. Dieselbe Zeichen-
 * kette, die im Feld steht, geht hinaus.
 */
export function frageParameter(q, { gespraech = '', vor = '' } = {}) {
  const parameter = { q: String(q ?? '').trim() }
  const g = String(gespraech || '').trim()
  const v = String(vor || '').trim()
  if (g) parameter.gespraech = g
  if (v) parameter.vor = v
  return parameter
}

// ── Aus der Antwort werden Zeilen ───────────────────────────────────────────

/**
 * Ein Treffer als Zeile für die Liste. `null`, wenn der Server keine
 * Nachrichten-Kennung geliefert hat — ohne sie gäbe es kein Ziel, und ein
 * geratenes Ziel ist schlimmer als keine Zeile.
 *
 * Die Zeit kommt aus `listenZeit` — DIESELBE relative Angabe wie in der
 * Gesprächsliste (heute „09:12“, gestern „gestern“, älter „18.11.“). Der
 * Server schickt `zeit` als ISO-Zeitstempel in UTC; `listenZeit` rechnet ihn
 * über `wandZeit` in Wandzeit um.
 */
export function trefferZeile(t, jetzt = new Date()) {
  if (!t || typeof t !== 'object') return null
  const nachricht = String(t.nachricht || '').trim()
  if (!nachricht) return null
  const kopf = t.gespraech && typeof t.gespraech === 'object' ? t.gespraech : {}
  const titel = String(kopf.titel || '').trim()
  return {
    nachricht,
    gespraech: String(kopf.name || '').trim(),
    art: String(kopf.art || '').trim(),
    titel,
    absender: String(t.absender || '').trim(),
    zeit: listenZeit(t.zeit, jetzt),
    teile: ausschnittTeile(t.ausschnitt),
  }
}

/**
 * Der Ausschnitt in seine drei Stücke — REINER TEXT.
 *
 * Nichts wird hier entschärft und nichts erkannt: `<script>` im Text ist
 * TEXT und bleibt Text, weil die Vorlage ihn interpoliert (`{{ }}`) und nicht
 * als HTML einsetzt. Fehlt ein Teil, ist er leer (kein „undefined“ in der
 * Zeile); fehlt der ganze Ausschnitt, bleibt `treffer` leer und `vor` trägt
 * den Rest — die Vorlage zeigt dann eben keinen hervorgehobenen Teil.
 */
export function ausschnittTeile(ausschnitt) {
  const a = ausschnitt && typeof ausschnitt === 'object' ? ausschnitt : {}
  return {
    vor: String(a.vor ?? ''),
    treffer: String(a.treffer ?? ''),
    nach: String(a.nach ?? ''),
  }
}

/** Die zusammengesetzte Zeile des Ausschnitts (nur für Textprüfungen/Tests). */
export function ausschnittText(teile) {
  const t = teile && typeof teile === 'object' ? teile : {}
  return String(t.vor ?? '') + String(t.treffer ?? '') + String(t.nach ?? '')
}

/**
 * Die ganzen Zeilen einer Antwort — und ob es danach weitergeht.
 *
 * `mehr` gilt nur, wenn der Server es sagt UND ein Anker (`vor`) da ist: ohne
 * Anker könnte „Weitere Treffer“ nichts laden, dann steht der Knopf nicht da.
 */
export function trefferAusAntwort(antwort, jetzt = new Date()) {
  const roh = Array.isArray(antwort?.treffer) ? antwort.treffer : []
  const zeilen = roh.map((t) => trefferZeile(t, jetzt)).filter(Boolean)
  const vor = String(antwort?.vor || '').trim()
  return { zeilen, mehr: antwort?.mehr === true && Boolean(vor), vor }
}

/**
 * Eine weitere Seite an die vorhandenen Zeilen hängen — ohne Doppelungen.
 *
 * Die Seiten sind per Keyset geschnitten (`(erstellt_am, name) < anker`), eine
 * Zeile kann also nicht zweimal kommen; der Vergleich über die Kennung steht
 * trotzdem hier, weil ein doppelter Schlüssel in einer `v-for`-Liste ein
 * Vue-Fehler ist.
 */
export function seiteAnhaengen(bisher, neu) {
  const alt = Array.isArray(bisher) ? bisher : []
  const gesehen = new Set(alt.map((z) => String(z?.nachricht || '')))
  const dazu = (Array.isArray(neu) ? neu : []).filter((z) => z && !gesehen.has(String(z.nachricht)))
  return [...alt, ...dazu]
}

/**
 * Gemeinsame Kennung und Begriff für eine Zeile — der Schlüssel, mit dem die
 * Leiste „welcher Eintrag ist gerade gewählt“ arbeitet.
 */
export function zeilenKennung(zeile) {
  return String(zeile?.nachricht || '')
}

// ── Sprung in den Verlauf ───────────────────────────────────────────────────

/**
 * Der Sprung zu einer Nachricht — EIN Weg, ohne zweiten.
 *
 * Der Weg ist der der Erwähnungs-Glocke (`glockenziele.mjs`, CHAT-9b):
 * `chat.nachricht_kontext(nachricht)` sagt, in WELCHEM Gespräch die Nachricht
 * steht, und liefert `null`-artige/fehlende Antworten, wenn sie unbekannt ist,
 * man sie nicht lesen darf oder sie gelöscht wurde. Danach öffnet die Seite
 * das Gespräch über die Adresse (`#/nachrichten/<kennung>`) — dieselbe
 * Adresse, die auch ein Klick auf die Liste setzt.
 *
 * Hier wird NICHTS nachgebaut: `kontext` ist `erwaehnungZiel`-artig, also
 * irgendeine Funktion `(nachricht) => Promise<{gespraech}|…>`. Was der Sprung
 * ZUSÄTZLICH braucht, ist die Kennung selbst — sie steht im Ziel:
 *
 *   { art: 'gespraech', gespraech, nachricht }  → Gespräch öffnen, zur
 *                                                  Nachricht springen
 *   { art: 'weg' }                              → Gespräch öffnen (wenn
 *                                                  bekannt), Hinweis zeigen
 *   { art: 'nichts' }                           → Gespräch unbekannt: der
 *                                                  Bereich „Nachrichten“
 *
 * @param {string} nachricht Kennung der Nachricht
 * @param {(nachricht: string) => Promise<object|null>} kontext
 * @param {(gespraech: string) => string} adresse die Adressfunktion der Seite
 */
export async function sprungZiel(nachricht, kontext, adresse) {
  const kennung = String(nachricht || '').trim()
  if (!kennung) return { art: 'nichts' }
  let antwort = null
  try {
    antwort = await kontext(kennung)
  } catch {
    // Fehler und neutrale Antwort sind dasselbe: keine Auskunft, kein Raten.
    return { art: 'nichts', nachricht: kennung }
  }
  const gespraech = String(antwort?.gespraech || '').trim()
  if (!gespraech) return { art: 'weg', nachricht: kennung }
  const ziel = typeof adresse === 'function' ? String(adresse(gespraech) || '') : ''
  return { art: 'gespraech', gespraech, nachricht: kennung, adresse: ziel }
}

/**
 * Wie der Sprung weitergeht, wenn die Nachricht noch nicht im geladenen
 * Verlauf steht (Karte Punkt 2: „so lange ältere Seiten nachladen, bis sie da
 * ist (höchstens 10 Seiten)“).
 *
 * `seiten` ist der Zähler der bereits nachgeladenen Seiten dieses Sprungs.
 *
 *   'da'       → die Nachricht steht im Verlauf, jetzt hervorheben
 *   'weiter'   → ältere Seite nachladen (Zähler +1)
 *   'weg'      → sie kommt nicht mehr: ruhiger Hinweis
 *   'aufgeben' → die 10 Seiten sind aufgebraucht: ruhiger Hinweis
 *
 * Warum ZWEI Gründe für denselben Satz: die Oberfläche zeigt beide Male
 * „Diese Nachricht gibt es nicht mehr.“ — für die lesende Person ist der
 * Unterschied (gelöscht oder zu tief im Verlauf) keiner. Der Unterschied
 * zählt nur für `aeltereLaden`, das bei `'aufgeben'` nicht endlos weiterläuft.
 */
export function naechsterSprung({ nachricht, vorhanden = [], aelterMoeglich = true, seiten = 0 } = {}) {
  const kennung = String(nachricht || '').trim()
  if (!kennung) return 'weg'
  const liste = Array.isArray(vorhanden) ? vorhanden : []
  if (liste.some((n) => String(n?.ident || n?.name || n?.id || '') === kennung)) return 'da'
  if (seiten >= SPRUNG_MAX_SEITEN) return 'aufgeben'
  // Kein Weg nach oben mehr: die Nachricht ist nicht da und kommt nicht mehr.
  if (!aelterMoeglich) return 'weg'
  return 'weiter'
}

/**
 * Darf an die ÄLTESTE bekannte Nachricht angehängt werden? (Leerer Verlauf:
 * nein — der Sprung lädt dann erst die neueste Seite, kein Nachladen ins
 * Leere.)
 */
export function sprungAnker(nachrichten) {
  const liste = Array.isArray(nachrichten) ? nachrichten : []
  const erste = liste[0]
  return String(erste?.ident || erste?.name || erste?.id || '').trim()
}

/**
 * EIN Schritt des Sprungs — die Entscheidung, was als Nächstes zu tun ist.
 *
 * Review R1/1 und R1/5: Vorher stand die Schleife in der Seite und hat
 *   * den Ladefall „Verlauf war leer“ NICHT gegen `SPRUNG_MAX_SEITEN`
 *     gezählt (endlos, wenn der Server leer antwortet),
 *   * und den Gesprächswechsel während des Nachladens nicht bemerkt (dann
 *     wurden Seiten des ALTEN Gesprächs geladen).
 * Beides ist hier eine Entscheidung, prüfbar ohne Browser:
 *
 *   'da'       → die Nachricht steht im Verlauf: hervorheben, fertig
 *   'laden'    → Verlauf ist leer: erst die neueste Seite holen
 *   'weiter'   → ältere Seite nachladen
 *   'weg'      → ruhiger Hinweis (gelöscht/zu tief/nicht ladbar)
 *   'wechsel'  → ein anderes Gespräch ist offen geworden: NICHTS tun
 *
 * `seiten` zählt JEDEN Ladeversuch dieses Sprungs — auch das Laden der
 * neuesten Seite im leeren Verlauf. Spätestens bei `SPRUNG_MAX_SEITEN`
 * Versuchen ist Schluss (`'weg'`), egal was der Server antwortet.
 *
 * `gespraech` (Ziel) und `offen` (gerade offen) sind Kennungen; `offen` leer
 * heißt „es ist noch keines offen“ (der Aufrufer wartet dann, s. Seite).
 *
 * @returns {{ schritt: 'da'|'laden'|'weiter'|'weg'|'wechsel', seiten: number }}
 */
export function sprungSchritt({ nachricht, vorhanden = [], gespraech = '', offen = '', seiten = 0 } = {}) {
  const kennung = String(nachricht || '').trim()
  const ziel = String(gespraech || '').trim()
  const jetzt = String(offen || '').trim()
  let stand = Math.max(0, Number(seiten) || 0)
  // Das Gespräch ist nicht mehr das gesuchte: ein anderes ist aufgegangen.
  if (ziel && jetzt !== ziel) return { schritt: 'wechsel', seiten: stand }
  if (!kennung) return { schritt: 'weg', seiten: stand }
  const liste = Array.isArray(vorhanden) ? vorhanden : []
  if (liste.some((n) => String(n?.ident || n?.name || n?.id || '') === kennung)) {
    return { schritt: 'da', seiten: stand }
  }
  if (stand >= SPRUNG_MAX_SEITEN) return { schritt: 'weg', seiten: stand }
  if (!sprungAnker(liste)) return { schritt: 'laden', seiten: stand + 1 }
  return { schritt: 'weiter', seiten: stand + 1 }
}

// ── Tastatur in der Trefferliste ────────────────────────────────────────────

/**
 * Was eine Taste in der offenen Trefferliste bedeutet (Karte „Prinzipien“:
 * Pfeiltasten in der Trefferliste, Enter öffnet).
 *
 * Dieselben Tasten wie im Hausmenü (`components/ui/aktionen.mjs`,
 * `tasteImMenue`) — aber hier nur die vier, die die Trefferliste braucht:
 *
 *   'weiter'   ↓ / ↓ mit offenem Feld → nächster Treffer (am Ende: erster)
 *   'zurueck'  ↑ → voriger Treffer (am Anfang: letzter)
 *   'oeffnen'  Enter → den gewählten Treffer öffnen
 *   'schliessen' Escape → Liste zu, Feld bleibt (Karte Punkt 3)
 *
 * `null` = die Taste gehört dem Feld (Tippen, Tab …). `isComposing` schützt
 * eine laufende IME-Eingabe: dort bedeutet Enter „übernehmen“, nicht
 * „öffnen“.
 *
 * @returns {'weiter'|'zurueck'|'oeffnen'|'schliessen'|null}
 */
export function trefferTaste({ key, isComposing = false, anzahl = 0 } = {}) {
  if (isComposing) return null
  const da = (Number(anzahl) || 0) > 0
  switch (key) {
    case 'Escape':
      return 'schliessen'
    case 'ArrowDown':
      return da ? 'weiter' : null
    case 'ArrowUp':
      return da ? 'zurueck' : null
    case 'Enter':
      return da ? 'oeffnen' : null
    default:
      return null
  }
}

/**
 * Die nächste Stelle in der Liste (mit Umlauf) — dieselbe Rechnung wie
 * `naechsteStelle` in `components/chat/erwaehnung.mjs`, hier eigenständig,
 * weil jenes Modul die Auswahl der Beteiligten beschreibt (Prinzip: eine
 * Baustelle, eine Regel — und diese Liste hat ihre eigene).
 */
export function naechsteTrefferStelle(aktiv, richtung, anzahl) {
  const n = Math.max(0, Number(anzahl) || 0)
  if (!n) return 0
  const a = Math.min(Math.max(0, Number(aktiv) || 0), n - 1)
  return (a + (richtung >= 0 ? 1 : -1) + n) % n
}

/**
 * Die Kennung einer Trefferzeile für `aria-activedescendant` — EINE Stelle für
 * Listbox-Kennungen (`<liste>-treffer-<n>`).
 */
export function optionKennung(listeId, index) {
  const i = index === null || index === undefined || index === '' ? NaN : Number(index)
  return Number.isInteger(i) && i >= 0 ? `${listeId}-treffer-${i}` : null
}
