<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Eingebettet im Mitglieder-Bereich entfällt der eigene Kopf (die Seite
         hat dann den Kopf und die Reiter des Bereichs). -->
    <div v-if="!embedded" class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Löschanträge</h1>
        <p class="dk-screen-sub">Anträge auf Löschung prüfen, freigeben oder ablehnen.</p>
      </div>
    </div>

    <LoeschantraegeListe
      :antraege="antraege"
      :laedt="laedt"
      :geladen="geladen"
      :fehler="fehler"
      :filter="filter"
      :mail-eingerichtet="mailEingerichtet"
      :embedded="embedded"
      @freigeben="freigabeOeffnen"
      @ablehnen="ablehnenOeffnen"
      @filter="filterWechseln"
    />

    <!-- ── Freigeben: Name abtippen, endgültig ── -->
    <FreigabeDialog
      v-model="freigabeOffen"
      :name="ziel ? nameFuerAntrag(ziel) : ''"
      :laeuft="sendet"
      :fehler="dialogFehler"
      :mail-eingerichtet="mailEingerichtet"
      @freigeben="freigeben"
    />

    <!-- ── Ablehnen: Begründung ist Pflicht ── -->
    <AblehnenDialog
      v-model="ablehnenOffen"
      :name="ziel ? nameFuerAntrag(ziel) : ''"
      :laeuft="sendet"
      :fehler="dialogFehler"
      :mail-eingerichtet="mailEingerichtet"
      @ablehnen="ablehnen"
    />
  </div>
</template>

<script setup>
/**
 * Mitglieder → Löschanträge (DSGVO-2c).
 *
 * Die Arbeitsliste der Verwaltung: je Antrag Name, Datum und Stand, dazu
 * „Löschung freigeben“ (endgültig, Name abtippen) und „Ablehnen“ (Begründung
 * ist Pflicht, die Person erhält sie per Mail). Kein `confirm()`.
 *
 * Aufteilung wie bei `AustrittDialog`/`LoeschantragKarte`: die Liste und die
 * beiden Dialoge sind dumm, die API-Aufrufe macht DIESE Seite über
 * `composables/useLoeschantraege.js`, die Regeln stehen in
 * `components/mitglieder/loeschantraege.mjs`.
 *
 * Rechte kommen vom Server (`_require_admin` in beiden Endpunkten, dazu die
 * Regeln aus P1-8c). Die Seite blendet nur aus, was der Server ohnehin
 * verweigert — sie entscheidet nichts selbst. Ohne eingerichteten Mailversand
 * sind Freigeben und Ablehnen gesperrt, weil der Server dann NICHTS tut.
 */
import { onMounted, ref } from 'vue'
import {
  antragAblehnen, antraegeLaden, loeschungFreigeben, mailversandStand,
} from '../../composables/useLoeschantraege.js'
import { freigabeFehlerText, nameFuerAntrag } from '../../components/mitglieder/loeschantraege.mjs'
import { showToast } from '../../composables/useToast.js'
import LoeschantraegeListe from '../../components/mitglieder/LoeschantraegeListe.vue'
import FreigabeDialog from '../../components/mitglieder/FreigabeDialog.vue'
import AblehnenDialog from '../../components/mitglieder/AblehnenDialog.vue'

// Im Mitglieder-Bereich eingebettet: eigener Kopf entfällt.
defineProps({ embedded: { type: Boolean, default: false } })

const antraege = ref([])
const filter = ref('offen')
const laedt = ref(false)
const geladen = ref(false)
const fehler = ref('')
/** Mailversand „ja/nein“ — ohne Auskunft (Fehler) wird nichts gesperrt. */
const mailEingerichtet = ref(true)

const ziel = ref(null)
const freigabeOffen = ref(false)
const ablehnenOffen = ref(false)
const sendet = ref(false)
const dialogFehler = ref('')

// Der Mitglieder-Rahmen lädt nach dem Anlegen einer Person nach (defineExpose).
defineExpose({ reload: laden })

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    antraege.value = await antraegeLaden(filter.value)
    geladen.value = true
  } catch (e) {
    fehler.value = freigabeFehlerText(e, 'Die Anträge konnten nicht geladen werden.')
  } finally {
    laedt.value = false
  }
}

async function standLaden() {
  // Eine fehlende Auskunft darf die Seite nicht kippen: dann bleibt alles
  // bedienbar, und der Server entscheidet (er verweigert ohne Mail ohnehin).
  const stand = await mailversandStand()
  if (stand) mailEingerichtet.value = stand.eingerichtet
}

function filterWechseln(wert) {
  filter.value = wert
  laden()
}

function freigabeOeffnen(antrag) {
  ziel.value = antrag
  dialogFehler.value = ''
  freigabeOffen.value = true
}

function ablehnenOeffnen(antrag) {
  ziel.value = antrag
  dialogFehler.value = ''
  ablehnenOffen.value = true
}

function schliessen() {
  freigabeOffen.value = false
  ablehnenOffen.value = false
  ziel.value = null
}

async function freigeben() {
  if (sendet.value || !ziel.value) return
  sendet.value = true
  dialogFehler.value = ''
  try {
    await loeschungFreigeben(ziel.value.mitglied)
    schliessen()
    showToast('Mail versendet, Daten gelöscht.', 'success')
    await laden()
  } catch (e) {
    // Der Dialog bleibt offen: die Verwaltung soll die Meldung lesen können
    // und es erneut versuchen (bei einem Mailfehler wurde NICHTS gelöscht).
    dialogFehler.value = freigabeFehlerText(e, 'Es wurde nichts gelöscht — der Antrag bleibt offen.')
  } finally {
    sendet.value = false
  }
}

async function ablehnen(begruendung) {
  if (sendet.value || !ziel.value) return
  sendet.value = true
  dialogFehler.value = ''
  try {
    await antragAblehnen(ziel.value.mitglied, begruendung)
    schliessen()
    showToast('Mail versendet, Antrag abgelehnt.', 'success')
    await laden()
  } catch (e) {
    dialogFehler.value = freigabeFehlerText(e, 'Es wurde nichts abgelehnt — der Antrag bleibt offen.')
  } finally {
    sendet.value = false
  }
}

onMounted(() => {
  laden()
  standLaden()
})
</script>

<style scoped>
/* Der Kopf ist der Standard-Kopf der übrigen Seiten (`.dk-screen-title`). */
</style>
