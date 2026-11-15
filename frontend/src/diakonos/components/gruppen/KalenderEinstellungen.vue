<template>
  <div class="ke-wurzel">
    <!-- UI-R2: Kalender der Gruppe — Liste, Anlegen, je Kalender Freigaben
         und Sichtbarkeit. Geladen wird EINE Quelle: die Verwaltungsliste
         (`get_kalender_verwaltung`). Sie liefert auch, wo der Aufrufer
         anlegen darf — die Oberfläche rät nichts. -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="3" text="Kalender werden geladen …" />

    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Kalender nicht geladen"
      :text="fehler"
      :erneut-versuchen="() => laden()"
    />

    <template v-else-if="!gesperrt">
      <p class="ke-hinweis">
        Hier stehen die Kalender dieser Gruppe<span v-if="istUntergruppe"> und dieser
        Untergruppe</span>. Wer einen Kalender sieht, einträgt oder prüft, steht je
        Kalender unter „Freigaben“.
      </p>

      <!-- ── Anlegen ──────────────────────────────────────────────────── -->
      <div v-if="ziele.length" class="ke-anlegen">
        <DkButton class="ke-anlegen-knopf" variant="secondary" size="md" @click="dialogOeffnen">
          Kalender anlegen
        </DkButton>
      </div>

      <DkEmpty
        v-if="!zeilen.length"
        icon="📅"
        title="Noch keine Kalender"
        :text="ziele.length
          ? 'Lege den ersten Kalender dieser Gruppe an — zum Beispiel „Proben“ oder „Auftritte“.'
          : 'Diese Gruppe hat noch keine Kalender.'"
      />

      <div v-else class="ke-liste">
        <DkCard v-for="k in zeilen" :key="k.name" flach>
          <div class="ke-karte" :data-kalender="k.name">
            <div class="ke-kopf">
              <span class="ke-farbe" :style="{ background: k.farbe || 'var(--primary)' }" aria-hidden="true"></span>
              <div class="ke-titel">
                <h3 class="ke-name">{{ k.titel }}</h3>
                <p class="ke-meta">
                  {{ k.untergruppe ? 'Untergruppe: ' + k.zuordnung : 'Gruppe: ' + k.zuordnung }}
                  ·
                  {{ k.standard_gruppe_lesen ? 'alle Gruppenmitglieder lesen' : 'Lesen nur bei Freigabe' }}
                </p>
              </div>
              <DkButton class="ke-aufklappen" variant="ghost" size="md" @click="umschalten(k.name)">
                {{ offen === k.name ? 'Schließen' : 'Freigaben & Sichtbarkeit' }}
              </DkButton>
            </div>

            <!-- Die Freigaben werden ERST beim Aufklappen geladen: die
                 Gruppenliste kann lang sein, und die Rechte eines fremden
                 Kalenders braucht niemand, der ihn nur sieht. -->
            <KalenderRechte
              v-if="offen === k.name"
              :objekt="rechte[k.name]?.daten || null"
              :kalender="k.name"
              :titel="k.titel"
              :untergruppe="k.untergruppe || ''"
              :laedt="Boolean(rechte[k.name]?.laedt)"
              :fehler="rechte[k.name]?.fehler || ''"
              :busy="busy"
              :freigabe-geklappt="freigabeGeklappt"
              :gruppen="gruppenAuswahl"
              :personen-laden="personenLaden"
              :erneut-laden="() => rechteLaden(k.name)"
              @freigabe-setzen="freigabeSetzen"
              @standard-setzen="(wert) => standardSetzen(k.name, wert)"
              @beantragen="(ziel) => sichtbarkeitAendern(k.name, ziel, 'beantragen')"
              @zuruecknehmen="(ziel) => sichtbarkeitAendern(k.name, ziel, 'zuruecknehmen')"
            />
          </div>
        </DkCard>
      </div>
    </template>

    <!-- ── Kalender anlegen ────────────────────────────────────────── -->
    <DkDialog
      v-model="dialogOffen"
      title="Kalender anlegen"
      size="md"
      :before-close="schutz.darfSchliessen"
    >
      <form id="ke-form" novalidate class="ke-formular" @submit.prevent="anlegenJetzt">
        <DkHint v-if="formFehler.allgemein" variant="err">{{ formFehler.allgemein }}</DkHint>

        <DkField v-slot="feld" label="Name" required :error="formFehler.titel"
                 help="So heißt der Kalender in allen Listen und Auswahlfeldern.">
          <input :id="feld.id" v-model="form.titel" class="dk-ui-eingabe" :maxlength="TITEL_MAX" />
        </DkField>

        <DkField v-slot="feld" label="Farbe" :error="formFehler.farbe"
                 help="Farbe der Termine in der Kalenderansicht.">
          <div class="ke-farbe-zeile">
            <input :id="feld.id" v-model="form.farbe" type="color" class="ke-farbe-feld" />
            <span class="ke-farbe-wert">{{ form.farbe }}</span>
          </div>
        </DkField>

        <DkField v-if="ziele.length > 1" label="Wohin gehört der Kalender?"
                 help="Der Kalender erscheint bei allen, die diese Gruppe sehen.">
          <DkSelect
            :model-value="zielWahl"
            :options="ziele.map((z) => ({ value: z.wert, label: z.anzeige }))"
            aria-label="Wohin gehört der Kalender?"
            @update:model-value="zielWahl = $event"
          />
        </DkField>

        <fieldset class="ke-frage" role="radiogroup" :aria-labelledby="'ke-frage-titel'">
          <legend id="ke-frage-titel" class="ke-frage-titel">{{ KALENDER_ANLEGEN_FRAGE }}</legend>
          <div class="ke-frage-auswahl">
            <label v-for="opt in FRAGE_OPTIONEN" :key="String(opt.wert)" class="ke-frage-option">
              <input
                v-model="form.standardGruppeLesen"
                type="radio"
                name="ke-standard-gruppe-lesen"
                :value="opt.wert"
              />
              <span>{{ opt.text }}</span>
            </label>
          </div>
        </fieldset>
      </form>

      <template #footer>
        <DkButton variant="secondary" size="md" :disabled="speichert" @click="schliessen">Abbrechen</DkButton>
        <DkButton variant="primary" size="md" type="submit" form="ke-form" :loading="speichert">
          Anlegen
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * KalenderEinstellungen — Kalender der Gruppe: Liste, Anlegen, Freigaben und
 * Sichtbarkeit je Kalender (UI-R2, Teil 2 der Gruppen-Einstellungen).
 *
 * Endpunkte (alle aus dem EINEN Rechtesystem):
 *   kalender_verwaltung.get_kalender_verwaltung      Liste + Anlegeorte
 *   kalender_verwaltung.create_kalender              Anlegen
 *   rechte.get_objekt_rechte                         Freigaben/Sichtbarkeit eines Kalenders
 *   rechte.setze_freigabe                            Freigabe setzen/entfernen (sofort)
 *   rechte.setze_standard_gruppe_lesen               Antwort der Anlege-Frage ändern
 *   rechte.beantrage_sichtbarkeit / nimm_sichtbarkeit_zurueck
 *   rechte.get_personen_auswahl                      Personensuche (nur Namen)
 *
 * Die Oberfläche entscheidet NICHTS über Rechte; sie blendet nur aus, was der
 * Server ohnehin verweigert (403/417), und zeigt dessen Satz.
 */
