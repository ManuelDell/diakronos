<template>
  <div class="rv-seite">
    <DkPageHeader
      title="Räume & Gegenstände verwalten"
      sub="Räume, Fahrzeuge und Gegenstände anlegen, ändern, stilllegen oder entfernen."
      :krumen="[{ text: 'Ressourcen', href: '#/ressourcen' }, { text: 'Verwalten' }]"
    >
      <template #actions>
        <DkButton variant="primary" @click="neu">
          <IconPlus /> Neue Ressource
        </DkButton>
      </template>
    </DkPageHeader>

    <DkHint variant="info">
      „In Wartung“ nimmt einen Raum aus der Buchung heraus, ohne ihn zu löschen —
      praktisch bei Renovierung oder Reparatur. Entfernen geht nur, solange keine
      Buchung und kein Termin mehr daran hängt.
    </DkHint>

    <div v-if="laedt" class="rv-zustand">Räume und Gegenstände werden geladen …</div>

    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

    <DkCard v-else flach>
      <DkTable
        :spalten="spalten"
        :leer="zeilen.length === 0"
        leer-titel="Noch nichts angelegt"
        leer-text="Lege den ersten Raum oder Gegenstand an."
      >
        <tr v-for="r in zeilen" :key="r.id">
          <td>{{ r.name }}</td>
          <td>{{ r.typ }}</td>
          <td>{{ r.kapazitaet ?? '–' }}</td>
          <td>
            <DkBadge v-if="r.wartung" variant="warn">In Wartung</DkBadge>
            <span v-else class="rv-muted">verfügbar</span>
          </td>
          <td class="rv-aktionen">
            <DkButton variant="secondary" size="sm" @click="bearbeiten(r)">Bearbeiten</DkButton>
            <DkButton variant="danger" size="sm" @click="entfernen(r)">Löschen</DkButton>
          </td>
        </tr>
      </DkTable>
    </DkCard>

    <DkDialog
      v-model="dialogOffen"
      :title="bearbeitet ? `„${form.name}“ bearbeiten` : 'Neue Ressource'"
      size="md"
      :before-close="schutz.darfSchliessen"
    >
      <form id="rv-form" novalidate class="rv-formular" @submit.prevent="speichern">
        <DkHint v-if="formFehler.allgemein" variant="err">{{ formFehler.allgemein }}</DkHint>

        <DkField v-slot="feld" label="Name" required :error="formFehler.name">
          <input :id="feld.id" v-model="form.name" class="dk-ui-eingabe" maxlength="140"
                 placeholder="z. B. Gemeindesaal" />
        </DkField>

        <DkField label="Art">
          <DkSelect v-model="form.typ" :options="artenOptionen" />
        </DkField>

        <DkField v-slot="feld" label="Kapazität" help="Wie viele Personen passen hinein? Leer lassen, wenn unbekannt."
                 :error="formFehler.kapazitaet">
          <input :id="feld.id" v-model="form.kapazitaet" type="number" min="0"
                 class="dk-ui-eingabe" inputmode="numeric" />
        </DkField>

        <DkField v-slot="feld" label="Beschreibung">
          <textarea :id="feld.id" v-model="form.beschreibung" class="dk-ui-eingabe" rows="2"
                    maxlength="500"></textarea>
        </DkField>

        <DkField v-slot="feld" label="Schlagwörter" help="Mit Komma getrennt, z. B. „barrierefrei, Küche“.">
          <input :id="feld.id" v-model="form.tags" class="dk-ui-eingabe" maxlength="300" />
        </DkField>

        <DkCheckbox v-model="form.wartung">
          In Wartung — kann in dieser Zeit nicht gebucht werden
        </DkCheckbox>
      </form>

      <template #footer>
        <DkButton variant="ghost" :disabled="speichert" @click="schliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="rv-form" :loading="speichert">
          {{ bearbeitet ? 'Speichern' : 'Anlegen' }}
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * RessourcenVerwaltung — Räume, Fahrzeuge und Gegenstände pflegen
 * (Nachtbefund OP-ADMIN-11).
 *
 * Vorher gab es keinen Weg: die 7 Bestandsräume stammten aus dem Import, und
 * weder ein neuer Raum noch eine Korrektur noch ein Entfernen waren möglich.
 * Das Feld „Wartung“ (das `get_ressourcen_liste` als Status „maintenance“
 * auswertet) war überhaupt nicht erreichbar.
 *
 * Rechte: alles serverseitig (`get_ressourcen_verwaltung` & Co., nur
 * Ressourcenmoderator/Administrator). Ohne Recht kommt eine verständliche
 * Meldung statt einer leeren Liste.
 */
