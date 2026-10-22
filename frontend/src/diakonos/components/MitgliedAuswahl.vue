<template>
  <div ref="wurzel" class="dk-ma">
    <!-- Eingabefeld: oeffnet die Liste sofort beim Draufklicken/Fokussieren. -->
    <div class="dk-ma-feld">
      <svg class="dk-ma-lupe" width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        ref="eingabe"
        v-model="suche"
        type="text"
        class="dk-ma-input"
        :placeholder="platzhalter"
        :aria-label="ariaLabel || platzhalter"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="offen ? 'true' : 'false'"
        autocomplete="off"
        @click="oeffnen()"
        @focus="oeffnen()"
        @keydown.down.prevent="weiter(1)"
        @keydown.up.prevent="weiter(-1)"
        @keydown.enter.prevent="auswaehlenAktiv()"
        @keydown.esc="offen = false"
      />
      <span v-if="laedt" class="dk-ma-lade" aria-hidden="true"></span>
    </div>

    <!-- Vorschlagsliste -->
    <ul v-if="offen" class="dk-ma-liste" role="listbox" :aria-label="ariaLabel || platzhalter">
      <li v-if="fehler" class="dk-ma-hinweis dk-ma-hinweis--fehler">
        {{ fehler }}
        <button type="button" class="dk-ma-wiederholen" @mousedown.prevent="laden()">Erneut versuchen</button>
      </li>
      <li v-else-if="!gefiltert.length" class="dk-ma-hinweis">
        {{ suche ? 'Kein Mitglied gefunden.' : 'Keine Mitglieder vorhanden.' }}
      </li>
      <li
        v-for="(m, i) in gefiltert"
        :key="m.mitglied"
        class="dk-ma-eintrag"
        :class="{ 'is-aktiv': i === aktivIndex, 'is-drin': m.in_gruppe }"
        role="option"
        :aria-selected="i === aktivIndex ? 'true' : 'false'"
        @mousedown.prevent="waehle(m)"
      >
        <span class="dk-ma-name">{{ m.name }}</span>
        <span v-if="m.in_gruppe" class="dk-ma-drin">bereits in der Gruppe</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
/**
 * MitgliedAuswahl — suchbare Auswahlliste aller Mitglieder (BF1-E).
 *
 * Der Live-Test verlangte, dass „Mitglieder hinzufügen“ aus einer
 * Dropdown-/Suchliste erfolgt, die beim Draufklicken SOFORT aufgeht (nicht
 * erst nach dem Tippen). Die Liste zeigt NUR den Namen (und ob die Person
 * schon in der Gruppe ist) — keine E-Mail, keine Adressdaten (B-1).
 * Wer die Liste sehen darf, entscheidet der Server; ein Fehler wird hier im
 * Feld angezeigt, nie still verschluckt.
 *
 * B-2: Bei einer Gemeinde mit mehr als 50 Mitgliedern reicht eine lokale
 * Filterung ueber die ersten 50 Eintraege nicht. Deshalb filtert der SERVER:
 * das Tippen wird entprellt und `ladeOptionen(suche)` erneut aufgerufen. Der
 * Aufruf ohne Suchbegriff laedt die ersten Treffer, damit die Liste beim
 * Klick sofort etwas zeigt.
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { suchNormal } from '../composables/bf1Anzeige.js'

const props = defineProps({
  // (suche?: string) => Promise<Array<{mitglied,name,in_gruppe}>>
  ladeOptionen: { type: Function, required: true },
  platzhalter: { type: String, default: 'Mitglied suchen…' },
  ariaLabel: { type: String, default: '' },
  entprellungMs: { type: Number, default: 250 },
})
const emit = defineEmits(['ausgewaehlt'])

const wurzel = ref(null)
const eingabe = ref(null)
const suche = ref('')
const alle = ref([])
const laedt = ref(false)
const fehler = ref('')
const offen = ref(false)
const aktivIndex = ref(0)

/** Umlaut-/gross-klein-unabhaengiger Vergleich (BF1-J) — Feinfilter. */
function normal(s) {
  return suchNormal(s)
}

/**
 * Feinfilter ueber die vom Server gelieferten Treffer. Der Server filtert
 * bereits; hier bleibt die Normalisierung, damit ein Server mit abweichender
 * LIKE-Semantik trotzdem gleich erscheint. Die E-Mail ist bewusst KEIN
 * Suchfeld mehr (B-1: kein Seitenkanal auf ein maskiertes Adressbuchfeld).
 */
