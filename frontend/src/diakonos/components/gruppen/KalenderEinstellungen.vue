<template>
  <div class="ke-wurzel">
    <!-- UI-R2: Kalender der Gruppe — Liste, Anlegen, je Kalender Freigaben
         und Sichtbarkeit. Geladen wird EINE Quelle: die Verwaltungsliste
         (`get_kalender_verwaltung`). Sie liefert auch, wo der Aufrufer
         anlegen darf — die Oberfläche rät nichts. -->
    <!-- UI-R3c (SOLL 4): Bis zur ersten Antwort steht hier NICHTS — kein
         Leerzustand („Noch keine Kalender“ blitzte vorher kurz auf, weil
         `zeilen` ohne Antwort ebenfalls leer ist), und das Skelett erst nach
         300 ms (`useLadeSkelett`). `antwortDa` ist der eine Schalter dafür. -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="3" text="Kalender werden geladen …" />

    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Kalender nicht geladen"
      :text="fehler"
      :erneut-versuchen="() => laden()"
    />

    <template v-else-if="!gesperrt && antwortDa">
      <!-- DES-1: der Hinweis gehört dem ORT — seit DES-1 steht er strukturell
           im KARTENKOPF (`DkCard sub`, über `@hinweis` an die Seite), nicht
           mehr als erster Absatz im Körper: dort quetschte er den Kartentitel.
           In der Kalenderverwaltung (`alleKalender`) gibt es ihn nicht — dort
           stehen nicht „die Kalender dieser Gruppe“, und ein zweiter Hinweis
           neben dem der Seite wäre einer zu viel (A4). -->

      <!-- ── Anlegen ──────────────────────────────────────────────────── -->
      <!-- UI-R3b: im Modus `alleKalender` führt die SEITE den einen
           Anlege-Knopf (A4) — die Fläche bringt dann keinen eigenen mit. -->
      <div v-if="ziele.length && !alleKalender" class="ke-anlegen">
        <DkButton class="ke-anlegen-knopf" variant="secondary" size="md" @click="dialogOeffnen">
          Kalender anlegen
        </DkButton>
      </div>

      <DkEmpty
        v-if="!zeilen.length"
        icon="📅"
        title="Noch keine Kalender"
        :text="leerText"
      />

      <div v-else class="ke-liste">
        <!-- DES-1: je Kalender EINE FLACHE Zeile im Kopf der Karte — kein
             Karte-in-Karte mit eigenem Schatten/Polster (Review 2: die Zeilen
             sind Gliederungen INNERHALB der Karte „Kalender der Gruppe“, nicht
             Karten für sich). Titel und Zuordnung trägt der Kartenkopf
             (`title`/`sub`), die Überschrift steht eine Ebene tiefer (`ebene=3`
             → h3 unter dem h2 der Karte), und der Farbpunkt des Kalenders
             gehört als Kennzeichen VOR den Titel (`#vor-titel`, Review 3).
             DES-1b: der Kopf ist KEIN Eigenbau mehr — der Baustein schreibt
             Überschrift, Unterzeile, Ellipse und Handy-Umbruch; die Zeile
             liefert nur noch `title`/`sub`/`ebene` und den Punkt.
             `zeile`: der Baustein gibt seine Kopf-Polsterung ab (DES-1b,
             Review 4) — die Zeile polstert selbst, Titel und Freigaben-Feld
             stehen bündig; `flach` nimmt den Innenabstand des Körpers. -->
        <DkCard
          v-for="k in zeilen"
          :key="k.name"
          class="ke-zeile"
          flach
          zeile
          :data-kalender="k.name"
          :ebene="3"
          :title="k.titel"
          :sub="kalenderZeileText(k)"
        >
          <template #vor-titel>
            <span
              class="ke-farbe"
              :style="{ background: k.farbe || 'var(--primary)' }"
              aria-hidden="true"
            ></span>
          </template>
          <template #actions>
            <DkButton
              class="ke-bearbeiten"
              variant="ghost"
              size="md"
              :disabled="Boolean(busy)"
              @click="bearbeiten(k)"
            >Bearbeiten</DkButton>
            <DkButton
              class="ke-loeschen"
              variant="ghost"
              size="md"
              :disabled="Boolean(busy)"
              @click="entfernen(k)"
            >Löschen</DkButton>
            <!-- DES-1 (Review 1): EIN Weg zum Aufklappen — der Knopf im Kopf
                 hängt am selben Handler wie vorher der Körperknopf
                 (`umschalten`). Der zweite Knopf im Körper ist entfallen.
                 DES-1b (Review 5): `aria-controls` zeigt auf das Feld, das er
                 aufklappt (id `ke-freigaben-<name>`). -->
            <DkButton
              class="ke-aufklappen"
              variant="ghost"
              size="md"
              :disabled="Boolean(busy)"
              :aria-expanded="offen === k.name ? 'true' : 'false'"
              :aria-controls="freigabenFeldId(k.name)"
              @click="umschalten(k.name)"
            >{{ offen === k.name ? 'Freigaben schließen' : 'Freigaben' }}</DkButton>
          </template>
          <div
            :id="freigabenFeldId(k.name)"
            class="ke-koerper"
          >
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
              :gruppen="gruppenAuswahlFuer(k)"
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

        <p v-if="nurEinZiel && einzigerOrtText" class="ke-ort">{{ einzigerOrtText }}</p>

        <DkField v-if="ziele.length && !nurEinZiel" label="Wohin gehört der Kalender?"
                 :help="zielHilfe">
          <DkSelect
            :model-value="zielWahl"
            :options="ziele.map((z) => ({ value: z.wert, label: z.anzeige }))"
            aria-label="Wohin gehört der Kalender?"
            @update:model-value="zielWahl = $event"
          />
        </DkField>

        <fieldset v-if="!istGemeindeZiel" class="ke-frage" role="radiogroup" :aria-labelledby="'ke-frage-titel'">
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
    <!-- ── Kalender bearbeiten (UI-R3b) ─────────────────────────────── -->
    <DkDialog
      v-model="bearbeitenOffen"
      :title="bearbeitet ? `Kalender „${bearbeitet.titel}“ bearbeiten` : 'Kalender bearbeiten'"
      size="md"
      :before-close="schutzBearbeiten.darfSchliessen"
    >
      <form id="ke-form-bearbeiten" novalidate class="ke-formular" @submit.prevent="bearbeitenSpeichern">
        <DkHint v-if="bearbeitenFehler.allgemein" variant="err">{{ bearbeitenFehler.allgemein }}</DkHint>

        <DkField v-slot="feld" label="Name" required :error="bearbeitenFehler.titel"
                 help="So heißt der Kalender in allen Listen und Auswahlfeldern.">
          <input :id="feld.id" v-model="bearbeitenForm.titel" class="dk-ui-eingabe" :maxlength="TITEL_MAX" />
        </DkField>

        <DkField v-slot="feld" label="Farbe" :error="bearbeitenFehler.farbe"
                 help="Farbe der Termine in der Kalenderansicht.">
          <div class="ke-farbe-zeile">
            <input :id="feld.id" v-model="bearbeitenForm.farbe" type="color" class="ke-farbe-feld" />
            <span class="ke-farbe-wert">{{ bearbeitenForm.farbe }}</span>
          </div>
        </DkField>

        <DkCheckbox v-model="bearbeitenForm.selbstverwaltet">
          Selbstverwaltet (eine Gruppe pflegt diesen Kalender selbst)
        </DkCheckbox>
      </form>

      <template #footer>
        <DkButton variant="secondary" size="md" :disabled="bearbeitenSpeichert" @click="bearbeitenSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" size="md" type="submit" form="ke-form-bearbeiten" :loading="bearbeitenSpeichert">
          Speichern
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * KalenderEinstellungen — Kalender der Gruppe: Liste, Anlegen, Bearbeiten,
 * Löschen, Freigaben und Sichtbarkeit je Kalender (UI-R2, Teil 2 der
 * Gruppen-Einstellungen; UI-R3b hat Bearbeiten/Löschen zurückgebracht).
 *
 * Endpunkte (alle aus dem EINEN Rechtesystem):
 *   kalender_verwaltung.get_kalender_verwaltung      Liste + Anlegeorte
 *   kalender_verwaltung.create_kalender              Anlegen
 *   kalender_verwaltung.update_kalender              Titel, Farbe, selbstverwaltet
 *   kalender_verwaltung.delete_kalender              Löschen (mit `bestaetigt`)
 *   rechte.get_objekt_rechte                         Freigaben/Sichtbarkeit eines Kalenders
 *   rechte.setze_freigabe                            Freigabe setzen/entfernen (sofort)
 *   rechte.setze_standard_gruppe_lesen               Antwort der Anlege-Frage ändern
 *   rechte.beantrage_sichtbarkeit / nimm_sichtbarkeit_zurueck
 *   rechte.get_personen_auswahl                      Personensuche (nur Namen)
 *
 * Die Oberfläche entscheidet NICHTS über Rechte; sie blendet nur aus, was der
 * Server ohnehin verweigert (403/417), und zeigt dessen Satz. Aendern und
 * Löschen prüft der Server selbst (`_require_kalender_verwalten`).
 */
