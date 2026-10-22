<template>
  <div class="dk-ui-datumzeit" :class="{ 'is-ganztags': ganztags || !mitZeit }">
    <div class="dk-ui-datumzeit-felder">
      <DkField :label="labelDatum" :required="required" :error="fehlerDatum" :help="hilfeDatum">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            :aria-describedby="ariaDescribedby || undefined"
            :aria-invalid="ariaInvalid || undefined"
            type="date"
            class="dk-ui-datumzeit-eingabe"
            :value="datum"
            :disabled="disabled"
            @input="datumGeaendert($event.target.value)"
            @change="datumGeaendert($event.target.value)"
          />
        </template>
      </DkField>

      <DkField
        v-if="mitZeit && !ganztags"
        :label="labelZeit"
        :required="required"
        :error="fehlerZeit"
        class="dk-ui-datumzeit-zeit"
      >
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            :aria-describedby="ariaDescribedby || undefined"
            :aria-invalid="ariaInvalid || undefined"
            type="time"
            step="60"
            class="dk-ui-datumzeit-eingabe"
            :value="zeit"
            :disabled="disabled"
            @input="zeitGeaendert($event.target.value)"
            @change="zeitGeaendert($event.target.value)"
          />
        </template>
      </DkField>

      <DkField v-if="mitZeit && !ganztags && mitEnde" label="Ende" :error="fehlerEnde" class="dk-ui-datumzeit-zeit">
        <template #default="{ id }">
          <input
            :id="id"
            type="time"
            step="60"
            class="dk-ui-datumzeit-eingabe"
            :value="endeZeit"
            :disabled="disabled"
            @input="endeGeaendert($event.target.value)"
            @change="endeGeaendert($event.target.value)"
          />
        </template>
      </DkField>

      <!-- B2: Mehrtägige Termine (Jugendfreizeit 23.–25.02.). Früher gab es
           nur EIN Datum; ein Termin über mehrere Tage wurde beim Bearbeiten
           still auf einen Tag gekürzt. Das Feld „Ende am“ erscheint, sobald
           es gebraucht wird, und lässt sich jederzeit einblenden. -->
      <DkField
        v-if="mitEnde"
        label="Ende am"
        :error="fehlerEnddatum"
        :help="mehrtaegig ? `Mehrtägiger Termin: ${mehrtaegigText}` : endeDatumHilfe"
        class="dk-ui-datumzeit-zeit"
      >
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            :aria-describedby="ariaDescribedby || undefined"
            :aria-invalid="ariaInvalid || undefined"
            type="date"
            class="dk-ui-datumzeit-eingabe"
            :value="endeDatum"
            :disabled="disabled"
            @input="endeDatumGeaendert($event.target.value)"
            @change="endeDatumGeaendert($event.target.value)"
          />
        </template>
      </DkField>

      <button
        v-if="mitEnde && !endeDatum"
        type="button"
        class="dk-ui-datumzeit-mehrtag"
        :disabled="disabled"
        @click="mehrtagEinschalten"
      >
        + Mehrtägig (Ende an einem späteren Tag)
      </button>
      <p v-else-if="mitEnde && endeDatum && !mehrtaegig" class="dk-ui-datumzeit-hinweis">
        Der Termin endet am selben Tag —
        <button type="button" class="dk-ui-datumzeit-link" :disabled="disabled" @click="mehrtagAusschalten">
          Enddatum entfernen
        </button>
      </p>
    </div>

    <!-- OP-UI-20: Deutsche Rückmeldung. Der Wert im Feld kommt vom Browser
         (am Handy die native Auswahl), die Zeile hier sagt ihn in Worten —
         damit niemand ein ISO-„2026-12-30 00:00“ lesen muss. -->
    <p v-if="vorschauText" class="dk-ui-datumzeit-vorschau">{{ vorschauText }}</p>
    <p v-else-if="!datum && hinweis" class="dk-ui-datumzeit-hinweis">{{ hinweis }}</p>
  </div>
</template>

<script setup>
/**
 * DkDatumZeit — ein Baustein für Datum und Uhrzeit (OP-UI-20 / S8).
 *
 * Warum native Felder: Am Handy öffnet `type="date"`/`type="time"` die
 * Auswahl des Geräts (kein winziger Kalender zum Treffen), auf dem Rechner
 * dieselbe verlässliche Eingabe mit Tastatur. Der Modellwert bleibt das
 * Serverformat „2026-12-30 19:00“; angezeigt und angesagt wird deutsch.
 *
 * R-DES-REST K-b (bekannte Grenze, in der BETRIEBSANLEITUNG Abschnitt 5.2
 * vermerkt): Native Felder zeigen ihre Schreibweise nach der BROWSERSPRACHE —
 * mit `en-US` steht im Feld „12/11/2026, 05:00 PM“. Deutsch ist nur die
 * Vorschauzeile darunter; sie ist die verbindliche Anzeige.
 *
 * Der Baustein erfindet keine Uhrzeit: ein reines Datum bleibt ohne Zeit.
 */
