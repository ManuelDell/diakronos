<template>
  <!-- Loading state -->
  <div v-if="checking" class="dk-screen dk-screen-enter mod-zustand">
    <!-- UX2d3b (Review UX2d3a/B): ruhiger Platzhalter statt des Satzes
         „Berechtigung wird geprüft…“ — der Umriss zeigt, dass etwas kommt. -->
    <div class="mod-zustand-box">
      <DkSkelett form="zeilen" :anzahl="3" text="Berechtigung wird geprüft" />
    </div>
  </div>

  <!-- CHAT-6-UI-2 (SOLL 3): Netz- oder Serverfehler beim ersten Laden. Vorher
       fiel die Seite auf die Sperrseite zurück — „Zugriff verweigert“, obwohl
       in Wahrheit nur die Antwort fehlt. Hier steht, was passiert ist, und der
       Weg zurück: „Erneut versuchen“. Sichtbar auch für Moderatorinnen und
       Moderatoren (die Sperrseite hängt am Recht, nicht am Fehler).

       Die Reihenfolge der Zweige ist die Aussage: `darfEtwas` ZUERST — wessen
       Weg offen ist, sieht seine Inhalte auch dann, wenn die andere Anfrage
       scheiterte. Erst wenn nichts offen ist, entscheidet der Fehler zwischen
       „gerade nicht erreichbar“ (noch keine Antwort) und „Zugriff verweigert“
       (beide Antworten sagen nein). -->
  <div v-else-if="!darfEtwas && (ladeFehler || !beideGeantwortet)"
       class="dk-screen dk-screen-enter mod-zustand mod-zustand--verweigert">
    <div class="mod-verweigert">
      <div class="mod-verweigert-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 8v5"/><path d="M12 16.5v.01"/><circle cx="12" cy="12" r="9"/>
        </svg>
      </div>
      <h2 class="mod-verweigert-titel">Gerade nicht erreichbar</h2>
      <p class="mod-verweigert-text" role="alert">
        {{ ladeFehler || 'Die Antwort des Servers steht noch aus.' }}
      </p>
      <DkButton variant="secondary" :loading="checking" @click="erneutVersuchen">
        Erneut versuchen
      </DkButton>
    </div>
  </div>

  <!-- Forbidden screen: NUR wenn weder Termine noch Chat-Meldungen zu prüfen
       sind. Die beiden Rechte sind VERSCHIEDEN (Review CHAT-6 R1): „Termine
       prüfen“ ist ein Kalender-Recht, die Chat-Meldungen hängen an HV/MV/GL
       der Gruppe bzw. an der Meldestelle im 1:1. Der Server sagt je Weg, ob
       er offen ist — hier steht keine eigene Rechtelogik. -->
  <div v-else-if="!darfEtwas" class="dk-screen dk-screen-enter mod-zustand mod-zustand--verweigert">
    <div class="mod-verweigert">
      <div class="mod-verweigert-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <h2 class="mod-verweigert-titel">Zugriff verweigert</h2>
      <p class="mod-verweigert-text">
        Du hast keine Berechtigung, Termine oder Meldungen zu prüfen.<br>
        Termine geben Moderatoren der Kalender frei, Meldungen aus dem Chat
        prüfen die Verantwortlichen der Gruppe.
      </p>
      <DkButton variant="secondary" @click="goToKalender">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        Zurück zum Kalender
      </DkButton>
    </div>
  </div>

  <!-- Tafel „Zu prüfen“ (UX3a: der vierte Reiter des Kalenders) -->
  <div v-else class="dk-screen dk-screen-wide dk-moderation dk-screen-enter">
    <!-- UX3d: Kopf und Reiterleiste des Kalenders stehen auch hier — der
         vierte Reiter ist der aktive, „Monat/Woche/Liste“ führen zurück. So
         ist der Weg hinein und hinaus EIN Muster, und der Seitentitel
         („Zu prüfen“) steht dort, wo sonst der Monatsname steht. Die
         Bedienung der Tafel bleibt unverändert (Alle freigeben, Erklärung,
         Änderungen, Brett). Vorher trug die Seite ihren eigenen Seitenkopf. -->
    <KronosTopbar
      class="dk-moderation-kopf"
      dateTitle="Zu prüfen"
      :currentView="'pruefen'"
      viewMode="view"
      :canWrite="false"
      :canModerate="canModerate"
      :offeneZahl="prüfZahl > 0 ? prüfZahl : null"
      :chatRecht="chatRecht"
      :chatZahl="chatOffen"
      :aktiverReiter="zeigeChat ? 'chat' : 'pruefen'"
      :pruefTafel="true"
    />
    <!-- CHAT-6-UI-2 (Review R2, MUSS 1): `pruefTafel` gilt auf der GANZEN
         Prüfseite. Vorher hing es am Chat-Zweig (`!zeigeChat && canModerate`)
         — dort zeigte der Kopf Kalender-Auswahl, „Heute“, ‹ › und
         Monat/Woche/Liste als UMSCHALTER, deren Ereignisse diese Seite nicht
         auswertet (tote Knöpfe, Befund wie DEV-B2). Mit `true` sind
         „Monat/Woche/Liste“ LINKS zurück in den Kalender, und die
         Kalender-Werkzeuge stehen hier gar nicht. -->

    <div class="dk-moderation-inhalt">
      <!-- CHAT-6-UI: Die Meldungen aus dem Chat stehen im BESTEHENDEN Ort
           „Moderation“ (Kalender-Kopf), als Reiter „Chat“ — kein neuer Ort.
           Die Reiterzeile erscheint NUR, wenn der Server `meldungen_liste`
           nicht mit 403 beantwortet: keine Rechtelogik im Frontend. -->
      <template v-if="zeigeChat">
        <div class="dk-moderation-aktionen">
          <!-- CHAT-6-UI-2 (SOLL 2): Der Rückweg „‹ Termine“ führt auf die
               TERMINE-Tafel — die gibt es ohne Kalender-Recht nicht. Wer nur
               Meldungen prüfen darf, bekommt hier KEINEN toten Weg: die
               Kopfzeile trägt „Monat/Woche/Liste“ als Links in den Kalender,
               und am Handy führt „‹ Kalender“ (eigene Zeile) zurück. -->
          <a
            v-if="canModerate"
            class="dk-moderation-mobile-back"
            href="#/kalender/pruefen"
            @click.prevent="nurTermine"
          >
            <DkSymbol name="zurueck" :groesse="16" />
            <span>Termine</span>
          </a>
          <span class="dk-moderation-anzahl">{{ chatOffen > 0 ? zahlWort(chatOffen, 'Meldung', 'Meldungen') + ' offen' : MELDE_TEXTE.keineOffenen }}</span>
        </div>
        <p class="dk-moderation-erklaerung">
          Hier stehen die Nachrichten, die im Chat gemeldet wurden. Aufgeklappt
          siehst du die gemeldete Nachricht und die fünf davor — nur so ist der
          Zusammenhang zu beurteilen. Du entscheidest, ob die Nachricht aus dem
          Verlauf genommen oder die Meldung zurückgewiesen wird.
        </p>
        <ChatMeldungen
          ref="meldungenEl"
          :zeilen="chatZeilen"
          :laedt="chatLaedt"
          :lade-fehler="chatFehler"
          :erledigt-geladen="erledigtGeholt"
          @erledigte-anfordern="erledigteAnfordern"
          @entschieden="meldungEntscheiden"
        />
      </template>

      <template v-else>
        <!-- CHAT-6-UI-2 (Review R2, SOLL 1): Hier stand ein ZWEITER Chat-Zweig
             für den Fall „kein Kalender-Recht“ — im `v-else` des Chat-Zweigs
             ist `canModerate` aber immer wahr: der Block war unerreichbar (und
             doppelte die Meldungsliste). Er ist entfernt; der Chat steht
             genau einmal, oben.

             Übrig bleibt die TERMINE-Tafel. Erreichbar ist dieser Zweig nur,
             wenn mindestens ein Weg offen ist (`darfEtwas`): kann die Person
             KEINE Termine prüfen, wurde oben bereits in den Chat-Zweig
             umgeleitet (`zeigeChat`) — und ist auch der Chat zu, steht die
             Sperrseite. -->
      <div class="dk-moderation-aktionen">
        <!-- DEV-B2 (Befund DMB-8e166c0aacff): Der Rückweg „‹ Kalender“ steht
             NUR am Handy hier. Am Desktop und am Tablet führen die Reiter der
             Kopfzeile („Monat · Woche · Liste“) zurück — ein zweiter Weg
             daneben war genau der Befund („‹ Kalender erscheint“). Bis hier
             hatte die Klasse GAR KEIN CSS: der Knopf stand auf jeder Breite. -->
        <a
          class="dk-moderation-mobile-back"
          href="#/kalender"
          @click.prevent="goToKalender"
        >
          <DkSymbol name="zurueck" :groesse="16" />
          <span>Kalender</span>
        </a>
        <span class="dk-moderation-anzahl">{{ prüfZahl > 0 ? zahlWort(prüfZahl, 'Termin', 'Termine') + ' zu prüfen' : '' }}</span>
        <DkButton variant="primary" :disabled="!canFinalize" @click="finalizeAll">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10-10"/></svg>
          {{ finalizing ? '…' : 'Alle freigeben' }}
        </DkButton>
      </div>

      <!-- OP-ADMIN-18: Erklärsatz über der Moderationstafel. Wer die Seite
           zum ersten Mal öffnet, soll ohne Nachfrage wissen, was hier passiert
           und was die beiden Ablagen bedeuten.
           UI-R4: „wird verbindlich“ stimmt nur bei der LETZTEN Stufe — bis
           dahin hakt jede Freigabe eine Stufe ab (das sagt die Warteline an
           jeder Karte). Deshalb hier kein Versprechen mehr, das bei mehreren
           Stufen falsch wäre. -->
      <p class="dk-moderation-erklaerung" data-test="moderation-erklaerung">
        Neue Terminvorschläge landen links unter „Vorschläge“. Ziehst du einen
        Vorschlag nach rechts in „Freigeben“ oder drückst „Alle freigeben“, wird
        er geprüft. Jede Karte sagt, welche Stufe als Nächstes dran ist — erst
        wenn keine mehr offen ist, erscheint der Termin im Kalender. Bis dahin
        sehen ihn nur die Moderatorinnen und Moderatoren.
      </p>

      <!-- UI-R4, Punkt 3: Freigabe-Anträge (Kalender/Inhalte für Gruppe oder
           Gemeinde). Der Abschnitt erscheint nur, wenn es welche gibt. -->
      <ModerationAntraege @entschieden="nachEntscheidung" />

      <!-- Änderungen an freigegebenen Terminen (Operator-Regel 16.10.) -->
      <ModerationAenderungen />

      <!-- Board -->
      <ModerationBoard ref="board" @entschieden="zaehlerLaden" />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import ModerationBoard from '../components/kronos/ModerationBoard.vue'
