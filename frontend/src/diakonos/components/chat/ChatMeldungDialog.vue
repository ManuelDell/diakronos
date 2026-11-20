<template>
  <!-- CHAT-6-UI: „Nachricht melden“ (Chat-Konzept 2.5).
       Grundauswahl, Freitext bis 500 Zeichen mit Zähler — und der Hinweis,
       was die Moderation sieht, steht IMMER sichtbar über dem Absenden
       (nicht erst nach dem Ausfüllen, nicht als Tooltip). Nach dem Absenden
       bleibt der Dialog offen und zeigt die ruhige Bestätigung; ein Fehler
       des Servers (etwa „Diese Nachricht wurde von dir bereits gemeldet.“)
       steht an derselben Stelle, ohne Vorwurf. -->
  <DkDialog
    :model-value="modelValue"
    :title="TEXTE.dialogTitel"
    size="sm"
    :beschrieben="hinweisId"
    @close="schliessen"
  >
    <!-- Erledigt: nur noch die Bestätigung. Kein zweites Absenden. -->
    <div v-if="fertig" class="dk-meldung"><p class="dk-meldung-danke" role="status">{{ TEXTE.danke }}</p></div>

    <form v-else class="dk-meldung" @submit.prevent="abschicken">
      <fieldset class="dk-meldung-gruende">
        <legend class="dk-meldung-label">{{ TEXTE.grundFrage }}</legend>
        <p class="dk-meldung-hilfe">{{ AUSWAHL_HILFE }}</p>
        <ul class="dk-meldung-liste">
          <li v-for="g in GRUENDE" :key="g.schluessel" class="dk-meldung-grund">
            <label class="dk-meldung-wahl">
              <input v-model="grund" type="radio" name="meldung-grund" :value="g.schluessel" />
              <span>{{ g.label }}</span>
            </label>
          </li>
        </ul>
      </fieldset>

      <!-- Freitext über DkField (Muster wie Datensicherung.vue): Label,
           Hilfe, Fehler und die aria-Auszeichnung kommen aus EINER Quelle. -->
      <DkField
        v-slot="feld"
        :label="TEXTE.freitextLabel"
        :help="zaehler"
        :wert="freitext"
        @update:wert="freitext = $event"
      >
        <textarea
          v-bind="feld.feldProps"
          class="dk-meldung-text"
          rows="3"
          :maxlength="FREITEXT_MAX"
        ></textarea>
      </DkField>

      <!-- DER Hinweis (Konzept 2.5): im Klartext, immer sichtbar. -->
      <p :id="hinweisId" class="dk-meldung-hinweis">{{ TEXTE.hinweis }}</p>

      <p v-if="meldung" class="dk-meldung-fehler" role="alert">{{ meldung }}</p>
      <div class="dk-meldung-aktionen">
        <DkButton variant="ghost" @click="schliessen">Abbrechen</DkButton>
        <DkButton type="submit" variant="primary" :loading="laeuft">{{ TEXTE.absenden }}</DkButton>
      </div>
    </form>
  </DkDialog>
</template>

<script setup>
/**
 * ChatMeldungDialog — eine fremde Nachricht melden (CHAT-6-UI).
 *
 * Der Dialog prüft nur die BEDIENUNG (`meldungPruefen`: Grund gewählt,
 * Freitext ≤ 500 Zeichen); ob Melden erlaubt ist, entscheidet der Server. Er
 * sendet NICHTS selbst — er meldet `melden` mit `{grund, freitext}` an die
 * Seite, die den Aufruf macht und die Antwort zurückgibt:
 *
 *   eingegangen: `meldung_offen`/`name` gesetzt → `fertig` (Bestätigung)
 *   Fehler:      `meldung` (Text des Servers, ruhig)
 */
import { computed, ref, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import {
  AUSWAHL_HILFE, FREITEXT_MAX, GRUENDE, TEXTE, meldungPruefen, zeichenZaehler,
} from './meldung.mjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Läuft der Aufruf beim Server? Der Elternteil hält den Zustand. */
  laeuft: { type: Boolean, default: false },
  /** Meldung des Servers (400 „bereits gemeldet“, 403 …) — ruhig angezeigt. */
  fehler: { type: String, default: '' },
  /** Die Antwort von `meldung_senden` (gesetzt = eingegangen). */
  eingegangen: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'melden'])

const grund = ref('')
const freitext = ref('')
const meldung = ref('')
const hinweisId = 'meldung-hinweis'
const zaehler = computed(() => zeichenZaehler(freitext.value))
const fertig = computed(() => props.eingegangen === true)

/** Beim Öffnen frisch starten; eine Servermeldung bleibt sichtbar. */
watch(() => props.modelValue, (offen) => {
  if (!offen) return
  grund.value = ''
  freitext.value = ''
  meldung.value = ''
})
watch(() => props.fehler, (neu) => { if (neu) meldung.value = neu })

function schliessen() {
  emit('update:modelValue', false)
}

function abschicken() {
  if (props.laeuft || fertig.value) return
  const geprueft = meldungPruefen({ grund: grund.value, freitext: freitext.value })
  if (!geprueft.ok) {
    meldung.value = geprueft.fehler
    return
  }
  meldung.value = ''
  emit('melden', { grund: geprueft.grund, freitext: geprueft.freitext })
}

/** Stand des Dialogs — nur für den Node-Test nachlesbar (kein Betriebsweg). */
defineExpose({ grund, freitext, meldung, abschicken, schliessen, zaehler })
</script>

<style scoped>
.dk-meldung {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.dk-meldung-gruende {
  margin: 0;
  padding: 0;
  border: none;
  min-width: 0;
}
.dk-meldung-label {
  display: block;
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  color: var(--text);
  padding: 0;
  margin: 0 0 var(--sp-1);
}
.dk-meldung-hilfe {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-12);
  color: var(--dk-text-muted);
  line-height: var(--lh-text);
}
.dk-meldung-liste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
/* K4: jede Wahl ist am Finger mindestens 44 px hoch — `--control-h` ist am
   groben Zeiger 44 px (tokens.css), also kein eigener fester Wert. */
.dk-meldung-wahl {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-14);
  color: var(--text);
  cursor: pointer;
}
.dk-meldung-wahl:hover { background: var(--surface-hover); }
.dk-meldung-wahl:focus-within { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-meldung-text {
  width: 100%;
  box-sizing: border-box;
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
  resize: vertical;
}
.dk-meldung-text:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-meldung-zaehler {
  align-self: flex-end;
  font-size: var(--fs-12);
  color: var(--subtle);
  font-variant-numeric: var(--fs-tabular);
}
/* Der Hinweis steht ruhig, aber in voller Schriftgröße — er ist keine
   Nebenbemerkung, sondern die Bedingung der Meldung. */
.dk-meldung-hinweis {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-left: var(--rahmen-breite) solid var(--line-strong);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-14);
  color: var(--text);
  line-height: var(--lh-text);
}
.dk-meldung-fehler { margin: 0; font-size: var(--fs-14); color: var(--err); }
.dk-meldung-danke {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  font-size: var(--fs-14);
  color: var(--text);
  line-height: var(--lh-text);
}
.dk-meldung-aktionen {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
</style>
