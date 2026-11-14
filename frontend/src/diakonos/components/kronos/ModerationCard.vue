<template>
  <!-- UI-R4: Die Karte ist ein Link (`href="#"`) und trägt KEIN aria-label
       mehr — ein Label überschreibt den gesamten Inhalt, sodass „wartet auf …“
       und die Stufe nicht vorgelesen wurden. Der Linktext ist jetzt Datum,
       Titel und Herkunft; was er tut, sagt ein eigener Satz (`dk-mcard-hint`),
       den der Freigeben-Knopf per aria-describedby mitliest.
       Bedienelemente liegen NICHT im Link: der Freigeben-Knopf und der
       „Zurück“-Knopf stehen im selben Kartenrahmen, aber außerhalb von
       `<a>` (verschachtelte Bedienelemente sind ungültig und verwirren
       Tastatur und Vorleseprogramme). -->
  <div
    class="dk-mcard"
    :class="{
      'dk-mcard--konflikt': isKonflikt,
      'dk-mcard--serie': item.type === 'serie',
    }"
    :data-id="item.id"
    :data-type="item.type || 'event'"
  >
    <!-- Color strip -->
    <div class="dk-mcard-strip" :style="{ background: sichereFarbe(item.calendar_color) }"></div>

    <div class="dk-mcard-body">
      <a
        class="dk-mcard-link"
        href="#"
        @click.prevent="$emit('click', item)"
      >
        <!-- Header row -->
        <div class="dk-mcard-header">
          <span class="dk-mcard-title">{{ item.title }}</span>

          <!-- Serie badge -->
          <DkBadge v-if="item.type === 'serie'" variant="neutral" class="dk-mcard-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
            {{ item.count }} Termine
          </DkBadge>

          <!-- Konflikt badge -->
          <DkBadge v-if="isKonflikt" variant="err" class="dk-mcard-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            Konflikt
          </DkBadge>

          <!-- P1-5b (W-1): Abgelehnt-Kennzeichnung in der Historie-Spalte -->
          <DkBadge v-if="column === 'abgelehnt'" variant="neutral" class="dk-mcard-badge">
            Abgelehnt
          </DkBadge>
        </div>

        <!-- Date/time -->
        <div class="dk-mcard-time">{{ formatDate(item) }}</div>

        <!-- Calendar -->
        <div class="dk-mcard-cal">
          <span class="dk-mcard-dot" :style="{ background: sichereFarbe(item.calendar_color) }"></span>
          {{ item.calendar_title }}
        </div>

        <!-- OP-EVENT-12: Antragsteller und Beschreibung auf der Karte -->
        <div v-if="item.antragsteller || item.owner" class="dk-mcard-antragsteller">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          Antragsteller: {{ item.antragsteller || item.owner }}
        </div>
        <div v-if="item.description" class="dk-mcard-beschreibung">{{ item.description }}</div>

        <!-- P1-5b (W-1): Ablehnungsgrund nur in der Historie-Spalte (Moderatoren) -->
        <div v-if="column === 'abgelehnt' && item.ablehnungs_grund" class="dk-mcard-beschreibung">
          Grund: {{ item.ablehnungs_grund }}
        </div>

        <!-- Ressource -->
        <div v-if="item.ressource" class="dk-mcard-ressource">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
          {{ item.ressource }}
        </div>

        <!-- Notification indicator -->
        <div v-if="notification" class="dk-mcard-notif">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          Bearbeitet von {{ notification.by || 'Unbekannt' }}
        </div>

        <!-- UI-R4: WELCHE Stufe dran ist. Der Server nennt sie (`stufe`); die
             Zeile sagt es im Fließtext, damit der Moderator weiß, ob er selbst
             zuständig ist, bevor er irgendwo hinspringt. Beim Serien-Termin
             zählt die Stufe der Termine (alle gehören zur selben Serie). -->
        <div v-if="warteText" class="dk-mcard-wartet">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ warteText }}
        </div>
      </a>

      <!-- „Zurück“ aus der Freigabe-Spalte (UX1e: Knopf aus dem System).
           Eigener Knopf AUSSERHALB des Links (kein verschachteltes
           Bedienelement). -->
      <div v-if="inFestlegen" class="dk-mcard-knoepfe">
        <DkButton
          class="dk-mcard-remove"
          variant="ghost"
          size="md"
          title="Zurück in die Vorschlags-Spalte"
          @click.stop="$emit('remove', item)"
        >&times; Zurück in die Vorschläge</DkButton>
      </div>

      <!-- UI-R4b (Punkt 1): In der KONFLIKT-Spalte gibt es KEINEN direkten
           Freigeben-Knopf. `resolveConflict(id,'festlegen')` ohne
           `ueberschneidung:1` gäbe den Termin trotz Überschneidung frei,
           ohne Warnung und ohne `ignore_conflict` — er stünde danach wieder
           als Konflikt auf dem Brett (DEV-7b umgangen). Freigeben geht dort
           NUR über den Konflikt-Dialog (ModerationModals.vue), der die
           Überschneidung anzeigt und `ueberschneidung: 1` setzt.

           UI-R4 (Punkt 7): Verweigerungstext (403/417) und Freigabe schließen
           sich nicht mehr aus — nach einer Verweigerung lädt die Tafel neu und
           entfernt den Knopf (`darf_pruefen` ist dann false); der Text bleibt
           als eigener Absatz stehen, statt von `v-else-if` verschluckt zu
           werden. -->
      <div v-if="freigabeSichtbar" class="dk-mcard-freigabe">
        <DkButton
          :id="freigebenId"
          class="dk-mcard-freigeben"
          variant="primary"
          size="md"
          :disabled="busy"
          :aria-describedby="hinweisId"
          @click="freigeben"
        >{{ busy ? '…' : 'Freigeben' }}</DkButton>
        <span class="dk-mcard-stufe">Stufe: {{ freigabeStufeText }}</span>
      </div>
      <p v-if="verweigerung" class="dk-mcard-verweigert" role="status">{{ verweigerung }}</p>

      <!-- Serie conflict details (collapsible) -->
      <div v-if="item.type === 'serie' && item.konflikt_events?.length && column === 'konflikte'" class="dk-mcard-serie-conflicts">
        <div class="dk-mcard-conflict-toggle" @click.stop="showConflicts = !showConflicts">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          {{ item.konflikt_events.length }} von {{ item.count }} Terminen haben einen Konflikt
        </div>
        <ul v-if="showConflicts" class="dk-mcard-conflict-list">
          <li
            v-for="ev in item.konflikt_events"
            :key="ev.id"
            class="dk-mcard-conflict-item"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            {{ datumZeitText(ev.start, ev.all_day) }}
            <DkButton
              class="dk-mcard-aufloesen"
              variant="secondary"
              size="md"
              :aria-label="'Konflikt am ' + datumZeitText(ev.start, ev.all_day) + ' auflösen'"
              @click.stop="$emit('resolve-conflict', ev)"
            >Auflösen</DkButton>
          </li>
        </ul>
      </div>

      <!-- Unsichtbarer Hinweis für Vorleseprogramme: was der Knopf tut. Der
           Satz existiert nur, wenn es den Freigeben-Knopf gibt (sonst zeigte
           aria-describedby auf eine leere Beschreibung). -->
      <span v-if="freigabeSichtbar" :id="hinweisId" class="dk-nur-vorlesen">
        Gibt diesen Termin auf der Stufe „{{ freigabeStufeText }}“ frei.
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
// UX1e: EIN Knopf-System für „Zurück“ und „Auflösen“.
import DkButton from '../ui/DkButton.vue'
import { terminZeitText } from './moderationskarte.js'
// UXD-R28: Kalenderfarbe nur als gueltiger Hex-Wert in den style-String.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
// UI-R4: EINE Quelle für Stufennamen (Server-Titel), „darf prüfen“ und die
// Warteline.
import { darfPruefen, istKonfliktEintrag, wartetAufText } from './freigabeStufen.mjs'
// Reativ: Titel zeichnen nach, sobald die Server-Antwort eintrifft.
// UI-R4b: `stufenTitelEinmalLaden` teilt sich den Ladevorgang mit allen
// anderen Karten/Änderungen der Seite — EINE Abfrage je Seite statt je Karte.
import { stufenNameReaktiv, stufenTitelEinmalLaden } from './freigabeStufenReaktiv.mjs'
import { apiCall } from '../../composables/useApi.js'