import ModerationAenderungen from '../components/kronos/ModerationAenderungen.vue'
import ModerationAntraege from '../components/kronos/ModerationAntraege.vue'
import KronosTopbar from '../components/kronos/KronosTopbar.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkSymbol from '../components/ui/DkSymbol.vue'
// CHAT-6-UI: der Reiter „Chat“ — Meldungen aus dem Chat, Ausschnitt,
// Entscheidungen. Der Reiter erscheint nur, wenn der Server nicht 403 sagt.
import ChatMeldungen from '../components/chat/ChatMeldungen.vue'
import {
  MELDUNGEN_ADRESSE, TEXTE as MELDE_TEXTE, keineRechte, meldungZeilen, offenZahl,
  reiterAusAdresse,
} from '../components/chat/meldung.mjs'
// CHAT-6-UI-2/UI-3 (MUSS 2): derselbe Merker wie `pages/Kalender.vue` — die
// Prüfseite holt die Arbeitsliste selbst und SCHREIBT die Antwort hinein; der
// Kalender-Kopf zeigt danach dieselbe Zahl. Kein zweiter Abrufweg.
import { useChatPruefRecht } from '../composables/chatPruefRecht.mjs'
// CHAT-6-UI: Fehlertexte des Servers (403/409/400) in Klartext — dieselbe
// Quelle wie die übrigen Seiten.
import { fehlertext, zustandFuer } from '../../shared/fehlertexte.js'
// UX2d3b (Review UX2d3a/B): Laden/Prüfen zeigt den Umriss, keinen Satz.
import DkSkelett from '../components/ui/DkSkelett.vue'
import { apiCall } from '../composables/useApi.js'
import { finalizeStagedEvents, getModerationCount } from '../api/kanbanApi.js'
import { showToast } from '../composables/useToast.js'
import { navigate } from '../router.js'
import { zahlWort } from '../components/ui/begriffe.mjs'
// UI-R4/R4b: ehrliche Freigabe-Meldung. `sammelMeldung` wertet für
// „Alle freigeben“ die Serverzahlen `festgelegt`/`weitergereicht` aus.
import { sammelMeldung } from '../components/kronos/freigabeStufen.mjs'

