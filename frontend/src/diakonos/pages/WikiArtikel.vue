<template>
  <div class="dk-screen dk-screen-enter">
    <!-- OP-UI-19: Laden, Fehler und „nicht gefunden“ als eigene Zustände. -->
    <DkSkelett v-if="ladenSkelett" form="zeilen" :anzahl="6" text="Artikel wird geladen …" />

    <div v-else-if="fehler" class="wk-lese-fehler">
      <p class="wk-lese-fehlertext">{{ fehler }}</p>
      <div class="wk-lese-fehlerknoepfe">
        <DkButton variant="secondary" size="md" @click="zurueck($event)">
          <span class="wk-pfeil" aria-hidden="true">‹</span> Zurück zum Wiki
        </DkButton>
        <!-- „Erneut versuchen“ nur bei Lagen, die ein neuer Versuch ändern kann. -->
        <DkButton v-if="erneutSinnvoll" variant="secondary" size="md" @click="ladenDaten">Erneut versuchen</DkButton>
      </div>
    </div>

    <template v-else-if="artikel">
      <!-- Kopf: Titel + „‹ zurück“ (MT-7: eigene Unterseite statt Fenster) -->
      <DkPageHeader ref="kopf" :title="artikel.title || 'Artikel'" :krumen="krumen">
        <template #actions>
          <DkButton class="wk-zurueck" variant="secondary" size="md" as="a" :href="zurueckZiel" @click="zurueck($event)">
            <span class="wk-pfeil" aria-hidden="true">‹</span> zurück
          </DkButton>
        </template>
      </DkPageHeader>

      <!-- Objekt-Aktionen (N6): dieselben Einträge wie in der Liste. -->
      <div v-if="aktionen.length" class="wk-lese-aktionen">
        <DkAktionen :eintraege="aktionen" :label="`Aktionen für ${artikel.title || 'diesen Artikel'}`" />
      </div>

      <article class="wk-lese">
        <div class="wk-lese-meta">
          <DkBadge variant="neutral">{{ categoryName(artikel.category) }}</DkBadge>
          <span class="wk-lese-person">
            <span class="dk-avatar dk-avatar-sm" aria-hidden="true">{{ autorKuerzel }}</span>
            {{ artikel.author }}
          </span>
          <span>Zuletzt bearbeitet: {{ formatDate(artikel.updatedAt) }}</span>
        </div>
        <div v-if="tags.length" class="wk-lese-tags">
          <DkBadge v-for="tag in tags" :key="tag" variant="neutral">{{ tag }}</DkBadge>
        </div>

        <div class="dk-lesetext wk-lese-inhalt" v-html="sanitize(artikel.content)" />

        <!-- Ähnliche Artikel — als Links auf ihre eigene Adresse. Ziel von
             „‹ zurück“ bleibt die Liste (Merker in `zurueckWege.mjs`). -->
        <section v-if="aehnliche.length" class="wk-lese-aehnlich" aria-labelledby="wk-aehnlich-titel">
          <h2 id="wk-aehnlich-titel" class="wk-lese-zwischentitel">Ähnliche Artikel</h2>
          <ul class="wk-lese-aehnlich-liste">
            <li v-for="a in aehnliche" :key="a.id">
              <a class="wk-lese-aehnlich-link" :href="adresseFuer(a.id)" @click="artikelOeffnen">
                <span class="wk-lese-aehnlich-symbol" aria-hidden="true">
                  <DkSymbol name="notiz" />
                </span>
                <span>{{ a.title }}</span>
              </a>
            </li>
          </ul>
        </section>
      </article>
    </template>
  </div>
</template>

