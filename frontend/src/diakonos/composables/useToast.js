/**
 * Ein Rückmeldedienst: Fehler bleiben bis zum Schließen, Erfolge vier Sekunden.
 *
 * UX2g: Ein leerer Text oder eine der alten Floskeln („Fehler",
 * „Unbekannter Fehler", „API-Fehler") ist keine Auskunft. Statt eines
 * eigenen Ersatzsatzes fragt der Toast den Fehlerkatalog
 * (`shared/fehlertexte.js`): er nennt, was passiert ist und was jetzt hilft.
 */
import { fehlertext, istFloskel } from '../../shared/fehlertexte.js'

export function rueckmeldeText(message, type) {
    const text = typeof message === 'string' ? message.trim() : ''
    if (type === 'error' && istFloskel(text)) {
        // Ohne verwertbaren Text bleibt die Lage unklar -> der Katalog nennt
        // den neutralen nächsten Schritt (Zustand „unbekannt").
        return fehlertext(null, {})
    }
    return text
}

function ensureContainer() {
    let container = document.querySelector('.diakonos-toast-container')
    if (!container) {
        container = document.createElement('div')
        container.className = 'diakonos-toast-container'
        document.body.appendChild(container)
    }
    return container
}

/** Optionale Aktion: { text, onClick }. Text wird niemals als HTML eingesetzt. */
export function showToast(message, type = 'info', aktion = null) {
    const container = ensureContainer()
    const el = document.createElement('div')
    el.className = `diakonos-toast diakonos-toast--${type}`
    el.setAttribute('role', type === 'error' ? 'alert' : 'status')
    el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite')
    el.setAttribute('aria-atomic', 'true')
    el.textContent = rueckmeldeText(message, type)
    el.style.pointerEvents = 'auto'
    const mitAktion = aktion && typeof aktion.onClick === 'function'
    let rest = type === 'error' ? 0 : (mitAktion ? 8000 : 4000)
    let timer = null
    let start = 0
    let entfernt = false
    let maus = false
    let fokus = false

    function entfernen() {
        if (entfernt) return
        entfernt = true
        clearTimeout(timer)
        el.classList.remove('show')
        setTimeout(() => { if (el.parentNode) el.remove() }, 300)
    }
    function weiter() {
        if (!rest || entfernt || maus || fokus) return
        start = Date.now()
        timer = setTimeout(entfernen, rest)
    }
    function pause() {
        clearTimeout(timer)
        if (start) rest = Math.max(1, rest - (Date.now() - start))
        start = 0
    }
    if (mitAktion) {
        const btn = document.createElement('button')
        btn.type = 'button'
        btn.className = 'diakonos-toast-aktion'
        btn.textContent = aktion.text || 'Ansehen'
        btn.addEventListener('click', () => { entfernen(); aktion.onClick() })
        el.appendChild(btn)
    }
    const schliessen = document.createElement('button')
    schliessen.type = 'button'
    schliessen.className = 'diakonos-toast-aktion'
    schliessen.textContent = '✕'
    schliessen.setAttribute('aria-label', 'Meldung schließen')
    schliessen.addEventListener('click', entfernen)
    el.appendChild(schliessen)
    el.addEventListener('mouseenter', () => { maus = true; pause() })
    el.addEventListener('mouseleave', () => { maus = false; weiter() })
    el.addEventListener('focusin', () => { fokus = true; pause() })
    el.addEventListener('focusout', e => {
        if (el.contains(e.relatedTarget)) return
        fokus = false
        weiter()
    })
    container.appendChild(el)
    requestAnimationFrame(() => el.classList.add('show'))
    weiter()
    return entfernen
}
