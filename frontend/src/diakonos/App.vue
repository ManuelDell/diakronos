<template>
  <!-- DEP-1: Der Anbieter von frappe-ui war eine reine Hülle — Socket und
       Ressourcen waren im Plugin ohnehin abgeschaltet (main.js), und keine
       Komponente hat ihn benutzt. Ersatzlos entfernt; jede der bisherigen
       Wurzeln (Seitenleiste, Sprunglink, Kopfleiste, Hauptbereich, Dialoge)
       steht weiterhin unmittelbar hier, deshalb bleibt die Vorlage mehrteilig. -->
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
    <div class="dk-app" :class="{ 'is-collapsed': sidebarCollapsed, 'has-impersonation-banner': impersonation.isActive.value, 'dk-app--vollbild': isVollbildMode, [HANDY_KLASSE]: istHandyLage }" :data-theme="theme">
      <!-- OP-UI-11: Das Hauptmenü bleibt in JEDER Ansicht dasselbe. Vorher
           tauschte der Kalender (und die Moderation) die Hauptnavigation
           gegen eine eigene Leiste; „Zur Hauptnavigation“ warf den Nutzer
           zwei Klicks zurück aufs Dashboard. Jetzt steht überall dieselbe
           Seitenleiste aus menue.js. Die Kalenderliste des Kalenders liegt
           als einklappbares Feld IN der Seite (Kalender.vue). -->
      <AppSidebar v-if="!isVollbildMode" :collapsed="sidebarCollapsed" :theme="theme" @toggle-collapse="sidebarCollapsed = !sidebarCollapsed" @toggle-theme="toggleTheme" />
      <div class="dk-main-wrap">
        <!-- UX3f (@suche) und UX3e (@open-menu) stehen NEBENeinander: das
             Suchfeld oeffnet die Befehlspalette, der Menue-Knopf (nur
             Mobil-Lage) die Schublade. -->
        <AppTopbar
          v-if="!isVollbildMode"
          :collapsed="sidebarCollapsed"
          :menue-offen="menueOffen"
          :rollen-marke="rollenMarke"
          @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
          @open-menu="menueOeffnen"
          @suche="befehlspalette?.oeffnen()"
        />
        <!-- OP-HANDY-24: Fortschrittsbalken während des Seitenwechsels. Bei
             langsamem Netz blieb sonst die alte Seite ohne jede Rückmeldung
             stehen; erst der fertig geladene Chunk wechselte das Bild. -->
        <div class="dk-seitenbalken" :class="{ 'is-ladend': seitenLadend }" role="progressbar"
             aria-label="Seite wird geladen" :aria-hidden="!seitenLadend"></div>
        <div
          id="dk-inhalt"
          class="dk-content"
          tabindex="-1"
          :class="{ 'dk-content--kronos': isKronosMode, 'dk-content--moderation': isModerationMode, 'dk-content--vollbild': isVollbildMode }"
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
              <p style="font-size:var(--fs-16);font-weight:var(--fw-fett);color:var(--dk-text);margin:0 0 6px;">{{ pageLadefehler.meldung }}</p>
              <p style="font-size:var(--fs-14);color:var(--dk-text-muted);margin:0 0 16px;">{{ pageLadefehler.hinweis }}</p>
              <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
                <DkButton
                  variant="primary"
                  size="md"
                  @click="routeNeuLaden"
                >Erneut versuchen</DkButton>
                <DkButton
                  variant="secondary"
                  size="md"
                  as="a"
                  href="#/"
                >Zur Übersicht</DkButton>
              </div>
            </div>
          </div>
          <!-- ON-3b (N4): Der Assistent bringt seinen EIGENEN Ladehinweis mit
               (`assistent-hinweis`). Der App-Rahmen zeigt beim Chunk-Laden
               sonst den Standard-Spinner — im Vollbild stünde er allein auf
               einer leeren Fläche, obwohl die Seite gleich ihre eigene Karte
               samt Kopfzeile aufbaut. -->
          <div v-else-if="!isVollbildMode" class="dk-screen dk-screen-enter" style="display:flex;align-items:center;justify-content:center;min-height:300px;">
            <!-- UX2d3a: gemeinsamer Platzhalter statt Spinner mit „Wird
                 geladen…“. Der Text bleibt als Vorlesehilfe am Baustein. -->
            <DkSpinner text="Seite wird geladen" />
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
    <AppBottomNav v-if="!isVollbildMode" :seite="currentPageName" />
    <!-- UX3e (Entwurf A9): Menü-Schublade — nur wenn es einen Menü-Knopf gibt,
         der sie öffnet: in der LEISTEN-Lage (`istHandyLage`). MT-1 (Manuel
         11.11., „nur EIN Seitenmenü“): am Laptop/Desktop gibt es sie NICHT
         mehr. Vorher stand sie bei eingeklappter Seitenleiste im DOM, geöffnet
         von einem zweiten Hamburger der Kopfzeile — daneben lag der
         Ausklapp-Knopf der Leiste selbst, zwei Einstiege für dasselbe Panel.
         Eingeklappt ist der Einstieg jetzt allein `.dk-sb-collapse` in der
         Leiste (index.css blendet den Kopfzeilen-Knopf dort aus). Damit es
         keinen Navigationsweg ohne sichtbaren Einstieg im Tab-Ring gibt,
         hängt das `v-if` an GENAU der Bedingung des Knopfes. -->
    <AppMenueSchublade
      v-if="!isVollbildMode && istHandyLage"
      :offen="menueOffen"
      :theme="theme"
      :seite="currentPageName"
      :hash="currentHash"
      @schliessen="menueOffen = false"
      @toggle-theme="toggleTheme"
    />
    <!-- FIX-7: Die Detailansicht des eigenen abgelehnten Termins haengt seit
         OP-UI-11 (`4927b9e2`) an der Kalenderliste in `pages/Kalender.vue` —
         dort stehen `showAbgelehntView` und `abgelehnterTermin`. Hier stand
         nur noch das Gerippe, und im Template fehlten BEIDE Bindungen: Vue
         brach beim Rendern mit „Property "showAbgelehntView" was accessed
         during render but is not defined" ab, sobald die App neu aufgebaut
         wurde. Ebenso `KronosEventView`, das hier nicht mehr importiert ist.
         Waechter: frontend/tests/fix7-vorlagen-bezeichner.test.mjs. -->
    <Befehlspalette ref="befehlspalette" />
    <SitzungsHinweis />
    <DkBestaetigung />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import SitzungsHinweis from './components/SitzungsHinweis.vue'
