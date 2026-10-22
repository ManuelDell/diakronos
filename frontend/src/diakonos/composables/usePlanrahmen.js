/**
 * Plan-Rahmen: zentrale API-Wrapper und Helfer für die generische UI.
 *
 * Alle Endpunkte laufen über apiCall() (bestehende Session-/CSRF-Mittel);
 * strukturierte Fachfehler bringen ihre Meldungen mit (error.meldungen).
 * Kein Plantyp-spezifischer Code: Felder, Ansichten und Regeln kommen
 * ausschließlich aus der mitgelieferten Definition.
 */
import { ref, computed } from 'vue'
import { apiCall } from './useApi.js'
import { apiAntwortPruefen } from './useApi.js'
import { formatTemplate } from '../components/planrahmen/format.mjs'
import { GELOESCHT_ANZEIGE, istGeloescht } from './geloeschte-person.mjs'
import { stammdatenNormalisieren } from '../components/planrahmen/stammdaten.mjs'
import { setzeFeiertagskatalog } from '../components/planrahmen/anlaesse.mjs'
import { merkeKatalogDefinition, merkeKochbuchVorlage } from '../components/planrahmen/auswahlwerte.mjs'
import { wertAnzeige } from '../components/planrahmen/auswahlwerte.mjs'
import {
    cacheNutzerSetzen, standLesen, standSchreiben, gleich as staendeGleich,
    eintragVerwerfen, cacheLeeren as browserCacheLeeren,
} from './usePlanrahmenCache.js'

const API = 'diakronos.planrahmen.api.'

// Nutzerkennung fuer den Browser-Cache setzen (Wechsel/Abmelden leert ihn).
function nutzerAktualisieren() {
    const boot = (typeof window !== 'undefined' ? window.__DIakonosBOOT : null) || {}
    cacheNutzerSetzen(boot.user_email || boot.user_fullname || '')
}
nutzerAktualisieren()

// PF1: Lese-Aufrufe, die im Browser zwischengespeichert werden duerfen
// (stale-while-revalidate). Nur reine Anzeige-Antworten, keine Rechenergebnisse.
const CACHEBARE_LESER = new Set([
    'plan_holen', 'stammdaten_holen', 'plantypen_liste', 'plantyp_versionen_liste',
    'plaene_liste', 'meine_dienste', 'termin_struktur', 'lied_rechte',
    'merkmal_kandidaten', 'bedarf', 'einrichten_rechte', 'termin_strukturen',
    'abwesenheiten_liste',
])

async function call(name, args = {}) {
    const ergebnis = await apiCall(API + name, args)
    if (['eintrag_setzen', 'eintrag_loesen', 'plan_generieren', 'undo',
         'ablauf_aendern', 'abwesenheit_melden', 'abwesenheit_loeschen', 'dienst_absagen',
         'merkmale_pflegen', 'sammlung_pflegen',
         'veroeffentlichen', 'plan_anlegen', 'plantyp_speichern', 'lied_speichern',
         'lied_material_hinzufuegen', 'lied_material_loeschen',
         'sammlungsmerkmal_werte_pflegen', 'platz_hinzufuegen'].includes(name)) {
        kandidatenCache.clear()
        // Schreibaktion aendert den Plan-Stand: zwischengespeicherte Staende
        // dieses Plans sofort verwerfen (nie veraltete Daten zeigen).
        if (args && args.plan) planCacheVerwerfen(args.plan)
    }
    return ergebnis
}

/** Zwischengespeicherte Lese-Staende eines Plans/einer Vorlage verwerfen. */
function planCacheVerwerfen(plan) {
    if (!plan) return
    eintragVerwerfen('plan_holen', { plan })
    eintragVerwerfen('plan_stand_version', { plan })
}

/**
 * Lese-Aufruf mit Browser-Cache (stale-while-revalidate).
 *
 * `onCache` erhaelt sofort den zuletzt gesehenen Stand (falls vorhanden),
 * danach wird im Hintergrund frisch geladen. Nur ein echter Unterschied wird
 * gemeldet (`onFrisch`). Ohne Speicher/Netz verhaelt es sich wie ein normaler
 * Aufruf: `undefined` heisst "kein Cache-Stand".
 */
async function callMitCache(name, args, { onCache, onFrisch, versionPruefen } = {}) {
    nutzerAktualisieren()
    const gecacht = standLesen(name, args)
    if (gecacht !== null && gecacht !== undefined && onCache) {
        try { onCache(gecacht) } catch { /* Anzeige darf nie kippen */ }
    }
    // Billiger Versionsvergleich: unveraendert -> der Cache-Stand bleibt.
    if (gecacht !== null && gecacht !== undefined && versionPruefen) {
        try {
            const unveraendert = await versionPruefen()
            if (unveraendert) return gecacht
        } catch { /* Versionspruefung darf das Laden nie verhindern */ }
    }
    const frisch = await call(name, args)
    if (gecacht === null || gecacht === undefined || !staendeGleich(gecacht, frisch)) {
        standSchreiben(name, args, frisch)
        if (onFrisch) {
            try { onFrisch(frisch) } catch { /* egal */ }
        }
    } else {
        standSchreiben(name, args, frisch)
    }
    return frisch
}

