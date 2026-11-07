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
    <DkPageHeader title="Personen" :sub="unterzeile">
      <template #actions>
        <DkButton
          v-if="zeigeAnlegenKnopf"
          variant="primary"
          @click="personAnlegen"
        >Person anlegen</DkButton>
      </template>
    </DkPageHeader>

    <DkSegment
      v-if="reiter.length > 1"
      class="p3-reiter"
      :model-value="aktiverReiter"
      :options="reiter"
      aria-label="Bereiche von Personen"
      @update:model-value="reiterWechseln"
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
    <Registrierung v-else-if="aktiverReiter === 'anfragen'" embedded />

    <!-- ── Datenschutz (nur mit Recht) ───────────────────────────────────── -->
    <Datenschutz v-else-if="aktiverReiter === 'datenschutz'" embedded />

    <!-- ── Import (nur mit Recht) ────────────────────────────────────────── -->
    <Import v-else-if="aktiverReiter === 'import'" embedded />
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
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkSegment from '../components/ui/DkSegment.vue'
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
// Für Nicht-Admins bleibt EINE Ansicht übrig — dann steht keine Reiterleiste
// (ein Reiter mit einem Eintrag ist keine Wahl).
const REITER = [
  { id: 'liste', label: 'Liste' },
  { id: 'anfragen', label: 'Anfragen', rolle: 'admin' },
  { id: 'datenschutz', label: 'Datenschutz', rolle: 'admin' },
  { id: 'import', label: 'Import', rolle: 'admin' },
]
const reiter = computed(() => REITER
  .filter(r => r.rolle !== 'admin' || istAdmin.value)
  .map(r => ({ value: r.id, label: r.label })))

/** Reiter aus der Adresse (`#/personen/<reiter>`), sonst „liste“. */
function reiterAusAdresse() {
  if (typeof window === 'undefined') return 'liste'
  const hash = String(window.location.hash || '')
  const pfad = hash.split('?')[0].replace(/\/+$/, '')
  const treffer = /^#\/personen\/([^/]+)$/.exec(pfad)
  const wert = treffer ? treffer[1] : ''
  // Unbekannte Werte (und Reiter ohne Recht) fallen auf die Liste zurück —
  // kein leerer Bildschirm über einer getippten Adresse.
  return reiter.value.some(r => r.value === wert) ? wert : 'liste'
}

const aktiverReiter = ref(reiterAusAdresse())
function reiterWechseln(wert) {
  if (!wert || wert === aktiverReiter.value) return
  if (!reiter.value.some(r => r.value === wert)) return
  // Die Adresse trägt den Reiter (Befund 6): Lesezeichen und „zurück“ wirken.
  navigate('#/personen/' + wert)
}
// Die Adresse ist die Wahrheit: jede Änderung (auch „zurück“) setzt den Reiter.
function adresseGeaendert() {
  const wert = reiterAusAdresse()
  if (wert !== aktiverReiter.value) aktiverReiter.value = wert
  // UX3f: „Person anlegen“ der Befehlspalette kommt als `#/personen?anlegen=1`
  // — auch wenn der Bereich schon offen ist (dann wechselt keine Seite).
  anlegeWunschAusAdresse()
}
// Die Rolle steht beim Aufbau fest; wechselt sie (z. B. Identitätswechsel im
// Devmodus), wird ein Reiter ohne Recht zur Liste.
watch(istAdmin, () => {
  if (!reiter.value.some(r => r.value === aktiverReiter.value)) aktiverReiter.value = 'liste'
})

const unterzeile = computed(() => {
  if (aktiverReiter.value === 'anfragen') return 'Neue Anmeldungen prüfen und aufnehmen'
  if (aktiverReiter.value === 'datenschutz') return 'Einwilligungen und Löschungen der Gemeinde'
  if (aktiverReiter.value === 'import') return 'Personen aus einer CSV-Datei einlesen'
  return istAdmin.value
    ? 'Alle Personen der Gemeinde'
    : 'Kontaktdaten der Gemeinde'
})

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
const zeigeAnlegenKnopf = computed(() => istAdmin.value && aktiverReiter.value === 'liste')

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
  laden, profilUrl, navigate, reiterWechseln, fehlerHinweis,
  ansichtWaehlen, sortierungUmschalten, statusFiltern,
  persoenlicheDatenUmschalten, form,
})
</script>

<style scoped>
/* Reiterleiste über dem Inhalt; Abstand aus der Skala (Prinzip Ä1). */
.p3-reiter { margin-bottom: var(--sp-4); }

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
</style>
