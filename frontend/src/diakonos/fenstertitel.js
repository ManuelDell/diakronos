/**
 * Fenstertitel (OP-UI-22, WCAG 2.4.2) — bewusst ohne eigene Abhängigkeiten.
 *
 * Vorher stand auf jeder Seite derselbe Titel („Meine Gemeinde"). Wer mehrere
 * Tabs offen hat oder mit einem Screenreader arbeitet, konnte Seiten nicht
 * unterscheiden. Der Titel lautet „‹Seite› – ‹Gemeinde›" und kommt aus
 * derselben Quelle wie die Navigation (menue.js) — Seiten ohne Menüeintrag
 * stehen in SEITENTITEL_NICHT_IM_MENUE.
 *
 * P3-4b/B1: Die Logik liegt in einem eigenen, importfreien Modul, weil die
 * Router-Tests `router.js` per vm ohne Importe ausführen. `menue.js` wird erst
 * beim Aufruf nachgeladen (dynamischer Import), damit dieses Modul ebenso
 * importfrei bleibt. Ein Fehler beim Titel darf den Seitenwechsel niemals
 * anhalten — deshalb try/catch in `setzeFenstertitel`.
 */

/** Seiten ohne Menüeintrag (dynamische Seiten, Sonderfälle). */
export const SEITENTITEL_NICHT_IM_MENUE = {
    Home: 'Übersicht',
    NichtGefunden: 'Seite nicht gefunden',
    Profile: 'Mein Profil',
    Registrierung: 'Registrierung',
    Anmeldung: 'Anmeldung',
    Beitraege: 'Beiträge',
    Wiki: 'Wiki',
    Lieder: 'Lieder',
    LiedNeu: 'Neues Lied',
    LiedDetail: 'Lied',
    Liedgruppen: 'Liedgruppen',
    LiedgruppeDetail: 'Liedgruppe',
    Adressbuch: 'Adressbuch',
    MitgliedDetail: 'Mitglied',
    GruppeDetail: 'Gruppe',
    KalenderImport: 'Kalender importieren',
    KalenderVerwaltung: 'Kalender verwalten',
    RessourcenVerwaltung: 'Ressourcen verwalten',
    Dienstplan: 'Dienstplan',
    Anmeldungen: 'Anmeldungen',
    Moderation: 'Moderation',
    PlanrahmenPlan: 'Plan',
    PlanrahmenDienste: 'Meine Dienste',
    PlanrahmenEinrichten: 'Pläne einrichten',
    PlanrahmenPlantypEditor: 'Planvorlage bearbeiten',
    PlanrahmenStammdaten: 'Plan vorbereiten',
    DevBefunde: 'Dev-Befunde',
}

/** Zwischenspeicher der Menüpunkte (menue.js wird nur einmal geladen). */
let menueQuelle = null

/**
 * Menüdefinition nachladen. `menue.js` ist ein reines Datenmodul; der
 * dynamische Import funktioniert im Browser (Vite-Bündel) genauso wie in den
 * Node-Tests, die `import(…)` durch ein festes Promise ersetzen.
 */
function ladeMenue() {
    if (!menueQuelle) {
        menueQuelle = import('./menue.js')
            .then(mod => (Array.isArray(mod?.MENUE) ? mod.MENUE : []))
            .catch(() => {
                menueQuelle = null
                return []
            })
    }
    return menueQuelle
}

/** Beschriftung einer Seite aus der Menüdefinition (erster Treffer). */
export function titelAusMenue(pageName, menue) {
    const gruppen = Array.isArray(menue) ? menue : []
    for (const gruppe of gruppen) {
        for (const eintrag of gruppe.eintraege || []) {
            if ((eintrag.seiten || []).includes(pageName)) return eintrag.label
        }
    }
    return null
}

/** Gemeindename für den Fenstertitel (fällt auf den bisherigen Text zurück). */
export function gemeindeName(win) {
    const w = win || (typeof window !== 'undefined' ? window : null)
    const boot = (w && w.__DIakonosBOOT) || {}
    return boot.church_name || 'Meine Gemeinde'
}

/** Fertiger Titel „‹Seite› – ‹Gemeinde›" (ohne Seitennamen nur die Gemeinde). */
export function baueTitel(pageName, menue, win) {
    const seite = titelAusMenue(pageName, menue) || SEITENTITEL_NICHT_IM_MENUE[pageName] || ''
    const gemeinde = gemeindeName(win)
    return seite ? `${seite} – ${gemeinde}` : gemeinde
}

function schreibeTitel(titel) {
    if (typeof document === 'undefined' || !document) return
    document.title = titel
}

/**
 * Fenstertitel setzen: „‹Seite› – ‹Gemeinde›".
 * Kennt das Menü die Seite noch nicht, wird zuerst der bekannte Titel gesetzt
 * und nach dem Nachladen der Menüzettel nachgezogen (nur wenn der Titel
 * inzwischen nicht schon von einer anderen Seite gesetzt wurde).
 */
export function setzeFenstertitel(pageName, win) {
    const w = win || (typeof window !== 'undefined' ? window : null)
    let titel
    try {
        titel = baueTitel(pageName, null, w)
        schreibeTitel(titel)
    } catch (err) {
        console.warn('Fenstertitel konnte nicht gesetzt werden:', err)
        return
    }
    // Menüzettel nachziehen (dynamischer Import) — nie den Wechsel aufhalten.
    try {
        ladeMenue().then(menue => {
            if (!menue.length) return
            const mitMenue = baueTitel(pageName, menue, w)
            if (mitMenue !== titel) schreibeTitel(mitMenue)
        }).catch(() => {})
    } catch (err) {
        console.warn('Fenstertitel aus dem Menü nicht verfügbar:', err)
    }
}