// ── Permission check ─────────────────────────────────────────────────────────
const checking = ref(true)
const canModerate = ref(false)

// ── Reiter „Chat“ (CHAT-6-UI): Zustand ───────────────────────────────────────
// Der Zustand steht VOR `canFinalize`/`zeigeChat` (die Eigenschaften der
// Kopfzeile oben lesen ihn). Ob es den Reiter gibt, entscheidet der SERVER:
// `chat.meldungen_liste` antwortet mit einer Liste oder mit 403 („keine
// Moderationsrechte“). Keine Rechtelogik im Frontend.
//
// WICHTIG (Review CHAT-6 R1): `chatRecht` ist ein EIGENES Recht — es hat mit
// `can_moderate` (Kalender) nichts zu tun. Beide Wege werden getrennt gefragt;
// eine Seite ist offen, wenn MINDESTENS einer von beiden offen ist.
const chatRecht = ref(false)
const chatLaedt = ref(false)
const chatFehler = ref('')
const chatZeilen = ref([])
const chatOffen = ref(0)
const meldungenEl = ref(null)
/**
 * CHAT-6-UI-2 (SOLL 3): Klartext eines Netz-/Serverfehlers beim ERSTEN Laden
 * (`''` = keiner). Ein 403 ist KEIN solcher Fehler (er schließt nur den
 * Chat-Weg) — er landet hier deshalb nie. Solange etwas fehlt, ist die Seite
 * weder Sperrseite noch Tafel, sondern eine Fehlerseite mit „Erneut
 * versuchen“.
 */
