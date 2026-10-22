import { ref } from 'vue'
import { apiCall } from './useApi.js'

/**
 * MAIL-1 — Mailversand: Einstellungen lesen, speichern, Testmail senden.
 *
 * EINE Stelle für alle Aufrufe (die Komponente kennt keinen Pfad). Der Server
 * entscheidet über die Rechte: alle Endpunkte verweigern einem
 * Nicht-System-Manager mit 403. Die Oberfläche blendet den Abschnitt
 * zusätzlich aus (Komfort, keine Schranke).
 *
 * Das Passwort kommt NIE vom Server zurück — nur `passwortGesetzt`
 * (ja/nein). Deshalb ist `passwort` im Formular immer leer: wer nichts
 * eintippt, lässt das hinterlegte Passwort unverändert.
 */
const API = 'diakronos.diakronos.api.mailversand.'

/** Fehlertext aus der Serverantwort lesen (Feld `message` der Compat-Schicht). */
function meldungAus(fehler, ersatz) {
    const text = typeof fehler?.message === 'string' ? fehler.message.trim() : ''
    if (!text || ['Fehler', 'Unbekannter Fehler', 'API-Fehler'].includes(text)) return ersatz
    return text
}

/** Die drei Verschlüsselungsarten — Wortlaut wie in der Oberfläche. */
export const SICHERHEIT_ARTEN = [
    {
        wert: 'starttls',
        label: 'STARTTLS (empfohlen)',
        port: 587,
        help: 'Der Server verschlüsselt die Verbindung nach dem Verbinden. Meist Port 587.',
    },
    {
        wert: 'ssl',
        label: 'SSL/TLS',
        port: 465,
        help: 'Die Verbindung ist von Anfang an verschlüsselt. Meist Port 465.',
    },
    {
        wert: 'keine',
        label: 'Keine Verschlüsselung',
        port: 25,
        help: 'Nur ohne Anmeldung möglich. E-Mails mit Personendaten gehen dann '
            + 'unverschlüsselt über das Netz — nur in einem abgeschotteten Netz vertretbar.',
    },
]

/** Ein leeres Formular (noch nichts eingerichtet). */
export function leeresFormular() {
    return {
        host: '',
        port: 587,
        sicherheit: 'starttls',
        benutzername: '',
        absender: '',
        absenderName: '',
        timeout: 15,
    }
}

