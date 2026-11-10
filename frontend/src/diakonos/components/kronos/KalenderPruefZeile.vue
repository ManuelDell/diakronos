<template>
  <!-- A10 (Entwurf „A10 Mobil Kalender”): goldene Statuszeile
       „Zu prüfen (3) · Von Gruppen eingetragen ›“ — ZAHL im goldenen Kreis,
       daneben Titel und Untertitel, rechts der Pfeil. Sie erscheint NUR für
       Moderatoren — ohne Recht gibt es keinen leeren Platz (Karte A10).
       Ziel ist die vorhandene Tafel `#/kalender/pruefen` (UX3d); sie ist
       kein vierter Reiter der Segmentsteuerung. -->
  <a
    v-if="sichtbar"
    class="dk-pruefzeile"
    :href="zeile.ziel"
    :aria-label="`${zeile.text} — Prüfliste öffnen`"
    @click.prevent="$emit('oeffnen')"
  >
    <!-- Zahl im goldenen Kreis (Entwurf A10: 24 px, weiße Zahl). Ohne
         bekannte Zahl bleibt der Kreis leer (kein erfundener Wert). -->
    <span class="dk-pruefzeile-kreis" :class="{ 'ist-leer': zahl === null }" aria-hidden="true">
      <template v-if="zahl !== null">{{ zahl }}</template>
    </span>
    <span class="dk-pruefzeile-texte">
      <span class="dk-pruefzeile-titel">Zu prüfen</span>
      <span class="dk-pruefzeile-unter">Von Gruppen eingetragen</span>
    </span>
    <span class="dk-pruefzeile-pfeil" aria-hidden="true"><DkSymbol name="weiter" :groesse="16" /></span>
  </a>
</template>

<script setup>
/**
 * KalenderPruefZeile — goldene Statuszeile der A10-Ansicht.
 *
 * Sichtbarkeit und Text entscheidet `mobilModeration.moderationsZeile`
 * (reine Funktion, geprüft in `tests/a10-*.test.mjs`). Diese Komponente
 * zeichnet nur.
 */
import { computed } from 'vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { moderationsZeile } from './mobilModeration.mjs'

const props = defineProps({
  /** `can_moderate` aus dem Boot-Objekt (eine Quelle mit UX3d). */
  darfPruefen: { type: Boolean, default: false },
  /** Zahl offener Prüfungen; `null` = unbekannt (dann ohne Zahl). */
  zahl: { type: Number, default: null },
})

defineEmits(['oeffnen'])

const zeile = computed(() => moderationsZeile({
  darfPruefen: props.darfPruefen === true,
  zahl: props.zahl,
}) || { sichtbar: false, text: '', ziel: '' })
const sichtbar = computed(() => zeile.value.sichtbar === true)
</script>

<style scoped>
/* Gold ist Statusfarbe („zu prüfen“) — Fläche weich, Schrift kräftig; der
   Text bleibt auch ohne Farbe lesbar (Prinzip Ä4: Farbe nie alleiniger
   Träger — der Text sagt, worum es geht). */
.dk-pruefzeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: var(--sp-7);
  margin: 0 var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-lg);
  background: var(--warn-soft);
  color: var(--badge-ink-warn);
  text-decoration: none;
}
.dk-pruefzeile:hover { background: color-mix(in srgb, var(--warn-soft) 70%, var(--warn)); }
.dk-pruefzeile:focus-visible { outline: var(--ring-breite) solid var(--focus-ring); outline-offset: var(--sp-1); }
/* Zahl im goldenen Kreis (Entwurf A10: 24 px Durchmesser, weiß auf Gold).
   Der Kreis trägt die Zahl — nicht mehr ein Punkt: die Zahl ist die
   Information, die zum Antippen führt. */
.dk-pruefzeile-kreis {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--sp-5);
  height: var(--sp-5);
  border-radius: var(--badge-r);
  background: var(--warn);
  color: var(--dk-warm-0);
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  font-variant-numeric: var(--fs-tabular);
  line-height: 1;
}
/* Unbekannte Zahl: der Kreis bleibt stehen (die Zeile hätte sonst keinen
   Anker), aber leer und ruhiger — nie eine erfundene 0. */
.dk-pruefzeile-kreis.ist-leer { background: transparent; border: var(--rahmen-breite) solid var(--warn); }
.dk-pruefzeile-texte {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-width: 0;
}
/* Enger Zeilenabstand der zwei Textzeilen — eine typografische Zeilenhöhe,
   kein Abstand (1,2 = Kompaktzeile für 14/12 px). */
.dk-pruefzeile-titel {
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-pruefzeile-unter {
  font-size: var(--fs-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-pruefzeile-pfeil { display: inline-flex; align-items: center; flex: none; }
</style>
