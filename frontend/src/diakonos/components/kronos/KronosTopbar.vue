<template>
  <div class="kronos-kopf">
    <header class="kronos-header">
      <div class="header-left">
        <!-- UX3i (Entwurf A4): EINE Kopfzeile.
             Links: die Reiter (Monat · Woche · Liste · Zu prüfen (n)); am Handy
             davor unverändert der Umschalter der Kalenderliste.
             Rechts: „Kalender“ (Auswahl, mit Zähler) · „Heute“ · ‹ › ·
             der EINE Primärknopf „+ Termin anlegen“ · ein „⋯“-Menü für
             Ressourcenplan / Verwalten / Importieren / Hilfe.
             Das Auswahlfeld „Monat“ ist entfallen — die Reiter bestimmen die
             Ansicht (vorher gab es sie zweimal). -->
        <template v-if="!pruefTafel">
          <!-- UXK-R9: Am Handy liegt die Kalenderliste (Kalenderliste,
               CalDAV-Anleitung, Import) ausserhalb des Bildes. Dieser Knopf
               oeffnet sie — nur auf schmalen Bildschirmen sichtbar. -->
          <DkButton
            class="sidebar-toggle-btn"
            variant="secondary"
            aria-label="Meine Kalender und Hilfe anzeigen"
            title="Meine Kalender"
            @click="$emit('sidebarToggle')"
          >
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>
            </template>
          </DkButton>
        </template>
        <!-- Die Reiterleiste steht LINKS in der Kopfzeile (A4). Sie kommt aus
             `menue.kalenderReiter` — eine Quelle für Beschriftung,
             Reihenfolge und „nur für Moderatoren“. Gerendert wird IMMER
             (ein v-if an der Komponente ließ sie nach dem Wechsel auf
             „Zu prüfen“ gar nicht erst entstehen, im Wegwerf-Stack gemessen);
             im Vollbild der Prüf-Tafel liefert `reiter` nur den aktiven
             Eintrag — dort wären „Monat/Woche/Liste“ tote Schaltflächen. -->
        <KalenderReiter
          class="kronos-reiter"
          :class="{ 'kronos-reiter--tafel': pruefTafel }"
          :options="reiter"
          :model-value="gewaehlterReiter"
          @waehlen="onReiterWaehlen"
        />
      </div>

      <div v-if="!pruefTafel" class="header-right">
        <!-- A4: Kalenderauswahl als Popover, Zähler der eingeblendeten. -->
        <DkButton
          class="kalender-auswahl-btn"
          data-kalender-ausloeser="1" data-kalender-sichtbar="1"
          variant="secondary"
          :aria-expanded="auswahlOffen ? 'true' : 'false'"
          aria-haspopup="dialog"
          aria-label="Kalender auswählen"
          title="Meine Kalender ein-/ausblenden"
          @click="$emit('kalenderAuswahlUmschalten')"
        >
          <template #icon><DkSymbol name="kalender" :groesse="16" /></template>
          <span class="kalender-auswahl-label">Kalender</span>
          <span v-if="eingeblendet !== null" class="kalender-auswahl-zahl" aria-hidden="true">{{ eingeblendet }}</span>
        </DkButton>

        <!-- „Heute“: am Desktop mit Beschriftung. Am Handy ist die Beschriftung
             ausgeblendet — dort zeichnet die Schaltfläche bisher NICHTS (leerer
             Knopf, Review 07.11.). Jetzt steht dort das Kalender-Symbol; der
             Name bleibt als aria-label und Tooltip. -->
        <DkButton class="todaybutton" variant="secondary" aria-label="Zum heutigen Tag springen" title="Heute" @click="$emit('today')">
          <template #icon><DkSymbol name="kalender" class="today-symbol" :groesse="16" /></template>
          <span class="today-label">Heute</span>
        </DkButton>

        <DkButton class="nav-btn prev-month" variant="secondary" aria-label="Vorheriger Zeitraum" title="Zurück" @click="$emit('prev')">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M15 6l-6 6 6 6"/></svg>
          </template>
        </DkButton>
        <DkButton class="nav-btn next-month" variant="secondary" aria-label="Nächster Zeitraum" title="Weiter" @click="$emit('next')">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 6l6 6-6 6"/></svg>
          </template>
        </DkButton>

        <!-- Der EINE Primärknopf je Ansicht (Regel UX1h / A4). Ohne
             Schreibrecht gibt es ihn nicht (UXK-R10) — dann steht der ruhige
             Hinweis „Nur lesen“ statt eines toten Knopfes. -->
        <DkButton
          v-if="canWrite"
          class="termin-anlegen-btn"
          variant="primary"
          data-primaer="1"
          aria-label="Termin anlegen"
          @click="$emit('terminAnlegen')"
        >
          <template #icon>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          </template>
          Termin anlegen
        </DkButton>
        <span v-else class="readonly-hinweis" title="Du kannst Termine nur lesen">
          <DkSymbol name="ansehen" :groesse="16" />
          <span class="readonly-label">Nur lesen</span>
        </span>

        <!-- A4: alles Seltene in EIN Menü — „Ressourcenplan“, „Kalender
             verwalten“, „Kalender importieren“, „Hilfe & Infos“. System-
             symbole aus dem Vorrat, keine Emoji. -->
        <DkAktionen
          kennung="kalender-kopf"
          :eintraege="menue"
          label="Weitere Kalender-Aktionen"
          menue-label="Weitere Kalender-Aktionen"
          @aktion="onMenueAktion"
        />
      </div>
    </header>
  </div>
