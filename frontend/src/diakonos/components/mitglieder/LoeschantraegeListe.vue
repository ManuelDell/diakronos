<template>
  <!-- DSGVO-2c: die Arbeitsliste der Verwaltung. Eine Zeile je Antrag:
       wer, seit wann, welcher Stand — und je nach Stand „Löschung freigeben“
       bzw. „Ablehnen“. Keine Spalte, kein Fachbegriff: Ehrenamtliche sollen
       ohne Erklärung wissen, was zu tun ist. -->
  <DkCard title="Löschanträge">
    <template #actions>
      <DkButton v-if="!embedded" variant="ghost" size="sm" :disabled="laedt" @click="laden">
        Aktualisieren
      </DkButton>
    </template>

    <div class="la-kopf">
      <p class="la-text">
        Eine Person hat beantragt, ihre Daten löschen zu lassen. Du prüfst den
        Antrag und gibst ihn frei — erst dann wird gelöscht.
      </p>
      <span v-if="offenAnzahl" class="la-zaehler" role="status">
        {{ offenAnzahl }} {{ offenAnzahl === 1 ? 'Antrag wartet' : 'Anträge warten' }} auf Bearbeitung
      </span>
    </div>

    <!-- Ohne eingerichteten Mailversand geht weder Freigeben noch Ablehnen:
         die Person MUSS vorher informiert werden (Server: fail closed). -->
    <DkHint v-if="!mailEingerichtet" variant="warn" role="status">
      Mailversand ist noch nicht eingerichtet — ohne ihn können Löschanträge
      weder freigegeben noch abgelehnt werden.
      <a href="#/einstellungen/mailversand">Mailversand einrichten</a>
    </DkHint>

    <!-- DES-01/S9: EINE Filterzeile für alle (DkFilterChips), keine
         handgebauten Knöpfe. „Offen“ ist die Arbeitsliste — hier ist der
         Ruhezustand deshalb NICHT „alle“. -->
    <DkFilterChips
      class="la-filter"
      :chips="ANTRAG_FILTER.map(f => ({ id: f.wert, label: f.text }))"
      :model-value="filter"
      :mit-zahl="false"
      aria-label="Anträge filtern"
      @waehlen="filterWechseln"
    />

    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <p v-if="laedt && !geladen" role="status">Löschanträge werden geladen…</p>

    <DkEmpty
      v-else-if="geladen && !antraege.length"
      title="Keine Löschanträge"
      :text="filter === 'offen'
        ? 'Zurzeit wartet kein Antrag auf Bearbeitung.'
        : 'Für diese Auswahl gibt es keine Anträge.'"
      icon="✓"
    />

    <ul v-else-if="geladen" class="la-liste">
      <li v-for="a in antraege" :key="a.mitglied" class="la-zeile">
        <div class="la-person">
          <span class="la-name">{{ nameFuerAntrag(a) }}</span>
          <p class="la-meta">
            <span>{{ beantragtText(a) }}</span>
            <span class="la-stand" :class="'is-' + antragsStatusText(a).ton">
              {{ standText(a) }}
            </span>
          </p>
          <p v-if="a.email" class="la-mail">{{ a.email }}</p>
          <!-- Eine Ablehnung ist eine Entscheidung: die Begründung bleibt lesbar. -->
          <p v-if="a.status === 'abgelehnt' && a.ablehnung_grund" class="la-grund">
            <strong>Begründung:</strong> {{ a.ablehnung_grund }}
          </p>
        </div>
        <div v-if="a.status === 'offen'" class="la-aktionen">
          <DkButton
            variant="secondary"
            size="sm"
            :aria-label="'Löschantrag ablehnen: ' + nameFuerAntrag(a)"
            @click="$emit('ablehnen', a)"
          >
            Ablehnen
          </DkButton>
          <DkButton
            variant="danger"
            size="sm"
            :aria-label="'Löschung freigeben: ' + nameFuerAntrag(a)"
            @click="$emit('freigeben', a)"
          >
            Löschung freigeben
          </DkButton>
        </div>
      </li>
    </ul>
  </DkCard>
