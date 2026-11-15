<template>
  <div class="kv-seite">
    <DkPageHeader
      title="Kalender verwalten"
      sub="Anlegen, Freigaben vergeben und Sichtbarkeit bestimmen."
      :krumen="[{ text: 'Kalender', href: '#/kalender' }, { text: 'Verwalten' }]"
    >
      <template #actions>
        <DkButton v-if="darfAnlegen" variant="primary" @click="neuerKalender">
          <IconPlus /> Neuer Kalender
        </DkButton>
      </template>
    </DkPageHeader>

    <DkHint v-if="darfAnlegen" variant="info">
      Je Kalender steht hier, <strong>wozu er gehört</strong> (Gemeinde, Gruppe oder
      Untergruppe) und <strong>wer ihn sehen, Termine eintragen oder prüfen</strong> darf.
      Die Änderungen wirken sofort — niemand muss sich neu anmelden.
    </DkHint>

    <!-- UX2d3b (Review UX2d3a/C): Der Platzhalter erscheint erst nach 300 ms
         (`useLadeSkelett`); darunter ist der Bildschirm ruhig und der
         Leerzustand kann nicht vor der Antwort aufblitzen. -->
    <DkSkelett v-if="skelettSichtbar" form="karten" :anzahl="2" text="Kalender werden geladen" />

    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

    <!-- UI-R3, Punkt 4: Wer nichts verwalten darf, bekommt vom Server 403 —
         die Seite ist dann KEINE Baustelle, sondern eine kurze Auskunft mit
         einem Weg (die eigenen Kalender stehen in der Gruppe). -->
    <DkEmpty
      v-else-if="gesperrt"
      title="Kein Kalender zu verwalten"
      text="Hier erscheinen Kalender, die du selbst pflegst. Kalender deiner Gruppe findest du unter „Gruppen“."
      icon="📅"
    />

    <DkEmpty
      v-else-if="!kalender.length && !darfAnlegen"
      title="Kein Kalender zu verwalten"
      text="Hier erscheinen Kalender, die du selbst pflegst. Kalender deiner Gruppe findest du unter „Gruppen“."
      icon="📅"
    />

    <!-- UI-R3b, Punkt 2: Die Fläche wird AUCH ohne Kalender gemountet — der
         Anlege-Dialog gehört ihr (`anlegenOeffnen`), und mit `!kalender.length`
         wäre `flaeche` null: „Neuer Kalender“ tat dann nichts. Den einzigen
         Anlege-Knopf und den einzigen Hinweis führt diese Seite (Punkt 3). -->
    <KalenderEinstellungen
      v-else
      ref="flaeche"
      alle-kalender
      :gruppe="gruppe"
      :ziele="zieleFuerFlaeche"
      :untergruppen="gruppenliste"
      @geaendert="nachladen"
      @gesperrt="aufGesperrt"
    />
  </div>
</template>

<script setup>
/**
 * KalenderVerwaltung — Kalender anlegen, umbenennen, Farbe und
 * „selbstverwaltet“ ändern, löschen, Freigaben vergeben (Nachtbefund
 * OP-ADMIN-10; seit UI-R3 auf dem EINEN Rechtesystem).
 *
 * Was UI-R3 geändert hat
 * ----------------------
 *  * Die Rollen-Auswahlen (Leserechte / Schreibrechte / Moderatoren) sind
 *    ENTFERNT. Der Server führt sie nur noch übergangsweise mit
 *    (`kalender_verwaltung._rechte_aus_alteingaben`); in der Fläche bewirkten
 *    sie nichts mehr.
 *  * Je Kalender: Zuordnung (Gemeinde / Gruppe X / Untergruppe Y), Freigaben
 *    und Sichtbarkeit — alles über die gemeinsame Fläche aus UI-R2
 *    (`rechte.get_objekt_rechte`, `setze_freigabe`, `beantrage_sichtbarkeit`, …).
 *  * Anlegen: „Gemeinde-Kalender“ nur mit `darf_gemeinde_kalender`, sonst die
 *    Auswahl aus `anlegen_gruppen` / `anlegen_untergruppen` des Servers, dazu
 *    die Frage „Sollen alle Gruppenmitglieder standardmäßig lesen dürfen?“.
 *  * Die Seite ist für JEDE Person da, die mindestens einen Kalender verwalten
 *    oder anlegen darf. Wer nichts verwalten darf, bekommt vom Server 403 —
 *    dann steht hier ein Satz statt Aktionen.
 *
 * Was UI-R3b geändert hat
 * -----------------------
 *  * Bearbeiten (Titel, Farbe, `selbstverwaltet` → `update_kalender`) und
 *    Löschen (`delete_kalender`; sofort + „Rückgängig“, nur bei einem
 *    Google-Import mit Rückfrage) stehen wieder — je Kalender in der
 *    gemeinsamen Fläche, also auch unter „Kalender der Gruppe“.
 *  * Die Fläche ist AUCH ohne Kalender gemountet: der Anlege-Dialog gehört ihr,
 *    sonst täte „Neuer Kalender“ beim ersten Kalender nichts.
 *  * EIN Anlege-Knopf und EIN Hinweis auf dieser Seite; die Fläche bringt im
 *    Modus `alleKalender` keinen eigenen mehr mit (A4).
 *  * Kein Rollen-Rückfall: `darfAnlegen` und die Anlegeorte kommen
 *    ausschließlich aus der Serverantwort (`get_kalender_verwaltung` liefert
 *    `darf_gemeinde_kalender` immer).
 *
 * Die Oberfläche entscheidet NIE über Rechte: sie blendet nur aus, was der
 * Server ohnehin verweigert, und zeigt Serverfehler (403/417) als Satz.
 */
