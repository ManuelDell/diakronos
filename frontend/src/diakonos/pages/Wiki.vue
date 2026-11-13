<template>
  <div ref="rootEl" class="dk-screen dk-screen-enter">

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
        <!-- FIX-3: Kategorien als gemeinsamer Chip-Baustein (DkFilterChips)
             statt eigener Knöpfe. Die Seite baute die Filterzeile bisher
             selbst — mit 29 px hohen Knöpfen neben dem Suchfeld, das über
             seinen Innenabstand auf 39 px kam. Jetzt kommt beides aus
             --filter-h (index.css) und bleibt auch neben dem Feld gleich hoch. -->
        <DkFilterChips
          :chips="kategorieChips"
          :model-value="activeCategory"
          alle-wert="all"
          aria-label="Wiki nach Kategorie filtern"
          @waehlen="activeCategory = $event"
        />

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
            role="link"
            tabindex="0"
            :data-id="article.id"
            :aria-label="`Artikel lesen: ${article.title || 'ohne Titel'}`"
            @click="openArticle(article)"
            @keydown.enter.self.prevent="openArticle(article)"
            @keydown.space.self.prevent="openArticle(article)"
            @contextmenu.prevent="zeilenKontextmenue($event, article)"
          >
            <div class="wk-article-header">
              <DkBadge variant="neutral">{{ categoryName(article.category) }}</DkBadge>
              <DkBadge v-if="article.isNew" variant="ok">Neu</DkBadge>
              <!-- UX2e (Entwurf B1, N6): Objekt-Aktionen am Artikel im „⋯"-Menü. -->
              <span class="wk-article-aktionen">
                <DkAktionen
                  :ref="el => setzeAktion(el, article)"
                  :eintraege="aktionenFuerArtikel(article)"
                  :label="`Aktionen für ${article.title || 'diesen Artikel'}`"
                />
              </span>
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

    <!-- MT-7: Lesen ist eine eigene Unterseite (#/wiki/<Kennung>,
         pages/WikiArtikel.vue) — kein Fenster mehr an dieser Stelle. -->

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
        <DkButton variant="secondary" @click="editorSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="saving" @click="saveArticle">Speichern</DkButton>
      </template>
    </DkDialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { suchNormal } from '../composables/bf1Anzeige.js'
import { showToast } from '../composables/useToast.js'
import { serverDatum, GEMEINDE_ZONE } from '../../shared/zeit.mjs'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
// UX2c (C2): Löschen ohne Rückfrage, dafür „Rückgängig“ (Stapel + Strg+Z).
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { useSession } from '../composables/useSession.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkCard from '../components/ui/DkCard.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkField from '../components/ui/DkField.vue'
import DkSelect from '../components/ui/DkSelect.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
// UX2e: EIN Aktionsmenü „⋯" für alle Listen (Entwurf B1).
import DkAktionen from '../components/ui/DkAktionen.vue'
// MT-7: Lesen wechselt die Route (eigene Unterseite statt Fenster).
import { navigate } from '../router.js'
// MT-7b: Merker für den Rückweg — die Liste schreibt ihre volle Adresse hier
// hinein, bevor sie einen Artikel öffnet.
import { adresseImVerlaufSetzen, rueckwegKennung, rueckwegMerken } from '../composables/zurueckWege.mjs'

const { isAdmin } = useSession()
// UX2c (C2): Rückgängig-Weg dieser Seite (Stapel-Eintrag + Meldung).
const { mitRueckgaengig } = useRueckgaengigAktion()

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
// MT-7: Weg zurück zur Liste — Ziel von „‹ zurück“ auf der Leseseite.
const ZURUECK_ZIEL = '#/wiki'
/** Wurzel der Seite — für den Fokus auf die zuletzt geöffnete Karte (MT-7b). */
const rootEl = ref(null)
const articles = ref([])
const activeCategory = ref('all')
const searchQuery = ref('')
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

