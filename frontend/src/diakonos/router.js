import { ref, computed, shallowRef } from 'vue'
import { setzeFenstertitel } from './fenstertitel.js'
// WEB-3: EINE Rollenregel für „Website“ (Menü und Guard teilen sie).
import { darfWebsite } from './composables/website.mjs'
// ON-3b: EINE Leitungsregel der Ersteinrichtung. Bewusst als NAMENSRAUM-Import
// (eine Zeile, ohne freie Namen daneben): die Router-Tests (vm) entfernen die
// Import-Zeilen und setzen feste Rückgaben ein — der Namesraum wird dort durch
// ein Objektliteral ersetzt. Aus demselben Grund stehen hier KEINE weiteren
// Kurzformen-Zeilen daneben (sie überlebten das Streichen).
import * as einrichtungLeitung from './einrichtungLeitung.mjs'
// UX2g: der Ladefehler einer Seite erscheint als Katalogtext statt als
// Floskel „Unbekannter Fehler".
import { fehlertext } from '../shared/fehlertexte.js'
// MT-7b (Review-Punkt 5): Der Rückweg-Merker der Listen gilt nur, solange der
// Nutzer aus der Liste kam. Der Wechsel wird HIER geprüft (eine Stelle), weil
// der Auslöser auch im Gerüst liegen kann (Menüpunkt in `AppSidebar.vue`) —
// ein Klick-Wächter in der Seite sähe ihn nie.
import { rueckwegBleibtGueltig, rueckwegMerken as rueckwegMerkenFuerRoute, rueckwegVergessen as rueckwegVergessenFuerRoute } from './composables/zurueckWege.mjs'

// Sicherheitsnetz: Läuft der Router ohne die Leitungsdatei (die VM-Tests
// streichen Importe), darf die Seite NICHT brechen — dann wird nicht
// geleitet und `#/einrichtung` bleibt erlaubt (der Server prüft erneut).
const leitung = typeof einrichtungLeitung === 'undefined'
    ? { EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen',
        einrichtungsWeiterleitung: () => null, einrichtungSeiteErlaubt: () => true,
        einrichtungGesehen: () => false }
    : einrichtungLeitung