const ladeFehler = ref('')
/** Antwort des Termine-Rechts dieses Besuchs — `null` = noch keine. */
const termineRecht = ref(null)

/** CHAT-6-UI-2 (MUSS 2): der geteilte Merker — hier wird hineingeschrieben. */
const { merken: chatMerken } = useChatPruefRecht()

/** Steht die Liste „Erledigte Meldungen“ offen? Dann werden die Stände
 *  `erledigt`/`verworfen` zusätzlich geholt (der Server filtert hart). */
const erledigtGeholt = ref(false)

/** Der Reiter steht in der Adresse (`?reiter=chat`) — Lesezeichen, Zurück. */
const aktiverReiter = ref(reiterAusAdresse(typeof window === 'undefined' ? '' : window.location.hash))
const chatGewaehlt = computed(() => chatRecht.value && aktiverReiter.value === 'chat')
const zeigeChat = computed(() => chatGewaehlt.value || (chatRecht.value && !canModerate.value))

/**
 * Ist die Seite überhaupt offen? Sperrseite nur, wenn BEIDE Wege zu sind UND
 * beide Antworten da sind. Solange ein Weg noch aussteht oder an einem
 * Netz-/Serverfehler scheiterte, steht die Fehlerseite (SOLL 3) — nicht
 * „Zugriff verweigert“.
 */
const beideGeantwortet = computed(() => termineRecht.value !== null && !chatLaedt.value)
const darfEtwas = computed(() => canModerate.value || chatRecht.value)

// ── Board state ──────────────────────────────────────────────────────────────
const board = ref(null)
const moderationCount = ref(0)
const finalizing = ref(false)

/**
 * UI-R4/R-12: Die Zahl „Zu prüfen“ kommt aus `getModerationCount` — der
 * Server zählt genau die Vorschläge, die der Aufrufer auf der OFFENEN Stufe
 * prüfen darf (dieselbe Regel wie `darf_pruefen` auf dem Brett). Reiterzahl,
 * Panelkopf und Liste laufen damit nicht mehr auseinander; die Seite führt
 * keine zweite, eigene Zählung.
 */
const prüfZahl = computed(() => moderationCount.value)

