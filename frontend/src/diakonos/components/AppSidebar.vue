<template>
  <!-- Sidebar -->
  <aside class="dk-sidebar" :class="{ 'is-collapsed': collapsed }">

    <!-- Top: Brand + Collapse -->
    <div class="dk-sb-top">
      <a href="#/" class="dk-sb-brand" @click="$emit('close-mobile')">
        <!-- ON-4 (H4, Entwurf 10): Logo der Gemeinde, sonst ihr Monogramm.
             Die Adresse kommt FERTIG vom Server (Betriebspräfix + `?v=`),
             der Buchstabe aus derselben Regel wie im Assistenten. Vorher
             stand hier immer dasselbe Personen-Symbol — die Gemeinde war
             nicht zu erkennen. Fällt beides aus (kein Status geladen), bleibt
             das bisherige Symbol stehen. -->
        <LogoMarke
          :quelle="logoQuelleMarke"
          :buchstabe="monogrammMarke"
          size="md"
          class="dk-sb-logo"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </LogoMarke>
        <div v-if="!collapsed" class="dk-sb-brand-text">
          <span class="dk-sb-brand-name">{{ PRODUKTNAME }}</span>
          <span class="dk-sb-brand-sub">{{ churchName }}</span>
        </div>
      </a>
      <!-- UX1g: Ein-/Ausklappen der Leiste ist ein Knopf des Systems
           (ghost, Seitenleisten-Töne über .dk-sb-collapse). -->
      <DkButton
        variant="ghost"
        class="dk-sb-collapse"
        :aria-label="collapsed ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'"
        :title="collapsed ? 'Ausklappen' : 'Einklappen'"
        @click="$emit('toggle-collapse')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
      </DkButton>
    </div>

    <!-- UXD-R19: Der frühere Such-Knopf war reines Markup ohne Funktion und
         wurde deshalb entfernt (Seitenleiste UND Kopfzeile) — statt einen
         toten Knopf zu zeigen. -->

    <!-- Navigation — aus der zentralen Menüdefinition (menue.js).
         UX3a (Entwurf A1): „Einstellungen“ steht NICHT in der Gruppenliste,
         sondern unten im Fußbereich; die Gruppen sind Gemeinde · Planen ·
         Inhalte (eine leere Gruppe „“ = Eintrag ohne Überschrift). -->
    <nav class="dk-sb-nav">
      <template v-for="(gruppe, gi) in sichtbaresMenue" :key="'g' + gi">
        <div v-if="gruppe.gruppe" class="dk-sb-section" :style="gi ? 'margin-top:var(--sp-2)' : ''">{{ gruppe.gruppe }}</div>
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

    <!-- Fußbereich (Entwurf A1): Einstellungen · Profil · Abmelden.
         UX3a: Entwicklermodus und Dev-Befunde liegen im Profilmenü (siehe
         unten) — sie sind Werkzeuge, keine Navigation. -->
    <div class="dk-sb-foot">

      <NavItem
        v-for="e in sichtbareFussEintraege"
        :key="e.id"
        :href="e.href"
        :icon="e.icon"
        :label="e.label"
        :active="istAktiv(e)"
        :collapsed="collapsed"
        :badge="null"
      />

      <!-- UX3a: Profilmenü (Entwurf A1 „Profil / Abmelden“). Der Eintrag
           öffnet ein kleines Menü: Profil · Entwicklermodus · Dev-Befunde.
           Die Werkzeuge erscheinen nur, wenn das Backend den Dev-Modus
           eingeschaltet hat UND der Nutzer Admin oder Tester ist (wie vorher
           der Menüpunkt „Dev-Befunde“) — der Server prüft dieselbe Rolle. -->
      <div class="dk-sb-profil">
        <button
          type="button"
          class="dk-sb-user"
          :aria-expanded="profilOffen ? 'true' : 'false'"
          aria-haspopup="menu"
          @click="profilOffen = !profilOffen"
        >
          <div class="dk-avatar dk-avatar-sm" :style="avatarStil(anzeigeName || user.fullname)">{{ initials }}</div>
          <div v-if="!collapsed" class="dk-sb-user-text">
            <!-- OP-HANDY-25: Anzeige = gepflegter Name (Mitglied), nicht der Kontoname. -->
            <div class="dk-sb-user-name">{{ mitgliedName || user.fullname || 'Nutzer' }}</div>
            <div class="dk-sb-user-role">{{ mitglied ? `${mitglied.vorname || ''} ${mitglied.nachname || ''}`.trim() || 'Kein Mitglied' : 'Kein Mitglied' }}</div>
          </div>
          <span v-if="!collapsed" class="dk-sb-chevron" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          </span>
        </button>

        <div v-if="profilOffen && !collapsed" class="dk-sb-profil-menu" role="menu">
          <a href="#/profile" role="menuitem" class="dk-sb-profil-punkt is-profilmenue" @click="profilOffen = false">Profil</a>
          <a
            v-if="darfDevWerkzeuge"
            href="#/einstellungen/dev-modus"
            role="menuitem"
            class="dk-sb-profil-punkt is-profilmenue"
            @click="profilOffen = false"
          >Entwicklermodus</a>
          <a
            v-if="darfDevWerkzeuge"
            href="#/dev-befunde"
            role="menuitem"
            class="dk-sb-profil-punkt is-profilmenue"
            @click="profilOffen = false"
          >Dev-Befunde</a>
            <!-- UX1g: Der Umschalter ist ein Menüpunkt der Leiste; seine
                 Klickfläche (--control-h, bei grobem Zeiger 44 px) erbt er
                 vom Knopf-System. Die Seitenleisten-Töne setzt
                 .dk-sb-theme-punkt (index.css). -->
          <DkButton
            variant="ghost"
            role="menuitem"
            class="dk-sb-profil-punkt is-profilmenue dk-sb-theme-punkt"
            @click="$emit('toggle-theme')"
          >{{ theme === 'dark' ? 'Hell-Modus' : 'Dunkel-Modus' }}</DkButton>
        </div>
      </div>

      <!-- BF1-L: Abmelden — im Nutzerbereich, unten in der Sidebar. -->
      <DkButton
        variant="ghost"
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
      </DkButton>
    </div>
  </aside>


