/**
/**
 * Ein Rückmeldedienst: JEDE Meldung blendet nach 10 s aus (`ANZEIGE_MS`),
 * gleich welcher Art; der Schließen-Knopf bleibt.
 *
 * UX2g: Ein leerer Text oder eine der alten Floskeln („Fehler",
 * „Unbekannter Fehler", „API-Fehler") ist keine Auskunft. Statt eines
 * eigenen Ersatzsatzes fragt der Toast den Fehlerkatalog
 * (`shared/fehlertexte.js`): er nennt, was passiert ist und was jetzt hilft.
 *
 * UX2a: Erfolge liefen vier Sekunden, Rückgängig-Meldungen acht — beides
 * heißt seit MT-3 `ANZEIGE_MS` (10 s, eine Zahl für alle Typen).
 *
 * UX2a2 (Review-Befunde):
 *  F4  Der Esc-Zuhörer wird beim Entfernen ABGEMELDET. Vorher blieb für jede
 *      gezeigte Meldung ein `keydown`-Zuhörer am Dokument hängen — nach einer
 *      Stunde Arbeit Tausende, jeder mit einer eigenen Prüfung. Jetzt hängt
 *      er nur, solange die Meldung offen ist, und fragt beim Drücken, ob
 *      diese Meldung überhaupt schließen DARF (`darfEsc`: oberste Meldung,
 *      kein offener Dialog, Verbindung lebt noch).
 *  F5  Beim Schließen einer Meldung fällt die Positionsklasse `--undo` am
 *      Behälter weg, wenn keine Rückgängig-Meldung mehr offen ist — sonst
 *      stünden Fehlermeldungen danach unten links statt an ihrem Ort.
 *  F6  Die Grenze verdrängt keine Fehlermeldungen. Vorher hieß es hier
 *      „Fehler bleiben, bis der Nutzer sie schließt“ — das ist seit MT-3
 *      überholt: ALLE Meldungen blenden nach `ANZEIGE_MS` aus, auch Fehler.
 *      Der Grund für F6 bleibt trotzdem richtig: eine Fehlermeldung wird
 *      nicht als erste verdrängt, weil sie sagt, was jetzt zu tun ist.
 *
 * UX2a2b (Restbefunde aus dem Review):
 *  E1  Esc schließt die OBERSTE Meldung — gleich welcher Art (auch eine
 *      Fehlermeldung), und keine, solange ein Dialog offen ist. Vorher
 *      entschied jede Meldung selbst (`darfEsc` sagte nur die
 *      Rückgängig-Meldung); eine Fehlermeldung ließ Esc laufen, und die
 *      oberste Rückgängig-Meldung konnte unter einer Fehlermeldung
 *      verschwinden. Jetzt gibt es EINEN Zuhörer am Dokument, der genau die
 *      oberste offene Meldung schließt (siehe `escSchliessen`).
 */
import { fehlertext, istFloskel } from '../../shared/fehlertexte.js'
// MT-3: die eine Zeit für Anzeige UND Frist der Aktion (eigene Datei, damit
// sie ohne Import-Zyklus auch im Rückgängig-Stapel steht).
import { ANZEIGE_MS } from './meldungszeit.mjs'

/**
 * MT-3 (Manuel 11.11.): EINE Zeit für ALLES, was mit einer Meldung zu tun hat
 * (ms): 10 Sekunden.
 *
 * Befund vorher: Meldungen oben rechts blieben dauerhaft stehen. Ursache war
 * die Sonderregel `error: 0` („bis zum Schließen“) und die kurzen 4 s für
 * Erfolge.
 *
 * Review-Nacharbeit (Operator, 11.11.): Sie ist außerdem die FRIST der
 * Rückgängig-Aktion — vorher standen dort 8 s (`ABlaufMS` im Stapel), und die
 * Aktion lief mitten in der noch sichtbaren Meldung ab. Zwei Zeiten für EINE
 * Sache („wie lange habe ich für diese Meldung“) waren eine Falle: die
 * Anzeige war schneller vorbei als die Frist oder umgekehrt, und der Bericht
 * dazu war falsch. Jetzt: Anzeige = Frist = `ANZEIGE_MS`.
 *
 * Die Zahl selbst steht in `meldungszeit.mjs` (der Stapel braucht sie auch;
 * eine Zahl in DIESER Datei schlösse einen Import-Zyklus). Hier wird sie
 * hereingeholt und weitergereicht, damit alle Aufrufer `ANZEIGE_MS` wie
 * gewohnt aus diesem Modul beziehen können.
 *
 * ACHTUNG beim Schreiben von Kommentaren in DIESER Datei: die Import-
 * Umschreiber einiger Tests suchen die Modulangabe per Muster über den
 * GANZEN Dateitext — auch über Kommentare. Steht hier ein Zitat der
 * Import-Zeile (Modulangabe in Anführungszeichen), hält der Umschreiber
 * das für einen echten Selbst-Import und läuft endlos in die Tiefe
 * („Maximum call stack size exceeded"). Kommentare nennen die Herkunft
 * deshalb ohne Anführungszeichen-Modulangabe.
 */
