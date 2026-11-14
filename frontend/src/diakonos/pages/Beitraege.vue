<template>
  <div ref="rootEl" class="dk-screen dk-screen-enter">

    <!-- Seitenkopf -->
    <DkPageHeader
      title="Beiträge"
      sub="Interner Gemeindebrief – Neuigkeiten & Ankündigungen"
      :actions-label="null"
    >
      <template #actions>
        <!-- R6: Anlegen darf, wer in mindestens einer (Unter-)Gruppe `anlegen`
             hat. Das weiß allein der Server: die Einheiten werden beim Laden
             der Seite EINMAL gefragt (`useAnlegenMitGruppe`), der Knopf
             erscheint nur, wenn mindestens eine sie bejaht hat. -->
        <DkButton v-if="darfAnlegen" variant="primary" :loading="anlegenLaeuft" @click="openEditor()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Neuer Beitrag
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- Filter -->
    <div class="dk-filters bt-filter">
      <!-- K4 (DES-REST-b): Dieselbe Filterzeile wie in Gruppen, Ressourcen und
           Liedgruppen. Vorher war dies ein DkSegment — neben vier Chip-Zeilen
           die zweite Optik für dieselbe Aufgabe. -->
      <DkFilterChips
        :chips="kategorieChips"
        :model-value="activeCategory"
        aria-label="Nach Kategorie filtern"
        @waehlen="activeCategory = $event"
      />
      <div class="dk-search-bar bt-suche">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <!-- FIX-3: kurzer Platzhalter, damit er neben den Chips NICHT
             abgeschnitten wird; der volle Text steht im aria-label. -->
        <input
          v-model="searchQuery"
          type="text"
          aria-label="Beiträge durchsuchen"
          placeholder="Suchen…"
        />
      </div>
    </div>

    <div class="dk-two-col">
      <!-- Beitragsliste -->
      <div class="dk-feed">
        <!-- OP-UI-19/S10: Laden, kein Treffer und „noch nichts da“ sind drei
             verschiedene Fälle. Vorher stand bei 0 Beiträgen „Suche oder
             Filter anpassen.“ — ein Rat, der nichts zu suchen hatte. -->
        <DkSkelett v-if="postsLadenSkelett" form="zeilen" :anzahl="4" text="Beiträge werden geladen …" />
        <DkEmpty
          v-else-if="filteredPosts.length === 0"
          icon="📰"
          :title="leerZustand.title"
          :text="leerZustand.text"
        >
          <DkButton v-if="filterAktiv" variant="ghost" size="md" @click="filterZuruecksetzen">Filter zurücksetzen</DkButton>
        </DkEmpty>

        <article
          v-for="post in filteredPosts"
          :key="post.id"
          class="dk-content-card bt-post"
          role="link"
          tabindex="0"
          :data-id="post.id"
          :aria-label="`Beitrag lesen: ${post.title || 'ohne Titel'}`"
          @click="oeffnenPost(post)"
          @keydown.enter.self.prevent="oeffnenPost(post)"
          @keydown.space.self.prevent="oeffnenPost(post)"
          @contextmenu.prevent="zeilenKontextmenue($event, post)"
        >
          <div v-if="post.image" class="bt-post-image" :style="{ backgroundImage: `url(${post.image})` }">
            <DkBadge class="bt-post-cat" variant="akzent">{{ categoryName(post.category) }}</DkBadge>
          </div>
          <div v-else class="bt-post-image bt-post-image--placeholder" :class="`cat-${post.category}`">
            <DkBadge class="bt-post-cat" variant="akzent">{{ categoryName(post.category) }}</DkBadge>
          </div>
          <!-- UX2e (Entwurf B1, N6): Objekt-Aktionen am Beitrag im „⋯"-Menü;
               die Karte bleibt ganz klickbar. -->
          <span class="bt-post-aktionen">
            <DkAktionen
              :ref="el => setzeAktion(el, post)"
              :eintraege="aktionenFuerPost(post)"
              :label="`Aktionen für ${post.title || 'diesen Beitrag'}`"
            />
          </span>

          <div class="bt-post-body">
            <h3 class="bt-post-title">{{ post.title }}</h3>
            <p class="bt-post-excerpt">{{ post.excerpt }}</p>
            <div class="bt-post-meta">
              <div class="bt-post-author">
                <div class="dk-avatar dk-avatar-sm">{{ post.authorAvatar }}</div>
                <span>{{ post.author }}</span>
              </div>
              <span class="bt-post-date">{{ formatDate(post.date) }}</span>
              <span class="bt-post-comments">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                {{ post.comments }}
              </span>
            </div>
          </div>
        </article>
      </div>

      <!-- Seitenspalte -->
      <aside class="dk-aside">
        <!-- Beliebt -->
        <DkCard title="Beliebte Beiträge" flach>
          <div
            v-for="p in popularPosts"
            :key="p.id"
            class="dk-widget-item bt-popular"
            @click="oeffnenPost(p)"
          >
            <div class="bt-popular-num">{{ p.rank }}</div>
            <div class="bt-popular-body">
              <div class="bt-popular-title">{{ p.title }}</div>
              <div class="bt-popular-date">{{ formatDate(p.date) }}</div>
            </div>
          </div>
        </DkCard>

        <!-- Kategorien -->
        <DkCard title="Kategorien" flach>
          <div class="bt-cat-list">
            <div
              v-for="c in categories.filter(c => c.id !== 'all')"
              :key="c.id"
              class="bt-cat-item"
              @click="activeCategory = c.id"
            >
              <span class="bt-cat-dot" :class="c.id" />
              <span class="bt-cat-name">{{ c.name }}</span>
              <span class="bt-cat-count">{{ postCountByCategory[c.id] || 0 }}</span>
            </div>
          </div>
        </DkCard>

        <!-- Archiv -->
        <DkCard title="Archiv" flach>
          <div class="bt-archive-list">
            <div
              v-for="a in archiveMonths"
              :key="a.key"
              class="bt-archive-item"
            >
              <span>{{ a.label }}</span>
              <span class="bt-archive-count">{{ a.count }}</span>
            </div>
          </div>
        </DkCard>
      </aside>
    </div>

    <!-- MT-7: Lesen ist eine eigene Unterseite (#/beitraege/<Kennung>,
         pages/BeitragDetail.vue) — kein Fenster mehr an dieser Stelle. -->

    <!-- UI-R6d: Die Detail-Knöpfe (Für Gäste freigeben / Bearbeiten / Löschen)
         stehen seit MT-7 auf der Leseseite (pages/BeitragDetail.vue) — hier
         gibt es kein Detail-Fenster mehr. -->

    <!-- Editor (Verwaltung) -->
    <DkDialog :model-value="showEditor" :before-close="editorSchutz.darfSchliessen" size="lg"
              :title="editingPost ? 'Beitrag bearbeiten' : 'Neuer Beitrag'"
              @update:model-value="showEditor = $event">
      <!-- OP-UI-23: Enter im Feld speichert (wie der Knopf). -->
      <form class="bt-editor" @submit.prevent="savePost">
        <!-- R6: gewählte Gruppe. Beim Anlegen fest (die Auswahl ist davor
             gelaufen); beim Bearbeiten nur zur Information — die Zuordnung
             eines bestehenden Beitrags ändert dieser Dialog nicht. -->
        <div v-if="!editingPost && gewaehlteEinheit" class="bt-einheit">
          <span class="bt-einheit-label">Für</span>
          <strong class="bt-einheit-text">{{ einheitAnzeige }}</strong>
        </div>
        <DkField label="Titel" required :error="editorFehler.titel">
          <input maxlength="140" v-model="editorForm.title" class="dk-ui-eingabe" type="text" placeholder="Titel des Beitrags" required />
        </DkField>
        <div class="dk-form-row">
          <DkField label="Kategorie">
            <DkSelect v-model="editorForm.category" :options="kategorieOptionen" />
          </DkField>
          <DkField label="Bild-URL" help="Leer lassen, wenn kein Bild.">
            <input v-model="editorForm.image" class="dk-ui-eingabe" type="text" placeholder="https://…" />
          </DkField>
        </div>
        <DkField label="Vorschautext">
          <textarea v-model="editorForm.excerpt" class="dk-ui-eingabe" rows="2" placeholder="Kurze Zusammenfassung…" />
        </DkField>
        <DkField label="Inhalt">
          <textarea v-model="editorForm.content" class="dk-ui-eingabe" rows="8" placeholder="Vollständiger Inhalt…" />
        </DkField>
        <!-- BS-1d (U3): Freigabe für die Website. Der Server schaltet sie über
             `website.beitrag_auf_website`; wirksam wird sie nur zusammen mit
             „veröffentlicht“. Ausschalten geht ohne Rückfrage, Einschalten
             fragt nach (G1: nichts wird ohne Willen öffentlich). -->
        <div v-if="editingPost && darfWebsite" class="bt-website">
          <DkCheckbox
            :model-value="aufWebsite"
            :disabled="savingPost || websiteLaeuft"
            @update:model-value="websiteUmschalten"
          >
            Auf Website zeigen
          </DkCheckbox>
          <p class="bt-website-hilfe">
            Nur zusammen mit „veröffentlicht“ sichtbar. Titel, Vorschautext und
            Inhalt erscheinen dann auf der Website — Personenangaben nicht.
          </p>
        </div>
        <p v-else-if="darfWebsite" class="bt-website-hilfe">
          Die Freigabe für die Website lässt sich nach dem ersten Speichern setzen.
        </p>
      </form>
      <template #footer>
        <DkButton variant="secondary" @click="editorSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" :disabled="savingPost" @click="savePost">Speichern</DkButton>
      </template>
    </DkDialog>

    <!-- R6: Auswahl der Gruppe beim Anlegen (nur geprüfte Einheiten). Der
         Dialog erklärt selbst, wenn es nichts zu wählen gibt. -->
    <GruppeWaehlen
      v-model="auswahlOffen"
      :optionen="optionen"
      :startwert="startwert"
      :laden="auswahlLaden"
      was="Beitrag"
      label="Beitrag anlegen für"
      hilfe="Sichtbar wird der Beitrag für die Mitglieder dieser Gruppe."
      @waehlen="beitragAnlegen"
    />

    <!-- R6: Gast-Link für einen Beitrag. -->
    <GastFreigabe
      :model-value="gastOffen"
      typ="beitrag"
      :objekt="gastObjekt?.id || ''"
      :titel="gastObjekt?.title || ''"
      @update:model-value="gastOffen = $event"
    />

  </div>