// Lazy-loaded page components
// N13: das Organigramm ist keine eigene Seite mehr, sondern die zweite
// Ansicht von „Gruppen“ (#/gruppen/organigramm). Die alte Adresse
// #/organigramm leitet in der Weiterleitungstabelle weiter.
const pages = {
    Home:            () => import('./pages/Home.vue'),
    // UX3a: „Personen“ (vorher „Mitglieder“) — derselbe Bereichsrahmen.
    // UX3b: der Einstieg zeigt EINE Ansicht je Rolle (Mitgliederliste für
    // Administratoren, Adressbuch-Sicht für alle anderen) und führt die vier
    // Reiter Liste · Anfragen · Datenschutz · Import selbst.
    Personen:        () => import('./pages/Personen.vue'),
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
    // UX3a (Entwurf A4): vierter Kalender-Reiter „Zu prüfen“ = Moderationsseite.
    Pruefen:         () => import('./pages/Moderation.vue'),
    Moderation:      () => import('./pages/Moderation.vue'),
    RessourcenVerwaltung: () => import('./pages/RessourcenVerwaltung.vue'),
    // UX3a: der Bereich „Dienste“ besteht aus vorhandenen Seiten (kein neues
    // Bauteil): Meine Dienste, Dienstpläne (Planübersicht), Vorlagen
    // (Einrichtung). Der Rahmen setzt die Reiterleiste darüber.
    Dienste:             () => import('./pages/dienste/Bereich.vue'),
    DiensteDienstplaene: () => import('./pages/dienste/Bereich.vue'),
    DiensteVorlagen:     () => import('./pages/dienste/Bereich.vue'),
    Dienstplan:      () => import('./pages/Dienstplan.vue'),
    Einstellungen:   () => import('./pages/Einstellungen.vue'),
    EinstellungenGemeinde: () => import('./pages/Einstellungen.vue'),
    EinstellungenAnmeldung: () => import('./pages/Einstellungen.vue'),
    EinstellungenRollen:    () => import('./pages/Einstellungen.vue'),
    EinstellungenDevModus:  () => import('./pages/Einstellungen.vue'),
    EinstellungenRegistrierung: () => import('./pages/Einstellungen.vue'),
    EinstellungenDatenschutz: () => import('./pages/Einstellungen.vue'),
    EinstellungenDatensicherung: () => import('./pages/Einstellungen.vue'),
    EinstellungenPapierkorb: () => import('./pages/Einstellungen.vue'),
    EinstellungenMailversand: () => import('./pages/Einstellungen.vue'),
    // WEB-3: Einstellungs-Abschnitt „Website (Primo)“.
    EinstellungenWebsite: () => import('./pages/Einstellungen.vue'),
    // UX1k: Einstellungs-Abschnitt „Gestaltung“ (nur System Manager).
    EinstellungenGestaltung: () => import('./pages/Einstellungen.vue'),
    // WEB-3: eigene Seite „Website“ mit dem Einstieg in Primo.
    Website: () => import('./pages/Website.vue'),
    Profile:         () => import('./pages/Profile.vue'),
    Ressourcen:      () => import('./pages/Ressourcen.vue'),
    Beitraege:       () => import('./pages/Beitraege.vue'),
    // MT-7: EIN Beitrag als eigene Unterseite (`#/beitraege/<Kennung>`) —
    // Lesen im Fenster war der Befund (keine Adresse, kein Zurück, kein Drucken).
    BeitragDetail:   () => import('./pages/BeitragDetail.vue'),
    Wiki:            () => import('./pages/Wiki.vue'),
    // MT-7: EIN Wiki-Eintrag als eigene Unterseite (`#/wiki/<Kennung>`).
    WikiArtikel:     () => import('./pages/WikiArtikel.vue'),
    Registrierung:   () => import('./pages/Registrierung.vue'),
    Moderation:       () => import('./pages/Moderation.vue'),
    Lieder:           () => import('./pages/Lieder.vue'),
    LiedNeu:          () => import('./pages/LiedNeu.vue'),
    LiedDetail:       () => import('./pages/LiedDetail.vue'),
    Liedgruppen:      () => import('./pages/Liedgruppen.vue'),
    LiedgruppeDetail: () => import('./pages/LiedgruppeDetail.vue'),
    PlanrahmenUebersicht: () => import('./pages/planrahmen/Uebersicht.vue'),
    PlanrahmenPlan:       () => import('./pages/planrahmen/Plan.vue'),
    // UX3c: „Meine Dienste“ ist ein Reiter von „Dienste“ — der Rahmen
    // zeichnet die Reiterzeile und wählt die Seite nach `currentPageName`.
    PlanrahmenDienste:    () => import('./pages/dienste/Bereich.vue'),
    PlanrahmenEinrichten: () => import('./pages/planrahmen/Einrichten.vue'),
    PlanrahmenPlantypEditor: () => import('./pages/planrahmen/PlantypEditor.vue'),
    PlanrahmenStammdaten: () => import('./pages/planrahmen/Stammdaten.vue'),
    // DM1: Dev-Befunde (ersetzt die Testsuite).
    DevBefunde:           () => import('./pages/devmodus/Befunde.vue'),
    // ON-3: Einrichtungs-Assistent (nur Admin-Rollen; Guard + Server prüfen).
    Einrichtung:          () => import('./pages/einrichtung/Assistent.vue'),
    // N1 (OP-UI-6): unbekannte Adresse → verständliche Seite statt still Dashboard.
    NichtGefunden:        () => import('./pages/NichtGefunden.vue'),
}