import { computed, reactive, ref, onMounted, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkCard from '../ui/DkCard.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import KalenderRechte from './KalenderRechte.vue'
import { apiCall } from '../../composables/useApi.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { showToast } from '../../composables/useToast.js'
import { useFormularSchutz } from '../../composables/useFormularSchutz.js'
import {
  KALENDER_ANLEGEN_FRAGE,
  TITEL_MAX,
  anfrageZaehler,
  anlegeAnfrage,
  anlegeZiele,
  busySchluessel,
  freigabeAnfrage,
  kalenderZuordnung,
  personenAuswahlOhne,
  pruefeNeuenKalender,
  sichererFehlertext,
  sichtbarkeitMeldung,
} from './kalenderRechte.mjs'

const RECHTS = 'diakronos_app.api.rechte'
const VERWALTUNG = 'kronos.kalender_verwaltung.get_kalender_verwaltung'
const ANLEGEN = 'kronos.kalender_verwaltung.create_kalender'

/**
 * Die zwei Antworten der Anlege-Frage — EINE Radiogruppe, nie „nichts
 * gewählt“: `form.standardGruppeLesen` ist von Anfang an `true`, und ein Klick
 * setzt den Wert wirklich (zwei Kästchen konnten beide leer stehen, Review
 * UI-R2b, Punkt 7).
 */
const FRAGE_OPTIONEN = [
  { wert: true, text: 'Ja, alle Gruppenmitglieder dürfen lesen' },
  { wert: false, text: 'Nein, nur mit eigener Freigabe' },
]

const props = defineProps({
  /** Kennung der HAUPTgruppe (auf einer Untergruppen-Seite: der Obergruppe). */
  gruppe: { type: String, required: true },
  /** Kennung dieser Untergruppe (leer auf einer Gruppenseite). */
  untergruppe: { type: String, default: '' },
  /** Anzeigename der Gruppe (für die Auswahl „Wohin gehört der Kalender?“). */
  gruppeName: { type: String, default: '' },
  /** Anzeigename dieser Untergruppe. */
  untergruppeName: { type: String, default: '' },
  /** Untergruppen der Gruppe: [{ name, anzeigename }]. */
  untergruppen: { type: Array, default: () => [] },
})

/**
 * `geaendert` — etwas hat sich geändert (die Seite lädt nach).
 * `gesperrt`  — UI-R2c: 403 aus `get_kalender_verwaltung`; die ganze Karte
 *               hat nichts zu zeigen und wird von der Seite ausgeblendet.
 *               UI-R2d: zweites Argument `antwortDa` — die Karte der Seite
 *               erscheint erst mit einer Antwort (kein Aufblitzen).
 *               UI-R2e: JEDE Antwort zählt, auch eine Fehlerantwort. Vorher
 *               meldete der Fehlerzweig `false` — die Seite hielt den Inhalt
 *               versteckt, und „Kalender nicht geladen / Erneut versuchen“ war
 *               nie zu sehen.
 */
const emit = defineEmits(['geaendert', 'gesperrt'])

const istUntergruppe = computed(() => Boolean(props.untergruppe))

// ── Laden ─────────────────────────────────────────────────────────────────
const laedt = ref(true)
const { skelettSichtbar } = useLadeSkelett(laedt)
const fehler = ref('')
const verwaltung = ref(null)
const busy = ref('')
/**
 * UI-R2e: Ausgang der letzten Freigabe — `null` solange keine Aussage da ist.
 * Der Rechte-Baustein leert seine Gruppenauswahl nur, wenn die Freigabe auch
 * durchging; nach einem 403/417 bleibt sie stehen.
 */
const freigabeGeklappt = ref(null)
/** 403 aus `get_kalender_verwaltung`: diese Person verwaltet keine Kalender. */
const gesperrt = ref(false)
/** Anfragezähler je Kalender (nur die jüngste Antwort schreibt). */
const zaehler = anfrageZaehler()

/** „Wohin gehört der Kalender?“ — der vom Server erlaubte Ort. */
const ziele = computed(() => anlegeZiele(verwaltung.value || {}, {
  gruppe: props.gruppe,
  untergruppe: props.untergruppe,
  gruppeName: namensSicher(props.gruppe, props.gruppeName),
  untergruppeName: namensSicher(props.untergruppe, props.untergruppeName),
}))

/**
 * Ein Anzeigename gilt NUR für seine eigene Kennung an dieser Stelle.
 *
 * Reicht ein Aufrufer (z. B. UI-R3) eine gruppenfremde Kennung durch, darf
 * der Name der Seite nicht daran kleben — sonst hieße ein fremder Kalender
 * wie diese Gruppe. Leer heißt: die Kennung spricht für sich.
 */
function namensSicher(kennung, name) {
  const k = String(kennung || '').trim()
  const n = String(name || '').trim()
  return n && n !== k ? n : ''
}

/** Anzeigenamen der (Unter-)Gruppen — die Liste liefert nur Kennungen. */
const namen = computed(() => {
  const karte = {}
  if (props.gruppe) karte[props.gruppe] = namensSicher(props.gruppe, props.gruppeName) || props.gruppe
  for (const u of (Array.isArray(props.untergruppen) ? props.untergruppen : [])) {
    if (u && u.name) karte[u.name] = u.anzeigename || u.untergruppenname || String(u.name)
  }
  if (props.untergruppe) {
    karte[props.untergruppe] = namensSicher(props.untergruppe, props.untergruppeName) || props.untergruppe
  }
  return karte
})

/** Die Kalender dieser Gruppe (und ihrer Untergruppen). */
const zeilen = computed(() => kalenderZuordnung(verwaltung.value?.kalender, {
  gruppe: props.gruppe,
  untergruppe: props.untergruppe,
  namen: namen.value,
}))

/** Gruppen für die Freigaben-Matrix: die eigene Gruppe und ihre Untergruppen. */
const gruppenAuswahl = computed(() => {
  const liste = []
  if (props.gruppe) {
    liste.push({ name: props.gruppe, anzeigename: namensSicher(props.gruppe, props.gruppeName) || props.gruppe })
  }
  for (const u of (Array.isArray(props.untergruppen) ? props.untergruppen : [])) {
    if (u && u.name) liste.push({ name: String(u.name), anzeigename: u.anzeigename || u.untergruppenname || String(u.name) })
  }
  return liste
})

/**
 * Freigaben je Kalender — NUR was aufgeklappt war wird geladen (`offen`).
 * Der Zustand je Kalender: { daten, laedt, fehler }.
 */
const rechte = reactive({})
const offen = ref('')

async function verwaltungLaden({ still = false } = {}) {
  if (!props.gruppe) { laedt.value = false; return }
  if (!still) {
    laedt.value = true
    fehler.value = ''
  }
  try {
    const antwort = await apiCall(VERWALTUNG, {})
    verwaltung.value = antwort || null
    fehler.value = ''
    gesperrt.value = false
    // UI-R2d: „Antwort da“ melden, BEVOR `laedt` fällt — die Seite zeigt die
    // Karte erst mit einer Antwort und blendet sie nie vorher ein (kein
    // Aufblitzen bei 403).
    emit('gesperrt', false, true)
  } catch (e) {
    // 403 = der Server gibt dieser Person keine verwaltbaren Kalender. Das ist
    // kein Fehler, sondern eine Lage: die Karte hat hier nichts zu zeigen und
    // blendet sich aus (Review UI-R2b, Punkt 16). Jeder andere Fehler bleibt
    // sichtbar — mit „Erneut versuchen“.
    if (Number(e?.status) === 403) {
      gesperrt.value = true
      verwaltung.value = null
      fehler.value = ''
      // UI-R2c: der 403 ist eine LAGE der ganzen Karte — nicht nur des Inhalts.
      // Die Karte „Kalender der Gruppe“ gehört der Seite (GruppeDetail.vue);
      // ohne diesen Ruf bliebe dort eine leere Fläche mit Titel stehen.
      // UI-R2d: der Ruf trägt jetzt mit, OB schon eine Antwort da ist (`false`)
      // — die Seite zeigt die Karte erst dann (kein Aufblitzen).
      emit('gesperrt', true, false)
      return
    }
    // Jeder andere Fehler: die Karte bleibt stehen (sie zeigt ihren Hinweis).
    // UI-R2e: und die Antwort GILT als Antwort (`true`) — sonst hielte die
    // Seite den Inhalt versteckt und der Hinweis „Kalender nicht geladen“
    // wäre nie zu sehen. Ein Fehler ist ein Ergebnis, kein Schweigen.
    fehler.value = sichererFehlertext(e, { text: 'Die Kalender konnten nicht geladen werden.' })
    emit('gesperrt', false, true)
  } finally {
    laedt.value = false
  }
}

/** Kurzform für Tests und Aufrufer von außen (gleicher Weg). */
const laden = verwaltungLaden

/**
 * Freigaben EINES Kalenders laden.
 *
 * Der Anfragezähler je Kalender sorgt dafür, dass nur die JÜNGSTE Antwort in
 * die Karte schreibt: auf/zu/auf (oder Speichern während eines Nachladens)
 * ließ vorher eine ältere Antwort die neueren Daten überschreiben
 * (Review UI-R2b, Punkt 4).
 */
async function rechteLaden(name) {
  if (!name) return
  const nr = zaehler.starten(name)
  if (!rechte[name]) rechte[name] = { daten: null, laedt: true, fehler: '' }
  else rechte[name] = { ...rechte[name], laedt: true, fehler: '' }
  try {
    const daten = await apiCall(`${RECHTS}.get_objekt_rechte`, { typ: 'kalender', objekt: name })
    if (!zaehler.aktuell(name, nr)) return
    rechte[name] = { daten: daten || null, laedt: false, fehler: '' }
  } catch (e) {
    if (!zaehler.aktuell(name, nr)) return
    rechte[name] = { daten: null, laedt: false, fehler: sichererFehlertext(e, {
      text: 'Die Freigaben konnten nicht geladen werden.',
    }) }
  }
}

/** Auf-/Zuklappen einer Karte — beim Aufklappen die Freigaben holen. */
function umschalten(name) {
  if (offen.value === name) { offen.value = ''; return }
  offen.value = name
  rechteLaden(name)
}

/**
 * Nach einer Änderung: Freigaben DIESES Kalenders still nachladen.
 *
 * `still` heißt: die Karte bleibt mit ihrem Inhalt stehen (kein Sprung nach
 * oben, kein Skelett); nur die Zahlen werden neu geholt.
 */
async function rechteNachladen(name, meldung) {
  await rechteLaden(name)
  await verwaltungLaden({ still: true })
  if (meldung) showToast(meldung, 'success')
  emit('geaendert')
}

// ── Freigaben ─────────────────────────────────────────────────────────────
async function freigabeSetzen({ objekt, art, kennung, lesen, schreiben, moderieren }) {
  // Der Schlüssel MUSS aus demselben Baukasten kommen wie im Baustein
  // (`busySchluessel`) — sonst sperrt die Zeile nie und ein Doppelklick
  // sendet zweimal (Review UI-R2b, Punkt 3).
  const schluessel = busySchluessel('freigabe', objekt, art, kennung)
  if (busy.value) return
  busy.value = schluessel
  // UI-R2e: `null` = noch keine Aussage. Erst das Ergebnis sagt, ob die
  // Gruppenauswahl im Rechte-Baustein geleert werden darf.
  freigabeGeklappt.value = null
  try {
    await apiCall(`${RECHTS}.setze_freigabe`, freigabeAnfrage({ objekt, art, kennung, lesen, schreiben, moderieren }))
    freigabeGeklappt.value = true
    const entfernt = !lesen && !schreiben && !moderieren
    await rechteNachladen(objekt, entfernt ? 'Freigabe entfernt — gilt sofort.' : 'Freigabe gespeichert — gilt sofort.')
  } catch (e) {
    // 403 beim „Moderieren“ (nur HV/MV) und 417 bei unzulässigen Werten
    // kommen als Fachsatz des Servers — zeigen, nichts lokal entscheiden.
    freigabeGeklappt.value = false
    showToast(sichererFehlertext(e, { text: 'Das Speichern hat nicht geklappt.' }), 'error')
    await rechteLaden(objekt)
  } finally {
    busy.value = ''
  }
}

async function standardSetzen(objekt, wert) {
  const schluessel = busySchluessel('standard', objekt)
  if (busy.value) return
  busy.value = schluessel
  try {
    await apiCall(`${RECHTS}.setze_standard_gruppe_lesen`, { typ: 'kalender', objekt, wert })
    await rechteNachladen(objekt, wert
      ? 'Alle Gruppenmitglieder dürfen diesen Kalender jetzt lesen.'
      : 'Jetzt lesen nur eingetragene Personen.')
  } catch (e) {
    showToast(sichererFehlertext(e, { text: 'Das Speichern hat nicht geklappt.' }), 'error')
  } finally {
    busy.value = ''
  }
}

async function sichtbarkeitAendern(objekt, ziel, weg) {
  const schluessel = busySchluessel('sichtbarkeit', objekt, ziel)
  if (busy.value) return
  busy.value = schluessel
  const endpunkt = weg === 'beantragen' ? 'beantrage_sichtbarkeit' : 'nimm_sichtbarkeit_zurueck'
  try {
    const antwort = await apiCall(`${RECHTS}.${endpunkt}`, { typ: 'kalender', objekt, ziel })
    // Der Server sagt, was daraus wurde (beantragt oder sofort aktiv, weil
    // der Aufrufer selbst prüfen darf) — die Meldung nennt SEINEN Stand UND
    // das Ziel: „für die ganze Gruppe“ ist etwas anderes als „für alle
    // Mitglieder der Gemeinde“ (Review UI-R2b, Punkt 12).
    const stand = ziel === 'gruppe' ? antwort?.gruppe_status : antwort?.gemeinde_status
    await rechteNachladen(objekt, sichtbarkeitMeldung({ ziel }, stand, weg))
  } catch (e) {
    showToast(sichererFehlertext(e, { text: 'Das Speichern hat nicht geklappt.' }), 'error')
    await rechteLaden(objekt)
  } finally {
    busy.value = ''
  }
}

/** Personen für die Freigabe-Suche (Konto + Name, nichts weiter). */
async function personenLaden(suche = '') {
  try {
    const res = await apiCall(`${RECHTS}.get_personen_auswahl`, { suche: suche || '', limit: 50 })
    const alle = Array.isArray(res?.personen) ? res.personen : []
    // Bereits eingetragene Personen dieses Kalenders fallen heraus — sonst
    // stünden sie doppelt in der Matrix.
    const aktuell = offen.value ? (rechte[offen.value]?.daten?.freigaben || []) : []
    return personenAuswahlOhne(alle, aktuell)
  } catch (e) {
    throw new Error(sichererFehlertext(e, { text: 'Die Personensuche ist gerade nicht erreichbar.' }))
  }
}

// ── Anlegen ───────────────────────────────────────────────────────────────
const dialogOffen = ref(false)
const speichert = ref(false)
const form = reactive({
  titel: '',
  farbe: '',
  standardGruppeLesen: true,
})
const zielWahl = ref('')
const formFehler = reactive({ allgemein: '', titel: '', farbe: '' })
// Solange der Dialog zu ist, gibt es nichts zu verlieren (`null`) — sonst
// fragte der Wächter nach jedem Schließen „Änderungen verwerfen?“.
const schutz = useFormularSchutz(() => (dialogOffen.value
  ? JSON.stringify({ titel: form.titel, farbe: form.farbe, lesen: form.standardGruppeLesen, ziel: zielWahl.value })
  : null))

/** Vorgewählter Ort: auf einer Untergruppen-Seite die eigene Untergruppe. */
const zielVorgabe = computed(() => (ziele.value.find((z) => z.art === 'untergruppe')
  || ziele.value[0] || null))

function dialogOeffnen() {
  form.titel = ''
  form.farbe = verwaltung.value?.farbe_standard || ''
  form.standardGruppeLesen = true
  zielWahl.value = zielVorgabe.value?.wert ?? ''
  formFehler.allgemein = ''
  formFehler.titel = ''
  formFehler.farbe = ''
  dialogOffen.value = true
  // Grundstand NACH dem Befüllen setzen: Vorgaben sind keine Änderung.
  schutz.merken()
}

function schliessen() {
  if (!schutz.darfSchliessen()) return
  dialogOffen.value = false
}

/** Der gewählte Ort — fehlt die Wahl, gilt die Vorgabe des Servers. */
function gewaehltesZiel() {
  const wert = zielWahl.value ?? ''
  return ziele.value.find((z) => (z.wert || '') === String(wert)) || zielVorgabe.value || null
}

async function anlegenJetzt() {
  const pruefung = pruefeNeuenKalender({ titel: form.titel, farbe: form.farbe })
  formFehler.titel = pruefung.titel
  formFehler.farbe = pruefung.farbe
  formFehler.allgemein = ''
  if (!pruefung.ok) return
  const ziel = gewaehltesZiel()
  if (!ziel) {
    formFehler.allgemein = 'Für diese Gruppe darfst du keinen Kalender anlegen.'
    return
  }

  speichert.value = true
  try {
    const anfrage = anlegeAnfrage({
      titel: form.titel,
      farbe: form.farbe,
      ziel,
      standardGruppeLesen: form.standardGruppeLesen,
    })
    await apiCall(ANLEGEN, anfrage)
    dialogOffen.value = false
    showToast(`Kalender „${anfrage.titel}“ angelegt.`, 'success')
    await verwaltungLaden({ still: true })
    emit('geaendert')
  } catch (e) {
    // Fachfehler des Servers („Ein Kalender mit dem Namen … gibt es schon.“)
    // stehen im Dialog — der Text bleibt erhalten, nichts wird geleert.
    formFehler.allgemein = sichererFehlertext(e, { text: 'Das Anlegen hat nicht geklappt.' })
  } finally {
    speichert.value = false
  }
}

onMounted(() => verwaltungLaden())
watch(() => [props.gruppe, props.untergruppe], () => {
  offen.value = ''
  for (const schluessel of Object.keys(rechte)) delete rechte[schluessel]
  verwaltungLaden()
})
</script>

<style scoped>
.ke-wurzel { display: flex; flex-direction: column; gap: var(--sp-4); }
.ke-hinweis { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.ke-anlegen { display: flex; justify-content: flex-start; }
.ke-liste { display: flex; flex-direction: column; gap: var(--sp-3); }
.ke-karte { display: flex; flex-direction: column; gap: var(--sp-3); }
.ke-kopf { display: flex; align-items: flex-start; gap: var(--sp-3); flex-wrap: wrap; }
.ke-farbe {
  width: var(--sp-3);
  height: var(--sp-3);
  border-radius: var(--radius-sm);
  margin-top: var(--sp-1);
  flex: none;
}
.ke-titel { display: flex; flex-direction: column; gap: var(--sp-1); flex: 1; min-width: 0; }
.ke-name { margin: 0; font-size: var(--fs); font-weight: var(--fw-medium); color: var(--text); overflow-wrap: anywhere; }
.ke-meta { margin: 0; color: var(--muted); font-size: var(--fs-xs); }
.ke-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
.ke-farbe-zeile { display: flex; align-items: center; gap: var(--sp-2); }
.ke-farbe-feld {
  width: calc(var(--sp-6) + var(--sp-3));
  height: var(--control-h);
  padding: 0;
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius-sm);
  background: var(--surface);
}
.ke-farbe-wert { font-size: var(--fs-sm); color: var(--muted); }
.ke-frage { border: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.ke-frage-titel { padding: 0; font-size: var(--fs-sm); font-weight: var(--fw-medium); color: var(--text); }
.ke-frage-auswahl { display: flex; flex-direction: column; gap: var(--sp-2); }
/* Echte Radiogruppe: ein Punkt, zwei Antworten — nie „nichts gewählt“. */
.ke-frage-option { display: flex; align-items: flex-start; gap: var(--sp-2); font-size: var(--fs-sm); color: var(--text); }
.ke-frage-option input { margin: 0; flex-shrink: 0; accent-color: var(--primary); }
</style>
