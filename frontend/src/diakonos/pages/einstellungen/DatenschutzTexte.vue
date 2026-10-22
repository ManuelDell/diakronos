<template>
  <div class="dt-abschnitt">
    <h2>Datenschutz-Texte</h2>
    <p>Die Texte, die Mitglieder und Besucher zu sehen bekommen. Passe sie an die
      Verhältnisse deiner Gemeinde an. Sie ersetzen keine Rechtsberatung.</p>

    <DkHint v-if="laedt" role="status">Texte werden geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <p v-if="geladen" class="dt-fassung">
      <span class="dt-badge">Fassung {{ version }}</span>
      <span>{{ statusText }}</span>
    </p>

    <form @submit.prevent="speichern">
      <fieldset :disabled="!bedienbar" class="dt-felder">
        <DkCard title="Einwilligung">
          <p class="dt-hilfe">Dieser Text wird auf der Anmeldeseite angezeigt und muss
            bestätigt werden, damit die Mitgliedschaft beginnen kann. Gespeichert
            wird er als Beleg genau so, wie er dort stand.</p>
          <DkField label="Einwilligungstext" required v-slot="feld">
            <textarea v-bind="feld" v-model="einwilligung" class="dk-ui-eingabe" rows="5"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Datenschutzerklärung">
          <p class="dt-hilfe">Was mit den Daten geschieht und was nicht. Erscheint
            aufklappbar unter der Einwilligung.</p>
          <DkField label="Datenschutzerklärung" required v-slot="feld">
            <textarea v-bind="feld" v-model="datenschutzerklaerung" class="dk-ui-eingabe" rows="6"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Aufbewahrung">
          <p class="dt-hilfe">Wie lange Daten bleiben und was nach einem Löschwunsch gilt.
            Erscheint aufklappbar auf der Anmeldeseite.</p>
          <DkField label="Hinweis zur Aufbewahrung" required v-slot="feld">
            <textarea v-bind="feld" v-model="aufbewahrung" class="dk-ui-eingabe" rows="4"
              maxlength="20000"></textarea>
          </DkField>
        </DkCard>

        <DkCard title="Veröffentlichung">
          <label class="dt-schalter">
            <input v-model="veroeffentlicht" type="checkbox" />
            <span>Diese Texte neuen Anmeldungen zeigen</span>
          </label>
          <DkHint variant="info">Solange der Haken fehlt, bleibt der bisherige Text
            auf der Anmeldeseite stehen (Entwurf). Erst mit dem Haken wird der
            gepflegte Wortlaut zur geltenden Fassung — und genau er wird als
            Beleg gespeichert.</DkHint>
        </DkCard>

        <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
      </fieldset>
    </form>
    <p v-if="erfolg" role="status">{{ erfolg }}</p>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDatenschutzTexte } from '../../composables/useGemeinde.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'

const { laedt, speichert, geladen, fehler, erfolg, einwilligung,
  datenschutzerklaerung, aufbewahrung, veroeffentlicht, version, statusText,
  bedienbar, laden, speichern } = useDatenschutzTexte()

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
