<template>
  <DkCard title="Verantwortliche">
    <template #actions>
      <DkButton v-if="darfPflegen && !bearbeiten" variant="ghost" size="sm" @click="startBearbeiten">
        Bearbeiten
      </DkButton>
    </template>

    <p class="verw-hinweis">
      Verantwortliche dürfen Pläne dieser Gruppe erstellen und bearbeiten.
      Auswählbar sind nur Personen mit einem Zugang (Konto).
    </p>

    <div v-if="laedt" class="verw-zustand">Lade…</div>
    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

    <template v-else>
      <!-- Anzeige -->
      <template v-if="!bearbeiten">
        <DkEmpty v-if="!ausgewaehlt.length" title="Keine Verantwortlichen eingetragen" icon="👤" />
        <ul v-else class="verw-liste">
          <li v-for="v in ausgewaehlt" :key="v.user" class="verw-eintrag">
            <span class="verw-name">{{ v.anzeige }}</span>
            <span v-if="v.email" class="verw-email">{{ v.email }}</span>
          </li>
        </ul>
      </template>

      <!-- Bearbeiten -->
      <div v-else class="verw-formular">
        <ul class="verw-liste">
          <li v-for="v in ausgewaehlt" :key="v.user" class="verw-eintrag">
            <span class="verw-name">{{ v.anzeige }}</span>
            <button type="button" class="verw-entfernen" @click="entfernen(v.user)">Entfernen</button>
          </li>
        </ul>
        <DkField label="Person hinzufügen">
          <input
            v-model="suche"
            class="dk-ui-eingabe"
            type="text"
            placeholder="Name eingeben…"
            aria-label="Person suchen"
          />
        </DkField>
        <ul v-if="treffer.length" class="verw-treffer">
          <li
            v-for="t in treffer"
            :key="t.user"
            class="verw-eintrag verw-eintrag--treffer"
            @click="hinzufuegen(t)"
          >
            <span class="verw-name">{{ t.name }}</span>
          </li>
        </ul>
        <p v-else-if="suche" class="verw-leer">Keine passende Person mit Zugang gefunden.</p>

        <div class="verw-aktionen">
          <DkButton variant="primary" size="sm" :loading="speichert" @click="speichern">Speichern</DkButton>
          <DkButton variant="ghost" size="sm" @click="abbrechen">Abbrechen</DkButton>
        </div>
      </div>
    </template>
  </DkCard>
</template>

<script setup>
/**
 * VerantwortlicheKarte — Personen mit Konto als Verantwortliche pflegen
 * (OP-CHOR-3 / OP-ADMIN-4, P1-8).
 *
 * Die Rechte kommen vom SERVER: `darf_pflegen` steuert nur den Knopf, die
 * Zuweisung selbst prueft das Backend. Auswählbar sind NUR Personen mit
 * Zugang — eine Person ohne Konto kann kein Recht ausueben (darum liefert
 * `get_verantwortliche_auswahl` genau diese Liste).
 *
 * Die Karte arbeitet für Dienstbereich, Gruppe und Untergruppe; `doctype`
 * waehlt die Ebene. Nach dem Speichern meldet sie über `gespeichert`, damit
 * die Seite ihre Sichtbarkeit neu laden kann.
 */
import { ref, computed, watch, onMounted } from 'vue'
import DkCard from './ui/DkCard.vue'
import DkButton from './ui/DkButton.vue'
import DkField from './ui/DkField.vue'
import DkHint from './ui/DkHint.vue'
import DkEmpty from './ui/DkEmpty.vue'
import { verantwortlicheLesen, verantwortlicheSetzen, verantwortlicheAuswahl } from '../composables/usePflege.js'
import { showToast } from '../composables/useToast.js'

const props = defineProps({
  // 'Dienstbereich' | 'Gruppe' | 'Untergruppe'
  doctype: { type: String, required: true },
  name: { type: String, required: true },
})
const emit = defineEmits(['gespeichert'])

const laedt = ref(true)
const fehler = ref('')
const darfPflegen = ref(false)
const ausgewaehlt = ref([])
const bearbeiten = ref(false)
const speichert = ref(false)
const suche = ref('')
const trefferListe = ref([])

const treffer = computed(() => trefferListe.value.filter(
  (t) => !ausgewaehlt.value.some((v) => v.user === t.user)
))

async function laden() {
  if (!props.name) return
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await verantwortlicheLesen(props.doctype, props.name)
    ausgewaehlt.value = daten.verantwortliche || []
    darfPflegen.value = !!daten.darf_pflegen
  } catch (e) {
    fehler.value = e?.message || 'Verantwortliche konnten nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

async function trefferLaden() {
  if (!bearbeiten.value) return
  try {
    const daten = await verantwortlicheAuswahl(props.doctype, props.name, suche.value)
    trefferListe.value = daten.auswahl || []
  } catch {
    trefferListe.value = []
  }
}

function startBearbeiten() {
  bearbeiten.value = true
  suche.value = ''
  trefferLaden()
}

function hinzufuegen(t) {
  if (!ausgewaehlt.value.some((v) => v.user === t.user)) {
    ausgewaehlt.value = [...ausgewaehlt.value, { user: t.user, anzeige: t.name, email: null }]
  }
  suche.value = ''
}

function entfernen(user) {
  ausgewaehlt.value = ausgewaehlt.value.filter((v) => v.user !== user)
}

function abbrechen() {
  bearbeiten.value = false
  laden()
}

async function speichern() {
  speichert.value = true
  try {
    await verantwortlicheSetzen(props.doctype, props.name, ausgewaehlt.value.map((v) => v.user))
    bearbeiten.value = false
    await laden()
    showToast('Verantwortliche gespeichert.', 'success')
    emit('gespeichert')
  } catch (e) {
    showToast(e?.message || 'Speichern fehlgeschlagen.', 'error')
  } finally {
    speichert.value = false
  }
}

let timer = null
watch(suche, () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(trefferLaden, 250)
})

onMounted(laden)
watch(() => [props.doctype, props.name], laden)
</script>

<style scoped>
.verw-hinweis {
  font-size: var(--fs-sm);
  color: var(--text-muted);
  margin: 0 0 var(--sp-3);
}
.verw-zustand { color: var(--text-muted); padding: var(--sp-3) 0; }
.verw-liste { list-style: none; margin: 0; padding: 0; }
.verw-eintrag {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: 1px solid var(--line);
}
.verw-eintrag--treffer { cursor: pointer; }
.verw-eintrag--treffer:hover { background: var(--surface-2, #f5f6f8); }
.verw-name { font-weight: var(--fw-medium, 500); }
.verw-email { color: var(--text-muted); font-size: var(--fs-sm); }
.verw-entfernen {
  background: none;
  border: none;
  color: var(--dk-err, #b42318);
  cursor: pointer;
  font-size: var(--fs-sm);
  padding: 0;
}
.verw-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.verw-treffer { list-style: none; margin: 0; padding: 0; max-height: 12rem; overflow: auto; }
.verw-leer { color: var(--text-muted); font-size: var(--fs-sm); margin: 0; }
.verw-aktionen { display: flex; gap: var(--sp-2); }
</style>
