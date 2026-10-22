<template>
  <section class="dk-ui-card">
    <header v-if="title || $slots.header || $slots.actions" class="dk-ui-card-kopf">
      <slot name="header">
        <h2 v-if="title" class="dk-ui-card-titel">{{ title }}</h2>
      </slot>
      <div v-if="$slots.actions" class="dk-ui-card-aktionen">
        <slot name="actions" />
      </div>
    </header>
    <div class="dk-ui-card-koerper" :class="{ 'is-flach': flach }">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="dk-ui-card-fuss">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script setup>
/**
 * DkCard — ruhige Fläche mit optionalem Kopf, Aktionen und Fuß (Stil A).
 * Nur Tokens, keine festen Farben.
 */
defineProps({
  title: { type: String, default: '' },
  // flach: kein Innenabstand (z. B. für Tabellen, die selbst randlos sind)
  flach: Boolean,
})
</script>

<style scoped>
.dk-ui-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.dk-ui-card-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  flex-wrap: wrap;
  padding: var(--pad) calc(var(--pad) * 1.2);
  border-bottom: 1px solid var(--line);
}
.dk-ui-card-titel { font-size: var(--fs-h3); font-weight: var(--fw-h); margin: 0; }
.dk-ui-card-aktionen { display: flex; align-items: center; gap: var(--sp-2); }
.dk-ui-card-koerper { padding: calc(var(--pad) * 1.2); }
.dk-ui-card-koerper.is-flach { padding: 0; }
.dk-ui-card-fuss {
  padding: var(--pad) calc(var(--pad) * 1.2);
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}
</style>
