<template>
  <div
    v-if="sichtbar"
    class="pr-hinweis-handy"
    role="status"
    data-test="pr-hinweis-handy"
  >
    <span class="pr-hinweis-handy-symbol" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    </span>
    <p class="pr-hinweis-handy-text">{{ text }}</p>
    <button
      type="button"
      class="dk-btn dk-btn-ghost dk-btn-sm pr-hinweis-handy-zu"
      data-test="pr-hinweis-handy-schliessen"
      aria-label="Hinweis schließen"
      title="Hinweis schließen"
      @click="schliessen"
    >Schließen</button>
  </div>
</template>

<script setup>
/**
 * PLAN-M1 — Hinweisband am Handy: „Pläne bearbeitest du am besten an einem
 * Desktop“ (Befund Manuel 2026-10-23).
 *
 * Eigenschaften:
 *   * `sichtbar` entscheidet der Aufrufer (schmal + Bearbeitungsrecht +
 *     nicht geschlossen, Kern in `composables/handyHinweis.mjs`) — als
 *     zusätzliche Wand sitzt dieselbe Bedingung hier noch einmal, damit ein
 *     alter Cache-Stand den Hinweis nicht bei Betrachtern einblendet.
 *   * Nichts wird gesperrt: das Band ist reine Auskunft, die Seite bleibt
 *     vollständig bedienbar.
 *   * Schließen merkt sich der Aufrufer je Benutzer (localStorage, 30 Tage);
 *     der Baustein meldet die Bedienung über `geschlossen`.
 *   * Darstellung: Hinweisfläche aus den vorhandenen Tokens und dem
 *     `dk-btn-ghost`-Knopf — keine eigenen Farbwerte, deshalb in beiden
 *     Themes (hell/dunkel) lesbar.
 */
import { computed } from 'vue'
import { HANDY_HINWEIS_TEXT, hinweisZeigen } from '../../composables/handyHinweis.mjs'

const props = defineProps({
  /** Ergebnis der Bedingung im Aufrufer (schmal + Recht + nicht geschlossen). */
  sichtbar: { type: Boolean, default: false },
  /** Zweite Wand: ohne Bearbeitungsrecht nie zeigen. */
  darfBearbeiten: { type: Boolean, default: false },
  /** Überschreibbarer Text (Tests/Vorschau); Vorgabe = Kartenwortlaut. */
  text: { type: String, default: HANDY_HINWEIS_TEXT },
})

const emit = defineEmits(['geschlossen'])

const sichtbar = computed(() => hinweisZeigen({
  schmal: true,
  darfBearbeiten: props.darfBearbeiten,
  geschlossen: !props.sichtbar,
}))

function schliessen() {
  emit('geschlossen')
}
</script>

<style scoped>
/* Das Band steht im Inhaltsstrom (kein Overlay): es verdeckt keine Daten,
   es schiebt sie nur nach unten. Nur Tokens, keine festen Farben. */
.pr-hinweis-handy {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--pad);
  margin-bottom: var(--sp-4);
  border: 1px solid color-mix(in oklch, var(--info) 25%, transparent);
  border-radius: var(--radius-lg);
  background: var(--info-soft);
  color: var(--text);
}
.pr-hinweis-handy-symbol {
  display: inline-flex;
  flex: none;
  color: var(--info);
  margin-top: 1px;
}
.pr-hinweis-handy-text {
  flex: 1;
  margin: 0;
  font-size: var(--fs);
  line-height: 1.5;
  color: var(--text);
}
/* Am Handy ist der Knopf die einzige Bedienung des Bandes — deshalb bleibt er
   unter 720 px als Text sichtbar und rutscht unter den Text, statt zu quetschen. */
.pr-hinweis-handy-zu { flex: none; }
@media (max-width: 420px) {
  .pr-hinweis-handy { flex-wrap: wrap; }
  .pr-hinweis-handy-text { flex-basis: calc(100% - 32px); }
  .pr-hinweis-handy-zu { margin-left: auto; }
}
</style>
