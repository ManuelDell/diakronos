<template>
  <!-- CHAT-3a — Bereich „Nachrichten“ (Chat-Konzept 6.2 Variante B, 10.1/10.2).
       Desktop: Liste links, Verlauf rechts. Handy: zwei Ansichten — die Liste
       unter `#/nachrichten`, der Verlauf unter `#/nachrichten/<gespraech>`
       (eine Ebene, kein Seitenbaum; Zurück führt zur Liste). -->
  <div class="dk-screen dk-screen-wide dk-screen-enter dk-chat">
    <DkPageHeader
      :title="kennung ? titel : 'Nachrichten'"
      :sub="unterzeile"
      :krumen="krumen"
    >
      <template #actions>
        <DkButton
          v-if="kennung && offenesGespraech"
          variant="secondary"
          size="sm"
          @click="stummUmschalten"
        >{{ offenesGespraech.stumm ? 'Nicht mehr stumm' : 'Stumm schalten' }}</DkButton>
      </template>
    </DkPageHeader>

    <!-- Modul aus (oder kein Leserecht): EIN Hinweis, keine leere Liste. -->
    <DkCard v-if="!modulAn" flach>
      <DkEmpty icon="✉" :title="MODUL_AUS.titel" :text="MODUL_AUS.text" />
    </DkCard>

    <template v-else>
      <!-- Fehler der Liste (403 → „kein Zugriff“, sonst Katalogtext). -->
      <DkCard v-if="listenFehler" flach>
        <DkEmpty
          icon="⚠"
          :title="listenFehler.titel"
          :text="listenFehler.text"
          :erneut-versuchen="laden"
        />
      </DkCard>

      <div v-else class="dk-chat-bereich">
        <!-- ── Liste ──────────────────────────────────────────────────── -->
        <div class="dk-chat-liste-spalte" :class="{ 'nur-handy-aus': Boolean(kennung) }">
          <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="5" text="Gespräche werden geladen …" />
          <DkEmpty
            v-else-if="!gruppen.length"
            icon="✉"
            :title="LISTE_LEER.titel"
            :text="LISTE_LEER.text"
          />
          <ChatListe
            v-else
            :gruppen="gruppen"
            :aktiv="kennung"
            :ungelesen="ungelesen"
          />
        </div>

        <!-- ── Verlauf ────────────────────────────────────────────────── -->
        <div class="dk-chat-verlauf-spalte" :class="{ 'nur-handy-aus': !kennung }">
          <!-- Leerzustand der rechten Seite (Desktop, kein Gespräch offen). -->
          <div v-if="!kennung" class="dk-chat-nichts">
            <DkEmpty
              icon="💬"
              title="Wähle ein Gespräch"
              text="Links stehen deine Gespräche — Gruppen und Untergruppen, in denen der Chat eingeschaltet ist."
            />
          </div>

          <div v-else class="dk-chat-verlauf">
            <!-- Kopf des offenen Gesprächs: zurück (nur Handy), Titel, Zähler. -->
            <div class="dk-chat-verlauf-kopf">
              <a class="dk-chat-zurueck" href="#/nachrichten" aria-label="Zurück zur Liste">
                <span aria-hidden="true">‹</span>
              </a>
              <div class="dk-chat-verlauf-titel">
                <h2>{{ titel }}</h2>
                <p class="dk-chat-verlauf-unter">
                  <span v-if="teilnehmerZahl">{{ teilnehmerZahl }} im Gespräch</span>
                  <span v-if="offenesGespraech && offenesGespraech.stumm" class="dk-chat-stumm-hinweis"> · stumm geschaltet</span>
                </p>
              </div>
            </div>

            <p v-if="verlaufFehler" class="dk-chat-fehler" role="alert">{{ verlaufFehler }}</p>
            <p v-else-if="verlaufHinweis || listeHinweis" class="dk-chat-hinweis">
              {{ verlaufHinweis || listeHinweis }}
            </p>

            <!-- Der Verlauf: role="log" + aria-live="polite" (Karte Punkt 5).
                 Nachladen nach oben beim Scrollen an den Anfang. -->
            <div
              ref="verlaufEl"
              class="dk-chat-nachrichten"
              role="log"
              aria-live="polite"
              aria-relevant="additions"
              :aria-label="`Verlauf von ${titel}`"
              tabindex="-1"
              @scroll.passive="beimScrollen"
            >
              <DkSkelett v-if="aelterLaedt" form="zeilen" :anzahl="2" />
              <DkButton
                v-else-if="aelterMoeglich"
                variant="ghost"
                size="sm"
                class="dk-chat-textknopf"
                @click="aeltereLaden"
              >Ältere Nachrichten laden</DkButton>

              <DkSkelett v-if="verlaufLaedt && !nachrichten.length" form="zeilen" :anzahl="4" text="Verlauf wird geladen …" />
              <DkEmpty
                v-else-if="!nachrichten.length"
                icon="💬"
                :title="VERLAUF_LEER.titel"
                :text="VERLAUF_LEER.text"
              />
              <!-- Die Zeilen stehen in einer LISTE innerhalb der Log-Region:
                   `role="log"` trägt keine <li>, die brauchen ein <ul>. -->
              <ul v-else class="dk-chat-verlaufsliste">
                <template v-for="n in nachrichtenMitTag" :key="n.ident">
                  <li v-if="n.tag" class="dk-chat-tag"><span>{{ n.tag }}</span></li>
                  <ChatBlase
                    :nachricht="n"
                    @reaktion="reaktionSetzen"
                    @antworten="antworten"
                    @bearbeiten="bearbeitenOeffnen"
                    @loeschen="loeschen"
                  />
                </template>
              </ul>
            </div>

            <!-- Eingabe: Enter sendet, Shift+Enter macht einen Absatz. -->
            <form class="dk-chat-eingabe" @submit.prevent="senden">
              <p v-if="antwortAuf" class="dk-chat-antwortzeile">
                <span class="dk-chat-antwort-text">Antwort auf: {{ antwortAuf.antwortText || antwortAuf.text || 'eine Nachricht' }}</span>
                <DkButton variant="ghost" size="sm" class="dk-chat-textknopf" @click="antwortAuf = null">Antwort verwerfen</DkButton>
              </p>
              <div class="dk-chat-eingabe-zeile">
                <label class="dk-chat-nur-vorlesen" for="chat-eingabe">Nachricht schreiben</label>
                <textarea
                  id="chat-eingabe"
                  ref="eingabeEl"
                  v-model="text"
                  class="dk-chat-feld"
                  rows="1"
                  :placeholder="eingabeHinweis"
                  :maxlength="NACHRICHT_MAX"
                  @keydown="beimTasten"
                ></textarea>
                <DkButton type="submit" variant="primary" :loading="sendet" :disabled="!text.trim()">
                  {{ SENDEN_TEXT }}
                </DkButton>
              </div>
              <p v-if="eingabeFehler" class="dk-chat-fehler" role="alert">{{ eingabeFehler }}</p>
            </form>
          </div>
        </div>
      </div>
    </template>

    <!-- Bearbeiten-Fenster: eigener Text, 15 Minuten (Server prüft erneut). -->
    <DkDialog
      :model-value="Boolean(bearbeiten)"
      title="Nachricht bearbeiten"
      @close="bearbeiten = null"
    >
      <label class="dk-chat-nur-vorlesen" for="chat-bearbeiten">Nachricht bearbeiten</label>
      <textarea
        id="chat-bearbeiten"
        v-model="bearbeitenText"
        class="dk-chat-feld dk-chat-feld-gross"
        rows="4"
        :maxlength="NACHRICHT_MAX"
      ></textarea>
      <p v-if="bearbeitenFehler" class="dk-chat-fehler" role="alert">{{ bearbeitenFehler }}</p>
      <template #footer>
        <DkButton variant="ghost" @click="bearbeiten = null">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="bearbeitenLaeuft" @click="bearbeitenSpeichern">Speichern</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * Nachrichten — der Bereich „Nachrichten“ (CHAT-3a).
 *
 * Grundlagen: `docs/konzepte/CHAT-KONZEPT.md` 1 (S1), 6.2 (Variante B),
 * 9 (F1–F11 — Lesestand nur als Summe, Stumm je Person, Untergruppe eigener
 * Raum), 10.1–10.3. Entwürfe `chat-entwurf/B-desktop.html` / `B-handy.html`,
 * aber mit dem BESTEHENDEN Design-System (DkCard, DkBadge, DkButton, Tokens) —
 * keine neuen Farben, Ausgrauung über `--subtle`/`--surface-2`.
 *
 * WAS HIER STEHT UND WAS NICHT
 * Die Regeln (Gruppierung, Zeitformate, Nachladen, Polling, Zähler) liegen in
 * `composables/nachrichtenLogik.mjs` und `composables/nachrichtenReaktionen.mjs`
 * — ohne DOM prüfbar (`tests/chat3a-nachrichten.test.mjs`). Diese Seite holt,
 * zeichnet und verdrahtet.
 *
 * SERVER (unverändert, `backend/src/diakronos_app/api/chat.py`):
 *   GET  chat.meine_gespraeche                 → {gespraeche: [...]}
 *   GET  chat.verlauf(gespraech, vor)          → {nachrichten, vor, seit}
 *   POST chat.gespraech_anlegen(gruppe?, untergruppe?)
 *   POST chat.senden(gespraech, text, antwort_auf)
 *   POST chat.aendern(nachricht, text)
 *   POST chat.loeschen(nachricht)
 *   POST chat.reaktion_setzen(nachricht, reaktion)
 *   POST chat.lesestand_setzen(gespraech, nachricht?)
 *   POST chat.stumm_setzen(gespraech, an)
 *
 * NICHT in dieser Karte: Personensuche/Profil (CHAT-3c), Chat-Reiter in der
 * Gruppe (CHAT-3b), Melden (CHAT-6), Umfragen, Anhänge, Direktnachrichten.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { apiCall, apiGet } from '../composables/useApi.js'
