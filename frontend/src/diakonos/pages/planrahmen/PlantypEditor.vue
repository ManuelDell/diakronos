<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">
    <div class="dk-crumbs">
      <a class="dk-crumb" href="#/planrahmen">Pläne</a>
      <span class="dk-crumb-sep" aria-hidden="true">/</span>
      <a class="dk-crumb" href="#/planrahmen/einrichten">Einrichten</a>
      <span class="dk-crumb-sep" aria-hidden="true">/</span>
      <span class="dk-crumb-current">{{ titel }}</span>
    </div>

    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">{{ titel }}</h1>
        <p class="dk-screen-sub">
          <span v-if="definition.id" class="dk-badge">{{ definition.id }}</span>
          <span v-if="aktuelleVersion" class="pr-pe-meta">Version {{ aktuelleVersion.versionsnummer }} · gültig ab {{ datumText(aktuelleVersion.gueltig_ab, false) }}<template v-if="aktuelleVersion.erstellt_von"> · von {{ aktuelleVersion.erstellt_von }}</template></span>
          <span v-else-if="definition.id" class="pr-pe-meta">noch keine Version gespeichert</span>
          <span v-if="dirty" class="dk-badge dk-badge-warning">ungesicherte Änderungen</span>
        </p>
      </div>
      <div class="dk-screen-actions">
        <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen/einrichten">Zur Liste</a>
        <button v-if="darfVorlageBearbeiten && !laden" type="button" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="speichert || !!jsonFehler" @click="speichernOffen = true">Als neue Version speichern …</button>
      </div>
    </div>

    <div v-if="laden" class="pr-pe-zustand">Lade Planvorlage …</div>

    <div v-else-if="seitenFehler.length" class="pr-pe-zustand pr-pe-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen/einrichten">Zurück zur Liste</a>
    </div>

    <template v-else>
      <!-- ST1: gemerkter Entwurf — wiederherstellen oder verwerfen. -->
      <div v-if="entwurfFrage" class="pr-pe-entwurf dk-card" data-test="pr-pe-entwurf-frage">
        <p class="pr-pe-entwurf-text">Es gibt einen gemerkten Entwurf dieser Planvorlage (lokale, ungespeicherte Änderungen). Entwurf wiederherstellen?</p>
        <div class="pr-pe-entwurf-aktionen">
          <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" data-test="pr-pe-entwurf-wiederherstellen" @click="entwurfFortsetzen">Entwurf wiederherstellen</button>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" data-test="pr-pe-entwurf-verwerfen" @click="entwurfVerwerfen">Verwerfen</button>
        </div>
      </div>

      <!-- Reiter: Formular · JSON · Probelauf -->
      <div class="dk-tab-list pr-pe-tabs" role="tablist" aria-label="Bearbeitungsweise">
        <button
          v-for="r in REITER" :key="r.wert" type="button" role="tab"
          class="dk-tab" :class="{ 'is-active': reiter === r.wert }"
          :aria-selected="reiter === r.wert ? 'true' : 'false'"
          @click="reiterWechseln(r.wert)"
        >{{ r.name }}</button>
      </div>

      <!-- Prüfstand immer sichtbar -->
      <div v-if="prueftLaeuft" class="pr-pe-pruefstatus" role="status">Eingaben werden geprüft …</div>
      <PrMeldungen v-else-if="pruefMeldungen.length" :meldungen="pruefMeldungen" zusammenfassung />
      <div v-else-if="pruefStand === 'ok'" class="pr-pe-pruefstatus pr-pe-pruefstatus--ok" role="status">Keine Beanstandungen — die Definition ist gültig.</div>

      <!-- Formular -->
      <div v-if="reiter === 'formular'" class="pr-pe-form">
        <!-- UXP-R5: Kennung gehört schon einer Vorlage -> nicht still überschreiben. -->
        <div v-if="istNeu && vorhandeneKennung" class="pr-pe-kollision dk-card" data-test="pr-pe-kennung-kollision">
          <p class="pr-pe-kollision-text">
            Die Kennung <strong>{{ definition.id }}</strong> gehört bereits zur Planvorlage
            „{{ vorhandeneKennungName }}“. Speichern legt dort eine NEUE VERSION an, die
            bestehende Vorlage wird ab dem Stichtag geändert.
          </p>
          <p class="pr-pe-kollision-text">
            Für eine eigenständige Vorlage bitte eine andere Kennung wählen.
          </p>
          <label class="pr-pe-checkbox">
            <input type="checkbox" v-model="kollisionBestaetigt" />
            Ich möchte eine neue Version der bestehenden Vorlage „{{ vorhandeneKennungName }}“ anlegen.
          </label>
        </div>
        <section class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Grunddaten</h2>
          <div class="pr-pe-zeile">
            <label class="pr-pe-label">Kennung (stabiler Kurzname)
              <input v-model="definition.id" type="text" class="dk-form-input pr-pe-kurz" placeholder="chorplan" />
              <span class="pr-pe-hilfe">Kleinbuchstaben, Ziffern, _ und - — wird versioniert, nie der Anzeigename.</span>
              <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="id" />
            </label>
            <label class="pr-pe-label">Anzeigename
              <input v-model="definition.name" type="text" class="dk-form-input" placeholder="Chorplan" />
              <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="name" />
            </label>
            <label class="pr-pe-label">Dienstbereich
              <!-- UXP-R9: Auswahlliste statt Freitext; findet die Kochbuch-Bereiche
                   keine Entsprechung, bleibt der eingetragene Wert wählbar. -->
              <select v-if="bereichOptionen.length" v-model="definition.bereich" class="dk-form-select">
                <option value="">— keinen Bereich —</option>
                <option v-for="b in bereichOptionen" :key="b.kennung" :value="b.kennung">{{ b.name }}</option>
                <option v-if="unbekannterBereich" :value="definition.bereich">{{ definition.bereich }} (nicht vorhanden)</option>
              </select>
              <input v-else v-model="definition.bereich" type="text" class="dk-form-input" placeholder="Chor" />
              <span v-if="definition.bereich && !bereichBekannt" class="pr-pe-hilfe pr-pe-hilfe--warnung">
                Diesen Dienstbereich gibt es in der Gemeinde nicht. Wähle einen vorhandenen Bereich.
              </span>
              <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="bereich" />
            </label>
          </div>
          <label class="pr-pe-label">Beschreibung
            <textarea v-model="definition.beschreibung" rows="2" class="dk-form-textarea" placeholder="Was regelt dieser Planvorlage?"></textarea>
            <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="beschreibung" />
          </label>
          <!-- ST3: Gruppenbindung (Personenpool) — nur Admin/Bereichsverantwortung
               aendert die Vorlage; die Liste liefert einrichten_rechte. -->
          <div class="pr-pe-abschnitt-teil">
            <h3 class="pr-pe-unter-titel">Personen aus Gruppen (Personenpool)</h3>
            <p class="pr-pe-hinweis">
              Binde diese Planvorlage an eine oder mehrere Gruppen. Dann können nur noch
              Mitglieder dieser Gruppen eingeplant werden — die Planer sehen nur, was sie
              sehen müssen. Ohne Auswahl gilt weiter: alle Personen.
            </p>
            <p v-if="!gruppenAuswahl.length" class="pr-pe-leer">Keine Gruppen vorhanden.</p>
            <div v-else class="pr-pe-chips">
              <label v-for="g in gruppenAuswahl" :key="g.kennung" class="pr-pe-chip">
                <input type="checkbox" :checked="gewaehlteGruppen.includes(g.kennung)"
                       @change="gruppeToggle(g.kennung, $event.target.checked)" />
                {{ g.name }}
              </label>
            </div>
            <!-- UXP-R10: veraltete Gruppenbindungen sichtbar machen und entfernen. -->
            <div v-if="unbekannteGruppen.length" class="pr-pe-hinweis pr-pe-hinweis--warnung" data-test="pr-pe-unbekannte-gruppen">
              <p class="pr-pe-hinweis-text">
                Diese Gruppenbindungen existieren in der Gemeinde nicht mehr und
                wirken als leerer Personenpool:
              </p>
              <ul class="pr-pe-unbekannte-liste">
                <li v-for="k in unbekannteGruppen" :key="k">
                  <span class="pr-pe-unbekannte-kennung">{{ gruppenName(k) }}</span>
                  <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="gruppeToggle(k, false)">entfernen</button>
                </li>
              </ul>
            </div>
            <label v-if="gewaehlteGruppen.length" class="pr-pe-checkbox">
              <input type="checkbox" :checked="definition.inkl_untergruppen === true"
                     @change="inklUntergruppenSetzen($event.target.checked)" />
              Auch Mitglieder der Untergruppen einbeziehen
            </label>
            <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="gruppen" />
            <PrPfadMeldungen :meldungen="pruefMeldungen" pfad="inkl_untergruppen" />
          </div>
        </section>

        <section id="pr-pe-termine" class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Termine und Felder</h2>
          <PrReihenEditor :definition="definition" :kontext="kontext" :meldungen="pruefMeldungen" />
        </section>

        <section class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Anlässe</h2>
          <p class="pr-pe-hinweis">
            Anlässe markieren einzelne Termine (Abendmahl, Kinderchor, Erntedank …)
            und können auf die Struktur wirken: Felder ausblenden (ohne), zusätzliche
            Felder zeigen (mit) oder eigene Regeln steuern. Ein Feiertag setzt
            automatisch einen Anlass gleichen Namens.
          </p>
          <p v-if="!anlaesse.length" class="pr-pe-leer">Keine Anlässe — jeder Termin hat dieselbe Struktur.</p>
          <div v-for="(a, ai) in anlaesse" :key="ai" class="pr-pe-anlass">
            <div class="pr-pe-zeile">
              <label class="pr-pe-label">Kennung
                <input v-model="a.id" type="text" class="dk-form-input pr-pe-kurz" placeholder="abendmahl" />
                <PrPfadMeldungen :meldungen="pruefMeldungen" :pfad="'anlaesse/' + ai + '/id'" />
              </label>
              <label class="pr-pe-label">Name
                <input v-model="a.name" type="text" class="dk-form-input" placeholder="Abendmahl" />
                <PrPfadMeldungen :meldungen="pruefMeldungen" :pfad="'anlaesse/' + ai + '/name'" />
              </label>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Anlass entfernen" @click="anlaesse.splice(ai, 1)">✕</button>
            </div>

            <h5 class="pr-pe-unter-titel">Welche Felder entfallen bei diesem Anlass? (ohne)</h5>
            <div class="pr-pe-chips">
              <label v-for="fid in topFeldIds" :key="fid" class="pr-pe-chip">
                <input type="checkbox" :checked="wirkungOhne(a).includes(fid)" @change="ohneToggle(a, fid, $event.target.checked)" />
                {{ fid }}
              </label>
            </div>

            <PrPfadMeldungen :meldungen="pruefMeldungen" :pfad="'anlaesse/' + ai + '/wirkung/ohne'" />
            <h5 class="pr-pe-unter-titel">Zusätzliche Felder, die nur bei diesem Anlass erscheinen (mit)</h5>
            <PrFelderEditor
              v-if="Array.isArray(a.wirkung?.mit)"
              :felder="a.wirkung.mit" :kontext="kontext" :gruppen-modus="true"
              :meldungen="pruefMeldungen" :basis-pfad="'anlaesse/' + ai + '/wirkung/mit/'"
            />
            <div class="pr-pe-zeile">
              <button v-if="!Array.isArray(a.wirkung?.mit)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="wirkungAnlegen(a); a.wirkung.mit = []">+ Zusatzfelder hinzufügen</button>
              <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="a.wirkung.mit = undefined">Zusatzfelder entfernen</button>
            </div>

            <h5 class="pr-pe-unter-titel">Eigene Regeln nur bei diesem Anlass</h5>
            <PrRegelnEditor
              v-if="Array.isArray(a.wirkung?.regeln)"
              :regeln="a.wirkung.regeln" :bausteine="regelBausteine" :kontext="kontext"
              :meldungen="pruefMeldungen" :basis-pfad="'anlaesse/' + ai + '/wirkung/regeln'"
            />
            <div class="pr-pe-zeile">
              <button v-if="!Array.isArray(a.wirkung?.regeln)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="wirkungAnlegen(a); a.wirkung.regeln = []">+ Anlassregeln hinzufügen</button>
              <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="a.wirkung.regeln = undefined">Anlassregeln entfernen</button>
            </div>

            <h5 class="pr-pe-unter-titel">Wirkung nur unter Bedingung</h5>
            <PrKnotenEditor v-if="istKnoten(a.wirkung?.bedingung)" :knoten="a.wirkung.bedingung" modus="bedingung" :kontext="kontext" />
            <PrPfadMeldungen :meldungen="pruefMeldungen" :pfad="'anlaesse/' + ai + '/wirkung/bedingung'" />
            <div class="pr-pe-zeile">
              <button v-if="!istKnoten(a.wirkung?.bedingung)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="wirkungAnlegen(a); a.wirkung.bedingung = { anlass: '' }">+ Bedingung hinzufügen</button>
              <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="a.wirkung.bedingung = undefined">Bedingung entfernen</button>
            </div>
          </div>
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="anlaesse.push({ id: '', name: '' })">+ Anlass hinzufügen</button>
        </section>

        <section id="pr-pe-deklarationen" class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Deklarationen</h2>
          <PrDeklarationenEditor :definition="definition" :kontext="kontext" :meldungen="pruefMeldungen" />
        </section>

        <section id="pr-pe-regeln" class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Regeln</h2>
          <PrRegelnEditor :regeln="regeln" :bausteine="regelBausteine" :kontext="kontext" :meldungen="pruefMeldungen" />
          <p v-if="!Object.keys(regelBausteine).length" class="pr-pe-hinweis">
            Die Baustein-Registry wird noch nachgeladen — die Formularfelder der
            Regeln erscheinen, sobald die Definition der Bausteine da ist.
          </p>
        </section>

        <section class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Ansichten</h2>
          <PrAnsichtenEditor :ansichten="ansichten" :definition="definition" :meldungen="pruefMeldungen" />
        </section>

        <section class="pr-pe-abschnitt">
          <h2 class="pr-pe-titel">Versionen</h2>
          <p v-if="!versionen.length" class="pr-pe-leer">Diese Definition wurde noch nie gespeichert.</p>
          <ul v-else class="pr-pe-versionen">
            <li v-for="v in versionen.slice().reverse()" :key="v.id" class="pr-pe-version">
              <span class="pr-pe-version-haupt">Version {{ v.versionsnummer }} · gültig ab {{ datumText(v.gueltig_ab, false) }}</span>
              <span class="pr-pe-version-neben">
                <span v-if="v.erstellt_von" class="dk-badge">{{ v.erstellt_von }}</span>
                <span v-if="v.kommentar" class="pr-pe-version-kommentar">{{ v.kommentar }}</span>
              </span>
            </li>
          </ul>
          <p class="pr-pe-hinweis">
            Jedes Speichern legt eine neue unveränderliche Version an. Bereits
            vergangene Termine behalten ihre alte Struktur.
          </p>
        </section>
      </div>

      <!-- JSON: synchron und verlustfrei -->
      <div v-else-if="reiter === 'json'" class="pr-pe-json">
        <p class="pr-pe-hinweis">
          Die vollständige Definition als JSON. Gültige Änderungen wirken sofort
          im Formular; ein ungültiger Text bleibt erhalten und wird nicht verworfen.
        </p>
        <PrMeldungen v-if="jsonFehler" :meldungen="[{ stufe: 'fehler', meldung: jsonFehler, hinweis: 'Der Text bleibt erhalten — bitte korrigieren.' }]" />
        <textarea
          v-model="jsonTextRoh" rows="26" class="dk-form-textarea pr-pe-jsonfeld" id="pr-pe-json"
          spellcheck="false" aria-label="Definition als JSON"
          @input="jsonUebernehmen"
        ></textarea>
      </div>

      <!-- Probelauf (Parent-Komponente, API trockenlauf) -->
      <div v-else-if="reiter === 'probelauf'" class="pr-pe-probe" id="pr-pe-probelauf">
        <Probelauf :definition="definition" />
      </div>
    </template>

    <BedarfDialog v-model="bedarfOffen" :bedarf="bedarfListe" @einrichten="stammdatenOeffnen" />

    <!-- ST1: Stammdaten im Seitenpanel (Entwurf des Editors bleibt erhalten). -->
    <PrStammdatenPanel
      v-model="stammdatenPanelOffen"
      :plantyp="definition.id"
      titel="Stammdaten pflegen"
      untertitel="Personen und Listen ergänzen — dann zurück zur Planvorlage."
      @geschlossen="stammdatenPanelGeschlossen"
    />
    <!-- Speichern: neue Version mit Pflichtangaben -->
    <DkModal variant="planrahmen" v-model="speichernOffen" title="Als neue Version speichern">
      <!-- OP-UI-23: <form @submit.prevent> — Enter im Feld speichert. -->
      <form class="pr-pe-speichern" @submit.prevent="speichern">
        <button type="submit" class="pr-pe-sr-submit" tabindex="-1" aria-hidden="true"></button>
        <!-- UXP-R12: ehrlicher Dialogtext + Zahl der betroffenen Termine. -->
        <p class="pr-pe-hinweis">
          Vergangene Termine behalten ihre alte Struktur. Bereits angelegte Termine
          <strong>ab dem Stichtag</strong> werden auf die neue Version umgebunden —
          das betrifft die unten genannte Zahl.
        </p>
        <p v-if="auswirkung" class="pr-pe-hinweis" data-test="pr-pe-auswirkung">
          Ab {{ datumText(gueltigAb, false) }} sind
          <strong>{{ auswirkung.termine }}</strong> Termine in
          <strong>{{ auswirkung.plaene }}</strong> Plänen betroffen.
        </p>
        <PrMeldungen v-if="speichernFehler.length" :meldungen="speichernFehler" />
        <PrMeldungen v-if="pruefFehler.length" :meldungen="pruefFehler" />
        <label class="pr-pe-label">Ab welchem Tag gilt diese Version? (Pflicht)
          <input v-model="gueltigAb" type="date" class="dk-form-input" :aria-invalid="!!speichernFeldFehler.gueltigAb" @change="auswirkungLaden" />
          <span v-if="speichernFeldFehler.gueltigAb" role="alert" class="dk-form-error">{{ speichernFeldFehler.gueltigAb }}</span>
        </label>
        <label class="pr-pe-label">Was hat sich geändert? (Pflicht)
          <textarea v-model="kommentar" rows="3" class="dk-form-textarea" :aria-invalid="!!speichernFeldFehler.kommentar" placeholder="z. B. Drittes Lied optional gemacht"></textarea>
          <span v-if="speichernFeldFehler.kommentar" role="alert" class="dk-form-error">{{ speichernFeldFehler.kommentar }}</span>
        </label>
      </form>
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="speichernOffen = false">Abbrechen</button>
        <button
          type="button" class="dk-btn dk-btn-primary"
          :disabled="speichert"
          @click="speichern"
        >{{ speichert ? 'Wird gespeichert …' : 'Version speichern' }}</button>
      </template>
    </DkModal>
  </div>
