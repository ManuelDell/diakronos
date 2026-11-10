<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
import { useZurueckSchliesst } from '../../composables/useZurueckSchliesst.js'
import { terminZeitZeile } from './terminZeitZeile.mjs'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkAktionen from '../ui/DkAktionen.vue'
// A10/A11: Handlungen und Status-Badge des Termin-Blatts (reine Funktionen,
// geprüft in tests/a10-*).
import { terminBlattAktionen, statusBadgeFuer, istPruefStatus } from './mobilTermin.mjs'

const props = defineProps({
  show: { type: Boolean, required: true },
  event: { type: Object, default: null },
  /**
   * A10: Die Seite lädt die VOLLSTÄNDIGEN Daten des Termins nach
   * (`get_mein_termin`). Solange das läuft, zeigt das Blatt einen Ladebalken
   * und KEINE Zeilen des vorigen Termins — sonst stünde nach einem Tipp auf
   * einen anderen Termin kurz der alte Inhalt da.
   */
  laedt: { type: Boolean, default: false },
  /**
   * A11: Darf der Betrachter diesen Termin bearbeiten? Die SEITE entscheidet
   * (Lesemodus/Rechte aus UX3i, `store.isViewMode`) und reicht das Ergebnis
   * durch — das Blatt prüft keine Rollen selbst.
   */
  bearbeitenErlaubt: { type: Boolean, default: false },
})

const emit = defineEmits(['update:show', 'bearbeiten', 'freigeben'])

// FIX-7b: Die Zeitzeile liest `start`/`end` (Antwort von `get_mein_termin`)
// und weiterhin `element_start`/`element_end` (Daten aus dem Kalender).
function formatTime(event) {
  return terminZeitZeile(event)
}

const descLines = computed(() => {
  const d = props.event?.description
  return d ? String(d).split('\n') : ['—']
})

const resourceTitle = computed(() => {
  // The event's extendedProps.ressource holds the Link name; we need the title
  // calendar_get.py already resolves ressource_name for zusaetzliche_ressourcen
  // For the primary Ort, we show the ressource ID as fallback
  return props.event?.ressource_name || props.event?.ressource || '—'
})

const additionalResources = computed(() => {
  return props.event?.zusaetzliche_ressourcen || []
})

/** Bestätigt → ok, sonst (z. B. Angefragt) → warn. */
function statusVariant(status) {
  return status === 'Bestätigt' ? 'ok' : 'warn'
}

/** K-A: Ablehnungsgrund aus den extendedProps (nur Antragsteller/Moderator).
 *  Der Server liefert die Felder nur an den Antragsteller bzw. Moderatoren —
 *  fehlen sie, bleibt der Block aus. */
const ablehnungsGrund = computed(
  () => props.event?.ablehnungs_grund || props.event?.extendedProps?.ablehnungs_grund || ''
)
const moderiertVon = computed(
  () => props.event?.moderiert_von || props.event?.extendedProps?.moderiert_von || ''
)

/* ── A10/A11: die Handlungen des Termin-Blatts am Handy ─────────────────────
 * Das Blatt ERSETZT am Handy die Terminliste der Kalender-Bibliothek (die es
 * dort nicht mehr gibt). Deshalb muss es alles anbieten, was die Liste
 * angeboten hat (Karte A10, Punkt 6 und 7): Freigeben (Moderator), Absagen
 * (Moderator), Bearbeiten und Löschen. Was erscheint, entscheidet EINE
 * Funktion in `mobilTermin.mjs`; die Seite führt die Handlung aus.
 */
const darfPruefen = computed(() => {
  const boot = (typeof window !== 'undefined' && window.__DIakonosBOOT)
    || (typeof globalThis !== 'undefined' ? globalThis.__DIakonosBOOT : null)
  return boot?.can_moderate === true
})
/** Darf der Betrachter bearbeiten? Die Seite reicht ihr Ergebnis durch. */
const darfBearbeiten = computed(() => props.bearbeitenErlaubt === true)
/** Status des Termins für das Badge („Zu prüfen · eingetragen von …"). */
const statusBadge = computed(() => statusBadgeFuer(props.event))
/** „Freigeben“ ist der EINE Primärknopf — nur bei einem zu prüfenden Termin. */
const primaerFreigeben = computed(() => istPruefStatus(props.event))

const blattAktionen = computed(() => terminBlattAktionen({
  darfPruefen: darfPruefen.value,
  darfBearbeiten: darfBearbeiten.value,
  status: props.event?.status || props.event?.extendedProps?.status || '',
  primaerFreigeben: primaerFreigeben.value,
}))

function onBlattAktion(ereignis) {
  const eintrag = ereignis && ereignis.eintrag ? ereignis.eintrag : ereignis
  if (!eintrag || !eintrag.key) return
  if (eintrag.key === 'bearbeiten') { emit('bearbeiten', props.event); return }
  emit('freigeben', { termin: props.event, aktion: eintrag.key })
}

function onKeydown(e) {
  if (e.key === 'Escape') emit('update:show', false)
}

