/**
 * UX3f — Befehlspalette (Strg+K): Regeln ohne Browser.
 *
 * Die Palette (`components/Befehlspalette.vue`) zeichnet nur; was sie zeigt und
 * wie sie auf Tasten reagiert, steht hier — prüfbar ohne DOM.
 *
 * ABSCHNITTE (Entwurf A5, verbindlich):
 *   Zuletzt verwendet · Seiten · Personen · Gruppen · Termine · Lieder ·
 *   Aktionen
 *
 * ZWEI QUELLEN, EINE LISTE
 *   * Treffer kommen aus dem SERVER (`suche.global`, UX3g): Art, Titel, Ort,
 *     Ziel. Welche Treffer jemand sehen darf, entscheidet ausschließlich der
 *     Server — hier wird NICHT gefiltert und NICHT nachgeladen.
 *   * Seiten kommen aus `menue.js` (die eine Quelle der Menünamen, Prinzip N4)
 *     und sind rollenabhängig; Aktionen sind die zwei Anlege-Wege des
 *     Entwurfs, ebenfalls je Recht.
 *
 * Freitext in der Palette hat zwei Aufgaben:
 *   1. leere Eingabe → „Zuletzt verwendet“ + Seiten + Aktionen (Entwurf A5)
 *   2. Eingabe      → Server-Treffer; passende SEITEN werden zusätzlich
 *      lokal gefiltert, damit „pers“ schon „Personen“ zeigt, bevor der Server
 *      (ab zwei Zeichen) überhaupt antwortet.
 *
 * Zustände (Prinzip I5): leer (nichts gefunden), ladend, Fehler mit „Erneut
 * versuchen“, Erfolg — die Palette behält dabei IMMER, was sie schon zeigt.
 */

/** Abschnittsüberschriften in Anzeigereihenfolge (Entwurf A5). */
export const ABSCHNITTE = [
  { id: 'zuletzt', label: 'Zuletzt verwendet' },
  { id: 'seiten', label: 'Seiten' },
  { id: 'person', label: 'Personen' },
  { id: 'gruppe', label: 'Gruppen' },
  { id: 'termin', label: 'Termine' },
  { id: 'lied', label: 'Lieder' },
  { id: 'aktion', label: 'Aktionen' },
]

/** Server-Arten außerhalb der Personen/Gruppen/Termine/Lieder-Abschnitte. */
const WEITERE_ARTEN = { wiki: 'seiten', beitrag: 'seiten', einstellung: 'seiten' }

/** Länge des Verlaufs „Zuletzt verwendet“ (K3: wenige, gute Voreinstellungen). */
export const VERLAUF_MAX = 5

/**
 * Symbol je Abschnitt für die Zeile. Schlüssel sind die Namen aus dem
 * Symbolvorrat (`components/ui/symbole.mjs`); Aktionen tragen ihr eigenes
 * Symbol (WhatsApp/Ruf) — hier nur der Rückfall.
 */
export const SYMBOL_JE_ABSCHNITT = {
  zuletzt: 'erneut',
  seiten: 'notiz',
  person: 'gruppe',
  gruppe: 'rolle',
  termin: 'kalender',
  lied: 'nachricht',
  aktion: 'hinzufuegen',
}

// ── Tastatur ─────────────────────────────────────────────────────────────────

const IST_MAC = typeof navigator !== 'undefined'
  && /Mac|iPhone|iPad|iPod/i.test(String(navigator.platform || navigator.userAgent || ''))

/**
 * Tastenkürzel-Text der Palette (Entwurf A5 zeigt „Esc“ in der Suchzeile,
 * die Fußzeile nennt ↑ ↓ ↵ Esc).
 */
export const KUERZEL = Object.freeze({
  oeffnen: IST_MAC ? '⌘K' : 'Strg+K',
  schliessen: 'Esc',
  hoch: '↑',
  runter: '↓',
  oeffnen_taste: '↵',
})

/**
 * Ist das die Öffnen-Taste? Strg+K (Windows/Linux) UND ⌘+K (Mac) — beide, weil
 * eine Tastatur nicht immer verrät, welches System der Nutzer meint.
 *
 * Bewusst tolerant zu `event.key`-Schreibweisen: Browser liefern „k“, „K“; bei
 * gedrückter Umschalttaste ein anderes Zeichen — deshalb zusätzlich `code`.
 * Zusammengesetzte Eingaben (IME) und Wiederholungen (`repeat`) lösen NICHT aus.
 */