import { computed, ref, watch } from 'vue'
import DkField from './DkField.vue'
import {
  zerlegeDatumZeit, baueDatumZeit, vorschau, pruefeZeitraum,
  endeAusBeginnMitDatum, endeMitBeginn, tageDazwischen, zeitraumText,
} from '../../composables/datumZeit.mjs'

const props = defineProps({
  /** „2026-12-30 19:00“, „2026-12-30T19:00:00“ oder „2026-12-30“ */
  modelValue: { type: String, default: '' },
  /** Uhrzeit mit erfassen (aus = reines Datum, z. B. Serienende). */
  mitZeit: { type: Boolean, default: true },
  /** Ganztägig: nur Datum, kein Zeitfeld. */
  ganztags: Boolean,
  /** Zusätzliches Feld „Ende“ (Termin von–bis). */
  mitEnde: Boolean,
  endeModelValue: { type: String, default: '' },
  labelDatum: { type: String, default: 'Datum' },
  labelZeit: { type: String, default: 'Beginn' },
  hilfeDatum: { type: String, default: '' },
  hinweis: { type: String, default: '' },
  fehlerDatum: { type: String, default: '' },
  fehlerZeit: { type: String, default: '' },
  fehlerEnde: { type: String, default: '' },
  fehlerEnddatum: { type: String, default: '' },
  required: Boolean,
  disabled: Boolean,
})

const emit = defineEmits(['update:modelValue', 'update:endeModelValue'])

const datum = ref('')
const zeit = ref('')
const endeZeit = ref('')
const endeDatum = ref('')
// B2: Wurde das Enddatum bewusst gesetzt? Nur dann wird es beim Ändern des
// Beginndatums mitgeführt — ein BESTEHENDER mehrtaegiger Termin behält sein
// Ende auch dann, wenn der Bearbeiter nur die Uhrzeit anfasst.
const endeDatumGesetzt = ref(false)

/**
 * Modell → Felder (auch bei nachträglichem Setzen, z. B. beim Bearbeiten).
 *
 * B2: Das Enddatum kommt aus `endeModelValue`. Fehlt es (Altdaten, ganztägig),
 * gilt das Beginndatum — dann verhält sich der Baustein wie vorher.
 */
function ausModell() {
  const zerlegt = zerlegeDatumZeit(props.modelValue)
  const ende = zerlegeDatumZeit(props.endeModelValue)
  if (zerlegt.datum !== datum.value) datum.value = zerlegt.datum
  if (zerlegt.zeit !== zeit.value) zeit.value = zerlegt.zeit
  if (ende.zeit !== endeZeit.value) endeZeit.value = ende.zeit
  const neuesEnde = ende.datum || zerlegt.datum
  if (neuesEnde !== endeDatum.value) endeDatum.value = neuesEnde
}
watch(() => props.modelValue, ausModell, { immediate: true })
watch(() => props.endeModelValue, ausModell)

/** Der Termin läuft über mehrere Kalendertage. */
const mehrtaegig = computed(() => {
  const diff = tageDazwischen(datum.value, endeDatum.value)
  return diff !== null && diff > 0
})

const mehrtaegigText = computed(() => zeitraumText(datum.value, endeDatum.value))

const endeDatumHilfe = computed(() => (
  props.ganztags ? '' : 'Leer lassen, wenn der Termin am selben Tag endet.'
))

/** Die tatsächlich zu speichernde Endzeit (Vorschlag nur, wenn nichts dasteht). */
const wirksameEndeZeit = computed(() => endeAusBeginnMitDatum(
  datum.value,
  (props.mitZeit && !props.ganztags) ? zeit.value : '',
  endeDatum.value,
  endeZeit.value,
  props.ganztags,
))

function melde() {
  const wert = baueDatumZeit(datum.value, (props.mitZeit && !props.ganztags) ? zeit.value : '')
  if (wert !== props.modelValue) emit('update:modelValue', wert)
  if (props.mitEnde) {
    // B2: Das Ende behält SEIN Datum. Nur wenn der Nutzer das Beginndatum
    // hinter das Ende schiebt, wandert das Ende mit — sonst entstünde ein
    // Termin, der vor seinem Beginn endet.
    const bisDatum = endeMitBeginn(datum.value, endeDatum.value)
    if (bisDatum !== endeDatum.value) endeDatum.value = bisDatum
    const ende = baueDatumZeit(bisDatum || datum.value, wirksameEndeZeit.value)
    if (ende !== props.endeModelValue) emit('update:endeModelValue', ende)
  }
}

function datumGeaendert(wert) {
  datum.value = String(wert || '')
  melde()
}