// A10 (Entwurf „A11 Mobil Termin“): Der Termin öffnet am Handy ein BLATT von
// unten (Griffleiste, obere Ecken rund, dunkler Kalender dahinter) statt eines
// Fensters in der Mitte. Der Inhalt ist DERSELBE — nur die Lage wechselt mit
// der Breite. Genau eine Grenze (wie `breiten.mjs`): 720 px.
const istHandyLage = ref(false)
let breitenMedia = null
function handyLagePruefen(e) {
  istHandyLage.value = e.matches
}
onMounted(() => {
  if (typeof window === 'undefined' || !window.matchMedia) return
  breitenMedia = window.matchMedia('(max-width: 720px)')
  istHandyLage.value = breitenMedia.matches
  breitenMedia.addEventListener?.('change', handyLagePruefen)
})
onBeforeUnmount(() => {
  breitenMedia?.removeEventListener?.('change', handyLagePruefen)
})

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

// OP-HANDY-7: Die Zurück-Taste/-Geste schließt das Termin-Fenster. Vorher
// blieb es offen und blockierte die Taps auf der Seite darunter.
useZurueckSchliesst(computed(() => props.show), () => emit('update:show', false))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="diakronos-modal show"
      :class="{ 'is-blatt': istHandyLage }"
      @click.self="emit('update:show', false)"
    >
      <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
        <div class="diakronos-modal-content">
          <!-- A11: Griffleiste des Blattes — nur in der Handy-Lage sichtbar. -->
          <div v-if="istHandyLage" class="diakronos-blatt-griff" aria-hidden="true"></div>
          <div class="diakronos-topbar">
            <div class="diakronos-color-bar" :style="{ background: sichereFarbe(event?.element_color) || 'var(--primary)' }"></div>
            <!-- A10/A11: „⋯" am Termin. Am Handy stehen hier die Handlungen,
                 die das Blatt nicht als Knopf trägt (Abbrechen, Löschen);
                 am Desktop bleibt die Lage wie bisher (kein ⋯). -->
            <div v-if="istHandyLage" class="diakronos-modal-mehr">
              <DkAktionen
                kennung="termin-blatt"
                :eintraege="blattAktionen"
                label="Weitere Aktionen für diesen Termin"
                menue-label="Weitere Aktionen für diesen Termin"
                @aktion="onBlattAktion"
              />
            </div>
          </div>
          <div class="diakronos-modal-header">
            <h5 class="modal-title">{{ event?.element_name || 'Termin' }}</h5>
            <button class="diakronos-close-btn" aria-label="Schließen" @click="emit('update:show', false)">&times;</button>
          </div>
          <div class="diakronos-modal-body">
            <div class="diakronos-ladebalken" :class="{ 'is-ladend': laedt }" role="progressbar"
                 aria-label="Termin wird geladen" :aria-hidden="laedt ? 'false' : 'true'"></div>
            <div v-if="laedt" class="diakronos-laden">
              <DkSkelett kurz form="zeilen" :anzahl="4" text="Termin wird geladen" />
            </div>
            <template v-else>
            <div class="event-time">{{ formatTime(event) }}</div>
            <!-- K-A (R-P1-8): Ein abgelehnter Termin des Antragstellers nennt
                 den Grund — der Server liefert ihn nur an ihn bzw. Moderatoren. -->
            <div v-if="ablehnungsGrund" class="event-ablehnung">
              <strong>Abgelehnt</strong>
              <span v-if="moderiertVon"> — bearbeitet von {{ moderiertVon }}</span>
              <div class="event-ablehnung-grund">{{ ablehnungsGrund }}</div>
            </div>
            <!-- A11 (Entwurf): Status-Badge über den Zeilen — „Zu prüfen ·
                 eingetragen von …". Die Werte kommen aus dem Termin (status,
                 antragsteller); fehlen sie, bleibt das Badge aus. -->
            <div v-if="statusBadge" class="event-status">
              <DkBadge :variant="statusBadge.variant">{{ statusBadge.text }}</DkBadge>
            </div>
            <dl class="diakronos-dl">
              <dt>Kalender</dt><dd>{{ event?.element_calendar || '—' }}</dd>
              <dt>Kategorie</dt><dd>{{ event?.event_category_name || '—' }}</dd>
              <dt>Ort</dt><dd>{{ resourceTitle }}</dd>
              <template v-if="additionalResources.length > 0">
                <dt>Weitere Ressourcen</dt>
                <dd>
                  <div class="additional-resources-list">
                    <div
                      v-for="(res, idx) in additionalResources"
                      :key="idx"
                      class="additional-resource-item"
                    >
                      <span class="resource-label">
                        {{ res.ressource_name || res.freitext_ressource || '—' }}
                      </span>
                      <DkBadge :variant="statusVariant(res.status)">{{ res.status }}</DkBadge>
                    </div>
                  </div>
                </dd>
              </template>
              <dt>Beschreibung</dt>
              <dd>
                <template v-for="(line, i) in descLines" :key="i">
                  <br v-if="i > 0" />{{ line }}
                </template>
              </dd>
            </dl>

            <!-- A11: die Handlungsleiste des Blattes. Genau EIN Primärknopf
                 je Ansicht: für Moderatoren bei einem zu prüfenden Termin
                 „Freigeben“ (Entwurf A11), sonst „Bearbeiten“ sekundär. Das
                 Blatt entscheidet NICHTS selbst — ohne Rechte (`darfBearbeiten`)
                 gibt es keinen Knopf, und die Seite entscheidet, was passiert. -->
            <div v-if="istHandyLage && (darfPruefen || darfBearbeiten)" class="diakronos-blatt-aktionen">
              <DkButton
                v-if="darfBearbeiten"
                variant="secondary"
                class="diakronos-blatt-knopf"
                @click="emit('bearbeiten', event)"
              >Bearbeiten</DkButton>
              <DkButton
                v-if="darfPruefen && primaerFreigeben"
                variant="primary"
                data-primaer="1"
                class="diakronos-blatt-knopf"
                @click="emit('freigeben', { termin: event, aktion: 'freigeben' })"
              >Freigeben</DkButton>
            </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.diakronos-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--med) var(--ease), visibility var(--med) var(--ease);
}
.diakronos-modal.show {
  opacity: 1;
  visibility: visible;
}
/* ── A11 (Entwurf „A11 Mobil Termin“): Blatt von unten ──────────────────────
   Am Handy liegt der Kalender abgedunkelt dahinter, das Blatt schiebt sich von
   unten darüber (obere Ecken rund, Griffleiste). Dieselbe Grenze wie das
   Mobil-Layout der App: 720 px Breite — und die flache Handy-Lage (Querformat),
   in der ebenfalls die untere Leiste regiert. */
