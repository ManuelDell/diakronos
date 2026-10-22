import { ref, computed, shallowRef } from 'vue'
import { setzeFenstertitel } from './fenstertitel.js'

// Lazy-loaded page components
// N13: das Organigramm ist keine eigene Seite mehr, sondern die zweite
// Ansicht von „Gruppen“ (#/gruppen/organigramm). Die alte Adresse
// #/organigramm leitet in der Weiterleitungstabelle weiter.
const pages = {
    Home:            () => import('./pages/Home.vue'),
    Mitglieder:      () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederUebersicht:  () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederListe:       () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederAnfragen:    () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederDatenschutz: () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederImport:      () => import('./pages/mitglieder/Bereich.vue'),
    MitgliederLoeschantraege: () => import('./pages/mitglieder/Bereich.vue'),
    MitgliedDetail:  () => import('./pages/MitgliedDetail.vue'),
    GruppeDetail:    () => import('./pages/GruppeDetail.vue'),
    GruppenBereich:  () => import('./pages/gruppen/Bereich.vue'),
    Adressbuch:      () => import('./pages/Adressbuch.vue'),
    Kalender:        () => import('./pages/Kalender.vue'),
    KalenderImport:  () => import('./pages/KalenderImport.vue'),
    KalenderVerwaltung: () => import('./pages/KalenderVerwaltung.vue'),
    RessourcenVerwaltung: () => import('./pages/RessourcenVerwaltung.vue'),
    Dienstplan:      () => import('./pages/Dienstplan.vue'),
    Einstellungen:   () => import('./pages/Einstellungen.vue'),
    EinstellungenGemeinde: () => import('./pages/Einstellungen.vue'),
    EinstellungenAnmeldung: () => import('./pages/Einstellungen.vue'),
    EinstellungenRollen:    () => import('./pages/Einstellungen.vue'),
    EinstellungenDevModus:  () => import('./pages/Einstellungen.vue'),
    EinstellungenRegistrierung: () => import('./pages/Einstellungen.vue'),
    EinstellungenDatenschutz: () => import('./pages/Einstellungen.vue'),
    EinstellungenDatensicherung: () => import('./pages/Einstellungen.vue'),
    EinstellungenMailversand: () => import('./pages/Einstellungen.vue'),
    Profile:         () => import('./pages/Profile.vue'),
    Ressourcen:      () => import('./pages/Ressourcen.vue'),
    Beitraege:       () => import('./pages/Beitraege.vue'),
    Wiki:            () => import('./pages/Wiki.vue'),
    Registrierung:   () => import('./pages/Registrierung.vue'),
    Moderation:       () => import('./pages/Moderation.vue'),
    Lieder:           () => import('./pages/Lieder.vue'),
    LiedNeu:          () => import('./pages/LiedNeu.vue'),
    LiedDetail:       () => import('./pages/LiedDetail.vue'),
    Liedgruppen:      () => import('./pages/Liedgruppen.vue'),
    LiedgruppeDetail: () => import('./pages/LiedgruppeDetail.vue'),
    PlanrahmenUebersicht: () => import('./pages/planrahmen/Uebersicht.vue'),
    PlanrahmenPlan:       () => import('./pages/planrahmen/Plan.vue'),
    PlanrahmenDienste:    () => import('./pages/planrahmen/MeineDienste.vue'),
    PlanrahmenEinrichten: () => import('./pages/planrahmen/Einrichten.vue'),
    PlanrahmenPlantypEditor: () => import('./pages/planrahmen/PlantypEditor.vue'),
    PlanrahmenStammdaten: () => import('./pages/planrahmen/Stammdaten.vue'),
    // DM1: Dev-Befunde (ersetzt die Testsuite).
    DevBefunde:           () => import('./pages/devmodus/Befunde.vue'),
    // N1 (OP-UI-6): unbekannte Adresse → verständliche Seite statt still Dashboard.
    NichtGefunden:        () => import('./pages/NichtGefunden.vue'),
}

