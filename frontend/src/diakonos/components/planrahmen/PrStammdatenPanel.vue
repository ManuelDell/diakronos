<template>
  <!--
    Seitenpanel für die Stammdaten (ST1, Punkt 1+2).

    Warum: Manuels Befund — „Wenn ich die Stammdaten pflege, während ich einen
    Plan erstelle, ist der Stand weg." Statt wegzunavigieren (und den
    Dialog/Entwurf zu verlieren) öffnet dieses Panel die bestehende
    Stammdaten-Komponente als Vollbild-Overlay ÜBER der aktuellen Seite.
    Beim Schließen bleibt die darunterliegende Seite samt Eingaben stehen.

    Rechte kommen vom Server: die Stammdaten-Komponente blendet nur aus, was
    der Server ohnehin verweigert.
  -->
  <Teleport to="body">
    <Transition name="pr-panel">
      <div v-if="modelValue" class="pr-panel-overlay" @click.self="schliessen">
        <div
          ref="fenster"
          class="pr-panel"
          role="dialog"
          aria-modal="true"
          :aria-label="titel"
          data-test="pr-stammdaten-panel"
          tabindex="-1"
          @keydown="tastenFaenger"
        >
          <header class="pr-panel-kopf">
            <div class="pr-panel-kopf-text">
              <strong class="pr-panel-titel">{{ titel }}</strong>
              <span class="pr-panel-sub">{{ untertitel }}</span>
            </div>
            <button
              type="button" class="dk-btn dk-btn-secondary dk-btn-sm"
              data-test="pr-stammdaten-panel-schliessen" @click="schliessen"
            >Fertig — zurück</button>
          </header>
          <div class="pr-panel-koerper" data-test="pr-stammdaten-panel-koerper">
            <!-- Bestehende Stammdaten-Komponente, eingebettet über Props. -->
            <Stammdaten :plantyp="plantyp" :plan="plan" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * PrStammdatenPanel — Vollbild-Overlay, das die bestehende Stammdaten-Seite
 * einbettet (Props plantyp/plan). Kein Weg-Navigieren, kein Verlust der
 * darunterliegenden Eingaben; das Schließen meldet `geschlossen`, damit die
 * aufrufende Seite z. B. den Bedarf neu prüfen kann.
 */
import Stammdaten from '../../pages/planrahmen/Stammdaten.vue'

import { ref, computed } from 'vue'
import { useDialogFokus } from '../../composables/useDialogFokus.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // Genau eines von beiden: Plantyp-Kennung ODER konkrete Plan-ID.
  plantyp: { type: String, default: '' },
  plan: { type: String, default: '' },
  titel: { type: String, default: 'Stammdaten pflegen' },
  untertitel: { type: String, default: 'Personen und Listen ergänzen — dann zurück zum Plan.' },
})
const emit = defineEmits(['update:modelValue', 'geschlossen'])

function schliessen() {
  emit('update:modelValue', false)
  emit('geschlossen')
}

// DES-R6: Fokusfuehrung und Esc-Schliessen wie in DkDialog.
const fenster = ref(null)
const offen = computed(() => props.modelValue)
const { tastenFaenger } = useDialogFokus(offen, fenster, schliessen)
</script>

<style scoped>
.pr-panel-overlay {
  position: fixed; inset: 0; z-index: 1200;
  background: color-mix(in oklch, var(--dk-navy-900) 45%, transparent);
  display: flex; flex-direction: column;
}
.pr-panel {
  display: flex; flex-direction: column;
  width: 100%; height: 100%;
  background: var(--dk-bg, var(--dk-surface));
  overflow: hidden;
}
.pr-panel-kopf {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  padding: 10px 16px;
  border-bottom: 1px solid var(--dk-border);
  background: var(--dk-surface);
  flex-shrink: 0;
  padding-top: calc(10px + env(safe-area-inset-top));
}
.pr-panel-kopf-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.pr-panel-titel { font-size: 0.98rem; color: var(--dk-text); }
.pr-panel-sub { font-size: 0.78rem; color: var(--dk-text-muted); }
.pr-panel-koerper { flex: 1; overflow: auto; }
/* Die eingebettete Seite bringt ihre eigenen Ränder mit — im Panel etwas enger. */
.pr-panel-koerper :deep(.dk-screen) { padding-top: 12px; }
/* Breadcrumbs der eingebetteten Seite verwirren im Panel — ausblenden. */
.pr-panel-koerper :deep(.dk-crumbs) { display: none; }
.pr-panel-koerper :deep(.dk-screen-header) { margin-top: 4px; }
.pr-panel-enter-active, .pr-panel-leave-active { transition: opacity 0.18s ease; }
.pr-panel-enter-from, .pr-panel-leave-to { opacity: 0; }
</style>
