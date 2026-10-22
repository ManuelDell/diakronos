/** Gemeinsame Pflichtprüfung; Feldkennungen sind zugleich DOM-IDs. */
export function pflichtFehler(felder) {
    return Object.fromEntries(felder
        .filter(([, wert]) => !String(wert ?? '').trim())
        .map(([id, , name]) => [id, `Bitte ${name} angeben.`]))
}

export function buchungsFehler(f = {}) {
    const fehler = pflichtFehler([
        ['rs-ressource', f.resourceId, 'eine Ressource'],
        ['rs-von-datum', f.date, 'das Startdatum'],
        ['rs-von-zeit', f.startTime, 'die Startzeit'],
        ['rs-bis-datum', f.endDate, 'das Enddatum'],
        ['rs-bis-zeit', f.endTime, 'die Endzeit'],
        ['rs-zweck', f.purpose, 'einen Zweck'],
    ])
    if (Object.keys(fehler).length) return fehler
    const von = new Date(`${f.date}T${f.startTime}`)
    const bis = new Date(`${f.endDate}T${f.endTime}`)
    if (!Number.isFinite(von.getTime()) || !Number.isFinite(bis.getTime()) || bis <= von) {
        fehler['rs-bis-zeit'] = 'Das Ende muss nach dem Beginn liegen.'
    }
    return fehler
}

export function erstesFehlerfeld(fehler) {
    const id = Object.keys(fehler)[0]
    if (id) requestAnimationFrame(() => document.getElementById(id)?.focus())
}
