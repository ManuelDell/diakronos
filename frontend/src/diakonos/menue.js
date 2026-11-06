/**
 * Zentrale Menüdefinition (Standard S12).
 *
 * EINE Quelle für Seitenleiste (Desktop), Menü-Schublade (Handy, UX3e) und
 * Kopfleiste. Wer einen Menüpunkt ändert, ändert ihn hier — nirgends sonst.
 *
 * Felder eines Eintrags:
 *   id       stabile Kennung (für Tests und Markierung)
 *   label    sichtbare Beschriftung
 *   href     Zieladresse (#/…)
 *   icon     Name aus dem Symbolvorrat (siehe ICON_PFADE)
 *   seiten   Seitennamen, bei denen der Eintrag als „aktiv“ gilt
 *   rolle    'alle' | 'admin'  — nur Komfort: der Server prüft weiter
 *   rollen   Liste von Rollen, von denen EINE genügen muss (Alternative zu
 *            `rolle`; WEB-3: „Website“ für System Manager, Administrator und
 *            Website-Moderator). Nur Komfort — der Server prüft weiter.
 *   tester   true = nur mit Tester-Rolle sichtbar (Dev-Befunde)
 *   badge    optionale Kennzahl-Quelle (siehe AppSidebar)
 *   suche    true = Ziel erscheint in der Befehlspalette (UX3f, noch nicht
 *            gebaut). Seiten ohne Menüeintrag (z. B. Profil) tragen es am
 *            Seitennamen.
 *
 * Gruppen folgen dem Entwurf A1 (UX3a, siehe unten).
 */

/**
 * Gruppen folgen dem **Entwurf A1** (UX3a, Manuel 2026-11-03/04): Übersicht
 * steht allein oben, darunter die drei Gruppen „Gemeinde“ (Personen, Gruppen),
 * „Planen“ (Kalender, Dienste, Ressourcen) und „Inhalte“ (Beiträge, Wiki,
 * Lieder, Website). „Einstellungen“ liegt NICHT in der Liste, sondern unten im
 * Fußbereich der Seitenleiste (siehe FUSS_EINTRAEGE); „Profil“ und „Abmelden“
 * stehen dort ohnehin. Kopfleiste (AppTopbar) und Brotkrumen lesen dieselbe
 * Definition.
 *
 * Die früheren Einzelpunkte „Adressbuch“, „Dienstplan“, „Pläne“, „Meine
 * Dienste“, „Liedgruppen“, „Moderation“, „Datenschutz“ und „Einrichtung“ sind
 * KEINE eigenen Menüeinträge mehr; ihre Bereiche sind Reiter bzw. Ansichten
 * (Adressbuch → Personen, Dienstplan/Meine Dienste → Dienste, Moderation →
 * Kalender „Zu prüfen“, Liedgruppen → Lieder, Datenschutz → Personen). Die
 * alten Adressen leiten im Router dauerhaft weiter (Lesezeichen).
 */
import { WEBSITE_ROLLEN } from './composables/website.mjs'

