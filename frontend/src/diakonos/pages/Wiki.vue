<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Seitenkopf -->
    <DkPageHeader
      title="Wiki"
      sub="Gemeindewissen – Wissensdatenbank für alle Mitglieder"
    >
      <template #actions>
        <DkButton v-if="isAdmin" variant="primary" @click="openEditor()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Neuer Artikel
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- Suche -->
    <div class="dk-search-bar wk-suche">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input v-model="searchQuery" type="text" placeholder="Wiki durchsuchen…" />
      <kbd v-if="searchQuery" class="wk-suche-clear" @click="searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </kbd>
    </div>

    <div class="dk-two-col">
      <!-- Hauptbereich -->
      <div class="wk-main">
        <!-- Kategorien -->
        <div class="wk-cat-chips">
          <button
            v-for="c in categories"
            :key="c.id"
            class="wk-cat-chip"
            :class="{ 'is-active': activeCategory === c.id }"
            @click="activeCategory = c.id"
          >
            <span class="wk-cat-icon" :class="c.id">{{ c.icon }}</span>
            <span>{{ c.name }}</span>
            <span class="wk-cat-count">{{ articleCountByCategory[c.id] || 0 }}</span>
          </button>
        </div>

        <!-- Artikel -->
        <DkEmpty
          v-if="filteredArticles.length === 0"
          title="Keine Artikel gefunden"
          text="Suche oder Kategorie anpassen."
          icon="📖"
        />

        <div class="dk-feed">
          <div
            v-for="article in filteredArticles"
            :key="article.id"
            class="dk-content-card wk-article-card"
            @click="openArticle(article)"
          >
            <div class="wk-article-header">
              <DkBadge variant="neutral">{{ categoryName(article.category) }}</DkBadge>
              <DkBadge v-if="article.isNew" variant="ok">Neu</DkBadge>
            </div>
            <h3 class="wk-article-title">{{ article.title }}</h3>
            <p class="wk-article-excerpt">{{ article.excerpt }}</p>
            <div class="wk-article-footer">
              <div class="wk-article-meta">
                <span class="wk-article-author">
                  <div class="dk-avatar dk-avatar-sm">{{ article.authorAvatar }}</div>
                  {{ article.author }}
                </span>
                <span>bearbeitet {{ timeAgo(article.updatedAt) }}</span>
              </div>
              <div class="wk-article-tags">
                <DkBadge v-for="tag in article.tags.slice(0, 3)" :key="tag" variant="neutral">{{ tag }}</DkBadge>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Seitenspalte -->
      <aside class="dk-aside">
        <!-- Zuletzt bearbeitet -->
        <DkCard title="Zuletzt bearbeitet" flach>
          <!-- Entwicklung 16.10.: Die Zeilen standen unformatiert da (die
               Klasse `dk-widget-item` erwartet ein Symbol UND Text, hier gab
               es nur Text). Jetzt eine eigene Zeilenklasse mit Abstand,
               Trennlinie und Hover — wie in den Nachbar-Karten. -->
          <div
            v-for="a in recentlyUpdated"
            :key="a.id"
            class="wk-recent-zeile"
            role="button"
            tabindex="0"
            @click="openArticle(a)"
            @keydown.enter.prevent="openArticle(a)"
            @keydown.space.prevent="openArticle(a)"
          >
            <div class="wk-recent-body">
              <div class="wk-recent-title">{{ a.title }}</div>
              <div class="wk-recent-info">{{ a.author }} · {{ timeAgo(a.updatedAt) }}</div>
            </div>
          </div>
        </DkCard>

        <!-- Beliebte Schlagwörter -->
        <DkCard title="Beliebte Schlagwörter" flach>
          <div class="wk-tag-cloud">
            <span
              v-for="tag in popularTags"
              :key="tag.name"
              class="wk-tag-cloud-item"
              :class="{ 'is-active': searchQuery === tag.name }"
              @click="searchQuery = tag.name"
            >
              {{ tag.name }} <small>{{ tag.count }}</small>
            </span>
          </div>
        </DkCard>

        <!-- Hilfe (UXD-R21): Kontakt aus den Gemeinde-Einstellungen. Der frühere
             erfundene Platzhalter und ein Verweis auf einen Chat, den es nicht
             gibt, sind entfernt. Ist nichts hinterlegt, erscheint dieser
             Hinweis gar nicht. -->
        <DkCard v-if="hilfeKontakt" title="Hilfe &amp; Support">
          <p class="wk-help-text">
            Du findest nicht, was du suchst? Schreib eine E-Mail an die
            Gemeindeleitung:
            <a :href="`mailto:${hilfeKontakt}`">{{ hilfeKontakt }}</a>.
          </p>
        </DkCard>
      </aside>
    </div>

    <!-- Artikel-Detail -->
    <DkDialog :model-value="showArticleDetail" size="lg" :title="selectedArticle?.title || 'Artikel'"
              @update:model-value="artikelDetailSichtbar($event)">
      <div v-if="selectedArticle" class="wk-detail">
        <div class="wk-detail-header">
          <DkBadge variant="neutral">{{ categoryName(selectedArticle.category) }}</DkBadge>
          <div class="wk-detail-aktionen">
            <DkButton v-if="isAdmin" variant="ghost" size="sm" @click="openEditor(selectedArticle); artikelSchliessen()">Bearbeiten</DkButton>
            <DkButton v-if="isAdmin" variant="danger" size="sm" @click="deleteArticle(selectedArticle)">Löschen</DkButton>
          </div>
        </div>

        <div class="wk-detail-body">
          <h2 class="wk-detail-title">{{ selectedArticle.title }}</h2>
          <div class="wk-detail-meta">
            <span class="wk-article-author">
              <div class="dk-avatar dk-avatar-sm">{{ selectedArticle.authorAvatar }}</div>
              {{ selectedArticle.author }}
            </span>
            <span>Zuletzt bearbeitet: {{ formatDate(selectedArticle.updatedAt) }}</span>
            <div class="wk-detail-tags">
              <DkBadge v-for="tag in selectedArticle.tags" :key="tag" variant="neutral">{{ tag }}</DkBadge>
            </div>
          </div>
          <div class="wk-detail-content" v-html="sanitize(selectedArticle.content)" />

          <!-- Ähnliche Artikel -->
          <div v-if="relatedArticles.length > 0" class="wk-related">
            <h4>Ähnliche Artikel</h4>
            <div class="wk-related-list">
              <div
                v-for="ra in relatedArticles"
                :key="ra.id"
                class="wk-related-item"
                @click="openArticle(ra)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>{{ ra.title }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <DkButton variant="ghost" @click="artikelSchliessen">Schließen</DkButton>
      </template>
    </DkDialog>

    <!-- Editor (Verwaltung) -->
    <DkDialog :model-value="showEditor" :before-close="editorSchutz.darfSchliessen" size="lg"
              :title="editingArticle ? 'Artikel bearbeiten' : 'Neuer Wiki-Artikel'"
              @update:model-value="showEditor = $event">
      <form class="wk-editor" @submit.prevent="saveArticle">
        <DkField label="Titel" required :error="editorFehler.titel">
          <input ref="titelFeld" maxlength="140" v-model="editorForm.title" class="dk-ui-eingabe" type="text" placeholder="Titel des Artikels" required />
        </DkField>
        <div class="dk-form-row">
          <DkField label="Kategorie">
            <DkSelect v-model="editorForm.category" :options="kategorieOptionen" />
          </DkField>
          <DkField label="Tags (kommagetrennt)" help="z. B. Tonanlage, Beamer, Anleitung">
            <input v-model="editorForm.tags" class="dk-ui-eingabe" type="text" placeholder="Tonanlage, Beamer, Anleitung…" />
          </DkField>
        </div>
        <DkField label="Vorschautext">
          <textarea v-model="editorForm.excerpt" class="dk-ui-eingabe" rows="2" placeholder="Kurze Beschreibung…" />
        </DkField>
        <DkField label="Inhalt" help="HTML erlaubt.">
          <textarea v-model="editorForm.content" class="dk-ui-eingabe" rows="10" placeholder="Artikel-Inhalt (HTML erlaubt)…" />
        </DkField>
      </form>
      <template #footer>
        <DkButton variant="ghost" @click="editorSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="saving" @click="saveArticle">Speichern</DkButton>
      </template>
    </DkDialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import DOMPurify from 'dompurify'
