<template>
  <div class="dk-screen dk-screen-enter">

    <!-- ON-4 (H1, Entwurf 10): Karte „Einrichtung abschließen — n von 7 offen“
         über der Widget-Übersicht. Sie entscheidet selbst, ob sie erscheint
         (`karteZeigen`: Admin, Assistent fertig, Punkte offen, keine
         Erinnerungspause) — hier steht nur der Einbau. -->
    <EinrichtungsKarte v-if="istAdmin" :admin="istAdmin" />

    <!-- Edit-Bar -->
    <div v-if="isEditing" class="dk-widget-edit-bar">
      <span class="dk-widget-edit-label">Übersicht bearbeiten</span>
      <div class="hm-aktionen">
        <DkButton
          variant="ghost"
          size="md"
          @click="resetLayout"
        >Zurücksetzen</DkButton>
        <DkButton
          variant="primary"
          size="md"
          @click="store.isEditing = false"
        >Fertig</DkButton>
      </div>
    </div>

    <!-- UX2d3c: Fehlerzustand der Übersicht. Vorher blieb der Bildschirm bei
         einem gescheiterten Laden LEER (das Widget-Layout kam nie an) — jetzt
         sagt die Fläche, was passiert ist, und bietet „Erneut versuchen". -->
    <DkEmpty
      v-if="store.fehler"
      icon="!"
      title="Übersicht nicht geladen"
      :text="store.fehler"
      :erneut-versuchen="store.loadConfig"
    />

    <!-- UX2d3c: Leerzustand mit Erklärung und nächstem Schritt. Zwei Wege:
         die Karten der Übersicht einblenden (Bearbeiten-Modus) oder die
         Standardübersicht zurückholen. -->
    <DkEmpty
      v-else-if="!store.loading && sichtbareWidgets.length === 0"
      icon="▦"
      title="Keine Karten sichtbar"
      text="Du hast alle Karten der Übersicht ausgeblendet. Blende sie wieder ein oder hole die Standardübersicht zurück."
    >
      <DkButton variant="primary" @click="store.isEditing = true">Karten einblenden</DkButton>
      <DkButton variant="secondary" @click="resetLayout">Standardübersicht</DkButton>
    </DkEmpty>

    <!-- Widget-Raster -->
    <WidgetGrid
      v-else-if="!store.loading"
      :widgets="sichtbareWidgets"
      :is-editing="isEditing"
      :badge-counts="badgeCounts"
      @hide-widget="store.toggleWidget"
      @reorder="onReorder"
      @collapse-widget="onCollapseChange"
    />

    <!-- Lade-Skeleton -->
    <div v-else class="dk-widget-grid-wrapper">
      <div v-for="i in 4" :key="i" class="dk-widget-card dk-widget-medium dk-widget-skeleton-card">
        <div class="dk-skeleton-line hm-skelett-titel"></div>
        <div class="dk-skeleton-line hm-skelett-breit"></div>
        <div class="dk-skeleton-line hm-skelett-mittel"></div>
      </div>
    </div>

    <!-- Ausgeblendete Widgets in Bearbeiten-Modus -->
    <div v-if="isEditing && hiddenWidgets.length" class="dk-widget-hidden-section">
      <p class="dk-widget-hidden-label">Ausgeblendete Karten</p>
      <div class="dk-widget-hidden-list">
        <div
          v-for="widget in hiddenWidgets"
          :key="widget.widget_id"
          class="dk-widget-hidden-item"
          @click="store.toggleWidget(widget.widget_id)"
        >
          <span>{{ widget.label }}</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </div>
      </div>
    </div>

    <!-- Bearbeiten-FAB -->
    <button
      v-if="!isEditing"
      class="dk-widget-edit-fab"
      title="Übersicht bearbeiten"
      @click="store.isEditing = true"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
    </button>

  </div>
</template>

<script setup>
import { apiAntwortPruefen } from '../composables/useApi.js'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../../shared/basis.js'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useDashboardConfig } from '../stores/dashboardConfig'
import { useSession } from '../composables/useSession.js'
import WidgetGrid from '../components/widgets/WidgetGrid.vue'
// ON-4/H1: die Einrichtungs-Karte („Einrichtung abschließen“).
import EinrichtungsKarte from '../components/einrichtung/EinrichtungsKarte.vue'
// UX2d3c: Leer-/Fehlerzustand der Übersicht aus der UI-Bibliothek.
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkButton from '../components/ui/DkButton.vue'

const pinia = createPinia()
setActivePinia(pinia)

