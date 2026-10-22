<template>
  <!-- Sidebar -->
  <aside class="dk-sidebar" :class="{ 'is-collapsed': collapsed }">

    <!-- Top: Brand + Collapse -->
    <div class="dk-sb-top">
      <a href="#/" class="dk-sb-brand" @click="$emit('close-mobile')">
        <div class="dk-sb-logo">
          <img v-if="logoUrl" :src="logoUrl" :alt="PRODUKTNAME" />
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <div v-if="!collapsed" class="dk-sb-brand-text">
          <span class="dk-sb-brand-name">{{ PRODUKTNAME }}</span>
          <span class="dk-sb-brand-sub">{{ churchName }}</span>
        </div>
      </a>
      <button
        class="dk-sb-collapse"
        @click="$emit('toggle-collapse')"
        :title="collapsed ? 'Ausklappen' : 'Einklappen'"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
      </button>
    </div>

    <!-- UXD-R19: Der frühere Such-Knopf war reines Markup ohne Funktion und
         wurde deshalb entfernt (Seitenleiste UND Kopfzeile) — statt einen
         toten Knopf zu zeigen. -->

    <!-- Navigation — aus der zentralen Menüdefinition (menue.js). -->
    <nav class="dk-sb-nav">
      <template v-for="(gruppe, gi) in sichtbaresMenue" :key="gruppe.gruppe">
        <div class="dk-sb-section" :style="gi ? 'margin-top:8px' : ''">{{ gruppe.gruppe }}</div>
        <NavItem
          v-for="e in gruppe.eintraege"
          :key="e.id"
          :href="e.href"
          :icon="e.icon"
          :label="e.label"
          :active="istAktiv(e)"
          :collapsed="collapsed"
          :badge="badgeFuer(e)"
        />
      </template>
    </nav>

    <!-- Footer -->
    <div class="dk-sb-foot">


      <!-- User -->
      <a href="#/profile" class="dk-sb-user">
        <div class="dk-avatar dk-avatar-sm" :style="avatarStil(anzeigeName || user.fullname)">{{ initials }}</div>
        <div v-if="!collapsed" class="dk-sb-user-text">
          <!-- OP-HANDY-25: Anzeige = gepflegter Name (Mitglied), nicht der Kontoname. -->
          <div class="dk-sb-user-name">{{ mitgliedName || user.fullname || 'Nutzer' }}</div>
          <div class="dk-sb-user-role">{{ mitglied ? `${mitglied.vorname || ''} ${mitglied.nachname || ''}`.trim() || 'Kein Mitglied' : 'Kein Mitglied' }}</div>
        </div>
        <button
          v-if="!collapsed"
          class="dk-sb-theme-btn"
          @click.prevent="$emit('toggle-theme')"
          :title="theme === 'dark' ? 'Hell-Modus' : 'Dunkel-Modus'"
        >
          <svg v-if="theme === 'dark'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
      </a>

      <!-- BF1-L: Abmelden — im Nutzerbereich, unten in der Sidebar. -->
      <button
        type="button"
        class="dk-sb-logout"
        :class="{ 'is-collapsed': collapsed }"
        :title="collapsed ? 'Abmelden' : ''"
        aria-label="Abmelden"
        @click="abmeldenMitMeldung"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/>
          <line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
        <span v-if="!collapsed">Abmelden</span>
      </button>
    </div>
  </aside>


</template>

<script setup>
import { computed, h, reactive, onMounted, onUnmounted } from 'vue'
import { useSession } from '../composables/useSession.js'
import { initialen } from '../composables/anzeigename.mjs'
import { useAbmelden } from '../composables/useAbmelden.js'
import { showToast } from '../composables/useToast.js'
import { currentPageName, currentHash } from '../router.js'
import { MENUE, ICON_PFADE, sichtbareEintraege } from '../menue.js'
import { PRODUKTNAME } from './ui/begriffe.mjs'
import { navigationZaehler } from '../composables/useVerwaltung.js'

const props = defineProps({
  collapsed: Boolean,
  theme: String,
})
const emit = defineEmits(['toggle-collapse', 'toggle-theme', 'close-mobile'])