import { computed, onMounted, ref, h } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import {
  alleKalenderZeilen,
  ausGruppenbaum,
  sichererFehlertext,
  verwaltungAnlegeZiele,
} from '../components/gruppen/kalenderRechte.mjs'
import KalenderEinstellungen from '../components/gruppen/KalenderEinstellungen.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkHint from '../components/ui/DkHint.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'

const VERWALTUNG = 'diakronos.kronos.api.kalender_verwaltung.get_kalender_verwaltung'

// „Neuer Kalender“ — dasselbe Plus wie in der Kalenderliste (kein Emoji).
const IconPlus = () => h('svg', {
  width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
}, [h('line', { x1: 12, y1: 5, x2: 12, y2: 19 }), h('line', { x1: 5, y1: 12, x2: 19, y2: 12 })])

// UI-R3b: KEIN Rollen-Rückfall. Ob angelegt werden darf, sagt ausschließlich
// die Serverantwort — `get_kalender_verwaltung` liefert `darf_gemeinde_kalender`
// und die Anlegeorte für JEDEN Aufrufer, der die Liste bekommt (wer nichts
// darf, bekommt 403 und sieht diese Seite gar nicht erst mit Knopf).

const verwaltung = ref(null)
const laedt = ref(true)
// UX2d3b: Platzhalter erst nach 300 ms — kein Blitzen, keine Aussage vor der Antwort.
const { skelettSichtbar } = useLadeSkelett(laedt)
const fehler = ref('')
/** 403 des Servers: diese Person verwaltet nichts (kein Fehler, eine Lage). */
const gesperrt = ref(false)
/** Die gemeinsame Fläche — ihr Anlege-Dialog ist der EINE Anlegeweg. */
const flaeche = ref(null)

/**
 * Anzeigenamen der (Unter-)Gruppen. Die Verwaltungsliste nennt je Kalender
 * nur Kennungen; `zuordnung` ist bereits der Anzeigename aus dem Server
 * (`verwaltung._name`). Fehlt er, bleibt die Kennung stehen — erfunden wird
 * kein Name.
 *
 * UI-R3: Zusätzlich die Namen aus dem Gruppenbaum
 * (`get_gruppen_hierarchie`) — dort steht `gruppenname`/`untergruppenname`
 * für ALLE Gruppen, während `get_kalender_verwaltung` die Anlegeorte nur als
 * Kennung liefert. Reine Anzeige, kein Rechtebezug: wer den Baum nicht lesen
 * darf, bekommt eine leere Liste und sieht wie bisher die Kennung.
 */
const baumNamen = ref({})

const namen = computed(() => {
  const karte = { ...baumNamen.value }
  for (const k of (verwaltung.value?.kalender || [])) {
    if (!k || !k.zuordnung) continue
    if (k.untergruppe) karte[k.untergruppe] = String(k.zuordnung)
    else if (k.gruppe) karte[k.gruppe] = String(k.zuordnung)
  }
  return karte
})

/** Den Gruppenbaum holen — Namen für die Anlegeorte. Nie ein Fehler für die Seite. */
async function ladeBaumNamen() {
  try {
    const antwort = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_hierarchie', {})
    baumNamen.value = ausGruppenbaum(antwort)
  } catch {
    // Kein Baum (403/Netzfehler): die Kennung bleibt stehen — die Seite
    // funktioniert weiter, nur ohne Klarnamen.
  }
}

/** Die Kalender dieser Person, mit Zuordnung (Gemeinde / Gruppe / Untergruppe). */
const kalender = computed(() => alleKalenderZeilen(verwaltung.value?.kalender, namen.value))

