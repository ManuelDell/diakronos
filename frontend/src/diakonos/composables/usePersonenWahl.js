/**
 * UI-R9 — Auswahl einer Person in einem modalen Dialog.
 *
 * Der vorhandene Bestätigungsdialog (`useBestaetigen`) beantwortet nur Ja/Nein;
 * die Aufgaben-Zuweisung braucht aber eine PERSON aus einer Liste, und ein
 * `select` im „⋯"-Menü wäre am Handy unbedienbar. Deshalb dieser eine,
 * schmale Dialog: eine Liste von Knöpfen (kein Verschachteln von Menüs), eine
 * Zeile je Person, die aktuelle Zuweisung markiert, „Niemanden" zum Aufheben.
 *
 * Das Ergebnis ist der Wert der gewählten Person, `''` für „Niemanden" und
 * `null`, wenn der Dialog abgebrochen wurde. Die Rechte prüft weiterhin der
 * Server — hier wird nur ausgewählt.
 */
import { shallowRef } from 'vue'

export const personenWahl = shallowRef(null)
const wartend = []
let antwort = null

function naechste() {
    if (antwort || !wartend.length) return
    const eintrag = wartend.shift()
    antwort = eintrag.resolve
    personenWahl.value = eintrag.frage
}

/**
 * @param {{titel: string, text?: string, optionen: Array<{value,label}>,
 *          aktuell?: string, leerLabel?: string}} frage
 * @returns {Promise<string|null>}
 */
export function waehlePerson(frage) {
    return new Promise(resolve => {
        wartend.push({ frage, resolve })
        naechste()
    })
}

export function personenWahlAntwort(wert) {
    const resolve = antwort
    antwort = null
    personenWahl.value = null
    resolve?.(typeof wert === 'string' ? wert : null)
    // Erst den alten Dialog schließen (Fokus zurück), dann den nächsten zeigen.
    queueMicrotask(naechste)
}
