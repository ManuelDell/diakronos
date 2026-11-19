<template>
  <!-- CHAT-5-UI: „Umfrage starten“ — Frage, Antworten (2–15), Mehrfach­auswahl,
       anonym/offen, Frist (Datum + Uhrzeit in Europe/Berlin). Die Bedienprüfung
       steht in `umfrage.mjs`; ob die Person darf, entscheidet der Server. -->
  <DkDialog
    :model-value="modelValue"
    :title="TEXTE.neu"
    size="md"
    @close="schliessen"
  >
    <form class="dk-umfrage-form" @submit.prevent="abschicken">
      <label class="dk-umfrage-feld" for="umfrage-frage">
        <span class="dk-umfrage-label">Frage</span>
        <textarea
          id="umfrage-frage"
          v-model="frage"
          class="dk-umfrage-text"
          rows="2"
          :maxlength="FRAGE_MAX"
          placeholder="Was möchtest du wissen?"
        ></textarea>
      </label>

      <fieldset class="dk-umfrage-feld">
        <legend class="dk-umfrage-label">Antworten</legend>
        <ul class="dk-umfrage-liste">
          <li v-for="(_, i) in optionen" :key="i" class="dk-umfrage-zeile">
            <label class="dk-umfrage-nur-vorlesen" :for="`umfrage-option-${i}`">Antwort {{ i + 1 }}</label>
            <input
              :id="`umfrage-option-${i}`"
              v-model="optionen[i]"
              class="dk-umfrage-eingabe"
              type="text"
              :maxlength="OPTION_MAX"
              :placeholder="`Antwort ${i + 1}`"
            />
            <DkButton
              v-if="optionen.length > OPTIONEN_MIN"
              variant="ghost"
              size="sm"
              :aria-label="`Antwort ${i + 1} entfernen`"
              @click="entfernen(i)"
            >Entfernen</DkButton>
          </li>
        </ul>
        <DkButton
          v-if="optionen.length < OPTIONEN_MAX"
          variant="secondary"
          size="sm"
          @click="hinzufuegen"
        >Antwort anlegen</DkButton>
      </fieldset>

      <div class="dk-umfrage-feld">
        <DkCheckbox v-model="mehrfach" label="Mehrfachauswahl möglich" />
      </div>

      <fieldset class="dk-umfrage-feld">
        <legend class="dk-umfrage-label">Auswertung</legend>
        <div class="dk-umfrage-wahlzeile">
          <label class="dk-umfrage-wahl">
            <input v-model="art" type="radio" value="anonym" />
            <span>{{ TEXTE.anonym }}</span>
          </label>
          <label class="dk-umfrage-wahl">
            <input v-model="art" type="radio" value="offen" />
            <span>{{ TEXTE.offen }}</span>
          </label>
        </div>
        <p class="dk-umfrage-hinweis">
          {{ art === 'anonym'
            ? 'Niemand sieht, wer wie gestimmt hat — auch du nicht. Eine anonyme Stimme lässt sich nicht ändern.'
            : 'Das Ergebnis zeigt zu jeder Antwort die Namen. Die eigene Stimme lässt sich bis zum Ende ändern.' }}
        </p>
      </fieldset>

      <fieldset class="dk-umfrage-feld">
        <legend class="dk-umfrage-label">Frist (optional)</legend>
        <div class="dk-umfrage-wahlzeile">
          <label class="dk-umfrage-wahl" for="umfrage-datum">
            <span>Datum</span>
            <input id="umfrage-datum" v-model="datum" class="dk-umfrage-eingabe" type="date" />
          </label>
          <label class="dk-umfrage-wahl" for="umfrage-uhrzeit">
            <span>Uhrzeit</span>
            <input id="umfrage-uhrzeit" v-model="uhrzeit" class="dk-umfrage-eingabe" type="time" />
          </label>
        </div>
        <p class="dk-umfrage-hinweis">
          Ohne Frist läuft die Umfrage bis zur Schließung; ohne Uhrzeit endet sie um 23:59.
          Zeiten gelten in deutscher Zeit.
        </p>
      </fieldset>

      <p v-if="meldung" class="dk-umfrage-fehler" role="alert">{{ meldung }}</p>
      <p v-if="darfSenden === false" class="dk-umfrage-hinweis">
        Hier darfst du gerade nichts senden — eine Umfrage lässt sich deshalb nicht starten.
      </p>

      <div class="dk-umfrage-aktionen">
        <DkButton variant="ghost" @click="schliessen">Abbrechen</DkButton>
        <DkButton type="submit" variant="primary" :loading="laeuft">Umfrage starten</DkButton>
      </div>
    </form>
  </DkDialog>