/** Anlegeorte aus der Serverantwort: Gemeinde nur mit `darf_gemeinde_kalender`. */
const anlegeziele = computed(() => verwaltungAnlegeZiele(verwaltung.value || {}, namen.value))

/**
 * Anlegen nur mit einem Ort — ohne Ort verweigert der Server (403). Die Orte
 * kommen AUSSCHLIESSLICH aus der Serverantwort (`darf_gemeinde_kalender`,
 * `anlegen_gruppen`, `anlegen_untergruppen`); die Seite prüft keine Rolle.
 */
const darfAnlegen = computed(() => anlegeziele.value.length > 0)

/** Anlegeorte für die gemeinsame Fläche — genau die des Servers. */
const zieleFuerFlaeche = computed(() => anlegeziele.value)

/**
 * Kennung der (Unter-)Gruppen für die Freigabe-Auswahl: die Orte, an denen
 * der Server ein Anlegen erlaubt. `anzeigename` ist der REINE Name
 * (`Jugendchor`) — die gemeinsame Fläche setzt „Gruppe“/„Untergruppe“ selbst
 * davor (`zuordnungsText`). Mit der fertigen Beschriftung stünde dort
 * „Untergruppe: Untergruppe Kinderchor“. Fehlt der Name, gilt die Kennung.
 */
const gruppenliste = computed(() => zieleFuerFlaeche.value
  .filter((z) => z.art === 'gruppe' || z.art === 'untergruppe')
  .map((z) => ({ name: String(z.wert || ''), anzeigename: namen.value[z.wert] || '' }))
  .filter((g) => g.name))

/**
 * Die gemeinsame Fläche (UI-R2) kennt eine Gruppen-Kennung für den Kopf
 * ihres Anlege-Dialogs. Die Kalenderverwaltung ist keine Gruppenseite:
 * `alleKalender` hebt den Filter auf, `ziele` nennt die Orte. Deshalb bleibt
 * die Kennung leer — eine erfundene Gruppe benennt fremde Kalender falsch.
 */
const gruppe = computed(() => '')


async function laden({ still = false } = {}) {
  if (!still) {
    laedt.value = true
    fehler.value = ''
  }
  try {
    verwaltung.value = (await apiCall(VERWALTUNG, {})) || null
    fehler.value = ''
    gesperrt.value = false
  } catch (err) {
    // 403 = der Server gibt dieser Person keine verwaltbaren Kalender. Das ist
    // keine Panne, sondern eine Lage: eine kurze Auskunft, keine Aktionen (der
    // Menüpunkt bleibt für sie weg — `kalenderVerwaltungSichtbar`).
    if (Number(err?.status) === 403) {
      verwaltung.value = null
      gesperrt.value = true
      fehler.value = ''
      return
    }
    gesperrt.value = false
    fehler.value = sichererFehlertext(err, { text: 'Die Kalender konnten nicht geladen werden.' })
  } finally {
    laedt.value = false
  }
}

/**
 * Nach einer Änderung in der gemeinsamen Fläche: still nachladen.
 *
 * Die Fläche lädt ihre eigenen Daten selbst; hier wird nur die Zuordnung der
 * Seite frisch geholt. `still` heißt: kein Skelett, die Fläche bleibt stehen.
 *
 * Sie meldet auch, wenn der Server die VERWALTUNG sperrt (403) — dann gilt
 * diese Lage auch für die Seite.
 */
function nachladen() {
  laden({ still: true })
}

/** 403 der gemeinsamen Fläche: hier gibt es nichts zu verwalten. */
function aufGesperrt(gesperrt2) {
  if (gesperrt2 === true) {
    verwaltung.value = null
    gesperrt.value = true
    fehler.value = ''
  }
}

/**
 * „Neuer Kalender“: derselbe Weg wie in der gemeinsamen Fläche — sie führt den
 * Anlege-Dialog samt Ortsauswahl und der Frage „Gruppe liest standardmäßig?“.
 * Ein zweiter Dialog hier wäre ein zweiter Weg zu denselben Daten. Die Fläche
 * gibt `anlegenOeffnen` dafür frei (`defineExpose`).
 */
function neuerKalender() {
  flaeche.value?.anlegenOeffnen?.()
}

onMounted(() => {
  // Namen und Verwaltungsliste unabhängig laden: fehlt der Baum, steht die
  // Kennung; fehlt die Liste, entscheidet das 403 (siehe `laden`).
  ladeBaumNamen()
  laden()
})
</script>

<style scoped>
.kv-seite { display: flex; flex-direction: column; gap: var(--sp-4); }
</style>