import DkBestaetigung from './components/ui/DkBestaetigung.vue'
import DkSpinner from './components/ui/DkSpinner.vue'
import AppTopbar from './components/AppTopbar.vue'
import AuditConfirmModal from './components/AuditConfirmModal.vue'
import AppBottomNav from './components/AppBottomNav.vue'
// UX3f: Befehlspalette (Strg+K), UX3e: Menü-Schublade am Handy (Entwurf A9).
import Befehlspalette from './components/Befehlspalette.vue'
import AppMenueSchublade from './components/AppMenueSchublade.vue'
import { currentComponent, currentHash, currentPageName, navigate, pageLadefehler, routeNeuLaden, seitenLadend } from './router.js'
import { useImpersonation } from './composables/useImpersonation.js'
import { devmodusAn, devmodusAutostart, devmodusPruefen } from './composables/useDevmodus.js'
import { useSession } from './composables/useSession.js'
// A10: Abzeichen der Seite an der App-Kopfzeile (am Handy neben dem Titel).
import { rollenMarke } from './composables/useBereichskopf.js'
// UX3e/DEV-B6: EINE Quelle der Handy-Lage (grob + schmal bzw. grobes
// Querformat) — dieselbe, die das CSS-Gerüst über die Klasse `.dk-app--handy`
// steuert. Vorher stand hier eine eigene Kopie der Zeichenkette.
import {
  HANDY_KLASSE, SEITENLEISTE_SCHMAL_ABFRAGE, useHandyLage,
} from './composables/handyLage.mjs'
// FIX-7: `useKronosSidebar`, `showToast` und `getMeinTermin` standen hier
// ohne jeden Nutzen — die Kalender-Seitenleiste und die Detailansicht des
// abgelehnten Termins liegen seit OP-UI-11 in `pages/Kalender.vue`.
import { startTheme, naechstesTheme, umschalterText } from './composables/theme.mjs'

// DM1: Der Dev-Rahmen wird NUR geladen, wenn der Dev-Modus aktiv ist —
// defineAsyncComponent sorgt dafuer, dass der Overlay-Code (inkl. der
// Screenshot-Bibliothek) bei normalen Nutzern nie im Bundle landet.
import { defineAsyncComponent } from 'vue'
import DkButton from './components/ui/DkButton.vue'
const DevRahmen = defineAsyncComponent(() => import('./components/devmodus/Rahmen.vue'))
const DevStart = defineAsyncComponent(() => import('./components/devmodus/DevStart.vue'))

