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
    >✕</button>
    <div class="sidebar-divider"></div>

    <div class="sidebar-calenderlist-section">
      <h4 class="sidebar-title">Meine Kalender</h4>
      <p v-if="store.loading.value" class="ksb-hinweis">Kalender werden geladen...</p>
      <p v-else-if="store.availableCalendars.value.length === 0" class="ksb-hinweis">Keine Kalender freigegeben</p>
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
          <span v-if="cal.write" class="ksb-recht-hinweis" title="Du darfst hier Termine eintragen">Eintragen erlaubt</span>
        </div>
      </template>
    </div>

    <a
      v-if="zeigeVerwalten"
      class="sidebar-import-btn"
      href="#/kalender/verwalten"
      @click.prevent="navigate('#/kalender/verwalten')"
    >
      <span class="sidebar-import-icon" aria-hidden="true">⚙</span> Kalender verwalten
    </a>

    <a
      v-if="showImport"
      class="sidebar-import-btn"
      href="#/kalender/import"
      @click.prevent="navigate('#/kalender/import')"
    >
      <span class="sidebar-import-icon">⬆</span> Kalender importieren
    </a>

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

    <button class="sidebar-help-btn" @click="showHelp = true">
      <span class="sidebar-help-icon">?</span> Hilfe &amp; Infos
    </button>

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
import { ref, watch, onMounted } from 'vue';
import { navigate } from '../../router.js';
import { apiCall } from '../../composables/useApi.js';
import { useKronosStore } from '../../composables/useKronosStore.js';
// UXD-R28: Kalenderfarbe nur als gueltiger Hex-Wert in die CSS-Variable.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js';

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
const selectedNames = ref([...store.selectedCalendars.value]);
watch(store.selectedCalendars, (val) => { selectedNames.value = [...val]; });

function onCalendarToggle() {
  store.setSelectedCalendars([...selectedNames.value]);
  emit('calendarsChange', selectedNames.value);
}

function onDateClick(dateStr) { emit('dateClick', dateStr); }
function onMonthChange(monthStr) { emit('monthChange', monthStr); }

// K-A: die Liste laden, sobald die Seitenleiste sichtbar wird. Am Schreibtisch
// (>768px) ist die Leiste IMMER sichtbar, `open` bleibt dort aber `false` — ein
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
    const userRoles = context.roles || [];
    // OP-ADMIN-10: beide Wege haengen an derselben Rolle. Der Eintrag
    // „Kalender verwalten“ fuehrt zur Verwaltungsseite (anlegen, Rechte,
    // Moderatoren, loeschen) — sie prueft dieselbe Rolle serverseitig erneut.
    const istKalenderAdmin = context.user === 'Administrator'
      || userRoles.includes('Administrator')
      || userRoles.includes('Kalenderadministrator');
    showImport.value = istKalenderAdmin;
    zeigeVerwalten.value = istKalenderAdmin;
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
.ksb-hinweis {
  padding: var(--sp-3);
  margin: 0;
  color: var(--muted);
  font-size: var(--fs);
}

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
.sidebar-ablehnung-zeit { color: var(--dk-sb-text-muted); font-size: 12px; flex: none; }

/* UXK-R9: Schliessen-Knopf nur im mobilen Overlay zeigen. */
.kronos-sidebar-close { display: none; }
@media (max-width: 768px) {
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
    font-size: 18px;
    line-height: 1;
    cursor: pointer;
  }
  .kronos-sidebar-close:hover { background: var(--dk-sb-hover); color: var(--dk-sb-text); }
}
</style>