import { apiCall } from '../composables/useApi.js'
import { suchNormal } from '../composables/bf1Anzeige.js'
import { showToast } from '../composables/useToast.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useSession } from '../composables/useSession.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import { getRouteParam } from '../router.js'

function sanitize(html) { return DOMPurify.sanitize(html || '') }

const { isAdmin } = useSession()

/* ─── Categories ─── */
const categories = [
  { id: 'all', name: 'Alle', icon: '★' },
  { id: 'technik', name: 'Technik', icon: '⚙️' },
  { id: 'ablaeufe', name: 'Abläufe', icon: '📋' },
  { id: 'raeume', name: 'Räume', icon: '🏢' },
  { id: 'kontakte', name: 'Kontakte', icon: '📞' },
  { id: 'faq', name: 'FAQ', icon: '❓' },
]

/* ─── State ─── */
const articles = ref([])
const activeCategory = ref('all')
const searchQuery = ref('')
const showArticleDetail = ref(false)
const selectedArticle = ref(null)
const showEditor = ref(false)
const editingArticle = ref(null)
const saving = ref(false)
const titelFeld = ref(null)
// UXD-R22: Fehler am Titel-Feld statt nur als Meldung.
const editorFehler = ref({ titel: '' })

const editorForm = ref({
  title: '', category: 'technik', tags: '', excerpt: '', content: ''
})

