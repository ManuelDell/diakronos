<template>
  <span :class="klassen"><slot /></span>
</template>

<script setup>
/**
 * DkBadge — Status- und Kennzeichen-Chip (Stil A).
 * variant: neutral | ok | warn | err | info | akzent
 * Nur Tokens, keine festen Farben.
 */
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'neutral' },
})
const klassen = computed(() => ['dk-ui-badge', 'dk-ui-badge--' + props.variant])
</script>

<style scoped>
.dk-ui-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border-radius: var(--badge-r);
  font-size: var(--fs-sm);
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.dk-ui-badge--neutral { background: var(--surface-2); color: var(--muted); }
/* DES-R15: Die Status-Schriften erreichten auf ihrer weichen Flaeche nur
   3,96 ("Entwurf"/"Gast") bzw. 4,42:1 ("Mitglied"). Die Tokens --badge-ink-*
   sind je Theme eine Stufe dunkler bzw. heller und halten 4,5:1.
   Das Gold-Abzeichen stand mit 2,34:1 da — es nutzt jetzt die Schriftfarbe
   seiner weichen Flaeche. */
.dk-ui-badge--ok      { background: var(--ok-soft);   color: var(--badge-ink-ok); }
.dk-ui-badge--warn    { background: var(--warn-soft); color: var(--badge-ink-warn); }
.dk-ui-badge--err     { background: var(--err-soft);  color: var(--err); }
.dk-ui-badge--info    { background: var(--info-soft); color: var(--badge-ink-info); }
.dk-ui-badge--akzent  { background: var(--accent-soft); color: var(--badge-ink-warn); }
</style>
