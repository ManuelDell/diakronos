<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Dienstplan</h1>
        <p class="dk-screen-sub">Deine nächsten Vorbereitungen und Einsätze</p>
      </div>
    </div>

    <!-- UX2d3a: Laden zeigt den Umriss der beiden Spalten (Skelett), keinen
         Satz; es erscheint erst nach 300 ms. -->
    <DkSkelett v-if="skelettSichtbar" form="karten" :anzahl="2" text="Dienstplan wird geladen …" />
    <DkEmpty
      v-else-if="error"
      class="dp-state"
      icon="!"
      title="Dienstplan nicht geladen"
      :text="error"
      :erneut-versuchen="fetchData"
    />

    <!-- UX2d3c (Review UX2d3b): `v-else` zeigte in den ersten 300 ms (vor dem
         Skelett) schon die Leersätze („Keine anstehende Vorbereitung."). Jetzt
         gilt der Rumpf erst, wenn wirklich nichts mehr lädt. -->
    <template v-else-if="!loading">
      <div class="dp-grid">
        <!-- Nächste Vorbereitung -->
        <section class="dk-card dp-col">
          <h2 class="dp-col-title">Nächste Vorbereitung</h2>
          <template v-if="nextVorbereitung">
            <div class="dp-entry-head">
              <div>
                <div class="dp-entry-name">{{ nextVorbereitung.element_name || '–' }}</div>
                <div class="dp-entry-meta">{{ formatDateTime(nextVorbereitung.element_start) }}</div>
              </div>
              <div class="dp-entry-side">
                <span v-if="nextVorbereitung.dienstrolle_name" class="dp-rolle">{{ nextVorbereitung.dienstrolle_name }}</span>
                <span class="dk-badge dk-badge-warning">Vorbereitung</span>
              </div>
            </div>
            <div v-if="nextVorbereitung.ablaufplan?.positionen?.length" class="dp-ablauf">
              <div class="dp-ablauf-title">Ablauf</div>
              <ol class="dp-positions">
                <li
                  v-for="pos in nextVorbereitung.ablaufplan.positionen"
                  :key="pos.reihenfolge + '-' + pos.bezeichnung"
                  class="dp-pos"
                  :class="{ 'dp-own': pos.verantwortet }"
                >
                  <span class="dp-pos-idx">{{ pos.reihenfolge }}</span>
                  <span class="dp-pos-body">
                    <span class="dp-pos-name">{{ pos.bezeichnung || '–' }}</span>
                    <span v-if="pos.funktion || pos.gruppe || pos.detail || pos.dauer_minuten" class="dp-pos-detail">
                      <template v-if="pos.funktion">{{ pos.funktion }}</template>
                      <template v-if="pos.gruppe"> · {{ pos.gruppe }}</template>
                      <template v-if="pos.detail"> · {{ pos.detail }}</template>
                      <template v-if="pos.dauer_minuten"> · {{ pos.dauer_minuten }} Min.</template>
                    </span>
                  </span>
                  <span v-if="pos.verantwortet" class="dp-own-badge">Du</span>
                </li>
              </ol>
            </div>
            <div v-else class="dp-no-ablauf">Kein Ablaufplan hinterlegt.</div>
          </template>
          <!-- UX2d3c: Der Leersatz sagt jetzt, warum nichts da ist und was
               zu tun ist (Du-Form, ohne Jargon). Ein Knopf gehört nicht
               hierher: die Einteilung macht die Gemeinde (fachliche
               Entscheidung, nicht Teil dieser Karte). -->
          <DkEmpty
            v-else
            class="dp-leer"
            icon="🗓"
            title="Keine anstehende Vorbereitung"
            text="Dir ist zurzeit keine Vorbereitung zugeteilt. Sobald die Gemeinde dich einteilt, erscheint sie hier."
          />
        </section>

        <!-- Nächster Einsatz -->
        <section class="dk-card dp-col">
          <h2 class="dp-col-title">Nächster Einsatz</h2>
          <template v-if="nextEinsatz">
            <div class="dp-entry-head">
              <div>
                <div class="dp-entry-name">{{ nextEinsatz.element_name || '–' }}</div>
                <div class="dp-entry-meta">{{ formatDateTime(nextEinsatz.element_start) }}</div>
              </div>
              <div class="dp-entry-side">
                <span v-if="nextEinsatz.dienstrolle_name" class="dp-rolle">{{ nextEinsatz.dienstrolle_name }}</span>
                <span class="dk-badge dk-badge-info">Einsatz</span>
              </div>
            </div>
            <div v-if="nextEinsatz.ablaufplan?.positionen?.length" class="dp-ablauf">
              <div class="dp-ablauf-title">Ablauf</div>
              <ol class="dp-positions">
                <li
                  v-for="pos in nextEinsatz.ablaufplan.positionen"
                  :key="pos.reihenfolge + '-' + pos.bezeichnung"
                  class="dp-pos"
                  :class="{ 'dp-own': pos.verantwortet }"
                >
                  <span class="dp-pos-idx">{{ pos.reihenfolge }}</span>
                  <span class="dp-pos-body">
                    <span class="dp-pos-name">{{ pos.bezeichnung || '–' }}</span>
                    <span v-if="pos.funktion || pos.gruppe || pos.detail || pos.dauer_minuten" class="dp-pos-detail">
                      <template v-if="pos.funktion">{{ pos.funktion }}</template>
                      <template v-if="pos.gruppe"> · {{ pos.gruppe }}</template>
                      <template v-if="pos.detail"> · {{ pos.detail }}</template>
                      <template v-if="pos.dauer_minuten"> · {{ pos.dauer_minuten }} Min.</template>
                    </span>
                  </span>
                  <span v-if="pos.verantwortet" class="dp-own-badge">Du</span>
                </li>
              </ol>
            </div>
            <div v-else class="dp-no-ablauf">Kein Ablaufplan hinterlegt.</div>
          </template>
          <DkEmpty
            v-else
            class="dp-leer"
            icon="📋"
            title="Kein anstehender Einsatz"
            text="Dir ist zurzeit kein Einsatz zugeteilt. Sobald die Gemeinde dich einteilt, erscheint er hier."
          />
        </section>
      </div>

      <!-- Weitere Termine -->
      <section v-if="weitereTermine.length" class="dk-card dp-further">
        <h2 class="dp-col-title">Weitere Termine</h2>
        <ul class="dp-further-list">
          <li v-for="(t, i) in weitereTermine" :key="t.element + '-' + (t.mitglied || '') + '-' + i" class="dp-further-row">
            <div class="dp-further-main">
              <div class="dp-entry-name">{{ t.element_name || '–' }}</div>
              <div class="dp-entry-meta">{{ formatDateTime(t.element_start) }}</div>
            </div>
            <div class="dp-entry-side">
              <span v-if="t.dienstrolle_name" class="dp-rolle">{{ t.dienstrolle_name }}</span>
              <span class="dk-badge" :class="pillClass(t.terminart)">
                {{ t.terminart === 'Vorbereitung' ? 'Vorbereitung' : 'Einsatz' }}
              </span>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'

const loading = ref(true)
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar } = useLadeSkelett(loading)
const error = ref(null)
const data = ref(null)

