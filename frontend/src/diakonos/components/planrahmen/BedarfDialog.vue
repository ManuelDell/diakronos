<template>
  <DkModal variant="planrahmen" v-model="offen" title="Daten einrichten?">
    <div class="pr-bd">
      <p class="pr-bd-intro">
        Für diesen Plan braucht das Programm noch Stammdaten. Was fehlt, ist hier aufgelistet.
        <strong>Überspringen heißt:</strong> das Feld bleibt leer oder wird nur von Hand gefüllt — mit Hinweis.
      </p>

      <div v-if="!merkmale.length && !sammlungen.length && !rollen.length" class="pr-bd-leer">
        Alles gepflegt — es fehlen keine Angaben oder Listen.
      </div>

      <!-- Fähigkeiten / Eigenschaften -->
      <section v-if="merkmale.length" class="pr-bd-gruppe">
        <h4 class="pr-bd-titel">Angaben der Personen ({{ merkmale.length }})</h4>
        <ul class="pr-bd-liste">
          <li v-for="e in merkmale" :key="schluessel(e)" class="pr-bd-eintrag" :class="{ 'pr-bd-eintrag--weg': uebersprungen.has(schluessel(e)) }">
            <span class="pr-bd-haupt">
              <span class="pr-bd-kennung">{{ e.name || e.kennung }}</span>
              <span class="pr-bd-abdeckung">{{ e.abdeckung }}</span>
              <span v-if="e.detail" class="pr-bd-detail">{{ e.detail }}</span>
            </span>
            <span class="pr-bd-neben">
              <span class="dk-badge" :class="einstufungKlasse(e.einstufung)">{{ einstufungText(e.einstufung) }}</span>
              <span v-if="uebersprungen.has(schluessel(e))" class="pr-bd-status">Übersprungen</span>
              <template v-else>
                <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="beschaeftigt" @click="einrichten(e)">Jetzt einrichten</button>
                <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" :disabled="beschaeftigt" @click="ueberspringen(e)">Überspringen</button>
              </template>
            </span>
          </li>
        </ul>
      </section>

      <!-- Listen -->
      <section v-if="sammlungen.length" class="pr-bd-gruppe">
        <h4 class="pr-bd-titel">Listen ({{ sammlungen.length }})</h4>
        <ul class="pr-bd-liste">
          <li v-for="e in sammlungen" :key="schluessel(e)" class="pr-bd-eintrag" :class="{ 'pr-bd-eintrag--weg': uebersprungen.has(schluessel(e)) }">
            <span class="pr-bd-haupt">
              <span class="pr-bd-kennung">{{ e.name || e.kennung }}</span>
              <span class="pr-bd-abdeckung">{{ e.abdeckung }}</span>
              <span v-if="e.detail" class="pr-bd-detail">{{ e.detail }}</span>
            </span>
            <span class="pr-bd-neben">
              <span class="dk-badge" :class="einstufungKlasse(e.einstufung)">{{ einstufungText(e.einstufung) }}</span>
              <span v-if="uebersprungen.has(schluessel(e))" class="pr-bd-status">Übersprungen</span>
              <template v-else>
                <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="beschaeftigt" @click="einrichten(e)">Jetzt einrichten</button>
                <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" :disabled="beschaeftigt" @click="ueberspringen(e)">Überspringen</button>
              </template>
            </span>
          </li>
        </ul>
      </section>

      <!-- Rollen: informationell (bilden sich aus Eigenschaften/Gruppen) -->
      <section v-if="rollen.length" class="pr-bd-gruppe">
        <h4 class="pr-bd-titel">Rollen ({{ rollen.length }})</h4>
        <ul class="pr-bd-liste">
          <li v-for="e in rollen" :key="schluessel(e)" class="pr-bd-eintrag pr-bd-eintrag--info">
            <span class="pr-bd-haupt">
              <span class="pr-bd-kennung">{{ e.name || e.kennung }}</span>
              <span class="pr-bd-abdeckung">{{ e.abdeckung }}</span>
            </span>
            <span class="pr-bd-neben">
              <span class="dk-badge" :class="einstufungKlasse(e.einstufung)">{{ einstufungText(e.einstufung) }}</span>
            </span>
          </li>
        </ul>
        <p class="pr-bd-fussnote">
          Rollen werden aus Gruppen und Eigenschaften gebildet — pflege die Angaben, dann erfüllt sich die Rolle von selbst.
        </p>
      </section>
    </div>

    <template #footer>
      <button
        v-if="fortsetzenText"
        type="button" class="dk-btn dk-btn-primary"
        :disabled="beschaeftigt"
        @click="fortsetzen"
      >{{ fortsetzenText }}</button>
      <button
        v-if="offeneEintraege.length"
        type="button" class="dk-btn dk-btn-ghost"
        :disabled="beschaeftigt"
        @click="alleUeberspringen"
      >Alle überspringen ({{ offeneEintraege.length }})</button>
      <button type="button" class="dk-btn dk-btn-secondary" :disabled="beschaeftigt" @click="schliessen">Schließen</button>
    </template>
  </DkModal>
</template>

