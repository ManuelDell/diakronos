/**
 * useRueckgaengig — zentraler Rückgängig-Stapel für die ganze Anwendung.
 *
 * Die Buchführung (wer ist zurückholbar, in welcher Reihenfolge, wie lange)
 * liegt in `rueckgaengigStapel.mjs` und ist dort ohne Browser geprüft. Diese
 * Datei verbindet sie mit der Oberfläche:
 *
 *  * EINE Meldung je Aktion (unten links), `ANZEIGE_MS` lang (10 s, dieselbe
 *    Zeit wie die Frist der Aktion) mit „Rückgängig“;
 *  * Strg+Z / Cmd+Z außerhalb von Eingabefeldern nimmt die letzte Aktion
 *    zurück (Prinzip S5 — „Bekannte Muster“);
 *  * die Tastenkombination ist ANGEKÜNDIGT: „Rückgängig (Strg+Z)“ steht in
 *    der Meldung, damit niemand raten muss;
 *  * Meldungen halten an, solange der Zeiger darüber steht oder der Fokus
 *    darin ist (man will den Knopf treffen, nicht die Uhr).
 *
 * NACHTRAG UX2a2 (Befunde aus dem Review, je Punkt geprüft):
 *  F1  Schlägt die Rücknahme fehl, wird das GEMELDET (showToast … 'error'),
 *      nicht verschluckt — `zuruecknehmen` fängt den Fehler selbst ab.
 *  F2  `zuruecknehmen(id)` übergibt IMMER die Uhrzeit ({ jetzt: Date.now() }).
 *      Damit gilt die Frist (`ANZEIGE_MS`, seit MT-3 10 s) auch für den Klick
 *      auf die Meldung: nach dem Tab-Schlaf ist eine zehn Minuten alte Aktion
 *      nicht mehr rückgängig.
 *  F3  Nach dem Schließen fällt der Fokus auf ein sinnvolles Ziel (den Knopf
 *      der nächsten Meldung, sonst den Auslöser von vorher, sonst die
 *      Hauptfläche der Seite) — nie auf `<body>` (WCAG 2.2.1).
 *  F4  Der Esc-Zuhörer des Meldungsdienstes wird beim Entfernen ABGEMELDET
 *      (keine Anhäufung); Esc schließt nur die oberste Meldung, nicht wenn
 *      ein Dialog offen ist, und nimmt den Eintrag aus dem Stapel (kein
 *      spätes Strg+Z auf eine Meldung, die niemand mehr sieht).
 *  F5  Die Positionsklasse `--undo` am Behälter fällt weg, sobald keine
 *      Rückgängig-Meldung mehr offen ist (Fehlermeldungen bleiben oben rechts).
 *  F6  Strg+UMSCHALT+Z ist KEIN Rückgängig (das ist „Wiederholen“),
 *      `ereignis.repeat` wird ignoriert, und die Meldungsgrenze verdrängt
 *      keine Fehlermeldungen.
 *
 * VERWENDUNG (UX2c stellt die Seiten darauf um)
 *   import { useRueckgaengig } from '../../composables/useRueckgaengig.js'
 *   const { registrieren } = useRueckgaengig()
 *   const { id } = registrieren('Aus Gruppe entfernt', async () => {
 *       await apiCall('POST', '/api/…/zuruecknehmen')
 *   })
 *
 * `registrieren` meldet eine BEREITS AUSGEFÜHRTE Aktion an; es führt nichts
 * aus. Die Rücknahme-Funktion führt die Gegenrichtung aus und darf async
 * sein. Wirft sie, bleibt die Aktion NICHT erneut zurückholbar (sie ist ja
 * versucht) und der Nutzer bekommt eine Fehlermeldung (F1).
 */
import { ref } from 'vue'
import {
  RueckgaengigStapel,
  ABlaufMS,
  GRENZE,
  HALTE_DECKEL_MS,
} from './rueckgaengigStapel.mjs'
// UX2a2b: `istGespraechOffen` gehört dazu — der Meldungsdienst entscheidet
// jetzt selbst über Esc, der Stapel fragt ihn nicht mehr.
import { showToast, entferneToast, istGespraechOffen, ANZEIGE_MS } from './useToast.js'
// UX2a2c: Die Floskel-Erkennung kommt aus dem Fehlerkatalog (UX2g) — eine
// Quelle für „das ist keine Auskunft“.
import { istFloskel } from '../../shared/fehlertexte.js'