export { ANZEIGE_MS }
/**
 * Wie lange eine Meldung steht (ms), je Typ.
 *
 * MT-3: EINE Zahl (`ANZEIGE_MS`) für alle Typen — abgeleitet, nicht
 * abgeschrieben. `normal`, `error`, `warning` und `mitAktion` sind bewusst
 * derselbe Wert; steht hier künftig etwas anderes, ist das eine bewusste
 * Entscheidung an DIESER Stelle.
 *
 * Review-Nacharbeit: `warning` wird von `showToast` NICHT eigens gelesen —
 * `showToast` fragt nur „Fehler?“, „Aktion?“ oder „sonst“. Der Eintrag bleibt
 * als Auskunft für Aufrufer stehen, die die Typ-Dauer selbst nachschlagen
 * (`DAUER_MS[typ]`), und weil ein fehlender Schlüssel hier eine Lücke wäre;
 * der Test sagt jetzt genau das und keine Wirkung, die es nicht gibt.
 */
export const DAUER_MS = {
    error: ANZEIGE_MS,
    warning: ANZEIGE_MS,
    mitAktion: ANZEIGE_MS,
    normal: ANZEIGE_MS,
}

/**
 * UX2a2: So lange ÜBER die Anzeigedauer hinaus dürfen Zeiger/Fokus eine
 * Meldung festhalten (Grenze gegen „hängt für immer").
 */
export const HALTE_ZUSATZ_MS = 20000

/**
 * Höchstens so viele Meldungen, wie der Rückgängig-Stapel hält
 * (`GRENZE` in rueckgaengigStapel.mjs). UX2a: Früher standen hier 3 und dort
 * 5 — die vierte Anmeldung verdrängte dann die Meldung der ÄLTESTEN Aktion,
 * deren Eintrag im Stapel aber stehen blieb: für den Nutzer war die Aktion
 * damit still verloren, obwohl der Stapel sie noch führte. EINE Zahl für
 * beides (importiert, nicht abgeschrieben).
 */
import { GRENZE as STAPEL_GRENZE } from './rueckgaengigStapel.mjs'
export const HOECHSTENS = STAPEL_GRENZE

export function rueckmeldeText(message, type) {
    const text = typeof message === 'string' ? message.trim() : ''
    if (type === 'error' && istFloskel(text)) {
        // Ohne verwertbaren Text bleibt die Lage unklar -> der Katalog nennt
        // den neutralen nächsten Schritt (Zustand „unbekannt").
        return fehlertext(null, {})
    }
    return text
}

/** Kennung für den nächsten Aufruf (einfacher Zähler, ohne Uhrzeit). */
let zaehler = 0

export function ensureContainer() {
    let container = document.querySelector('.diakonos-toast-container')
    if (!container) {
        // UX2a2b: Ein Behälter aus einem früheren Seitenstand zählt nicht —
        // sonst meldeten sich Meldungen an einem Knoten an, der gar nicht
        // mehr im Dokument hängt, und kein Tastendruck und kein Klick käme an.
        escZaehler = 0
        container = document.createElement('div')
        container.className = 'diakonos-toast-container'
        container.setAttribute('role', 'region')
        container.setAttribute('aria-label', 'Meldungen')
        document.body.appendChild(container)
    }
    return container
}

/** Aktuell offene Meldungen: `{ id, type, el, entfernen }`. */
export const offeneMeldungen = []

