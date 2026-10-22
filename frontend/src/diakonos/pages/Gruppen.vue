<template>
  <div class="dk-screen dk-screen-enter gr-screen">
    <!-- Kopf: im Gruppen-Bereich liefert ihn der Rahmen. -->
    <div v-if="!embedded" class="dk-screen-header gr-kopf">
      <div>
        <h1 class="dk-screen-title">Gruppen</h1>
        <p class="dk-screen-sub">Übersicht aller Dienstbereiche, Gruppen und Untergruppen.</p>
      </div>
      <!-- OP-ADMIN-6: Bereichsverantwortliche sollen Gruppen auch hier anlegen
           können, ohne den Umweg über Verwaltung → Organigramm. Der Server
           entscheidet über can_create_*; der Knopf zeigt nur, was er erlaubt. -->
      <div v-if="perms.can_create_any" class="gr-kopf-aktionen">
        <DkButton v-if="perms.can_create_gruppe" variant="primary" @click="openCreate('gruppe')">+ Neue Gruppe</DkButton>
        <DkButton v-if="perms.can_create_untergruppe" variant="secondary" @click="openCreate('untergruppe')">+ Neue Untergruppe</DkButton>
      </div>
    </div>

    <!-- Anlegen (OP-ADMIN-6/UXD-R4): gleiche Felder wie im Organigramm, hier
         an der Stelle, an der die Gruppen auch erscheinen. -->
    <DkDialog v-model="showCreate" :title="createForm.typ === 'untergruppe' ? 'Neue Untergruppe' : 'Neue Gruppe'">
      <!-- OP-UI-23: <form @submit.prevent> — Enter im Feld sendet dieselbe
           Hauptaktion wie der Knopf (statt wirkungslos zu bleiben). -->
      <form class="gr-formular" @submit.prevent="submitCreate">
        <DkField label="Name" required :error="createFehler.name">
          <input v-model="createForm.name" type="text" class="dk-ui-eingabe" placeholder="Name eingeben" required />
        </DkField>
        <DkField v-if="createForm.typ === 'gruppe'" label="Dienstbereich" required :error="createFehler.parent">
          <DkSelect v-model="createForm.parent" :options="dienstbereichOptionen" placeholder="Bitte wählen" />
        </DkField>
        <DkField v-else label="Gruppe" required :error="createFehler.parent">
          <DkSelect v-model="createForm.parent" :options="gruppenOptionen" placeholder="Bitte wählen" />
        </DkField>
      </form>
      <template #footer>
        <DkButton variant="ghost" @click="showCreate = false">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="sendingCreate" @click="submitCreate">Erstellen</DkButton>
      </template>
    </DkDialog>

    <!-- OP-UI-19: Der Seitenkopf steht schon, der Inhalt ist ein ruhiges
         Skelett. Vorher stand hier „Lade…“ ohne Umriss; nach dem Laden
         erschienen Zähler wie „0“, die wie ein Ergebnis aussahen. -->
    <DkSkelett v-if="loading" form="karten" :anzahl="6" text="Gruppen werden geladen …" />

    <template v-else>

      <!-- ═══ Meine Gruppen ═══ -->
      <section v-if="meineGruppen.length > 0" class="gr-abschnitt">
        <div class="gr-abschnitt-kopf">
          <span class="gr-abschnitt-titel">Meine Gruppen</span>
          <span class="gr-zaehler">{{ gefilterteMeineGruppen.length }}</span>
        </div>

        <!-- DES-01: eine Chip-Zeile aus dem Baustein (vorher 28 handgebaute
             Knöpfe in 12 Seiten, hier zusätzlich ohne umschaltbaren Zustand). -->
        <div class="gr-filterzeile">
          <DkFilterChips
            :chips="meineDienstbereichChips"
            :model-value="aktiverMeineChip"
            aria-label="Meine Gruppen nach Dienstbereich filtern"
            @waehlen="chipWaehlen('meine', $event)"
          />
        </div>

        <!-- Horizontales 2-Zeilen-Grid -->
        <!-- OP-UI-19/S10: Drei getrennte Leerfälle — kein Treffer für den
             Filter, gar keine Gruppen, oder nur „Meine“ leer. Ein einziger
             Satz für alles sagte dem Nutzer das Falsche. -->
        <DkEmpty
          v-if="gefilterteMeineGruppen.length === 0"
          icon="🔎"
          title="Keine Gruppe in diesem Dienstbereich"
          text="Wähle oben „Alle“ oder einen anderen Dienstbereich."
        >
          <DkButton variant="ghost" size="sm" @click="chipWaehlen('meine', 'alle')">Alle zeigen</DkButton>
        </DkEmpty>
        <div v-else class="gr-grid-scroll">
          <a
            v-for="g in gefilterteMeineGruppen"
            :key="g.name"
            class="gr-kachel"
            :href="'#/gruppe/' + g.name"
          >
            <div class="gr-kachel-img">
              <img v-if="g.bild" :src="g.bild" :alt="g.gruppenname" class="gr-kachel-bild" />
              <div v-else class="gr-kachel-farbe" :style="{ background: kachelFarbe(g) }"></div>
              <span v-if="g.ist_verantwortlich" class="gr-badge">Verantwortlich</span>
            </div>
            <div class="gr-kachel-body">
              <div class="gr-kachel-name">{{ g.gruppenname }}</div>
              <div class="gr-tags">
                <span v-if="g.gruppentyp_name" class="gr-typ-tag">{{ g.gruppentyp_name }}</span>
              </div>
              <div class="gr-kachel-meta">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </a>
        </div>
      </section>

      <!-- ═══ Alle Gruppen (nur Admins) ═══ -->
      <section v-if="isAdmin && alleGruppenFlach.length > 0" class="gr-abschnitt gr-abschnitt--letzter">
        <div class="gr-abschnitt-kopf">
          <span class="gr-abschnitt-titel">Alle Gruppen</span>
          <span class="gr-zaehler">{{ gefilterteAlleGruppen.length }}</span>
        </div>

        <div class="gr-filterzeile">
          <DkFilterChips
            :chips="alleDienstbereichChips"
            :model-value="aktiverAlleChip"
            aria-label="Alle Gruppen nach Dienstbereich filtern"
            @waehlen="chipWaehlen('alle', $event)"
          />
        </div>

        <!-- Horizontales 2-Zeilen-Grid -->
        <DkEmpty
          v-if="gefilterteAlleGruppen.length === 0"
          icon="🔎"
          title="Keine Gruppe in diesem Dienstbereich"
          text="Wähle oben „Alle“ oder einen anderen Dienstbereich."
        >
          <DkButton variant="ghost" size="sm" @click="chipWaehlen('alle', 'alle')">Alle zeigen</DkButton>
        </DkEmpty>
        <div v-else class="gr-grid-scroll">
          <a
            v-for="g in gefilterteAlleGruppen"
            :key="g.name"
            class="gr-kachel"
            :href="'#/gruppe/' + g.name"
          >
            <div class="gr-kachel-img">
              <img v-if="g.bild" :src="g.bild" :alt="g.gruppenname" class="gr-kachel-bild" />
              <div v-else class="gr-kachel-farbe" :style="{ background: kachelFarbe(g) }"></div>
            </div>
            <div class="gr-kachel-body">
              <div class="gr-kachel-name">{{ g.gruppenname }}</div>
              <div class="gr-tags">
                <span v-if="g.gruppentyp_name" class="gr-typ-tag">{{ g.gruppentyp_name }}</span>
              </div>
              <div class="gr-kachel-meta">👤 {{ g.mitglieder_count }} Mitglieder</div>
            </div>
          </a>
        </div>
      </section>

      <!-- OP-UI-19/S10: gar keine Gruppen sichtbar (dritter Leerfall). -->
      <DkEmpty
        v-if="!loading && meineGruppen.length === 0 && !(isAdmin && alleGruppenFlach.length > 0)"
        icon="👥"
        title="Noch keine Gruppe sichtbar"
        text="Sobald du einer Gruppe zugeordnet bist oder eine eigene Gruppe entsteht, erscheint sie hier."
      />

    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { navigate } from '../router.js'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'
