<template>
  <div class="wf-zeile">
    <div class="wf-zeile-haupt">
      <DkCheckbox
        :model-value="freigabe"
        :disabled="laeuft || !name"
        :aria-label="`Auf Website zeigen: ${titel}`"
        @update:model-value="umschalten"
      >
        <span class="wf-zeile-titel">{{ titel }}</span>
      </DkCheckbox>
      <code v-if="freigabe && slug" class="wf-zeile-slug" :title="`Adresse auf der Website: /${slug}`">/{{ slug }}</code>
      <span v-else-if="freigabe" class="wf-zeile-ohne-slug">noch kein Kürzel</span>
    </div>

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

    <div v-if="zeigeKategorieSchalter" class="wf-zeile-extra">
      <DkCheckbox
        :model-value="nurOeffentlicheKategorien"
        :disabled="laeuft || !name"
        @update:model-value="kategorieUmschalten"
      >
        Nur öffentliche Terminarten zeigen
      </DkCheckbox>
      <p class="wf-zeile-hilfe">{{ kategoriHinweis }}</p>
    </div>

    <div v-if="slugGeaendert" class="wf-zeile-speichern">
      <DkButton size="sm" variant="primary" :loading="laeuft" @click="slugSpeichern">
        Kürzel speichern
      </DkButton>
      <DkButton size="sm" variant="ghost" :disabled="laeuft" @click="slugEingabe = slug">
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
 * Vor dem EINSCHALTEN kommt die Warnung des Aufrufers (`warnung`) — bei
 * Kalendern nennt sie die komplette Beschreibung (Orchestrator-Zusatz).
 *
 * Die Komponente entscheidet nichts selbst: Texte, Slug-Prüfung und die
 * Entscheidung „ist das ein Fehler“ stehen in `shared/website-freigaben.mjs`.
 */
import { computed, ref, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkField from '../ui/DkField.vue'
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
.wf-zeile {
  display: grid;
  gap: var(--sp-2);
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--line);
  min-width: 0;
}
.wf-zeile:first-child { border-top: none; }
.wf-zeile-haupt {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.wf-zeile-titel { font-weight: 600; color: var(--text); }
.wf-zeile-slug,
.wf-zeile-ohne-slug {
  font-size: var(--fs-sm);
  color: var(--muted);
  min-width: 0;
  overflow-wrap: anywhere;
}
.wf-zeile-slug {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
}
.wf-zeile-slugfeld { max-width: 420px; }
.wf-zeile-extra { display: grid; gap: var(--sp-1); }
.wf-zeile-hilfe { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.wf-zeile-speichern { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
</style>
