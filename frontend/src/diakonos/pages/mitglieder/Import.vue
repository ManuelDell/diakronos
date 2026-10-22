<template>
  <section aria-label="Mitglieder importieren" class="mi-bereich">
    <p>
      Eine Liste als CSV-Datei einlesen. Vor dem Übernehmen zeigt der nächste
      Schritt jede Zeile: neu, möglicherweise doppelt oder fehlerhaft.
    </p>

    <DkHint
      variant="info"
      :schritte="['Datei wählen', 'Spalten zuordnen', 'Prüfen und übernehmen']"
      :aktiv="schritt"
    >
      Der Import legt nur fehlerfreie Zeilen an. Nichts wird geschrieben, bevor
      nicht ausdrücklich übernommen wurde.
    </DkHint>

    <DkHint v-if="meldung" variant="err" role="alert">{{ meldung }}</DkHint>

    <!-- Schritt 1: Datei ---------------------------------------------------->
    <DkCard title="1. Datei wählen">
      <DkField
        label="CSV-Datei"
        help="Aus Excel oder Numbers als CSV gespeichert. Semikolon und Komma sind beide möglich."
      >
        <input
          ref="dateiFeld"
          class="dk-ui-eingabe"
          type="file"
          accept=".csv,text/csv,text/plain"
          @change="dateiGewaehlt"
        />
      </DkField>
      <p class="mi-hinweis">
        Höchstens {{ maxZeilen }} Personen und {{ maxKb }} kB je Datei. Größere
        Listen bitte aufteilen.
      </p>
      <p v-if="dateiName" class="mi-datei" role="status">
        <strong>{{ dateiName }}</strong> — {{ zeilenAnzahl }} Zeilen erkannt,
        Trennzeichen „{{ trenner === ';' ? 'Semikolon' : 'Komma' }}“.
      </p>
    </DkCard>

    <!-- Schritt 2: Spalten -------------------------------------------------->
    <DkCard v-if="dateiName" title="2. Spalten zuordnen">
      <p>
        Ordne jeder Angabe die Spalte aus der Datei zu. Bereits erkannte
        Spalten sind vorbelegt — bitte prüfen.
      </p>
      <div class="mi-raster">
        <DkField
          v-for="f in felder"
          :key="f.feld"
          :label="f.label"
          :required="f.pflicht"
          :help="f.pflicht ? 'Pflichtangabe' : 'Kann leer bleiben'"
        >
          <DkSelect
            v-model="zuordnung[f.feld]"
            :options="spaltenOptionen"
            placeholder="— nicht in der Datei —"
          />
        </DkField>
      </div>
      <template #footer>
        <div class="mi-fuss">
          <span v-if="fehlende.length" class="mi-fehlt" role="alert">
            Noch zuordnen: {{ fehlende.join(', ') }}
          </span>
          <span v-else class="mi-bereit">Alle Pflichtangaben zugeordnet.</span>
          <DkButton variant="primary" :loading="prueft" :disabled="fehlende.length > 0" @click="pruefen">
            {{ prueft ? 'Wird geprüft…' : 'Vorschau anzeigen' }}
          </DkButton>
        </div>
      </template>
    </DkCard>

    <!-- Schritt 3: Vorschau ------------------------------------------------->
    <DkCard v-if="vorschau" title="3. Prüfen und übernehmen">
      <p class="mi-zahlen" role="status">
        <DkBadge variant="ok">{{ zusammenfassung.neu }} neu</DkBadge>
        <DkBadge variant="warn">{{ zusammenfassung.dubletten }} möglich doppelt</DkBadge>
        <DkBadge variant="err">{{ zusammenfassung.fehler }} fehlerhaft</DkBadge>
        <span class="mi-gesamt">von {{ zusammenfassung.gesamt }} Zeilen</span>
      </p>

      <DkTable :spalten="spalten" :leer="!zeilen.length" leer-titel="Keine Zeilen in der Datei">
        <tr v-for="z in zeilen" :key="z.zeile">
          <td class="mi-nr">{{ z.zeile }}</td>
          <td>{{ zeilenName(z) }}</td>
          <td class="dk-text-muted">{{ feldAnzeige(z.felder, 'email') }}</td>
          <td><DkBadge :variant="badgeVariant(z.status)">{{ statusWort(z.status) }}</DkBadge></td>
          <td class="dk-text-muted">{{ zeilenHinweis(z) }}</td>
        </tr>
      </DkTable>

      <DkHint v-if="zusammenfassung.dubletten" variant="warn">
        Zeilen, die es schon geben könnte, werden nicht angelegt, solange die
        Auswahl unten auf „überspringen“ steht. Eine E-Mail-Adresse gehört
        aber immer nur zu einer Person: Zeilen mit einer bereits vergebenen
        Adresse lehnt der Server ab, auch wenn sie hier zum Anlegen gewählt
        sind.
      </DkHint>

      <DkField label="Möglicherweise doppelte Personen">
        <DkSelect v-model="dublettenBehandlung" :options="dublettenOptionen" />
      </DkField>

      <DkCheckbox v-if="!dublettenUeberspringen" v-model="bestaetigt">
        Ja, ich habe die doppelten Zeilen geprüft — Zeilen mit gleichem Namen
        (ohne E-Mail-Adresse) trotzdem anlegen.
      </DkCheckbox>

      <p v-if="ergebnis" class="mi-ergebnis" role="status">
        <strong>{{ ergebnis.angelegt }}</strong> angelegt,
        <strong>{{ ergebnis.uebersprungen }}</strong> übersprungen,
        <strong>{{ ergebnis.abgelehnt }}</strong> abgelehnt.
      </p>

      <template #footer>
        <div class="mi-fuss">
          <DkButton variant="ghost" @click="neuStarten">Andere Datei wählen</DkButton>
          <DkButton
            variant="primary"
            :loading="uebernimmt"
            :disabled="!darfUebernehmen"
            @click="uebernehmenJetzt"
          >
            {{ uebernimmt ? 'Wird übernommen…' : 'Jetzt übernehmen' }}
          </DkButton>
        </div>
      </template>
    </DkCard>

    <!-- Muster-Datei -------------------------------------------------------->
    <DkCard title="Muster-Datei">
      <p>
        Zum Ausfüllen am eigenen Rechner. Die erste Zeile ist die Kopfzeile
        (Spaltennamen), darunter steht eine Beispielperson.
      </p>
      <DkButton variant="secondary" @click="musterHerunterladen">Muster-Datei herunterladen</DkButton>
    </DkCard>
  </section>
