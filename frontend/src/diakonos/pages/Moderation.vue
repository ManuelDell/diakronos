<template>
  <!-- Loading state -->
  <div v-if="checking" class="dk-screen dk-screen-enter mod-zustand">
    <!-- UX2d3b (Review UX2d3a/B): ruhiger Platzhalter statt des Satzes
         „Berechtigung wird geprüft…“ — der Umriss zeigt, dass etwas kommt. -->
    <div class="mod-zustand-box">
      <DkSkelett form="zeilen" :anzahl="3" text="Berechtigung wird geprüft" />
    </div>
  </div>

  <!-- Forbidden screen (exact match to original behavior) -->
  <div v-else-if="!canModerate" class="dk-screen dk-screen-enter mod-zustand mod-zustand--verweigert">
    <div class="mod-verweigert">
      <div class="mod-verweigert-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </div>
      <h2 class="mod-verweigert-titel">Zugriff verweigert</h2>
      <p class="mod-verweigert-text">
        Du hast keine Berechtigung, Termine zu prüfen.<br>
        Nur Moderatoren der Kalender können Termine freigeben.
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
      :canModerate="true"
      :offeneZahl="prüfZahl > 0 ? prüfZahl : null"
      aktiverReiter="pruefen"
      pruefTafel
    />

    <div class="dk-moderation-inhalt">
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ModerationBoard from '../components/kronos/ModerationBoard.vue'
import ModerationAenderungen from '../components/kronos/ModerationAenderungen.vue'
import ModerationAntraege from '../components/kronos/ModerationAntraege.vue'
import KronosTopbar from '../components/kronos/KronosTopbar.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkSymbol from '../components/ui/DkSymbol.vue'
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
onMounted(async () => {
  try {
    const info = await apiCall('diakronos.kronos.api.permissions.get_session_info')
    canModerate.value = !!info?.can_moderate
  } catch (e) {
    console.error('Session-Info konnte nicht geladen werden', e)
    canModerate.value = false
  } finally {
    checking.value = false
  }

  // Zahl „Zu prüfen“ (Reiter, Badge, Kopfzeile) — EINE Quelle: der Server.
  if (canModerate.value) await zaehlerLaden()
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