// UXD-R21: Kontaktadresse der Gemeindeleitung aus den Gemeinde-Einstellungen.
// Ohne hinterlegte Adresse bleibt der Hilfe-Hinweis ausgeblendet — kein
// erfundener Platzhalter mehr.
const hilfeKontakt = ref('')
async function ladenHilfeKontakt() {
  if (!isAdmin.value) {
    // Auch Nicht-Admins sehen nur, was die Einstellungen hergeben; der
    // öffentliche Kontakt steckt im Boot-Objekt, sonst bleibt es leer.
    hilfeKontakt.value = window.__DIakonosBOOT?.gemeinde_kontakt_email || ''
    return
  }
  try {
    const res = await apiCall('diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen', {})
    const d = res.message || res
    hilfeKontakt.value = d?.kontakt_email || ''
  } catch {
    hilfeKontakt.value = ''
  }
}

const editorSchutz = useFormularSchutz(() => editorForm.value, () => saving.value)
async function editorSchliessen() {
  if (await editorSchutz.darfSchliessen()) showEditor.value = false
}

/* Bausteine beschicken */
const kategorieOptionen = computed(() =>
  categories.filter(c => c.id !== 'all').map(c => ({ value: c.id, label: c.name })))

/* ─── API ─── */
async function loadArticles() {
  const params = {}
  if (activeCategory.value && activeCategory.value !== 'all') params.kategorie = activeCategory.value
  if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
  const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_liste', params)
  if (res) articles.value = res
}

async function openArticle(article) {
  showArticleDetail.value = true
  selectedArticle.value = { ...article, content: '' }
  // UXD-R20: der geöffnete Artikel bekommt eine eigene, teilbare Adresse.
  // P3-1b (W2): Die Adresse wird mit `history.replaceState` nachgeführt, NICHT
  // per `navigate`. Ein Hashwechsel löste einen Routenwechsel aus, und weil
  // App.vue die Seite mit `:key="currentHash"` rendert, wurde Wiki bei jedem
  // Klick neu aufgebaut: Suche und Filter gingen verloren, Liste und Artikel
  // wurden doppelt geladen. `replaceState` ändert die Adresse ohne Ereignis —
  // teilbar und lesbar bleibt sie trotzdem.
  artikelAdresseSetzen(article?.id)
  const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_detail', { artikel_id: article.id })
  if (res) selectedArticle.value = res
}

