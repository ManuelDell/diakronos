/**
 * A10 (Review 09.11., Punkt 4) — die Marke neben dem Titel in der App-Kopfzeile.
 *
 * Am Handy steht „Kalender“ EINMAL im Kopf: die Kopfzeile der App trägt
 * Menü, Titel, ggf. eine Rolle und die Suche (Entwurf A10). Die Seite hat
 * dafür ihren eigenen Bereichstitel abgegeben (der Bereichskopf darunter
 * trägt nur noch Segmente und Werkzeuge).
 *
 * Damit die ROLLE an derselben Stelle erscheint, meldet sie die Seite hier —
 * eine Quelle (`can_moderate`), kein zweiter Rechte-Prüfweg. Der Wert ist
 * bewusst nur Text: sagte die Seite etwas, erscheint das Abzeichen, sonst
 * nichts (kein leerer Platz, Karte A10). Beim Seitenwechsel räumt die Seite
 * ihren Eintrag in `onUnmounted` ab (`setzeRollenMarke('')`), damit kein
 * Abzeichen auf einer anderen Seite hängen bleibt.
 */
import { ref } from 'vue'

/** Text des Abzeichens an der App-Kopfzeile; `''` = kein Abzeichen. */
export const rollenMarke = ref('')

/**
 * Abzeichen setzen. Nur Text ist erlaubt, höchstens 24 Zeichen — ein
 * Rechte-Flag oder ein Objekt würde hier eine zweite Logik einführen.
 */
export function setzeRollenMarke(text) {
  rollenMarke.value = String(text || '').trim().slice(0, 24)
}

export default { rollenMarke, setzeRollenMarke }