import { adresseSchreiben, zustandAusAdresse, pfadOhneAbfrage } from '../composables/listenzustand.mjs'
import { chipsAus, filtereNachChip } from '../composables/filterChips.mjs'
import DkButton from '../components/ui/DkButton.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'

// Im Gruppen-Bereich eingebettet: eigener Kopf entfällt.
defineProps({ embedded: { type: Boolean, default: false } })

const loading = ref(true)
const meineGruppen = ref([])
const andereGruppen = ref([])
const isAdmin = ref(false)

// OP-ADMIN-6: Anlegen-Rechte und die auswählbaren Dienstbereiche/Gruppen.
const perms = ref({ can_create_any: false, can_create_gruppe: false, can_create_untergruppe: false, can_edit_ids: [] })
const alleDienstbereiche = ref([])
const alleGruppenNamen = ref([])
const showCreate = ref(false)
const sendingCreate = ref(false)
const createForm = ref({ typ: 'gruppe', name: '', parent: '' })
// OP-UI-5/UXD-R22: der Knopf bleibt aktiv; der Klick prüft und benennt das
// fehlende Feld, statt stumm nichts zu tun (vorher `:disabled`).
const createFehler = ref({ name: '', parent: '' })

const dienstbereichOptionen = computed(() =>
  alleDienstbereiche.value.map(d => ({ value: d.name, label: d.ministry || d.name })))
