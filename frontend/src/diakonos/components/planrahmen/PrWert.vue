<template>
  <span class="pr-wert" :class="{ 'pr-wert--leer': istLeer }">
    <template v-if="chips.length">
      <span v-for="(c, i) in chips" :key="i" class="pr-wert-chip">{{ c }}</span>
    </template>
    <template v-else>{{ text }}</template>
  </span>
</template>

<script setup>
/**
 * Generische Wertanzeige eines Eintrags: Mehrfachwerte als Chips,
 * alles andere als Text. Kein Chor-Spezialfall — die Art kommt aus
 * der Feld-Deklaration.
 */
import { computed } from 'vue'
import { wertText, nameZeigen } from '../../composables/usePlanrahmen.js'

const props = defineProps({
  wert: { default: null },
  art: { type: String, default: '' },
})

const WERT_ARTEN = new Set(['person', 'personen', 'eintrag', 'team'])

const roh = computed(() => (Array.isArray(props.wert) ? props.wert : (props.wert === null || props.wert === undefined || props.wert === '' ? [] : [props.wert])))
const chips = computed(() => {
    if (!WERT_ARTEN.has(props.art)) return []
    return roh.value.map((w) => (w && typeof w === 'object' ? (w.titel || w.name || w.kuerzel || '') : nameZeigen(String(w))))
})
const text = computed(() => wertText(props.wert))
const istLeer = computed(() => chips.value.length === 0 && (props.wert === null || props.wert === undefined || props.wert === ''))
</script>

<style scoped>
.pr-wert { display: inline-flex; flex-wrap: wrap; gap: 4px; align-items: baseline; min-width: 0; }
.pr-wert--leer { color: var(--dk-text-subtle); }
.pr-wert-chip {
  display: inline-block; padding: 1px 8px; border-radius: 999px;
  background: var(--dk-surface-2); border: 1px solid var(--dk-border);
  font-size: 0.78rem; color: var(--dk-text); white-space: nowrap;
  max-width: 220px; overflow: hidden; text-overflow: ellipsis;
}
</style>