// ── Fehler in Freundesmund ─────────────────────────────────────────────────

/** Fachfehler als freundliche deutsche Meldungsliste (nie roher Stack). */
export function fehlerMeldungen(err) {
    if (err && Array.isArray(err.meldungen) && err.meldungen.length) {
        return err.meldungen.map((m) => ({
            pfad: m.pfad || '',
            code: m.code || '',
            meldung: m.meldung || 'Unbekannter Fehler.',
            hinweis: m.hinweis || '',
            stufe: m.stufe === 'sollte' ? 'warnung' : (m.stufe || 'fehler'),
        }))
    }
    return [{ pfad: '', code: '', meldung: fehlerText(err), hinweis: '', stufe: 'fehler' }]
}

export function fehlerText(err) {
    if (!err) return 'Unbekannter Fehler.'
    if (err.status === 403) return 'Dafür fehlt dir die Berechtigung.'
    if (err.status === 404) return 'Der Eintrag wurde nicht gefunden.'
    if (err.status === 405) return 'Diese Aktion ist hier nicht erlaubt.'
    if (err.status === 417) return err.message || 'Die Eingaben konnten nicht geprüft werden.'
    if (err.status === 419 || err.status === 401) return 'Die Sitzung ist abgelaufen — bitte neu anmelden.'
    return err.message || 'Der Server hat die Anfrage abgelehnt.'
}

// ── Anzeige- und Attribut-Caches ───────────────────────────────────────────

const anzeigeCache = new Map()        // kennung → Anzeigename (Text oder Objekt)
const sammlungWerteCache = new Map()  // kennung → Attributobjekt (Titel, Seite …)

/** Anzeigedaten übernehmen (plan_holen.anzeige, feld_kandidaten). */
export function anzeigeUebernehmen(anzeige) {
    for (const [kennung, wert] of Object.entries(anzeige || {})) {
        if (kennung && wert) anzeigeCache.set(kennung,
            typeof wert === 'object' && wert.nr !== undefined ? { ...wert, nummer: wert.nummer ?? wert.nr } : wert)
    }
}

/** Kandidatenliste in die Anzeige-/Attributcaches übernehmen. */
export function kandidatenMerken(liste) {
    for (const k of liste || []) {
        if (typeof k === 'string') continue
        if (!k?.kennung) continue
        if (k.anzeige || k.name || k.titel) anzeigeCache.set(k.kennung, k)
        const daten = k.attribute || k.daten
        if (daten && typeof daten === 'object') sammlungWerteCache.set(k.kennung, daten)
    }
}

/**
 * Anzeigetext einer Kennung (niemals der interne Rohname, wenn bekannt).
 *
 * DSGVO-2d: Ist die Kennung die einer geloeschten Person (`geloescht-…`),
 * steht hier „Gelöschte Person“ — auch dann, wenn fuer diesen Termin keine
 * Anzeige mitkommt (alter Plan, geloeschter Eintrag). Sonst stuende die
 * technische Kennung in der Zelle.
 */
export function nameZeigen(kennung) {
    if (kennung === null || kennung === undefined || kennung === '') return '–'
    const wert = anzeigeCache.get(kennung)
    if (wert && typeof wert === 'object') {
        const text = wert.name || wert.titel || wert.kuerzel || String(kennung)
        if (istGeloescht(wert) || istGeloescht(text)) return GELOESCHT_ANZEIGE
        return text
    }
    if (istGeloescht(kennung) || istGeloescht(wert)) return GELOESCHT_ANZEIGE
    return wert || kennung
}

/** Anzeigeobjekt einer Kennung (für Formatvorlagen: .kuerzel, .name, .seite). */
export function anzeigeZu(kennung) {
    if (typeof kennung !== 'string') return kennung
    return anzeigeCache.get(kennung) || sammlungWerteCache.get(kennung) || nameZeigen(kennung)
}

export function sammlungAttribut(kennung) {
    return sammlungWerteCache.get(kennung) || null
}

export function cacheLeeren() {
    anzeigeCache.clear()
    sammlungWerteCache.clear()
    definitionCache.clear()
    kandidatenCache.clear()
}

// ── Endpunkte (Bestand) ────────────────────────────────────────────────────

async function schemaHolen() { return call('schema_holen') }
/**
 * K4: der Feiertags-Katalog des Servers — EINE Quelle für die Oberfläche.
 *
 * P3-1d (W3): Der Aufruf wird von der ÜBERSICHT beim Laden des Plan-Bereichs
 * ausgeführt (`Uebersicht.vue` → `ladenAlles`), also BEVOR ein Editor oder
 * eine Planseite geöffnet wird. Die zurückgegebenen Namen ersetzen die (nur
 * als Rückfall dienende) statische Liste in `editor.mjs`/`anlaesse.mjs`, damit
 * ein im Backend geänderter Name ohne Neubau sichtbar wird.
 */
