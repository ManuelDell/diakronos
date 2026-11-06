<template>
  <!-- UX3c (Entwurf A2): Rahmen des Bereichs „Dienste“.
       Er zeichnet die Reiterzeile EINMAL — nicht jede Seite selbst. Das
       Rechtebild wird hier geholt (wie im Gruppen-Rahmen der Anlege-Knopf):
       die Reiter erscheinen damit schon, bevor die Reiterseite geladen ist,
       und bleiben beim Wechsel stehen.
       Die Seiten selbst bleiben unverändert (MeineDienste · Uebersicht ·
       Einrichten) — der Bereich schaltet nur um. -->
  <div class="dk-screen dk-screen-enter">
    <DiensteReiter
      :reiter="DIENSTE_REITER"
      :seite="aktiveSeite"
      :darf-planen="darfPlanen"
      aria-label="Bereiche von Dienste"
    />
    <component :is="inhalt" />
  </div>
</template>

<script setup>
/**
 * Dienste-Bereich — die Klammer um die Reiter „Meine Dienste“,
 * „Dienstpläne“ und „Vorlagen“ (#/dienste…).
 *
 * Warum ein Rahmen? Ohne ihn hatte jede Reiterseite ihre eigene Reiterzeile:
 * beim Wechsel verschwand sie kurz und die Rechte mussten je Seite neu
 * geholt werden. Der Rahmen holt die Rechte EINMAL und entscheidet, welche
 * Reiter angeboten werden.
 *
 * `darfPlanen` kommt vom Server (`einrichten_rechte`, dieselbe Abfrage wie
 * die Planübersicht): erfolgreich gelesen = Admin, Bereichs- oder
 * Gruppenverantwortlicher. 403 = kein Planungsrecht. Bis zur Antwort bleibt
 * `undefined` — dann zeigt `sichtbareReiter` die Administration (kein
 * Aufblitzen eines falschen Reiters).
 */
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import DiensteReiter from '../../components/DiensteReiter.vue'
import { DIENSTE_REITER, reiterAusHash } from '../../menue.js'
import { currentPageName } from '../../router.js'
import { usePlanrahmen } from '../../composables/usePlanrahmen.js'

const { einrichtenRechte } = usePlanrahmen()

const MeineDienste = defineAsyncComponent(() => import('../planrahmen/MeineDienste.vue'))
const Uebersicht = defineAsyncComponent(() => import('../planrahmen/Uebersicht.vue'))
const Einrichten = defineAsyncComponent(() => import('../planrahmen/Einrichten.vue'))

/**
 * Seite je Reiter. Der Router lädt für alle Dienste-Adressen diesen Rahmen;
 * welche Seite darin steht, entscheidet der Seitenname der Route.
 */
const SEITEN = {
  Dienste: MeineDienste,
  PlanrahmenDienste: MeineDienste,
  DiensteDienstplaene: Uebersicht,
  DiensteVorlagen: Einrichten,
}
const inhalt = computed(() => SEITEN[currentPageName.value] || SEITEN.PlanrahmenDienste)

/** Planungsrecht: `undefined` = noch nicht geantwortet, dann keine Annahme. */
const darfPlanen = ref(undefined)

onMounted(async () => {
  try {
    await einrichtenRechte()
    darfPlanen.value = true
  } catch {
    // 403 (und jeder andere Fehlschlag) heißt: kein Planungsrecht. Die
    // Reiterseite zeigt den Grund ohnehin selbst an.
    darfPlanen.value = false
  }
})

/**
 * Aktiver Reiter. Bevorzugt die Adresse (auch Unteradressen wie
 * `#/dienste/vorlagen/‹Vorlage›`), sonst der Seitenname der geöffneten Seite.
 */
const aktiveSeite = computed(() => {
  const ausHash = reiterAusHash(DIENSTE_REITER, window.location.hash)
  if (ausHash) return ausHash
  const seite = currentPageName.value
  return seite === 'Dienste' ? 'PlanrahmenDienste' : seite
})
</script>
