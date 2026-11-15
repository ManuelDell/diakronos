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

    <!-- UI-R3e (MUSS 1): Bis die SEITE ihre Antwort hat, steht NICHTS. Vorher
         hing die Bedingung am geteilten `antwortDa` — beim Wechsel von der
         Kalenderseite ist das schon true, das eigene `verwaltung` aber noch
         leer, und „Kein Kalender zu verwalten“ blitzte auf. Jetzt entscheidet
         `!laedt` (eigener Ladestand). -->
    <template v-else-if="!antwortDa || laedt" />

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
      :verwaltung="verwaltung"
      :nachladen="nachladen"
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
// UI-R3c: EIN Ladevorgang für `get_kalender_verwaltung` je Seite.
import { useKalenderVerwaltung } from '../composables/useKalenderVerwaltung.js'
// (Der geteilte Stand importiert `useApi` über DENSELBEN Pfad,
// `./useApi.js` → hier `../composables/useApi.js` — die Test-Übersetzer
// ersetzen damit dieselbe Attrappe für Seite und Stand.)
import {
  alleKalenderZeilen,
  ausGruppenbaum,
  elternAusGruppenbaum,
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

// UI-R3c: EIN Ladevorgang für die Verwaltungsliste je Seite. Diese Seite holt
// sie und gibt die Antwort an die gemeinsame Fläche weiter (`:verwaltung`);
// die Fläche fragt nicht ein zweites Mal.
const {
  laden: ladenKalenderVerwaltung,
  sperrt: sperrtKalenderVerwaltung,
  fehler: fehlerKalenderVerwaltung,
} = useKalenderVerwaltung()

/**
 * UI-R3e (MUSS 1): Ist die Antwort DIESER Seite da? `false` = der Bildschirm
 * bleibt leer (kein Leerzustand vor der Antwort — der blitzte vorher auf).
 *
 * Quelle ist der EIGENE geladene Stand, nicht der geteilte `antwortDa`: beim
 * normalen Weg (Kalenderseite → ⋯ → „Kalender verwalten“) ist der geteilte
 * Stand schon gefüllt, das lokale `verwaltung` aber noch leer. Bestimmt wird
 * es in `laden()` — `laedt` und `antwortDaEigene` sind dieselbe Aussage.
 */
const antwortDaEigene = ref(false)
const antwortDa = computed(() => antwortDaEigene.value === true)

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
/**
 * UI-R3c: Untergruppe → Obergruppe aus demselben Gruppenbaum. Die
 * Freigabe-Auswahl je Kalender braucht den Kontext („welche Gruppen gehören zu
 * diesem Kalender“) — der Baum ist die eine Quelle dafür.
 */
const baumEltern = ref({})

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
    // UI-R3c: aus DERSELBEN Antwort die Obergruppen (siehe `baumEltern`).
    baumEltern.value = elternAusGruppenbaum(antwort)
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
 * Der GRUPPENBAUM für die Freigabe-Auswahl — aus `get_gruppen_hierarchie`.
 *
 * UI-R3e (MUSS 3): Die Freigabe-Auswahl je Kalender kommt aus dem GANZEN Baum,
 * nicht aus den Anlegezielen. Ein reiner Moderator hat keine Anlegeziele und
 * sah vorher eine leere Auswahl; ein Anlegerecht nur in der Gruppe G ließ
 * ihre Untergruppen fehlen. Kennung → `{ anzeigename, gruppe }` (`gruppe` ist
 * die Obergruppe einer Untergruppe, leer bei einer Gruppe).
 */
const gruppenbaum = computed(() => {
  const karte = {}
  for (const [name, anzeigename] of Object.entries(baumNamen.value || {})) {
    karte[String(name)] = { anzeigename: anzeigename || '', gruppe: stringOderLeer(baumEltern.value?.[name]) }
  }
  return karte
})

/** Kennung als Text (nie `null`/`undefined`). */
function stringOderLeer(wert) {
  return wert === null || wert === undefined ? '' : String(wert)
}

/**
 * Gruppen für die Freigabe-Auswahl, in der Form, die die gemeinsame Fläche
 * erwartet: `[{ name, anzeigename, gruppe }]` — `gruppe` ist die Obergruppe
 * (leer bei einer Gruppe), `anzeigename` der REINE Name.
 *
 * Der Baum ist der ganze Gruppenbaum (siehe `gruppenbaum`). Was für EINEN
 * Kalender daraus angeboten wird, entscheidet `gruppenAuswahlFuer` in der
 * Fläche: seine Gruppe samt Untergruppen, bei einem Gemeinde-Kalender alle.
 */
const gruppenliste = computed(() => {
  // Der BAUM ist die Grundlage (jede Gruppe samt Untergruppen, unabhängig vom
  // Anlegerecht); die Anlegeziele ergänzen ihn um Orte ohne Baumeintrag.
  const eintraege = new Map()
  for (const z of zieleFuerFlaeche.value) {
    if (z.art !== 'gruppe' && z.art !== 'untergruppe') continue
    const name = String(z.wert || '')
    if (!name || eintraege.has(name)) continue
    // Der REINE Name kommt aus `namen` (Kennung → Name des Gruppenbaums). Ein
    // leerer Name ist erlaubt: die Fläche zeigt dann die Kennung.
    eintraege.set(name, { name, anzeigename: namen.value[z.wert] || '', gruppe: '' })
  }
  for (const [name, eintrag] of Object.entries(gruppenbaum.value)) {
    if (eintraege.has(name)) {
      // Die Obergruppe aus dem BAUM hat Vorrang (ein Anlegeziel kennt seinen
      // Kontext nicht) — die Freigabe-Auswahl der Fläche hängt daran.
      if (eintrag.gruppe) eintraege.get(name).gruppe = String(eintrag.gruppe)
      continue
    }
    eintraege.set(name, { name, anzeigename: eintrag.anzeigename || '', gruppe: eintrag.gruppe || '' })
  }
  return [...eintraege.values()]
})

/**
 * Die gemeinsame Fläche (UI-R2) kennt eine Gruppen-Kennung für den Kopf
 * ihres Anlege-Dialogs. Die Kalenderverwaltung ist keine Gruppenseite:
 * `alleKalender` hebt den Filter auf, `ziele` nennt die Orte. Deshalb bleibt
 * die Kennung leer — eine erfundene Gruppe benennt fremde Kalender falsch.
 */
const gruppe = computed(() => '')

/**
 * Die Verwaltungsliste holen — EIN Ladevorgang für die Seite (der geteilte
 * Stand). Liefert die Antwort (`null` = keine) und schreibt `verwaltung`.
 *
 * UI-R3e: Die eigene Antwort wird über `teilen` der jüngste Stand des
 * geteilten Laders — eine ältere, noch laufende Anfrage (z. B. der
 * Kalenderseite) überschreibt sie danach nicht mehr.
 *
 * UI-R3f (SOLL 2): Die Antwort von `laden()` wird NICHT erneut über `teilen()`
 * geschickt, sondern DIREKT übernommen. Zwei Gründe:
 *  * bei 403 gibt `laden()` `null` zurück und setzt `sperrt`; `teilen(null)`
 *    setzte `sperrt` wieder auf false — der Zweig `gesperrt` war tot;
 *  * `teilen()` erhöht `juengste` und bricht damit eine neuere laufende
 *    Anfrage ab.
 */
async function listeHolen({ frisch = false } = {}) {
  const antwort = await ladenKalenderVerwaltung({ frisch })
  verwaltung.value = antwort || null
  return verwaltung.value
}

async function laden({ still = false } = {}) {
  if (!still) {
    laedt.value = true
    antwortDaEigene.value = false
    fehler.value = ''
  }
  // UI-R3c: EIN Ladevorgang. Die gemeinsame Fläche fragt denselben Endpunkt für
  // die Kalenderliste; sie bekommt die Antwort HIER über `:verwaltung` — sie
  // stellt keine eigene Anfrage mehr. `null` heißt „keine Antwort“ und wird
  // ausdrücklich übergeben (dann lädt die Fläche selbst, z. B. solo in einem
  // Test oder auf einer fremden Seite).
  //
  // UI-R3f (MUSS 1): JEDER Aufruf dieser Seite lädt FRISCH. Beim Aufbau hielt
  // der geteilte Lader sonst die Antwort der Kalenderseite fest (gelöschte
  // Kalender mit aktivem Löschen-Knopf); nach einer Änderung (`nachladen`) ist
  // der Stand ohnehin veraltet. Die Leiste liest weiter nur den reaktiven
  // Stand — je Seitenbesuch bleibt es bei EINER Anfrage.
  await listeHolen({ frisch: true })
  // 403 = der Server gibt dieser Person keine verwaltbaren Kalender. Das ist
  // keine Panne, sondern eine Lage: eine kurze Auskunft, keine Aktionen (der
  // Menüpunkt bleibt für sie weg — `kalenderVerwaltungSichtbar`).
  gesperrt.value = sperrtKalenderVerwaltung.value === true && !fehlerKalenderVerwaltung.value
  // UI-R3e (SOLL 7): auch der stille Weg räumt einen alten Fehler ab — sonst
  // bliebe die Meldung nach einem geglückten Nachladen stehen.
  //
  // Der Grund des Servers steht VORNE, der allgemeine Satz dahinter — so bleibt
  // „Die Kalender konnten nicht geladen werden.“ immer lesbar (auch wenn der
  // Grund nur „HTTP 500“ heißt) und der konkrete Text geht nicht verloren.
  { const grund = String(fehlerKalenderVerwaltung.value || '').trim()
    fehler.value = grund
      ? `${sichererFehlertext(new Error(grund), { text: 'Die Kalender konnten nicht geladen werden.' })}`
      : '' }
  // UI-R3e (MUSS 1): ab hier entscheidet die EIGENE Antwort über den Inhalt —
  // vorher hing das am geteilten `antwortDa`, das beim Wechsel von der
  // Kalenderseite schon true war.
  antwortDaEigene.value = true
  laedt.value = false
}

/**
 * Nach einer Änderung in der gemeinsamen Fläche: still nachladen.
 *
 * `still` heißt: kein Skelett, die Fläche bleibt stehen.
 *
 * UI-R3e (SOLL 4): Die Fläche WARTET auf diese Promise. Vorher war der Aufruf
 * folgenlos für sie (`verwaltungLaden({still:true})` war mit `:verwaltung`
 * ein No-op) — Toast und „Rückgängig“ erschienen, während die gelöschte Zeile
 * mit aktivem Löschen-Knopf noch dastand.
 *
 * Sie meldet auch, wenn der Server die VERWALTUNG sperrt (403) — dann gilt
 * diese Lage auch für die Seite.
 */
function nachladen() {
  return laden({ still: true })
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
  //
  // UI-R3e (MUSS 3): Die Freigabe-Auswahl je Kalender braucht den BAUM. Die
  // Fläche wird erst mit der Liste gemountet — sie bekommt den fertigen Baum
  // deshalb über `:untergruppen`; hier wird er geholt, bevor die Liste da ist.
  ladeBaumNamen()
  laden()
})
</script>

<style scoped>
.kv-seite { display: flex; flex-direction: column; gap: var(--sp-4); }
</style>
