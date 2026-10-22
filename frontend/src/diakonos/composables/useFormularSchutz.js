import { bestaetigen } from './useBestaetigen.js'

// Vergleich des vollständigen Formularmodells, nicht bloß eines input-Events:
// zurückgeänderte Felder sind wieder sauber; voreingestellte Werte zählen nicht
// als Änderung. Der Grundstand wird nach dem Befüllen ausdrücklich gesetzt.
//
/**
 * Merkt sich den Ausgangsstand (`lesen()`) und fragt nur dann nach, wenn sich
 * seither wirklich etwas geändert hat.
 *
 * `lesen` liefert einen Wert ODER `null`/`undefined`, wenn gerade gar kein
 * Formular offen ist. P3-1d (W1, UXD-R29): Geschlossen heißt „nichts zu
 * verlieren“ — vorher verglich der Wächter `"null"` gegen den zuletzt
 * gemerkten Stand des Formulars und fragte deshalb nach Speichern und nach
 * Abbrechen bei jedem weiteren Seitenwechsel fälschlich „Änderungen
 * verwerfen?“. Die Regel gilt zentral für alle Seiten, die diese Composable
 * benutzen (Mitglied, Profil, Gruppe, Dialoge).
 */
export function useFormularSchutz(lesen, beschaeftigt = () => false, fragen = bestaetigen) {
    let grundstand = JSON.stringify(lesen())
    let pruefung = null
    function merken() { grundstand = JSON.stringify(lesen()) }
    async function darfSchliessen() {
        if (beschaeftigt()) return false
        const jetzt = lesen()
        // Kein offenes Formular -> keine Rückfrage.
        if (jetzt === null || jetzt === undefined) return true
        if (JSON.stringify(jetzt) === grundstand) return true
        if (!pruefung) {
            pruefung = fragen({
                titel: 'Änderungen verwerfen?',
                text: 'Deine Eingaben sind noch nicht gespeichert.',
                abbrechen: 'Weiter bearbeiten', aktion: 'Verwerfen', gefahr: true,
            }).finally(() => { pruefung = null })
        }
        return pruefung
    }
    return { merken, darfSchliessen }
}
