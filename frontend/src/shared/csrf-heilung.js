/**
 * WEB-8b/WEB-8c — CSRF-Fehler im Client automatisch heilen.
 *
 * BEFUND (Manuel): „Wenn die Meldung 'CSRF-Token ungültig' kommt, soll ein
 * Force-Refresh beim Client kommen, damit es automatisiert geschieht." Bisher
 * führte die CSRF-Ablehnung des Servers (HTTP 417 + `exc_type=
 * CSRFTokenError`) direkt zur Anmeldemaske — obwohl der alte Token nur
 * veraltet sein muss (Tab lange offen, Sitzung im anderen Tab erneuert), die
 * Person aber angemeldet ist.
 *
 * ABLAUF (Orchestrator-Vorgabe C1–C4; EINE Wahrheit für alle Aufrufer):
 *
 *   1. Antwort ist keine CSRF-Ablehnung  -> unverändert weitergeben.
 *   2. Antwort ist eine CSRF-Ablehnung:
 *      a) EINMAL still ein frisches Token holen — über den vorhandenen Weg
 *         `diakronos.diakonos.api.session.sitzung_status` (liefert
 *         `{user, csrf_token}`; schon im Einsatz in
 *         `composables/useSitzungsablauf.js`, GET und vom CSRF-Zwang
 *         ausgenommen). Danach die ursprüngliche Anfrage genau EINMAL
 *         wiederholen.
 *      b) Scheitert schon der Token-Abruf (kein Token, z. B. 401), ist die
 *         Sitzung wirklich weg -> keine sinnlose Wiederholung, sondern
 *         Neuladen/Anmeldung (s. 3.).
 *      c) Scheitert die Wiederholung erneut mit `CSRFTokenError` ->
 *         `window.location.reload()` (Force-Refresh).
 *   3. Schleifenschutz (C2): höchstens 1 automatisches Neuladen pro 60 s
 *      (Zeitstempel in `sessionStorage`, Zugriff in try/catch). Innerhalb des
 *      Fensters wird NICHT neu geladen, sondern zur Anmeldung geleitet
 *      (`anmeldeUrl()`, präfixbewusst) mit dem Hinweis „Sitzung abgelaufen —
 *      bitte neu anmelden."
 *
 * NACHTRAG WEB-8c (Befunde aus dem Opus-Review, alle hier umgesetzt):
 *
 *   R2  `heileOderMelde({anfrage, res, data})` nimmt die ERSTE Antwort
 *       entgegen. Vorher rief jeder Aufrufer `anfrage()` und danach
 *       `heileOderMelde({anfrage})`, das `anfrage()` erneut ausführte — jede
 *       Heilung schickte die Anfrage einmal zu viel (Upload dreimal).
 *       Erwartet: genau DREI fetch-Aufrufe (Versuch, Token, Wiederholung).
 *   R3  Parallele Fehler: EIN gemeinsames Promise für den Token-Abruf (N
 *       parallele 417 -> 1 Token-Abruf) und die Kennzeichnung
 *       „Neuladen/Weiterleitung läuft" — weitere Aufrufer werfen nur noch,
 *       sie navigieren NICHT zusätzlich (sonst überschreibt
 *       `location.assign(login)` das `reload()`).
 *   R4  Der Hinweis aus C2 erschien nie. Der Hauptbereich öffnet den
 *       vorhandenen Dialog (`SitzungsHinweis.vue` über `sitzungBeendet`) und
 *       navigiert NICHT weg — dafür nehmen `zurAnmeldung()` und
 *       `neuLadenOderAnmelden()` die Option `ohneNavigation: true` (die
 *       Heilung kennt die SPA nicht). Die öffentlichen Bundles gehen auf die
 *       FESTE Kennung `?grund=csrf` (kein Freitext in der Adresse).
 *   R7  Ohne nutzbaren `sessionStorage` (wirft ODER fehlt) gibt es KEIN
 *       Auto-Reload: der Merker ginge über das Neuladen verloren, die Seite
 *       liefe in eine Endlosschleife. Dann geht es direkt zur Anmeldung mit
 *       Hinweis. `letzteHeilung()` liefert `null`, wenn es keinen
 *       `sessionStorage` gibt.
 *   R10 `csrf-heilung.js` importiert `sitzung-pruefen.js` NICHT mehr (der
 *       Zirkel ist aufgelöst): die einzige gemeinsame Regel
 *       `istSitzungsAbbruch` steht hier und `sitzung-pruefen.js` reicht sie
 *       weiter.
 *
 * NACHTRAG WEB-8d (zweite Opus-Nachbesserung):
 *
 *   M1  Gast-/Registrierungsseiten (WEB-8d M1): `heileOderMelde({gast: true})`
 *       überspringt den Token-Abruf (`sitzung_status` verlangt Anmeldung —
 *       ein Gast bekam 401 und landete auf `/login`, obwohl er kein Konto
 *       hat). Stattdessen: höchstens EIN Neuladen (frisches Seiten-Token,
 *       gleicher 60-s-Schutz wie C2), danach der feste Hinweis `GAST_HINWEIS`
 *       auf der Seite (`fehler.meldung`), NIEMALS eine Weiterleitung zur
 *       Anmeldung.
 *   N5  `sitzung-pruefen.js` importiert `istCsrfAblehnung` und
 *       `SITZUNGS_STATUS` von hier (eine Wahrheit statt Kopie).
 *   N6  `SITZUNG_GRUND` und `sitzungsFehler()` sind entfallen (ungenutzt).
 *
 * NACHTRAG WEB-8e (Restpunkte aus dem Opus-Review zu WEB-8d):
 *
 *   E1  Der Hauptbereich OHNE Navigation (SPA-Dialog) wurde bis hier mit
 *       `zurAnmeldung('neuLaden', {ohneNavigation: true})` gekennzeichnet —
 *       das setzte `neuLaden` UND `imBereich`. `useApi.js` wertete `neuLaden`
 *       als „es wird schon navigiert" und der Fehler erreichte den Dialog
 *       nie (`sitzungImBereich` war unerreichbar). Jetzt tragen diese Fehler
 *       NUR `imBereich` (`ohneNavigationFehler`), und `useApi.js` zeigt sie
 *       im vorhandenen Dialog.
 *   E2  Gastseiten: 401/419 (`SessionExpired`) lösen KEIN Neuladen mehr aus —
 *       dort gibt es keine Sitzung zu erneuern (Neuladen hätte die Eingaben
 *       verworfen und den Fehler nur verschoben). Es geht sofort die feste
 *       Meldung auf der Seite (`gastFehler({neuLaden:false})`); nur eine
 *       CSRF-Ablehnung nimmt den einmaligen Neulade-Weg.
 *   E3  Nach dem einmaligen Gast-Neuladen erscheint beim neuen Seitenleben
 *       EIN kurzer Hinweis (`gastNachNeuladen()` → `HINWEIS_NACH_NEULADEN`);
 *       der Merker dafür ist derselbe Zeitstempel wie der Schleifenschutz.
 *   E4  Der Text „Die Anmeldung wird neu geladen …" ist auf Gastseiten
 *       ersetzt: die Person hat kein Konto und wird nicht angemeldet.
 *
 * NACHTRAG WEB-8f (Nachbesserung des Opus-Reviews zu WEB-8e):
 *
 *   B1  `useApi.js` zeigt NUR noch Fehler mit `sitzung` im Sitzungsdialog
 *       (`if (fehler?.sitzung) throw sitzungImBereich(fehler); throw fehler`).
 *       Ein 417 `ValidationError`, ein 403 `PermissionError`, ein 500 oder ein
 *       Netzwerkfehler geht unverändert an den Aufrufer (Feldfehler,
 *       Rechtehinweis, Verbindungstext) — vorher meldete jeder dieser Fehler
 *       „Sitzung abgelaufen".
 *   B2  Der Gast-Einmal-Hinweis hängt an einem EIGENEN Merker
 *       (`dk-gast-hinweis`), nicht mehr am Schleifenschutz-Zeitstempel
 *       (`dk-csrf-neuladen`): der bleibt jetzt erhalten, deshalb lädt ein
 *       wiederkehrender CSRF-Fehler innerhalb von 60 s NICHT erneut (kein
 *       Verlust der Eingaben) und `GAST_HINWEIS` erscheint. Gesetzt wird der
 *       Hinweis-Merker ausschließlich von der Gast-Heilung; Heilungen im
 *       Hauptbereich und im Organigramm lösen ihn nicht aus.
 *   B3  VERHALTENSÄNDERUNG gegenüber WEB-8b/8c (dokumentiert in
 *       `docs/BETRIEBSANLEITUNG.md`, Abschnitt „CSRF-Heilung"): Der
 *       Hauptbereich lädt bei einer CSRF-Ablehnung NICHT mehr neu, sondern
 *       zeigt den vorhandenen Sitzungsdialog (`SitzungsHinweis.vue`). Der Weg
 *       ist: frisches Token holen -> Anfrage genau einmal wiederholen ->
 *       scheitert auch das, Dialog (kein Reload, keine Weiterleitung). Der
 *       R3-Test hält das als 1 -> 0 Neuladungen fest.
 *
 * SICHERHEIT DER WIEDERHOLUNG (C3): Die CSRF-Prüfung sitzt in der
 * `CsrfMiddleware` VOR der Ausführung der Methode. Eine mit 417 beantwortete
 * Anfrage hat den Server deshalb nachweislich nicht ausgeführt — die einmalige
 * Wiederholung ist damit auch für nicht idempotente Aufrufe unbedenklich. Eine
 * Wiederholung gibt es AUSSCHLIESSLICH in genau diesem Fall; 401/419
 * (`SessionExpired`) laufen unverändert in die Anmeldung.
 *
 * TOKEN (C4): Der Token wird nirgends protokolliert. Er lebt in
 * `window.__DIakonosBOOT.csrf_token` und im `<meta name="csrf-token">` — den
 * beiden Stellen, die die Aufrufer schon lesen.
 *
 * Warum eigenständige Datei ohne Vue: dieselbe Heilung braucht der
 * Hauptbereich (`useApi.js`) UND die eigenständigen Bundles
 * (`shared/sitzung-pruefen.js` für organigramm/registrierung/gast). Sie ist
 * deshalb so abhängigkeitsarm wie `basis.js` und wird von beiden benutzt.
 *
 * Wächter: `frontend/tests/web8c-csrf-nachbesserung.test.mjs` (und
 * `web8b-csrf-heilung.test.mjs` für den Grundablauf).
 */

// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl, anmeldeUrl } from './basis.js'

/** Merker der letzten automatischen Heilung (C2). */
export const NEULADEN_SCHLUESSEL = 'dk-csrf-neuladen'

/**
 * Eigener Merker „Gast-Hinweis steht noch aus" (WEB-8f B2).
 *
 * Vorher löschte `gastNachNeuladen()` den Zeitstempel `dk-csrf-neuladen` —
 * also denselben Schlüssel wie der 60-s-Schleifenschutz. Folge: nach dem
 * ersten Neuladen war der Schleifenschutz weg, jedes weitere Absenden mit
 * veraltetem Token lud erneut (Eingaben verloren), und weil auch der Merker
 * für den Hinweis weg war, erschien `GAST_HINWEIS` nie. Jetzt bleibt der
 * Zeitstempel unangetastet; nur die Gast-Heilung setzt diesen Schlüssel, und
 * nur `gastNachNeuladen()` nimmt ihn wieder weg (Einmal-Hinweis).
 */
export const GAST_HINWEIS_SCHLUESSEL = 'dk-gast-hinweis'

/** Mindestabstand zwischen zwei automatischen Neuladungen. */
export const NEULADEN_SPERRE_MS = 60_000

/** Hinweis, wenn das Neuladen nicht mehr erlaubt ist (C2). */
export const SITZUNG_HINWEIS = 'Sitzung abgelaufen — bitte neu anmelden.'

