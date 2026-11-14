<template>
  <!-- UI-R9 · „Meine Aufgaben“ — eigene Aufgaben und mir zugewiesene
       Gruppenaufgaben. Die Karte rechnet die Liste NICHT selbst aus: sie holt
       `get_meine_aufgaben` (der Server entscheidet, was zu sehen ist) und
       blendet nur aus, was er ohnehin verweigert (`darf_abhaken` /
       `darf_bearbeiten`). -->
  <BaseWidgetCard
    label="Meine Aufgaben"
    gridSize="medium"
    :loading
    :error
    :badgeCount="anzahl"
    :isEditing="props.isEditing"
    @refresh="laden"
    @hide="$emit('hide')"
    @collapse-change="$emit('collapse-change', $event)"
  >
    <!-- Neue EIGENE Aufgabe -->
    <div v-if="darfAnlegen" class="ma-neu">
      <div v-if="!neuOffen" class="ma-neu-zeile">
        <DkButton variant="secondary" size="md" @click="neuOeffnen">
          <DkSymbol name="hinzufuegen" /> Eigene Aufgabe
        </DkButton>
      </div>
      <form v-else class="ma-form" @submit.prevent="anlegen">
        <DkField label="Was ist zu tun?">
          <input
            v-model="neuerTitel"
            ref="titelFeld"
            class="dk-ui-eingabe"
            type="text"
            maxlength="200"
            placeholder="z. B. Noten für den Chor kopieren"
          />
        </DkField>
        <DkField label="Fällig am (optional)">
          <input v-model="neuesFaellig" class="dk-ui-eingabe" type="date" />
        </DkField>
        <p v-if="neuFehler" class="ma-fehler" role="alert">{{ neuFehler }}</p>
        <div class="ma-aktionen">
          <DkButton
            variant="primary"
            size="md"
            type="submit"
            :disabled="!neuerTitel.trim() || sendet"
            :loading="sendet"
          >Anlegen</DkButton>
          <DkButton variant="secondary" size="md" @click="neuSchliessen">Abbrechen</DkButton>
        </div>
      </form>
    </div>

    <!-- Offene Aufgaben: eigene zuerst, darunter die zugewiesenen Gruppenaufgaben -->
    <!-- Leerzustand UNTER dem Knopf: die Karte selbst meldet NICHT „leer“
         (`isEmpty`), sonst zeigt BaseWidgetCard nur die Leermeldung und der
         Knopf „Eigene Aufgabe“ verschwände — genau dann, wenn er gebraucht wird.
         UI-R9c: der Hinweis „Eigene Aufgaben legst du hier an“ steht nur, wenn
         man das auch darf — sonst verspricht er einen Knopf, den es nicht gibt. -->
    <p v-if="!offen.length && !erledigt.length" class="ma-muted">
      {{ darfAnlegen
        ? 'Keine Aufgaben. Eigene Aufgaben legst du hier an; Gruppenaufgaben erscheinen, sobald sie dir zugewiesen sind.'
        : 'Keine Aufgaben. Gruppenaufgaben erscheinen hier, sobald sie dir zugewiesen sind.' }}
    </p>
    <ul v-if="offen.length" class="ma-liste">
      <li v-for="a in offen" :key="a.name" class="ma-zeile">
        <DkCheckbox
          :model-value="!!a.erledigt"
          :disabled="!darfAbhaken(a) || busy === a.name"
          :aria-label="`„${a.titel}“ erledigt`"
          @update:model-value="abhaken(a)"
        />
        <div class="ma-haupt">
          <span class="ma-titel">{{ a.titel }}</span>
          <span class="ma-meta">
            <span v-if="a.eigene" class="ma-herkunft">Eigene Aufgabe</span>
            <a v-else-if="gruppenHref(a)" :href="gruppenHref(a)" class="ma-link" :aria-label="gruppenName(a) || 'Gruppe'">{{ gruppenName(a) }}</a>
            <span v-if="zuweisungsText(a)" class="ma-zuweisung">{{ zuweisungsText(a) }}</span>
            <span v-if="faelligkeit(a).text" :class="['ma-frist', { 'is-ueberfaellig': faelligkeit(a).ueberfaellig }]">
              {{ faelligkeit(a).text }}
            </span>
          </span>
        </div>
        <DkAktionen
          v-if="darfBearbeiten(a)"
          :eintraege="aktionenFuer(a)"
          :label="`Aktionen für „${a.titel}“`"
        />
      </li>
    </ul>
    <!-- UI-R9c: Die Meldung gehört zu „alles erledigt“ — vorher war die
         Bedingung vertauscht (sie stand, wenn Aufgaben OFFEN waren). -->
    <p v-if="!offen.length && erledigt.length" class="ma-muted">Nichts offen — gute Arbeit.</p>

    <!-- Erledigte einklappbar (Knopf aus der UI-Bibliothek, keine Eigenklasse) -->
    <div v-if="erledigt.length" class="ma-erledigt">
      <DkButton ref="erledigtKnopf" variant="ghost" size="md" @click="zeigeErledigte = !zeigeErledigte">
        {{ erledigt.length === 1 ? '1 erledigte Aufgabe' : `${erledigt.length} erledigte Aufgaben` }}
        {{ zeigeErledigte ? 'ausblenden' : 'anzeigen' }}
      </DkButton>
      <ul v-if="zeigeErledigte" class="ma-liste ma-liste-erledigt">
        <li v-for="a in erledigt" :key="a.name" class="ma-zeile">
          <DkCheckbox
            :model-value="true"
            :disabled="!darfAbhaken(a) || busy === a.name"
            :aria-label="`„${a.titel}“ wieder öffnen`"
            @update:model-value="abhaken(a)"
          />
          <div class="ma-haupt">
            <span class="ma-titel is-erledigt">{{ a.titel }}</span>
            <span class="ma-meta">
              <span v-if="a.eigene" class="ma-herkunft">Eigene Aufgabe</span>
              <a v-else-if="gruppenHref(a)" :href="gruppenHref(a)" class="ma-link" :aria-label="gruppenName(a) || 'Gruppe'">{{ gruppenName(a) }}</a>
            </span>
          </div>
          <DkAktionen
            v-if="darfBearbeiten(a)"
            :eintraege="aktionenFuer(a)"
            :label="`Aktionen für „${a.titel}“`"
          />
        </li>
      </ul>
    </div>
  </BaseWidgetCard>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import BaseWidgetCard from './BaseWidgetCard.vue'
