<template>
  <aside class="kronos-sidebar">
    <button type="button" class="kronos-back-btn" @click="$emit('backClick')" title="Zur Hauptnavigation">
      <div class="kronos-back-logo">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </div>
      <div class="kronos-back-text">
        <span class="kronos-back-name">Diakonos</span>
        <span class="kronos-back-sub">Zur Hauptnavigation</span>
      </div>
    </button>
    <div class="sidebar-divider"></div>

    <div class="sidebar-calenderlist-section">
      <h4 class="sidebar-title">Meine Kalender</h4>
      <p v-if="loading" class="text-muted p-3">Kalender werden geladen...</p>
      <p v-else-if="calendars.length === 0" class="text-muted p-3">Keine Kalender freigegeben</p>
      <template v-else>
        <div
          v-for="cal in calendars"
          :key="cal.name"
          class="calendar-item"
          :style="{ '--calendar-color': cal.color || 'var(--primary)' }"
        >
          <input
            type="checkbox"
            :id="'cal-' + cal.name"
            v-model="selectedNames"
            :value="cal.name"
            @change="onCalendarToggle"
          />
          <label :for="'cal-' + cal.name">{{ cal.title || cal.name }}</label>
          <span v-if="cal.write" class="pencil-icon" title="Schreibrecht">&#9998;</span>
        </div>
      </template>
    </div>

    <a
      v-if="showImport"
      class="sidebar-import-btn"
      href="/app/google-kalender-import"
    >
      <span class="sidebar-import-icon">&#11014;</span> Kalender importieren
    </a>

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
          Ihr könnt die Gemeindekalender direkt in euer Handy oder euren Computer laden – so habt ihr die Termine immer dabei.
        </p>

        <div class="diakronos-help-credentials">
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Server-Adresse</span>
            <span class="diakronos-help-cred-value">{{ davUrl }}</span>
          </div>
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Benutzername</span>
            <span class="diakronos-help-cred-value diakronos-help-cred-muted">eure Anmelde-E-Mail-Adresse</span>
          </div>
          <div class="diakronos-help-cred-row">
            <span class="diakronos-help-cred-label">Passwort</span>
            <span class="diakronos-help-cred-value diakronos-help-cred-muted">euer normales Anmelde-Passwort</span>
          </div>
        </div>

        <div class="diakronos-help-section">
          <h3>iPhone / iPad</h3>
          <ol>
            <li>Öffnet <strong>Einstellungen</strong> → <strong>Apps</strong> → <strong>Kalender</strong> → <strong>Kalender-Accounts</strong></li>
            <li>Tippt auf <strong>Account hinzufügen</strong> → <strong>Andere</strong></li>
            <li>Wählt <strong>CalDAV-Account hinzufügen</strong></li>
            <li>Tragt Server-Adresse, Benutzername und Passwort von oben ein</li>
            <li>Auf <strong>Weiter</strong> tippen – fertig!</li>
          </ol>
        </div>

        <div class="diakronos-help-section">
          <h3>Android (mit der App DAVx⁵)</h3>
          <ol>
            <li>Installiert <strong>DAVx⁵</strong> kostenlos aus dem Play Store</li>
            <li>Öffnet die App und tippt auf das <strong>+</strong>-Symbol</li>
            <li>Wählt <strong>Mit URL und Benutzername anmelden</strong></li>
            <li>Tragt Server-Adresse, Benutzername und Passwort von oben ein</li>
            <li>Wählt die gewünschten Kalender aus und synchronisiert</li>
          </ol>
        </div>

        <div class="diakronos-help-section">
          <h3>Thunderbird (Computer)</h3>
          <ol>
            <li>Öffnet Thunderbird → <strong>Kalender</strong>-Ansicht</li>
            <li>Rechtsklick in der Kalender-Liste → <strong>Neuer Kalender…</strong></li>
            <li>Wählt <strong>Im Netzwerk</strong> → Typ <strong>CalDAV</strong></li>
            <li>Tragt die Server-Adresse von oben ein</li>
            <li>Benutzername und Passwort eingeben – fertig!</li>
          </ol>
        </div>

        <div class="diakronos-help-footer">Diakronos · Dells Dienste</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

const props = defineProps({
  currentMonth: {
    type: String,
    default: () => {
      const now = new Date();
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    }
  }
});

const emit = defineEmits(['calendarsChange', 'dateClick', 'monthChange', 'backClick']);

const calendars = ref([]);
const loading = ref(true);
const selectedNames = ref([]);
const showHelp = ref(false);
const showImport = ref(false);

const davUrl = `${window.location.origin}/dav/`;

const writableCalendars = computed(() => calendars.value.filter(c => c.write === true));
const readableCalendars = computed(() => calendars.value.filter(c => c.write !== true));

async function loadCalendars() {
  try {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const response = await fetch('/api/method/diakronos.kronos.api.permissions.get_accessible_calendars', {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
        'X-Frappe-CSRF-Token': csrfToken
      }
    });

    if (!response.ok) {
      throw new Error(`API Fehler: ${response.status} - ${response.statusText}`);
    }

    const result = await response.json();
    calendars.value = result.message || [];

    const stored = localStorage.getItem('selected_calendars');
    if (stored) {
      selectedNames.value = JSON.parse(stored);
    } else {
      selectedNames.value = calendars.value.map(cal => cal.name);
    }
    emit('calendarsChange', selectedNames.value);
  } catch (err) {
    console.error('❌ Fehler beim Laden der Kalender:', err);
    calendars.value = [];
  } finally {
    loading.value = false;
  }
}

function onCalendarToggle() {
  localStorage.setItem('selected_calendars', JSON.stringify(selectedNames.value));
  emit('calendarsChange', selectedNames.value);
}

function onDateClick(dateStr) {
  emit('dateClick', dateStr);
}

function onMonthChange(monthStr) {
  emit('monthChange', monthStr);
}

onMounted(() => {
  loadCalendars();
  const userRoles = window._kronosUserRoles || [];
  showImport.value = userRoles.includes('Administrator') || userRoles.includes('Kalenderadministrator');
});
</script>

