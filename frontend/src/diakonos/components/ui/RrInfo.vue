<template>
  <!--
    UI-R8: ⓘ „Was bewirkt <Rolle>?“ — der Text kommt AUS DER QUELLE
    (`api.rechte.get_rollen_erklaerung()`, gefiltert über rollenErklaerung.mjs).
    Hier steht KEIN Rollenwissen. Fehlt die Erklärung, erscheint kein Knopf:
    ein ⓘ, das nichts erklärt, ist schlimmer als keiner.

    UI-R8b — Aufbau der Zeile (gleiches Vorgehen in RollenRechte.vue und
    ZugangKarte.vue): die Rollenzeile ist `display: flex; flex-wrap: wrap`,
    der ⓘ steht direkt hinter dem Rollennamen, das Erklärfeld ist sein
    GESCHWISTER und bekommt mit `flex-basis: 100%` eine eigene volle Zeile
    darunter. Deshalb klappt hier in der Wurzel nichts auf und nichts
    schwebt: ein absolut gesetztes Feld wurde von `overflow: hidden` der
    Karte abgeschnitten und hätte im Dialog Querscrollen erzeugt.
  -->
  <template v-if="da">
    <DkButton
      :id="knopfId"
      ref="knopfEl"
      variant="ghost"
      size="sm"
      class="rr-info-knopf"
      :aria-label="beschriftung"
      :aria-expanded="offen ? 'true' : 'false'"
      aria-haspopup="dialog"
      :aria-controls="offen ? panelId : undefined"
      :title="beschriftung"
      @click="umschalten"
      @keydown.escape="knopfEscape($event)"
    >
      <span class="rr-info-zeichen" aria-hidden="true">i</span>
    </DkButton>

    <span
      v-if="offen"
      :id="panelId"
      ref="panelEl"
      class="rr-info-panel"
      role="dialog"
      :aria-labelledby="titelId"
      tabindex="-1"
      @keydown.escape.stop.prevent="schliessen(true)"
    >
      <span :id="titelId" class="rr-info-titel">{{ kopf }}</span>
      <span v-if="erklaerung.kurz" class="rr-info-kurz">{{ erklaerung.kurz }}</span>
      <template v-if="erklaerung.darf.length">
        <span class="rr-info-ueber">Darf</span>
        <ul class="rr-info-liste">
          <li v-for="(eintrag, i) in erklaerung.darf" :key="`d-${i}`">{{ eintrag }}</li>
        </ul>
      </template>
      <template v-if="erklaerung.darf_nicht.length">
        <span class="rr-info-ueber">Darf nicht</span>
        <ul class="rr-info-liste rr-info-liste--nein">
          <li v-for="(eintrag, i) in erklaerung.darf_nicht" :key="`n-${i}`">{{ eintrag }}</li>
        </ul>
      </template>
      <DkButton variant="ghost" size="sm" @click="schliessen(true)">Schließen</DkButton>
    </span>
  </template>
</template>

<script setup>
/**
 * RrInfo — der ⓘ-Knopf zu einer Rolle (UI-R8).
 *
 * Barrierefreiheit (Kartenauftrag): der Knopf heißt „Was bewirkt <Rolle>?“ und
 * öffnet ein Popover, das mit Escape schließt. Das Popover ist ein
 * `role="dialog"` mit Titel — in der Rollenauswahl steht es IN einem modalen
 * Dialog, darum darf es kein zweites `aria-modal` setzen; es nimmt nur den
 * Fokus und gibt ihn beim Schließen an den Knopf zurück.
 *
 * Escape am KNOPF wirkt nur, solange das Popover offen ist (Review R8-4):
 * sonst verschluckte ein geschlossener ⓘ das Escape des umgebenden Dialogs und
 * die Rückfrage ließe sich per Tastatur nicht mehr abbrechen.
 *
 * Kein eigener Knopf: es ist ein <DkButton> (UX1g2 — Alt-Knöpfe sind verboten),
 * nur rund gesetzt. Maße und Abstände kommen aus Tokens (UX1a/UX1c).
 *
 * Zwei Geschwister, keine Wurzel (UI-R8b): der ⓘ und das Erklärfeld liegen
 * direkt in der Rollenzeile der aufrufenden Ansicht. Eine eigene Wurzel um
 * beide hätte das Feld wieder in ein Inline-Element eingesperrt — genau daran
 * verschwand am Handy die Checkbox.
 */
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { normalisiereErklaerung } from '../../composables/rollenErklaerung.mjs'
import DkButton from './DkButton.vue'

const props = defineProps({
  /** Rollenname, wie er angezeigt wird (nur für die Beschriftung). */
  name: { type: String, required: true },
  /** Erklärung aus der Quelle (bereits normalisiert oder roh). */
  erklaerung: { type: Object, default: null },
})

/**
 * Eindeutige Kennung für Knopf, Feld und Titel. `useId()` je Instanz
 * (Vue ≥ 3.5, wie DkEndgueltig.vue) statt eines Modulzählers: der war pro
 * Bündel fortlaufend und damit doppelt, sobald zwei Bündel im selben Dokument
 * lagen — dann zeigten `aria-controls`/`aria-labelledby` auf das falsche Feld.
 */
const kennung = `rr-info-${useId()}`
const panelId = `${kennung}-panel`
const knopfId = `${kennung}-knopf`
const titelId = `${kennung}-titel`

const offen = ref(false)
const panelEl = ref(null)
const knopfEl = ref(null)

