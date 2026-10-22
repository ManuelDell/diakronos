/**
 * Zentrale Menüdefinition (Standard S12).
 *
 * EINE Quelle für Seitenleiste (Desktop), „Mehr“-Blatt (Handy) und
 * Kopfleiste. Wer einen Menüpunkt ändert, ändert ihn hier — nirgends sonst.
 *
 * Felder eines Eintrags:
 *   id       stabile Kennung (für Tests und Markierung)
 *   label    sichtbare Beschriftung
 *   href     Zieladresse (#/…)
 *   icon     Name aus dem Symbolvorrat (siehe ICON_PFADE)
 *   seiten   Seitennamen, bei denen der Eintrag als „aktiv“ gilt
 *   rolle    'alle' | 'admin'  — nur Komfort: der Server prüft weiter
 *   tester   true = nur mit Tester-Rolle sichtbar (Dev-Befunde)
 *   badge    optionale Kennzahl-Quelle (siehe AppSidebar)
 *
 * Gruppen folgen der Aufgabenordnung aus dem Neuordnungs-Konzept
 * Abschnitt 2 („Nachher“).
 */

/**
 * Gruppen folgen der Aufgabenordnung aus dem Neuordnungs-Konzept
 * Abschnitt 2 („Nachher“) und werden für OP-UI-11 nach Aufgaben geschnitten:
 * Gemeinde · Termine & Dienste · Infos · Musik · Verwaltung. Kopfleiste
 * (AppTopbar) und Brotkrumen lesen dieselbe Definition.
 */
export const MENUE = [
    {
        gruppe: 'Gemeinde',
        eintraege: [
            { id: 'dashboard', label: 'Übersicht', href: '#/', icon: 'home', seiten: ['Home'] },
            {
                id: 'mitglieder', label: 'Mitglieder', href: '#/mitglieder', icon: 'users',
                seiten: ['Mitglieder', 'MitgliederUebersicht', 'MitgliederListe', 'MitgliederAnfragen', 'MitgliederDatenschutz', 'MitgliederLoeschantraege', 'MitgliedDetail'],
                rolle: 'alle', badge: 'anfragen',
            },
            { id: 'adressbuch', label: 'Adressbuch', href: '#/adressbuch', icon: 'book-open', seiten: ['Adressbuch'] },
            {
                id: 'gruppen', label: 'Gruppen', href: '#/gruppen', icon: 'layout-grid',
                seiten: ['GruppenBereich', 'GruppeDetail'],
            },
            // DES-R9: Der Datenschutz-Reiter hing nur unter „Mitglieder“ und war
            // am Handy gar nicht erreichbar. Er bekommt einen eigenen Eintrag
            // (nur Administration — der Server weist alle anderen ohnehin ab).
            {
                id: 'datenschutz', label: 'Datenschutz', href: '#/mitglieder/datenschutz',
                icon: 'shield', seiten: ['MitgliederDatenschutz'], rolle: 'admin',
            },
        ],
    },
    {
        gruppe: 'Termine & Dienste',
        eintraege: [
            { id: 'kalender', label: 'Kalender', href: '#/kalender', icon: 'calendar', seiten: ['Kalender', 'KalenderImport', 'KalenderVerwaltung'] },
            { id: 'dienstplan', label: 'Dienstplan', href: '#/dienstplan', icon: 'clock', seiten: ['Dienstplan'] },
            {
                id: 'plaene', label: 'Pläne', href: '#/planrahmen', icon: 'clipboard-list',
                seiten: ['PlanrahmenUebersicht', 'PlanrahmenPlan', 'PlanrahmenEinrichten', 'PlanrahmenPlantypEditor', 'PlanrahmenStammdaten'],
            },
            { id: 'meine-dienste', label: 'Meine Dienste', href: '#/planrahmen/meine-dienste', icon: 'user-plus', seiten: ['PlanrahmenDienste'] },
            { id: 'ressourcen', label: 'Ressourcen', href: '#/ressourcen', icon: 'box', seiten: ['Ressourcen', 'RessourcenVerwaltung'] },
            { id: 'moderation', label: 'Moderation', href: '#/moderation', icon: 'moderation', seiten: ['Moderation'], rolle: 'admin' },
        ],
    },
    {
        gruppe: 'Infos',
        eintraege: [
            { id: 'beitraege', label: 'Beiträge', href: '#/beitraege', icon: 'file-text', seiten: ['Beitraege'] },
            { id: 'wiki', label: 'Wiki', href: '#/wiki', icon: 'help-circle', seiten: ['Wiki'] },
        ],
    },
    {
        gruppe: 'Musik',
        eintraege: [
            { id: 'lieder', label: 'Lieder', href: '#/lieder', icon: 'music', seiten: ['Lieder', 'LiedDetail', 'LiedNeu'] },
            { id: 'liedgruppen', label: 'Liedgruppen', href: '#/liedgruppen', icon: 'folder', seiten: ['Liedgruppen', 'LiedgruppeDetail'] },
        ],
    },
    {
        gruppe: 'Verwaltung',
        eintraege: [
            { id: 'einstellungen', label: 'Einstellungen', href: '#/einstellungen', icon: 'settings', seiten: ['Einstellungen', 'EinstellungenGemeinde', 'EinstellungenAnmeldung', 'EinstellungenRollen', 'EinstellungenRegistrierung', 'EinstellungenDatenschutz', 'EinstellungenDatensicherung', 'EinstellungenMailversand', 'EinstellungenDevModus'], rolle: 'admin' },
            { id: 'dev-befunde', label: 'Dev-Befunde', href: '#/dev-befunde', icon: 'clipboard-check', seiten: ['DevBefunde'], rolle: 'admin', tester: true },
        ],
    },
]