const gruppenOptionen = computed(() =>
  alleGruppenNamen.value.map(g => ({ value: g.name, label: g.gruppenname || g.name })))

function openCreate(typ) {
  createForm.value = { typ, name: '', parent: '' }
  createFehler.value = { name: '', parent: '' }
  showCreate.value = true
}

/** Pflichtfelder prüfen (OP-UI-5): Fehler am Feld, Fokus ins erste Feld. */
function pruefeCreate() {
  const f = createForm.value
  const fehler = { name: '', parent: '' }
  if (!f.name.trim()) fehler.name = 'Bitte einen Namen angeben.'
  if (!f.parent) fehler.parent = f.typ === 'untergruppe'
    ? 'Bitte eine Gruppe wählen.'
    : 'Bitte einen Dienstbereich wählen.'
  createFehler.value = fehler
  return !fehler.name && !fehler.parent
}

async function submitCreate() {
  if (sendingCreate.value) return
  if (!pruefeCreate()) {
    requestAnimationFrame(() => document.querySelector('.gr-formular .dk-ui-eingabe')?.focus())
    return
  }
  const f = createForm.value
  sendingCreate.value = true
  try {
    if (f.typ === 'untergruppe') {
      await apiCall('diakronos.diakonos.api.gruppen.create_untergruppe', {
        name: f.name.trim(), gruppe: f.parent,
      })
      showToast('Untergruppe angelegt', 'success')
    } else {
      await apiCall('diakronos.diakonos.api.gruppen.create_gruppe', {
        name: f.name.trim(), dienstbereich: f.parent,
      })
      showToast('Gruppe angelegt', 'success')
    }
    showCreate.value = false
    await loadData()
  } catch (err) {
    showToast(err?.message || 'Fehler beim Anlegen', 'error')
  } finally {
    sendingCreate.value = false
  }
}

const aktiverMeineChip = ref('alle')
const aktiverAlleChip = ref('alle')

/**
 * OP-UI-8: Der gewählte Dienstbereich gehört in die Adresse (#/gruppen?gruppenname=…).
 * Sonst gingen Suche/Filter beim Öffnen einer Gruppe und Zurückkehren verloren
 * (15 Kacheln statt 26 im Befund).
 */
