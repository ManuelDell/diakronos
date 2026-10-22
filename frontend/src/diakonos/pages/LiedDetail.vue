<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Seitenkopf -->
    <DkPageHeader
      :title="lied.titel || 'Ohne Titel'"
      :sub="lied.alternativtitel || ''"
      :krumen="[{ text: 'Lieder', href: '#/lieder' }, { text: lied.titel || 'Lied' }]"
      :badges="[{ text: lied.rechte_status || 'Ungeklärt', variant: rechteVariante(lied.rechte_status) }]"
    >
      <template v-if="darfSchreiben && !bearbeiten" #actions>
        <DkButton variant="primary" @click="bearbeiten = true">
          <svg slot="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          Bearbeiten
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- OP-UI-19: eine Ladeform für alle Seiten — Skelett statt „Lade Lied…“. -->
    <DkSkelett v-if="loading" form="zeilen" :anzahl="6" text="Lied wird geladen …" />

    <!-- Fehler -->
    <div v-else-if="error" class="ld-fehler">
      {{ error }}
      <DkButton variant="secondary" size="sm" @click="loadDetail">Nochmal</DkButton>
    </div>

    <!-- LI1: Bearbeiten — dieselbe Komponente wie „Neues Lied“ -->
    <LiedBearbeiten
      v-else-if="bearbeiten"
      :lied="lied"
      :strophen="strophen"
      :material="standardMaterial"
      @gespeichert="nachSpeichern"
      @verlassen="bearbeiten = false"
      @reload="loadDetail"
    />

    <template v-else>
      <!-- Kopf -->
      <DkCard class="ld-head">
        <div class="ld-head-inhalt">
          <div class="ld-head-haupt">
            <div class="ld-meta-row">
              <DkBadge v-if="lied.anzeige" :variant="istKopie(lied) ? 'neutral' : 'akzent'">{{ lied.anzeige }}</DkBadge>
              <DkBadge v-if="lied.ccli_nummer" variant="neutral">CCLI {{ lied.ccli_nummer }}</DkBadge>
              <DkBadge v-if="lied.zuletzt_gesungen" variant="neutral">Zuletzt gesungen: {{ formatDate(lied.zuletzt_gesungen) }}</DkBadge>
              <DkBadge v-if="lied.anzahl_gesungen" variant="neutral">{{ lied.anzahl_gesungen }}× gesungen</DkBadge>
            </div>
            <div v-if="lied.kategorien && lied.kategorien.length" class="ld-tags">
              <DkBadge v-for="k in lied.kategorien" :key="k" variant="info">{{ k }}</DkBadge>
            </div>
            <div v-if="lied.anlaesse && lied.anlaesse.length" class="ld-tags">
              <DkBadge v-for="a in lied.anlaesse" :key="a" variant="neutral">{{ a }}</DkBadge>
            </div>
          </div>
          <div v-if="lied.notiz || lied.rechtehinweis" class="ld-head-neben">
            <p v-if="lied.notiz">{{ lied.notiz }}</p>
            <p v-if="lied.rechtehinweis" class="ld-rechtehinweis">{{ lied.rechtehinweis }}</p>
          </div>
        </div>
      </DkCard>

      <div class="ld-grid">
        <!-- Linke Spalte -->
        <div class="ld-main">
          <!-- Strophen -->
          <DkCard title="Strophen">
            <DkEmpty v-if="!strophen.length" title="Noch keine Strophen hinterlegt" icon="🎼" />
            <div v-for="s in strophen" :key="s.nummer" class="ld-strophe">
              <div class="ld-strophe-head">
                <span class="ld-strophe-nr">{{ s.nummer }}</span>
                <DkBadge v-if="s.typ && s.typ !== 'Strophe'" variant="neutral">{{ s.typ }}</DkBadge>
                <span v-if="s.sprache" class="ld-strophe-sprache">{{ s.sprache }}</span>
                <DkBadge v-if="s.nur_chor" variant="warn">nur Chor</DkBadge>
              </div>
              <p class="ld-strophe-text">{{ s.text }}</p>
            </div>
          </DkCard>

          <!-- Fassungen -->
          <DkCard title="Fassungen">
            <template #actions>
              <span class="ld-muted">{{ fassungen.length }} {{ wortImNumerus(fassungen.length, 'Fassung', 'Fassungen') }}</span>
            </template>

            <div v-if="fassungen.length" class="ld-tabs">
              <button
                v-for="(f, i) in fassungen"
                :key="f.name"
                class="ld-tab"
                :class="{ 'is-active': activeTab === i }"
                @click="activeTab = i"
              >
                <span v-if="f.ist_standard" class="ld-tab-star" title="Standardfassung">★</span>
                {{ f.fassungsname || 'Fassung ' + (i + 1) }}
              </button>
            </div>
            <DkEmpty v-else title="Noch keine Fassungen" text="Zu diesem Lied sind noch keine Fassungen hinterlegt." icon="🎵" />

            <template v-if="fassungen.length">
              <div class="ld-fassung">
                <div class="ld-fassung-grid">
                  <div v-for="f in fassungFelder" :key="f.label" class="ld-fassung-field">
                    <span class="ld-fassung-label">{{ f.label }}</span>
                    <span class="ld-fassung-value">{{ f.wert || '–' }}</span>
                  </div>
                </div>

                <p v-if="activeFassung.notiz" class="ld-fassung-notiz">{{ activeFassung.notiz }}</p>

                <div v-if="(activeFassung.material || []).length" class="ld-material">
                  <h3 class="ld-material-title">Material</h3>
                  <DkTable :spalten="materialSpalten">
                    <tr v-for="(m, idx) in activeFassung.material" :key="idx">
                      <td class="dk-cell-text">{{ m.art || '–' }}</td>
                      <td class="dk-cell-text">{{ m.stimme || '–' }}</td>
                      <td class="dk-cell-text">
                        <!-- UXM-R4: Die Datei-URL liefert der Server als datei.datei_url;
                             `m.anhang` ist nur die interne SichererAnhang-Kennung (404). -->
                        <a
                          v-if="m.datei && m.datei.datei_url"
                          :href="m.datei.datei_url" target="_blank" rel="noopener" class="ld-link"
                        >{{ m.dateiname || 'Öffnen' }}</a>
                        <span v-else class="dk-text-subtle">–</span>
                      </td>
                      <td class="dk-cell-text">{{ m.beschreibung || '–' }}</td>
                    </tr>
                  </DkTable>
                </div>

                <div v-if="activeFassung.externe_links" class="ld-fassung-links">
                  <a :href="activeFassung.externe_links" target="_blank" rel="noopener" class="ld-link">Externer Link ↗</a>
                </div>
              </div>
            </template>
          </DkCard>
        </div>

        <!-- Rechte Spalte -->
        <aside class="ld-side">
          <DkCard title="In Liedgruppen">
            <DkEmpty v-if="liedgruppen.length === 0" title="Keine Liedgruppe" text="Dieses Lied steckt in keiner Liedgruppe." icon="📁" />
            <ul v-else class="ld-group-list">
              <li v-for="g in liedgruppen" :key="g.liedgruppe">
                <a :href="'#/liedgruppen/' + encodeURIComponent(g.liedgruppe)" class="ld-group-link">
                  <span class="ld-group-name">{{ g.liedgruppe }}</span>
                  <span v-if="g.nummer" class="ld-group-num">{{ g.nummer }}</span>
                  <span v-if="g.fassung" class="ld-group-fassung">{{ g.fassung }}</span>
                </a>
              </li>
            </ul>
          </DkCard>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * LiedDetail — Lied in allen Fassungen, Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Karten, Kennzeichen, Tabelle und
 * Leerzustaende kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { getRouteParam, navigate } from '../router.js'
