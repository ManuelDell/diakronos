/**
 * CHAT-12b — die Regeln der Anhänge, ohne DOM und ohne Vue.
 *
 * Grundlagen: `docs/konzepte/CHAT-KONZEPT.md` Abschnitt S4 („Anhänge“) und
 * F11, Karte CHAT-12b. Die Oberfläche (`Nachrichten.vue`, `ChatAnhangChips.vue`,
 * `ChatAnhangBlase.vue`) zeichnet nur; was gilt, steht HIER — prüfbar im
 * Node-Test (`frontend/tests/chat12b-anhaenge.test.mjs`).
 *
 * BACKEND (CHAT-12a, `backend/src/diakronos_app/api/chat.py`, ClientModelle in
 * `models/chat.py`) — hier NUR gespiegelt, nie eine zweite Wahrheit:
 *
 *   POST chat.anhang_hochladen(gespraech, datei=<Multipart>)
 *        → {name, dateiname, mime, groesse, gespraech}
 *        Typen per MAGIE: jpg/png/webp/heic, pdf, mp3/m4a/ogg/opus.
 *        Höchstgröße JE ANHANG = die EINSTELLUNG der Gemeinde
 *        (`anhang_max_mb`, CHAT-12c), Standard 10 MB; Tagesgrenze
 *        `ANHAENGE_PRO_TAG` = 20 je Person → 429 (`RateLimitError`).
 *        Die Chat-Seite erfährt die Grenze in `chat.meine_gespraeche` als
 *        `anhang_max_bytes` (Bytes) — in der Antwort, die sie ohnehin lädt.
 *   chat.senden(gespraech, text, antwort_auf, erwaehnt, anhaenge=[name, …])
 *        höchstens `ANHAENGE_MAX` = 3 je Nachricht (`_anhaenge_pruefen`).
 *        Mit Anhang darf der TEXT LEER sein (`_pruefe_text(…, mit_anhang=True)`
 *        speichert dann die leere Zeichenkette) — „Foto ohne Worte“.
 *   Der Verlauf trägt je Nachricht `anhaenge: [{name, dateiname, mime,
 *        groesse}]`; eine GELÖSCHTE Nachricht trägt `[]` (`_zeile`).
 *   GET chat.anhang?name=<name> liefert die Datei. OFFENE Anhänge (noch an
 *        keiner Nachricht) sind dort 404 — eine Vorschau VOR dem Senden gibt es
 *        deshalb nur lokal (`URL.createObjectURL`).
 *
 * WAS HIER BEWUSST NICHT STEHT: die Typ-Prüfung. Die entscheidet der Server
 * über die MAGIC BYTES; der Browser kennt nur den Dateinamen und den (frei
 * wählbaren) MIME-Typ des Systems. Die `accept`-Liste ist deshalb eine
 * BEQUEMLICHKEIT für die Dateiauswahl, keine Prüfung.
 */
import { apiUrl } from '../../../shared/basis.js'

// ── Grenzen (dieselben Zahlen wie im Server) ────────────────────────────────

/**
 * Höchstgröße EINES Anhangs, wenn der Server NICHTS liefert — der Standard der
 * Einstellung (`ANHANG_MAX_MB_STANDARD = 10` in `models/chat.py`).
 *
 * Seit CHAT-12c ist die Grenze EINSTELLBAR (`anhang_max_mb`, 1…50 MB, Admin).
 * Maßgeblich ist deshalb `anhangMaxBytes(antwort)` unten; diese Zahl hier ist
 * nur der Rückfall, wenn die Antwort das Feld `anhang_max_bytes` nicht trägt
 * (alter Server). Keine zweite Wahrheit: die Rechnung steht EINMAL.
 */
export const ANHANG_MAX_BYTES = 10 * 1024 * 1024

/** Die Grenze in MB, wie sie in Sätzen steht (ganze Zahl). */
export const ANHANG_MAX_MB = ANHANG_MAX_BYTES / (1024 * 1024)

/** Höchstzahl Anhänge je Nachricht — `ANHAENGE_MAX` in `models/chat.py`. */
export const ANHAENGE_MAX = 3