/**
 * UX2a2b (E1): Ist gerade ein Dialog/Gesprächsfluss offen? Dann gehört Esc
 * dem Dialog, nicht der Meldung.
 *
 * Es zählt, was im DOM steht (`aria-modal`, `role`), nicht was ein Zähler
 * behauptet: Dialoge verschiedener Bausteine (DkDialog, DkModal, Mehr-Blatt,
 * Kalender) melden sich unterschiedlich an, die Rolle setzen sie alle.
 * Steht hier (und nicht in `useRueckgaengig.js`), weil der Meldungsdienst
 * jetzt selbst über Esc entscheidet — ohne Rückgriff auf den Stapel.
 */
export function istDialogOffen() {
  if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return false
  return Boolean(document.querySelector(
    '[role="dialog"][aria-modal="true"], [role="alertdialog"][aria-modal="true"]',
  ))
}

/** Ist gerade ein anderer Dialog/Gesprächsfluss offen (auch ohne aria-modal)? */
export function istGespraechOffen() {
  if (istDialogOffen()) return true
  if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return false
  return Boolean(document.querySelector('[role="dialog"], [role="menu"], [role="alertdialog"]'))
}

/** Der EINE Esc-Zuhörer am Dokument (UX2a2b E1). */
let escZaehler = 0

/**
 * UX2a2b (E1): Esc schließt die OBERSTE offene Meldung — gleich welcher Art.
 *
 * Reihenfolge: die zuletzt gezeigte Meldung, die Esc annehmen möchte. Ein
 * offener Dialog hat Vorrang (Esc gehört ihm). Meldungen, die ausdrücklich
 * nicht per Esc schließen wollen (`darfEsc() === false`, z. B. eine Meldung
 * aus einem alten Seitenstand), werden übersprungen.
 *
 * @param {string} [grund]
 * @returns {boolean} true, wenn eine Meldung geschlossen wurde
 */
export function escSchliessen(grund = 'esc') {
  if (istGespraechOffen()) return false
  for (let i = offeneMeldungen.length - 1; i >= 0; i -= 1) {
    const eintrag = offeneMeldungen[i]
    if (typeof eintrag.darfEsc === 'function' && !eintrag.darfEsc()) continue
    eintrag.entfernen(grund)
    return true
  }
  return false
}

/** Der einzige Zuhörer: Esc ans Schließen geben. */
function beiEscTaste(ereignis) {
  if (!ereignis || ereignis.key !== 'Escape') return
  if (!escSchliessen('esc')) return
  if (typeof ereignis.stopPropagation === 'function') ereignis.stopPropagation()
}

/** Zuhörer anhängen, solange mindestens eine Meldung offen ist (E1). */
function escSichern() {
  if (typeof document === 'undefined') return
  const an = document.addEventListener
  const weg = document.removeEventListener
  const noetig = offeneMeldungen.length > 0
  if (noetig && escZaehler === 0 && typeof an === 'function') {
    document.addEventListener('keydown', beiEscTaste)
    escZaehler = 1
  } else if (!noetig && escZaehler === 1 && typeof weg === 'function') {
    document.removeEventListener('keydown', beiEscTaste)
    escZaehler = 0
  }
}

/** Schließt die Positionsklasse nach, wenn keine Rückgängig-Meldung mehr offen ist (F5). */
function positionNachziehen() {
    if (typeof document === 'undefined' || typeof document.querySelector !== 'function') return
    const container = document.querySelector('.diakonos-toast-container')
    // Nicht jede Umgebung liefert eine volle `classList` (Tests mit
    // schlanker Attrappe, sehr alte Einbettungen) — dann bleibt es beim
    // Standardplatz oben rechts, statt zu werfen.
    const liste = container && container.classList
    if (!liste || typeof liste.contains !== 'function') return
    const noetig = offeneMeldungen.some(m => m.type === 'undo')
    const steht = liste.contains('diakonos-toast-container--undo') === true
    if (noetig && !steht) liste.add('diakonos-toast-container--undo')
    else if (!noetig && steht) liste.remove('diakonos-toast-container--undo')
}

/**
 * Eine bestimmte Meldung entfernen (UX2a: wenn ihre Aktion abgelaufen ist).
 * @param {string} id
 */
export function entferneToast(id) {
    const index = offeneMeldungen.findIndex(e => e.id === id)
    if (index < 0) return false
    const [eintrag] = offeneMeldungen.splice(index, 1)
    eintrag.entfernen()
    return true
}