</template>

<script setup>
/**
 * Beitraege — interner Gemeindebrief im Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Filter, Beitraege, Dialoge und Formulare
 * kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { useWebsiteFreigaben } from '../composables/useWebsiteFreigaben.js'
import { darfFreigabenVerwalten } from '../../shared/website-freigaben.mjs'
import { suchNormal } from '../composables/bf1Anzeige.js'
// MT-7: Lesen wechselt die Route (eigene Unterseite statt Fenster).
import { navigate } from '../router.js'
// MT-7b: Merker für den Rückweg — die Liste schreibt ihre volle Adresse hier
// hinein, bevor sie einen Beitrag öffnet.
import { adresseImVerlaufSetzen, rueckwegKennung, rueckwegMerken } from '../composables/zurueckWege.mjs'
import { chipsAus } from '../composables/filterChips.mjs'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
// UX2c (C2): Löschen ohne Rückfrage, dafür „Rückgängig“ (Stapel + Strg+Z).
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import DkCheckbox from '../components/ui/DkCheckbox.vue'
// UX2e: EIN Aktionsmenü „⋯" für alle Listen (Entwurf B1).
import DkAktionen from '../components/ui/DkAktionen.vue'
// R6: Gruppe wählen + Gast-Links.
import GruppeWaehlen from '../components/r6/GruppeWaehlen.vue'
import GastFreigabe from '../components/r6/GastFreigabe.vue'
import { useAnlegenMitGruppe } from '../composables/useAnlegenMitGruppe.js'
import { einheitText } from '../composables/r6Gastzugang.mjs'
import { darfBearbeiten as serverErlaubtBearbeiten } from '../composables/r6Detail.js'

const { rollen } = useSession()
// UX2c (C2): der Rückgängig-Weg dieser Seite (Stapel-Eintrag + Meldung).
const { mitRueckgaengig } = useRueckgaengigAktion()
// BS-1d: Website-Schalter nur für Website-Rollen (Server antwortet sonst 403).
const darfWebsite = computed(() => darfFreigabenVerwalten({ rollen: rollen.value }))

/* ─── Kategorien ─── */
const categories = [
  { id: 'all', name: 'Alle' },
  { id: 'ankuendigung', name: 'Ankündigung' },
  { id: 'gottesdienst', name: 'Gottesdienst' },
  { id: 'jugend', name: 'Jugend' },
  { id: 'gemeindeleben', name: 'Gemeindeleben' },
  { id: 'allgemein', name: 'Allgemein' },
]

