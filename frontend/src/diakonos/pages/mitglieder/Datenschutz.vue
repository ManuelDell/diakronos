<template>
  <section aria-label="Datenschutz" class="ds-bereich">
    <p>Einwilligungen und Löschanträge der Gemeinde. Auskunft lädt die zugeordneten Daten als JSON-Datei herunter.</p>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="fehler" variant="secondary" @click="laden">Erneut laden</DkButton>
    <p v-if="laedt" role="status">Datenschutz wird geladen…</p>
    <template v-else-if="geladen">
      <!-- MAIL-1: ohne eingerichteten Mailversand lässt sich kein Löschantrag
           freigeben (die Meldung muss vor der Anonymisierung raus). Der
           Hinweis steht dort, wo freigegeben wird — nur System Manager können
           ihn abstellen, deshalb sehen ihn nur sie. -->
      <DkHint v-if="!mailversand.eingerichtet && mailversand.darf_aendern" variant="warn" role="status">
        Mailversand ist noch nicht eingerichtet — ohne ihn können Löschanträge
        nicht freigegeben werden.
        <a href="#/einstellungen/mailversand">Mailversand einrichten</a>
      </DkHint>
      <DkCard title="Offene Löschanträge">
        <!-- DSGVO-2c: Freigeben und Ablehnen stehen auf der eigenen Seite
             „Löschanträge“ (mit Name abtippen bzw. Pflicht-Begründung). Diese
             Karte nennt den Weg dorthin — ein Knopf mit zwei verschiedenen
             Rückfragen wäre zwei Wahrheiten. -->
        <p v-if="antraege.length">
          {{ antraege.length }} {{ antraege.length === 1 ? 'Antrag wartet' : 'Anträge warten' }}
          auf Bearbeitung.
          <a href="#/mitglieder/loeschantraege">Zu den Löschanträgen</a>
        </p>
        <p v-else>Keine offenen Löschanträge.</p>
      </DkCard>
      <DkCard title="Einwilligungsstand">
        <p>Gezählt werden Personen, nicht einzelne Protokolleinträge.</p>
        <div class="ds-filter">
          <label>Stand
            <select v-model="stand" class="dk-input">
              <option value="">Alle ({{ personen.length }})</option>
              <option v-for="(text, wert) in DATENSCHUTZ_STAND" :key="wert" :value="wert">{{ text }} ({{ stats[wert] || 0 }})</option>
            </select>
          </label>
          <label>Person suchen<input v-model="suche" type="search" class="dk-input" placeholder="Name oder E-Mail" /></label>
        </div>
        <p role="status">{{ gefiltert.length }} von {{ personen.length }} Personen</p>
        <p v-if="!gefiltert.length">Keine Personen für diese Auswahl.</p>
        <ul v-else class="ds-liste">
          <li v-for="m in gefiltert" :key="m.name" class="ds-person">
            <div class="ds-identitaet">
              <!-- DSGVO-2d: Eine gelöschte Person hat kein Profil mehr und
                   keinen Klarnamen. Die Zeile bleibt stehen (Zählung), ist aber
                   nur noch lesbar — kein Link, kein zweites „Anonymisieren“. -->
              <a v-if="!m.geloescht" :href="'#/mitglied/' + encodeURIComponent(m.name)">{{ name(m) }}</a>
              <span v-else>{{ name(m) }}</span>
              <p>{{ DATENSCHUTZ_STAND[m.dsgvo_status] }} · {{ datum(m.dsgvo_datum) }}</p>
            </div>
            <div v-if="!m.geloescht" class="ds-aktionen">
              <DkButton variant="secondary" :loading="exportId === m.name" :aria-label="'Auskunft für ' + name(m)" @click="auskunft(m)">Auskunft</DkButton>
              <DkButton variant="danger" :aria-label="'Anonymisieren: ' + name(m)" @click="oeffnen(m)">Anonymisieren</DkButton>
            </div>
          </li>
        </ul>
      </DkCard>
    </template>
    <DkDialog :model-value="offen" :title="dialogTitel" :close-on-overlay="false" @update:model-value="schliessen">
      <template v-if="ziel">
        <p><strong>{{ name(ziel) }}</strong></p>
        <DkHint variant="warn">Die Anonymisierung kann nicht rückgängig gemacht werden.</DkHint>
        <p v-if="schritt === 1">Prüfe zuerst, ob gesetzliche Aufbewahrungspflichten oder offene Vorgänge bestehen. Ein Löschantrag allein ändert noch keine Daten.</p>
        <p>Bereinigt werden Namen, Kontaktangaben, Geburtstag, Foto-Verweis und Notiz im Personenstamm sowie zugeordnete Registrierungsdaten mit Antworten und Kindern. Bereiche und Familienbeziehungen werden entfernt. Das lokale Konto wird gesperrt und seine Sitzungen werden beendet.</p>
        <p>Dienstplan-Historie, technische Kennungen (auch die Konto-Kennung) und Einwilligungsnachweise bleiben erhalten. Kennungen können Namen oder E-Mail-Adressen enthalten; die Konto-Kennung bleibt belegt. Dateien, Freitextnennungen in Beiträgen und ein externes Anmeldekonto werden nicht automatisch entfernt. Prüfe sie gesondert.</p>
        <label v-if="schritt === 2" class="ds-bestaetigung">Zum endgültigen Anonymisieren ANONYMISIEREN eingeben
          <input v-model="wort" class="dk-input" autocomplete="off" />
        </label>
        <DkHint v-if="dialogFehler" variant="err" role="alert">{{ dialogFehler }}</DkHint>
      </template>
      <template #footer>
        <DkButton variant="ghost" :disabled="sendet" @click="schliessen(false)">Abbrechen</DkButton>
        <DkButton v-if="schritt === 1" variant="danger" @click="schritt = 2">Geprüft, weiter</DkButton>
        <DkButton v-else variant="danger" :loading="sendet" @click="anonymisieren">Endgültig anonymisieren</DkButton>
      </template>
    </DkDialog>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { DATENSCHUTZ_STAND, gefiltertePersonen, personenAnzeige, zweiteBestaetigung } from '../../components/mitglieder/datenschutz.mjs'
