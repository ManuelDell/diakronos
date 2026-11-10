<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
import { useZurueckSchliesst } from '../../composables/useZurueckSchliesst.js'
import { terminZeitZeile } from './terminZeitZeile.mjs'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
// A11 (Karte t_3c23f0a5): Am Handy ist der Termin ein Blatt von unten
// (`TerminBlatt.vue`, Entwurf „A11 Mobil Termin“). Die Handlungen des Blattes
// stehen dort; hier bleibt das Fenster für den Desktop (A4) unverändert.
import TerminBlatt from './TerminBlatt.vue'
// A10/A11: Status-Badge des Termins (reine Funktion, geprüft in tests/a10-*).
import { statusBadgeFuer } from './mobilTermin.mjs'

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
   * A11 (Review): Handy-Lage kommt von der SEITE (`Kalender.vue`, `istSchmal`)
   * — EINE Stelle für die Lage, keine eigene Breitenabfrage hier (DEV-B6
   * stellt die Lage zentral um).
   */
  handyLage: { type: Boolean, default: false },
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

/* ── A10/A11: Status des Termins und Rechte ─────────────────────────────────
 * Am Handy zeigt das Blatt (`TerminBlatt.vue`) den Status als Abzeichen und
 * bietet die Handlungen an; hier bleiben nur die Werte, die BEIDE Lagen
 * brauchen. Die Seite entscheidet, was sie durchreicht (Lesemodus/Rechte aus
 * UX3i) — dieses Fenster prüft keine Rollen selbst.
 */
const darfPruefen = computed(() => {
  const boot = (typeof window !== 'undefined' && window.__DIakonosBOOT)
    || (typeof globalThis !== 'undefined' ? globalThis.__DIakonosBOOT : null)
  return boot?.can_moderate === true
})
/** Status des Termins für das Badge („Zu prüfen · eingetragen von …“). */
const statusBadge = computed(() => statusBadgeFuer(props.event))

function onKeydown(e) {
  if (e.key === 'Escape') emit('update:show', false)
}

// A11: Blatt (Handy) oder Fenster (Desktop) — die Lage reicht die Seite
// durch (`handyLage`), hier wird nichts gemessen.
const istHandyLage = computed(() => props.handyLage === true)

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

// OP-HANDY-7: Die Zurück-Taste/-Geste schließt das Termin-Fenster. Vorher
// blieb es offen und blockierte die Taps auf der Seite darunter.
useZurueckSchliesst(computed(() => props.show), () => emit('update:show', false))
</script>

<template>
  <!-- A11 (Entwurf „A11 Mobil Termin“): Am HANDY ist der Termin ein Blatt von
       unten (`TerminBlatt.vue`); am Desktop bleibt das Fenster wie bisher
       (A4). Der Inhalt ist DERSELBE — nur die Lage wechselt mit der Breite
       (die Lage bestimmt die Seite: Prop `handyLage`). -->
  <TerminBlatt
    v-if="istHandyLage"
    :show="show"
    :event="event"
    :laedt="laedt"
    :darf-pruefen="darfPruefen"
    :bearbeiten-erlaubt="bearbeitenErlaubt"
    @schliessen="emit('update:show', false)"
    @bearbeiten="(t) => emit('bearbeiten', t)"
    @freigeben="(e) => emit('freigeben', e)"
  />

  <Teleport v-else-if="show" to="body">
    <div
      v-if="show"
      class="diakronos-modal show"
      @click.self="emit('update:show', false)"
    >
      <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
        <div class="diakronos-modal-content">
          <div class="diakronos-topbar">
            <div class="diakronos-color-bar" :style="{ background: sichereFarbe(event?.element_color) || 'var(--primary)' }"></div>
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
                 eingetragen von …“. Die Werte kommen aus dem Termin (status,
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
/* ── A11: Die Blatt-Regeln (innen liegender Schleier, Griff, Handlungsleiste)
   stehen seit der Karte t_3c23f0a5 in `TerminBlatt.vue` — dieses Fenster gilt
   nur noch am Desktop (A4). Entfernt: `.is-blatt`-Regeln, `.diakronos-blatt-griff`,
   `.diakronos-modal-mehr`, `.diakronos-blatt-aktionen` (toter Bestand, sonst
   stünden hier zwei Fassungen derselben Sache). */
.diakronos-topbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.diakronos-topbar .diakronos-color-bar { flex: 1; }
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
