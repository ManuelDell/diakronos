<template>
  <!-- ON-3 (W2, Schritt 1 „Gemeinde“, Entwurf 04/14): Name ist Pflicht,
       Kurzname optional, Logo mit Vorschau und „Entfernen“. Die Texte stehen
       wörtlich im Entwurf; „z. B. …“ ist Platzhalter, keine Vorbelegung. -->
  <section class="schritt">
    <h1 class="schritt-titel">Gemeinde</h1>
    <p class="schritt-unterzeile">Grunddaten Ihrer Kirchengemeinde – änderbar in den Einstellungen.</p>

    <DkField
      label="Gemeindename"
      required
      :error="fehler.gemeindename"
      help="Erscheint im Kopfbereich und auf Einladungen."
    >
      <template #default="{ id, ariaDescribedby, ariaInvalid }">
        <input
          :id="id"
          class="dk-ui-eingabe dk-ui-eingabe--feld"
          type="text"
          maxlength="140"
          placeholder="z. B. Ev. Gemeinde Musterstadt"
          autocomplete="organization"
          :value="entwurf.gemeindename"
          :aria-describedby="ariaDescribedby"
          :aria-invalid="ariaInvalid || undefined"
          required
          @input="$emit('feld', { feld: 'gemeindename', wert: $event.target.value })"
        />
      </template>
    </DkField>

    <DkField label="Kurzname" :error="fehler.kurzname" help="Erscheint in Kopfzeile und Kalenderkürzeln.">
      <template #default="{ id, ariaDescribedby, ariaInvalid }">
        <input
          :id="id"
          class="dk-ui-eingabe dk-ui-eingabe--feld"
          type="text"
          maxlength="40"
          placeholder="z. B. Musterstadt"
          :value="entwurf.kurzname"
          :aria-describedby="ariaDescribedby"
          :aria-invalid="ariaInvalid || undefined"
          @input="$emit('feld', { feld: 'kurzname', wert: $event.target.value })"
        />
      </template>
    </DkField>

    <div class="schritt-trenner" aria-hidden="true"></div>

    <h2 class="schritt-abschnitt">Logo</h2>
    <div class="logo-zeile">
      <!-- Vorschau: das hinterlegte Logo, sonst das Monogramm (Entwurf 04:
           „Ohne Logo verwendet Diakronos ein Monogramm.“). Die Adresse kommt
           fertig vom Server (logo_url, mit ?v=…), wird NICHT nachgebaut. -->
      <div class="logo-platz">
        <img v-if="logoUrl" :src="logoUrl" alt="Logo der Gemeinde" class="logo-bild" />
        <span v-else class="logo-monogramm" aria-hidden="true">{{ monogramm }}</span>
      </div>

      <div class="logo-aktionen">
        <p class="logo-zustand">{{ logoUrl ? 'Logo hinterlegt' : 'Kein Logo hinterlegt' }}</p>
        <div class="logo-knoepfe">
          <label class="logo-waehlen">
            <AssistentSymbol name="hochladen" :size="'var(--icon-sm)'" />
            <span>{{ logoLaeuft ? 'Wird geladen …' : 'Datei auswählen' }}</span>
            <input
              ref="dateiFeld"
              class="logo-datei"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/svg+xml"
              :disabled="logoLaeuft"
              @change="dateiGewaehlt"
            />
          </label>
          <DkButton
            v-if="logoUrl"
            variant="ghost"
            size="md"
            :disabled="logoLaeuft"
            @click="$emit('logo-entfernen')"
          >
            <template #icon><AssistentSymbol name="entfernen" :size="'var(--icon-sm)'" /></template>
            Entfernen
          </DkButton>
        </div>
        <p class="logo-hinweis">PNG, JPEG, WebP oder SVG, quadratisch empfohlen, max. 2 MB</p>
        <p v-if="logoFehler" class="logo-fehler" role="alert">{{ logoFehler }}</p>
      </div>
    </div>
  </section>
</template>

