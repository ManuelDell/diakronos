<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Beiträge</h1>
        <p class="dk-screen-sub">Interner Gemeindebrief – Neuigkeiten & Ankündigungen</p>
      </div>
      <button v-if="isAdmin" class="dk-btn dk-btn-primary" @click="openEditor()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Neuer Beitrag
      </button>
    </div>

    <!-- Filters -->
    <div class="dk-filters" style="margin-bottom:24px">
      <div class="dk-filter-group">
        <button
          v-for="c in categories"
          :key="c.id"
          class="dk-filter-chip"
          :class="{ 'is-active': activeCategory === c.id }"
          @click="activeCategory = c.id"
        >
          {{ c.name }} {{ c.id === 'all' ? posts.length : postCountByCategory[c.id] || 0 }}
        </button>
      </div>
      <div class="dk-search" style="max-width:280px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input v-model="searchQuery" type="text" placeholder="Beiträge durchsuchen…" />
      </div>
    </div>

    <div class="bt-layout">
      <!-- Posts Feed -->
      <div class="bt-feed">
        <div v-if="filteredPosts.length === 0" class="dk-empty">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <p>Keine Beiträge gefunden.</p>
        </div>

        <article
          v-for="post in filteredPosts"
          :key="post.id"
          class="bt-post"
          @click="openPost(post)"
        >
          <div v-if="post.image" class="bt-post-image" :style="{ backgroundImage: `url(${post.image})` }">
            <span class="bt-post-cat" :class="post.category">{{ categoryName(post.category) }}</span>
          </div>
          <div v-else class="bt-post-image bt-post-image--placeholder" :class="`cat-${post.category}`">
            <span class="bt-post-cat" :class="post.category">{{ categoryName(post.category) }}</span>
          </div>

          <div class="bt-post-body">
            <h3 class="bt-post-title">{{ post.title }}</h3>
            <p class="bt-post-excerpt">{{ post.excerpt }}</p>
            <div class="bt-post-meta">
              <div class="bt-post-author">
                <div class="bt-avatar">{{ post.authorAvatar }}</div>
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

      <!-- Sidebar -->
      <aside class="bt-sidebar">
        <!-- Popular -->
        <div class="bt-widget">
          <h4>Beliebte Beiträge</h4>
          <div
            v-for="p in popularPosts"
            :key="p.id"
            class="bt-popular"
            @click="openPost(p)"
          >
            <div class="bt-popular-num">{{ p.rank }}</div>
            <div class="bt-popular-body">
              <div class="bt-popular-title">{{ p.title }}</div>
              <div class="bt-popular-date">{{ formatDate(p.date) }}</div>
            </div>
          </div>
        </div>

        <!-- Categories -->
        <div class="bt-widget">
          <h4>Kategorien</h4>
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
        </div>

        <!-- Archive -->
        <div class="bt-widget">
          <h4>Archiv</h4>
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
        </div>
      </aside>
    </div>

    <!-- Post Detail Modal -->
    <div v-if="showPostDetail" class="dk-modal-overlay" @click.self="showPostDetail = false">
      <div class="dk-modal dk-modal--lg">
        <div v-if="selectedPost" class="bt-detail">
          <div v-if="selectedPost.image" class="bt-detail-image" :style="{ backgroundImage: `url(${selectedPost.image})` }">
            <button class="bt-detail-close" @click="showPostDetail = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <div v-else class="bt-detail-image bt-detail-image--placeholder" :class="`cat-${selectedPost.category}`">
            <button class="bt-detail-close" @click="showPostDetail = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          <div class="bt-detail-body">
            <span class="bt-detail-cat" :class="selectedPost.category">{{ categoryName(selectedPost.category) }}</span>
            <h2 class="bt-detail-title">{{ selectedPost.title }}</h2>
            <div class="bt-detail-meta">
              <div class="bt-post-author">
                <div class="bt-avatar">{{ selectedPost.authorAvatar }}</div>
                <span>{{ selectedPost.author }}</span>
              </div>
              <span>{{ formatDate(selectedPost.date) }}</span>
            </div>
            <div class="bt-detail-content" v-html="selectedPost.content" />

            <!-- Comments -->
            <div class="bt-comments">
              <h4>Kommentare ({{ selectedPost.comments }})</h4>
              <div v-for="c in selectedPost.commentList" :key="c.id" class="bt-comment">
                <div class="bt-comment-avatar">{{ c.avatar }}</div>
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
                <button class="dk-btn dk-btn-primary dk-btn-sm" @click="addComment">Absenden</button>
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
          <h3>{{ editingPost ? 'Beitrag bearbeiten' : 'Neuer Beitrag' }}</h3>
          <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showEditor = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="dk-modal-body">
          <div class="dk-form-group">
            <label>Titel</label>
            <input v-model="editorForm.title" class="dk-form-input" type="text" placeholder="Titel des Beitrags" />
          </div>
          <div class="dk-form-row">
            <div class="dk-form-group">
              <label>Kategorie</label>
              <select v-model="editorForm.category" class="dk-form-select">
                <option v-for="c in categories.filter(c => c.id !== 'all')" :key="c.id" :value="c.id">{{ c.name }}</option>
              </select>
            </div>
            <div class="dk-form-group">
              <label>Bild-URL</label>
              <input v-model="editorForm.image" class="dk-form-input" type="text" placeholder="https://…" />
            </div>
          </div>
          <div class="dk-form-group">
            <label>Vorschautext</label>
            <textarea v-model="editorForm.excerpt" class="dk-form-input" rows="2" placeholder="Kurze Zusammenfassung…" />
          </div>
          <div class="dk-form-group">
            <label>Inhalt</label>
            <textarea v-model="editorForm.content" class="dk-form-input" rows="8" placeholder="Vollständiger Inhalt…" />
          </div>
        </div>
        <div class="dk-modal-actions">
          <button class="dk-btn dk-btn-secondary" @click="showEditor = false">Abbrechen</button>
          <button class="dk-btn dk-btn-primary" @click="savePost">Speichern</button>
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
  { id: 'all', name: 'Alle' },
  { id: 'ankuendigung', name: 'Ankündigung' },
  { id: 'gottesdienst', name: 'Gottesdienst' },
  { id: 'jugend', name: 'Jugend' },
  { id: 'gemeindeleben', name: 'Gemeindeleben' },
  { id: 'allgemein', name: 'Allgemein' },
]

