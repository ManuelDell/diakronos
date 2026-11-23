<template>
  <div class="wf-zeile">
    <!-- BEF-DESIGN-2: EINE Schalterzeile für jede Freigabe. Der Schalter steht
         sichtbar und linksbündig in der Zeile (früher stand das Kästchen je
         nach Umgebung zwischen Absätzen, ohne eigenen Bereich). Der Stand ist
         das Modell; die Rückfrage vor dem EINSCHALTEN entscheidet der
         Aufrufer — deshalb springt hier nichts um, bevor er geantwortet hat. -->
    <DkSchalterZeile
      :model-value="freigabe"
      :aria-label="`Auf Website zeigen: ${titel}`"
      :disabled="laeuft || !name"
      @update:model-value="umschalten"
    >
      <span class="wf-zeile-titel">{{ titel }}</span>
    </DkSchalterZeile>

    <div v-if="freigabe && slug" class="wf-zeile-adresse">
      <code class="wf-zeile-slug" :title="`Adresse auf der Website: /${slug}`">/{{ slug }}</code>
    </div>
    <p v-else-if="freigabe" class="wf-zeile-ohne-slug">noch kein Kürzel</p>

    <!-- Feld und Hilfetext teilen EINE Breite (BEF-DESIGN-2, Befund: das
         Kürzel-Feld war anders breit als sein Hilfetext darunter). -->
    <DkField
      :label="`Kürzel für ${titel}`"
      :help="slugHilfe"
      :error="slugFehler"
      class="wf-zeile-slugfeld"
    >
      <input
        class="dk-ui-eingabe"
        type="text"
        :value="slugEingabe"
        :maxlength="SLUG_MAX"
        :disabled="laeuft || !name"
        :aria-invalid="!!slugFehler"
        autocomplete="off"
        spellcheck="false"
        placeholder="z. B. jugend-freizeit"
        @input="slugEingabe = $event.target.value"
      />
    </DkField>

    <DkSchalterZeile
      v-if="zeigeKategorieSchalter"
      :model-value="nurOeffentlicheKategorien"
      label="Nur öffentliche Terminarten zeigen"
      :help="kategoriHinweis"
      :disabled="laeuft || !name"
      @update:model-value="kategorieUmschalten"
    />

    <div v-if="slugGeaendert" class="wf-zeile-speichern">
      <DkButton size="md" variant="primary" :loading="laeuft" @click="slugSpeichern">
        Kürzel speichern
      </DkButton>
      <DkButton size="md" variant="ghost" :disabled="laeuft" @click="slugEingabe = slug">
        Verwerfen
      </DkButton>
    </div>
  </div>
</template>

<script setup>
/**
 * BS-1d — eine Zeile der Freigabeliste (Kalender oder Gruppe).
 *
 * Der Schalter gilt SOFORT (er ist die Freigabe selbst), der Kürzel erst auf
 * „Kürzel speichern“: ein Tippfehler im Feld darf nicht mit jeder Tastatur-
 * bewegung eine Server-Prüfung auslösen, und ein abgelehnter Slug (vergeben)
 * würde sonst den Schalter mit zurückziehen.
 *
 * BEF-DESIGN-2: Der Aufbau der Zeile kommt aus den gemeinsamen Bausteinen der
 * Formular-Sprache (`DkSchalterZeile`, `DkField`) — nicht mehr aus eigenen
 * Kästchen und Absätzen. Damit stehen Schalter sichtbar und linksbündig,
 * Hilfetexte haben überall denselben Abstand zum Element darüber, und Feld und
 * Hilfetext teilen sich eine Breite.
 *
 * Vor dem EINSCHALTEN kommt die Warnung des Aufrufers (`warnung`) — bei
 * Kalendern nennt sie die komplette Beschreibung (Orchestrator-Zusatz).
 *
 * Die Komponente entscheidet nichts selbst: Texte, Slug-Prüfung und die
 * Entscheidung „ist das ein Fehler“ stehen in `shared/website-freigaben.mjs`.
 */
