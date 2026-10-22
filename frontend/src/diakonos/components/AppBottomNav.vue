<template>
  <!-- Nur auf Touch/Mobile sichtbar (via CSS) -->
  <nav class="dk-bottom-nav" :class="{ 'is-kronos': isKronosMode }">

    <!-- OP-HANDY-15: Die festen Tabs kommen aus derselben Liste wie das
         „Mehr“-Blatt. Gäste erreichen „Ressourcen“ nicht (der Server weist sie
         ab); der Tab führte sie nur in eine stille Rückleitung. Er entfällt
         deshalb für sie, statt ins Leere zu zeigen. -->
    <a
      v-for="tab in hauptTabs"
      :key="tab.href"
      class="dk-bn-tab"
      :href="tab.href"
      :class="{ active: tab.seiten.includes(page) }"
      @click="closeMore"
    >
      <div v-if="tab.avatar" class="dk-bn-avatar" :style="avatarStil(user?.fullname)">{{ initials }}</div>
      <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path :d="ICON_PFADE[tab.icon]" />
      </svg>
      <span>{{ tab.label }}</span>
    </a>

    <!-- OP-HANDY-15: Gästen fehlen die mittleren Tabs; das „Mehr“-Blatt war
         für sie leer (nur die Überschrift „Navigation“, 74 px). Der Knopf
         erscheint jetzt nur noch, wenn es wirklich etwas zu zeigen gibt —
         das schließt den Theme-Umschalter (DES-R22) ein. Da das Blatt immer
         den Theme-Umschalter enthält, ist es nie leer (R-P2-3-code K1). -->
    <button class="dk-bn-tab" :class="{ active: showMore }" @click.stop="toggleMore">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>
      </svg>
      <span>Mehr</span>
    </button>

  </nav>

  <!-- Slide-up Sheet -->
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="showMore" class="dk-bn-sheet-overlay" @click.self="closeMore">
        <div
          ref="sheetFenster"
          class="dk-bn-sheet"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          tabindex="-1"
          @keydown="tastenFaenger"
        >
          <div class="dk-bn-sheet-handle"></div>
          <div class="dk-bn-sheet-title">Navigation</div>

          <!-- DES-R22: Der Theme-Umschalter lag nur in der Seitenleiste — am
               Handy ist sie ausgeblendet, der Knopf damit unerreichbar. Hier
               bekommt er einen erreichbaren Platz. -->
          <div class="dk-bn-sheet-theme">
            <span>{{ umschalterText(aktuellesTheme) }}</span>
            <button
              type="button"
              class="dk-bn-theme-schalter"
              :aria-pressed="String(aktuellesTheme === 'dark')"
              @click="$emit('toggle-theme')"
            >
              <svg v-if="aktuellesTheme === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
              <span>{{ aktuellesTheme === 'dark' ? 'Hell' : 'Dunkel' }}</span>
            </button>
          </div>

          <div class="dk-bn-sheet-grid">
            <a
              v-for="e in sheetEintraege"
              :key="e.id"
              class="dk-bn-sheet-item"
              :href="e.href"
              @click="closeMore"
            >
              <div class="dk-bn-sheet-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path :d="ICON_PFADE[e.icon] || ''"/></svg>
              </div>
              <span>{{ e.label }}</span>
            </a>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { currentPageName, currentHash, navigate } from '../router.js'
import { useSession } from '../composables/useSession.js'
import { initialen } from '../composables/anzeigename.mjs'
import { MENUE, ICON_PFADE, sichtbareEintraege } from '../menue.js'
import { fusstabs } from './fusstabs.mjs'
import { useDialogFokus } from '../composables/useDialogFokus.js'
import { useZurueckSchliesst } from '../composables/useZurueckSchliesst.js'
import { umschalterText } from '../composables/theme.mjs'

const { user, mitglied, isAdmin, istTester: istTesterRef, devmodeAn: devmodeAnRef, anzeigeName } = useSession()

const props = defineProps({
  isKronosMode: Boolean,
  // DES-R22: aktuelles Theme von App.vue (der Umschalter liegt in der Leiste).
  theme: { type: String, default: 'light' },
})
const emit = defineEmits(['toggle-theme'])
const aktuellesTheme = computed(() => props.theme)

const page = currentPageName
const showMore = ref(false)

const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')
const istTester = computed(() => Boolean(istTesterRef?.value && devmodeAnRef?.value))

// OP-HANDY-15: Gäste sehen „Ressourcen“ nicht — der Server verweigert es
// ohnehin. Die festen Tabs kommen aus derselben Regel wie das Blatt.
const hauptTabs = computed(() => fusstabs({ istGast: isGast.value }))

// Menüeinträge, die schon als fester Tab vorhanden sind, erscheinen nicht
// noch einmal im „Mehr“-Blatt.
const tabZiele = computed(() => new Set(hauptTabs.value.map(t => t.href)))

// OP-HANDY-15/DES-R22: Das Blatt enthält immer den Theme-Umschalter und ist
// damit nie leer — der Knopf bleibt dauerhaft sichtbar. Für Gäste, für die
// keine Menüeinträge übrig bleiben, ist der Theme-Umschalter der einzige
// Inhalt (akzeptiert, R-P2-3-code K1).
const sheetEintraege = computed(() =>
  MENUE
    .flatMap(gruppe => sichtbareEintraege(gruppe, {
      istAdmin: isAdmin.value,
      istTester: istTester.value,
      istGast: isGast.value,
    }))
    .filter(e => !tabZiele.value.has(e.href)),
)

/* OP-HANDY-25: Initialen aus dem gepflegten Namen (Mitglied), nicht aus dem
   Kontonamen — sonst stand dort im Testbestand ein „M" für „mitglied". */
