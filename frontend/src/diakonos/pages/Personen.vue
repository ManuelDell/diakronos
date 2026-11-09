<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">
    <!-- UX3b (Entscheidung Manuel): „Personen“ hat vier Reiter — Liste ·
         Anfragen · Datenschutz · Import. Die Verwaltungsreiter sieht nur, wer
         darf; alle anderen sehen die Liste, und die zeigt dann die
         Adressbuch-Sicht (dieselbe Zeile, nur die Felder, die der Server
         freigibt).

         UX3b2: Der Reiter steht in der ADRESSE (#/personen/<reiter>), nicht
         nur im Speicher — ein Lesezeichen öffnet denselben Reiter, und
         „zurück“ führt auf den vorigen. -->
    <DkPageHeader title="Personen" :sub="unterzeile" />

    <!-- UX3j (Entwurf A3, Review-Nacharbeit Punkt 4): EINE Kopfzeile — links
         die Reiterzeile, rechts ihre Werkzeuge („Filter“, Hauptaktion). Die
         Werkzeuge sitzen auf HÖHE der Reiterzeile, nicht in einem eigenen
         Block darüber (A3). Die Einträge sind Links: der Reiter steht in der
         Adresse (#/personen/<reiter>), Lesezeichen und „zurück“ wirken. -->
    <div class="p3-reiterzeile">
      <DkReiter
        v-if="zeigeReiter"
        class="p3-reiter"
        :model-value="aktiverReiter"
        :options="reiterOptionen"
        aria-label="Bereiche von Personen"
      />
      <div v-if="zeigeAktionen" class="p3-aktionen">
        <!-- UX1h/S1 + UX3j (A3, Punkt 3): EIN Ort, EINE Regel.
             „Person anlegen“ steht in JEDEM Reiter an derselben Stelle und
             ist dort der eine Primärknopf — AUSSER der Reiter hat eine eigene
             Hauptaktion (Unterbereiche „Links & QR-Codes“ → „Neuer Link“,
             „Formulare“ → „Neues Formular“): dann ist diese primär und
             „Person anlegen“ sekundär. Pro Ansicht bleibt es bei genau einem
             gefüllten Knopf. -->
        <DkButton v-if="zeigeFilter" variant="secondary" @click="filterZeigen">
          <template #icon><DkSymbol name="filter" :groesse="16" /></template>
          Filter
        </DkButton>
        <DkButton
          v-if="zeigeAnlegenKnopf"
          :variant="anlegenIstHauptaktion ? 'primary' : 'secondary'"
          @click="personAnlegen"
        >
          <template #icon><DkSymbol name="person-plus" :groesse="16" /></template>
          Person anlegen
        </DkButton>
        <!-- Hauptaktion des sichtbaren Unterbereichs (nur mit eigenem
             Bedarf): dieselbe Zeile, kein zweiter Kopf. -->
        <DkButton v-if="unterbereichHauptaktion === 'link'" variant="primary" @click="linkAnlegen">
          <template #icon><DkSymbol name="hinzufuegen" :groesse="16" /></template>
          Neuer Link
        </DkButton>
        <DkButton v-else-if="unterbereichHauptaktion === 'formular'" variant="primary" @click="formularAnlegen">
          <template #icon><DkSymbol name="hinzufuegen" :groesse="16" /></template>
          Neues Formular
        </DkButton>
      </div>
    </div>

    <!-- Zweite, kleinere Ebene: die Unterbereiche von „Anfragen“ — direkt
         unter der Reiterzeile als kleiner Segmentschalter (Punkt 3 der
         Nacharbeit), dieselbe Adresse wie bisher
         (#/personen/anfragen[/<unter>]). -->
    <DkReiter
      v-if="zeigeUnterreiter"
      class="p3-unterreiter"
      klein
      segment
      :model-value="aktiverUnterbereich"
      :options="unterReiterOptionen"
      aria-label="Bereiche von Anfragen"
    />

    <!-- ── Liste (Admins: Mitgliederliste, alle anderen: Adressbuch-Sicht) ── -->
    <template v-if="aktiverReiter === 'liste'">
      <div class="p3-werkzeuge">
        <div class="dk-toolbar-search">
          <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="suchbegriff"
            type="search"
            aria-label="Personen durchsuchen"
            placeholder="Nach Name, E-Mail oder Ort suchen…"
            @input="sucheGeaendert"
          />
        </div>

        <!-- UX3b2 (Befund 1): Die Verwaltungsfunktionen der früheren
             Mitgliederseite sind wieder da — Statusfilter, „persönliche Daten
             zeigen“, Sortierung, Karten/Tabelle und die wartenden Konten.
             Sie erscheinen nur für Mitgliederadministratoren; für alle
             anderen ist die Liste die Freigabe-Sicht (kein Datenzuwachs). -->
        <DkSegment
          v-if="verwaltung"
          :model-value="statusFilter"
          :options="filterOptionen"
          aria-label="Status-Filter"
          @update:model-value="statusFiltern"
        />

        <DkButton
          v-if="verwaltung"
          variant="secondary"
          size="md"
          :aria-pressed="zeigePersoenlicheDatenWert ? 'true' : 'false'"
          :title="datenschalterTitel"
          @click="persoenlicheDatenUmschalten"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" /><circle cx="12" cy="12" r="3" />
          </svg>
          {{ datenschalterText(zeigePersoenlicheDatenWert) }}
        </DkButton>

        <DkButton
          v-if="verwaltung"
          variant="ghost"
          size="md"
          :title="'Sortierung: ' + sortierBeschriftung(sortOrder)"
          @click="sortierungUmschalten"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          {{ sortierBeschriftung(sortOrder) }}
        </DkButton>

        <DkSegment
          v-if="ansichten"
          :model-value="form"
          :options="ansichten"
          aria-label="Ansicht"
          @update:model-value="ansichtWaehlen"
        />

        <span class="p3-spacer" />

        <!-- Export gehört zur Liste (der Server exportiert die ganze
             gefilterte Liste) — nur für Mitgliederadministratoren. -->
        <DkButton
          v-if="verwaltung"
          variant="secondary"
          :loading="exportLaeuft"
          @click="exportieren"
        >{{ exportLaeuft ? 'Exportiere…' : 'Export' }}</DkButton>
      </div>

      <PersonenListe
        :zeilen="zeilen"
        :form="form"
        :laedt="laedt"
        :fehler="fehler"
        :sucht="sucht"
        :gesamt="gesamt"
        :seite="seite"
        :seiten="seiten"
        :darf-anlegen="istAdmin"
        :verwaltung="verwaltung"
        :quelle="quelle"
        :persoenlich="persoenlicheAngefordert"
        @anlegen="personAnlegen"
        @blaettern="blaettern"
        @erneut="laden"
      />

      <!-- UX3b2 (Befund 1): wartende Konten (Konto ohne Mitglied) — dieselbe
           Karte wie auf der früheren Mitgliederseite, sie darf nicht am
           Einbetten hängen. Nur für Mitgliederadministratoren. -->
      <WartendeKontenKarte v-if="verwaltung" class="p3-wartende" />
    </template>

    <!-- ── Anfragen (nur mit Recht) ──────────────────────────────────────── -->
    <!-- UX3j: Der Unterbereich kommt aus der ADRESSE (zweite Reiterzeile oben);
         die Seite selbst bringt keinen zweiten Umschalter mit. Die Hauptaktion
         des Unterbereichs („Neuer Link“ / „Neues Formular“) steht im
         Seitenkopf und ruft die vorhandenen Dialoge hier an (Template-Ref). -->
    <Registrierung
      v-else-if="aktiverReiter === 'anfragen'"
      ref="anfragenInhalt"
      embedded
      class="p3-inhalt"
      :unterbereich="aktiverUnterbereich"
    />

    <!-- ── Datenschutz (nur mit Recht) ───────────────────────────────────── -->
    <Datenschutz v-else-if="aktiverReiter === 'datenschutz'" embedded class="p3-inhalt" />

    <!-- ── Import (nur mit Recht) ────────────────────────────────────────── -->
    <Import v-else-if="aktiverReiter === 'import'" embedded class="p3-inhalt" />
    <!-- Anlegen: EIN Dialog für alle Rollen (derselbe wie im
         Mitglieder-Bereich) — keine zweite Maske. -->
    <MitgliedHinzufuegenDialog
      v-model="hinzufuegenOffen"
      :gruppen="gruppenAuswahl"
      @angelegt="nachAnlegen"
    />
  </div>
</template>

<script setup>
/**
 * Personen — EIN Bereich für Mitglieder UND Adressbuch (UX3b, Entscheidung
 * Manuel 2026-11-03: „zusammenlegen, Ansicht je Rolle“).
 *
 * Rollen (kein Datenzuwachs, Datenschutz zuerst):
 *  • Mitgliederadministrator: Reiter Liste · Anfragen · Datenschutz · Import.
 *    Die Liste kommt aus `get_mitglieder_liste` — dieselbe Quelle wie bisher,
 *    persönliche Daten weiterhin nur nach bewusstem Anzeigen serverseitig.
 *  • Alle anderen: EINE Ansicht „Personen“ mit der Adressbuch-Sicht. Die
 *    Quelle ist `get_adressbuch` (B2: `adressbuch_sichtbarkeit` streng,
 *    fail-closed) — es werden KEINE Felder zusätzlich geliefert. Eigene Daten
 *    zeigt der Server vollständig (eigenes Profil).
 *
 * UX3b2 (Review UX3b): Die zusammengelegte Liste hatte die Funktionen der
 * früheren Mitgliederseite verloren. Sie sind hier wieder angebunden —
 * Statusfilter, „persönliche Daten zeigen“, Status-/Gruppenspalten,
 * Sortierung, Karten/Tabelle und die Karte „wartende Konten“ — und zwar über
 * die EINE Darstellung `PersonenListe.vue` statt einer zweiten Umsetzung.
 * Zusätzlich: die Form der Liste hängt an der GESAMTZAHL (nicht an der
 * aktuellen Seite), die Fußzeile steht außerhalb der Tabelle (am Handy
 * sichtbar), und die Adressbuch-Sicht bekommt keine erfundene Seitenzahl.
 *
 * Warum die Liste nicht mehr die Mitglieder-Seite einbettet: die Seite muss
 * die QUELLE je Rolle wählen. Die Darstellung ist EIN Baustein
 * (components/personen/PersonenListe.vue) für beide Quellen, damit Tabelle,
 * Karten, „E-Mail verborgen“ und Blättern nicht zweimal gebaut sind.
 */
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { useSession } from '../composables/useSession.js'
import { showToast } from '../composables/useToast.js'
import { navigate } from '../router.js'
import { aktionsfehler, fehlertext } from '../../shared/fehlertexte.js'
import {
  personenQuelle, zeileAusListe, zeileAusAdressbuch, seitenzahl,
} from '../composables/personenZeilen.mjs'
import {
  ansichtOptionen, datenschalterText, listenFormFuer, naechsteSortierung,
  persoenlicheDatenAnfordern, sortierBeschriftung, statusFilterOptionen,
  verwaltungSichtbar, zielSeite, statusAusAdresse, adresseMitStatus,
} from '../composables/personenVerwaltung.mjs'
import {
  personenReiter, personenAnfragenReiter, personenReiterAusHash,
  anfragenUnterbereichAusHash,
} from '../menue.js'
import { anfragenZaehler } from '../composables/useVerwaltung.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkReiter from '../components/ui/DkReiter.vue'
import DkSegment from '../components/ui/DkSegment.vue'
import DkSymbol from '../components/ui/DkSymbol.vue'
import PersonenListe from '../components/personen/PersonenListe.vue'
import WartendeKontenKarte from '../components/WartendeKontenKarte.vue'
// Das Anlege-Formular ist EIN Dialog für alle Rollen (Rahmen und Liste öffnen
// denselben); er lebt beim Mitglieder-Bereich.
import MitgliedHinzufuegenDialog from '../components/mitglieder/MitgliedHinzufuegenDialog.vue'

const Registrierung = defineAsyncComponent(() => import('./Registrierung.vue'))
const Datenschutz = defineAsyncComponent(() => import('./mitglieder/Datenschutz.vue'))
const Import = defineAsyncComponent(() => import('./mitglieder/Import.vue'))

const { isAdmin } = useSession()
const istAdmin = computed(() => isAdmin.value === true)
/** Verwaltungsfunktionen nur für Mitgliederadministratoren (fail closed). */
const verwaltung = computed(() => verwaltungSichtbar(isAdmin.value === true))

// ── Reiter ──────────────────────────────────────────────────────────────────
// Reihenfolge des Entwurfs A3: Liste · Anfragen · Datenschutz · Import.
// Die Einträge (Beschriftung, Adresse, Kennzahl, Recht) stehen EINMAL in
// menue.js (`MITGLIEDER_REITER`, `personenReiter`) — die Reiterzeile, der
// Rechte-Guard und die Tests lesen dieselbe Quelle.
// Für Nicht-Admins bleibt EINE Ansicht übrig — dann steht keine Reiterleiste
// (ein Reiter mit einem Eintrag ist keine Wahl).
const reiterOptionen = computed(() => personenReiter({
  istAdmin: istAdmin.value === true,
  anfragenZahl: anfragenZahl.value,
}))
const unterReiterOptionen = computed(() => personenAnfragenReiter({
  istAdmin: istAdmin.value === true,
}))
/** Zeigt dieser Reiter die zweite Ebene? (fertiger Wahrheitswert — in der
 *  Vorlage werden Refs in Ausdrücken nicht ausgepackt.) */
const zeigeUnterreiter = computed(
  () => aktiverReiter.value === 'anfragen' && unterReiterOptionen.value.length > 1,
)
/** Mehr als ein Reiter = es gibt eine Wahl (sonst keine Leiste). */
const zeigeReiter = computed(() => reiterOptionen.value.length > 1)

/** Reiter aus der Adresse (`#/personen/<reiter>`), sonst „liste“. */
function reiterAusAdresse() {
  if (typeof window === 'undefined') return 'liste'
  // Unbekannte Werte (und Reiter ohne Recht) fallen auf die Liste zurück —
  // kein leerer Bildschirm über einer getippten Adresse.
  return personenReiterAusHash(window.location.hash, { istAdmin: istAdmin.value === true })
    || 'liste'
}

/** Unterbereich aus der Adresse (`#/personen/anfragen[/<unter>]`). */
function unterbereichAusAdresse() {
  if (typeof window === 'undefined') return 'anfragen'
  return anfragenUnterbereichAusHash(window.location.hash)
}

const aktiverReiter = ref(reiterAusAdresse())
const aktiverUnterbereich = ref(unterbereichAusAdresse())
/** Die Adresse ist die Wahrheit: jeder Wechsel (auch „zurück“) setzt BEIDE
 *  Ebenen — Reiter und Unterbereich kommen aus derselben Adresse. */
function adresseGeaendert() {
  const reiter = reiterAusAdresse()
  const unter = unterbereichAusAdresse()
  if (reiter !== aktiverReiter.value) aktiverReiter.value = reiter
  if (unter !== aktiverUnterbereich.value) aktiverUnterbereich.value = unter
  // UX3f: „Person anlegen“ der Befehlspalette kommt als `#/personen?anlegen=1`
  // — auch wenn der Bereich schon offen ist (dann wechselt keine Seite).
  anlegeWunschAusAdresse()
}
// Die Rolle steht beim Aufbau fest; wechselt sie (z. B. Identitätswechsel im
// Devmodus), wird ein Reiter ohne Recht zur Liste.
watch(istAdmin, () => {
  if (!reiterOptionen.value.some(r => r.value === aktiverReiter.value)) aktiverReiter.value = 'liste'
})

const unterzeile = computed(() => {
  if (aktiverReiter.value === 'anfragen') {
    if (aktiverUnterbereich.value === 'links') return 'Registrierungslinks und QR-Codes teilen'
    if (aktiverUnterbereich.value === 'formulare') return 'Anmeldeformulare anlegen und pflegen'
    return 'Neue Anmeldungen prüfen und aufnehmen'
  }
  if (aktiverReiter.value === 'datenschutz') return 'Einwilligungen und Löschungen der Gemeinde'
  if (aktiverReiter.value === 'import') return 'Personen aus einer CSV-Datei einlesen'
  return istAdmin.value
    ? 'Alle Personen der Gemeinde'
    : 'Kontaktdaten der Gemeinde'
})

// ── Kopfzeile: Kennzahl und Hauptaktion ─────────────────────────────────────
/** Kennzahl offener Anfragen — DERSELBE Stand wie in der Seitenleiste
 *  (useVerwaltung.js, eine Abfrage; die Seitenleiste hält den Takt). */
const anfragenZahl = anfragenZaehler

/** Unterbereiche von „Anfragen“, die ihre EIGENE Hauptaktion haben. */
const UNTERBEREICH_HAUPTAKTIONEN = { links: 'link', formulare: 'formular' }
/** Welche Hauptaktion trägt der sichtbare Unterbereich? (`''` = keine) */
const unterbereichHauptaktion = computed(() => (aktiverReiter.value === 'anfragen'
  ? (UNTERBEREICH_HAUPTAKTIONEN[aktiverUnterbereich.value] || '')
  : ''))

/**
 * UX1h/S1: Der Kopf trägt GENAU EINEN gefüllten Knopf. „Person anlegen“
 * bleibt überall, wo Anlegen die Hauptsache ist (Liste, Anfragen, Datenschutz,
 * Import — dort gibt es keine zweite Anlege-Tätigkeit); in den Unterbereichen
 * „Links & QR-Codes“ und „Formulare“ ist deren eigene Aktion („Neuer Link“ /
 * „Neues Formular“) primär, „Person anlegen“ daneben sekundär.
 */
const anlegenIstHauptaktion = computed(() => !unterbereichHauptaktion.value)

// ── Liste ───────────────────────────────────────────────────────────────────
const quelle = computed(() => personenQuelle(istAdmin.value))
const PRO_SEITE = 20

const zeilen = ref([])
const laedt = ref(false)
const fehler = ref('')
const fehlerGrund = ref(null)
const gesamt = ref(0)
const seite = ref(1)
const suchbegriff = ref('')
// Startfilter aus der Adresse (Kachel „#/personen/liste?status=Mitglied“).
const statusFilter = ref(typeof window === 'undefined' ? '' : statusAusAdresse(window.location.hash))
const sortOrder = ref('asc')
/** Schalter der Ansicht („persönliche Daten zeigen“): der Server liefert die
 *  persönlichen Felder erst, wenn er an ist (fail closed auf beiden Seiten).
 *  Ein Name auf oberster Ebene (der Test greift ihn so ab) — kein Objekt mit
 *  Feld, das die Vorlage nicht auspacken würde. */
const zeigePersoenlicheDatenWert = ref(false)
const statusZaehler = ref({})
const gesamtAlle = ref(0)
/** Gewählte Ansicht (null = nach Gesamtzahl, Entwurf A3). */
const ansicht = ref(null)

const persoenlicheAngefordert = computed(
  () => persoenlicheDatenAnfordern(istAdmin.value === true, zeigePersoenlicheDatenWert.value),
)
const seiten = computed(() => seitenzahl(gesamt.value, PRO_SEITE))
const sucht = computed(() => Boolean(String(suchbegriff.value || '').trim()))

/** Form der Liste nach GESAMTZAHL (Befund 2) — nicht nach der Seite. */
const form = computed(() => listenFormFuer({ gesamt: gesamt.value, wunsch: ansicht.value }))
/** Am Handy zeigen die Karten (dieselbe Grenze wie im Baustein: 720 px). */
const schmal = ref(false)
const ansichten = computed(() => ansichtOptionen({
  istAdmin: istAdmin.value === true,
  schmal: schmal.value,
}))

const filterOptionen = computed(() => statusFilterOptionen({
  statusZaehler: statusZaehler.value,
  gesamtAlle: gesamtAlle.value,
}))
const datenschalterTitel = computed(() => (persoenlicheAngefordert.value
  ? 'Telefon, Adresse und Geburtstag werden jetzt geladen'
  : 'Telefon, Adresse und Geburtstag werden nicht geladen'))

/** Nur die Mitgliederliste kennt einen Status; die Adressbuch-Sicht nicht
 *  (deren Zeilen kommen ohne Status) — die Ansicht fragt ihn also nur dort
 *  ab, wo er existiert. */
async function laden() {
  if (laedt.value) return
  laedt.value = true
  fehler.value = ''
  fehlerGrund.value = null
  const suche = String(suchbegriff.value || '').trim()
  try {
    if (quelle.value === 'adressbuch') {
      // B2: Die Freigabe-Sicht kennt keinen Blätter-Parameter; sie liefert
      // höchstens 200 Einträge. Gesucht wird serverseitig (umlautfest).
      const antwort = await apiCall('diakronos.diakonos.api.mitglieder.get_adressbuch', {
        suche: suche || undefined,
      })
      zeilen.value = (antwort?.data || []).map(zeileAusAdressbuch)
      gesamt.value = zeilen.value.length
      seite.value = 1
    } else {
      const antwort = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste', {
        start: (seite.value - 1) * PRO_SEITE,
        limit: PRO_SEITE,
        suche: suche || undefined,
        status: statusFilter.value || undefined,
        sort_by: 'nachname',
        sort_order: sortOrder.value,
        // UX3b2 (Befund 1): nur auf ausdrückliche Anforderung — sonst stand
        // in jeder Zeile „E-Mail verborgen“, obwohl das MITGLIED sie gar
        // nicht verbirgt. Der Server prüft dieselbe Regel erneut.
        persoenliche_daten: persoenlicheAngefordert.value,
      })
      // UX3b2: Ohne Anforderung NUR die Felder durchreichen, die die Liste
      // wirklich braucht. Der Server setzt die persönlichen Felder schon auf
      // `null` (W7) — doppelt gehalten, weil die Zeilenform dieselbe bleibt,
      // egal welche Fassung der Server gerade schickt (fail closed).
      const roh = antwort?.data || []
      zeilen.value = roh.map((eintrag) => {
        const zeile = zeileAusListe(eintrag)
        if (persoenlicheAngefordert.value) return zeile
        return { ...zeile, email: null, telefonnummer: null, geburtstag: null, ort: '' }
      })
      gesamt.value = Number(antwort?.total) || 0
      if (antwort?.status_zaehler && typeof antwort.status_zaehler === 'object') {
        statusZaehler.value = { ...antwort.status_zaehler }
      }
      if (typeof antwort?.gesamt_alle === 'number') gesamtAlle.value = antwort.gesamt_alle
    }
  } catch (err) {
    fehler.value = aktionsfehler('laden', err)
    fehlerGrund.value = err
    zeilen.value = []
    gesamt.value = 0
  } finally {
    laedt.value = false
  }
}

/** Text unter dem Fehlerzustand: was jetzt hilft (I4), aus dem Katalog. */
const fehlerHinweis = computed(() => {
  if (!fehler.value) return ''
  return fehlertext(fehlerGrund.value)
})

/** Suche entprellt (300 ms) — sonst eine Abfrage je Tastendruck. */
let suchUhr = null
function sucheGeaendert() {
  clearTimeout(suchUhr)
  suchUhr = setTimeout(() => {
    seite.value = 1
    laden()
  }, 300)
}

/** Statusfilter: erneutes Anklicken des aktiven Status wählt ihn ab („Alle“). */
function statusFiltern(wert) {
  const neu = wert === statusFilter.value ? '' : wert
  if (neu === statusFilter.value) return
  statusFilter.value = neu
  // Filter im aktuellen Verlaufseintrag (kein neuer): „zurück“ aus dem
  // Detail stellt die Liste mit diesem Filter wieder her.
  try {
    window.history.replaceState(null, '', adresseMitStatus(window.location.hash, neu))
  } catch { /* ohne Verlauf (Test/SSR) bleibt nur der Filter */ }
  seite.value = 1
  laden()
}

/** Sortierung A–Z ⇄ Z–A — der Server sortiert, die Seite lädt neu. */
function sortierungUmschalten() {
  sortOrder.value = naechsteSortierung(sortOrder.value)
  seite.value = 1
  laden()
}

/** Ansicht (Tabelle/Karten) wählen — sie hat Vorrang vor der Regel nach
 *  Gesamtzahl, bleibt aber eine reine Anzeige-Wahl. */
function ansichtWaehlen(wert) {
  if (wert !== 'tabelle' && wert !== 'karten') return
  ansicht.value = wert
}

/** Persönliche Daten: der Server liefert sie erst auf diese Anforderung — die
 *  Liste wird danach neu geladen (sonst stünden die alten, leeren Zeilen da). */
function persoenlicheDatenUmschalten() {
  zeigePersoenlicheDatenWert.value = !zeigePersoenlicheDatenWert.value
  laden()
}

function blaettern(ziel) {
  const neu = zielSeite(seite.value, ziel, seiten.value)
  if (neu === null) return
  seite.value = neu
  laden()
}

// Die Rolle steht beim Aufbau fest; wechselt sie (z. B. Identitätswechsel im
// Devmodus), wird die Quelle neu gewählt und die Liste neu geladen.
watch(quelle, () => {
  seite.value = 1
  laden()
})
watch(aktiverReiter, (wert) => {
  if (wert === 'liste') laden()
})

function breiteMessen() {
  if (typeof window === 'undefined') return
  schmal.value = window.innerWidth <= 720
}

onMounted(() => {
  breiteMessen()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', breiteMessen)
    window.addEventListener('hashchange', adresseGeaendert)
  }
  laden()
  anlegeWunschAusAdresse()
})