import { useSession } from '../composables/useSession.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { modulChatErlaubt } from '../modulRechte.mjs'
import { fehlertext } from '../../shared/fehlertexte.js'
import {
  BEREICH, LISTE_LEER, MODUL_AUS, NACHRICHT_MAX, SENDEN_TEXT, TAKT_MS, VERLAUF_LEER,
  aelterStand, backoffMs, eingabePlatzhalter,
  fehlerZustand, fremdeNeue, gespraechAusHash, gespraechHash, gruppierteListe,
  lesestandFaellig, mitTagesmarken, pruefeText, seiteEinordnen, taktGeber, tasteImFeld,
  ungelesenSumme, verlaufsZeile, zeilenSchluessel,
} from '../composables/nachrichtenLogik.mjs'
import { naechsteReaktion } from '../composables/nachrichtenReaktionen.mjs'
import DkCard from '../components/ui/DkCard.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import ChatListe from '../components/chat/ChatListe.vue'
import ChatBlase from '../components/chat/ChatBlase.vue'

// ── Sitzung und Adresse ────────────────────────────────────────────────────

const { mitglied } = useSession()
const boot = computed(() => (typeof window === 'undefined' ? {} : (window.__DIakonosBOOT || {})))
/** Das Modul `chat` — dieselbe Regel wie Router-Guard und Handy-Leiste. */
const modulAn = computed(() => modulChatErlaubt(boot.value))
/** „Ich“ = Mitglied-Kennung. Der Server setzt `eigene` je Nachricht; das hier
 *  ist nur der Rückfall, wenn eine Antwort das Feld nicht trägt. */