function chipWaehlen(bereich, chipId) {
  if (bereich === 'meine') aktiverMeineChip.value = chipId
  else aktiverAlleChip.value = chipId
  if (typeof window === 'undefined') return
  const pfad = pfadOhneAbfrage(window.location.href)
  // Immer den Zustand des Bereichs „Alle“ schreiben, den die Adresse trägt
  // (der Bereich „Meine“ ist eine persoenliche Untermenge ohne eigene Adresse).
  const wert = (chipId && chipId !== 'alle') ? chipId : ''
  window.history.replaceState(null, '', adresseSchreiben(pfad, { gruppenname: wert }))
}

/** OP-UI-8: gewählten Dienstbereich beim Öffnen aus der Adresse übernehmen. */
function chipAusAdresse() {
  if (typeof window === 'undefined') return 'alle'
  const wert = zustandAusAdresse(window.location.hash).gruppenname
  return wert || 'alle'
}

/**
 * DES-04: Nur ein gueltiger Hex-Wert darf in einen style-String. Der Server
 * prueft ebenfalls (`_normalisiere_farbe`); diese zweite Schranke haelt einen
 * Altbestand (`zzz-keine-farbe`) aus dem CSS und die Kachel bleibt farbig.
 */
const FARB_MUSTER = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/
const STANDARD_FARBE = '#667eea'

function kachelFarbe(g) {
  const wert = g && g.dienstbereich_farbe
  return wert && FARB_MUSTER.test(String(wert).trim()) ? wert : STANDARD_FARBE
}

// ─── Chips und Filterung (DES-01: ein Baustein statt sechsmal dieselbe Schleife) ───
const dienstbereichVon = (g) => g.dienstbereich_name || ''
const meineDienstbereichChips = computed(() => chipsAus(meineGruppen.value, dienstbereichVon))
const gefilterteMeineGruppen = computed(() =>
  filtereNachChip(meineGruppen.value, aktiverMeineChip.value, dienstbereichVon))

// ─── Alle Gruppen: flaches Array aus andereGruppen ───
const alleGruppenFlach = computed(() => {
  const flat = []
  for (const db of andereGruppen.value) {
    for (const g of db.gruppen) {
      flat.push({
        ...g,
        dienstbereich_name: g.dienstbereich_name || db.dienstbereich_name || g.dienstbereich_abbr || '',
        dienstbereich_farbe: g.dienstbereich_farbe || db.dienstbereich_farbe || null,
      })
    }
  }
  return flat
})

const alleDienstbereichChips = computed(() => chipsAus(alleGruppenFlach.value, dienstbereichVon))
const gefilterteAlleGruppen = computed(() =>
  filtereNachChip(alleGruppenFlach.value, aktiverAlleChip.value, dienstbereichVon))

async function loadData() {
  loading.value = true
  try {
    const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    meineGruppen.value = data?.meine_gruppen || []
    andereGruppen.value = data?.andere_gruppen || []
    isAdmin.value = data?.is_admin || false
    perms.value = data?.create_permissions || perms.value
    alleDienstbereiche.value = data?.dienstbereich_auswahl || []
    alleGruppenNamen.value = data?.gruppen_auswahl || []
  } catch (err) {
    console.error('Fehler beim Laden:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // OP-UI-8: gewählten Dienstbereich aus der Adresse übernehmen.
  aktiverAlleChip.value = chipAusAdresse()
  loadData()
})
</script>

<style scoped>
/* DES-02: Die 22 Inline-Stil-Attribute dieser Seite sind hier zu Klassen
   geworden (Abstände und Schriftgrade aus tokens.css). */
.gr-screen { display: flex; flex-direction: column; gap: 0; }
.gr-kopf {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-bottom: var(--sp-5);
}
.gr-kopf-aktionen { display: flex; gap: var(--sp-2); }

.gr-abschnitt { margin-bottom: var(--sp-8); }
.gr-abschnitt--letzter { margin-top: var(--sp-1); }
.gr-abschnitt-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}
.gr-abschnitt-titel {
  font-size: var(--fs-h3);
  font-weight: var(--fw-h);
  color: var(--text);
}
.gr-zaehler {
  font-size: var(--fs-sm);
  color: var(--muted);
  background: var(--surface-2);
  padding: 2px 9px;
  border-radius: var(--badge-r);
  border: 1px solid var(--line);
}
.gr-filterzeile { margin-bottom: var(--sp-3); }
.gr-tags {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-bottom: 5px;
}

