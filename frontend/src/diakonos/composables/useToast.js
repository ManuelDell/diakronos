/**
 * Eigener Toast-Service als Ersatz für frappe.show_alert()
 * Funktioniert im www-Space ohne globales frappe-Objekt.
 */

function ensureContainer() {
    let container = document.querySelector('.diakonos-toast-container')
    if (!container) {
        container = document.createElement('div')
        container.className = 'diakonos-toast-container'
        document.body.appendChild(container)
    }
    return container
}

export function showToast(message, type = 'info') {
    const container = ensureContainer()
    const el = document.createElement('div')
    el.className = `diakonos-toast diakonos-toast--${type}`
    el.textContent = message
    container.appendChild(el)

    requestAnimationFrame(() => el.classList.add('show'))

    setTimeout(() => {
        el.classList.remove('show')
        setTimeout(() => {
            if (el.parentNode) el.remove()
        }, 300)
    }, 3000)
}
