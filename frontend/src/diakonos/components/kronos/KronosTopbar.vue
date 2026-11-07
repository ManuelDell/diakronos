<template>
  <div class="kronos-kopf">
  <header class="kronos-header">
    <div class="header-left">
      <!-- UX3d-Review: im Vollbild der Prüf-Tafel fehlen alle Kalender-
           Bedienelemente (Seitenleiste, Heute, Blättern, rechte Leiste) —
           dort wären sie tote Schaltflächen. -->
      <template v-if="!pruefTafel">
      <!-- UXK-R9: Am Handy liegt die Kalender-Seitenleiste (Kalenderliste,
           CalDAV-Anleitung, Import) dauerhaft ausserhalb des Bildes. Dieser
           Knopf oeffnet sie — nur auf schmalen Bildschirmen sichtbar. -->
      <DkButton
        class="sidebar-toggle-btn"
        variant="secondary"
        size="md"
        aria-label="Meine Kalender und Hilfe anzeigen"
        title="Meine Kalender"
        @click="$emit('sidebarToggle')"
      >
        <span class="icon-menu" v-html="ICON_MENU"></span>
      </DkButton>
      <DkButton class="todaybutton" variant="secondary" size="md" aria-label="Zum heutigen Tag springen" title="Heute" @click="$emit('today')">
        <span class="today-label">Heute</span>
        <span class="icon-calendar-today" v-html="ICON_CALENDAR_TODAY"></span>
      </DkButton>
      </template>
    </div>

    <div class="header-center">
      <template v-if="!pruefTafel">
      <DkButton class="nav-btn prev-month" variant="secondary" size="md" aria-label="Vorheriger Monat" @click="$emit('prev')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_LEFT"></span>
      </DkButton>
      <DkButton class="nav-btn next-month" variant="secondary" size="md" aria-label="Nächster Monat" @click="$emit('next')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_RIGHT"></span>
      </DkButton>
      </template>
      <!-- UX2d3a: solange der Monatstitel fehlt, steht eine leere Stelle mit
           Breite — kein „Lade...“-Text, der springt. -->
      <span class="current-date"><span v-if="shortTitle">{{ shortTitle }}<span v-if="yearPart" class="date-year">&nbsp;{{ yearPart }}</span></span><span v-else class="date-platzhalter" aria-hidden="true"><span class="date-skelett"></span></span></span>
    </div>

    <div v-if="!pruefTafel" class="header-right">
      <DkButton
        id="resource-toggle-btn"
        class="resource-toggle-btn"
        :variant="isResourceView ? 'primary' : 'secondary'"
        size="md"
        :aria-pressed="isResourceView ? 'true' : 'false'"
        aria-label="Ressourcenplan anzeigen"
        title="Ressourcenplan"
        @click="onResourceToggle"
      >
        <span v-html="ICON_ROOM_VIEW"></span>
        <span class="resource-btn-label">Ressourcenplan</span>
      </DkButton>

      <select
        id="view-selector"
        class="view-dropdown"
        aria-label="Ansicht wählen"
        :value="displayView"
        @change="onViewChange"
      >
        <option value="dayGridMonth">Monat</option>
        <option value="timeGridWeek">Woche</option>
        <option value="timeGridDay">Tag</option>
        <option value="listMonth">Liste</option>
      </select>

      <div v-if="canWrite" class="toggle-container" data-toggle-group="edit-mode" aria-label="Bearbeitungs- / Ansichtsmodus">
        <button
          class="toggle-btn toggle-left"
          :class="{ active: viewMode === 'view' }"
          aria-label="Ansichtsmodus"
          title="Nur anzeigen"
          @click="$emit('viewModeChange', 'view')"
        >
          <span v-html="ICON_EYE"></span>
        </button>
        <button
          class="toggle-btn toggle-right"
          :class="{ active: viewMode === 'edit' }"
          aria-label="Bearbeitungsmodus"
          title="Termine verschieben / bearbeiten"
          @click="$emit('viewModeChange', 'edit')"
        >
          <span v-html="ICON_PENCIL"></span>
        </button>
      </div>
      <span v-else class="readonly-hinweis" title="Du kannst Termine nur lesen">
        <span v-html="ICON_EYE"></span>
        <span class="readonly-label">Nur lesen</span>
      </span>

      <!-- UX3d: „Zu prüfen“ ist KEIN eigener Knopf mehr in der Kopfzeile —
           es ist der vierte Reiter der Kalender-Leiste direkt unter dem Kopf
           (Entwurf A4: Monat · Woche · Liste · Zu prüfen (n)). Der Knopf
           rechts machte dieselbe Sache ein zweites Mal und war die einzige
           Stelle, an der die Zahl stand. -->
    </div>
  </header>

  <!-- UX3d: die Reiterleiste des Kalenders. Sie kommt aus `menue.kalenderReiter`
       (eine Quelle für Beschriftung, Reihenfolge und die Sichtbarkeit „nur
       für Moderatoren“).
       Sie steht AUCH auf der Seite „Zu prüfen“ (dort ist der vierte Eintrag
       der aktive): der Weg zurück zum Kalender muss sichtbar bleiben; der
       frühere Stummel-Knopf „Zurück zum Kalender“ entfällt dadurch. Nur im
       Vollbild der Prüf-Tafel (`pruefTafel`) fehlt sie — dort ersetzt das
       Brett die Ansicht, und ein Umschalter „Monat/Woche/Liste“ wäre eine
       tote Schaltfläche. Gerendert wird IMMER (v-if am inneren Element):
       ein `v-if` um die Komponente ließ die Reiter nach dem Wechsel auf
       „Zu prüfen“ gar nicht erst entstehen (im Wegwerf-Stack gemessen). -->
  <KalenderReiter
    class="kronos-reiter"
    :class="{ 'kronos-reiter--tafel': pruefTafel }"
    :options="reiter"
    :model-value="gewaehlterReiter"
    @waehlen="onReiterWaehlen"
  />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import DkButton from '../ui/DkButton.vue';