// Exact routes
const routeMap = {
    '#/':              'Home',
    '#/mitglieder':    'Mitglieder',
    // Entscheidung 4: jeder Mitglieder-Reiter hat eine eigene Adresse.
    '#/mitglieder/uebersicht': 'MitgliederUebersicht',
    '#/mitglieder/liste':      'MitgliederListe',
    '#/mitglieder/anfragen':   'MitgliederAnfragen',
    '#/mitglieder/datenschutz':'MitgliederDatenschutz',
    '#/mitglieder/import':     'MitgliederImport',
    // DSGVO-2c: eigene Seite der Verwaltung für Löschanträge.
    '#/mitglieder/loeschantraege': 'MitgliederLoeschantraege',
    '#/gruppen':      'GruppenBereich',
    // N13: das Organigramm ist die zweite Ansicht der Gruppenseite
    // (Umschalter Liste/Organigramm), keine eigene Seite mehr.
    '#/gruppen/organigramm': 'GruppenBereich',
    '#/adressbuch':    'Adressbuch',
    '#/kalender':      'Kalender',
    '#/kalender/import': 'KalenderImport',
    '#/kalender/verwalten': 'KalenderVerwaltung',
    '#/ressourcen/verwalten': 'RessourcenVerwaltung',
    '#/dienstplan':    'Dienstplan',
    '#/anmeldungen':   'Registrierung',
    '#/registrierung': 'Registrierung',
    '#/moderation':    'Moderation',
    '#/einstellungen': 'Einstellungen',
    // Entscheidung „N9": jeder Einstellungs-Abschnitt hat eine eigene Adresse.
    '#/einstellungen/gemeinde':      'EinstellungenGemeinde',
    '#/einstellungen/anmeldung': 'EinstellungenAnmeldung',
    // N10: Rollen & Rechte und Dev-Modus.
    '#/einstellungen/rollen':        'EinstellungenRollen',
    '#/einstellungen/dev-modus':     'EinstellungenDevModus',
    '#/einstellungen/registrierung': 'EinstellungenRegistrierung',
    '#/einstellungen/datenschutz':   'EinstellungenDatenschutz',
    // BACKUP-1: eigene Datensicherung (nur System Manager — Server prueft).
    '#/einstellungen/datensicherung': 'EinstellungenDatensicherung',
    // MAIL-1: eigenes Postfach fuer den Mailversand (nur System Manager — Server prueft).
    '#/einstellungen/mailversand': 'EinstellungenMailversand',
    '#/profile':       'Profile',
    '#/ressourcen':    'Ressourcen',
    '#/beitraege':     'Beitraege',
    '#/wiki':          'Wiki',
    '#/lieder':        'Lieder',
    '#/lieder/neu':    'LiedNeu',
    '#/liedgruppen':   'Liedgruppen',
    '#/planrahmen': 'PlanrahmenUebersicht',
    '#/planrahmen/meine-dienste': 'PlanrahmenDienste',
    '#/planrahmen/einrichten': 'PlanrahmenEinrichten',
    '#/dev-befunde': 'DevBefunde',
}