/* ─── Mock Posts ─── */
const posts = ref([
  {
    id: 1, title: 'Sommerfest 2026 – Save the Date!',
    excerpt: 'Am 15. August feiern wir unser jährliches Sommerfest auf dem Gemeindegelände. Musik, Grillen und Spiele für die ganze Familie.',
    content: '<p>Am <strong>15. August 2026</strong> laden wir alle Gemeindemitglieder herzlich zu unserem jährlichen Sommerfest ein!</p><p>Auf dem Programm stehen:</p><ul><li>Live-Musik ab 16:00 Uhr</li><li>Grillbuffet für Groß und Klein</li><li>Kinderbetreuung mit Hüpfburg und Bastelstation</li><li>Gemeinsamer Gottesdienst um 19:00 Uhr</li></ul><p>Bringt eure Freunde und Nachbarn mit – alle sind willkommen!</p>',
    category: 'ankuendigung', image: '',
    author: 'Pastor Müller', authorAvatar: 'PM', date: '2026-04-20',
    comments: 3,
    commentList: [
      { id: 1, author: 'Anna S.', avatar: 'AS', text: 'Freue mich schon!', date: '2026-04-21' },
      { id: 2, author: 'Thomas B.', avatar: 'TB', text: 'Kann ich beim Grillen helfen?', date: '2026-04-22' },
    ]
  },
  {
    id: 2, title: 'Neuer Jugendleiter vorgestellt',
    excerpt: 'Wir begrüßen David Klein als neuen Jugendleiter. Er übernimmt ab Juni die Leitung der Jugendgruppe.',
    content: '<p>Wir freuen uns, <strong>David Klein</strong> als neuen Jugendleiter begrüßen zu dürfen!</p><p>David ist 28 Jahre alt, studiert Theologie und engagiert sich seit drei Jahren ehrenamtlich in unserer Jugendarbeit. Ab <strong>Juni 2026</strong> übernimmt er die Leitung der Jugendgruppe.</p><p>Ein erstes Kennenlernen findet am <strong>5. Mai um 19:30 Uhr</strong> im Besprechungsraum statt.</p>',
    category: 'jugend', image: '',
    author: 'Gemeinderat', authorAvatar: 'GR', date: '2026-04-18',
    comments: 5,
    commentList: [
      { id: 1, author: 'Lisa M.', avatar: 'LM', text: 'Herzlich willkommen David!', date: '2026-04-18' },
    ]
  },
  {
    id: 3, title: 'Änderungen im Gottesdienstablauf ab Mai',
    excerpt: 'Ab dem 1. Mai gibt es kleine Anpassungen im Ablauf unserer Sonntagsgottesdienste. Hier die Übersicht.',
    content: '<p>Ab <strong>1. Mai 2026</strong> gibt es folgende Anpassungen im Gottesdienstablauf:</p><ul><li>Beginn um 10:00 Uhr (statt 10:30 Uhr)</li><li>Neue Kinderbetreuung während des Gottesdienstes</li><li>Kaffeerunde nach dem Gottesdienst im Kirchencafé</li></ul>',
    category: 'gottesdienst', image: '',
    author: 'Pastor Müller', authorAvatar: 'PM', date: '2026-04-15',
    comments: 1,
    commentList: []
  },
  {
    id: 4, title: 'Ehrenamtliche Helfer gesucht: Gartenpflege',
    excerpt: 'Unser Gemeindegarten braucht wieder grüne Daumen! Wir suchen ehrenamtliche Helfer für die Pflege der Außenanlagen.',
    content: '<p>Unser Gemeindegarten ist ein wichtiger Treffpunkt – doch er braucht eure Hilfe!</p><p>Wir suchen ehrenamtliche Helfer für:</p><ul><li>Rasenmähen (wöchentlich)</li><li>Beetpflege</li><li>Hecke schneiden</li></ul><p>Bei Interesse meldet euch bei <strong>Peter Gärtner</strong> (p.gaertner@gemeinde.de).</p>',
    category: 'gemeindeleben', image: '',
    author: 'Peter Gärtner', authorAvatar: 'PG', date: '2026-04-10',
    comments: 0,
    commentList: []
  },
  {
    id: 5, title: 'Gemeinderatssitzung Protokoll März',
    excerpt: 'Das Protokoll der Gemeinderatssitzung vom 15. März ist jetzt verfügbar.',
    content: '<p>Das Protokoll der Gemeinderatssitzung vom <strong>15. März 2026</strong> steht nun allen Mitgliedern zur Einsicht zur Verfügung.</p><p>Besprochene Themen:</p><ul><li>Haushaltsplan 2026/2027</li><li>Sommerfest-Planung</li><li>Neue Beschallungsanlage</li></ul>',
    category: 'allgemein', image: '',
    author: 'Sekretariat', authorAvatar: 'SE', date: '2026-04-05',
    comments: 2,
    commentList: []
  },
])

