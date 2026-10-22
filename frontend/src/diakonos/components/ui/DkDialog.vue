<template>
  <Teleport to="body">
    <Transition name="dk-ui-dialog">
      <div
        v-if="modelValue"
        class="dk-ui-dialog-overlay"
        :class="{ 'dk-ui-dialog-overlay--vorrang': vorrang }"
        :data-dk-dev="dev ? '' : null"
        @mousedown.self="overlaySchliessen"
      >
        <div
          ref="dialogEl"
          class="dk-ui-dialog"
          :class="'dk-ui-dialog--' + size"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
          @keydown="tastenFaenger"
        >
          <header class="dk-ui-dialog-kopf">
            <h3 v-if="title" class="dk-ui-dialog-titel">{{ title }}</h3>
            <button
              v-if="dismissible"
              type="button"
              class="dk-ui-dialog-schliessen"
              aria-label="Schließen"
              @click="schliessen"
            >✕</button>
          </header>
          <div class="dk-ui-dialog-koerper">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="dk-ui-dialog-fuss">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * DkDialog — modaler Dialog (Stil A) mit Fokusfalle, Esc-Schließen und
 * aria-Auszeichnung. Beim Öffnen wandert der Fokus in den Dialog, beim
 * Schließen zurück auf das vorher fokussierte Element.
 *
 * size: sm | md | lg
 * Nur Tokens, keine festen Farben.
 */
import { ref, computed } from 'vue'
import { useDialogFokus } from '../../composables/useDialogFokus.js'
import { useZurueckSchliesst } from '../../composables/useZurueckSchliesst.js'

const props = defineProps({
  modelValue: Boolean,
  // Globale Rückfragen liegen auch über später teleportierten Formularen.
  vorrang: { type: Boolean, default: false },
  beforeClose: { type: Function, default: null },
  dismissible: { type: Boolean, default: true },
  title: { type: String, default: '' },
  size: { type: String, default: 'md' },
  // Formulare dürfen bei einem Fehlklick keine Eingaben verlieren.
  closeOnOverlay: { type: Boolean, default: false },
  // DM3b: markiert den GANZEN Dialog (Overlay/Rahmen/Kopf/Fuß) als Dev-Element.
  // Der Dev-Screenshot schließt dann alles davon aus — ein per Teleport
  // gerenderter Dialog läge sonst mit Abdunkelung und Fuß im Bild.
  dev: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'close'])

const dialogEl = ref(null)
const offen = computed(() => props.modelValue)
const { tastenFaenger } = useDialogFokus(offen, dialogEl, schliessen)

/**
 * Schließen. Liefert `true`, wenn tatsächlich geschlossen wurde, `false`, wenn
 * ein Wächter (`dismissible`, `beforeClose`) abgelehnt hat.
 * P3-4 (Restpunkt 11): Der Rückgabewert entscheidet in `useZurueckSchliesst`,
 * ob der verbrauchte History-Eintrag neu angelegt werden muss.
 */
async function schliessen() {
  if (!props.dismissible) return false
  if (props.beforeClose && !(await props.beforeClose())) return false
  emit('update:modelValue', false)
  emit('close')
  return true
}

function overlaySchliessen() {
  if (props.closeOnOverlay) schliessen()
}

// OP-HANDY-7: Die Zurück-Taste/-Geste schließt den Dialog, statt die Seite zu
// verlassen. Der Modellwert wird über denselben Weg zurückgesetzt wie beim ✕.
useZurueckSchliesst(
  computed(() => props.modelValue),
  () => schliessen(),
)
</script>

<style scoped>
.dk-ui-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
}
.dk-ui-dialog-overlay--vorrang { z-index: calc(var(--z-modal) + 20); }
.dk-ui-dialog {
  width: 100%;
  max-height: calc(100dvh - 32px);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  outline: none;
}
.dk-ui-dialog--sm { max-width: 380px; }
.dk-ui-dialog--md { max-width: 560px; }
.dk-ui-dialog--lg { max-width: 860px; }

.dk-ui-dialog-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--pad) calc(var(--pad) * 1.2);
  border-bottom: 1px solid var(--line);
}
.dk-ui-dialog-titel { font-size: var(--fs-h3); font-weight: var(--fw-h); margin: 0; }
.dk-ui-dialog-schliessen {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: var(--fs);
}
.dk-ui-dialog-schliessen:hover { background: var(--surface-hover); color: var(--text); }
.dk-ui-dialog-koerper { padding: calc(var(--pad) * 1.2); overflow: auto; }
.dk-ui-dialog-fuss {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--pad) calc(var(--pad) * 1.2);
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}

.dk-ui-dialog-enter-active,
.dk-ui-dialog-leave-active { transition: opacity var(--fast) var(--ease); }
.dk-ui-dialog-enter-from,
.dk-ui-dialog-leave-to { opacity: 0; }
</style>
