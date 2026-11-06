<template>
  <!-- UX3a (Entwurf A2): Reiterleiste des Bereichs „Dienste“.
       Meine Dienste · Dienstpläne · Vorlagen — jeder Reiter hat eine eigene
       Adresse (#/dienste/…), damit ein Reiter teilbar ist und ein Neuladen
       ihn hält. Die Liste kommt aus menue.js (EINE Quelle); sichtbar ist,
       was die Rolle sehen darf („Vorlagen“ nur Administration).
       Der Bereichsrahmen der Personen-Seite (DkBereichsliste) ist hier NICHT
       wiederverwendet: er ist für eine Liste LINKS neben dem Inhalt gebaut.
       Für den Bereich „Dienste“ zeichnet der Entwurf eine Reiterzeile über
       dem Inhalt — siehe BERICHT.md, A2. -->
  <nav v-if="eintraege.length > 1" class="dk-dienste-reiter" :aria-label="ariaLabel">
    <a
      v-for="r in eintraege"
      :key="r.id"
      class="dk-dienste-reiter-punkt"
      :class="{ 'is-aktiv': r.seite === aktiveSeite }"
      :href="r.href"
      :aria-current="r.seite === aktiveSeite ? 'page' : undefined"
      :data-reiter="r.id"
    >{{ r.label }}</a>
  </nav>
</template>

<script setup>
/**
 * DiensteReiter — Reiterzeile für zusammengelegte Bereiche (UX3a).
 *
 * Eigenschaften:
 *   reiter      Liste aus menue.js (DIENSTE_REITER / LIEDER_REITER)
 *   seite       Seitenname der aktuell geöffneten Seite (currentPageName)
 *   darfPlanen  Planungsrecht vom Server (UX3c). `undefined` = noch nicht
 *               geantwortet → es gilt die Administration (kein Aufblitzen
 *               eines falschen Reiters). Die Regel selbst steht in
 *               menue.js::sichtbareReiter — eine Wahrheit für Oberfläche und
 *               Tests.
 *
 * Nur Tokens (tokens.css), keine festen Farben; die Klickfläche folgt der
 * Vorgabe --control-h (bei Finger breiter über die Zeilenhöhe).
 */
import { computed } from 'vue'
import { sichtbareReiter } from '../menue.js'
import { useSession } from '../composables/useSession.js'

const props = defineProps({
  reiter: { type: Array, required: true },
  seite: { type: String, default: '' },
  darfPlanen: { type: Boolean, default: undefined },
  ariaLabel: { type: String, default: 'Bereiche' },
})

const { isAdmin } = useSession()
const eintraege = computed(() => sichtbareReiter(props.reiter, {
  istAdmin: isAdmin.value === true,
  darfPlanen: props.darfPlanen,
}))
const aktiveSeite = computed(() => props.seite)
</script>

<style scoped>
.dk-dienste-reiter {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  border-bottom: var(--rahmen-breite) solid var(--dk-border);
  margin-bottom: var(--sp-4);
}
.dk-dienste-reiter-punkt {
  display: inline-flex;
  align-items: center;
  min-height: var(--control-h);
  padding: 0 var(--sp-3);
  margin-bottom: calc(-1 * var(--rahmen-breite));
  border-bottom: calc(2 * var(--rahmen-breite)) solid transparent;
  color: var(--dk-text-muted);
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  text-decoration: none;
}
.dk-dienste-reiter-punkt:hover { color: var(--dk-text); }
/* Aktiver Reiter: Farbe UND Unterstrich + Gewicht (Farbe nie allein, Ä4). */
.dk-dienste-reiter-punkt.is-aktiv {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: var(--fw-fett);
}
.dk-dienste-reiter-punkt:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 1px;
}
@media (pointer: coarse) {
  .dk-dienste-reiter-punkt { min-height: var(--row-h); }
}
</style>