async function feiertageHolen() {
    const liste = await call('feiertage_holen')
    setzeFeiertagskatalog(liste)
    return liste
}
async function dokuHolen(name = 'REFERENZ') { return call('doku_holen', { name }) }
async function kochbuchListe() { return call('kochbuch_liste') }
async function kochbuchHolen(name) { return call('kochbuch_holen', { name }) }

/**
 * P3-1d (W2): die Kochbuch-Vorlagen als Katalog für Anzeigenamen merken —
 * ZUERST, damit die danach gemerkten gespeicherten Versionen Vorrang haben.
 * Fehler bleiben still: ohne Kochbuch-Nachschlag zeigt die Oberfläche wie
 * bisher die gespeicherte Kennung.
 */
async function kochbuchKatalogMerken() {
    // REST-1 (2): Ein Fehler der LISTE wird weitergereicht, damit
    // `katalogSichern` sein Versprechen verwirft und die naechste Seite es
    // erneut versucht. (Eine einzelne defekte Vorlage bleibt folgenlos.)
    const namen = await kochbuchListe()
    const liste = Array.isArray(namen) ? namen : []
    // REST-1 (2): PARALLEL statt nacheinander. Der Katalog wird jetzt auch
    // beim Direktaufruf einer Planseite geladen (siehe `katalogSichern`) —
    // nacheinander wären das ~10 Roundtrips, bevor die Seite etwas zeigt.
    // Gemerkt wird in der Reihenfolge der Liste, damit der Vorrang
    // (zuletzt gemerkt gewinnt) unverändert bleibt.
    const vorlagen = await Promise.all(liste.map(async (name) => {
        try {
            return await kochbuchHolen(name)
        } catch {
            // Eine defekte Kochbuch-Datei darf die Planseite nicht aufhalten.
            return null
        }
    }))
    for (const vorlage of vorlagen) {
        if (vorlage) merkeKochbuchVorlage(vorlage)
    }
    return liste
}

/**
 * REST-1 (2): Katalog EINMAL je Sitzung laden — Kochbuch-Vorlagen
 * (Anzeigenamen) und Feiertagsliste des Servers.
 *
 * Befund R-P3-1d W-a: Beides wurde nur in `Uebersicht.vue` geladen. Wer direkt
 * auf eine Planseite, die Druckansicht, die Stammdaten oder einen Editor kam
 * (geteilter Link, Neuladen, Sprung aus „Meine Dienste“), sah für gespeicherte
 * Vorlagen weiter die Kennung („Floete“ statt „Flöte“).
 *
 * Das Versprechen wird zwischengespeichert (K-a: kein zweiter Satz Aufrufe bei
 * jedem Besuch der Übersicht) und bei einem Fehler wieder verworfen, damit die
 * nächste Seite es erneut versuchen kann. Fehler bleiben still: ohne Katalog
 * zeigt die Oberfläche wie bisher die gespeicherte Kennung.
 */
let katalogVersprechen = null

export function katalogSichern() {
    if (katalogVersprechen) return katalogVersprechen
    katalogVersprechen = (async () => {
        const [vorlagen, feiertage] = await Promise.allSettled([
            kochbuchKatalogMerken(),
            feiertageHolen(),
        ])
        if (vorlagen.status === 'rejected' || feiertage.status === 'rejected') {
            // Nicht dauerhaft auf einem Fehlschlag stehen bleiben.
            katalogVersprechen = null
        }
        return {
            vorlagen: vorlagen.status === 'fulfilled' ? vorlagen.value : [],
            feiertage: feiertage.status === 'fulfilled' ? feiertage.value : [],
        }
    })()
    return katalogVersprechen
}
/**
 * Einrichtungs-Rechte des eigenen Bereichs (nur Bereichs-/Planverantwortliche).
 * UXP-R2: Fuer Mitglieder ohne Verantwortung ist 403 vorgesehen — dann wird
 * still `{darf_anlegen:false}` geliefert. Vorher warf der Aufruf, und weil die
 * Uebersicht ihn per `Promise.all` mit den Plaenen holte, verschwand die
 * gesamte Planliste hinter einem Berechtigungsfehler („Dafuer fehlt dir die
 * Berechtigung.") obwohl `plaene_liste` die veroeffentlichten Plaene liefert.
 */
