<template>
  <header class="dk-topbar">
    <div class="dk-topbar-left">
      <!-- UX3e (Entwurf A8): Menü-Symbol OBEN LINKS öffnet die Schublade mit
           der vollständigen Navigation. MT-1 (Manuel 11.11.): Es gehört
           AUSSCHLIESSLICH zur Handy-Lage. Am Laptop/Desktop gibt es genau EINEN
           Einstieg zur Navigation — die Seitenleiste selbst; eingeklappt ist
           das ihr eigener Ausklapp-Knopf oben in der Leiste (S4/N5). Vorher
           zeigte die Kopfzeile bei eingeklappter Leiste zusätzlich einen
           Hamburger, der ein ZWEITES, identisches Panel öffnete; damit standen
           beide Einstiege nebeneinander und der Hamburger lag direkt neben der
           Überschrift. Die Sichtbarkeit regelt index.css: Grundregel `none`,
           an nur noch `.dk-app--handy`. -->
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

      <!-- Breadcrumbs. A10 (Review 09.11., Punkt 4): Am Handy ist die letzte
           Krume der SEITENTITEL („Kalender“) — die Gestaltung der Titelstufe
           steht in index.css; die Seite gibt dafür ihren eigenen Titel ab,
           damit „Kalender“ nur EINMAL im Kopf steht. Andere Krumen
           („Personen / X“) stehen dort nicht mehr: der Titel des Bereichs
           genügt, wie Entwurf A10 es zeigt. -->
      <nav class="dk-crumbs">
        <template v-for="(crumb, i) in breadcrumbs" :key="i">
          <span v-if="i === breadcrumbs.length - 1" class="dk-crumb dk-crumb-current">{{ crumb }}</span>
          <span v-else-if="i === 0 && breadcrumbs.length > 1" class="dk-crumb dk-crumb-weg">{{ crumb }}</span>
          <span v-else-if="i > 0" class="dk-crumb dk-crumb-sep">/</span>
        </template>
      </nav>
      <!-- A10: Abzeichen „Moderator“ am Handy neben dem Titel (Entwurf A10:
           Menü · Kalender [Moderator] · Suche). Die SEITE setzt es, wenn sie
           das Recht hat (eine Rechtequelle, `can_moderate`); ohne Recht ist
           der Halter leer — kein Platz, kein Abzeichen. -->
      <span v-if="rollenMarke" class="dk-topbar-rolle">
        <DkBadge variant="info">{{ rollenMarke }}</DkBadge>
      </span>
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
              :class="{ 'is-neu': !n.read, 'is-datenanfrage': istDatenanfrage(n) }"
            >
              <!-- R-9 (Manuel 11.11.): Eine „Datenanfrage“ ist kein Lesetext,
                   sondern ein Weg — der Klick führt ins EIGENE Profil zum
                   Abschnitt „Sichtbarkeit“, wo die Freigabe-Schalter stehen.
                   Welche Anfrage gemeint ist, geht als Kennung mit (der
                   Profilseite sagt sie, wer gefragt hat). Alle anderen
                   Meldungen bleiben Text wie bisher. -->
              <DkButton
                v-if="istDatenanfrage(n)"
                variant="ghost"
                size="md"
                class="dk-notify-eintrag-knopf"
                :aria-label="datenanfrageLabel(n)"
                @click="zurSichtbarkeit(n)"
              >
                <span class="dk-notify-knopftext">
                  <span class="dk-notify-betreff">{{ n.subject || 'Datenanfrage' }}</span>
                  <span class="dk-notify-text">{{ kurz(n.email_content) }}</span>
                  <span class="dk-notify-zeit">{{ zeitText(n.creation) }}<template v-if="vorText(n.creation)"> · {{ vorText(n.creation) }}</template></span>
                  <span class="dk-notify-weg">Zur Sichtbarkeit im Profil ›</span>
                </span>
              </DkButton>
              <template v-else>
                <div class="dk-notify-betreff">{{ n.subject || 'Benachrichtigung' }}</div>
                <div class="dk-notify-text">{{ kurz(n.email_content) }}</div>
                <div class="dk-notify-zeit">{{ zeitText(n.creation) }}<template v-if="vorText(n.creation)"> · {{ vorText(n.creation) }}</template></div>
              </template>
            </li>
          </ul>
        </div>
      </div>

      <div class="dk-topbar-divider" />

      <!-- DEVBADGE-1: Platz für einen Eintrag der Kopfzeile — dort setzt
           `App.vue` den Dev-Einschaltknopf ein, solange die Handy-Lage gilt
           (die Karte erlaubt ausdrücklich „Eintrag im Kopf statt schwebendes
           Element“). Am Desktop trägt `App.vue` den Knopf gar nicht hier ein
           (`:dev-knopf="devStartZeigen && istHandyLage"` bleibt dort falsch),
           also wird dieser Platz dort auch nicht gerendert — kein leerer
           Rest, keine 44-px-Lücke.
           BEWUSST `v-if` MIT EIGENER EIGENSCHAFT (`devKnopf`, gesetzt in
           `App.vue`) statt eines Slots, der sich selbst ein-/ausblendet: der
           Platz in der Kopfzeile soll nur entstehen, wenn der Knopf wirklich
           da ist (sonst stünde am Handy eine leere 44-px-Lücke), und die
           Kopfzeile soll nicht am Dev-Zustand der App hängen. Die Bedingung
           steht damit an EINER Stelle (`devStartZeigen && istHandyLage` in
           App.vue) und ist im Quelltext nachprüfbar. -->
      <div v-if="devKnopf" class="dk-topbar-dev">
        <slot name="dev-knopf" />
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, nextTick, onMounted, onUnmounted } from 'vue'
import { currentPageName, navigate } from '../router.js'
import { useNotifications } from '../composables/useNotifications.js'
import { rollenMarke } from '../composables/useBereichskopf.js'
import { serverZeit, serverZeitText } from '../../shared/zeit.mjs'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import DkButton from './ui/DkButton.vue'
import DkSkelett from './ui/DkSkelett.vue'
import DkEmpty from './ui/DkEmpty.vue'
import DkSymbol from './ui/DkSymbol.vue'
import DkBadge from './ui/DkBadge.vue'
import { darfAlsGelesenMarkieren } from '../composables/glocke.mjs'
import { istDatenanfrage, fragendePerson, profilAdresse } from '../composables/datenAnfrage.mjs'
import { krumenZuSeite } from '../menue.js'
import { MENUE_KNOPF_TEXT } from './handyMenue.mjs'

