<template>
  <aside class="kronos-sidebar" :class="{ open: open }">
    <!-- OP-UI-11: Die Kalenderliste ersetzt nicht mehr das Hauptmenü. Der
         Kopf der Leiste ist jetzt eine Überschrift mit Schließen-Knopf;
         „Zur Hauptnavigation“ entfällt (das Hauptmenü steht ohnehin links). -->
    <button type="button" class="kronos-back-btn" @click="$emit('close')" :title="'Kalenderliste schließen'">
      <div class="kronos-back-icon" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
      </div>
      <div class="kronos-back-text">
        <span class="kronos-back-name">Kalender</span>
        <span class="kronos-back-sub">Liste ein-/ausklappen</span>
      </div>
    </button>
    <!-- UXK-R9: Am Handy ist die Leiste ein Overlay; dieser Knopf schliesst
         sie wieder, ohne dass man den Kalender verlassen muss. -->
    <button
      type="button"
      class="kronos-sidebar-close"
      aria-label="Kalenderliste schließen"
      @click="$emit('close')"
    ><DkSymbol name="abbrechen" :groesse="18" /></button>
    <div class="sidebar-divider"></div>

    <div class="sidebar-calenderlist-section">
      <h4 class="sidebar-title">Meine Kalender</h4>
      <DkSkelett v-if="store.loading.value" kurz form="zeilen" :anzahl="3" text="Kalender werden geladen" />
      <!-- ON-4 (H3, dasselbe Muster wie die Mitgliederliste): Gibt es noch
           GAR KEINEN Kalender, wird der Einstieg angeboten; sind nur keine
           freigegeben, bleibt der knappe Hinweis (Rechte, nicht Einrichtung).
           `kalenderLeerzustand` entscheidet — ein Test wacht darüber. -->
      <div v-else-if="store.availableCalendars.value.length === 0" class="ksb-leer">
        <p class="ksb-hinweis">{{ kalenderLeer.titel }}</p>
        <p v-if="kalenderLeer.text" class="ksb-hinweis ksb-hinweis--klein">{{ kalenderLeer.text }}</p>
        <a v-if="kalenderLeer.ziel" :href="kalenderLeer.ziel" class="ksb-leer-link">
          {{ kalenderLeer.zielText }}
        </a>
      </div>
      <template v-else>
        <div
          v-for="cal in store.availableCalendars.value"
          :key="cal.name"
          class="calendar-item"
          :style="{ '--calendar-color': sichereFarbe(cal.color) || 'var(--primary)' }"
        >
          <input
            type="checkbox"
            :id="'cal-' + cal.name"
            v-model="selectedNames"
            :value="cal.name"
            @change="onCalendarToggle"
          />
          <label :for="'cal-' + cal.name">{{ cal.title || cal.name }}</label>
          <!-- UX3i (A4): „Eintragen erlaubt“ nur noch als dezentes Symbol mit
               Tooltip. Vorher stand der Satz in JEDER Zeile und lief bei
               „Gemeindeleben“ über den Rand der Leiste. -->
          <span v-if="cal.write" class="ksb-recht-hinweis" title="Du darfst hier Termine eintragen"
                aria-label="Eintragen erlaubt" role="img">
            <DkSymbol name="stift" :groesse="14" />
          </span>
        </div>
      </template>
    </div>

    <!-- UX1e: EIN Knopf-System — die beiden Link-Knöpfe der Leiste waren
         eigene Links mit Eigenklasse und sind jetzt DkButton (gleiche Ziele,
         gleiche Beschriftung, weiter echte Links). -->
    <DkButton
      v-if="zeigeVerwalten"
      ref="verwaltenKnopf"
      as="a"
      class="sb-navigationsknopf"
      variant="ghost"
      size="md"
      href="#/kalender/verwalten"
      @click.prevent="navigate('#/kalender/verwalten')"
    >
      <template #icon><DkSymbol name="bearbeiten" :groesse="14" /></template>
      Kalender verwalten
    </DkButton>

    <DkButton
      v-if="showImport"
      as="a"
      class="sb-navigationsknopf"
      variant="ghost"
      size="md"
      href="#/kalender/import"
      @click.prevent="navigate('#/kalender/import')"
    >
      <template #icon><DkSymbol name="herunterladen" :groesse="14" /></template>
      Kalender importieren
    </DkButton>

    <!-- K-A (R-P1-8): Die eigenen abgelehnten Termine. Abgelehnte Termine
         bleiben aus allen Listen heraus; hier bekommt der Antragsteller den
         Weg zu seiner Detailansicht mit dem Ablehnungsgrund. -->
    <div v-if="abgelehnteTermine.length" class="sidebar-ablehnung-section">
      <h4 class="sidebar-title">Abgelehnte Termine</h4>
      <button
        v-for="t in abgelehnteTermine"
        :key="t.id"
        type="button"
        class="sidebar-ablehnung-item"
        @click="$emit('ablehnungClick', t.id)"
      >
        <span class="sidebar-ablehnung-titel">{{ t.title }}</span>
        <span class="sidebar-ablehnung-zeit">{{ kurzDatum(t.start) }}</span>
      </button>
    </div>

    <DkButton class="sb-navigationsknopf" variant="ghost" size="sm" @click="showHelp = true">
      <template #icon><DkSymbol name="notiz" :groesse="14" /></template>
      Hilfe &amp; Infos
    </DkButton>

    <div
      v-if="showHelp"
      class="diakronos-help-overlay visible"
      @click.self="showHelp = false"
    >
      <div class="diakronos-help-box">
        <button class="diakronos-help-close" aria-label="Schließen" @click="showHelp = false">
          &times;
        </button>
        <h2 class="diakronos-help-title">Kalender auf dem Handy einrichten</h2>
        <p class="diakronos-help-intro">
          Du kannst die Gemeindekalender direkt in dein Handy oder deinen Computer laden – so hast du die Termine immer dabei.
        </p>

        <div class="diakronos-help-credentials">
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Server-Adresse</span>
            <span class="diakronos-help-cred-value">{{ davUrl }}</span>
          </div>
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Benutzername</span>
            <span class="diakronos-help-cred-value diakronos-help-cred-muted">deine Anmelde-E-Mail-Adresse</span>
          </div>
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Passwort</span>
            <span class="diakronos-help-cred-value diakronos-help-cred-muted">dein normales Anmelde-Passwort</span>
          </div>
        </div>

        <!-- OP-ADMIN-20: Bei Anmeldung über Authentik (Single Sign-on) gilt das
             normale Passwort NICHT für CalDAV. -->
        <p class="diakronos-help-note">
          Tipp: Wenn du dich über „Mit Authentik anmelden“ einloggst, gilt dein
          normales Passwort hier nicht. Frag dann bei der Gemeindeleitung nach
          einem Kalender-Passwort.
        </p>

        <div class="diakronos-help-section">
          <h3>iPhone / iPad</h3>
          <ol>
            <li>Öffne <strong>Einstellungen</strong> → <strong>Apps</strong> → <strong>Kalender</strong> → <strong>Kalender-Accounts</strong></li>
            <li>Tippe auf <strong>Account hinzufügen</strong> → <strong>Andere</strong></li>
            <li>Wähle <strong>CalDAV-Account hinzufügen</strong></li>
            <li>Trage Server-Adresse, Benutzername und Passwort von oben ein</li>
            <li>Auf <strong>Weiter</strong> tippen – fertig!</li>
          </ol>
        </div>

        <div class="diakronos-help-section">
          <h3>Android (mit der App DAVx⁵)</h3>
          <ol>
            <li>Installiere <strong>DAVx⁵</strong> kostenlos aus dem Play Store</li>
            <li>Öffne die App und tippe auf das <strong>+</strong>-Symbol</li>
            <li>Wähle <strong>Mit URL und Benutzername anmelden</strong></li>
            <li>Trage Server-Adresse, Benutzername und Passwort von oben ein</li>
            <li>Wähle die gewünschten Kalender aus und synchronisiere</li>
          </ol>
        </div>

        <div class="diakronos-help-section">
          <h3>Thunderbird (Computer)</h3>
          <ol>
            <li>Öffne Thunderbird → <strong>Kalender</strong>-Ansicht</li>
            <li>Rechtsklick in der Kalender-Liste → <strong>Neuer Kalender…</strong></li>
            <li>Wähle <strong>Im Netzwerk</strong> → Typ <strong>CalDAV</strong></li>
            <li>Trage die Server-Adresse von oben ein</li>
            <li>Benutzername und Passwort eingeben – fertig!</li>
          </ol>
        </div>

        <div class="diakronos-help-footer">Diakronos</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