</template>

<script setup>
/**
 * KronosTopbar — die Kopfzeile des Kalenders (Entwurf A4, UX3i).
 *
 * Aufbau: EINE Zeile. Links die Reiter, rechts die Werkzeuge in der
 * Reihenfolge „Kalender · Heute · ‹ › · + Termin anlegen · ⋯“. Zwei frühere
 * Bedienelemente sind ENTFALLEN:
 *
 *   * das Auswahlfeld „Monat“ — die Reiter bestimmen die Ansicht, das Feld
 *     war ein zweiter Weg zu demselben Zustand;
 *   * der Umschalter Ansehen/Bearbeiten — Begründung im Kartenkommentar von
 *     UX3i: Bearbeiten ist über den Klick auf einen Termin und über
 *     „Termin anlegen“ erreichbar; Ziehen/Ändern im Raster ist bei
 *     bestehendem Schreibrecht immer möglich (die Seite schaltet es frei),
 *     und der gefüllte Umschalter war ein zweiter Hauptknopf neben
 *     „Termin anlegen“ (Regel: genau ein Primärknopf je Ansicht).
 *
 * Rechte und Kennzahlen kommen von der Seite; hier wird nichts entschieden.
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import KalenderReiter from './KalenderReiter.vue'
// UX3d/UX3i: Reiterleiste und Sichtbarkeitsregel „nur Moderatoren“ aus EINER
// Quelle (dieselbe Liste prüfen die Wächter-Tests ux3d und ux3i).
import { kalenderReiter } from '../../menue.js'
import { kalenderMenue } from './kalenderRechte.mjs'

const props = defineProps({
  /** Monatstitel der Seite (in A4 steht er im Kartenkopf, nicht hier). */
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  /** UXK-R10: mindestens ein Kalender mit Schreibrecht. */
  canWrite: { type: Boolean, default: true },
  /** UX3d: Reiter „Zu prüfen“ zeigen (Moderator mindestens eines Kalenders). */
  canModerate: { type: Boolean, default: false },
  /** Zahl offener Prüfungen — `null` = unbekannt (dann ohne Zahl). */
  offeneZahl: { type: Number, default: null },
  /** Zahl der eingeblendeten Kalender (Zähler am Knopf „Kalender“). */
  eingeblendet: { type: Number, default: null },
  /** Kalenderauswahl (Popover) ist offen. */
  auswahlOffen: { type: Boolean, default: false },
  /**
   * Darf die Person Kalender verwalten/importieren? Die Seite entscheidet das
   * aus `get_current_user_context` (Administrator ODER Kalenderadministrator)
   * — die Kopfzeile prüft keine Rollen selbst (eine Quelle, siehe
   * `kalenderRechte.mjs`).
   */
  istKalenderAdmin: { type: Boolean, default: false },
  /**
   * Lesemodus (`true`, Standard wie vor UX3i) oder Bearbeiten. Der Umschalter
   * steht dezent im „⋯“-Menü; gefüllte Knöpfe bleiben der Hauptaktion
   * vorbehalten (Regel UX1h).
   */
  lesemodus: { type: Boolean, default: true },
  /**
   * Der Kalender steht im Vollbild der Prüf-Tafel. Dann ist das Brett die
   * Ansicht: die Einträge „Monat/Woche/Liste“ sind ausgeblendet (tote
   * Schaltfläche), „Zu prüfen“ bleibt als aktive Markierung stehen.
   */
  pruefTafel: { type: Boolean, default: false },
  /** Aktiver Reiter: `kalender`, `pruefen` oder eine Kalender-Ansicht. */
  aktiverReiter: { type: String, default: 'kalender' },
})

const emit = defineEmits([
  'prev', 'next', 'today', 'viewChange', 'resourceToggle',
  'sidebarToggle', 'kalenderAuswahlUmschalten', 'terminAnlegen', 'hilfe',
  // Nacharbeit 07.11.: Lesemodus umschalten und die eigenen abgelehnten
  // Termine öffnen (beides aus dem „⋯“-Menü).
  'lesemodusWechsel', 'abgelehnteTermine',
])