<script setup>
/**
 * WikiArtikel — EIN Wiki-Eintrag als eigene Unterseite (MT-7).
 *
 * Befund: „Wiki-Eintrag lesen“ öffnete ein Fenster (DkDialog) ohne eigene
 * Adresse; der Zurück-Knopf des Browsers führte nicht zur Liste, Drucken war
 * nicht vorgesehen. SOLL: Unterseite mit eigener Adresse, Kopf mit Titel und
 * „‹ zurück“, Lesebreite, druckbar.
 *
 * Adresse: `#/wiki/<Kennung>` (Router: WikiArtikel). Die Liste (`Wiki.vue`)
 * bleibt in ihrer Aufgabe und verlinkt je Karte auf diese Adresse — dadurch
 * funktionieren Lesezeichen und geteilte Links wie bisher (P3-1b/UXD-R20),
 * jetzt aber mit echtem Routenwechsel und Verlauf.
 *
 * Rechte unverändert (nur Darstellung): Lesen darf jeder Angemeldete
 * (`get_wiki_artikel_detail` prüft der Server), Bearbeiten/Löschen stehen im
 * Aktionsmenü nur Administratoren — dieselbe Bedingung wie in der Liste.
 *
 * Farben/Abstände ausschließlich aus tokens.css; Symbole stehen auf der
 * Textlinie (Flex `align-items: center`), keine eigenen Farbwerte.
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import DOMPurify from 'dompurify'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'
import { serverDatum, GEMEINDE_ZONE } from '../../shared/zeit.mjs'
import { useSession } from '../composables/useSession.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { aktionsfehler, fehlertext, zustandFuer } from '../../shared/fehlertexte.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import { getRouteParam, navigate } from '../router.js'
// MT-7b (Operator-Entscheidung): „‹ zurück“ ERSETZT den eigenen
// Verlaufs-Eintrag durch die gemerkte Listen-Adresse MIT Filtern — kein
// `history.back()` (griff nie) und kein Push (Zurück-Falle).
import { rueckwegErsetzen, rueckwegZiel } from '../composables/zurueckWege.mjs'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import DkAktionen from '../components/ui/DkAktionen.vue'
import DkSymbol from '../components/ui/DkSymbol.vue'

function sanitize(html) { return DOMPurify.sanitize(html || '') }

const KATEGORIEN = {
  technik: 'Technik',
  ablaeufe: 'Abläufe',
  raeume: 'Räume',
  kontakte: 'Kontakte',
  faq: 'FAQ',
}
function categoryName(id) { return KATEGORIEN[id] || id || '' }

const { isAdmin } = useSession()
const { mitRueckgaengig } = useRueckgaengigAktion()

/**
 * Die Kennung kommt aus der Adresse. `getRouteParam` liefert sie NUR, wenn die
 * Route diese Seite ist — beim bloßen Durchlaufen von `#/wiki` steht im
 * Parameter-Objekt nichts. Deshalb der Rückfall auf den Pfadteil der Adresse.
 */
const artikelId = computed(() => {
  const ausRoute = getRouteParam('id', 'WikiArtikel')
  if (ausRoute) return ausRoute
  const treffer = /^#\/wiki\/([^?#]+)/.exec(String(window.location.hash || ''))
  return treffer ? decodeURIComponent(treffer[1]) : ''
})
const artikel = ref(null)
/** Alle Artikel der Übersicht — nur für „Ähnliche Artikel“ (gleiche Tags). */
const alleArtikel = ref([])
const fehler = ref('')
/** Zustand des Fehlers (Katalogschlüssel) — entscheidet über „Erneut versuchen“. */
const fehlerZustand = ref('')
const erneutSinnvoll = computed(() => !['weg', 'rechte'].includes(fehlerZustand.value))
const kopf = ref(null)
const laden = ref(true)
const { skelettSichtbar: ladenSkelett } = useLadeSkelett(laden)

const tags = computed(() => artikel.value?.tags || [])
/**
 * Das Ziel von „‹ zurück“ (MT-7b): die Listen-Adresse, die sich die Liste beim
 * Öffnen gemerkt hat (mit `?q=`/`?kategorie=`), sonst das Wiki ohne Filter.
 */
const zurueckZiel = computed(() => rueckwegZiel('#/wiki'))
const krumen = computed(() => [
  { text: 'Wiki', href: zurueckZiel.value },
  { text: artikel.value?.title || 'Artikel' },
])
const autorKuerzel = computed(() => {
  const teile = String(artikel.value?.author || '').trim().split(/\s+/).filter(Boolean)
  return (teile.slice(0, 2).map((t) => t[0]).join('') || '?').toUpperCase()
})

/** Eigene Adresse eines Artikels — EIN Ort, den auch die Liste benutzt. */
function adresseFuer(id) { return `#/wiki/${encodeURIComponent(id)}` }

/**
 * Link auf einen ähnlichen Artikel (MT-7b). Das Ziel von „‹ zurück“ ist die
 * Listen-Adresse im Merker — die bleibt stehen, auch wenn der Nutzer von hier
 * auf einen weiteren Artikel springt. `preventDefault` NUR für den eigenen
 * Routenwechsel: ein Mittelklick, Strg-/Umschalt-/Alt-Klick muss den Link
 * normal öffnen (neuer Tab) — vorher lief die Prüfung NACH dem Abschalten des
 * Browser-Verhaltens, und der erwartete neue Tab kam nie.
 */
function artikelOeffnen(ereignis) {
  // Mittelklick/Modifier öffnet einen NEUEN Tab — der Browser entscheidet,
  // der Router greift nicht ein.
  if (ereignis && (ereignis.button > 0 || ereignis.metaKey || ereignis.ctrlKey || ereignis.shiftKey || ereignis.altKey)) return
  ereignis?.preventDefault?.()
  navigate(ereignis?.currentTarget?.getAttribute?.('href') || zurueckZiel.value)
}