async function einrichtenRechte() {
    try {
        return await call('einrichten_rechte')
    } catch (err) {
        if (err?.status === 403) return { darf_anlegen: false, bereiche: [], gruppen: [], admin: false }
        throw err
    }
}
async function stammdatenHolen(plantyp, plan = null) {
    // REST-1 (2): Anzeigenamen/Feiertage auch beim Direktaufruf der Stammdaten.
    await katalogSichern().catch(() => null)
    const daten = await callMitCache('stammdaten_holen', { plantyp, plan })
    return stammdatenNormalisieren(daten)
}
async function plantypPruefen(definition) { return call('plantyp_pruefen', { definition }) }
/** UXP-R5: ``bestehendeErlauben=false`` ist der Weg „neue Planvorlage anlegen“. */
async function plantypSpeichern(definition, gueltigAb, kommentar, bestehendeErlauben = true) {
    return call('plantyp_speichern', { definition, gueltig_ab: gueltigAb,
        kommentar: kommentar || null, bestehende_erlauben: bestehendeErlauben })
}
async function plantypVersionenListe(plantyp) {
    // REST-1 (2): der Plantyp-Editor ist ein eigener Einstieg (Direktlink).
    await katalogSichern().catch(() => null)
    return call('plantyp_versionen_liste', { plantyp })
}
/** UXP-R12: Zahl der Termine/Pläne, die eine neue Version umbindet. */
async function plantypAuswirkung(plantyp, gueltigAb) {
    return call('plantyp_auswirkung', { plantyp, gueltig_ab: gueltigAb })
}
async function planAnlegen(plantyp, titel, von, bis, parameter, verantwortlich) {
    return call('plan_anlegen', {
        plantyp, titel, von, bis,
        parameter: parameter || {},
        verantwortlich: verantwortlich || null,
    })
}

/* ── P1-14 / OP-UI-12: Plan-Lebenszyklus ───────────────────────────────── */

/** OP-UI-12 / P1-14b: Entwurf endgültig löschen (veröffentlichte nur archivieren).
 *
 * Der Server verlangt ``bestaetigt=true`` (unwiderrufliche Löschung); die
 * Oberfläche holt die Bestätigung über einen DkDialog ein.
 */
async function planLoeschen(plan, bestaetigt = false) {
    return call('plan_loeschen', { plan, bestaetigt })
}
/** OP-UI-12: Plan archivieren bzw. zurückholen. */
async function planArchivieren(plan, archivieren = true) {
    return call('plan_archivieren', { plan, archivieren })
}
/** OP-UI-12: Plan samt Terminen (und optional Einträgen) kopieren. */
async function planKopieren(plan, titel, mitEintraegen = true, von = null, bis = null) {
    return call('plan_kopieren', { plan, titel, mit_eintraegen: mitEintraegen, von, bis })
}
/** OP-UI-12: Titel/Zeitraum/Parameter eines Plans ändern. */
async function planAendern(plan, { titel = null, von = null, bis = null, parameter = null } = {}) {
    return call('plan_aendern', { plan, titel, von, bis, parameter })
}

/* ── P1-14 / OP-CHOR-1 + OP-EVENT-18: Termine ändern ───────────────────── */

/** OP-CHOR-1: Datum, Uhrzeit, Absage, Titel, Anlässe eines Termins ändern. */
async function terminAendern(plan, termin, felder = {}) {
    return call('termin_aendern', { plan, termin, ...felder })
}
/** OP-CHOR-1: manuellen Sondertermin hinzufügen. */
async function terminHinzufuegen(plan, daten) {
    return call('termin_hinzufuegen', { plan, ...daten })
}
/** OP-CHOR-1: Termin samt Einträgen entfernen (mit Undo). */
async function terminEntfernen(plan, termin) {
    return call('termin_entfernen', { plan, termin })
}

/** UXP-R20: Was würde „Rückgängig“ zurücknehmen? (nur lesend) */
async function undoVorschau(plan) { return call('undo_vorschau', { plan }) }
async function planHolen(plan, optionen = {}) {
    // REST-1 (2): Katalog (Anzeigenamen + Feiertage) mitladen, damit auch der
    // DIREKTAUFRUF dieser Seite (Link, Neuladen) die Anzeigenamen kennt.
    // Vor dem Anzeigen abwarten — sonst zeigte der erste Aufbau noch
    // „Floete“ und tauschte erst nach dem Nachladen auf „Flöte“ um. Ein
    // Katalogfehler hält die Planseite nicht auf.
    await katalogSichern().catch(() => null)
    const daten = await callMitCache('plan_holen', { plan }, {
        onCache: optionen.onCache,
        onFrisch: (erg) => {
            anzeigeCache.clear()
            sammlungWerteCache.clear()
            if (erg?.anzeige) anzeigeUebernehmen(erg.anzeige)
            if (optionen.onFrisch) optionen.onFrisch(erg)
        },
        versionPruefen: optionen.versionPruefen,
    })
    if (optionen.onCache) {
        // Der Cache-Stand wird sofort gezeigt: seine Anzeige uebernehmen.
        anzeigeCache.clear()
        sammlungWerteCache.clear()
        if (daten?.anzeige) anzeigeUebernehmen(daten.anzeige)
    }
    return daten
}