import { istKopie } from '../components/planrahmen/lied-anzeige.mjs'
import { wortImNumerus } from '../components/ui/begriffe.mjs'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import LiedBearbeiten from '../components/lieder/LiedBearbeiten.vue'
import { useSession } from '../composables/useSession.js'

const lied = ref({})
const strophen = ref([])
const fassungen = ref([])
const liedgruppen = ref([])
const loading = ref(true)
const error = ref(null)
const activeTab = ref(0)
const bearbeiten = ref(false)
const darfSchreiben = ref(false)

const liedName = getRouteParam('id') || ''

const activeFassung = computed(() => fassungen.value[activeTab.value] || {})

/** Material der Standardfassung (bzw. der ersten) für die Bearbeiten-Ansicht. */
const standardMaterial = computed(() => {
  const f = fassungen.value.find((x) => x.ist_standard) || fassungen.value[0]
  return (f?.material || []).map((m) => ({ ...m, anhang: m.anhang }))
})

/* Bausteine beschicken */
const materialSpalten = [
  { key: 'art', label: 'Art' },
  { key: 'stimme', label: 'Stimme' },
  { key: 'anhang', label: 'Datei' },
  { key: 'beschreibung', label: 'Beschreibung' },
]
const fassungFelder = computed(() => {
  const f = activeFassung.value
  const felder = [
    { label: 'Besetzung', wert: f.besetzung || '' },
    { label: 'Tonart', wert: f.tonart || '' },
    { label: 'Taktart', wert: f.taktart || '' },
    { label: 'Tempo', wert: f.tempo_bpm ? f.tempo_bpm + ' BPM' : '' },
    { label: 'Dauer', wert: f.dauer_minuten ? f.dauer_minuten + ' Min.' : '' },
    { label: 'Schwierigkeit', wert: f.schwierigkeit || '' },
  ]
  if (f.arrangeur) felder.push({ label: 'Arrangeur', wert: f.arrangeur })
  felder.push({ label: 'Stimmen', wert: f.stimmen || '' })
  return felder
})