const gefiltert = computed(() => {
  const woerter = normal(suche.value).split(/\s+/).filter(Boolean)
  const liste = alle.value.filter((m) => woerter.every(wort => normal(m.name).includes(wort)))
  // Bereits enthaltene Mitglieder nach hinten, damit Neuzugänge oben stehen.
  return liste.slice().sort((a, b) => (a.in_gruppe ? 1 : 0) - (b.in_gruppe ? 1 : 0))
})

async function laden(mitSuche = suche.value) {
  laedt.value = true
  fehler.value = ''
  try {
    alle.value = (await props.ladeOptionen(mitSuche || '')) || []
  } catch (e) {
    fehler.value = e?.message || 'Mitglieder konnten nicht geladen werden.'
    alle.value = []
  } finally {
    laedt.value = false
  }
}

let entprellung = null
watch(suche, () => {
  aktivIndex.value = 0
  if (!offen.value) oeffnen()
  // B-2: der Server soll filtern, aber nicht bei jedem Tastendruck.
  if (entprellung) clearTimeout(entprellung)
  entprellung = setTimeout(() => laden(), props.entprellungMs)
})

function oeffnen() {
  offen.value = true
  // Beim ersten Oeffnen sofort die ersten Treffer laden.
  if (!alle.value.length && !laedt.value && !fehler.value) laden()
}

function weiter(schritt) {
  if (!offen.value) { oeffnen(); return }
  if (!gefiltert.value.length) return
  const n = gefiltert.value.length
  aktivIndex.value = (aktivIndex.value + schritt + n) % n
}

function auswaehlenAktiv() {
  // K5: Enter bei geschlossener Liste darf nicht den ersten Eintrag
  // hinzufuegen — tippen ohne sichtbare Auswahl ist kein Auswaehlen.
  if (!offen.value) return
  const m = gefiltert.value[aktivIndex.value]
  if (m) waehle(m)
}

function waehle(m) {
  emit('ausgewaehlt', m)
  suche.value = ''
  offen.value = false
}

function beiKlickAussen(e) {
  if (wurzel.value && !wurzel.value.contains(e.target)) offen.value = false
}
onMounted(() => document.addEventListener('mousedown', beiKlickAussen))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', beiKlickAussen)
  if (entprellung) clearTimeout(entprellung)
})

defineExpose({ neuLaden: () => laden(''), fokussieren: () => eingabe.value?.focus() })
</script>

<style scoped>
.dk-ma { position: relative; width: 100%; }
.dk-ma-feld { position: relative; display: flex; align-items: center; }
.dk-ma-lupe {
  position: absolute; left: 10px; color: var(--muted); pointer-events: none;
}
.dk-ma-input {
  width: 100%;
  height: var(--control-h, 34px);
  padding: 0 12px 0 32px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs);
  box-sizing: border-box;
}
.dk-ma-input:focus {
  outline: 2px solid var(--focus-ring);
  outline-offset: 0;
  border-color: var(--dk-navy-400);
}
.dk-ma-lade {
  position: absolute; right: 10px;
  width: 13px; height: 13px;
  border: 2px solid var(--line); border-top-color: var(--primary);
  border-radius: 50%; animation: dk-ma-spin .7s linear infinite;
}
@keyframes dk-ma-spin { to { transform: rotate(360deg); } }

.dk-ma-liste {
  position: absolute;
  z-index: var(--z-dropdown, 20);
  top: calc(100% + 4px);
  left: 0; right: 0;
  max-height: 260px;
  overflow-y: auto;
  margin: 0; padding: 4px;
  list-style: none;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
}
.dk-ma-eintrag {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.dk-ma-eintrag:hover,
.dk-ma-eintrag.is-aktiv { background: var(--surface-hover); }
.dk-ma-eintrag.is-drin { opacity: .6; }
.dk-ma-name { font-weight: 550; color: var(--text); }
.dk-ma-drin {
  margin-left: auto;
  font-size: var(--fs-xs, 11px);
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 0 8px;
}
.dk-ma-hinweis { padding: 8px 10px; color: var(--muted); font-size: var(--fs-sm); }
.dk-ma-hinweis--fehler { color: var(--err); }
.dk-ma-wiederholen {
  margin-left: 8px;
  background: none; border: none; padding: 0;
  color: var(--primary); font: inherit; font-size: var(--fs-sm);
  text-decoration: underline; cursor: pointer;
}
</style>