</template>

<script setup>
/**
 * Mitglieder — Reiter „Import“ (Neuordnung N11).
 *
 * Drei Schritte: Datei wählen → Spalten zuordnen → Vorschau und übernehmen.
 * Alles Schreibende macht der Server (`import_mitglieder_uebernehmen`); diese
 * Seite zeigt nur an, was er zurückmeldet. Die Vorprüfung legt NICHTS an.
 * Bestehende Personen werden über „möglicherweise doppelt“ markiert; angelegt
 * werden sie nur nach ausdrücklicher Bestätigung (Server erwartet
 * `bestaetigt=1`, Vorgabe sonst 0).
 */
import { computed, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { apiCall } from '../../composables/useApi.js'
import {
  IMPORT_FELDER,
  datenzeilen,
  erkenneSpalten,
  ersteZeile,
  fehlendePflichtspalten,
  feldAnzeige,
  musterCsv,
  statusWort,
  zeilenName,
} from '../../components/mitglieder/importPruefung.mjs'
import {
  MAX_IMPORT_BYTES,
  MAX_IMPORT_ZEILEN,
  useMitgliederImport,
} from '../../composables/useMitgliederImport.js'
import DkCard from '../../components/ui/DkCard.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkSelect from '../../components/ui/DkSelect.vue'
import DkCheckbox from '../../components/ui/DkCheckbox.vue'
import DkBadge from '../../components/ui/DkBadge.vue'
import DkTable from '../../components/ui/DkTable.vue'

defineProps({ embedded: Boolean })

const felder = IMPORT_FELDER
const maxZeilen = MAX_IMPORT_ZEILEN
const maxKb = Math.round(MAX_IMPORT_BYTES / 1000)

const { prueft, uebernimmt, vorschau, ergebnis, pruefen: pruefenApi, uebernehmen, zuruecksetzen } =
  useMitgliederImport()

const dateiFeld = ref(null)
const dateiName = ref('')
const kopfzeilen = ref([])
const trenner = ref(';')
const zuordnung = ref({})
const meldung = ref('')
const dublettenBehandlung = ref('ueberspringen')
const bestaetigt = ref(false)

const dublettenOptionen = [
  { value: 'ueberspringen', label: 'Überspringen (empfohlen)' },
  { value: 'anlegen', label: 'Zeilen mit gleichem Namen trotzdem anlegen' },
]

const spaltenOptionen = computed(() => kopfzeilen.value.map(k => ({ value: k, label: k })))
const fehlende = computed(() => fehlendePflichtspalten(zuordnung.value))
const zeilenAnzahl = ref(0)
const dublettenUeberspringen = computed(() => dublettenBehandlung.value !== 'anlegen')

const schritt = computed(() => {
  if (!dateiName.value) return 0
  if (!vorschau.value) return 1
  return 2
})

const zeilen = computed(() => (vorschau.value && vorschau.value.zeilen) || [])
const zusammenfassung = computed(() =>
  (vorschau.value && vorschau.value.zusammenfassung) || { neu: 0, dubletten: 0, fehler: 0, gesamt: 0 })

const spalten = [
  { key: 'zeile', label: 'Zeile' },
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'E-Mail' },
  { key: 'status', label: 'Ergebnis' },
  { key: 'hinweis', label: 'Hinweis' },
]