import { computed, ref, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import DkSchalterZeile from '../ui/DkSchalterZeile.vue'
import { SLUG_MAX, slugPruefen } from '../../../shared/website-freigaben.mjs'

const props = defineProps({
  /** Anzeigename (Kalender- oder Gruppenname) — nie die interne Kennung. */
  titel: { type: String, default: '' },
  /** Interne Kennung — wird nur mitgeschickt, nie angezeigt. */
  name: { type: String, default: '' },
  freigabe: Boolean,
  slug: { type: String, default: '' },
  nurOeffentlicheKategorien: Boolean,
  /** Zeigt den Schalter „Nur öffentliche Terminarten“ (nur Kalender). */
  zeigeKategorieSchalter: Boolean,
  /** Text unter dem Kategorie-Schalter (siehe `kategorieHinweis`). */
  kategoriHinweis: { type: String, default: '' },
  laeuft: Boolean,
  /** Fehlermeldung des Servers zu DIESER Zeile. */
  fehler: { type: String, default: '' },
})
const emit = defineEmits(['freigabe', 'nur-oeffentliche-kategorien', 'slug'])

const slugEingabe = ref(props.slug || '')
const slugFehlerLokal = ref('')

// Ändert der Server den Slug (Antwort nach dem Freigeben leitet einen ab),
// zeigt das Feld den gespeicherten Wert. Eine laufende Eingabe wird nicht
// überschrieben, solange sie sich vom alten Wert unterscheidet.
watch(() => props.slug, (neu, alt) => {
  if (String(slugEingabe.value || '') === String(alt || '')) slugEingabe.value = neu || ''
})

const slugGeaendert = computed(() => String(slugEingabe.value || '').trim() !== String(props.slug || '').trim())
const slugFehler = computed(() => slugFehlerLokal.value || (slugGeaendert.value ? '' : props.fehler))

/**
 * Der Schalter trägt KEINEN Hilfetext und KEINE Servermeldung mehr (R1):
 * der Schalter sagt selbst, was er tut („keine Bemutterung“), und die
 * Servermeldung dieser Zeile steht schon am Kürzel-Feld (`slugFehler`) —
 * zweimal `role="alert"` wäre eine doppelte Vorlesung. Der lange Warnsatz vor
 * dem EINSCHALTEN steht in der Rückfrage (`bestaetigen`).
 */
const slugHilfe = computed(() => (
  props.freigabe
    ? 'Der Kürzel ist der Name in der Adresse der Website. Kleinbuchstaben, Ziffern, Bindestrich.'
    : 'Erst nach dem Einschalten nötig — er wird sonst aus dem Namen abgeleitet.'
))

async function umschalten(wert) {
  // Ausschalten ist immer frei; EINSCHALTEN geht über die Warnung des Aufrufers.
  emit('freigabe', { an: wert === true, slug: String(slugEingabe.value || '').trim() })
}

function kategorieUmschalten(wert) {
  emit('nur-oeffentliche-kategorien', wert === true)
}

function slugSpeichern() {
  const ergebnis = slugPruefen(slugEingabe.value)
  if (!ergebnis.ok) {
    slugFehlerLokal.value = ergebnis.fehler
    return
  }
  slugFehlerLokal.value = ''
  emit('slug', ergebnis.slug)
}

defineExpose({ slugEingabe })
</script>

<style scoped>
/* EINE Freigabezeile = EINE Gruppe (Faktor 1): Schalter, Adresse, Kürzel-Feld
   und der Terminarten-Schalter gehören zusammen; getrennt werden die Zeilen
   durch den Abstand des Aufrufers und die Haarlinie. */
.wf-zeile {
  display: grid;
  gap: var(--gap);
  padding: var(--sp-3) 0;
  border-top: var(--rahmen-breite) solid var(--line);
  min-width: 0;
}
.wf-zeile:first-child { border-top: none; }
/* Der Titel ist die Beschriftung des Schalters und steht wieder fett
   (Schriftgewicht aus Token, kein fester Wert). */
.wf-zeile-titel { font-weight: var(--fw-fett); }
.wf-zeile-adresse { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); min-width: 0; }
.wf-zeile-slug,
.wf-zeile-ohne-slug {
  font-size: var(--fs-sm);
  color: var(--muted);
  min-width: 0;
  overflow-wrap: anywhere;
}
.wf-zeile-slug {
  background: var(--surface-2);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
}
.wf-zeile-ohne-slug { margin: 0; }
.wf-zeile-slugfeld { width: 100%; }
.wf-zeile-speichern { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
</style>