const props = defineProps({
  item: { type: Object, required: true },
  column: { type: String, default: 'vorschlaege' },
  notification: { type: Object, default: null },
  /** UI-R4: läuft gerade eine Freigabe für genau diese Karte? */
  busy: { type: Boolean, default: false },
  /** UI-R4: Klartext einer Verweigerung (403/417) für genau diese Karte. */
  verweigerung: { type: String, default: '' },
})

const emit = defineEmits(['click', 'remove', 'resolve-conflict', 'freigeben'])

// UI-R4: eindeutige Kennungen für aria-describedby (mehrere Karten je Seite).
const _uid = `mcard-${Math.random().toString(36).slice(2, 9)}`
const freigebenId = `${_uid}-freigeben`
const hinweisId = `${_uid}-hinweis`

const showConflicts = ref(false)

const isKonflikt = computed(() => {
  if (props.item.type === 'serie') return props.item.has_konflikt
  return props.item.status === 'Konflikt'
})

const inFestlegen = computed(() => props.column === 'festlegen')

// ── UI-R4: Stufe und Freigabe ───────────────────────────────────────────────
/** Beim Serien-Termin zählt die Stufe des ersten enthaltenen Termins. */
function stufenEintrag() {
  const item = props.item || {}
  if (item.type === 'serie') {
    const erster = (item.events || [])[0]
    if (erster) return erster
    // Ohne Einzeltermine bleibt nur, was die Karte selbst trägt.
  }
  return item
}

