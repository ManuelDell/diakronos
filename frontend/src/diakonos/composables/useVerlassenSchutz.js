/**
 * useVerlassenSchutz — Rückfrage bei einem Wechsel MITTEN im Formular
 * (UXD-R29).
 *
 * Befund: Die Bearbeiten-Formulare (Mitglied, Profil, Gruppe) verloren
 * ungespeicherte Eingaben still, wenn der Nutzer über die Seitenleiste oder
 * die Zurück-Taste wegnavigierte. `useFormularSchutz` schützt schon das
 * Schließen EINES Fensters; hier wird dieselbe Prüfung an den ROUTENWECHSEL
 * gehängt.
 *
 * Der Router (`router.js`) führt Guards aus und wartet ein zurückgegebenes
 * Promise ab; `false` bricht den Wechsel ab. Genau das nutzt diese Composable:
 *
 *   const schutz = useFormularSchutz(() => form, () => speichert.value)
 *   useVerlassenSchutz(schutz)
 *
 * Bestätigt der Nutzer „Verwerfen“, ist der Wechsel erlaubt (`true`); wählt er
 * „Weiter bearbeiten“, bleibt die Seite stehen (`false`).
 */
import { onMounted, onBeforeUnmount } from 'vue'
import { onBeforeEach } from '../router.js'

/**
 * @param {{darfSchliessen: () => Promise<boolean>}} schutz  aus useFormularSchutz
 */
export function useVerlassenSchutz(schutz) {
    let abmelden = null
    const guard = async () => {
        if (!schutz || typeof schutz.darfSchliessen !== 'function') return true
        return await schutz.darfSchliessen()
    }
    onMounted(() => {
        abmelden = onBeforeEach(guard)
    })
    onBeforeUnmount(() => {
        if (abmelden) abmelden()
        abmelden = null
    })
}

export default useVerlassenSchutz