/**
 * F1: Der Fehlerkatalog-Text zu einem gescheiterten Aufruf.
 *
 * Dieselbe Staffelung wie `fehlerText` in `usePlanrahmen.js` (dort steht sie
 * fuer die Planrahmen-Bausteine), hier bewusst als kleine eigene Funktion:
 * `useRueckgaengig` wird von der GANZEN App benutzt, ein Import aus dem
 * Planrahmen-Modul zoege dessen Umfang in jede Seite. Kommt ein Fehler mit
 * eigener Meldung vom Server, gewinnt sie — sie sagt „was jetzt“.
 */
export function fehlerMeldung(fehler) {
  if (!fehler) return 'Das hat nicht geklappt. Bitte versuche es später noch einmal.'
  const status = Number(fehler.status)
  if (status === 401 || status === 419) return 'Die Sitzung ist abgelaufen — bitte neu anmelden.'
  if (status === 403) return 'Dafür fehlt dir die Berechtigung.'
  if (status === 404) return 'Der Eintrag wurde nicht gefunden.'
  if (status === 405) return 'Diese Aktion ist hier nicht erlaubt.'
  const text = typeof fehler.meldung === 'string' ? fehler.meldung.trim() : ''
  if (text) return text
  // UX2a2c (nach UX2g): Die Floskel-Liste steht EINMAL im Fehlerkatalog
  // (`shared/fehlertexte.js`). Hier stand eine eigene Kopie mit drei Wörtern —
  // „Fehler beim Laden“, „Ein Fehler ist aufgetreten“ und die übrigen alten
  // Rahmen gingen daran vorbei und landeten als Meldung im Toast.
  const nachricht = typeof fehler.message === 'string' ? fehler.message.trim() : ''
  if (nachricht && !istFloskel(nachricht)) return nachricht
  return 'Das hat nicht geklappt. Bitte versuche es später noch einmal.'
}

/** EIN Stapel für die ganze Sitzung — wie beim Fensterstapel. */
const stapel = new RueckgaengigStapel({ grenze: GRENZE, ablaufMs: ABlaufMS })

/** Anzahl der gerade zurückholbaren Aktionen (für Anzeigen und Tests). */
export const rueckgaengigAnzahl = ref(0)

/** Ids, zu denen gerade eine Meldung offen ist: Eintrags-Id → Meldungs-Id. */
const offeneMeldungen = new Map()

/** Läuft der Takt, der abgelaufene Meldungen abräumt? */
let takt = null
let zuhoererZaehler = 0
let tastaturAngemeldet = false
let meldungZaehler = 0

/**
 * F4: Kennung DIESES Stands der Verbindung. Der Zuhörer am Fenster trägt sie
 * mit; sein Tastendruck nimmt nur Aktionen an, die derselbe Stand angemeldet
 * hat. Nach einem Seitenwechsel bleibt kein alter Zuhörer wirksam.
 */
const vorgang = { name: 'rueckgaengig', erlaubt: [], kette: [] }
let vorgangAktiv = false

/** F3: Wer den Fokus vor dem Schließen der Meldung hatte. */
let fokusVorher = null

/**
 * F3: Wer hatte zuletzt den Fokus? Wird beim Schließen einer Meldung
 * gebraucht — fällt der Fokus sonst auf `<body>`, beginnen Tastaturnutzer
 * wieder bei null (WCAG 2.2.1 „Tastatur“).
 */
function beiFokus(ereignis) {
  const ziel = ereignis?.target
  if (!ziel || typeof ziel.closest !== 'function') return
  fokusVorher = ziel.closest('.diakonos-toast') || ziel
}
if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
  document.addEventListener('focusin', beiFokus, true)
}

/**
 * Ist das Ereignisziel ein Eingabefeld, in dem Strg+Z dem Text gilt?
 *
 * Rückgängig im TEXT ist eine andere Sache als Rückgängig in der App: wer im
 * Feld „Name“ gerade getippt hat und Strg+Z drückt, will den Buchstaben
 * zurück — nicht das Löschen von vorhin. Alles, was Text aufnimmt, ist
 * deshalb ausgenommen (`contenteditable` ebenso wie Eingabefelder).
 */
