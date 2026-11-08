<template>
  <!-- UX3i (Entwurf A4, Punkt 5): „Meine Kalender“ ist KEIN dunkler Block in
       der Seite mehr, sondern ein Popover am Knopf „Kalender“ der Kopfzeile.
       Jede Zeile: Farbpunkt, Name, Kästchen; das Schreibrecht steht als
       dezentes Symbol mit Tooltip (vorher der Text „Eintragen erlaubt“ in
       jeder Zeile, der bei „Gemeindeleben“ über den Rand lief). -->
  <Teleport to="body">
    <div v-if="open" class="dk-kal-pop-ebene" @click.self="$emit('schliessen')">
      <div
        ref="flaeche"
        class="dk-kal-pop"
        role="dialog"
        aria-modal="false"
        :aria-label="'Kalender auswählen'"
        :style="lage"
        tabindex="-1"
        @keydown.esc.stop.prevent="$emit('schliessen')"
      >
        <p class="dk-kal-pop-titel">Meine Kalender</p>

        <DkSkelett v-if="loading" kurz form="zeilen" :anzahl="3" text="Kalender werden geladen" />

        <!-- ON-4 (H3): Gibt es noch GAR KEINEN Kalender, wird der Einstieg
             angeboten; sind nur keine freigegeben, bleibt der knappe Hinweis
             (Rechte, nicht Einrichtung) — dieselbe Regel wie in der Leiste. -->
        <div v-else-if="!kalender.length" class="dk-kal-pop-leer">
          <p class="dk-kal-pop-hinweis">{{ leerzustand.titel }}</p>
          <p v-if="leerzustand.text" class="dk-kal-pop-hinweis dk-kal-pop-hinweis--klein">{{ leerzustand.text }}</p>
          <a v-if="leerzustand.ziel" :href="leerzustand.ziel" class="dk-kal-pop-ziel">{{ leerzustand.zielText }}</a>
        </div>

        <ul v-else class="dk-kal-pop-liste">
          <li
            v-for="k in kalender"
            :key="kalenderSchluessel(k)"
            class="dk-kal-pop-zeile"
          >
            <DkCheckbox
              :model-value="istGewaehlt(k)"
              :label="kalenderName(k)"
              @update:model-value="(an) => umschalten(k, an)"
            />
            <span class="dk-kal-pop-punkt" :style="{ background: farbe(k) }" aria-hidden="true"></span>
            <DkSymbol
              v-if="k.write"
              class="dk-kal-pop-recht"
              name="stift"
              :groesse="14"
              :title="'Eintragen erlaubt'"
            />
          </li>
        </ul>

        <p v-if="kalender.length" class="dk-kal-pop-fuss">
          {{ gewaehlteZahl }} von {{ kalender.length }} eingeblendet
        </p>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * KalenderAuswahl — Popover „Meine Kalender“ (UX3i, Entwurf A4 Punkt 5).
 *
 * Tastatur (Auflage der Karte): Escape schließt, der Fokus springt beim
 * Öffnen in die Fläche und beim Schließen zum Auslöser zurück. Die Auswahl
 * selbst liegt bei der Seite (`v-model`), damit Kopfzeile und Kalender
 * dieselbe Wahrheit haben.
 *
 * Nur Tokens, keine festen Farben. Klickflächen ≥ --control-h; bei
 * Fingerbedienung 44 px (K4).
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
import { kalenderLeerzustand } from '../../composables/einrichtungsHinweise.mjs'
import {
  kalenderName, kalenderSchluessel, eingeblendeteZahl,
} from './kalenderKopf.mjs'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** Alle Kalender, die der Server für diesen Nutzer kennt. */
  kalender: { type: Array, default: () => [] },
  /** Kennungen der eingeblendeten Kalender. */
  ausgewaehlt: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  /** Bildschirmrechteck des Auslösers (Position des Popovers). */
  anker: { type: Object, default: null },
})
const emit = defineEmits(['schliessen', 'update:ausgewaehlt'])

const flaeche = ref(null)
const gewaehlteZahl = computed(() => eingeblendeteZahl(props.kalender, props.ausgewaehlt))

const leerzustand = computed(() => kalenderLeerzustand({
  anzahl: props.kalender.length,
  gesamt: typeof window !== 'undefined' ? (window.__DIakonosBOOT?.kalender_gesamt ?? null) : null,
  admin: typeof window !== 'undefined' && window.__DIakonosBOOT?.is_admin === true,
}))

