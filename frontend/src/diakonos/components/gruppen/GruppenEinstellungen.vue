<template>
  <div class="gr-einst">
    <!-- UI-R1: Einstellungen der Gruppe — Teil 1: Rollen.
         Ob die Karte überhaupt erscheint, entscheidet die GRUPPENSEITE über die
         Serverfelder von `get_gruppe_detail`; hier werden keine Rollen mehr
         eigenständig geladen (früher stand `get_gruppenrollen` doppelt).
         UI-R2b: Dies ist eine reine Inhaltssammlung OHNE eigene Karten — die
         Gruppenseite stellt je Bereich EINE Karte („Rollen der Gruppe“,
         „Kalender der Gruppe“). Vorher lag hier eine Karte in einer Karte
         desselben Titels (Review UI-R2b, Punkt 6). -->
    <RollenEinstellungen
      v-if="zeigt('rollen')"
      :gruppe="gruppe"
      :untergruppe="untergruppe"
      :untergruppen="untergruppen"
      @geaendert="$emit('geaendert')"
    />

    <KalenderEinstellungen
      v-if="zeigt('kalender')"
      :gruppe="gruppe"
      :untergruppe="untergruppe"
      :gruppe-name="gruppeName"
      :untergruppe-name="untergruppeName"
      :untergruppen="untergruppen"
      @geaendert="$emit('geaendert')"
      @gesperrt="onGesperrt"
    />
  </div>
</template>

<script setup>
/**
 * GruppenEinstellungen — der Bereich „Einstellungen“ auf der Gruppenseite.
 *
 * Teil 1 (UI-R1): Rollen (HV, MV, GL) — `RollenEinstellungen.vue`.
 * Teil 2 (UI-R2): Kalender der Gruppe — `KalenderEinstellungen.vue`.
 *
 * Die Sichtbarkeit hängt allein an den Rechten, die `get_gruppe_detail`
 * mitliefert (der Server entscheidet, nicht die Oberfläche). Die Rollenliste
 * selbst lädt `get_gruppenrollen` — und zwar NUR dort, nicht zusätzlich hier.
 * Die Kalenderliste lädt `get_kalender_verwaltung` ebenfalls genau einmal.
 *
 * Die KARTEN gehören der Seite: hier stehen nur die Inhalte. Ein `DkCard` an
 * dieser Stelle ergäbe auf der Seite eine Karte im Kartenkopf desselben
 * Titels (Review UI-R2b, Punkt 6).
 */
import RollenEinstellungen from './RollenEinstellungen.vue'
import KalenderEinstellungen from './KalenderEinstellungen.vue'

const emit = defineEmits(['geaendert', 'gesperrt'])

/**
 * `gesperrt` WEITERGEBEN — die Pfeil-Funktion im Muster verliert das zweite
 * Argument (UI-R2d): `$emit` ist bei einer Komponente ein ZWEI-Wertiges
 * Ereignis, kein DOM-Ereignis. Vue reicht `$event` nur als ersten Wert an eine
 * Pfeil-Funktion, `@gesperrt="(a, b) => $emit(..., b)"` bekäme für `b` immer
 * `undefined` — die Karte der Seite erführe nie, dass eine Antwort da ist.
 * Darum eine echte Methode mit beiden Werten (und `emit` aus `defineEmits`).
 *
 * AUSNAHME `$event`: `emit(..., undefined)` würde das ZWEITE Argument
 * mitreichen und `$event` damit zu `undefined` machen — das fängt der
 * erste Zweig ab (Aufrufer ohne „Antwort da“-Signal).
 */
function onGesperrt(gesperrt, antwortDa) {
  if (antwortDa === undefined) emit('gesperrt', gesperrt)
  else emit('gesperrt', gesperrt, antwortDa)
}


const props = defineProps({
  /**
   * Welcher Teil soll stehen? `'rollen'` oder `'kalender'` (die Seite baut je
   * Teil eine eigene Karte) — leer = beide, für Aufrufer, die beides an einer
   * Stelle zeigen wollen.
   */
  teil: { type: String, default: '' },
  /** Kennung der HAUPTgruppe (auf einer Untergruppen-Seite: der Obergruppe). */
  gruppe: { type: String, required: true },
  /** Kennung dieser Untergruppe (leer auf einer Gruppenseite). */
  untergruppe: { type: String, default: '' },
  /** Untergruppen: [{ name, anzeigename }]. */
  untergruppen: { type: Array, default: () => [] },
  /** Anzeigename der Gruppe (Kopf der Kalender-Auswahl). */
  gruppeName: { type: String, default: '' },
  /** Anzeigename dieser Untergruppe. */
  untergruppeName: { type: String, default: '' },
})
/** Zeigt dieser Aufbau den genannten Teil? (leer = alle) */
function zeigt(teil) {
  return !props.teil || props.teil === teil
}
</script>

<style scoped>
.gr-einst { display: flex; flex-direction: column; gap: var(--sp-4); }
</style>