/* ─── Zustand ─── */
// MT-7: eigener Weg zurück zur Liste — das Ziel von „‹ zurück“ auf der
// Leseseite. EINE Schreibweise, auch im Verlaufs-Merkmal (`zurueckWege.mjs`).
const ZURUECK_ZIEL = '#/beitraege'
/** Wurzel der Seite — für den Fokus auf die zuletzt geöffnete Karte (MT-7b). */
const rootEl = ref(null)
const posts = ref([])
const activeCategory = ref('alle')
const searchQuery = ref('')
// MT-7: kein Detail-Fenster mehr — der geöffnete Beitrag ist eine eigene Seite.
const showEditor = ref(false)
const editingPost = ref(null)
const savingPost = ref(false)
// UXD-R22: Fehler am Titel-Feld statt nur als Meldung.
const editorFehler = ref({ titel: '' })

const editorForm = ref({
  title: '', category: 'allgemein', image: '', excerpt: '', content: ''
})

/* ─── R6: Anlegen in einer (Unter-)Gruppe, Freigabe für Gäste ─────────────
 * Die Seite entscheidet keine Rechte. Die Orte, an denen diese Person anlegen
 * darf (samt Titel und Reihenfolge), kommen aus EINER Serverantwort:
 * `api.rechte.get_anlegeorte` (über `useAnlegenOrte`, Pfad aus
 * `whitelist.json`). `darf_bearbeiten` trägt der LISTENEintrag
 * (`get_beitraege_liste`) — die Lese-Unterseite (`pages/BeitragDetail.vue`)
 * bekommt es seit UI-R6e direkt aus ihrer Detail-Antwort (R-12l).
 */
const {
  optionen, auswahlOffen, auswahlLaden, startwert, darfAnlegen,
  rechteLaden, starten: anlegenStarten,
} = useAnlegenMitGruppe('beitrag')
// Einheit, für die der Editor gerade offen ist (beim Bearbeiten: leer).
const gewaehlteEinheit = ref(null)
const anlegenLaeuft = ref(false)
/**
 * Was im Editor unter „Für“ steht: der `titel` des Servers.
 *
 * UI-R6c: Nur der Titel — kein eigener Gemeinde-Text und keine zusammengesetzte
 * Kennung mehr (`einheitText` in `r6Gastzugang.mjs` liefert nichts anderes).
 */
const einheitAnzeige = computed(() => einheitText(gewaehlteEinheit.value))

// Der Auswahl-Dialog meldet die Wahl über `@waehlen` — erst dann steht die
// Einheit fest und der Editor darf aufgehen.
//
// UI-R6c: Der Dialog gibt den GANZEN Ort zurück (`ortAusWert`, inklusive
// Server-`titel`) — genau wie `anlegenStarten` bei genau einer Möglichkeit.
// Hier wird deshalb nichts mehr nachgeschlagen oder zusammengesetzt: der Titel
// im Editor ist der des Servers (oder leer, wenn der Server keinen nannte).
function beitragAnlegen(ort) {
  auswahlOffen.value = false
  openEditor(null, ort)
}

/**
 * Hat der Server Bearbeiten für diesen Beitrag erlaubt?
 * Regel in `composables/r6Detail.js` (eine Wahrheit für Beiträge und Wiki).
 */
const darfBearbeiten = serverErlaubtBearbeiten

