/**
 * UI-R9 — Aufgaben: reine Regeln der Oberfläche (ohne Vue, ohne Netz).
 *
 * Die Rechte-Logik liegt ALLEIN beim Server (R-7b, `darf_abhaken` /
 * `darf_bearbeiten` je Zeile). Hier stehen nur die Regeln, die man ohne
 * Server prüfen kann und die in Tests belegbar sein sollen:
 *
 *   · welche Kästchen/ Menüs eine Zeile bekommt,
 *   · wie die Liste in offen/erledigt zerfällt,
 *   · wie eine Zuweisung als Text erscheint („Zugewiesen an …“),
 *   · was ein Fälligkeitsdatum als Text sagt (überfällig / heute / …),
 *   · welche Personen zur Auswahl „Zuweisen an“ stehen.
 *
 * Bewusst KEINE eigene Rechteentscheidung: ohne `darf_*` im Datensatz gilt
 * „nein“ (fail closed) — die Oberfläche bietet dann nichts an, was der
 * Server ohnehin verweigern würde.
 */

/** Wahr, wenn der Server das Abhaken erlaubt (nur dann ist das Kästchen aktiv). */
export function darfAbhaken(aufgabe) {
    return aufgabe?.darf_abhaken === true
}

/** Wahr, wenn der Server Zuweisen/Löschen erlaubt (nur dann gibt es das Menü). */
export function darfBearbeiten(aufgabe) {
    return aufgabe?.darf_bearbeiten === true
}

/** Offen ist alles, was nicht erledigt ist. */
export function istOffen(aufgabe) {
    return !aufgabe?.erledigt
}

/** Zwei getrennte Listen: offene und erledigte Aufgaben (Reihenfolge bleibt). */
export function teileNachErledigt(aufgaben) {
    const liste = Array.isArray(aufgaben) ? aufgaben : []
    return {
        offen: liste.filter(istOffen),
        erledigt: liste.filter(a => !!a?.erledigt),
    }
}

/**
 * Text der Zuweisung. Die eigene Aufgabe der Kachel (ohne Gruppe, mit
 * `eigene`) wird nie zugewiesen und sagt deshalb nichts; jede andere Aufgabe
 * ohne Zuweisung sagt „Niemandem zugewiesen“ — kein leerer Fleck, der wie ein
 * Fehler aussieht.
 *
 * UI-R9c: Die Kopplung an `gruppe`/`untergruppe` ist weg. Die Gruppenseite
 * (`get_gruppe_detail` → `_aufgaben_ausliefern` OHNE `mit_gruppe`) schickt
 * diese Felder gar nicht — dort stand der Text deshalb leer. `eigene` ist das
 * einzige Feld, das „keine Gruppenaufgabe“ bedeutet, und kommt nur aus
 * `get_meine_aufgaben`.
 */
export function zuweisungsText(aufgabe) {
    const name = (aufgabe?.zugewiesen_name || '').trim()
    if (name) return `Zugewiesen an ${name}`
    if (aufgabe?.eigene) return ''
    return 'Niemandem zugewiesen'
}

/** Zähltext „n offen“ / „n offen, m erledigt“ — ohne Klammerplural. */
export function offenZahlText(aufgaben) {
    const { offen, erledigt } = teileNachErledigt(aufgaben)
    const offenText = offen.length === 1 ? '1 offen' : `${offen.length} offen`
    if (!erledigt.length) return offenText
    const erledigtText = erledigt.length === 1 ? '1 erledigt' : `${erledigt.length} erledigt`
    return `${offenText}, ${erledigtText}`
}

/**
 * Datum als deutsches Kalenderdatum (ISO `YYYY-MM-DD` oder Zeitstempel).
 *
 * Bewusst mit `formatToParts` und OHNE `2-digit`: die Laufzeit liefert je nach
 * ICU-Stand „5.11.2026“ oder „05.11.2026“. Ein reines Datum `YYYY-MM-DD` ist
 * ein Kalendertag, kein Zeitpunkt — es wird deshalb direkt zerlegt, damit
 * keine Zeitzone den Tag verschieben kann.
 */
export function datumText(wert) {
    if (!wert) return ''
    const reinesDatum = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(wert))
    if (reinesDatum) {
        return `${Number(reinesDatum[3])}.${Number(reinesDatum[2])}.${reinesDatum[1]}`
    }
    const d = new Date(wert)
    if (isNaN(d.getTime())) return String(wert)
    const teile = new Intl.DateTimeFormat('de-DE', {
        day: 'numeric', month: 'numeric', year: 'numeric',
    }).formatToParts(d)
    const wert_ = (typ) => (teile.find(t => t.type === typ) || {}).value || ''
    return `${wert_('day')}.${wert_('month')}.${wert_('year')}`
}