export function istOeffnenTaste(event) {
  if (!event || event.repeat) return false
  const key = String(event.key || '')
  const code = String(event.code || '')
  const istK = key.toLowerCase() === 'k' || code === 'KeyK'
  if (!istK) return false
  return event.ctrlKey === true || event.metaKey === true
}

/**
 * Darf die Palette in diesem Feld aufgehen? In einem Eingabefeld gehört Strg+K
 * dem Feld (Suchen/Ersetzen, Browser-Vervollständigung) — dort nicht kapern.
 * Auf dem Seitenkörper (kein Feld) gilt das Kürzel überall.
 */
export function darfKuerzelGreifen(ziel) {
  if (!ziel || typeof ziel !== 'object') return true
  if (ziel.isContentEditable) return false
  const tag = String(ziel.tagName || '').toUpperCase()
  return !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)
}

/** Richtung einer Pfeiltaste: -1 hoch, +1 runter, 0 sonst. */
export function richtungstaste(event) {
  if (!event) return 0
  const key = String(event.key || '')
  if (key === 'ArrowDown' || key === 'Down') return 1
  if (key === 'ArrowUp' || key === 'Up') return -1
  return 0
}

/**
 * Nächste Auswahl in einer Liste von `anzahl` Treffern.
 *
 * Ringbewegung: unter dem letzten Treffer kommt der erste, über dem ersten der
 * letzte. Ohne Auswahl (-1) beginnt ↑ beim LETZTEN und ↓ beim ERSTEN Treffer —
 * das ist die Erwartung, die eine Palette weckt. Leere Liste bleibt bei -1.
 */
export function naechsteAuswahl(aktuell, anzahl, richtung) {
  const n = Number(anzahl)
  if (!Number.isFinite(n) || n <= 0) return -1
  const schritt = richtung < 0 ? -1 : 1
  const von = Number.isInteger(aktuell) && aktuell >= 0 && aktuell < n ? aktuell : null
  if (von === null) return schritt < 0 ? n - 1 : 0
  return (von + schritt + n) % n
}

// ── Verlauf (localStorage) ───────────────────────────────────────────────────

/**
 * Grundschlüssel des Verlaufs. Der TATSÄCHLICHE Schlüssel hängt am Nutzer
 * (`verlaufSchluessel`) — siehe DSGVO-Hinweis dort.
 */
export const VERLAUF_SCHLUESSEL = 'dk-befehlspalette-zuletzt'

/**
 * Kleiner, stabiler Hash (FNV-1a, 32 Bit) — nur dazu da, die Nutzerkennung
 * (E-Mail) NICHT im Klartext in den Speicher des Browsers zu schreiben. Kein
 * Sicherheitsmerkmal: der Verlauf selbst steht weiter lesbar daneben.
 */