const ich = computed(() => String(mitglied.value?.name || ''))

/** Kennung aus der Adresse (`#/nachrichten/<gespraech>`) — folgt dem Router. */
const kennung = ref(gespraechAusHash(typeof window === 'undefined' ? '' : window.location.hash))
function hashGeaendert() {
  kennung.value = gespraechAusHash(window.location.hash)
}

// ── Liste ──────────────────────────────────────────────────────────────────

const gespraeche = ref([])
const listeLaedt = ref(true)
const listeFehlerRoh = ref(null)
/** Kleiner Hinweis, wenn ein TAKT-Abruf scheitert — die letzte gute Liste bleibt
 *  stehen (Review R1: kein Vollbild-Fehler für einen misslungenen Poll). */
const listeHinweis = ref('')
const { skelettSichtbar } = useLadeSkelett(listeLaedt)

/**
 * Was die Liste im Fehlerfall zeigt: 403 → „kein Zugriff“, 404 → „gibt es
 * nicht“, 417 → Satz des Servers; alles andere (Netz, 500) den Katalogtext
 * (`fehlertext`) — NIE eine leere Fläche ohne Erklärung (Prinzip I5).
 */
const listenFehler = computed(() => {
  const roh = listeFehlerRoh.value
  if (!roh) return null
  const zustand = fehlerZustand(roh)
  if (zustand) return zustand
  return { art: 'allgemein', titel: 'Die Gespräche konnten nicht geladen werden', text: fehlertext(roh) }
})
const gruppen = computed(() => gruppierteListe(gespraeche.value))
const ungelesen = computed(() => ungelesenSumme(gespraeche.value))
/** Sind wir noch da? Ein Abruf, der nach dem Abbau zurückkommt, darf nichts mehr
 *  schreiben und nichts mehr starten (Review R1, MUSS 3). */
let aktivSeite = true

/** Die Zeile des offenen Gesprächs (Titel, Teilnehmer, Stumm) aus der Liste. */
const offenesGespraech = computed(() => {
  const k = String(kennung.value || '')
  if (!k) return null
  return gespraeche.value.find((e) => String(e?.name || '') === k
    || zeilenSchluessel(e) === k) || null
})
const titel = computed(() => String(offenesGespraech.value?.titel || 'Gespräch'))
const teilnehmerZahl = computed(() => Number(offenesGespraech.value?.teilnehmer) || 0)

const unterzeile = computed(() => {
  if (!kennung.value) return 'Alle Gespräche an einem Ort.'
  return teilnehmerZahl.value ? `${teilnehmerZahl.value} im Gespräch` : 'Gruppe und Untergruppe, in denen der Chat an ist.'
})

const krumen = computed(() => (kennung.value
  ? [{ text: 'Nachrichten', href: BEREICH }, { text: titel.value }]
  : []))

/**
 * Die Gesprächsliste holen — die EINE Abfrage von `meine_gespraeche` je Takt
 * (Review R1, MUSS 4: Liste UND Zähler kommen aus demselben Ergebnis).
 *
 * @param {{still?: boolean}} [lage] `still` = Takt/Poll: kein Ladeprotokoll,
 *        kein großer Fehler — die letzte gute Liste bleibt stehen, nur ein
 *        kleiner Hinweis erscheint.
 * @returns {Promise<boolean>} ob es geklappt hat
 */
async function laden({ still = false } = {}) {
  if (!still) {
    listeFehlerRoh.value = null
    listeHinweis.value = ''
  }
  try {
    const antwort = await apiGet('chat.meine_gespraeche')
    if (!aktivSeite) return false
    gespraeche.value = Array.isArray(antwort?.gespraeche) ? antwort.gespraeche : []
    listeHinweis.value = ''
    // Den Zähler der Handy-Leiste nachziehen — mit DIESER Zahl, kein zweiter
    // Aufruf: die App-Wurzel übernimmt `detail.ungelesen`.
    mitteilungSenden()
    return true
  } catch (fehler) {
    if (!aktivSeite) return false
    if (still || gespraeche.value.length) {
      // Fehlgeschlagener Poll: letzte gute Liste behalten, nur ein Hinweis.
      listeHinweis.value = 'Die Liste konnte gerade nicht aktualisiert werden.'
    } else {
      listeFehlerRoh.value = fehler
    }
    return false
  } finally {
    listeLaedt.value = false
  }
}

/**
 * Die App-Wurzel führt den Zähler der Leiste — sie bekommt die fertige SUMME
 * im Ereignis (`detail.ungelesen`) und holt sie nicht selbst noch einmal.
 *
 * MUSS 4: `summe` ist die Zahl, die mitreist. Ohne Angabe wird sie aus der
 * Liste gerechnet; `null` heißt „die Seite übernimmt, aber es gibt noch keine
 * Zahl“ — die App zeigt dann keinen Zähler und fragt NICHT nach (`fraegt`).
 * Ein `null` nur zu senden, wenn wirklich keine Liste da ist, wäre ein
 * Unterschied ohne Bedeutung: der App-Zähler unterscheidet beides nicht.
 */