// UX1e: EIN Knopf-System (verwalten/importieren/Hilfe).
import DkButton from '../ui/DkButton.vue';
// UX3i (A4): dezentes Symbol für „Eintragen erlaubt“.
import DkSymbol from '../ui/DkSymbol.vue';
// UX2d3b (Review UX2d3a/B): Laden zeigt den Umriss, keinen Satz.
import DkSkelett from '../ui/DkSkelett.vue';
import { navigate } from '../../router.js';
import { apiCall } from '../../composables/useApi.js';
import { useKronosStore } from '../../composables/useKronosStore.js';
// Nacharbeit 07.11. Punkt 7: Die Rolle wird an EINER Stelle geprüft
// (`kalenderRechte.mjs`), nicht ein zweites Mal hier.
import { istKalenderAdmin } from './kalenderRechte.mjs';
// UXD-R28: Kalenderfarbe nur als gueltiger Hex-Wert in die CSS-Variable.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js';
// ON-4/H3: Leerzustand der Kalenderliste (dasselbe Muster wie die Mitglieder).
import { kalenderLeerzustand } from '../../composables/einrichtungsHinweise.mjs';

const props = defineProps({
  // UXK-R9: steuert das Overlay am Handy (Klasse `open` in kronos.css).
  open: { type: Boolean, default: false },
  currentMonth: {
    type: String,
    default: () => {
      const now = new Date();
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    }
  }
});