/**
 * Der FESTE Hinweis auf Gastseiten (WEB-8d M1): nennt das Neuladen, nicht die
 * Anmeldung — die Person hat kein Konto.
 */
export const GAST_HINWEIS =
  'Die Seite konnte nicht abgeschickt werden — bitte öffne sie neu und versuche es noch einmal. Dein Link bleibt gültig.'

/**
 * Text, während die Gastseite neu lädt (WEB-8e E4). Früher stand hier „Die
 * Anmeldung wird neu geladen …" — auf einer Seite ohne Konto falsch.
 */
export const GAST_NEULADEN_HINWEIS = 'Die Seite wird neu geladen …'

/**
 * Hinweis beim NEUEN Seitenleben nach dem einmaligen Gast-Neuladen
 * (WEB-8e E3): Die Eingaben sind weg, die Person muss wissen warum.
 */
export const HINWEIS_NACH_NEULADEN =
  'Die Seite wurde neu geladen, bitte Eingaben prüfen.'

/** Text des Neuladens im Hauptbereich (dort ist die Anmeldung das Ziel). */
export const NEULADEN_HINWEIS = 'Die Anmeldung wird neu geladen …'

/** Feste Kennung für die Anmeldemaske (R4): kein Freitext in der Adresse. */
export const GRUND_CSRF = 'csrf'