function mitteilungSenden(summe = undefined) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  const zahl = summe === undefined ? ungelesenSumme(gespraeche.value) : summe
  window.dispatchEvent(new CustomEvent('dk-chat-ungelesen', {
    detail: { ungelesen: zahl, fraegt: false },
  }))
}

/**
 * Der Seite wird auf- oder abgebaut. Abgebaut gibt sie den Zähler FREI, damit
 * die App-Wurzel ihn wieder führt (sonst bliebe er für immer bei „die Seite
 * fragt“ stehen und zeigte den letzten Stand bis zum Neuladen).
 */
function mitteilungSeite(offen) {
  if (typeof window === 'undefined' || typeof window.dispatchEvent !== 'function') return
  window.dispatchEvent(new CustomEvent('dk-chat-seite', { detail: { offen: offen === true } }))
}

// ── Verlauf ────────────────────────────────────────────────────────────────

const nachrichten = ref([])
const verlaufLaedt = ref(false)
const verlaufFehler = ref('')
/** Kleiner Hinweis nach einem misslungenen Poll (der Verlauf bleibt stehen). */
const verlaufHinweis = ref('')
const aelterLaedt = ref(false)
const aelterMoeglich = ref(false)
const verlaufEl = ref(null)
const eingabeEl = ref(null)
const text = ref('')
const sendet = ref(false)
const eingabeFehler = ref('')
const antwortAuf = ref(null)
const eingabeHinweis = computed(() => eingabePlatzhalter(titel.value))
/** Höhe des Verlaufs VOR dem Nachladen — hält die Leseposition beim Nachladen. */
let scrollVorher = 0

function zuruecksetzen() {
  nachrichten.value = []
  verlaufFehler.value = ''
  eingabeFehler.value = ''
  antwortAuf.value = null
  aelterMoeglich.value = false
}

/** Gespräch öffnen: Verlauf holen, Lesestand setzen, Fokus in den Verlauf. */
async function oeffnen() {
  const offen = kennung.value
  if (!offen) return
  zuruecksetzen()
  // Ein Gespräch, das noch nie geöffnet wurde, hat serverseitig KEINE Kennung
  // (`geoeffnet: false`). Hier wird es angelegt (`gespraech_anlegen`, lazy im
  // Server) und die Adresse auf die neue Kennung gestellt — EIN Weg, kein
  // Sonderfall im Verlauf.
  if (!(await sicherstellen())) return
  const daten = await verlaufLaden()
  if (daten) await lesestandSetzen()
  // Karte Punkt 5: Fokus nach Gesprächswechsel in den Verlauf — die neue
  // Region wird vorgelesen, der Fokus bleibt nicht im alten Gespräch.
  await nextTick()
  if (verlaufEl.value && typeof verlaufEl.value.focus === 'function') verlaufEl.value.focus()
  await nachUntenScrollen()
}

/**
 * Der Eintrag einer Adresse, die noch keine Gesprächszeile hat (sonst `null`).
 *
 * Review R1: adressiert wird über den ORT (Gruppe + Untergruppe), nicht über
 * den Titel — zwei Untergruppen können denselben Anzeigenamen tragen, und der
 * Titel ist frei.
 *
 * CHAT-3a-3/C1 (Review Runde 2): Ein Hauptgruppen-Name („Jugend“) durfte NICHT
 * die Untergruppe („Jugend – Leiter“) treffen. Vorher stand hier
 * `e.gruppe === a || e.untergruppe === a` — bei `a = 'Jugend'` passte auch der
 * Eintrag der Untergruppe, denn dessen `gruppe` ist ebenfalls „Jugend“; der
 * Server sortiert nie geöffnete Einträge nach Titel ABSTEIGEND, „Jugend –
 * Leiter“ stand also VOR „Jugend“, und der falsche Chat wurde geöffnet (und
 * angelegt). Die Adresse nennt jetzt GENAU eine Einheit:
 *
 *   * Hauptgruppe  → `!e.untergruppe && e.gruppe === a` (nur der Haupt-Chat),
 *   * Untergruppe  → `e.untergruppe === a` (die Untergruppe ist eindeutig),
 *   * `gruppe/untergruppe` → beide Felder zusammen.
 */
function ungeoeffneteZeile(adresse) {
  const a = String(adresse || '')
  if (!a) return null
  return gespraeche.value.find((e) => {
    if (e.name || e.geoeffnet !== false) return false
    const gruppe = String(e.gruppe || '')
    const unter = String(e.untergruppe || '')
    if (unter) return unter === a || `${gruppe}/${unter}` === a
    return gruppe === a
  }) || null
}

/**
 * Stellt sicher, dass das Gespräch der Adresse EXISTIERT (legt es bei Bedarf an)
 * und die Adresse auf seine Kennung zeigt. `true` = es kann geladen werden.
 */