/* ── Horizontales 2-Zeilen-Grid mit Scroll ── */
.gr-grid-scroll {
  display: grid;
  grid-auto-flow: column;
  /* DES-R7: Ohne `grid-auto-columns` bemisst der Browser die Spalten am
     Inhalt; bei `overflow-x:auto` kollabierte jede Spalte auf ~45 px und die
     Gruppennamen waren am Handy auf „A…“ abgeschnitten. Die Spaltenbreite
     wird deshalb fest vorgegeben: 150–190 px, auf schmalen Anzeigen kleiner. */
  grid-auto-columns: minmax(150px, 190px);
  grid-template-rows: repeat(2, auto);
  gap: 14px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  padding-bottom: 8px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
@media (max-width: 400px) {
  .gr-grid-scroll { grid-auto-columns: minmax(132px, 168px); }
}
.gr-grid-scroll::-webkit-scrollbar { display: none; }

/* ── Kachel ── */
.gr-kachel {
  /* DES-R7: `width:100%` zusammen mit der früheren inhaltsbasierten Spalte
     war eine der Ursachen des 45-px-Fehlers. Die Breite kommt jetzt aus
     `grid-auto-columns` der Spalte — die Kachel füllt sie nur aus. */
  width: auto;
  min-width: 0;
  max-width: 190px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  scroll-snap-align: start;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s;
  flex-shrink: 0;
  text-decoration: none;
  color: inherit;
  display: block;
  /* DES-03: Schatten aus Tokens — im Dunkelmodus eigene, kräftigere Werte.
     Vorher war der Schatten fest (kaum sichtbar auf dunklem Grund) und der
     Hover-Effekt hing an einem Inline-Handler, der beim Umbau auf <a> verloren
     ging (die Kachel reagierte nicht mehr auf die Maus). */
  box-shadow: var(--dk-shadow-xs);
}
/* DES-03: Hover und Tastaturfokus als CSS (kein Inline-Handler mehr). Der
   Fokusrahmen ist für Tastaturnutzer sichtbar, die Kachel ist ein Link. */
.gr-kachel:hover {
  border-color: var(--dk-border-strong);
  box-shadow: var(--dk-shadow-sm);
  transform: translateY(-2px);
}
.gr-kachel:focus-visible {
  outline: 2px solid var(--dk-accent);
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  .gr-kachel { transition: none; }
  .gr-kachel:hover { transform: none; }
}

.gr-kachel-img {
  height: 96px;
  position: relative;
  overflow: hidden;
}
/* DES-02: Bildfläche und Ersatzfarbe als Klasse statt style-Attribut. Die
   Farbe selbst kommt weiter aus den Daten (dienstbereich_farbe, DES-04). */
.gr-kachel-bild {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.gr-kachel-farbe {
  width: 100%;
  height: 100%;
  opacity: 0.85;
}

.gr-badge {
  position: absolute;
  top: 7px;
  right: 7px;
  background: rgba(0,0,0,0.55);
  color: white;
  font-size: 0.62rem;
  padding: 2px 7px;
  border-radius: 20px;
  backdrop-filter: blur(4px);
}

.gr-kachel-body {
  padding: 10px 12px;
}

.gr-kachel-name {
  font-weight: 600;
  font-size: 0.87rem;
  color: var(--dk-text);
  margin-bottom: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gr-typ-tag {
  font-size: 0.67rem;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  border: 1px solid var(--dk-border);
}

.gr-kachel-meta {
  font-size: 0.75rem;
  color: var(--dk-text-muted);
}

.gr-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