import KalenderReiter from './KalenderReiter.vue';
// UX3d: Reiterleiste und Sichtbarkeitsregel „nur Moderatoren“ aus EINER
// Quelle (dieselbe Liste prüft der Wächter-Test `ux3d-kalender-pruefen`).
import { kalenderReiter } from '../../menue.js';

const props = defineProps({
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  viewMode: { type: String, default: 'view' },
  canWrite: { type: Boolean, default: true },
  /** UX3d: Reiter „Zu prüfen“ zeigen (Moderator mindestens eines Kalenders). */
  canModerate: { type: Boolean, default: false },
  /** Zahl offener Prüfungen — `null` = unbekannt (dann ohne Zahl). */
  offeneZahl: { type: Number, default: null },
  /**
   * Der Kalender steht im Vollbild der Prüf-Tafel. Dann ist das Brett die
   * Ansicht: die Einträge „Monat/Woche/Liste“ sind ausgeblendet (tote
   * Schaltfläche), „Zu prüfen“ bleibt als aktive Markierung stehen.
   */
  pruefTafel: { type: Boolean, default: false },
  /** Aktiver Reiter: `kalender`, `pruefen` oder eine Kalender-Ansicht. */
  aktiverReiter: { type: String, default: 'kalender' },
});

const emit = defineEmits([
  'prev', 'next', 'today', 'viewChange', 'resourceToggle',
  'viewModeChange', 'sidebarToggle'
]);

const RESOURCE_VIEW_MAP = {
  dayGridMonth: 'resourceTimelineMonth',
  timeGridWeek: 'resourceTimelineWeek',
  timeGridDay:  'resourceTimelineDay',
  listMonth:    'resourceTimelineWeek',
};
const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP));

