<template>
  <div class="rr-abschnitt">
    <h2>Rollen &amp; Rechte</h2>
    <p>Hier siehst du, wer welche Rolle hat. Rollen bestimmen, was jemand darf —
      Verantwortliche bestimmen zusätzlich, wer einen Bereich oder eine Gruppe
      pflegen darf.</p>

    <DkHint v-if="laedt" role="status">Übersicht wird geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>
    <p v-if="erfolg" role="status">{{ erfolg }}</p>

    <template v-if="geladen">
      <!-- ── Rollen je Person ───────────────────────────────────────────── -->
      <DkCard title="Wer hat welche Rolle">
        <p class="rr-hilfe">Jede Person mit Zugang erscheint hier. Antippen öffnet die Rollenauswahl.
          Rollen mit Verwaltungsrechten darf nur ein System Manager vergeben oder entziehen.</p>

        <DkField label="Person suchen" v-slot="feld">
          <input v-bind="feld" v-model="suche" class="dk-ui-eingabe" type="search"
            placeholder="Name oder E-Mail …" aria-label="Person suchen" />
        </DkField>

        <DkEmpty v-if="!gefiltert.length" title="Keine passende Person" icon="👤" />
        <ul v-else class="rr-liste">
          <li v-for="k in gefiltert" :key="k.user" class="rr-zeile">
            <div class="rr-person">
              <span class="rr-name">{{ k.anzeige }}</span>
              <span class="rr-unter">{{ k.email || k.user }}</span>
              <span v-if="!k.enabled" class="rr-schild rr-schild--gesperrt">Gesperrt</span>
              <span v-else-if="k.ausgeschlossen" class="rr-schild rr-schild--raus">Ausgeschlossen</span>
              <span v-if="k.hinweis" class="rr-hinweis">{{ k.hinweis }}</span>
            </div>
            <div class="rr-rollen">
              <span v-for="r in k.rollen" :key="r" class="rr-chip">{{ r }}</span>
              <span v-if="!k.rollen.length" class="rr-unter">Keine Rolle</span>
            </div>
            <DkButton variant="ghost" size="sm" :disabled="!k.mitglied"
              :title="k.hinweis || (k.mitglied ? '' : 'Ohne Mitglied kann keine Rolle zugewiesen werden')"
              @click="bearbeiten(k)">Rollen ändern</DkButton>
          </li>
        </ul>
      </DkCard>

      <!-- ── Verantwortliche je Bereich/Gruppe ──────────────────────────── -->
      <DkCard title="Verantwortliche für Bereiche und Gruppen">
        <p class="rr-hilfe">Verantwortliche dürfen Pläne ihres Bereichs bzw. ihrer Gruppe
          erstellen und bearbeiten. Auswählbar sind nur Personen mit Zugang.</p>
        <DkField label="Bereich oder Gruppe wählen" v-slot="feld">
          <select v-bind="feld" v-model="bereich" class="dk-ui-eingabe">
            <option value="">Bitte wählen</option>
            <option v-for="b in bereiche" :key="b.id" :value="b.id">{{ b.label }}</option>
          </select>
        </DkField>

        <template v-if="bereich">
          <VerantwortlicheKarte :key="bereich" :doctype="gewaehlt.typ" :name="gewaehlt.name" />
        </template>
        <p v-else class="rr-unter">Noch kein Bereich gewählt.</p>
      </DkCard>
    </template>

    <!-- ── Rollenauswahl (Dialog) ───────────────────────────────────────── -->
    <DkDialog :model-value="!!dialog" :title="dialog ? `Rollen für ${dialog.anzeige}` : ''"
      :close-on-overlay="false" @update:model-value="schliesseDialog">
      <template v-if="dialog">
        <p class="rr-hilfe">Die Auswahl ersetzt die Rollen dieser Person. Rollen außerhalb
          dieser Liste (aus der Einrichtung) bleiben unberührt.</p>
        <ul class="rr-rollen-liste">
          <li v-for="r in rollenWaehlbar" :key="r">
            <label class="rr-rolle">
              <input type="checkbox" :value="r" v-model="gewaehlteRollen" />
              <span>{{ r }}</span>
            </label>
          </li>
        </ul>
        <DkHint v-if="!istSystemManager && beruehrtVerwaltung" variant="warn">
          Verwaltungsrollen kann nur ein System Manager vergeben oder entziehen.
        </DkHint>
        <DkHint v-if="dialogFehler" variant="err" role="alert">{{ dialogFehler }}</DkHint>
      </template>
      <template #footer>
        <DkButton variant="secondary" :disabled="speichert" @click="schliesseDialog(false)">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="speichert" @click="speichern">Speichern</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * N10 — Einstellungen-Abschnitt „Rollen & Rechte".
 *
 * Zeigt je Person mit Konto die Rollen und den Kontozustand (Lese-Tabelle) und
 * erlaubt das Aendern der Rollen. Zusaetzlich die Verantwortlichen je Bereich/
 * Gruppe (K1: auch Dienstbereiche) ueber die bestehende VerantwortlicheKarte.
 *
 * Die Rechte kommen vom Server: `get_rollen_uebersicht` liefert
 * `rollen_waehlbar`, `ist_system_manager` und die Konten; `setze_rollen` prueft
 * jede Vergabe erneut. Die Oberflaeche blendet nur aus (Warnhinweis), was der
 * Server ohnehin verweigert — die letzte Admin-Rolle ist dort nicht entziehbar.
 */
