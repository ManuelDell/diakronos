<template>
  <!-- ON-4 (H2, Entwurf 11): amber Leiste „… ist noch nicht eingerichtet.“ über
       dem betroffenen Einstellungs-Abschnitt, mit „Einrichten“ auf dieselbe
       Seite (die Felder stehen darunter) bzw. auf `#/einrichtung`.
       Sichtbarkeit und Wortlaut kommen aus `hinweisFuer` (ein Test wacht). -->
  <div
    v-if="sichtbar && hinweis"
    class="dk-einrichtungs-leiste"
    role="status"
    aria-live="polite"
  >
    <span class="dk-einrichtungs-leiste-zeichen" aria-hidden="true">!</span>
    <div class="dk-einrichtungs-leiste-text">
      <p class="dk-einrichtungs-leiste-titel">{{ hinweis.titel }}</p>
      <p v-if="hinweis.text" class="dk-einrichtungs-leiste-satz">{{ hinweis.text }}</p>
      <ul v-if="hinweis.fehlend.length > 1" class="dk-einrichtungs-leiste-fehlend">
        <li v-for="f in hinweis.fehlend" :key="f.schluessel">{{ f.titel }}</li>
      </ul>
    </div>
    <a :href="hinweis.ziel" class="dk-einrichtungs-leiste-knopf">{{ hinweis.zielText }}</a>
  </div>
</template>

<script setup>
/**
 * EinrichtungsLeiste — amber Hinweis am Kopf eines Einstellungs-Abschnitts
 * (ON-4/H2, Entwurf Frame 11).
 *
 * `seite` entscheidet, welcher Punkt gilt (`mailversand`, `gemeinde`,
 * `einrichtung`) — die Zuordnung steht in `composables/einrichtungsHinweise.mjs`
 * (SEITEN_PUNKTE), damit Menü, Leiste und Karte nicht auseinanderlaufen.
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { computed, onMounted, watch } from 'vue'

import {
  hinweisFuer,
  statusLaden,
  statusStand,
} from '../../composables/einrichtungsHinweise.mjs'

const props = defineProps({
  /** mailversand | gemeinde | einrichtung */
  seite: { type: String, required: true },
  /** Admin? (Boot-Objekt oder `true`) — sonst erscheint gar nichts. */
  rollen: { type: [Boolean, Object, Array], default: false },
  heute: { type: Date, default: () => new Date() },
})

const hinweis = computed(() => hinweisFuer(statusStand.value, props.seite, props.rollen, props.heute))
const sichtbar = computed(() => hinweis.value !== null)

function laden() {
  // Nur Admin-Rollen fragen (der Server verweigert sonst ohnehin mit 403).
  if (!props.rollen) return
  statusLaden()
}

onMounted(laden)
watch(() => props.seite, laden)
</script>

<style scoped>
.dk-einrichtungs-leiste {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--pad);
  background: var(--warn-soft);
  border: 1px solid color-mix(in oklch, var(--warn) 28%, transparent);
  border-radius: var(--radius);
}
.dk-einrichtungs-leiste-zeichen {
  display: grid;
  place-items: center;
  flex: none;
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: 50%;
  background: var(--warn);
  color: var(--surface);
  font-size: var(--fs-xs);
  font-weight: var(--fw-h);
  line-height: 1;
}
.dk-einrichtungs-leiste-text { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.dk-einrichtungs-leiste-titel { margin: 0; font-size: var(--fs); font-weight: 600; color: var(--text); }
.dk-einrichtungs-leiste-satz { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.dk-einrichtungs-leiste-fehlend {
  margin: var(--sp-1) 0 0;
  padding-left: var(--sp-4);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-einrichtungs-leiste-knopf {
  flex: none;
  align-self: center;
  padding: var(--sp-1) var(--sp-3);
  border-radius: var(--radius);
  border: 1px solid color-mix(in oklch, var(--warn) 40%, transparent);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}
.dk-einrichtungs-leiste-knopf:hover { background: var(--warn-soft); }
.dk-einrichtungs-leiste-knopf:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
@media (max-width: 720px) {
  .dk-einrichtungs-leiste { flex-wrap: wrap; }
  .dk-einrichtungs-leiste-knopf { width: 100%; text-align: center; }
}
</style>