/** Rechte-Status → Kennzeichen-Variante. */
function rechteVariante(s) {
  if (s === 'Gemeinfrei') return 'ok'
  if (s === 'Lizenz vorhanden') return 'info'
  if (s === 'Lizenz nötig') return 'warn'
  return 'err'
}

function formatDate(val) {
  if (!val) return ''
  const d = new Date(String(val).replace(' ', 'T'))
  if (isNaN(d)) return val
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
}

async function loadDetail() {
  if (!liedName) {
    error.value = 'Keine Lied-ID angegeben.'
    loading.value = false
    return
  }
  loading.value = true
  error.value = null
  try {
    const data = await apiCall('diakronos.psalmos.api.musik.get_lied_detail', { lied: liedName })
    lied.value = data?.lied || {}
    strophen.value = data?.strophen || []
    fassungen.value = data?.fassungen || []
    liedgruppen.value = data?.liedgruppen || []
    activeTab.value = 0
  } catch (err) {
    error.value = err?.message || 'Fehler beim Laden des Liedes'
    console.error('LiedDetail — Fehler:', err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadDetail(), rechteLaden()])
})

/* ── LI1: Bearbeiten nur für Schreibberechtigte ─────────────────────────── */
const { user, isAdmin } = useSession()

async function rechteLaden() {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {})
    darfSchreiben.value = !!erg?.darf_schreiben
  } catch (e) {
    darfSchreiben.value = !!isAdmin.value
  }
}

/** Nach dem Speichern in der Bearbeiten-Ansicht: Detail neu laden und zeigen. */
async function nachSpeichern(name) {
  bearbeiten.value = false
  if (name && name !== liedName) {
    navigate('#/lieder/' + encodeURIComponent(name))
    return
  }
  await loadDetail()
}
</script>

<style scoped>
.ld-zustand { padding: var(--sp-8); text-align: center; color: var(--muted); }
.ld-muted { font-size: var(--fs-sm); color: var(--muted); }

