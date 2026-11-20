<template>
  <!-- CHAT-7b-UI (Karte Punkt 4) — Vorschlags-Systemzeile im Verlauf.
       Der Satz kommt vom Server („X möchte Y hinzufügen“); solange der
       Vorschlag OFFEN ist, stimmen die übrigen Teilnehmenden ab. Am eigenen
       Vorschlag stehen keine Knöpfe. Der Stand (angenommen/abgelehnt/beendet)
       steht ruhig als Text daneben.

       Hier gibt es bewusst KEINE Aktionen von `ChatBlase` (kein Antworten,
       Bearbeiten, Löschen, Melden, keine Reaktionen): die Zeile hat keinen
       Besitz und keinen Text im Datensatz — sie ist ein Hinweis, kein Beitrag. -->
  <li class="dk-chat-system" :data-name="zeile.ident">
    <p class="dk-chat-system-satz">{{ lage.satz }}</p>
    <span v-if="lage.standText" class="dk-chat-system-stand">{{ lage.standText }}</span>
    <span v-if="laeuft" class="dk-chat-system-laeuft" role="status">Wird gesendet …</span>
    <span v-else-if="lage.abstimmbar" class="dk-chat-system-knoepfe">
      <DkButton
        variant="secondary"
        size="sm"
        :disabled="gesperrt"
        @click="$emit('zustimmen', { gespraech: zeile.gespraech, vorschlag: lage.vorschlag })"
      >Zustimmen</DkButton>
      <DkButton
        variant="ghost"
        size="sm"
        :disabled="gesperrt"
        @click="$emit('ablehnen', { gespraech: zeile.gespraech, vorschlag: lage.vorschlag })"
      >Ablehnen</DkButton>
    </span>
    <!-- Fehler zu DIESER Zeile: ruhig, als Status — die anderen Zeilen bleiben
         unberührt. -->
    <span v-if="fehler" class="dk-chat-system-fehler" role="alert">{{ fehler }}</span>
  </li>
</template>

<script setup>
/**
 * ChatVorschlagZeile — die Vorschlags-Systemzeile (CHAT-7b-UI-a, Punkt 4).
 *
 * Was hier steht, entscheidet `vorschlagZeile` (`nachrichtenRunden.mjs`):
 * Satz, Stand, „abstimmbar oder nicht“. Die Komponente zeichnet nur und meldet
 * Klicks (`zustimmen`/`ablehnen`) — gesendet wird in `Nachrichten.vue`
 * (`chat.runde_zustimmen`/`chat.runde_ablehnen`).
 */
import { computed } from 'vue'
import { vorschlagZeile } from '../../composables/nachrichtenRunden.mjs'
import DkButton from '../ui/DkButton.vue'

const props = defineProps({
  /** Die Verlaufszeile (`verlaufsZeile`) mit `system.art = 'runde_vorschlag'`. */
  zeile: { type: Object, required: true },
  /** Läuft gerade eine Antwort zu DIESER Zeile? (sperrt die Knöpfe) */
  laeuft: { type: Boolean, default: false },
  /** Ist die Zeile gerade gesperrt (z. B. Runde verlassen)? */
  gesperrt: { type: Boolean, default: false },
  /** Satz eines Fehlschlags zu dieser Zeile (`''` = keiner). */
  fehler: { type: String, default: '' },
})
defineEmits(['zustimmen', 'ablehnen'])

const lage = computed(() => vorschlagZeile(props.zeile) || { satz: '', standText: '', abstimmbar: false })
</script>

<style scoped>
.dk-chat-system {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  align-self: center;
  max-width: 100%;
  padding: var(--sp-1) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-12);
}
.dk-chat-system-satz { margin: 0; }
.dk-chat-system-stand { color: var(--subtle); }
.dk-chat-system-laeuft { color: var(--subtle); }
.dk-chat-system-knoepfe { display: inline-flex; gap: var(--sp-1); }
.dk-chat-system-fehler { flex-basis: 100%; color: var(--err); }
</style>
