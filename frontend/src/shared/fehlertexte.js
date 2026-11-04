/**
 * UX2g — Fehlerkatalog: EINE Quelle für angezeigte Fehlertexte.
 *
 * BEFUND (Manuel, Dev-Modus): Fehlerflächen zeigten „Unbekannter Fehler",
 * „Fehler beim Speichern", „Fehler beim Laden", „Ein Fehler ist aufgetreten"
 * oder technische Codes wie „HTTP 500". Damit kann niemand etwas anfangen:
 * die Meldung sagt nicht, was passiert ist, warum, und was jetzt hilft.
 *
 * REGEL (I4 aus den UI-Prinzipien): jede Meldung beantwortet
 *
 *   was ist passiert · was jetzt hilft
 *
 * in EINEM Satz, ohne Jargon, ohne Code, ohne Diagnosetext. Beispiele:
 *
 *   Kathrin lädt die Personenliste, der Server ist weg
 *     -> „Der Server antwortet gerade nicht. Lade die Seite neu oder
 *         versuche es in ein paar Minuten noch einmal."
 *
 * Die EINSTUFUNG ist eine reine Funktion von `exc_type` und HTTP-Status —
 * beide Werte liefert die Compat-Schicht bereits (Allowlist in
 * `backend/src/diakronos_app/frappe_compat/router.py`,
 * `shared/csrf-heilung.js` bzw. `shared/sitzung-pruefen.js` für den
 * Sitzungsabbruch). NEU ist nur die Übersetzung in Klartext; die bestehende
 * CSRF- und Sitzungslogik bleibt unverändert.
 *
 * WICHTIG — Fachliche Meldungen des Servers gehen VOR: Der Server antwortet auf
 * einen fachlichen Fehler (z. B. „Das Ende muss nach dem Beginn liegen.")
 * bewusst mit einem deutschen Satz in `message`. Genau dieser Satz wird
 * angezeigt, nicht der Katalogtext. Der Katalog greift nur, wo der Server
 * nichts Vorzeigbares mitschickt — und dort, wo der Servertext eine
 * Floskel ist („Ungueltige Anfrage", „Interner Fehler") oder nach innen
 * zeigt (Traceback, Exception-Klasse, Modulpfad, Statuscode).
 *
 * Verworfen wird ein Servertext, wenn er
 *   * leer ist,
 *   * eine der alten Floskeln ist (`FLOKSEN`),
 *   * eine intern aussehende Kennung trägt (Unterstrich, Klammern, Pfad,
 *     CamelCase-Klassenname, Versions-/Statuscode),
 *   * zu lang für eine Fehlerfläche ist (dann ist er ein Stapel).
 *
 * Keine Importe: Diese Datei wird von den eigenständigen Bündeln (gast,
 * registrierung, organigramm) UND vom Hauptbereich geladen. Ein Import aus
 * `sitzung-pruefen.js` herum (CSRF-Heilung <-> Sitzungsprüfung) entstünde
 * sonst wieder.
 */

/**
 * Die Sätze des Katalogs. Jeder Eintrag: `was` (Zustand) + `jetzt` (nächster
 * Schritt). Wortlaut bewusst ohne „Fehler", ohne Status, ohne „System".
 */