/** Artikel-Kennung in die Adresse schreiben (ohne Routenwechsel). */
function artikelAdresseSetzen(id) {
  const ziel = id ? `#/wiki/${encodeURIComponent(id)}` : '#/wiki'
  if (window.location.hash === ziel) return
  window.history.replaceState(null, '', ziel)
}

/**
 * Artikel schließen: Adresse zurück auf „#/wiki“ (P3-1b, W2).
 *
 * Vorher blieb „#/wiki/<id>“ stehen — ein Neuladen öffnete den eben
 * geschlossenen Artikel wieder. Der Weg über `replaceState` vermeidet auch
 * hier den Neuaufbau der Seite.
 */
function artikelSchliessen() {
  showArticleDetail.value = false
  selectedArticle.value = null
  artikelAdresseSetzen(null)
}

/** Schließen über den Dialog selbst (Esc, Klick daneben, Kreuz). */
function artikelDetailSichtbar(offen) {
  if (offen) { showArticleDetail.value = true; return }
  artikelSchliessen()
}

/**
 * UXD-R20: Beim Öffnen von „#/wiki/‹Kennung›“ (geteilter Link, Lesezeichen)
 * wird der Artikel direkt geladen. Unbekannte Kennung → verständlicher Hinweis,
 * kein stiller Wechsel auf das Dashboard.
 */
async function artikelAusAdresse() {
  const id = getRouteParam('id', 'Wiki')
  if (!id) return
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_detail', { artikel_id: id })
    if (res) {
      selectedArticle.value = res
      showArticleDetail.value = true
    } else {
      showToast('Dieser Wiki-Artikel wurde nicht gefunden.', 'error')
    }
  } catch {
    showToast('Dieser Wiki-Artikel wurde nicht gefunden.', 'error')
  }
}

async function saveArticle() {
  const f = editorForm.value
  if (saving.value) return
  if (!f.title.trim()) {
    // UXD-R22: Fehler AM FELD (nicht nur als Toast) und Fokus dorthin.
    editorFehler.value = { titel: 'Bitte gib einen Titel ein.' }
    showToast('Bitte gib einen Titel ein.', 'error')
    titelFeld.value?.focus()
    return
  }
  editorFehler.value = { titel: '' }
  saving.value = true
  try {
    if (editingArticle.value) {
      const res = await apiCall('diakronos.diakonos.api.wiki.update_wiki_artikel', {
        artikel_id: editingArticle.value.id,
        titel:      f.title.trim(),
        inhalt:     f.content,
        kategorie:  f.category,
        tags:       f.tags.trim(),
        auszug:     f.excerpt.trim(),
      })
      if (res?.success) {
        showToast('Artikel gespeichert.', 'success')
        showEditor.value = false
        await loadArticles()
      }
    } else {
      const res = await apiCall('diakronos.diakonos.api.wiki.create_wiki_artikel', {
        titel:     f.title.trim(),
        inhalt:    f.content,
        kategorie: f.category,
        tags:      f.tags.trim(),
        auszug:    f.excerpt.trim(),
      })
      if (res?.artikel_id) {
        showToast('Artikel erstellt.', 'success')
        showEditor.value = false
        await loadArticles()
      }
    }
  } catch (e) {
    showToast(e.message || 'Artikel konnte nicht gespeichert werden.', 'error')
  } finally {
    saving.value = false
  }
}

async function deleteArticle(article) {
  if (!(await bestaetigen({ titel: 'Artikel löschen?', text: `„${article.title}“ wird unwiderruflich gelöscht.`, aktion: 'Löschen', gefahr: true }))) return
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.delete_wiki_artikel', { artikel_id: article.id })
    if (res?.success) {
      showToast('Artikel gelöscht.', 'success')
      artikelSchliessen()
      await loadArticles()
    }
  } catch (e) {
    showToast(e.message || 'Artikel konnte nicht gelöscht werden.', 'error')
  }
}