import { ref, computed, onMounted } from 'vue'
import {
  rollenUebersicht, rollenSetzen, bereicheLesen,
} from '../../composables/useRollenRechte.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkDialog from '../../components/ui/DkDialog.vue'
import DkEmpty from '../../components/ui/DkEmpty.vue'
import VerantwortlicheKarte from '../../components/VerantwortlicheKarte.vue'

const laedt = ref(true)
const geladen = ref(false)
const fehler = ref('')
const erfolg = ref('')
const konten = ref([])
const rollenWaehlbar = ref([])
const istSystemManager = ref(false)
const suche = ref('')

const bereiche = ref([])
const bereich = ref('')

const dialog = ref(null)
const gewaehlteRollen = ref([])
const speichert = ref(false)
const dialogFehler = ref('')

const VERWALTUNGSROLLEN = ['System Manager', 'Mitgliederadministrator']

const gefiltert = computed(() => {
  const begriff = suche.value.trim().toLowerCase()
  if (!begriff) return konten.value
  return konten.value.filter((k) =>
    (k.anzeige || '').toLowerCase().includes(begriff)
    || (k.email || '').toLowerCase().includes(begriff)
    || (k.user || '').toLowerCase().includes(begriff))
})

const gewaehlt = computed(() => {
  const treffer = bereiche.value.find((b) => b.id === bereich.value)
  return treffer ? { typ: treffer.typ, name: treffer.name } : { typ: 'Gruppe', name: '' }
})

const beruehrtVerwaltung = computed(() => {
  if (!dialog.value) return false
  const alt = new Set(dialog.value.rollen || [])
  const neu = new Set(gewaehlteRollen.value)
  return VERWALTUNGSROLLEN.some((r) => alt.has(r) !== neu.has(r))
})

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await rollenUebersicht()
    konten.value = daten.konten || []
    rollenWaehlbar.value = daten.rollen_waehlbar || []
    istSystemManager.value = !!daten.ist_system_manager
    geladen.value = true
  } catch (e) {
    fehler.value = e?.message || 'Die Übersicht konnte nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

async function ladeBereiche() {
  try {
    const daten = await bereicheLesen()
    bereiche.value = (daten.nodes || []).filter(
      (n) => n.type === 'dienstbereich' || n.type === 'gruppe' || n.type === 'untergruppe',
    ).map((n) => ({
      id: n.id,
      name: n.raw_name,
      label: `${bereichWort(n.type)}: ${n.name}`,
      typ: n.type === 'dienstbereich' ? 'Dienstbereich'
        : n.type === 'untergruppe' ? 'Untergruppe' : 'Gruppe',
    }))
  } catch {
    bereiche.value = []
  }
}

function bereichWort(typ) {
  if (typ === 'dienstbereich') return 'Bereich'
  if (typ === 'untergruppe') return 'Untergruppe'
  return 'Gruppe'
}

function bearbeiten(k) {
  if (!k.mitglied) return
  dialogFehler.value = ''
  dialog.value = k
  gewaehlteRollen.value = [...(k.rollen || [])].filter((r) => rollenWaehlbar.value.includes(r))
}

function schliesseDialog(offen) {
  if (!offen && !speichert.value) dialog.value = null
}

async function speichern() {
  if (!dialog.value || speichert.value) return
  speichert.value = true
  dialogFehler.value = ''
  try {
    await rollenSetzen(dialog.value.mitglied, gewaehlteRollen.value)
    erfolg.value = `Rollen für ${dialog.value.anzeige} gespeichert.`
    dialog.value = null
    await laden()
  } catch (e) {
    dialogFehler.value = e?.message || 'Die Rollen konnten nicht gespeichert werden.'
  } finally {
    speichert.value = false
  }
}

onMounted(() => { laden(); ladeBereiche() })
</script>

<style scoped>
.rr-abschnitt { display: grid; gap: var(--sp-4); min-width: 0; }
.rr-abschnitt h2, .rr-abschnitt p { margin: 0; }
.rr-hilfe { color: var(--muted); font-size: var(--fs-sm); }
.rr-liste { list-style: none; padding: 0; margin: var(--sp-3) 0 0; display: grid; gap: var(--sp-1); }
.rr-zeile {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--line);
}
.rr-person { display: flex; flex-direction: column; min-width: 0; overflow-wrap: anywhere; }
.rr-name { font-weight: 550; }
.rr-unter { color: var(--muted); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.rr-schild { font-size: var(--fs-sm); font-weight: 550; }
.rr-hinweis { color: var(--muted); font-size: var(--fs-sm); font-style: italic; }
.rr-schild--gesperrt { color: var(--warn); }
.rr-schild--raus { color: var(--err); }
.rr-rollen { display: flex; flex-wrap: wrap; gap: var(--sp-1); min-width: 0; }
.rr-chip {
  background: var(--surface-2); border: 1px solid var(--line);
  border-radius: var(--radius-sm); padding: 2px var(--sp-2); font-size: var(--fs-sm);
}
.rr-rollen-liste { list-style: none; padding: 0; margin: var(--sp-2) 0; display: grid; gap: var(--sp-2); }
.rr-rolle { display: flex; align-items: flex-start; gap: var(--sp-2); }
.rr-rolle input { margin-top: var(--sp-1); flex-shrink: 0; }
@media (max-width: 720px) {
  .rr-zeile { grid-template-columns: 1fr; }
}
</style>