/** Billiger Versionsstempel des Plan-Stands (PF1, Browser-Cache). */
async function planStandVersion(plan) {
    return call('plan_stand_version', { plan })
}
async function plaeneListe() { return call('plaene_liste') }
async function meineDienste() {
    // REST-1 (2): „Meine Dienste“ ist ein Direktaufruf-Einstieg (Sidebar,
    // Nachricht, Lesezeichen) — die Anzeigenamen müssen dort stehen.
    await katalogSichern().catch(() => null)
    return call('meine_dienste')
}
async function terminStruktur(plan, termin) { return call('termin_struktur', { plan, termin }) }
/** PF1: alle Termin-Strukturen eines Plans in einem Aufruf (kein N+1 mehr). */
async function terminStrukturen(plan) { return call('termin_strukturen', { plan }) }
async function planGenerieren(plan, nurVorschau = false, seed = 0, nurLuecken = false) {
    return call('plan_generieren', { plan, nur_vorschau: nurVorschau, seed, nur_luecken: nurLuecken })
}
async function planEntwurf(plan) { return call('plan_entwurf', { plan }) }
async function eintragSetzen(plan, termin, feldPfad, wert) {
    return call('eintrag_setzen', { plan, termin, feld_pfad: feldPfad, wert })
}
async function eintragLoesen(plan, termin, feldPfad) {
    return call('eintrag_loesen', { plan, termin, feld_pfad: feldPfad })
}
async function platzHinzufuegen(plan, termin, feldPfad) {
    return call('platz_hinzufuegen', { plan, termin, feld_pfad: feldPfad })
}
async function undoPlan(plan) { return call('undo', { plan }) }
async function veroeffentlichen(plan) { return call('veroeffentlichen', { plan }) }
async function bedarf(plantyp, plan = null) { return call('bedarf', { plantyp, plan }) }
async function trockenlauf(definition, parameter = {}, ab = null, wochen = 8, seed = 0) {
    return call('trockenlauf', { definition, parameter, ab, wochen, seed })
}
async function merkmalePflegen(plantyp, werte, plan = null) {
    return call('merkmale_pflegen', { plantyp, werte, plan })
}
async function sammlungPflegen(plantyp, sammlung, eintraege, plan = null) {
    return call('sammlung_pflegen', { plantyp, sammlung, eintraege, plan })
}
async function abwesenheitMelden(mitglied, von, bis, grund = '', plantyp = null, plan = null) {
    return call('abwesenheit_melden', { mitglied, von, bis, grund, plantyp, plan })
}
/** UXP-R17: gemeldete Abwesenheiten lesen (ohne mitglied: die eigenen). */
async function abwesenheitenListe(mitglied = null, plantyp = null, plan = null) {
    return call('abwesenheiten_liste', { mitglied, plantyp, plan })
}
/** UXP-R17: eigene Abwesenheit zuruecknehmen (Fehleingabe korrigieren). */
async function abwesenheitLoeschen(abwesenheit) {
    return call('abwesenheit_loeschen', { abwesenheit })
}
/** OP-HANDY-18: eigene Einteilung absagen — der Platz wird wieder frei. */
async function dienstAbsagen(plan, termin, feldPfad) {
    return call('dienst_absagen', { plan, termin, feld_pfad: feldPfad })
}

// ── ST2: Lieder pflegen ────────────────────────────────────────────────────

/** Rollengefilterte Personen-Kandidaten eines Listen-Merkmals (ST2). */
async function merkmalKandidaten(plantyp, schluessel, plan = null) {
    return call('merkmal_kandidaten', { plantyp, schluessel, plan })
}

/** Lied umbenennen bzw. Nummer/Buch/Seite aendern (Psalmos = eine Wahrheit). */
async function liedSpeichern(plantyp, lied, daten, plan = null) {
    return call('lied_speichern', { plantyp, lied, daten, plan })
}

/** Material (Noten/Audio/Notensatz) an ein Lied haengen. */
async function liedMaterialHinzufuegen(plantyp, lied, art, dateiname, dateiUrl,
                                       stimme = '', beschreibung = '', plan = null) {
    return call('lied_material_hinzufuegen', {
        plantyp, lied, art, dateiname, datei_url: dateiUrl,
        stimme: stimme || '', beschreibung: beschreibung || '', plan,
    })
}

/** Material eines Liedes entfernen. */
async function liedMaterialLoeschen(plantyp, lied, material, plan = null) {
    return call('lied_material_loeschen', { plantyp, lied, material, plan })
}

/* ── P1-10 / UXM-R9: Liedgruppen pflegen ────────────────────────────────── */

// Liedgruppen liegen in Psalmos (eine Wahrheit), nicht im Plan-Rahmen.
const MUSIK = 'diakronos.psalmos.api.musik.'

/** Liedgruppe anlegen oder aendern (`daten` enthaelt `name` zum Aendern). */
async function liedgruppeSpeichern(daten) {
    return apiCall(MUSIK + 'save_liedgruppe', { daten })
}

/** Liedgruppe mit ihren Zuordnungen loeschen. */
async function liedgruppeLoeschen(liedgruppe) {
    return apiCall(MUSIK + 'delete_liedgruppe', { liedgruppe })
}

/** Lieder fuer die Auswahl in der Liedgruppen-Pflege suchen (max. 50). */
async function liederSuchen(suche = '', limit = 50) {
    return apiCall(MUSIK + 'get_lieder', { suche: suche || null, limit })
}

/** Auswahl-/Tag-Werte eines Listen-Merkmals pflegen (ST2). */
async function sammlungsmerkmalWertePflegen(plantyp, schluessel, aktion, wert, neu = null, plan = null) {
    return call('sammlungsmerkmal_werte_pflegen', { plantyp, schluessel, aktion, wert, neu, plan })
}