</template>

<script setup>
/**
 * Plantyp-Editor (UI2): vollständiges Formular statt JSON-only.
 *
 * - Formular-Reiter: Grunddaten, Termine/Felder (Kurzform oder mehrere,
 *   ggf. abgeleitete Reihen), Anlässe mit Wirkung, Deklarationen
 *   (Parameter/Merkmale/Sammlungen/Rollen), Regeln aus der
 *   Baustein-Registry, Ansichten mit Formatvorschau.
 * - JSON-Reiter: synchron und verlustfrei in beide Richtungen.
 * - Probelauf-Reiter: trockener Lauf ohne Speichern.
 *
 * Route: '#/planrahmen/einrichten/neu' (neu, ggf. mit sessionStorage-Vorlage
 * 'pr-editor-vorlage' = Kochbuchkennung) oder '#/planrahmen/einrichten/<id>'.
 * Emits: 'gespeichert' mit { plantyp, version }. Exposed: gespeicherteTypId.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { getRouteParam, onBeforeEach } from '../../router.js'
import { usePlanrahmen, fehlerMeldungen, datumText } from '../../composables/usePlanrahmen.js'
import { useEntwurf } from '../../composables/useEntwurf.js'
import { showToast } from '../../composables/useToast.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import DkModal from '../../components/DkModal.vue'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import PrPfadMeldungen from '../../components/planrahmen/PrPfadMeldungen.vue'
import PrReihenEditor from '../../components/planrahmen/PrReihenEditor.vue'
import PrFelderEditor from '../../components/planrahmen/PrFelderEditor.vue'
import PrKnotenEditor from '../../components/planrahmen/PrKnotenEditor.vue'
import PrDeklarationenEditor from '../../components/planrahmen/PrDeklarationenEditor.vue'
import PrRegelnEditor from '../../components/planrahmen/PrRegelnEditor.vue'
import PrAnsichtenEditor from '../../components/planrahmen/PrAnsichtenEditor.vue'
import Probelauf from '../../components/planrahmen/Probelauf.vue'
import BedarfDialog from '../../components/planrahmen/BedarfDialog.vue'
import PrStammdatenPanel from '../../components/planrahmen/PrStammdatenPanel.vue'
import { leereDefinition, jsonText, jsonUebernehmen as jsonPruefen, feldPfadListe, feldKennungen } from '../../components/planrahmen/editor.mjs'

const emit = defineEmits(['gespeichert'])

const { schemaHolen, kochbuchListe, kochbuchHolen, plantypPruefen, plantypSpeichern, plantypVersionenListe, plantypAuswirkung, plantypenListe, bedarf, einrichtenRechte } = usePlanrahmen()

// UXP-R5: Kennungen, die bereits eine Vorlage belegen (Anlege-Weg warnt dann).
const bekannteKennungen = ref(new Map())
// UXP-R5: ausdrückliche Bestätigung „neue Version der bestehenden Vorlage“.
const kollisionBestaetigt = ref(false)

const REITER = [
  { wert: 'formular', name: 'Formular' },
  { wert: 'json', name: 'JSON (für Fortgeschrittene)' },
  { wert: 'probelauf', name: 'Probelauf' },
]

const laden = ref(true)
const darfVorlageBearbeiten = ref(false)
const seitenFehler = ref([])
const definition = ref(leereDefinition())
const reiter = ref('formular')
const versionen = ref([])
const aktuelleVersion = ref(null)
const regelBausteine = ref({})

// ── Prüfung (debounced, gegen den Server) ──────────────────────────────────
const pruefMeldungen = ref([])
const prueftLaeuft = ref(false)
const pruefStand = ref('')
let pruefNummer = 0
let pruefTimer = null

const signatur = computed(() => JSON.stringify(definition.value))
watch(signatur, () => pruefenGeplant())

function pruefenGeplant() {
  clearTimeout(pruefTimer)
  pruefTimer = setTimeout(pruefen, 700)
}

async function pruefen() {
  const n = ++pruefNummer
  prueftLaeuft.value = true
  try {
    const roh = JSON.parse(JSON.stringify(definition.value))
    const erg = await plantypPruefen(roh)
    if (n !== pruefNummer) return
    pruefMeldungen.value = Array.isArray(erg?.meldungen) ? erg.meldungen : []
    pruefStand.value = erg?.gueltig ? 'ok' : 'fehler'
  } catch (err) {
    if (n !== pruefNummer) return
    pruefMeldungen.value = fehlerMeldungen(err)
    pruefStand.value = 'fehler'
  } finally {
    if (n === pruefNummer) prueftLaeuft.value = false
  }
}

const pruefFehler = computed(() => pruefMeldungen.value.filter((m) => m.stufe === 'fehler'))

// ── Kontext für die Baukästen ─────────────────────────────────────────────

// ST3: waehlbare Gruppen fuer die Gruppenbindung (aus einrichten_rechte).
const gruppenAuswahl = ref([])
// UXP-R9: waehlbare Dienstbereiche (Kennung + Anzeigename) aus einrichten_rechte.
const bereichOptionen = ref([])
const gewaehlteGruppen = computed(() => Array.isArray(definition.value.gruppen) ? definition.value.gruppen : [])

/** UXP-R10: gebundene Gruppen, die es in der Gemeinde nicht (mehr) gibt. */
const unbekannteGruppen = computed(() => {
  const bekannt = new Set(gruppenAuswahl.value.map((g) => g.kennung))
  return gewaehlteGruppen.value.filter((k) => k && !bekannt.has(k))
})

