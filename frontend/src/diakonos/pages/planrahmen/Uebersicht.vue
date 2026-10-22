<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Pläne</h1>
        <p class="dk-screen-sub">Gemeinsam planen mit wiederverwendbaren Planvorlagen</p>
      </div>
      <div class="dk-screen-actions">
        <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen/meine-dienste">Meine Dienste</a>
        <a v-if="kannEinrichten" class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen/einrichten">Einrichten</a>
        <button v-if="hatArchiv" type="button" class="dk-btn dk-btn-secondary dk-btn-sm"
                data-test="pr-ue-archiv-filter" :aria-pressed="archivZeigen ? 'true' : 'false'"
                @click="archivZeigen = !archivZeigen">
          {{ archivZeigen ? 'Archiv ausblenden' : 'Archiv anzeigen' }}
        </button>
        <button v-if="kannAnlegen" type="button" class="dk-btn dk-btn-primary dk-btn-sm" @click="neuOffen = true">Neuer Plan</button>
      </div>
    </div>

    <div v-if="laden" class="pr-ue-zustand">Lade Pläne …</div>

    <div v-else-if="seitenFehler.length" class="pr-ue-zustand pr-ue-zustand--fehler">
      <PrMeldungen :meldungen="seitenFehler" />
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="ladenAlles">Nochmal</button>
    </div>

    <template v-else>
      <div v-if="!gruppen.length" class="dk-empty">
        <p class="dk-empty-title">Keine Pläne sichtbar</p>
        <p class="dk-empty-desc">
          <template v-if="kannAnlegen">Beginne mit „Neuer Plan“: Wähle eine Planvorlage, pflege die Fähigkeiten der Personen und lege den Zeitraum fest.</template>
          <template v-else-if="kannEinrichten">Richte zuerst eine Planvorlage unter „Einrichten“ ein. Bereichsverantwortliche können danach einen Plan erstellen.</template>
          <template v-else>Bereichsverantwortliche erstellen und veröffentlichen die Pläne. Für dich ist derzeit kein Plan freigegeben. Persönliche Dienste findest du unter „Meine Dienste“.</template>
        </p>
        <a class="dk-btn dk-btn-secondary dk-btn-sm" href="#/planrahmen/meine-dienste">Meine Dienste öffnen</a>
      </div>

      <section v-for="g in gruppen" :key="g.name" class="pr-ue-gruppe">
        <h2 class="pr-ue-gruppe-titel">{{ g.name }}</h2>
        <div class="dk-list">
          <a
            v-for="p in g.plaene"
            :key="p.id"
            class="dk-list-item pr-ue-zeile"
            :href="'#/planrahmen/plan/' + encodeURIComponent(p.id)"
          >
            <span class="pr-ue-haupt">
              <span class="pr-ue-titel">{{ p.titel }}</span>
              <span v-if="zeitraumVon(p)" class="pr-ue-meta">{{ zeitraumVon(p) }}</span>
            </span>
            <span class="pr-ue-neben">
              <span v-if="plantypName(p)" class="dk-badge dk-badge-brand">{{ plantypName(p) }}</span>
              <span :class="statusBadgeKlasse(p.status)">
                {{ statusSprache(p.status).wort }}
              </span>
            </span>
          </a>
        </div>
      </section>
    </template>

    <!-- Neuer Plan: generische Parameter aus der Planvorlage-Deklaration -->
    <DkModal variant="planrahmen" v-model="neuOffen" title="Neuer Plan">
      <!-- OP-UI-23: <form @submit.prevent> — Enter im Feld legt den Plan an
           (wie der Knopf). Der versteckte Absende-Knopf macht das Formular
           für Tastatur/Enter vollständig, ohne das Aussehen zu ändern. -->
      <form class="pr-ue-neu" @submit.prevent="planAnlegenDurchfuehren">
        <button type="submit" class="pr-ue-sr-submit" tabindex="-1" aria-hidden="true"></button>
        <p>* = Pflichtfeld</p>
        <!-- ST1: angefangener Entwurf — fortsetzen oder verwerfen. -->
        <div v-if="entwurfFrage" class="pr-ue-entwurf" data-test="pr-ue-entwurf-frage">
          <p class="pr-ue-entwurf-text">
            Du hast einen angefangenen Plan<template v-if="entwurfTitel"> „{{ entwurfTitel }}“</template> — fortsetzen oder verwerfen?
          </p>
          <div class="pr-ue-entwurf-aktionen">
            <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" data-test="pr-ue-entwurf-fortsetzen" @click="entwurfFortsetzen">Fortsetzen</button>
            <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" data-test="pr-ue-entwurf-verwerfen" @click="entwurfVerwerfen">Verwerfen</button>
          </div>
        </div>

        <div v-if="neuFehler.length" class="pr-ue-neu-block">
          <PrMeldungen :meldungen="neuFehler" />
        </div>

        <div class="dk-form-group">
          <label for="pr-ue-typ">Planvorlage *</label>
          <p v-if="feldFehler['pr-ue-typ']" id="pr-ue-typ-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-ue-typ'] }}</p>
          <select id="pr-ue-typ" :aria-invalid="!!feldFehler['pr-ue-typ']" :aria-describedby="feldFehler['pr-ue-typ'] ? 'pr-ue-typ-fehler' : undefined" v-model="neuPlantyp" class="dk-form-select" @change="parameterZuruecksetzen">
            <option value="" hidden>— bitte wählen —</option>
            <option v-for="t in anlegbareTypen" :key="t.id" :value="t.schluessel">
              {{ t.name || t.schluessel }}<template v-if="t.bereich"> ({{ t.bereich }})</template>
            </option>
          </select>
        </div>

        <!-- ST3: Personenpool-Hinweis — an welche Gruppen die Vorlage gebunden ist. -->
        <p v-if="neuPoolKontext" class="pr-ue-neu-hinweis pr-ue-pool" data-test="pr-ue-pool-hinweis">
          Personen aus {{ neuPoolKontext }} — es können nur diese Personen eingeplant werden.
        </p>

        <!-- ST1: Stammdaten im Seitenpanel statt Weg-Navigieren (kein Verlust). -->
        <PrErststart
          :bedarf="neuBedarf"
          :definition="neuPlantypObjekt?.letzte_version?.definition || {}"
          :stammdaten="stammdatenRoute(neuPlantyp)"
          panel @stammdaten-oeffnen="stammdatenPanelOeffnen"
        />

        <div class="dk-form-group">
          <label for="pr-ue-titel">Titel *</label>
          <p v-if="feldFehler['pr-ue-titel']" id="pr-ue-titel-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-ue-titel'] }}</p>
          <input id="pr-ue-titel" :aria-invalid="!!feldFehler['pr-ue-titel']" :aria-describedby="feldFehler['pr-ue-titel'] ? 'pr-ue-titel-fehler' : undefined" v-model="neuTitel" type="text" class="dk-form-input" placeholder="z. B. Chorplan 2026" />
        </div>

        <div class="dk-form-grid">
          <div class="dk-form-group">
            <label for="pr-ue-von">Zeitraum von *</label>
            <p v-if="feldFehler['pr-ue-von']" id="pr-ue-von-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-ue-von'] }}</p>
            <input id="pr-ue-von" :aria-invalid="!!feldFehler['pr-ue-von']" :aria-describedby="feldFehler['pr-ue-von'] ? 'pr-ue-von-fehler' : undefined" v-model="neuVon" type="date" class="dk-form-input" />
          </div>
          <div class="dk-form-group">
            <label for="pr-ue-bis">Zeitraum bis *</label>
            <p v-if="feldFehler['pr-ue-bis']" id="pr-ue-bis-fehler" role="alert" class="dk-form-error">{{ feldFehler['pr-ue-bis'] }}</p>
            <input id="pr-ue-bis" :aria-invalid="!!feldFehler['pr-ue-bis']" :aria-describedby="feldFehler['pr-ue-bis'] ? 'pr-ue-bis-fehler' : undefined" v-model="neuBis" type="date" class="dk-form-input" />
          </div>
        </div>

        <PrParameterForm v-if="neuParameterDef.length" :parameter="neuParameterDef" v-model="neuParameter" />

        <p v-else class="pr-ue-neu-hinweis">Diese Planvorlage braucht keine weiteren Angaben.</p>
      </form>

      <template #footer>
        <button type="button" class="dk-btn dk-btn-ghost" @click="neuOffen = false">Abbrechen</button>
        <button
          type="button" class="dk-btn dk-btn-primary"
          :disabled="neuSpeichert"
          @click="planAnlegenDurchfuehren"
        >{{ neuSpeichert ? 'Wird angelegt …' : 'Plan anlegen' }}</button>
      </template>
    </DkModal>
    <BedarfDialog v-model="bedarfOffen" :bedarf="bedarfListe" :busy="neuSpeichert" fortsetzen-text="Trotzdem Plan anlegen" @einrichten="bedarfEinrichten" @fortsetzen="planAnlegenOhneBedarf" />

    <!-- ST1: Stammdaten im Seitenpanel (über dem Dialog) — kein Weg-Navigieren. -->
    <PrStammdatenPanel
      v-model="stammdatenPanelOffen"
      :plantyp="stammdatenPanelTyp"
      :plan="stammdatenPanelPlan"
      @geschlossen="stammdatenPanelGeschlossen"
    />
  </div>