/* Gast-Link-Dialog (nur für Einträge mit `darf_bearbeiten`). */
const gastOffen = ref(false)
const gastObjekt = ref(null)
function gastFreigeben(post) {
  if (!darfBearbeiten(post)) return
  gastObjekt.value = post
  gastOffen.value = true
}

/* ─── Bausteine beschicken ─── */
// K4: Chip-Zeile aus dem gemeinsamen Baustein — dieselbe Form wie in Gruppen,
// Ressourcen und Liedgruppen. Die Zahl am Chip setzt `DkFilterChips` selbst
// aus `anzahl`; die Beschriftung bleibt deshalb der reine Name.
const kategorieChips = computed(() => chipsAus(
  posts.value.map(p => ({ kategorie: p.category })),
  (p) => p.kategorie,
  null,
  { alleLabel: 'Alle', leerLabel: 'Ohne Kategorie' },
))
const kategorieOptionen = computed(() =>
  categories.filter(c => c.id !== 'all').map(c => ({ value: c.id, label: c.name })))
const postsLaden = ref(true)
// UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht.
const { skelettSichtbar: postsLadenSkelett } = useLadeSkelett(postsLaden)
const filterAktiv = computed(() => activeCategory.value !== 'alle' || !!String(searchQuery.value || '').trim())
const leerZustand = computed(() => (
  filterAktiv.value
    ? { title: 'Keine Beiträge gefunden', text: 'Für diese Suche gibt es keinen Beitrag. Setze den Filter zurück, um alle zu sehen.' }
    : { title: 'Noch keine Beiträge', text: 'Sobald jemand etwas veröffentlicht, erscheint es hier.' }
))

/** OP-UI-19: Der Weg zurück aus einem leeren Suchergebnis. */
function filterZuruecksetzen() {
  activeCategory.value = 'alle'
  searchQuery.value = ''
}

/* ─── Data Loading ─── */
async function loadPosts() {
  postsLaden.value = true
  try {
    posts.value = await apiCall('diakronos.diakonos.api.beitraege.get_beitraege_liste')
  } catch (err) {
    showToast('Beiträge konnten nicht geladen werden', 'error')
  } finally {
    postsLaden.value = false
  }
}

/**
 * MT-7b: Die vollständige Adresse der Liste — Suche und Kategorie kommen aus
 * dem Zustand der Seite (nicht aus der Adresse: nach `?bearbeiten=` steht dort
 * weniger). Das Ergebnis ist die Adresse des Listen-Eintrags im Verlauf und das
 * Ziel von „‹ zurück“ auf der Leseseite.
 *
 * RUHZUSTAND (Review-Punkt 2): Sowohl `kategorie=alle` als auch `q=` werden
 * AUSGESCHRIEBEN — sonst bliebe `?q=Beamer` stehen, wenn der Nutzer den Filter
 * danach zurücksetzt, und „zurück“ brächte einen längst aufgehobenen Filter
 * wieder mit. Eine leere Suche steht als `q=` da.
 */
function beitraegeListenAdresse() {
  const teile = [`kategorie=${encodeURIComponent(activeCategory.value || 'alle')}`]
  const suche = String(searchQuery.value || '').trim()
  if (suche) teile.push(`q=${encodeURIComponent(suche)}`)
  else teile.push('q=')
  return '#/beitraege' + `?${teile.join('&')}`
}

/**
 * MT-7b (Review-Punkt 2): Die Filter in den EIGENEN Verlaufs-Eintrag
 * schreiben, während der Nutzer tippt/filtert (wie `Lieder.vue`). Dann trägt
 * der Listen-Eintrag die Suche schon, wenn ein Eintrag geöffnet wird —
 * Browser-„Zurück“ landet auf der gefilterten Liste.
 */
watch([activeCategory, searchQuery], () => { adresseImVerlaufSetzen(beitraegeListenAdresse()) })

/**
 * MT-7: Lesen ist eine eigene Unterseite mit eigener Adresse
 * (`#/beitraege/<Kennung>` → pages/BeitragDetail.vue). Die Liste lädt keinen
 * Detailtext mehr und öffnet kein Fenster — ein Klick ist ein Routenwechsel,
 * damit der Zurück-Knopf des Browsers zur Liste führt.
 *
 * MT-7b (Review-Punkt 2): Suche und Kategorie gehen auch beim BROWSER-Zurück
 * nicht verloren. Vor dem Sprung wird die vollständige Listen-Adresse (mit
 * `?q=`/`?kategorie=`) in den EIGENEN Verlaufs-Eintrag geschrieben
 * (`adresseImVerlaufSetzen` → `replaceState`, kein neuer Eintrag, wie
 * `Lieder.vue`); die Liste übernimmt sie beim Aufbau aus der Adresse. Zusätzlich
 * liegt sie im Merker (`rueckwegMerken`, mit der Kennung für den Fokus) — Ziel
 * von „‹ zurück“ auf der Leseseite.
 */
function oeffnenPost(post) {
  if (!post?.id) return
  const adresse = beitraegeListenAdresse()
  adresseImVerlaufSetzen(adresse)
  rueckwegMerken(adresse, ZURUECK_ZIEL, post.id)
  navigate(`#/beitraege/${encodeURIComponent(post.id)}`)
}


/**
 * MT-7b (Review-Punkt 4): Nach dem Aufbau den Fokus auf den Eintrag legen, den
 * der Nutzer zuletzt geöffnet hatte (Zurück von der Leseseite). Ohne das steht
 * der Fokus nach dem Neuaufbau auf `body` und die Seite oben — bei einer langen
 * Liste ist die Stelle verloren. `scrollIntoView` bringt die Karte in Sicht.
 */