/** Alle Meldungen entfernen (Seitenwechsel, Abmelden, Tests). */
export function schliesseAlle() {
    for (const eintrag of [...offeneMeldungen]) {
        offeneMeldungen.splice(offeneMeldungen.indexOf(eintrag), 1)
        eintrag.entfernen()
    }
    escSichern()
}

/**
 * F6: Bei Überzahl fällt die ÄLTESTE entbehrliche Meldung heraus. Fehler
 * gelten nie als entbehrlich — eine Fehlermeldung sagt, was jetzt zu tun ist
 * (Prinzip I4), und wird deshalb nicht als erste weggeschoben; sie blendet
 * nach `ANZEIGE_MS` aus wie jede andere (MT-3). Eine Rückgängig-Meldung
 * bleibt nur so lange nützlich, wie ihr Eintrag im Stapel steht.
 */
function schliesseAelteste() {
    while (offeneMeldungen.length >= HOECHSTENS) {
        const index = offeneMeldungen.findIndex(m => m.type !== 'error')
        if (index < 0) return            // nur Fehler offen: nicht verdrängen
        offeneMeldungen.splice(index, 1)[0].entfernen()
    }
}

/**
 * Eine Meldung zeigen.
 *
 * @param {string} message   Text (nie als HTML eingesetzt).
 * @param {string} type      info | success | error | warning | undo
 * @param {null|{text: string, onClick: Function, beschriftung?: string}} aktion
 *        Optionaler EIN Knopf. `beschriftung` ist die Vorlese-Beschriftung
 *        (Standard: der Knopftext) — z. B. „Rückgängig: Aus Gruppe entfernt“.
 * @param {{ schliessen?: boolean, id?: string, dauer?: number,
 *           beiSchliessen?: Function, darfEsc?: Function,
 *           onPause?: Function, onWeiter?: Function }} [optionen]
 *        `schliessen: false` blendet das ✕ aus (Rückgängig-Meldungen haben
 *        genau eine Aktion); `id` macht die Meldung von außen entfernbar;
 *        `dauer` überschreibt die Typ-Dauer; `beiSchliessen(grund)` wird beim
 *        Entfernen gerufen (`esc` | `x` | `klick` | `frist` | `raum`);
 *        `darfEsc()` sagt, ob diese Meldung Esc annehmen soll (UX2a2 F4 —
 *        Standard ist JA, der Dienst nimmt die oberste); `onPause()` und
 *        `onWeiter(restMs)` melden Hover/Fokus an die Aktion, damit auch
 *        IHRE Frist stehenbleibt (UX2a2b).
 * @returns {Function} entfernen(grund?)
 */