export const MENUE = [
    {
        // Gruppe ohne Überschrift (Entwurf A1): „Übersicht“ steht allein oben.
        gruppe: '',
        eintraege: [
            { id: 'dashboard', label: 'Übersicht', href: '#/', icon: 'home', seiten: ['Home'], suche: true },
        ],
    },
    {
        gruppe: 'Gemeinde',
        eintraege: [
            {
                id: 'personen', label: 'Personen', href: '#/personen', icon: 'users',
                // UX3b: „Übersicht“ ist kein Reiter von Personen mehr —
                // der Einstieg zeigt die Liste (je Rolle Mitglieder- oder
                // Adressbuch-Sicht). „MitgliederUebersicht“ bleibt als
                // weitergeleitete Altadresse in der Liste (Lesezeichen).
                seiten: ['Personen', 'MitgliederListe', 'PersonenListe', 'PersonenAnfragen', 'PersonenDatenschutz', 'MitgliederDatenschutz', 'PersonenLoeschantraege',
                    'MitgliederLoeschantraege', 'PersonenImport', 'MitgliedDetail', 'Adressbuch'],
                rolle: 'alle', badge: 'anfragen', suche: true,
            },
            {
                id: 'gruppen', label: 'Gruppen', href: '#/gruppen', icon: 'layout-grid',
                seiten: ['GruppenBereich', 'GruppeDetail'], suche: true,
            },
        ],
    },
    {
        gruppe: 'Planen',
        eintraege: [
            { id: 'kalender', label: 'Kalender', href: '#/kalender', icon: 'calendar', seiten: ['Kalender', 'KalenderImport', 'KalenderVerwaltung', 'Pruefen', 'Moderation'], suche: true },
            { id: 'dienste', label: 'Dienste', href: '#/dienste', icon: 'clock', seiten: ['Dienste', 'Dienstplan', 'DiensteDienstplaene', 'DiensteVorlagen', 'PlanrahmenUebersicht', 'PlanrahmenPlan', 'PlanrahmenEinrichten', 'PlanrahmenPlantypEditor', 'PlanrahmenStammdaten', 'PlanrahmenDienste'], suche: true },
            { id: 'ressourcen', label: 'Ressourcen', href: '#/ressourcen', icon: 'box', seiten: ['Ressourcen', 'RessourcenVerwaltung'], suche: true },
        ],
    },
    {
        gruppe: 'Inhalte',
        eintraege: [
            { id: 'beitraege', label: 'Beiträge', href: '#/beitraege', icon: 'file-text', seiten: ['Beitraege'], suche: true },
            { id: 'wiki', label: 'Wiki', href: '#/wiki', icon: 'help-circle', seiten: ['Wiki'], suche: true },
            { id: 'lieder', label: 'Lieder', href: '#/lieder', icon: 'music', seiten: ['Lieder', 'LiedDetail', 'LiedNeu', 'Liedgruppen', 'LiedgruppeDetail'], suche: true },
            // WEB-3: „Website“ steht bei den Inhalten — die Redaktion der
            // Gemeinde-Seiten ist eine Inhaltsaufgabe (Entwurf A1). Sichtbar für
            // die WEBSITE_ROLLEN (System Manager, Administrator,
            // Website-Moderator); der Server prüft nach.
            {
                id: 'website', label: 'Website', href: '#/website', icon: 'globe',
                seiten: ['Website'], rollen: WEBSITE_ROLLEN, suche: true,
            },
        ],
    },
]

/**
 * Fußbereich der Seitenleiste (Entwurf A1): „Einstellungen“ steht dort, nicht
 * in der Gruppenliste. Nur Administration — der Server prüft jede Seite erneut.
 * ON-3b: „Einrichtung“ bleibt KEIN Menüpunkt (Ersteinrichtung des Containers).
 */
export const FUSS_EINTRAEGE = [
    { id: 'einstellungen', label: 'Einstellungen', href: '#/einstellungen', icon: 'settings', seiten: ['Einstellungen', 'EinstellungenGemeinde', 'EinstellungenAnmeldung', 'EinstellungenRollen', 'EinstellungenRegistrierung', 'EinstellungenDatenschutz', 'EinstellungenDatensicherung', 'EinstellungenMailversand', 'EinstellungenDevModus', 'EinstellungenPapierkorb', 'EinstellungenWebsite', 'EinstellungenGestaltung', 'Einrichtung'], rolle: 'admin', suche: true },
]

/**
 * Adressen, die AUSSCHLIESSLICH Admin-Seiten öffnen (Rechte-Guard des Routers
 * und Sichtbarkeit im Menü ziehen aus DERSELBEN Liste — sonst liefen sie
 * auseinander). „Dev-Befunde“ und der Entwicklermodus liegen im Profilmenü.
 */
export const MENUE_EINTRAEGE = [...MENUE.flatMap(g => g.eintraege), ...FUSS_EINTRAEGE]

/** Reiter des Personen-Bereichs (Entwurf A3; Entscheidung 4: jede Adresse eigen).
 *  Nur Reiter, deren Inhalt es schon gibt — kein toter Knopf.
 *  UX3a: „Adressbuch“ und „Datenschutz“ sind Reiter dieses Bereichs geworden
 *  (vorher eigene Menüpunkte); die Adressen liegen unter `#/personen/…`. */
