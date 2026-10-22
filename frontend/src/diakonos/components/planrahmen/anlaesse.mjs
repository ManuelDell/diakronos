/**
 * UXP-R22 — Anlass-Chips verständlich machen.
 *
 * Befund: Die Chips zeigten interne Kennungen („feiertag“, „heiligabend“,
 * „1_weihnachtstag“) statt der Katalognamen; der Sammelanlass „feiertag“
 * stand zusätzlich neben dem echten Feiertag, sodass jeder Feiertag doppelt
 * erschien.
 *
 * Diese Datei ist die EINE Stelle, die Kennung → Anzeigename auflöst:
 *   1. Anlässe der gewählten Planvorlage (haben immer einen `name`),
 *   2. sonst der Feiertagskatalog (Spiegel von
 *      `planrahmen/feiertage.py` — Namen müssen dort gleich lauten),
 *   3. sonst ein lesbarer Ersatz aus der Kennung (`1_weihnachtstag` →
 *      „1. Weihnachtstag“), nie die rohe Kennung.
 */

/** Sammelanlass, der nur „irgendein Feiertag“ bedeutet und nie angezeigt wird. */
import { FEIERTAGE } from './editor.mjs'

export const SAMMELANLASS = 'feiertag'

/**
 * Namen der Feiertage — ABGELEITET aus dem einen Katalog der Oberfläche
 * (`editor.mjs`). Der Build-Zeit-Abgleich mit dem Server läuft als
 * Vergleichstest (K4, `frontend/tests/p3-1b-feiertagskatalog.test.mjs`).
 *
 * Zur LAUFZEIT kann die Oberfläche den Server-Katalog über `feiertage_holen`
 * nachladen; `setzeFeiertagskatalog` überschreibt dann die Namen (siehe
 * `composables/usePlanrahmen.js`). So bleibt der Server die eine Quelle, auch
 * wenn sich ein Name dort ändert, ohne dass die Oberfläche neu gebaut wird.
 */
export const FEIERTAG_NAMEN = Object.fromEntries(
    FEIERTAGE.map(f => [f.schluessel, f.name]),
)

/**
 * REST-1: Anmeldung fuer „der Katalog hat sich geaendert“.
 *
 * `FEIERTAGE` ist ein einfaches Array (kein Vue-Ref) — wer es direkt rendert,
 * sah einen nachgeladenen Server-Katalog erst beim naechsten Oeffnen. Der
 * Termin-Editor haelt deshalb eine eigene Kopie und laesst sie hier
 * aktualisieren. Ohne Vue-Abhaengigkeit in diesem reinen Modul.
 */
const katalogEmpfaenger = new Set()

export function beiFeiertagskatalog(fn) {
    if (typeof fn !== 'function') return () => {}
    katalogEmpfaenger.add(fn)
    return () => katalogEmpfaenger.delete(fn)
}

/**
 * Übernimmt den Server-Katalog (`feiertage_holen`: [{schluessel, name, art}]).
 * Unbekannte Kennungen werden ergänzt, bekannte mit dem Servernamen
 * überschrieben. Leere/ungültige Eingaben bleiben wirkungslos — die
 * statische Liste ist der Rückfall.
 *
 * P3-1d (W3): Es wird NICHT nur `FEIERTAG_NAMEN` (Anlass-Chips) gefüllt,
 * sondern auch `FEIERTAGE` IN PLACE — genau die Liste, die der Termin-Editor
 * als Schalter rendert (`PrTermineEditor.vue`). Vorher blieb der Editor auf
 * der statischen Liste stehen, der Endpunkt hatte dort keine Wirkung.
 */
export function setzeFeiertagskatalog(liste) {
    if (!Array.isArray(liste)) return
    const geprueft = liste.filter(eintrag => eintrag
        && typeof eintrag.schluessel === 'string' && eintrag.schluessel
        && typeof eintrag.name === 'string' && eintrag.name)
    if (!geprueft.length) return
    for (const eintrag of geprueft) {
        FEIERTAG_NAMEN[eintrag.schluessel] = eintrag.name
    }
    // In Place ersetzen: Namentausch bei gleicher Kennung, neue Kennungen
    // hinten anfügen, die Reihenfolge des Servers bleibt erhalten.
    const bekannt = new Map(FEIERTAGE.map(f => [f.schluessel, f]))
    const neu = geprueft.map((eintrag) => {
        const alt = bekannt.get(eintrag.schluessel)
        bekannt.delete(eintrag.schluessel)
        return { schluessel: eintrag.schluessel, name: eintrag.name, art: eintrag.art || alt?.art || 'fest' }
    })
    // Kennungen, die der Server nicht (mehr) führt, bleiben erhalten — die
    // Oberfläche soll nichts verlieren, was eine Vorlage benutzt.
    FEIERTAGE.splice(0, FEIERTAGE.length, ...neu, ...bekannt.values())
    // REST-1: offene Ansichten (Termin-Editor) sofort nachziehen.
    for (const fn of katalogEmpfaenger) {
        try {
            fn()
        } catch {
            // Eine Ansicht darf den Katalog nicht aufhalten.
        }
    }
}

/** Kennung lesbar machen, wenn weder Vorlage noch Katalog sie kennt. */
export function lesbareKennung(kennung) {
    const text = String(kennung || '').trim()
    if (!text) return ''
    const ordnungszahl = text.match(/^(\d+)_(.+)$/)
    const rest = ordnungszahl ? `${ordnungszahl[1]}. ${ordnungszahl[2]}` : text
    const mitLeerzeichen = rest.replace(/_/g, ' ')
    return mitLeerzeichen.charAt(0).toUpperCase() + mitLeerzeichen.slice(1)
}

/**
 * Anzeigename eines Anlasses.
 * @param {string} kennung  z. B. 'heiligabend'
 * @param {Array<{id:string,name?:string}>} [definition]  `anlaesse` der Vorlage
 */
export function anlassName(kennung, definition) {
    const liste = Array.isArray(definition) ? definition : []
    const treffer = liste.find((x) => x && x.id === kennung)
    if (treffer && treffer.name) return treffer.name
    if (FEIERTAG_NAMEN[kennung]) return FEIERTAG_NAMEN[kennung]
    return lesbareKennung(kennung)
}

/**
 * Die anzuzeigenden Anlässe eines Termins: ohne den Sammelanlass und ohne
 * Doppelungen. Reihenfolge bleibt die der Vorlage.
 */
export function sichtbareAnlaesse(anlaesse) {
    const liste = Array.isArray(anlaesse) ? anlaesse : []
    const gesehen = new Set()
    const ergebnis = []
    for (const a of liste) {
        if (!a || a === SAMMELANLASS || gesehen.has(a)) continue
        gesehen.add(a)
        ergebnis.push(a)
    }
    return ergebnis
}
