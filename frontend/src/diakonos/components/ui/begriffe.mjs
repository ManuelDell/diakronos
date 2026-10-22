/**
 * BEGRIFFE — verbindliches Glossar der Oberfläche (Standard S15).
 *
 * Viele Befunde der Nachtprüfung waren reine Wortwahl: „freigeben“ hieß an
 * vier Stellen anders, „Anmeldung“ bedeutete zugleich Login und
 * Registrierungsantrag, „Vorschlag“ hatte vier Bedeutungen, „Plantyp“ war
 * Fachjargon. Hier steht EINMAL, welches Wort wofür gilt; Oberfläche, Tests
 * und Dokumentation (doku/GLOSSAR.md) ziehen daraus.
 *
 * Zielgruppe: ehrenamtliche Planerinnen und Planer. Kein Fachbegriff ohne
 * Erklärung, keine internen Kennungen im Text.
 */

/** Produktname — festgelegt, nicht mehr wechselnd (OP-UI-24). */
export const PRODUKTNAME = 'Diakronos'

/**
 * Wortlisten: je Begriff die zulässige Schreibweise und die verbannten
 * Varianten. `verboten` dient dem Wächter-Test (p3-1-begriffe).
 */
export const BEGRIFFE = {
    freigeben: {
        wort: 'Freigeben',
        bedeutet: 'Einen Vorschlag oder Termin verbindlich machen (vorher: wartet auf Freigabe).',
        verboten: ['Genehmigen', 'Bestätigen', 'Festlegen', 'freischalten'],
    },
    freigabe: {
        wort: 'Freigabe',
        bedeutet: 'Der Schritt, nach dem alle sichtbaren Termine verbindlich sind. Im Moderationsbrett heißt die Ablage deshalb „Freigeben“ — vorher hieß sie „Festlegen“.',
        verboten: ['Festlegen', 'Festlegung'],
    },
    festgelegt: {
        wort: 'Von Hand festgelegt',
        bedeutet: 'Ein Wert im Plan, den du selbst eingetragen hast und den der Vorschlag unverändert lässt (📌). NICHT zu verwechseln mit dem Freigeben von Terminen — diese Bedeutung ist ausdrücklich richtig und bleibt.',
        verboten: [],
    },
    anmeldung: {
        wort: 'Anmeldung',
        bedeutet: 'NUR die Anmeldung mit Konto (Login). Ein Antrag auf Mitgliedschaft heißt „Registrierung“.',
        verboten: [],
    },
    planvorlage: {
        wort: 'Planvorlage',
        bedeutet: 'Die wiederverwendbare Vorlage eines Plans (intern: Plantyp).',
        verboten: ['Plantyp'],
    },
    uebersicht: {
        wort: 'Übersicht',
        bedeutet: 'Die Startseite (intern: Dashboard) — in der Oberfläche immer „Übersicht“, nie „Dashboard“.',
        verboten: ['Dashboard'],
    },
    registrierung: {
        wort: 'Registrierung',
        bedeutet: 'Der Antrag einer Person auf Mitgliedschaft. Angenommen wird er mit „Aufnehmen“ — das Wort „Genehmigt“ gehört zum Freigeben von Terminen und Plänen, nicht hierher.',
        verboten: ['Genehmigt', 'Genehmigung'],
    },
    eigenschaft: {
        wort: 'Eigenschaft',
        bedeutet: 'Eine Angabe, die eine Person oder ein Eintrag haben kann (intern: Merkmal).',
        verboten: [],
    },
    einteilen: {
        wort: 'Automatisch einteilen',
        bedeutet: 'Der Vorschlag der Engine: sie füllt die Plätze nach den Regeln.',
        verboten: ['Vorschlag erzeugen', 'generieren'],
    },
    auswahl: {
        wort: 'Auswahl',
        bedeutet: 'Was beim automatischen Einteilen herauskommt, bevor es freigegeben ist.',
        verboten: [],
    },
    wartet_auf_freigabe: {
        wort: 'Wartet auf Freigabe',
        bedeutet: 'Zustand eines Vorschlags, der noch nicht verbindlich ist.',
        verboten: ['Vorschlag (Zustand)', 'vorgeschlagen'],
    },
    anlegen: {
        wort: 'Anlegen',
        bedeutet: 'Etwas Neues erzeugen (Plan, Vorlage, Eintrag).',
        verboten: [],
    },
    speichern: {
        wort: 'Speichern',
        bedeutet: 'Änderungen an einem bestehenden Objekt übernehmen.',
        verboten: [],
    },
    veroeffentlichen: {
        wort: 'Veröffentlichen',
        bedeutet: 'Einen Plan für alle sichtbar machen.',
        verboten: [],
    },
}

/**
 * Wort im richtigen Numerus — OP-CHOR-12/OP-UI-27: Die Oberfläche schrieb
 * bisher „1 Lied(er)“, „1 Termin(e)“, „1 Fassung(en)“. Das Klammerplural
 * liest sich wie ein Formular und passt zu keiner Zahl; hier steht EINMAL
 * die Regel, die Lieder, Liedgruppen, Moderation und der Plan-Rahmen
 * gemeinsam nutzen.
 *
 * @param {number} n
 * @param {string} einzahl   z. B. 'Lied'
 * @param {string} [mehrzahl] z. B. 'Lieder' (Vorgabe: einzahl + 'en')
 * @returns {string} z. B. 'Lied' oder 'Lieder'
 */
export function wortImNumerus(n, einzahl, mehrzahl) {
    return Math.abs(Number(n)) === 1 ? einzahl : (mehrzahl || `${einzahl}en`)
}

/**
 * Zahl mit Wort im richtigen Numerus und deutscher Tausendertrennung
 * („1 Änderung“, „1.234 Lieder“).
 */
export function zahlWort(n, einzahl, mehrzahl) {
    const zahl = Number(n)
    if (!Number.isFinite(zahl)) return ''
    return `${zahl.toLocaleString('de-DE')} ${wortImNumerus(zahl, einzahl, mehrzahl)}`
}

/** Ist die Schreibweise verboten (S15)? Gibt die verletzten Begriffe zurück. */
export function verboteneBegriffe(text, ausgenommen = []) {
    const treffer = []
    for (const [id, def] of Object.entries(BEGRIFFE)) {
        if (ausgenommen.includes(id)) continue
        for (const v of def.verboten) {
            if (text.includes(v)) treffer.push({ begriff: id, variante: v })
        }
    }
    return treffer
}