async function sicherstellen() {
  const ziel = kennung.value
  if (!ziel) return false
  if (gespraeche.value.some((e) => String(e?.name || '') === ziel)) return true
  const neu = ungeoeffneteZeile(ziel)
  if (!neu) return true // unbekannte Kennung: der Verlauf meldet „gibt es nicht“
  try {
    const angelegt = await apiCall('chat.gespraech_anlegen', {
      gruppe: neu.gruppe,
      untergruppe: neu.untergruppe || undefined,
    })
    const kennungNeu = String(angelegt?.name || '')
    if (!kennungNeu) return false
    // Die Liste kennt den Eintrag jetzt als geöffnet — ohne zweiten Abruf.
    gespraeche.value = gespraeche.value.map((e) => (e === neu
      ? { ...e, name: kennungNeu, geoeffnet: true, art: angelegt?.art || e.art }
      : e))
    // Die Adresse auf die echte Kennung stellen (ersetzt den Platzhalter-Titel).
    // Verglichen wird der PFAD ohne Abfrageteil — ein `?…` darf den Wechsel nicht
    // verhindern und auch nicht mitgeschleppt werden.
    const zielHash = gespraechHash(kennungNeu)
    const aktuell = typeof window === 'undefined' ? '' : String(window.location.hash || '').split('?')[0]
    if (typeof window !== 'undefined' && aktuell !== zielHash) {
      window.location.replace(zielHash)
      return false // der hashchange-Handler lädt den Verlauf
    }
    kennung.value = kennungNeu
    return true
  } catch (fehler) {
    listeFehlerRoh.value = fehler
    return false
  }
}

/**
 * Neueste Seite laden (erstes Öffnen und Polling).
 *
 * CHAT-3a-3/B (Review Runde 2): Der Poll schickt KEIN `seit` mehr. `seit`
 * liefert serverseitig nur Nachrichten mit SPÄTEREM Zeitstempel
 * (`api/chat.py`, `verlauf` → `ChatNachricht.erstellt_am > anker`) — eine
 * Bearbeitung, eine Löschung (samt `geloescht_grund`), eine neue Reaktion oder
 * ein geänderter Lesestand einer schon sichtbaren Nachricht kam damit NIE an.
 * Ohne `seit` antwortet der Server mit `richtung: 'neueste'` — der vollen,
 * jüngsten Seite; `seiteEinordnen` ersetzt bekannte Zeilen in place, hängt
 * neue hinten an und zählt `aktualisiert`. Ein verschobener Verlauf ist damit
 * der Normalfall, kein Sonderfall (`istAeltereSeite` fragt die `richtung`).
 *
 * @returns {boolean} ob geladen wurde (für `lesestandSetzen`)
 */
async function verlaufLaden({ still = false } = {}) {
  const offen = kennung.value
  if (!offen) return false
  if (!still) verlaufLaedt.value = true
  let erfolg = false
  try {
    const antwort = await apiGet('chat.verlauf', { gespraech: offen })
    if (!aktivSeite || offen !== kennung.value) return false // inzwischen anderes Gespräch
    const vorher = nachrichten.value
    const lage = seiteEinordnen(antwort, { alt: vorher, ich: ich.value })
    nachrichten.value = lage.nachrichten
    // „nachladen nach oben“: NUR ein voller, älterer Abruf ändert das; die
    // neueste Seite und der Poll sagen nichts darüber (`aelterStand`).
    aelterMoeglich.value = aelterStand(aelterMoeglich.value, lage.aelterMoeglich)
    verlaufFehler.value = ''
    verlaufHinweis.value = ''
    erfolg = true
    if (still) {
      // MUSS 2: neue fremde Nachrichten in einem SICHTBAREN Tab sind gelesen —
      // Lesestand melden, sonst bliebe der Zähler stehen.
      if (lesestandFaellig({
        neuHinzugefuegt: lage.neuHinzugefuegt,
        neueFremde: fremdeNeue(vorher, lage.nachrichten),
        ungelesen: Number(offenesGespraech.value?.ungelesen) || 0,
        sichtbar: tabSichtbar(),
      })) {
        await lesestandSetzen()
      }
      if (lage.neuHinzugefuegt > 0) await nachUntenScrollen()
    }
  } catch (fehler) {
    if (!aktivSeite || offen !== kennung.value) return false
    if (still) {
      // Ein misslungener Poll behält den letzten guten Verlauf und zeigt nur
      // einen kleinen Hinweis (Review R1).
      verlaufHinweis.value = 'Der Verlauf konnte gerade nicht aktualisiert werden.'
    } else {
      const zustand = fehlerZustand(fehler)
      verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
    }
  } finally {
    if (!still) verlaufLaedt.value = false
  }
  return erfolg
}

/** Nachladen nach OBEN: die Seite VOR der ältesten bekannten Nachricht. */
async function aeltereLaden() {
  const offen = kennung.value
  if (!offen || aelterLaedt.value || !nachrichten.value.length) return
  aelterLaedt.value = true
  const anker = nachrichten.value[0].ident
  scrollVorher = verlaufEl.value ? verlaufEl.value.scrollHeight : 0
  try {
    const antwort = await apiGet('chat.verlauf', { gespraech: offen, vor: anker })
    if (offen !== kennung.value) return
    const seite = Array.isArray(antwort?.nachrichten) ? antwort.nachrichten : []
    const lage = seiteEinordnen(antwort, { alt: nachrichten.value, ich: ich.value })
    nachrichten.value = lage.nachrichten
    aelterMoeglich.value = aelterStand(aelterMoeglich.value, lage.aelterMoeglich)
    await nextTick()
    // Die gelesene Stelle bleibt stehen: die neuen Zeilen stehen OBEN, deshalb
    // wird um die hinzugekommene Höhe nachgeschoben (sonst springt der Verlauf).
    if (verlaufEl.value && scrollVorher) {
      verlaufEl.value.scrollTop = verlaufEl.value.scrollHeight - scrollVorher
    }
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    aelterLaedt.value = false
  }
}

