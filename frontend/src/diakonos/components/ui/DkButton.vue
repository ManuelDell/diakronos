<template>
  <!-- UX1e: `as="a"` — ein Weg, der wirklich nur verlinkt (z. B. „Moderation“
       in der Kalender-Kopfzeile), bleibt ein echter Link und wird trotzdem vom
       Knopf-System gestaltet. Alle übrigen Attribute (href, title, aria-*,
       @click) reicht Vue unverändert durch. -->
  <a
    v-if="as === 'a'"
    :class="klassen"
    :aria-label="$attrs['aria-label']"
    :aria-busy="loading || undefined"
    v-bind="$attrs"
  >
    <span v-if="loading" class="dk-ui-spinner" aria-hidden="true"></span>
    <slot name="icon" />
    <span v-if="$slots.default" class="dk-ui-btn-label"><slot /></span>
  </a>
  <button
    v-else
    :type="htmlType"
    :class="klassen"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="dk-ui-spinner" aria-hidden="true"></span>
    <slot name="icon" />
    <span v-if="$slots.default" class="dk-ui-btn-label"><slot /></span>
  </button>
</template>

<script setup>
/**
 * DkButton — einziger Button der Bibliothek (Stil A).
 *
 * variant: primary | secondary | ghost | danger
 * size:    sm | md
 * as:      'button' | 'a'  (als <a> für Hash-Links statt Router)
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'secondary' },
  size: { type: String, default: 'md' },
  type: { type: String, default: 'button' },
  disabled: Boolean,
  loading: Boolean,
  block: Boolean,
  /** 'button' (Vorgabe) oder 'a' — ein Element, das nur verlinkt. */
  as: { type: String, default: 'button' },
})
const htmlType = computed(() => props.type)

const klassen = computed(() => [
  'dk-ui-btn',
  'dk-ui-btn--' + props.variant,
  'dk-ui-btn--' + props.size,
  { 'dk-ui-btn--block': props.block, 'is-loading': props.loading },
])
</script>

<style scoped>
.dk-ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: var(--filter-h);
  padding: 0 14px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font: inherit;
  font-size: var(--fs);
  font-weight: 550;
  line-height: 1;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  transition: background var(--fast), color var(--fast),
    border-color var(--fast), transform var(--fast);
}
.dk-ui-btn:active { transform: translateY(1px); }
.dk-ui-btn:disabled,
.dk-ui-btn.is-loading { opacity: .55; cursor: default; transform: none; }
.dk-ui-btn:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 1px;
}
.dk-ui-btn--block { width: 100%; }
/* Icons stehen neben dem Text, nie darüber (globales svg{display:block}).
   Der Standard-Slot ist flex, damit ein Icon im Slot (z.B. <Icon/> Text) genauso
   wie im #icon-Slot neben dem Text sitzt; mehrzeilige Beschriftungen brechen um. */
.dk-ui-btn-label { display: inline-flex; align-items: center; justify-content: center; gap: 7px; flex-wrap: wrap; }
.dk-ui-btn :deep(svg) { flex: none; }

/* md */
/* FIX-3: Höhe aus demselben Token wie Suchfeld (.dk-search-bar) und
   Filterchip (.dk-ui-chip) — in einer Filterzeile stehen alle gleich hoch.
   --filter-h ist heute --control-h; eine Quelle bleibt es trotzdem. */
.dk-ui-btn--md { height: var(--filter-h); padding: 0 14px; }
/* sm */
.dk-ui-btn--sm { height: 28px; padding: 0 10px; font-size: var(--fs-sm); }

/* primary */
.dk-ui-btn--primary {
  background: var(--primary);
  color: var(--primary-ink);
  border-color: var(--primary);
}
.dk-ui-btn--primary:hover:not(:disabled) { background: var(--primary-hover); }

/* secondary */
.dk-ui-btn--secondary {
  background: var(--surface);
  color: var(--text);
  border-color: var(--line);
}
.dk-ui-btn--secondary:hover:not(:disabled) {
  background: var(--surface-hover);
  border-color: var(--line-strong);
}

/* ghost */
.dk-ui-btn--ghost {
  background: transparent;
  color: var(--muted);
}
.dk-ui-btn--ghost:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
}

/* danger */
.dk-ui-btn--danger {
  background: var(--err);
  color: var(--primary-ink);
  border-color: var(--err);
}
.dk-ui-btn--danger:hover:not(:disabled) {
  background: color-mix(in oklch, var(--err) 85%, black);
}

/* DEV-4: Im Dunkelmodus war die Schrift der Primär- und Gefahrenknöpfe
   `--primary-ink` = navy-900 (dunkelblau) auf WEISSER Fläche — der Knopf
   wirkte wie ein leerer Block mit unlesbarer Beschriftung (Seiten „Meine
   Dienste“, „Ressourcen“).
   DEV-4b (Review): Die Korrektur sah eine eigene Dunkelmodus-Regel vor, die
   `color: var(--dk-navy-900)` noch einmal setzte — `--primary-ink` zeigt im
   Dunkelmodus aber bereits auf `--dk-navy-900` (tokens.css), die Regel war
   wirkungslos und ist entfernt. */

.dk-ui-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: dk-ui-spin .7s linear infinite;
}
@keyframes dk-ui-spin { to { transform: rotate(360deg); } }
</style>