const displayView = ref('dayGridMonth');
const shortTitle = computed(() => {
  // Monatsteil ohne Jahr, egal ob die Quelle „Oktober 2026“ oder „Oktober2026“ liefert.
  return (props.dateTitle || '').replace(/\s*\d{4}\s*$/g, '').trim()
})
const yearPart = computed(() => {
  const m = (props.dateTitle || '').match(/\d{4}(?!.*\d{4})/)
  return m ? m[0] : ''
})
const lastNormalView = ref('dayGridMonth');
const isResourceView = computed(() => RESOURCE_VIEWS.has(props.currentView));

// UX3d: Die Reiterleiste (Monat · Woche · Liste · „Zu prüfen (n)“). Welche
// Einträge erscheinen, entscheidet `menue.kalenderReiter` — hier wird nur
// durchgereicht, was die Seite über Rechte und Kennzahl weiß. Die Zahl bleibt
// `null`, solange sie unbekannt ist (kein erfundenes „0“).
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

// Welcher Eintrag ist aktiv? Der Reiter ist eine EIGENE Seite (`pruefen`);
// im Kalender entscheidet die Ansicht. Ressourcenansichten (Timeline) gehören
// zur Ansicht, aus der sie geöffnet wurden — das ist `lastNormalView`.
const gewaehlterReiter = computed(() => {
  if (props.aktiverReiter === 'pruefen') return 'pruefen'
  const sicht = RESOURCE_VIEWS.has(props.currentView) ? lastNormalView.value : props.currentView
  if (sicht === 'timeGridWeek') return 'woche'
  if (sicht === 'timeGridDay') return 'tag'
  if (sicht === 'listMonth') return 'liste'
  return 'monat'
})

/**
 * Klick auf einen Reiter: „Zu prüfen“ ist ein Link (navigiert der Browser).
 * Ansichten derselben Seite wechselt diese Komponente — über denselben Weg
 * wie das frühere Auswahlfeld (`viewChange`), damit Kalender und Kopfzeile
 * eine Wahrheit behalten.
 */
function onReiterWaehlen(r) {
  if (!r || r.ansicht !== true) return
  onViewChange({ target: { value: r.aktiv } })
}

const ICON_CHEVRON_LEFT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M15 6l-6 6l6 6"/></svg>`;
const ICON_CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M9 6l6 6l-6 6"/></svg>`;
const ICON_EYE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0-4 0"/><path d="M21 12c-2.4 4-5.4 6-9 6c-3.6 0-6.6-2-9-6c2.4-4 5.4-6 9-6c3.6 0 6.6 2 9 6"/></svg>`;
const ICON_PENCIL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 20h4l10.5-10.5a2.828 2.828 0 1 0-4-4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>`;
const ICON_ROOM_VIEW = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M12 4l0 16"/></svg>`;
const ICON_MENU = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>`;
const ICON_CALENDAR_TODAY = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><rect x="4" y="5" width="16" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="4" y1="11" x2="20" y2="11"/><line x1="8" y1="16" x2="8.01" y2="16"/></svg>`;

watch(() => props.currentView, (newVal) => {
  if (!RESOURCE_VIEWS.has(newVal)) {
    displayView.value = newVal;
    lastNormalView.value = newVal;
  }
});

function onViewChange(e) {
  const val = e.target.value;
  lastNormalView.value = val;
  emit('viewChange', val);
}

function onResourceToggle() {
  if (isResourceView.value) {
    emit('viewChange', lastNormalView.value);
  } else {
    lastNormalView.value = displayView.value;
    const resourceView = RESOURCE_VIEW_MAP[displayView.value] || 'resourceTimelineWeek';
    emit('viewChange', resourceView);
  }
}

