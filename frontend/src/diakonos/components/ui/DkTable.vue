<template>
  <div class="dk-ui-table-wrap">
    <table class="dk-ui-table">
      <thead v-if="spalten.length">
        <tr>
          <th v-for="s in spalten" :key="s.key" :style="s.width ? { width: s.width } : null"
              :class="{ 'is-num': s.numeric }">{{ s.label }}</th>
        </tr>
      </thead>
      <tbody>
        <slot />
      </tbody>
    </table>
    <DkEmpty v-if="leer" :title="leerTitel" :text="leerText">
      <template v-if="$slots.leer" #aktion><slot name="leer" /></template>
    </DkEmpty>
  </div>
</template>

<script setup>
/**
 * DkTable — Tabelle (Stil A) mit Kopf, Zeilen, leerem Zustand und
 * waagerechtem Scrollen. Zeilen kommen über den Standard-Slot
 * (<tr><td>…</td></tr>). Spalten definieren die Kopfzeile.
 *
 * spalten: [{ key, label, width?, numeric? }]
 * Nur Tokens, keine festen Farben (waagerechtes Scrollen ist echte
 * Funktionalität und bleibt erlaubt).
 */
import DkEmpty from './DkEmpty.vue'

defineProps({
  spalten: { type: Array, default: () => [] },
  leer: Boolean,
  leerTitel: { type: String, default: 'Keine Einträge' },
  leerText: { type: String, default: '' },
})
</script>

<style scoped>
.dk-ui-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.dk-ui-table {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
}
.dk-ui-table thead th {
  text-align: left;
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--subtle);
  padding: 10px calc(var(--pad) * 1.2);
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.dk-ui-table thead th.is-num { text-align: right; }
.dk-ui-table tbody :deep(td) {
  height: var(--row-h);
  padding: 0 calc(var(--pad) * 1.2);
  border-top: 1px solid var(--line);
  vertical-align: middle;
  color: var(--text);
}
.dk-ui-table tbody :deep(tr:first-child td) { border-top: none; }
.dk-ui-table tbody :deep(tr:hover td) { background: var(--surface-hover); }
</style>
