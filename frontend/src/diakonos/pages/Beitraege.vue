<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Seitenkopf -->
    <DkPageHeader
      title="Beiträge"
      sub="Interner Gemeindebrief – Neuigkeiten & Ankündigungen"
      :actions-label="null"
    >
      <template #actions>
        <DkButton v-if="isAdmin" variant="primary" @click="openEditor()">
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
          <DkButton v-if="filterAktiv" variant="ghost" size="sm" @click="filterZuruecksetzen">Filter zurücksetzen</DkButton>
        </DkEmpty>

        <article
          v-for="post in filteredPosts"
          :key="post.id"
          class="dk-content-card bt-post"
          @click="openPost(post)"
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
            @click="openPost(p)"
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

    <!-- Beitrags-Detail -->
    <DkDialog :model-value="showPostDetail" size="lg" :title="selectedPost?.title || 'Beitrag'"
              @update:model-value="showPostDetail = $event">
      <div v-if="selectedPost" class="bt-detail">
        <div v-if="selectedPost.image" class="bt-detail-image" :style="{ backgroundImage: `url(${selectedPost.image})` }" />
        <div v-else class="bt-detail-image bt-detail-image--placeholder" :class="`cat-${selectedPost.category}`" />

        <div class="bt-detail-body">
          <DkBadge class="bt-detail-cat" variant="akzent">{{ categoryName(selectedPost.category) }}</DkBadge>
          <h2 class="bt-detail-title">{{ selectedPost.title }}</h2>
          <div class="bt-detail-meta">
            <div class="bt-post-author">
              <div class="dk-avatar dk-avatar-sm">{{ selectedPost.authorAvatar }}</div>
              <span>{{ selectedPost.author }}</span>
            </div>
            <span>{{ formatDate(selectedPost.date) }}</span>
          </div>
          <div class="bt-detail-content" v-html="sanitize(selectedPost.content)" />

          <!-- Kommentare -->
          <div class="bt-comments">
            <h4>Kommentare ({{ selectedPost.comments }})</h4>
            <div v-for="c in selectedPost.commentList" :key="c.id" class="bt-comment">
              <div class="dk-avatar dk-avatar-md">{{ c.avatar }}</div>
              <div class="bt-comment-body">
                <div class="bt-comment-header">
                  <strong>{{ c.author }}</strong>
                  <span>{{ formatDate(c.date) }}</span>
                </div>
                <p>{{ c.text }}</p>
              </div>
            </div>
            <div class="bt-comment-form">
              <input v-model="newComment" type="text" placeholder="Kommentar schreiben…" @keyup.enter="addComment" />
              <DkButton variant="primary" size="sm" :disabled="addingComment" :loading="addingComment" @click="addComment">Absenden</DkButton>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <DkButton v-if="isAdmin && selectedPost" variant="danger" size="sm" @click="deletePost(selectedPost)">Löschen</DkButton>
        <DkButton variant="ghost" @click="showPostDetail = false">Schließen</DkButton>
      </template>
    </DkDialog>

    <!-- Editor (Verwaltung) -->
    <DkDialog :model-value="showEditor" :before-close="editorSchutz.darfSchliessen" size="lg"
              :title="editingPost ? 'Beitrag bearbeiten' : 'Neuer Beitrag'"
              @update:model-value="showEditor = $event">
      <!-- OP-UI-23: Enter im Feld speichert (wie der Knopf). -->
      <form class="bt-editor" @submit.prevent="savePost">
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

  </div>
</template>

<script setup>
/**
 * Beitraege — interner Gemeindebrief im Design-System „A · Ruhig & Klar“.
 * Reiner Darstellungsumbau: Kopf, Filter, Beitraege, Dialoge und Formulare
 * kommen aus components/ui; Farben nur aus tokens.css.
 */
