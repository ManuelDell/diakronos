<template>
  <DkDialog
    :model-value="modelValue"
    :title="erfolgOffen ? 'Mitglied angelegt' : 'Mitglied hinzufügen'"
    :close-on-overlay="false"
    size="md"
    @update:model-value="schliessen"
  >
    <!-- Erfolgsmeldung nach dem Anlegen (Konzept N4, Schritt 4). -->
    <div v-if="erfolgOffen" class="mh-erfolg">
      <DkHint variant="ok">
        <strong>{{ angelegtName }}</strong> wurde als Person angelegt.
        <template v-if="!hatEmail">
          Ohne E-Mail-Adresse wurde kein Zugang erzeugt — die Person wird nur
          als Eintrag geführt.
        </template>
      </DkHint>
      <PasswortLink v-if="erfolgreich.zugang?.link" :daten="erfolgreich.zugang" :name="form.vorname" />
      <DkHint v-if="erfolgreich.warnungen?.length" variant="warn">{{ erfolgreich.warnungen.join(' ') }} Die Person wurde angelegt. Den Zugang kannst du in der Karte „Zugang“ beim Mitglied erneut einrichten.</DkHint>
      <DkHint v-if="erfolgreich.startpasswort" variant="info">Gib das Startpasswort persönlich weiter. Beim ersten Anmelden muss die Person ein anderes Passwort festlegen.</DkHint>
    </div>

    <!-- Eingabeformular -->
    <div v-else class="mh-form">
      <p class="mh-einleitung">
        Trage die Person ein und wähle, ob sie einen Zugang erhalten soll.
        Für einen Zugang ist eine E-Mail-Adresse erforderlich.
      </p>

      <div class="mh-paar">
        <DkField v-slot="feld" label="Vorname" required :error="fehler.vorname">
          <input
            :id="feld.id"
            :aria-describedby="feld['aria-describedby']"
            :aria-invalid="feld['aria-invalid']"
            v-model="form.vorname"
            class="dk-ui-eingabe"
            autocomplete="off"
            @input="dubletteZuruecksetzen"
            @blur="dublettePruefen"
          />
        </DkField>
        <DkField v-slot="feld" label="Nachname" required :error="fehler.nachname">
          <input
            :id="feld.id"
            :aria-describedby="feld['aria-describedby']"
            :aria-invalid="feld['aria-invalid']"
            v-model="form.nachname"
            class="dk-ui-eingabe"
            autocomplete="off"
            @input="dubletteZuruecksetzen"
            @blur="dublettePruefen"
          />
        </DkField>
      </div>

      <div class="mh-paar">
        <DkField
          v-slot="feld"
          label="E-Mail"
          :error="fehler.email"
          help="Ohne E-Mail wird kein Zugang angelegt."
        >
          <input
            :id="feld.id"
            :aria-describedby="feld['aria-describedby']"
            :aria-invalid="feld['aria-invalid']"
            v-model="form.email"
            class="dk-ui-eingabe"
            type="email"
            autocomplete="off"
            @input="dubletteZuruecksetzen"
            @blur="dublettePruefen"
          />
        </DkField>
        <DkField label="Status" required>
          <DkSelect v-model="form.status" :options="statusOptionen" />
        </DkField>
      </div>

      <DkField label="Gruppe" help="Leer lassen, wenn keine Gruppe zugewiesen werden soll.">
        <DkSelect v-model="form.gruppe" :options="gruppeOptionen" empty-value="" />
      </DkField>

      <DkHint v-if="modus === null" variant="info">Anmeldeverfahren wird geladen…</DkHint>
      <DkHint v-else-if="modus" variant="info">Die Person meldet sich über Authentik an. Lege sie dort mit derselben E-Mail-Adresse an. Die Zuordnung erfolgt beim ersten Login; hier entsteht nur der Eintrag.</DkHint>
      <fieldset v-else class="mh-zugang">
        <legend>Zugang zu Diakronos</legend>
        <label><input v-model="zugangsart" type="radio" value="link"> Einladungslink (empfohlen) — die Person vergibt ihr Passwort selbst. Gültig für 7 Tage, einmalig; du teilst den Link selbst.</label>
        <label><input v-model="zugangsart" type="radio" value="startpasswort"> Ich vergebe ein Startpasswort — beim ersten Anmelden ist eine Änderung Pflicht.</label>
        <DkField v-if="zugangsart === 'startpasswort'" v-slot="feld" label="Startpasswort" help="Mindestens 8 Zeichen. Gib es persönlich weiter.">
          <input :id="feld.id" v-model="startpasswort" class="dk-ui-eingabe" :type="passwortSichtbar ? 'text' : 'password'" autocomplete="new-password" minlength="8" maxlength="1024">
          <div class="mh-passwort-aktionen">
            <DkButton variant="secondary" size="sm" @click="passwortVorschlagen">Passwort vorschlagen</DkButton>
            <DkButton variant="secondary" size="sm" :aria-pressed="String(passwortSichtbar)" @click="passwortSichtbar = !passwortSichtbar">{{ passwortSichtbar ? 'Verbergen' : 'Anzeigen' }}</DkButton>
          </div>
        </DkField>
        <label><input v-model="zugangsart" type="radio" value="kein"> Kein Zugang — nur als Eintrag führen.</label>
      </fieldset>

      <!-- Dublettenprüfung beim Tippen (UXD-R15): gleiche E-Mail blockiert,
           gleicher Name warnt nur. Der Hinweis kommt aus dem Server. -->
      <DkHint v-if="dublette" :variant="dubletteBlockiert ? 'err' : 'warn'">
        <template v-if="dubletteBlockiert">
          Diese E-Mail-Adresse gehört bereits zu
          <strong>{{ dubletteAnzeige }}</strong>.
          <template v-if="dublette.mitglied_id">
            Bitte die vorhandene Person
            <button type="button" class="mh-link" @click="vorhandeneOeffnen">öffnen</button>
            statt eine zweite anzulegen.
          </template>
          <template v-else>Bitte eine andere E-Mail-Adresse verwenden.</template>
        </template>
        <template v-else>
          Möglicher Treffer:
          <strong>{{ dubletteAnzeige }}</strong>
          <button type="button" class="mh-link" @click="vorhandeneOeffnen">Öffnen</button>
        </template>
      </DkHint>

      <DkHint v-if="fehler.allgemein" variant="err">{{ fehler.allgemein }}</DkHint>
    </div>

    <template #footer>
      <template v-if="erfolgOffen">
        <DkButton variant="primary" @click="schliessen">Schließen</DkButton>
      </template>
      <template v-else>
        <DkButton variant="secondary" @click="schliessen">Abbrechen</DkButton>
        <DkButton
          variant="primary"
          :loading="laeuft"
          :disabled="!speicherbar"
          @click="anlegen"
        >
          Mitglied anlegen
        </DkButton>
      </template>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * Dialog „Mitglied hinzufügen“ (Neuordnung N4).
 *
 * Konzept Abschnitt 4: Pflicht sind Vorname/Nachname, dazu E-Mail, Status und
 * optional eine Gruppe. Beim Tippen fragt der Dialog den Server, ob dieselbe
 * Person schon existiert (Dublettenprüfung): gleiche E-Mail blockiert das
 * Speichern, gleicher Name warnt nur.
 *
 * N5 ergänzt Einladungslink (Standard) und Startpasswort mit Erstwechsel.
 * Der Server entscheidet das Anmeldeverfahren; bei Authentik entsteht nur
 * der Eintrag. `create_user` bleibt für alte Aufrufer reserviert.
 *
 * Rechte kommen vom Server (create_mitglied/pruefe_mitglied_dublette verlangen
 * „Mitgliederadministrator“); dieser Dialog blendet nichts Sicherheits-
 * relevantes ein oder aus.
 */