import DkButton from '../ui/DkButton.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkField from '../ui/DkField.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { aktionsfehler } from '../../../shared/fehlertexte.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import {
  darfAbhaken, darfBearbeiten, teileNachErledigt, zuweisungsText, faelligkeit,
  gruppenHref, gruppenName, darfEigeneAnlegen,
} from '../../composables/aufgaben.mjs'

const props = defineProps({
  isEditing: { type: Boolean, default: false },
})
defineEmits(['hide', 'collapse-change'])

const aufgaben = ref([])
// UI-R9b: `darf_anlegen` kommt aus `get_meine_aufgaben` (Server-Flag) — die
// frühere Herleitung aus `module_sichtbar` war geraten und traf nicht das
// Recht, das `create_aufgabe` tatsächlich prüft.
const rechte = ref({ darf_eigene_aufgabe: false })
const loading = ref(true)
const error = ref(null)
const zeigeErledigte = ref(false)
const busy = ref('')

const neuOffen = ref(false)
const neuerTitel = ref('')
const neuesFaellig = ref('')
const neuFehler = ref('')
const sendet = ref(false)
const titelFeld = ref(null)
// UI-R9c: Ziel des Fokus, wenn keine offene Zeile mehr da ist.
const erledigtKnopf = ref(null)

const geteilt = computed(() => teileNachErledigt(aufgaben.value))
const offen = computed(() => geteilt.value.offen)
const erledigt = computed(() => geteilt.value.erledigt)
// Bewusst KEIN `isEmpty` an die Karte: der Leerzustand steht im Slot (s. o.).
const anzahl = computed(() => offen.value.length + erledigt.value.length)
const darfAnlegen = computed(() => darfEigeneAnlegen(rechte.value))