/**
 * UX3f: Die Befehlspalette bietet „Person anlegen“ als `#/personen?anlegen=1`.
 * Der Schalter wird EINMAL gelesen und aus der Adresse entfernt, sonst öffnete
 * jedes Neuladen das Formular erneut. Ohne Recht bleibt es beim Seitenwechsel
 * (der Knopf erscheint dann gar nicht erst).
 */
function anlegeWunschAusAdresse() {
  let werte
  try {
    werte = new URLSearchParams(String(location.hash || '').split('?')[1] || '')
  } catch (_) {
    return
  }
  if (werte.get('anlegen') !== '1') return
  const rest = String(location.hash || '').split('?')[0] || '#/personen'
  try {
    history.replaceState(null, '', rest)
  } catch (_) {
    // s. Kalender.vue — der Dialog öffnet trotzdem einmal.
  }
  if (!istAdmin.value) return
  personAnlegen()
}

onBeforeUnmount(() => {
  clearTimeout(suchUhr)
  if (typeof window === 'undefined') return
  window.removeEventListener('resize', breiteMessen)
  window.removeEventListener('hashchange', adresseGeaendert)
})

// ── Anlegen ─────────────────────────────────────────────────────────────────
const hinzufuegenOffen = ref(false)
const gruppenAuswahl = ref([])
/** UX3j: „Person anlegen“ steht in ALLEN Reitern an derselben Stelle (Punkt 3
 *  der Karte) — nur für Mitgliederadministratoren (der Server prüft erneut). */
