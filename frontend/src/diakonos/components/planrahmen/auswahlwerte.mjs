/**
 * Auswahlwerte: gespeicherte Kennung und Anzeigename (UXP-R23, P3-1b W3, P3-1c A).
 *
 * Ein `auswahl`-Feld (Feld, Merkmal oder Parameter) traegt in `werte` die
 * GESPEICHERTEN Kennungen — ASCII, ohne Umlaute („Maennerchor“, „Floete“).
 * Diese Kennungen stehen in Plaenen, Vorlagen und Vergleichen; sie werden nie
 * nachtraeglich umbenannt, sonst passen gespeicherte Plaene nicht mehr.
 *
 * Angezeigt wird der Anzeigename aus `anzeigenamen` („Männerchor“, „Flöte“).
 *
 * P3-1c (A) — zwei Luecken geschlossen:
 *   1. Die Anzeigenamen werden jetzt an ALLEN Anzeigeorten benutzt (Zellen,
 *      Ablauf, Programm/Druck, Filter), nicht nur im Formular.
 *   2. Aeltere, in der Betriebs-DB gespeicherte Vorlagenversionen tragen
 *      selbst kein `anzeigenamen`. Der Name wird dann ZUR LAUFZEIT aus dem
 *      Katalog aufgeloest. Katalogquellen sind (in dieser Reihenfolge, spaeter
 *      gewinnt) die KOCHBUCH-Vorlagen und die jeweils neueste Plantyp-Version.
 *      KEINE Datenmigration — nur ein Nachschlag (P3-1d W2).
 *
 * Merkmale sind gruppenweise organisiert (`{person: […], lieder: […]}`) — der
 * Katalog wertet diese Gruppenform aus (`alleMerkmale`), nicht `{id: def}`.
 *
 * Katalog-Register: `merkeKatalogDefinition` sammelt je Feld-/Merkmals-/Pa-
 * rameter-`id` die zuletzt gesehenen `anzeigenamen`. `wertAnzeige` greift
 * darauf NUR zurueck, wenn die uebergebene Definition selbst keinen Eintrag
 * fuer den Wert hat — die Definition am Objekt hat immer Vorrang.
 */

/** id → { wert → Anzeigename } aus dem (neuesten) Katalog. */
const katalog = new Map()

/**
 * Eine Katalog-Definition merken (z. B. die neueste Plantyp-Version). Sammelt
 * `anzeigenamen` aller Felder (rekursiv), Merkmale und Parameter.
 */
export function merkeKatalogDefinition(definition) {
    if (!definition || typeof definition !== 'object') return
    for (const feld of alleFelder(definition.felder)) {
        if (!feld || typeof feld.id !== 'string' || !feld.anzeigenamen) continue
        if (!feld.anzeigenamen || typeof feld.anzeigenamen !== 'object') continue
        katalog.set(feld.id, { ...(katalog.get(feld.id) || {}), ...feld.anzeigenamen })
    }
    // P3-1d (W2): Merkmale sind GRUPPENWEISE organisiert
    // (`{person: [merkmal, …], lieder: [merkmal, …]}`), nicht `{id: def}`.
    // Vorher wurde deshalb nie ein Merkmal in den Katalog uebernommen und
    // gespeicherte Vorlagen zeigten weiter „Floete“ statt „Flöte“.
    for (const def of alleMerkmale(definition.merkmale)) {
        const karte = karteVon(def)
        if (karte && def?.id) katalog.set(def.id, { ...(katalog.get(def.id) || {}), ...karte })
    }
    for (const def of definition.parameter || []) {
        const karte = karteVon(def)
        if (karte && def?.id) katalog.set(def.id, { ...(katalog.get(def.id) || {}), ...karte })
    }
}

/** `anzeigenamen` einer Definition — nur wenn vorhanden und Objekt. */
function karteVon(def) {
    const karte = def?.anzeigenamen
    return (karte && typeof karte === 'object') ? karte : null
}

