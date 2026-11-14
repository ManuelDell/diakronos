<template>
  <div class="gr-einst">
    <!-- UI-R1: Einstellungen der Gruppe — Teil 1: Rollen.
         Ob die Karte überhaupt erscheint, entscheidet die GRUPPENSEITE über die
         Serverfelder von `get_gruppe_detail`; hier werden keine Rollen mehr
         eigenständig geladen (früher stand `get_gruppenrollen` doppelt).
         Weitere Teile (Module, Freigaben) folgen an dieser Stelle. -->
    <RollenEinstellungen
      :gruppe="gruppe"
      :untergruppe="untergruppe"
      :untergruppen="untergruppen"
      @geaendert="$emit('geaendert')"
    />
  </div>
</template>

<script setup>
/**
 * GruppenEinstellungen — der Bereich „Einstellungen“ auf der Gruppenseite
 * (UI-R1, Teil 1: Rollen).
 *
 * Die Sichtbarkeit hängt allein an den Rechten, die `get_gruppe_detail`
 * mitliefert (der Server entscheidet, nicht die Oberfläche). Die Rollenliste
 * selbst lädt `get_gruppenrollen` — und zwar NUR dort, nicht zusätzlich hier.
 */
import RollenEinstellungen from './RollenEinstellungen.vue'

defineProps({
  /** Kennung der HAUPTgruppe (auf einer Untergruppen-Seite: der Obergruppe). */
  gruppe: { type: String, required: true },
  /** Kennung dieser Untergruppe (leer auf einer Gruppenseite). */
  untergruppe: { type: String, default: '' },
  /** Untergruppen: [{ name, anzeigename }]. */
  untergruppen: { type: Array, default: () => [] },
})
defineEmits(['geaendert'])
</script>