import { computed, reactive, ref, onMounted, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkCard from '../ui/DkCard.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
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
// UX2c (C2 · Prinzip I2): Löschen ist umkehrbar (neu anlegen) → sofort +
// „Rückgängig“; nur bei einem Google-Import bleibt die Rückfrage.
import { useRueckgaengigAktion } from '../../composables/useRueckgaengigAktion.js'
import { wiederherstellen as gegenrichtung, vollstaendig } from '../../composables/rueckgaengigWeg.mjs'
import { bestaetigen } from '../../composables/useBestaetigen.js'
// ON-0b: die EINE Standardfarbe (`shared/sichere-ausgabe.js`) — kein Literal
// im Farbfeld, wenn der Server einmal keine Farbe mitliefert.
import { STANDARD_FARBE } from '../../../shared/sichere-ausgabe.js'
import {
  KALENDER_ANLEGEN_FRAGE,
  TITEL_MAX,
  aenderungsAnfrage,
  alleKalenderZeilen,
  anfrageZaehler,
  anlegeAnfrage,
  anlegeZiele,
  busySchluessel,
  freigabeAnfrage,
  kalenderZuordnung,
  loeschAnfrage,
  loeschRueckfrageText,
  personenAuswahlOhne,
  pruefeNeuenKalender,
  sichererFehlertext,
  sichtbarkeitMeldung,
  verweigerungsText,
} from './kalenderRechte.mjs'

const RECHTS = 'diakronos_app.api.rechte'
const VERWALTUNG = 'kronos.kalender_verwaltung.get_kalender_verwaltung'
const ANLEGEN = 'kronos.kalender_verwaltung.create_kalender'
const AENDERN = 'kronos.kalender_verwaltung.update_kalender'
const LOESCHEN = 'kronos.kalender_verwaltung.delete_kalender'

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
  /**
   * UI-R3: Alles anzeigen, was der Server dieser Person freigibt — nicht nur
   * die Kalender DIESER Gruppe. Die Kalenderverwaltung (`#/kalender/verwalten`)
   * ist keine Gruppenseite: sie zeigt alle verwaltbaren Kalender samt
   * Zuordnung und bringt die Anlegeorte in `ziele`. Vorgabe `false` — die
   * Gruppen-Seite (UI-R2) bleibt unverändert auf ihre Gruppe beschränkt.
   */
  alleKalender: { type: Boolean, default: false },
  /**
   * Anlegeziele von außen (`anlegeZiele(...)` aus `kalenderRechte.mjs`).
   * Nur wirksam mit `alleKalender`; fehlt die Liste, gilt die Vorgabe des
   * Servers aus `get_kalender_verwaltung`.
   */
  ziele: { type: Array, default: null },
  /**
   * UI-R3c: Die Verwaltungsliste, wenn der AUFRUFER sie schon geholt hat.
   *
   * `KalenderVerwaltung.vue` und diese Fläche fragten beide
   * `get_kalender_verwaltung` — zwei Anfragen für dieselbe Antwort, und die
   * Seite zeigte ihren Stand aus einer anderen Antwort als die Liste hier.
   * Jetzt holt die Seite sie einmal und reicht sie hier herein; nur ohne
   * diesen Prop lädt die Fläche selbst (Gruppenseite, Einzel-Mount im Test).
   * `null` heisst ausdrücklich „keine Antwort“ — dann wird geladen.
   */
  verwaltung: { type: Object, default: undefined },
  /**
   * UI-R3e (SOLL 4): Das Nachladen der SEITE, wenn sie die Liste besitzt.
   *
   * Mit `:verwaltung` ist `verwaltungLaden({still:true})` hier ein No-op — die
   * Fläche wartete also NICHT auf die frischen Daten, und Toast, „Rückgängig“
   * und `busy`-Ende erschienen, während die gelöschte Zeile noch dastand. Der
   * Aufrufer gibt seine Lade-Funktion (eine Promise) hier herein; fehlt sie,
   * lädt die Fläche wie bisher selbst.
   */
  nachladen: { type: Function, default: null },
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
const emit = defineEmits(['geaendert', 'gesperrt', 'hinweis'])

const istUntergruppe = computed(() => Boolean(props.untergruppe))

// ── Laden ─────────────────────────────────────────────────────────────────
const laedt = ref(true)
const { skelettSichtbar } = useLadeSkelett(laedt)
const fehler = ref('')
const verwaltung = ref(null)
/**
 * UI-R3c: Hat der AUFRUFER die Liste schon geholt (`:verwaltung`)? Dann ist
 * sie die EINE Quelle — diese Fläche fragt nicht ein zweites Mal. `null` als
 * Prop heisst „keine Antwort“ und lädt hier (siehe `verwaltungLaden`).
 */
const verwaltungVonAussen = computed(() => props.verwaltung !== undefined && props.verwaltung !== null)
const busy = ref('')
/**
 * UI-R2e: Ausgang der letzten Freigabe — `null` solange keine Aussage da ist.
 * Der Rechte-Baustein leert seine Gruppenauswahl nur, wenn die Freigabe auch
 * durchging; nach einem 403/417 bleibt sie stehen.
 */
const freigabeGeklappt = ref(null)
/** 403 aus `get_kalender_verwaltung`: diese Person verwaltet keine Kalender. */
const gesperrt = ref(false)
/**
 * UI-R3c (SOLL 4): Ist die erste Antwort da? Vorher stand der Leerzustand
 * („Noch keine Kalender“) schon, weil `zeilen` ohne Antwort ebenfalls leer
 * ist — er blitzte für die Dauer der Anfrage auf. Bis zur Antwort zeigt die
 * Fläche NICHTS (das Skelett erst nach 300 ms).
 *
 * Gesetzt wird es in JEDEM Ausgang: Antwort, 403, Fehler, „kein Kontext“.
 */
const antwortDa = ref(false)
/** Anfragezähler je Kalender (nur die jüngste Antwort schreibt). */
const zaehler = anfrageZaehler()

/**
 * DES-1: die Beschreibung dieser Karte — EINE Quelle für den Kartenkopf.
 * Sie stand früher als erster Absatz im Körper; jetzt liest die Gruppenseite
 * sie über `@hinweis` ab und setzt sie als `sub` in den Kopf (über die volle
 * Textbreite). Leer, solange keine Antwort da ist (dann gibt es auch nichts
 * zu beschreiben), und leer im Modus `alleKalender` (dort beschreibt der
 * Hinweis der Seite den Ort, nicht diese Karte).
 */
const kalenderHinweis = computed(() => {
  if (props.alleKalender || !antwortDa.value || gesperrt.value || fehler.value) return ''
  // Wortlaut wie bisher (UI-R3b), nur an EINER Stelle statt im Markup.
  const wo = istUntergruppe.value ? 'dieser Gruppe und dieser Untergruppe' : 'dieser Gruppe'
  return `Hier stehen die Kalender ${wo}. Wer einen Kalender sieht, einträgt oder prüft, `
    + 'steht je Kalender unter „Freigaben“.'
})

// DES-1: der Text geht an die SEITE (Kartenkopf der Gruppenseite).
watch(kalenderHinweis, (text) => emit('hinweis', text), { immediate: true })

/** „Wohin gehört der Kalender?“ — der vom Server erlaubte Ort. */
const ziele = computed(() => {
  if (props.alleKalender) {
    // UI-R3: die Kalenderverwaltung bringt ihre Anlegeorte selbst mit
    // (`anlegeZiele` über alle Gruppen/Untergruppen). Fehlt die Liste, gilt
    // die Vorgabe des Servers für DIESE Gruppe — nie eine erfundene Auswahl.
    if (Array.isArray(props.ziele)) return props.ziele.filter((z) => z && typeof z.art === 'string')
    return anlegeZiele(verwaltung.value || {}, {
      gruppe: props.gruppe,
      gruppeName: namensSicher(props.gruppe, props.gruppeName),
    })
  }
  return anlegeZiele(verwaltung.value || {}, {
    gruppe: props.gruppe,
    untergruppe: props.untergruppe,
    gruppeName: namensSicher(props.gruppe, props.gruppeName),
    untergruppeName: namensSicher(props.untergruppe, props.untergruppeName),
  })
})

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

/**
 * Der Gruppenbaum für die Freigabe-Auswahl: Gruppe → ihre Untergruppen.
 *
 * Quelle ist AUSSCHLIESSLICH `untergruppen` — der Gruppenbaum
 * (`get_gruppen_hierarchie`, auf der Gruppenseite der Baum der Seite, in der
 * Kalenderverwaltung der ganze Baum). Ein Eintrag `{ name, gruppe }` nennt
 * seine Obergruppe ausdrücklich; fehlt sie, hängt er an `props.gruppe` (auf
 * der Gruppenseite ist das der Kontext) — sonst bleibt er ohne Obergruppe und
 * liefert keine Freigabe-Auswahl („kein Kontext“ ist ehrlicher als ein
 * geratener).
 *
 * UI-R3e (MUSS 3): Früher hieß es hier, in der Verwaltung seien `untergruppen`
 * die Gruppen der ANLEGEZIELE. Das war der Fehler: die Freigabe-Auswahl zeigte
 * damit, wo jemand anlegen darf — ein reiner Moderator ohne Anlegeziele sah
 * eine leere Auswahl, und ein Anlegerecht nur in der Gruppe G ließ ihre
 * Untergruppen fehlen. Der Baum ist unabhängig vom Anlegerecht; was der Server
 * bei `setze_freigabe` zulässt, prüft er selbst.
 */
const mitglieder = computed(() => {
  const baum = {}
  const eintragen = (name, obergruppe) => {
    const n = String(name || '')
    if (!n) return
    if (!baum[n]) baum[n] = { untergruppen: [] }
    if (obergruppe && !baum[n].gruppe) baum[n].gruppe = String(obergruppe)
  }
  for (const u of (Array.isArray(props.untergruppen) ? props.untergruppen : [])) {
    if (!u || !u.name) continue
    const obergruppe = u.gruppe || (props.alleKalender ? '' : props.gruppe)
    eintragen(u.name, obergruppe)
    if (obergruppe) {
      eintragen(obergruppe)
      const liste = baum[String(obergruppe)].untergruppen
      if (!liste.includes(String(u.name))) liste.push(String(u.name))
    }
  }
  // Die eigene Gruppe der Seite steht immer im Baum — auch ohne Untergruppen.
  if (props.gruppe) eintragen(props.gruppe)
  return baum
})

/** Alle Gruppen des Baums (Gruppen und Untergruppen in EINER Liste). */
const alleBaumGruppen = computed(() => {
  const liste = []
  for (const [name, eintrag] of Object.entries(mitglieder.value)) {
    liste.push({ name: String(name), gruppe: String(eintrag.gruppe || '') })
  }
  for (const eintrag of Object.values(mitglieder.value)) {
    for (const u of (eintrag.untergruppen || [])) {
      if (!liste.some((e) => e.name === String(u))) liste.push({ name: String(u), gruppe: '' })
    }
  }
  return liste
})

/**
 * Anzeigenamen der (Unter-)Gruppen — die Liste liefert nur Kennungen.
 */
const namen = computed(() => {
  // UI-R3: NICHT mit `alleKalender` vermischen. Auf einer Gruppenseite gehören
  // `gruppe`/`untergruppe`/`gruppeName` ZUSAMMEN; in der Kalenderverwaltung
  // gibt es keine Gruppenseite (`gruppe` ist leer), dort kommen die Namen aus
  // dem Prop `untergruppen` (Kennung + Anzeigename) — und nur für Kennungen,
  // die wirklich dort stehen.
  const karte = {}
  if (!props.alleKalender) {
    if (props.gruppe) karte[props.gruppe] = namensSicher(props.gruppe, props.gruppeName) || props.gruppe
    if (props.untergruppe) {
      karte[props.untergruppe] = namensSicher(props.untergruppe, props.untergruppeName) || props.untergruppe
    }
  }
  for (const u of (Array.isArray(props.untergruppen) ? props.untergruppen : [])) {
    if (u && u.name) karte[u.name] = u.anzeigename || u.untergruppenname || String(u.name)
  }
  return karte
})

/** Die Kalender dieser Gruppe (und ihrer Untergruppen). */
const zeilen = computed(() => {
  if (props.alleKalender) {
    // UI-R3: ALLE Kalender, die der Server dieser Person zum Verwalten gibt —
    // je Zeile mit ihrer Zuordnung (Gemeinde / Gruppe / Untergruppe).
    return alleKalenderZeilen(verwaltung.value?.kalender, namen.value)
  }
  return kalenderZuordnung(verwaltung.value?.kalender, {
    gruppe: props.gruppe,
    untergruppe: props.untergruppe,
    namen: namen.value,
  })
})

/**
 * Text des Leerzustands. In der Kalenderverwaltung (`alleKalender`) gibt es
 * keine „diese Gruppe“, für die etwas angelegt würde — dort sagt der Satz nur,
 * was der Stand ist und was der Knopf der SEITE tut (UI-R3b, Punkt 4).
 */
const leerText = computed(() => {
  if (props.alleKalender) {
    return ziele.value.length
      ? 'Lege den ersten Kalender an — er erscheint danach mit seiner Zuordnung hier.'
      : 'Hier ist noch kein Kalender zu verwalten.'
  }
  return ziele.value.length
    ? 'Lege den ersten Kalender dieser Gruppe an — zum Beispiel „Proben“ oder „Auftritte“.'
    : 'Diese Gruppe hat noch keine Kalender.'
})

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
 * Kennungen der Freigabe-Auswahl EINES Kalenders — aus dem GANZEN Gruppenbaum.
 *
 * REGEL (UI-R3c, verschärft in UI-R3e/MUSS 3):
 *   Gruppenkalender: seine Gruppe + ALLE ihre Untergruppen laut Baum
 *                    (`mitglieder`) — unabhängig davon, wo jemand anlegen darf.
 *   Gemeinde-Kalender (`gruppe` leer): ALLE Gruppen des Baums (wie vor UI-R3c).
 *                    Die Rechtmäßigkeit prüft der Server (`setze_freigabe`).
 *
 * @param {{gruppe?: string|null, untergruppe?: string|null}} zeile
 * @returns {string[]}
 */
function kennungenFuer(zeile) {
  const gruppe = gruppeDerZeile(zeile)
  // Ohne Gruppe (Gemeinde-Kalender): der GANZE Baum. Die Rechtmäßigkeit prüft
  // der Server (`setze_freigabe`) — die Auswahl entscheidet nichts.
  if (!gruppe) return alleBaumGruppen.value.map((g) => g.name)
  return [gruppe, ...untergruppenVon(gruppe)]
}

/** Die Gruppe eines Kalenders — eine Untergruppe zählt zu ihrer Obergruppe. */
function gruppeDerZeile(zeile) {
  const k = zeile || {}
  return k.untergruppe
    ? String(mitglieder.value[k.untergruppe]?.gruppe || k.gruppe || '')
    : String(k.gruppe || '')
}

/** Die Untergruppen einer Gruppe laut Baum (`mitglieder`). */
function untergruppenVon(gruppe) {
  const liste = mitglieder.value[gruppe]?.untergruppen
  return (Array.isArray(liste) ? liste : []).map(String).filter(Boolean)
}

/** Die Auswahl als `[{name, anzeigename}]` — Namen aus `namen`, sonst Kennung. */
function auswahlAus(kennungen) {
  return kennungen.map((k) => ({ name: String(k), anzeigename: namensSicher(String(k), namen.value[k]) || String(k) }))
}

/**
 * Die Gruppen aus dem Gruppenbaum, die zu EINEM Kalender gehören: seine Gruppe
 * samt ihrer Untergruppen (aus `mitglieder`), unabhängig davon, wo jemand
 * anlegen darf.
 */
function kontextAuswahl(zeile) {
  const gruppe = gruppeDerZeile(zeile)
  if (!gruppe) return []
  return auswahlAus([gruppe, ...untergruppenVon(gruppe)])
}

/**
 * Auf einer Gruppenseite IST die Seite der Kontext (`gruppenAuswahl`); ein
 * Kalender einer FREMDEN Gruppe behält seinen eigenen (etwa ein
 * Gemeinde-Kalender, der über die Gruppenliste sichtbar wird), und ein
 * Kalender OHNE Gruppe (Gemeinde) bekommt den ganzen Baum.
 *
 * @param {{name?: string, gruppe?: string|null, untergruppe?: string|null}} zeile
 * @returns {Array<{name: string, anzeigename: string}>}
 */
function gruppenAuswahlFuer(zeile) {
  if (props.alleKalender) return auswahlAus(kennungenFuer(zeile || {}))
  const k = zeile || {}
  const gruppe = gruppeDerZeile(k)
  if (!gruppe) return auswahlAus(alleBaumGruppen.value.map((g) => g.name))
  if (gruppe !== String(props.gruppe || '')) return kontextAuswahl(k)
  return gruppenAuswahl.value
}

/**
 * Freigaben je Kalender — NUR was aufgeklappt war wird geladen (`offen`).
 * Der Zustand je Kalender: { daten, laedt, fehler }.
 */
const rechte = reactive({})
const offen = ref('')

async function verwaltungLaden({ still = false } = {}) {
  // UI-R3c: Liegt die Liste vom Aufrufer vor, ist SIE die eine Quelle — kein
  // zweiter Aufruf desselben Endpunkts. Die Fläche meldet trotzdem „Antwort
  // da“ (die Karte der Seite erscheint) und zeigt den Inhalt.
  if (verwaltungVonAussen.value) {
    verwaltung.value = props.verwaltung
    fehler.value = ''
    gesperrt.value = false
    antwortDa.value = true
    laedt.value = false
    emit('gesperrt', false, true)
    return
  }
  // Kein Kontext (weder Gruppe noch `alleKalender`): hier gibt es nichts zu
  // laden — die Fläche bleibt leer, ohne je etwas zu behaupten.
  //
  // UI-R3c (Randfall): Früher kehrte dieser Zweig STUMM zurück. Auf einer
  // Seite, die die Karte erst mit „Antwort da“ einblendet (`GruppeDetail.vue`),
  // blieb sie damit für immer versteckt — es kam nie ein `gesperrt`-Signal.
  // Jetzt gilt „keine Kalender, Antwort da, nicht gesperrt“ und wird gemeldet.
  if (!props.gruppe && !props.alleKalender) {
    verwaltung.value = null
    gesperrt.value = false
    fehler.value = ''
    antwortDa.value = true
    laedt.value = false
    emit('gesperrt', false, true)
    return
  }
  if (!still) {
    laedt.value = true
    fehler.value = ''
  }
  try {
    const antwort = await apiCall(VERWALTUNG, {})
    verwaltung.value = antwort || null
    fehler.value = ''
    gesperrt.value = false
    antwortDa.value = true
    // UI-R2d: „Antwort da“ melden, BEVOR `laedt` fällt — die Seite zeigt die
    // Karte erst mit einer Antwort und blendet sie nie vorher ein (kein
    // Aufblitzen bei 403).
    emit('gesperrt', false, true)
  } catch (e) {
    // 403 = der Server gibt dieser Person keine verwaltbaren Kalender. Das ist
    // kein Fehler, sondern eine Lage: die Karte hat hier nichts zu zeigen und
    // blendet sich aus (Review UI-R2b, Punkt 16). Jeder andere Fehler bleibt
    // sichtbar — mit „Erneut versuchen“.
    // UI-R3c: Das 403 steht als ERSTE Zeile dieses Zweigs — der Quelltext-Test
    // (UI-R2b/P16) prüft genau diese Nachbarschaft (Statusprüfung → `gesperrt`).
    if (Number(e?.status) === 403) {
      gesperrt.value = true
      verwaltung.value = null
      fehler.value = ''
      antwortDa.value = true
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
    antwortDa.value = true
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
 * DES-1b (Review 5): `aria-controls` des Aufklapp-Knopfs braucht die id des
 * Feldes, das er aufklappt. Die id leitet sich aus dem Kalendernamen ab
 * (`op2`, `team-2027`, …) — Doppelpunkte und Leerzeichen würden in einem
 * CSS-Selektor bzw. manchen Vorlesehilfen stören, deshalb werden sie ersetzt.
 */
function freigabenFeldId(name) {
  const sicher = String(name || '').replace(/[^A-Za-z0-9_-]/g, '-')
  return `ke-freigaben-${sicher}`
}

/**
 * Zuordnung aus den KENNUNGEN der Zeile, ohne Namen zu raten: nur ein Name aus
 * `namen` zählt, der zur eigenen Kennung gehört (`G-Chor` → „Chor“). Eine
 * fremde Kennung zeigt sich selbst — sonst trüge sie den Namen dieser Seite.
 * (Die Kalenderverwaltung übergibt gefüllte `namen`; die Gruppenseite lässt es
 * leer, dort gilt `kalenderZeile` mit den Namen der Seite.)
 *
 * Die Vorsilbe („Gemeinde“ / „Gruppe: …“ / „Untergruppe: …“) setzt diese
 * Funktion — die Anlegeorte der Seite nennen ebenfalls nur den reinen Namen.
 */
function zuordnungsText(k) {
  const zeile = k || {}
  if (zeile.untergruppe) return 'Untergruppe: ' + (namen.value[zeile.untergruppe] || zeile.untergruppe)
  if (zeile.gruppe) return 'Gruppe: ' + (namen.value[zeile.gruppe] || zeile.gruppe)
  return 'Gemeinde'
}

/**
 * DES-1: die Unterzeile EINER Kalenderzeile — Zuordnung, Leseregel und
 * „selbstverwaltet“ in einem Satz. Sie stand vorher im nachgebauten Kopf im
 * Kartenkörper; jetzt ist sie die Unterzeile des Kartenkopfs (`DkCard sub`),
 * also derselbe Baustein wie überall.
 */
function kalenderZeileText(k) {
  const zeile = k || {}
  let text = zuordnungsText(zeile)
  if (zeile.gruppe || zeile.untergruppe) {
    text += ' · ' + (zeile.standard_gruppe_lesen ? 'alle Gruppenmitglieder lesen' : 'Lesen nur bei Freigabe')
  }
  if (zeile.selbstverwaltet) text += ' · selbstverwaltet'
  return text
}

/** Hilfesatz der Orts-Auswahl (Gemeinde-Kalender erscheint bei allen). */
const zielHilfe = computed(() => (istGemeindeZiel.value
  ? 'Ein Gemeinde-Kalender gehört keiner Gruppe — er erscheint bei allen, die ihn sehen dürfen.'
  : 'Der Kalender erscheint bei allen, die diese Gruppe sehen.'))

/** Ist der gewählte Ort der Gemeinde-Kalender (dann gibt es die Frage nicht)? */
const istGemeindeZiel = computed(() => gewaehltesZiel()?.art === 'gemeinde')

/**
 * Die Ortsauswahl steht NUR dort, wo es mehr als einen Ort gibt. Sonst nennt
 * der Dialog den einen Ort als Satz — ein Auswahlfeld mit einer Zeile ist
 * eine Frage ohne Wahl (Prinzip: keine Scheinentscheidung), und in der
 * Kalenderverwaltung gibt es oft nur den einen Gemeinde-Kalender.
 */
const nurEinZiel = computed(() => ziele.value.length <= 1)

/** Der eine Ort als Satz, wenn es nichts zu wählen gibt (sonst leer). */
const einzigerOrtText = computed(() => (nurEinZiel.value
  ? `Der Kalender gehört zu: ${ziele.value[0]?.anzeige || ''}`
  : ''))

/**
 * Nach einer Änderung: Freigaben DIESES Kalenders still nachladen.
 *
 * `still` heißt: die Karte bleibt mit ihrem Inhalt stehen (kein Sprung nach
 * oben, kein Skelett); nur die Zahlen werden neu geholt.
 */
async function rechteNachladen(name, meldung) {
  await rechteLaden(name)
  await kontextNachladen()
  if (meldung) showToast(meldung, 'success')
}

/**
 * UI-R3e (SOLL 4): die Liste nach einer Änderung wirklich auffrischen und
 * WARTEN, bis der neue Stand da ist.
 *
 * Besitzt die SEITE die Liste (`:verwaltung`), lädt sie — die Fläche kann den
 * Endpunkt nicht selbst fragen, ohne den geteilten Stand zu umgehen. Sie gibt
 * ihre Lade-Funktion als `nachladen` herein; darauf wird gewartet. Ohne diesen
 * Prop lädt die Fläche wie bisher selbst (`verwaltungLaden({still:true})`,
 * ohne `:verwaltung` ein echter Aufruf).
 *
 * `geaendert` bleibt für Aufrufer, die selbst nachladen (Gruppenseiten).
 */
async function kontextNachladen() {
  if (typeof props.nachladen === 'function') await props.nachladen()
  else await verwaltungLaden({ still: true })
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
  // Die Frage gibt es nur bei Gruppen-/Untergruppen-Kalendern (`anlegeAnfrage`
  // setzt `standard_gruppe_lesen` immer aus dem Formular). Ein Gemeinde-Kalender
  // hat keine Gruppe, an der „alle Mitglieder“ hängen könnte — die Antwort wird
  // deshalb auf `Ja` zurückgesetzt und mitgeschickt; der Server wertet das Feld
  // ohne Gruppe/Untergruppe nicht aus.
  if (ziel.art === 'gemeinde') form.standardGruppeLesen = true

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
    await kontextNachladen()
  } catch (e) {
    // Fachfehler des Servers („Ein Kalender mit dem Namen … gibt es schon.“)
    // stehen im Dialog — der Text bleibt erhalten, nichts wird geleert.
    formFehler.allgemein = sichererFehlertext(e, { text: 'Das Anlegen hat nicht geklappt.' })
  } finally {
    speichert.value = false
  }
}

/** „Kalender anlegen“ für Aufrufer (die Kalenderverwaltung öffnet denselben Dialog). */
defineExpose({ anlegenOeffnen: dialogOeffnen, freigabenFeldId })

// ── Bearbeiten (UI-R3b) ───────────────────────────────────────────────────
const bearbeitenOffen = ref(false)
const bearbeitenSpeichert = ref(false)
/** Die Zeile, die gerade bearbeitet wird (Name = Schlüssel des Kalenders). */
const bearbeitet = ref(null)
const bearbeitenForm = reactive({ titel: '', farbe: '', selbstverwaltet: false })
const bearbeitenFehler = reactive({ allgemein: '', titel: '', farbe: '' })
const schutzBearbeiten = useFormularSchutz(() => (bearbeitenOffen.value
  ? JSON.stringify({
    titel: bearbeitenForm.titel,
    farbe: bearbeitenForm.farbe,
    selbstverwaltet: bearbeitenForm.selbstverwaltet,
  })
  : null))

/** Bearbeiten-Dialog mit dem Stand DIESES Kalenders füllen. */
function bearbeiten(k) {
  if (!k || !k.name) return
  bearbeitet.value = k
  bearbeitenForm.titel = k.titel
  // Der Server liefert eine gültige Farbe (`_kalender_eintrag` setzt sonst die
  // Standardfarbe); `farbe_standard` steht zusätzlich in der Liste. Ein LEERER
  // Wert würde das Farbfeld schwarz öffnen — deshalb nie ein Literal hier.
  bearbeitenForm.farbe = k.farbe || verwaltung.value?.farbe_standard || STANDARD_FARBE
  bearbeitenForm.selbstverwaltet = k.selbstverwaltet === true
  bearbeitenFehler.allgemein = ''
  bearbeitenFehler.titel = ''
  bearbeitenFehler.farbe = ''
  bearbeitenOffen.value = true
  schutzBearbeiten.merken()
}

function bearbeitenSchliessen() {
  if (!schutzBearbeiten.darfSchliessen()) return
  bearbeitenOffen.value = false
}

/** Titel, Farbe und „selbstverwaltet“ per `update_kalender` speichern. */
async function bearbeitenSpeichern() {
  if (bearbeitenSpeichert.value || !bearbeitet.value) return
  const pruefung = pruefeNeuenKalender({ titel: bearbeitenForm.titel, farbe: bearbeitenForm.farbe })
  bearbeitenFehler.titel = pruefung.titel
  bearbeitenFehler.farbe = pruefung.farbe
  bearbeitenFehler.allgemein = ''
  if (!pruefung.ok) return
  bearbeitenSpeichert.value = true
  try {
    const anfrage = aenderungsAnfrage({
      name: bearbeitet.value.name,
      titel: bearbeitenForm.titel,
      farbe: bearbeitenForm.farbe,
      selbstverwaltet: bearbeitenForm.selbstverwaltet,
    })
    await apiCall(AENDERN, anfrage)
    bearbeitenOffen.value = false
    showToast(`Kalender „${anfrage.titel}“ gespeichert.`, 'success')
    await kontextNachladen()
  } catch (e) {
    // 403 = der Server lässt diese Person nicht ändern (`_require_kalender_verwalten`);
    // 417/„gibt es schon“ = Fachfehler. Beides steht IM Dialog, nichts wird geleert.
    bearbeitenFehler.allgemein = verweigerungsText(e, 'bearbeiten')
  } finally {
    bearbeitenSpeichert.value = false
  }
}

// ── Löschen (UI-R3b) ──────────────────────────────────────────────────────
// UX2c (C2 · Prinzip I2): Löschen ist UMKEHRBAR, solange der Zustand VOLLSTÄNDIG
// zurückkommt — also sofort ausführen und „Rückgängig“ anbieten. Ein Kalender
// aus dem Google-Import (`calender_details`) käme ohne diesen Vermerk zurück;
// dann bleibt die Rückfrage (Review 06.11.).
const { mitRueckgaengig } = useRueckgaengigAktion()

async function entfernen(k) {
  if (!k || !k.name || busy.value) return
  if (!vollstaendig('kalender', k)) {
    // UI-R3d/UI-R3c: Es gibt ZWEI Gründe für die Rückfrage — der Google-Import
    // (`calender_details`) und Freigaben/Sichtbarkeit. Der Satz nennt JEDEN
    // Grund, der hier gilt (`loeschRueckfrageText`): vorher nannte er bei
    // beidem nur den Google-Grund, und der Verlust der Freigaben blieb
    // unerwähnt.
    const ok = await bestaetigen({
      titel: 'Kalender löschen?',
      text: loeschRueckfrageText(k),
      aktion: 'Löschen',
      gefahr: true,
    })
    if (!ok) return
    busy.value = busySchluessel('loeschen', k.name)
    try {
      await apiCall(LOESCHEN, loeschAnfrage(k.name))
      // UI-R3f (SOLL 3): erst die frischen Daten, DANN die Meldung — wie im
      // Rückgängig-Zweig. Vorher meldete der Toast das Löschen, während die
      // Zeile mit aktivem Löschen-Knopf noch dastand.
      await kontextNachladen()
      showToast(`Kalender „${k.titel}“ gelöscht.`, 'success')
    } catch (e) {
      // 417 „enthält noch Termine“ / „wird noch verwendet“ kommt als Fachsatz.
      showToast(verweigerungsText(e, 'loeschen'), 'error')
    } finally {
      busy.value = ''
    }
    return
  }
  busy.value = busySchluessel('loeschen', k.name)
  try {
    await apiCall(LOESCHEN, loeschAnfrage(k.name))
    await kontextNachladen()
    await mitRueckgaengig({
      beschreibung: `Kalender „${k.titel}“ gelöscht`,
      zurueck: () => gegenrichtung('kalender', k),
      // UI-R3d (Punkt 2): Nach dem Rückgängig lädt die FLÄCHE ihre Liste — und
      // `geaendert` holt zusätzlich die Daten der SEITE (`verwaltung` in
      // KalenderVerwaltung.vue) neu. Ohne diesen Ruf stünde dort weiterhin der
      // gelöschte Stand.
      danach: kontextNachladen,
      erfolg: `Kalender „${k.titel}“ ist wieder da.`,
    })
  } catch (e) {
    showToast(verweigerungsText(e, 'loeschen'), 'error')
  } finally {
    busy.value = ''
  }
}

onMounted(() => verwaltungLaden())
watch(() => [props.gruppe, props.untergruppe], () => {
  offen.value = ''
  for (const schluessel of Object.keys(rechte)) delete rechte[schluessel]
  verwaltungLaden()
})
/**
 * UI-R3c: Der Aufrufer hat die Liste (neu) geholt — hier NUR übernehmen, kein
 * zweiter Aufruf. Die neue Antwort nach einer Änderung bringt die Fläche also
 * ebenfalls ohne eigene Anfrage auf den Stand (die Seite lädt bei `geaendert`
 * ohnehin nach).
 */
watch(() => props.verwaltung, (neu) => {
  if (neu === undefined || neu === null) return
  verwaltung.value = neu
  fehler.value = ''
  gesperrt.value = false
  antwortDa.value = true
  laedt.value = false
  emit('gesperrt', false, true)
})
</script>

<style scoped>
.ke-wurzel { display: flex; flex-direction: column; gap: var(--sp-4); }
.ke-anlegen { display: flex; justify-content: flex-start; }
.ke-liste { display: flex; flex-direction: column; gap: var(--sp-2); }
/* DES-1 (Review 2): eine Kalenderzeile ist eine FLACHE Gliederung in der Karte
   „Kalender der Gruppe“ — keine Karte in der Karte: kein eigener Schatten,
   keine eigene Rundung, keine getönte Fläche. Sie trennt sich über Abstand,
   wie die SSOT es für Zeilen vorsieht; nur eine Haarlinie hält lange Listen
   lesbar. Farbpunkt und Titel stehen im Kartenkopf des Bausteins (`#vor-titel`
   + `title`/`sub`): der Punkt als Kennzeichen VOR dem Titel.
   DES-1b (Review 2): der Innenabstand kommt AUSSCHLIESSLICH von hier — `flach`
   nimmt Kopf und Körper des Bausteins ihre Karteninnen-Polsterung, die Zeile
   polstert EINMAL (oben/unten), damit Titel und aufgeklapptes Freigaben-Feld
   bündig stehen und in der äußeren Karte nichts doppelt gepolstert wird. */
.ke-zeile {
  box-shadow: none;
  border-radius: 0;
  border: 0;
  background: transparent;
  padding: var(--sp-2) 0;
}
.ke-zeile + .ke-zeile { border-top: var(--rahmen-breite) solid var(--line); }
/* DES-1b (Review 3): KEIN eigener Titelbau mehr — `.ke-titel` (h3 von Hand),
   `.ke-titel-text` (eigene Ellipse + nowrap) sind entfallen. Überschrift,
   Unterzeile, Ellipse und der Handy-Umbruch kommen aus DkCard. */
.ke-farbe {
  width: var(--sp-3);
  height: var(--sp-3);
  border-radius: var(--radius-sm);
  flex: none;
}
.ke-zeile > .dk-ui-card-koerper,
.ke-zeile :deep(.dk-ui-card-koerper) { padding-top: var(--sp-2); }
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
/* UI-R3: der EINE Anlegeort als Satz (statt Auswahlfeld mit einer Zeile). */
.ke-ort { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
</style>