/** UXP-R9/R13: den Anzeigenamen einer gebundenen Gruppe nennen. */
function gruppenName(kennung) {
  const treffer = gruppenAuswahl.value.find((g) => g.kennung === kennung)
  return treffer?.name || kennung
}

const bereichBekannt = computed(() =>
  !definition.value.bereich || bereichOptionen.value.some((b) => b.kennung === definition.value.bereich))
const unbekannterBereich = computed(() => !!definition.value.bereich && !bereichBekannt.value)

/** UXP-R5: die Kennung gehört bereits einer bestehenden Vorlage. */
const vorhandeneKennung = computed(() =>
  !!definition.value.id && bekannteKennungen.value.has(definition.value.id))
/** Name der bestehenden Vorlage zu dieser Kennung (oder die Kennung selbst). */
const vorhandeneKennungName = computed(() =>
  bekannteKennungen.value.get(definition.value.id) || definition.value.id)

function gruppeToggle(kennung, an) {
  const liste = gewaehlteGruppen.value.slice()
  const i = liste.indexOf(kennung)
  if (an && i === -1) liste.push(kennung)
  if (!an && i !== -1) liste.splice(i, 1)
  if (liste.length) definition.value.gruppen = liste
  else {
    definition.value.gruppen = undefined
    definition.value.inkl_untergruppen = undefined
  }
}
function inklUntergruppenSetzen(an) {
  definition.value.inkl_untergruppen = an ? true : undefined
}