export function istEingabefeld(ziel) {
  if (!ziel || typeof ziel !== 'object') return false
  const tag = String(ziel.tagName || '').toLowerCase()
  if (tag === 'textarea' || tag === 'select' || tag === 'input') return true
  if (ziel.isContentEditable === true) return true
  return String(ziel.getAttribute?.('contenteditable') || '').toLowerCase() === 'true'
}

/**
 * Ist das die Rückgängig-Tastenkombination dieses Systems?
 *
 * Strg+Z ist der Windows-/Linux-Standard, Cmd+Z der auf dem Mac (Prinzip S5).
 *
 * UX2a2 (F6): Strg+UMSCHALT+Z ist es NICHT. Auf Windows und in Textfeldern
 * bedeutet Umschalt+Z „Wiederholen“, und die Rücknahme einer Rücknahme gibt
 * es hier nicht — die Tastenkombination soll niemanden überraschen.
 * Ebenso zählt ein Wiederholungs-Ereignis (`ereignis.repeat`, Taste gehalten)
 * nicht: eine gehaltene Taste darf nicht den ganzen Stapel abräumen.
 */
export function istRueckgaengigTaste(ereignis) {
  if (!ereignis) return false
  if (ereignis.altKey === true || ereignis.shiftKey === true) return false
  if (ereignis.repeat === true) return false
  const taste = String(ereignis.key || '').toLowerCase()
  if (taste !== 'z') return false
  return ereignis.ctrlKey === true || ereignis.metaKey === true
}

/** Kurzbeschreibung der Tastenkombination für die Meldung. */
export function tastaturHinweis() {
  const mac = typeof navigator !== 'undefined'
    && /Mac|iPhone|iPad|iPod/i.test(String(navigator.platform || navigator.userAgent || ''))
  return mac ? '⌘Z' : 'Strg+Z'
}

/**
 * Ist gerade ein Dialog offen? Dann gehört Esc dem Dialog, nicht der Meldung.
 *
 * UX2a2b (E1): Die Prüfung steht in `useToast.js` — dort entscheidet der EINE
 * Esc-Zuhörer. Es zählt, was im DOM steht (`aria-modal`), nicht was ein
 * Zähler behauptet: Dialoge verschiedener Bausteine (DkDialog, DkModal,
 * Mehr-Blatt, Kalender) melden sich unterschiedlich an, die Rolle setzen
 * sie alle.
 */

/**
 * F3: Ein sinnvolles Fokusziel nach dem Schließen einer Meldung.
 *
 * Reihenfolge: das Element, das den Fokus vorher hatte · der Knopf der
 * nächsten offenen Rückgängig-Meldung · die Hauptfläche der Anwendung.
 * `<body>` ist KEIN Ziel: dort fängt jede Tastaturbedienung wieder bei null
 * an (WCAG 2.2.1 „Tastatur“).
 */
export function fokusZiel(gehabt) {
  const kandidaten = []
  // 1. Stand der Fokus in einer MELDUNG? Dann gehört er in die Meldungsfamilie
  //    (der Knopf der geschlossenen Meldung verschwindet ja gerade).
  const inMeldung = Boolean(gehabt && typeof gehabt.closest === 'function'
    && gehabt.closest('.diakonos-toast'))
  if (!inMeldung && gehabt && gehabt.isConnected !== false
      && `${gehabt.className}`.split(/\s+/).includes('diakonos-toast')) {
    kandidaten.push(gehabt)          // gehabt WAR die Meldung selbst
  }
  // 2. Der Knopf der nächsten offenen Rückgängig-Meldung (zuletzt angemeldet
  //    zuerst) — dahin gehört der Fokus, wenn er aus einer Meldung kam.
  const ids = [...offeneMeldungen.values()]
  for (let i = ids.length - 1; i >= 0; i -= 1) {
    const el = findeMeldung(ids[i])
    const knopf = el && knopfIn(el)
    if (knopf) { kandidaten.push(knopf); break }
  }
  // 3. Die Hauptfläche der Anwendung (nie `<body>`).
  //
  // UX2a2b (F3): `.dk-content` ist das Ziel aus `App.vue` — `#dk-inhalt`,
  // tabindex="-1", das Sprungziel „Zum Inhalt springen". Fehlte es hier, fiel
  // der Fokus in der fertigen App auf `<body>`, obwohl der Rückfall gedacht
  // war. `[data-fokus-start]` und `main` bleiben als frühere Ziele erhalten.
  if (typeof document !== 'undefined' && typeof document.querySelector === 'function') {
    kandidaten.push(document.querySelector(
      '[data-fokus-start], .dk-main, main, [role="main"], #dk-inhalt, .dk-content',
    ))
  }
  return kandidaten.find(el => el && typeof el.focus === 'function'
    && el.isConnected !== false) || null
}

