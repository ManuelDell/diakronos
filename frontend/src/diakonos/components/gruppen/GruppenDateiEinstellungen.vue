<template>
  <div class="gde-wurzel">
    <!-- DATEIEN-4, Punkt 3 — die beiden Gruppenschalter der Dateien.

         Geladen wird `dateien.einstellungen(gruppe)` (reine Durchreiche an
         `rechte.verwaltung.gruppeneinstellungen`): `werte` und `darf_aendern`.
         Ist `darf_aendern` falsch, stehen die Schalter GESPERRT da — lesbar,
         aber nicht klickbar. Durchgesetzt wird ohnehin serverseitig
         (`einstellung_setzen` verlangt VERWALTEN an der Gruppe). -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="2" text="Einstellungen werden geladen …" />

    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Datei-Einstellungen nicht geladen"
      :text="fehler"
      :erneut-versuchen="() => laden()"
    />

    <template v-else-if="antwortDa">
      <div class="gde-schalter">
        <DkSchalterZeile
          v-for="s in SCHALTER"
          :key="s.key"
          :model-value="werte[s.key] === true"
          :label="s.label"
          :help="s.help"
          :error="meldungen[s.key] || ''"
          :aria-label="s.label"
          :disabled="!darfAendern || busy === s.key"
          @update:model-value="(wert) => setzen(s.key, wert)"
        />
      </div>
      <p v-if="!darfAendern" class="gde-leise">
        Nur die Leitung dieser Gruppe kann diese Schalter umstellen.
      </p>
    </template>
  </div>
</template>

<script setup>
/**
 * GruppenDateiEinstellungen — die Karte „Dateien“ im Reiter „Einstellungen“
 * der Gruppenseite (DATEIEN-4, Punkt 3).
 *
 * Zwei Schalter aus dem Kern (`rechte.kern.GRUPPENEINSTELLUNGEN`):
 *   · `dateien_hochladen_alle`  — alle Mitglieder dürfen hochladen
 *   · `dateien_anpinnen_alle`   — alle Mitglieder dürfen anpinnen
 *
 * Aufrufe: `dateien.einstellungen(gruppe)` und
 * `dateien.einstellung_setzen(gruppe, schluessel, wert)`. Die Schalter gelten
 * für die Gruppe UND ihre Untergruppen — deshalb steht hier immer die
 * HAUPTgruppe (die Seite übergibt sie als `gruppe`).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { aktionsfehler } from '../../../shared/fehlertexte.js'
import DkSkelett from '../ui/DkSkelett.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkSchalterZeile from '../ui/DkSchalterZeile.vue'
import { PFADE, SCHALTER, einstellungenAus } from './gruppenDateien.mjs'

const props = defineProps({
  /** Kennung der HAUPTgruppe (die Schalter hängen an ihr, nicht an der Untergruppe). */
  gruppe: { type: String, required: true },
})

const emit = defineEmits(['geaendert', 'hinweis'])

const roh = ref(null)
const fehler = ref('')
const laedt = ref(true)
const { skelettSichtbar } = useLadeSkelett(laedt)
/** Laufende Änderung je Schalter (sperrt genau diese Zeile, keine Doppelklicks). */
const busy = ref('')
const meldungen = ref({})

const stand = computed(() => einstellungenAus(roh.value))
const werte = computed(() => stand.value.werte)
const darfAendern = computed(() => stand.value.darfAendern)
const antwortDa = computed(() => roh.value !== null)

const hinweis = computed(() => (darfAendern.value
  ? 'Wer Dateien hochladen und anpinnen darf — zusätzlich zur Leitung immer.'
  : 'Dateien dieser Gruppe: Hochladen und Anpinnen.'))
watch(hinweis, (wert) => emit('hinweis', wert), { immediate: true })

async function laden() {
  if (!props.gruppe) { laedt.value = false; return }
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await apiCall(PFADE.einstellungen, { gruppe: props.gruppe })
    roh.value = antwort
  } catch (e) {
    roh.value = null
    fehler.value = aktionsfehler('laden', e)
  } finally {
    laedt.value = false
  }
}

/**
 * Einen Schalter setzen. Der neue Wert wird ERST gesendet und dann aus der
 * Antwort übernommen — springt der Server ab (403/417), geht der Schalter
 * zurück und die Meldung steht an der Zeile (kein stiller Fehlschlag).
 */
async function setzen(schluessel, wert) {
  if (!darfAendern.value || busy.value) return
  const vorher = werte.value[schluessel] === true
  const neu = wert === true
  if (neu === vorher) return
  busy.value = schluessel
  meldungen.value = { ...meldungen.value, [schluessel]: '' }
  // Sofort anzeigen (der Schalter folgt der Hand), bei Fehler zurück.
  roh.value = { ...(roh.value || {}), werte: { ...(roh.value?.werte || {}), [schluessel]: neu } }
  try {
    const antwort = await apiCall(PFADE.einstellung_setzen, {
      gruppe: props.gruppe,
      schluessel,
      wert: neu,
    })
    if (!antwort || antwort.success === false) {
      throw new Error(antwort?.message || '')
    }
    roh.value = { ...(roh.value || {}), werte: { ...(roh.value?.werte || {}), [schluessel]: antwort.wert === true } }
    emit('geaendert')
  } catch (e) {
    roh.value = { ...(roh.value || {}), werte: { ...(roh.value?.werte || {}), [schluessel]: vorher } }
    meldungen.value = {
      ...meldungen.value,
      [schluessel]: e?.message || aktionsfehler('speichern', e),
    }
  } finally {
    busy.value = ''
  }
}

onMounted(() => laden())
watch(() => props.gruppe, (neu, alt) => {
  if (neu && neu !== alt) laden()
})

defineExpose({ laden })
</script>

<style scoped>
.gde-wurzel { display: flex; flex-direction: column; gap: var(--sp-3); min-width: 0; }
.gde-schalter { display: flex; flex-direction: column; gap: var(--gap); }
.gde-leise { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
</style>
