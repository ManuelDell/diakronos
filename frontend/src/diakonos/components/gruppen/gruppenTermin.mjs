/**
 * UI-R5 — „+ Termin“ auf der Gruppenseite: welche Kalender dieser Seite
 * gehören, und was ein neuer Termin dort bedeutet.
 *
 * Der Server liefert die Rechte (`get_accessible_calendars`): je Kalender
 * `write`, `direkt` (neuer Termin wirkt sofort), `stufen` (Prüfstufen) sowie
 * `gruppe` / `untergruppe` (Zuordnung im Rechtesystem; `null` = Gemeinde).
 * Diese Datei entscheidet NICHTS über Rechte — sie liest die Serverfelder und
 * blendet zusammen, was der Server ohnehin liefert. Fehlt ein Feld, gilt die
 * vorsichtige Annahme (nicht schreibbar / geprüft).
 *
 * Alles hier sind reine Funktionen: `tests/ui-r5-*.test.mjs` führt sie ohne
 * Browser und ohne Server aus.
 */

// UI-R5b (Punkt 4): Die DEV-5-Regel des Zeitvorschlags steht in datumZeit.mjs
// (eine Quelle). Hier wird sie nur gelesen, in Gemeinde-Ortszeit gestellt.
import { vorschlagZeitraum } from '../../composables/datumZeit.mjs'

/** Pflichttext der Karte, wenn ein Termin vor der Veröffentlichung geprüft wird. */
export const PRUEFHINWEIS = 'Der Termin wird vor der Veröffentlichung geprüft.'

/** Zeitzone der Gemeinde — die Zeitangaben sind Ortszeit (ZEIT-2/ZEIT-3). */
export const GEMEINDE_ZEITZONE = 'Europe/Berlin'

/**
 * Kalender, die zu DIESER Gruppenseite gehören und in denen der Aufrufer
 * schreiben bzw. vorschlagen darf.
 *
 * Zugeordnet wird über die Felder der Serverliste:
 *   * Gruppe-Seite:     `gruppe === gruppenId && untergruppe == null`
 *                       (der Kalender der Gruppe selbst),
 *   * Untergruppe-Seite:`untergruppe === gruppenId` (Kalender der Untergruppe)
 *                       oder `gruppe === hauptgruppe && untergruppe == null`
 *                       (der Kalender der Hauptgruppe, den auch die GL sieht).
 * Ein Kalender OHNE `gruppe` ist ein Gemeinde-Kalender — er erscheint hier
 * nicht, auch wenn der Aufrufer dort schreiben darf (das ist Sache des
 * Kalenders, nicht der Gruppe). Fehlt `untergruppe` ganz (alter Server), zählt
 * der Kalender als Kalender der Gruppe selbst.
 *
 * @param {Array<object>} kalender — Einträge aus `get_accessible_calendars`
 * @param {{gruppenId?: string, hauptgruppe?: string|null, istUntergruppe?: boolean}} lage
 * @returns {Array<object>} dieselben Einträge, unverändert, in Serverreihenfolge
 */
export function kalenderDerGruppe(kalender, { gruppenId = '', hauptgruppe = null, istUntergruppe = false } = {}) {
    const liste = Array.isArray(kalender) ? kalender : []
    const id = String(gruppenId || '')
    if (!id) return []
    return liste.filter((c) => {
        if (!c || typeof c !== 'object') return false
        if (c.write !== true) return false // nur schreiben/vorschlagen
        const g = c.gruppe == null ? null : String(c.gruppe)
        const u = c.untergruppe == null ? null : String(c.untergruppe)
        if (istUntergruppe) {
            if (u === id) return true
            return hauptgruppe != null && g === String(hauptgruppe) && u === null
        }
        return g === id && u === null
    })
}

/**
 * Vorbelegter Kalender eines neuen Termins.
 *
 * Ein Kalender → dieser (das Formular zeigt ihn vorbelegt). Mehrere → leer:
 * dann fragt Diakronos, für welchen (die Auswahl bleibt im Formular sichtbar
 * und ist Pflichtfeld).
 *
 * @param {Array<object>} auswahl — Ergebnis von {@link kalenderDerGruppe}
 * @returns {string} Kalenderkennung oder ''
 */
export function vorbelegterKalender(auswahl) {
    const liste = Array.isArray(auswahl) ? auswahl : []
    return liste.length === 1 ? String(liste[0]?.name || '') : ''
}

/**
 * Wird der Termin dieses Kalenders vor der Veröffentlichung geprüft?
 *
 * Maßgeblich ist `direkt === false` des Servers. Ein FEHLENDES Feld heißt
 * NICHT „geprüft“: auf der Kalenderseite liefert `get_writable_calendars` vor
 * R-12e kein `direkt`, und die alte Regel (`!== true`) zeigte deshalb JEDER
 * Person den Prüfhinweis, auch HV und Admin (Review UI-R5, HOCH). Ohne
 * Auskunft wird jetzt nichts behauptet.
 *
 * Diese Funktion ist die EINE Quelle: das Formular (KronosEventCreate.vue)
 * liest sie, statt die Bedingung ein zweites Mal zu schreiben.
 *
 * @param {object|null} kalender — Eintrag aus der Serverliste
 * @returns {boolean}
 */