</template>

<script setup>
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useSession } from '../composables/useSession.js'
import { initialen } from '../composables/anzeigename.mjs'
// ON-4/H4: Logo oder Monogramm der Gemeinde in der Seitenleiste.
import LogoMarke from './einrichtung/LogoMarke.vue'
import { monogramm } from '../composables/einrichtung.mjs'
import { useAbmelden } from '../composables/useAbmelden.js'
import { showToast } from '../composables/useToast.js'
import { currentPageName, currentHash } from '../router.js'
import { MENUE, ICON_PFADE, sichtbareEintraege, FUSS_EINTRAEGE } from '../menue.js'
import { PRODUKTNAME } from './ui/begriffe.mjs'
import DkButton from './ui/DkButton.vue'
import { anfragenZaehler, anfragenZaehlerBeobachten } from '../composables/useVerwaltung.js'

const props = defineProps({
  collapsed: Boolean,
  theme: String,
})
const emit = defineEmits(['toggle-collapse', 'toggle-theme', 'close-mobile'])

const { user, mitglied, isAdmin, istTester: istTesterRef, devmodeAn: devmodeAnRef, anzeigeName, rollen: rollenRef } = useSession()
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
   still: eine Kennzahl darf die Navigation nicht stören.
   UX-A2a: Die Abfrage und der Stand liegen in `useVerwaltung.js`, weil die
   Mitglieder-Bereichsliste dieselbe Zahl an „Anfragen“ zeigt — eine Abfrage,
   ein Stand, keine zwei Anzeigen mit verschiedenen Zahlen.
   UX-A2a2: Auch der Takt ist gemeinsam (`anfragenZaehlerBeobachten`): EIN
   Intervall für Seitenleiste und Bereich, nicht eines je Bauteil. Gefragt
   wird nur mit Mitgliederadministrator-Recht — sonst liefe die Leiste bei
   jedem Nutzer in eine Absage. */
