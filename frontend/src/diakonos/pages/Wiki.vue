<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Wiki</h1>
        <p class="dk-screen-sub">Gemeindewissen – Wissensdatenbank für alle Mitglieder</p>
      </div>
      <button v-if="isAdmin" class="dk-btn dk-btn-primary" @click="openEditor()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Neuer Artikel
      </button>
    </div>

    <!-- Search Bar -->
    <div class="wk-search-bar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      <input v-model="searchQuery" type="text" placeholder="Wiki durchsuchen…" />
      <kbd v-if="searchQuery" class="wk-search-clear" @click="searchQuery = ''">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </kbd>
    </div>

    <div class="wk-layout">
      <!-- Main Content -->
      <div class="wk-main">
        <!-- Categories -->
        <div class="wk-categories">
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

        <!-- Articles -->
        <div v-if="filteredArticles.length === 0" class="dk-empty">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <p>Keine Artikel gefunden.</p>
        </div>

        <div class="wk-articles">
          <div
            v-for="article in filteredArticles"
            :key="article.id"
            class="wk-article-card"
            @click="openArticle(article)"
          >
            <div class="wk-article-header">
              <span class="wk-article-cat" :class="article.category">{{ categoryName(article.category) }}</span>
              <span v-if="article.isNew" class="wk-article-badge">Neu</span>
            </div>
            <h3 class="wk-article-title">{{ article.title }}</h3>
            <p class="wk-article-excerpt">{{ article.excerpt }}</p>
            <div class="wk-article-footer">
              <div class="wk-article-meta">
                <span class="wk-article-author">
                  <div class="wk-avatar">{{ article.authorAvatar }}</div>
                  {{ article.author }}
                </span>
                <span class="wk-article-date">bearbeitet {{ timeAgo(article.updatedAt) }}</span>
              </div>
              <div class="wk-article-tags">
                <span v-for="tag in article.tags.slice(0, 3)" :key="tag" class="wk-tag">{{ tag }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar -->
      <aside class="wk-sidebar">
        <!-- Recently Updated -->
        <div class="wk-widget">
          <h4>Zuletzt bearbeitet</h4>
          <div
            v-for="a in recentlyUpdated"
            :key="a.id"
            class="wk-recent"
            @click="openArticle(a)"
          >
            <div class="wk-recent-body">
              <div class="wk-recent-title">{{ a.title }}</div>
              <div class="wk-recent-info">{{ a.author }} · {{ timeAgo(a.updatedAt) }}</div>
            </div>
          </div>
        </div>

        <!-- Popular Tags -->
        <div class="wk-widget">
          <h4>Beliebte Schlagwörter</h4>
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
        </div>

        <!-- Quick Help -->
        <div class="wk-widget wk-widget--info">
          <h4>Hilfe & Support</h4>
          <p class="wk-help-text">
            Du findest nicht was du suchst? Frag im 
            <a href="#/gruppen">Gemeinde-Chat</a> nach oder kontaktiere das 
            <a href="mailto:sekretariat@gemeinde.de">Sekretariat</a>.
          </p>
        </div>
      </aside>
    </div>

    <!-- Article Detail Modal -->
    <div v-if="showArticleDetail" class="dk-modal-overlay" @click.self="showArticleDetail = false">
      <div class="dk-modal dk-modal--lg">
        <div v-if="selectedArticle" class="wk-detail">
          <div class="wk-detail-header">
            <span class="wk-detail-cat" :class="selectedArticle.category">{{ categoryName(selectedArticle.category) }}</span>
            <button class="wk-detail-close" @click="showArticleDetail = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <div class="wk-detail-body">
            <h2 class="wk-detail-title">{{ selectedArticle.title }}</h2>
            <div class="wk-detail-meta">
              <span class="wk-article-author">
                <div class="wk-avatar">{{ selectedArticle.authorAvatar }}</div>
                {{ selectedArticle.author }}
              </span>
              <span>Zuletzt bearbeitet: {{ formatDate(selectedArticle.updatedAt) }}</span>
              <div class="wk-detail-tags">
                <span v-for="tag in selectedArticle.tags" :key="tag" class="wk-tag">{{ tag }}</span>
              </div>
            </div>
            <div class="wk-detail-content" v-html="selectedArticle.content" />

            <!-- Related Articles -->
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

            <!-- Version History -->
            <div class="wk-versions">
              <h4>Versionsverlauf</h4>
              <div class="wk-version-list">
                <div
                  v-for="v in selectedArticle.versions"
                  :key="v.id"
                  class="wk-version-item"
                >
                  <div class="wk-version-dot" />
                  <div class="wk-version-body">
                    <div class="wk-version-date">{{ formatDate(v.date) }} · {{ v.author }}</div>
                    <div class="wk-version-note">{{ v.note }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Editor Modal (Admin) -->
    <div v-if="showEditor" class="dk-modal-overlay" @click.self="showEditor = false">
      <div class="dk-modal dk-modal--lg">
        <div class="dk-modal-header">
          <h3>{{ editingArticle ? 'Artikel bearbeiten' : 'Neuer Wiki-Artikel' }}</h3>
          <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showEditor = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="dk-modal-body">
          <div class="dk-form-group">
            <label>Titel</label>
            <input v-model="editorForm.title" class="dk-form-input" type="text" placeholder="Titel des Artikels" />
          </div>
          <div class="dk-form-row">
            <div class="dk-form-group">
              <label>Kategorie</label>
              <select v-model="editorForm.category" class="dk-form-select">
                <option v-for="c in categories.filter(c => c.id !== 'all')" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>
            <div class="dk-form-group">
              <label>Tags (kommagetrennt)</label>
              <input v-model="editorForm.tags" class="dk-form-input" type="text" placeholder="Tonanlage, Beamer, Anleitung…" />
            </div>
          </div>
          <div class="dk-form-group">
            <label>Vorschautext</label>
            <textarea v-model="editorForm.excerpt" class="dk-form-input" rows="2" placeholder="Kurze Beschreibung…" />
          </div>
          <div class="dk-form-group">
            <label>Inhalt</label>
            <textarea v-model="editorForm.content" class="dk-form-input" rows="10" placeholder="Artikel-Inhalt (HTML erlaubt)…" />
          </div>
          <div class="dk-form-group">
            <label>Änderungsnotiz</label>
            <input v-model="editorForm.changeNote" class="dk-form-input" type="text" placeholder="z. B. 'Kontaktdaten aktualisiert'" />
          </div>
        </div>
        <div class="dk-modal-actions">
          <button class="dk-btn dk-btn-secondary" @click="showEditor = false">Abbrechen</button>
          <button class="dk-btn dk-btn-primary" @click="saveArticle">Speichern</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const isAdmin = window.__DIakonosBOOT?.user_role === 'Admin'

/* ─── Categories ─── */
const categories = [
  { id: 'all', name: 'Alle', icon: '★' },
  { id: 'technik', name: 'Technik', icon: '⚙️' },
  { id: 'abluaeufe', name: 'Abläufe', icon: '📋' },
  { id: 'raeume', name: 'Räume', icon: '🏢' },
  { id: 'kontakte', name: 'Kontakte', icon: '📞' },
  { id: 'faq', name: 'FAQ', icon: '❓' },
]

/* ─── Mock Articles ─── */
const articles = ref([
  {
    id: 1, title: 'Tonanlage bedienen – Schritt-für-Schritt',
    excerpt: 'Anleitung für die Bedienung der Mischpulte und Lautsprecher im Gemeindesaal.',
    content: '<h3>Vorbereitung</h3><p>Schalten Sie zuerst die Stromversorgung über den Hauptschalter rechts neben der Bühne ein.</p><h3>Mischpult</h3><ul><li>Kanal 1–4: Mikrofone</li><li>Kanal 5–6: Instrumente</li><li>Master-Fader auf 0 dB</li></ul><h3>Lautsprecher</h3><p>Die Aktivlautsprecher sind bereits verkabelt. Bitte nichts umstecken!</p><p>Bei Problemen: <strong>Peter Müller (0176/12345678)</strong></p>',
    category: 'technik', tags: ['Tonanlage', 'Mischpult', 'Anleitung'],
    author: 'Peter Müller', authorAvatar: 'PM', updatedAt: '2026-04-22', isNew: false,
    versions: [
      { id: 1, date: '2026-04-22', author: 'Peter Müller', note: 'Kontaktdaten aktualisiert' },
      { id: 2, date: '2026-03-15', author: 'Peter Müller', note: 'Erste Version' },
    ]
  },
  {
    id: 2, title: 'Beamer & Präsentation im Gottesdienst',
    excerpt: 'So richtest du den Beamer ein und spielst Präsentationen ab.',
    content: '<h3>Beamer einschalten</h3><p>Der Beamer befindet sich an der Decke über der Bühne. Die Fernbedienung liegt im Technik-Rack.</p><h3>Quellen</h3><ul><li>HDMI 1: Laptop</li><li>HDMI 2: Kamera</li></ul><h3>Präsentation</h3><p>Empfohlene Software: <strong>OpenLP</strong> oder <strong>PowerPoint</strong>. Auflösung: 1920×1080.</p>',
    category: 'technik', tags: ['Beamer', 'Präsentation', 'Gottesdienst'],
    author: 'Lisa Schmidt', authorAvatar: 'LS', updatedAt: '2026-04-20', isNew: false,
    versions: [
      { id: 1, date: '2026-04-20', author: 'Lisa Schmidt', note: 'OpenLP hinzugefügt' },
    ]
  },
  {
    id: 3, title: 'Ablauf Sonntagsgottesdienst',
    excerpt: 'Der Standardablauf für unsere Sonntagsgottesdienste.',
    content: '<h3>Zeitplan</h3><table style="width:100%;border-collapse:collapse;margin:12px 0"><tr style="border-bottom:1px solid var(--dk-divider)"><td style="padding:6px"><strong>09:30</strong></td><td style="padding:6px">Technik-Check</td></tr><tr style="border-bottom:1px solid var(--dk-divider)"><td style="padding:6px"><strong>10:00</strong></td><td style="padding:6px">Gottesdienstbeginn</td></tr><tr style="border-bottom:1px solid var(--dk-divider)"><td style="padding:6px"><strong>10:45</strong></td><td style="padding:6px">Predigt</td></tr><tr style="border-bottom:1px solid var(--dk-divider)"><td style="padding:6px"><strong>11:15</strong></td><td style="padding:6px">Abschluss & Kaffeerunde</td></tr></table><h3>Aufgaben</h3><ul><li>Predigt: Pastor Müller</li><li>Technik: Peter Müller</li><li>Kinderbetreuung: Jugendteam</li></ul>',
    category: 'abluaeufe', tags: ['Gottesdienst', 'Ablauf', 'Zeitplan'],
    author: 'Pastor Müller', authorAvatar: 'PM', updatedAt: '2026-04-18', isNew: false,
    versions: [
      { id: 1, date: '2026-04-18', author: 'Pastor Müller', note: 'Zeiten angepasst' },
    ]
  },
  {
    id: 4, title: 'Gemeindesaal – Nutzungsregeln',
    excerpt: 'Regeln für die Nutzung des Gemeindesaals und der Technik.',
    content: '<h3>Allgemeines</h3><ul><li>Der Saal ist nach Nutzung aufzuräumen</li><li>Keine Essensreste im Saal zurücklassen</li><li>Technik ausschalten und abschließen</li></ul><h3>Buchung</h3><p>Räume werden über das <a href="#/ressourcen">Ressourcenportal</a> gebucht.</p><h3>Kontakt</h3><p>Bei Fragen: <strong>Sekretariat (sekretariat@gemeinde.de)</strong></p>',
    category: 'raeume', tags: ['Gemeindesaal', 'Regeln', 'Buchung'],
    author: 'Sekretariat', authorAvatar: 'SE', updatedAt: '2026-04-15', isNew: false,
    versions: [
      { id: 1, date: '2026-04-15', author: 'Sekretariat', note: 'Ressourcenportal-Link hinzugefügt' },
    ]
  },
  {
    id: 5, title: 'Ansprechpartner & Kontakte',
    excerpt: 'Übersicht aller wichtigen Ansprechpartner in der Gemeinde.',
    content: '<h3>Pastor</h3><p><strong>Thomas Müller</strong><br>Email: pastor@gemeinde.de<br>Tel: 0123/456789</p><h3>Jugendleitung</h3><p><strong>David Klein</strong><br>Email: jugend@gemeinde.de<br>Tel: 0176/9876543</p><h3>Sekretariat</h3><p><strong>Anna Schmidt</strong><br>Email: sekretariat@gemeinde.de<br>Tel: 0123/456790</p><h3>Technik</h3><p><strong>Peter Müller</strong><br>Email: technik@gemeinde.de<br>Tel: 0176/12345678</p>',
    category: 'kontakte', tags: ['Kontakte', 'Ansprechpartner', 'Telefon'],
    author: 'Sekretariat', authorAvatar: 'SE', updatedAt: '2026-04-12', isNew: false,
    versions: [
      { id: 1, date: '2026-04-12', author: 'Sekretariat', note: 'David Klein hinzugefügt' },
    ]
  },
  {
    id: 6, title: 'Wie buche ich einen Raum?',
    excerpt: 'Schritt-für-Schritt Anleitung zur Raumbuchung.',
    content: '<h3>Schritt 1</h3><p>Öffne das <a href="#/ressourcen">Ressourcenportal</a> im Menü.</p><h3>Schritt 2</h3><p>Wähle die gewünschte Ressource aus (z. B. Gemeindesaal).</p><h3>Schritt 3</h3><p>Klicke auf <strong>"Buchen"</strong> und fülle das Formular aus.</p><h3>Schritt 4</h3><p>Die Buchung wird automatisch bestätigt, sofern kein Konflikt besteht.</p>',
    category: 'faq', tags: ['FAQ', 'Raumbuchung', 'Ressourcen'],
    author: 'Sekretariat', authorAvatar: 'SE', updatedAt: '2026-04-25', isNew: true,
    versions: [
      { id: 1, date: '2026-04-25', author: 'Sekretariat', note: 'Neuer Artikel' },
    ]
  },
])

/* ─── State ─── */
const activeCategory = ref('all')
const searchQuery = ref('')
const showArticleDetail = ref(false)
const selectedArticle = ref(null)
const showEditor = ref(false)
const editingArticle = ref(null)

const editorForm = ref({
  title: '', category: 'technik', tags: '', excerpt: '', content: '', changeNote: ''
})

/* ─── Computed ─── */
const filteredArticles = computed(() => {
  let list = articles.value
  if (activeCategory.value !== 'all') {
    list = list.filter(a => a.category === activeCategory.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(a =>
      a.title.toLowerCase().includes(q) ||
      a.excerpt.toLowerCase().includes(q) ||
      a.tags.some(t => t.toLowerCase().includes(q))
    )
  }
  return list.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
})

const articleCountByCategory = computed(() => {
  const counts = {}
  articles.value.forEach(a => { counts[a.category] = (counts[a.category] || 0) + 1 })
  return counts
})

const recentlyUpdated = computed(() => {
  return [...articles.value]
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .slice(0, 5)
})

const popularTags = computed(() => {
  const tagCounts = {}
  articles.value.forEach(a => {
    a.tags.forEach(t => { tagCounts[t] = (tagCounts[t] || 0) + 1 })
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
      a.tags.some(t => selectedArticle.value.tags.includes(t)))
    .slice(0, 3)
})

/* ─── Helpers ─── */
function categoryName(id) {
  return categories.find(c => c.id === id)?.name || id
}
function formatDate(d) {
  if (!d) return ''
  const date = new Date(d)
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
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
function openArticle(article) {
  selectedArticle.value = article
  showArticleDetail.value = true
}
function openEditor(article = null) {
  editingArticle.value = article
  editorForm.value = article
    ? { ...article, tags: article.tags.join(', ') }
    : { title: '', category: 'technik', tags: '', excerpt: '', content: '', changeNote: '' }
  showEditor.value = true
}
function saveArticle() {
  const f = editorForm.value
  if (!f.title.trim()) return
  const tags = f.tags.split(',').map(t => t.trim()).filter(Boolean)
  if (editingArticle.value) {
    const idx = articles.value.findIndex(a => a.id === editingArticle.value.id)
    if (idx !== -1) {
      const a = articles.value[idx]
      a.title = f.title
      a.category = f.category
      a.tags = tags
      a.excerpt = f.excerpt
      a.content = f.content
      a.updatedAt = new Date().toISOString().split('T')[0]
      a.versions.unshift({
        id: Date.now(),
        date: a.updatedAt,
        author: window.__DIakonosBOOT?.user_name || 'Ich',
        note: f.changeNote || 'Bearbeitet'
      })
    }
  } else {
    articles.value.unshift({
      id: Date.now(),
      ...f,
      tags,
      author: window.__DIakonosBOOT?.user_name || 'Ich',
      authorAvatar: (window.__DIakonosBOOT?.user_name || 'Ich').split(' ').map(n => n[0]).join('').slice(0, 2),
      updatedAt: new Date().toISOString().split('T')[0],
      isNew: true,
      versions: [{
        id: Date.now(),
        date: new Date().toISOString().split('T')[0],
        author: window.__DIakonosBOOT?.user_name || 'Ich',
        note: 'Erstellt'
      }]
    })
  }
  showEditor.value = false
}
</script>

<style scoped>
/* Layout */
.wk-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  align-items: start;
}
@media (max-width: 1100px) {
  .wk-layout { grid-template-columns: 1fr; }
  .wk-sidebar { order: -1; }
}

/* Search Bar */
.wk-search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 20px;
  transition: border-color var(--dk-fast);
}
.wk-search-bar:focus-within { border-color: var(--dk-accent); }
.wk-search-bar svg { color: var(--dk-text-muted); flex-shrink: 0; }
.wk-search-bar input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--dk-text);
  font-size: 14px;
  font-family: inherit;
  outline: none;
}
.wk-search-bar input::placeholder { color: var(--dk-text-subtle); }
.wk-search-clear {
  cursor: pointer;
  color: var(--dk-text-muted);
  transition: color var(--dk-fast);
}
.wk-search-clear:hover { color: var(--dk-text); }

/* Categories */
.wk-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 20px;
}
.wk-cat-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--dk-border);
  background: var(--dk-surface);
  color: var(--dk-text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--dk-fast);
}
.wk-cat-chip:hover { border-color: var(--dk-border-strong); background: var(--dk-surface-hover); }
.wk-cat-chip.is-active {
  background: var(--dk-brand-500);
  color: #fff;
  border-color: var(--dk-brand-500);
}
.wk-cat-icon { font-size: 14px; line-height: 1; }
.wk-cat-count {
  font-size: 11px;
  font-weight: 600;
  background: var(--dk-surface-2);
  padding: 1px 6px;
  border-radius: 999px;
  color: var(--dk-text-muted);
}
.wk-cat-chip.is-active .wk-cat-count { background: rgba(255,255,255,.2); color: #fff; }

/* Articles */
.wk-articles {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wk-article-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  padding: 16px;
  cursor: pointer;
  transition: all var(--dk-med);
  box-shadow: var(--dk-shadow-xs);
}
.wk-article-card:hover {
  border-color: var(--dk-border-strong);
  box-shadow: var(--dk-shadow-sm);
  transform: translateY(-1px);
}

.wk-article-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.wk-article-cat {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.wk-article-cat.technik { background: #f0f4ff; color: #1d4ed8; }
.wk-article-cat.abluaeufe { background: #f0fdf4; color: #15803d; }
.wk-article-cat.raeume { background: #fef3e2; color: #b45309; }
.wk-article-cat.kontakte { background: #fdf2f8; color: #be185d; }
.wk-article-cat.faq { background: #f5f5f4; color: #57534e; }

.wk-article-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--dk-success);
  color: #fff;
}

.wk-article-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 6px;
}
.wk-article-excerpt {
  font-size: 13px;
  color: var(--dk-text-muted);
  line-height: 1.5;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wk-article-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.wk-article-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--dk-text-muted);
}
.wk-article-author {
  display: flex;
  align-items: center;
  gap: 6px;
}
.wk-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-weight: 700;
}
.wk-article-tags {
  display: flex;
  gap: 4px;
}
.wk-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}

/* Sidebar */
.wk-sidebar { display: flex; flex-direction: column; gap: 16px; }
.wk-widget {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  padding: 16px;
  box-shadow: var(--dk-shadow-xs);
}
.wk-widget h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 12px;
}
.wk-widget--info { background: linear-gradient(135deg, rgba(212,162,76,.08) 0%, rgba(212,162,76,.02) 100%); }