async function fokusWiederherstellen() {
  const kennung = rueckwegKennung(ZURUECK_ZIEL)
  if (!kennung) return
  await nextTick()
  const karte = [...(rootEl.value?.querySelectorAll?.('[data-id]') || [])]
    .find((el) => el.getAttribute('data-id') === String(kennung))
  if (!karte) return
  karte.focus?.({ preventScroll: true })
  karte.scrollIntoView?.({ block: 'center' })
}

/**
 * MT-7 (Review-Punkt 3, Regression): Die Leseseite springt zum Bearbeiten
 * hierher (`#/beitraege?bearbeiten=<Kennung>`) — der Editor ist ein Fenster
 * dieser Liste. Vorher wertete die Liste den Teil nicht aus, „Bearbeiten“ im
 * Menü der Leseseite öffnete also NICHTS. Die Kennung wird sofort wieder aus
 * der Adresse genommen (`replaceState`, kein neuer Verlaufseintrag), damit ein
 * Neuladen oder „zurück“ das Fenster nicht erneut aufreißt.
 *
 * Liegt der Beitrag nach dem Laden nicht in der Liste (Papierkorb, inzwischen
 * gelöscht), sagt die Meldung das — sonst geschähe nach dem Klick gar nichts.
 */
async function bearbeitenAusAdresse() {
  const hash = String(window.location.hash || '')
  const frage = hash.indexOf('?')
  if (frage === -1) return
  const teile = new URLSearchParams(hash.slice(frage + 1))
  const kennung = teile.get('bearbeiten')
  if (!kennung) return
  // Teil aus der Adresse nehmen — VOR dem Laden, damit kein zweiter Aufbau ihn
  // erneut liest (`replaceState` erzeugt keinen Routenwechsel).
  teile.delete('bearbeiten')
  const rest = teile.toString()
  try { window.history.replaceState(window.history.state, '', `#/beitraege${rest ? `?${rest}` : ''}`) } catch { /* Verlauf nicht verfügbar */ }

  let post = posts.value.find((p) => String(p.id) === String(kennung))
  if (!post) {
    // Die Liste wurde ohne ausreichende Felder geladen? EIN Nachladen, dann
    // erneut suchen — erst danach gilt der Beitrag als nicht vorhanden.
    await loadPosts()
    post = posts.value.find((p) => String(p.id) === String(kennung))
  }
  if (!post) {
    showToast('Der Beitrag ist nicht mehr vorhanden. Lade die Liste neu.', 'error')
    return
  }
  await bearbeitenPost(post)
}

/**
 * MT-7b (Review-Punkt A): Beim Aufbau der Liste Suche und Kategorie aus ihrer
 * Adresse übernehmen. Die Leseseite schickt den Nutzer mit der vollen
 * Listen-Adresse zurück (`#/beitraege?kategorie=…&q=…`); die App baut die
 * Seite dabei neu auf — ohne diesen Schritt stünden Filter und Suchbegriff
 * wieder auf Anfang. Der Ruhezustand heißt in der Adresse `kategorie=alle`
 * (so schreibt ihn `beitraegeListenAdresse`).
 */
function listenZustandUebernehmen() {
  activeCategory.value = 'alle'
  searchQuery.value = ''
  const hash = String(window.location.hash || '')
  const frage = hash.indexOf('?')
  if (frage === -1) return
  const teile = new URLSearchParams(hash.slice(frage + 1))
  const kategorie = teile.get('kategorie')
  if (kategorie === 'alle') activeCategory.value = 'alle'
  else if (kategorie && categories.some(c => c.id === kategorie)) activeCategory.value = kategorie
  const suche = teile.get('q')
  if (suche) searchQuery.value = suche
}

/**
 * MT-7b (Review-Punkt E): Vorher liefen `loadPosts()` und
 * `bearbeitenAusAdresse()` GLEICHZEITIG — bei `?bearbeiten=` sah die Auswertung
 * eine noch leere Liste, lud sie ein zweites Mal nach und die Seite holte die
 * Liste überflüssig zweimal. Jetzt erst Filter aus der Adresse, dann EINMAL
 * laden, danach auswerten; `bearbeitenAusAdresse()` lädt nur noch nach, wenn
 * der Beitrag im Ergebnis fehlt.
 */
onMounted(async () => {
  // UI-R6d: Beim Laden der Seite EINMAL fragen, wo diese Person anlegen darf —
  // der Kopfknopf hängt daran (ohne Möglichkeit erscheint er nicht).
  // `rechteLaden` öffnet NICHTS; der Auswahl-Dialog gehört zum Klick.
  rechteLaden().catch(() => {})
  listenZustandUebernehmen()
  await loadPosts()
  await fokusWiederherstellen()
  await bearbeitenAusAdresse()
})

/* ─── Computed ─── */
const filteredPosts = computed(() => {
  let list = posts.value
  if (activeCategory.value !== 'alle') {
    list = list.filter(p => p.category === activeCategory.value)
  }
  if (searchQuery.value.trim()) {
    // BF1-J/W8: umlaut- und gross-klein-unabhaengig.
    const q = suchNormal(searchQuery.value)
    list = list.filter(p =>
      suchNormal(p.title).includes(q) ||
      suchNormal(p.excerpt).includes(q) ||
      suchNormal(p.author).includes(q)
    )
  }
  return list.sort((a, b) => new Date(b.date) - new Date(a.date))
})

