/**
 * ST2 — reine UI-Logik für die Lieder-Pflege (node-testbar, ohne Vue).
 *
 * Alles hier ist bewusst frei von DOM/Vue: Filtern nach Tag/Suche, Ermitteln
 * der pflegbaren Tag-Merkmale, Zusammenfassen von Material nach Art und das
 * Sortieren rollengefilterter Personenkandidaten.
 */

/** Merkmals-Arten mit pflegbaren Auswahl-/Tag-Werten. */
const WERT_ARTEN = ['auswahl', 'tag']

/** Alle Merkmale einer Sammlung aus der Definition (Array-Form). */
export function sammlungMerkmale(definition, schluessel) {
    const m = definition?.merkmale
    const liste = m && Array.isArray(m[schluessel]) ? m[schluessel] : []
    return liste
}

/** Auswahl-/Tag-Merkmale (mehrfach oder nicht), deren Werte pflegbar sind. */
export function pflegbareWertMerkmale(definition, schluessel) {
    return sammlungMerkmale(definition, schluessel).filter((m) => WERT_ARTEN.includes(m?.art))
}

/** Personen-Merkmale einer Sammlung (z. B. Standard-Dirigent/Klavier). */
export function personMerkmale(definition, schluessel) {
    return sammlungMerkmale(definition, schluessel).filter((m) => m?.art === 'person')
}

/**
 * Lieder nach Volltext und Tags filtern.
 * `tagFilter` ist {merkmalId: [werte]} — ein Lied muss alle genannten Werte
 * tragen (UND über Merkmale, ODER innerhalb der Werte eines Merkmals).
 */
export function liederFiltern(lieder, { suche = '', tagFilter = {} } = {}) {
    const q = String(suche || '').trim().toLocaleLowerCase('de-DE')
    const aktiv = Object.entries(tagFilter || {}).filter(([, werte]) => (werte || []).length)
    return (lieder || []).filter((l) => {
        if (q) {
            const text = [l?.titel, l?.daten?.titel, l?.daten?.gesangbuch_nummer, l?.id]
                .map((t) => String(t || '').toLocaleLowerCase('de-DE')).join(' ')
            if (!text.includes(q)) return false
        }
        for (const [mid, werte] of aktiv) {
            const hat = asListe(l?.merkmale?.[mid])
            if (!werte.every((w) => hat.includes(w))) return false
        }
        return true
    })
}

/** Beliebigen Merkmalswert als Liste von Skalaren normalisieren. */
export function asListe(wert) {
    if (wert === null || wert === undefined || wert === '') return []
    if (Array.isArray(wert)) return wert.filter((w) => w !== null && w !== undefined && w !== '')
    return [wert]
}

/** Verfuegbare Tag-Werte je Merkmal — Definition plus tatsaechlich verwendete. */
export function tagWerte(definition, schluessel, lieder) {
    const ergebnis = {}
    for (const m of pflegbareWertMerkmale(definition, schluessel)) {
        const werte = new Set(m.werte || [])
        for (const l of lieder || []) for (const w of asListe(l?.merkmale?.[m.id])) werte.add(w)
        ergebnis[m.id] = [...werte].sort((a, b) => String(a).localeCompare(String(b), 'de'))
    }
    return ergebnis
}

/** Material eines Liedes nach Art gruppieren (Reihenfolge der Arten). */
export const MATERIAL_REIHENFOLGE = ['noten_pdf', 'audio', 'musescore', 'musicxml']

export const MATERIAL_ARTEN = {
    noten_pdf: { label: 'Noten (PDF)', endungen: ['.pdf'], dateiFeld: 'Noten' },
    audio: { label: 'Audio (zum Anhören)', endungen: ['.mp3', '.m4a', '.ogg', '.wav'], hoerbar: true },
    musescore: { label: 'MuseScore (zum Bearbeiten)', endungen: ['.mscz', '.mscx'] },
    musicxml: { label: 'MusicXML (zum Weiterverarbeiten)', endungen: ['.musicxml', '.mxl'] },
}

/** Material je Art, in fester Reihenfolge; unbekannte Arten bleiben erhalten. */
export function materialNachArt(material) {
    const gruppen = new Map()
    for (const m of material || []) {
        const art = m?.art || 'sonstiges'
        if (!gruppen.has(art)) gruppen.set(art, [])
        gruppen.get(art).push(m)
    }
    const reihenfolge = [...MATERIAL_REIHENFOLGE, ...[...gruppen.keys()].filter((a) => !MATERIAL_REIHENFOLGE.includes(a))]
    return reihenfolge.filter((a) => gruppen.has(a)).map((art) => ({
        art, label: MATERIAL_ARTEN[art]?.label || art, eintraege: gruppen.get(art),
    }))
}

/** Passende Material-Art zu einem Dateinamen (Endung), oder null. */
export function artFuerDateiname(name) {
    const endung = ('.' + String(name || '').split('.').pop()).toLocaleLowerCase()
    for (const [art, def] of Object.entries(MATERIAL_ARTEN)) {
        if (def.endungen.includes(endung)) return art
    }
    return null
}