/**
 * Datei-Upload (Multipart) über den bestehenden `upload_file`-Endpunkt.
 * Liefert `{file_url, file_name, ...}`. Kein JSON-Weg — bewusst rohes fetch,
 * weil `apiCall` JSON erzwingt.
 */
async function uploadDatei(file) {
    const url = '/api/method/upload_file'
    const csrf_token = window.__DIakonosBOOT?.csrf_token || ''
    const form = new FormData()
    form.append('file', file, file.name)
    form.append('is_private', 'true')
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'X-Frappe-CSRF-Token': csrf_token },
        body: form,
    })
    const data = await apiAntwortPruefen(res)
    if (!res.ok || data?.exc) {
        const err = new Error(data?.message || data?.exception || `HTTP ${res.status}`)
        err.status = res.status
        throw err
    }
    return data.message
}

// ── Endpunkte (UI1-Erweiterungen) ──────────────────────────────────────────

/**
 * Plantypen des eigenen Bereichs (nur Planer). Für Mitglieder ist 403
 * vorgesehen — dann wird still None geliefert (kein Fehlerbild).
 */
async function plantypenListe() {
    try {
        // REST-1 (2): Einrichten/Editor ohne vorherige Übersicht.
        await katalogSichern().catch(() => null)
        const liste = await call('plantypen_liste')
        // P3-1c (A): die neuesten Plantyp-Versionen sind der Katalog, aus dem
        // gespeicherte Vorlagen ohne eigenes `anzeigenamen` ihre Anzeigenamen
        // zur Laufzeit aufloesen.
        for (const t of Array.isArray(liste) ? liste : []) {
            merkeKatalogDefinition(t?.letzte_version?.definition)
        }
        return liste
    } catch (err) {
        if (err?.status === 403) return null
        throw err
    }
}

const kandidatenCache = new Map()

/** Rollengefilterte Kandidaten eines Felds (ersetzt jede Freitexteingabe). */
async function feldKandidaten(plan, termin, feldPfad) {
    const key = `${plan}|${termin}|${feldPfad}`
    if (kandidatenCache.has(key)) return kandidatenCache.get(key)
    const erg = await call('feld_kandidaten', { plan, termin, feld_pfad: feldPfad })
    kandidatenMerken(erg?.kandidaten)
    kandidatenCache.set(key, erg)
    return erg
}

/** Ablauf-Elemente ändern: Operationen (hinzufuegen/verschieben/loeschen). */
async function ablaufAendern(plan, termin, operationen) {
    const ergebnisse = []
    for (const op of operationen) {
        ergebnisse.push(await call('ablauf_aendern', {
            plan, termin, feld: op.feld_pfad, aktion: op.aktion,
            element_typ: op.typ || null, element_id: op.element_id || null,
            position: op.position ?? null,
        }))
    }
    kandidatenCache.clear()
    return ergebnisse
}

// ── Definitionen (versioniert pro Termin) ──────────────────────────────────

const definitionCache = new Map()  // `${plan}:${versionId}` → definition

/**
 * Liefert { versionId → definition } für alle Versionsbindungen der Termine.
 * Quelle ist termin_struktur (fixierte Versionsdefinition je Termin) —
 * auch für Mitglieder lesbar, damit niemals Kandidaten im Lesemodus nötig sind.
 */
async function ladeDefinitionen(plan, termine) {
    const proVersion = new Map()
    for (const t of termine || []) {
        if (!proVersion.has(t.plantyp_version)) proVersion.set(t.plantyp_version, t.id)
    }
    const ergebnis = new Map()
    for (const [versionId, terminId] of proVersion) {
        const key = `${plan}:${versionId}`
        if (definitionCache.has(key)) {
            ergebnis.set(versionId, definitionCache.get(key))
            continue
        }
        const struktur = await terminStruktur(plan, terminId)
        const definition = struktur?.version?.definition || null
        if (definition) {
            definitionCache.set(key, definition)
            // P3-1c (A): auch die fixierte Version kann Anzeigenamen tragen.
            merkeKatalogDefinition(definition)
        }
        ergebnis.set(versionId, definition)
    }
    return ergebnis
}

// ── Werte und Datum ────────────────────────────────────────────────────────

/** Rohwert als kurze deutsche Anzeige (ohne Formatvorlage). */
export function wertText(wert) {
    if (wert === null || wert === undefined || wert === '') return '–'
    if (Array.isArray(wert)) return wert.map((w) => wertText(w)).filter((s) => s !== '–').join(', ') || '–'
    if (typeof wert === 'boolean') return wert ? 'ja' : 'nein'
    if (typeof wert === 'object') return wert.name || wert.titel || wert.kuerzel || JSON.stringify(wert)
    return nameZeigen(String(wert))
}

/** Datum (ISO) deutsch, z. B. 'So, 04.10.2026'. */
export function datumText(iso, mitWochentag = true) {
    if (!iso) return '–'
    const d = new Date(String(iso).slice(0, 10) + 'T12:00:00')
    if (isNaN(d)) return String(iso)
    const opts = { day: '2-digit', month: '2-digit', year: 'numeric' }
    if (mitWochentag) opts.weekday = 'short'
    return d.toLocaleDateString('de-DE', opts)
}