/* FIX-3: Chip-Zeile aus der festen Kategorienliste (Zahlen aus dem Bestand).
   „Alle“ ist der Ruhezustand (Wert 'alle'), die Kategorien tragen ihren
   Schlüssel; `activeCategory` bleibt unverändert 'all'/'technik'/… — die
   Chips liefern nur den Wert, das Filtern selbst hängt weiter an loadArticles. */
const kategorieChips = computed(() =>
  categories.map(c => ({ id: c.id, label: c.name, anzahl: articleCountByCategory.value[c.id] || 0 })))

/* ─── API ─── */
/**
 * MT-7b: Die vollständige Adresse der Liste — Suche und Kategorie kommen aus
 * dem Zustand der Seite (nicht aus der Adresse: nach `?bearbeiten=` steht dort
 * weniger). Das Ergebnis ist die Adresse des Listen-Eintrags im Verlauf und das
 * Ziel von „‹ zurück“ auf der Leseseite.
 *
 * RUHZUSTAND (Review-Punkt 2): `kategorie=all` und `q=` werden AUSGESCHRIEBEN
 * (wie in `Beitraege.vue`) — sonst bliebe eine längst aufgehobene Suche in der
 * Adresse stehen und „zurück“ brächte sie wieder mit.
 */
function listenAdresse() {
  const teile = [`kategorie=${encodeURIComponent(activeCategory.value || 'all')}`]
  const suche = String(searchQuery.value || '').trim()
  if (suche) teile.push(`q=${encodeURIComponent(suche)}`)
  else teile.push('q=')
  return '#/wiki' + `?${teile.join('&')}`
}

/**
 * MT-7b (Review-Punkt 2): Die Filter in den EIGENEN Verlaufs-Eintrag schreiben,
 * während der Nutzer tippt/filtert (wie `Lieder.vue`) — dann liegt der
 * Listen-Eintrag mit Suche im Verlauf, und Browser-„Zurück“ landet darauf.
 */
watch([activeCategory, searchQuery], () => { adresseImVerlaufSetzen(listenAdresse()) })

/**
 * Beim Aufbau der Liste: Suche und Kategorie aus der Adresse übernehmen.
 * Review-Punkt 2: Zuerst auf den Ruhezustand zurück — sonst bliebe ein Wert
 * stehen, der in der Adresse nicht (mehr) genannt ist.
 */
function listenZustandUebernehmen() {
  activeCategory.value = 'all'
  searchQuery.value = ''
  const hash = String(window.location.hash || '')
  const frage = hash.indexOf('?')
  if (frage === -1) return
  const teile = new URLSearchParams(hash.slice(frage + 1))
  const kategorie = teile.get('kategorie')
  if (kategorie === 'all') activeCategory.value = 'all'
  else if (kategorie && categories.some(c => c.id === kategorie)) activeCategory.value = kategorie
  const suche = teile.get('q')
  if (suche) searchQuery.value = suche
}

async function loadArticles() {
  const params = {}
  if (activeCategory.value && activeCategory.value !== 'all') params.kategorie = activeCategory.value
  if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
  const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_liste', params)
  if (res) articles.value = res
}

/**
 * MT-7: Lesen ist eine eigene Unterseite mit eigener Adresse
 * (`#/wiki/<Kennung>` → pages/WikiArtikel.vue). Der Klick wechselt die Route;
 * damit führt der Zurück-Knopf des Browsers zur Liste, und die Artikeladresse
 * ist ein echter Verlaufseintrag (vorher: `replaceState` ohne Ereignis).
 *
 * MT-7b (Review-Punkt 2): Suche und Filter gehen auch beim BROWSER-Zurück nicht
 * verloren. Vor dem Sprung wird die vollständige Listen-Adresse (mit
 * `?q=`/`?kategorie=`) in den EIGENEN Verlaufs-Eintrag geschrieben
 * (`adresseImVerlaufSetzen` → `replaceState`, kein neuer Eintrag, wie
 * `Lieder.vue`); die Liste übernimmt sie beim Aufbau aus der Adresse. Zusätzlich
 * liegt sie im Merker (`rueckwegMerken`, mit der Kennung für den Fokus) — Ziel
 * von „‹ zurück“ auf der Leseseite.
 */
