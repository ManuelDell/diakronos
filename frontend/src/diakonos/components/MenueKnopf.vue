<template>
  <!-- LEISTE-1/2 · DER Menü-Knopf (☰) der App — ein Baustein, damit es auch
       auf Vollbild-Seiten ohne App-Kopfzeile (Nachrichten, Kalender) genau
       EINEN Einstieg in die Schublade gibt (MT-1, Manuel 11.11.: „nur EIN
       Seitenmenü“). Sichtbar nur in der Handy-Lage: die Regel hängt an
       `.dk-app--handy .dk-topbar-symbol.dk-menue-knopf` (index.css). Den
       Zustand der Schublade hält die App-Wurzel; hier nur das Ereignis. -->
  <DkButton
    variant="ghost"
    class="dk-topbar-symbol dk-menue-knopf"
    :aria-label="MENUE_KNOPF_TEXT"
    :title="MENUE_KNOPF_TEXT"
    :aria-expanded="offen === null ? undefined : (offen ? 'true' : 'false')"
    aria-haspopup="dialog"
    @click="$emit('oeffnen')"
  >
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </DkButton>
</template>

<script setup>
import DkButton from './ui/DkButton.vue'
import { MENUE_KNOPF_TEXT } from './handyMenue.mjs'

defineProps({
  /** Ist die Schublade offen? `null` = unbekannt (kein aria-expanded). */
  offen: { type: Boolean, default: null },
})
defineEmits(['oeffnen'])
</script>
