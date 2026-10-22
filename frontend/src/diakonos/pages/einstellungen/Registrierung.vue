<template>
  <div class="rg-abschnitt">
    <h2>Registrierung</h2>
    <p>Voreinstellungen für neue Registrierungslinks und einen Überblick über die
      vorhandenen Anmeldeformulare. Die Links selbst verwaltest du unter
      „Mitglieder → Anfragen → Links & QR-Codes“.</p>

    <DkHint v-if="laedt" role="status">Einstellungen werden geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <form ref="formular" @submit.prevent="speichernMitFokus">
      <fieldset :disabled="!bedienbar" class="rg-felder">
        <DkCard title="Vorgaben für neue Links">
          <p class="rg-hilfe">Beim Anlegen eines Links sind diese Werte vorbelegt.
            Du kannst sie am einzelnen Link jederzeit ändern.</p>
          <DkField label="Gültigkeitsdauer (Tage)" help="0 = kein Ablaufdatum."
            :error="feldFehler.laufzeit" v-slot="feld">
            <input v-bind="feld" v-model.number="linkLaufzeitTage" class="dk-ui-eingabe"
              type="number" min="0" max="365" />
          </DkField>
          <DkField label="Höchstzahl Anmeldungen" help="0 = unbegrenzt."
            :error="feldFehler.maximum" v-slot="feld">
            <input v-bind="feld" v-model.number="linkMaxAnmeldungen" class="dk-ui-eingabe"
              type="number" min="0" max="100000" />
          </DkField>
          <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
        </DkCard>
      </fieldset>
    </form>
    <p v-if="erfolg" role="status">{{ erfolg }}</p>

    <DkCard title="Anmeldeformulare">
      <p class="rg-hilfe">Formulare bestimmen, welche Felder eine Person beim Anmelden
        ausfüllt. Neue Formulare entstehen in „Mitglieder → Anfragen → Formulare“.</p>
      <DkHint v-if="formulareFehler" variant="err" role="alert">{{ formulareFehler }}</DkHint>
      <p v-else-if="!formulare.length" class="rg-hilfe">Keine Anmeldeformulare vorhanden.</p>
      <ul v-else class="rg-formulare">
        <li v-for="f in formulare" :key="f.name" class="rg-formular">
          <span>{{ f.bezeichnung || f.name }}</span>
          <a href="#/mitglieder/anfragen">Öffnen</a>
        </li>
      </ul>
    </DkCard>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { useGemeinde } from '../../composables/useGemeinde.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'

const { laedt, speichert, geladen, fehler, erfolg, linkLaufzeitTage,
  linkMaxAnmeldungen, bedienbar, laden, linkvorgabenSpeichern } = useGemeinde()

const formular = ref(null)
const feldFehler = ref({})
const formulare = ref([])
const formulareFehler = ref('')

async function speichernMitFokus() {
  feldFehler.value = {}
  if (linkLaufzeitTage.value < 0 || linkLaufzeitTage.value > 365)
    feldFehler.value.laufzeit = 'Bitte 0 bis 365 Tage angeben.'
  if (linkMaxAnmeldungen.value < 0 || linkMaxAnmeldungen.value > 100000)
    feldFehler.value.maximum = 'Bitte 0 bis 100000 angeben.'
  if (Object.keys(feldFehler.value).length) {
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
    return
  }
  await linkvorgabenSpeichern()
}

async function ladeFormulare() {
  formulareFehler.value = ''
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldeformulare', {})
    formulare.value = (res.message || res).formulare || []
  } catch (e) {
    formulareFehler.value = e.message || 'Die Formulare konnten nicht geladen werden.'
  }
}

onMounted(() => { laden(); ladeFormulare() })
</script>

<style scoped>
.rg-abschnitt, .rg-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.rg-abschnitt h2, .rg-abschnitt p { margin: 0; }
.rg-felder { padding: 0; border: 0; margin: 0; }
.rg-felder:disabled { opacity: .65; }
.rg-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.rg-formulare { list-style: none; padding: 0; margin: var(--sp-2) 0 0; display: grid; gap: var(--sp-2); }
.rg-formular { display: flex; justify-content: space-between; gap: var(--sp-3);
  padding-bottom: var(--sp-2); border-bottom: 1px solid var(--line); }
</style>
