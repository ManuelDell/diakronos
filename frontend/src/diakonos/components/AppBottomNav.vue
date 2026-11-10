<template>
  <!-- UX3e (Entwurf A8): Die untere Leiste zeigt nur noch die fünf häufigen
       Ziele — Übersicht · Kalender · Dienste · Beiträge · Wiki. Der frühere
       „Mehr“-Knopf und sein Blatt sind entfallen (Entscheidung Manuel
       2026-11-03): alles Weitere steht in der Menü-Schublade, die das
       Menü-Symbol oben links öffnet (AppMenueSchublade.vue).

       Gäste sehen nur, was der Server ihnen erlaubt (OP-HANDY-15/UX3a2):
       Übersicht und Kalender — dieselbe Regel wie zuvor (fusstabs.mjs). -->
  <nav class="dk-bottom-nav" aria-label="Hauptnavigation">
    <a
      v-for="tab in hauptTabs"
      :key="tab.href"
      class="dk-bn-tab"
      :href="tab.href"
      :class="{ active: istAktiv(tab) }"
      :aria-current="istAktiv(tab) ? 'page' : undefined"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path :d="ICON_PFADE[tab.icon]" />
      </svg>
      <span>{{ tab.label }}</span>
    </a>
  </nav>
</template>

<script setup>
/**
 * UX3e — untere Leiste am Handy (Entwurf A8).
 *
 * Die Tabs stehen NUR in `fusstabs.mjs` (eine Quelle).
 *
 * `seite` kommt von App.vue: die Markierung hängt an der aktuellen
 * Route. Vorher las die Komponente den Seitenzustand selbst — dadurch war die
 * Regel im Test nicht nachvollziehbar.
 */
import { computed } from 'vue'
import { useSession } from '../composables/useSession.js'
import { ICON_PFADE } from '../menue.js'
import { fusstabs } from './fusstabs.mjs'
import { istTabAktiv } from './handyMenue.mjs'

const props = defineProps({
  seite: { type: String, default: '' },
})
const { mitglied, isAdmin } = useSession()

const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')
const hauptTabs = computed(() => fusstabs({ istGast: isGast.value }))

const istAktiv = (tab) => istTabAktiv(tab, { seite: props.seite })
</script>

<style scoped>
/* Bottom Nav — nur auf Touch/Mobile */
.dk-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  /* DEV-B6b (Punkt 6): Höhe aus EINEM Token (tokens.css, --bottom-nav-h) —
     Kalender (FAB, Liste) rechnen mit demselben Wert. */
  height: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--dk-surface);
  border-top: 1px solid var(--dk-border);
  z-index: 200;
  flex-direction: row;
  align-items: stretch;
}
/* DEV-B6 (Manuel 09.11., Befund DMB-3a7d335074cc; Review-Nacharbeit 10.11.):
   Die untere Leiste ist die Handy-Navigation — sie erscheint NUR in der
   Handy-Lage der App: KLASSE `.dk-app--handy`, die `App.vue` aus
   `composables/handyLage.mjs` setzt (grober Zeiger UND schmal, bzw. grober
   Zeiger und flaches Querformat). Dieselbe Quelle wie Skript und Token
   `--layout-mobil`. „Auf einem Laptop darf nie die Handyleiste kommen“: ein
   Maus-/Trackpad-Fenster mit 702 px, 400 px oder 1280×450 behält die
   Seitenleiste (mit Menü-Knopf) statt der Leiste. Das ändert die FIX-6-Regel
   („Zeiger ist nie Layout-Kriterium“) bewusst — Begründung im Kartenkommentar
   DEV-B6. Der Wähler steht OHNE `:global`: die Hüllenklasse ist ein
   Vorfahre, der Scope-Anhang landet am letzten Selektor (`.dk-bottom-nav`),
   und der liegt im eigenen Markup. Mit `:global(...)` fiel die Regel im
   Bündel ganz heraus (im Wegwerf-Stack gemessen: Leiste blieb aus). */
.dk-app--handy .dk-bottom-nav { display: flex; }

/* Tabs */
.dk-bn-tab {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: var(--sp-1);
  text-decoration: none;
  /* Operator-Review DEP-2, Punkt 6: die Beschriftungen der unteren Leiste waren
     mit 10 px/500 zu duenn und zu hell (--dk-text-muted) — am Handy kaum lesbar.
     Jetzt kraeftiger (600) und in der Textfarbe des Themes. Die Groesse ist
     seit UX1b die kleinste Stufe (12 px statt 10): 5 Reiter muessen in 390 px
     passen („Ressourcen" ist der laengste) — bei 12 px passt die Leiste, der
     Hinweis auf die 10 px gilt nicht mehr. */
  color: var(--dk-text);
  font-size: var(--fs-12); font-weight: var(--fw-fett);
  background: none; border: none; cursor: pointer;
  padding: 0;
  /* UX3e (Entwurf A8): Trefferfläche ≥ 44 px (Prinzip K4) — die Zeile füllt
     die 64 px hohe Leiste, also deutlich mehr als das Mindestmaß.
     UX1c (T6): das Maß steht als Token, nicht als Literal in der Komponente
     (der Wächter UX1c/T6 lässt genau das nicht zu). */
  min-height: var(--control-h);
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
}
/* Der aktive Reiter nahm --primary — im Dunkelmodus ist das WEISS und damit von
   den inaktiven nicht zu unterscheiden (dieselbe Falle wie DEV-4 bei DkTabs).
   --accent ist in beiden Themes die Markenfarbe: hell 4,84:1, dunkel 9,48:1
   auf der Leistenfläche. Zusaetzlich ein Unterstrich, damit der Zustand nicht
   allein an der Farbe haengt (WCAG 1.4.1). */
.dk-bn-tab.active {
  color: var(--accent);
  font-weight: var(--fw-fett);
}
.dk-bn-tab.active span { position: relative; }
.dk-bn-tab.active span::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: -3px;
  height: 2px; border-radius: 1px;
  background: var(--accent);
}
.dk-bn-tab:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
}
.dk-bn-tab svg { flex-shrink: 0; }
</style>