const postCountByCategory = computed(() => {
  const counts = {}
  posts.value.forEach(p => { counts[p.category] = (counts[p.category] || 0) + 1 })
  return counts
})

const popularPosts = computed(() => {
  return [...posts.value]
    .sort((a, b) => b.comments - a.comments)
    .slice(0, 5)
    .map((p, i) => ({ ...p, rank: i + 1 }))
})

const archiveMonths = computed(() => {
  const map = {}
  posts.value.forEach(p => {
    const d = new Date(p.date)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!map[key]) map[key] = { key, label: d.toLocaleString('de-DE', { month: 'long', year: 'numeric' }), count: 0 }
    map[key].count++
  })
  return Object.values(map).sort((a, b) => b.key.localeCompare(a.key))
})

/* ─── Helpers ─── */
function categoryName(id) {
  return categories.find(c => c.id === id)?.name || id
}
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
}
const editorSchutz = useFormularSchutz(() => editorForm.value, () => savingPost.value)

/* ─── BS-1d (U3): Website-Freigabe des Beitrags ───────────────────────────
 * Der Schalter steht im Editor, geschaltet wird er über
 * `website.beitrag_auf_website` (POST über `apiCall`, CSRF) — NICHT über
 * `update_beitrag`. Deshalb bewahrt `openEditor` den Stand aus der Liste, und
 * `savePost` schickt ihn nicht mit.
 */
const { beitragSetzen } = useWebsiteFreigaben()
const websiteLaeuft = ref(false)
const aufWebsite = ref(false)

async function websiteUmschalten(wert) {
  if (!editingPost.value || websiteLaeuft.value) return
  const an = wert === true
  if (an && !(await bestaetigen({
    titel: 'Beitrag auf der Website zeigen?',
    text: `„${editingPost.value.title}“ erscheint auf der Website, sobald er zusätzlich `
      + 'veröffentlicht ist. Titel, Vorschautext, Inhalt und Bild des Beitrags werden dabei '
      + 'öffentlich — Personenangaben (Autor, Kommentare) nicht.',
    aktion: 'Freigeben',
  }))) return
  websiteLaeuft.value = true
  const ergebnis = await beitragSetzen(editingPost.value.id, an)
  websiteLaeuft.value = false
  if (!ergebnis.ok) {
    showToast(ergebnis.fehler, 'error')
    return
  }
  aufWebsite.value = an
  const eintrag = posts.value.find((p) => p.id === editingPost.value.id)
  if (eintrag) eintrag.auf_website = an
  showToast(an ? 'Beitrag steht auf der Website' : 'Beitrag von der Website genommen')
}

async function editorSchliessen() {
  if (await editorSchutz.darfSchliessen()) showEditor.value = false
}
/**
 * Editor öffnen.
 *
 * R6: OHNE `post` UND ohne bereits gewählte Einheit ist das der Weg des
 * Kopfknopfes „+ Neuer Beitrag“ — dann wird ZUERST die (Unter-)Gruppe geklärt
 * (`anlegenStarten`), denn ein Beitrag ohne Gruppe ist gemeindeweit und damit
 * dem Administrator vorbehalten. Gibt es genau eine Möglichkeit, steht sie
 * sofort fest; bei mehreren öffnet sich die Auswahl und ruft diese Funktion
 * mit `einheit` erneut auf.
 */