/** Zeit (ISO-Time) deutsch, z. B. '10:00 Uhr'. */
export function uhrzeitText(iso) {
    if (!iso) return ''
    return String(iso).slice(0, 5) + ' Uhr'
}

// ── Feldbaum-Helfer (generisch, aus der Definition) ────────────────────────

/** Anzahl-Bereich 'min..max' → { min, max|null(offen) }. */
export function anzahlBereich(anzahl) {
    if (anzahl === undefined || anzahl === null || anzahl === '') return { min: 1, max: 1 }
    if (typeof anzahl === 'number') return { min: anzahl, max: anzahl }
    const m = String(anzahl).match(/^(\d+)\.\.(\d+|\*)$/)
    if (!m) return { min: 1, max: 1 }
    return { min: parseInt(m[1], 10), max: m[2] === '*' ? null : parseInt(m[2], 10) }
}

/** Terminreihen der Definition ('standard' = Kurzform). */
export function reihenFelder(definition) {
    if (!definition) return [{ id: 'standard', name: '', felder: [] }]
    const reihen = definition.terminreihen
    if (Array.isArray(reihen) && reihen.length) {
        return reihen.map((r) => ({ id: r.id, name: r.name || r.id, felder: r.felder || [] }))
    }
    return [{ id: 'standard', name: '', felder: definition.felder || [] }]
}

/** Reihen-Präfix für Feldpfade ('gottesdienst:team'; 'standard' → ''). */
export function reihePraefix(reiheId) {
    return !reiheId || reiheId === 'standard' ? '' : reiheId + ':'
}

/** Blattfelder eines Feldbaums als flache Liste mit Pfad. */
export function blattFelder(felder, basis = '') {
    const result = []
    for (const f of felder || []) {
        const pfad = basis + f.id
        if (f.art === 'gruppe') {
            result.push({ ...f, pfad, blatt: false })
            result.push(...blattFelder(f.inhalt || [], pfad + '.'))
            for (const zweig of [...(f.varianten || []), ...(f.teile || [])]) {
                const obj = typeof zweig === 'string' ? { id: zweig } : zweig
                if (Array.isArray(obj.inhalt)) result.push(...blattFelder(obj.inhalt, pfad + '.'))
            }
        } else if (f.art === 'ablauf') {
            result.push({ ...f, pfad, blatt: false })
            for (const el of f.elemente || []) {
                const elem = typeof el === 'string' ? { typ: el } : el
                result.push(...blattFelder(elem.inhalt || [], `${pfad}/${elem.typ}.`))
            }
        } else {
            result.push({ ...f, pfad, blatt: true })
            if (Array.isArray(f.inhalt)) result.push(...blattFelder(f.inhalt, pfad + '.'))
        }
    }
    return result
}

/** Einträge eines Termins als Map: feld_pfad → Eintrag. */
export function eintraegeMap(eintraege, terminId) {
    const m = new Map()
    for (const e of eintraege || []) {
        if (terminId && e.termin !== terminId) continue
        m.set(e.feld_pfad, e)
    }
    return m
}

/** Feldzugehörigkeit einschließlich Varianten, Teilen und Terminreihen. */
export function feldGehoertZu(pfad, basis) {
    if (basis.endsWith(':')) return pfad.startsWith(basis)
    return pfad === basis || ['.', '[', '@', '#', '/'].some(trenner => pfad.startsWith(basis + trenner))
}

/** Einträge, die zu einem Feldpfad gehören (auch Instanzen/Unterfelder). */
export function eintraegeZu(eintraege, terminId, basisPfad) {
    const punkt = basisPfad + '.'
    return (eintraege || []).filter((e) =>
        e.termin === terminId && (e.feld_pfad === basisPfad || e.feld_pfad.startsWith(punkt) ||
            e.feld_pfad.startsWith(basisPfad + '[')))
}

/** Instanzen eines Feldpfads: [{index, selbst, unter: Map(id → Eintrag)}]. */
export function instanzenZu(eintraege, terminId, basisPfad) {
    const gruppen = new Map()
    for (const e of eintraege || []) {
        if (e.termin !== terminId) continue
        let rest = null
        let index = null
        if (e.feld_pfad === basisPfad) {
            rest = ''
        } else if (e.feld_pfad.startsWith(basisPfad + '[')) {
            const m = e.feld_pfad.slice(basisPfad.length).match(/^\[(\d+)\](.*)$/)
            if (!m) continue
            index = parseInt(m[1], 10)
            rest = m[2]
        } else if (e.feld_pfad.startsWith(basisPfad + '.')) {
            rest = e.feld_pfad.slice(basisPfad.length)
        } else {
            continue
        }
        const key = index === null ? '–' : String(index)
        if (!gruppen.has(key)) gruppen.set(key, { index, selbst: null, unter: new Map() })
        const g = gruppen.get(key)
        if (rest === '') g.selbst = e
        else g.unter.set(rest.slice(1), e)
    }
    const liste = [...gruppen.values()].sort((a, b) => (a.index ?? 0) - (b.index ?? 0))
    return liste.length ? liste : [{ index: null, selbst: null, unter: new Map() }]
}