const canFinalize = computed(() => {
  if (!board.value) return false
  const ids = board.value.getStagingIds()
  return ids.length > 0 && !finalizing.value
})

/** Die Zahl neu holen (nach einem Entscheid auf dem Brett). */
async function zaehlerLaden() {
  try {
    const cnt = await getModerationCount()
    const n = Number(cnt?.count)
    moderationCount.value = Number.isFinite(n) ? n : 0
  } catch {
    // Ein Fehler bleibt still: die Zahl ist eine Kennzahl, kein Inhalt.
  }
}

/** Ein Freigabe-Antrag wurde entschieden — Tafel und Zahl nachziehen. */
async function nachEntscheidung() {
  await board.value?.reloadBoard?.()
  await zaehlerLaden()
}

// ── Navigation ───────────────────────────────────────────────────────────────
function goToKalender() {
  navigate('#/kalender')
}

// ── Reiter „Chat“ (CHAT-6-UI): Laden und Entscheiden ────────────────────────

/**
 * Der Reiter „Chat“ ist ein LINK am Kalender-Kopf
 * (`menue.KALENDER_CHAT_REITER`, Adresse `#/kalender/pruefen?reiter=chat`):
 * der Klick schreibt die Adresse, der Router lädt dieselbe Seite neu — hier
 * wird der Reiter aus der Adresse gelesen und die Liste geholt. Kein eigener
 * Umschalter, keine zweite Wahrheit über den gewählten Reiter.
 */
async function reiterAusAdresseLesen() {
  if (typeof window === 'undefined') return ''
  const wert = reiterAusAdresse(window.location.hash)
  if (wert === 'chat' && aktiverReiter.value !== 'chat') {
    aktiverReiter.value = 'chat'
    await meldungenLaden()
    return wert
  }
  if (wert !== 'chat') aktiverReiter.value = ''
  return wert
}

/** Zurück auf die Termine (Rückweg am Handy im Reiter). */
function nurTermine() {
  aktiverReiter.value = ''
  if (typeof window !== 'undefined') navigate('#/kalender/pruefen')
}

/**
 * Meldungen holen — offene Meldungen und, wenn verlangt, die erledigten.
 *
 * Der Server filtert hart auf `stand`; deshalb sind es GETRENNTE Abrufe
 * (Review CHAT-6 R1, MUSS 2): `offen` ist die Arbeitsliste und trägt den
 * Zähler, `erledigt` + `verworfen` füllen den zweiten Abschnitt. Die Listen
 * werden zusammengeführt (je Meldung gilt der Abruf, der sie geliefert hat).
 *
 * Ob es den Reiter gibt, entscheidet NUR die Antwort dieses Abrufs: eine
 * Liste heißt „darf moderieren“, ein 403 heißt „nein“. Jeder ANDERE Fehler
 * (Netz, 5xx) ist KEINE Antwort über Rechte — `chatRecht` bleibt, wo es war,
 * und der Text steht in der Fläche (im Reiter bzw. auf der Fehlerseite).
 *
 * Die Antwort wird in den geteilten Merker geschrieben (CHAT-6-UI-2, MUSS 2):
 * der Kalender-Kopf zeigt danach dieselbe Zahl, ohne selbst erneut zu fragen.
 */
async function meldungenLaden() {
  chatLaedt.value = true
  chatFehler.value = ''
  ladeFehler.value = ''
  let offenOk = false
  try {
    const daten = await apiCall('chat.meldungen_liste', { stand: 'offen' })
    chatOffen.value = offenZahl(daten)
    const offene = meldungZeilen(daten)
    offenOk = true
    chatRecht.value = true
    chatZeilen.value = offene
    chatMerken({ recht: true, zahl: chatOffen.value })
    // Erledigte NUR holen, wenn der zweite Abschnitt offen ist — kein Abruf
    // auf Vorrat.
    if (erledigtGeholt.value) await erledigteHolen()
  } catch (fehler) {
    if (keineRechte(fehler)) {
      // 403 = keine Moderationsrechte: der Reiter erscheint gar nicht.
      chatRecht.value = false
      chatMerken({ recht: false, zahl: null })
    } else {
      // Netz/Server: KEINE Rechtelage. Der Text steht im Reiter; ist der
      // Chat der EINZIGE Weg, bleibt davon nur die Fehlerseite übrig
      // (`ladeFehler`).
      chatFehler.value = fehlertext(fehler)
      ladeFehler.value = chatFehler.value
    }
  } finally {
    chatLaedt.value = false
  }
  return offenOk
}