const aehnliche = computed(() => {
  const jetzt = artikel.value
  if (!jetzt) return []
  const meine = new Set(tags.value)
  if (!meine.size) return []
  return alleArtikel.value
    .filter((a) => a.id !== jetzt.id && (a.tags || []).some((t) => meine.has(t)))
    .slice(0, 3)
})

/**
 * Zurück (MT-7b): KEIN Push — der Knopf ERSETZT den eigenen Verlaufs-Eintrag
 * durch die Listen-Adresse aus dem Merker (mit Filtern), sonst durch das Wiki
 * ohne Filter. Ein geteilter Link (ohne Merker) landet damit ebenfalls in der
 * Liste und nicht irgendwo außerhalb der App. Vorher lief `navigate(ziel)`:
 * das legte einen neuen Eintrag an, und der Zurück-Knopf des Browsers führte
 * wieder auf die Leseseite (Zurück-Falle).
 *
 * `preventDefault` erst NACH der Modifier-Prüfung (wie bei „Ähnliche
 * Artikel“): Strg-/Umschalt-/Mittelklick soll den Link normal in einem neuen
 * Tab öffnen — `@click.prevent` in der Vorlage hätte ihm das genommen.
 */
function zurueck(ereignis) {
  if (ereignis && (ereignis.button > 0 || ereignis.metaKey || ereignis.ctrlKey || ereignis.shiftKey || ereignis.altKey)) return
  ereignis?.preventDefault?.()
  rueckwegErsetzen('#/wiki')
}

async function ladenDaten() {
  const id = artikelId.value
  if (!id) {
    fehlerZustand.value = 'weg'
    fehler.value = fehlertext(null, { zustand: 'weg' })
    laden.value = false
    return
  }
  laden.value = true
  fehler.value = ''
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_detail', { artikel_id: id })
    if (!res) {
      artikel.value = null
      fehlerZustand.value = 'weg'
      fehler.value = fehlertext(null, { zustand: 'weg' })
      return
    }
    artikel.value = res
  } catch (err) {
    // UX2g (Review-Punkt 4): „nicht gefunden“ (DoesNotExistError/404) und
    // „keine Berechtigung“ (403) sind eigene Sätze; „Prüfe die Verbindung …“
    // stand hier vorher für JEDEN Fall.
    fehlerZustand.value = zustandFuer({ status: err?.status, excType: err?.exc_type || err?.excType })
    fehler.value = fehlertext(err, { zustand: fehlerZustand.value })
  } finally {
    laden.value = false
  }
  // MT-7b (Review-Punkt B): Der Fokus wird NACH `laden = false` gesetzt. Vorher
  // lief er im Versuch, solange `laden` noch wahr war — bei einer Antwort über
  // 300 ms stand dort das Ladeskelett, der Seitenkopf existierte noch gar nicht,
  // und der Fokus blieb auf `body`.
  await nextTick()
  if (artikel.value) fokusAufTitel()
}

async function listeLaden() {
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.get_wiki_artikel_liste', {})
    alleArtikel.value = Array.isArray(res) ? res : []
  } catch {
    alleArtikel.value = []
  }
}

/* ── Objekt-Aktionen (N6) — dieselben Einträge wie in der Liste ─────────── */
function bearbeiten() {
  navigate(`#/wiki?bearbeiten=${encodeURIComponent(artikel.value.id)}`)
}
async function loeschen() {
  const ziel = artikel.value
  if (!ziel) return
  // MT-7b: Auch nach dem Löschen zurück auf die gemerkte Listen-Adresse —
  // VOR dem Sprung lesen, denn der Merker gehört der Liste.
  const rueckweg = zurueckZiel.value
  try {
    const res = await apiCall('diakronos.diakonos.api.wiki.delete_wiki_artikel', { artikel_id: ziel.id })
    if (!res?.success) return
    navigate(rueckweg)
    await mitRueckgaengig({
      beschreibung: papierkorbMeldung(ziel.title, res.wiederherstellbar_bis),
      zurueck: () => wiederherstellen('artikel', ziel.id),
      erfolg: `„${ziel.title}“ wiederhergestellt.`,
    })
  } catch (e) {
    showToast(aktionsfehler('löschen', e), 'error')
  }
}
const aktionen = computed(() => {
  if (!isAdmin.value || !artikel.value) return []
  return [
    { key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten', aktion: bearbeiten },
    { key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true, aktion: loeschen },
  ]
})

/**
 * Fokus auf die Überschrift der Seite (Review-Punkt 7): nach dem Aufbau einer
 * Detailseite stünde der Fokus sonst auf `body`. `tabindex="-1"` macht die h1
 * programmatisch erreichbar, ohne sie in den Tab-Strom zu nehmen.
 */
function fokusAufTitel() {
  const el = kopf.value?.$el?.querySelector?.('.dk-ui-pageheader-titel')
  if (!el) return
  el.setAttribute('tabindex', '-1')
  el.focus({ preventScroll: true })
}

/* ── Anzeige ─────────────────────────────────────────────────────────────── */
/** ZEIT-2: `updatedAt` ist ein Datum (`YYYY-MM-DD`) — bleibt der Tag. */
function formatDate(d) {
  if (!d) return ''
  const tag = serverDatum(d)
  if (!tag) return ''
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: GEMEINDE_ZONE,
  }).format(tag)
}