const zaehler = anfragenZaehler
let zaehlerAbmelden = null

onMounted(() => {
  zaehlerAbmelden = anfragenZaehlerBeobachten()
})
onUnmounted(() => {
  if (zaehlerAbmelden) zaehlerAbmelden()
  zaehlerAbmelden = null
})

const sichtbaresMenue = computed(() =>
  MENUE
    .map(gruppe => ({
      gruppe: gruppe.gruppe,
      eintraege: sichtbareEintraege(gruppe, {
        istAdmin: isAdmin.value,
        istTester: istTester.value,
        istGast: isGast.value,
        // WEB-3: Rollenliste der Sitzung für Einträge mit eigener Rollenliste.
        rollen: rollenRef?.value || [],
      }),
    }))
    .filter(gruppe => gruppe.eintraege.length > 0),
)

/** Fußbereich: „Einstellungen“ (nur Administration). Dieselbe Rollenregel. */
const sichtbareFussEintraege = computed(() =>
  FUSS_EINTRAEGE.filter(e => e.rolle !== 'admin' || isAdmin.value === true),
)

/** Profilmenü offen? (Entwurf A1: Profil, Entwicklermodus, Dev-Befunde) */
const profilOffen = ref(false)

/** Werkzeuge im Profilmenü nur bei eingeschaltetem Dev-Modus und Admin/Tester. */
const darfDevWerkzeuge = computed(() => Boolean(
  (isAdmin.value || istTesterRef?.value) && devmodeAnRef?.value,
))

function istAktiv(eintrag) {
  if (eintrag.href === '#/gruppen') return currentHash.value.startsWith('#/gruppen') || page.value === 'GruppeDetail'
  return eintrag.seiten.includes(page.value)
}

function badgeFuer(eintrag) {
  if (eintrag.badge === 'anfragen' && zaehler.value > 0) return zaehler.value
  return null
}

const churchName = window.__DIakonosBOOT?.church_name || 'Meine Gemeinde'

/**
 * ON-4 (H4): Marke der Gemeinde. Das Boot-Objekt trägt `logo_url` und
 * `church_name` schon immer; das Monogramm kommt aus derselben Funktion wie im
 * Assistenten (`monogramm`, Kurzname vor Gemeindename — Entwurf 04).
 *
 * WARUM NICHT DER STATUS-ABRUF: die Seitenleiste sehen ALLE Rollen, der
 * Status ist Administratoren vorbehalten (Server: 403). Deshalb werden nur die
 * Boot-Angaben benutzt — kein zusätzlicher Aufruf, kein 403 im Netz-Log.
 */
/**
 * Das Boot-Objekt ist beim Aufbau der App gesetzt.
 *
 * ON-5 (E2-5): Nach einem Logo-Upload/Entfernen schreibt
 * `useEinrichtungsAssistent.merkeMarke` die neue Adresse ins Boot-Objekt und
 * meldet `dk-marke-geaendert`. Das Boot-Objekt ist plain JS — ein `computed`
 * darauf allein zeichnet NICHT neu (im Prüflauf blieb darum das alte Logo
 * stehen). Deshalb hält dieses Modul eine eigene `ref`, die das Ereignis
 * fortschreibt: es bleibt EIN Zustand (der Serverstand), nur mit einem
 * Auslöser für die Neuzeichnung.
 */
const markeStand = ref(String(window.__DIakonosBOOT?.logo_url || ''))
function markeNachziehen() {
  markeStand.value = String(window.__DIakonosBOOT?.logo_url || '')
}
onMounted(() => window.addEventListener('dk-marke-geaendert', markeNachziehen))
onUnmounted(() => window.removeEventListener('dk-marke-geaendert', markeNachziehen))
const logoQuelleMarke = computed(() => markeStand.value)
const monogrammMarke = computed(() => {
  const text = String(churchName || '').trim()
  if (!text) return ''
  const buchstabe = monogramm({ gemeindename: text }, text)
  return buchstabe === '?' ? '' : buchstabe
})

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