import DkCard from '../../components/ui/DkCard.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkDialog from '../../components/ui/DkDialog.vue'

defineProps({ embedded: Boolean })
const API = 'diakronos.diakonos.api.datenschutz.'
const personen = ref([]), stats = ref({}), antraege = ref([])
// MAIL-1: „eingerichtet: ja/nein“ — der Server gibt Mitgliederadministratoren
// nur diese Auskunft, keinen Server und keinen Absender.
const mailversand = ref({ eingerichtet: true, darf_aendern: false })
const laedt = ref(true), geladen = ref(false), fehler = ref('')
const suche = ref(''), stand = ref(new URLSearchParams(window.location.hash.split('?')[1] || '').get('stand') || '')
const exportId = ref(''), ziel = ref(null), schritt = ref(0), wort = ref(''), sendet = ref(false), dialogFehler = ref(''), istAntrag = ref(false)
const offen = computed(() => schritt.value > 0)
const dialogTitel = computed(() => istAntrag.value ? 'Löschantrag prüfen' : 'Person anonymisieren')
const gefiltert = computed(() => gefiltertePersonen(personen.value, stand.value, suche.value))
// DSGVO-2d: gelöschte Person -> „Gelöschte Person“ (eine Regel, s. Helfer).
const name = personenAnzeige
const datum = d => d ? new Date(String(d).slice(0, 10) + 'T12:00:00').toLocaleDateString('de-DE') : 'Kein Datum'

async function laden() {
  laedt.value = true
  fehler.value = ''
  geladen.value = false
  try {
    const [uebersicht, offen, post] = await Promise.all([
      apiCall('diakronos.diakronos.api.admin_hub.get_dsgvo_uebersicht'),
      apiCall(API + 'get_loeschantraege'),
      // Ein Fehler hier darf die Seite nicht kippen: dann bleibt der Hinweis
      // einfach aus (kein falsches „nicht eingerichtet“).
      apiCall('diakronos.diakronos.api.mailversand.mailversand_status').catch(() => null),
    ])
    personen.value = uebersicht.mitglieder
    stats.value = uebersicht.stats
    antraege.value = offen
    if (post) mailversand.value = { eingerichtet: true, darf_aendern: false, ...post }
    geladen.value = true
  } catch (e) {
    fehler.value = e.message || 'Datenschutz konnte nicht geladen werden.'
  } finally { laedt.value = false }
}

async function auskunft(m) {
  if (exportId.value) return
  exportId.value = m.name
  fehler.value = ''
  try {
    const daten = await apiCall(API + 'auskunft', { mitglied_id: m.name })
    const url = URL.createObjectURL(new Blob([JSON.stringify(daten, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'datenauskunft.json'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    showToast('Datenauskunft wurde heruntergeladen.', 'success')
  } catch (e) { fehler.value = e.message || 'Auskunft konnte nicht geladen werden.' }
  finally { exportId.value = '' }
}

function oeffnen(m, antrag = false) {
  ziel.value = m
  istAntrag.value = antrag
  schritt.value = 1
  wort.value = ''
  dialogFehler.value = ''
}
function schliessen(wert) {
  if (sendet.value || wert) return
  schritt.value = 0
  ziel.value = null
}
async function anonymisieren() {
  if (sendet.value) return
  if (!zweiteBestaetigung(schritt.value, wort.value)) {
    dialogFehler.value = 'Bitte ANONYMISIEREN eingeben.'
    return
  }
  sendet.value = true
  dialogFehler.value = ''
  try {
    await apiCall(API + 'anonymisieren', {
      mitglied_id: ziel.value.name || ziel.value.mitglied,
      bestaetigt: true, bestaetigung: wort.value, nur_antrag: istAntrag.value,
    })
    schritt.value = 0
    ziel.value = null
    showToast('Personenstamm anonymisiert und Zugang beendet.', 'success')
    await laden()
  } catch (e) { dialogFehler.value = e.message || 'Anonymisierung fehlgeschlagen.' }
  finally { sendet.value = false }
}
onMounted(laden)
</script>

<style scoped>
.ds-bereich { display: grid; gap: var(--sp-4); }
.ds-filter, .ds-aktionen { display: flex; gap: var(--sp-3); flex-wrap: wrap; }
.ds-filter label, .ds-bestaetigung { display: grid; gap: var(--sp-2); }
.ds-filter label { flex: 1; min-width: 0; }
.ds-liste { padding: 0; margin: 0; list-style: none; }
.ds-person { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); padding: var(--sp-3) 0; border-bottom: 1px solid var(--dk-border); flex-wrap: wrap; }
.ds-identitaet { min-width: 0; overflow-wrap: anywhere; }
.ds-person p { margin: var(--sp-1) 0; color: var(--dk-text-muted); }
@media (max-width: 600px) { .ds-filter { flex-direction: column; } .ds-aktionen { width: 100%; } }
</style>