export const MITGLIEDER_REITER = [
    // UX3b (Entwurf A3, Entscheidung Manuel): VIER Reiter — Liste · Anfragen ·
    // Datenschutz · Import. „Liste“ ist für ALLE sichtbar und zeigt je Rolle
    // die passende Quelle (Mitgliederliste oder Adressbuch-Sicht); ein eigener
    // Reiter „Adressbuch“ entfällt, weil die Liste diese Sicht schon ist.
    // Reiter, die nur der Mitgliederbereich selbst kennt (Übersicht,
    // Löschanträge), stehen hier NICHT: sie haben weiter ihre Adresse, sind
    // aber kein Reiter des Bereichs mehr (Entwurf A3).
    { id: 'liste', label: 'Liste', href: '#/personen/liste', seite: 'MitgliederListe', rolle: 'alle' },
    { id: 'anfragen', label: 'Anfragen', href: '#/personen/anfragen', seite: 'MitgliederAnfragen', rolle: 'admin' },
    { id: 'datenschutz', label: 'Datenschutz', href: '#/personen/datenschutz', seite: 'MitgliederDatenschutz', rolle: 'admin' },
    { id: 'import', label: 'Import', href: '#/personen/import', seite: 'MitgliederImport', rolle: 'admin' },
]

/**
 * Unterbereiche von „Anfragen“ (UX-A2a). Bis hierher waren sie eine zweite
 * Reiterzeile IN der Anfragen-Seite; jetzt sind sie eigene Einträge der
 * Mitglieder-Bereichsliste, eingerückt UNTER „Anfragen“.
 *
 * Entwurf A2 (Operator-Review, Punkt 3): „Anfragen“ selbst IST der erste
 * Unterbereich — der Hauptpunkt mit der Zahl führt auf die Anfragenliste.
 * Deshalb steht hier nur, was eingerückt DARUNTER gehört: „Links & QR-Codes“
 * und „Formulare“. Ein zweiter Eintrag „Anfragen“ wäre ein doppelter Punkt.
 *
 * Jeder Unterbereich hat eine EIGENE Adresse mit Abfrageteil
 * (`#/mitglieder/anfragen?bereich=links`). Der Abfrageteil ist bewusst
 * gewählt: die Seite bleibt dieselbe (Router, Rechte-Guard, Fenstertitel),
 * der Unterbereich ist teilbar und übersteht das Neuladen. Ohne Abfrageteil
 * ist es der erste Eintrag.
 *
 * `seite` gilt für alle drei Ansichten — die Seitenleiste markiert weiter
 * „Mitglieder“, der Rechte-Guard (`ADMIN_ONLY_PAGES`) prüft weiter
 * `MitgliederAnfragen`.
 */
export const ANFRAGEN_UNTERBEREICHE = [
    { id: 'links', label: 'Links & QR-Codes', seite: 'MitgliederAnfragen', rolle: 'admin' },
    { id: 'formulare', label: 'Formulare', seite: 'MitgliederAnfragen', rolle: 'admin' },
]

/** Der Unterbereich, auf den der Hauptpunkt „Anfragen“ führt (die Liste). */
export const ANFRAGEN_HAUPTBEREICH = 'anfragen'

/**
 * Werte der Einträge. Ober- und Unterpunkt teilen sich NICHT denselben Wert —
 * sonst wären alle gleichzeitig „gewählt“ (im Browser gefunden: drei
 * aria-current). `bereichsWertFuer`/`aktiverBereichsWert` bilden dasselbe Paar
 * im Rahmen (pages/mitglieder/Bereich.vue).
 */
export function bereichsWert(seite) {
    return seite || ''
}

/** Wert eines Unterbereichs: Seite plus Unterbereich. */
export function unterbereichsWert(seite, bereich) {
    return bereich ? `${seite}:${bereich}` : bereichsWert(seite)
}

