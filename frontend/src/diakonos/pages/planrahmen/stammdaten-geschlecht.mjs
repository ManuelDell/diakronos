/**
 * PR-G1 — Personen der Stammdaten nach Geschlecht filtern und sortieren.
 *
 * Die Ansicht (pages/planrahmen/Stammdaten.vue) und der Test
 * (tests/pr-g1-geschlecht.test.mjs) nutzen DIESELBE Rechnung — so kann die
 * Oberfläche nicht anders filtern als der Test prüft.
 *
 * Der Server liefert `geschlecht` bereits normalisiert als 'm' | 'w';
 * '' heißt „keine Angabe". Diese Datei verlässt sich NICHT darauf: sie
 * normalisiert Rohwerte („Männlich", „W") genauso, damit alte Antworten und
 * Testdaten nicht zu falschen Filtern führen.
 *
 * DEV-B3 (Entscheidung Manuel 2026-10-29, DMB-e2a7f41994d7): Geschlecht gibt
 * es überall nur noch als „Männlich"/„Weiblich" (+ leer = nicht angegeben).
 * Alte Angaben wie „Divers"/„inter" werden zu '' („Nicht angegeben") — die
 * Datensätze selbst werden NICHT umgeschrieben.
 */

/** Beschriftung und Schlüssel der Filterauswahl (Reihenfolge wie im Feld). */
export const GESCHLECHT_FILTER = [
    { value: '', label: 'Alle Geschlechter' },
    { value: 'm', label: 'Männlich' },
    { value: 'w', label: 'Weiblich' },
    { value: 'ohne', label: 'Nicht angegeben' },
]

/** Kurzanzeige je Person in der Tabelle (klein und ruhig). */
const KURZ = { m: 'm', w: 'w' }

/** Ausführliche Beschriftung für aria-label/title. */
const LANG = { m: 'Männlich', w: 'Weiblich' }

// DEV-B3: Nur männlich und weiblich. Alles andere (auch „divers"/„inter")
// ergibt '' = „keine Angabe" — fail-closed, damit niemand in einer Auswahl
// landet, die es nicht mehr gibt.
const ALIASE = new Map([
    ['m', 'm'], ['maennlich', 'm'], ['mann', 'm'], ['male', 'm'], ['man', 'm'],
    ['w', 'w'], ['weiblich', 'w'], ['frau', 'w'], ['female', 'w'], ['woman', 'w'],
])

/**
 * Rohangabe auf 'm' | 'w' | '' abbilden.
 *
 * Unbekanntes ergibt '' („keine Angabe") — fail-closed, damit niemand
 * versehentlich in der Männer-Auswahl landet. Gleiche Regeln wie im Backend
 * (`geschlecht_normalisieren` in planrahmen/datenquelle_db.py).
 */
export function geschlechtNormalisieren(roh) {
    if (typeof roh !== 'string') return ''
    const key = roh.trim().toLocaleLowerCase('de-DE')
        .replace(/ä/g, 'ae').replace(/ß/g, 'ss')
    return ALIASE.get(key) || ''
}

/** Einbuchstabige Anzeige ('m' | 'w') oder '–' für „keine Angabe". */
export function geschlechtKurz(roh) {
    return KURZ[geschlechtNormalisieren(roh)] || '–'
}

/** Ausgeschriebene Anzeige („Männlich") oder „Nicht angegeben". */
export function geschlechtLang(roh) {
    return LANG[geschlechtNormalisieren(roh)] || 'Nicht angegeben'
}

/** Trifft die Person die Filterwahl? `wahl` ist '', 'm', 'w' oder 'ohne'. */
export function passtGeschlecht(person, wahl) {
    if (!wahl) return true
    const g = geschlechtNormalisieren(person?.geschlecht)
    return wahl === 'ohne' ? g === '' : g === wahl
}

/** Textsuche über Name, Kürzel und Kennung (wie bisher). */
export function passtSuche(person, suche) {
    const q = String(suche || '').trim().toLocaleLowerCase('de-DE')
    if (!q) return true
    return [person?.name, person?.kuerzel, person?.id, person?.kennung]
        .some((t) => String(t || '').toLocaleLowerCase('de-DE').includes(q))
}

/** Gruppe: leer = alle, sonst muss die Gruppe in `person.gruppen` stehen. */
export function passtGruppe(person, gruppe) {
    if (!gruppe) return true
    return (person?.gruppen || []).includes(gruppe)
}

/** Personen für Suche + Gruppe + Geschlecht zusammen (alle Filter wirken UND). */
export function personenFiltern(personen, { suche = '', gruppe = '', geschlecht = '' } = {}) {
    return (Array.isArray(personen) ? personen : [])
        .filter((p) => passtGruppe(p, gruppe) && passtGeschlecht(p, geschlecht) && passtSuche(p, suche))
}

const ORDNUNG = { m: 0, w: 1, '': 2 }

/**
 * Sortierschlüssel einer Person: erst Geschlecht (m, w, ohne Angabe),
 * dann Name (deutsche Sortierung, natürliche Zahlenfolge). Der Name ist der
 * zweite Schlüssel, damit die Reihenfolge innerhalb eines Geschlechts ruhig
 * und vorhersehbar bleibt.
 */
export function sortSchluessel(person) {
    const g = geschlechtNormalisieren(person?.geschlecht)
    return [ORDNUNG[g], String(person?.name || person?.anzeige || person?.kennung || person?.id || '')]
}

/**
 * Nach Geschlecht sortieren. `richtung` ist 'auf' (m → w → ohne) oder
 * 'ab' (umgekehrt); der Name läuft immer aufsteigend, damit die Liste beim
 * Umschalten nicht komplett durchgemischt wirkt.
 */
export function nachGeschlechtSortieren(personen, richtung = 'auf') {
    const liste = [...(Array.isArray(personen) ? personen : [])]
    const faktor = richtung === 'ab' ? -1 : 1
    liste.sort((a, b) => {
        const [ga, na] = sortSchluessel(a)
        const [gb, nb] = sortSchluessel(b)
        if (ga !== gb) return (ga - gb) * faktor
        return na.localeCompare(nb, 'de-DE', { numeric: true })
    })
    return liste
}

/**
 * Spaltenkopf-Logik der Tabelle: Klick schaltet auf/ab, ein drittes Mal
 * zurück auf „ohne Sortierung" (dann gilt wieder die Server-Reihenfolge).
 * Rückgabe ist der neue Zustand { spalte, richtung }.
 */
export function sortierungUmschalten(aktuell, spalte) {
    const a = aktuell || { spalte: '', richtung: 'auf' }
    if (a.spalte !== spalte) return { spalte, richtung: 'auf' }
    if (a.richtung === 'auf') return { spalte, richtung: 'ab' }
    return { spalte: '', richtung: 'auf' }
}

/** Anzahl der Personen ohne Geschlechtsangabe (für den Hinweis). */
export function anzahlOhneAngabe(personen) {
    return (Array.isArray(personen) ? personen : [])
        .filter((p) => geschlechtNormalisieren(p?.geschlecht) === '').length
}

/** Filter + Sortierung in der Reihenfolge, in der die Tabelle sie zeigt. */
export function personenAnzeigen(personen, { suche = '', gruppe = '', geschlecht = '', sortierung } = {}) {
    const gefiltert = personenFiltern(personen, { suche, gruppe, geschlecht })
    if (sortierung?.spalte === 'geschlecht') {
        return nachGeschlechtSortieren(gefiltert, sortierung.richtung)
    }
    return gefiltert
}
