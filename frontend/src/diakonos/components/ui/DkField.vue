<template>
  <div class="dk-ui-field" :class="{ 'has-error': !!angezeigterFehler, 'is-disabled': disabled }"
    :id="anker ? ankerId : undefined">
    <label v-if="label" :for="eingabeId" class="dk-ui-field-label">
      {{ label }}<span v-if="pflichtAktiv" class="dk-ui-field-pflicht" aria-hidden="true">*</span>
    </label>
    <slot
      :id="eingabeId"
      :aria-describedby="beschriebenDurch"
      :aria-invalid="!!angezeigterFehler"
      :fehler="angezeigterFehler"
      :gueltig="gueltig"
      :pruefe="pruefe"
      :zuruecksetzen="zuruecksetzen"
      :onBlur="verlassen"
      :onFocus="verlassen"
      :onInput="getippt"
      :feldProps="feldProps"
    />
    <p v-if="angezeigterFehler" :id="meldungId" class="dk-ui-field-fehler" role="alert">
      {{ angezeigterFehler }}
    </p>
    <!-- Hilfetext: eigene Kennung (UX2f2a, Review-Befund). Vorher nannte
         `aria-describedby` bei Hilfe OHNE Meldung die Kennung `…-desc-…`, die
         im DOM niemand trug — das Feld zeigte auf nichts. Jetzt trägt der
         Hilfe-Absatz `hilfeId`, und `beschriebenDurch` wählt aus: Meldung,
         sonst Hilfe, sonst gar nichts. Sichtbar bleibt er, solange keine
         Meldung dasteht — unabhängig davon, ob schon ein gültiger Wert im
         Feld steht. -->
    <p v-else-if="hilfeText" :id="hilfeId" class="dk-ui-field-hilfe">{{ hilfeText }}</p>
  </div>
</template>

<script setup>
/**
 * DkField — Hülle für ein Eingabefeld: Label, Hilfe, Fehler (Stil A).
 *
 * UX2f „Feld mit Prüfung": Zusätzlich zum von außen gesetzten `error`
 * (Servermeldung, Sammelprüfung beim Speichern) kann das Feld seine Regel
 * SELBST prüfen. Dann gilt:
 *
 *   * geprüft wird beim VERLASSEN des Feldes (blur) — nicht bei jedem
 *     Tastendruck, solange noch nichts beanstandet wurde;
 *   * nach dem ERSTEN Fehler wird bei jedem Tippen erneut geprüft, damit die
 *     Meldung verschwindet, sobald der Fehler behoben ist (I4);
 *   * die Meldung steht DIREKT am Feld und ist per `aria-describedby`
 *     verbunden, das Feld trägt `aria-invalid` (Karte UX2f);
 *   * die Eingabe bleibt unangetastet — eine Prüfung liest nur.
 *
 * Regeln kommen aus `composables/feldPruefung.mjs` (pflicht, email, url, plz,
 * laenge, eigene Funktion) oder als eigene Funktion `wert => meldung|''`.
 *
 * Zwei Schreibweisen, beide gleichwertig — `feldProps` enthält Wert, Eingabe,
 * Verlassen und aria-Auszeichnung vollständig:
 *
 *   <DkField label="E-Mail" :regel="email()" :wert="form.email"
 *            @update:wert="form.email = $event">
 *     <DkEingabe v-bind="feldProps" />
 *   </DkField>
 *
 *   <DkField v-slot="feld" label="E-Mail" :regel="email()" :wert="form.email"
 *            @update:wert="form.email = $event">
 *     <input v-bind="feld.feldProps" type="email" />
 *   </DkField>
 *
 * Ohne `regel` verhält sich das Feld genau wie bisher (nur `error` von außen).
 * Nur Tokens, keine festen Farben.
 */
import { computed, ref, useId, watch } from 'vue'
import { sprungId } from '../../pages/sprung.mjs'

