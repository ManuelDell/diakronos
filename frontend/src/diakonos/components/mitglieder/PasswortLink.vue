<template>
  <div class="pw-link">
    <DkHint variant="info">Gib diesen Link nur an die betreffende Person weiter. Er gilt 7 Tage und nur einmal. Es wird keine E-Mail versendet.</DkHint>
    <RegLinkTeilen :link="daten.link" bezeichnung="Persönlicher Passwort-Link" vertraulich />
    <p>Gültig bis {{ ablauf }}. Ein neu erzeugter Link macht den vorherigen ungültig.</p>
    <DkButton variant="secondary" size="sm" @click="textKopieren">Textvorlage kopieren</DkButton>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkHint from '../ui/DkHint.vue'
import RegLinkTeilen from '../registrierung/RegLinkTeilen.vue'
import { showToast } from '../../composables/useToast.js'

const props = defineProps({ daten: { type: Object, required: true }, name: { type: String, default: '' } })
const ablauf = computed(() => new Date(props.daten.gueltig_bis).toLocaleString('de-DE'))
async function textKopieren() {
  const url = new URL(props.daten.link, window.location.origin).href
  try {
    await navigator.clipboard.writeText(`Hallo${props.name ? ' ' + props.name : ''}, hier legst du dein Passwort für Diakronos fest: ${url}\nDer Link gilt bis ${ablauf.value} und nur einmal. Bitte nicht an andere weitergeben.`)
    showToast('Textvorlage kopiert', 'success')
  } catch {
    showToast('Kopieren nicht möglich — bitte den Link von Hand auswählen.', 'warning')
  }
}
</script>

<style scoped>
.pw-link { display: flex; flex-direction: column; gap: var(--sp-3); min-width: 0; }
.pw-link p { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
</style>