const props = defineProps({
  collapsed: Boolean,
  // UX3e: Zustand des Menü-Knopfes (`aria-expanded`) — er muss sagen, ob die
  // Schublade offen ist, sonst kündigt er sie falsch an (Prinzip N4/S4).
  menueOffen: { type: Boolean, default: false },
  // A10: Abzeichen neben dem Titel am Handy („Moderator“) — LEER, wenn die
  // Seite kein Recht gemeldet hat (dann gibt es kein Abzeichen und keinen
  // Platz dafür, Karte A10).
  rollenMarke: { type: String, default: '' },
  // DEVBADGE-1: In der Handy-Lage trägt die Kopfzeile den Dev-Einschaltknopf
  // (statt eines schwebenden Abzeichens). Der Platz entsteht nur, wenn der
  // Knopf wirklich da ist — sonst stünde am Handy eine leere Lücke.
  devKnopf: { type: Boolean, default: false },
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

/** Vorlesehilfe-Text des Weges: wer gefragt hat, sonst allgemein. */
function datenanfrageLabel(meldung) {
  const wer = fragendePerson(meldung)
  return wer
    ? `Datenanfrage von ${wer} — zur Sichtbarkeit im Profil`
    : 'Datenanfrage — zur Sichtbarkeit im Profil'
}

/**
 * R-9: Der Klick auf eine „Datenanfrage“ führt ins Profil, Abschnitt
 * „Sichtbarkeit“ — dort stehen die Freigabe-Schalter. Die Kennung der
 * angefragten Meldung geht als `anfrage` mit, damit die Profilseite sagen
 * kann, WER gefragt hat (der Betreff trägt den Namen). Das Panel schließt
 * dabei: die Meldung ist gelesen, die Person ist unterwegs.
 */
function zurSichtbarkeit(meldung) {
  const ziel = profilAdresse('sichtbarkeit')
  const kennung = String(meldung?.name || '')
  const adresse = kennung
    ? `${ziel}&anfrage=${encodeURIComponent(kennung)}`
    : ziel
  listeOffen.value = false
  if (unreadCount.value > 0) markAsRead([meldung].filter(Boolean))
  navigate(adresse)
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

/** ZEIT-2: `creation` einer Benachrichtigung ist ein SERVER-Zeitstempel (UTC). */
function zeitText(iso) {
  return serverZeitText(iso)
}

/**
 * ZEIT-2: „vor 3 Minuten“ fuer dieselbe Angabe. Der Vergleich laeuft auf
 * echten Zeitpunkten, nicht auf Text: vorher entstand aus einem UTC-Wert
 * minus Ortszeit eine Zeitspanne, die 1–2 h zu klein war („gerade eben“).
 */
function vorText(iso) {
  const d = serverZeit(iso)
  if (!d) return ''
  return 'vor ' + kurzVor(Date.now() - d.getTime())
}

function kurzVor(ms) {
  if (!(ms > 0)) return 'gerade eben'
  const minuten = Math.floor(ms / 60000)
  if (minuten < 1) return 'gerade eben'
  if (minuten < 60) return `${minuten} ${minuten === 1 ? 'Minute' : 'Minuten'}`
  const stunden = Math.floor(minuten / 60)
  if (stunden < 24) return `${stunden} ${stunden === 1 ? 'Stunde' : 'Stunden'}`
  const tage = Math.floor(stunden / 24)
  return `${tage} ${tage === 1 ? 'Tag' : 'Tagen'}`
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
  // UX3j (A3, Punkt 4): Die Reiter von „Personen“ tragen oben „Personen“ —
  // vorher stand dort der rohe Komponentenname („MitgliederAnfragen“).
  // Die Seitennamen selbst bleiben (Anker für Rechte-Guard und Fenstertitel).
  MitgliederAnfragen:    ['Personen'],
  MitgliederDatenschutz: ['Personen'],
  MitgliederImport:      ['Personen'],
  MitgliederLoeschantraege: ['Personen', 'Löschanträge'],
  MitgliederUebersicht:  ['Personen', 'Übersicht'],
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