const props = defineProps({
  label: { type: String, default: '' },
  help: { type: String, default: '' },
  /** Fehler von AUSSEN (Server, Sammelprüfung). Hat Vorrang vor der Eigenprüfung. */
  error: { type: String, default: '' },
  /** Prüfregel: `(wert, form) => meldung|''` (aus feldPruefung.mjs). */
  regel: { type: Function, default: null },
  /**
   * Wert, gegen den die Regel läuft.
   *
   * UX2f2a (Review-Befund): Vorgabe ist `undefined`, NICHT `''`. `feldProps`
   * gibt `value` nur weiter, wenn wirklich ein Wert gesetzt wurde — sonst
   * überschriebe ein leeres `value` ein `v-model` am Eingabeelement bei jedem
   * Tastendruck (Muster `<input v-bind="feld.feldProps" v-model="x">`, z. B.
   * Registrierung.vue: das Feld leerte sich nach jedem Zeichen).
   */
  wert: { type: [String, Number, Boolean, Array, Object], default: undefined },
  /** Zusätzliche Werte für eigene Regeln (ganzes Formular). */
  form: { type: Object, default: () => ({}) },
  /** Pflichtzeichen im Label. Wird bei `regel` aus `pflicht()` erkannt. */
  required: Boolean,
  /** Eigener Name für die Pflichtmeldung („Bitte E-Mail-Adresse angeben."). */
  pflichtName: { type: String, default: '' },
  /** Mindestens ein Zeichen (Pflicht), auch ohne eigene Regel. */
  minlength: { type: [String, Number], default: undefined },
  /** Höchstens so viele Zeichen. */
  maxlength: { type: [String, Number], default: undefined },
  disabled: Boolean,
  /**
   * UX3h: Sprungmarke dieses Feldes (`dk-sprung-<anker>`). Die Suche der
   * Einstellungen führt zu genau dieser Kennung; ein Feld ohne `anker` hat
   * keine. Die Kennung kommt aus `pages/sprung.mjs` — EINE Wahrheit für
   * Marke und Ziel, damit beide nicht auseinanderlaufen.
   */
  anker: { type: String, default: '' },
})

const emit = defineEmits(['update:wert', 'pruefung'])

// EINE Kennung pro Feld: Label (<label for>), Eingabe und Meldung gehören
// zusammen. `useId` gibt es erst ab Vue 3.5 — der Rückfall deckt 3.4 ab und
// ist ebenfalls server-/hydration-sicher (Aufruf nur im Browser/SSR-Kontext).
const id = typeof useId === 'function'
  ? useId()
  : 'dk' + Math.random().toString(36).slice(2, 9) + Date.now().toString(36).slice(-4)
const eingabeId = computed(() => 'dk-field-' + id)
/**
 * Zwei getrennte Kennungen (UX2f2a, Review-Befund): die MELDUNG und die
 * HILFE. Vorher gab es nur `…-desc-…` — es stand an der Meldung, wurde aber
 * auch bei Hilfe OHNE Meldung genannt, und dort trug es niemand im DOM.
 */
const meldungId = computed(() => 'dk-field-desc-' + id)
const hilfeId = computed(() => 'dk-field-hilfe-' + id)
/** UX3h: Sprungmarke des Feldes (leer = keine). */
const ankerId = computed(() => sprungId(props.anker))

// ── Zustand der Eigenprüfung ───────────────────────────────────────────────
// Das Feld wurde einmal verlassen — BEFUND der Abnahme: Fokussieren ist
// nicht Verlassen. Ein Klick ins Feld ohne Weitertippen darf keinen Fehler
// zeigen (sonst blitzte er schon beim zweiten Besuch auf).
const beruehrt = ref(false)
const eigenFehler = ref('')      // Meldung aus der Regel
const gueltig = ref(false)       // zuletzt geprüft und in Ordnung

const pflichtName = computed(() => {
  if (props.pflichtName) return props.pflichtName
  return props.label ? `„${props.label}"` : 'einen Wert'
})