export function wirdGeprueft(kalender) {
    if (!kalender || typeof kalender !== 'object') return false
    return kalender.direkt === false
}

/** Statuswert, den der Server als „ohne Prüfung veröffentlicht“ führt. */
export const STATUS_DIREKT = 'Festgelegt'

/**
 * Schickt das Formular einen `status` mit — und welchen? (UI-R5b, Punkt 1)
 *
 * Der Server legt einen Termin nur auf AUSDRÜCKLICHEN Wunsch direkt an:
 * `_erzwungener_status` (event_crud.py) macht ohne `status` IMMER „Vorschlag“,
 * und Nicht-Direktschreiber bekommen trotz `status` einen Vorschlag. „HV und
 * MV schreiben direkt“ (Manuel) heißt deshalb: das Formular bittet um
 * „Festgelegt“, wenn der gewählte Kalender `direkt === true` meldet.
 *
 * Umgekehrt wird NICHTS behauptet: bei `direkt === false` oder FEHLENDEM Feld
 * bleibt `status` weg — dann entscheidet der Server (Vorschlag), und die
 * Oberfläche schickt kein „Festgelegt“, das er ohnehin verwerfen würde.
 *
 * Dieselbe Quelle für Einzeltermin und Serie (`create_event`/`create_series`
 * nehmen beide `status`).
 *
 * @param {object|null} kalender — Eintrag aus der Serverliste
 * @returns {string} `'Festgelegt'` oder `''` (kein status im Payload)
 */
export function statusFuerKalender(kalender) {
    if (!kalender || typeof kalender !== 'object') return ''
    return kalender.direkt === true ? STATUS_DIREKT : ''
}

/**
 * Optionsliste für die Auswahl im Termin-Formular.
 *
 * UI-R5b (Punkt 3): Das zweite Argument (`alleBeschreibbaren`) ist entfallen —
 * es war wirkungslos: das Formular reicht die Kalender der Seite schon
 * GEFILTERT UND BESCHREIBBAR durch (die Anfrage dort ist
 * `get_accessible_calendars`, `loadData` behält nur `write === true` und die
 * Namen der Vorgabe). Ein „danach die übrigen“ gab es also nie. Auch
 * Gemeinde-Kalender gehören NICHT dazu — der Aufrufer entscheidet über die
 * Vorgabe (`kalenderDerGruppe` kennt nur Kalender dieser Seite).
 *
 * Doppelte Namen fallen trotzdem weg: der Server liefert je Kalender einen
 * Eintrag, ein doppelter Name wäre ein Fehler und kein zweiter Eintrag.
 *
 * @param {Array<object>} kalender — bereits gefilterte Kalender (Reihenfolge
 *   des Servers)
 * @returns {Array<{value: string, label: string}>}
 */
export function kalenderOptionen(kalender) {
    const gesehen = new Set()
    const out = []
    for (const c of Array.isArray(kalender) ? kalender : []) {
        const name = String(c?.name || '')
        if (!name || gesehen.has(name)) continue
        gesehen.add(name)
        out.push({ value: name, label: String(c.title || c.calendar_name || name) })
    }
    return out
}

/**
 * Vorschlag für einen NEUEN Termin von der Gruppenseite: `{ element_start,
 * element_end }` — beide vollständig, nie nur der Beginn.
 *
 * Review UI-R5 (MITTEL): Der Beginn allein (aktuelle Minute) übersprang den
 * Vorschlag von DEV-5 (`resetForm` fasst nur ein Datum OHNE Uhrzeit an) und
 * legte ohne Anfassen einen Termin OHNE Dauer an. Deshalb dieselbe Regel
 * wie im Kalender (DEV-5): nächste volle Stunde, eine Stunde Dauer, bei
 * Mitternacht mit Tageswechsel — aber in der Gemeinde-Zeitzone gerechnet und
 * OHNE Zeitzonen-Anhang (`parse_iso_datetime_raw` lehnt „…Z“/„+01:00“ ab).
 * Das Format ist `YYYY-MM-DDTHH:MM`, wie es das Formular und der Server
 * verstehen.
 *
 * UI-R5b (Punkt 4): Die Regel selbst steht NICHT mehr hier — sie stand hier
 * als zweite Fassung von `vorschlagZeitraum` (datumZeit.mjs, DEV-5) und
 * konnte davon abweichen. Gelesen wird jetzt die eine Quelle; diese Funktion
 * ergänzt nur, was der Kalender-Vorschlag nicht weiß: Ortzeit der Gemeinde
 * statt Gerätezeit und kein Zeitzonen-Anhang.
 *
 * @param {Date} [jetzt]
 * @returns {{element_start: string, element_end: string}}
 */
