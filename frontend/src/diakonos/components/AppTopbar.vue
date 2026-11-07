<template>
  <header class="dk-topbar">
    <div class="dk-topbar-left">
      <!-- UX3e (Entwurf A8): Menü-Symbol OBEN LINKS öffnet die Schublade mit
           der vollständigen Navigation. Am Desktop ist es ausgeblendet (dort
           gibt es die Seitenleiste) — die Sichtbarkeit regelt index.css. Der
           Knopf liegt in der Kopfzeile, damit er auf JEDER Seite an derselben
           Stelle steht (Prinzip S4/S5) und nicht je Bereich wandert. -->
      <DkButton
        variant="ghost"
        class="dk-topbar-symbol dk-menue-knopf"
        :aria-label="MENUE_KNOPF_TEXT"
        :title="MENUE_KNOPF_TEXT"
        :aria-expanded="menueOffen ? 'true' : 'false'"
        aria-haspopup="dialog"
        ref="menueKnopf"
        @click="$emit('open-menu')"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </DkButton>

      <!-- Zurück (UX1f): ein Weg der Kopfzeile, kein Alt-Knopf — dieselbe
           Gestaltung wie die übrigen ghost-Knöpfe (Symbol + Wort, N8), aber in
           der Höhe der Kopfzeilenknöpfe (md statt sm). -->
      <DkButton
        v-if="showBack"
        variant="ghost"
        class="dk-zurueck"
        @click="navigateBack"
      >
        <template #icon>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        </template>
        Zurück
      </DkButton>

      <!-- Breadcrumbs -->
      <nav class="dk-crumbs">
        <span v-for="(crumb, i) in breadcrumbs" :key="i" class="dk-crumb">
          <span class="dk-crumb-sep" v-if="i > 0">/</span>
          <span :class="i === breadcrumbs.length - 1 ? 'dk-crumb-current' : ''">{{ crumb }}</span>
        </span>
      </nav>
    </div>

    <div class="dk-topbar-right">
      <!-- UX3f (Entwurf A5): Die Kopfzeile trägt wieder eine Suche — diesmal
           MIT Funktion: der Klick öffnet die Befehlspalette (Strg+K / ⌘+K).
           Der frühere tote „Suchen ⌘K“-Knopf (UXD-R19) war reines Markup ohne
           Ziel; dieser hier ruft `oeffnen()` der Palette auf. Das Kürzel steht
           als Text „Strg K“ daneben (nicht als Tastatur-Element), damit die
           Anzeige nicht wie eine zweite Bedienfläche wirkt. -->
      <button
        type="button"
        class="dk-topbar-suche"
        title="Suchen (Strg K)"
        aria-label="Suchen — Befehlspalette öffnen (Strg K)"
        @click="$emit('suche')"
      >
        <DkSymbol name="suchen" :groesse="16" />
        <span>Suchen …</span>
        <span class="dk-topbar-suche-kuerzel" aria-hidden="true">Strg K</span>
      </button>

      <!-- Notifications (OP-HANDY-6): Klick OEFFNET die Liste. Markiert wird
           erst danach — vorher setzte der Klick ungesehen alles auf gelesen. -->
      <div class="dk-notify">
        <DkButton
          variant="ghost"
          class="dk-topbar-symbol"
          :aria-label="unreadCount > 0 ? `${unreadCount} neue Benachrichtigungen` : 'Benachrichtigungen'"
          :title="unreadCount > 0 ? `${unreadCount} neue Benachrichtigungen` : 'Benachrichtigungen'"
          :aria-expanded="listeOffen ? 'true' : 'false'"
          @click="toggleListe"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          <span v-if="unreadCount > 0" class="dk-notify-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </DkButton>

        <div v-if="listeOffen" class="dk-notify-panel" role="dialog" aria-label="Benachrichtigungen">
          <div class="dk-notify-kopf">
            <strong>Benachrichtigungen</strong>
            <!-- UX1g: Der Schliessen-Knopf des Panels ist ein Knopf des
                 Systems (ghost, benannt) statt eines stummen „✕" in 28 px. -->
            <DkButton
              variant="ghost"
              class="dk-notify-schliessen"
              aria-label="Benachrichtigungen schliessen"
              title="Schließen"
              @click="listeOffen = false"
            >✕</DkButton>
          </div>
          <!-- UX2d3a: ruhiger Platzhalter statt „Lade …“; bei Fehler die echte
               Meldung mit „Erneut versuchen“ am vorhandenen `ladeListe`. -->
          <DkSkelett v-if="listenSichtbar" kurz form="zeilen" :anzahl="3" text="Benachrichtigungen werden geladen" />
          <DkEmpty
            v-else-if="fehler"
            icon="!"
            title="Benachrichtigungen nicht geladen"
            :text="fehler"
            :erneut-versuchen="ladeListe"
          />
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
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import DkButton from './ui/DkButton.vue'
import DkSkelett from './ui/DkSkelett.vue'
import DkEmpty from './ui/DkEmpty.vue'
import DkSymbol from './ui/DkSymbol.vue'
import { darfAlsGelesenMarkieren } from '../composables/glocke.mjs'
import { krumenZuSeite } from '../menue.js'
import { MENUE_KNOPF_TEXT } from './handyMenue.mjs'

defineProps({
  collapsed: Boolean,
  // UX3e: Zustand des Menü-Knopfes (`aria-expanded`) — er muss sagen, ob die
  // Schublade offen ist, sonst kündigt er sie falsch an (Prinzip N4/S4).
  menueOffen: { type: Boolean, default: false },
})
// UX3f: `suche` öffnet die Befehlspalette (der Klick auf das Suchfeld).
defineEmits(['toggle-collapse', 'open-menu', 'suche'])

const { unreadCount, notifications, laden, fehler, ladeListe, markAsRead } = useNotifications()
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar: listenSichtbar } = useLadeSkelett(laden)
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
  if (page.value === 'MitgliedDetail') navigate('#/personen')
  else if (page.value === 'GruppeDetail') navigate('#/gruppen')
}
</script>