/** Pflicht aus `required`, `pflichtName` oder `minlength`/`maxlength`. */
const pflichtAktiv = computed(() => props.required || Boolean(props.pflichtName))

/**
 * Wirksame Meldung: Was von AUSSEN kommt, gewinnt (Server weiß mehr).
 * Danach die Eigenprüfung — aber nur, wenn das Feld schon verlassen wurde
 * oder von außen ausdrücklich „geprüft werden" verlangt wird.
 */
const angezeigterFehler = computed(() => props.error || (beruehrt.value ? eigenFehler.value : ''))

/**
 * Hilfetext.
 *
 * UX2f2a: Der Hilfetext bleibt sichtbar, solange keine Meldung dasteht —
 * auch dann, wenn schon ein gültiger Wert im Feld steht. Vorher blendete ihn
 * eine Regel nach der ersten gültigen Prüfung aus; das war ein Review-Befund
 * („Hilfetext behält seine id und bleibt sichtbar“).
 *
 * WICHTIG: Der Hilfetext trägt ABSICHTLICH nicht die Beschreibungs-ID —
 * diese zeigt auf die Fehlermeldung. Sonst läse ein Screenreader bei einem
 * Fehler den Hilfetext als „Beschreibung" vor und die Meldung gar nicht
 * (Review-Befund im Entwurf B1: „description ist der Tipp, nicht der Fehler").
 */
const hilfeText = computed(() => props.help)

/**
 * Was das Eingabeelement als „Beschreibung" ansieht (Review-Befund UX2f2a,
 * Punkt 1): die MELDUNG, wenn eine dasteht — sonst der HILFETEXT, wenn es
 * einen gibt — sonst nichts. Beide Ziele existieren im DOM (die Kennungen
 * stehen an den jeweiligen `<p>`), damit ein Screenreader nie auf ein
 * Element zeigt, das es nicht gibt.
 */
const beschriebenDurch = computed(() => {
  if (angezeigterFehler.value) return meldungId.value
  if (hilfeText.value) return hilfeId.value
  return undefined
})

/**
 * Prüft den aktuellen Wert. Gibt die Meldung zurück ('' = in Ordnung) und
 * merkt sich das Ergebnis. `sichtbar = true` zeigt sie sofort an.
 */
function pruefe(wert = props.wert, sichtbar = true) {
  let meldung = ''
  if (props.regel) {
    meldung = props.regel(wert, props.form) || ''
  } else if (pflichtAktiv.value && !String(wert ?? '').trim()) {
    meldung = `Bitte ${pflichtName.value} angeben.`
  }
  eigenFehler.value = meldung
  gueltig.value = !meldung && Boolean(String(wert ?? '').trim())
  if (sichtbar) beruehrt.value = true
  emit('pruefung', meldung)
  return meldung
}

/**
 * Beim Verlassen: immer prüfen und das Ergebnis zeigen.
 *
 * BEFUND (Abnahme im Wegwerk-Stack): `DkEingabe` war NICHT an diesen
 * Handler angeschlossen — das Feld prüfte nie. Jetzt reicht `feldProps`
 * `onBlur` UND `onFocus` ans Element: `onFocus` liefert das Element selbst
 * (`$el`), das braucht `verlassen()`, um Fokus↔Blur zu unterscheiden
 * (Focusin feuert bei manchen Feldern ebenfalls; das Element bleibt dann
 * `document.activeElement`, der Blur ruft danach mit demselben Element).
 */
function verlassen(ereignis) {
  const ziel = ereignis && typeof ereignis === 'object' && 'target' in ereignis ? ereignis.target : null
  const el = ziel && ziel.nodeType ? ziel : null
  if (el && typeof el.matches === 'function' && el === document.activeElement) return
  pruefe(props.wert, true)
}

