<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Eingebettet im Mitglieder-Bereich entfällt der eigene Kopf. -->
    <div v-if="!embedded" class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Übersicht</h1>
        <p class="dk-screen-sub">Auf einen Blick sehen, ob etwas zu tun ist.</p>
      </div>
    </div>

    <DkHint v-if="error" variant="err">{{ error }}</DkHint>

    <!-- Kennzahlen — jede Kachel führt in den passenden Reiter. -->
    <div v-if="loading" class="ub-kacheln">
      <div v-for="n in 4" :key="n" class="dk-skeleton dk-skeleton-card" style="height:104px"></div>
    </div>
    <div v-else class="ub-kacheln">
      <button
        v-for="k in kacheln"
        :key="k.id"
        type="button"
        class="dk-ui-kachel"
        @click="navigate(k.href)"
      >
        <span class="dk-ui-kachel-label">{{ k.label }}</span>
        <span class="dk-ui-kachel-wert" :class="'is-' + k.ton">{{ k.wert }}</span>
        <span v-if="k.hinweis" class="dk-ui-kachel-hinweis">{{ k.hinweis }}</span>
      </button>
    </div>

    <!-- Zu erledigen: nur Punkte mit etwas zu tun (kein toter Eintrag). -->
    <DkCard v-if="!loading && aufgaben.length" title="Zu erledigen" class="ub-block">
      <ul class="ub-aufgaben">
        <li v-for="a in aufgaben" :key="a.id">
          <span class="ub-aufgabe-text">{{ a.text }}</span>
          <DkButton variant="ghost" size="sm" @click="navigate(a.href)">{{ a.aktion }}</DkButton>
        </li>
      </ul>
    </DkCard>

    <!-- Verteilung nach Status (Personen, nicht Protokollzeilen). -->
    <DkCard v-if="!loading" title="Verteilung nach Status" class="ub-block">
      <ul class="ub-verteilung">
        <li v-for="z in verteilung" :key="z.id">
          <span class="ub-verteilung-name">{{ z.label }}</span>
          <span class="ub-verteilung-zahl">{{ z.wert }}</span>
        </li>
      </ul>
      <p class="ub-leise">
        Neu in diesem Monat: {{ stats.anmeldungen.diesen_monat }} ·
        Aktive Links: {{ stats.links.aktiv }} ·
        Anmeldungen über Links gesamt: {{ stats.links.gesamt_anmeldungen }}
      </p>
    </DkCard>
  </div>
</template>

<script setup>
/**
 * Mitglieder → Übersicht (Neuordnung N1).
 *
 * Mini-Dashboard für Mitgliederadministratoren. Ersetzt die alte Seite
 * „Statistik“. Jede Kachel ist klickbar und springt in den passenden Reiter
 * mit gesetztem Filter (Adresse über die Reiterdefinition in menue.js).
 *
 * „Datenschutz offen“ zählt PERSONEN ohne Einwilligung, nicht Protokollzeilen
 * (Befund UXD-R16) — die Zahl kommt so vom Server (get_statistik).
 * „Gruppen“ gehört bewusst nicht hierher; die Zahl steht auf der Seite Gruppen.
 */
import { ref, computed, onMounted } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { offeneAntraegeZaehlen } from '../../composables/useLoeschantraege.js'
import { navigate } from '../../router.js'
import DkCard from '../../components/ui/DkCard.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkHint from '../../components/ui/DkHint.vue'

// Im Mitglieder-Bereich eingebettet: eigener Kopf entfällt.
defineProps({ embedded: { type: Boolean, default: false } })

const loading = ref(true)
const error = ref('')
// DSGVO-2c: Zahl offener Löschanträge. `null` = keine Auskunft (Fehler) —
// dann zeigt die Kachel KEINE Zahl („–“) und keinen Hinweis, statt eine
// erfundene Null zu behaupten. DSGVO-2c2: gezählt wird über den vorhandenen
// Helfer `offeneAntraegeZaehlen()`, damit es nur EINEN Weg zur Zahl gibt.
const offeneLoeschantraege = ref(null)
const stats = ref({
  mitglieder: { gesamt: 0, mitglied: 0, gast: 0, passives_mitglied: 0, passiver_gast: 0 },
  dsgvo: { ok: 0, widerrufen: 0, fehlt: 0 },
  anmeldungen: { gesamt: 0, diesen_monat: 0, offen: 0, nach_status: {} },
  links: { aktiv: 0, inaktiv: 0, gesamt_anmeldungen: 0, top: [] },
})

defineExpose({ reload: laden })