// UXK-R16: Der frühere Strg+F-Handler fing die Browsersuche ab, öffnete aber
// nichts. Entfernt — die normale Browsersuche funktioniert dadurch wieder.
// UX3d: Das frühere `loadDeskLink()` (Sitzungsinfo + Kennzahl für den
// „Zu prüfen“-Knopf der Kopfzeile) ist entfallen: das Recht kommt jetzt im
// Boot-Objekt (`can_moderate`) und die Kennzahl von der Seite — sonst
// entstünde die Zahl an zwei Stellen und könnte auseinanderlaufen.
</script>

<style scoped>
/* UX3d: Kopf + Reiterleiste als EIN Block mit der Trennlinie unten. Vorher
   trug die Kopfzeile selbst die `border-bottom`; jetzt sitzt die Linie unter
   den Reitern, damit Kopf und Reiter zusammen wie der Kopf der Seite wirken
   (Entwurf A4). */
.kronos-kopf {
  flex: 0 0 auto;
  /* Die Reiterleiste gehört in den Kasten: ohne diese Zeile konnte der
     umbrechende Kopf den verfügbaren Platz auffressen und die Reiter wurden
     beschnitten. */
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  /* Stapelkontext: die Reiterzeile liegt UNTER dem Kopf und muss ihn beim
     Scrollen überdecken. Ohne eigenes `z-index` malte der Browser sie unter
     die (im DOM frühere) Kopfzeile — am Handy lag der obere Teil der Reiter
     unsichtbar hinter „Heute/Datum/Auswahlfeld“ (im Wegwerf-Stack gemessen:
     ein Klick auf „Zu prüfen“ traf das Auswahlfeld). */
  position: relative;
  z-index: 1;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.kronos-reiter {
  margin: 0;
  padding: 0 var(--sp-4);
}
/* Vollbild der Prüf-Tafel: nur der aktive Eintrag steht in der Leiste — die
   Unterlinie der ganzen Leiste wäre dann eine Linie ohne Inhalt. */
.kronos-reiter--tafel { border-bottom-color: transparent; }
/* FIX-6: Die Reiterleiste rückt am Handy bündig mit dem Kopf (dessen
   Seitenrand dort schmaler ist) — LAYOUT, also nur die Breite, nie der
   Zeigertyp. */
@media (max-width: 720px) {
  .kronos-reiter { padding: 0 var(--sp-3); }
}
.kronos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  /* UX3d: `min-height` allein ließ die Kopfzeile am Handy auf der festen
     Zeilenhöhe stehen, während sie ZWEI Zeilen umbrach (`flex-wrap`) — die
     zweite Zeile (Auswahlfeld, Augen/Stift) ragte aus dem Kasten und legte
     sich über die Reiterleiste darunter. `height: auto` lässt den Kasten
     mitwachsen; am Desktop ist er ohnehin genau eine Zeile hoch. */
  height: auto;
  min-height: var(--topbar-h);
  padding: 8px var(--sp-4);
  background: var(--surface);
  gap: var(--gap);
  /* UXK-008: Auf schmalen Bildschirmen darf die Kopfzeile nicht aus dem
     Fenster laufen — die Umbruchfaehigkeit ist die Grundlage dafuer, dass
     Stift und „Moderation“ am Handy erreichbar bleiben. */
  flex-wrap: wrap;
}
.header-left,
.header-center,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  /* min-width:0 erlaubt es den Flexkindern zu schrumpfen statt die Zeile zu
     sprengen (Vorbedingung fuer den Umbruch). */
  min-width: 0;
}
.header-center {
  flex: 1;
  justify-content: center;
}
/* UXK-R9: Der Umschalter fuer die Kalender-Seitenleiste wird nur am Handy
   gebraucht; am Desktop ist die Leiste ohnehin sichtbar. */