async function openEditor(post = null, einheit = null) {
  if (!post && !einheit) {
    if (anlegenLaeuft.value) return
    anlegenLaeuft.value = true
    try {
      const sofort = await anlegenStarten()
      if (sofort) await openEditor(null, sofort)
    } finally {
      anlegenLaeuft.value = false
    }
    return
  }
  editingPost.value = post
  editorFehler.value = { titel: '' }
  // R6: beim Anlegen die gewählte (Unter-)Gruppe; beim Bearbeiten keine.
  gewaehlteEinheit.value = post ? null : einheit
  // BS-1d: Stand der Website-Freigabe aus der Liste (Default AUS) — der
  // Schalter ist NICHT Teil des Formulars und wird nicht mitgespeichert.
  aufWebsite.value = post?.auf_website === true
  editorForm.value = post
    ? { title: post.title, category: post.category, image: post.image || '', excerpt: post.excerpt, content: post.content || '' }
    : { title: '', category: 'allgemein', image: '', excerpt: '', content: '' }
  editorSchutz.merken()
  showEditor.value = true
}
async function savePost() {
  const f = editorForm.value
  if (savingPost.value) return
  if (!f.title.trim()) {
    // UXD-R22: Fehler am Feld (nicht nur als Meldung) und Fokus dorthin.
    editorFehler.value = { titel: 'Bitte gib einen Titel ein.' }
    showToast('Bitte gib einen Titel ein.', 'error')
    document.querySelector('.bt-editor input')?.focus()
    return
  }
  editorFehler.value = { titel: '' }
  savingPost.value = true
  try {
    if (editingPost.value) {
      await apiCall('diakronos.diakonos.api.beitraege.update_beitrag', {
        beitrag_id: editingPost.value.id,
        titel: f.title, inhalt: f.content, kategorie: f.category,
        auszug: f.excerpt, bild: f.image || '',
      })
      showToast('Beitrag aktualisiert')
    } else {
      // R6: OHNE Gruppe legt nur der Administrator an — der Server antwortet
      // sonst 403 mit genau dieser Erklärung (`aktionsfehler` zeigt sie).
      await apiCall('diakronos.diakonos.api.beitraege.create_beitrag', {
        titel: f.title, inhalt: f.content, kategorie: f.category,
        auszug: f.excerpt, bild: f.image || '',
        gruppe: gewaehlteEinheit.value?.gruppe || null,
        untergruppe: gewaehlteEinheit.value?.untergruppe || null,
      })
      showToast('Beitrag erstellt')
    }
    showEditor.value = false
    await loadPosts()
  } catch (err) {
    showToast(aktionsfehler('speichern', err), 'error')
  } finally {
    savingPost.value = false
  }
}
async function deletePost(post) {
  /* UX2c (C2 · Prinzip I2): Löschen ist UMKEHRBAR (Papierkorb, 7 Tage) —
     also KEINE Rückfrage mehr, sondern sofort ausführen und „Rückgängig“
     anbieten (10 s = `ANZEIGE_MS`, Strg+Z, Meldung mit der Frist aus UX2b). */
  try {
    const antwort = await apiCall('diakronos.diakonos.api.beitraege.delete_beitrag', { beitrag_id: post.id })
    await loadPosts()
    await mitRueckgaengig({
      beschreibung: papierkorbMeldung(post.title, antwort?.wiederherstellbar_bis),
      zurueck: () => wiederherstellen('beitrag', post.id),
      danach: loadPosts,
      erfolg: `„${post.title}“ wiederhergestellt.`,
    })
  } catch (err) {
    showToast(aktionsfehler('löschen', err), 'error')
  }
}
/* ── UX2e · Aktionsmenü „⋯" an jedem Beitrag (Entwurf B1, N6/K4) ─────────
   Die Karte hat bisher KEINE Aktion getragen (Bearbeiten/Löschen lagen im
   Detail-Dialog). Jetzt stehen sie am Eintrag:
     · Beitrag öffnen        (immer)
     · Für Gäste freigeben   (`darf_bearbeiten`)
     · Bearbeiten            (`darf_bearbeiten`)
     · Löschen               (`darf_bearbeiten`, gefährlich, abgesetzt am Ende)
   R6: Das Recht kommt aus der Serverantwort (`darf_bearbeiten` — HV/MV der
   Gruppe bzw. GL), NICHT aus `isAdmin`. Der Server prüft jeden Aufruf erneut. */
const aktionRefs = new Map()
const postSchluessel = (p) => String(p?.id ?? '')
function setzeAktion(el, p) {
  const schluessel = postSchluessel(p)
  if (!schluessel) return
  if (el) aktionRefs.set(schluessel, el)
  else aktionRefs.delete(schluessel)
}

async function bearbeitenPost(post) {
  // Der Bearbeiten-Dialog braucht den vollen Beitrag (Inhalt), die Liste
  // liefert nur die Vorschau — deshalb erst den Detailaufruf.
  try {
    const detail = await apiCall('diakronos.diakonos.api.beitraege.get_beitrag_detail', { beitrag_id: post.id })
    openEditor({ ...post, ...detail })
  } catch (err) {
    showToast(aktionsfehler('laden', err), 'error')
  }
}

async function loeschenPost(post) {
  // EIN Löschweg (S4): derselbe Aufruf wie auf der Leseseite
  // (pages/BeitragDetail.vue) — Papierkorb, „Rückgängig“ statt Rückfrage.
  await deletePost(post)
}

function aktionenFuerPost(post) {
  const eintraege = [{
    key: 'oeffnen', label: 'Beitrag öffnen', icon: 'ansehen',
    aktion: () => oeffnenPost(post),
  }]
  if (darfBearbeiten(post)) {
    eintraege.push({
      key: 'gast', label: 'Für Gäste freigeben', icon: 'freigeben',
      aktion: () => gastFreigeben(post),
    })
    eintraege.push({
      key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten',
      aktion: () => bearbeitenPost(post),
    })
    eintraege.push({
      key: 'loeschen', label: 'Löschen', icon: 'loeschen',
      gefahr: true,
      aktion: () => loeschenPost(post),
    })
  }
  return eintraege
}

/** Rechtsklick auf die Beitragskarte öffnet dasselbe Menü. */
function zeilenKontextmenue(ereignis, post) {
  aktionRefs.get(postSchluessel(post))?.oeffnenFuerZeile(ereignis, ereignis?.currentTarget)
}
</script>

<style scoped>
/* Beitragsliste */
.bt-post {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow var(--med) var(--ease), border-color var(--med) var(--ease), transform var(--med) var(--ease);
  box-shadow: var(--shadow);
}
.bt-post:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

/* UX2e: Das „⋯" der Beitragskarte sitzt oben rechts (über dem Bild) und
   bleibt für alle sichtbar, die die Karte bedienen dürfen. Die Bildfläche
   hält den Platz frei. */
.bt-post { position: relative; }
.bt-post-aktionen {
  position: absolute;
  top: var(--sp-1);
  right: var(--sp-1);
  z-index: 2;
}
.bt-post-aktionen :deep(.dk-ui-aktionen-ausloeser) {
  background: var(--surface);
  box-shadow: var(--shadow);
}