export function showToast(message, type = 'info', aktion = null, optionen = {}) {
    const container = ensureContainer()
    const mitAktion = Boolean(aktion && typeof aktion.onClick === 'function')
    const dauer = Number.isFinite(optionen.dauer)
        ? optionen.dauer
        : (type === 'error' ? DAUER_MS.error : (mitAktion ? DAUER_MS.mitAktion : DAUER_MS.normal))
    const schliessenZeigen = optionen.schliessen !== false
    const id = optionen.id || `toast-${++zaehler}`
    const beiSchliessen = typeof optionen.beiSchliessen === 'function' ? optionen.beiSchliessen : null
    const darfEsc = typeof optionen.darfEsc === 'function' ? optionen.darfEsc : null
    // UX2a2b: Hover/Fokus halten nicht nur die Anzeige an, sondern auch die
    // Frist der Aktion (der Stapel rechnet sie nach). `onPause()` kommt beim
    // Anhalten, `onWeiter(restMs)` beim Fortsetzen (nach dem Deckel-Ablauf
    // mit der gedeckelten Restzeit).
    const onPause = typeof optionen.onPause === 'function' ? optionen.onPause : null
    const onWeiter = typeof optionen.onWeiter === 'function' ? optionen.onWeiter : null

    const el = document.createElement('div')
    el.className = `diakonos-toast diakonos-toast--${type}`
    el.setAttribute('role', type === 'error' ? 'alert' : 'status')
    el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite')
    el.setAttribute('aria-atomic', 'true')
    // UX2a2: Kennung am Knoten — die Verbindung findet „ihre“ Meldung wieder
    // (Fokus-Ziel F3, Zustand der Aktion), ohne über Klassennamen zu raten.
    el.setAttribute('data-meldung', id)
    // Die Meldung selbst ist kein Tab-Stopp; der Knopf darin ist einer.
    if (type === 'undo') container.classList.add('diakonos-toast-container--undo')

    let rest = dauer
    let timer = null
    let start = 0
    let entfernt = false
    let grund = null
    // UX2a2 (F3): Die Uhr läuft erst, wenn `showToast` zurückgegeben hat.
    // Vorher startete die Frist INNERHALB des Aufrufs — ein Zeiger, der schon
    // über der Stelle stand (oder im selben Zug dorthin ging), traf eine Uhr,
    // die noch gar nicht angefangen hatte: `pause()` merkte sich dann fast
    // 0 ms Rest, und die Meldung verschwand nach dem Verlassen sofort.
    let bereit = false
    let maus = false
    let fokus = false
    // UX2a2 (Befund aus der Abnahme): Hover/Fokus halten die Meldung — aber
    // nicht über die LEBENSDAUER der Aktion hinaus. Ein liegengebliebener
    // Zeiger (oder ein Fokus, der nach dem Schließen auf `<body>` fiel) hielt
    // sie sonst unbegrenzt: im Browser stand sie nach 8 s noch, und die
    // Messung „Hover hält" war nicht zu unterscheiden von „Hover hängt".
    // `deckel` nimmt nach `dauer + HALTE_ZUSATZ_MS` jede Halte-Bremse weg.
    let deckel = null
    function haltenAus() { maus = false; fokus = false }
    function deckeln() {
        clearTimeout(deckel)
        // MT-3: Jede Meldung läuft ab (`dauer` immer > 0). Der Deckel steht
        // trotzdem als Schutz für `dauer: 0`: ein Aufrufer, der die Anzeige
        // ausdrücklich abschaltet, bekommt auch keinen Halte-Deckel.
        if (!dauer) return
        deckel = setTimeout(() => {
            const hielt = maus || fokus
            haltenAus()
            if (onWeiter && hielt) {
                // UX2a2b: Der Deckel nimmt die Halte-Bremse weg — die Frist
                // der Aktion läuft mit der GEdeckelten Restzeit weiter (und
                // der Takt räumt sie ab, wenn sie abläuft).
                const restzeit = rest ? Math.min(rest, HALTE_ZUSATZ_MS) : 0
                if (!restzeit) { entfernen('frist'); return }
                try { onWeiter(restzeit) } catch { /* die Meldung darf nicht hängen */ }
            }
            if (!rest) return
            clearTimeout(timer)
            start = 0
            rest = Math.min(rest, HALTE_ZUSATZ_MS)
            weiter()
        }, dauer + HALTE_ZUSATZ_MS)
    }
    deckeln()

    const text = document.createElement('span')
    text.className = 'diakonos-toast-text'
    text.textContent = rueckmeldeText(message, type)
    el.appendChild(text)

    /**
     * Die Meldung entfernen. `grund` sagt dem Aufrufer, warum — die
     * Rückgängig-Meldung unterscheidet „Esc“ (Eintrag verwerfen) von
     * „Klick“ (Eintrag ist verbraucht) von „Frist“ (Eintrag abgelaufen).
     */
    function entfernen(warum = 'x') {
        if (entfernt) return
        entfernt = true
        grund = warum
        clearTimeout(timer)
        clearTimeout(deckel)
        el.classList.remove('show')
        const index = offeneMeldungen.findIndex(e => e.id === id)
        if (index >= 0) offeneMeldungen.splice(index, 1)
        // UX2a2b (E1): Der EINE Esc-Zuhörer fällt ab, wenn nichts mehr offen ist.
        escSichern()
        // F5: Positionsklasse nachziehen, Fehlermeldungen bleiben oben rechts.
        positionNachziehen()
        if (beiSchliessen) {
            try { beiSchliessen(grund) } catch { /* darf das Entfernen nicht blockieren */ }
        }
        if (typeof setTimeout === 'function') {
            setTimeout(() => { if (el.parentNode) el.remove() }, 300)
        } else if (el.parentNode) {
            el.remove()
        }
    }
    function weiter() {
        if (!rest || entfernt || maus || fokus || !bereit) return
        start = Date.now()
        timer = setTimeout(() => entfernen('frist'), rest)
    }
    function pause() {
        clearTimeout(timer)
        if (start) rest = Math.max(1, rest - (Date.now() - start))
        start = 0
    }
    /**
     * UX2a2b: Hover/Fokus AN — Uhr anhalten und die Frist der Aktion mit
     * anhalten (`onPause`). Kommt der Zeiger/Fokus nur auf die Fläche, die
     * eben schon hielt, wird der Stapel nicht erneut gerufen.
     */
    function haltenAn(quelle) {
        const vorher = maus || fokus
        if (quelle === 'maus') maus = true
        else fokus = true
        pause()
        if (!vorher && onPause) {
            try { onPause() } catch { /* die Meldung darf nicht hängen */ }
        }
    }
    /**
     * UX2a2b: Hover/Fokus AUS — nur wenn keine andere Bremse mehr steht, darf
     * die Frist der Aktion weiterlaufen (`onWeiter`). Die Uhr der Meldung
     * läuft erst in `weiter()`, wenn sie wieder `bereit` ist.
     */
    function haltenAusFuer(quelle) {
        if (quelle === 'maus') maus = false
        else fokus = false
        if (maus || fokus) return
        if (onWeiter) {
            try { onWeiter(rest) } catch { /* die Meldung darf nicht hängen */ }
        }
        weiter()
    }
    if (mitAktion) {
        const btn = document.createElement('button')
        btn.type = 'button'
        btn.className = 'diakonos-toast-aktion'
        btn.textContent = aktion.text || 'Ansehen'
        if (aktion.beschriftung) btn.setAttribute('aria-label', aktion.beschriftung)
        btn.addEventListener('click', () => {
            entfernen('klick')
            aktion.onClick()
        })
        el.appendChild(btn)
    }
    if (schliessenZeigen) {
        const schliessen = document.createElement('button')
        schliessen.type = 'button'
        schliessen.className = 'diakonos-toast-schliessen'
        // Review-Nacharbeit (A11y): Die Fläche steht am Ende von `<body>`;
        // bis das ✕ per Tab erreicht ist, kann die Meldung längst weg sein.
        // Esc schließt sie sofort — das steht deshalb im Namen mit (WCAG
        // 3.3.2 „Beschriftung oder Anweisung“, Prinzip S5 „bekannte Muster“).
        schliessen.setAttribute('aria-label', 'Meldung schließen (Esc)')
        schliessen.title = 'Meldung schließen (Esc)'
        schliessen.textContent = '✕'
        schliessen.addEventListener('click', () => entfernen('x'))
        el.appendChild(schliessen)
    }
    /* UX2a2b (E1): Esc schließt die OBERSTE Meldung (Prinzip S5). Wer das
       entscheidet, steht an EINER Stelle: der Zuhörer `beiEscTaste` am
       Dokument (`escSchliessen`) — es gibt keinen Zuhörer je Meldung mehr.
       Ein offener Dialog hat Vorrang (Esc gehört ihm). `darfEsc` ist die
       Ausnahme EINER Meldung (Rückgängig-Meldung eines abgemeldeten Stands). */

    el.addEventListener('mouseenter', () => haltenAn('maus'))
    el.addEventListener('mouseleave', () => haltenAusFuer('maus'))
    el.addEventListener('focusin', () => haltenAn('fokus'))
    el.addEventListener('focusout', e => {
        if (el.contains(e.relatedTarget)) return
        haltenAusFuer('fokus')
    })

    schliesseAelteste()
    container.appendChild(el)
    offeneMeldungen.push({ id, type, el, entfernen, darfEsc })
    escSichern()
    positionNachziehen()
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => el.classList.add('show'))
    else el.classList.add('show')
    bereit = true
    weiter()
    el.style.pointerEvents = 'auto'
    // Aufrufer (z. B. der Rückgängig-Stapel) erfahren den Grund — und ob die
    // Meldung schon weg ist: `weg()` sagt es, bevor sie sich abmeldet.
    entfernen.weg = () => entfernt
    entfernen.grund = () => grund
    // UX2a2b: Der Knoten selbst — der Aufrufer braucht ihn, um zu prüfen, ob
    // der Fokus in DIESER Meldung stand (Fokus nicht stehlen).
    entfernen.el = el
    return entfernen
}