export const FEHLERTEXTE = {
  // ── Sitzung ────────────────────────────────────────────────────────────
  sitzung: {
    was: 'Deine Anmeldung ist abgelaufen.',
    jetzt: 'Melde dich neu an.',
  },

  // ── Verbindung ─────────────────────────────────────────────────────────
  netz: {
    was: 'Die Verbindung ist unterbrochen.',
    jetzt: 'Prüfe deine Internetverbindung und versuche es dann erneut.',
  },
  server: {
    was: 'Der Server antwortet gerade nicht.',
    jetzt: 'Versuche es in ein paar Minuten noch einmal.',
  },
  ueberlastet: {
    was: 'Der Server ist gerade ausgelastet.',
    jetzt: 'Warte einen Moment und versuche es dann erneut.',
  },

  // ── Berechtigung ───────────────────────────────────────────────────────
  rechte: {
    was: 'Dafür fehlt dir die Berechtigung.',
    jetzt: 'Bitte die Gemeindeleitung fragen, wenn du das ändern sollst.',
  },

  // ── Eingabe ────────────────────────────────────────────────────────────
  eingabe: {
    was: 'Die Angaben sind unvollständig oder ungültig.',
    jetzt: 'Prüfe die markierten Felder und versuche es erneut.',
  },

  // ── Konflikt ───────────────────────────────────────────────────────────
  konflikt: {
    was: 'Der Eintrag wurde zwischenzeitlich geändert.',
    jetzt: 'Lade die Seite neu und trage deine Änderung erneut ein.',
  },

  // ── Nicht gefunden ─────────────────────────────────────────────────────
  weg: {
    was: 'Der Eintrag ist nicht mehr vorhanden.',
    jetzt: 'Lade die Liste neu — vielleicht wurde er inzwischen entfernt.',
  },

  // ── Vorübergehend ──────────────────────────────────────────────────────
  spaeter: {
    was: 'Das hat gerade nicht geklappt.',
    jetzt: 'Versuche es in einem Moment noch einmal.',
  },

  // ── Unklar (keine Fehlerlage übergeben) ────────────────────────────────
  unbekannt: {
    was: 'Das hat gerade nicht geklappt.',
    jetzt: 'Versuche es in einem Moment noch einmal — bleibt es dabei, lade die Seite neu.',
  },
}

/**
 * Alte Floskeln — alles, was als Meldung NICHTS sagt. Sie dürfen weder
 * angezeigt noch neu geschrieben werden (Wächter:
 * `frontend/tests/ux2g-fehlerkatalog.test.mjs`). Die Liste deckt jedes
 * Verb der alten Rahmen ab („Fehler beim Speichern/Erstellen/Laden/…"), weil
 * `istFloskel` zusätzlich jedes Wort nach „Fehler" verwirft.
 */
export const FLOKSEN = [
  'unbekannter fehler',
  'ein fehler ist aufgetreten',
  'fehler beim',
  'fehler beim speichern',
  'fehler beim erstellen',
  'fehler beim laden',
  'fehler beim entfernen',
  'fehler beim löschen',
  'fehler beim anlegen',
  'api-fehler',
  'fehler',
]

/** Zustände sortiert nach „am häufigsten zuerst". */
export const ZUSTAENDE = ['sitzung', 'netz', 'server', 'ueberlastet', 'rechte', 'eingabe', 'konflikt', 'weg', 'spaeter', 'unbekannt']

/**
 * Sätze des SERVERS, die keine Auskunft sind: die generischen 404/417-Texte
 * der Compat-Schicht (`_argumentfehler`/`_nicht_gefunden`) in ASCII-Schreib-
 * weise. Sie sagen nur „irgendetwas war falsch", nicht was — dort tritt der
 * Katalogtext an ihre Stelle.
 */
const SERVERALLGEMEIN = [
  'ungueltige anfrage',
  'methode nicht gefunden',
  'ungültige anfrage',
  'interner fehler',
  'internal server error',
  'bad gateway',
  'service unavailable',
  'gateway timeout',
]

/** Längste Meldung, die noch als Satz durchgeht (Fehlerflächen sind schmal). */
const MAX_LAENGE = 260

/**
 * Sieht der Text nach Innereien aus? Dann ist er kein Satz für Menschen.
 * Geprüft werden Zeichen und Muster, die in deutschen Fachsätzen nicht
 * vorkommen: Unterstriche (Feld-/Modulnamen), Klammern mit Code, Pfade,
 * Statuscodes, Exception-Klassennamen mit angehängtem „Error".
 */
export function wirktTechnisch(text) {
  const wert = typeof text === 'string' ? text.trim() : ''
  if (!wert) return true
  if (wert.length > MAX_LAENGE) return true
  if (wert.includes('_')) return true
  if (/[{}[\]<>]/.test(wert)) return true
  if (/(^|\s)(\/|\.\/|\.\.\/|[A-Za-z]:\\)/.test(wert)) return true
  if (/\b[\w-]+\.(py|js|mjs|ts|json|tsx|vue)\b/.test(wert)) return true
  if (/\b(HTTP|Status)\s*\d{3}\b/i.test(wert)) return true
  // Ein eingekleidetes Status-/Diagnosekürzel: „500", „HTTP 404", „ERR-52".
  if (/^\W*(HTTP\s*)?[1-5]\d\d\W*$/i.test(wert)) return true
  if (/^ERR[_-]?[A-Z0-9]+$/i.test(wert)) return true
  if (/\b[A-Z][a-z]+(Error|Exception)\b/.test(wert)) return true
  if (/Traceback|Exception in|stack trace/i.test(wert)) return true
  // Browser-/Laufzeitmeldungen, die keine deutsche Auskunft sind: fetch wirft
  // bei Netzausfall `TypeError: Failed to fetch` — englisch, technisch, und
  // für eine Ehrenamtliche nichtssagend (UX2g-Befund aus der Abnahme).
  if (/failed to fetch|network ?error|load failed|network request failed/i.test(wert)) return true
  return false
}

