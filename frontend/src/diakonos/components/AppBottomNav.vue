<template>
  <!-- UX3e (Entwurf A8): Die untere Leiste zeigt nur die häufigen Ziele.
       CHAT-3a (Chat-Konzept 10.1/10.2, Manuel 17.11.): fünf Plätze
       **Start · Nachrichten · Gruppen · Kalender · Mehr**. Der fünfte Platz
       „Mehr“ öffnet die bestehende Menü-Schublade (AppMenueSchublade.vue) —
       kein eigener Seitenbaum, kein Blatt. Die Regel „kein Mehr in der
       Leiste“ vom 03.11. ist damit abgelöst (Konzept 10.2).

       Gäste sehen nur, was der Server ihnen erlaubt (OP-HANDY-15/UX3a2):
       Start und Kalender — dieselbe Regel wie zuvor (fusstabs.mjs). -->
  <nav class="dk-bottom-nav" aria-label="Hauptnavigation">
    <template v-for="tab in hauptTabs" :key="tab.href || tab.label">
      <!-- „Mehr“: ein KNOPF, der die Schublade öffnet. WAS ein Platz ist,
           entscheidet `tabArt()` in `handyMenue.mjs` — hier steht kein zweites
           `if` über die Kennung des Platzes. -->
      <button
        v-if="tabArt(tab) === 'schublade'"
        type="button"
        class="dk-bn-tab"
        :class="{ active: istAktiv(tab) }"
        :aria-expanded="menueOffen ? 'true' : 'false'"
        aria-haspopup="dialog"
        :aria-label="MEHR_TEXT"
        @click="$emit('open-menu')"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path :d="ICON_PFADE[tab.icon]" />
        </svg>
        <span>{{ tab.label }}</span>
      </button>
      <a
        v-else
        class="dk-bn-tab"
        :href="tab.href"
        :class="{ active: istAktiv(tab) }"
        :aria-current="istAktiv(tab) ? 'page' : undefined"
        :aria-label="zaehlerFuer(tab) ? `${tab.label} — ${zaehlerFuer(tab)} ungelesene Nachrichten` : undefined"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path :d="ICON_PFADE[tab.icon]" />
        </svg>
        <!-- CHAT-3a: Ungelesen-Zähler am Platz „Nachrichten“ — die EINE Zahl
             aus `meine_gespraeche` (dieselbe in Leiste, Schublade, Seitenleiste).
             Review R1: KEIN `role="status"` — ein Status hätte jede Änderung
             angesagt, auch mitten im Tippen. Die Zahl ist reine Anzeige
             (`aria-hidden`); den Satz trägt der Platz selbst als `aria-label`. -->
        <span
          v-if="zaehlerFuer(tab)"
          class="dk-bn-zaehler"
          aria-hidden="true"
        >{{ zaehlerFuer(tab) }}</span>
        <span>{{ tab.label }}</span>
      </a>
    </template>
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
 *
 * CHAT-3a (Chat-Konzept 10.1/10.2): fünf Plätze, davon einer „Mehr“.
 * `menueOffen` und `@open-menu` verbinden ihn mit der BESTEHENDEN Schublade
 * (App.vue hält den einen Zustand) — die Leiste baut kein zweites Menü.
 * `ungelesen` ist die eine Zahl der Nachrichten; der Zähler steht damit am
 * Tab „Nachrichten“.
 *
 * CHAT-R2a-2 (Punkt b): Die Modulliste der Sitzung
 * (`window.__DIakonosBOOT.module_sichtbar`, vom Server gerechnet) und
 * `isAdmin` werden durchgereicht — `fusstabs()` blendet „Nachrichten“ ohne
 * Chat-Leserecht aus, mit GENAU der Regel des Router-Guards
 * (`modulChatErlaubt`: Administrator immer, sonst nur mit `chat` in der
 * Liste, ohne Liste gar nicht). Ohne diese beiden Werte hätte die Leiste
 * einen Tab gezeigt, den der Wächter anschließend auf den Start zurückwarf.
 */
