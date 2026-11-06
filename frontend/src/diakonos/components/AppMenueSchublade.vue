<template>
  <!-- UX3e (Entwurf A9): Menü-Schublade am Handy. Öffnet sich von links,
       gruppiert wie die Seitenleiste; Profil und Abmelden stehen unten.
       Sie liegt NUR in der Mobil-Lage im DOM (`v-if` in App.vue), damit
       Desktop-Nutzer keinen zweiten Navigationsweg im Tab-Ring haben. -->
  <Teleport to="body">
    <Transition name="dk-schublade">
      <div v-if="offen" class="dk-schublade-ueberlagerung" @click.self="$emit('schliessen')">
        <div
          ref="fenster"
          class="dk-schublade"
          role="dialog"
          aria-modal="true"
          :aria-label="SCHUBLADE_KOPF_TEXT"
          tabindex="-1"
          @keydown="tastenFaenger"
          @touchstart.passive="wischStart"
          @touchend.passive="wischEnde"
        >
          <!-- Kopf: Marke (S5 „Logo oben links → Start“) und Schließen -->
          <div class="dk-schublade-kopf">
            <a href="#/" class="dk-schublade-marke" @click="$emit('schliessen')">
              <LogoMarke :quelle="logoQuelle" :buchstabe="monogrammText" size="md">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </LogoMarke>
              <span class="dk-schublade-marke-text">
                <span class="dk-schublade-marke-name">{{ PRODUKTNAME }}</span>
                <span class="dk-schublade-marke-ort">{{ gemeindeName }}</span>
              </span>
            </a>
            <button
              type="button"
              class="dk-schublade-schliessen"
              :aria-label="SCHUBLADE_SCHLIESSEN_TEXT"
              :title="SCHUBLADE_SCHLIESSEN_TEXT"
              @click="$emit('schliessen')"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <!-- Gruppen wie in der Seitenleiste (menue.js) -->
          <nav class="dk-schublade-liste">
            <template v-for="(gruppe, gi) in gruppen" :key="'g' + gi">
              <div v-if="gruppe.gruppe" class="dk-schublade-abschnitt">{{ gruppe.gruppe }}</div>
              <a
                v-for="e in gruppe.eintraege"
                :key="e.id"
                class="dk-schublade-punkt"
                :class="{ 'is-aktiv': istAktiv(e) }"
                :href="e.href"
                :aria-current="istAktiv(e) ? 'page' : undefined"
                @click="$emit('schliessen')"
              >
                <svg class="dk-schublade-symbol" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path :d="ICON_PFADE[e.icon] || ''"/>
                </svg>
                <span class="dk-schublade-text">{{ e.label }}</span>
                <span v-if="badgeFuer(e)" class="dk-schublade-zaehler">{{ badgeFuer(e) }}</span>
              </a>
            </template>

            <!-- Fuß der Seitenleiste (Entwurf A9): „Einstellungen“ steht wie am
                 Desktop UNTEN, nicht in einer der Gruppen. Sie ist Teil der
                 Navigation (nicht des Kontos) und bleibt deshalb vor dem
                 Trennstrich. -->
            <div v-if="fussEintraege.length" class="dk-schublade-fussliste">
              <a
                v-for="e in fussEintraege"
                :key="e.id"
                class="dk-schublade-punkt"
                :class="{ 'is-aktiv': istAktiv(e) }"
                :href="e.href"
                :aria-current="istAktiv(e) ? 'page' : undefined"
                @click="$emit('schliessen')"
              >
                <svg class="dk-schublade-symbol" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path :d="ICON_PFADE[e.icon] || ''"/>
                </svg>
                <span class="dk-schublade-text">{{ e.label }}</span>
              </a>
            </div>
          </nav>

          <!-- Fuß (Entwurf A9): Profil mit Beschriftung, Abmelden, Darstellung -->
          <div class="dk-schublade-fuss">
            <a href="#/profile" class="dk-schublade-profil" @click="$emit('schliessen')">
              <span class="dk-schublade-avatar" :style="avatarStil(anzeigeName || user?.fullname)">{{ initialenText }}</span>
              <span class="dk-schublade-profil-text">
                <span class="dk-schublade-profil-name">{{ profilName }}</span>
                <span class="dk-schublade-profil-rolle">Profil</span>
              </span>
              <svg class="dk-schublade-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="9 6 15 12 9 18"/>
              </svg>
            </a>

            <!-- DES-R22: Der Darstellungs-Umschalter lag nur in der
                 Seitenleiste — am Handy ist sie ausgeblendet. Er bleibt in der
                 Schublade erreichbar (beschriftet, Prinzip N8). -->
            <button
              type="button"
              class="dk-schublade-punkt dk-schublade-darstellung"
              :aria-pressed="String(theme === 'dark')"
              @click="$emit('toggle-theme')"
            >
              <svg class="dk-schublade-symbol" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <!-- Symbol zeigt das ZIEL, nicht den Zustand (wie der Text
                     „Hell darstellen“): Sonne = es wird hell, Mond = dunkel. -->
                <template v-if="theme === 'dark'">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                </template>
                <path v-else d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
              <span class="dk-schublade-text">{{ theme === 'dark' ? 'Hell darstellen' : 'Dunkel darstellen' }}</span>
            </button>

            <button type="button" class="dk-schublade-punkt" @click="abmeldenMitMeldung">
              <svg class="dk-schublade-symbol" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              <span class="dk-schublade-text">Abmelden</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * UX3e — Menü-Schublade am Handy (Entwurf A9).
 *
 * Regeln, die OHNE Browser prüfbar sind (was steht drin, was ist aktiv), liegen
 * in `handyMenue.mjs`; diese Datei zeichnet sie und führt die Bedienung:
 *   * Esc schließt (useDialogFokus — Fokusfalle, Fokus kehrt zum Menü-Knopf),
 *   * Zurück-Taste/-Geste schließt (useZurueckSchliesst),
 *   * Wischen nach links schließt (Entwurf A9: „Esc/Wischen schließt“),
 *   * Tippen neben die Schublade schließt,
 *   * jeder Menüpunkt ist ≥ 44 px hoch (Prinzip K4, Entwurf A8/A9).
 */