.wk-recent {
  padding: 8px 0;
  border-bottom: 1px solid var(--dk-divider);
  cursor: pointer;
  transition: background var(--dk-fast);
}
.wk-recent:last-child { border-bottom: none; }
.wk-recent:hover { background: var(--dk-surface-hover); margin: 0 -16px; padding: 8px 16px; }
.wk-recent-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--dk-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wk-recent-info { font-size: 11px; color: var(--dk-text-muted); margin-top: 1px; }

.wk-tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.wk-tag-cloud-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--dk-fast);
}
.wk-tag-cloud-item:hover { background: var(--dk-brand-100); color: var(--dk-brand-500); }
.wk-tag-cloud-item.is-active { background: var(--dk-brand-500); color: #fff; }
.wk-tag-cloud-item small { opacity: 0.7; }

.wk-help-text {
  font-size: 13px;
  color: var(--dk-text-muted);
  line-height: 1.6;
  margin: 0;
}
.wk-help-text a { color: var(--dk-brand-500); text-decoration: none; }
.wk-help-text a:hover { text-decoration: underline; }

/* Detail Modal */
.wk-detail { max-height: 80vh; overflow-y: auto; }
.wk-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--dk-divider);
}
.wk-detail-cat {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.wk-detail-cat.technik { background: #f0f4ff; color: #1d4ed8; }
.wk-detail-cat.abluaeufe { background: #f0fdf4; color: #15803d; }
.wk-detail-cat.raeume { background: #fef3e2; color: #b45309; }
.wk-detail-cat.kontakte { background: #fdf2f8; color: #be185d; }
.wk-detail-cat.faq { background: #f5f5f4; color: #57534e; }

.wk-detail-close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--dk-fast);
}
.wk-detail-close:hover { background: var(--dk-surface-hover); color: var(--dk-text); }

.wk-detail-body { padding: 24px; }
.wk-detail-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--dk-text);
  margin: 0 0 10px;
}
.wk-detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--dk-text-muted);
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--dk-divider);
}
.wk-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.wk-detail-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--dk-text);
}
.wk-detail-content :deep(p) { margin: 0 0 12px; }
.wk-detail-content :deep(ul) { margin: 0 0 12px 20px; padding: 0; }
.wk-detail-content :deep(li) { margin-bottom: 4px; }
.wk-detail-content :deep(h3) {
  font-size: 16px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 20px 0 8px;
}
.wk-detail-content :deep(a) { color: var(--dk-brand-500); text-decoration: none; }
.wk-detail-content :deep(a:hover) { text-decoration: underline; }
.wk-detail-content :deep(table) { width: 100%; border-collapse: collapse; }
.wk-detail-content :deep(td) { padding: 8px; border-bottom: 1px solid var(--dk-divider); }
.wk-detail-content :deep(strong) { color: var(--dk-text); }

/* Related */
.wk-related {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--dk-divider);
}
.wk-related h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 12px;
}
.wk-related-list { display: flex; flex-direction: column; gap: 6px; }
.wk-related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--dk-surface-2);
  color: var(--dk-text);
  font-size: 13px;
  cursor: pointer;
  transition: background var(--dk-fast);
}
.wk-related-item:hover { background: var(--dk-surface-hover); }
.wk-related-item svg { color: var(--dk-text-muted); flex-shrink: 0; }

/* Versions */
.wk-versions {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--dk-divider);
}
.wk-versions h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 12px;
}
.wk-version-list { display: flex; flex-direction: column; gap: 0; }
.wk-version-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--dk-divider);
}
.wk-version-item:last-child { border-bottom: none; }
.wk-version-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dk-brand-400);
  margin-top: 4px;
  flex-shrink: 0;
}
.wk-version-body { flex: 1; }
.wk-version-date {
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text);
}
.wk-version-note {
  font-size: 12px;
  color: var(--dk-text-muted);
  margin-top: 1px;
}

/* Modal sizing */
.dk-modal--lg { max-width: 720px; }
</style>