const { istTester: istTesterRef, devmodeAn: serverDevmodeRef } = useSession()
const devmodusVerfuegbar = computed(() => Boolean(istTesterRef?.value && serverDevmodeRef?.value))

async function devmodusBeimStart() {
  await devmodusAutostart()
}

const sidebarCollapsed = ref(false)

/**
 * UX3e: Zustand der Menü-Schublade (nur Mobil-Lage). EIN offener Zustand in
 * App.vue, weil sowohl der Menü-Knopf der Kopfzeile als auch die Schublade
 * daran hängen — zwei Kopien liefen auseinander, sobald Esc oder Zurück
 * schließt.
 */
const menueOffen = ref(false)
function menueOeffnen() { menueOffen.value = true }

/**
 * Ist die App in der LEISTEN-Lage (untere Handy-Navigation, Kopfzeilen-Knopf,
 * Schublade im DOM)?
 *
 * DEV-B6 (Manuel 09.11., Befund DMB-3a7d335074cc; Review-Nacharbeit 10.11.):
 * „Auf einem Laptop darf nie die Handyleiste kommen.“ EINE Quelle —
 * `composables/handyLage.mjs`:
 *
 *   (pointer: coarse) and (max-width: 720px),
 *   (pointer: coarse) and (max-height: 480px) and (orientation: landscape)
 *
 * Dieselbe Zeichenkette steht als Token `--layout-mobil` in `tokens.css`;
 * das CSS-Gerüst hängt an der hieraus gesetzten Klasse `.dk-app--handy`
 * (`HANDY_KLASSE` im Template), NICHT an einer zweiten Media-Regel.
 * Ausdrücklich ändert das die Layout-Hälfte von FIX-6 („Zeiger ist nie
 * Layout-Kriterium“) — Begründung im Kartenkommentar DEV-B6.
 *
 * Beim Verlassen der Lage wird die Schublade geschlossen: sonst bliebe sie
 * „offen“ gemerkt, während es sie nicht mehr gibt.
 */
const { istHandyLage } = useHandyLage()
watch(istHandyLage, (an) => { if (!an) menueOffen.value = false })
/**
 * Schmale Fenster: Seitenleiste einklappen. Am Laptop (702 px, Befund) fraß
 * die offene Leiste 256 von 702 px — die Inhaltsfläche war schmaler als am
 * Handy. Eingeklappt bleibt die Navigation über den Ausklapp-Knopf der Leiste
 * selbst erreichbar (`.dk-sb-collapse` in AppSidebar.vue).
 *
 * MT-1 (Manuel 11.11.): Der frühere zweite Weg — ein Hamburger in der
 * Kopfzeile, der bei eingeklappter Leiste eine Schublade öffnete — ist
 * entfallen. Er stand neben der Überschrift und öffnete dasselbe Panel ein
 * zweites Mal; die Regel „nur EIN Seitenmenü“ gilt auf allen Oberflächen.
 *
 * DEV-B6/Review-Punkt 6: Das Einklappen ist die VORGABE je Breitenlage
 * (≤ 1100 px) und wird beim Wechsel der Lage nachgezogen — eine bewusste
 * Wahl des Nutzers überlebt, solange die Lage dieselbe bleibt.
 * `watch(isKronosMode)` klappt die Leiste NICHT mehr auf (das lief gegen
 * diese Vorgabe und öffnete beim Wechsel in den Kalender 256 px).
 */
let flachAbfrage = null
function breiteNachziehen() {
  if (!flachAbfrage) return
  sidebarCollapsed.value = flachAbfrage.matches
}
/**
 * UX3f: Griff auf die Befehlspalette. Der Klick auf das Suchfeld der Kopfzeile
 * ruft `oeffnen()`; das Tastenkürzel (Strg+K / ⌘+K) hört die Palette selbst.
 */
const befehlspalette = ref(null)
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
// Dialoge, die Menü-Schublade der Handy-Navigation und die Toast-Meldungen
// werden an <body> teleportiert und lagen damit AUSSERHALB von .dk-app — sie
// behielten die hellen :root-Werte und standen als grellweisse Fenster in der
// dunklen Ansicht. `document.documentElement` ist Vorfahre beider Bereiche.
watch(theme, (wert) => {
  document.documentElement.setAttribute('data-theme', wert)
}, { immediate: true })