/** Höchstzahl Anhänge je Person und Kalendertag — `ANHAENGE_PRO_TAG`. */
export const ANHAENGE_PRO_TAG = 20

/**
 * Die `accept`-Liste der Dateiauswahl: die Typen aus `ANHANG_TYPEN`
 * (Endungen, damit auch Windows und Android sie verstehen), plus `image/*`,
 * damit das System auf dem Handy die KAMERA anbietet (Karte Punkt 1).
 *
 * KEINE Prüfung — nur eine Vorauswahl. Was wirklich angenommen wird, entscheidet
 * der Server an den ersten Bytes der Datei.
 */
export const ANHANG_ACCEPT = [
  '.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.pdf',
  '.mp3', '.m4a', '.ogg', '.opus',
  'image/*', 'application/pdf', 'audio/*',
].join(',')

// ── Texte (eine Stelle, deutsche Wörter ohne Fachbegriffe) ──────────────────

export const TEXTE = Object.freeze({
  anhaengen: 'Datei anhängen',
  entfernen: 'Anhang entfernen',
  laedt: 'wird hochgeladen …',
  fertig: 'bereit',
  fehler: 'ging nicht',
  tageslimit: 'Tageslimit für Anhänge erreicht. Morgen geht es wieder.',
  hoechstzahl: `Es sind schon ${ANHAENGE_MAX} Anhänge ausgewählt — mehr geht je Nachricht nicht.`,
  unbekannt: 'Das hat nicht geklappt. Bitte später noch einmal versuchen.',
  bildOeffnen: 'Groß ansehen',
  herunterladen: 'Herunterladen',
})

// ── Die eingestellte Anhangsgröße (CHAT-12c) ────────────────────────────────

/**
 * Die Grenze aus der Serverantwort von `chat.meine_gespraeche` — `anhang_max_bytes`.
 *
 * Der Server schickt die WIRKSAME Grenze in Bytes (Einstellung der Gemeinde ×
 * 1024 × 1024). Sie ist maßgeblich; `ANHANG_MAX_BYTES` gilt NUR, wenn das Feld
 * fehlt oder unbrauchbar ist (alter Server) — dann ist 10 MB die ehrlichste
 * Aussage, die die Oberfläche machen kann.
 *
 * @param {object} antwort die Antwort von `chat.meine_gespraeche`
 * @returns {number} Grenze in Bytes (> 0, immer eine ganze Zahl)
 */
export function anhangMaxBytes(antwort) {
  const roh = antwort && typeof antwort === 'object' ? antwort.anhang_max_bytes : null
  if (roh === null || roh === undefined || roh === '') return ANHANG_MAX_BYTES
  const n = Number(roh)
  if (!Number.isFinite(n) || n <= 0) return ANHANG_MAX_BYTES
  return Math.floor(n)
}

/**
 * Wie viele MB sind das? Aus BYTES die Zahl aus dem Satz „max. 25 MB“.
 *
 * Ganze MB (der Server rechnet 1024 × 1024) werden ohne Nachkommastelle
 * genannt; ein krummer Wert (von Hand gesetzt) bekommt EINE Nachkommastelle
 * mit Komma — nie eine geratene ganze Zahl, die nicht stimmt.
 */
export function mbText(bytes) {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return String(ANHANG_MAX_MB)
  const mb = n / (1024 * 1024)
  if (Number.isInteger(mb)) return String(mb)
  return mb.toFixed(1).replace('.', ',')
}

// ── Größe und Typ (nur für die ANZEIGE) ─────────────────────────────────────

/**
 * Dateigröße in Worten: „824 B“, „12 kB“, „1,4 MB“.
 *
 * Bewusst dezimal (kB/MB) wie im Dateimanager: die Grenze von 10 MB heißt in
 * dieser Schreibweise 10 MB, nicht „9,5 MiB“.
 */
export function groesseText(bytes) {
  if (bytes === null || bytes === undefined || bytes === '') return ''
  const n = Number(bytes)
  if (!Number.isFinite(n) || n < 0) return ''
  if (n < 1000) return `${Math.round(n)} B`
  const kb = n / 1000
  if (kb < 1000) return `${kb < 10 ? kb.toFixed(1).replace('.', ',') : Math.round(kb)} kB`
  const mb = kb / 1000
  return `${mb.toFixed(1).replace('.', ',')} MB`
}