import { computed, ref } from 'vue'
import { useSession } from '../composables/useSession.js'
import { initialen } from '../composables/anzeigename.mjs'
import { useAbmelden } from '../composables/useAbmelden.js'
import { showToast } from '../composables/useToast.js'
import { ICON_PFADE } from '../menue.js'
import { PRODUKTNAME } from './ui/begriffe.mjs'
import { monogramm } from '../composables/einrichtung.mjs'
import { useDialogFokus } from '../composables/useDialogFokus.js'
import { useZurueckSchliesst } from '../composables/useZurueckSchliesst.js'
import LogoMarke from './einrichtung/LogoMarke.vue'
import {
  schubladeMenue, sichtbarerFuss, istEintragAktiv,
  SCHUBLADE_KOPF_TEXT, SCHUBLADE_SCHLIESSEN_TEXT,
} from './handyMenue.mjs'

const props = defineProps({
  offen: Boolean,
  theme: { type: String, default: 'light' },
  // Seitenname und Adresse der aktuellen Route — für die Markierung „wo bin ich“.
  seite: { type: String, default: '' },
  hash: { type: String, default: '' },
  // Kennzahl an „Personen“ (offene Anfragen), wie in der Seitenleiste.
  anfragenZahl: { type: [Number, null], default: null },
})
const emit = defineEmits(['schliessen', 'toggle-theme'])

const { user, mitglied, isAdmin, istTester: istTesterRef, devmodeAn: devmodeAnRef, anzeigeName, rollen: rollenRef } = useSession()
const { abmelden } = useAbmelden()

const istTester = computed(() => Boolean(istTesterRef?.value && devmodeAnRef?.value))
const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')

const gruppen = computed(() => schubladeMenue({
  istAdmin: isAdmin.value,
  istTester: istTester.value,
  istGast: isGast.value,
  rollen: rollenRef?.value || [],
}))