import { computed } from 'vue'
import { useSession } from '../composables/useSession.js'
import { ICON_PFADE } from '../menue.js'
import { fusstabs, tabZaehler } from './fusstabs.mjs'
import { istTabAktiv, tabArt, MEHR_TEXT } from './handyMenue.mjs'

const props = defineProps({
  seite: { type: String, default: '' },
  /** Zustand der Menü-Schublade — markiert den Platz „Mehr“ (CHAT-3a). */
  menueOffen: { type: Boolean, default: false },
  /** Ungelesene Nachrichten (`ungelesenSumme` der Gespräche), `null` = unbekannt. */
  ungelesen: { type: Number, default: null },
})
defineEmits(['open-menu'])
const { mitglied, isAdmin } = useSession()

const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')
/** Modulliste der Sitzung — `null`, wenn der Server sie nicht liefert. */
const module = computed(() => {
  const liste = typeof window === 'undefined' ? null : window.__DIakonosBOOT?.module_sichtbar
  return Array.isArray(liste) ? liste : null
})
const hauptTabs = computed(() => fusstabs({
  istGast: isGast.value,
  istAdmin: isAdmin.value === true,
  module: module.value,
}))

/**
 * Markiert ist GENAU EIN Platz (Review R1). Die Regel steht in `istTabAktiv`
 * (eine Stelle): bei offener Schublade ist ausschließlich „Mehr“ markiert, der
 * Platz der aktuellen Seite liegt dahinter und ist es NICHT.
 */
const istAktiv = (tab) => istTabAktiv(tab, { seite: props.seite, schubladeOffen: props.menueOffen })
/** Der Zähler eines Platzes ('' = keiner) — dieselbe Quelle wie die Leiste. */
const zaehlerFuer = (tab) => tabZaehler(tab, { nachrichten: props.ungelesen })
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
  /* CHAT-3a: Der Platz „Mehr“ ist ein <button> — ohne diese Zeile erbte er die
     Browser-Schrift und stünde sichtbar anders da als die Links daneben. */
  font-family: inherit;
}
/* Der aktive Reiter nahm --primary — im Dunkelmodus ist das WEISS und damit von
   den inaktiven nicht zu unterscheiden (dieselbe Falle wie DEV-4 bei DkTabs).
   --accent ist in beiden Themes die Markenfarbe: hell 4,84:1, dunkel 9,48:1
   auf der Leistenfläche. Zusaetzlich ein Unterstrich, damit der Zustand nicht
   allein an der Farbe haengt (WCAG 1.4.1).
   UX-K1: `--accent-leiste` — die Leiste ist in BEIDEN Themes weiß (bzw. im
   Dunkelmodus fast schwarz), `--accent` ist hell die abgedunkelte
   Schriftstufe (4,9:1 auf Weiß) und dunkel gold-300 (8,9:1 auf der Leiste). */
.dk-bn-tab.active {
  color: var(--accent-leiste);
  font-weight: var(--fw-fett);
}
/* CHAT-3a: der Unterstrich sitzt an der BESCHRIFTUNG (letztes <span>), nicht an
   jedem — der Zähler ist auch ein <span> und bekäme sonst einen Strich. */
.dk-bn-tab.active > span:last-child { position: relative; }
.dk-bn-tab.active > span:last-child::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: -3px;
  height: 2px; border-radius: 1px;
  background: var(--accent-leiste);
}
.dk-bn-tab:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
}
.dk-bn-tab svg { flex-shrink: 0; }

/* CHAT-3a: Ungelesen-Zähler am Platz „Nachrichten“. Dieselbe Form und Farbe
   wie der Zähler der Seitenleiste (--marke-flaeche/--marke-ink) — er steht IN
   der Spalte über der Beschriftung, nicht schwebend darüber, damit er nichts
   verdeckt. */
.dk-bn-zaehler {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--marke-flaeche);
  color: var(--marke-ink);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  line-height: 1;
}
</style>