const RESOURCE_VIEW_MAP = {
  dayGridMonth: 'resourceTimelineMonth',
  timeGridWeek: 'resourceTimelineWeek',
  timeGridDay:  'resourceTimelineDay',
  listMonth:    'resourceTimelineWeek',
}
const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP))

const lastNormalView = computed(() => {
  const v = props.currentView
  return RESOURCE_VIEWS.has(v) ? 'dayGridMonth' : v
})

// UX3d: Reiterleiste — welche Einträge erscheinen, entscheidet
// `menue.kalenderReiter`. Die Zahl bleibt `null`, solange sie unbekannt ist
// (kein erfundenes „0“).
const reiter = computed(() => {
  const liste = kalenderReiter({
    can_moderate: props.canModerate === true,
    offeneZahl: props.offeneZahl,
  })
  // Vollbild der Prüf-Tafel: keine Ansichts-Umschalter, nur der aktive Reiter
  // (er ist ein Link auf sich selbst — sichtbar als „hier bist du“).
  if (props.pruefTafel) return liste.filter(r => r.ansicht !== true)
  return liste
})

// Welcher Eintrag ist aktiv? „Zu prüfen“ ist eine EIGENE Seite; im Kalender
// entscheidet die Ansicht. Ressourcenansichten (Timeline) gehören zur
// Ansicht, aus der sie geöffnet wurden — das ist `lastNormalView`.
const gewaehlterReiter = computed(() => {
  if (props.aktiverReiter === 'pruefen') return 'pruefen'
  const sicht = lastNormalView.value
  if (sicht === 'timeGridWeek') return 'woche'
  if (sicht === 'timeGridDay') return 'tag'
  if (sicht === 'listMonth') return 'liste'
  return 'monat'
})

/**
 * Klick auf einen Reiter: „Zu prüfen“ ist ein Link (navigiert der Browser).
 * Ansichten derselben Seite wechselt diese Komponente über denselben Weg wie
 * das frühere Auswahlfeld (`viewChange`), damit Kalender und Kopfzeile eine
 * Wahrheit behalten.
 */
function onReiterWaehlen(r) {
  if (!r || r.ansicht !== true) return
  emit('viewChange', r.aktiv)
}

// A4: das „⋯“-Menü. Symbolnamen kommen aus dem Vorrat (`symbole.mjs`).
// Nacharbeit 07.11.: Welche Einträge erscheinen, entscheidet EINE Funktion
// (`kalenderRechte.kalenderMenue`) — Verwalten/Import nur mit der Rolle
// „Administrator“ ODER „Kalenderadministrator“ (wie bisher in der
// Kalenderliste), „Bearbeiten“ nur mit Schreibrecht, „Abgelehnte Termine“ für
// alle (die Daten liefert der Server, er liefert nur die eigenen).
const menue = computed(() => kalenderMenue({
  istKalenderAdmin: props.istKalenderAdmin === true,
  hatSchreibrecht: props.canWrite === true,
  lesemodus: props.lesemodus !== false,
}))

/** DkAktionen meldet `{ eintrag, index }` — hier wird nur das Ereignis gebraucht. */
function onMenueAktion(ereignis) {
  const eintrag = ereignis && ereignis.eintrag ? ereignis.eintrag : ereignis
  if (!eintrag) return
  if (eintrag.key === 'ressourcenplan') {
    emit('resourceToggle')
  } else if (eintrag.key === 'hilfe') {
    emit('hilfe')
  } else if (eintrag.key === 'bearbeiten') {
    // Der Eintrag heißt nach der HANDLUNG, die er ermöglicht: im Lesemodus
    // schaltet er das Bearbeiten ein und umgekehrt.
    emit('lesemodusWechsel', props.lesemodus === true)
  } else if (eintrag.key === 'abgelehnte') {
    emit('abgelehnteTermine')
  }
  // „Kalender verwalten“ / „Kalender importieren“ sind echte Links
  // (`href` in `kalenderRechte.mjs`) — der Browser navigiert.
}
</script>

<style scoped>
/* Kopf + Reiter als EIN Block. Die frühere Trennlinie unter der Leiste fällt
   weg (A4: die Karte trennt sich über Fläche und Schatten, nicht über eine
   Linie — Prinzip Ä2). */