onMounted(async () => {
  await ladenDaten()
  listeLaden()
})
watch(artikelId, () => { if (artikelId.value) ladenDaten() })
</script>

<style scoped>
/* ── Leseansicht ─────────────────────────────────────────────────────────────
   Eine Fläche, Lesebreite (--lesebreite), kein Rahmen (Ä2). */
.wk-lese {
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  padding: var(--pad);
}

.wk-lese-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: var(--sp-3);
}
.wk-lese-person { display: flex; align-items: center; gap: var(--sp-2); }
.wk-lese-tags { display: flex; flex-wrap: wrap; gap: var(--sp-1); margin-bottom: var(--sp-4); }

.wk-lese-inhalt { font-size: var(--fs); line-height: 1.7; color: var(--text); }
.wk-lese-inhalt :deep(p) { margin: 0 0 var(--sp-3); }
.wk-lese-inhalt :deep(ul),
.wk-lese-inhalt :deep(ol) { margin: 0 0 var(--sp-3); padding-left: var(--sp-5); }
.wk-lese-inhalt :deep(li) { margin-bottom: var(--sp-1); }
.wk-lese-inhalt :deep(h3) { font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); margin: var(--sp-5) 0 var(--sp-2); }
.wk-lese-inhalt :deep(a) { color: var(--primary); text-decoration: none; }
.wk-lese-inhalt :deep(a:hover) { text-decoration: underline; }
.wk-lese-inhalt :deep(table) { width: 100%; border-collapse: collapse; }
/* Ä2/S3: Tabellenzellen trennen sich über Abstand, nicht über Linien. */
.wk-lese-inhalt :deep(td) { padding: var(--sp-2); }
.wk-lese-inhalt :deep(img) { max-width: 100%; height: auto; }
.wk-lese-inhalt :deep(strong) { color: var(--text); }

/* Ähnliche Artikel */
.wk-lese-aehnlich { margin-top: var(--sp-6); }
.wk-lese-zwischentitel { font-size: var(--fs-h4); font-weight: var(--fw-h); color: var(--text); margin: 0 0 var(--sp-3); }
.wk-lese-aehnlich-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.wk-lese-aehnlich-link {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text);
  font-size: var(--fs-sm);
  text-decoration: none;
  transition: background var(--fast) var(--ease);
}
.wk-lese-aehnlich-link:hover { background: var(--surface-hover); }
/* Symbol auf der Textlinie (Auflage 04.11.): feste Größe je Schriftstufe,
   gleiche optische Mitte wie der Text daneben. */
.wk-lese-aehnlich-symbol { display: inline-flex; align-items: center; color: var(--muted); }

/* Kopf-Aktionen: „‹ zurück“ — Pfeil auf der Textlinie (gleiche optische Mitte). */
.wk-lese-aktionen { display: flex; align-items: center; justify-content: flex-end; margin-bottom: var(--sp-3); }
.wk-pfeil { display: inline-flex; align-items: center; line-height: 1; font-size: var(--fs-h4); margin-right: var(--sp-1); }

/* Fehlerzustand */
.wk-lese-fehler { display: flex; flex-direction: column; gap: var(--sp-4); padding: var(--pad); }
.wk-lese-fehlertext { margin: 0; font-size: var(--fs); color: var(--text); }
.wk-lese-fehlerknoepfe { display: flex; gap: var(--sp-3); flex-wrap: wrap; }

@media (max-width: 700px) {
  .wk-lese-aktionen { justify-content: flex-start; }
  .wk-lese-aehnlich-link { min-height: var(--control-h); }
}

/* Druck: nur der Artikel, ohne Gerüst — volle Breite, ohne Schatten. */
@media print {
  /* MT-7c: „‹ zurück“ sitzt im `#actions`-Slot des Seitenkopfs und wurde
     mitgedruckt (ausgeblendet war nur die Objekt-Aktionen-Leiste). */
  .wk-zurueck { display: none; }
  .wk-lese-aktionen { display: none; }
  .wk-lese { box-shadow: none; padding: 0; background: transparent; }
  .wk-lese-inhalt { max-width: none; }
}
</style>