import { ref, computed, onMounted } from 'vue'
import DOMPurify from 'dompurify'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { useWebsiteFreigaben } from '../composables/useWebsiteFreigaben.js'
import { darfFreigabenVerwalten } from '../../shared/website-freigaben.mjs'
import { suchNormal } from '../composables/bf1Anzeige.js'
import { chipsAus } from '../composables/filterChips.mjs'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { loeschFrage, papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
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

function sanitize(html) { return DOMPurify.sanitize(html || '') }

const { isAdmin, rollen } = useSession()
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
const posts = ref([])
const activeCategory = ref('alle')
const searchQuery = ref('')
const showPostDetail = ref(false)
const selectedPost = ref(null)
const showEditor = ref(false)
const editingPost = ref(null)
const newComment = ref('')
const savingPost = ref(false)
const addingComment = ref(false)
// UXD-R22: Fehler am Titel-Feld statt nur als Meldung.
const editorFehler = ref({ titel: '' })

const editorForm = ref({
  title: '', category: 'allgemein', image: '', excerpt: '', content: ''
})

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

async function openPost(post) {
  try {
    const detail = await apiCall('diakronos.diakonos.api.beitraege.get_beitrag_detail', { beitrag_id: post.id })
    selectedPost.value = {
      ...detail,
      authorAvatar: (detail.author || '').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || '?',
    }
    showPostDetail.value = true
  } catch (err) {
    showToast('Beitrag konnte nicht geladen werden', 'error')
  }
}

onMounted(loadPosts)

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
function openEditor(post = null) {
  editingPost.value = post
  editorFehler.value = { titel: '' }
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
      await apiCall('diakronos.diakonos.api.beitraege.create_beitrag', {
        titel: f.title, inhalt: f.content, kategorie: f.category,
        auszug: f.excerpt, bild: f.image || '',
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
  // UX2b: kein „unwiderruflich“ mehr — der Beitrag landet im Papierkorb
  // (7 Tage wiederherstellbar). Die Meldung nennt die Frist; „Rückgängig“
  // holt ihn über `beitraege.wiederherstellen_beitrag` zurück.
  if (!(await bestaetigen(loeschFrage(post.title, 'Beitrag')))) return
  try {
    const antwort = await apiCall('diakronos.diakonos.api.beitraege.delete_beitrag', { beitrag_id: post.id })
    showPostDetail.value = false
    selectedPost.value = null
    await loadPosts()
    await showToast(papierkorbMeldung(post.title, antwort?.wiederherstellbar_bis), 'success', { text: 'Rückgängig', onClick: async () => {
      const ergebnis = await wiederherstellen('beitrag', post.id)
      if (ergebnis.ok) {
        showToast(`„${post.title}“ wiederhergestellt.`)
        await loadPosts()
      } else {
        showToast(ergebnis.fehler, 'error')
      }
    } })
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}
/* ── UX2e · Aktionsmenü „⋯" an jedem Beitrag (Entwurf B1, N6/K4) ─────────
   Die Karte hat bisher KEINE Aktion getragen (Bearbeiten/Löschen lagen im
   Detail-Dialog). Jetzt stehen sie am Eintrag:
     · Beitrag öffnen        (immer)
     · Bearbeiten            (Admin)
     · Löschen               (Admin, gefährlich, abgesetzt am Ende)
   Rechte: dieselben wie MF3 (isAdmin) — der Server prüft erneut. */
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
  // Dieselbe Rückfrage und derselbe Serveraufruf wie im Detail-Dialog.
  // `selectedPost` NICHT vorher setzen: das Detail-Fenster hängt an dessen
  // Inhalt (Titel/Teilnehmer) und würde beim Löschen kurz aufgehen.
  await deletePost(post)
}

function aktionenFuerPost(post) {
  const eintraege = [{
    key: 'oeffnen', label: 'Beitrag öffnen', icon: 'ansehen',
    aktion: () => openPost(post),
  }]
  if (isAdmin.value) {
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

async function addComment() {
  // UXD-R11: Doppelklick erzeugte zwei Kommentare — `addingComment` wurde
  // gesetzt, aber nie geprüft.
  if (addingComment.value) return
  if (!newComment.value.trim() || !selectedPost.value) return
  addingComment.value = true
  try {
    const res = await apiCall('diakronos.diakonos.api.beitraege.create_kommentar', {
      beitrag_id: selectedPost.value.id,
      text: newComment.value.trim(),
    })
    if (res.success) {
      selectedPost.value.commentList = selectedPost.value.commentList || []
      selectedPost.value.commentList.push(res.kommentar)
      selectedPost.value.comments = (selectedPost.value.comments || 0) + 1
      newComment.value = ''
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  } finally {
    addingComment.value = false
  }
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

/* Detail */
.bt-detail { max-height: 70vh; overflow-y: auto; }
.bt-detail-image {
  height: 220px;
  background-size: cover;
  background-position: center;
  position: relative;
}
.bt-detail-image--placeholder.cat-ankuendigung  { background: color-mix(in oklch, var(--dk-cat-ankuendigung) 16%, var(--surface-2)); }
.bt-detail-image--placeholder.cat-gottesdienst  { background: color-mix(in oklch, var(--dk-cat-gottesdienst) 16%, var(--surface-2)); }
.bt-detail-image--placeholder.cat-jugend        { background: color-mix(in oklch, var(--dk-cat-jugend) 16%, var(--surface-2)); }
.bt-detail-image--placeholder.cat-gemeindeleben { background: color-mix(in oklch, var(--dk-cat-gemeindeleben) 16%, var(--surface-2)); }
.bt-detail-image--placeholder.cat-allgemein     { background: color-mix(in oklch, var(--dk-cat-allgemein) 16%, var(--surface-2)); }

.bt-detail-body { padding: var(--sp-4) 0 0; }
.bt-detail-cat { margin-bottom: var(--sp-2); }
.bt-detail-title {
  font-size: var(--fs-h2);
  font-weight: 700;
  color: var(--text);
  margin: 0 0 var(--sp-2);
  line-height: 1.3;
}
.bt-detail-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: var(--sp-alt-20);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--divider);
}
.bt-detail-content { font-size: var(--fs); line-height: 1.7; color: var(--text); max-width: var(--lesebreite); }
.bt-detail-content :deep(p) { margin: 0 0 var(--sp-3); }
.bt-detail-content :deep(ul) { margin: 0 0 var(--sp-3) var(--sp-alt-20); padding: 0; }
.bt-detail-content :deep(li) { margin-bottom: var(--sp-1); }
.bt-detail-content :deep(strong) { color: var(--text); }

/* Kommentare */
.bt-comments { margin-top: var(--sp-5); padding-top: var(--sp-alt-20); border-top: 1px solid var(--divider); }
.bt-comments h4 { font-size: var(--fs-h4); font-weight: var(--fw-h); color: var(--text); margin: 0 0 var(--sp-3); }
.bt-comment { display: flex; gap: var(--sp-3); padding: var(--sp-3) 0; border-bottom: 1px solid var(--divider); }
.bt-comment:last-child { border-bottom: none; }
.bt-comment-body { flex: 1; }
.bt-comment-header { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-1); }
.bt-comment-header strong { font-size: var(--fs-sm); color: var(--text); }
.bt-comment-header span { font-size: var(--fs-xs); color: var(--muted); }
.bt-comment-body p { font-size: var(--fs-sm); color: var(--muted); margin: 0; }

.bt-comment-form { display: flex; gap: var(--sp-2); margin-top: var(--sp-3); }
.bt-comment-form input {
  flex: 1;
  padding: 8px var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs-sm);
  font-family: inherit;
}
.bt-comment-form input:focus { outline: none; border-color: var(--accent); }

/* Editor */
.bt-editor { display: flex; flex-direction: column; gap: var(--sp-3); }
/* BS-1d (U3): Website-Freigabe im Editor — Schalter mit kurzer Erklärung. */
.bt-website { display: grid; gap: var(--sp-1); }
.bt-website-hilfe { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
</style>