function openArticle(article) {
  if (!article?.id) return
  const adresse = listenAdresse()
  adresseImVerlaufSetzen(adresse)
  rueckwegMerken(adresse, ZURUECK_ZIEL, article.id)
  navigate(`#/wiki/${encodeURIComponent(article.id)}`)
}


/**
 * MT-7b (Review-Punkt 4): Nach dem Aufbau den Fokus auf den Artikel legen, den
 * der Nutzer zuletzt geöffnet hatte (Zurück von der Leseseite) und ihn in die
 * Sicht bringen — sonst steht der Fokus auf `body` und die Seite oben.
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
 * hierher (`#/wiki?bearbeiten=<Kennung>`) — der Editor ist ein Fenster dieser
 * Liste. Vorher wertete die Liste den Teil nicht aus, „Bearbeiten“ im Menü der
 * Leseseite öffnete also NICHTS (der alte Wiki-Dialog tat es). Die Kennung wird
 * sofort wieder aus der Adresse genommen (`replaceState`, kein neuer
 * Verlaufseintrag), damit Neuladen/„zurück“ das Fenster nicht erneut aufreißt.
 */
async function bearbeitenAusAdresse() {
  const hash = String(window.location.hash || '')
  const frage = hash.indexOf('?')
  if (frage === -1) return
  const teile = new URLSearchParams(hash.slice(frage + 1))
  const kennung = teile.get('bearbeiten')
  if (!kennung) return
  teile.delete('bearbeiten')
  const rest = teile.toString()
  try { window.history.replaceState(window.history.state, '', `#/wiki${rest ? `?${rest}` : ''}`) } catch { /* Verlauf nicht verfügbar */ }

  let article = articles.value.find((a) => String(a.id) === String(kennung))
  if (!article) {
    // EIN Nachladen (die Liste kann aus dem Papierkorb-Stand kommen), dann
    // gilt der Artikel als nicht vorhanden — und die Meldung sagt es.
    await loadArticles()
    article = articles.value.find((a) => String(a.id) === String(kennung))
  }
  if (!article) {
    showToast('Der Artikel ist nicht mehr vorhanden. Lade die Liste neu.', 'error')
    return
  }
  await bearbeitenArtikel(article)
}

/* ── UX2e · Aktionsmenü „⋯" an jedem Wiki-Artikel (Entwurf B1, N6/K4) ─────
   Die Karte trägt bisher nur „öffnen" (der ganze Block ist klickbar). Das
   Menü bringt die Aktionen des Artikels an den Artikel:
     · Artikel öffnen    (immer)
     · Bearbeiten        (Admin)
     · Löschen           (Admin, gefährlich, abgesetzt am Ende)
   Rechte/Bestätigung wie im Detail-Dialog — dieselbe Funktion `deleteArticle`,
   damit es EINEN Löschweg gibt (S4). */
const aktionRefs = new Map()
const artikelSchluessel = (a) => String(a?.id ?? '')
function setzeAktion(el, a) {
  const schluessel = artikelSchluessel(a)
  if (!schluessel) return
  if (el) aktionRefs.set(schluessel, el)
  else aktionRefs.delete(schluessel)
}

/** Bearbeiten braucht den Inhalt — der kommt erst mit dem Detailaufruf. */
async function bearbeitenArtikel(article) {
  try {
    const detail = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_detail', { artikel_id: article.id })
    openEditor({ ...article, ...detail })
  } catch (e) {
    showToast(e?.message || 'Der Artikel konnte nicht geladen werden.', 'error')
  }
}

function aktionenFuerArtikel(article) {
  const eintraege = [{
    key: 'oeffnen', label: 'Artikel öffnen', icon: 'ansehen',
    aktion: () => openArticle(article),
  }]
  if (isAdmin.value) {
    eintraege.push({
      key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten',
      aktion: () => bearbeitenArtikel(article),
    })
    eintraege.push({
      key: 'loeschen', label: 'Löschen', icon: 'loeschen',
      gefahr: true,
      aktion: () => deleteArticle(article),
    })
  }
  return eintraege
}