.kronos-kopf {
  flex: 0 0 auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
}
.kronos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* UX3d: `min-height` allein ließ die Kopfzeile am Handy auf der festen
     Zeilenhöhe stehen, während sie ZWEI Zeilen umbrach (`flex-wrap`) — die
     zweite Zeile ragte aus dem Kasten und legte sich über die Reiterleiste
     darunter. `height: auto` lässt den Kasten mitwachsen. */
  height: auto;
  min-height: var(--control-h);
  padding: var(--sp-2) 0;
  gap: var(--sp-4);
  /* UXK-008: Auf schmalen Bildschirmen darf die Kopfzeile nicht aus dem
     Fenster laufen — die Umbruchfähigkeit ist die Grundlage dafür, dass die
     Werkzeuge am Handy erreichbar bleiben. */
  flex-wrap: wrap;
}
.header-left,
.header-right {
  display: flex;
  align-items: center;
  /* Innerhalb einer Gruppe gehört zusammen (Prinzip S3): 8 px. */
  gap: var(--sp-2);
  /* min-width:0 erlaubt es den Flexkindern zu schrumpfen statt die Zeile zu
     sprengen (Vorbedingung fuer den Umbruch). */
  min-width: 0;
}
.header-right { margin-left: auto; }

/* Die Reiterleiste sitzt im Kopf und trägt dort KEINE eigene Unterlinie
   (A4: Reiter + Werkzeuge stehen auf einer Linie). */
.kronos-reiter { margin: 0; border-bottom: 0; padding: 0; }
.kronos-reiter--tafel { margin: 0; }

/* A4: „Kalender“ trägt einen Zähler; er steht als ruhige Zahl neben dem
   Namen, nicht als Abzeichen mit eigener Fläche. */
.kalender-auswahl-zahl {
  min-width: var(--sp-4);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.kalender-auswahl-btn[aria-expanded="true"] {
  background: var(--surface-hover);
  border-color: var(--line-strong);
}

/* Symbolknöpfe ‹ › : quadratisch, Klickfläche --control-h (bei
   Fingerbedienung 44 px, siehe unten). */
.nav-btn { width: var(--control-h); padding: 0; }
/* UXK-R9: Der Umschalter für die Kalender-Seitenleiste wird nur am Handy
   gebraucht; am Desktop ist die Leiste ohnehin sichtbar. */
.sidebar-toggle-btn { display: none; }
.readonly-hinweis {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  height: var(--filter-h);
  padding: 0 var(--sp-3);
  font-size: var(--fs);
  color: var(--muted);
}

/* ── Handy (≤ 720 px): die bisherige Anordnung bleibt ─────────────────────
   UX3i ändert nur den Desktop; A10 (Mobil-Kalender) ist eine eigene Karte.
   Reihenfolge und Erreichbarkeit bleiben erhalten, nichts wird kleiner als
   44 px (K4). */
@media (max-width: 720px) {
  .kronos-header { row-gap: var(--sp-2); }
  .header-left { order: 1; flex: 1 1 auto; }
  .header-right {
    order: 3;
    /* `0 0 100%` hält die Zeile am Fenster (siehe UX3d: `1 0 100%` wuchs mit
       dem Inhalt und ragte über den Kopf hinaus). */
    flex: 0 0 100%;
    /* UX3i (Review): KEIN `margin-left: auto` in dieser Zeile — der
       automatische Rand verbraucht am Handy die ganze freie Breite und die
       Werkzeuge rutschten aus dem Bild (gemessen 390 px: „Termin anlegen“
       und „⋯“ hinter dem Rand). Am Desktop bleibt er (siehe oben). */
    margin-left: 0;
    min-width: 0;
    justify-content: flex-end;
    flex-wrap: wrap;
    row-gap: var(--sp-2);
  }
  /* Am Handy hat die Reiterleiste ihre eigene Zeile: sie soll volle Breite
     bekommen und nicht neben dem Menü-Knopf umbrechen. */
  .header-left { flex-wrap: wrap; }
  .today-label { display: none; }
  .todaybutton { width: var(--control-h); padding: 0; }
  /* Ohne Beschriftung muss das Symbol stehen — sonst wäre der Knopf leer. */
  .today-symbol { display: inline-flex; }
  /* Am Handy stehen die Werkzeuge platzsparend: Icon-Knöpfe behalten ihr
     aria-label, „Termin anlegen“ bleibt der eine Primärknopf. */
  .termin-anlegen-btn { width: var(--control-h); padding: 0; }
  .termin-anlegen-btn :deep(.dk-ui-btn-label) { display: none; }
  .kalender-auswahl-label { display: none; }
  .kronos-reiter { flex: 1 1 auto; }
}
/* Der Umschalter der Kalenderliste gehoert zur Handy-Lage der Seite
   (dieselbe Grenze wie kronos.css: die Liste ist dort ein Overlay). Er wird
   NUR hier geschaltet — eine Grenze, nicht zwei. */
@media (max-width: 720px) {
  .sidebar-toggle-btn { display: inline-flex; }
}
@media (pointer: coarse) {
  .nav-btn,
  .todaybutton,
  .termin-anlegen-btn,
  .sidebar-toggle-btn { height: 44px; }
  .nav-btn,
  .todaybutton,
  .termin-anlegen-btn { width: 44px; }
}
</style>