/**
 * DEV-B6 (Review-Nacharbeit 10.11.): Die Handy-Lage zusätzlich an den
 * <body> — Leiste, Schublade, Befehlspalette und Meldungen werden NEBEN
 * `.dk-app` gerendert (Geschwister im Wurzelknoten), nicht darin. Im
 * Wegwerf-Stack gemessen: `nav.dk-bottom-nav` hing direkt an <body>, ein
 * Nachfahren-Wähler `.dk-app--handy …` konnte es nie erreichen — die Leiste
 * blieb auch am Touchgerät aus. Die Klasse steht deshalb an BEIDEN Stellen;
 * die Regeln bleiben unverändert (`.dk-app--handy …`).
 */
watch(istHandyLage, (an) => {
  if (typeof document === 'undefined' || !document.body) return
  document.body.classList.toggle(HANDY_KLASSE, an === true)
}, { immediate: true })
// UX3a: „Zu prüfen“ ist der vierte Reiter des Kalenders — beide Adressen
// zählen zum Kalender-Layout; die alte Adresse bleibt gültig (Weiterleitung).
const isKronosMode = computed(() => currentHash.value.startsWith('#/kalender'))
const isModerationMode = computed(() => ['#/moderation', '#/kalender/pruefen'].includes(currentHash.value))
/**
 * ON-3b (N4): Einrichtungs-Assistent im VOLLBILD (Entwurf 04/09).
 *
 * Der Assistent hat seine eigene Kopfzeile (Marke, „Einrichtung“, „Speichern
 * und später fortsetzen“) und seine eigene Fußleiste. Mit der App-Seitenleiste
 * und der App-Kopfzeile daneben standen zwei Leisten und zwei Kopfzeilen
 * übereinander — im Entwurf gibt es genau eine. Deshalb: keine Seitenleiste,
 * keine App-Kopfzeile, keine untere Navigation, solange `#/einrichtung` offen
 * ist. Die Rolle bleibt geprüft (Router-Guard + Server), nur das Gerüst
 * entfällt.
 */
const isVollbildMode = computed(() => currentHash.value === '#/einrichtung')
const impersonation = useImpersonation()
const now = ref(Date.now())

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
  // UX3e/DEV-B6: Schmale Fenster klappen die Seitenleiste ein. Die
  // LEISTEN-Lage beobachtet `useHandyLage()` selbst (matchMedia + resize).
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    flachAbfrage = window.matchMedia(SEITENLEISTE_SCHMAL_ABFRAGE)
    breiteNachziehen()
    if (typeof flachAbfrage.addEventListener === 'function') {
      flachAbfrage.addEventListener('change', breiteNachziehen)
    } else if (typeof flachAbfrage.addListener === 'function') {
      // Safari < 14 kennt nur addListener — sonst bliebe die Lage stehen.
      flachAbfrage.addListener(breiteNachziehen)
    }
  }
})
onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('dk-devmodus-start', devmodusPruefen)
  if (!flachAbfrage) return
  if (typeof flachAbfrage.removeEventListener === 'function') {
    flachAbfrage.removeEventListener('change', breiteNachziehen)
  } else if (typeof flachAbfrage.removeListener === 'function') {
    flachAbfrage.removeListener(breiteNachziehen)
  }
})

function stopImpersonation() {
  impersonation.stop()
  navigate('#/')
}

// UX3e: Die untere Leiste meldet kein `open-admin-dialog` mehr (der „Mehr“-
// Knopf ist entfallen) — der Admin-Dialog hängt am Rollenwechsel der Sitzung
// (`AuditConfirmModal`), nicht an einer Navigation.

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
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  box-shadow: var(--shadow-md);
}
.impersonation-timer {
  font-family: var(--font-mono);
  font-size: var(--fs-14);
  opacity: 0.9;
}
.impersonation-stop {
  background: color-mix(in oklch, var(--surface) 22%, transparent);
  border: 1px solid color-mix(in oklch, var(--surface) 45%, transparent);
  color: var(--surface);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--fs-14);
  font-weight: var(--fw-fett);
  transition: background var(--fast);
}
.impersonation-stop:hover { background: color-mix(in oklch, var(--surface) 38%, transparent); }
.has-impersonation-banner { margin-top: 40px; }
</style>