/**
 * Laden.
 *
 * `still` = Nachladen im Hintergrund: KEIN Skelett (`loading` bleibt false),
 * damit Abhaken und Scrollposition nicht springen. Scheitert es, bleibt die
 * bereits gezeigte Liste stehen (eine Meldung im Hintergrund wäre Lärm).
 */
async function laden({ still = false } = {}) {
  if (!still) {
    loading.value = true
    error.value = null
  }
  try {
    const res = await apiCall('diakronos.diakonos.api.gruppen.get_meine_aufgaben')
    aufgaben.value = Array.isArray(res?.data) ? res.data : []
    rechte.value = { darf_eigene_aufgabe: res?.darf_anlegen === true }
  } catch (e) {
    if (still) return
    error.value = aktionsfehler('laden', e)
    aufgaben.value = []
  } finally {
    if (!still) loading.value = false
  }
}

async function abhaken(a) {
  if (!darfAbhaken(a) || busy.value) return
  busy.value = a.name
  const vorher = !!a.erledigt
  try {
    const res = await apiCall('diakronos.diakonos.api.gruppen.toggle_aufgabe', { aufgabe_id: a.name })
    if (res?.success) {
      // Sofort umschalten (die Liste teilt sich über `erledigt` selbst neu)
      // und STILL nachladen — kein Skelett, kein Sprung.
      a.erledigt = !!res.erledigt
      await laden({ still: true })
      // UI-R9c: die abgehakte Zeile verschwindet — ohne Ziel fiele der Fokus
      // auf <body>. Erst NACH dem Nachladen setzen: `laden` schreibt die Zeilen
      // neu, ein Fokus auf das alte Element wäre sofort wieder weg.
      await nextTick()
      fokusNachAbhaken(a)
    } else {
      a.erledigt = vorher
      showToast(aktionsfehler('speichern', res), 'error')
    }
  } catch (e) {
    a.erledigt = vorher
    showToast(aktionsfehler('speichern', e), 'error')
  } finally {
    busy.value = ''
  }
}

/**
 * Fokus nach dem Abhaken (UI-R9c).
 *
 * Die abgehakte Zeile wandert aus der offenen Liste, ihr Kästchen ist weg.
 * Ziel ist deshalb die nächste offene Zeile, sonst der Knopf „Erledigte
 * anzeigen“ — ein definierter Platz statt des `<body>`, an dem Tastatur und
 * Vorleseprogramm die Stelle verlieren.
 */
function fokusNachAbhaken(a) {
  const inOffen = offen.value.some((x) => x.name === a?.name && !x.erledigt)
  if (inOffen) return // aufgeklappt (wieder geöffnet): die Zeile steht noch da
  const naechste = offen.value[0]
  const zeilen = document.querySelectorAll('.ma-liste .ma-zeile')
  let ziel = null
  if (naechste) {
    for (const zeile of zeilen) {
      const input = zeile.querySelector('input[type="checkbox"]')
      if (input?.getAttribute('aria-label') === `„${naechste.titel}“ erledigt`) {
        ziel = input
        break
      }
    }
  }
  if (!ziel) ziel = erledigtKnopf.value
  if (ziel && typeof ziel.focus === 'function') ziel.focus()
}