const eintrag = computed(() => stufenEintrag())

/** Die Warteline „wartet auf Freigabe für: …“ — nur, wenn der Server eine Stufe nennt. */
const warteText = computed(() => {
  // Historie und Ablage sind keine Prüfentscheidung: dort wartet nichts.
  if (props.column === 'abgelehnt') return null
  if (props.column === 'festlegen') return null
  return wartetAufText(eintrag.value)
})

const freigabeStufe = computed(() => {
  const s = String(eintrag.value?.stufe || '').trim()
  return s || null
})

/** Nur der Server entscheidet; die Ablage-Hilfe ist kein Freigabe-Ort.
 *
 * UI-R4b (Punkt 1): Die KONFLIKT-Spalte hat keinen direkten Freigeben-Knopf —
 * dort führt die Freigabe ausschließlich über den Konflikt-Dialog, der die
 * Überschneidung nennt und `ueberschneidung: 1` setzt. Ohne diesen Schalter
 * bliebe `ignore_conflict` 0 und der Termin käme als Konflikt zurück.
 */
const freigabeSichtbar = computed(() => {
  if (props.column !== 'vorschlaege') return false
  // UI-R4c (Punkt 3): Status „Konflikt“ (auch eines Serientermins) heißt:
  // Freigabe NUR über den Konflikt-Dialog, egal in welcher Spalte die Karte
  // gerade steht. Vorher hängte das allein an der Spalte — eine Konfliktkarte
  // in der Vorschlags-Spalte hätte einen direkten Freigeben-Knopf bekommen.
  if (istKonfliktEintrag(props.item)) return false
  return darfPruefen(eintrag.value)
})

// `stufenTitel` ist reaktiv: treffen die Titel nach dem ersten Zeichnen ein,
// zeichnet diese Zeile von selbst neu.
const freigabeStufeText = computed(() => stufenNameReaktiv(freigabeStufe.value))

function freigeben() {
  if (!freigabeSichtbar.value) return
  emit('freigeben', { item: props.item, stufe: freigabeStufe.value })
}

// UI-R4: Die Stufen-Titel kommen vom Server (`get_rollen_erklaerung`).
// Vorher standen sie hier fest; ohne Titel bleibt die Anzeige neutral
// (`STUFE_UNBEKANNT`), sie erfindet keinen Namen.
// UI-R4b: EINMAL je Seite — nicht je Karte (sonst 20 gleiche Abfragen bei
// 20 Vorschlägen).
onMounted(() => { stufenTitelEinmalLaden(apiCall) })

function formatDate(item) {
  return terminZeitText(item)
}

/**
 * FIX-7: Datum/Uhrzeit eines EINZELNEN Konflikttermins in der Serienkarte.
 *
 * Vorher stand hier `fmtDate(ev.start, ev.all_day)` — eine Funktion, die es
 * in diesem Skript nie gab (`fmtDate` lebte nur in `ModerationModals.vue`).
 * Vue brach beim Aufklappen der Konfliktliste mit „Property "fmtDate" was
 * accessed during render but is not defined" ab, die Zeile blieb leer.
 * Jetzt nimmt die Karte denselben Helfer wie ihre eigene Zeitzeile: die
 * vorhandene Formatierung aus `moderationskarte.js` (deutsches Datum,
 * Uhrzeit nur bei Terminen mit Uhrzeit).
 */
function datumZeitText(start, allDay) {
  return terminZeitText({ start, end: null, all_day: allDay })
}
</script>

<style scoped>
/* ── Card base ───────────────────────────────────────────────────────────── */
.dk-mcard {
  display: flex;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--fast), box-shadow var(--fast);
  /* UXK-006: In der Flex-Spalte (.dk-mboard-col-body) liessen sich die Karten
     zusammendruecken — mobil bis auf 10 px, am Desktop ab ~10 Karten auf 37 px.
     `flex-shrink: 0` haelt die natuerliche Hoehe, die Spalte scrollt stattdessen. */
  flex-shrink: 0;
}
.dk-mcard:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}
.dk-mcard--konflikt {
  border-color: color-mix(in oklch, var(--err) 40%, var(--line));
}
.dk-mcard--konflikt:hover {
  border-color: var(--err);
}

/* Strip */
.dk-mcard-strip {
  width: 4px;
  flex-shrink: 0;
}