/** Plan-/Termin-Kontext für Formatvorlagen (kopf, fuss, Zellen). */
export function planKontext(plan, termin) {
    const anlaesse = Array.isArray(termin?.anlaesse) ? termin.anlaesse.join(', ') : ''
    return {
        plan: { id: plan?.id, titel: plan?.titel || '' },
        termin: {
            datum: termin?.datum || '',
            uhrzeit: termin?.uhrzeit ? String(termin.uhrzeit).slice(0, 5) : '',
            titel: termin?.titel || '',
            anlass: anlaesse,
            anlaesse,
        },
        parameter: plan?.parameter || {},
        anlass: anlaesse,
    }
}

/** Kennungswert in Formatkontext: Anzeigeobjekt (name/kuerzel/titel …). */
function kontextWertRoh(wert, art, feld) {
    if (wert === null || wert === undefined) return undefined
    if (Array.isArray(wert)) return wert.map((w) => kontextWertRoh(w, art, feld))
    if (typeof wert === 'object') return wert
    // P3-1c (A): Auswahlwerte zeigen ihren Anzeigenamen („Männerchor“), auch in
    // Programm-/Druckvorlagen (`{wert}`), nicht die gespeicherte Kennung.
    if (art === 'auswahl') return wertAnzeige(feld, String(wert))
    if (art === 'person' || art === 'personen' || art === 'team' || art === 'eintrag') {
        return anzeigeZu(String(wert))
    }
    return wert
}

/**
 * Kontext einer Zelle (eine Instanz eines Felds) für Formatvorlagen:
 * { eintrag, <unterfeld-id>, wert, … } plus Plan-/Termin-Basis.
 */
export function zellenKontext(plan, termin, instanz, feld) {
    const ctx = planKontext(plan, termin)
    const selbst = instanz?.selbst?.wert
    if (feld?.art === 'eintrag') ctx.eintrag = kontextWertRoh(selbst, 'eintrag')
    // P3-1c (A): das Feld selbst mitgeben, damit Auswahlwerte ihren
    // Anzeigenamen zeigen (auch `{wert}` in Programm-/Druckvorlagen).
    ctx.wert = kontextWertRoh(selbst, feld?.art, feld)
    const deklarationen = new Map()
    for (const u of feld?.inhalt || []) deklarationen.set(u.id, u)
    for (const [id, e] of instanz?.unter || []) {
        const dek = deklarationen.get(id) || deklarationen.get(String(id).split(/[@#]/)[0])
        ctx[id] = kontextWertRoh(e.wert, dek?.art || '', dek)
    }
    return ctx
}

/** Formatvorlage anwenden (Parser: components/planrahmen/format.mjs). */
export function formatVorlage(template, kontext) {
    if (!template) return ''
    try {
        return formatTemplate(template, kontext || {})
    } catch {
        return ''
    }
}

// ── Composable ─────────────────────────────────────────────────────────────

const erweiterungenFehlend = ref(0)

export function usePlanrahmen() {
    return {
        // Endpunkte
        schemaHolen, feiertageHolen, dokuHolen, kochbuchListe, kochbuchHolen, kochbuchKatalogMerken, katalogSichern, einrichtenRechte, stammdatenHolen, plantypPruefen, plantypSpeichern,
        plantypVersionenListe, plantypAuswirkung, plantypenListe, planAnlegen, planHolen, planStandVersion, plaeneListe,
        planLoeschen, planArchivieren, planKopieren, planAendern,
        terminAendern, terminHinzufuegen, terminEntfernen, undoVorschau,
        meineDienste, terminStruktur, terminStrukturen, planGenerieren, planEntwurf, eintragSetzen, eintragLoesen, platzHinzufuegen,
        undoPlan, veroeffentlichen, bedarf, trockenlauf, merkmalePflegen,
        sammlungPflegen, abwesenheitMelden, abwesenheitenListe, abwesenheitLoeschen, dienstAbsagen, feldKandidaten, ablaufAendern,
        // ST2: Lieder pflegen
        merkmalKandidaten, liedSpeichern, liedMaterialHinzufuegen, liedMaterialLoeschen,
        sammlungsmerkmalWertePflegen, uploadDatei,
        // P1-10 / UXM-R9: Liedgruppen pflegen
        liedgruppeSpeichern, liedgruppeLoeschen, liederSuchen,
        // Helfer
        fehlerMeldungen, fehlerText, wertText, datumText, uhrzeitText,
        nameZeigen, anzeigeZu, anzeigeUebernehmen, kandidatenMerken, sammlungAttribut,
        anzahlBereich, reihenFelder, blattFelder, eintraegeMap, eintraegeZu,
        instanzenZu, planKontext, zellenKontext, reihePraefix,
        formatVorlage, ladeDefinitionen, cacheLeeren,
        erweiterungenFehlend: computed(() => erweiterungenFehlend.value > 0),
    }
}