onMounted(async () => {
  await loadArticles()
  ladenHilfeKontakt()
  await artikelAusAdresse()
})

/* ─── Computed ─── */
const filteredArticles = computed(() => {
  let list = articles.value
  if (activeCategory.value !== 'all') {
    list = list.filter(a => a.category === activeCategory.value)
  }
  if (searchQuery.value.trim()) {
    // BF1-J/W8: umlaut- und gross-klein-unabhaengig — dieselbe Faltung wie
    // in der Mitgliedersuche ("mueller" findet "Müller").
    const q = suchNormal(searchQuery.value)
    list = list.filter(a =>
      suchNormal(a.title).includes(q) ||
      suchNormal(a.excerpt).includes(q) ||
      (a.tags || []).some(t => suchNormal(t).includes(q))
    )
  }
  return list
})

const articleCountByCategory = computed(() => {
  const counts = {}
  articles.value.forEach(a => { counts[a.category] = (counts[a.category] || 0) + 1 })
  // DES-R16: „Alle" zeigte immer 0 — jeder Artikel wird gezählt, der
  // Kategorie-Schlüssel „all" hatte nie eine Zählung.
  counts.all = articles.value.length
  return counts
})

const recentlyUpdated = computed(() => articles.value.slice(0, 5))

const popularTags = computed(() => {
  const tagCounts = {}
  articles.value.forEach(a => {
    (a.tags || []).forEach(t => { tagCounts[t] = (tagCounts[t] || 0) + 1 })
  })
  return Object.entries(tagCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12)
})

const relatedArticles = computed(() => {
  if (!selectedArticle.value) return []
  return articles.value
    .filter(a => a.id !== selectedArticle.value.id &&
      (a.tags || []).some(t => (selectedArticle.value.tags || []).includes(t)))
    .slice(0, 3)
})

/* ─── Helpers ─── */
function categoryName(id) {
  return categories.find(c => c.id === id)?.name || id
}
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
}
function timeAgo(d) {
  const now = new Date()
  const then = new Date(d)
  const diff = Math.floor((now - then) / (1000 * 60 * 60 * 24))
  if (diff === 0) return 'heute'
  if (diff === 1) return 'gestern'
  if (diff < 7) return `vor ${diff} Tagen`
  if (diff < 30) return `vor ${Math.floor(diff / 7)} Wochen`
  return `vor ${Math.floor(diff / 30)} Monaten`
}
function openEditor(article = null) {
  editingArticle.value = article
  editorFehler.value = { titel: '' }
  editorForm.value = article
    ? { title: article.title, category: article.category, tags: (article.tags || []).join(', '), excerpt: article.excerpt || '', content: article.content || '' }
    : { title: '', category: 'technik', tags: '', excerpt: '', content: '' }
  editorSchutz.merken()
  showEditor.value = true
}
</script>

<style scoped>
/* Suche */
.wk-suche { margin-bottom: var(--sp-4); }
.wk-suche-clear { cursor: pointer; }

/* Kategorien */
.wk-cat-chips { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin-bottom: var(--sp-5); }
.wk-cat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--sp-3);
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--fast) var(--ease);
}
.wk-cat-chip:hover { border-color: var(--line-strong); background: var(--surface-hover); }
.wk-cat-chip.is-active { background: var(--primary); color: var(--primary-ink); border-color: var(--primary); }
.wk-cat-icon { font-size: var(--fs); line-height: 1; }
.wk-cat-count {
  font-size: var(--fs-xs);
  font-weight: 600;
  background: var(--surface-2);
  padding: 1px 6px;
  border-radius: var(--badge-r);
  color: var(--muted);
}
.wk-cat-chip.is-active .wk-cat-count { background: color-mix(in oklch, var(--primary-ink) 22%, transparent); color: var(--primary-ink); }