function zeitGeaendert(wert) {
  const neu = String(wert || '')
  zeit.value = neu
  // S8: Nach dem Beginn wird das Ende vorgeschlagen, solange es leer ist.
  // B2: Bei einem mehrtägigen Termin bleibt das Ende unangetastet.
  if (props.mitEnde && !endeZeit.value) {
    const diff = tageDazwischen(datum.value, endeDatum.value)
    if (!(diff !== null && diff > 0)) endeZeit.value = endeAusBeginnMitDatum(datum.value, neu, '', '', false)
  }
  melde()
}

function endeGeaendert(wert) {
  endeZeit.value = String(wert || '')
  melde()
}

function endeDatumGeaendert(wert) {
  endeDatum.value = String(wert || '')
  endeDatumGesetzt.value = true
  melde()
}

/** „Mehrtägig“ einschalten: Enddatum vorschlagen (nächster Tag). */
function mehrtagEinschalten() {
  if (!datum.value) return
  const d = new Date(`${datum.value}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return
  d.setUTCDate(d.getUTCDate() + 1)
  endeDatum.value = d.toISOString().slice(0, 10)
  endeDatumGesetzt.value = true
  melde()
}

/** Enddatum wieder entfernen — der Termin endet dann am Beginntag. */
function mehrtagAusschalten() {
  endeDatum.value = datum.value
  endeDatumGesetzt.value = true
  melde()
}

const vorschauText = computed(() => {
  const kopf = vorschau(
    datum.value,
    (props.mitZeit && !props.ganztags) ? zeit.value : '',
    '',
  )
  if (!kopf) return ''
  if (!props.mitEnde) return kopf
  if (mehrtaegig.value) {
    // B2: Der mehrtägige Zeitraum wird ausgesprochen, statt ihn zu verschweigen.
    // R-DES-REST (K-a): `kopf` nennt „…, 09:00 Uhr“ schon — deshalb hier NUR
    // der Endteil („– Mi., 25.02.2026, 18:00 Uhr“). Vorher stand die
    // Beginnzeit doppelt, ganztägig ein überzähliges „Uhr“.
    const zEnde = props.ganztags ? '' : `, ${wirksameEndeZeit.value}`
    const vorschlag = (!props.ganztags && endeZeit.value !== wirksameEndeZeit.value)
      ? ' (Vorschlag)' : ''
    const uhr = props.ganztags ? '' : ' Uhr'
    return `${kopf} – ${wochentagKurz(endeDatum.value)}, ${datumDeutschKurz(endeDatum.value)}${zEnde}${uhr}${vorschlag}`
  }
  if (props.ganztags) return kopf
  const z = wirksameEndeZeit.value
  if (!z) return kopf
  const vorschlag = endeZeit.value !== wirksameEndeZeit.value ? ' (Vorschlag)' : ''
  return `${kopf}, ${zeit.value}–${z} Uhr${vorschlag}`
})

function wochentagKurz(d) {
  const m = String(d || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return ''
  const dat = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12))
  return ['So.', 'Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.'][dat.getUTCDay()]
}

function datumDeutschKurz(d) {
  const m = String(d || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  return m ? `${m[3]}.${m[2]}.${m[1]}` : ''
}

</script>

<style scoped>
.dk-ui-datumzeit {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-ui-datumzeit-felder {
  display: flex;
  gap: var(--sp-3);
  flex-wrap: wrap;
  align-items: flex-start;
}
.dk-ui-datumzeit-felder > :first-child { flex: 1 1 170px; min-width: 0; }
.dk-ui-datumzeit-zeit { flex: 0 0 auto; }

/* OP-HANDY-26: Am Handy ist das Zeitfeld ein eigenes Tippziel mit 44 px. */
.dk-ui-datumzeit-eingabe {
  min-height: var(--control-h);
  padding: 0 var(--sp-2);
  width: 100%;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs);
}
.dk-ui-datumzeit-zeit .dk-ui-datumzeit-eingabe { min-width: 118px; }
/* B2: „Ende am“ braucht Platz für ein vollständiges Datum. */
.dk-ui-datumzeit-felder > .dk-ui-datumzeit-zeit:has(input[type="date"]) { flex: 1 1 170px; }
.dk-ui-datumzeit-mehrtag,
.dk-ui-datumzeit-link {
  align-self: flex-start;
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  font-size: var(--fs-sm);
  color: var(--dk-navy-400, var(--accent, currentColor));
  text-decoration: underline;
  cursor: pointer;
}
.dk-ui-datumzeit-mehrtag { text-decoration-style: dashed; }
.dk-ui-datumzeit-mehrtag:disabled,
.dk-ui-datumzeit-link:disabled { opacity: .6; cursor: default; }

.dk-ui-datumzeit-eingabe:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 1px;
}
.dk-ui-datumzeit-eingabe:disabled { opacity: .6; }

.dk-ui-datumzeit-vorschau,
.dk-ui-datumzeit-hinweis {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--muted);
}
@media (pointer: coarse) {
  .dk-ui-datumzeit-eingabe { min-height: 44px; font-size: var(--fs-md, 16px); }
}
</style>