export function formularZeitraum(jetzt = new Date()) {
    const d = jetzt instanceof Date && !Number.isNaN(jetzt.getTime()) ? jetzt : new Date()
    const teile = ortszeitTeile(d)
    const ortszeit = new Date(`${teile.datum}T${teile.uhrzeit}:00`)
    // `datum` (nicht ein eigener Mitternachts-Zweig) trägt den Tageswechsel:
    // bei 23:30 ist der Beginn schon 00:00 des Folgetags.
    const { datum, beginn, ende, endeDatum } = vorschlagZeitraum(ortszeit)
    return {
        element_start: `${datum}T${beginn}`,
        element_end: `${endeDatum}T${ende}`,
    }
}

/**
 * Titel einer Prüfstufe, wie der Server sie nennt (`get_rollen_erklaerung()`
 * → `stufen_titel`). Fehlt die Erklärung, bleibt die Stufe selbst lesbar.
 *
 * @param {string|null} stufe — „untergruppe“ | „gruppe“ | „gemeinde“
 * @param {object} [stufenTitel] — `stufen_titel` aus der Rollen-Erklärung
 * @returns {string}
 */
export function stufenName(stufe, stufenTitel = {}) {
    const schluessel = String(stufe || '').trim()
    if (!schluessel) return ''
    const titel = stufenTitel && typeof stufenTitel === 'object'
        ? String(stufenTitel[schluessel] || '').trim()
        : ''
    if (titel) return titel
    // Rückfall ohne Servertext: die Stufe als Wort, keine erfundene Bezeichnung.
    return schluessel
}

/**
 * Meldung nach dem Speichern — sagt ehrlich, wo der Termin jetzt steht.
 *
 * Review UI-R5 (3): Bei einem Vorschlag nannte die Seite nur „(Vorschlag)“.
 * Der Server liefert seit R-12e `status`, `offen` und `naechste_stufe` (Serien
 * zusätzlich `status`), damit die Oberfläche die offene Stufe benennen kann.
 * Ein `status` aus der Antwort gilt auch für Serien (kein pauschales
 * „(Vorschlag)“ mehr).
 *
 * @param {object} antwort — `message` aus `create_event`/`create_series`
 * @param {object} [stufenTitel] — `stufen_titel` aus `get_rollen_erklaerung()`
 * @returns {{text: string, variante: 'success'|'info'}}
 */
export function meldungNachSpeichern(antwort, stufenTitel = {}) {
    const daten = antwort && typeof antwort === 'object' ? antwort : {}
    const status = String(daten.status || '')
    // Serie: der Server zählt die angelegten Termine — die Meldung nennt sie.
    const serie = Number(daten.created_count)
    const serieZusatz = Number.isFinite(serie) && serie > 1 ? ` (${serie} Termine)` : ''

    if (status === 'Festgelegt') {
        return { text: `Termin gespeichert${serieZusatz}.`, variante: 'success' }
    }
    if (status === 'Vorschlag') {
        const stufe = stufenName(daten.naechste_stufe, stufenTitel)
        const weiter = stufe
            ? `wartet auf ${stufe}`
            : 'wird zum Prüfen vorgelegt'
        return { text: `Termin gespeichert${serieZusatz} — ${weiter}.`, variante: 'info' }
    }
    // Unbekannter/fehlender Status: keine Behauptung über den Weg (alter Server).
    return { text: `Termin gespeichert${serieZusatz}.`, variante: 'success' }
}

/**
 * Teile eines Zeitpunkts in der Gemeinde-Zeitzone.
 * @param {Date} jetzt
 * @returns {{datum: string, uhrzeit: string}}
 */
export function ortszeitTeile(jetzt = new Date()) {
    const d = jetzt instanceof Date && !Number.isNaN(jetzt.getTime()) ? jetzt : new Date()
    let jahr = d.getFullYear()
    let monat = d.getMonth() + 1
    let tag = d.getDate()
    let stunde = d.getHours()
    let minute = d.getMinutes()
    try {
        const fmt = new Intl.DateTimeFormat('de-DE', {
            timeZone: GEMEINDE_ZEITZONE,
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hour12: false,
        })
        const teile = Object.fromEntries(fmt.formatToParts(d).map((t) => [t.type, t.value]))
        const p = (v) => String(v || '').padStart(2, '0')
        if (teile.year && teile.month && teile.day && teile.hour && teile.minute) {
            return {
                datum: `${teile.year}-${p(teile.month)}-${p(teile.day)}`,
                // Intl liefert für Mitternacht in manchen Engines „24“.
                uhrzeit: `${p(teile.hour === '24' ? '00' : teile.hour)}:${p(teile.minute)}`,
            }
        }
    } catch { /* Zone unbekannt — Gerätezeit unten */ }
    const p = (v) => String(v).padStart(2, '0')
    return {
        datum: `${jahr}-${p(monat)}-${p(tag)}`,
        uhrzeit: `${p(stunde)}:${p(minute)}`,
    }
}