export function nutzerHash(kennung) {
  const text = String(kennung || '').trim().toLowerCase()
  if (!text) return ''
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    // Math.imul hält die Rechnung bei 32 Bit (kein Überlauf in float).
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

/**
 * Verlaufs-Schlüssel EINES Nutzers (Review UX3f, DSGVO).
 *
 * „Zuletzt verwendet“ verrät, wonach jemand gesucht hat — auf einem geteilten
 * Rechner darf das nicht in den Verlauf des nächsten Nutzers wandern. Deshalb
 * steht die Nutzerkennung (gehasht) IM Schlüssel UND ein Identitätswechsel
 * räumt die alten Schlüssel weg (`verlaufFuerNutzerAufraeumen`).
 *
 * Ohne Kennung (Gastaussicht, Boot-Objekt fehlt) gilt der alte, ungeteilte
 * Schlüssel: dort gibt es keinen zweiten Nutzer, dessen Verlauf man sehen
 * könnte.
 */
export function verlaufSchluessel(nutzer) {
  const hash = nutzerHash(nutzer)
  return hash ? `${VERLAUF_SCHLUESSEL}:${hash}` : VERLAUF_SCHLUESSEL
}

/**
 * Beim Anmelden/Identitätswechsel: ALLE Verlaufs-Schlüssel löschen, die nicht
 * zu diesem Nutzer gehören. Fehlt die Kennung, wird alles gelöscht (fail
 * closed — lieber Komfort verloren als fremde Suchspuren behalten).
 *
 * Läuft beim Start der SPA (main.js) und beim Abmelden. Still: ohne Speicher
 * passiert nichts.
 */
export function verlaufFuerNutzerAufraeumen(speicher, nutzer) {
  try {
    if (!speicher || typeof speicher.key !== 'function') return
    const behalten = nutzerHash(nutzer)
    const weg = []
    for (let i = 0; i < speicher.length; i += 1) {
      const k = speicher.key(i)
      if (!k || k !== VERLAUF_SCHLUESSEL) continue
      weg.push(k)   // alter, ungeteilter Schlüssel: gehört niemandem mehr
    }
    for (let i = 0; i < speicher.length; i += 1) {
      const k = speicher.key(i)
      if (!k || !k.startsWith(VERLAUF_SCHLUESSEL + ':')) continue
      if (behalten && k === `${VERLAUF_SCHLUESSEL}:${behalten}`) continue
      weg.push(k)
    }
    for (const k of new Set(weg)) speicher.removeItem(k)
  } catch (_) {
    // Speicher gesperrt: dann liegt auch nichts von einem früheren Nutzer.
  }
}

/**
 * Verlauf lesen — IMMER abgesichert (Privater Modus, gesperrter Speicher,
 * kaputter Wert). Was nicht lesbar ist, ist leer; die Palette bleibt nutzbar.
 *
 * Gespeichert wird nur, was die Palette selbst zum Ziel hat: `id`, `titel`,
 * `ziel`, `gruppe`. Kein Text, den jemand in der Suche getippt hat.
 */
export function verlaufLesen(speicher, nutzer = '') {
  try {
    const roh = speicher && typeof speicher.getItem === 'function'
      ? speicher.getItem(verlaufSchluessel(nutzer))
      : null
    if (!roh) return []
    const daten = JSON.parse(roh)
    if (!Array.isArray(daten)) return []
    return daten
      .filter(e => e && typeof e.id === 'string' && typeof e.titel === 'string'
        && typeof e.ziel === 'string' && e.ziel.startsWith('#'))
      .slice(0, VERLAUF_MAX)
  } catch (_) {
    return []
  }
}

/** Verlauf schreiben — still scheitern, nie die Palette stören. */
export function verlaufSchreiben(speicher, eintraege, nutzer = '') {
  try {
    if (!speicher || typeof speicher.setItem !== 'function') return
    const sauber = (Array.isArray(eintraege) ? eintraege : [])
      .filter(e => e && typeof e.id === 'string' && typeof e.titel === 'string'
        && typeof e.ziel === 'string' && e.ziel.startsWith('#'))
      .slice(0, VERLAUF_MAX)
    speicher.setItem(verlaufSchluessel(nutzer), JSON.stringify(sauber))
  } catch (_) {
    // Speicher voll/gesperrt: der Verlauf ist Komfort, kein Fachzustand.
  }
}

/**
 * Neuen Verlauf bilden: der gewählte Treffer steht vorn, gleiche Ziele fallen
 * heraus (keine Dubletten in „Zuletzt verwendet“).
 */
export function verlaufNachWahl(bisher, eintrag) {
  const alt = Array.isArray(bisher) ? bisher : []
  if (!eintrag || typeof eintrag.id !== 'string') return alt.slice(0, VERLAUF_MAX)
  const ohne = alt.filter(e => e && e.ziel !== eintrag.ziel)
  return [{
    id: eintrag.id,
    titel: String(eintrag.titel || ''),
    // Der Ort steht in der Zeile rechts — auch im Verlauf.
    ort: String(eintrag.ort || eintrag.gruppe || ''),
    ziel: eintrag.ziel,
    gruppe: eintrag.gruppe || '',
  }, ...ohne].slice(0, VERLAUF_MAX)
}

// ── Seiten und Aktionen ──────────────────────────────────────────────────────

/** Faltet Text für den Vergleich: klein, ohne Umlaute/Sonderzeichen. */
function falte(text) {
  return String(text || '')
    .normalize('NFC')
    .toLowerCase()
    .replace(/ß/g, 'ss').replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue')
    .replace(/[^a-z0-9]+/g, ' ').trim()
}

/**
 * Erfüllt `begriff` den Text? Wortanfang zählt zuerst („per“ → „Personen“),
 * aber auch ein Wort im Inneren („ein“ → „Einstellungen“).
 */
export function passtZu(begriff, ...texte) {
  const suche = falte(begriff)
  if (!suche) return true
  for (const text of texte) {
    const ziel = falte(text)
    if (!ziel) continue
    if (ziel.startsWith(suche)) return true
    if (ziel.split(' ').some(wort => wort.startsWith(suche))) return true
    if (ziel.includes(suche)) return true
  }
  return false
}

/**
 * Seiten-Einträge der Palette aus der Menüdefinition.
 *
 * Nur Einträge mit `suche: true` erscheinen (die Menüdefinition führt das Feld
 * selbst — Seiten ohne Menüeintrag tragen es am Seitennamen). Sichtbarkeit
 * folgt DERSELBEN Regel wie die Seitenleiste (`sichtbareEintraege`), damit die
 * Palette keine Rolle verspricht, die das Menü versteckt.
 *
 * @param {{menue: Array, fuss: Array, sichtbareEintraege: Function,
 *          rechte: {istAdmin?: boolean, istTester?: boolean, istGast?: boolean,
 *                   rollen?: string[]}}} lage
 * @returns {Array<{id, abschnitt, titel, ort, ziel, symbol, gruppe}>}
 */
export function seitenEintraege({ menue = [], fuss = [], sichtbareEintraege, rechte = {} } = {}) {
  const sichtbar = typeof sichtbareEintraege === 'function' ? sichtbareEintraege : (g) => (g.eintraege || [])
  const ergebnis = []
  for (const gruppe of menue || []) {
    for (const eintrag of sichtbar(gruppe, rechte) || []) {
      if (eintrag.suche !== true) continue
      ergebnis.push({
        id: 'seite:' + eintrag.id,
        abschnitt: 'seiten',
        titel: eintrag.label,
        // N7: Treffer zeigen ihren ORT. Bei Seiten ist das die Menügruppe.
        ort: gruppe.gruppe || 'Übersicht',
        ziel: eintrag.href,
        symbol: eintrag.icon || SYMBOL_JE_ABSCHNITT.seiten,
        gruppe: gruppe.gruppe || '',
      })
    }
  }
  for (const eintrag of fuss || []) {
    if (eintrag.suche !== true) continue
    if (eintrag.rolle === 'admin' && !rechte.istAdmin) continue
    if ((eintrag.rollen || []).length
      && !eintrag.rollen.some(r => (rechte.rollen || []).includes(r))) continue
    ergebnis.push({
      id: 'seite:' + eintrag.id,
      abschnitt: 'seiten',
      titel: eintrag.label,
      ort: 'Verwaltung',
      ziel: eintrag.href,
      symbol: eintrag.icon || SYMBOL_JE_ABSCHNITT.seiten,
      gruppe: '',
    })
  }
  return ergebnis
}

/**
 * Die zwei Anlege-Wege des Entwurfs A5 — je Recht.
 *
 * „Termin anlegen“ und „Person anlegen“ stehen nur da, wenn die Ziele die
 * Aktion wirklich anbieten (Kalender: Schreibrecht auf mindestens einen
 * Kalender; Personen: Mitgliederverwaltung). Ein Eintrag, der auf einer Seite
 * landet, die nichts anlegen kann, wäre ein toter Knopf (Prinzip I4).
 *
 * Ziele: `#/kalender?neu=1` öffnet den Kalender im Anlege-Dialog (Kalender.vue
 * liest den Schalter EINMAL beim Öffnen), `#/personen?anlegen=1` die
 * Personenliste im Anlege-Dialog. Beide Adressen bleiben lesbar, wenn die
 * Aktion wegfällt — dann öffnet sich nur die Seite.
 */
export function aktionsEintraege({ darfTermin = false, darfPerson = false } = {}) {
  const liste = []
  if (darfTermin) {
    liste.push({
      id: 'aktion:termin-anlegen',
      abschnitt: 'aktion',
      titel: 'Termin anlegen',
      ort: 'Aktion',
      ziel: '#/kalender?neu=1',
      symbol: 'kalender',
      gruppe: '',
    })
  }
  if (darfPerson) {
    liste.push({
      id: 'aktion:person-anlegen',
      abschnitt: 'aktion',
      titel: 'Person anlegen',
      ort: 'Aktion',
      ziel: '#/personen?anlegen=1',
      symbol: 'gruppe',
      gruppe: '',
    })
  }
  return liste
}

/**
 * Server-Treffer in Abschnitte einsortieren.
 *
 * Der Server liefert `[{art, titel, ort, ziel}]` in der Reihenfolge seiner
 * `ARTEN`. Die Palette ordnet sie den Abschnitten zu; unbekannte Arten bleiben
 * AUS (eine Zeile ohne Abschnitt hätte keinen Ort). Innerhalb eines
 * Abschnitts bleibt die Server-Reihenfolge erhalten — sie ist fachlich
 * sortiert (Personen nach Nachname, Termine nach Datum).
 */
export function trefferEinsortieren(treffer, { gefragt = true, quellen = null } = {}) {
  const raus = []
  // Nur Arten, für die der Server WIRKLICH gesucht hat. `quellen` sind seine
  // Zähler (`{art: anzahl}`): ein Abschnitt ohne Treffer, aber mit Zähler 0
  // ist „nichts gefunden“ — ein Abschnitt, dessen Art gar nicht in `quellen`
  // steht, ist für diese Sitzung nicht vorhanden (z. B. Einstellungen ohne
  // Verwaltungsrecht). Im Wegwerf-Stack gemessen: die Palette zeigte
  // „TERMINE“ als leere Überschrift über der Fußzeile.
  const zugelassen = (art) => {
    if (!quellen || typeof quellen !== 'object') return true
    // Nur Arten mit Zähler UND mindestens einem Treffer bekommen eine
    // Überschrift — eine leere Überschrift ist ein Befund (Wegwerf-Stack:
    // „TERMINE“ über der Fußzeile, obwohl der Zähler 5 sagte und die Quelle
    // ausgefallen war).
    return Object.prototype.hasOwnProperty.call(quellen, art) && quellen[art] > 0
  }
  for (const t of Array.isArray(treffer) ? treffer : []) {
    if (!t || typeof t.ziel !== 'string' || !t.ziel.startsWith('#')) continue
    // Ein Zähler > 0 OHNE Treffer ist ein Widerspruch in der Antwort (der
    // Server ließ eine Quelle ausfallen): der Abschnitt bliebe eine leere
    // Überschrift im Bild. Deshalb zählt zusätzlich der Treffer selbst.
    if (!zugelassen(t.art)) continue
    const abschnitt = ABSCHNITTE.some(a => a.id === t.art) ? t.art : WEITERE_ARTEN[t.art]
    if (!abschnitt) continue
    raus.push({
      id: `${t.art}:${t.ziel}:${t.titel}`,
      abschnitt,
      titel: String(t.titel || ''),
      ort: String(t.ort || ''),
      ziel: t.ziel,
      symbol: SYMBOL_JE_ABSCHNITT[t.art] || SYMBOL_JE_ABSCHNITT[abschnitt],
      gruppe: '',
      // Stammen die Treffer aus einer ANTWORT auf den aktuellen Begriff?
      // Sonst (alter Stand während des Tippens) bleiben sie sichtbar, aber
      // „nichts gefunden“ wird nicht behauptet.
      gefragt: gefragt === true,
    })
  }
  return raus
}

/**
 * Die Arten, für die der Server in DIESER Antwort gesucht hat (`quellen`).
 * Fehlt der Zähler (alte Antwort), gilt „unbekannt“ = alle Arten — dann
 * entscheidet allein das Vorhandensein von Treffern.
 */
export function gesuchteArten(antwort) {
  const quellen = antwort && typeof antwort.quellen === 'object' ? antwort.quellen : null
  if (!quellen) return null
  return new Set(Object.keys(quellen))
}

// ── Gesamtliste ──────────────────────────────────────────────────────────────

/**
 * Alle Zeilen der Palette in Anzeigereihenfolge — die EINE Liste, über die
 * ↑↓ laufen. `position` ist der Zeilenindex über ALLE Abschnitte (nicht je
 * Abschnitt), damit die Auswahl an Abschnittsgrenzen nicht springt.
 *
 * @param {object} lage
 * @param {string} lage.begriff      getippter Text
 * @param {Array}  lage.verlauf      Einträge aus `verlaufLesen`
 * @param {Array}  lage.seiten       aus `seitenEintraege`
 * @param {Array}  lage.aktionen     aus `aktionsEintraege`
 * @param {Array}  lage.treffer      aus `trefferEinsortieren`
 * @param {boolean} lage.trefferGefragt  Server hat für DIESEN Begriff geantwortet
 * @returns {{zeilen: Array, gruppen: Array<{id, label, zeilen}>}}
 */
export function paletteZeilen({ begriff = '', verlauf = [], seiten = [], aktionen = [], treffer = [] } = {}) {
  const leer = !String(begriff || '').trim()

  // Seiten: bei leerer Eingabe alle (Entwurf A5 zeigt „Personen“,
  // „Einstellungen“), sonst die passenden.
  const seitenZeilen = (seiten || []).filter(s => leer || passtZu(begriff, s.titel, s.ort))
  const aktionsZeilen = (aktionen || []).filter(a => leer || passtZu(begriff, a.titel, a.ort))

  // Verlauf nur ohne Eingabe — „Zuletzt verwendet“ ist der Startzustand.
  const verlaufZeilen = leer
    ? (verlauf || []).map(e => ({
      id: 'zuletzt:' + e.id + ':' + e.ziel,
      abschnitt: 'zuletzt',
      titel: e.titel,
      ort: e.ort || 'Verlauf',
      ziel: e.ziel,
      symbol: SYMBOL_JE_ABSCHNITT.zuletzt,
      gruppe: '',
    }))
    : []

  // Server-Treffer: bei leerer Eingabe keine (der Endpunkt liefert dafür
  // ohnehin nichts — kein Aufruf).
  const nachAbschnitt = {}
  for (const t of leer ? [] : (treffer || [])) {
    ;(nachAbschnitt[t.abschnitt] = nachAbschnitt[t.abschnitt] || []).push(t)
  }

  const gruppen = []
  const zeilen = []
  for (const abschnitt of ABSCHNITTE) {
    let inhalt
    if (abschnitt.id === 'zuletzt') inhalt = verlaufZeilen
    else if (abschnitt.id === 'seiten') {
      // Seiten aus dem Menü UND Seiten-Treffer des Servers (Wiki, Beiträge,
      // Einstellungs-Abschnitte). Dubletten nach Ziel entfernen — der
      // Menüname gilt (Prinzip N4).
      const bekannt = new Set(seitenZeilen.map(z => z.ziel))
      const vomServer = (nachAbschnitt.seiten || []).filter(t => !bekannt.has(t.ziel))
      inhalt = [...seitenZeilen, ...vomServer]
    } else if (abschnitt.id === 'aktion') inhalt = aktionsZeilen
    else inhalt = nachAbschnitt[abschnitt.id] || []

    if (!inhalt.length) continue
    for (const zeile of inhalt) {
      zeile.position = zeilen.length
      zeilen.push(zeile)
    }
    gruppen.push({ id: abschnitt.id, label: abschnitt.label, zeilen: inhalt })
  }
  return { zeilen, gruppen }
}

/**
 * Leerzustand: es gibt NICHTS zu zeigen. Nur behaupten, wenn der Server für
 * den aktuellen Begriff geantwortet hat und auch die lokalen Seiten/Aktionen
 * leer sind — während des Tippens nie „nichts gefunden“ (I5).
 */
export function istLeer({ begriff, zeilen, trefferGefragt }) {
  if ((zeilen || []).length) return false
  if (!String(begriff || '').trim()) return false
  return trefferGefragt === true
}

/** Mindestlänge, ab der der Server gefragt wird (wie `suche.MIN_ZEICHEN`). */
export const MIN_ZEICHEN = 2
