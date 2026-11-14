/**
 * R6 — „+ Beitrag“ / „+ Neuer Artikel“ mit Gruppenwahl.
 *
 * EINE Wahrheit für beide Seiten (Beiträge, Wiki):
 *   1. Beim Seitenladen EINMAL fragen, wo diese Person anlegen darf — EIN
 *      Aufruf (`api.rechte.get_anlegeorte(typ)`), der Server antwortet mit der
 *      fertigen Liste `{orte: [...]}` samt Titel und Reihenfolge.
 *   2. `darfAnlegen` steuert den Kopfknopf: ohne eine einzige Möglichkeit
 *      erscheint er gar nicht.
 *   3. Gibt es genau eine Möglichkeit, wird sie ohne Rückfrage genommen.
 *   4. Gibt es mehrere, öffnet sich `GruppeWaehlen`; die Wahl kommt über den
 *      `@waehlen`-Ausgang zurück.
 *
 * Die Oberfläche entscheidet damit nichts selbst — sie zeigt nur, was der
 * Server bejaht.
 */
import { computed, ref } from 'vue'
import { useAnlegenOrte } from './useAnlegenOrte.js'
import { vorauswahl } from './r6Gastzugang.mjs'
import { darfIrgendwoAnlegen } from './r6AnlegenSichtbar.mjs'
import { showToast } from './useToast.js'

const KEIN_RECHT_TEXT = 'Du darfst derzeit keinen Eintrag anlegen. Das dürfen die '
    + 'Hauptverantwortlichen (HV) und Mitverantwortlichen (MV) einer Gruppe bzw. die '
    + 'Gruppenleitung (GL) einer Untergruppe.'

/**
 * @param {'beitrag'|'wiki'} typ
 * @param {object} [optionen]
 * @param {string} [optionen.fest]  Optionswert der Gruppe, die vorausgewählt
 *   werden soll (z. B. die Gruppe der Gruppenseite).
 */
export function useAnlegenMitGruppe(typ, { fest = null } = {}) {
    const { optionen, laden, fehler, holen, zuruecksetzen } = useAnlegenOrte(typ)
    const auswahlOffen = ref(false)
    const auswahlLaden = ref(false)
    const startwert = ref('')

    /** Darf die Person überhaupt irgendwo anlegen? (steuert den Kopfknopf) */
    const darfAnlegen = computed(() => darfIrgendwoAnlegen(optionen.value))

    /**
     * Nur FRAGEN, nichts öffnen: füllt `optionen` und damit `darfAnlegen`.
     *
     * Befund (eigener Beleg-Lauf): `starten()` öffnet bei mehreren
     * Möglichkeiten den Auswahl-Dialog. Wer das beim Seitenladen aufrief, bekam
     * den Dialog ungefragt über die Seite — ein Fehler, den erst das Bild
     * zeigte. Deshalb getrennt: `rechteLaden()` beim Öffnen der Seite,
     * `starten()` erst beim Klick auf den Kopfknopf.
     */
    async function rechteLaden() {
        auswahlLaden.value = true
        try {
            return await holen()
        } finally {
            auswahlLaden.value = false
        }
    }

    /**
     * Startet den Anlege-Weg.
     *
     * UI-R6c: Zurück kommt das GANZE Ortsobjekt des Servers
     * (`{gruppe, untergruppe, titel, tiefe, gemeinde}`), nicht mehr nur
     * `{gruppe, untergruppe}`. Befund: gab es GENAU EINEN Ort, ging der
     * Server-Titel verloren und der Editor zeigte die Kennung („GR-Chor“,
     * „GR-Chor · UG-Blas“) statt „Chor“ — bei mehreren Orten kam der Titel
     * über `GruppeWaehlen`/`artikelAnlegen` an, bei genau einem nicht.
     *
     * @returns {Promise<object|null>} der Ort (mit `titel`), wenn ohne
     *   Rückfrage klar (genau eine Möglichkeit); `null`, wenn der Dialog offen
     *   ist oder nichts erlaubt wurde.
     */
    async function starten({ fest: festJetzt = fest, neuLaden = false } = {}) {
        auswahlLaden.value = true
        try {
            // Erst fragen, DANN den Dialog öffnen: sonst stünde er mit leerer
            // Liste da (und „Weiter“ wäre gesperrt), bis die Antwort kommt.
            // Gefragt wird beim Öffnen der Seite; `neuLaden` holt den Stand
            // ausdrücklich neu (Rollen können sich in der Sitzung ändern).
            const liste = neuLaden || optionen.value.length === 0 ? await holen() : optionen.value
            if (fehler.value) {
                showToast(fehler.value, 'error')
                return null
            }
            if (liste.length === 0) {
                showToast(KEIN_RECHT_TEXT, 'error')
                return null
            }
            startwert.value = vorauswahl(liste, festJetzt)
            if (liste.length === 1) {
                // Das ganze Ortsobjekt: `titel` gehört dazu (Anzeige im Editor).
                return { ...liste[0] }
            }
            auswahlOffen.value = true
            return null
        } finally {
            auswahlLaden.value = false
        }
    }

    /** „Abbrechen“ im Dialog. */
    function schliessen() {
        auswahlOffen.value = false
    }

    return {
        optionen,
        orteLaden: laden,
        darfAnlegen,
        rechteLaden,
        auswahlOffen,
        auswahlLaden,
        startwert,
        starten,
        schliessen,
        zuruecksetzen,
    }
}