const erklaerung = computed(() => normalisiereErklaerung(props.erklaerung))
const da = computed(() => !!(erklaerung.value.kurz || erklaerung.value.darf.length
  || erklaerung.value.darf_nicht.length))
const kopf = computed(() => erklaerung.value.titel || props.name)

/**
 * UI-R8b: Weicht der Titel der Erklärung vom Rollennamen ab (die Checkbox
 * heißt „Mitgliederadministrator“, die Erklärung „Mitgliederverwaltung“), nennt
 * das aria-label BEIDE — sonst stünde am ⓘ ein Wort, das in der Zeile nicht
 * vorkommt, und ein Screenreader spräche von zwei verschiedenen Dingen.
 */
const beschriftung = computed(() => {
  const titel = kopf.value
  const name = String(props.name ?? '').trim()
  if (!name || name === titel) return `Was bewirkt ${titel}?`
  return `Was bewirkt ${name} (${titel})?`
})

function umschalten() {
  offen.value ? schliessen(true) : oeffnen()
}

async function oeffnen() {
  offen.value = true
  await nextTick()
  panelEl.value?.focus()
}

/** Schließen; mit `zurueck` bekommt der Knopf den Fokus wieder. */
function schliessen(zurueck = false) {
  if (!offen.value) return
  offen.value = false
  if (zurueck) knopfEl.value?.$el?.focus?.()
}

/**
 * Escape am Knopf: nur greifen, wenn das Popover offen ist. Ist es zu, bleibt
 * das Ereignis unangetastet — der umgebende Dialog schließt wie gewohnt.
 */
function knopfEscape(ereignis) {
  if (!offen.value) return
  ereignis?.stopPropagation?.()
  ereignis?.preventDefault?.()
  schliessen(true)
}

/** Klick außerhalb schließt — das Erklärfeld ist eine Lesehilfe, keine Sperre. */
function aussenKlick(ereignis) {
  if (!offen.value) return
  const ziel = ereignis.target
  if (panelEl.value && panelEl.value.contains(ziel)) return
  if (knopfEl.value?.$el && knopfEl.value.$el.contains(ziel)) return
  offen.value = false
}

watch(offen, (an) => {
  if (typeof document === 'undefined') return
  if (an) document.addEventListener('pointerdown', aussenKlick, true)
  else document.removeEventListener('pointerdown', aussenKlick, true)
})

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('pointerdown', aussenKlick, true)
})
</script>

<style scoped>
/* Der ⓘ-Knopf ist ein DkButton in „ghost“. Damit er in Ruhe als Bedienelement
   erkennbar ist (nicht als kursives „i“ im Text), trägt das Zeichen einen
   Kreis mit Rahmen und Textfarbe — Kontrast Rahmen/Fläche ≥ 3:1. */
.rr-info-knopf {
  flex-shrink: 0;
  border-radius: 50%;
  color: var(--text);
  cursor: help;
}
.rr-info-zeichen {
  display: inline-flex; align-items: center; justify-content: center;
  width: max(var(--fs-sm), var(--sp-4));
  border: var(--rahmen-breite) solid var(--muted);
  border-radius: var(--radius-sm);
  font-style: italic; font-size: var(--fs-sm); line-height: 1;
}
.rr-info-knopf:hover,
.rr-info-knopf:focus-visible { color: var(--text); }
.rr-info-knopf:hover .rr-info-zeichen,
.rr-info-knopf:focus-visible .rr-info-zeichen { border-color: var(--text); }
.rr-info-knopf[aria-expanded="true"] .rr-info-zeichen { border-color: var(--text); }

/* Erklärfeld: Tokens statt Hartwerte. Es schwebt NICHT (UI-R8b): als absolut
   gesetztes Feld ragte es aus der Karte (DkCard hat `overflow: hidden`) und
   wurde abgeschnitten; im Rollen-Dialog (Körper `overflow: auto`) hätte es
   Querscrollen erzeugt. Es ist eine eigene volle Zeile UNTER der Rollenzeile —
   auf allen Breiten gleich. Die Zeile drumherum ist `flex-wrap: wrap`
   (RollenRechte.vue/ZugangKarte.vue); `flex-basis: 100%` macht daraus die
   volle Zeile. `min-width: 0` und `overflow-wrap: anywhere` halten lange
   Rollennamen im Feld. */
.rr-info-panel {
  flex: 1 0 100%; box-sizing: border-box;
  min-width: 0; max-width: 100%;
  display: flex; flex-direction: column; align-items: flex-start;
  gap: var(--sp-1);
  padding: var(--sp-3);
  width: 100%;
  background: var(--surface); color: var(--text);
  border: var(--rahmen-breite) solid var(--rahmen-farbe-sanft);
  border-radius: var(--radius);
  box-shadow: var(--schatten-karte);
  font-size: var(--fs-sm); line-height: 1.45;
  text-align: left;
  overflow-wrap: anywhere;
}
.rr-info-titel { font-weight: var(--fw-fett); }
.rr-info-kurz { color: var(--text); }
.rr-info-ueber {
  color: var(--muted);
  font-size: var(--fs-sm); font-weight: var(--fw-fett);
  text-transform: uppercase; letter-spacing: 0.04em;
}
.rr-info-liste {
  padding-left: var(--sp-4);
  display: flex; flex-direction: column; gap: var(--sp-1);
}
.rr-info-liste--nein { color: var(--muted); }
</style>