<script setup>
/**
 * Bedarfs-Dialog (B5/P5): zeigt die Bedarfsprüfung des Servers
 * (Endpunkt bedarf — Liste {art, kennung, abdeckung, detail, einstufung})
 * und fragt pro fehlendem Merkmal/einer Sammlung: [Jetzt einrichten]
 * [Überspringen]. Nur Einträge mit einstufung !== 'ok' werden gezeigt;
 * übersprungene Einträge werden markiert und jederzeit nachpflegbar.
 *
 * Emits: 'einrichten' (Eintrag) zum Einrichten der Stammdaten,
 * 'ueberspringen' (Eintrag) zum Verschieben auf später,
 * 'fortsetzen' (ohne Argument) beim optionalen Footer-Button
 * fortsetzenText (z. B. „Trotzdem Plan anlegen“),
 * 'update:modelValue' zum Schließen.
 */
import { ref, computed, watch } from 'vue'
import DkModal from '../DkModal.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // Bedarfsliste aus api.bedarf: [{art, kennung, abdeckung, detail, einstufung}]
  bedarf: { type: Array, default: () => [] },
  // Optional: während einer laufenden Aktion Aktionen sperren.
  busy: { type: Boolean, default: false },
  // Optional: Footer-Button, der den Dialog schließt und 'fortsetzen' sendet.
  fortsetzenText: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'einrichten', 'ueberspringen', 'fortsetzen'])

const offen = computed({
  get: () => !!props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const beschaeftigt = computed(() => !!props.busy)

const uebersprungen = ref(new Set())

/** Eindeutiger Schlüssel: Merkmal und Sammlung dürfen dieselbe Kennung tragen. */
const schluessel = (e) => `${e?.art || ''}:${e?.kennung || ''}`

// Jeder Öffnung und jeder neuen Bedarfsliste gilt alles wieder als offen.
watch(() => props.modelValue, (an) => { if (an) uebersprungen.value = new Set() })
watch(() => props.bedarf, () => { uebersprungen.value = new Set() })

// Nur echte Lücken zeigen — 'ok' ist bereits ausreichend gepflegt.
const vonArt = (art) => (props.bedarf || []).filter((e) => (e?.art || '') === art && e?.einstufung !== 'ok')
const merkmale = computed(() => vonArt('merkmal'))
const sammlungen = computed(() => vonArt('sammlung'))
const rollen = computed(() => vonArt('rolle'))

/** Noch nicht behandelte Merkmale/Sammlungen (für „Alle überspringen“). */
const offeneEintraege = computed(() =>
    [...merkmale.value, ...sammlungen.value].filter((e) => !uebersprungen.value.has(schluessel(e))))

const EINSTUFUNG = {
    ok: { text: 'Ausreichend', klasse: 'dk-badge-success' },
    eingeschraenkt: { text: 'Unvollständig', klasse: 'dk-badge-warning' },
    // Nie blockiert der Plan — die Automatik kommt nur nicht mehr hinterher.
    blockiert_automatik: { text: 'Automatik eingeschränkt', klasse: 'dk-badge-danger' },
}
function einstufungText(einstufung) { return EINSTUFUNG[einstufung]?.text || einstufung || 'Prüfen' }
function einstufungKlasse(einstufung) { return EINSTUFUNG[einstufung]?.klasse || 'dk-badge' }

function einrichten(eintrag) {
    emit('einrichten', eintrag)
    schliessen()
}
function ueberspringen(eintrag) {
    uebersprungen.value = new Set(uebersprungen.value).add(schluessel(eintrag))
    emit('ueberspringen', eintrag)
}
function alleUeberspringen() {
    for (const eintrag of offeneEintraege.value) ueberspringen(eintrag)
    schliessen()
}
function fortsetzen() {
    schliessen()
    emit('fortsetzen')
}
function schliessen() { offen.value = false }

defineExpose({ merkmale, sammlungen, rollen, offeneEintraege, schluessel, einstufungText, einstufungKlasse, einrichten, ueberspringen, alleUeberspringen, fortsetzen, schliessen })
</script>

<style scoped>
.pr-bd { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.pr-bd-intro { font-size: 0.86rem; color: var(--dk-text-muted); margin: 0; line-height: 1.5; }
.pr-bd-leer { font-size: 0.88rem; color: var(--dk-text-muted); padding: 6px 0; }
.pr-bd-titel {
  font-size: 0.76rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 0 0 8px;
}
.pr-bd-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.pr-bd-eintrag {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; padding: 9px 12px;
  border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface);
}
.pr-bd-eintrag--weg { opacity: 0.6; }
.pr-bd-haupt { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.pr-bd-kennung { font-size: 0.88rem; font-weight: 600; color: var(--dk-text); }
.pr-bd-abdeckung { font-size: 0.8rem; color: var(--dk-text); }
.pr-bd-detail { font-size: 0.76rem; color: var(--dk-text-muted); }
.pr-bd-neben { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; }
.pr-bd-status { font-size: 0.78rem; font-style: italic; color: var(--dk-text-muted); }
.pr-bd-fussnote { font-size: 0.78rem; color: var(--dk-text-subtle); margin: 8px 0 0; }
</style>
