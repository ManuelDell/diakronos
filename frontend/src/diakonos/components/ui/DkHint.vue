<template>
  <div class="dk-ui-hint" :class="'dk-ui-hint--' + variant">
    <div class="dk-ui-hint-koerper">
      <slot />
    </div>
    <div v-if="schritte.length" class="dk-ui-hint-schritte">
      <span
        v-for="(s, i) in schritte"
        :key="i"
        class="dk-ui-schritt"
        :class="{ 'is-fertig': i < aktiv, 'is-aktiv': i === aktiv }"
      >
        <i aria-hidden="true">{{ i < aktiv ? '✓' : i + 1 }}</i>{{ s }}
      </span>
    </div>
  </div>
</template>

<script setup>
/**
 * DkHint — Hinweisfläche (Stil A) mit optionaler Schrittfolge.
 * variant: info | akzent | ok | warn | err
 * schritte: Liste von Beschriftungen; aktiv = Index des laufenden Schritts.
 * Nur Tokens, keine festen Farben.
 */
defineProps({
  variant: { type: String, default: 'akzent' },
  schritte: { type: Array, default: () => [] },
  aktiv: { type: Number, default: -1 },
})
</script>

<style scoped>
.dk-ui-hint {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--pad);
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
}
.dk-ui-hint--akzent { background: var(--accent-soft); border-color: color-mix(in oklch, var(--accent) 25%, transparent); }
.dk-ui-hint--info   { background: var(--info-soft);   border-color: color-mix(in oklch, var(--info) 25%, transparent); }
.dk-ui-hint--ok     { background: var(--ok-soft);     border-color: color-mix(in oklch, var(--ok) 25%, transparent); }
.dk-ui-hint--warn   { background: var(--warn-soft);   border-color: color-mix(in oklch, var(--warn) 28%, transparent); }
.dk-ui-hint--err    { background: var(--err-soft);    border-color: color-mix(in oklch, var(--err) 28%, transparent); }
.dk-ui-hint-koerper { font-size: var(--fs); color: var(--text); line-height: 1.5; }
.dk-ui-hint-schritte { display: flex; gap: var(--gap); flex-wrap: wrap; }
.dk-ui-schritt {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-ui-schritt i {
  font-style: normal;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  font-size: var(--fs-xs);
  font-weight: 700;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--muted);
}
.dk-ui-schritt.is-fertig i { background: var(--ok); color: var(--surface); border-color: var(--ok); }
.dk-ui-schritt.is-aktiv { color: var(--text); font-weight: 600; }
.dk-ui-schritt.is-aktiv i { border-color: var(--primary); color: var(--primary); }
</style>