// Exact routes
const routeMap = {
    '#/':              'Home',
    // UX3a: der Bereich heißt „Personen“ (vorher „Mitglieder“); die
    // Seitennamen der Bauteile bleiben, damit Anker/Guards stabil sind.
    '#/personen':      'Personen',
    // UX3b: der Reiter „Liste“ ist die zusammengelegte Ansicht (je Rolle
    // Mitgliederliste oder Adressbuch-Sicht). Er zeigt auf dieselbe Seite wie
    // der Einstieg — keine zwei Umsetzungen derselben Liste.
    '#/personen/liste':      'Personen',
    '#/personen/anfragen':   'MitgliederAnfragen',
    // UX3j (Entwurf A3): Die Unterbereiche von „Anfragen“ sind PFADTEILE
    // (`#/personen/<reiter>/<unter>`). Alle drei bleiben derselbe Seitenname —
    // Seitenleiste, Rechte-Guard und Fenstertitel gelten unverändert.
    '#/personen/anfragen/anfragen': 'MitgliederAnfragen',
    '#/personen/anfragen/links': 'MitgliederAnfragen',
    '#/personen/anfragen/formulare': 'MitgliederAnfragen',
    // UX3j (A3): „Übersicht“ und „Löschanträge“ sind KEINE Reiter der
    // Personen-Reiterzeile mehr (A3: Liste · Anfragen · Datenschutz · Import).
    // Die Reiter-Seitennamen bleiben trotzdem erhalten: `pages/mitglieder/
    // Bereich.vue` ist nur noch das Adress-Ziel der Personen-Seite, und der
    // Rechte-Guard (`ADMIN_ONLY_PAGES`) prüft weiterhin „Mitglieder…“ —
    // sonst wären beide Adressen für Mitglieder ohne Verwaltungsrecht offen.
    '#/personen/uebersicht': 'MitgliederUebersicht',
    '#/personen/loeschantraege': 'MitgliederLoeschantraege',
    '#/personen/datenschutz':'MitgliederDatenschutz',
    '#/personen/import':     'MitgliederImport',
    // UX3a: das Adressbuch ist ein Reiter von „Personen“ (vorher eigener Punkt).
    // UX3b2: die alte Adressbuch-Seite ist NICHT mehr erreichbar — beide
    // Adressen leiten DAUERHAFT auf die zusammengelegte Liste (deren Sicht
    // für Rollen ohne Verwaltungsrecht IST das Adressbuch). Eine eigene
    // Seite „Adressbuch“ hätte sonst eine zweite Liste ohne Blättern,
    // Statusfilter und „persönliche Daten“ — zwei halbe Wege.
    '#/personen/adressbuch': 'Personen',
    '#/gruppen':      'GruppenBereich',
    // N13: das Organigramm ist die zweite Ansicht der Gruppenseite
    // (Umschalter Liste/Organigramm), keine eigene Seite mehr.
    '#/gruppen/organigramm': 'GruppenBereich',
    '#/kalender':      'Kalender',
    '#/kalender/import': 'KalenderImport',
    '#/kalender/verwalten': 'KalenderVerwaltung',
    // UX3a (Entwurf A4): „Zu prüfen“ ist der vierte Reiter des Kalenders —
    // die bisherige Moderationsseite, nur für Moderatoren (Guard + Server).
    '#/kalender/pruefen': 'Pruefen',
    // UX3a: EIN Bereich „Dienste“ mit den Reitern Meine Dienste ·
    // Dienstpläne · Vorlagen. Der Einstieg öffnet „Meine Dienste“.
    '#/dienste':                  'Dienste',
    '#/dienste/meine-dienste':    'PlanrahmenDienste',
    '#/dienste/dienstplaene':     'DiensteDienstplaene',
    '#/dienste/vorlagen':         'DiensteVorlagen',
    // Unterbereiche der Dienstpläne (Plan, Vorlagen-Editor, Stammdaten) —
    // sie markieren in der Seitenleiste weiter „Dienste“.
    '#/dienste/dienstplaene/plan':  'DiensteDienstplaene',
    '#/dienste/dienstplaene/vorbereiten': 'DiensteDienstplaene',
    '#/ressourcen/verwalten': 'RessourcenVerwaltung',
    '#/anmeldungen':   'Registrierung',
    '#/registrierung': 'Registrierung',
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
    // UX2b: Papierkorb (nur Administration — der Server prueft die Rolle).
    '#/einstellungen/papierkorb': 'EinstellungenPapierkorb',
    '#/einstellungen/mailversand': 'EinstellungenMailversand',
    // WEB-3: Zustand der Primo-Anbindung + Kurzanleitung.
    '#/einstellungen/website': 'EinstellungenWebsite',
    // UX1k: Abstände, Rahmen und Rundungen (nur System Manager).
    '#/einstellungen/gestaltung': 'EinstellungenGestaltung',
    '#/website': 'Website',
    '#/profile':       'Profile',
    '#/ressourcen':    'Ressourcen',
    '#/beitraege':     'Beitraege',
    '#/wiki':          'Wiki',
    '#/lieder':        'Lieder',
    // UX3a: Liedgruppen sind der zweite Reiter von „Lieder“.
    '#/lieder/gruppen': 'Liedgruppen',
    '#/lieder/neu':    'LiedNeu',
    '#/liedgruppen':   'Liedgruppen',
    '#/planrahmen': 'PlanrahmenUebersicht',
    '#/planrahmen/meine-dienste': 'PlanrahmenDienste',
    '#/planrahmen/einrichten': 'PlanrahmenEinrichten',
    '#/dev-befunde': 'DevBefunde',
    // ON-3 (W4): dieselbe Adresse ist nach dem Abschluss „Einstellungen →
    // Einrichtung“ (Checkliste) — EIN Ort, kein zweiter Assistent.
    '#/einrichtung': 'Einrichtung',
}