</template>

<script setup>
/**
 * LoeschantraegeListe — Verwaltungsliste „Löschanträge“ (DSGVO-2c).
 *
 * Die Komponente ist dumm: sie zeigt, was der Server geliefert hat, und meldet
 * Absichten nach oben (`freigeben`, `ablehnen`, `filter`). Die API-Aufrufe und
 * die Dialoge liegen bei der Seite (`pages/mitglieder/Loeschantraege.vue`) —
 * dieselbe Aufteilung wie bei `AustrittDialog`/`LoeschantragKarte`.
 *
 * Was hier NICHT entschieden wird: ob jemand freigeben darf. Die Knöpfe
 * erscheinen für OFFENE Anträge, weil die Seite sie nur Verwaltungskonten
 * überhaupt ausliefert; der Server prüft jedes Recht erneut (403).
 */
import {
  ANTRAG_FILTER, antragsStatusText, beantragtText, nameFuerAntrag,
} from './loeschantraege.mjs'
import { computed } from 'vue'
import DkCard from '../ui/DkCard.vue'
import DkButton from '../ui/DkButton.vue'
import DkHint from '../ui/DkHint.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkFilterChips from '../ui/DkFilterChips.vue'

const props = defineProps({
  antraege: { type: Array, default: () => [] },
  laedt: { type: Boolean, default: false },
  geladen: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
  filter: { type: String, default: 'offen' },
  mailEingerichtet: { type: Boolean, default: true },
  /** Eingebettet im Mitglieder-Bereich: kein eigener „Aktualisieren“-Knopf nötig. */
  embedded: { type: Boolean, default: false },
})
const emit = defineEmits(['freigeben', 'ablehnen', 'filter'])

/**
 * Zähler offener Anträge: die Liste unter „Offen“ IST die Arbeitsliste. Bei
 * jeder anderen Auswahl sagt der Count nichts über die offenen Anträge —
 * dann bleibt der Hinweis aus, statt eine falsche Zahl zu zeigen.
 */
const offenAnzahl = computed(
  () => (props.filter === 'offen' && props.geladen ? props.antraege.length : 0),
)

function standText(a) {
  const stand = antragsStatusText(a)
  if (stand.am) return `${stand.text} · ${stand.am}`
  return stand.text
}

function filterWechseln(wert) {
  // DkFilterChips schaltet einen zweiten Klick auf denselben Chip ab
  // (`naechsterChip` → leer). Hier gibt es keinen Ruhezustand: ein Klick auf
  // „Offen“ bleibt „Offen“, statt eine leere Auswahl zu schicken.
  const ziel = wert || props.filter
  if (ziel === props.filter) return
  emit('filter', ziel)
}
</script>

<style scoped>
.la-kopf { display: grid; gap: var(--sp-2); margin-bottom: var(--sp-3); }
.la-text { margin: 0; color: var(--text); line-height: 1.55; }
.la-zaehler {
  display: inline-block;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--warn);
}
.la-filter { margin: var(--sp-3) 0; }
.la-liste { list-style: none; margin: 0; padding: 0; }
.la-zeile {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--divider);
  flex-wrap: wrap;
}
.la-zeile:first-child { border-top: none; }
.la-person { min-width: 0; overflow-wrap: anywhere; }
.la-name { font-weight: 600; }
.la-meta { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin: var(--sp-1) 0 0; color: var(--muted); font-size: var(--fs-sm); }
.la-stand { font-weight: 600; }
.la-stand.is-warn { color: var(--warn); }
.la-stand.is-ok { color: var(--ok); }
.la-stand.is-neutral, .la-stand.is-info { color: var(--muted); }
.la-mail, .la-grund { margin: var(--sp-1) 0 0; font-size: var(--fs-sm); color: var(--muted); }
.la-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
@media (max-width: 600px) { .la-aktionen { width: 100%; } }
</style>