/** Status, die für sich schon ein Sitzungsende sind (401/419 `SessionExpired`). */
export const SITZUNGS_STATUS = [401, 419]

/**
 * Ist die Antwort eine CSRF-Ablehnung (417 + `exc_type=CSRFTokenError`)?
 *
 * Genau diese eine Form erzeugt der Server (`CsrfMiddleware._csrf_ablehnung`,
 * `frappe_compat/auth_middleware.py`) — unverändert seit WEB-8b.
 */
export function istCsrfAblehnung(res, data) {
  return res?.status === 417 && String(data?.exc_type || '') === 'CSRFTokenError'
}

/**
 * Ist die Antwort ein Sitzungsabbruch? Neben 401/419 zählt auch der
 * CSRF-Ablauf (417 + `CSRFTokenError`) — der alte Token ist dann wertlos.
 *
 * Steht hier (und nicht in `sitzung-pruefen.js`), damit die Heilung die
 * Sitzungsprüfung nicht importieren muss (R10: kein Zirkel).
 */
export function istSitzungsAbbruch(status, data) {
  if (SITZUNGS_STATUS.includes(status)) return true
  return istCsrfAblehnung({ status }, data)
}

/**
 * Der (angezeigte) Hinweis zum Sitzungsende — fest, nie aus der Adresse
 * übernommen (R4). Im Hauptbereich reicht ihn der Fehler an den vorhandenen
 * Dialog weiter (`sitzungsHinweis`).
 */
/**
 * Kennzeichnung „Neuladen oder Weiterleitung läuft bereits" (R3). Weitere
 * Aufrufer werfen diesen Fehler nur noch — sie navigieren NICHT zusätzlich.
 */
function laeuftFehler(art) {
  const fehler = new Error('Die Sitzung wird bereits erneuert …')
  fehler.name = 'SitzungWirdErneuert'
  fehler.sitzung = true
  fehler.hinweis = SITZUNG_HINWEIS
  if (art === 'neuLaden') fehler.neuLaden = true
  else fehler.weitergeleitet = true
  return fehler
}

/** Läuft gerade ein Neuladen oder eine Weiterleitung (R3)? */
let laufendeNavigation = ''

/** Frischer Token-Abruf, den sich alle Aufrufer teilen (R3). */
let tokenAbruf = null

/**
 * Alle Zustände zurücksetzen, die ein Seitenleben lang gelten. Nur für Tests
 * gedacht (im Betrieb beginnt mit dem Neuladen ein frisches Modul).
 */
export function zustandZuruecksetzen() {
  laufendeNavigation = ''
  tokenAbruf = null
}

/** Daten einer Antwort — bevorzugt die schon gelesenen (`res.dkDaten`). */
export async function datenVon(res) {
  if (res && typeof res === 'object' && res.dkDaten !== undefined) return res.dkDaten
  return liesAntwort(res)
}

/**
 * Antwort robust lesen. Ein Proxy (500/502) liefert kein JSON; ein blindes
 * `res.json()` würde hier „Unexpected token …" werfen (UXD-R8).
 */
export async function liesAntwort(res) {
  let text = ''
  try {
    text = await res.text()
  } catch {
    return { message: `Serverfehler (HTTP ${res?.status})` }
  }
  if (!text) return { message: `Serverfehler (HTTP ${res?.status})` }
  try {
    return JSON.parse(text)
  } catch {
    return { message: `Serverfehler (HTTP ${res?.status})` }
  }
}