/**
 * Die Einträge der Mitglieder-Bereichsliste in Anzeigereihenfolge — EINE
 * Quelle für Oberfläche, Tests und Adressen.
 *
 * `zahl: 'anfragen'` ist eine Kennzahl-QUELLE, kein Wert: die Zahl offener
 * Anfragen kommt vom Server (`get_navigation_zaehler`, dieselbe Abfrage und
 * derselbe Stand wie die Kennzahl an „Mitglieder“ in der Seitenleiste). Ohne
 * Zahl fehlt der Schlüssel — dann wird nichts angezeigt (nie eine erfundene
 * Null).
 *
 * Der Hauptpunkt „Anfragen“ führt auf die Anfragenliste (`?bereich=anfragen`
 * wäre derselbe Inhalt) und trägt die Zahl; darunter stehen eingerückt nur
 * „Links & QR-Codes“ und „Formulare“ (Entwurf A2).
 *
 * @param {{istAdmin?: boolean, anfragenZahl?: number|null}} optionen
 * @returns {Array<{id, label, href, value, seite, rolle, zahl, unterpunkte}>}
 */
export function mitgliederBereichEintraege({ istAdmin = false, anfragenZahl = null } = {}) {
    const sichtbar = sichtbareMitgliederReiter({ istAdmin })
    const eintraege = sichtbar.map(r => ({
        id: r.id,
        label: r.label,
        href: r.href,
        value: bereichsWert(r.seite),
        seite: r.seite,
        rolle: r.rolle,
        zahl: r.id === 'anfragen' ? anfragenZahl : null,
    }))
    const anfragen = eintraege.find(e => e.id === 'anfragen')
    if (anfragen) {
        const unter = sichtbareAnfragenUnterbereiche({ istAdmin })
        if (unter.length) {
            anfragen.unterpunkte = unter.map(u => ({
                id: 'anfragen-' + u.id,
                label: u.label,
                href: `#/personen/anfragen?bereich=${u.id}`,
                value: unterbereichsWert(u.seite, u.id),
                seite: u.seite,
                bereich: u.id,
                rolle: u.rolle,
                zahl: null,
            }))
        }
    }
    return eintraege
}

/** Sichtbare Unterbereiche von „Anfragen“ (ohne Recht: keine). */
export function sichtbareAnfragenUnterbereiche({ istAdmin = false } = {}) {
    return ANFRAGEN_UNTERBEREICHE.filter(u => u.rolle !== 'admin' || istAdmin)
}

/**
 * Gewählter Eintrag der Bereichsliste aus der Adresse (Hash).
 * → { eintrag, unterbereich } oder null, wenn die Adresse nicht zum
 * Mitglieder-Bereich gehört.
 *
 * Die Anfragen-Adresse ohne Abfrageteil (oder mit `bereich=anfragen`) ist der
 * Hauptpunkt selbst — dann ist `unterbereich` null und der Hauptpunkt trägt
 * die Markierung. Ein unbekannter `bereich`-Wert fällt ebenfalls darauf
 * zurück, damit alte Lesezeichen gültig bleiben.
 */
export function bereichsEintragAusHash(hash, { istAdmin = false, anfragenZahl = null } = {}) {
    const eintraege = mitgliederBereichEintraege({ istAdmin, anfragenZahl })
    const roh = typeof hash === 'string' ? hash : ''
    const [pfad, abfrage] = roh.split('?')
    const eintrag = (eintraege.find(e =>
        (e.unterpunkte || []).some(u => u.href.split('?')[0] === pfad))
        || eintraege.find(e => e.href === pfad))
    if (!eintrag) return null
    let unterbereich = null
    if (eintrag.unterpunkte) {
        const werte = new URLSearchParams(abfrage || '')
        unterbereich = eintrag.unterpunkte.find(u => u.bereich === werte.get('bereich')) || null
    }
    return { eintrag, unterbereich }
}

