<template>
  <!-- OP-HANDY-6 / LEISTE-1: DIE Glocke der App — ein Baustein, drei Orte
       (App-Kopfzeile, Seitenleiste, Vollbild-Kopf der Nachrichten). Bis
       LEISTE-1 stand die ganze Liste samt Markieren in AppTopbar.vue; mit
       einem zweiten Ort hätte es sie zweimal gegeben (zwei Zustände, zwei
       Wege, die auseinanderlaufen). Die Logik ist unverändert dieselbe:
       Klick öffnet die Liste, erst NACH dem Anzeigen wird als gelesen
       markiert (`glocke.mjs`, REST-1).

       Zwei Formen:
         knopf="symbol"  — Symbolknopf mit Abzeichen (Kopfzeile, Nachrichten-Kopf)
         knopf="eintrag" — Zeile der Seitennavigation mit Abzeichen
                           (Seitenleiste, Schublade). Die Hülle der Navigation
                           stellt der Aufrufer (a-Tag, NavItem, DkButton). -->
  <div class="dk-notify" :class="{ 'dk-notify--eintrag': knopf === 'eintrag' }">
    <template v-if="knopf === 'eintrag'">
      <!-- Knopf-System (DkButton, UX1g2) in der Bauweise von „Abmelden“ der
           Seitenleiste: Form und Töne aus index.css (`.dk-sb-glocke`). -->
      <DkButton
        variant="ghost"
        class="dk-sb-glocke"
        :aria-label="knopfText"
        :title="knopfText"
        :aria-expanded="listeOffen ? 'true' : 'false'"
        aria-haspopup="dialog"
        @click="toggleListe"
      >
        <template #icon>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        </template>
        <span class="dk-notify-eintrag-text">{{ ZEILE_TEXT }}</span>
        <span v-if="unreadCount > 0" class="dk-nav-badge" aria-hidden="true">{{ kurzZahl }}</span>
      </DkButton>
    </template>

    <template v-else>
      <DkButton
        variant="ghost"
        :class="gross ? 'dk-notify-gross' : 'dk-topbar-symbol'"
        :aria-label="knopfText"
        :title="knopfText"
        :aria-expanded="listeOffen ? 'true' : 'false'"
        aria-haspopup="dialog"
        @click="toggleListe"
      >
        <svg :width="gross ? 20 : 18" :height="gross ? 20 : 18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        <span v-if="unreadCount > 0" class="dk-notify-badge">{{ kurzZahl }}</span>
      </DkButton>
    </template>

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
          <!-- CHAT-6-UI: „Neue Meldung im Chat“ ist kein Lesetext, sondern
               ein Weg — der Klick führt in den Reiter „Chat“ unter „Zu
               prüfen“, wo die Moderation entscheidet. Welche Einträge das
               sind, entscheidet `composables/glockenziele.mjs`. -->
          <DkButton
            v-else-if="istChatMeldung(n)"
            variant="ghost"
            size="md"
            class="dk-notify-eintrag-knopf"
            :aria-label="`Neue Meldung im Chat — zu „Zu prüfen“`"
            @click="zurMeldung(n)"
          >
            <span class="dk-notify-knopftext">
              <span class="dk-notify-betreff">{{ n.subject || 'Neue Meldung im Chat' }}</span>
              <span class="dk-notify-text">{{ kurz(n.email_content) }}</span>
              <span class="dk-notify-zeit">{{ zeitText(n.creation) }}<template v-if="vorText(n.creation)"> · {{ vorText(n.creation) }}</template></span>
              <span class="dk-notify-weg">Zu prüfen · Chat ›</span>
            </span>
          </DkButton>
          <template v-else>
            <!-- CHAT-9b: „…: Du wurdest erwähnt“ ist ebenfalls ein Weg —
                 in den Bereich „Nachrichten“. Die Zuordnung steht in
                 derselben Datei wie die Meldung (`glockenziele.mjs`). -->
            <DkButton
              v-if="istChatErwaehnung(n)"
              variant="ghost"
              size="md"
              class="dk-notify-eintrag-knopf"
              :aria-label="`Erwähnt — zu „Nachrichten“`"
              @click="zurErwaehnung(n)"
            >
              <span class="dk-notify-knopftext">
                <span class="dk-notify-betreff">{{ n.subject || 'Du wurdest erwähnt' }}</span>
                <span class="dk-notify-text">{{ kurz(n.email_content) }}</span>
                <span class="dk-notify-zeit">{{ zeitText(n.creation) }}<template v-if="vorText(n.creation)"> · {{ vorText(n.creation) }}</template></span>
                <span class="dk-notify-weg">Nachrichten ›</span>
              </span>
            </DkButton>
            <template v-else>
              <div class="dk-notify-betreff">{{ n.subject || 'Benachrichtigung' }}</div>
              <div class="dk-notify-text">{{ kurz(n.email_content) }}</div>
              <div class="dk-notify-zeit">{{ zeitText(n.creation) }}<template v-if="vorText(n.creation)"> · {{ vorText(n.creation) }}</template></div>
            </template>
          </template>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { navigate } from '../router.js'
