<template>
  <!-- DSGVO-2b: eigener Bereich im Profil. Erklärt VOR dem Antrag, was
       passiert, stellt den Stand des eigenen Antrags dar und öffnet die
       Bestätigung als Dialog (kein `confirm()`). Rechte/Stand kommen vom
       Server — hier wird nichts über die Person angenommen. -->
  <DkCard title="Meine Daten löschen lassen">
    <template #actions>
      <DkButton v-if="stand !== ANTRAG_STAND.AUSGEFUEHRT" variant="ghost" size="sm"
                :disabled="laedt" @click="$emit('neu-laden')">
        Stand neu laden
      </DkButton>
    </template>

    <div class="la-block">
      <p v-for="(satz, i) in ERKLAERUNG" :key="i" class="la-text">{{ satz }}</p>
      <p class="la-klein">
        Erst danach wird gelöscht, und die Löschung ist endgültig. Überlege es dir
        in Ruhe — bis zum Bestätigen durch die Verwaltung kannst du den Antrag
        jederzeit zurückziehen.
      </p>

      <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <!-- ── Nie beantragt ── -->
      <template v-if="stand === ANTRAG_STAND.OHNE">
        <DkHint variant="warn" role="status">
          Deine Daten sind gespeichert. Ein Antrag ändert noch nichts.
        </DkHint>
        <div class="la-aktionen">
          <DkButton variant="danger" size="sm" :disabled="laedt" @click="oeffneAntrag">
            Löschung beantragen
          </DkButton>
        </div>
      </template>

      <!-- ── Antrag läuft ── -->
      <template v-else-if="stand === ANTRAG_STAND.OFFEN">
        <DkHint variant="info" role="status">
          <strong>Antrag gestellt am {{ daten.beantragt_am }} — wartet auf Bearbeitung.</strong>
          <br />
          Ein Administrator prüft den Antrag. Erst nach seiner Bestätigung bekommst
          du die E-Mail, danach werden deine Daten gelöscht.
        </DkHint>
        <div class="la-aktionen">
          <DkButton variant="secondary" size="sm" :loading="laeuft" :disabled="laedt"
                    @click="$emit('zurueckziehen')">
            Antrag zurückziehen
          </DkButton>
        </div>
      </template>

      <!-- ── Zurückgezogen ── -->
      <template v-else-if="stand === ANTRAG_STAND.ZURUECKGEZOGEN">
        <DkHint variant="info" role="status">
          Dein Antrag<template v-if="daten.beantragt_am"> vom {{ daten.beantragt_am }}</template>
          wurde zurückgezogen<template v-if="daten.zurueckgezogen_am"> (am {{ daten.zurueckgezogen_am }})</template>.
          Deine Daten bleiben gespeichert. Du kannst jederzeit neu beantragen.
        </DkHint>
        <div class="la-aktionen">
          <DkButton variant="danger" size="sm" :disabled="laedt" @click="oeffneAntrag">
            Löschung beantragen
          </DkButton>
        </div>
      </template>

      <!-- ── Abgelehnt (DSGVO-2a) ── -->
      <template v-else-if="stand === ANTRAG_STAND.ABGELEHNT">
        <DkHint variant="warn" role="status">
          Dein Antrag<template v-if="daten.beantragt_am"> vom {{ daten.beantragt_am }}</template>
          wurde am {{ daten.abgelehnt_am || 'unbekannten Datum' }} von der Gemeindeverwaltung
          abgelehnt.
          <template v-if="daten.ablehnung_grund">
            <br /><strong>Begründung:</strong> {{ daten.ablehnung_grund }}
          </template>
          <br />Deine Daten bleiben gespeichert. Du kannst erneut beantragen oder dich bei
          der Datenschutz-Aufsichtsbehörde beschweren.
        </DkHint>
        <div class="la-aktionen">
          <DkButton variant="danger" size="sm" :disabled="laedt" @click="oeffneAntrag">
            Erneut beantragen
          </DkButton>
        </div>
      </template>

      <!-- ── Ausgeführt: nur noch Nachweis ── -->
      <template v-else>
        <DkHint variant="ok" role="status">
          Deine Löschung wurde am {{ daten.anonymisiert_am || 'unbekannten Datum' }} ausgeführt.
          Name und E-Mail-Adresse sind entfernt; in alten Plänen stehst du als
          „Gelöschte Person“.
        </DkHint>
      </template>
    </div>

    <!-- ── Bestätigung: Kontrollkästchen + Wort (kein confirm()) ── -->
    <DkDialog
      :model-value="dialogOffen"
      title="Löschung beantragen"
      size="sm"
      :dismissible="!laeuft"
      :close-on-overlay="false"
      @update:model-value="schliesseDialog"
    >
      <p class="la-text">
        Du beantragst die endgültige Löschung deiner Daten bei der
        Gemeindeverwaltung. Ein Administrator prüft und bestätigt den Antrag.
        Danach bekommst du eine E-Mail, und deine Daten werden vollständig
        entfernt — das lässt sich nicht rückgängig machen.
      </p>
      <p class="la-klein">
        Bis zur Bestätigung bleibt alles gespeichert, und du kannst den Antrag
        unter „Mein Profil“ zurückziehen.
      </p>

      <DkCheckbox v-model="verstanden" class="la-kaestchen">
        Ich habe verstanden, dass meine Daten danach endgültig gelöscht sind, mein
        Name und meine E-Mail-Adresse verschwinden und die Löschung nicht
        rückgängig gemacht werden kann.
      </DkCheckbox>

      <DkField :label="`Zur Bestätigung „${BESTAETIGUNG_WORT}“ eintippen`">
        <input
          v-model="wort"
          class="dk-ui-eingabe"
          autocomplete="off"
          autocapitalize="characters"
          :disabled="laeuft"
          :aria-invalid="wort !== '' && !wortPasst"
        />
      </DkField>

      <DkHint v-if="dialogFehler" variant="err" role="alert">{{ dialogFehler }}</DkHint>

      <template #footer>
        <DkButton variant="ghost" size="sm" :disabled="laeuft" @click="schliesseDialog(false)">
          Abbrechen
        </DkButton>
        <DkButton
          variant="danger"
          size="sm"
          :disabled="!bestaetigungVollstaendig({ kaestchen: verstanden, wort, laeuft })"
          :loading="laeuft"
          @click="abschicken"
        >
          Löschung beantragen
        </DkButton>
      </template>
    </DkDialog>
  </DkCard>
