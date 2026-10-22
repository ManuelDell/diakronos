<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">
    <div class="dk-crumbs">
      <a class="dk-crumb" href="#/planrahmen">Pläne</a>
      <span class="dk-crumb-sep" aria-hidden="true">/</span>
      <span class="dk-crumb-current">{{ plan?.titel || 'Plan' }}</span>
    </div>

    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">{{ plan?.titel || 'Plan' }}</h1>
        <p class="dk-screen-sub">
          <span v-if="zeitraumText" class="pr-plan-zeitraum">{{ zeitraumText }}</span>
          <span :class="statusBadgeKlasse(plan?.status)">
            {{ statusSprache(plan?.status).wort }}
          </span>
          <!-- OP-HANDY-6: „geändert am“-Marker (Konzept B10) — wann wurde
               dieser Stand zuletzt gespeichert/veröffentlicht. -->
          <span v-if="geaendertText" class="pr-plan-stand">Zuletzt gespeichert: {{ geaendertText }}</span>
        </p>
      </div>
      <div v-if="darfBearbeiten" class="dk-screen-actions">
        <template v-if="istArchiviert">
          <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" data-test="pr-plan-archiv-holen"
                  :disabled="beschaeftigt" @click="archivUmschalten(false)">Aus dem Archiv holen</button>
        </template>
        <template v-else>
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" data-test="pr-plan-stammdaten" @click="stammdatenPanelOeffnen">Stammdaten vorbereiten</button>
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" :disabled="beschaeftigt || laden" @click="neuLaden">
            <span v-if="laden" class="dk-spinner" aria-hidden="true"></span>{{ laden ? 'Wird geladen …' : 'Neu laden' }}
          </button>
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" :disabled="beschaeftigt"
                  :title="undoZiel?.moeglich ? ('Zurücknehmen: ' + undoZiel.beschreibung) : 'Nichts zurückzunehmen'"
                  @click="rueckgaengig">Rückgängig</button>
          <button
            type="button"
            class="dk-btn dk-btn-secondary dk-btn-sm"
            :disabled="beschaeftigt || generatorLaeuft"
            :title="'Nur leere Plätze und Regelverstöße beheben — bestehende Vorschläge bleiben stehen'"
            @click="generatorOeffnen(true)"
          >
            <span v-if="generatorLaeuft && generatorNurLuecken" class="dk-spinner" aria-hidden="true"></span>Lücken füllen
          </button>
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" :disabled="beschaeftigt || generatorLaeuft" @click="generatorOeffnen(false)">
            <span v-if="generatorLaeuft && !generatorNurLuecken" class="dk-spinner" aria-hidden="true"></span>{{ generatorLaeuft && !generatorNurLuecken ? 'Wird berechnet …' : 'Automatisch einteilen' }}
          </button>
          <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="beschaeftigt" @click="veroeffentlichungOeffnen">
            <span v-if="beschaeftigt && veroeffentlichLaeuft" class="dk-spinner" aria-hidden="true"></span>Veröffentlichen
          </button>
        </template>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" data-test="pr-plan-kopieren"
                :disabled="beschaeftigt" @click="kopieDialogOeffnen">Kopieren</button>
        <button v-if="!istArchiviert" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" data-test="pr-plan-archivieren"
                :disabled="beschaeftigt" @click="archivUmschalten(true)">Archivieren</button>
        <button v-if="istLoeschbar" type="button" class="dk-btn dk-btn-ghost dk-btn-sm pr-plan-gefahr"
                data-test="pr-plan-loeschen" :disabled="beschaeftigt" @click="loeschenDialogOffen = true">Löschen</button>
      </div>
    </div>

    <!-- P1-14b: Ein archivierter Plan ist schreibgeschützt; der Weg zurück ist
         ausdrücklich („Aus dem Archiv holen“), nicht eine stille Änderung. -->
    <div v-if="istArchiviert" class="pr-plan-archiv" data-test="pr-plan-archiv-hinweis">
      <strong>Dieser Plan ist archiviert.</strong>
      Er ist für Mitglieder nicht mehr sichtbar. Hol ihn mit „Aus dem Archiv holen“ zurück, bevor du ihn änderst.
    </div>


    <div v-if="laden" class="pr-plan-zustand">Lade Plan …</div>

    <div v-else-if="seitenFehler.length" class="pr-plan-zustand pr-plan-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen">Zurück zur Übersicht</a>
    </div>

    <template v-else>
      <div v-if="meldungenSeite.length" class="pr-plan-meldungen">
        <PrMeldungen :meldungen="meldungenSeite" zusammenfassung titel="Prüfung der letzten Aktion" />
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Meldungen ausblenden" @click="meldungenSeite = []">Ausblenden</button>
      </div>

      <PrErststart v-if="darfBearbeiten" :bedarf="bedarfListe" :definition="erstdefinition || {}" :stammdaten="'#/planrahmen/vorbereiten/' + encodeURIComponent(planId)" panel angelegt :veroeffentlicht="plan?.status === 'veroeffentlicht'" @stammdaten-oeffnen="stammdatenPanelOeffnen" />
      <!-- UXP-R19: Die Regelprüfung ist internes Planerwissen („0 Fehler ·
           39 Warnungen"). Mitglieder lesen nur den veröffentlichten Stand und
           duerfen die Prüfung nicht sehen. -->
      <PrMeldungen v-if="darfBearbeiten" :meldungen="terminMeldungen(eintraege)" zusammenfassung titel="Regelprüfung des aktuellen Plans" />
      <PrLegende />

      <!-- Ansichtenwahl + Terminwahl für Ablauf-/Programmansichten -->
      <div v-if="ansichten.length > 1 || brauchtTermin" class="pr-plan-leiste">
        <div v-if="ansichten.length > 1" class="dk-tab-list" role="tablist" aria-label="Ansicht des Plans wählen">
          <button
            v-for="(a, i) in ansichten"
            :key="i"
            type="button"
            role="tab"
            class="dk-tab"
            :class="{ 'is-active': i === aktiveAnsichtIndex }"
            :aria-selected="i === aktiveAnsichtIndex ? 'true' : 'false'"
            @click="ansichtWaehlen(i)"
          >{{ a.name || artName(a.art) }}</button>
        </div>
        <label v-if="brauchtTermin" class="pr-plan-terminwahl">
          <span class="pr-plan-terminwahl-label">Termin</span>
          <select v-model="terminIdWahl" class="dk-form-select" aria-label="Termin für diese Ansicht wählen">
            <option v-for="t in termine" :key="t.id" :value="t.id">
              {{ datumText(t.datum) }}{{ t.titel ? ' — ' + t.titel : '' }}
            </option>
          </select>
        </label>
      </div>

      <PrAnsicht
        :key="ladeSchluessel"
        :plan="planFuerAnsicht"
        :termine="termine"
        :eintraege="eintraege"
        :definitionen="definitionen"
        :ansicht="aktuelleAnsicht"
        :termin="aktiverTermin"
        :bearbeitbar="darfBearbeiten"
        druck-knopf
        @bearbeiten="editorOeffnen"
        @operationen="operationenAnwenden"
        @variante="varianteSetzen"
        @navigation="geheZu"
      />
    </template>

    <!-- Generator: Vorschau, dann Übernahme -->
    <DkModal variant="planrahmen" v-model="generatorOffen" title="Automatisch einteilen — Vorschau" footer-sticky>
      <p class="pr-plan-modaltext">
        Das Programm schlägt eine neue Einteilung vor. Werte, die von Hand festgelegt sind (📌), bleiben erhalten.
      </p>
      <PrMeldungen v-if="generatorMeldungen.length" :meldungen="generatorMeldungen" zusammenfassung />
      <PrDiff vorschlag :diff="generatorDiff" :termine="termine" :definitionen="definitionen" :anzeige="diffAnzeige" />
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="generatorOffen = false">Abbrechen</button>
        <button type="button" class="dk-btn dk-btn-primary" :disabled="beschaeftigt" @click="generatorAnwenden">
          {{ beschaeftigt ? 'Wird angewendet …' : 'Übernehmen' }}
        </button>
      </template>
    </DkModal>

    <!-- Veröffentlichung: Vorschau des Wert-Diffs, dann Veröffentlichung.
         Der Titel grenzt sich klar vom Vorschlag-Generator ab (UX C4). -->
    <DkModal variant="planrahmen" v-model="veroeffentlichOffen" title="Plan veröffentlichen — das sehen danach alle Mitglieder" footer-sticky>
      <p class="pr-plan-modaltext">
        Nach der Veröffentlichung sehen alle Mitglieder diesen Stand. Diese Wertänderungen gehen damit öffentlich:
      </p>
      <PrDiff v-if="veroeffentlichDiff.length" :diff="veroeffentlichDiff" :termine="termine" :definitionen="definitionen" :anzeige="diffAnzeige" />
      <p v-else-if="plan?.veroeffentlichter_stand == null" class="pr-plan-modaltext">Dieser Plan wird zum ersten Mal sichtbar. Es sind noch keine Aufgaben eingeteilt.</p>
      <p v-else class="pr-plan-modaltext">Es gibt keine Wertänderungen gegenüber dem letzten veröffentlichten Stand.</p>
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="veroeffentlichOffen = false">Abbrechen</button>
        <button type="button" class="dk-btn dk-btn-primary" :disabled="beschaeftigt" @click="veroeffentlichenDurchfuehren">
          {{ beschaeftigt ? 'Wird veröffentlicht …' : 'Jetzt veröffentlichen' }}
        </button>
      </template>
    </DkModal>

    <!-- Einzelwert-Bearbeitung -->
    <PrEditor
      v-model="editorOffen"
      :plan="planId"
      :termin="editorZiel?.termin || null"
      :feld-pfad="editorZiel?.feldPfad || ''"
      :slots="editorSlots"
      :definition="definitionen.get(editorZiel?.termin?.plantyp_version) || {}"
      :eintraege="eintraege"
      @gespeichert="editorGespeichert"
      @geloest="editorGeloest"
      @platz-hinzugefuegt="editorPlatzHinzugefuegt"
    />

    <!-- ST1: Stammdaten im Seitenpanel statt Seitenwechsel. -->
    <PrStammdatenPanel
      v-model="stammdatenPanelOffen"
      :plan="planId"
      titel="Stammdaten vorbereiten"
      untertitel="Personen und Listen ergänzen — dann zurück zum Plan."
      @geschlossen="stammdatenPanelGeschlossen"
    />

    <!-- P1-14b: Bestätigung vor dem unwiderruflichen Löschen. Der Server
         verlangt zusätzlich bestaetigt=true (nicht umgehbar). -->
    <DkDialog v-model="loeschenDialogOffen" title="Plan endgültig löschen?" size="sm" :close-on-overlay="false">
      <p class="pr-plan-modaltext">
        „{{ plan?.titel }}“ und alle zugehörigen Termine werden dauerhaft entfernt.
        Das lässt sich nicht rückgängig machen. Alternativ kannst du den Plan archivieren.
      </p>
      <PrMeldungen v-if="loeschenFehler.length" :meldungen="loeschenFehler" />
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="loeschenDialogOffen = false">Abbrechen</button>
        <button type="button" class="dk-btn dk-btn-secondary" :disabled="beschaeftigt" @click="archivUmschalten(true)">
          Stattdessen archivieren
        </button>
        <button type="button" class="dk-btn dk-btn-primary pr-plan-gefahr" :disabled="beschaeftigt"
                data-test="pr-plan-loeschen-bestaetigen" @click="loeschenDurchfuehren">
          {{ beschaeftigt ? 'Wird gelöscht …' : 'Endgültig löschen' }}
        </button>
      </template>
    </DkDialog>

    <!-- P1-14b: Kopie anlegen (neuer Entwurf). -->
    <DkDialog v-model="kopieDialogOffen" title="Plan kopieren" size="sm" :close-on-overlay="false">
      <div class="dk-form-group">
        <label for="pr-plan-kopie-titel">Titel der Kopie</label>
        <input id="pr-plan-kopie-titel" v-model="kopieTitel" type="text" class="dk-form-input"
               placeholder="z. B. Chorplan 2027" />
      </div>
      <PrMeldungen v-if="kopieFehler.length" :meldungen="kopieFehler" />
      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="kopieDialogOffen = false">Abbrechen</button>
        <button type="button" class="dk-btn dk-btn-primary" :disabled="beschaeftigt || !kopieTitel.trim()"
                data-test="pr-plan-kopie-speichern" @click="kopieDurchfuehren">
          {{ beschaeftigt ? 'Wird kopiert …' : 'Kopie anlegen' }}
        </button>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * Planansicht des Plan-Rahmens: lädt plan_holen (Entwurf für Planer,
 * veröffentlichter Stand für Mitglieder), dazu je Termin die fixierte
 * Versionsdefinition und die Einzelplätze aus termin_struktur.
 *
 * Die Darstellung kommt vollständig aus der deklarierten Definition
 * (PrAnsicht mit Tabelle/Raster/Kalender/Ablauf/Programm/Druck/iCal).
 * Bearbeitung nur für berechtigte Planer: Einzelwerte über PrEditor
 * (feld_kandidaten + eintrag_setzen/eintrag_loesen), Ablauf über die
 * Operationen der PrAblauf-Komponente, Generator und Veröffentlichung
 * jeweils mit Vorschau vor dem Schreibaufruf.
 */
import { ref, computed, watch, onUnmounted, provide, nextTick } from 'vue'
import { getRouteParam } from '../../router.js'
import { usePlanrahmen, datumText, fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { showToast } from '../../composables/useToast.js'
import DkModal from '../../components/DkModal.vue'
import DkDialog from '../../components/ui/DkDialog.vue'
import PrAnsicht from '../../components/planrahmen/PrAnsicht.vue'
import PrDiff from '../../components/planrahmen/PrDiff.vue'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import PrErststart from '../../components/planrahmen/PrErststart.vue'
import PrEditor from '../../components/planrahmen/PrEditor.vue'
import PrLegende from '../../components/planrahmen/PrLegende.vue'
import PrStammdatenPanel from '../../components/planrahmen/PrStammdatenPanel.vue'
import { terminMeldungen } from '../../components/planrahmen/meldungen.mjs'
import { diffAnzeigeLaden, kandidatenZiel } from '../../components/planrahmen/klartext.mjs'
import { statusSprache, statusBadgeKlasse } from '../../components/ui/statussprache.mjs'

const { planHolen, planStandVersion, terminStruktur, terminStrukturen, planGenerieren, planEntwurf, undoPlan, undoVorschau, veroeffentlichen, ablaufAendern, feldKandidaten, terminAendern, bedarf,
        planArchivieren, planLoeschen, planKopieren } = usePlanrahmen()

const planId = computed(() => getRouteParam('id', 'PlanrahmenPlan') || '')

const laden = ref(true)
const seitenFehler = ref([])
const bedarfListe = ref([])
const meldungenSeite = ref([])
const planDaten = ref(null)
const cacheVersion = ref('')            // PF1: Versionsstempel des Browser-Caches
const definitionen = ref(new Map())      // plantyp_version → definition
const slotsProTermin = ref(new Map())    // termin-id → slots (nur Planer)
const ladeSchluessel = ref(0)
const beschaeftigt = ref(false)

const aktiveAnsichtIndex = ref(0)
const terminIdWahl = ref('')

const editorOffen = ref(false)
const editorZiel = ref(null)

const generatorOffen = ref(false)
const generatorDiff = ref([])
const generatorMeldungen = ref([])
// UXP-R11: eigener Zustand fuer die Berechnung des Vorschlags. Der Knopf
// zeigt damit „Wird berechnet …“ samt Spinner (die Berechnung dauerte bei
// einem Chorplan mit 56 Terminen 21–28 s) und ist nicht nur grau.
const generatorLaeuft = ref(false)
// UXP-R16: Modus „nur Lücken und Regelverstöße beheben" (Vorgabe des letzten Laufs).
const generatorNurLuecken = ref(false)
// Laueft gerade die Veroeffentlichungs-Vorbereitung/-Durchfuehrung? Dann zeigt
// der Knopf „Veröffentlichen“ einen Spinner (Befund K3).
const veroeffentlichLaeuft = ref(false)

const veroeffentlichOffen = ref(false)
const veroeffentlichDiff = ref([])
const diffAnzeige = ref({})

// ST1: Stammdaten im Seitenpanel; ein offener Generator-Vorschlag überlebt das Panel.
const stammdatenPanelOffen = ref(false)
const generatorWarOffen = ref(false)
provide('planrahmenAnzeige', computed(() => ({
    definitionen: definitionen.value, termine: termine.value,
    anzeige: { ...(planDaten.value?.anzeige || {}), ...diffAnzeige.value },
})))

// ── Plan-Daten ─────────────────────────────────────────────────────────────

const plan = computed(() => planDaten.value?.plan || null)
const termine = computed(() => planDaten.value?.termine || [])
const eintraege = computed(() => planDaten.value?.eintraege || [])
const darfBearbeiten = computed(() => !!(planDaten.value?.darf_bearbeiten ?? planDaten.value?.bearbeiten))
// P1-14b: Ein archivierter Plan ist schreibgeschützt (Server lehnt jede
// Änderung ab). Die Oberfläche blendet nur aus, was der Server ohnehin
// verweigert — und bietet den ausdrücklichen Weg zurück an.
const istArchiviert = computed(() => plan.value?.status === 'archiviert')
// Nur ein Entwurf ohne veröffentlichten Stand lässt sich endgültig löschen
// (veröffentlichte Pläne werden archiviert) — genau wie der Server prüft.
const istLoeschbar = computed(() => !!plan.value && !istArchiviert.value &&
    plan.value.status === 'entwurf' && plan.value.veroeffentlichter_stand == null)

const loeschenDialogOffen = ref(false)
const loeschenFehler = ref([])
const kopieDialogOffen = ref(false)
const kopieTitel = ref('')
const kopieFehler = ref([])

const zeitraumText = computed(() => {
    if (!plan.value?.zeitraum_von && !plan.value?.zeitraum_bis) return ''
    return `${datumText(plan.value.zeitraum_von, false)} – ${datumText(plan.value.zeitraum_bis, false)}`
})

/** OP-HANDY-6: „geändert am“-Marker aus `plan.modified` (Konzept B10). */
const geaendertText = computed(() => {
    const iso = plan.value?.modified
    if (!iso) return ''
    const d = new Date(String(iso).replace(' ', 'T'))
    if (Number.isNaN(d.getTime())) return ''
    return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
})

const erstdefinition = computed(() => {
    for (const d of definitionen.value.values()) if (d) return d
    return null
})

const ansichten = computed(() => {
    const liste = Array.isArray(erstdefinition.value?.ansichten) ? erstdefinition.value.ansichten : []
    return liste.length ? liste : [{ art: 'tabelle', name: 'Tabelle' }]
})

const aktuelleAnsicht = computed(() => ansichten.value[aktiveAnsichtIndex.value] || ansichten.value[0])
const brauchtTermin = computed(() => ['ablauf', 'programm'].includes(aktuelleAnsicht.value?.art))

const aktiverTermin = computed(() =>
    termine.value.find((t) => t.id === terminIdWahl.value) || termine.value[0] || null)

/** Plankopf mit den Ansichten der Definition (für Druck-Rückfall). */
const planFuerAnsicht = computed(() => ({ ...(plan.value || {}), ansichten: ansichten.value }))

const editorSlots = computed(() =>
    (editorZiel.value && slotsProTermin.value.get(editorZiel.value.termin?.id)) || [])

async function diffNamenLaden(diff, id) {
    return diffAnzeigeLaden(diff, termine.value, definitionen.value, planDaten.value?.anzeige || {},
        (termin, pfad) => {
            const ziel = kandidatenZiel(termin, pfad, termine.value, definitionen.value, slotsProTermin.value)
            return ziel ? feldKandidaten(id, ziel.termin, ziel.pfad) : { kandidaten: [] }
        })
}

// ── Laden ──────────────────────────────────────────────────────────────────

let ladeNummer = 0
async function neuLaden() {
    const nummer = ++ladeNummer
    const id = planId.value
    if (!id) return
    // PF1: Zuerst den zuletzt gesehenen Stand aus dem Browser zeigen (sofort
    // bedienbar), dann im Hintergrund pruefen. Nur bei echter Aenderung wird
    // getauscht — stale-while-revalidate, nie veraltete Anzeige bei Schreiben.
    laden.value = true
    seitenFehler.value = []
    const hatteCache = planDaten.value != null
    try {
        diffAnzeige.value = {}
        // Versionsstempel: unveraendert -> der Cache-Stand bleibt stehen.
        let versionPruefen
        if (hatteCache) {
            const vorher = cacheVersion.value
            versionPruefen = async () => {
                if (!vorher) return false
                try {
                    const stempel = await planStandVersion(id)
                    return stempel?.version === vorher && stempel?.darf_bearbeiten === darfBearbeiten.value
                } catch {
                    return false   // im Zweifel frisch laden (nie falsch stehen)
                }
            }
        }
        const daten = await planHolen(id, {
            onCache: (zwischen) => {
                // Sofortiger Zwischenstand nur, wenn wir noch nichts zeigen.
                if (!planDaten.value) planDaten.value = zwischen
            },
            versionPruefen,
        })
        if (nummer !== ladeNummer) return
        planDaten.value = daten
        cacheVersion.value = daten?.stand_version || cacheVersion.value
        await versionMerken(id)
        bedarfListe.value = []
        if (darfBearbeiten.value && daten?.plan?.plantyp) {
            const luecken = await bedarf(daten.plan.plantyp, id)
            if (nummer !== ladeNummer) return
            bedarfListe.value = Array.isArray(luecken) ? luecken : []
        }
        await strukturenLaden(id, nummer)
        if (nummer !== ladeNummer) return
        // UXP-R20: Beschriftung des Rückgängig-Knopfes aktuell halten.
        await undoZielLaden()
        if (nummer !== ladeNummer) return
        if (aktiveAnsichtIndex.value >= ansichten.value.length) aktiveAnsichtIndex.value = 0
        if (!termine.value.some((t) => t.id === terminIdWahl.value)) {
            terminIdWahl.value = termine.value[0]?.id || ''
        }
    } catch (err) {
        if (nummer !== ladeNummer) return
        planDaten.value = null
        seitenFehler.value = fehlerMeldungen(err)
    } finally {
        if (nummer === ladeNummer) {
            laden.value = false
            ladeSchluessel.value += 1
        }
    }
}

/** Aktuellen Versionsstempel des Plans merken (Grundlage des Versionsvergleichs). */
async function versionMerken(id) {
    try {
        const stempel = await planStandVersion(id)
        cacheVersion.value = stempel?.version || ''
    } catch {
        cacheVersion.value = ''
    }
}

/**
 * Versionsdefinitionen und Einzelplätze je Termin. Planer erhalten zusätzlich
 * die Slots (Basis für Kandidaten und Bearbeitung); Mitglieder brauchen nur
 * die fixierte Versionsdefinition pro Termin-Version.
 */
async function strukturenLaden(id, nummer) {
    const neu = new Map()
    const definitionenNeu = new Map()
    const liste = termine.value || []
    // PF1: EIN Aufruf statt je Termin einer (vorher 56 HTTP-Runden, jede lud
    // den kompletten Plan-Kontext neu). Der Server liefert je Termin dieselbe
    // Form wie termin_struktur; wir verteilen nur noch auf die Maps.
    let strukturen = null
    try {
        const ergebnis = await terminStrukturen(id)
        strukturen = Array.isArray(ergebnis?.strukturen) ? ergebnis.strukturen : null
    } catch {
        strukturen = null   // z.B. Server ohne den Endpunkt -> Einzelweg unten
    }
    if (nummer !== ladeNummer) return
    if (strukturen) {
        for (const eintrag of strukturen) {
            const t = eintrag?.termin
            if (!t) continue
            if (darfBearbeiten.value) {
                neu.set(t.id, Array.isArray(eintrag?.slots) ? eintrag.slots : [])
            }
            const definition = eintrag?.version?.definition || null
            if (definition && !definitionenNeu.has(t.plantyp_version)) {
                definitionenNeu.set(t.plantyp_version, definition)
            }
        }
    } else if (!darfBearbeiten.value) {
        // Lesemodus-Rueckfall: je Termin-Version einmal termin_struktur.
        const proVersion = new Map()
        for (const t of liste) if (!proVersion.has(t.plantyp_version)) proVersion.set(t.plantyp_version, t.id)
        for (const [versionId, terminId] of proVersion) {
            if (nummer !== ladeNummer) return
            const struktur = await terminStruktur(id, terminId)
            const definition = struktur?.version?.definition || null
            if (definition) definitionenNeu.set(versionId, definition)
        }
    } else {
        // Bearbeitungs-Rueckfall: pro Termin (Slots + fixierte Definition).
        const portionen = []
        for (let i = 0; i < liste.length; i += 8) portionen.push(liste.slice(i, i + 8))
        for (const portion of portionen) {
            if (nummer !== ladeNummer) return
            const ergebnisse = await Promise.all(
                portion.map((t) => terminStruktur(id, t.id)))
            portion.forEach((t, i) => {
                const struktur = ergebnisse[i]
                neu.set(t.id, Array.isArray(struktur?.slots) ? struktur.slots : [])
                const definition = struktur?.version?.definition || null
                if (definition && !definitionenNeu.has(t.plantyp_version)) {
                    definitionenNeu.set(t.plantyp_version, definition)
                }
            })
        }
    }
    if (nummer === ladeNummer) {
        slotsProTermin.value = neu
        definitionen.value = definitionenNeu
    }
}

watch(planId, () => {
    editorOffen.value = false
    generatorOffen.value = false
    veroeffentlichOffen.value = false
    meldungenSeite.value = []
    aktiveAnsichtIndex.value = 0
    neuLaden()
}, { immediate: true, flush: 'sync' })

onUnmounted(() => { ladeNummer += 1 })

watch(brauchtTermin, (braucht) => {
    if (braucht && !terminIdWahl.value) terminIdWahl.value = termine.value[0]?.id || ''
})

function ansichtWaehlen(index) {
    aktiveAnsichtIndex.value = index
}

const ART_NAMEN = {
    tabelle: 'Tabelle', raster: 'Raster', kalender: 'Kalender', ablauf: 'Ablauf',
    programm: 'Programm', druck: 'Druck', ical: 'Kalenderdatei', meine_dienste: 'Meine Dienste',
}
function artName(art) { return ART_NAMEN[art] || art || 'Ansicht' }

function geheZu(pfad) {
    if (typeof pfad === 'string' && pfad.startsWith('#')) window.location.hash = pfad
}

// ── Einzelwerte bearbeiten ─────────────────────────────────────────────────

function editorOeffnen(termin, feldPfad) {
    if (!darfBearbeiten.value) return
    if (!termin || !feldPfad) return
    editorZiel.value = { termin, feldPfad }
    editorOffen.value = true
}

function editorGespeichert(info) {
    meldungenSeite.value = info?.meldungen || []
    showToast('Änderung gespeichert.')
    neuLaden()
}

function editorGeloest() {
    showToast('Das Programm darf diesen Wert wieder vorschlagen.')
    neuLaden()
}

/** Neuer optionaler Platz: Struktur neu laden und den Platz direkt öffnen. */
async function editorPlatzHinzugefuegt(info) {
    const termin = editorZiel.value?.termin
    await neuLaden()
    if (!termin) return
    const aktualisiert = termine.value.find((t) => t.id === termin.id) || termin
    // Editor kurz schliessen, damit PrEditor den neuen Pfad frisch startet.
    editorOffen.value = false
    await nextTick()
    editorZiel.value = { termin: aktualisiert, feldPfad: info?.feld_pfad || editorZiel.value?.feldPfad }
    editorOffen.value = true
    showToast('Platz angelegt — jetzt besetzen.')
}

// ── Stammdaten im Seitenpanel (ST1) ────────────────────────────────────────

function stammdatenPanelOeffnen() {
    // Ein offener Generator-Vorschlag bleibt vorgemerkt (kein stiller Verlust).
    generatorWarOffen.value = generatorOffen.value
    if (generatorOffen.value) generatorOffen.value = false
    stammdatenPanelOffen.value = true
}

/**
 * Nach dem Schließen: Bedarf neu prüfen und — falls ein Vorschlag offen war —
 * die Vorschau wieder herstellen. Weil sich die Stammdaten geändert haben
 * können, wird der Vorschlag frisch erzeugt; das wird dem Planer gesagt
 * (keine stille Übernahme eines veralteten Vorschlags).
 */
async function stammdatenPanelGeschlossen() {
    await neuLaden()
    if (generatorWarOffen.value) {
        generatorWarOffen.value = false
        showToast('Stammdaten geändert — der Vorschlag wird neu erzeugt.')
        await generatorOeffnen()
    }
}

// ── Ablauf-Operationen ─────────────────────────────────────────────────────

async function operationenAnwenden(ops) {
    if (!darfBearbeiten.value || !Array.isArray(ops) || !ops.length) return
    beschaeftigt.value = true
    try {
        await ablaufAendern(planId.value, aktiverTermin.value?.id, ops)
        showToast(ops.length === 1 ? 'Ablauf geändert.' : `${ops.length} Ablaufänderungen gespeichert.`)
        await neuLaden()
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
        await neuLaden()
    } finally {
        beschaeftigt.value = false
    }
}

// ── Generator (Vorschau, dann Übernahme) ───────────────────────────────────

async function generatorOeffnen(nurLuecken = false) {
    beschaeftigt.value = true
    generatorLaeuft.value = true
    meldungenSeite.value = []
    try {
        const id = planId.value
        const nummer = ladeNummer
        // UXP-R16: Auf einem veroeffentlichten Plan oeffnet der Knopf den Plan
        // selbst als Entwurf (Mitglieder sehen den eingefrorenen Stand weiter) —
        // statt den Planer mit „Veröffentlichten Plan zuerst ... zum Entwurf
        // machen" auf eine Handänderung zu schicken.
        if (plan.value?.status === 'veroeffentlicht') {
            await planEntwurf(id)
            if (id !== planId.value || nummer !== ladeNummer) return
            showToast('Der Plan ist jetzt ein Entwurf. Änderungen sehen Mitglieder erst nach dem Veröffentlichen.')
        }
        generatorNurLuecken.value = Boolean(nurLuecken)
        const erg = await planGenerieren(id, true, 0, generatorNurLuecken.value)
        if (id !== planId.value || nummer !== ladeNummer) return
        const diff = Array.isArray(erg?.diff) ? erg.diff : []
        const anzeige = await diffNamenLaden(diff, id)
        if (id !== planId.value || nummer !== ladeNummer) return
        diffAnzeige.value = anzeige
        generatorDiff.value = diff
        generatorMeldungen.value = nachrichten([
            ...(Array.isArray(erg?.meldungen) ? erg.meldungen : []),
            ...(Array.isArray(erg?.verstoesse) ? erg.verstoesse : []),
        ])
        generatorOffen.value = true
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
        generatorLaeuft.value = false
    }
}

async function generatorAnwenden() {
    beschaeftigt.value = true
    try {
        // UXP-R16: Genau derselbe Modus wie in der Vorschau — sonst zeigt die
        // Vorschau „nur Lücken“, die Übernahme würfelt aber alles neu.
        const erg = await planGenerieren(planId.value, false, 0, generatorNurLuecken.value)
        const anzahl = Array.isArray(erg?.diff) ? erg.diff.length : 0
        generatorOffen.value = false
        meldungenSeite.value = nachrichten(
            Array.isArray(erg?.verstoesse) ? erg.verstoesse : [])
        showToast('Vorschlag übernommen. Bitte die Hinweise prüfen und anschließend veröffentlichen.')
        await neuLaden()
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

// ── Veröffentlichung (Vorschau, dann Veröffentlichung) ─────────────────────

function wertGleich(a, b) {
    if (a === b) return true
    try { return JSON.stringify(a) === JSON.stringify(b) } catch { return false }
}

/**
 * Wert-Diff zum letzten veröffentlichten Stand aus den Plan-Daten:
 * Planer erhalten in plan_holen den eingefrorenen Stand mitgeliefert.
 */
function veroeffentlichungsDiff() {
    const alt = new Map()
    for (const e of plan.value?.veroeffentlichter_stand?.eintraege || []) {
        alt.set(e.termin + '|' + e.feld_pfad, e.wert)
    }
    const neu = new Map()
    for (const e of eintraege.value) neu.set(e.termin + '|' + e.feld_pfad, e.wert)
    const schluessel = new Set([...alt.keys(), ...neu.keys()])
    const result = []
    for (const key of schluessel) {
        const a = alt.has(key) ? alt.get(key) : null
        const b = neu.has(key) ? neu.get(key) : null
        if (wertGleich(a, b)) continue
        const [termin, ...feld] = key.split('|')
        result.push({ termin, feld_pfad: feld.join('|'), vorher: a, nachher: b })
    }
    return result.sort((x, y) => (x.termin + x.feld_pfad).localeCompare(y.termin + y.feld_pfad))
}

async function veroeffentlichungOeffnen() {
    const id = planId.value
    const nummer = ladeNummer
    beschaeftigt.value = true
    veroeffentlichLaeuft.value = true
    try {
        const diff = veroeffentlichungsDiff()
        const anzeige = await diffNamenLaden(diff, id)
        if (id !== planId.value || nummer !== ladeNummer) return
        diffAnzeige.value = anzeige
        veroeffentlichDiff.value = diff
        veroeffentlichOffen.value = true
    } catch (err) {
        if (id === planId.value) meldungenSeite.value = fehlerMeldungen(err)
    } finally { beschaeftigt.value = false; veroeffentlichLaeuft.value = false }
}

async function veroeffentlichenDurchfuehren() {
    beschaeftigt.value = true
    try {
        const erg = await veroeffentlichen(planId.value)
        const anzahl = Array.isArray(erg?.diff) ? erg.diff.length : 0
        veroeffentlichOffen.value = false
        // BF1-B: Ehrlich melden, was passiert ist. Beim ERSTEN Veröffentlichen
        // gibt es keinen Vergleichsstand — die Meldung nennt das ausdruecklich,
        // statt „0 Änderungen öffentlich“ zu behaupten, obwohl der Plan
        // gerade sichtbar wurde.
        if (erg?.erstveroeffentlichung) {
            showToast(anzahl === 0
                ? 'Plan erstmals veröffentlicht. Er ist jetzt sichtbar; es sind noch keine Aufgaben eingeteilt.'
                : anzahl === 1
                    ? 'Plan erstmals veröffentlicht — 1 Wert ist jetzt für alle sichtbar.'
                    : `Plan erstmals veröffentlicht — ${anzahl} Werte sind jetzt für alle sichtbar.`)
        } else if (anzahl === 0) {
            showToast('Plan veröffentlicht — es gab keine Wertänderungen seit dem letzten Stand.')
        } else {
            showToast(anzahl === 1 ? 'Plan veröffentlicht — 1 Änderung öffentlich.' : `Plan veröffentlicht — ${anzahl} Änderungen öffentlich.`)
        }
        await neuLaden()
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

async function varianteSetzen(termin, variante) {
    if (!darfBearbeiten.value || !termin?.id) return
    beschaeftigt.value = true
    try {
        await terminAendern(planId.value, termin.id, { variante, variante_setzen: true })
        await neuLaden()
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

// ── Rückgängig ─────────────────────────────────────────────────────────────

// UXP-R20: der Knopf nennt in Klartext, WAS zurückgenommen würde. Die
// Veröffentlichung und der Versionswechsel sind ausgenommen (Server).
const undoZiel = ref(null)

async function undoZielLaden() {
    if (!darfBearbeiten.value || !planId.value) { undoZiel.value = null; return }
    try {
        undoZiel.value = await undoVorschau(planId.value)
    } catch { undoZiel.value = null }
}

async function rueckgaengig() {
    beschaeftigt.value = true
    try {
        const erg = await undoPlan(planId.value)
        const was = erg?.beschreibung ? ` (${erg.beschreibung})` : ''
        showToast(`Rückgängig gemacht${was}.`)
        await neuLaden()
    } catch (err) {
        meldungenSeite.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

// ── P1-14b: Archivieren, Löschen, Kopieren ─────────────────────────────────

/** Archivieren bzw. zurückholen; danach frisch laden (Status ist Server-Wahrheit). */
async function archivUmschalten(archivieren) {
    if (!plan.value || beschaeftigt.value) return
    beschaeftigt.value = true
    loeschenFehler.value = []
    try {
        await planArchivieren(planId.value, archivieren)
        loeschenDialogOffen.value = false
        showToast(archivieren
            ? 'Plan archiviert — Mitglieder sehen ihn nicht mehr.'
            : 'Plan aus dem Archiv geholt.')
        await neuLaden()
    } catch (err) {
        (loeschenDialogOffen.value ? loeschenFehler : meldungenSeite).value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

/** Endgültiges Löschen NUR mit Bestätigung — der Server verlangt bestaetigt=true. */
async function loeschenDurchfuehren() {
    if (!plan.value || beschaeftigt.value) return
    beschaeftigt.value = true
    loeschenFehler.value = []
    try {
        await planLoeschen(planId.value, true)
        loeschenDialogOffen.value = false
        showToast('Plan gelöscht.')
        window.location.hash = '#/planrahmen'
    } catch (err) {
        loeschenFehler.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

function kopieDialogOeffnen() {
    kopieTitel.value = plan.value?.titel ? plan.value.titel + ' (Kopie)' : ''
    kopieFehler.value = []
    kopieDialogOffen.value = true
}

async function kopieDurchfuehren() {
    if (!plan.value || beschaeftigt.value || !kopieTitel.value.trim()) return
    beschaeftigt.value = true
    kopieFehler.value = []
    try {
        const erg = await planKopieren(planId.value, kopieTitel.value.trim(), true)
        kopieDialogOffen.value = false
        showToast('Kopie angelegt.')
        if (erg?.plan) window.location.hash = '#/planrahmen/plan/' + encodeURIComponent(erg.plan)
    } catch (err) {
        kopieFehler.value = fehlerMeldungen(err)
    } finally {
        beschaeftigt.value = false
    }
}

// ── Meldungs-Hilfen ────────────────────────────────────────────────────────

function nachrichten(liste) {
    return (liste || []).map((m) => {
        const roh = typeof m === 'string' ? { meldung: m } : (m || {})
        return {
            ...roh,
            pfad: roh.pfad || roh.feld_pfad || '',
            code: roh.code || roh.baustein || '',
            meldung: roh.meldung || 'Unbekannte Meldung.',
            hinweis: roh.hinweis || '',
            stufe: roh.stufe === 'muss' ? 'fehler' : roh.stufe === 'sollte' ? 'warnung' : 'hinweis',
        }
    })
}
</script>

<style scoped>
.pr-plan-zeitraum { margin-right: 10px; }
.pr-plan-stand { margin-left: 10px; color: var(--dk-text-muted); font-size: 0.78rem; }
.pr-plan-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: 0.9rem; }
.pr-plan-zustand--fehler { color: var(--dk-danger); }
.pr-plan-meldungen { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 14px; }
.pr-plan-meldungen > *:first-child { flex: 1; min-width: 0; }
.pr-plan-leiste {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 14px;
}
.pr-plan-terminwahl { display: inline-flex; align-items: center; gap: 8px; }
.pr-plan-terminwahl-label { font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-plan-terminwahl .dk-form-select { width: auto; min-width: 220px; }
.pr-plan-modaltext { font-size: 0.86rem; color: var(--dk-text-muted); margin: 0 0 12px; }
.pr-plan-archiv {
  padding: 10px 14px; margin-bottom: 14px; border-radius: 10px;
  border: 1px solid color-mix(in oklch, var(--dk-warning) 45%, var(--dk-border));
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
  color: var(--dk-text); font-size: 0.88rem;
}
.pr-plan-gefahr { color: var(--dk-danger); }
</style>