// Dynamic routes: pattern regex → page name
const dynamicRoutes = [
    { pattern: /^#\/mitglied\/(.+)$/, page: 'MitgliedDetail', param: 'id' },
    // UXD-R20: Wiki-Artikel sind teilbar („#/wiki/‹Kennung›“ öffnet den Artikel).
    { pattern: /^#\/wiki\/(.+)$/, page: 'Wiki', param: 'id' },
    { pattern: /^#\/gruppe\/(.+)$/, page: 'GruppeDetail', param: 'id' },
    { pattern: /^#\/lieder\/(.+)$/, page: 'LiedDetail', param: 'id' },
    { pattern: /^#\/liedgruppen\/(.+)$/, page: 'LiedgruppeDetail', param: 'id' },
    { pattern: /^#\/planrahmen\/einrichten\/(.+)$/, page: 'PlanrahmenPlantypEditor', param: 'id' },
    { pattern: /^#\/planrahmen\/stammdaten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plantyp' },
    { pattern: /^#\/planrahmen\/vorbereiten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plan' },
    { pattern: /^#\/planrahmen\/plan\/(.+)$/, page: 'PlanrahmenPlan', param: 'id' },
]

// ── Weiterleitungen alter Adressen ─────────────────────────────────────────
// Konzept „Neuordnung“ Abschnitt 8: gespeicherte Lesezeichen und geteilte
// Links bleiben gültig. Rechte werden serverseitig geprüft; wer nicht darf,
// landet über den Guard auf dem Dashboard.
const WEITERLEITUNGEN = {
    '#/plaene':       '#/planrahmen',
    '#/registrierung':'#/mitglieder/anfragen',
    '#/anmeldungen':  '#/mitglieder/anfragen',
    '#/statistik':    '#/mitglieder/uebersicht',
    '#/anmeldung':    '#/einstellungen/anmeldung',
    // Entscheidung 9: Organigramm wird eine Ansicht in „Gruppen“.
    '#/organigramm':  '#/gruppen/organigramm',
}

// ── Fenstertitel (OP-UI-22, WCAG 2.4.2) ─────────────────────────────────────
// Ausgelagert nach fenstertitel.js (P3-4b/B1): Dieses Modul ist importfrei und
// damit in den Router-Tests (vm ohne Importe) lauffähig; ein Fehler im Titel
// darf den Seitenwechsel nie anhalten (try/catch dort).

/** Pfad und Abfrageteil einer Adresse trennen ("#/x?a=1" → ["#/x", "?a=1"]). */
function zerlegeHash(hash) {
    const frage = hash.indexOf('?')
    if (frage === -1) return [hash, '']
    return [hash.slice(0, frage), hash.slice(frage)]
}

/** Endet der Pfad auf "/" (aber nicht die Wurzel)? → für die Weiterleitung entfernen. */
function ohneSchlussslash(pfad) {
    return pfad.length > 2 && pfad.endsWith('/') ? pfad.replace(/\/+$/, '') : pfad
}

// Rollenabhängige Weiterleitungen (nur wenn das Ziel für die Rolle passt).
function rollenWeiterleitung(pfad) {
    const boot = window.__DIakonosBOOT || {}
    const isAdmin = boot.is_admin || false
    if (pfad === '#/dsgvo') {
        // Abschnitt 8: Admin → Datenschutz-Reiter, alle anderen → Profil.
        return isAdmin ? '#/mitglieder/datenschutz' : '#/profile'
    }
    if (pfad === '#/mitglieder') {
        // Admins öffnen die Übersicht, alle anderen die Liste.
        return isAdmin ? '#/mitglieder/uebersicht' : '#/mitglieder/liste'
    }
    return null
}

/**
 * Ziel einer Weiterleitung (ohne Abfrageteil), oder null.
 * Ein Schluss-Schrägstrich wird ignoriert, damit "#/registrierung/" ebenso
 * greift wie "#/registrierung" (Befund R-N0-code 3).
 */
function weiterleitungsZiel(pfad) {
    return WEITERLEITUNGEN[pfad] || rollenWeiterleitung(pfad) || null
}

// Scope und Parameter müssen auch für synchrone Watcher zusammen wechseln.
const acceptedRoute = ref({ hash: window.location.hash || '#/', pageName: 'Home', params: {} })
const currentHash = computed(() => acceptedRoute.value.hash)
const currentPageName = computed(() => acceptedRoute.value.pageName)
const currentComponent = shallowRef(null)

// Route guards (simple)
const beforeEachGuards = []

export function onBeforeEach(fn) {
    beforeEachGuards.push(fn)
    return () => {
        const index = beforeEachGuards.indexOf(fn)
        if (index >= 0) beforeEachGuards.splice(index, 1)
    }
}

let navigationsNummer = 0
async function resolveRoute() {
    const nummer = ++navigationsNummer
    const vollerHash = window.location.hash || '#/'

    // Alte Adressen bleiben benutzbar (Konzept Abschnitt 8, Entscheidung 9).
    // Der Abfrageteil ("?status=Mitglied", "?q=…") gehoert NICHT zur Route:
    // ohne diese Trennung findet `routeMap['#/lieder?q=Komm']` nichts, die
    // Seite faellt still auf 'Home' zurueck und die Suche aus der Adresse geht
    // verloren (OP-HANDY-13). Er wird ans Weiterleitungsziel weitergereicht;
    // ein Schluss-Schraegstrich im Pfad wird ignoriert (Befund R-N0-code 3).
    // Der volle Hash (mit Abfrage) bleibt in `acceptedRoute`, damit Seiten ihn
    // lesen koennen (Lieder.vue nutzt `window.location.hash`).
    const [rohpfad, abfrage] = zerlegeHash(vollerHash)
    const pfad = ohneSchlussslash(rohpfad)
    const ziel = weiterleitungsZiel(pfad)
    if (ziel) {
        const zielMitAbfrage = ziel + abfrage
        if (zielMitAbfrage !== vollerHash) {
            window.location.replace(zielMitAbfrage)
            return
        }
    }
    // N13: das Organigramm ist seit der Neuordnung die Ansicht „Organigramm“
    // der Seite Gruppen. Alte Lesezeichen und Links landen dort.
    //
    // Extract params from dynamic routes.
    // H1 (N1b): nachgeschlagen wird der PFAD ohne Abfrageteil und ohne
    // Schluss-Schrägstrich — vorher ging "#/mitglieder/liste?status=Mitglied"
    // (Kachel der Übersicht, Weiterleitungen mit Abfrage) ungefunden aus und
    // landete auf „Seite nicht gefunden“.
    let pageName = routeMap[pfad]
    let params = {}
    if (!pageName) {
        for (const r of dynamicRoutes) {
            const m = pfad.match(r.pattern)
            if (m) {
                pageName = r.page
                params[r.param] = decodeURIComponent(m[1])
                break
            }
        }
    }
    // Unbekannte Adresse → „Seite nicht gefunden“ (OP-UI-6), nicht still zum
    // Dashboard. Die Wurzel bleibt die Startseite.
    pageName = pageName || (pfad === '#/' ? 'Home' : 'NichtGefunden')

    // Run guards
    for (const guard of beforeEachGuards) {
        let result = guard({ to: vollerHash, name: pageName, params })
        // App-Rückfragen liefern Promises. Bis zur Antwort bleibt die alte
        // Seite gemountet; eine verspätete Antwort darf nie eine neuere Route ersetzen.
        if (result && typeof result.then === 'function') {
            try { result = await result } catch (err) {
                console.error('Routenwechsel konnte nicht bestätigt werden:', err)
                result = false
            }
        }
        if (nummer !== navigationsNummer) return
        if (result === false) {
            // P1-11b: Ein abgebrochener Routenwechsel darf einen alten
            // Ladefehler nicht stehen lassen — sonst bliebe nach dem
            // Dashboard-Wechsel die Fehlermeldung der Vorgängerseite sichtbar.
            pageLadefehler.value = null
            if (window.location.hash === vollerHash) window.history.replaceState(null, '', currentHash.value)
            return
        }
        if (typeof result === 'string') {
            navigate(result)
            return
        }
    }

    acceptedRoute.value = { hash: vollerHash, pageName, params }
    const route = acceptedRoute.value
    // OP-UI-22: Fenstertitel sofort mit dem Wechsel setzen (nicht erst, wenn
    // das Nachladen fertig ist — sonst trägt der Tab während des Ladens noch
    // den Titel der Vorgängerseite).
    setzeFenstertitel(pageName)
    const loader = pages[pageName] || pages.Home
    // OP-HANDY-24: Bei langsamem Netz stand die alte Seite still da, ohne dass
    // erkennbar war, dass schon gewechselt wird. `seitenLadend` blendet den
    // Fortschrittsbalken ein (App.vue); gesetzt wird er VOR dem Nachladen.
    seitenLadend.value = true
    loader().then(mod => {
        if (acceptedRoute.value === route) {
            pageLadefehler.value = null
            currentComponent.value = mod.default
        }
    }).catch((err) => {
        // Ein fehlgeschlagener Nachlade-Versuch (Chunk 404, Netzfehler) darf
        // NICHT als ewiger Spinner enden. Vorher blieb `currentComponent`
        // null, die App zeigte „Wird geladen…" fuer immer und der Nutzer kam
        // nie zum Ende (Dev-Befund 16.10.: #/planrahmen/meine-dienste).
        if (acceptedRoute.value !== route) return
        currentComponent.value = null
        pageLadefehler.value = {
            hash: vollerHash, pageName,
            meldung: 'Die Seite konnte nicht geladen werden.',
            hinweis: 'Bitte die Seite neu laden. Bleibt der Fehler, den Browser-Zwischenspeicher leeren.',
            grund: String(err?.message || err || 'Unbekannter Fehler'),
        }
    }).finally(() => {
        // OP-HANDY-24: Balken nur beenden, wenn seither kein neuerer Wechsel
        // läuft — sonst würde ein altes, spätes Nachladen den Balken der
        // neuen Seite abschalten.
        if (acceptedRoute.value === route) seitenLadend.value = false
    })
}

/**
 * Läuft gerade ein Seitenwechsel (Nachladen des Seitenbündels)?
 * App.vue zeigt bei true einen schmalen Fortschrittsbalken unter der
 * Kopfleiste (OP-HANDY-24: bei langsamem Netz fehlte jede Rückmeldung).
 */
export const seitenLadend = ref(false)

/**
 * Zustand eines fehlgeschlagenen Nachladens der Seite (null = kein Fehler).
 * Die App zeigt statt des ewigen Spinners eine verstaendliche Meldung.
 */
export const pageLadefehler = ref(null)

/** Erneuter Versuch: Adresse unveraendert neu aufloesen (z. B. nach Netzfehler). */
export function routeNeuLaden() {
    pageLadefehler.value = null
    resolveRoute()
}
export function navigate(path) {
    if (typeof path !== 'string') {
        console.warn('[router] navigate expected string, got', typeof path, path)
        path = String(path || '')
    }
    if (!path.startsWith('#')) path = '#' + path
    window.location.hash = path
}

// Lazy-Seiten bleiben während des Routenwechsels noch gemountet. Mit einem
// Seitenscope dürfen ihre Watcher keine Parameter der nächsten Seite laden.
export function getRouteParam(key, pageName) {
    const route = acceptedRoute.value
    if (pageName && route.pageName !== pageName) return undefined
    return route.params[key]
}

export function getRouteParams() {
    return { ...acceptedRoute.value.params }
}

// ── Gast-Guard ──────────────────────────────────────────────────────────────
// Routen, die ein Gast (Status = 'Gast') aufrufen darf
const GAST_ALLOWED_ROUTES = new Set(['#/', '#/kalender', '#/profile'])
const GAST_ALLOWED_PAGES  = new Set(['Home', 'Kalender', 'Profile'])

onBeforeEach(({ to, name }) => {
    const boot = window.__DIakonosBOOT || {}
    const mitglied = boot.mitglied || null
    const isAdmin  = boot.is_admin  || false
    if (isAdmin) return            // Admins dürfen alles
    if (!mitglied) return          // Kein Mitglied-Datensatz → kein Guard
    if (mitglied.status !== 'Gast') return   // Vollmitglieder dürfen alles
    if (GAST_ALLOWED_PAGES.has(name)) return // Erlaubte Seite
    // Gesperrte Route → zurück zum Dashboard
    navigate('#/')
    return false
})

// ── Admin-Guard für Verwaltungs-Seiten ──────────────────────────────────────
// Ausblenden im Menü ist nur Komfort; direkte Aufrufe von Verwaltungsseiten
// landen ohne Recht auf dem Dashboard (der Server verweigert ohnehin).
const ADMIN_ONLY_PAGES = new Set([
    'MitgliederUebersicht', 'MitgliederAnfragen', 'MitgliederDatenschutz', 'MitgliederImport',
    // DSGVO-2c: eigene Seite der Verwaltung (der Server verweigert sonst 403).
    'MitgliederLoeschantraege',
    'Einstellungen', 'EinstellungenGemeinde', 'EinstellungenAnmeldung',
    'EinstellungenRollen', 'EinstellungenDevModus',
    'EinstellungenRegistrierung', 'EinstellungenDatenschutz',
    // BACKUP-1: die Datensicherung ist serverseitig nur fuer System Manager;
    // der Guard haelt alle anderen schon auf der Seite auf.
    'EinstellungenDatensicherung',
    // MAIL-1: Mailversand ebenso — der Server prueft zusaetzlich (403).
    'EinstellungenMailversand',
    'Registrierung',
])
onBeforeEach(({ name }) => {
    if (!ADMIN_ONLY_PAGES.has(name)) return
    const boot = window.__DIakonosBOOT || {}
    if (boot.is_admin) return
    navigate('#/')
    return false
})

onBeforeEach(({ name }) => {
    if (name !== 'DevBefunde') return
    const boot = window.__DIakonosBOOT || {}
    if (boot.devmode && (boot.is_admin || boot.ist_tester)) return
    navigate('#/')
    return false
})

// Listen to hash changes
window.addEventListener('hashchange', resolveRoute)

// Initial resolve
resolveRoute()

export { currentHash, currentPageName, currentComponent }