/**
 * Alle Merkmals-Definitionen — die echte Form ist gruppiert: `merkmale` ist ein
 * Objekt `{gruppe: [merkmal, …]}` (person, lieder, …). Die alte Einzelform
 * `{id: merkmal}` wird weiterhin verstanden (Tests, aeltere Aufrufer).
 */
export function alleMerkmale(merkmale) {
    if (!merkmale || typeof merkmale !== 'object') return []
    const liste = []
    for (const inhalt of Object.values(merkmale)) {
        if (Array.isArray(inhalt)) {
            for (const m of inhalt) if (m && typeof m === 'object') liste.push(m)
        } else if (inhalt && typeof inhalt === 'object' && typeof inhalt.id === 'string') {
            liste.push(inhalt)
        }
    }
    return liste
}

/**
 * Kochbuch-Vorlagen als Katalogquelle (P3-1d W2).
 *
 * In der Betriebs-DB tragen die gespeicherten Plantyp-Versionen oft KEIN
 * `anzeigenamen` (sie wurden vor der Katalogkennung angelegt). Angezeigt werden
 * soll trotzdem „Flöte“/„Männerchor“. Deshalb werden die Kochbuch-Definitionen
 * (dieselbe Quelle, aus der die Planvorlagen einmal angelegt wurden) zusaetzlich
 * als Nachschlag gemerkt.
 *
 * Vorrang: eine Definition AM OBJEKT gewinnt immer; unter den Katalogquellen
 * gewinnt die ZULETZT gemerkte. Die Oberflaeche merkt daher die Kochbuch-
 * Vorlagen ZUERST und die gespeicherten Versionen DANACH — so bleiben
 * betriebliche Aenderungen an Versionen wirksam.
 */
export function merkeKochbuchVorlage(definition) {
    merkeKatalogDefinition(definition)
}

/** Alle Felder eines Baums (rekursiv: Gruppen, Varianten, Teile, Ablauf). */
function alleFelder(felder, gefunden = []) {
    for (const f of felder || []) {
        if (!f || typeof f !== 'object') continue
        gefunden.push(f)
        if (Array.isArray(f.inhalt)) alleFelder(f.inhalt, gefunden)
        for (const zweig of [...(f.varianten || []), ...(f.teile || [])]) {
            const obj = typeof zweig === 'string' ? { id: zweig } : zweig
            if (Array.isArray(obj?.inhalt)) alleFelder(obj.inhalt, gefunden)
        }
        for (const elem of f.elemente || []) {
            const e = typeof elem === 'string' ? { typ: elem } : elem
            if (Array.isArray(e?.inhalt)) alleFelder(e.inhalt, gefunden)
        }
    }
    return gefunden
}

/** Katalog zuruecksetzen (Tests / Plantypwechsel). */
export function katalogLeeren() {
    katalog.clear()
}

/**
 * Anzeigename eines Auswahlwerts.
 *
 * Reihenfolge: eigener Eintrag der Definition → Katalog-Nachschlag (fuer
 * gespeicherte Vorlagen ohne `anzeigenamen`) → der Wert selbst. Kein
 * Platzhalter, keine stille Ersatzschreibung.
 */
export function wertAnzeige(definition, wert) {
    const karte = definition?.anzeigenamen
    if (karte && Object.prototype.hasOwnProperty.call(karte, wert)) return karte[wert]
    const ausKatalog = definition?.id ? katalog.get(definition.id) : null
    if (ausKatalog && Object.prototype.hasOwnProperty.call(ausKatalog, wert)) return ausKatalog[wert]
    return wert
}

/**
 * Alle Auswahlwerte einer Definition mit Anzeigenamen, in der Reihenfolge von
 * `werte` — fuer Umschalter, Auswahllisten und Chips.
 * @returns {Array<{wert: string, text: string}>}
 */
export function auswahlOptionen(definition) {
    const liste = definition?.werte
    if (!Array.isArray(liste)) return []
    return liste.map(w => ({ wert: w, text: wertAnzeige(definition, w) }))
}