const anlaesse = computed(() => (Array.isArray(definition.value.anlaesse) ? definition.value.anlaesse : []))
const regeln = computed(() => (Array.isArray(definition.value.regeln) ? definition.value.regeln : []))
const ansichten = computed(() => (Array.isArray(definition.value.ansichten) ? definition.value.ansichten : []))

/** Top-Level-Felder für die Anlass-Wirkung 'ohne' (Kurzform oder Reihen). */
const topFeldIds = computed(() => feldKennungen(definition.value))

const kontext = computed(() => ({
  parameter: definition.value.parameter || [],
  anlaesse: anlaesse.value,
  rollen: definition.value.rollen || [],
  sammlungen: definition.value.sammlungen || [],
  feldPfade: feldPfadListeGesamt(),
}))

function feldPfadListeGesamt() {
  const liste = []
  if (Array.isArray(definition.value.felder)) liste.push(...feldPfadListe(definition.value.felder))
  for (const r of definition.value.terminreihen || []) liste.push(...feldPfadListe(r.felder || []))
  return liste
}

function wirkungAnlegen(anlass) {
  if (!anlass.wirkung || typeof anlass.wirkung !== 'object') anlass.wirkung = {}
}
function wirkungOhne(anlass) {
  return Array.isArray(anlass.wirkung?.ohne) ? anlass.wirkung.ohne : []
}
function ohneToggle(anlass, fid, an) {
  wirkungAnlegen(anlass)
  const liste = wirkungOhne(anlass).slice()
  const i = liste.indexOf(fid)
  if (an && i === -1) liste.push(fid)
  if (!an && i !== -1) liste.splice(i, 1)
  if (liste.length) anlass.wirkung.ohne = liste
  else anlass.wirkung.ohne = undefined
}
function istKnoten(wert) {
  return !!wert && typeof wert === 'object' && !Array.isArray(wert)
}

