<template>
  <input
    v-bind="eingabeAttrs()"
    class="dk-ui-eingabe dk-ui-eingabe--feld"
    :type="type"
    :value="modelValue ?? $attrs.value"
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
 * UX2f (BEFUND der Abnahme im Wegwerf-Stack): Das Feld reichte NUR seine
 * eigenen Props durch. Was `DkField` über `v-bind="feld.feldProps"` zusätzlich
 * bindet — `id`, `aria-describedby`, `aria-invalid`, `onBlur`, `onFocus`,
 * `minlength`, `maxlength` — kam als „Attribut" an, und Vue hängt automatisch
 * nur `class`/`style` an ein Element. Folge: die Prüfung von DkField war am
 * Feld UNSICHTBAR (kein Blur-Handler, keine aria-Auszeichnung). Deshalb jetzt
 * `v-bind="$attrs"` am Eingabeelement und `inheritAttrs: false`, damit nichts
 * doppelt landet.
 *
 * UX2f2a (Review-Befund, Punkt 3): `$attrs` brachte ZWEI Dinge durcheinander.
 *
 *   * `:value="modelValue"` stand HINTER `v-bind="$attrs"` und überschrieb
 *     damit den Wert aus dem Feldsatz: `modelValue` hatte die Vorgabe `''`,
 *     also zeigte ein Feld wie „Kontakt-E-Mail" (`:wert` gesetzt, kein
 *     `v-model` an DkEingabe) immer leer. Jetzt ist die Vorgabe `undefined`,
 *     und der Wert kommt aus `modelValue`, sonst aus `$attrs.value`.
 *   * `onUpdate:modelValue` aus `$attrs` und das eigene
 *     `update:modelValue` lösten BEIDE aus — eine Eingabe wurde doppelt
 *     weitergereicht (Zähler, Dublettenprüfung u. a. liefen zweimal). Der
 *     Zuhörer aus `$attrs` wird nicht mehr angenommen; das eigene
 *     `update:modelValue` bleibt. `feldProps` liefert ihn seit UX2f2a auch
 *     nicht mehr (Eingabeannahme läuft über `onInput`).
 *
 * Verwendung immer innerhalb von <DkField>:
 *
 *   <DkField label="E-Mail" :regel="email()" :wert="form.email"
 *            @update:wert="form.email = $event">
 *     <DkEingabe v-bind="feldProps" type="email" />
 *   </DkField>
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
import { useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

const attrs = useAttrs()

defineProps({
  // UX2f2a: Vorgabe `undefined` — dann zählt der Wert aus `$attrs` (Feldsatz).
  modelValue: { type: [String, Number], default: undefined },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  autocomplete: { type: String, default: undefined },
  disabled: Boolean,
  required: Boolean,
  name: { type: String, default: undefined },
})
defineEmits(['update:modelValue'])

/**
 * Attribute für das Eingabeelement: `$attrs` OHNE `onUpdate:modelValue`.
 * Der Zuhörer aus dem Feldsatz würde zusammen mit dem eigenen
 * `update:modelValue` doppelt feuern (Punkt 3) — er wird hier entfernt.
 */
function eingabeAttrs() {
  const rest = { ...attrs }
  delete rest['onUpdate:modelValue']
  return rest
}
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