/**
 * Beim Tippen: NICHT prüfen, solange nichts beanstandet wurde — sonst
 * blitzt beim ersten Buchstaben ein Fehler auf („Feld mit Prüfung" der
 * Karte: erst beim Verlassen, DANACH beim Tippen).
 */
function getippt(wert) {
  emit('update:wert', wert)
  if (beruehrt.value && eigenFehler.value) pruefe(wert, true)
  else if (gueltig.value) pruefe(wert, true)
}

/** Zustand zurücksetzen (z. B. wenn ein Dialog neu geöffnet wird). */
function zuruecksetzen() {
  beruehrt.value = false
  eigenFehler.value = ''
  gueltig.value = false
}

// Wechselt der Wert von außen (Programm, Zurücksetzen), die alte Meldung
// nicht stehen lassen: sie gehört zu einem anderen Wert.
watch(() => props.wert, (neu) => {
  if (!beruehrt.value) return
  if (eigenFehler.value) pruefe(neu, true)
})

/**
 * Fertige Auszeichnung für das Eingabeelement — ALLES, was ein Feld braucht:
 * Kennung für das Label, Wert, Entgegennahme der Eingabe, Verlassen, die
 * aria-Auszeichnung.
 *
 * UX2f2a (Review-Befund): Vorher stand hier nur die halbe Auszeichnung
 * (`id`, aria, Handler) — der WERT fehlte. Wer den Feldsatz wie vorgesehen
 * bindet (`<input v-bind="feld.feldProps">`) bekam ein leeres Feld, das keine
 * Eingabe annahm; die migrierten Formulare warfen TypeError bzw. blieben leer.
 *
 * Zwei Zusagen aus der Nachprüfung (UX2f2a, Punkte 2 und 3):
 *
 *   * `value` steht NUR im Feldsatz, wenn `wert` wirklich gesetzt wurde.
 *     Sonst überschriebe `value: undefined` ein `v-model` am Eingabeelement:
 *     `<input v-bind="feld.feldProps" v-model="x">` setzt den Wert aus `x`,
 *     der Feldsatz darunter schrieb ihn bei jedem Re-Render wieder auf leer —
 *     das Feld leerte sich nach jedem Tastendruck.
 *   * `onUpdate:modelValue` steht NICHT mehr drin. Die Eingabeannahme läuft
 *     über `onInput` → `update:wert`; ein zweiter Zuhörer in `feldProps`
 *     läuft an einem echten `v-model` VORBEI und die Eingabe käme doppelt
 *     (einmal über `v-model`, einmal über `update:wert`). `DkEingabe` liest
 *     `onUpdate:modelValue` auch nicht mehr aus `$attrs`.
 */
const feldProps = computed(() => {
  const satz = {
    id: eingabeId.value,
    onInput: (ereignis) => getippt(ereignis?.target?.value ?? ''),
    onBlur: verlassen,
    onFocus: verlassen,
    'aria-describedby': beschriebenDurch.value,
    'aria-invalid': angezeigterFehler.value ? 'true' : undefined,
    required: pflichtAktiv.value || undefined,
    minlength: props.minlength ?? undefined,
    maxlength: props.maxlength ?? undefined,
  }
  // Nur setzen, wenn es einen Wert gibt (`wert` hat Vorgabe `undefined`).
  if (props.wert !== undefined) satz.value = props.wert
  return satz
})

defineExpose({ pruefen: pruefe, zuruecksetzen })
</script>

<style scoped>
.dk-ui-field { display: flex; flex-direction: column; gap: var(--sp-1); }
.dk-ui-field-label {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text);
}
.dk-ui-field-pflicht { color: var(--err); margin-left: var(--sp-1); }
.dk-ui-field-hilfe { font-size: var(--fs-sm); color: var(--muted); margin: 0; }
.dk-ui-field-fehler { font-size: var(--fs-sm); color: var(--err); margin: 0; font-weight: 500; }
.dk-ui-field.is-disabled { opacity: .6; }
</style>
