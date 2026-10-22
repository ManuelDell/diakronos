<template>
  <header class="dk-topbar">
    <div class="dk-topbar-left">
      <!-- Mobile menu toggle -->
      <button class="dk-icon-btn" style="display:none" @click="$emit('toggle-collapse')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>

      <!-- Back button for detail pages -->
      <button
        v-if="showBack"
        class="dk-btn dk-btn-ghost dk-btn-sm"
        @click="navigateBack"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        Zurück
      </button>

      <!-- Breadcrumbs -->
      <nav class="dk-crumbs">
        <span v-for="(crumb, i) in breadcrumbs" :key="i" class="dk-crumb">
          <span class="dk-crumb-sep" v-if="i > 0">/</span>
          <span :class="i === breadcrumbs.length - 1 ? 'dk-crumb-current' : ''">{{ crumb }}</span>
        </span>
      </nav>
    </div>

    <div class="dk-topbar-right">
      <!-- UXD-R19: Der frühere Such-Knopf war ohne Funktion (Kopfzeile wie
           Seitenleiste) und wurde entfernt. -->

      <!-- Notifications (OP-HANDY-6): Klick OEFFNET die Liste. Markiert wird
           erst danach — vorher setzte der Klick ungesehen alles auf gelesen. -->
      <div class="dk-notify">
        <button
          class="dk-icon-btn"
          :title="unreadCount > 0 ? `${unreadCount} neue Benachrichtigungen` : 'Benachrichtigungen'"
          :aria-expanded="listeOffen ? 'true' : 'false'"
          @click="toggleListe"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          <span v-if="unreadCount > 0" class="dk-notify-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </button>

        <div v-if="listeOffen" class="dk-notify-panel" role="dialog" aria-label="Benachrichtigungen">
          <div class="dk-notify-kopf">
            <strong>Benachrichtigungen</strong>
            <button type="button" class="dk-notify-schliessen" title="Schließen" @click="listeOffen = false">✕</button>
          </div>
          <div v-if="laden" class="dk-notify-zustand">Lade …</div>
          <div v-else-if="fehler" class="dk-notify-zustand dk-notify-zustand--fehler">{{ fehler }}</div>
          <div v-else-if="!notifications.length" class="dk-notify-zustand">
            Keine Benachrichtigungen.
          </div>
          <ul v-else class="dk-notify-liste">
            <li
              v-for="n in notifications"
              :key="n.name"
              class="dk-notify-eintrag"
              :class="{ 'is-neu': !n.read }"
            >
              <div class="dk-notify-betreff">{{ n.subject || 'Benachrichtigung' }}</div>
              <div class="dk-notify-text">{{ kurz(n.email_content) }}</div>
              <div class="dk-notify-zeit">{{ zeitText(n.creation) }}</div>
            </li>
          </ul>
        </div>
      </div>

      <div class="dk-topbar-divider" />
    </div>
  </header>
</template>

<script setup>
import { computed, ref, nextTick, onMounted, onUnmounted } from 'vue'
import { currentPageName, navigate } from '../router.js'
import { useNotifications } from '../composables/useNotifications.js'
import { darfAlsGelesenMarkieren } from '../composables/glocke.mjs'
import { krumenZuSeite } from '../menue.js'

defineProps({ collapsed: Boolean })
defineEmits(['toggle-collapse'])

const { unreadCount, notifications, laden, fehler, ladeListe, markAsRead } = useNotifications()
const page = currentPageName

// Listen-Panel: Klick auf die Glocke laedt die Liste und markiert erst
// anschliessend als gelesen (OP-HANDY-6).
const listeOffen = ref(false)
let oeffnung = 0

async function toggleListe() {
  if (listeOffen.value) {
    listeOffen.value = false
    return
  }
  const aktuell = ++oeffnung
  listeOffen.value = true
  const eintraege = await ladeListe()
  // Erst nach erfolgreichem Rendern der weiterhin aktuellen Öffnung lesen.
  // Eine alte Antwort darf weder ein geschlossenes noch ein neu geöffnetes
  // Panel stellvertretend als gesehen behandeln (REST-1: die Bedingung steht
  // als reine Funktion in `glocke.mjs` und ist dort ohne Browser geprüft).
  await nextTick()
  if (!darfAlsGelesenMarkieren({
    offen: listeOffen.value, anfrage: aktuell, oeffnung, eintraege, fehler: fehler.value,
  })) return
  if (unreadCount.value > 0) await markAsRead(eintraege)
}

function schliesseBeiKlick(event) {
  if (event.target.closest?.('.dk-notify')) return
  listeOffen.value = false
}

function beiFlucht(event) {
  if (event.key === 'Escape') listeOffen.value = false
}

onMounted(() => {
  document.addEventListener('click', schliesseBeiKlick)
  document.addEventListener('keydown', beiFlucht)
})
onUnmounted(() => {
  listeOffen.value = false
  ++oeffnung
  document.removeEventListener('click', schliesseBeiKlick)
  document.removeEventListener('keydown', beiFlucht)
})

function kurz(text) {
  const s = String(text || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
  return s.length > 160 ? s.slice(0, 157) + '…' : s
}

function zeitText(iso) {
  if (!iso) return ''
  const d = new Date(String(iso).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const CRUMB_MAP = {
  PlanrahmenPlan:       ['Pläne', 'Plan'],
  PlanrahmenEinrichten: ['Pläne', 'Einrichten'],
  PlanrahmenPlantypEditor: ['Pläne', 'Planvorlage bearbeiten'],
  PlanrahmenStammdaten: ['Pläne', 'Stammdaten'],
  MitgliedDetail:['Mitglieder', 'Profil'],
  GruppeDetail:  ['Gruppen', 'Detail'],
  KalenderImport:['Kalender', 'Import'],
  LiedNeu:       ['Lieder', 'Neu'],
  LiedDetail:    ['Lieder', 'Detail'],
  LiedgruppeDetail: ['Liedgruppen', 'Detail'],
  Profile:       ['Profil'],
  // UXM-R14: Seiten ohne Menüeintrag zeigten den rohen Komponentennamen.
  // Sie bekommen hier ihren Lesetext — „Registrierung“ heißt wie die Seite,
  // nicht „Anmeldungen“. Die alte Seite „Anmeldung“ ist mit N12 entfallen
  // (ihre Einstellungen liegen unter „Einstellungen → Anmeldung“).
  Registrierung: ['Mitglieder', 'Registrierung'],
  Wiki:          ['Wiki'],
  NichtGefunden: ['Seite nicht gefunden'],
}

// Brotkrumen aus der zentralen Menüdefinition (Standard S12). Der Rückfall
// liefert IMMER einen Lesetext — nie einen internen Komponentennamen.
const breadcrumbs = computed(() => CRUMB_MAP[page.value] || krumenZuSeite(page.value) || ['Übersicht'])

const showBack = computed(() => ['MitgliedDetail', 'GruppeDetail'].includes(page.value))

function navigateBack() {
  if (page.value === 'MitgliedDetail') navigate('#/mitglieder')
  else if (page.value === 'GruppeDetail') navigate('#/gruppen')
}
</script>