/** Die Meldung mit dieser Id im Dokument (Attribut `data-meldung`). */
function findeMeldung(meldungId) {
  if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return null
  return document.querySelector(`[data-meldung="${meldungId}"]`)
}

/** Der erste Knopf in einem Knoten (auch in der DOM-Attrappe der Tests). */
function knopfIn(el) {
  if (!el) return null
  if (typeof el.querySelector === 'function') {
    const t = el.querySelector('button')
    if (t) return t
  }
  const istKnopf = (k) => `${k.tagName}`.toUpperCase() === 'BUTTON'
  const suchen = (knoten) => {
    for (const k of knoten.children || []) {
      if (istKnopf(k)) return k
      const tief = suchen(k)
      if (tief) return tief
    }
    return null
  }
  return suchen(el)
}


/**
 * F3: Fokus zurückgeben — nur wenn er sonst auf `<body>` fiele.
 *
 * UX2a2b (F2): Der Fokus wird NUR gestohlen, wenn er in der schließenden
 * Meldung stand — Fokus auf `<body>` bleibt, wo er ist.
 * Vorher rief `beiMeldungZu` diese Funktion bei jedem Grund außer „klick“ —
 * ein alter Toast, der nebenbei abgelaufen ist, riss den Nutzer damit aus
 * dem Feld, in dem er gerade tippte.
 *
 * @param {object|null} [ausMeldung]  Die Meldung, die gerade schließt. Ohne
 *        Angabe gilt `fokusVorher` (Stand beim Klick auf „Rückgängig“).
 */
function fokusSichern(ausMeldung = fokusVorher) {
  if (typeof document === 'undefined') return
  const aktiv = document.activeElement
  // UX2a2c (Review): NUR der schließende Toast zählt. Vorher genügte
  // `closest('.diakonos-toast')` — lief eine Rückgängig-Meldung ab, während
  // der Fokus auf dem ✕ einer Fehlermeldung stand, galt das als „in der
  // Meldung“ und der Fokus wurde auf `<body>` bzw. ein anderes Ziel
  // geschoben. Der Mensch verlor seinen Platz mitten in der Arbeit.
  const inMeldung = Boolean(aktiv && ausMeldung
    && (aktiv === ausMeldung
      || (typeof ausMeldung.contains === 'function' && ausMeldung.contains(aktiv))))
  if (!inMeldung) {
    // Der Nutzer arbeitet woanders (Eingabefeld, Knopf …) — Finger weg.
    fokusVorher = null
    return
  }
  const ziel = fokusZiel(ausMeldung)
  if (ziel && ziel !== aktiv) {
    try { ziel.focus() } catch { /* nicht fokussierbar — dann eben nicht */ }
  }
  fokusVorher = null
}

/**
 * Die Meldung zu einer angemeldeten Aktion zeigen. Sie wird über `useToast`
 * gebaut (ein Aussehen, eine Stelle, Tokens aus tokens.css) und bekommt
 * genau EINEN Knopf: „Rückgängig“. Das Schließen-Kreuz entfällt, weil die
 * Meldung ihre Aktion selbst anbietet — zwei Knöpfe auf derselben kurzen
 * Fläche wären eine Auswahl, die niemand braucht.
 */
