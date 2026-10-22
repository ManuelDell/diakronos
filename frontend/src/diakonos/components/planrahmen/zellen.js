/**
 * Gemeinsame Zellenlogik der generischen Ansichten (Tabelle/Raster/Kalender):
 * Werte eines Felds je Termin als Textzeilen mit Fixierungs- und Regelhinweis.
 * Pfade kommen ausschließlich vom Server (Slots/Einträge), nie erfunden.
 *
 * P3-1c (A): Ein `auswahl`-Feld speichert ASCII-Kennungen („Maennerchor“,
 * „Floete“); angezeigt wird der Anzeigename („Männerchor“, „Flöte“). Diese
 * Zelle ist ein Anzeigeort wie das Formular — deshalb laeuft jeder Wert eines
 * Auswahlfelds durch `wertAnzeige(feld, wert)` (mit Katalog-Rueckfall fuer
 * gespeicherte Vorlagen ohne eigenes `anzeigenamen`).
 */
import { instanzenZu, wertText, formatVorlage, zellenKontext, feldGehoertZu } from '../../composables/usePlanrahmen.js'
import { wertAnzeige } from './auswahlwerte.mjs'

/** Regelmeldungen einer Instanz (Selbst + Unterfelder). */
function meldungenZu(instanz) {
    const liste = []
    for (const e of [instanz.selbst, ...instanz.unter.values()]) {
        if (Array.isArray(e?.meldungen)) liste.push(...e.meldungen)
    }
    return liste
}

/**
 * Anzeigetext eines Werts unter Kenntnis seiner Felddefinition.
 * `auswahl` → Anzeigename je Wert (auch bei Listen); sonst wie `wertText`.
 */
export function feldWertText(feld, wert) {
    if (feld?.art === 'auswahl') {
        if (wert === null || wert === undefined || wert === '') return '–'
        if (Array.isArray(wert)) {
            return wert.map((w) => feldWertText(feld, w)).filter((s) => s !== '–').join(', ') || '–'
        }
        if (typeof wert !== 'object') return wertAnzeige(feld, String(wert))
    }
    return wertText(wert)
}

/** Eine Zeile je Instanz eines einfachen Felds. */
export function feldZellen({ eintraege, plan, termin, feldPfad, feld, format }) {
    const unterDeklaration = new Map()
    for (const u of feld?.inhalt || []) unterDeklaration.set(u.id, u)
    return instanzenZu(eintraege, termin?.id, feldPfad).map((instanz) => {
        const wert = instanz.selbst?.wert
        const unter = [...instanz.unter.entries()].map(([id, e]) =>
            `${id}: ${feldWertText(unterDeklaration.get(id), e.wert)}`)
        const gesetzt = wert !== null && wert !== undefined && wert !== ''
        let text = ''
        if (format && (gesetzt || unter.length)) {
            text = formatVorlage(format, zellenKontext(plan, termin, instanz, feld))
        }
        if (!text) {
            const teile = gesetzt ? [feldWertText(feld, wert)] : []
            teile.push(...unter)
            text = teile.join(' · ')
        }
        return { text: text || '–', fixiert: !!instanz.selbst?.fixiert, meldungen: meldungenZu(instanz) }
    })
}

/** Letzter Pfadteil als Anzeigename ('abend@regen#leitung' → 'leitung'). */
export function pfadBlattName(vollerPfad, basis) {
    let rest = vollerPfad.slice(basis.length)
    rest = rest.replace(/^\[[\d]+\]/, '')
    const teile = rest.split('.')
    return teile[teile.length - 1] || basis
}

/**
 * Unterfeldzeilen eines Gruppenfelds (reale Serverpfade, inkl. Varianten).
 * `inhalt` sind die deklarierten Unterfelder — daraus loesen Auswahlwerte
 * ihren Anzeigenamen auf.
 */
export function gruppenZellen({ eintraege, termin, basis, inhalt }) {
    const deklaration = new Map()
    for (const u of inhalt || []) deklaration.set(u.id, u)
    const treffer = (eintraege || []).filter((e) => e.termin === termin?.id && feldGehoertZu(e.feld_pfad, basis))
    const result = []
    for (const e of treffer) {
        const blatt = pfadBlattName(e.feld_pfad, basis)
        // Variantenpfade enden auf 'name@variante' oder '#variante' — die
        // Deklaration ist unter der reinen Feld-id abgelegt.
        const basisId = blatt.split(/[@#]/)[0]
        const w = feldWertText(deklaration.get(blatt) || deklaration.get(basisId), e.wert)
        if (w === '–' && !e.fixiert) continue
        result.push({
            name: blatt,
            text: w,
            fixiert: !!e.fixiert,
            meldungen: Array.isArray(e.meldungen) ? e.meldungen : [],
        })
    }
    return result
}

/** Zelleninhalt je Feldart (gruppe → Unterfeldzeilen, sonst Instanzzeilen). */
export function zellenInhalt({ eintraege, plan, termin, feld, format }) {
    if (!feld) return []
    if (feld.art === 'gruppe') {
        return gruppenZellen({ eintraege, termin, basis: feld.pfad || feld.id, inhalt: feld.inhalt })
    }
    return feldZellen({ eintraege, plan, termin, feldPfad: feld.pfad || feld.id, feld, format })
}