/** Symbolvorrat: Pfade im 24×24-Raster. */
export const ICON_PFADE = {
    home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
    users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
    'layout-grid': 'M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z',
    'book-open': 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
    calendar: 'M3 4h18v16H3z M16 2v4 M8 2v4 M3 10h18',
    clock: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 6v6l4 2',
    'user-plus': 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M12 7a4 4 0 1 1-4-4 M20 8v6 M23 11h-6',
    'git-branch': 'M6 3v12 M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 9a9 9 0 0 1-9 9',
    'bar-chart-2': 'M18 20V10 M12 20V4 M6 20v-6',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05 M12 22.08V12',
    folder: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
    'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
    'clipboard-list': 'M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2 M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2z M9 12l1 1 2-2 M9 16l1 1 2-2 M16 12l1 1 2-2 M16 16l1 1 2-2',
    'clipboard-check': 'M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2 M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z M9 14l2 2 4-4',
    'help-circle': 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01 M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z',
    music: 'M9 18V5l12-2v13 M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0z M21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
    moderation: 'M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z M14 17h6 M17 14v6',
    // WEB-3: Globus für „Website“.
    globe: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1.08 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
}

/**
 * Sichtbare Einträge einer Gruppe für den aktuellen Nutzer.
 * Das Ausblenden ist nur Komfort — der Server prüft jedes Recht erneut.
 *
 * `rollen` (WEB-3): der Eintrag erscheint, wenn EINE der genannten Rollen in
 * der Sitzung liegt. Die Rollenliste kommt aus dem Boot-Objekt
 * (`window.__DIakonosBOOT.roles`); ohne Angabe gilt sie als leer, also sieht
 * ein Nutzer ohne bekannte Rollen den Eintrag nicht (fail closed).
 */
export function sichtbareEintraege(gruppe, { istAdmin = false, istTester = false, istGast = false, rollen = [] } = {}) {
    const meineRollen = new Set(
        (Array.isArray(rollen) ? rollen : []).map(r => String(r || '').trim()),
    )
    return (gruppe.eintraege || []).filter(eintrag => {
        if (eintrag.rolle === 'admin' && !istAdmin) return false
        if (Array.isArray(eintrag.rollen) && eintrag.rollen.length
            && !eintrag.rollen.some(r => meineRollen.has(r))) return false
        if (eintrag.tester && !(istAdmin && istTester)) return false
        if (istGast) {
            // Gäste sehen nur Start, Kalender und Profil (wie bisher, N5).
            // UX3a2: „Dienste“ wieder entfernt — UX3a hatte den Punkt für
            // Gäste geöffnet, die Seite ist aber (wie vor UX3a) nicht für sie
            // gedacht; der Router sperrt sie ebenso.
            return eintrag.seiten.some(s => GAST_SEITEN.includes(s))
        }
        return true
    })
}

/** Menü-Einträge, deren Seiten ein Gast öffnen darf (N5, Entwurf A8). */
export const GAST_SEITEN = ['Home', 'Kalender']

/** Sichtbare Reiter des Mitglieder-Bereichs (ohne Rechte = nur Liste). */
export function sichtbareMitgliederReiter({ istAdmin = false } = {}) {
    return MITGLIEDER_REITER.filter(r => r.rolle !== 'admin' || istAdmin)
}

/** Sichtbare Reiter einer Bereichsliste (dieselbe Rollenregel wie das Menü).
 *
 *  `darfPlanen` (UX3c) ist das Planungsrecht des Servers
 *  (`plantypen_liste`/`einrichten_rechte` konnten gelesen werden = der Aufrufende
 *  ist Admin, Bereichs- oder Gruppenverantwortlicher). Reiter mit
 *  `rolle: 'planer'` erscheinen nur dann — ein reiner Admin ohne Planungsrecht
 *  sieht keinen leeren Reiter „Dienstpläne“, ein Planer ohne Admin sieht ihn
 *  (vorher war er für Nicht-Admins gesperrt). Fehlt der Wert (`undefined`),
 *  gilt die Administration: die Rechte werden geladen, der Reiter bleibt
 *  stehen (kein Aufblitzen beim ersten Anzeigen).
 */
export function sichtbareReiter(reiter, { istAdmin = false, darfPlanen } = {}) {
    const planen = typeof darfPlanen === 'boolean' ? darfPlanen : istAdmin
    return (reiter || []).filter(r => {
        if (r.rolle === 'admin') return istAdmin
        if (r.rolle === 'planer') return istAdmin || planen
        return true
    })
}