function meldungZeigen(eintrag) {
  const id = `rueckgaengig-${eintrag.id}-${++meldungZaehler}`
  // UX2a2b (F1): Die Meldung hält die Frist der AKTION mit an. Solange der
  // Zeiger darüber steht oder der Fokus darin ist, darf der 250-ms-Takt den
  // Eintrag nicht abräumen (der Toast-Timer pausiert ja auch) — sonst steht
  // „Rückgängig“ noch, der Klick darauf tut aber nichts mehr.
  let entfernen = null
  const anhalten = () => { stapel.pausieren(eintrag.id, Date.now()) }
  const weiterlaufen = (restMs) => {
    stapel.fortsetzen(eintrag.id, {
      jetzt: Date.now(),
      deckelMs: Number.isFinite(restMs) ? restMs : HALTE_DECKEL_MS,
    })
    taktSichern(true)
    aktualisieren()
  }
  // UX2a2 (Befund aus der Abnahme): Die Zuordnung steht VOR dem Anzeigen in
  // der Liste. Sonst sahen `positionSichern` (der Takt, 250 ms) und ein
  // Zeiger, der im selben Zug auf der Meldung landet, eine leere Liste: die
  // Klasse `--undo` fiel weg, die Meldung sprang von unten links nach oben
  // rechts — unter dem Zeiger weg — und die Frist lief weiter.
  offeneMeldungen.set(eintrag.id, id)
  entfernen = showToast(eintrag.beschreibung, 'undo', {
    text: 'Rückgängig',
    beschriftung: `Rückgängig: ${eintrag.beschreibung} (${tastaturHinweis()})`,
    onClick: () => { zuruecknehmen(eintrag.id) },
  }, {
    schliessen: false,
    id,
    // MT-3 (Manuel 11.11.): Die Meldung steht `ANZEIGE_MS` — und ihre Aktion
    // ist GENAU SO LANGE zurückholbar (`ABlaufMS` leitet sich seit der
    // Review-Nacharbeit aus derselben Zahl ab). Vorher waren es zwei Zeiten
    // (8 s Frist, 10 s Anzeige): die Aktion lief mitten in der sichtbaren
    // Meldung ab. Eine Zeit für beides.
    dauer: ANZEIGE_MS,
    onPause: anhalten,
    onWeiter: weiterlaufen,
    // UX2a2 (F3): Fokus im Blick behalten, damit er nach dem Schließen nicht
    // auf `body` fällt; UX2a2b (F2): nur, wenn er in DIESER Meldung stand.
    beiSchliessen: (grund) => {
      beiMeldungZu(eintrag.id, grund, entfernen && entfernen.el)
    },
    // UX2a2 (F4)/UX2a2b (E1): Esc schließt die oberste Meldung — der
    // Meldungsdienst nimmt sie; die Rückgängig-Meldung sagt nur „nein“,
    // solange ihre Verbindung nicht mehr lebt.
    darfEsc: () => typeof document !== 'undefined' && vorgangAktiv,
  })
  positionSichern()
  return entfernen
}

/**
 * Eine Rückgängig-Meldung ist zu (Esc, Klick, Frist).
 *
 * F3: Fokus retten, wenn er in dieser Meldung stand.
 * F4: Grund „esc“ heißt: der Nutzer hat die Meldung weggeschoben — ihren
 *     Eintrag aus dem Stapel nehmen, sonst nähme ein spätes Strg+Z eine
 *     Aktion zurück, die niemand mehr sieht.
 * UX2a2b (F2): `knoten` ist die Meldung, die gerade schließt — nur wenn der
 *     Fokus DARIN stand, wird er weitergegeben.
 */
function beiMeldungZu(eintragId, grund, knoten) {
  // Die Zuordnung kann schon weg sein (Ablauf über `aktualisieren`).
  const eintrag = stapel.alle().find(e => e.id === eintragId)
  // F4: Esc schiebt die Meldung weg — der Eintrag verlässt den Stapel, sonst
  // nähme ein spätes Strg+Z eine Aktion zurück, die niemand mehr sieht.
  if (grund === 'esc' && eintrag) {
    stapel.verwerfen(eintragId)
  }
  // UX2a2c (Review): Wurde die Meldung VERDRÄNGT (Grenze erreicht, neue
  // Aktion gemeldet), hielt ihr Eintrag die Frist noch an — `pruefen` räumt
  // angehaltene Einträge nie ab, die Aktion bliebe also ewig zurückholbar,
  // ohne dass eine Meldung den Knopf noch anbietet. Hier wird sie wieder
  // losgelassen und läuft mit dem REST ihrer Frist weiter (`deckelMs: 0`:
  // keine neue Gnadenfrist, der Ablauf ist sofort erreicht).
  else if (grund !== 'klick' && eintrag && eintrag.haelt) {
    stapel.fortsetzen(eintragId, { jetzt: Date.now(), deckelMs: 0 })
  }
  offeneMeldungen.delete(eintragId)
  // F3: Fokus auf ein sinnvolles Ziel setzen, wenn er in DIESER Meldung stand
  // (sonst faellt er beim naechsten Tab auf `<body>`).
  // Beim Klick auf „Rückgängig" nicht: dort arbeitet der Nutzer mit der Maus
  // weiter. `fokusVorher` wird IMMER verworfen — ein Stand von vorhin darf
  // keinen spaeteren Fokus stehlen.
  if (grund !== 'klick') fokusSichern(knoten || fokusVorher)
  else fokusVorher = null
  aktualisieren()
}