/**
 * Die erledigten Stände holen (`erledigt` und `verworfen` — getrennt, weil der
 * Server je Abruf genau EINEN Stand liefert) und an die offene Liste hängen.
 * Die offenen Meldungen bleiben, was der letzte `offen`-Abruf geliefert hat.
 *
 * Ein 403 hier setzt `chatRecht` NICHT auf `false` (SOLL 5): die Arbeitsliste
 * war eben offen — der zweite Abschnitt ist ein Zusatz. Der Fehler steht als
 * Hinweis über der Liste.
 */
async function erledigteHolen() {
  erledigtGeholt.value = true
  const fertig = []
  for (const stand of ['erledigt', 'verworfen']) {
    try {
      const daten = await apiCall('chat.meldungen_liste', { stand })
      fertig.push(...meldungZeilen(daten))
    } catch (fehler) {
      chatFehler.value = fehlertext(fehler)
    }
  }
  const offene = chatZeilen.value.filter((m) => m.offen)
  chatZeilen.value = [...offene, ...fertig]
}

/**
 * Der zweite Abschnitt wurde geöffnet (oder der Filter gewechselt).
 *
 * SOLL 4: Nur `erledigtGeholt` entscheidet — wurde schon geholt, wird NICHT
 * erneut gefragt, auch wenn die Liste leer ist (vorher löste jede leere Liste
 * einen neuen Abruf aus, weil zusätzlich nach einer erledigten Zeile gesucht
 * wurde).
 */
async function erledigteAnfordern() {
  if (erledigtGeholt.value) return
  await erledigteHolen()
}

/**
 * Eine Entscheidung — `chat.meldung_entscheiden(meldung, entscheidung, grund)`.
 * Danach die Liste neu holen (der Server ist die Wahrheit: Stände, Zähler,
 * mit-erledigte Meldungen derselben Nachricht).
 */
async function meldungEntscheiden({ meldung, entscheidung, grund }) {
  try {
    await apiCall('chat.meldung_entscheiden', {
      meldung,
      entscheidung,
      grund: grund || undefined,
    })
    await meldungenLaden()
    meldungenEl.value?.auftragBeendet?.(meldung, '')
  } catch (fehler) {
    const zustand = zustandFuer({
      status: fehler?.status, excType: fehler?.exc_type || fehler?.name, angefragt: true,
    })
    meldungenEl.value?.auftragBeendet?.(meldung, fehlertext(fehler, { zustand }))
  }
}

// ── Finalize all ─────────────────────────────────────────────────────────────
/**
 * „Alle freigeben“/Ziehen — ehrliche Meldung (UI-R4b, Punkt 3).
 *
 * Vorher stand hier `${ids.length} Termine freigegeben` + „Im Kalender
 * ansehen“ — auch wenn nur EINE Stufe abgehakt war und die Termine noch auf
 * die nächste warteten. Der Server (R-12d) sagt jetzt je Termin, was gilt:
 * `festgelegt`, `weitergereicht` und `ergebnisse[id].naechste_stufe`.
 * Gemeldet wird `freigabeMeldung` (EINE Quelle), und der Kalender-Link
 * erscheint NUR, wenn wirklich Termine festgelegt sind.
 */
