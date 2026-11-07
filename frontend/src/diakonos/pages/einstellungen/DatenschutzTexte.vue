<template>
  <div class="dt-abschnitt">
    <h2>Datenschutz-Texte</h2>
    <p>Die Texte, die Mitglieder und Besucher zu sehen bekommen. Passe sie an die
      Verhältnisse deiner Gemeinde an. Sie ersetzen keine Rechtsberatung.</p>

    <DkSkelett v-if="laedt" form="zeilen" :anzahl="4" text="Texte werden geladen" />
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <p v-if="geladen" class="dt-fassung">
      <span class="dt-badge">Fassung {{ version }}</span>
      <span>{{ statusText }}</span>
    </p>

    <form @submit.prevent="speichernMitStand">
      <fieldset :disabled="!bedienbar" class="dt-felder">
        <DkCard title="Einwilligung">
          <p class="dt-hilfe">Dieser Text wird auf der Anmeldeseite angezeigt und muss
            bestätigt werden, damit die Mitgliedschaft beginnen kann. Gespeichert
            wird er als Beleg genau so, wie er dort stand.</p>
          <DkField label="Einwilligungstext" required anker="einwilligung"
            :wert="einwilligung" @update:wert="einwilligung = $event" v-slot="feld">
            <textarea v-bind="feld.feldProps"
              class="dk-ui-eingabe" rows="5"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Datenschutzerklärung">
          <p class="dt-hilfe">Was mit den Daten geschieht und was nicht. Erscheint
            aufklappbar unter der Einwilligung.</p>
          <DkField label="Datenschutzerklärung" required anker="datenschutzerklaerung"
            :wert="datenschutzerklaerung" @update:wert="datenschutzerklaerung = $event" v-slot="feld">
            <textarea v-bind="feld.feldProps"
              class="dk-ui-eingabe" rows="6"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Aufbewahrung">
          <p class="dt-hilfe">Wie lange Daten bleiben und was nach einem Löschwunsch gilt.
            Erscheint aufklappbar auf der Anmeldeseite.</p>
          <DkField label="Hinweis zur Aufbewahrung" required anker="aufbewahrung"
            :wert="aufbewahrung" @update:wert="aufbewahrung = $event" v-slot="feld">
            <textarea v-bind="feld.feldProps"
              class="dk-ui-eingabe" rows="4"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Veröffentlichung" anker="veroeffentlichung">
          <label class="dt-schalter">
            <input v-model="veroeffentlicht" type="checkbox" />
            <span>Diese Texte neuen Anmeldungen zeigen</span>
          </label>
          <DkHint variant="info">Solange der Haken fehlt, bleibt der bisherige Text
            auf der Anmeldeseite stehen (Entwurf). Erst mit dem Haken wird der
            gepflegte Wortlaut zur geltenden Fassung — und genau er wird als
            Beleg gespeichert.</DkHint>
        </DkCard>

        <DkButton type="submit" variant="primary" :loading="speichert"
          :disabled="!kannSpeichern" :aria-disabled="kannSpeichern ? undefined : 'true'"
          :title="kannSpeichern ? undefined : 'Keine Änderung zum Speichern'">Speichern</DkButton>
      </fieldset>
    </form>
    <DkErfolgsmeldung :text="erfolg" />
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useDatenschutzTexte } from '../../composables/useGemeinde.js'
// UX3h3: „Speichern nur, wenn geändert“ — EINE Regel für alle Abschnitte.
import { useGeaendertStand } from '../../composables/useGeaendert.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
// UX2d3b (Review UX2d3a/B): Laden zeigt den Umriss, keinen Satz.
import DkSkelett from '../../components/ui/DkSkelett.vue'

const { laedt, speichert, geladen, fehler, erfolg, einwilligung,
  datenschutzerklaerung, aufbewahrung, veroeffentlicht, version, statusText,
  bedienbar, laden, speichern } = useDatenschutzTexte()

// ── UX3h3: „Speichern nur, wenn geändert“ ────────────────────────────────
/**
 * Der geladene Stand umfasst AUCH den Veröffentlichungs-Haken: „diesen Text
 * neuen Anmeldungen zeigen“ ist eine Änderung, die gespeichert werden muss.
 */
const stand = useGeaendertStand()
const feldsatz = () => ({
  einwilligung: einwilligung.value,
  datenschutzerklaerung: datenschutzerklaerung.value,
  aufbewahrung: aufbewahrung.value,
  veroeffentlicht: veroeffentlicht.value,
})
const geaendert = stand.geaendert(feldsatz)
const kannSpeichern = computed(() => bedienbar.value && geaendert.value)
watch(geladen, (ist) => { if (ist) stand.merken(feldsatz) })

/**
 * Absenden wie bisher (`@submit.prevent="speichern"`) — nur mit der
 * UX3h3-Nachbereitung: nach erfolgreichem Speichern ist der neue Stand der
 * gespeicherte, der Knopf also wieder gesperrt.
 */
async function speichernMitStand() {
  const ok = await speichern()
  if (ok === false) return false
  stand.merken(feldsatz)
  return true
}

onMounted(laden)
</script>

<style scoped>
.dt-abschnitt, .dt-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.dt-abschnitt h2, .dt-abschnitt p { margin: 0; }
.dt-felder { padding: 0; border: 0; margin: 0; }
.dt-felder:disabled { opacity: .65; }
.dt-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.dt-fassung { display: flex; align-items: center; gap: var(--sp-2);
  color: var(--muted); font-size: var(--fs-sm); }
.dt-badge { background: var(--surface-2); border: 1px solid var(--line);
  border-radius: var(--radius-sm); padding: 2px 8px; color: var(--text); font-weight: 600; }
.dt-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); }
.dt-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
</style>
