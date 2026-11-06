<template>
  <div class="web-abschnitt">
    <!-- UX3a: „Website-Baukasten“ statt des alten Werkzeugnamens. -->
    <h2>Website-Baukasten</h2>
    <p>
      Die Gemeinde-Website wird im Website-Baukasten gepflegt — einem eigenen
      System, das Diakronos ansteuert. Die Anbindung ist
      <strong>optional</strong>: ohne sie arbeitet Diakronos vollständig. Hier
      siehst du, ob sie steht, und was für die Einrichtung zu tun ist.
    </p>

    <!-- ── Zustand ───────────────────────────────────────────────────── -->
    <DkCard title="Zustand der Anbindung">
      <div class="web-zustand">
        <DkBadge :variant="zustand().ton">{{ zustand().titel }}</DkBadge>
        <span v-if="details()" class="web-details">{{ details() }}</span>
      </div>
      <p class="web-hilfe">{{ zustand().text }}</p>

      <!-- UX2d3b (Review UX2d3a/B): Laden zeigt den Umriss, keinen Satz. -->
      <DkSkelett v-if="laedt" kurz form="zeilen" :anzahl="2" text="Verbindung wird geprüft" />
      <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <!-- WEB-1b (H): http statt https — Hinweis, keine Sperre. -->
      <DkHint v-if="daten && daten.warnung" variant="warn" role="status">
        {{ daten.warnung }}
      </DkHint>

      <p v-if="daten && daten.url" class="web-hilfe">
        Browser-Adresse der Website: <strong>{{ daten.url }}</strong>
      </p>

      <div class="web-aktionen">
        <DkButton variant="secondary" :loading="laedt" @click="pruefen">
          Verbindung prüfen
        </DkButton>
      </div>
    </DkCard>

    <!-- ── Kurzanleitung ─────────────────────────────────────────────── -->
    <DkCard v-if="!istVerbunden" title="So wird die Website angeschlossen">
      <ol class="web-schritte">
        <li v-for="(s, i) in ANSCHLUSS_SCHRITTE" :key="i">
          <strong>{{ s.titel }}</strong>
          <p class="web-hilfe">{{ s.text }}</p>
        </li>
      </ol>

      <p class="web-hilfe">Diese Werte trägt der Betrieb ein:</p>
      <ul class="web-werte">
        <li v-for="w in BENOETIGTE_WERTE" :key="w"><code>{{ w }}</code></li>
      </ul>

      <DkHint variant="info">
        {{ ANLEITUNG_ORT }}
        Die Einrichtung ist ein Vorgang am Server, nicht in dieser Oberfläche —
        die Werte werden nicht hier gespeichert.
      </DkHint>
    </DkCard>
  </div>
</template>

<script setup>
/**
 * WEB-3 (S1) — Einstellungen-Abschnitt „Website (Primo)“.
 *
 * Zeigt den Zustand aus `website.status` (nicht angeschlossen / nicht
 * erreichbar / verbunden mit Version und Seitenzahl), die https-Warnung des
 * Servers und eine Kurzanleitung zum Anschließen. „Verbindung prüfen“ fragt
 * neu ab.
 *
 * Nur Anzeige: Die Anbindung wird über `settings/.env` eingeschaltet, nicht
 * über diese Seite. Ein Formular hier wäre eine zweite Wahrheit neben der
 * `.env` und würde nach einem Neustart stillschweigend verschwinden.
 */
import { computed, onMounted } from 'vue'
import { useWebsite } from '../../composables/useWebsite.js'
import {
  ANLEITUNG_ORT,
  ANSCHLUSS_SCHRITTE,
  BENOETIGTE_WERTE,
} from '../../composables/website.mjs'
import DkBadge from '../../components/ui/DkBadge.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
// UX2d3b (Review UX2d3a/B): Laden zeigt den Umriss, keinen Satz.
import DkSkelett from '../../components/ui/DkSkelett.vue'

defineProps({ embedded: Boolean })

const { daten, laedt, fehler, pruefen, zustand, details } = useWebsite()

// „Verbunden“ blendet die Anleitung aus — wer sie braucht, sieht sie.
const istVerbunden = computed(() => daten.value?.status === 'verbunden')

onMounted(pruefen)
</script>

<style scoped>
.web-abschnitt { display: grid; gap: var(--sp-4); min-width: 0; }
.web-abschnitt h2, .web-abschnitt p { margin: 0; }
.web-zustand {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  /* FIX-6: Umbruch nur nach Breite — keine Zeiger-Abfrage. */
  min-width: 0;
}
.web-details { color: var(--muted); font-size: var(--fs-sm); }
.web-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.web-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
.web-schritte {
  margin: 0;
  padding-left: var(--sp-4);
  display: grid;
  gap: var(--sp-3);
}
.web-schritte li { min-width: 0; }
.web-schritte p { margin-top: var(--sp-1); }
.web-werte {
  margin: 0;
  padding-left: var(--sp-4);
  color: var(--muted);
  font-size: var(--fs-sm);
}
.web-werte code { color: var(--text); }
</style>