// Fuß der Seitenleiste („Einstellungen“) — dieselbe Rollenregel wie dort.
const fussEintraege = computed(() => sichtbarerFuss({ istAdmin: isAdmin.value }))

const istAktiv = (e) => istEintragAktiv(e, { seite: props.seite, hash: props.hash })

/** Kennzahl wie in der Seitenleiste (nur „Personen“); nie eine erfundene Null. */
function badgeFuer(e) {
  if (e.badge === 'anfragen' && props.anfragenZahl > 0) return props.anfragenZahl
  return null
}

const gemeindeName = window.__DIakonosBOOT?.church_name || 'Meine Gemeinde'
const logoQuelle = computed(() => String(window.__DIakonosBOOT?.logo_url || ''))
// Dieselbe Regel wie in der Seitenleiste (ON-4/H4): Monogramm, sonst nichts.
const monogrammText = computed(() => {
  const text = String(gemeindeName || '').trim()
  if (!text) return ''
  const buchstabe = monogramm({ gemeindename: text }, text)
  return buchstabe === '?' ? '' : buchstabe
})

const profilName = computed(() => {
  const m = mitglied.value
  const ausMitglied = m ? [m.vorname, m.nachname].filter(Boolean).join(' ').trim() : ''
  return ausMitglied || anzeigeName.value || user.value?.fullname || 'Profil'
})
// OP-HANDY-25: Initialen aus dem gepflegten Namen (Mitglied), nicht aus dem Kontonamen.
const initialenText = computed(() => initialen(mitglied.value, anzeigeName.value || user.value?.fullname))

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

/** W3: Bei einem Fehler bleibt der Nutzer hier und bekommt eine Meldung. */
async function abmeldenMitMeldung() {
  const ergebnis = await abmelden()
  if (ergebnis && ergebnis.ok === false) {
    showToast(ergebnis.fehler || 'Abmelden fehlgeschlagen.', 'error')
  }
}

// Fokusfalle + Esc (DES-R6) und Zurück-Taste/-Geste (OP-HANDY-7).
const fenster = ref(null)
const offenRef = computed(() => props.offen)
const { tastenFaenger } = useDialogFokus(offenRef, fenster, () => emit('schliessen'))
useZurueckSchliesst(offenRef, () => emit('schliessen'))

/* Wischen nach links schließt (Entwurf A9). Nur waagerechte Gesten zählen:
   senkrechtes Wischen bleibt Scrollen der Liste (sonst schlösse die Schublade
   beim Blättern). Mindestweg 40 px, damit ein Tipp mit Zittern nicht zählt. */
const WISCH_MIN_PX = 40
let startX = 0
let startY = 0
let wischAktiv = false
function wischStart(e) {
  const t = e.touches?.[0]
  if (!t) return
  startX = t.clientX
  startY = t.clientY
  wischAktiv = true
}
function wischEnde(e) {
  if (!wischAktiv) return
  wischAktiv = false
  const t = e.changedTouches?.[0]
  if (!t) return
  const dx = t.clientX - startX
  const dy = t.clientY - startY
  if (Math.abs(dx) >= WISCH_MIN_PX && Math.abs(dx) > Math.abs(dy) && dx < 0) {
    emit('schliessen')
  }
}
</script>

<style scoped>
/* Überlagerung: derselbe Ton wie beim früheren Blatt (DES-R1: Tokens, damit
   Hell- und Dunkelmodus aus EINER Quelle kommen). */
.dk-schublade-ueberlagerung {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  justify-content: flex-start;
  background: color-mix(in oklch, var(--dk-navy-900) 45%, transparent);
}
/* Breite nach Entwurf A9: 300 px, höchstens 84 % der Anzeige (schmale Geräte). */
.dk-schublade {
  display: flex;
  flex-direction: column;
  width: 300px;
  max-width: 84vw;
  height: 100%;
  background: var(--dk-surface);
  box-shadow: var(--shadow-lg);
  padding-top: env(safe-area-inset-top, 0px);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  overflow: hidden;
}
.dk-schublade:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }

/* Kopf */
.dk-schublade-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.dk-schublade-marke {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 44px;
  text-decoration: none;
  color: var(--dk-text);
  min-width: 0;
}
.dk-schublade-marke-text { display: flex; flex-direction: column; min-width: 0; }
.dk-schublade-marke-name {
  font-size: var(--fs-16);
  font-weight: var(--fw-fett);
  line-height: 1.2;
}
.dk-schublade-marke-ort {
  font-size: var(--fs-12);
  color: var(--dk-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-schublade-schliessen {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: none;
  border: 0;
  border-radius: var(--radius);
  background: none;
  color: var(--dk-text-muted);
  cursor: pointer;
}
.dk-schublade-schliessen:hover { background: var(--dk-surface-2); color: var(--dk-text); }
.dk-schublade-schliessen:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }

/* Liste */
.dk-schublade-liste {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-2) var(--sp-2) var(--sp-4);
  overscroll-behavior: contain;
}
.dk-schublade-fussliste {
  margin-top: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.dk-schublade-abschnitt {
  padding: var(--sp-2) var(--sp-3) var(--sp-1);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
/* Jeder Menüpunkt: ganze Zeile klickbar, mindestens 44 px (K4), Symbol und
   Text auf gemeinsamer optischer Mitte (Manuel-Auflage 2026-11-04). */
.dk-schublade-punkt {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  min-height: 44px;
  padding: var(--sp-2) var(--sp-3);
  border: 0;
  border-radius: var(--radius);
  background: none;
  color: var(--dk-text);
  font-family: inherit;
  font-size: var(--fs-16);
  font-weight: var(--fw-mittel);
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.dk-schublade-punkt:hover { background: var(--dk-surface-2); }
.dk-schublade-punkt:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
/* Aktiver Eintrag: Fläche + Gewicht, nicht nur Farbe (WCAG 1.4.1). */
.dk-schublade-punkt.is-aktiv {
  background: var(--dk-nav-active-bg, var(--dk-surface-2));
  font-weight: var(--fw-fett);
}
.dk-schublade-symbol { flex: none; color: var(--dk-text-muted); }
.dk-schublade-punkt.is-aktiv .dk-schublade-symbol { color: var(--accent); }
.dk-schublade-text { flex: 1; min-width: 0; }
.dk-schublade-zaehler {
  flex: none;
  padding: 0 var(--sp-2);
  border-radius: var(--badge-r);
  background: var(--accent);
  color: var(--dk-navy-900);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  line-height: 1.6;
}

/* Fuß */
.dk-schublade-fuss {
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
  padding: var(--sp-2) var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.dk-schublade-profil {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: 44px;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  text-decoration: none;
  color: var(--dk-text);
}
.dk-schublade-profil:hover { background: var(--dk-surface-2); }
.dk-schublade-profil:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
.dk-schublade-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 50%;
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
}
.dk-schublade-profil-text { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.dk-schublade-profil-name {
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-schublade-profil-rolle { font-size: var(--fs-12); color: var(--dk-text-muted); }
.dk-schublade-chevron { flex: none; color: var(--dk-text-subtle); }

/* Übergang: von links herein (Entwurf A9), ruhig und kurz. */
.dk-schublade-enter-active, .dk-schublade-leave-active { transition: opacity 0.2s; }
.dk-schublade-enter-active .dk-schublade, .dk-schublade-leave-active .dk-schublade {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.dk-schublade-enter-from, .dk-schublade-leave-to { opacity: 0; }
.dk-schublade-enter-from .dk-schublade, .dk-schublade-leave-to .dk-schublade {
  transform: translateX(-100%);
}
@media (prefers-reduced-motion: reduce) {
  .dk-schublade-enter-active, .dk-schublade-leave-active,
  .dk-schublade-enter-active .dk-schublade, .dk-schublade-leave-active .dk-schublade { transition: none; }
}
</style>