.ld-head-inhalt {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
}
.ld-head-haupt { min-width: 0; }
.ld-head-neben { max-width: 320px; font-size: var(--fs-sm); color: var(--muted); text-align: right; }
.ld-head-neben p { margin: 0 0 6px; }
.ld-rechtehinweis { color: var(--subtle); font-style: italic; }
.ld-meta-row { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-bottom: var(--sp-3); }
.ld-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--sp-1); }

/* Entwicklung 16.10.: Zwischen den großen Blöcken (Kopf-Karte, Raster,
   Seitenleiste) fehlte der Abstand — die Blöcke stießen direkt aneinander.
   Das `.dk-screen` der Seite gibt nur Innenabstand, keinen Zwischenraum. */
.ld-head { margin-bottom: var(--sp-4); }
.ld-grid { display: grid; grid-template-columns: 1fr 280px; gap: var(--sp-4); align-items: start; }
@media (max-width: 860px) { .ld-grid { grid-template-columns: 1fr; } }
.ld-main { display: flex; flex-direction: column; gap: var(--sp-4); min-width: 0; }
.ld-side { min-width: 0; }

.ld-strophe { padding: var(--sp-3) 0; border-top: 1px solid var(--divider); }
.ld-strophe:first-of-type { border-top: none; }
.ld-strophe-head { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: 6px; }
.ld-strophe-nr {
  width: 22px; height: 22px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--surface-2);
  color: var(--muted); font-size: var(--fs-xs); font-weight: 600;
}
.ld-strophe-sprache { font-size: var(--fs-xs); color: var(--subtle); }
.ld-strophe-text { margin: 0; font-size: var(--fs); line-height: 1.6; color: var(--text); white-space: pre-wrap; }

.ld-tabs {
  display: flex; flex-wrap: wrap; gap: 6px;
  border-bottom: 1px solid var(--line);
  padding-bottom: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.ld-tab {
  font-size: var(--fs-sm);
  padding: 6px var(--sp-3);
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--muted);
  cursor: pointer;
  transition: background var(--fast) var(--ease), color var(--fast) var(--ease), border-color var(--fast) var(--ease);
}
.ld-tab:hover { border-color: var(--primary); color: var(--text); }
.ld-tab.is-active { background: var(--primary); border-color: var(--primary); color: var(--primary-ink); }
.ld-tab-star { margin-right: 3px; color: var(--accent); }

.ld-fassung-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--sp-3) var(--sp-4); }
.ld-fassung-field { display: flex; flex-direction: column; gap: 2px; }
.ld-fassung-label { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.03em; color: var(--subtle); }
.ld-fassung-value { font-size: var(--fs-sm); font-weight: 500; color: var(--text); }
.ld-fassung-notiz { margin: var(--sp-3) 0 0; font-size: var(--fs-sm); color: var(--muted); }

.ld-material { margin-top: var(--sp-4); }
.ld-material-title { font-size: var(--fs-sm); font-weight: 600; text-transform: uppercase; color: var(--muted); margin: 0 0 var(--sp-2); }
.ld-fassung-links { margin-top: var(--sp-3); }
.ld-link { color: var(--primary); font-size: var(--fs-sm); text-decoration: none; }
.ld-link:hover { text-decoration: underline; }

.ld-group-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.ld-group-link {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: var(--sp-2) var(--sp-3); border-radius: var(--radius); border: 1px solid var(--line);
  text-decoration: none; color: var(--text);
  transition: border-color var(--fast) var(--ease), background var(--fast) var(--ease);
}
.ld-group-link:hover { border-color: var(--primary); background: var(--surface-2); }
.ld-group-name { font-size: var(--fs-sm); font-weight: 500; }
.ld-group-num { font-size: var(--fs-sm); color: var(--muted); }
.ld-group-fassung { font-size: var(--fs-sm); color: var(--subtle); }

.ld-fehler {
  padding: var(--sp-5);
  background: var(--err-soft);
  border: 1px solid color-mix(in oklch, var(--err) 25%, var(--line));
  border-radius: var(--radius-lg);
  color: var(--err);
  font-size: var(--fs-sm);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
</style>