/** Am Anfang des Verlaufs angekommen → ältere Seite holen (Karte Punkt 1). */
function beimScrollen() {
  const el = verlaufEl.value
  if (!el || !aelterMoeglich.value || aelterLaedt.value) return
  if (el.scrollTop <= 24) aeltereLaden()
}

async function nachUntenScrollen() {
  await nextTick()
  if (verlaufEl.value) verlaufEl.value.scrollTop = verlaufEl.value.scrollHeight
}

/** Verlauf mit Tages-Marken für die Anzeige (Heute/Gestern/Wochentag/Datum). */
const nachrichtenMitTag = computed(() => mitTagesmarken(nachrichten.value))

// ── Lesestand, Stumm ───────────────────────────────────────────────────────

/**
 * Lesestand setzen — beim Öffnen und nach neuen Nachrichten. Die Antwort trägt
 * den neuen Zähler des Gesprächs; er wird in die Liste übernommen (kein
 * zweiter Abruf), damit „ungelesen“ sofort stimmt.
 */
async function lesestandSetzen() {
  const offen = kennung.value
  if (!offen) return
  try {
    const antwort = await apiCall('chat.lesestand_setzen', { gespraech: offen })
    const zahl = Number(antwort?.ungelesen)
    if (Number.isInteger(zahl)) {
      gespraeche.value = gespraeche.value.map((e) => (String(e?.name || '') === String(offen)
        ? { ...e, ungelesen: zahl }
        : e))
      mitteilungSenden()
    }
  } catch {
    // Der Lesestand ist Beiwerk — ein Fehler darf das Lesen nicht stören.
  }
}

async function stummUmschalten() {
  const offen = kennung.value
  const eintrag = offenesGespraech.value
  if (!offen || !eintrag) return
  const an = eintrag.stumm !== true
  try {
    await apiCall('chat.stumm_setzen', { gespraech: offen, an })
    gespraeche.value = gespraeche.value.map((e) => (String(e?.name || '') === String(offen)
      ? { ...e, stumm: an }
      : e))
  } catch (fehler) {
    verlaufFehler.value = fehlertext(fehler)
  }
}

// ── Eingabe, Antworten ─────────────────────────────────────────────────────

function beimTasten(ereignis) {
  const absicht = tasteImFeld({
    key: ereignis.key,
    shiftKey: ereignis.shiftKey,
    isComposing: ereignis.isComposing,
  })
  if (absicht !== 'senden') return
  ereignis.preventDefault()
  senden()
}

async function senden() {
  const offen = kennung.value
  if (!offen || sendet.value) return
  const pruefung = pruefeText(text.value)
  if (!pruefung.ok) {
    eingabeFehler.value = pruefung.fehler
    return
  }
  sendet.value = true
  eingabeFehler.value = ''
  try {
    const args = { gespraech: offen, text: pruefung.text }
    if (antwortAuf.value?.ident) args.antwort_auf = antwortAuf.value.ident
    const neu = await apiCall('chat.senden', args)
    const zeile = verlaufsZeile(neu, { ich: ich.value })
    if (zeile) nachrichten.value = [...nachrichten.value.filter((n) => n.ident !== zeile.ident), zeile]
    text.value = ''
    antwortAuf.value = null
    await nachUntenScrollen()
    // Liste (letzte Nachricht, Zähler) zieht nach — eine Abfrage, kein Raten.
    await laden()
    if (eingabeEl.value && typeof eingabeEl.value.focus === 'function') eingabeEl.value.focus()
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    eingabeFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    sendet.value = false
  }
}

/** Antworten: die Zitatzeile über der Eingabe; Senden nimmt sie mit. */
function antworten(nachricht) {
  antwortAuf.value = nachricht
  if (eingabeEl.value && typeof eingabeEl.value.focus === 'function') eingabeEl.value.focus()
}

// ── Reaktionen, Bearbeiten, Löschen ────────────────────────────────────────

async function reaktionSetzen({ nachricht, reaktion }) {
  const neu = naechsteReaktion(nachricht.reaktionen, reaktion)
  try {
    const antwort = await apiCall('chat.reaktion_setzen', { nachricht: nachricht.ident, reaktion: neu })
    const stand = Array.isArray(antwort?.reaktionen) ? antwort.reaktionen : []
    nachrichten.value = nachrichten.value.map((n) => (n.ident === nachricht.ident ? { ...n, reaktionen: stand } : n))
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  }
}

const bearbeiten = ref(null)
const bearbeitenText = ref('')
const bearbeitenLaeuft = ref(false)
const bearbeitenFehler = ref('')

function bearbeitenOeffnen(nachricht) {
  bearbeiten.value = nachricht
  bearbeitenText.value = nachricht.text || ''
  bearbeitenFehler.value = ''
}

async function bearbeitenSpeichern() {
  const ziel = bearbeiten.value
  if (!ziel || bearbeitenLaeuft.value) return
  const pruefung = pruefeText(bearbeitenText.value)
  if (!pruefung.ok) {
    bearbeitenFehler.value = pruefung.fehler
    return
  }
  bearbeitenLaeuft.value = true
  try {
    const geaendert = await apiCall('chat.aendern', { nachricht: ziel.ident, text: pruefung.text })
    const zeile = verlaufsZeile(geaendert, { ich: ich.value })
    if (zeile) nachrichten.value = nachrichten.value.map((n) => (n.ident === ziel.ident ? { ...n, ...zeile } : n))
    bearbeiten.value = null
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    bearbeitenFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  } finally {
    bearbeitenLaeuft.value = false
  }
}