const zeigeAnlegenKnopf = computed(() => istAdmin.value === true)

/**
 * UX3j-Nacharbeit (Punkt 4): „Filter“ erscheint nur dort, wo er wirkt —
 * also in den Ansichten mit einem Filter (Liste mit Status, „Anfragen“ mit
 * Status, „Datenschutz“ mit Stand). „Links & QR-Codes“, „Formulare“ und
 * „Import“ haben keinen Filter; dort kein Knopf, der ins Leere greift.
 */
const REITER_MIT_FILTER = ['liste', 'anfragen', 'datenschutz']

/** Wo der Filterknopf wirkt (Punkt 4): nur in „anfragen“, wenn nicht der
 *  Unterbereich „Links“/„Formulare“ gewählt ist — dort gibt es keinen
 *  Statusfilter. */
const zeigeFilter = computed(() => {
  if (!zeigeAktionen.value) return false
  if (aktiverReiter.value === 'anfragen') return aktiverUnterbereich.value === 'anfragen'
  return REITER_MIT_FILTER.includes(aktiverReiter.value)
})

/** Werkzeugzeile überhaupt zeigen (Aktionen rechts auf Höhe der Reiter). */
const zeigeAktionen = computed(() => zeigeReiter.value || zeigeAnlegenKnopf.value)