const store = useDashboardConfig()
const { user, isAdmin: istAdminRef } = useSession()
// ON-4/H1: Die Einrichtungs-Karte ist Verwaltungsarbeit — nur Admin-Rollen
// (der Server verweigert `einrichtung.status` sonst mit 403).
const istAdmin = computed(() => istAdminRef.value === true)
const isEditing = computed(() => store.isEditing)
const hiddenWidgets = computed(() => store.allWidgets.filter(w => !w.visible))
const badgeCounts = ref({})
let badgeTimer = null

/**
 * MAIL-1b (N3, Kartentreue S5): „Mailversand ist noch nicht eingerichtet …“
 * muss auf der ADMIN-STARTSEITE stehen, nicht nur bei den Löschanträgen. Damit
 * diese Warnung nicht durch Ausblenden verschwindet, hält die Startseite die
 * DSGVO-Kachel für System Manager sichtbar — dieselbe Kachel, die auch den
 * Stand der Löschanträge zeigt.
 *
 * Das ist reine Anzeige: der Server entscheidet (die Kachel fragt
 * `mailversand_status`, dort sehen nur System Manager ein `darf_aendern`).
 */
const DSGVO_COMPLIANCE = 'dsgvo-compliance';

function istErzwungen(widget) {
  return widget.widget_id === DSGVO_COMPLIANCE && user.value?.isSystemManager === true;
}

// Die sichtbaren Kacheln, ergänzt um die erzwungene DSGVO-Kachel eines
// System Managers (Reihenfolge: ihre gespeicherte Position, sonst ans Ende).
const sichtbareWidgets = computed(() => {
  const liste = store.visibleWidgets.filter((widget) => widget.visible || istErzwungen(widget));
  if (liste.length === store.visibleWidgets.length) return liste;
  const fehlend = store.allWidgets.filter(
    (widget) => istErzwungen(widget) && !liste.some((w) => w.widget_id === widget.widget_id),
  );
  return [...liste, ...fehlend].sort((a, b) => (a.position ?? 99) - (b.position ?? 99));
});

onMounted(async () => {
  await store.loadConfig()
  loadBadgeCounts()
  badgeTimer = setInterval(loadBadgeCounts, 60_000)
})

onUnmounted(() => clearInterval(badgeTimer))

async function loadBadgeCounts() {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch(apiUrl('diakronos.diakonos.api.dashboard.get_widget_badge_counts'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({}),
    })
    const json = await apiAntwortPruefen(res)
    badgeCounts.value = json.message || {}
  } catch {}
}

function onReorder(reordered) {
  reordered.forEach(w => {
    const item = store.layout.find(l => l.widget_id === w.widget_id)
    if (item) item.position = w.position
  })
  store.scheduleSave()
}

function onCollapseChange(widgetId, collapsed) {
  const w = store.layout.find(l => l.widget_id === widgetId)
  if (w) {
    w.collapsed = collapsed
    store.scheduleSave()
  }
}

async function resetLayout() {
  await store.resetToDefaults()
}
</script>
<style scoped>
/* DES-02: Inline-Angaben der Bearbeiten-Leiste und des Ladeskeletts als Klassen. */
.hm-aktionen { display: flex; gap: var(--sp-2); }
.hm-skelett-titel { width: 40%; height: 16px; margin-bottom: var(--sp-3); }
.hm-skelett-breit { width: 80%; }
.hm-skelett-mittel { width: 60%; }

/* FIX-6: Der Bearbeiten-Knopf der Startseite wird in der Mobil-Lage zur
   breiten Leiste unter den Kacheln — LAYOUT, also nur die Breite
   (index.css «FIX-6 · Layout nur nach Breite», composables/eingabeart.mjs
   `istMobilLayout`). Vorher stand hier `(hover: none) and (pointer: coarse)`:
   ein Touch-Notebook mit 1410 px bekam die mobile Leiste, obwohl Maus und
   Platz vorhanden sind. */
@media (max-width: 720px) {
  .dk-widget-edit-fab {
    position: static !important;
    bottom: auto !important;
    right: auto !important;
    display: flex !important;
    width: 100%;
    margin-top: 12px;
    justify-content: center;
    background: none !important;
    box-shadow: none !important;
    border: 1px solid var(--dk-border) !important;
    border-radius: 8px !important;
    color: var(--dk-text-muted) !important;
    padding: 10px 16px !important;
    font-size: var(--fs-14) !important;
    gap: 6px;
  }
}
</style>
