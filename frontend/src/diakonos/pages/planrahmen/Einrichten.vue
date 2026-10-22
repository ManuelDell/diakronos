<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Pläne einrichten</h1>
        <p class="dk-screen-sub">Vorlagen und unveränderliche Versionen für deine Gemeindepläne.</p>
      </div>
      <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen">Zur Planübersicht</a>
    </div>

    <p v-if="laden" role="status">Lade Planvorlagen …</p>
    <PrMeldungen :meldungen="fehler" />
    <button v-if="fehler.length" class="dk-btn dk-btn-secondary" @click="neuLaden">Nochmal</button>
    <!-- Leerzustand nur bei erfolgreich geladener, aber leerer Liste.
         Beim Laden erscheint weder dieser Hinweis noch die Liste: veraltete
         Rendererstände dürfen keine Planvorlagen behaupten, die es nicht gibt. -->
    <!-- UXP-R21: Der Anlege-Bereich steht auch OHNE vorhandene Vorlagen bereit —
         sonst kommt man auf einer frischen Installation nie zur ersten Vorlage. -->
    <section v-if="!laden && !fehler.length && rechte.darf_anlegen" class="pr-ein-neu">
      <h2>Neue Planvorlage</h2>
      <label for="pr-ein-vorlage">Vorlage</label>
      <select id="pr-ein-vorlage" v-model="vorlage" class="dk-form-select">
        <option value="">Leer anfangen</option>
        <option v-for="name in freieVorlagen" :key="name" :value="name">{{ vorlagenName(name) }}</option>
      </select>
      <p v-if="kochbuch.length && !freieVorlagen.length" class="pr-ein-hinweis">
        Alle mitgelieferten Vorlagen sind bereits angelegt. Bearbeite eine bestehende
        Vorlage, um eine neue Version anzulegen.
      </p>
      <button type="button" class="dk-btn dk-btn-primary" @click="anlegen">Planvorlage anlegen</button>
    </section>
    <template v-if="!laden && !fehler.length && typen.length">
      <section v-for="typ in typen" :key="typ.id" class="pr-ein-typ">
        <div class="pr-ein-kopf">
          <div><h2>{{ typ.name }}</h2><p>{{ typ.bereich || 'Gemeindeweit' }}</p></div>
          <a v-if="typ.darf_plantyp_bearbeiten" class="dk-btn dk-btn-secondary" :href="editorRoute(typ.schluessel)">Planvorlage bearbeiten</a>
        </div>
        <p v-if="!typ.darf_plantyp_bearbeiten">Du kannst deine eigenen Pläne vorbereiten. Die Vorlage selbst pflegen die Bereichsverantwortlichen.</p>
        <template v-else>
          <a class="dk-btn dk-btn-ghost dk-btn-sm" :href="stammdatenRoute(typ.schluessel)">Stammdaten einrichten</a>
          <details @toggle="versionenOeffnen(typ, $event.target.open)">
            <summary>Versionen ansehen · aktuell {{ typ.letzte_version?.versionsnummer || '—' }}</summary>
            <p v-if="versionLaedt[typ.id]" role="status">Lade Versionen …</p>
            <PrMeldungen :meldungen="versionFehler[typ.id] || []" />
            <button v-if="versionFehler[typ.id]?.length" class="dk-btn dk-btn-secondary dk-btn-sm" @click="versionenOeffnen(typ, true)">Versionen neu laden</button>
            <ul class="pr-ein-versionen">
              <li v-for="v in versionen[typ.id] || []" :key="v.id">
                <strong>Version {{ v.versionsnummer }}</strong> · gilt ab {{ datumText(v.gueltig_ab) }}
                <span>{{ v.kommentar || 'Ohne Kommentar' }}</span>
                <!-- UXP-R23: Die Spalte heißt `erstellt_von` (nicht `created_by`) —
                     deshalb stand hier immer „—“. -->
                <small>Erstellt von {{ v.erstellt_von || v.created_by || 'unbekannt' }} · {{ datumText(v.created?.slice(0, 10)) }}</small>
              </li>
            </ul>
          </details>
        </template>
      </section>
    </template>
    <p v-else-if="!laden && !fehler.length" class="dk-empty-desc" data-test="pr-ein-leer">
      Noch keine Planvorlagen vorhanden. Beginne mit einer Vorlage oder einem leeren Formular.
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePlanrahmen, fehlerMeldungen, datumText } from '../../composables/usePlanrahmen.js'
import { stammdatenRoute } from '../../components/planrahmen/einrichten-flow.mjs'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'