</template>

<script setup>
/**
 * ChatUmfrageDialog — „Umfrage starten“ (CHAT-5-UI).
 *
 * Felder und Grenzen: Frage (≤ `FRAGE_MAX`), 2–15 Antworten (≤ `OPTION_MAX`),
 * Mehrfachauswahl, anonym (VOREINSTELLUNG, wie im Server) oder offen, Frist
 * optional als Datum + Uhrzeit. Der Dialog prüft nur die BEDIENUNG
 * (`umfragePruefen`); Rechte prüft der Server — der Elternteil zeigt eine
 * Ablehnung ruhig als Meldung in `meldung`.
 */
import { ref, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkDialog from '../ui/DkDialog.vue'
import { FRAGE_MAX, OPTIONEN_MAX, OPTIONEN_MIN, OPTION_MAX, TEXTE, umfragePruefen } from './umfrage.mjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Läuft der Aufruf beim Server? Der Elternteil hält den Zustand. */
  laeuft: { type: Boolean, default: false },
  /** Meldung des Servers (403, 400 …) — ruhig angezeigt. */
  fehler: { type: String, default: '' },
  /** Darf die Person senden? `false` = Knopf im Eingabebereich ist weg;
   *  der Dialog erklärt es, statt stumm zu scheitern. */
  darfSenden: { type: Boolean, default: undefined },
})

const emit = defineEmits(['update:modelValue', 'anlegen'])

const frage = ref('')
const optionen = ref(['', ''])
const mehrfach = ref(false)
const art = ref('anonym') // Voreinstellung ANONYM (Konzept F5)
const datum = ref('')
const uhrzeit = ref('')
const meldung = ref('')

/** Beim Öffnen frisch starten; ein Serverfehler bleibt sichtbar. */
watch(() => props.modelValue, (offen) => {
  if (!offen) return
  frage.value = ''
  optionen.value = ['', '']
  mehrfach.value = false
  art.value = 'anonym'
  datum.value = ''
  uhrzeit.value = ''
  meldung.value = ''
})
watch(() => props.fehler, (neu) => { if (neu) meldung.value = neu })

function hinzufuegen() {
  if (optionen.value.length >= OPTIONEN_MAX) return
  optionen.value = [...optionen.value, '']
}

function entfernen(index) {
  if (optionen.value.length <= OPTIONEN_MIN) return
  optionen.value = optionen.value.filter((_, i) => i !== index)
}

function schliessen() {
  emit('update:modelValue', false)
}

function abschicken() {
  if (props.laeuft) return
  const geprueft = umfragePruefen({
    frage: frage.value,
    optionen: optionen.value,
    mehrfach: mehrfach.value,
    anonym: art.value !== 'offen',
    datum: datum.value,
    uhrzeit: uhrzeit.value,
  })
  if (!geprueft.ok) {
    meldung.value = geprueft.fehler
    return
  }
  meldung.value = ''
  emit('anlegen', {
    frage: geprueft.frage,
    optionen: geprueft.optionen,
    mehrfach: geprueft.mehrfach,
    anonym: geprueft.anonym,
    frist: geprueft.frist,
  })
}

/** Stand des Dialogs — nur für den Node-Test nachlesbar (kein Betriebsweg). */
defineExpose({ frage, optionen, mehrfach, art, datum, uhrzeit, meldung, hinzufuegen, entfernen, abschicken })
</script>

<style scoped>
.dk-umfrage-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.dk-umfrage-feld {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}
.dk-umfrage-label {
  padding: 0;
  font-size: var(--fs-12);
  font-weight: var(--fw-mittel);
  color: var(--muted);
}
.dk-umfrage-text,
.dk-umfrage-eingabe {
  width: 100%;
  min-height: var(--control-h);
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
}
.dk-umfrage-text { resize: vertical; }
.dk-umfrage-text:focus-visible,
.dk-umfrage-eingabe:focus-visible {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: var(--rahmen-breite);
}
.dk-umfrage-liste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-umfrage-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.dk-umfrage-wahlzeile {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.dk-umfrage-wahl {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  font-size: var(--fs-14);
  cursor: pointer;
}
.dk-umfrage-wahl input[type="radio"] {
  width: 20px;
  height: 20px;
  accent-color: var(--accent);
}
.dk-umfrage-wahl input[type="date"],
.dk-umfrage-wahl input[type="time"] { width: auto; }
.dk-umfrage-hinweis {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--subtle);
}
.dk-umfrage-fehler {
  margin: 0;
  padding: var(--sp-2);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-12);
}
.dk-umfrage-aktionen {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}
.dk-umfrage-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(var(--rahmen-breite) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