async function finalizeAll() {
  if (!board.value) return
  const ids = board.value.getStagingIds()
  if (ids.length === 0) return

  finalizing.value = true
  try {
    const antwort = await finalizeStagedEvents(ids)
    const meldung = sammelMeldung(antwort)
    // OP-UI-25: Nicht ungefragt in den Kalender springen — der Moderator
    // bleibt in der Moderation und bekommt die Moeglichkeit, den Kalender
    // anzusehen. Das gilt aber nur für Termine, die WIRKLICH im Kalender
    // stehen (festgelegt); wartende sind dort nicht zu sehen.
    showToast(
      meldung.text,
      meldung.ton,
      // „Im Kalender ansehen“ nur bei Terminen, die WIRKLICH dort stehen.
      meldung.festgelegt > 0 ? { text: 'Im Kalender ansehen', onClick: goToKalender } : null,
    )
    await board.value.reloadBoard()
    await zaehlerLaden()
  } catch (e) {
    showToast(e.message || 'Freigabe fehlgeschlagen', 'error')
  } finally {
    finalizing.value = false
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

/**
 * BEIDE Rechte aus EINER Antwort erfragen: `can_moderate` (Termine) und
 * `chat_moderieren` (Chat-Einstieg, CHAT-6-UI-3). Vorher entschied der
 * Einstieg über eine 403-Antwort der Liste — jetzt sagt es der Rechte-Kern.
 *
 * CHAT-6-UI-2 (SOLL 3): Ein Netz- oder Serverfehler ist KEINE Antwort „nein“.
 * Er wird als `fehler` zurückgegeben, damit die Seite die Fehlerseite mit
 * „Erneut versuchen“ zeigt statt der Sperrseite. Ein 403 dagegen IST die
 * Antwort „darf nicht“.
 *
 * @returns {Promise<{termine: boolean, chat: boolean, fehler: string}>}
 */
async function rechteAusSitzungLaden() {
  try {
    const info = await apiCall('diakronos.kronos.api.permissions.get_session_info')
    return {
      termine: !!info?.can_moderate,
      chat: info?.chat_moderieren === true,
      fehler: '',
    }
  } catch (e) {
    if (keineRechte(e)) return { termine: false, chat: false, fehler: '' }
    console.error('Session-Info konnte nicht geladen werden', e)
    return { termine: false, chat: false, fehler: fehlertext(e) }
  }
}

/**
 * Die Seite freigeben — EINSTIEG und Inhalt getrennt.
 *
 * ZWEI getrennte Rechte (Review CHAT-6 R1): „Termine prüfen“ (Kalender) und
 * „Meldungen aus dem Chat prüfen“ (HV/MV/GL bzw. Meldestelle). Keines
 * entscheidet über das andere — beide stehen in DERSELBEN Antwort
 * (`get_session_info`, CHAT-6-UI-3).
 *
 * ZUERST der Einstieg: ohne Chat-Recht geht KEIN Listen-Abruf hinaus (dann
 * ist die Liste die Antwort auf eine Frage, die niemand gestellt hat). Mit
 * Chat-Recht läuft die Arbeitsliste wie bisher — und ihre Antwort schreibt
 * den geteilten Merker (der geteilte Merker).
 *
 * Ein Netz-/Serverfehler der Sitzungs-Antwort ist keine Rechtelage: er steht
 * in `ladeFehler`, die Seite zeigt „Gerade nicht erreichbar“.
 */
async function rechteLaden() {
  checking.value = true
  ladeFehler.value = ''
  const lage = await rechteAusSitzungLaden()
  termineRecht.value = lage.termine
  canModerate.value = lage.termine
  chatRecht.value = lage.chat
  // MUSS 1 (Review R1): Ein „nein“ der Sitzungs-Antwort wird GEMERKT. Vorher
  // schrieb nur der 403 der Liste den Merker — seit CHAT-6-UI-3 kommt der
  // Einstieg aber aus `get_session_info`, also muss SEINE Antwort in den
  // geteilten Merker, sonst zeigte der Kalender weiter den Reiter. Ein Fehler
  // ist keine Antwort (`lage.fehler`) und schreibt deshalb nichts.
  if (!lage.fehler && !lage.chat) chatMerken({ recht: false, zahl: null })
  if (lage.fehler) ladeFehler.value = lage.fehler
  checking.value = false
  if (lage.fehler) return

  // Zahl „Zu prüfen“ (Reiter, Badge, Kopfzeile) — EINE Quelle: der Server.
  // Nur der Termine-Weg braucht sie.
  if (lage.termine) await zaehlerLaden()

  // Die Arbeitsliste NUR mit Chat-Recht — und VOR dem Öffnen des Reiters ist
  // sie die Seite (`zeigeChat` hängt an `chatRecht`).
  if (lage.chat) await meldungenLaden()
}

/** „Erneut versuchen“ auf der Fehlerseite (SOLL 3). */
async function erneutVersuchen() {
  termineRecht.value = null
  await rechteLaden()
}

onMounted(async () => {
  await rechteLaden()

  // Adresswechsel (Klick auf den Reiter am Kopf, Zurück/Vorwärts): der
  // Reiter folgt der Adresse.
  if (typeof window !== 'undefined') window.addEventListener('hashchange', reiterAusAdresseLesen)
})

onUnmounted(() => {
  if (typeof window !== 'undefined') window.removeEventListener('hashchange', reiterAusAdresseLesen)
})
</script>

<style scoped>
@keyframes mod-spin { to { transform: rotate(360deg); } }

.mod-zustand {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}
.mod-zustand--verweigert { min-height: 400px; }
.mod-zustand-box { text-align: center; color: var(--subtle); }
.mod-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--line);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: mod-spin 0.8s linear infinite;
  margin: 0 auto var(--sp-3);
}
.mod-zustand-text { font-size: var(--fs-14); margin: 0; }