/**
 * Wie wird dieser Anhang GEZEIGT? `bild` | `pdf` | `audio` | `datei`.
 *
 * Entschieden wird am vom SERVER geprüften `mime` (nicht am Dateinamen) —
 * dieselbe Einteilung wie `ANHANG_BILDER` im Backend. HEIC ist ABSICHTLICH
 * `datei`: die wenigsten Browser zeichnen es, und ein „kaputtes“ Vorschaubild
 * wäre schlechter als eine ehrliche Dateizeile.
 */
export function anhangArt(anhang) {
  const mime = String(anhang?.mime || '').toLowerCase()
  if (mime === 'image/png' || mime === 'image/jpeg' || mime === 'image/webp') return 'bild'
  if (mime === 'application/pdf') return 'pdf'
  if (mime === 'audio/mpeg' || mime === 'audio/mp4' || mime === 'audio/ogg' || mime === 'audio/opus') return 'audio'
  return 'datei'
}

/** Das Symbol eines Anhangs (Namen aus `components/ui/symbole.mjs`). */
export function anhangSymbol(anhang) {
  const art = anhangArt(anhang)
  if (art === 'pdf' || art === 'datei') return 'notiz'
  if (art === 'audio') return 'ton'
  return 'bild'
}

/** Der angezeigte Dateiname — ersatzweise aus der Kennung, NIE leer. */
export function anhangName(anhang) {
  const name = String(anhang?.dateiname || '').trim()
  if (name) return name
  const kennung = String(anhang?.name || '').trim()
  return kennung || 'Anhang'
}

// ── Adresse ─────────────────────────────────────────────────────────────────

/**
 * Adresse eines Anhangs: `chat.anhang?name=<kennung>` mit Dem Betriebs-Präfix.
 *
 * `basis` ist `apiUrl` (aus `shared/basis.js`) — hineingereicht, damit diese
 * Datei ohne DOM prüfbar bleibt und es KEINE zweite Adress-Logik gibt. Ohne
 * `basis` wird der nackte Pfad gebaut (dieselbe Form wie ohne Präfix).
 *
 * `apiUrl` liefert `/api/method/chat.anhang`; der Anhang braucht `?name=…`
 * GET-Form, damit ein `<a href>`/`<img src>` genügt (kein POST, kein Token).
 */
export function anhangUrl(name, basis = null) {
  const kennung = String(name || '').trim()
  if (!kennung) return ''
  const pfad = String((typeof basis === 'function' ? basis : apiUrl)('chat.anhang') || '')
  if (!pfad) return ''
  return `${pfad}?name=${encodeURIComponent(kennung)}`
}

// ── Die Liste der OFFENEN Anhänge (über der Eingabe) ────────────────────────

/**
 * Einen Eintrag der offenen Liste bauen.
 *
 * Zustände (`stand`):
 *   `laedt`  — der Upload läuft (Fortschritt unbekannt, kein Prozentwert:
 *              `fetch` meldet keinen, und eine geschätzte Zahl wäre geraten)
 *   `fertig` — der Server hat eine Kennung geliefert (`name`)
 *   `fehler` — `fehler` steht als Satz daneben; `name` ist leer
 *
 * `id` unterscheidet JEDEN Upload für sich — zwei Dateien mit demselben Namen
 * in derselben Sekunde sind damit zwei Einträge, und eine Antwort findet genau
 * ihren Chip. Ohne eigene `id` trafen sich zwei gleiche Dateien am selben
 * `schluessel`, und die zweite Antwort überschrieb den ersten Chip.
 *
 * `datei` bleibt für eine spätere lokale Vorschau am Eintrag (gebraucht wird
 * sie heute nicht: offene Anhänge sind beim Server nicht abrufbar, und die
 * Eingabezeile zeigt keine Vorschau, sondern Name/Größe/Stand).
 */