// ── JSON-Reiter (synchron, verlustfrei) ────────────────────────────────────

const jsonTextRoh = ref('')
const jsonFehler = ref('')

async function reiterWechseln(neu) {
  if (neu === reiter.value) return
  if (reiter.value === 'json' && jsonFehler.value) {
    if (!await bestaetigen({ titel: 'Ungültigen Text verwerfen?', text: 'Der eingegebene Text kann nicht gelesen werden. Beim Wechsel wird der letzte lesbare Stand wiederhergestellt.', aktion: 'Text verwerfen', gefahr: true })) return
    jsonFehler.value = ''
  }
  if (neu === 'json') {
    jsonTextRoh.value = jsonText(definition.value)
    jsonFehler.value = ''
  }
  reiter.value = neu
}

function jsonUebernehmen() {
  const erg = jsonPruefen(jsonTextRoh.value)
  if (erg.ok) {
    jsonFehler.value = ''
    // Verlustfrei: nur der Text der Oberfläche bleibt eigens erhalten;
    // die Formularansicht folgt der gültigen Definition.
    definition.value = erg.definition
  } else {
    jsonFehler.value = erg.fehler
  }
}

// ── Laden, Speichern, Versionen ────────────────────────────────────────────

const titel = computed(() => definition.value.name || (istNeu.value ? 'Neue Planvorlage' : definition.value.id || 'Planvorlage'))
const istNeu = computed(() => (getRouteParam('id') || 'neu') === 'neu')

