<template>
  <div class="kv-seite">
    <DkPageHeader
      title="Kalender verwalten"
      sub="Anlegen, umbenennen, Rechte vergeben, Moderatoren bestimmen und löschen."
      :krumen="[{ text: 'Kalender', href: '#/kalender' }, { text: 'Verwalten' }]"
    >
      <template #actions>
        <DkButton variant="primary" @click="neuerKalender">
          <IconPlus /> Neuer Kalender
        </DkButton>
      </template>
    </DkPageHeader>

    <DkHint variant="info">
      Wer einen Kalender <strong>sehen</strong>, <strong>Termine eintragen</strong> oder
      <strong>Termine freigeben</strong> (moderieren) darf, wird hier über Rollen und
      Personen eingestellt. Die Änderungen wirken sofort — niemand muss sich neu anmelden.
    </DkHint>

    <div v-if="laedt" class="kv-zustand">Kalender werden geladen …</div>

    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

    <DkEmpty
      v-else-if="kalender.length === 0"
      title="Noch keine Kalender"
      text="Lege den ersten Kalender an — zum Beispiel „Gemeinde“ oder „Jugend“."
      icon="📅"
    >
      <DkButton variant="primary" @click="neuerKalender">Neuer Kalender</DkButton>
    </DkEmpty>

    <div v-else class="kv-karten">
      <DkCard v-for="k in kalender" :key="k.name" flach>
        <div class="kv-karte">
          <div class="kv-karte-kopf">
            <span class="kv-farbe" :style="{ background: k.farbe }" aria-hidden="true"></span>
            <div class="kv-karte-titel">
              <h2 class="kv-name">{{ k.titel }}</h2>
              <p class="kv-meta">
                <span v-if="k.selbstverwaltet">Selbstverwaltet</span>
                <span v-if="k.selbstverwaltet">·</span>
                <span>{{ k.leserechte.length ? 'Lesbar: ' + k.leserechte.join(', ') : 'Niemand darf lesen' }}</span>
              </p>
            </div>
            <div class="kv-karte-aktionen">
              <DkButton variant="secondary" size="sm" @click="bearbeiten(k)">Bearbeiten</DkButton>
              <DkButton variant="danger" size="sm" @click="kalenderEntfernen(k)">Löschen</DkButton>
            </div>
          </div>

          <dl class="kv-listen">
            <div class="kv-liste">
              <dt>Termine eintragen</dt>
              <dd>{{ k.schreibrechte.length ? k.schreibrechte.join(', ') : 'niemand' }}</dd>
            </div>
            <div class="kv-liste">
              <dt>Termine freigeben</dt>
              <dd>{{ k.moderatoren.length ? k.moderatoren.join(', ') : 'niemand' }}</dd>
            </div>
          </dl>
        </div>
      </DkCard>
    </div>

    <!-- Anlegen / Bearbeiten -->
    <DkDialog
      v-model="dialogOffen"
      :title="bearbeitet ? `Kalender „${form.titel}“ bearbeiten` : 'Neuer Kalender'"
      size="md"
      :before-close="schutz.darfSchliessen"
    >
      <form id="kv-form" novalidate class="kv-formular" @submit.prevent="speichern">
        <DkHint v-if="formFehler.allgemein" variant="err">{{ formFehler.allgemein }}</DkHint>

        <DkField v-slot="feld" label="Name" required :error="formFehler.titel"
                 help="So heißt der Kalender in allen Listen und Auswahlfeldern.">
          <input :id="feld.id" v-model="form.titel" class="dk-ui-eingabe" maxlength="140" />
        </DkField>

        <DkField v-slot="feld" label="Farbe"
                 help="Die Farbe der Termine in der Kalenderansicht.">
          <div class="kv-farbe-zeile">
            <input :id="feld.id" v-model="form.farbe" type="color" class="kv-farbe-feld" />
            <span class="kv-farbe-wert">{{ form.farbe }}</span>
          </div>
        </DkField>

        <DkCheckbox v-model="form.selbstverwaltet">
          Selbstverwaltet (eine Gruppe pflegt diesen Kalender selbst)
        </DkCheckbox>

        <DkField label="Wer darf sehen" help="Mehrfachauswahl mit Strg/Cmd.">
          <select v-model="form.leserechte" class="dk-ui-eingabe" multiple size="6">
            <option v-for="r in rollen" :key="r" :value="r">{{ r }}</option>
          </select>
        </DkField>

        <DkField label="Wer darf Termine eintragen" help="Mehrfachauswahl mit Strg/Cmd.">
          <select v-model="form.schreibrechte" class="dk-ui-eingabe" multiple size="6">
            <option v-for="r in rollen" :key="r" :value="r">{{ r }}</option>
          </select>
        </DkField>

        <DkField
          label="Wer darf Termine freigeben"
          help="Personen (Konten), nicht Rollen. Freigeben heißt: Vorschläge als Termin bestätigen."
        >
          <select v-model="form.moderatoren" class="dk-ui-eingabe" multiple size="6">
            <option v-for="u in personen" :key="u.wert" :value="u.wert">{{ u.text }}</option>
          </select>
        </DkField>
        <p v-if="personen.length === 0" class="kv-hinweis">
          Es wurden keine Konten gefunden, die hier eingetragen werden könnten.
        </p>
      </form>

      <template #footer>
        <DkButton variant="ghost" :disabled="speichert" @click="schliessen">Abbrechen</DkButton>
        <DkButton variant="primary" type="submit" form="kv-form" :loading="speichert">
          {{ bearbeitet ? 'Speichern' : 'Anlegen' }}
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * KalenderVerwaltung — Kalender anlegen, umbenennen, Rechte und Moderatoren
 * setzen, löschen (Nachtbefund OP-ADMIN-10).
 *
 * Vorher gab es diese Seite nicht: Kalender entstanden nur über den iCal-
 * Import, Rechte waren nirgends einstellbar, und das ✎ in der Kalenderliste
 * sah klickbar aus, tat aber nichts (es bedeutet „du hast Schreibrecht“).
 *
 * Rechte: alles serverseitig (`kalender_verwaltung`). Die Seite ist nur für
 * Kalenderadministratoren erreichbar; wer sie ohne Recht aufruft, bekommt
 * eine verständliche Meldung statt einer leeren Liste.
 */