/**
 * F5: Die Klasse `--undo` (unten links) steht nur am Behälter, solange eine
 * Rückgängig-Meldung offen ist. Fehlermeldungen bleiben oben rechts.
 *
 * UX2a2 (Befund aus der Browser-Abnahme): Der Takt (250 ms) und das
 * Schließen einer Meldung riefen diese Funktion auch dann, wenn die
 * Rückgängig-Meldung eben erst aufgeklappt ist und der Zeiger schon darauf
 * steht. Die Klasse fiel dann weg, der Behälter sprang nach oben rechts —
 * die Meldung wanderte UNTER dem Zeiger weg, `mouseleave` feuerte, und die
 * Frist lief weiter, obwohl der Nutzer sie festhalten wollte. Deshalb: die
 * Klasse bleibt, solange eine Rückgängig-Meldung beim Meldungsdienst offen
 * ist (die führt jede Meldung, nicht nur die des Stapels).
 */
function positionSichern() {
  if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return
  const behaelter = document.querySelector('.diakonos-toast-container')
  if (!behaelter || !behaelter.classList) return
  const offen = offeneMeldungen.size > 0
  const steht = behaelter.classList.contains('diakonos-toast-container--undo')
  if (offen && !steht) behaelter.classList.add('diakonos-toast-container--undo')
  else if (!offen && steht) behaelter.classList.remove('diakonos-toast-container--undo')
}

/**
 * F3/F4: Läuft eine Uhr? Ja, solange eine Aktion offen ist ODER eine Meldung
 * noch steht (nach dem Zurücknehmen läuft ihre Anzeige-Uhr weiter, bis sie
 * ausblendet). Sonst wird der Takt abgeräumt — die Seite bleibt ruhig.
 */
function laeuftEineUhr() {
  return stapel.laenge > 0 || offeneMeldungen.size > 0
}

/** Takt starten/stoppen — nur solange es etwas zu prüfen gibt. */
function taktSichern(an) {
  if (an && !takt) {
    takt = setInterval(() => {
      stapel.pruefen(Date.now())
      aktualisieren()
    }, 250)
    // In Node (Tests) existiert `unref` — sonst hielte der Takt den Lauf offen.
    if (typeof takt?.unref === 'function') takt.unref()
  } else if (!an && takt) {
    clearInterval(takt)
    takt = null
  }
}

/** Anzeigen (Anzahl) und offene Meldungen mit dem Stapel abgleichen. */
function aktualisieren() {
  // F3/F4: Die Meldung weiss, ob ihre Aktion noch offen ist.
  for (const [eintragId, meldungId] of [...offeneMeldungen]) {
    const el = findeMeldung(meldungId)
    if (el && typeof el.setAttribute === 'function') {
      el.setAttribute('data-offen', stapel.alle().some(e => e.id === eintragId) ? 'true' : 'false')
    }
  }
  rueckgaengigAnzahl.value = stapel.laenge
  for (const [eintragId, meldungId] of [...offeneMeldungen]) {
    if (stapel.alle().some(e => e.id === eintragId)) continue
  offeneMeldungen.delete(eintragId)
    entferneToast(meldungId)
  }
  taktSichern(laeuftEineUhr())
  // F4: Der Zuhörer hängt nur, solange es etwas zurückzunehmen gibt.
  tastaturSichern(stapel.hoerer > 0 && stapel.laenge > 0)
  positionSichern()
}

/**
 * F4: Tastatur-Zuhörer anhängen, solange DIESER Stand der Verbindung lebt.
 *
 * Vorher hing er am Bestand des Stapels: war der Stapel kurz leer (Aktion
 * zurückgenommen, nächste Seite), blieb der Zuhörer des alten Stands am
 * Fenster und ein Strg+Z auf der neuen Seite nahm still eine Aktion zurück,
 * die zu einer ganz anderen Ansicht gehörte. Jetzt gilt: angemeldet beim
 * ersten `useRueckgaengig()`, abgemeldet beim letzten `abmelden()`.
 */
