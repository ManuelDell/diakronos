<template>
  <FrappeUIProvider>
    <!-- DES-R18: Sprunglink. Am Dashboard lagen 24 Tab-Stopps vor dem Inhalt
         (Seitenleiste, Kopfleiste). Er ist das erste fokussierbare Element,
         bleibt ausserhalb des Fokus unsichtbar und springt zum Hauptbereich.
         P3-4 (Restpunkt 5): als <button> statt <a href="#dk-inhalt"> — der
         Fragment-Link haette im Hash-Router eine zweite Adresse (#dk-inhalt)
         erzeugt; Mittelklick/„In neuem Tab öffnen" landete auf einer
         kaputten Seite. Ein Knopf kann das nicht. -->
    <button type="button" class="dk-sprunglink" @click="zumInhalt">Zum Inhalt springen</button>
    <!-- Impersonation Banner -->
    <div v-if=impersonation.isActive.value class="impersonation-banner">
      <span>👁️ Du siehst als <strong>{{ impersonation.fullName.value }}</strong></span>
      <span class="impersonation-timer">{{ remainingTime }}</span>
      <button class="impersonation-stop" @click="stopImpersonation">✕ Beenden</button>
    </div>
    <div class="dk-app" :class="{ 'is-collapsed': sidebarCollapsed, 'has-impersonation-banner': impersonation.isActive.value }" :data-theme="theme">
      <!-- OP-UI-11: Das Hauptmenü bleibt in JEDER Ansicht dasselbe. Vorher
           tauschte der Kalender (und die Moderation) die Hauptnavigation
           gegen eine eigene Leiste; „Zur Hauptnavigation“ warf den Nutzer
           zwei Klicks zurück aufs Dashboard. Jetzt steht überall dieselbe
           Seitenleiste aus menue.js. Die Kalenderliste des Kalenders liegt
           als einklappbares Feld IN der Seite (Kalender.vue). -->
      <AppSidebar :collapsed="sidebarCollapsed" :theme="theme" @toggle-collapse="sidebarCollapsed = !sidebarCollapsed" @toggle-theme="toggleTheme" />
      <div class="dk-main-wrap">
        <AppTopbar :collapsed="sidebarCollapsed" @toggle-collapse="sidebarCollapsed = !sidebarCollapsed" />
        <!-- OP-HANDY-24: Fortschrittsbalken während des Seitenwechsels. Bei
             langsamem Netz blieb sonst die alte Seite ohne jede Rückmeldung
             stehen; erst der fertig geladene Chunk wechselte das Bild. -->
        <div class="dk-seitenbalken" :class="{ 'is-ladend': seitenLadend }" role="progressbar"
             aria-label="Seite wird geladen" :aria-hidden="!seitenLadend"></div>
        <div
          id="dk-inhalt"
          class="dk-content"
          tabindex="-1"
          :class="{ 'dk-content--kronos': isKronosMode, 'dk-content--moderation': isModerationMode }"
        >
          <!-- UXD-R7: `:key` erzwingt einen Neubau der Seitenkomponente beim
               Wechsel zwischen zwei Detailrouten derselben Seite
               (#/gruppe/A -> #/gruppe/B). Ohne den Schluessel blieb die alte
               Instanz gemountet und zeigte weiter das vorige Objekt.

               P3-1b (W2/UXD-R20): Seiten, die ihre Adresse IM BETRIEB nur zum
               Teilen nachführen (Wiki-Artikel), schreiben sie mit
               `history.replaceState` und loesen damit keinen Routenwechsel und
               keinen Neuaufbau aus — der Schluessel bleibt hier der Hash. -->
          <component :is="currentComponent" :key="currentHash" v-if="currentComponent" />
          <!-- Nachladen fehlgeschlagen: verstaendliche Meldung statt ewiger
               Spinner (Dev-Befund #/planrahmen/meine-dienste, 16.10.). -->
          <div v-else-if="pageLadefehler" class="dk-screen dk-screen-enter" style="padding:40px 24px;">
            <div style="max-width:520px;margin:0 auto;text-align:center;">
              <p style="font-size:15px;font-weight:600;color:var(--dk-text);margin:0 0 6px;">{{ pageLadefehler.meldung }}</p>
              <p style="font-size:13px;color:var(--dk-text-muted);margin:0 0 16px;">{{ pageLadefehler.hinweis }}</p>
              <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
                <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" @click="routeNeuLaden">Nochmal versuchen</button>
                <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/">Zur Übersicht</a>
              </div>
            </div>
          </div>
          <div v-else class="dk-screen dk-screen-enter" style="display:flex;align-items:center;justify-content:center;min-height:300px;">
            <div style="text-align:center;color:var(--dk-text-subtle)">
              <div style="width:32px;height:32px;border:2px solid var(--dk-border);border-top-color:var(--dk-brand-800);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px"></div>
              <p style="font-size:13px;margin:0">Wird geladen…</p>
            </div>
          </div>
        </div>
        <AuditConfirmModal v-if="!isKronosMode && !isModerationMode" />
      </div>
    </div>
    <!-- DM1: Dev-Modus-Rahmen. Der Overlay-Code wird NUR geladen, wenn der
         Nutzer den Dev-Modus eingeschaltet hat (defineAsyncComponent). Ohne
         Dev-Modus existiert hier nichts und es wird auch nichts nachgeladen. -->
    <DevRahmen v-if="devmodusAn" />
    <!-- DM1: Einschalt-Knopf — nur wenn der Server den Dev-Modus erlaubt und
         der Nutzer berechtigt ist, aber noch keine Dev-Sitzung laeuft. -->
    <DevStart v-else-if="devmodusVerfuegbar" />
    <AppBottomNav :theme="theme" @toggle-theme="toggleTheme" @open-admin-dialog="handleOpenAdminDialog" />
    <!-- K-A (R-P1-8): Detailansicht des EIGENEN abgelehnten Termins aus der
         Kalender-Seitenleiste. Der Termin kommt aus `get_mein_termin`; der
         Server liefert ihn nur an den Antragsteller bzw. Moderatoren, weil
         abgelehnte Termine sonst aus allen Listen heraus bleiben. -->
    <KronosEventView
      v-model:show="showAbgelehntView"
      :event="abgelehnterTermin"
    />
    <SitzungsHinweis />
    <DkBestaetigung />
  </FrappeUIProvider>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { FrappeUIProvider } from 'frappe-ui'
import AppSidebar from './components/AppSidebar.vue'
import SitzungsHinweis from './components/SitzungsHinweis.vue'
import DkBestaetigung from './components/ui/DkBestaetigung.vue'
import AppTopbar from './components/AppTopbar.vue'
import AuditConfirmModal from './components/AuditConfirmModal.vue'
import AppBottomNav from './components/AppBottomNav.vue'
import { currentComponent, currentHash, navigate, pageLadefehler, routeNeuLaden, seitenLadend } from './router.js'
import { useImpersonation } from './composables/useImpersonation.js'
import { devmodusAn, devmodusAutostart, devmodusPruefen } from './composables/useDevmodus.js'
import { useSession } from './composables/useSession.js'
import { useKronosSidebar } from './composables/useKronosSidebar.js'
import { showToast } from './composables/useToast.js'
import { getMeinTermin } from './composables/useEventsApi.js'
import { startTheme, naechstesTheme, umschalterText } from './composables/theme.mjs'

// DM1: Der Dev-Rahmen wird NUR geladen, wenn der Dev-Modus aktiv ist —
// defineAsyncComponent sorgt dafuer, dass der Overlay-Code (inkl. der
// Screenshot-Bibliothek) bei normalen Nutzern nie im Bundle landet.
import { defineAsyncComponent } from 'vue'
const DevRahmen = defineAsyncComponent(() => import('./components/devmodus/Rahmen.vue'))
const DevStart = defineAsyncComponent(() => import('./components/devmodus/DevStart.vue'))

const { istTester: istTesterRef, devmodeAn: serverDevmodeRef } = useSession()
const devmodusVerfuegbar = computed(() => Boolean(istTesterRef?.value && serverDevmodeRef?.value))

async function devmodusBeimStart() {
  await devmodusAutostart()
}

const sidebarCollapsed = ref(false)
/**
 * DES-R22: Startwert aus composables/theme.mjs — erst die bewusste Wahl
 * (localStorage), sonst die Systemeinstellung, sonst hell.
 */
function systemTheme() {
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return null
}
const theme = ref(startTheme({ speicher: window.localStorage, system: systemTheme() }))

// DES-R1: Das Theme muss am Wurzelelement stehen, nicht nur am App-Container.
// Dialoge, das „Mehr“-Blatt der Handy-Navigation und die Toast-Meldungen
// werden an <body> teleportiert und lagen damit AUSSERHALB von .dk-app — sie
// behielten die hellen :root-Werte und standen als grellweisse Fenster in der
// dunklen Ansicht. `document.documentElement` ist Vorfahre beider Bereiche.
watch(theme, (wert) => {
  document.documentElement.setAttribute('data-theme', wert)
}, { immediate: true })
const isKronosMode = computed(() => currentHash.value === '#/kalender')
const isModerationMode = computed(() => currentHash.value === '#/moderation')
const impersonation = useImpersonation()
const now = ref(Date.now())

watch(isKronosMode, (val) => {
  if (val) sidebarCollapsed.value = false
})

const remainingTime = computed(() => {
  if (!impersonation.expiresAt.value) return ''
  const ms = impersonation.expiresAt.value - now.value
  if (ms <= 0) return '00:00'
  const min = Math.floor(ms / 60000)
  const sec = Math.floor((ms % 60000) / 1000)
  return `${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
})

let timer
onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now()
    impersonation.checkExpiry()
  }, 1000)
  // DM1: Dev-Modus-Zustand vom Server holen (bei Bedarf automatisch starten).
  devmodusBeimStart()
  window.addEventListener('dk-devmodus-start', devmodusPruefen)
})
onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('dk-devmodus-start', devmodusPruefen)
})

function stopImpersonation() {
  impersonation.stop()
  navigate('#/')
}

const { enterAdminMode } = useSession()
function handleOpenAdminDialog() { enterAdminMode() }
/**
 * DES-R18: Fokus auf den Hauptbereich setzen. `scrollIntoView` waere hier
 * wirkungslos, weil der Hauptbereich selbst scrollt; der Fokus auf den
 * Container stellt zugleich den Anfang der Tab-Reihenfolge her.
 */
function zumInhalt() {
  const ziel = document.getElementById('dk-inhalt')
  if (!ziel) return
  ziel.focus({ preventScroll: true })
  ziel.scrollTop = 0
}

function toggleTheme() {
  theme.value = naechstesTheme(theme.value)
  try { localStorage.setItem('dk-theme', theme.value) } catch { /* gesperrt */ }
}
</script>

<style>
@keyframes spin { to { transform: rotate(360deg); } }
.impersonation-banner {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: var(--z-toast);
  background: var(--err);
  color: var(--surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: var(--shadow-md);
}
.impersonation-timer {
  font-family: monospace;
  font-size: 13px;
  opacity: 0.9;
}
.impersonation-stop {
  background: color-mix(in oklch, var(--surface) 22%, transparent);
  border: 1px solid color-mix(in oklch, var(--surface) 45%, transparent);
  color: var(--surface);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: background var(--fast);
}
.impersonation-stop:hover { background: color-mix(in oklch, var(--surface) 38%, transparent); }
.has-impersonation-banner { margin-top: 40px; }
</style>