export function useMailversand() {
    const laedt = ref(false)
    const speichert = ref(false)
    const testet = ref(false)
    const geladen = ref(false)
    const fehler = ref('')
    const erfolg = ref('')
    const testFehler = ref('')
    const testErfolg = ref('')

    const form = ref(leeresFormular())
    const passwort = ref('')
    const passwortGesetzt = ref(false)
    const eingerichtet = ref(false)
    const geaendert = ref('')
    const meineAdresse = ref('')

    function uebernehmen(einstellungen) {
        const e = einstellungen || {}
        form.value = {
            host: e.host || '',
            port: Number(e.port ?? 587),
            sicherheit: e.sicherheit || 'starttls',
            benutzername: e.benutzername || '',
            absender: e.absender || '',
            absenderName: e.absender_name || '',
            timeout: Number(e.timeout ?? 15),
        }
        passwortGesetzt.value = e.passwort_gesetzt === true
        eingerichtet.value = e.eingerichtet === true
        geaendert.value = e.geaendert || ''
    }

    async function laden({ mitteilungLeeren = true } = {}) {
        laedt.value = true
        if (mitteilungLeeren) {
            fehler.value = ''
            erfolg.value = ''
        }
        try {
            const res = await apiCall(API + 'mailversand_get', {})
            const d = res.message || res
            uebernehmen(d.einstellungen)
            meineAdresse.value = d.meine_adresse || ''
            passwort.value = ''
            geladen.value = true
            return true
        } catch (grund) {
            // NICHT `catch (e)` nennen: `fehler` waere dann die Ausnahme.
            fehler.value = meldungAus(
                grund, 'Der Mailversand konnte nicht geladen werden.')
            return false
        } finally {
            laedt.value = false
        }
    }

    /**
     * Prüfung im Browser VOR dem Absenden — dieselben Grenzen wie der Server
     * (der entscheidet verbindlich). Spart eine Runde und zeigt den Fehler am
     * Feld statt am Seitenende.
     */
    function pruefeFormular({ alsTest = false } = {}) {
        const f = form.value
        if (!String(f.host || '').trim()) return 'Bitte den Namen des Mailservers angeben.'
        if (!/^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$/.test(String(f.host).trim())) {
            return 'Der Mailserver ist ein Name wie mail.example.org — ohne http:// und ohne Schrägstrich.'
        }
        const port = Number(f.port)
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            return 'Bitte den Port als Zahl angeben (meist 587).'
        }
        if (!String(f.absender || '').includes('@')) {
            return 'Bitte die Absenderadresse angeben.'
        }
        if (f.sicherheit === 'keine' && String(f.benutzername || '').trim()) {
            return 'Ohne Verschlüsselung geht der Mailversand nur ohne Anmeldung.'
        }
        if (f.sicherheit !== 'keine' && String(f.benutzername || '').trim()
            && !passwort.value && !passwortGesetzt.value && !passwortEntfernen.value) {
            return 'Für die Anmeldung fehlt das Passwort.'
        }
        if (!alsTest) {
            const t = Number(f.timeout)
            if (!Number.isInteger(t) || t < 3 || t > 120) {
                return 'Das Zeitlimit muss zwischen 3 und 120 Sekunden liegen.'
            }
        }
        return ''
    }

    /**
     * Felder, die der Server erwartet (snake_case).
     *
     * `passwort`/`passwort_entfernen` gehoeren bewusst NICHT hierher: der
     * Speicherpfad setzt `passwort` selbst (sonst Stale-Wert nach dem Laden),
     * und `passwort_entfernen` gilt nur fuer die eine bestaetigte Aktion.
     */
    function alsRumpf() {
        const f = form.value
        return {
            host: String(f.host).trim(),
            port: Number(f.port),
            sicherheit: f.sicherheit,
            benutzername: String(f.benutzername || '').trim(),
            absender: String(f.absender || '').trim(),
            absender_name: String(f.absenderName || '').trim(),
            timeout: Number(f.timeout),
        }
    }

    async function speichern() {
        fehler.value = ''
        erfolg.value = ''
        testFehler.value = ''
        testErfolg.value = ''
        const prüfung = pruefeFormular()
        if (prüfung) {
            fehler.value = prüfung
            return false
        }
        speichert.value = true
        try {
            const res = await apiCall(API + 'mailversand_speichern',
                { ...alsRumpf(), passwort: passwort.value })
            const d = res.message || res
            uebernehmen(d.einstellungen)
            // Das Passwort bleibt nie im Formular stehen (es kam nie zurück).
            passwort.value = ''
            erfolg.value = 'Einstellungen gespeichert.'
            return true
        } catch (grund) {
            fehler.value = meldungAus(
                grund, 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.')
            return false
        } finally {
            speichert.value = false
        }
    }

    /**
     * Testmail an die Adresse des angemeldeten System Managers. Geprüft werden
     * die EINGEGEBENEN Werte (proben vor dem Speichern) — ein leeres
     * Passwortfeld nimmt das gespeicherte.
     */
    async function testmail() {
        testFehler.value = ''
        testErfolg.value = ''
        fehler.value = ''
        erfolg.value = ''
        const prüfung = pruefeFormular({ alsTest: true })
        if (prüfung) {
            testFehler.value = prüfung
            return false
        }
        testet.value = true
        try {
            const res = await apiCall(API + 'mailversand_testmail',
                { ...alsRumpf(), passwort: passwort.value })
            const d = res.message || res
            testErfolg.value = `Testmail ist an ${d.an} unterwegs. Bitte den Posteingang prüfen.`
            return true
        } catch (grund) {
            testFehler.value = meldungAus(
                grund, 'Die Testmail konnte nicht verschickt werden.')
            return false
        } finally {
            testet.value = false
        }
    }

    /**
     * MAIL-1b (N4): „Gespeichertes Passwort entfernen“.
     *
     * Die API kennt `passwort_entfernen` seit MAIL-1, die Oberflaeche bot es
     * nicht an — damit war der Wechsel auf „keine Verschlüsselung“ oder einen
     * Server ohne Anmeldung nicht bedienbar (der Server verlangt dann
     * ausdruecklich, das Passwort zu entfernen).
     *
     * Kein `confirm()`: der Aufrufer oeffnet `passwortEntfernen` (eigener
     * Dialog) und ruft danach `passwortEntfernenBestaetigen`.
     */
    const passwortEntfernen = ref(false)

    function passwortEntfernenOeffnen() {
        passwortEntfernen.value = true
    }

    function passwortEntfernenAbbrechen() {
        passwortEntfernen.value = false
    }

    async function passwortEntfernenBestaetigen() {
        fehler.value = ''
        erfolg.value = ''
        speichert.value = true
        try {
            // Dieselben Felder wie beim Speichern: erst das Formular pruefen,
            // dann den Server entscheiden lassen.
            const prüfung = pruefeFormular()
            if (prüfung) {
                fehler.value = prüfung
                speichert.value = false
                return false
            }
            // Derselbe Endpunkt wie Speichern: kein vierter Weg, dieselbe
            // Pruefung, derselbe Audit-Eintrag.
            //
            // `passwort_entfernen` geloescht, wenn ein NEUES Passwort eingetippt
            // ist: der Server lehnt die Kombination zu Recht ab („Für die
            // Anmeldung fehlt das Passwort“), und ein eingetipptes Passwort zu
            // loeschen waere die falsche Antwort (Befund aus der Abnahme).
            let rumpf = { ...alsRumpf(), passwort: passwort.value, passwort_entfernen: true }
            if (passwort.value) {
                rumpf.passwort_entfernen = false
            }
            const res = await apiCall(API + 'mailversand_speichern', rumpf)
            const d = res.message || res
            uebernehmen(d.einstellungen)
            passwort.value = ''
            passwortEntfernen.value = false
            erfolg.value = d.einstellungen?.passwort_gesetzt
                ? 'Das neue Passwort wurde gespeichert. Das alte ist damit ersetzt.'
                : 'Das gespeicherte Passwort wurde entfernt. '
                    + 'Ohne Passwort meldet sich Diakronos nicht am Mailserver an.'
            return true
        } catch (grund) {
            passwortEntfernen.value = false
            fehler.value = meldungAus(
                grund, 'Das Passwort konnte nicht entfernt werden.')
            return false
        } finally {
            speichert.value = false
        }
    }

    return {
        laedt, speichert, testet, geladen, fehler, erfolg, testFehler, testErfolg,
        form, passwort, passwortGesetzt, eingerichtet, geaendert, meineAdresse,
        passwortEntfernen,
        laden, speichern, testmail, pruefeFormular, leeresFormular,
        passwortEntfernenOeffnen, passwortEntfernenAbbrechen,
        passwortEntfernenBestaetigen,
    }
}