import { ref, computed, reactive, watch } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { zugangsmodusLesen } from '../../composables/usePflege.js'
import { navigate } from '../../router.js'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkHint from '../ui/DkHint.vue'
import PasswortLink from './PasswortLink.vue'

const API = 'diakronos.diakonos.api.mitglieder.'
/** Muss zu mitglieder.MITGLIED_STATUS passen (Server prüft den Wert). */
const MITGLIED_STATUS = ['Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast']

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Gruppenauswahl (Komfort) — dieselbe Quelle wie überall. */
  gruppen: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'angelegt'])

const form = reactive({ vorname: '', nachname: '', email: '', status: 'Mitglied', gruppe: '' })
const fehler = reactive({ vorname: '', nachname: '', email: '', allgemein: '' })
// `null`, solange kein Treffer gemeldet ist; sonst {grund, mitglied_id, name, status, gruppen}.
const dublette = ref(null)
let pruefung = 0
const laeuft = ref(false)
const modus = ref(null)
const zugangsart = ref('link')
const startpasswort = ref('')
const passwortSichtbar = ref(false)
const erfolgreich = ref(null)

const statusOptionen = MITGLIED_STATUS.map(s => ({ value: s, label: s }))
const gruppeOptionen = computed(() => [
  { value: '', label: '– Keine Gruppe –' },
  ...props.gruppen.map(g => ({ value: g.name, label: g.gruppenname || g.name })),
])