.sidebar-toggle-btn { display: none; }
.icon-calendar-today { display: none; }
.nav-btn {
  padding: 0;
  width: 32px;
}
.icon-chevron {
  display: inline-flex;
  align-items: center;
}
.current-date {
  font-size: var(--fs-h3);
  font-weight: var(--fw-fett);
  min-width: 0;   /* UXK-008: vorher 120px — sprengte die Zeile am Handy */
  text-align: center;
  color: var(--text);
}
/* UX2d3a: Platzhalter für den noch fehlenden Monatstitel — gleiche Höhe wie
   eine Textzeile, damit die Leiste beim Eintreffen des Titels nicht springt. */
.date-platzhalter {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  min-height: 1em;
}
.date-skelett {
  display: block;
  width: 9ch;
  height: 0.75em;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}
.resource-toggle-btn {
  gap: 6px;
}
.view-dropdown {
  height: var(--control-h);
  padding: 0 24px 0 10px;
  font-size: var(--fs-14);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  color: var(--text);
}
.toggle-container {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  /* UX1c/C3 (Nacharbeit 07.11.): Mindestbreite kommt aus dem Token
     (Desktop 36 px ist zu schmal fuer ein 44-px-Tippziel; Konzept K4:
     `--control-h`, am groben Zeiger 44 px). Vorher stand hier das Literal
     36px, das am Handy jede Trefferflaeche auf 36 px festnagelte. */
  min-width: var(--control-h);
  height: var(--control-h);
  background: var(--surface);
  border: none;
  cursor: pointer;
  color: var(--muted);
}
.toggle-btn.active {
  background: var(--primary);
  color: var(--primary-ink);
}
.readonly-hinweis {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: var(--control-h);
  padding: 0 10px;
  font-size: var(--fs-14);
  color: var(--muted);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}

/* UX3d: Die Styles des früheren „Zu prüfen“-Knopfes in der Kopfzeile
   (`.moderation-knopf`, `.moderation-btn-label`, `.moderation-btn-zahl`) sind
   entfallen — dieser Eintrag ist jetzt der vierte Reiter der Kalender-Leiste
   (components/kronos/KalenderReiter.vue, Zähler dort als `.kal-reiter-zahl`
   mit denselben Status-Tokens).
   Der Kommentar MUSS geschlossen werden: ein offenes Kommentierende
   verschluckte die
   folgende @media-Regel (der Browser verwarf sie still — im Wegwerf-Stack
   gemessen: die Bedienzeile blieb am Handy einzeilig und legte sich über die
   Reiter). Wächter: `ux3d-kalender-pruefen.test.mjs`, „CSS-Kommentare sind
   geschlossen“. */

/* UXK-008: Auf schmalen Bildschirmen umbrechen Kopfzeile und Bedienelemente
   so, dass Auswahl-Umschalter, Stift „Bearbeiten“ und „Moderation“ im Bild
   bleiben. „Heute“ wird zum Symbol, die Datumsanzeige darf schrumpfen. */
@media (max-width: 768px) {
  .kronos-header {
    /* Zwei Zeilen: oben Navigation/Datum, unten die Bedienelemente. */
    row-gap: 6px;
  }
  .header-left { order: 1; }
  .header-center { order: 2; flex: 1 1 auto; }
  .header-right {
    order: 3;
    /* `1 0 100%` allein ist ein `flex-basis`-Startwert: ist der Inhalt breiter
       als das Fenster, wuchs die Basis mit und die Zeile ragte über den Kopf
       hinaus — das Auswahlfeld lag dann (gemessen 390 px) über der
       Reiterzeile darunter. `0 0 100%` hält die Zeile am Fenster. */
    flex: 0 0 100%;
    min-width: 0;
    justify-content: flex-end;
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .sidebar-toggle-btn { display: inline-flex; }
  .today-label { display: none; }
  .icon-calendar-today { display: inline-flex; align-items: center; }
  .current-date {
    font-size: var(--fs);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

</style>
<style scoped>
@media (max-width: 720px) {
  .date-year { display: none; }
  .resource-toggle-btn { display: none; }
  .view-dropdown { font-size: var(--fs-xs); padding: 4px 6px; }
}
</style>