/** Anlegen ist gesperrt, solange nichts Neues da ist oder die Bestätigung fehlt. */
const darfUebernehmen = computed(() => {
  if (!vorschau.value) return false
  if (!dublettenUeberspringen.value && zusammenfassung.value.dubletten > 0 && !bestaetigt.value) return false
  const anlegbar = zusammenfassung.value.neu
    + (dublettenUeberspringen.value ? 0 : zusammenfassung.value.dubletten)
  return anlegbar > 0
})

function badgeVariant(status) {
  if (status === 'neu') return 'ok'
  if (status === 'dublette') return 'warn'
  return 'err'
}

function zeilenHinweis(z) {
  if (z.status === 'dublette') return dublettenText(z.dublette)
  if (z.status === 'fehler') return (z.fehler || []).join(', ') || 'Zeile nicht lesbar'
  return ''
}

function dublettenText(dublette) {
  if (!dublette) return ''
  const grund = {
    email: 'E-Mail-Adresse gibt es schon',
    // K-c (SEC-c): schon in der Datei vergebene Adressen meldet der Server als
    // Fehlerzeile; der Text bleibt fuer aeltere Vorschauen stehen.
    email_in_datei: 'E-Mail-Adresse steht mehrfach in der Datei',
    name: 'Name gibt es schon',
    name_in_datei: 'Name steht mehrfach in der Datei',
  }[dublette.grund] || 'Sieht aus wie eine bereits vorhandene Person'
  return dublette.vorhanden ? `${grund} (${dublette.vorhanden})` : grund
}

/** Datei einlesen. Groessen- und Zeilenpruefung wie beim Server — der prueft
 *  ohnehin noch einmal; hier wird nur der Weg ueber das Netz gespart. */