function tastaturSichern(an, zielUebergabe = null) {
  const ziel = zielUebergabe || (typeof window !== 'undefined' ? window : null)
  if (!ziel) return
  // F4: Der Zuhörer hängt, solange jemand zuhört (`hoerer > 0`, gepflegt von
  // `useRueckgaengig`/`abmelden`) UND es etwas zurückzunehmen gibt. Zusätzlich
  // löst er sich, wenn eine Taste auf einen veralteten Stapel trifft.
  const will = typeof an === 'boolean' ? an : (stapel.hoerer > 0)
  if (will && !tastaturAngemeldet) {
    ziel.addEventListener('keydown', beiTaste)
    tastaturAngemeldet = true
  } else if (!will && tastaturAngemeldet) {
    ziel.removeEventListener('keydown', beiTaste)
    tastaturAngemeldet = false
  }
}

async function beiTaste(ereignis) {
  // F6: Strg+Umschalt+Z („Wiederholen“) und gehaltene Tasten zählen nicht.
  if (!istRueckgaengigTaste(ereignis)) return
  if (istEingabefeld(ereignis.target)) return
  if (!vorgangAktiv) return
  // F4: Ein Zuhörer aus einem ALTEN Stand greift GAR NICHT ein — auch nicht
  // mit `preventDefault`: die neue Seite behält ihr Verhalten (Text-Rücknahme
  // des Browsers in Feldern, eigene Kürzel).
  if (!stapel.hoert(vorgang)) {
    tastaturSichern(false)
    return
  }
  // F4: Nach einem Sprung in der Zeit (Tab-Schlaf) fällt der Zuhörer ab,
  // sobald der Stapel leer ist. Das räumt die gehaltene Taste gleich mit auf.
  if (stapel.laenge === 0) {
    tastaturSichern(false)
    return
  }
  ereignis.preventDefault()
  // F2: Die Uhrzeit geht IMMER mit (auch hier, nicht nur beim Klick).
  // F1: Ein Fehler landet als Meldung — das erledigt `zuruecknehmen` selbst.
  await zuruecknehmen({ jetzt: Date.now(), kraft: vorgang })
}

/**
 * Die letzte Aktion zurücknehmen (oder eine bestimmte).
 *
 * Zwei Aufrufformen, wie bisher:
 *   zuruecknehmen()        — den obersten Eintrag (Strg+Z)
 *   zuruecknehmen(id)      — genau diesen (Klick auf die Meldung)
 *
 * F2: Die Uhrzeit wird IMMER mitgegeben (beide Formen „jetzt“). Ohne sie
 * hätte der Klick auf eine Meldung die Frist übersprungen: ein Tab, der
 * Stunden schläft, zeigte die alte Meldung noch — und ein Klick darauf nähme
 * eine längst abgelaufene Aktion zurück.
 *
 * F1: Ein Fehler der Rücknahme wird gemeldet (Fehlerkatalog-Text aus
 * `fehlerText`), das Promise aber NICHT abgelehnt — sonst verlöre ein
 * `onClick`-Aufruf im Meldungsdienst den Fehler still.
 *
 * @param {(number|{jetzt?: number, kraft?: object})} [idOderOptionen]
 * @param {{ jetzt?: number }} [optionen]
 * @returns {Promise<object|null>} der zurückgenommene Eintrag oder `null`
 */
export async function zuruecknehmen(idOderOptionen, optionen = {}) {
  const istId = typeof idOderOptionen === 'number'
  const id = istId ? idOderOptionen : undefined
  const vorgaben = istId ? (optionen || {}) : (idOderOptionen || {})
  const jetzt = Number.isFinite(vorgaben.jetzt) ? vorgaben.jetzt : Date.now()
  const befehl = { jetzt }
  if (vorgaben.kraft) befehl.kraft = vorgaben.kraft
  else if (vorgangAktiv) befehl.kraft = vorgang
  // F3: Hatte der Nutzer den Fokus in einer Meldung? Dann bleibt er in der
  // Familie der Meldungen, statt auf `body` zu fallen.
  if (typeof document !== 'undefined' && typeof document.activeElement?.closest === 'function') {
    fokusVorher = document.activeElement.closest('.diakonos-toast') || null
  }
  try {
    return await stapel.zuruecknehmen(id ?? befehl, istId ? befehl : undefined)
  } catch (fehler) {
    // F1: Der Stapel hat den Eintrag bereits verbraucht (genau einmal
    // versucht). Jetzt sagt die App, dass es nicht geklappt hat.
    showToast(fehlerMeldung(fehler), 'error')
    return null
  } finally {
    aktualisieren()
  }
}