</template>

<script setup>
/**
 * LoeschantragKarte — der Bereich „Meine Daten löschen lassen“ im eigenen
 * Profil (DSGVO-2b).
 *
 * Die Karte ist dumm: sie zeigt den Stand, den der Server geliefert hat, und
 * meldet Absichten nach oben (`beantragen`, `zurueckziehen`, `neu-laden`).
 * Die API-Aufrufe macht die Seite über `composables/useLoeschantrag.js` —
 * dieselbe Aufteilung wie bei `austritt/AustrittDialog.vue`.
 *
 * Kein `confirm()`: die Bestätigung ist ein eigener Dialog mit
 * Kontrollkästchen und abgetipptem Wort (`composables/loeschantrag.mjs`).
 */
import { computed, ref, watch } from 'vue'
import DkCard from '../ui/DkCard.vue'
import DkButton from '../ui/DkButton.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import {
  ANTRAG_STAND, BESTAETIGUNG_WORT, ERKLAERUNG,
  antragsStand, bestaetigungVollstaendig, datumDeutsch,
} from '../../composables/loeschantrag.mjs'

const props = defineProps({
  /** Stand von `datenschutz.mein_loeschantrag` (null = nie beantragt). */
  antrag: { type: Object, default: null },
  laedt: { type: Boolean, default: false },
  laeuft: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
  /** Fehler aus dem Dialog selbst (Server lehnt ab, Sitzung abgelaufen …). */
  dialogFehler: { type: String, default: '' },
  /** Steuerung von außen: Dialog nach einem Fehler wieder öffnen. */
  dialogAnfangsOffen: { type: Boolean, default: false },
})
const emit = defineEmits(['beantragen', 'zurueckziehen', 'neu-laden'])

const stand = computed(() => antragsStand(props.antrag))
const daten = computed(() => ({
  beantragt_am: datumDeutsch(props.antrag?.beantragt_am),
  zurueckgezogen_am: datumDeutsch(props.antrag?.zurueckgezogen_am),
  abgelehnt_am: datumDeutsch(props.antrag?.abgelehnt_am),
  ablehnung_grund: props.antrag?.ablehnung_grund || '',
  anonymisiert_am: datumDeutsch(props.antrag?.anonymisiert_am),
}))

const dialogOffen = ref(false)
const verstanden = ref(false)
const wort = ref('')

const wortPasst = computed(
  () => String(wort.value || '').trim().toUpperCase() === BESTAETIGUNG_WORT,
)

// Jede Öffnung beginnt leer: kein Kästchen und kein Wort aus dem letzten Mal.
watch(dialogOffen, (offen) => {
  if (!offen) return
  verstanden.value = false
  wort.value = ''
})

watch(() => props.dialogAnfangsOffen, (offen) => { if (offen) dialogOffen.value = true })

function oeffneAntrag() {
  dialogOffen.value = true
}

function schliesseDialog(wert = false) {
  if (props.laeuft) return
  if (wert === true) return
  dialogOffen.value = false
}

function abschicken() {
  if (!bestaetigungVollstaendig({
    kaestchen: verstanden.value, wort: wort.value, laeuft: props.laeuft,
  })) return
  emit('beantragen')
}

/*
 * Nach einem GESETZTEN Antrag schließt die Seite den Dialog (`antrag` wechselt
 * auf „offen“). Nach einem Serverfehler bleibt er offen — die Person soll die
 * Meldung sehen und es erneut versuchen können.
 */
watch(() => props.antrag, (neu) => {
  if (neu && antragsStand(neu) !== ANTRAG_STAND.ZURUECKGEZOGEN) {
    if (antragsStand(neu) === ANTRAG_STAND.OFFEN && dialogOffen.value) dialogOffen.value = false
  }
})
</script>

<style scoped>
.la-block { display: flex; flex-direction: column; gap: var(--sp-3); }
.la-text { margin: 0; color: var(--text); line-height: 1.55; font-size: var(--fs); }
.la-klein { margin: 0; color: var(--muted); font-size: var(--fs-sm); line-height: 1.5; }
.la-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-1); }
.la-kaestchen { margin-block: var(--sp-3); align-items: flex-start; }
</style>