const dubletteBlockiert = computed(() => dublette.value?.grund === 'email')
const dubletteAnzeige = computed(() => {
  const d = dublette.value
  if (!d) return ''
  const teile = [d.name]
  if (d.status) teile.push(d.status)
  if (d.gruppen?.length) teile.push(d.gruppen.join(', '))
  return teile.filter(Boolean).join(' · ')
})

const speicherbar = computed(() =>
  form.vorname.trim() !== '' && form.nachname.trim() !== '' && !dubletteBlockiert.value && modus.value !== null && !laeuft.value,
)
const hatEmail = computed(() => form.email.trim() !== '')
const angelegtName = computed(() => erfolgreich.value?.name || '')
const erfolgOffen = computed(() => erfolgreich.value !== null)

// Beim Öffnen immer frisch beginnen — kein Rest der letzten Person.
watch(() => props.modelValue, async (offen) => {
  pruefung += 1
  if (!offen) { startpasswort.value = ''; erfolgreich.value = null; return }
  zuruecksetzen()
  modus.value = null
  try {
    const daten = await zugangsmodusLesen()
    modus.value = daten.oidc_aktiv === true
  } catch (e) {
    fehler.allgemein = e?.message || 'Das Anmeldeverfahren konnte nicht geladen werden.'
  }
})

function passwortVorschlagen() {
  const zufall = crypto.getRandomValues(new Uint8Array(12))
  startpasswort.value = Array.from(zufall, z => z.toString(16).padStart(2, '0')).join('')
}

function zuruecksetzen() {
  passwortSichtbar.value = false
  zugangsart.value = 'link'
  startpasswort.value = ''
  form.vorname = ''
  form.nachname = ''
  form.email = ''
  form.status = 'Mitglied'
  form.gruppe = ''
  fehler.vorname = ''
  fehler.nachname = ''
  fehler.email = ''
  fehler.allgemein = ''
  pruefung += 1
  dublette.value = null
  erfolgreich.value = null
  laeuft.value = false
}

function dubletteZuruecksetzen() {
  pruefung += 1
  dublette.value = null
  fehler.allgemein = ''
  fehler.email = ''
}

/** Beim Verlassen eines Feldes den Server nach einem Doppelgaenger fragen. */
async function dublettePruefen() {
  const nummer = ++pruefung
  // Ohne E-Mail und ohne vollen Namen gibt es nichts Sinnvolles zu vergleichen.
  if (!form.email.trim() && !(form.vorname.trim() && form.nachname.trim())) {
    dublette.value = null
    return
  }
  try {
    const res = await apiCall(API + 'pruefe_mitglied_dublette', {
      vorname: form.vorname.trim(),
      nachname: form.nachname.trim(),
      email: form.email.trim(),
    })
    if (nummer === pruefung) dublette.value = res?.dublette || null
  } catch (err) {
    // Die Prüfung ist nur ein Hinweis — ein Fehler darf das Anlegen nicht
    // verhindern. Verbindlich prüft ohnehin `create_mitglied`.
    if (nummer === pruefung) dublette.value = null
    console.error('Dublettenprüfung fehlgeschlagen:', err)
  }
}