stapel.beobachten(aktualisieren)

/** Der Stapel selbst (für Anzeigen und Prüfungen). */
export function getStapel() {
  return stapel
}

/**
 * Zugang für Seiten und Bausteine.
 *
 * F4: Jeder Aufruf meldet einen Zuhörer an. `abmelden()` MUSS beim Verlassen
 * der Seite gerufen werden (`onBeforeUnmount`) — dann fällt der Zuhörer am
 * Fenster, sobald der letzte Vorgang weg ist.
 *
 * @returns {{ registrieren: Function, zuruecknehmen: Function,
 *             abmelden: Function, anzahl: typeof rueckgaengigAnzahl,
 *             getStapel: Function }}
 */
export function useRueckgaengig() {
  // F4: Der Strg+Z-Zuhörer hängt ab dem ersten Zugang (und bleibt, solange
  // der letzte Zugang nicht `abmelden()` gerufen hat). So hängt NICHT für
  // jeden Bestand ein neuer Zuhörer am Fenster.
  zuhoererZaehler += 1
  stapel.hoerer = zuhoererZaehler
  if (!vorgangAktiv) {
    vorgangAktiv = true
    stapel._vorgang = vorgang
    tastaturSichern(true)
  }
  let abgemeldet = false
  const abmelden = () => {
    if (abgemeldet) return
    abgemeldet = true
    zuhoererZaehler = Math.max(0, zuhoererZaehler - 1)
    stapel.hoerer = zuhoererZaehler
    if (zuhoererZaehler === 0) {
      vorgangAktiv = false
      stapel._vorgang = null
      // F4: Erst jetzt fällt der Zuhörer am Fenster.
      tastaturSichern(false)
    }
  }
  return {
    registrieren,
    zuruecknehmen,
    abmelden,
    anzahl: rueckgaengigAnzahl,
    getStapel,
  }
}

/**
 * Eine sofort ausgeführte Aktion anmelden. Gibt `{ id, beschreibung }` zurück.
 * @param {string} beschreibung
 * @param {Function} rueckgaengigFn
 */
export function registrieren(beschreibung, rueckgaengigFn) {
  // F4: Wer anmeldet, ist ab jetzt ein Zuhörer — ohne Zugang über
  // `useRueckgaengig()` (z. B. ein Baustein, der nur anmeldet) hinge der
  // Strg+Z-Zuhörer sonst nie am Fenster.
  if (!vorgangAktiv) {
    zuhoererZaehler += 1
    stapel.hoerer = zuhoererZaehler
    vorgangAktiv = true
    stapel._vorgang = vorgang
    tastaturSichern(true)
  }
  const eintrag = stapel.registrieren(beschreibung, rueckgaengigFn, {
    jetzt: Date.now(),
    vorgang,
    neu: true,
  })
  meldungZeigen(eintrag)
  aktualisieren()
  return eintrag
}

/**
 * Für Tests und beim Abmelden: alles vergessen, Meldungen entfernen.
 * Führt KEINE Rücknahme aus.
 */
export function rueckgaengigZuruecksetzen() {
  stapel.leeren()
  aktualisieren()
  offeneMeldungen.clear()
  positionSichern()
  zuhoererZaehler = 0
  stapel.hoerer = 0
  vorgangAktiv = false
  stapel._vorgang = null
  tastaturSichern(false)
  fokusVorher = null
}

/** Nur für Tests: die Tastatur einmalig an die Attrappe hängen. */
export function _tastaturAnmelden() {
  vorgangAktiv = true
  stapel._vorgang = vorgang
  stapel.hoerer = Math.max(1, stapel.hoerer)
  if (typeof window === 'undefined') return
  if (!tastaturAngemeldet) {
    window.addEventListener('keydown', beiTaste)
    tastaturAngemeldet = true
  }
}

/** Nur für Tests: ist der Zuhörer am Fenster angemeldet? */
export function _tastaturAngemeldet() {
  return tastaturAngemeldet
}

export { ABlaufMS, GRENZE, RueckgaengigStapel }