/* Body */
.dk-mcard-body {
  flex: 1;
  padding: 10px 12px;
  min-width: 0;
}

/* Header */
.dk-mcard-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.dk-mcard-title {
  font-size: var(--fs-14);
  font-weight: var(--fw-fett);
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* UI-R4: Der Link IST der lesbare Inhalt der Karte (Titel, Zeit, Kalender,
   Stufe). Er trägt keine eigene Farbe/Unterstreichung — die Karte bleibt
   die Fläche; der Link nimmt nur den ganzen Inhalt auf, damit ein Klick
   irgendwo im Text den Termin öffnet. */
.dk-mcard-link {
  display: block;
  color: inherit;
  text-decoration: none;
}
.dk-mcard-link:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* UI-R4: Nur für Vorleseprogramme sichtbar (Beschreibung des Freigeben-
   Knopfes). Kein `display: none` — sonst lesen Screenreader den Satz nicht.
   Länge/Position kommen aus bestehenden Tokens (UX1a: keine neuen
   Festwerte im Abstands-Bestand). */
.dk-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(-1 * var(--rahmen-breite));
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  clip-path: inset(50%);
}

/* UI-R4: Knöpfe stehen außerhalb des Links — eigener Bereich unter dem
   Inhalt, gleiche Trennung wie die Freigabe. */
.dk-mcard-knoepfe {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

/* Badges (Fläche/Farbe liefert DkBadge) */
.dk-mcard-badge {
  font-size: var(--fs-xs);
  font-weight: var(--fw-fett);
  flex-shrink: 0;
}

/* „Zurück“ — UX1e: DkButton (ghost, sm). Nur die Lage bleibt eigen; Farbe
   und Fläche kommen aus dem Knopf-System, nicht mehr aus einer Eigenregel. */
.dk-mcard-remove {
  flex-shrink: 0;
  padding: 0 var(--sp-1);
}

/* Time */
.dk-mcard-time {
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: 3px;
}

/* Calendar */
.dk-mcard-cal {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-xs);
  color: var(--subtle);
}
.dk-mcard-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Ressource */
.dk-mcard-ressource {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--subtle);
  margin-top: 3px;
}

/* OP-EVENT-12: Antragsteller + Beschreibung auf der Vorschlagskarte */
.dk-mcard-antragsteller {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--subtle);
  margin-top: 3px;
}
.dk-mcard-beschreibung {
  font-size: var(--fs-xs);
  color: var(--muted);
  margin-top: 3px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Notification */
.dk-mcard-notif {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--info);
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--divider);
}

/* UI-R4: „wartet auf Freigabe für: …“ — ruhig, aber nicht zu übersehen.
   Gold ist die Statusfarbe „zu prüfen“ (wie die Zahl in „Zu prüfen“); Fläche
   bekommt sie nicht, damit die Karte nicht schreit.
   Abstände als Tokens (UX1a-Wächter: keine festen Werte in NEUEM Code). */
.dk-mcard-wartet {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  margin-top: var(--sp-1);
  font-size: var(--fs-xs);
  font-weight: var(--fw-mittel);
  color: var(--warn);
  /* Lange Stufennamen brechen um statt abgeschnitten zu werden. */
  overflow-wrap: anywhere;
}

/* UI-R4: Freigabe nur bei server-seitigem darf_pruefen. */
.dk-mcard-freigabe {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe-leise);
}
/* UX1e: DkButton (primary, md) — keine eigene Knopfoptik, nur die Lage. */
.dk-mcard-freigeben {
  flex: none;
}
.dk-mcard-stufe {
  font-size: var(--fs-xs);
  color: var(--muted);
}
/* UI-R4: Verweigerung des Servers (403/417) — Klartext, kein Lärm. */
.dk-mcard-verweigert {
  margin: var(--sp-2) 0 0;
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe-leise);
  font-size: var(--fs-xs);
  color: var(--muted);
  overflow-wrap: anywhere;
}
/* K4: bei Fingerbedienung ist der Freigabe-Knopf 44 px hoch. */
@media (pointer: coarse) {
  .dk-mcard-freigeben { min-height: 44px; }
}

/* Serie conflict details */
.dk-mcard-serie-conflicts {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--divider);
}
.dk-mcard-conflict-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--err);
  cursor: pointer;
  user-select: none;
}
.dk-mcard-conflict-toggle:hover {
  opacity: 0.8;
}
.dk-mcard-conflict-list {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dk-mcard-conflict-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-xs);
  color: var(--muted);
  padding: 3px 6px;
  background: var(--err-soft);
  border-radius: var(--radius-sm);
}
/* UX1e: DkButton (secondary, sm) — keine eigene Knopfoptik mehr. */
.dk-mcard-aufloesen {
  margin-left: auto;
}
</style>