const { plantypenListe, einrichtenRechte, kochbuchListe, plantypVersionenListe } = usePlanrahmen()
const typen = ref([])
const rechte = ref({ darf_anlegen: false })
const kochbuch = ref([])
const vorlage = ref('')
const laden = ref(true)
const fehler = ref([])
const versionen = ref({})
const versionLaedt = ref({})
const versionFehler = ref({})
let request = 0
let aktiv = true
const editorRoute = key => '#/planrahmen/einrichten/' + encodeURIComponent(key)
// UXP-R9/R23: Anzeigenamen fuer ALLE Kochbuch-Vorlagen (vorher nur vier).
const VORLAGEN_NAMEN = {
  chorplan: 'Chorplan', freizeit: 'Freizeit', musikteams: 'Musikteams',
  programm: 'Programmablauf', gottesdienstablauf: 'Gottesdienstablauf',
  kindergottesdienst: 'Kindergottesdienst', musikerplan: 'Musikerplan',
  predigerplan: 'Predigerplan', putzplan: 'Putzplan', technik: 'Technik',
}
const vorlagenName = key => VORLAGEN_NAMEN[key] || key
// UXP-R5: nur noch Vorlagen anbieten, deren Kennung es noch nicht gibt.
const freieVorlagen = computed(() => kochbuch.value.filter((k) => !bekannteKennungen.value.has(k)))
const bekannteKennungen = computed(() => new Set(typen.value.map((t) => t.schluessel)))

function anlegen() {
  sessionStorage.setItem('pr-editor-vorlage', vorlage.value)
  window.location.hash = editorRoute('neu')
}
async function neuLaden() {
  const n = ++request
  laden.value = true
  fehler.value = []
  try {
    const [liste, erlaubnis, vorlagen] = await Promise.all([plantypenListe(), einrichtenRechte(), kochbuchListe()])
    if (!aktiv || n !== request) return
    typen.value = liste || []
    rechte.value = erlaubnis
    kochbuch.value = vorlagen
    versionen.value = {}
  } catch (e) {
    if (aktiv && n === request) fehler.value = fehlerMeldungen(e)
  } finally {
    if (aktiv && n === request) laden.value = false
  }
}
async function versionenOeffnen(typ, offen) {
  if (!offen || versionen.value[typ.id] || versionLaedt.value[typ.id]) return
  versionLaedt.value[typ.id] = true
  versionFehler.value[typ.id] = []
  try {
    const liste = await plantypVersionenListe(typ.schluessel)
    if (aktiv) versionen.value[typ.id] = liste.slice().reverse()
  } catch (e) {
    if (aktiv) versionFehler.value[typ.id] = fehlerMeldungen(e)
  } finally {
    if (aktiv) versionLaedt.value[typ.id] = false
  }
}
onMounted(neuLaden)
onUnmounted(() => { aktiv = false; request++ })
</script>

<style scoped>
.pr-ein-neu { display: grid; gap: 12px; padding: 18px; border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface); margin-bottom: 22px; max-width: 600px; }
.pr-ein-neu h2,.pr-ein-typ h2,.pr-ein-kopf p { margin: 0; }
.pr-ein-neu h2,.pr-ein-typ h2 { font-size: 1rem; }
.pr-ein-typ { padding: 18px; border: 1px solid var(--dk-border); border-radius: 12px; margin-top: 14px; min-width: 0; }
.pr-ein-kopf { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.pr-ein-kopf p,.pr-ein-versionen small { color: var(--dk-text-muted); }
.pr-ein-typ details { margin-top: 16px; }
.pr-ein-typ summary { cursor: pointer; }
.pr-ein-versionen { padding-left: 20px; }
.pr-ein-versionen li { margin-top: 12px; overflow-wrap: anywhere; }
.pr-ein-versionen span,.pr-ein-versionen small { display: block; margin-top: 4px; }
.pr-ein-hinweis { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0; }
</style>