<script setup>
/**
 * Schritt „Gemeinde“ (ON-3/W2, Entwurf 04 + 14).
 *
 * Reine Darstellung: die Eingaben liegen im Modulzustand
 * (`useEinrichtungsAssistent`), dieser Schritt meldet Änderungen per Ereignis.
 * So bleiben die Werte beim Wechsel des Schritts erhalten und „Weiter“ in der
 * Fußleiste speichert genau das, was hier steht.
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { ref } from 'vue'
import DkField from '../ui/DkField.vue'
import DkButton from '../ui/DkButton.vue'
import AssistentSymbol from './AssistentSymbol.vue'

const props = defineProps({
  entwurf: { type: Object, required: true },
  fehler: { type: Object, default: () => ({}) },
  logoUrl: { type: String, default: '' },
  monogramm: { type: String, default: 'D' },
  logoLaeuft: Boolean,
  logoFehler: { type: String, default: '' },
})
const emit = defineEmits(['feld', 'logo-hochladen', 'logo-entfernen'])

const dateiFeld = ref(null)

function dateiGewaehlt(ereignis) {
  const datei = ereignis.target?.files?.[0]
  // Feld zurücksetzen: dieselbe Datei soll nach einem Fehler erneut wählbar
  // sein (sonst feuert `change` beim zweiten Mal nicht).
  ereignis.target.value = ''
  if (datei) emit('logo-hochladen', datei)
}
</script>

<style scoped>
.schritt { display: flex; flex-direction: column; gap: var(--sp-4); }
.schritt-titel {
  margin: 0;
  font-size: var(--fs-h1);
  font-weight: var(--fw-h);
  color: var(--text);
  line-height: 1.25;
}
.schritt-unterzeile {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.schritt-trenner { height: 1px; background: var(--line); margin: var(--sp-2) 0; }
.schritt-abschnitt {
  margin: 0;
  font-size: var(--fs-feld);
  font-weight: 600;
  color: var(--muted);
}

.logo-zeile { display: flex; gap: var(--sp-4); align-items: flex-start; flex-wrap: wrap; }
.logo-platz {
  width: var(--logo-vorschau);
  height: var(--logo-vorschau);
  flex: none;
  border-radius: var(--radius-lg);
  border: 1px dashed var(--line-strong);
  background: var(--surface-2);
  display: grid;
  place-items: center;
  overflow: hidden;
}
.logo-bild { width: 100%; height: 100%; object-fit: contain; background: var(--qr-flaeche); }
.logo-monogramm {
  font-size: var(--fs-h1);
  font-weight: var(--fw-h);
  color: var(--accent);
  letter-spacing: 0.02em;
}
.logo-aktionen { display: flex; flex-direction: column; gap: var(--sp-2); min-width: 0; }
.logo-zustand { margin: 0; font-size: var(--fs); color: var(--muted); }
.logo-knoepfe { display: flex; gap: var(--sp-2); flex-wrap: wrap; align-items: center; }
/* Das <label> ist der Knopf: <input type=file> ist kaum gestaltbar, aber
   Tastatur und Vorlesehilfe arbeiten damit korrekt (Fokusring am Label). */
.logo-waehlen {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  height: calc(var(--control-h) - var(--sp-1));
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs);
  font-weight: 550;
  cursor: pointer;
}
.logo-waehlen:hover { background: var(--surface-hover); border-color: var(--line-strong); }
.logo-waehlen:focus-within { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.logo-datei {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  border: 0;
}
.logo-hinweis { margin: 0; font-size: var(--fs-hinweis); color: var(--subtle); max-width: 340px; }
.logo-fehler { margin: 0; font-size: var(--fs-sm); font-weight: 500; color: var(--err); }

/* Handy (Entwurf 14): kleineres Logo-Feld, Aktionen darunter. */
@media (max-width: 600px) {
  .logo-platz { width: var(--logo-klein); height: var(--logo-klein); }
  .schritt-unterzeile { font-size: var(--fs); }
}
</style>
