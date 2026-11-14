/**
 * UI-R6b — „Wo darf ICH anlegen?“ für Beiträge und Wiki: EINE Abfrage.
 *
 * EINE Stelle, die den Server EINMAL fragt (`api.rechte.get_anlegeorte(typ)`,
 * Pfad aus `frappe_compat/inventar/whitelist.json`) — ein Aufruf beim
 * Seitenladen statt einer Welle von POSTs je Gruppe. Der Server antwortet mit
 * der fertigen Liste `{orte: [{gruppe, untergruppe, titel, tiefe, gemeinde}]}`
 * in Anzeigereihenfolge (Gemeinde nur für den Administrator, dann je Gruppe die
 * Gruppe und ihre Untergruppen) — dieselbe Regel, mit der er das Anlegen
 * hernach durchsetzt.
 *
 * Die Oberfläche entscheidet damit nichts selbst: sie zeigt genau die Orte, die
 * der Server nennt. Kein eigenes `isAdmin`, keine eigene Gruppenhierarchie,
 * kein eigener Gemeinde-Text — Titel und Reihenfolge kommen vom Server.
 *
 * `holen()` fragt nur erneut, wenn ausdrücklich danach verlangt wird.
 */
import { ref } from 'vue'
import { apiCall } from './useApi.js'
import { anlegeorteAusAntwort } from './r6Gastzugang.mjs'

/**
 * Aufrufpfad — EINER der `pfade` dieses Eintrags aus `whitelist.json`
 * (`diakronos_app.api.rechte.get_anlegeorte`: `api.get_anlegeorte`,
 * `get_anlegeorte`, `rechte.get_anlegeorte`,
 * `diakronos_app.api.rechte.get_anlegeorte`). Hier steht die kurze Form mit
 * Modulkürzel; ein Pfad mit Paketpräfix (`diakronos.…`) stünde NICHT in der
 * Whitelist und liefe nur über den Rückfall. Geprüft in
 * `tests/r6-methodenpfade.test.mjs`.
 */
const PFAD_ANLEGEORTE = 'rechte.get_anlegeorte'

/**
 * @param {'beitrag'|'wiki'} typ
 * @returns {{ optionen, laden, fehler, holen, zuruecksetzen }}
 *   `optionen` — Orte vom Server; `holen()` fragt ihn (kein Zwischenspeicher:
 *   Rollen können sich in der Sitzung ändern).
 */
export function useAnlegenOrte(typ) {
    const optionen = ref([])
    const laden = ref(false)
    const fehler = ref('')

    /**
     * Fragen und `optionen` füllen. Liefert die Orte.
     * Kein Zwischenspeicher: der Aufrufer entscheidet, wann neu gefragt wird.
     */
    async function holen() {
        laden.value = true
        fehler.value = ''
        try {
            const antwort = await apiCall(PFAD_ANLEGEORTE, { typ })
            optionen.value = anlegeorteAusAntwort(antwort)
        } catch (e) {
            optionen.value = []
            fehler.value = e?.message || 'Die Anlegeorte konnten nicht geladen werden.'
        } finally {
            laden.value = false
        }
        return optionen.value
    }

    function zuruecksetzen() {
        optionen.value = []
        fehler.value = ''
    }

    return { optionen, laden, fehler, holen, zuruecksetzen }
}