export function chipBauen(datei, { lauf = 0, gespraech = '', id = '' } = {}) {
  return {
    schluessel: String(id || `a${lauf}-${String(datei?.name || 'datei')}-${sizeVon(datei)}`),
    gespraech: String(gespraech || ''),
    lauf,
    datei: datei || null,
    dateiname: String(datei?.name || 'Datei'),
    groesse: sizeVon(datei),
    mime: String(datei?.type || ''),
    stand: 'laedt',
    name: '',
    fehler: '',
  }
}

function sizeVon(datei) {
  const n = Number(datei?.size)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

/**
 * Wie viele Plätze sind bei EINER Auswahl noch frei? Die Karte sagt: mehr als
 * 3 → freundliche Meldung, KEIN Upload. Gemeint ist die Zahl der Dateien, die
 * nach dieser Auswahl zusammen hingen — fertige, laufende UND die gerade
 * gewählten.
 *
 * `kaputt` = die Chips, deren Upload GESCHEITERT ist. Sie zählen NICHT mit:
 * drei Fehlschläge hintereinander blockierten sonst jede weitere Auswahl, ohne
 * dass je ein Anhang dastünde. Sie bleiben nur als Auskunft stehen, bis die
 * Person sie entfernt.
 *
 * `maxBytes` = die EINGESTELLTE Grenze aus `anhangMaxBytes(antwort)` (CHAT-12c).
 * Ohne Angabe gilt der Standard — der Rückfall für Aufrufe ohne Serverantwort,
 * NICHT eine zweite Wahrheit. Der Satz nennt immer die Zahl, gegen die
 * tatsächlich geprüft wurde („max. 25 MB“, wenn 25 eingestellt sind).
 */
export function auswahlPruefen(dateien, bereits = 0, kaputt = 0, maxBytes = ANHANG_MAX_BYTES) {
  const liste = Array.isArray(dateien) ? dateien.filter(Boolean) : []
  if (!liste.length) return { ok: false, text: '', dateien: [] }
  const belegt = Math.max(0, Number(bereits) || 0) - Math.max(0, Number(kaputt) || 0)
  if (belegt + liste.length > ANHAENGE_MAX) {
    return { ok: false, text: TEXTE.hoechstzahl, dateien: [] }
  }
  const grenze = Number.isFinite(Number(maxBytes)) && Number(maxBytes) > 0
    ? Number(maxBytes)
    : ANHANG_MAX_BYTES
  const zuGross = liste.find((d) => sizeVon(d) > grenze)
  if (zuGross) {
    return { ok: false, text: `${dateiText(zuGross)} ist zu groß (max. ${mbText(grenze)} MB).`, dateien: [] }
  }
  const leer = liste.find((d) => sizeVon(d) === 0)
  if (leer) {
    return { ok: false, text: `${dateiText(leer)} ist leer — dafür gibt es nichts zu senden.`, dateien: [] }
  }
  return { ok: true, text: '', dateien: liste }
}

/** Der Dateiname in Anführungszeichen — für Sätze über EINE Datei. */
function dateiText(datei) {
  return `„${String(datei?.name || 'Die Datei')}“`
}

/** Der Chip eines Kennung wechseln (unveränderlich — die Liste ist ein `ref`). */
export function chipAendern(liste, schluessel, werte) {
  return (Array.isArray(liste) ? liste : [])
    .map((c) => (c.schluessel === schluessel ? { ...c, ...werte } : c))
}

/** Einen Chip entfernen. */
export function chipEntfernen(liste, schluessel) {
  return (Array.isArray(liste) ? liste : []).filter((c) => c.schluessel !== schluessel)
}

/** Läuft noch ein Upload? Solange JA, ist Senden gesperrt (Karte Punkt 2). */
export function laedtNoch(liste) {
  return (Array.isArray(liste) ? liste : []).some((c) => c.stand === 'laedt')
}

/** Die Kennungen der FERTIGEN Anhänge — das ist, was `senden` mitnimmt. */
export function anhangKennungen(liste) {
  return (Array.isArray(liste) ? liste : [])
    .filter((c) => c && c.stand === 'fertig' && c.name)
    .map((c) => String(c.name))
}

/**
 * Darf JETZT gesendet werden?
 *
 * * nur mit offenem Gespräch,
 * * nicht während eines laufenden Uploads (der Server kennte die Kennung noch
 *   nicht — die Nachricht ginge ohne den Anhang hinaus),
 * * mit Text ODER mit mindestens einem fertigen Anhang („Foto ohne Worte“ ist
 *   im Server ausdrücklich erlaubt, `_pruefe_text(mit_anhang=True)`).
 */
export function darfSenden({ gespraech = '', text = '', liste = [], sendet = false } = {}) {
  if (!String(gespraech || '').trim()) return false
  if (sendet === true) return false
  if (laedtNoch(liste)) return false
  const kennungen = anhangKennungen(liste)
  if (kennungen.length) return true
  return String(text ?? '').trim().length > 0
}

/**
 * Was an `chat.senden` geht: Text und Anhänge.
 *
 * Der Text geht UNGETRIMMT hinaus (der Server trimmt nie, Zeilenumbrüche sind
 * Inhalt); nur die Entscheidung „leer“ schaut auf den Rand. `anhaenge` steht
 * NUR in der Anfrage, wenn es welche gibt — ein leeres Feld hieße „keine“,
 * wäre aber eine Aussage, die niemand gemacht hat.
 */
export function sendeRumpf({ gespraech, text = '', anhaenge = [], antwortAuf = '', erwaehnt = [] } = {}) {
  const rumpf = { gespraech: String(gespraech || ''), text: String(text ?? '') }
  if (antwortAuf) rumpf.antwort_auf = antwortAuf
  const kennungen = (Array.isArray(anhaenge) ? anhaenge : []).map(String).filter(Boolean)
  if (kennungen.length) rumpf.anhaenge = kennungen
  const personen = (Array.isArray(erwaehnt) ? erwaehnt : []).map(String).filter(Boolean)
  if (personen.length) rumpf.erwaehnt = personen
  return rumpf
}

// ── Antworten des Servers deuten ────────────────────────────────────────────

/**
 * Die Antwort von `chat.anhang_hochladen` prüfen.
 *
 * Ein Erfolg braucht eine KENNUNG (`name`) — ohne sie kann `senden` den Anhang
 * nicht mitnehmen, und die Datei wäre eine Waise im Verlauf. Fehlt sie, ist das
 * ein Fehler, kein „irgendwie fertig“.
 *
 * @returns {{ok: boolean, name: string, dateiname: string, mime: string, groesse: number, text: string}}
 */
export function uploadAntwort(antwort) {
  const roh = antwort && typeof antwort === 'object' ? antwort : {}
  const name = String(roh.name || '').trim()
  if (!name) return { ok: false, name: '', dateiname: '', mime: '', groesse: 0, text: TEXTE.unbekannt }
  return {
    ok: true,
    name,
    dateiname: String(roh.dateiname || ''),
    mime: String(roh.mime || ''),
    groesse: Number(roh.groesse) || 0,
    text: '',
  }
}

/**
 * Der Satz zu einem misslungenen Upload.
 *
 * 429 (`RateLimitError`, Tagesgrenze) bekommt den FESTEN Satz der Karte —
 * „Tageslimit für Anhänge erreicht“ —, weil der Servertext je nach Zähler
 * anders lauten darf. Alles andere ist die Server-Meldung; die ist für
 * Menschen geschrieben („Die Datei ist zu groß (max. 10 MB).“).
 */
export function uploadFehlerText(fehler, { ersatz = TEXTE.unbekannt } = {}) {
  const status = Number(fehler?.status)
  if (status === 429) return TEXTE.tageslimit
  const roh = String(fehler?.message || '').trim()
  if (roh) return roh
  return ersatz
}

/**
 * Die Anhänge EINER Nachricht aus dem Verlauf — IMMER eine Liste.
 *
 * Eine GELÖSCHTE Nachricht zeigt keine Anhänge: der Server schickt dort `[]`
 * (`_zeile`: `"anhaenge": [] if geloescht`), und ein alter Stand dürfte nichts
 * nachreichen. Deshalb entscheidet hier die Zeile, nicht die bloße Liste.
 */
export function zeilenAnhaenge(nachricht) {
  if (!nachricht || typeof nachricht !== 'object') return []
  if (nachricht.geloescht === true) return []
  const liste = Array.isArray(nachricht.anhaenge) ? nachricht.anhaenge : []
  return liste
    .filter((a) => a && typeof a === 'object' && String(a.name || '').trim())
    .map((a) => ({
      name: String(a.name),
      dateiname: anhangName(a),
      mime: String(a.mime || ''),
      groesse: Number(a.groesse) || 0,
      art: anhangArt(a),
    }))
}

// ── Laufnummer für Uploads ──────────────────────────────────────────────────

/**
 * Die Laufnummer EINES GESPRÄCHS — dieselbe Ordnung wie beim Sprung
 * (`nachrichtenTreffer.mjs`), aber pro Gespräch statt pro Upload.
 *
 * `neu()` liefert den AKTUELLEN Stand und erhöht ihn NICHT: alle Uploads
 * desselben Gesprächs laufen unter derselben Nummer. Das ist der Kern — zwei
 * Dateien auf einmal (oder eine zweite während der ersten) sind gleichzeitig
 * unterwegs, und KEINE von beiden darf die Antwort der anderen entwerten. Der
 * erste Entwurf zählte je Upload; dann blieb der erste Chip ewig bei „wird
 * hochgeladen …“, und Senden war dauerhaft gesperrt.
 *
 * Erhöht wird NUR bei `abbrechen()` — also beim Gesprächswechsel. Alle
 * laufenden Uploads sind damit entwertet: ihre späten Antworten kommen an,
 * finden ihre Nummer nicht mehr gültig und tragen nichts ein. Ohne das landete
 * der Anhang des alten Gesprächs in der Liste des neuen, und `chat.senden`
 * lehnte ihn mit „Anhang nicht gefunden.“ ab.
 *
 * Jeder Chip trägt zusätzlich seine EIGENE `id` (s. `chipBauen`): die
 * Laufnummer sagt „gehört dieser Upload noch zu diesem Gespräch“, die `id`
 * sagt „welcher Chip ist gemeint“.
 */
export function uploadLauf() {
  let generation = 1
  return {
    neu() { return generation },
    gilt(nummer) { return Number(nummer) === generation },
    abbrechen() { generation += 1 },
    stand: () => generation,
  }
}

// ── Gehört eine Upload-Antwort noch hierher? ────────────────────────────────

/**
 * Darf die Antwort eines Uploads den Chip noch ändern?
 *
 * Zwei Bedingungen, und beide werden gebraucht:
 *
 *   1. `gespraech` — die Antwort gehört zu dem Gespräch, in dem die Datei
 *      gewählt wurde. Der Wechsel kann WÄHREND des Uploads passiert sein.
 *   2. `lauf` — die Laufnummer des Gesprächs gilt noch (`uploadLauf`). Sie
 *      entwertet das, was der Gesprächswechsel ohnehin nicht abwarten konnte,
 *      und die Nachträge eines anderen Laufs.
 *
 * Warum das hier steht und nicht in der Seite: die Seite ist in `<script
 * setup>` geschrieben und kann nichts exportieren — und durch die Seite ist der
 * Gesprächswechsel im Node-Test nicht prüfbar (jsdom führt keine Navigation
 * aus, ein `location.hash`-Wechsel baut die Seite nicht neu auf). Als benannte
 * Funktion in dieser Datei prüft der Test sie einzeln und nachweislich.
 *
 * @param {{gespraech?: string, lauf?: number}} chip der Eintrag aus `chipBauen`
 * @param {{nummer?: number, gespraech?: string, gilt?: (n: number) => boolean}} jetzt
 *        die Lage JETZT: Nummer des Uploads, offenes Gespräch, Prüfung der
 *        Laufnummer (`uploadLauf().gilt`)
 * @returns {boolean}
 */
export function anhangAntwortGilt(chip, jetzt = {}) {
  const gemeint = String(chip?.gespraech ?? '')
  const offen = String(jetzt?.gespraech ?? '')
  if (gemeint !== offen) return false
  // `gilt` ist die EINE Quelle für „Laufnummer noch gültig“ — keine zweite Zählung.
  if (typeof jetzt?.gilt === 'function') return jetzt.gilt(jetzt?.nummer) === true
  return true
}