.bt-post-image {
  height: 180px;
  background-size: cover;
  background-position: center;
  position: relative;
}
.bt-post-image--placeholder {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  background: var(--surface-2);
}
.bt-post-image--placeholder.cat-ankuendigung  { background: color-mix(in oklch, var(--dk-cat-ankuendigung) 16%, var(--surface-2)); }
.bt-post-image--placeholder.cat-gottesdienst  { background: color-mix(in oklch, var(--dk-cat-gottesdienst) 16%, var(--surface-2)); }
.bt-post-image--placeholder.cat-jugend        { background: color-mix(in oklch, var(--dk-cat-jugend) 16%, var(--surface-2)); }
.bt-post-image--placeholder.cat-gemeindeleben { background: color-mix(in oklch, var(--dk-cat-gemeindeleben) 16%, var(--surface-2)); }
.bt-post-image--placeholder.cat-allgemein     { background: color-mix(in oklch, var(--dk-cat-allgemein) 16%, var(--surface-2)); }

.bt-post-cat { position: absolute; top: var(--sp-3); left: var(--sp-3); }

.bt-post-body { padding: var(--pad); }
.bt-post-title {
  font-size: var(--fs-h3);
  font-weight: var(--fw-h);
  color: var(--text);
  margin: 0 0 var(--sp-1);
  line-height: 1.35;
}
.bt-post-excerpt {
  font-size: var(--fs-sm);
  color: var(--muted);
  line-height: 1.5;
  margin: 0 0 var(--sp-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bt-post-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.bt-post-author { display: flex; align-items: center; gap: var(--sp-2); }
.bt-post-comments { display: inline-flex; align-items: center; gap: var(--sp-1); margin-left: auto; }

/* Seitenspalte */
.bt-filter {
  margin-bottom: var(--sp-5);
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  /* FIX-3: KEIN Umbruch. Vorher (flex-wrap: wrap) rutschte das Suchfeld bei
     344 px in die naechste Zeile, weil die 4 Chips 296 px belegten — Feld und
     Chip waren dann zwar gleich hoch, standen aber untereinander. Jetzt bleibt
     alles in EINER Zeile: die Chips duerfen seitlich scrollen, das Feld
     behaelt seine Breite (flex: none). */
  flex-wrap: nowrap;
}
/* FIX-3: Höhe kommt aus --filter-h (index.css: .dk-search-bar, .dk-ui-chip).
   Breite: am Desktop nimmt das Feld den Rest (max 280 px), am Handy eine feste
   Spalte, damit die Chip-Zeile daneben scrollen kann statt umzubrechen. */
.bt-suche { max-width: 280px; flex: 1 1 auto; min-width: 140px; align-self: center; margin-bottom: 0; }

@media (max-width: 700px) {
  /* Am Handy: Chips scrollen waagerecht, das Feld steht rechts daneben. */
  .bt-filter { align-items: center; }
  .bt-filter > .dk-ui-chips {
    flex: 1 1 auto;
    min-width: 0;
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none;
    align-items: center;
  }
  .bt-filter > .dk-ui-chips::-webkit-scrollbar { display: none; }
  /* FIX-3: schmal (Rest der Zeile), aber breit genug fuer den Platzhalter
     „Beiträge durchsuchen…“ — 100 px schnitten ihn ab. */
  .bt-suche { flex: 0 0 148px; min-width: 148px; max-width: none; align-self: center; margin-bottom: 0; }
}

.bt-popular-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-xs);
  font-weight: 700;
  flex-shrink: 0;
}
.bt-popular-body { flex: 1; min-width: 0; }
.bt-popular-title {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bt-popular-date { font-size: var(--fs-xs); color: var(--muted); margin-top: 1px; }

.bt-cat-list { display: flex; flex-direction: column; gap: var(--sp-1); }
.bt-cat-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px var(--sp-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--fast) var(--ease);
}
.bt-cat-item:hover { background: var(--surface-hover); }
.bt-cat-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.bt-cat-dot.ankuendigung  { background: var(--dk-cat-ankuendigung); }
.bt-cat-dot.gottesdienst  { background: var(--dk-cat-gottesdienst); }
.bt-cat-dot.jugend        { background: var(--dk-cat-jugend); }
.bt-cat-dot.gemeindeleben { background: var(--dk-cat-gemeindeleben); }
.bt-cat-dot.allgemein     { background: var(--dk-cat-allgemein); }
.bt-cat-name { flex: 1; font-size: var(--fs-sm); color: var(--text); }
.bt-cat-count {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--muted);
  background: var(--surface-2);
  padding: 1px 7px;
  border-radius: var(--badge-r);
}

.bt-archive-list { display: flex; flex-direction: column; gap: var(--sp-1); }
.bt-archive-item {
  display: flex;
  justify-content: space-between;
  padding: 6px var(--sp-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  color: var(--text);
  cursor: pointer;
  transition: background var(--fast) var(--ease);
}
.bt-archive-item:hover { background: var(--surface-hover); }
.bt-archive-count { color: var(--muted); font-weight: 500; }

/* MT-7: Die Regeln des Beitrags-Fensters (.bt-detail*, .bt-comments,
   .bt-comment*) sind mit dem Fenster entfallen — Lesen ist die eigene Seite
   pages/BeitragDetail.vue. */

/* Editor */
.bt-editor { display: flex; flex-direction: column; gap: var(--sp-3); }
/* R6: gewählte Gruppe beim Anlegen — eine Zeile, ruhig, ohne Rahmen. */
.bt-einheit { display: flex; align-items: baseline; gap: var(--sp-2); font-size: var(--fs-sm); }
.bt-einheit-label { color: var(--muted); }
.bt-einheit-text { color: var(--text); }
/* BS-1d (U3): Website-Freigabe im Editor — Schalter mit kurzer Erklärung. */
.bt-website { display: grid; gap: var(--sp-1); }
.bt-website-hilfe { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
</style>