const gespeicherteTypId = ref('')

let ladeNummer = 0
watch(() => getRouteParam('id', 'PlanrahmenPlantypEditor'), ladenAlles, { immediate: true, flush: 'sync' })

async function ladenAlles() {
  const n = ++ladeNummer
  const id = getRouteParam('id', 'PlanrahmenPlantypEditor')
  ++pruefNummer
  clearTimeout(pruefTimer)
  if (!id) return
  laden.value = true
  seitenFehler.value = []
  darfVorlageBearbeiten.value = false
  try {
    // Keine bedienbare Vorlage zeigen, bevor der Server das Recht bestätigt.
    const rechte = await einrichtenRechte()
    let erlaubt = rechte?.darf_anlegen === true
    if (id !== 'neu') {
      const typen = await plantypenListe()
      erlaubt = (typen || []).some(t => (t.id === id || t.schluessel === id) && t.darf_plantyp_bearbeiten === true)
    }
    if (n !== ladeNummer) return
    if (!erlaubt) throw new Error('Du darfst diese Planvorlage nicht bearbeiten. Bitte wende dich an die Bereichsverantwortlichen.')
    darfVorlageBearbeiten.value = true
    // Vorlage aus der Einrichten-Liste (einmalig, danach verworfen).
    const vorlage = window.sessionStorage.getItem('pr-editor-vorlage') || ''
    window.sessionStorage.removeItem('pr-editor-vorlage')

    const [schema, kochbuch] = await Promise.all([
      schemaHolen().catch(() => null),
      kochbuchListe().catch(() => []),
    ])
    if (n !== ladeNummer) return
    regelBausteine.value = schema?.['x-regel-bausteine'] || {}
    // UXP-R5: bestehende Kennungen merken, damit der Anlege-Weg warnen kann.
    try {
      const typen = await plantypenListe()
      bekannteKennungen.value = new Map(
        (Array.isArray(typen) ? typen : [])
          .filter((t) => t.schluessel)
          .map((t) => [t.schluessel, t.name || t.schluessel]))
    } catch { bekannteKennungen.value = new Map() }
    // ST3: waehlbare Gruppen (nur berechtigte Planer erhalten eine Liste).
    try {
      const rechte = await einrichtenRechte()
      gruppenAuswahl.value = Array.isArray(rechte?.gruppen) ? rechte.gruppen : []
      // UXP-R9/R13: Bereiche mit Anzeigename (bereich_liste) — Fallback auf die
      // reine Kennungsliste, falls ein aelterer Server sie noch nicht liefert.
      bereichOptionen.value = Array.isArray(rechte?.bereich_liste) && rechte.bereich_liste.length
        ? rechte.bereich_liste
        : (Array.isArray(rechte?.bereiche) ? rechte.bereiche.map((k) => ({ kennung: k, name: k })) : [])
    } catch {
      gruppenAuswahl.value = []
      bereichOptionen.value = []
    }
    if (n !== ladeNummer) return

    if (id === 'neu') {
      if (vorlage) {
        const vorlagenDefinition = await kochbuchHolen(vorlage)
        if (n !== ladeNummer) return
        definition.value = vorlagenDefinition
      } else {
        definition.value = leereDefinition()
      }
      versionen.value = []
      aktuelleVersion.value = null
    } else {
      const liste = await plantypVersionenListe(decodeURIComponent(id))
      if (n !== ladeNummer) return
      versionen.value = Array.isArray(liste) ? liste : []
      const letzte = versionen.value.slice().sort((a, b) => (b.versionsnummer || 0) - (a.versionsnummer || 0))[0] || null
      aktuelleVersion.value = letzte
      definition.value = letzte?.definition ? JSON.parse(JSON.stringify(letzte.definition)) : leereDefinition()
    }
    for (const key of ['anlaesse', 'regeln', 'ansichten']) {
      if (!Array.isArray(definition.value[key])) definition.value[key] = []
    }
    grundstand.value = signatur.value
    // ST1: lokalen Entwurf anbieten, wenn er sich vom Serverstand unterscheidet.
    entwurfFrage.value = false
    entwurfBereit = false
    const entwurfsStand = entwurfApi().laden()
    if (entwurfsStand && JSON.stringify(entwurfsStand) !== grundstand.value) {
      entwurfFrage.value = true
    } else {
      entwurfBereit = true
    }
    pruefen()
  } catch (err) {
    if (n === ladeNummer) seitenFehler.value = fehlerMeldungen(err)
  } finally {
    if (n === ladeNummer) laden.value = false
  }
}

// ── Schmutzschutz ──────────────────────────────────────────────────────────

const grundstand = ref('')
const dirty = computed(() => darfVorlageBearbeiten.value && !laden.value && !seitenFehler.value.length
  && (signatur.value !== grundstand.value || !!jsonFehler.value))

const abbrechenGuard = () => !dirty.value || bestaetigen({ titel: 'Änderungen verwerfen?', text: 'Deine Änderungen an dieser Planvorlage wurden noch nicht gespeichert.', aktion: 'Verwerfen', gefahr: true, abbrechen: 'Weiter bearbeiten' })
const guardEntfernen = onBeforeEach(abbrechenGuard)