function aktionenFuer(a) {
  const eintraege = []
  if (!a.eigene) {
    eintraege.push({
      key: 'gruppe', label: 'Zur Gruppe', icon: 'gruppe',
      aktion: () => { window.location.hash = gruppenHref(a) },
    })
  }
  eintraege.push({
    key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true,
    aktion: () => loeschen(a),
  })
  return eintraege
}

async function loeschen(a) {
  const ok = await bestaetigen({
    titel: 'Aufgabe löschen?',
    text: `„${a.titel}“ wird endgültig entfernt. Das lässt sich nicht rückgängig machen.`,
    aktion: 'Löschen',
    gefahr: true,
  })
  if (!ok) return
  try {
    const res = await apiCall('diakronos.diakonos.api.gruppen.delete_aufgabe', { aufgabe_id: a.name })
    if (res?.success) {
      showToast('Aufgabe gelöscht')
      // Still nachladen: kein Skelett, die Zeile verschwindet ohne Sprung.
      await laden({ still: true })
    } else {
      showToast(aktionsfehler('loeschen', res), 'error')
    }
  } catch (e) {
    showToast(aktionsfehler('loeschen', e), 'error')
  }
}

function neuOeffnen() {
  neuOffen.value = true
  neuFehler.value = ''
  nextTick(() => titelFeld.value?.focus())
}

function neuSchliessen() {
  neuOffen.value = false
  neuerTitel.value = ''
  neuesFaellig.value = ''
  neuFehler.value = ''
}

async function anlegen() {
  const titel = neuerTitel.value.trim()
  if (!titel || sendet.value) return
  sendet.value = true
  neuFehler.value = ''
  try {
    // Ohne Gruppe = eigene Aufgabe (so verlangt es der Server; `zugewiesen_an`
    // wäre hier ausdrücklich verboten).
    const res = await apiCall('diakronos.diakonos.api.gruppen.create_aufgabe', {
      titel,
      faellig: neuesFaellig.value || null,
    })
    if (res?.success) {
      neuSchliessen()
      showToast('Aufgabe angelegt', 'success')
      // Still nachladen: die neue Zeile erscheint, ohne dass die Karte blinkt.
      await laden({ still: true })
    } else {
      neuFehler.value = aktionsfehler('anlegen', res)
    }
  } catch (e) {
    neuFehler.value = aktionsfehler('anlegen', e)
  } finally {
    sendet.value = false
  }
}

onMounted(() => {
  laden()
})
</script>

<style scoped>
/* Nur Tokens, keine Hartwerte (Prinzip der UI-Bibliothek). */
.ma-neu { margin-bottom: var(--sp-3); }
.ma-neu-zeile { display: flex; }
.ma-form { display: flex; flex-direction: column; gap: var(--sp-2); }
.ma-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.ma-fehler { color: var(--danger, var(--err)); font-size: var(--fs-sm); margin: 0; }
.ma-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.ma-zeile {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.ma-zeile:last-child { border-bottom: none; }
.ma-haupt { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.ma-titel { color: var(--text); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.ma-titel.is-erledigt { text-decoration: line-through; color: var(--muted); }
.ma-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); font-size: var(--fs-xs); color: var(--muted); }
.ma-herkunft { font-weight: var(--fw-fett); }
.ma-link { color: var(--primary); text-decoration: none; }
.ma-link:hover { text-decoration: underline; }
.ma-frist.is-ueberfaellig { color: var(--err); font-weight: var(--fw-fett); }
.ma-muted { color: var(--muted); font-size: var(--fs-sm); margin: var(--sp-2) 0; }
.ma-erledigt { margin-top: var(--sp-3); border-top: var(--rahmen-breite) solid var(--rahmen-farbe); padding-top: var(--sp-2); }
.ma-liste-erledigt { margin-top: var(--sp-1); }
/* Am Handy bricht die Zeile sauber um; am Laptop bleibt sie eine Zeile. */
@media (max-width: 720px) {
  .ma-zeile { flex-wrap: wrap; }
}
</style>
