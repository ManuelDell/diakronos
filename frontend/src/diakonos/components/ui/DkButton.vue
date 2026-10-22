<template>
  <button
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
  height: var(--control-h);
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
.dk-ui-btn--md { height: var(--control-h); padding: 0 14px; }
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