async function loeschen(nachricht) {
  const ja = await bestaetigen({
    titel: 'Nachricht löschen?',
    text: 'Die Nachricht verschwindet für alle. Im Verlauf bleibt sichtbar, dass hier etwas gelöscht wurde.',
    aktion: 'Löschen',
    gefahr: true,
  })
  if (!ja) return
  try {
    const stand = await apiCall('chat.loeschen', { nachricht: nachricht.ident })
    const zeile = verlaufsZeile(stand, { ich: ich.value })
    if (zeile) nachrichten.value = nachrichten.value.map((n) => (n.ident === nachricht.ident ? { ...n, ...zeile } : n))
    await laden()
  } catch (fehler) {
    const zustand = fehlerZustand(fehler)
    verlaufFehler.value = zustand ? `${zustand.titel}. ${zustand.text}` : fehlertext(fehler)
  }
}

// ── Takt (Polling) ─────────────────────────────────────────────────────────

/** Ist der Tab sichtbar? (Nur dann darf gelesen und gefragt werden.) */
function tabSichtbar() {
  return typeof document === 'undefined' || document.hidden !== true
}

/**
 * Kurzes Polling (Karte Punkt 2): EIN Abruf von `meine_gespraeche` je Takt
 * (MUSS 4 — Liste und Zähler aus demselben Ergebnis) und der offene Verlauf,
 * ±10 s, NUR bei sichtbarem Tab. Kein WebSocket.
 *
 * MUSS 3 (Timer-Leck): Den Timer hält `taktGeber`, und der ist nach `anhalten`
 * GESTOPPT — der Aufbau wartet auf Antworten (`await laden()`), und kommt
 * `onUnmounted` dazwischen, öffnet ein spätes `starten()` keinen zweiten Timer
 * mehr. Hier steht deshalb KEIN eigenes `setInterval`/`setTimeout`.
 *
 * Backoff: nach einem Fehler wächst die Wartezeit (10 → 20 → 40 → 60 s). Der
 * Rückgabewert des Abrufs trägt sie (`dauer`), der Takt plant damit den
 * nächsten Termin; der erste Erfolg setzt auf den Grundtakt zurück.
 */
let fehlschlaege = 0

async function taktAbruf() {
  if (!aktivSeite || !modulAn.value) return undefined
  let erfolg = await laden({ still: true })
  if (aktivSeite && erfolg && kennung.value) {
    // CHAT-3a-3/B: OHNE `seit` — die volle neueste Seite (`richtung:
    // 'neueste'`). `seit` trug nur Nachrichten mit späterem Zeitstempel und
    // liess Bearbeitungen, Löschungen, Reaktionen und Lesestände sichtbarer
    // Zeilen aus. Die Zusammenführung leistet `seiteEinordnen` (bekannte
    // Zeilen ersetzen, neue hinten anhängen, `aktualisiert` zählen).
    const geladen = await verlaufLaden({ still: true })
    erfolg = geladen || erfolg
  }
  fehlschlaege = erfolg ? 0 : fehlschlaege + 1
  return { dauer: fehlschlaege ? backoffMs(fehlschlaege) : TAKT_MS }
}

const takt = taktGeber({
  takt: TAKT_MS,
  abfragen: taktAbruf,
  sichtbar: tabSichtbar,
  sichtbarkeitBeobachten: (fn) => {
    if (typeof document === 'undefined') return () => {}
    document.addEventListener('visibilitychange', fn)
    return () => document.removeEventListener('visibilitychange', fn)
  },
})

/**
 * Stand des Takts — für den Node-Test nachlesbar, ohne etwas zu raten.
 * Kein Betriebsweg.
 */
function taktStand() {
  return {
    aktiv: aktivSeite,
    gestartet: takt.istGestartet(),
    gestoppt: takt.istGestoppt(),
    fehlschlaege,
    ...takt.stand(),
  }
}
defineExpose({ taktStand })

// ── Start und Wechsel ──────────────────────────────────────────────────────

onMounted(async () => {
  aktivSeite = true
  window.addEventListener('hashchange', hashGeaendert)
  if (!modulAn.value) return
  // MUSS 4: Die Seite übernimmt den Zähler SOFORT — noch bevor sie ihre Liste
  // geholt hat. Sonst liefe in der Zwischenzeit der Takt der App-Wurzel (er
  // prüft `seiteOffen`, und das ist beim Aufbau noch nicht gesetzt) und
  // `meine_gespraeche` ginge zweimal raus. `null` = „noch keine Zahl“; der
  // App-Zähler übernimmt sie unverändert und fragt nicht selbst nach.
  mitteilungSenden(null)
  mitteilungSeite(true)
  // Erst laden und öffnen; DANN den Takt starten — steht die Seite bis dahin
  // nicht mehr (`onUnmounted` lief bereits), startet er nicht mehr (MUSS 3).
  await laden()
  if (!aktivSeite) return
  await oeffnen()
  if (!aktivSeite) return
  takt.starten()
})

onUnmounted(() => {
  aktivSeite = false
  window.removeEventListener('hashchange', hashGeaendert)
  takt.anhalten()
  // MUSS 4: Zähler wieder an die App-Wurzel zurückgeben (sie übernimmt den
  // letzten bekannten Stand und fragt im eigenen, langen Takt weiter).
  mitteilungSeite(false)
})