/* ─── State ─── */
const activeCategory = ref('all')
const searchQuery = ref('')
const showPostDetail = ref(false)
const selectedPost = ref(null)
const showEditor = ref(false)
const editingPost = ref(null)
const newComment = ref('')

const editorForm = ref({
  title: '', category: 'allgemein', image: '', excerpt: '', content: ''
})

/* ─── Computed ─── */
const filteredPosts = computed(() => {
  let list = posts.value
  if (activeCategory.value !== 'all') {
    list = list.filter(p => p.category === activeCategory.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(p =>
      p.title.toLowerCase().includes(q) ||
      p.excerpt.toLowerCase().includes(q) ||
      p.author.toLowerCase().includes(q)
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
  const date = new Date(d)
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' })
}
function openPost(post) {
  selectedPost.value = post
  showPostDetail.value = true
}
function openEditor(post = null) {
  editingPost.value = post
  editorForm.value = post
    ? { ...post }
    : { title: '', category: 'allgemein', image: '', excerpt: '', content: '' }
  showEditor.value = true
}
function savePost() {
  const f = editorForm.value
  if (!f.title.trim()) return
  if (editingPost.value) {
    const idx = posts.value.findIndex(p => p.id === editingPost.value.id)
    if (idx !== -1) posts.value[idx] = { ...posts.value[idx], ...f }
  } else {
    posts.value.unshift({
      id: Date.now(),
      ...f,
      author: window.__DIakonosBOOT?.user_name || 'Ich',
      authorAvatar: (window.__DIakonosBOOT?.user_name || 'Ich').split(' ').map(n => n[0]).join('').slice(0, 2),
      date: new Date().toISOString().split('T')[0],
      comments: 0,
      commentList: []
    })
  }
  showEditor.value = false
}
function addComment() {
  if (!newComment.value.trim() || !selectedPost.value) return
  selectedPost.value.commentList.push({
    id: Date.now(),
    author: window.__DIakonosBOOT?.user_name || 'Ich',
    avatar: (window.__DIakonosBOOT?.user_name || 'Ich').split(' ').map(n => n[0]).join('').slice(0, 2),
    text: newComment.value,
    date: new Date().toISOString().split('T')[0]
  })
  selectedPost.value.comments++
  newComment.value = ''
}
</script>

<style scoped>
/* Layout */
.bt-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  align-items: start;
}
@media (max-width: 1100px) {
  .bt-layout { grid-template-columns: 1fr; }
  .bt-sidebar { order: -1; }
}

/* Feed */
.bt-feed { display: flex; flex-direction: column; gap: 16px; }

.bt-post {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all var(--dk-med);
  box-shadow: var(--dk-shadow-xs);
}
.bt-post:hover {
  border-color: var(--dk-border-strong);
  box-shadow: var(--dk-shadow-sm);
  transform: translateY(-2px);
}

.bt-post-image {
  height: 180px;
  background-size: cover;
  background-position: center;
  position: relative;
}
.bt-post-image--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef1f8 0%, #d6dcea 100%);
}
.bt-post-image--placeholder.cat-ankuendigung { background: linear-gradient(135deg, #fef3e2 0%, #fde8c4 100%); }
.bt-post-image--placeholder.cat-gottesdienst { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); }
.bt-post-image--placeholder.cat-jugend { background: linear-gradient(135deg, #f0f4ff 0%, #e0e8ff 100%); }
.bt-post-image--placeholder.cat-gemeindeleben { background: linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%); }
.bt-post-image--placeholder.cat-allgemein { background: linear-gradient(135deg, #f5f5f4 0%, #e7e5e4 100%); }

.bt-post-cat {
  position: absolute;
  top: 12px;
  left: 12px;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(255,255,255,.92);
  color: var(--dk-text);
  backdrop-filter: blur(4px);
}

.bt-post-body { padding: 16px; }
.bt-post-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 6px;
  line-height: 1.35;
}
.bt-post-excerpt {
  font-size: 13px;
  color: var(--dk-text-muted);
  line-height: 1.5;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.bt-post-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--dk-text-muted);
}
.bt-post-author {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bt-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--dk-brand-100);
  color: var(--dk-brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
}
.bt-post-date { font-size: 12px; }
.bt-post-comments {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

/* Sidebar */
.bt-sidebar { display: flex; flex-direction: column; gap: 16px; }
.bt-widget {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--dk-shadow-xs);
}
.bt-widget h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 12px;
}

.bt-popular {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--dk-divider);
  cursor: pointer;
  transition: background var(--dk-fast);
}
.bt-popular:last-child { border-bottom: none; }
.bt-popular:hover { background: var(--dk-surface-hover); margin: 0 -16px; padding: 8px 16px; }
.bt-popular-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.bt-popular-body { flex: 1; min-width: 0; }
.bt-popular-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--dk-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bt-popular-date { font-size: 11px; color: var(--dk-text-muted); margin-top: 1px; }

.bt-cat-list { display: flex; flex-direction: column; gap: 2px; }
.bt-cat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background var(--dk-fast);
}
.bt-cat-item:hover { background: var(--dk-surface-hover); }
.bt-cat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.bt-cat-dot.ankuendigung { background: #d97706; }
.bt-cat-dot.gottesdienst { background: #16a34a; }
.bt-cat-dot.jugend { background: #2563eb; }
.bt-cat-dot.gemeindeleben { background: #db2777; }
.bt-cat-dot.allgemein { background: #78716c; }
.bt-cat-name { flex: 1; font-size: 13px; color: var(--dk-text); }
.bt-cat-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text-muted);
  background: var(--dk-surface-2);
  padding: 1px 7px;
  border-radius: 999px;
}

.bt-archive-list { display: flex; flex-direction: column; gap: 2px; }
.bt-archive-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--dk-text);
  cursor: pointer;
  transition: background var(--dk-fast);
}
.bt-archive-item:hover { background: var(--dk-surface-hover); }
.bt-archive-count { color: var(--dk-text-muted); font-weight: 500; }

/* Detail Modal */
.bt-detail { max-height: 80vh; overflow-y: auto; }
.bt-detail-image {
  height: 220px;
  background-size: cover;
  background-position: center;
  position: relative;
}
.bt-detail-image--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef1f8 0%, #d6dcea 100%);
}
.bt-detail-image--placeholder.cat-ankuendigung { background: linear-gradient(135deg, #fef3e2 0%, #fde8c4 100%); }
.bt-detail-image--placeholder.cat-gottesdienst { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); }
.bt-detail-image--placeholder.cat-jugend { background: linear-gradient(135deg, #f0f4ff 0%, #e0e8ff 100%); }
.bt-detail-image--placeholder.cat-gemeindeleben { background: linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%); }
.bt-detail-image--placeholder.cat-allgemein { background: linear-gradient(135deg, #f5f5f4 0%, #e7e5e4 100%); }

.bt-detail-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(255,255,255,.9);
  color: var(--dk-text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--dk-fast);
}
.bt-detail-close:hover { background: #fff; }

.bt-detail-body { padding: 24px; }
.bt-detail-cat {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.bt-detail-cat.ankuendigung { background: #fef3e2; color: #b45309; }
.bt-detail-cat.gottesdienst { background: #dcfce7; color: #15803d; }
.bt-detail-cat.jugend { background: #dbeafe; color: #1d4ed8; }
.bt-detail-cat.gemeindeleben { background: #fce7f3; color: #be185d; }
.bt-detail-cat.allgemein { background: #f5f5f4; color: #57534e; }

.bt-detail-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--dk-text);
  margin: 0 0 10px;
  line-height: 1.3;
}
.bt-detail-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--dk-text-muted);
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--dk-divider);
}
.bt-detail-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--dk-text);
}
.bt-detail-content :deep(p) { margin: 0 0 12px; }
.bt-detail-content :deep(ul) { margin: 0 0 12px 20px; padding: 0; }
.bt-detail-content :deep(li) { margin-bottom: 4px; }
.bt-detail-content :deep(strong) { color: var(--dk-text); }

/* Comments */
.bt-comments {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--dk-divider);
}
.bt-comments h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 14px;
}
.bt-comment {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--dk-divider);
}
.bt-comment:last-child { border-bottom: none; }
.bt-comment-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.bt-comment-body { flex: 1; }
.bt-comment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.bt-comment-header strong { font-size: 13px; color: var(--dk-text); }
.bt-comment-header span { font-size: 11px; color: var(--dk-text-muted); }
.bt-comment-body p { font-size: 13px; color: var(--dk-text-muted); margin: 0; }

.bt-comment-form {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.bt-comment-form input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--dk-border);
  border-radius: 8px;
  background: var(--dk-surface);
  color: var(--dk-text);
  font-size: 13px;
  font-family: inherit;
}
.bt-comment-form input:focus { outline: none; border-color: var(--dk-accent); }

/* Editor Modal sizing */
.dk-modal--lg { max-width: 720px; }
</style>