/** Tagesdatum eines Zeitstempels als `YYYY-MM-DD` in LOKALER Zeit (ohne Uhrzeit). */
function tagesschluessel(datum) {
    const d = datum instanceof Date ? datum : new Date(datum)
    if (isNaN(d.getTime())) return ''
    const monat = String(d.getMonth() + 1).padStart(2, '0')
    const tag = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${monat}-${tag}`
}

/**
 * Fälligkeit als Satz: „Heute fällig“, „Überfällig seit …“, „Fällig am …“.
 * Erledigte Aufgaben tragen KEINEN Fälligkeitstext mehr — die Frist ist vorbei,
 * ein „überfällig“ an einer abgehakten Aufgabe wäre eine Falschaussage.
 *
 * @param {object} aufgabe  Zeile aus `get_aufgaben`/`get_meine_aufgaben`
 * @param {Date} [jetzt]    Prüfzeitpunkt (Tests setzen ihn fest)
 * @returns {{text: string, ueberfaellig: boolean}}
 */
export function faelligkeit(aufgabe, jetzt = new Date()) {
    if (!aufgabe?.faellig || aufgabe?.erledigt) return { text: '', ueberfaellig: false }
    const tag = tagesschluessel(aufgabe.faellig)
    const heute = tagesschluessel(jetzt)
    if (!tag) return { text: '', ueberfaellig: false }
    if (tag === heute) return { text: 'Heute fällig', ueberfaellig: false }
    if (tag < heute) return { text: `Überfällig seit ${datumText(aufgabe.faellig)}`, ueberfaellig: true }
    return { text: `Fällig am ${datumText(aufgabe.faellig)}`, ueberfaellig: false }
}

/**
 * Auswahl „Zuweisen an“ aus den Mitgliedern, die die Gruppenseite schon kennt.
 *
 * · nur echte Personen mit Kennung (keine Zeile ohne `mitglied`),
 * · alphabetisch nach dem angezeigten Namen,
 * · ohne Dubletten (eine Person steht je Mitgliedschaft einmal in der Liste),
 * · `''` als erste Option heißt „niemanden“ (Zuweisung aufheben) — bewusst
 *   NICHT `null`, damit das Auswahlfeld einen beschrifteten Eintrag hat.
 */
export function zuweisungsOptionen(mitglieder) {
    const gesehen = new Set()
    const personen = []
    for (const m of Array.isArray(mitglieder) ? mitglieder : []) {
        const wert = m?.mitglied || ''
        if (!wert || gesehen.has(wert)) continue
        gesehen.add(wert)
        personen.push({
            value: wert,
            label: (m?.vollstaendiger_name || m?.name || wert).trim(),
        })
    }
    personen.sort((a, b) => a.label.localeCompare(b.label, 'de'))
    return [{ value: '', label: 'Niemanden (offen für die Gruppe)' }, ...personen]
}

/**
 * Ziel einer Gruppenaufgabe als Adresse (für den Link „Zur Gruppe“).
 * Untergruppen laufen über dieselbe Seitenadresse wie Gruppen
 * (`#/gruppe/<name>`), damit ein Klick immer beim richtigen Objekt landet.
 */
export function gruppenHref(aufgabe) {
    const ziel = aufgabe?.untergruppe || aufgabe?.gruppe
    return ziel ? `#/gruppe/${ziel}` : ''
}

/**
 * Anzeigename einer Gruppenaufgabe: `gruppe_name` aus der Antwort.
 *
 * UI-R9c: Der Server (`get_meine_aufgaben`, R-12k) schickt den Anzeigenamen
 * der Untergruppe bzw. Gruppe; `null` heißt „eigene Aufgabe“. Die Kennung
 * (`untergruppe`/`gruppe`) ist NUR noch für den Link da — sie wurde zuvor als
 * Text angezeigt („UG-2“). Fehlt `gruppe_name` (alter Server), bleibt der Text
 * leer statt einer Kennung, die niemand lesen soll.
 */
export function gruppenName(aufgabe) {
    return String(aufgabe?.gruppe_name || '').trim()
}

/**
 * Anzeigename einer Gruppe OHNE rohe Kennung: der Name aus der Antwort
 * (`untergruppenname`/`gruppenname`), sonst der für Menschen gedachte
 * Ersatztext (`*_name`, `titel`), zuletzt die Kennung selbst. UI-R9b: der Link
 * „Zur Gruppe“ zeigte die ID („GRU-1“) an — gelesen wird der Name.
 */
export function anzeigeName(v, ersatz = '') {
    const wert = v?.untergruppenname || v?.gruppenname || v?.name_anzeige
        || v?.gruppen_name || v?.untergruppen_name || v?.titel
    return String(wert || ersatz || '').trim()
}

/**
 * Darf man im Feld „Meine Aufgaben“ eine EIGENE Aufgabe anlegen?
 * Der Server entscheidet (`get_meine_aufgaben` liefert `darf_anlegen`, geprüft
 * mit derselben Regel wie `create_aufgabe`). Ohne Angabe: nein.
 */
export function darfEigeneAnlegen(rechte) {
    return rechte?.darf_eigene_aufgabe === true
}