// Gesprächswechsel INNERHALB der Seite (Adresswechsel ohne neuen Aufbau).
// Ein Wechsel holt das neue Gespräch sofort; der Takt läuft weiter (sein
// nächster Termin ist ohnehin geplant — kein zweiter Timer).
watch(kennung, async (neu, alt) => {
  if (neu === alt || !modulAn.value || !aktivSeite) return
  fehlschlaege = 0
  if (!neu) {
    zuruecksetzen()
    return
  }
  await oeffnen()
})

</script>

<style scoped>
/* Der Bereich nimmt die verfügbare Höhe: Liste links (bis 340 px), Verlauf
   rechts. Am Handy EINE Spalte — die Seite zeigt dann entweder Liste oder
   Verlauf (Entwurf B-handy: eine Ebene, kein Seitenbaum). */
.dk-chat-bereich {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-height: 0;
  height: calc(100vh - var(--sp-8) - var(--sp-6) - var(--sp-5));
  border-radius: var(--radius-lg);
  box-shadow: var(--schatten-karte);
  background: var(--surface);
  overflow: hidden;
}
.dk-chat-liste-spalte {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: var(--rahmen-breite) solid var(--divider);
  overflow: hidden;
}
.dk-chat-verlauf-spalte {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: var(--bg-subtle);
}
.dk-chat-nichts {
  display: grid;
  place-items: center;
  height: 100%;
  padding: var(--sp-5);
}
.dk-chat-verlauf {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}
.dk-chat-verlauf-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: var(--rahmen-breite) solid var(--divider);
  background: var(--surface);
  flex: none;
}
.dk-chat-zurueck {
  display: none;
  align-items: center;
  justify-content: center;
  min-width: var(--control-h);
  min-height: var(--control-h);
  border-radius: var(--radius);
  color: var(--text);
  text-decoration: none;
  font-size: var(--fs-20);
}
.dk-chat-zurueck:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-verlauf-titel { min-width: 0; }
.dk-chat-verlauf-titel h2 {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: var(--fw-fett);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-verlauf-unter {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-chat-stumm-hinweis { color: var(--subtle); }

.dk-chat-nachrichten {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  list-style: none;
}
.dk-chat-nachrichten:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: calc(var(--rahmen-breite) * -2); }
/* Die Liste der Nachrichten INNERHALB der Log-Region (role="log" trägt keine
   <li>) — kein eigenes Layout, die Blasen tragen es. */
.dk-chat-verlaufsliste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
/* Kleiner Hinweis nach einem misslungenen Poll — ruhig, kein Alarm. */
.dk-chat-hinweis {
  margin: 0;
  padding: var(--sp-1) var(--sp-4);
  color: var(--subtle);
  font-size: var(--fs-12);
}
.dk-chat-mehr {
  align-self: center;
  border: none;
  background: none;
  color: var(--muted);
  font-size: var(--fs-12);
  font-family: inherit;
  padding: var(--sp-1) var(--sp-2);
}
.dk-chat-mehr.is-knopf { text-decoration: underline; }
/* Die schmalen Textknöpfe sind DkButton (ghost/sm) — hier nur die Schrift. */
.dk-chat-textknopf { font-size: var(--fs-12); }
.dk-chat-tag {
  list-style: none;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  color: var(--subtle);
  font-size: var(--fs-12);
  font-weight: var(--fw-mittel);
}
.dk-chat-tag::before,
.dk-chat-tag::after {
  content: '';
  height: 1px;
  background: var(--divider);
  flex: 1;
}
.dk-chat-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-4);
  color: var(--err);
  font-size: var(--fs-12);
  background: var(--err-soft);
}

/* Eingabezeile unten (Entwurf B-desktop/B-handy). */
.dk-chat-eingabe {
  flex: none;
  padding: var(--sp-3) var(--sp-4);
  border-top: var(--rahmen-breite) solid var(--divider);
  background: var(--surface);
}
.dk-chat-eingabe-zeile {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-2);
}
.dk-chat-feld {
  flex: 1;
  min-height: var(--control-h);
  max-height: calc(var(--sp-8) * 2);
  resize: vertical;
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
}
.dk-chat-feld:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-feld-gross { width: 100%; }
.dk-chat-antwortzeile {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  margin: 0 0 var(--sp-2);
  padding: var(--sp-1) var(--sp-2);
  border-left: var(--rahmen-breite) solid var(--accent);
  background: var(--surface-2);
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-chat-antwort-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dk-chat-antwort-weg {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--muted);
  font-size: var(--fs-12);
  font-family: inherit;
  cursor: pointer;
  text-decoration: underline;
}
.dk-chat-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(var(--rahmen-breite) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/* Handy: eine Spalte; die jeweils andere Ansicht ist ausgeblendet. Dieselbe
   Bedingung wie überall (`--layout-mobil`: grober Zeiger und schmal bzw. flaches
   Querformat) — „Chat ist am Handy nicht anders“, nur eine Ebene tiefer. */
@media (max-width: 720px) {
  .dk-chat-bereich {
    grid-template-columns: 1fr;
    height: calc(100vh - var(--sp-8) - var(--sp-6) - var(--sp-4));
  }
  .dk-chat-liste-spalte { border-right: none; }
  .dk-chat-bereich .nur-handy-aus { display: none; }
  .dk-chat-zurueck { display: inline-flex; }
}
</style>