/* Artikel */
.wk-article-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: var(--pad);
  cursor: pointer;
  transition: box-shadow var(--med) var(--ease), border-color var(--med) var(--ease), transform var(--med) var(--ease);
  box-shadow: var(--shadow);
}
.wk-article-card:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.wk-article-header { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-2); }
.wk-article-title { font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); margin: 0 0 var(--sp-1); }
.wk-article-excerpt {
  font-size: var(--fs-sm);
  color: var(--muted);
  line-height: 1.5;
  margin: 0 0 var(--sp-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.wk-article-footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--sp-2); }
.wk-article-meta { display: flex; align-items: center; gap: var(--sp-3); font-size: var(--fs-sm); color: var(--muted); }
.wk-article-author { display: flex; align-items: center; gap: 6px; }
.wk-article-tags { display: flex; gap: var(--sp-1); }

/* Seitenspalte */
.wk-recent-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-1);
  border-bottom: 1px solid var(--line);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.wk-recent-zeile:last-child { border-bottom: none; }
.wk-recent-zeile:hover { background: var(--surface-hover); }
.wk-recent-body { flex: 1; min-width: 0; }
.wk-recent-title { font-size: var(--fs-sm); font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wk-recent-info { font-size: var(--fs-xs); color: var(--muted); margin-top: 1px; }

.wk-tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; }
.wk-tag-cloud-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: all var(--fast) var(--ease);
}
.wk-tag-cloud-item:hover { background: var(--surface-hover); color: var(--text); }
.wk-tag-cloud-item.is-active { background: var(--primary); color: var(--primary-ink); }
.wk-tag-cloud-item small { opacity: 0.7; }

.wk-help-text { font-size: var(--fs-sm); color: var(--muted); line-height: 1.6; margin: 0; }
.wk-help-text a { color: var(--primary); text-decoration: none; }
.wk-help-text a:hover { text-decoration: underline; }

/* Detail */
.wk-detail { max-height: 70vh; overflow-y: auto; }
.wk-detail-header { display: flex; align-items: center; justify-content: space-between; padding-bottom: var(--sp-3); border-bottom: 1px solid var(--divider); }
.wk-detail-aktionen { display: flex; gap: var(--sp-2); align-items: center; }
.wk-detail-body { padding: var(--sp-4) 0 0; }
.wk-detail-title { font-size: var(--fs-h2); font-weight: 700; color: var(--text); margin: 0 0 var(--sp-2); }
.wk-detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: var(--sp-4);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--divider);
}
.wk-detail-tags { display: flex; flex-wrap: wrap; gap: var(--sp-1); }
.wk-detail-content { font-size: var(--fs); line-height: 1.7; color: var(--text); }
.wk-detail-content :deep(p) { margin: 0 0 var(--sp-3); }
.wk-detail-content :deep(ul) { margin: 0 0 var(--sp-3) var(--sp-5); padding: 0; }
.wk-detail-content :deep(li) { margin-bottom: var(--sp-1); }
.wk-detail-content :deep(h3) { font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); margin: var(--sp-5) 0 var(--sp-2); }
.wk-detail-content :deep(a) { color: var(--primary); text-decoration: none; }
.wk-detail-content :deep(a:hover) { text-decoration: underline; }
.wk-detail-content :deep(table) { width: 100%; border-collapse: collapse; }
.wk-detail-content :deep(td) { padding: var(--sp-2); border-bottom: 1px solid var(--divider); }
.wk-detail-content :deep(strong) { color: var(--text); }

/* Ähnliche Artikel */
.wk-related { margin-top: var(--sp-6); padding-top: var(--sp-5); border-top: 1px solid var(--divider); }
.wk-related h4 { font-size: var(--fs-h4); font-weight: var(--fw-h); color: var(--text); margin: 0 0 var(--sp-3); }
.wk-related-list { display: flex; flex-direction: column; gap: 6px; }
.wk-related-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text);
  font-size: var(--fs-sm);
  cursor: pointer;
  transition: background var(--fast) var(--ease);
}
.wk-related-item:hover { background: var(--surface-hover); }
.wk-related-item svg { color: var(--muted); flex-shrink: 0; }

/* Editor */
.wk-editor { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