const initials = computed(() => initialen(mitglied.value, anzeigeName.value || user.value?.fullname))
/* DES-08: Initialen tragen Schrift UND Flaeche aus Tokens — vorher
   --primary-ink auf Gold (2,68:1) bzw. im Dunkelmodus 1,41:1. */
const AVATAR_PAARE = [
  { bg: 'var(--dk-avatar-1-bg)', ink: 'var(--dk-avatar-1-ink)' },
  { bg: 'var(--dk-avatar-2-bg)', ink: 'var(--dk-avatar-2-ink)' },
  { bg: 'var(--dk-avatar-3-bg)', ink: 'var(--dk-avatar-3-ink)' },
  { bg: 'var(--dk-avatar-4-bg)', ink: 'var(--dk-avatar-4-ink)' },
  { bg: 'var(--dk-avatar-5-bg)', ink: 'var(--dk-avatar-5-ink)' },
  { bg: 'var(--dk-avatar-6-bg)', ink: 'var(--dk-avatar-6-ink)' },
]
function avatarStil(name) {
  const n = String(name || 'U').trim()
  const summe = (n.charCodeAt(0) || 85) + (n.length > 1 ? n.charCodeAt(n.length - 1) : 0)
  const paar = AVATAR_PAARE[summe % AVATAR_PAARE.length]
  return { background: paar.bg, color: paar.ink }
}

function toggleMore() { showMore.value = !showMore.value }
function closeMore() { showMore.value = false }

// DES-R6: Das „Mehr“-Blatt ist ein modales Fenster — Fokus hinein, Tab bleibt
// darin, Esc schliesst (vorher blieb der Fokus auf der Leiste dahinter).
// OP-HANDY-7: Zusätzlich schließt die Zurück-Taste/-Geste das Blatt; vorher
// blieb es offen und die Route wechselte dahinter.
const sheetFenster = ref(null)
const { tastenFaenger } = useDialogFokus(showMore, sheetFenster, closeMore)
useZurueckSchliesst(showMore, closeMore)
</script>

<style scoped>
/* Bottom Nav — nur auf Touch/Mobile */
.dk-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: calc(64px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--dk-surface);
  border-top: 1px solid var(--dk-border);
  z-index: 200;
  flex-direction: row;
  align-items: stretch;
}
@media (hover: none) and (pointer: coarse) and (max-width: 720px) {
  .dk-bottom-nav { display: flex; }
}
/* OP-HANDY-10: Im Querformat am Handy (844x390) waren Seitenleiste UND untere
   Leiste gleichzeitig sichtbar — Kontobereich und „Hilfe & Infos“ der
   Seitenleiste wurden von der unteren Leiste verdeckt. Eine Regel für beide:
   In flachen Touch-Querformaten nur die untere Leiste. */
@media (hover: none) and (pointer: coarse) and (orientation: landscape) and (max-height: 480px) {
  .dk-bottom-nav { display: flex; }
}

/* Tabs */
.dk-bn-tab {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px;
  text-decoration: none;
  color: var(--dk-text-muted);
  font-size: 10px; font-weight: 500;
  background: none; border: none; cursor: pointer;
  padding: 0;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.dk-bn-tab.active { color: var(--primary); }
.dk-bn-tab svg { flex-shrink: 0; }

/* Avatar mini */
.dk-bn-avatar {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: var(--primary-ink); flex-shrink: 0;
}

/* Slide-up sheet */
.dk-bn-sheet-overlay {
  position: fixed; inset: 0;
  background: color-mix(in oklch, var(--dk-navy-900) 45%, transparent);
  z-index: 300;
  display: flex; flex-direction: column; justify-content: flex-end;
}
.dk-bn-sheet {
  background: var(--dk-surface);
  border-radius: 16px 16px 0 0;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
  max-height: 80vh;
  overflow-y: auto;
}
.dk-bn-sheet-handle {
  width: 36px; height: 4px; border-radius: 2px;
  background: var(--dk-border);
  margin: 12px auto 8px;
}
.dk-bn-sheet-title {
  font-size: 12px; font-weight: 600;
  color: var(--dk-text-muted);
  text-transform: uppercase; letter-spacing: 0.5px;
  padding: 4px 20px 12px;
}
/* DES-R22: Theme-Umschalter im „Mehr“-Blatt — am Handy war er sonst
   unerreichbar (die Seitenleiste ist dort ausgeblendet). */
.dk-bn-sheet-theme {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 20px 12px;
  color: var(--dk-text-muted);
  font-size: 12px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.dk-bn-theme-schalter {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px;
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  background: var(--dk-surface-2);
  color: var(--dk-text);
  font-size: 13px; font-weight: 500;
  cursor: pointer;
}
.dk-bn-theme-schalter:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 1px;
}
.dk-bn-sheet-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 0 12px;
}
.dk-bn-sheet-item {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 14px 8px;
  border-radius: 12px;
  text-decoration: none;
  color: var(--dk-text);
  font-size: 12px; font-weight: 500;
  background: none;
  transition: background 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.dk-bn-sheet-item:active { background: var(--dk-surface-2); }
.dk-bn-sheet-icon {
  width: 44px; height: 44px; border-radius: 12px;
  background: var(--dk-surface-2);
  display: flex; align-items: center; justify-content: center;
  color: var(--dk-text);
}
.dk-bn-sheet-footer {
  padding: 12px 16px 0;
  border-top: 1px solid var(--dk-border);
  margin-top: 8px;
}
/* Sheet transition */
.sheet-enter-active, .sheet-leave-active { transition: opacity 0.2s; }
.sheet-enter-active .dk-bn-sheet, .sheet-leave-active .dk-bn-sheet {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .dk-bn-sheet, .sheet-leave-to .dk-bn-sheet {
  transform: translateY(100%);
}
</style>