import { computed, reactive, ref, onMounted, h } from 'vue'
import { showToast } from '../composables/useToast.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import {
  kalenderVerwaltungLaden,
  kalenderAnlegen,
  kalenderAendern,
  kalenderLoeschen,
  kontenListe,
  serverFehlerText,
} from '../composables/useVerwaltung.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
import DkHint from '../components/ui/DkHint.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'

const IconPlus = () => h('svg', {
  width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
}, [h('line', { x1: 12, y1: 5, x2: 12, y2: 19 }), h('line', { x1: 5, y1: 12, x2: 19, y2: 12 })])

const STANDARD_FARBE = '#3b82f6'

const kalender = ref([])
const rollen = ref([])
const laedt = ref(true)
const fehler = ref('')
const speichert = ref(false)
const dialogOffen = ref(false)
const bearbeitet = ref(null)
const personen = ref([])

const formFehler = reactive({ titel: '', allgemein: '' })

function leeresFormular() {
  return {
    titel: '',
    farbe: STANDARD_FARBE,
    selbstverwaltet: false,
    leserechte: [],
    schreibrechte: [],
    moderatoren: [],
  }
}
const form = reactive(leeresFormular())

// Eingaben bei Fehlklick nicht verlieren (gleiche Mechanik wie die übrigen
// Verwaltungsseiten).
const schutz = useFormularSchutz(
  () => [form], () => speichert.value,
)

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await kalenderVerwaltungLaden()
    kalender.value = Array.isArray(antwort?.kalender) ? antwort.kalender : []
    rollen.value = Array.isArray(antwort?.rollen) ? antwort.rollen : []
  } catch (err) {
    fehler.value = serverFehlerText(err, 'Die Kalender konnten nicht geladen werden.')
  } finally {
    laedt.value = false
  }
}

/** Konten für die Moderatorenauswahl — nur wenn die Liste gebraucht wird. */
async function personenLaden() {
  if (personen.value.length) return
  try {
    const konten = await kontenListe()
    personen.value = konten
      .map(k => ({ wert: k.user, text: k.email ? `${k.name} (${k.email})` : k.name }))
      .filter(p => p.wert)
      .sort((a, b) => a.text.localeCompare(b.text, 'de'))
  } catch {
    personen.value = []
  }
}