async function dateiGewaehlt(ereignis) {
  const datei = ereignis.target.files && ereignis.target.files[0]
  if (!datei) return
  meldung.value = ''
  zuruecksetzen()
  bestaetigt.value = false
  dublettenBehandlung.value = 'ueberspringen'

  if (datei.size > MAX_IMPORT_BYTES) {
    meldung.value = `Die Datei ist zu groß (höchstens ${maxKb} kB). Bitte in kleinere Listen aufteilen.`
    dateiFeld.value.value = ''
    return
  }
  let text = ''
  try {
    text = await datei.text()
  } catch (f) {
    meldung.value = 'Die Datei ließ sich nicht lesen.'
    return
  }
  // Umlaute: Excel speichert deutsche CSV oft in Windows-1252 („ANSI“).
  // Ist der Text voller Ersatzzeichen, wird er neu in Windows-1252 gelesen.
  if ((text.match(/\ufffd/g) || []).length > 0 && typeof TextDecoder !== 'undefined') {
    try {
      text = new TextDecoder('windows-1252').decode(await datei.arrayBuffer())
    } catch (f) { /* dann bleibt der urspruengliche Text */ }
  }
  const { trenner: t, kopf } = ersteZeile(text)
  trenner.value = t
  kopfzeilen.value = kopf
  zuordnung.value = erkenneSpalten(kopf)
  dateiName.value = datei.name
  zeilenAnzahl.value = datenzeilen(text)
  dateiInhalt.value = text
  if (!kopf.length) meldung.value = 'In der Datei wurde keine Kopfzeile gefunden.'
}

// Der Dateiinhalt selbst wird erst beim Prüfen gebraucht; als Ref, damit
// „Andere Datei wählen“ ihn mit zurücksetzt.
const dateiInhalt = ref('')

async function pruefen() {
  if (fehlende.value.length) return
  meldung.value = ''
  try {
    await pruefenApi(dateiInhalt.value, zuordnung.value)
    bestaetigt.value = false
  } catch (e) {
    meldung.value = e.message || 'Die Vorschau konnte nicht erstellt werden.'
  }
}

async function uebernehmenJetzt() {
  if (!darfUebernehmen.value) return
  meldung.value = ''
  try {
    const res = await uebernehmen(dateiInhalt.value, zuordnung.value, {
      dublettenUeberspringen: dublettenUeberspringen.value,
      bestaetigt: bestaetigt.value,
    })
    showToast(`${res.angelegt} Person(en) angelegt.`, 'success')
    // Die eingebettete Liste soll die neuen Personen sofort zeigen — der
    // Rahmen (Bereich.vue) laedt sie beim Wechsel in den Reiter ohnehin neu;
    // hier wird nur der Reiter-Zustand zurueckgesetzt, damit die Vorschau
    // keine veralteten Zahlen zeigt.
    await pruefenApi(dateiInhalt.value, zuordnung.value)
    bestaetigt.value = false
  } catch (e) {
    meldung.value = e.message || 'Der Import konnte nicht übernommen werden.'
  }
}

function neuStarten() {
  zuruecksetzen()
  meldung.value = ''
  dateiName.value = ''
  kopfzeilen.value = []
  zuordnung.value = {}
  zeilenAnzahl.value = 0
  dateiInhalt.value = ''
  bestaetigt.value = false
  dublettenBehandlung.value = 'ueberspringen'
  const feld = dateiFeld.value
  if (feld) feld.value = ''
}

const musterDatei = musterCsv

function musterHerunterladen() {
  const blob = new Blob([musterDatei()], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'mitglieder-muster.csv'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.mi-bereich { display: flex; flex-direction: column; gap: var(--sp-4); }
.mi-hinweis { font-size: var(--fs-sm); color: var(--text-muted); margin-top: var(--sp-2); }
.mi-datei { font-size: var(--fs-sm); color: var(--text); }
.mi-raster {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--sp-3);
}
.mi-fuss {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.mi-fehlt { color: var(--err); font-size: var(--fs-sm); }
.mi-bereit { color: var(--text-muted); font-size: var(--fs-sm); }
.mi-zahlen { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.mi-gesamt { color: var(--text-muted); font-size: var(--fs-sm); }
.mi-nr { color: var(--text-muted); font-size: var(--fs-sm); }
.mi-ergebnis { margin-top: var(--sp-3); }
</style>
