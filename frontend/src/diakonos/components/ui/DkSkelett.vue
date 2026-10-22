<template>
  <div
    class="dk-ui-skelett"
    :class="[`dk-ui-skelett--${form}`, { 'is-kurz': kurz }]"
    role="status"
    :aria-label="text || 'Inhalt wird geladen'"
  >
    <p v-if="text" class="dk-ui-skelett-text">{{ text }}</p>
    <div class="dk-ui-skelett-zeilen" aria-hidden="true">
      <span v-for="n in zeilen" :key="n" class="dk-ui-skelett-zeile" :style="{ width: breiten[(n - 1) % breiten.length] }" />
    </div>
  </div>
</template>

<script setup>
/**
 * DkSkelett — Platzhalter für Inhalte, die noch geladen werden (OP-UI-19).
 *
 * Befund: Beim Laden blieb die alte Seite stehen, und Platzhalter wie „0“,
 * „Unbekannt“ oder „Ohne Titel“ täuschten bereits geladenen Inhalt vor. Sechs
 * verschiedene Ladeformen (Spinner, „Lade…“, leerer Bildschirm …) machten es
 * zusätzlich uneinheitlich.
 *
 * Regel jetzt (Standard S10): Seitenkopf und Seitenumriss stehen sofort, der
 * Inhalt ist ein ruhiges Skelett ohne Zahlen. Kein Zähler, keine Null, keine
 * erfundenen Namen, solange nichts geladen ist.
 */
import { computed } from 'vue'

const props = defineProps({
  /** Form des Inhalts: 'zeilen' (Liste), 'karten' (Kacheln), 'text' (Absatz), 'tabelle'. */
  form: { type: String, default: 'zeilen' },
  /** Zahl der Platzhalterzeilen. */
  anzahl: { type: Number, default: 4 },
  /** Vorlesehilfe; leer = „Inhalt wird geladen“. */
  text: { type: String, default: '' },
  /** Nur zwei Zeilen (für Bereiche in Karten). */
  kurz: Boolean,
})

const zeilen = computed(() => {
  const n = Number(props.anzahl)
  return Number.isFinite(n) && n > 0 ? Math.min(Math.round(n), 12) : 4
})
// Unregelmässige Breiten sehen nach Text aus statt nach einem Balken.
const breiten = ['92%', '78%', '86%', '64%', '90%', '72%']
</script>

<style scoped>
.dk-ui-skelett {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-ui-skelett-text {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-ui-skelett-zeilen {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-ui-skelett--karten .dk-ui-skelett-zeilen {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--sp-3);
}
.dk-ui-skelett--tabelle .dk-ui-skelett-zeilen { gap: var(--sp-1); }

.dk-ui-skelett-zeile {
  display: block;
  height: 14px;
  border-radius: var(--radius);
  background: var(--surface-2);
  position: relative;
  overflow: hidden;
}
.dk-ui-skelett--karten .dk-ui-skelett-zeile {
  height: 104px;
  width: 100% !important;
}
.dk-ui-skelett--tabelle .dk-ui-skelett-zeile {
  height: 40px;
  border-radius: 0;
  border-bottom: 1px solid var(--divider);
}
.dk-ui-skelett.is-kurz .dk-ui-skelett-zeile { height: 10px; }

/* Ruhiges Pulsieren; bei reduzierter Bewegung steht ein ruhiger Balken. */
.dk-ui-skelett-zeile::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--surface-hover), transparent);
  transform: translateX(-100%);
  animation: dk-skelett-lauf 1.4s ease-in-out infinite;
}
@keyframes dk-skelett-lauf {
  100% { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
  .dk-ui-skelett-zeile::after { animation: none; }
}
</style>
