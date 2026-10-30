<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader title="Website" sub="Die Gemeinde-Website in Primo bearbeiten." />

    <div class="wb-bereich">
      <DkCard title="Redaktion">
        <p class="wb-text">
          Inhalte der Gemeinde-Website werden in Primo gepflegt. „Primo öffnen“
          meldet dich dort mit deinem Diakronos-Konto an — ein eigenes Passwort
          für die Website brauchst du nicht.
        </p>

        <div class="wb-zustand">
          <DkBadge :variant="zustand().ton">{{ zustand().titel }}</DkBadge>
          <span v-if="details()" class="wb-details">{{ details() }}</span>
        </div>
        <p class="wb-hilfe">{{ zustand().text }}</p>

        <DkHint v-if="hinweis" :variant="hinweis.ton" role="alert">{{ hinweis.text }}</DkHint>

        <!-- D: die Primo-Sitzung endet mit dem Token (nicht verlängerbar). -->
        <p class="wb-hilfe">{{ SITZUNGS_HINWEIS }}</p>

        <div class="wb-aktionen">
          <DkButton variant="primary" :loading="oeffnet" :disabled="!verbunden"
            @click="primoOeffnen">
            Primo öffnen
          </DkButton>
          <DkButton variant="secondary" :loading="laedt" @click="pruefen">
            Verbindung prüfen
          </DkButton>
        </div>

        <p v-if="!verbunden" class="wb-hilfe">
          Solange die Anbindung nicht steht, lässt sich Primo von hier nicht
          öffnen. Die Einrichtung steht in den Einstellungen unter
          „Website (Primo)“ — dort arbeitet der Betrieb die Kurzanleitung ab.
        </p>
      </DkCard>
    </div>
  </div>
</template>

<script setup>
/**
 * WEB-3 (S2) — Seite „Website“ mit dem Einstieg in Primo.
 *
 * Erreichbar nur für System Manager, Administrator und Website-Moderator
 * (Menüeintrag und Router-Guard blenden aus; der Server weist zusätzlich mit
 * 403 ab). Der Knopf „Primo öffnen“ holt die Übergabe-URL per POST (CSRF über
 * `apiCall`) und öffnet sie in einem neuen Tab mit `noopener`.
 *
 * S3 — kein Token im DOM: Die Adresse trägt das Token im Fragment. Sie wird
 * nicht in den Zustand gelegt, nicht angezeigt und nicht geloggt; sie geht
 * direkt an `window.open`. Bei Popup-Blocker bleibt der Tab aus — dann steht
 * hier die Erklärung, nicht das Token.
 */
import { computed, onMounted, ref } from 'vue'
import {
  useWebsite,
  oeffneInNeuemTab,
} from '../composables/useWebsite.js'
import { sitzungsHinweis } from '../composables/website.mjs'
import DkBadge from '../components/ui/DkBadge.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkHint from '../components/ui/DkHint.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'

const { daten, laedt, pruefen, zustand, details, primoOeffnen: holeUndOeffne } = useWebsite()

const oeffnet = ref(false)
/** Klartext-Rückmeldung: `{text, ton}` — nie die Adresse. */
const hinweis = ref(null)

// WEB-1b (D): Default 14400 s = 4 h. Die Oberfläche nennt die Dauer, weil sie
// sich nicht verlängert.
const SITZUNGS_HINWEIS = sitzungsHinweis(14400)

const verbunden = computed(() => daten.value?.status === 'verbunden')

async function primoOeffnen() {
  oeffnet.value = true
  hinweis.value = null
  try {
    const ergebnis = await holeUndOeffne({ oeffne: oeffneInNeuemTab })
    if (!ergebnis.ok) {
      hinweis.value = { text: ergebnis.fehler, ton: 'err' }
      return
    }
    hinweis.value = {
      // Kein „Der Tab ist offen" — das laesst sich mit `noopener` nicht
      // feststellen (window.open liefert dort immer null). Der Nutzer sieht es
      // selbst; der Hinweis nennt nur, was er tun kann, wenn nicht.
      text: 'Die Übergabe an Primo wurde gestartet. Der neue Tab sollte sich öffnen — '
        + 'ist er nicht zu sehen, bitte die Pop-up-Sperre für diese Seite prüfen '
        + 'und erneut versuchen.',
      ton: 'ok',
    }
  } finally {
    oeffnet.value = false
  }
}

onMounted(pruefen)
</script>

<style scoped>
.wb-bereich { display: grid; gap: var(--sp-4); min-width: 0; }
.wb-text, .wb-hilfe { margin: 0; }
.wb-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.wb-zustand {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  /* FIX-6: Umbruch nur nach Breite. */
  min-width: 0;
}
.wb-details { color: var(--muted); font-size: var(--fs-sm); }
.wb-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
</style>