/**
 * Seitenname einer Bereichs-Adresse (`#/dienste/vorlagen` → `DiensteVorlagen`).
 * Der Abfrageteil (`?bereich=…`) und ein Schluss-Schrägstrich werden ignoriert.
 * UX3c: Auch UNTERADRESSEN markieren ihren Reiter (`#/dienste/vorlagen/chorplan`
 * → `DiensteVorlagen`, `#/dienste/dienstplaene/plan/abc` → `DiensteDienstplaene`),
 * sonst stünde beim Bearbeiten einer Vorlage kein Reiter als „aktiv“.
 * → null, wenn die Adresse nicht zum Bereich gehört.
 */
export function reiterAusHash(reiter, hash) {
    const roh = String(hash || '').split('?')[0].replace(/\/+$/, '')
    const treffer = (reiter || []).find(r => r.href === roh)
    if (treffer) return treffer.seite
    // Unteradresse: längster passender Reiter gewinnt, damit
    // `#/dienste/meine-dienste/…` nicht den Reiter „Dienstpläne“ erbt.
    const unter = (reiter || [])
        .filter(r => roh.startsWith(`${r.href}/`))
        .sort((a, b) => b.href.length - a.href.length)[0]
    return unter ? unter.seite : null
}

/** Menüeintrag zu einem Seitennamen finden (für die Kopfleiste).
 *  Durchsucht die Gruppen UND den Fußbereich („Einstellungen“). */
export function eintragZuSeite(seitenName) {
    for (const gruppe of MENUE) {
        for (const eintrag of gruppe.eintraege) {
            if (eintrag.seiten.includes(seitenName)) return { gruppe: gruppe.gruppe, eintrag }
        }
    }
    for (const eintrag of FUSS_EINTRAEGE) {
        if (eintrag.seiten.includes(seitenName)) return { gruppe: '', eintrag }
    }
    return null
}

/** Brotkrumen zu einer Seite aus der Menüdefinition (S12). */
export function krumenZuSeite(seitenName) {
    const treffer = eintragZuSeite(seitenName)
    if (!treffer) return [seitenName]
    return [treffer.eintrag.label]
}

/**
 * Reiter des Bereichs „Dienste“ (UX3a, Entwurf A2 … UX3b/3c/3d bauen die
 * Inhalte). Die Reiter heißen genau wie im Entwurf:
 *   „Meine Dienste“ · „Dienstpläne“ · „Vorlagen“
 * Jeder Reiter hat eine EIGENE Adresse (Entscheidung 4: jeder Bereichsteil ist
 * teilbar). Der Einstieg `#/dienste` öffnet „Meine Dienste“.
 *
 * Nur Reiter, deren Inhalt es schon gibt — kein toter Knopf: „Meine Dienste“
 * ist die bisherige Seite `#/planrahmen/meine-dienste`, „Dienstpläne“ die
 * bisherige Planübersicht `#/planrahmen`, „Vorlagen“ die Einrichtung
 * (`#/planrahmen/einrichten`). Die Seitennamen `Dienste` /
 * `DiensteDienstplaene` / `DiensteVorlagen` gibt es nur, damit die
 * Seitenleiste den Bereich „Dienste“ markiert — dort entsteht kein zweiter
 * Eintrag. Unterbereiche (einzelner Plan, Vorlagen-Editor, Stammdaten)
 * markieren weiter „Dienstpläne“ über ihre Seitennamen.
 *
 * UX3c (Kartentext): Start ist „Meine Dienste“ — für ALLE Rollen.
 * „Dienstpläne“ ist Planungsarbeit und erscheint nur mit Planungsrecht
 * (`rolle: 'planer'`, Recht kommt vom Server). „Vorlagen“ bleibt
 * Verwaltungsarbeit (`rolle: 'admin'`).
 */
export const DIENSTE_REITER = [
    { id: 'meine-dienste', label: 'Meine Dienste', href: '#/dienste/meine-dienste', seite: 'PlanrahmenDienste', rolle: 'alle' },
    { id: 'dienstplaene', label: 'Dienstpläne', href: '#/dienste/dienstplaene', seite: 'DiensteDienstplaene', rolle: 'planer' },
    { id: 'vorlagen', label: 'Vorlagen', href: '#/dienste/vorlagen', seite: 'DiensteVorlagen', rolle: 'admin' },
]