</template>

<script setup>
/**
 * Planeliste des Plan-Rahmens: ausschließlich sichtbare Pläne aus
 * plaene_liste, gruppiert nach Plantyp (bei fehlenden Stammdaten nach
 * Status). Planer legen neue Pläne über generische Plantyp-Parameter an
 * (PrParameterForm aus der Deklaration der jeweils neuesten Version).
 */
import { ref, computed, onMounted, watch } from 'vue'
import { usePlanrahmen, datumText, fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { useEntwurf } from '../../composables/useEntwurf.js'
import { showToast } from '../../composables/useToast.js'
import { pflichtFehler, erstesFehlerfeld } from '../../composables/formularPruefung.mjs'
import DkModal from '../../components/DkModal.vue'
import PrMeldungen from '../../components/planrahmen/PrMeldungen.vue'
import PrParameterForm from '../../components/planrahmen/PrParameterForm.vue'
import PrErststart from '../../components/planrahmen/PrErststart.vue'
import PrStammdatenPanel from '../../components/planrahmen/PrStammdatenPanel.vue'
import BedarfDialog from '../../components/planrahmen/BedarfDialog.vue'
import { fehlenderBedarf, stammdatenRoute } from '../../components/planrahmen/einrichten-flow.mjs'
import { statusSprache, statusBadgeKlasse } from '../../components/ui/statussprache.mjs'

const { plaeneListe, plantypenListe, planAnlegen, einrichtenRechte, bedarf, stammdatenHolen,
    katalogSichern } = usePlanrahmen()

const entwurf = useEntwurf('neuer-plan')

const laden = ref(true)
const seitenFehler = ref([])
const plaene = ref([])
const plantypen = ref(null)   // null = kein Planer (403 stillschweigend)
const einrichtRecht = ref(false)
const bedarfOffen = ref(false)
const bedarfListe = ref([])

const neuBedarf = ref([])

const neuOffen = ref(false)
const neuSpeichert = ref(false)
const neuFehler = ref([])
const feldFehler = ref({})
const neuPlantyp = ref('')
const neuTitel = ref('')
const neuVon = ref('')
const neuBis = ref('')
const neuParameter = ref({})

let bedarfNummer = 0
watch(() => neuPlantyp.value, async (typ) => {
    const nummer = ++bedarfNummer
    neuBedarf.value = []
    if (!typ) return
    try {
        const liste = await bedarf(typ)
        if (nummer === bedarfNummer) neuBedarf.value = fehlenderBedarf(liste)
    } catch (err) { if (nummer === bedarfNummer) neuFehler.value = fehlerMeldungen(err) }
})

// ── Entwurf (ST1): fortlaufend sichern, nie verlieren ──────────────────────

const entwurfFrage = ref(false)      // Frage „fortsetzen/verwerfen" sichtbar
const entwurfTitel = ref('')         // gemerkter Titel für die Frage
let entwurfBereit = false            // erst nach Laden/Auflösen des Entwurfs speichern
let entwurfTimer = null
let panelRueckkehr = false           // Dialog wird nur wegen Panel-Rückkehr erneut geöffnet
let fehlerRueckkehr = false          // Dialog wird nach einem Speicherfehler erneut geöffnet

/** Der aktuelle Inhalt der Dialog-Eingaben. */
function entwurfInhalt() {
    return {
        plantyp: neuPlantyp.value,
        titel: neuTitel.value,
        von: neuVon.value,
        bis: neuBis.value,
        parameter: neuParameter.value,
    }
}

/** Ist etwas zu sichern? (Nur ein angefangener Plan wird gemerkt.) */
function entwurfHatInhalt(i) {
    return !!(i && (i.plantyp || String(i.titel || '').trim() || i.von || i.bis ||
        (i.parameter && Object.keys(i.parameter).length)))
}

function entwurfSichern() {
    if (!entwurfBereit) return
    entwurf.speichern(entwurfInhalt(), { titel: String(neuTitel.value || '').trim() })
}

function entwurfSichernVerzoegert() {
    if (!entwurfBereit) return
    clearTimeout(entwurfTimer)
    entwurfTimer = setTimeout(entwurfSichern, 250)
}

function entwurfVerwerfen() {
    entwurf.entfernen()
    entwurfFrage.value = false
    entwurfTitel.value = ''
}

function entwurfFortsetzen() {
    const i = entwurf.laden()
    entwurfFrage.value = false
    if (!i) { entwurfBereit = true; return }
    neuPlantyp.value = i.plantyp || ''
    neuTitel.value = i.titel || ''
    neuVon.value = i.von || ''
    neuBis.value = i.bis || ''
    neuParameter.value = (i.parameter && typeof i.parameter === 'object') ? i.parameter : {}
    // Ab jetzt werden weitere Änderungen wieder fortlaufend gesichert.
    entwurfBereit = true
}

/** Beim Öffnen des Dialogs: Entwurf prüfen und ggf. nachfragen. */
function neuDialogGeoeffnet(offen) {
    if (!offen) {
        entwurfBereit = false
        entwurfFrage.value = false
        return
    }
    // Rückkehr aus dem Stammdaten-Panel: die Eingaben stehen ohnehin noch im
    // Dialog — kein Wiederherstellen-Dialog, sofort weitermachen.
    if (panelRueckkehr) {
        panelRueckkehr = false
        entwurfBereit = true
        entwurfFrage.value = false
        return
    }
    // UXP-R24 (d): nach einem Speicherfehler dasselbe — die Fehlermeldung
    // steht im Dialog, die Entwurfsfrage wäre nur im Weg.
    if (fehlerRueckkehr) {
        fehlerRueckkehr = false
        entwurfBereit = true
        entwurfFrage.value = false
        return
    }
    const info = entwurf.info()
    entwurfBereit = false
    entwurfFrage.value = false
    if (info && entwurfHatInhalt(entwurf.laden())) {
        entwurfTitel.value = info.titel || ''
        entwurfFrage.value = true
        return
    }
    entwurfBereit = true
}

watch(neuOffen, neuDialogGeoeffnet)
watch(entwurfInhalt, entwurfSichernVerzoegert, { deep: true })
watch(() => neuTitel.value, entwurfSichernVerzoegert)

// ── Stammdaten im Seitenpanel (ST1) ────────────────────────────────────────

const stammdatenPanelOffen = ref(false)
const stammdatenPanelTyp = ref('')
const stammdatenPanelPlan = ref('')

/** Aus dem Erststart des Neuer-Plan-Dialogs: Panel über dem Dialog öffnen. */
function stammdatenPanelOeffnen() {
    stammdatenPanelTyp.value = neuPlantyp.value
    stammdatenPanelPlan.value = ''
    stammdatenPanelOffen.value = true
}

/** Nach dem Schließen: Bedarf des Plantyps neu prüfen (Haken in Schritt 1). */
async function stammdatenPanelGeschlossen() {
    const typ = neuPlantyp.value
    if (!typ) return
    const nummer = ++bedarfNummer
    try {
        const liste = await bedarf(typ)
        if (nummer === bedarfNummer) neuBedarf.value = fehlenderBedarf(liste)
    } catch (err) { if (nummer === bedarfNummer) neuFehler.value = fehlerMeldungen(err) }
}


async function ladenAlles() {
    laden.value = true
    seitenFehler.value = []
    // P3-1d (W2/W3) / REST-1 (2): Kochbuch-Vorlagen (Anzeigenamen-Nachschlag)
    // und der Feiertags-Katalog des Servers werden EINMAL je Sitzung geholt
    // (`katalogSichern` merkt das Versprechen — kein zweiter Satz Aufrufe bei
    // jedem Besuch). Dieselbe Funktion laden die Arbeitsseiten beim
    // Direktaufruf. Beides ist Beiwerk: ein Fehler dort darf die Planliste
    // nicht verhindern.
    const katalog = katalogSichern().catch(() => null)
    try {
        const [p, t, r] = await Promise.all([plaeneListe(), plantypenListe(), einrichtenRechte()])
        einrichtRecht.value = !!r?.darf_anlegen
        plaene.value = Array.isArray(p) ? p : []
        plantypen.value = Array.isArray(t) ? t : null
    } catch (err) {
        plaene.value = []
        seitenFehler.value = fehlerMeldungen(err)
    } finally {
        laden.value = false
    }
    await Promise.allSettled([katalog])
}

onMounted(ladenAlles)

// ── Plantypen und Rechte ───────────────────────────────────────────────────

const plantypenMap = computed(() => {
    const karte = new Map()
    for (const t of plantypen.value || []) {
        if (t.id) karte.set(t.id, t)
        if (t.schluessel) karte.set(t.schluessel, t)
    }
    return karte
})

const kannAnlegen = computed(() => (plantypen.value || []).some((t) => t.darf_plan_anlegen))
const kannEinrichten = computed(() => einrichtRecht.value || (plantypen.value || []).length > 0)
const anlegbareTypen = computed(() => (plantypen.value || []).filter((t) => t.darf_plan_anlegen))

function typFuer(plan) {
    return plantypenMap.value.get(plan?.plantyp) || null
}
function plantypName(plan) {
    return typFuer(plan)?.name || plan?.plantyp_name || ''
}
function statusText(status) {
    return statusSprache(status).wort
}
function zeitraumVon(plan) {
    const von = plan?.zeitraum_von
    const bis = plan?.zeitraum_bis
    if (!von && !bis) return ''
    return `${datumText(von, false)} – ${datumText(bis, false)}`
}

// ── Gruppierung ────────────────────────────────────────────────────────────

/** PLÄNE-FILTER (P1-14b): Planer sehen archivierte Pläne auf Wunsch. Mitglieder
 *  erhalten sie vom Server gar nicht (plaene_liste blendet sie aus), hier ist
 *  der Filter deshalb wirkungslos — er erscheint nur, wenn wirklich ein Archiv
 *  vorhanden ist. */
const archivZeigen = ref(false)
const hatArchiv = computed(() => plaene.value.some((p) => p.status === 'archiviert'))
const sichtbarePlaene = computed(() => archivZeigen.value
    ? plaene.value
    : plaene.value.filter((p) => p.status !== 'archiviert'))

const gruppen = computed(() => {
    const karte = new Map()
    for (const p of sichtbarePlaene.value) {
        // Plantyp-Gruppe, sonst Statusgruppe — nie eine leere Gruppe.
        const gruppe = [p.bereich, plantypName(p)].filter(Boolean).join(' — ') || statusText(p.status)
        if (!karte.has(gruppe)) karte.set(gruppe, [])
        karte.get(gruppe).push(p)
    }
    return [...karte.entries()]
        .map(([name, liste]) => ({
            name,
            plaene: liste.slice().sort((a, b) => (a.titel || '').localeCompare(b.titel || '', 'de')),
        }))
        .sort((a, b) => a.name.localeCompare(b.name, 'de'))
})

// ── Neuer Plan ─────────────────────────────────────────────────────────────

const neuPlantypObjekt = computed(() => plantypenMap.value.get(neuPlantyp.value) || null)

/**
 * UXP-R24: Parameter, die den Zeitraum noch einmal abfragen, erscheinen nicht.
 * Der Plan hat bereits „Zeitraum von/bis“; ein zusätzlicher Parameter `datum`
 * (Programmablauf) oder `zeitraum` (Freizeit) wurde doppelt abgefragt.
 * Der Wert wird stattdessen aus dem Planzeitraum übernommen (siehe
 * `parameterFuerServer`).
 */
const ZEITRAUM_PARAMETER = new Set(['datum', 'zeitraum'])

const neuParameterDef = computed(() => {
    const liste = neuPlantypObjekt.value?.letzte_version?.definition?.parameter
    if (!Array.isArray(liste)) return []
    return liste.filter((p) => !ZEITRAUM_PARAMETER.has(String(p?.id || '').toLowerCase()))
})

/** Die Zeitraum-Parameter der Vorlage (ausgeblendet, aber weiterhin nötig). */
const neuParameterZeitraum = computed(() => {
    const liste = neuPlantypObjekt.value?.letzte_version?.definition?.parameter
    return Array.isArray(liste)
        ? liste.filter((p) => ZEITRAUM_PARAMETER.has(String(p?.id || '').toLowerCase()))
        : []
})

/**
 * Der Parameterstand, der an den Server geht: die sichtbaren Angaben plus die
 * aus dem Planzeitraum abgeleiteten Zeitraum-Parameter. So verliert der Plan
 * seine Parameter nicht und niemand tippt dasselbe Datum zweimal.
 */
function parameterFuerServer() {
    const fertig = { ...(neuParameter.value || {}) }
    for (const p of neuParameterZeitraum.value) {
        const id = p.id
        if (p.art === 'zeitraum') {
            if (neuVon.value && neuBis.value) fertig[id] = [neuVon.value, neuBis.value]
        } else if (neuVon.value) {
            fertig[id] = neuVon.value
        }
    }
    return fertig
}

// ST3: Personenpool des gewaehlten Plantyps (Gruppen + Anzahl) fuer den Hinweis.
const neuPool = ref(null)
const neuPoolKontext = computed(() => {
    const p = neuPool.value
    if (!p || !Array.isArray(p.gruppen) || !p.gruppen.length) return ''
    const namen = (p.namen && p.namen.length ? p.namen : p.gruppen).map((n) => '„' + n + '“').join(', ')
    return `${namen} (${p.anzahl ?? 0})`
})

async function poolLaden() {
    neuPool.value = null
    if (!neuPlantyp.value) return
    try {
        const daten = await stammdatenHolen(neuPlantyp.value)
        neuPool.value = daten?.pool || null
    } catch {
        neuPool.value = null
    }
}

function parameterZuruecksetzen() {
    neuParameter.value = {}
    neuFehler.value = []
    poolLaden()
}

const neuPflichtenOk = computed(() =>
    !!neuPlantyp.value && !!neuTitel.value.trim() && !!neuVon.value && !!neuBis.value)

async function planAnlegenDurchfuehren() {
    if (neuSpeichert.value) return
    feldFehler.value = pflichtFehler([
        ['pr-ue-typ', neuPlantyp.value, 'eine Planvorlage'],
        ['pr-ue-titel', neuTitel.value, 'einen Titel'],
        ['pr-ue-von', neuVon.value, 'den Beginn'],
        ['pr-ue-bis', neuBis.value, 'das Ende'],
    ])
    if (neuVon.value && neuBis.value && neuBis.value < neuVon.value) {
        feldFehler.value['pr-ue-bis'] = 'Das Ende darf nicht vor dem Beginn liegen.'
    }
    if (Object.keys(feldFehler.value).length) {
        erstesFehlerfeld(feldFehler.value)
        return
    }
    neuSpeichert.value = true
    neuFehler.value = []
    try {
        bedarfListe.value = fehlenderBedarf(await bedarf(neuPlantyp.value))
        if (bedarfListe.value.length) {
            neuOffen.value = false
            bedarfOffen.value = true
            return
        }
    } catch (err) {
        neuFehler.value = fehlerMeldungen(err)
        return
    } finally { neuSpeichert.value = false }
    await planAnlegenOhneBedarf()
}

/**
 * ST1: „Jetzt einrichten" aus dem Bedarfsdialog öffnet die Stammdaten im
 * Seitenpanel über dem Dialog — statt wegzunavigieren (sonst wäre der
 * angefangene Plan verloren). Nach dem Schließen wird der Bedarf neu geprüft.
 */
function bedarfEinrichten() {
    bedarfOffen.value = false
    panelRueckkehr = true
    neuOffen.value = true
    stammdatenPanelTyp.value = neuPlantyp.value
    stammdatenPanelPlan.value = ''
    stammdatenPanelOffen.value = true
}

async function planAnlegenOhneBedarf() {
    if (!neuPflichtenOk.value || neuSpeichert.value) return
    bedarfOffen.value = false
    neuSpeichert.value = true
    neuFehler.value = []
    try {
        const erg = await planAnlegen(
            neuPlantyp.value, neuTitel.value.trim(), neuVon.value, neuBis.value, parameterFuerServer())
        // Erfolgreich angelegt → der Entwurf hat sich erledigt.
        entwurf.entfernen()
        entwurfFrage.value = false
        entwurfTitel.value = ''
        neuOffen.value = false
        showToast('Plan angelegt.')
        if (erg?.id) {
            window.location.hash = '#/planrahmen/plan/' + encodeURIComponent(erg.id)
        } else {
            await ladenAlles()
        }
    } catch (err) {
        neuFehler.value = fehlerMeldungen(err)
        // UXP-R24 (d): beim Wiederöffnen nach einem Fehler NICHT zusätzlich
        // „angefangener Plan — fortsetzen oder verwerfen?“ über der
        // Fehlermeldung zeigen; die Eingaben stehen ohnehin noch im Dialog.
        fehlerRueckkehr = true
        neuOffen.value = true
    } finally {
        neuSpeichert.value = false
    }
}
</script>

<style scoped>
.dk-form-error { color: var(--err); font-size: var(--fs-sm); margin: 0; }
.pr-ue-zustand { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--dk-text-muted); font-size: 0.9rem; }
.pr-ue-zustand--fehler { color: var(--dk-danger); }
.pr-ue-gruppe + .pr-ue-gruppe { margin-top: 24px; }
.pr-ue-gruppe-titel {
  font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--dk-text-muted); margin: 0 0 10px;
}
.pr-ue-zeile { text-decoration: none; justify-content: space-between; gap: 14px; }
.pr-ue-haupt { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.pr-ue-titel { font-size: 0.94rem; font-weight: 600; color: var(--dk-text); }
.pr-ue-meta { font-size: 0.76rem; color: var(--dk-text-muted); }
.pr-ue-neben { display: inline-flex; align-items: center; gap: 6px; flex-shrink: 0; }
@media (max-width: 600px) {
  .pr-ue-zeile { flex-wrap: wrap; }
  .pr-ue-neben { flex-wrap: wrap; }
}
.pr-ue-neu { display: flex; flex-direction: column; gap: 4px; }
/* OP-UI-23: unsichtbarer Absende-Knopf, damit Enter im Feld absendet. */
.pr-ue-sr-submit {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
.pr-ue-neu-block { margin-bottom: 8px; }
.pr-ue-neu-hinweis { font-size: 0.84rem; color: var(--dk-text-muted); margin: 4px 0 0; }
.pr-ue-pool { margin: 8px 0 0; padding: 8px 12px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--line); color: var(--text); font-weight: 600; }
.pr-ue-entwurf {
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px; margin-bottom: 6px;
  border: 1px solid color-mix(in oklch, var(--dk-warning) 45%, var(--dk-border));
  border-radius: 10px;
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
}
.pr-ue-entwurf-text { margin: 0; font-size: 0.88rem; color: var(--dk-text); }
.pr-ue-entwurf-aktionen { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