function vorhandeneOeffnen() {
  const id = dublette.value?.mitglied_id
  if (!id) return
  emit('update:modelValue', false)
  navigate('#/mitglied/' + encodeURIComponent(id))
}

function pruefefelder() {
  fehler.vorname = form.vorname.trim() ? '' : 'Bitte einen Vornamen angeben.'
  fehler.nachname = form.nachname.trim() ? '' : 'Bitte einen Nachnamen angeben.'
  if (modus.value === false && zugangsart.value !== 'kein' && !form.email.trim()) {
    fehler.email = 'Für einen Zugang bitte eine E-Mail-Adresse angeben.'
    return false
  }
  if (modus.value === false && zugangsart.value === 'startpasswort' && startpasswort.value.length < 8) {
    fehler.allgemein = 'Das Startpasswort muss mindestens 8 Zeichen haben.'
    return false
  }
  const email = form.email.trim()
  fehler.email = email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)
    ? 'Bitte eine gültige E-Mail-Adresse angeben.'
    : ''
  return !fehler.vorname && !fehler.nachname && !fehler.email
}

async function anlegen() {
  if (laeuft.value || modus.value === null) return
  fehler.allgemein = ''
  if (!pruefefelder()) return
  // E-Mail-Dublette ist ein harter Riegel (Konzept Abschnitt 4).
  if (dubletteBlockiert.value) return

  laeuft.value = true
  try {
    const res = await apiCall(API + 'create_mitglied', {
      vorname: form.vorname.trim(),
      nachname: form.nachname.trim(),
      email: form.email.trim(),
      status: form.status,
      gruppe_id: form.gruppe || null,
      // N5: Zugangsart wird serverseitig geprüft; altes Flag bleibt aus.
      create_user: false,
      zugangsart: modus.value ? 'kein' : zugangsart.value,
      startpasswort: modus.value || zugangsart.value !== 'startpasswort' ? '' : startpasswort.value,
    })
    const warnungen = res?.warnungen || []
    if (warnungen.length) {
      showToast(warnungen.join(' '), 'warning')
    }
    erfolgreich.value = {
      name: res?.mitglied_name || `${form.vorname.trim()} ${form.nachname.trim()}`,
      zugang: res?.zugang,
      warnungen,
      startpasswort: zugangsart.value === 'startpasswort' && res?.zugang?.success,
    }
    startpasswort.value = ''
    emit('angelegt', res)
  } catch (err) {
    // Fehler (z. B. E-Mail in der Zwischenzeit vergeben) bleibt im Dialog
    // stehen, damit die Person die Meldung sieht — kein flüchtiger Toast.
    fehler.allgemein = err?.message || 'Das Mitglied konnte nicht angelegt werden.'
  } finally {
    laeuft.value = false
  }
}

function schliessen(offen) {
  // DkDialog meldet `update:modelValue` mit dem neuen Wert (false beim Schließen).
  if (offen === false || offen === undefined) {
    if (laeuft.value) return
    emit('update:modelValue', false)
  }
}
</script>

<style scoped>
.mh-einleitung { margin: 0 0 var(--sp-3); color: var(--muted); font-size: var(--fs-sm); line-height: 1.5; }
.mh-zugang { border: 1px solid var(--line); border-radius: var(--radius); padding: var(--sp-3); display: flex; flex-direction: column; gap: var(--sp-3); }
.mh-zugang label { font-size: var(--fs-sm); }
.mh-passwort-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-top: var(--sp-2); }
.mh-form { display: flex; flex-direction: column; gap: var(--sp-3); }
.mh-paar { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-3); }
.mh-erfolg { display: flex; flex-direction: column; gap: var(--sp-3); }
/* Hinweis-Link im Fließtext (gleiche Optik wie die übrigen Textlinks). */
.mh-link {
  background: none; border: none; padding: 0; margin: 0 2px;
  color: var(--primary); font: inherit; font-weight: 600;
  text-decoration: underline; cursor: pointer;
}
@media (max-width: 520px) {
  .mh-paar { grid-template-columns: 1fr; }
}
</style>