/** Reiter des Bereiches „Lieder“ (UX3a): „Lieder“ und „Liedgruppen“.
 *  Liedgruppen war bis UX3a ein eigener Menüpunkt; jetzt ein Reiter. */
export const LIEDER_REITER = [
    { id: 'lieder', label: 'Lieder', href: '#/lieder', seite: 'Lieder', rolle: 'alle' },
    { id: 'liedgruppen', label: 'Liedgruppen', href: '#/lieder/gruppen', seite: 'Liedgruppen', rolle: 'alle' },
]

/** Reiter des Kalenders (UX3a, Entwurf A4): Monat · Woche · Liste · „Zu prüfen“.
 *  Die Reiter „Monat/Woche/Liste“ werden von KronosTopbar gezeichnet (eigener
 *  Umschalter); `seite` bleibt für beide „Kalender“. „Zu prüfen“ ist die
 *  frühere Moderationsseite und nur für Moderatoren sichtbar (Server prüft). */
export const KALENDER_PRUEF_REITER = {
    id: 'pruefen', label: 'Zu prüfen', seite: 'Pruefen', href: '#/kalender/pruefen',
}

/**
 * Reiter, die der Kalender dem aktuellen Nutzer ANZEIGT (UX3d).
 *
 * Entwurf A4 zeigt am Kopf des Kalenders EINE Leiste
 * **Monat · Woche · Liste · Zu prüfen (n)**. Der letzte Eintrag erscheint nur
 * für Moderatoren — Entscheidung Manuel (UX3d): „nur für Moderatoren
 * sichtbar“. Das Recht kommt aus dem Boot-Objekt (`can_moderate`, dieselbe
 * Quelle wie `get_session_info` im Server); ohne Angabe gilt `false`
 * (fail closed — lieber kein Reiter als einer, der „Zugriff verweigert“
 * anzeigt).
 *
 * Die Zahl offener Prüfungen (`offeneZahl`) ist eine Kennzahl, kein Wert:
 * fehlt sie oder ist sie keine Zahl, bleibt die Beschriftung ohne Zahl — nie
 * eine erfundene 0.
 *
 * @param {{can_moderate?: boolean, offeneZahl?: number|null}} optionen
 * @returns {Array<{id: string, label: string, href: string|null, seite: string,
 *                  zahl: number|null, aktiv: string}>}
 *          `aktiv` ist der Ansichtsname, den `KronosTopbar` als aktiv markiert
 *          (`dayGridMonth`/`timeGridWeek`/`listMonth`/`pruefen`).
 */
export function kalenderReiter({ can_moderate = false, offeneZahl = null } = {}) {
    const zahl = (offeneZahl === null || offeneZahl === undefined || offeneZahl === '')
        ? null
        : (Number.isFinite(Number(offeneZahl)) ? Number(offeneZahl) : null)
    const reiter = [
        // `ansicht: true` = Umschalter derselben Seite (Knopf im Bauteil),
        // ohne = eigene Seite (Link). Das Bauteil entscheidet NICHT anhand
        // von `href` — ein gesetzter `href` an einem Umschalter würde daraus
        // einen Seitenwechsel machen.
        { id: 'monat', label: 'Monat', href: '#/kalender', ansicht: true, seite: 'Kalender', zahl: null, aktiv: 'dayGridMonth' },
        { id: 'woche', label: 'Woche', href: null, ansicht: true, seite: 'Kalender', zahl: null, aktiv: 'timeGridWeek' },
        { id: 'liste', label: 'Liste', href: null, ansicht: true, seite: 'Kalender', zahl: null, aktiv: 'listMonth' },
    ]
    if (can_moderate === true) {
        reiter.push({
            id: KALENDER_PRUEF_REITER.id,
            label: KALENDER_PRUEF_REITER.label,
            href: KALENDER_PRUEF_REITER.href,
            ansicht: false,
            seite: KALENDER_PRUEF_REITER.seite,
            zahl: (zahl !== null && zahl > 0) ? zahl : null,
            aktiv: KALENDER_PRUEF_REITER.id,
        })
    }
    return reiter
}