.diakronos-modal.is-blatt {
  align-items: flex-end;
  justify-content: stretch;
}
.diakronos-modal.is-blatt .diakronos-modal-dialog {
  width: 100%;
  max-width: none;
  max-height: 92%;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  border-bottom: none;
  padding-bottom: env(safe-area-inset-bottom);
}
.diakronos-modal.is-blatt .diakronos-modal-content {
  max-height: 92vh;
}
.diakronos-blatt-griff {
  flex: none;
  width: var(--sp-6);
  height: var(--sp-1);
  margin: var(--sp-2) auto var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--line-strong);
}
/* Farbstreifen und „⋯“ stehen in einer Zeile über dem Kopf: der Streifen
   bleibt oben, das Menü sitzt am rechten Rand auf 44 px. */
.diakronos-topbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.diakronos-topbar .diakronos-color-bar { flex: 1; }
.diakronos-modal-mehr { flex: none; margin-right: var(--sp-2); display: flex; }
/* A10: Ladebalken oben im Blatt (Muster des Seitenbalkens) und der ruhige
   Platzhalter, solange die Detaildaten unterwegs sind (Prinzip I1/I5). */
.diakronos-ladebalken {
  height: var(--ring-breite);
  overflow: hidden;
  opacity: 0;
  border-radius: var(--badge-r);
  background: transparent;
  transition: opacity var(--fast) var(--ease);
}
.diakronos-ladebalken.is-ladend { opacity: 1; background: var(--warn-soft); }
.diakronos-laden { padding: var(--sp-2) 0; }
.event-status { margin-bottom: var(--sp-3); }
.diakronos-blatt-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding-top: var(--sp-4);
  margin-top: var(--sp-4);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe-leise);
}
.diakronos-blatt-aktionen .diakronos-blatt-knopf {
  flex: 1;
  min-height: var(--sp-7);
}
.diakronos-modal-dialog {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  max-width: 560px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.diakronos-modal-content {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
.diakronos-color-bar {
  height: 6px;
  width: 100%;
}
.diakronos-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-alt-20);
  border-bottom: 1px solid var(--line);
}
.diakronos-modal-header h5 {
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: var(--fw-h);
  color: var(--text);
}
.diakronos-close-btn {
  background: none;
  border: none;
  font-size: var(--fs-26);
  cursor: pointer;
  color: var(--muted);
  line-height: 1;
}
.diakronos-close-btn:hover { color: var(--text); }
.diakronos-modal-body {
  padding: var(--sp-4) var(--sp-alt-20);
  overflow-y: auto;
}
.event-time {
  font-size: var(--fs);
  color: var(--muted);
  margin-bottom: var(--sp-3);
}
.event-ablehnung {
  border-left: 3px solid var(--dk-danger);
  background: color-mix(in oklch, var(--dk-danger) 8%, transparent);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-3);
  font-size: var(--fs-sm);
}
.event-ablehnung-grund { margin-top: var(--sp-1); color: var(--text); white-space: pre-wrap; }
.diakronos-dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--sp-1) var(--sp-3);
  margin: 0;
}
.diakronos-dl dt {
  font-weight: var(--fw-fett);
  font-size: var(--fs);
  color: var(--text);
}
.diakronos-dl dd {
  margin: 0;
  font-size: var(--fs);
  color: var(--muted);
}

/* Additional resources */
.additional-resources-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.additional-resource-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.resource-label {
  font-size: var(--fs);
}
</style>