// ── Entwurf (ST1): ungespeicherte Änderungen lokal sichern ─────────────────

// Ein Entwurf je Planvorlage (bzw. 'neu'). Der Schlüssel steht erst nach dem
// Laden der Route fest — deshalb wird der Entwurf pro Zugriff gebildet.
const entwurfFrage = ref(false)
let entwurfBereit = false
let entwurfTimer = null

function entwurfZweck() {
  const id = getRouteParam('id', 'PlanrahmenPlantypEditor') || 'neu'
  return 'plantyp-editor:' + decodeURIComponent(id)
}
function entwurfApi() { return useEntwurf(entwurfZweck()) }

function entwurfSichern() {
  if (!entwurfBereit || !dirty.value) return
  entwurfApi().speichern(definition.value, { titel: definition.value.name || definition.value.id || '' })
}
function entwurfSichernVerzoegert() {
  if (!entwurfBereit) return
  clearTimeout(entwurfTimer)
  entwurfTimer = setTimeout(entwurfSichern, 400)
}
function entwurfVerwerfen() {
  entwurfApi().entfernen()
  entwurfFrage.value = false
}
function entwurfFortsetzen() {
  const i = entwurfApi().laden()
  entwurfFrage.value = false
  if (!i) return
  definition.value = i
  for (const key of ['anlaesse', 'regeln', 'ansichten']) {
    if (!Array.isArray(definition.value[key])) definition.value[key] = []
  }
  jsonFehler.value = ''
  entwurfBereit = true
}

// Der Entwurf folgt jeder Definitionsänderung (auch JSON/Formularfelder).
watch(signatur, entwurfSichernVerzoegert)

