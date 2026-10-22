import { ref } from 'vue'
import { apiCall } from './useApi.js'

/**
 * BACKUP-1 — Datensicherung: Einstellungen, Liste, „Jetzt sichern“, Löschen.
 *
 * EINE Stelle für alle Aufrufe (die Komponente kennt keinen Pfad). Der Server
 * entscheidet über die Rechte: alle vier Endpunkte verweigern einem Nicht-
 * System-Manager mit 403. Die Oberfläche blendet den Abschnitt zusätzlich aus
 * — das ist Komfort, keine Schranke.
 *
 * Es gibt bewusst KEIN Herunterladen und KEIN Wiederherstellen: die Dateien
 * liegen mit Rechten 0600 außerhalb des HTTP-Wurzelbaums, und die
 * Wiederherstellung ist ein Kommandozeilen-Vorgang (Betriebsanleitung).
 */
const API = 'diakronos.diakonos.api.sicherung.'

/** Fehlertext aus der Serverantwort lesen (Feld `message` der Compat-Schicht). */
function meldungAus(fehler, ersatz) {
    const text = typeof fehler?.message === 'string' ? fehler.message.trim() : ''
    if (!text || ['Fehler', 'Unbekannter Fehler', 'API-Fehler'].includes(text)) return ersatz
    return text
}

/** Bytes als lesbare Größe — ohne Nachkommastellen bei KB/MB/GB-Angaben sinnlos. */
export function groesseText(bytes) {
    const wert = Number(bytes) || 0
    if (wert <= 0) return '—'
    if (wert < 1024) return `${wert} Byte`
    const einheiten = ['KB', 'MB', 'GB', 'TB']
    let rest = wert / 1024
    let i = 0
    while (rest >= 1024 && i < einheiten.length - 1) {
        rest /= 1024
        i += 1
    }
    // Unter 10 MB eine Nachkommastelle (eine Sicherung von 0,4 MB soll nicht
    // als "0 MB" erscheinen), darüber reicht die ganze Zahl.
    return `${rest < 10 ? rest.toFixed(1) : Math.round(rest)} ${einheiten[i]}`
}

/** Zeitstempel `JJJJ-MM-TT_HHMMSS` oder ISO als deutsches Datum + Uhrzeit. */
export function zeitpunktText(wert) {
    if (!wert) return '—'
    // Der Name der Sicherung ist der Zeitstempel (siehe Server) — die Liste
    // liefert zusätzlich ein ISO-Feld; beide Wege führen zum selben Text.
    const treffer = String(wert).match(/^(\d{4})-(\d{2})-(\d{2})[T_](\d{2}):?(\d{2})/)
    if (!treffer) return String(wert)
    const [, jahr, monat, tag, stunde, minute] = treffer
    return `${tag}.${monat}.${jahr}, ${stunde}:${minute} Uhr`
}

/** Statuswort und Bedeutung für die Oberfläche (kein Fachjargon). */
export function statusText(status) {
    // `ton` sind die Varianten von DkBadge (neutral | ok | warn | err | info).
    if (status === 'ok') return { wort: 'Fertig', ton: 'ok' }
    if (status === 'fehlgeschlagen') return { wort: 'Fehlgeschlagen', ton: 'err' }
    if (status === 'laeuft') return { wort: 'Läuft gerade', ton: 'info' }
    return { wort: status || 'Unbekannt', ton: '' }
}