import { computed, reactive, ref, onMounted, h } from 'vue'
import { showToast } from '../composables/useToast.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import {
  ressourcenVerwaltungLaden,
  ressourceAnlegen,
  ressourceAendern,
  ressourceLoeschen,
  serverFehlerText,
} from '../composables/useVerwaltung.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkHint from '../components/ui/DkHint.vue'

const IconPlus = () => h('svg', {
  width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
}, [h('line', { x1: 12, y1: 5, x2: 12, y2: 19 }), h('line', { x1: 5, y1: 12, x2: 19, y2: 12 })])

const spalten = [
  { key: 'name', label: 'Name' },
  { key: 'typ', label: 'Art' },
  { key: 'kapazitaet', label: 'Kapazität', numeric: true },
  { key: 'status', label: 'Zustand' },
  { key: 'aktionen', label: 'Aktionen' },
]

const zeilen = ref([])
const arten = ref(['Raum', 'Fahrzeug', 'Gegenstand'])
const laedt = ref(true)
const fehler = ref('')
const speichert = ref(false)
const dialogOffen = ref(false)
const bearbeitet = ref(null)

const artenOptionen = computed(() => arten.value.map(a => ({ value: a, label: a })))

const formFehler = reactive({ name: '', kapazitaet: '', allgemein: '' })

function leeresFormular() {
  return { name: '', typ: 'Raum', kapazitaet: '', beschreibung: '', tags: '', wartung: false }
}
const form = reactive(leeresFormular())

const schutz = useFormularSchutz(() => [form], () => speichert.value)

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await ressourcenVerwaltungLaden()
    zeilen.value = Array.isArray(antwort?.ressourcen) ? antwort.ressourcen : []
    if (Array.isArray(antwort?.arten) && antwort.arten.length) arten.value = antwort.arten
  } catch (err) {
    fehler.value = serverFehlerText(err, 'Die Räume und Gegenstände konnten nicht geladen werden.')
  } finally {
    laedt.value = false
  }
}

function neu() {
  bearbeitet.value = null
  Object.assign(form, leeresFormular())
  formFehler.name = ''
  formFehler.kapazitaet = ''
  formFehler.allgemein = ''
  schutz.merken()
  dialogOffen.value = true
}

function bearbeiten(r) {
  bearbeitet.value = r
  Object.assign(form, {
    name: r.name,
    typ: r.typ || 'Raum',
    kapazitaet: r.kapazitaet ?? '',
    beschreibung: r.beschreibung || '',
    tags: r.tags || '',
    wartung: !!r.wartung,
  })
  formFehler.name = ''
  formFehler.kapazitaet = ''
  formFehler.allgemein = ''
  schutz.merken()
  dialogOffen.value = true
}

async function schliessen() {
  if (await schutz.darfSchliessen()) dialogOffen.value = false
}

async function speichern() {
  if (speichert.value) return
  formFehler.name = ''
  formFehler.kapazitaet = ''
  formFehler.allgemein = ''

  if (!form.name.trim()) {
    formFehler.name = 'Bitte einen Namen angeben.'
    return
  }
  const kap = String(form.kapazitaet ?? '').trim()
  if (kap && !/^\d+$/.test(kap)) {
    formFehler.kapazitaet = 'Bitte eine ganze Zahl angeben.'
    return
  }

  speichert.value = true
  try {
    const daten = {
      name: form.name.trim(),
      typ: form.typ,
      kapazitaet: kap === '' ? null : kap,
      beschreibung: form.beschreibung,
      tags: form.tags,
      wartung: form.wartung ? 1 : 0,
    }
    if (bearbeitet.value) {
      await ressourceAendern(bearbeitet.value.id, daten)
      showToast('Ressource gespeichert')
    } else {
      await ressourceAnlegen(daten)
      showToast('Ressource angelegt')
    }
    schutz.merken()
    dialogOffen.value = false
    await laden()
  } catch (err) {
    formFehler.allgemein = serverFehlerText(err, 'Die Ressource konnte nicht gespeichert werden.')
  } finally {
    speichert.value = false
  }
}

async function entfernen(r) {
  const ok = await bestaetigen({
    titel: `„${r.name}“ löschen?`,
    text: 'Die Ressource wird entfernt. Das geht nur, wenn keine Buchung und kein Termin daran hängt.',
    aktion: 'Löschen',
    gefahr: true,
  })
  if (!ok) return
  try {
    await ressourceLoeschen(r.id)
    showToast('Ressource gelöscht')
    await laden()
  } catch (err) {
    showToast(serverFehlerText(err, 'Die Ressource konnte nicht gelöscht werden.'), 'error')
  }
}

onMounted(laden)
</script>

<style scoped>
.rv-seite { display: flex; flex-direction: column; gap: var(--sp-4); }
.rv-zustand { color: var(--muted); padding: var(--sp-4) 0; }
.rv-muted { color: var(--muted); font-size: var(--fs-sm); }
.rv-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.rv-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