const emit = defineEmits(['calendarsChange', 'dateClick', 'monthChange', 'backClick', 'close', 'ablehnungClick']);

const store = useKronosStore();
const showHelp = ref(false);
const showImport = ref(false);
const verwaltenKnopf = ref(null);

/**
 * UX3i (A4): „Hilfe & Infos“ steht jetzt in der Kalender-Kopfzeile (⋯-Menü).
 * Die Erklärung selbst bleibt hier, wo sie schon liegt — die Seite öffnet sie
 * über diese Methode, statt den langen Text ein zweites Mal zu bauen.
 */
function hilfeOeffnen() {
  showHelp.value = true;
  // Den Weg dorthin sichtbar machen: die Leiste liegt am Handy ausserhalb
  // des Bildes, dort wäre die Erklärung sonst nicht zu sehen.
  emit('close');
}
defineExpose({ hilfeOeffnen, verwaltenKnopf });
// OP-ADMIN-10: „Kalender verwalten“ — nur fuer Kalenderadministratoren
// (derselbe Rollenpruef wie der Import; der Server prueft erneut).
const zeigeVerwalten = ref(false);
const abgelehnteTermine = ref([]);
const davUrl = `${window.location.origin}/dav/`;

/** K-A: Datum kurz und deutsch fuer die Liste der abgelehnten Termine. */
function kurzDatum(wert) {
  if (!wert) return '';
  const d = new Date(String(wert).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
}

// Local copy for v-model on checkboxes; syncs with store
/**
 * ON-4 (H3): Leerzustand der Kalenderliste (dasselbe Muster wie die
 * Mitgliederliste). `gesamt` = Zahl ALLER Kalender der Gemeinde — nur
 * Admin-Rollen dürfen sie erfragen; sonst bleibt sie unbekannt und die Leiste
 * behauptet NICHT „noch keine Kalender“.
 */
const kalenderGesamt = ref(null);
const kalenderLeer = computed(() => kalenderLeerzustand({
  anzahl: store.availableCalendars.value.length,
  gesamt: kalenderGesamt.value,
  admin: window.__DIakonosBOOT?.is_admin === true,
}));

/**
 * Zahl ALLER Kalender der Gemeinde — Grundlage des Leerzustands (ON-4/H3).
 *
 * Der Wert wird aus der LISTE der Verwaltungsseite gelesen, die die Leiste
 * ohnehin kennt: `store.availableCalendars` trägt `alle_anzahl`, sobald ein
 * Kalenderadministrator sie geladen hat (der Server liefert die Zahl NUR
 * denen, siehe `permissions.get_accessible_calendars`). Kein eigener Aufruf
 * hier: der Aufbau der Leiste darf nicht an einer zweiten Abfrage hängen, und
 * ohne die Zahl bleibt es beim knappen Hinweis („nichts behaupten“).
 */
watch(
  () => store.availableCalendars.value,
  (liste) => {
    const zahl = Array.isArray(liste) ? liste.find((k) => typeof k?.alle_anzahl === 'number') : null;
    kalenderGesamt.value = zahl ? Number(zahl.alle_anzahl) : null;
  },
  { immediate: true, deep: false },
);

const selectedNames = ref([...store.selectedCalendars.value]);
watch(store.selectedCalendars, (val) => { selectedNames.value = [...val]; });

function onCalendarToggle() {
  store.setSelectedCalendars([...selectedNames.value]);
  emit('calendarsChange', selectedNames.value);
}

function onDateClick(dateStr) { emit('dateClick', dateStr); }
function onMonthChange(monthStr) { emit('monthChange', monthStr); }

// K-A: die Liste laden, sobald die Seitenleiste sichtbar wird. Am Schreibtisch
// (>720px) ist die Leiste IMMER sichtbar, `open` bleibt dort aber `false` — ein
// Watch nur auf `props.open` liesse die Liste dort leer. Deshalb einmal beim
// Aufbau laden und zusaetzlich, wenn mobil aufgeklappt wird.
watch(() => props.open, (offen) => { if (offen) ladeAbgelehnteTermine(); });

/**
 * K-A (R-P1-8): eigene abgelehnte Termine laden (der Server liefert nur die
 * eigenen).
 */
async function ladeAbgelehnteTermine() {
  try {
    const res = await apiCall('diakronos.kronos.api.calendar_get.get_meine_abgelehnten_termine');
    abgelehnteTermine.value = Array.isArray(res) ? res : (res?.message || []);
  } catch {
    abgelehnteTermine.value = [];
  }
}

onMounted(async () => {
  try {
    // Standalone does not inject the Desk-only _kronosUserRoles global.
    const context = await apiCall('diakronos.diakonos.api.session.get_current_user_context');
    // OP-ADMIN-10: beide Wege haengen an derselben Rolle. Der Eintrag
    // „Kalender verwalten“ fuehrt zur Verwaltungsseite (anlegen, Rechte,
    // Moderatoren, loeschen) — sie prueft dieselbe Rolle serverseitig erneut.
    // Nacharbeit 07.11. Punkt 7: Die Prüfung stand hier ein ZWEITES Mal
    // (gleiche drei Bedingungen wie `kalenderRechte.mjs`) und konnte
    // auseinanderlaufen — jetzt EINE Stelle.
    const darfVerwalten = istKalenderAdmin(context);
    showImport.value = darfVerwalten;
    zeigeVerwalten.value = darfVerwalten;
  } catch {
    showImport.value = false;
    zeigeVerwalten.value = false;
  }
  // K-A: am Schreibtisch ist die Leiste sofort sichtbar (ohne Aufklappen).
  // Nie den Aufbau der Leiste daran scheitern lassen, wenn die Liste nicht
  // geladen werden kann.
  try {
    await ladeAbgelehnteTermine();
  } catch {
    abgelehnteTermine.value = [];
  }
});
</script>

<style scoped>
/* UX1e: Die Navigationsknöpfe der Leiste (Kalender verwalten, Kalender
   importieren, Hilfe & Infos). Vor UX1e standen die Eigenklassen
   `.sidebar-help-btn` / `.sidebar-import-btn` doppelt in kronos.css (zwei
   parallele Regelsätze, zwei Optiken); UX1e hat sie durch DkButton (ghost, sm)
   ersetzt, UX1e2 die toten CSS-Regeln entfernt. Hier bleibt nur die Lage in
   der Leiste plus die Farben der dunklen Fläche. Werte aus tokens.css, keine
   festen Farben. */
/* UX1e2: Die Navigationsknöpfe der Leiste stehen auf der dunklen
   Seitenleisten-Fläche (--dk-sb-bg). Die Ghost-Variante des Knopf-Systems
   nimmt --muted/--surface-hover — Farben der HELLEN Fläche; auf der Leiste war
   die Beschriftung dadurch zu blass und der Hover ein heller Block. Hier
   bekommt der Knopf die Farben der Leiste: Schrift var(--dk-sb-text), Hover
   var(--dk-sb-hover) — dieselben Tokens, die die Leiste selbst benutzt, keine
   neuen Farbwerte. Das ist Gestaltung, KEIN Layout: nur Farben, damit die
   Regel in jeder Breite gilt und nicht an eine Media-Query gekoppelt ist. */
.sb-navigationsknopf {
  /* UX1e2: `display: flex` statt `inline-flex`. Der Knopf ist inline-flex; bei
     `width: calc(100% - …)` bleibt ein inline-flex-Element dann auf Inhalts-
     breite (gemessen 22 px — nur das Symbol, der Text wurde abgeschnitten).
     Als Block-Flex nimmt er die Breite der Leiste an. */
  display: flex;
  width: calc(100% - var(--sp-5) * 2);
  margin: var(--sp-1) var(--sp-5);
  justify-content: flex-start;
  color: var(--dk-sb-text);
  background: transparent;
}
.sb-navigationsknopf:hover:not(:disabled),
.sb-navigationsknopf:focus-visible:not(:disabled) {
  color: var(--dk-sb-text);
  background: var(--dk-sb-hover);
}
.ksb-hinweis {
  padding: var(--sp-3);
  margin: 0;
  color: var(--muted);
  font-size: var(--fs);
}
/* ON-4 (H3): Leerzustand der Kalenderliste mit dem Weg „Kalender anlegen“. */
.ksb-leer {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-1);
  padding: var(--sp-2);
}
.ksb-hinweis--klein { font-size: var(--fs-sm); padding: 0 var(--sp-3); }
.ksb-leer-link {
  margin: var(--sp-2) var(--sp-3);
  padding: var(--sp-1) var(--sp-3);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  color: var(--link);
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  text-decoration: none;
}
.ksb-leer-link:hover { background: var(--surface-2); color: var(--link-hover); }
.ksb-leer-link:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

/* K-A (R-P1-8): Liste der eigenen abgelehnten Termine. */
.sidebar-ablehnung-section {
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-ablehnung-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-left: 3px solid var(--dk-danger);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--dk-sb-text);
  font-size: var(--fs);
  text-align: left;
  cursor: pointer;
}
.sidebar-ablehnung-item:hover { background: var(--dk-sb-hover); }
.sidebar-ablehnung-titel { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sidebar-ablehnung-zeit { color: var(--dk-sb-text-muted); font-size: var(--fs-12); flex: none; }

/* UXK-R9: Schliessen-Knopf nur im mobilen Overlay zeigen. */
.kronos-sidebar-close { display: none; }
@media (max-width: 720px) {
  .kronos-sidebar-close {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 12px;
    right: 12px;
    width: 32px;
    height: 32px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--dk-sb-text-muted);
    font-size: var(--fs-20);
    line-height: 1;
    cursor: pointer;
  }
  .kronos-sidebar-close:hover { background: var(--dk-sb-hover); color: var(--dk-sb-text); }
}
</style>