/** Rechtsklick auf die Artikelkarte öffnet dasselbe Menü. */
function zeilenKontextmenue(ereignis, article) {
  aktionRefs.get(artikelSchluessel(article))?.oeffnenFuerZeile(ereignis, ereignis?.currentTarget)
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
  /* UX2c (C2): „Löschen“ heißt Papierkorb (7 Tage umkehrbar) — also KEINE
     Rückfrage, sondern sofort ausführen und „Rückgängig“ anbieten. */
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.delete_wiki_artikel', { artikel_id: article.id })
    if (res?.success) {
      await loadArticles()
      await mitRueckgaengig({
        beschreibung: papierkorbMeldung(article.title, res.wiederherstellbar_bis),
        zurueck: () => wiederherstellen('artikel', article.id),
        danach: loadArticles,
        erfolg: `„${article.title}“ wiederhergestellt.`,
      })
    }
  } catch (e) {
    showToast(e.message || 'Artikel konnte nicht gelöscht werden.', 'error')
  }
}

onMounted(async () => {
  listenZustandUebernehmen()
  await loadArticles()
  await fokusWiederherstellen()
  ladenHilfeKontakt()
  // MT-7 (Review-Punkt 3): „Bearbeiten“ von der Leseseite kommt als
  // `?bearbeiten=<Kennung>` hier an — erst NACH dem Laden der Liste auswerten.
  await bearbeitenAusAdresse()
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

/*
 * MT-7: „Ähnliche Artikel“ stand im Artikel-Fenster. Es gehört zur Leseseite
 * und steht jetzt dort (pages/WikiArtikel.vue) — die Liste braucht es nicht.
 */

/* ─── Helpers ─── */
function categoryName(id) {
  return categories.find(c => c.id === id)?.name || id
}
/**
 * ZEIT-2: `updatedAt` kommt als Datum (`YYYY-MM-DD`) — bleibt der Tag.
 * `serverDatum` rechnet nicht um (vorher: `new Date(d)` = UTC-Mitternacht,
 * in Berlin also schon der richtige Tag, aber nur zufaellig).
 */
function formatDate(d) {
  if (!d) return ''
  const tag = serverDatum(d)
  if (!tag) return ''
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: GEMEINDE_ZONE,
  }).format(tag)
}
function timeAgo(d) {
  // ZEIT-2: Kalendertage vergleichen (beide Mittag UTC), nicht „jetzt“ gegen
  // Mittag — sonst vormittags „vor -1 Tagen“ und am Folgetag „heute“.
  const then = serverDatum(d)
  if (!then) return ''
  const heute = serverDatum(new Intl.DateTimeFormat('en-CA', { timeZone: GEMEINDE_ZONE }).format(new Date()))
  const diff = Math.round((heute - then) / (1000 * 60 * 60 * 24))
  if (diff <= 0) return 'heute'
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

/* Kategorien: die Zeile ist jetzt der gemeinsame Baustein DkFilterChips
   (.dk-ui-chips/.dk-ui-chip in index.css). Die früheren Eigenregeln
   .wk-cat-chips/.wk-cat-chip/.wk-cat-icon/.wk-cat-count sind mit FIX-3
   entfallen — sie waren der Grund, warum die Knöpfe hier anders hoch waren
   als das Suchfeld daneben. Nur der Abstand zur Artikelliste bleibt. */
.wk-main > .dk-ui-chips { margin-bottom: var(--sp-alt-20); }

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
/* UX2e: Das „⋯" schließt die Kopfzeile rechts ab (Badges links, Aktionen
   rechts) — Symbol und Text stehen dabei auf derselben Linie. */
.wk-article-aktionen { margin-left: auto; }
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

/* MT-7: Die Regeln des Artikel-Fensters (.wk-detail*, .wk-related*) sind mit
   dem Fenster entfallen — Lesen ist die eigene Seite pages/WikiArtikel.vue. */

/* Editor */
.wk-editor { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