const { user, mitglied, isAdmin, istTester: istTesterRef, devmodeAn: devmodeAnRef, anzeigeName } = useSession()
const { abmelden } = useAbmelden()

/** W3: Bei einem Fehler bleibt der Nutzer hier und bekommt eine Meldung —
 *  es wird nicht auf /login gesprungen, waehrend die Serversitzung lebt. */
async function abmeldenMitMeldung() {
  const ergebnis = await abmelden()
  if (ergebnis && ergebnis.ok === false) {
    showToast(ergebnis.fehler || 'Abmelden fehlgeschlagen.', 'error')
  }
}
// DM1: Dev-Befunde nur, wenn das Backend den Dev-Modus eingeschaltet hat UND
// der Benutzer Admin oder Tester ist. Der Server prueft dieselbe Rolle.
const istTester = computed(() => Boolean(istTesterRef?.value && devmodeAnRef?.value))
const page = currentPageName

const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')

/* UXD-R18: Die Kennzahl am Menüpunkt „Mitglieder“ (offene Anmeldeanfragen).
   Vorher stand hier eine feste 0 — die Seitenleiste zeigte damit
   „Registrierung 0“, obwohl offene Anmeldungen vorlagen. Die Zahl kommt vom
   Server (`get_navigation_zaehler`); ohne Rolle fehlt der Schlüssel, dann
   wird nichts eingeblendet (nie eine erfundene Null). Ein Fehler bleibt
   still: eine Kennzahl darf die Navigation nicht stören. */
const zaehler = reactive({ anfragen: 0 })
let zaehlerTimer = null

async function ladeZaehler() {
  try {
    const antwort = await navigationZaehler()
    zaehler.anfragen = Number(antwort?.anfragen || 0)
  } catch {
    zaehler.anfragen = 0
  }
}

onMounted(() => {
  ladeZaehler()
  zaehlerTimer = setInterval(ladeZaehler, 60_000)
})
onUnmounted(() => { if (zaehlerTimer) clearInterval(zaehlerTimer) })

const sichtbaresMenue = computed(() =>
  MENUE
    .map(gruppe => ({
      gruppe: gruppe.gruppe,
      eintraege: sichtbareEintraege(gruppe, {
        istAdmin: isAdmin.value,
        istTester: istTester.value,
        istGast: isGast.value,
      }),
    }))
    .filter(gruppe => gruppe.eintraege.length > 0),
)

function istAktiv(eintrag) {
  if (eintrag.href === '#/gruppen') return currentHash.value.startsWith('#/gruppen') || page.value === 'GruppeDetail'
  return eintrag.seiten.includes(page.value)
}

function badgeFuer(eintrag) {
  if (eintrag.badge === 'anfragen' && zaehler.anfragen > 0) return zaehler.anfragen
  return null
}

const churchName = window.__DIakonosBOOT?.church_name || 'Meine Gemeinde'
const logoUrl = window.__DIakonosBOOT?.logo_url || null

// OP-HANDY-25: Initialen und Name aus dem gepflegten Mitgliedsnamen.
const mitgliedName = computed(() => {
  const m = mitglied.value
  if (!m) return ''
  return [m.vorname, m.nachname].filter(Boolean).join(' ').trim()
})
const initials = computed(() => initialen(mitglied.value, anzeigeName.value || user.value.fullname))

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



// --- NavItem as inline component ---
const NavItem = {
  props: ['href', 'icon', 'label', 'active', 'collapsed', 'badge'],
  setup(props) {
    return () => h('a', {
      href: props.href,
      class: ['dk-nav-item', props.active ? 'is-active' : ''],
      title: props.collapsed ? props.label : '',
    }, [
      h('svg', {
        width: 16, height: 16,
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        style: 'flex-shrink:0',
      }, [h('path', { d: ICON_PFADE[props.icon] || '' })]),
      !props.collapsed && h('span', props.label),
      !props.collapsed && props.badge && h('span', { class: 'dk-nav-badge' }, props.badge),
    ])
  }
}
</script>
