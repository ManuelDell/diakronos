<template>
  <!-- ASVS2-3: das EIGENE Passwort aendern. Bei Anmeldung ueber Authentik
       (OIDC) gibt es kein lokales Passwort — dann nur der Hinweis. -->
  <DkCard title="Passwort">
    <p v-if="oidc" class="pw-hinweis">
      Dein Passwort verwaltest du bei der Anmeldung (Authentik), nicht hier.
    </p>
    <form v-else class="pw-form" novalidate @submit.prevent="absenden">
      <label class="pw-feld">
        <span>Aktuelles Passwort</span>
        <input v-model="aktuell" class="dk-ui-eingabe" type="password"
               autocomplete="current-password" required />
      </label>
      <label class="pw-feld">
        <span>Neues Passwort</span>
        <input v-model="neu" class="dk-ui-eingabe" type="password"
               autocomplete="new-password" minlength="8" required />
      </label>
      <label class="pw-feld">
        <span>Neues Passwort wiederholen</span>
        <input v-model="wiederholung" class="dk-ui-eingabe" type="password"
               autocomplete="new-password" minlength="8" required />
      </label>
      <p class="pw-regel">Mindestens 8 Zeichen. Sehr häufige Passwörter werden abgelehnt.
        Danach meldest du dich neu an — auch auf deinen anderen Geräten.</p>
      <p v-if="fehler" class="pw-fehler" role="alert">{{ fehler }}</p>
      <DkButton type="submit" variant="secondary" size="md" :loading="laeuft"
                :disabled="laeuft || !aktuell || !neu || !wiederholung">
        Passwort ändern
      </DkButton>
    </form>
  </DkCard>
</template>

<script setup>
import { ref, computed } from 'vue'
import DkCard from '../ui/DkCard.vue'
import DkButton from '../ui/DkButton.vue'
import { apiCall } from '../../composables/useApi.js'
import { anmeldeUrl } from '../../../shared/basis.js'
import { pruefeEingabe } from './passwortAendern.mjs'

const oidc = computed(() => window.__DIakonosBOOT?.oidc_aktiv === true)
const aktuell = ref('')
const neu = ref('')
const wiederholung = ref('')
const fehler = ref('')
const laeuft = ref(false)

async function absenden() {
  fehler.value = pruefeEingabe(aktuell.value, neu.value, wiederholung.value)
  if (fehler.value) return
  laeuft.value = true
  try {
    await apiCall('diakronos.diakonos.api.profile.passwort_aendern', {
      aktuelles_passwort: aktuell.value,
      neues_passwort: neu.value,
    })
    // Alle Sitzungen sind beendet (auch diese) — zur Anmeldung mit Hinweis.
    window.location.assign(anmeldeUrl(undefined, 'passwort'))
  } catch (e) {
    fehler.value = e?.message || 'Das Passwort konnte nicht geändert werden.'
  } finally {
    laeuft.value = false
    aktuell.value = ''
  }
}
</script>

<style scoped>
.pw-form { display: grid; gap: var(--sp-3); max-width: 420px; }
.pw-feld { display: grid; gap: var(--sp-1); font-size: var(--fs-sm); }
.pw-regel, .pw-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0; }
.pw-fehler { font-size: var(--fs-sm); color: var(--err); margin: 0; }
</style>