/** Reiterleiste des Mitglieder-Bereichs (Entscheidung 4: jede Adresse eigen).
 *  Nur Reiter, deren Inhalt es schon gibt — kein toter Knopf. */
export const MITGLIEDER_REITER = [
    { id: 'uebersicht', label: 'Übersicht', href: '#/mitglieder/uebersicht', seite: 'MitgliederUebersicht', rolle: 'admin' },
    { id: 'liste', label: 'Liste', href: '#/mitglieder/liste', seite: 'MitgliederListe', rolle: 'alle' },
    { id: 'anfragen', label: 'Anfragen', href: '#/mitglieder/anfragen', seite: 'MitgliederAnfragen', rolle: 'admin' },
    { id: 'datenschutz', label: 'Datenschutz', href: '#/mitglieder/datenschutz', seite: 'MitgliederDatenschutz', rolle: 'admin' },
    // DSGVO-2c: eigene Seite für die Arbeitsliste der Verwaltung (vor dem
    // Import, weil sie zu tun gibt — der Import ist Vorbereitung).
    { id: 'loeschantraege', label: 'Löschanträge', href: '#/mitglieder/loeschantraege', seite: 'MitgliederLoeschantraege', rolle: 'admin' },
    { id: 'import', label: 'Import', href: '#/mitglieder/import', seite: 'MitgliederImport', rolle: 'admin' },
]

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
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1.08 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
}

/**
 * Sichtbare Einträge einer Gruppe für den aktuellen Nutzer.
 * Das Ausblenden ist nur Komfort — der Server prüft jedes Recht erneut.
 */
export function sichtbareEintraege(gruppe, { istAdmin = false, istTester = false, istGast = false } = {}) {
    return (gruppe.eintraege || []).filter(eintrag => {
        if (eintrag.rolle === 'admin' && !istAdmin) return false
        if (eintrag.tester && !(istAdmin && istTester)) return false
        if (istGast) {
            // Gäste sehen nur Dashboard, Kalender und Profil (wie bisher).
            return eintrag.seiten.some(s => ['Home', 'Kalender'].includes(s))
        }
        return true
    })
}

/** Sichtbare Reiter des Mitglieder-Bereichs (ohne Rechte = nur Liste). */
export function sichtbareMitgliederReiter({ istAdmin = false } = {}) {
    return MITGLIEDER_REITER.filter(r => r.rolle !== 'admin' || istAdmin)
}

/** Menüeintrag zu einem Seitennamen finden (für die Kopfleiste). */
export function eintragZuSeite(seitenName) {
    for (const gruppe of MENUE) {
        for (const eintrag of gruppe.eintraege) {
            if (eintrag.seiten.includes(seitenName)) return { gruppe: gruppe.gruppe, eintrag }
        }
    }
    return null
}

/** Brotkrumen zu einer Seite aus der Menüdefinition (S12). */
export function krumenZuSeite(seitenName) {
    const treffer = eintragZuSeite(seitenName)
    if (!treffer) return [seitenName]
    return [treffer.eintrag.label]
}
