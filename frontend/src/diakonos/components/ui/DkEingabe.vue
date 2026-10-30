<template>
  <input
    class="dk-ui-eingabe dk-ui-eingabe--feld"
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :autocomplete="autocomplete"
    :disabled="disabled"
    :required="required"
    :name="name"
    @input="$emit('update:modelValue', $event.target.value)"
  />
</template>

<script setup>
/**
 * DkEingabe — einzeiliges Eingabefeld (Stil A).
 *
 * DEP-1: Ersatz für `FormControl`/`TextInput` aus frappe-ui.
 *
 * DEP-2: Darstellung vollständig in dieser Datei (scoped, nur Tokens aus
 * tokens.css). Bis hierher stand sie in der zentralen Regel `.dk-ui-eingabe`
 * in index.css — die Einstiege organigramm und registrierung laden aber nur
 * tokens.css, dort fehlte sie: Felder in der Registrierung waren die
 * Browser-Vorgaben. Die Farben unten sind dieselben wie in index.css.
 *
 * Verwendung immer innerhalb von <DkField>, damit Label, Pflichtzeichen und
 * Fehlertext aus einer Quelle kommen:
 *
 *   <DkField label="Vorname" required>
 *     <template #default="{ id, ariaDescribedby, ariaInvalid }">
 *       <DkEingabe :id="id" v-model="form.vorname" :aria-describedby="ariaDescribedby" :aria-invalid="ariaInvalid" />
 *     </template>
 *   </DkField>
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  autocomplete: { type: String, default: undefined },
  disabled: Boolean,
  required: Boolean,
  name: { type: String, default: undefined },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
/* DEP-2: Farbe + Form des Feldes stehen hier, nicht mehr (nur) in der
   zentralen Regel `.dk-ui-eingabe` in index.css: die Einstiege organigramm
   und registrierung laden nur tokens.css und hatten dadurch die
   Browser-Vorgabe. Werte = dieselben Tokens wie in index.css.
   Die Schriftgröße bleibt ABSICHTLICH weg (Touch-Regel OP-HANDY-14 in
   index.css hebt auf 16 px, sonst zoomt iOS beim Antippen).
   `:where()` hält die Spezifität bei (0,1,0) — index.css gewinnt weiterhin,
   wo es geladen ist. */
.dk-ui-eingabe:where(.dk-ui-eingabe--feld) {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius);
  font-family: inherit;
  background: var(--dk-surface);
  color: var(--dk-text);
  border: 1px solid var(--dk-border);
}
.dk-ui-eingabe:where(.dk-ui-eingabe--feld)::placeholder { color: var(--dk-text-subtle); }
.dk-ui-eingabe:where(.dk-ui-eingabe--feld):focus-visible { border-color: var(--dk-border-strong); }
</style>