/** Hauptaktionen der Anfragen-Unterbereiche reicht der Rahmen in den Inhalt
 *  durch: die Knöpfe stehen im EINEN Seitenkopf (kein zweiter Kopf) und
 *  öffnen die vorhandenen Dialoge der Anfragen-Seite. */
const anfragenInhalt = ref(null)
function linkAnlegen() {
  const ziel = anfragenInhalt.value
  if (ziel && typeof ziel.linkOeffnen === 'function') ziel.linkOeffnen()
}
function formularAnlegen() {
  const ziel = anfragenInhalt.value
  if (ziel && typeof ziel.formularOeffnen === 'function') ziel.formularOeffnen()
}

/** Der Filterknopf der Kopfzeile führt zum Filter des Reiters: in der Liste
 *  zum Statusfilter, in „Anfragen“ zum Statusfilter über der Tabelle, in
 *  „Datenschutz“ zum Stand. Er wird nur gezeichnet, wo es ihn gibt
 *  (`zeigeFilter`, Punkt 4). */
function filterZeigen() {
  if (typeof document === 'undefined') return
  const ziele = aktiverReiter.value === 'liste'
    ? ['.p3-werkzeuge [aria-label="Status-Filter"]', '.p3-werkzeuge input']
    : aktiverReiter.value === 'datenschutz'
      ? ['.ds-filter [role="tablist"]', '.ds-filter input']
      : ['.reg-statusfilter [role="tablist"]']
  const feld = ziele
    .map(sel => document.querySelector(sel))
    .find(el => el != null)
  if (!feld) return
  try { feld.focus({ preventScroll: true }) } catch (_) { feld.focus() }
  feld.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

async function gruppenLaden() {
  if (!istAdmin.value) return
  try {
    const res = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    gruppenAuswahl.value = res?.gruppen_auswahl || []
  } catch (err) {
    gruppenAuswahl.value = []
    console.error('Gruppenauswahl nicht geladen:', err)
  }
}

async function personAnlegen() {
  // Ohne Recht führt der Weg in die Anfragen (dort prüft die Verwaltung) —
  // kein zweites Formular, keine Halbwahrheit.
  if (!istAdmin.value) return
  await gruppenLaden()
  hinzufuegenOffen.value = true
}

function nachAnlegen() {
  laden()
}

// ── Export (nur Mitgliederadministratoren) ──────────────────────────────────
const exportLaeuft = ref(false)
async function exportieren() {
  if (exportLaeuft.value) return
  exportLaeuft.value = true
  try {
    const antwort = await apiCall('diakronos.diakonos.api.mitglieder.exportiere_mitglieder_csv', {
      suche: String(suchbegriff.value || '').trim() || undefined,
      status: statusFilter.value || undefined,
      // Dieselbe Filterung wie die Liste vor dem Auge — inklusive der
      // persönlichen Spalten nur, wenn sie angezeigt werden.
      persoenliche_daten: persoenlicheAngefordert.value === true,
    })
    const blob = new Blob(['\ufeff' + (antwort?.csv || '')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = antwort?.dateiname || 'mitglieder.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast(`${antwort?.anzahl ?? 0} Person(en) exportiert`, 'success')
  } catch (err) {
    showToast(aktionsfehler('aktion', err, { was: 'Der Export hat nicht geklappt.' }), 'error')
  } finally {
    exportLaeuft.value = false
  }
}

// Nicht genutzt, hält aber die Adressen-Schreibweise an EINER Stelle: das
// Profil ist die Detailseite (kein zweites Ziel).
function profilUrl(name) {
  return '#/mitglied/' + encodeURIComponent(String(name || ''))
}
defineExpose({
  laden, profilUrl, navigate, fehlerHinweis,
  ansichtWaehlen, sortierungUmschalten, statusFiltern,
  persoenlicheDatenUmschalten, form, filterZeigen, zeigeFilter,
  linkAnlegen, formularAnlegen,
})
</script>

<style scoped>
/* UX3j (A3 + Nacharbeit Punkt 4): EINE Kopfzeile — Reiterzeile links, ihre
   Werkzeuge rechts auf DERSELBEN Höhe (Unterkante der Reiter = Unterkante der
   Knöpfe). Am Handy rutschen die Werkzeuge unter die Reiter (die Reiter
   scrollen dort waagerecht, Punkt 5). */
.p3-reiterzeile {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--gap);
  flex-wrap: wrap;
  margin-bottom: var(--sp-3);
}
.p3-reiter,
.p3-unterreiter { margin-bottom: 0; }
/* Die zweite Ebene schließt die Kopfzone ab — der Inhalt folgt mit dem
   normalen Abstand darunter, bündig links (Punkt 6). */
.p3-unterreiter { margin-bottom: var(--sp-3); }
/* Die Reiterzeile nimmt den freien Platz; `min-width: 0` + `align-self`
   halten sie in der Zeile (ohne das dehnt der Scroll-Container die Zeile auf
   die Höhe des Inhalts). */
.p3-reiterzeile .p3-reiter {
  flex: 1 1 auto;
  min-width: 0;
  align-self: flex-end;
  margin-bottom: 0;
}
.p3-aktionen {
  display: flex;
  align-items: center;
  align-self: flex-end;
  gap: var(--sp-2);
  flex-wrap: wrap;
  /* Die Werkzeuge stehen auf der Unterkante der Reiterzeile (Punkt 4) und
     sind genau einen Knopf hoch — kein Polster darüber oder darunter. */
  padding-bottom: 0;
}

/* Punkt 6: Inhalt bündig mit der Reiterzeile — kein Einzug darüber (die
   Inhaltsseiten bringten sonst ihren eigenen Oberabstand mit). */
.p3-inhalt { margin-top: 0; }

.p3-werkzeuge {
  display: flex;
  align-items: center;
  gap: var(--gap);
  flex-wrap: wrap;
  margin-bottom: var(--sp-4);
}
.p3-werkzeuge .dk-toolbar-search { flex: 1 1 260px; min-width: 0; }
.p3-spacer { flex: 1; }
.p3-wartende { margin-top: var(--sp-4); }

@media (max-width: 720px) {
  /* Werkzeuge nehmen die zweite Zeile ein; die Reiterzeile bleibt die erste. */
  .p3-aktionen { width: 100%; justify-content: flex-start; padding-bottom: 0; }
}
</style>
