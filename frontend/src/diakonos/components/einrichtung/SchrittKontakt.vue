<template>
  <!-- ON-3 (W2, Schritt 2 „Kontakt“, Entwurf 05): Anschrift, Erreichbarkeit und
       die Zeitzone. Die Zeitzone ist NUR ANZEIGE — sie steht in der
       Betriebseinstellung (CALENDAR_TIMEZONE) und ist hier kein Eingabefeld
       (ON2-VERTRAG Abschnitt 1). -->
  <section class="schritt">
    <h1 class="schritt-titel">Kontakt</h1>
    <p class="schritt-unterzeile">Anschrift und Erreichbarkeit der Gemeinde – die Zeitzone gilt überall.</p>

    <DkField label="Straße und Hausnummer" :error="fehler.strasse">
      <template #default="{ id, ariaDescribedby, ariaInvalid }">
        <input
          :id="id"
          class="dk-ui-eingabe dk-ui-eingabe--feld"
          type="text"
          maxlength="120"
          autocomplete="street-address"
          placeholder="z. B. Kirchplatz 1"
          :value="entwurf.strasse"
          :aria-describedby="ariaDescribedby"
          :aria-invalid="ariaInvalid || undefined"
          @input="$emit('feld', { feld: 'strasse', wert: $event.target.value })"
        />
      </template>
    </DkField>

    <div class="schritt-raster">
      <DkField label="PLZ" :error="fehler.plz">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            class="dk-ui-eingabe dk-ui-eingabe--feld"
            type="text"
            inputmode="numeric"
            maxlength="10"
            autocomplete="postal-code"
            placeholder="z. B. 12345"
            :value="entwurf.plz"
            :aria-describedby="ariaDescribedby"
            :aria-invalid="ariaInvalid || undefined"
            @input="$emit('feld', { feld: 'plz', wert: $event.target.value })"
          />
        </template>
      </DkField>
      <DkField label="Ort" :error="fehler.ort">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            class="dk-ui-eingabe dk-ui-eingabe--feld"
            type="text"
            maxlength="120"
            autocomplete="address-level2"
            placeholder="z. B. Musterstadt"
            :value="entwurf.ort"
            :aria-describedby="ariaDescribedby"
            :aria-invalid="ariaInvalid || undefined"
            @input="$emit('feld', { feld: 'ort', wert: $event.target.value })"
          />
        </template>
      </DkField>
    </div>

    <DkField
      label="Kontakt-E-Mail"
      :error="fehler.kontakt_email"
      help="An diese Adresse gehen Rückfragen von Interessierten."
    >
      <template #default="{ id, ariaDescribedby, ariaInvalid }">
        <input
          :id="id"
          class="dk-ui-eingabe dk-ui-eingabe--feld"
          type="email"
          maxlength="255"
          autocomplete="email"
          placeholder="z. B. buero@gemeinde.example"
          :value="entwurf.kontakt_email"
          :aria-describedby="ariaDescribedby"
          :aria-invalid="ariaInvalid || undefined"
          @input="$emit('feld', { feld: 'kontakt_email', wert: $event.target.value })"
        />
      </template>
    </DkField>

    <div class="schritt-raster">
      <DkField label="Telefon" :error="fehler.telefon">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            class="dk-ui-eingabe dk-ui-eingabe--feld"
            type="tel"
            maxlength="40"
            autocomplete="tel"
            placeholder="z. B. +49 1234 56789"
            :value="entwurf.telefon"
            :aria-describedby="ariaDescribedby"
            :aria-invalid="ariaInvalid || undefined"
            @input="$emit('feld', { feld: 'telefon', wert: $event.target.value })"
          />
        </template>
      </DkField>
      <DkField label="Website" :error="fehler.website" help="Mit http:// oder https:// beginnen.">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            class="dk-ui-eingabe dk-ui-eingabe--feld"
            type="url"
            maxlength="255"
            autocomplete="url"
            placeholder="z. B. https://gemeinde.example"
            :value="entwurf.website"
            :aria-describedby="ariaDescribedby"
            :aria-invalid="ariaInvalid || undefined"
            @input="$emit('feld', { feld: 'website', wert: $event.target.value })"
          />
        </template>
      </DkField>
    </div>

    <!-- Zeitzone: nur Anzeige, kein Feld. Ein Wert, der sich ändern liesse,
         würde alle Termine der Gemeinde verschieben. -->
    <div class="zeitzone">
      <span class="zeitzone-label">Zeitzone</span>
      <span class="zeitzone-wert">{{ zeitzone || '—' }}</span>
      <span class="zeitzone-hinweis">{{ zeitzoneHinweis || 'Voreingestellt – die Zeitzone gilt für alle Termine.' }}</span>
    </div>
  </section>
</template>

<script setup>
/**
 * Schritt „Kontakt“ (ON-3/W2, Entwurf 05).
 *
 * Reine Darstellung; die Eingaben liegen im Modulzustand, damit „Weiter“ in der
 * Fußleiste den vollständigen Satz speichern kann (der Server LÖSCHT leere
 * Felder, siehe `speicherRumpf`).
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import DkField from '../ui/DkField.vue'

defineProps({
  entwurf: { type: Object, required: true },
  fehler: { type: Object, default: () => ({}) },
  zeitzone: { type: String, default: '' },
  zeitzoneHinweis: { type: String, default: '' },
})
defineEmits(['feld'])
</script>

<style scoped>
.schritt { display: flex; flex-direction: column; gap: var(--sp-4); }
.schritt-titel { margin: 0; font-size: var(--fs-h1); font-weight: var(--fw-h); color: var(--text); line-height: 1.25; }
.schritt-unterzeile {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.schritt-raster {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 9fr);
  gap: var(--sp-3);
}
.zeitzone {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-2);
}
.zeitzone-label { font-size: var(--fs-feld); font-weight: 600; color: var(--muted); }
.zeitzone-wert { font-size: var(--fs); color: var(--text); }
.zeitzone-hinweis { font-size: var(--fs-sm); color: var(--subtle); }

@media (max-width: 600px) {
  .schritt-raster { grid-template-columns: minmax(0, 1fr); }
  .schritt-unterzeile { font-size: var(--fs); }
}
</style>
