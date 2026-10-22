<template>
  <BaseWidgetCard label="DSGVO-Compliance" gridSize="medium" :loading :error :isEmpty="false" :isEditing @refresh="aktualisieren" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <!-- MAIL-1b (N3, Kartentreue S5): der Hinweis steht auf der
         Admin-Startseite. Nur System Manager koennen ihn abstellen, deshalb
         sehen nur sie ihn; ohne Auskunft des Servers (Fehler) bleibt er aus
         — kein falsches „nicht eingerichtet“. -->
    <DkHint v-if="mailversandHinweis" variant="warn" role="status" class="dw-mail">
      Mailversand ist noch nicht eingerichtet — ohne ihn können Löschanträge
      nicht freigegeben werden.
      <a href="#/einstellungen/mailversand">Mailversand einrichten</a>
    </DkHint>
    <div class="stat-grid small">
      <div class="stat-tile"><div class="stat-value">{{ data?.gesamt ?? 0 }}</div><div class="stat-label">Gesamt</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.eingewilligt ?? 0 }}</div><div class="stat-label">Eingewilligt</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.ausstehend ?? 0 }}</div><div class="stat-label">Ausstehend</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.abgelehnt ?? 0 }}</div><div class="stat-label">Abgelehnt</div></div>
    </div>
  </BaseWidgetCard>
</template>
<script setup>
/**
 * Kachel „DSGVO-Compliance“ (Widget-Kennung `dsgvo-compliance`).
 *
 * MAIL-1b (N3): Sie traegt seit dieser Karte den Mailversand-Hinweis der
 * Admin-Startseite; `Home.vue` haelt sie fuer System Manager auch dann
 * sichtbar, wenn sie sich ausgeblendet wurde.
 */
import BaseWidgetCard from './BaseWidgetCard.vue'
import DkHint from '../ui/DkHint.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { apiCall } from '../../composables/useApi.js'
import { useSession } from '../../composables/useSession.js'
import { ref, computed, onMounted } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('dsgvo-compliance', props.refreshInterval)
const { istSystemManager } = useSession()

// „eingerichtet: ja/nein“ + „darf_aendern“ — der Server gibt Nicht-System-
// Managern das „darf_aendern“ nicht, deshalb bleibt der Hinweis bei ihnen aus.
const stand = ref(null)
const mailversandHinweis = computed(() =>
  Boolean(stand.value && stand.value.eingerichtet === false && stand.value.darf_aendern === true))

async function standLaden() {
  if (!istSystemManager.value) {
    // Kein Aufruf, kein Fehlerstrom: der Server wuerde ohnehin nur „nein“ sagen.
    stand.value = null
    return
  }
  try {
    // Ein Fehler hier darf die Kachel nicht kippen: dann bleibt der Hinweis aus.
    const antwort = await apiCall('diakronos.diakronos.api.mailversand.mailversand_status')
    stand.value = antwort?.message || antwort
  } catch {
    stand.value = null
  }
}

function aktualisieren() {
  refresh()
  standLaden()
}

onMounted(standLaden)
</script>
<style scoped>
.dw-mail { margin-bottom: var(--sp-3); }
.dw-mail a { color: var(--primary); font-weight: 550; }
</style>