/**
 * Ist der Text (nur) eine der alten Floskeln oder ein nichtssagender
 * Server-Allgemeinplatz?
 */
export function istFloskel(text) {
  const wert = typeof text === 'string' ? text.trim().toLowerCase() : ''
  if (!wert) return true
  const ohnePunkt = wert.replace(/[.…]+$/, '').trim()
  if (FLOKSEN.includes(wert) || FLOKSEN.includes(ohnePunkt)) return true
  // Die alten Rahmen „Fehler beim Speichern/Erstellen/Laden/…" sind keine
  // Auskunft, egal welches Verb folgt (Vergleich ohne Satzzeichen, damit
  // auch „Fehler beim Laden…" greift).
  if (/^fehler\b/.test(ohnePunkt)) return true
  return SERVERALLGEMEIN.includes(ohnePunkt)
}

/** Darf dieser Servertext angezeigt werden? */
export function servertextBrauchbar(text) {
  if (typeof text !== 'string') return false
  const wert = text.trim()
  if (!wert) return false
  if (istFloskel(wert)) return false
  if (wirktTechnisch(wert)) return false
  // Ein einzelnes Wort ist keine Auskunft („Fehler", „abgelehnt", „Error").
  if (!/\s/.test(wert) && wert.length < 24) return false
  return true
}

/**
 * Zustand aus `exc_type` und HTTP-Status bestimmen.
 * @param {{status?: number, excType?: string}} lage
 * @returns {keyof FEHLERTEXTE}
 */
export function zustandFuer(lage = {}) {
  const status = Number(lage.status) || 0
  const exc = String(lage.excType || '')

  // Sitzung zuerst: 401/419 sind immer „neu anmelden", egal welcher Text da ist.
  if (status === 401 || status === 419) return 'sitzung'
  if (exc === 'SessionExpired' || exc === 'CSRFTokenError') return 'sitzung'

  // Status 0/fehlend = kein Server geantwortet. Das ist „Verbindung weg" —
  // aber nur, wenn tatsächlich eine Anfrage gescheitert ist
  // (`angefragt`). Ohne jede Lage (`{}`) weiß niemand, was passiert ist.
  if (!status) {
    if (exc === 'TypeError') return 'netz'   // fetch wirft TypeError bei Netzausfall
    return lage.angefragt ? 'netz' : 'unbekannt'
  }
  if (status === 408) return 'netz'

  if (status === 403 || exc === 'PermissionError') return 'rechte'
  if (status === 429) return 'ueberlastet'
  if (status === 404 || status === 410 || exc === 'DoesNotExistError') return 'weg'
  if (status === 409 || status === 412) return 'konflikt'
  if (status === 417 || status === 422 || status === 400) return 'eingabe'
  if (status === 502 || status === 503 || status === 504) return 'server'
  if (status >= 500) return 'server'
  if (status >= 400) return 'spaeter'
  return 'spaeter'
}

/** Der Zustand, den eine Fehlerlage hat (Kurzform von `zustandFuer`). */
function lageZustand(fehler, ersatz = {}) {
  if (ersatz.zustand && FEHLERTEXTE[ersatz.zustand]) return ersatz.zustand
  return zustandFuer({
    status: ersatz.status ?? fehler?.status,
    excType: ersatz.excType ?? fehler?.exc_type ?? fehler?.excType ?? fehler?.name,
    angefragt: ersatz.angefragt ?? fehler?.angefragt ?? (fehler?.status !== undefined),
  })
}

/** Der fertige Satz eines Zustands. */
export function katalogText(zustand) {
  const eintrag = FEHLERTEXTE[zustand] || FEHLERTEXTE.spaeter
  return `${eintrag.was} ${eintrag.jetzt}`
}