export function useSicherung() {
    const laedt = ref(false)
    const speichert = ref(false)
    const sichert = ref(false)
    const geladen = ref(false)
    const fehler = ref('')
    const erfolg = ref('')

    const automatisch = ref(true)
    const uhrzeit = ref('03:00')
    const aufbewahrungTage = ref(30)
    const sicherungen = ref([])
    const ablage = ref({ benutzbar: true, hinweis: '', vorhanden: 0 })
    const letztesErgebnis = ref(null)

    /**
     * Laden. `mitteilungLeeren` ist fuer den Aufruf nach einem Schreibvorgang
     * falsch: sonst waere die Meldung von „Jetzt sichern“ (Erfolg ODER
     * Fehlschlag) schon weg, bevor sie jemand lesen konnte. Zurueckgesetzt
     * wird sie deshalb erst beim naechsten ausdruecklichen Neuladen.
     */
    async function laden({ mitteilungLeeren = true } = {}) {
        laedt.value = true
        if (mitteilungLeeren) {
            fehler.value = ''
            erfolg.value = ''
        }
        let ladeFehler = ''
        try {
            const res = await apiCall(API + 'sicherung_get', {})
            const d = res.message || res
            const e = d.einstellungen || {}
            automatisch.value = e.automatisch !== false
            uhrzeit.value = e.uhrzeit || '03:00'
            aufbewahrungTage.value = Number(e.aufbewahrung_tage ?? 30)
            sicherungen.value = Array.isArray(d.sicherungen) ? d.sicherungen : []
            ablage.value = d.ablage || { benutzbar: true, hinweis: '', vorhanden: 0 }
            geladen.value = true
            return true
        } catch (e) {
            ladeFehler = meldungAus(
                e, 'Die Datensicherung konnte nicht geladen werden.')
            if (!fehler.value) fehler.value = ladeFehler
            return false
        } finally {
            laedt.value = false
        }
    }

    /**
     * Einstellungen speichern. Geprueft wird ZUERST im Browser, damit ein
     * offensichtlicher Tippfehler keine Runde zum Server kostet — die
     * verbindliche Pruefung macht der Server (gleiche Grenzen, eine Quelle
     * fuer den Scheduler).
     */
    async function einstellungenSpeichern() {
        fehler.value = ''
        erfolg.value = ''
        const tage = Number(aufbewahrungTage.value)
        if (!Number.isInteger(tage) || tage < 1) {
            fehler.value = 'Die Aufbewahrung muss mindestens 1 Tag betragen.'
            return false
        }
        if (tage > 3650) {
            fehler.value = 'Die Aufbewahrung darf höchstens 3650 Tage betragen.'
            return false
        }
        if (!/^([01]\d|2[0-3]):([0-5]\d)$/.test(String(uhrzeit.value || '').trim())) {
            fehler.value = 'Bitte die Uhrzeit als HH:MM angeben, zum Beispiel 03:00.'
            return false
        }
        speichert.value = true
        try {
            const res = await apiCall(API + 'sicherung_einstellungen_speichern', {
                automatisch: Boolean(automatisch.value),
                uhrzeit: String(uhrzeit.value).trim(),
                aufbewahrung_tage: tage,
            })
            const d = res.message || res
            const e = d.einstellungen || {}
            if (e.uhrzeit) uhrzeit.value = e.uhrzeit
            if (e.aufbewahrung_tage) aufbewahrungTage.value = e.aufbewahrung_tage
            erfolg.value = 'Einstellungen gespeichert.'
            return true
        } catch (grund) {
            // NICHT `catch (e)` nennen: `fehler` waere dann die Ausnahme und
            // `fehler.value` still wirkungslos — die Meldung erschiene nie.
            fehler.value = meldungAus(
                grund, 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.')
            return false
        } finally {
            speichert.value = false
        }
    }

    /** „Jetzt sichern“ — synchron, das Ergebnis kommt direkt zurück. */
    async function jetztSichern() {
        fehler.value = ''
        erfolg.value = ''
        sichert.value = true
        letztesErgebnis.value = null
        try {
            const res = await apiCall(API + 'sicherung_jetzt', {})
            const d = res.message || res
            letztesErgebnis.value = d
            if (d.ok) {
                erfolg.value = `Sicherung fertig (${groesseText(d.groesse_bytes)}).`
            } else {
                fehler.value = d.meldung || 'Die Sicherung ist fehlgeschlagen.'
            }
            // Die Liste wird auch nach einem Fehlschlag neu geladen: die
            // fehlgeschlagene Zeile gehört sichtbar in die Tabelle. Die
            // Meldung bleibt dabei stehen (sonst wäre sie sofort weg).
            await laden({ mitteilungLeeren: false })
            return Boolean(d.ok)
        } catch (grund) {
            fehler.value = meldungAus(grund, 'Die Sicherung konnte nicht gestartet werden.')
            return false
        } finally {
            sichert.value = false
        }
    }

    /** Eine Sicherung löschen (der Aufrufer fragt vorher nach). */
    async function loeschen(name) {
        fehler.value = ''
        erfolg.value = ''
        try {
            await apiCall(API + 'sicherung_loeschen', { name })
            erfolg.value = 'Sicherung gelöscht.'
            await laden({ mitteilungLeeren: false })
            return true
        } catch (grund) {
            fehler.value = meldungAus(grund, 'Die Sicherung konnte nicht gelöscht werden.')
            return false
        }
    }

    return {
        laedt, speichert, sichert, geladen, fehler, erfolg,
        automatisch, uhrzeit, aufbewahrungTage, sicherungen, ablage, letztesErgebnis,
        laden, einstellungenSpeichern, jetztSichern, loeschen,
    }
}