// Dynamic routes: pattern regex → page name
const dynamicRoutes = [
    // UX3h: ein Feldtreffer der Einstellungen-Suche führt auf
    // `#/einstellungen/<bereich>/<feld>` — dieselbe Seite, der Abschnitt
    // springt dann zu seiner Marke `dk-sprung-<feld>` (pages/sprung.mjs).
    // Das Muster steht VOR allen anderen Einstellungs-Mustern; ohne es landete
    // der Treffer auf „Seite nicht gefunden“.
    { pattern: /^#\/einstellungen\/([a-z0-9-]+)\/[a-z0-9-]+$/, page: 'Einstellungen', param: 'bereich' },
    { pattern: /^#\/mitglied\/(.+)$/, page: 'MitgliedDetail', param: 'id' },
    // MT-7: EIN Beitrag ist eine eigene Unterseite (vorher nur ein Fenster).
    { pattern: /^#\/beitraege\/(.+)$/, page: 'BeitragDetail', param: 'id' },
    // UXD-R20: Wiki-Artikel sind teilbar („#/wiki/‹Kennung›“ öffnet den Artikel).
    // MT-7: … jetzt als eigene Unterseite (pages/WikiArtikel.vue) statt Fenster.
    { pattern: /^#\/wiki\/(.+)$/, page: 'WikiArtikel', param: 'id' },
    { pattern: /^#\/gruppe\/(.+)$/, page: 'GruppeDetail', param: 'id' },
    // UX3a: Liedgruppen sind ein Reiter von „Lieder“ (wörtlich VOR dem
    // Detailmuster, sonst schluckte `#/lieder/gruppen/…` den Reiter).
    { pattern: /^#\/lieder\/gruppen\/(.+)$/, page: 'LiedgruppeDetail', param: 'id' },
    { pattern: /^#\/lieder\/(.+)$/, page: 'LiedDetail', param: 'id' },
    // UX3a2: alte Lesezeichen `#/liedergruppen/‹id›` (Tippfehler-Muster aus
    // UX3a, dort stand `/liedergruppen/`) bleiben gültig.
    { pattern: /^#\/liedergruppen\/(.+)$/, page: 'LiedgruppeDetail', param: 'id' },
    // UX3a: Dienstpläne/Vorlagen sind Reiter von „Dienste“.
    { pattern: /^#\/dienste\/dienstplaene\/plan\/(.+)$/, page: 'PlanrahmenPlan', param: 'id' },
    { pattern: /^#\/dienste\/dienstplaene\/vorbereiten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plan' },
    // UX3a: der Vorlagen-Editor liegt unter „Dienste → Vorlagen“. Das Muster
    // steht HINTER dem Stammdaten-Muster, sonst würde `…/chorplan/stammdaten/neu`
    // als Editor-Kennung gelesen.
    { pattern: /^#\/planrahmen\/einrichten\/(.+)$/, page: 'PlanrahmenPlantypEditor', param: 'id' },
    // '-1' ist das Muster „ohne festen Plantyp“ (siehe einrichten-flow.mjs).
    { pattern: /^#\/dienste\/vorlagen\/([^/]+)\/stammdaten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plantyp' },
    { pattern: /^#\/dienste\/vorlagen\/(.+)$/, page: 'PlanrahmenPlantypEditor', param: 'id' },
    { pattern: /^#\/planrahmen\/stammdaten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plantyp' },
    { pattern: /^#\/planrahmen\/vorbereiten\/(.+)$/, page: 'PlanrahmenStammdaten', param: 'plan' },
    { pattern: /^#\/planrahmen\/plan\/(.+)$/, page: 'PlanrahmenPlan', param: 'id' },
]

// ── Weiterleitungen alter Adressen ─────────────────────────────────────────
// Konzept „Neuordnung“ Abschnitt 8: gespeicherte Lesezeichen und geteilte
// Links bleiben gültig. Rechte werden serverseitig geprüft; wer nicht darf,
// landet über den Guard auf dem Dashboard.
//
// UX3a (Manuel 2026-11-03): Die Menü-Umbenennung darf keine Lesezeichen
// brechen — JEDE alte Adresse leitet DAUERHAFT weiter. Ziele, die selbst ein
// Bereich-Einstieg sind, werden in `rolleWeiterleitung` rollenabhängig
// aufgelöst (`#/mitglieder` und `#/dienste`).
const WEITERLEITUNGEN = {
    '#/plaene':       '#/dienste/dienstplaene',
    '#/registrierung':'#/personen/anfragen',
    '#/anmeldungen':  '#/personen/anfragen',
    '#/statistik':    '#/personen/uebersicht',
    '#/anmeldung':    '#/einstellungen/anmeldung',
    // Entscheidung 9: Organigramm wird eine Ansicht in „Gruppen“.
    '#/organigramm':  '#/gruppen/organigramm',

    // ── UX3a: Umbenennungen und zusammengelegte Bereiche ──────────────────
    // Personen (vorher „Mitglieder“)
    // UX3b2: Auch der bloße Bereichsname führt auf die Liste. Administratoren
    // landeten vorher auf der „Übersicht“ (Kachel-Dashboard) — die Liste ist
    // seit UX3b der Einstieg (Entwurf A3: Liste ist der erste Reiter), also
    // gilt für ALLE dieselbe Weiterleitung.
    '#/mitglieder':                '#/personen/liste',
    '#/mitglieder/liste':          '#/personen/liste',
    '#/mitglieder/uebersicht':     '#/personen/uebersicht',
    '#/mitglieder/anfragen':       '#/personen/anfragen',
    '#/mitglieder/datenschutz':    '#/personen/datenschutz',
    '#/mitglieder/loeschantraege': '#/personen/loeschantraege',
    '#/mitglieder/import':         '#/personen/import',
    // Adressbuch und Datenschutz sind Reiter von „Personen“.
    // UX3b2: beide Adressbuch-Schreibweisen leiten DAUERHAFT auf die Liste
    // (#/personen/liste) — die alte Adressbuch-Seite ist nicht mehr erreichbar.
    '#/adressbuch':           '#/personen/liste',
    '#/personen/adressbuch':  '#/personen/liste',
    '#/datenschutz':  '#/personen/datenschutz',
    // „Zu prüfen“ ist der vierte Reiter des Kalenders (vorher „Moderation“).
    '#/moderation':   '#/kalender/pruefen',
    // Dienste (vorher „Dienstplan“ + „Pläne“ + „Meine Dienste“)
    '#/dienstplan':   '#/dienste/meine-dienste',
    '#/meine-dienste':'#/dienste/meine-dienste',
    '#/planrahmen':   '#/dienste/dienstplaene',
    '#/planrahmen/meine-dienste': '#/dienste/meine-dienste',
    '#/planrahmen/einrichten':    '#/dienste/vorlagen',
    '#/planrahmen/plan':          '#/dienste/dienstplaene',
    // Liedgruppen sind ein Reiter von „Lieder“.
    '#/liedgruppen':  '#/lieder/gruppen',
    // Die Detailmuster alter Form (#/lieder/‹id›, #/liedergruppen/‹id›) bleiben
    // in `dynamicRoutes` — nur der Reiter „Liedgruppen“ hat eine eigene Adresse.
}

// Weiterleitungen für Adressen MIT Kennung (Muster → Ziel mit Platzhalter).
// UX3a2: Das Tippfehler-Muster aus UX3a lautete `/liedergruppen/(.+)` und
// offenbarte damit, wie die alte Adresse gemeint war: `#/liedgruppen/‹id›`.
// Solche Lesezeichen leiten DAUERHAFT auf den Reiter „Lieder → Liedgruppen“ um
// (`location.replace`, Abfrageteil wird wie bei den festen Regeln mitgenommen).
//
// UX3c (Kartentext: „Begriff Planrahmen verschwindet aus Adresse und
// Oberfläche“): dieselbe Regel für ALLE Dienstplan-Adressen mit Kennung.
// Bisher fielen `#/planrahmen/plan/‹id›`, `…/vorbereiten/‹id›`,
// `…/stammdaten/‹Plantyp›` und `…/einrichten/‹id›` in „Seite nicht gefunden“
// — die alten festen Regeln deckten nur den Bereichseinstieg ab.
const MUSTER_WEITERLEITUNGEN = [
    // UX3j (Entwurf A3): Die Unterbereiche von „Anfragen“ stehen seit dieser
    // Karte als PFADTEIL in der Adresse (`#/personen/anfragen/links`). Die
    // frühere Form mit Abfrageteil (`?bereich=links`, aus UX-A2a) leitet
    // DAUERHAFT um — alte Lesezeichen bleiben gültig. `anfragen` selbst ist
    // der Hauptbereich und verliert den Abfrageteil.
    {
        pattern: /^#\/personen\/anfragen\?bereich=(?:anfragen)?$/,
        mitAbfrage: true,
        ziel: () => '#/personen/anfragen',
    },
    {
        pattern: /^#\/personen\/anfragen\?bereich=(links|formulare)$/,
        mitAbfrage: true,
        ziel: bereich => `#/personen/anfragen/${bereich}`,
    },
    // `/liedergruppen/…` (Tippfehler aus UX3a) UND `/liedgruppen/…` (die
    // gemeinte Adresse) → Reiter „Lieder → Liedgruppen“. Beide Muster stehen
    // einzeln: `ziel` bekommt IMMER die Kennung als erstes Argument.
    { pattern: /^#\/liedergruppen\/(.+)$/, ziel: id => `#/lieder/gruppen/${id}` },
    { pattern: /^#\/liedgruppen\/(.+)$/, ziel: id => `#/lieder/gruppen/${id}` },
    // Einzelner Plan → Reiter „Dienstpläne“.
    { pattern: /^#\/planrahmen\/plan\/(.+)$/, ziel: id => `#/dienste/dienstplaene/plan/${id}` },
    // Plan vorbereiten (Stammdaten im Plan-Kontext) → Reiter „Dienstpläne“.
    { pattern: /^#\/planrahmen\/vorbereiten\/(.+)$/, ziel: plan => `#/dienste/dienstplaene/vorbereiten/${plan}` },
    // Stammdaten einer Vorlage → Reiter „Vorlagen“. Der Plan-Kontext der alten
    // Adresse ist die Vorlage selbst (Platzhalter „-“ wie in einrichten-flow).
    { pattern: /^#\/planrahmen\/stammdaten\/(.+)$/, ziel: plantyp => `#/dienste/vorlagen/${plantyp}/stammdaten/-` },
    // Vorlagen-Editor → Reiter „Vorlagen“.
    { pattern: /^#\/planrahmen\/einrichten\/(.+)$/, ziel: id => `#/dienste/vorlagen/${id}` },
]

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

/**
 * UX3b2 (Befund 6): Steckt im Hash ein `?…`-Teil, gehört er NUR dann ans
 * Weiterleitungsziel, wenn die Weiterleitung ihn nicht selbst schon trägt
 * (sonst entstünde `#/personen/liste?status=Mitglied?bereich=…`).
 */
function _mitAbfrage(ziel, abfrage) {
    if (!abfrage) return ziel
    return ziel.includes('?') ? ziel : ziel + abfrage
}

// Rollenabhängige Weiterleitungen (nur wenn das Ziel für die Rolle passt).
function rollenWeiterleitung(pfad) {
    const boot = window.__DIakonosBOOT || {}
    const isAdmin = boot.is_admin || false
    if (pfad === '#/dsgvo') {
        // Abschnitt 8: Admin → Datenschutz-Reiter, alle anderen → Profil.
        return isAdmin ? '#/personen/datenschutz' : '#/profile'
    }
    if (pfad === '#/personen') {
        // UX3b (Entscheidung Manuel): „Personen“ ist EINE Ansicht je Rolle.
        // Wer die Verwaltungsreiter darf, landet auf der Liste (erste Reiter,
        // Entwurf A3); alle anderen ebenso — dort zeigt die Seite dann die
        // Adressbuch-Sicht. Kein Rollenrecht nötig: die Seite fragt den
        // Server, und der entscheidet über die Felder.
        return '#/personen/liste'
    }
    if (pfad === '#/dienste') {
        // Einstieg in den Bereich: „Meine Dienste“ ist die persönliche Sicht
        // (Entwurf A2, aktiv auf der Handy-Startseite). Die Planung liegt einen
        // Reiter daneben — kein Umweg über ein Rollenrecht nötig.
        const ziel = '#/dienste/meine-dienste'
        return pfad === ziel ? null : ziel
    }
    return null
}

/**
 * Ziel einer Weiterleitung (ohne Abfrageteil), oder null.
 * Ein Schluss-Schrägstrich wird ignoriert, damit "#/registrierung/" ebenso
 * greift wie "#/registrierung" (Befund R-N0-code 3).
 *
 * UX3j (Review-Nacharbeit Punkt 7): Die FESTEN Weiterleitungen haben Vorrang
 * vor den Mustern — ein Muster darf eine vorhandene Adresse nicht
 * überschreiben. Die Muster bekommen den Hash OHNE Abfrageteil; nur die
 * Muster, die den Abfrageteil selbst brauchen (alte `?bereich=`-Formen),
 * tragen das Flag `mitAbfrage` und sehen den vollen Hash. Vorher liefen die
 * Muster zuerst und sahen den vollen Hash — dadurch konnte ein `?…` an einem
 * Muster hängen bleiben und eine feste Regel verdecken.
 * `ziel` bekommt den ersten Klammer-Treffer.
 */
function weiterleitungsZiel(pfad, vollerHash = pfad) {
    const fest = WEITERLEITUNGEN[pfad] || rollenWeiterleitung(pfad)
    if (fest) return fest
    const [pfadTeil, abfrage] = zerlegeHash(String(vollerHash))
    const suchTeil = ohneSchlussslash(pfadTeil) + abfrage
    const pfadOhneAbfrage = ohneSchlussslash(pfadTeil)
    for (const regel of MUSTER_WEITERLEITUNGEN) {
        const m = String(regel.mitAbfrage ? suchTeil : pfadOhneAbfrage).match(regel.pattern)
        if (m) return regel.ziel(m[1])
    }
    return null
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
    // ON-3b (Orchestrator-Nachtrag): Die Ersteinrichtung ist ein EINMALIGER
    // Vorgang. Solange sie läuft, führt sie einen Admin beim Öffnen der App
    // auf den Assistenten (einmal pro Sitzung); danach gibt es die Adresse
    // für die Bedienung nicht mehr und leitet auf die Einstellungen.
    // Die Regel selbst steht in der importfreien Leitungsdatei (eine Wahrheit);
    // die VM-Tests des Routers setzen dort feste Rückgaben ein.
    const boot = window.__DIakonosBOOT || {}
    const einrichtungsZiel = leitung.einrichtungsWeiterleitung({
        pfad,
        hash: vollerHash,
        boot,
        gesehen: leitung.einrichtungGesehen(window.sessionStorage),
    })
    if (einrichtungsZiel && einrichtungsZiel !== vollerHash) {
        window.location.replace(einrichtungsZiel)
        return
    }
    // Ist der Assistent geschlossen, wird seine Seite GAR NICHT mehr geladen
    // (kein Bündel-Nachladen für eine Seite, die es nicht gibt). Die
    // Weiterleitung oben greift vorher — hier bleibt nur der Schutz für den
    // Fall, dass das Ziel gleich der aktuellen Adresse ist.
    if (pfad === leitung.EINRICHTUNG_ROUTE && !leitung.einrichtungSeiteErlaubt(boot)) {
        window.location.replace(leitung.EINRICHTUNG_ZIEL_NACH_ABSCHLUSS)
        return
    }
    const ziel = weiterleitungsZiel(pfad, vollerHash)
    if (ziel) {
        // UX3j: Ein Abfrageteil wird nur mitgenommen, wenn er zur Adresse
        // gehört (`?status=`, `?q=`) — die alten Anfragen-Unterbereiche trugen
        // ihren Bereich unter `?bereich=` und leiten auf einen PFAD um; diese
        // Abfrage darf am Ziel nicht hängen bleiben.
        const zielMitAbfrage = (abfrage && !/^#\/personen\/anfragen\?bereich=/.test(vollerHash))
            ? _mitAbfrage(ziel, abfrage)
            : ziel
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

    // MT-7b (Review-Punkt 5): Gilt der gemerkte Rückweg noch? Nur der Weg
    // Liste → Leseseite derselben Liste behält ihn; jeder andere Wechsel
    // (Menüpunkt im Gerüst, Gruppen-Detail, …) verwirft ihn. Die Liste selbst
    // setzt ihn beim Öffnen neu (`rueckwegMerken`).
    for (const liste of ['#/beitraege', '#/wiki']) {
        const vorher = acceptedRoute.value?.hash || ''
        // Sicherheitsnetz wie oben (`einrichtungLeitung`): fehlt das Modul
        // (Router-Tests streichen Importe), wird nichts verworfen und die
        // Seite bricht nicht.
        if (typeof rueckwegBleibtGueltig !== 'function') break
        if (!rueckwegBleibtGueltig(vorher, vollerHash, liste)) rueckwegVergessenFuerRoute(liste)
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
            hinweis: 'Lade die Seite neu. Bleibt es dabei, leere den Browser-Zwischenspeicher.',
            // UX2g: `grund` ist reine Diagnose (wird NICHT angezeigt) — der
            // Katalogtext ersetzt die Floskel „Unbekannter Fehler".
            grund: fehlertext(err),
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
// UX3a2: „Dienste“ wieder herausgenommen — wie vor UX3a (auf main: nur Start,
// Kalender, Profil). Die Erweiterung in UX3a galt nur dem Menüpunkt; die
// Seiten selbst sind für Gäste nicht vorgesehen (der Server liefert dort keine
// fremden Zuordnungen, die persönliche Sicht ist für Mitglieder gedacht).
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
    // UX3a: „Vorlagen“ (bisheriges Einrichten) ist Verwaltungsarbeit.
    'DiensteVorlagen', 'PlanrahmenEinrichten',
    // UX3c: „Dienstpläne“ steht bewusst NICHT hier. Dieser Guard kennt nur
    // `boot.is_admin`; Planer ohne Admin-Rolle (Bereichs-/Gruppenverantwort-
    // liche) müssen die Planübersicht wie auf main erreichen. Das Planungs-
    // recht prüft der Server (`einrichten_rechte`, sonst 403 → Leerzustand);
    // die Reiterzeile blendet den Reiter nach derselben Antwort aus.
    'Einstellungen', 'EinstellungenGemeinde', 'EinstellungenAnmeldung',
    'EinstellungenRollen', 'EinstellungenDevModus',
    'EinstellungenRegistrierung', 'EinstellungenDatenschutz',
    // BACKUP-1: die Datensicherung ist serverseitig nur fuer System Manager;
    // der Guard haelt alle anderen schon auf der Seite auf.
    'EinstellungenDatensicherung',
    // MAIL-1: Mailversand ebenso — der Server prueft zusaetzlich (403).
    'EinstellungenMailversand',
    // WEB-3: „Website (Primo)“ ist ein Einstellungs-Abschnitt wie die anderen.
    'EinstellungenWebsite',
    // UX1k: „Gestaltung“ ändert die Maße für alle — der Server verweigert
    // Nicht-System-Managern ohnehin mit 403.
    'EinstellungenGestaltung',
    'Registrierung',
    // ON-3: der Einrichtungs-Assistent ist Verwaltungsarbeit — der Server
    // weist Nicht-Admins ohnehin mit 403 ab.
    'Einrichtung',
])
onBeforeEach(({ name }) => {
    if (!ADMIN_ONLY_PAGES.has(name)) return
    const boot = window.__DIakonosBOOT || {}
    if (boot.is_admin) return
    navigate('#/')
    return false
})

// UX3a2: KEIN Admin-Guard für „Zu prüfen“/„Moderation“. Wie auf main dürfen
// Kalender-Moderatoren ohne Admin-Rolle die Seite erreichen — das Recht kommt
// vom Server (`can_moderate`); Moderation.vue fragt es ab und der Server prüft
// jeden Terminvorgang erneut. Ein Guard auf `boot.is_admin` sperrte genau
// diese Moderatoren aus.

// „Dev-Befunde“ liegt seit UX3a im Profilmenü (nicht mehr in der Seitenleiste).
// Die Adresse bleibt gültig; der Guard verlangt wie bisher eingeschalteten
// Dev-Modus und Admin- oder Tester-Rolle.
onBeforeEach(({ name }) => {
    if (name !== 'DevBefunde') return
    const boot = window.__DIakonosBOOT || {}
    if (boot.devmode && (boot.is_admin || boot.ist_tester)) return
    navigate('#/')
    return false
})

// WEB-3: „Website“ ist für System Manager, Administrator und Website-Moderator
// gedacht (dieselben Rollen wie `WEBSITE_ROLLEN` im Server). Der Server weist
// jede Anfrage zusätzlich mit 403 ab — hier wird nur die Seite nicht geladen.
onBeforeEach(({ name }) => {
    if (name !== 'Website') return
    const boot = window.__DIakonosBOOT || {}
    if (darfWebsite({ rollen: boot.roles })) return
    navigate('#/')
    return false
})

// Listen to hash changes
window.addEventListener('hashchange', resolveRoute)

// Initial resolve
resolveRoute()

export { currentHash, currentPageName, currentComponent }