function neuerKalender() {
  bearbeitet.value = null
  Object.assign(form, leeresFormular())
  formFehler.titel = ''
  formFehler.allgemein = ''
  schutz.merken()
  dialogOffen.value = true
  personenLaden()
}

function bearbeiten(k) {
  bearbeitet.value = k
  Object.assign(form, {
    titel: k.titel,
    farbe: /^#[0-9a-f]{6}$/i.test(k.farbe || '') ? k.farbe : STANDARD_FARBE,
    selbstverwaltet: !!k.selbstverwaltet,
    leserechte: [...k.leserechte],
    schreibrechte: [...k.schreibrechte],
    moderatoren: [...k.moderatoren],
  })
  formFehler.titel = ''
  formFehler.allgemein = ''
  schutz.merken()
  dialogOffen.value = true
  personenLaden()
}

async function schliessen() {
  if (await schutz.darfSchliessen()) dialogOffen.value = false
}

async function speichern() {
  if (speichert.value) return
  formFehler.titel = ''
  formFehler.allgemein = ''
  if (!form.titel.trim()) {
    formFehler.titel = 'Bitte einen Namen angeben.'
    return
  }
  speichert.value = true
  try {
    const daten = {
      titel: form.titel.trim(),
      farbe: form.farbe,
      selbstverwaltet: form.selbstverwaltet ? 1 : 0,
      leserechte: form.leserechte,
      schreibrechte: form.schreibrechte,
      moderatoren: form.moderatoren,
    }
    if (bearbeitet.value) {
      await kalenderAendern(bearbeitet.value.name, daten)
      showToast('Kalender gespeichert')
    } else {
      await kalenderAnlegen(daten)
      showToast('Kalender angelegt')
    }
    schutz.merken()
    dialogOffen.value = false
    await laden()
  } catch (err) {
    formFehler.allgemein = serverFehlerText(err, 'Der Kalender konnte nicht gespeichert werden.')
  } finally {
    speichert.value = false
  }
}

async function kalenderEntfernen(k) {
  const ok = await bestaetigen({
    titel: `Kalender „${k.titel}“ löschen?`,
    text: 'Der Kalender wird entfernt. Das geht nur, solange keine Termine darin stehen.',
    aktion: 'Löschen',
    gefahr: true,
  })
  if (!ok) return
  try {
    await kalenderLoeschen(k.name)
    showToast('Kalender gelöscht')
    await laden()
  } catch (err) {
    showToast(serverFehlerText(err, 'Der Kalender konnte nicht gelöscht werden.'), 'error')
  }
}

onMounted(laden)
</script>

<style scoped>
.kv-seite { display: flex; flex-direction: column; gap: var(--sp-4); }

.kv-zustand { color: var(--muted); padding: var(--sp-4) 0; }

.kv-karten { display: grid; gap: var(--sp-3); grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.kv-karte { display: flex; flex-direction: column; gap: var(--sp-3); padding: calc(var(--pad) * 1.2); }
.kv-karte-kopf { display: flex; align-items: flex-start; gap: var(--sp-3); flex-wrap: wrap; }
.kv-farbe { width: 14px; height: 14px; border-radius: 4px; flex-shrink: 0; margin-top: 6px; }
.kv-karte-titel { flex: 1 1 160px; min-width: 0; }
.kv-name { font-size: var(--fs-h3); font-weight: var(--fw-h); margin: 0; }
.kv-meta { font-size: var(--fs-sm); color: var(--muted); margin: 2px 0 0; display: flex; gap: 4px; flex-wrap: wrap; }
.kv-karte-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }

.kv-listen { margin: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.kv-liste { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2px; }
.kv-liste dt { font-size: var(--fs-sm); color: var(--muted); }
.kv-liste dd { margin: 0; color: var(--text); word-break: break-word; }

.kv-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.kv-farbe-zeile { display: flex; align-items: center; gap: var(--sp-2); }
.kv-farbe-feld { width: 56px; height: 32px; padding: 0; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
.kv-farbe-wert { font-size: var(--fs-sm); color: var(--muted); }
.kv-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0; }

@media (max-width: 640px) {
  .kv-karte-aktionen { width: 100%; }
}
</style>
