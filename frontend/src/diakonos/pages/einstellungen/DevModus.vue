<template>
  <div class="dm-abschnitt">
    <h2>Dev-Modus</h2>
    <p>Der Dev-Modus hilft beim Testen: er blendet die Befund-Werkzeuge ein und
      sammelt Fehler rund um einen Befund. Er ist eine Einstellung des Servers
      und nur für Personen mit der Rolle „Tester“ (oder für Verwaltungskonten)
      verfügbar.</p>

    <DkHint v-if="laedt" role="status">Dev-Modus wird geladen …</DkHint>

    <DkHint v-else-if="nichtVerfuegbar" variant="info" role="status">
      <template v-if="nichtErlaubt">
        <strong>Für deinen Zugang ist der Dev-Modus nicht freigeschaltet.</strong>
        <p>Der Dev-Modus ist auf dieser Installation eingeschaltet, aber nur für
          Personen mit der Rolle „Tester“ (oder für Verwaltungskonten) sichtbar.
          Bitte die Gemeindeleitung, dir die Rolle „Tester“ zu geben.</p>
      </template>
      <template v-else>
        <strong>Dev-Modus ist auf dieser Installation ausgeschaltet.</strong>
        <p>Er wird von der Person eingeschaltet, die den Server betreut
          (Betriebsanleitung, Abschnitt „Entwicklungsmodus“). Diese Seite zeigt
          dann die Werkzeuge.</p>
      </template>
    </DkHint>

    <template v-else>
      <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <DkCard title="Werkzeuge">
        <p class="dm-hilfe">Das Befund-Werkzeug erscheint unten rechts auf jeder Seite.
          Es sammelt Fehler, Bilder und Notizen und erzeugt daraus einen Bericht.</p>
        <ul class="dm-status">
          <li><strong>Deine Dev-Sitzung</strong>
            <span class="dm-wert">{{ an ? 'aktiv' : 'nicht aktiv' }}</span></li>
          <li><strong>Deine Berechtigung</strong>
            <span class="dm-wert">{{ berechtigt ? 'vorhanden (Tester oder Verwaltung)' : 'nicht vorhanden' }}</span></li>
          <li v-if="kuerzel"><strong>Tastenkürzel</strong>
            <span class="dm-wert">{{ kuerzel }}</span></li>
          <li v-if="kennzahlen"><strong>Offene Befunde</strong>
            <span class="dm-wert">{{ offeneBefunde }}</span></li>
        </ul>
      </DkCard>

      <DkCard title="Dev-Befunde">
        <p class="dm-hilfe">Die gesammelten Befunde liegen im Menüpunkt „Dev-Befunde“.</p>
        <DkButton variant="secondary" size="sm" href="#/dev-befunde" @click.prevent="oeffneBefunde">
          Dev-Befunde öffnen
        </DkButton>
      </DkCard>

      <DkCard title="Demo-Daten">
        <p class="dm-hilfe">Beispieldaten (Demo-Gemeinde) gehören in eine eigene Testumgebung
          und werden nicht in dieser Oberfläche angelegt — sonst mischen sie sich mit
          echten Mitgliedern. Zum Ausprobieren eine Kopie der Installation verwenden.</p>
      </DkCard>
    </template>
  </div>
</template>

<script setup>
/**
 * N10 — Einstellungen-Abschnitt „Dev-Modus".
 *
 * Zeigt den Zustand des Dev-Modus: ob der Server ihn zulaesst
 * (`DEVMODE_ENABLED`), ob der Nutzer berechtigt ist (Tester oder Verwaltung)
 * und die Kennzahlen der Befunde. Der Abschnitt ist im Menue nur sichtbar,
 * wenn die Instanz ihn zulaesst (Konzept §7); der Server prueft dasselbe.
 *
 * Kein Schalter in der Oberflaeche: der Dev-Modus ist eine Einstellung des
 * SERVERS (Compose/.env) und pro Nutzer eine Sitzung — wer nicht darf, sieht
 * hier keinen toten Knopf, sondern den Hinweis, dass die Instanz ihn nicht
 * zulaesst.
 */
import { ref, computed, onMounted } from 'vue'
import { devmodusUebersicht, fehlerZeilen } from '../../composables/useRollenRechte.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'

const laedt = ref(true)
const nichtVerfuegbar = ref(false)
// K1 (R-N10): 404 = Instanz hat den Dev-Modus nicht zugelassen; 403 = der
// Zugang hat keine Berechtigung (fehlende Tester-Rolle). Beides blendet die
// Werkzeuge aus, aber mit unterschiedlichem Hinweis.
const nichtErlaubt = ref(false)
const berechtigt = ref(false)
const an = ref(false)
const kuerzel = ref('')
const kennzahlen = ref(null)
const fehler = ref('')

const offeneBefunde = computed(() => {
  const k = kennzahlen.value || {}
  return k.offen ?? k.offene ?? k.gesamt ?? '–'
})

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await devmodusUebersicht()
    berechtigt.value = true
    an.value = !!daten?.sitzung
    kuerzel.value = daten?.kuerzel || ''
    kennzahlen.value = daten?.kennzahlen || null
  } catch (e) {
    // 404 = Instanz laesst den Dev-Modus nicht zu; 403 = keine Berechtigung.
    // Beides heisst: hier gibt es keine Werkzeuge — kein Fehler, sondern ein
    // verstaendlicher Hinweis. Der Text unterscheidet sich (K1, R-N10).
    if (e?.status === 404 || e?.status === 403) {
      nichtVerfuegbar.value = true
      nichtErlaubt.value = e.status === 403
    } else {
      fehler.value = fehlerZeilen(e).join(' ')
    }
  } finally {
    laedt.value = false
  }
}

function oeffneBefunde() {
  window.location.hash = '#/dev-befunde'
}

onMounted(laden)
</script>

<style scoped>
.dm-abschnitt { display: grid; gap: var(--sp-4); min-width: 0; }
.dm-abschnitt h2, .dm-abschnitt p { margin: 0; }
.dm-hilfe { color: var(--muted); font-size: var(--fs-sm); }
.dm-status { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--sp-2); }
.dm-status li { display: flex; justify-content: space-between; gap: var(--sp-3); }
.dm-wert { color: var(--muted); }
</style>
