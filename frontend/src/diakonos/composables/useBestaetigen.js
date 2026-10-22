import { shallowRef } from 'vue'

export const bestaetigung = shallowRef(null)
const wartend = []
let antwort

function naechste() {
    if (antwort || !wartend.length) return
    const eintrag = wartend.shift()
    antwort = eintrag.resolve
    bestaetigung.value = eintrag.frage
}

// Eine Antwort gehört immer genau einer Frage; parallele Aufrufer werden
// nacheinander gezeigt, nicht durch die nächste Frage überschrieben.
export function bestaetigen(frage) {
    return new Promise(resolve => {
        wartend.push({ frage, resolve })
        naechste()
    })
}

export function bestaetigungAntwort(wert) {
    const resolve = antwort
    antwort = null
    bestaetigung.value = null
    resolve?.(wert === true)
    // Erst den alten Dialog einschließlich Fokus-Rückgabe schließen.
    queueMicrotask(naechste)
}