/** Ein einzelner Token-Abruf über den vorhandenen Endpunkt. */
async function tokenHolen() {
  try {
    const res = await fetch(apiUrl('diakronos.diakonos.api.session.sitzung_status'), {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) return ''
    const daten = await liesAntwort(res)
    const token = daten?.message?.csrf_token
    return typeof token === 'string' ? token : ''
  } catch {
    return ''
  }
}

/**
 * Frisches CSRF-Token der laufenden Sitzung — über den vorhandenen Endpunkt.
 *
 * R3: parallele Aufrufer teilen sich EINEN Abruf. Das gemeinsame Promise wird
 * nach dem Abruf wieder gelöst, damit ein späterer Fehler nicht den alten
 * (vielleicht inzwischen wieder abgelehnten) Token erneut verwendet.
 */
export function frischesToken() {
  if (!tokenAbruf) {
    tokenAbruf = tokenHolen().finally(() => { tokenAbruf = null })
  }
  return tokenAbruf
}

/**
 * Übernimmt einen neuen Token in BEIDE Quellen, die die Aufrufer lesen:
 * `window.__DIakonosBOOT.csrf_token` und das Meta-Element (Kalender-/Upload-
 * Aufrufer). Leere Werte werden nie übernommen — ein geratener Token wäre
 * schlimmer als der alte.
 */
export function tokenUebernehmen(token) {
  if (!token) return false
  try {
    if (globalThis.window?.__DIakonosBOOT) globalThis.window.__DIakonosBOOT.csrf_token = token
  } catch { /* Boot-Objekt gesperrt: dann bleibt nur das Meta-Element */ }
  try {
    const meta = globalThis.document?.querySelector?.('meta[name="csrf-token"]')
    meta?.setAttribute?.('content', token)
  } catch { /* kein Dokument (Fremdkontext) */ }
  return true
}

/**
 * Zeitstempel der letzten Heilung (>= 0) oder `null`, wenn der Speicher gar
 * nicht nutzbar ist (R7: fehlend ODER werfend). In diesem Fall gibt es kein
 * Auto-Reload (der Merker ginge über das Neuladen verloren -> Schleife).
 */
export function letzteHeilung() {
  let speicher
  try {
    speicher = globalThis.sessionStorage
  } catch {
    return null
  }
  if (!speicher || typeof speicher.getItem !== 'function') return null
  let roh = null
  try {
    roh = speicher.getItem(NEULADEN_SCHLUESSEL) ?? null
  } catch {
    return null
  }
  const wert = Number(roh)
  return Number.isFinite(wert) && wert > 0 ? wert : 0
}

/**
 * Zeitstempel der letzten Heilung setzen.
 *
 * @returns {boolean} `true`, wenn er für das nächste Seitenleben gespeichert
 *   ist. `false` = kein nutzbarer Speicher (dann darf NICHT neu geladen werden,
 *   R7 — sonst Endlosschleife).
 */
function heilungMerken(jetzt) {
  try {
    const speicher = globalThis.sessionStorage
    if (!speicher || typeof speicher.setItem !== 'function') return false
    speicher.setItem(NEULADEN_SCHLUESSEL, String(jetzt))
    return speicher.getItem(NEULADEN_SCHLUESSEL) !== null
  } catch {
    return false
  }
}

/**
 * Merker „Gast-Hinweis steht noch aus" setzen (WEB-8f B2).
 *
 * @returns {boolean} `true`, wenn er gespeichert ist (sonst erscheint der
 *   Hinweis beim nächsten Seitenleben nicht — nie ein Fehlerfall).
 */
function hinweisMerken() {
  try {
    const speicher = globalThis.sessionStorage
    if (!speicher || typeof speicher.setItem !== 'function') return false
    speicher.setItem(GAST_HINWEIS_SCHLUESSEL, '1')
    return speicher.getItem(GAST_HINWEIS_SCHLUESSEL) !== null
  } catch {
    return false
  }
}

/**
 * Zur Anmeldemaske (C2) — präfixbewusst über `anmeldeUrl()`, mit Rücksprung
 * auf die aktuelle Adresse samt Hash und der festen Kennung `grund=csrf`.
 *
 * Der Hinweis selbst reist NICHT als Freitext in die Adresse (sonst könnte
 * jeder beliebigen Text einschleusen): `grund=csrf` bildet die Anmeldeseite
 * auf den festen Text `SITZUNG_HINWEIS` ab. Im Hauptbereich erscheint der
 * Hinweis zusätzlich über den bestehenden Dialog (`SitzungsHinweis.vue`).
 *
 * `art` ('neuLaden' | 'weitergeleitet') landet am Fehler, damit die
 * Gast-/Registrierungsseiten (R8) nichts rendern, während navigiert wird.
 *
 * `ohneNavigation` (Hauptbereich): der Fehler trägt NUR `imBereich` — die
 * SPA zeigt den vorhandenen Dialog und navigiert NICHT. Der frühere
 * Doppelmerker `neuLaden` + `imBereich` ließ `useApi.js` „es wird schon
 * navigiert" annehmen, der Dialog blieb aus (WEB-8e E1).
 */
export function zurAnmeldung(art = 'weitergeleitet', { ohneNavigation = false } = {}) {
  if (!ohneNavigation) {
    const ziel =
      (globalThis.location?.pathname || '') +
      (globalThis.location?.search || '') +
      (globalThis.location?.hash || '')
    try {
      globalThis.location?.assign?.(anmeldeUrl(ziel, GRUND_CSRF))
    } catch { /* keine Navigation möglich (Fremdkontext) */ }
  }
  // Der Aufrufer hat die Anzeige selbst uebernommen (SPA-Dialog).
  if (ohneNavigation) return imBereichFehler(SITZUNG_HINWEIS, 'SitzungAbgelaufen')
  const fehler = new Error(SITZUNG_HINWEIS)
  fehler.name = 'SitzungAbgelaufen'
  fehler.sitzung = true
  fehler.hinweis = SITZUNG_HINWEIS
  if (art === 'neuLaden') fehler.neuLaden = true
  else fehler.weitergeleitet = true
  return fehler
}

/**
 * Fehler für „Sitzung ist weg, aber im Hauptbereich OHNE Navigation"
 * (WEB-8e E1). Merkmale: `sitzung` + `imBereich` — und absichtlich WEDER
 * `neuLaden` (Seite lädt neu) NOCH `weitergeleitet` (Anmeldemaske). Nur so
 * erreicht der Fehler `mitSitzungsdialog` in `useApi.js` und damit den
 * vorhandenen Dialog; `useApi.js` leitet
 * `navigiertBereits = (neuLaden || weitergeleitet) && !imBereich` daraus ab.
 */
export function imBereichFehler(hinweis = SITZUNG_HINWEIS, name = 'SitzungAbgelaufen') {
  const fehler = new Error(hinweis)
  fehler.name = name
  fehler.sitzung = true
  fehler.imBereich = true
  fehler.hinweis = hinweis
  return fehler
}

/**
 * Force-Refresh oder — im Sperrfenster bzw. ohne Speicher — die Anmeldemaske
 * (C2/R7). Die Navigation passiert GENAU EINMAL (R3): weitere Aufrufer
 * bekommen nur den Fehler.
 */
export function neuLadenOderAnmelden(jetzt = Date.now(), { ohneNavigation = false } = {}) {
  // Hauptbereich: die SPA zeigt den Dialog und laedt NICHT neu — auch kein
  // Merker, damit die naechste echte Pruefung normal entscheiden darf.
  if (ohneNavigation) return imBereichFehler(SITZUNG_HINWEIS, 'SitzungAbgelaufen')

  if (laufendeNavigation) return laeuftFehler(laufendeNavigation)

  if (neuladenErlaubt(jetzt) && heilungMerken(jetzt)) {
    laufendeNavigation = 'neuLaden'
    try {
      globalThis.location?.reload?.()
    } catch { /* kein Neuladen möglich */ }
    const fehler = new Error(NEULADEN_HINWEIS)
    fehler.name = 'NeuLaden'
    fehler.sitzung = true
    fehler.neuLaden = true
    fehler.hinweis = SITZUNG_HINWEIS
    return fehler
  }

  // Kein (weiteres) Neuladen: entweder im 60-s-Fenster (C2) oder ohne
  // nutzbaren Speicher (R7). Dann direkt zur Anmeldung mit Hinweis.
  laufendeNavigation = 'weitergeleitet'
  return zurAnmeldung('neuLaden')
}

/** Darf jetzt automatisch neu geladen werden (C2/R7)? */
export function neuladenErlaubt(jetzt = Date.now()) {
  const zuletzt = letzteHeilung()
  // Ohne nutzbaren Speicher KEIN Neuladen (R7): der Merker wäre nach dem
  // Neuladen weg, die Seite liefe endlos.
  if (zuletzt === null) return false
  if (!zuletzt) return true
  return jetzt - zuletzt >= NEULADEN_SPERRE_MS
}

/**
 * Sitzungsende auf einer GASTSEITE (WEB-8d M1) — ohne Anmeldung, ohne
 * `/login`. Die Person hat kein Konto; ein Token-Abruf über
 * `session.sitzung_status` endete für sie nur in 401. Eine CSRF-Ablehnung
 * bekommt höchstens EIN frisches Seiten-Token (Neuladen, Schleifenschutz wie
 * C2); alles andere (auch 401/419, WEB-8e E2) meldet sofort auf der Seite
 * (`meldung`).
 *
 * E4: der Text nennt NIE die Anmeldung — auf einer Gastseite wird niemand
 * angemeldet. Er beschreibt nur, was die Seite gerade tut bzw. tun soll.
 */
function gastFehler({ neuLaden }) {
  const fehler = new Error(neuLaden ? GAST_NEULADEN_HINWEIS : GAST_HINWEIS)
  fehler.name = neuLaden ? 'NeuLaden' : 'GastSitzungAbgelaufen'
  fehler.sitzung = true
  fehler.gast = true
  if (neuLaden) fehler.neuLaden = true
  // Die Seite zeigt ihren FESTEN Text (kein Freitext aus der Adresse).
  else fehler.meldung = true
  fehler.hinweis = GAST_HINWEIS
  return fehler
}

/**
 * Gastweg: KEIN Token-Abruf (der verlangt Anmeldung). NUR eine CSRF-Ablehnung
 * bekommt höchstens EIN automatisches Neuladen (frisches Seiten-Token);
 * alles andere meldet sofort (`WEB-8e E2`). Der Schleifenschutz ist derselbe
 * wie im Hauptbereich (C2/R7) — ohne nutzbaren `sessionStorage` gibt es kein
 * Neuladen, weil der Merker sonst über das Neuladen verloren ginge
 * (Endlosschleife). NIEMALS eine Weiterleitung zur Anmeldemaske.
 */
function gastHeilen(jetzt, { ohneNavigation = false, art = 'meldung' } = {}) {
  // Ein Aufrufer hat das Neuladen schon ausgelöst: hier nur noch melden.
  if (laufendeNavigation) return gastFehler({ neuLaden: false })

  // WEB-8e E2: ein 401/419 (Sitzung weg) ist auf einer Gastseite keine
  // CSRF-Frage — die Sitzung lässt sich hier nicht erneuern. Neuladen würde
  // nur die Eingaben verwerfen und den Fehler verschieben.
  if (art !== 'csrf') return gastFehler({ neuLaden: false })

  if (!ohneNavigation && neuladenErlaubt(jetzt) && heilungMerken(jetzt)) {
    laufendeNavigation = 'neuLaden'
    try {
      globalThis.location?.reload?.()
    } catch { /* kein Neuladen möglich (Fremdkontext) */ }
    // WEB-8f B2: eigener Merker für den Einmal-Hinweis, unabhängig vom
    // 60-s-Zeitstempel — nur die Gast-Heilung setzt ihn.
    hinweisMerken()
    return gastFehler({ neuLaden: true })
  }
  return gastFehler({ neuLaden: false })
}

/**
 * Hinweis nach dem einmaligen Gast-Neuladen (WEB-8e E3 / WEB-8f B2).
 *
 * Der Zeitstempel `dk-csrf-neuladen` (Schleifenschutz) bleibt UNANGETASTET —
 * er entscheidet weiter, ob ein weiteres Neuladen erlaubt ist. Der Hinweis
 * hängt an einem eigenen Merker `dk-gast-hinweis`, den ausschließlich die
 * Gast-Heilung (`gastHeilen`, Art `csrf`) setzt. Heilungen im Hauptbereich
 * und im Organigramm lösen den Gast-Hinweis deshalb nicht aus.
 *
 * @returns {boolean} `true` = den Hinweis zeigen (genau einmal)
 */
export function gastNachNeuladen() {
  try {
    const speicher = globalThis.sessionStorage
    if (!speicher || typeof speicher.getItem !== 'function') return false
    if (speicher.getItem(GAST_HINWEIS_SCHLUESSEL) === null) return false
    speicher.removeItem(GAST_HINWEIS_SCHLUESSEL)
    return true
  } catch {
    return false
  }
}

/**
 * Zentrale Heilung für APIs, die ihren Aufruf selbst wiederholen können.
 *
 * @param {{anfrage: () => Promise<Response>, res?: Response, data?: object,
 *          ohneNavigation?: boolean, gast?: boolean}} optionen
 *   `res`/`data` (R2): die ERSTE Antwort des Aufrufers. Liegt sie vor, beginnt
 *   die Heilung direkt beim Token-Abruf — es gibt keinen zusätzlichen
 *   Fach-Aufruf. Fehlt sie, wird `anfrage()` genau einmal ausgeführt.
 *   `anfrage` MUSS den (möglicherweise erneuerten) Token bei jedem Aufruf
 *   frisch lesen — sonst trüge die Wiederholung wieder den alten.
 *   `gast` (WEB-8d M1): Seite ohne Konto (Gast-/Registrierungslink). Kein
 *   Token-Abruf, kein zweiter Versuch mit leerem Token, nie `/login`.
 * @returns {Promise<object>} `{res, data}` der Antwort, die der Aufrufer wie
 *   gewohnt auswertet (Erfolg oder ein Fehler, der NICHT CSRF ist).
 * @throws {Error} Sitzungsende / erschöpfte Heilung (s. `neuLadenOderAnmelden`);
 *   diese Fehler tragen `sitzung` und `neuLaden` ODER `weitergeleitet`
 *   (Gastseiten stattdessen `gast` und `neuLaden` ODER `meldung`).
 */
export async function heileOderMelde({ anfrage, res, data, ohneNavigation = false, gast = false } = {}) {
  if (!res) res = await anfrage()
  if (data === undefined) data = await datenVon(res)

  // Reihenfolge ist wichtig: `istSitzungsAbbruch()` zählt den CSRF-Ablauf
  // selbst als Sitzungsende (das war bis WEB-8b die einzige Reaktion). Erst
  // prüfen, ob es eine CSRF-Ablehnung ist — die wird geheilt; danach der
  // echte Sitzungsabbruch (401/419 `SessionExpired`) -> unverändert zur
  // Anmeldung (C3), ohne Wiederholung und ohne Neuladen. Alles andere wird
  // 1:1 weitergegeben (z. B. 417 `ValidationError`).
  if (gast) {
    // WEB-8d M1: Auf einer Gastseite gibt es keine Sitzung, die man erneuern
    // könnte — kein Token-Abruf, nie `/login`.
    // WEB-8e E2: NUR eine CSRF-Ablehnung nimmt den einmaligen Neulade-Weg;
    // 401/419 meldet sofort auf der Seite (kein Neuladen, keine Meldung erst
    // nach einem verlorenen Formular).
    if (istCsrfAblehnung(res, data)) throw gastHeilen(Date.now(), { ohneNavigation, art: 'csrf' })
    if (istSitzungsAbbruch(res.status, data)) throw gastHeilen(Date.now(), { ohneNavigation, art: 'meldung' })
    return mitDaten(res, data)
  }

  if (!istCsrfAblehnung(res, data)) {
    if (istSitzungsAbbruch(res.status, data)) {
      if (laufendeNavigation) throw laeuftFehler(laufendeNavigation)
      // Der Hauptbereich (ohneNavigation) zeigt den Dialog und navigiert
      // nicht — dann keinen Navigationsmerker setzen (WEB-8e E1).
      if (!ohneNavigation) laufendeNavigation = 'weitergeleitet'
      throw zurAnmeldung('weitergeleitet', { ohneNavigation })
    }
    return mitDaten(res, data)
  }

  // (a) EINMAL still ein frisches Token holen (parallele Aufrufer teilen sich
  // den Abruf, R3) und genau einmal wiederholen.
  const token = await frischesToken()
  if (!token) {
    // Ohne frisches Token ist die Sitzung nicht zu retten: kein sinnloser
    // zweiter Versuch, sondern der gemeldete Weg (Neuladen/Anmeldung).
    if (ohneNavigation) throw imBereichFehler(SITZUNG_HINWEIS, 'SitzungAbgelaufen')
    throw neuLadenOderAnmelden()
  }
  tokenUebernehmen(token)
  if (laufendeNavigation) throw laeuftFehler(laufendeNavigation)
  const wieder = await anfrage()
  const wiederDaten = await datenVon(wieder)

  // (b) Heilung hat nicht gereicht -> Force-Refresh (mit Schleifenschutz).
  if (istCsrfAblehnung(wieder, wiederDaten)) {
    // Nach einer echten Wiederholung gilt der 60-s-Schutz (C2) auch im
    // Hauptbereich: dann oeffnet der Aufrufer den Dialog statt zu laden.
    throw neuLadenOderAnmelden(Date.now(), { ohneNavigation })
  }

  return mitDaten(wieder, wiederDaten)
}

/**
 * Hängt die bereits gelesenen Daten an die Antwort, damit Aufrufer sie nicht
 * ein zweites Mal lesen müssen (`res.text()` ist nach dem ersten Lesen leer).
 */
function mitDaten(res, data) {
  if (res && typeof res === 'object') {
    try {
      res.dkDaten = data
    } catch { /* eingefrorene Attrappe: Aufrufer liest selbst */ }
  }
  return { res, data }
}