const nextVorbereitung = computed(() => (data.value?.vorbereitung || [])[0] || null)
const nextEinsatz = computed(() => (data.value?.einsatz || [])[0] || null)
const weitereTermine = computed(() => {
  const vor = data.value?.vorbereitung || []
  const ein = data.value?.einsatz || []
  const rest = [...vor.slice(1), ...ein.slice(1)]
  return rest.sort((a, b) => (a.element_start || '').localeCompare(b.element_start || ''))
})

function pillClass(t) {
  return t === 'Vorbereitung' ? 'dk-badge-warning' : 'dk-badge-info'
}

function formatDateTime(s) {
  if (!s) return ''
  const d = new Date(String(s).replace(' ', 'T'))
  if (isNaN(d)) return s
  return (
    d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }) +
    ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  )
}

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const result = await apiCall('diakronos.diakonos.api.dienstplan.get_meine_dienste', {})
    data.value = result || { vorbereitung: [], einsatz: [] }
  } catch (err) {
    error.value = aktionsfehler('laden', err)
    console.error('Dienstplan — Fehler:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.dp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-4);
  align-items: start;
}
@media (max-width: 760px) {
  .dp-grid { grid-template-columns: 1fr; }
}
.dp-col { padding: var(--sp-4) var(--sp-4); }
.dp-col-title { font-size: var(--fs-14); font-weight: var(--fw-fett); text-transform: uppercase; letter-spacing: 0.04em; color: var(--dk-text-muted); margin: 0 0 var(--sp-3); }
.dp-state { display: flex; align-items: center; gap: var(--sp-3); }
.dp-error { color: var(--dk-danger); }

.dp-entry-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: var(--sp-2);
}
.dp-entry-name { font-size: var(--fs-16); font-weight: var(--fw-fett); color: var(--dk-text); line-height: 1.3; }
.dp-entry-meta { font-size: var(--fs-12); color: var(--dk-text-muted); margin-top: var(--sp-1); }
.dp-entry-side { display: inline-flex; align-items: center; gap: var(--sp-2); flex-shrink: 0; }
.dp-rolle { font-size: var(--fs-12); color: var(--dk-text-muted); max-width: 110px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.dp-ablauf { border-top: var(--rahmen-breite) solid var(--dk-divider); margin-top: var(--sp-3); padding-top: var(--sp-3); }
.dp-ablauf-title { font-size: var(--fs-12); font-weight: var(--fw-fett); text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-subtle); margin-bottom: var(--sp-2); }
.dp-positions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.dp-pos {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  border: var(--rahmen-breite) solid var(--dk-border);
  background: var(--dk-surface);
}
.dp-pos.dp-own {
  background: color-mix(in oklch, var(--dk-brand-400) 10%, var(--dk-surface));
  border-color: color-mix(in oklch, var(--dk-brand-400) 35%, var(--dk-surface));
}
.dp-pos-idx {
  width: 22px; height: 22px;
  flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  font-size: var(--fs-12); font-weight: var(--fw-fett);
}
.dp-pos.dp-own .dp-pos-idx { background: var(--dk-navy-400); color: var(--primary-ink); }
.dp-pos-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.dp-pos-name { font-size: var(--fs-14); font-weight: var(--fw-mittel); color: var(--dk-text); }
.dp-pos.dp-own .dp-pos-name { color: var(--dk-brand-700); font-weight: var(--fw-fett); }
.dp-pos-detail { font-size: var(--fs-12); color: var(--dk-text-muted); margin-top: var(--sp-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dp-own-badge {
  flex-shrink: 0;
  font-size: var(--fs-xs); font-weight: var(--fw-fett);
  padding: var(--sp-1) var(--sp-2); border-radius: var(--badge-r);
  background: var(--primary); color: var(--primary-ink);
}
.dp-no-ablauf { font-size: var(--fs-12); color: var(--dk-text-subtle); margin-top: var(--sp-1); }
/* UX2d3c: Der Leerzustand einer Spalte ist eine ruhige Fläche, kein Satz —
   Abstand nach oben, damit er nicht am Spaltentitel klebt. */
.dp-leer { padding-top: var(--sp-3); }

.dp-further { padding: var(--sp-4) var(--sp-4); margin-top: var(--sp-1); }
.dp-further-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.dp-further-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: var(--rahmen-breite) solid var(--dk-divider);
}
.dp-further-row:last-child { border-bottom: none; }
.dp-further-main { flex: 1; min-width: 0; }
</style>