function farbe(k) {
  return sichereFarbe(k?.color) || 'var(--primary)'
}

function istGewaehlt(k) {
  const n = kalenderSchluessel(k)
  return (props.ausgewaehlt || []).map(String).includes(n)
}

/**
 * Ein Kästchen umgeschaltet: die neue Auswahl folgt der Reihenfolge der
 * Kalenderliste (nicht der Klickfolge) — die gespeicherte Auswahl bleibt
 * damit stabil.
 */
function umschalten(k, an) {
  const name = kalenderSchluessel(k)
  const jetzt = new Set((props.ausgewaehlt || []).map(String))
  if (an) jetzt.add(name)
  else jetzt.delete(name)
  const neu = (props.kalender || []).map(kalenderSchluessel).filter((n) => jetzt.has(n))
  emit('update:ausgewaehlt', neu)
}

/** Lage unter dem Auslöser, im Bild gehalten (kein Abschneiden am Rand). */
const lage = ref({})
function messen() {
  const r = props.anker
  if (!r || typeof window === 'undefined') return
  const breite = Math.min(320, window.innerWidth - 2 * 12)
  const links = Math.max(12, Math.min(r.left, window.innerWidth - breite - 12))
  lage.value = {
    position: 'fixed',
    top: `${Math.round(r.bottom + 6)}px`,
    left: `${Math.round(links)}px`,
    width: `${breite}px`,
  }
}

function beiKlickAusserhalb(e) {
  if (!props.open) return
  const el = flaeche.value
  if (el && !el.contains(e.target) && !e.target.closest?.('[data-kalender-ausloeser]')) {
    emit('schliessen')
  }
}

watch(() => props.open, async (offen) => {
  if (typeof window === 'undefined') return
  if (offen) {
    messen()
    window.addEventListener('mousedown', beiKlickAusserhalb, true)
    window.addEventListener('resize', messen)
    await nextTick()
    flaeche.value?.focus?.()
  } else {
    window.removeEventListener('mousedown', beiKlickAusserhalb, true)
    window.removeEventListener('resize', messen)
  }
})

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('mousedown', beiKlickAusserhalb, true)
  window.removeEventListener('resize', messen)
})

defineExpose({ messen })
</script>

<style scoped>
/* Die Ebene liegt über der Seite; sie selbst fängt KEINE Klicks ab außer
   ihrem Inhalt (`@click.self` schließt). */
.dk-kal-pop-ebene {
  position: fixed;
  inset: 0;
  z-index: var(--z-sheet, 300);
}
.dk-kal-pop {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-4);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
  border: var(--karte-rand) solid var(--rahmen-farbe);
}
.dk-kal-pop-titel {
  margin: 0;
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  color: var(--muted);
}
.dk-kal-pop-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  margin: 0;
  padding: 0;
  list-style: none;
}
.dk-kal-pop-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-2);
  border-radius: var(--radius-sm);
}
.dk-kal-pop-zeile:hover { background: var(--surface-hover); }
/* Reihenfolge in der Zeile: Kästchen (mit Name) zuerst, dann der Farbpunkt.
   Der Punkt steht REIN optisch hinter dem Text — Farbe ist nie der einzige
   Träger des Namens (Prinzip Ä4). */
.dk-kal-pop-punkt {
  width: 10px;
  height: 10px;
  flex: none;
  border-radius: 50%;
  order: -1;
}
.dk-kal-pop-recht { color: var(--muted); flex: none; margin-left: auto; }
.dk-kal-pop-hinweis { margin: 0; color: var(--muted); font-size: var(--fs); }
.dk-kal-pop-hinweis--klein { font-size: var(--fs-sm); }
.dk-kal-pop-leer { display: flex; flex-direction: column; align-items: flex-start; gap: var(--sp-1); }
.dk-kal-pop-ziel {
  color: var(--link);
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  text-decoration: none;
  padding: var(--sp-1) 0;
}
.dk-kal-pop-ziel:hover { color: var(--link-hover); text-decoration: underline; }
.dk-kal-pop-fuss {
  margin: 0;
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe-leise);
  color: var(--muted);
  font-size: var(--fs-sm);
}
@media (pointer: coarse) {
  .dk-kal-pop-zeile { min-height: 44px; }
}
</style>