async function laden() {
  loading.value = true
  error.value = ''
  // Die Löschanträge kommen aus ihrem eigenen Endpunkt und dürfen die
  // Kennzahlen nicht kippen: ein Fehler lässt die Kachel leer („–“).
  // DSGVO-2c2: über den Helfer aus `useLoeschantraege.js` — nicht zweimal
  // dasselbe zählen. `null` heißt dabei ausdrücklich „keine Auskunft“.
  offeneLoeschantraege.value = await offeneAntraegeZaehlen()
  try {
    stats.value = await apiCall('diakronos.diakonos.api.admin_hub.get_statistik')
  } catch (e) {
    error.value = e?.message || 'Die Kennzahlen konnten nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

/** Zieladressen der Reiter mit gesetztem Filter (Konzept Abschnitt 3). */
const HREF = {
  liste: '#/personen/liste',
  mitglieder: '#/personen/liste?status=Mitglied',
  anfragen: '#/personen/anfragen',
  datenschutz: '#/personen/datenschutz',
  // DSGVO-2c: eigene Arbeitsliste für Löschanträge.
  loeschantraege: '#/personen/loeschantraege',
}

const kacheln = computed(() => {
  const m = stats.value.mitglieder || {}
  const d = stats.value.dsgvo || {}
  const a = stats.value.anmeldungen || {}
  return [
    { id: 'personen', label: 'Personen', wert: m.gesamt || 0, ton: 'neutral', href: HREF.liste },
    { id: 'mitglieder', label: 'Mitglieder', wert: m.mitglied || 0, ton: 'ok', href: HREF.mitglieder },
    {
      id: 'anfragen', label: 'Offene Anfragen', wert: a.offen || 0,
      ton: (a.offen ? 'warn' : 'neutral'), href: HREF.anfragen,
      hinweis: a.offen ? 'warten auf Prüfung' : '',
    },
    {
      id: 'datenschutz', label: 'Datenschutz offen', wert: d.fehlt || 0,
      ton: (d.fehlt ? 'warn' : 'neutral'), href: HREF.datenschutz,
      hinweis: d.fehlt ? 'ohne Einwilligung' : '',
    },
    // DSGVO-2c: eigener Zähler für offene Löschanträge — sie gaben bisher
    // nirgends auf der Übersicht zu erkennen, dass etwas zu tun ist.
    // DSGVO-2c2: ohne Auskunft (`null`) steht hier „–“ statt einer 0, die es
    // nicht gibt; Ton und Hinweis hängen ebenfalls an einer echten Zahl.
    {
      id: 'loeschantraege', label: 'Löschanträge',
      wert: offeneLoeschantraege.value === null ? '–' : offeneLoeschantraege.value,
      ton: ((offeneLoeschantraege.value ?? 0) > 0 ? 'warn' : 'neutral'), href: HREF.loeschantraege,
      hinweis: (offeneLoeschantraege.value ?? 0) > 0 ? 'warten auf Freigabe' : '',
    },
  ]
})

const aufgaben = computed(() => {
  const a = stats.value.anmeldungen || {}
  const d = stats.value.dsgvo || {}
  const liste = []
  if (a.offen) {
    liste.push({
      id: 'anfragen',
      text: `${a.offen} ${a.offen === 1 ? 'Anfrage wartet' : 'Anfragen warten'} auf Prüfung`,
      aktion: 'Prüfen',
      href: HREF.anfragen,
    })
  }
  if (d.fehlt) {
    liste.push({
      id: 'datenschutz',
      text: `${d.fehlt} ${d.fehlt === 1 ? 'Person hat' : 'Personen haben'} noch keine Einwilligung`,
      aktion: 'Ansehen',
      href: HREF.datenschutz,
    })
  }
  // DSGVO-2c: offene Löschanträge sind eine Aufgabe der Verwaltung.
  const offen = offeneLoeschantraege.value
  if (offen) {
    liste.push({
      id: 'loeschantraege',
      text: `${offen} ${offen === 1 ? 'Löschantrag wartet' : 'Löschanträge warten'} auf Freigabe`,
      aktion: 'Prüfen',
      href: HREF.loeschantraege,
    })
  }
  return liste
})

const verteilung = computed(() => {
  const m = stats.value.mitglieder || {}
  return [
    { id: 'mitglied', label: 'Mitglieder', wert: m.mitglied || 0 },
    { id: 'gast', label: 'Gäste', wert: m.gast || 0 },
    { id: 'passives_mitglied', label: 'Passive Mitglieder', wert: m.passives_mitglied || 0 },
    { id: 'passiver_gast', label: 'Passive Gäste', wert: m.passiver_gast || 0 },
  ]
})

onMounted(laden)
</script>

<style scoped>
.ub-kacheln {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--sp-4);
}
.dk-skeleton-card { border-radius: var(--radius-lg); }

/* Kacheln sind Schaltflächen (klickbar), sehen aber wie ruhige Karten aus.
   UX1d (D2): kein Rahmen mehr — getönte Fläche + sanfter Schatten trennen
   sie vom Grund (Prinzip Ä2); die Kennfarbe erscheint erst bei Hover/Fokus. */
.dk-ui-kachel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  text-align: left;
  padding: var(--karte-innen);
  border: var(--karte-rand) solid var(--rahmen-farbe);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
  color: inherit;
  font: inherit;
  cursor: pointer;
  transition: box-shadow var(--fast), background var(--fast);
}
.dk-ui-kachel:hover { box-shadow: var(--shadow-md); background: var(--surface-hover); }
.dk-ui-kachel:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: var(--sp-1); }
.dk-ui-kachel-label {
  font-size: var(--fs-sm);
  color: var(--muted);
  font-weight: 500;
}
.dk-ui-kachel-wert {
  font-size: var(--fs-h1);
  font-weight: 600;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--text);
}
.dk-ui-kachel-wert.is-ok    { color: var(--ok); }
.dk-ui-kachel-wert.is-warn  { color: var(--warn); }
.dk-ui-kachel-hinweis { font-size: var(--fs-sm); color: var(--muted); }

.ub-block { margin-top: var(--sp-alt-20); }

.ub-aufgaben { list-style: none; margin: 0; padding: 0; }
/* UX1d (D2): Abstand trennt die Zeilen (Prinzip S3) — die Linie ist weg. */
.ub-aufgaben li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
}
.ub-aufgaben li + li { margin-top: var(--sp-1); }
.ub-aufgabe-text { color: var(--text); }

.ub-verteilung { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--sp-alt-20); }
.ub-verteilung li { display: flex; flex-direction: column; gap: 2px; }
.ub-verteilung-name { font-size: var(--fs-sm); color: var(--muted); }
.ub-verteilung-zahl { font-size: var(--fs-h3); font-weight: 600; font-variant-numeric: tabular-nums; }
.ub-leise { margin: var(--sp-4) 0 0; font-size: var(--fs-sm); color: var(--muted); }
</style>