import { useNotifications } from '../composables/useNotifications.js'
import { serverZeit, serverZeitText } from '../../shared/zeit.mjs'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import DkButton from './ui/DkButton.vue'
import DkSkelett from './ui/DkSkelett.vue'
import DkEmpty from './ui/DkEmpty.vue'
import { darfAlsGelesenMarkieren } from '../composables/glocke.mjs'
import { istDatenanfrage, fragendePerson, profilAdresse } from '../composables/datenAnfrage.mjs'
// CHAT-6-UI: „Neue Meldung im Chat“ führt in den Reiter „Chat“ unter
// „Zu prüfen“ — die Zuordnung steht in EINER Datei (`glockenziele.mjs`).
import { istChatMeldung, meldungZiel } from '../composables/glockenziele.mjs'
// CHAT-9b: „Du wurdest erwähnt“ führt in das GESPRÄCH der Nachricht
// (`chat.nachricht_kontext`) — dieselbe EINE Zuordnungsdatei.
import { erwaehnungZiel, istChatErwaehnung } from '../composables/glockenziele.mjs'
import { apiGet } from '../composables/useApi.js'

const props = defineProps({
  /**
   * Form des Auslösers: `symbol` (Symbolknopf mit Abzeichen, für Kopfzeilen)
   * oder `eintrag` (beschriftete Zeile der Navigation).
   */
  knopf: { type: String, default: 'symbol' },
  /** Nur bei `symbol`: größere Trefferfläche (Vollbild-Kopf am Handy). */
  gross: { type: Boolean, default: false },
})

/** Der Name der Zeile in der Navigation (Manuel 23.11.: „Benachrichtigungen“). */
const ZEILE_TEXT = 'Benachrichtigungen'

const { unreadCount, notifications, laden, fehler, ladeListe, markAsRead } = useNotifications()
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar: listenSichtbar } = useLadeSkelett(laden)

/**
 * Der Vorlese-Text des Auslösers: mit Zahl, sonst nur das Ziel. Dieselbe
 * Aussage in allen drei Orten (Kopfzeile, Seitenleiste, Nachrichten-Kopf).
 */
const kurzZahl = computed(() => (unreadCount.value > 99 ? '99+' : unreadCount.value))
const knopfText = computed(() => (unreadCount.value > 0
  ? `${unreadCount.value} neue Benachrichtigungen`
  : 'Benachrichtigungen'))

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

/**
 * CHAT-6-UI: Der Klick auf „Neue Meldung im Chat“ führt in den Reiter „Chat“
 * unter „Zu prüfen“. Das Panel schließt dabei (die Meldung ist gelesen, die
 * Person ist unterwegs) und markiert die Zeile als gelesen — wie beim
 * Datenanfrage-Weg.
 */
function zurMeldung(meldung) {
  listeOffen.value = false
  if (unreadCount.value > 0) markAsRead([meldung].filter(Boolean))
  navigate(meldungZiel())
}

/**
 * CHAT-9b: Der Klick auf „Du wurdest erwähnt“ führt in das Gespräch der
 * Nachricht. Die Glocke trägt die Kennung der NACHRICHT; welches Gespräch das
 * ist, sagt der Server (`chat.nachricht_kontext`, siehe `glockenziele.mjs`).
 * Antwortet er neutral oder scheitert der Aufruf, bleibt es beim Bereich
 * „Nachrichten“ — keine geratene Kennung.
 */
async function zurErwaehnung(meldung) {
  listeOffen.value = false
  if (unreadCount.value > 0) markAsRead([meldung].filter(Boolean))
  const ziel = await erwaehnungZiel(meldung, apiGet)
  navigate(ziel)
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
</script>

<style scoped>
.dk-notify-eintrag-text { flex: 1 1 auto; }
/* Symbolform der Kopfzeile/des Nachrichten-Kopfs: Abzeichen oben rechts am
   Knopf — Position wie `.dk-topbar-symbol` (der Abstand kommt aus Tokens). */
.dk-notify-gross {
  position: relative;
  min-width: var(--control-h);
  min-height: var(--control-h);
}
</style>