/**
 * EIN Fehlertext für die Oberfläche.
 *
 * @param {Error|{message?: string, status?: number, exc_type?: string, excType?: string}|null} fehler
 * @param {{zustand?: keyof FEHLERTEXTE, status?: number, excType?: string, text?: string}} [ersatz]
 *   `zustand` erzwingt einen Katalogtext (z. B. „netz" wenn der Aufrufer
 *   weiß, dass fetch gescheitert ist), `status`/`excType` ergänzen eine
 *   Fehlerlage, `text` ist ein eigener Fallback-Satz.
 * @returns {string}
 */
export function fehlertext(fehler, ersatz = {}) {
  const kandidaten = []
  if (typeof fehler === 'string') kandidaten.push(fehler)
  if (fehler && typeof fehler === 'object') {
    kandidaten.push(fehler.message, fehler.fehler, fehler.meldung, fehler.exception)
  }
  for (const kandidat of kandidaten) {
    if (servertextBrauchbar(kandidat)) return kandidat.trim()
  }

  if (ersatz && servertextBrauchbar(ersatz.text)) return ersatz.text.trim()

  return katalogText(lageZustand(fehler, ersatz))
}

/**
 * Kurzform für Zeilen (Menüs, Tabellen, schmale Flächen): nur „was ist
 * passiert", ohne nächsten Schritt. Dieselbe Einstufung.
 */
export function fehlerkurz(fehler, ersatz = {}) {
  const zustand = lageZustand(fehler, ersatz)
  const text = fehlertext(fehler, { ...ersatz, zustand })
  const eintrag = FEHLERTEXTE[zustand]
  // Ein brauchbarer Servertext bleibt auch in der Kurzform stehen — er ist
  // schon ein Satz.
  if (eintrag && text === katalogText(zustand)) return eintrag.was
  return text
}

/**
 * Aufruf-Kurzformen für den Alltag: `speichern(fehler)`, `laden(fehler)`.
 *
 * Sie liefern IMMER einen vollständigen Satz („was ist passiert · was jetzt
 * hilft") und ersetzen die alten Floskeln „Fehler beim Speichern", „Fehler
 * beim Laden", „Ein Fehler ist aufgetreten". Ein brauchbarer Fachsatz des
 * Servers geht unverändert durch — der Wortlaut „beim Speichern" ist also
 * nur der Rahmen, wenn der Server nichts sagt.
 */
const AKTIONEN = {
  speichern: { was: 'Das Speichern hat nicht geklappt.' },
  anlegen: { was: 'Das Anlegen hat nicht geklappt.' },
  laden: { was: 'Die Daten konnten nicht geladen werden.' },
  entfernen: { was: 'Das Entfernen hat nicht geklappt.' },
  loeschen: { was: 'Das Löschen hat nicht geklappt.' },
  senden: { was: 'Das Senden hat nicht geklappt.' },
  aktion: { was: 'Das hat nicht geklappt.' },
}

/**
 * Meldung für eine Aktion: `aktionsfehler('speichern', err)`.
 *
 * Der Zustand kommt aus Status/`exc_type` des Fehlers (ein 500 ist kein
 * Konflikt, ein 409 kein Serverausfall); nur wenn die Lage unklar bleibt,
 * greift der neutrale Satz „Das hat gerade nicht geklappt.".
 * @param {keyof AKTIONEN} aktion
 */
export function aktionsfehler(aktion, fehler, ersatz = {}) {
  const rahmen = AKTIONEN[aktion] || AKTIONEN.aktion
  const zustand = lageZustand(fehler, ersatz)
  const text = fehlertext(fehler, { ...ersatz, zustand })
  if (text !== katalogText(zustand)) return text
  // Nur bei UNKLARER Lage sagt der Katalog „Das hat gerade nicht geklappt."
  // — dann nennt der Rahmen die Handlung („Das Speichern hat nicht
  // geklappt."). Steht die Lage fest (Server weg, keine Berechtigung,
  // Verbindung unterbrochen), ist SIE die Auskunft: ein 500 ist ein
  // Serverausfall, kein Speicherproblem.
  if (zustand !== 'spaeter' && zustand !== 'unbekannt') return katalogText(zustand)
  const eintrag = FEHLERTEXTE[zustand]
  return `${rahmen.was} ${eintrag.jetzt}`
}