.mod-verweigert { text-align: center; max-width: 380px; }
.mod-verweigert-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  background: var(--surface-2);
  color: var(--subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--sp-4);
}
.mod-verweigert-titel { font-size: var(--fs-h2); font-weight: var(--fw-fett); margin: 0 0 var(--sp-2); color: var(--text); }
.mod-verweigert-text { font-size: var(--fs-14); color: var(--muted); margin: 0 0 var(--sp-alt-20); line-height: 1.6; }

/* BF1-I: Gemeinsamer Seitenrahmen wie alle anderen Seiten (.dk-screen liefert
   die einheitlichen Raender). Nur die innere Anordnung bleibt flexibel. */
.dk-moderation { display: flex; flex-direction: column; }
/* UX3d: Kopf + Reiterleiste stehen randlos oben (wie im Kalender); erst der
   Inhalt der Tafel bekommt den Seitenrand. */
.dk-moderation-inhalt { min-width: 0; }
.dk-moderation-kopf { margin: calc(-1 * var(--pad)) calc(-1 * var(--pad)) 0; }
.dk-moderation-inhalt {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  padding-top: var(--sp-4);
  min-height: 0;
}
/* Aktionszeile: links der Rückweg (am Handy), rechts die Hauptaktion — genau
   EIN gefüllter Primärknopf je Ansicht (S1). Die Zahl steht als ruhiger Satz
   zwischen beiden; im Entwurf trägt sie der Reiter. */
.dk-moderation-aktionen {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--sp-3);
  margin: 0 0 var(--sp-3);
}
.dk-moderation-anzahl {
  margin-right: auto;
  font-size: var(--fs-14);
  color: var(--dk-text-muted);
  font-variant-numeric: var(--fs-tabular);
}

/* DEV-B2: Der Rückweg „‹ Kalender“ ist ein HANDY-Weg, kein Desktop-Element.
   Er trägt die Klasse seit UX3d, CSS hatte er nie — dadurch stand er auf
   jeder Breite neben den Reitern und „Alle freigeben“. Am Desktop führen die
   Reiter der Kopfzeile (Monat · Woche · Liste) zurück.
   „Handy“ = die EINE Handy-Lage der App (Klasse `.dk-app--handy`, gesetzt in
   App.vue aus `composables/handyLage.mjs`, DEV-B6) — KEINE eigene
   Breitenabfrage: ein Maus-Laptop mit 702 px bekommt keine Handy-Wege. */
.dk-moderation-mobile-back { display: none; }
.dk-app--handy .dk-moderation-mobile-back {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  /* Klickfläche K4: am Handy mindestens 44 px hoch. */
  min-height: 44px;
  padding: 0 var(--sp-2);
  color: var(--text);
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  text-decoration: none;
  border-radius: var(--radius-sm);
}
.dk-app--handy .dk-moderation-mobile-back:hover { color: var(--accent); }
.dk-app--handy .dk-moderation-mobile-back:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
/* Am Handy steht er allein links, die Zahl direkt dahinter — die Zeile
   bleibt zwischen Rückweg und „Alle freigeben“ getrennt (S3). */
.dk-app--handy .dk-moderation-anzahl { margin-right: auto; }

/* OP-ADMIN-18: kurze Erklärung, was die beiden Ablagen bedeuten. */
.dk-moderation-erklaerung {
  margin: 0 0 12px;
  font-size: var(--fs-14);
  line-height: 1.5;
  color: var(--dk-text-muted);
  max-width: 70ch;
}
</style>