function vorDemVerlassen(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', vorDemVerlassen))
onUnmounted(() => {
  guardEntfernen()
  ++ladeNummer
  ++pruefNummer
  clearTimeout(pruefTimer)
  clearTimeout(entwurfTimer)
  window.removeEventListener('beforeunload', vorDemVerlassen)
})

// ── Speichern ──────────────────────────────────────────────────────────────

const speichernOffen = ref(false)
const speichert = ref(false)
const speichernFehler = ref([])
// OP-UI-5/UXD-R22: der Knopf bleibt aktiv; der Klick benennt das fehlende Feld.
const speichernFeldFehler = ref({ gueltigAb: '', kommentar: '' })
const gueltigAb = ref('')
const kommentar = ref('')
// UXP-R12: Zahl der Termine/Pläne, die eine neue Version ab dem Stichtag umbindet.
const auswirkung = ref(null)

const speichernPflichtenOk = computed(() => !jsonFehler.value && !!gueltigAb.value && !!kommentar.value.trim()
  // UXP-R5: kollidierende Kennung aus dem Anlege-Weg braucht die Bestätigung.
  && !(istNeu.value && vorhandeneKennung.value && !kollisionBestaetigt.value))

/** UXP-R12: Auswirkung der Version ab dem gewählten Stichtag vorab laden. */
async function auswirkungLaden() {
  auswirkung.value = null
  if (!gueltigAb.value || !definition.value.id) return
  try {
    auswirkung.value = await plantypAuswirkung(definition.value.id, gueltigAb.value)
  } catch { auswirkung.value = null }
}

watch(speichernOffen, (offen) => { if (offen) auswirkungLaden() })
watch(gueltigAb, () => { if (speichernOffen.value) auswirkungLaden() })

async function speichern() {
  if (speichert.value) return
  if (jsonFehler.value) {
    speichernFeldFehler.value = { gueltigAb: '', kommentar: '' }
    speichernFehler.value = [{ stufe: 'fehler', meldung: 'Das JSON ist ungültig. Bitte vor dem Speichern korrigieren.', hinweis: 'Der eingegebene Text bleibt erhalten; die letzte lesbare Definition wird nicht gespeichert.' }]
    return
  }
  // OP-UI-5/UXD-R22: Pflichtfelder am Feld benennen statt grauem Knopf.
  const feldFehler = { gueltigAb: '', kommentar: '' }
  if (!gueltigAb.value) feldFehler.gueltigAb = 'Bitte einen Stichtag angeben.'
  if (!kommentar.value.trim()) feldFehler.kommentar = 'Bitte kurz beschreiben, was sich geändert hat.'
  if (istNeu.value && vorhandeneKennung.value && !kollisionBestaetigt.value) {
    speichernFeldFehler.value = feldFehler
    speichernFehler.value = [{ stufe: 'warnung', meldung: `Die Kennung „${definition.value.id}“ gibt es schon.`, hinweis: 'Bitte die bestehende Kollision unten prüfen und die neue Version anhaken, dann erneut speichern.' }]
    return
  }
  speichernFeldFehler.value = feldFehler
  if (feldFehler.gueltigAb || feldFehler.kommentar) {
    requestAnimationFrame(() => document.querySelector('.pr-pe-speichern .dk-form-input, .pr-pe-speichern .dk-form-textarea')?.focus())
    return
  }
  if (speichert.value) return
  speichert.value = true
  speichernFehler.value = []
  try {
    const roh = JSON.parse(JSON.stringify(definition.value))
    // UXP-R5: Aus dem Anlege-Weg „neue Planvorlage“ darf eine vorhandene
    // Kennung nicht still überschreiben. Nur hier wird `false` gesendet; der
    // reguläre Weg über eine bestehende Vorlage bestätigt sie ausdrücklich.
    const erlauben = !(istNeu.value && vorhandeneKennung.value && !kollisionBestaetigt.value)
    const erg = await plantypSpeichern(roh, gueltigAb.value, kommentar.value.trim(), erlauben)
    grundstand.value = JSON.stringify(roh)
    // Die Kennung ist jetzt belegt — künftige Speichervorgänge sind Versionspflege.
    bekannteKennungen.value.set(definition.value.id, definition.value.name || definition.value.id)
    kollisionBestaetigt.value = false
    // Erfolgreich gespeichert → der Entwurf hat sich erledigt.
    entwurfApi().entfernen()
    entwurfFrage.value = false
    speichernOffen.value = false
    gueltigAb.value = ''
    kommentar.value = ''
    gespeicherteTypId.value = definition.value.id
    showToast('Neue Version gespeichert.')
    emit('gespeichert', { plantyp: definition.value.id, version: erg })
    // Versionenliste nachziehen (bleibt auf der Seite — weitere Folgeversionen sind möglich).
    if (definition.value.id) {
      try {
        const liste = await plantypVersionenListe(definition.value.id)
        versionen.value = Array.isArray(liste) ? liste : []
        aktuelleVersion.value = versionen.value.at(-1) || null
      } catch { /* Liste ist Beiwerk — Speichern ist bereits bestätigt */ }
    }
    try {
      // Das Speichern ist bereits bestätigt — ein nachgelagerter Bedarfsfehler
      // darf den Dialog nicht als Fehlschlag erscheinen lassen (wie die Liste).
      bedarfListe.value = await bedarf(roh.id)
      bedarfOffen.value = bedarfListe.value.some(e => e.einstufung !== 'ok')
    } catch { /* Bedarf ist Beiwerk — Speichern bleibt bestätigt */ }
  } catch (err) {
    speichernFehler.value = fehlerMeldungen(err)
  } finally {
    speichert.value = false
  }
}

defineExpose({ gespeicherteTypId, definition })
const bedarfOffen = ref(false)
const bedarfListe = ref([])
// ST1: Stammdaten im Seitenpanel statt Weg-Navigieren (Entwurf bleibt erhalten).
const stammdatenPanelOffen = ref(false)
function stammdatenOeffnen() {
  if (!definition.value.id) return
  stammdatenPanelOffen.value = true
}
async function stammdatenPanelGeschlossen() {
  // Bedarf nach dem Pflegen neu prüfen, damit die Anzeige nicht veraltet.
  try {
    if (definition.value.id) bedarfListe.value = await bedarf(definition.value.id)
  } catch { /* Bedarf ist Beiwerk */ }
}
</script>

<style scoped>
.pr-pe-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: 0.9rem; }
.pr-pe-zustand--fehler { color: var(--dk-danger); }
.pr-pe-tabs { margin-bottom: 12px; }
.pr-pe-meta { font-size: 0.78rem; color: var(--dk-text-muted); }
.pr-pe-pruefstatus { font-size: 0.82rem; color: var(--dk-text-muted); padding: 6px 0; }
.pr-pe-pruefstatus--ok { color: var(--ok); }
.pr-pe-form { display: flex; flex-direction: column; gap: 26px; }
.pr-pe-abschnitt { display: flex; flex-direction: column; gap: 10px; }
.pr-pe-titel {
  font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--dk-text-muted); margin: 0; border-bottom: 1px solid var(--dk-divider); padding-bottom: 6px;
}
.pr-pe-hinweis { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0; line-height: 1.5; }
.pr-pe-hinweis--warnung {
  border: 1px solid color-mix(in oklch, var(--dk-warning) 45%, var(--dk-border));
  border-radius: 10px; padding: 10px 12px;
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
}
.pr-pe-hinweis-text { margin: 0 0 6px; font-size: 0.82rem; color: var(--dk-text); }
.pr-pe-unbekannte-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.pr-pe-unbekannte-liste li { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.pr-pe-unbekannte-kennung { font-family: ui-monospace, monospace; font-size: 0.82rem; color: var(--dk-text); }
.pr-pe-hilfe--warnung { color: var(--dk-warning); }
.pr-pe-kollision {
  display: flex; flex-direction: column; gap: 8px; padding: 12px;
  border: 1px solid color-mix(in oklch, var(--dk-warning) 45%, var(--dk-border));
  border-radius: 10px;
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
}
.pr-pe-kollision-text { margin: 0; font-size: 0.86rem; color: var(--dk-text); }
.pr-pe-checkbox { display: inline-flex; align-items: center; gap: 6px; font-size: 0.84rem; color: var(--dk-text); }
.pr-pe-leer { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0; }
.pr-pe-zeile { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.pr-pe-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); min-width: 0; }
.pr-pe-kurz { max-width: 220px; font-family: ui-monospace, monospace; }
.pr-pe-unter-titel { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 6px 0 0; }
.pr-pe-chips { display: flex; flex-wrap: wrap; gap: 6px 12px; }
.pr-pe-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; font-family: ui-monospace, monospace; }
.pr-pe-anlass { border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface); padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.pr-pe-versionen { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.pr-pe-version { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; padding: 8px 10px; border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); }
.pr-pe-version-haupt { font-size: 0.86rem; color: var(--dk-text); font-weight: 500; }
.pr-pe-version-neben { display: inline-flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.pr-pe-version-kommentar { font-size: 0.78rem; color: var(--dk-text-muted); }
.pr-pe-json { display: flex; flex-direction: column; gap: 8px; }
.pr-pe-jsonfeld { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; line-height: 1.45; }
.pr-pe-speichern { display: flex; flex-direction: column; gap: 12px; }
/* OP-UI-23: unsichtbarer Absende-Knopf, damit Enter im Feld absendet. */
.pr-pe-sr-submit {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.pr-pe-entwurf {
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px; margin-bottom: 12px;
  border: 1px solid color-mix(in oklch, var(--dk-warning) 45%, var(--dk-border));
  border-radius: 10px;
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
}
.pr-pe-entwurf-text { margin: 0; font-size: 0.86rem; color: var(--dk-text); }
.pr-pe-entwurf-aktionen { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 640px) {
  .pr-pe-kurz { max-width: none; width: 100%; }
}
</style>
